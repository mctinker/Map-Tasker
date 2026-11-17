"""MapTasker Naming and Structure Rules (namerules, namefix) Unit Tests

The rules are the user's house style: a prefix per kind of name, no default names, a label on every action of a long
Task, a longest Task.  What is tested is that each rule finds what it should and only that, that every rule is off
until it is set, that a variable prefix that would change a variable's scope is refused rather than applied, that the
rules survive being saved, and that the renames offered are done without leaving a call to the old name behind -- and
are declined, with the reason, where they could not be done safely.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import maprefac, namefix, namerules
from maptasker.src.mapops.namerules import Rules

from tests.shared_fixtures import _load_local
from tests.test_taskstep import _act, _i, _s, flash, labelled, set_

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("_runtime")


def perform(name: str) -> str:
    return _act("130", _s(0, name), _i(1, 5))


def profile(number: int, name: str, task: int) -> str:
    return f'<Profile sr="prof{number}" ve="2"><id>{number}</id><mid0>{task}</mid0><nme>{name}</nme></Profile>'


def load(tmp_path: Path, *, profiles: tuple[tuple[int, str, int], ...] = (), **tasks: tuple[str, ...]) -> None:
    """Tasks 1.. in a Project called 'Home', plus the given Profiles (number, name, Task id)."""
    body = ""
    for number, (name, actions) in enumerate(tasks.items(), start=1):
        numbered = "".join(action.replace("act{}", f"act{index}") for index, action in enumerate(actions))
        body += f'<Task sr="task{number}" ve="2"><id>{number}</id><nme>{name.replace("_", " ")}</nme>{numbered}</Task>'
    tids = ",".join(str(number) for number in range(1, len(tasks) + 1))
    pids = ",".join(str(number) for number, _name, _task in profiles)
    project = f'<Project sr="proj0" ve="2"><name>Home</name><pids>{pids}</pids><tids>{tids}</tids></Project>'
    profile_xml = "".join(profile(*each) for each in profiles)
    _load_local(tmp_path, f'<TaskerData sr="" dvi="1" tv="6.3.13">{project}{profile_xml}{body}</TaskerData>')


def breaches(rules: Rules) -> list[namerules.Breach]:
    return namerules.check(rules, PrimeItems)


def names(found: list[namerules.Breach], rule: str) -> list[str]:
    return [breach.name for breach in found if breach.rule == rule]


# ##################################################################################
# Every rule is off until it is set.
# ##################################################################################
def test_with_no_rule_set_nothing_is_a_breach(tmp_path: Path) -> None:
    load(tmp_path, Task_12=(flash("x"),))

    assert breaches(Rules()) == []


def test_the_report_of_empty_rules_says_there_is_nothing_to_check(tmp_path: Path) -> None:
    load(tmp_path, Task_12=(flash("x"),))

    text = text_report(namerules.report_rows(Rules(), []))

    assert "No rule has been set" in text


# ##################################################################################
# Prefixes and default names.
# ##################################################################################
def test_a_task_that_does_not_start_with_the_prefix_is_a_breach_with_a_new_name(tmp_path: Path) -> None:
    load(tmp_path, Z_Sync=(flash("x"),), Wake_Up=(flash("y"),))

    (breach,) = breaches(Rules(task_prefix="Z "))

    assert breach.rule == namerules.PREFIX
    assert breach.name == "Wake Up"
    assert breach.suggestion == "Z Wake Up"
    assert breach.where is not None
    assert breach.where.key == "2"


def test_a_profile_prefix_is_read_against_profiles_not_tasks(tmp_path: Path) -> None:
    load(tmp_path, profiles=((1, "Home Wifi", 1),), Do=(flash("x"),))

    found = breaches(Rules(profile_prefix="P_"))

    assert [(breach.kind, breach.name) for breach in found] == [("profile", "Home Wifi")]


def test_default_names_are_found_in_each_kind_and_get_no_suggestion(tmp_path: Path) -> None:
    load(tmp_path, profiles=((1, "Profile 3", 1),), New_Task_12=(flash("x"),), Task_7=(flash("y"),), Wake=(flash("z"),))

    found = breaches(Rules(no_default_names=True))

    assert sorted(names(found, namerules.DEFAULT_NAME)) == ["New Task 12", "Profile 3", "Task 7"]
    assert not any(breach.can_rename for breach in found)


def test_a_default_name_is_not_also_reported_for_its_prefix(tmp_path: Path) -> None:
    load(tmp_path, Task_7=(flash("y"),))

    found = breaches(Rules(no_default_names=True, task_prefix="Z "))

    assert [breach.rule for breach in found] == [namerules.DEFAULT_NAME]


def test_a_profile_with_no_name_is_left_to_the_health_check(tmp_path: Path) -> None:
    load(tmp_path, profiles=((1, "", 1),), Do=(flash("x"),))

    assert [breach.kind for breach in breaches(Rules(profile_prefix="P_", no_default_names=True))] == []


def test_a_task_with_no_name_is_left_to_the_health_check(tmp_path: Path) -> None:
    load(tmp_path, _=(flash("x"),))

    assert breaches(Rules(task_prefix="Z ", no_default_names=True)) == []


# ##################################################################################
# Variables.
# ##################################################################################
def test_a_global_without_the_prefix_is_a_breach_and_a_local_is_judged_by_its_own_rule(tmp_path: Path) -> None:
    load(tmp_path, Do=(set_("%Counter", "1"), set_("%total", "2")))

    found = breaches(Rules(global_variable_prefix="App", local_variable_prefix="my_"))

    assert {(breach.kind, breach.name, breach.suggestion) for breach in found} == {
        ("global variable", "%Counter", "%AppCounter"),
        ("local variable", "%total", "%my_total"),
    }


def test_a_global_prefix_without_a_capital_is_refused_not_applied(tmp_path: Path) -> None:
    load(tmp_path, Do=(set_("%Counter", "1"),))

    found = breaches(Rules(global_variable_prefix="app_"))

    assert [breach.rule for breach in found] == [namerules.BAD_RULE]
    assert "would become a local variable" in found[0].message


def test_a_local_prefix_with_a_capital_is_refused_not_applied(tmp_path: Path) -> None:
    load(tmp_path, Do=(set_("%total", "1"),))

    found = breaches(Rules(local_variable_prefix="My_"))

    assert [breach.rule for breach in found] == [namerules.BAD_RULE]


def test_a_variable_that_already_has_the_prefix_is_not_a_breach(tmp_path: Path) -> None:
    load(tmp_path, Do=(set_("%AppCounter", "1"),))

    assert breaches(Rules(global_variable_prefix="App")) == []


# ##################################################################################
# Structure.
# ##################################################################################
def test_a_task_over_the_limit_is_too_long_and_one_at_the_limit_is_not(tmp_path: Path) -> None:
    load(tmp_path, Long=tuple(flash("x") for _ in range(4)), Exact=tuple(flash("x") for _ in range(3)))

    found = breaches(Rules(max_task_length=3))

    assert names(found, namerules.TOO_LONG) == ["Long"]


def test_a_long_task_must_label_every_action_and_a_short_one_need_not(tmp_path: Path) -> None:
    long_task = (labelled(flash("a"), "one"), flash("b"), flash("c"), labelled(flash("d"), "four"))
    load(tmp_path, Long=long_task, Short=(flash("x"), flash("y")))

    found = breaches(Rules(label_after=3))

    (breach,) = found
    assert breach.rule == namerules.UNLABELED
    assert breach.name == "Long"
    assert "2 of them have no label (action 2, 3)" in breach.message
    assert breach.where is not None
    assert breach.where.action == 2


def test_an_end_if_is_not_asked_for_a_label(tmp_path: Path) -> None:
    end_if = _act("38")
    load(tmp_path, Long=(labelled(flash("a"), "one"), labelled(flash("b"), "two"), end_if))

    assert breaches(Rules(label_after=2)) == []


# ##################################################################################
# Keeping the rules, and the report.
# ##################################################################################
def test_the_rules_are_kept_and_read_back(tmp_path: Path) -> None:
    where = str(tmp_path / "rules.json")
    rules = Rules(task_prefix="Z ", no_default_names=True, label_after=5, max_task_length=40)

    assert namerules.save(rules, where)

    assert namerules.load(where) == rules


def test_a_file_that_is_missing_or_not_json_gives_every_rule_off(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")

    assert namerules.load(str(tmp_path / "none.json")) == Rules()
    assert namerules.load(str(broken)) == Rules()


def test_a_hand_edited_field_that_is_wrong_costs_only_itself(tmp_path: Path) -> None:
    where = tmp_path / "rules.json"
    where.write_text(json.dumps({"task_prefix": "Z ", "label_after": "lots", "max_task_length": -4}))

    rules = namerules.load(str(where))

    assert (rules.task_prefix, rules.label_after, rules.max_task_length) == ("Z ", 0, 0)


def test_the_report_says_the_rules_and_each_breach_and_what_it_could_be_renamed(tmp_path: Path) -> None:
    load(tmp_path, Wake=(flash("x"),), Task_4=(flash("y"),))
    rules = Rules(task_prefix="Z ", no_default_names=True)

    text = text_report(namerules.report_rows(rules, breaches(rules)))

    assert "Task names start with:" in text
    assert "NAMES THAT DO NOT START WITH THEIR PREFIX -- 1" in text
    assert "could be renamed Z Wake" in text
    assert "NAMES TASKER GAVE AND NOBODY CHANGED -- 1" in text


def test_the_report_with_nothing_loaded_says_so() -> None:
    assert "No XML file has been loaded" in text_report(
        namerules.report_rows(Rules(task_prefix="Z "), [], loaded=False)
    )


def test_the_report_is_written_to_a_timestamped_file(tmp_path: Path) -> None:
    load(tmp_path, Wake=(flash("x"),))
    rules = Rules(task_prefix="Z ")

    path = namerules.write_report(namerules.report_rows(rules, breaches(rules)), PrimeItems)

    assert "MapTasker_NamingRules_" in path
    assert "NAMING AND STRUCTURE RULES" in open(path, encoding="utf-8").read()


# ##################################################################################
# Renaming, with a preview.
# ##################################################################################
def apply(rules: Rules) -> tuple[namefix.Plan, bool, list[str]]:
    plan = namefix.plan_renames(breaches(rules), PrimeItems)
    done, errors = maprefac.apply(plan, PrimeItems) if plan.can_apply else (False, [])
    return plan, done, errors


def test_renaming_a_task_rewrites_every_perform_task_that_calls_it(tmp_path: Path) -> None:
    load(tmp_path, Main=(perform("Wake Up"), flash("x")), Wake_Up=(flash("y"),))

    plan, done, errors = apply(Rules(task_prefix="Z "))

    assert (done, errors) == (True, [])
    assert any("1 Perform Task action that call it" in step.text for step in plan.steps)
    tasks = PrimeItems.tasker_root_elements
    assert tasks["all_tasks"]["2"]["name"] == "Z Wake Up"
    assert "Z Wake Up" in tasks["all_tasks_by_name"]
    assert "Wake Up" not in tasks["all_tasks_by_name"]
    performed = tasks["all_tasks"]["1"]["xml"].find("Action/Str[@sr='arg0']")
    assert performed is not None
    assert performed.text == "Z Wake Up"


def test_the_preview_is_a_plan_that_changes_nothing_until_it_is_applied(tmp_path: Path) -> None:
    load(tmp_path, Wake_Up=(flash("y"),))

    plan = namefix.plan_renames(breaches(Rules(task_prefix="Z ")), PrimeItems)

    assert plan.can_apply
    assert PrimeItems.tasker_root_elements["all_tasks"]["1"]["name"] == "Wake Up"
    assert "Rename Task 'Wake Up' to 'Z Wake Up'" in text_report(maprefac.report_rows(plan))


def test_a_task_whose_new_name_is_taken_is_left_alone_and_the_reason_is_given(tmp_path: Path) -> None:
    load(tmp_path, Wake_Up=(flash("y"),), Z_Wake_Up=(flash("z"),))

    plan, _done, _errors = apply(Rules(task_prefix="Z "))

    assert not plan.can_apply
    assert any("a Task called 'Z Wake Up' already exists" in warning for warning in plan.warnings)
    assert PrimeItems.tasker_root_elements["all_tasks"]["1"]["name"] == "Wake Up"


def test_two_tasks_with_one_name_are_not_renamed_because_a_call_could_mean_either(tmp_path: Path) -> None:
    load(tmp_path, Main=(perform("Twin"),), Twin=(flash("a"),), Twin_=(flash("b"),))
    PrimeItems.tasker_root_elements["all_tasks"]["3"]["name"] = "Twin"

    plan = namefix.plan_renames(breaches(Rules(task_prefix="Z ")), PrimeItems)

    assert any("another Task is also called 'Twin'" in warning for warning in plan.warnings)


def test_a_profile_is_renamed_in_every_table(tmp_path: Path) -> None:
    load(tmp_path, profiles=((1, "Home Wifi", 1),), Do=(flash("x"),))

    plan, done, errors = apply(Rules(profile_prefix="P_"))

    assert (done, errors) == (True, [])
    root = PrimeItems.tasker_root_elements
    assert root["all_profiles"]["1"]["name"] == "P_Home Wifi"
    assert "P_Home Wifi" in root["all_profiles_by_name"]
    assert root["all_profiles"]["1"]["xml"].findtext("nme") == "P_Home Wifi"
    assert plan.steps[0].text == "Rename Profile 'Home Wifi' to 'P_Home Wifi'"


def test_a_global_variable_is_renamed_everywhere_it_is_used(tmp_path: Path) -> None:
    load(tmp_path, One=(set_("%Counter", "1"),), Two=(flash("%Counter"),))

    plan, done, errors = apply(Rules(global_variable_prefix="App"))

    assert (done, errors) == (True, [])
    assert any("%Counter to %AppCounter" in step.text for step in plan.steps)
    xml = PrimeItems.tasker_root_elements["all_tasks"]["2"]["xml"]
    assert "%AppCounter" in "".join(element.text or "" for element in xml.iter())


def test_a_breach_with_no_new_name_is_not_something_to_rename(tmp_path: Path) -> None:
    load(tmp_path, Task_7=(flash("x"),))

    plan = namefix.plan_renames(breaches(Rules(no_default_names=True)), PrimeItems)

    assert not plan.can_apply
    assert "None of the chosen breaches has a new name to give." in plan.warnings


def test_applying_is_one_undo_step(tmp_path: Path) -> None:
    load(tmp_path, Wake_Up=(flash("y"),), Sleep=(flash("z"),))
    sessundo.clear(PrimeItems)

    apply(Rules(task_prefix="Z "))

    assert [label for label, _when in sessundo.history(PrimeItems)] == [
        "Rename 2 objects to follow the naming rules",
    ]
