"""'Upgrade To New Version' Unit Tests

Two things went wrong on Windows when the upgrade button was pressed, and both left the
user worse off than not pressing it at all:

* pip cannot delete the running 'maptasker.exe', so the install died with 'WinError 32 ...
  being used by another process' -- and the program restarted anyway, announcing an upgrade
  that had not happened.
* the change log written afterwards is full of characters (arrows, bullets, curly quotes)
  that Windows' default cp1252 cannot encode, so writing it raised UnicodeEncodeError.

Nothing here installs anything or reaches the network: the installer is a stub and the
change log's contents are handed over directly.
"""

from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace

import pytest
from maptasker.src import guiutils, maputils


class FakeCompletedProcess(SimpleNamespace):
    """Enough of subprocess.CompletedProcess for update_maptasker."""


@pytest.fixture
def scripts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in for the environment's Scripts directory, holding a 'maptasker.exe'."""
    script_dir = tmp_path / "Scripts"
    script_dir.mkdir()
    (script_dir / "maptasker.exe").write_text("the running program")
    monkeypatch.setattr(maputils.sys, "executable", str(script_dir / "python.exe"))
    monkeypatch.setattr(maputils.sys, "platform", "win32")
    return script_dir


def test_locked_scripts_left_alone_off_windows(scripts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every other platform replaces a running program's file, so there is nothing to do."""
    monkeypatch.setattr(maputils.sys, "platform", "darwin")

    assert maputils.move_locked_scripts_aside() == []
    assert (scripts_dir / "maptasker.exe").is_file()


def test_locked_script_moved_aside(scripts_dir: Path) -> None:
    """The name the installer needs is freed up, and we can still say where it went."""
    moved = maputils.move_locked_scripts_aside()

    stashed = scripts_dir / f"maptasker.exe{maputils.STASHED_SCRIPT_SUFFIX}"
    assert moved == [(scripts_dir / "maptasker.exe", stashed)]
    assert not (scripts_dir / "maptasker.exe").exists()
    assert stashed.read_text() == "the running program"


def test_leftover_stash_cleared_first(scripts_dir: Path) -> None:
    """The stash from the last upgrade is nothing to run from now: it is overwritten."""
    stashed = scripts_dir / f"maptasker.exe{maputils.STASHED_SCRIPT_SUFFIX}"
    stashed.write_text("last upgrade's leftover")

    maputils.move_locked_scripts_aside()

    assert stashed.read_text() == "the running program"


def test_missing_script_is_not_missed(scripts_dir: Path) -> None:
    """An environment without our console script has nothing in the installer's way."""
    (scripts_dir / "maptasker.exe").unlink()

    assert maputils.move_locked_scripts_aside() == []


def test_restore_puts_back_what_the_installer_never_wrote(scripts_dir: Path) -> None:
    """A failed install must not leave the environment without its 'maptasker' command."""
    moved = maputils.move_locked_scripts_aside()

    maputils.restore_locked_scripts(moved)

    assert (scripts_dir / "maptasker.exe").read_text() == "the running program"
    assert not (scripts_dir / f"maptasker.exe{maputils.STASHED_SCRIPT_SUFFIX}").exists()


def test_restore_keeps_the_new_script(scripts_dir: Path) -> None:
    """A script the installer did write is the new version, and stays."""
    moved = maputils.move_locked_scripts_aside()
    (scripts_dir / "maptasker.exe").write_text("the new version")

    maputils.restore_locked_scripts(moved)

    assert (scripts_dir / "maptasker.exe").read_text() == "the new version"


@pytest.fixture
def installer(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stands in for pip/uv, recording the command and returning what the test asks for."""
    recorded = {"command": None, "returncode": 0, "stderr": "", "stdout": ""}

    def fake_run(command, **_kwargs):
        recorded["command"] = command
        return FakeCompletedProcess(
            returncode=recorded["returncode"],
            stderr=recorded["stderr"],
            stdout=recorded["stdout"],
        )

    monkeypatch.setattr(maputils.subprocess, "run", fake_run)
    monkeypatch.setattr(maputils, "get_pypi_version", lambda: "==14.0.5")
    monkeypatch.setattr(maputils.console, "say", lambda *_args, **_kwargs: None)
    return recorded


def test_the_script_is_moved_aside_before_the_installer_runs(
    scripts_dir: Path,
    installer: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point: the name is free by the time the installer wants to write it."""
    monkeypatch.setattr(maputils.shutil, "which", lambda _name: None)
    seen = {}

    def fake_run(command, **_kwargs):
        seen["exe_exists"] = (scripts_dir / "maptasker.exe").exists()
        (scripts_dir / "maptasker.exe").write_text("the new version")
        return FakeCompletedProcess(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(maputils.subprocess, "run", fake_run)

    assert maputils.update_maptasker() == (True, "")
    assert seen["exe_exists"] is False


def test_a_failed_install_is_reported_not_assumed_away(
    scripts_dir: Path,
    installer: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restarting into a version that was never installed is what this has to prevent."""
    monkeypatch.setattr(maputils.shutil, "which", lambda _name: None)
    installer["returncode"] = 1
    installer["stderr"] = "ERROR: Could not install packages due to an OSError: [WinError 32]"

    updated, complaint = maputils.update_maptasker()

    assert updated is False
    assert "WinError 32" in complaint
    # ...and the command we came in with is still there to be run next time.
    assert (scripts_dir / "maptasker.exe").read_text() == "the running program"


def test_an_installer_that_will_not_start_is_reported(
    scripts_dir: Path,
    installer: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No pip, no uv, no upgrade -- but also no crash and no bogus restart."""
    monkeypatch.setattr(maputils.shutil, "which", lambda _name: None)

    def fake_run(_command, **_kwargs):
        message = "no such file"
        raise OSError(message)

    monkeypatch.setattr(maputils.subprocess, "run", fake_run)

    updated, complaint = maputils.update_maptasker()

    assert updated is False
    assert "no such file" in complaint
    assert (scripts_dir / "maptasker.exe").read_text() == "the running program"


def test_a_silent_installer_still_says_something(
    scripts_dir: Path,
    installer: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare non-zero return code is all there is to go on: pass it along."""
    monkeypatch.setattr(maputils.shutil, "which", lambda _name: None)
    installer["returncode"] = 2

    updated, complaint = maputils.update_maptasker()

    assert updated is False
    assert complaint


def test_uv_upgrades_the_copy_we_are_running(
    scripts_dir: Path,
    installer: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """uv otherwise picks an environment out of VIRTUAL_ENV or the current directory."""
    monkeypatch.setattr(maputils.shutil, "which", lambda name: f"/usr/local/bin/{name}")

    maputils.update_maptasker()

    command = installer["command"]
    assert command[:3] == ["uv", "pip", "install"]
    assert command[command.index("--python") + 1] == maputils.sys.executable
    assert "maptasker==14.0.5" in command


def test_pip_upgrades_the_copy_we_are_running(
    scripts_dir: Path,
    installer: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without uv it is our own interpreter's pip, which installs where we are."""
    monkeypatch.setattr(maputils.shutil, "which", lambda _name: None)

    maputils.update_maptasker()

    assert installer["command"][:4] == [maputils.sys.executable, "-m", "pip", "install"]


# The character the change log actually died on: a small down-pointing triangle.
UNENCODABLE = "▾"


@pytest.fixture
def windows_default_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Text written without naming an encoding goes through cp1252, as it does on Windows."""
    real_open = builtins.open

    def cp1252_open(file, mode="r", *args, **kwargs):
        if "b" not in mode and not kwargs.get("encoding"):
            kwargs["encoding"] = "cp1252"
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", cp1252_open)


def test_change_log_is_written_whatever_is_in_it(
    tmp_path: Path,
    windows_default_encoding: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The change log is written on GitHub in utf-8, and cp1252 cannot encode half of it."""
    changelog = tmp_path / "changelog.txt"
    monkeypatch.setattr(guiutils, "CHANGELOG_FILE", str(changelog))
    monkeypatch.setattr(guiutils, "get_changelog_file", lambda *_args: [f"## [14.0.5] {UNENCODABLE} FIX"])

    guiutils.create_changelog()

    assert UNENCODABLE in changelog.read_text(encoding="utf-8")


def test_change_log_is_read_back_the_way_it_was_written(
    tmp_path: Path,
    windows_default_encoding: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'What's New?' shows it after the restart, and must not choke on it either."""
    changelog = tmp_path / "changelog.txt"
    changelog.write_text(f"## [14.0.5] {UNENCODABLE} FIX\n", encoding="utf-8")
    monkeypatch.setattr(guiutils, "CHANGELOG_FILE", str(changelog))
    view = SimpleNamespace(message="")

    guiutils.check_for_changelog(view)

    assert UNENCODABLE in view.message
    assert not changelog.exists()  # shown once, then cleared away


def test_an_unwritable_change_log_does_not_strand_the_upgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing to read afterwards is a disappointment; a crash before the restart is not."""
    monkeypatch.setattr(guiutils, "CHANGELOG_FILE", str(tmp_path / "no-such-directory" / "changelog.txt"))
    monkeypatch.setattr(guiutils, "get_changelog_file", lambda *_args: ["## [14.0.5] FIX"])
    complaints = []
    monkeypatch.setattr(guiutils, "rutroh_error", complaints.append)

    guiutils.create_changelog()

    assert complaints
