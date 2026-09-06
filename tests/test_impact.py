"""MapTasker Impact Analysis Unit Tests

impact.py answers "what breaks if I delete this?" from the lookup tables
taskerd.get_the_xml_data builds, so these tests build those tables from a small XML
fixture rather than loading a backup or standing up the GUI -- the same arrangement
test_healthck.py uses, and for the same reason.

The fixture is built so that every consequence has a counter-example beside it: the
Profile link that IS repaired by a Task delete next to the Perform Task that is not, the
Task left with nothing running it next to one that keeps a second caller, the Scene left
in no Project next to a Task that is moved into "Base" instead.  Both halves matter --
a check that reported everything would pass a test that only asserted it fires.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src import impact, taskerd
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK, text_report
from maptasker.src.primitem import PrimeItems

# Two Projects, so that a reference reaching across one Project's boundary into another
# can be told from one that stays inside it.
#
#   Project 'Home'    pids 10,11    tids 20,21,22,23,24    scenes 'Menu','Solo'
#   Project 'Away'    pids 12       tids 25
#   Profile 10 'Wake'    entry Task 20 -- its only Task
#   Profile 11 'Idle'    entry Task 21 -- its only Task
#   Profile 12 'Remote'  entry Task 22, and sits in the OTHER Project: deleting 'Home'
#                        with its contents leaves this one holding a Task that is gone,
#                        because that cascade unlinks nothing.
#   Task 20 'Wake Up'    calls 'Helper', shows Scene 'Menu', names 'Widget Task' as a home
#                        screen widget, and is the only thing that sets %Handoff
#   Task 21 'Helper'     run by Profile 'Idle', by Task 20 and by Scene 'Menu' -- three
#                        referrers, so deleting any one of them leaves it alive
#   Task 22 'Shared'     in Project 'Home', run by a Profile in Project 'Away'
#   Task 23 'Widget Task'  reachable only as Task 20's home screen widget
#   Task 24 'Reader'     reads %Handoff, which only Task 20 sets
#   Task 25 'Lonely'     nothing runs it already -- deleting it breaks nothing, and
#                        deleting anything else does not make it newly dead
#   Scene 'Menu'         a Button firing Task 21; shown by Task 20
#   Scene 'Solo'         listed by Project 'Home' and shown by nothing
_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>10,11</pids>
    <tids>20,21,22,23,24</tids>
    <scenes>Menu,Solo</scenes>
  </Project>
  <Project sr="proj1" ve="2">
    <name>Away</name>
    <pids>12</pids>
    <tids>25</tids>
  </Project>
  <Profile sr="prof10" ve="2"><id>10</id><nme>Wake</nme><mid0>20</mid0></Profile>
  <Profile sr="prof11" ve="2"><id>11</id><nme>Idle</nme><mid0>21</mid0></Profile>
  <Profile sr="prof12" ve="2"><id>12</id><nme>Remote</nme><mid0>22</mid0></Profile>
  <Task sr="task20">
    <id>20</id>
    <nme>Wake Up</nme>
    <Action sr="act0" ve="7"><code>130</code><Str sr="arg0" ve="3">Helper</Str></Action>
    <Action sr="act1" ve="7"><code>47</code><Str sr="arg0" ve="3">Menu</Str></Action>
    <Action sr="act2" ve="7"><code>155</code><Str sr="arg0" ve="3">Widget Task</Str></Action>
    <Action sr="act3" ve="7">
      <code>547</code><Str sr="arg0" ve="3">%Handoff</Str><Str sr="arg1" ve="3">ready</Str>
    </Action>
  </Task>
  <Task sr="task21"><id>21</id><nme>Helper</nme></Task>
  <Task sr="task22"><id>22</id><nme>Shared</nme></Task>
  <Task sr="task23"><id>23</id><nme>Widget Task</nme></Task>
  <Task sr="task24">
    <id>24</id>
    <nme>Reader</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">%Handoff</Str></Action>
  </Task>
  <Task sr="task25"><id>25</id><nme>Lonely</nme></Task>
  <Scene sr="scene0">
    <nme>Menu</nme>
    <ButtonElement sr="elements0">
      <geom>0,0,10,10,0,0,10,10</geom>
      <Str sr="arg0" ve="3">Go</Str>
      <clickTask>21</clickTask>
    </ButtonElement>
  </Scene>
  <Scene sr="scene1"><nme>Solo</nme></Scene>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file."""
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100}

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


@pytest.fixture(autouse=True)
def _loaded() -> None:
    """Every test in this file runs against the fixture above."""
    _load(_XML)


def _tagged(analysis: impact.Impact, tag: str) -> list[impact.Consequence]:
    """Every consequence carrying one tag -- what the assertions match against."""
    return [item for item in analysis.consequences if item.tag == tag]


