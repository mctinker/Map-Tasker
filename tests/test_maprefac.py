"""MapTasker refactoring (maprefac) Unit Tests

What these assert is mostly about what SURVIVES, and about what is REFUSED.

Every operation in maprefac is easy to get visibly right and hard to get invisibly right.
A test that only checks the happy path -- six actions moved, a Perform Task written -- would
pass on an implementation that silently reorders the actions left behind, drops an action's
label, or hands two Tasks the same id.  So the happy-path tests here check the surroundings
as much as the result: the numbering of what stayed, the Project membership of what was
made, the label and condition on a copy.

The other half is the refusals, and they carry as many tests as the successes.  A refactor
that runs when it should not is the failure this whole module exists to prevent, because
nothing about the result looks wrong -- the configuration parses, loads and runs, doing
something other than it did.  Each block therefore has a test that provokes it, and asserts
that NOTHING was changed.

Fixture-driven, the same arrangement test_mapswap.py, test_mapfind.py and test_healthck.py
use.  The fixture is small and every part of it is load-bearing; see its own comments.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import maprefac, sessundo, taskedit, taskerd
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.primitem import PrimeItems

# Codes used below, named so the tests read as prose.
VARIABLE_SET = "547"
FLASH = "548"
IF = "37"
END_IF = "38"
PERFORM_TASK = "130"
GOTO = "135"
SHOW_SCENE = "47"

# Two Projects, so that "move to another Project" has somewhere to move to and a Project
# duplication has a boundary to respect.
#
#   Home  Profiles Dawn + Dusk, Tasks Morning/Wake Steps/Quiet/Looper, Scene Panel.
#   Away  Profile Roaming, Task Trip.
#
# Task 20 'Morning' is the extract subject and carries every shape the checks care about:
#   run order 0  Variable Set %count      -- a local also used inside the If block
#             1  Flash, with a <label>    -- proves a label travels with its action
#             2  If %count > 0            -- opens a block ...
#             3  Flash 'many'
#             4  End If                   -- ... that closes at 4
#             5  Perform Task 'Wake Steps', passing 7 as Parameter 1
# and its <Action> children are written to the fixture OUT of run order (act3 before act2),
# because Tasker orders actions by the numeric suffix of sr= and writes them sorted as text.
# A test suite that fed them in document order would pass on an implementation that used
# findall("Action") and be wrong on every real backup.
#
# Task 21 'Wake Steps' is the inline subject: it reads %par1 (its caller's parameter) and
# %total (a local it shares by name with nothing, until it is inlined somewhere that has one).
#
# Task 23 'Looper' holds a Goto, which every rearrangement of a Task must refuse.
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>100,101</pids>
    <tids>20,21,22,23</tids>
    <scenes>Panel</scenes>
  </Project>
  <Project sr="proj1" ve="2">
    <name>Away</name>
    <pids>102</pids>
    <tids>24</tids>
  </Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <nme>Dawn</nme>
    <mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time>
  </Profile>
  <Profile sr="prof101" ve="2">
    <id>101</id>
    <nme>Dusk</nme>
    <mid0>22</mid0>
    <mid1>21</mid1>
    <Time sr="con0"><fh>18</fh><fm>0</fm><th>19</th><tm>0</tm></Time>
  </Profile>
  <Profile sr="prof102" ve="2">
    <id>102</id>
    <nme>Roaming</nme>
    <mid0>24</mid0>
    <State sr="con0" ve="2"><code>100</code></State>
  </Profile>
  <Task sr="task20" ve="2">
    <id>20</id>
    <nme>Morning</nme>
    <pri>50</pri>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%count</Str>
      <Str sr="arg1" ve="3">0</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <label>say hello</label>
      <Str sr="arg0" ve="3">hello %count</Str>
    </Action>
    <Action sr="act3" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">many</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>37</code>
      <ConditionList sr="if"><Condition sr="c0" ve="3"><lhs>%count</lhs><op>7</op><rhs>0</rhs></Condition></ConditionList>
    </Action>
    <Action sr="act4" ve="7">
      <code>38</code>
    </Action>
    <Action sr="act5" ve="7">
      <code>130</code>
      <Str sr="arg0" ve="3">Wake Steps</Str>
      <Int sr="arg1"><var>%priority</var></Int>
      <Str sr="arg2" ve="3">7</Str>
    </Action>
  </Task>
  <Task sr="task21" ve="2">
    <id>21</id>
    <nme>Wake Steps</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%total</Str>
      <Str sr="arg1" ve="3">%par1</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">woke %total</Str>
    </Action>
  </Task>
  <Task sr="task22" ve="2">
    <id>22</id>
    <nme>Quiet</nme>
    <Action sr="act0" ve="7">
      <code>47</code>
      <Str sr="arg0" ve="3">Panel</Str>
    </Action>
  </Task>
  <Task sr="task23" ve="2">
    <id>23</id>
    <nme>Looper</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">round</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>135</code>
      <Int sr="arg0" val="0"/>
      <Int sr="arg1" val="0"/>
    </Action>
  </Task>
  <Task sr="task24" ve="2">
    <id>24</id>
    <nme>Trip</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">away</Str>
    </Action>
  </Task>
  <Scene sr="scenePanel">
    <nme>Panel</nme>
    <cdate>1600000000000</cdate>
  </Scene>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file.

    The same loader test_mapswap.py uses, including tasker_arg_specs -- taskedit reads it
    to decide what an argument is, and a Task created without it comes out wrong rather
    than failing.
    """
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.xml_tree = ET.ElementTree(root)
    PrimeItems.program_arguments = {"task_action_warning_limit": 100, "language": "English"}

    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file) as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"  # proginit appends this one; see its own note.
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
    """The fixture configuration, in the tables maprefac reads, with an empty undo history."""
    sessundo.clear()
    _load(_FIXTURE_XML)
    yield
    sessundo.clear()


