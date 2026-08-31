"""MapTasker Application/icon inventory (deviceinv) Unit Tests

Three things are being asserted here, and they fail in different ways.

*What can be harvested* -- the inventory is built by walking a whole configuration for its
<App> and <Img> elements, and Tasker writes those in five shapes (an argument's parallel
comma-joined lists, a condition's indexed one, and three of the four icon forms).  Missing
one shape doesn't raise; it silently produces a shorter list, which nobody notices.  So the
fixture carries every shape and the tests name each of them.

*What survives a write* -- these are the first arguments this tool writes that are not a
single Int or Str, and the failure mode is not an exception either: a stale <pkg> left
behind by a previous icon reads back as an icon pack, and a stale <label> list re-pairs the
wrong label with the wrong package.  Those two are tested directly.

*That addability moves* -- an App argument is addable only while there is an inventory, and
list_addable_actions memoizes addability.  The test that loading a configuration changes
what the Add Action picker offers is the one guarding the trap that memo sets.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import xml.etree.ElementTree as ET

import pytest
from urllib.parse import unquote

from maptasker.src import deviceinv, taskedit, taskerd
from maptasker.src.primitem import PrimeItems

LAUNCH_APP = "20t"  # App=arg0
KILL_APP = "18t"  # App=arg0
NOTIFY = "523t"  # Icon(<Img>)=arg2
FLASH = "548t"  # no App and no Icon -- addable with or without an inventory

MAPS = "com.google.android.apps.maps"
WHATSAPP = "com.whatsapp"
CRYSTAL = "net.dinglisch.android.ipack.crystalhd"

#   Task 20 'Opener'  a Launch App naming TWO apps (the comma-joined argument form, with
#                     labels and classes), and a Notify whose <Img> is a Tasker built-in
#                     carrying a <tint> that no icon change may destroy.
#   Task 21 'Killer'  a Kill App naming WhatsApp again, this time with no <label> at all --
#                     the ragged case, and what the merge has to fill in from Task 20.
#   Task 22 'Iconic'  an <Img> that is an app's own icon (so it stocks the app list too,
#                     with the launcher class), an icon pack's, and a %variable's.
#   Task 23 'Varied'  an <App> whose package is a %variable, which is real (backups in this
#                     repo hold them) and must sort last rather than first.
#   Profile 100       an App CONDITION -- the indexed cls0/label0/pkg0 form.
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>100</pids>
    <tids>20,21,22,23</tids>
  </Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <mid0>20</mid0>
    <nme>Watching</nme>
    <App sr="con0" ve="2">
      <cls0>com.google.android.maps.MapsActivity</cls0>
      <flags>2</flags>
      <label0>Maps</label0>
      <pkg0>com.google.android.apps.maps</pkg0>
    </App>
  </Profile>
  <Task sr="task20">
    <id>20</id>
    <nme>Opener</nme>
    <Img sr="icn" ve="2"><nme>hd_aaa_ext_home</nme></Img>
    <Action sr="act0" ve="7">
      <code>20</code>
      <App sr="arg0">
        <appClass>com.whatsapp.Main, com.google.android.maps.MapsActivity</appClass>
        <appPkg>com.whatsapp, com.google.android.apps.maps</appPkg>
        <label>WhatsApp, Maps</label>
      </App>
      <Str sr="arg1" ve="3"/>
      <Int sr="arg2" val="0"/>
      <Int sr="arg3" val="0"/>
    </Action>
    <Action sr="act1" ve="7">
      <code>523</code>
      <Str sr="arg0" ve="3">Hi</Str>
      <Img sr="arg2" ve="2"><nme>mw_action_language</nme><tint>-1</tint></Img>
    </Action>
  </Task>
  <Task sr="task21">
    <id>21</id>
    <nme>Killer</nme>
    <Action sr="act0" ve="7">
      <code>18</code>
      <App sr="arg0">
        <appClass>com.whatsapp.Main</appClass>
        <appPkg>com.whatsapp</appPkg>
      </App>
    </Action>
  </Task>
  <Task sr="task22">
    <id>22</id>
    <nme>Iconic</nme>
    <Action sr="act0" ve="7">
      <code>523</code>
      <Img sr="arg2" ve="2"><cls>com.docs.Main</cls><pkg>com.docs</pkg></Img>
    </Action>
    <Action sr="act1" ve="7">
      <code>523</code>
      <Img sr="arg2" ve="2"><nme>spreadsheet</nme><pkg>net.dinglisch.android.ipack.crystalhd</pkg></Img>
    </Action>
    <Action sr="act2" ve="7">
      <code>523</code>
      <Img sr="arg2" ve="2"><var>%my_icon</var></Img>
    </Action>
  </Task>
  <Task sr="task23">
    <id>23</id>
    <nme>Varied</nme>
    <Action sr="act0" ve="7">
      <code>20</code>
      <App sr="arg0">
        <appPkg>%app_package</appPkg>
      </App>
    </Action>
  </Task>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def _isolated_inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """No test in this file may read or write the real MapTasker_Apps.json.

    deviceinv.cache_path() resolves against the current directory, which during a test run
    is the checkout -- and anyone who has fetched from their own phone has a real cache
    sitting right there.  Without this, "no configuration is loaded" quietly means "the 630
    applications on the maintainer's phone", and every test that asserts an empty inventory
    fails on that one machine and passes everywhere else.  Found exactly that way, which is
    why this is autouse rather than something each fixture remembers to ask for.

    The module-level inventory state is reset for the same reason: it is global, and a test
    that fetches would otherwise leave its applications sitting in the next test's picker.
    """
    monkeypatch.setattr(deviceinv, "cache_path", lambda: str(tmp_path / "MapTasker_Apps.json"))
    monkeypatch.setattr(deviceinv, "_auth_keys", {})
    monkeypatch.setattr(deviceinv, "_device_apps", [])
    monkeypatch.setattr(deviceinv, "_cache_loaded", False)
    monkeypatch.setattr(deviceinv, "_harvested_from", deviceinv._NOT_HARVESTED)  # noqa: SLF001


def _load(xml_text: str) -> None:
    """Build the PrimeItems tables from XML text, the way taskerd does from a file.

    tasker_arg_specs matters as much here as it does in test_mapswap: it is the table that
    says arg_type '2' is an App and '4' an Icon, and without it every one of them reads as
    an unknown category and nothing is offered for editing at all.
    """
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100, "language": "English"}

    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file) as handle:
        specs = json.load(handle)
    # Both of proginit's own additions -- see its arg_specs load, and _ICON_CATEGORIES.
    specs[str(len(specs))] = "ConditionList"
    specs[str(len(specs))] = "Img"
    PrimeItems.tasker_arg_specs = specs

    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }
    tables["all_profiles_by_name"] = {
        profile["name"]: {"xml": profile["xml"], "id": key} for key, profile in tables["all_profiles"].items()
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items() if task["name"]
    }
    PrimeItems.tasker_root_elements = tables


@pytest.fixture
def loaded() -> None:
    """The fixture configuration, harvested."""
    _load(_FIXTURE_XML)


@pytest.fixture
def _nothing_loaded() -> None:
    """No configuration at all -- what the program starts up with, and what every App and
    Icon argument used to look like permanently.
    """
    PrimeItems.xml_root = None
    yield
    PrimeItems.xml_root = None


def _packages(entries: list[deviceinv.AppEntry]) -> list[str]:
    return [entry.pkg for entry in entries]


# ##################################################################################
# What the harvest finds.
# ##################################################################################
def test_apps_come_from_arguments_and_from_conditions(loaded: None) -> None:
    """Both spellings of an App reach the same list.

    The argument form and the condition form share not one tag name -- appPkg/appClass/
    label against pkg0/cls0/label0 -- so reading only one of them is an easy thing to do
    and leaves an inventory that looks plausible and is half empty.
    """
    found = _packages(deviceinv.apps())
    assert WHATSAPP in found  # <appPkg>, Task 20
    assert MAPS in found  # <pkg0>, Profile 100 -- and <appPkg> as well
    assert "com.docs" in found  # only ever named by an <Img>, Task 22


def test_the_most_complete_triple_wins(loaded: None) -> None:
    """WhatsApp is named twice: once with a label and class, once with no label.

    Picking it must give the complete triple whichever occurrence was met first, since an
    App written without a class is an App that Launch App cannot launch.
    """
    entry = deviceinv.resolve_app(WHATSAPP)
    assert entry.label == "WhatsApp"
    assert entry.cls == "com.whatsapp.Main"


def test_an_app_icon_contributes_its_launcher_class(loaded: None) -> None:
    """An <Img> naming an app is also a sighting of the app, and it carries the field that
    is hardest to come by anywhere else.
    """
    entry = deviceinv.resolve_app("com.docs")
    assert entry.cls == "com.docs.Main"


def test_variable_packages_sort_last(loaded: None) -> None:
    """'%' leads the alphabet, and a picker that opens on a screen of variables buries the
    apps it exists to offer.
    """
    found = _packages(deviceinv.apps())
    assert "%app_package" in found
    assert found[-1] == "%app_package"


def test_every_icon_form_is_recognised(loaded: None) -> None:
    """Built-in, icon pack, app icon, %variable -- all four, told apart by kind."""
    by_kind: dict[str, list[deviceinv.IconRef]] = {}
    for icon in deviceinv.icons():
        by_kind.setdefault(icon.kind, []).append(icon)

    assert {"builtin", "pack", "app", "var"} <= set(by_kind)
    assert "mw_action_language" in [icon.name for icon in by_kind["builtin"]]
    assert by_kind["pack"][0].pkg == CRYSTAL
    assert by_kind["app"][0].pkg == "com.docs"
    assert by_kind["var"][0].name == "%my_icon"


def test_an_empty_configuration_offers_nothing(_nothing_loaded: None) -> None:
    """No inventory is not an error -- it is the state every App and Icon argument was
    permanently in before this module existed, and the fields fall back to read-only.
    """
    assert deviceinv.apps() == []
    assert deviceinv.have_apps() is False
    assert deviceinv.have_icons() is False


# ##################################################################################
# Reading and writing the XML.
# ##################################################################################
def test_an_app_argument_unzips_into_triples(loaded: None) -> None:
    """Three parallel comma-joined lists, one app per position."""
    element = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"].find(".//App[@sr='arg0']")
    entries = deviceinv.read_app_element(element)
    assert _packages(entries) == [WHATSAPP, MAPS]
    assert entries[1].label == "Maps"
    assert entries[1].cls == "com.google.android.maps.MapsActivity"


def test_a_missing_label_list_reads_blank_rather_than_shifting(loaded: None) -> None:
    """Task 21's Kill App has an <appPkg> and an <appClass> and no <label> at all.

    The package list decides how many apps there are; a list the others run out of comes
    back blank.  Anything else would pair a package with the next app's label.
    """
    element = PrimeItems.tasker_root_elements["all_tasks"]["21"]["xml"].find(".//App[@sr='arg0']")
    entries = deviceinv.read_app_element(element)
    assert entries == [deviceinv.AppEntry(pkg=WHATSAPP, label="", cls="com.whatsapp.Main")]


def test_writing_fewer_apps_leaves_no_stale_list_behind(loaded: None) -> None:
    """Two apps down to one.  All three lists are rewritten every time, so the second
    label cannot survive to be re-paired with the first package on the next read.
    """
    element = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"].find(".//App[@sr='arg0']")
    deviceinv.write_app_element(element, [deviceinv.AppEntry(pkg=MAPS, label="Maps", cls="MapsActivity")])

    assert element.findtext("appPkg") == MAPS
    assert element.findtext("label") == "Maps"
    assert deviceinv.read_app_element(element) == [
        deviceinv.AppEntry(pkg=MAPS, label="Maps", cls="MapsActivity"),
    ]


def test_changing_an_icon_clears_the_previous_form_but_keeps_the_tint(loaded: None) -> None:
    """A built-in icon replaced by an app's, then by a built-in again.

    The <pkg> written for the app has to go when a built-in replaces it -- left behind, it
    reads back as an icon pack, which is a different icon that happens not to raise.  The
    <tint> is nobody's business but the user's and outlives every one of those changes.
    """
    element = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"].find(".//Img[@sr='arg2']")

    deviceinv.write_icon_element(element, deviceinv.IconRef(kind="app", pkg="com.docs", cls="com.docs.Main"))
    assert deviceinv.read_icon_element(element) == deviceinv.IconRef(
        kind="app",
        pkg="com.docs",
        cls="com.docs.Main",
    )

    deviceinv.write_icon_element(element, deviceinv.IconRef(kind="builtin", name="hd_action_call"))
    assert deviceinv.read_icon_element(element) == deviceinv.IconRef(kind="builtin", name="hd_action_call")
    assert element.findtext("pkg") is None
    assert element.findtext("tint") == "-1"


def test_an_empty_icon_is_a_reachable_state(loaded: None) -> None:
    """'No icon' is what an action whose icon was never set has always carried, so it has
    to stay reachable now that a picker exists.
    """
    element = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"].find(".//Img[@sr='arg2']")
    deviceinv.write_icon_element(element, deviceinv.parse_icon_value(""))
    assert deviceinv.read_icon_element(element) is None


# ##################################################################################
# What a single text field holds.
# ##################################################################################
@pytest.mark.parametrize(
    "icon",
    [
        deviceinv.IconRef(kind="builtin", name="mw_action_language"),
        deviceinv.IconRef(kind="pack", name="spreadsheet", pkg=CRYSTAL),
        deviceinv.IconRef(kind="app", pkg="com.docs", cls="com.docs.Main"),
        deviceinv.IconRef(kind="app", pkg="com.docs"),
        deviceinv.IconRef(kind="var", name="%my_icon"),
    ],
)
def test_an_icon_reference_survives_a_round_trip_through_a_text_field(icon: deviceinv.IconRef) -> None:
    """All four forms go into one field and come back out as themselves -- the field is
    what the user types into, so a form that cannot be spelled cannot be typed.
    """
    assert deviceinv.parse_icon_value(deviceinv.format_icon_value(icon)) == icon


def test_a_typed_package_keeps_its_own_text_and_gets_no_class(loaded: None) -> None:
    """The picker is a convenience over the field, not a gate in front of it.  A package
    the inventory has never heard of is still a working App -- Tasker matches on the
    package -- so it is accepted, labelled with itself, and given no class to invent.
    """
    entries = deviceinv.parse_app_value(f"{WHATSAPP}, com.nobody.knows")
    assert entries[0].cls == "com.whatsapp.Main"  # resolved from the inventory
    assert entries[1] == deviceinv.AppEntry(pkg="com.nobody.knows", label="com.nobody.knows", cls="")


# ##################################################################################
# What it unblocks.
# ##################################################################################
def test_launch_app_is_not_addable_without_an_inventory(_nothing_loaded: None) -> None:
    """With nothing to pick from, the refusal stands -- and says what is actually missing
    rather than the old blanket "this tool can't generate that kind of value".
    """
    addable, reason = taskedit.classify_action_addability(LAUNCH_APP)
    assert addable is False
    assert "Applications" in reason


def test_loading_a_configuration_makes_launch_app_addable(loaded: None) -> None:
    """The 22 entries app_icon_fetch_design.md counts, by way of three of them."""
    for key in (LAUNCH_APP, KILL_APP, NOTIFY):
        addable, reason = taskedit.classify_action_addability(key)
        assert addable is True, f"{key}: {reason}"


def test_the_addable_action_memo_follows_the_inventory(_nothing_loaded: None) -> None:
    """The trap list_addable_actions sets: it memoizes addability on the grounds that its
    inputs never change, and one of them now does.  Without the generation check, the Add
    Action picker goes on offering the answer it computed before a configuration existed.
    """
    before = {row["action_key"]: row["addable"] for row in taskedit.list_addable_actions()}
    assert before[LAUNCH_APP] is False
    assert before[FLASH] is True  # nothing to do with the inventory, addable throughout

    _load(_FIXTURE_XML)

    after = {row["action_key"]: row["addable"] for row in taskedit.list_addable_actions()}
    assert after[LAUNCH_APP] is True


def test_a_synthesized_launch_app_writes_the_xml_tasker_writes(loaded: None) -> None:
    """End to end: add the action, type two packages into its field, and read the result.

    The labels and classes are the assertion.  Nobody typed them -- they were re-attached
    from the inventory on the way to the XML, which is the whole reason harvesting is
    worth doing rather than just letting the field be typed into.
    """
    edited_task = taskedit.create_new_task("Opener2", "3")
    taskedit.add_action_to_task(edited_task, LAUNCH_APP)

    errors = taskedit.apply_edits_to_task(
        edited_task,
        "Opener2",
        "3",
        {taskedit.arg_key(0, "0"): f"{WHATSAPP}, {MAPS}"},
    )
    assert errors == []

    app_element = edited_task.task_element.find(".//App[@sr='arg0']")
    assert app_element.findtext("appPkg") == f"{WHATSAPP}, {MAPS}"
    assert app_element.findtext("appClass") == "com.whatsapp.Main, com.google.android.maps.MapsActivity"
    assert app_element.findtext("label") == "WhatsApp, Maps"


def test_a_synthesized_notify_writes_its_icon(loaded: None) -> None:
    """The Icon counterpart, and the one place the <Img> is built from nothing at all."""
    edited_task = taskedit.create_new_task("Noisy2", "3")
    taskedit.add_action_to_task(edited_task, NOTIFY)

    errors = taskedit.apply_edits_to_task(
        edited_task,
        "Noisy2",
        "3",
        {taskedit.arg_key(0, "2"): f"spreadsheet@{CRYSTAL}"},
    )
    assert errors == []

    img_element = edited_task.task_element.find(".//Img[@sr='arg2']")
    assert img_element.attrib["ve"] == "2"
    assert img_element.findtext("nme") == "spreadsheet"
    assert img_element.findtext("pkg") == CRYSTAL


def test_an_existing_action_offers_its_app_as_a_picker(loaded: None) -> None:
    """Edit Task's side of it: the argument that used to come back read-only now comes back
    as a field holding the packages it already names.
    """
    edited_task = taskedit.load_task_for_edit("Opener")
    launch_action = edited_task.actions[0]
    app_arg = launch_action.args[0]

    assert app_arg.widget_kind == "app_picker"
    assert app_arg.current_value == f"{WHATSAPP}, {MAPS}"


# ##################################################################################
# Fetching the list from the Android device.
#
# No device is involved.  maputil2 reaches the network through one module-level
# `requests`, so replacing it with a recorder both drives the exchange and asserts what was
# actually sent -- which is the part that matters here, since the order of these calls IS
# the design (see fetch_apps_from_device): a Task that is imported twice, or a result file
# read before the previous run's copy was deleted, are both failures that would look like
# success from inside.
#
# What this cannot test, and no test on this machine can, is whether Tasker's own
# 'List Apps' returns Package, App and Activity in the same order.  That is why
# parse_device_payload discards a mismatched list instead of zipping it, and why the
# mismatch case below is tested as carefully as the aligned one.
# ##################################################################################
GOOD_PAYLOAD = """MAPTASKER-APPS 1
PACKAGES
com.whatsapp|~|com.google.android.apps.maps
LABELS
WhatsApp|~|Maps
ACTIVITIES
com.whatsapp.Main|~|com.google.android.maps.MapsActivity
MAPTASKER-END
"""


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content

    def json(self) -> object:
        """maputil2._request_android_auth_key reads the auth reply through this."""
        return json.loads(self.content)


class _FakeRequests:
    """Stands in for maputil2's `requests`, recording every call and answering by URL."""

    def __init__(self, payload: str = GOOD_PAYLOAD, task_installed: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.payload = payload
        self.task_installed = task_installed
        self.imported_xml = ""

    def _record(self, verb: str, url: str) -> None:
        self.calls.append((verb, url))

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        self._record("GET", url)
        if "/api/auth" in url:
            return _FakeResponse(200, b'{"key": "TESTKEY", "authorized": true}')
        if "/api/tasks" in url:
            listed = [{"name": deviceinv.HELPER_TASK_NAME, "running": False}] if self.task_installed else []
            return _FakeResponse(200, json.dumps(listed).encode())
        if "maptasker_apps.txt" in url:
            if self.payload is None:
                return _FakeResponse(404)
            return _FakeResponse(200, self.payload.encode())
        return _FakeResponse(404)

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self._record("POST", url)
        if "/api/import" in url:
            self.imported_xml = kwargs.get("data", b"").decode()
            self.task_installed = True  # Tasker committed it, so the re-check now finds it.
        return _FakeResponse(200, b"{}")

    def delete(self, url: str, **_kwargs: object) -> _FakeResponse:
        self._record("DELETE", url)
        return _FakeResponse(404)  # Nothing there yet -- which http_delete_request calls success.


@pytest.fixture
def device(monkeypatch: pytest.MonkeyPatch) -> _FakeRequests:
    """A stand-in Android device, a cache file of its own, and no module state carried in
    from another test.
    """
    from maptasker.src import maputil2

    fake = _FakeRequests()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    _load(_FIXTURE_XML)
    return fake


def test_a_fetch_runs_the_whole_exchange_in_order(device: _FakeRequests) -> None:
    """Key, is-it-installed, import, is-it-installed-now, delete, run, read.

    The order is the design.  Deleting after running would read the file the run had just
    written and then throw it away; reading before deleting would believe a previous run's
    answer on a device where nothing ran at all.
    """
    return_code, message = deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    assert return_code == 0, message

    verbs_and_paths = [(verb, url.split("1821", 1)[1]) for verb, url in device.calls]
    assert verbs_and_paths[0] == ("GET", "/api/auth")
    assert verbs_and_paths[1][0] == "GET" and "/api/tasks?name=" in verbs_and_paths[1][1]
    assert verbs_and_paths[2] == ("POST", "/api/import")
    assert ("DELETE", "/api/file/Tasker/maptasker_apps.txt") in verbs_and_paths
    assert ("POST", "/api/tasks") in verbs_and_paths
    delete_at = verbs_and_paths.index(("DELETE", "/api/file/Tasker/maptasker_apps.txt"))
    run_at = verbs_and_paths.index(("POST", "/api/tasks"))
    # Matched on the verb too: the DELETE's own path ('/api/file/Tasker/...') contains the
    # GET's ('/file/Tasker/...') as a substring, so a path-only match finds the wrong call.
    read_at = next(i for i, (verb, path) in enumerate(verbs_and_paths) if verb == "GET" and "maptasker_apps" in path)
    assert delete_at < run_at < read_at


def test_an_already_installed_helper_task_is_not_imported_again(device: _FakeRequests) -> None:
    """Tasker's api/import adds a Task, it does not replace one of the same name.  A fetch
    that imported unconditionally would leave a growing pile of identical Tasks in the
    user's own configuration.
    """
    device.task_installed = True

    return_code, message = deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    assert return_code == 0, message
    assert not any("/api/import" in url for _verb, url in device.calls)


def _codes(xml_text: str) -> list[str]:
    """The action codes of a rendered Task, in order."""
    return [action.findtext("code") for action in ET.fromstring(xml_text).findall(".//Action")]  # noqa: S314


def test_the_helper_task_maptasker_installs_is_the_one_it_meant_to(device: _FakeRequests) -> None:
    """What actually goes onto the user's device, asserted as XML.

    It is built by taskedit's own Add-Task machinery rather than shipped as a blob (see
    build_helper_task), so this is also the proof that machinery produces what Tasker
    expects.  With PAIR_LABELS_ON_DEVICE on, that is: list the packages, walk them asking
    'Test App' for each one's name, then the activities in bulk, then write the file a line
    at a time with only the first write truncating.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")

    root = ET.fromstring(device.imported_xml)  # noqa: S314  (built by this program, above)
    actions = root.findall(".//Action")
    codes = [action.findtext("code") for action in actions]

    # Packages and activities in bulk; labels are no longer one of them -- that is the
    # whole point of the loop.
    list_types = [action.find("Int[@sr='arg0']").attrib["val"] for action in actions if action.findtext("code") == "815"]
    assert list_types == ["0", "2"]  # Package, Activity

    assert codes.count("39") == 1  # For
    assert codes.count("40") == 1  # End For
    assert codes.count("344") == 1  # Test App
    test_app = next(action for action in actions if action.findtext("code") == "344")
    assert test_app.find("Int[@sr='arg0']").attrib["val"] == "8"  # 'App Name'
    assert test_app.findtext("Str[@sr='arg1']") == "%mtapp"  # the package being asked about

    writes = [action for action in actions if action.findtext("code") == "410"]
    assert len(writes) == 8
    assert writes[0].find("Int[@sr='arg2']").attrib["val"] == "0"  # first write truncates
    assert all(write.find("Int[@sr='arg2']").attrib["val"] == "1" for write in writes[1:])  # rest append
    assert writes[0].findtext("Str[@sr='arg1']") == "MAPTASKER-APPS 1"
    assert writes[-1].findtext("Str[@sr='arg1']") == "MAPTASKER-END"


def test_the_loop_runs_before_the_packages_are_joined(device: _FakeRequests) -> None:
    """Order that is easy to get wrong and impossible to notice until a real device runs it.

    The 'For' iterates '%mtapps_pkg()' -- the ARRAY that 'List Apps' produced.  'Variable
    Join' collapses that array into one string, so joining first would leave the loop with
    nothing to walk and every label empty.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")

    codes = _codes(device.imported_xml)
    end_for = codes.index("40")
    first_join = codes.index("592")
    assert end_for < first_join


def test_backing_the_switch_out_restores_the_bulk_task(
    device: _FakeRequests,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAIR_LABELS_ON_DEVICE is meant to be revertible, so the reverted shape is tested too.

    Off, the Task goes back to three bulk 'List Apps' calls with no loop in it at all -- and
    to its v1 name, so the v2 Task left on the device is neither found nor used.
    """
    monkeypatch.setattr(deviceinv, "PAIR_LABELS_ON_DEVICE", False)
    built = deviceinv.build_helper_task()
    assert not isinstance(built, str), built

    codes = _codes(taskedit.render_standalone_task_xml(built))
    assert codes.count("815") == 3  # Package, App, Activity -- all in bulk
    assert "39" not in codes  # no For
    assert "344" not in codes  # no Test App

    assert deviceinv._HELPER_TASK_BULK != deviceinv._HELPER_TASK_PAIRED  # noqa: SLF001
    assert deviceinv.HELPER_TASK_NAME == deviceinv._HELPER_TASK_PAIRED  # noqa: SLF001


def test_fetched_apps_join_the_inventory_and_the_cache(device: _FakeRequests) -> None:
    """A fetch is only worth making if the picker is different afterwards."""
    before = {entry.pkg for entry in deviceinv.apps()}
    assert "com.google.android.apps.maps" in before  # harvested from the fixture

    return_code, _ = deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    assert return_code == 0

    assert deviceinv.fetched_devices()[0][0] == "192.168.0.210:1821"
    assert deviceinv.fetched_devices()[0][2] == 2
    assert json.loads(pathlib.Path(deviceinv.cache_path()).read_text())["devices"]


def test_the_harvest_wins_where_the_two_sources_disagree(device: _FakeRequests) -> None:
    """A fetched triple and a harvested one for the same package.

    The harvested one came out of a file Tasker itself wrote, so its label and class are
    exactly right; the fetched one's are whatever 'List Apps' happened to line up.  Where
    both have an answer, the harvest's is kept.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    entry = deviceinv.resolve_app(WHATSAPP)
    assert entry.label == "WhatsApp"
    assert entry.cls == "com.whatsapp.Main"


def test_a_fetch_replaces_that_devices_previous_answer(device: _FakeRequests) -> None:
    """Replaced, not merged: an app uninstalled since the last fetch must not live on in
    the list forever, and the device has just been asked what is actually installed.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    device.payload = "MAPTASKER-APPS 1\nPACKAGES\ncom.only.this.one\nMAPTASKER-END\n"
    device.task_installed = True
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")

    cached = json.loads(pathlib.Path(deviceinv.cache_path()).read_text())
    packages = [app["pkg"] for app in cached["devices"]["192.168.0.210:1821"]["apps"]]
    assert packages == ["com.only.this.one"]


def test_an_unfinished_file_is_not_read_as_a_complete_list(device: _FakeRequests) -> None:
    """The Task writes the file a line at a time, so it is readable long before it is
    finished.  Without the terminator check, a truncated app list would be cached as though
    it were the whole thing.
    """
    device.payload = "MAPTASKER-APPS 1\nPACKAGES\ncom.whatsapp"

    return_code, message = deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    assert return_code != 0
    assert "never finished" in message
    assert deviceinv.fetched_devices() == []


# ##################################################################################
# The payload, and the alignment question.
# ##################################################################################
def test_an_aligned_payload_gives_complete_triples() -> None:
    entries, error = deviceinv.parse_device_payload(GOOD_PAYLOAD)
    assert error == ""
    assert entries[0] == deviceinv.AppEntry(pkg=WHATSAPP, label="WhatsApp", cls="com.whatsapp.Main")


def test_a_mismatched_label_list_is_discarded_rather_than_zipped() -> None:
    """The open question this whole format is built around.

    If 'List Apps' does not return Package and App in the same order, zipping them labels
    every app with some other app's name -- and a wrong label looks right, so nobody would
    ever catch it.  Dropping the labels entirely leaves package names on screen, which are
    ugly and correct.  The activities alongside them are unaffected: each list is judged on
    its own length.
    """
    payload = GOOD_PAYLOAD.replace("WhatsApp|~|Maps", "WhatsApp")
    entries, error = deviceinv.parse_device_payload(payload)

    assert error == ""
    assert [entry.pkg for entry in entries] == [WHATSAPP, MAPS]
    assert [entry.label for entry in entries] == ["", ""]
    assert entries[0].cls == "com.whatsapp.Main"  # the aligned list still counts


def test_a_section_whose_variable_never_got_set_is_empty_not_an_app() -> None:
    """Tasker writes an unset %variable out as its own name, so a device with no activities
    to report writes the literal '%mtapps_cls' where the list should be.
    """
    payload = GOOD_PAYLOAD.replace(
        "com.whatsapp.Main|~|com.google.android.maps.MapsActivity",
        "%mtapps_cls",
    )
    entries, error = deviceinv.parse_device_payload(payload)
    assert error == ""
    assert [entry.cls for entry in entries] == ["", ""]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("something else entirely", "not a MapTasker application list"),
        ("MAPTASKER-APPS 1\nPACKAGES\ncom.whatsapp", "incomplete"),
        ("MAPTASKER-APPS 1\nPACKAGES\n\nMAPTASKER-END", "no applications"),
    ],
)
def test_a_payload_that_cannot_be_trusted_is_refused_with_a_reason(payload: str, expected: str) -> None:
    entries, error = deviceinv.parse_device_payload(payload)
    assert entries == []
    assert expected in error


# ##################################################################################
# The dead end: no Applications at all.
# ##################################################################################
# A configuration that names no Application anywhere -- so the harvest finds nothing, so
# 'Launch App' is not addable, so its Application picker never opens, so the picker's own
# 'App not listed?' button cannot be reached.  Fetching is the only way out of that, which
# is why the refusal is a named constant the GUI can recognise (guiwins
# ._render_addability_reason) rather than a sentence buried in a return.
_NO_APPS_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Task sr="task30">
    <id>30</id>
    <nme>Quiet</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">Hello</Str>
    </Action>
  </Task>
</TaskerData>
"""


@pytest.fixture
def no_apps_device(monkeypatch: pytest.MonkeyPatch) -> _FakeRequests:
    """The stand-in device again, but with a configuration that harvests no Applications."""
    from maptasker.src import maputil2

    fake = _FakeRequests()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    _load(_NO_APPS_XML)
    return fake


def test_the_refusal_the_gui_can_act_on_is_exactly_the_named_one(no_apps_device: _FakeRequests) -> None:
    """Compared by equality against taskedit.NO_APPS_REASON, not by looking for a word in
    it, so the two cannot drift apart without this failing.
    """
    assert deviceinv.apps() == []
    addable, reason = taskedit.classify_action_addability(LAUNCH_APP)
    assert addable is False
    assert reason == taskedit.NO_APPS_REASON


def test_a_fetch_opens_the_dead_end(no_apps_device: _FakeRequests) -> None:
    """The whole point of offering the fetch beside that refusal.

    With no Applications anywhere, 'Launch App' cannot be added, so its picker cannot be
    opened, so the picker's own fetch button cannot be reached.  A fetch from the refusal
    itself has to be enough to turn the row addable -- which it is only because the fetch
    moves deviceinv's generation and taskedit.list_addable_actions rebuilds on that.
    """
    rows = {row["action_key"]: row for row in taskedit.list_addable_actions()}
    assert rows[LAUNCH_APP]["addable"] is False
    assert rows[LAUNCH_APP]["reason"] == taskedit.NO_APPS_REASON

    return_code, message = deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    assert return_code == 0, message

    rows = {row["action_key"]: row for row in taskedit.list_addable_actions()}
    assert rows[LAUNCH_APP]["addable"] is True


def test_an_app_argument_with_nothing_to_offer_says_why(no_apps_device: _FakeRequests) -> None:
    """The read-only fallback carries the same sentence.

    It used to say "'App' arguments are not editable in this version", which stopped being
    true the moment this version made them editable -- the obstacle is an empty inventory,
    not the tool.
    """
    arg = next(a for a in taskedit.action_codes[LAUNCH_APP].args if a.arg_id == "0")
    element = ET.fromstring('<Action sr="act0"><App sr="arg0"/></Action>')  # noqa: S314
    editable = taskedit.build_editable_args(element, [arg])[0]

    assert editable.widget_kind == "readonly"
    assert editable.readonly_note == taskedit.NO_APPS_REASON


# ##################################################################################
# The other dead end: no icons at all.
# ##################################################################################
# Same shape as the Applications one above, and the same way out.  An app's own icon is a
# package plus a launcher activity, which is exactly what the Application fetch brings
# back, so asking the device for applications is also asking it for icons -- and the GUI
# offers that fetch wherever it shows NO_ICONS_REASON (guiwins._render_inventory_fetch).
# The other two icon kinds are not reachable this way and are not pretended to be.
def test_the_icon_refusal_is_a_named_one_too(no_apps_device: _FakeRequests) -> None:
    """The fixture that harvests no Applications harvests no icons either, so Notify --
    whose arg2 is an <Img> -- is refused for the icon reason, by equality.
    """
    assert deviceinv.icons() == []
    addable, reason = taskedit.classify_action_addability(NOTIFY)
    assert addable is False
    assert reason == taskedit.NO_ICONS_REASON


def test_a_fetch_opens_the_icon_dead_end(no_apps_device: _FakeRequests) -> None:
    """The whole point of offering the fetch beside that refusal.

    With no icons anywhere, Notify cannot be added, so its icon picker cannot be opened, so
    the picker's own fetch button cannot be reached.  The fetch has to be enough on its own
    to turn the row addable -- which it is, because every fetched application stands as an
    icon and the fetch moves deviceinv's generation.
    """
    rows = {row["action_key"]: row for row in taskedit.list_addable_actions()}
    assert rows[NOTIFY]["addable"] is False
    assert rows[NOTIFY]["reason"] == taskedit.NO_ICONS_REASON

    return_code, message = deviceinv.fetch_apps_from_device("192.168.0.210", "1821")
    assert return_code == 0, message

    rows = {row["action_key"]: row for row in taskedit.list_addable_actions()}
    assert rows[NOTIFY]["addable"] is True


def test_a_fetched_icon_is_the_app_icon_tasker_writes(no_apps_device: _FakeRequests) -> None:
    """What a fetch actually adds: one 'app' icon per installed application, carrying the
    package and the launcher activity, spelled the way a field holds one.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")

    icons = deviceinv.icons()
    assert {icon.kind for icon in icons} == {"app"}
    whatsapp = next(icon for icon in icons if icon.pkg == WHATSAPP)
    assert whatsapp.cls == "com.whatsapp.Main"
    assert deviceinv.format_icon_value(whatsapp) == f"app:{WHATSAPP}/com.whatsapp.Main"


def test_a_fetch_adds_no_icon_kind_it_cannot_know(no_apps_device: _FakeRequests) -> None:
    """The honest half of the offer.

    Tasker's built-in icon names live inside its own APK and an icon pack's contents are
    not enumerable remotely, so a fetch must not appear to supply either -- what it returns
    is applications, and only their own icons come of it.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")

    kinds = {icon.kind for icon in deviceinv.icons()}
    assert "builtin" not in kinds
    assert "pack" not in kinds


def test_the_harvest_wins_for_an_icon_both_sources_have(device: _FakeRequests) -> None:
    """The same precedence the Applications merge keeps, for the same reason: a harvested
    <Img> came out of a file Tasker itself wrote, so its <cls> is right, where a fetched
    launcher activity is whatever 'List Apps' reported.  One entry per package either way.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")

    whatsapp = [icon for icon in deviceinv.icons() if icon.kind == "app" and icon.pkg == WHATSAPP]
    assert len(whatsapp) == 1
    assert whatsapp[0].cls == "com.whatsapp.Main"


def test_fetched_icons_sort_after_the_ones_already_in_use(device: _FakeRequests) -> None:
    """A fetch can add hundreds of app icons at once.  Built-ins and pack icons -- the ones
    this configuration actually uses -- have to stay at the top of the picker rather than
    being pushed under them.
    """
    deviceinv.fetch_apps_from_device("192.168.0.210", "1821")

    kinds = [icon.kind for icon in deviceinv.icons()]
    assert kinds == sorted(kinds, key={"builtin": 0, "pack": 1, "app": 2, "var": 3}.get)


def test_an_icon_argument_stops_being_read_only_once_the_icons_arrive(
    no_apps_device: _FakeRequests,
) -> None:
    """What the GUI leans on to redraw a greyed-out field in place.

    An argument's widget kind is decided when its model is built, so a field built before
    the fetch goes on saying 'No icons were found...' however many times it is redrawn.
    reclassify_action_args re-asks the question -- which is the whole reason the fetch can
    be offered beside that message instead of only inside a picker it cannot open.
    """
    action_xml = '<Action sr="act0" ve="7"><code>523</code><Img sr="arg2" ve="2"/></Action>'
    action = taskedit._build_editable_action(ET.fromstring(action_xml), 0)  # noqa: S314, SLF001
    icon_arg = next(arg for arg in action.args if arg.arg_id == "2")
    assert icon_arg.widget_kind == "readonly"
    assert icon_arg.readonly_note == taskedit.NO_ICONS_REASON

    assert deviceinv.fetch_apps_from_device("192.168.0.210", "1821")[0] == 0
    taskedit.reclassify_action_args(action)

    icon_arg = next(arg for arg in action.args if arg.arg_id == "2")
    assert icon_arg.widget_kind == "icon_picker"
    assert not icon_arg.readonly_note


def test_a_paired_label_line_survives_its_trailing_joiner() -> None:
    """The append loop's signature, and the one thing about it that could shift every label.

    Tasker has no 'join with a separator between' in an append, so each label goes on with
    the joiner after it and the line ends with one.  Split naively that is an extra empty
    entry, the label count no longer matches the package count, and parse_device_payload
    would discard every name the loop just spent a few hundred iterations collecting.
    """
    payload = (
        "MAPTASKER-APPS 1\n"
        "PACKAGES\n"
        "com.whatsapp|~|com.google.android.apps.maps\n"
        "LABELS\n"
        "WhatsApp|~|Maps|~|\n"  # <- the loop's trailing joiner
        "MAPTASKER-END\n"
    )
    entries, error = deviceinv.parse_device_payload(payload)

    assert error == ""
    assert [entry.label for entry in entries] == ["WhatsApp", "Maps"]


def test_only_one_trailing_blank_is_forgiven() -> None:
    """A blank anywhere else is a real position and has to stay one.

    An app the device reported no name for is an empty string in the middle of the line, and
    dropping it would move every label after it onto the wrong package -- the exact failure
    the length check exists to prevent.
    """
    payload = (
        "MAPTASKER-APPS 1\n"
        "PACKAGES\n"
        "com.a|~|com.b|~|com.c\n"
        "LABELS\n"
        "Alpha|~||~|Gamma|~|\n"  # middle one blank, plus the loop's trailing joiner
        "MAPTASKER-END\n"
    )
    entries, error = deviceinv.parse_device_payload(payload)

    assert error == ""
    assert [(entry.pkg, entry.label) for entry in entries] == [
        ("com.a", "Alpha"),
        ("com.b", ""),
        ("com.c", "Gamma"),
    ]


# ##################################################################################
# A package that is a variable rather than an application.
# ##################################################################################
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("%app_package", True),
        ("%App(%par1)", True),  # a function call -- real, from this repo's own backup
        ("%app_package(%ld_selected_index)", True),  # an array index -- likewise
        ("  %spaced  ", True),
        ("%", False),  # the prefix alone names nothing
        (" % ", False),
        ("", False),
        ("com.whatsapp", False),
    ],
)
def test_what_counts_as_a_variable(text: str, expected: bool) -> None:
    """A leading '%' and something after it, and nothing stricter.

    A variable-name pattern would reject '%App(%par1)', which Tasker itself writes into
    <appPkg>.  What follows the '%' is Tasker's business.
    """
    assert deviceinv.is_variable_reference(text) is expected


def test_a_variable_entry_matches_what_tasker_writes(loaded: None) -> None:
    """Package and label both the variable, class empty.

    Not invented -- every variable-valued <App> in this repo's backup repeats the <appPkg>
    text in <label> and carries no <appClass>.
    """
    assert deviceinv.variable_app_entry(" %LastMusicApp ") == deviceinv.AppEntry(
        pkg="%LastMusicApp",
        label="%LastMusicApp",
        cls="",
    )


def test_a_variable_reaches_the_xml_through_the_ordinary_field(loaded: None) -> None:
    """The picker writes into the field, so a variable has to survive the same trip a typed
    package does -- parsed back out of the field, resolved, and written to <App>.
    """
    element = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"].find(".//App[@sr='arg0']")
    deviceinv.write_app_element(element, deviceinv.parse_app_value("%app_package"))

    assert element.findtext("appPkg") == "%app_package"
    assert element.findtext("label") == "%app_package"
    assert element.findtext("appClass") == ""


def test_a_variable_and_real_packages_can_share_one_argument(loaded: None) -> None:
    """An <App> argument names a list, and nothing says every entry has to be the same kind
    of thing -- so the variable has to keep its position among them.
    """
    entries = deviceinv.parse_app_value(f"{WHATSAPP}, %app_package, {MAPS}")

    assert [entry.pkg for entry in entries] == [WHATSAPP, "%app_package", MAPS]
    assert entries[1].label == "%app_package"
    assert entries[1].cls == ""
    assert entries[0].cls == "com.whatsapp.Main"  # the real ones still resolve


# ##################################################################################
# Listing the device's XML files.
#
# This replaced a GET on the 'maplist' route -- a route served not by the HTTP Server
# Example project but by a separate 'MapTasker List' Profile the user had to import from
# TaskerNet by hand and keep enabled.  Tasker's HTTP API can import a Task and nothing
# else (POST /api/import), so the Profile could never have been installed automatically;
# a Task doing the same job can be, and is.
#
# The same fake-device approach as the Applications fetch above, and for the same reason:
# the ORDER of the exchange is the design.  A device is never involved.
# ##################################################################################
GOOD_FILE_PAYLOAD = """MAPTASKER-FILES 1
FILES
/storage/emulated/0/Tasker/configs/user/backup.xml|~|/storage/emulated/0/Tasker/Home.prj.xml
MAPTASKER-END
"""


class _FakeFileListRequests:
    """maputil2's `requests`, answering for a device that has no listing Task on it yet."""

    def __init__(self, payload: str | None = GOOD_FILE_PAYLOAD, task_installed: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.payload = payload
        self.task_installed = task_installed
        self.imported_xml = ""

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        self.calls.append(("GET", url))
        if "/api/auth" in url:
            return _FakeResponse(200, b'{"key": "TESTKEY", "authorized": true}')
        if "/api/tasks" in url:
            listed = [{"name": deviceinv.FILE_LIST_TASK_NAME, "running": False}] if self.task_installed else []
            return _FakeResponse(200, json.dumps(listed).encode())
        if "maptasker_files.txt" in url:
            if self.payload is None:
                return _FakeResponse(404)
            return _FakeResponse(200, self.payload.encode())
        return _FakeResponse(404)

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append(("POST", url))
        if "/api/import" in url:
            self.imported_xml = kwargs.get("data", b"").decode()
            self.task_installed = True
        return _FakeResponse(200, b"{}")

    def delete(self, url: str, **_kwargs: object) -> _FakeResponse:
        self.calls.append(("DELETE", url))
        return _FakeResponse(404)


@pytest.fixture
def file_list_device(monkeypatch: pytest.MonkeyPatch) -> _FakeFileListRequests:
    """A stand-in device with a loaded configuration -- Add Task needs one for the id."""
    from maptasker.src import maputil2

    fake = _FakeFileListRequests()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)
    return fake


def test_a_file_list_fetch_runs_the_whole_exchange_in_order(file_list_device: _FakeFileListRequests) -> None:
    """Key, is-it-installed, import, is-it-installed-now, delete, run, read.

    Deleting after running would throw away the answer the run had just written; reading
    before deleting would believe the PREVIOUS listing on a device where nothing ran --
    and unlike the app list, a file list is asked for over and over in one session, so a
    stale file is the normal case rather than the rare one.
    """
    return_code, result = deviceinv.fetch_file_list_from_device("192.168.0.210", "1821")
    assert return_code == 0, result

    verbs_and_paths = [(verb, url.split("1821", 1)[1]) for verb, url in file_list_device.calls]
    assert verbs_and_paths[0] == ("GET", "/api/auth")
    assert verbs_and_paths[1][0] == "GET" and "/api/tasks?name=" in verbs_and_paths[1][1]
    assert verbs_and_paths[2] == ("POST", "/api/import")
    assert verbs_and_paths[3][0] == "GET" and "/api/tasks?name=" in verbs_and_paths[3][1]
    assert verbs_and_paths[4][0] == "DELETE"
    assert "maptasker_files.txt" in verbs_and_paths[4][1]
    assert verbs_and_paths[5] == ("POST", "/api/tasks")
    assert verbs_and_paths[6][0] == "GET" and "maptasker_files.txt" in verbs_and_paths[6][1]


def test_a_fetch_returns_the_paths_the_device_reported(file_list_device: _FakeFileListRequests) -> None:
    """Exactly as Tasker spelled them -- it is the caller that decides how it wants them."""
    return_code, result = deviceinv.fetch_file_list_from_device("192.168.0.210", "1821")

    assert return_code == 0
    assert result == [
        "/storage/emulated/0/Tasker/configs/user/backup.xml",
        "/storage/emulated/0/Tasker/Home.prj.xml",
    ]


def test_the_listing_task_is_not_imported_twice(file_list_device: _FakeFileListRequests) -> None:
    """api/import ADDS a Task of the same name rather than replacing it, so a fetch that
    imported unconditionally would leave a growing pile of identical Tasks behind."""
    file_list_device.task_installed = True
    deviceinv.fetch_file_list_from_device("192.168.0.210", "1821")

    assert not any(verb == "POST" and "/api/import" in url for verb, url in file_list_device.calls)


def test_the_imported_task_lists_xml_under_the_tasker_directory(file_list_device: _FakeFileListRequests) -> None:
    """What actually goes to the device.  'List Files' has to recurse -- the XML lives in
    Tasker's subdirectories, not in the directory named -- and has to filter to XML, or
    the pulldown fills with every file on the device."""
    deviceinv.fetch_file_list_from_device("192.168.0.210", "1821")

    imported = ET.fromstring(file_list_device.imported_xml)  # noqa: S314  (built by this program)
    list_files = imported.find(".//Action[code='446']")
    assert list_files is not None
    assert list_files.findtext("Str[@sr='arg1']") == deviceinv.FILE_LIST_DIRECTORY
    assert list_files.findtext("Str[@sr='arg2']") == "Files"
    assert list_files.findtext("Str[@sr='arg3']") == "*xml"
    assert list_files.find("Int[@sr='arg5']").get("val") == "1"  # Recurse


def test_the_imported_task_writes_a_payload_this_can_read_back(
    file_list_device: _FakeFileListRequests,
) -> None:
    """The Task and the parser are two halves of one format.  The first write truncates and
    the rest append, so a re-run replaces the previous answer rather than growing it -- and
    the terminator is written last, which is what makes the poll's 'is it finished' check
    mean anything."""
    deviceinv.fetch_file_list_from_device("192.168.0.210", "1821")

    imported = ET.fromstring(file_list_device.imported_xml)  # noqa: S314
    writes = imported.findall(".//Action[code='410']")
    assert [write.findtext("Str[@sr='arg1']") for write in writes] == [
        "MAPTASKER-FILES 1",
        "FILES",
        "%lfp_full_path",
        "MAPTASKER-END",
    ]
    assert [write.find("Int[@sr='arg2']").get("val") for write in writes] == ["0", "1", "1", "1"]


def test_a_device_that_never_writes_the_file_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Task that runs but produces nothing must not read as an empty configuration."""
    from maptasker.src import maputil2

    fake = _FakeFileListRequests(payload=None)
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = deviceinv.fetch_file_list_from_device("192.168.0.210", "1821")

    assert return_code != 0
    assert "file list" in message


def test_a_payload_from_the_other_helper_task_is_refused() -> None:
    """Both helpers write a MAPTASKER-* file with the same terminator.  Reading one as the
    other would be a silent misparse, which is why the headers differ."""
    paths, error = deviceinv.parse_file_list_payload(GOOD_PAYLOAD)

    assert paths == []
    assert error


def test_an_unfinished_payload_is_refused() -> None:
    """No terminator means the Task was still writing -- a truncated list, not a short one."""
    paths, error = deviceinv.parse_file_list_payload("MAPTASKER-FILES 1\nFILES\n/Tasker/a.xml\n")

    assert paths == []
    assert "incomplete" in error


def test_a_listing_that_found_nothing_reads_as_nothing() -> None:
    """Tasker writes an unset variable out as its own name, so an empty listing arrives as
    the literal '%lfp_full_path' -- which must not become a file by that name."""
    paths, error = deviceinv.parse_file_list_payload(
        "MAPTASKER-FILES 1\nFILES\n%lfp_full_path\nMAPTASKER-END\n",
    )

    assert paths == []
    assert "No XML files" in error


# ##################################################################################
# The GUI's own layer on top of the fetch (guiutils.get_list_of_files).
#
# Two jobs, both of which used to be tangled up with the old route's payload format: the
# paths have to lose the storage-root prefix before the 'file' route can fetch them, and
# Tasker's trash has to be kept out of the pulldown.  What is gone is the third job --
# chopping three characters off the end of every entry to strip a file count the old
# 'maplist' route glued on, and splitting on a comma that can appear in a file name.
# ##################################################################################


@pytest.fixture
def listed_files(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    """Lets a test say what the device reported, without a device or a fetch."""
    from maptasker.src import guiutils

    def _set(return_code: int, result: object) -> None:
        monkeypatch.setattr(
            guiutils.deviceinv,
            "fetch_file_list_from_device",
            lambda *_args, **_kwargs: (return_code, result),
        )

    return _set


def test_the_storage_root_is_stripped_off_every_path(listed_files) -> None:  # noqa: ANN001
    """The 'file' route is rooted at the storage root, so a path that still carries it
    cannot be fetched -- see deviceinv's own note on the two spellings."""
    from maptasker.src.guiutils import get_list_of_files

    listed_files(0, ["/storage/emulated/0/Tasker/configs/user/backup.xml"])

    assert get_list_of_files("1.2.3.4", "1821", "/storage/emulated/0/Tasker") == (
        0,
        ["/Tasker/configs/user/backup.xml"],
    )


def test_trashed_files_are_kept_out_of_the_list(listed_files) -> None:  # noqa: ANN001
    """Tasker's own trash is full of XML nobody wants offered as a configuration."""
    from maptasker.src.guiutils import get_list_of_files

    listed_files(
        0,
        [
            "/storage/emulated/0/Tasker/.Trash/old.xml",
            "/storage/emulated/0/Tasker/configs/user/backup.xml",
        ],
    )

    assert get_list_of_files("1.2.3.4", "1821", "/storage/emulated/0/Tasker") == (
        0,
        ["/Tasker/configs/user/backup.xml"],
    )


def test_a_name_with_a_comma_in_it_survives(listed_files) -> None:  # noqa: ANN001
    """The old route joined its paths with commas, so this file arrived as two.  Nothing
    splits on a comma any more, and a Tasker export named after a Project can easily have
    one in it ('Bonza, Jigsaw.prj.xml')."""
    from maptasker.src.guiutils import get_list_of_files

    listed_files(0, ["/storage/emulated/0/Tasker/Bonza, Jigsaw.prj.xml"])

    assert get_list_of_files("1.2.3.4", "1821", "/storage/emulated/0/Tasker") == (
        0,
        ["/Tasker/Bonza, Jigsaw.prj.xml"],
    )


def test_a_fetch_failure_is_passed_straight_through(listed_files) -> None:  # noqa: ANN001
    """The caller shows this message to the user, so it must be the fetch's own account of
    what went wrong rather than a generic one invented here."""
    from maptasker.src.guiutils import get_list_of_files

    listed_files(8, "Tasker did not report the Task afterwards.")

    assert get_list_of_files("1.2.3.4", "1821", "/storage/emulated/0/Tasker") == (
        8,
        "Tasker did not report the Task afterwards.",
    )


def test_a_listing_of_nothing_but_trash_is_an_error(listed_files) -> None:  # noqa: ANN001
    """An empty pulldown with a green 'success' behind it tells the user nothing."""
    from maptasker.src.guiutils import get_list_of_files

    listed_files(0, ["/storage/emulated/0/Tasker/.Trash/old.xml"])

    return_code, message = get_list_of_files("1.2.3.4", "1821", "/storage/emulated/0/Tasker")

    assert return_code != 0
    assert "trashed" in message


# ##################################################################################
# Importing a Profile into Tasker's live configuration
#
# The endpoint everything else here leans on, POST /api/import, takes a Task and nothing
# else -- so a Profile is put in by running a helper Task built around Tasker's own
# 'Import Data' action, which is the very action the shipped api/import Task uses (see
# deviceinv's section comment).
#
# What these assert is the part that can be settled without a device: the shape of the Task
# that gets installed, and the order and the refusals of the exchange around it.  What they
# CANNOT settle is what Tasker does with a 'Configuration' import -- that needs a real
# device with an expendable configuration, and it is why import_profile_to_device refuses
# to do anything at all unless the caller says out loud that it accepts the answer.
# ##################################################################################
GOOD_IMPORT_PAYLOAD = """MAPTASKER-IMPORT 1
STAGED
/storage/emulated/0/Tasker/profiles/Watched.prf.xml
MAPTASKER-END
"""

_STAGED_PROFILE_XML = b'<TaskerData sr="" dvi="1" tv="6.3.13"><Profile sr="prof1"><nme>Watched</nme></Profile></TaskerData>'


class _FakeImportRequests:
    """maputil2's `requests`, for a device with neither the helper Task nor the Profile."""

    def __init__(
        self,
        payload: str | None = GOOD_IMPORT_PAYLOAD,
        task_installed: bool = False,
        profiles_after: set[str] | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self.payload = payload
        self.installed_tasks: set[str] = {deviceinv.IMPORT_PROFILE_TASK_NAME} if task_installed else set()
        # Which Profiles Tasker reports once the helper has run.  An empty set is the case
        # worth having: the Task ran to completion and Tasker still reports nothing new.
        self.profiles_after = {"Watched"} if profiles_after is None else profiles_after
        self.installed_profiles: set[str] = set()
        self.imported_xml = ""
        self.uploaded: bytes = b""
        self.uploaded_filename = ""
        self.task_ran = False
        # The JSON bodies POST /api/tasks was called with.  The helper Task is told which
        # file to work on through this -- 'par1' -- so what is in here is the difference
        # between an import of one Profile and an import of whatever was staged last.
        self.run_bodies: list[dict] = []
        # Which helper's answer file this device is serving.  The two Profile routes write
        # to different paths on purpose (see test_the_two_routes_do_not_share_an_answer_file),
        # so the fake has to be told which one it is standing in for.
        self.result_filename = "maptasker_import.txt"

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        self.calls.append(("GET", url))
        if "/api/auth" in url:
            return _FakeResponse(200, b'{"key": "TESTKEY", "authorized": true}')
        if "/api/tasks" in url:
            # Answers for the name actually asked about, not for a single hard-coded one:
            # which Task is installed is the point of _import_task_name.
            wanted = unquote(url.split("name=", 1)[1]) if "name=" in url else ""
            listed = [{"name": wanted, "running": False}] if wanted in self.installed_tasks else []
            return _FakeResponse(200, json.dumps(listed).encode())
        if "/api/profiles" in url:
            # 'name' is documented as repeatable and the real caller sends it that way, so
            # the fake has to answer for the whole list rather than one hard-coded name --
            # that is how a Project import is confirmed at all.
            query = url.split("?", 1)[1] if "?" in url else ""
            wanted = [unquote(part.split("=", 1)[1]) for part in query.split("&") if part.startswith("name=")]
            listed = [
                {"name": name, "enabled": True, "active": False}
                for name in wanted
                if name in self.installed_profiles
            ]
            return _FakeResponse(200, json.dumps(listed).encode())
        # Every kind whose upload gets read back, '.scn.xml' included: a Scene is not staged
        # for an intent any more, but sceneedit.save_scene_to_android verifies its own write
        # the same way, and a double that 404s that read cannot tell a good write from a bad.
        if any(url.endswith(kind) or f"{kind}?" in url for kind in (".prf.xml", ".prj.xml", ".scn.xml")):
            return _FakeResponse(200, self.uploaded) if self.uploaded else _FakeResponse(404)
        if self.result_filename in url:
            if self.payload is None or not self.task_ran:
                return _FakeResponse(404)
            return _FakeResponse(200, self.payload.encode())
        return _FakeResponse(404)

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append(("POST", url))
        if "/api/import" in url:
            self.imported_xml = kwargs.get("data", b"").decode()
            self.installed_tasks.add(ET.fromstring(self.imported_xml).findtext(".//Task/nme"))  # noqa: S314
        elif "/upload" in url:
            files = kwargs.get("files", {})
            self.uploaded_filename = next(iter(files))
            self.uploaded = next(iter(files.values()))[1]
        elif "/api/tasks" in url:
            self.run_bodies.append(json.loads(kwargs.get("data", b"{}").decode()))
            self.task_ran = True
            # Standing in for the helper Task's own run: it imports, then writes its file.
            self.installed_profiles |= self.profiles_after
        return _FakeResponse(200, b"{}")

    def delete(self, url: str, **_kwargs: object) -> _FakeResponse:
        self.calls.append(("DELETE", url))
        return _FakeResponse(404)


@pytest.fixture
def import_device(monkeypatch: pytest.MonkeyPatch) -> _FakeImportRequests:
    """A stand-in device with a loaded configuration -- Add Task needs one for the id."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)
    return fake


def _import(device: _FakeImportRequests, **kwargs: object) -> tuple[int, str]:
    """The call under test, with the risk acknowledged -- see import_profile_to_device."""
    return deviceinv.import_profile_to_device(
        _STAGED_PROFILE_XML,
        "Watched",
        "192.168.0.210",
        "1821",
        acknowledged_risk=True,
        **kwargs,
    )


def test_an_import_that_is_not_acknowledged_never_touches_the_device(
    import_device: _FakeImportRequests,
) -> None:
    """The gate is the point of the gate: a caller that has not said it accepts an import
    whose effect on the rest of the configuration is unestablished gets nothing sent at
    all -- not an auth prompt on the device, not a Task installed, nothing."""
    return_code, message = deviceinv.import_profile_to_device(
        _STAGED_PROFILE_XML,
        "Watched",
        "192.168.0.210",
        "1821",
    )

    assert return_code != 0
    assert "acknowledged_risk" in message
    assert import_device.calls == []


def test_an_import_runs_the_whole_exchange_in_order(import_device: _FakeImportRequests) -> None:
    """Key, is-the-Profile-already-there, is-the-Task-installed, install it, upload, read
    the upload back, run, read the answer, ask Tasker for the Profile.

    The two readings at the ends are what make this worth anything.  The first is a refusal
    to duplicate; the last is the only confirmation available -- unlike a Task import there
    is no second endpoint to fall back on, and a run request's own 200 says only that the
    Task was started.
    """
    return_code, message = _import(import_device)
    assert return_code == 0, message

    verbs_and_paths = [(verb, url.split("1821", 1)[1]) for verb, url in import_device.calls]
    assert verbs_and_paths[0] == ("GET", "/api/auth")
    assert verbs_and_paths[1][0] == "GET" and "/api/profiles?name=" in verbs_and_paths[1][1]
    assert ("POST", "/api/import") in verbs_and_paths  # the helper Task being installed

    upload_at = verbs_and_paths.index(("POST", "/upload"))
    run_at = verbs_and_paths.index(("POST", "/api/tasks"))
    read_back_at = next(
        i for i, (verb, path) in enumerate(verbs_and_paths) if verb == "GET" and "Watched.prf.xml" in path
    )
    answer_at = next(
        i for i, (verb, path) in enumerate(verbs_and_paths) if verb == "GET" and "maptasker_import.txt" in path
    )
    # Read the upload back BEFORE running: /upload answers 200 whatever it wrote, so a
    # half-written .prf.xml would otherwise be imported rather than reported.
    assert upload_at < read_back_at < run_at < answer_at
    assert verbs_and_paths[-1][0] == "GET" and "/api/profiles?name=" in verbs_and_paths[-1][1]

    assert import_device.uploaded == _STAGED_PROFILE_XML
    assert "Watched" in message


def test_a_staged_profile_still_settling_is_read_back_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """The upload and the read-back are two unrelated Tasker Tasks, so a read that arrives
    too soon answers 404 about a file that is on the device a moment later.

    This route used to make ONE un-retried GET and report a write that never landed --
    failing an import over the timing rather than over anything wrong with it.  It goes
    through maputil2.read_back_uploaded_file now, the way every other upload in this program
    already did.
    """
    from maptasker.src import maputil2

    class _SlowToSettle(_FakeImportRequests):
        """Answers the first read of the staged file with a 404, then behaves."""

        def __init__(self) -> None:
            super().__init__()
            self.stage_misses = 0

        def get(self, url: str, **kwargs: object) -> _FakeResponse:
            if self.uploaded and ".prf.xml" in url and self.stage_misses == 0:
                self.stage_misses += 1
                self.calls.append(("GET", url))
                return _FakeResponse(404)
            return super().get(url, **kwargs)

    fake = _SlowToSettle()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)  # the read-back settle
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _import(fake)

    assert return_code == 0, message
    assert fake.stage_misses == 1  # the miss happened; the retry after it is what saved this


def test_a_staged_profile_that_never_lands_still_stops_the_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retrying is not believing: bytes that never match end as a failure, and nothing is
    handed to 'Import Data' -- importing an in-memory render at that point would be importing
    something other than the file this says it imports."""
    from maptasker.src import maputil2

    class _NeverLands(_FakeImportRequests):
        """Answers every read of the staged file with something other than what was sent --
        a device still holding the previous version of that path looks exactly like this."""

        def get(self, url: str, **kwargs: object) -> _FakeResponse:
            if self.uploaded and ".prf.xml" in url:
                self.calls.append(("GET", url))
                return _FakeResponse(200, b"<TaskerData>something else</TaskerData>")
            return super().get(url, **kwargs)

    fake = _NeverLands()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _import(fake)

    assert return_code != 0
    assert "could not confirm it landed correctly" in message
    assert not any(verb == "POST" and "/api/tasks" in url for verb, url in fake.calls)


def test_the_import_task_hands_the_staged_xml_to_import_data(import_device: _FakeImportRequests) -> None:
    """What actually goes onto the user's device, asserted as XML.

    'Read File' into a variable, then 'Import Data' (code 153) with Type=1 -- Configuration,
    the option api/import does not use -- taking that same variable.  Type is the argument
    the whole idea rests on: 0 there would import the Profile XML as a Task.
    """
    _import(import_device)

    imported = ET.fromstring(import_device.imported_xml)  # noqa: S314  (built by this program)
    read_file = imported.find(".//Action[code='417']")
    assert read_file is not None
    # %par1, not a path: one installed Task, told which file at run time -- see below.
    assert read_file.findtext("Str[@sr='arg0']") == "%par1"
    assert read_file.findtext("Str[@sr='arg1']") == "%mtimport_xml"
    assert read_file.find("Int[@sr='arg2']").get("val") == "0"  # verbatim, not structured

    import_data = imported.find(".//Action[code='153']")
    assert import_data is not None
    assert import_data.find("Int[@sr='arg0']").get("val") == "1"  # Configuration
    assert import_data.find("Int[@sr='arg1']").get("val") == "0"  # Source, as api/import sends
    assert import_data.findtext("Str[@sr='arg2']") == "%mtimport_xml"


def test_the_import_run_names_the_file_it_is_about(import_device: _FakeImportRequests) -> None:
    """The prototype stages under the Profile's own name too, and tells the helper which file
    through par1 -- the same mechanism the offer routes use.  A fixed 'maptasker_import.prf.xml'
    in the folder the user browses was the reported complaint; it was in both routes."""
    return_code, message = _import(import_device)
    assert return_code == 0, message

    assert import_device.uploaded_filename == "Watched.prf.xml"
    assert import_device.run_bodies[-1]["par1"] == "/storage/emulated/0/Tasker/profiles/Watched.prf.xml"


def test_the_import_task_reports_only_after_it_has_imported(import_device: _FakeImportRequests) -> None:
    """The order that makes the answer file mean something.

    'Import Data' can fail (action_codes["153t"].canfail), and a failed action stops the
    Task -- so every 'Write File' has to come after it.  Written the other way round the
    terminator would land whether or not anything was imported, and the poll would report a
    success that never happened.
    """
    _import(import_device)

    codes = _codes(import_device.imported_xml)
    assert codes.index("153") < codes.index("410")

    imported = ET.fromstring(import_device.imported_xml)  # noqa: S314
    writes = imported.findall(".//Action[code='410']")
    assert [write.findtext("Str[@sr='arg1']") for write in writes][0] == "MAPTASKER-IMPORT 1"
    assert [write.findtext("Str[@sr='arg1']") for write in writes][-1] == "MAPTASKER-END"
    assert [write.find("Int[@sr='arg2']").get("val") for write in writes] == ["0", "1", "1", "1"]


def test_a_profile_tasker_already_has_is_refused(import_device: _FakeImportRequests) -> None:
    """api/import ADDS a Task whose name is taken rather than replacing it.  If a
    Configuration import behaves the same, importing over an existing Profile leaves two --
    so the name is checked before anything is uploaded or run."""
    import_device.installed_profiles = {"Watched"}

    return_code, message = _import(import_device)

    assert return_code == deviceinv.DUPLICATE_PROFILE_CODE
    assert "already has a Profile" in message
    assert not any("/upload" in url for _verb, url in import_device.calls)
    assert not any(verb == "POST" and "/api/tasks" in url for verb, url in import_device.calls)


def test_allow_existing_gets_past_that(import_device: _FakeImportRequests) -> None:
    """The refusal is a default, not a policy -- once the device's behaviour is known, the
    caller can say so."""
    import_device.installed_profiles = {"Watched"}

    return_code, message = _import(import_device, allow_existing=True)

    assert return_code == 0, message
    assert any("/upload" in url for _verb, url in import_device.calls)


def test_the_import_task_is_not_installed_twice(import_device: _FakeImportRequests) -> None:
    """Same reason as every other helper: api/import adds rather than replaces, so a second
    import would leave a second identical Task behind."""
    import_device.installed_tasks.add(deviceinv.IMPORT_PROFILE_TASK_NAME)

    return_code, message = _import(import_device)

    assert return_code == 0, message
    assert not any(verb == "POST" and "/api/import" in url for verb, url in import_device.calls)


def test_a_task_that_writes_nothing_reads_as_a_refused_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """No answer file means 'Import Data' failed and stopped the Task.  Nothing was
    imported, and that is the one thing the message has to say."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=None)
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _import(fake)

    assert return_code != 0
    assert "Import Data" in message


def test_an_import_tasker_does_not_confirm_is_not_a_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper got past 'Import Data' without failing and Tasker still reports no such
    Profile.  Reporting that as success is the failure this whole exchange is built to
    avoid -- the user would go looking for a Profile that is not there."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(profiles_after=set())
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _import(fake)

    assert return_code != 0
    assert "does not report a Profile" in message


def test_an_unknown_import_type_is_refused_rather_than_defaulted(import_device: _FakeImportRequests) -> None:
    """apply_arg_values resolves a dropdown by label and falls back to index 0 for anything
    it does not recognize -- and index 0 of this dropdown is 'Task'.  Unchecked, a typo
    would quietly import the Profile XML as a Task instead of saying so."""
    built = deviceinv.build_import_profile_task(import_type="Config")

    assert isinstance(built, str)
    assert "Task, Configuration" in built


def test_the_source_argument_can_be_changed_without_editing_the_builder(
    import_device: _FakeImportRequests,
) -> None:
    """lookup_values["153a"] is a one-entry placeholder, so this codebase does not know what
    Source's options are called and apply_arg_values can only ever reach 0 through it.  0 is
    what api/import sends and stays the default; a prototype should not make the question
    unaskable."""
    built = deviceinv.build_import_profile_task(source_index="1")
    assert not isinstance(built, str), built

    imported = ET.fromstring(taskedit.render_standalone_task_xml(built))  # noqa: S314
    assert imported.find(".//Action[code='153']/Int[@sr='arg1']").get("val") == "1"


def test_a_different_experiment_installs_a_differently_named_task(import_device: _FakeImportRequests) -> None:
    """Both settings are baked into the Task's actions at install time, and
    _install_task_on_android skips a name that is already on the device.  Sharing one name
    across settings would silently re-run the Task built with the previous ones -- the
    prototype would report on an experiment nobody asked for."""
    import_device.installed_tasks.add(deviceinv.IMPORT_PROFILE_TASK_NAME)  # the default-named one is there

    return_code, message = _import(import_device, import_type=deviceinv.IMPORT_TYPE_TASK)
    assert return_code == 0, message

    # Installed anyway, because it is not the same Task.
    assert any(verb == "POST" and "/api/import" in url for verb, url in import_device.calls)
    imported = ET.fromstring(import_device.imported_xml)  # noqa: S314
    assert imported.find(".//Action[code='153']/Int[@sr='arg0']").get("val") == "0"  # Task
    assert imported.findtext(".//Task/nme") == f"{deviceinv.IMPORT_PROFILE_TASK_NAME} [Task/0]"


def test_the_default_experiment_keeps_the_plain_name(import_device: _FakeImportRequests) -> None:
    """The name a user actually sees in Tasker for the ordinary case."""
    _import(import_device)

    imported = ET.fromstring(import_device.imported_xml)  # noqa: S314
    assert imported.findtext(".//Task/nme") == deviceinv.IMPORT_PROFILE_TASK_NAME


# ##################################################################################
# Offering a Profile to Tasker's own import screen
#
# The other route's headless 'Import Data' against this one's tap on the device.  What is
# asserted here is mostly what makes the two DIFFERENT: this one puts nothing at stake but
# the one Profile, so there is no risk gate -- and its answer file proves less, so it must
# not claim more.
# ##################################################################################
GOOD_OPEN_PAYLOAD = """MAPTASKER-OPEN-PROFILE 1
OFFERED
/storage/emulated/0/Tasker/profiles/Watched.prf.xml
MAPTASKER-END
"""


@pytest.fixture
def open_device(monkeypatch: pytest.MonkeyPatch) -> _FakeImportRequests:
    """The same stand-in device, answering for the 'Open File' helper's own files."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=GOOD_OPEN_PAYLOAD)
    fake.result_filename = "maptasker_open_profile.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)
    return fake


def _open(device: _FakeImportRequests, **kwargs: object) -> tuple[int, str]:
    return deviceinv.open_profile_on_device(
        _STAGED_PROFILE_XML,
        "Watched",
        "192.168.0.210",
        "1821",
        **kwargs,
    )


def test_the_offer_uploads_under_the_profiles_own_name(open_device: _FakeImportRequests) -> None:
    """What lands in /Tasker/profiles is 'Watched.prf.xml'.  It used to be
    'maptasker_import.prf.xml' for every Profile ever offered, which is what a user browsing
    that folder for the Profile they just sent actually found."""
    return_code, message = _open(open_device, wait_for_confirmation=False)

    assert return_code == 0, message
    assert open_device.uploaded_filename == "Watched.prf.xml"
    # Named in the message too, because this one is handing the user something to finish:
    # a handoff Tasker does not complete leaves them to import it themselves, and they can
    # only do that if they are told which file it is.
    assert "/storage/emulated/0/Tasker/profiles/Watched.prf.xml" in message


def test_the_run_tells_the_helper_which_file_to_open(open_device: _FakeImportRequests) -> None:
    """The path travels WITH the run, as par1 -- which the HTTP Server Example's own handler
    unpacks into %par1 for the Task it runs (deviceinv.run_task_on_android quotes the
    actions).  Without it the helper would open whatever it was built with, which is the
    fixed filename this replaced."""
    return_code, message = _open(open_device)
    assert return_code == 0, message

    assert open_device.run_bodies[-1] == {
        "name": deviceinv.OPEN_FILE_ROUTE.task_name,
        "par1": "/storage/emulated/0/Tasker/profiles/Watched.prf.xml",
    }


def test_the_staged_path_is_not_read_before_it_is_written(
    open_device: _FakeImportRequests,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One read of that path, and it belongs to the CALLER.

    The staged file is the user's own now -- exactly where 'Save As File' writes -- so
    something does have to ask what is already there and copy it.  That is the GUI's job,
    from the same read it uses to put the overwrite prompt up (see
    userintr._offer_into_tasker).  Reading it here as well would be a second GET of a path
    just read, and the Tasker HTTP Server Example flashes 'File doesn't exist' on the phone
    for every miss -- two flashes for one import.
    """
    monkeypatch.chdir(tmp_path)

    return_code, message = _open(open_device, wait_for_confirmation=False)
    assert return_code == 0, message

    upload_at = next(i for i, (verb, path) in enumerate(open_device.calls) if verb == "POST" and "/upload" in path)
    # The read AFTER the upload is the read-back that proves the write landed, and it stays.
    assert [path for verb, path in open_device.calls[:upload_at] if verb == "GET" and ".prf.xml" in path] == []
    assert not (tmp_path / "MapTasker_Backups").exists()  # nothing copied down here either


def test_offering_a_profile_needs_no_risk_acknowledged(open_device: _FakeImportRequests) -> None:
    """The whole reason this route exists.  Android is handed a file and Tasker shows the
    user what it is about to import, so nothing outside that one Profile is at stake and
    there is no unanswered question to gate on -- unlike import_profile_to_device, which
    refuses to send anything at all without one."""
    return_code, message = _open(open_device)

    assert return_code == 0, message
    assert open_device.uploaded == _STAGED_PROFILE_XML


def test_the_offered_task_opens_the_staged_file_with_no_mime_type(open_device: _FakeImportRequests) -> None:
    """'Open File' (code 102) on the staged path, carrying NO mime type -- which is what
    makes this the "Open with..." a file manager fires.

    It used to send 'text/xml', and that is what a chooser of seven apps without Tasker in it
    was measured on: a filter that claims an extension declares a pathPattern and no
    android:mimeType, and Android matches those only against intents that carry no type.
    Asking for text/xml gets text/xml viewers.  See deviceinv._OPEN_WITH_MIME_TYPE."""
    _open(open_device)

    imported = ET.fromstring(open_device.imported_xml)  # noqa: S314  (built by this program)
    open_file = imported.find(".//Action[code='102']")
    assert open_file is not None
    assert open_file.findtext("Str[@sr='arg0']") == "%par1"  # told which file at run time
    assert (open_file.findtext("Str[@sr='arg1']") or "") == ""

    # And no 'Import Data' anywhere -- that is the other route, and mixing them would put
    # the unproven one back in the path of a caller that deliberately chose this one.
    assert "153" not in _codes(open_device.imported_xml)


def test_the_two_routes_do_not_share_an_answer_file(open_device: _FakeImportRequests) -> None:
    """Both write a MAPTASKER-* file ending in the same terminator.  Reading one as the
    other would be a silent misparse, so they differ in header and in path."""
    _open(open_device)

    imported = ET.fromstring(open_device.imported_xml)  # noqa: S314
    writes = imported.findall(".//Action[code='410']")
    assert writes[0].findtext("Str[@sr='arg1']") == "MAPTASKER-OPEN-PROFILE 1"
    assert all(write.findtext("Str[@sr='arg0']") == "Tasker/maptasker_open_profile.txt" for write in writes)
    assert deviceinv.OPEN_FILE_ROUTE.read_path != deviceinv._IMPORT_RESULT_READ_PATH  # noqa: SLF001


def test_an_unconfirmed_offer_is_not_reported_as_a_save(monkeypatch: pytest.MonkeyPatch) -> None:
    """'Open File' fires an intent and returns without waiting for the person to decide, so
    the answer file lands whether or not anything is imported.  With no confirmation asked
    for, the message has to say the import is still pending -- shown as a completed save it
    would send the user looking for a Profile that is not there."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=GOOD_OPEN_PAYLOAD, profiles_after=set())
    fake.result_filename = "maptasker_open_profile.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _open(fake, wait_for_confirmation=False)

    assert return_code == 0
    assert "not imported until it is confirmed" in message


def test_a_confirmation_that_never_comes_is_not_a_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """The user declined, or has not picked the phone up.  Neither is the device's fault and
    neither is a success, so the message says so without blaming the device."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=GOOD_OPEN_PAYLOAD, profiles_after=set())
    fake.result_filename = "maptasker_open_profile.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _open(fake)

    assert return_code != 0
    assert "may have been declined" in message


def test_waiting_stops_as_soon_as_the_profile_appears(open_device: _FakeImportRequests) -> None:
    """The poll is for a person, so it is long -- two minutes.  It must not spend them on a
    device that already answered."""
    return_code, message = deviceinv.await_import("192.168.0.210", "1821", ["Watched"], "Profile " + chr(39) + "Watched" + chr(39))
    assert return_code != 0  # nothing imported yet

    open_device.installed_profiles = {"Watched"}
    before = len(open_device.calls)
    return_code, message = deviceinv.await_import("192.168.0.210", "1821", ["Watched"], "Profile " + chr(39) + "Watched" + chr(39))

    assert return_code == 0, message
    assert len(open_device.calls) - before == 1  # asked once, answered, stopped


def test_a_profile_tasker_already_has_is_offered_anyway(open_device: _FakeImportRequests) -> None:
    """Measured on a real device: Tasker asks whether to replace a Profile it already has.
    Refusing here would put a worse prompt in front of a better one -- and a wrong one, since
    it would warn about a duplicate Tasker is about to offer to replace."""
    open_device.installed_profiles = {"Watched"}

    return_code, message = _open(open_device)

    assert return_code == 0, message
    assert open_device.uploaded == _STAGED_PROFILE_XML  # it was offered, not refused


def test_a_replacement_is_not_reported_as_a_confirmed_import(open_device: _FakeImportRequests) -> None:
    """The whole confirmation is 'does Tasker report a Profile of this name', and for one it
    ALREADY reports that is true before the user touches anything.  Waiting on it would
    confirm the import the instant it was asked -- Cancel included -- so it is not waited on,
    and the message says what actually happened instead."""
    open_device.installed_profiles = {"Watched"}

    return_code, message = _open(open_device)

    assert return_code == 0
    assert "will offer to replace" in message
    assert "cannot be seen from here" in message


def test_a_new_profile_is_still_really_confirmed(open_device: _FakeImportRequests) -> None:
    """The case where the question does mean something: Tasker had no such Profile before,
    so reporting one afterwards is real evidence the user tapped Import."""
    return_code, message = _open(open_device)

    assert return_code == 0
    assert "is now in Tasker" in message


def test_import_is_confirmable_keeps_could_not_ask_apart_from_absent(
    open_device: _FakeImportRequests,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Folding None into True would turn an unconfirmable import into a confirmed one --
    exactly the mistake the pre-check exists to prevent."""
    assert deviceinv.import_is_confirmable("192.168.0.210", "1821", ["Watched"]) is True

    open_device.installed_profiles = {"Watched"}
    assert deviceinv.import_is_confirmable("192.168.0.210", "1821", ["Watched"]) is False

    monkeypatch.setattr(deviceinv, "_ensure_auth_key", lambda _ip, _port: (8, "unreachable"))
    assert deviceinv.import_is_confirmable("192.168.0.210", "1821", ["Watched"]) is None


def test_nothing_to_ask_about_is_not_confirmed(open_device: _FakeImportRequests) -> None:
    """A Project owning only unnamed Profiles gives nothing the HTTP API can be asked about
    (see projedit.project_profile_names).  'No questions asked' must not read as 'confirmed'
    -- it is the one case where an empty answer and a good one look identical."""
    assert deviceinv.import_is_confirmable("192.168.0.210", "1821", []) is False
    assert deviceinv.import_is_confirmable("192.168.0.210", "1821", ["", "  "]) is False


# ##################################################################################
# The same offer, addressed to Tasker explicitly
#
# 'Open File' asks Android to find a handler; 'Send Intent' names one.  These assert the
# intent's shape -- which is taken from the ACTION_VIEW intents in this repo's real backups,
# not invented -- and that choosing a route actually changes which Task runs and which file
# is read, rather than quietly running the other one.
# ##################################################################################
GOOD_INTENT_PAYLOAD = """MAPTASKER-SEND-PROFILE 1
OFFERED
/storage/emulated/0/Tasker/profiles/Watched.prf.xml
MAPTASKER-END
"""


@pytest.fixture
def intent_device(monkeypatch: pytest.MonkeyPatch) -> _FakeImportRequests:
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=GOOD_INTENT_PAYLOAD)
    fake.result_filename = "maptasker_send_profile.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)
    return fake


def test_the_intent_is_the_shape_real_backups_use(intent_device: _FakeImportRequests) -> None:
    """Every ACTION_VIEW 'Send Intent' in this repo's backups uses Cat=None (0) and
    Target=Activity (1), and the ones meant for a particular app name it in Package.  A
    Broadcast Receiver or a Service target would send it somewhere that cannot show an
    import screen, and neither failure would say so."""
    return_code, message = _open(intent_device, route=deviceinv.SEND_INTENT_ROUTE)
    assert return_code == 0, message

    imported = ET.fromstring(intent_device.imported_xml)  # noqa: S314  (built by this program)
    intent = imported.find(".//Action[code='877']")
    assert intent is not None
    assert intent.findtext("Str[@sr='arg0']") == "android.intent.action.VIEW"
    assert intent.find("Int[@sr='arg1']").get("val") == "0"  # Cat: None
    assert intent.findtext("Str[@sr='arg2']") == "text/xml"
    assert intent.findtext("Str[@sr='arg3']") == "file://%par1"  # told which file at run time
    assert intent.findtext("Str[@sr='arg7']") == "net.dinglisch.android.taskerm"
    assert intent.findtext("Str[@sr='arg8']") == "net.dinglisch.android.taskerm.Tasker"
    assert intent.find("Int[@sr='arg9']").get("val") == "1"  # Target: Activity


def test_choosing_a_route_changes_which_task_runs(intent_device: _FakeImportRequests) -> None:
    """The routes are separate Tasks with separate names, so a device can hold both and
    neither run is the other's.  Asking for one and getting the other would be invisible
    from here -- both write a MAPTASKER-* file and both end in the same terminator."""
    _open(intent_device, route=deviceinv.SEND_INTENT_ROUTE)

    imported = ET.fromstring(intent_device.imported_xml)  # noqa: S314
    assert imported.findtext(".//Task/nme") == deviceinv.SEND_INTENT_ROUTE.task_name
    assert "102" not in _codes(intent_device.imported_xml)  # not the Open File Task

    assert deviceinv.SEND_INTENT_ROUTE.read_path != deviceinv.OPEN_FILE_ROUTE.read_path
    assert deviceinv.SEND_INTENT_ROUTE.header != deviceinv.OPEN_FILE_ROUTE.header
    assert deviceinv.SEND_INTENT_ROUTE.task_name != deviceinv.OPEN_FILE_ROUTE.task_name


def test_a_route_reads_only_its_own_answer_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A device still holding the OTHER route's answer file must not be read as this one's
    success.  The header is what catches it."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=GOOD_OPEN_PAYLOAD)  # the wrong route's payload
    fake.result_filename = "maptasker_send_profile.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _open(fake, route=deviceinv.SEND_INTENT_ROUTE)

    assert return_code != 0
    assert "not a MapTasker import result" in message


def test_the_intent_route_names_the_failure_only_it_has(monkeypatch: pytest.MonkeyPatch) -> None:
    """Since Android 7 a file:// URI in an outgoing intent is rejected, and this route is the
    only one that has to use one -- 'Open File' can hand out a content:// URI and this
    cannot.  A device that writes nothing back should point at that, and at the route that
    does not have the problem, rather than leaving the user guessing."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=None)
    fake.result_filename = "maptasker_send_profile.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = _open(fake, route=deviceinv.SEND_INTENT_ROUTE)

    assert return_code != 0
    assert "file://" in message
    assert "try the Open File route instead" in message  # named for a user, not for a reader of this code


def test_both_routes_share_everything_around_the_task(intent_device: _FakeImportRequests) -> None:
    """Staging, the duplicate refusal and the confirmation wait are one implementation, not
    two -- the routes are data handed to one orchestrator.  Asserted through the intent
    route because the other one's tests would pass either way."""
    return_code, message = _open(intent_device, route=deviceinv.SEND_INTENT_ROUTE)

    assert return_code == 0, message
    assert intent_device.uploaded == _STAGED_PROFILE_XML  # the shared staging upload
    assert "is now in Tasker" in message  # the shared confirmation wait


# ##################################################################################
# Confirming at the right endpoint
#
# The three kinds do not all confirm the same way.  A Profile and a Scene each have an
# endpoint of their own; a Project has none -- Tasker's API reports Profiles, Tasks, Scenes
# and Globals by name and that is the whole list -- so it is confirmed through the Profiles
# it brings with it.  Asking at the wrong one answers about the wrong thing.
# ##################################################################################


def test_the_endpoint_reaches_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The endpoint has to travel all the way to the URL, not just sit in the route."""
    from maptasker.src import maputil2

    asked = []

    class _Recorder(_FakeImportRequests):
        def get(self, url: str, **kwargs: object) -> _FakeResponse:
            if "/api/" in url:
                asked.append(url.split("1821", 1)[1].split("?", 1)[0])
            return super().get(url, **kwargs)

    fake = _Recorder()
    monkeypatch.setattr(maputil2, "requests", fake)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    deviceinv.import_is_confirmable("192.168.0.210", "1821", ["Dialog"], deviceinv.SCENES_ENDPOINT)

    assert "/api/scenes" in asked
    assert "/api/profiles" not in asked


def _open_file_args(route: deviceinv.OfferRoute) -> tuple[str, str]:
    """The staged path and mime type the route's helper Task hands to 'Open File'."""
    built = route.builder()
    assert not isinstance(built, str), built
    task_xml = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))  # noqa: S314
    action = task_xml.find(".//Action[code='102']")
    assert action is not None
    return action.findtext("Str[@sr='arg0']"), action.findtext("Str[@sr='arg1']")


def _send_intent_args(route: deviceinv.OfferRoute) -> tuple[str, str, str]:
    """The mime type, data URI and package the route's helper Task sends ACTION_VIEW with."""
    built = route.builder()
    assert not isinstance(built, str), built
    task_xml = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))  # noqa: S314
    action = task_xml.find(".//Action[code='877']")
    assert action is not None
    return (
        action.findtext("Str[@sr='arg2']"),
        action.findtext("Str[@sr='arg3']"),
        action.findtext("Str[@sr='arg7']"),
    )


