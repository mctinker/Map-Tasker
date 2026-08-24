"""MapTasker bulk-replace (mapswap) Unit Tests

Two halves, tested differently because they fail differently.

The classification half -- which arguments carry across a pair of action codes, and how
much of the old action survives -- is a pure function of actionc.py and arg_specs.json, so
it is tested against the real tables rather than a fixture.  A fixture would prove only
that the rule was implemented, not that it produces the right answer for Flash and Notify,
which is the whole question.

The rewriting half is tested against a small XML fixture, the same arrangement
test_mapfind.py and test_healthck.py use.  What it asserts is mostly about what SURVIVES:
a swap that produces the right code and loses the label, the disabled state or the value
the user typed is a swap that quietly damaged the configuration.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import mapfind, mapjump, mapswap, taskerd, varxref
from maptasker.src.mapjump import PROFILE, SCENE, TASK
from maptasker.src.primitem import PrimeItems

# Codes used below, named so the tests read as prose.
FLASH = "548t"  # 16 arguments; Text=arg0, Title=arg3
NOTIFY = "523t"  # 16 arguments; Title=arg0, Text=arg1, Icon(<Img>)=arg2
LAUNCH_APP = "20t"  # App=arg0, named 'Package/App Name'
KILL_APP = "18t"  # App=arg0, named 'App'
IF_ACTION = "37t"
SYSTEM_LOCK = "16t"  # no arguments at all -- 64 actions have none

#   Task 20 'Noisy'   two Flashes: act0 carries a label, a disabled flag and a Timeout
#                     that Notify has no home for; act1 is bare.
#   Task 21 'Opener'  a Launch App with a filled <App> subtree -- the picker carry.
#   Task 22 'Quiet'   a Say, so that a swap of Flash never touches it.
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <tids>20,21,22</tids>
  </Project>
  <Task sr="task20" ve="2">
    <id>20</id>
    <nme>Noisy</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <label>flash the total</label>
      <on>false</on>
      <se>false</se>
      <Str sr="arg0" ve="3">Done: %n</Str>
      <Str sr="arg3" ve="3">Report</Str>
      <Str sr="arg8" ve="3">30</Str>
      <Int sr="arg1" val="1"/>
    </Action>
    <Action sr="act1" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">bare</Str>
    </Action>
  </Task>
  <Task sr="task21" ve="2">
    <id>21</id>
    <nme>Opener</nme>
    <Action sr="act0" ve="7">
      <code>20</code>
      <App sr="arg0"><appClass>com.spotify.Main</appClass><appPkg>com.spotify</appPkg><label>Spotify</label></App>
      <Str sr="arg1" ve="3"/>
    </Action>
  </Task>
  <Task sr="task22" ve="2">
    <id>22</id>
    <nme>Quiet</nme>
    <Action sr="act0" ve="7">
      <code>559</code>
      <Str sr="arg0" ve="3">hello</Str>
    </Action>
  </Task>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file.

    Includes tasker_arg_specs, which mapfind and healthck never need and every one of
    these tests does: it is the table that says arg_type '2' means an App, and without it
    every argument reads as an unknown category and nothing carries anywhere.
    """
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
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
    """The fixture configuration, in the tables mapswap reads."""
    _load(_FIXTURE_XML)


def _action(task_id: str, position: int) -> ET.Element:
    """One action element of the fixture, in document order."""
    return PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"].findall("Action")[position]


def _args(action_element: ET.Element) -> dict[str, ET.Element]:
    """{'arg0': element} for one action."""
    return {child.attrib["sr"]: child for child in action_element if child.attrib.get("sr", "").startswith("arg")}


# ##################################################################################
# Which arguments carry, and what that makes the pair worth.
# ##################################################################################
def test_matching_name_and_type_carries(loaded: None) -> None:
    """Flash's Text and Title reach Notify's, which are at different argument numbers."""
    carry = mapswap.carry_over_map(FLASH, NOTIFY)
    assert carry == {"0": "1", "3": "0"}


def test_matching_name_with_a_different_type_does_not_carry(loaded: None) -> None:
    """Flash's 'Icon' is a String naming one; Notify's is an <Img> subtree.

    The case the type half of the rule exists for -- the names are identical, and copying
    one into the other would produce an <Img> holding text.
    """
    carry = mapswap.carry_over_map(FLASH, NOTIFY)
    assert "4" not in carry  # Flash's Icon
    assert "2" not in carry.values()  # Notify's Icon


