"""MapTasker Task test cases (taskcases) Unit Tests

A test case is only worth having if it fails when it should and stays quiet when it should not.  So each kind of
thing a case pins has a pair: change that and the case fails with a sentence that says what moved, change
something it does not pin and it still passes.  The second half matters as much as the first -- a test that fails
when an unrelated action is added above it is one nobody trusts for long.

The Task is built from the Stepper's own small action helpers (test_taskstep's), and "an edit" is the same edit a
person would make: a Flash's text changed, an If's number changed, an action added.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from maptasker.src.analysis import taskcases, taskstep
from maptasker.src.core.primitem import PrimeItems

from tests.shared_fixtures import _load_local
from tests.test_taskstep import _xml, else_, end_if, flash, http, if_, set_, stop

pytestmark = pytest.mark.usefixtures("_runtime")

# T: a number over 3 is "big", otherwise "small"; either way it flashes what it decided, and then asks a web page.
_BRANCHING = (
    if_("%n", 7, "3"),
    set_("%r", "big"),
    flash("big %n"),
    else_(),
    set_("%r", "small"),
    flash("small %n"),
    end_if(),
    http("http://example.com/%r"),
)


def _load(tmp_path: Path, *actions: str, **tasks: tuple[str, ...]) -> None:
    """Load a Task called T made of `actions`, and any others by name."""
    _load_local(tmp_path, _xml(T=actions, **tasks))


def _setup(**variables: str) -> taskcases.Setup:
    return taskcases.Setup(variables=dict(variables))


def _walk(setup: taskcases.Setup, task: str = "T") -> taskstep.Trace:
    trace = taskstep.step_task(task, PrimeItems, setup.options(PrimeItems))
    assert trace is not None
    return trace


def _case(tmp_path: Path, *actions: str, name: str = "big", pins: taskcases.Pins | None = None, **variables: str):
    """Load a Task, run it with these starting variables, and keep the run as a case."""
    _load(tmp_path, *(actions or _BRANCHING))
    setup = _setup(**variables)
    return taskcases.capture(name, "T", setup, _walk(setup), pins)


def _edit(task: str, find: str, replace: str) -> None:
    """Make an edit to a Task in place: text in one of its arguments changed, as the Task editor would."""
    element = PrimeItems.tasker_root_elements["all_tasks_by_name"][task]["xml"]
    changed = 0
    for node in element.iter():
        if node.text and find in node.text:
            node.text = node.text.replace(find, replace)
            changed += 1
    assert changed, f"nothing in Task {task!r} says {find!r}"


# ##################################################################################
# What is kept of a run.
# ##################################################################################


def test_a_case_keeps_the_outcome_what_the_task_changed_and_what_it_does(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")

    assert case.expected.outcome == taskstep.FINISHED
    assert case.expected.variables == {"r": "big"}
    assert case.expected.effects is not None
    assert case.expected.effects[0].startswith("Flash: ")
    assert "big 5" in case.expected.effects[0]
    assert any("example.com/big" in line for line in case.expected.effects)
    assert case.expected.path is None, "the route is only kept when it is asked for"
    assert case.setup.variables == {"n": "5"}
    assert case.saved


def test_the_effects_leave_the_action_numbers_out(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")

    assert case.expected.effects is not None
    assert not any(line[:1].isdigit() for line in case.expected.effects)


def test_a_value_that_depended_on_something_not_simulated_is_not_pinned(tmp_path: Path) -> None:
    """A test of '(unknown)' would pass for the wrong reasons."""
    case = _case(tmp_path, set_("%a", "1"), http("http://example.com/x"), name="unknown")

    assert taskstep.UNKNOWN_TEXT not in case.expected.variables.values()
    assert "a" in case.expected.variables


def test_the_variables_to_keep_can_be_chosen(tmp_path: Path) -> None:
    _load(tmp_path, set_("%a", "1"), set_("%b", "2"), set_("%c", "3"))
    setup = _setup()

    case = taskcases.capture("some", "T", setup, _walk(setup), taskcases.Pins(variables=["b"]))

    assert case.expected.variables == {"b": "2"}


def test_what_the_task_does_and_the_route_can_be_left_out_or_asked_for(tmp_path: Path) -> None:
    _load(tmp_path, *_BRANCHING)
    setup = _setup(n="5")
    trace = _walk(setup)

    quiet = taskcases.capture("quiet", "T", setup, trace, taskcases.Pins(effects=False))
    strict = taskcases.capture("strict", "T", setup, trace, taskcases.Pins(path=True))

    assert quiet.expected.effects is None
    assert strict.expected.path == ["1:taken"]


def test_a_run_that_needed_a_value_cannot_be_kept(tmp_path: Path) -> None:
    _load(tmp_path, *_BRANCHING)
    setup = _setup()

    with pytest.raises(ValueError, match="%n"):
        taskcases.capture("nothing", "T", setup, _walk(setup))


def test_the_setup_is_copied_not_shared(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")

    case.setup.variables["n"] = "99"

    assert _case(tmp_path, n="5").setup.variables == {"n": "5"}


# ##################################################################################
# Running them again.
# ##################################################################################


def test_a_case_passes_against_the_task_it_was_made_from(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.PASSED
    assert result.differences == []
    assert result.trace is not None


def test_a_changed_condition_fails_and_says_which_variable_moved(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")
    _edit("T", "3", "9")  # now 5 > 9 is false, so it is 'small'

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.FAILED
    assert "%r is 'small', where it was expected to be 'big'." in result.differences


def test_a_changed_flash_fails_as_a_change_in_what_the_task_does(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")
    _edit("T", "big %n", "BIG NUMBER %n")

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.FAILED
    assert any("What it does changed: 'Flash: " in line and "BIG NUMBER 5" in line for line in result.differences)
    assert not any(line.startswith("%") for line in result.differences), "no variable moved"


def test_a_web_request_to_somewhere_else_fails(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")
    _edit("T", "example.com", "elsewhere.example.org")

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.FAILED
    assert any("elsewhere.example.org" in line for line in result.differences)


def test_an_effect_that_is_gone_and_one_that_is_new_are_each_said(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")
    element = PrimeItems.tasker_root_elements["all_tasks_by_name"]["T"]["xml"]
    actions = element.findall("Action")
    flash_action = next(action for action in actions if action.findtext("code") == "548")
    element.remove(flash_action)

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.FAILED
    assert any(line.startswith("What it does no longer happens: 'Flash: ") for line in result.differences)


def test_an_unrelated_action_added_above_does_not_fail_it(tmp_path: Path) -> None:
    """The point of leaving the numbers out: a refactor is not a regression."""
    case = _case(tmp_path, n="5")
    _load(tmp_path, set_("%unrelated", "1"), *_BRANCHING)

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.PASSED, result.differences


def test_the_route_is_only_held_when_asked_for(tmp_path: Path) -> None:
    pinned = _case(tmp_path, n="5", name="pinned", pins=taskcases.Pins(path=True))
    free = _case(tmp_path, n="5", name="free")
    _load(tmp_path, set_("%unrelated", "1"), *_BRANCHING)  # the If moves from action 1 to action 2

    assert taskcases.run_case(free, PrimeItems).status == taskcases.PASSED
    result = taskcases.run_case(pinned, PrimeItems)
    assert result.status == taskcases.FAILED
    assert any(line.startswith("The route") for line in result.differences)


def test_a_different_ending_fails(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")
    _load(tmp_path, *_BRANCHING[:2], stop())

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.FAILED
    assert any(line.startswith("It stopped, where it was expected to be finished.") for line in result.differences)


def test_a_variable_that_is_no_longer_set_says_so(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")
    _load(tmp_path, flash("nothing happens to r"))

    result = taskcases.run_case(case, PrimeItems)

    assert "%r is not set, where it was expected to be 'big'." in result.differences


def test_a_variable_that_can_no_longer_be_worked_out_says_so(tmp_path: Path) -> None:
    case = _case(tmp_path, set_("%a", "1"), name="known")
    _load(tmp_path, http("http://example.com/x"), set_("%a", "%http_data"))

    result = taskcases.run_case(case, PrimeItems)

    assert any(line.startswith("%a ") for line in result.differences)


def test_a_case_for_a_task_that_is_not_in_the_file_is_not_a_failure(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5")
    _load_local(tmp_path, _xml(Other=(flash("hello"),)))

    result = taskcases.run_case(case, PrimeItems)

    assert result.status == taskcases.MISSING
    assert result.differences == ["Task 'T' is not in the file that is open."]
    assert taskcases.failing([result]) == []


def test_the_globals_saved_in_the_backup_are_part_of_what_a_case_runs_with(tmp_path: Path) -> None:
    xml = _xml(T=(set_("%r", "%Mode"),)).replace(
        "</TaskerData>", '<Variable sr="vars0"><n>%Mode</n><v>home</v></Variable></TaskerData>'
    )
    _load_local(tmp_path, xml)
    setup = taskcases.Setup(use_globals=True)
    case = taskcases.capture("globals", "T", setup, _walk(setup))
    assert case.expected.variables["r"] == "home"

    _load_local(tmp_path, xml.replace(">home<", ">away<"))

    result = taskcases.run_case(case, PrimeItems)
    assert result.status == taskcases.FAILED
    assert "%r is 'away', where it was expected to be 'home'." in result.differences


def test_a_case_that_does_not_use_the_globals_is_not_moved_by_them(tmp_path: Path) -> None:
    xml = _xml(T=(set_("%r", "%Mode"),)).replace(
        "</TaskerData>", '<Variable sr="vars0"><n>%Mode</n><v>home</v></Variable></TaskerData>'
    )
    _load_local(tmp_path, xml)
    setup = taskcases.Setup(use_globals=False, policy=taskstep.POLICY_UNSET)

    case = taskcases.capture("no globals", "T", setup, _walk(setup))
    _load_local(tmp_path, xml.replace(">home<", ">away<"))

    assert taskcases.run_case(case, PrimeItems).status == taskcases.PASSED


def test_a_typed_value_wins_over_a_global_of_the_same_name(tmp_path: Path) -> None:
    _load_local(
        tmp_path, _xml(T=(flash("x"),)).replace("</TaskerData>", "<Variable><n>%A</n><v>1</v></Variable></TaskerData>")
    )

    options = taskcases.Setup(variables={"A": "2"}).options(PrimeItems)

    assert options.variables["A"] == "2"


def test_what_an_action_not_simulated_leaves_is_part_of_the_case(tmp_path: Path) -> None:
    _load(
        tmp_path,
        http("http://example.com/x"),
        if_("%http_data", 0, "ok"),
        set_("%r", "good"),
        else_(),
        set_("%r", "bad"),
        end_if(),
    )
    setup = taskcases.Setup(assumed={1: {"http_data": "ok"}})

    case = taskcases.capture("assumed", "T", setup, _walk(setup))

    assert case.expected.variables["r"] == "good"
    assert taskcases.run_case(case, PrimeItems).status == taskcases.PASSED


# ##################################################################################
# Counting and reporting.
# ##################################################################################


def test_counts_failing_and_the_report(tmp_path: Path) -> None:
    good = _case(tmp_path, n="5", name="good")
    bad = _case(tmp_path, n="5", name="bad")
    gone = taskcases.Case(name="elsewhere", task="Nowhere", setup=_setup(), expected=taskcases.Expected())
    _edit("T", "big %n", "changed %n")
    book = taskcases.CaseBook(cases=[good, bad, gone])

    results = taskcases.run_all(book, PrimeItems)

    assert [result.status for result in results] == [taskcases.FAILED, taskcases.FAILED, taskcases.MISSING]
    assert taskcases.counts(results) == (0, 2, 1)
    assert [result.case.name for result in taskcases.failing(results)] == ["good", "bad"]
    text = taskcases.report(results)
    assert text.startswith("Task tests: 3 run -- 0 passed, 2 failed, 1 not in this file.")
    assert "[FAILED] good  (Task 'T')" in text
    assert "[NOT IN THIS FILE] elsewhere  (Task 'Nowhere')" in text


def test_a_long_list_of_differences_is_cut_and_counted(tmp_path: Path) -> None:
    flashes = tuple(flash(f"line {number}") for number in range(12))
    _load(tmp_path, *flashes)
    setup = _setup()
    case = taskcases.capture("many", "T", setup, _walk(setup))
    _load(tmp_path, *(flash(f"other {number}") for number in range(12)))

    result = taskcases.run_case(case, PrimeItems)

    assert len(result.differences) == 7
    assert result.differences[-1] == "... and 6 more What it does differences"


# ##################################################################################
# Keeping them.
# ##################################################################################


def test_the_book_replaces_a_case_of_the_same_name_and_drops_one_by_name() -> None:
    book = taskcases.CaseBook()
    first = taskcases.Case(name="one", task="T")

    assert book.put(first) is False
    assert book.put(taskcases.Case(name="one", task="U")) is True
    assert [case.task for case in book.cases] == ["U"]
    assert book.get("one") is not None and book.get("two") is None
    assert book.remove("one") is True and book.remove("one") is False
    assert book.cases == []


def test_the_book_finds_a_task_s_cases_and_a_name_nothing_has(tmp_path: Path) -> None:
    book = taskcases.CaseBook(
        cases=[
            taskcases.Case(name="a", task="T"),
            taskcases.Case(name="a 2", task="U"),
            taskcases.Case(name="b", task="T"),
        ]
    )

    assert book.unused_name("a") == "a 3"
    assert book.unused_name("fresh") == "fresh"


def test_the_book_survives_being_saved_and_read_again(tmp_path: Path) -> None:
    case = _case(tmp_path, n="5", pins=taskcases.Pins(path=True))
    case.setup.assumed = {3: {"x": "1", "y": "2"}}
    case.setup.policy = taskstep.POLICY_UNSET
    case.setup.use_globals = False
    case.note = "the happy path"
    book = taskcases.CaseBook(cases=[case], after_edit=False)
    where = str(tmp_path / "tests.json")

    assert taskcases.save_book(book, where) == ""
    loaded, unreadable = taskcases.load_book(where)

    assert unreadable == 0
    assert loaded.after_edit is False
    assert loaded.cases == [case]


def test_a_missing_file_is_an_empty_book(tmp_path: Path) -> None:
    book, unreadable = taskcases.load_book(str(tmp_path / "nothing.json"))

    assert (book.cases, book.after_edit, unreadable) == ([], True, 0)


def test_a_file_that_is_not_json_is_an_empty_book_and_says_so(tmp_path: Path) -> None:
    where = tmp_path / "tests.json"
    where.write_text("this is not json", encoding="utf-8")

    book, unreadable = taskcases.load_book(str(where))

    assert (book.cases, unreadable) == ([], 1)


def test_entries_that_are_not_cases_are_counted_and_the_rest_kept(tmp_path: Path) -> None:
    where = tmp_path / "tests.json"
    where.write_text(
        json.dumps({"cases": [{"name": "ok", "task": "T"}, {"name": "no task"}, "junk", {"task": "T"}]}),
        encoding="utf-8",
    )

    book, unreadable = taskcases.load_book(str(where))

    assert [case.name for case in book.cases] == ["ok"]
    assert unreadable == 3


def test_a_case_read_with_missing_fields_gets_the_defaults(tmp_path: Path) -> None:
    where = tmp_path / "tests.json"
    where.write_text(
        json.dumps({"cases": [{"name": "bare", "task": "T", "setup": {"policy": "nonsense"}}]}), encoding="utf-8"
    )

    (case,) = taskcases.load_book(str(where))[0].cases

    assert case.setup.policy == taskstep.POLICY_STOP
    assert case.setup.follow_calls is True and case.setup.use_globals is True
    assert case.expected.outcome == taskstep.FINISHED
    assert case.expected.effects is None and case.expected.path is None


def test_a_book_that_cannot_be_written_says_why(tmp_path: Path) -> None:
    message = taskcases.save_book(taskcases.CaseBook(), str(tmp_path / "no such folder" / "tests.json"))

    assert message


def test_the_book_lives_in_the_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert Path(taskcases.book_path()) == tmp_path / "MapTasker_TaskTests.json"
    assert taskcases.save_book(taskcases.CaseBook(cases=[taskcases.Case(name="n", task="T")])) == ""
    assert [case.name for case in taskcases.load_book()[0].cases] == ["n"]


# ##################################################################################
# The Stepper's boxes, written back.
# ##################################################################################


def test_starting_variables_and_assumptions_can_be_put_back_in_their_boxes() -> None:
    values = {"n": "5", "text": "a = b"}
    assumed = {3: {"x": "1"}, 5: {"y": "2", "z": "3"}}

    assert taskstep.parse_assignments(taskstep.format_assignments(values))[0] == values
    assert taskstep.parse_assumed(taskstep.format_assumed(assumed))[0] == assumed
