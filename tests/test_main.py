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
import subprocess
import sys
from collections.abc import Iterator

import pytest
from maptasker import main as entry_point
from maptasker.src import clireports, mapit
from maptasker.src.core.mtexcept import MapTaskerError


@pytest.fixture(autouse=True)
def _restore_sys_path() -> Iterator[None]:
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
    monkeypatch.setattr(mapit, "mapit_all", lambda: 7)
    monkeypatch.setattr(sys, "argv", ["maptasker"])

    assert entry_point.main() == 7


def test_the_version_alone_is_said_without_starting_the_program(monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(entry_point, "display_version", lambda: said.append("version"))
    monkeypatch.setattr(mapit, "mapit_all", lambda: pytest.fail("the whole program was started to say the version"))
    monkeypatch.setattr(sys, "argv", ["maptasker", "-v"])

    assert entry_point.main() == 0
    assert said == ["version"]


def test_the_version_ending_with_a_failure_code_hands_that_code_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> None:
        raise MapTaskerError(exit_code=3)

    monkeypatch.setattr(entry_point, "display_version", refuse)
    monkeypatch.setattr(sys, "argv", ["maptasker", "-v"])

    assert entry_point.main() == 3


@pytest.mark.parametrize("argv", [["maptasker", "-v", "-d"], ["maptasker", "-d"], ["maptasker", "-v", "-v"]])
def test_anything_besides_the_version_takes_the_full_route(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(entry_point, "display_version", lambda: pytest.fail("the short route was taken"))
    monkeypatch.setattr(mapit, "mapit_all", lambda: 5)
    monkeypatch.setattr(sys, "argv", argv)

    assert entry_point.main() == 5


def test_saying_the_version_leaves_the_program_unimported() -> None:
    """The point of the short route, checked where it counts: in a fresh interpreter, which imports what it imports."""
    code = (
        "import sys; sys.argv = ['maptasker', '-v']\n"
        "from maptasker.main import main\n"
        "main()\n"
        "heavy = [m for m in ('nicegui', 'fastapi', 'maptasker.src.mapit', 'maptasker.src.runcli') if m in sys.modules]\n"
        "print('LOADED', heavy)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert "LOADED []" in result.stdout


def test_a_report_is_run_without_starting_the_program(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[list[str]] = []

    def fake_run(argv: list[str]) -> int:
        ran.append(argv)
        return 10

    monkeypatch.setattr(clireports, "run", fake_run)
    monkeypatch.setattr(mapit, "mapit_all", lambda: pytest.fail("the whole program was started for a report"))
    monkeypatch.setattr(sys, "argv", ["maptasker", "-healthcheck", "-file", "backup.xml"])

    assert entry_point.main() == 10
    assert ran == [["-healthcheck", "-file", "backup.xml"]]


def test_asking_for_a_reports_help_leaves_the_window_framework_unimported() -> None:
    """In a fresh interpreter, which imports only what the report needs: no web framework, no windows."""
    code = (
        "import sys; sys.argv = ['maptasker', '-healthcheck', '-h']\n"
        "from maptasker.main import main\n"
        "try:\n"
        "    main()\n"
        "except SystemExit:\n"
        "    pass\n"
        "loaded = [m for m in ('nicegui', 'fastapi', 'maptasker.src.mapit', 'maptasker.src.rungui') if m in sys.modules]\n"
        "print('LOADED', loaded)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert "LOADED []" in result.stdout
