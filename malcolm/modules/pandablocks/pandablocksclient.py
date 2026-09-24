import asyncio
import logging
from collections import OrderedDict, namedtuple

# Create a module level logger
log = logging.getLogger(__name__)

# Longest single line we will accept from the PandA
LINE_LIMIT = 2**20


BlockData = namedtuple("BlockData", "number,description,fields")
FieldData = namedtuple("FieldData", "field_type,field_subtype,description,labels")
TableFieldData = namedtuple(
    "TableFieldData", "bits_hi,bits_lo,description,labels,signed"
)


def strip_ok(resp):
    assert resp.startswith("OK ="), f"Expected 'OK =val', got {resp!r}"
    value = resp[4:]
    return value


class PandABlocksClient:
    # Sentinel that tells the send_loop and recv_loop to stop
    STOP = object()

    def __init__(self, hostname="localhost", port=8888, queue_cls=None):
        if queue_cls is None:
            from queue import Queue as queue_cls
        self.queue_cls = queue_cls
        self.hostname = hostname
        self.port = port
        # Completed lines for a response in progress
        self._completed_response_lines = []
        # True if the current response is multiline
        self._is_multiline = None
        # True when we have been started
        self.started = False
        # Filled in on start
        self._spawn = None
        self._loop = None
        self._reader = None
        self._writer = None
        self._send_spawned = None
        self._send_queue = None
        self._recv_spawned = None
        self._response_queues = None

    def start(self, spawn):
        """Connect to the PandA and start servicing the connection

        Args:
            spawn: Callable returning something with wait()/get(), used to run
                the send and recv coroutines on an event loop
        """
        assert not self.started, "Send and recv loops already started"
        self._spawn = spawn
        # Connect on the event loop, and wait here until it has happened
        spawn(self._connect).get()
        self._send_spawned = spawn(self._send_loop)
        self._recv_spawned = spawn(self._recv_loop)
        self.started = True

    async def _connect(self):
        # We are on the event loop, so remember it: send() is called from
        # worker threads and has to hand messages over to this loop
        self._loop = asyncio.get_running_loop()
        # Holds (message, response_queue) to send next
        self._send_queue = asyncio.Queue()
        # Holds response_queue to send next
        self._response_queues = asyncio.Queue()
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.hostname, self.port, limit=LINE_LIMIT
            )
        except OSError as e:
            raise ConnectionError(
                f"Can't connect to '{self.hostname}:{self.port}', "
                "did all services on the PandA start correctly?"
            ) from e

    def stop(self):
        assert self.started, "Send and recv loops not started"
        self._queue_send((self.STOP, None))
        self._send_spawned.wait()
        # Closing the write side gives the recv loop its EOF
        self._spawn(self._close).get()
        self._recv_spawned.wait()
        self._loop = None
        self._reader = None
        self._writer = None
        self.started = False

    async def _close(self):
        self._writer.close()
        try:
            await self._writer.wait_closed()
        except OSError:
            # The PandA has gone away, which is what we wanted anyway
            pass

    def _queue_send(self, item):
        """Hand an item to the send loop from whatever thread we are on"""
        self._loop.call_soon_threadsafe(self._send_queue.put_nowait, item)

    def send(self, message):
        response_queue = self.queue_cls()
        self._queue_send((message, response_queue))
        return response_queue

    def recv(self, response_queue, timeout=10.0):
        response = response_queue.get(timeout=timeout)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    def send_recv(self, message, timeout=10.0):
        """Send a message to a PandABox and wait for the response

        Args:
            message (str): The message to send
            timeout (float): How long to wait before raising queue.Empty

        Returns:
            str: The response
        """
        response_queue = self.send(message)
        response = self.recv(response_queue, timeout)
        return response

    async def _send_loop(self):
        """Service self._send_queue, sending requests to server"""
        while True:
            message, response_queue = await self._send_queue.get()
            if message is self.STOP:
                break
            try:
                self._response_queues.put_nowait(response_queue)
                self._writer.write(message.encode("utf-8"))
                await self._writer.drain()
            except Exception:  # pylint:disable=broad-except
                log.exception("Exception sending message %s", message)

    async def _get_line(self):
        """Return the next complete line, or None at end of stream"""
        line = await self._reader.readline()
        if not line.endswith(b"\n"):
            # End of stream. Anything left is an incomplete line, which we
            # drop, as we never had a whole response to make of it
            return None
        return line[:-1].decode("utf-8")

    async def _respond(self, resp):
        """Respond to the person waiting"""
        response_queue = await asyncio.wait_for(self._response_queues.get(), 0.1)
        response_queue.put(resp)
        self._completed_response_lines = []
        self._is_multiline = None

    async def _recv_loop(self):
        """Service the connection, returning responses to the correct queue"""
        self._completed_response_lines = []
        self._is_multiline = None
        while True:
            try:
                line = await self._get_line()
                if line is None:
                    return
                if self._is_multiline is None:
                    self._is_multiline = line.startswith("!") or line == "."
                if line.startswith("ERR"):
                    await self._respond(ValueError(line))
                elif self._is_multiline:
                    if line == ".":
                        await self._respond(self._completed_response_lines)
                    else:
                        assert (
                            line[0] == "!"
                        ), f"Multiline response {repr(line)} doesn't start with !"
                        self._completed_response_lines.append(line[1:])
                else:
                    await self._respond(line)
            except Exception:
                log.exception("Exception receiving message")
                raise

    def _get_block_numbers(self):
        block_numbers = OrderedDict()
        for line in self.send_recv("*BLOCKS?\n"):
            block_name, number = line.split()
            block_numbers[block_name] = int(number)
        return block_numbers

    def parameterized_send(self, request, parameter_list):
        """Send batched requests for a list of parameters

        Args:
            request (str): Request to send, like "%s.*?\n"
            parameter_list (list): parameters to format with, like
                ["TTLIN", "TTLOUT"]

        Returns:
            dict: {parameter: response_queue}
        """
        response_queues = OrderedDict()
        for parameter in parameter_list:
            response_queues[parameter] = self.send(request % parameter)
        return response_queues

    def get_blocks_data(self):
        blocks = OrderedDict()

        # Get details about number of blocks
        block_numbers = self._get_block_numbers()
        block_names = list(block_numbers)

        # Queue up info about each block
        desc_queues = self.parameterized_send("*DESC.%s?\n", block_names)
        field_queues = self.parameterized_send("%s.*?\n", block_names)

        # Create BlockData for each block
        # TODO: we sort here while server gives these in hash table order
        for block_name in sorted(block_names):
            number = block_numbers[block_name]
            description = strip_ok(self.recv(desc_queues[block_name]))
            fields = OrderedDict()
            blocks[block_name] = BlockData(number, description, fields)

            # Parse the field list
            unsorted_fields = {}
            for line in self.recv(field_queues[block_name]):
                split = line.split()
                assert len(split) in (
                    3,
                    4,
                ), f"Expected field_data to have len 3 or 4, got {len(split)}"
                if len(split) == 3:
                    split.append("")
                field_name, index, field_type, field_subtype = split
                unsorted_fields[field_name] = (int(index), field_type, field_subtype)

            # Sort the field list
            def get_field_index(field_name):
                return unsorted_fields[field_name][0]

            field_names = sorted(unsorted_fields, key=get_field_index)

            # Request description for each field
            field_desc_queues = self.parameterized_send(
                "*DESC.%s.%%s?\n" % block_name, field_names
            )

            # Request enum labels for fields that are enums
            enum_fields = []
            for field_name in field_names:
                _, field_type, field_subtype = unsorted_fields[field_name]
                if field_type in ("bit_mux", "pos_mux") or field_subtype == "enum":
                    enum_fields.append(field_name)
                elif field_type == "ext_out":
                    enum_fields.append(field_name + ".CAPTURE")
            enum_queues = self.parameterized_send(
                "*ENUMS.%s.%%s?\n" % block_name, enum_fields
            )

            # Get desc and enum data for each field
            for field_name in field_names:
                _, field_type, field_subtype = unsorted_fields[field_name]
                if field_name in enum_queues:
                    labels = self.recv(enum_queues[field_name])
                elif field_name + ".CAPTURE" in enum_queues:
                    labels = self.recv(enum_queues[field_name + ".CAPTURE"])
                else:
                    labels = []
                description = strip_ok(self.recv(field_desc_queues[field_name]))
                fields[field_name] = FieldData(
                    field_type, field_subtype, description, labels
                )

        return blocks

    def get_pcap_bits_fields(self):
        # {field_to_set: [bit_names]}
        # E.g. {"PCAP.BITS0"=["TTLIN1.VAL", "TTLIN2.VAL", ...], ...}
        bits_fields = []
        for line in self.send_recv("PCAP.*?\n"):
            split = line.split()
            if len(split) == 4:
                field_name, _, field_type, field_subtype = split
                if field_type == "ext_out" and field_subtype == "bits":
                    bits_fields.append(f"PCAP.{field_name}")
        bits_queues = self.parameterized_send("%s.BITS?\n", sorted(bits_fields))
        bits = OrderedDict()
        for k, queue in bits_queues.items():
            bits[k + ".CAPTURE"] = self.recv(queue)
        return bits

    def get_changes(self, include_errors=False):
        table_queues = {}
        for line in self.send_recv("*CHANGES?\n"):
            if "=" in line:
                field, val = line.split("=", 1)
            elif line[-1] == "<":
                # table
                field = line[:-1]
                val = None
                table_queues[field] = self.send(f"{field}?\n")
            elif line.endswith("(error)"):
                if include_errors:
                    field = line.split(" ", 1)[0]
                    val = Exception
                else:
                    continue
            else:
                log.warning("Can't parse line %r of changes", line)
                continue
            yield field, val
        for field, q in table_queues.items():
            yield field, self.recv(q)

    def get_table_fields(self, block, field):
        fields = OrderedDict()
        enum_queues = {}
        for line in self.send_recv(f"{block}.{field}.FIELDS?\n"):
            split = line.split()
            name = split[1].strip()
            signed = False
            if len(split) > 2:
                # Field is an enum, get its values
                if split[2] == "enum":
                    enum_queues[name] = self.send(f"*ENUMS.{block}.{field}[].{name}?\n")
                elif split[2] == "int":
                    signed = True
            fields[name] = (split[0], signed)

        # Request description for each field
        desc_queues = self.parameterized_send(
            "*DESC.%s.%s[].%%s?\n" % (block, field), list(fields)
        )
        for name, (bits_str, signed) in fields.items():
            bits_hi, bits_lo = [int(x) for x in bits_str.split(":")]
            description = strip_ok(self.recv(desc_queues[name]))
            if name in enum_queues:
                labels = self.recv(enum_queues[name])
            else:
                labels = None
            fields[name] = TableFieldData(bits_hi, bits_lo, description, labels, signed)
        return fields

    def get_field(self, block, field):
        try:
            resp = self.send_recv(f"{block}.{field}?\n")
        except ValueError as e:
            raise ValueError(f"Error getting {block}.{field}: {e}")
        else:
            return strip_ok(resp)

    def set_field(self, block, field, value):
        self.set_fields({f"{block}.{field}": value})

    def set_fields(self, field_values):
        queues = OrderedDict()
        for field, value in field_values.items():
            message = f"{field}={value}\n"
            queues[(field, value)] = self.send(message)
        for (field, value), queue in queues.items():
            try:
                resp = self.recv(queue)
            except ValueError as e:
                raise ValueError(f"Error setting {field} to {value!r}: {e}")
            else:
                assert resp == "OK", f"Expected OK, got {resp!r}"

    def set_table(self, block, field, int_values):
        lines = [f"{block}.{field}<\n"]
        lines += [f"{int_value}\n" for int_value in int_values]
        lines += ["\n"]
        resp = self.send_recv("".join(lines))
        assert resp == "OK", f"Expected OK, got {resp!r}"
