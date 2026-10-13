"""taskstep: dry-run one Task -- walk it action by action, with the variables it starts with."""

#! /usr/bin/env python3

#                                                                                        #
# taskstep: pick a Task, say what its variables hold when it starts, and read off what     #
#           it would do: which If, Else If, For and Goto branches it takes, which actions  #
#           it skips, and what every variable holds after each step.                        #
#                                                                                        #
# firesim answers "which Profiles does this moment make active, and which Tasks do they    #
# start?" and stops there.  This is the next question: once a Task starts, what does it do?  #
# taskflow already reads a Task's structure -- its blocks, where each Goto lands, which       #
# actions can never run -- and answers "can this ever run?"; this answers "does it, with      #
# THESE values?".  The structure is taskflow's own, imported rather than read again, so the   #
# two cannot disagree about where an Else or a Goto goes.                                    #
#                                                                                        #
# WHAT IS SIMULATED, AND WHAT IS NOT                                                      #
#                                                                                        #
# The things that decide the path, exactly:                                                 #
#                                                                                        #
#   control flow   If / Else If / Else / End If, For / End For, Goto (by number, label, top    #
#                  or end of loop, or end of If), Stop, Return, and the "If" any action can    #
#                  carry.  A disabled action is stepped over.                                #
#   variables      Variable Set (with Do Maths, Recurse and Append), Variable Add (with Wrap     #
#                  Around), Variable Clear, Variable Split, and %name / %array(n) / %array(#) /   #
#                  %array() wherever one is written.                                         #
#   conditions     Equals, Doesn't Equal, Matches, Doesn't Match, Matches Regex, Doesn't Match     #
#                  Regex, Less Than, Greater Than, Is Set, Isn't Set, joined by And / Or / Xor     #
#                  in Tasker's precedence (condjoin's).                                       #
#                                                                                        #
# Everything else is SHOWN rather than done: Flash, Notify, Say, Wait and the like say what       #
# they would put on screen with the variables filled in, and anything that talks to the world     #
# (a web request, a shell, a plugin, another Task) is listed as "not simulated".                  #
#                                                                                        #
# THREE ANSWERS, NOT TWO.  A variable is known (it was given, or an action set it), UNKNOWN (an    #
# action that was not simulated may have set it -- its Store Output In, say) or absent.  A         #
# condition that depends on an unknown or absent variable is not guessed at: the walk STOPS and    #
# says which variables it needs, unless the user chose another policy -- treat the variable as     #
# not set (what Tasker itself does for a local), or assume the condition true, or false -- and     #
# whichever was chosen is written against the step it applied to.  The same rule as firesim's:     #
# reading a thing this module cannot read is how a working Task gets reported as broken.         #
#                                                                                        #
# WHAT THIS CANNOT TELL YOU, SAID PLAINLY BECAUSE A DRY RUN GETS TRUSTED                            #
#                                                                                        #
#   * It is Tasker's rules as documented and measured, not Tasker's code.  Matches uses *-and-?    #
#     patterns ignoring case, Matches Regex must match the whole value, and a comparison of two     #
#     numbers is numeric.  Each condition line shows the values it compared, so a reader can see     #
#     what was decided and check it against the device.                                         #
#   * A JavaScriptlet may change any variable.  The walk carries on assuming it did not, and says   #
#     so against that step.                                                                  #
#   * Perform Task is not entered.  Its Return Value Variable is unknown afterwards.                #
#   * Time passes in none of it: a Wait waits for nothing, and %TIMES and friends are not made up.  #
#   * A Task that loops without end is cut off after max_steps actions and reported as such.        #
#                                                                                        #
# Same contract as taskflow and firesim: reads PrimeItems.tasker_root_elements and nothing else --   #
# no GUI, no generated HTML -- so it is testable without a window; guiwins_taskstep is the drawing.  #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import ast
import fnmatch
import math
import operator
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from maptasker.src.analysis import taskflow
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.condjoin import boolean_operators
from maptasker.src.core.mapjump import actions_in_map_order

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

# What a step did.
RAN = "ran"
SKIPPED = "skipped"  # the action's own "If" was false
TAKEN = "taken"  # a branch, a loop turn or a jump that was taken
NOT_TAKEN = "not taken"  # a condition that was false
DISABLED = "disabled"
NOT_SIMULATED = "not simulated"
ASSUMED = "assumed"
ENDED = "ended"
UNDECIDED = "undecided"

# How a walk ended.
FINISHED = "finished"  # ran off the end of the Task
STOPPED = "stopped"  # a Stop in this Task
RETURNED = "returned"  # a Return
NEEDS_VALUE = "needs a value"  # a condition depended on something unknown, and the policy was to stop
STEP_LIMIT = "step limit"
FAILED = "failed"  # something in the Task the walk cannot make sense of

# What to do about a condition that depends on a variable with no value.
POLICY_STOP = "stop"
POLICY_UNSET = "unset"
POLICY_TRUE = "true"
POLICY_FALSE = "false"
POLICIES = (POLICY_STOP, POLICY_UNSET, POLICY_TRUE, POLICY_FALSE)

DEFAULT_MAX_STEPS = 500

# Shown in place of a value the walk cannot know.
UNKNOWN_TEXT = "(unknown)"

# Tasker's action codes the walk interprets itself.
_IF, _ELSE, _END_IF = "37", "43", "38"
_FOR, _END_FOR = "39", "40"
_GOTO, _STOP, _RETURN, _PERFORM = "135", "137", "126", "130"
_VAR_SET, _VAR_ADD, _VAR_CLEAR, _VAR_SPLIT = "547", "888", "549", "590"
_JAVASCRIPTLET = "129"

# Actions that put something on screen or make a sound and touch no variable.  They are "run"
# in the sense of "would happen"; their text is shown with the variables filled in.
_SHOWN_ONLY = frozenset({"30", "35", "61", "62", "171", "523", "548", "550", "559", "779", "300"})

