"""MapTasker variable rename and scope assistant (maprefac_variable) Unit Tests

What matters here is what is REFUSED, and that refusing leaves the configuration alone.

A rename is easy to get visibly right.  What goes wrong is the change of scope that rides on a spelling: Tasker
reads %counter as private to the running Task and %Counter as one variable for the whole file, so changing the case
changes who can see the value, and nothing about the result looks different.  So the tests that matter most provoke
each reason the change must not be made -- a name already taken, a Task that reads a value it never set, a Scene
that cannot see a local -- and then assert NOTHING was written.

Fixture-driven, the same arrangement test_maprefac.py and test_mapswap.py use.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from collections.abc import Iterator

import pytest
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapgen import taskerd, varxref
from maptasker.src.mapops import maprefac, maprefac_variable
from maptasker.src.mapops.maprefac_variable import RENAME, TO_GLOBAL, TO_LOCAL

#   %Count    a global set in Stepper and read there afterwards, and read in Reader that never sets it
#   %Solo     a global declared in the Variables tab, set then read in ONE Task: safe to make local
#   %Hits     a global one Task increments ('%Hits + 1') -- it reads the previous run's value
#   %Total    a global that Mixer uses next to a local %total of its own: the clash
#   %Gate     a global a Scene and a Profile condition read: no local could be seen from there
#   %tally    a local in Stepper AND in Twin -- two variables with one name
#   %steps    a second local of Twin's, so that renaming %tally to %steps there is a clash
#   %Pair     a global two Tasks each set before they read: safe to make local, and no longer shared
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="var0"><n>%Solo</n><v>9</v></Variable>
  <Variable sr="var1"><n>%Orphan</n><v>1</v></Variable>
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>10</pids>
    <tids>40,41,42,43,44,45,46,47</tids>
    <scenes>Panel</scenes>
  </Project>
  <Profile sr="prof10" ve="2">
    <id>10</id>
    <nme>Watcher</nme>
    <mid0>45</mid0>
    <State sr="con0" ve="2">
      <code>160</code>
      <Str sr="arg0" ve="3">%Gate is on</Str>
    </State>
  </Profile>
  <Task sr="task40" ve="2">
    <id>40</id>
    <nme>Stepper</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Count</Str>
      <Str sr="arg1" ve="3">0</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">Count is %Count and %Counter</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%tally</Str>
      <Str sr="arg1" ve="3">1</Str>
    </Action>
    <Action sr="act3" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">tally %tally</Str>
    </Action>
  </Task>
  <Task sr="task41" ve="2">
    <id>41</id>
    <nme>Reader</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">see %Count</Str>
    </Action>
  </Task>
  <Task sr="task42" ve="2">
    <id>42</id>
    <nme>Solo user</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Solo</Str>
      <Str sr="arg1" ve="3">x</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">solo is %Solo</Str>
    </Action>
  </Task>
  <Task sr="task43" ve="2">
    <id>43</id>
    <nme>Mixer</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Total</Str>
      <Str sr="arg1" ve="3">1</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">big %Total</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%total</Str>
      <Str sr="arg1" ve="3">2</Str>
    </Action>
    <Action sr="act3" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">small %total</Str>
    </Action>
  </Task>
  <Task sr="task44" ve="2">
    <id>44</id>
    <nme>Hit counter</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Hits</Str>
      <Str sr="arg1" ve="3">%Hits + 1</Str>
    </Action>
  </Task>
  <Task sr="task45" ve="2">
    <id>45</id>
    <nme>Twin</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%tally</Str>
      <Str sr="arg1" ve="3">5</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">twin %tally</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%steps</Str>
      <Str sr="arg1" ve="3">1</Str>
    </Action>
  </Task>
  <Task sr="task46" ve="2">
    <id>46</id>
    <nme>Pair A</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Pair</Str>
      <Str sr="arg1" ve="3">a</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">a has %Pair</Str>
    </Action>
  </Task>
  <Task sr="task47" ve="2">
    <id>47</id>
    <nme>Pair B</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Pair</Str>
      <Str sr="arg1" ve="3">b</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">b has %Pair</Str>
    </Action>
  </Task>
  <Scene sr="scenePanel">
    <nme>Panel</nme>
    <EditTextElement sr="elt0">
      <geom sr="geom"><h>50</h></geom>
      <Str sr="arg0" ve="3">Entry</Str>
      <Str sr="arg1" ve="3">%Gate</Str>
    </EditTextElement>
  </Scene>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file."""
    root = ET.fromstring(xml_text)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.xml_tree = ET.ElementTree(root)
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")

    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file, encoding="utf-8") as handle:
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
def loaded() -> Iterator[None]:
    """The fixture configuration, in the tables the planner reads, with an empty undo history."""
    sessundo.clear(PrimeItems)
    _load(_FIXTURE_XML)
    yield
    sessundo.clear(PrimeItems)


