"""MapTasker entry point unit tests

main.py is two lines of logic and one rule: importing it must not change how the
interpreter resolves imports.  It used to break that rule twice over -- inserting the
project root into sys.path and then a bundled overrides directory at position 0 -- which
is a global change made by a package on the strength of having been installed, and the
sort of thing that produces a bug report nobody else can reproduce.

These tests are what stops that coming back.  They restore sys.path afterwards, since a
test that leaked it would be doing the very thing the module is being tested for not
doing.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest
from maptasker import main as entry_point


@pytest.fixture(autouse=True)
def _restore_sys_path() -> None:
    """Put sys.path back exactly as it was, whatever a test did to it."""
    original = list(sys.path)
    yield
    sys.path[:] = original


def test_importing_the_entry_point_leaves_sys_path_alone() -> None:
    """Re-importing the module must not touch sys.path.

    The module is already imported by the time this runs, so this is really a test that
    nothing at module scope has anything to say about the import path -- which is the
    whole of the fix.
    """
    before = list(sys.path)

    importlib.reload(entry_point)

    assert sys.path == before


def test_the_entry_point_adds_nothing_to_the_front_of_the_import_path() -> None:
    """Nothing under the installed package sits ahead of the installed packages.

    Stated as its own test rather than left to the reload above, because the failure it
    guards against is not "sys.path changed during this test" -- it is a directory put
    there at any point during start-up, by a mechanism added later.
    """
    package_directory = os.path.dirname(os.path.abspath(entry_point.__file__))

    assert not [path for path in sys.path if path.startswith(package_directory)]


def test_main_returns_the_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() hands back what mapit_all returns -- what the console script exits with."""
    monkeypatch.setattr(entry_point, "mapit_all", lambda: 7)

    assert entry_point.main() == 7
