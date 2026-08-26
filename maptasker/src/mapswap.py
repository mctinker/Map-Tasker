"""mapswap: bulk replace over the loaded configuration -- one action, argument, context or variable for another."""

#! /usr/bin/env python3

#                                                                                        #
# mapswap: bulk replace over the loaded configuration, rather than over rendered text.   #
#                                                                                        #
# Four operations, one machinery.  Swap every Task action of one code for another; set  #
# or edit one argument of every action of a code; swap every Profile context of one kind #
# for another; rename every use of a variable, or fold it into another variable.  They   #
# share the dialog, the preview, the report and the apply path, and nothing below that.  #
# Three of them are STRUCTURAL (a different element, holding a different set of children #
# that mean different things) and one -- the variable rename -- is TEXTUAL (one string   #
# rewritten in place, every field keeping its meaning).                                  #
#                                                                                        #
# Same contract as healthck / varxref / mapfind -- reads PrimeItems.tasker_root_elements #
# and nothing else, no GUI import, identity from mapjump.  What differs is that this one #
# WRITES, and four rules follow from that:                                               #
#                                                                                        #
#   NOTHING IS APPLIED UNSEEN.  A report that is 90% right is useful; a replace that is  #
#   90% right is a corrupted configuration the user cannot spot by looking.  plan() and  #
#   apply() are separate, apply() only ever takes a plan(), and every planned change is  #
#   a clickable mapjump Row before it is a change.                                       #
#                                                                                        #
#   ONE SCANNER.  Finding the places and rewriting them must be one pass, or the two     #
#   drift and the preview says 14 places while 12 get changed -- silently.  So there is  #
#   no scanner here: mapfind and varxref are asked where things are, and each carries    #
#   the element handle its own reports never needed.                                     #
#                                                                                        #
#   ONE UNDO.  A hundred-site rename is one thing the user did, so the whole of apply()  #
#   runs inside a single re-entrant sessundo.undoable block.                             #
#                                                                                        #
#   ONLY WHAT IS ON SCREEN.  With a single Project/Profile/Task/Scene selected, both     #
#   operations reach that object and no further (mapjump.current_scope), and say so --   #
#   in the plan, in the saved report, and in the Undo label.                             #
#                                                                                        #
# What cannot be reached is reported rather than dropped: a variable a plugin produces   #
# without naming it, a target built at run time ('Variable Set %(%which)'), a plugin     #
# payload bundle.py has no definition for.  A silent skip is the worst thing this module #
# could do -- the user reads "23 changed", believes the job done, and the two it could   #
# not touch are the two that now disagree with the other twenty-one.                     #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import copy
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from maptasker.src import mapfind, profedit, sessundo, taskedit, varxref
from maptasker.src.actionc import ArgumentCode, action_codes
from maptasker.src.globalvr import tasker_global_variables
from maptasker.src.mapjump import PROFILE, TASK, VARIABLE, Row, Target, current_scope, text_report
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import SWAP_FILE, logger
from maptasker.src.varxref import _LOW_CONFIDENCE_LENGTH, VARIABLE_PATTERN

if TYPE_CHECKING:
    import defusedxml.ElementTree


# ##################################################################################
# What a place to be changed looks like.
# ##################################################################################

# The kinds of field a value can sit in.  Not decoration: the rewrite is different for
# each (a <Str> holds its value as .text, an <Int> holds it in a <var> child, a Version 2
# Scene holds it inside a JSON blob that has to be parsed, edited and re-serialized), and
# the preview needs to say which so a user can tell "the Task's argument" from "the
# Scene's binding" when the same name appears in both.
STR_ARG = "Str"  # <Str sr="argN">text</Str>
INT_VAR = "Int"  # <Int sr="argN"><var>%Name</var></Int>
CONDITION = "condition"  # <Condition><lhs>/<rhs>
BUNDLE = "bundle"  # anything under a plugin's <Bundle>
LEGACY_SCENE = "legacy"  # a Legacy Scene element's argument
V2_SCENE = "v2"  # a property inside a Version 2 Scene's JSON layout
DECLARATION = "declaration"  # a top-level <Variable>, i.e. Tasker's Variables tab
IMPORT_VARIABLE = "import"  # <ProfileVariable><pvn>: a Project's or Profile's configure-on-import variable
INT_VALUE = "IntVal"  # <Int sr="argN" val="7"/> -- the value is the attribute, not the text
NEW_ARG = "new"  # an argument the action does not carry yet, to be written into it
ACTION_ELEMENT = "action"  # the whole <Action>, for an action swap
PROFILE_CONDITION = "profcond"  # the whole <Time>/<Day>/<State>/<Event>/<App>/<Loc> of a Profile


@dataclass(frozen=True)
class Site:
    """One field that holds a value, in a form that can be read and written again.

    Frozen and holding the element rather than a path to it: the element IS the identity
    here, the tree is not re-parsed between plan() and apply(), and a path expressed as
    "the third <Str> of action 4 of Task 118" would have to be re-resolved against a tree
    that an earlier change in the same plan may already have renumbered.

    THIS IS ONLY VALID UNTIL THE TREE IS RELOADED.  A Plan is a short-lived thing --
    built when the user presses Find, spent when they press Replace, discarded if they
    load another file in between.  apply() re-checks that every element is still attached
    before writing to it, for the case where the user did something else in another
    dialog while the preview was on screen.
    """

    kind: str  # one of the constants above
    element: defusedxml.ElementTree.Element
    where: Target  # what the preview prints and what a click on it jumps to
    detail: str = ""  # "Flash, Text=" -- varxref._argument_label's wording, reused
    path: tuple = ()  # V2_SCENE only: the key path into the parsed layout
    # ACTION_ELEMENT and PROFILE_CONDITION only: what this action, or this Profile context,
    # is becoming -- an actionc.py key for the one, a condition_key for the other.  Carried
    # on the Site rather than read off the Plan at apply time so that _apply_one needs
    # nothing but the Change -- which is what lets apply() sort the list before running it.
    new_key: str = ""
    carry: dict[str, str] = field(default_factory=dict)
    # Variable rename only: (pattern, new name).  On the Site for the same reason as
    # new_key above -- so that performing one change needs nothing but the Change itself,
    # and a V2 property whose value is a nested structure can be rewritten in place rather
    # than reconstructed from the flat string the preview shows.
    rename: tuple = ()
    # Argument replace only: what this field is to hold, whole.  None means "not that kind
    # of change", which is what distinguishes it from a deliberate empty value -- clearing
    # an argument is a thing somebody may well want, and "" has to be able to mean it.
    new_value: str | None = None
    # NEW_ARG only: (action key, argument id) for the argument to be written into this
    # action.  `element` is then the <Action> itself, since the argument's own element does
    # not exist yet -- planning must not touch the tree, so it is built at apply time from
    # these two facts.
    create_arg: tuple = ()


@dataclass(frozen=True)
class Change:
    """One site, and what it would hold afterwards.

    before/after are the whole field value, not the matched fragment, because that is
    what the preview should show: 'Flash %Total items in %Dir' -> 'Flash %Count items in
    %Dir' tells the user something that '%Total -> %Count' does not, namely that the
    second %Dir was correctly left alone.
    """

    site: Site
    before: str
    after: str
    note: str = ""  # anything the user should read before ticking this one

    @property
    def identity(self) -> tuple:
        """What this change points at, in a form that survives the plan being rebuilt.

        A preview is thrown away whenever the dialog closes -- a Site holds a live element,
        and holding one across a reopen is the stale-handle case apply()'s attachment check
        exists to catch -- so a user's tick boxes can only be carried over by describing
        what they were ticking, never by remembering their POSITION in the list.  Position
        is exactly what goes wrong: an edit made in another dialog between the two previews
        shifts every index after it, and index-restored ticks would then silently select
        different changes from the ones the user chose.

        The anchor alone is too coarse -- two arguments of one action share it -- so the
        field within the object and the value being replaced are part of it too.  Two
        changes CAN still collide (the same argument label holding the same text twice),
        and that is why the ticks are carried as a Counter rather than a set: changes that
        are indistinguishable here are also indistinguishable on screen, so restoring "two
        of these were ticked" is the whole of what the user chose.
        """
        return (self.site.where.anchor, self.site.kind, self.site.detail, self.site.path, self.before)


# Why a site that matched is not being offered as a change.
BLOCKED_UNADDABLE = "unaddable"  # taskedit cannot synthesize the target action
BLOCKED_INDIRECT = "indirect"  # the name is computed at run time: '%(%which)'
BLOCKED_DETACHED = "detached"  # element no longer in the tree (checked at apply time)
BLOCKED_DUPLICATE = "duplicate"  # the Profile already holds a context of the target's kind


@dataclass
class Skip:
    """A place that matched and cannot be changed, with the reason in the user's terms.

    Carried in the Plan rather than dropped, and printed in the preview above the
    changes.  A silent skip is the worst outcome this feature can produce: the user reads
    "23 places changed", believes the job is done, and the two the tool could not touch
    are the two that now disagree with the other twenty-one.
    """

    where: Target
    reason: str
    explanation: str


@dataclass
class Plan:
    """Everything one Replace would do, before any of it is done.

    Ordinary dataclass, not frozen: the dialog ticks and unticks individual changes, and
    `selected` is what it ticks.  Everything else is built once and read-only by
    convention.
    """

    what: str  # one line of prose for the header and the report: "Replace Flash with Notify"
    changes: list[Change] = field(default_factory=list)
    skips: list[Skip] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # things true of the plan as a whole
    # Indices into `changes` that are ticked.  Everything except the RESET-fidelity action
    # swaps starts ticked -- see plan_action_swap on why those alone are opt-in.
    selected: set[int] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        """Nothing to offer.  Distinct from 'nothing found' only in that skips may exist."""
        return not self.changes

    def ticked_identities(self) -> Counter:
        """The ticks, as what they point at rather than as where they sit.  See Change.identity."""
        return Counter(change.identity for position, change in enumerate(self.changes) if position in self.selected)

    def restore_ticks(self, remembered: Counter) -> None:
        """Re-tick a freshly built plan to match what the user had chosen before.

        Overrides the defaults outright rather than merging with them -- including the
        unticked-by-default RESET rows, which the user may well have gone through and
        ticked one at a time, and which it would be rude to un-tick again on the way back
        from looking at one of them.
        """
        budget = Counter(remembered)
        self.selected = set()
        for position, change in enumerate(self.changes):
            identity = change.identity
            if budget[identity] > 0:
                budget[identity] -= 1
                self.selected.add(position)

    def tally(self) -> str:
        """'14 places in 6 Tasks' -- the line the button's confirmation asks about.

        Counted over the TICKED changes, not over everything found: the number in front of
        the user just before they commit has to be the number of things about to happen.
        """
        ticked = [change for position, change in enumerate(self.changes) if position in self.selected]
        objects = {(change.site.where.kind, change.site.where.key) for change in ticked}
        places = "place" if len(ticked) == 1 else "places"
        owners = "object" if len(objects) == 1 else "objects"
        return f"{len(ticked)} {places} in {len(objects)} {owners}"


# ##################################################################################
# Action for action.
#
# The whole difficulty is the arguments.  Two action codes are two different sets of
# arguments with different names, types and meanings, and there is no general mapping
# between them -- so the question this section answers is not "how do I copy the
# arguments across" but "how much of this action survives, and how do I say so plainly
# enough that the user can decide before rather than after".
#
# All four fidelity levels are offered, which is a decision with teeth: the target
# pulldown is NOT filtered down to the pairs that carry cleanly, so 'replace Flash with
# anything' is a question the user is allowed to ask.  What makes that safe is that the
# fidelity of the pair is computed and shown BEFORE the target is chosen -- see
# fidelity_choices -- rather than discovered in the preview afterwards.
# ##################################################################################

# What is preserved whatever the codes are, because none of it belongs to the code: the
# action's position in the Task, its <label>, its <on>false</on> disabled state, its
# <se>false</se> continue-after-error flag, and its attached <Condition> ("If %x is set"
# hanging off the action itself).  All five are the user's intent about WHERE and WHEN
# the action runs, which a swap does not change.  The label is preserved and FLAGGED --
# a label reading 'flash the total' on a Notify is stale, and the tool cannot rewrite
# prose, so it says so instead.
_PRESERVED_CHILDREN = ("label", "on", "se", "ConditionList", "Condition")

# How much of the old action survives, worst last.  Shown per candidate target in the
# pulldown and again per Task in the preview, because 'replace Flash with Notify' means
# something very different at each level and the user is the only one who knows which
# they wanted.
EXACT = "exact"  # every argument carried: same names, same types
MAPPED = "mapped"  # some carried, the rest left at the value Tasker itself writes for unset
RESET = "reset"  # nothing carried; a fresh action, every argument unset
BLOCKED = "blocked"  # cannot be built at all -- see _swap_blocked


# ##################################################################################
# Why this does NOT delegate to taskedit.classify_action_addability.
#
# That function answers "can Add Action build this from nothing", and its Icon/App/Scene
# refusals are right for that question: the Add dialog offers no picker widget, so an
# argument it cannot generate is one the user could never fill in afterwards either.
#
# A swap is not building from nothing, and measuring the sample XML says the premise
# does not survive the move.  An Icon argument is <Img sr="argN"> and an App argument is
# <App sr="argN">, and across the XML/ sample files:
#
#     <Img>  783 filled     675 EMPTY
#     <App>  639 filled     287 EMPTY
#
# The empty element is not a degenerate case to be avoided -- it is what Tasker itself
# writes for a picker the user has not set, nearly a thousand times in the sample data.
# So there is a generic default after all, at the XML level, and the argument that made
# these actions unaddable does not make them unswappable.
#
# Deferring to classify_action_addability would have blocked 34 of the 550 action codes,
# including Notify, Launch App, Kill App, Browse URL, Media Control and the whole Notify
# LED/Sound/Vibrate family -- which between them are a large share of the actions anybody
# would actually want to bulk-replace.  Judged on the swap's own terms it blocks 24: the
# 17 plugin actions whose payload bundle.py has not recorded, and the 7 structural ones
# below.  The two sets barely overlap, which is the point: nearly every action the old
# test refused is refused for a reason that only applies to building from nothing.
#
# Two things follow, and they are the reason this is worth the paragraphs:
#
#   A picker argument the source can supply should be MOVED, not defaulted.  See
#   _PICKER_CATEGORIES.
#
#   A picker argument nothing supplies is written as the empty element rather than
#   omitted.  Omitting it is the one option not on the table: every real Notify in the
#   sample data carries its <Img sr="arg2">, all 90 of them, and an action missing an
#   argument Tasker expects is the shape that reaches the device and misbehaves there.
# ##################################################################################

