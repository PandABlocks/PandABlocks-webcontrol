import os
import unittest

from malcolm.annotypes import json_decode
from malcolm.core import Return
from malcolm.modules.web.parts import WebsocketServerPart
from malcolm.modules.web.parts.websocketserverpart import MalcWebSocketHandler
from mock import Mock, patch

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


class TestMalcWebSocketHandlerResponses(unittest.TestCase):
    """on_response runs on the event loop, so it must never block there"""

    def make_handler(self):
        handler = MalcWebSocketHandler.__new__(MalcWebSocketHandler)
        handler.initialize()
        handler.write_message = Mock()
        return handler

    @on_loop
    async def test_writes_every_response(self):
        # This used to hand each write to the IOLoop and then block every
        # tenth response waiting for those writes to finish. That was safe
        # from a worker thread, but on the event loop it is the loop waiting
        # for work only the loop can do, so the client stopped getting
        # updates after the tenth response and the UI showed stale state.
        handler = self.make_handler()
        for i in range(25):
            handler.on_response(Return(id=i, value=i))
        assert handler.write_message.call_count == 25

    @on_loop
    async def test_writes_stay_in_order(self):
        # Deltas are only meaningful in order, so responses must not be
        # scheduled in a way that lets them overtake each other
        handler = self.make_handler()
        for i in range(25):
            handler.on_response(Return(id=i, value=i))
        sent = [
            json_decode(c[0][0])["value"]
            for c in handler.write_message.call_args_list
        ]
        assert sent == list(range(25))
