"""Every module in maptasker/src is held to pyright's strict mode, or is on a list that can only shrink.

Basic mode is ratcheted by scripts/typecheck_ratchet.py (pyright_baseline.json), which stops the
count of errors rising.  Strict mode finds a good deal more -- every value of unknown type -- and
turning it on for the whole code base would bury it.  So it is switched on file by file: the files
[tool.pyright] strict lists are clean under it (the ratchet fails if one stops being), and
scripts/strict_exempt.json names the ones that are not yet.

What this test adds is the direction of travel.  A module that is in neither list is a new one, and
it is written strict-clean and listed in pyproject.toml, not added to the exempt list.  A module in
both lists has been paid off, and comes off the exempt one.
"""

from __future__ import annotations

import json
import pathlib
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "maptasker" / "src"


def _sources() -> set[str]:
    return {path.relative_to(_ROOT).as_posix() for path in _SOURCE.rglob("*.py")}


def _strict() -> set[str]:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(config["tool"]["pyright"]["strict"])


def _exempt() -> set[str]:
    return set(json.loads((_ROOT / "scripts" / "strict_exempt.json").read_text(encoding="utf-8")))


def test_a_new_module_is_written_strict_clean() -> None:
    new = sorted(_sources() - _strict() - _exempt())
    assert not new, (
        f"{new} are in neither [tool.pyright] strict nor scripts/strict_exempt.json.  A new module is "
        "written clean under pyright's strict mode and added to the strict list in pyproject.toml; "
        "the exempt list only ever shrinks."
    )


def test_a_module_that_has_been_cleaned_comes_off_the_exempt_list() -> None:
    paid_off = sorted(_exempt() & _strict())
    assert not paid_off, f"{paid_off} are strict-clean now: remove them from scripts/strict_exempt.json."


def test_the_lists_name_modules_that_exist() -> None:
    gone = sorted((_strict() | _exempt()) - _sources())
    assert not gone, f"{gone} no longer exist: remove them from pyproject.toml's strict list or strict_exempt.json."
