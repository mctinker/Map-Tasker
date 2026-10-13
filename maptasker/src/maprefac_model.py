"""maprefac_model: what a refactor is made of -- the Step, Block and Plan every move builds, and how the tree is read.

The four moves (extract, inline, move, duplicate) and the apply that carries a Plan out are described in
maprefac's header; this is the vocabulary they share: the tables a Plan reads, the variables that would stop
being the same variable, and the control flow a rearrangement would break."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src import mapjump, taskedit_model, varxref
from maptasker.src.actionc import action_codes
from maptasker.src.mapjump import PROFILE, TASK, Target
from maptasker.src.varxref import VARIABLE_PATTERN

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

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


def blocked(kind: str, what: str, *blocks: Block) -> Plan:
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


def _tables(state: RunState) -> dict:
    """The four object tables, whatever state the program is in."""
    return state.tasker_root_elements or {}


def object_table(name: str, state: RunState) -> dict:
    """One object table -- all_tasks, all_profiles, all_projects, all_scenes -- or {}."""
    return _tables(state=state).get(name) or {}


def members(project_element: Element, tag: str) -> list[str]:
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


def projects_listing(tag: str, member: str, state: RunState) -> list[str]:
    """EVERY Project whose <pids>/<tids>/<scenes> names this member, in table order.

    Deliberately not mapfind's project-membership map, which answers "which Project does
    this belong to" with one name.  That is the right answer for a report, which prints one
    location, and the wrong one for a rewrite: nothing in the format stops two Projects
    listing the same Task id, real backups in this repo do it, and a move that updated the
    first owner and left the second would leave the Task owned by both -- the exact
    inconsistency taskedit_save.delete_task scans every Project to avoid.
    """
    return [
        name
        for name, entry in object_table("all_projects", state=state).items()
        if member in members(entry["xml"], tag)
    ]


def display_project(tag: str, member: str, state: RunState) -> str:
    """The one Project name a Target should print for this member, or "" for none."""
    owners = projects_listing(tag, member, state=state)
    return owners[0] if owners else ""


def task_target(task_id: str, state: RunState) -> Target:
    """The Target for a Task, with the Project a report would file it under."""
    entry = object_table("all_tasks", state=state).get(task_id) or {}
    return Target(
        kind=TASK, key=task_id, name=entry.get("name", ""), project=display_project("tids", task_id, state=state)
    )


def profile_target(profile_id: str, state: RunState) -> Target:
    """The Target for a Profile, with the Project a report would file it under."""
    entry = object_table("all_profiles", state=state).get(profile_id) or {}
    return Target(
        kind=PROFILE,
        key=profile_id,
        name=entry.get("name", ""),
        project=display_project("pids", profile_id, state=state),
    )


def actions_of(task_element: Element) -> list:
    """A Task's actions in the order Tasker runs them.

    mapjump's, not findall("Action")'s.  Tasker orders actions by the numeric suffix of
    sr="actN" and writes them to the file sorted as TEXT -- act0, act1, act10, act2 -- so
    the eighth element in the file is routinely not the eighth action.  Every number this
    module prints, blocks on, or renumbers is a run-order number, because that is the only
    number the user has ever seen.
    """
    return mapjump.actions_in_map_order(task_element)


def renumber(actions: list) -> None:
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


def action_code(action: Element) -> str:
    """An action's <code>, or "" -- the one field every action has."""
    return (action.findtext("code") or "").strip()


def string_argument(action: Element, arg_id: str) -> str:
    """The text of an action's <Str sr="argN">, or "".

    Matched on the "sr" attribute rather than on child order, the way every reader in this
    codebase reaches an argument -- Tasker does not guarantee the order.
    """
    wanted = f"arg{arg_id}"
    for child in action.findall("Str"):
        if child.attrib.get("sr") == wanted:
            return (child.text or "").strip()
    return ""


def action_name(action: Element) -> str:
    """What this action is called, for a preview line.  Its code, when nothing names it."""
    code = action_code(action)
    entry = action_codes.get(f"{code}t")
    return entry.name if entry is not None else f"code {code}"


