# CLAUDE.md

Guidance for working in this repository.

## What this is

`PandABlocks-webcontrol` serves the web UI for a PandA box. It is a trimmed-down
fork of DLS's **pymalcolm** (the `malcolm` package here is that framework, with
everything not needed for PandA removed — no EPICS/CA, no scanning, no
areaDetector). It does two things at runtime:

1. Talks to the PandA TCP control server (default `localhost:8888`) over its
   line-based ASCII protocol, and models every PandA block/field as a Malcolm
   **Block** with **Attributes**.
2. Serves the pre-built **malcolmjs** React front end (checked in under
   `malcolm/modules/web/www/`) over Tornado, plus a WebSocket endpoint that the
   front end uses to get/put/subscribe to those Attributes.

Entry point: the `panda-webcontrol` console script → `malcolm/webcontrol.py:main`.

## Layout

```
malcolm/
  webcontrol.py        # argparse + wiring of the two controllers; the only "app" code
  annotypes/           # vendored `annotypes`: Anno/Array/@add_call_types, serialization
  core/                # the framework: Process, Controller, Part, Hook, Models, Views
  modules/
    builtin/           # generic Controllers (Basic/Stateful/Manager/ServerComms) + Parts
    pandablocks/       # PandA TCP client, controllers, field Parts, block SVG icons
    web/               # Tornado server comms, websocket/GUI Parts, www/ bundle
  compat.py            # OrderedDict + ElementTree helper
tests/                 # mirrors malcolm/ (test_core, test_modules/test_{builtin,pandablocks,web})
docs/                  # MyST (mystmd) docs, Diátaxis structure, built via `make docs`
```

The package is deliberately trimmed to what `webcontrol.py` actually reaches: the
YAML assembly layer, proxy/client comms, the REST handler, the demo and unused
generic Parts, the profiler and the test-only helpers have all been removed. If
you add a module, it should be on a path that `panda-webcontrol` executes — and
if you find something unreferenced, it is fair game to delete.

## Core concepts (`malcolm/core`)

Understand these five and the rest follows:

- **Process** (`process.py`) — owns a dict of `mri → Controller`, spawns threads
  (`Spawned`), and runs `ProcessStartHook` / `ProcessPublishHook` /
  `ProcessStopHook` across all controllers. An **MRI** (Malcolm Resource
  Identifier) is a Block's unique name, e.g. `PANDA`, `PANDA:PULSE1`, `WS`.
- **Controller** (`controller.py`) — owns one `BlockModel` and the parts that
  populate it. Serves `Get`/`Put`/`Post`/`Subscribe`/`Unsubscribe` `Request`s
  (`request.py`) and answers with `Return`/`Error`/`Update`/`Delta`
  (`response.py`). All state changes happen under `self._lock`; batch them with
  `with self.changes_squashed:`.
- **Part** (`part.py`) — a reusable chunk of behaviour that registers Attributes
  and Methods on its Controller via `PartRegistrar`, and hooks into lifecycle
  hooks. Parts never own the Block; the Controller does.
- **Hook** (`hook.py`) — typed publish/subscribe for lifecycle events. A Part
  calls `registrar.hook(SomeHook, self.on_something)`; a Controller calls
  `self.run_hooks(SomeHook(p, c) for p, c in ...)`, which runs the hooked
  functions concurrently and collects returned `Info` objects.
- **Model / Meta / View** (`models.py`, `views.py`) — `*Meta` objects
  (`NumberMeta`, `ChoiceMeta`, `TableMeta`, …) describe and validate a field;
  `create_attribute_model()` turns one into an `AttributeModel` holding a value,
  `Alarm` and `TimeStamp`. `Notifier` (`notifier.py`) turns model mutations into
  `Delta`/`Update` responses for subscribers. `views.py` wraps models in
  user-friendly `Block`/`Attribute`/`Method` views used through a `Context`.

**Tags drive the GUI.** `core/tags.py` defines `Widget` (`textinput`, `led`,
`table`, `flowgraph`, `icon`, `help`, …), `Port` (`sourcePort:`/`sinkPort:` tags
that malcolmjs draws as flowgraph wires), `group_tag`, `config_tag` (field takes
part in save/restore), `badge_value_tag` and `linked_value_tag`. If a field looks
wrong in the browser, the tags on its meta are usually the reason.

`annotypes` supplies the `with Anno("description"): AFoo = str` idiom plus
`@add_call_types`; these annotations are what generate `MethodMeta` argument
descriptions and YAML parameter signatures, so keep them accurate.

## Runtime wiring

`webcontrol.py:main()` builds one `Process` with exactly two top-level
controllers, waits for the PandA TCP port to open (`wait_for_port`), then starts:

