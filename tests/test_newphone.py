"""New-phone checklist (newphone.py) Unit Tests -- what is left to set up after restoring a backup

The checklist is readiness.py's answer for the whole backup, mapvars' globals and the Profiles that are switched on,
arranged as one list, crossed with the app list fetched from the new phone, and remembered tick by tick.  Each group
is tested with the thing that earns an entry and the look-alike that does not: a Profile that is off, a variable that
holds nothing, an app chosen by variable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from maptasker.src.core import appinv
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import newphone, readiness

from tests.shared_fixtures import _load_local

_BLURB = "com.twofortyfouram.locale.intent.extra.BLURB"
ADB = "adb shell pm grant net.dinglisch.android.taskerm android.permission.WRITE_SECURE_SETTINGS"
PHONE = "192.168.0.59:1821"
OTHER = "192.168.0.60:1821"


def _plugin(package: str) -> str:
    return (
        '<Action sr="act0" ve="7"><code>1040876951</code>'
        f'<Bundle sr="arg0"><Vals sr="val"><{_BLURB}>b</{_BLURB}></Vals></Bundle>'
        f'<Str sr="arg1">{package}</Str><Str sr="arg2">com.example.Edit</Str></Action>'
    )


def _launch(package: str, label: str) -> str:
    return (
        '<Action sr="act1" ve="7"><code>20</code>'
        f'<App sr="arg0"><appClass>c</appClass><appPkg>{package}</appPkg><label>{label}</label></App></Action>'
    )


def _needs_access() -> str:
    return '<Action sr="act2" ve="7"><code>245</code></Action>'


XML = f"""<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="vars0"><n>%Home</n><v>Berlin</v></Variable>
  <Variable sr="vars1"><n>%Key</n><v>s3cret</v></Variable>
  <Variable sr="vars2"><n>%Blank</n><v></v></Variable>
  <Project sr="proj0" ve="2"><name>Home</name><pids>100,101</pids><tids>10</tids></Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Dawn</nme><mid0>10</mid0></Profile>
  <Profile sr="prof101" ve="2"><id>101</id><nme>Sleeping</nme><limit>true</limit><mid0>10</mid0></Profile>
  <Task sr="task10" ve="2"><id>10</id><nme>Morning</nme>{_plugin("com.joaomgcd.autoinput")}{_launch("com.example.music", "Music")}{_launch("%app", "")}{_needs_access()}</Task>
</TaskerData>"""


@pytest.fixture(autouse=True)
def _configuration(_runtime: None, tmp_path: Path) -> None:
    """Load the backup under test over the runtime's own, which is why this names it: it must load first."""
    _load_local(tmp_path, XML)
    sessundo.clear(PrimeItems)


def _store(device: str, *packages: str) -> None:
    appinv.store_fetched_apps(device, [appinv.AppEntry(pkg=package, label="", cls="") for package in packages])


def _group(checklist: newphone.Checklist, kind: str) -> dict[str, newphone.Item]:
    return {item.key: item for group in checklist.groups if group.kind == kind for item in group.items}


# ==========================================
# The groups
# ==========================================
def test_the_groups_come_in_the_order_a_phone_is_set_up() -> None:
    assert [group.kind for group in newphone.build(PrimeItems).groups] == list(newphone.KINDS)


def test_nothing_loaded_is_an_empty_checklist() -> None:
    PrimeItems.xml_root = None  # type: ignore[assignment]

    assert newphone.build(PrimeItems).groups == []


def test_a_plugin_and_an_app_are_listed_and_an_app_chosen_by_variable_is_not() -> None:
    checklist = newphone.build(PrimeItems)

    assert list(_group(checklist, newphone.PLUGINS)) == ["plugin:com.joaomgcd.autoinput"]
    assert list(_group(checklist, newphone.APPS)) == ["app:com.example.music"]
    assert "Music" in _group(checklist, newphone.APPS)["app:com.example.music"].text


def test_special_access_carries_the_commands_that_grant_it() -> None:
    (item,) = _group(newphone.build(PrimeItems), newphone.ACCESS).values()

    assert item.commands == (ADB,)
    assert "any one of them" in item.text
    assert "Accessibility" in item.text


def test_only_a_variable_that_holds_a_value_is_one_to_enter() -> None:
    variables = _group(newphone.build(PrimeItems), newphone.VARIABLES)

    assert {key: item.value for key, item in variables.items()} == {
        "variable:%Home": "Berlin",
        "variable:%Key": "s3cret",
    }


def test_only_a_profile_that_is_switched_on_is_one_to_enable() -> None:
    profiles = _group(newphone.build(PrimeItems), newphone.PROFILES)

    assert list(profiles) == ["profile:Dawn"]
    assert "Home" in profiles["profile:Dawn"].detail
    target = profiles["profile:Dawn"].target
    assert target is not None
    assert target.name == "Dawn"


