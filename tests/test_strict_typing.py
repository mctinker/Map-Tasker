"""Every module in maptasker/src is held to pyright's strict mode.

Basic mode is ratcheted by scripts/typecheck_ratchet.py (pyright_baseline.json), which stops the
count of errors rising.  Strict mode finds a good deal more -- every value of unknown type -- so it was
switched on file by file as each module was cleaned, and the files [tool.pyright] strict lists are clean
under it (the ratchet fails if one stops being).

All of maptasker/src is on that list now, and what this test keeps is that it stays so: a new module is
written strict-clean and listed in pyproject.toml.  There is no exempt list to add it to any more.

The tests and the tools are being brought under it the same way, a file at a time.  A file that is written strict-clean
is listed in pyproject.toml, and the ratchet holds it there.  The ones not yet converted are named in
tests/strict_pending.txt, which can only shrink: a new test or tool is written strict-clean, and a pending file that has
become clean (or has gone) has to come off the list.  A test that reaches into private helpers on purpose says so with
`# pyright: reportPrivateUsage=false` at the top, which is the one rule a test is allowed to turn off.
"""

from __future__ import annotations

import pathlib
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "maptasker" / "src"


def _sources() -> set[str]:
    return {path.relative_to(_ROOT).as_posix() for path in _SOURCE.rglob("*.py")}


def _written_here() -> set[str]:
    """Every test and tool, as a path from the repository root."""
    found: set[str] = set()
    for folder in ("tests", "tools"):
        found |= {path.relative_to(_ROOT).as_posix() for path in (_ROOT / folder).rglob("*.py")}
    return found


def _pending() -> set[str]:
    lines = (_ROOT / "tests" / "strict_pending.txt").read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def _strict() -> set[str]:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(config["tool"]["pyright"]["strict"])


def test_a_new_module_is_written_strict_clean() -> None:
    new = sorted(_sources() - _strict())
    assert not new, (
        f"{new} are not in [tool.pyright] strict.  Every module is written clean under pyright's strict mode "
        "and added to the strict list in pyproject.toml."
    )


def test_the_list_names_modules_that_exist() -> None:
    gone = sorted(_strict() - _sources() - _written_here())
    assert not gone, f"{gone} no longer exist: remove them from pyproject.toml's strict list."


def test_a_new_test_or_tool_is_written_strict_clean() -> None:
    new = sorted(_written_here() - _strict() - _pending())
    assert not new, (
        f"{new} are neither in [tool.pyright] strict nor on tests/strict_pending.txt.  Write them clean under "
        "pyright's strict mode and add them to the strict list in pyproject.toml (the pending list only shrinks)."
    )


def test_a_pending_file_that_is_strict_or_gone_comes_off_the_list() -> None:
    done = sorted(_pending() & _strict())
    gone = sorted(_pending() - _written_here())
    assert not done, f"{done} are in the strict list now: remove them from tests/strict_pending.txt."
    assert not gone, f"{gone} no longer exist: remove them from tests/strict_pending.txt."
