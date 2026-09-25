import socket
import unittest

from malcolm.core import Process
from malcolm.modules.web.controllers import HTTPServerComms


class TestHTTPServerComms(unittest.TestCase):
    def setUp(self):
        self.o = HTTPServerComms(mri="mri")

    def test_init(self):
        assert self.o.port == 8008
        assert self.o.mri == "mri"


class TestServerLifecycle(unittest.TestCase):
    """do_init runs on the event loop Tornado runs on, so it listens directly

    Handing listen() to the loop instead meant do_init returned before the
    port was bound, and a bind failure went to the loop's exception handler
    rather than putting the Block into Fault.
    """

    def setUp(self):
        # Port 0 so the OS picks a free one and the test can't clash
        self.process = Process("proc")
        self.o = HTTPServerComms(mri="WS", port=0)
        self.process.add_controller(self.o)

    def tearDown(self):
        self.process.stop(timeout=10)

    def bound_port(self):
        # listen(0) binds one socket per family, all sharing the one port the
        # OS picked, so any of them will do
        sock = next(iter(self.o._server._sockets.values()))
        return sock.getsockname()[1]

    def test_the_port_is_listening_once_start_returns(self):
        self.process.start()
        assert self.o._server_started is True
        # Nothing was deferred: the socket accepts by the time we get here
        with socket.create_connection(("127.0.0.1", self.bound_port()), timeout=10):
            pass

    def test_a_port_already_in_use_faults_the_block(self):
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        self.addCleanup(blocker.close)
        clashing = HTTPServerComms(mri="WS2", port=blocker.getsockname()[1])
        self.process.add_controller(clashing)

        self.process.start()

        # The OSError came back out of do_init rather than being swallowed
        assert clashing.state.value == "Fault"
        assert "Address already in use" in clashing.health.value
