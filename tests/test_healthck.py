"""MapTasker Health Check Unit Tests

Every check in healthck.py is a pure function over the lookup tables
taskerd.get_the_xml_data builds, so these tests build those tables from a small XML
fixture rather than loading a backup or standing up the GUI.

The fixture (_DEFECTIVE_XML) deliberately carries one instance of every defect the
health check reports, plus healthy objects alongside them.  Both halves matter: the
tests assert that each check fires on the broken object AND stays silent on the sound
one, which is what stops a check that simply reports everything from passing.

The real-backup checks that this cannot cover -- how the report behaves at scale -- are
not the point here.  The point is the checks that a well-formed backup never triggers,
which are exactly the ones no amount of running it against a real file will exercise.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import taskerd
from maptasker.src.healthck import (
    ERROR,
    INFO,
    WARNING,
    run_health_check,
    write_health_check_report,
)
from maptasker.src.primitem import PrimeItems

# One Project holding a sound Profile, a sound Task and a Scene, plus one of every
# defect.  Ids are deliberately spread out so a wrong lookup shows up as a miss rather
# than an accidental hit on a neighbouring object.
#
#   Project 'Good'    pids 10,12 (ok), 99 (missing), tids 20,21,26,96 (96 missing),
#                     scenes 'Menu','Backstage','Inline','Curtain' (ok), 'Ghost' (missing)
#   Project 'Hollow'  no Profiles, no Tasks -> EMPTY-PROJECT
#   Profile 10        entry Task 20 (ok), exit Task 98 (missing) -> BROKEN-TASK-REF
#   Profile 11        in no Project's <pids> -> ORPHAN-PROFILE, and disabled.  Runs Task
#                     25 so that the duplicate-name pair below does not also land in the
#                     unreachable count and blur what that test is measuring.
#   Task 20 'Runner'  calls 'Helper' (ok) and 'Nowhere' (missing), shows Scene 'Menu'
#                     (ok) and Scene 'Vanished' (missing), and %Var (unresolvable)
#   Task 21 'Helper'  reached by Task 20
#   Task 22 'Dead'    nothing runs it -> UNREACHABLE-TASK
#   Task 23 'Widget'  named by a Set Widget Label action -> NOT unreachable
#   Task 24 'Dupe'    same name as Task 25 -> DUPLICATE-NAME.  Fired by Scene 'Menu'.
#   Task 25 'Dupe'    run by Profile 11.
#   Task 26 'Owned'   in Project 'Good' <tids> but nothing runs it -> UNREACHABLE-TASK,
#                     which is the ownership-is-not-invocation case.
#   Profile 12        run by Project 'Good'.  Its entry Task 27 has no name at all.
#   Task 27 (unnamed) shows Scene 'Backstage' -- the Profile > anonymous Task > Scene
#                     path, which is why 'Backstage' must not read as unused.
#   Task 28 'Inline'  called ONLY from a Scene's inline anonymous task.
#   Scene 'Menu'      a Button firing Task 21 (ok), Task 24 (ok) and Task 97 (missing)
#   Scene 'Backstage' shown by the unnamed Task 27
#   Scene 'Inline'    holds an anonymous task inline (<Action> children of a
#                     ListElementItem) that calls Task 28 and destroys Scene 'Curtain'.
#                     Nothing shows this Scene itself -> UNUSED-SCENE.
#   Scene 'Curtain'   destroyed by that inline anonymous task -> NOT unused
#   Scene 'Adrift'    in no Project's <scenes> -> ORPHAN-SCENE
_DEFECTIVE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Good</name>
    <pids>10,12,99</pids>
    <tids>20,21,26,96</tids>
    <scenes>Menu,Backstage,Inline,Curtain,Ghost</scenes>
  </Project>
  <Project sr="proj1" ve="2">
    <name>Hollow</name>
  </Project>
  <Profile sr="prof10" ve="2">
    <id>10</id>
    <nme>Sound Profile</nme>
    <mid0>20</mid0>
    <mid1>98</mid1>
  </Profile>
  <Profile sr="prof11" ve="2">
    <id>11</id>
    <nme>Adrift Profile</nme>
    <limit>true</limit>
    <mid0>25</mid0>
  </Profile>
  <Profile sr="prof12" ve="2">
    <id>12</id>
    <nme>Anonymous Entry</nme>
    <limit>true</limit>
    <mid0>27</mid0>
  </Profile>
  <Task sr="task20">
    <id>20</id>
    <nme>Runner</nme>
    <Action sr="act0" ve="7"><code>130</code><Str sr="arg0" ve="3">Helper</Str></Action>
    <Action sr="act1" ve="7"><code>130</code><Str sr="arg0" ve="3">Nowhere</Str></Action>
    <Action sr="act2" ve="7"><code>130</code><Str sr="arg0" ve="3">%Var</Str></Action>
    <Action sr="act3" ve="7"><code>47</code><Str sr="arg0" ve="3">Menu</Str></Action>
    <Action sr="act4" ve="7"><code>47</code><Str sr="arg0" ve="3">Vanished</Str></Action>
    <Action sr="act5" ve="7"><code>155</code><Str sr="arg0" ve="3">Widget</Str></Action>
  </Task>
  <Task sr="task21"><id>21</id><nme>Helper</nme></Task>
  <Task sr="task22"><id>22</id><nme>Dead</nme></Task>
  <Task sr="task23"><id>23</id><nme>Widget</nme></Task>
  <Task sr="task24"><id>24</id><nme>Dupe</nme></Task>
  <Task sr="task25"><id>25</id><nme>Dupe</nme></Task>
  <Task sr="task26"><id>26</id><nme>Owned</nme></Task>
  <Task sr="task27">
    <id>27</id>
    <Action sr="act0" ve="7"><code>47</code><Str sr="arg0" ve="3">Backstage</Str></Action>
  </Task>
  <Task sr="task28"><id>28</id><nme>Inline</nme></Task>
  <Scene sr="scene0">
    <nme>Menu</nme>
    <ButtonElement sr="elements0">
      <geom>0,0,10,10,0,0,10,10</geom>
      <Str sr="arg0" ve="3">Go</Str>
      <clickTask>21</clickTask>
      <itemclickTask>24</itemclickTask>
      <longclickTask>97</longclickTask>
    </ButtonElement>
  </Scene>
  <Scene sr="scene1"><nme>Adrift</nme></Scene>
  <Scene sr="scene2"><nme>Backstage</nme></Scene>
  <Scene sr="scene3"><nme>Curtain</nme></Scene>
  <Scene sr="scene4">
    <nme>Inline</nme>
    <ListElement sr="elements0">
      <geom>0,0,10,10,0,0,10,10</geom>
      <Str sr="arg0" ve="3">Choices</Str>
      <ListElementItem sr="item0">
        <Action sr="action" ve="7"><code>130</code><Str sr="arg0" ve="3">Inline</Str></Action>
        <Action sr="action" ve="7"><code>49</code><Str sr="arg0" ve="3">Curtain</Str></Action>
      </ListElementItem>
    </ListElement>
  </Scene>
</TaskerData>
"""

