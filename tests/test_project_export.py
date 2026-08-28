"""MapTasker standalone Project export (projedit.render_standalone_project_xml) Unit Tests

What is asserted here is one bug and the reasoning that fixes it.

The export used to STRIP <clr>, <id> and <mdate> from the Project element, on the belief
that Tasker's own single-Project export leaves them out.  It does not.  Measured on a real
device, Tasker REFUSES to import a Project with no <id> -- and the file looks perfectly
well-formed from this end, so the failure is silent and total.

The belief came from too small a sample: the derivation diffed four Tasker-produced
.prj.xml files that happened to have no <id>, but eight of the eighteen in this repo's
sample data carry one.  The ones without are TaskerNet downloads, which strip identity on
the way through the service.  That is why these tests assert against a Project that has all
three rather than against "what an export looks like": the whole class of bug here is a
conclusion drawn from whichever examples were nearest.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import projedit, taskerd
from maptasker.src.primitem import PrimeItems

# Home's Scene fires Tasks no <tids> and no Profile <mid0>/<mid1> mentions -- which is the
# whole point of bundling them -- including one from a NESTED Scene and one anonymous inline
# Task (negative id).
#
# One Project carrying every identity child (Home), one carrying none but its name and
# contents (Spare) -- the shape a Project built entirely in-app could reach if it ever lost
# them.  Home's children are in the alphabetical order real Tasker Projects use, with a
# compound <Img> after the metadata, because where a synthesized child LANDS is half of what
# is being tested.
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <dmetric>2800.0,1752.0</dmetric>
  <Project sr="proj0" ve="2">
    <cdate>1700000000000</cdate>
    <clr>4280793266</clr>
    <id>f19b5151-01b6-46f6-8cd5-b3bc1fe0b486</id>
    <mdate>1786121691586</mdate>
    <name>Home</name>
    <pids>100</pids>
    <scenes>Dialog,Gone</scenes>
    <tids>20</tids>
    <Img sr="icn"><nme>mw_action_settings</nme></Img>
  </Project>
  <Project sr="proj1" ve="2">
    <cdate>1700000000000</cdate>
    <name>Spare</name>
    <tids>20</tids>
    <Img sr="icn"><nme>mw_action_settings</nme></Img>
  </Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <mid0>20</mid0>
    <nme>Watching</nme>
  </Profile>
  <Task sr="task20">
    <id>20</id>
    <nme>Opener</nme>
  </Task>
  <Task sr="task30">
    <id>30</id>
    <nme>Tapped</nme>
  </Task>
  <Task sr="task31">
    <id>31</id>
    <nme>Held</nme>
  </Task>
  <Task sr="task32">
    <id>32</id>
    <nme>Stroked</nme>
  </Task>
  <Scene sr="scene0">
    <nme>Dialog</nme>
    <RectElement sr="rect0">
      <clickTask>30</clickTask>
      <longclickTask>31</longclickTask>
    </RectElement>
    <TextElement sr="text0">
      <!-- An anonymous inline Task: no Task element anywhere carries a negative id. -->
      <clickTask>-2</clickTask>
    </TextElement>
    <Scene sr="scene0sub">
      <nme>Nested</nme>
      <RectElement sr="rect1">
        <strokeTask>32</strokeTask>
      </RectElement>
    </Scene>
  </Scene>
  <Scene sr="scene1">
    <nme>Unrelated</nme>
  </Scene>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def loaded() -> None:
    """The PrimeItems tables, built from the fixture the way taskerd does from a file."""
    root = ET.fromstring(_FIXTURE_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100, "language": "English"}

    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file) as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"
    specs[str(len(specs))] = "Img"
    PrimeItems.tasker_arg_specs = specs

    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }


def _exported(project_name: str) -> ET.Element:
    """The <Project> element of a standalone export."""
    return _document(project_name).find("Project")


def _document(project_name: str) -> ET.Element:
    """The whole exported <TaskerData> document."""
    return ET.fromstring(projedit.render_standalone_project_xml(project_name))  # noqa: S314


def test_the_project_keeps_the_id_tasker_imports_by() -> None:
    """The bug this file exists for.  Tasker refuses the whole import of a Project with no
    <id>, and every Project in a real backup has one -- so removing it could only ever cost
    an import."""
    assert _exported("Home").findtext("id") == "f19b5151-01b6-46f6-8cd5-b3bc1fe0b486"


def test_the_project_keeps_its_modified_stamp_and_its_colour() -> None:
    """The other two that went with it.  <mdate> travels with <id> in every real Project,
    and <clr> is the Project's own UI tab colour -- the user's, not this program's to
    discard."""
    exported = _exported("Home")

    assert exported.findtext("mdate") == "1786121691586"
    assert exported.findtext("clr") == "4280793266"


def test_an_identity_that_is_genuinely_missing_is_synthesized() -> None:
    """A safety net rather than the normal path -- but the failure it prevents is silent,
    so a Project that somehow reaches the export without an <id> gets one rather than a
    file Tasker will reject."""
    exported = _exported("Spare")

    assert exported.findtext("id")
    assert exported.findtext("mdate")


def test_a_synthesized_id_is_a_uuid_like_every_real_one() -> None:
    """Matching create_new_project and every real Project.  A Project <id> is a UUID, not
    the small integer a Task or Profile uses -- which is also what makes it unconditionally
    collision-free against those."""
    import uuid  # noqa: PLC0415

    uuid.UUID(_exported("Spare").findtext("id"))  # raises if it is not one


def test_a_synthesized_child_lands_where_tasker_writes_it() -> None:
    """Alphabetical among the simple metadata, ahead of the compound elements.  Appending
    would put <id> after <Img>, which no Tasker-written Project does -- and this export
    already normalizes pids-before-tids on the same reasoning."""
    tags = [child.tag for child in _exported("Spare")]

    assert tags.index("id") < tags.index("mdate") < tags.index("name")
    assert tags.index("cdate") < tags.index("id")
    assert tags.index("mdate") < tags.index("Img")


def test_nothing_is_synthesized_over_something_real() -> None:
    """The net catches only a genuine absence.  Overwriting a Project's real identity with
    a fresh UUID would make every export a different Project to Tasker."""
    first = _exported("Home").findtext("id")
    second = _exported("Home").findtext("id")

    assert first == second == "f19b5151-01b6-46f6-8cd5-b3bc1fe0b486"


def test_the_live_tree_is_left_alone() -> None:
    """The export works on a deep copy.  A synthesized <id> that leaked back into the loaded
    configuration would silently edit the user's Project."""
    projedit.render_standalone_project_xml("Spare")

    live = PrimeItems.tasker_root_elements["all_projects"]["Spare"]["xml"]
    assert live.find("id") is None