def test_the_intent_names_a_class_and_not_just_a_package(import_device: _FakeImportRequests) -> None:
    """What makes an intent addressed rather than advertised, which is what this route is
    for.  A package with no class is still matched against that package's intent-filters, so
    package-only is not the fallback it claims to be -- it fails wherever implicit
    resolution fails, and looks identical from here.  Package AND class is an explicit
    component, delivered without matching anything."""
    for route in (deviceinv.SEND_INTENT_ROUTE, deviceinv.SEND_INTENT_PROJECT_ROUTE):
        _mime, _uri, package = _send_intent_args(route)
        built = route.builder()
        task_xml = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))  # noqa: S314
        intent = task_xml.find(".//Action[code='877']")
        assert package == "net.dinglisch.android.taskerm"
        assert intent.findtext("Str[@sr='arg8']") == "net.dinglisch.android.taskerm.Tasker"


# ##################################################################################
# Suppressing output must not cost the program its output
#
# Every HTTP call here runs inside maputil2.suppress_stdout, and every one of them runs in a
# worker thread (run.io_bound) -- the import confirmation polls one every two seconds for
# two minutes.  sys.stdout and sys.stderr are process wide, so two of those overlapping used
# to leave the SECOND one restoring a devnull the first had already closed, and every write
# to stderr from then on raised.  Observed end state: uvicorn down with 'lost sys.stderr'.
# ##################################################################################