# A Scene shown only under a name Tasker works out at run time.  Kept apart from the
# fixture above so that one's UNUSED-SCENE finding stays the plain wording: the caveat is
# attached to every such finding once any variable reference exists anywhere in the file.
_VARIABLE_SCENE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Chooser</name><pids>10</pids><tids>20</tids><scenes>Shown,Hidden</scenes>
  </Project>
  <Profile sr="prof10" ve="2"><id>10</id><nme>Pick</nme><mid0>20</mid0></Profile>
  <Task sr="task20">
    <id>20</id><nme>Show Whichever</nme>
    <Action sr="act0" ve="7"><code>47</code><Str sr="arg0" ve="3">%Which_Menu</Str></Action>
  </Task>
  <Scene sr="scene0"><nme>Shown</nme></Scene>
  <Scene sr="scene1"><nme>Hidden</nme></Scene>
</TaskerData>
"""

# A Profile naming a Task counts as a reference even when that Profile is itself an
# orphan (Profile 11 here).  That is deliberate and worth stating: chasing the chain --
# "the Profile is unreachable, so its Tasks are too" -- would report one broken thing as
# several, when the single ORPHAN-PROFILE finding is the root cause and the only one the
# user needs to act on.
_UNREACHABLE_TASK_NAMES = {"Dead", "Owned"}


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


def _findings_for(report: str, tag: str) -> list[str]:
    """The '[TAG]  where' lines of one tag, which is what the assertions match against."""
    return [line for line in report.splitlines() if line.startswith(f"[{tag}]")]


@pytest.fixture
def report() -> str:
    """The health check report for the defective fixture."""
    _load(_DEFECTIVE_XML)
    text, _ = run_health_check()
    return text


@pytest.fixture
def counts() -> dict:
    """The severity counts for the defective fixture."""
    _load(_DEFECTIVE_XML)
    _, totals = run_health_check()
    return totals


# ##################################################################################
# Reference integrity -- every one of these is an ERROR.
# ##################################################################################
def test_broken_profile_reference(report: str) -> None:
    """A Project's <pids> naming a Profile that is not in the file."""
    findings = _findings_for(report, "BROKEN-PROFILE-REF")
    assert len(findings) == 1
    assert "Project 'Good'" in findings[0]
    assert "99" in report


