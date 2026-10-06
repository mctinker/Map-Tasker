"""bldargs: harvesting the arguments a backup uses but the action tables do not declare.

A development tool, run only by the build-all start-up.  What is worth holding is what it
must NOT do: change an action Tasker publishes (its table is authoritative), add an argument
twice, add one to an entry that merely redirects to another, or rewrite the overlay when there
was nothing to add -- since that file is hand-reviewed one action per line.

The real overlay is never touched: the file written to is a temporary copy of the same shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from maptasker.src import bldargs, console
from maptasker.src.actionc import action_codes

_BACKUP = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Profile sr="prof1">
    <State sr="con0" ve="2"><code>2</code><Int sr="arg0" val="1"/><Str sr="arg1" ve="3">x</Str><Bundle sr="arg2"/></State>
    <Event sr="con1" ve="2"><code>4</code><pri>0</pri><Str sr="arg0" ve="3"/><Int sr="arg1" val="3"/></Event>
  </Profile>
  <Task sr="task1">
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hi</Str><Int sr="arg99" val="1"/></Action>
    <Action sr="act1" ve="7"><code>548</code><Str sr="arg0" ve="3">again</Str><Str sr="arg99" ve="3">text</Str><Str sr="arg98" ve="3">t</Str></Action>
    <Action sr="act2" ve="7"><code>548</code><Int sr="arg99" val="2"/><Label sr="arg5"/><Str notanarg="1"/><Str sr="argx"/></Action>
    <Action sr="act3" ve="7"><code>  </code><Str sr="arg0">no code</Str></Action>
    <Action sr="act4" ve="7"><Str sr="arg0">no code at all</Str></Action>
  </Task>
</TaskerData>
"""


def _backup(tmp_path: Path, text: str = _BACKUP) -> str:
    path = tmp_path / "backup.xml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _overlay(tmp_path: Path, extra: dict | None = None) -> str:
    """An overlay of the shape the real one has, small enough to read."""
    overlay = {
        "_comment": ["A comment", "on two lines."],
        "eval": {"548t": {"0": ", Text="}, "20t": {"1": ", Data="}, "9t": {}},
        "extra": extra
        if extra is not None
        else {
            "2s": {
                "args": [["0", False, "", "0", ", Arg 0="]],
                "canfail": "",
                "category": "",
                "name": "Power",
                "redirect": "",
            },
            "4e": {"args": [], "canfail": "", "category": "", "name": "Phone Idle", "redirect": ""},
            "zzz_named": {"args": [], "canfail": "", "category": "", "name": "Named", "redirect": ""},
        },
    }
    path = tmp_path / "action_overlay.json"
    path.write_text(json.dumps(overlay), encoding="utf-8")
    return str(path)


