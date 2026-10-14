"""Safety copies: a save that overwrites a file keeps the old one first, and says so when it cannot."""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src.core import presave


def test_nothing_to_copy_is_not_a_failure(tmp_path: Path) -> None:
    """The ordinary case for a save to a new name, and for a save with no path at all."""
    assert presave.backup_local_file("") == (True, "")
    assert presave.backup_local_file(str(tmp_path / "new.prj.xml")) == (True, "")
    assert not (tmp_path / presave.BACKUP_FOLDER).exists()


def test_an_existing_file_is_copied_beside_itself(tmp_path: Path) -> None:
    """The copy is in MapTasker_Backups next to the original, keeps the whole compound extension
    and has the original's content."""
    original = tmp_path / "Wake Up.tsk.xml"
    original.write_text("<Task/>", encoding="utf-8")

    done, copy = presave.backup_local_file(str(original))

    assert done
    made = Path(copy)
    assert made.parent == tmp_path / presave.BACKUP_FOLDER
    assert made.name.startswith("Wake Up_")
    assert made.name.endswith(".tsk.xml")
    assert made.read_text(encoding="utf-8") == "<Task/>"
    assert original.read_text(encoding="utf-8") == "<Task/>"  # the original is left where it was


def test_only_the_newest_copies_are_kept(tmp_path: Path) -> None:
    """Repeated saves of one file cannot fill the disk: the oldest copies beyond the limit go,
    and a file the user put in the folder themselves is never touched."""
    folder = tmp_path / presave.BACKUP_FOLDER
    folder.mkdir()
    for number in range(presave.MAX_COPIES_PER_FILE + 3):
        (folder / f"Home_20260101_0000{number:02d}.prj.xml").write_text("old", encoding="utf-8")
    (folder / "Home_notes.txt").write_text("mine", encoding="utf-8")
    original = tmp_path / "Home.prj.xml"
    original.write_text("<Project/>", encoding="utf-8")

    assert presave.backup_local_file(str(original))[0]

    copies = sorted(entry.name for entry in folder.glob("Home_2*.prj.xml"))
    assert len(copies) == presave.MAX_COPIES_PER_FILE
    assert "Home_20260101_000000.prj.xml" not in copies  # the oldest went first
    assert (folder / "Home_notes.txt").exists()


def test_a_copy_that_cannot_be_removed_does_not_stop_the_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pruning is housekeeping.  Failing at it is logged, and the new copy is still reported."""
    folder = tmp_path / presave.BACKUP_FOLDER
    folder.mkdir()
    for number in range(presave.MAX_COPIES_PER_FILE + 1):
        (folder / f"Home_20260101_0000{number:02d}.prj.xml").write_text("old", encoding="utf-8")
    original = tmp_path / "Home.prj.xml"
    original.write_text("<Project/>", encoding="utf-8")

    def refuse(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "unlink", refuse)
    assert presave.backup_local_file(str(original))[0]


def test_a_folder_that_cannot_be_made_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The caller says so and saves anyway: a copy that fails never blocks a save."""
    original = tmp_path / "Home.prj.xml"
    original.write_text("<Project/>", encoding="utf-8")

    def refuse(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "mkdir", refuse)
    done, message = presave.backup_local_file(str(original))
    assert not done
    assert presave.BACKUP_FOLDER in message


def test_a_file_that_cannot_be_copied_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "Home.prj.xml"
    original.write_text("<Project/>", encoding="utf-8")

    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(presave.shutil, "copy2", refuse)
    assert presave.backup_local_file(str(original)) == (False, "disk full")


def test_an_unreadable_path_is_not_taken_for_an_absent_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken mount cannot be told from a file that is not there, so it is reported rather than skipped."""

    def refuse(self: Path) -> bool:
        raise OSError("input/output error")

    monkeypatch.setattr(Path, "is_file", refuse)
    assert presave.backup_local_file("/somewhere/Home.prj.xml") == (False, "input/output error")


def test_nothing_on_the_device_means_nothing_to_keep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert presave.save_android_safety_copy("", b"x") == (True, "")
    assert presave.save_android_safety_copy("/Tasker/projects/A.prj.xml", b"") == (True, "")
    assert not (tmp_path / presave.BACKUP_FOLDER).exists()


def test_what_was_on_the_device_is_kept_under_a_name_saying_where_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A device path cannot be a filename, so it is flattened -- otherwise "which folder was this?"
    could not be answered later."""
    monkeypatch.chdir(tmp_path)

    done, copy = presave.save_android_safety_copy("/Tasker/projects/My Project.prj.xml", b"<Project/>")

    assert done
    made = Path(copy)
    assert made.parent == tmp_path / presave.BACKUP_FOLDER
    assert made.name.startswith("Tasker_projects_My Project_")
    assert made.name.endswith(".prj.xml")
    assert made.read_bytes() == b"<Project/>"


def test_a_device_copy_that_cannot_be_written_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    def refuse(self: Path, data: bytes) -> int:
        raise OSError("no space left")

    monkeypatch.setattr(Path, "write_bytes", refuse)
    assert presave.save_android_safety_copy("/Tasker/a.prj.xml", b"x") == (False, "no space left")


def test_a_device_copy_in_an_unwritable_folder_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    def refuse(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "mkdir", refuse)
    done, message = presave.save_android_safety_copy("/Tasker/a.prj.xml", b"x")
    assert not done
    assert presave.BACKUP_FOLDER in message
