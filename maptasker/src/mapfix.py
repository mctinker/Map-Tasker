"""mapfix: the repairs the Health Check can make for itself, with a preview."""

#! /usr/bin/env python3

#                                                                                        #
# mapfix: turning a Health Check finding into a change.                                   #
#                                                                                        #
# The check reports forty-five kinds of problem and, until this, repaired none of them.   #
# Most of the forty-five have no single right answer -- there is no way to know which of  #
# two Profiles fighting over the same setting is the one that was meant, and a password   #
# written into an action is not this program's to replace.  A handful do, and those are   #
# the ones here:                                                                          #
#                                                                                        #
#   MISSING-COLLISION            set the Task's Collision Handling                        #
#   NO-TIMEOUT                   write a timeout into the action that has none            #
#   FLOW-IF-WITHOUT-END-IF       close the block with an 'End If'                         #
#   FLOW-FOR-WITHOUT-END-FOR     close the block with an 'End For'                        #
#   FLOW-GOTO-MISSING-LABEL      point the 'Goto' at a label the Task actually carries     #
#   UNREFERENCED-TASK            delete the Task                                          #
#                                                                                        #
# Same contract as healthck / maprefac / mapswap -- reads and writes                      #
# PrimeItems.tasker_root_elements and nothing else, no GUI import, identity from mapjump  #
# -- and the same two rules every writer in this program follows:                         #
#                                                                                        #
#   NOTHING IS APPLIED UNSEEN.  plan_fixes() and apply() are separate, apply() only ever  #
#   takes a plan, and every repair in that plan is a clickable mapjump Row -- saying what #
#   the field holds now and what it will hold -- before it is a change.                   #
#                                                                                        #
#   ONE UNDO.  Repairing thirty findings is one thing the user did and costs one press of #
#   Undo, so the whole of apply() runs inside a single re-entrant sessundo.undoable block. #
#                                                                                        #
# WHY THIS IS SHAPED LIKE mapswap AND NOT LIKE maprefac                                   #
#                                                                                        #
# A refactor is ONE change made of steps that are meaningless apart, so maprefac's Plan is #
# all-or-nothing.  A list of repairs is the opposite: each finding is independent of every #
# other, the user will want some and not others, and a reason one cannot be made is no     #
# reason to abandon the rest.  So this has mapswap's tick box per repair and mapswap's     #
# per-item Skip, and apply() is a loop that can report one failure and carry on.           #
#                                                                                        #
# WHAT A CHOICE IS FOR                                                                    #
#                                                                                        #
# Three of the six repairs cannot be made without a decision that is the user's: which     #
# collision handling, how long a timeout, which label.  Those are carried as a Choice on   #
# the repair rather than guessed at, and the one with no defensible default -- the label    #
# -- starts unmade, so the repair cannot be applied until somebody picks one.  A default    #
# invented here would be applied by everybody who never looked, which is the failure this   #
# whole family of modules is arranged to prevent.                                           #
#                                                                                        #
# WHAT IS DELIBERATELY NOT REPAIRED                                                       #
#                                                                                        #
# Everything whose repair would be a guess.  A broken Perform Task names a Task that is    #
# not in the file, and picking the nearest name in the backup is how a Task comes to call  #
# something it was never meant to call.  A duplicated name, two Profiles in conflict, a    #
# variable that is read and never set, a secret written into an argument -- each of those  #
# is a decision about what the configuration is FOR, and the report exists to put it in     #
# front of the person who can make it.                                                     #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src import clock, healthck, mapswap, maputil2, objprops, proflint, sessundo, taskedit
from maptasker.src.actionc import action_codes
from maptasker.src.mapjump import TASK, Row, Target, actions_in_map_order, text_report
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FIX_FILE, logger

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    import defusedxml.ElementTree


# ##################################################################################
# What can be repaired.
#
# One entry per tag, because the tag is the unit everything else in the health check is
# keyed by -- the chooser panel's boxes, the report's grouping, the skip set saved in the
# settings file.  The prose is the offer as the preview makes it, written for somebody
# deciding whether they want it rather than as a restatement of the finding.
# ##################################################################################
MISSING_COLLISION = "MISSING-COLLISION"
NO_TIMEOUT = "NO-TIMEOUT"
IF_WITHOUT_END_IF = "FLOW-IF-WITHOUT-END-IF"
FOR_WITHOUT_END_FOR = "FLOW-FOR-WITHOUT-END-FOR"
GOTO_MISSING_LABEL = "FLOW-GOTO-MISSING-LABEL"
UNREFERENCED_TASK = "UNREFERENCED-TASK"

# In the order the preview groups them: the two that change a setting, the two that close
# a block, the one that repoints a jump, and the delete last -- which is also roughly the
# order of how much of the configuration each one touches.
FIXABLE_TAGS: tuple[str, ...] = (
    MISSING_COLLISION,
    NO_TIMEOUT,
    IF_WITHOUT_END_IF,
    FOR_WITHOUT_END_FOR,
    GOTO_MISSING_LABEL,
    UNREFERENCED_TASK,
)

