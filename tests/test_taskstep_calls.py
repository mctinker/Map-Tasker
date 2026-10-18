"""MapTasker Task Stepper, walking into a Perform Task (taskstep) Unit Tests

A call is where a dry run most easily lies, so what is tested is the contract Tasker keeps between two Tasks: what the
performed Task is handed (%par1, %par2, the globals, and only the locals the call passes through), what it gives back
(its Return value, its globals, and only the locals its Return passes through), and where it ends (a Stop or a Return ends
the called Task and nothing else).

And, as everywhere in this module, what it cannot know: a Task named by a variable with no value, one that is not in the
file, one nested too deep and one that loops are each said so against the step, and none is guessed at.
"""

from __future__ import annotations

from pathlib import Path

from maptasker.src.analysis import taskstep
from maptasker.src.core.primitem import PrimeItems

from tests.test_taskstep import _act, _i, _s, _xml, else_, end_if, flash, for_, end_for, if_, lines, return_, set_, stop
from tests.test_tnupdate import _load_local, _runtime  # noqa: F401  (_runtime is the fixture)


def perform(
    task: str,
    par1: str = "",
    par2: str = "",
    into: str = "",
    *,
    passthrough: bool = False,
    limit: str = "",
    reset: bool = False,
    overwrite: bool = False,
    own: str = "",
) -> str:
    """A Perform Task action, with every argument Tasker writes."""
    return _act(
        "130",
        _s(0, task),
        _i(1, 5),
        _s(2, par1),
        _s(3, par2),
        _s(4, into),
        _i(5, 0),
        _i(6, int(passthrough)),
        _s(7, limit),
        _i(8, int(reset)),
        _i(9, int(overwrite)),
        extra=own,
    )


def returning(value: str, *, passthrough: bool = False, limit: str = "", replace: bool = False) -> str:
    """A Return action, with the passthrough options it can carry."""
    return _act("126", _s(0, value), _i(1, 1), _i(2, int(passthrough)), _i(3, int(replace)), _s(4, limit))


def walk(
    tmp_path: Path, options: taskstep.Options | None = None, root: str = "Caller", **tasks: tuple[str, ...]
) -> taskstep.Trace:
    _load_local(tmp_path, _xml(**tasks))
    trace = taskstep.step_task(root, PrimeItems, options or taskstep.Options())
    assert trace is not None
    return trace


def value(trace: taskstep.Trace, name: str) -> str:
    return trace.variables.get(name, "")


# ##################################################################################
# Walking into the call.
# ##################################################################################


def test_the_called_task_is_walked_under_the_call_and_the_caller_goes_on(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%a", "1"), perform("Callee"), set_("%b", "2")),
        Callee=(set_("%x", "9"), flash("hi")),
    )

    assert [(step.number, step.task) for step in trace.steps] == [
        (1, ""),
        (2, ""),
        (1, "Callee"),
        (2, "Callee"),
        (3, ""),
    ]
    assert trace.steps[1].detail == "performed Task 'Callee': ran to the end"
    assert value(trace, "b") == "2"
    assert trace.outcome == taskstep.FINISHED


def test_a_called_step_is_indented_one_level_further_and_points_at_its_own_task(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(if_("%n", 0, "1"), perform("Callee"), end_if()),
        Callee=(set_("%x", "9"),),
        options=taskstep.Options(variables={"n": "1"}),
    )

    perform_step = next(step for step in trace.steps if step.name.startswith("Perform"))
    called = next(step for step in trace.steps if step.task == "Callee")
    assert called.depth == perform_step.depth + 1
    assert called.where is not None
    assert called.where.name == "Callee"
    assert perform_step.where is None, "the Task being stepped is the trace's own target"


def test_a_call_whose_own_if_is_false_is_not_entered(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(
            perform(
                "Callee",
                own='<ConditionList sr="if"><Condition sr="c0" ve="3"><lhs>%go</lhs><op>0</op><rhs>yes</rhs></Condition></ConditionList>',
            ),
        ),
        Callee=(set_("%x", "9"),),
        options=taskstep.Options(variables={"go": "no"}),
    )

    assert lines(trace) == [(1, taskstep.SKIPPED)]


# ##################################################################################
# What the called Task is handed.
# ##################################################################################


def test_the_parameters_arrive_as_par1_and_par2(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%name", "Ann"), perform("Callee", "hello %name", "7")),
        Callee=(set_("%got", "%par1/%par2"),),
    )

    called = next(step for step in trace.steps if step.task == "Callee")
    assert called.variables["got"] == "hello Ann/7"


def test_the_called_task_does_not_see_the_callers_locals(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%mine", "secret"), perform("Callee")),
        Callee=(set_("%seen", "%mine"),),
    )

    called = next(step for step in trace.steps if step.task == "Callee")
    assert called.variables["seen"] == "%mine", "left written out: it has no such variable"