# ##################################################################################
# Reading the fixture, the way the tests want to talk about it.
# ##################################################################################


def _task(task_id: str) -> ET.Element:
    """One Task element of the loaded configuration."""
    return PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]


def _codes(task_id: str) -> list[str]:
    """A Task's action codes IN RUN ORDER -- what the Task actually does, as a list."""
    return [(action.findtext("code") or "") for action in maprefac._actions(_task(task_id))]


def _srs(task_id: str) -> list[str]:
    """A Task's sr= attributes in run order.  Should always be act0, act1, ... with no gaps."""
    return [action.attrib.get("sr", "") for action in maprefac._actions(_task(task_id))]


def _members(project_name: str, tag: str) -> list[str]:
    """A Project's <pids>/<tids>/<scenes> as a list."""
    return maprefac._members(PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"], tag)


def _task_id(name: str) -> str:
    """A Task's id, by name."""
    return PrimeItems.tasker_root_elements["all_tasks_by_name"][name]["id"]


def _string_arg(action: ET.Element, arg_id: str) -> str:
    """One <Str sr="argN"> of an action."""
    return maprefac._string_argument(action, arg_id)


# ##################################################################################
# Run order, which everything below depends on being right.
# ##################################################################################


def test_actions_are_read_in_run_order_not_document_order(loaded: None) -> None:
    """The fixture writes Morning's act3 before its act2; the module must not care."""
    assert [child.attrib["sr"] for child in _task("20").findall("Action")] == [
        "act0",
        "act1",
        "act3",
        "act2",
        "act4",
        "act5",
    ]
    assert _srs("20") == ["act0", "act1", "act2", "act3", "act4", "act5"]
    assert _codes("20") == [VARIABLE_SET, FLASH, IF, FLASH, END_IF, PERFORM_TASK]


# ##################################################################################
# Extract.
# ##################################################################################


def test_extract_moves_the_actions_and_leaves_a_call(loaded: None) -> None:
    """The whole operation, checked from both ends and from the Project."""
    plan = maprefac.plan_extract("20", [2, 3, 4], "Loud Part")
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])

    # What is left runs in the same order, with the call standing where the block did.
    assert _codes("20") == [VARIABLE_SET, FLASH, PERFORM_TASK, PERFORM_TASK]
    assert _srs("20") == ["act0", "act1", "act2", "act3"]
    call = maprefac._actions(_task("20"))[2]
    assert _string_arg(call, "0") == "Loud Part"

    # ...and the block itself is now a Task, renumbered from zero, in the same Project.
    new_id = _task_id("Loud Part")
    assert _codes(new_id) == [IF, FLASH, END_IF]
    assert _srs(new_id) == ["act0", "act1", "act2"]
    assert new_id in _members("Home", "tids")
    assert PrimeItems.tasker_root_elements["all_tasks_by_name"]["Loud Part"]["id"] == new_id


