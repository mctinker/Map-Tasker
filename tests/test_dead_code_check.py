"""scripts/dead_code_check.py: the source has no dead code, and the names pyproject.toml excuses stay excused.

The names [tool.vulture] says are called from somewhere vulture cannot see are checked too, since an entry that
stopped working would put a framework's callback back among the findings.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "dead_code_check.py"
_spec = importlib.util.spec_from_file_location("dead_code_check", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
dc = importlib.util.module_from_spec(_spec)
sys.modules["dead_code_check"] = dc
_spec.loader.exec_module(dc)


@pytest.fixture(scope="module")
def vulture_found() -> list[tuple[str, int, str]]:
    """What vulture finds in the source, read once: it is the slow part of every test that looks."""
    return dc.find_dead_code()


def test_nothing_in_the_source_is_unused(vulture_found: list[tuple[str, int, str]]) -> None:
    """The check CI runs."""
    assert vulture_found == []


@pytest.mark.parametrize(
    "name",
    ["handle_starttag", "handle_endtag", "find_class", "popout_view", "map_tasker_root", "output_directory_restored"],
)
def test_what_a_framework_calls_is_not_a_finding(vulture_found: list[tuple[str, int, str]], name: str) -> None:
    """These are reached by a route vulture cannot follow; pyproject.toml says so."""
    assert not [finding for finding in vulture_found if f"'{name}'" in finding[2]]


def test_a_dead_function_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The check does fail on something: a function nothing calls."""
    (tmp_path / "pyproject.toml").write_text('[tool.vulture]\npaths = ["pkg"]\nmin_confidence = 60\n', encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("def orphan():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(dc, "ROOT", tmp_path)

    assert dc.find_dead_code() == [("pkg/mod.py", 1, "unused function 'orphan'")]
    assert dc.main() == 1
