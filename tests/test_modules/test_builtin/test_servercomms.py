import asyncio
import unittest

from malcolm.core import Get, Process
from malcolm.modules.builtin.controllers import BasicController, ServerComms
from malcolm.modules.builtin.infos import RequestInfo

from ...loop import on_loop


class TestRequestRouting(unittest.TestCase):
    """An mri of "." means the ServerComms Block itself

    The web GUI Gets [".", "blocks"] off the websocket to find out what Blocks
    the process has, so this is the route it starts up through. Nothing is
    registered under "." for process.get_controller() to find, so routing it
    like any other mri fails with "No controller registered for mri '.'".
    """

    def setUp(self):
        self.process = Process("proc")
        self.o = ServerComms(mri="WS")
        self.process.add_controller(self.o)
        self.process.add_controller(BasicController(mri="OTHER"))
        self.process.start()

    def tearDown(self):
        self.process.stop(timeout=10)

    async def get_via(self, msg_id, mri, path):
        responses: asyncio.Queue = asyncio.Queue()
        request = Get(id=msg_id, path=path)
        request.set_callback(responses.put_nowait)
        # This is what WebsocketServerPart does for every message it decodes
        self.o.info_registry.report(None, RequestInfo(request, mri))
        # handle_request doesn't wait for the response, so await it here
        return await asyncio.wait_for(responses.get(), 10)

    @on_loop
    async def test_a_dot_mri_is_handled_by_the_server_comms_itself(self):
        response = await self.get_via(1, ".", [".", "meta", "label"])
        assert response.id == 1
        assert response.value == "WS"

    @on_loop
    async def test_a_named_mri_is_routed_to_that_controller(self):
        response = await self.get_via(2, "OTHER", ["OTHER", "meta", "label"])
        assert response.id == 2
        assert response.value == "OTHER"

    @on_loop
    async def test_an_unknown_mri_raises(self):
        # This propagates up to WebsocketServerPart.on_message, which turns it
        # into an Error response for the client. Routing "." as an ordinary
        # mri lands here, which is how dropping the "." case broke startup
        request = Get(id=3, path=["MISSING", "meta"])
        with self.assertRaises(ValueError) as cm:
            self.o.info_registry.report(None, RequestInfo(request, "MISSING"))
        assert "No controller registered for mri 'MISSING'" in str(cm.exception)