def test_a_unique_picker_carries_despite_a_different_name(loaded: None) -> None:
    """'Package/App Name' -> 'App': rule 1 refuses it, uniqueness allows it.

    Without this the user would re-pick an app by hand in every Task the swap touched.
    """
    assert mapswap.carry_over_map(LAUNCH_APP, KILL_APP) == {"0": "0"}
    assert mapswap.carry_over_map(KILL_APP, LAUNCH_APP) == {"0": "0"}


def test_fidelity_reports_what_the_user_loses_not_what_the_target_gains(loaded: None) -> None:
    """A target with no arguments is not EXACT just because it has nothing left unfilled.

    67 actions have no arguments at all, so testing only the target would call
    'Flash -> Airplane Mode' exact -- promising the user their message text survived into
    an action that cannot hold it.
    """
    fidelity, carry, _ = mapswap.classify_swap(FLASH, SYSTEM_LOCK)
    assert not mapswap._wanted_args(SYSTEM_LOCK)  # the target has nothing to fill
    assert not carry
    assert fidelity == mapswap.RESET

    # ...and a pair with nothing on EITHER side really is exact: nothing was lost.
    assert mapswap.classify_swap(SYSTEM_LOCK, "139t")[0] == mapswap.EXACT


def test_flash_to_notify_is_mapped(loaded: None) -> None:
    """The headline pair, and the reason the swap does not defer to taskedit's addability
    test: Notify needs an <Img>, which Add Action cannot generate and a swap can leave empty.
    """
    fidelity, _, reason = mapswap.classify_swap(FLASH, NOTIFY)
    assert fidelity == mapswap.MAPPED
    assert not reason


def test_structural_actions_are_blocked_both_ways(loaded: None) -> None:
    """Swapping an If leaves its End If dangling; nothing here reasons about nesting."""
    assert mapswap.classify_swap(FLASH, IF_ACTION)[0] == mapswap.BLOCKED
    assert mapswap.classify_swap(IF_ACTION, FLASH)[0] == mapswap.BLOCKED


def test_the_target_pulldown_offers_every_level_and_hides_nothing(loaded: None) -> None:
    """All four fidelities appear, blocked entries included, and the ones that carry the
    most sit at the top of the list.
    """
    choices = mapswap.fidelity_choices(FLASH)
    levels = {fidelity for _, _, fidelity in choices}
    assert mapswap.MAPPED in levels
    assert mapswap.RESET in levels
    assert mapswap.BLOCKED in levels
    assert FLASH not in {key for key, _, _ in choices}  # replacing an action with itself

    ranks = [{mapswap.EXACT: 0, mapswap.MAPPED: 1, mapswap.RESET: 2, mapswap.BLOCKED: 3}[f] for _, _, f in choices]
    assert ranks == sorted(ranks)
    blocked_labels = [label for _, label, fidelity in choices if fidelity == mapswap.BLOCKED]
    assert blocked_labels
    assert all("cannot" in label for label in blocked_labels)


# ##################################################################################
# Rewriting one action.
# ##################################################################################
def test_swap_preserves_everything_that_does_not_belong_to_the_code(loaded: None) -> None:
    """Label, disabled state and continue-after-error survive, along with the sr position.

    All four are the user's intent about WHERE and WHEN the action runs, which a swap does
    not change -- and losing the <on>false</on> would silently re-enable an action the user
    had turned off.
    """
    action_element = _action("20", 0)
    _, carry, _ = mapswap.classify_swap(FLASH, NOTIFY)
    mapswap._swap_one_action(action_element, NOTIFY, carry)

    assert action_element.attrib["sr"] == "act0"
    assert action_element.findtext("code") == "523"
    assert action_element.findtext("label") == "flash the total"
    assert action_element.findtext("on") == "false"
    assert action_element.findtext("se") == "false"


def test_swap_carries_the_values_and_drops_the_rest(loaded: None) -> None:
    """Text and Title land in Notify's own numbering; the Timeout has nowhere to go."""
    action_element = _action("20", 0)
    _, carry, _ = mapswap.classify_swap(FLASH, NOTIFY)
    mapswap._swap_one_action(action_element, NOTIFY, carry)

    arguments = _args(action_element)
    assert arguments["arg1"].text == "Done: %n"  # Flash arg0 Text -> Notify arg1 Text
    assert arguments["arg0"].text == "Report"  # Flash arg3 Title -> Notify arg0 Title
    assert (arguments["arg8"].text or "") == ""  # Flash's Timeout is not Notify's arg8