# Categories whose value is a SUBTREE rather than text -- <App><appPkg>..</appPkg></App>,
# <Img><nme>..</nme></Img>.  Carried by deep-copying the element across, which is also why
# they cannot go through the name-and-type rule below: it compares text.
_PICKER_CATEGORIES = ("App", "Icon", "Scene")

# Actions whose meaning is structural rather than argumentative, blocked as source and as
# target both.  Swapping an If leaves its End If dangling and every action between them in
# a block that no longer opens -- taskedit.add_if_block_to_task exists precisely because
# these come in matched sets, and a bulk operation is the wrong place to start reasoning
# about nesting.  Perform Task is here for a different reason: its argument is another
# Task's NAME, so replacing it silently unhooks a call that nothing else records.
_STRUCTURAL = (
    "37t",  # If
    "38t",  # End If
    "43t",  # Else
    "39t",  # For
    "40t",  # End For
    "135t",  # Goto -- addresses an action by NUMBER, and a swap does not renumber
    "130t",  # Perform Task
)


# The XML tag each picker category is written as.  Not derivable from arg_specs.json,
# which names the category and not the element: an Icon argument is <Img>, and nothing in
# the spec table says so.  Scene has no entry because no action in actionc.py declares a
# Scene-category argument and none appears in any sample XML -- listed in
# _PICKER_CATEGORIES anyway, so that a Tasker release introducing one is carried rather
# than silently dropped, and left out here so that writing an empty one is a no-op rather
# than a guess at a tag name.
_PICKER_TAGS = {"App": "App", "Icon": "Img"}


def _effective_args(action_key: str) -> list:
    """The arguments an action really has, following actionc.py's redirect.

    Same two lines add_action_to_task and _build_editable_action each open with.  Here
    rather than imported from taskedit because both of those inline it privately, and a
    third copy in this module would be the one that gets forgotten when the shape changes.
    """
    action_code = action_codes.get(action_key)
    if action_code is None:
        return []
    if action_code.redirect:
        target = action_codes.get(action_code.redirect)
        return list(target.args or ()) if target else []
    return list(action_code.args or ())


def _category(arg: ArgumentCode) -> str:
    """An argument's category name -- 'String', 'Int', 'App', 'Icon', 'Bundle'."""
    return PrimeItems.tasker_arg_specs.get(arg.arg_type, "")


def _is_hint_bundle(arg: ArgumentCode) -> bool:
    """Whether a Bundle argument is the informational 'Output Variables' note rather than
    a plugin payload.  taskedit skips these when synthesizing; nothing has to be produced
    for one, so it must not count towards either the target's argument tally or BLOCKED.
    """
    return _category(arg) == "Bundle" and arg.arg_name == taskedit.OUTPUT_VARIABLES_ARG_NAME


def _wanted_args(action_key: str) -> list:
    """The target's arguments that a swap actually has to produce a value for."""
    return [arg for arg in _effective_args(action_key) if not _is_hint_bundle(arg)]


def carry_over_map(old_key: str, new_key: str) -> dict[str, str]:
    """{old arg id: new arg id} for the arguments that can move across, derived from
    actionc.py rather than listed by hand -- same rule as varxref._write_arguments, so a
    Tasker release that adds an action is covered when actionc.py is regenerated.

    TWO rules, and the second one exists only because the first cannot see a picker.

    1. NAME AND TYPE, for everything that holds text.  Both must agree:

         Flash 'Text' (String) -> Notify 'Text' (String)      carried.  The message
                                                              survives, which is the single
                                                              most useful thing this whole
                                                              feature does.
         Flash 'Title' (String) -> Notify 'Title' (String)    carried.
         'Store Result In' -> 'Store Result In'               carried, and it matters more
                                                              than most: this is the output
                                                              variable, and dropping it
                                                              silently breaks every read of
                                                              it downstream.
         Flash 'Icon' (String) -> Notify 'Icon' (Icon)        NOT carried, and this is the
                                                              case the type half of the rule
                                                              exists for: same word, and
                                                              Flash's is a string naming an
                                                              icon while Notify's is an <Img>
                                                              subtree.  Copying one into the
                                                              other produces an <Img> holding
                                                              text, which is not a thing.
         'Message' -> 'Text'                                  NOT carried.  A synonym table
                                                              is the obvious next idea and is
                                                              deliberately not here: it would
                                                              be hand-written, it would be
                                                              wrong somewhere, and the failure
                                                              is a value silently landing in
                                                              the wrong field, which reads as
                                                              correct in the Map.

       Positional fallback ('arg0 -> arg0') is likewise rejected: nothing except position
       connects the two, and position means nothing across codes.

    2. UNIQUE PICKER, for _PICKER_CATEGORIES only.  When source and target each have
       exactly ONE argument of the same picker category, that subtree moves across
       whatever the two arguments are called:

         Launch App 'Package/App Name' (App) -> Kill App 'App' (App)      carried.

       Different names, so rule 1 refuses it, and refusing it here would mean re-picking an
       app by hand in every Task the swap touched.  What justifies the looser test is
       uniqueness: with one argument of the category on each side there is nothing else it
       could map to, so the ambiguity that makes a general name-blind fallback dangerous is
       absent.  Two on either side and the rule declines rather than guesses.

       Deliberately not extended to text categories.  Flash has ten String arguments; 'the
       only String' is never true there and 'the first String' is exactly the positional
       guess rule 1 rejects.
    """
    old_args = _effective_args(old_key)
    new_args = _wanted_args(new_key)
    carry: dict[str, str] = {}
    claimed: set[str] = set()

    # Rule 1.  First target argument wins a (name, type) pair: actionc.py does carry a few
    # actions with two identically named arguments of the same type, and mapping both old
    # ones onto the same new one would put the second value where the first belongs.
    by_name_and_type: dict[tuple[str, str], str] = {}
    for arg in new_args:
        by_name_and_type.setdefault((arg.arg_name or "", arg.arg_type), arg.arg_id)

    for arg in old_args:
        name = arg.arg_name or ""
        if not name or _category(arg) in _PICKER_CATEGORIES:
            continue  # An unnamed argument has nothing to match on; pickers are rule 2's.
        new_id = by_name_and_type.get((name, arg.arg_type))
        if new_id is not None and new_id not in claimed:
            carry[arg.arg_id] = new_id
            claimed.add(new_id)

    # Rule 2.  Uniqueness is the whole warrant, so it is tested per category and both
    # sides have to be unique -- one App out of one App, never one of two.
    for category in _PICKER_CATEGORIES:
        from_source = [arg for arg in old_args if _category(arg) == category]
        to_target = [arg for arg in new_args if _category(arg) == category]
        if len(from_source) == 1 and len(to_target) == 1 and to_target[0].arg_id not in claimed:
            carry[from_source[0].arg_id] = to_target[0].arg_id
            claimed.add(to_target[0].arg_id)

    return carry


def _swap_blocked(old_key: str, new_key: str) -> str:
    """Why this pair cannot be built at all, or "" if it can.

    Three reasons, and only three:

      Either side is _STRUCTURAL.
      The target carries a plugin <Bundle> that bundle.py has no recorded definition for
        (taskedit.get_bundle_definition returns None).  An opaque payload is opaque: there
        is no empty form of it that a plugin will accept, which is what separates it from a
        picker, and carrying one over from the source is not on the table either -- a
        different code is a different plugin, and its payload would mean nothing here.
      The target's code is not in action_codes at all -- a Tasker release newer than the
        actionc.py in this build.

    Everything else has a buildable form, however little of the old action reaches it.
    """
    for key, label in ((old_key, "source"), (new_key, "target")):
        if key in _STRUCTURAL:
            name = action_codes[key].name if key in action_codes else key
            return (
                f"'{name}' controls the shape of the Task rather than doing something, so it "
                f"cannot be the {label} of a swap."
            )

    if new_key not in action_codes:
        return f"'{new_key}' is not an action this build knows about."

    # An opaque plugin payload has no empty form a plugin will accept, which is what
    # separates it from a picker: bundle.py either has the definition or nothing can be
    # written.  Carrying one across from the source is not attempted -- a different code is
    # a different plugin, and its payload would mean nothing to this one.
    if taskedit.get_bundle_definition(new_key) is None:
        for arg in _wanted_args(new_key):
            if _category(arg) == "Bundle":
                return (
                    f"'{action_codes[new_key].name}' is a plugin action and no definition of its "
                    "configuration has been recorded, so an empty one cannot be built."
                )

    return ""


def classify_swap(old_key: str, new_key: str) -> tuple[str, dict[str, str], str]:
    """(fidelity, carry-over map, reason) for one code pair, without touching the tree.

    EXACT when every argument of the target is carried, RESET when none is, MAPPED in
    between, BLOCKED when _swap_blocked gives a reason.

    Pure and cheap -- no tree access, and the inputs are two strings -- which is what lets
    fidelity_choices call it 550 times to build a pulldown.
    """
    reason = _swap_blocked(old_key, new_key)
    if reason:
        return BLOCKED, {}, reason

    carry = carry_over_map(old_key, new_key)
    wanted = _wanted_args(new_key)
    given = _wanted_args(old_key)

    # EXACT means the user loses nothing, which is a claim about BOTH sides: every
    # argument of the target is filled AND every argument of the source found a home.
    # Testing only the target gets this wrong in the case that matters most -- Flash has
    # sixteen arguments and 67 actions have none, so 'Flash -> Airplane Mode' fills every
    # argument the target has by filling none, and calling that EXACT would promise the
    # user that their message text survived into an action that cannot hold it.
    if len(carry) == len(wanted) == len(given):
        return EXACT, carry, ""
    return (MAPPED if carry else RESET), carry, ""


def fidelity_choices(old_key: str) -> list[tuple[str, str, str]]:
    """(action key, label, fidelity) for every action, as the target pulldown offers them.

    This is where "offer all four levels" is actually delivered.  Nothing is filtered out;
    instead every candidate is labelled with what choosing it would cost, the same way
    mapfind.Choice.label puts the count beside the value so that no entry in a pulldown is
    a surprise:

        Notify                    -- keeps Text, Title  (2 of 16)
        Say                       -- keeps Text  (1 of 8)
        Kill App                  -- keeps nothing  (resets 2)
        Custom Setting            -- cannot: plugin payload not recorded

    Sorted by fidelity first and name second, so the pairs that carry the most sit at the
    top and the RESET wall is somewhere the user has to scroll to on purpose.  A BLOCKED
    entry stays in the list, greyed and unselectable with its reason as the label -- listed
    rather than hidden, because a user who cannot find Custom Setting in the list learns
    nothing, and one who sees why learns the answer to the question they were about to ask.
    """
    rank = {EXACT: 0, MAPPED: 1, RESET: 2, BLOCKED: 3}
    choices = []
    carried_count: dict[str, int] = {}

    for key, action_code in action_codes.items():
        # Real numeric Task actions only -- the same filter list_addable_actions uses, so
        # the two pulldowns offer the same universe.
        if not (key.endswith("t") and key[:-1].isdigit()):
            continue
        if key == old_key:
            continue  # Replacing an action with itself is not a question.

        fidelity, carry, reason = classify_swap(old_key, key)
        name = action_code.name

        if fidelity == BLOCKED:
            label = f"{name}  -- cannot: {reason}"
        elif not carry:
            wanted = len(_wanted_args(key))
            label = f"{name}  -- keeps nothing" + (f"  (resets {wanted})" if wanted else "")
        else:
            kept = _carried_names(old_key, carry)
            label = f"{name}  -- keeps {', '.join(kept)}  ({len(carry)} of {len(_wanted_args(key))})"

        carried_count[key] = len(carry)
        choices.append((key, label, fidelity))

    # Fidelity band first, then how much survives within the band, then name.  The middle
    # term is the one worth stating: MAPPED is much the largest band, and sorted by name
    # alone it opens on whatever happens to start with A -- 'Android Notifier, keeps
    # Title' sitting above 'Notify, keeps Text and Title' is the pulldown answering a
    # question nobody asked.  Same rule as mapfind.FindIndex.choices, and for the same
    # reason: commonest first, alphabetical only to break a tie.
    choices.sort(key=lambda entry: (rank[entry[2]], -carried_count[entry[0]], entry[1]))
    return choices


def _carried_names(old_key: str, carry: dict[str, str]) -> list[str]:
    """The SOURCE's names for the arguments that survive, in the source's own order.

    The source's names rather than the target's because the user is looking at a list of
    things they are about to lose, and knows the action they started from -- "keeps Text,
    Title" answers "what happens to my Flash", which is the question being asked of this
    pulldown.  Where the two differ the source's name is also the more informative half:
    "keeps Package/App Name" says more than "keeps App".
    """
    return [arg.arg_name or f"arg{arg.arg_id}" for arg in _effective_args(old_key) if arg.arg_id in carry]


def source_choices(index: mapfind.FindIndex) -> list[tuple[str, str, int]]:
    """(action key, label, count) for every action the CONFIGURATION uses, commonest first.

    The Replace tab's left-hand pulldown.  Built from the same index the Find tab's action
    pulldown is built from, and for the same reason mapfind gives: a pulldown of Tasker's
    whole action table runs to 550 entries, nearly all of which match nothing in the file
    in front of the user.

    Keyed by action KEY rather than by name, which is the one way this differs from
    mapfind's own catalog.  A name is what a search matches and is not unique -- two codes
    in actionc.py are both called 'Calendar Task' -- while a swap has to know which code it
    is rewriting.
    """
    counts: Counter = Counter()
    for record in index.objects:
        if record.kind != TASK:
            continue
        for action in record.actions:
            # Structural actions are excluded rather than offered and refused.  They are
            # four of the six commonest things in a real configuration -- If, End If, Else
            # and Perform Task together outnumber everything else -- so leaving them in
            # puts four dead ends at the top of the list.  Unlike a blocked TARGET, where
            # the reason is worth reading, a source that can never be swapped teaches
            # nothing by being selectable.
            if action.code and f"{action.code}t" not in _STRUCTURAL:
                counts[f"{action.code}t"] += 1

    choices = []
    for key, count in counts.items():
        name = action_codes[key].name if key in action_codes else f"code {key[:-1]}"
        choices.append((key, f"{name}  ({count})", count))
    choices.sort(key=lambda entry: (-entry[2], entry[1]))
    return choices


