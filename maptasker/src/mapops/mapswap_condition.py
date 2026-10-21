"""mapswap_condition: Profile context for Profile context -- a State, Event, Time, Day, App or Location for another."""

from __future__ import annotations

import copy
from collections import Counter
from typing import TYPE_CHECKING

from maptasker.src.analysis import mapfind
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import PROFILE
from maptasker.src.edit import profedit, taskedit_addable
from maptasker.src.mapops.mapswap_model import (
    BLOCKED,
    BLOCKED_DUPLICATE,
    EXACT,
    MAPPED,
    PICKER_TAGS,
    PROFILE_CONDITION,
    RESET,
    Change,
    Plan,
    Site,
    Skip,
    argument_category,
    argument_element,
    carried_names,
    carry_over_map,
    effective_args,
    has_value,
    note_scope_limit,
    wanted_args,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

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


def _condition_blocked(new_key: str, state: RunState) -> str:
    """Why an empty context of this kind cannot be built at all, or "".

    The same single reason a swap target is ever blocked: a plugin payload <Bundle> that
    bundles.json has no recorded definition for.  An opaque payload has no empty form a
    plugin will accept, and carrying one over from the source is not on the table either
    -- a different code is a different plugin, and its payload would mean nothing here.
    """
    tag, code_key = _split_condition(new_key)
    if not code_key:
        return "" if tag in _FLAT_CONDITIONS else f"'{tag}' is not a Profile context this build knows about."
    if code_key not in action_codes:
        return f"'{new_key}' is not a Profile context this build knows about."
    if taskedit_addable.get_bundle_definition(code_key) is None:
        for arg in wanted_args(code_key, state=state):
            if argument_category(arg, state=state) == "Bundle":
                return (
                    f"'{action_codes[code_key].name}' is a plugin {tag.lower()} and no definition of its "
                    "configuration has been recorded, so an empty one cannot be built."
                )
    return ""


def classify_condition_swap(old_key: str, new_key: str, state: RunState) -> tuple[str, dict[str, str], str]:
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
    reason = _condition_blocked(new_key, state=state)
    if reason:
        return BLOCKED, {}, reason

    _, old_code = _split_condition(old_key)
    _, new_code = _split_condition(new_key)
    if not old_code or not new_code:
        return RESET, {}, ""

    carry = carry_over_map(old_code, new_code, state=state)
    wanted = wanted_args(new_code, state=state)
    given = wanted_args(old_code, state=state)
    if len(carry) == len(wanted) == len(given):
        return EXACT, carry, ""
    return (MAPPED if carry else RESET), carry, ""


def condition_targets(old_key: str, state: RunState) -> list[tuple[str, str, str]]:
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
        fidelity, carry, reason = classify_condition_swap(old_key, key, state=state)
        name = _condition_name(key)
        _, code_key = _split_condition(key)

        if fidelity == BLOCKED:
            label = f"{name}  -- cannot: {reason}"
        elif not carry:
            label = f"{name}  -- a fresh, empty {name.split(':')[0]}"
        else:
            kept = carried_names(_split_condition(old_key)[1], carry)
            label = f"{name}  -- keeps {', '.join(kept)}  ({len(carry)} of {len(wanted_args(code_key, state=state))})"

        carried_count[key] = len(carry)
        choices.append((key, label, fidelity))

    # Same ordering rule as fidelity_choices: the band that keeps the most first, then how
    # much survives within the band, then the name.  The four flat kinds sit in the RESET
    # band with everything else that carries nothing, rather than being pinned to the top
    # -- a Day is not a better answer than an Event that keeps the SSID.
    choices.sort(key=lambda entry: (rank[entry[2]], -carried_count[entry[0]], entry[1]))
    return choices


def _fresh_condition(element_cls: type, new_key: str, state: RunState) -> Element:
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
    # bundles.json's recorded definition for this very code -- see build_synthesized_args.
    taskedit_addable.build_synthesized_args(element_cls, fresh, effective_args(code_key), code_key, state=state)

    # The picker arguments build_synthesized_args cannot write, as the empty element
    # Tasker writes for an unset picker.  Step 6 of swap_one_action, for the same reason.
    present = {child.attrib.get("sr", "") for child in fresh}
    for arg in wanted_args(code_key, state=state):
        picker_tag = PICKER_TAGS.get(argument_category(arg, state=state))
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


def _has_time_window(element: Element) -> bool:
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


def _condition_summary(element: Element, tag: str, code_key: str = "", *, state: RunState) -> str:
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
        for arg in wanted_args(code_key, state=state):
            argument = argument_element(element, arg.arg_id)
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
    element: Element,
    old_key: str,
    new_key: str,
    carry: dict[str, str],
    state: RunState,
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
    for arg in wanted_args(old_code, state=state):
        if arg.arg_id not in carry:
            continue
        argument = argument_element(element, arg.arg_id)
        text = (argument.text or "").strip() if argument is not None else ""
        if text:
            return f"{name} '{text[:60]}'"
    return name


def _condition_note(
    record: mapfind.ObjectRecord,
    condition: mapfind.ConditionRecord,
    new_key: str,
    carry: dict[str, str],
    fidelity: str,
    state: RunState,
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
    if element is None:  # The caller passes over conditions with no element.
        return ""
    pieces = []

    if condition.key and new_code:
        dropped = [
            arg.arg_name or f"arg{arg.arg_id}"
            for arg in wanted_args(condition.key, state=state)
            if arg.arg_id not in carry and has_value(argument_element(element, arg.arg_id))
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


def _duplicate_context(
    record: mapfind.ObjectRecord, condition: mapfind.ConditionRecord, new_tag: str, already_planned: int
) -> str:
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
        return f"this Profile already has {article} {name} condition, and Tasker writes only one of those per Profile."
    if already_planned:
        return (
            f"the row above already gives this Profile its one {name} condition -- replace the rest with "
            f"something else, or leave them."
        )
    return ""


def _plan_condition_changes(
    plan: Plan,
    old_key: str,
    new_key: str,
    project: str,
    carry: dict[str, str],
    fidelity: str,
    state: RunState,
) -> int:
    """Add a Change for every Profile context of the old kind (and a Skip for each that would be a duplicate).

    Returns how many of the contexts being changed carry a name written for the old condition.
    """
    old_name = _condition_name(old_key)
    new_tag, _ = _split_condition(new_key)
    index = mapfind.build_index(state=state)
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
                    before=_condition_summary(condition.element, condition.tag, condition.key, state=state),
                    after=_projected_condition_summary(condition.element, old_key, new_key, carry, state=state),
                    note=_condition_note(record, condition, new_key, carry, fidelity, state=state),
                ),
            )
    return named


def _condition_replace_warnings(
    plan: Plan,
    old_key: str,
    new_key: str,
    carry: dict[str, str],
    fidelity: str,
    named: int,
) -> None:
    """The notes a condition replace ends with: arriving empty, what carries over, Events, and kept names."""
    new_name = _condition_name(new_key)
    old_tag, _ = _split_condition(old_key)
    new_tag, _ = _split_condition(new_key)
    if plan.changes and not carry:
        plan.warnings.append(
            f"Each of these arrives EMPTY -- a new {new_name} exactly as 'Add Condition' writes one, with "
            f"nothing filled in.  Open each Profile afterwards and set it up, or the Profile will not "
            f"trigger on anything.",
        )
    if fidelity == MAPPED:
        plan.warnings.append(f"Carries over: {', '.join(carried_names(_split_condition(old_key)[1], carry))}.")
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


def plan_condition_replace(old_key: str, new_key: str, project: str = "", *, state: RunState) -> Plan:
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

    what = f"Replace Profile condition '{old_name}' with '{new_name}'"
    if project:
        what = f"{what} in Project '{project}'"
    plan = Plan(what=what)

    # The same scope note the other three carry, and for the same reason: `what` is the
    # Undo label, so a plan that touched one Profile must not describe itself as touching
    # the file.
    note_scope_limit(plan, what, state)

    fidelity, carry, reason = classify_condition_swap(old_key, new_key, state=state)
    if fidelity == BLOCKED:
        plan.warnings.append(reason)
        return plan

    named = _plan_condition_changes(plan, old_key, new_key, project, carry, fidelity, state)

    plan.selected = set(range(len(plan.changes)))

    _condition_replace_warnings(plan, old_key, new_key, carry, fidelity, named)

    return plan


def _order_condition_children(condition_element: Element) -> None:
    """Put a context's children in the order Tasker writes them: the non-argument ones in
    alphabetical order, then the arguments by their 'sr' as a string.

    order_action_children's counterpart for a Profile context, and it differs in the first half
    because the XML does.  An <Action> keeps its non-argument children in the order they
    were already in; a context's are alphabetical, and the sample XML is unambiguous about
    it -- Time reads fh, fm, rep, repval, th, tm; State reads cname, code, ConditionList;
    App reads cls0, cls1, cls10, cls2 ... cname, flags, label0 ... pin, pkg0, which is a
    plain case-insensitive string sort with the numbered families falling where they fall.
    Event reads code, pri and then its arguments, which is the same rule again.

    For the diff, exactly as order_action_children is: a context rebuilt in an order Tasker would
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


def swap_one_condition(
    condition_element: Element,
    new_key: str,
    carry: dict[str, str],
    state: RunState,
) -> None:
    """Rewrite one Profile context in place.  Called only from apply(), inside its undo block.

    In place -- the element keeps its identity, its sr="conN" and its position among the
    Profile's children -- for the reason swap_one_action gives about an <Action>, and one
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
    fresh = _fresh_condition(element_cls, new_key, state=state)
    keep_tags = _kept_condition_children(fresh.tag)

    # 1.  Lift what survives, deep, before the tear-down -- the arguments that carry over
    # (only ever coded-to-coded) and the children that outlive the kind.
    carried: dict[str, Element] = {}
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
        child.attrib.get("sr", ""): child for child in condition_element if child.attrib.get("sr", "").startswith("arg")
    }
    for new_id, lifted in carried.items():
        existing = synthesized.get(f"arg{new_id}")
        if existing is not None:
            condition_element.remove(existing)
        condition_element.append(lifted)

    # 5.  What outlived the kind, and then back into Tasker's own order.
    condition_element.extend(kept)
    _order_condition_children(condition_element)
