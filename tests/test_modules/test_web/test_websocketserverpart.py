import asyncio
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

from malcolm.annotypes import json_decode
from malcolm.core import Error, Return, Subscribe, Unsubscribe
from malcolm.modules.web.parts import WebsocketServerPart
from malcolm.modules.web.parts.websocketserverpart import MalcWebSocketHandler

from ...loop import on_loop


@patch("malcolm.modules.web.parts.websocketserverpart.get_ip_validator")
@patch.object(WebsocketServerPart, "is_interface_up")
@patch.object(os, "listdir")
class TestWebsocketServerPart(unittest.TestCase):
    def test_on_report_handlers_with_subnet_validation_succeeds_for_one_good_interface(
        self, mock_os_listdir, mock_is_interface_up, mock_get_ip_validator
    ):
        # Return our fake interfaces
        mock_os_listdir.return_value = ["interface_1", "interface_2", "interface_3"]
        # The state of the interfaces - 2 are "up"
        mock_is_interface_up.side_effect = [True, False, True]
        # Return a pretend validator and one error
        mock_get_ip_validator.side_effect = ["validator_1", OSError()]

        websocket_server_part = WebsocketServerPart()

        info = websocket_server_part.on_report_handlers()

        # We should only have one validator
        assert info.kwargs["validators"] == ["validator_1"]

    def test_on_report_handlers_fails_with_subnet_validation_with_no_good_interfaces(
        self, mock_os_listdir, mock_is_interface_up, mock_get_ip_validator
    ):
        # Return our fake interfaces
        mock_os_listdir.return_value = ["interface_1", "interface_2", "interface_3"]
        # The state of the interfaces
        mock_is_interface_up.side_effect = [False, False, True]
        # Pretend validators
        mock_get_ip_validator.side_effect = [OSError()]

        websocket_server_part = WebsocketServerPart()

        self.assertRaises(AssertionError, websocket_server_part.on_report_handlers)


def make_handler(registrar=None, maxsize=None):
    handler = MalcWebSocketHandler.__new__(MalcWebSocketHandler)
    handler.initialize(registrar=registrar)
    if maxsize is not None:
        handler._responses = asyncio.Queue(maxsize=maxsize)
    # Real write_message hands back a Future, so the writer can await it
    handler.write_message = AsyncMock()
    handler.close = Mock()
    # open() would have worked this out from the client's ip
    handler._writeable = True
    return handler


def subscribe_message(msg_id, mri):
    return (
        '{"typeid": "malcolm:core/Subscribe:1.0", '
        f'"id": {msg_id}, "path": ["{mri}", "health"]}}'
    )


def unsubscribe_message(msg_id):
    return f'{{"typeid": "malcolm:core/Unsubscribe:1.0", "id": {msg_id}}}'


def reported_requests(registrar):
    return [c[0][0].request for c in registrar.report.call_args_list]


class TestMalcWebSocketHandlerResponses(unittest.TestCase):
    """on_response runs on the event loop, so it must never block there"""

    @on_loop
    async def test_writes_every_response(self):
        # This used to hand each write to the IOLoop and then block every
        # tenth response waiting for those writes to finish. That was safe
        # from a worker thread, but on the event loop it is the loop waiting
        # for work only the loop can do, so the client stopped getting
        # updates after the tenth response and the UI showed stale state.
        handler = make_handler()
        for i in range(25):
            handler.on_response(Return(id=i, value=i))
        await handler._responses.join()
        assert handler.write_message.call_count == 25
        handler.on_close()

    @on_loop
    async def test_writes_stay_in_order(self):
        # Deltas are only meaningful in order, so responses must not be
        # scheduled in a way that lets them overtake each other
        handler = make_handler()
        for i in range(25):
            handler.on_response(Return(id=i, value=i))
        await handler._responses.join()
        sent = [
            json_decode(c[0][0])["value"] for c in handler.write_message.call_args_list
        ]
        assert sent == list(range(25))
        handler.on_close()

    @on_loop
    async def test_a_client_that_cannot_keep_up_is_dropped(self):
        # Nothing bounded the outbound buffer once the writes stopped being
        # waited on: a client slower than the poll loop grew it without limit.
        # Queue is size 3 and nothing is awaited here, so the writer never
        # gets a chance to drain it
        handler = make_handler(maxsize=3)
        for i in range(4):
            handler.on_response(Return(id=i, value=i))
        assert handler.close.called
        assert handler._closed is True
        # Further responses are dropped rather than queued for a dead socket
        handler.on_response(Return(id=99, value=99))
        assert handler._responses.qsize() == 3
        handler.on_close()

    @on_loop
    async def test_a_dead_socket_unsubscribes(self):
        # The Controllers keep producing Deltas until they are told not to
        registrar = Mock()
        handler = make_handler(registrar=registrar)
        await handler.on_message(subscribe_message(1, "BLOCK1"))
        await handler.on_message(subscribe_message(2, "BLOCK2"))
        assert handler._id_to_mri == {1: "BLOCK1", 2: "BLOCK2"}

        handler.on_close()

        unsubscribes = [
            r for r in reported_requests(registrar) if isinstance(r, Unsubscribe)
        ]
        assert sorted(r.id for r in unsubscribes) == [1, 2]
        # The Notifier matches a subscription on (callback, id), so the
        # Unsubscribe has to carry the callback the Subscribe did
        assert all(r.callback == handler.on_response for r in unsubscribes)
        assert handler._id_to_mri == {}


class TestMalcWebSocketHandlerSubscriptions(unittest.TestCase):
    @on_loop
    async def test_unsubscribe_frees_the_id_for_reuse(self):
        # The id was only ever removed when a write failed, so a client that
        # unsubscribed and reused the id got an error instead of a
        # subscription, and the map grew for the life of the connection
        registrar = Mock()
        handler = make_handler(registrar=registrar)

        await handler.on_message(subscribe_message(1, "BLOCK1"))
        await handler.on_message(unsubscribe_message(1))
        assert handler._id_to_mri == {}
        await handler.on_message(subscribe_message(1, "BLOCK2"))

        requests = reported_requests(registrar)
        assert [type(r) for r in requests] == [Subscribe, Unsubscribe, Subscribe]
        # The Unsubscribe is routed to the mri the Subscribe was for
        assert [c[0][0].mri for c in registrar.report.call_args_list] == [
            "BLOCK1",
            "BLOCK1",
            "BLOCK2",
        ]
        assert handler._id_to_mri == {1: "BLOCK2"}
        assert handler._responses.qsize() == 0
        handler.on_close()

    @on_loop
    async def test_a_live_id_cannot_be_subscribed_twice(self):
        registrar = Mock()
        handler = make_handler(registrar=registrar)

        await handler.on_message(subscribe_message(1, "BLOCK1"))
        await handler.on_message(subscribe_message(1, "BLOCK2"))

        # The second one is refused, and the first is left alone
        assert handler._id_to_mri == {1: "BLOCK1"}
        assert len(reported_requests(registrar)) == 1
        error = handler._responses.get_nowait()
        assert isinstance(error, Error)
        assert error.id == 1
        assert "Duplicate subscription ID 1" in str(error.message)
        handler.on_close()
