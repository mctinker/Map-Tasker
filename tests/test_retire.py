"""Plugin Retirement Advisor (retire.py) Unit Tests -- which plugins the file uses that Tasker now does itself

The advisor is plugchk's list of the plugins a configuration uses, set against a short table of the plugins Tasker has
taken over from, with each built-in's name and version read from compat.json.  Each behaviour is tested with the thing
that earns a line and the look-alike that does not: a plugin the table has no built-in for, a built-in the file uses
without the plugin, a Tasker too old to have what replaces the plugin.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import compat, retire

from tests.shared_fixtures import _load_local

_BLURB = "com.twofortyfouram.locale.intent.extra.BLURB"
SHORTCUT = "com.joaomgcd.autoshortcut"
ALARM = "com.joaomgcd.autoalarm"
JOIN = "com.joaomgcd.join"
INPUT = "com.joaomgcd.autoinput"


def _plugin(package: str, number: int = 0) -> str:
    return (
        f'<Action sr="act{number}" ve="7"><code>1040876951</code>'
        f'<Bundle sr="arg0"><Vals sr="val"><{_BLURB}>b</{_BLURB}></Vals></Bundle>'
        f'<Str sr="arg1">{package}</Str><Str sr="arg2">com.example.Edit</Str></Action>'
    )


def _xml(tasker: str = "6.7.8") -> str:
    """AutoShortcut once, Join three times (two Tasks), AutoInput that has no built-in, and an AutoAlarm Profile condition."""
    version = f' tv="{tasker}"' if tasker else ""
    return f"""<TaskerData sr="" dvi="1"{version}>
  <Project sr="proj0" ve="2"><name>Home</name><pids>100</pids><tids>10,11</tids></Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Alarmed</nme><mid0>10</mid0>
    <Event sr="con0" ve="2"><code>1040876951</code>
      <Bundle sr="arg0"><Vals sr="val"><{_BLURB}>b</{_BLURB}></Vals></Bundle>
      <Str sr="arg1">{ALARM}</Str><Str sr="arg2">com.example.Edit</Str></Event>
  </Profile>
  <Task sr="task10" ve="2"><id>10</id><nme>Morning</nme>{_plugin(SHORTCUT, 0)}{_plugin(JOIN, 1)}{_plugin(INPUT, 2)}</Task>
  <Task sr="task11" ve="2"><id>11</id><nme>Evening</nme>{_plugin(JOIN, 0)}{_plugin(JOIN, 1)}</Task>
</TaskerData>"""


@pytest.fixture(autouse=True)
def _configuration(_runtime: None, tmp_path: Path) -> None:
    """Load the backup under test over the runtime's own, which is why this names it: it must load first."""
    _load_local(tmp_path, _xml())
    sessundo.clear(PrimeItems)


def _reload(tmp_path: Path, tasker: str) -> None:
    _load_local(tmp_path, _xml(tasker))


def _advice(result: retire.Retirement) -> dict[str, retire.Advice]:
    return {each.entry.package: each for each in result.advice}


# ==========================================
# The data
# ==========================================
def test_every_built_in_the_table_names_is_in_the_compatibility_table() -> None:
    """The name and the version come from compat.json, so a key it lacks would be a plugin with nothing to say."""
    for entry in retire.entries():
        assert entry.replacements, entry.plugin
        for each in entry.replacements:
            assert any(item.key == each.key for item in compat.items()), (entry.plugin, each.key)


def test_every_built_in_is_one_maptasker_knows_by_a_name() -> None:
    """A key compat.json holds with no name in actionc would be a built-in the user could not look for in a Task."""
    for entry in retire.entries():
        for each in entry.replacements:
            assert action_codes.get(each.key) is not None, (entry.plugin, each.key)


