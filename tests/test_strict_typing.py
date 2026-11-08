"""Every module in maptasker/src is held to pyright's strict mode.

Basic mode is ratcheted by scripts/typecheck_ratchet.py (pyright_baseline.json), which stops the
count of errors rising.  Strict mode finds a good deal more -- every value of unknown type -- so it was
switched on file by file as each module was cleaned, and the files [tool.pyright] strict lists are clean
under it (the ratchet fails if one stops being).

All of maptasker/src is on that list now, and what this test keeps is that it stays so: a new module is
written strict-clean and listed in pyproject.toml.  There is no exempt list to add it to any more.
"""

from __future__ import annotations

import pathlib
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "maptasker" / "src"


def _sources() -> set[str]:
    return {path.relative_to(_ROOT).as_posix() for path in _SOURCE.rglob("*.py")}


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
    gone = sorted(_strict() - _sources())
    assert not gone, f"{gone} no longer exist: remove them from pyproject.toml's strict list."
