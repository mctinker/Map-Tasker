"""taskflow: a Task's control flow -- whether it holds together, and what it looks like."""

#! /usr/bin/env python3

#                                                                                       #
# taskflow: read a Task's If / Else / End If, For / End For, Goto and Stop as a          #
#           structure rather than as a list -- report what does not hold together, and   #
#           draw one Task as a flowchart.                                                #
#                                                                                        #
# Same contract as healthck.py and varxref.py: everything here reads                     #
# PrimeItems.tasker_root_elements and nothing else -- no GUI, no output_lines, no        #
# generated HTML.  The checks therefore run the moment an XML file is loaded (no Map run #
# required) and are testable without standing up a GUI.                                  #
#                                                                                        #
# The dependency runs healthck -> taskflow, never the other way: healthck folds the      #
# findings below into its own report, exactly as it folds in varxref's suspects.  That   #
# is why the two severity words are spelled out again here rather than imported from     #
# healthck -- importing it back would be a cycle.  mapfind.py repeats healthck's own     #
# four for the same reason.                                                              #
#                                                                                        #
# Why any of it.  The Map lists a Task's actions in the order they are written, and that #
# is the one thing a reader cannot turn into an answer: which actions actually run, in   #
# what order, and where a Goto lands.  Everything below is built on one small            #
# control-flow graph per Task -- each action's possible next actions -- because both     #
# halves of this module need exactly that.  The lint is questions asked of the graph     #
# ("can anything arrive at action 12?"); the flowchart is the graph drawn.               #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from maptasker.src.actionc import action_codes
from maptasker.src.mapjump import (
    TASK,
    Row,
    Target,
    actions_in_map_order,
    text_report,
)
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    FLOWCHART_FILE,
    MY_VERSION,
    TASKFLOW_FILE,
    logger,
)

if TYPE_CHECKING:
    import defusedxml.ElementTree  # Need for type hints

# The same two words healthck grades by, spelled out again rather than imported: healthck
# imports this module to fold these findings in, so importing it back would be a cycle.
# There is no INFO here -- nothing this module can see is merely worth knowing about.  A
# block that never closes and a Goto with nowhere to land are both defects; the split is
# between "the device will do the wrong thing" and "the device will do nothing at all".
ERROR = "ERROR"
WARNING = "WARNING"

_SEVERITY_ORDER = (ERROR, WARNING)
_SEVERITY_HEADINGS = {
    ERROR: "ERRORS -- these will misbehave on the device",
    WARNING: "WARNINGS -- probably not what you intended",
}

_REPORT_WIDTH = 78

# Tasker's control-flow action codes.  These are the whole of the structure: every other
# action is a straight line from the one above it to the one below.
_IF = "37"
_ELSE = "43"  # "Else" and "Else If" are one action; the "If" half is a condition on it.
_END_IF = "38"
_FOR = "39"
_END_FOR = "40"
_GOTO = "135"
_STOP = "137"
_RETURN = "126"
_PERFORM_TASK = "130"

_BLOCK_OPENERS = {_IF: "If", _FOR: "For"}
_BLOCK_CLOSERS = {_END_IF: "If", _END_FOR: "For"}
# Actions that end the Task where they stand.  Return ends the Task it is in exactly as
# Stop does -- the difference between them is what they hand back to a caller, which
# control flow inside this Task does not care about.
_TERMINATORS = frozenset({_STOP, _RETURN})

# Goto's arg0 -- which kind of destination its other two arguments name.  The values are
# positions in actiont.py's list "135": Action Number, Action Label, Top of Loop, End of
# Loop, End of If.
_GOTO_ACTION_NUMBER = "0"
_GOTO_ACTION_LABEL = "1"
_GOTO_TOP_OF_LOOP = "2"
_GOTO_END_OF_LOOP = "3"
_GOTO_END_OF_IF = "4"
# Which block kind each of the last three names, and how the phrase reads in a report.
_GOTO_BLOCK_KINDS = {_GOTO_TOP_OF_LOOP: "For", _GOTO_END_OF_LOOP: "For", _GOTO_END_OF_IF: "If"}
# Block kinds a Goto may name from outside without it being a defect -- see _goto_by_block.
_GOTO_BLOCKS_ALLOWED_LOOSE = frozenset({"For"})
# The two kinds of block a Task can open, spelled the way Block.kind spells them.  Named so
# the tag families below can be built from them rather than transcribed.
_BLOCK_KINDS = ("If", "For")
_GOTO_PHRASES = {
    _GOTO_TOP_OF_LOOP: "top of loop",
    _GOTO_END_OF_LOOP: "end of loop",
    _GOTO_END_OF_IF: "end of If",
}

# Every tag this module raises, including the ones built from a block's kind rather than
# written out ("FLOW-END-IF-WITHOUT-IF" and friends).  Exported for proflint.TAGS' reason
# and one more: healthck offers the user a checkbox per category of finding, and a family
# spelled out only inside an f-string could not be offered at all.
TAGS: frozenset[str] = frozenset(
    {
        "FLOW-MISMATCHED-BLOCK",
        "FLOW-ELSE-WITHOUT-IF",
        "FLOW-GOTO-MISSING-LABEL",
        "FLOW-GOTO-BAD-NUMBER",
        "FLOW-DUPLICATE-LABEL",
        "FLOW-UNREACHABLE",
    }
    | {f"FLOW-END-{kind.upper()}-WITHOUT-{kind.upper()}" for kind in _BLOCK_KINDS}
    | {f"FLOW-{kind.upper()}-WITHOUT-END-{kind.upper()}" for kind in _BLOCK_KINDS}
    | {f"FLOW-GOTO-OUTSIDE-{kind.upper()}" for kind in set(_GOTO_BLOCK_KINDS.values()) - _GOTO_BLOCKS_ALLOWED_LOOSE}
)

