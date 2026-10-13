"""mapswap_action: Task action for Task action -- how much of the old action survives, the plan, and the swap itself."""

from __future__ import annotations

import copy
from collections import Counter
from typing import TYPE_CHECKING

from maptasker.src.analysis import mapfind
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import TASK
from maptasker.src.edit import taskedit_addable
from maptasker.src.mapops.mapswap_model import (
    ACTION_ELEMENT,
    BLOCKED,
    EXACT,
    MAPPED,
    PICKER_TAGS,
    RESET,
    Change,
    Plan,
    Site,
    argument_category,
    argument_element,
    carried_names,
    carry_over_map,
    effective_args,
    has_value,
    note_scope_limit,
    order_action_children,
    wanted_args,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

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


def _swap_blocked(old_key: str, new_key: str, state: RunState) -> str:
    """Why this pair cannot be built at all, or "" if it can.

    Three reasons, and only three:

      Either side is _STRUCTURAL.
      The target carries a plugin <Bundle> that bundles.json has no recorded definition for
        (taskedit_addable.get_bundle_definition returns None).  An opaque payload is opaque: there
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
    # separates it from a picker: bundles.json either has the definition or nothing can be
    # written.  Carrying one across from the source is not attempted -- a different code is
    # a different plugin, and its payload would mean nothing to this one.
    if taskedit_addable.get_bundle_definition(new_key) is None:
        for arg in wanted_args(new_key, state=state):
            if argument_category(arg, state=state) == "Bundle":
                return (
                    f"'{action_codes[new_key].name}' is a plugin action and no definition of its "
                    "configuration has been recorded, so an empty one cannot be built."
                )

    return ""


def classify_swap(old_key: str, new_key: str, state: RunState) -> tuple[str, dict[str, str], str]:
    """(fidelity, carry-over map, reason) for one code pair, without touching the tree.

    EXACT when every argument of the target is carried, RESET when none is, MAPPED in
    between, BLOCKED when _swap_blocked gives a reason.

    Pure and cheap -- no tree access, and the inputs are two strings -- which is what lets
    fidelity_choices call it 550 times to build a pulldown.
    """
    reason = _swap_blocked(old_key, new_key, state=state)
    if reason:
        return BLOCKED, {}, reason

    carry = carry_over_map(old_key, new_key, state=state)
    wanted = wanted_args(new_key, state=state)
    given = wanted_args(old_key, state=state)

    # EXACT means the user loses nothing, which is a claim about BOTH sides: every
    # argument of the target is filled AND every argument of the source found a home.
    # Testing only the target gets this wrong in the case that matters most -- Flash has
    # sixteen arguments and 67 actions have none, so 'Flash -> Airplane Mode' fills every
    # argument the target has by filling none, and calling that EXACT would promise the
    # user that their message text survived into an action that cannot hold it.
    if len(carry) == len(wanted) == len(given):
        return EXACT, carry, ""
    return (MAPPED if carry else RESET), carry, ""


def fidelity_choices(old_key: str, state: RunState) -> list[tuple[str, str, str]]:
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

        fidelity, carry, reason = classify_swap(old_key, key, state=state)
        name = action_code.name

        if fidelity == BLOCKED:
            label = f"{name}  -- cannot: {reason}"
        elif not carry:
            wanted = len(wanted_args(key, state=state))
            label = f"{name}  -- keeps nothing" + (f"  (resets {wanted})" if wanted else "")
        else:
            kept = carried_names(old_key, carry)
            label = f"{name}  -- keeps {', '.join(kept)}  ({len(carry)} of {len(wanted_args(key, state=state))})"

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


def plan_action_swap(old_key: str, new_key: str, project: str = "", *, state: RunState) -> Plan:
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
    note_scope_limit(plan, what, state)

    fidelity, carry, reason = classify_swap(old_key, new_key, state=state)
    if fidelity == BLOCKED:
        plan.warnings.append(reason)
        return plan

    index = mapfind.build_index(state=state)
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
                    before=_action_summary(action.element, old_key, state=state),
                    after=_projected_summary(action.element, old_key, new_key, carry, state=state),
                    note=_swap_note(action.element, fidelity, carry, old_key, state=state),
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
        plan.warnings.append(f"Carries over: {', '.join(carried_names(old_key, carry))}.")
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


def _action_summary(action_element: Element, action_key: str, state: RunState) -> str:
    """One line describing an action as it stands -- "Flash 'Done: %n'".

    The first argument that holds text, which is the one the Map leads with and almost
    always the one that says what the action is for.
    """
    name = action_codes[action_key].name if action_key in action_codes else action_key
    for arg in wanted_args(action_key, state=state):
        element = argument_element(action_element, arg.arg_id)
        text = (element.text or "").strip() if element is not None else ""
        if text:
            return f"{name} '{text[:60]}'"
    return name


def _projected_summary(
    action_element: Element,
    old_key: str,
    new_key: str,
    carry: dict[str, str],
    state: RunState,
) -> str:
    """The same line, as it would read after the swap -- without performing it.

    Projected rather than produced by swapping a copy: a preview that ran the real
    mutation on a deep copy would be the more obviously correct thing and would cost a
    copy and a full synthesize per row, on a list that can run to hundreds.  What it
    would buy is exactness about which argument leads, which is a cosmetic property of
    one line of preview text.
    """
    name = action_codes[new_key].name if new_key in action_codes else new_key
    for arg in wanted_args(old_key, state=state):
        if arg.arg_id not in carry:
            continue
        element = argument_element(action_element, arg.arg_id)
        text = (element.text or "").strip() if element is not None else ""
        if text:
            return f"{name} '{text[:60]}'"
    return name


def _swap_note(
    action_element: Element,
    fidelity: str,
    carry: dict[str, str],
    old_key: str,
    state: RunState,
) -> str:
    """What this particular action loses, as opposed to what the pair loses in general.

    Per action rather than per pair because the answer differs per action: two Flashes
    swapped for Notifies lose the same arguments in principle, and only the one that
    actually set a Timeout loses a Timeout.  A note naming an argument nobody filled in
    is the kind of warning that teaches users to skim past warnings.
    """
    dropped = [
        arg.arg_name or f"arg{arg.arg_id}"
        for arg in wanted_args(old_key, state=state)
        if arg.arg_id not in carry and has_value(argument_element(action_element, arg.arg_id))
    ]
    if not dropped:
        return ""
    if fidelity == RESET:
        return "Discards: " + ", ".join(dropped)
    return "Drops: " + ", ".join(dropped)


def swap_one_action(
    action_element: Element,
    new_key: str,
    carry: dict[str, str],
    state: RunState,
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
      4. Synthesize the new argument set with taskedit_addable.build_synthesized_args -- the same
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
    carried: dict[str, Element] = {}
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
    taskedit_addable.build_synthesized_args(element_cls, action_element, effective_args(new_key), new_key, state=state)

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
    for arg in wanted_args(new_key, state=state):
        tag = PICKER_TAGS.get(argument_category(arg, state=state))
        if tag and f"arg{arg.arg_id}" not in present:
            action_element.append(element_cls(tag, {"sr": f"arg{arg.arg_id}"}))

    # 7.  Back into the order Tasker writes them.  See order_action_children.
    order_action_children(action_element)
