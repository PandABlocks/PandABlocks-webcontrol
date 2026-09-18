import logging
import queue as queue_module
import threading
import time
from typing import Any, Callable, Dict, Tuple, TypeVar, Union

from .errors import TimeoutError

T = TypeVar("T")


# Make a module level logger
log = logging.getLogger(__name__)

# Re-export
sleep = time.sleep
RLock = threading.RLock


class Spawned:
    """Internal object keeping track of a spawned function"""

    NO_RESULT = object()

    def __init__(self, func: Callable[..., Any], args: Tuple, kwargs: Dict) -> None:
        self._result_queue = Queue()
        self._result: Union[Any, Exception] = self.NO_RESULT
        self._function = func
        self._args = args
        self._kwargs = kwargs
        threading.Thread(target=self.catching_function, daemon=True).start()

    def catching_function(self):
        try:
            self._result = self._function(*self._args, **self._kwargs)
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
        self._result_queue.put(None)

    def wait(self, timeout: float = None) -> None:
        # Only one person can wait on this at a time
        if self._result == self.NO_RESULT:
            self._result_queue.get(timeout)

    def ready(self) -> bool:
        """Return True if the spawned result has returned or errored"""
        return self._result != self.NO_RESULT

    def get(self, timeout: float = None) -> T:
        """Return the result or raise the error the function has produced"""
        self.wait(timeout)
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