def _texts(task_id: str) -> list[str]:
    """Every <Str> of a Task, in document order -- everything a variable could be written in."""
    task = PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]
    return [(child.text or "") for child in task.iter("Str")]


def _snapshot() -> str:
    """The whole configuration as text, to prove a refused change wrote nothing."""
    return ET.tostring(PrimeItems.xml_root, encoding="unicode")


def _plan(operation: str, name: str, owner: str | None = "", new_name: str = "") -> maprefac_variable.Plan:
    """A plan for the fixture, the way the dialog asks for one."""
    return maprefac_variable.plan_variable(operation, name, owner, new_name, state=PrimeItems)


def _reasons(plan: maprefac_variable.Plan) -> list[str]:
    """The tag of every block, in order."""
    return [block.reason for block in plan.blocks]


# ##################################################################################
# Names, and what the dialog's pulldown is made of.
# ##################################################################################


def test_a_scope_change_implies_the_spelling() -> None:
    """Lower case is a local and a leading capital is a global, because that is how Tasker decides."""
    assert maprefac_variable.suggested_name(TO_LOCAL, "%MyCount") == "%mycount"
    assert maprefac_variable.suggested_name(TO_GLOBAL, "%mycount") == "%Mycount"
    assert maprefac_variable.suggested_name(TO_GLOBAL, "mycount") == "%Mycount"
    assert maprefac_variable.suggested_name(RENAME, "%anything") == ""


def test_a_choice_key_round_trips_every_owner() -> None:
    """A global's empty owner, a Task id and 'every instance' all survive being a pulldown key."""
    for owner in ("", "40", maprefac_variable.EVERY_INSTANCE):
        key = maprefac_variable.choice_key("%tally", owner)
        assert maprefac_variable.split_key(key) == ("%tally", owner)


def test_each_operation_is_offered_only_the_variables_it_can_be_asked_of(loaded: None) -> None:
    """Make local lists globals, Make global lists locals, and neither lists what Tasker supplies."""
    index = varxref.build_index(state=PrimeItems)
    local_names = {
        maprefac_variable.split_key(key)[0] for key, _ in maprefac_variable.variable_choices(index, TO_LOCAL)
    }
    global_names = {
        maprefac_variable.split_key(key)[0] for key, _ in maprefac_variable.variable_choices(index, TO_GLOBAL)
    }
    every_name = {maprefac_variable.split_key(key)[0] for key, _ in maprefac_variable.variable_choices(index, RENAME)}

    assert "%Count" in local_names
    assert "%tally" not in local_names
    assert "%tally" in global_names
    assert "%Count" not in global_names
    assert {"%Count", "%tally"} <= every_name


# ##################################################################################
# Rename.
# ##################################################################################


def test_a_rename_reaches_every_use_and_only_the_whole_name(loaded: None) -> None:
    """%Count is rewritten in both Tasks and the Scene-free places that name it; %Counter is left alone."""
    plan = _plan(RENAME, "%Count", "", "%Tally")
    assert not plan.is_blocked, [block.explanation for block in plan.blocks]
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _texts("40")[:3] == ["%Tally", "0", "Count is %Tally and %Counter"]
    assert _texts("41") == ["see %Tally"]


