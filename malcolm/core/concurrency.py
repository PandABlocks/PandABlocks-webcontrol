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


async def maybe_await(result: Any) -> Any:
    """Await result if it needs awaiting, otherwise pass it straight back

    Lets a caller on the event loop accept either a coroutine function or a
    plain one, so the two can be converted independently.
    """
    if inspect.isawaitable(result):
        return await result
    return result


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


async def run_blocking(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Await a blocking function on a worker thread

    Everything runs on one event loop, so work that blocks it - file IO, a
    subprocess - stalls the UI and the PandA polling along with itself. Hand
    that kind of work to a thread and await the result.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _EXECUTOR, functools.partial(func, *args, **kwargs)
    )


class EventLoop:
    """The single asyncio event loop that this process runs its callbacks on.

    It lives on its own daemon thread, so that work can be put on it from, and
    waited on by, ordinary blocking code in any thread. Both `Spawned` and the
    Tornado server run on it: a Tornado IOLoop is a wrapper around an asyncio
    loop, so the web server needs no loop of its own and calls straight onto
    this one.
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

    @classmethod
    def is_current_thread(cls) -> bool:
        """True if the caller is running on the event loop's thread"""
        return threading.current_thread() is cls._thread

    @classmethod
    def check_not_on_loop(cls, what: str) -> None:
        """Refuse to block the event loop from the event loop

        Blocking the loop to wait for work that only the loop can do hangs the
        whole application, and a hang is far harder to diagnose than an error.
        """
        if cls.is_current_thread():
            raise RuntimeError(
                f"{what} was called from the event loop, which would deadlock: "
                "the loop would be waiting for work only it can do. Await the "
                "coroutine instead."
            )

    @classmethod
    def run(cls, coro, timeout: float = None) -> Any:
        """Run a coroutine on the loop from another thread, returning its result

        For code that isn't on the loop and has a coroutine in hand, like the
        interactive console: run(block.save(designName="mine")).
        """
        loop = cls.get()
        cls.check_not_on_loop("EventLoop.run()")
        return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)

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


# Strong references to work scheduled straight onto the loop. asyncio only
# keeps a weak reference to a Task, so one that nothing else holds on to can be
# garbage collected mid-flight
_PENDING_TASKS: "set" = set()


def _schedule_on_loop(coro) -> "asyncio.Future":
    """Schedule a coroutine on the loop the caller is already running on"""
    task = asyncio.ensure_future(coro)
    _PENDING_TASKS.add(task)
    task.add_done_callback(_PENDING_TASKS.discard)
    return task


class Spawned:
    """Internal object keeping track of a spawned function

    The work is run as a coroutine on the shared `EventLoop`. A
    coroutine function is awaited on that loop; a plain function is handed to a
    worker thread, as it is free to block.
    """

    NO_RESULT = object()

    # An asyncio Task when the work was scheduled from the loop, a
    # concurrent Future when it was handed over from another thread
    _future: Union["asyncio.Future", concurrent.futures.Future]

    def __init__(self, func: Callable[..., Any], args: Tuple, kwargs: Dict) -> None:
        self._result: Union[Any, Exception] = self.NO_RESULT
        self._function = func
        self._args = args
        self._kwargs = kwargs
        # Set once the work has finished, so a caller on another thread can
        # block on it whichever of the two ways it was scheduled
        self._done = threading.Event()
        coro = self.catching_function()
        if EventLoop.is_current_thread():
            # We are already on the loop, so schedule directly.
            # run_coroutine_threadsafe would cost a concurrent Future and a
            # self-pipe wakeup here, and every request from the web UI spawns
            self._future = _schedule_on_loop(coro)
        else:
            self._future = asyncio.run_coroutine_threadsafe(coro, EventLoop.get())
        self._future.add_done_callback(lambda _: self._done.set())

    @staticmethod
    def _is_async(func: Callable[..., Any]) -> bool:
        # A View's method is a plain object with an async __call__, which
        # iscoroutinefunction doesn't see on its own
        return inspect.iscoroutinefunction(func) or inspect.iscoroutinefunction(
            getattr(func, "__call__", None)
        )

    async def catching_function(self) -> None:
        try:
            if self._is_async(self._function):
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
        """Block until the function has finished, or timeout seconds pass

        For callers that are not on the event loop. Coroutines must use
        wait_async(), or they would block the loop they are running on.
        """
        EventLoop.check_not_on_loop("Spawned.wait()")
        # Wait on the Event rather than the future: work scheduled from the
        # loop is an asyncio Task, which isn't safe to touch from here. A
        # cancelled task still fires its callbacks, so this returns for one
        # too - wait() only reports that we finished, get() is what re-raises
        if not self._done.wait(timeout):
            raise TimeoutError(f"Spawned function didn't finish within {timeout}s")

    async def wait_async(self, timeout: float = None) -> None:
        """Wait from the event loop for the function to finish

        Like wait(), but for callers that are themselves coroutines. Shielded,
        so that timing out here doesn't cancel the work, matching wait().
        """
        if isinstance(self._future, asyncio.Future):
            waitable = asyncio.shield(self._future)
        else:
            waitable = asyncio.shield(asyncio.wrap_future(self._future))
        try:
            await asyncio.wait_for(waitable, timeout)
        except (asyncio.TimeoutError, TimeoutError):
            raise TimeoutError(f"Spawned function didn't finish within {timeout}s")
        except asyncio.CancelledError:
            pass

    def ready(self) -> bool:
        """Return True if the spawned result has returned or errored"""
        return self._future.done()

    def get(self, timeout: float = None) -> T:
        """Return the result or raise the error the function has produced"""
        self.wait(timeout)
        if self._result is self.NO_RESULT:
            # We never stored a result, so the coroutine was cancelled or hit a
            # BaseException. Asking the future re-raises whatever that was, and
            # it has finished by now, so this doesn't block for either kind
            self._future.result()
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