# What each repair does, in one line, for the panel that offers them.
WHAT_IT_DOES: dict[str, str] = {
    MISSING_COLLISION: "Set the Task's Collision Handling, so a trigger arriving mid-run is not dropped.",
    NO_TIMEOUT: "Write a timeout into an action that can otherwise block for ever.",
    IF_WITHOUT_END_IF: "Close an unclosed 'If' with an 'End If' at the end of the Task.",
    FOR_WITHOUT_END_FOR: "Close an unclosed 'For' with an 'End For' at the end of the Task.",
    GOTO_MISSING_LABEL: "Point a broken 'Goto' at a label the Task actually carries.",
    UNREFERENCED_TASK: "Delete a Task that nothing in this file runs.",
}

# Tasker's control-flow action codes, spelled here rather than imported from taskflow:
# that module reads them and this one WRITES them, and a writer that borrowed a reader's
# private constants would be a rename away from building the wrong action.
_END_IF_CODE = "38"
_END_FOR_CODE = "40"
_GOTO_LABEL_ARG = "2"  # <Str sr="arg2"> -- the label a "Goto action label" names.

# Which closer closes which unclosed block, by the tag the finding carries.
_CLOSER_OF_TAG = {
    IF_WITHOUT_END_IF: (_END_IF_CODE, "End If", "If"),
    FOR_WITHOUT_END_FOR: (_END_FOR_CODE, "End For", "For"),
}

# Tasker's <rty>, as objprops reads it: index 0 is the default and is written by leaving
# the tag out, which is exactly the state MISSING-COLLISION reports.  So the two offered
# here are the two that are not that state.
_COLLISION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("1", objprops.COLLISION_CHOICES[1]),
    ("2", objprops.COLLISION_CHOICES[2]),
)

# The timeout offered, in seconds.  Generous on purpose: the finding's own wording is that
# "a timeout that is generous is still an exit", and a repair that made a working Task
# start giving up after five seconds would be a worse outcome than the hang it prevents.
# Every action proflint reports takes its timeout in seconds -- the two that take
# milliseconds (Flash, Wait For Scene v2 Result) are both dialogs, which it excludes.
DEFAULT_TIMEOUT_SECONDS = "60"


def whole_seconds(value: str) -> str:
    """A timeout as Tasker stores it -- the digits alone -- or "" when it is not one.

    Public, and tolerant of a trailing ".0", because of where the value comes from: a
    NiceGUI number box hands back a FLOAT whatever its format string says, so the dialog's
    "60" arrives here as "60.0".  Normalising in one place is what keeps the preview line
    ("a timeout of 60 seconds") and what gets written into the XML from disagreeing about
    the same number -- and what stops a perfectly ordinary entry being refused as unusable.

    Empty for anything that is not a whole number above zero: a blank box, a fraction of a
    second, and zero itself -- which is the state being repaired, so writing it back is not
    a repair.
    """
    try:
        seconds = float(value.strip())
    except (AttributeError, ValueError):
        return ""
    return str(int(seconds)) if seconds > 0 and seconds == int(seconds) else ""


# How many repairs a plan will build.  A configuration with more findings than this has a
# problem that is not going to be solved one tick box at a time, and a preview of several
# thousand rows is one nobody reads.  Reported rather than silently cut -- see plan_fixes.
_PLAN_LIMIT = 500


# What a repair needs decided before it can be made.
CHOICE_OPTIONS = "options"  # one of a fixed list
CHOICE_NUMBER = "number"  # a whole number the user types


@dataclass(frozen=True)
class Choice:
    """A decision that belongs to the user, carried on the repair that needs it.

    `value` is the default, and "" means there is no defensible one -- which label a broken
    Goto was meant to name is not something this file can know, so that repair arrives
    unmade and cannot be applied until somebody picks.  A default invented for it would be
    taken by everybody who never looked.

    `options` is empty for CHOICE_NUMBER, where what is offered is a box rather than a list.
    """

    kind: str
    prompt: str
    value: str = ""
    options: tuple[tuple[str, str], ...] = ()
    units: str = ""  # "seconds" -- what the number is in, for CHOICE_NUMBER

    def label_of(self, value: str) -> str:
        """How a chosen value reads in the preview."""
        for option, label in self.options:
            if option == value:
                return label
        return f"{value} {self.units}".strip() if value else "(not chosen)"


