"""MapTasker one-click Health Check repairs (mapfix) Unit Tests

What these assert is what the repair LEAVES BEHIND, and what it REFUSES.

Every repair here is trivially easy to make look right and easy to get invisibly wrong: an
'End If' appended with an sr= that is already taken lands in the middle of the Task rather
than at the end of it, a timeout written beside a <var> child is ignored by Tasker, and a
Task deleted by name is the wrong Task the moment two of them share one.  So the happy-path
tests check the surroundings as much as the result -- the run order afterwards, the shape of
the element written, the Project membership of what was removed.

The other half is the refusals, and they carry as many tests as the successes: a repair made
where it should not be is the failure this module is arranged to prevent, because the
configuration still parses, still loads, and quietly does something else.

The last assertion of most of these is that the health check no longer reports the finding.
That is the whole claim the feature makes, and it is the one worth checking against the
checker rather than against this file's idea of what the checker wants.

Fixture-driven, the same arrangement test_maprefac.py, test_mapswap.py and test_healthck.py
use.  The fixture is small and every part of it is load-bearing; see its own comments.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import healthck, mapfix, sessundo, taskerd
from maptasker.src.mapjump import actions_in_map_order
from maptasker.src.primitem import PrimeItems

# Codes used below, named so the tests read as prose.
WAIT = "30"
IF = "37"
END_IF = "38"
FOR = "39"
END_FOR = "40"
FLASH = "548"
GOTO = "135"
RUN_SHELL = "123"

# One Project, one Profile, and a Task for each repair -- plus, for each repair that can be
# refused, the case that refuses it.
#
#   Task 20 'Nightly'    a For that is never closed, and a Wait inside it.  Started by the
#                        Profile and carrying no <rty>, so it is also the MISSING-COLLISION
#                        subject -- one Task raising two findings, which is the ordinary
#                        case and the one that would catch a planner keyed by Task.
#   Task 21 'Fetch'      a Run Shell with its Timeout argument present and zero, an HTTP-ish
#                        blocking action of the sort NO-TIMEOUT is about.
#   Task 22 'Jumper'     an If that is never closed, and a Goto naming a label nothing
#                        carries -- with two labelled actions to choose between, one of
#                        which is the Goto's own (which must NOT be offered).
#   Task 23 'Nowhere'    the same broken Goto with no labels anywhere in the Task, which is
#                        the one FLOW-GOTO-MISSING-LABEL case that has to be refused.
#   Task 24 'Spare'      unreferenced, uniquely named -- the delete subject.
#   Task 25/26 'Twin'    unreferenced and sharing a name, which the delete has to refuse.
#
# Task 20's <Action> children are written OUT of run order (act2 before act1), because
# Tasker orders actions by the numeric suffix of sr= and writes them sorted as text.  A
# suite that fed them in document order would pass on an implementation that used
# findall("Action") and be wrong on every real backup.
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>100</pids>
    <tids>20,21,22,23,24,25,26</tids>
  </Project>
  <Profile sr="prof100" ve="2">
    <id>100</id>
    <nme>Dawn</nme>
    <mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time>
  </Profile>
  <Task sr="task20" ve="2">
    <id>20</id>
    <nme>Nightly</nme>
    <Action sr="act0" ve="7">
      <code>39</code>
      <Str sr="arg0" ve="3">%item</Str>
      <Str sr="arg1" ve="3">a,b,c</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">tick</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>30</code>
      <Int sr="arg0" val="0"/>
      <Int sr="arg1" val="30"/>
      <Int sr="arg2" val="0"/>
      <Int sr="arg3" val="0"/>
      <Int sr="arg4" val="0"/>
    </Action>
  </Task>
  <Task sr="task21" ve="2">
    <id>21</id>
    <nme>Fetch</nme>
    <Action sr="act0" ve="7">
      <code>123</code>
      <Str sr="arg0" ve="3">echo hello</Str>
      <Int sr="arg1" val="0"/>
    </Action>
  </Task>
  <Task sr="task22" ve="2">
    <id>22</id>
    <nme>Jumper</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <label>the top</label>
      <Str sr="arg0" ve="3">start</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>37</code>
      <ConditionList sr="if">
        <Condition sr="c0" ve="3"><lhs>%x</lhs><op>7</op><rhs>0</rhs></Condition>
      </ConditionList>
    </Action>
    <Action sr="act2" ve="7">
      <code>135</code>
      <label>the jump itself</label>
      <Int sr="arg0" val="1"/>
      <Int sr="arg1" val="1"/>
      <Str sr="arg2" ve="3">nowhere at all</Str>
    </Action>
  </Task>
  <Task sr="task23" ve="2">
    <id>23</id>
    <nme>Nowhere</nme>
    <Action sr="act0" ve="7">
      <code>135</code>
      <Int sr="arg0" val="1"/>
      <Int sr="arg1" val="1"/>
      <Str sr="arg2" ve="3">missing</Str>
    </Action>
  </Task>
  <Task sr="task24" ve="2">
    <id>24</id>
    <nme>Spare</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">nobody calls me</Str>
    </Action>
  </Task>
  <Task sr="task25" ve="2">
    <id>25</id>
    <nme>Twin</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">one</Str>
    </Action>
  </Task>
  <Task sr="task26" ve="2">
    <id>26</id>
    <nme>Twin</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">two</Str>
    </Action>
  </Task>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file.

    The same loader test_maprefac.py uses, including tasker_arg_specs -- taskedit reads it
    to decide what an argument is, and an argument synthesized without it comes out wrong
    rather than failing.
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
    """The fixture configuration, in the tables mapfix reads, with an empty undo history."""
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
    return [(action.findtext("code") or "") for action in actions_in_map_order(_task(task_id))]


def _only(plan: mapfix.Plan, tag: str) -> tuple[int, mapfix.Fix]:
    """The one repair in this plan for that tag, as (position, fix)."""
    matches = [(position, fix) for position, fix in enumerate(plan.fixes) if fix.tag == tag]
    assert len(matches) == 1, f"expected exactly one {tag}, got {len(matches)}"
    return matches[0]


def _positions(plan: mapfix.Plan, tag: str) -> list[int]:
    """Every position in the plan carrying that tag."""
    return [position for position, fix in enumerate(plan.fixes) if fix.tag == tag]


def _tags_reported() -> list[str]:
    """Every tag the full health check raises against the configuration as it stands now."""
    return [finding.tag for finding in healthck.collect_findings().findings]


def _tick_only(plan: mapfix.Plan, positions: list[int]) -> None:
    """Tick exactly these repairs and nothing else."""
    plan.selected = set(positions)


# ##################################################################################
# What is offered at all.
# ##################################################################################


def test_plan_offers_a_repair_for_every_repairable_finding(loaded: None) -> None:
    """Each of the six repairable tags in the fixture turns up exactly once, and nothing else does."""
    plan = mapfix.plan_fixes()

    offered = {fix.tag for fix in plan.fixes}
    assert offered == {
        mapfix.MISSING_COLLISION,
        mapfix.NO_TIMEOUT,
        mapfix.IF_WITHOUT_END_IF,
        mapfix.FOR_WITHOUT_END_FOR,
        mapfix.GOTO_MISSING_LABEL,
        mapfix.UNREFERENCED_TASK,
    }
    # Every offered repair is about a Task, carries an element to check and knows how to run.
    for fix in plan.fixes:
        assert fix.elements
        assert fix.run is not None
        assert fix.where.key


def test_plan_leaves_the_delete_and_the_undecided_unticked(loaded: None) -> None:
    """The two nobody should apply by not looking: the one that deletes, and the one nobody has decided."""
    plan = mapfix.plan_fixes()

    for position, fix in enumerate(plan.fixes):
        if fix.tag == mapfix.UNREFERENCED_TASK or not plan.is_ready(position):
            assert position not in plan.selected
        else:
            assert position in plan.selected

    # And the undecided one really is in there, so this is not passing by describing an
    # empty set: a tick on it could not be honoured, because apply() refuses it.
    goto_position, _ = _only(plan, mapfix.GOTO_MISSING_LABEL)
    assert goto_position not in plan.selected


def test_plan_honours_the_health_checks_own_skip_list(loaded: None) -> None:
    """A category the user has unticked in the Health Check panel is not offered here either."""
    plan = mapfix.plan_fixes(skip=[mapfix.UNREFERENCED_TASK, mapfix.NO_TIMEOUT])

    assert not _positions(plan, mapfix.UNREFERENCED_TASK)
    assert not _positions(plan, mapfix.NO_TIMEOUT)
    assert _positions(plan, mapfix.MISSING_COLLISION)


def test_plan_offers_nothing_for_a_finding_it_cannot_repair(loaded: None) -> None:
    """A tag with no repair produces neither a fix nor a skip -- it is simply not this dialog's business."""
    plan = mapfix.plan_fixes()

    assert "DUPLICATE-NAME" in _tags_reported()  # The fixture's two 'Twin' Tasks.
    assert all(fix.tag in mapfix.FIXABLE_TAGS for fix in plan.fixes)
    assert all(item.tag in mapfix.FIXABLE_TAGS for item in plan.skips)


