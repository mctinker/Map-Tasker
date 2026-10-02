"""MapTasker restore-from-history (maprestore) Unit Tests

What these assert is what a restore LEAVES BEHIND in the configuration that is open now, and
what it declines to touch.

A restore is easy to get visibly right and invisibly wrong in exactly the ways Duplicate is:
a Task brought back on an id something else now holds overwrites that something else in
all_tasks; a Task brought back under a name another Task has leaves every Perform Task
ambiguous; a Profile brought back pointing at an old id runs whatever holds that id today.
So each happy path checks the surroundings -- the id, the name, the Project, the by-name
table -- and not only that the object is there.

The other half is ONE OBJECT AT A TIME.  Every test that restores something also checks
that the objects next to it were left exactly as they were: the Profile that ran a restored
Task is not relinked, and nothing about a restore turns it into a merge.

Two configurations, not one: the snapshot (the older side, as timeline would hand it over)
and the configuration open now.  The snapshot is parsed with a different Element class
from the live one on purpose -- that is what diffload's second parse can hand back, and an
element of the wrong class appended into the live tree is a failure no single-parse test
would ever see.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.initparg import ProgramArguments
from maptasker.src import maprefac, maprestore, sessundo, taskerd, xmldiff
from maptasker.src.mapjump import actions_in_map_order
from maptasker.src.primitem import PrimeItems

FLASH = "548"
PERFORM_TASK = "130"
FROM_WHEN = "backup.xml, 15-Sep-2026 14:29:18"

# The configuration as it stood, in the history.
#
#   Project Home (id p-home)   Profiles Dawn, Dusk.  Tasks Morning, Helper, Evening, Old Name.
#                              Scene Panel.
#   Project Gone (id p-gone)   Task Orphaned.  Deleted since, with its Task.
#
#   Profile 101 'Dusk' runs Task 22 'Evening' -- both deleted since, which is the pair the
#   link resolution is about.
_OLDER_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="v0"><n>%Global</n><v>1</v></Variable>
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <id>p-home</id>
    <pids>100,101</pids>
    <tids>20,21,22,23</tids>
    <scenes>Panel</scenes>
  </Project>
  <Project sr="proj1" ve="2">
    <name>Gone</name>
    <id>p-gone</id>
    <tids>24</tids>
  </Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Dawn</nme><mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Profile sr="prof101" ve="2"><id>101</id><nme>Dusk</nme><mid0>22</mid0>
    <Time sr="con0"><fh>18</fh><fm>0</fm><th>19</th><tm>0</tm></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action>
    <Action sr="act1" ve="7"><code>548</code><Str sr="arg0" ve="3">world</Str></Action>
  </Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Helper</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">helping</Str></Action>
  </Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Evening</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">night</Str></Action>
  </Task>
  <Task sr="task23" ve="2"><id>23</id><nme>Old Name</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">original</Str></Action>
  </Task>
  <Task sr="task24" ve="2"><id>24</id><nme>Orphaned</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">alone</Str></Action>
  </Task>
  <Scene sr="scenePanel"><nme>Panel</nme><widthPort>100</widthPort></Scene>
</TaskerData>
"""

# The configuration open now.
#
#   Task 20 'Morning' edited: one Flash gone, a Perform Task 'Helper' added -- so bringing
#   Helper back is bringing back something a call is still waiting for.
#   Task 23 renamed to 'New Name' AND edited -- two xmldiff entries, one revert.
#   Task 30 added, the %Global value changed, Project Gone deleted -- all three differences
#   the list must decline to offer, and count.
_NEWER_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="v0"><n>%Global</n><v>2</v></Variable>
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <id>p-home</id>
    <pids>100</pids>
    <tids>20,23,30</tids>
  </Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Dawn</nme><mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action>
    <Action sr="act1" ve="7"><code>130</code><Str sr="arg0" ve="3">Helper</Str></Action>
  </Task>
  <Task sr="task23" ve="2"><id>23</id><nme>New Name</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">original</Str></Action>
    <Action sr="act1" ve="7"><code>548</code><Str sr="arg0" ve="3">added later</Str></Action>
  </Task>
  <Task sr="task30" ve="2"><id>30</id><nme>Added</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">new</Str></Action>
  </Task>
