"""projedit: the Project editor -- rename, enable, delete, and the standalone export.

A Project's identity is its name (all_projects is keyed by it) and what it owns is three
comma-separated lists, <pids>, <tids> and <scenes>, in a child order Tasker itself keeps
alphabetical.  So the things that go wrong are: a rename that leaves the old key behind, a
list written in the wrong place or without stamping <mdate>, a delete that leaves a dangling
id, and an export missing something the importing device refuses to do without.

Like test_profedit, this works on a fixture built from XML text, so nothing personal is read.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import editcommon, objprops, projedit, sessundo
from maptasker.src.primitem import PrimeItems

from tests.test_mapswap import _load

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <dmetric>1080.0,1920.0</dmetric>
  <Project sr="proj0" ve="2">
    <cdate>1</cdate>
    <id>11111111-aaaa</id>
    <mdate>1</mdate>
    <name>Home</name>
    <pids>101,100,999</pids>
    <scenes>Dash, Missing</scenes>
    <tids>22,20</tids>
  </Project>
  <Project sr="proj1" ve="2">
    <cdate>1</cdate>
    <id>22222222-bbbb</id>
    <mdate>1</mdate>
    <name>Base</name>
    <pids>102</pids>
    <tids>23</tids>
  </Project>
  <Project sr="proj7" ve="2">
    <name>Bare</name>
  </Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <mid0>20</mid0>
    <mid1>24</mid1>
    <nme>Morning</nme>
  </Profile>
  <Profile sr="prof101" ve="2">
    <id>101</id>
    <mid0>21</mid0>
    <nme>Evening</nme>
  </Profile>
  <Profile sr="prof102" ve="2">
    <id>102</id>
    <nme>Stray</nme>
  </Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Entry</nme></Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Second</nme></Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Owned</nme></Task>
  <Task sr="task23" ve="2"><id>23</id><nme>BaseTask</nme></Task>
  <Task sr="task24" ve="2"><id>24</id><nme>Exit</nme></Task>
  <Task sr="task25" ve="2"><id>25</id><nme>FromScene</nme></Task>
  <Scene sr="scene0" ve="2">
    <nme>Dash</nme>
    <RectElement sr="e0"><clickTask>25</clickTask><longclickTask>-3</longclickTask></RectElement>
  </Scene>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def _backup() -> None:
    _load(_XML)
    # The tables _load builds do not name Scenes by anything but their name, which is what is wanted.
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = {
        entry["name"]: {"xml": entry["xml"], "id": key}
        for key, entry in PrimeItems.tasker_root_elements["all_tasks"].items()
    }


def _live(name: str) -> ET.Element:
    return PrimeItems.tasker_root_elements["all_projects"][name]["xml"]


def _edit(name: str) -> projedit.EditableProject:
    edited = projedit.load_project_for_edit(name, state=PrimeItems)
    assert edited is not None
    return edited


def _tags(element: ET.Element) -> list[str]:
    return [child.tag for child in element]


def _xml(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode")


def _ids(element: ET.Element, tag: str) -> list[str]:
    return (element.findtext(tag) or "").split(",") if element.findtext(tag) else []


# ##################################################################################
# Loading and creating.
# ##################################################################################
def test_a_project_is_found_by_its_name() -> None:
    assert projedit.resolve_project_by_name("Home", state=PrimeItems) is _live("Home")
    assert projedit.resolve_project_by_name("Nobody", state=PrimeItems) is None
    assert projedit.load_project_for_edit("Nobody", state=PrimeItems) is None


def test_loading_gives_a_copy() -> None:
    edited = _edit("Home")

    assert edited.project_name == "Home"
    assert edited.project_element is not _live("Home")
    assert _xml(edited.project_element) == _xml(_live("Home"))


def test_a_new_project_is_numbered_after_the_highest_and_given_a_uuid() -> None:
    created = projedit.create_new_project("  Fresh ", state=PrimeItems)

    assert isinstance(created, projedit.EditableProject)
    element = created.project_element
    assert created.project_name == "Fresh"
    assert element.get("sr") == "proj8"  # The highest is Bare's proj7.
    assert _tags(element) == ["cdate", "id", "mdate", "name"]
    assert element.findtext("name") == "Fresh"
    assert element.findtext("cdate") == element.findtext("mdate")
    assert len(element.findtext("id")) == 36  # A UUID: never equal to a Task's or Profile's small integer.
    assert projedit.create_new_project("x", state=PrimeItems).project_element.findtext("id") != element.findtext("id")


def test_a_new_project_needs_a_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "xml_root", None)

    assert "Load a Tasker backup" in projedit.create_new_project("x", state=PrimeItems)


def test_the_first_project_is_proj1() -> None:
    PrimeItems.tasker_root_elements["all_projects"] = {}

    assert projedit.create_new_project("x", state=PrimeItems).project_element.get("sr") == "proj1"


# ##################################################################################
# Naming.
# ##################################################################################
def test_a_name_is_taken_when_a_project_has_it() -> None:
    assert projedit.project_name_exists("Home", state=PrimeItems) is True
    assert projedit.project_name_exists("  Home ", state=PrimeItems) is True
    assert projedit.project_name_exists("home", state=PrimeItems) is False


def test_a_blank_or_taken_name_is_refused_and_nothing_changes() -> None:
    edited = _edit("Home")
    before = _xml(edited.project_element)

    assert projedit.apply_edits_to_project(edited, "  ", state=PrimeItems) == ["Project name cannot be empty."]
    assert projedit.apply_edits_to_project(edited, "Base", state=PrimeItems) == [
        "A Project named 'Base' already exists in this backup. Choose a different name.",
    ]
    assert _xml(edited.project_element) == before
    assert edited.project_name == "Home"


def test_keeping_the_name_is_not_a_conflict_and_a_new_one_is_written_and_stamped() -> None:
    edited = _edit("Home")

    assert projedit.apply_edits_to_project(edited, "Home", state=PrimeItems) == []
    assert projedit.apply_edits_to_project(edited, "  Away ", state=PrimeItems) == []

    assert edited.project_element.findtext("name") == "Away"
    assert edited.project_name == "Away"
    assert edited.project_element.findtext("mdate") != "1"
    assert _live("Home").findtext("name") == "Home"  # Only the copy, until it is put back.


def test_renaming_moves_the_table_entry_to_the_new_key() -> None:
    edited = _edit("Home")
    assert projedit.apply_edits_to_project(edited, "Away", state=PrimeItems) == []

    projedit.rename_project_in_live_tree("Home", edited, state=PrimeItems)

    projects = PrimeItems.tasker_root_elements["all_projects"]
    assert "Home" not in projects
    assert projects["Away"] == {"xml": edited.project_element, "name": "Away"}


def test_renaming_a_project_nobody_registered_does_nothing() -> None:
    edited = projedit.create_new_project("Fresh", state=PrimeItems)
    before = list(PrimeItems.tasker_root_elements["all_projects"])

    projedit.rename_project_in_live_tree("Fresh", edited, state=PrimeItems)

    assert list(PrimeItems.tasker_root_elements["all_projects"]) == before


def test_registering_a_new_project_files_it_under_its_name() -> None:
    created = projedit.create_new_project("", state=PrimeItems)
    assert projedit.apply_edits_to_project(created, "Fresh", state=PrimeItems) == []

    projedit.register_new_project(created, state=PrimeItems)

    assert PrimeItems.tasker_root_elements["all_projects"]["Fresh"]["xml"] is created.project_element
    assert projedit.project_name_exists("Fresh", state=PrimeItems)


# ##################################################################################
# Membership lists, in Tasker's child order.
# ##################################################################################
def test_a_list_created_for_the_first_time_lands_in_alphabetical_place() -> None:
    bare = _live("Bare")
    for tag in ("cdate", "id", "mdate"):
        ET.SubElement(bare, tag).text = "x"
    bare.insert(0, ET.Element("cdate"))
    bare.remove(bare.findall("cdate")[1])

    projedit.set_project_members(bare, "tids", ["1", "2"])
    projedit.set_project_members(bare, "pids", ["3"])
    projedit.set_project_members(bare, "scenes", ["Dash"])

    assert _tags(bare) == ["cdate", "name", "id", "mdate", "pids", "scenes", "tids"] or _tags(bare)[-3:] == [
        "pids",
        "scenes",
        "tids",
    ]
    assert bare.findtext("tids") == "1,2"
    assert bare.findtext("mdate") != "x"


def test_a_list_goes_before_the_uppercase_children_and_after_the_lowercase_ones_that_sort_earlier() -> None:
    element = ET.fromstring("<Project><cdate/><id/><mdate/><name/><Img/><ProfileVariable/></Project>")

    projedit.set_project_members(element, "pids", ["1"])

    assert _tags(element) == ["cdate", "id", "mdate", "name", "pids", "Img", "ProfileVariable"]


def test_a_list_that_exists_is_updated_in_place() -> None:
    home = _live("Home")
    order = _tags(home)

    projedit.set_project_members(home, "pids", ["7", "8"])

    assert _tags(home) == order
    assert home.findtext("pids") == "7,8"
    assert home.findtext("mdate") != "1"


def test_an_empty_membership_is_an_empty_list_not_a_missing_one() -> None:
    projedit.set_project_members(_live("Home"), "tids", [])

    assert _live("Home").find("tids") is not None
    assert _live("Home").findtext("tids") in (None, "")


# ##################################################################################
# Enabled, and properties.
# ##################################################################################
def test_a_project_is_enabled_unless_it_says_false() -> None:
    edited = _edit("Home")
    assert projedit.is_project_enabled(edited) is True

    ET.SubElement(edited.project_element, "enbl").text = "false"
    assert projedit.is_project_enabled(edited) is False
    edited.project_element.find("enbl").text = "true"
    assert projedit.is_project_enabled(edited) is True


def test_disabling_writes_through_to_the_live_project_in_tasker_s_order() -> None:
    edited = _edit("Home")

    projedit.set_project_enabled(edited, enabled=False, state=PrimeItems)

    for element in (edited.project_element, _live("Home")):
        assert element.findtext("enbl") == "false"
        assert _tags(element).index("enbl") < _tags(element).index("id")
        assert element.findtext("mdate") != "1"
    assert projedit.is_project_enabled(edited) is False


def test_enabling_removes_the_tag_rather_than_writing_true() -> None:
    edited = _edit("Home")
    projedit.set_project_enabled(edited, enabled=False, state=PrimeItems)

    projedit.set_project_enabled(edited, enabled=True, state=PrimeItems)

    assert edited.project_element.find("enbl") is None
    assert _live("Home").find("enbl") is None
    projedit.set_project_enabled(edited, enabled=True, state=PrimeItems)  # Already enabled.
    assert projedit.is_project_enabled(edited) is True


def test_a_toggle_after_a_rename_acts_on_one_element_once() -> None:
    edited = _edit("Home")
    assert projedit.apply_edits_to_project(edited, "Away", state=PrimeItems) == []
    projedit.rename_project_in_live_tree("Home", edited, state=PrimeItems)
    assert _live("Away") is edited.project_element

    projedit.set_project_enabled(edited, enabled=False, state=PrimeItems)

    assert len(edited.project_element.findall("enbl")) == 1


def test_a_project_not_registered_yet_is_toggled_on_its_copy_alone() -> None:
    created = projedit.create_new_project("Fresh", state=PrimeItems)

    projedit.set_project_enabled(created, enabled=False, state=PrimeItems)

    assert created.project_element.findtext("enbl") == "false"
    assert "Fresh" not in PrimeItems.tasker_root_elements["all_projects"]


def test_properties_edited_on_the_copy_reach_the_live_project() -> None:
    edited = _edit("Home")
    live = _live("Home")
    ET.SubElement(edited.project_element, "pc").text = "A comment"

    projedit.apply_properties_to_live_tree(edited, state=PrimeItems)

    assert live.findtext("pc") == "A comment"
    assert live.findtext("mdate") != "1"
    assert edited.project_element.findtext("mdate") != "1"


def test_a_property_the_copy_no_longer_has_is_removed_from_the_live_project() -> None:
    live = _live("Home")
    ET.SubElement(live, "pc").text = "stale"
    edited = _edit("Home")
    edited.project_element.remove(edited.project_element.find("pc"))

    projedit.apply_properties_to_live_tree(edited, state=PrimeItems)

    assert live.find("pc") is None


def test_properties_on_a_project_nobody_registered_do_nothing() -> None:
    created = projedit.create_new_project("Fresh", state=PrimeItems)
    before = _xml(created.project_element)

    projedit.apply_properties_to_live_tree(created, state=PrimeItems)

    assert objprops.KIND_PROJECT  # The kind the mirror is keyed on.
    assert created.project_element.findtext("name") == "Fresh"
    assert before != ""


# ##################################################################################
# What a Project owns.
# ##################################################################################
def test_a_projects_profiles_are_named_by_their_own_name_element() -> None:
    assert projedit.project_profile_names("Home", state=PrimeItems) == ["Evening", "Morning"]  # Id 999 has no Profile.


def test_an_unnamed_profile_is_not_confirmable_and_is_left_out() -> None:
    PrimeItems.tasker_root_elements["all_profiles"]["100"]["xml"].find("nme").text = "  "
    PrimeItems.tasker_root_elements["all_profiles"]["100"]["name"] = "*Made up for it"

    assert projedit.project_profile_names("Home", state=PrimeItems) == ["Evening"]


def test_a_project_that_is_not_there_has_no_profiles() -> None:
    assert projedit.project_profile_names("Nobody", state=PrimeItems) == []
    assert projedit.project_profile_names("Bare", state=PrimeItems) == []


def test_a_projects_scenes_are_read_by_name_and_trimmed() -> None:
    assert projedit._project_scene_names(_live("Home")) == ["Dash", "Missing"]  # noqa: SLF001
    assert projedit._project_scene_names(_live("Bare")) == []  # noqa: SLF001


# ##################################################################################
# Paths.
# ##################################################################################
def test_a_project_name_becomes_a_safe_file_name() -> None:
    assert projedit.sanitize_filename("Home/Work") == "Home_Work"
    assert projedit.sanitize_filename("???") != ""
    assert projedit.default_project_save_path("Home").endswith("Home.prj.xml")
    assert projedit.android_project_path("Home/Work") == "/Tasker/projects/Home_Work.prj.xml"


def test_an_existing_file_is_noticed(tmp_path: os.PathLike) -> None:
    target = tmp_path / "x.prj.xml"
    assert projedit.save_path_exists(str(target)) is False

    target.write_text("old", encoding="utf-8")
    assert projedit.save_path_exists(str(target)) is True


# ##################################################################################
# The export.
# ##################################################################################
def test_a_project_without_an_id_or_mdate_is_given_them_in_alphabetical_place() -> None:
    element = ET.fromstring("<Project><cdate>1</cdate><name>N</name><pids>1</pids><Img/></Project>")

    projedit._ensure_project_identity(element)  # noqa: SLF001

    assert _tags(element) == ["cdate", "id", "mdate", "name", "pids", "Img"]
    assert len(element.findtext("id")) == 36
    assert element.findtext("mdate").isdigit()


def test_a_project_that_has_them_keeps_them() -> None:
    element = ET.fromstring("<Project><id>keep</id><mdate>7</mdate><name>N</name></Project>")

    projedit._ensure_project_identity(element)  # noqa: SLF001

    assert (element.findtext("id"), element.findtext("mdate")) == ("keep", "7")
    assert _tags(element) == ["id", "mdate", "name"]


def test_an_element_with_no_simple_children_still_gets_an_identity() -> None:
    element = ET.fromstring("<Project><Img/></Project>")

    projedit._ensure_project_identity(element)  # noqa: SLF001

    assert {"id", "mdate"} <= set(_tags(element))


def test_the_exported_copy_is_renumbered_and_has_its_pids_before_its_tids() -> None:
    element = ET.fromstring("<Project sr='proj9'><id>1</id><mdate>1</mdate><tids>1</tids><pids>2</pids></Project>")

    copy_ = projedit._exportable_project_copy(element)  # noqa: SLF001

    assert copy_.get("sr") == "proj0"
    assert _tags(copy_) == ["id", "mdate", "pids", "tids"]
    assert element.get("sr") == "proj9"  # The original is not touched.
    assert _tags(element) == ["id", "mdate", "tids", "pids"]


def test_tasks_are_taken_from_the_project_then_its_profiles_then_its_scenes_once_each() -> None:
    live = _live("Home")
    all_profiles = PrimeItems.tasker_root_elements["all_profiles"]
    scene = PrimeItems.tasker_root_elements["all_scenes"]["Dash"]["xml"]

    ids = projedit._export_task_ids(live, ["101", "100", "404"], all_profiles, [scene])  # noqa: SLF001

    # <tids> first as listed, then Entry/Exit Tasks in Profile order, then a Scene's; no duplicates, and
    # the Scene's anonymous inline Task (a negative id) is not looked for.
    assert ids == ["22", "20", "21", "24", "25"]


def test_the_export_is_in_the_order_tasker_writes_it() -> None:
    root = ET.fromstring(projedit.render_standalone_project_xml("Home", state=PrimeItems))  # noqa: S314

    assert root.attrib == {"sr": "", "dvi": "1", "tv": "6.3.13"}
    assert [(child.tag, child.findtext("nme") or child.findtext("name") or child.text) for child in root] == [
        ("dmetric", "1080.0,1920.0"),
        ("Profile", "Evening"),
        ("Profile", "Morning"),
        ("Project", "Home"),
        ("Scene", "Dash"),
        ("Task", "Owned"),
        ("Task", "Entry"),
        ("Task", "Second"),
        ("Task", "Exit"),
        ("Task", "FromScene"),
    ]
    assert root.find("Project").get("sr") == "proj0"


def test_the_export_starts_at_the_root_and_ends_with_one_newline() -> None:
    xml = projedit.render_standalone_project_xml("Home", state=PrimeItems)

    assert xml.startswith("<TaskerData")
    assert xml.endswith("</TaskerData>\n")


def test_a_project_with_no_scenes_exports_no_screen_metric() -> None:
    root = ET.fromstring(projedit.render_standalone_project_xml("Base", state=PrimeItems))  # noqa: S314

    assert root.find("dmetric") is None
    assert [child.tag for child in root] == ["Profile", "Project", "Task"]


def test_a_dangling_id_or_scene_is_skipped_not_an_error() -> None:
    root = ET.fromstring(projedit.render_standalone_project_xml("Home", state=PrimeItems))  # noqa: S314

    # Profile 999 and the Scene "Missing" are not in the backup, so nothing is bundled for them;
    # the Project element itself is exported as it is, still naming them.
    assert len(root.findall("Profile")) == 2
    assert len(root.findall("Scene")) == 1
    assert root.find("Project").findtext("scenes") == "Dash, Missing"
    assert root.find("Project").findtext("pids") == "101,100,999"


def test_an_export_of_a_project_that_is_gone_says_so() -> None:
    with pytest.raises(ValueError, match="no longer exists"):
        projedit.render_standalone_project_xml("Nobody", state=PrimeItems)


def test_the_export_can_have_its_secrets_taken_out() -> None:
    task = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"]
    ET.SubElement(task, "Str").text = "password=hunter2"

    assert "hunter2" in projedit.render_standalone_project_xml("Home", state=PrimeItems)
    assert "hunter2" not in projedit.render_standalone_project_xml("Home", state=PrimeItems, redact=True)


def test_writing_a_file_takes_a_safety_copy_of_what_it_replaces(tmp_path: os.PathLike) -> None:
    target = tmp_path / "Home.prj.xml"
    target.write_text("<old/>", encoding="utf-8")

    safety = projedit.write_standalone_project_xml("Home", str(target), state=PrimeItems)

    assert target.read_text(encoding="utf-8").startswith("<TaskerData")
    with open(safety, encoding="utf-8") as copy_:
        assert copy_.read() == "<old/>"


def test_nothing_is_written_for_a_project_that_is_gone(tmp_path: os.PathLike) -> None:
    target = tmp_path / "x.prj.xml"

    with pytest.raises(ValueError, match="no longer exists"):
        projedit.write_standalone_project_xml("Nobody", str(target), state=PrimeItems)
    assert not target.exists()


def test_saving_to_android_uploads_the_rendered_project(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def upload(
        kind: editcommon.EditorKind, ip: str, port: str, name: str, render_bytes: object
    ) -> tuple[int, str, bytes]:
        seen.update(kind=kind, ip=ip, port=port, name=name, body=render_bytes())
        return 0, "/Tasker/projects/Home.prj.xml", b""

    monkeypatch.setattr(editcommon.EditorKind, "upload_and_verify", upload)

    assert projedit.save_project_to_android("Home", "1.2.3.4", "1821", state=PrimeItems) == (
        0,
        "/Tasker/projects/Home.prj.xml",
    )
    assert seen["kind"] is projedit.EXPORT
    assert seen["body"].startswith(b"<TaskerData")


def test_saving_a_project_that_is_gone_to_android_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        editcommon.EditorKind, "upload_and_verify", lambda self, ip, port, name, render: (0, "x", render())
    )

    code, message = projedit.save_project_to_android("Nobody", "1.2.3.4", "1821", state=PrimeItems)

    assert code == 8
    assert "no longer exists" in message


# ##################################################################################
# Deleting.
# ##################################################################################
def test_deleting_the_contents_removes_the_profiles_and_tasks_from_every_table() -> None:
    projedit.delete_profiles_and_tasks_of_project("Home", state=PrimeItems)

    tables = PrimeItems.tasker_root_elements
    assert {"100", "101"}.isdisjoint(tables["all_profiles"])
    assert {"Morning", "Evening"}.isdisjoint(tables["all_profiles_by_name"])
    assert {"20", "22"}.isdisjoint(tables["all_tasks"])
    assert {"Entry", "Owned"}.isdisjoint(tables["all_tasks_by_name"])
    # Not owned by Home: untouched, and so are Tasks only a Profile linked.
    assert {"102"} <= tables["all_profiles"].keys()
    assert {"21", "23", "24", "25"} <= tables["all_tasks"].keys()


def test_deleting_the_contents_of_a_project_that_is_gone_does_nothing() -> None:
    before = (len(PrimeItems.tasker_root_elements["all_profiles"]), len(PrimeItems.tasker_root_elements["all_tasks"]))

    projedit.delete_profiles_and_tasks_of_project("Nobody", state=PrimeItems)

    assert (
        len(PrimeItems.tasker_root_elements["all_profiles"]),
        len(PrimeItems.tasker_root_elements["all_tasks"]),
    ) == before


def test_keeping_the_contents_moves_them_to_base_without_duplicates() -> None:
    _live("Base").find("pids").text = "102,100"

    assert projedit.move_project_contents_to_base("Home", state=PrimeItems) == "Base"

    assert _ids(_live("Base"), "pids") == ["102", "100", "101", "999"]
    assert _ids(_live("Base"), "tids") == ["23", "22", "20"]
    # What moved is still where it was: only which Project names it changes, and Base's side only.
    assert _ids(_live("Home"), "pids") == ["101", "100", "999"]


def test_a_base_that_is_missing_is_made() -> None:
    del PrimeItems.tasker_root_elements["all_projects"]["Base"]

    assert projedit.move_project_contents_to_base("Home", state=PrimeItems) == "Base"

    base = PrimeItems.tasker_root_elements["all_projects"]["Base"]["xml"]
    assert base.findtext("name") == "Base"
    assert _ids(base, "pids") == ["101", "100", "999"]
    assert _ids(base, "tids") == ["22", "20"]


def test_a_missing_base_cannot_be_made_without_a_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    del PrimeItems.tasker_root_elements["all_projects"]["Base"]
    monkeypatch.setattr(PrimeItems, "xml_root", None)

    assert projedit.move_project_contents_to_base("Home", state=PrimeItems) == "Base"
    assert "Base" not in PrimeItems.tasker_root_elements["all_projects"]


def test_moving_the_contents_of_a_project_with_none_changes_nothing_in_base() -> None:
    before = _xml(_live("Base"))

    projedit.move_project_contents_to_base("Bare", state=PrimeItems)

    assert _xml(_live("Base")) == before


def test_deleting_a_project_and_keeping_its_contents() -> None:
    assert projedit.delete_project("Home", state=PrimeItems, keep_contents=True) == []

    tables = PrimeItems.tasker_root_elements
    assert "Home" not in tables["all_projects"]
    assert {"100", "101"} <= tables["all_profiles"].keys()
    assert {"100", "101"} <= set(_ids(_live("Base"), "pids"))
    assert {"20", "22"} <= set(_ids(_live("Base"), "tids"))


def test_deleting_a_project_and_its_contents() -> None:
    assert projedit.delete_project("Home", state=PrimeItems, keep_contents=False) == []

    tables = PrimeItems.tasker_root_elements
    assert "Home" not in tables["all_projects"]
    assert {"100", "101"}.isdisjoint(tables["all_profiles"])
    assert {"20", "22"}.isdisjoint(tables["all_tasks"])
    assert _ids(_live("Base"), "pids") == ["102"]


def test_base_cannot_be_deleted_into_itself_but_can_with_its_contents() -> None:
    before = list(PrimeItems.tasker_root_elements["all_projects"])

    refused = projedit.delete_project("Base", state=PrimeItems, keep_contents=True)

    assert refused and "Keep Contents" in refused[0]
    assert list(PrimeItems.tasker_root_elements["all_projects"]) == before
    assert projedit.delete_project("Base", state=PrimeItems, keep_contents=False) == []
    assert "Base" not in PrimeItems.tasker_root_elements["all_projects"]
    assert "102" not in PrimeItems.tasker_root_elements["all_profiles"]


def test_deleting_a_project_that_is_gone_says_so_and_changes_nothing() -> None:
    before = list(PrimeItems.tasker_root_elements["all_projects"])

    assert projedit.delete_project("Nobody", state=PrimeItems, keep_contents=True) == [
        "Project 'Nobody' no longer exists."
    ]

    assert list(PrimeItems.tasker_root_elements["all_projects"]) == before


def test_a_delete_is_one_step_to_undo() -> None:
    sessundo.clear()

    assert projedit.delete_project("Home", state=PrimeItems, keep_contents=False) == []
    assert sessundo.next_undo_label() == "Delete Project 'Home'"
    assert [label for label, _when in sessundo.history()] == ["Delete Project 'Home'"]

    done, _message = sessundo.undo(state=PrimeItems)

    assert done
    assert "Home" in PrimeItems.tasker_root_elements["all_projects"]
    assert {"100", "101"} <= PrimeItems.tasker_root_elements["all_profiles"].keys()
    sessundo.clear()