def variable_choices(index: varxref.VariableIndex) -> list[tuple[str, str, str]]:
    """(name, owner, label) for every variable that could be renamed, commonest first.

    Locals carry their Task in the label because they ARE per-Task: two Tasks using
    %counter have two variables, and a pulldown that showed one '%counter' would be
    offering to rename something that does not exist.

    A name used by more than one instance ALSO gets an all-instances entry, carrying
    EVERY_INSTANCE as its owner -- "rename the loop counter throughout" needs a way to be
    said, and typing the name into a box would not distinguish it from picking one of the
    59 Tasks that use %i.  It sits directly above that name's individual entries, sorted
    with them, so the choice between "this one" and "all of them" is made in one place
    rather than by finding a checkbox somewhere else.

    The ones plan_variable_rename would refuse outright are left out rather than offered
    and then rejected -- a built-in and a one-character name cannot become renameable by
    anything the user types in the other box.
    """
    choices = []
    instances: Counter = Counter()
    totals: Counter = Counter()
    for (name, _owner), variable in index.variables.items():
        if _rename_refusal(name, f"{name}_"):
            continue
        instances[name] += 1
        totals[name] += len(variable.sets) + len(variable.reads)

    for (name, owner), variable in index.variables.items():
        if _rename_refusal(name, f"{name}_"):
            continue  # Refused whatever it would be renamed to.
        uses = len(variable.sets) + len(variable.reads)
        where = ""
        if owner:
            location = index.scope_locations.get(owner)
            where = f" in {location.label}" if location else f" in {owner}"
        label = f"{name}  ({variable.scope}{where}: set {len(variable.sets)}, read {len(variable.reads)})"
        # Sunk to the bottom rather than left out: renaming one of these is almost always a
        # mistake -- something outside the file puts the value there, so the new name would
        # never hold anything -- and %err, %errmsg and %priority are among the most used
        # names in any configuration, so ranking purely by use opens the list on three
        # entries nobody wants.  Still offered, because varxref recognises the built-in
        # SHAPE as well as the documented list, and that shape also covers somebody's own
        # SHOUTING global.
        pointless = variable.scope in (varxref.TASKER_SET, varxref.BUILTIN)
        choices.append((name, owner, label, uses, pointless))

    # Ranked by the NAME's total use, not the instance's, so every entry for one name
    # stays together instead of the busiest Task's %i sorting hundreds of rows away from
    # the next Task's.  The all-instances entry leads its group (the -1 ordinal), and
    # within the individual ones the busiest comes first.
    for name, count in instances.items():
        if count < 2:
            continue  # One instance: "all of them" and "this one" are the same entry.
        variable = next(entry for (candidate, _o), entry in index.variables.items() if candidate == name)
        pointless = variable.scope in (varxref.TASKER_SET, varxref.BUILTIN)
        label = f"{name}  (ALL {count} instances: {totals[name]} uses in total)"
        choices.append((name, EVERY_INSTANCE, label, totals[name], pointless))

    choices.sort(
        key=lambda entry: (
            entry[4],  # the ones renaming cannot help, last
            -totals[entry[0]],  # busiest NAME first, so a name's entries stay together
            entry[0],
            entry[1] is not EVERY_INSTANCE,  # "all of them" leads its own group
            -entry[3],
        ),
    )
    return [(name, owner, label) for name, owner, label, _, _ in choices]


def plan_action_swap(
    old_key: str,
    new_key: str,
    project: str = "",
) -> Plan:
    """Every action in the file with `old_key`'s code, and what replacing it would do.

    Finds them through mapfind: a Query with only the action facet set is the question
    'which Tasks perform an HTTP Request', which the index already answers, and the
    per-Task action numbers come back with it.  `project` narrows exactly as the Find
    dialog's Project narrowing does -- and narrowing matters more here than it does for a
    search, since 'replace this everywhere' over an 83-Project backup is rarely what
    somebody means the first time they think of it.

    Does not touch the tree.  Each Change carries the whole <Action> as its site and the
    old/new one-line renderings for the preview, so the user reads 'Flash "Done: %n"' ->
    'Notify "Done: %n"' per row rather than a code number.

    RESET rows arrive UNTICKED, alone among the fidelities.  Offering RESET and defaulting
    it to on are different decisions: EXACT and MAPPED lose nothing the preview does not
    show, while RESET discards every argument value in every action it touches, and a user
    who ticked the header box without reading to the bottom of a 60-row list would not find
    out until they looked at a Task days later.  Unticked, the same user gets nothing they
    did not ask for individually, and the plan's warnings say how many are waiting.
    """
    old_name = action_codes[old_key].name if old_key in action_codes else old_key
    new_name = action_codes[new_key].name if new_key in action_codes else new_key
    what = f"Replace '{old_name}' with '{new_name}'"
    if project:
        what = f"{what} in Project '{project}'"
    plan = Plan(what=what)

    # `what` is also the Undo label, so the scope belongs in it: "Replace 'Flash' with
    # 'Notify'" sitting in the history of a run that only touched one Task would describe
    # a much bigger change than the one that can be taken back.
    scope = current_scope()
    if not scope.is_everything:
        plan.what = f"{what} in {scope.phrase}"
        plan.warnings.append(
            f"Limited to {scope.phrase}, which is what the app is displaying.  Clear the single-item "
            f"selection to replace across the whole configuration.",
        )

    fidelity, carry, reason = classify_swap(old_key, new_key)
    if fidelity == BLOCKED:
        plan.warnings.append(reason)
        return plan

    index = mapfind.build_index()
    old_code = old_key[:-1]

    for record in index.objects:
        if record.kind != TASK:
            continue
        if project and record.project != project:
            continue
        for action in record.actions:
            if action.code != old_code or action.element is None:
                continue
            site = Site(
                kind=ACTION_ELEMENT,
                element=action.element,
                where=record.target.at_action(action.number),
                detail=old_name,
                new_key=new_key,
                carry=carry,
            )
            plan.changes.append(
                Change(
                    site=site,
                    before=_action_summary(action.element, old_key),
                    after=_projected_summary(action.element, old_key, new_key, carry),
                    note=_swap_note(action.element, fidelity, carry, old_key),
                ),
            )

    # EXACT and MAPPED start ticked; RESET is opt-in.  See the docstring above.
    if fidelity != RESET:
        plan.selected = set(range(len(plan.changes)))
    elif plan.changes:
        plan.warnings.append(
            f"Every one of these {len(plan.changes)} discards all of "
            f"'{old_name}'s arguments -- nothing carries over to '{new_name}'.  None are ticked.",
        )

    if fidelity == MAPPED:
        plan.warnings.append(f"Carries over: {', '.join(_carried_names(old_key, carry))}.")
        # What is LOST is deliberately not summarized here.  It differs per action -- only
        # the Flashes that set a Timeout lose a Timeout -- so it belongs on the rows that
        # actually lose it, where _swap_note puts it, and a plan-level list would name
        # arguments most of these actions never filled in.

    if any(action_element.find("label") is not None for action_element in _elements_of(plan)):
        plan.warnings.append(
            "Some of these actions carry a label written for the old action.  Labels are kept as they "
            "are -- this tool does not rewrite prose -- so check the ones that describe what the action did.",
        )

    return plan


def _elements_of(plan: Plan) -> list:
    """Every element a plan would change."""
    return [change.site.element for change in plan.changes]


def _argument_element(
    action_element: defusedxml.ElementTree.Element | None,
    arg_id: str,
) -> defusedxml.ElementTree.Element | None:
    """One argument of an action, by its 'sr', or None."""
    if action_element is None:
        return None
    for child in action_element:
        if child.attrib.get("sr", "") == f"arg{arg_id}":
            return child
    return None


def _has_value(element: defusedxml.ElementTree.Element | None) -> bool:
    """Whether an argument element holds anything at all.

    Three shapes count as holding something: text, a val= other than the '0' Tasker writes
    for an unset numeric, and any child element (a <var> binding, or a picker's subtree).
    """
    if element is None:
        return False
    if (element.text or "").strip():
        return True
    if element.attrib.get("val", "0") not in ("", "0"):
        return True
    return len(element) > 0


def _action_summary(action_element: defusedxml.ElementTree.Element, action_key: str) -> str:
    """One line describing an action as it stands -- "Flash 'Done: %n'".

    The first argument that holds text, which is the one the Map leads with and almost
    always the one that says what the action is for.
    """
    name = action_codes[action_key].name if action_key in action_codes else action_key
    for arg in _wanted_args(action_key):
        element = _argument_element(action_element, arg.arg_id)
        text = (element.text or "").strip() if element is not None else ""
        if text:
            return f"{name} '{text[:60]}'"
    return name


def _projected_summary(
    action_element: defusedxml.ElementTree.Element,
    old_key: str,
    new_key: str,
    carry: dict[str, str],
) -> str:
    """The same line, as it would read after the swap -- without performing it.

    Projected rather than produced by swapping a copy: a preview that ran the real
    mutation on a deep copy would be the more obviously correct thing and would cost a
    copy and a full synthesize per row, on a list that can run to hundreds.  What it
    would buy is exactness about which argument leads, which is a cosmetic property of
    one line of preview text.
    """
    name = action_codes[new_key].name if new_key in action_codes else new_key
    for arg in _wanted_args(old_key):
        if arg.arg_id not in carry:
            continue
        element = _argument_element(action_element, arg.arg_id)
        text = (element.text or "").strip() if element is not None else ""
        if text:
            return f"{name} '{text[:60]}'"
    return name


def _swap_note(
    action_element: defusedxml.ElementTree.Element,
    fidelity: str,
    carry: dict[str, str],
    old_key: str,
) -> str:
    """What this particular action loses, as opposed to what the pair loses in general.

    Per action rather than per pair because the answer differs per action: two Flashes
    swapped for Notifies lose the same arguments in principle, and only the one that
    actually set a Timeout loses a Timeout.  A note naming an argument nobody filled in
    is the kind of warning that teaches users to skim past warnings.
    """
    dropped = [
        arg.arg_name or f"arg{arg.arg_id}"
        for arg in _wanted_args(old_key)
        if arg.arg_id not in carry and _has_value(_argument_element(action_element, arg.arg_id))
    ]
    if not dropped:
        return ""
    if fidelity == RESET:
        return "Discards: " + ", ".join(dropped)
    return "Drops: " + ", ".join(dropped)


def _order_children(action_element: defusedxml.ElementTree.Element) -> None:
    """Put an action's children back in the order Tasker writes them: non-argument children
    first in the order they already had, then the arguments sorted by their 'sr' as a
    STRING -- which is why the sample data reads arg0, arg1, arg10, arg11 ... arg2, and not
    in numeric order.

    Nothing reads them this way.  Every reader in this codebase matches on the 'sr'
    attribute rather than on child order, for the reason varxref._string_arguments gives:
    Tasker does not guarantee it.  This is for the diff.  An action rebuilt in a different
    order than Tasker would have written it is a hundred moved lines in xmldiff's output and
    in any version control the user keeps their backups in, all of them noise, hiding the
    one line that is the change they actually made.

    Used by the swap, which rebuilds an action's whole argument set, and by an argument
    replace that ADDS one -- a new <Str sr="arg3"> appended after <Str sr="arg8"> would be
    that same noise, for one line of real change.
    """
    children = list(action_element)
    for child in children:
        action_element.remove(child)
    plain = [child for child in children if not child.attrib.get("sr", "").startswith("arg")]
    arguments = [child for child in children if child.attrib.get("sr", "").startswith("arg")]
    arguments.sort(key=lambda child: child.attrib.get("sr", ""))
    action_element.extend(plain + arguments)


def _swap_one_action(
    action_element: defusedxml.ElementTree.Element,
    new_key: str,
    carry: dict[str, str],
) -> None:
    """Rewrite one <Action> in place.  Called only from apply(), only inside its undo block.

    In place, rather than building a new element and substituting it into the parent:
    the <Action> keeps its 'sr' attribute and its position among its siblings for free,
    and taskedit._renumber_actions is not needed because no action was added or removed.

      1. Take the carried values out of the old element -- text for rule 1, a deep copy of
         the subtree for rule 2.  Deep, because the element is about to be removed from the
         tree and a shallow reference would be to a detached node.
      2. Remove every child except _PRESERVED_CHILDREN.
      3. Set <code> to the new code.
      4. Synthesize the new argument set with taskedit.build_synthesized_args -- the same
         function Add Action uses, so a swapped-in action is byte-identical to an added
         one and there is one definition of what a fresh action looks like.
      5. Write the carried values over the synthesized defaults.
      6. For every picker argument the target needs and step 5 did not fill, write the
         empty <App sr="argN"/> / <Img sr="argN"/> that Tasker writes for an unset picker.

    Step 6 is the half taskedit does not do, because Add Action never needs it, and it is
    what the whole classify_action_addability discussion above comes down to in code.  It
    runs after step 5 rather than as part of step 4 so that a carried picker is never
    overwritten by an empty one.

    Steps 4-before-5 rather than skipping the defaults for carried arguments: an argument
    Tasker expects to be present is present with its default even when nothing was carried
    into it, which is what stops a half-populated action reaching the device.
    """
    element_cls = type(action_element)

    # 1.  Lift what survives, before anything is torn down.  Whole elements rather than
    # their text, and deep copies rather than references: the source element is about to
    # be removed from the tree, and carrying the element keeps everything hanging off it
    # that a text copy would drop -- an <Int>'s val=, the <var>%Volume</var> a user bound
    # to a numeric argument in place of a figure, an <App>'s appPkg/appClass/label, an
    # <Img>'s nme/tint.  Rule 1 only pairs arguments of the same arg_type, so the element
    # being moved is always the shape the target expects.
    carried: dict[str, defusedxml.ElementTree.Element] = {}
    for child in list(action_element):
        sr = child.attrib.get("sr", "")
        if sr.startswith("arg") and sr[3:] in carry:
            lifted = copy.deepcopy(child)
            lifted.attrib["sr"] = f"arg{carry[sr[3:]]}"
            carried[carry[sr[3:]]] = lifted

    # 2.  Tear down.  <code> is kept alongside _PRESERVED_CHILDREN and then overwritten,
    # rather than removed and rebuilt, so it keeps its position as the first child -- which
    # is where Tasker writes it and where a human reading the file looks for it.
    for child in list(action_element):
        if child.tag not in _PRESERVED_CHILDREN and child.tag != "code":
            action_element.remove(child)

    # 3.  The new identity.
    code_element = action_element.find("code")
    if code_element is None:
        code_element = element_cls("code")
        action_element.insert(0, code_element)
    code_element.text = new_key[:-1]

    # 4.  A fresh argument set, through the same function Add Action uses.
    taskedit.build_synthesized_args(element_cls, action_element, _effective_args(new_key), new_key)

    # 5.  The carried values displace the defaults just synthesized for them.
    synthesized = {
        child.attrib.get("sr", ""): child for child in action_element if child.attrib.get("sr", "").startswith("arg")
    }
    for new_id, lifted in carried.items():
        existing = synthesized.get(f"arg{new_id}")
        if existing is not None:
            action_element.remove(existing)
        action_element.append(lifted)

    # 6.  The picker arguments step 4 cannot write.  build_synthesized_args goes through
    # _build_default_arg, which returns None for every App/Icon category argument, so
    # without this the target is left missing an argument Tasker expects -- and every one
    # of the 90 Notify actions in the sample data carries its <Img sr="arg2">, filled or
    # empty.  The empty element is not an invention: 675 empty <Img> and 287 empty <App>
    # sit in that same sample data, which is what Tasker itself writes for an unset picker.
    present = {child.attrib.get("sr", "") for child in action_element}
    for arg in _wanted_args(new_key):
        tag = _PICKER_TAGS.get(_category(arg))
        if tag and f"arg{arg.arg_id}" not in present:
            action_element.append(element_cls(tag, {"sr": f"arg{arg.arg_id}"}))

    # 7.  Back into the order Tasker writes them.  See _order_children.
    _order_children(action_element)