@dataclass(frozen=True)
class Fix:
    """One repair, before it is made.

    Frozen for Site's and Target's reason: a repair is a fact worked out about the file
    once, and what the user changes about it -- whether it is ticked, what they chose --
    lives on the Plan, not here.

    `where` is the object or the action the finding was about, so the preview's line and
    the click on it can never disagree with the report the user read a moment ago.

    `describe` is a function of the chosen value rather than a string, because for three of
    the six repairs the value IS what happens: "Set Collision Handling to 'Run Both
    Together'" and "... to 'Abort Existing Task'" are two different offers.

    `elements` is every live element the repair depends on, checked by apply() before any
    of it runs.  A PLAN IS ONLY VALID UNTIL THE TREE IS RELOADED, for the reason mapswap's
    Site gives at greater length: a preview can sit on screen while the user edits
    something else in another dialog.
    """

    tag: str
    where: Target
    before: str  # what is there now, in the user's terms
    describe: Callable[[str], str]  # what will happen, given the chosen value
    note: str = ""  # anything to read before ticking this one
    choice: Choice | None = None
    elements: tuple = ()
    # Repairs to one Task that must happen in a particular order, highest first.  Only the
    # block closers use it -- see plan_fixes.
    order: int = 0
    run: Callable[[str], None] | None = None

    @property
    def identity(self) -> tuple:
        """What this repair points at, in a form that survives the plan being rebuilt.

        mapswap.Change.identity's reason, unchanged: a preview is thrown away whenever the
        dialog closes, so a user's ticks can only be carried over by describing what they
        were ticking and never by remembering their POSITION in the list.
        """
        return (self.tag, self.where.anchor, self.before)


@dataclass(frozen=True)
class Skip:
    """A finding this module knows how to repair and cannot repair HERE, with the reason.

    Carried in the plan rather than dropped, and printed above the repairs.  A silent skip
    is the worst outcome this feature can produce: the user reads "6 findings repaired",
    believes the health check is that much shorter now, and the two it could not touch are
    the two still waiting.
    """

    tag: str
    where: Target
    explanation: str