def test_swap_writes_the_empty_picker_tasker_writes_itself(loaded: None) -> None:
    """Notify's <Img> is present and empty rather than missing.

    build_synthesized_args cannot write one -- _build_default_arg returns None for every
    picker category -- and an action missing an argument Tasker expects is the shape that
    reaches the device and misbehaves there.  The empty element is not an invention: it is
    what Tasker writes for an unset picker, in hundreds of places in real backups.
    """
    action_element = _action("20", 1)
    _, carry, _ = mapswap.classify_swap(FLASH, NOTIFY)
    mapswap._swap_one_action(action_element, NOTIFY, carry)

    icon = _args(action_element)["arg2"]
    assert icon.tag == "Img"
    assert len(icon) == 0
    assert not (icon.text or "").strip()


def test_swap_moves_a_picker_subtree_whole(loaded: None) -> None:
    """The <App>'s children come across, not just its text -- which it has none of."""
    action_element = _action("21", 0)
    _, carry, _ = mapswap.classify_swap(LAUNCH_APP, KILL_APP)
    mapswap._swap_one_action(action_element, KILL_APP, carry)

    app = _args(action_element)["arg0"]
    assert app.tag == "App"
    assert app.findtext("appPkg") == "com.spotify"
    assert app.findtext("label") == "Spotify"


def test_swap_leaves_the_arguments_in_the_order_tasker_writes_them(loaded: None) -> None:
    """arg0, arg1, arg10 ... arg2 -- sorted as strings, which is what a backup looks like.

    Nothing reads them this way; every reader matches on 'sr'.  This is for the diff: an
    action rebuilt in a different order is a hundred moved lines of noise in xmldiff and in
    whatever version control the user keeps their backups in.
    """
    action_element = _action("20", 0)
    _, carry, _ = mapswap.classify_swap(FLASH, NOTIFY)
    mapswap._swap_one_action(action_element, NOTIFY, carry)

    order = [child.attrib["sr"] for child in action_element if child.attrib.get("sr", "").startswith("arg")]
    assert order == sorted(order)
    assert order[:3] == ["arg0", "arg1", "arg10"]


# ##################################################################################
# Planning over the whole configuration.
# ##################################################################################
def test_plan_finds_every_instance_and_only_that_action(loaded: None) -> None:
    """Both Flashes, and not the Say sitting beside them."""
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    assert len(plan.changes) == 2
    assert all(change.site.where.kind == TASK for change in plan.changes)
    assert {change.site.where.name for change in plan.changes} == {"Noisy"}


def test_plan_notes_what_each_action_loses_rather_than_what_the_pair_loses(loaded: None) -> None:
    """The labelled Flash sets a Timeout and loses it; the bare one loses nothing.

    A note naming an argument nobody filled in is the kind of warning that teaches users to
    skim past warnings.
    """
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    notes = {change.site.where.action: change.note for change in plan.changes}
    assert "Timeout" in notes[1]
    assert notes[2] == ""


def test_reset_rows_start_unticked(loaded: None) -> None:
    """Offering RESET and defaulting it to on are different decisions.

    RESET discards every argument value in every action it touches, so a user who ticked
    the header box without reading to the bottom would not find out until much later.
    """
    plan = mapswap.plan_action_swap(FLASH, LAUNCH_APP)
    assert plan.changes
    assert plan.selected == set()
    assert "None are ticked" in " ".join(plan.warnings)


def test_mapped_rows_start_ticked(loaded: None) -> None:
    """What the preview shows, it shows as selected -- there is nothing hidden to lose."""
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    assert plan.selected == set(range(len(plan.changes)))


def test_a_blocked_pair_plans_nothing_and_says_why(loaded: None) -> None:
    """Not an empty answer -- an explained one."""
    plan = mapswap.plan_action_swap(FLASH, IF_ACTION)
    assert not plan.changes
    assert plan.warnings
    assert "cannot be the target" in plan.warnings[0]


def test_a_stale_label_is_warned_about_not_rewritten(loaded: None) -> None:
    """'flash the total' on a Notify is stale prose, and this tool does not rewrite prose."""
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    assert any("label" in warning for warning in plan.warnings)


