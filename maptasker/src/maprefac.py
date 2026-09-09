"""maprefac: refactoring operations -- moves that rearrange the configuration rather than rewrite fields."""

#! /usr/bin/env python3

#                                                                                        #
# maprefac: the structural moves.  Four of them, one machinery.                          #
#                                                                                        #
#   EXTRACT    a run of a Task's actions becomes a Task of its own, and a Perform Task   #
#              takes their place.                                                        #
#   INLINE     the reverse: a Perform Task becomes the actions of the Task it calls.     #
#   MOVE       a Task or a Profile changes which Project owns it.                        #
#   DUPLICATE  a Project, Profile, Task or Scene is copied under a new name.             #
#                                                                                        #
# Same contract as healthck / varxref / mapfind / mapswap -- reads and writes            #
# PrimeItems.tasker_root_elements and nothing else, no GUI import, identity from         #
# mapjump -- and the same two rules every writer in this program follows:                #
#                                                                                        #
#   NOTHING IS APPLIED UNSEEN.  plan() and apply() are separate, apply() only ever takes #
#   a plan(), and every step of that plan is a clickable mapjump Row before it is a      #
#   change.                                                                              #
#                                                                                        #
#   ONE UNDO.  A refactor touches several objects at once -- extract writes a new Task,  #
#   edits an old one and edits a Project -- and all of it is one thing the user did, so  #
#   the whole of apply() runs inside a single re-entrant sessundo.undoable block.        #
#                                                                                        #
# WHERE THIS DIFFERS FROM mapswap, AND WHY THE DIFFERENCE IS THE POINT                   #
#                                                                                        #
# A bulk replace is a hundred independent changes, so mapswap's Plan carries a tick box  #
# per change and its apply() is a loop that can skip one and carry on.  A refactor is    #
# ONE change, made of steps that are meaningless apart: extracting six actions without   #
# writing the Perform Task that replaces them does not leave the user with a partly-done #
# refactor, it leaves them with six actions that no longer run.  So there are no ticks   #
# here, and a Plan is all-or-nothing.                                                    #
#                                                                                        #
# That is also why the refusals are BLOCKS rather than mapswap's per-site Skips.  A skip #
# reports one place a bulk operation could not reach and lets the rest proceed.  There   #
# is no "rest" here: a reason this refactor is unsafe is a reason not to do it at all,   #
# so a Plan carrying blocks describes what WOULD have happened and apply() refuses it.   #
#                                                                                        #
# WHAT A BLOCK IS FOR, AND WHY THERE ARE SO MANY                                         #
#                                                                                        #
# Every one of these moves is trivially correct on a Task of five Flashes and quietly    #
# wrong on a real one.  Pull six actions out of the middle of an If block and the three  #
# that are left run unconditionally.  Inline a Task holding a Goto and the Goto now      #
# addresses somebody else's action.  Split a Task in half and the local variables the    #
# two halves shared stop being the same variable, because a local belongs to the running #
# Task and a Perform Task starts a new one.                                              #
#                                                                                        #
# None of those show up as an error.  The configuration parses, loads, and runs -- doing #
# something other than what it did before, discovered days later on the device.  So the  #
# checks below are the feature, not paperwork around it, and each one names the specific #
# thing that would go wrong rather than refusing in the abstract.                        #
#                                                                                        #
# WHAT IS DELIBERATELY NOT ATTEMPTED                                                     #
#                                                                                        #
# Nothing here rewrites prose.  A Task label reading "flash the total" on an action that #
# has moved to another Task is stale, and a description mentioning six steps that are    #
# now one is stale, and this tool says so rather than editing English.                   #
#                                                                                        #
# Nothing here repoints references it cannot see.  A Task named in a home screen widget, #
# in a Tasker shortcut, or built at run time out of a variable is beyond the file, and   #
# the moves that could strand one say so in a warning instead of pretending otherwise.   #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import copy
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from maptasker.src import mapjump, maputil2, profedit, projedit, sessundo, taskedit, varxref
from maptasker.src.actionc import action_codes
from maptasker.src.editcommon import set_child_text as _set_child_text
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK, Row, Target, text_report
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import REFACTOR_FILE, logger
from maptasker.src.varxref import VARIABLE_PATTERN

if TYPE_CHECKING:
    from collections.abc import Callable

    import defusedxml.ElementTree


# ##################################################################################
# What a plan is.
# ##################################################################################

# Which refactor a Plan describes.  Carried on the Plan so a caller that holds one without
# having built it -- the report writer, the dialog that re-opens on the tab it was made on
# -- can still say which of the four it is.
EXTRACT = "extract"
INLINE = "inline"
MOVE = "move"
DUPLICATE = "duplicate"


@dataclass(frozen=True)
class Step:
    """One thing that will happen, in the order it will happen.

    Numbered and printed in the preview.  The steps are not separately applicable and are
    not offered as choices -- see this module's note on why a refactor is all-or-nothing --
    so this exists to be READ.  Its job is to let a user recognise a move they did not mean
    before it happens: "the new Task is added to Project 'Home'" is the line that catches a
    Task extracted into the wrong Project.

    `where` is what a click on the line jumps to, and is None for a step whose subject does
    not exist yet -- the new Task an extract is about to write has no anchor in a Map drawn
    before it existed, and a link that is guaranteed to go nowhere is worse than no link.
    """

    text: str
    where: Target | None = None


@dataclass(frozen=True)
class Block:
    """Why this refactor will not be done, in the user's terms.

    `reason` is a short, stable, un-translated tag (UNBALANCED-IF) for the same purpose
    healthck's Finding.tag serves: two previews can be diffed and a reason can be searched
    for.  `explanation` is the prose, and it has one job -- to say what would go wrong,
    specifically enough that the user can decide whether to restructure and try again.

    "Cannot extract these actions" is a refusal.  "Actions 3-6 open an If block that is
    closed at action 9, which is not being extracted -- the three actions left behind would
    then run unconditionally" is an answer.
    """

    reason: str
    explanation: str
    where: Target | None = None


@dataclass
class Plan:
    """Everything one refactor would do, before any of it is done.

    `run` is the refactor itself, as a closure over exactly what the planner resolved --
    the elements, the ids, the names -- rather than a payload dict that apply() would
    re-interpret through a dispatch on `kind`.

    That is a deliberate departure from mapswap, whose Change carries data because its
    apply() has to SORT the changes before running them (the variable declaration must be
    rewritten last) and a closure cannot be sorted.  Nothing here is sorted or skipped:
    apply() checks the blocks, checks the elements are still in the tree, opens one undo
    block and calls this.  Keeping each operation's planning and its rewriting adjacent in
    this file, sharing one set of local names, is worth more than the inspectability a
    payload would buy -- and what a caller actually needs to inspect is `steps`, `blocks`
    and `warnings`, which are data.

    A Plan IS ONLY VALID UNTIL THE TREE IS RELOADED, for the reason mapswap's Site gives at
    greater length: it closes over live elements, and a preview can sit on screen while the
    user edits something else in another dialog.  `elements` is every element the closure
    depends on, and apply() re-checks each is still attached before running any of it.
    """

    kind: str
    what: str  # one line of prose: the preview's heading, the report's title, the Undo label
    steps: list[Step] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    elements: tuple = ()
    run: Callable[[], list[str]] | None = None

    @property
    def is_blocked(self) -> bool:
        """Whether anything stops this refactor being done."""
        return bool(self.blocks)

    @property
    def can_apply(self) -> bool:
        """Whether apply() would do anything.  What the Apply button's enabled state is."""
        return not self.blocks and self.run is not None


def _blocked(kind: str, what: str, *blocks: Block) -> Plan:
    """A Plan that describes a refactor and refuses it.

    Returned rather than raising, and carrying `what` rather than an empty heading, because
    the preview still has something to say: the user asked a question ("can I extract
    these?") and the answer is the block, printed under the heading of what they asked.
    """
    return Plan(kind=kind, what=what, blocks=list(blocks))


# ##################################################################################
# Reading the tree.
#
# Everything below reads live elements and never a copy.  A refactor's whole subject is
# WHERE things are, and a copy is somewhere else.
# ##################################################################################


def _tables() -> dict:
    """The four object tables, whatever state the program is in."""
    return PrimeItems.tasker_root_elements or {}


def _table(name: str) -> dict:
    """One object table -- all_tasks, all_profiles, all_projects, all_scenes -- or {}."""
    return _tables().get(name) or {}


def _members(project_element: defusedxml.ElementTree.Element, tag: str) -> list[str]:
    """A Project's <pids>, <tids> or <scenes> as a list, [] when it holds none.

    A fifth copy of a three-line read that mapjump, mapfind, projedit and sceneedit each
    keep privately.  Not shared from one of them for the reason each of those gives about
    the same body: it is smaller than the import that would carry it, and every module that
    walks Projects needs it.  What is NOT duplicated is the write half -- see
    projedit.set_project_members, which stamps the <mdate> that a hand-rolled write forgets.
    """
    child = project_element.find(tag)
    raw = (child.text or "").strip() if child is not None else ""
    return [piece.strip() for piece in raw.split(",") if piece.strip()]


def _projects_listing(tag: str, member: str) -> list[str]:
    """EVERY Project whose <pids>/<tids>/<scenes> names this member, in table order.

    Deliberately not mapfind's project-membership map, which answers "which Project does
    this belong to" with one name.  That is the right answer for a report, which prints one
    location, and the wrong one for a rewrite: nothing in the format stops two Projects
    listing the same Task id, real backups in this repo do it, and a move that updated the
    first owner and left the second would leave the Task owned by both -- the exact
    inconsistency taskedit.delete_task scans every Project to avoid.
    """
    return [name for name, entry in _table("all_projects").items() if member in _members(entry["xml"], tag)]


def _display_project(tag: str, member: str) -> str:
    """The one Project name a Target should print for this member, or "" for none."""
    owners = _projects_listing(tag, member)
    return owners[0] if owners else ""


def _task_target(task_id: str) -> Target:
    """The Target for a Task, with the Project a report would file it under."""
    entry = _table("all_tasks").get(task_id) or {}
    return Target(kind=TASK, key=task_id, name=entry.get("name", ""), project=_display_project("tids", task_id))


def _profile_target(profile_id: str) -> Target:
    """The Target for a Profile, with the Project a report would file it under."""
    entry = _table("all_profiles").get(profile_id) or {}
    return Target(
        kind=PROFILE,
        key=profile_id,
        name=entry.get("name", ""),
        project=_display_project("pids", profile_id),
    )


def _actions(task_element: defusedxml.ElementTree.Element) -> list:
    """A Task's actions in the order Tasker runs them.

    mapjump's, not findall("Action")'s.  Tasker orders actions by the numeric suffix of
    sr="actN" and writes them to the file sorted as TEXT -- act0, act1, act10, act2 -- so
    the eighth element in the file is routinely not the eighth action.  Every number this
    module prints, blocks on, or renumbers is a run-order number, because that is the only
    number the user has ever seen.
    """
    return mapjump.actions_in_map_order(task_element)