</TaskerData>
"""


class _SnapshotElement(ET.Element):
    """The snapshot's own Element class -- deliberately not the live tree's."""


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


def _older() -> xmldiff.Configuration:
    """The snapshot, parsed with its own Element class, as a comparison side."""
    parser = ET.XMLParser(target=ET.TreeBuilder(element_factory=_SnapshotElement))  # noqa: S314  (fixture text)
    parser.feed(_OLDER_XML)
    root = parser.close()
    return xmldiff.Configuration(path="snapshot", tables=_tables(root), root=root)


def _newer() -> xmldiff.Configuration:
    """The configuration open now, as a comparison side."""
    return xmldiff.Configuration(path="now", tables=PrimeItems.tasker_root_elements, root=PrimeItems.xml_root)


@pytest.fixture
def loaded() -> None:
    """The newer configuration open, with an empty undo history."""
    sessundo.clear()
    root = ET.fromstring(_NEWER_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.xml_tree = ET.ElementTree(root)
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file) as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"
    PrimeItems.tasker_arg_specs = specs
    PrimeItems.tasker_root_elements = _tables(root)
    yield
    sessundo.clear()


# ##################################################################################
# Reading the configuration open now, the way the tests want to talk about it.
# ##################################################################################


def _live(table: str) -> dict:
    return PrimeItems.tasker_root_elements[table]


def _tids() -> list[str]:
    return [item for item in (_live("all_projects")["Home"]["xml"].findtext("tids") or "").split(",") if item]


def _candidate(kind: str, key: str) -> maprestore.Candidate:
    """The one candidate the list offers for this object."""
    matches = [c for c in maprestore.candidates(_older(), _newer(), state=PrimeItems).candidates if (c.kind, c.key) == (kind, key)]
    assert len(matches) == 1, f"expected one candidate for {kind} {key}, got {len(matches)}"
    return matches[0]


def _restore(kind: str, key: str, older: xmldiff.Configuration | None = None) -> maprefac.Plan:
    """Plan and apply the restore of one object; assert it went through; return the plan."""
    older = older or _older()
    plan = maprestore.plan_restore(_candidate(kind, key), older, FROM_WHEN, state=PrimeItems)
    assert plan.can_apply, [block.explanation for block in plan.blocks]
    done, errors = maprestore.restore(plan)
    assert (done, errors) == (True, [])
    return plan


def _add_task(task_id: str, name: str) -> None:
    """Put another Task into the configuration open now -- the thing a restore must not overwrite."""
    element = ET.fromstring(f'<Task sr="task{task_id}" ve="2"><id>{task_id}</id><nme>{name}</nme></Task>')  # noqa: S314
    _live("all_tasks")[task_id] = {"xml": element, "name": name}
    _live("all_tasks_by_name")[name] = {"xml": element, "id": task_id}


# ##################################################################################
# What is offered.
# ##################################################################################


def test_every_removed_and_changed_object_is_offered_once(loaded: None) -> None:
    """Removed Tasks, Profile and Scene to bring back; the edited Tasks to revert -- one row each."""
    offer = maprestore.candidates(_older(), _newer(), state=PrimeItems)

    rows = {(c.kind, c.key, c.action) for c in offer.candidates}
    assert rows == {
        ("Task", "21", maprestore.BRING_BACK),
        ("Task", "22", maprestore.BRING_BACK),
        ("Task", "24", maprestore.BRING_BACK),
        ("Profile", "101", maprestore.BRING_BACK),
        ("Scene", "Panel", maprestore.BRING_BACK),
        ("Task", "20", maprestore.REVERT),
        ("Task", "23", maprestore.REVERT),
    }
    assert len(offer.candidates) == len(rows)


def test_a_rename_and_an_edit_of_one_task_are_one_revert(loaded: None) -> None:
    """xmldiff reports Task 23 twice; the list offers it once, carrying both lines of detail."""
    candidate = _candidate("Task", "23")

    assert candidate.action == maprestore.REVERT
    assert any("Old Name" in detail for detail in candidate.details)
    assert len(candidate.details) >= 2
    assert candidate.tag == "TASK-CHANGED"  # the edit is the larger fact


def test_a_row_carries_the_reports_own_tag(loaded: None) -> None:
    """The same bracketed word Changes Since printed, so the two can be read side by side."""
    assert _candidate("Task", "21").tag == "TASK-REMOVED"
    assert _candidate("Scene", "Panel").tag == "SCENE-REMOVED"
    assert _candidate("Task", "20").tag == "TASK-CHANGED"


def test_a_rename_alone_is_tagged_renamed(loaded: None) -> None:
    """Undo only the name: the row says RENAMED, not CHANGED."""
    task = PrimeItems.tasker_root_elements["all_tasks"]["23"]["xml"]
    task.remove(task.findall("Action")[1])  # now differs from the snapshot by name alone

    assert _candidate("Task", "23").tag == "TASK-RENAMED"


def test_bring_back_rows_come_first_and_have_nowhere_to_jump(loaded: None) -> None:
    """The row somebody is looking for is the deleted one -- and it is not here to be gone to."""
    offer = maprestore.candidates(_older(), _newer(), state=PrimeItems)
    actions = [c.action for c in offer.candidates]

    assert actions == sorted(actions, key=lambda action: action != maprestore.BRING_BACK)
    assert all(c.target is None for c in offer.candidates if c.action == maprestore.BRING_BACK)
    assert all(c.target is not None for c in offer.candidates if c.action == maprestore.REVERT)


def test_additions_projects_and_values_are_counted_not_offered(loaded: None) -> None:
    """A short list must not look like a short comparison: what it leaves out, it says."""
    offer = maprestore.candidates(_older(), _newer(), state=PrimeItems)

    assert offer.left_out[maprestore.LEFT_OUT_ADDED] == 1  # Task 30
    assert offer.left_out[maprestore.LEFT_OUT_PROJECT] >= 1  # Home changed, Gone removed
    assert offer.left_out[maprestore.LEFT_OUT_VALUE] == 1  # %Global
    assert not any(c.kind == "Project" for c in offer.candidates)


# ##################################################################################
# Bringing a Task back.
# ##################################################################################


def test_task_comes_back_on_its_own_id_and_in_its_project(loaded: None) -> None:
    """Its own id when that is free: the id Tasker on the device last knew it by."""
    _restore("Task", "21")

    assert _live("all_tasks")["21"]["name"] == "Helper"
    assert _live("all_tasks_by_name")["Helper"]["id"] == "21"
    assert "21" in _tids()
    assert [a.findtext("code") for a in actions_in_map_order(_live("all_tasks")["21"]["xml"])] == [FLASH]
    # And the comparison no longer has it as removed -- which is the whole claim.
    assert ("Task", "21") not in {(c.kind, c.key) for c in maprestore.candidates(_older(), _newer(), state=PrimeItems).candidates}


def test_restored_element_is_of_the_live_trees_class(loaded: None) -> None:
    """Built from the live tree's Element class, not the snapshot's -- all the way down."""
    _restore("Task", "21")

    restored = _live("all_tasks")["21"]["xml"]
    live_class = type(PrimeItems.xml_root)
    assert all(type(node) is live_class for node in restored.iter())


def test_task_whose_id_was_taken_comes_back_on_a_new_one(loaded: None) -> None:
    """The ID-conflict check: never overwrite whatever holds the old id now."""
    _add_task("21", "Squatter")

    plan = _restore("Task", "21")

    assert _live("all_tasks")["21"]["name"] == "Squatter"  # untouched
    restored_id = _live("all_tasks_by_name")["Helper"]["id"]
    assert restored_id != "21"
    assert _live("all_tasks")[restored_id]["xml"].findtext("id") == restored_id
    assert _live("all_tasks")[restored_id]["xml"].attrib["sr"] == f"task{restored_id}"
    assert restored_id in _tids()
    assert any("belongs to something else now" in step.text for step in plan.steps)


def test_task_whose_id_a_profile_holds_comes_back_on_a_new_one(loaded: None) -> None:
    """Tasks and Profiles draw from one id space -- a free Task id is not enough."""
    profile = ET.fromstring('<Profile sr="prof21" ve="2"><id>21</id><nme>Holder</nme></Profile>')  # noqa: S314
    _live("all_profiles")["21"] = {"xml": profile, "name": "Holder"}

    _restore("Task", "21")

    assert "21" not in _live("all_tasks")
    assert _live("all_tasks_by_name")["Helper"]["id"] != "21"


def test_task_whose_name_was_taken_comes_back_as_restored(loaded: None) -> None:
    """Duplicate's name check: never a second Task answering to the same name."""
    _add_task("31", "Helper")

    plan = _restore("Task", "21")

    assert _live("all_tasks_by_name")["Helper"]["id"] == "31"
    assert _live("all_tasks")["21"]["name"] == "Helper (restored)"
    assert _live("all_tasks")["21"]["xml"].findtext("nme") == "Helper (restored)"
    assert any("comes back as 'Helper (restored)'" in warning for warning in plan.warnings)


