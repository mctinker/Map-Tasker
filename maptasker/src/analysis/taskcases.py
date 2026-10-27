"""taskcases: save a Task Stepper run as a named test, and run every test again after an edit."""

#! /usr/bin/env python3

#                                                                                        #
# taskcases: the Task Stepper's runs, kept.                                              #
#                                                                                        #
# The Stepper answers "what does this Task do with THESE values?".  Once it has been right, the   #
# answer is worth keeping: edit the Task, run Fix Findings over the file, move half of it into a   #
# Task of its own, and the same question asked of the same values should still be answered the     #
# same way.  A test case is that question and that answer, saved under a name; running it asks      #
# the question again of the configuration as it is now and says where the answer has moved.        #
#                                                                                        #
# WHAT A CASE PINS                                                                        #
#                                                                                        #
#   outcome   how the walk ended -- finished, stopped, returned.  Always.                         #
#   variables the final value of each variable the Task changed, as chosen when it was saved.     #
#             Only what the walk KNEW: a value that depended on something not simulated is not     #
#             pinned, since a test of "(unknown)" would pass for the wrong reasons.               #
#   effects   what the Task would put on screen, say, or send out -- the text of every action the   #
#             walk shows or does not simulate, with the variables filled in, in order.  A Flash that   #
#             now says something else is a change in what the Task does, and so is a web request to a   #
#             different address.  Numbers are left out, so adding an action elsewhere does not fail it.   #
#   path      OPTIONAL, and off unless asked for: which branches were taken and which loop turns, by     #
#             action number.  Strict on purpose -- it fails when an action is added above a branch, which   #
#             is a refactor and not a regression -- and so for a Task whose route is the point.              #
#                                                                                        #
# WHAT IS KEPT, AND WHERE                                                                  #
#                                                                                        #
# A case is found again by the Task's NAME: ids are renumbered whenever a backup passes through       #
# Tasker, and the name is what the Task is called everywhere else.  The file is in the current         #
# directory beside the settings (TASK_TESTS_FILE), plain JSON that can be read and edited.  A case       #
# whose Task is not in the file that is open is reported as that and counted separately from a failure,   #
# because a friend's backup is not a regression in yours.                                            #
#                                                                                        #
# Same contract as taskstep: reads the run state's tables and writes nothing but its own file -- no   #
# GUI -- so it is testable without a window, and guiwins_taskcases is the drawing.                  #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import difflib
import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from maptasker.src.analysis import taskstep
from maptasker.src.core import clock
from maptasker.src.core.sysconst import TASK_TESTS_FILE, logger

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# How a case came out.
PASSED = "passed"
FAILED = "failed"
MISSING = "not in this file"

# The version of the file's layout, so a later release can tell what it is reading.
FORMAT_VERSION = 1

# How many differing lines of one kind a result lists before counting the rest.
_LINES_SHOWN = 6
# How much of a value a difference line quotes.
_VALUE_WIDTH = 80

# The word the walks of a Task a step belongs to are told apart by, in an effect line.
_IN_TASK = "in Task"


# ##################################################################################
# What a case is.
# ##################################################################################
@dataclass
class Setup:
    """What a run starts from: the question.  The same things the Stepper's controls hold."""

    variables: dict[str, str] = field(default_factory=dict[str, str])
    assumed: dict[int, dict[str, str]] = field(default_factory=dict[int, dict[str, str]])
    policy: str = taskstep.POLICY_STOP
    follow_calls: bool = True
    # Whether the globals saved in the backup are part of the starting values.  They are not copied into the case:
    # a Task that reads one is deciding by whatever the file says, and a test of it should notice when that moves.
    use_globals: bool = True
    max_steps: int = taskstep.DEFAULT_MAX_STEPS

    def options(self, state: RunState) -> taskstep.Options:
        """The Stepper's options for this setup, against the configuration `state` holds."""
        values = taskstep.global_values(state) if self.use_globals else {}
        values.update(self.variables)
        return taskstep.Options(
            variables=values,
            policy=self.policy,
            max_steps=self.max_steps,
            assumed={number: dict(found) for number, found in self.assumed.items()},
            follow_calls=self.follow_calls,
        )


@dataclass
class Expected:
    """What the run came to: the answer.  `effects` and `path` are None when the case does not pin them."""

    outcome: str = taskstep.FINISHED
    variables: dict[str, str] = field(default_factory=dict[str, str])
    effects: list[str] | None = None
    path: list[str] | None = None