def test_two_threads_suppressing_at_once_leave_the_streams_usable() -> None:
    """The interleaving that did the damage, run directly: one thread enters, a second
    enters while it is inside, the first exits and closes its devnull, the second exits and
    restores what it saved.  Whatever it restores has to be a stream that still works."""
    import threading

    from maptasker.src.maputil2 import suppress_stdout

    real_stdout, real_stderr = sys.stdout, sys.stderr
    first_inside, first_done = threading.Event(), threading.Event()

    def first() -> None:
        with suppress_stdout():
            first_inside.set()
            first_done.wait(timeout=5)

    def second() -> None:
        first_inside.wait(timeout=5)
        with suppress_stdout():
            first_done.set()
            time.sleep(0.05)  # still inside while the other one exits and closes its file

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    left_behind_out, left_behind_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = real_stdout, real_stderr  # before asserting, or a failure cannot be reported

    left_behind_err.write("")  # ValueError("I/O operation on closed file") before the lock
    left_behind_out.write("")
    assert left_behind_err is real_stderr
    assert left_behind_out is real_stdout


# ##################################################################################
# Opening Tasker, for the import only a person can finish
#
# A Scene cannot be handed to Tasker by intent -- four ways tried, all measured failing (see
# the section comment in deviceinv).  So the Scene goes over under its own name and Tasker is
# merely brought to the front; the user finishes in 'Scenes > Import One Scene'.
# ##################################################################################


