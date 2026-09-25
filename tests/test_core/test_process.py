import unittest
from typing import List
from unittest.mock import MagicMock

from malcolm.annotypes import add_call_types
from malcolm.core import (
    APublished,
    Process,
    ProcessPublishHook,
    ProcessStartHook,
    UnpublishedInfo,
)
from malcolm.core.controller import Controller

from ..loop import on_loop


class PublishController(Controller):
    published: List[APublished] = []

    def on_hook(self, hook):
        if isinstance(hook, ProcessPublishHook):
            hook(self.do_publish)

    @add_call_types
    def do_publish(self, published: APublished) -> None:
        self.published = published


class UnpublishableController(Controller):
    def on_hook(self, hook):
        if isinstance(hook, ProcessStartHook):
            hook(self.on_start)

    def on_start(self):
        return UnpublishedInfo(self.mri)


class TestProcess(unittest.TestCase):
    def setUp(self):
        self.o = Process("proc")
        self.o.start()

    def tearDown(self):
        self.o.stop(timeout=1)

    @on_loop
    async def test_init(self):
        assert self.o.name == "proc"

    @on_loop
    async def test_add_controller(self):
        controller = MagicMock(mri="mri")
        await self.o.add_controllers_async([controller])
        assert self.o.get_controller("mri") == controller

    @on_loop
    async def test_init_controller(self):
        class InitController(Controller):
            init = False

            def on_hook(self, hook):
                if isinstance(hook, ProcessStartHook):
                    self.init = True

        c = InitController("mri")
        await self.o.add_controllers_async([c])
        assert c.init is True

    @on_loop
    async def test_publish_controller(self):
        c = PublishController("mri")
        await self.o.add_controllers_async([c])
        assert c.published == ["mri"]
        await self.o.add_controllers_async([Controller(mri="mri2")])
        assert c.published == ["mri", "mri2"]
        await self.o.add_controllers_async([UnpublishableController("mri3")])
        assert c.published == ["mri", "mri2"]