# ##################################################################################
# Condition for condition.
#
# The fourth operation, and the only one that rewrites a PROFILE rather than a Task.  A
# Profile's contexts are the WHEN of a configuration -- "at 8am", "while the screen is
# off", "when this app opens" -- and this answers the question Tasker itself has no
# answer for: "every Profile watching for the old thing should watch for the new one",
# across a hundred Profiles at once.
#
# Structural, like the action swap and for the same reason: two kinds of context are two
# different elements holding different children that mean different things.  Three things
# make it its own operation rather than a case of that one.
#
#   HALF THE KINDS CARRY NO CODE.  A Time is a Time -- its shape is fh/fm/th/tm and there
#   is nothing to look up.  An Event or a State is one of hundreds of codes reading its
#   arguments out of actionc.py exactly as a Task action does, just under a different key
#   suffix (condition.py's condition_event/condition_state).  So a pair of THOSE carries
#   values across through carry_over_map, unchanged, and any pair involving a flat kind
#   carries nothing -- by nature, not by accident.
#
#   A PROFILE HOLDS ONE OF MOST KINDS.  See _ONE_PER_PROFILE.  Giving a Profile a second
#   Time writes a shape Tasker itself never writes, so it is refused with the reason.
#
#   AN EMPTY CONTEXT IS NOT AN EMPTY ARGUMENT.  An action stripped of its arguments still
#   runs; a Profile whose only context is a Day with no days ticked does not trigger at
#   all.  That is on the plan's warnings and on the row of every Profile it is true of.
# ##################################################################################

# The six tags a context is written as, split by whether the tag alone says what it IS.
# mapfind draws the same line for the trigger facet (_TIME_CONTEXTS/_CODED_CONTEXTS) and
# profedit draws it again for the Profile editor (CONDITION_TYPES_ADDABLE splits Event and
# State out of the four it can add from a type name alone) -- three modules, one fact
# about the XML, because each needs it in a different shape.
_FLAT_CONDITIONS = ("Time", "Day", "App", "Loc")
_CODED_CONDITIONS = {"Event": "e", "State": "s"}

# The contexts a Profile carries at most ONE of.  Not a rule written down anywhere in this
# codebase; it is what the sample XML says.  Across 3,475 Profiles: 2,207 Events, 427
# Times, 110 Apps, 35 Days and 5 Locations, and not one Profile holding two of any of
# them -- against 373 Profiles holding two or more States.  A replace that gave a Profile
# a second Time would be writing a shape Tasker never writes, and the user could not see
# it was wrong by looking at the Map, so it becomes a Skip with the reason on it.
_ONE_PER_PROFILE = ("Time", "Day", "App", "Loc", "Event")

# The contexts that can be inverted -- "while the screen is NOT off".  <pin>true</pin>,
# and it appears on State (159 times in the sample XML) and on App (13), on nothing else.
# So the flag is carried over to a State or an App target and dropped for the rest, which
# is the difference between preserving the user's intent and inverting a condition they
# never asked to invert.
_INVERTIBLE_CONDITIONS = ("State", "App")


def condition_key(tag: str, code_key: str = "") -> str:
    """One string naming a kind of context, for the pulldowns to key their options by.

    'Time', 'Day', 'App', 'Loc' for the flat kinds; 'Event:2078e', 'State:100s' for the
    coded ones -- the tag is carried alongside the actionc.py key rather than derived from
    its suffix, so that reading a key never depends on knowing that 'e' means Event.
    """
    return f"{tag}:{code_key}" if code_key else tag


def _split_condition(key: str) -> tuple[str, str]:
    """A condition key back into (tag, actionc.py key) -- the second is '' for a flat kind."""
    tag, _, code_key = key.partition(":")
    return tag, code_key


def _condition_name(key: str) -> str:
    """What this kind of context is called: 'Time', 'Application', 'Event: Wifi Connected'.

    The flat names come from mapfind's own trigger labels rather than from the tag, so
    that one context reads the same in the Find tab's pulldown, in the Replace tab's, and
    in the report -- 'Location', never 'Loc'.
    """
    tag, code_key = _split_condition(key)
    if not code_key:
        return mapfind._PLAIN_TRIGGER_LABELS.get(tag, tag)  # noqa: SLF001
    entry = action_codes.get(code_key)
    return f"{tag}: {entry.name if entry else f'code {code_key[:-1]}'}"


def condition_choices(index: mapfind.FindIndex) -> list[tuple[str, str, int]]:
    """(condition key, label, count) for every context the CONFIGURATION uses, commonest first.

    The same bargain source_choices strikes for actions: Tasker's whole table of Events and
    States runs to hundreds of entries, nearly none of which are in the file in front of
    the user, and the count beside each one is also the number of places a swap would touch
    before any preview is run.
    """
    counts: Counter = Counter()
    names: dict[str, str] = {}
    for record in index.objects:
        if record.kind != PROFILE:
            continue
        for condition in record.conditions:
            if condition.element is None:
                continue
            key = condition_key(condition.tag, condition.key)
            counts[key] += 1
            names[key] = condition.name

    choices = [(key, f"{names[key]}  ({count})", count) for key, count in counts.items()]
    choices.sort(key=lambda entry: (-entry[2], entry[1]))
    return choices


def _condition_blocked(new_key: str) -> str:
    """Why an empty context of this kind cannot be built at all, or "".

    The same single reason a swap target is ever blocked: a plugin payload <Bundle> that
    bundle.py has no recorded definition for.  An opaque payload has no empty form a
    plugin will accept, and carrying one over from the source is not on the table either
    -- a different code is a different plugin, and its payload would mean nothing here.
    """
    tag, code_key = _split_condition(new_key)
    if not code_key:
        return "" if tag in _FLAT_CONDITIONS else f"'{tag}' is not a Profile context this build knows about."
    if code_key not in action_codes:
        return f"'{new_key}' is not a Profile context this build knows about."
    if taskedit.get_bundle_definition(code_key) is None:
        for arg in _wanted_args(code_key):
            if _category(arg) == "Bundle":
                return (
                    f"'{action_codes[code_key].name}' is a plugin {tag.lower()} and no definition of its "
                    "configuration has been recorded, so an empty one cannot be built."
                )
    return ""


def classify_condition_swap(old_key: str, new_key: str) -> tuple[str, dict[str, str], str]:
    """(fidelity, carry-over map, reason) for one pair of context kinds.

    EXACT/MAPPED/RESET mean exactly what they mean for an action swap, and are computed
    the same way -- by carry_over_map, off actionc.py -- for the one pair that can carry
    anything: a coded context for another coded context.  Every pair involving a flat kind
    is RESET, and that is a statement about the XML rather than a limitation: there is no
    correspondence between fh/fm/th/tm and a list of weekdays, and inventing one would put
    an hour where a day number belongs.

    Event and State are compared to each other as freely as two Events are.  Their
    arguments live in the same actionc.py table under different key suffixes, so 'State:
    Wifi Connected' -> 'Event: Wifi Connected' carries the SSID across by the same
    name-and-type rule that carries a Flash's Text into a Notify.
    """
    reason = _condition_blocked(new_key)
    if reason:
        return BLOCKED, {}, reason

    _, old_code = _split_condition(old_key)
    _, new_code = _split_condition(new_key)
    if not old_code or not new_code:
        return RESET, {}, ""

    carry = carry_over_map(old_code, new_code)
    wanted = _wanted_args(new_code)
    given = _wanted_args(old_code)
    if len(carry) == len(wanted) == len(given):
        return EXACT, carry, ""
    return (MAPPED if carry else RESET), carry, ""


def condition_targets(old_key: str) -> list[tuple[str, str, str]]:
    """(condition key, label, fidelity) for every kind a context could become.

    Everything Tasker can watch for: the four flat kinds and every Event and State code in
    actionc.py.  Nothing is filtered out; every entry says what choosing it would cost,
    the same way fidelity_choices does for actions:

        State: Wifi Connected     -- keeps SSID, MAC  (2 of 3)
        Event: Wifi Connected     -- keeps SSID  (1 of 4)
        Day                       -- a fresh, empty Day
        Custom Setting            -- cannot: plugin payload not recorded

    'a fresh, empty X' rather than 'keeps nothing', which is what the action pulldown says
    in the same place.  For an action, keeping nothing is a loss of arguments off something
    that still runs; for a context it means the Profile is left with a trigger that has not
    been set up yet, and the wording is the first place the user meets that.
    """
    rank = {EXACT: 0, MAPPED: 1, RESET: 2, BLOCKED: 3}
    carried_count: dict[str, int] = {}
    choices = []

    candidates = [condition_key(tag) for tag in _FLAT_CONDITIONS]
    candidates += [
        condition_key(tag, key)
        for tag, suffix in _CODED_CONDITIONS.items()
        for key in action_codes
        if key.endswith(suffix) and key[:-1].isdigit()
    ]

    for key in candidates:
        if key == old_key:
            continue  # Replacing a context with the same kind of context is not a question.
        fidelity, carry, reason = classify_condition_swap(old_key, key)
        name = _condition_name(key)
        _, code_key = _split_condition(key)

        if fidelity == BLOCKED:
            label = f"{name}  -- cannot: {reason}"
        elif not carry:
            label = f"{name}  -- a fresh, empty {name.split(':')[0]}"
        else:
            kept = _carried_names(_split_condition(old_key)[1], carry)
            label = f"{name}  -- keeps {', '.join(kept)}  ({len(carry)} of {len(_wanted_args(code_key))})"

        carried_count[key] = len(carry)
        choices.append((key, label, fidelity))

    # Same ordering rule as fidelity_choices: the band that keeps the most first, then how
    # much survives within the band, then the name.  The four flat kinds sit in the RESET
    # band with everything else that carries nothing, rather than being pinned to the top
    # -- a Day is not a better answer than an Event that keeps the SSID.
    choices.sort(key=lambda entry: (rank[entry[2]], -carried_count[entry[0]], entry[1]))
    return choices


def _fresh_condition(element_cls: type, new_key: str) -> defusedxml.ElementTree.Element:
    """An empty context of this kind, built exactly as adding one by hand would build it.

    The flat kinds go through profedit.add_condition_to_profile -- the same call the
    Profile editor's 'Add Condition' makes -- on a throwaway Profile, which is the
    _creatable trick again: what a fresh Time looks like (fh/fm/th/tm at 0, sr, ve) is
    profedit's fact, and a second statement of it here is the one that would be forgotten
    when Tasker changes.

    The coded kinds are built here rather than through profedit's own Event/State adders,
    for the reason this module's classify_action_addability note gives at length: those
    refuse a code carrying an App or Icon argument, because the Add dialog offers no picker
    widget to fill one in -- while a swap can write the empty <App sr="argN"> Tasker itself
    writes nearly a thousand times in the sample XML.  The three lines that differ from a
    Task action are all there is to it: the tag, and the <pri>0</pri> that Event carries
    and State does not (condition.py's condition_event reads one on every Event).

    Raises ValueError if the kind cannot be built, which apply() turns into one reported
    failure rather than a crashed batch.
    """
    tag, code_key = _split_condition(new_key)

    if not code_key:
        scratch = profedit.EditableProfile(profile_id="", profile_element=element_cls("Profile"))
        built = profedit.add_condition_to_profile(scratch, tag)
        if isinstance(built, list):
            raise ValueError("; ".join(built))
        return built.condition_element

    fresh = element_cls(tag, {"sr": "con0", "ve": "2"})
    code_element = element_cls("code")
    code_element.text = code_key[:-1]
    fresh.append(code_element)
    if tag == "Event":
        priority = element_cls("pri")
        priority.text = "0"
        fresh.append(priority)

    # code_key is passed so that a plugin's opaque payload <Bundle> is rebuilt from
    # bundle.py's recorded definition for this very code -- see build_synthesized_args.
    taskedit.build_synthesized_args(element_cls, fresh, _effective_args(code_key), code_key)

    # The picker arguments build_synthesized_args cannot write, as the empty element
    # Tasker writes for an unset picker.  Step 6 of _swap_one_action, for the same reason.
    present = {child.attrib.get("sr", "") for child in fresh}
    for arg in _wanted_args(code_key):
        picker_tag = _PICKER_TAGS.get(_category(arg))
        if picker_tag and f"arg{arg.arg_id}" not in present:
            fresh.append(element_cls(picker_tag, {"sr": f"arg{arg.arg_id}"}))
    return fresh


def _kept_condition_children(new_tag: str) -> tuple[str, ...]:
    """The children that survive into a context of this kind, whatever kind it was before.

    Decided by the TARGET, not by the pair: a child is kept when the new context can still
    mean something by it, and dropped when it cannot.  <cname> is the user's own name for
    the context and is kept always -- prose, like an action's label, and flagged rather
    than rewritten.  <pin> is the inverted flag and only State and App carry one.
    <ConditionList>/<Condition> are the if-clauses hung off a coded context, which only a
    coded context can hold.  <abort> is Event's alone.
    """
    keep = ["cname"]
    if new_tag in _INVERTIBLE_CONDITIONS:
        keep.append("pin")
    if new_tag in _CODED_CONDITIONS:
        keep.extend(("ConditionList", "Condition"))
    if new_tag == "Event":
        keep.append("abort")
    return tuple(keep)


def _has_time_window(element: defusedxml.ElementTree.Element) -> bool:
    """Whether a Time condition names a from/to time at all.

    Tasker writes fh/fm/th/tm as -1 for a Time that only REPEATS -- "every 12 minutes",
    with no window -- and 37 of the 293 Profiles in one real backup are that shape.
    profedit's 12-hour formatter is written for the editor, where a negative hour is never
    offered, and renders -1 as '11:-1 AM'; so the raw hour decides here, and the formatted
    string is used only where there is something to format.
    """
    if (element.findtext("fromvar") or "").strip() or (element.findtext("tovar") or "").strip():
        return True
    hour = (element.findtext("fh") or "").strip()
    return bool(hour) and not hour.startswith("-")