def _tags(analysis: impact.Impact) -> set[str]:
    """Which sorts of consequence this delete has, ignoring how many of each."""
    return {item.tag for item in analysis.consequences}


# ##################################################################################
# References the delete leaves pointing at nothing.
# ##################################################################################
def test_perform_task_call_dangles() -> None:
    """A Perform Task naming the deleted Task is reported, at the action that makes it."""
    found = _tagged(impact.analyze_delete(TASK, "Helper"), "DANGLING-PERFORM-TASK")
    assert len(found) == 1
    assert "Task 'Wake Up' (id 20) action 1" in found[0].where
    assert found[0].severity == impact.BREAKS
    # The jump goes to the ACTION, not merely to the Task holding it -- the location is
    # what the reader recognises, the action is where the fix is made.
    assert found[0].target.action == 1


def test_scene_element_binding_dangles() -> None:
    """A Scene element firing the deleted Task is reported, named as the designer names it."""
    found = _tagged(impact.analyze_delete(TASK, "Helper"), "DANGLING-SCENE-TASK")
    assert len(found) == 1
    assert "Scene 'Menu'" in found[0].where
    assert "Button 'Go'" in found[0].where


def test_widget_reference_dangles() -> None:
    """A Set Widget Label naming the deleted Task means a home screen widget stops working."""
    found = _tagged(impact.analyze_delete(TASK, "Widget Task"), "DANGLING-WIDGET")
    assert len(found) == 1
    assert "action 3" in found[0].where


def test_scene_action_dangles() -> None:
    """Deleting a Scene leaves every action that shows or hides it by name pointing at nothing."""
    found = _tagged(impact.analyze_delete(SCENE, "Menu"), "DANGLING-SCENE-ACTION")
    assert len(found) == 1
    assert "Task 'Wake Up' (id 20) action 2" in found[0].where


def test_profile_link_is_repaired_not_broken() -> None:
    """A Task delete unlinks the Profiles that run it, so those links are not reported broken.

    The counter-example to every test above, and the reason the reference index records
    what SORT each reference is: taskedit.delete_task rewrites this one.
    """
    assert "DANGLING-PROFILE-LINK" not in _tags(impact.analyze_delete(TASK, "Helper"))


def test_project_cascade_leaves_outside_profile_links_dangling() -> None:
    """Deleting a Project's contents does NOT unlink Profiles outside it.

    projedit.delete_profiles_and_tasks_of_project drops the Tasks from the lookup tables
    and stops there, which is exactly the asymmetry with the Task delete above.
    """
    found = _tagged(
        impact.analyze_delete(PROJECT, "Home", keep_contents=False),
        "DANGLING-PROFILE-LINK",
    )
    assert len(found) == 1
    assert "Project 'Away' > Profile 'Remote' (id 12)" in found[0].where


def test_keeping_the_contents_breaks_no_references() -> None:
    """Moving a Project's contents into "Base" leaves every reference to them working."""
    analysis = impact.analyze_delete(PROJECT, "Home", keep_contents=True)
    assert analysis.breaks == 0


def test_references_from_inside_the_delete_are_not_reported() -> None:
    """A reference whose both ends are being deleted is not a consequence of anything.

    Task 20 calls Task 21 and both go in the cascade, so that call is not reported -- while
    the Scene binding to Task 21 is, because the Scene itself survives.
    """
    analysis = impact.analyze_delete(PROJECT, "Home", keep_contents=False)
    assert "DANGLING-PERFORM-TASK" not in _tags(analysis)
    assert _tagged(analysis, "DANGLING-SCENE-TASK")


# ##################################################################################
# Things left working but no longer doing what they did.
# ##################################################################################
def test_profile_left_with_nothing_to_run() -> None:
    """A Profile whose every Task is deleted is kept, and will trigger and do nothing."""
    found = _tagged(impact.analyze_delete(TASK, "Wake Up"), "PROFILE-WITHOUT-TASK")
    assert len(found) == 1
    assert "Profile 'Wake' (id 10)" in found[0].where
    assert found[0].severity == impact.CHANGES


def test_task_left_with_nothing_running_it() -> None:
    """Deleting a Profile leaves the Task it alone ran in the file with nothing running it."""
    found = _tagged(impact.analyze_delete(PROFILE, "Wake"), "TASK-LEFT-DEAD")
    assert len(found) == 1
    assert "Task 'Wake Up' (id 20)" in found[0].where
    # The detail says what is going, so the finding explains itself rather than asserting.
    assert "Profile 'Wake'" in found[0].detail