def test_extract_carries_the_label_with_its_action(loaded: None) -> None:
    """A label belongs to the action, not to the Task, and must not be left behind."""
    plan = maprefac.plan_extract("20", [1], "Greeting")
    assert maprefac.apply(plan) == (True, [])
    moved = maprefac._actions(_task(_task_id("Greeting")))[0]
    assert moved.findtext("label") == "say hello"


def test_extract_takes_the_source_tasks_priority(loaded: None) -> None:
    """A new Task's priority is a property of the actions moved, not a default of 100."""
    plan = maprefac.plan_extract("20", [0], "Counter")
    assert maprefac.apply(plan) == (True, [])
    assert _task(_task_id("Counter")).findtext("pri") == "50"


def test_extract_writes_a_perform_task_tasker_would_recognise(loaded: None) -> None:
    """The call has to be the shape Tasker writes, not merely one this program can read."""
    plan = maprefac.plan_extract("20", [0], "Counter")
    assert maprefac.apply(plan) == (True, [])
    call = maprefac._actions(_task("20"))[0]

    assert call.findtext("code") == PERFORM_TASK
    assert call.attrib["ve"] == "7"
    # Priority is inherited from the calling Task, which is what these actions were doing
    # a moment ago as part of it.
    assert call.find("Int[@sr='arg1']/var").text == "%priority"
    # Every argument present, in the order Tasker writes them (sorted as text, so arg10
    # sits between arg1 and arg2) -- see maprefac's own note on why that matters.
    assert [child.attrib["sr"] for child in call if child.tag != "code"] == [
        "arg0",
        "arg1",
        "arg10",
        "arg2",
        "arg3",
        "arg4",
        "arg5",
        "arg6",
        "arg7",
        "arg8",
        "arg9",
    ]


def test_extract_refuses_a_selection_with_gaps(loaded: None) -> None:
    """One Perform Task cannot stand in two places, and choosing one would reorder the rest."""
    plan = maprefac.plan_extract("20", [1, 3], "Bits")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "NOT-CONTIGUOUS"
    assert maprefac.apply(plan)[0] is False
    assert _codes("20") == [VARIABLE_SET, FLASH, IF, FLASH, END_IF, PERFORM_TASK]


def test_extract_refuses_half_an_if_block(loaded: None) -> None:
    """Taking the If and not the End If leaves the rest of the Task inside a block."""
    plan = maprefac.plan_extract("20", [2, 3], "Half")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "UNBALANCED-BLOCK"
    assert "End If" in plan.blocks[0].explanation


def test_extract_refuses_an_end_if_it_did_not_open(loaded: None) -> None:
    """The mirror failure: the actions BEFORE the selection lose their End If."""
    plan = maprefac.plan_extract("20", [3, 4], "Tail")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "UNBALANCED-BLOCK"


def test_extract_refuses_a_task_holding_a_goto(loaded: None) -> None:
    """A Goto addresses an action by number, and extracting renumbers them."""
    plan = maprefac.plan_extract("23", [0], "Round")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "GOTO-PRESENT"


def test_extract_refuses_a_name_another_task_has(loaded: None) -> None:
    """Perform Task calls by name, so two Tasks sharing one makes every call ambiguous."""
    plan = maprefac.plan_extract("20", [0], "Quiet")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "NAME-TAKEN"


def test_extract_refuses_an_empty_selection(loaded: None) -> None:
    plan = maprefac.plan_extract("20", [], "Nothing")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "NO-ACTIONS"


def test_extract_warns_about_locals_that_stop_being_shared(loaded: None) -> None:
    """The check the module exists for: %count is set at action 0 and read inside the block."""
    plan = maprefac.plan_extract("20", [2, 3, 4], "Loud Part")
    assert not plan.is_blocked
    assert any("%count" in warning for warning in plan.warnings)
    assert any("Perform Task's Parameter" in warning for warning in plan.warnings)


def test_extract_does_not_warn_when_no_local_is_shared(loaded: None) -> None:
    """A warning on every extract would be a warning nobody reads.

    Morning's last action is the Perform Task, which mentions %priority and a Task name and
    no local of its own -- so pulling it out shares nothing with the five left behind.
    """
    plan = maprefac.plan_extract("20", [5], "Tail Call")
    assert not any("%" in warning and "used both inside and outside" in warning for warning in plan.warnings)


# ##################################################################################
# Inline.
# ##################################################################################