# Variables an action that is not simulated is known to leave behind, by code.  Partial on purpose: it
# names the common ones; the rest are found from the arguments (see _output_names).
_FIXED_OUTPUTS = {
    "339": ("http_data", "http_response_code", "http_headers", "http_cookies"),
    "902": ("LOC", "LOCACC", "LOCSPD", "LOCTMS"),
}
# Arguments whose NAME says the variable in them is written to, and the explicit ones for actions whose
# written-to argument is called something plain.
_OUTPUT_ARGUMENT = re.compile(r"store|output|result|return value variable|to var|variable array", re.IGNORECASE)
_NAMED_OUTPUTS = {"545": ("0",), "596": ("0", "2"), "598": ("0", "5"), "592": ("0",)}

# %name, %name(3), %name(#), %name().  A name starts with a letter; what follows % that is not a name is
# not a variable (50%, 100 %).
_VARIABLE = re.compile(r"%(?P<name>[A-Za-z][A-Za-z0-9_]*)(?:\((?P<index>#|\d*)\))?")
# A variable NAME as an action writes it: %head, then perhaps more (%arr%i).
_NAME = re.compile(r"^%(?P<head>[A-Za-z][A-Za-z0-9_]*)(?P<rest>.*)$", re.DOTALL)
# The numbers For takes as a range.
_RANGE = re.compile(r"^\s*(-?\d+)\s*:\s*(-?\d+)\s*$")

_MAX_ITEMS = 10_000
_MAX_RECURSION = 3
_MAX_POWER = 64
_DEFAULT_ROUNDING = 3

# How many characters of a value or an action's text a line quotes.
_TEXT_LIMIT = 120
_ARGUMENTS_SHOWN = 3

# Tasker's If operators, by the <op> code -- action.evaluate_condition's table.
_EQUALS, _NOT_EQUALS, _MATCHES, _NOT_MATCHES, _REGEX, _NOT_REGEX = "0", "1", "2", "3", "4", "5"
_LESS, _GREATER, _MATHS_EQUALS, _MATHS_NOT_EQUALS, _IS_SET, _NOT_SET = "6", "7", "8", "9", "12", "13"
_SYMBOL = {
    _EQUALS: "=",
    _NOT_EQUALS: "!=",
    _MATCHES: "matches",
    _NOT_MATCHES: "doesn't match",
    _REGEX: "matches regex",
    _NOT_REGEX: "doesn't match regex",
    _LESS: "<",
    _GREATER: ">",
    _MATHS_EQUALS: "= (maths)",
    _MATHS_NOT_EQUALS: "!= (maths)",
    _IS_SET: "is set",
    _NOT_SET: "is not set",
}
_UNARY = frozenset({_IS_SET, _NOT_SET})
# Tasker's boolean precedence: condjoin's, spelled the same so the two read a chain the same way.
_PRECEDENCE = {"and": 0, "or": 1, "xor": 1, "and2": 2, "or2": 3}


# ##################################################################################
# What a walk produces.
# ##################################################################################
@dataclass
class Change:
    """One variable's value before and after a step.  '' for before means it had none."""

    name: str
    before: str
    after: str


@dataclass
class Step:
    """One action as the walk met it: what it was, what happened, and what the variables held after.

    `number` is the number the Map prints for the action.  A loop meets the same action many times, so
    the same number can appear many times, in the order the walk was at them.
    """

    number: int
    name: str
    text: str
    status: str
    detail: str = ""
    changes: list[Change] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    # The block depth the action sits at, for indenting the display.
    depth: int = 0


@dataclass
class Options:
    """What a walk starts from and how it behaves."""

    variables: dict[str, str] = field(default_factory=dict)
    policy: str = POLICY_STOP
    max_steps: int = DEFAULT_MAX_STEPS
    # What an action that is not simulated leaves behind, by the action's number: {5: {"http_data": "ok"}}.
    assumed: dict[int, dict[str, str]] = field(default_factory=dict)


@dataclass
class Trace:
    """A whole walk: every step, how it ended, and what it did and did not touch."""

    task: str
    steps: list[Step] = field(default_factory=list)
    # Where the Task is in the Map, for a line to link to its actions.  None when the walk was not made on a loaded Task.
    target: Target | None = None
    outcome: str = FINISHED
    message: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    # Variables the walk needed and did not have, in the order it first needed them.
    needed: list[str] = field(default_factory=list)
    # The numbers of the actions that were never reached -- the branches that did not run.
    not_reached: list[int] = field(default_factory=list)

    def as_text(self) -> str:
        """The walk as plain text, for a forum post or a bug report."""
        lines = [f"Task '{self.task}': {self.outcome}.  {self.message}".rstrip(), ""]
        for step in self.steps:
            lines.append(f"{'  ' * step.depth}{step.number}. {step.name} [{step.status}]  {step.text}".rstrip())
            if step.detail:
                lines.append(f"{'  ' * step.depth}     {step.detail}")
            lines.extend(
                f"{'  ' * step.depth}     %{c.name}: '{_shorten(c.before, 60)}' -> '{_shorten(c.after, 60)}'"
                for c in step.changes
            )
        if self.not_reached:
            lines += ["", "Never reached: " + ", ".join(str(number) for number in self.not_reached)]
        return "\n".join(lines)