# ==========================================
# The Scenes a Project owns, and the screen they were laid out on
#
# A Project's <scenes> names Scenes the export was not shipping, so an import had nothing to
# resolve them against.  <dmetric> is the other half of the same omission: it records the
# device screen the Scenes were measured on, and Tasker writes it exactly when an export
# carries Scenes -- all eleven of the sample .prj.xml files with <Scene> elements have one,
# all seven without have none, and <id> presence cuts across that in both directions, so it
# is a rule about Scenes rather than an artifact of where the files came from.
# ==========================================


def test_the_scenes_the_project_owns_are_bundled() -> None:
    """Without them the exported <scenes> names Scenes that are not in the file."""
    scenes = _document("Home").findall("Scene")

    assert [scene.findtext("nme") for scene in scenes] == ["Dialog"]


def test_a_scene_the_project_does_not_own_is_left_out() -> None:
    """<scenes> is the membership list.  Sweeping in every Scene in the backup would make a
    single-Project export carry someone else's."""
    assert "Unrelated" not in [scene.findtext("nme") for scene in _document("Home").findall("Scene")]


def test_a_named_scene_that_is_missing_is_skipped_not_faked() -> None:
    """'Gone' is named in <scenes> and is not in the backup.  Same treatment as a dangling
    <pids> id -- an empty stand-in would import a broken Scene rather than none."""
    document = _document("Home")

    assert len(document.findall("Scene")) == 1
    assert document.find("Project").findtext("scenes") == "Dialog,Gone"