def test_project_narrowing_excludes_everything_outside_it(loaded: None) -> None:
    """A Project that owns none of them answers with none of them."""
    assert mapswap.plan_action_swap(FLASH, NOTIFY, project="Home").changes
    assert not mapswap.plan_action_swap(FLASH, NOTIFY, project="Nowhere").changes


# ##################################################################################
# Applying.
# ##################################################################################
def test_apply_changes_only_the_ticked_rows(loaded: None) -> None:
    """The tick boxes are the contract; an unticked row is untouched."""
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    plan.selected = {0}
    changed, errors = mapswap.apply(plan)

    assert (changed, errors) == (1, [])
    codes = [_action("20", position).findtext("code") for position in (0, 1)]
    assert sorted(codes) == ["523", "548"]


def test_apply_refuses_an_element_no_longer_in_the_configuration(loaded: None) -> None:
    """The preview can sit on screen while the user edits a Task in another dialog.

    An element deleted underneath a plan must not be resurrected by writing to it -- and
    the check is by identity, since a Task deleted and another added in its place would
    match by every describable property and be a different object.
    """
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    task = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"]
    task.remove(plan.changes[0].site.element)

    changed, errors = mapswap.apply(plan)
    assert changed == 1
    assert len(errors) == 1
    assert "no longer in the configuration" in errors[0]


# ##################################################################################
# Renaming a variable.
#
# A separate fixture, because what a rename has to get right is the SPREAD of places a
# variable can hide in -- an argument, a numeric argument a variable is bound to, an
# action's own condition, a plugin's Bundle, a Profile context, a Legacy Scene binding,
# and the declaration in Tasker's Variables tab.  Miss one and the configuration is left
# half-renamed, which is worse than not offering the feature.
# ##################################################################################

#   %Total       a global, used in every shape the scan can reach
#   %Totals      the prefix trap: it must survive a rename of %Total untouched
#   %counter     an all-lower-case local, used in TWO Tasks that must not be merged
_RENAME_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="var0"><n>%Total</n><v>7</v></Variable>
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>10</pids>
    <tids>30,31</tids>
    <scenes>Panel</scenes>
  </Project>
  <Profile sr="prof10" ve="2">
    <id>10</id>
    <nme>Watcher</nme>
    <mid0>30</mid0>
    <State sr="con0" ve="2">
      <code>160</code>
      <Str sr="arg0" ve="3">%Total is high</Str>
    </State>
  </Profile>
  <Task sr="task30" ve="2">
    <id>30</id>
    <nme>Adder</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Total</Str>
      <Str sr="arg1" ve="3">%Total plus %Totals and %counter</Str>
      <Condition sr="if0"><lhs>%Total</lhs><op>2</op><rhs>%Totals</rhs></Condition>
    </Action>
    <Action sr="act1" ve="7">
      <code>30</code>
      <Int sr="arg0"><var>%Total</var></Int>
    </Action>
    <Action sr="act2" ve="7">
      <code>1000</code>
      <Bundle sr="arg0"><Vals sr="val"><com.example.MESSAGE>sum is %Total</com.example.MESSAGE></Vals></Bundle>
    </Action>
  </Task>
  <Task sr="task31" ve="2">
    <id>31</id>
    <nme>Other</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%counter</Str>
      <Str sr="arg1" ve="3">1</Str>
    </Action>
  </Task>
  <Scene sr="scenePanel">
    <nme>Panel</nme>
    <EditTextElement sr="elt0">
      <geom sr="geom"><h>50</h></geom>
      <Str sr="arg0" ve="3">Entry</Str>
      <Str sr="arg1" ve="3">%Total</Str>
    </EditTextElement>
  </Scene>
