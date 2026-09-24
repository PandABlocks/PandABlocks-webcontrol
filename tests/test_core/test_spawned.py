import asyncio
import threading
import unittest

from malcolm.core import EventLoop, Queue, Spawned
from malcolm.core.errors import TimeoutError, UnexpectedError


def do_div(a, b, q, throw_me=None):
    if throw_me:
        q.put(throw_me)
        raise throw_me
    q.put(a / b)
    return a / b


class TestSpawned(unittest.TestCase):
    def setUp(self):
        self.q = Queue()

    def do_spawn(self, throw_me=None):
        s = Spawned(do_div, (40, 2, self.q, throw_me), {})
        return s

    def test_spawn_div(self):
        s = self.do_spawn()
        s.wait(1)
        assert s.ready() is True
        assert self.q.get(1) == 20
        assert s.get() == 20

    def test_spawn_err(self):
        s = self.do_spawn(UnexpectedError)
        s.wait(1)
        assert s.ready() is True
        assert self.q.get(1) == UnexpectedError
        with self.assertRaises(UnexpectedError):
            s.get()


class TestSpawnedCoroutines(unittest.TestCase):
    def setUp(self):
        self.q = Queue()

    def test_coroutine_function_is_awaited(self):
        async def coro(a, b):
            await asyncio.sleep(0)
            return a + b

        s = Spawned(coro, (40, 2), {})
        assert s.get(1) == 42
        assert s.ready() is True

    def test_coroutine_runs_on_the_event_loop(self):
        async def coro():
            # There is a running loop here, and it is not the caller's thread
            return asyncio.get_running_loop(), threading.current_thread()

        loop, thread = Spawned(coro, (), {}).get(1)
        assert loop is EventLoop.get()
        assert thread is not threading.current_thread()

    def test_coroutine_err(self):
        async def coro():
            raise UnexpectedError("bad")

        s = Spawned(coro, (), {})
        s.wait(1)
        with self.assertRaises(UnexpectedError):
            s.get()

    def test_blocking_function_doesnt_run_on_the_event_loop(self):
        def blocking():
            # No loop is running in a worker thread, so a blocking call here
            # can't stall the coroutines on the loop
            with self.assertRaises(RuntimeError):
                asyncio.get_running_loop()
            return threading.current_thread()

        thread = Spawned(blocking, (), {}).get(1)
        assert thread is not threading.current_thread()

    def test_timeout_waiting(self):
        s = Spawned(self.q.get, (), {})
        with self.assertRaises(TimeoutError):
            s.wait(0.01)
        assert s.ready() is False
        # Let it finish so we don't leave the thread hanging around
        self.q.put(None)
        s.wait(1)
        assert s.ready() is True

    def test_many_blocking_spawns_all_start(self):
        # A bounded executor would deadlock here: these all block until every
        # one of them has started, which is the shape of the poll and send/recv
        # loops plus the hook functions that wait on them
        count = 50
        started = Queue()
        release = Queue()

        def blocker():
            started.put(None)
            return release.get(10)

        spawned = [Spawned(blocker, (), {}) for _ in range(count)]
        for _ in range(count):
            started.get(10)
        for _ in range(count):
            release.put("done")
        for s in spawned:
            assert s.get(10) == "done"