def test_the_display_metric_leads_the_document() -> None:
    """First element, where Tasker puts it -- Scan.prj.xml, Custom Theme.prj.xml and
    backup.xml all lead with it."""
    document = _document("Home")

    assert [child.tag for child in document][0] == "dmetric"
    assert document.findtext("dmetric") == "2800.0,1752.0"


def test_the_display_metric_is_copied_from_the_loaded_backup() -> None:
    """The right screen size is the one the Scenes were actually laid out on -- the device
    the backup came from.  Inventing one would have Tasker scale Scenes to a device that
    never existed."""
    assert _document("Home").findtext("dmetric") == PrimeItems.xml_root.findtext("dmetric")


def test_an_export_with_no_scenes_has_no_display_metric() -> None:
    """What Tasker does, without exception across the eighteen samples: it is Scene
    metadata, and an export with no Scenes has nothing to describe."""
    document = _document("Spare")

    assert document.findall("Scene") == []
    assert document.find("dmetric") is None


def test_the_elements_come_in_taskers_own_order() -> None:
    """dmetric, Profiles, the Project, Scenes, Tasks -- matched against Scan.prj.xml and
    Custom Theme.prj.xml.  Not Project-first, which is what you would expect from
    <pids>/<tids> being inside <Project>."""
    tags = [child.tag for child in _document("Home")]

    assert tags.index("dmetric") < tags.index("Profile")
    assert tags.index("Profile") < tags.index("Project")
    assert tags.index("Project") < tags.index("Scene")
    assert tags.index("Scene") < tags.index("Task")


# ==========================================
# The Tasks a Scene fires
#
# A Scene button's Task is reached from neither the Project's <tids> nor a Profile's
# <mid0>/<mid1> -- nothing links to it but the Scene element itself.  Exported without it,
# the Scene arrives on the device and its buttons do nothing, which is a failure that looks
# like a successful import.  Measured against this repo's own backup: 17 Projects were
# short a Scene-fired Task, 188 Tasks in total, one Project missing 118 of them.
# ==========================================


def _task_names(project_name: str) -> set[str]:
    return {task.findtext("nme") for task in _document(project_name).findall("Task")}


def test_a_scene_button_brings_its_task_with_it() -> None:
    """Task 30 is fired by <clickTask> and by nothing else -- no <tids>, no Profile."""
    assert "Tapped" in _task_names("Home")


def test_every_handler_type_counts_not_just_taps() -> None:
    """The handler tags come from sysconst.SCENE_TASK_TYPES, the same table
    sceneview.element_tasks reads -- so the export and the Scene view cannot disagree about
    what counts as firing a Task."""
    names = _task_names("Home")

    assert "Held" in names  # <longclickTask>
    assert "Stroked" in names  # <strokeTask>


def test_a_nested_scenes_tasks_come_too() -> None:
    """A Scene can contain another Scene -- eight do in this repo's own backup -- and its
    elements fire Tasks just the same.  'Stroked' is only reachable through the nested one,
    which is why the walk is iter() rather than direct children."""
    assert "Stroked" in _task_names("Home")


def test_an_anonymous_inline_task_is_not_chased() -> None:
    """A negative id is one of Tasker's inline Tasks: no <Task> element anywhere carries
    one (all 18 in this repo's backup), because it lives inside the Scene already and
    travels with it.  Looking for it would find nothing; the danger is only that it not be
    mistaken for a missing Task."""
    from maptasker.src.sceneedit import scene_task_ids  # noqa: PLC0415

    assert scene_task_ids(_document("Home").find("Scene")) == ["30", "31", "32"]


def test_a_task_already_coming_is_not_duplicated() -> None:
    """Task 20 is in <tids> and would also be reachable if a Scene fired it.  Two copies of
    one Task in an import is worse than none."""
    ids = [task.findtext("id") for task in _document("Home").findall("Task")]

    assert len(ids) == len(set(ids))
    assert "20" in ids


def test_scene_tasks_come_after_the_ones_already_accounted_for() -> None:
    """Ordering that costs nothing and is easy to lose: the Project's own <tids> and its
    Profiles' Entry/Exit Tasks keep their places, and the Scene-fired ones follow, rather
    than being re-ordered by which Scene happens to mention them."""
    ids = [task.findtext("id") for task in _document("Home").findall("Task")]

    assert ids.index("20") < ids.index("30")