def test_bringing_back_a_called_task_says_the_calls_will_reach_it(loaded: None) -> None:
    """Task 20 still calls 'Helper' -- worth saying, since that is usually why it is wanted back."""
    plan = maprestore.plan_restore(_candidate("Task", "21"), _older(), FROM_WHEN, state=PrimeItems)

    assert any("1 Perform Task action" in warning for warning in plan.warnings)


def test_the_profile_that_ran_a_task_is_named_and_not_relinked(loaded: None) -> None:
    """One object at a time: 'Dusk' ran 'Evening', and bringing Evening back leaves Dusk alone."""
    plan = _restore("Task", "22")

    assert any("Profile 'Dusk'" in warning and "not relinked" in warning for warning in plan.warnings)
    assert "101" not in _live("all_profiles")


def test_task_whose_project_is_gone_comes_back_in_no_project(loaded: None) -> None:
    """Project Gone was deleted with it; the restore says so rather than rebuilding it."""
    plan = _restore("Task", "24")

    assert "24" in _live("all_tasks")
    assert "Gone" not in _live("all_projects")
    assert "24" not in _tids()
    assert any("Project 'Gone'" in warning for warning in plan.warnings)


# ##################################################################################
# Bringing a Profile back -- and its links, which cannot be taken on trust.
# ##################################################################################


