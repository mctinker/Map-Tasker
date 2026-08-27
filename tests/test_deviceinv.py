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
/storage/emulated/0/Tasker/maptasker_import.prf.xml
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
        self.task_ran = False
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
        if url.endswith((".prf.xml", ".prj.xml")) or ".prf.xml?" in url or ".prj.xml?" in url:
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
            self.uploaded = next(iter(files.values()))[1]
        elif "/api/tasks" in url:
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
        i for i, (verb, path) in enumerate(verbs_and_paths) if verb == "GET" and "maptasker_import.prf.xml" in path
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
    assert read_file.findtext("Str[@sr='arg0']") == "/storage/emulated/0/Tasker/maptasker_import.prf.xml"
    assert read_file.findtext("Str[@sr='arg1']") == "%mtimport_xml"
    assert read_file.find("Int[@sr='arg2']").get("val") == "0"  # verbatim, not structured

    import_data = imported.find(".//Action[code='153']")
    assert import_data is not None
    assert import_data.find("Int[@sr='arg0']").get("val") == "1"  # Configuration
    assert import_data.find("Int[@sr='arg1']").get("val") == "0"  # Source, as api/import sends
    assert import_data.findtext("Str[@sr='arg2']") == "%mtimport_xml"


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
/storage/emulated/0/Tasker/maptasker_import.prf.xml
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


def test_offering_a_profile_needs_no_risk_acknowledged(open_device: _FakeImportRequests) -> None:
    """The whole reason this route exists.  Android is handed a file and Tasker shows the
    user what it is about to import, so nothing outside that one Profile is at stake and
    there is no unanswered question to gate on -- unlike import_profile_to_device, which
    refuses to send anything at all without one."""
    return_code, message = _open(open_device)

    assert return_code == 0, message
    assert open_device.uploaded == _STAGED_PROFILE_XML


def test_the_offered_task_opens_the_staged_file_with_a_mime_type(open_device: _FakeImportRequests) -> None:
    """'Open File' (code 102) on the staged path.  The mime type is named rather than left
    blank: with none, Android has only the extension to go on, and '.prf.xml' is not one it
    knows."""
    _open(open_device)

    imported = ET.fromstring(open_device.imported_xml)  # noqa: S314  (built by this program)
    open_file = imported.find(".//Action[code='102']")
    assert open_file is not None
    assert open_file.findtext("Str[@sr='arg0']") == "/storage/emulated/0/Tasker/maptasker_import.prf.xml"
    assert open_file.findtext("Str[@sr='arg1']") == "text/xml"

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
/storage/emulated/0/Tasker/maptasker_import.prf.xml
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
    assert intent.findtext("Str[@sr='arg3']") == "file:///storage/emulated/0/Tasker/maptasker_import.prf.xml"
    assert intent.findtext("Str[@sr='arg7']") == "net.dinglisch.android.taskerm"
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