def test_opening_tasker_hands_over_nothing(import_device: _FakeImportRequests) -> None:
    """ACTION_MAIN at an explicit component, and no data, no mime type: there is no file to
    hand over any more, and a VIEW with no data is not a launch.  If this ever grows a data
    argument again it has become the route that does not work."""
    built = deviceinv.build_launch_tasker_task()
    assert not isinstance(built, str), built

    task_xml = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))  # noqa: S314
    intent = task_xml.find(".//Action[code='877']")
    assert intent.findtext("Str[@sr='arg0']") == "android.intent.action.MAIN"
    assert intent.findtext("Str[@sr='arg2']") == ""  # no mime type
    assert intent.findtext("Str[@sr='arg3']") == ""  # no data
    assert intent.findtext("Str[@sr='arg7']") == "net.dinglisch.android.taskerm"
    assert intent.findtext("Str[@sr='arg8']") == "net.dinglisch.android.taskerm.Tasker"
    assert "102" not in _codes(ET.tostring(built.task_element, encoding="unicode"))  # no 'Open File'


def test_opening_tasker_runs_its_own_task_and_reads_its_own_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Its own Task name and its own answer file, for the reason every other route has them:
    reading another route's leftover answer as this one's would report a launch that never
    happened."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload="MAPTASKER-LAUNCH-TASKER 1\nOFFERED\n/Tasker/scenes\nMAPTASKER-END\n")
    fake.result_filename = "maptasker_launch_tasker.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = deviceinv.open_tasker_on_device("192.168.0.210", "1821")

    assert return_code == 0, message
    assert ET.fromstring(fake.imported_xml).findtext(".//Task/nme") == deviceinv.LAUNCH_TASKER_TASK_NAME  # noqa: S314
    assert any("maptasker_launch_tasker.txt" in url for verb, url in fake.calls if verb == "GET")


