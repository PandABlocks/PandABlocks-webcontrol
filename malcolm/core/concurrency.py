import asyncio
import atexit
import concurrent.futures
import functools
import inspect
import logging
import queue as queue_module
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, Union

from .errors import TimeoutError

T = TypeVar("T")


# Make a module level logger
log = logging.getLogger(__name__)

# Re-export
sleep = time.sleep
RLock = threading.RLock


class _ThreadPerTaskExecutor(concurrent.futures.Executor):
    """Executor that runs each callable on its own daemon thread.

    An event loop's default executor is a bounded pool, which we can't use for
    spawned work: some of it runs for the lifetime of the process (the PandA
    poll loop, the client send and recv loops), and hook functions block
    waiting on other spawned work, so a bounded pool would run out of workers
    and deadlock.
    """

    def submit(  # type: ignore[override]
        self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future:
        future: concurrent.futures.Future = concurrent.futures.Future()

        def run() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(fn(*args, **kwargs))
            except BaseException as e:  # noqa: BLE001 - handed to the waiter
                future.set_exception(e)

        threading.Thread(target=run, daemon=True).start()
        return future


# Runs the blocking functions that are handed to Spawned
_EXECUTOR = _ThreadPerTaskExecutor()


class EventLoop:
    """The single asyncio event loop that this process runs its callbacks on.

    It lives on its own daemon thread, so that work can be put on it from, and
    waited on by, ordinary blocking code in any thread. Both `Spawned` and the
    Tornado server (via `web.util.IOLoopHelper`) use it: a Tornado IOLoop is a
    wrapper around an asyncio loop, so the web server needs no loop of its own.
    """

    _loop: Optional[asyncio.AbstractEventLoop] = None
    _thread: Optional[threading.Thread] = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> asyncio.AbstractEventLoop:
        """Return the running event loop, starting it if it isn't up yet"""
        with cls._lock:
            if cls._loop is None:
                loop = asyncio.new_event_loop()
                cls._loop = loop
                cls._thread = threading.Thread(
                    target=cls._run_forever,
                    args=(loop,),
                    daemon=True,
                    name="malcolm-event-loop",
                )
                cls._thread.start()
                atexit.register(cls.stop)
            return cls._loop

    @classmethod
    def call(cls, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Call func(*args, **kwargs) on the loop thread, from any thread"""
        if kwargs:
            func = functools.partial(func, **kwargs)
        cls.get().call_soon_threadsafe(func, *args)

    @staticmethod
    def _run_forever(loop: asyncio.AbstractEventLoop) -> None:
        # Tornado's IOLoop.current() picks the loop up from here, so that
        # server.listen() works when we dispatch it onto this thread
        asyncio.set_event_loop(loop)
        loop.run_forever()

    @classmethod
    def stop(cls, timeout: float = 10) -> None:
        """Stop the loop. Work still running on it is abandoned, as it is on
        daemon threads"""
        with cls._lock:
            loop, thread = cls._loop, cls._thread
            cls._loop, cls._thread = None, None
        if loop is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        assert thread, "Loop with no thread"
        thread.join(timeout)
        if thread.is_alive():
            log.warning("Event loop didn't stop within %ss", timeout)
        else:
            loop.close()


class Spawned:
    """Internal object keeping track of a spawned function

    The work is run as a coroutine on the shared `EventLoop`. A
    coroutine function is awaited on that loop; a plain function is handed to a
    worker thread, as it is free to block.
    """

    NO_RESULT = object()

    def __init__(self, func: Callable[..., Any], args: Tuple, kwargs: Dict) -> None:
        self._result: Union[Any, Exception] = self.NO_RESULT
        self._function = func
        self._args = args
        self._kwargs = kwargs
        self._future = asyncio.run_coroutine_threadsafe(
            self.catching_function(), EventLoop.get()
        )

    async def catching_function(self) -> None:
        try:
            if inspect.iscoroutinefunction(self._function):
                self._result = await self._function(*self._args, **self._kwargs)
            else:
                call = functools.partial(self._function, *self._args, **self._kwargs)
                loop = asyncio.get_running_loop()
                self._result = await loop.run_in_executor(_EXECUTOR, call)
        except Exception as e:
            log.debug(
                "Exception calling %s(*%s, **%s)",
                self._function,
                self._args,
                self._kwargs,
                exc_info=True,
            )
            self._result = e
        # We finished running the function, so remove the reference to it
        # in case it's stopping garbage collection
        self._function = None
        self._args = None
        self._kwargs = None

    def wait(self, timeout: float = None) -> None:
        """Block until the function has finished, or timeout seconds pass"""
        try:
            # exception() returns the error rather than raising it: wait() only
            # reports that we finished, get() is what re-raises
            self._future.exception(timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Spawned function didn't finish within {timeout}s")
        except concurrent.futures.CancelledError:
            pass

    def ready(self) -> bool:
        """Return True if the spawned result has returned or errored"""
        return self._future.done()

    def get(self, timeout: float = None) -> T:
        """Return the result or raise the error the function has produced"""
        self.wait(timeout)
        if self._result is self.NO_RESULT:
            # We never stored a result, so the coroutine was cancelled or hit a
            # BaseException. Asking the future re-raises whatever that was.
            self._future.result(0)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class Queue:
    """Threadsafe queue with gets in calling thread"""

    def __init__(self):
        self._event_queue: "queue_module.Queue" = queue_module.Queue()

    def get(self, timeout=None):
        try:
            return self._event_queue.get(timeout=timeout)
        except queue_module.Empty:
            raise TimeoutError("Queue().get() timed out")

    def put(self, value):
        self._event_queue.put(value)