def test_task_with_another_caller_is_not_left_dead() -> None:
    """A Task keeping a referrer the delete does not reach is not reported.

    Scene 'Menu' fires 'Helper', but a Profile and a Perform Task run it too, so deleting
    the Scene does not strand it.  The counter-example to the test above.
    """
    assert "TASK-LEFT-DEAD" not in _tags(impact.analyze_delete(SCENE, "Menu"))


def test_already_dead_task_is_not_reported() -> None:
    """A Task nothing ran to begin with is not blamed on this delete."""
    analysis = impact.analyze_delete(PROFILE, "Wake")
    assert not [item for item in _tagged(analysis, "TASK-LEFT-DEAD") if "Lonely" in item.where]


def test_project_scenes_are_left_in_no_project() -> None:
    """A Project's Scenes are neither moved nor deleted, under either choice."""
    for keep in (True, False):
        found = _tagged(impact.analyze_delete(PROJECT, "Home", keep_contents=keep), "SCENE-LEFT-ADRIFT")
        assert sorted(item.target.key for item in found) == ["Menu", "Solo"]


# ##################################################################################
# Variables.
# ##################################################################################
def test_global_read_elsewhere_is_left_unset() -> None:
    """A global only the deleted Task sets, read by a Task that stays, is reported."""
    found = _tagged(impact.analyze_delete(TASK, "Wake Up"), "DANGLING-VARIABLE")
    assert len(found) == 1
    assert "%Handoff" in found[0].detail
    assert "Task 'Reader' (id 24)" in found[0].where
    # A read that comes back empty is not an error Tasker reports, which is the whole
    # reason this is worth saying before the delete rather than after.
    assert "empty" in found[0].detail


def test_variable_finding_carries_its_caveat() -> None:
    """A global can be set from outside the backup, and the report says so."""
    analysis = impact.analyze_delete(TASK, "Wake Up")
    assert any("Variables tab" in caveat for caveat in analysis.caveats)


def test_no_variable_finding_when_the_reader_goes_too() -> None:
    """Nothing is stranded when everything that reads the variable is deleted as well."""
    analysis = impact.analyze_delete(PROJECT, "Home", keep_contents=False)
    assert "DANGLING-VARIABLE" not in _tags(analysis)


# ##################################################################################
# What the whole answer looks like.
# ##################################################################################
def test_a_harmless_delete_says_so() -> None:
    """A Task nothing points at produces no consequences and a summary that says as much."""
    analysis = impact.analyze_delete(TASK, "Lonely")
    assert analysis.consequences == []
    assert "Nothing else in this configuration points at it" in analysis.summary()
    assert impact.consequence_rows(analysis) == []


def test_what_goes_is_stated_for_every_kind() -> None:
    """Each kind of delete says what it takes with it and what it leaves behind."""
    assert "unlinked from 1 Profile(s)" in " ".join(impact.analyze_delete(TASK, "Helper").goes)
    assert "linked Task(s) are kept" in " ".join(impact.analyze_delete(PROFILE, "Wake").goes)
    assert "the Tasks they fire are kept" in " ".join(impact.analyze_delete(SCENE, "Menu").goes)
    assert "move into 'Base'" in " ".join(impact.analyze_delete(PROJECT, "Home").goes)
    assert "deleted with it" in " ".join(impact.analyze_delete(PROJECT, "Home", keep_contents=False).goes)


def test_object_that_is_already_gone() -> None:
    """A stale dialog is answered rather than crashed on.

    The delete dialogs are opened from an editor that may have been sitting open while the
    configuration changed underneath it -- the same staleness the analysis is run at
    confirmation time to avoid.
    """
    analysis = impact.analyze_delete(TASK, "No Such Task")
    assert analysis.consequences == []
    assert any("no longer in the loaded configuration" in caveat for caveat in analysis.caveats)


def test_breaks_are_reported_before_changes() -> None:
    """Worst first, then grouped by tag -- what makes a long list skimmable."""
    severities = [item.severity for item in impact.analyze_delete(TASK, "Helper").consequences]
    assert severities == sorted(severities, key=[impact.BREAKS, impact.CHANGES].index)


def test_the_dialog_list_leaves_out_the_report_heading() -> None:
    """consequence_rows is report_rows without the heading the dialog already shows itself."""
    analysis = impact.analyze_delete(TASK, "Helper")
    assert text_report(impact.report_rows(analysis)).startswith("Deleting Project 'Home' > Task 'Helper'")
    assert "Deleting" not in text_report(impact.consequence_rows(analysis))


def test_every_reported_place_is_somewhere_to_go() -> None:
    """Each consequence carries a Map target, which is what makes its line clickable."""
    for kind, name in ((TASK, "Helper"), (TASK, "Wake Up"), (SCENE, "Menu"), (PROFILE, "Wake")):
        for item in impact.analyze_delete(kind, name).consequences:
            assert item.target is not None, f"{kind} {name}: {item.tag}"