def test_broken_task_id_reference(report: str) -> None:
    """A Project's <tids> naming a Task that is not in the file."""
    findings = _findings_for(report, "BROKEN-TID-REF")
    assert len(findings) == 1
    assert "Project 'Good'" in findings[0]


def test_broken_scene_reference(report: str) -> None:
    """A Project's <scenes> naming a Scene that is not in the file."""
    findings = _findings_for(report, "BROKEN-SCENE-REF")
    assert len(findings) == 1
    assert "Ghost" in report


def test_broken_profile_task_reference(report: str) -> None:
    """A Profile's exit Task id that resolves to nothing.

    The entry Task on the same Profile is sound, so this also proves the check reads
    <mid0> and <mid1> separately rather than reporting the pair.
    """
    findings = _findings_for(report, "BROKEN-TASK-REF")
    assert len(findings) == 1
    assert "Sound Profile" in findings[0]
    assert "Exit Task" in report


def test_broken_scene_task_binding(report: str) -> None:
    """A Scene element firing a Task id that is not in the file."""
    findings = _findings_for(report, "BROKEN-SCENE-TASK")
    assert len(findings) == 1
    assert "Scene 'Menu'" in findings[0]
    # Named by the label the Scene designer shows, not by the raw tag.
    assert "Button 'Go'" in report


def test_broken_perform_task(report: str) -> None:
    """A Perform Task action calling a Task name that is not in the file."""
    findings = _findings_for(report, "BROKEN-PERFORM-TASK")
    assert len(findings) == 1
    assert "Nowhere" in report
    # The sound call on the same Task is not reported.
    assert "'Helper'" not in "\n".join(findings)


def test_broken_scene_action(report: str) -> None:
    """A Show Scene action naming a Scene that is not in the file."""
    findings = _findings_for(report, "BROKEN-SCENE-ACTION")
    assert len(findings) == 1
    assert "Vanished" in report


def test_variable_reference_is_not_reported(report: str) -> None:
    """A reference holding a variable is skipped rather than called broken.

    '%Var' is decided on the device at run time.  Reporting it would be a false alarm on
    a configuration that works, which is the one failure mode that would make the whole
    report untrustworthy.
    """
    assert "%Var" not in report


# ##################################################################################
# Reachability.
# ##################################################################################
def test_unreachable_task(report: str) -> None:
    """Exactly the Tasks nothing runs are reported, and no others.

    The 'and no others' half is the point: every Task in the fixture that IS run -- by a
    Profile, by a Scene element, by a Perform Task, by a widget -- has to stay out of
    this list, or the check is just reporting everything.
    """
    findings = _findings_for(report, "UNREACHABLE-TASK")
    # Task 26 is in Project 'Good' <tids> and so is named with it; Task 22 is in no
    # Project's, and a location says nothing at all rather than inventing a placeholder.
    assert sorted(findings) == [
        "[UNREACHABLE-TASK]  Project 'Good' > Task 'Owned' (id 26)",
        "[UNREACHABLE-TASK]  Task 'Dead' (id 22)",
    ]
    for reachable in ("Runner", "Helper", "Widget", "Dupe"):
        assert not any(f"'{reachable}'" in finding for finding in findings), f"{reachable} is run by something"


def test_unreachable_task_without_a_project_says_so(report: str) -> None:
    """Belonging to no Project is part of the case for a Task nobody runs.

    It goes in the detail rather than the location: the location stays uniform across
    every finding so the report sorts into Project order, and 'no Project' is a fact
    about the Task, not a place to look for it.
    """
    detail = report[report.index("Task 'Dead' (id 22)") :]
    assert "no Project lists it" in detail.split("\n\n")[0]
    # The Task that does have one does not carry the phrase.
    owned = report[report.index("Task 'Owned' (id 26)") :]
    assert "no Project lists it" not in owned.split("\n\n")[0]


def test_task_owned_by_project_is_still_unreachable(report: str) -> None:
    """Being listed in a Project's <tids> does not make a Task reachable.

    <tids> records which Project a Task is filed under, not that anything runs it.
    Counting it as a reference made this check unable to fire at all against a real
    backup, where every Task a Project owns appears there -- 0 findings out of 840 Tasks.
    """
    findings = _findings_for(report, "UNREACHABLE-TASK")
    # Task 26 'Owned' is in Project 'Good' <tids> and nothing runs it.
    assert any("'Owned'" in finding for finding in findings)