def _condition_summary(element: defusedxml.ElementTree.Element, tag: str, code_key: str = "") -> str:
    """One line describing a context as it stands -- "Time 08:00 AM to 09:30 AM".

    Read through profedit's own field getters rather than off the XML, so the preview says
    what the Profile editor would say about the same context, down to the 12-hour clock and
    the weekday names.  condition.py's parse_profile_condition is the other candidate and
    is the wrong one here: it renders HTML for the Map, follows the 'pretty' and 'debug'
    program arguments, and builds missing action codes as a side effect -- none of which
    belongs in a preview row.
    """
    label = _condition_name(condition_key(tag, code_key))
    inverted = " [inverted]" if (element.findtext("pin") or "").strip() == "true" else ""

    if code_key:
        for arg in _wanted_args(code_key):
            argument = _argument_element(element, arg.arg_id)
            text = (argument.text or "").strip() if argument is not None else ""
            if text:
                return f"{label} '{text[:60]}'{inverted}"
        return f"{label}{inverted}"

    condition = profedit.EditableCondition(cond_index=0, cond_type=tag, condition_element=element)
    if tag == "Time":
        values = profedit.get_time_field_values(condition)
        pieces = []
        if _has_time_window(element):
            pieces.append(f"{values['start_time']} to {values['end_time']}")
        if values["rep_value"]:
            pieces.append(f"every {values['rep_value']} {values['rep_unit'].lower()}")
        detail = ", ".join(pieces)
    elif tag == "Day":
        weekdays = [profedit.WEEKDAY_NAMES[day] for day in profedit.get_day_selected_weekdays(condition) if day <= 7]
        months = [profedit.MONTH_NAMES[month] for month in profedit.get_day_selected_months(condition) if month <= 11]
        month_days = [str(day) for day in profedit.get_day_selected_month_days(condition)]
        detail = ", ".join(piece for piece in (" ".join(weekdays), " ".join(months), " ".join(month_days)) if piece)
    elif tag == "App":
        detail = ", ".join(entry["label"] or entry["pkg"] for entry in profedit.get_app_entries(condition))
    elif tag == "Loc":
        values = profedit.get_loc_field_values(condition)
        detail = f"{values['lat']},{values['long']} radius {values['rad']}" if values["lat"] else ""
    else:
        detail = ""

    return f"{label} {detail}{inverted}".replace("  ", " ").strip()


def _projected_condition_summary(
    element: defusedxml.ElementTree.Element,
    old_key: str,
    new_key: str,
    carry: dict[str, str],
) -> str:
    """The same line as it would read afterwards, projected rather than performed.

    Same bargain _projected_summary strikes for an action, and the answer is shorter here:
    nothing carries at all unless both kinds are coded, so most of these are the name of
    the new context and nothing else -- which is the honest preview of a context that
    arrives empty.
    """
    name = _condition_name(new_key)
    _, old_code = _split_condition(old_key)
    if not carry or not old_code:
        return name
    for arg in _wanted_args(old_code):
        if arg.arg_id not in carry:
            continue
        argument = _argument_element(element, arg.arg_id)
        text = (argument.text or "").strip() if argument is not None else ""
        if text:
            return f"{name} '{text[:60]}'"
    return name


def _condition_note(
    record: object,
    condition: object,
    new_key: str,
    carry: dict[str, str],
    fidelity: str,
) -> str:
    """What this particular Profile loses, as opposed to what the pair loses in general.

    Per Profile for the reason _swap_note is per action: a note naming something nobody
    filled in is the kind of warning that teaches users to skim past warnings.  The last
    clause is the one worth having -- a Profile with one context and nothing in it is a
    Profile that has stopped working, and that is not visible in a before/after line
    reading 'Time 08:00 AM to 09:30 AM  ->  Day'.
    """
    new_tag, new_code = _split_condition(new_key)
    element = condition.element
    pieces = []

    if condition.key and new_code:
        dropped = [
            arg.arg_name or f"arg{arg.arg_id}"
            for arg in _wanted_args(condition.key)
            if arg.arg_id not in carry and _has_value(_argument_element(element, arg.arg_id))
        ]
        if dropped:
            pieces.append(("Discards: " if fidelity == RESET else "Drops: ") + ", ".join(dropped))

    kept = _kept_condition_children(new_tag)
    if element.find("ConditionList") is not None and "ConditionList" not in kept:
        pieces.append("drops the conditions attached to it")
    if (element.findtext("pin") or "").strip() == "true" and "pin" not in kept:
        pieces.append("drops its 'inverted' setting")
    if not carry and len(record.conditions) == 1:
        pieces.append("the Profile's only condition -- it will not trigger until the new one is set up")

    return "; ".join(pieces)


def _duplicate_context(record: object, condition: object, new_tag: str, already_planned: int) -> str:
    """Why this Profile cannot take another context of the target kind, or "".

    See _ONE_PER_PROFILE.  Two ways it happens, and the second one only exists because a
    Profile may hold several States: replacing both of a Profile's States with the same
    Event would hand it two Events one row at a time, and each row on its own looks fine.
    """
    if new_tag not in _ONE_PER_PROFILE:
        return ""
    name = _condition_name(condition_key(new_tag))
    article = "an" if name[:1] in "AEIOU" else "a"
    if any(other is not condition and other.tag == new_tag for other in record.conditions):
        return (
            f"this Profile already has {article} {name} condition, and Tasker writes only one of those "
            f"per Profile."
        )
    if already_planned:
        return (
            f"the row above already gives this Profile its one {name} condition -- replace the rest with "
            f"something else, or leave them."
        )
    return ""


def plan_condition_replace(
    old_key: str,
    new_key: str,
    project: str = "",
) -> Plan:
    """Every Profile context of one kind, and what replacing it with another would do.

    `project` narrows exactly as the other three do.  Nothing is touched: each Change
    carries the context element as its site and the old and new one-line renderings, so
    the user reads 'Time 08:00 AM to 09:30 AM  ->  Day' per row rather than a tag name.

    EVERY ROW ARRIVES TICKED, INCLUDING THE RESET ONES, which is where this parts company
    with plan_action_swap -- deliberately, and for a reason that does not carry across:

      For an action, RESET is the accident.  The user picked a target from a pulldown full
      of pairs that DO carry the message text, and a row that quietly discards sixteen
      arguments is a surprise they may not have read to the bottom of the list to find.

      For a context, carrying nothing is what replacing one KIND with another means.  A
      Time is not a Day; there is no correspondence to lose.  Every entry in the target
      pulldown says 'a fresh, empty Day' before it is chosen, every row's before/after line
      shows the settings going and the empty context arriving, and the plan says once,
      loudly, that the new ones have to be filled in.  Unticking all of them by default
      would leave the ordinary use of this feature -- 'these forty Profiles should trigger
      on something else' -- to be re-ticked forty times.

    What IS refused rather than ticked is a Profile that would end up with two Times, or
    two Events, or two of any of _ONE_PER_PROFILE.  Those become Skips: the user cannot see
    that shape is wrong by looking at the Map, so the tool must not write it.
    """
    old_name, new_name = _condition_name(old_key), _condition_name(new_key)
    old_tag, _ = _split_condition(old_key)
    new_tag, _ = _split_condition(new_key)

    what = f"Replace Profile condition '{old_name}' with '{new_name}'"
    if project:
        what = f"{what} in Project '{project}'"
    plan = Plan(what=what)

    # The same scope note the other three carry, and for the same reason: `what` is the
    # Undo label, so a plan that touched one Profile must not describe itself as touching
    # the file.
    scope = current_scope()
    if not scope.is_everything:
        plan.what = f"{what} in {scope.phrase}"
        plan.warnings.append(
            f"Limited to {scope.phrase}, which is what the app is displaying.  Clear the single-item "
            f"selection to replace across the whole configuration.",
        )

    fidelity, carry, reason = classify_condition_swap(old_key, new_key)
    if fidelity == BLOCKED:
        plan.warnings.append(reason)
        return plan

    index = mapfind.build_index()
    named = 0

    for record in index.objects:
        if record.kind != PROFILE:
            continue
        if project and record.project != project:
            continue
        planned = 0
        for condition in record.conditions:
            if condition.element is None or condition_key(condition.tag, condition.key) != old_key:
                continue
            # Numbered from 1 for the user, off the 0-based number Tasker writes in the
            # condition's own sr="conN" -- the same offset the Map applies to action numbers.
            where = record.target.with_text(f"condition {condition.index + 1}")
            clash = _duplicate_context(record, condition, new_tag, planned)
            if clash:
                plan.skips.append(Skip(where=where, reason=BLOCKED_DUPLICATE, explanation=clash))
                continue
            planned += 1
            named += condition.element.find("cname") is not None
            plan.changes.append(
                Change(
                    site=Site(
                        kind=PROFILE_CONDITION,
                        element=condition.element,
                        where=where,
                        detail=old_name,
                        new_key=new_key,
                        carry=carry,
                    ),
                    before=_condition_summary(condition.element, condition.tag, condition.key),
                    after=_projected_condition_summary(condition.element, old_key, new_key, carry),
                    note=_condition_note(record, condition, new_key, carry, fidelity),
                ),
            )

    plan.selected = set(range(len(plan.changes)))

    if plan.changes and not carry:
        plan.warnings.append(
            f"Each of these arrives EMPTY -- a new {new_name} exactly as 'Add Condition' writes one, with "
            f"nothing filled in.  Open each Profile afterwards and set it up, or the Profile will not "
            f"trigger on anything.",
        )
    if fidelity == MAPPED:
        plan.warnings.append(f"Carries over: {', '.join(_carried_names(_split_condition(old_key)[1], carry))}.")
    if plan.changes and new_tag == "Event" and old_tag != "Event":
        # An Event happens at a moment; everything else lasts.  Worth saying once, because
        # it is invisible in a before/after line and it silently strands an Exit Task.
        plan.warnings.append(
            "An Event happens at an instant, where a Time, Day, Application, Location or State stays true "
            "for a while.  A Profile left with only an Event has no end to run an Exit Task at -- check "
            "the ones that have an Exit Task.",
        )
    if named:
        plan.warnings.append(
            f"{named} of these carry a name written for the old condition.  Names are kept as they are -- "
            f"this tool does not rewrite prose -- so check the ones that describe what they watched for.",
        )

    return plan


def _order_condition_children(condition_element: defusedxml.ElementTree.Element) -> None:
    """Put a context's children in the order Tasker writes them: the non-argument ones in
    alphabetical order, then the arguments by their 'sr' as a string.

    _order_children's counterpart for a Profile context, and it differs in the first half
    because the XML does.  An <Action> keeps its non-argument children in the order they
    were already in; a context's are alphabetical, and the sample XML is unambiguous about
    it -- Time reads fh, fm, rep, repval, th, tm; State reads cname, code, ConditionList;
    App reads cls0, cls1, cls10, cls2 ... cname, flags, label0 ... pin, pkg0, which is a
    plain case-insensitive string sort with the numbered families falling where they fall.
    Event reads code, pri and then its arguments, which is the same rule again.

    For the diff, exactly as _order_children is: a context rebuilt in an order Tasker would
    not have written is a screenful of moved lines in xmldiff and in whatever the user keeps
    their backups in, hiding the one line that is the change they made.
    """
    children = list(condition_element)
    for child in children:
        condition_element.remove(child)
    plain = [child for child in children if not child.attrib.get("sr", "").startswith("arg")]
    arguments = [child for child in children if child.attrib.get("sr", "").startswith("arg")]
    plain.sort(key=lambda child: child.tag.lower())
    arguments.sort(key=lambda child: child.attrib.get("sr", ""))
    condition_element.extend(plain + arguments)


def _swap_one_condition(
    condition_element: defusedxml.ElementTree.Element,
    new_key: str,
    carry: dict[str, str],
) -> None:
    """Rewrite one Profile context in place.  Called only from apply(), inside its undo block.

    In place -- the element keeps its identity, its sr="conN" and its position among the
    Profile's children -- for the reason _swap_one_action gives about an <Action>, and one
    more that is specific to a context: sr="conN" is its POSITION among the contexts, so a
    context added and removed rather than rewritten would need every one after it
    renumbered (profedit._renumber_conditions), and a plan changing two contexts of one
    Profile would be renumbering the tree under its own second site.

    The tag itself changes, which is the one thing an action swap never does: a Time
    becoming a Day is a <Time> element becoming a <Day> element.  So the whole element is
    emptied -- children and attributes both -- and refilled from a freshly built one,
    rather than having its <code> overwritten in place.
    """
    element_cls = type(condition_element)

    # Built FIRST, before anything is torn down: if the target cannot be built this raises,
    # and it must raise with the Profile's context still intact.
    fresh = _fresh_condition(element_cls, new_key)
    keep_tags = _kept_condition_children(fresh.tag)

    # 1.  Lift what survives, deep, before the tear-down -- the arguments that carry over
    # (only ever coded-to-coded) and the children that outlive the kind.
    carried: dict[str, defusedxml.ElementTree.Element] = {}
    for child in list(condition_element):
        sr = child.attrib.get("sr", "")
        if carry and sr.startswith("arg") and sr[3:] in carry:
            lifted = copy.deepcopy(child)
            lifted.attrib["sr"] = f"arg{carry[sr[3:]]}"
            carried[carry[sr[3:]]] = lifted
    kept = [copy.deepcopy(child) for child in condition_element if child.tag in keep_tags]

    # 2.  Tear down, keeping only the position.  The attributes go with the children: 've'
    # belongs to the kind, and only 'sr' -- which context this is -- belongs to the Profile.
    position = condition_element.attrib.get("sr", "")
    for child in list(condition_element):
        condition_element.remove(child)
    condition_element.tag = fresh.tag
    condition_element.attrib.clear()
    condition_element.attrib.update(fresh.attrib)
    if position:
        condition_element.set("sr", position)

    # 3.  The new context, whole.
    condition_element.extend(list(fresh))

    # 4.  The carried values displace the defaults just built for them.
    synthesized = {
        child.attrib.get("sr", ""): child
        for child in condition_element
        if child.attrib.get("sr", "").startswith("arg")
    }
    for new_id, lifted in carried.items():
        existing = synthesized.get(f"arg{new_id}")
        if existing is not None:
            condition_element.remove(existing)
        condition_element.append(lifted)

    # 5.  What outlived the kind, and then back into Tasker's own order.
    condition_element.extend(kept)
    _order_condition_children(condition_element)


# ##################################################################################
# An argument's value.
#
# The third operation, and the narrowest: one argument of one action code, across every
# Task the scope allows.  "Every Flash that says 'Done' should say 'Finished'", "every
# HTTP Request pointing at the old host should point at the new one" -- questions that are
# a Find away from being answered and were, until now, a hundred hand edits away from
# being acted on.
#
# Two things it deliberately does NOT do:
#
#   It does not create an argument.  Tasker leaves out an argument the user never set, and
#   an action that does not carry the one being replaced is reported as a skip rather than
#   grown a new element: "replace" is a promise about something that is there, and filling
#   in an argument nobody has ever set is the Task editor's job, one action at a time,
#   where the rest of the action is on screen to judge it by.
#
#   It does not touch a picker.  An App, an Icon or a Scene argument is a subtree Tasker
#   builds from a chooser, not a value anybody types, so those arguments are offered in the
#   pulldown with the reason they cannot be used rather than left out of it -- the same
#   courtesy fidelity_choices pays a blocked swap target.
# ##################################################################################