def _renumber(actions: list) -> None:
    """Stamp sr="actN" over a list of action elements in the order they are to run.

    THE ONE PLACE IN THIS MODULE THAT COUNTS FROM ZERO, and it has to: sr="act0" is the
    first action in Tasker's own format.  Every number this module SHOWS counts from one,
    because that is what the Map prints and what healthck, varxref and taskflow all report
    (each of them enumerates actions_in_map_order with start=1).  Displayed number minus one
    is the index into the list; do not let the two meet anywhere but here.

    The whole of what a reorder costs: Tasker reads the order off this attribute and
    ignores document order entirely (see taskedit._renumber_actions, which says the same of
    the editor's own copy of a Task).  So an extract does not have to move XML children
    around to change what runs when -- it has to get this right.
    """
    for number, action in enumerate(actions):
        action.set("sr", f"act{number}")


def _code(action: defusedxml.ElementTree.Element) -> str:
    """An action's <code>, or "" -- the one field every action has."""
    return (action.findtext("code") or "").strip()


def _string_argument(action: defusedxml.ElementTree.Element, arg_id: str) -> str:
    """The text of an action's <Str sr="argN">, or "".

    Matched on the "sr" attribute rather than on child order, the way every reader in this
    codebase reaches an argument -- Tasker does not guarantee the order.
    """
    wanted = f"arg{arg_id}"
    for child in action.findall("Str"):
        if child.attrib.get("sr") == wanted:
            return (child.text or "").strip()
    return ""


def _action_name(action: defusedxml.ElementTree.Element) -> str:
    """What this action is called, for a preview line.  Its code, when nothing names it."""
    code = _code(action)
    entry = action_codes.get(f"{code}t")
    return entry.name if entry is not None else f"code {code}"


def _describe_actions(numbers: list[int]) -> str:
    """'actions 3-6' or 'action 3' -- how a run of actions is named in prose."""
    if len(numbers) == 1:
        return f"action {numbers[0]}"
    return f"actions {numbers[0]}-{numbers[-1]}"


def _now_millis() -> str:
    """Tasker's timestamp format: milliseconds since the epoch, as text."""
    return str(int(time.time() * 1000))


# ##################################################################################
# Variables that would stop being the same variable.
#
# This is the check that justifies the module.  Tasker scopes a lower case variable to
# the RUNNING TASK: %total in one Task and %total in another are two variables, and a
# Perform Task starts a new Task.  So splitting a Task in half, or folding one into
# another, silently changes what a local name refers to -- and nothing about the result
# looks wrong.  It parses, it loads, and on the device the second half reads an empty
# %total forever.
#
# What is computed is deliberately weaker than "which of these is written where": that
# needs varxref's write-argument tables and a scan of every argument's role, and a
# half-right answer here would be worse than an honest coarse one, because the user
# would trust it.  The names USED on both sides of the split is a fact, it is cheap, and
# it is exactly the list somebody has to look at before deciding.
# ##################################################################################


def _variable_names(elements: list) -> set[str]:
    """Every variable name mentioned anywhere inside these elements, whatever its scope.

    Walks text and attribute values both: an <Int sr="arg1"><var>%priority</var></Int> puts
    its name in a child's text, a Version 2 Scene puts one inside a JSON blob that is also
    just text, and neither is reachable by looking only at the arguments a code declares.
    Over-reading is the right failure here -- a name found in a comment costs one line of
    warning, a name missed costs the user a Task that has quietly stopped working.
    """
    found: set[str] = set()
    for element in elements:
        for node in element.iter():
            for text in (node.text or "", *(str(value) for value in node.attrib.values())):
                if "%" not in text:
                    continue
                found.update(f"%{match.group(1)}" for match in VARIABLE_PATTERN.finditer(text))
    return found


def _local_names(elements: list) -> set[str]:
    """The subset of those names that Tasker scopes to the running Task.

    Scope comes from varxref, which is where Tasker's own rule lives (at least one upper
    case letter makes a name global) along with the two exceptions to it that matter:
    Tasker's documented built-ins, and the %par1/%caller/%priority/%err family Tasker sets
    itself.  Neither of those is the user's to lose track of, so neither is reported here --
    %par1 is handled separately by the warnings that are specifically about it, because what
    happens to a parameter across one of these moves is a different fact from what happens
    to a local.
    """
    return {name for name in _variable_names(elements) if varxref.scope_of(name) == varxref.LOCAL}


# A Perform Task's two parameters, as the called Task reads them.  Tasker sets these rather
# than the user, so varxref classifies them apart from locals -- and every operation here
# that crosses a Perform Task boundary changes whose parameters they are.
_PARAMETERS = ("%par1", "%par2")


def _shared_locals_warning(inside: list, outside: list, moving_to: str) -> str:
    """The warning for locals used on both sides of a split, or "" when there are none.

    Named rather than counted.  "3 local variables are shared" tells the user there is a
    problem and nothing about where to look; the names are what they take back to the Task.
    """
    shared = sorted(_local_names(inside) & _local_names(outside))
    if not shared:
        return ""
    listed = ", ".join(shared[:8]) + (", ..." if len(shared) > 8 else "")
    return (
        f"{listed} {'is' if len(shared) == 1 else 'are'} used both inside and outside the actions being "
        f"moved.  Tasker scopes a lower case variable to the Task that is running, so once these actions "
        f"are {moving_to} they will no longer share those values.  Pass them across (Perform Task's "
        f"Parameter 1 and 2, and its Return Value Variable), or give them names with a capital letter in "
        f"so Tasker treats them as global."
    )


# ##################################################################################
# Control flow that a rearrangement would break.
#
# Four of Tasker's actions mean something only in relation to another action, and all
# four are why these operations need permission to refuse.  If/Else/End If and For/End
# For come in matched sets that a move can split; Goto addresses an action by NUMBER,
# which every one of these operations changes.
#
# taskedit.add_if_block_to_task exists because the first three come in sets, and
# mapswap's _STRUCTURAL blocks all four for the same reason from the other direction.
# This is the third statement of one fact about the format.
# ##################################################################################

_IF = taskedit.IF_ACTION_CODE  # "37"
_ELSE = taskedit.ELSE_ACTION_CODE  # "43"
_END_IF = taskedit.END_IF_ACTION_CODE  # "38"
_FOR = "39"
_END_FOR = "40"
# "Goto".  Its argument is an action NUMBER, and every operation in this module renumbers
# actions, so a Goto anywhere in a Task being rearranged is a jump that will land somewhere
# else afterwards -- silently, and to a perfectly valid action.
_GOTO = "135"

_CONTROL_FLOW = (_IF, _ELSE, _END_IF, _FOR, _END_FOR, _GOTO)


def _imbalance(numbered: list[tuple[int, object]]) -> str:
    """Why this run of actions cannot stand alone, or "" when it can.

    A run is self-contained when every If and every For it opens is also closed inside it,
    and it closes nothing it did not open.  Both halves matter and they fail differently:
    a run that opens an If it does not close leaves the actions AFTER it running
    unconditionally, and a run that closes one it did not open takes the End If away from
    the actions BEFORE it.  Each says which, and names the action, because "unbalanced" on
    its own does not tell anybody what to select instead.
    """
    if_depth = 0
    for_depth = 0
    for number, action in numbered:
        code = _code(action)
        if code == _IF:
            if_depth += 1
        elif code == _ELSE and if_depth == 0:
            return f"action {number} is an Else belonging to an If that is not included"
        elif code == _END_IF:
            if if_depth == 0:
                return f"action {number} is an End If belonging to an If that is not included"
            if_depth -= 1
        elif code == _FOR:
            for_depth += 1
        elif code == _END_FOR:
            if for_depth == 0:
                return f"action {number} is an End For belonging to a For that is not included"
            for_depth -= 1

    if if_depth:
        opened = "If block is" if if_depth == 1 else "If blocks are"
        return f"{if_depth} {opened} opened and never closed -- the End If is not included"
    if for_depth:
        opened = "For loop is" if for_depth == 1 else "For loops are"
        return f"{for_depth} {opened} opened and never closed -- the End For is not included"
    return ""


def _goto_numbers(actions: list) -> list[int]:
    """The positions of every Goto among these actions, counted from 1 as the Map prints them."""
    return [number for number, action in enumerate(actions, start=1) if _code(action) == _GOTO]


def _control_flow_codes(actions: list) -> set[str]:
    """Which of the flow-control codes appear among these actions."""
    return {_code(action) for action in actions} & set(_CONTROL_FLOW)


# ##################################################################################
# Extract: a run of actions becomes a Task, and a Perform Task takes its place.
# ##################################################################################

# The shape Tasker writes for a Perform Task, measured rather than guessed.  Of the 9,901
# Perform Task actions in this repo's sample XML, 6,982 carry exactly these twelve children
# and no others (the rest add a <label>, an attached <ConditionList>, or both), and the
# value written below is the commonest for every single argument: <var>%priority</var> in
# 8,540 of them, arg10=1 in 7,773, and 0 for arg5/arg6/arg8/arg9 in between 8,485 and 9,299.
#
# %priority rather than a number is Tasker's own default and the only one that is right
# here: it means "run at the priority of the Task that called me", which is exactly what the
# extracted actions were doing a moment ago as part of that Task.
#
# The order is arg0, arg1, arg10, arg2 ... arg9, which looks like a mistake and is not:
# Tasker sorts an action's argument children by their 'sr' as TEXT.  Written in that order
# for the reason mapswap._order_children gives -- an action built in a different order than
# Tasker would have written it is a screenful of moved lines in any diff of the backup, all
# of it noise around the one line that is the actual change.
_PERFORM_TASK_TEMPLATE = (
    ("Int", "arg10", "1"),
    ("Str", "arg2", ""),
    ("Str", "arg3", ""),
    ("Str", "arg4", ""),
    ("Int", "arg5", "0"),
    ("Int", "arg6", "0"),
    ("Str", "arg7", ""),
    ("Int", "arg8", "0"),
    ("Int", "arg9", "0"),
)


def _new_perform_task(element_cls: type, task_name: str) -> defusedxml.ElementTree.Element:
    """A Perform Task action calling `task_name`, built from nothing.

    Built here rather than through taskedit.add_action_to_task because that route refuses:
    classify_action_addability blocks Perform Task, on the grounds that its 'Name' argument
    has no category it can generate a default for.  That is the right answer to the question
    the Add Action dialog asks -- offer the user an action with an unfillable argument and
    they can never finish it -- and the wrong answer here, where the name is not a default to
    be invented but the whole point of the call, known before the element exists.

    sr="act0" is a placeholder; the caller renumbers every action in the Task afterwards.
    """
    action = element_cls("Action", {"sr": "act0", "ve": "7"})

    code = element_cls("code")
    code.text = taskedit.PERFORM_TASK_ACTION_CODE
    action.append(code)

    name = element_cls("Str", {"sr": f"arg{taskedit.PERFORM_TASK_NAME_ARG_ID}", "ve": "3"})
    name.text = task_name
    action.append(name)

    priority = element_cls("Int", {"sr": "arg1"})
    variable = element_cls("var")
    variable.text = "%priority"
    priority.append(variable)
    action.append(priority)

    for tag, sr_value, value in _PERFORM_TASK_TEMPLATE:
        if tag == "Int":
            action.append(element_cls("Int", {"sr": sr_value, "val": value}))
        else:
            child = element_cls("Str", {"sr": sr_value, "ve": "3"})
            child.text = value
            action.append(child)

    return action