def test_the_globals_are_shared_both_ways(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%Total", "1"), perform("Callee"), set_("%after", "%Total/%Made")),
        Callee=(set_("%Total", "5"), set_("%Made", "new")),
    )

    assert value(trace, "Total") == "5"
    assert value(trace, "after") == "5/new"


def test_a_local_the_called_task_makes_does_not_come_back(tmp_path: Path) -> None:
    trace = walk(tmp_path, Caller=(perform("Callee"),), Callee=(set_("%inside", "1"),))

    assert "inside" not in trace.variables


def test_a_call_that_passes_its_locals_through_hands_them_over(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%mine", "m"), set_("%other", "o"), perform("Callee", passthrough=True)),
        Callee=(set_("%seen", "%mine/%other"),),
    )

    called = next(step for step in trace.steps if step.task == "Callee")
    assert called.variables["seen"] == "m/o"


def test_a_passthrough_limited_to_names_hands_over_only_those(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%mine", "m"), set_("%other", "o"), perform("Callee", passthrough=True, limit="mine")),
        Callee=(set_("%seen", "%mine/%other"),),
    )

    called = next(step for step in trace.steps if step.task == "Callee")
    assert called.variables["seen"] == "m/%other"


def test_a_parameter_that_depends_on_an_unknown_is_unknown_in_the_called_task(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee", "%mystery"),),
        Callee=(if_("%par1", 0, "x"), set_("%r", "1"), end_if()),
    )

    assert trace.outcome == taskstep.NEEDS_VALUE
    assert "par1" in trace.needed


# ##################################################################################
# What it gives back.
# ##################################################################################


def test_the_return_value_goes_to_the_return_value_variable(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee", into="%answer"), if_("%answer", 0, "42"), set_("%r", "right"), end_if()),
        Callee=(returning("42"),),
    )

    assert value(trace, "answer") == "42"
    assert value(trace, "r") == "right"
    assert trace.steps[0].detail == "performed Task 'Callee': returned '42'"


def test_the_return_value_is_worked_out_in_the_called_task(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee", "5", into="%answer"),),
        Callee=(set_("%double", "%par1*2", maths=True), returning("%double")),
    )

    assert value(trace, "answer") == "10"


def test_a_called_task_that_returns_nothing_leaves_the_variable_alone(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%answer", "old"), perform("Callee", into="%answer")),
        Callee=(flash("no return"),),
    )

    assert value(trace, "answer") == "old"


def test_reset_return_variable_clears_it_before_the_call(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%answer", "old"), perform("Callee", into="%answer", reset=True)),
        Callee=(flash("no return"),),
    )

    assert "answer" not in trace.variables


def test_a_return_that_passes_its_locals_through_gives_them_to_the_caller(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee"),),
        Callee=(set_("%made", "m"), set_("%also", "a"), returning("v", passthrough=True)),
    )

    assert value(trace, "made") == "m"
    assert value(trace, "also") == "a"


def test_a_passthrough_back_is_limited_to_the_names_given(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee"),),
        Callee=(set_("%made", "m"), set_("%also", "a"), returning("v", passthrough=True, limit="made")),
    )

    assert value(trace, "made") == "m"
    assert "also" not in trace.variables


def test_a_returned_local_does_not_replace_one_the_caller_has_unless_told_to(tmp_path: Path) -> None:
    callee = (set_("%made", "new"), returning("v", passthrough=True))
    kept = walk(tmp_path, Caller=(set_("%made", "old"), perform("Callee")), Callee=callee)
    replaced_by_return = walk(
        tmp_path,
        Caller=(set_("%made", "old"), perform("Callee")),
        Callee=(set_("%made", "new"), returning("v", passthrough=True, replace=True)),
    )
    replaced_by_call = walk(tmp_path, Caller=(set_("%made", "old"), perform("Callee", overwrite=True)), Callee=callee)

    assert value(kept, "made") == "old"
    assert value(replaced_by_return, "made") == "new"
    assert value(replaced_by_call, "made") == "new"


def test_a_return_value_that_depends_on_an_unknown_makes_the_variable_unknown(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee", into="%answer"), if_("%answer", 0, "1"), set_("%r", "x"), end_if()),
        Callee=(returning("%mystery"),),
    )

    assert trace.outcome == taskstep.NEEDS_VALUE
    assert trace.needed == ["answer"]


# ##################################################################################
# Where the called Task ends.
# ##################################################################################