# ##################################################################################
# Variables.
# ##################################################################################
class Variables:
    """What the variables hold.  Names are kept without their %.  A name can also be UNKNOWN: set by something
    that was not simulated, so it has a value the walk cannot say."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        """`values` are the ones the Task starts with; a leading % on a name is allowed."""
        self.values: dict[str, str] = {}
        self.unknown: set[str] = set()
        for name, value in (values or {}).items():
            self.values[name.lstrip("%")] = str(value)

    def has(self, name: str) -> bool:
        """Whether the name has a value the walk knows."""
        return name in self.values and name not in self.unknown

    def get(self, name: str) -> str:
        """The value, or '' when it has none."""
        return self.values.get(name, "") if name not in self.unknown else ""

    def put(self, name: str, value: str) -> None:
        """Give a name a value, which makes it known."""
        self.values[name] = value
        self.unknown.discard(name)

    def forget(self, name: str) -> None:
        """Take a name away altogether."""
        self.values.pop(name, None)
        self.unknown.discard(name)

    def mark_unknown(self, name: str) -> None:
        """Say something unseen may have set this name."""
        self.unknown.add(name)

    def array(self, name: str) -> list[str]:
        """The elements of an array, in order: name1, name2, ..."""
        found = sorted(
            (int(key[len(name) :]), value)
            for key, value in self.values.items()
            if key.startswith(name) and key[len(name) :].isdigit() and key not in self.unknown
        )
        return [value for _, value in found]

    def snapshot(self) -> dict[str, str]:
        """Every variable and its value now, unknown ones shown as such."""
        shown = dict(self.values)
        shown.update(dict.fromkeys(self.unknown, UNKNOWN_TEXT))
        return dict(sorted(shown.items()))

    def substitute(self, text: str) -> tuple[str, list[str]]:
        """`text` with each %variable replaced by its value, and the names it needed that have none.

        A name with no value is left as Tasker leaves it: written out, % and all.
        """
        needed: list[str] = []

        def replace(match: re.Match) -> str:
            name, index = match["name"], match["index"]
            if index is None:
                if self.has(name):
                    return self.values[name]
                needed.append(name)
                return match[0]
            if name in self.unknown or (name not in self.values and not self.array(name)):
                needed.append(name)
                return match[0]
            elements = self.array(name)
            if index == "#":
                return str(len(elements))
            if index == "":
                return ",".join(elements)
            position = int(index)
            return elements[position - 1] if 1 <= position <= len(elements) else match[0]

        return _VARIABLE.sub(replace, text), needed


# ##################################################################################
# Numbers, patterns and maths.
# ##################################################################################
def _number(text: str) -> float | None:
    """The number `text` holds, or None if it is not one."""
    try:
        value = float(text.strip())
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _format(value: float, digits: int = _DEFAULT_ROUNDING) -> str:
    """A number as Tasker would write it: no trailing .0, rounded to `digits` places."""
    rounded = round(value, digits)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.{digits}f}".rstrip("0").rstrip(".")


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
}


def calculate(expression: str) -> float | None:
    """The value of a plain arithmetic expression, or None if it is anything else.

    + - * / % ** and brackets, and a few functions (abs, round, sqrt, floor, ceil, min, max).  Parsed with
    ast and walked by hand, never evaluated: the text is somebody's Task and names nothing it should reach.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        return float(_evaluate(tree.body))
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None


def _evaluate(node: ast.AST) -> float:
    """One node of an arithmetic expression.  Raises ValueError for anything not arithmetic."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        value = _evaluate(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        return _binary(node)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
        and not node.keywords
    ):
        return float(_FUNCTIONS[node.func.id](*(_evaluate(argument) for argument in node.args)))
    message = "not arithmetic"
    raise ValueError(message)


def _binary(node: ast.BinOp) -> float:
    """+ - * / % and ** with its operands, refusing a power too large to be worth computing."""
    left, right = _evaluate(node.left), _evaluate(node.right)
    if isinstance(node.op, ast.Pow):
        if abs(right) > _MAX_POWER or abs(left) > 10**6:
            message = "power too large"
            raise ValueError(message)
        return left**right
    function = _BINARY.get(type(node.op))
    if function is None:
        message = "not arithmetic"
        raise ValueError(message)
    return function(left, right)


def _shorten(text: str, limit: int = _TEXT_LIMIT) -> str:
    """One line, cut at `limit` characters."""
    single = " ".join(text.split())
    return single if len(single) <= limit else f"{single[: limit - 3]}..."


# ##################################################################################
# Conditions.
# ##################################################################################
@dataclass
class Verdict:
    """What a condition came to: True, False, or None when it depends on something with no value."""

    value: bool | None
    text: str = ""
    needed: list[str] = field(default_factory=list)


def _compare(code: str, left: str, right: str) -> bool | None:
    """One comparison of two values, by Tasker's operator code.  None for an operator or value it cannot judge."""
    first, second = _number(left), _number(right)
    if code in (_EQUALS, _NOT_EQUALS):
        same = left == right if first is None or second is None else first == second
        return same if code == _EQUALS else not same
    if code in (_MATHS_EQUALS, _MATHS_NOT_EQUALS):
        return None if first is None or second is None else (first == second) == (code == _MATHS_EQUALS)
    if code in (_LESS, _GREATER):
        if first is None or second is None:
            return None
        return first < second if code == _LESS else first > second
    if code in (_MATCHES, _NOT_MATCHES):
        matched = fnmatch.fnmatchcase(left.casefold(), right.casefold())
        return matched if code == _MATCHES else not matched
    if code in (_REGEX, _NOT_REGEX):
        try:
            matched = re.fullmatch(right, left) is not None
        except re.error:
            return None
        return matched if code == _REGEX else not matched
    return None


def _combine(values: list[bool | None], joiner: str) -> bool | None:
    """Join conditions by one of Tasker's operators, three-valued: any unknown unknowns the answer unless the rest decide it."""
    kind = joiner.rstrip("2")
    if kind == "and":
        if False in values:
            return False
        return None if None in values else True
    if kind == "or":
        if True in values:
            return True
        return None if None in values else False
    if None in values:
        return None
    return sum(1 for value in values if value) % 2 == 1  # xor