def plan_extract(task_id: str, action_numbers: list[int], new_task_name: str) -> Plan:
    """Move a run of a Task's actions into a new Task, leaving a Perform Task behind.

    `action_numbers` are the numbers the MAP PRINTS -- counting from 1, in run order, which
    is what every report in this program reports and what the pulldowns offer.  They are
    neither indices into findall("Action") (see _actions) nor sr="actN" suffixes (see
    _renumber, which is the only thing here that counts from zero).

    The run has to be CONTIGUOUS, and that is not a simplification to be lifted later.
    Extract actions 2 and 5 and there is one Perform Task to put back but two holes to put
    it in: whichever is chosen, actions 3 and 4 change places with action 5 relative to each
    other, which is a reordering the user did not ask for and would not see.  A refusal that
    says so is a better answer than a rule for guessing.

    The Perform Task is written at the position the run started, so what runs when is
    unchanged -- with the one exception the warnings are about, which is local variables.
    """
    entry = _table("all_tasks").get(task_id)
    if entry is None:
        return _blocked(EXTRACT, "Extract actions into a new Task", Block("NO-TASK", "That Task is not in this file."))

    task_element = entry["xml"]
    task_name = entry.get("name", "") or task_id
    where = _task_target(task_id)
    all_actions = _actions(task_element)

    wanted = sorted({int(number) for number in action_numbers})
    new_name = (new_task_name or "").strip()
    which = _describe_actions(wanted) if wanted else "actions"
    what = f"Extract {which} of Task '{task_name}' into a new Task '{new_name}'"

    scope = extract_scope()
    if not scope.allows(TASK, task_id):
        # Belt to the filtered pulldown's braces.  The picker does not offer an
        # out-of-scope Task, but a dialog can sit open while the user changes what the Map
        # is showing, and a plan built before that must not be applied after it.
        return _blocked(
            EXTRACT,
            what,
            Block(
                "OUT-OF-SCOPE",
                f"Task '{task_name}' is not among the Tasks {scope.phrase} covers.  Extract works on "
                f"the Task selected in the pulldowns, the same way the Edit buttons beside it do.  "
                f"Change or clear that selection to reach other Tasks.",
                where,
            ),
        )

    block = _extract_block(all_actions, wanted, new_name, where)
    if block is not None:
        return _blocked(EXTRACT, what, block)

    moving = [all_actions[number - 1] for number in wanted]
    kept = [action for number, action in enumerate(all_actions, start=1) if number not in set(wanted)]
    owners = _projects_listing("tids", task_id)

    plan = Plan(kind=EXTRACT, what=what, elements=(task_element, *all_actions))
    plan.steps = _extract_steps(moving, wanted, new_name, task_name, where, owners)
    plan.warnings = _extract_warnings(moving, kept, task_name, owners)

    def run() -> list[str]:
        """Move the elements, write the call, register the Task, file it under a Project."""
        priority = task_element.findtext("pri", "") or "100"
        new_task = taskedit.create_new_task(new_name, priority)
        if isinstance(new_task, str):
            return [new_task]

        # The elements themselves move; they are not copied.  A copy would be a second set
        # of elements holding the same plugin payloads, icons and conditions, and the first
        # set would then have to be deleted -- two operations that can disagree, where this
        # is one that cannot.
        for action in moving:
            task_element.remove(action)
            new_task.task_element.append(action)
        _renumber(moving)

        call = _new_perform_task(type(task_element), new_name)
        task_element.append(call)
        # wanted[0] is a displayed number; the split in `kept` is an index.
        before = wanted[0] - 1
        _renumber([*kept[:before], call, *kept[before:]])

        taskedit.register_new_task(new_task, new_name)
        for project_name in owners:
            profedit.add_task_to_project(new_task.task_id, project_name)
        return []

    plan.run = run
    return plan


def _extract_block(all_actions: list, wanted: list[int], new_name: str, where: Target) -> Block | None:
    """The one reason this extract will not be done, or None.

    One rather than all of them: the checks are ordered from the user's mistake outwards,
    and a run that is not contiguous has not got a meaningful If balance to report on.
    """
    if not wanted:
        return Block("NO-ACTIONS", "No actions were selected to extract.", where)
    if wanted[0] < 1 or wanted[-1] > len(all_actions):
        return Block(
            "OUT-OF-RANGE",
            f"This Task has {len(all_actions)} actions, numbered 1 to {len(all_actions)}, and the "
            f"selection reaches outside that.  It may have been edited since this preview was built.",
            where,
        )
    if wanted != list(range(wanted[0], wanted[-1] + 1)):
        missing = sorted(set(range(wanted[0], wanted[-1] + 1)) - set(wanted))
        return Block(
            "NOT-CONTIGUOUS",
            f"The selected actions have gaps in them ({', '.join(str(number) for number in missing[:6])} "
            f"{'is' if len(missing) == 1 else 'are'} in between and not selected).  One Perform Task can "
            f"only stand in one place, so extracting a run with holes would silently reorder the actions "
            f"left behind.  Select an unbroken run.",
            where,
        )
    if not new_name:
        return Block("NO-NAME", "The new Task needs a name.", where)
    if taskedit.task_name_exists(new_name):
        return Block(
            "NAME-TAKEN",
            f"A Task named '{new_name}' is already in this file.  Perform Task calls a Task by name, so "
            f"two Tasks sharing one would leave it ambiguous which of them this call runs.",
            where,
        )

    imbalance = _imbalance([(number, all_actions[number - 1]) for number in wanted])
    if imbalance:
        return Block(
            "UNBALANCED-BLOCK",
            f"The selection is not self-contained: {imbalance}.  Moving it would leave the actions on the "
            f"other side of the split running under a condition, or a loop, that is no longer there.  "
            f"Extend the selection to take in the whole block.",
            where,
        )

    gotos = _goto_numbers(all_actions)
    if gotos:
        listed = ", ".join(str(number) for number in gotos[:6])
        return Block(
            "GOTO-PRESENT",
            f"This Task contains a Goto (action {listed}).  A Goto addresses an action by its NUMBER, and "
            f"extracting anything renumbers every action after it -- so the jump would still be valid and "
            f"would land somewhere else.  Nothing here can tell which action it was aiming at.",
            where,
        )
    return None


def _extract_steps(
    moving: list,
    wanted: list[int],
    new_name: str,
    task_name: str,
    where: Target,
    owners: list[str],
) -> list[Step]:
    """What an extract will do, in order, one line each."""
    first = wanted[0]
    steps = [
        Step(
            f"Create Task '{new_name}' holding {len(moving)} "
            f"{'action' if len(moving) == 1 else 'actions'}: "
            + ", ".join(_action_name(action) for action in moving[:4])
            + (", ..." if len(moving) > 4 else ""),
        ),
        Step(
            f"Remove {_describe_actions(wanted)} from Task '{task_name}'",
            where.at_action(first),
        ),
        Step(f"Put a Perform Task '{new_name}' in their place, as action {first}", where.at_action(first)),
    ]
    if owners:
        steps.extend(
            Step(f"Add Task '{new_name}' to Project '{project_name}'", Target(kind=PROJECT, key=project_name))
            for project_name in owners
        )
    else:
        steps.append(Step(f"Task '{new_name}' is filed under no Project, because Task '{task_name}' is not either"))
    return steps


def _extract_warnings(moving: list, kept: list, task_name: str, owners: list[str]) -> list[str]:
    """What is true of this extract that the user should read before doing it."""
    warnings = []

    shared = _shared_locals_warning(moving, kept, "in a Task of their own")
    if shared:
        warnings.append(shared)

    parameters = sorted(name for name in _variable_names(moving) if name.lower() in _PARAMETERS)
    if parameters:
        warnings.append(
            f"The actions being moved use {', '.join(parameters)}.  Those are the parameters of whatever "
            f"called this Task, and after the move they will be the new Task's parameters instead -- which "
            f"the Perform Task being written does not pass anything into.",
        )

    if not kept:
        warnings.append(
            "Every action in this Task is being extracted, so what is left is a Task whose only action is a "
            "call to the new one.  That is a valid thing to want; it is worth being sure it is what you meant.",
        )

    labelled = [action for action in moving if action.find("label") is not None]
    if labelled:
        warnings.append(
            f"{len(labelled)} of the actions being moved {'carries' if len(labelled) == 1 else 'carry'} a "
            f"label.  Labels travel with their action and are not rewritten, so any that describe this Task "
            f"by name will now say so from inside another.",
        )

    if len(owners) > 1:
        warnings.append(
            f"Task '{task_name}' is listed by {len(owners)} Projects ({', '.join(owners)}), so the new Task "
            f"is added to all of them -- the same arrangement the original is in.",
        )
    return warnings


# ##################################################################################
# Inline: a Perform Task becomes the actions of the Task it calls.
#
# The mirror of extract, and the harder direction.  Extract splits one scope into two,
# which loses shared locals; inline MERGES two scopes into one, which is worse, because
# nothing is lost -- two variables that were separate quietly become the same variable.
# A %count the called Task uses as a loop counter and a %count the calling Task uses for
# something else have never met before and now overwrite each other.
#
# Both are warnings rather than blocks, for the same reason: they are frequently exactly
# what the user wants (that is often WHY somebody inlines a Task), and they are never
# something the tool can decide on its own.  What it can do is name the variables.
# ##################################################################################

_CONDITION_LIST = "ConditionList"


def _perform_task_callers(task_name: str) -> list[Target]:
    """Every action in the file that calls this Task by name, as clickable Targets.

    A targeted scan rather than a healthck index: that builds a picture of the whole
    configuration to answer a hundred questions, and this asks one.  Matched exactly, the
    way Tasker matches it -- a call naming a Task built out of a variable at run time
    ('%which') is not resolvable here and is not counted, which healthck's _is_resolvable
    says at greater length.
    """
    callers: list[Target] = []
    for caller_id, entry in _table("all_tasks").items():
        for number, action in enumerate(_actions(entry["xml"]), start=1):
            if _code(action) != taskedit.PERFORM_TASK_ACTION_CODE:
                continue
            if _string_argument(action, taskedit.PERFORM_TASK_NAME_ARG_ID) == task_name:
                callers.append(_task_target(caller_id).at_action(number))
    return callers