# How a condition's <op> reads.  action.py's own table, in symbols rather than words: this
# goes inside a flowchart node, where "%i > 5" fits and " > " as prose does not.
_OPERATORS = {
    "0": "=",
    "1": "!=",
    "2": "~",
    "3": "!~",
    "4": "~R",
    "5": "!~R",
    "6": "<",
    "7": ">",
    "8": "=",
    "9": "!=",
    "12": "is set",
    "13": "is not set",
}
_UNARY_OPERATORS = frozenset({"is set", "is not set"})

# A name holding a variable is decided on the device at run time.  healthck's rule, for
# healthck's reason: reporting one as broken would be a false alarm on a configuration
# that works perfectly, and one of those makes the whole report untrustworthy.
_VARIABLE_MARKER = "%"

# How much of an action the flowchart prints before cutting it short.  Long enough for a
# condition and a label, short enough that the jump gutter drawn to the right of the text
# is still on screen at a sane window width.
_TEXT_LIMIT = 96
_LABEL_LIMIT = 40


# ##################################################################################
# What the walk over a Task produces.
# ##################################################################################
@dataclass
class Step:
    """One action of a Task, read for its control flow and nothing else.

    'number' is the number the Map prints, which is the number the user can find -- see
    mapjump.actions_in_map_order for why that is not the action's position in the file.

    'label' is flattened and shortened for printing; 'raw_label' is what Tasker actually
    stored, which is what a Goto's label has to be matched against.  Keeping both is what
    stops a jump to a label 45 characters long from being reported as missing.
    """

    number: int
    code: str
    name: str
    label: str
    raw_label: str
    condition: str  # "" when the action carries no <ConditionList sr="if">
    detail: str  # the arguments a flowchart needs: a Goto's target, a For's list
    disabled: bool
    # Whether the action ends THIS Task where it stands.  Not the same question as "is it
    # a Stop": a Stop naming another Task stops that one and carries straight on here.
    terminates: bool = False
    # Goto's three arguments as Tasker wrote them: (type, action number, label).  None for
    # every other action.  Held raw rather than parsed back out of 'detail', which is
    # display text and free to be reworded.
    goto: tuple[str, str, str] | None = None


@dataclass
class Block:
    """One If/End If or For/End For pair, and the Elses in between.

    'end' is None for a block that is never closed -- a finding, not a reason to stop: the
    rest of the Task is still worth reading, and a half-open block simply has no exit edge.
    """

    kind: str  # "If" or "For"
    open: int
    end: int | None = None
    elses: list[int] = field(default_factory=list)


@dataclass
class Jump:
    """One Goto and the action it lands on.

    'resolved' False means the destination cannot be worked out from the XML -- a label
    built from a variable, or one that is simply not there.  Those are what make a
    reachability answer a guess rather than a fact, so the unreachable check stands down on
    a Task holding one (see _unreachable).
    """

    source: int
    target: int | None
    resolved: bool
    conditional: bool


@dataclass
class Problem:
    """One control-flow defect, ready to be printed by either report.

    'where' is a Target rather than a sentence so that a finding can be clicked: healthck
    folds these into its own findings unchanged, and both reports render the location line
    through the same mapjump machinery every other finding uses.
    """

    severity: str
    tag: str
    where: Target
    detail: str


@dataclass
class Flow:
    """One Task's control flow, whole.

    Held together rather than returned piecemeal because the flowchart needs every part of
    it: the steps to print, the depths to indent by, the jumps to draw arrows for, and the
    reachable set to mark what never runs.
    """

    target: Target
    steps: list[Step]
    depth: list[int]
    blocks: dict[int, Block]
    jumps: dict[int, Jump]
    reachable: set[int]
    problems: list[Problem]


# ##################################################################################
# Reading the XML.
# ##################################################################################
def _project_of_task() -> dict[str, str]:
    """{task id: owning Project name}, from each Project's <tids>.

    Built in one pass rather than by calling maputils.find_owning_project_for_task per
    Task: that one walks every Project, which would make a scan of the whole configuration
    quadratic.  healthck and varxref each keep their own copy of this for the same reason,
    and because all three promise to read nothing but PrimeItems.

    The filter on empty items is not decoration -- Tasker writes an empty list as an empty
    element, and "".split(",") is [""], which would claim a Project owns a Task whose id is
    the empty string.
    """
    owners = {}
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        text = (project["xml"].findtext("tids") or "").strip()
        for member in (item.strip() for item in text.split(",") if item.strip()):
            owners[member] = project_name
    return owners


def _argument(action: defusedxml.ElementTree.Element, arg_id: str) -> str:
    """One of an action's arguments, whichever shape Tasker wrote it in.

    Matched on the "sr" attribute rather than child order, which Tasker does not guarantee
    -- the same way taskedit.py, healthck.py and varxref.py each reach an argument.

    Both shapes are covered.  A text argument is <Str sr="argN">, but an argument Tasker
    expects a number in holds <Int sr="argN" val="3"/> -- or <Int sr="argN"><var>%N</var></Int>
    once a variable has been bound to it instead of a figure.  Goto needs all three: its
    type and its action number are Ints, its label is a Str, and any of them may hold a
    variable.
    """
    wanted = f"arg{arg_id}"
    for child in action:
        if child.attrib.get("sr") != wanted:
            continue
        if child.tag == "Int":
            variable = child.find("var")
            if variable is not None:
                return (variable.text or "").strip()
            return (child.attrib.get("val") or "").strip()
        return (child.text or "").strip()
    return ""


def _condition_text(action: defusedxml.ElementTree.Element) -> str:
    """An action's <ConditionList sr="if"> as one short line, or "" when it has none.

    Covers the per-action "If" Tasker allows on any action AND the If/Else actions
    themselves, whose condition IS that same element -- which is what lets one function
    answer "under what circumstances does this action run" for every action alike.

    The joiners live outside the conditions they join: Tasker writes <bool0>Or</bool0>
    before the pair it applies to, so the Nth joiner sits between condition N and N+1.
    """
    condition_list = action.find("ConditionList")
    if condition_list is None:
        return ""

    parts = []
    for position, condition in enumerate(condition_list.findall("Condition")):
        if position:
            parts.append((condition_list.findtext(f"bool{position - 1}") or "And").strip().upper())
        left = (condition.findtext("lhs") or "").strip()
        operator = _OPERATORS.get((condition.findtext("op") or "").strip(), "?")
        right = (condition.findtext("rhs") or "").strip()
        parts.append(f"{left} {operator}" if operator in _UNARY_OPERATORS else f"{left} {operator} {right}".rstrip())
    return " ".join(parts)


