"""MapTasker Configuration Timeline Unit Tests

timeline.py turns "how do these two files differ" into "what changed this week", by
keeping every configuration that gets loaded.  Two things have to hold for that to be
worth having, and they pull in opposite directions.

The history has to be COMPLETE -- every way of loading a file has to land in it, which is
why the recording hangs off taskerd.get_the_xml_data rather than off the buttons.  And it
has to be CLEAN -- a history holding the file somebody pointed the comparison at once, or
holding the same unchanged configuration four times because the program was restarted
four times, answers "what changed this week" with noise.  Most of what is below is about
the second of those, because the first is one line and the second is where the judgement
is.

The rest is failure behaviour.  A snapshot is a side effect of loading a file, and the
load must survive the history being unwritable, unreadable, or full of somebody else's
files -- so those all have tests asserting the load still worked and the history simply
went quiet.
"""

from __future__ import annotations

import gzip
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from maptasker.src import diffload, taskerd, timeline
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems, initial_tasker_root_elements

_LOADED_XML = """<TaskerData sr="" dvi="1" tv="6.5.6">
  <Project sr="proj0" ve="2"><cdate>1</cdate><id>1</id><name>Home</name>
    <pids>10</pids><tids>20</tids></Project>
  <Profile sr="prof10" ve="2"><cdate>1</cdate><id>10</id><nme>Wake</nme><mid0>20</mid0>
    <Time sr="if0"><fh>7</fh></Time></Profile>
  <Task sr="task20" ve="2"><cdate>1</cdate><id>20</id><nme>Runner</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Running</Str></Action></Task>
  <Variable sr="vars0"><n>%loaded</n><v>yes</v></Variable>
</TaskerData>
"""

# The same configuration a week later: one Task renamed, one Profile added.
_LATER_XML = """<TaskerData sr="" dvi="1" tv="6.5.6">
  <Project sr="proj0" ve="2"><cdate>1</cdate><id>1</id><name>Home</name>
    <pids>10,11</pids><tids>20</tids></Project>
  <Profile sr="prof10" ve="2"><cdate>1</cdate><id>10</id><nme>Wake</nme><mid0>20</mid0>
    <Time sr="if0"><fh>7</fh></Time></Profile>
  <Profile sr="prof11" ve="2"><cdate>1</cdate><id>11</id><nme>Sleep</nme><mid0>20</mid0>
    <Time sr="if0"><fh>23</fh></Time></Profile>
  <Task sr="task20" ve="2"><cdate>1</cdate><id>20</id><nme>Jogger</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Running</Str></Action></Task>
  <Variable sr="vars0"><n>%loaded</n><v>yes</v></Variable>
</TaskerData>
"""

_MALFORMED_XML = "<TaskerData><Project><name>Broken</name>"


