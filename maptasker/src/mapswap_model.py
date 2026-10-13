"""mapswap_model: what a bulk replace is made of -- the Site, Change, Skip and Plan every operation builds, and what the four operations share.

The four operations (action swap, condition swap, argument replace, variable rename) and the apply that
carries a Plan out are described in mapswap's header; the rules there (nothing is applied unseen, one scanner,
one undo, only what is on screen) are what this vocabulary exists to serve."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src import taskedit_model
from maptasker.src.actionc import ArgumentCode, action_codes
from maptasker.src.mapjump import Target, current_scope

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

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
    element: Element
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


# How much of the old action survives, worst last.  Shown per candidate target in the
# pulldown and again per Task in the preview, because 'replace Flash with Notify' means
# something very different at each level and the user is the only one who knows which
# they wanted.
EXACT = "exact"  # every argument carried: same names, same types
MAPPED = "mapped"  # some carried, the rest left at the value Tasker itself writes for unset
RESET = "reset"  # nothing carried; a fresh action, every argument unset
BLOCKED = "blocked"  # cannot be built at all -- see _swap_blocked


# ##################################################################################
# Why this does NOT delegate to taskedit_addable.classify_action_addability.
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
# 17 plugin actions whose payload bundles.json has not recorded, and the 7 structural ones
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


# The XML tag each picker category is written as.  Not derivable from arg_specs.json,
# which names the category and not the element: an Icon argument is <Img>, and nothing in
# the spec table says so.  Scene has no entry because no action in actionc.py declares a
# Scene-category argument and none appears in any sample XML -- listed in
# _PICKER_CATEGORIES anyway, so that a Tasker release introducing one is carried rather
# than silently dropped, and left out here so that writing an empty one is a no-op rather
# than a guess at a tag name.
PICKER_TAGS = {"App": "App", "Icon": "Img"}


def effective_args(action_key: str) -> list:
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


def argument_category(arg: ArgumentCode, state: RunState) -> str:
    """An argument's category name -- 'String', 'Int', 'App', 'Icon', 'Bundle'."""
    return state.tasker_arg_specs.get(arg.arg_type, "")


def is_hint_bundle(arg: ArgumentCode, state: RunState) -> bool:
    """Whether a Bundle argument is the informational 'Output Variables' note rather than
    a plugin payload.  taskedit skips these when synthesizing; nothing has to be produced
    for one, so it must not count towards either the target's argument tally or BLOCKED.
    """
    return argument_category(arg, state=state) == "Bundle" and arg.arg_name == taskedit_model.OUTPUT_VARIABLES_ARG_NAME


def wanted_args(action_key: str, state: RunState) -> list:
    """The target's arguments that a swap actually has to produce a value for."""
    return [arg for arg in effective_args(action_key) if not is_hint_bundle(arg, state=state)]


def carry_over_map(old_key: str, new_key: str, state: RunState) -> dict[str, str]:
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
    old_args = effective_args(old_key)
    new_args = wanted_args(new_key, state=state)
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
        if not name or argument_category(arg, state=state) in _PICKER_CATEGORIES:
            continue  # An unnamed argument has nothing to match on; pickers are rule 2's.
        new_id = by_name_and_type.get((name, arg.arg_type))
        if new_id is not None and new_id not in claimed:
            carry[arg.arg_id] = new_id
            claimed.add(new_id)

    # Rule 2.  Uniqueness is the whole warrant, so it is tested per category and both
    # sides have to be unique -- one App out of one App, never one of two.
    for category in _PICKER_CATEGORIES:
        from_source = [arg for arg in old_args if argument_category(arg, state=state) == category]
        to_target = [arg for arg in new_args if argument_category(arg, state=state) == category]
        if len(from_source) == 1 and len(to_target) == 1 and to_target[0].arg_id not in claimed:
            carry[from_source[0].arg_id] = to_target[0].arg_id
            claimed.add(to_target[0].arg_id)

    return carry


def carried_names(old_key: str, carry: dict[str, str]) -> list[str]:
    """The SOURCE's names for the arguments that survive, in the source's own order.

    The source's names rather than the target's because the user is looking at a list of
    things they are about to lose, and knows the action they started from -- "keeps Text,
    Title" answers "what happens to my Flash", which is the question being asked of this
    pulldown.  Where the two differ the source's name is also the more informative half:
    "keeps Package/App Name" says more than "keeps App".
    """
    return [arg.arg_name or f"arg{arg.arg_id}" for arg in effective_args(old_key) if arg.arg_id in carry]


def argument_element(
    action_element: Element | None,
    arg_id: str,
) -> Element | None:
    """One argument of an action, by its 'sr', or None."""
    if action_element is None:
        return None
    for child in action_element:
        if child.attrib.get("sr", "") == f"arg{arg_id}":
            return child
    return None


def has_value(element: Element | None) -> bool:
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


def order_action_children(action_element: Element) -> None:
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


def note_scope_limit(plan: Plan, what: str, state: RunState) -> None:
    """Say on a replace or swap plan when the app is displaying only part of the configuration.

    `what` is the Undo label, so a plan that touched one Task or Profile must not describe
    itself as touching the file: when a scope is in force the label says so too.
    """
    scope = current_scope(state=state)
    if not scope.is_everything:
        plan.what = f"{what} in {scope.phrase}"
        plan.warnings.append(
            f"Limited to {scope.phrase}, which is what the app is displaying.  Clear the single-item "
            f"selection to replace across the whole configuration.",
        )
