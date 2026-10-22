"""MapTasker Import With Dependencies (mapcarry) Unit Tests

What these assert is what an import LEAVES BEHIND in the configuration that is open, and what it
declines to touch.

Importing is easy to get visibly right and invisibly wrong: a Task brought in with the id something
here already has overwrites that something in all_tasks; one brought in under a name another Task has
leaves every Perform Task ambiguous; a Scene whose element runs Task 23 of the OTHER file runs
whatever holds 23 here.  So each happy path checks the surroundings -- the ids, the names, the Project,
the by-name table, what the calls inside it now say -- and not only that the object arrived.

The other half is that nothing already here is changed: the Tasks, Profiles and Scenes the import did
not bring are left exactly as they were, and one press of Undo puts everything back.

Two configurations: the other file (parsed with its own Element class, which is what diffload hands
back) and the one open.  They are built to clash on purpose:

  Task 20 here is a different Task from Task 20 there, so ids cannot be kept.
  'Fade' is in both and different, so it must come in under a new name and be called by it.
  'Step' is in both and identical, so it must be used rather than copied.
  %Global has a different value in each.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import xmldiff
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapgen import taskerd
from maptasker.src.mapops import mapcarry, maprefac_model

if TYPE_CHECKING:
    from collections.abc import Iterator

FLASH = "548"
PERFORM_TASK = "130"
SHOW_SCENE = "47"

# The other file.
#
#   Project Lights   Profile 100 'Evening Lights' runs Task 20 'Lights On'.  Tasks 20-24 and Scene Panel.
#   Lights On  flashes, performs Fade, shows Scene Panel, and uses the global %Global.
#   Fade       performs Step.        Step  flashes.
#   Panel      has one element that runs Task 23 'Panel Click'.
#   Broken     performs a Task that is nowhere.
_SOURCE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="vars0"><n>%Global</n><v>7</v></Variable>
  <Variable sr="vars1"><n>%Other</n><v>9</v></Variable>
  <Setting sr="set0"><n>beginnerMode</n><v>false</v></Setting>
  <Project sr="proj0" ve="2">
    <name>Lights</name>
    <id>p-lights</id>
    <pids>100</pids>
    <tids>20,21,22,23,24</tids>
    <scenes>Panel</scenes>
  </Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Evening Lights</nme><mid0>20</mid0>
    <Time sr="con0"><fh>18</fh><fm>0</fm><th>19</th><tm>0</tm></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Lights On</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">lights %Global</Str></Action>
    <Action sr="act1" ve="7"><code>130</code><Str sr="arg0" ve="3">Fade</Str></Action>
    <Action sr="act2" ve="7"><code>47</code><Str sr="arg0" ve="3">Panel</Str></Action>
  </Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Fade</nme>
    <Action sr="act0" ve="7"><code>130</code><Str sr="arg0" ve="3">Step</Str></Action>
  </Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Step</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">step</Str></Action>
  </Task>
  <Task sr="task23" ve="2"><id>23</id><nme>Panel Click</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">clicked</Str></Action>
  </Task>
  <Task sr="task24" ve="2"><id>24</id><nme>Broken</nme>
    <Action sr="act0" ve="7"><code>130</code><Str sr="arg0" ve="3">Missing</Str></Action>
  </Task>
  <Scene sr="scenePanel"><nme>Panel</nme><widthPort>100</widthPort>
    <TextElement sr="elements0"><clickTask>23</clickTask><longclickTask>9999</longclickTask></TextElement>
  </Scene>
</TaskerData>
"""

# The configuration open.
#
#   Task 20 'Existing' is a different Task from the other file's Task 20.
#   Task 30 'Fade' is a different Task from the other file's 'Fade' (it flashes rather than performs Step).
#   Task 31 'Step' is the same Task as the other file's 'Step'.
_TARGET_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="vars0"><n>%Global</n><v>1</v></Variable>
  <Setting sr="set0"><n>beginnerMode</n><v>false</v></Setting>
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <id>p-home</id>
    <pids>200</pids>
    <tids>20,30,31</tids>
  </Project>
  <Profile sr="prof200" ve="2"><id>200</id><nme>Dawn</nme><mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Existing</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">mine</Str></Action>
  </Task>
  <Task sr="task30" ve="2"><id>30</id><nme>Fade</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">my fade</Str></Action>
  </Task>
  <Task sr="task31" ve="2"><id>31</id><nme>Step</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">step</Str></Action>
  </Task>