def _action_name(code: str) -> str:
    """What Tasker calls this action code, or "Action <code>" when the table has no name.

    One hop through 'redirect' because actionc.py files the plugin actions that share a
    configurator under a single entry, and it is that entry which carries the name.
    """
    entry = action_codes.get(f"{code}t")
    if entry is not None and entry.redirect:
        entry = action_codes.get(entry.redirect, entry)
    return entry.name if entry is not None and entry.name else f"Action {code}"


def _flatten(text: str, limit: int) -> str:
    """One line of at most `limit` characters.

    A Tasker label is free text and routinely holds newlines; a flowchart is a grid of
    columns, and one embedded newline in it moves every arrow drawn below that row.
    """
    single = " ".join(text.split())
    return f"{single[: limit - 3]}..." if len(single) > limit else single


def _goto_detail(goto: tuple[str, str, str]) -> str:
    """A Goto's destination as the user wrote it, before anything is resolved."""
    goto_type, number, label = goto
    if goto_type == _GOTO_ACTION_LABEL:
        return f"label '{_flatten(label, _LABEL_LIMIT)}'"
    if goto_type == _GOTO_ACTION_NUMBER:
        return f"action {number or '?'}"
    return _GOTO_PHRASES.get(goto_type, "?")


def _detail(code: str, action: defusedxml.ElementTree.Element, goto: tuple[str, str, str] | None) -> str:
    """The arguments worth putting in a flowchart node, which is very few of them.

    A flowchart answers "what runs next", so only the arguments that decide that earn a
    place: where a Goto goes, what a For walks, which Task a Perform Task hands control to.
    Every other action is named and left at that -- the Map is where an action reads out in
    full, and repeating that here would bury the shape of the Task in its own parameters.
    """
    if goto is not None:
        return _goto_detail(goto)
    if code == _FOR:
        return f"{_argument(action, '0')} in {_argument(action, '1')}".strip()
    if code == _PERFORM_TASK:
        name = _argument(action, "0")
        return f"'{name}'" if name else ""
    return ""


def _terminates(code: str, action: defusedxml.ElementTree.Element, task_name: str) -> bool:
    """Whether this action ends THIS Task's flow where it stands.

    A Stop with its Task argument left blank stops the Task it is written in, which is what
    strands everything below it.  A Stop that NAMES a Task stops that other Task and then
    carries on to the next action here -- an everyday way to shut down a companion Task --
    so reading it as the end of this one would strand the whole of the rest of the Task and
    invite somebody to delete actions that run every day.  A Stop naming this very Task is
    the exception: that one really does end the flow.

    A name built from a variable is decided on the device, so it is read as naming some
    other Task -- the answer that reports nothing rather than the one that guesses.
    """
    if code not in _TERMINATORS:
        return False
    if code != _STOP:
        return True
    named = _argument(action, "1")
    return not named or named == task_name


def _steps(task_element: defusedxml.ElementTree.Element, task_name: str = "") -> list[Step]:
    """A Task's actions, in the order the Map numbers them, read for their control flow."""
    steps = []
    for number, action in enumerate(actions_in_map_order(task_element), start=1):
        code = (action.findtext("code") or "").strip()
        goto = (_argument(action, "0"), _argument(action, "1"), _argument(action, "2")) if code == _GOTO else None
        raw_label = (action.findtext("label") or "").strip()
        steps.append(
            Step(
                number=number,
                code=code,
                name=_action_name(code),
                label=_flatten(raw_label, _LABEL_LIMIT),
                raw_label=raw_label,
                condition=_flatten(_condition_text(action), _TEXT_LIMIT),
                detail=_detail(code, action, goto),
                # <on> present is how Tasker records a disabled action -- see
                # action.get_label_disabled_condition, which reads the same element.
                disabled=action.find("on") is not None,
                terminates=_terminates(code, action, task_name),
                goto=goto,
            ),
        )
    return steps


# ##################################################################################
# Structure: matching the blocks, and finding the labels.
# ##################################################################################
def _close_block(stack: list[Block], closer: int, wanted: str, where: Target) -> Problem | None:
    """Close the innermost open block with an End If / End For, reporting a bad match.

    A closer that does not match what is open closes it anyway.  That is deliberate: the
    alternative -- leaving the block open -- turns one mistake into three findings (the
    mismatch, then the block that never closes, then everything after it reported
    stranded), when there is only one thing to go and fix.
    """
    if not stack:
        return Problem(
            ERROR,
            f"FLOW-END-{wanted.upper()}-WITHOUT-{wanted.upper()}",
            where.at_action(closer + 1),
            f"'End {wanted}' with no '{wanted}' open above it.",
        )

    block = stack.pop()
    block.end = closer
    if block.kind == wanted:
        return None
    return Problem(
        ERROR,
        "FLOW-MISMATCHED-BLOCK",
        where.at_action(closer + 1),
        f"'End {wanted}' closes the '{block.kind}' opened at action {block.open + 1}.",
    )


@dataclass
class _Structure:
    """What one pass over a Task's actions works out about its blocks.

    'enclosing' is kept because a Goto asks for it by name: "Top of Loop" and "End of Loop"
    mean the For this Goto is inside, and "End of If" the If it is inside, none of which
    can be answered from the Goto alone.
    """

    blocks: dict[int, Block] = field(default_factory=dict)
    depth: list[int] = field(default_factory=list)
    enclosing: list[tuple[Block, ...]] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)


