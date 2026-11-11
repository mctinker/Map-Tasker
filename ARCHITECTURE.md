# MapTasker architecture

How the source is laid out, what is allowed to depend on what, and the automated checks that keep it that way.
Most of this was only written down in comments in `pyproject.toml` and at the top of the scripts that enforce it;
this is the one place that says it all, and points to those for the detail.

## What it does

MapTasker reads a Tasker backup (`backup.xml`) and writes a Map of it -- an HTML document of every Project, Profile,
Task, Scene and preference -- and can also draw a Diagram of who calls whom, answer questions about the
configuration (health check, search, comparison against its history), edit it, and read and write the Android device
over Tasker's HTTP server.  It runs from the command line or as a NiceGUI web app in the user's browser.

## Layers

Everything is under `maptasker/src`.  A layer may import only the layers below it.

| Layer | Contents |
| --- | --- |
| entry points | `mapit.py` (the process), `runcli.py`, `rungui.py`, `clireports.py`, `progargs.py` |
| `gui` | NiceGUI windows, dialogs and their event handlers |
| `device` | what is done on the Android device, through Tasker's HTTP server |
| `mapops` | bulk operations: replace, refactor, repair, restore, draft; the TaskerNet and readiness tools |
| `analysis` | read-only questions asked of a configuration |
| `mapgen`, `edit` | `mapgen` loads a backup and builds the Map from it; `edit` holds the Task, Profile, Project and Scene editors and Undo.  Siblings: each needs a little of the other |
| `core` | run state, the Tasker action tables, shared utilities |