</TaskerData>
"""


@pytest.fixture
def variables() -> "varxref.VariableIndex":
    """The variable cross-reference for the rename fixture."""
    _load(_RENAME_XML)
    return varxref.build_index()


def _values(plan: mapswap.Plan) -> list[str]:
    """What each planned change would leave behind."""
    return [change.after for change in plan.changes]


def test_rename_reaches_every_shape_a_variable_hides_in(variables) -> None:
    """An argument, a bound numeric, a condition side, a Bundle, a Profile context, a
    Legacy Scene binding and the declaration -- all of them, in one plan.

    The list is the point.  A rename that reaches six of the seven leaves a configuration
    that is half-renamed, which is worse than one this tool declined to touch.
    """
    plan = mapswap.plan_variable_rename(variables, "%Total", "", "%Sum")
    kinds = {change.site.kind for change in plan.changes}
    assert mapswap.STR_ARG in kinds
    assert mapswap.INT_VAR in kinds
    assert mapswap.CONDITION in kinds
    assert mapswap.BUNDLE in kinds
    assert mapswap.DECLARATION in kinds
    # ...and the two that are not Task actions at all: the Profile context that tests it
    # and the Scene field bound to it.
    assert {change.site.where.kind for change in plan.changes} >= {TASK, PROFILE, SCENE}
    assert all("%Sum" in after for after in _values(plan))


def test_rename_leaves_a_longer_name_that_merely_starts_the_same(variables) -> None:
    """%Totals is not %Total, and str.replace cannot tell them apart.

    Not a theoretical worry: the sample backup has 2483 pairs where one variable's name
    is a prefix of another's.
    """
    plan = mapswap.plan_variable_rename(variables, "%Total", "", "%Sum")
    rewritten = " ".join(_values(plan))
    assert "%Totals" in rewritten
    assert "%Sums" not in rewritten


def test_rename_keeps_a_subscript_or_member_suffix(variables) -> None:
    """'%Total(3)' and '%Total.length' name %Total and keep what follows them."""
    pattern = mapswap._rename_pattern("%Total")
    assert pattern.sub("%Sum", "%Total(%i) and %Total.length") == "%Sum(%i) and %Sum.length"


def test_renaming_a_local_stays_inside_its_own_task(variables) -> None:
    """The single most important thing on this side.

    Tasker scopes an all-lower-case name to the running Task, so two Tasks using %counter
    have two variables.  Renaming file-wide would rewrite hundreds of unrelated loop
    counters in a real configuration -- 525 of 1523 local names appear in more than one
    Task there.
    """
    plan = mapswap.plan_variable_rename(variables, "%counter", "30", "%tally")
    assert plan.changes
    assert {change.site.where.key for change in plan.changes} == {"30"}


def test_a_case_change_is_reported_as_the_scope_change_it_is(variables) -> None:
    """'%counter' -> '%Counter' promotes a per-Task local into one shared global.

    A real thing to want, and never a thing to do by accident, so it warns and proceeds.
    """
    plan = mapswap.plan_variable_rename(variables, "%counter", "30", "%Counter")
    assert any("SCOPE" in warning for warning in plan.warnings)
    assert plan.changes  # warned, not refused


def test_renaming_onto_an_existing_name_is_reported_as_a_merge(variables) -> None:
    """Two variables becoming one is not what 'rename' sounds like, so it says so."""
    plan = mapswap.plan_variable_rename(variables, "%Total", "", "%Totals")
    assert any("MERGE" in warning for warning in plan.warnings)


@pytest.mark.parametrize(
    ("old_name", "new_name", "because"),
    [
        ("%Total", "%9bad", "not a name Tasker would accept"),
        ("%Total", "%d", "too short"),
        ("%BATT", "%Battery", "built-in"),
        ("%Total", "%TIME", "built-in"),
        ("%Total", "%Total", "the same"),
    ],
)
def test_unsafe_renames_are_refused_not_warned_about(variables, old_name, new_name, because) -> None:
    """Each of these produces a configuration wrong in a way no reading of the Map shows.

    The short-name case is the one worth keeping: '%d' matches a strftime format inside a
    Parse/Format DateTime and a printf escape inside a Run Shell.
    """
    plan = mapswap.plan_variable_rename(variables, old_name, "", new_name)
    assert not plan.changes
    assert plan.warnings
    assert because in plan.warnings[0]


def test_apply_rewrites_the_configuration_itself(variables) -> None:
    """End to end: plan, apply, and re-scan to confirm the old name is gone."""
    plan = mapswap.plan_variable_rename(variables, "%Total", "", "%Sum")
    changed, errors = mapswap.apply(plan)
    assert errors == []
    assert changed == len(plan.changes)

    rescanned = varxref.build_index()
    assert ("%Total", "") not in rescanned.variables
    assert ("%Sum", "") in rescanned.variables
    # ...and the prefix neighbour is still there, with its own uses intact.
    assert ("%Totals", "") in rescanned.variables


def test_apply_moves_the_declaration_too(variables) -> None:
    """Leaving it behind orphans the value in Tasker's Variables tab under a dead name."""
    plan = mapswap.plan_variable_rename(variables, "%Total", "", "%Sum")
    mapswap.apply(plan)

    declared = [list(element)[0].text for element in PrimeItems.xml_root.findall("Variable")]
    assert "%Sum" in declared
    assert "%Total" not in declared