def _join(values: list[bool | None], joiners: list[str]) -> bool | None:
    """Fold a chain of conditions by Tasker's precedence: split at the loosest operator, join what lies between."""
    if not joiners:
        return values[0]
    loosest = min(_PRECEDENCE.get(joiner, 0) for joiner in joiners)
    groups: list[bool | None] = []
    start = 0
    for position, joiner in enumerate([*joiners, ""]):
        if joiner and _PRECEDENCE.get(joiner, 0) != loosest:
            continue
        groups.append(_join(values[start : position + 1], joiners[start:position]))
        start = position + 1
    loosest_joiner = next(joiner for joiner in joiners if _PRECEDENCE.get(joiner, 0) == loosest)
    return _combine(groups, loosest_joiner)


# ##################################################################################
# The walk.
# ##################################################################################
FALL = -1  # a result's `next` for "carry on with the next action"


@dataclass
class _Result:
    """What one action did, before the walk records it.

    An empty `status` is an action that is structure and nothing else -- End If, End For, an Else run off the
    end of the branch above it -- and is not worth a line in the trace.  `after` are lines to record AFTER this
    action's own: the Else Ifs an If passed through on its way to the branch it took.
    """

    text: str
    status: str = RAN
    detail: str = ""
    next: int | None = FALL  # an action index, FALL, or None for the end of the Task
    halt: str = ""  # an outcome, when the walk is over
    message: str = ""
    after: list[Step] = field(default_factory=list)


@dataclass
class _Answer:
    """A condition's answer under the policy: True, False, or None when the walk has to stop; and how it came out."""

    value: bool | None
    why: str
    needed: list[str] = field(default_factory=list)


@dataclass
class _Loop:
    """A For in progress: its items, and which one it is on."""

    variable: str
    items: list[str]
    position: int = 0