def test_inline_replaces_the_call_with_the_called_tasks_actions(loaded: None) -> None:
    """Morning's action 5 calls Wake Steps; afterwards it holds Wake Steps' two actions."""
    plan = maprefac.plan_inline("20", 5)
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])

    assert _codes("20") == [VARIABLE_SET, FLASH, IF, FLASH, END_IF, VARIABLE_SET, FLASH]
    assert _srs("20") == [f"act{number}" for number in range(7)]
    assert _string_arg(maprefac._actions(_task("20"))[6], "0") == "woke %total"

    # A copy: the called Task is untouched and still callable from anywhere else.
    assert _codes("21") == [VARIABLE_SET, FLASH]
    assert "Wake Steps" in PrimeItems.tasker_root_elements["all_tasks_by_name"]


def test_inline_in_the_middle_keeps_what_follows_in_order(loaded: None) -> None:
    """Inlining is an insertion, and everything after it has to shift rather than move."""
    call = maprefac._actions(_task("20"))[5]
    # Put the call in the middle by moving it to position 1 first.
    actions = maprefac._actions(_task("20"))
    maprefac._renumber([actions[0], call, *actions[1:5]])

    plan = maprefac.plan_inline("20", 1)
    assert maprefac.apply(plan) == (True, [])
    assert _codes("20") == [VARIABLE_SET, VARIABLE_SET, FLASH, FLASH, IF, FLASH, END_IF]
    assert _srs("20") == [f"act{number}" for number in range(7)]


def test_inline_carries_the_calls_condition_onto_every_copy(loaded: None) -> None:
    """The call ran only sometimes; the actions replacing it must too."""
    call = maprefac._actions(_task("20"))[5]
    condition = ET.SubElement(call, "ConditionList", {"sr": "if"})
    inner = ET.SubElement(condition, "Condition", {"sr": "c0", "ve": "3"})
    ET.SubElement(inner, "lhs").text = "%count"

    plan = maprefac.plan_inline("20", 5)
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])

    copied = maprefac._actions(_task("20"))[5:]
    assert len(copied) == 2
    assert all(action.find("ConditionList/Condition/lhs").text == "%count" for action in copied)


def test_inline_carries_the_calls_disabled_state_onto_every_copy(loaded: None) -> None:
    """A disabled call that inlined into enabled actions would start doing something."""
    call = maprefac._actions(_task("20"))[5]
    ET.SubElement(call, "on").text = "false"

    plan = maprefac.plan_inline("20", 5)
    assert maprefac.apply(plan) == (True, [])
    assert all(action.findtext("on") == "false" for action in maprefac._actions(_task("20"))[5:])


def test_inline_moves_the_calls_label_onto_the_first_copy(loaded: None) -> None:
    """The label described the call, so it belongs where the call stood."""
    call = maprefac._actions(_task("20"))[5]
    ET.SubElement(call, "label").text = "wake up"

    plan = maprefac.plan_inline("20", 5)
    assert maprefac.apply(plan) == (True, [])
    copied = maprefac._actions(_task("20"))[5:]
    assert copied[0].findtext("label") == "wake up"
    assert copied[1].find("label") is None


def test_inline_refuses_an_action_that_is_not_a_call(loaded: None) -> None:
    plan = maprefac.plan_inline("20", 1)
    assert plan.is_blocked
    assert plan.blocks[0].reason == "NOT-A-CALL"


def test_inline_refuses_a_call_to_a_task_that_is_not_here(loaded: None) -> None:
    """Already broken before the refactor -- and saying so is more use than a generic refusal."""
    call = maprefac._actions(_task("20"))[5]
    call.find("Str[@sr='arg0']").text = "Nowhere"
    plan = maprefac.plan_inline("20", 5)
    assert plan.is_blocked
    assert plan.blocks[0].reason == "NO-SUCH-TASK"


def test_inline_refuses_a_call_built_from_a_variable(loaded: None) -> None:
    """Which Task's actions to copy is decided on the device, not in the file."""
    call = maprefac._actions(_task("20"))[5]
    call.find("Str[@sr='arg0']").text = "%which"
    plan = maprefac.plan_inline("20", 5)
    assert plan.is_blocked
    assert plan.blocks[0].reason == "INDIRECT-NAME"


def test_inline_refuses_a_task_calling_itself(loaded: None) -> None:
    call = maprefac._actions(_task("20"))[5]
    call.find("Str[@sr='arg0']").text = "Morning"
    plan = maprefac.plan_inline("20", 5)
    assert plan.is_blocked
    assert plan.blocks[0].reason == "SELF-CALL"