# ==========================================
# Plugins and apps against the phone
# ==========================================
def test_what_the_phone_lacks_is_flagged_and_what_it_has_is_not() -> None:
    _store(PHONE, "com.joaomgcd.autoinput")

    checklist = newphone.build(PrimeItems, PHONE)

    assert _group(checklist, newphone.PLUGINS)["plugin:com.joaomgcd.autoinput"].status == newphone.HAVE
    assert _group(checklist, newphone.APPS)["app:com.example.music"].status == newphone.MISSING
    assert checklist.missing() == 1
    assert checklist.device == PHONE


def test_with_no_phone_picked_nothing_is_flagged() -> None:
    _store(PHONE, "com.joaomgcd.autoinput")

    checklist = newphone.build(PrimeItems)

    assert {item.status for item in checklist.items()} == {newphone.UNKNOWN}
    assert checklist.device == ""


def test_a_phone_that_is_not_in_the_cache_flags_nothing() -> None:
    checklist = newphone.build(PrimeItems, "10.0.0.1:1821")

    assert checklist.missing() == 0
    assert checklist.device == ""


def test_the_phone_picked_decides_not_every_phone_fetched() -> None:
    """Unlike plugchk, which accepts a package found on any list: this checks THE new phone."""
    _store(PHONE, "com.example.music")
    _store(OTHER, "com.joaomgcd.autoinput")

    assert _group(newphone.build(PrimeItems, PHONE), newphone.PLUGINS)["plugin:com.joaomgcd.autoinput"].status == (
        newphone.MISSING
    )
    assert _group(newphone.build(PrimeItems, OTHER), newphone.APPS)["app:com.example.music"].status == newphone.MISSING


def test_the_phone_fetched_last_is_the_one_to_start_with() -> None:
    assert newphone.default_device() == ""
    _store(PHONE, "a.b")
    appinv.forget_device(PHONE)
    _store(OTHER, "a.b")

    assert newphone.devices() == [OTHER]
    assert newphone.default_device() == OTHER


# ==========================================
# The ticks
# ==========================================
def test_ticks_are_remembered_across_a_save_and_a_load(tmp_path: Path) -> None:
    where = str(tmp_path / "ticks.json")
    book = newphone.TickBook(keys={"profile:Dawn", "plugin:com.joaomgcd.autoinput"})

    assert newphone.save_ticks(book, where) == ""

    assert newphone.load_ticks(where).keys == book.keys


def test_no_ticks_file_is_no_ticks(tmp_path: Path) -> None:
    book = newphone.load_ticks(str(tmp_path / "none.json"))

    assert book.keys == set()
    assert book.unreadable == ""


def test_a_damaged_ticks_file_is_kept_aside_before_it_is_written_over(tmp_path: Path) -> None:
    where = tmp_path / "ticks.json"
    where.write_text("{not json", encoding="utf-8")
    book = newphone.load_ticks(str(where))
    assert book.unreadable

    newphone.save_ticks(book, str(where))

    assert (tmp_path / "ticks.json.unreadable").read_text(encoding="utf-8") == "{not json"
    assert json.loads(where.read_text(encoding="utf-8"))["ticked"] == []


def test_the_ticks_file_lives_in_the_current_directory(tmp_path: Path) -> None:
    assert Path(newphone.ticks_path()).parent == tmp_path


def test_progress_counts_only_what_is_in_the_list() -> None:
    checklist = newphone.build(PrimeItems)

    done, total = checklist.counts({"profile:Dawn", "profile:Gone"})

    assert (done, total) == (1, len(checklist.items()))


# ==========================================
# The text
# ==========================================
def test_the_text_marks_ticked_items_and_says_what_is_not_on_the_phone() -> None:
    _store(PHONE, "com.joaomgcd.autoinput")

    text = newphone.as_text(newphone.build(PrimeItems, PHONE), {"plugin:com.joaomgcd.autoinput"})

    assert "[x] com.joaomgcd.autoinput" in text
    assert "[ ] Music (com.example.music)  -- NOT ON THE PHONE" in text
    assert f"$ {ADB}" in text
    assert "Value: Berlin" in text
    assert "checked against the app list fetched from" in text


def test_the_text_says_when_no_app_list_was_used() -> None:
    assert "No app list was fetched" in newphone.as_text(newphone.build(PrimeItems), set())


def test_hiding_values_keeps_them_out_of_the_text() -> None:
    text = newphone.as_text(newphone.build(PrimeItems), set(), show_values=False)

    assert "s3cret" not in text
    assert "Berlin" not in text
    assert "(hidden)" in text


def test_the_report_is_written_to_the_output_folder() -> None:
    path = newphone.write_report(newphone.build(PrimeItems), {"profile:Dawn"}, show_values=True, state=PrimeItems)

    assert path
    assert "[x] Dawn" in Path(path).read_text(encoding="utf-8")


# ==========================================
# The data it reads from readiness
# ==========================================
def test_every_command_in_the_data_is_also_in_what_the_recipient_is_told() -> None:
    """The commands are the 'how' text typed out; if one is edited without the other the checklist disagrees with Readiness."""
    for access_id in ("write_secure_settings", "read_logs"):
        for command in readiness.access_adb(access_id):
            assert command in readiness.access_how(access_id)


def test_an_access_with_no_commands_has_none() -> None:
    assert readiness.access_adb("root") == ()