class _Walk:
    """One dry run: the Task's structure, the variables, and where the walk is."""

    def __init__(self, flow: taskflow.Flow, actions: list[Element], options: Options) -> None:
        """`flow` is taskflow's reading of the Task, `actions` its action elements in the Map's order."""
        self.flow = flow
        self.actions = actions
        self.options = options
        self.variables = Variables(options.variables)
        self.trace = Trace(task=flow.target.name, target=flow.target)
        self.loops: dict[int, _Loop] = {}
        self.visited: set[int] = set()
        self.previous = -1
        self.elses = {position: block for block in flow.blocks.values() for position in block.elses}
        self.closers = {
            block.end: block for block in flow.blocks.values() if block.end is not None and block.kind == "For"
        }
        self.labels = taskflow.labels_of(flow.steps)
        self.handlers = self._handlers()

    # -- the loop ------------------------------------------------------------------
    def run(self) -> Trace:
        """Walk from the first action until the Task ends, stops, needs something, or runs too long."""
        position: int | None = 0 if self.flow.steps else None
        count = 0
        while position is not None and not self.trace.message:
            if count >= self.options.max_steps:
                self._end(STEP_LIMIT, f"Stopped after {count} actions -- the Task may go round forever.")
                break
            count += 1
            position = self._execute(position)
        self._finish()
        return self.trace

    def _finish(self) -> None:
        """Fill in what the walk ended with."""
        if not self.trace.message and self.trace.outcome == FINISHED:
            self.trace.message = "Ran to the end of the Task."
        self.trace.variables = self.variables.snapshot()
        self.trace.not_reached = [
            step.number for index, step in enumerate(self.flow.steps) if index not in self.visited and not step.disabled
        ]

    def _end(self, outcome: str, message: str) -> None:
        """Record how the walk ended."""
        self.trace.outcome = outcome
        self.trace.message = message

    def _execute(self, position: int) -> int | None:
        """Do the action at `position`, record it, and say where the walk goes next."""
        step, action = self.flow.steps[position], self.actions[position]
        self.visited.add(position)
        before = self.variables.snapshot()
        result = self._decide_action(position, step, action)
        self._apply_assumed(step, result)
        if result.status:
            self._record(position, result, before)
        self.trace.steps.extend(result.after)
        self.previous = position
        if result.halt:
            self._end(result.halt, result.message)
            return None
        following = self._after(position) if result.next == FALL else result.next
        # A jump past the last action -- out of a loop that is the last thing in the Task -- is the end of it.
        return following if following is None or following < len(self.flow.steps) else None

    def _after(self, position: int) -> int | None:
        """The action reached by finishing this one: the next, except that an If's true branch skips its Elses."""
        following = position + 1
        if following >= len(self.flow.steps):
            return None
        block = self.elses.get(following)
        if block is not None and block.open < position:
            return block.end
        return following

    def _record(self, position: int, result: _Result, before: dict[str, str]) -> None:
        """Add a step to the trace, with what it changed."""
        step = self.flow.steps[position]
        after = self.variables.snapshot()
        changes = [Change(name, before.get(name, ""), after[name]) for name in after if before.get(name) != after[name]]
        changes += [Change(name, before[name], "") for name in before if name not in after]
        self.trace.steps.append(
            Step(
                number=step.number,
                name=step.name,
                text=result.text,
                status=result.status,
                detail=result.detail,
                changes=changes,
                variables=after,
                depth=self.flow.depth[position] if position < len(self.flow.depth) else 0,
            ),
        )

    # -- conditions ----------------------------------------------------------------
    def _read(self, text: str) -> tuple[str, list[str]]:
        """Substitute variables, treating a variable with no value as not set when the policy says so."""
        value, needed = self.variables.substitute(text)
        return value, [] if self.options.policy == POLICY_UNSET else needed

    def _one(self, condition: Element) -> Verdict:
        """One <Condition>: its two sides with the variables filled in, and what the comparison came to."""
        code = (condition.findtext("op") or "").strip()
        left_raw, right_raw = (condition.findtext("lhs") or "").strip(), (condition.findtext("rhs") or "").strip()
        left, needed = self._read(left_raw)
        if code in _UNARY:
            value = None if needed else (left not in (left_raw, "")) == (code == _IS_SET)
            return Verdict(value, f"{left_raw} {_SYMBOL[code]}", needed)
        right, more = self._read(right_raw)
        symbol = _SYMBOL.get(code, f"operator {code}")
        shown = f"{_shorten(left, 40)} {symbol} {_shorten(right, 40)}"
        if needed or more:
            return Verdict(None, f"{left_raw} {symbol} {right_raw}", [*needed, *more])
        return Verdict(_compare(code, left, right), shown)

    def _condition(self, element: Element) -> Verdict:
        """A <ConditionList>: each condition, joined as Tasker joins them."""
        conditions = element.findall("Condition")
        verdicts = [self._one(condition) for condition in conditions]
        if not verdicts:
            return Verdict(True)
        joiners = [joiner.strip().lower() for joiner in boolean_operators(element, len(verdicts))]
        value = _join([verdict.value for verdict in verdicts], joiners)
        names = [name for verdict in verdicts for name in verdict.needed]
        text = (
            f" {joiners[0] if joiners else ''} ".join(verdict.text for verdict in verdicts)
            if len(set(joiners)) <= 1
            else "; ".join(verdict.text for verdict in verdicts)
        )
        return Verdict(value, text, names)

    def _judge(self, element: Element) -> _Answer:
        """A condition's answer under the policy.  `value` None means the walk must stop here."""
        verdict = self._condition(element)
        if verdict.value is not None:
            return _Answer(verdict.value, f"{verdict.text} -> {'true' if verdict.value else 'false'}")
        for name in verdict.needed:
            if name not in self.trace.needed:
                self.trace.needed.append(name)
        names = ", ".join(dict.fromkeys(f"%{name}" for name in verdict.needed)) or "values it cannot compare"
        if self.options.policy in (POLICY_TRUE, POLICY_FALSE):
            assumed = self.options.policy == POLICY_TRUE
            return _Answer(assumed, f"{verdict.text} -> assumed {'true' if assumed else 'false'} ({names})")
        return _Answer(None, f"{verdict.text}: needs {names}", list(dict.fromkeys(verdict.needed)))

    # -- one action ----------------------------------------------------------------
    def _decide_action(self, position: int, step: taskflow.Step, action: Element) -> _Result:
        """Run one action, or step over it: disabled, or with its own If false."""
        if step.disabled:
            return _Result(step.name, DISABLED, "switched off, so Tasker steps over it")
        own = action.find("ConditionList")
        if own is not None and step.code not in (_IF, _ELSE):
            answer = self._judge(own)
            if answer.value is None:
                return self._needs(step, answer)
            if not answer.value:
                return _Result(self._describe(step, action), SKIPPED, f"its If is false: {answer.why}")
        handler = self.handlers.get(step.code)
        if handler is not None:
            return handler(position, step, action)
        return self._other(step, action)

    def _handlers(self) -> dict[str, Callable[[int, taskflow.Step, Element], _Result]]:
        """The actions the walk interprets, by code."""
        return {
            _IF: self._if,
            _ELSE: self._else,
            _END_IF: self._noop,
            _FOR: self._for,
            _END_FOR: self._end_for,
            _GOTO: self._goto,
            _STOP: self._stop,
            _RETURN: self._return,
            _VAR_SET: self._variable_set,
            _VAR_ADD: self._variable_add,
            _VAR_CLEAR: self._variable_clear,
            _VAR_SPLIT: self._variable_split,
        }

    def _needs(self, step: taskflow.Step, answer: _Answer) -> _Result:
        """A condition the walk cannot decide and was told to stop at."""
        names = ", ".join(f"%{name}" for name in answer.needed) or "values it cannot compare"
        return _Result(
            step.name,
            UNDECIDED,
            answer.why,
            next=None,
            halt=NEEDS_VALUE,
            message=f"Stopped at action {step.number}: it depends on {names}.  "
            "Give them starting values, or choose another way to treat missing values.",
        )

    def _noop(self, _position: int, step: taskflow.Step, _action: Element) -> _Result:
        """End If: nothing to do, and nothing worth a line."""
        return _Result(step.name, "")

    # -- description ---------------------------------------------------------------
    def _arguments(self, step: taskflow.Step, action: Element) -> list[tuple[str, str]]:
        """The arguments the action has filled in, as (name, value with variables substituted)."""
        entry = action_codes.get(f"{step.code}t")
        found = []
        for argument in entry.args if entry is not None else []:
            raw = taskflow.action_argument(action, argument.arg_id)
            if raw:
                value, _ = self.variables.substitute(raw)
                found.append((argument.arg_name, value))
        return found

    def _describe(self, step: taskflow.Step, action: Element) -> str:
        """'Flash: Text = 'Hello 5'' -- the action with the variables filled in."""
        shown = [
            f"{name} = '{_shorten(value, 60)}'" for name, value in self._arguments(step, action)[:_ARGUMENTS_SHOWN]
        ]
        return f"{step.name}: {', '.join(shown)}" if shown else step.name

    def _other(self, step: taskflow.Step, action: Element) -> _Result:
        """An action the walk does not interpret: shown, with what it may leave behind marked unknown."""
        text = self._describe(step, action)
        if step.code in _SHOWN_ONLY:
            return _Result(text, RAN, "shown, not performed")
        outputs = _outputs(step.code, action)
        for name in outputs:
            self.variables.mark_unknown(name)
        left = f"; may set {', '.join('%' + name for name in outputs)}" if outputs else ""
        if step.code == _JAVASCRIPTLET:
            left += "; may have changed any variable -- later values assume it did not"
        return _Result(text, NOT_SIMULATED, f"not simulated{left}")

    def _apply_assumed(self, step: taskflow.Step, result: _Result) -> None:
        """What the user said an action leaves behind, applied after it."""
        assumed = self.options.assumed.get(step.number)
        if not assumed:
            return
        for name, value in assumed.items():
            self.variables.put(name.lstrip("%"), value)
        if result.status == NOT_SIMULATED:
            result.status = ASSUMED
        result.detail = f"{result.detail}; you said it leaves " + ", ".join(
            f"%{n.lstrip('%')} = '{v}'" for n, v in assumed.items()
        )

    # -- control flow --------------------------------------------------------------
    def _if(self, position: int, step: taskflow.Step, action: Element) -> _Result:
        """If: take the body, or go to the first Else whose condition holds, or past the End If."""
        block = self.flow.blocks.get(position)
        condition = action.find("ConditionList")
        answer = self._judge(condition) if condition is not None else _Answer(True, "no condition")
        if answer.value is None:
            return self._needs(step, answer)
        if answer.value:
            return _Result(f"If {answer.why}", TAKEN, "runs the actions below")
        return self._alternative(block, position, f"If {answer.why}")

    def _alternative(self, block: taskflow.Block | None, position: int, said: str) -> _Result:
        """An If whose condition was false: walk its Elses for one that holds.

        The Elses passed through are lines of their own, recorded after the If's.
        """
        passed: list[Step] = []
        for index in block.elses if block is not None else []:
            if index < position:
                continue
            action, step = self.actions[index], self.flow.steps[index]
            self.visited.add(index)
            condition = action.find("ConditionList")
            if condition is None or not step.condition:
                passed.append(self._branch(index, "Else", TAKEN, "runs the actions below"))
                return _Result(
                    said, NOT_TAKEN, f"goes to the Else at action {step.number}", next=index + 1, after=passed
                )
            answer = self._judge(condition)
            if answer.value is None:
                return self._needs(step, answer)
            if answer.value:
                passed.append(self._branch(index, f"Else If {answer.why}", TAKEN, "runs the actions below"))
                return _Result(
                    said, NOT_TAKEN, f"goes to the Else If at action {step.number}", next=index + 1, after=passed
                )
            passed.append(self._branch(index, f"Else If {answer.why}", NOT_TAKEN, "tries the next branch"))
        end = block.end if block is not None else None
        return _Result(
            said, NOT_TAKEN, "skips to after the End If", next=None if end is None else end + 1, after=passed
        )

    def _branch(self, index: int, text: str, status: str, detail: str) -> Step:
        """The line for an Else or Else If the walk passed through while choosing a branch."""
        step = self.flow.steps[index]
        return Step(step.number, step.name, text, status, detail, [], self.variables.snapshot(), self.flow.depth[index])

    def _else(self, position: int, step: taskflow.Step, _action: Element) -> _Result:
        """An Else reached by running off the end of a branch: its If is done, so go past the End If."""
        block = next((candidate for candidate in self.flow.blocks.values() if position in candidate.elses), None)
        end = block.end if block is not None else None
        return _Result(step.name, "", next=None if end is None else end + 1)

    def _for(self, position: int, step: taskflow.Step, action: Element) -> _Result:
        """For: start the loop, or move on to its next item; leave it when the items are used up."""
        block = self.flow.blocks.get(position)
        loop = self.loops.get(position)
        inside = block is not None and block.end is not None and block.open < self.previous <= block.end
        if loop is None or not inside:
            loop, needed = self._start_loop(action)
            if needed and self.options.policy == POLICY_STOP:
                self.trace.needed.extend(name for name in needed if name not in self.trace.needed)
                why = f"For %{loop.variable}: the items depend on a variable with no value"
                return self._needs(step, _Answer(None, why, needed))
            self.loops[position] = loop
        else:
            loop.position += 1
        exit_to = None if block is None or block.end is None else block.end + 1
        if loop.position >= len(loop.items):
            self.loops.pop(position, None)
            return _Result(f"For %{loop.variable}", NOT_TAKEN, "no more items: leaves the loop", next=exit_to)
        self.variables.put(loop.variable, loop.items[loop.position])
        return _Result(
            f"For %{loop.variable} = '{_shorten(loop.items[loop.position], 40)}'",
            TAKEN,
            f"item {loop.position + 1} of {len(loop.items)}",
        )

    def _start_loop(self, action: Element) -> tuple[_Loop, list[str]]:
        """A new loop -- the variable it sets and the items it goes through -- and the variables the items needed."""
        name = taskflow.action_argument(action, "0").lstrip("%")
        items_text, needed = self.variables.substitute(taskflow.action_argument(action, "1"))
        ranged = _RANGE.match(items_text)
        if ranged:
            first, last = int(ranged[1]), int(ranged[2])
            step = 1 if last >= first else -1
            items = [str(value) for value in range(first, last + step, step)][:_MAX_ITEMS]
        else:
            items = [item.strip() for item in items_text.split(",") if item.strip()][:_MAX_ITEMS]
        return _Loop(name, items), list(dict.fromkeys(needed))

    def _end_for(self, position: int, step: taskflow.Step, _action: Element) -> _Result:
        """End For: back to its For, which moves to the next item.  Not worth a line of its own."""
        block = self.closers.get(position)
        return _Result(step.name, "", next=block.open if block is not None else FALL)

    def _goto(self, position: int, step: taskflow.Step, _action: Element) -> _Result:
        """Goto: where taskflow resolved it, or where its number or label comes out as now the variables are filled in."""
        jump = self.flow.jumps.get(position)
        target = jump.target if jump is not None else None
        if target is None and step.goto is not None:
            target = self._late_target(step)
        if target is None:
            return _Result(f"Goto {step.detail}", NOT_TAKEN, "lands nowhere, so Tasker carries on with the next action")
        return _Result(f"Goto {step.detail}", TAKEN, f"jumps to action {target + 1}", next=target)

    def _late_target(self, step: taskflow.Step) -> int | None:
        """A Goto whose number or label held a variable: now it has its value."""
        goto_type, number, label = step.goto or ("", "", "")
        if goto_type == taskflow.GOTO_ACTION_NUMBER:
            value, _ = self.variables.substitute(number)
            return int(value) - 1 if value.isdigit() and 1 <= int(value) <= len(self.flow.steps) else None
        if goto_type == taskflow.GOTO_ACTION_LABEL:
            value, _ = self.variables.substitute(label)
            found = self.labels.get(value, [])
            return found[0] if found else None
        return None

    def _stop(self, _position: int, step: taskflow.Step, action: Element) -> _Result:
        """Stop: ends this Task if it names none (or itself); otherwise stops another and carries on."""
        if not step.terminates:
            named = taskflow.action_argument(action, "1")
            return _Result(f"Stop task '{named}'", RAN, "stops another Task and carries on here")
        return _Result("Stop", ENDED, "ends the Task here", next=None, halt=STOPPED, message="Ended by a Stop action.")

    def _return(self, _position: int, _step: taskflow.Step, action: Element) -> _Result:
        """Return: ends the Task and hands back a value."""
        value, _ = self.variables.substitute(taskflow.action_argument(action, "0"))
        return _Result(
            f"Return '{_shorten(value, 60)}'",
            ENDED,
            "ends the Task here",
            next=None,
            halt=RETURNED,
            message=f"Returned '{_shorten(value, 60)}'.",
        )

    # -- variables -----------------------------------------------------------------
    def _target_name(self, action: Element, arg: str = "0") -> str:
        """The variable an action names.

        The name is written %like_this and IS the variable's name -- it is not looked up.  Only what follows
        the first name is: %arr%i is %arr followed by whatever %i holds.
        """
        written = taskflow.action_argument(action, arg).strip()
        match = _NAME.match(written)
        if match is None:
            return self.variables.substitute(written)[0].lstrip("%")
        return match["head"] + self.variables.substitute(match["rest"])[0]

    def _variable_set(self, _position: int, step: taskflow.Step, action: Element) -> _Result:
        """Variable Set: To, with Recurse, Do Maths and Append."""
        name = self._target_name(action)
        raw = taskflow.action_argument(action, "1")
        value, needed = self.variables.substitute(raw)
        for _ in range(_MAX_RECURSION if taskflow.action_argument(action, "2") == "1" else 0):
            value, more = self.variables.substitute(value)
            needed += more
        unknown = [item for item in needed if item in self.variables.unknown]
        if unknown:
            # Copying (or building from) something that has a value the walk cannot say: so has the target.
            self.variables.mark_unknown(name)
            return _Result(
                f"{step.name}: %{name} = '{_shorten(raw, 80)}'",
                NOT_SIMULATED,
                f"depends on %{unknown[0]}, which is unknown; %{name} is now unknown",
            )
        note = ""
        if needed and taskflow.action_argument(action, "3") == "1":
            note = f"; %{needed[0]} has no value, so the maths was left as written"
        elif taskflow.action_argument(action, "3") == "1":
            value, note = self._maths(value, action)
        if taskflow.action_argument(action, "4") == "1":
            value = self.variables.get(name) + value
        self.variables.put(name, value)
        return _Result(f"{step.name}: %{name} = '{_shorten(value, 80)}'", RAN, note.lstrip("; "))

    def _maths(self, value: str, action: Element) -> tuple[str, str]:
        """The value after Do Maths, and a note if it could not be done."""
        result = calculate(value)
        if result is None:
            return value, "Do Maths could not read this as arithmetic, so it is left as written"
        digits = taskflow.action_argument(action, "5")
        return _format(result, int(digits) if digits.isdigit() else _DEFAULT_ROUNDING), ""

    def _variable_add(self, _position: int, step: taskflow.Step, action: Element) -> _Result:
        """Variable Add: the name plus a value, wrapping round at the third argument."""
        name = self._target_name(action)
        amount, needed = self.variables.substitute(taskflow.action_argument(action, "1"))
        wrap = _number(taskflow.action_argument(action, "2")) or 0
        current = self.variables.get(name) or "0"
        if needed or name in self.variables.unknown or _number(current) is None or _number(amount) is None:
            self.variables.mark_unknown(name)
            return _Result(
                f"{step.name}: %{name} += '{amount}'",
                NOT_SIMULATED,
                "needs numbers it does not have; %" + name + " is now unknown",
            )
        total = (_number(current) or 0) + (_number(amount) or 0)
        if wrap:
            total %= wrap
        self.variables.put(name, _format(total))
        return _Result(f"{step.name}: %{name} += {amount}", RAN)

    def _variable_clear(self, _position: int, step: taskflow.Step, action: Element) -> _Result:
        """Variable Clear: one name, a pattern of them, or all."""
        if taskflow.action_argument(action, "3") == "1":
            cleared = list(self.variables.values)
        else:
            name = self._target_name(action)
            pattern = taskflow.action_argument(action, "1") == "1"
            cleared = [key for key in self.variables.values if fnmatch.fnmatchcase(key, name)] if pattern else [name]
        for key in cleared:
            self.variables.forget(key)
        return _Result(f"{step.name}: {', '.join('%' + key for key in cleared[:5]) or 'nothing'}", RAN)

    def _variable_split(self, _position: int, step: taskflow.Step, action: Element) -> _Result:
        """Variable Split: name -> name1, name2, ... (and the original removed when asked)."""
        name = self._target_name(action)
        splitter, _ = self.variables.substitute(taskflow.action_argument(action, "1"))
        if not self.variables.has(name) or not splitter:
            self.variables.mark_unknown(name)
            return _Result(
                f"{step.name}: %{name}", NOT_SIMULATED, "no value or no splitter to go by; the parts are unknown"
            )
        value = self.variables.get(name)
        regex = taskflow.action_argument(action, "3") == "1"
        try:
            parts = re.split(splitter, value) if regex else value.split(splitter)
        except re.error:
            return _Result(f"{step.name}: %{name}", NOT_SIMULATED, "the splitter is not a valid regex")
        if taskflow.action_argument(action, "2") == "1":
            self.variables.forget(name)
        for number, part in enumerate(parts, start=1):
            self.variables.put(f"{name}{number}", part)
        return _Result(f"{step.name}: %{name} into {len(parts)} parts", RAN)


