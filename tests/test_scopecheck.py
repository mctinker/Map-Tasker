"""MapTasker Safe Variable Rename and Scope Fixer (scopecheck, mapscope) Unit Tests

Tasker takes a variable's scope from the case of its name, so what is tested is the evidence a spelling is wrong and
the fix that follows -- and, just as much, what is NOT reported: the lower case copy of a global a Task makes on
purpose, a local its caller hands it, a local that is set and read in one Task and so is doing its job.  A rule about
spelling fails by firing on a configuration that is perfectly deliberate, and only the negative half of each test can
catch that.

The fixes are maprefac_variable's, so their blocks, previews and one Undo are tested there; what is tested here is
that each finding is handed to it with the right arguments, and that a merge is a merge only when asked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src.analysis import scopecheck
from maptasker.src.analysis.healthck import run_health_check
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import maprefac, mapscope

from tests.shared_fixtures import _load_local
from tests.test_mapvars import _act, _i, _s, _task, _variable, flash, set_

pytestmark = pytest.mark.usefixtures("_runtime")


def perform(task: str) -> str:
    return _act("130", _s(0, task), _i(1, 5), _s(2, ""), _s(3, ""), _s(4, ""))


# The configuration, by what each Task is there to show:
#   Owner         sets and reads the global %Counter                                  -> where %Counter comes from
#   Slip Read     only READS the local %counter, never spells %Counter                -> SCOPE-CASE-MISMATCH
#   Slip Write    only SETS the local %counter, never spells %Counter                 -> SCOPE-CASE-MISMATCH
#   Both Ways     uses %counter AND %Counter: a deliberate copy                       -> left alone
#   Balanced      sets and reads %counter itself: a local doing its job               -> left alone
#   Handed        reads %counter, and Owner performs it, so the call may have passed it -> left alone
#   Reads Shared  reads %shared, never sets it                                        -> SCOPE-LOCAL-NEVER-SET
#   Sets Shared   sets %shared                                                        ('s the other end)
#   Called Reader reads %other, performed by Owner                                    -> left alone
#   Sets Other    sets %other
#   Mode Setter   sets %mode, which the Variables tab holds in lower case             -> SCOPE-DECLARED-LOWERCASE
_XML = f"""<TaskerData sr="" dvi="1" tv="6.3.13">
  {_variable(0, "%Counter", "1")}
  {_variable(1, "%mode", "day")}
  {_task(1, "Owner", set_("%Counter", "2"), flash("n %Counter"), perform("Handed"), perform("Called Reader"))}
  {_task(2, "Slip Read", flash("count %counter"))}
  {_task(3, "Slip Write", set_("%counter", "5"))}
  {_task(4, "Both Ways", set_("%counter", "%Counter"), flash("%counter"))}
  {_task(5, "Balanced", set_("%counter", "1"), flash("%counter"))}
  {_task(6, "Handed", flash("got %counter"))}
  {_task(7, "Reads Shared", flash("value %shared"))}
  {_task(8, "Sets Shared", set_("%shared", "yes"), flash("%shared"))}
  {_task(9, "Called Reader", flash("here %other"))}
  {_task(10, "Sets Other", set_("%other", "1"), flash("%other"))}
  {_task(11, "Mode Setter", set_("%mode", "night"))}