def test_a_rename_of_a_declared_global_moves_the_variables_tab_entry_too(loaded: None) -> None:
    """Leaving the declaration orphans its value under a name nothing uses."""
    plan = _plan(RENAME, "%Solo", "", "%Lonely")
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    names = [(variable.findtext("n") or "") for variable in PrimeItems.xml_root.findall("Variable")]
    assert names == ["%Lonely", "%Orphan"]
    assert _texts("42") == ["%Lonely", "x", "solo is %Lonely"]


def test_a_rename_of_a_local_stays_inside_its_own_task(loaded: None) -> None:
    """%tally is two variables, one per Task; renaming Stepper's must not touch Twin's."""
    plan = _plan(RENAME, "%tally", "40", "%running")
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _texts("40")[3:] == ["%running", "1", "tally %running"]
    assert _texts("45") == ["%tally", "5", "twin %tally", "%steps", "1"]


def test_a_rename_of_every_instance_renames_them_all(loaded: None) -> None:
    """The all-instances choice is how 'rename the loop counter throughout' is said."""
    plan = _plan(RENAME, "%tally", maprefac_variable.EVERY_INSTANCE, "%rounds")
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _texts("45")[:3] == ["%rounds", "5", "twin %rounds"]
    assert "tally %rounds" in _texts("40")


def test_a_rename_onto_a_name_already_in_use_is_refused_as_a_clash(loaded: None) -> None:
    """Two variables silently becoming one is a merge, and a rename must never be one."""
    before = _snapshot()
    plan = _plan(RENAME, "%Count", "", "%Total")

    assert _reasons(plan) == ["NAME-CLASH"]
    assert "ONE variable" in plan.blocks[0].explanation
    assert maprefac.apply(plan, state=PrimeItems)[0] is False
    assert _snapshot() == before


def test_a_local_rename_is_refused_in_the_task_that_already_has_that_name(loaded: None) -> None:
    """%steps is free in Stepper and taken in Twin, so it is Twin that is named -- and Stepper is not."""
    before = _snapshot()
    plan = _plan(RENAME, "%tally", maprefac_variable.EVERY_INSTANCE, "%steps")

    assert _reasons(plan) == ["NAME-CLASH"]
    assert "Twin" in plan.blocks[0].explanation
    assert "Stepper" not in plan.blocks[0].explanation
    assert maprefac.apply(plan, state=PrimeItems)[0] is False
    assert _snapshot() == before


def test_the_same_local_rename_is_fine_where_the_name_is_free(loaded: None) -> None:
    """Stepper alone has no %steps, so renaming only its %tally goes ahead."""
    assert not _plan(RENAME, "%tally", "40", "%steps").is_blocked


def test_a_rename_that_changes_the_spelling_of_the_scope_points_at_the_right_move(loaded: None) -> None:
    """'%Count' -> '%count' is a promotion's opposite, not a rename; the block says which button to press."""
    plan = _plan(RENAME, "%Count", "", "%count")

    assert _reasons(plan) == ["SPELLING"]
    assert "Make local" in plan.blocks[0].explanation


@pytest.mark.parametrize("name", ["%BATT", "%ab", "%1x"])
def test_unusable_names_are_refused(loaded: None, name: str) -> None:
    """A built-in, a name too short to rewrite safely, and one Tasker would not accept."""
    assert _reasons(_plan(RENAME, "%Count", "", name)) == ["NAME"]


def test_a_variable_only_declared_has_nothing_to_rewrite_when_made_local(loaded: None) -> None:
    """%Orphan is in the Variables tab and in no Task: a plan that changes nothing must not offer Apply."""
    plan = _plan(TO_LOCAL, "%Orphan")

    assert _reasons(plan) == ["NOTHING-TO-REWRITE"]
    assert not plan.can_apply