# Argument categories this can write.  Anything else is a picker: a subtree with its own
# shape, which a typed string cannot stand in for.
#
# Both spellings of the string category, because there are two: arg_specs.json says
# "String" and proginit.build_action_codes_from_json rewrites the entry to "Str" as it
# loads.  Matching only the one in the file left every Str argument in the file --
# Flash's Text among them -- labelled "cannot be typed", which is every argument anybody
# would want this for.
_WRITABLE_CATEGORIES = ("Str", "String", "Int", "Boolean")


def argument_choices(action_key: str) -> list[tuple[str, str, str]]:
    """(arg id, label, refusal) for every argument of one action, in Tasker's own order.

    The Replace tab's argument pulldown.  Named as Tasker's action editor names them,
    because that is what the user is looking at in the Map -- "Text", "Title", "Timeout",
    not "arg0".

    An argument that cannot be written carries its reason as the third field and says so in
    its label rather than being dropped: an argument missing from the list teaches nothing,
    while "Icon -- cannot be typed" answers the question the user was about to ask.
    """
    choices = []
    for argument in _effective_args(action_key):
        if _is_hint_bundle(argument):
            continue  # Not an argument at all -- the plugin's note about what it outputs.
        category = _category(argument)
        name = argument.arg_name or f"arg{argument.arg_id}"
        writable = category in _WRITABLE_CATEGORIES
        refusal = "" if writable else f"a {category or 'picker'} argument is chosen from a picker, not typed"
        label = f"{name}  ({category})" if writable else f"{name}  ({category} -- cannot be typed)"
        choices.append((argument.arg_id, label, refusal))
    return choices


def _argument_site(
    action_element: defusedxml.ElementTree.Element,
    arg_id: str,
    where: Target,
    detail: str,
) -> tuple[Site | None, str]:
    """The field one argument's value sits in, or (None, why not).

    Three shapes, which is the whole reason this is a function: Tasker writes a string
    argument as the text of <Str sr="argN">, a plain numeric as the val= attribute of
    <Int sr="argN">, and a numeric bound to a variable as a <var> child of that <Int>.  The
    same three taskedit.apply_arg_values writes when the Task editor saves one action; this
    is that rule applied to a thousand of them at once.
    """
    element = _argument_element(action_element, arg_id)
    if element is None:
        return None, "this action does not carry that argument -- Tasker leaves out one that was never set."

    if element.tag == "Str":
        return Site(kind=STR_ARG, element=element, where=where, detail=detail), ""
    if element.tag == "Int":
        bound = element.find("var")
        if bound is not None:
            return Site(kind=INT_VAR, element=bound, where=where, detail=detail), ""
        return Site(kind=INT_VALUE, element=element, where=where, detail=detail), ""
    return None, f"this argument is a <{element.tag}>: a picker's choice rather than a typed value."


def _numeric_refusal(numeric: bool, value: str) -> str:
    """Why this value cannot go into a numeric field, or "".

    Only the val= shape is fussy, and it has to be: Tasker reads that attribute as a
    number, so writing "off" or "%level" into it produces an action that looks edited in
    the Map and misbehaves on the device.  A <var>-bound numeric is left alone by this --
    it already holds an expression rather than a number, which is what a binding is for.

    Takes the fact rather than the Site, because an argument being ADDED has no element to
    read the shape off: there, the shape comes from the argument's category instead.
    """
    if not numeric or value.lstrip("-").isdigit():
        return ""
    return (
        f"'{value}' is not a number, and this argument is stored as one.  Bind it to a variable "
        f"in the Task editor if that is what you meant."
    )


def _creatable(action_element: defusedxml.ElementTree.Element, arg_id: str) -> bool:
    """Whether an argument this action does not carry could be written into it.

    Asked of taskedit rather than answered here, and asked by BUILDING one on a throwaway
    copy of the action: build_synthesized_args declines an argument it has no generic
    default for, and the only way to know which those are without restating its rules is to
    let it try.  The copy is the point -- planning must not touch the tree.
    """
    action_key = f"{(action_element.findtext('code') or '').strip()}t"
    argument = next((entry for entry in _effective_args(action_key) if entry.arg_id == arg_id), None)
    if argument is None:
        return False
    scratch = copy.deepcopy(action_element)
    built = taskedit.build_synthesized_args(type(scratch), scratch, [argument])
    return bool(built) and built[0].element is not None


def plan_argument_replace(
    action_key: str,
    arg_id: str,
    new_value: str,
    match: str = "",
    project: str = "",
    substitute: bool = False,
    add_missing: bool = False,
) -> Plan:
    """Every action of one code, and what putting `new_value` in one of its arguments would do.

    `match` narrows by what the argument holds NOW: blank means every action of this code,
    anything else means only those whose value contains it.  Case-insensitively, which is
    how the Find tab already searches -- two halves of one dialog answering the same words
    differently would be a trap.

    `substitute` changes what `new_value` means:

      off (the default)  the argument is SET to it -- "make every Flash say 'Done'".
      on                 only the matched text inside the value is replaced -- "wherever a
                         URL says http://old, say http://new" -- leaving the rest of each
                         value alone.  Needs `match`: there is otherwise nothing to look
                         for.

    `add_missing` writes the argument into the actions that do not carry one.  Tasker
    leaves out an argument nobody has ever set, so "give every Flash a two-second Timeout"
    is mostly a question about actions that have no Timeout element at all -- and without
    this it answered "12 of them cannot be changed".  Off by default, because adding an
    argument to a hundred actions is a bigger thing than editing the ones that have it, and
    those rows carry a note saying which they are.

    It only applies to the plain case: a value filter cannot match a field that does not
    exist, and there is nothing inside a missing value to substitute, so with either of
    those set the switch says so rather than quietly doing nothing.

    Nothing is done here.  Every action found becomes a Change carrying the field's value
    before and after, ticked individually; every action that matched and cannot be changed
    becomes a Skip carrying the reason.
    """
    action = action_codes.get(action_key)
    action_name = action.name if action else action_key
    argument = next((entry for entry in _effective_args(action_key) if entry.arg_id == arg_id), None)
    arg_name = (argument.arg_name if argument else "") or f"arg{arg_id}"

    what = (
        f"Replace '{match}' with '{new_value}' in {action_name} {arg_name}"
        if substitute
        else f"Set {action_name} {arg_name} to '{new_value}'"
    )
    if match and not substitute:
        what = f"{what}, where it contains '{match}'"
    if project:
        what = f"{what} in Project '{project}'"
    plan = Plan(what=what)

    # The same scope note the other two carry, and for the same reason: `what` is the Undo
    # label, so a plan that touched one Task must not describe itself as touching the file.
    scope = current_scope()
    if not scope.is_everything:
        plan.what = f"{what} in {scope.phrase}"
        plan.warnings.append(
            f"Limited to {scope.phrase}, which is what the app is displaying.  Clear the single-item "
            f"selection to replace across the whole configuration.",
        )

    if argument is None:
        plan.warnings.append(f"'{action_name}' has no argument {arg_id}.")
        return plan
    if _category(argument) not in _WRITABLE_CATEGORIES:
        plan.warnings.append(
            f"{arg_name} is {_category(argument)}: chosen from a picker rather than typed, so there is "
            f"no value here to replace.",
        )
        return plan
    if substitute and not match:
        plan.warnings.append("Replacing text inside a value needs the text to look for.")
        return plan

    numeric = _category(argument) in ("Int", "Boolean")
    refusal = _numeric_refusal(numeric, new_value)

    adding = add_missing and not match and not substitute
    if add_missing and not adding:
        plan.warnings.append(
            "An argument can only be ADDED where nothing is being matched: a value filter cannot match a "
            "field that does not exist, and there is nothing inside a missing value to replace.",
        )

    pattern = re.compile(re.escape(match), re.IGNORECASE) if substitute else None
    wanted = match.lower()
    detail = f"{action_name}, {arg_name}="
    index = mapfind.build_index()
    code = action_key[:-1]
    added = 0

    for record in index.objects:
        if record.kind != TASK:
            continue
        if project and record.project != project:
            continue
        for found in record.actions:
            if found.code != code or found.element is None:
                continue
            where = record.target.at_action(found.number)
            site, reason = _argument_site(found.element, arg_id, where, detail)
            if site is None:
                # An argument the action never set.  Written into it when the user asked
                # for that, and otherwise reported: it is exactly the action they meant to
                # change and did not, so it says so and says what to tick.
                if not adding:
                    # Reported only when nothing was filtering.  A value filter cannot rule
                    # out a field there is nothing to read, so with one set these would be
                    # noise; without one, they are the ones the user did not get.
                    if not wanted:
                        plan.skips.append(
                            Skip(
                                where=where,
                                reason=BLOCKED_UNADDABLE,
                                explanation=f"{reason}  Tick 'Add it where missing' to write one in.",
                            ),
                        )
                    continue
                if refusal:
                    plan.skips.append(Skip(where=where, reason=BLOCKED_UNADDABLE, explanation=refusal))
                    continue
                if not _creatable(found.element, arg_id):
                    plan.skips.append(
                        Skip(
                            where=where,
                            reason=BLOCKED_UNADDABLE,
                            explanation="this argument cannot be written from nothing -- it is not a plain value.",
                        ),
                    )
                    continue
                added += 1
                plan.changes.append(
                    Change(
                        site=Site(
                            kind=NEW_ARG,
                            element=found.element,
                            where=where,
                            detail=detail,
                            new_value=new_value,
                            create_arg=(action_key, arg_id),
                        ),
                        before="",
                        after=new_value,
                        note=f"this action has no {arg_name} -- one is added",
                    ),
                )
                continue

            before = _current_value(site)
            if wanted and wanted not in before.lower():
                continue

            if refusal and not substitute:
                plan.skips.append(Skip(where=where, reason=BLOCKED_UNADDABLE, explanation=refusal))
                continue

            site = Site(
                kind=site.kind,
                element=site.element,
                where=where,
                detail=detail,
                new_value=None if substitute else new_value,
                rename=(pattern, new_value) if substitute else (),
            )
            after = _rewrite_site(site, pattern, new_value)[1]
            if after == before:
                continue  # Already holds it: a change that would change nothing.
            plan.changes.append(Change(site=site, before=before, after=after))

    plan.selected = set(range(len(plan.changes)))
    if added:
        plan.warnings.append(
            f"{added} of these ADD a {arg_name} to an action that never had one, rather than changing "
            f"one it has.  Each says so on its own row.",
        )
    if plan.changes and not wanted and not substitute:
        plan.warnings.append(
            f"Every {action_name} in scope gets the same {arg_name} -- {len(plan.changes)} of them.  "
            f"Narrow it with the value filter if that is more than you meant.",
        )
    return plan


# ##################################################################################
# Variable for variable.
#
# Textual, and therefore easy to get 95% right and hard to get right.  Four things
# below are each individually capable of quietly corrupting a configuration, and each
# is handled here rather than left to the user to notice.
# ##################################################################################

# 1. BOUNDARY.  '%Time' must not match inside '%TimeStamp', and str.replace does exactly
#    that.  varxref.VARIABLE_PATTERN already knows what a name is; this anchors on the
#    whole name and refuses a partial.  The trailing lookahead is the entire point.
# Passed as `owner` to mean "every instance of this name", as against one particular
# instance.  None rather than "" because "" is already a real owner -- varxref keys
# everything that is not a Task's local under it -- so the two must not be the same value.
EVERY_INSTANCE = None


def _rename_pattern(old_name: str) -> re.Pattern:
    """A pattern matching this name and nothing that merely starts with it.

    Also matches the subscripted and member forms, which are the same variable:
    '%Row(3)', '%Row(%i)' and '%Row.length' all name %Row and all keep their suffix.
    """
    return re.compile(rf"%{re.escape(old_name.lstrip('%'))}(?![A-Za-z0-9_])")


# 2. SCOPE.  Tasker scopes a variable by its SPELLING: all lower case is local to the
#    running Task, anything with a capital is global.  Two consequences, and the second
#    one is the one that bites:
#
#      A local is one variable PER TASK.  varxref keys them (name, owner) for this
#      reason and its own note counts 525 of 1523 local names appearing in more than one
#      Task in a real backup.  Renaming '%i' file-wide would rewrite a few hundred
#      unrelated loop counters.  So a rename of a local takes the OWNER as well as the
#      name and never leaves that Task.
#
#      Changing the case CHANGES THE SCOPE.  '%counter' -> '%Counter' is not a rename,
#      it is a promotion from local to global, and it silently makes every Task that
#      used its own %counter share one.  Detected and warned about explicitly; not
#      blocked, because promoting a local to a global on purpose is a real thing to want.
#
# 3. COLLISION.  If the new name is already in use, this is a MERGE, not a rename: two
#    variables become one, and everything that read the old one now reads whatever the
#    other one happens to hold.  Warned about with the existing name's own set/read
#    counts, so 'and %Count is already set in 4 places and read in 19' is on screen
#    before the button is pressed.
#
# 4. WHAT IS NOT REWRITABLE.  varxref.indirect_references counts the actions that build
#    their target name at run time ('Variable Set %(%which)').  Any of them could be
#    touching this variable and none of them can be rewritten.  They become Skips with
#    BLOCKED_INDIRECT, listed with their Targets so the user can go and read them.