@dataclass
class Plan:
    """Everything the repairs would do, before any of them are done.

    Ordinary dataclass, not frozen: the dialog ticks, unticks and chooses, and `selected`
    and `chosen` are what it writes.  Everything else is built once and read-only by
    convention.
    """

    what: str  # one line for the header, the report and the Undo label
    fixes: list[Fix] = field(default_factory=list)
    skips: list[Skip] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # true of the plan as a whole
    # Positions in `fixes` that are ticked, and what has been chosen for the ones that ask.
    selected: set[int] = field(default_factory=set)
    chosen: dict[int, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Nothing to offer.  Distinct from 'nothing found' only in that skips may exist."""
        return not self.fixes

    def value_of(self, position: int) -> str:
        """What has been chosen for this repair -- the user's answer, or the default."""
        fix = self.fixes[position]
        if fix.choice is None:
            return ""
        return self.chosen.get(position, fix.choice.value)

    def is_ready(self, position: int) -> bool:
        """Whether this repair can be applied at all.

        False only for a repair whose Choice has no default and has not been made.  The
        dialog leaves those unticked and apply() refuses them, so the one repair that
        cannot have a sensible default cannot be made by not looking at it.
        """
        return self.fixes[position].choice is None or bool(self.value_of(position))

    def describe(self, position: int) -> str:
        """The one line saying what this repair will do, for the value chosen now."""
        return self.fixes[position].describe(self.value_of(position))

    def tally(self) -> str:
        """'7 findings in 4 Tasks' -- the line the button's confirmation asks about.

        Counted over the TICKED repairs, not over everything offered: the number in front
        of the user just before they commit has to be the number of things about to happen.
        """
        ticked = [fix for position, fix in enumerate(self.fixes) if position in self.selected]
        objects = {(fix.where.kind, fix.where.key) for fix in ticked}
        findings = "finding" if len(ticked) == 1 else "findings"
        owners = "object" if len(objects) == 1 else "objects"
        return f"{len(ticked)} {findings} in {len(objects)} {owners}"

    def ticked_identities(self) -> set:
        """The ticks as what they point at rather than as where they sit.  See Fix.identity."""
        return {fix.identity for position, fix in enumerate(self.fixes) if position in self.selected}

    def restore(self, ticks: set, values: dict) -> None:
        """Re-tick and re-choose a freshly built plan to match what the user had chosen.

        Both carried by identity rather than by position, for the reason Fix.identity
        gives: a repair applied, or an edit made in another dialog, shifts every position
        after it, and position-restored ticks would then select different repairs from the
        ones the user chose.

        The decisions go back first and the ticks second, and the ticks are filtered by what
        is ready afterwards: a repair that was ticked because a label had been chosen for it
        must not come back ticked if that label has gone from the Task in the meantime.
        """
        self.chosen = {
            position: values[fix.identity] for position, fix in enumerate(self.fixes) if fix.identity in values
        }
        self.selected = {
            position for position, fix in enumerate(self.fixes) if fix.identity in ticks and self.is_ready(position)
        }


# ##################################################################################
# Reading the tree.
#
# Everything below reads live elements and never a copy: a repair's whole subject is the
# element it is about to write to, and a copy is somewhere else.
# ##################################################################################


def _table(name: str) -> dict:
    """One object table -- all_tasks, all_tasks_by_name -- or {}."""
    return (PrimeItems.tasker_root_elements or {}).get(name) or {}


def _task_element(task_id: str) -> defusedxml.ElementTree.Element | None:
    """One Task's live element, or None when the id is not in the tables."""
    entry = _table("all_tasks").get(task_id)
    return entry["xml"] if entry else None


def _action_at(task_element: defusedxml.ElementTree.Element, number: int) -> defusedxml.ElementTree.Element | None:
    """The action a report calls number `number`, or None when the Task has no such action.

    `number` counts from 1 in RUN order, which is the only number the user has ever seen --
    see mapjump.actions_in_map_order on why that is not the action's position in the file.
    """
    actions = actions_in_map_order(task_element)
    return actions[number - 1] if 1 <= number <= len(actions) else None


def _action_name(code: str) -> str:
    """What an action is called, for a preview line.  Its code, when nothing names it."""
    entry = action_codes.get(f"{code}t")
    return entry.name if entry is not None else f"code {code}"


def _code(action: defusedxml.ElementTree.Element) -> str:
    """An action's <code>, or "" -- the one field every action has."""
    return (action.findtext("code") or "").strip()


def _argument_element(
    action: defusedxml.ElementTree.Element,
    arg_id: str,
) -> defusedxml.ElementTree.Element | None:
    """One of an action's argument children, matched on 'sr' rather than on child order.

    The way every reader in this codebase reaches an argument -- Tasker does not guarantee
    the order.
    """
    wanted = f"arg{arg_id}"
    return next((child for child in action if child.attrib.get("sr") == wanted), None)


def _next_sr(task_element: defusedxml.ElementTree.Element) -> str:
    """The sr= an action appended to this Task must carry to run last.

    One past the highest in use, rather than the action count: Tasker orders actions by the
    numeric suffix of this attribute and a Task whose numbering has a gap in it (which
    nothing forbids) would otherwise be handed an sr that is already taken, putting the new
    action somewhere in the middle of the Task.

    Computed at the moment of writing rather than when the repair was planned, so that two
    closers appended to one Task get two different numbers.
    """
    highest = -1
    for action in task_element.findall("Action"):
        suffix = str(action.attrib.get("sr", ""))[3:]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"act{highest + 1}"


def _labels_of(task_element: defusedxml.ElementTree.Element, except_number: int = 0) -> list[tuple[str, str]]:
    """Every label this Task carries, as (label, 'action 4 -- "check the total"').

    A Tasker label doubles as an action's comment, so most of these are prose that nothing
    jumps to -- and all of them are offered, because a Goto naming a label that is not there
    was meant to name one of these and there is no way to tell which from here.

    `except_number` leaves out one action's own label: a Goto pointed at itself is an
    infinite loop, and offering it as the repair for a broken jump would be handing the
    user a worse Task than the one they started with.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, action in enumerate(actions_in_map_order(task_element), start=1):
        label = (action.findtext("label") or "").strip()
        if not label or number == except_number or label in seen:
            continue
        seen.add(label)
        flattened = " ".join(label.split())
        shown = flattened if len(flattened) <= 40 else f"{flattened[:37]}..."
        found.append((label, f"action {number} -- '{shown}'"))
    return found


# ##################################################################################
# The six repairs.
#
# One planner each, all of the same shape: it is handed the finding's Target, it goes and
# looks at what the finding is about, and it returns either a Fix or a Skip saying why not.
# Nothing here writes anything -- the writing is the closure the Fix carries, which apply()
# is the only caller of.
# ##################################################################################


def _plan_collision(where: Target) -> Fix | Skip:
    """Set a long-running Task's Collision Handling.

    The finding names two acceptable answers and this offers both, defaulting to the one it
    names first: 'Abort Existing Task' honours the trigger that has just arrived, which is
    the case the finding is about -- a Profile firing while the last run is still going.
    'Run Both Together' is the other answer and is a real choice, not a variant: a Task that
    writes to the same variables from two runs at once is its own kind of wrong.
    """
    task = _task_element(where.key)
    if task is None:
        return Skip(MISSING_COLLISION, where, "This Task is no longer in the configuration.")
    if task.find("rty") is not None:
        # Something set it between the scan and now -- another dialog, or an Undo.
        return Skip(MISSING_COLLISION, where, "This Task already has Collision Handling set.")

    choice = Choice(
        CHOICE_OPTIONS,
        "Collision Handling",
        value=_COLLISION_OPTIONS[0][0],
        options=_COLLISION_OPTIONS,
    )

    def run(value: str) -> None:
        objprops.set_child_text_in_tag_order(task, "rty", value)

    return Fix(
        tag=MISSING_COLLISION,
        where=where,
        before=f"Tasker's default -- {objprops.COLLISION_CHOICES[0]}",
        describe=lambda value: f"Set Collision Handling to '{choice.label_of(value)}'",
        choice=choice,
        elements=(task,),
        run=run,
    )


def _plan_timeout(where: Target, timeouts: dict[str, str]) -> Fix | Skip:
    """Write a timeout into an action that has none.

    The argument is the one proflint read to raise the finding, taken from the same table
    rather than worked out again here -- see proflint.timeout_arguments.  An action that
    has never carried the argument at all gets it synthesized the way Add Action and the
    Replace tab synthesize one, so that what is written is indistinguishable from what
    Tasker itself would have written.
    """
    task = _task_element(where.key)
    if task is None:
        return Skip(NO_TIMEOUT, where, "This Task is no longer in the configuration.")
    action = _action_at(task, where.action)
    if action is None:
        return Skip(NO_TIMEOUT, where, "This action is no longer in the Task -- it has been edited since the scan.")

    code = _code(action)
    arg_id = timeouts.get(code)
    if arg_id is None:
        return Skip(NO_TIMEOUT, where, "This action no longer takes a timeout -- it has been changed since the scan.")

    name = _action_name(code)
    choice = Choice(CHOICE_NUMBER, "Timeout", value=DEFAULT_TIMEOUT_SECONDS, units="seconds")

    def run(value: str) -> None:
        seconds = whole_seconds(value)
        if not seconds:
            unusable = f"a timeout of '{value}' is not a whole number of seconds above zero"
            raise ValueError(unusable)
        element = _argument_element(action, arg_id)
        if element is None:
            element = _create_timeout_argument(action, code, arg_id)
        if element.tag == "Int":
            element.set("val", seconds)
            # An <Int> holding a variable keeps the <var> child alongside the attribute, and
            # Tasker reads the child in preference -- so a number written beside one would
            # be ignored.  proflint never reports one (a variable is not "" or "0"), and
            # this is the belt to that braces.
            variable = element.find("var")
            if variable is not None:
                element.remove(variable)
        else:
            element.text = seconds

    return Fix(
        tag=NO_TIMEOUT,
        where=where,
        before=f"'{name}' has no timeout",
        describe=lambda value: f"Give '{name}' a timeout of {whole_seconds(value) or '?'} seconds",
        note=(
            "A timeout makes this action give up and carry on.  Make it longer than the "
            "action could reasonably take, or the Task will start failing on a slow day."
        ),
        choice=choice,
        elements=(task, action),
        run=run,
    )


def _create_timeout_argument(
    action: defusedxml.ElementTree.Element,
    code: str,
    arg_id: str,
) -> defusedxml.ElementTree.Element:
    """Write the timeout argument into an action that has never carried one.

    Built through taskedit.build_synthesized_args -- the same function Add Action uses and
    the same one the Replace tab adds a missing argument with -- so the element is the shape
    Tasker writes rather than this module's idea of it.  No action key is passed, which is
    deliberate: given one that function also writes the plugin payload <Bundle>, and this is
    adding one argument to an action that already has whatever payload it came with.
    """
    action_key = f"{code}t"
    entry = action_codes.get(action_key)
    argument = next((arg for arg in (entry.args or ()) if arg.arg_id == arg_id), None) if entry else None
    if argument is None:
        unbuildable = f"{_action_name(code)} has no timeout argument to add"
        raise ValueError(unbuildable)

    built = taskedit.build_synthesized_args(type(action), action, [argument])
    if not built or built[0].element is None:
        unbuildable = f"a timeout cannot be written into '{_action_name(code)}' from nothing"
        raise ValueError(unbuildable)
    # In the order Tasker writes them, rather than appended at the end -- a new <Int
    # sr="arg1"> sitting after <Str sr="arg8"> is a screenful of moved lines in any diff of
    # the backup for one line of real change.
    mapswap.order_action_children(action)
    return built[0].element


def _plan_closer(tag: str, where: Target) -> Fix | Skip:
    """Close a block that is never closed, with an 'End If' or an 'End For' at the Task's end.

    THE END OF THE TASK IS THE ONLY PLACE THIS CAN GO, and that is worth being plain about.
    An unclosed 'If' is not inert: Tasker runs everything below it only when the condition
    held, right through to the last action -- so the block already ends where the Task ends,
    and writing the closer there changes what is WRITTEN without changing what RUNS.  That
    is the whole of what makes this repair safe to offer.

    If the block was meant to close earlier -- which is the likelier mistake -- then the
    actions below it are running conditionally today and will still be running
    conditionally afterwards.  The note says so, because this repair does not fix that and
    must not be mistaken for having fixed it: moving the closer up is an edit only the
    person who wrote the Task can make.
    """
    closer_code, closer_name, block = _CLOSER_OF_TAG[tag]
    task = _task_element(where.key)
    if task is None:
        return Skip(tag, where, "This Task is no longer in the configuration.")
    opener = _action_at(task, where.action)
    if opener is None:
        return Skip(tag, where, "This action is no longer in the Task -- it has been edited since the scan.")

    def run(_value: str) -> None:
        element_cls = type(task)
        action = element_cls("Action", {"sr": _next_sr(task), "ve": "7"})
        code = element_cls("code")
        code.text = closer_code
        action.append(code)
        task.append(action)

    return Fix(
        tag=tag,
        where=where,
        before=f"'{block}' at action {where.action} is never closed",
        describe=lambda _value: f"Add an '{closer_name}' as the Task's last action",
        note=(
            f"This closes the block where it already ends -- at the end of the Task -- so what runs is "
            f"unchanged.  If the '{block}' was meant to close sooner than that, the actions below it are "
            f"running conditionally now and still will be: move the '{closer_name}' up yourself afterwards."
        ),
        # Innermost first.  Every closer is appended to the end of the Task, so two of them
        # on one Task come out in the order they were applied -- and the block that opened
        # LAST has to be the one closed FIRST or the two end up crossed.
        order=where.action,
        elements=(task, opener),
        run=run,
    )


def _plan_goto(where: Target) -> Fix | Skip:
    """Point a 'Goto' at a label the Task actually carries.

    WHICH label is the user's to say and nothing here guesses at it: the Choice arrives with
    no default, so the repair cannot be applied by somebody who never looked at it.  A
    nearest-match on the spelling is exactly the wrong kind of clever -- a Goto sent to the
    wrong label does not fail, it runs the wrong half of the Task, which is a far quieter
    fault than the one being repaired.

    A Task carrying no labels at all is skipped rather than offered: there is nothing to
    point at, and the repair is to write a label onto the action that was meant to be jumped
    to, which is an edit this cannot make for somebody.
    """
    task = _task_element(where.key)
    if task is None:
        return Skip(GOTO_MISSING_LABEL, where, "This Task is no longer in the configuration.")
    action = _action_at(task, where.action)
    if action is None:
        return Skip(
            GOTO_MISSING_LABEL,
            where,
            "This action is no longer in the Task -- it has been edited since the scan.",
        )

    labels = _labels_of(task, except_number=where.action)
    if not labels:
        return Skip(
            GOTO_MISSING_LABEL,
            where,
            "No other action in this Task carries a label, so there is nothing to point this 'Goto' at.  "
            "Give the action it was meant to jump to a label first, then run this again.",
        )

    current = _argument_element(action, _GOTO_LABEL_ARG)
    wanted = (current.text or "").strip() if current is not None else ""
    choice = Choice(
        CHOICE_OPTIONS,
        "Jump to",
        value="",  # No default: see this function's own note.
        options=tuple((label, shown) for label, shown in labels),
    )

    def run(value: str) -> None:
        if not value:
            unchosen = "no label has been chosen for this 'Goto'"
            raise ValueError(unchosen)
        element = _argument_element(action, _GOTO_LABEL_ARG)
        if element is None:
            element = type(action)("Str", {"sr": f"arg{_GOTO_LABEL_ARG}", "ve": "3"})
            action.append(element)
            mapswap.order_action_children(action)
        element.text = value

    return Fix(
        tag=GOTO_MISSING_LABEL,
        where=where,
        before=f"'Goto' names label '{wanted}', which nothing carries" if wanted else "'Goto' names no label at all",
        describe=lambda value: f"Point this 'Goto' at '{choice.label_of(value)}'" if value else "Choose a label",
        choice=choice,
        elements=(task, action),
        run=run,
    )


def _plan_delete_task(where: Target) -> Fix | Skip:
    """Delete a Task nothing in this file runs.

    The one repair here that takes something away, and the only one that arrives UNTICKED --
    see plan_fixes.  The check's own closing note is the reason: a Task can be started by a
    home screen widget, a Quick Settings tile, a launcher shortcut or another app entirely,
    and none of those live in a Tasker backup, so "nothing in this file runs it" is not the
    same statement as "nothing runs it".

    Deleted through taskedit.delete_task, which unlinks it from every Project's <tids> and
    from any Profile naming it -- the three things that have to happen together or the
    backup is left inconsistent.

    That function resolves by NAME, so a name two Tasks share is refused outright, and BOTH
    of them are refused rather than the one the by-name table does not happen to hold.  Which
    Task the name 'Twin' refers to is exactly the ambiguity DUPLICATE-NAME exists to report,
    and answering it by deleting one of them is the worst possible answer: the user would be
    told a Task called 'Twin' had gone and have no way to know which.  Rename one of them
    first and both are offered on the next run.
    """
    task = _task_element(where.key)
    if task is None:
        return Skip(UNREFERENCED_TASK, where, "This Task is no longer in the configuration.")

    name = (_table("all_tasks").get(where.key) or {}).get("name", "")
    sharing = [key for key, entry in _table("all_tasks").items() if entry.get("name") == name]
    entry = _table("all_tasks_by_name").get(name) if name else None
    if not name or entry is None or len(sharing) > 1:
        return Skip(
            UNREFERENCED_TASK,
            where,
            "Another Task in this file has the same name, so deleting by name could take the wrong one.  "
            "Rename one of them first -- the check reports the pair as DUPLICATE-NAME.",
        )

    actions = len(task.findall("Action"))

    def run(_value: str) -> None:
        current = _table("all_tasks_by_name").get(name)
        if current is None or current.get("id") != where.key:
            moved = f"'{name}' no longer names this Task -- nothing was deleted"
            raise ValueError(moved)
        errors = taskedit.delete_task(name)
        if errors:
            raise ValueError(errors[0])

    return Fix(
        tag=UNREFERENCED_TASK,
        where=where,
        before=f"{actions} action{'' if actions == 1 else 's'}, run by nothing in this file",
        describe=lambda _value: f"Delete Task '{name}'",
        note=(
            "Nothing in the backup runs it -- but a home screen widget, a Quick Settings tile, a "
            "launcher shortcut or another app can, and none of those are in the file.  Make sure this "
            "is not one of those before you tick it."
        ),
        elements=(task,),
        run=run,
    )


# ##################################################################################
# Building the plan.
# ##################################################################################


def _planner_for(tag: str, timeouts: dict[str, str]) -> Callable[[Target], Fix | Skip] | None:
    """The function that plans a repair for this tag, or None when there is no repair for it."""
    if tag == MISSING_COLLISION:
        return _plan_collision
    if tag == NO_TIMEOUT:
        return lambda where: _plan_timeout(where, timeouts)
    if tag in _CLOSER_OF_TAG:
        return lambda where: _plan_closer(tag, where)
    if tag == GOTO_MISSING_LABEL:
        return _plan_goto
    if tag == UNREFERENCED_TASK:
        return _plan_delete_task
    return None


def plan_fixes(skip: Collection[str] = ()) -> Plan:
    """Run the health check for the repairable categories and offer a repair for each finding.

    `skip` is the health check's own -- the categories the chooser panel has unticked, saved
    in the settings file.  Honoured here rather than ignored, so that a user who has said
    they do not care about unreferenced Tasks is not offered a list of Tasks to delete: the
    two panels answer the same question and must not disagree about what is being looked for.

    Everything this cannot repair is left out of the scan entirely rather than scanned and
    filtered -- the secrets and variables passes are each a separate walk over the whole
    configuration, and there is no repair here for anything either of them raises, so a plan
    does a fraction of the work a full check does.

    Findings arrive sorted by tag and location, which is the order the report prints them
    in, so somebody working down the report finds the repairs in the same order.

    Every repair starts TICKED except two.  A delete starts unticked because it takes a Task
    away on the strength of an absence of evidence -- see _plan_delete_task.  A repair whose
    Choice has no default starts unticked because it has not been decided, and a tick on an
    undecided repair is a tick that cannot be honoured: apply() would refuse it, so offering
    it ticked would be promising something and then reporting it as an error.
    """
    leave_out = set(skip) | {category.tag for category in healthck.all_categories() if category.tag not in FIXABLE_TAGS}
    index = healthck.collect_findings(leave_out)

    timeouts = proflint.timeout_arguments()
    plan = Plan(what="Fix Health Check findings")
    order = {tag: position for position, tag in enumerate(FIXABLE_TAGS)}

    findings = sorted(index.findings, key=lambda item: (order.get(item.tag, len(order)), item.where))
    if len(findings) > _PLAN_LIMIT:
        # "Looked at", not "offered": some of these will turn out to be skips, and a count
        # promising 500 repairs in front of a list holding 480 is a worse answer than none.
        plan.warnings.append(
            f"{len(findings)} findings are of a kind this can repair, and the first {_PLAN_LIMIT} are "
            f"looked at here.  Apply these, then scan again for the rest.",
        )
        findings = findings[:_PLAN_LIMIT]

    for finding in findings:
        planner = _planner_for(finding.tag, timeouts)
        # A finding with no target names a NAME rather than an object (see healthck's
        # Finding.target), and none of the repairable tags do -- but a planner cannot work
        # without one, so this is checked rather than assumed.
        if planner is None or finding.target is None or finding.target.kind != TASK:
            continue
        planned = planner(finding.target)
        if isinstance(planned, Skip):
            plan.skips.append(planned)
            continue
        position = len(plan.fixes)
        plan.fixes.append(planned)
        if planned.tag != UNREFERENCED_TASK and plan.is_ready(position):
            plan.selected.add(position)

    return plan


# ##################################################################################
# The preview.
# ##################################################################################
_REPORT_WIDTH = 88


def _wrapped(text: str, indent: str) -> list[str]:
    """A paragraph broken to the report's width, on spaces, each line indented.

    The notes here are prose -- a sentence or three of it -- and the same text is written to
    a text file, where nothing is going to wrap it at all.  maprefac's, with the indent
    folded in because every caller here was adding one.
    """
    lines, current = [], ""
    for word in text.split():
        if current and len(indent) + len(current) + 1 + len(word) > _REPORT_WIDTH:
            lines.append(f"{indent}{current}")
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(f"{indent}{current}")
    return lines or [indent.rstrip()]


def report_rows(plan: Plan) -> list[Row]:
    """The plan as mapjump Rows: what cannot be repaired first, then the repairs by tag.

    Skips first, for mapswap's reason: they are the part the user must read and the part
    they will not scroll back up for.

    Grouped under the tag, which is the word the report they have just read prints in
    brackets in front of every finding -- so "the six NO-TIMEOUT ones" is a group here as
    well as there.

    Rows rather than a string so the preview is clickable in the Map the same way the health
    check's own findings are.  That matters more here than in any other preview in this
    program: the only way to judge "should this Task really be deleted" is to go and look at
    it, and the row is the way there.
    """
    rows: list[Row] = [Row(plan.what), Row("")]

    for warning in plan.warnings:
        rows.extend(Row(line) for line in _wrapped(warning, "  "))
    if plan.warnings:
        rows.append(Row(""))

    if plan.skips:
        rows.append(Row(f"CANNOT BE REPAIRED HERE ({len(plan.skips)})"))
        for item in plan.skips:
            rows.append(Row(f"  [{item.tag}]  {item.where.label}", item.where))
            rows.extend(Row(line) for line in _wrapped(item.explanation, "      "))
        rows.append(Row(""))

    if not plan.fixes:
        rows.append(Row("Nothing to repair."))
        return rows

    rows.extend((Row(f"WOULD REPAIR ({len(plan.selected)} of {len(plan.fixes)} ticked)"), Row("")))

    current_tag = ""
    for position, fix in enumerate(plan.fixes):
        if fix.tag != current_tag:
            current_tag = fix.tag
            rows.extend((Row(f"  [{fix.tag}]  {WHAT_IT_DOES.get(fix.tag, '')}"), Row("")))
        tick = "[x]" if position in plan.selected else "[ ]"
        rows.append(Row(f"    {tick} {fix.where.label}", fix.where))
        rows.append(Row(f"        now:  {fix.before}"))
        rows.append(Row(f"        fix:  {plan.describe(position)}"))
        if fix.note:
            rows.extend(Row(line) for line in _wrapped(fix.note, "        "))
        rows.append(Row(""))

    return rows


def write_fix_report(rows: list[Row]) -> str:
    """Save the preview as text, the way healthck, mapswap and maprefac save theirs.

    Worth having for the repairs the user decided NOT to make as much as the ones they did:
    a skip names what has to be done by hand before the repair can be offered again, and
    that is a work list which does not survive closing the dialog otherwise.
    """
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(FIX_FILE, stamp)
    if not file_name:
        return ""
    try:
        with open(os.path.join(os.getcwd(), file_name), "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Fix preview could not be written: {error}")
        return ""
    return file_name


# ##################################################################################
# Doing it.
# ##################################################################################
def apply(plan: Plan) -> tuple[int, list[str]]:
    """Make the ticked repairs.  Returns (how many were made, anything that went wrong).

    ONE undo block around the whole thing, and the outermost one.  Repairing thirty findings
    is one thing the user did and costs one press of Undo, which is what sessundo's
    re-entrancy is for -- the same reason deleting a Project does not cost ten.

    Each repair is independent, so a failure reports itself and the loop carries on.  That
    is the opposite of maprefac, and the difference is the point: there is no "rest" of a
    refactor, and there is nothing BUT the rest here.

    Three things are re-checked before a repair is made, each a different question:

      IS IT DECIDED.  A repair whose Choice has no default and has not been made is refused
      rather than applied with an empty value -- the dialog leaves those unticked, and this
      refuses them again rather than trusting it to have.

      IS IT STILL THE SAME FILE.  Every element the repair depends on is checked against the
      loaded configuration.  A preview can sit on screen while the user deletes the Task it
      describes in another dialog, and writing to a detached element would rewrite a tree
      nothing renders from -- silently doing nothing, or worse, resurrecting a deleted Task.

      DID IT WORK.  A raise from inside a repair is caught and reported against the object
      it was about, rather than escaping into the GUI as a traceback.

    Order matters twice, and both are handled here rather than left to the caller, so that a
    plan assembled in any order still applies in a safe one:

      BLOCK CLOSERS INNERMOST FIRST.  Each is appended to the end of its Task, so two on one
      Task come out in the order they were applied -- and the block opened LAST has to be
      closed FIRST or the two end up crossed.

      DELETES LAST.  A delete takes its Task out of the tables, and anything else ticked that
      lives inside that Task would then have nothing to write to.  Doing it last means a
      user who ticked both gets both, rather than one of them and an error.
    """
    ticked = [(position, plan.fixes[position]) for position in sorted(plan.selected)]
    if not ticked:
        return 0, []

    ticked.sort(key=lambda item: (item[1].tag == UNREFERENCED_TASK, -item[1].order))

    errors: list[str] = []
    repaired = 0
    attached = maputil2.attached_elements()

    with sessundo.undoable(plan.what):
        for position, fix in ticked:
            if not plan.is_ready(position):
                errors.append(f"{fix.where.label}: nothing has been chosen for this one yet.  Skipped.")
                continue
            if any(id(element) not in attached for element in fix.elements):
                errors.append(
                    f"{fix.where.label}: no longer in the configuration -- it was deleted or reloaded "
                    f"while this preview was open.  Skipped.",
                )
                continue
            try:
                fix.run(plan.value_of(position))
            except (AttributeError, KeyError, TypeError, ValueError) as failure:
                logger.error(f"Fix for {fix.tag} at {fix.where.label} failed: {failure}")
                errors.append(f"{fix.where.label}: {failure}")
                continue
            repaired += 1
            # A delete takes its Task's elements out of the tables, and anything else ticked
            # that lives inside that Task must not then be written to.  Cheaper and safer
            # than re-walking the whole tree per repair: only a delete can invalidate one.
            if fix.tag == UNREFERENCED_TASK:
                attached = maputil2.attached_elements()

    return repaired, errors
