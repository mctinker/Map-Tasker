"""Readiness check (readiness.py) Unit Tests -- what a shared configuration needs on another phone

Two kinds of test live here.

The data tests exist because readiness.json is a hand-built table keyed by Tasker code, and
the failure mode of a wrong key is silence: an action the table fails to match reads as
"needs nothing", which is the one answer this feature must not give by accident.  So every
key is resolved against actionc, and every argument a 'when' names has to be one that action
really has.

The behaviour tests build small <TaskerData> documents and read them the way an export would
be read, one need at a time.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import taskerd
from maptasker.src.mapops import readiness

TABLE = readiness.READINESS_FILE


def _data() -> dict:
    with open(TABLE, encoding="utf-8") as handle:
        return json.load(handle)


# ==========================================
# The data file
# ==========================================


def test_every_key_is_an_action_event_or_state_actionc_knows() -> None:
    """A key that matches nothing would read as 'no requirement'."""
    unknown = [key for key in _data()["items"] if key not in action_codes or not action_codes[key].name]
    assert not unknown


def test_every_key_has_the_suffix_of_what_it_is() -> None:
    assert all(key[-1] in "tes" and key[:-1].isdigit() for key in _data()["items"])


def test_every_need_names_an_access_the_file_describes() -> None:
    data = _data()
    named = {part for row in data["items"].values() for spec in row.get("needs", ()) for part in spec.split("|")}
    named |= set(data["by_argument"].values())
    assert named <= set(data["access"])


def test_every_access_says_what_to_do_about_it() -> None:
    assert all(entry["label"] and entry["how"] for entry in _data()["access"].values())


def test_every_when_names_an_argument_the_action_has() -> None:
    for key, row in _data()["items"].items():
        have = {f"arg{argument.arg_id}" for argument in action_codes[key].args}
        assert set(row.get("when", {})) <= have, key


def test_every_switch_the_structural_rule_reads_exists_on_some_action() -> None:
    """If Tasker renames 'Use Root' the rule goes quiet; this is where that is noticed."""
    present = {argument.arg_name.lower() for entry in action_codes.values() for argument in entry.args}
    assert set(_data()["by_argument"]) <= present


def test_every_release_is_a_version_that_sorts() -> None:
    for key, row in _data()["items"].items():
        if "since" in row:
            assert readiness.version_key(row["since"]), key


def test_the_names_the_table_was_built_from_are_still_the_names() -> None:
    """Spot checks of the entries the table's reasoning rests on."""
    names = {key: action_codes[key].name for key in ("375t", "18t", "379t", "235t", "47t", "2085e", "461e")}
    assert names == {
        "375t": "ADB Wifi",
        "18t": "Kill App",
        "379t": "Device Admin/Owner",
        "235t": "Custom Setting",
        "47t": "Show Scene",
        "2085e": "Logcat Entry",
        "461e": "Notification",
    }


def test_version_key_sorts_numerically_not_alphabetically() -> None:
    assert readiness.version_key("5.10") > readiness.version_key("5.9.3")
    assert readiness.version_key("6.7.6-beta") == (6, 7, 6)


# ==========================================
# Building documents
# ==========================================
_BLURB = "com.twofortyfouram.locale.intent.extra.BLURB"


def _action(code: int, *arguments: str) -> str:
    return f'<Action sr="act0" ve="7"><code>{code}</code>{"".join(arguments)}</Action>'


def _int(argument: int, value: int) -> str:
    return f'<Int sr="arg{argument}" val="{value}"/>'


def _task(name: str, *actions: str) -> str:
    return f'<Task sr="task1"><id>1</id><nme>{name}</nme>{"".join(actions)}</Task>'


def _document(*children: str, tv: str = "6.3.13") -> ET.Element:
    return ET.fromstring(f'<TaskerData sr="" dvi="1" tv="{tv}">{"".join(children)}</TaskerData>')


def _check(*children: str, **kwargs: str) -> readiness.Readiness:
    return readiness.check_tree(_document(*children, **kwargs))


def _access(result: readiness.Readiness) -> dict[tuple[str, ...], tuple[str, ...]]:
    return {need.any_of: need.used_by for need in result.access}


# ==========================================
# Special access
# ==========================================


def test_adb_wifi_is_needed_by_the_adb_wifi_action() -> None:
    result = _check(_task("Backup", _action(375)))

    assert _access(result) == {("adb_wifi",): ("ADB Wifi in Task 'Backup'",)}


def test_a_switch_that_is_on_asks_for_what_it_names() -> None:
    """Run Shell's Use Root is argument 2; Use Shizuku is argument 8."""
    result = _check(_task("Shell", _action(123, _int(2, 1)), _action(123, _int(8, 1))))

    assert set(_access(result)) == {("root",), ("shizuku",)}