def describe_actions(numbers: list[int]) -> str:
    """'actions 3-6' or 'action 3' -- how a run of actions is named in prose."""
    if len(numbers) == 1:
        return f"action {numbers[0]}"
    return f"actions {numbers[0]}-{numbers[-1]}"


def now_millis() -> str:
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


def variable_names(elements: list) -> set[str]:
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


def local_names(elements: list) -> set[str]:
    """The subset of those names that Tasker scopes to the running Task.

    Scope comes from varxref, which is where Tasker's own rule lives (at least one upper
    case letter makes a name global) along with the two exceptions to it that matter:
    Tasker's documented built-ins, and the %par1/%caller/%priority/%err family Tasker sets
    itself.  Neither of those is the user's to lose track of, so neither is reported here --
    %par1 is handled separately by the warnings that are specifically about it, because what
    happens to a parameter across one of these moves is a different fact from what happens
    to a local.
    """
    return {name for name in variable_names(elements) if varxref.scope_of(name) == varxref.LOCAL}


# A Perform Task's two parameters, as the called Task reads them.  Tasker sets these rather
# than the user, so varxref classifies them apart from locals -- and every operation here
# that crosses a Perform Task boundary changes whose parameters they are.
PARAMETERS = ("%par1", "%par2")


def shared_locals_warning(inside: list, outside: list, moving_to: str) -> str:
    """The warning for locals used on both sides of a split, or "" when there are none.

    Named rather than counted.  "3 local variables are shared" tells the user there is a
    problem and nothing about where to look; the names are what they take back to the Task.
    """
    shared = sorted(local_names(inside) & local_names(outside))
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

_IF = taskedit_model.IF_ACTION_CODE  # "37"
_ELSE = taskedit_model.ELSE_ACTION_CODE  # "43"
_END_IF = taskedit_model.END_IF_ACTION_CODE  # "38"
_FOR = "39"
_END_FOR = "40"
# "Goto".  Its argument is an action NUMBER, and every operation in this module renumbers
# actions, so a Goto anywhere in a Task being rearranged is a jump that will land somewhere
# else afterwards -- silently, and to a perfectly valid action.
_GOTO = "135"

_CONTROL_FLOW = (_IF, _ELSE, _END_IF, _FOR, _END_FOR, _GOTO)


def control_flow_imbalance(numbered: list[tuple[int, object]]) -> str:
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
        code = action_code(action)
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


def goto_numbers(actions: list) -> list[int]:
    """The positions of every Goto among these actions, counted from 1 as the Map prints them."""
    return [number for number, action in enumerate(actions, start=1) if action_code(action) == _GOTO]


def control_flow_codes(actions: list) -> set[str]:
    """Which of the flow-control codes appear among these actions."""
    return {action_code(action) for action in actions} & set(_CONTROL_FLOW)


def perform_task_callers(task_name: str, state: RunState) -> list[Target]:
    """Every action in the file that calls this Task by name, as clickable Targets.

    A targeted scan rather than a healthck index: that builds a picture of the whole
    configuration to answer a hundred questions, and this asks one.  Matched exactly, the
    way Tasker matches it -- a call naming a Task built out of a variable at run time
    ('%which') is not resolvable here and is not counted, which healthck's _is_resolvable
    says at greater length.
    """
    callers: list[Target] = []
    for caller_id, entry in object_table("all_tasks", state=state).items():
        for number, action in enumerate(actions_of(entry["xml"]), start=1):
            if action_code(action) != taskedit_model.PERFORM_TASK_ACTION_CODE:
                continue
            if string_argument(action, taskedit_model.PERFORM_TASK_NAME_ARG_ID) == task_name:
                callers.append(task_target(caller_id, state=state).at_action(number))
    return callers


def profile_task_ids(profile_element: Element) -> list[str]:
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


def extract_scope(state: RunState) -> mapjump.Scope:
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
    return mapjump.current_scope(state=state)