def test_a_variable_nothing_uses_is_said_to_be_unused(loaded: None) -> None:
    assert _reasons(_plan(RENAME, "%Nothing", "", "%Other")) == ["NOT-USED"]


# ##################################################################################
# Global to local.
# ##################################################################################


def test_a_global_used_by_one_task_can_become_its_local(loaded: None) -> None:
    """Set then read in one Task: nothing outside it can notice, so it goes ahead."""
    plan = _plan(TO_LOCAL, "%Solo")
    assert not plan.is_blocked, [block.explanation for block in plan.blocks]
    assert plan.what == "Make %Solo a local variable (%solo)"
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _texts("42") == ["%solo", "x", "solo is %solo"]


def test_a_global_made_local_leaves_its_variables_tab_entry_and_says_so(loaded: None) -> None:
    """The entry stays, nothing reads it, and the preview tells the user to delete it."""
    plan = _plan(TO_LOCAL, "%Solo")
    maprefac.apply(plan, state=PrimeItems)

    assert [(v.findtext("n") or "") for v in PrimeItems.xml_root.findall("Variable")] == ["%Solo", "%Orphan"]
    assert any("Variables tab" in warning for warning in plan.warnings)


def test_a_task_that_reads_before_it_sets_stops_the_change(loaded: None) -> None:
    """Reader never sets %Count: as a local it would be empty every time, so the action would change meaning."""
    before = _snapshot()
    plan = _plan(TO_LOCAL, "%Count")

    assert _reasons(plan) == ["READ-BEFORE-SET"]
    assert "Reader" in plan.blocks[0].explanation
    assert plan.blocks[0].where is not None
    assert maprefac.apply(plan, state=PrimeItems)[0] is False
    assert _snapshot() == before


def test_reading_the_value_in_the_action_that_sets_it_counts_as_before(loaded: None) -> None:
    """'%Hits + 1' reads the previous run's value; a local would always give 1."""
    plan = _plan(TO_LOCAL, "%Hits")

    assert _reasons(plan) == ["READ-BEFORE-SET"]
    assert "action 1" in plan.blocks[0].explanation


def test_a_name_the_task_already_owns_is_a_clash_not_a_merge(loaded: None) -> None:
    """Mixer has a %total of its own; making %Total local would fold the two together."""
    plan = _plan(TO_LOCAL, "%Total")

    assert _reasons(plan) == ["NAME-CLASH"]
    assert "Mixer" in plan.blocks[0].explanation


def test_a_global_a_scene_or_profile_reads_cannot_become_local(loaded: None) -> None:
    """A local exists only inside a running Task; the Scene and the Profile's condition could never see it."""
    plan = _plan(TO_LOCAL, "%Gate")

    assert _reasons(plan) == ["USED-OUTSIDE-A-TASK"]
    assert "Panel" in plan.blocks[0].explanation or "Watcher" in plan.blocks[0].explanation


def test_a_local_cannot_be_made_local_and_a_global_cannot_be_made_global(loaded: None) -> None:
    assert _reasons(_plan(TO_LOCAL, "%tally", "40")) == ["WRONG-SCOPE"]
    assert _reasons(_plan(TO_GLOBAL, "%Count")) == ["WRONG-SCOPE"]


def test_a_local_name_with_a_capital_is_not_a_local(loaded: None) -> None:
    """Asking for a local named %Mine is asking for something Tasker will read as global."""
    plan = _plan(TO_LOCAL, "%Solo", "", "%Mine")

    assert _reasons(plan) == ["SPELLING"]


def test_several_tasks_sharing_a_global_is_a_warning_when_they_all_set_it_first(loaded: None) -> None:
    """Two Tasks that each set before reading lose nothing but the sharing, which the preview says."""
    plan = _plan(TO_LOCAL, "%Pair")
    assert not plan.is_blocked, [block.explanation for block in plan.blocks]
    assert any("2 Tasks use %Pair" in warning for warning in plan.warnings)
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _texts("46")[0] == "%pair"
    assert _texts("47")[2] == "b has %pair"