@dataclass
class Case:
    """One named test: a Task, the values it starts with, and what it is expected to do."""

    name: str
    task: str
    setup: Setup = field(default_factory=Setup)
    expected: Expected = field(default_factory=Expected)
    saved: str = ""
    note: str = ""


@dataclass
class Pins:
    """What to keep of a run when it is saved as a case."""

    # The variables to pin, by name; None for every one the Task changed that the walk knew.
    variables: list[str] | None = None
    effects: bool = True
    path: bool = False


# ##################################################################################
# Reading a trace.
# ##################################################################################
def touched(trace: taskstep.Trace) -> list[str]:
    """The variables the Task changed and the walk knew the final value of, in the order they were first changed."""
    names = dict.fromkeys(change.name for step in trace.steps for change in step.changes)
    return [name for name in names if name in trace.variables and trace.variables[name] != taskstep.UNKNOWN_TEXT]


def effects(trace: taskstep.Trace) -> list[str]:
    """What the Task would show, say or send, in order: the text of every action shown or not simulated.

    The number is left off: it is where the action is, not what it does, and a test that fails when an
    unrelated action is added above it would be one nobody trusts.  A step inside a performed Task is marked.
    """
    lines: list[str] = []
    for step in trace.steps:
        shown = step.status == taskstep.RAN and step.detail == taskstep.SHOWN_DETAIL
        if shown or step.status in (taskstep.NOT_SIMULATED, taskstep.ASSUMED):
            where = f"[{_IN_TASK} {step.task}] " if step.task else ""
            lines.append(f"{where}{step.text}")
    return lines


def path(trace: taskstep.Trace) -> list[str]:
    """Every branch and loop turn the walk took or passed over, by action number -- 'task:5:taken' for a Task performed."""
    chosen = (taskstep.TAKEN, taskstep.NOT_TAKEN, taskstep.SKIPPED)
    return [
        f"{step.task + ':' if step.task else ''}{step.number}:{step.status}"
        for step in trace.steps
        if step.status in chosen
    ]


def problem_with(trace: taskstep.Trace) -> str:
    """Why this run cannot be kept as a test, or "" when it can."""
    if trace.outcome == taskstep.NEEDS_VALUE:
        return (
            "The walk stopped because it needed a value"
            + (f" for {', '.join('%' + name for name in trace.needed[:5])}" if trace.needed else "")
            + ".  Give it one, or choose how to treat a variable with no value, and step it again."
        )
    if trace.outcome == taskstep.FAILED:
        return "The walk could not make sense of the Task, so there is nothing sound to keep."
    return ""


def capture(name: str, task: str, setup: Setup, trace: taskstep.Trace, pins: Pins | None = None) -> Case:
    """The case that says: with `setup`, this Task did what `trace` shows.

    Raises ValueError, with the reason, for a run that cannot be kept -- see problem_with.
    """
    problem = problem_with(trace)
    if problem:
        raise ValueError(problem)
    pins = pins or Pins()
    wanted = touched(trace) if pins.variables is None else [n for n in pins.variables if n in trace.variables]
    values = {name_: trace.variables[name_] for name_ in wanted if trace.variables[name_] != taskstep.UNKNOWN_TEXT}
    expected = Expected(
        outcome=trace.outcome,
        variables=values,
        effects=effects(trace) if pins.effects else None,
        path=path(trace) if pins.path else None,
    )
    return Case(
        name=name.strip(),
        task=task,
        setup=Setup(
            variables=dict(setup.variables),
            assumed={number: dict(found) for number, found in setup.assumed.items()},
            policy=setup.policy,
            follow_calls=setup.follow_calls,
            use_globals=setup.use_globals,
            max_steps=setup.max_steps,
        ),
        expected=expected,
        saved=clock.now().isoformat(timespec="seconds"),
    )


# ##################################################################################
# Running.
# ##################################################################################
@dataclass
class Result:
    """What one case came to when it was run again."""

    case: Case
    status: str
    # Each way the run differs from what was expected, one line each.  Empty for a pass.
    differences: list[str] = field(default_factory=list[str])
    trace: taskstep.Trace | None = None


def _cut(value: str) -> str:
    """One line of a value, cut short -- a variable can hold a whole web page."""
    single = " ".join(value.split())
    return single if len(single) <= _VALUE_WIDTH else f"{single[: _VALUE_WIDTH - 3]}..."