def plan_inline(task_id: str, action_number: int) -> Plan:
    """Replace one Perform Task with a copy of the actions of the Task it calls.

    A COPY, and the called Task is left exactly where it is.  Anything else would be two
    operations wearing one name: a Task called from six places, inlined at one of them and
    then deleted, breaks the other five.  Whether the called Task is now unused is a
    question this answers -- see the callers warning -- and deleting it stays the user's
    own click.
    """
    entry = _table("all_tasks").get(task_id)
    if entry is None:
        return _blocked(INLINE, "Inline a Perform Task", Block("NO-TASK", "That Task is not in this file."))

    task_element = entry["xml"]
    task_name = entry.get("name", "") or task_id
    where = _task_target(task_id)
    all_actions = _actions(task_element)

    if not 1 <= action_number <= len(all_actions):
        return _blocked(
            INLINE,
            f"Inline action {action_number} of Task '{task_name}'",
            Block(
                "NO-ACTION",
                f"Task '{task_name}' has no action {action_number}.  It may have been edited since this "
                f"preview was built.",
                where,
            ),
        )

    call = all_actions[action_number - 1]
    called_name = _string_argument(call, taskedit.PERFORM_TASK_NAME_ARG_ID)
    what = f"Inline Perform Task '{called_name}' at action {action_number} of Task '{task_name}'"

    called = _table("all_tasks_by_name").get(called_name)
    block = _inline_block(call, called_name, called, task_id, where.at_action(action_number))
    if block is not None:
        return _blocked(INLINE, what, block)

    called_element = called["xml"]
    called_actions = _actions(called_element)
    condition = call.find(_CONDITION_LIST)
    label = call.find("label")
    disabled = (call.findtext("on") or "") == "false"
    kept = [action for number, action in enumerate(all_actions, start=1) if number != action_number]

    plan = Plan(
        kind=INLINE,
        what=what,
        elements=(task_element, called_element, call, *all_actions, *called_actions),
    )
    plan.steps = _inline_steps(called_name, called_actions, task_name, action_number, where, condition, disabled)
    plan.warnings = _inline_warnings(call, called_name, called_actions, kept)

    def run() -> list[str]:
        """Copy the called Task's actions in, carrying over what the call itself said."""
        copies = [copy.deepcopy(action) for action in called_actions]

        for index, action in enumerate(copies):
            # The call's own condition and disabled flag are statements about WHETHER this
            # runs, and inlining must not quietly turn them off.  Distributed over every
            # copy, which is equivalent because the block above refused the two shapes where
            # it would not be -- flow control among the copies, and a copy with a condition
            # of its own.
            if condition is not None:
                action.append(copy.deepcopy(condition))
            if disabled:
                _set_child_text(action, "on", "false")
            # The call's label describes the call, so it belongs on the action that now
            # stands where the call did -- but only when that action has none of its own,
            # which is what the warning covers.
            if index == 0 and label is not None and action.find("label") is None:
                action.append(copy.deepcopy(label))

        task_element.remove(call)
        for action in copies:
            task_element.append(action)
        # action_number is a displayed number; the split in `kept` is an index.
        before = action_number - 1
        _renumber([*kept[:before], *copies, *kept[before:]])
        return []

    plan.run = run
    return plan


def _inline_block(
    call: defusedxml.ElementTree.Element,
    called_name: str,
    called: dict | None,
    task_id: str,
    where: Target,
) -> Block | None:
    """The one reason this inline will not be done, or None."""
    if _code(call) != taskedit.PERFORM_TASK_ACTION_CODE:
        return Block(
            "NOT-A-CALL",
            f"That action is a {_action_name(call)}, not a Perform Task.  There is nothing to inline.",
            where,
        )
    if not called_name:
        return Block("NO-NAME", "This Perform Task names no Task to run.", where)
    if "%" in called_name:
        return Block(
            "INDIRECT-NAME",
            f"This call runs '{called_name}', which is decided by a variable when the Task runs.  Which "
            f"Task's actions to inline is not knowable from the file.",
            where,
        )
    if called is None:
        return Block(
            "NO-SUCH-TASK",
            f"'{called_name}' is not a Task in this file, so this call is already broken.  Point it at a "
            f"Task that exists, or delete it.",
            where,
        )
    if called["id"] == task_id:
        return Block(
            "SELF-CALL",
            f"'{called_name}' is this same Task.  Inlining it into itself would copy its actions into the "
            f"middle of themselves, and the copy would still hold the call.",
            where,
        )

    called_actions = _actions(called["xml"])
    gotos = _goto_numbers(called_actions)
    if gotos:
        listed = ", ".join(str(number) for number in gotos[:6])
        return Block(
            "GOTO-IN-CALLED-TASK",
            f"Task '{called_name}' contains a Goto (action {listed}).  A Goto addresses an action by its "
            f"NUMBER, and inlining shifts every one of these actions by however many come before them in "
            f"the calling Task -- so the jump would land on an unrelated action rather than fail.",
            where,
        )

    if call.find(_CONDITION_LIST) is not None:
        flow = _control_flow_codes(called_actions)
        if flow:
            return Block(
                "CONDITIONAL-BLOCK",
                f"This call runs only if its own condition is met, and Task '{called_name}' contains "
                f"If/For actions.  The condition can be carried onto each inlined action one at a time, "
                f"but not onto a block -- an If whose condition was false would have its End If skipped "
                f"and the rest of the Task would run inside a block that never opened.",
                where,
            )
        conditioned = [
            number for number, action in enumerate(called_actions, start=1) if action.find(_CONDITION_LIST) is not None
        ]
        if conditioned:
            listed = ", ".join(str(number) for number in conditioned[:6])
            return Block(
                "CONDITION-ON-CONDITION",
                f"This call has a condition of its own, and so does action {listed} of Task "
                f"'{called_name}'.  Both would have to hold, and combining two conditions into one is a "
                f"decision about the user's intent that this tool will not make on its own.",
                where,
            )
    return None


def _inline_steps(
    called_name: str,
    called_actions: list,
    task_name: str,
    action_number: int,
    where: Target,
    condition: object,
    disabled: bool,
) -> list[Step]:
    """What an inline will do, in order, one line each."""
    count = len(called_actions)
    called_entry = _table("all_tasks_by_name").get(called_name)
    called_where = _task_target(called_entry["id"]) if called_entry else None
    steps = [
        Step(
            f"Remove the Perform Task at action {action_number} of Task '{task_name}'",
            where.at_action(action_number),
        ),
        Step(
            f"Put {count} {'action' if count == 1 else 'actions'} copied from Task '{called_name}' in its "
            "place: "
            + ", ".join(_action_name(action) for action in called_actions[:4])
            + (", ..." if count > 4 else ""),
            called_where,
        ),
    ]
    if condition is not None:
        steps.append(Step(f"Carry the call's condition onto each of the {count} copied actions"))
    if disabled:
        steps.append(Step(f"Carry the call's disabled state onto each of the {count} copied actions"))
    steps.append(Step(f"Leave Task '{called_name}' itself exactly as it is"))
    return steps


def _inline_warnings(
    call: defusedxml.ElementTree.Element,
    called_name: str,
    called_actions: list,
    kept: list,
) -> list[str]:
    """What is true of this inline that the user should read before doing it."""
    warnings = []

    if not called_actions:
        warnings.append(
            f"Task '{called_name}' has no actions, so this inline removes the call and puts nothing in its place.",
        )

    collisions = sorted(_local_names(called_actions) & _local_names(kept))
    if collisions:
        listed = ", ".join(collisions[:8]) + (", ..." if len(collisions) > 8 else "")
        warnings.append(
            f"{listed} {'is' if len(collisions) == 1 else 'are'} used by both Tasks.  They are separate "
            f"variables today, because Tasker scopes a lower case name to the Task that is running; after "
            f"this they are one, and each Task's values will overwrite the other's.",
        )

    parameters = sorted(name for name in _variable_names(called_actions) if name.lower() in _PARAMETERS)
    passed = [value for value in (_string_argument(call, "2"), _string_argument(call, "3")) if value]
    if parameters:
        detail = f" This call passes {', '.join(passed)}." if passed else " This call passes nothing."
        warnings.append(
            f"Task '{called_name}' reads {', '.join(parameters)} -- the parameters of whatever called it."
            f"{detail}  Inlined, those actions will read the CALLING Task's parameters instead, which are "
            f"a different thing entirely.",
        )

    returned = _string_argument(call, "4")
    if returned:
        warnings.append(
            f"This call puts the called Task's return value into {returned}.  Inlined actions do not return "
            f"anything, so nothing will set {returned} any more.",
        )

    if call.find("label") is not None and called_actions and called_actions[0].find("label") is not None:
        warnings.append(
            f"The call carries a label and so does the first action of '{called_name}'.  The action keeps "
            f"its own, and the call's label is not preserved.",
        )

    remaining = len(_perform_task_callers(called_name)) - 1
    if remaining > 0:
        warnings.append(
            f"{remaining} other {'call' if remaining == 1 else 'calls'} to '{called_name}' "
            f"{'remains' if remaining == 1 else 'remain'} elsewhere in this file, so the Task is still "
            f"needed and is left in place.",
        )
    elif remaining == 0:
        warnings.append(
            f"Nothing else calls '{called_name}'.  It is left in place either way -- deleting a Task is its "
            f"own decision, and Perform Task is not the only way a Task can be reached (a home screen "
            f"widget or a Tasker shortcut leaves no trace in this file).",
        )
    return warnings


# ##################################################################################
# Move: a Task or a Profile changes which Project owns it.
#
# The smallest of the four, and the one whose smallness is the surprise.  A Task is not
# INSIDE a Project in the file -- every Task is a top-level element, and a Project owns
# one by naming its id in <tids>.  So moving a Task between Projects moves no XML at
# all; it edits two lists.  profedit.add_task_to_project and taskedit.delete_task are
# the two halves of that already, from the add and the delete side.
#
# What makes it worth a preview anyway is what a Project's membership decides: it is
# what the Map, the Diagram, the Tree and every pulldown walk (getids.get_ids), and it
# is what a single-Project export writes.  A Task quietly filed under the wrong Project
# is a Task the user cannot find and an export that does not carry it.
# ##################################################################################


def _relocate(tag: str, member: str, to_project: str, from_projects: list[str]) -> None:
    """Take a member out of every Project listing it and put it in one.

    Every Project, not the first: see _projects_listing on why two of them can hold the
    same id, and taskedit.delete_task, which scans them all for the same reason.
    """
    projects = _table("all_projects")
    for project_name in from_projects:
        entry = projects.get(project_name)
        if entry is None or project_name == to_project:
            continue
        projedit.set_project_members(
            entry["xml"],
            tag,
            [existing for existing in _members(entry["xml"], tag) if existing != member],
        )

    entry = projects.get(to_project)
    if entry is not None:
        existing = _members(entry["xml"], tag)
        if member not in existing:
            projedit.set_project_members(entry["xml"], tag, [*existing, member])