def test_inline_refuses_a_called_task_holding_a_goto(loaded: None) -> None:
    """Its Goto would still be valid after the shift and would land somewhere else."""
    call = maprefac._actions(_task("20"))[5]
    call.find("Str[@sr='arg0']").text = "Looper"
    plan = maprefac.plan_inline("20", 5)
    assert plan.is_blocked
    assert plan.blocks[0].reason == "GOTO-IN-CALLED-TASK"


def test_inline_refuses_a_conditional_call_to_a_task_with_a_block(loaded: None) -> None:
    """A condition can be put on each action; it cannot be put on an If block."""
    call = maprefac._actions(_task("20"))[5]
    call.find("Str[@sr='arg0']").text = "Morning Copy"
    # A called Task that holds an If, plus a condition on the call itself.
    branching = maprefac.plan_duplicate(TASK, "20", "Morning Copy")
    assert maprefac.apply(branching) == (True, [])
    ET.SubElement(call, "ConditionList", {"sr": "if"})

    plan = maprefac.plan_inline("20", 5)
    assert plan.is_blocked
    assert plan.blocks[0].reason == "CONDITIONAL-BLOCK"


def test_inline_warns_that_parameters_stop_meaning_what_they_did(loaded: None) -> None:
    """Wake Steps reads %par1; inlined, that is the calling Task's %par1 instead."""
    plan = maprefac.plan_inline("20", 5)
    assert any("%par1" in warning for warning in plan.warnings)
    # ...and it says what this call was actually passing, which is what makes it actionable.
    assert any("passes 7" in warning for warning in plan.warnings)


def test_inline_warns_when_two_tasks_locals_become_one(loaded: None) -> None:
    """%total is Wake Steps'; give Morning one too and the two merge silently."""
    maprefac._actions(_task("20"))[1].find("Str[@sr='arg0']").text = "hello %total"
    plan = maprefac.plan_inline("20", 5)
    assert any("%total" in warning and "separate variables today" in warning for warning in plan.warnings)


def test_inline_says_when_nothing_else_calls_the_task(loaded: None) -> None:
    """Whether the Task is now dead is the question the user asks next."""
    plan = maprefac.plan_inline("20", 5)
    assert any("Nothing else calls 'Wake Steps'" in warning for warning in plan.warnings)


# ##################################################################################
# Move.
# ##################################################################################


def test_move_task_changes_which_project_lists_it(loaded: None) -> None:
    plan = maprefac.plan_move(TASK, "22", "Away")
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])
    assert "22" not in _members("Home", "tids")
    assert "22" in _members("Away", "tids")


def test_move_task_stamps_both_projects_as_modified(loaded: None) -> None:
    """A Project whose membership changed has been modified, and Tasker records that."""
    projects = PrimeItems.tasker_root_elements["all_projects"]
    for entry in projects.values():
        entry["xml"].find("mdate").text if entry["xml"].find("mdate") is not None else None
    plan = maprefac.plan_move(TASK, "22", "Away")
    assert maprefac.apply(plan) == (True, [])
    assert projects["Home"]["xml"].findtext("mdate")
    assert projects["Away"]["xml"].findtext("mdate")


def test_move_refuses_a_task_already_only_there(loaded: None) -> None:
    plan = maprefac.plan_move(TASK, "22", "Home")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "ALREADY-THERE"


def test_move_refuses_an_unknown_project(loaded: None) -> None:
    plan = maprefac.plan_move(TASK, "22", "Nowhere")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "NO-PROJECT"


def test_move_task_warns_when_a_profile_is_left_behind(loaded: None) -> None:
    """Task 22 is Dusk's Entry Task, and Dusk is staying in Home."""
    plan = maprefac.plan_move(TASK, "22", "Away")
    assert any("'Dusk'" in warning for warning in plan.warnings)


def test_move_profile_takes_its_own_tasks_with_it(loaded: None) -> None:
    """Dawn runs Task 20 and nothing else does, so Task 20 travels."""
    plan = maprefac.plan_move(PROFILE, "100", "Away")
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])
    assert "100" in _members("Away", "pids")
    assert "100" not in _members("Home", "pids")
    assert "20" in _members("Away", "tids")
    assert "20" not in _members("Home", "tids")


