from typing import Union

from malcolm.annotypes import Anno, Array
from malcolm.core import EventLoop, Table


class IOLoopHelper:
    """Puts Tornado callbacks on the process' shared event loop.

    Tornado doesn't need a loop of its own: an IOLoop is a wrapper around an
    asyncio loop, and `EventLoop` runs one already for spawned work. Sharing it
    means server callbacks and spawned work are ordered against each other, and
    there is one thread rather than two. The loop is owned by malcolm.core, so
    nothing here starts or stops it.
    """

    @classmethod
    def loop(cls):
        return EventLoop.get()

    @classmethod
    def call(cls, func, *args, **kwargs):
        # add_callback(func, *args, **kwargs) on an IOLoop, but without
        # needing the IOLoop wrapper
        EventLoop.call(func, *args, **kwargs)


with Anno("The Malcolm Resource Identifier for the Block"):
    AMris = Union[Array[str]]
with Anno("A human readable label for the Block"):
    ALabels = Union[Array[str]]


class BlockTable(Table):
    def __init__(self, mri: AMris, label: ALabels) -> None:
        self.mri = mri
        self.label = label