def test_another_routes_answer_is_not_read_as_a_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The header is what catches it -- a device still holding an offer route's answer file
    must not be read as Tasker having been opened."""
    from maptasker.src import maputil2

    fake = _FakeImportRequests(payload=GOOD_OPEN_PAYLOAD)  # the wrong route's answer
    fake.result_filename = "maptasker_launch_tasker.txt"
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001
    _load(_FIXTURE_XML)

    return_code, message = deviceinv.open_tasker_on_device("192.168.0.210", "1821")

    assert return_code != 0
    assert "not a MapTasker launch result" in message


def test_a_scene_has_a_route_again_and_it_is_the_open_with_one() -> None:
    """A Scene had no route at all: both measured handoffs failed (a chooser of text/xml apps
    without Tasker, and an explicit intent Tasker answers by importing nothing), so it was
    uploaded and Tasker merely opened.

    The "Open with..." is a third thing, not a repeat of either -- an implicit VIEW carrying
    no type, which is the only one of the three that lets an extension filter match.  It is
    offered on that reasoning, and the by-hand instruction stays in the message for when it
    is wrong."""
    assert deviceinv.OPEN_SCENE_ROUTE.stage_location == "Tasker/scenes"
    assert deviceinv.OPEN_SCENE_ROUTE.extension == "scn.xml"
    assert deviceinv.OPEN_SCENE_ROUTE.confirm_endpoint == deviceinv.SCENES_ENDPOINT == "api/scenes"
    # Still there, and still what a device that cannot be handed a Scene falls back to.
    assert callable(deviceinv.open_tasker_on_device)


# ##################################################################################
# A Task's 'Save As File', which is the Profile's with a different extension
#
# The Save To Android dialog offers two things for every kind now: a file written onto the
# device's storage, and an import into Tasker.  For a Task the second one is the easy half
# -- api/import is documented Task-only and needs no tap -- and the FILE half was the one
# missing: 'Save' used to import and nothing wrote a .tsk.xml to the device at all.
# ##################################################################################


class _FakeUploadRequests:
    """A device that accepts /upload and serves back whatever it was given.

    served_back is what a read-back gets, so a test can hand it something OTHER than what
    was uploaded -- which is the case that matters: /upload answers 200 whatever it wrote.
    """

    def __init__(self, served_back: bytes | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.uploaded: bytes = b""
        self.location = ""
        self.filename = ""
        self.served_back = served_back

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append(("POST", url))
        files = kwargs.get("files", {})
        self.filename = next(iter(files))
        self.uploaded = next(iter(files.values()))[1]
        self.location = kwargs.get("params", {}).get("location", "")
        return _FakeResponse(200, b"OK")

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        self.calls.append(("GET", url))
        content = self.uploaded if self.served_back is None else self.served_back
        return _FakeResponse(200, content)


def _save_task_file(monkeypatch: pytest.MonkeyPatch, fake: _FakeUploadRequests) -> tuple[int, str]:
    from maptasker.src import maputil2

    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)  # the read-back settle
    _load(_FIXTURE_XML)
    edited_task = taskedit.load_task_for_edit("Opener")  # by NAME -- see load_task_for_edit
    assert edited_task is not None
    return taskedit.save_task_to_android_file(edited_task, "192.168.0.210", "1821", "Opener")


def test_a_task_file_goes_to_taskers_tasks_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    """/Tasker/tasks, beside /Tasker/profiles and /Tasker/scenes.  The path comes from
    android_task_path, which is also what the overwrite check asks about -- the two reading
    it from one place is what keeps a prompt about one file from guarding another."""
    fake = _FakeUploadRequests()
    return_code, result = _save_task_file(monkeypatch, fake)

    assert return_code == 0, result
    assert result == taskedit.android_task_path("Opener") == "/Tasker/tasks/Opener.tsk.xml"
    assert fake.location == taskedit.ANDROID_TASK_LOCATION == "Tasker/tasks"
    assert fake.filename == "Opener.tsk.xml"
    assert fake.uploaded.startswith(b"<TaskerData")


def test_a_task_file_that_did_not_land_is_not_called_a_save(monkeypatch: pytest.MonkeyPatch) -> None:
    """/upload answers 200 for anything -- it does not validate the location and it creates
    missing folders silently -- so the read-back is the only thing that can tell a written
    file from a lost one.  Reported as a failure, the way profedit.save_profile_to_android
    reports its own."""
    fake = _FakeUploadRequests(served_back=b"<TaskerData>something else</TaskerData>")
    return_code, result = _save_task_file(monkeypatch, fake)

    assert return_code != 0
    assert "could not confirm it landed correctly" in result


def test_the_three_kinds_write_to_three_sibling_folders() -> None:
    """One naming scheme, not three near-misses: a Task landing in /Tasker/profiles, or in a
    folder of its own invention, is the kind of thing nothing fails on and nobody finds."""
    from maptasker.src import profedit, sceneedit

    assert taskedit.android_task_path("A") == "/Tasker/tasks/A.tsk.xml"
    assert profedit.android_profile_path("A") == "/Tasker/profiles/A.prf.xml"
    assert sceneedit.android_scene_path("A") == "/Tasker/scenes/A.scn.xml"


def test_a_task_name_that_is_no_filename_still_writes_somewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasker names are free text and slashes are legal in them.  sanitize_filename is what
    keeps 'Wake: Up' from addressing a folder that does not exist -- and what makes two names
    collide onto one path, which is why the caller prompts before overwriting."""
    assert taskedit.android_task_path("Wake: Up") == "/Tasker/tasks/Wake_ Up.tsk.xml"
    assert taskedit.android_task_path("a/b") == "/Tasker/tasks/a_b.tsk.xml"
    assert taskedit.android_task_path("") == "/Tasker/tasks/task.tsk.xml"  # the fallback name


