"""The Compatibility Check (compat): the curated table, and what it finds in a configuration.

Two kinds of test.  The TABLE is data somebody typed from release notes, and a typo in it is silent: a code that is not
an action, a release that is not one, a row that says something different from readiness.json (which was built from the
same notes).  So every row is held to actionc and to the releases, and the rows both files have are held to each other.

The CHECK is tested on a small configuration with one of each shape the rules care about: an item newer than a target,
a Profile's Event and State, a Scene's own action, a behaviour change in each direction, and the Android a thing needs.
What is checked most is what is NOT reported: a version no different from the file's, a change nothing in the file uses,
a rename when the target is older (the older Tasker still has the old name).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator

import pytest
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import PROFILE, SCENE, TASK, text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import compat
from maptasker.src.mapops.readiness import READINESS_FILE, version_key

from tests.test_maprefac import _load

KINDS = {"action": "t", "event": "e", "state": "s"}


# ##################################################################################
# The table.
# ##################################################################################


def test_every_item_with_a_key_is_an_action_event_or_state_maptasker_knows_by_that_name() -> None:
    for item in compat.items():
        if not item.key:
            continue
        assert item.key.endswith(KINDS[item.kind]), item
        assert item.key in action_codes, item
        assert action_codes[item.key].name == item.name, item


def test_every_key_a_change_names_is_known() -> None:
    for change in compat.changes():
        for key in change.keys:
            assert key in action_codes, change
        assert len(change.keys) <= len(change.named), "a key without a name to show for it"


def test_every_release_an_item_or_change_names_is_one_the_table_lists() -> None:
    known = {release.version for release in compat.releases()}

    assert {item.since for item in compat.items()} <= known
    assert {change.release for change in compat.changes()} <= known
    assert {release for release, _api in compat.target_api_bumps()} <= known


def test_releases_are_listed_oldest_first_with_none_twice() -> None:
    versions = [release.version for release in compat.releases()]

    assert versions == sorted(versions, key=version_key)
    assert len(set(versions)) == len(versions)


def test_no_action_is_in_the_table_twice() -> None:
    keys = [item.key for item in compat.items() if item.key]

    assert len(keys) == len(set(keys))


def test_the_kinds_and_android_levels_are_ones_the_window_can_say() -> None:
    assert {item.kind for item in compat.items()} <= set(KINDS)
    assert {change.kind for change in compat.changes()} <= {"removed", "renamed", "changed"}
    assert {item.android for item in compat.items()} - {0} <= set(compat.ANDROID_NAMES)
    assert {api for _release, api in compat.target_api_bumps()} <= set(compat.ANDROID_NAMES)


def test_the_table_agrees_with_readiness_json_about_when_each_thing_came_in() -> None:
    """readiness.json was built from the same release notes by hand; two readings of one page must say one thing."""
    with open(READINESS_FILE, encoding="utf-8") as file:
        readiness = json.load(file)["items"]
    ours = {item.key: item.since for item in compat.items() if item.key}

    for key, row in readiness.items():
        if "since" in row:
            assert ours.get(key) == row["since"], key


def test_the_table_file_is_where_the_code_looks_for_it() -> None:
    assert os.path.isfile(compat.TABLE_FILE)


def test_scenes_v2_came_in_with_6_7_1_and_6_7_1_is_a_release_the_window_offers() -> None:
    scene_v2 = [item for item in compat.items() if "Scene v2" in item.name or item.name == "Scene V2 Event"]

    assert len(scene_v2) >= 9
    assert {item.since for item in scene_v2} == {"6.7.1"}
    assert "6.7.1" in {release.version for release in compat.releases()}


def test_an_android_level_is_called_by_its_version() -> None:
    assert compat.android_name(33) == "Android 13"
    assert compat.android_name(99) == "Android API 99"


# ##################################################################################
# The check.
# ##################################################################################


def _key(kind: str, name: str) -> str:
    """The key of a table item, by what it is called."""
    return next(item.key for item in compat.items() if item.kind == kind and item.name == name and item.key)


def _code(key: str) -> str:
    return key[:-1]


def _action(code: str, number: int) -> str:
    return f'<Action sr="act{number}" ve="7"><code>{code}</code></Action>'


def _configuration(tv: str) -> str:
    """A configuration using one of each shape: see the module docstring."""
    java = _code(_key("action", "Java Code"))  # new in 6.6.18
    effects = _code(_key("action", "Set Device Effects"))  # new in 6.3.12, needs Android 15
    test_net = _code(next(key for key in _change_keys("Test Net")))  # changed in 6.2.18
    tether = (
        _code(_key("action", "WiFi Tether (Hotspot)")) if False else _code(_change_keys("WiFi Tether (Hotspot)")[0])
    )
    app_changed = _code(_key("event", "App Changed"))  # new in 5.8
    dark_mode = _code(_key("state", "Dark Mode"))  # new in 5.8.5, needs Android 8
    scene_task = _code(_key("action", "Get Battery Info"))  # new in 6.0.9, used inside a Scene
    return (
        f'<TaskerData sr="" dvi="1" tv="{tv}">'
        '<Project sr="proj0" ve="2"><name>Home</name><pids>100</pids><tids>10,11</tids><scenes>Panel</scenes></Project>'
        f'<Profile sr="prof100" ve="2"><id>100</id><nme>Dawn</nme><mid0>10</mid0>'
        f'<Event sr="con0" ve="2"><code>{app_changed}</code></Event>'
        f'<State sr="con1" ve="2"><code>{dark_mode}</code></State></Profile>'
        f'<Task sr="task10" ve="2"><id>10</id><nme>Morning</nme>{_action(java, 0)}{_action(effects, 1)}</Task>'
        f'<Task sr="task11" ve="2"><id>11</id><nme>Evening</nme>{_action(test_net, 0)}{_action(tether, 1)}</Task>'
        f'<Scene sr="scenePanel"><nme>Panel</nme><Task sr="task0"><Action sr="act0" ve="7"><code>{scene_task}</code></Action></Task></Scene>'
        "</TaskerData>"
    )


def _change_keys(name: str) -> list[str]:
    return [
        key
        for change in compat.changes()
        for key, named in zip(change.keys, change.named, strict=False)
        if named == name
    ]


@pytest.fixture
def loaded() -> Iterator[None]:
    sessundo.clear(PrimeItems)
    _load(_configuration("6.3.13"))
    yield
    sessundo.clear(PrimeItems)


def _tags(result: compat.Compatibility, tag: str) -> list[compat.Finding]:
    return [finding for finding in result.findings if finding.tag == tag]


def test_what_is_newer_than_the_target_is_found_with_where_it_is(loaded: None) -> None:
    result = compat.check(PrimeItems, "6.0.9")

    newer = {finding.text: finding for finding in _tags(result, compat.NEWER_TASKER)}
    assert "Action Java Code is new in Tasker 6.6.18." in newer
    assert "Action Set Device Effects is new in Tasker 6.3.12." in newer
    java = newer["Action Java Code is new in Tasker 6.6.18."]
    assert [(place.kind, place.key, place.action) for place in java.places] == [(TASK, "10", 1)]


def test_nothing_is_newer_when_the_target_has_it_all(loaded: None) -> None:
    assert _tags(compat.check(PrimeItems, "6.7.8"), compat.NEWER_TASKER) == []


def test_the_newest_thing_used_says_how_new_a_tasker_the_file_needs(loaded: None) -> None:
    result = compat.check(PrimeItems, "6.7.8")

    assert result.minimum == "6.6.18"
    assert result.minimum_names == ("Action Java Code",)
    assert result.items_used >= 5


def test_a_profiles_event_and_state_and_a_scenes_own_action_are_found_too(loaded: None) -> None:
    result = compat.check(PrimeItems, "5.0")
    places = {(place.kind, place.key) for finding in _tags(result, compat.NEWER_TASKER) for place in finding.places}

    assert (PROFILE, "100") in places
    assert (SCENE, "Panel") in places


def test_findings_come_newest_release_first(loaded: None) -> None:
    releases = [finding.release for finding in _tags(compat.check(PrimeItems, "5.0"), compat.NEWER_TASKER)]

    assert releases == sorted(releases, key=version_key, reverse=True)


def test_an_android_too_old_for_something_is_named_with_where(loaded: None) -> None:
    result = compat.check(PrimeItems, "6.7.8", target_android=33)

    (finding,) = _tags(result, compat.NEWER_ANDROID)
    assert finding.text == "Action Set Device Effects needs Android 15 or later."
    assert [place.key for place in finding.places] == ["10"]


def test_no_android_asked_means_none_is_checked(loaded: None) -> None:
    assert _tags(compat.check(PrimeItems, "6.7.8", target_android=0), compat.NEWER_ANDROID) == []


def test_a_tasker_that_needs_a_newer_android_than_the_target_is_said(loaded: None) -> None:
    texts = [
        finding.text for finding in _tags(compat.check(PrimeItems, "6.6.18", target_android=26), compat.NEWER_ANDROID)
    ]

    assert "Tasker 6.6.18 needs Android 8.1 or later." in texts


def test_a_change_since_the_file_was_written_is_reported_where_the_file_uses_it(loaded: None) -> None:
    result = compat.check(PrimeItems, "6.7.8")  # written by 6.3.13

    texts = [finding.text for finding in _tags(result, compat.CHANGED)]
    assert not any("Local Network IP" in text for text in texts), "6.2.18 is before the file was written"


def test_a_change_after_the_file_was_written_is_reported() -> None:
    sessundo.clear(PrimeItems)
    _load(_configuration("6.0.9"))

    result = compat.check(PrimeItems, "6.7.8")

    changed = [finding for finding in result.findings if "Local Network IP" in finding.text]
    assert changed
    assert changed[0].tag == compat.CHANGED
    assert [place.key for place in changed[0].places] == ["11"]


def test_a_rename_is_reported_going_up_and_not_going_down() -> None:
    sessundo.clear(PrimeItems)
    _load(_configuration("6.0.9"))

    up = [finding for finding in compat.check(PrimeItems, "6.7.8").findings if "WiFi Tether" in finding.text]
    sessundo.clear(PrimeItems)
    _load(_configuration("6.7.8"))
    down = [finding for finding in compat.check(PrimeItems, "6.0.9").findings if "WiFi Tether" in finding.text]

    assert up
    assert up[0].tag == compat.REMOVED
    assert down == [], "an older Tasker still has the old name"


def test_going_down_a_behaviour_change_is_reported_as_what_the_file_may_rely_on() -> None:
    sessundo.clear(PrimeItems)
    _load(_configuration("6.7.8"))

    changed = [finding for finding in compat.check(PrimeItems, "6.0.9").findings if "Local Network IP" in finding.text]

    assert changed
    assert changed[0].text.startswith("Written for the newer behaviour: ")


def test_the_same_version_as_the_file_has_no_changes_between(loaded: None) -> None:
    result = compat.check(PrimeItems, "6.3.13")

    assert [
        finding for finding in result.findings if finding.tag in {compat.CHANGED, compat.REMOVED, compat.GENERAL}
    ] == []


def test_a_target_api_bump_is_said_once_for_everything_and_is_not_a_finding(loaded: None) -> None:
    result = compat.check(PrimeItems, "6.7.8")
    general = result.notes

    assert _tags(result, compat.GENERAL) == [], "what is true of everything is not something the file did"
    assert any("targets Android 15" in finding.text for finding in general)
    assert all(finding.places == () for finding in general if "targets" in finding.text)


def test_a_file_that_does_not_say_who_wrote_it_gets_the_items_and_no_changes() -> None:
    sessundo.clear(PrimeItems)
    _load(_configuration("").replace(' tv=""', ""))

    result = compat.check(PrimeItems, "6.0.9")

    assert result.written_by == ""
    assert _tags(result, compat.NEWER_TASKER)
    assert [
        finding for finding in result.findings if finding.tag in {compat.CHANGED, compat.REMOVED, compat.GENERAL}
    ] == []


def test_a_beta_is_read_as_the_release_it_leads_to() -> None:
    sessundo.clear(PrimeItems)
    _load(_configuration("6.7.6-beta"))

    assert compat.written_by(PrimeItems) == "6.7.6-beta"
    assert version_key("6.7.6-beta") == (6, 7, 6)


def test_a_configuration_that_uses_nothing_in_the_table_is_clean() -> None:
    sessundo.clear(PrimeItems)
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13"><Task sr="task1" ve="2"><id>1</id><nme>Plain</nme></Task></TaskerData>'
    )

    result = compat.check(PrimeItems, "5.0")

    assert result.is_clean
    assert "Nothing in this file is known to break on that version." in text_report(compat.report_rows(result))


def test_nothing_loaded_is_nothing_found() -> None:
    sessundo.clear(PrimeItems)
    PrimeItems.xml_root = None  # type: ignore[assignment]

    result = compat.check(PrimeItems, "6.0.9")

    assert result.is_clean
    assert compat.written_by(PrimeItems) == ""


# ##################################################################################
# Saying it.
# ##################################################################################


def test_the_report_names_the_file_the_version_and_each_finding_with_its_places(loaded: None) -> None:
    rows = compat.report_rows(compat.check(PrimeItems, "6.0.9", 33))
    text = text_report(rows)

    assert "Written by Tasker 6.3.13" in text
    assert "It uses " in text and " actions, events and states the table can find." in text
    assert "Checked against Tasker 6.0.9, Android 13" in text
    assert "NEWER-TASKER  [6.6.18] Action Java Code is new in Tasker 6.6.18." in text
    assert any(row.target is not None and row.target.key == "10" for row in rows)


def test_a_long_list_of_places_is_cut_and_counted(loaded: None) -> None:
    places = tuple(compat.task_target(str(number), state=PrimeItems) for number in range(10, 18))

    rows = compat._places_row(places)

    assert len(rows) == compat.PLACES_SHOWN + 1
    assert rows[-1].text == f"      ... and {8 - compat.PLACES_SHOWN} more"


def test_the_reference_table_is_newest_first_and_counts_what_the_file_uses(loaded: None) -> None:
    rows = compat.table(PrimeItems)

    assert [version_key(row.release) for row in rows] == sorted(
        (version_key(row.release) for row in rows), reverse=True
    )
    java = next(row for row in rows if row.name == "Action Java Code")
    assert (java.what, java.release, java.used) == ("New", "6.6.18", 1)


def test_a_row_with_no_code_cannot_be_counted_and_without_a_file_nothing_can(loaded: None) -> None:
    no_code = next(row for row in compat.table(PrimeItems) if row.name == "Action Google Drive List")
    assert no_code.used is None

    sessundo.clear(PrimeItems)
    PrimeItems.xml_root = None  # type: ignore[assignment]
    assert all(row.used is None for row in compat.table(PrimeItems))


def test_the_report_is_saved_where_the_others_are(
    loaded: None, tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(compat, "output_path", lambda name, state: os.path.join(str(tmp_path), name))

    path = compat.write_report(compat.report_rows(compat.check(PrimeItems, "6.0.9")), state=PrimeItems)

    assert os.path.basename(path).startswith("MapTasker_Compatibility_")
    with open(path, encoding="utf-8") as saved:
        assert saved.read().startswith("COMPATIBILITY CHECK")


def test_a_report_that_cannot_be_written_says_so_with_an_empty_path(
    loaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(compat, "output_path", lambda name, state: os.path.join("/nonexistent-folder", name))

    assert compat.write_report([], state=PrimeItems) == ""
