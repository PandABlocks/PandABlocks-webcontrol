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

**Everything runs on one event loop**: `core/concurrency.py:EventLoop`, on a
daemon thread called `malcolm-event-loop`. There are no worker threads — a
running server is MainThread plus that loop. Tornado shares it (an IOLoop is
only a wrapper round an asyncio loop); `EventLoop` is owned by `core`, and
nothing in `web` starts or stops it. `web` calls onto the loop directly —
`HTTPServerComms` calls `listen()`/`stop()` from `do_init`/`do_disable`/
`do_reset`, which are coroutines and so already on it. There used to be a
`web/util.py:IOLoopHelper` adapter for dispatching those from off the loop;
deferring them meant `do_init` returned before the port was bound, and a bind
failure went to the loop's exception handler instead of faulting the Block.

The request path, the hooks, `Context`, the PandA client and the poll loop are
all coroutines. `Spawned` still exists: it schedules a coroutine on the loop and
hands back something you can `wait()` on, and it will still put a plain blocking
function on a thread if you give it one. Called *from* the loop it schedules the
task directly rather than paying for `run_coroutine_threadsafe`, which is the
common case now that every request and every hook spawns from the loop.

**Locking.** There is exactly one lock on the message path: `Controller._lock`,
an `asyncio.Lock`, one per Controller — so `PANDA:PULSE1` and `PANDA:SEQ1` never
contend, and `WS` has its own. `asyncio.Lock` wakes waiters FIFO, which is the
only thing making two requests from one client run in arrival order, since
`handle_request` spawns and does not wait. It replaced an `RLock`, which was not
a like-for-like swap: an `RLock` is re-entrant *per thread*, so once its holders
are coroutines on one thread it silently stops excluding anything (two
coroutines both enter).

The lock is narrower than it looks, and it is worth knowing exactly where it is
*not* held:

- `_handle_request` holds it while it dispatches, and drops it before delivering
  responses to callbacks.
- `Get`/`Subscribe`/`Unsubscribe` never await under it, so they would be atomic
  on one loop regardless; the lock is what makes a `Get`'s frozen snapshot
  consistent.
- `Put`/`Post` hand it *back* in the middle — `async with self.lock_released:`
  around the call into the Part — because that is where the slow work is. So the
  lock stops two Puts validating and dispatching at once, but it does **not**
  make a Put atomic end to end, and two Parts can be running on one Block at
  once. `lock_released` re-acquires on the way out, so a put function returning
  may suspend again waiting to get the lock back.
- Subscription updates take no lock at all: the PandA poll loop calls
  `handle_changes` directly rather than through `_handle_request`.

Everywhere else the lock simply went away — a block of code that awaits nothing
cannot be interleaved with on a single loop, so `block_view`/`make_view`/
`update_label` take nothing at all, and `changes_squashed` is now just a nesting
counter. That last one comes with a rule.

**A `changes_squashed` block must not span an `await`.** It reads like a lock
and is not one any more. Because `lock_released` drops the Controller lock
exactly where Parts run, and the poll loop holds no lock at all, a block that
suspends lets a second operation squash into the same counter and change list.
Neither one's changes are then published when its own block exits — only when
the last one out takes the count to zero. The visible symptoms are a client
being told its `Put` returned *before* being told the value changed, and two
unrelated operations arriving in one `Delta`. Do the awaiting either side of the
block; `update_block_endpoints` is the worked example, computing its new fields
first and then mutating under its own batch. Six blocks got this wrong after the
conversion, including one holding a batch open across a round trip to the PandA.
`TestChangesSquashedNeverSpansAnAwait` (in the `test_managercontroller.py`
tests) records the nesting depth at every await and asserts it is zero, under
two concurrent Puts as well as sequential calls.

**What stayed synchronous, and why.** `models.py`, `notifier.py` and the view
getters are sync, so `attr.set_value(...)` needs no `await` — making it async
would have put an `await` in front of every assignment in every Part. The
consequence is that `Notifier` delivers responses from a plain context manager,
so a *coroutine* callback there is scheduled with `ensure_future` rather than
awaited. Keep callbacks that must take effect immediately sync:
`ManagerController.update_modified` is sync for exactly this reason, while
`update_exportable` is a coroutine because it may rebuild the Block's endpoints.

**Calling in from outside the loop**: `EventLoop.run(coro)` blocks and returns
the result. That's what the `panda-webcontrol` console passes to the user as
`run()`, since `block.save()` is a coroutine now. `Process.start()`/`stop()` are
blocking facades over `start_async()`/`stop_async()` for the same reason; from
*on* the loop you must use the async ones, or you deadlock.

### Request path