@pytest.fixture
def said(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    lines: list[str] = []
    monkeypatch.setattr(console, "say", lines.append)
    monkeypatch.setattr(console, "error", lines.append)
    return lines


# ##################################################################################
# Reading the backup.
# ##################################################################################
def test_the_argument_slots_each_code_uses_are_collected_by_owner_kind(tmp_path: Path) -> None:
    harvested = bldargs.get_backup_arguments(_backup(tmp_path))

    assert harvested["2s"] == {"0": "Int", "1": "Str", "2": "Bundle"}  # A State's key ends in s.
    assert harvested["4e"] == {"0": "Str", "1": "Int"}  # An Event's in e.
    # An Action's key ends in t.  Every <... sr="argN"> counts as a slot, whatever its tag: what may be
    # added is decided later (see find_missing_arguments), so the Label shows up here and goes no further.
    assert harvested["548t"] == {"0": "Str", "99": "Int", "98": "Str", "5": "Label"}


def test_a_slot_written_with_two_tags_takes_the_one_seen_most(tmp_path: Path) -> None:
    # arg99 is Int twice and Str once.
    assert bldargs.get_backup_arguments(_backup(tmp_path))["548t"]["99"] == "Int"


def test_things_that_are_not_argument_slots_are_not_counted(tmp_path: Path) -> None:
    harvested = bldargs.get_backup_arguments(_backup(tmp_path))

    assert "x" not in harvested["548t"]  # "argx" is not a number.
    assert all(arg_id.isdigit() for slots in harvested.values() for arg_id in slots)


def test_an_owner_with_no_code_is_skipped(tmp_path: Path) -> None:
    harvested = bldargs.get_backup_arguments(_backup(tmp_path))

    assert set(harvested) == {"2s", "4e", "548t"}  # Neither a blank <code> nor a missing one makes a key.


def test_a_backup_that_is_not_xml_is_a_parse_error(tmp_path: Path) -> None:
    with pytest.raises(bldargs.ET.ParseError):
        bldargs.get_backup_arguments(_backup(tmp_path, "<TaskerData><Action>"))


# ##################################################################################
# Which of them are missing.
# ##################################################################################
def test_only_slots_the_tables_do_not_declare_are_missing() -> None:
    missing = bldargs.find_missing_arguments({"548t": {"0": "Str", "1": "Int", "99": "Int", "98": "Str"}})

    # Flash declares 0 and 1; 98 and 99 are new, and come out in numeric order.
    assert missing == {"548t": {"98": "1", "99": "0"}}
    assert list(missing["548t"]) == ["98", "99"]


def test_the_tag_decides_the_type_and_anything_else_is_not_harvested() -> None:
    missing = bldargs.find_missing_arguments({"548t": {"97": "Bundle", "98": "Str", "99": "Int", "96": "Label"}})

    assert missing == {"548t": {"98": "1", "99": "0"}}
    assert bldargs.HARVEST_TAGS == {"Str": "1", "Int": "0"}  # Bundle is never harvested: it would print twice.


def test_a_code_the_tables_do_not_know_is_ignored() -> None:
    assert bldargs.find_missing_arguments({"999999999t": {"0": "Str"}}) == {}


def test_a_code_with_nothing_missing_is_not_listed() -> None:
    declared = {arg.arg_id: "Str" for arg in action_codes["548t"].args}

    assert bldargs.find_missing_arguments({"548t": declared}) == {}


def test_a_redirecting_entry_has_its_arguments_added_to_what_it_redirects_to() -> None:
    redirecting = next(key for key, code in action_codes.items() if code.redirect)
    target = action_codes[redirecting].redirect

    missing = bldargs.find_missing_arguments({redirecting: {"98": "Str"}})

    assert missing == {target: {"98": "1"}}


def test_the_argument_is_wanted_once_however_many_entries_say_so() -> None:
    redirecting = [key for key, code in action_codes.items() if code.redirect and code.redirect == "1040876951t"]
    harvested = {key: {"98": "Str"} for key in redirecting[:2]}

    assert len(bldargs.find_missing_arguments(harvested)) == 1


# ##################################################################################
# What is written for each.
# ##################################################################################
def test_a_harvested_argument_is_a_generic_one_the_display_can_label() -> None:
    record = bldargs.harvested_argument("7", "1")

    assert record == ["7", False, "", "1", ", Arg 7="]
    assert record[4]  # arg_eval is the display prefix, and extract_string indexes its last character.


def test_the_overlay_is_written_one_code_per_line_numeric_first_named_last() -> None:
    overlay = {
        "_comment": ["one", "two"],
        "eval": {"20t": {"1": "a"}, "9t": {}},
        "extra": {"zzz": {"args": []}, "1000e": {"args": [["0", False, "", "0", "x"]]}, "2s": {"args": []}},
    }

    text = bldargs.format_overlay(overlay)

    assert json.loads(text) == overlay
    assert text.endswith("}\n")
    lines = text.splitlines()
    eval_keys = [
        line.split('"')[1]
        for line in lines
        if line.startswith("    ") and line.strip().startswith('"') and ('"9t"' in line or '"20t"' in line)
    ]
    assert eval_keys == ["9t", "20t"]  # Numeric order, not text order.
    extra_keys = [
        line.split('"')[1]
        for line in lines
        if line.startswith("    ") and any(token in line for token in ('"zzz"', '"1000e"', '"2s"'))
    ]
    assert extra_keys == ["2s", "1000e", "zzz"]
    # One line per code, however many arguments it has.
    assert sum('"1000e"' in line for line in lines) == 1


def test_the_real_overlay_survives_being_formatted_unchanged() -> None:
    """If this is not so, a harvest would rewrite the whole file and bury its one real change."""
    path = Path(bldargs.__file__).parent / bldargs.OVERLAY_FILENAME
    original = path.read_text(encoding="utf-8")

    assert bldargs.format_overlay(json.loads(original)) == original


# ##################################################################################
# Updating the overlay.
# ##################################################################################
def test_arguments_are_added_to_an_extra_entry_in_argument_order(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(tmp_path)

    added = bldargs.insert_arguments(overlay_file, {"2s": {"2": "1", "1": "0"}})

    assert added == 2
    written = json.loads(Path(overlay_file).read_text(encoding="utf-8"))
    assert [arg[0] for arg in written["extra"]["2s"]["args"]] == ["0", "1", "2"]
    assert written["extra"]["2s"]["args"][2] == ["2", False, "", "1", ", Arg 2="]
    # Everything else is as it was.
    assert written["extra"]["4e"]["args"] == []
    assert written["eval"] == {"548t": {"0": ", Text="}, "20t": {"1": ", Data="}, "9t": {}}


def test_a_published_action_is_reported_and_left_alone(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(tmp_path)
    before = Path(overlay_file).read_text(encoding="utf-8")

    added = bldargs.insert_arguments(overlay_file, {"548t": {"99": "0", "98": "1"}})

    assert added == 0
    assert Path(overlay_file).read_text(encoding="utf-8") == before  # Not even rewritten.
    assert len(said) == 1
    assert "548t is published in task_all_actions.json and was NOT changed" in said[0]
    assert "argument(s) 98, 99" in said[0]


def test_a_mixed_harvest_adds_what_it_may_and_reports_the_rest(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(tmp_path)

    added = bldargs.insert_arguments(overlay_file, {"2s": {"5": "1"}, "548t": {"99": "0"}})

    assert added == 1
    assert [arg[0] for arg in json.loads(Path(overlay_file).read_text(encoding="utf-8"))["extra"]["2s"]["args"]] == [
        "0",
        "5",
    ]
    assert any("548t" in line for line in said)


# ##################################################################################
# Doing it all.
# ##################################################################################
def test_a_harvest_adds_what_the_backup_uses_that_the_overlay_lacks(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(tmp_path)

    assert bldargs.build_arguments(_backup(tmp_path), overlay_file) == 0

    written = json.loads(Path(overlay_file).read_text(encoding="utf-8"))
    assert [arg[0] for arg in written["extra"]["2s"]["args"]] == ["0", "1"]  # arg2 is a Bundle: never harvested.
    assert [arg[0] for arg in written["extra"]["4e"]["args"]] == ["0", "1"]
    assert any("Added 3 argument(s)" in line for line in said)
    assert any("548t is published" in line for line in said)  # Reported, not changed.


def test_running_it_twice_adds_nothing_the_second_time(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(tmp_path)
    bldargs.build_arguments(_backup(tmp_path), overlay_file)
    after_first = Path(overlay_file).read_text(encoding="utf-8")
    said.clear()

    # In the same process: the tables are as they were loaded, so the same arguments look missing again.
    assert bldargs.build_arguments(_backup(tmp_path), overlay_file) == 0

    assert Path(overlay_file).read_text(encoding="utf-8") == after_first
    assert any("Added 0 argument(s)" in line for line in said)


def test_a_backup_that_uses_nothing_new_leaves_the_overlay_alone(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(tmp_path)
    before = Path(overlay_file).read_text(encoding="utf-8")
    flash_only = (
        '<TaskerData><Task sr="task1"><Action sr="act0" ve="7"><code>548</code>'
        '<Str sr="arg0" ve="3">hi</Str><Int sr="arg1" val="1"/></Action></Task></TaskerData>'
    )

    assert bldargs.build_arguments(_backup(tmp_path, flash_only), overlay_file) == 0

    assert Path(overlay_file).read_text(encoding="utf-8") == before  # Not even rewritten.
    assert any("No missing arguments" in line for line in said)


def test_arguments_an_entry_already_has_are_not_added_again(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(
        tmp_path,
        extra={"2s": {"args": [["0", False, "", "0", "x"], ["1", False, "", "1", "y"]], "name": "Power"}},
    )
    before = Path(overlay_file).read_text(encoding="utf-8")

    assert bldargs.insert_arguments(overlay_file, {"2s": {"0": "0", "1": "1"}}) == 0
    assert Path(overlay_file).read_text(encoding="utf-8") == before

    assert bldargs.insert_arguments(overlay_file, {"2s": {"1": "1", "2": "0"}}) == 1
    written = json.loads(Path(overlay_file).read_text(encoding="utf-8"))
    assert [arg[0] for arg in written["extra"]["2s"]["args"]] == ["0", "1", "2"]


def test_a_file_that_is_not_there_is_reported(tmp_path: Path, said: list[str]) -> None:
    assert bldargs.build_arguments(str(tmp_path / "nope.xml"), _overlay(tmp_path)) == 1
    assert bldargs.build_arguments(_backup(tmp_path), str(tmp_path / "nope.json")) == 1
    assert any("file not found" in line for line in said)


def test_a_backup_that_does_not_parse_is_reported(tmp_path: Path, said: list[str]) -> None:
    overlay_file = _overlay(tmp_path)
    before = Path(overlay_file).read_text(encoding="utf-8")

    assert bldargs.build_arguments(_backup(tmp_path, "<TaskerData><Action>"), overlay_file) == 2

    assert Path(overlay_file).read_text(encoding="utf-8") == before
    assert any("error parsing" in line for line in said)


def test_an_overlay_that_cannot_be_written_is_reported(
    tmp_path: Path, said: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: object) -> int:
        raise OSError("read-only")

    monkeypatch.setattr(bldargs, "insert_arguments", refuse)

    assert bldargs.build_arguments(_backup(tmp_path), _overlay(tmp_path)) == 3
    assert any("error updating" in line and "read-only" in line for line in said)


def test_the_default_overlay_is_the_real_one_and_the_default_backup_is_looked_for(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, said: list[str]
) -> None:
    seen = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bldargs.os.path, "isfile", lambda path: seen.setdefault(path, True) or True)
    monkeypatch.setattr(bldargs, "get_backup_arguments", lambda xml: {})

    assert bldargs.build_arguments() == 0

    paths = list(seen)
    assert any(path.endswith("backup.xml") for path in paths)
    assert any(path.endswith("action_overlay.json") for path in paths)
