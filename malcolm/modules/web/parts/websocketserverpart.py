import asyncio
import fcntl
import logging
import os
import socket
import struct
from typing import Optional

from tornado.websocket import WebSocketError, WebSocketHandler

from malcolm.annotypes import (
    Anno,
    add_call_types,
    deserialize_object,
    json_decode,
    json_encode,
)
from malcolm.core import (
    Error,
    FieldError,
    Part,
    PartRegistrar,
    Post,
    Put,
    Request,
    Response,
    Subscribe,
    Unsubscribe,
)
from malcolm.modules import builtin

from ..hooks import ReportHandlersHook, UHandlerInfos
from ..infos import HandlerInfo

# Create a module level logger
log = logging.getLogger(__name__)

# Signals we can send to get info
SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891B

# Where we get info about interfaces on Linux
SYSNET = "/sys/class/net"


def get_if_info(s, sig, ifname):
    # Use an ioctl to get interface address or netmask
    packed_ifname = struct.pack("256s", ifname[:15].encode())
    info = fcntl.ioctl(s.fileno(), sig, packed_ifname)
    return struct.unpack("!I", info[20:24])[0]


def get_ip_validator(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ifaddr = get_if_info(s, SIOCGIFADDR, ifname)
    ifnetmask = get_if_info(s, SIOCGIFNETMASK, ifname)

    def validator(remoteaddr):
        return remoteaddr & ifnetmask == ifaddr & ifnetmask

    return validator


# For some reason tornado doesn't make us implement all abstract methods
# noinspection PyAbstractClass
class MalcWebSocketHandler(WebSocketHandler):
    # How many responses may be waiting to go out to one client before we give
    # up on it. A client that can't keep up would otherwise grow Tornado's
    # write buffer without limit, and dropping the odd response is not an
    # option: Deltas only mean anything applied in order and in full
    MAX_QUEUED_RESPONSES = 1000

    _registrar: PartRegistrar
    _id_to_mri: dict[int, str]
    _responses: "asyncio.Queue"
    _writer: Optional["asyncio.Future"] = None
    _validators = None
    # Left False until open() works it out, so the safe answer wins if we are
    # ever asked before then
    _writeable = False
    _closed = False

    def initialize(self, registrar=None, validators=()):
        self._registrar = registrar
        # {id: mri}
        self._id_to_mri = {}
        self._validators = validators
        self._responses = asyncio.Queue(maxsize=self.MAX_QUEUED_RESPONSES)

    def open(self, *args, **kwargs):
        # Work out once, when the connection opens, whether the remote ip is
        # within the netmask of any of our interfaces. If not, Put and Post are
        # forbidden for the life of the connection
        ipv4_ip = self.request.remote_ip
        if ipv4_ip == "::1":
            # Special case IPV6 loopback
            ipv4_ip = "127.0.0.1"
        remoteaddr = struct.unpack("!I", socket.inet_aton(ipv4_ip))[0]
        if self._validators:
            self._writeable = any(v(remoteaddr) for v in self._validators)
        else:
            self._writeable = True
        log.info(
            "Puts and Posts are %s from %s",
            "allowed" if self._writeable else "forbidden",
            self.request.remote_ip,
        )

    async def on_message(self, message):
        # called on the event loop
        msg_id = -1
        try:
            d = json_decode(message)
            try:
                msg_id = d["id"]
            except KeyError as e:
                raise FieldError("id field not present in JSON message") from e
            request = deserialize_object(d, Request)
            request.set_callback(self.on_response)
            if isinstance(request, Subscribe):
                if msg_id in self._id_to_mri:
                    raise FieldError(f"Duplicate subscription ID {msg_id}")
                self._id_to_mri[msg_id] = request.path[0]
            if isinstance(request, Unsubscribe):
                # An Unsubscribe carries no path, so the mri comes from the
                # Subscribe it cancels. Take the entry out as we go: the id is
                # the client's to reuse once it has unsubscribed
                mri = self._id_to_mri.pop(msg_id)
            else:
                mri = request.path[0]
            if isinstance(request, (Put, Post)) and not self._writeable:
                raise ValueError(f"Put/Post is forbidden from {self.request.remote_ip}")
            self._registrar.report(builtin.infos.RequestInfo(request, mri))
        except Exception as e:
            log.exception("Error handling message:\n%s", message)
            # Out through the queue like any other response, so an error can't
            # overtake the responses that were produced before it
            self.on_response(Error(msg_id, e))

    def on_response(self, response: Response) -> None:
        # Called on the event loop, by the Controller that handled a request or
        # by the Notifier when a value changed. Queue the response rather than
        # writing it here: awaiting the write is what gives us flow control,
        # and this is called from sync code that cannot await. Writing straight
        # from here left nothing bounding the write buffer for a slow client
        if self._closed:
            # Nothing to write to, and the subscriptions are being torn down
            return
        if self._writer is None:
            self._writer = asyncio.ensure_future(self._write_responses())
        try:
            self._responses.put_nowait(response)
        except asyncio.QueueFull:
            # This client is too far behind to catch up. Deltas are only
            # meaningful in order and in full, so dropping responses would
            # silently desync its model: drop the connection and let it
            # reconnect, which resubscribes from a known state
            log.warning(
                "Closing websocket: %d responses queued and unsent",
                self._responses.qsize(),
            )
            self._closed = True
            self.close(1011, "Client too slow to keep up")

    async def _write_responses(self) -> None:
        # One writer per connection, so responses go out in the order they were
        # produced, and awaiting each write means a slow client slows the queue
        # down rather than growing the write buffer without limit
        while True:
            response = await self._responses.get()
            try:
                await self.write_message(json_encode(response))
            except WebSocketError:
                # The websocket is dead. Awaiting the write catches this
                # whether it failed straight away or once the write was under
                # way, which writing without awaiting did not
                log.info("WebSocket write failed, dropping the connection")
                self._closed = True
                self._unsubscribe_all()
                return
            finally:
                self._responses.task_done()

    def on_close(self) -> None:
        self._closed = True
        self._unsubscribe_all()
        if self._writer is not None:
            self._writer.cancel()
            self._writer = None

    def _unsubscribe_all(self) -> None:
        """Unsubscribe everything this connection still holds a subscription to

        Otherwise the Controllers keep producing Deltas for a socket nobody is
        reading. This used to happen only when a write failed, which missed
        both a clean close and a write that failed after it had started.
        """
        if not self._registrar:
            return
        while self._id_to_mri:
            msg_id, mri = self._id_to_mri.popitem()
            log.info("Unsubscribing %s from %s for a closed websocket", msg_id, mri)
            unsubscribe = Unsubscribe(msg_id)
            # The Notifier matches a subscription on (callback, id), so this
            # has to carry the same callback the Subscribe did. on_response
            # drops the Return it produces, as we are closed by now
            unsubscribe.set_callback(self.on_response)
            self._registrar.report(builtin.infos.RequestInfo(unsubscribe, mri))

    # http://stackoverflow.com/q/24851207
    # TODO: remove this when the web gui is hosted from the box
    def check_origin(self, origin):
        return True


with Anno("Part name and subdomain name to host websocket on"):
    AName = str
with Anno("If True, check any client is in the same subnet as the host"):
    ASubnetValidation = bool


class WebsocketServerPart(Part):
    def __init__(
        self, name: AName = "ws", subnet_validation: ASubnetValidation = True
    ) -> None:
        super().__init__(name)
        self.subnet_validation = subnet_validation

    def setup(self, registrar: PartRegistrar) -> None:
        super().setup(registrar)
        # Hooks
        registrar.hook(ReportHandlersHook, self.on_report_handlers)

    @staticmethod
    def is_interface_up(ifname: str) -> bool:
        with open(os.path.join(SYSNET, ifname, "operstate")) as f:
            return f.read() != "down\n"

    @add_call_types
    def on_report_handlers(self) -> UHandlerInfos:
        validators = []
        if self.subnet_validation:
            # Try creating an ip validator for every interface that is up
            for ifname in os.listdir(SYSNET):
                if self.is_interface_up(ifname):
                    try:
                        validators.append(get_ip_validator(ifname))
                    except OSError as exception_message:
                        # Ignore any interfaces that fail
                        log.warning(
                            "%s - failed to create IP validator for %s (skipping): %s",
                            self.name,
                            ifname,
                            exception_message,
                        )
            # Check we have at least one created validator
            assert len(validators) > 0, "Failed to create any IP validators!"

        info = HandlerInfo(
            f"/{self.name}",
            MalcWebSocketHandler,
            registrar=self.registrar,
            validators=validators,
        )
        return info
