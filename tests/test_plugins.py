"""Plugin support Unit Tests -- reading plugin settings, and plugins not installed

Two halves.  plugset reads the settings of the four plugins Tasker users reach for most
(AutoTools, AutoInput, Join, Home Assistant) the way the plugin itself would, where the Map
used to show one "Name=value" line per raw field -- which for a TaskerPluginLibrary plugin
is a single line of JSON.  plugchk crosses the plugins a configuration uses against the app
list fetched from the device, and the Health Check reports the ones that are not on it.

Every bundle here is invented: the field NAMES are the plugins' own, as they appear in real
backups, and every value is made up.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from maptasker.src import actargs, healthck, plugchk, plugset, taskedit, taskerd
from maptasker.src.actionc import action_codes
from maptasker.src.initparg import ProgramArguments
from maptasker.src.mapjump import text_report
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    import pathlib

_BLURB = "com.twofortyfouram.locale.intent.extra.BLURB"


def _vals(fields: dict[str, str], blurb: str = "") -> str:
    """A <Vals> the way Tasker writes one: each value with its '-type' twin beside it."""
    body = "".join(
        f"<{name}>{value}</{name}><{name}-type>java.lang.String</{name}-type>" for name, value in fields.items()
    )
    return f'<Vals sr="val"><{_BLURB}>{blurb}</{_BLURB}>{body}</Vals>'


def _action(package: str, fields: dict[str, str], blurb: str = "", code: str = "1040876951") -> ET.Element:
    """A plugin action: <Bundle> in arg0, the plugin's package in arg1, its screen in arg2."""
    return ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<Action sr="act0" ve="7"><code>{code}</code><Bundle sr="arg0">{_vals(fields, blurb)}</Bundle>'
        f'<Str sr="arg1" ve="3">{package}</Str><Str sr="arg2" ve="3">{package}.Config</Str></Action>',
    )


def _decoded(package: str, fields: dict[str, str], blurb: str = "") -> dict[str, str]:
    """{label: value} for one plugin action's settings, as plugset reads them."""
    action = _action(package, fields, blurb)
    decoded = plugset.decode_settings(action.find("Bundle/Vals"), package, blurb)
    assert decoded is not None
    return dict(decoded.lines)


def _json(document: dict) -> str:
    """A 'parameters' field, escaped for the XML it sits in."""
    return json.dumps(document).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ##################################################################################
# Which plugin an action belongs to
# ##################################################################################
def test_a_plugin_action_names_its_package() -> None:
    """arg1, on every plugin Action, Event and State."""
    assert plugset.plugin_package(_action("com.joaomgcd.join", {})) == "com.joaomgcd.join"


def test_a_built_in_actions_output_variables_bundle_is_not_a_plugin() -> None:
    """HTTP Request and friends carry a <Bundle> too, listing the variables they set.  It has
    no blurb, and it is not a plugin however many arguments sit beside it.
    """
    action = ET.fromstring(  # noqa: S314
        '<Action sr="act0" ve="7"><code>339</code><Bundle sr="arg0"><Vals sr="val">'
        "<net.dinglisch.android.tasker.RELEVANT_VARIABLES>x</net.dinglisch.android.tasker.RELEVANT_VARIABLES>"
        '</Vals></Bundle><Str sr="arg1" ve="3">https://example.com</Str></Action>',
    )
    assert not plugset.is_plugin(action)
    assert plugset.plugin_package(action) == ""


@pytest.mark.parametrize(
    ("name", "label"),
    [("pushDevices", "Push Devices"), ("_action", "Action"), ("htmlReadURL", "Html Read URL"), ("Text", "Text")],
)
def test_a_field_name_reads_as_a_label(name: str, label: str) -> None:
    """The case changes and underscores the plugins' authors use, as words."""
    assert plugset.humanize(name) == label


# ##################################################################################
# Join
# ##################################################################################
_JOIN_PUSH = {
    "parameters": _json(
        {
            "advancedSettings": {"sendCustomMessage": False},
            "app": {},
            "find": False,
            "screenshot": True,
            "pushDevices": "0123abcd",
            "title": "Door",
            "text": "Somebody rang",
            "generatedValues": {},
        },
    ),
    "plugininstanceid": "1111-2222",
    "plugintypeid": "com.joaomgcd.join.tasker.intent.IntentSendPush",
}


def test_a_join_push_is_read_out_of_its_json() -> None:
    """The whole push is one field of JSON; each setting in it is a line of its own."""
    settings = _decoded("com.joaomgcd.join", _JOIN_PUSH)
    assert settings["Title"] == "Door"
    assert settings["Text"] == "Somebody rang"
    assert settings["Take Screenshot"] == "true"