def plan_variable_rename(
    index: varxref.VariableIndex,
    old_name: str,
    owner: str | None,
    new_name: str,
) -> Plan:
    """Every place this variable is set or read, and what renaming it would do.

    (old_name, owner) is varxref's own key: owner is the Task id for a local, "" for a
    global.  Naming the instance is what makes the local case safe by default -- %i is a
    different variable in each of the 59 Tasks that use it, and a rename that took only a
    name would rewrite all 59 the first time somebody meant one.

    Pass EVERY_INSTANCE as the owner to mean exactly that, on purpose: every instance of
    the name in scope, however many Tasks they belong to.  "Rename the loop counter
    throughout" is a real thing to want and the only way to say it -- but it is spelled
    differently from the safe case rather than reachable by leaving an argument out.

    Sites come from index.variables[(old_name, owner)].sets + .reads, which is one list
    of every place the cross-reference already knows about: Task arguments, plugin
    Bundles, action and Profile conditions, Legacy and Version 2 Scene bindings, and the
    top-level <Variable> declaration.  That last one is why a rename cannot be done by
    walking Tasks alone: leaving the declaration behind orphans the value in Tasker's
    Variables tab.

    Refuses outright, rather than warning:
      - a new name that is not a legal Tasker name (VARIABLE_PATTERN must match the whole)
      - a built-in (%BATT, %TIME) as either side; Tasker owns those
      - a name of one or two characters, either side.  varxref holds these out of its own
        totals as low-confidence for good reason: '%d' matches a strftime format inside a
        Parse/Format DateTime and a printf escape inside a Run Shell, and a rename that
        rewrote those would break a Task in a way no reading of the Map would reveal.

    Warns, and proceeds:
      - the scope change of item 2 above
      - the merge of item 3
      - a Tasker-set name (%par1, %err): renaming the reference does not rename what
        Tasker sets, so the new name is simply never populated.
    """
    old_name = f"%{old_name.lstrip('%')}"
    new_name = f"%{new_name.lstrip('%')}"

    entries = _entries_to_rename(index, old_name, owner)

    scope_phrase = ""
    if owner is EVERY_INSTANCE and len(entries) > 1:
        scope_phrase = f" ({len(entries)} instances)"
    elif owner:
        location = index.scope_locations.get(owner)
        scope_phrase = f" in {location.label}" if location else f" in Task {owner}"
    plan = Plan(what=f"Rename {old_name} to {new_name}{scope_phrase}")

    # Worth more here than on a swap.  A rename that stops at the scope's edge leaves the
    # configuration half-renamed -- the places inside still read the new name, the places
    # outside still read the old one -- and unlike a swap, that is a broken configuration
    # rather than a partly-done job.  So it is said as a warning, not just in the title.
    displaying = current_scope()
    if not displaying.is_everything:
        plan.warnings.append(
            f"Limited to {displaying.phrase}, which is what the app is displaying.  Uses of {old_name} "
            f"anywhere else keep the old name -- which for a GLOBAL means the two halves stop agreeing.  "
            f"Nor can {new_name} be checked for a clash outside this scope.  "
            f"Clear the single-item selection to rename across the whole configuration.",
        )

    refusal = _rename_refusal(old_name, new_name)
    if refusal:
        plan.warnings.append(refusal)
        return plan

    if not entries:
        # "in this configuration" would be a lie under a scope -- the variable may be used
        # in a hundred places the scan was told not to look at.
        where = displaying.phrase if not displaying.is_everything else "this configuration"
        plan.warnings.append(f"{old_name} is not used anywhere in {where}.")
        return plan

    plan.warnings.extend(_rename_warnings(index, entries, old_name, new_name, owner))

    pattern = _rename_pattern(old_name)
    seen: set[tuple[int, tuple]] = set()

    # sets before reads, and both in scan order, so the preview reads down the file the
    # way the Map does.  Deduplicated on (element, path) because one field can be recorded
    # twice over: an in-place action records its target as a set AND a read, and a field
    # naming the variable more than once is one field to rewrite either way.
    for reference in [ref for entry in entries for ref in entry.sets + entry.reads]:
        if reference.element is None:
            plan.skips.append(
                Skip(
                    where=reference.target,
                    reason=BLOCKED_INDIRECT,
                    explanation=(
                        f"{reference.detail} -- this action produces {old_name} without naming it anywhere, "
                        f"so there is nothing here to rewrite."
                    ),
                ),
            )
            continue

        if _is_plugin_declaration(reference.element):
            plan.skips.append(
                Skip(
                    where=reference.target,
                    reason=BLOCKED_INDIRECT,
                    explanation=(
                        "this is the plugin's own declaration of the variables it produces, not a use of "
                        f"{old_name} -- renaming it here would not change what the plugin sets."
                    ),
                ),
            )
            continue

        key = (id(reference.element), reference.path)
        if key in seen:
            continue
        seen.add(key)

        site = Site(
            kind=_site_kind(reference),
            element=reference.element,
            where=reference.target,
            detail=reference.detail,
            path=reference.path,
            rename=(pattern, new_name),
        )
        before, after = _rewrite_site(site, pattern, new_name)
        if before == after:
            continue  # The name is in this field's record but not in this particular value.
        plan.changes.append(Change(site=site, before=before, after=after))

    declaration = _declaration_site(old_name, entries, (pattern, new_name))
    if declaration is not None:
        before, after = _rewrite_site(declaration, pattern, new_name)
        if before != after:
            plan.changes.append(Change(site=declaration, before=before, after=after))

    if index.indirect_references:
        plan.warnings.append(
            f"{index.indirect_references} actions in this configuration build the name of the variable they "
            f"set at run time ('Variable Set %(%which)').  Any of them could be setting {old_name}, and none "
            f"of them can be rewritten -- check them by hand.",
        )

    plan.selected = set(range(len(plan.changes)))
    return plan


def _entries_to_rename(
    index: varxref.VariableIndex,
    old_name: str,
    owner: str | None,
) -> list[varxref.Variable]:
    """The variable record(s) this rename covers -- one instance, or every one of the name.

    Ordered as varxref found them, so a plan over several instances still reads down the
    file the way the Map does rather than jumping between Tasks.
    """
    if owner is not EVERY_INSTANCE:
        entry = index.variables.get((old_name, owner))
        return [entry] if entry is not None else []
    return [entry for (name, _owner), entry in index.variables.items() if name == old_name]


def _rename_refusal(old_name: str, new_name: str) -> str:
    """Why this rename must not be attempted at all, or "" if it may be.

    Refusals rather than warnings, because each of these produces a configuration that is
    wrong in a way no reading of the Map would reveal.
    """
    if not VARIABLE_PATTERN.fullmatch(new_name):
        return (
            f"'{new_name}' is not a name Tasker would accept.  A variable name begins with a letter and "
            f"continues with letters, digits and underscores."
        )

    # globalvr's list carries the leading '%', so these are compared whole.  Getting that
    # wrong is silent: every built-in passes the test and %BATT becomes renameable.
    for name, side in ((old_name, "renamed"), (new_name, "renamed to")):
        if name in tasker_global_variables:
            return f"{name} is one of Tasker's own built-in variables and cannot be {side}."
        if len(name) - 1 <= _LOW_CONFIDENCE_LENGTH:
            # varxref holds these out of its own totals for the same reason.
            return (
                f"{name} is too short to rename safely.  A name this short collides with things that are not "
                f"variables at all -- a strftime letter in a Parse/Format DateTime, a printf escape in a Run "
                f"Shell, a '%' wildcard in a SQL Query -- and rewriting one of those would break a Task in a "
                f"way nothing in the Map would show."
            )

    if old_name == new_name:
        return "The old and new names are the same."
    return ""


def _rename_warnings(
    index: varxref.VariableIndex,
    entries: list[varxref.Variable],
    old_name: str,
    new_name: str,
    owner: str | None,
) -> list[str]:
    """What the user should read before pressing Replace.  Each of these proceeds."""
    warnings = []

    # Renaming every instance of a LOCAL is the case that needs saying out loud.  Each of
    # those instances is a separate variable -- Tasker scopes a lower-case name to the
    # running Task -- so this is not one rename but as many as there are Tasks, and the
    # count is the only thing on screen that says how far it reaches.
    locals_covered = [entry for entry in entries if entry.scope == varxref.LOCAL]
    if owner is EVERY_INSTANCE and len(locals_covered) > 1:
        where = ", ".join(
            (index.scope_locations[entry.owner].label if entry.owner in index.scope_locations else entry.owner)
            for entry in locals_covered[:3]
        )
        warnings.append(
            f"{old_name} is a LOCAL, so these are {len(locals_covered)} separate variables, one per Task "
            f"({where}{', ...' if len(locals_covered) > 3 else ''}).  Every one of them is renamed.",
        )

    # A scope change.  Tasker scopes by SPELLING, so this is not cosmetic: '%counter' ->
    # '%Counter' promotes a variable that was private to each Task into one global that
    # every Task then shares.  A real thing to want, and never a thing to do by accident.
    was, becomes = varxref.scope_of(old_name), varxref.scope_of(new_name)
    if was != becomes:
        warnings.append(
            f"This changes the variable's SCOPE, not just its name: {old_name} is {was} and {new_name} would "
            f"be {becomes}.  Tasker decides scope from the spelling -- all lower case is local to the running "
            f"Task, anything with a capital is global.",
        )

    # The target already exists.  Said plainly rather than as an alarm: picking an
    # existing variable is a supported thing to do -- "everywhere this Task says
    # %app_name, say %app_package" consolidates two variables into one, and the target
    # pulldown offers exactly these.  What the user still has to be told is the
    # consequence, because it is not what the word "rename" suggests.
    # Looked up per instance when every instance is in play: a local's target is keyed to
    # the same Task, so "does %tally already exist" has a different answer in each of them
    # and the first one that says yes is worth reporting.
    if becomes == varxref.LOCAL:
        owners = [entry.owner for entry in entries] if owner is EVERY_INSTANCE else [owner]
        existing = next(
            (found for key in owners if (found := index.variables.get((new_name, key))) is not None),
            None,
        )
    else:
        existing = index.variables.get((new_name, ""))
    if existing is not None:
        warnings.append(
            f"{new_name} already exists -- set in {len(existing.sets)} places and read in "
            f"{len(existing.reads)}.  This MERGES the two rather than renaming one: afterwards there is a "
            f"single variable, and everything that read {old_name} reads whatever {new_name} holds.",
        )

    # Something produces it that this rename cannot reach.
    producers = {reference.detail for entry in entries for reference in entry.sets if reference.element is None}
    if producers:
        warnings.append(
            f"{old_name} is produced by an action that never names it ({', '.join(sorted(producers)[:3])}).  "
            f"That action will go on producing {old_name}, so after this rename nothing will set {new_name}.",
        )

    # Tasker-set (%par1, %err) and the built-in SHAPE both mean "something outside this
    # file puts the value there".  The documented built-ins are refused outright; this
    # catches the ones varxref recognises by shape alone -- globalvr's list was transcribed
    # from a page that predates %HUMIDITY, %SDK and the %DEV*/%CAL* families -- where a
    # refusal would be wrong, since the same shape covers somebody's own SHOUTING global.
    outside_scopes = {entry.scope for entry in entries} & {varxref.TASKER_SET, varxref.BUILTIN}
    if outside_scopes:
        source = "Tasker itself as a Task runs" if varxref.TASKER_SET in outside_scopes else "Tasker, by the look of it"
        warnings.append(
            f"{old_name} is set by {source}.  Renaming the places that read it does not change what sets it, "
            f"so {new_name} would never hold anything.  Ignore this if {old_name} is your own variable.",
        )

    return warnings


def _is_plugin_declaration(element: defusedxml.ElementTree.Element) -> bool:
    """Whether this Bundle entry is a plugin declaring its OUTPUT variables.

    A plugin lists what it produces in a RELEVANT_VARIABLES entry, which varxref reads to
    work out what sets %http_data and its like.  It is metadata about the plugin, not a
    use of the user's variable, and 4313 of them sit in one real backup -- rewriting them
    would edit the plugin's description of itself while changing nothing about what it
    actually sets.
    """
    return element.tag.endswith("RELEVANT_VARIABLES")


def _site_kind(reference: varxref.Reference) -> str:
    """Which sort of field a reference sits in -- for the preview's wording, and for the
    one case (_write_site) where the rewrite genuinely differs.
    """
    if reference.path:
        return V2_SCENE
    if reference.element.tag in ("lhs", "rhs"):
        return CONDITION
    if reference.element.tag == "var":
        return INT_VAR
    # A Project's or Profile's own declaration of a variable to configure on import: the
    # name in <pvn>, the value offered for it in <pvv>.  Named rather than left to fall
    # through to BUNDLE below: the preview prints the kind, and "bundle" would tell the
    # user this rename is touching a plugin's payload when it is touching the Project's
    # properties.
    if reference.element.tag in ("pvn", "pvv"):
        return IMPORT_VARIABLE
    if reference.element.tag == "Str":
        return LEGACY_SCENE if "component" in reference.detail or "value" in reference.detail else STR_ARG
    return BUNDLE


def _declaration_site(old_name: str, entries: list[varxref.Variable], rename: tuple) -> Site | None:
    """The top-level <Variable> that declares this name, if the file carries one.

    Why a rename cannot be done by walking Tasks alone: Tasker's Variables tab holds the
    declaration and its value, and leaving it behind orphans the value under a name
    nothing uses any more.
    """
    if not any(entry.declared for entry in entries) or PrimeItems.xml_root is None:
        return None

    # Only when the whole configuration is in play.  A <Variable> is a file-level object,
    # not part of any Project/Profile/Task/Scene, so it is not inside the one object a
    # scoped run was told to touch -- and renaming it from inside a single Task would
    # rename Tasker's Variables tab entry out from under every OTHER Task still using the
    # old name.  A scoped rename is partial by the user's own choice; this keeps it
    # partial in the safe direction.
    if not current_scope().is_everything:
        return None
    for element in PrimeItems.xml_root.findall("Variable"):
        children = list(element)
        if children and (children[0].text or "").strip() == old_name:
            return Site(
                kind=DECLARATION,
                element=children[0],
                where=Target(kind=VARIABLE, key=old_name, name=old_name),
                detail="Tasker's Variables tab",
                rename=rename,
            )
    return None


def _current_value(site: Site) -> str:
    """What this field holds now, whichever shape it holds it in.

    The odd one out is INT_VALUE: Tasker writes a plain numeric argument as an ATTRIBUTE
    (<Int sr="arg1" val="7"/>) and everything else in this module as element text, so a
    single .text read would report every numeric argument as empty and then replace an
    empty string with the new value -- which would look right in the preview and write
    nothing anybody could see.
    """
    if site.kind == NEW_ARG:
        # Nothing holds it yet.  Read off site.element and this would be the <Action>'s own
        # text -- the whitespace before its first child -- shown to the user as the value
        # they are about to replace.
        return ""
    if site.kind == INT_VALUE:
        return site.element.attrib.get("val", "")
    return site.element.text or ""


def _set_value(site: Site, value: str) -> None:
    """Put a value into this field, in the shape the field keeps it in.  The write half of
    _current_value, and the reason the two sit together."""
    if site.kind == NEW_ARG:
        _create_argument(site, value)
        return
    if site.kind == INT_VALUE:
        site.element.set("val", value)
        return
    site.element.text = value