def _match_blocks(steps: list[Step], where: Target) -> _Structure:
    """Pair every block opener with its closer, and report what does not pair up."""
    found = _Structure()
    stack: list[Block] = []

    for index, step in enumerate(steps):
        found.enclosing.append(tuple(stack))
        if step.code in _BLOCK_OPENERS:
            found.depth.append(len(stack))
            block = Block(_BLOCK_OPENERS[step.code], index)
            found.blocks[index] = block
            stack.append(block)
        elif step.code in _BLOCK_CLOSERS:
            problem = _close_block(stack, index, _BLOCK_CLOSERS[step.code], where)
            if problem is not None:
                found.problems.append(problem)
            found.depth.append(len(stack))
        elif step.code == _ELSE:
            found.depth.append(_record_else(stack, index, where, found.problems))
        else:
            found.depth.append(len(stack))

    found.problems += [
        Problem(
            ERROR,
            f"FLOW-{block.kind.upper()}-WITHOUT-END-{block.kind.upper()}",
            where.at_action(block.open + 1),
            f"'{block.kind}' opened here is never closed -- the Task ends with it still open.",
        )
        for block in stack
    ]
    return found


def _record_else(stack: list[Block], index: int, where: Target, problems: list[Problem]) -> int:
    """Attach an Else to the If it belongs to, and return the depth it is drawn at.

    An Else sits at its If's own depth, not one in: the Map and Tasker both show If, Else
    and End If as the three edges of one block, with only what is between them indented.
    """
    innermost = stack[-1] if stack else None
    if innermost is not None and innermost.kind == "If":
        innermost.elses.append(index)
        return len(stack) - 1
    problems.append(
        Problem(ERROR, "FLOW-ELSE-WITHOUT-IF", where.at_action(index + 1), "'Else' with no 'If' open above it."),
    )
    return len(stack)


def _labels(steps: list[Step]) -> dict[str, list[int]]:
    """{label: the indexes of every action carrying it}.

    Every label, not only the ones a Goto uses.  A Tasker label doubles as an action's
    comment, so most of these are prose that nothing points at -- which is exactly why a
    duplicate is only worth reporting once a Goto actually names it (see _goto_by_label).
    """
    found: dict[str, list[int]] = {}
    for index, step in enumerate(steps):
        if step.raw_label:
            found.setdefault(step.raw_label, []).append(index)
    return found


# ##################################################################################
# Where each Goto lands.
# ##################################################################################
def _goto_by_label(
    step: Step,
    labels: dict[str, list[int]],
    where: Target,
    problems: list[Problem],
) -> int | None:
    """Where a "Goto action label" lands, reporting a label that is not there.

    A label built from a variable is left alone rather than reported, for the reason
    healthck gives about every other unresolvable name: it is decided on the device, and
    calling it broken would be a false alarm on a Task that runs perfectly.
    """
    wanted = step.goto[2] if step.goto else ""
    shown = _flatten(wanted, _LABEL_LIMIT)
    if not wanted:
        problems.append(
            Problem(ERROR, "FLOW-GOTO-MISSING-LABEL", where.at_action(step.number), "'Goto' names no label at all."),
        )
        return None
    if _VARIABLE_MARKER in wanted:
        return None

    matches = labels.get(wanted, [])
    if not matches:
        problems.append(
            Problem(
                ERROR,
                "FLOW-GOTO-MISSING-LABEL",
                where.at_action(step.number),
                f"'Goto' jumps to label '{shown}', which no action in this Task carries.",
            ),
        )
        return None
    if len(matches) > 1:
        others = ", ".join(str(other + 1) for other in matches)
        problems.append(
            Problem(
                WARNING,
                "FLOW-DUPLICATE-LABEL",
                where.at_action(step.number),
                f"'Goto' jumps to label '{shown}', which actions {others} all carry -- Tasker takes the first.",
            ),
        )
    return matches[0]


def _goto_by_number(step: Step, count: int, where: Target, problems: list[Problem]) -> int | None:
    """Where a "Goto action number" lands, reporting a number that is not an action."""
    wanted = step.goto[1] if step.goto else ""
    if not wanted.isdigit():
        return None  # A variable, or nothing typed at all -- decided on the device.
    number = int(wanted)
    if 1 <= number <= count:
        return number - 1
    problems.append(
        Problem(
            ERROR,
            "FLOW-GOTO-BAD-NUMBER",
            where.at_action(step.number),
            f"'Goto' jumps to action {number}, and this Task has {count}.",
        ),
    )
    return None


def _goto_by_block(
    step: Step,
    enclosing: tuple[Block, ...],
    where: Target,
    problems: list[Problem],
) -> int | None:
    """Where a Top of Loop / End of Loop / End of If lands, reporting one with no block.

    All three name a block the Goto is inside.  Outside one there is nothing to name and
    Tasker does nothing -- a Goto that quietly falls through to the next action rather than
    one that fails, and so the quieter of the two severities.

    The loop pair are not reported.  Tasker is content to let a 'Goto top/end of loop' sit
    outside any For -- it is allowed, not a mistake -- so saying so would be a false alarm
    on a Task that works.  Where the destination still cannot be worked out, which is what
    keeps the unreachable check from guessing about the Task.
    """
    goto_type = step.goto[0] if step.goto else ""
    kind = _GOTO_BLOCK_KINDS[goto_type]
    block = next((item for item in reversed(enclosing) if item.kind == kind), None)
    if block is None:
        if kind not in _GOTO_BLOCKS_ALLOWED_LOOSE:
            problems.append(
                Problem(
                    WARNING,
                    f"FLOW-GOTO-OUTSIDE-{kind.upper()}",
                    where.at_action(step.number),
                    f"'Goto {step.detail}' is not inside a '{kind}', so there is nothing for it to jump to.",
                ),
            )
        return None
    return block.open if goto_type == _GOTO_TOP_OF_LOOP else block.end


