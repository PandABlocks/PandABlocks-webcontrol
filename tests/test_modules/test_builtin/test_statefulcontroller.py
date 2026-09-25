import gc
import unittest

from malcolm.annotypes import add_call_types
from malcolm.compat import OrderedDict
from malcolm.core import NotWriteableError, Part, Process
from malcolm.modules.builtin.controllers import StatefulController
from malcolm.modules.builtin.hooks import (
    AContext,
    AStructure,
    DisableHook,
    HaltHook,
    InitHook,
    ResetHook,
    SaveHook,
)
from malcolm.modules.builtin.util import StatefulStates

from ...loop import on_loop


class TestStates(unittest.TestCase):
    def setUp(self):
        self.o = StatefulStates()

    @on_loop
    async def test_init(self):
        expected = OrderedDict()
        expected["Resetting"] = {"Ready", "Fault", "Disabling"}
        expected["Ready"] = {"Fault", "Disabling"}
        expected["Fault"] = {"Resetting", "Disabling"}
        expected["Disabling"] = {"Disabled", "Fault"}
        expected["Disabled"] = {"Resetting"}
        assert self.o._allowed == expected

    @on_loop
    async def test_transition_allowed(self):
        assert self.o.transition_allowed("Ready", "Resetting") is False
        assert self.o.transition_allowed("Ready", "Disabling")

    @on_loop
    async def test_set_allowed(self):
        assert self.o.transition_allowed("Ready", "Resetting") is False
        self.o.set_allowed("Ready", "Resetting")
        assert self.o.transition_allowed("Ready", "Resetting")


class MyPart(Part):
    reset_done, disable_done, started, halted = False, False, False, False
    context = None
    exception = None

    def on_hook(self, hook):
        if isinstance(hook, ResetHook):
            self.reset_done = True
        elif isinstance(hook, DisableHook):
            self.disable_done = True
        elif isinstance(hook, InitHook):
            self.started = True
        elif isinstance(hook, HaltHook):
            self.halted = True
        elif isinstance(hook, SaveHook):
            hook(self.func)

    @add_call_types
    def func(self, context: AContext) -> AStructure:
        if self.exception:
            raise self.exception
        self.context = context
        return {"foo": "bar" + self.name}


class TestStatefulController(unittest.TestCase):
    def setUp(self):
        self.process = Process("proc")
        self.part = MyPart("testpart")
        self.part2 = MyPart("testpart2")
        self.o = StatefulController("MyMRI")
        self.o.add_part(self.part)
        self.o.add_part(self.part2)
        self.process.add_controller(self.o)
        self.b = self.process.block_view("MyMRI")

    async def start_process(self):
        # start_async, not the blocking start() facade: these tests run on the
        # event loop, where blocking would deadlock
        await self.process.start_async()
        self.addCleanup(self.stop_process)

    def stop_process(self):
        if self.process.state:
            self.process.stop(timeout=1)

    @on_loop
    async def test_process_init(self):
        assert not self.part.started
        await self.start_process()
        assert self.part.started

    @on_loop
    async def test_process_stop(self):
        await self.start_process()
        assert not self.part.halted
        await self.process.stop_async(timeout=1)
        assert self.part.halted

    @on_loop
    async def test_init(self):
        assert self.b.state.value == "Disabled"
        await self.start_process()
        assert list(self.b) == ["meta", "health", "state", "disable", "reset"]
        assert self.b.state.value == "Ready"
        assert self.b.disable.meta.writeable is True
        assert self.b.reset.meta.writeable is False

    @on_loop
    async def test_reset_fails_from_ready(self):
        await self.start_process()
        with self.assertRaises(TypeError):
            await self.o.reset()
        assert not self.part.reset_done

    @on_loop
    async def test_disable(self):
        await self.start_process()
        assert not self.part.disable_done
        await self.b.disable()
        assert self.part.disable_done
        assert self.b.state.value == "Disabled"
        with self.assertRaises(NotWriteableError) as cm:
            await self.b.disable()
        assert str(cm.exception) == (
            "Field ['MyMRI', 'disable'] is not writeable, maybe because Block "
            "state = Disabled"
        )
        assert not self.part.reset_done
        await self.b.reset()
        assert self.part.reset_done
        assert self.b.state.value == "Ready"

    @on_loop
    async def test_run_hook(self):
        await self.start_process()
        part_contexts = self.o.create_part_contexts()
        result = await self.o.run_hooks(
            SaveHook(p, c) for p, c in part_contexts.items()
        )
        assert set(result) == {"testpart", "testpart2"}
        assert result["testpart"] == {"foo": "bartestpart"}
        assert result["testpart2"] == {"foo": "bartestpart2"}
        # The part.context is a weakref, so compare on one of its strong
        # methods instead
        assert self.part.context.sleep == part_contexts[self.part].sleep
        del part_contexts
        gc.collect()
        with self.assertRaises(ReferenceError):
            await self.part.context.sleep(0)

    @on_loop
    async def test_run_hook_raises(self):
        await self.start_process()

        class MyException(Exception):
            pass

        self.part.exception = MyException()
        with self.assertRaises(Exception) as cm:
            await self.o.run_hooks(
                SaveHook(p, c) for p, c in self.o.create_part_contexts().items()
            )
        self.assertIs(self.part.context, None)
        self.assertIs(cm.exception, self.part.exception)