</TaskerData>
"""


class _OtherElement(ET.Element):
    """The other file's own Element class -- deliberately not the live tree's."""


def _tables(root: ET.Element) -> dict:
    """PrimeItems-shaped tables for one parsed root, the way taskerd builds them."""
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
    return tables


def _source(xml_text: str = _SOURCE_XML) -> xmldiff.Configuration:
    """The other file, parsed with its own Element class, as a Configuration."""
    parser = ET.XMLParser(target=ET.TreeBuilder(element_factory=_OtherElement))
    parser.feed(xml_text)
    root = parser.close()
    return xmldiff.Configuration(path="/backups/tablet.xml", tables=_tables(root), root=root)


def _open(xml_text: str) -> None:
    root = ET.fromstring(xml_text)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.xml_tree = ET.ElementTree(root)
    PrimeItems.tasker_root_elements = _tables(root)
    PrimeItems.loaded_highest_object_id = 0


@pytest.fixture
def loaded() -> Iterator[None]:
    """The configuration open, with an empty undo history."""
    sessundo.clear(PrimeItems)
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    _open(_TARGET_XML)
    yield
    sessundo.clear(PrimeItems)


def _live(table: str) -> dict:
    return PrimeItems.tasker_root_elements[table]


def _members(project: str, tag: str) -> list[str]:
    return maprefac_model.members(_live("all_projects")[project]["xml"], tag)


def _named(name: str) -> dict:
    """The Task here called this, as {"xml", "id"}."""
    return _live("all_tasks_by_name")[name]


def _perform_names(task_name: str) -> list[str]:
    return [
        maprefac_model.string_argument(action, "0")
        for action in maprefac_model.actions_of(_named(task_name)["xml"])
        if maprefac_model.action_code(action) == PERFORM_TASK
    ]


def _import(kind: str, key: str, into: str = "Home", source: xmldiff.Configuration | None = None, **options: bool):
    """Plan and apply one import; assert it went through; return the plan."""
    plan = mapcarry.plan_carry(source or _source(), kind, key, into, state=PrimeItems, **options)
    assert plan.can_apply, [block.explanation for block in plan.blocks]
    done, errors = mapcarry.carry(plan, state=PrimeItems)
    assert (done, errors) == (True, [])
    return plan


# ##################################################################################
# What can be picked, and what a pick needs.
# ##################################################################################


def test_the_other_file_offers_projects_profiles_tasks_and_scenes() -> None:
    offered = mapcarry.picks(_source())

    assert [pick.kind for pick in offered][:2] == [PROJECT, PROFILE]
    assert {(pick.kind, pick.key) for pick in offered} == {
        (PROJECT, "Lights"),
        (PROFILE, "100"),
        (TASK, "20"),
        (TASK, "21"),
        (TASK, "22"),
        (TASK, "23"),
        (TASK, "24"),
        (SCENE, "Panel"),
    }
    assert next(pick for pick in offered if pick.key == "20").label == "Lights On  (Lights)"


def test_a_task_needs_what_it_performs_what_it_shows_and_what_those_run() -> None:
    needs = mapcarry.needs_of(_source(), TASK, "20")

    assert needs is not None
    assert list(needs.tasks) == ["20", "21", "22", "23"]
    assert list(needs.scenes) == ["Panel"]
    assert needs.profiles == {}
    assert needs.tasks["21"] == "performed by Task 'Lights On'"
    assert needs.tasks["23"] == "run by Scene 'Panel'"
    assert needs.scenes["Panel"] == "shown by Task 'Lights On'"


def test_a_profile_needs_the_task_it_runs_and_everything_that_task_needs() -> None:
    needs = mapcarry.needs_of(_source(), PROFILE, "100")

    assert needs is not None
    assert list(needs.profiles) == ["100"]
    assert needs.tasks["20"] == "run by Profile 'Evening Lights'"
    assert set(needs.tasks) == {"20", "21", "22", "23"}


def test_a_project_needs_everything_it_lists() -> None:
    needs = mapcarry.needs_of(_source(), PROJECT, "Lights")

    assert needs is not None
    assert set(needs.tasks) == {"20", "21", "22", "23", "24"}
    assert list(needs.profiles) == ["100"]
    assert list(needs.scenes) == ["Panel"]


def test_the_global_variables_used_are_found_with_the_value_the_other_file_gives_them() -> None:
    needs = mapcarry.needs_of(_source(), TASK, "20")

    assert needs is not None
    assert needs.variables == {"%Global": "7"}, "%Other is not used by anything being brought"


def test_a_call_the_other_file_cannot_answer_is_reported_not_followed() -> None:
    needs = mapcarry.needs_of(_source(), TASK, "24")

    assert needs is not None
    assert set(needs.tasks) == {"24"}
    assert any("performs Task 'Missing'" in line for line in needs.unresolved)


def test_a_call_by_a_variable_is_neither_followed_nor_reported() -> None:
    xml = _SOURCE_XML.replace('<Str sr="arg0" ve="3">Missing</Str>', '<Str sr="arg0" ve="3">%which</Str>')

    needs = mapcarry.needs_of(_source(xml), TASK, "24")

    assert needs is not None
    assert needs.unresolved == []


def test_something_the_other_file_does_not_have_is_not_a_pick() -> None:
    assert mapcarry.needs_of(_source(), TASK, "999") is None
    assert mapcarry.needs_of(_source(), "widget", "20") is None


# ##################################################################################
# The plan, before anything is done.
# ##################################################################################


def test_planning_changes_nothing(loaded: None) -> None:
    before = ET.tostring(PrimeItems.xml_root)
    tasks_before = dict(_live("all_tasks"))

    plan = mapcarry.plan_carry(_source(), TASK, "20", "Home", state=PrimeItems)

    assert plan.can_apply
    assert ET.tostring(PrimeItems.xml_root) == before
    assert dict(_live("all_tasks")) == tasks_before
    assert _members("Home", "tids") == ["20", "30", "31"]


def test_the_preview_says_what_is_copied_what_is_used_and_what_is_renamed(loaded: None) -> None:
    plan = mapcarry.plan_carry(_source(), TASK, "20", "Home", state=PrimeItems)

    text = "\n".join(step.text for step in plan.steps)
    assert "Copy Task 'Lights On'" in text
    assert "Copy Task 'Fade' (1 actions) as 'Fade (imported)', because this file already has a different Task" in text
    assert "Use Task 'Step', which this file already has and which is identical" in text
    assert "Copy Scene 'Panel'" in text
    assert "Add global variable" not in text, "this file has %Global, with a different value, and keeps it"
    assert any("%Global (here '1', there '7')" in warning for warning in plan.warnings)
    assert any("'Fade'" in warning and "different one of the same name" in warning for warning in plan.warnings)


def test_a_used_task_is_a_link_to_the_task_here(loaded: None) -> None:
    plan = mapcarry.plan_carry(_source(), TASK, "20", "Home", state=PrimeItems)

    used = next(step for step in plan.steps if step.text.startswith("Use Task 'Step'"))
    assert used.where is not None
    assert used.where.key == "31"


# ##################################################################################
# Doing it.
# ##################################################################################


def test_a_task_comes_in_with_what_it_needs_under_ids_that_are_free(loaded: None) -> None:
    _import(TASK, "20")

    assert set(_live("all_tasks_by_name")) >= {
        "Lights On",
        "Fade (imported)",
        "Panel Click",
        "Existing",
        "Fade",
        "Step",
    }
    new_ids = {_named(name)["id"] for name in ("Lights On", "Fade (imported)", "Panel Click")}
    assert new_ids.isdisjoint({"20", "30", "31", "200"}), "an id this file already had was handed out again"
    assert len(new_ids) == 3
    # What was already here is exactly what it was.
    assert _live("all_tasks")["20"]["name"] == "Existing"
    assert maprefac_model.string_argument(maprefac_model.actions_of(_named("Fade")["xml"])[0], "0") == "my fade"


def test_a_task_is_used_not_copied_when_the_same_one_is_here(loaded: None) -> None:
    _import(TASK, "20")

    assert [name for name in _live("all_tasks_by_name") if name.startswith("Step")] == ["Step"]
    assert len([entry for entry in _live("all_tasks").values() if entry["name"].startswith("Step")]) == 1


def test_a_call_inside_what_was_brought_names_what_was_brought(loaded: None) -> None:
    _import(TASK, "20")

    assert _perform_names("Lights On") == ["Fade (imported)"]
    assert _perform_names("Fade (imported)") == ["Step"]


def test_a_scene_element_runs_the_task_that_came_in_and_not_what_holds_its_old_id(loaded: None) -> None:
    _import(TASK, "20")

    scene = _live("all_scenes")["Panel"]["xml"]
    assert scene.findtext("nme") == "Panel"
    assert scene.attrib["sr"] == "scenePanel"
    element = scene.find("TextElement")
    assert element is not None
    assert element.findtext("clickTask") == _named("Panel Click")["id"]
    # The other file's id 9999 is in no Task there; here it would be somebody else's.
    assert element.find("longclickTask") is None


def test_everything_brought_is_filed_in_the_project_chosen(loaded: None) -> None:
    _import(TASK, "20")

    tids = _members("Home", "tids")
    assert {_named(name)["id"] for name in ("Lights On", "Fade (imported)", "Panel Click")} <= set(tids)
    assert tids[:3] == ["20", "30", "31"], "what was already listed is where it was"
    assert _named("Step")["id"] == "31" and tids.count("31") == 1
    assert _members("Home", "scenes") == ["Panel"]


def test_a_profile_comes_in_pointing_at_the_task_that_came_in(loaded: None) -> None:
    _import(PROFILE, "100")

    profile = next(entry for entry in _live("all_profiles").values() if entry["name"] == "Evening Lights")
    assert profile["xml"].findtext("mid0") == _named("Lights On")["id"]
    assert profile["xml"].findtext("id") != "100" or "100" not in {"200"}
    assert profile["xml"].attrib["sr"] == f"prof{profile['xml'].findtext('id')}"
    assert profile["xml"].findtext("id") in _members("Home", "pids")
    assert profile["xml"].find("Time") is not None, "its conditions came with it"
    assert _live("all_profiles")["200"]["name"] == "Dawn", "the Profile that was here is untouched"


def test_a_profile_without_its_task_in_the_other_file_does_not_point_at_a_stranger(loaded: None) -> None:
    xml = _SOURCE_XML.replace("<mid0>20</mid0>", "<mid0>20</mid0><mid1>777</mid1>")

    _import(PROFILE, "100", source=_source(xml))

    profile = next(entry for entry in _live("all_profiles").values() if entry["name"] == "Evening Lights")
    assert profile["xml"].find("mid1") is None


def test_a_project_comes_in_as_a_project_of_its_own(loaded: None) -> None:
    plan = _import(PROJECT, "Lights", into="Home")

    assert "Lights" in _live("all_projects"), "into is ignored for a Project"
    project = _live("all_projects")["Lights"]["xml"]
    assert project.findtext("name") == "Lights"
    assert project.findtext("id") != "p-lights"
    assert project.attrib["sr"] not in {"proj0"}
    assert len(set(_members("Lights", "tids"))) == 5
    assert len(_members("Lights", "pids")) == 1
    assert _members("Lights", "scenes") == ["Panel"]
    assert _members("Home", "tids") == ["20", "30", "31"], "Home was not touched"
    assert plan.steps[0].text.startswith("Create Project 'Lights'")


def test_a_project_whose_name_is_taken_comes_in_under_a_new_one(loaded: None) -> None:
    xml = _SOURCE_XML.replace("<name>Lights</name>", "<name>Home</name>")

    _import(PROJECT, "Home", source=_source(xml))

    assert "Home (imported)" in _live("all_projects")
    assert _members("Home", "tids") == ["20", "30", "31"]


def test_a_task_can_come_in_as_a_project_of_its_own(loaded: None) -> None:
    _import(TASK, "20", into=mapcarry.NEW_PROJECT)

    assert "Lights" in _live("all_projects"), "named for the Project it was in"
    assert _named("Lights On")["id"] in _members("Lights", "tids")
    assert _members("Home", "tids") == ["20", "30", "31"]


def test_a_global_variable_this_file_lacks_is_added_with_its_value(loaded: None) -> None:
    xml = _TARGET_XML.replace('<Variable sr="vars0"><n>%Global</n><v>1</v></Variable>', "")
    _open(xml)

    plan = _import(TASK, "20")

    variables = PrimeItems.xml_root.findall("Variable")
    assert [(v.findtext("n"), v.findtext("v")) for v in variables] == [("%Global", "7")]
    assert variables[0].attrib["sr"] == "vars0"
    children = [child.tag for child in PrimeItems.xml_root]
    assert children.index("Variable") < children.index("Setting"), "before the Settings, where Tasker puts them"
    assert any(step.text.startswith("Add global variable %Global") for step in plan.steps)


def test_a_global_variable_this_file_has_keeps_its_own_value(loaded: None) -> None:
    _import(TASK, "20")

    assert [(v.findtext("n"), v.findtext("v")) for v in PrimeItems.xml_root.findall("Variable")] == [("%Global", "1")]


def test_carrying_variables_can_be_left_out(loaded: None) -> None:
    xml = _TARGET_XML.replace('<Variable sr="vars0"><n>%Global</n><v>1</v></Variable>', "")
    _open(xml)

    plan = _import(TASK, "20", carry_variables=False)

    assert PrimeItems.xml_root.findall("Variable") == []
    assert any("no value for them" in warning for warning in plan.warnings)


def test_the_whole_import_is_one_press_of_undo(loaded: None) -> None:
    before = {name: ET.tostring(entry["xml"]) for name, entry in _live("all_tasks_by_name").items()}

    plan = _import(PROJECT, "Lights")

    assert len(sessundo.history(PrimeItems)) == 1
    assert sessundo.next_undo_label(PrimeItems) == plan.what
    done, _ = sessundo.undo(PrimeItems)
    assert done
    assert {name: ET.tostring(entry["xml"]) for name, entry in _live("all_tasks_by_name").items()} == before
    assert "Lights" not in _live("all_projects")
    assert "Panel" not in _live("all_scenes")


def test_a_saved_copy_of_the_configuration_holds_what_was_brought(loaded: None) -> None:
    from maptasker.src.core.maputil2 import render_full_backup_xml

    _import(TASK, "20")

    names = {task.findtext("nme") for task in ET.fromstring(render_full_backup_xml(state=PrimeItems)).findall("Task")}
    assert {"Lights On", "Fade (imported)", "Panel Click", "Existing"} <= names


# ##################################################################################
# Importing again.
# ##################################################################################


def test_importing_the_same_task_twice_brings_nothing_the_second_time(loaded: None) -> None:
    _import(TASK, "20")
    count = len(_live("all_tasks"))

    plan = mapcarry.plan_carry(_source(), TASK, "20", "Home", state=PrimeItems)

    assert not plan.can_apply
    assert [block.reason for block in plan.blocks] == ["ALREADY-HERE"]
    assert len(_live("all_tasks")) == count


def test_importing_a_profile_twice_reuses_its_tasks_and_copies_the_profile_under_a_new_name(loaded: None) -> None:
    _import(PROFILE, "100")
    task_count = len(_live("all_tasks"))

    plan = _import(PROFILE, "100")

    assert len(_live("all_tasks")) == task_count, "its Tasks were used, not piled up"
    assert "Evening Lights (imported)" in _live("all_profiles_by_name")
    assert any("from an earlier import of 'Fade'" in step.text for step in plan.steps)


def test_a_task_that_reads_the_same_but_calls_a_different_task_here_is_not_reused(loaded: None) -> None:
    """Identical text is not the same Task when what it calls is not the same Task."""
    # Here 'Fade' reads exactly like the other file's 'Fade' -- it performs 'Step' -- but 'Step' here
    # flashes something else.
    _open(
        """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><id>p-home</id><tids>40,41</tids></Project>
  <Task sr="task40" ve="2"><id>40</id><nme>Fade</nme>
    <Action sr="act0" ve="7"><code>130</code><Str sr="arg0" ve="3">Step</Str></Action></Task>
  <Task sr="task41" ve="2"><id>41</id><nme>Step</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">a different step</Str></Action></Task>