# ##################################################################################
# ...and the import that now goes through that same file
#
# 'Import Into Tasker' writes /Tasker/tasks/<name>.tsk.xml first and posts what the device
# gives back, so the import sources from the folder and always leaves a copy behind.  The
# thing that must not regress: the bytes posted are the device's, not a second render.
# ##################################################################################


class _FakeImportViaFileRequests(_FakeUploadRequests):
    """The upload double, plus the two endpoints an import needs."""

    def __init__(self, served_back: bytes | None = None) -> None:
        super().__init__(served_back)
        self.imported: list[bytes] = []

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        if "/api/auth" in url:
            return _FakeResponse(200, b'{"key": "TESTKEY", "authorized": true}')
        return super().get(url, **kwargs)

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        if "/api/import" in url:
            self.calls.append(("POST", url))
            self.imported.append(kwargs.get("data", b""))
            return _FakeResponse(200, b"{}")
        return super().post(url, **kwargs)


def _import_task(monkeypatch: pytest.MonkeyPatch, fake: _FakeImportViaFileRequests, **kwargs: object):
    from maptasker.src import maputil2

    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)  # the read-back settle
    _load(_FIXTURE_XML)
    edited_task = taskedit.load_task_for_edit("Opener")
    assert edited_task is not None
    return taskedit.save_task_to_android(edited_task, "192.168.0.210", "1821", "Opener", **kwargs)