So a GUI module cannot be pulled into the core by accident, the core stays usable by the command line and the tests
without a web server, and the Map builder never reaches up into an operation.  [import-linter](https://import-linter.readthedocs.io)
enforces it in CI (`lint-imports`, configured under `[tool.importlinter]` in `pyproject.toml`).  Three contracts beyond the
layering: NiceGUI is imported only by the GUI and the entry points, and each kind of Scene editor (Legacy and Version 2)
is imported only by the code that edits that kind -- everything else asks `edit/scenemodel.py`, which decides which kind
it is looking at.  Every module has to be in exactly one layer, so a new package fails the check until it is placed.

`tests/test_import_structure.py` ratchets what import-linter cannot see: there is no import cycle, the imports deferred
into functions (usually to avoid one) are a known list, and the largest loop of modules may only shrink.

## A run

1. `mapit.mapit_all()` is the top of the process.  It builds the `RunState`, gets the arguments from `runcli` or, for the
   GUI, from `rungui` (which serves the window), and is the one place a `MapTaskerError` becomes an exit status.
2. A backup is loaded by `mapgen/proginit.py` and `mapgen/taskerd.py`, which parse it into the tables on the run state
   (`tasker_root_elements`: Projects, Profiles, Tasks, Scenes).  What an action, event or state *is* comes from
   `core/actionc.py`, built at import from `assets/json/task_all_actions.json` (Tasker's own, vendored as it is) and
   `assets/json/action_overlay.json` (everything Tasker does not publish).
3. `mapgen/bildhtml.build_html` walks Project -> Profile -> Task -> Action (`projects.py`, `profiles.py`, `tasks.py`,
   `taskactn.py`, with `actione.py`, `actargs.py` and `actionr.py` turning an action's XML into text).  Each piece goes to
   `lineout.LineOut.add_line_to_output`, which formats it (`core/format.py`).  `core/mapwriter.py` writes the lines and
   keeps the HTML well formed on the way out.
4. The GUI shows the file, or the Map is opened in a browser.  Unchanged input is not rebuilt (`mapgen/mapcache.py`).

## State

A `RunState` (`core/primitem.py`) is one run: the arguments, the loaded tables, the output.  Code takes a `state`
parameter and reads and writes only that, so it can be run against a `RunState` of its own, and two runs kept apart,
without the global.  `PrimeItems` is the `RunState` a real run passes in.  `tests/test_global_state.py` lists the few
functions still allowed to name `PrimeItems` -- the two entry points that have no state to be given (`mapit_all` and the
command-line reports) and the process-wide session attributes -- and fails on any other, and on a listed one that has gone.
Building a window (`MyGui`), the output lines (`LineOut`), reading the settings (`current_config`), loading the argument
specs and recording an error all take their `state`; none falls back to the global.  What a run does to the configuration
history (`timeline.suppressed`) is a flag on its own `RunState`, so one run's comparison cannot stop another's load from
being recorded.  The module-level flags that remain are the process's own: the terminal's mute switch, the crash hook, and
the one Scene being drawn.

## Errors

Library code does not end the run and does not decide what the user is shown.  It raises
`MapTaskerError(message, exit_code, show_code=...)` (`core/mtexcept.py`) and whoever started the work decides: the GUI's
loads and builds record it with `core/error.record_error` and carry on in the window; `mapit_all` prints the message and
returns the exit code.  `tests/test_no_deep_exits.py` fails if a module outside `main.py`, `mapit.py` and the restart
code calls `sys.exit` or brings back the old `error_handler` / `exit_program`.

## The GUI

`MyGui` (`gui/userintr.py`) is the window.  Its event handlers are not mixins: `MapTaskerEventHandlers` is a hub that
holds one `HandlerGroup` object per feature (`hub.editors`, `hub.android`, `hub.ai` ...; see `gui/userintr_group.py`),
and a group asks another by name through the hub, so the dependencies between groups can be read off the code.  Dialogs
are tested without a browser by NiceGUI's simulated user -- `tests/nicegui_harness.py` is the small layer over it.

## The rule: fix it, don't exempt it

Every check below is a **ratchet**.  It records where things stand, fails on anything *worse*, and fails on anything
*better* until the record is lowered to match, so a cleanup cannot leave room for the same problem to come back.  Nothing
is exempted to make a build pass; the fix belongs in the code.  A baseline only ever goes down by running the script's
`--update`.  If a new exception really is the right call, the number is raised **by hand** in the baseline file, so the
increase shows up in review with its reason.

| Check | What it holds | Baseline | Run |
| --- | --- | --- | --- |
| `ruff check` | every lint rule, every file; the only per-file exemptions are deliberate (tests, scripts, `__init__.py`) and carry their reason in `pyproject.toml` | -- | `ruff check` |
| `ruff format --check` | ruff's stable style | -- | `ruff format --check` |
| noqa ratchet | the count of inline `# noqa` comments, rule by rule | `scripts/noqa_baseline.json` | `python scripts/noqa_ratchet.py` |
| complexity ratchet | function length, statements, branches, McCabe complexity and arguments against the targets in `[tool.complexity-ratchet]`; a function over a target is listed and may not get bigger.  Ruff's own ceilings (`max-args` ...) sit just above and fail outright | `scripts/complexity_baseline.json` | `python scripts/complexity_ratchet.py` |
| dead code | any unused function, method, attribute or constant vulture finds.  What it reports wrongly (an `HTMLParser` callback, a `@ui.page` route, a widget looked up by name) or what is kept on purpose is named under `[tool.vulture]` in `pyproject.toml`, with the reason; there is no list of allowed findings | none | `python scripts/dead_code_check.py` |
| translation ratchet | the drift `tools/language_support/check_catalogs.py` finds: a string the program translates that a catalog lacks or holds blank, a lost placeholder, a stale `messages.mo`, a README block a translation does not follow.  Keyed by the string and the languages, so fixing one cannot cover for a new one | `scripts/translation_baseline.json` | `python scripts/translation_ratchet.py` |
| generated docs | the pages `tools/misc` generates (Command Reference, Runtime Options, Generated Output) are what their generators write now, and `README.md`'s section on reports from the command line names every report that runs with no window and lists the exit codes the program documents | the generators' own `--check` | `python scripts/docs_check.py` |
| typecheck ratchet | pyright (basic mode) errors per file and rule, for the source, `scripts`, `tests` and `tools` | `scripts/pyright_baseline.json` | `python scripts/typecheck_ratchet.py` |
| strict typing | every module in `maptasker/src` is in `[tool.pyright] strict` and clean under pyright's strict mode.  A new module is written strict-clean and listed (`tests/test_strict_typing.py`).  The patterns that clear the usual errors are in `pyproject.toml` above the list | `pyproject.toml` | `pyright` |
| coverage | `fail_under` for the whole program, and a floor per layer (a well-tested layer cannot cover for a neglected one) | `scripts/coverage_baseline.json` | `pytest --cov=maptasker` then `python scripts/coverage_ratchet.py` |
| build speed | the Map and Diagram build times, against a copy of `tests/data` scaled up, in units of a fixed piece of Python work so the machine does not matter; more than 25% slower fails | `scripts/perf_baseline.json` | `python scripts/perf_check.py` |
| import layers | the table above | `[tool.importlinter]` | `lint-imports` |
| package smoke test | the built wheel installs into an empty environment and runs: it holds every file git tracks under `maptasker/` and no more, every module imports, and `-version`, `-healthcheck` and `-export` work on a sample backup | -- | `python scripts/package_smoke.py` |
| dependency audit | the versions pinned in `uv.lock` against the known-vulnerability databases | -- | `scripts/dependency_audit.sh` |

## Continuous integration

`.github/workflows/ci.yml`, on every push and pull request:

* **test** -- the suite, in parallel (`pytest -n auto`, from pytest-xdist), on Ubuntu for Python 3.11 to 3.15, and on
  Windows and macOS for 3.13 (paths, per-user folders, font discovery, the password store and the filesystem all
  differ).  Coverage is measured on one leg, Ubuntu with Python 3.13 (`MEASURE_COVERAGE` in the workflow), which also
  holds the per-layer coverage floors: tracing every line makes the suite about two thirds slower, and how much of the
  code the tests reach does not depend on the system.
* **lint** -- ruff, the four ratchets and the dead-code check, import layers and the format check.
* **build distribution** -- `uv build` and `twine check`.

`.github/workflows/audit.yml` runs the dependency audit whenever the lock file changes and every Monday, since an
advisory is published on its own schedule and has nothing to do with the change being tested.  Dependabot
(`.github/dependabot.yml`) opens a weekly pull request for the locked dependencies and the workflow actions.

Tests are type-checked like the source (the typecheck ratchet above).  `tests/doubles.py` builds the stand-ins a test hands
to code that wants a `RunState`, a `MyGui` or a `RunConfig` (`fake_state`, `fake_window`, `fake_config`) and narrows what a
test knows to be there (`required` for a value that may be `None`, `expect` for one that is a result or an error message), so
a type error in a test is a real one rather than a stand-in.

Tests run in parallel, so none may depend on the one before it.  `tests/conftest.py` puts `PrimeItems` back to what it was
after every test, and anything else a test changes -- the working directory, the environment, a module attribute -- is
monkeypatched or kept in `tmp_path`.  A test that needs a loaded backup loads it itself, and the name of a parametrized
case must be the same in every process (xdist fails if two workers collect different names).  Plain `pytest` still runs
them serially, which is the way to debug one.

`tests/test_fuzz_backup.py` fuzzes the parser with Hypothesis: it spoils a well-formed backup in the tree (elements dropped,
attributes missing or junk, ids empty), in the encoding and in the bytes, and checks that loading raises nothing but
`MapTaskerError` and that the Health Check, the Map and the Diagram each end in a documented exit code.  A backup that names
something it does not hold is not an error -- the Map leaves the item out and Health Check reports it.  Each crash it has
found is pinned in `REGRESSIONS`.  `MAPTASKER_FUZZ_SCALE=20` runs twenty times as many examples, and
`MAPTASKER_FUZZ_BACKUP=<file>` adds a backup of your own as a base (with a fractional scale, as a real one is large).

`./run-ci.sh` runs the same gates locally (`--quick` skips the slow ones; `--fix` formats first).  Keep it in step with
`ci.yml`.

## Where things are decided

| Question | Where |
| --- | --- |
| What may import what | `[tool.importlinter]` in `pyproject.toml` |
| Lint, complexity and typing settings, with the reasoning for each | `pyproject.toml` (`[tool.ruff]`, `[tool.complexity-ratchet]`, `[tool.pyright]`) |
| Which modules are strict-typed (all of them) and how to keep a new one clean | `pyproject.toml` (`[tool.pyright] strict`) |
| What a user-visible change looks like in the changelog | `CLAUDE.md`, `Changelog.md` |
| The maintainer tools (language support, TaskerNet collection) | `tools/README.md` |