def test_a_switch_that_is_off_asks_for_nothing() -> None:
    assert _check(_task("Shell", _action(123, _int(2, 0)))).access == []


def test_a_switch_set_from_a_variable_is_not_guessed_at() -> None:
    variable = '<Int sr="arg2"><var>%UseRoot</var></Int>'
    assert _check(_task("Shell", _action(123, variable))).access == []


def test_the_use_root_switch_is_found_on_actions_the_table_has_no_entry_for() -> None:
    """The reason the rule is structural: Delete File (406) has one and no table row."""
    assert "406t" not in _data()["items"]
    assert set(_access(_check(_task("Clean", _action(406, _int(2, 1)))))) == {("root",)}


def test_a_choice_of_access_is_one_need_with_every_alternative() -> None:
    result = _check(_task("Quit", _action(18)))

    assert [need.any_of for need in result.access] == [("root", "adb_wifi", "device_owner", "shizuku")]


def test_a_stricter_need_absorbs_the_looser_one_and_says_what_it_also_meets() -> None:
    """If something here needs root outright the phone has root, so Kill App's choice is no choice."""
    result = _check(_task("Quit", _action(18)), _task("Shell", _action(123, _int(2, 1))))

    [need] = result.access
    assert need.any_of == ("root",)
    assert need.used_by == ("Run Shell in Task 'Shell'",)
    assert need.also_meets == ("Kill App in Task 'Quit'",)


def test_needs_that_do_not_cover_each_other_stay_apart() -> None:
    result = _check(_task("Both", _action(375), _action(379)))

    assert set(_access(result)) == {("adb_wifi",), ("device_owner",)}


def test_the_same_place_is_listed_once_however_often_it_is_used() -> None:
    result = _check(_task("Loop", _action(375), _action(375), _action(375)))

    assert _access(result) == {("adb_wifi",): ("ADB Wifi in Task 'Loop'",)}


def test_custom_setting_needs_secure_settings_only_for_global_and_secure() -> None:
    """Type is argument 0: 0 Global, 1 Secure, 2 System.  System is a permission Tasker asks for itself."""
    assert set(_access(_check(_task("Set", _action(235, _int(0, 0)))))) == {("write_secure_settings", "root")}
    assert set(_access(_check(_task("Set", _action(235, _int(0, 1)))))) == {("write_secure_settings", "root")}
    assert _check(_task("Set", _action(235, _int(0, 2)))).access == []


def test_what_an_access_merely_meets_is_not_reported_as_needing_it() -> None:
    """Custom Setting could use Write Secure Settings; under Root it is 'also met', never 'needed by'."""
    text = _check(_task("Set", _action(235, _int(0, 1))), _task("Shell", _action(123, _int(2, 1)))).as_text()

    assert "Needed by: Run Shell in Task 'Shell'.  Also met by it: Custom Setting in Task 'Set'" in text


def test_custom_setting_with_root_ticked_needs_root_not_a_choice() -> None:
    result = _check(_task("Set", _action(235, _int(0, 1), _int(3, 1))))

    assert set(_access(result)) == {("root",)}


def test_show_scene_needs_the_overlay_permission_only_for_overlay_modes() -> None:
    """Display As is argument 1: 0-2 are the three overlay modes, 3 onward are dialogs and activities."""
    assert set(_access(_check(_task("Show", _action(47, _int(1, 0)))))) == {("overlay",)}
    assert _check(_task("Show", _action(47, _int(1, 3)))).access == []


def test_an_event_can_need_access_too() -> None:
    profile = '<Profile sr="prof1"><id>1</id><nme>Logs</nme><Event sr="con0" ve="2"><code>2085</code></Event></Profile>'

    assert set(_access(_check(profile))) == {("read_logs", "root", "adb_wifi", "shizuku")}


def test_an_action_the_table_does_not_know_is_not_reported() -> None:
    """Said the other way round from how it is easy to read: not listed does not mean needs nothing."""
    result = _check(_task("Plain", _action(547)))  # Variable Set

    assert result.access == []
    assert result.needs_nothing


# ==========================================
# Plugins and apps
# ==========================================


def _plugin_action(package: str, code: int = 1040876951) -> str:
    return (
        f'<Action sr="act0" ve="7"><code>{code}</code>'
        f'<Bundle sr="arg0"><Vals sr="val"><{_BLURB}>blurb</{_BLURB}></Vals></Bundle>'
        f'<Str sr="arg1">{package}</Str><Str sr="arg2">com.example.Edit</Str></Action>'
    )


def test_a_plugin_is_listed_by_package_with_where_it_is_used() -> None:
    result = _check(_task("Click", _plugin_action("com.joaomgcd.autoinput")))

    assert [(need.package, len(need.used_by)) for need in result.plugins] == [("com.joaomgcd.autoinput", 1)]
    assert "Task 'Click'" in result.plugins[0].used_by[0]