def test_move_profile_leaves_a_task_another_profile_still_runs(loaded: None) -> None:
    """Dusk's Exit Task is 21; nothing else uses 22 -- so 22 travels and 21 does not."""
    # Make Task 21 shared: Dawn gets it as an Exit Task too.
    ET.SubElement(_task_element_of_profile("100"), "mid1").text = "21"

    plan = maprefac.plan_move(PROFILE, "101", "Away")
    assert maprefac.apply(plan) == (True, [])
    assert "22" in _members("Away", "tids")
    assert "21" in _members("Home", "tids")
    assert "21" not in _members("Away", "tids")


def test_move_profile_says_which_task_stayed_and_why(loaded: None) -> None:
    ET.SubElement(_task_element_of_profile("100"), "mid1").text = "21"
    plan = maprefac.plan_move(PROFILE, "101", "Away")
    assert any("Wake Steps" in warning and "Dawn" in warning for warning in plan.warnings)


def _task_element_of_profile(profile_id: str) -> ET.Element:
    """A Profile element, for tests that need to add a Task link to it."""
    return PrimeItems.tasker_root_elements["all_profiles"][profile_id]["xml"]


# ##################################################################################
# Duplicate.
# ##################################################################################


def test_duplicate_task_makes_a_second_independent_task(loaded: None) -> None:
    plan = maprefac.plan_duplicate(TASK, "22")
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])

    new_id = _task_id("Quiet (copy)")
    assert new_id != "22"
    assert _codes(new_id) == _codes("22")
    assert new_id in _members("Home", "tids")
    # Independent: editing the copy must not reach the original.
    maprefac._actions(_task(new_id))[0].find("Str[@sr='arg0']").text = "Changed"
    assert _string_arg(maprefac._actions(_task("22"))[0], "0") == "Panel"


def test_duplicate_task_honours_a_name_the_user_chose(loaded: None) -> None:
    plan = maprefac.plan_duplicate(TASK, "22", "Hush")
    assert maprefac.apply(plan) == (True, [])
    assert "Hush" in PrimeItems.tasker_root_elements["all_tasks_by_name"]


def test_duplicate_refuses_a_name_already_in_use(loaded: None) -> None:
    plan = maprefac.plan_duplicate(TASK, "22", "Morning")
    assert plan.is_blocked
    assert plan.blocks[0].reason == "NAME-TAKEN"


def test_duplicate_profile_copies_its_tasks_and_points_at_them(loaded: None) -> None:
    """A copy sharing the original's Task is a second name for it, not a copy."""
    plan = maprefac.plan_duplicate(PROFILE, "100", "Dawn Two")
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])

    profiles = PrimeItems.tasker_root_elements["all_profiles_by_name"]
    new_profile = PrimeItems.tasker_root_elements["all_profiles"][profiles["Dawn Two"]["id"]]["xml"]
    new_entry_task = new_profile.findtext("mid0")

    assert new_entry_task != "20"
    assert _codes(new_entry_task) == _codes("20")
    assert new_entry_task in _members("Home", "tids")
    assert profiles["Dawn Two"]["id"] in _members("Home", "pids")


def test_duplicate_scene_takes_a_name_of_its_own_everywhere(loaded: None) -> None:
    """A Scene's sr= is built from its name, so a copy keeping it still says the old one."""
    plan = maprefac.plan_duplicate(SCENE, "Panel", "Panel Two")
    assert maprefac.apply(plan) == (True, [])

    copied = PrimeItems.tasker_root_elements["all_scenes"]["Panel Two"]["xml"]
    assert copied.findtext("nme") == "Panel Two"
    assert copied.attrib["sr"] == "scenePanel Two"
    assert "Panel Two" in _members("Home", "scenes")
    assert "Panel" in _members("Home", "scenes")


def test_duplicate_project_copies_everything_it_owns(loaded: None) -> None:
    plan = maprefac.plan_duplicate(PROJECT, "Home", "Home Two")
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])

    assert "Home Two" in PrimeItems.tasker_root_elements["all_projects"]
    assert len(_members("Home Two", "tids")) == len(_members("Home", "tids"))
    assert len(_members("Home Two", "pids")) == len(_members("Home", "pids"))
    assert _members("Home Two", "scenes") == ["Panel (copy)"]
    # Nothing shared with the original.
    assert not set(_members("Home Two", "tids")) & set(_members("Home", "tids"))
    assert not set(_members("Home Two", "pids")) & set(_members("Home", "pids"))