def _resolve_gotos(
    steps: list[Step],
    enclosing: list[tuple[Block, ...]],
    labels: dict[str, list[int]],
    where: Target,
) -> tuple[dict[int, Jump], list[Problem]]:
    """Every Goto in the Task, and the action each one actually lands on."""
    jumps: dict[int, Jump] = {}
    problems: list[Problem] = []

    for index, step in enumerate(steps):
        if step.goto is None or step.disabled:
            continue
        goto_type = step.goto[0]
        if goto_type == _GOTO_ACTION_LABEL:
            target = _goto_by_label(step, labels, where, problems)
        elif goto_type == _GOTO_ACTION_NUMBER:
            target = _goto_by_number(step, len(steps), where, problems)
        elif goto_type in _GOTO_BLOCK_KINDS:
            target = _goto_by_block(step, enclosing[index], where, problems)
        else:
            target = None  # A Goto type this Tasker release did not have when this was written.
        jumps[index] = Jump(index, target, target is not None, bool(step.condition))

    return jumps, problems


# ##################################################################################
# Reachability: the control-flow graph, and what is not on it.
# ##################################################################################
def _fall_through(count: int, elses: dict[int, Block], index: int) -> int | None:
    """The action reached by simply finishing this one, or None at the end of the Task.

    Not always the next action.  Running off the end of an If's true branch does not fall
    into the Else below it -- that is the whole point of an Else -- it jumps past the End
    If.  Everything else really is "the next line", which is why this is the only special
    case here.
    """
    following = index + 1
    if following >= count:
        return None
    block = elses.get(following)
    if block is not None and block.open < index:
        return block.end
    return following


def _branch_successors(index: int, block: Block, elses_after: list[int]) -> set[int]:
    """Where a decision goes, both ways.

    An If (or an Else If) whose condition fails hands control to the next Else of the same
    block, and to the End If when there is not one.
    """
    alternative = elses_after[0] if elses_after else block.end
    return {index + 1} | ({alternative} if alternative is not None else set())


def _successors(steps: list[Step], blocks: dict[int, Block], jumps: dict[int, Jump]) -> dict[int, set[int]]:
    """Each action's possible next actions -- the whole control-flow graph.

    A disabled action is not a node with no successors, it is not there at all: Tasker
    steps straight over it, so it falls through like any other line.  That matters to the
    unreachable check, which would otherwise report the whole of a Task below a Stop
    somebody had already switched off.
    """
    elses = {position: block for block in blocks.values() for position in block.elses}
    closers = {block.end: block for block in blocks.values() if block.end is not None}
    graph: dict[int, set[int]] = {}

    for index, step in enumerate(steps):
        onward = _fall_through(len(steps), elses, index)
        default = {onward} if onward is not None else set()
        block = blocks.get(index)

        if step.disabled:
            graph[index] = default
        elif block is not None and block.kind == "If":
            graph[index] = _branch_successors(index, block, block.elses)
        elif block is not None:  # A For runs its body, or steps over it when the list is empty.
            graph[index] = {index + 1} | ({block.end + 1} if block.end is not None else set())
        elif index in elses:
            after = [other for other in elses[index].elses if other > index]
            graph[index] = _branch_successors(index, elses[index], after) if step.condition else {index + 1}
        elif step.code == _END_FOR and index in closers:
            # The one edge that runs backwards on its own: End For returns to its For, which
            # is what re-tests the list.  An End For with no For falls through instead.
            graph[index] = {closers[index].open}
        elif step.terminates:
            graph[index] = default if step.condition else set()
        elif index in jumps:
            graph[index] = _jump_successors(jumps[index], default)
        else:
            graph[index] = default

    return graph


def _jump_successors(jump: Jump, default: set[int]) -> set[int]:
    """Where a Goto goes.  An unresolved one is assumed to fall through rather than jump.

    Assumed, not known -- which is exactly why _unreachable declines to report anything
    about a Task holding one.
    """
    if not jump.resolved or jump.target is None:
        return default
    return {jump.target} | (default if jump.conditional else set())


def _reachable(graph: dict[int, set[int]], count: int) -> set[int]:
    """Every action a run of the Task can arrive at, walking out from action 1."""
    if not count:
        return set()
    seen = {0}
    pending = [0]
    while pending:
        index = pending.pop()
        for following in graph.get(index, ()):
            if 0 <= following < count and following not in seen:
                seen.add(following)
                pending.append(following)
    return seen


def _actionable_run(steps: list[Step], run: list[int]) -> list[int]:
    """The part of an unreachable run there is anything to say about.

    An End If or an End For is punctuation, not a step: it closes the block above it and
    does nothing else.  Reaching one is beside the point, and a run of nothing but closers
    -- the End If sitting directly under an unconditional Goto, the commonest shape there
    is -- is not a defect at all.  Trimmed from both ends so that the span a finding names
    begins and ends on an action the reader can actually do something about.
    """
    first, last = 0, len(run)
    while first < last and steps[run[first]].code in _BLOCK_CLOSERS:
        first += 1
    while last > first and steps[run[last - 1]].code in _BLOCK_CLOSERS:
        last -= 1
    return run[first:last]


def _unreachable_problem(steps: list[Step], run: list[int], where: Target) -> Problem:
    """One "nothing gets here" finding, naming the action that ended the flow above it."""
    first, last = steps[run[0]], steps[run[-1]]
    span = f"action {first.number}" if len(run) == 1 else f"actions {first.number}-{last.number}"
    culprit = next(
        (steps[index] for index in reversed(range(run[0])) if steps[index].terminates or steps[index].code == _GOTO),
        None,
    )
    because = (
        f"action {culprit.number} ('{culprit.name}') ends the flow above it and nothing jumps here"
        if culprit is not None
        else "nothing above falls into it and nothing jumps here"
    )
    return Problem(
        WARNING, "FLOW-UNREACHABLE", where.at_action(first.number), f"Nothing can reach {span} -- {because}."
    )