def test_widget_task_is_not_unreachable(report: str) -> None:
    """A Task named by a Set Widget Label action is treated as launched by its widget."""
    assert "Widget" not in "".join(_findings_for(report, "UNREACHABLE-TASK"))


def test_orphan_profile(report: str) -> None:
    """A Profile no Project lists in <pids>."""
    findings = _findings_for(report, "ORPHAN-PROFILE")
    assert len(findings) == 1
    assert "Adrift Profile" in findings[0]


def test_orphan_scene(report: str) -> None:
    """A Scene no Project lists in <scenes>."""
    findings = _findings_for(report, "ORPHAN-SCENE")
    assert len(findings) == 1
    assert "Adrift" in findings[0]


def test_unused_scene_is_separate_from_orphan(report: str) -> None:
    """An owned Scene that no action shows is INFO, not the ORPHAN-SCENE warning.

    'Menu' is owned by Project 'Good' AND shown by an action, so it is neither.
    """
    assert "Menu" not in "".join(_findings_for(report, "ORPHAN-SCENE"))
    assert "Menu" not in "".join(_findings_for(report, "UNUSED-SCENE"))


def test_scene_shown_by_a_profiles_anonymous_task_is_not_unused(report: str) -> None:
    """Profile > unnamed Task > Show Scene keeps that Scene off the unused list.

    Profile 12's entry Task has no <nme> at all.  An unnamed Task is still a Task -- it
    has an id, it holds actions, a Profile runs it -- so the Scenes it shows count.
    Skipping unnamed Tasks would report 'Backstage' as a Scene nothing ever displays.
    """
    unused = "".join(_findings_for(report, "UNUSED-SCENE"))
    assert "Backstage" not in unused
    assert "Backstage" not in "".join(_findings_for(report, "ORPHAN-SCENE"))


def test_scene_acted_on_by_an_inline_anonymous_task_is_not_unused(report: str) -> None:
    """A Scene destroyed by another Scene's inline anonymous task is not unused.

    Tasker stores a task created inline on a Scene element inside the Scene rather than
    as a top-level <Task>, so it is in no lookup table and the walk over all Tasks never
    reaches it.  'Curtain' is destroyed only from there.
    """
    assert "Curtain" not in "".join(_findings_for(report, "UNUSED-SCENE"))


def test_task_called_by_an_inline_anonymous_task_is_not_unreachable(report: str) -> None:
    """The same inline actions count as Task references too.

    Task 'Inline' is called only by the anonymous task inside Scene 'Inline'.  Before
    those actions were walked it read as a Task nothing runs.
    """
    assert "'Inline'" not in "".join(_findings_for(report, "UNREACHABLE-TASK"))


def test_unused_scene_still_fires_when_nothing_shows_it(report: str) -> None:
    """The check has not been widened into uselessness: a genuinely unused Scene reports.

    Scene 'Inline' holds an anonymous task that acts on other things, but nothing anywhere
    shows 'Inline' itself.
    """
    findings = _findings_for(report, "UNUSED-SCENE")
    assert len(findings) == 1
    # Named with the Project that owns it, the way a Task or Profile finding is: knowing a
    # Scene is unused is only half of what you need to go and do something about it.
    assert findings[0] == "[UNUSED-SCENE]  Project 'Good' > Scene 'Inline'"
    # No variable-named Scene action in this fixture, so the plain wording is used.
    assert "NOTE ON UNUSED SCENES" not in report


def test_scene_named_by_a_variable_makes_unused_scene_say_so() -> None:
    """A Show Scene naming its Scene with a variable is reported as a caveat, not silently.

    The action could be showing any Scene in the file, so neither 'Shown' nor 'Hidden' can
    be ruled out.  They are still listed -- the list is a place to start looking -- but the
    report has to say why it cannot be trusted as a delete list.
    """
    _load(_VARIABLE_SCENE_XML)
    text, _ = run_health_check()

    findings = _findings_for(text, "UNUSED-SCENE")
    assert len(findings) == 2
    assert "NOTE ON UNUSED SCENES" in text
    assert "1 action(s)" in text
    # And the variable itself is still never reported as a broken reference.
    assert not _findings_for(text, "BROKEN-SCENE-ACTION")


def test_empty_project(report: str) -> None:
    """A Project with no Profiles and no Tasks."""
    findings = _findings_for(report, "EMPTY-PROJECT")
    assert len(findings) == 1
    assert "Hollow" in findings[0]