def test_a_plugin_action_is_not_also_looked_up_as_a_built_in() -> None:
    """Plugin codes are shared by many plugins; the package is the identity."""
    assert _check(_task("Click", _plugin_action("com.example.plugin", code=375))).access == []


def test_a_plugin_condition_counts_as_a_plugin() -> None:
    profile = (
        '<Profile sr="prof1"><id>1</id><nme>P</nme><State sr="con0" ve="2"><code>1000</code>'
        f'<Bundle sr="arg0"><Vals sr="val"><{_BLURB}>b</{_BLURB}></Vals></Bundle>'
        '<Str sr="arg1">com.example.state</Str></State></Profile>'
    )

    assert [need.package for need in _check(profile).plugins] == ["com.example.state"]


def _app(package: str, label: str = "") -> str:
    return f'<App sr="arg0"><appClass>c</appClass><appPkg>{package}</appPkg><label>{label}</label></App>'


def test_an_app_is_listed_with_the_label_the_file_gives_it() -> None:
    result = _check(_task("Open", _action(20, _app("com.example.app", "Example"))))

    assert [(need.package, need.label) for need in result.apps] == [("com.example.app", "Example")]


def test_an_app_chosen_by_variable_is_not_an_app_to_install() -> None:
    assert _check(_task("Open", _action(20, _app("%app_package")))).apps == []


def test_tasker_itself_is_not_an_app_to_install() -> None:
    assert _check(_task("Open", _action(20, _app("net.dinglisch.android.taskerm")))).apps == []


def test_an_app_condition_on_a_profile_counts() -> None:
    profile = (
        '<Profile sr="prof1"><id>1</id><nme>When</nme><App sr="con0"><cls0>c</cls0>'
        "<label0>Maps</label0><pkg0>com.example.maps</pkg0></App></Profile>"
    )

    assert [need.package for need in _check(profile).apps] == ["com.example.maps"]


# ==========================================
# Variables Tasker will ask about
# ==========================================


def _variable(name: str, *, configure: str | None, value: str = "", prompt: str = "") -> str:
    flag = "" if configure is None else f"<pvci>{configure}</pvci>"
    return (
        f'<ProfileVariable sr="pv0"><pvn>{name}</pvn>{flag}<pvd>{prompt}</pvd>'
        f"<pvt>t</pvt><pvv>{value}</pvv></ProfileVariable>"
    )


def _project(*variables: str) -> str:
    return f'<Project sr="proj0"><name>Home</name>{"".join(variables)}</Project>'


def test_a_configure_on_import_variable_is_one_tasker_asks_about() -> None:
    result = _check(_project(_variable("%ApiKey", configure="true", prompt="Your API key")))

    [need] = result.prompts
    assert (need.owner, need.variable, need.prompt, need.type_label) == (
        "Project 'Home'",
        "%ApiKey",
        "Your API key",
        "Text",
    )


def test_a_variable_with_configure_on_import_off_is_not() -> None:
    assert _check(_project(_variable("%Quiet", configure="false"))).prompts == []


def test_a_variable_with_no_flag_is_not_assumed_to_be() -> None:
    assert _check(_project(_variable("%Odd", configure=None))).prompts == []


def test_whether_there_is_a_default_is_reported_but_never_the_default() -> None:
    result = _check(_project(_variable("%ApiKey", configure="true", value="sk-" + "live-do-not-print-this")))
    [need] = result.prompts

    assert need.has_default
    assert "sk-" + "live-do-not-print-this" not in result.as_text()


def test_a_task_and_a_profile_can_ask_too() -> None:
    task = f'<Task sr="task1"><id>1</id><nme>T</nme>{_variable("%A", configure="true")}</Task>'
    profile = f'<Profile sr="prof1"><id>1</id><nme>P</nme>{_variable("%B", configure="true")}</Profile>'

    assert {need.owner for need in _check(task, profile).prompts} == {"Task 'T'", "Profile 'P'"}


# ==========================================
# The Tasker version
# ==========================================


def test_the_minimum_is_the_newest_release_among_what_is_used() -> None:
    result = _check(_task("New", _action(374), _action(379)))  # Screen Capture 5.14.6, Device Admin/Owner 6.3.12

    assert result.minimum == readiness.VersionNeed("6.3.12", ("Device Admin/Owner",))


def test_two_items_from_the_newest_release_are_both_named() -> None:
    result = _check(_task("New", _action(379), _action(448)))

    assert result.minimum is not None
    assert set(result.minimum.because) == {"Device Admin/Owner", "Array Compare"}