def _unreachable(steps: list[Step], jumps: dict[int, Jump], reachable: set[int], where: Target) -> list[Problem]:
    """Report the runs of actions nothing can arrive at.

    Stands down entirely on a Task holding a Goto whose destination could not be worked
    out.  One unknown jump could land anywhere, so every "nothing reaches this" answer in
    that Task would be a guess -- and a wrong one invites somebody to delete an action that
    runs every day.  healthck takes the same line wherever it cannot be sure.

    Reported as runs rather than one finding per action, because they come in runs:
    everything after an unconditional Stop is stranded together, and one finding naming the
    range is something a reader can act on where fifteen identical ones is not.
    """
    if any(not jump.resolved for jump in jumps.values()):
        return []

    problems: list[Problem] = []
    run: list[int] = []
    for index in [*range(len(steps)), None]:
        if index is not None and index not in reachable and not steps[index].disabled:
            run.append(index)
            continue
        if run:
            actionable = _actionable_run(steps, run)
            if actionable:
                problems.append(_unreachable_problem(steps, actionable, where))
            run = []
    return problems


# ##################################################################################
# The analysis, one Task at a time.
# ##################################################################################
def analyze_task_flow(task_id: str, project_name: str = "") -> Flow | None:
    """Read one Task's control flow, or None when no such Task is loaded.

    'project_name' saves the caller a walk over every Project when it already knows the
    answer -- a scan of the whole configuration builds that map once and passes it in.
    """
    task = PrimeItems.tasker_root_elements["all_tasks"].get(task_id)
    if task is None:
        return None

    where = Target(TASK, task_id, task["name"], project_name or _project_of_task().get(task_id, ""))
    steps = _steps(task["xml"], task["name"])
    structure = _match_blocks(steps, where)
    jumps, jump_problems = _resolve_gotos(steps, structure.enclosing, _labels(steps), where)
    reachable = _reachable(_successors(steps, structure.blocks, jumps), len(steps))

    problems = structure.problems + jump_problems + _unreachable(steps, jumps, reachable, where)
    problems.sort(key=lambda problem: (problem.where.action, problem.tag))
    return Flow(where, steps, structure.depth, structure.blocks, jumps, reachable, problems)


def control_flow_problems() -> list[Problem]:
    """Every control-flow defect in the loaded configuration.

    What healthck folds into its own report, and what this module's own report is built
    from.  The Project map is built once here rather than per Task, for the reason
    _project_of_task gives.
    """
    owners = _project_of_task()
    found = []
    for task_id in PrimeItems.tasker_root_elements["all_tasks"]:
        flow = analyze_task_flow(task_id, owners.get(task_id, ""))
        if flow is not None:
            found += flow.problems
    return found


# ##################################################################################
# The report.
# ##################################################################################
def _current_xml_file() -> str:
    """The path of the XML file being read.

    PrimeItems.file_to_get is sometimes an open file object and sometimes the path as a
    plain string -- the same ambiguity healthck._current_xml_file handles, resolved the
    same way.
    """
    file_to_get = PrimeItems.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) and path else "(unknown)"


def _counts(found: list[Problem]) -> dict:
    """How many problems of each severity."""
    return {severity: sum(1 for item in found if item.severity == severity) for severity in _SEVERITY_ORDER}


def _finding_order(problem: Problem) -> tuple:
    """Findings of one tag in the order a reader would look for them.

    On the object, and then on the action NUMBER -- not on the location line's text, in
    which "action 13" sorts above "action 7" and one Task's findings come out shuffled.
    """
    where = problem.where
    return (problem.tag, where.project, where.name, where.key, where.action)


def _finding_rows(found: list[Problem], indent: str = "") -> list[Row]:
    """The findings, worst severity first and grouped by tag within it.

    Sorted by tag so that every instance of one problem reads as a group, which is what
    makes a long report skimmable -- and what makes two reports diff cleanly.  healthck's
    layout exactly, because in healthck's report these are printed alongside its own.
    """
    rows = []
    for severity in _SEVERITY_ORDER:
        of_this_severity = [item for item in found if item.severity == severity]
        if not of_this_severity:
            continue
        rows += [Row(""), Row(f"{indent}{_SEVERITY_HEADINGS[severity]}"), Row(f"{indent}{'-' * _REPORT_WIDTH}")]
        for item in sorted(of_this_severity, key=_finding_order):
            # The location line is the clickable one, never the detail -- healthck's rule:
            # the detail is what is wrong, the location is the thing to go and look at.
            rows += [
                Row(f"{indent}[{item.tag}]  {item.where.label}", item.where),
                Row(f"{indent}    {item.detail}"),
                Row(""),
            ]
    return rows


def _header_rows(title: str) -> list[Row]:
    """The block every report here opens with: which file, when, and by what version."""
    return [
        Row(title),
        Row("=" * _REPORT_WIDTH),
        Row(f"XML file:    {_current_xml_file()}"),
        Row(f"Generated:   {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}"),  # noqa: DTZ005
        Row(f"Version:     {MY_VERSION}"),
    ]


def run_task_flow_check() -> tuple[list[Row], dict]:
    """Scan every loaded Task's control flow and return (report rows, counts by severity).

    Rows rather than finished text, for the reason healthck gives: the caller saves them as
    plain text and shows them as HTML, and the two have to be the same report.
    """
    found = control_flow_problems()
    counts = _counts(found)
    tasks = PrimeItems.tasker_root_elements["all_tasks"]
    actions = sum(len(task["xml"].findall("Action")) for task in tasks.values())

    rows = [
        *_header_rows("MapTasker Task Flow"),
        Row(""),
        Row(f"Scanned:     {len(tasks)} Tasks, {actions} actions"),
        Row(f"Findings:    {counts[ERROR]} Errors, {counts[WARNING]} Warnings"),
        Row(""),
    ]

    if not found:
        return [
            *rows,
            Row("Nothing to report -- every If and For is closed, every Goto has somewhere"),
            Row("to land, and no action is left stranded."),
            Row(""),
        ], counts

    return rows + _finding_rows(found) + [Row(line) for line in _limitations()], counts


