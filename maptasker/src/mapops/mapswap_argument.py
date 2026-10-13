"""mapswap_argument: setting or editing one argument of every action of a code."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.analysis import mapfind
from maptasker.src.core.actionc import ArgumentCode, action_codes
from maptasker.src.core.mapjump import TASK, Target
from maptasker.src.edit import taskedit_addable
from maptasker.src.mapops.mapswap_model import (
    BLOCKED_UNADDABLE,
    INT_VALUE,
    INT_VAR,
    NEW_ARG,
    STR_ARG,
    Change,
    Plan,
    Site,
    Skip,
    argument_category,
    argument_element,
    effective_args,
    is_hint_bundle,
    note_scope_limit,
)
from maptasker.src.mapops.mapswap_sites import current_value, rewrite_site

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

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
# "String" and actionc.load_arg_specs rewrites the entry to "Str" as it
# loads.  Matching only the one in the file left every Str argument in the file --
# Flash's Text among them -- labelled "cannot be typed", which is every argument anybody
# would want this for.
_WRITABLE_CATEGORIES = ("Str", "String", "Int", "Boolean")


def argument_choices(action_key: str, state: RunState) -> list[tuple[str, str, str]]:
    """(arg id, label, refusal) for every argument of one action, in Tasker's own order.

    The Replace tab's argument pulldown.  Each is labelled with both its position and the
    name Tasker's action editor gives it -- "arg0 Text", "arg3 Title" -- because the name is
    what the user is looking at in the Map, and the position is what the XML calls it.

    An argument that cannot be written carries its reason as the third field and says so in
    its label rather than being dropped: an argument missing from the list teaches nothing,
    while "Icon -- cannot be typed" answers the question the user was about to ask.
    """
    choices = []
    for argument in effective_args(action_key):
        if is_hint_bundle(argument, state=state):
            continue  # Not an argument at all -- the plugin's note about what it outputs.
        category = argument_category(argument, state=state)
        name = f"arg{argument.arg_id} {argument.arg_name}".rstrip()
        writable = category in _WRITABLE_CATEGORIES
        refusal = "" if writable else f"a {category or 'picker'} argument is chosen from a picker, not typed"
        label = f"{name}  ({category})" if writable else f"{name}  ({category} -- cannot be typed)"
        choices.append((argument.arg_id, label, refusal))
    return choices


def _argument_site(
    action_element: Element,
    arg_id: str,
    where: Target,
    detail: str,
) -> tuple[Site | None, str]:
    """The field one argument's value sits in, or (None, why not).

    Three shapes, which is the whole reason this is a function: Tasker writes a string
    argument as the text of <Str sr="argN">, a plain numeric as the val= attribute of
    <Int sr="argN">, and a numeric bound to a variable as a <var> child of that <Int>.  The
    same three taskedit_apply.apply_arg_values writes when the Task editor saves one action; this
    is that rule applied to a thousand of them at once.
    """
    element = argument_element(action_element, arg_id)
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


def _creatable(action_element: Element, arg_id: str, state: RunState) -> bool:
    """Whether an argument this action does not carry could be written into it.

    Asked of taskedit rather than answered here, and asked by BUILDING one on a throwaway
    copy of the action: build_synthesized_args declines an argument it has no generic
    default for, and the only way to know which those are without restating its rules is to
    let it try.  The copy is the point -- planning must not touch the tree.
    """
    action_key = f"{(action_element.findtext('code') or '').strip()}t"
    argument = next((entry for entry in effective_args(action_key) if entry.arg_id == arg_id), None)
    if argument is None:
        return False
    scratch = copy.deepcopy(action_element)
    built = taskedit_addable.build_synthesized_args(type(scratch), scratch, [argument], state=state)
    return bool(built) and built[0].element is not None


def _replace_plan_title(
    action_name: str,
    arg_name: str,
    new_value: str,
    match: str,
    project: str,
    *,
    substitute: bool,
) -> str:
    """What the plan is called -- which is also its Undo label."""
    what = (
        f"Replace '{match}' with '{new_value}' in {action_name} {arg_name}"
        if substitute
        else f"Set {action_name} {arg_name} to '{new_value}'"
    )
    if match and not substitute:
        what = f"{what}, where it contains '{match}'"
    if project:
        what = f"{what} in Project '{project}'"
    return what


def _argument_replace_problem(
    argument: ArgumentCode,
    arg_name: str,
    *,
    substitute: bool,
    match: str,
    state: RunState,
) -> str:
    """Why this replace cannot be planned at all, or "" if it can: a picker, or no text to look for."""
    category = argument_category(argument, state=state)
    if category not in _WRITABLE_CATEGORIES:
        return (
            f"{arg_name} is {category}: chosen from a picker rather than typed, so there is no value here to replace."
        )
    if substitute and not match:
        return "Replacing text inside a value needs the text to look for."
    return ""


def _scan_actions_for_replace(job: _ArgumentReplace, action_key: str, project: str, state: RunState) -> None:
    """Hand every action of the code, in the Project asked for, to the job to consider."""
    for record in mapfind.build_index(state=state).objects:
        if record.kind != TASK:
            continue
        if project and record.project != project:
            continue
        for found in record.actions:
            if found.code != action_key[:-1] or found.element is None:
                continue
            job.consider(found.element, record.target.at_action(found.number))


def plan_argument_replace(
    action_key: str,
    arg_id: str,
    new_value: str,
    match: str = "",
    project: str = "",
    substitute: bool = False,
    add_missing: bool = False,
    *,
    state: RunState,
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
    argument = next((entry for entry in effective_args(action_key) if entry.arg_id == arg_id), None)
    arg_name = (argument.arg_name if argument else "") or f"arg{arg_id}"

    what = _replace_plan_title(action_name, arg_name, new_value, match, project, substitute=substitute)
    plan = Plan(what=what)

    # The same scope note the other two carry, and for the same reason: `what` is the Undo
    # label, so a plan that touched one Task must not describe itself as touching the file.
    note_scope_limit(plan, what, state)

    if argument is None:
        plan.warnings.append(f"'{action_name}' has no argument {arg_id}.")
        return plan
    problem = _argument_replace_problem(argument, arg_name, substitute=substitute, match=match, state=state)
    if problem:
        plan.warnings.append(problem)
        return plan

    numeric = argument_category(argument, state=state) in ("Int", "Boolean")

    adding = add_missing and not match and not substitute
    if add_missing and not adding:
        plan.warnings.append(
            "An argument can only be ADDED where nothing is being matched: a value filter cannot match a "
            "field that does not exist, and there is nothing inside a missing value to replace.",
        )

    job = _ArgumentReplace(
        plan=plan,
        action_key=action_key,
        arg_id=arg_id,
        arg_name=arg_name,
        new_value=new_value,
        wanted=match.lower(),
        substitute=substitute,
        adding=adding,
        refusal=_numeric_refusal(numeric, new_value),
        pattern=re.compile(re.escape(match), re.IGNORECASE) if substitute else None,
        detail=f"{action_name}, {arg_name}=",
        state=state,
    )
    _scan_actions_for_replace(job, action_key, project, state)

    plan.selected = set(range(len(plan.changes)))
    if job.added:
        plan.warnings.append(
            f"{job.added} of these ADD a {arg_name} to an action that never had one, rather than changing "
            f"one it has.  Each says so on its own row.",
        )
    if plan.changes and not job.wanted and not substitute:
        plan.warnings.append(
            f"Every {action_name} in scope gets the same {arg_name} -- {len(plan.changes)} of them.  "
            f"Narrow it with the value filter if that is more than you meant.",
        )
    return plan


@dataclass
class _ArgumentReplace:
    """One plan_argument_replace: what is being asked, and the plan it is adding to.

    consider() is given each action of the code in turn and either adds a Change, adds a Skip
    saying why it cannot, or -- for an action the value filter rules out, or that already holds
    the value -- does nothing.
    """

    plan: Plan
    action_key: str
    arg_id: str
    arg_name: str
    new_value: str
    wanted: str  # the value filter, lowercased; "" for none
    substitute: bool
    adding: bool  # write the argument into actions that have none
    refusal: str  # why new_value cannot go in a numeric argument; "" if it can
    pattern: re.Pattern | None
    detail: str
    state: RunState
    added: int = 0  # how many of the changes ADD an argument

    def consider(self, element: Element, where: Target) -> None:
        """Work out what putting the new value into one action's argument would do."""
        site, reason = _argument_site(element, self.arg_id, where, self.detail)
        if site is None:
            self._consider_missing(element, where, reason)
        else:
            self._consider_present(site, where)

    def _consider_missing(self, element: Element, where: Target, reason: str) -> None:
        """An argument the action never set.  Written into it when the user asked for that, and
        otherwise reported: it is exactly the action they meant to change and did not, so it
        says so and says what to tick.
        """
        plan = self.plan
        if not self.adding:
            # Reported only when nothing was filtering.  A value filter cannot rule
            # out a field there is nothing to read, so with one set these would be
            # noise; without one, they are the ones the user did not get.
            if not self.wanted:
                plan.skips.append(
                    Skip(
                        where=where,
                        reason=BLOCKED_UNADDABLE,
                        explanation=f"{reason}  Tick 'Add it where missing' to write one in.",
                    ),
                )
            return
        if self.refusal:
            plan.skips.append(Skip(where=where, reason=BLOCKED_UNADDABLE, explanation=self.refusal))
            return
        if not _creatable(element, self.arg_id, state=self.state):
            plan.skips.append(
                Skip(
                    where=where,
                    reason=BLOCKED_UNADDABLE,
                    explanation="this argument cannot be written from nothing -- it is not a plain value.",
                ),
            )
            return
        self.added += 1
        plan.changes.append(
            Change(
                site=Site(
                    kind=NEW_ARG,
                    element=element,
                    where=where,
                    detail=self.detail,
                    new_value=self.new_value,
                    create_arg=(self.action_key, self.arg_id),
                ),
                before="",
                after=self.new_value,
                note=f"this action has no {self.arg_name} -- one is added",
            ),
        )

    def _consider_present(self, site: Site, where: Target) -> None:
        """An action that carries the argument: a Change to its value, unless that would change nothing."""
        plan = self.plan
        before = current_value(site)
        if self.wanted and self.wanted not in before.lower():
            return

        if self.refusal and not self.substitute:
            plan.skips.append(Skip(where=where, reason=BLOCKED_UNADDABLE, explanation=self.refusal))
            return

        site = Site(
            kind=site.kind,
            element=site.element,
            where=where,
            detail=self.detail,
            new_value=None if self.substitute else self.new_value,
            rename=(self.pattern, self.new_value) if self.substitute else (),
        )
        after = rewrite_site(site, self.pattern, self.new_value)[1]
        if after == before:
            return  # Already holds it: a change that would change nothing.
        plan.changes.append(Change(site=site, before=before, after=after))