def test_versions_are_compared_as_numbers() -> None:
    """5.10 is newer than 5.9.3 -- a string comparison would say the opposite."""
    result = _check(_task("New", _action(378), _action(383)))  # List Dialog 5.9.3, Settings Panel 5.11.13

    assert result.minimum is not None
    assert result.minimum.version == "5.11.13"


def test_nothing_known_to_be_new_gives_no_minimum_and_says_so() -> None:
    result = _check(_task("Old", _action(547)))

    assert result.minimum is None
    [version] = [section for section in result.sections() if section.title == "Tasker version"]
    assert "known to need a recent Tasker" in version.empty


def test_the_version_that_wrote_the_file_is_reported() -> None:
    assert _check(_task("Old", _action(547)), tv="6.7.6-beta").written_by == "6.7.6-beta"


# ==========================================
# The report
# ==========================================


def test_an_empty_configuration_says_what_it_found_and_not_that_it_is_ready() -> None:
    text = _check(_task("Nothing", _action(547))).as_text()

    assert "No plugins are used." in text
    assert "Built from what is in the file" in text
    assert "ready" not in text.lower()


def test_places_are_capped_with_a_count_of_the_rest() -> None:
    tasks = [_task(f"T{number}", _action(375)) for number in range(7)]
    text = _check(*tasks).as_text()

    assert "and 3 more" in text


def test_the_text_report_names_the_scope_and_every_section() -> None:
    result = readiness.check_tree(_document(_task("T", _action(375))), "Project 'Home'")
    text = result.as_text()

    assert text.startswith("What Project 'Home' needs on another phone")
    for heading in ("Tasker version", "Plugins", "Apps", "Special access", "Variables Tasker will ask about"):
        assert heading in text


def test_a_choice_reads_as_a_choice() -> None:
    [section] = [s for s in _check(_task("Quit", _action(18))).sections() if s.title == "Special access"]

    assert section.lines[0].text == "Root, ADB Wi-Fi, Device Admin/Owner or Shizuku (any one of them)"


# ==========================================
# Reading a real export: the Project's own contents, and only those
# ==========================================
_PROJECT_XML = f"""<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <id>f19b5151-01b6-46f6-8cd5-b3bc1fe0b486</id>
    <name>Home</name>
    <pids>100</pids>
    <tids>20</tids>
    {_variable("%ApiKey", configure="true", prompt="Your API key")}
  </Project>
  <Project sr="proj1" ve="2">
    <id>a0000000-0000-0000-0000-000000000001</id>
    <name>Elsewhere</name>
    <tids>30</tids>
  </Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <nme>Watching</nme>
    <mid0>20</mid0>
  </Profile>
  <Task sr="task20"><id>20</id><nme>Opener</nme>{_action(379)}</Task>
  <Task sr="task30"><id>30</id><nme>Unshared</nme>{_action(375)}</Task>
  <Scene sr="scene0">
    <nme>Panel</nme>
    <RectElement sr="rect0"><clickTask>30</clickTask></RectElement>
  </Scene>
</TaskerData>
"""


@pytest.fixture
def loaded() -> None:
    root = ET.fromstring(_PROJECT_XML)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file, encoding="utf-8") as handle:
        specs = json.load(handle)
    PrimeItems.tasker_arg_specs = specs
    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }


def test_a_project_is_checked_as_its_export_would_be_written(loaded: None) -> None:
    result = readiness.check_project("Home", state=PrimeItems)

    assert result.scope == "Project 'Home'"
    assert set(_access(result)) == {("device_owner",)}
    assert [need.variable for need in result.prompts] == ["%ApiKey"]
    assert result.minimum is not None
    assert result.minimum.version == "6.3.12"
    assert result.written_by == "6.3.13"


def test_what_the_project_does_not_ship_is_not_counted(loaded: None) -> None:
    """ADB Wifi lives in 'Unshared', which belongs to another Project: not in this export."""
    assert ("adb_wifi",) not in _access(readiness.check_project("Home", state=PrimeItems))


def test_a_project_that_is_gone_raises_as_the_export_does(loaded: None) -> None:
    with pytest.raises(ValueError, match="no longer exists"):
        readiness.check_project("Missing", state=PrimeItems)


def test_a_scene_is_checked_with_the_tasks_its_buttons_fire(loaded: None) -> None:
    """The Scene export bundles the Task a button fires, so what that Task needs is the Scene's need."""
    result = readiness.check_scene("Panel", state=PrimeItems)

    assert result.scope == "Scene 'Panel'"
    assert set(_access(result)) == {("adb_wifi",)}


def test_a_scene_that_is_gone_raises_as_the_export_does(loaded: None) -> None:
    with pytest.raises(ValueError, match="Missing"):
        readiness.check_scene("Missing", state=PrimeItems)
