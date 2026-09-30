"""folderwatch Unit Tests

The watcher looks at a folder of Tasker backups and records each new one in the history.  What
is tested is how it behaves in the three situations that go wrong with a folder of backups: a
file that is still being written, a folder that already holds a year of backups, and the same
backup seen twice.  Nothing sleeps and nothing is scheduled: the watcher is given the time, and
asked to look one time at a time.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from maptasker.src import folderwatch, timeline

_SYNTHETIC_BACKUP = Path(__file__).parent / "data" / "synthetic_backup.xml"
_NOW = 2_000_000_000.0  # The watcher's idea of the time, in seconds since the epoch.
_SETTLED = _NOW - 60  # A file last modified a minute ago: long finished being written.


@pytest.fixture(autouse=True)
def _history_in_a_scratch_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the history in the test's own folder, and put it back afterwards."""
    monkeypatch.chdir(tmp_path)
    history = tmp_path / "history"
    timeline.use_history_folder(history)
    yield history
    timeline.use_history_folder(None)


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """An empty folder for backups to arrive in."""
    folder = tmp_path / "backups"
    folder.mkdir()
    return folder


def _backup(folder: Path, name: str, modified: float, *, marker: str = "") -> Path:
    """A whole Tasker backup in `folder`, last modified at `modified`.

    `marker` goes into the file as a comment, so two backups can be told apart without either
    stopping being a valid one.
    """
    text = _SYNTHETIC_BACKUP.read_text(encoding="utf-8")
    if marker:
        text = text.replace("<TaskerData", f"<!-- {marker} -->\n<TaskerData", 1)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    os.utime(path, (modified, modified))
    return path


def _watcher(folder: Path, *, now: float = _NOW, settle: float = 5) -> folderwatch.Watcher:
    return folderwatch.Watcher(folder, settle=settle, now=lambda: now)


def _outcomes(events: list[folderwatch.Event]) -> dict[str, str]:
    return {event.path.name: event.outcome for event in events}


# ##################################################################################
# What is a backup, and which one is newest
# ##################################################################################
def test_only_xml_files_in_the_folder_itself_count_and_come_oldest_first(folder: Path) -> None:
    _backup(folder, "b.xml", _NOW - 100)
    _backup(folder, "a.xml", _NOW - 200)
    (folder / "notes.txt").write_text("not a backup", encoding="utf-8")
    (folder / "sub").mkdir()
    _backup(folder / "sub", "deep.xml", _NOW - 10)

    assert [path.name for path in folderwatch.backup_files(folder)] == ["a.xml", "b.xml"]


def test_the_newest_backup_is_the_most_recently_modified_one(folder: Path) -> None:
    _backup(folder, "a.xml", _NOW - 100)
    _backup(folder, "z.xml", _NOW - 300)

    assert folderwatch.newest_backup(folder).name == "a.xml"


def test_an_empty_or_missing_folder_has_no_newest_backup(folder: Path, tmp_path: Path) -> None:
    assert folderwatch.newest_backup(folder) is None
    assert folderwatch.newest_backup(tmp_path / "nowhere") is None


def test_a_whole_backup_is_complete(folder: Path) -> None:
    assert folderwatch.is_complete_backup(_backup(folder, "a.xml", _SETTLED))


def test_a_truncated_backup_is_not_complete(folder: Path) -> None:
    path = folder / "cut.xml"
    path.write_bytes(_SYNTHETIC_BACKUP.read_bytes()[:3000])

    assert not folderwatch.is_complete_backup(path)


def test_xml_that_is_not_a_tasker_backup_is_not_complete(folder: Path) -> None:
    path = folder / "other.xml"
    path.write_text("<html><body>hello</body></html>", encoding="utf-8")

    assert not folderwatch.is_complete_backup(path)


# ##################################################################################
# A file that is still being written
# ##################################################################################
def test_a_file_modified_moments_ago_is_left_for_the_next_look(folder: Path) -> None:
    _backup(folder, "new.xml", _NOW - 1)  # A second ago: perhaps still being copied.

    assert _watcher(folder).scan() == []


def test_the_same_file_is_recorded_once_it_has_settled(folder: Path) -> None:
    _backup(folder, "new.xml", _NOW - 1)
    events = _watcher(folder, now=_NOW + 30).scan()  # Thirty seconds later: surely done.

    assert _outcomes(events) == {"new.xml": folderwatch.RECORDED}


def test_a_half_written_file_is_not_recorded(folder: Path) -> None:
    path = folder / "partial.xml"
    path.write_bytes(_SYNTHETIC_BACKUP.read_bytes()[:3000])
    os.utime(path, (_SETTLED, _SETTLED))

    events = _watcher(folder).scan()

    assert _outcomes(events) == {"partial.xml": folderwatch.INCOMPLETE}
    assert timeline.snapshots() == []


def test_a_file_that_was_incomplete_is_looked_at_again_once_it_changes(folder: Path) -> None:
    path = folder / "growing.xml"
    path.write_bytes(_SYNTHETIC_BACKUP.read_bytes()[:3000])
    os.utime(path, (_SETTLED, _SETTLED))
    watcher = _watcher(folder)
    assert _outcomes(watcher.scan()) == {"growing.xml": folderwatch.INCOMPLETE}
    assert watcher.scan() == [], "a file that has not changed is not parsed again at every look"

    _backup(folder, "growing.xml", _SETTLED + 10)  # The copy finished.

    assert _outcomes(watcher.scan()) == {"growing.xml": folderwatch.RECORDED}


def test_a_backup_dated_in_the_future_is_recorded_not_waited_for(folder: Path) -> None:
    """A phone whose clock runs ahead of this one's: waiting for this clock to catch up would be forever."""
    _backup(folder, "ahead.xml", _NOW + 3600)

    events = _watcher(folder).scan()

    assert _outcomes(events) == {"ahead.xml": folderwatch.RECORDED}