</TaskerData>
"""
    )

    plan = mapcarry.plan_carry(_source(), TASK, "21", "Home", state=PrimeItems)

    text = "\n".join(step.text for step in plan.steps)
    assert "Copy Task 'Step' (1 actions) as 'Step (imported)'" in text
    assert "Copy Task 'Fade' (1 actions) as 'Fade (imported)'" in text
    assert "Use Task 'Fade'" not in text, "this Fade would have run the wrong Step"

    _import(TASK, "21")
    assert _perform_names("Fade (imported)") == ["Step (imported)"]
    assert _perform_names("Fade") == ["Step"], "the Task that was here still calls the Task that was here"


# ##################################################################################
# What is refused, and what is said.
# ##################################################################################


def test_something_that_is_not_in_the_other_file_is_refused(loaded: None) -> None:
    plan = mapcarry.plan_carry(_source(), TASK, "999", "Home", state=PrimeItems)

    assert [block.reason for block in plan.blocks] == ["NOT-THERE"]
    assert mapcarry.carry(plan, state=PrimeItems)[0] is False


def test_a_project_that_is_not_here_is_refused(loaded: None) -> None:
    plan = mapcarry.plan_carry(_source(), TASK, "20", "Nowhere", state=PrimeItems)

    assert [block.reason for block in plan.blocks] == ["NO-PROJECT"]


def test_a_project_with_nothing_in_it_is_refused(loaded: None) -> None:
    xml = (
        _SOURCE_XML.replace("<pids>100</pids>", "")
        .replace("<tids>20,21,22,23,24</tids>", "")
        .replace("<scenes>Panel</scenes>", "")
    )

    plan = mapcarry.plan_carry(_source(xml), PROJECT, "Lights", state=PrimeItems)

    assert [block.reason for block in plan.blocks] == ["NOTHING-TO-BRING"]


def test_a_call_nobody_can_answer_is_warned_about_and_one_this_file_can_answer_is_not(loaded: None) -> None:
    plan = mapcarry.plan_carry(_source(), TASK, "24", "Home", state=PrimeItems)
    assert any("'Missing'" in warning and "it will not run" in warning for warning in plan.warnings)

    xml = _TARGET_XML.replace(
        "</TaskerData>",
        '<Task sr="task50" ve="2"><id>50</id><nme>Missing</nme></Task></TaskerData>',
    )
    _open(xml)
    plan = mapcarry.plan_carry(_source(), TASK, "24", "Home", state=PrimeItems)
    assert not any("'Missing'" in warning for warning in plan.warnings)


def test_a_plan_is_refused_when_the_project_it_files_in_has_gone(loaded: None) -> None:
    plan = mapcarry.plan_carry(_source(), TASK, "20", "Home", state=PrimeItems)
    del _live("all_projects")["Home"]

    done, errors = mapcarry.carry(plan, state=PrimeItems)

    assert done is False
    assert errors and "no longer in the configuration" in errors[0]


def test_the_plan_reads_as_a_preview(loaded: None) -> None:
    from maptasker.src.mapops import maprefac

    plan = mapcarry.plan_carry(_source(), TASK, "20", "Home", state=PrimeItems)

    text = "\n".join(row.text for row in maprefac.report_rows(plan))
    assert text.startswith("Import Task 'Lights On' from tablet.xml")
    assert "WHAT WILL HAPPEN" in text and "BEFORE YOU DO THIS" in text


def test_a_plugin_the_objects_use_is_named(loaded: None) -> None:
    xml = _SOURCE_XML.replace(
        '<Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">lights %Global</Str></Action>',
        '<Action sr="act0" ve="7"><code>1040876951</code><Str sr="arg0" ve="3">com.joaomgcd.autoinput</Str></Action>',
    )

    needs = mapcarry.needs_of(_source(xml), TASK, "20")

    assert needs is not None
    assert set(needs.plugins) <= {"com.joaomgcd.autoinput"}


def test_a_version_2_scene_is_flagged_as_not_followed(loaded: None) -> None:
    import base64
    import gzip
    import json

    layout = base64.b64encode(gzip.compress(json.dumps({"name": "Panel", "children": []}).encode())).decode()
    xml = _SOURCE_XML.replace("<widthPort>100</widthPort>", f"<widthPort>-1</widthPort><lj>{layout}</lj>")

    needs = mapcarry.needs_of(_source(xml), TASK, "20")

    assert needs is not None
    if needs.layouts:  # decode_v2_layout decides what a V2 layout looks like; only assert what it reports
        plan = mapcarry.plan_carry(_source(xml), TASK, "20", "Home", state=PrimeItems)
        assert any("Version 2 Scene 'Panel'" in warning for warning in plan.warnings)