def test_an_import_leaves_the_task_in_the_tasks_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    """The copy is not a side effect to be tidied away later -- it is where the import reads
    from, and afterwards it is the record of exactly what was imported."""
    fake = _FakeImportViaFileRequests()
    return_code, result, _key = _import_task(monkeypatch, fake)

    assert return_code == 0, result
    assert fake.location == "Tasker/tasks"
    assert fake.filename == "Opener.tsk.xml"
    assert fake.imported, "nothing was imported"


def test_the_import_posts_the_devices_bytes_and_not_a_second_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """'Import it from that directory' is only true if the bytes come FROM there.  The
    device is made to serve back something distinguishable: if the import posts a fresh
    render instead, this is where that shows up."""
    from_device = b"<TaskerData>what the device actually holds</TaskerData>"
    fake = _FakeImportViaFileRequests(served_back=from_device)

    # The read-back doubles as the write's verify, so a device serving something else is a
    # failed write -- which is the other half of the contract, tested just below.  Here the
    # verify is neutralised so the import step itself can be observed.
    monkeypatch.setattr(taskedit, "render_standalone_task_xml", lambda _task: from_device.decode())
    return_code, result, _key = _import_task(monkeypatch, fake)

    assert return_code == 0, result
    assert fake.imported == [from_device]


def test_a_file_that_did_not_land_is_never_imported(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no verified file in the folder there is nothing to import from, and importing
    the in-memory render at that point would import something other than what the copy on
    the device says was imported.  So the import does not happen at all."""
    fake = _FakeImportViaFileRequests(served_back=b"<TaskerData>not what was sent</TaskerData>")
    return_code, result, _key = _import_task(monkeypatch, fake)

    assert return_code != 0
    assert "could not confirm it landed correctly" in result
    assert fake.imported == []
    # And no authorization was asked for either -- the prompt lands on the user's phone.
    assert not any("/api/auth" in url for _verb, url in fake.calls)


def test_a_helper_task_does_not_leave_a_file_behind(monkeypatch: pytest.MonkeyPatch) -> None:
    """via_file=False, for MapTasker's own plumbing.  /Tasker/tasks is a folder the user
    browses for their own Tasks; 'MapTasker Send Profile v1.tsk.xml' in it is litter they
    never asked for and would have to recognize before deleting."""
    fake = _FakeImportViaFileRequests()
    return_code, result, _key = _import_task(monkeypatch, fake, via_file=False)

    assert return_code == 0, result
    assert fake.imported, "nothing was imported"
    assert not any("/upload" in url for _verb, url in fake.calls)


def test_the_retry_reimports_the_file_rather_than_re_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback when Tasker will not confirm the import.  It re-reads the file already
    written and verified, so the retry is the same request being retried -- re-rendering
    here would quietly make it a different one."""
    from maptasker.src import maputil2

    fake = _FakeImportViaFileRequests()
    monkeypatch.setattr(maputil2, "requests", fake)
    _load(_FIXTURE_XML)
    edited_task = taskedit.load_task_for_edit("Opener")
    fake.uploaded = b"<TaskerData>already on the device</TaskerData>"  # what the folder holds

    return_code, result = taskedit.save_task_to_android_directory(
        edited_task,
        "192.168.0.210",
        "1821",
        "Opener",
        "TESTKEY",
    )

    assert return_code == 0, result
    assert fake.imported == [b"<TaskerData>already on the device</TaskerData>"]


def test_a_write_still_settling_is_waited_for_rather_than_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE REPORT THIS EXISTS FOR: Tasker flashes 'File doesn\'t exist' and the save fails,
    and the file is sitting there when the user goes to look.  /upload is one Tasker Task
    writing to storage and the read-back is another answering a second request -- nothing
    orders the two -- so a read that arrives too early gets a 404 for a file that is on its
    way.  Failing on the first miss aborts a save that worked."""
    from maptasker.src import maputil2

    fake = _FakeImportViaFileRequests()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)
    _load(_FIXTURE_XML)

    # The device answers 404 twice -- the write has not landed yet -- and then serves it.
    misses = [0]
    real_get = fake.get

    def slow_to_appear(url: str, **kwargs: object) -> _FakeResponse:
        if "/file/" in url and misses[0] < 2:
            misses[0] += 1
            return _FakeResponse(404)
        return real_get(url, **kwargs)

    fake.get = slow_to_appear
    edited_task = taskedit.load_task_for_edit("Opener")
    return_code, result, _key = taskedit.save_task_to_android(edited_task, "192.168.0.210", "1821", "Opener")

    assert return_code == 0, result
    assert misses[0] == 2  # it really did have to wait
    assert fake.imported, "the import was abandoned over a file that was on its way"


def test_a_write_that_never_appears_is_still_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Waiting is not believing.  A file that never turns up must not be reported as saved --
    the retry exists to absorb a slow write, not to paper over a failed one."""
    from maptasker.src import maputil2

    fake = _FakeImportViaFileRequests()
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)
    _load(_FIXTURE_XML)
    fake.get = lambda url, **_kwargs: (
        _FakeResponse(200, b'{"key": "TESTKEY", "authorized": true}') if "/api/auth" in url else _FakeResponse(404)
    )

    edited_task = taskedit.load_task_for_edit("Opener")
    return_code, result, _key = taskedit.save_task_to_android(edited_task, "192.168.0.210", "1821", "Opener")

    assert return_code != 0
    assert "could not confirm it landed correctly" in result
    assert fake.imported == []


def test_one_read_answers_both_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    """'Is anything already there' and 'give me a copy of it' used to be two GETs of the same
    path, and the server example flashes on every miss -- so a first-time save put two
    'File doesn't exist' messages on the user's phone before writing anything.  One read
    answers both."""
    from maptasker.src import maputil2

    fake = _FakeImportViaFileRequests(served_back=b"<TaskerData>already there</TaskerData>")
    monkeypatch.setattr(maputil2, "requests", fake)

    exists, content = maputil2.read_android_file("192.168.0.210", "1821", "/Tasker/tasks/Opener.tsk.xml")

    assert exists is True
    assert content == b"<TaskerData>already there</TaskerData>"
    assert len([url for verb, url in fake.calls if verb == "GET"]) == 1