def test_what_a_join_push_leaves_alone_is_not_shown() -> None:
    """A switch that is off, an empty heading and the library's own bookkeeping are all
    what the plugin writes for a setting nobody made.
    """
    settings = _decoded("com.joaomgcd.join", _JOIN_PUSH)
    assert "Find Device" not in settings
    assert "Send Custom Message" not in settings
    assert not any("plugin" in label.lower() or "generated" in label.lower() for label in settings)


def test_join_devices_are_left_to_the_blurb_when_it_names_them() -> None:
    """Join stores the devices as ids and names them in its blurb whenever it can."""
    assert "Devices" in _decoded("com.joaomgcd.join", _JOIN_PUSH)
    assert "Devices" not in _decoded("com.joaomgcd.join", _JOIN_PUSH, "Device: Kitchen Tablet")


def test_a_join_filter_carries_its_own_switches() -> None:
    """'Push Received' filters on text, title and URL, each with four switches.  Read on its
    own, "FilterTitleRegex=true" says nothing about what is being matched.
    """
    settings = _decoded(
        "com.joaomgcd.join",
        {
            "FilterTitle": "ring.*",
            "FilterTitleRegex": "true",
            "FilterTitleCaseInsensitive": "true",
            "FilterTitleExact": "false",
            "FilterText": "",
            "FilterTextRegex": "true",
        },
    )
    assert settings == {"Title Filter": "ring.* (regex, ignoring case)"}


# ##################################################################################
# AutoInput
# ##################################################################################
def test_autoinputs_numbers_are_read_as_what_they_mean() -> None:
    """ActionType and GlobalAction are Android's own constants: 16 is a click, 1 is Back."""
    settings = _decoded("com.joaomgcd.autoinput", {"ActionType": "16", "FieldSelectionType": "1", "ActionId": "ok"})
    assert settings == {"Action": "Click", "Find By": "Id", "Value": "ok"}
    assert _decoded("com.joaomgcd.autoinput", {"GlobalAction": "1"}) == {"Global Action": "Back"}


def test_a_number_autoinput_does_not_document_is_shown_as_it_is() -> None:
    """A guess would be worse than the number."""
    assert _decoded("com.joaomgcd.autoinput", {"FieldSelectionType": "3"}) == {"Find By": "3"}


def test_what_the_blurb_already_says_is_not_repeated() -> None:
    """AutoInput's blurb is the whole of what the action does."""
    settings = _decoded(
        "com.joaomgcd.autoinput",
        {"ActionType": "16", "FieldSelectionType": "0", "ActionId": "Settings", "UnlockScreen": "true"},
        "Type: Text\nValue: Settings\nAction : Click",
    )
    assert settings == {"Unlock Screen": "true"}


def test_a_value_is_not_hidden_because_the_blurb_mentions_the_word() -> None:
    """Only the blurb's own "Label: value" lines count as saying a setting."""
    settings = _decoded("com.joaomgcd.join", {"parameters": _json({"title": "Alarm"})}, "Push about the alarm clock")
    assert settings == {"Title": "Alarm"}


def test_an_autoinput_script_stays_on_one_line() -> None:
    """Everything downstream reads one setting per line."""
    script = "click(text,OK)\n\nclick(id,com.example:id/next)"
    settings = _decoded("com.joaomgcd.autoinput", {"parameters": _json({"_action": script})})
    assert settings == {"Actions": "click(text,OK); click(id,com.example:id/next)"}


# ##################################################################################
# AutoTools
# ##################################################################################
def test_a_list_in_taskers_own_encoding_is_read_as_a_list() -> None:
    """AutoTools keeps a list in one field, as a <StringArray>; an empty one says nothing."""
    fields = {
        "FieldsToGet": (
            '&lt;StringArray sr=""&gt;&lt;_array_FieldsToGet0&gt;seconds&lt;/_array_FieldsToGet0&gt;'
            "&lt;_array_FieldsToGet1&gt;minutes&lt;/_array_FieldsToGet1&gt;&lt;/StringArray&gt;"
        ),
        "Empty": '&lt;StringArray sr=""/&gt;',
    }
    assert _decoded("com.joaomgcd.autotools", fields) == {"Fields To Get": "seconds, minutes"}


def test_two_settings_of_one_name_are_told_apart_by_their_heading() -> None:
    """An AutoTools dialog has a top margin for its bottom buttons and another for its title's."""
    settings = _decoded(
        "com.joaomgcd.autotools",
        {"parameters": _json({"dialogButtomButtons": {"topMargin": "16"}, "dialogTitleButtons": {"topMargin": "8"}})},
    )
    assert settings == {"Top Margin": "16", "Dialog Title Buttons Top Margin": "8"}