def _profile_task_ids(profile_element: defusedxml.ElementTree.Element) -> list[str]:
    """A Profile's Entry and Exit Task ids, deduplicated, in <mid0>/<mid1> order.

    dict.fromkeys rather than a set: a Profile may legitimately name one Task as both its
    Entry and its Exit (profedit.render_standalone_profile_xml records a real case), and
    the order is the order the Profile itself lists them in.
    """
    return list(
        dict.fromkeys(
            (child.text or "").strip()
            for child in profile_element
            if child.tag in ("mid0", "mid1") and (child.text or "").strip()
        ),
    )


def plan_move(kind: str, key: str, to_project: str) -> Plan:
    """Move a Task (kind=TASK, key=its id) or a Profile (kind=PROFILE, key=its id) to a Project.

    A Profile takes its Entry and Exit Tasks with it, EXCEPT any that another Profile left
    behind still runs.  That exception is not an edge case: a Task shared between two
    Profiles of one Project is ordinary, and moving it would take it out from under the
    Profile that stayed -- turning one deliberate move into a second, invisible one.  The
    Tasks that do not travel are named in a warning rather than passed over in silence.
    """
    if to_project not in _table("all_projects"):
        return _blocked(
            MOVE,
            "Move to another Project",
            Block("NO-PROJECT", f"'{to_project}' is not a Project in this file."),
        )

    if kind == TASK:
        return _plan_move_task(key, to_project)
    if kind == PROFILE:
        return _plan_move_profile(key, to_project)
    return _blocked(
        MOVE,
        "Move to another Project",
        Block("NOT-MOVABLE", f"A {kind} cannot be moved between Projects."),
    )


def _plan_move_task(task_id: str, to_project: str) -> Plan:
    """Move one Task's Project membership."""
    entry = _table("all_tasks").get(task_id)
    if entry is None:
        return _blocked(MOVE, "Move a Task to another Project", Block("NO-TASK", "That Task is not in this file."))

    task_name = entry.get("name", "") or task_id
    where = _task_target(task_id)
    owners = _projects_listing("tids", task_id)
    what = f"Move Task '{task_name}' to Project '{to_project}'"

    if owners == [to_project]:
        return _blocked(
            MOVE,
            what,
            Block(
                "ALREADY-THERE",
                f"Task '{task_name}' already belongs to Project '{to_project}' and to no other, so there "
                f"is nothing to move.",
                where,
            ),
        )

    plan = Plan(kind=MOVE, what=what, elements=(entry["xml"],))
    plan.steps = [
        *(
            Step(f"Remove Task '{task_name}' from Project '{owner}'", Target(kind=PROJECT, key=owner))
            for owner in owners
            if owner != to_project
        ),
        Step(f"Add Task '{task_name}' to Project '{to_project}'", Target(kind=PROJECT, key=to_project)),
    ]
    plan.warnings = _move_task_warnings(task_id, task_name, owners, to_project)

    def run() -> list[str]:
        _relocate("tids", task_id, to_project, owners)
        return []

    plan.run = run
    return plan


def _move_task_warnings(task_id: str, task_name: str, owners: list[str], to_project: str) -> list[str]:
    """What a Task's move leaves behind that the user should know about."""
    warnings = []
    if not owners:
        warnings.append(
            f"Task '{task_name}' is not currently listed by any Project, so this files it under one for the "
            f"first time rather than moving it.",
        )

    stranded = []
    for profile_id, profile in _table("all_profiles").items():
        if task_id not in _profile_task_ids(profile["xml"]):
            continue
        profile_projects = _projects_listing("pids", profile_id)
        if to_project not in profile_projects:
            stranded.append(f"'{profile.get('name', '') or profile_id}'")
    if stranded:
        warnings.append(
            f"{', '.join(stranded[:6])} {'runs' if len(stranded) == 1 else 'run'} this Task and "
            f"{'is' if len(stranded) == 1 else 'are'} not in Project '{to_project}'.  Tasker allows that and "
            f"real backups contain it, so nothing breaks -- but the Task will no longer appear beside the "
            f"Profile that runs it, and a single-Project export of that Profile's Project will not carry it.",
        )

    callers = _perform_task_callers(task_name)
    outside = [target for target in callers if target.project and target.project != to_project]
    if outside:
        warnings.append(
            f"{len(outside)} Perform Task {'call' if len(outside) == 1 else 'calls'} to '{task_name}' "
            f"{'is' if len(outside) == 1 else 'are'} in other Projects.  Perform Task calls by name and does "
            f"not care which Project a Task is in, so those keep working.",
        )
    return warnings


def _plan_move_profile(profile_id: str, to_project: str) -> Plan:
    """Move one Profile's Project membership, and its Tasks' with it where that is safe."""
    entry = _table("all_profiles").get(profile_id)
    if entry is None:
        return _blocked(
            MOVE,
            "Move a Profile to another Project",
            Block("NO-PROFILE", "That Profile is not in this file."),
        )

    profile_element = entry["xml"]
    profile_name = entry.get("name", "") or profile_id
    where = _profile_target(profile_id)
    owners = _projects_listing("pids", profile_id)
    what = f"Move Profile '{profile_name}' to Project '{to_project}'"

    if owners == [to_project]:
        return _blocked(
            MOVE,
            what,
            Block(
                "ALREADY-THERE",
                f"Profile '{profile_name}' already belongs to Project '{to_project}' and to no other, so there "
                f"is nothing to move.",
                where,
            ),
        )

    # A Task travels with its Profile unless a Profile that is staying behind also runs it.
    task_ids = _profile_task_ids(profile_element)
    staying = {
        other_id: other
        for other_id, other in _table("all_profiles").items()
        if other_id != profile_id and set(_projects_listing("pids", other_id)) & set(owners)
    }
    shared = {
        task_id: sorted(
            other.get("name", "") or other_id
            for other_id, other in staying.items()
            if task_id in _profile_task_ids(other["xml"])
        )
        for task_id in task_ids
    }
    travelling = [task_id for task_id in task_ids if not shared[task_id]]

    plan = Plan(kind=MOVE, what=what, elements=(profile_element,))
    plan.steps = [
        *(
            Step(f"Remove Profile '{profile_name}' from Project '{owner}'", Target(kind=PROJECT, key=owner))
            for owner in owners
            if owner != to_project
        ),
        Step(f"Add Profile '{profile_name}' to Project '{to_project}'", Target(kind=PROJECT, key=to_project)),
        *(
            Step(
                f"Move its Task '{_table('all_tasks').get(task_id, {}).get('name', '') or task_id}' "
                f"to Project '{to_project}' as well",
                _task_target(task_id),
            )
            for task_id in travelling
        ),
    ]
    plan.warnings = _move_profile_warnings(shared, to_project)

    def run() -> list[str]:
        _relocate("pids", profile_id, to_project, owners)
        for task_id in travelling:
            _relocate("tids", task_id, to_project, _projects_listing("tids", task_id))
        return []

    plan.run = run
    return plan


def _move_profile_warnings(shared: dict[str, list[str]], to_project: str) -> list[str]:
    """Which of a moving Profile's Tasks are staying, and why."""
    left = {task_id: users for task_id, users in shared.items() if users}
    if not left:
        return []

    tasks = _table("all_tasks")
    described = [
        f"'{tasks.get(task_id, {}).get('name', '') or task_id}' (also run by {', '.join(users[:3])})"
        for task_id, users in left.items()
    ]
    return [
        (
            f"{len(left)} of this Profile's {'Task stays' if len(left) == 1 else 'Tasks stay'} where "
            f"{'it is' if len(left) == 1 else 'they are'}: {'; '.join(described)}.  Moving "
            f"{'it' if len(left) == 1 else 'them'} to '{to_project}' would take "
            f"{'it' if len(left) == 1 else 'them'} out from under a Profile that is not moving."
        ),
    ]


# ##################################################################################
# Duplicate: a copy of an object, under a name of its own.
#
# Trivial for a Task and a Scene, which own nothing.  The whole difficulty is that a
# Profile owns Tasks and a Project owns everything, and a copy that shares its original's
# children is not a copy -- it is a second name for the same thing, and the first edit
# the user makes to "the copy" changes the original too.
#
# So a Profile and a Project are copied DEEP, and the ids and names of everything
# underneath are made new.  That in turn creates the only genuinely hard problem in this
# module: a Tasker configuration refers to Tasks and Scenes BY NAME, in the arguments of
# ordinary actions, and a deep copy that does not repoint those names produces a second
# Project whose actions all reach back into the first one.  It looks right in every view
# and is wrong the moment it runs.
#
# What is repointed is what the file states plainly: Perform Task's Name argument, and
# the Create/Show/Hide/Destroy Scene actions' own.  What is not is listed in the
# warnings, because a reference this cannot see is exactly the one the user has to check.
# ##################################################################################

# Create / Show / Hide / Destroy Scene.  Their arg0 is a Scene NAME -- the only other
# by-name reference in the action set besides Perform Task's.  The same four codes
# healthck names, for the same reason it has to name them: their argument is called "Name"
# rather than "Scene Name", so nothing can find them by looking at argument names.
_SCENE_NAME_CODES = {"46": "0", "47": "0", "48": "0", "49": "0"}


def _unique_name(base: str, taken: set[str]) -> str:
    """`base` if nothing has it, else 'base (copy)', 'base (copy 2)' and so on.

    Used for the children of a deep copy, whose names the user never chose.  Uniqueness is
    not cosmetic for a Task: Perform Task resolves a call by name across the whole file, so
    two Tasks sharing a name make every call to either of them ambiguous -- which is why
    healthck reports duplicate names as a finding of its own.
    """
    if base not in taken:
        return base
    candidate = f"{base} (copy)"
    counter = 2
    while candidate in taken:
        candidate = f"{base} (copy {counter})"
        counter += 1
    return candidate


def _copy_task_element(task_element: defusedxml.ElementTree.Element, new_id: str, new_name: str) -> object:
    """A deep copy of a Task, under a new id and name, ready to register.

    <cdate> is left as the original's -- when this Task's actions were first written is a
    fact about them and copying does not change it -- while <edate> is stamped now, which
    is what every other write in this program does to a Task it has just produced.
    """
    element = copy.deepcopy(task_element)
    element.set("sr", f"task{new_id}")
    _set_child_text(element, "id", str(new_id))
    _set_child_text(element, "nme", new_name)
    _set_child_text(element, "edate", _now_millis())
    return element


def _copy_profile_element(profile_element: defusedxml.ElementTree.Element, new_id: str, new_name: str) -> object:
    """A deep copy of a Profile, under a new id and name.  The Task links are left for the caller."""
    element = copy.deepcopy(profile_element)
    element.set("sr", f"prof{new_id}")
    _set_child_text(element, "id", str(new_id))
    _set_child_text(element, "nme", new_name)
    return element