# ##################################################################################
# Where an import stages its file
#
# Reported from a real device: 'the profile to be imported does not appear in
# /Tasker/profiles'.  It did not -- it was staged in /Tasker, a corner of the storage nobody
# would think to look in, while the folder the user was browsing held only what the file-write
# button had put there.  The staged file now goes into the kind's own folder: it is where the
# user looks for it, and where Tasker's own import browses when the handoff fails.
# ##################################################################################


def test_each_kind_stages_into_the_folder_it_belongs_in() -> None:
    """The same folders the 'Save As File' button writes to, so a user browsing for the file
    being imported finds it beside the files they saved by hand."""
    from maptasker.src import profedit, projedit

    assert deviceinv.OPEN_FILE_ROUTE.stage_location == profedit.ANDROID_PROFILE_LOCATION == "Tasker/profiles"
    assert deviceinv.OPEN_PROJECT_ROUTE.stage_location == projedit.ANDROID_PROJECT_LOCATION == "Tasker/projects"
    # Both routes of a kind stage the same file -- they differ in how Tasker is asked to open
    # it, never in what it is asked to open.
    assert deviceinv.SEND_INTENT_ROUTE.staged_file_paths("A") == deviceinv.OPEN_FILE_ROUTE.staged_file_paths("A")
    assert deviceinv.SEND_INTENT_PROJECT_ROUTE.staged_file_paths("A") == deviceinv.OPEN_PROJECT_ROUTE.staged_file_paths(
        "A",
    )


# ##################################################################################
# ...under the object's own name
#
# Reported from a real device, after the folder was fixed: 'the profile does not appear in
# /Tasker/profiles -- what appears is maptasker_import.prf.xml'.  It was one fixed filename
# per kind, because the path was baked into the helper Task at install time and POST
# /api/tasks was believed to carry a name and nothing else.  It carries a body, and the HTTP
# Server Example's own handler unpacks 'par1' out of it into %par1 for the Task it runs -- so
# the Task can be told which file at run time, and the file can be the user's own.
# ##################################################################################


def test_the_staged_file_carries_the_objects_own_name() -> None:
    """Byte for byte the path the 'Save As File' button writes -- so the import and the file
    save are the same file, and a user browsing Tasker's own import screen sees the Profile
    they asked for rather than 'maptasker_import'."""
    from maptasker.src import profedit, projedit

    _filename, read_path, task_path = deviceinv.OPEN_FILE_ROUTE.staged_file_paths("Morning")
    assert read_path == profedit.android_profile_path("Morning") == "/Tasker/profiles/Morning.prf.xml"
    assert task_path == "/storage/emulated/0/Tasker/profiles/Morning.prf.xml"

    _filename, read_path, _task_path = deviceinv.OPEN_PROJECT_ROUTE.staged_file_paths("Save Parking Spot")
    assert read_path == projedit.android_project_path("Save Parking Spot") == "/Tasker/projects/Save Parking Spot.prj.xml"


def test_a_name_that_is_no_filename_still_stages_somewhere() -> None:
    """Tasker names are free text and slashes are legal in them.  The same substitution the
    editors' own sanitize_filename makes -- spelled again in deviceinv because importing them
    would be a cycle, so a test is what holds the two together."""
    from maptasker.src import profedit, projedit

    for name in ("Wake: Up", "a/b", "", "  "):
        _filename, read_path, _task_path = deviceinv.OPEN_FILE_ROUTE.staged_file_paths(name)
        assert read_path == profedit.android_profile_path(name), name
        # A Project too, because the empty case is the one where they DIFFER: each editor
        # falls back to its own type's word, and the route gets there from its own label.
        _filename, read_path, _task_path = deviceinv.OPEN_PROJECT_ROUTE.staged_file_paths(name)
        assert read_path == projedit.android_project_path(name), name


def test_the_import_data_route_stages_the_same_way() -> None:
    """The Import Data prototype and the offer routes put a Profile in the same place under
    the same name -- one file per Profile, not one per route."""
    assert deviceinv._PROFILE_STAGE_LOCATION == "Tasker/profiles"  # noqa: SLF001
    assert deviceinv.staged_paths(  # noqa: SLF001
        deviceinv._PROFILE_STAGE_LOCATION,
        "Morning",
        deviceinv._PROFILE_EXTENSION,  # noqa: SLF001
        "profile",
    ) == deviceinv.OPEN_FILE_ROUTE.staged_file_paths("Morning")
    # What the Task reads is part of its body and _install_task_on_android skips a name
    # already on the device, so changing it had to rename the Task -- see
    # test_the_helper_task_name_moved_with_what_the_task_opens for the offer routes' own.
    assert deviceinv.IMPORT_PROFILE_TASK_NAME.endswith(" v3")
    # ...and MapTasker's bookkeeping still stays out of the user's Profile folder.
    assert deviceinv._IMPORT_RESULT_READ_PATH.startswith("/Tasker/maptasker_")  # noqa: SLF001


def test_every_kind_has_an_open_with_route_into_its_own_folder() -> None:
    """All four now, and each into the folder its own 'Save As File' button writes to -- so
    the file the chooser is about is the file the user finds when the chooser cannot place
    it.  Held to the editors' own constants by this test rather than by an import, since
    those modules import from this one's callers."""
    from maptasker.src import profedit, projedit, sceneedit, taskedit

    assert deviceinv.OPEN_FILE_ROUTE.stage_location == profedit.ANDROID_PROFILE_LOCATION
    assert deviceinv.OPEN_PROJECT_ROUTE.stage_location == projedit.ANDROID_PROJECT_LOCATION
    assert deviceinv.OPEN_SCENE_ROUTE.stage_location == sceneedit.ANDROID_SCENE_LOCATION
    assert deviceinv.OPEN_TASK_ROUTE.stage_location == taskedit.ANDROID_TASK_LOCATION

    assert deviceinv.OPEN_SCENE_ROUTE.staged_file_paths("A")[1] == sceneedit.android_scene_path("A")
    assert deviceinv.OPEN_TASK_ROUTE.staged_file_paths("A")[1] == taskedit.android_task_path("A")

    # A Task confirms at its own endpoint; a Project still has none and borrows Profiles'.
    assert deviceinv.OPEN_TASK_ROUTE.confirm_endpoint == deviceinv.TASKS_ENDPOINT == "api/tasks"
    assert deviceinv.OPEN_PROJECT_ROUTE.confirm_endpoint == deviceinv.PROFILES_ENDPOINT


def test_only_the_open_with_route_drops_the_mime_type() -> None:
    """The two routes want opposite things from a mime type, so the change is scoped to one.

    Open File is matched against every filter on the device, and a type excludes the
    extension filters that are the only ones claiming '.prf.xml'.  Send Intent names a
    component and is delivered without matching at all, so its type is not doing any
    matching -- it is what the receiver reads to know what it was handed, and dropping it
    there would lose information for no gain.
    """
    built = deviceinv.OPEN_FILE_ROUTE.builder()
    assert not isinstance(built, str), built
    task_xml = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))  # noqa: S314
    assert (task_xml.find(".//Action[code='102']").findtext("Str[@sr='arg1']") or "") == ""

    built = deviceinv.SEND_INTENT_ROUTE.builder()
    assert not isinstance(built, str), built
    task_xml = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))  # noqa: S314
    assert task_xml.find(".//Action[code='877']").findtext("Str[@sr='arg2']") == "text/xml"


def test_no_two_routes_share_an_answer_file() -> None:
    """Eight routes now, and reading one's payload as another's has to be impossible rather
    than unlikely: a Task route reading the Profile route's answer would report a stale
    Profile import as its own success."""
    routes = (
        deviceinv.OPEN_FILE_ROUTE,
        deviceinv.SEND_INTENT_ROUTE,
        deviceinv.OPEN_PROJECT_ROUTE,
        deviceinv.SEND_INTENT_PROJECT_ROUTE,
        deviceinv.OPEN_SCENE_ROUTE,
        deviceinv.SEND_INTENT_SCENE_ROUTE,
        deviceinv.OPEN_TASK_ROUTE,
        deviceinv.SEND_INTENT_TASK_ROUTE,
    )
    assert len({route.read_path for route in routes}) == len(routes)
    assert len({route.header for route in routes}) == len(routes)
    assert len({route.task_name for route in routes}) == len(routes)


def test_the_answer_files_stay_out_of_those_folders() -> None:
    """MapTasker's bookkeeping does not belong among the user's Profiles: a
    'maptasker_open_profile.txt' in the list they browse is litter in a place they look."""
    for route in (
        deviceinv.OPEN_FILE_ROUTE,
        deviceinv.SEND_INTENT_ROUTE,
        deviceinv.OPEN_PROJECT_ROUTE,
        deviceinv.SEND_INTENT_PROJECT_ROUTE,
        deviceinv.OPEN_SCENE_ROUTE,
        deviceinv.SEND_INTENT_SCENE_ROUTE,
        deviceinv.OPEN_TASK_ROUTE,
        deviceinv.SEND_INTENT_TASK_ROUTE,
    ):
        assert route.read_path.startswith("/Tasker/maptasker_")
        for folder in ("/profiles/", "/projects/", "/scenes/", "/tasks/"):
            assert folder not in route.read_path


def test_the_helper_task_name_moved_with_what_the_task_opens() -> None:
    """What the Task opens is part of its body and _install_task_on_android installs only
    what is not already there -- so a device still holding an older Task would go on opening
    the path THAT one was built with, running fine and writing its answer file while handing
    Tasker a file nothing writes any more.  v1 baked /Tasker, v2 baked the kind's folder, v3
    opens %par1.  Each change needed a new name."""
    for route in (
        deviceinv.OPEN_FILE_ROUTE,
        deviceinv.SEND_INTENT_ROUTE,
        deviceinv.OPEN_PROJECT_ROUTE,
        deviceinv.SEND_INTENT_PROJECT_ROUTE,
        deviceinv.OPEN_SCENE_ROUTE,
        deviceinv.SEND_INTENT_SCENE_ROUTE,
        deviceinv.OPEN_TASK_ROUTE,
        deviceinv.SEND_INTENT_TASK_ROUTE,
    ):
        assert route.task_name.endswith(" v4"), route.task_name


# ##################################################################################
# Which of this program's helper Tasks on the device are dead
#
# Every helper is installed under a versioned name and never replaced -- Tasker's api/import
# adds a Task whose name is taken rather than replacing it -- so each change to a helper's
# body leaves the previous generation behind in the user's own Task list.  Nothing can delete
# them from here (the server example has no route for it), so the whole feature is: name them
# exactly, and be careful not to name a live one.
# ##################################################################################


def test_the_current_helper_names_come_from_the_routes_themselves() -> None:
    """A hand-kept list is the thing that goes stale, and the failure is the dangerous
    direction: a version bump that updated the constant and not the list would report the
    Task now in use as dead and invite the user to delete the working one."""
    current = deviceinv.current_helper_task_names()

    assert len(deviceinv.ALL_OFFER_ROUTES) == 8
    for route in deviceinv.ALL_OFFER_ROUTES:
        assert route.task_name in current, route.task_name
    for standalone in (
        deviceinv.IMPORT_PROFILE_TASK_NAME,
        deviceinv.FILE_LIST_TASK_NAME,
        deviceinv.LAUNCH_TASKER_TASK_NAME,
        deviceinv.HELPER_TASK_NAME,
    ):
        assert standalone in current
    assert all(name.startswith(deviceinv.HELPER_TASK_PREFIX) for name in current)


def test_only_this_programs_leftovers_are_called_stale() -> None:
    """Three ways to get this wrong, and each one is in here: naming a live helper, naming a
    Task the user wrote, and missing a leftover."""
    current, stale = deviceinv.classify_helper_tasks(
        [
            "MapTasker Open Profile v1",  # a leftover
            "MapTasker Open Profile v4",  # the one in use
            "MapTasker Get Apps v1",  # a leftover from before the paired build
            "Morning Alarm",  # the user's own
            "MapTaskerish",  # theirs too -- the prefix has a space in it for this reason
            "",
        ],
    )

    assert stale == ["MapTasker Get Apps v1", "MapTasker Open Profile v1"]
    assert current == ["MapTasker Open Profile v4"]


def test_an_experiment_variant_of_the_current_prototype_is_not_stale() -> None:
    """_import_task_name spells the settings into the name ('... v3 [Task/0]').  That is this
    build's Task with one argument changed, not an older build's, and telling someone to
    delete the Task their experiment is running would lose the experiment."""
    current, stale = deviceinv.classify_helper_tasks(
        [
            f"{deviceinv.IMPORT_PROFILE_TASK_NAME} [Task/0]",
            "MapTasker Import Profile v1 [Task/0]",
        ],
    )

    assert current == [f"{deviceinv.IMPORT_PROFILE_TASK_NAME} [Task/0]"]
    assert stale == ["MapTasker Import Profile v1 [Task/0]"]


class _FakeTaskListRequests(_FakeImportRequests):
    """A device with a Task list of its own to report."""

    def __init__(self, names: list[str]) -> None:
        super().__init__()
        self.names = names

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        if "/api/tasks" in url and "name=" not in url:
            self.calls.append(("GET", url))
            return _FakeResponse(200, json.dumps([{"name": n, "running": False} for n in self.names]).encode())
        return super().get(url, **kwargs)


def test_the_whole_task_list_is_asked_for_without_a_name_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """The server example's 'GET Tasks' handler matches 'name=' out of the request path and,
    with none there, works from every Task Tasker reports.  Sending one would ask about a
    single Task, which answers nothing about what is left over."""
    from maptasker.src import maputil2

    fake = _FakeTaskListRequests(["MapTasker Open Profile v1", "MapTasker Open Profile v4", "Morning Alarm"])
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001

    return_code, message, stale, current = deviceinv.stale_helper_tasks_on_device("192.168.0.210", "1821")

    assert return_code == 0, message
    assert stale == ["MapTasker Open Profile v1"]
    assert current == ["MapTasker Open Profile v4"]
    listed = [url for verb, url in fake.calls if verb == "GET" and "/api/tasks" in url]
    assert listed and all("name=" not in url for url in listed)


def test_a_device_that_cannot_be_asked_reports_rather_than_guesses(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty answer and an unanswerable question lead to opposite conclusions: 'nothing is
    left over' would be a quiet lie about a device that never replied."""
    from maptasker.src import maputil2

    class _NoTaskList(_FakeTaskListRequests):
        def get(self, url: str, **kwargs: object) -> _FakeResponse:
            if "/api/tasks" in url and "name=" not in url:
                self.calls.append(("GET", url))
                return _FakeResponse(500, b"nope")
            return _FakeImportRequests.get(self, url, **kwargs)

    fake = _NoTaskList([])
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(deviceinv.time, "sleep", lambda _seconds: None)
    deviceinv._auth_keys.clear()  # noqa: SLF001

    return_code, message, stale, current = deviceinv.stale_helper_tasks_on_device("192.168.0.210", "1821")

    assert return_code != 0
    assert (stale, current) == ([], [])
    assert message


def test_no_address_is_refused_before_the_device_is_touched() -> None:
    """The same refusal every other call here makes, in the same words."""
    return_code, message, stale, current = deviceinv.stale_helper_tasks_on_device("", "")

    assert return_code != 0
    assert "IP address and port" in message
    assert (stale, current) == ([], [])
