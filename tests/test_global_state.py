"""The program's code reads the run it is given, not the global one -- except in the places listed here.

PrimeItems is the RunState a real run passes in.  Every function that is handed a ``state`` reads and
writes only that, which is what lets a run be exercised, or two be kept apart, without the global.  A
function that names PrimeItems itself defeats that: it works on whichever run happens to be global, and
a RunState built for a test is quietly not the one it used.

So the places that still name it are listed below, each with why, and this test keeps the list honest in
both directions:

  * A new reference in code (a comment or docstring does not count) fails.  Take the ``state`` as a
    parameter; if the function really is one of the session-wide ones, add it here with its reason.
  * A listed reference that has gone fails too, so the list can only shrink.

Two kinds are listed.  A FALLBACK is ``PrimeItems if state is None else state`` -- an entry point that
callers may leave the state out of, which then means "the run the program is on".  A SESSION entry reads
something that belongs to the process and not to one run over one backup, as primitem.py's header says:
the language and its translator, the debug and trace switches the logging helpers read underneath
everything, and the lookup a window falls back on when it has no state of its own.
"""

from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "maptasker"

# (file, function) -> why it may name PrimeItems.
_ALLOWED: dict[tuple[str, str], str] = {
    # Fallbacks: the state parameter may be left out, and then it is PrimeItems.
    (
        "maptasker/src/mapit.py",
        "mapit_all",
    ): "FALLBACK: the console script and `python -m maptasker.main` give no state",
    ("maptasker/src/clireports.py", "run"): "FALLBACK: a report asked for on the command line gives no state",
    ("maptasker/src/core/error.py", "error_handler"): "FALLBACK: errors are reported from places that hold no state",
    ("maptasker/src/core/runcfg.py", "current_config"): "FALLBACK: a snapshot of the global settings by default",
    ("maptasker/src/core/runcfg.py", "overridden_config"): "FALLBACK: a temporary override of the global settings",
    ("maptasker/src/core/actionc.py", "load_arg_specs"): "FALLBACK: start-up loads them onto the run it is starting",
    ("maptasker/src/core/valcodes.py", "debug_print"): "FALLBACK: a developer tool, run with no state of its own",
    ("maptasker/src/core/valcodes.py", "validate_states_and_events"): "FALLBACK: as debug_print",
    (
        "maptasker/src/gui/userintr.py",
        "__init__",
    ): "FALLBACK: the window shows the program's run unless it is given one",
    (
        "maptasker/src/mapgen/lineout.py",
        "state",
    ): "FALLBACK: a LineOut made without a state belongs to the program's run",
    # Session: belongs to the process, not to one run over one backup.
    (
        "maptasker/src/core/console.py",
        "_in_debug_mode",
    ): "SESSION: the debug switch the logging helpers read underneath everything",
    (
        "maptasker/src/core/translator.py",
        "set_language",
    ): "SESSION: the language and the translation function it installs",
    (
        "maptasker/src/core/maputil2.py",
        "translate_string",
    ): "SESSION: translates with the function the language installed",
    (
        "maptasker/src/gui/guiutil2.py",
        "my_trace_function",
    ): "SESSION: the trace switch for sys.settrace, which is per process",
    ("maptasker/src/gui/guiutils.py", "window_state"): "SESSION: what a window with no state of its own falls back on",
}


def _references() -> set[tuple[str, str]]:
    """Every (file, function) whose code -- not comments, not docstrings -- names PrimeItems."""
    found: set[tuple[str, str]] = set()
    for path in sorted(_SOURCE.rglob("*.py")):
        if path.name == "primitem.py":  # where it is defined
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Name) and node.id == "PrimeItems" and isinstance(node.ctx, ast.Load)):
                continue
            function = "<module>"
            up = node
            while up in parents:
                up = parents[up]
                if isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function = up.name
                    break
            found.add((path.relative_to(_ROOT).as_posix(), function))
    return found


def test_no_new_function_reads_the_global_run() -> None:
    new = sorted(_references() - set(_ALLOWED))
    assert not new, (
        f"{new} name PrimeItems in code.  Take the RunState as a parameter (state: RunState) and read that; "
        "if one really is session-wide, add it to _ALLOWED in tests/test_global_state.py with its reason."
    )


def test_a_listed_reference_that_has_gone_comes_off_the_list() -> None:
    gone = sorted(set(_ALLOWED) - _references())
    assert not gone, f"{gone} no longer name PrimeItems; remove them from _ALLOWED so the list only shrinks."


def test_every_listed_reference_says_which_kind_it_is() -> None:
    assert all(reason.startswith(("FALLBACK:", "SESSION:")) for reason in _ALLOWED.values())
