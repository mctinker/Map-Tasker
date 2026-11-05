"""MapTasker Error-handling Audit Unit Tests

Every check in errcheck.py is a pure function over the lookup tables taskerd.get_the_xml_data builds, so these
tests build those tables from a small XML fixture, the way tests/test_proflint.py does.

The fixture holds, for each way of getting it wrong, the Task that does and beside it the Task that does the same
thing right.  Both halves matter: a rule about a failure being thrown away fails by firing on a Task that checks
%err in some way nobody thought of, and only the negative half of each test can catch that.

The default -- no 'Continue Task After Error' -- stops the Task on a failure, which is loud, so the rule is about
the ticked box only.  Tasker writes the ticked box as <se>false</se>, which reads backwards; the fixture does the
same, so a test that passed on the wrong reading would not pass here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src.analysis import errcheck, healthck
from maptasker.src.analysis.healthck import run_health_check
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import taskerd


def _act(number: int, code: int, *, carries_on: bool = False, off: bool = False, text: str = "") -> str:
    """One action: 'Continue Task After Error' ticked or not, switched off or not, with some text in an argument."""
    flag = "<se>false</se>" if carries_on else ""
    disabled = "<on>false</on>" if off else ""
    argument = f'<Str sr="arg0" ve="3">{text}</Str>' if text else ""
    return f'<Action sr="act{number}" ve="7"><code>{code}</code>{flag}{disabled}{argument}</Action>'


def _task(task_id: int, name: str, *actions: str) -> str:
    return f'<Task sr="task{task_id}"><id>{task_id}</id><nme>{name}</nme>{"".join(actions)}</Task>'


_WEB, _SHELL, _PERFORM, _WRITE, _FLASH, _SET = 339, 123, 130, 410, 548, 547
_IF_ERR = (
    '<Action sr="act1" ve="7"><code>37</code><ConditionList sr="if">'
    '<Condition sr="c0" ve="3"><lhs>%errmsg</lhs><op>3</op><rhs>*</rhs></Condition></ConditionList></Action>'
)
_MANY = (_WEB, _SHELL, _PERFORM, _WRITE, 118, 404)

_FIXTURE = f"""<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><tids>50,51,52,53,54,55,56,57,58,59,60,61,62</tids></Project>
  {_task(50, "Ignored Request", _act(0, _WEB, carries_on=True), _act(1, _SHELL, carries_on=True))}
  {_task(51, "Checked In Text", _act(0, _WEB, carries_on=True), _act(1, _FLASH, text="Failed: %err"))}
  {_task(52, "Checked In If", _act(0, _WEB, carries_on=True), _IF_ERR)}
  {_task(53, "Stops On Error", _act(0, _WEB), _act(1, _FLASH, text="Done"))}
  {_task(54, "Switched Off", _act(0, _WEB, carries_on=True, off=True))}
  {_task(55, "Disabled Reader", _act(0, _WEB, carries_on=True), _act(1, _FLASH, off=True, text="%err"))}
  {_task(56, "Read Before", _act(0, _FLASH, text="%err"), _act(1, _WEB, carries_on=True))}
  {_task(57, "Longer Name", _act(0, _WEB, carries_on=True), _act(1, _FLASH, text="%error_count"))}
  {_task(58, "Upper Case", _act(0, _WEB, carries_on=True), _act(1, _FLASH, text="%ERRMSG"))}
  {_task(59, "Not Risky", _act(0, _SET, carries_on=True), _act(1, _FLASH, text="Done"))}
  {_task(60, "Many", *(_act(number, code, carries_on=True) for number, code in enumerate(_MANY)))}
  {_task(61, "Map Order", *(_act(number, _FLASH, text="x") for number in range(10)), _act(10, _WEB, carries_on=True))}
  {
    _task(
        62, "Two Reads", _act(0, _WEB, carries_on=True), _act(1, _SHELL, carries_on=True), _act(2, _FLASH, text="%err")
    )
}
</TaskerData>
"""


def _load(xml_text: str) -> None:
    root = ET.fromstring(xml_text)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100)
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": {},
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": {},
        "all_services": [],
        "all_profiles_by_name": {},
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items() if task["name"]
    }
    PrimeItems.tasker_root_elements = tables


@pytest.fixture
def problems() -> list[errcheck.Problem]:
    _load(_FIXTURE)
    return errcheck.lint_problems(state=PrimeItems)


def _flagged(problems: list[errcheck.Problem]) -> list[str]:
    """The names of the Tasks with a finding."""
    return sorted(problem.where.name for problem in problems)


def _finding(problems: list[errcheck.Problem], name: str) -> errcheck.Problem:
    return next(problem for problem in problems if problem.where.name == name)


def test_a_failure_nothing_looks_at_is_reported(problems: list[errcheck.Problem]) -> None:
    assert "Ignored Request" in _flagged(problems)


def test_one_finding_names_every_unhandled_action_of_the_task(problems: list[errcheck.Problem]) -> None:
    finding = _finding(problems, "Ignored Request")

    assert finding.tag == errcheck.IGNORED_ERROR
    assert finding.where.action == 1, "the click goes to the first one"
    assert [target.action for target in finding.related] == [2], "and the others are one jump each"
    assert "1 HTTP Request (web request)" in finding.detail
    assert "2 Run Shell (shell command)" in finding.detail
    assert "These actions are set to 'Continue Task After Error'" in finding.detail


def test_a_single_action_is_described_in_the_singular(problems: list[errcheck.Problem]) -> None:
    finding = _finding(problems, "Read Before")

    assert finding.detail.startswith("This action is set to 'Continue Task After Error'")
    assert finding.related == []


@pytest.mark.parametrize("name", ["Checked In Text", "Checked In If", "Upper Case"])
def test_reading_err_or_errmsg_afterwards_is_looking(problems: list[errcheck.Problem], name: str) -> None:
    """In an argument, in an If condition, whatever the case."""
    assert name not in _flagged(problems)


def test_the_default_stops_the_task_and_is_not_reported(problems: list[errcheck.Problem]) -> None:
    """Without the box ticked the Task stops where it failed, which is not a failure thrown away."""
    assert "Stops On Error" not in _flagged(problems)


def test_an_action_that_is_switched_off_cannot_fail(problems: list[errcheck.Problem]) -> None:
    assert "Switched Off" not in _flagged(problems)


def test_a_read_in_a_disabled_action_is_not_looking(problems: list[errcheck.Problem]) -> None:
    assert "Disabled Reader" in _flagged(problems)


def test_a_read_before_the_action_does_not_cover_it(problems: list[errcheck.Problem]) -> None:
    assert "Read Before" in _flagged(problems)


def test_a_longer_variable_name_is_not_err(problems: list[errcheck.Problem]) -> None:
    """%error_count is the person's own variable."""
    assert "Longer Name" in _flagged(problems)