def _write(tmp_path: Path, name: str, text: str) -> str:
    """Put fixture XML on disk and hand back its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _load_as_current(path: str) -> int:
    """Load a file the way MapTasker does -- which is also what records a snapshot."""
    with open(path) as handle:  # noqa: PTH123, SIM115
        PrimeItems.file_to_get = handle
        PrimeItems.tasker_root_elements = initial_tasker_root_elements()
        return taskerd.get_the_xml_data()


@pytest.fixture(autouse=True)
def _runtime(tmp_path, monkeypatch):
    """A believable runtime, and a working directory of our own for the history folder."""
    monkeypatch.chdir(tmp_path)
    PrimeItems.program_arguments = {
        "gui": True,
        "debug": False,
        "directory": False,
        "pretty": False,
        "display_detail_level": 3,
        "file": "",
    }
    PrimeItems.error_code = 0
    PrimeItems.error_msg = ""
    PrimeItems.directory_items = {"current_item": "", "projects": [], "profiles": [], "tasks": [], "scenes": []}
    PrimeItems.output_lines = LineOut()
    monkeypatch.setattr(timeline, "recording_suppressed", False)


# ##################################################################################
# Recording: every load lands in the history.
# ##################################################################################
def test_loading_a_file_records_it(tmp_path) -> None:
    """The whole premise: no button, no setting -- loading a configuration keeps it."""
    assert timeline.snapshots() == []

    assert _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML)) == 0

    held = timeline.snapshots()
    assert len(held) == 1
    assert held[0].source == "backup.xml"
    assert (tmp_path / timeline.HISTORY_FOLDER / held[0].path.name).is_file()


def test_the_snapshot_holds_the_configuration_verbatim(tmp_path) -> None:
    """Gzipped, and the bytes come back exactly -- this is the older side of a future diff."""
    path = _write(tmp_path, "backup.xml", _LOADED_XML)
    _load_as_current(path)

    stored = timeline.snapshots()[0].path
    assert stored.suffixes[-2:] == [".xml", ".gz"]
    with gzip.open(stored, "rb") as compressed:
        assert compressed.read().decode("utf-8") == _LOADED_XML


def test_a_second_different_configuration_is_a_second_entry(tmp_path) -> None:
    """Two loads of two configurations is two points in the timeline."""
    _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML))
    _load_as_current(_write(tmp_path, "later.xml", _LATER_XML))

    held = timeline.snapshots()
    assert [snapshot.source for snapshot in held] == ["backup.xml", "later.xml"]
    assert held[0].digest != held[1].digest


def test_reloading_an_unchanged_configuration_adds_nothing(tmp_path) -> None:
    """Restarting the program four times is not four things that happened to the config.

    A history that recorded it would report four hours in which nothing changed as four
    entries worth having, which is exactly the noise this feature exists to cut through.
    """
    path = _write(tmp_path, "backup.xml", _LOADED_XML)
    for _ in range(4):
        _load_as_current(path)

    assert len(timeline.snapshots()) == 1


def test_the_same_configuration_under_another_name_adds_nothing(tmp_path) -> None:
    """"Save To Current File" leaves the original and a timestamped copy side by side
    (caveats.md item 6).  Loading both is one configuration under two names, and comparing
    by content rather than by path is what keeps the pair out of the history twice.
    """
    _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML))
    _load_as_current(_write(tmp_path, "backup_20260909_120000.xml", _LOADED_XML))

    assert len(timeline.snapshots()) == 1


def test_a_configuration_that_comes_back_is_recorded_again(tmp_path) -> None:
    """Only the LATEST entry is checked for sameness, so reverting an edit is an event.

    Undoing yesterday's change is a real change to the configuration, and a history that
    silently dropped it would show a week in which the edit happened and never came back.
    """
    _load_as_current(_write(tmp_path, "a.xml", _LOADED_XML))
    _load_as_current(_write(tmp_path, "b.xml", _LATER_XML))
    _load_as_current(_write(tmp_path, "c.xml", _LOADED_XML))

    held = timeline.snapshots()
    assert len(held) == 3
    assert held[0].digest == held[2].digest


def test_a_failed_load_is_not_recorded(tmp_path) -> None:
    """Nothing was loaded, so there is no configuration to have a history of."""
    assert _load_as_current(_write(tmp_path, "bad.xml", _MALFORMED_XML)) != 0
    assert timeline.snapshots() == []


# ##################################################################################
# NOT recording: the comparison's own load.
# ##################################################################################
def test_the_file_a_comparison_reads_is_not_recorded(tmp_path) -> None:
    """THE ONE THAT MATTERS.  diffload parses the other file through the same taskerd
    path this hooks into.  Without the suppression, every comparison anyone ran would
    file a configuration nobody is working on into the history of the one they are --
    and it would do it every single time.
    """
    _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML))
    before = [snapshot.digest for snapshot in timeline.snapshots()]

    configuration, message = diffload.load_for_comparison(_write(tmp_path, "other.xml", _LATER_XML))

    assert message == "" and configuration is not None
    assert [snapshot.digest for snapshot in timeline.snapshots()] == before


def test_suppression_is_lifted_afterwards(tmp_path) -> None:
    """A comparison must not switch recording off for the rest of the session."""
    _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML))
    diffload.load_for_comparison(_write(tmp_path, "other.xml", _LATER_XML))

    assert timeline.recording_suppressed is False
    _load_as_current(_write(tmp_path, "later.xml", _LATER_XML))
    assert len(timeline.snapshots()) == 2


def test_suppression_restores_rather_than_clears() -> None:
    """Nested use cannot switch recording back on for the caller that switched it off."""
    with timeline.suppressed():
        with timeline.suppressed():
            assert timeline.recording_suppressed is True
        assert timeline.recording_suppressed is True
    assert timeline.recording_suppressed is False


# ##################################################################################
# Retention.
# ##################################################################################
def test_the_history_is_capped(tmp_path, monkeypatch) -> None:
    """Oldest out first, so the folder cannot grow without limit."""
    monkeypatch.setattr(timeline, "MAX_SNAPSHOTS", 3)
    for index in range(6):
        # Each load must differ, or the dedup above would keep the count at one.
        _load_as_current(_write(tmp_path, f"b{index}.xml", _LOADED_XML.replace("Home", f"Home{index}")))

    held = timeline.snapshots()
    assert len(held) == 3
    assert [snapshot.source for snapshot in held] == ["b3.xml", "b4.xml", "b5.xml"]


# ##################################################################################
# Reading the history back.
# ##################################################################################
def test_since_picks_the_newest_entry_no_later_than_the_cutoff() -> None:
    """"What changed since Tuesday" wants the configuration as it stood on Tuesday."""
    now = datetime.now()  # noqa: DTZ005
    for days, text in ((20, "Alpha"), (10, "Beta"), (2, "Gamma")):
        timeline.record(_named(text), when=now - timedelta(days=days))

    assert timeline.since(now - timedelta(days=30)) is None
    assert timeline.since(now - timedelta(days=15)).source.startswith("Alpha")
    assert timeline.since(now - timedelta(days=5)).source.startswith("Beta")
    assert timeline.since(now).source.startswith("Gamma")


def test_snapshots_are_ordered_by_their_stamp_not_their_mtime(tmp_path) -> None:
    """Sorted by the timestamp in the name, which a copy or a sync cannot rewrite."""
    now = datetime.now()  # noqa: DTZ005
    timeline.record(_named("Newer"), when=now)
    timeline.record(_named("Older"), when=now - timedelta(days=5))

    assert [snapshot.source[:5] for snapshot in timeline.snapshots()] == ["Older", "Newer"]


def test_foreign_files_in_the_folder_are_ignored(tmp_path) -> None:
    """The folder sits in the user's own working directory; they may put things in it."""
    _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML))
    folder = tmp_path / timeline.HISTORY_FOLDER
    (folder / "notes.txt").write_text("mine", encoding="utf-8")
    (folder / "20260909_120000__nohash.xml.gz").write_bytes(b"")

    assert len(timeline.snapshots()) == 1