def test_report_rows_name_every_repair_and_link_to_it(loaded: None) -> None:
    """The preview is clickable, which for a delete is the only way to judge it."""
    plan = mapfix.plan_fixes()
    rows = mapfix.report_rows(plan)

    text = "\n".join(row.text for row in rows)
    assert "WOULD REPAIR" in text
    assert "CANNOT BE REPAIRED HERE" in text
    # One linked row per repair and per skip, and no more: the location line is the
    # clickable one, not the prose under it.
    linked = [row for row in rows if row.target is not None]
    assert len(linked) == len(plan.fixes) + len(plan.skips)


# ##################################################################################
# Collision handling.
# ##################################################################################


def test_collision_writes_the_chosen_handling_and_clears_the_finding(loaded: None) -> None:
    """The chosen handling is what lands in <rty>, and the finding stops being reported."""
    plan = mapfix.plan_fixes()
    position, fix = _only(plan, mapfix.MISSING_COLLISION)
    assert fix.where.key == "20"

    plan.chosen[position] = "2"  # Run Both Together
    _tick_only(plan, [position])
    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    assert _task("20").findtext("rty") == "2"
    assert mapfix.MISSING_COLLISION not in _tags_reported()


def test_collision_defaults_to_abort_existing_task(loaded: None) -> None:
    """The default is the finding's own first suggestion, and it is applied when nobody chooses."""
    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.MISSING_COLLISION)
    _tick_only(plan, [position])

    assert "Abort Existing Task" in plan.describe(position)
    mapfix.apply(plan)

    assert _task("20").findtext("rty") == "1"


