#! /usr/bin/env python3
"""The 'build_all' rebuild path -- the one branch no ordinary run ever takes.

proginit.start_up carries a development-only branch that refreshes the half of the
action code tables Tasker does not publish as json.  It reaches the network, rewrites
files in the source tree and then exits the program, so it is never taken during a real
run and never taken by the rest of the suite either.  That made it the one piece of the
project where a stale module name or a swapped argument survived every check and only
surfaced the next time somebody updated Tasker -- which is precisely what happened when
acmerge was renamed.

So these tests exercise it deliberately, with everything it reaches stubbed out:

  - the flag really is False, because shipping it as True ends every user's startup;
  - the deferred imports resolve, since nothing else in the suite imports those modules;
  - each step runs, in order, against the right url;
  - debug is turned on first, without which the whole rebuild reports nothing;
  - the two valcodes helpers that read Tasker's published Java source.
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest
from maptasker.src import proginit, valcodes
from maptasker.src.primitem import PrimeItems


def test_build_all_is_off() -> None:
    """The development flag is False in the source that ships.

    Read out of the file rather than called, because it is a local in start_up and the
    branch it guards exits the program.  With it True, MapTasker would rebuild its
    tables from the network and quit before showing anybody anything.
    """
    tree = ast.parse(pathlib.Path(proginit.__file__).read_text(encoding="utf-8"))
    start_up = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "start_up")
    assignments = [
        node
        for node in ast.walk(start_up)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "build_all" for t in node.targets)
    ]
    assert len(assignments) == 1, "expected exactly one 'build_all =' in start_up"
    assert assignments[0].value.value is False, "build_all must not be committed as True"


def test_the_deferred_imports_resolve() -> None:
    """Every module rebuild_action_tables imports at call time resolves, by that name.

    The names are read out of its source rather than written down again here, because
    what is being checked is exactly what that function says -- importing the modules
    directly would pass just as happily while proginit still named a module that had
    been renamed.  That is not hypothetical: valcodes was acmerge until recently, and
    nothing in the suite noticed, because this branch is never taken.
    """
    tree = ast.parse(pathlib.Path(proginit.__file__).read_text(encoding="utf-8"))
    rebuild = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "rebuild_action_tables"
    )
    imports = [n for n in ast.walk(rebuild) if isinstance(n, ast.ImportFrom)]
    assert imports, "rebuild_action_tables should import its dependencies at call time"

    for node in imports:
        module = importlib.import_module(node.module)
        for alias in node.names:
            assert hasattr(module, alias.name), f"{node.module} has no {alias.name}"
            assert callable(getattr(module, alias.name)), f"{node.module}.{alias.name} is not callable"


@pytest.fixture
def _stubbed(monkeypatch: pytest.MonkeyPatch) -> list:
    """Record what the rebuild does instead of letting it do it.

    build_bundles and build_arguments would otherwise write into the source tree with
    their default paths, and validate_states_and_events would fetch from tasker.com.
    """
    calls = []
    monkeypatch.setattr(PrimeItems, "program_arguments", {"debug": False}, raising=False)
    monkeypatch.setattr(
        valcodes,
        "validate_states_and_events",
        lambda code_type, url: calls.append(("validate", code_type, url, PrimeItems.program_arguments["debug"])),
    )
    import maptasker.src.bldargs as bldargs
    import maptasker.src.bldbndle as bldbndle

    monkeypatch.setattr(bldbndle, "build_bundles", lambda: calls.append(("bundles",)))
    monkeypatch.setattr(bldargs, "build_arguments", lambda: calls.append(("arguments",)))
    return calls


def test_every_step_runs_in_order(_stubbed: list) -> None:
    """All four steps, in the order the rebuild depends on.

    The validations come first so that a code Tasker has added is reported before the
    bundle and argument harvests go looking for it.
    """
    proginit.rebuild_action_tables()
    assert [call[0] for call in _stubbed] == ["validate", "validate", "bundles", "arguments"]


def test_each_code_type_gets_its_own_url(_stubbed: list) -> None:
    """Events are checked against EventCodes.java and states against StateCodes.java.

    Swapping these is the quiet failure this guards: both urls fetch, both parse, and
    every code is then reported as missing from a table it was never in.
    """
    proginit.rebuild_action_tables()
    validations = {call[1]: call[2] for call in _stubbed if call[0] == "validate"}
    assert validations == {"e": proginit.EVENT_CODES_URL, "s": proginit.STATE_CODES_URL}
    assert validations["e"].endswith("EventCodes.java")
    assert validations["s"].endswith("StateCodes.java")


def test_debug_is_on_before_anything_reports(_stubbed: list) -> None:
    """Debug is set before the first validation, not after.

    valcodes.debug_print is the only way any of this reaches the screen and it returns
    silently when debug is off, so a rebuild that turned it on afterwards would look
    like a clean run no matter what it found.
    """
    proginit.rebuild_action_tables()
    assert all(call[3] is True for call in _stubbed if call[0] == "validate")


# One State code that is in the table (10s, 'Battery Level'), one that is not, and a
# '= -1' entry, which Tasker uses for codes that no longer have one.
_JAVA = """\
package net.dinglisch.android.tasker;
public class StateCodes {
    public static final int BATTERY_LEVEL = 10;
    public static final int NOT_A_REAL_CODE = 999991;
    public static final int RETIRED = -1;
    private static final int IGNORED = 5;
    public static final String ALSO_IGNORED = "7";
}
"""


def test_java_constants_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only 'public static final int' declarations are picked up, negatives included."""

    class _Response:
        text = _JAVA

        def raise_for_status(self) -> None:
            """Nothing to raise for a stubbed 200."""

    monkeypatch.setattr(valcodes.requests, "get", lambda url, timeout: _Response())  # noqa: ARG005
    assert valcodes.java_constants_to_dict("https://example.invalid/StateCodes.java") == {
        "BATTERY_LEVEL": 10,
        "NOT_A_REAL_CODE": 999991,
        "RETIRED": -1,
    }


def test_validation_reports_a_code_the_table_lacks(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A code Tasker publishes that the overlay does not carry is called out by name.

    This is the whole point of the exercise: it is how a new Tasker release's Events and
    States get noticed, since they are not in task_all_actions.json to be picked up.
    """
    monkeypatch.setattr(PrimeItems, "program_arguments", {"debug": True}, raising=False)
    monkeypatch.setattr(PrimeItems, "tasker_state_codes", {}, raising=False)
    monkeypatch.setattr(valcodes, "java_constants_to_dict", lambda url: {"NOT_A_REAL_CODE": 999991})  # noqa: ARG005
    # debug_print appends to buildit.log in the working directory; keep it out of the repo.
    monkeypatch.setattr(valcodes, "debug_print", lambda message: print(message))

    valcodes.validate_states_and_events("s", "https://example.invalid/StateCodes.java")

    out = capsys.readouterr().out
    assert "999991" in out
    assert "not found in actionc table" in out
    assert PrimeItems.tasker_state_codes == {"NOT_A_REAL_CODE": 999991}, "the fetched codes are recorded"