</TaskerData>"""


@pytest.fixture
def issues(tmp_path: Path) -> list[scopecheck.ScopeIssue]:
    _load_local(tmp_path, _XML)
    return scopecheck.find_issues(PrimeItems)


def _named(issues: list[scopecheck.ScopeIssue], kind: str) -> list[scopecheck.ScopeIssue]:
    return [issue for issue in issues if issue.kind == kind]


def _tasks(issues: list[scopecheck.ScopeIssue], kind: str) -> set[str]:
    return {issue.where.name for issue in _named(issues, kind)}


# ##################################################################################
# What is found
# ##################################################################################
def test_a_local_only_read_beside_a_global_of_the_same_letters_is_a_slip(issues: list[scopecheck.ScopeIssue]) -> None:
    assert "Slip Read" in _tasks(issues, scopecheck.CASE_MISMATCH)


def test_a_local_only_set_beside_a_global_of_the_same_letters_is_a_slip(issues: list[scopecheck.ScopeIssue]) -> None:
    assert "Slip Write" in _tasks(issues, scopecheck.CASE_MISMATCH)


def test_the_finding_suggests_the_global_s_own_spelling(issues: list[scopecheck.ScopeIssue]) -> None:
    slip = next(issue for issue in _named(issues, scopecheck.CASE_MISMATCH) if issue.where.name == "Slip Read")

    assert (slip.name, slip.suggestion, slip.merge) == ("%counter", "%Counter", True)
    assert "reads %counter" in slip.detail
    assert "nothing in this Task ever put a value there" in slip.detail


def test_a_write_that_is_lost_says_so(issues: list[scopecheck.ScopeIssue]) -> None:
    slip = next(issue for issue in _named(issues, scopecheck.CASE_MISMATCH) if issue.where.name == "Slip Write")

    assert "the value is gone when the Task ends" in slip.detail


def test_a_deliberate_local_copy_of_a_global_is_left_alone(issues: list[scopecheck.ScopeIssue]) -> None:
    """The Task spells both ways, so it has seen the difference."""
    assert "Both Ways" not in _tasks(issues, scopecheck.CASE_MISMATCH)


def test_a_local_that_is_set_and_read_is_a_local_doing_its_job(issues: list[scopecheck.ScopeIssue]) -> None:
    assert "Balanced" not in _tasks(issues, scopecheck.CASE_MISMATCH)


def test_a_performed_task_may_have_been_handed_the_local(issues: list[scopecheck.ScopeIssue]) -> None:
    assert "Handed" not in _tasks(issues, scopecheck.CASE_MISMATCH)


def test_a_local_read_and_never_set_while_another_task_sets_one_is_a_shared_local(
    issues: list[scopecheck.ScopeIssue],
) -> None:
    (found,) = _named(issues, scopecheck.LOCAL_NEVER_SET)

    assert (found.name, found.suggestion, found.owner) == ("%shared", "%Shared", None)
    assert found.where.name == "Reads Shared"
    assert "Sets Shared" in found.detail


def test_a_performed_task_reading_a_local_is_not_evidence(issues: list[scopecheck.ScopeIssue]) -> None:
    assert "%other" not in {issue.name for issue in issues}


def test_a_declared_name_with_no_capital_is_found(issues: list[scopecheck.ScopeIssue]) -> None:
    (found,) = _named(issues, scopecheck.DECLARED_LOWERCASE)

    assert (found.name, found.suggestion, found.owner) == ("%mode", "%Mode", "")
    assert "LOCAL of that name" in found.detail


def test_the_grading(issues: list[scopecheck.ScopeIssue]) -> None:
    severities = {issue.kind: issue.severity for issue in issues}

    assert severities[scopecheck.DECLARED_LOWERCASE] == scopecheck.WARNING
    assert severities[scopecheck.CASE_MISMATCH] == scopecheck.INFO
    assert severities[scopecheck.LOCAL_NEVER_SET] == scopecheck.INFO


def test_the_findings_come_strongest_kind_first(issues: list[scopecheck.ScopeIssue]) -> None:
    order = [issue.kind for issue in issues]

    assert order == sorted(
        order, key=[scopecheck.CASE_MISMATCH, scopecheck.DECLARED_LOWERCASE, scopecheck.LOCAL_NEVER_SET].index
    )


def test_a_tasker_variable_is_never_a_finding(tmp_path: Path) -> None:
    _load_local(tmp_path, _task_xml(set_("%par1", "x"), flash("%err and %errmsg and %BATT")))

    assert scopecheck.find_issues(PrimeItems) == []


def _task_xml(*actions: str) -> str:
    return f'<TaskerData sr="" dvi="1" tv="6.3.13">{_task(1, "Only", *actions)}</TaskerData>'


def test_two_globals_of_the_same_letters_leave_no_single_suggestion(tmp_path: Path) -> None:
    xml = (
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        f"{_variable(0, '%MyVar', '1')}{_variable(1, '%Myvar', '2')}"
        f"{_task(1, 'Slip', flash('%myvar'))}</TaskerData>"
    )
    _load_local(tmp_path, xml)

    (found,) = scopecheck.find_issues(PrimeItems)

    assert found.suggestion == ""
    assert not found.merge
    assert "%MyVar, %Myvar" in found.detail


def test_nothing_loaded_finds_nothing() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}, "all_projects": {}, "all_profiles": {}, "all_scenes": {}}

    assert scopecheck.find_issues(PrimeItems) == []


# ##################################################################################
# The fixes
# ##################################################################################
def _text_of_task(name: str) -> str:
    task = next(task for task in PrimeItems.tasker_root_elements["all_tasks"].values() if task["name"] == name)
    return "".join(task["xml"].itertext())


def test_a_slip_is_fixed_by_spelling_it_as_the_global_and_the_plan_says_it_is_a_merge(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    slip = next(i for i in scopecheck.find_issues(PrimeItems) if i.where.name == "Slip Read")

    plan = mapscope.plan_fix(slip, PrimeItems)

    assert plan.can_apply, [block.explanation for block in plan.blocks]
    assert plan.warnings[0].startswith("MERGE:")
    done, errors = maprefac.apply(plan, state=PrimeItems)
    assert done, errors
    assert "%Counter" in _text_of_task("Slip Read")
    assert "%counter" not in _text_of_task("Slip Read")
    assert "%counter" in _text_of_task("Slip Write"), "only the Task chosen was changed"


def test_one_undo_puts_a_fix_back(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    slip = next(i for i in scopecheck.find_issues(PrimeItems) if i.where.name == "Slip Read")
    maprefac.apply(mapscope.plan_fix(slip, PrimeItems), state=PrimeItems)

    assert sessundo.undo(PrimeItems)[0]

    assert "%counter" in _text_of_task("Slip Read")


def test_after_a_fix_the_finding_is_gone(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    slip = next(i for i in scopecheck.find_issues(PrimeItems) if i.where.name == "Slip Read")
    maprefac.apply(mapscope.plan_fix(slip, PrimeItems), state=PrimeItems)

    assert "Slip Read" not in _tasks(scopecheck.find_issues(PrimeItems), scopecheck.CASE_MISMATCH)


def test_a_merge_is_not_one_unless_the_name_is_taken(tmp_path: Path) -> None:
    """Typing a name nothing uses is a plain scope change, and carries no merge warning."""
    _load_local(tmp_path, _XML)
    slip = next(i for i in scopecheck.find_issues(PrimeItems) if i.where.name == "Slip Read")

    plan = mapscope.plan_fix(slip, PrimeItems, "%CounterCopy")

    assert plan.can_apply
    assert not any(warning.startswith("MERGE:") for warning in plan.warnings)


def test_a_new_name_that_would_not_change_the_scope_is_blocked(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    slip = next(i for i in scopecheck.find_issues(PrimeItems) if i.where.name == "Slip Read")

    plan = mapscope.plan_fix(slip, PrimeItems, "%counter2")

    assert plan.is_blocked
    assert plan.blocks[0].reason == "SPELLING"


def test_the_declared_lower_case_name_is_renamed_everywhere_including_the_variables_tab(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    declared = next(i for i in scopecheck.find_issues(PrimeItems) if i.kind == scopecheck.DECLARED_LOWERCASE)

    plan = mapscope.plan_fix(declared, PrimeItems)
    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done, errors
    root = PrimeItems.xml_root
    assert root is not None
    assert {element.findtext("n") for element in root.findall("Variable")} == {"%Counter", "%Mode"}
    assert "%Mode" in _text_of_task("Mode Setter")


def test_a_shared_local_becomes_one_global_in_every_task_that_uses_it(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    shared = next(i for i in scopecheck.find_issues(PrimeItems) if i.kind == scopecheck.LOCAL_NEVER_SET)

    plan = mapscope.plan_fix(shared, PrimeItems)
    assert plan.can_apply, [block.explanation for block in plan.blocks]
    assert any("ONE variable" in warning for warning in plan.warnings)
    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done, errors
    assert "%Shared" in _text_of_task("Reads Shared")
    assert "%Shared" in _text_of_task("Sets Shared")
    assert "%shared" not in _text_of_task("Sets Shared")


def test_a_finding_with_no_single_answer_needs_a_name_given(tmp_path: Path) -> None:
    xml = (
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        f"{_variable(0, '%MyVar', '1')}{_variable(1, '%Myvar', '2')}"
        f"{_task(1, 'Slip', flash('%myvar'))}</TaskerData>"
    )
    _load_local(tmp_path, xml)
    (found,) = scopecheck.find_issues(PrimeItems)

    assert mapscope.plan_fix(found, PrimeItems).blocks[0].reason == "NO-SUGGESTION"
    assert mapscope.plan_fix(found, PrimeItems, "%MyVar").can_apply


# ##################################################################################
# In the Health Check
# ##################################################################################
def test_the_health_check_reports_them_with_a_note(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    rows, _counts = run_health_check(state=PrimeItems)
    report = text_report(rows)

    for tag in scopecheck.TAGS:
        assert [line for line in report.splitlines() if line.startswith(f"[{tag}]")], tag
    assert "NOTE ON VARIABLE SPELLING" in report


def test_the_categories_can_be_unticked(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    rows, _counts = run_health_check(state=PrimeItems, skip=scopecheck.TAGS)
    report = text_report(rows)

    assert not [line for line in report.splitlines() if line.startswith("[SCOPE-")]
    assert "NOTE ON VARIABLE SPELLING" not in report