def _create_argument(site: Site, value: str) -> None:
    """Write an argument the action has never carried, and put the value in it.

    Built through taskedit.build_synthesized_args -- the same function Add Action uses, and
    the same one _swap_one_action synthesizes a whole argument set with -- so an argument
    added here is indistinguishable from one Tasker itself wrote: <Str sr="argN" ve="3"> for
    text, <Int sr="argN" val="0"/> for a number or a checkbox.  A second definition of "what
    an empty argument looks like" is exactly the thing that goes stale.

    No action key is passed, which is deliberate: given one, that function also writes the
    plugin payload <Bundle> for the action, and this is adding one argument to an action
    that already has whatever payload it came with.

    Raises rather than returning quietly if nothing was built -- apply() catches it and
    reports that one change, which is the right outcome for an argument that turns out not
    to be synthesizable after the preview said it was.
    """
    action_key, arg_id = site.create_arg
    argument = next((entry for entry in _effective_args(action_key) if entry.arg_id == arg_id), None)
    if argument is None:
        unbuildable = f"{action_key} has no argument {arg_id} to add"
        raise ValueError(unbuildable)

    built = taskedit.build_synthesized_args(type(site.element), site.element, [argument])
    if not built or built[0].element is None:
        unbuildable = f"an argument of this kind cannot be written from nothing ({site.detail})"
        raise ValueError(unbuildable)

    element = built[0].element
    if element.tag == "Int":
        element.set("val", value)
    else:
        element.text = value
    # In the order Tasker writes them, rather than appended at the end.  See _order_children.
    _order_children(site.element)


def _rewrite_site(site: Site, pattern: re.Pattern | None = None, new_name: str = "") -> tuple[str, str]:
    """(before, after) for one site, without writing anything.  The read half of apply().

    Per-kind, because a value does not live in the same place twice:
      STR_ARG        element.text
      INT_VAR        element.find('var').text
      CONDITION      the <lhs>/<rhs> child named in site.detail
      BUNDLE         element.text, anywhere under the <Bundle>
      LEGACY_SCENE   the <Str sr="argN"> named in site.detail
      V2_SCENE       site.path into the parsed JSON layout, re-serialized on write
      DECLARATION    the <Variable>'s name child
      IMPORT_VARIABLE the <pvn> element's own text
      INT_VALUE      the <Int>'s val= attribute

    A Version 2 Scene is the one that is not a string swap: the layout is gzipped JSON, so
    the value has to be decoded, changed at site.path and re-encoded.  Not batched per
    Scene -- each site decodes the layout as it now stands, so two changes to one Scene
    compose correctly; it costs a decode and an encode each, on the handful of V2 Scenes a
    configuration has.
    """
    if site.kind == V2_SCENE:
        value = _v2_value(site)
        return _flatten(value), _flatten(_substitute(value, pattern, new_name))

    before = _current_value(site)
    # A whole value replaced, rather than something matched inside it.  Checked first
    # because such a Site carries no pattern at all: what it is going to hold does not
    # depend on what it holds now.
    if site.new_value is not None:
        return before, site.new_value
    return before, pattern.sub(new_name, before)


def _substitute(value: object, pattern: re.Pattern, new_name: str) -> object:
    """The value with every whole-name match rewritten, at whatever depth it sits.

    Recursive because a V2 property is not always a string: a component's value can be a
    dict or a list of them, which is why varxref._v2_strings has to recurse to FIND the
    names.  Anything that is not a string, dict or list is returned as it stands -- a
    number or a boolean cannot hold a variable name.
    """
    if isinstance(value, str):
        return pattern.sub(new_name, value)
    if isinstance(value, dict):
        return {key: _substitute(item, pattern, new_name) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, pattern, new_name) for item in value]
    return value


def _flatten(value: object) -> str:
    """One line of preview text for a value that may not be a string."""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _v2_layout_and_node(site: Site) -> tuple[object, dict | None, str]:
    """(the decoded layout, the component the site points at, the property key).

    Decoded fresh every time.  The layout a plan was built from is long gone by the time
    anything is applied, and would be the wrong object to write into even if it were not:
    what is on disk is the <lj> of the element, and that is what has to be edited.
    """
    from maptasker.src import sceneedit  # noqa: PLC0415

    layout = sceneedit.decode_v2_layout(site.element)
    if layout is None:
        return None, None, ""
    node_path, key = site.path
    return layout, sceneedit.v2_node_at(layout, node_path), key


def _v2_value(site: Site) -> object:
    """The current value of the property a V2 site points at."""
    _, node, key = _v2_layout_and_node(site)
    return node.get(key) if node is not None else ""


# ##################################################################################
# Preview, and then -- separately -- apply.
# ##################################################################################
def report_rows(plan: Plan) -> list[Row]:
    """The plan as mapjump Rows: skips first, then changes grouped by Project and Task.

    Skips first because they are the part the user must read and the part they will not
    scroll back up for.  Rows rather than a string so the preview is clickable in the Map
    the same way a health-check finding is -- which for this feature is not a nicety: the
    only way to judge 'should this one be changed' is to go and look at it.
    """
    rows: list[Row] = [Row(plan.what), Row("")]

    rows.extend(Row(f"  {warning}") for warning in plan.warnings)

    if plan.skips:
        rows.extend((Row(""), Row(f"CANNOT BE CHANGED ({len(plan.skips)})")))
        for skip in plan.skips:
            rows.append(Row(f"  {skip.where.label}", skip.where))
            rows.append(Row(f"      {skip.explanation}"))

    if not plan.changes:
        rows.extend((Row(""), Row("Nothing to change.")))
        return rows

    rows.extend((Row(""), Row(f"WOULD CHANGE ({len(plan.selected)} of {len(plan.changes)} ticked)")))

    # Grouped by Project, in the order the objects came out of the index, so the list reads
    # in the same order as the Map the user is about to click into.
    current_project = None
    for position, change in enumerate(plan.changes):
        project = change.site.where.project
        if project != current_project:
            current_project = project
            rows.append(Row(f"  Project '{project}'" if project else "  No Project"))
        tick = "[x]" if position in plan.selected else "[ ]"
        rows.append(Row(f"    {tick} {change.site.where.label}", change.site.where))
        rows.append(Row(f"        {change.before}  ->  {change.after}"))
        if change.note:
            rows.append(Row(f"        {change.note}"))

    return rows


def write_swap_report(rows: list[Row]) -> str:
    """Save the preview as text, the way varxref and mapfind save theirs.

    Worth having for the plan the user did NOT apply as much as the one they did: a
    hundred-row preview is a work list, and 'which ones did I decide to leave' does not
    survive closing the dialog otherwise.
    """
    stamp = datetime.now().strftime("_%m-%d-%Y_%H-%M-%S")  # noqa: DTZ005
    file_name = append_to_filename(SWAP_FILE, stamp)
    if not file_name:
        return ""
    try:
        with open(os.path.join(os.getcwd(), file_name), "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Replace report could not be written: {error}")
        return ""
    return file_name


def apply(plan: Plan) -> tuple[int, list[str]]:
    """Make the selected changes.  Returns (how many were made, errors).

    ONE undo block around the whole thing, and the outermost one:

        with sessundo.undoable(plan.what):
            ...

    A rename touching 60 sites is one thing the user did.  sessundo is re-entrant
    precisely so that a bulk operation calling per-item mutators still costs one press of
    Undo -- the same reason delete-a-Project does not cost ten -- and its render-and-
    compare means a plan whose every change was unticked leaves no entry behind.

    Re-checks each site is still attached to the tree before writing (BLOCKED_DETACHED):
    the preview can sit on screen while the user edits a Task in another dialog, and an
    element deleted underneath a plan must not be resurrected by writing to it.

    Order within the block matters in one case only: a variable rename must rewrite the
    <Variable> declaration LAST.  If it goes first and something later raises, the file
    holds a declaration for a name nothing uses and no declaration for the name
    everything uses -- the one intermediate state that survives as a plausible-looking
    configuration.
    """
    changes = [change for position, change in enumerate(plan.changes) if position in plan.selected]
    if not changes:
        return 0, []

    errors: list[str] = []
    changed = 0

    # The declaration goes last.  Ordering by kind rather than by leaving the caller to
    # order the list, so that a plan assembled in any order still applies in a safe one.
    changes.sort(key=lambda change: change.site.kind == DECLARATION)

    attached = _attached_elements()

    with sessundo.undoable(plan.what):
        for change in changes:
            if id(change.site.element) not in attached:
                errors.append(
                    f"{change.site.where.label}: no longer in the configuration -- it was deleted or "
                    f"reloaded while this preview was open.  Skipped.",
                )
                continue
            try:
                _apply_one(change)
            except (AttributeError, KeyError, ValueError) as failure:
                errors.append(f"{change.site.where.label}: {failure}")
                continue
            changed += 1

    return changed, errors


def _attached_elements() -> set[int]:
    """The id() of every element currently reachable from the loaded configuration.

    By identity rather than by re-finding each site: a Site holds the element itself, and
    the question being asked is whether THAT element is still in the tree, which no search
    by name or number can answer -- a Task deleted and another added in its place would
    match by every describable property and be a different object.

    Rebuilt once per apply() rather than per site, since it walks the whole tree.

    Walked from the ROOT, not from the Project/Profile/Task/Scene tables.  The tables were
    the obvious place to start and are the wrong one: a top-level <Variable> -- Tasker's
    Variables tab, and the declaration every rename has to move -- sits beside those
    objects rather than inside any of them, so a walk of the tables alone declares it
    detached and every rename silently loses its declaration.  The root is what "still in
    the configuration" actually means.
    """
    root = PrimeItems.xml_root
    if root is not None:
        return {id(element) for element in root.iter()}

    # No root parsed: fall back to the tables, so a caller holding only those is still
    # checked rather than waved through.
    reachable: set[int] = set()
    for tag in ("all_projects", "all_profiles", "all_tasks", "all_scenes"):
        for item in (PrimeItems.tasker_root_elements.get(tag) or {}).values():
            element = item.get("xml") if isinstance(item, dict) else item
            if element is None:
                continue
            reachable.update(id(descendant) for descendant in element.iter())
    return reachable


def _apply_one(change: Change) -> None:
    """Perform one planned change.  Raises rather than reporting; apply() catches."""
    if change.site.kind == ACTION_ELEMENT:
        _swap_one_action(change.site.element, change.site.new_key, change.site.carry)
        return
    if change.site.kind == PROFILE_CONDITION:
        _swap_one_condition(change.site.element, change.site.new_key, change.site.carry)
        return
    _write_site(change.site)


def _write_site(site: Site) -> None:
    """Rewrite one field in place -- the write half of _rewrite_site.

    Takes no value: the Site carries the pattern and the new name, so what gets written is
    computed here from what the field holds NOW rather than from what it held when the
    plan was built.  That is what makes two renames touching one field compose, and what
    stops a stale preview value being written over a field somebody edited meanwhile.
    """
    if site.new_value is not None:
        _set_value(site, site.new_value)
        return

    pattern, new_name = site.rename

    if site.kind == V2_SCENE:
        from maptasker.src import sceneedit  # noqa: PLC0415

        layout, node, key = _v2_layout_and_node(site)
        if node is None or key not in node:
            # A layout that will not decode, or a path that no longer resolves.  Left
            # alone rather than rebuilt, for the reason decode_v2_layout gives: a layout
            # that cannot be read certainly should not be re-encoded over the original.
            unreachable = f"the Version 2 layout of {site.where.label} could not be read"
            raise ValueError(unreachable)
        node[key] = _substitute(node[key], pattern, new_name)
        sceneedit.encode_v2_layout(site.element, layout)
        return

    _set_value(site, pattern.sub(new_name, _current_value(site)))


# ##################################################################################
# Where this hangs off the GUI -- guiwins.py, not here.  Sketched as prose because the
# module has to stay GUI-free; the code goes in find_event.
# ##################################################################################
def caller_sketch() -> None:
    """Replace is a second TAB inside the existing Find dialog, not a dialog of its own.

    find_event (guiwins.py ~8962) currently opens one ui.dialog holding one ui.card of
    pickers.  It grows a ui.tabs()/ui.tab_panels() pair -- "Find" and "Replace" -- and the
    Replace panel is built from the same `index` the Find panel already built:

        index = mapfind.build_index()          # unchanged, still per-open, still shared
        with ui.dialog() as dialog, ui.card()...:
            with ui.tabs() as tabs:
                find_tab = ui.tab(translate_string("Find"))
                replace_tab = ui.tab(translate_string("Replace"))
            with ui.tab_panels(tabs, value=find_tab):
                ...the existing pickers, unchanged...
                ...the Replace panel...

    THREE THINGS THIS BUYS, which is why it is a tab rather than a dialog:

    The index is built once for both.  find_event's own docstring explains why it is
    rebuilt on every open and not cached on the view -- 60ms, and a cached one keeps
    offering an action of a Task that has been deleted.  A separate Replace dialog would
    pay that a second time and, worse, could be opened alongside a Find holding an index
    from before an edit.  One dialog, one index, one answer about what is in the file.

    The source pulldown is the Find dialog's action pulldown, unchanged.  Same entries,
    same counts, built from index.choices(mapfind.ACTION) -- so "Flash (37)" means the
    same thing on both tabs, and the count doubles as the number of actions a swap would
    touch before any preview is run.

    Find becomes the way into Replace.  The natural move is to look for something, see
    the 37 places it is, and then decide to change them; switching tabs keeps the
    Project narrowing and the action already chosen, so that is one click rather than
    re-entering the query in a second window.

    THE PROBLEM THE TAB CREATES, AND WHAT IT COSTS TO FIX

    jump_to closes the dialog before jumping, and must -- the dialog is modal, so a jump
    behind it scrolls a view the user cannot see.  On the Find tab that is free: the query
    is remembered on the view (self._find_query) and pressing Find again returns to the
    same list.  On the Replace tab it destroys the Plan, and a Plan cannot be remembered
    the way a Query can: its Sites hold live elements, and holding them across a dialog
    that may have been reopened after another edit is precisely the stale-handle bug
    apply()'s BLOCKED_DETACHED check exists to catch.

    So the view remembers the INPUTS, not the Plan:

        self._replace_inputs: tuple[str, str, str] | None    # old key, new key, project

    and reopening the dialog restores the fields and rebuilds the Plan from scratch.  That
    is a second plan() -- one pass over the file, the same order as a Find -- and it is
    worth paying every time, because it makes the rule below true by construction rather
    than by the dialog remembering to enforce it.

    THE RULE THE WHOLE DESIGN IS ARRANGED AROUND

    The Replace button is disabled until a preview exists for the values currently in the
    fields, and changing any field clears the preview and disables it again.  A user
    cannot apply a plan they have not seen, because there is no path through the widgets
    that reaches apply() without report_rows() having been drawn first.  Everything else
    here -- the separate plan()/apply(), the unticked RESET rows, the skips pinned above
    the changes -- is a way of making sure that what they saw was the truth.

    Two smaller things the tab inherits for free: from_diagram, so a Replace run from the
    Diagram previews with Diagram-preferred jumps exactly as a Find does, and
    translate_string on every label, since the Replace panel is new user-facing text and
    the rest of this dialog is already translated.
    """