def test_duplicate_project_gives_it_a_uuid_of_its_own(loaded: None) -> None:
    """A Project's <id> is a UUID in every real backup, and two Projects must not share one."""
    plan = maprefac.plan_duplicate(PROJECT, "Home", "Home Two")
    assert maprefac.apply(plan) == (True, [])
    projects = PrimeItems.tasker_root_elements["all_projects"]
    assert projects["Home Two"]["xml"].findtext("id") != projects["Home"]["xml"].findtext("id")
    assert projects["Home Two"]["xml"].attrib["sr"] != projects["Home"]["xml"].attrib["sr"]


def test_duplicate_project_repoints_calls_at_the_copies(loaded: None) -> None:
    """The failure this exists to prevent: a copied Project calling back into the original."""
    plan = maprefac.plan_duplicate(PROJECT, "Home", "Home Two")
    assert maprefac.apply(plan) == (True, [])

    copied_morning = _task_id("Morning (copy)")
    call = maprefac._actions(_task(copied_morning))[5]
    assert _string_arg(call, "0") == "Wake Steps (copy)"

    # ...and the Scene reference likewise.
    copied_quiet = _task_id("Quiet (copy)")
    assert _string_arg(maprefac._actions(_task(copied_quiet))[0], "0") == "Panel (copy)"

    # The original is not touched by any of it.
    assert _string_arg(maprefac._actions(_task("20"))[5], "0") == "Wake Steps"


def test_duplicate_project_repoints_its_profiles_task_links(loaded: None) -> None:
    """Those are by id rather than by name, so they need doing separately."""
    plan = maprefac.plan_duplicate(PROJECT, "Home", "Home Two")
    assert maprefac.apply(plan) == (True, [])

    profiles = PrimeItems.tasker_root_elements["all_profiles"]
    for profile_id in _members("Home Two", "pids"):
        for tag in ("mid0", "mid1"):
            linked = profiles[profile_id]["xml"].findtext(tag)
            if linked:
                assert linked in _members("Home Two", "tids")


def test_duplicate_project_warns_about_the_globals_it_cannot_copy(loaded: None) -> None:
    """The single most likely surprise, so it is the first thing the preview says."""
    plan = maprefac.plan_duplicate(PROJECT, "Home", "Home Two")
    assert "Global variables are not copied" in plan.warnings[0]


# ##################################################################################
# The preview, and the gates on applying one.
# ##################################################################################


def test_a_blocked_plan_prints_the_reason_and_not_the_steps(loaded: None) -> None:
    """Showing a user a list of things that are not going to happen would bury the reason."""
    rows = maprefac.report_rows(maprefac.plan_extract("20", [2, 3], "Half"))
    text = "\n".join(row.text for row in rows)
    assert "CANNOT BE DONE" in text
    assert "WHAT WILL HAPPEN" not in text


def test_a_preview_is_clickable_where_it_names_something(loaded: None) -> None:
    """The only way to judge a refactor is to go and look at what it names."""
    rows = maprefac.report_rows(maprefac.plan_extract("20", [2, 3, 4], "Loud Part"))
    targets = [row.target for row in rows if row.target is not None]
    assert targets
    assert any(target.kind == TASK and target.key == "20" for target in targets)
    assert any(target.kind == PROJECT and target.key == "Home" for target in targets)


def test_apply_refuses_a_blocked_plan_even_if_it_is_asked(loaded: None) -> None:
    """The dialog disables the button; apply() does not rely on it having remembered to."""
    plan = maprefac.plan_extract("20", [1, 3], "Bits")
    done, errors = maprefac.apply(plan)
    assert done is False
    assert errors == [plan.blocks[0].explanation]


def test_apply_refuses_a_plan_whose_subject_was_deleted_meanwhile(loaded: None) -> None:
    """A preview can sit on screen while the user deletes the Task it describes."""
    plan = maprefac.plan_extract("20", [2, 3, 4], "Loud Part")
    assert not plan.is_blocked

    taskedit.delete_task("Morning")
    done, errors = maprefac.apply(plan)

    assert done is False
    assert "no longer in the configuration" in errors[0]
    assert "Loud Part" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]


def test_the_whole_refactor_costs_one_undo(loaded: None) -> None:
    """Extract writes a Task, edits a Task and edits a Project.  That is one thing the user did."""
    before = _codes("20")
    plan = maprefac.plan_extract("20", [2, 3, 4], "Loud Part")
    assert maprefac.apply(plan) == (True, [])

    assert sessundo.can_undo()
    assert sessundo.next_undo_label() == plan.what

    assert sessundo.undo()[0] is True
    assert _codes("20") == before
    assert "Loud Part" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert not sessundo.can_undo()