browser → `/ws` (`MalcWebSocketHandler.on_message`) → JSON deserialized into a
`Request` → `registrar.report(RequestInfo(request, mri))` →
`ServerComms.update_request_received` →
`process.get_controller(mri).handle_request(...)` (schedules a coroutine on the
loop and doesn't wait for it) → responses come back via the request callback,
`on_response`.

`on_response` is called from sync code (a Controller, or the `Notifier` when a
value changed) so it cannot await, and writing from there directly left nothing
bounding Tornado's write buffer. It puts the response on a bounded per-
connection `asyncio.Queue` instead, drained by one `_write_responses` task that
*awaits* each `write_message`: that is the flow control, and one writer is what
keeps Deltas in order. A client that fills the queue is closed rather than
silently desynced, and `on_close` unsubscribes everything in `_id_to_mri` so the
Controllers stop producing for a socket nobody reads.

An mri of `"."` means the `ServerComms` Block itself rather than one of the
Process' controllers, and `ServerComms.update_request_received` special-cases
it. It is not dead: the web GUI Gets `[".", "blocks"]` to discover what Blocks
exist, so removing it breaks startup with "No controller registered for mri
'.'". It is spelled `[".","blocks"]` inside the minified bundle, which is easy
to miss when grepping.

`Put`/`Post` are rejected unless the client IP is inside a local interface's
subnet (worked out once in `open()`), unless subnet validation is disabled
(`--optionsdir` containing `no-subnet-validation`). There is no REST surface:
the WebSocket is the only API.

### PandA path

`PandABlocksClient` (`modules/pandablocks/pandablocksclient.py`) keeps one
connection over `asyncio.open_connection`, with a send coroutine, a recv
coroutine and an `asyncio.Queue` per in-flight request. Its whole public API is
async. `send()` stays sync and hands back the queue to await, so a caller can
pipeline a batch of requests before awaiting any of them — `parameterized_send`
and `get_blocks_data` depend on that. `get_changes` returns a list rather than
being a generator, since a coroutine can't be iterated lazily. Table column
metadata is read by the manager and passed to `PandATablePart`, because a
constructor can't await. It knows the PandA protocol (`*BLOCKS?`, `*DESC.…?`, `*ENUMS.…?`, `<block>.*?`,
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

`update_icon` is a coroutine because `PandALutIconPart` asks the box for
`FUNC.RAW` to work out which elements to hide. That await is why
`PandABlockController.handle_changes` publishes a poll's field changes and the
icon in **two** `Delta`s: rendering happens outside `changes_squashed`, so the
batch is not held open across a round trip to the PandA (see the
`changes_squashed` rule above). `test_block_fields_lut` asserts both deltas.

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
- **A test that touches the framework must run on its event loop**: decorate it
  `@on_loop` (`tests/loop.py`) and make it `async`. Do not use
  `IsolatedAsyncioTestCase` — it creates its own loop, and queues and locks
  belong to the loop they were first used on, so the test would hand work to
  coroutines waiting on a different one and hang. For the same reason, a test on
  the loop must never block on a threading `Queue`: use an `asyncio.Queue` and
  `await` it, or you stall the loop that has to deliver the response. Mocks come
  from the standard library's `unittest.mock`, not the `mock` backport. Mock a
  coroutine with `AsyncMock`, or patch a whole class with `autospec=True`, which
  picks `AsyncMock` for its coroutine methods automatically.
- **`Context.sleep` is a pump, not a sleep.** A `Context` routes its responses
  into a queue of its own (`subscribe` sets the request callback to
  `self._q.put_nowait`), and the callback you passed only runs when something
  drains that queue — which is what `sleep` and `wait_all_futures` do, via
  `_service_futures`. So waiting on a Context's subscription with
  `asyncio.sleep` stops the thing you are waiting for from ever happening. Poll
  with `context.sleep` instead.

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

- Runtime deps in `pyproject.toml` are `numpy` + `tornado`, which is accurate
  for the package itself. The tests need only `pytest` on top of those: they
  use `unittest.mock` from the standard library, so there is no `mock`
  dependency to install.
- Import the vendored copy as `malcolm.annotypes`, never as a top-level
  `annotypes`. The latter is a different, undeclared package; where it was used
  (six test modules and the `py3_examples`) those files failed at *collection*,
  which aborts the whole pytest run rather than failing one test.
- 2 tests fail out of the box, both for pre-existing reasons:
  `test_models.py::test_unsigned_validates` expects numpy 1 wrap-around where
  numpy 2 raises `OverflowError` (so it is 1 failure on numpy 1.x, where that
  one passes); and `test_pandablockcontroller.py::test_block_fields_pulse`
  still expects the old help-URL format (`/docs/build/pulse_doc.html`) that
  commit 5941a9d5 replaced with `/docs/pulse-doc/`.
- Don't wait for a subscription with a fixed sleep. `test_managercontroller.py`
  used to `await context.sleep(0.1)` and then assert the callback had fired,
  which failed intermittently on a loaded machine; it now polls with a
  `wait_until(context, predicate)` helper, which is both robust and faster.
- `test_request_response.py` asserts the serialized `to_dict()` shapes the
  browser parses. Those expected dicts were read from `docs/reference/json/`
  until the docs restructure deleted it; they are now inlined, copied from the
  same examples in pymalcolm upstream. Keep them inline — there is no fixture
  directory to go back to.
- The checked-in formatting predates current ruff: `ruff format --check` wants
  to rewrite files nobody has touched, and `ruff check` reports hundreds of
  `UP`/`B` findings against the project's own rule selection. Don't reformat the
  world — compare a changed file against its `HEAD` version and only care about
  findings your edit introduced.
- `malcolm/modules/web/www/` is a vendored malcolmjs build. Do not hand-edit it;
  `update_malcolmjs.sh` re-downloads a release tarball and regenerates
  `index-nav.html` (the nav-bar variant rendered by the Tornado template handler
  in `webcontrol.py`).