def _limitations() -> list[str]:
    """The closing note on what this check cannot see.

    Printed rather than left implied, for healthck's reason: a reader has to be able to
    tell which silences are answers and which are the check declining to guess.
    """
    return [
        "",
        "NOTE ON WHAT IS NOT CHECKED",
        "-" * _REPORT_WIDTH,
        "A Goto whose label or action number is built from a variable is decided on the",
        "device, so it is left alone rather than reported -- and a Task holding one is",
        "not checked for stranded actions at all, since an unknown jump could land on any",
        "of them.  Conditions are read for their shape and never evaluated: an 'If' that",
        "can never be true still counts here as a way through.",
        "",
    ]


def write_task_flow_report(rows: list[Row]) -> str:
    """Write the control-flow report to a timestamped file in the current directory.

    Returns the file name written, or "" if the write failed -- named, stamped and handled
    exactly as healthck.write_health_check_report does, and for its reasons.
    """
    return _write(rows, TASKFLOW_FILE, "Task Flow report")


def write_flowchart(rows: list[Row]) -> str:
    """Write one Task's flowchart to a timestamped file.  Returns the file name, or ""."""
    return _write(rows, FLOWCHART_FILE, "Flowchart")


def _write(rows: list[Row], base_name: str, what: str) -> str:
    """Write rows as plain text to a timestamped copy of base_name in the current directory."""
    stamp = datetime.now().strftime("_%m-%d-%Y_%H-%M-%S")  # noqa: DTZ005
    file_name = append_to_filename(base_name, stamp)
    if not file_name:
        return ""
    try:
        with open(os.path.join(os.getcwd(), file_name), "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"{what} could not be written: {error}")
        return ""
    return file_name


# ##################################################################################
# The flowchart: the same graph, drawn.
# ##################################################################################
# Box-drawing rather than a picture, for the reason the Diagram view is drawn that way:
# the views are monospace text, they are searchable, they copy and paste, and they cost
# nothing to render on a Task with four hundred actions.
#
# The shape is a spine down the left with one line per action.  Nesting is indentation --
# an If's body sits one column in, and the "|" characters of the levels above run past it
# -- which is the one thing the Map cannot show, since it prints every action at the same
# margin whatever it is inside.  Jumps are the other thing, and they are drawn as arrows
# in a gutter to the RIGHT of the text, where they can run up as easily as down without
# disturbing a single column of what they connect.
_SPINE = "│  "  # One level of nesting: the enclosing block's own line, continuing downward.
_BRANCH = "├─"  # This action, with the spine carrying on below it.
_LAST = "└─"  # The last action at this level, closing the spine that held it.
_NUMBER_WIDTH = 4
_MARGIN = " " * (_NUMBER_WIDTH + 2)

_PLAIN_GLYPH = "─"
_GLYPHS = {
    _IF: "◆",  # A decision: two ways out.
    _FOR: "◆",
    _ELSE: "◈",  # The other way out of the decision above it.
    _END_IF: "◇",  # Where the ways back together.
    _END_FOR: "◇",
    _GOTO: "▶",
    _STOP: "■",
    _RETURN: "■",
    _PERFORM_TASK: "▷",
}

# The jump gutter.  Two columns per lane -- one for the vertical run, one of clear air
# beside it -- and a ceiling on how many lanes are drawn: past a dozen overlapping jumps
# the gutter is wider than the chart and reads as noise, so the ones that do not fit are
# left to the text of the Goto itself, which names its destination anyway.
_LANE_WIDTH = 2
_MAX_LANES = 12


def _glyph(step: Step) -> str:
    """The one character that says what kind of action this is."""
    return _GLYPHS.get(step.code, _PLAIN_GLYPH)


def _node_text(step: Step) -> str:
    """One action as the flowchart prints it: what it is, and what decides where it goes.

    The label is included because a Tasker label is the user's own comment on the action --
    the closest thing in the file to a sentence saying what this step is for -- and because
    it is what a Goto names when it jumps here.
    """
    pieces = [step.name]
    if step.detail:
        pieces.append(step.detail)
    if step.condition:
        # For an If or an Else the condition IS the action; anywhere else it is the
        # per-action "If" qualifier, and reads as one.
        pieces.append(step.condition if step.code in (_IF, _ELSE) else f"if {step.condition}")
    if step.label:
        pieces.append(f"label: {step.label}")
    if step.disabled:
        pieces.append("[DISABLED]")
    return _flatten("  ".join(pieces), _TEXT_LIMIT)


def _body(flow: Flow) -> tuple[list[str], list[int], list[int]]:
    """The chart's lines, which action each draws (-1 for "start"), and where its text begins.

    An action is drawn with "└" instead of "├" when the next line steps back out of its
    block, which is what closes the vertical the block was drawn with rather than leaving it
    running off the bottom of its own contents.

    The text column is carried out because only the text of a line is made clickable, never
    the drawing: a spine of "│" characters with a dotted underline through it stops looking
    like a spine, and the drawing is not the thing a click is being offered on.
    """
    lines = [f"{_MARGIN}┌─ start of Task"]
    owners = [-1]
    starts = [0]
    last = len(flow.steps) - 1

    for index, step in enumerate(flow.steps):
        depth = flow.depth[index]
        closing = index == last or flow.depth[index + 1] < depth
        stranded = "" if index in flow.reachable else "   [not reached]"
        prefix = f"{step.number:>{_NUMBER_WIDTH}}  {_SPINE * depth}{_LAST if closing else _BRANCH}{_glyph(step)} "
        lines.append(f"{prefix}{_node_text(step)}{stranded}")
        owners.append(index)
        starts.append(len(prefix))

    return lines, owners, starts


def _assign_lanes(edges: list[tuple[int, int]]) -> dict[int, int]:
    """{edge position: gutter lane}, packing jumps into as few lanes as they will go.

    Shortest span first, so a jump between neighbouring actions gets the lane nearest the
    text and a jump across the whole Task is pushed out to the edge.  That is what keeps
    the common case -- a loop back over a handful of actions -- readable next to a long
    one, rather than having the two swap places depending on which was written first.
    """
    lanes: list[list[tuple[int, int]]] = []
    assignment: dict[int, int] = {}

    for position, (source, target) in sorted(enumerate(edges), key=lambda item: abs(item[1][1] - item[1][0])):
        span = (min(source, target), max(source, target))
        for index, occupied in enumerate(lanes):
            if all(span[1] < low or span[0] > high for low, high in occupied):
                occupied.append(span)
                assignment[position] = index
                break
        else:
            lanes.append([span])
            assignment[position] = len(lanes) - 1

    return assignment


def _place(grid: list[list[str]], row: int, column: int, character: str, *, only_blank: bool = False) -> None:
    """Write one character into the gutter, optionally only where there is nothing yet."""
    if not (0 <= row < len(grid) and 0 <= column < len(grid[row])):
        return
    if only_blank and grid[row][column] != " ":
        return
    grid[row][column] = character


def _horizontal(grid: list[list[str]], row: int, start: int, stop: int) -> None:
    """The stub joining one end of a jump to the text it belongs to.

    Drawn only into blank cells, so that a stub reaching an outer lane leaves the inner
    lanes it crosses intact.  The trade is deliberate and one-sided: a stub with a gap in
    it still reads as a stub, while a vertical with a gap in it is a connection the reader
    can no longer follow.
    """
    for column in range(start, stop):
        _place(grid, row, column, "─", only_blank=True)


def _draw_edges(lines: list[str], edges: list[tuple[int, int]]) -> list[str]:
    """Draw each jump as an arrow in the gutter, from the Goto to the action it lands on.

    Verticals and their corners go down first and horizontals second, for the reason
    _horizontal gives: whichever is drawn first wins the cells they share, and the vertical
    is the half that has to survive.
    """
    lanes = _assign_lanes(edges)
    drawn = {position: lane for position, lane in lanes.items() if lane < _MAX_LANES}
    if not drawn:
        return lines

    base = max(len(line) for line in lines) + 2
    grid = [list(line.ljust(base + _LANE_WIDTH * (max(drawn.values()) + 1))) for line in lines]

    for position, lane in drawn.items():
        source, target = edges[position]
        column = base + _LANE_WIDTH * lane
        downward = target > source
        # "╮" turns a run coming from the left downward and "╯" turns one arriving from
        # above back to the left; a jump upward is the same two corners the other way round.
        _place(grid, source, column, "╮" if downward else "╯")
        _place(grid, target, column, "╯" if downward else "╮")
        for row in range(min(source, target) + 1, max(source, target)):
            _place(grid, row, column, "│", only_blank=True)

    for position, lane in drawn.items():
        source, target = edges[position]
        column = base + _LANE_WIDTH * lane
        _horizontal(grid, source, len(lines[source]) + 1, column)
        _place(grid, target, len(lines[target]) + 1, "◄")
        _horizontal(grid, target, len(lines[target]) + 2, column)

    return ["".join(row).rstrip() for row in grid]


def _legend() -> list[str]:
    """What the glyphs mean, spelled out under the chart rather than left to be guessed."""
    return [
        "",
        "-" * _REPORT_WIDTH,
        "Key   ◆ If / For (two ways out)   ◈ Else   ◇ End If / End For   ▶ Goto",
        "      ■ Stop / Return   ▷ Perform Task   ─ every other action",
        "",
        "      Indentation is nesting: what sits inside an If or a For is one column in.",
        "      An arrow on the right joins a Goto to the action it lands on.",
    ]


def flowchart(flow: Flow) -> list[Row]:
    """One Task drawn as a flowchart, one Row per line.

    Rows rather than lines so that the chart is clickable in the view exactly as a report
    finding is: each line's TEXT carries the Target of the action it draws, so clicking it
    takes the reader to that action in the Map (see _chart_row for why the drawing around
    it does not).  The plain text saved to file is the same Rows with the targets dropped
    (see write_flowchart), so the file and the screen cannot drift apart.

    The Task's own control-flow problems are printed above the chart rather than left to
    the whole-configuration report: somebody looking at one Task's flow is owed the reason
    they were sent to look at it.
    """
    rows = [
        *_header_rows("MapTasker Task Flowchart"),
        Row(""),
        # The label alone is the clickable piece, not the whole line: an underline running
        # through "Task:" and the padding in front of it reads as a mis-click waiting to
        # happen.  Same rule the chart's own lines follow (see _chart_row).
        Row.of_pieces([("Task:        ", None), (flow.target.label, flow.target)]),
        Row(f"Actions:     {len(flow.steps)}"),
    ]

    if flow.problems:
        rows += _finding_rows(flow.problems)
    else:
        rows += [Row(""), Row("No control-flow problems found in this Task."), Row("")]

    lines, owners, starts = _body(flow)
    # A Goto onto its own line is a Task that never gets past it.  Nothing is drawn for it:
    # an arrow from a line back to itself has nowhere to go, and the action's own text
    # already names its destination.
    edges = [
        (jump.source + 1, jump.target + 1)
        for jump in flow.jumps.values()
        if jump.resolved and jump.target is not None and jump.target != jump.source
    ]
    drawn = _draw_edges(lines, edges) if edges else lines
    rows += [
        _chart_row(flow, text, owners[position], starts[position], len(lines[position]))
        for position, text in enumerate(drawn)
    ]

    return rows + [Row(line) for line in _legend()]


def _chart_row(flow: Flow, text: str, owner: int, start: int, end: int) -> Row:
    """One drawn line, with its action's text -- and only that -- made clickable.

    Split into three so the spine to the left of the text and the jump gutter to the right
    of it stay plain: a click is offered on the action, which is what the Map can be taken
    to, and underlining the drawing as well would make the chart look like a page of links.
    """
    if owner < 0:
        return Row(text)
    pieces = [
        (text[:start], None),
        (text[start:end], flow.target.at_action(flow.steps[owner].number)),
        (text[end:], None),
    ]
    return Row.of_pieces([(part, target) for part, target in pieces if part])