def test_a_plugins_declaration_of_its_outputs_is_skipped_not_rewritten(variables) -> None:
    """A RELEVANT_VARIABLES entry describes what the plugin produces.

    Rewriting it would edit the plugin's description of itself and change nothing about
    what it actually sets -- 4313 of these sit in one real backup, so this is not an edge.
    """
    element = ET.fromstring(  # noqa: S314
        '<net.dinglisch.android.tasker.RELEVANT_VARIABLES>x</net.dinglisch.android.tasker.RELEVANT_VARIABLES>',
    )
    assert mapswap._is_plugin_declaration(element)
    assert not mapswap._is_plugin_declaration(ET.fromstring('<Str sr="arg0">x</Str>'))  # noqa: S314


# ##################################################################################
# Scope: Find and Replace reach only what the app is displaying.
#
# The app has a "display only this one" selector.  With it set, the Map on screen is one
# object, and a Replace that changed the other 82 Projects would be changing things the
# user cannot see -- so the scope is applied when the INDEX is built, not when a query is
# answered, which is what keeps the pulldown counts and the results agreeing.
# ##################################################################################


@pytest.fixture
def _no_selection() -> None:
    """Clear the single-item selectors before and after each scope test.

    They live on PrimeItems.program_arguments, which is global and survives between
    tests: one test leaving 'single_task_name' set would silently scope every test after
    it, and they would fail somewhere else entirely.
    """
    keys = ("single_project_name", "single_profile_name", "single_task_name", "single_scene_name")
    for key in keys:
        PrimeItems.program_arguments[key] = ""
    yield
    for key in keys:
        PrimeItems.program_arguments[key] = ""


def test_no_selection_reaches_the_whole_configuration(loaded, _no_selection) -> None:
    """The default, and the thing every other test in this file relies on."""
    assert mapjump.current_scope().is_everything
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    assert len(plan.changes) == 2  # both Flashes, in the one Task that has them


def test_a_selected_task_scopes_the_swap_to_itself(loaded, _no_selection) -> None:
    """Selecting the Task that has no Flash leaves nothing for a Flash swap to do."""
    PrimeItems.program_arguments["single_task_name"] = "Quiet"
    scope = mapjump.current_scope()
    assert not scope.is_everything
    assert scope.phrase == "Task 'Quiet'"

    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    assert not plan.changes
    assert any("Limited to Task 'Quiet'" in warning for warning in plan.warnings)


def test_a_selected_task_still_finds_what_is_inside_it(loaded, _no_selection) -> None:
    """...and selecting the Task that does have them finds exactly those."""
    PrimeItems.program_arguments["single_task_name"] = "Noisy"
    plan = mapswap.plan_action_swap(FLASH, NOTIFY)
    assert len(plan.changes) == 2
    assert {change.site.where.name for change in plan.changes} == {"Noisy"}


def test_the_pulldown_counts_agree_with_the_scoped_answer(loaded, _no_selection) -> None:
    """The reason scoping happens at index time rather than at query time.

    A pulldown offering 'Flash (2)' over a scope that would only change one is the
    disagreement mapfind's own design notes exist to prevent.
    """
    PrimeItems.program_arguments["single_task_name"] = "Noisy"
    index = mapfind.build_index()
    offered = dict(index.catalog[mapfind.ACTION]).get("Flash", 0)
    assert offered == len(mapswap.plan_action_swap(FLASH, NOTIFY).changes)


def test_a_selected_project_pulls_in_what_it_contains(variables, _no_selection) -> None:
    """A Project's scope is its Profiles, Tasks and Scenes, not just its own name."""
    PrimeItems.program_arguments["single_project_name"] = "Home"
    scope = mapjump.current_scope()
    assert scope.projects == frozenset({"Home"})
    assert scope.profiles == frozenset({"10"})
    assert scope.tasks == frozenset({"30", "31"})
    assert scope.scenes == frozenset({"Panel"})