def test_collision_goes_in_taskers_own_child_order(loaded: None) -> None:
    """<rty> is inserted where Tasker writes it, not appended -- see objprops.set_child_text_in_tag_order."""
    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.MISSING_COLLISION)
    _tick_only(plan, [position])
    mapfix.apply(plan)

    plain = [child.tag for child in _task("20") if child.tag[:1].islower()]
    assert plain == sorted(plain)


# ##################################################################################
# Timeouts.
# ##################################################################################


def test_timeout_is_written_into_the_argument_proflint_read(loaded: None) -> None:
    """Into the same argument the finding came out of -- a second derivation could pick another."""
    plan = mapfix.plan_fixes()
    position, fix = _only(plan, mapfix.NO_TIMEOUT)
    assert (fix.where.key, fix.where.action) == ("21", 1)

    plan.chosen[position] = "45"
    _tick_only(plan, [position])
    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    action = actions_in_map_order(_task("21"))[0]
    assert action.find("Int[@sr='arg1']").attrib["val"] == "45"
    assert mapfix.NO_TIMEOUT not in _tags_reported()


def test_timeout_refuses_a_value_that_is_not_a_number(loaded: None) -> None:
    """Reported against the action it was about, and nothing is written."""
    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.NO_TIMEOUT)
    plan.chosen[position] = "soon"
    _tick_only(plan, [position])

    repaired, errors = mapfix.apply(plan)

    assert repaired == 0
    assert len(errors) == 1
    assert "soon" in errors[0]
    assert actions_in_map_order(_task("21"))[0].find("Int[@sr='arg1']").attrib["val"] == "0"


def test_timeout_accepts_what_a_number_box_actually_hands_back(loaded: None) -> None:
    """NiceGUI's ui.number gives a FLOAT whatever its format string says, so "60" arrives as "60.0"."""
    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.NO_TIMEOUT)
    plan.chosen[position] = "60.0"
    _tick_only(plan, [position])

    assert "60 seconds" in plan.describe(position)

    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    assert actions_in_map_order(_task("21"))[0].find("Int[@sr='arg1']").attrib["val"] == "60"


def test_whole_seconds_takes_only_a_whole_number_above_zero() -> None:
    """The one place the preview line and the value written are normalised, so they cannot differ."""
    assert mapfix.whole_seconds("30") == "30"
    assert mapfix.whole_seconds(" 30.0 ") == "30"
    assert mapfix.whole_seconds("0") == ""
    assert mapfix.whole_seconds("0.5") == ""
    assert mapfix.whole_seconds("-5") == ""
    assert mapfix.whole_seconds("") == ""
    assert mapfix.whole_seconds("soon") == ""