- `web.controllers.HTTPServerComms(port=--wsport, mri="WS")` with
  `WebsocketServerPart` (`/ws`) and a templated `GuiServerPart` (static files,
  `/gui/…` and `/details/…`). At `do_init` it runs `ReportHandlersHook` over its
  parts, collects `HandlerInfo(regexp, handler_cls, **kwargs)` and builds the
  Tornado `Application`.
- `pandablocks.controllers.PandAManagerController(mri=--mri, …)` — the PandA
  itself.

**There is one event loop in the process**: `core/concurrency.py:EventLoop`, on
a daemon thread called `malcolm-event-loop`. Both users share it — a Tornado
IOLoop is only a wrapper around an asyncio loop, so `web/util.py:IOLoopHelper`
is a thin adapter that puts server callbacks on `EventLoop` rather than running
a loop of its own. Anything touching Tornado (`server.listen`,
`write_message`, …) must still go through `IOLoopHelper.call(...)`, since it has
to happen on that thread. `EventLoop` is owned by `core`: nothing in `web`
starts or stops it.

Background work goes through `core/concurrency.py:Spawned`, which runs it as a
coroutine on that same loop. An `async def` callable is awaited there and costs
no thread; a plain function is handed to a worker thread, since it is free to
block. Each blocking callable gets its own thread rather than a slot in a pool —
spawned work includes a loop that runs forever (the manager's poll loop) and
hook functions that block waiting on *other* spawned work, so a bounded pool
would run out of workers and deadlock. That re-entrancy is
also why `Spawned.wait()`/`get()` are still blocking calls: callers reach them
from sync code, including from inside other spawned work.

The corollary of one shared loop: **a spawned coroutine must not block or do
heavy CPU work**, or it stalls HTTP and websocket serving along with everything
else. Put anything that blocks in a plain function and let it have a thread.
`Queue` and `RLock` remain the threading versions. `cothread` was removed in
commit `111e0792`.

### Request path

browser → `/ws` (`MalcWebSocketHandler.on_message`) → JSON deserialized into a
`Request` → `registrar.report(RequestInfo(request, mri))` →
`ServerComms.update_request_received` → `process.get_controller(mri)
.handle_request(...)` (spawns a worker thread) → responses come back via the
request callback → `IOLoopHelper.call` → `write_message`. `Put`/`Post` are
rejected unless the client IP is inside a local interface's subnet, unless
subnet validation is disabled (`--optionsdir` containing `no-subnet-validation`).
There is no REST surface: the WebSocket is the only API.

### PandA path

`PandABlocksClient` (`modules/pandablocks/pandablocksclient.py`) keeps one
connection with a send coroutine and a recv coroutine and a queue per in-flight
request. The transport is `asyncio.open_connection`, so neither loop costs a
thread: `_send_loop` awaits an `asyncio.Queue` that worker threads feed through
`loop.call_soon_threadsafe` (`_queue_send`), and `_recv_loop` awaits
`reader.readline()`. The per-request response queues stay *threading* queues,
because that is where the loop hands results back to the blocking callers of
`recv()`. The client remembers the loop it was started on, so it needs no import
from `malcolm.core`. It knows the PandA protocol (`*BLOCKS?`, `*DESC.…?`, `*ENUMS.…?`, `<block>.*?`,
`*CHANGES?`, `field=value`, `field<` table writes).

`PandAManagerController`:

- On init, `_make_child_controllers()` reads `get_blocks_data()` and creates one
  `PandABlockController` (a `BasicController`, MRI `PANDA:<BLOCK>`) per block
  instance, plus a `builtin.parts.ChildPart` on itself for each so they appear in
  the layout flowgraph.
- Runs `_poll_loop()` in a spawned thread every `poll_period` seconds (hard-coded to
  0.1 in `webcontrol.py`), calling
  `client.get_changes()` and `handle_changes()`. The loop self-throttles to at
  most 50% duty cycle and publishes the achieved period as `lastPollPeriod`.
- `handle_changes()` splits incoming `BLOCK.FIELD=value` pairs three ways: bus
  tables (`PandABussesPart`), the owning child controller, and `*METADATA`
  (block labels and the JSON `LAYOUT` blob). `bit_out` fields get special
  treatment: a value that is unchanged is deliberately toggled and restored on
  the next poll so the GUI LED visibly blinks.
- Layout positions live in the PandA itself under `*METADATA.LAYOUT`;
  `set_layout()` reconciles the Malcolm layout table with that JSON.

`PandABlockController._make_parts_for()` is the field-type → Part mapping —
the table to consult when a new PandA field type appears:

| PandA field type | What is created |
|---|---|
| `param`/`read`/`write` | `PandAFieldPart` with meta from `make_meta(subtype)`, grouped into `parameters`/`readbacks` |
| `time`, `*.UNITS` | float64 value + `ChoiceMeta` units (value restored in config iteration 2) |
| `write`/`action` | `PandAActionPart` → a Method, not an Attribute |
| `bit_out`/`pos_out` | read-only attr tagged as a flowgraph **source port** |
| `bit_mux`/`pos_mux` | `ChoiceMeta` **sink port** + `.DELAY` attr; `mux_metas` keeps the `linked_value_tag` up to date |
| `ext_out` | `.CAPTURE` choice (or handled wholesale by the busses table if `bits`) |
| `table` | `PandATablePart` — unpacks/packs the PandA's uint32 rows into typed columns via bit masks |
| `HEALTH` | folded into the Controller's own `health` attribute |

Each block also gets an icon, a label and a help link: `PandAIconPart`
(specialised as `PandALutIconPart`, `PandAPulseIconPart`,
`PandASRGateIconPart`) mutates the SVG in `modules/pandablocks/icons/` in
response to field changes; `HelpPart` points at
`<--doc-url-base>/<blocktype>-doc/`.

`PandABussesPart` owns the two big cross-block tables (`bits`, `positions`)
shown at the PandA top level, including PCAP capture columns.

### Save / restore ("designs")

`PandAManagerController` extends `builtin.controllers.ManagerController`, which
adds the state machine (`ManagerStates`: Ready/Saving/Loading/Fault/Disabled),
the `layout` and `exports` tables and the `design` attribute. `save()` walks
`SaveHook` over the parts and writes `<--configdir>/<mri>/<design>.json`;
setting `design` runs `LoadHook`. Read-only template designs live in
`--templatedesigns` (defaults to `www/template_designs/`) and must be named
`template_*.json`; saving over them is refused.

## Conventions

- **Field names are camelCase** on the Malcolm side (`FieldRegistry._add_field`
  asserts it); PandA names are UPPER_SNAKE and converted with
  `snake_to_camel`. Dots in PandA field names become underscores in Part names
  (the web GUI treats `.` as a reserved separator).
- New behaviour is normally a new **Part**, not a new Controller. Subclass a
  Controller only when the whole Block lifecycle changes.
- Re-export annotypes at the top of a module (`AMri = AMri`) so subclasses in
  other modules can reference them — this pattern is everywhere, it is
  deliberate.
- Modules expose a flat namespace via `submodule_all(globals())` in
  `__init__.py`; add new public names to the relevant `from .x import Y`.
- Tests mirror the package layout and mostly drive a real `Process` with a
  `Mock()` client. Test-only helpers live in `tests/`, never in the shipped
  package.

## Development

```bash
python -m pytest tests                 # test suite (needs the dev extras)
make docs                              # MyST build into docs/_build/html (npx mystmd)
make docs-dev                          # live docs server
panda-webcontrol --hostname <panda> --configdir <dir>   # run against a real box
```

Formatting/lint config lives in `pyproject.toml`: ruff (line length 88, rules
B/C4/E/F/W/I/UP), isort with the black profile, mypy with
`ignore_missing_imports`. CI (`.github/workflows/ci.yml`) currently only builds,
releases and publishes the docs via the shared
`DiamondLightSource/myst-version-switcher-plugin` reusable workflows — **the
Python tests are not run in CI**, so run them locally.

## Rough edges (verified, as of this writing)

- `[tool.pytest.ini_options] addopts` still contains `--black --mypy`, which need
  the abandoned `pytest-black`/`pytest-mypy` plugins. Without them pytest aborts
  with "unrecognized arguments"; override with
  `pytest -o addopts="--tb=native" …`.
- Runtime deps in `pyproject.toml` are `numpy` + `tornado`, which is now accurate
  for the package itself; the tests additionally import `mock`, which is only
  listed under the `dev` extra.
- 13 tests fail out of the box, all for pre-existing reasons: 11 in
  `test_request_response.py` read JSON fixtures from `docs/reference/json/`,
  which no longer exists; `test_models.py::test_unsigned_validates` expects
  numpy 1 wrap-around where numpy 2 raises `OverflowError`; and
  `test_pandablockcontroller.py::test_block_fields_pulse` still expects the old
  help-URL format (`/docs/build/pulse_doc.html`) that commit 5941a9d5 replaced
  with `/docs/pulse-doc/`.
- `malcolm/modules/web/www/` is a vendored malcolmjs build. Do not hand-edit it;
  `update_malcolmjs.sh` re-downloads a release tarball and regenerates
  `index-nav.html` (the nav-bar variant rendered by the Tornado template handler
  in `webcontrol.py`).