def test_a_selection_that_names_nothing_scopes_to_nothing(loaded, _no_selection) -> None:
    """Fails closed.

    Falling back to "everything" when the named object is missing would silently widen a
    Replace from one Task to the whole configuration -- the one direction this must never
    fail in.
    """
    PrimeItems.program_arguments["single_project_name"] = "No Such Project"
    scope = mapjump.current_scope()
    assert not scope.is_everything
    assert scope.tasks == frozenset()
    assert not mapswap.plan_action_swap(FLASH, NOTIFY).changes


def test_a_rename_is_confined_to_the_selected_object(variables, _no_selection) -> None:
    """%Total is used in a Task, a Profile context and a Scene; selecting the Task drops
    the other two out of the plan entirely.
    """
    everywhere = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum")
    assert {change.site.where.kind for change in everywhere.changes} >= {TASK, PROFILE, SCENE}

    PrimeItems.program_arguments["single_task_name"] = "Adder"
    scoped = mapswap.plan_variable_rename(varxref.build_index(mapjump.current_scope()), "%Total", "", "%Sum")
    assert {change.site.where.kind for change in scoped.changes} == {TASK}
    assert {change.site.where.key for change in scoped.changes} == {"30"}
    assert 0 < len(scoped.changes) < len(everywhere.changes)