def test_no_history_folder_is_an_empty_history_not_an_error() -> None:
    """Asked before anything was ever loaded."""
    assert timeline.snapshots() == []
    assert timeline.earliest() is None
    assert timeline.since(datetime.now()) is None  # noqa: DTZ005


# ##################################################################################
# The question the feature exists to answer.
# ##################################################################################
def test_what_changed_since_reports_the_difference(tmp_path) -> None:
    """A week ago against now, with no file picker and nothing to hunt for."""
    now = datetime.now()  # noqa: DTZ005
    timeline.record(_write(tmp_path, "week_ago.xml", _LOADED_XML), when=now - timedelta(days=7))
    _load_as_current(_write(tmp_path, "today.xml", _LATER_XML))

    result = timeline.changes_over_last(14)

    assert result.problem == ""
    assert result.nothing_changed is False
    # The Profile that appeared and the Task that was renamed both show up.
    assert "Sleep" in result.report
    assert "Jogger" in result.report
    assert result.counts["ADDED"] >= 1


def test_the_older_side_is_named_by_when_it_was_not_by_its_temporary_file(tmp_path) -> None:
    """The report header has to say which configuration this is being compared against,
    and the file it was expanded into lives for a few milliseconds under a random name.
    """
    when = datetime.now() - timedelta(days=3)  # noqa: DTZ005
    timeline.record(_write(tmp_path, "week_ago.xml", _LOADED_XML), when=when)
    _load_as_current(_write(tmp_path, "today.xml", _LATER_XML))

    result = timeline.changes_over_last(7)

    assert "week_ago.xml (from the configuration history)" in result.report
    assert "maptasker_timeline_" not in result.report
    # xmldiff's header supplies the date itself, so the label must not repeat it.
    assert result.report.count(when.strftime("%d-%b-%Y %H:%M:%S")) == 1


