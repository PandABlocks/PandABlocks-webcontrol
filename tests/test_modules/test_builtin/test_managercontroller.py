import asyncio
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from malcolm.compat import OrderedDict
from malcolm.core import (
    Context,
    Part,
    PartRegistrar,
    Process,
    Put,
    StringMeta,
    Widget,
    config_tag,
)
from malcolm.modules.builtin.controllers import ManagerController, StatefulController
from malcolm.modules.builtin.parts import ChildPart
from malcolm.modules.builtin.util import ExportTable, LayoutTable, ManagerStates

from ...loop import on_loop


class TestManagerStates(unittest.TestCase):
    def setUp(self):
        self.o = ManagerStates()

    @on_loop
    async def test_init(self):
        expected = OrderedDict()
        expected["Resetting"] = {"Ready", "Fault", "Disabling"}
        expected["Ready"] = {"Saving", "Fault", "Disabling", "Loading"}
        expected["Saving"] = {"Fault", "Ready", "Disabling"}
        expected["Loading"] = {"Disabling", "Fault", "Ready"}
        expected["Fault"] = {"Resetting", "Disabling"}
        expected["Disabling"] = {"Disabled", "Fault"}
        expected["Disabled"] = {"Resetting"}
        assert self.o._allowed == expected


async def wait_until(context, predicate, timeout=10):
    """Wait for a condition instead of sleeping a fixed time

    Everything shares one event loop, so how long a subscription takes to come
    back depends on what else is on it. A sleep long enough on an idle machine
    is not long enough on a loaded one, which made the tests below flaky, and
    sizing it for the worst case would slow every run down.

    It has to be `context.sleep`, not `asyncio.sleep`: a Context's responses
    land in a queue of its own and the subscription callbacks only run when
    something drains it, which is exactly what Context.sleep does. Polling with
    asyncio.sleep would stop the thing we are waiting for from ever happening.
    """
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, f"Timed out after {timeout}s waiting"
        await context.sleep(0.01)


class MyPart(Part):
    attr = None

    def setup(self, registrar: PartRegistrar) -> None:
        self.attr = StringMeta(
            tags=[config_tag(), Widget.TEXTINPUT.tag()]
        ).create_attribute_model("defaultv")
        registrar.add_attribute_model("attr", self.attr, self.attr.set_value)


