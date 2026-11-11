"""Split Project (maprefac_split): some Tasks and Profiles move, with what they need, into a new Project.

The fixture is Project Dependencies' own -- four Projects that use each other in every way the rules care about -- plus
a small one of its own for the shared Task a Profile left behind still runs.  What is checked:

  what comes along (the walk Import With Dependencies makes, run on the loaded file) and why it is said to,
  that Apply moves membership and nothing else, in one press of Undo,
  that what is reported as still crossing the new boundary IS what Project Dependencies shows once it is done,
  and what stops a split before it starts.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from maptasker.src.core.mapjump import PROFILE, TASK, text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import maprefac, maprefac_split, projdeps
from maptasker.src.mapops.maprefac_model import SPLIT, members, object_table

from tests.doubles import required
from tests.test_maprefac import _load
from tests.test_projdeps import _XML, _action, _perform, _project, _task

NEW = "Morning Stuff"


@pytest.fixture
def loaded() -> Iterator[None]:
    sessundo.clear(PrimeItems)
    _load(_XML)
    yield
    sessundo.clear(PrimeItems)


def _plan(picks: list[tuple[str, str]], name: str = NEW) -> maprefac_split.Plan:
    return maprefac_split.plan_split(picks, name, PrimeItems)


def _steps(plan: maprefac_split.Plan) -> list[str]:
    return [step.text for step in plan.steps]


def _crossings(plan: maprefac_split.Plan) -> list[str]:
    return [step.text for step in plan.crossings or []]


def _members(project: str, tag: str) -> list[str]:
    return members(object_table("all_projects", state=PrimeItems)[project]["xml"], tag)


# ##################################################################################
# What comes along
# ##################################################################################
def test_a_task_comes_with_the_tasks_it_performs_and_the_scene_it_shows_and_what_that_runs(loaded: None) -> None:
    plan = _plan([(TASK, "10")])

    assert not plan.is_blocked
    steps = _steps(plan)
    assert steps[0] == f"Create Project '{NEW}'"
    assert "Move Task 'Morning' out of Project 'Home' -- chosen" in steps
    assert "Move Task 'Setup' out of Project 'Utilities' -- performed by Task 'Morning'" in steps
    assert "Move Task 'Local' out of Project 'Home' -- performed by Task 'Morning'" in steps
    assert "Move Scene 'Panel' out of Project 'Media' -- shown by Task 'Morning'" in steps
    assert "Move Task 'Chime' out of Project 'Utilities' -- run by Scene 'Panel'" in steps


def test_a_profile_comes_with_the_tasks_it_runs(loaded: None) -> None:
    steps = _steps(_plan([(PROFILE, "100")]))

    assert "Move Profile 'Boot Profile' out of Project 'Home' -- chosen" in steps
    assert "Move Task 'Boot' out of Project 'Utilities' -- run by Profile 'Boot Profile'" in steps


def test_what_two_things_both_need_is_moved_once(loaded: None) -> None:
    steps = _steps(_plan([(TASK, "10"), (TASK, "30")]))  # both perform 'Setup'

    assert sum("Task 'Setup'" in step for step in steps) == 1


def test_every_step_that_names_an_object_is_a_click_to_it(loaded: None) -> None:
    plan = _plan([(TASK, "10")])

    assert plan.steps[0].where is None, "the Project does not exist yet"
    assert all(step.where is not None for step in plan.steps[1:])


# ##################################################################################
# Doing it
# ##################################################################################
def test_apply_lists_everything_in_the_new_project_and_takes_it_out_of_the_old_ones(loaded: None) -> None:
    plan = _plan([(TASK, "10")])

    assert maprefac.apply(plan, state=PrimeItems) == (True, [])

    assert set(_members(NEW, "tids")) == {"10", "20", "12", "22"}
    assert _members(NEW, "scenes") == ["Panel"]
    assert _members("Home", "tids") == ["11"]
    assert _members("Utilities", "tids") == ["21", "23", "24", "25"]
    assert _members("Media", "scenes") == []
    assert _members("Lonely", "tids") == ["40", "41"], "a Project nothing moved out of is not touched"


def test_nothing_is_copied_renamed_or_given_a_new_id(loaded: None) -> None:
    before = {key: entry["name"] for key, entry in object_table("all_tasks", state=PrimeItems).items()}
    ids = set(before)

    maprefac.apply(_plan([(TASK, "10")]), state=PrimeItems)

    after = {key: entry["name"] for key, entry in object_table("all_tasks", state=PrimeItems).items()}
    assert after == before
    assert set(after) == ids


def test_the_whole_split_is_one_press_of_undo(loaded: None) -> None:
    before = {name: _members(name, "tids") for name in object_table("all_projects", state=PrimeItems)}
    maprefac.apply(_plan([(TASK, "10")]), state=PrimeItems)
    assert NEW in object_table("all_projects", state=PrimeItems)

    assert sessundo.undo(state=PrimeItems)[0] is True

    assert NEW not in object_table("all_projects", state=PrimeItems)
    assert {name: _members(name, "tids") for name in object_table("all_projects", state=PrimeItems)} == before
    assert _members("Media", "scenes") == ["Panel"]
    assert not sessundo.can_undo(PrimeItems)


def test_a_task_listed_by_two_projects_is_taken_out_of_both(loaded: None) -> None:
    home = object_table("all_projects", state=PrimeItems)["Home"]["xml"]
    maprefac_split.projedit.set_project_members(home, "tids", ["10", "11", "12", "40"])  # 40 is Lonely's too

    maprefac.apply(_plan([(TASK, "40")]), state=PrimeItems)

    assert "40" not in _members("Home", "tids")
    assert "40" not in _members("Lonely", "tids")
    assert "40" in _members(NEW, "tids")


# ##################################################################################
# What still crosses
# ##################################################################################
def test_what_is_left_behind_and_still_uses_something_that_moved_is_reported(loaded: None) -> None:
    plan = _plan([(TASK, "10")])

    assert _crossings(plan) == [
        "Project 'Media' > Task 'Show' (id 30) action 1 performs Task 'Setup', which has moved to the new Project",
    ]
    assert required(plan.crossings)[0].where is not None, "and it is a click to the place that uses it"


def test_a_profile_that_stays_and_runs_a_task_that_moved_is_reported(loaded: None) -> None:
    sessundo.clear(PrimeItems)
    _load(_SHARED_XML)

    plan = _plan([(PROFILE, "100")])

    assert any(
        "Profile 'Second' (id 101) runs Task 'Shared Helper'" in line and "has moved to the new Project" in line
        for line in _crossings(plan)
    ), _crossings(plan)


def test_a_global_variable_set_on_the_other_side_is_reported(loaded: None) -> None:
    plan = _plan([(TASK, "11")])  # Evening reads %Alarm, which only Utilities' Alarmer sets

    assert any("%Alarm" in line and "which is set only in Project 'Utilities'" in line for line in _crossings(plan))


def test_a_split_that_leaves_nothing_joined_says_so(loaded: None) -> None:
    plan = _plan([(TASK, "40")])  # Solo, and the Solo Helper it performs: all of Lonely, and nothing else touches it

    assert plan.crossings == []
    rows = text_report(maprefac.report_rows(plan))
    assert "NOTHING CROSSES THE NEW BOUNDARY" in rows


def test_the_crossings_are_what_project_dependencies_shows_once_it_is_done(loaded: None) -> None:
    """The preview and the window it points at must never say two things about the same split."""
    for picks in ([(TASK, "10")], [(TASK, "11")], [(PROFILE, "100")], [(TASK, "24")], [(TASK, "10"), (TASK, "24")]):
        sessundo.clear(PrimeItems)
        _load(_XML)
        plan = _plan(picks)
        assert maprefac.apply(plan, state=PrimeItems)[0]

        graph = projdeps.build_graph(PrimeItems)
        shown = {
            (link.user.label, link.verb, link.used)
            for edge in (*graph.uses(NEW), *graph.used_by(NEW))
            for link in edge.links
        }
        said = {
            (step.where.label, verb, used)
            for step in plan.crossings or []
            for verb, used in [_verb_and_used(step.text)]
            if step.where is not None
        }
        assert said == shown, picks


def _verb_and_used(line: str) -> tuple[str, str]:
    """('performs', 'Setup') from "... performs Task 'Setup', which ...", the pieces a Link is compared by."""
    for verb in ("performs", "shows", "runs", "reads"):
        marker = f" {verb} "
        if marker in line:
            thing = line.split(marker, 1)[1].split(", which", 1)[0]
            return verb, thing.split("'", 2)[1] if "'" in thing else thing
    return "", ""


# ##################################################################################
# Warnings
# ##################################################################################
def test_a_project_every_member_of_which_moved_is_said_to_be_left_empty(loaded: None) -> None:
    plan = _plan([(TASK, "40")])

    assert any("Project 'Lonely' will be left with nothing in it" in warning for warning in plan.warnings)


def test_a_task_no_project_lists_is_said_to_be_filed_for_the_first_time(loaded: None) -> None:
    plan = _plan([(TASK, "99")])  # Orphan: in no Project at all

    assert any("Task 'Orphan'" in warning and "not listed by any Project" in warning for warning in plan.warnings)


def test_a_call_to_a_task_that_is_not_in_the_file_is_said_not_to_run(loaded: None) -> None:
    sessundo.clear(PrimeItems)
    _load(_XML.replace("</TaskerData>", _task("50", "Caller", _perform("Nowhere")) + "</TaskerData>"))

    plan = _plan([(TASK, "50")])

    assert any("'Nowhere', which is not in this file" in warning for warning in plan.warnings)


def test_a_name_a_moving_task_shares_with_one_that_stays_is_said(loaded: None) -> None:
    plan = _plan([(TASK, "23")])  # 'Shared' in Utilities; Media has another

    assert any("Another Task is called 'Shared'" in warning for warning in plan.warnings)


# ##################################################################################
# What stops it
# ##################################################################################
@pytest.mark.parametrize(
    ("picks", "name", "reason"),
    [
        ([], NEW, "NOTHING-CHOSEN"),
        ([(TASK, "10")], "", "NO-NAME"),
        ([(TASK, "10")], "   ", "NO-NAME"),
        ([(TASK, "10")], "Home", "NAME-TAKEN"),
        ([(TASK, "10")], "Bad\x01Name", "BAD-NAME"),
        ([(TASK, "9999")], NEW, "NO-TASK"),
        ([(PROFILE, "9999")], NEW, "NO-PROFILE"),
    ],
)
def test_what_cannot_be_split_is_refused_with_the_reason(
    loaded: None, picks: list[tuple[str, str]], name: str, reason: str
) -> None:
    plan = _plan(picks, name)

    assert plan.is_blocked
    assert reason in [block.reason for block in plan.blocks]
    assert not plan.can_apply
    assert maprefac.apply(plan, state=PrimeItems)[0] is False


def test_a_refused_split_changes_nothing(loaded: None) -> None:
    before = {name: _members(name, "tids") for name in object_table("all_projects", state=PrimeItems)}

    maprefac.apply(_plan([(TASK, "10")], "Home"), state=PrimeItems)

    assert {name: _members(name, "tids") for name in object_table("all_projects", state=PrimeItems)} == before


def test_the_plan_is_a_split_and_is_named_for_the_new_project(loaded: None) -> None:
    plan = _plan([(TASK, "10")])

    assert plan.kind == SPLIT
    assert plan.what == f"Split into new Project '{NEW}'"


# ##################################################################################
# What can be chosen
# ##################################################################################
def test_every_profile_and_task_can_be_chosen_by_a_key_that_says_which(loaded: None) -> None:
    choices = dict(maprefac_split.pick_choices(PrimeItems))

    assert choices["profile:100"].startswith("Profile: Boot Profile")
    assert choices["task:10"] == "Task: Morning  (Home)"
    assert len([key for key in choices if key.startswith("task:")]) == len(object_table("all_tasks", state=PrimeItems))


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("task:12", (TASK, "12")),
        ("profile:5", (PROFILE, "5")),
        ("scene:Panel", ("", "")),
        ("task:", ("", "")),
        ("12", ("", "")),
    ],
)
def test_a_choice_key_is_read_back(key: str, expected: tuple[str, str]) -> None:
    assert maprefac_split.split_pick(key) == expected


# Home holds two Profiles that both run Task 5: splitting out the first takes the Task from under the second.
_SHARED_XML = (
    '<TaskerData sr="" dvi="1" tv="6.3.13">'
    + _project("Home", "100,101", "5")
    + '<Profile sr="prof100" ve="2"><id>100</id><nme>First</nme><mid0>5</mid0></Profile>'
    + '<Profile sr="prof101" ve="2"><id>101</id><nme>Second</nme><mid0>5</mid0></Profile>'
    + _task("5", "Shared Helper", _action("548", "hi"))
    + "</TaskerData>"
)