def test_a_stop_in_the_called_task_ends_it_and_the_caller_carries_on(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee"), set_("%after", "reached")),
        Callee=(set_("%x", "1"), stop(), set_("%never", "1")),
    )

    assert trace.outcome == taskstep.FINISHED
    assert value(trace, "after") == "reached"
    assert trace.steps[0].detail == "performed Task 'Callee': ended at a Stop"
    assert trace.callee_not_reached == {"Callee": [3]}


def test_a_return_in_the_called_task_does_not_end_the_caller(tmp_path: Path) -> None:
    trace = walk(tmp_path, Caller=(perform("Callee"), set_("%after", "reached")), Callee=(returning("1"),))

    assert trace.outcome == taskstep.FINISHED
    assert value(trace, "after") == "reached"


def test_a_task_called_twice_is_never_reached_only_where_neither_call_went(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee", "a"), perform("Callee", "b")),
        Callee=(if_("%par1", 0, "a"), flash("first"), else_(), flash("second"), end_if(), flash("never")),
    )

    assert trace.callee_not_reached == {}, "the second call took the Else, so every action was reached"


def test_the_actions_of_a_called_task_that_no_call_reached_are_listed_under_its_name(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee", "a"),),
        Callee=(if_("%par1", 0, "a"), flash("first"), else_(), flash("second"), end_if()),
    )

    assert trace.callee_not_reached == {"Callee": [3, 4]}


# ##################################################################################
# What it cannot follow.
# ##################################################################################


def test_a_task_named_by_a_variable_is_followed_when_the_variable_is_known(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(set_("%which", "Callee"), perform("%which", into="%answer")),
        Callee=(returning("ok"),),
    )

    assert value(trace, "answer") == "ok"


def test_a_task_named_by_a_variable_with_no_value_is_not_entered(tmp_path: Path) -> None:
    trace = walk(tmp_path, Caller=(perform("%which", into="%answer"),), Callee=(returning("ok"),))

    assert trace.steps[0].status == taskstep.NOT_SIMULATED
    assert "its Task name depends on %which" in trace.steps[0].detail
    assert trace.variables["answer"] == taskstep.UNKNOWN_TEXT


def test_a_task_that_is_not_in_the_file_is_not_entered_and_says_so(tmp_path: Path) -> None:
    trace = walk(tmp_path, Caller=(perform("Nowhere", into="%answer"),))

    assert trace.steps[0].status == taskstep.NOT_SIMULATED
    assert "no Task named 'Nowhere' is in the loaded configuration" in trace.steps[0].detail
    assert trace.variables["answer"] == taskstep.UNKNOWN_TEXT


def test_with_following_turned_off_a_call_is_shown_and_not_entered(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        taskstep.Options(follow_calls=False),
        Caller=(perform("Callee", into="%answer"),),
        Callee=(returning("ok"),),
    )

    assert len(trace.steps) == 1
    assert "following Perform Task is turned off" in trace.steps[0].detail
    assert trace.variables["answer"] == taskstep.UNKNOWN_TEXT


def test_a_task_that_calls_itself_is_followed_to_a_limit_and_no_further(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        taskstep.Options(max_call_depth=3),
        Caller=(perform("Caller"),),
    )

    entered = [step for step in trace.steps if step.name.startswith("Perform")]
    assert len(entered) == 4, "the Task, and three calls into itself"
    assert entered[-1].status == taskstep.NOT_SIMULATED
    assert "more than 3 Tasks deep" in entered[-1].detail
    assert trace.outcome == taskstep.FINISHED


def test_a_called_task_that_loops_is_cut_off_by_the_one_budget(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        taskstep.Options(max_steps=40),
        Caller=(perform("Callee"), set_("%after", "never")),
        Callee=(for_("%i", "1:1000"), set_("%n", "%i"), end_for()),
    )

    assert trace.outcome == taskstep.STEP_LIMIT
    assert "In Task 'Callee'" in trace.message
    assert "after" not in trace.variables


def test_a_condition_the_called_task_cannot_decide_stops_the_whole_walk_and_names_the_task(tmp_path: Path) -> None:
    trace = walk(
        tmp_path,
        Caller=(perform("Callee"), set_("%after", "never")),
        Callee=(if_("%unknown_here", 0, "1"), set_("%r", "x"), end_if()),
    )

    assert trace.outcome == taskstep.NEEDS_VALUE
    assert trace.message.startswith("In Task 'Callee': Stopped at action 1")
    assert trace.needed == ["unknown_here"]
    assert "after" not in trace.variables


def test_the_text_of_a_walk_says_which_task_each_line_is_in(tmp_path: Path) -> None:
    trace = walk(tmp_path, Caller=(perform("Callee"), flash("done")), Callee=(flash("inside"),))

    text = trace.as_text()

    assert "-- in Task 'Callee' --" in text
    assert "-- back in 'Caller' --" in text