def test_timeout_refuses_zero(loaded: None) -> None:
    """Zero is the state being repaired, so writing it back is not a repair."""
    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.NO_TIMEOUT)
    plan.chosen[position] = "0"
    _tick_only(plan, [position])

    repaired, errors = mapfix.apply(plan)

    assert (repaired, len(errors)) == (0, 1)
    assert mapfix.NO_TIMEOUT in _tags_reported()


def test_timeout_is_synthesized_when_the_action_never_carried_one(loaded: None) -> None:
    """An argument that is absent rather than zero is built the way Tasker writes one, and put in order."""
    action = actions_in_map_order(_task("21"))[0]
    action.remove(action.find("Int[@sr='arg1']"))

    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.NO_TIMEOUT)
    plan.chosen[position] = "90"
    _tick_only(plan, [position])
    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    written = actions_in_map_order(_task("21"))[0].find("Int[@sr='arg1']")
    assert written is not None
    assert written.attrib["val"] == "90"
    # Arguments sorted by 'sr' as text, after the non-argument children -- order_action_children's job.
    arguments = [child.attrib["sr"] for child in actions_in_map_order(_task("21"))[0] if "sr" in child.attrib]
    assert arguments == sorted(arguments)


# ##################################################################################
# Closing a block.
# ##################################################################################


def test_end_if_is_appended_as_the_tasks_last_action(loaded: None) -> None:
    """Last in RUN order, which is what sr= decides and not what document order suggests."""
    plan = mapfix.plan_fixes()
    position, fix = _only(plan, mapfix.IF_WITHOUT_END_IF)
    assert fix.where.key == "22"

    _tick_only(plan, [position])
    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    assert _codes("22") == [FLASH, IF, GOTO, END_IF]
    assert mapfix.IF_WITHOUT_END_IF not in _tags_reported()


def test_end_for_closes_a_for_without_touching_the_if_family(loaded: None) -> None:
    """The closer matches the block that was left open, not whichever one is more common."""
    plan = mapfix.plan_fixes()
    position, fix = _only(plan, mapfix.FOR_WITHOUT_END_FOR)
    assert fix.where.key == "20"

    _tick_only(plan, [position])
    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    assert _codes("20") == [FOR, WAIT, FLASH, END_FOR]
    assert mapfix.FOR_WITHOUT_END_FOR not in _tags_reported()


def test_a_closer_is_appended_with_an_sr_that_is_not_already_taken(loaded: None) -> None:
    """A Task whose numbering has a gap in it must not be handed an sr that puts the closer mid-Task."""
    task = _task("22")
    for action in task.findall("Action"):
        if action.attrib["sr"] == "act2":
            action.set("sr", "act9")  # act0, act1, act9 -- the count is no guide at all.

    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.IF_WITHOUT_END_IF)
    _tick_only(plan, [position])
    mapfix.apply(plan)

    assert _codes("22") == [FLASH, IF, GOTO, END_IF]


def test_two_unclosed_blocks_in_one_task_are_closed_innermost_first(loaded: None) -> None:
    """A For opened inside an If has to be closed before the If, or the two end up crossed."""
    task = _task("22")
    opener = type(task)("Action", {"sr": "act3", "ve": "7"})
    code = type(task)("code")
    code.text = FOR
    opener.append(code)
    task.append(opener)

    plan = mapfix.plan_fixes()
    positions = [
        position
        for position, fix in enumerate(plan.fixes)
        if fix.where.key == "22" and fix.tag in (mapfix.IF_WITHOUT_END_IF, mapfix.FOR_WITHOUT_END_FOR)
    ]
    assert len(positions) == 2
    _tick_only(plan, positions)
    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (2, [])
    # End For first: it closes the inner block, opened last.
    assert _codes("22") == [FLASH, IF, GOTO, FOR, END_FOR, END_IF]
    assert mapfix.IF_WITHOUT_END_IF not in _tags_reported()


# ##################################################################################
# Repointing a Goto.
# ##################################################################################


def test_goto_offers_every_label_but_its_own(loaded: None) -> None:
    """A Goto pointed at itself is an infinite loop, so it is not on the menu."""
    plan = mapfix.plan_fixes()
    _, fix = _only(plan, mapfix.GOTO_MISSING_LABEL)

    offered = [label for label, _shown in fix.choice.options]
    assert offered == ["the top"]
    assert "the jump itself" not in offered


