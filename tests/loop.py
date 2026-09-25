"""Helper for tests that drive the framework's event loop.

Malcolm runs everything on one event loop (`malcolm.core.EventLoop`), so a test
has to enter *that* loop rather than make one of its own the way
`unittest.IsolatedAsyncioTestCase` does. Queues and locks belong to the loop
they were first used on, so a test driving its own loop would hand work to
coroutines waiting on a different one, and hang.
"""

import functools

from malcolm.core import Spawned

# Long enough that a slow machine doesn't fail, short enough that a deadlock
# shows up as a failure rather than a hung suite
DEFAULT_TEST_TIMEOUT = 30


def on_loop(func=None, timeout=DEFAULT_TEST_TIMEOUT):
    """Run this async test (or helper) on the framework's event loop

    Blocks the calling thread until it finishes, re-raising whatever it raised,
    so failed assertions are reported normally.
    """

    def decorate(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            return Spawned(f, args, kwargs).get(timeout)

        return wrapper

    if func is not None:
        return decorate(func)
    return decorate