def test_an_undone_refactor_can_be_redone(loaded: None) -> None:
    plan = maprefac.plan_extract("20", [2, 3, 4], "Loud Part")
    assert maprefac.apply(plan) == (True, [])
    sessundo.undo()

    assert sessundo.redo()[0] is True
    assert "Loud Part" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    assert _codes("20") == [VARIABLE_SET, FLASH, PERFORM_TASK, PERFORM_TASK]


# ##################################################################################
# The dialog's translation layer.
#
# guiwins_refactor is widgets and wiring, and neither is testable without a running
# page -- except for the one piece of it that is a decision rather than a layout:
# turning the values in the boxes into a Plan.  That is where the two mistakes a form
# can make live, so it is tested directly, against stand-ins that carry a .value and
# nothing else (which is all _plan_for reads).
# ##################################################################################


class _Box:
    """A stand-in for one widget: something with a .value."""

    def __init__(self, value: object = None) -> None:
        self.value = value


def _widgets(**values: object) -> dict:
    """The widget dict guiwins_refactor builds, filled in with the given values."""
    keys = (
        "extract_task",
        "extract_from",
        "extract_to",
        "extract_name",
        "inline_task",
        "inline_call",
        "move_kind",
        "move_object",
        "move_project",
        "duplicate_kind",
        "duplicate_object",
        "duplicate_name",
    )
    return {key: _Box(values.get(key)) for key in keys}


def test_the_dialog_asks_for_the_range_the_user_selected(loaded: None) -> None:
    """Two pulldowns naming the ends; the operation takes the whole run between them."""
    from maptasker.src import guiwins_refactor

    plan = guiwins_refactor._plan_for(
        guiwins_refactor.EXTRACT,
        _widgets(extract_task="20", extract_from="2", extract_to="4", extract_name="Loud Part"),
    )
    assert plan is not None
    assert not plan.is_blocked
    assert maprefac.apply(plan) == (True, [])
    assert _codes(_task_id("Loud Part")) == [IF, FLASH, END_IF]


def test_the_dialog_does_not_mind_which_end_was_picked_first(loaded: None) -> None:
    """'First action' and 'Last action' are two pulldowns over one list, not a valid order."""
    from maptasker.src import guiwins_refactor

    plan = guiwins_refactor._plan_for(
        guiwins_refactor.EXTRACT,
        _widgets(extract_task="20", extract_from="4", extract_to="2", extract_name="Loud Part"),
    )
    assert plan is not None
    assert not plan.is_blocked


def test_an_unfilled_form_is_not_a_blocked_plan(loaded: None) -> None:
    """An empty box is the user's turn; a block is the tool's answer.  Collapsing the two
    would put "That Task is not in this file" in front of somebody who has not chosen one.
    """
    from maptasker.src import guiwins_refactor

    for mode, filled in (
        (guiwins_refactor.EXTRACT, {"extract_task": "20"}),
        (guiwins_refactor.INLINE, {"inline_task": "20"}),
        (guiwins_refactor.MOVE, {"move_kind": TASK, "move_object": "22"}),
        (guiwins_refactor.DUPLICATE, {}),
    ):
        assert guiwins_refactor._plan_for(mode, _widgets(**filled)) is None


def test_action_zero_is_not_mistaken_for_an_empty_box(loaded: None) -> None:
    """The bug this shape invites: `if not value` is true for action 0, which is a real action."""
    from maptasker.src import guiwins_refactor

    plan = guiwins_refactor._plan_for(
        guiwins_refactor.INLINE,
        _widgets(inline_task="20", inline_call="0"),
    )
    assert plan is not None
    assert plan.blocks[0].reason == "NOT-A-CALL"  # reached the engine, rather than returning None


def test_the_dialog_offers_only_the_calls_that_can_be_inlined(loaded: None) -> None:
    """A pulldown of forty actions where thirty-eight are refusals is a worse answer."""
    assert [number for number, _ in maprefac.call_choices("20")] == [5]
    assert "Wake Steps" in dict(maprefac.call_choices("20"))[5]
    assert maprefac.call_choices("22") == []


def test_the_pickers_name_the_project_so_repeated_names_can_be_told_apart(loaded: None) -> None:
    """Task names are not unique across a configuration and routinely repeat."""
    labels = dict(maprefac.task_choices())
    assert labels["20"] == "Morning  (Home)"
    assert labels["24"] == "Trip  (Away)"