# ##################################################################################
# Asking.
# ##################################################################################
def find_task(name_or_id: str, state: RunState) -> tuple[str, Element] | None:
    """(id, element) of the Task with this name or id, or None.  A name wins over an id that happens to match."""
    tables = state.tasker_root_elements
    by_name = tables.get("all_tasks_by_name", {}).get(name_or_id)
    task_id = by_name["id"] if isinstance(by_name, dict) and "id" in by_name else name_or_id
    entry = tables.get("all_tasks", {}).get(task_id)
    return (task_id, entry["xml"]) if isinstance(entry, dict) else None


def step_task(name_or_id: str, state: RunState, options: Options | None = None) -> Trace | None:
    """Dry-run one Task.  None when there is no such Task loaded."""
    found = find_task(name_or_id, state)
    if found is None:
        return None
    task_id, element = found
    flow = taskflow.analyze_task_flow(task_id, state=state)
    if flow is None:
        return None
    return _Walk(flow, actions_in_map_order(element), options or Options()).run()


def inputs_needed(name_or_id: str, state: RunState) -> list[str]:
    """The variables a Task reads before anything in it sets them -- what it needs given at the start.

    Read in the order the actions are written, ignoring which branch they are on: a variable set in one
    branch and read in another is listed if the read comes first, which errs towards asking.
    """
    found = find_task(name_or_id, state)
    if found is None:
        return []
    _, element = found
    set_here: set[str] = set()
    needed: list[str] = []
    for action in actions_in_map_order(element):
        code = (action.findtext("code") or "").strip()
        assigns = code in (_VAR_SET, _VAR_ADD, _FOR, _VAR_SPLIT)
        # The variable an assigning action names in its first argument is written, not read.
        text = " ".join(
            (child.text or child.attrib.get("val", "") or "")
            for child in action.iter()
            if child.tag in {"Str", "lhs", "rhs"} and not (assigns and child.attrib.get("sr") == "arg0")
        )
        written = set(_outputs(code, action))
        for match in _VARIABLE.finditer(text):
            name = match["name"]
            if name not in set_here and name not in needed and name not in written:
                needed.append(name)
        set_here |= written
        if assigns:
            set_here.add(taskflow.action_argument(action, "0").lstrip("%"))
    return needed