def _copy_scene_element(scene_element: defusedxml.ElementTree.Element, new_name: str) -> object:
    """A deep copy of a Scene under a new name.

    A Scene's own sr is 'scene<its name>' rather than 'sceneN' -- unlike every other object
    in the format, which numbers them.  Measured across this repo's sample XML, where every
    Scene carries the name it is called; a copy keeping the original's sr would be the one
    place in the file that still says the old name.
    """
    element = copy.deepcopy(scene_element)
    element.set("sr", f"scene{new_name}")
    _set_child_text(element, "nme", new_name)
    return element


def _repoint_names(element: object, tasks: dict[str, str], scenes: dict[str, str]) -> int:
    """Rewrite by-name references inside a copied object to point at the copies.  Returns how many.

    Walks every <Action> anywhere beneath, which reaches a Scene's own inline anonymous
    Tasks as well as a Task's -- healthck makes the same point about its scan: those inline
    actions refer to Tasks and Scenes exactly as a named Task's do, and a second copy of
    this logic for them is how the two would drift apart.

    Only exact matches are rewritten.  A name assembled at run time ('%which') is not a
    reference this can resolve, and guessing at one would repoint a call the user meant to
    leave alone.
    """
    rewritten = 0
    for action in element.iter("Action"):
        code = _code(action)
        if code == taskedit.PERFORM_TASK_ACTION_CODE:
            mapping, arg_id = tasks, taskedit.PERFORM_TASK_NAME_ARG_ID
        elif code in _SCENE_NAME_CODES:
            mapping, arg_id = scenes, _SCENE_NAME_CODES[code]
        else:
            continue
        for child in action.findall("Str"):
            if child.attrib.get("sr") != f"arg{arg_id}":
                continue
            current = (child.text or "").strip()
            if current in mapping:
                child.text = mapping[current]
                rewritten += 1
    return rewritten


def plan_duplicate(kind: str, key: str, new_name: str = "") -> Plan:
    """Copy a Project, Profile, Task or Scene under a new name.

    `key` is the Task's or Profile's id, and the Project's or Scene's name -- the same
    split every table in this program uses.  `new_name` empty means "choose one", which is
    the original's with '(copy)' appended and a number after that if it is taken too.
    """
    planners = {
        TASK: _plan_duplicate_task,
        PROFILE: _plan_duplicate_profile,
        SCENE: _plan_duplicate_scene,
        PROJECT: _plan_duplicate_project,
    }
    planner = planners.get(kind)
    if planner is None:
        return _blocked(DUPLICATE, "Duplicate", Block("NOT-COPYABLE", f"A {kind} cannot be duplicated."))
    return planner(key, (new_name or "").strip())


def _plan_duplicate_task(task_id: str, new_name: str) -> Plan:
    """Copy one Task, into the same Projects as the original."""
    entry = _table("all_tasks").get(task_id)
    if entry is None:
        return _blocked(DUPLICATE, "Duplicate a Task", Block("NO-TASK", "That Task is not in this file."))

    task_name = entry.get("name", "") or task_id
    new_name = new_name or _unique_name(task_name, set(_table("all_tasks_by_name")))
    what = f"Duplicate Task '{task_name}' as '{new_name}'"
    where = _task_target(task_id)

    if taskedit.task_name_exists(new_name):
        return _blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(TASK, new_name), where))

    owners = _projects_listing("tids", task_id)
    actions = _actions(entry["xml"])

    plan = Plan(kind=DUPLICATE, what=what, elements=(entry["xml"],))
    plan.steps = [
        Step(
            f"Create Task '{new_name}' with all {len(actions)} of Task '{task_name}'s actions",
            where,
        ),
        *(Step(f"Add Task '{new_name}' to Project '{owner}'", Target(kind=PROJECT, key=owner)) for owner in owners),
    ]
    plan.warnings = [
        (
            f"Nothing calls '{new_name}' yet.  A copy of a Task is not a copy of the calls to it: every "
            f"existing Perform Task still runs '{task_name}'."
        ),
    ]

    def run() -> list[str]:
        new_id = str(taskedit.next_unique_task_or_profile_id())
        element = _copy_task_element(entry["xml"], new_id, new_name)
        taskedit.register_new_task(taskedit.EditableTask(task_id=new_id, task_element=element), new_name)
        for project_name in owners:
            profedit.add_task_to_project(new_id, project_name)
        return []

    plan.run = run
    return plan


def _plan_duplicate_profile(profile_id: str, new_name: str) -> Plan:
    """Copy one Profile, and the Tasks it runs, into the same Projects as the original.

    Its Tasks are copied too, and that is the decision worth arguing.  A Profile sharing
    its original's Entry Task is a Profile that cannot be edited: change what the copy does
    and the original does it too, which is precisely what somebody duplicating a Profile in
    order to vary it does not want.  The cost is a second Task per copy, which is what
    Tasker's own "Duplicate" does on the device.
    """
    entry = _table("all_profiles").get(profile_id)
    if entry is None:
        return _blocked(DUPLICATE, "Duplicate a Profile", Block("NO-PROFILE", "That Profile is not in this file."))

    profile_element = entry["xml"]
    profile_name = entry.get("name", "") or profile_id
    new_name = new_name or _unique_name(profile_name, set(_table("all_profiles_by_name")))
    what = f"Duplicate Profile '{profile_name}' as '{new_name}'"
    where = _profile_target(profile_id)

    if profedit.profile_name_exists(new_name):
        return _blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(PROFILE, new_name), where))

    owners = _projects_listing("pids", profile_id)
    task_ids = _profile_task_ids(profile_element)
    taken = set(_table("all_tasks_by_name"))
    task_names = {}
    for task_id in task_ids:
        original = _table("all_tasks").get(task_id, {}).get("name", "") or task_id
        task_names[task_id] = _unique_name(original, taken)
        taken.add(task_names[task_id])

    plan = Plan(kind=DUPLICATE, what=what, elements=(profile_element,))
    plan.steps = [
        Step(f"Create Profile '{new_name}' with the same conditions as '{profile_name}'", where),
        *(
            Step(
                f"Copy its Task '{_table('all_tasks').get(task_id, {}).get('name', '') or task_id}' as "
                f"'{task_names[task_id]}', and point the new Profile at that",
                _task_target(task_id),
            )
            for task_id in task_ids
        ),
        *(Step(f"Add Profile '{new_name}' to Project '{owner}'", Target(kind=PROJECT, key=owner)) for owner in owners),
    ]
    plan.warnings = _duplicate_profile_warnings(new_name, task_ids, owners)

    def run() -> list[str]:
        reserved: set[str] = set()
        copied_task_ids = {}
        for task_id in task_ids:
            source = _table("all_tasks").get(task_id)
            if source is None:
                continue
            new_task_id = str(taskedit.next_unique_task_or_profile_id(reserved))
            reserved.add(new_task_id)
            element = _copy_task_element(source["xml"], new_task_id, task_names[task_id])
            taskedit.register_new_task(
                taskedit.EditableTask(task_id=new_task_id, task_element=element),
                task_names[task_id],
            )
            copied_task_ids[task_id] = new_task_id

        new_profile_id = str(taskedit.next_unique_task_or_profile_id(reserved))
        element = _copy_profile_element(profile_element, new_profile_id, new_name)
        for child in element:
            if child.tag in ("mid0", "mid1"):
                child.text = copied_task_ids.get((child.text or "").strip(), (child.text or "").strip())

        editable = profedit.EditableProfile(
            profile_id=new_profile_id,
            profile_element=element,
            entry_task_id=element.findtext("mid0", "") or "",
            exit_task_id=element.findtext("mid1", "") or "",
        )
        profedit.register_new_profile(editable, new_name)
        # add_profile_to_project files the copied Tasks under the Project too -- see its
        # own docstring on why a Project-linked Task with no <tids> entry is invisible.
        for project_name in owners:
            profedit.add_profile_to_project(editable, project_name)
        return []

    plan.run = run
    return plan


def _duplicate_profile_warnings(new_name: str, task_ids: list[str], owners: list[str]) -> list[str]:
    """What a duplicated Profile does and does not carry with it."""
    warnings = []
    if not task_ids:
        warnings.append(
            f"Profile '{new_name}' has no Entry or Exit Task to copy, because the original has none.  A "
            f"Profile with nothing to run is valid in the file and does nothing on the device.",
        )
    if not owners:
        warnings.append(
            "The original Profile is not listed by any Project, so the copy is not either -- neither of "
            "them will appear in the Map, the Diagram or the Tree until one is.",
        )
    warnings.append(
        "The copy is enabled or disabled exactly as the original is, and its conditions are the same ones.  "
        "Two Profiles watching for the same event both fire on it.",
    )
    return warnings


def _plan_duplicate_scene(scene_name: str, new_name: str) -> Plan:
    """Copy one Scene, into the same Projects as the original."""
    entry = _table("all_scenes").get(scene_name)
    if entry is None:
        return _blocked(DUPLICATE, "Duplicate a Scene", Block("NO-SCENE", "That Scene is not in this file."))

    new_name = new_name or _unique_name(scene_name, set(_table("all_scenes")))
    what = f"Duplicate Scene '{scene_name}' as '{new_name}'"
    where = Target(kind=SCENE, key=scene_name, name=scene_name, project=_display_project("scenes", scene_name))

    if new_name in _table("all_scenes"):
        return _blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(SCENE, new_name), where))

    owners = _projects_listing("scenes", scene_name)

    plan = Plan(kind=DUPLICATE, what=what, elements=(entry["xml"],))
    plan.steps = [
        Step(f"Create Scene '{new_name}' with all of Scene '{scene_name}'s elements", where),
        *(Step(f"Add Scene '{new_name}' to Project '{owner}'", Target(kind=PROJECT, key=owner)) for owner in owners),
    ]
    plan.warnings = [
        (
            "The copy's elements fire the same Tasks the original's do -- a Scene names the Task an element "
            "runs, and those Tasks are not copied.  Editing one of them changes what both Scenes do."
        ),
        f"Nothing shows '{new_name}' yet: every existing Show Scene action still names '{scene_name}'.",
    ]

    def run() -> list[str]:
        element = _copy_scene_element(entry["xml"], new_name)
        _table("all_scenes")[new_name] = {"xml": element, "name": new_name}
        for project_name in owners:
            project_entry = _table("all_projects").get(project_name)
            if project_entry is not None:
                projedit.set_project_members(
                    project_entry["xml"],
                    "scenes",
                    [*_members(project_entry["xml"], "scenes"), new_name],
                )
        return []

    plan.run = run
    return plan


def _name_taken(kind: str, new_name: str) -> str:
    """The refusal for a name something else already has."""
    if kind == TASK:
        return (
            f"A Task named '{new_name}' is already in this file.  Perform Task calls a Task by name, so two "
            f"of them sharing one leaves every call to either ambiguous."
        )
    return f"A {kind.capitalize()} named '{new_name}' is already in this file.  Choose a different name."