def test_a_scoped_rename_leaves_the_variables_tab_declaration_alone(variables, _no_selection) -> None:
    """A <Variable> is file-level, so it is not inside the one object that was selected.

    Renaming it from inside a single Task would rename Tasker's Variables tab entry out
    from under every other Task still using the old name.
    """
    assert any(change.site.kind == mapswap.DECLARATION for change in
               mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum").changes)

    PrimeItems.program_arguments["single_task_name"] = "Adder"
    scoped = mapswap.plan_variable_rename(varxref.build_index(mapjump.current_scope()), "%Total", "", "%Sum")
    assert not any(change.site.kind == mapswap.DECLARATION for change in scoped.changes)


def test_a_scoped_rename_warns_that_it_leaves_the_rest_alone(variables, _no_selection) -> None:
    """A half-renamed global is a broken configuration, not a partly-done job."""
    PrimeItems.program_arguments["single_task_name"] = "Adder"
    plan = mapswap.plan_variable_rename(varxref.build_index(mapjump.current_scope()), "%Total", "", "%Sum")
    assert any("keep the old name" in warning for warning in plan.warnings)


def test_the_scope_reaches_the_saved_reports(loaded, _no_selection) -> None:
    """An empty answer has to say it was scoped, or it reads as "there are none"."""
    PrimeItems.program_arguments["single_task_name"] = "Quiet"
    rows = mapfind.report_rows(mapfind.Query(action="Flash"), [], 0, mapfind.build_index())
    assert any("Limited to Task 'Quiet'" in row.text for row in rows)


def test_varxref_is_whole_file_unless_a_scope_is_asked_for(loaded, _no_selection) -> None:
    """The default that keeps the health check honest.

    healthck folds varxref.suspects() into its own whole-configuration report, and
    "read but never set" is decided by not having seen a setter -- so an index that
    silently narrowed to the displayed object would turn nearly every global in the file
    into a false alarm there.  Only the rename asks for a scope, because only the rename
    writes.
    """
    PrimeItems.program_arguments["single_task_name"] = "Quiet"

    assert varxref.build_index().scope.is_everything
    assert not varxref.build_index(mapjump.current_scope()).scope.is_everything


def test_replacing_a_variable_with_an_existing_one_merges_and_says_so(variables, _no_selection) -> None:
    """Consolidating two variables into one is a supported operation, not an accident.

    "Everywhere this Task says %Total, say %Totals" is a real thing to want inside a
    single object, and it is what the target pulldown offers.  What the user is told is
    the consequence, since it is not what the word "rename" suggests.
    """
    plan = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Totals")
    assert plan.changes
    merge = [warning for warning in plan.warnings if "MERGES" in warning]
    assert merge
    assert "already exists" in merge[0]
    assert all("%Totals" in change.after for change in plan.changes)


def test_a_scoped_substitution_changes_only_the_selected_object(variables, _no_selection) -> None:
    """The two halves of this feature together: every occurrence inside the object, and
    nothing outside it.
    """
    PrimeItems.program_arguments["single_task_name"] = "Adder"
    plan = mapswap.plan_variable_rename(varxref.build_index(mapjump.current_scope()), "%Total", "", "%Totals")
    changed, errors = mapswap.apply(plan)
    assert errors == []
    assert changed == len(plan.changes)

    # Inside: no USES of %Total left in the Task that was selected.  The entry itself
    # survives with no references, because the top-level <Variable> declaring it is
    # scanned whatever the scope -- which is deliberate and load-bearing: declared_names
    # is what tells varxref that a lower-case declared name is a global rather than some
    # Task's local, and a scoped-out declaration would misfile it.
    inside = varxref.build_index(mapjump.current_scope())
    survivor = inside.variables[("%Total", "")]
    assert survivor.sets == []
    assert survivor.reads == []
    assert survivor.declared

    # Outside: the Profile context and the Scene binding still name it, untouched.
    PrimeItems.program_arguments["single_task_name"] = ""
    whole = varxref.build_index()
    remaining = whole.variables[("%Total", "")]
    assert {reference.target.kind for reference in remaining.sets + remaining.reads} == {PROFILE, SCENE}


# ##################################################################################
# Carrying tick boxes across a rebuild.
#
# Clicking a preview row closes the dialog to get out of the jump's way, which throws the
# plan away -- a Site holds a live element and cannot outlive the dialog.  So the way back
# rebuilds the plan from the remembered inputs, and the user's tick boxes have to be put
# back onto a list that was built from scratch.
# ##################################################################################


def test_ticks_are_carried_by_what_they_point_at_not_by_position(variables) -> None:
    """The whole reason Change.identity exists.

    An edit made in another dialog between the two previews shifts every index after it.
    Ticks restored by position would then select different changes from the ones the user
    chose -- silently, and in a plan that is about to be applied.
    """
    plan = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum")
    assert len(plan.changes) > 2

    plan.selected = {0, 2}
    remembered = plan.ticked_identities()
    wanted = {plan.changes[0].identity, plan.changes[2].identity}

    # Rebuild, with the list deliberately reordered to stand in for a tree that moved.
    rebuilt = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum")
    rebuilt.changes.reverse()
    rebuilt.restore_ticks(remembered)

    assert {rebuilt.changes[position].identity for position in rebuilt.selected} == wanted


def test_restoring_ticks_overrides_the_defaults_in_both_directions(variables) -> None:
    """A row the user unticked comes back unticked, and one they ticked comes back ticked.

    Merging with the defaults instead would un-tick the RESET rows a user had gone through
    and enabled one at a time -- the exact work this is meant to preserve.
    """
    plan = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum")
    plan.selected = {1}
    remembered = plan.ticked_identities()

    rebuilt = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum")
    assert rebuilt.selected == set(range(len(rebuilt.changes)))  # all ticked by default
    rebuilt.restore_ticks(remembered)

    assert len(rebuilt.selected) == 1
    assert next(iter(rebuilt.selected)) == 1


def test_indistinguishable_changes_are_restored_by_count(variables) -> None:
    """Two rows that read identically are also indistinguishable to the user.

    So "two of these were ticked" is the whole of what they chose, and a Counter restores
    it exactly -- where a set would collapse the pair and lose one of the ticks.
    """
    plan = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum")
    duplicated = mapswap.Change(
        site=plan.changes[0].site,
        before=plan.changes[0].before,
        after=plan.changes[0].after,
    )
    plan.changes.append(duplicated)
    assert duplicated.identity == plan.changes[0].identity

    plan.selected = {0, len(plan.changes) - 1}
    rebuilt_ticks = plan.ticked_identities()
    assert rebuilt_ticks[duplicated.identity] == 2

    plan.restore_ticks(rebuilt_ticks)
    assert len(plan.selected) == 2


def test_ticks_from_a_different_question_do_not_leak_across(variables) -> None:
    """Identities name the object, the field and the value, so a plan for another
    variable cannot match them and comes back at its own defaults.
    """
    counter = mapswap.plan_variable_rename(varxref.build_index(), "%Total", "", "%Sum")
    counter.selected = {0}
    remembered = counter.ticked_identities()

    other = mapswap.plan_variable_rename(varxref.build_index(), "%counter", "30", "%tally")
    other.restore_ticks(remembered)
    assert other.selected == set()