# ##################################################################################
# Home Assistant
# ##################################################################################
_HA_CALL = {
    "domain": "light",
    "service": "turn_on",
    "entityId": "light.hall",
    "dataJson": "{}",
    "instanceId": "abcd1234",
}


def test_a_home_assistant_service_is_named_the_way_home_assistant_names_it() -> None:
    """domain + service is light.turn_on; the server id and an empty "{}" of data are left out."""
    settings = _decoded("com.github.db1996.taskerha", _HA_CALL)
    assert settings == {"Service": "light.turn_on", "Entity": "light.hall"}


def test_home_assistants_blurb_gives_way_to_its_settings() -> None:
    """Its blurb is nothing but the raw fields again ("dataJson: {}"), server id and all."""
    action = _action("com.github.db1996.taskerha", _HA_CALL, "dataJson: {}\ninstanceId: abcd1234")
    value = actargs.get_bundle(action, {"returning_something": True}, "0")["arg0"]["value"]
    assert value == "Configuration Parameter(s):\nService=light.turn_on\nEntity=light.hall\n"


# ##################################################################################
# Everything else, and the editors
# ##################################################################################
def test_any_other_plugin_is_left_to_the_generic_reading() -> None:
    """One "Name=value" line per field, exactly as before."""
    action = _action("com.example.other", {"parameters": _json({"a": 1})})
    assert plugset.decode_settings(action.find("Bundle/Vals"), "com.example.other") is None
    value = actargs.get_bundle(action, {"returning_something": True}, "0")["arg0"]["value"]
    assert 'parameters={"a": 1}' in value


def test_a_decoded_plugin_still_leads_with_its_blurb_in_the_map() -> None:
    """The blurb is the plugin's own sentence about what the action does."""
    action = _action("com.joaomgcd.join", _JOIN_PUSH, "Device: Kitchen Tablet")
    value = actargs.get_bundle(action, {"returning_something": True}, "0")["arg0"]["value"]
    assert value.startswith("Configuration Parameter(s):\nDevice: Kitchen Tablet\n")
    assert "Title=Door" in value
    assert "plugininstanceid" not in value


def test_the_editor_shows_what_a_plugin_is_set_to() -> None:
    """Still read-only, but no longer a blank box."""
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file) as handle:
        PrimeItems.tasker_arg_specs = json.load(handle)
    action = _action("com.joaomgcd.join", _JOIN_PUSH, "Device: Kitchen Tablet", code="774351906")
    entry = action_codes["774351906t"]
    effective = action_codes[entry.redirect].args if entry.redirect else entry.args
    settings = next(arg for arg in taskedit.build_editable_args(action, effective, state=PrimeItems) if arg.arg_id == "0")
    assert settings.widget_kind == "readonly"
    assert settings.current_value.startswith("Device: Kitchen Tablet; ")
    assert "Title: Door" in settings.current_value


# ##################################################################################
# Plugins that are not installed
# ##################################################################################
_CONFIG_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><pids>5</pids><tids>1,2</tids></Project>
  <Profile sr="prof5" ve="2"><id>5</id><nme>Doorbell</nme><mid0>1</mid0>
    <Event sr="con0" ve="2"><code>1344888481</code><Bundle sr="arg0">{missing_vals}</Bundle>
      <Str sr="arg1" ve="3">com.example.missing</Str><Str sr="arg2" ve="3">com.example.missing.Edit</Str></Event>
  </Profile>
  <Task sr="task1"><id>1</id><nme>Ring</nme>
    <Action sr="act0" ve="7"><code>774351906</code><Bundle sr="arg0">{join_vals}</Bundle>
      <Str sr="arg1" ve="3">com.joaomgcd.join</Str><Str sr="arg2" ve="3">com.joaomgcd.join.Config</Str></Action>
    <Action sr="act1" ve="7"><code>1040876951</code><Bundle sr="arg0">{missing_vals}</Bundle>
      <Str sr="arg1" ve="3">com.example.missing</Str><Str sr="arg2" ve="3">com.example.missing.Edit</Str></Action>
  </Task>
  <Task sr="task2"><id>2</id><nme>Plain</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action>
  </Task>