class TestManagerController(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.p = Process("process1")

        # create a child to client
        self.c_child = StatefulController("childBlock")
        self.c_part = MyPart("cp1")
        self.c_child.add_part(self.c_part)
        self.p.add_controller(self.c_child)

        # Create temporary config directory for ProcessController
        self.config_dir = tempfile.mkdtemp()
        self.main_block_name = "mainBlock"
        self.c = ManagerController("mainBlock", config_dir=self.config_dir)
        self.c.add_part(MyPart("part1"))
        self.c.add_part(ChildPart("part2", mri="childBlock", initial_visibility=True))
        self.p.add_controller(self.c)
        self.b = self.p.block_view("mainBlock")

        # check that do_initial_reset works asynchronously
        assert self.c.state.value == "Disabled"
        self.p.start()
        assert self.c.state.value == "Ready"

    def tearDown(self):
        # Generous: this is cleanup, not something under test, and a tight
        # bound here just turns a slow machine into a failing test
        self.p.stop(timeout=10)
        shutil.rmtree(self.config_dir)

    @on_loop
    async def test_init(self):
        assert self.c.layout.value.name == ["part2"]
        assert self.c.layout.value.mri == ["childBlock"]
        assert self.c.layout.value.x == [0.0]
        assert self.c.layout.value.y == [0.0]
        assert self.c.layout.value.visible == [True]
        assert self.c.layout.meta.elements["name"].writeable is False
        assert self.c.layout.meta.elements["mri"].writeable is False
        assert self.c.layout.meta.elements["x"].writeable is True
        assert self.c.layout.meta.elements["y"].writeable is True
        assert self.c.layout.meta.elements["visible"].writeable is True
        assert self.c.design.value == ""
        assert self.c.exports.value.source == []
        assert self.c.exports.meta.elements["source"].choices == [
            "part2.health",
            "part2.state",
            "part2.disable",
            "part2.reset",
            "part2.attr",
        ]
        assert self.c.exports.value.export == []
        assert self.c.modified.value is False
        assert self.c.modified.alarm.message == ""
        assert self.b.mri.value == "mainBlock"
        assert self.b.mri.meta.tags == ["sourcePort:block:mainBlock"]

    def _get_design_filename(self, block_name, design_name):
        return f"{self.config_dir}/{block_name}/{design_name}.json"

    def check_expected_save(
        self, design_name, x=0.0, y=0.0, visible="true", attr="defaultv"
    ):
        expected = [
            x.strip()
            for x in (
                """{
          "attributes": {
             "layout": {
               "part2": {
                 "x": %s,
                 "y": %s,
                 "visible": %s
               }
             },
             "exports": {},
             "attr": "defaultv"
          },
          "children": {
             "part2": {
               "attr": "%s"
             }
          }
        }"""
                % (x, y, visible, attr)
            ).splitlines()
        ]
        with open(self._get_design_filename(self.main_block_name, design_name)) as f:
            actual = [x.strip() for x in f.readlines()]
        assert actual == expected

    @on_loop
    async def test_save(self):
        assert self.c.design.value == ""
        assert self.c.design.meta.choices == [""]
        c = Context(self.p)
        li = []
        c.subscribe(["mainBlock", "design", "meta"], li.append)
        # Wait for the subscription's initial Update to come back
        await wait_until(c, lambda: li)
        assert len(li) == 1
        assert li.pop()["choices"] == [""]
        b = c.block_view("mainBlock")
        design_name = "testSaveLayout"
        await b.save(designName=design_name)
        assert len(li) == 3
        assert li[0]["writeable"] is False
        assert li[1]["choices"] == ["", design_name]
        assert li[2]["writeable"] is True
        assert self.c.design.meta.choices == ["", design_name]
        self.check_expected_save(design_name)
        assert self.c.state.value == "Ready"
        assert self.c.design.value == design_name
        assert self.c.modified.value is False
        os.remove(self._get_design_filename(self.main_block_name, design_name))
        self.c_part.attr.set_value("newv")
        assert self.c.modified.value is True
        assert (
            self.c.modified.alarm.message == "part2.attr.value = 'newv' not 'defaultv'"
        )
        await self.c.save(designName="")
        self.check_expected_save(design_name, attr="newv")
        assert self.c.design.value == "testSaveLayout"

    async def move_child_block(self):
        new_layout = dict(
            name=["part2"], mri=["anything"], x=[10], y=[20], visible=[True]
        )
        await self.b.layout.put_value(new_layout)

    @on_loop
    async def test_move_child_block_dict(self):
        assert self.b.layout.value.x == [0]
        await self.move_child_block()
        assert self.b.layout.value.x == [10]

    @on_loop
    async def test_set_and_load_layout(self):
        new_layout = LayoutTable(
            name=["part2"], mri=["anything"], x=[10], y=[20], visible=[False]
        )
        await self.c.set_layout(new_layout)
        assert self.c.parts["part2"].x == 10
        assert self.c.parts["part2"].y == 20
        assert self.c.parts["part2"].visible is False
        assert self.c.modified.value is True
        assert self.c.modified.alarm.message == "layout changed"

        # save the layout, modify and restore it
        design_name = "testSaveLayout"
        await self.b.save(designName=design_name)
        assert self.c.modified.value is False
        self.check_expected_save(design_name, 10.0, 20.0, "false")
        self.c.parts["part2"].x = 30
        await self.c.set_design(design_name)
        assert self.c.parts["part2"].x == 10

    @on_loop
    async def test_set_export_parts(self):
        context = Context(self.p)
        b = context.block_view("mainBlock")
        assert list(b) == [
            "meta",
            "health",
            "state",
            "disable",
            "reset",
            "mri",
            "layout",
            "design",
            "exports",
            "modified",
            "save",
            "attr",
        ]
        assert b.attr.meta.tags == ["widget:textinput"]
        new_exports = ExportTable.from_rows(
            [("part2.attr", "childAttr"), ("part2.reset", "childReset")]
        )
        await self.c.set_exports(new_exports)
        assert self.c.modified.value is True
        assert self.c.modified.alarm.message == "exports changed"
        await self.c.save(designName="testSaveLayout")
        assert self.c.modified.value is False
        # block has changed, get a new view
        b = context.block_view("mainBlock")
        assert list(b) == [
            "meta",
            "health",
            "state",
            "disable",
            "reset",
            "mri",
            "layout",
            "design",
            "exports",
            "modified",
            "save",
            "attr",
            "childAttr",
            "childReset",
        ]
        assert self.c.state.value == "Ready"
        assert b.childAttr.value == "defaultv"
        assert self.c.modified.value is False
        m = MagicMock()
        b.childAttr.subscribe_value(m)
        # allow a subscription to come through
        await wait_until(context, lambda: m.called)
        m.assert_called_once_with("defaultv")
        m.reset_mock()
        self.c_part.attr.set_value("newv")
        assert b.childAttr.value == "newv"
        assert self.c_part.attr.value == "newv"
        assert self.c.modified.value is True
        assert (
            self.c.modified.alarm.message == "part2.attr.value = 'newv' not 'defaultv'"
        )
        # allow a subscription to come through
        await wait_until(context, lambda: m.called)
        m.assert_called_once_with("newv")
        await b.childAttr.put_value("again")
        assert b.childAttr.value == "again"
        assert self.c_part.attr.value == "again"
        assert self.c.modified.value is True
        assert (
            self.c.modified.alarm.message == "part2.attr.value = 'again' not 'defaultv'"
        )
        # remove the field
        new_exports = ExportTable([], [])
        await self.c.set_exports(new_exports)
        assert self.c.modified.value is True
        await self.c.save()
        assert self.c.modified.value is False
        # block has changed, get a new view
        b = context.block_view("mainBlock")
        assert "childAttr" not in b

    @on_loop
    async def test_save_does_not_block_the_event_loop(self):
        # Writing the design and flushing it can take a while on a PandA's
        # flash. Everything shares one event loop, so it has to happen on a
        # thread or the UI and the hardware polling stall with it
        ticks = []

        async def tick():
            for _ in range(20):
                await asyncio.sleep(0.01)
                ticks.append(1)

        ticking = asyncio.ensure_future(tick())
        with patch(
            "malcolm.modules.builtin.controllers.managercontroller.subprocess.call",
            side_effect=lambda *a, **k: time.sleep(0.2),
        ):
            await self.c.save(designName="blocking")
        assert ticks, "the loop made no progress while saving"
        ticking.cancel()


def spy_on_awaits(controller):
    """Record the Notifier's nesting depth each time the controller awaits

    A changes_squashed block must not span an await: the Controller drops its
    lock around the call into a Part, so a second request can run while we are
    suspended, and then neither one's changes are published when its own block
    exits. Every one of these should be reached with no batch open.
    """
    depths = []

    def wrap(name):
        original = getattr(controller, name)

        async def wrapper(*args, **kwargs):
            depths.append((name, controller._notifier._squashed_count))
            return await original(*args, **kwargs)

        setattr(controller, name, wrapper)

    for name in ("update_block_endpoints", "update_exportable"):
        wrap(name)
    return depths


class TestChangesSquashedNeverSpansAnAwait(unittest.TestCase):
    # Reuse the fixture, but not the tests that go with it
    setUp = TestManagerController.setUp
    tearDown = TestManagerController.tearDown

    @on_loop
    async def test_when_called_directly(self):
        depths = spy_on_awaits(self.c)

        layout = self.c.layout.value
        await self.c.set_layout(
            LayoutTable(layout.name, layout.mri, layout.x, layout.y, [False])
        )
        await self.c.set_exports(ExportTable(["part2.attr"], ["myattr"]))
        await self.c.update_exportable()
        await self.c._mark_clean("")

        # All four routes reached, and none of them with a batch open
        assert [name for name, _ in depths] != []
        assert depths == [(name, 0) for name, _ in depths], depths

    @on_loop
    async def test_under_two_concurrent_puts(self):
        # This is the case that made it matter: _handle_put releases the
        # Controller's lock around the call into the Part, so these two run
        # interleaved on the one event loop
        depths = spy_on_awaits(self.c)
        layout = self.c.layout.value

        requests = [
            Put(
                id=1,
                path=["mainBlock", "layout"],
                value=LayoutTable(layout.name, layout.mri, layout.x, layout.y, [False]),
            ),
            Put(
                id=2,
                path=["mainBlock", "exports"],
                value=ExportTable(["part2.attr"], ["myattr"]),
            ),
        ]
        responses: asyncio.Queue = asyncio.Queue()
        spawned = []
        for request in requests:
            request.set_callback(responses.put_nowait)
            spawned.append(self.c.handle_request(request))
        for s in spawned:
            await s.wait_async(10)

        assert [name for name, _ in depths] != []
        assert depths == [(name, 0) for name, _ in depths], depths