def test_profile_whose_task_is_gone_comes_back_unlinked(loaded: None) -> None:
    """Its Entry Task was deleted too, and bringing that back is a second object."""
    plan = _restore("Profile", "101")

    profile = _live("all_profiles")["101"]["xml"]
    assert profile.find("mid0") is None
    assert "101" in (_live("all_projects")["Home"]["xml"].findtext("pids") or "").split(",")
    assert any("'Evening'" in warning and "comes back without one" in warning for warning in plan.warnings)
    assert "22" not in _live("all_tasks")


def test_profile_brought_back_after_its_task_finds_it_by_id(loaded: None) -> None:
    """Task first, then Profile: the ordinary way to put a pair back, and the link is made."""
    _restore("Task", "22")
    _restore("Profile", "101")

    assert _live("all_profiles")["101"]["xml"].findtext("mid0") == "22"


def test_profile_finds_its_task_by_name_when_the_task_came_back_on_a_new_id(loaded: None) -> None:
    """The case the link resolution exists for: an old id pointing at the wrong Task now."""
    _add_task("22", "Squatter")
    _restore("Task", "22")
    evening_id = _live("all_tasks_by_name")["Evening"]["id"]
    assert evening_id != "22"

    plan = _restore("Profile", "101")

    assert _live("all_profiles")["101"]["xml"].findtext("mid0") == evening_id
    assert any("now id" in step.text for step in plan.steps)