def _outputs(code: str, action: Element) -> list[str]:
    """The variables an action is known or likely to write: its fixed ones, and those named in its output arguments."""
    names = list(_FIXED_OUTPUTS.get(code, ()))
    entry = action_codes.get(f"{code}t")
    explicit = _NAMED_OUTPUTS.get(code, ())
    for argument in entry.args if entry is not None else []:
        if argument.arg_id in explicit or _OUTPUT_ARGUMENT.search(argument.arg_name or ""):
            value = taskflow.action_argument(action, argument.arg_id)
            names += [match["name"] for match in _VARIABLE.finditer(value) if value.startswith("%")]
    return list(dict.fromkeys(names))


def named_tasks(state: RunState) -> list[str]:
    """The names of the Tasks that have one -- what a person can pick from -- in alphabetical order."""
    names = {
        entry["name"]
        for entry in state.tasker_root_elements.get("all_tasks", {}).values()
        if isinstance(entry, dict) and entry.get("name")
    }
    return sorted(names, key=str.casefold)


def global_values(state: RunState) -> dict[str, str]:
    """The global variables as the loaded backup holds them: {name without %: value}.

    The values are what they were on the phone when the backup was taken, which is the best answer there is to
    "what do the globals hold?" -- and a Task that reads one decides by it.
    """
    root = getattr(state, "xml_root", None)
    if root is None:
        return {}
    found = {}
    for item in root.findall("Variable"):
        name = (item.findtext("n") or "").strip().lstrip("%")
        if name:
            found[name] = (item.findtext("v") or "").strip()
    return found


def parse_assignments(text: str) -> tuple[dict[str, str], list[str]]:
    """Variables typed one per line as '%name = value' -- ({name: value}, the lines that could not be read).

    A line with nothing after the = is a variable the user listed and has no value for yet, and is left out; blank
    lines are ignored.  The value is everything after the first =, so a value may contain one.
    """
    found: dict[str, str] = {}
    bad: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        name, separator, value = line.partition("=")
        name = name.strip().lstrip("%")
        written = _NAME.match(f"%{name}")
        if not separator or written is None or written["rest"]:
            bad.append(line.strip())
        elif value.strip():
            found[name] = value.strip()
    return found, bad


def parse_assumed(text: str) -> tuple[dict[int, dict[str, str]], list[str]]:
    """What an action that is not simulated leaves, typed as '5: %name = value' -- ({action: {name: value}}, bad lines)."""
    found: dict[int, dict[str, str]] = {}
    bad: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        number, separator, rest = line.partition(":")
        values, problems = parse_assignments(rest)
        if not separator or not number.strip().isdigit() or problems or not values:
            bad.append(line.strip())
        else:
            found.setdefault(int(number), {}).update(values)
    return found, bad