def test_a_backup_dated_in_the_future_is_entered_in_the_history_as_of_now(folder: Path) -> None:
    _backup(folder, "ahead.xml", _NOW + 3600)

    _watcher(folder).scan()

    assert timeline.snapshots()[-1].when.timestamp() <= _NOW + 1


# ##################################################################################
# A folder that already holds old backups
# ##################################################################################
def test_the_first_look_records_only_the_newest_of_many_old_backups(folder: Path) -> None:
    _backup(folder, "jan.xml", _NOW - 3000, marker="january")
    _backup(folder, "feb.xml", _NOW - 2000, marker="february")
    _backup(folder, "mar.xml", _NOW - 1000, marker="march")

    events = _watcher(folder).scan()

    assert _outcomes(events) == {"mar.xml": folderwatch.RECORDED}
    assert len(timeline.snapshots()) == 1


def test_the_old_backups_passed_over_are_not_recorded_by_a_later_look(folder: Path) -> None:
    _backup(folder, "jan.xml", _NOW - 3000, marker="january")
    _backup(folder, "mar.xml", _NOW - 1000, marker="march")
    watcher = _watcher(folder)
    watcher.scan()

    assert watcher.scan() == []
    assert len(timeline.snapshots()) == 1


def test_a_backup_that_arrives_later_is_recorded_dated_by_its_file(folder: Path) -> None:
    _backup(folder, "mon.xml", _NOW - 5000, marker="monday")
    watcher = _watcher(folder)
    watcher.scan()

    arrived = _backup(folder, "tue.xml", _NOW - 4000, marker="tuesday")
    events = watcher.scan()

    assert _outcomes(events) == {"tue.xml": folderwatch.RECORDED}
    newest = timeline.snapshots()[-1]
    assert newest.source == "tue.xml"
    assert abs(newest.when.timestamp() - arrived.stat().st_mtime) < 1, "the history is dated by the file, not the look"


# ##################################################################################
# The same backup seen twice
# ##################################################################################
def test_the_same_backup_under_a_new_name_adds_nothing(folder: Path) -> None:
    _backup(folder, "backup.xml", _NOW - 2000)
    watcher = _watcher(folder)
    watcher.scan()

    _backup(folder, "backup_copy.xml", _NOW - 1000)  # Same configuration, written again.

    assert _outcomes(watcher.scan()) == {"backup_copy.xml": folderwatch.UNCHANGED}
    assert len(timeline.snapshots()) == 1


def test_a_file_rewritten_with_new_content_is_recorded_again(folder: Path) -> None:
    _backup(folder, "backup.xml", _NOW - 2000, marker="one")
    watcher = _watcher(folder)
    watcher.scan()

    _backup(folder, "backup.xml", _NOW - 1000, marker="two")

    assert _outcomes(watcher.scan()) == {"backup.xml": folderwatch.RECORDED}
    assert len(timeline.snapshots()) == 2


def test_a_file_that_goes_and_comes_back_is_looked_at_afresh(folder: Path) -> None:
    path = _backup(folder, "backup.xml", _NOW - 2000)
    watcher = _watcher(folder)
    watcher.scan()
    path.unlink()
    assert watcher.scan() == []

    _backup(folder, "backup.xml", _NOW - 2000)  # Put back exactly as it was.

    assert _outcomes(watcher.scan()) == {"backup.xml": folderwatch.UNCHANGED}


# ##################################################################################
# watch(): the loop around the looks
# ##################################################################################
def test_watch_once_looks_a_single_time_and_does_not_wait_for_a_file_to_settle(folder: Path) -> None:
    """A scheduled run has nothing later to look again with, and the parse catches a half-written file."""
    _backup(folder, "new.xml", folderwatch.time.time() - 1)
    heard: list[folderwatch.Event] = []

    folderwatch.watch(folder, once=True, on_event=heard.append, sleep=lambda _seconds: pytest.fail("slept"))

    assert _outcomes(heard) == {"new.xml": folderwatch.RECORDED}


def test_watch_keeps_looking_between_naps_until_stopped(folder: Path) -> None:
    _backup(folder, "a.xml", folderwatch.time.time() - 600, marker="first")
    heard: list[folderwatch.Event] = []
    naps: list[float] = []

    def nap(seconds: float) -> None:
        naps.append(seconds)
        if len(naps) == 1:
            _backup(folder, "b.xml", folderwatch.time.time() - 600, marker="second")  # Arrives during the nap.
        else:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        folderwatch.watch(folder, interval=7, on_event=heard.append, sleep=nap)

    assert naps == [7, 7]
    assert [event.path.name for event in heard] == ["a.xml", "b.xml"]


# ##################################################################################
# timeline.use_history_folder, which the watcher depends on to share the GUI's history
# ##################################################################################
def test_the_history_can_be_kept_somewhere_other_than_the_working_directory(
    folder: Path,
    tmp_path: Path,
    _history_in_a_scratch_folder: Path,
) -> None:
    _backup(folder, "a.xml", _SETTLED)

    _watcher(folder).scan()

    assert list(_history_in_a_scratch_folder.glob("*.xml.gz")), "it was not written where it was told to"
    assert not (tmp_path / timeline.HISTORY_FOLDER).exists(), "it was also written to the working directory"


def test_no_override_means_the_working_directory_again(tmp_path: Path) -> None:
    timeline.use_history_folder(None)
    backup = _backup(tmp_path, "a.xml", _SETTLED)

    timeline.record(str(backup))

    assert list((tmp_path / timeline.HISTORY_FOLDER).glob("*.xml.gz"))