def test_a_new_id_never_takes_one_the_snapshot_still_needs(loaded: None) -> None:
    """Evening's new id must not be 101: Profile 'Dusk' is in the same snapshot and needs it.

    next_unique_task_or_profile_id alone would hand out max+1 of what is open NOW -- 101 here,
    since Dusk is not open -- and Dusk, restored next, would lose its own id to the order the
    two happened to be restored in.
    """
    _add_task("22", "Squatter")

    _restore("Task", "22")

    evening_id = _live("all_tasks_by_name")["Evening"]["id"]
    snapshot_ids = set(_older().tables["all_tasks"]) | set(_older().tables["all_profiles"])
    assert evening_id not in snapshot_ids
    assert "101" not in _live("all_tasks")


def test_scene_comes_back_into_a_configuration_that_has_no_scenes(loaded: None) -> None:
    """An EMPTY table is falsy: a write through `.get(...) or {}` would land in a dict nobody holds."""
    assert _live("all_scenes") == {}

    _restore("Scene", "Panel")

    assert "Panel" in PrimeItems.tasker_root_elements["all_scenes"]


# ##################################################################################
# Bringing a Scene back.
# ##################################################################################


def test_scene_comes_back_under_its_own_name_and_in_its_project(loaded: None) -> None:
    """Its own name, back in the Project whose <scenes> listed it."""
    _restore("Scene", "Panel")

    assert "Panel" in _live("all_scenes")
    assert _live("all_projects")["Home"]["xml"].findtext("scenes") == "Panel"


def test_scene_whose_name_is_taken_is_refused_not_renamed(loaded: None) -> None:
    """A Scene is its name: one brought back as 'Panel (restored)' is one nothing can show."""
    candidate = _candidate("Scene", "Panel")
    element = ET.fromstring('<Scene sr="scenePanel"><nme>Panel</nme></Scene>')  # noqa: S314
    _live("all_scenes")["Panel"] = {"xml": element, "name": "Panel"}

    plan = maprestore.plan_restore(candidate, _older(), FROM_WHEN, state=PrimeItems)

    assert not plan.can_apply
    assert plan.blocks[0].reason == "NAME-TAKEN"
    done, _ = maprestore.restore(plan)
    assert not done
    assert _live("all_scenes")["Panel"]["xml"] is element


# ##################################################################################
# Reverting.
# ##################################################################################


def test_revert_puts_the_old_actions_back_on_the_same_element(loaded: None) -> None:
    """In place: the element the tables hold is still the element the tree holds."""
    live_element = _live("all_tasks")["20"]["xml"]

    _restore("Task", "20")

    assert _live("all_tasks")["20"]["xml"] is live_element
    assert live_element in list(PrimeItems.xml_root)
    texts = [a.findtext("Str") for a in actions_in_map_order(live_element)]
    assert texts == ["hello", "world"]
    assert live_element.attrib["sr"] == "task20"
    assert live_element.findtext("id") == "20"


def test_revert_takes_the_old_name_back_and_moves_the_by_name_entry(loaded: None) -> None:
    """The by-name table is keyed by name, so a revert that renames has to move the entry."""
    _restore("Task", "23")

    assert _live("all_tasks")["23"]["name"] == "Old Name"
    assert _live("all_tasks_by_name")["Old Name"]["id"] == "23"
    assert "New Name" not in _live("all_tasks_by_name")
    assert len(actions_in_map_order(_live("all_tasks")["23"]["xml"])) == 1


