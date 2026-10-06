"""sceneedit: the Scene editor's model -- creating, renaming, applying, deleting, exporting.

A Scene differs from the other three editable objects in one way that drives most of what is
tested here: it has no <id>.  Its name is its identity, so the name lives in several places
that have to move together (the <nme>, the sr attribute, a Version 2 Scene's embedded layout,
the all_scenes key, and every Project's comma-separated <scenes> list), and an edit has to be
transplanted onto the live element rather than swapped in or the saved file ends up with two
Scenes where there was one.

The designers (sceneedit_legacy, sceneedit_v2) are tested elsewhere; this is the part around them.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import editcommon, sceneedit, sessundo
from maptasker.src.primitem import PrimeItems

from tests.test_mapswap import _load

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <dmetric>1080.0,1920.0</dmetric>
  <Project sr="proj0" ve="2">
    <id>p1</id>
    <mdate>1</mdate>
    <name>Home</name>
    <scenes>Alpha,Dash,Zulu</scenes>
  </Project>
  <Project sr="proj1" ve="2">
    <id>p2</id>
    <mdate>1</mdate>
    <name>Work</name>
    <scenes>Dash</scenes>
  </Project>
  <Project sr="proj2" ve="2"><id>p3</id><name>Empty</name></Project>
  <Task sr="task25" ve="2"><id>25</id><nme>Clicked</nme></Task>
  <Task sr="task26" ve="2"><id>26</id><nme>Held</nme></Task>
  <Scene sr="sceneDash">
    <cdate>1</cdate>
    <edate>1</edate>
    <heightLand>-1</heightLand>
    <heightPort>800</heightPort>
    <nme>Dash</nme>
    <widthLand>-1</widthLand>
    <widthPort>600</widthPort>
    <RectElement sr="elements0">
      <clickTask>25</clickTask>
      <longclickTask>-3</longclickTask>
    </RectElement>
    <TextElement sr="elements1">
      <longclickTask>26</longclickTask>
      <clickTask>25</clickTask>
    </TextElement>
  </Scene>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def _backup() -> None:
    _load(_XML)


def _live(name: str) -> ET.Element:
    return PrimeItems.tasker_root_elements["all_scenes"][name]["xml"]


def _project(name: str) -> ET.Element:
    return PrimeItems.tasker_root_elements["all_projects"][name]["xml"]


def _edit(name: str) -> sceneedit.EditableScene:
    edited = sceneedit.load_scene_for_edit(name, state=PrimeItems)
    assert edited is not None
    return edited


def _new(name: str, version: str = sceneedit.SCENE_VERSION_LEGACY, **kwargs: str) -> sceneedit.EditableScene:
    created = sceneedit.create_new_scene(name, version, state=PrimeItems, **kwargs)
    assert isinstance(created, sceneedit.EditableScene)
    return created


def _tags(element: ET.Element) -> list[str]:
    return [child.tag for child in element]


def _xml(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode")


def _v2_alpha() -> sceneedit.EditableScene:
    """A registered Version 2 Scene, so a rename has a layout name to keep in step."""
    created = _new("Alpha", sceneedit.SCENE_VERSION_V2)
    sceneedit.register_new_scene(created, state=PrimeItems)
    return _edit("Alpha")


# ##################################################################################
# Which kind of Scene.
# ##################################################################################
def test_a_scene_with_a_layout_child_is_version_two() -> None:
    assert sceneedit.is_v2_scene(_live("Dash")) is False
    assert sceneedit.scene_version(_live("Dash")) == "Legacy"
    assert sceneedit.is_v2_scene(_new("N", "Version 2").scene_element) is True
    assert sceneedit.scene_version(_new("N", "Version 2").scene_element) == "Version 2"


# ##################################################################################
# The layout encoding.
# ##################################################################################
def test_a_layout_survives_encoding_and_decoding() -> None:
    element = ET.Element("Scene")
    layout = {"root": {"type": "Column", "children": [{"type": "Text", "text": "café – ü"}]}, "name": "N"}

    sceneedit.encode_v2_layout(element, layout)

    assert sceneedit.decode_v2_layout(element) == layout


def test_the_encoding_is_the_one_tasker_writes_so_an_untouched_scene_is_byte_identical() -> None:
    """Compact separators, gzip level 6 and a zeroed mtime: anything else makes every save differ."""
    element = ET.Element("Scene")
    sceneedit.encode_v2_layout(element, {"a": 1, "b": [1, 2]})
    first = element.findtext("lj")
    sceneedit.encode_v2_layout(element, {"a": 1, "b": [1, 2]})

    assert element.findtext("lj") == first
    raw = base64.b64decode(first)
    assert raw[:2] == b"\x1f\x8b"
    assert raw[4:8] == b"\x00\x00\x00\x00"  # The mtime header.
    assert json.loads(gzip.decompress(raw)) == {"a": 1, "b": [1, 2]}
    assert gzip.decompress(raw) == b'{"a":1,"b":[1,2]}'


def test_a_layout_that_cannot_be_read_is_none_and_is_left_alone() -> None:
    legacy = _live("Dash")
    assert sceneedit.decode_v2_layout(legacy) is None

    broken = ET.Element("Scene")
    ET.SubElement(broken, "lj").text = "not base64 at all!!"
    assert sceneedit.decode_v2_layout(broken) is None

    empty = ET.Element("Scene")
    ET.SubElement(empty, "lj")
    assert sceneedit.decode_v2_layout(empty) is None


@pytest.mark.parametrize(
    "bad",
    ["", "####", base64.b64encode(b"plain, not gzip").decode(), base64.b64encode(gzip.compress(b"{not json")).decode()],
)
def test_a_bad_encoding_is_reported_as_text_not_raised(bad: str) -> None:
    result = sceneedit.decompress_gzip_json(bad)

    assert isinstance(result, str)
    assert result.startswith("An error occurred")


def test_a_layout_that_is_json_but_not_an_object_is_not_a_layout() -> None:
    element = ET.Element("Scene")
    ET.SubElement(element, "lj").text = base64.b64encode(gzip.compress(b"[1, 2]")).decode()

    assert sceneedit.decode_v2_layout(element) is None


def test_renaming_a_layout_that_cannot_be_read_leaves_it_as_it_was() -> None:
    broken = ET.Element("Scene")
    ET.SubElement(broken, "lj").text = "garbage"

    sceneedit._rename_v2_layout(broken, "New")  # noqa: SLF001

    assert broken.findtext("lj") == "garbage"
    sceneedit._rename_v2_layout(ET.Element("Scene"), "New")  # A Legacy Scene: nothing to do.  # noqa: SLF001


# ##################################################################################
# Creating a Scene.
# ##################################################################################
def test_a_new_legacy_scene_has_a_portrait_canvas_and_the_children_real_scenes_have() -> None:
    created = _new("  Fresh ")
    element = created.scene_element

    assert created.scene_name == "Fresh"
    assert element.get("sr") == "sceneFresh"
    assert _tags(element) == ["cdate", "edate", "heightLand", "heightPort", "nme", "widthLand", "widthPort"]
    assert [element.findtext(tag) for tag in ("widthPort", "heightPort", "widthLand", "heightLand")] == [
        "600",
        "800",
        "-1",
        "-1",
    ]
    assert element.findtext("cdate") == element.findtext("edate")
    assert element.find("lj") is None
    assert created.element_renames == []


def test_a_new_version_two_scene_has_no_canvas_and_a_layout_in_its_place() -> None:
    element = _new("V", "Version 2").scene_element

    assert _tags(element) == ["cdate", "edate", "heightLand", "heightPort", "lj", "nme", "widthLand", "widthPort"]
    assert [element.findtext(tag) for tag in ("widthPort", "heightPort", "widthLand", "heightLand")] == ["-1"] * 4
    layout = sceneedit.decode_v2_layout(element)
    assert layout["name"] == "V"
    assert layout["root"]["type"] == "Column"
    assert layout["root"]["children"] == []


@pytest.mark.parametrize(
    ("template", "root_type"),
    [("Empty", "Column"), ("Titled dialog", "Column"), ("Dialog with buttons", "Column"), ("Full screen", "Scaffold")],
)
def test_each_version_two_template_makes_the_tree_it_names(template: str, root_type: str) -> None:
    layout = sceneedit.decode_v2_layout(_new("T", "Version 2", template=template).scene_element)

    assert layout["root"]["type"] == root_type
    assert layout["name"] == "T"


def test_a_dialog_with_buttons_reports_which_button_was_pressed() -> None:
    layout = sceneedit.v2_template_layout("D", "Dialog with buttons")

    row = layout["root"]["children"][-1]
    assert row["id"] == "button_row"
    set_actions = [
        action
        for button in row["children"]
        for handler in button["eventHandlers"]["handlers"]
        for action in handler["actions"]
        if action["type"] == "SetVariable"
    ]
    assert [(action["variable"], action["value"]) for action in set_actions] == [
        ("sd_button", "Cancel"),
        ("sd_button", "OK"),
    ]
    # A dialog without buttons has the header and body only.
    assert [child["id"] for child in sceneedit.v2_template_layout("D", "Titled dialog")["root"]["children"]] == [
        "header",
        "content",
    ]


def test_an_unknown_template_is_a_blank_scene() -> None:
    assert sceneedit.v2_template_layout("X", "Nonsense") == sceneedit.new_v2_layout("X")
    assert sceneedit.V2_DEFAULT_TEMPLATE == "Empty"


def test_a_new_scene_needs_a_backup_and_a_kind_that_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "is not a kind of Scene" in sceneedit.create_new_scene("x", "Version 3", state=PrimeItems)

    monkeypatch.setattr(PrimeItems, "xml_root", None)
    assert "Load a Tasker backup" in sceneedit.create_new_scene("x", state=PrimeItems)


# ##################################################################################
# Loading, naming and the rename itself.
# ##################################################################################
def test_a_scene_is_found_by_name_and_loaded_as_a_copy() -> None:
    assert sceneedit.resolve_scene_by_name("Dash", state=PrimeItems) is _live("Dash")
    assert sceneedit.resolve_scene_by_name("Nobody", state=PrimeItems) is None
    assert sceneedit.load_scene_for_edit("Nobody", state=PrimeItems) is None

    edited = _edit("Dash")
    assert edited.scene_element is not _live("Dash")
    assert _xml(edited.scene_element) == _xml(_live("Dash"))


def test_a_name_is_taken_when_a_scene_has_it() -> None:
    assert sceneedit.scene_name_exists("Dash", state=PrimeItems) is True
    assert sceneedit.scene_name_exists("  Dash ", state=PrimeItems) is True
    assert sceneedit.scene_name_exists("dash", state=PrimeItems) is False


@pytest.mark.parametrize(
    ("name", "fragment"),
    [("  ", "cannot be empty"), ("Big,Red", "cannot contain a comma"), ("Alpha", "already exists")],
)
def test_a_bad_name_is_refused_and_nothing_changes(name: str, fragment: str) -> None:
    _v2_alpha()
    edited = _edit("Dash")
    before = _xml(edited.scene_element)

    errors = sceneedit.apply_edits_to_scene(edited, name, state=PrimeItems)

    assert len(errors) == 1
    assert fragment in errors[0]
    assert _xml(edited.scene_element) == before
    assert edited.scene_name == "Dash"


def test_a_rename_writes_the_name_everywhere_the_scene_keeps_it() -> None:
    edited = _v2_alpha()

    assert sceneedit.apply_edits_to_scene(edited, "  Beta ", state=PrimeItems) == []

    element = edited.scene_element
    assert element.findtext("nme") == "Beta"
    assert element.get("sr") == "sceneBeta"
    assert sceneedit.decode_v2_layout(element)["name"] == "Beta"
    assert edited.scene_name == "Beta"
    assert element.findtext("edate") != "1"


def test_keeping_the_name_is_not_a_conflict() -> None:
    assert sceneedit.apply_edits_to_scene(_edit("Dash"), "Dash", state=PrimeItems) == []


def test_the_size_is_written_and_the_scene_stamped() -> None:
    edited = _edit("Dash")

    sceneedit.set_scene_dimensions(edited, {"widthPort": "720", "heightPort": "1280"})

    assert (edited.scene_element.findtext("widthPort"), edited.scene_element.findtext("heightPort")) == ("720", "1280")
    assert edited.scene_element.findtext("edate") != "1"
    assert _live("Dash").findtext("widthPort") == "600"
    assert [tag for tag, _label in sceneedit.SCENE_DIMENSION_FIELDS] == [
        "widthPort",
        "heightPort",
        "widthLand",
        "heightLand",
    ]


# ##################################################################################
# Registering, and which Project owns what.
# ##################################################################################
def test_registering_files_the_scene_under_its_name() -> None:
    created = _new("Fresh")

    sceneedit.register_new_scene(created, state=PrimeItems)

    assert PrimeItems.tasker_root_elements["all_scenes"]["Fresh"] == {"xml": created.scene_element, "name": "Fresh"}
    assert sceneedit.scene_name_exists("Fresh", state=PrimeItems)


def test_adding_to_a_project_appends_the_name_once_and_stamps_the_project() -> None:
    sceneedit.add_scene_to_project("Fresh", "Home", state=PrimeItems)
    sceneedit.add_scene_to_project("Fresh", "Home", state=PrimeItems)

    assert _project("Home").findtext("scenes") == "Alpha,Dash,Zulu,Fresh"
    assert _project("Home").findtext("mdate") != "1"


def test_a_project_with_no_scenes_gets_the_list() -> None:
    sceneedit.add_scene_to_project("Fresh", "Empty", state=PrimeItems)

    assert _project("Empty").findtext("scenes") == "Fresh"


def test_adding_to_a_project_that_is_not_there_does_nothing() -> None:
    before = [_xml(entry["xml"]) for entry in PrimeItems.tasker_root_elements["all_projects"].values()]

    sceneedit.add_scene_to_project("Fresh", "Nowhere", state=PrimeItems)

    assert [_xml(entry["xml"]) for entry in PrimeItems.tasker_root_elements["all_projects"].values()] == before


def test_the_scene_names_of_a_project_ignore_blanks() -> None:
    element = ET.fromstring("<Project><scenes>A,,B,</scenes></Project>")

    assert sceneedit._project_scene_names(element) == ["A", "B"]  # noqa: SLF001
    assert sceneedit._project_scene_names(ET.fromstring("<Project/>")) == []  # noqa: SLF001
    assert sceneedit._project_scene_names(ET.fromstring("<Project><scenes/></Project>")) == []  # noqa: SLF001


def test_the_first_project_that_lists_a_scene_owns_it() -> None:
    assert sceneedit.project_owning_scene("Dash", state=PrimeItems) == "Home"
    assert sceneedit.project_owning_scene("Nobody", state=PrimeItems) == ""
    assert sceneedit.project_owning_scene("", state=PrimeItems) == ""


def test_a_scenes_list_is_removed_when_the_last_scene_goes_rather_than_left_empty() -> None:
    element = ET.fromstring("<Project><scenes>A</scenes></Project>")

    sceneedit._set_project_scene_names(element, [])  # noqa: SLF001
    assert element.find("scenes") is None
    sceneedit._set_project_scene_names(element, [])  # Nothing there to remove.  # noqa: SLF001

    sceneedit._set_project_scene_names(element, ["A", "B"])  # noqa: SLF001
    assert element.findtext("scenes") == "A,B"


# ##################################################################################
# Putting an edit back into the loaded backup.
# ##################################################################################
def test_an_edit_is_transplanted_onto_the_live_element_not_swapped_in() -> None:
    live = _live("Dash")
    edited = _edit("Dash")
    sceneedit.set_scene_dimensions(edited, {"widthPort": "720"})

    sceneedit.apply_edited_scene_to_live_tree("Dash", edited, state=PrimeItems)

    assert _live("Dash") is live
    assert live.findtext("widthPort") == "720"
    assert edited.scene_element is live  # From here on the dialog edits the real one.
    # A second save from the same dialog transplants onto itself and changes nothing.
    before = _xml(live)
    sceneedit.apply_edited_scene_to_live_tree("Dash", edited, state=PrimeItems)
    assert _xml(live) == before


def test_a_rename_moves_the_table_entry_and_every_project_list_keeping_the_order() -> None:
    live = _live("Dash")
    edited = _edit("Dash")
    assert sceneedit.apply_edits_to_scene(edited, "Mid", state=PrimeItems) == []

    sceneedit.apply_edited_scene_to_live_tree("Dash", edited, state=PrimeItems)

    scenes = PrimeItems.tasker_root_elements["all_scenes"]
    assert "Dash" not in scenes
    assert scenes["Mid"] == {"xml": live, "name": "Mid"}
    assert live.findtext("nme") == "Mid"
    assert live.get("sr") == "sceneMid"
    assert _project("Home").findtext("scenes") == "Alpha,Mid,Zulu"  # Replaced in place, not moved to the end.
    assert _project("Work").findtext("scenes") == "Mid"
    assert _project("Home").findtext("mdate") != "1"
    assert edited.scene_name == "Mid"


def test_a_project_that_does_not_list_the_scene_is_left_alone() -> None:
    before = _xml(_project("Empty"))
    edited = _edit("Dash")
    assert sceneedit.apply_edits_to_scene(edited, "Mid", state=PrimeItems) == []

    sceneedit.apply_edited_scene_to_live_tree("Dash", edited, state=PrimeItems)

    assert _xml(_project("Empty")) == before


def test_pending_element_renames_are_applied_to_the_tasks_at_this_point_and_no_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    # The list is cleared once applied, so what it held has to be copied at the time.
    monkeypatch.setattr(
        sceneedit, "apply_element_renames_to_tasks", lambda scene, renames, **_: calls.append((scene, list(renames)))
    )
    edited = _edit("Dash")
    edited.element_renames.append(("Old", "New"))

    assert calls == []
    sceneedit.apply_edited_scene_to_live_tree("Dash", edited, state=PrimeItems)

    assert calls == [("Dash", [("Old", "New")])]
    assert edited.element_renames == []


def test_applying_an_edit_to_a_scene_nobody_registered_does_nothing() -> None:
    created = _new("Fresh")
    created.element_renames.append(("a", "b"))

    sceneedit.apply_edited_scene_to_live_tree("Fresh", created, state=PrimeItems)

    assert "Fresh" not in PrimeItems.tasker_root_elements["all_scenes"]
    assert created.element_renames == [("a", "b")]  # Not applied: there was nothing to apply them to.


# ##################################################################################
# Deleting.
# ##################################################################################
def test_deleting_a_scene_removes_it_from_the_table_and_from_every_project() -> None:
    assert sceneedit.delete_scene("Dash", state=PrimeItems) == []

    assert "Dash" not in PrimeItems.tasker_root_elements["all_scenes"]
    assert _project("Home").findtext("scenes") == "Alpha,Zulu"
    assert _project("Work").find("scenes") is None  # The last one: the element goes, it is not left empty.
    assert _project("Work").findtext("mdate") != "1"
    # The Tasks its elements fired belong to a Project and stay.
    assert {"25", "26"} <= PrimeItems.tasker_root_elements["all_tasks"].keys()


def test_deleting_a_scene_that_is_gone_says_so_and_changes_nothing() -> None:
    before = _xml(_project("Home"))

    assert sceneedit.delete_scene("Nobody", state=PrimeItems) == ["Scene 'Nobody' no longer exists."]

    assert _xml(_project("Home")) == before


def test_a_delete_is_one_step_to_undo() -> None:
    sessundo.clear()

    assert sceneedit.delete_scene("Dash", state=PrimeItems) == []
    assert sessundo.next_undo_label() == "Delete Scene 'Dash'"
    done, _message = sessundo.undo(state=PrimeItems)

    assert done
    assert "Dash" in PrimeItems.tasker_root_elements["all_scenes"]
    assert "Dash" in _project("Home").findtext("scenes")
    sessundo.clear()


# ##################################################################################
# Paths and the export.
# ##################################################################################
def test_a_scene_name_becomes_a_safe_file_name() -> None:
    assert sceneedit.sanitize_filename("A/B") == "A_B"
    assert sceneedit.sanitize_filename("???") != ""
    assert sceneedit.default_scene_save_path("Dash").endswith("Dash.scn.xml")
    assert sceneedit.android_scene_path("A/B") == "/Tasker/scenes/A_B.scn.xml"


def test_an_existing_file_is_noticed(tmp_path: os.PathLike) -> None:
    target = tmp_path / "x.scn.xml"
    assert sceneedit.save_path_exists(str(target)) is False

    target.write_text("old", encoding="utf-8")
    assert sceneedit.save_path_exists(str(target)) is True


def test_the_tasks_a_scene_fires_are_listed_in_document_order_and_inline_ones_are_not() -> None:
    assert sceneedit.scene_task_ids(_live("Dash")) == ["25", "26", "25"]  # The -3 is an inline Task: it travels inside.
    assert sceneedit.scene_task_ids(ET.fromstring("<Scene/>")) == []
    assert sceneedit.scene_task_ids(
        ET.fromstring("<Scene><clickTask> </clickTask><clickTask>7</clickTask></Scene>")
    ) == ["7"]


def test_the_export_is_the_screen_metric_the_scene_and_the_tasks_it_fires_once_each() -> None:
    root = ET.fromstring(sceneedit.render_standalone_scene_xml("Dash", state=PrimeItems))  # noqa: S314

    assert root.attrib == {"sr": "", "dvi": "1", "tv": "6.3.13"}
    assert [(child.tag, child.findtext("nme")) for child in root] == [
        ("dmetric", None),
        ("Scene", "Dash"),
        ("Task", "Clicked"),
        ("Task", "Held"),
    ]
    assert root.find("Scene").get("sr") == "sceneDash"


def test_a_backup_with_no_screen_metric_exports_without_one(monkeypatch: pytest.MonkeyPatch) -> None:
    PrimeItems.xml_root.remove(PrimeItems.xml_root.find("dmetric"))

    root = ET.fromstring(sceneedit.render_standalone_scene_xml("Dash", state=PrimeItems))  # noqa: S314

    assert root.find("dmetric") is None


def test_a_task_that_is_not_in_the_backup_is_skipped() -> None:
    del PrimeItems.tasker_root_elements["all_tasks"]["26"]

    root = ET.fromstring(sceneedit.render_standalone_scene_xml("Dash", state=PrimeItems))  # noqa: S314

    assert [task.findtext("nme") for task in root.findall("Task")] == ["Clicked"]


def test_an_export_of_a_scene_that_is_gone_says_so() -> None:
    with pytest.raises(ValueError, match="no longer exists"):
        sceneedit.render_standalone_scene_xml("Nobody", state=PrimeItems)


def test_the_export_can_have_its_secrets_taken_out() -> None:
    ET.SubElement(_live("Dash"), "Str").text = "password=hunter2"

    assert "hunter2" in sceneedit.render_standalone_scene_xml("Dash", state=PrimeItems)
    assert "hunter2" not in sceneedit.render_standalone_scene_xml("Dash", state=PrimeItems, redact=True)


def test_the_export_is_of_the_loaded_scene_and_leaves_it_alone() -> None:
    before = _xml(_live("Dash"))

    sceneedit.render_standalone_scene_xml("Dash", state=PrimeItems)

    assert _xml(_live("Dash")) == before


def test_writing_a_file_takes_a_safety_copy_of_what_it_replaces(tmp_path: os.PathLike) -> None:
    target = tmp_path / "Dash.scn.xml"
    target.write_text("<old/>", encoding="utf-8")

    safety = sceneedit.write_standalone_scene_xml("Dash", str(target), state=PrimeItems)

    assert target.read_text(encoding="utf-8").startswith("<TaskerData")
    with open(safety, encoding="utf-8") as copy_:
        assert copy_.read() == "<old/>"


def test_nothing_is_written_for_a_scene_that_is_gone(tmp_path: os.PathLike) -> None:
    target = tmp_path / "x.scn.xml"

    with pytest.raises(ValueError, match="no longer exists"):
        sceneedit.write_standalone_scene_xml("Nobody", str(target), state=PrimeItems)
    assert not target.exists()


def test_saving_to_android_uploads_the_rendered_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def upload(
        kind: editcommon.EditorKind, ip: str, port: str, name: str, render_bytes: object
    ) -> tuple[int, str, bytes]:
        seen.update(kind=kind, ip=ip, port=port, name=name, body=render_bytes())
        return 0, "/Tasker/scenes/Dash.scn.xml", b""

    monkeypatch.setattr(editcommon.EditorKind, "upload_and_verify", upload)

    assert sceneedit.save_scene_to_android("Dash", "1.2.3.4", "1821", state=PrimeItems) == (
        0,
        "/Tasker/scenes/Dash.scn.xml",
    )
    assert seen["kind"] is sceneedit.EXPORT
    assert (seen["ip"], seen["port"], seen["name"]) == ("1.2.3.4", "1821", "Dash")
    assert seen["body"].startswith(b"<TaskerData")


def test_saving_a_scene_that_is_gone_to_android_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        editcommon.EditorKind, "upload_and_verify", lambda self, ip, port, name, render: (0, "x", render())
    )

    code, message = sceneedit.save_scene_to_android("Nobody", "1.2.3.4", "1821", state=PrimeItems)

    assert code == 8
    assert "no longer exists" in message


# ##################################################################################
# Cancel: putting the session's edits back.
# ##################################################################################
def test_cancelling_an_unchanged_session_has_nothing_to_undo() -> None:
    edited = _edit("Dash")
    snapshot = sceneedit.session_snapshot(edited)

    assert sceneedit.revert_session(edited, snapshot) is False
    assert _xml(edited.scene_element) == _xml(_live("Dash"))


def test_cancelling_restores_the_element_in_place_and_says_it_did() -> None:
    edited = _edit("Dash")
    element = edited.scene_element
    snapshot = sceneedit.session_snapshot(edited)
    sceneedit.set_scene_dimensions(edited, {"widthPort": "999"})
    ET.SubElement(element, "Extra")
    element.set("sr", "sceneChanged")

    assert sceneedit.revert_session(edited, snapshot) is True

    assert edited.scene_element is element  # The dialog and the preview hold this object.
    assert element.findtext("widthPort") == "600"
    assert element.find("Extra") is None
    assert element.get("sr") == "sceneDash"


def test_pending_element_renames_count_as_a_change_and_are_dropped() -> None:
    edited = _edit("Dash")
    snapshot = sceneedit.session_snapshot(edited)
    edited.element_renames.append(("a", "b"))

    assert sceneedit.revert_session(edited, snapshot) is True
    assert edited.element_renames == []


def test_a_version_two_session_lives_in_its_layout_dict_and_cancel_reverts_that() -> None:
    edited = _v2_alpha()
    snapshot = sceneedit.session_snapshot(edited)
    layout = sceneedit.decode_v2_layout(edited.scene_element)
    original = json.loads(json.dumps(layout))

    # The element is untouched: the session's work is in the dict until a save encodes it.
    layout["root"]["children"].append({"type": "Text", "id": "added"})
    assert sceneedit.revert_session(edited, snapshot, layout) is True

    assert layout == original


def test_a_version_two_session_that_changed_nothing_has_nothing_to_undo() -> None:
    edited = _v2_alpha()
    snapshot = sceneedit.session_snapshot(edited)
    layout = sceneedit.decode_v2_layout(edited.scene_element)

    assert sceneedit.revert_session(edited, snapshot, layout) is False
