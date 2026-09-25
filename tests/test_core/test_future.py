import unittest

from malcolm.core.future import Future
from mock import AsyncMock, MagicMock

from ..loop import on_loop


class MyError(Exception):
    pass


class TestFuture(unittest.TestCase):
    def setUp(self):
        self.context = MagicMock()

    def test_set_result(self):
        f = Future(self.context)
        f.set_result("testResult")
        assert f.done()
        assert f.result(0) == "testResult"

    def test_set_exception(self):
        f = Future(self.context)
        e = ValueError("test Error")
        f.set_exception(e)
        assert f.done()
        with self.assertRaises(ValueError):
            f.result(timeout=0)
        assert f.exception() == e

    def test_result_before_finished_raises(self):
        # result() used to service the Context until the Future finished. The
        # Context is a coroutine now, which a sync method can't wait on, so
        # asking early is an error rather than a quietly wrong answer
        f = Future(self.context)
        with self.assertRaises(RuntimeError) as cm:
            f.result()
        assert "not finished" in str(cm.exception)
        with self.assertRaises(RuntimeError):
            f.exception()

    @on_loop
    async def test_await_result(self):
        f = Future(self.context)

        async def wait_all_futures(fs):
            fs[0].set_result(32)

        self.context.wait_all_futures = AsyncMock(side_effect=wait_all_futures)

        assert await f == 32
        self.context.wait_all_futures.assert_called_once_with([f])
        self.context.wait_all_futures.reset_mock()
        # Finished now, so awaiting again doesn't go back to the Context
        assert await f == 32
        self.context.wait_all_futures.assert_not_called()

    @on_loop
    async def test_await_exception(self):
        f = Future(self.context)

        async def wait_all_futures(fs):
            fs[0].set_exception(MyError())

        self.context.wait_all_futures = AsyncMock(side_effect=wait_all_futures)

        with self.assertRaises(MyError):
            await f

        self.context.wait_all_futures.assert_called_once_with([f])
        self.context.wait_all_futures.reset_mock()
        self.assertIsInstance(f.exception(), MyError)
        self.context.wait_all_futures.assert_not_called()