# ##################################################################################
# Hygiene.
# ##################################################################################
def test_duplicate_task_name(report: str) -> None:
    """Two Tasks sharing a name.

    Built from all_tasks rather than all_tasks_by_name, which silently overwrites a
    collision and so could never report one.
    """
    findings = _findings_for(report, "DUPLICATE-NAME")
    assert len(findings) == 1
    assert "Dupe" in findings[0]
    assert "24" in report
    assert "25" in report


def test_disabled_profile(report: str) -> None:
    """A Profile carrying <limit>true</limit>, named with the Project that owns it.

    Both renderings are pinned here: Profile 12 is owned by a Project and Profile 11 is
    not, and a location is only prefixed when something owns the object.
    """
    findings = _findings_for(report, "DISABLED-PROFILE")
    assert sorted(findings) == [
        "[DISABLED-PROFILE]  Profile 'Adrift Profile' (id 11)",
        "[DISABLED-PROFILE]  Project 'Good' > Profile 'Anonymous Entry' (id 12)",
    ]


def test_large_task_respects_the_warning_limit() -> None:
    """LARGE-TASK fires off the user's own action-count limit, and is off at the default.

    Counted here rather than read from PrimeItems.task_action_warnings, which is only
    filled while the Map output is built -- a health check run straight after loading a
    file would otherwise never report one.
    """
    _load(_DEFECTIVE_XML)
    # Task 'Runner' has 6 actions.  The default limit of 100 disables the check entirely.
    report_at_default, _ = run_health_check()
    assert not _findings_for(report_at_default, "LARGE-TASK")

    PrimeItems.program_arguments["task_action_warning_limit"] = 5
    report_at_five, _ = run_health_check()
    findings = _findings_for(report_at_five, "LARGE-TASK")
    assert findings == ["[LARGE-TASK]  Project 'Good' > Task 'Runner' (id 20)"]


# ##################################################################################
# The report itself.
# ##################################################################################
def test_report_names_the_xml_file(report: str) -> None:
    """The file being checked is named in the report, as asked for."""
    assert "fixture.xml" in report


def test_report_counts_match_the_findings(report: str, counts: dict) -> None:
    """The Findings line agrees with what is actually listed below it."""
    assert counts[ERROR] == len([line for line in report.splitlines() if line.startswith("[BROKEN-")])
    assert f"{counts[ERROR]} Errors" in report
    assert f"{counts[WARNING]} Warnings" in report
    assert f"{counts[INFO]} Info" in report


def test_report_carries_the_unreachable_caveat(report: str) -> None:
    """The limits of UNREACHABLE-TASK are stated in the report, not just in the code.

    A report inviting someone to delete a Task their home screen widget launches, without
    saying it cannot see widgets, would be worse than no report.
    """
    assert "NOTE ON UNREACHABLE TASKS" in report
    assert "widget" in report


def test_clean_configuration_reports_nothing() -> None:
    """A sound configuration produces a report that says so, and no findings."""
    _load(
        """<TaskerData sr="" dvi="1" tv="6.3.13">
          <Project sr="proj0" ve="2"><name>Solid</name><pids>10</pids><tids>20</tids></Project>
          <Profile sr="prof10" ve="2"><id>10</id><nme>Fine</nme><mid0>20</mid0></Profile>
          <Task sr="task20"><id>20</id><nme>Works</nme></Task>
        </TaskerData>""",
    )
    text, totals = run_health_check()
    assert totals == {ERROR: 0, WARNING: 0, INFO: 0}
    assert "Nothing to report" in text


def test_report_is_written_to_the_runtime_directory(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """The file lands in the current directory, named date-then-time.

    The order is asserted rather than just the prefix: it is a stated requirement, and
    date-first is what makes successive reports from one day sort into the order they
    were run.  Both halves are zero padded, so the name is always the same width.
    """
    monkeypatch.chdir(tmp_path)
    _load(_DEFECTIVE_XML)
    text, _ = run_health_check()

    file_name = write_health_check_report(text)

    # MapTasker_HealthCheck_MM-DD-YYYY_HH-MM-SS.txt
    assert re.fullmatch(
        r"MapTasker_HealthCheck_\d{2}-\d{2}-\d{4}_\d{2}-\d{2}-\d{2}\.txt",
        file_name,
    ), file_name
    written = os.path.join(tmp_path, file_name)
    assert os.path.isfile(written)
    # Saved as the plain text it was built as -- the HTML escaping for display happens in
    # the GUI handler, on a copy, and must not reach the file.
    with open(written, encoding="utf-8") as saved:
        assert saved.read() == text