def _list_differences(label: str, expected: list[str], got: list[str]) -> list[str]:
    """How two ordered lists of lines differ, as sentences: what went, what came, and what changed."""
    if expected == got:
        return []
    lines: list[str] = []
    matcher = difflib.SequenceMatcher(a=expected, b=got, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        pairs = min(i2 - i1, j2 - j1) if tag == "replace" else 0
        lines += [f"{label} changed: '{_cut(expected[i1 + k])}' became '{_cut(got[j1 + k])}'" for k in range(pairs)]
        lines += [f"{label} no longer happens: '{_cut(line)}'" for line in expected[i1 + pairs : i2]]
        lines += [f"{label} now also happens: '{_cut(line)}'" for line in got[j1 + pairs : j2]]
    if len(lines) > _LINES_SHOWN:
        lines = [*lines[:_LINES_SHOWN], f"... and {len(lines) - _LINES_SHOWN} more {label} differences"]
    return lines


def compare(expected: Expected, trace: taskstep.Trace) -> list[str]:
    """Every way `trace` differs from `expected`, one sentence each.  Empty when it matches."""
    differences: list[str] = []
    if trace.outcome != expected.outcome:
        said = f"  ({trace.message})" if trace.message else ""
        differences.append(f"It {trace.outcome}, where it was expected to be {expected.outcome}.{said}")
    for name, was in expected.variables.items():
        now = trace.variables.get(name)
        if now is None:
            differences.append(f"%{name} is not set, where it was expected to be '{_cut(was)}'.")
        elif now == taskstep.UNKNOWN_TEXT:
            differences.append(f"%{name} can no longer be worked out, where it was expected to be '{_cut(was)}'.")
        elif now != was:
            differences.append(f"%{name} is '{_cut(now)}', where it was expected to be '{_cut(was)}'.")
    if expected.effects is not None:
        differences += _list_differences("What it does", expected.effects, effects(trace))
    if expected.path is not None:
        differences += _list_differences("The route", expected.path, path(trace))
    return differences


def run_case(case: Case, state: RunState) -> Result:
    """Run one case against the configuration `state` holds."""
    trace = taskstep.step_task(case.task, state, case.setup.options(state))
    if trace is None:
        return Result(case, MISSING, [f"Task '{case.task}' is not in the file that is open."])
    differences = compare(case.expected, trace)
    return Result(case, FAILED if differences else PASSED, differences, trace)


def run_all(book: CaseBook, state: RunState) -> list[Result]:
    """Run every case in the book, in the book's order."""
    return [run_case(case, state) for case in book.cases]


def counts(results: list[Result]) -> tuple[int, int, int]:
    """(passed, failed, not in this file)."""
    return (
        sum(result.status == PASSED for result in results),
        sum(result.status == FAILED for result in results),
        sum(result.status == MISSING for result in results),
    )


def failing(results: list[Result]) -> list[Result]:
    """The results that are regressions: a case that ran and no longer comes out as saved."""
    return [result for result in results if result.status == FAILED]


def report(results: list[Result]) -> str:
    """The results as plain text, for a file or a forum post."""
    passed, failed, missing = counts(results)
    lines = [
        f"Task tests: {len(results)} run -- {passed} passed, {failed} failed, {missing} not in this file.",
        "",
    ]
    for result in results:
        lines.append(f"[{result.status.upper()}] {result.case.name}  (Task '{result.case.task}')")
        lines.extend(f"      {line}" for line in result.differences)
    return "\n".join(lines)


# ##################################################################################
# Keeping them.
# ##################################################################################
@dataclass
class CaseBook:
    """Every saved case, and the one setting that goes with them."""

    cases: list[Case] = field(default_factory=list[Case])
    # Whether the window runs them all again whenever the configuration is edited.
    after_edit: bool = True

    def get(self, name: str) -> Case | None:
        """The case with this name, or None."""
        return next((case for case in self.cases if case.name == name), None)

    def put(self, case: Case) -> bool:
        """Keep a case, in the place of the one of the same name.  True when it replaced one."""
        for position, found in enumerate(self.cases):
            if found.name == case.name:
                self.cases[position] = case
                return True
        self.cases.append(case)
        return False

    def remove(self, name: str) -> bool:
        """Drop the case with this name.  True when there was one."""
        kept = [case for case in self.cases if case.name != name]
        removed = len(kept) != len(self.cases)
        self.cases = kept
        return removed

    def for_task(self, task: str) -> list[Case]:
        """The cases that are about this Task."""
        return [case for case in self.cases if case.task == task]

    def unused_name(self, wanted: str) -> str:
        """`wanted`, or 'wanted 2', 'wanted 3' ... when a case already has it."""
        names = {case.name for case in self.cases}
        if wanted not in names:
            return wanted
        number = 2
        while f"{wanted} {number}" in names:
            number += 1
        return f"{wanted} {number}"


def book_path() -> str:
    """Where the cases are kept -- in the current directory, beside the settings."""
    return os.path.join(os.getcwd(), TASK_TESTS_FILE)


def _dict(value: object) -> dict[str, Any]:
    """A JSON value as a dict, or an empty one if it is anything else."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _strings(value: object) -> dict[str, str]:
    """A JSON object of text to text."""
    return {str(key): str(item) for key, item in _dict(value).items()}


def _lines(value: object) -> list[str] | None:
    """A JSON list of text, or None when it is not one (a pin the case does not have)."""
    return [str(item) for item in cast("list[Any]", value)] if isinstance(value, list) else None


def _case_from(data: object) -> Case | None:
    """One case from its JSON, or None when it is not one -- a name and a Task are the least a case is."""
    raw = _dict(data)
    name, task = str(raw.get("name") or "").strip(), str(raw.get("task") or "").strip()
    if not name or not task:
        return None
    setup, expected = _dict(raw.get("setup")), _dict(raw.get("expected"))
    assumed = {
        int(number): _strings(found) for number, found in _dict(setup.get("assumed")).items() if str(number).isdigit()
    }
    policy = str(setup.get("policy") or taskstep.POLICY_STOP)
    return Case(
        name=name,
        task=task,
        setup=Setup(
            variables=_strings(setup.get("variables")),
            assumed=assumed,
            policy=policy if policy in taskstep.POLICIES else taskstep.POLICY_STOP,
            follow_calls=bool(setup.get("follow_calls", True)),
            use_globals=bool(setup.get("use_globals", True)),
            max_steps=int(setup.get("max_steps") or taskstep.DEFAULT_MAX_STEPS),
        ),
        expected=Expected(
            outcome=str(expected.get("outcome") or taskstep.FINISHED),
            variables=_strings(expected.get("variables")),
            effects=_lines(expected.get("effects")),
            path=_lines(expected.get("path")),
        ),
        saved=str(raw.get("saved") or ""),
        note=str(raw.get("note") or ""),
    )


def _case_to_json(case: Case) -> dict[str, Any]:
    """A case as JSON."""
    return {
        "name": case.name,
        "task": case.task,
        "saved": case.saved,
        "note": case.note,
        "setup": {
            "variables": case.setup.variables,
            "assumed": {str(number): found for number, found in case.setup.assumed.items()},
            "policy": case.setup.policy,
            "follow_calls": case.setup.follow_calls,
            "use_globals": case.setup.use_globals,
            "max_steps": case.setup.max_steps,
        },
        "expected": {
            "outcome": case.expected.outcome,
            "variables": case.expected.variables,
            "effects": case.expected.effects,
            "path": case.expected.path,
        },
    }


def load_book(file_path: str | None = None) -> tuple[CaseBook, int]:
    """(the saved cases, how many entries in the file could not be read).  An empty book when there is no file."""
    where = file_path or book_path()
    try:
        with open(where, encoding="utf-8") as handle:
            data = _dict(json.load(handle))
    except FileNotFoundError:
        return CaseBook(), 0
    except (OSError, ValueError) as error:
        logger.error(f"Task tests could not be read from {where}: {error}")
        return CaseBook(), 1
    entries = cast("list[Any]", data.get("cases")) if isinstance(data.get("cases"), list) else []
    cases = [case for case in (_case_from(entry) for entry in entries) if case is not None]
    return CaseBook(cases=cases, after_edit=bool(data.get("after_edit", True))), len(entries) - len(cases)


def save_book(book: CaseBook, file_path: str | None = None) -> str:
    """Write the cases.  Returns "" or why they could not be saved."""
    where = file_path or book_path()
    data = {
        "version": FORMAT_VERSION,
        "after_edit": book.after_edit,
        "cases": [_case_to_json(case) for case in book.cases],
    }
    try:
        with open(where, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
    except OSError as error:
        logger.error(f"Task tests could not be written to {where}: {error}")
        return str(error)
    return ""