def test_revert_keeps_the_current_name_when_the_old_one_is_taken(loaded: None) -> None:
    """Duplicate's rule again: no second Task answering to one name."""
    _add_task("32", "Old Name")

    plan = _restore("Task", "23")

    assert _live("all_tasks")["23"]["name"] == "New Name"
    assert _live("all_tasks")["23"]["xml"].findtext("nme") == "New Name"
    assert _live("all_tasks_by_name")["Old Name"]["id"] == "32"
    assert len(actions_in_map_order(_live("all_tasks")["23"]["xml"])) == 1  # content still reverted
    assert any("keeps the name 'New Name'" in warning for warning in plan.warnings)


def test_revert_of_a_task_that_went_away_since_is_refused(loaded: None) -> None:
    """The list can sit on screen while another dialog deletes the Task it offers to revert."""
    candidate = _candidate("Task", "20")
    del _live("all_tasks")["20"]

    plan = maprestore.plan_restore(candidate, _older(), FROM_WHEN, state=PrimeItems)

    assert not plan.can_apply
    assert plan.blocks[0].reason == "NOT-HERE"


def test_a_plan_whose_element_was_detached_is_refused_at_apply(loaded: None) -> None:
    """maprefac.apply's attachment check, reached through restore()."""
    plan = maprestore.plan_restore(_candidate("Task", "20"), _older(), FROM_WHEN, state=PrimeItems)
    element = _live("all_tasks")["20"]["xml"]
    del _live("all_tasks")["20"]
    PrimeItems.xml_root.remove(element)

    done, errors = maprestore.restore(plan)

    assert not done
    assert "no longer in the configuration" in errors[0]
    assert len(element.findall("Action")) == 2  # nothing was written to it


# ##################################################################################
# The rules that hold for every restore.
# ##################################################################################


def test_a_restore_is_one_undo(loaded: None) -> None:
    """Task, Project membership and by-name table: one press puts all of it back."""
    _restore("Task", "21")
    assert sessundo.can_undo()

    done, _ = sessundo.undo()

    assert done
    assert "21" not in PrimeItems.tasker_root_elements["all_tasks"]
    assert "21" not in _tids()


def test_nothing_next_to_a_restored_object_is_touched(loaded: None) -> None:
    """Never a merge: bringing one Task back leaves every other object exactly as it was."""
    before = {key: ET.tostring(entry["xml"]) for key, entry in _live("all_tasks").items()}
    profiles_before = {key: ET.tostring(entry["xml"]) for key, entry in _live("all_profiles").items()}

    _restore("Task", "21")

    after = {key: ET.tostring(entry["xml"]) for key, entry in _live("all_tasks").items() if key != "21"}
    assert after == before
    assert {key: ET.tostring(entry["xml"]) for key, entry in _live("all_profiles").items()} == profiles_before


def test_heading_says_where_the_old_version_comes_from(loaded: None) -> None:
    """'Restore Task X' without 'as it stood when' is the one thing the user has to be sure of."""
    plan = maprestore.plan_restore(_candidate("Task", "20"), _older(), FROM_WHEN, state=PrimeItems)

    assert FROM_WHEN in plan.what
    rows = maprefac.report_rows(plan)
    assert rows[0].text == plan.what


def test_a_task_brought_back_under_a_new_name_is_not_then_offered_as_a_rename(loaded: None) -> None:
    """Its only difference is the name, and the old name is taken -- a revert would change nothing."""
    _add_task("31", "Helper")
    _restore("Task", "21")  # comes back as 'Helper (restored)'

    offered = {(c.kind, c.key) for c in maprestore.candidates(_older(), _newer(), state=PrimeItems).candidates}

    assert ("Task", "21") not in offered
