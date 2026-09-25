class Future:
    """Represents the result of an asynchronous computation.
    This class has a similar API to concurrent.futures.Future but this
    simpler version is not thread safe"""

    # Possible future states (for internal use).
    RUNNING = "RUNNING"
    #  Task has set the return or exception and this future is filled
    FINISHED = "FINISHED"

    def __init__(self, context):
        """
        Args:
            context (Context): The context to run under
        """
        self._context = context
        self._state = self.RUNNING
        self._result = None
        self._exception = None

    def done(self):
        """Return True if the future finished executing."""
        return self._state == self.FINISHED

    def __await__(self):
        """Wait for the Future to finish and give up its result"""
        return self._wait_for_result().__await__()

    async def _wait_for_result(self):
        if self._state == self.RUNNING:
            await self._context.wait_all_futures([self])
        return self.__get_result()

    def __get_result(self):
        if self._exception:
            raise self._exception
        else:
            return self._result

    def result(self, timeout=None):
        """Return the result of the call that the future represents.

        The Future has to have finished already: this never waits. Await the
        Future, or await context.wait_all_futures(), to make it finish.

        Args:
            timeout: Ignored, and kept only so that existing callers still
                work. Waiting here would block the one event loop.

        Returns:
            The result of the call that the future represents.

        Raises:
            RuntimeError: If the future hasn't finished executing.
            Exception: If the call raised then that exception will be
                raised.
        """
        if self._state == self.RUNNING:
            raise RuntimeError(
                "Future is not finished, so it has no result yet. Await the "
                "Future, or await context.wait_all_futures(), first"
            )
        return self.__get_result()

    def exception(self, timeout=None):
        """Return the exception raised by the call that the future represents.

        The Future has to have finished already: this never waits. Await the
        Future, or await context.wait_all_futures(), to make it finish.

        Args:
            timeout: Ignored, and kept only so that existing callers still
                work. Waiting here would block the one event loop.

        Returns:
            The exception raised by the call that the future represents or None
            if the call completed without raising.

        Raises:
            RuntimeError: If the future hasn't finished executing.
        """
        if self._state == self.RUNNING:
            raise RuntimeError(
                "Future is not finished, so it has no exception yet. Await "
                "the Future, or await context.wait_all_futures(), first"
            )
        return self._exception

    # The following methods should only be used by Task and in unit tests.

    def set_result(self, result):
        """Sets the return value of work associated with the future.

        Should only be used by Task and unit tests.
        """
        self._result = result
        self._state = self.FINISHED

    def set_exception(self, exception):
        """Sets the result of the future as being the given exception.

        Should only be used by Task and unit tests.
        """
        assert isinstance(exception, Exception), f"{exception!r} should be an Exception"
        self._exception = exception
        self._state = self.FINISHED