def test_an_action_that_cannot_be_risky_is_left_alone(problems: list[errcheck.Problem]) -> None:
    """Variable Set with the box ticked is not one of the four kinds."""
    assert "Not Risky" not in _flagged(problems)


def test_one_read_covers_every_risky_action_before_it(problems: list[errcheck.Problem]) -> None:
    """The documented limit: a single %err read after several requests is taken as looking at all of them."""
    assert "Two Reads" not in _flagged(problems)


def test_every_kind_of_risky_action_is_recognised(problems: list[errcheck.Problem]) -> None:
    finding = _finding(problems, "Many")

    for kind in (errcheck.WEB, errcheck.SHELL, errcheck.TASK_CALL, errcheck.FILE_WRITE):
        assert f"({kind})" in finding.detail
    assert finding.where.action == 1
    assert [target.action for target in finding.related] == [2, 3, 4, 5, 6]


def test_only_the_first_few_are_named_and_the_rest_counted(problems: list[errcheck.Problem]) -> None:
    finding = _finding(problems, "Many")

    assert finding.detail.count("(") == errcheck._ACTIONS_NAMED
    assert " and 2 more." in finding.detail
    assert len(finding.related) == 5, "all of them stay one jump away"


def test_the_action_number_is_the_one_the_map_shows(problems: list[errcheck.Problem]) -> None:
    """Tasker writes act0, act1, act10, act2 ... so the file's own order puts act10 second; the Map says 11."""
    assert _finding(problems, "Map Order").where.action == 11


def test_findings_are_warnings(problems: list[errcheck.Problem]) -> None:
    assert {problem.severity for problem in problems} == {errcheck.WARNING}


def test_nothing_loaded_is_nothing_found() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}, "all_projects": {}}

    assert errcheck.lint_problems(state=PrimeItems) == []


# ##################################################################################
# In the Health Check
# ##################################################################################
@pytest.fixture
def report() -> str:
    _load(_FIXTURE)
    rows, _counts = run_health_check(state=PrimeItems)
    return text_report(rows)


def test_the_health_check_reports_it_with_its_note(report: str) -> None:
    lines = [line for line in report.splitlines() if line.startswith("[ERROR-IGNORED]")]

    assert len(lines) == 6, lines
    assert any("Task 'Ignored Request'" in line and "action 1" in line for line in lines)
    assert "NOTE ON IGNORED ERRORS" in report


def test_the_category_is_offered_and_can_be_unticked() -> None:
    assert errcheck.IGNORED_ERROR in {category.tag for category in healthck.all_categories()}
    _load(_FIXTURE)

    rows, _counts = run_health_check(state=PrimeItems, skip=errcheck.TAGS)
    report = text_report(rows)

    assert not [line for line in report.splitlines() if line.startswith("[ERROR-IGNORED]")]
    assert "NOTE ON IGNORED ERRORS" not in report
