"""MapTasker Task Stepper (taskstep) Unit Tests

A dry run is trusted, so what is tested is that it does what Tasker does -- and that where it cannot know, it says so
instead of choosing.

THE PATH.  Every branch construct has a test for each way through it: an If taken and not taken, an Else If chain,
a For over a range, a list, nothing and a loop inside a loop, each kind of Goto, a Stop that ends the Task and one that
stops another and carries on.  Each asserts the line the trace shows as well as where the walk went, because the lines
are what the user reads.

THE VARIABLES.  Set with maths, append and recursion, Add with wrap-around, Clear, Split and the %array forms -- and a
variable that has no value is left written out, as Tasker does.

WHAT IT CANNOT KNOW.  A condition that depends on a variable with no value stops the walk and names the variable; the
other three policies each do their own thing and say so against the step.  An action that is not simulated marks what it
may have written as unknown, and a condition on that stops the same way.

The Task is built from small action helpers, so each test reads as the Task it is about.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src.analysis import taskstep
from maptasker.src.core.primitem import PrimeItems

from tests.test_tnupdate import _load_local, _runtime  # noqa: F401  (_runtime is the fixture)

# ##################################################################################
# Building Tasks.
# ##################################################################################


def _act(code: str, *arguments: str, extra: str = "") -> str:
    return f'<Action sr="act{{}}" ve="7"><code>{code}</code>{"".join(arguments)}{extra}</Action>'


def _s(index: int, value: str) -> str:
    return f'<Str sr="arg{index}" ve="3">{value}</Str>'


def _i(index: int, value: int | str) -> str:
    return f'<Int sr="arg{index}" val="{value}"/>'


def _cond(
    lhs: str, op: int, rhs: str = "", *, more: tuple[tuple[str, int, str], ...] = (), joiners: tuple[str, ...] = ()
) -> str:
    conditions = [(lhs, op, rhs), *more]
    body = "".join(
        f'<Condition sr="c{n}" ve="3"><lhs>{left}</lhs><op>{operator}</op><rhs>{right}</rhs></Condition>'
        + (f"<bool{n}>{joiners[n]}</bool{n}>" if n < len(joiners) else "")
        for n, (left, operator, right) in enumerate(conditions)
    )
    return f'<ConditionList sr="if">{body}</ConditionList>'


def set_(
    name: str, value: str, *, maths: bool = False, append: bool = False, recurse: bool = False, own: str = ""
) -> str:
    return _act(
        "547",
        _s(0, name),
        _s(1, value),
        _i(2, int(recurse)),
        _i(3, int(maths)),
        _i(4, int(append)),
        _i(5, 3),
        extra=own,
    )


def add(name: str, value: str, wrap: int = 0) -> str:
    return _act("888", _s(0, name), _s(1, value), _i(2, wrap))


def if_(lhs: str, op: int, rhs: str = "", **kwargs: object) -> str:
    return _act("37", extra=_cond(lhs, op, rhs, **kwargs))


def else_if(lhs: str, op: int, rhs: str = "") -> str:
    return _act("43", extra=_cond(lhs, op, rhs))


def else_() -> str:
    return _act("43")


def end_if() -> str:
    return _act("38")


def for_(variable: str, items: str) -> str:
    return _act("39", _s(0, variable), _s(1, items), _i(2, 0))


def end_for() -> str:
    return _act("40")


def goto_number(number: int) -> str:
    return _act("135", _i(0, 0), _i(1, number), _s(2, ""))


def goto_label(label: str) -> str:
    return _act("135", _i(0, 1), _i(1, 0), _s(2, label))


def goto_block(kind: int) -> str:
    return _act("135", _i(0, kind), _i(1, 0), _s(2, ""))


def stop(task: str = "") -> str:
    return _act("137", _i(0, 0), _s(1, task))


def return_(value: str) -> str:
    return _act("126", _s(0, value), _i(1, 1), _i(2, 0), _i(3, 0))


def flash(text: str, *, own: str = "") -> str:
    return _act("548", _s(0, text), _i(1, 0), _i(2, 0), extra=own)


def http(url: str) -> str:
    return _act("339", _s(2, url))


def labelled(action: str, label: str) -> str:
    return action.replace("</Action>", f"<label>{label}</label></Action>")


def disabled(action: str) -> str:
    return action.replace("</Action>", "<on>false</on></Action>")


def _xml(**tasks: tuple[str, ...]) -> str:
    body = ""
    for number, (name, actions) in enumerate(tasks.items(), start=1):
        numbered = "".join(action.replace("act{}", f"act{index}") for index, action in enumerate(actions))
        body += f'<Task sr="task{number}" ve="2"><id>{number}</id><nme>{name.replace("_", " ")}</nme>{numbered}</Task>'
    return f'<TaskerData sr="" dvi="1" tv="6.3.13">{body}</TaskerData>'


def walk(tmp_path: Path, *actions: str, **options: object) -> taskstep.Trace:
    """Load a Task made of `actions`, called 'T', and dry-run it."""
    _load_local(tmp_path, _xml(T=actions))
    trace = taskstep.step_task("T", PrimeItems, taskstep.Options(**options))
    assert trace is not None
    return trace


def lines(trace: taskstep.Trace) -> list[tuple[int, str]]:
    """(action number, status) for every step, in the order the walk met them."""
    return [(step.number, step.status) for step in trace.steps]


def value(trace: taskstep.Trace, name: str) -> str:
    return trace.variables.get(name, "")


# ##################################################################################
# If, Else If, Else.
# ##################################################################################


def test_an_if_that_holds_runs_its_body_and_skips_the_else(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        if_("%n", 7, "3"),
        set_("%r", "big"),
        else_(),
        set_("%r", "small"),
        end_if(),
        variables={"n": "5"},
    )

    assert value(trace, "r") == "big"
    assert lines(trace) == [(1, taskstep.TAKEN), (2, taskstep.RAN)]
    assert "5 > 3 -> true" in trace.steps[0].text
    assert trace.not_reached == [3, 4]
    assert trace.outcome == taskstep.FINISHED


def test_an_if_that_fails_goes_to_the_else(tmp_path: Path) -> None:
    trace = walk(
        tmp_path, if_("%n", 7, "3"), set_("%r", "big"), else_(), set_("%r", "small"), end_if(), variables={"n": "1"}
    )

    assert value(trace, "r") == "small"
    assert lines(trace) == [(1, taskstep.NOT_TAKEN), (3, taskstep.TAKEN), (4, taskstep.RAN)]
    assert "goes to the Else at action 3" in trace.steps[0].detail
    assert trace.not_reached == [2]


def test_an_if_with_no_else_that_fails_skips_to_after_the_end_if(tmp_path: Path) -> None:
    trace = walk(tmp_path, if_("%n", 7, "3"), set_("%r", "big"), end_if(), set_("%after", "yes"), variables={"n": "1"})

    assert value(trace, "r") == ""
    assert value(trace, "after") == "yes"
    assert lines(trace) == [(1, taskstep.NOT_TAKEN), (4, taskstep.RAN)]


def test_an_else_if_chain_takes_the_first_branch_that_holds_and_shows_the_ones_passed(tmp_path: Path) -> None:
    actions = (
        if_("%n", 0, "1"),
        set_("%r", "one"),
        else_if("%n", 0, "2"),
        set_("%r", "two"),
        else_if("%n", 0, "3"),
        set_("%r", "three"),
        else_(),
        set_("%r", "other"),
        end_if(),
    )

    trace = walk(tmp_path, *actions, variables={"n": "3"})

    assert value(trace, "r") == "three"
    assert lines(trace) == [(1, taskstep.NOT_TAKEN), (3, taskstep.NOT_TAKEN), (5, taskstep.TAKEN), (6, taskstep.RAN)]
    assert trace.steps[1].text.startswith("Else If"), "the Else Ifs it passed are lines of their own, after the If"
    assert trace.not_reached == [2, 4, 7, 8]


def test_running_off_the_end_of_a_branch_skips_the_other_branches(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        if_("%n", 0, "1"),
        set_("%r", "a"),
        else_if("%n", 0, "1"),
        set_("%r", "b"),
        else_(),
        set_("%r", "c"),
        end_if(),
        variables={"n": "1"},
    )

    assert value(trace, "r") == "a", "the first true branch runs and the later ones are not even tried"
    assert lines(trace) == [(1, taskstep.TAKEN), (2, taskstep.RAN)]


def test_nested_ifs(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        if_("%a", 0, "1"),
        if_("%b", 0, "1"),
        set_("%r", "both"),
        else_(),
        set_("%r", "only a"),
        end_if(),
        else_(),
        set_("%r", "neither"),
        end_if(),
        variables={"a": "1", "b": "0"},
    )

    assert value(trace, "r") == "only a"


def test_an_action_with_its_own_if_is_skipped_when_it_is_false_and_says_why(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%r", "x", own=_cond("%n", 0, "9")), set_("%s", "y"), variables={"n": "1"})

    assert value(trace, "r") == ""
    assert value(trace, "s") == "y"
    assert lines(trace) == [(1, taskstep.SKIPPED), (2, taskstep.RAN)]
    assert "its If is false" in trace.steps[0].detail


def test_a_disabled_action_is_stepped_over(tmp_path: Path) -> None:
    trace = walk(tmp_path, disabled(set_("%r", "x")), set_("%s", "y"))

    assert value(trace, "r") == ""
    assert lines(trace) == [(1, taskstep.DISABLED), (2, taskstep.RAN)]
    assert 1 not in trace.not_reached, "it is not a branch that did not run, it is off"


# ##################################################################################
# Conditions.
# ##################################################################################


@pytest.mark.parametrize(
    ("op", "left", "right", "expected"),
    [
        (0, "5", "5.0", True),  # two numbers are compared as numbers
        (0, "abc", "abc", True),
        (0, "abc", "ABC", False),
        (1, "a", "b", True),
        (2, "Hello World", "hello*", True),  # Matches: a pattern, ignoring case
        (2, "Hello", "h?llo", True),
        (3, "Hello", "x*", True),
        (4, "abc123", "[a-z]+[0-9]+", True),  # Matches Regex: the whole value
        (4, "abc123", "[a-z]+", False),
        (5, "abc123", "[a-z]+", True),
        (6, "2", "10", True),  # numbers, not text
        (7, "10", "2", True),
        (8, "1.0", "1", True),
        (9, "1", "2", True),
    ],
)
def test_each_operator_decides_as_tasker_does(tmp_path: Path, op: int, left: str, right: str, expected: bool) -> None:
    trace = walk(tmp_path, if_(left, op, right), set_("%r", "yes"), else_(), set_("%r", "no"), end_if())

    assert value(trace, "r") == ("yes" if expected else "no")


def test_is_set_and_is_not_set(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        if_("%given", 12),
        set_("%a", "set"),
        end_if(),
        if_("%empty", 13),
        set_("%b", "unset"),
        end_if(),
        variables={"given": "x", "empty": ""},
    )

    assert value(trace, "a") == "set"
    assert value(trace, "b") == "unset", "an empty variable is not set"


def test_conditions_are_joined_by_taskers_precedence(tmp_path: Path) -> None:
    """'A | B & C | D' is '(A | B) & (C | D)': Or binds tighter than And."""
    trace = walk(
        tmp_path,
        if_("%a", 0, "1", more=(("%b", 0, "1"), ("%c", 0, "1"), ("%d", 0, "1")), joiners=("Or", "And", "Or")),
        set_("%r", "yes"),
        else_(),
        set_("%r", "no"),
        end_if(),
        variables={"a": "0", "b": "1", "c": "1", "d": "0"},
    )

    assert value(trace, "r") == "yes"


@pytest.mark.parametrize(
    ("values", "joiners", "expected"),
    [
        ([True, False], ["and"], False),
        ([True, False], ["or"], True),
        ([True, True], ["xor"], False),
        ([True, False], ["xor"], True),
        ([None, False], ["and"], False),  # one false decides an And whatever the rest are
        ([None, True], ["and"], None),
        ([None, True], ["or"], True),
        ([None, False], ["or"], None),
        ([None, True], ["xor"], None),
        ([False, True, False], ["and", "or"], False),
    ],
)
def test_joining_three_valued(values: list, joiners: list, expected: bool | None) -> None:
    assert taskstep._join(values, joiners) is expected  # noqa: SLF001


# ##################################################################################
# Variables.
# ##################################################################################


def test_variable_set_fills_in_variables_and_leaves_an_unset_one_written_out(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%greeting", "Hello %who, %missing"), variables={"who": "Ann"})

    assert value(trace, "greeting") == "Hello Ann, %missing"


def test_variable_set_with_maths_rounds_and_formats(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        set_("%a", "%n * 2 + 1", maths=True),
        set_("%b", "10 / 4", maths=True),
        set_("%c", "1/3", maths=True),
        variables={"n": "4"},
    )

    assert (value(trace, "a"), value(trace, "b"), value(trace, "c")) == ("9", "2.5", "0.333")


def test_do_maths_on_something_that_is_not_arithmetic_leaves_it_and_says_so(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%a", "hello", maths=True))

    assert value(trace, "a") == "hello"
    assert "could not read this as arithmetic" in trace.steps[0].detail


def test_variable_set_append_and_recurse(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        set_("%list", "a"),
        set_("%list", ",b", append=True),
        set_("%name", "list"),
        set_("%indirect", "%%name", recurse=True),
    )

    assert value(trace, "list") == "a,b"
    assert value(trace, "indirect") == "a,b", "the %name inside was filled in, and then the %list that gave"


def test_variable_add_counts_from_nothing_and_wraps_round(tmp_path: Path) -> None:
    trace = walk(tmp_path, add("%n", "1"), add("%n", "1"), add("%w", "7", wrap=5), add("%x", "%n"))

    assert value(trace, "n") == "2"
    assert value(trace, "w") == "2"
    assert value(trace, "x") == "2"


def test_variable_clear_one_by_pattern_and_all(tmp_path: Path) -> None:
    clear_one = _act("549", _s(0, "%a"), _i(1, 0), _i(2, 0), _i(3, 0))
    clear_pattern = _act("549", _s(0, "tmp*"), _i(1, 1), _i(2, 0), _i(3, 0))
    clear_all = _act("549", _s(0, ""), _i(1, 0), _i(2, 0), _i(3, 1))

    one = walk(tmp_path, clear_one, variables={"a": "1", "b": "2"})
    pattern = walk(tmp_path, clear_pattern, variables={"tmp1": "1", "tmp2": "2", "keep": "3"})
    everything = walk(tmp_path, clear_all, variables={"a": "1", "b": "2"})

    assert one.variables == {"b": "2"}
    assert pattern.variables == {"keep": "3"}
    assert everything.variables == {}


def test_the_array_forms(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        set_("%count", "%arr(#)"),
        set_("%second", "%arr(2)"),
        set_("%all", "%arr()"),
        set_("%beyond", "%arr(9)"),
        variables={"arr1": "x", "arr2": "y", "arr3": "z"},
    )

    assert (value(trace, "count"), value(trace, "second"), value(trace, "all")) == ("3", "y", "x,y,z")
    assert value(trace, "beyond") == "%arr(9)", "an element that is not there is left written out"


def test_variable_split_makes_an_array_a_loop_can_walk(tmp_path: Path) -> None:
    split = _act("590", _s(0, "%csv"), _s(1, ","), _i(2, 1), _i(3, 0))

    trace = walk(
        tmp_path,
        split,
        for_("%p", "%csv()"),
        add("%n", "1"),
        set_("%seen", "%p", append=True),
        end_for(),
        variables={"csv": "a,b,c"},
    )

    assert value(trace, "csv1") == "a"
    assert "csv" not in trace.variables, "Delete Base removed the original"
    assert value(trace, "n") == "3"
    assert value(trace, "seen") == "abc"


def test_each_step_shows_what_changed_and_what_the_variables_held_after(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%a", "1"), set_("%a", "2"), variables={"b": "x"})

    assert [(c.name, c.before, c.after) for c in trace.steps[0].changes] == [("a", "", "1")]
    assert [(c.name, c.before, c.after) for c in trace.steps[1].changes] == [("a", "1", "2")]
    assert trace.steps[1].variables == {"a": "2", "b": "x"}


# ##################################################################################
# For.
# ##################################################################################


def test_for_over_a_range_runs_the_body_once_per_item(tmp_path: Path) -> None:
    trace = walk(tmp_path, for_("%i", "1:3"), add("%sum", "%i"), end_for(), set_("%done", "yes"))

    assert value(trace, "sum") == "6"
    assert value(trace, "i") == "3"
    assert value(trace, "done") == "yes"
    assert [step.text for step in trace.steps if step.name == "For"][:3] == [
        "For %i = '1'",
        "For %i = '2'",
        "For %i = '3'",
    ]
    assert any("no more items" in step.detail for step in trace.steps)


def test_for_over_a_descending_range_and_a_list(tmp_path: Path) -> None:
    down = walk(tmp_path, for_("%i", "3:1"), set_("%s", "%i", append=True), end_for())
    listed = walk(tmp_path, for_("%w", "red, green,blue"), set_("%s", "%w,", append=True), end_for())

    assert value(down, "s") == "321"
    assert value(listed, "s") == "red,green,blue,"


def test_for_over_nothing_skips_the_body(tmp_path: Path) -> None:
    trace = walk(
        tmp_path, for_("%i", "%empty"), set_("%ran", "yes"), end_for(), set_("%after", "yes"), variables={"empty": ""}
    )

    assert value(trace, "ran") == ""
    assert value(trace, "after") == "yes"


def test_a_loop_inside_a_loop_starts_again_each_time_round(tmp_path: Path) -> None:
    trace = walk(tmp_path, for_("%a", "1:2"), for_("%b", "1:3"), add("%n", "1"), end_for(), end_for())

    assert value(trace, "n") == "6"


def test_goto_top_of_loop_goes_to_the_next_item(tmp_path: Path) -> None:
    """'Continue': skip the rest of this item."""
    trace = walk(
        tmp_path,
        for_("%i", "1:4"),
        if_("%i", 0, "2"),
        goto_block(2),
        end_if(),
        set_("%seen", "%i", append=True),
        end_for(),
    )

    assert value(trace, "seen") == "134"


# ##################################################################################
# Goto, Stop, Return, and a Task that never ends.
# ##################################################################################


def test_goto_by_number(tmp_path: Path) -> None:
    trace = walk(tmp_path, goto_number(3), set_("%skipped", "yes"), set_("%r", "landed"))

    assert value(trace, "skipped") == ""
    assert value(trace, "r") == "landed"
    assert trace.steps[0].detail == "jumps to action 3"
    assert trace.not_reached == [2]


def test_goto_by_label(tmp_path: Path) -> None:
    trace = walk(tmp_path, goto_label("End"), set_("%skipped", "yes"), labelled(set_("%r", "landed"), "End"))

    assert value(trace, "r") == "landed"
    assert value(trace, "skipped") == ""


def test_goto_whose_number_is_a_variable_is_resolved_with_its_value(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        _act("135", _i(0, 0), _s(1, "%where"), _s(2, "")),
        set_("%skipped", "yes"),
        set_("%r", "landed"),
        variables={"where": "3"},
    )

    assert value(trace, "r") == "landed"
    assert value(trace, "skipped") == ""


def test_a_goto_that_lands_nowhere_carries_on(tmp_path: Path) -> None:
    trace = walk(tmp_path, goto_label("Nowhere"), set_("%r", "next"))

    assert value(trace, "r") == "next"
    assert trace.steps[0].status == taskstep.NOT_TAKEN


def test_a_conditional_goto_only_jumps_when_its_if_holds(tmp_path: Path) -> None:
    jump = _act("135", _i(0, 0), _i(1, 3), _s(2, ""), extra=_cond("%n", 0, "1"))

    held = walk(tmp_path, jump, set_("%skipped", "yes"), set_("%r", "landed"), variables={"n": "1"})
    failed = walk(tmp_path, jump, set_("%skipped", "yes"), set_("%r", "landed"), variables={"n": "2"})

    assert value(held, "skipped") == ""
    assert value(failed, "skipped") == "yes"


def test_a_task_that_goes_round_forever_is_cut_off_and_says_so(tmp_path: Path) -> None:
    trace = walk(tmp_path, add("%n", "1"), goto_number(1), max_steps=50)

    assert trace.outcome == taskstep.STEP_LIMIT
    assert "50" in trace.message
    assert len(trace.steps) == 50


def test_stop_ends_the_task(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%a", "1"), stop(), set_("%b", "2"))

    assert trace.outcome == taskstep.STOPPED
    assert value(trace, "b") == ""
    assert trace.not_reached == [3]


def test_stop_that_names_another_task_stops_that_one_and_carries_on(tmp_path: Path) -> None:
    trace = walk(tmp_path, stop("Some Other Task"), set_("%b", "2"))

    assert trace.outcome == taskstep.FINISHED
    assert value(trace, "b") == "2"


def test_return_ends_the_task_with_its_value(tmp_path: Path) -> None:
    trace = walk(tmp_path, return_("got %n"), set_("%b", "2"), variables={"n": "5"})

    assert trace.outcome == taskstep.RETURNED
    assert "Returned 'got 5'" in trace.message


def test_an_empty_task_just_finishes(tmp_path: Path) -> None:
    trace = walk(tmp_path)

    assert trace.outcome == taskstep.FINISHED
    assert trace.steps == []


# ##################################################################################
# What it cannot know.
# ##################################################################################


def test_a_condition_on_a_variable_with_no_value_stops_the_walk_and_names_it(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%a", "1"), if_("%mystery", 0, "5"), set_("%b", "2"), end_if())

    assert trace.outcome == taskstep.NEEDS_VALUE
    assert trace.needed == ["mystery"]
    assert "%mystery" in trace.message
    assert trace.steps[-1].status == taskstep.UNDECIDED
    assert value(trace, "b") == ""


def test_the_unset_policy_treats_a_missing_variable_as_not_set(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        if_("%mystery", 13),
        set_("%r", "was unset"),
        else_(),
        set_("%r", "was set"),
        end_if(),
        policy=taskstep.POLICY_UNSET,
    )

    assert value(trace, "r") == "was unset"
    assert trace.outcome == taskstep.FINISHED


@pytest.mark.parametrize(("policy", "expected"), [(taskstep.POLICY_TRUE, "yes"), (taskstep.POLICY_FALSE, "no")])
def test_assuming_a_condition_says_so_against_the_step(tmp_path: Path, policy: str, expected: str) -> None:
    trace = walk(
        tmp_path, if_("%mystery", 0, "5"), set_("%r", "yes"), else_(), set_("%r", "no"), end_if(), policy=policy
    )

    assert value(trace, "r") == expected
    assert f"assumed {policy}" in trace.steps[0].text
    assert "mystery" in trace.needed, "and what it was missing is still reported"


def test_an_action_that_is_not_simulated_marks_what_it_writes_as_unknown_and_a_condition_on_it_stops(
    tmp_path: Path,
) -> None:
    trace = walk(
        tmp_path, http("https://example.com"), if_("%http_response_code", 0, "200"), set_("%ok", "yes"), end_if()
    )

    assert trace.steps[0].status == taskstep.NOT_SIMULATED
    assert "%http_data" in trace.steps[0].detail
    assert trace.outcome == taskstep.NEEDS_VALUE
    assert trace.needed == ["http_response_code"]
    assert trace.variables["http_data"] == taskstep.UNKNOWN_TEXT


def test_the_user_can_say_what_an_unsimulated_action_leaves_and_the_walk_goes_on(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        http("https://example.com"),
        if_("%http_response_code", 0, "200"),
        set_("%ok", "yes"),
        end_if(),
        assumed={1: {"%http_response_code": "200"}},
    )

    assert trace.steps[0].status == taskstep.ASSUMED
    assert "you said it leaves %http_response_code = '200'" in trace.steps[0].detail
    assert value(trace, "ok") == "yes"


def test_an_action_naming_where_its_output_goes_marks_that_variable(tmp_path: Path) -> None:
    shell = _act("123", _s(0, "ls"), _s(3, "%files"), _s(5, "%rc"))

    trace = walk(tmp_path, shell)

    assert {"files", "rc"} <= set(trace.variables)


def test_a_javascriptlet_warns_that_it_may_have_changed_anything(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%a", "1"), _act("129", _s(0, "var x = 1;")))

    assert trace.steps[1].status == taskstep.NOT_SIMULATED
    assert "may have changed any variable" in trace.steps[1].detail
    assert value(trace, "a") == "1", "and the walk carries on assuming it did not"


def test_perform_task_is_not_entered_and_its_return_value_is_unknown(tmp_path: Path) -> None:
    perform = _act("130", _s(0, "Other"), _i(1, 5), _s(2, ""), _s(3, ""), _s(4, "%answer"))

    trace = walk(tmp_path, perform, if_("%answer", 0, "42"), set_("%r", "x"), end_if())

    assert trace.steps[0].status == taskstep.NOT_SIMULATED
    assert trace.outcome == taskstep.NEEDS_VALUE
    assert trace.needed == ["answer"]


def test_flash_and_the_like_show_what_they_would_say_with_the_variables_filled_in(tmp_path: Path) -> None:
    trace = walk(tmp_path, flash("Hello %who"), variables={"who": "Ann"})

    assert trace.steps[0].status == taskstep.RAN
    assert "Hello Ann" in trace.steps[0].text
    assert trace.steps[0].detail == "shown, not performed"


def test_a_value_is_never_given_to_a_variable_the_walk_does_not_know(tmp_path: Path) -> None:
    trace = walk(tmp_path, set_("%copy", "%mystery"))

    assert value(trace, "copy") == "%mystery", "left written out, as Tasker leaves it -- not made up"


# ##################################################################################
# Maths.
# ##################################################################################


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1+2*3", 7),
        ("(1+2)*3", 9),
        ("10/4", 2.5),
        ("7%3", 1),
        ("-5+2", -3),
        ("2**10", 1024),
        ("sqrt(16)", 4),
        ("max(1,5,3)", 5),
        ("round(2.6)", 3),
        ("abs(-2)", 2),
    ],
)
def test_arithmetic(expression: str, expected: float) -> None:
    assert taskstep.calculate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "hello",
        "1+",
        "__import__('os')",
        "(1).real",
        "[1,2]",
        "1/0",
        "2**1000",
        "open('x')",
        "True",
        "x+1",
        "sqrt(1)(2)",
    ],
)
def test_anything_that_is_not_arithmetic_is_refused_not_evaluated(expression: str) -> None:
    assert taskstep.calculate(expression) is None


@pytest.mark.parametrize(
    ("number", "text"), [(9.0, "9"), (2.5, "2.5"), (1 / 3, "0.333"), (2.0004, "2"), (-1.5, "-1.5")]
)
def test_numbers_are_written_as_tasker_writes_them(number: float, text: str) -> None:
    assert taskstep._format(number) == text  # noqa: SLF001


# ##################################################################################
# Asking.
# ##################################################################################


def test_a_task_is_found_by_name_or_by_id_and_an_unknown_one_is_none(tmp_path: Path) -> None:
    _load_local(tmp_path, _xml(First=(set_("%a", "1"),), Second=(set_("%a", "2"),)))

    by_name = taskstep.step_task("Second", PrimeItems)
    by_id = taskstep.step_task("1", PrimeItems)

    assert by_name is not None and by_name.variables == {"a": "2"}
    assert by_id is not None and by_id.task == "First"
    assert taskstep.step_task("Nothing", PrimeItems) is None


def test_the_inputs_a_task_needs_are_what_it_reads_before_it_sets(tmp_path: Path) -> None:
    _load_local(
        tmp_path,
        _xml(
            T=(
                set_("%a", "%par1"),
                if_("%a", 0, "%limit"),
                set_("%b", "%a %b"),
                end_if(),
                for_("%i", "1:%count"),
                end_for(),
                set_("%z", "%i"),
            )
        ),
    )

    assert taskstep.inputs_needed("T", PrimeItems) == ["par1", "limit", "b", "count"], (
        "%b is read by the Set that writes it"
    )
    assert taskstep.inputs_needed("Nothing", PrimeItems) == []


def test_the_trace_reads_as_text(tmp_path: Path) -> None:
    trace = walk(tmp_path, if_("%n", 7, "3"), set_("%r", "big"), end_if(), variables={"n": "5"})

    text = trace.as_text()

    assert text.startswith("Task 'T': finished.")
    assert "1. If [taken]" in text
    assert "r: '' -> 'big'" in text


def test_walking_a_task_leaves_the_configuration_and_the_start_values_untouched(tmp_path: Path) -> None:
    _load_local(tmp_path, _xml(T=(set_("%a", "changed"),)))
    start = {"a": "original"}
    before = {key: entry["xml"].findtext("nme") for key, entry in PrimeItems.tasker_root_elements["all_tasks"].items()}

    taskstep.step_task("T", PrimeItems, taskstep.Options(variables=start))

    assert start == {"a": "original"}
    assert before == {
        key: entry["xml"].findtext("nme") for key, entry in PrimeItems.tasker_root_elements["all_tasks"].items()
    }


def test_copying_something_unknown_makes_the_copy_unknown_too(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        http("https://example.com"),
        set_("%b", "got %http_data"),
        if_("%b", 0, "x"),
        set_("%r", "yes"),
        end_if(),
    )

    assert trace.variables["b"] == taskstep.UNKNOWN_TEXT
    assert "depends on %http_data, which is unknown" in trace.steps[1].detail
    assert trace.outcome == taskstep.NEEDS_VALUE
    assert trace.needed == ["b"]


def test_a_for_over_items_that_are_unknown_needs_a_value_not_one_made_up_item(tmp_path: Path) -> None:
    actions = (http("https://example.com"), for_("%x", "%http_data()"), add("%n", "1"), end_for())

    stopped = walk(tmp_path, *actions)
    unset = walk(tmp_path, *actions, policy=taskstep.POLICY_UNSET)

    assert stopped.outcome == taskstep.NEEDS_VALUE
    assert "http_data" in stopped.needed
    assert unset.outcome == taskstep.FINISHED, "treated as not set, Tasker walks it once, over the text as written"


def test_what_an_action_writes_is_not_an_input_the_task_needs(tmp_path: Path) -> None:
    shell = _act("123", _s(0, "ls"), _s(3, "%files"), _s(5, "%rc"))
    _load_local(
        tmp_path,
        _xml(
            T=(
                shell,
                if_("%files", 0, "x"),
                end_if(),
                http("u"),
                if_("%http_response_code", 0, "200"),
                end_if(),
                set_("%a", "%real_input"),
            )
        ),
    )

    assert taskstep.inputs_needed("T", PrimeItems) == ["real_input"]