</TaskerData>""".format(join_vals=_vals({"x": "1"}, "Join"), missing_vals=_vals({"y": "2"}, "Missing"))

_ONE_DEVICE = {"192.0.2.1:1821": ("2026-09-01 10:00:00", frozenset({"com.joaomgcd.join", "com.example.app"}))}


@pytest.fixture(autouse=True)
def _loaded() -> None:
    """Build the PrimeItems tables from the fixture, the way taskerd does from a file."""
    root = ET.fromstring(_CONFIG_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100)
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": {},
        "all_services": [],
    }
    tables["all_profiles_by_name"] = {p["name"]: {"xml": p["xml"], "id": k} for k, p in tables["all_profiles"].items()}
    tables["all_tasks_by_name"] = {t["name"]: {"xml": t["xml"], "id": k} for k, t in tables["all_tasks"].items()}
    PrimeItems.tasker_root_elements = tables


def _devices(devices: dict) -> mock._patch:
    """The fetched app lists, instead of the MapTasker_Apps.json in whatever directory this runs in."""
    return mock.patch.object(plugchk.appinv, "fetched_packages", return_value=devices)


def test_a_plugin_the_device_does_not_have_is_reported_once_for_all_its_uses() -> None:
    """One finding per plugin, naming the list it was checked against and every place using it."""
    with _devices(_ONE_DEVICE):
        problems = plugchk.lint_problems()
    assert [problem.where for problem in problems] == ["Plugin com.example.missing"]
    detail = "".join(text for text, _ in problems[0].detail)
    assert "192.0.2.1:1821 on 2026-09-01 10:00:00" in detail
    assert "all 2 places" in detail
    assert "Task 'Ring' (id 1) action 2 (AutoInput UI Query)" in detail
    assert "Join" not in detail  # installed, so not among the places named
    assert "Profile 'Doorbell' (id 5) Event" in detail


def test_each_place_is_named_by_its_own_action_not_the_one_it_borrows_arguments_from() -> None:
    """actionc.py points most plugin codes at 1040876951t for their arguments, and that
    entry is named 'AutoInput UI Query'.  A Join action is a Join action.
    """
    PrimeItems.tasker_root_elements["all_tasks"]["1"]["xml"].find("Action/Str[@sr='arg1']").text = "com.example.gone"
    with _devices(_ONE_DEVICE):
        problems = {problem.where: problem for problem in plugchk.lint_problems()}
    detail = "".join(text for text, _ in problems["Plugin com.example.gone"].detail)
    assert detail.endswith("action 1 (Join Action).")


def test_each_place_a_missing_plugin_is_used_is_a_link() -> None:
    """The location line goes to the first place; the detail line links every one."""
    with _devices(_ONE_DEVICE):
        problem = plugchk.lint_problems()[0]
    linked = [target for _, target in problem.detail if target is not None]
    assert problem.target == linked[0]
    assert problem.related == linked[1:]
    assert problem.target.action == 2


def test_a_plugin_on_any_fetched_device_is_not_reported() -> None:
    """The backup does not say which phone it is for."""
    tablet = {"192.0.2.2:1821": ("2026-08-01 09:00:00", frozenset({"com.example.missing"}))}
    with _devices({**_ONE_DEVICE, **tablet}):
        assert plugchk.lint_problems() == []


def test_with_no_app_list_nothing_is_reported_and_the_report_says_why() -> None:
    """Silence would read as every plugin being installed."""
    with _devices({}):
        assert plugchk.lint_problems() == []
        rows, _ = healthck.run_health_check(state=PrimeItems)
    report = text_report(rows)
    assert "[PLUGIN-NOT-INSTALLED]" not in report
    assert "uses 2 plugin(s), and none of them was checked" in report


def test_the_health_check_reports_it_as_a_warning_with_a_note() -> None:
    """A warning, since the list may be older than what is on the phone -- which the note says."""
    with _devices(_ONE_DEVICE):
        rows, counts = healthck.run_health_check(state=PrimeItems)
    report = text_report(rows)
    assert "[PLUGIN-NOT-INSTALLED]  Plugin com.example.missing" in report
    assert "NOTE ON PLUGINS" in report
    assert "none of them was checked" not in report
    assert counts[healthck.WARNING] >= 1


def test_unticking_it_skips_the_check() -> None:
    """And takes its note with it."""
    with _devices(_ONE_DEVICE):
        rows, _ = healthck.run_health_check(skip=[plugchk.NOT_INSTALLED], state=PrimeItems)
    report = text_report(rows)
    assert "[PLUGIN-NOT-INSTALLED]" not in report
    assert "NOTE ON PLUGINS" not in report


def test_the_app_list_is_read_per_device(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Merged, it would call an app installed on the tablet installed on the phone."""
    cache = {
        "devices": {
            "phone": {"fetched": "2026-09-01", "apps": [{"pkg": "a.b", "label": "", "cls": ""}]},
            "tablet": {"fetched": "2026-08-01", "apps": [{"pkg": "c.d"}, {"pkg": " "}]},
        },
    }
    (tmp_path / "MapTasker_Apps.json").write_text(json.dumps(cache))
    monkeypatch.chdir(tmp_path)
    assert plugchk.appinv.fetched_packages() == {
        "phone": ("2026-09-01", frozenset({"a.b"})),
        "tablet": ("2026-08-01", frozenset({"c.d"})),
    }