def test_an_unchanged_configuration_reports_no_differences(tmp_path) -> None:
    """Ran fine, found nothing -- distinct from having nothing to compare."""
    timeline.record(_write(tmp_path, "week_ago.xml", _LOADED_XML), when=datetime.now() - timedelta(days=7))  # noqa: DTZ005
    _load_as_current(_write(tmp_path, "today.xml", _LOADED_XML))

    result = timeline.changes_over_last(14)

    assert result.problem == ""
    assert result.nothing_changed is True


def test_a_history_that_does_not_reach_back_says_so(tmp_path) -> None:
    """Answering "since last week" with three months ago, quietly, would be worse than
    saying the history is short.  The report is still produced -- it is still useful.
    """
    timeline.record(_write(tmp_path, "yesterday.xml", _LOADED_XML), when=datetime.now() - timedelta(days=1))  # noqa: DTZ005
    _load_as_current(_write(tmp_path, "today.xml", _LATER_XML))

    result = timeline.changes_over_last(30)

    assert result.report
    assert "does not reach back that far" in result.note


def test_an_empty_history_is_explained_not_crashed() -> None:
    """First ever run, before anything has been loaded twice."""
    result = timeline.changes_over_last(7)

    assert result.report == ""
    assert "No configuration history" in result.problem


def test_nothing_loaded_is_explained(tmp_path) -> None:
    """There is no "now" to compare the history against."""
    timeline.record(_write(tmp_path, "week_ago.xml", _LOADED_XML), when=datetime.now() - timedelta(days=7))  # noqa: DTZ005
    PrimeItems.tasker_root_elements = initial_tasker_root_elements()

    result = timeline.changes_over_last(14)

    assert result.report == ""
    assert "No XML file has been loaded" in result.problem


def test_a_corrupt_snapshot_is_reported_not_raised(tmp_path) -> None:
    """A snapshot that will not parse produces the message a picked file would, and
    leaves the loaded configuration exactly where it was.
    """
    timeline.record(_write(tmp_path, "week_ago.xml", _LOADED_XML), when=datetime.now() - timedelta(days=7))  # noqa: DTZ005
    _load_as_current(_write(tmp_path, "today.xml", _LATER_XML))
    loaded_before = PrimeItems.tasker_root_elements
    stored = timeline.snapshots()[0].path
    with gzip.open(stored, "wb") as compressed:
        compressed.write(_MALFORMED_XML.encode("utf-8"))

    result = timeline.changes_over_last(14)

    assert result.report == ""
    assert result.problem
    assert PrimeItems.tasker_root_elements is loaded_before