def test_every_package_looks_like_one_and_none_is_listed_twice() -> None:
    packages = [entry.package for entry in retire.entries()]

    assert len(set(packages)) == len(packages)
    assert all(re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", package) for package in packages)


def test_every_entry_says_how_much_is_covered_and_where_that_was_said() -> None:
    for entry in retire.entries():
        assert entry.coverage in {retire.REPLACES, retire.OVERLAPS}, entry.plugin
        assert entry.source.startswith("https://"), entry.plugin
        assert entry.note.endswith("."), entry.plugin


def test_the_built_in_is_read_from_compat_not_written_twice() -> None:
    """Shortcut is 5.9.0 in compat.json; the plugin table must not hold a version of its own."""
    data = json.loads(Path(retire.TABLE_FILE).read_text(encoding="utf-8"))

    assert all(set(row) == {"package", "plugin", "coverage", "builtins", "note", "source"} for row in data["plugins"])
    (shortcut,) = (entry for entry in retire.entries() if entry.package == SHORTCUT)
    assert [(each.label, each.since) for each in shortcut.replacements] == [("Action Shortcut", "5.9.0")]


def test_the_version_that_has_every_built_in_is_the_newest_of_them() -> None:
    (alarm,) = (entry for entry in retire.entries() if entry.package == ALARM)

    assert {each.since for each in alarm.replacements} == {"5.9.0", "5.9.1"}
    assert alarm.needs == "5.9.1"


# ==========================================
# What the file uses
# ==========================================
def test_a_plugin_with_a_built_in_is_found_and_one_without_is_not() -> None:
    result = retire.advise(PrimeItems)

    assert set(_advice(result)) == {SHORTCUT, ALARM, JOIN}
    assert result.plugins_used == 4, "AutoInput is used, and has no built-in"
    assert result.known == len(retire.entries())


def test_the_places_a_plugin_is_used_are_all_listed_with_what_each_does() -> None:
    join = _advice(retire.advise(PrimeItems))[JOIN]

    assert len(join.uses) == 3
    assert {use.where.key for use in join.uses} == {"10", "11"}


def test_a_plugin_used_in_a_profile_condition_counts() -> None:
    (use,) = _advice(retire.advise(PrimeItems))[ALARM].uses

    assert use.where.key == "100"


def test_those_fully_replaced_come_before_those_only_partly_replaced() -> None:
    order = [each.entry.coverage for each in retire.advise(PrimeItems).advice]

    assert order == sorted(order, key=lambda coverage: coverage != retire.REPLACES)
    assert order[-1] == retire.OVERLAPS
    assert retire.advise(PrimeItems).advice[-1].entry.package == JOIN


def test_nothing_loaded_is_nothing_found() -> None:
    PrimeItems.xml_root = None  # type: ignore[assignment]

    result = retire.advise(PrimeItems)

    assert result.advice == []
    assert result.plugins_used == 0
    assert result.is_clean


def test_a_file_that_uses_only_plugins_with_no_built_in_is_clean(tmp_path: Path) -> None:
    only_input = _xml().replace(SHORTCUT, INPUT).replace(JOIN, INPUT).replace(ALARM, INPUT)
    _load_local(tmp_path, only_input)

    result = retire.advise(PrimeItems)

    assert result.is_clean
    assert result.plugins_used == 1


# ==========================================
# Does the Tasker that wrote the file have it
# ==========================================
def test_a_tasker_that_has_the_built_in_is_ready() -> None:
    assert {each.ready for each in retire.advise(PrimeItems).advice} == {True}


def test_a_tasker_older_than_the_built_in_is_not(tmp_path: Path) -> None:
    _reload(tmp_path, "5.8")

    advice = _advice(retire.advise(PrimeItems))

    assert advice[SHORTCUT].ready is False
    assert advice[JOIN].ready is False


def test_the_version_decides_per_plugin_not_for_all_of_them(tmp_path: Path) -> None:
    """5.9.0 has Shortcut but not Alarm Changed, which is 5.9.1; 6.4 is where Remote Action Execution comes in."""
    _reload(tmp_path, "5.9.0")

    advice = _advice(retire.advise(PrimeItems))

    assert advice[SHORTCUT].ready is True
    assert advice[ALARM].ready is False
    assert advice[JOIN].ready is False


def test_a_file_that_does_not_say_which_tasker_wrote_it_is_neither_ready_nor_not(tmp_path: Path) -> None:
    _reload(tmp_path, "")

    result = retire.advise(PrimeItems)

    assert result.written_by == ""
    assert {each.ready for each in result.advice} == {None}


# ==========================================
# The report
# ==========================================
def _text(result: retire.Retirement) -> str:
    return text_report(retire.report_rows(result))


def _flat(text: str) -> str:
    """The text with each run of spaces and line breaks as one space: a sentence is broken to fit, and read whole."""
    return " ".join(text.split())


def test_the_report_names_the_built_in_and_since_when() -> None:
    text = _text(retire.advise(PrimeItems))

    assert "REPLACED  AutoShortcut (com.joaomgcd.autoshortcut)" in text
    assert "Tasker's Action Shortcut, since Tasker 5.9.0" in text
    assert "Tasker's Action Remote Action Execution, since Tasker 6.4.1 (a beta; released in 6.4.13)" in text
    assert "Used in 3 places:" in text
    assert "Used in 1 place:" in text


def test_a_partly_replaced_plugin_is_tagged_as_that() -> None:
    text = _text(retire.advise(PrimeItems))

    assert "  PARTLY-REPLACED  Join (com.joaomgcd.join)" in text
    assert "  REPLACED  AutoAlarm (com.joaomgcd.autoalarm)" in text


def test_the_report_says_whether_the_backups_tasker_has_it(tmp_path: Path) -> None:
    assert "The backup was written by Tasker 6.7.8, which already has it." in _flat(_text(retire.advise(PrimeItems)))

    _reload(tmp_path, "5.8")
    assert "which does not have it yet." in _flat(_text(retire.advise(PrimeItems)))

    _reload(tmp_path, "")
    assert "The file does not say which Tasker wrote it." in _flat(_text(retire.advise(PrimeItems)))


def test_no_line_of_the_report_is_wider_than_a_window_shows() -> None:
    """The long notes are broken into lines; the window does not wrap, so a long line would be cut off."""
    widest = max(len(row.text) for row in retire.report_rows(retire.advise(PrimeItems)) if row.target is None)

    assert widest <= 110, widest


def test_the_whole_note_is_still_in_the_report_when_it_is_broken_into_lines() -> None:
    (join,) = (entry for entry in retire.entries() if entry.package == JOIN)

    assert join.note in _flat(_text(retire.advise(PrimeItems)))


def test_the_report_says_what_the_file_uses_the_plugin_for() -> None:
    assert "The file uses it for: " in _text(retire.advise(PrimeItems))


def test_each_place_in_the_report_is_a_click_into_the_map() -> None:
    places = [row for row in retire.report_rows(retire.advise(PrimeItems)) if row.target is not None]

    assert len(places) == 1 + 1 + 3
    assert {row.target.key for row in places if row.target is not None} == {"10", "11", "100"}


def test_every_place_is_listed_however_many_there_are(tmp_path: Path) -> None:
    """Not the first few and 'and N more': each is a click into the Map, and the ones left out could not be reached."""
    many = "".join(_plugin(JOIN, number) for number in range(25))
    _load_local(
        tmp_path,
        f'<TaskerData sr="" dvi="1" tv="6.7.8"><Task sr="task10" ve="2"><id>10</id><nme>Busy</nme>{many}</Task></TaskerData>',
    )

    rows = retire.report_rows(retire.advise(PrimeItems))

    assert sum(1 for row in rows if row.target is not None) == 25
    assert "... and" not in _text(retire.advise(PrimeItems))
    assert "Used in 25 places:" in _text(retire.advise(PrimeItems))


def test_a_clean_file_says_so_and_says_the_list_is_short() -> None:
    PrimeItems.xml_root = None  # type: ignore[assignment]

    text = text_report(retire.report_rows(retire.advise(PrimeItems), loaded=True))

    assert "None of them has a built-in in Tasker that is known to do its job." in text
    assert "The table is short on purpose" in text


def test_with_no_file_the_report_says_to_get_one() -> None:
    text = text_report(retire.report_rows(retire.advise(PrimeItems), loaded=False))

    assert "No XML file has been loaded." in text


def test_the_report_is_written_to_the_output_folder() -> None:
    rows = retire.report_rows(retire.advise(PrimeItems))

    path = retire.write_report(rows, PrimeItems)

    assert path
    assert "PLUGIN RETIREMENT ADVISOR" in Path(path).read_text(encoding="utf-8")


# ==========================================
# The reference table
# ==========================================
def test_the_table_lists_every_plugin_with_how_much_of_the_file_uses_it() -> None:
    rows = {row.plugin: row for row in retire.table(PrimeItems)}

    assert set(rows) == {entry.plugin for entry in retire.entries()}
    assert rows["Join"].used == 3
    assert rows["AutoShortcut"].used == 1
    assert rows["Join"].covers == "Partly replaced"
    assert rows["AutoShortcut"].covers == "Replaced"
    assert rows["AutoAlarm"].since == "5.9.1"


def test_the_table_with_no_file_loaded_has_no_counts() -> None:
    PrimeItems.xml_root = None  # type: ignore[assignment]

    assert {row.used for row in retire.table(PrimeItems)} == {None}
