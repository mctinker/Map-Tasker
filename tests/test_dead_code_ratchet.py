"""scripts/dead_code_ratchet.py: what it finds in the source, and what it makes of the comparison.

The gate is that vulture's findings may only shrink: a finding the baseline does not list fails, one it lists that has
gone fails until the baseline is lowered, and --update only ever removes entries.  The names pyproject.toml tells vulture
are called from somewhere it cannot see are checked too, since an entry that stopped working would put a framework's
callback back among the findings.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "dead_code_ratchet.py"
_spec = importlib.util.spec_from_file_location("dead_code_ratchet", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
dc = importlib.util.module_from_spec(_spec)
sys.modules["dead_code_ratchet"] = dc
_spec.loader.exec_module(dc)


@pytest.fixture(scope="module")
def vulture_found() -> tuple[dict[str, Counter[str]], dict[tuple[str, str], list[int]]]:
    """What vulture finds in the source, read once: it is the slow part of every test that looks."""
    return dc.find_dead_code()


FUNCTION = "unused function 'orphan'"
ATTRIBUTE = "unused attribute 'widget'"


def _findings(**entries: dict[str, int]) -> dict[str, Counter[str]]:
    return {path.replace("__", "/"): Counter(counts) for path, counts in entries.items()}


def test_a_finding_the_baseline_does_not_list_is_new() -> None:
    found = _findings(a__py={FUNCTION: 1, ATTRIBUTE: 1})
    allowed = _findings(a__py={ATTRIBUTE: 1})

    assert dc.compare(found, allowed) == ([("a/py", FUNCTION, 1)], [])


def test_a_second_copy_of_a_listed_finding_is_new() -> None:
    found = _findings(a__py={ATTRIBUTE: 3})
    allowed = _findings(a__py={ATTRIBUTE: 2})

    assert dc.compare(found, allowed) == ([("a/py", ATTRIBUTE, 1)], [])


def test_a_listed_finding_that_has_gone_is_reported_as_gone() -> None:
    found = _findings(a__py={ATTRIBUTE: 1})
    allowed = _findings(a__py={ATTRIBUTE: 2}, b__py={FUNCTION: 1})

    assert dc.compare(found, allowed) == ([], [("a/py", ATTRIBUTE, 1), ("b/py", FUNCTION, 1)])


def test_the_same_findings_are_neither_new_nor_gone() -> None:
    found = _findings(a__py={FUNCTION: 1})

    assert dc.compare(found, _findings(a__py={FUNCTION: 1})) == ([], [])


def test_lowering_removes_what_is_gone_and_adds_nothing() -> None:
    found = _findings(a__py={ATTRIBUTE: 1, "unused variable 'brand_new'": 1})
    allowed = _findings(a__py={ATTRIBUTE: 2, FUNCTION: 1}, b__py={FUNCTION: 1})

    lowered = {path: dict(counts) for path, counts in dc.lowered(found, allowed).items()}

    assert lowered == {"a/py": {ATTRIBUTE: 1}, "b/py": {}}


def test_the_baseline_is_saved_sorted_without_empty_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dc, "BASELINE", tmp_path / "baseline.json")

    dc.save_baseline(_findings(z__py={FUNCTION: 1}, a__py={ATTRIBUTE: 1, FUNCTION: 1}, m__py={}))

    saved = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
    assert list(saved) == ["a/py", "z/py"]
    assert list(saved["a/py"]) == [ATTRIBUTE, FUNCTION]


def test_the_committed_baseline_is_what_vulture_finds_now(vulture_found) -> None:
    """The check CI runs: no new dead code, and none the baseline still allows that has gone."""
    found, _ = vulture_found
    new, gone = dc.compare(found, dc.load_baseline())

    assert new == []
    assert gone == []


@pytest.mark.parametrize(
    "name",
    ["handle_starttag", "handle_endtag", "find_class", "popout_view", "map_tasker_root", "output_directory_restored"],
)
def test_what_a_framework_calls_is_not_a_finding(vulture_found, name: str) -> None:
    """These are reached by a route vulture cannot follow; pyproject.toml says so, and they stay out of the baseline."""
    found, lines = vulture_found

    assert not [message for _, message in lines if f"'{name}'" in message]
    assert not [entries for entries in found.values() if any(f"'{name}'" in message for message in entries)]