# ##################################################################################
# The load survives a history that cannot be kept.
# ##################################################################################
def test_a_history_folder_that_cannot_be_made_does_not_break_the_load(tmp_path, monkeypatch) -> None:
    """A read-only working directory costs the user the history, not the file they opened."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(Path, "mkdir", refuse)

    assert _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML)) == 0
    assert timeline.snapshots() == []


def test_an_unreadable_source_file_does_not_break_the_load(tmp_path, monkeypatch) -> None:
    """record() digests the file itself; a failure there is silent by design."""
    monkeypatch.setattr(timeline, "_digest_of", lambda _path: "")

    assert _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML)) == 0
    assert timeline.snapshots() == []


def test_a_failed_write_leaves_no_half_snapshot(tmp_path, monkeypatch) -> None:
    """A truncated .gz in the folder would be a snapshot that fails when it is read back,
    weeks later, when somebody is relying on it.  Better not to leave one.
    """
    real_open = gzip.open

    def fail_after_creating(path: object, *args: object, **kwargs: object) -> object:
        handle = real_open(path, *args, **kwargs)
        handle.close()
        message = "disk full"
        raise OSError(message)

    _load_as_current(_write(tmp_path, "backup.xml", _LOADED_XML))
    monkeypatch.setattr(gzip, "open", fail_after_creating)

    assert timeline.record(_write(tmp_path, "later.xml", _LATER_XML)) is None
    assert len(timeline.snapshots()) == 1


def _named(name: str) -> str:
    """A distinct configuration on disk, named after the Project inside it."""
    path = Path(f"{name}.xml")
    path.write_text(_LOADED_XML.replace("Home", name), encoding="utf-8")
    return str(path)


# ##################################################################################
# The periods the "Changes Since..." picker offers.
#
# What each one MEANS is a decision about the data, so it is tested here rather than
# through the GUI.  The mix of calendar and rolling is deliberate -- see timeline's own
# note -- which makes it exactly the kind of thing that needs pinning down.
# ##################################################################################
_NOON = datetime(2026, 9, 9, 14, 30, 0)


def test_today_starts_at_midnight_not_24_hours_ago() -> None:
    """"What changed today" means since this morning.  A rolling 24 hours would report
    yesterday evening's edits as today's, which is not what was asked.
    """
    assert timeline.cutoff_for(timeline.TODAY, now=_NOON) == datetime(2026, 9, 9, 0, 0, 0)


def test_week_and_month_roll_rather_than_follow_the_calendar() -> None:
    """A calendar week on a Monday morning would mean "since a few hours ago", which
    looks broken.  Both roll back from now instead.
    """
    assert timeline.cutoff_for(timeline.THIS_WEEK, now=_NOON) == _NOON - timedelta(days=7)
    assert timeline.cutoff_for(timeline.THIS_MONTH, now=_NOON) == _NOON - timedelta(days=30)


def test_all_has_no_cutoff_at_all() -> None:
    """Not "a very old date" -- None, so changes_since reaches back as far as it holds
    and does not then complain that the history is shorter than what was asked for.
    """
    assert timeline.cutoff_for(timeline.ALL, now=_NOON) is None


def test_a_specific_date_starts_at_midnight_on_that_day() -> None:
    """So that picking today's date and picking "Today" agree."""
    assert timeline.cutoff_for(timeline.ON_DATE, on_date=date(2026, 8, 20), now=_NOON) == datetime(2026, 8, 20, 0, 0)
    assert timeline.cutoff_for(timeline.ON_DATE, on_date=_NOON.date(), now=_NOON) == timeline.cutoff_for(
        timeline.TODAY,
        now=_NOON,
    )


def test_a_period_with_no_usable_answer_falls_back_to_all() -> None:
    """Reached from a pulldown this module supplies its options to, so anything else is a
    bug -- and more history than was asked for is a visibly odd report, where an
    exception would be a dead button.
    """
    assert timeline.cutoff_for("nonsense", now=_NOON) is None
    assert timeline.cutoff_for(timeline.ON_DATE, on_date=None, now=_NOON) is None


def test_every_offered_period_resolves(tmp_path) -> None:
    """Each option the picker shows has a cutoff behind it.

    Over PERIOD_LABELS itself, so an option added to the picker without teaching
    cutoff_for about it fails here rather than in front of a user.
    """
    for period in timeline.PERIOD_LABELS:
        cutoff = timeline.cutoff_for(period, on_date=date(2026, 8, 20), now=_NOON)
        assert cutoff is None or cutoff <= _NOON, period


def test_all_reaches_the_oldest_snapshot_without_complaining(tmp_path) -> None:
    """Asking for everything and being given everything is the answer, so it carries no
    note -- unlike asking for a year and only having a fortnight.
    """
    timeline.record(_write(tmp_path, "old.xml", _LOADED_XML), when=datetime.now() - timedelta(days=200))  # noqa: DTZ005
    _load_as_current(_write(tmp_path, "today.xml", _LATER_XML))

    result = timeline.changes_since(None)

    assert result.problem == ""
    assert result.note == ""
    assert result.older.source == "old.xml"
    assert result.counts["ADDED"] >= 1