def test_goto_arrives_with_no_choice_made_and_cannot_be_applied_until_one_is(loaded: None) -> None:
    """The one repair with no defensible default refuses to be made by somebody who never looked."""
    plan = mapfix.plan_fixes()
    position, fix = _only(plan, mapfix.GOTO_MISSING_LABEL)

    assert fix.choice.value == ""
    assert not plan.is_ready(position)

    _tick_only(plan, [position])
    repaired, errors = mapfix.apply(plan)

    assert repaired == 0
    assert len(errors) == 1
    assert "nothing has been chosen" in errors[0]
    assert mapfix.GOTO_MISSING_LABEL in _tags_reported()


def test_goto_points_at_the_chosen_label_and_clears_the_finding(loaded: None) -> None:
    """The label the user picked, written into the argument Tasker reads it from."""
    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.GOTO_MISSING_LABEL)
    plan.chosen[position] = "the top"
    _tick_only(plan, [position])

    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    goto = actions_in_map_order(_task("22"))[2]
    assert goto.find("Str[@sr='arg2']").text == "the top"
    # Task 'Nowhere' still carries the same finding -- it has no label to be pointed at --
    # so the claim is about this Task, not about the configuration.
    still_broken = [
        finding.tag
        for finding in healthck.collect_findings().findings
        if finding.target is not None and finding.target.key == "22"
    ]
    assert mapfix.GOTO_MISSING_LABEL not in still_broken


def test_goto_is_skipped_when_the_task_carries_no_labels(loaded: None) -> None:
    """Nothing to point at, so it is reported as a skip rather than quietly dropped."""
    plan = mapfix.plan_fixes()

    skipped = [item for item in plan.skips if item.tag == mapfix.GOTO_MISSING_LABEL]
    assert len(skipped) == 1
    assert skipped[0].where.key == "23"
    assert "no other action in this task carries a label" in skipped[0].explanation.lower()


# ##################################################################################
# Deleting an unreferenced Task.
# ##################################################################################


def test_delete_removes_the_task_and_unlinks_it_from_its_project(loaded: None) -> None:
    """Both tables and the owning Project's <tids>, which is what makes it gone from every view."""
    plan = mapfix.plan_fixes()
    position = next(
        position for position in _positions(plan, mapfix.UNREFERENCED_TASK) if plan.fixes[position].where.key == "24"
    )
    _tick_only(plan, [position])

    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (1, [])
    assert "24" not in PrimeItems.tasker_root_elements["all_tasks"]
    assert "Spare" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]
    members = PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"].findtext("tids")
    assert "24" not in members.split(",")


def test_delete_is_refused_for_two_tasks_sharing_a_name(loaded: None) -> None:
    """Deleting by name would take whichever of them the by-name table happens to hold."""
    plan = mapfix.plan_fixes()

    twins = [item for item in plan.skips if item.tag == mapfix.UNREFERENCED_TASK]
    assert {item.where.key for item in twins} == {"25", "26"}
    assert all("same name" in item.explanation for item in twins)
    # Neither of them is offered.  Refusing only the one the by-name table does not happen
    # to hold would delete a Task called 'Twin' and leave the user unable to say which.
    offered = {plan.fixes[position].where.key for position in _positions(plan, mapfix.UNREFERENCED_TASK)}
    assert offered.isdisjoint({"25", "26"})


def test_a_delete_is_applied_after_every_other_repair_to_the_same_task(loaded: None) -> None:
    """Both ticked repairs are made, and neither is written to a Task that has already gone."""
    # 'Fetch' is unreferenced as well as short of a timeout, so both are offered for it.
    plan = mapfix.plan_fixes()
    timeout_position, _ = _only(plan, mapfix.NO_TIMEOUT)
    delete_positions = [
        position for position in _positions(plan, mapfix.UNREFERENCED_TASK) if plan.fixes[position].where.key == "21"
    ]
    assert delete_positions, "Task 'Fetch' should be reported unreferenced"

    plan.chosen[timeout_position] = "30"
    _tick_only(plan, [*delete_positions, timeout_position])
    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (2, [])
    assert "21" not in PrimeItems.tasker_root_elements["all_tasks"]


