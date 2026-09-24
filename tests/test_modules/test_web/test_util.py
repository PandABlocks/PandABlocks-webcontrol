import asyncio
import threading
import unittest

from malcolm.core import EventLoop, Queue, Spawned
from malcolm.modules.web.util import IOLoopHelper


class TestIOLoopHelper(unittest.TestCase):
    def test_shares_the_core_event_loop(self):
        assert IOLoopHelper.loop() is EventLoop.get()

    def test_call_runs_on_the_loop_thread(self):
        q = Queue()

        def callback(*args, **kwargs):
            loop = asyncio.get_running_loop()
            q.put((loop, threading.current_thread(), args, kwargs))

        IOLoopHelper.call(callback, 1, 2, three=3)
        loop, thread, args, kwargs = q.get(5)
        assert loop is EventLoop.get()
        assert thread is not threading.current_thread()
        # Same signature as the IOLoop.add_callback() this replaced
        assert args == (1, 2)
        assert kwargs == {"three": 3}

    def test_server_callbacks_and_spawned_work_share_one_loop(self):
        async def where_am_i():
            return asyncio.get_running_loop(), threading.current_thread()

        spawned_loop, spawned_thread = Spawned(where_am_i, (), {}).get(5)

        q = Queue()
        IOLoopHelper.call(lambda: q.put(threading.current_thread()))
        callback_thread = q.get(5)

        assert spawned_loop is IOLoopHelper.loop()
        assert spawned_thread is callback_thread