# ##################################################################################
# Duplicating a Project: the deep one.
#
# A Project owns Profiles, Tasks and Scenes by listing their ids and names, so a copy has
# to produce a new one of each and a membership list pointing at those rather than at the
# originals.  Three things have to be right together, and each has its own failure:
#
#   NEW IDS.  A copy sharing the original's Task ids is not a copy at all -- both
#   Projects' <tids> then name the same Tasks, and the second Project is a second view of
#   the first.
#
#   NEW NAMES, AND THE LINKS THAT USE THEM REPOINTED.  A Task's id is private to the file;
#   its NAME is what Perform Task calls and what a Scene element runs.  Copy a Project
#   whose Tasks call one another and leave the names alone, and every call in the copy
#   reaches back into the original.
#
#   THE PROFILES' TASK LINKS REPOINTED, which are by id rather than by name and so need
#   doing separately from everything above.
#
# WHAT THIS DELIBERATELY DOES NOT COPY: global variables.  A Project does not own them --
# they are one namespace across the whole file, which is Tasker's design and not an
# oversight here -- so the copy reads and writes the same %Globals the original does.
# That is the single most likely surprise in this operation and it is the first warning.
# ##################################################################################

_PROJECT_SR_PREFIX = "proj"


def _next_project_sr() -> str:
    """The next free 'projN' attribute.

    A Project's sr is an internal counter unrelated to its <id> (which is a UUID) -- see
    projedit.create_new_project, whose own numbering this mirrors so that a duplicated
    Project and an added one cannot be handed the same one.
    """
    used = [
        int(entry["xml"].attrib.get("sr", "")[len(_PROJECT_SR_PREFIX) :])
        for entry in _table("all_projects").values()
        if entry["xml"].attrib.get("sr", "").startswith(_PROJECT_SR_PREFIX)
        and entry["xml"].attrib.get("sr", "")[len(_PROJECT_SR_PREFIX) :].isdigit()
    ]
    return f"{_PROJECT_SR_PREFIX}{max(used, default=0) + 1}"


@dataclass(frozen=True)
class _ProjectCopy:
    """The names and ids a Project duplication has decided on, before any of it exists.

    Worked out at PLAN time rather than at apply time, because the preview has to show them:
    "copy its Task 'Wake Up' as 'Wake Up (copy)'" is the line that tells a user the naming
    is not what they wanted, and it can only say that if the name is already chosen.  The
    ids are the exception -- those are drawn when the copy is made, since a Task added in
    another dialog between the preview and the Apply would otherwise take the id this had
    reserved.
    """

    task_names: dict[str, str]  # old Task id -> the copy's name
    profile_names: dict[str, str]  # old Profile id -> the copy's name
    scene_names: dict[str, str]  # old Scene name -> the copy's name


def _plan_project_copy(project_element: defusedxml.ElementTree.Element) -> _ProjectCopy:
    """Choose a free name for every child of a Project about to be duplicated.

    Each kind is checked against its own table AND against the names chosen earlier in this
    same call: two Tasks of one Project called 'Setup' and 'Setup (copy)' would otherwise
    both be offered 'Setup (copy)', and the second registration would silently overwrite
    the first in all_tasks_by_name.
    """
    task_names, taken_tasks = {}, set(_table("all_tasks_by_name"))
    for task_id in _members(project_element, "tids"):
        original = _table("all_tasks").get(task_id, {}).get("name", "") or task_id
        task_names[task_id] = _unique_name(original, taken_tasks)
        taken_tasks.add(task_names[task_id])

    profile_names, taken_profiles = {}, set(_table("all_profiles_by_name"))
    for profile_id in _members(project_element, "pids"):
        original = _table("all_profiles").get(profile_id, {}).get("name", "") or profile_id
        profile_names[profile_id] = _unique_name(original, taken_profiles)
        taken_profiles.add(profile_names[profile_id])

    scene_names, taken_scenes = {}, set(_table("all_scenes"))
    for scene_name in _members(project_element, "scenes"):
        scene_names[scene_name] = _unique_name(scene_name, taken_scenes)
        taken_scenes.add(scene_names[scene_name])

    return _ProjectCopy(task_names=task_names, profile_names=profile_names, scene_names=scene_names)


def _plan_duplicate_project(project_name: str, new_name: str) -> Plan:
    """Copy a Project and everything it owns."""
    entry = _table("all_projects").get(project_name)
    if entry is None:
        return _blocked(DUPLICATE, "Duplicate a Project", Block("NO-PROJECT", "That Project is not in this file."))

    project_element = entry["xml"]
    new_name = new_name or _unique_name(project_name, set(_table("all_projects")))
    what = f"Duplicate Project '{project_name}' as '{new_name}'"
    where = Target(kind=PROJECT, key=project_name, name=project_name)

    if projedit.project_name_exists(new_name):
        return _blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(PROJECT, new_name), where))

    chosen = _plan_project_copy(project_element)
    task_ids = _members(project_element, "tids")
    profile_ids = _members(project_element, "pids")
    scene_names = _members(project_element, "scenes")

    plan = Plan(kind=DUPLICATE, what=what, elements=(project_element,))
    plan.steps = _duplicate_project_steps(new_name, chosen, task_ids, profile_ids, scene_names, where)
    plan.warnings = _duplicate_project_warnings(project_name, chosen, task_ids)

    def run() -> list[str]:
        reserved: set[str] = set()
        new_task_ids: dict[str, str] = {}
        # Tasks first: the Profiles copied below point at them by id, and the Project's own
        # <tids> is the list those ids go into.
        for task_id in task_ids:
            source = _table("all_tasks").get(task_id)
            if source is None:
                continue
            new_id = str(taskedit.next_unique_task_or_profile_id(reserved))
            reserved.add(new_id)
            new_task_ids[task_id] = new_id
            taskedit.register_new_task(
                taskedit.EditableTask(
                    task_id=new_id,
                    task_element=_copy_task_element(source["xml"], new_id, chosen.task_names[task_id]),
                ),
                chosen.task_names[task_id],
            )

        new_profile_ids: dict[str, str] = {}
        for profile_id in profile_ids:
            source = _table("all_profiles").get(profile_id)
            if source is None:
                continue
            new_id = str(taskedit.next_unique_task_or_profile_id(reserved))
            reserved.add(new_id)
            new_profile_ids[profile_id] = new_id
            element = _copy_profile_element(source["xml"], new_id, chosen.profile_names[profile_id])
            for child in element:
                if child.tag in ("mid0", "mid1"):
                    current = (child.text or "").strip()
                    child.text = new_task_ids.get(current, current)
            profedit.register_new_profile(
                profedit.EditableProfile(
                    profile_id=new_id,
                    profile_element=element,
                    entry_task_id=element.findtext("mid0", "") or "",
                    exit_task_id=element.findtext("mid1", "") or "",
                ),
                chosen.profile_names[profile_id],
            )

        for scene_name in scene_names:
            source = _table("all_scenes").get(scene_name)
            if source is None:
                continue
            copied = chosen.scene_names[scene_name]
            _table("all_scenes")[copied] = {
                "xml": _copy_scene_element(source["xml"], copied),
                "name": copied,
            }

        # Every by-name reference inside everything just copied, repointed at the copies --
        # after all of them exist, so a Task calling a Task copied later is still caught.
        name_map = {
            _table("all_tasks").get(old, {}).get("name", "") or old: chosen.task_names[old] for old in new_task_ids
        }
        for new_id in new_task_ids.values():
            _repoint_names(_table("all_tasks")[new_id]["xml"], name_map, chosen.scene_names)
        for scene_name in scene_names:
            copied = chosen.scene_names.get(scene_name)
            if copied in _table("all_scenes"):
                _repoint_names(_table("all_scenes")[copied]["xml"], name_map, chosen.scene_names)

        element = copy.deepcopy(project_element)
        element.set("sr", _next_project_sr())
        _set_child_text(element, "id", str(uuid.uuid4()))
        _set_child_text(element, "name", new_name)
        projedit.register_new_project(projedit.EditableProject(project_name=new_name, project_element=element))
        # Written through set_project_members rather than by hand, so a Project that had no
        # <scenes> of its own gets one in Tasker's child order, and the <mdate> is stamped.
        for tag, ids in (
            ("tids", [new_task_ids[old] for old in task_ids if old in new_task_ids]),
            ("pids", [new_profile_ids[old] for old in profile_ids if old in new_profile_ids]),
            ("scenes", [chosen.scene_names[old] for old in scene_names if old in chosen.scene_names]),
        ):
            projedit.set_project_members(element, tag, ids)
        return []

    plan.run = run
    return plan


def _duplicate_project_steps(
    new_name: str,
    chosen: _ProjectCopy,
    task_ids: list[str],
    profile_ids: list[str],
    scene_names: list[str],
    where: Target,
) -> list[Step]:
    """What a Project duplication will do.  Counts, then the renamings, which are the surprise."""
    steps = [Step(f"Create Project '{new_name}'", where)]
    for label, count in (
        ("Profile", len(profile_ids)),
        ("Task", len(task_ids)),
        ("Scene", len(scene_names)),
    ):
        if count:
            steps.append(Step(f"Copy its {count} {label}{'' if count == 1 else 's'}, each under a new name"))

    renamed = [
        (original, copied)
        for original, copied in (
            *((_table("all_tasks").get(old, {}).get("name", "") or old, new) for old, new in chosen.task_names.items()),
            *(
                (_table("all_profiles").get(old, {}).get("name", "") or old, new)
                for old, new in chosen.profile_names.items()
            ),
            *chosen.scene_names.items(),
        )
        if original != copied
    ]
    steps.extend(Step(f"    '{original}' becomes '{copied}'") for original, copied in renamed[:12])
    if len(renamed) > 12:
        steps.append(Step(f"    ...and {len(renamed) - 12} more"))

    steps.append(
        Step("Point the copies' Perform Task and Show/Hide Scene actions at the copies rather than the originals"),
    )
    return steps


def _duplicate_project_warnings(project_name: str, chosen: _ProjectCopy, task_ids: list[str]) -> list[str]:
    """What a duplicated Project shares with its original whether the user wants it to or not."""
    warnings = [
        (
            "Global variables are not copied and cannot be: Tasker keeps one set of them for the whole "
            "configuration, so the copy reads and writes exactly the same %Globals the original does.  Two "
            "Projects both setting %Mode will overwrite each other."
        ),
    ]

    shared_tasks = [task_id for task_id in task_ids if len(_projects_listing("tids", task_id)) > 1]
    if shared_tasks:
        named = ", ".join(
            f"'{_table('all_tasks').get(task_id, {}).get('name', '') or task_id}'" for task_id in shared_tasks[:5]
        )
        warnings.append(
            f"{named} {'is' if len(shared_tasks) == 1 else 'are'} listed by other Projects as well as "
            f"'{project_name}'.  A copy is made for the new Project regardless, so those Projects keep the "
            f"original and are not affected.",
        )

    warnings.append(
        "References this cannot see are not repointed: a home screen widget, a Tasker shortcut, or a Task "
        "name built out of a variable at run time still names the original.  Only Perform Task's Name and "
        "the Create/Show/Hide/Destroy Scene actions' own are rewritten.",
    )

    if any(name.endswith(")") for name in chosen.task_names.values()):
        warnings.append(
            "The copied Tasks are renamed because Perform Task resolves a call by name across the whole "
            "file, and two Tasks sharing a name make every call to either of them ambiguous.  Rename them "
            "afterwards if the suffix is not what you want -- Edit Task's Rename repoints the calls with it.",
        )
    return warnings