# ##################################################################################
# Local to global.
# ##################################################################################


def test_a_local_becomes_a_global_in_its_own_task_only(loaded: None) -> None:
    """Stepper's %tally is promoted; Twin's, which has the same name, is a different variable and is not."""
    plan = _plan(TO_GLOBAL, "%tally", "40")
    assert not plan.is_blocked, [block.explanation for block in plan.blocks]
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert _texts("40")[3:] == ["%Tally", "1", "tally %Tally"]
    assert _texts("45") == ["%tally", "5", "twin %tally", "%steps", "1"]


def test_promoting_a_local_warns_that_it_is_now_shared(loaded: None) -> None:
    plan = _plan(TO_GLOBAL, "%tally", "40")

    assert any("ONE variable for the whole configuration" in warning for warning in plan.warnings)


def test_promoting_every_instance_says_how_many_variables_become_one(loaded: None) -> None:
    plan = _plan(TO_GLOBAL, "%tally", maprefac_variable.EVERY_INSTANCE)

    assert not plan.is_blocked
    assert any("2 separate variables" in warning for warning in plan.warnings)


def test_promoting_onto_an_existing_global_is_a_clash(loaded: None) -> None:
    """Mixer's local %total becoming %Total would join the global it already uses."""
    plan = _plan(TO_GLOBAL, "%total", "43", "%Total")

    assert _reasons(plan) == ["NAME-CLASH"]


# ##################################################################################
# The preview, the one undo, and what survives.
# ##################################################################################


def test_the_preview_lists_each_object_with_the_fields_it_touches(loaded: None) -> None:
    """One numbered line per Task, the changed fields indented under it, each a link to the action."""
    rows = maprefac.report_rows(_plan(RENAME, "%Count", "", "%Tally"))
    text = [row.text for row in rows]

    assert any("Stepper" in line and "2 places" in line for line in text)
    assert any(line.lstrip().startswith("action 2") and "%Count" in line and "%Tally" in line for line in text)
    assert any(row.target is not None and row.target.action == 2 for row in rows)


def test_a_blocked_preview_leads_with_the_reason(loaded: None) -> None:
    rows = maprefac.report_rows(_plan(TO_LOCAL, "%Count"))

    assert rows[2].text.startswith("CANNOT BE DONE")


def test_the_whole_change_is_one_undo(loaded: None) -> None:
    """A rename touching fields in two Tasks is one thing the user did."""
    plan = _plan(RENAME, "%Count", "", "%Tally")
    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert sessundo.next_undo_label(PrimeItems) == plan.what
    assert _texts("41") == ["see %Tally"]
    assert sessundo.undo(state=PrimeItems)[0] is True
    # Read back through the tables: undo restores them, and the root is not what the app renders from.
    assert _texts("41") == ["see %Count"]
    assert _texts("40")[:2] == ["%Count", "0"]
    assert not sessundo.can_undo(PrimeItems)


def test_the_whole_configuration_is_read_whatever_is_selected(loaded: None) -> None:
    """A global renamed in only the selected Task would be one variable spelled two ways."""
    PrimeItems.program_arguments.single_task_name = "Reader"
    try:
        plan = _plan(RENAME, "%Count", "", "%Tally")
        assert maprefac.apply(plan, state=PrimeItems) == (True, [])
    finally:
        PrimeItems.program_arguments.single_task_name = ""

    assert _texts("40")[0] == "%Tally"
    assert _texts("41") == ["see %Tally"]


def test_a_plan_whose_task_was_deleted_meanwhile_is_refused(loaded: None) -> None:
    """Writing to an element nobody renders from would silently do nothing, so apply says so."""
    plan = _plan(RENAME, "%Count", "", "%Tally")
    root = PrimeItems.xml_root
    root.remove(PrimeItems.tasker_root_elements["all_tasks"]["41"]["xml"])
    del PrimeItems.tasker_root_elements["all_tasks"]["41"]

    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done is False
    assert "no longer in the configuration" in errors[0]