def test_a_closer_is_applied_before_a_delete_of_the_same_task(loaded: None) -> None:
    """The ordering above holds whichever way round the two sit in the plan."""
    plan = mapfix.plan_fixes()
    closer_position, _ = _only(plan, mapfix.IF_WITHOUT_END_IF)
    delete_positions = [
        position for position in _positions(plan, mapfix.UNREFERENCED_TASK) if plan.fixes[position].where.key == "22"
    ]
    _tick_only(plan, [closer_position, *delete_positions])

    repaired, errors = mapfix.apply(plan)

    assert errors == []
    assert repaired == 1 + len(delete_positions)


# ##################################################################################
# The rules that hold for every repair.
# ##################################################################################


def test_the_whole_plan_is_one_undo(loaded: None) -> None:
    """Five repairs across four Tasks, and one press of Undo puts every one of them back."""
    plan = mapfix.plan_fixes()
    goto_position, _ = _only(plan, mapfix.GOTO_MISSING_LABEL)
    timeout_position, _ = _only(plan, mapfix.NO_TIMEOUT)
    plan.chosen[goto_position] = "the top"
    plan.chosen[timeout_position] = "30"

    before = _codes("20"), _codes("22")
    repaired, errors = mapfix.apply(plan)

    assert errors == []
    assert repaired == len(plan.selected)
    assert sessundo.can_undo()

    done, _message = sessundo.undo()

    assert done
    assert (_codes("20"), _codes("22")) == before
    assert _task("20").find("rty") is None


def test_nothing_ticked_changes_nothing_and_leaves_no_undo_entry(loaded: None) -> None:
    """An empty plan must not cost a press of Undo that puts nothing back."""
    plan = mapfix.plan_fixes()
    plan.selected = set()

    repaired, errors = mapfix.apply(plan)

    assert (repaired, errors) == (0, [])
    assert not sessundo.can_undo()


def test_a_repair_whose_element_has_gone_is_refused_rather_than_written(loaded: None) -> None:
    """A preview can sit on screen while the user deletes the Task in another dialog."""
    plan = mapfix.plan_fixes()
    position, _ = _only(plan, mapfix.IF_WITHOUT_END_IF)
    _tick_only(plan, [position])

    detached = next(element for element in PrimeItems.xml_root if element.attrib.get("sr") == "task22")
    del PrimeItems.tasker_root_elements["all_tasks"]["22"]
    del PrimeItems.tasker_root_elements["all_tasks_by_name"]["Jumper"]
    PrimeItems.xml_root.remove(detached)

    repaired, errors = mapfix.apply(plan)

    assert repaired == 0
    assert len(errors) == 1
    assert "no longer in the configuration" in errors[0]
    # Nothing was written to the element that is no longer anybody's -- the End If would have
    # gone in here, and a resurrected Task is the failure the attachment check exists for.
    assert len(detached.findall("Action")) == 3


def test_ticks_and_choices_survive_the_plan_being_rebuilt(loaded: None) -> None:
    """Carried by what they point at, never by where they sat -- see Fix.identity."""
    plan = mapfix.plan_fixes()
    goto_position, goto = _only(plan, mapfix.GOTO_MISSING_LABEL)
    plan.chosen[goto_position] = "the top"
    plan.selected = {goto_position}

    ticks = plan.ticked_identities()
    values = {goto.identity: "the top"}

    rebuilt = mapfix.plan_fixes()
    rebuilt.restore(ticks, values)

    position, _ = _only(rebuilt, mapfix.GOTO_MISSING_LABEL)
    assert rebuilt.selected == {position}
    assert rebuilt.value_of(position) == "the top"
    assert rebuilt.is_ready(position)


def test_plan_is_empty_and_harmless_with_nothing_loaded() -> None:
    """Every table empty, so there is nothing to find and nothing to repair."""
    PrimeItems.tasker_root_elements = {
        "all_projects": {},
        "all_profiles": {},
        "all_tasks": {},
        "all_scenes": {},
        "all_tasks_by_name": {},
        "all_profiles_by_name": {},
        "all_services": [],
    }
    PrimeItems.xml_root = None

    plan = mapfix.plan_fixes()

    assert plan.is_empty
    assert mapfix.apply(plan) == (0, [])


def test_every_repairable_tag_is_a_category_the_health_check_reports() -> None:
    """A tag renamed in healthck and not here would silently stop being offered."""
    known = {category.tag for category in healthck.all_categories()}

    assert set(mapfix.FIXABLE_TAGS) <= known
    assert set(mapfix.WHAT_IT_DOES) == set(mapfix.FIXABLE_TAGS)