# ##################################################################################
# What there is to choose from.
#
# Here rather than in the dialog for the reason mapswap's own choice builders are: the
# labels have to say what the object IS -- which Project a Task is in, which of a Task's
# actions are calls -- and every one of those facts is read off the tables this module
# already walks.  A dialog building them itself would be a second reader of the same
# structures, drifting from this one.
# ##################################################################################


def task_choices(scope: mapjump.Scope | None = None) -> list[tuple[str, str]]:
    """Every Task as (id, label), Project named, sorted the way a user looks for one.

    The Project is in the label because Task names are not unique across a configuration
    and routinely repeat -- 'Setup' in four Projects is ordinary -- so an id-keyed pulldown
    showing bare names would offer four identical entries.

    `scope` narrows the list to what the app is currently displaying -- see extract_scope,
    which is the only caller that passes one and explains why.  None, or an empty Scope,
    offers every Task in the file.
    """
    entries = [
        (task_id, entry.get("name", "") or f"Task {task_id}", _display_project("tids", task_id))
        for task_id, entry in _table("all_tasks").items()
        if scope is None or scope.allows(TASK, task_id)
    ]
    entries.sort(key=lambda item: (item[2].lower(), item[1].lower()))
    return [
        (task_id, f"{name}  ({project})" if project else f"{name}  (no Project)") for task_id, name, project in entries
    ]


def extract_scope() -> mapjump.Scope:
    """The Tasks an Extract may be asked about: the ones the single-item pulldowns select.

    WHY THIS ONE OPERATION IS SCOPED AND THE OTHER THREE ARE NOT.

    Extract is the only one that reaches INSIDE a Task, and the only one whose second and
    third questions -- which actions, from where to where -- are about a Task's contents
    rather than about the Task as a whole.  Narrowing it to the selected Task is the same
    contract every Edit button in that panel already keeps ("Select a single Task first
    (Task pulldown above)"), so Extract behaves like the buttons beside it rather than
    being the one that ignores the selection.

    The other three name an object and do something to it as a whole.  Nothing about
    duplicating a Project or moving a Profile depends on what is selected for display, and
    narrowing those would force somebody to change what they are displaying in order to
    tidy up something else -- coupling two things that have no business being coupled.

    mapjump.current_scope is the whole of the rule: a single Task selected puts that Task
    in scope and nothing else, a single Profile puts the Tasks it runs in scope, and a
    Project puts the Tasks it lists in scope.  A Scene has no Tasks of its own, so it
    scopes to none -- the dialog says so rather than showing an empty pulldown with no
    reason for being empty.  Nothing selected is not a scope at all, and every Task is
    offered; Extract has its own Task picker, so unlike Edit Task it has no reason to
    refuse outright.
    """
    return mapjump.current_scope()


def profile_choices() -> list[tuple[str, str]]:
    """Every Profile as (id, label), Project named.  Same reasoning as task_choices."""
    entries = [
        (profile_id, entry.get("name", "") or f"Profile {profile_id}", _display_project("pids", profile_id))
        for profile_id, entry in _table("all_profiles").items()
    ]
    entries.sort(key=lambda item: (item[2].lower(), item[1].lower()))
    return [
        (profile_id, f"{name}  ({project})" if project else f"{name}  (no Project)")
        for profile_id, name, project in entries
    ]


def project_choices() -> list[str]:
    """Every Project name, sorted."""
    return sorted(_table("all_projects"), key=str.lower)


def scene_choices() -> list[str]:
    """Every Scene name, sorted."""
    return sorted(_table("all_scenes"), key=str.lower)


def action_choices(task_id: str) -> list[tuple[int, str]]:
    """A Task's actions as (number, label), counted from 1.

    Numbered as the Map prints them -- 1, 2, 3 -- because that is the number the user is
    looking at when they decide which actions to extract, and because every other report in
    this program counts them that way (healthck, varxref and taskflow each enumerate
    actions_in_map_order with start=1).  Counting from 0 here made every jump land one
    action early, and made action 0 lose its anchor outright: Target.anchor appends the
    action only `if self.action`, and 0 is falsy.  A label the user gave an
    action is shown alongside its name: on a Task of forty Flashes it is the only thing
    telling one from another.
    """
    entry = _table("all_tasks").get(task_id)
    if entry is None:
        return []
    choices = []
    for number, action in enumerate(_actions(entry["xml"]), start=1):
        label = (action.findtext("label") or "").strip().splitlines()
        suffix = f"  -- {label[0][:40]}" if label and label[0] else ""
        choices.append((number, f"{number}: {_action_name(action)}{suffix}"))
    return choices


def call_choices(task_id: str) -> list[tuple[int, str]]:
    """Only the Perform Task actions of a Task -- the ones an inline can be asked about.

    Filtered here rather than offering every action and refusing the rest in the preview.
    A pulldown of forty actions where thirty-eight produce "that is not a Perform Task" is
    a worse answer than a pulldown of two, and the refusal still exists for the case where
    the Task was edited while the dialog was open.
    """
    entry = _table("all_tasks").get(task_id)
    if entry is None:
        return []
    choices = []
    for number, action in enumerate(_actions(entry["xml"]), start=1):
        if _code(action) != taskedit.PERFORM_TASK_ACTION_CODE:
            continue
        called = _string_argument(action, taskedit.PERFORM_TASK_NAME_ARG_ID) or "(no Task named)"
        choices.append((number, f"{number}: Perform Task '{called}'"))
    return choices


# ##################################################################################
# The preview, and the one thing it is for.
# ##################################################################################


def report_rows(plan: Plan) -> list[Row]:
    """The plan as mapjump Rows: what it is, what stops it, what to read, what it will do.

    Blocks first and steps last, which is the reverse of how the plan was built and the
    order the user reads in.  A refusal is the whole answer when there is one -- printing
    the steps above it would show a user a list of things that are not going to happen and
    make them scroll for the reason.

    Rows rather than a string so the preview is clickable in the Map the way a health-check
    finding is.  For this feature that is not decoration: "actions 3-6 of Task 'Morning'"
    is not enough to decide by, and going to look at them is the only way to be sure.
    """
    rows: list[Row] = [Row(plan.what), Row("")]

    if plan.blocks:
        rows.append(Row(f"CANNOT BE DONE ({len(plan.blocks)})"))
        for block in plan.blocks:
            rows.append(Row(f"  {block.where.label}" if block.where else f"  {block.reason}", block.where))
            rows.extend(Row(f"      {line}") for line in _wrapped(block.explanation))
        return rows

    if plan.warnings:
        rows.extend((Row(f"BEFORE YOU DO THIS ({len(plan.warnings)})"), Row("")))
        for warning in plan.warnings:
            rows.extend(Row(f"  {line}") for line in _wrapped(warning))
            rows.append(Row(""))

    rows.append(Row(f"WHAT WILL HAPPEN ({len(plan.steps)} {'step' if len(plan.steps) == 1 else 'steps'})"))
    for number, step in enumerate(plan.steps, start=1):
        # A step whose text is already indented is a continuation of the one above it (the
        # renamings under a Project duplication), and numbering those would imply they are
        # separate things that happen in turn.
        prefix = "     " if step.text.startswith("    ") else f"  {number:>2}. "
        rows.append(Row(f"{prefix}{step.text.strip()}", step.where))

    if not plan.steps:
        rows.append(Row("  Nothing."))
    return rows


_REPORT_WIDTH = 88


def _wrapped(text: str) -> list[str]:
    """A paragraph broken to the report's width, on spaces.

    The explanations here are prose -- several sentences of it -- where healthck's and
    mapswap's are one line, so they are the first thing in this program that has to wrap.
    Done on the Row rather than left to the widget because the same text is written to a
    text file, where nothing is going to wrap it at all.
    """
    words, lines, current = text.split(), [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > _REPORT_WIDTH:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines or [""]


def write_refactor_report(rows: list[Row]) -> str:
    """Save the preview as text, the way mapfind, varxref and mapswap save theirs.

    Worth having for the refactor the user decided NOT to do as much as the one they did:
    a block's explanation names the actions that would have to be selected differently, and
    that is a work list which does not survive closing the dialog otherwise.
    """
    stamp = datetime.now().strftime("_%m-%d-%Y_%H-%M-%S")  # noqa: DTZ005
    file_name = append_to_filename(REFACTOR_FILE, stamp)
    if not file_name:
        return ""
    try:
        with open(os.path.join(os.getcwd(), file_name), "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Refactor report could not be written: {error}")
        return ""
    return file_name


def apply(plan: Plan) -> tuple[bool, list[str]]:
    """Do the refactor.  Returns (whether it was done, anything that went wrong).

    Three gates, in this order, and each is a different question:

      IS IT ALLOWED.  A Plan carrying blocks is a preview of something that was refused,
      and apply() refuses it again rather than trusting the dialog to have disabled its
      own button.  The blocks are returned as the errors, so a caller that reached here
      wrongly still shows the user the real reason instead of a bare failure.

      IS IT STILL THE SAME FILE.  Every element the plan closed over is re-checked against
      the loaded configuration.  A preview can sit on screen while the user deletes the
      Task it describes in another dialog, and a refactor that ran against a detached
      element would rewrite a tree nothing renders from -- silently doing nothing, or
      worse, resurrecting a deleted Task by registering a copy of it.

      DID IT WORK.  Anything the operation itself could not do comes back as an error, and
      a raise from inside it is caught rather than escaping into the GUI -- a half-applied
      refactor is exactly what the undo checkpoint below exists for, and the user needs to
      be told, not shown a traceback.

    ONE undo block around the whole thing, and the outermost one.  Extract writes a new
    Task, edits an old one and edits a Project; those are one thing the user did and cost
    one press of Undo, which is what sessundo's re-entrancy is for (see its note on
    deleting a Project, which runs ten mutators for one undoable action).
    """
    if plan.blocks:
        return False, [block.explanation for block in plan.blocks]
    if plan.run is None:
        return False, ["There is nothing to apply."]

    attached = maputil2.attached_elements()
    if any(id(element) not in attached for element in plan.elements):
        return False, [
            (
                "Something this refactor was going to change is no longer in the configuration -- it was "
                "deleted, or another file was loaded, while this preview was open.  Nothing was changed.  "
                "Build the preview again."
            ),
        ]

    with sessundo.undoable(plan.what):
        try:
            errors = plan.run()
        except (AttributeError, KeyError, TypeError, ValueError) as failure:
            logger.error(f"Refactor '{plan.what}' failed: {failure}")
            return False, [f"{plan.what} could not be completed: {failure}"]

    return not errors, errors
