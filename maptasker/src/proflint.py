"""proflint: Profile conflicts, and the settings that quietly cost battery."""

#! /usr/bin/env python3

#                                                                                       #
# proflint: read the loaded configuration for the problems that are about BEHAVIOUR     #
#           rather than about structure -- two Profiles fighting over the same switch,  #
#           a Profile whose conditions can never all be true, a Task that polls in a    #
#           loop, a monitor left running, a Task that can block for ever.               #
#                                                                                       #
# Same contract as healthck.py, varxref.py and taskflow.py: everything here reads       #
# PrimeItems.tasker_root_elements and nothing else -- no GUI, no output_lines, no       #
# generated HTML.  The checks therefore run the moment an XML file is loaded (no Map    #
# run required) and are testable without standing up a GUI.                             #
#                                                                                       #
# The dependency runs healthck -> proflint, never the other way: healthck folds the     #
# findings below into its own report, exactly as it folds in taskflow's and varxref's.  #
# That is why the three severity words and the Problem record are spelled out again     #
# here rather than imported from healthck -- importing it back would be a cycle.        #
# taskflow.py and mapfind.py repeat them for the same reason.                            #
#                                                                                       #
# Why any of it.  Everything healthck reported until now was a fact about the FILE: a   #
# reference that points at nothing, a Task nothing runs, two objects sharing a name.    #
# None of that is what sends a Tasker user to a forum.  What sends them there is a      #
# configuration that is structurally perfect and still behaves badly -- the Profile     #
# that undoes what the other one just did, the loop that wakes the phone every second,  #
# the Task that hangs because a shell command never came back.  Every one of those is   #
# visible in the XML without running anything, and every one of them is below.          #
#                                                                                       #
# The whole module is advisory, and says so.  A conflict between two Profiles is only a #
# conflict if both really do fire, and a backup cannot prove that; a polling loop is    #
# sometimes exactly what was wanted.  So these findings are graded as things to look at #
# rather than as defects, and healthck prints a closing note saying which of them are   #
# judgement calls -- see _limitations there.                                             #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

from maptasker.src.actionc import action_codes
from maptasker.src.mapjump import (
    PROFILE,
    TASK,
    Target,
    actions_in_map_order,
)
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    import defusedxml.ElementTree  # Need for type hints

# Two of healthck's three grading words, spelled out rather than imported (see the
# header).  ERROR is deliberately not among them: nothing here is broken.  A Profile whose
# conditions contradict each other is the closest this module comes, and even that is a
# Profile Tasker loads and runs happily -- it simply never becomes active.  WARNING is for
# a finding whose answer costs something every day it is left alone (a monitor that never
# stops, a loop that never sleeps); INFO is for the ones that are only worth a look.
WARNING = "WARNING"
INFO = "INFO"

# The Profile children that are conditions.  condition.parse_profile_condition's own list,
# and the whole of what makes one Profile's trigger the same as another's: everything else
# under a <Profile> is metadata (id, dates, flags), its Task links, or TaskerNet.
_CONDITION_TAGS = ("Time", "Day", "State", "Event", "App", "Loc")

# Left out of a trigger's signature.  <cname> is the name the user typed on the condition
# and <pri> is an Event's priority: two Profiles watching the identical event are watching
# the identical event whether or not one of them has been labelled or nudged up the queue.
_UNSIGNED_TAGS = frozenset({"cname", "pri"})

# <pin>true</pin> inverts a State condition (see condition.condition_state).  It is part of
# the signature -- "screen on" and "screen NOT on" are different triggers -- but the
# never-fires check needs the signature WITHOUT it, which is how it spots the pair.
_INVERT_TAG = "pin"

# Tasker's control-flow and blocking action codes.  taskflow.py names the same handful for
# its own graph; these are the few this module needs to recognise a loop and a wait.
_IF = "37"
_END_IF = "38"
_FOR = "39"
_END_FOR = "40"
_WAIT = "30"
_WAIT_UNTIL = "35"
_GOTO = "135"
# Goto's arg0: "0" is "Action Number", the only destination kind that can be compared with
# the Goto's own number to see whether it jumps backwards.
_GOTO_ACTION_NUMBER = "0"

# Wait's five duration arguments and what each is worth in seconds.
_WAIT_UNITS = {"0": 0.001, "1": 1.0, "2": 60.0, "3": 3600.0, "4": 86400.0}

# A Wait shorter than this is a settling pause, not a poll.  One second is where Tasker's
# own documentation stops calling it a delay and starts warning about battery.
_POLL_SECONDS = 1.0

# A <Time> condition repeating this often is a poll dressed up as a Profile: it wakes the
# device on a schedule whatever else is going on.  Five minutes is Android's own doze
# window, below which a repeating alarm stops being cheap.
_FREQUENT_MINUTES = 5

# <rep>2</rep> means the repeat interval in <repval> is minutes; anything else is hours
# (condition.condition_time reads the same element the same way).
_REPEAT_MINUTES = "2"

# Location and radio actions.  Turning one of these on is free; leaving it on is not.
_GPS = "332"  # GPS on/off -- a Boolean argument, "1" for on
_STOP_LOCATION = "901"
# A ticked checkbox.  Tasker writes every Boolean argument as <Int sr="argN" val="1"/>,
# never as the word -- which is worth naming, because reading it as "true" fails silently:
# the argument is there, it is simply never equal to what is being looked for.
_TICKED = "1"

# "Get Location" asks once unless "Keep Tracking" is ticked, and then it does not stop.
# Only the original action is here: "Get Location v2" has no equivalent argument -- it
# takes a location and returns, so there is nothing left running behind it.
_GET_LOCATION = "902"
_KEEP_TRACKING_ARG = {_GET_LOCATION: "3"}

# Profile State conditions that cannot be evaluated without something scanning all the
# time.  Keyed by the <code> a <State> carries, valued with what is left running.
_ALWAYS_ON_STATES = {
    "170": "Tasker has to keep scanning for Wi-Fi networks",
    "4": "Tasker has to keep scanning for Bluetooth devices",
    "7": "Tasker has to keep the cell radio reporting nearby towers",
    "125": "Tasker has to keep the proximity sensor powered",
}

# Actions that put something on the screen and wait for the person looking at it.  They
# have a Timeout argument like the blocking actions below, but leaving it at zero there
# means "until it is answered", which is the point of a dialog rather than a hazard.
_DIALOG_CODES = frozenset({"314", "484", "548", "550", "551", "552", "595", "903", "941"})

# How an on/off/toggle argument reads.  actiont.py's "switch_set" list, which is also how
# _switch_actions below finds every action that takes one.
_SWITCH_VALUES = {"0": "Off", "1": "On", "2": "Toggle"}
_SWITCH_LOOKUP = "switch_set"

# Condition operators, from action.evaluate_condition_operator's table.  Only the ones two
# conditions can be checked against each other are named -- the ordering comparisons are
# left alone, because "%x > 3" and "%x > 5" are perfectly capable of both being true.
_EQUALS = frozenset({"0", "8"})  # 0 is the text =, 8 the numeric one
_NOT_EQUALS = frozenset({"1", "9"})
_MATCHES = "2"  # Tasker's "Matches" -- a glob, so only equality when it holds no wildcard
_NOT_MATCHES = "3"
_IS_SET = "12"
_IS_NOT_SET = "13"
_NUMERIC_OPERATORS = frozenset({"8", "9"})

# What turns a "Matches" from an equality into a pattern.  "~" is by far the operator a
# Tasker condition is actually written with, so leaving it out altogether would leave this
# check with almost nothing to read -- but "%x ~ a*" and "%x ~ ab" are both true of "ab",
# so a pattern holding any of these is not something two values can be compared through.
_GLOB_MARKERS = "*?+/"

# A name or value holding a variable is decided on the device at run time.  healthck's
# rule, for healthck's reason: reporting one as a defect would be a false alarm on a
# configuration that works perfectly, and one of those makes the whole report untrusted.
_VARIABLE_MARKER = "%"

# Days each month can hold.  February is 29 because leap years happen -- a Profile set for
# 29 February fires every four years, which is unusual but not impossible, and this check
# only ever reports what can NEVER happen.
_DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


# Every tag this module raises.  Exported so healthck can tell its own findings from
# these ones without matching on prefixes: the note it prints about them is about how much
# of a judgement call they are, and that has to name the exact set it applies to.
TAGS = frozenset(
    {
        "PROFILE-CONFLICT",
        "PROFILE-DUPLICATE-TRIGGER",
        "PROFILE-NEVER-FIRES",
        "ALWAYS-ON-MONITOR",
        "FREQUENT-TRIGGER",
        "POLLING-LOOP",
        "MISSING-COLLISION",
        "NO-TIMEOUT",
    },
)


@dataclass
class Problem:
    """One behavioural defect, in the shape healthck folds into its report.

    Deliberately the same four fields taskflow.Problem carries, for the same reason: both
    modules exist to be read by healthck.add, and a finding that arrives in a different
    shape would need a different fold.

    'where' is a Target rather than a sentence so a finding can be clicked, and is refined
    as far as the subject goes -- a polling loop points at the Wait, not merely at the Task
    holding it.
    """

    severity: str
    tag: str
    where: Target
    detail: str


# ##################################################################################
# Reading the XML.
# ##################################################################################
def _argument(element: defusedxml.ElementTree.Element, arg_id: str) -> str:
    """One of an action's arguments, whichever shape Tasker wrote it in.

    taskflow._argument, for taskflow's reason: matched on the "sr" attribute rather than
    child order, which Tasker does not guarantee, and covering <Str sr="argN">,
    <Int sr="argN" val="3"/> and the <Int sr="argN"><var>%N</var></Int> a bound variable
    turns the second into.
    """
    wanted = f"arg{arg_id}"
    for child in element:
        if child.attrib.get("sr") != wanted:
            continue
        if child.tag == "Int":
            variable = child.find("var")
            return (variable.text or "").strip() if variable is not None else (child.attrib.get("val") or "").strip()
        return (child.text or "").strip()
    return ""


def _text(element: defusedxml.ElementTree.Element, tag: str) -> str:
    """The text of a child element, stripped, or "" if it is missing or empty."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _is_enabled(profile: dict) -> bool:
    """Whether Tasker will act on this Profile at all.

    <limit>true</limit> is how a disabled Profile is marked -- see objprops.py, which says
    at length that the element means this and nothing else.  A disabled Profile is skipped
    by the conflict and battery checks because it cannot conflict with anything or cost
    anything; healthck reports it as DISABLED-PROFILE, which is the finding that matters
    about it.  The never-fires check does NOT skip it: "you disabled it" and "its
    conditions contradict each other" are two different things to fix.
    """
    return _text(profile["xml"], "limit") != "true"


def _project_owners(kind: str) -> dict[str, str]:
    """{object id: owning Project name} for Profiles (<pids>) or Tasks (<tids>).

    Built in one pass rather than by asking maputils per object: those walk every Project,
    which would make a scan of the whole configuration quadratic.  healthck, varxref and
    taskflow each keep their own copy of this for that reason and because all four promise
    to read nothing but PrimeItems.

    The filter on empty items is not decoration -- Tasker writes an empty list as an empty
    element, and "".split(",") is [""], which would claim a Project owns an object whose id
    is the empty string.
    """
    owners: dict[str, str] = {}
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def _profile_target(profile_id: str, profile: dict, owners: dict[str, str]) -> Target:
    """Somewhere to go and look at one Profile."""
    return Target(PROFILE, profile_id, profile["name"], owners.get(profile_id, ""))


def _action_name(code: str, suffix: str = "t") -> str:
    """What Tasker calls this action, event or state code.

    taskflow._action_name, widened by the suffix so the same hop works for a Profile's
    <State> and <Event> codes.  The hop through 'redirect' is because actionc.py files the
    plugin actions that share a configurator under one entry, and it is that entry which
    carries the name.
    """
    entry = action_codes.get(f"{code}{suffix}")
    if entry is not None and entry.redirect:
        entry = action_codes.get(entry.redirect, entry)
    return entry.name if entry is not None and entry.name else f"code {code}"


# ##################################################################################
# Trigger signatures -- what makes two Profiles watch the same thing.
# ##################################################################################
def _signature(element: defusedxml.ElementTree.Element, skip: frozenset[str], *, top: bool = False) -> str:
    """One condition element rendered as a string two Profiles can be compared on.

    Recursive because a condition is not flat: an Event carries a plugin <Bundle> whose
    values are what actually distinguish one AutoNotification trigger from the next, and
    comparing only the <code> would call every one of them the same trigger.

    Children are sorted, because Tasker's element order inside a condition is not
    meaningful and does vary between exports -- but each child keeps its "sr" attribute, so
    sorting cannot make arg0="A" arg1="B" look like arg0="B" arg1="A".  The one "sr" left
    out is the top element's own, which is only its position in the Profile (con0, con1):
    the same State watched by two Profiles is the same trigger wherever each of them
    happens to list it.
    """
    parts = [element.tag]
    if not top and (marker := element.attrib.get("sr")):
        parts.append(f"@{marker}")
    if value := (element.attrib.get("val") or "").strip():
        parts.append(f"={value}")
    elif text := (element.text or "").strip():
        parts.append(f"={text}")
    children = sorted(_signature(child, skip) for child in element if child.tag not in skip)
    return "".join(parts) + (f"({','.join(children)})" if children else "")


def _conditions(profile: dict) -> list[defusedxml.ElementTree.Element]:
    """A Profile's condition elements, in the order Tasker wrote them."""
    return [child for child in profile["xml"] if child.tag in _CONDITION_TAGS]


def _trigger_signature(profile: dict) -> tuple[str, ...]:
    """Everything this Profile watches, as a key two Profiles can be grouped by.

    Sorted, because Tasker ANDs a Profile's conditions together and an AND does not care
    which was written first: "app is Maps AND screen is on" and "screen is on AND app is
    Maps" are one trigger, and grouping them apart would miss exactly the pair of Profiles
    this check exists to find.
    """
    return tuple(sorted(_signature(element, _UNSIGNED_TAGS, top=True) for element in _conditions(profile)))


# ##################################################################################
# What a Task switches on and off.
# ##################################################################################
def _switch_actions() -> dict[str, str]:
    """{action code: arg id} for every action that sets something to Off / On / Toggle.

    Derived from the action table rather than listed here, the way healthck._scene_name_args
    is: the twenty-odd actions that take one of these all point their argument at actiont's
    "switch_set" lookup, so an action added to actionc.py in a later Tasker release is
    covered without this module being touched.
    """
    codes = {}
    for key, action in action_codes.items():
        if not key.endswith("t"):  # 'e' and 's' keys are Profile events and states.
            continue
        for argument in action.args or ():
            evaluation = argument.arg_eval
            if isinstance(evaluation, list) and _SWITCH_LOOKUP in evaluation:
                codes[key[:-1]] = argument.arg_id
                break
    return codes


def _subject(action: defusedxml.ElementTree.Element, code: str, switch_arg: str) -> tuple:
    """What this action is switching, apart from on or off.

    Nearly every one of these actions switches a fixed thing -- WiFi switches Wi-Fi -- and
    the code alone says which.  "Profile Status" is the exception: it names the Profile it
    is enabling in another argument, so two of them are only in conflict when they name the
    SAME Profile.  Every other argument of the action goes into the key, which covers that
    case and any later one like it without a list of exceptions to keep up to date.
    """
    entry = action_codes.get(f"{code}t")
    others = tuple(
        _argument(action, argument.arg_id)
        for argument in (entry.args or () if entry is not None else ())
        if argument.arg_id != switch_arg
    )
    return (code, others)


def _subject_label(subject: tuple) -> str:
    """The thing being switched, as a finding names it: WiFi, or Profile Status 'Night'."""
    code, others = subject
    named = ", ".join(f"'{item}'" for item in others if item and _VARIABLE_MARKER not in item)
    return f"{_action_name(code)} {named}" if named else _action_name(code)


def _settings_set(task_element: defusedxml.ElementTree.Element, switches: dict[str, str]) -> dict[tuple, str]:
    """{what this Task switches: the value it switches it to}, for the settings it always sets.

    Only the actions that run every time this Task runs are counted -- not one inside an
    If block, and not one carrying a condition of its own.  That is what makes a reported
    conflict worth reading: two Profiles whose Tasks MIGHT set the same switch differently,
    depending on conditions this file cannot evaluate, are not a conflict, they are a
    configuration.  Two that unconditionally set it differently are.

    A value built from a variable is skipped for _is_resolvable's reason -- what it will be
    is decided on the device -- and a setting written twice in one Task keeps the last
    value, which is what the device ends up with.
    """
    settings: dict[tuple, str] = {}
    depth = 0
    for action in actions_in_map_order(task_element):
        code = (action.findtext("code") or "").strip()
        if code == _IF:
            depth += 1
            continue
        if code == _END_IF:
            depth = max(0, depth - 1)
            continue
        # <on> present is how Tasker records a disabled action (action.py reads the same
        # element); a per-action <ConditionList sr="if"> is Tasker's "run this only if".
        if depth or code not in switches or action.find("on") is not None or action.find("ConditionList") is not None:
            continue
        value = _argument(action, switches[code])
        if value in _SWITCH_VALUES:
            settings[_subject(action, code, switches[code])] = _SWITCH_VALUES[value]
    return settings


# ##################################################################################
# Profiles: conflicting triggers, and triggers that can never be met.
# ##################################################################################
def _conflicts(first: dict[tuple, str], second: dict[tuple, str]) -> list[tuple[tuple, str, str]]:
    """Every setting these two Tasks leave in a different state, worst-named first."""
    return sorted(
        (subject, value, second[subject]) for subject, value in first.items() if second.get(subject, value) != value
    )


def _check_profile_conflicts(problems: list[Problem]) -> None:
    """Report Profiles that watch the same trigger, and say when their Tasks disagree.

    Two findings out of one grouping, because they are two different things to do about
    it.  Where the entry Tasks set the same switch to opposite values the outcome depends
    on the order Tasker happens to run them, which is not a thing the user controls --
    that is PROFILE-CONFLICT.  Where they merely both fire, it is worth knowing they are a
    pair (they may have been meant to be one Profile) but nothing is going wrong --
    PROFILE-DUPLICATE-TRIGGER, and only when no conflict was found, so the weaker finding
    never buries the stronger one.

    Only the entry Task is read, not the Tasks it goes on to perform.  A conflict this
    check reports is therefore always one a reader can see for themselves in two Tasks
    side by side, which is the point: chasing Perform Task chains would find more, and
    would report them as sentences no one can check.
    """
    profiles = PrimeItems.tasker_root_elements["all_profiles"]
    profile_owners = _project_owners("pids")
    switches = _switch_actions()
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]

    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for profile_id, profile in profiles.items():
        signature = _trigger_signature(profile)
        # A Profile with no conditions at all is _check_never_fires' finding, not a
        # trigger every other conditionless Profile can be said to share.
        if signature and _is_enabled(profile):
            groups[signature].append(profile_id)

    for members in groups.values():
        if len(members) < 2:
            continue
        settings = {
            profile_id: _settings_set(all_tasks[entry]["xml"], switches)
            for profile_id in members
            if (entry := _text(profiles[profile_id]["xml"], "mid0")) in all_tasks
        }
        found = False
        for first, second in combinations(sorted(members, key=int), 2):
            for subject, mine, theirs in _conflicts(settings.get(first, {}), settings.get(second, {})):
                found = True
                problems.append(
                    Problem(
                        WARNING,
                        "PROFILE-CONFLICT",
                        _profile_target(first, profiles[first], profile_owners),
                        f"Watches the same trigger as {_profile_target(second, profiles[second], profile_owners).label}"
                        f", and their entry Tasks disagree: this one sets {_subject_label(subject)} {mine}, the other"
                        f" sets it {theirs}.  Which of them the device is left with depends on the order Tasker"
                        " happens to run the two Profiles, which is not something you can set.",
                    ),
                )
        if not found:
            leader, *rest = sorted(members, key=int)
            others = ", ".join(_profile_target(item, profiles[item], profile_owners).label for item in rest)
            problems.append(
                Problem(
                    INFO,
                    "PROFILE-DUPLICATE-TRIGGER",
                    _profile_target(leader, profiles[leader], profile_owners),
                    f"Watches exactly the same trigger as {others}.  All of them become active together, in no"
                    " guaranteed order.  Nothing here contradicts anything -- but if they were meant to be one"
                    " Profile, this is where the copy is.",
                ),
            )


def _inverted(element: defusedxml.ElementTree.Element) -> bool:
    """Whether this condition is the NOT of itself -- Tasker's <pin>true</pin>."""
    return _text(element, _INVERT_TAG) == "true"


def _same_value(left: str, right: str, *, numeric: bool) -> bool:
    """Whether these two condition values are the same value.

    Compared case-insensitively, because "Matches" is, and a pair of tests is only reported
    as a contradiction when it is one under every reading -- folding case can only make two
    values look alike, which loses a contradiction rather than inventing one.  The exception
    is a value holding a %variable: Tasker's variable names are not case-insensitive, and
    %a and %A are two different variables rather than one written twice.

    A numeric comparison is reconciled as a number first, so "5" and "5.0" are not called
    a contradiction for being spelled differently.
    """
    if numeric:
        try:
            return float(left) == float(right)
        except ValueError:
            pass
    if _VARIABLE_MARKER in left or _VARIABLE_MARKER in right:
        return left == right
    return left.casefold() == right.casefold()


def _comparison(operator: str, value: str) -> tuple[bool, bool] | None:
    """(wants equality, compares as a number) for a test, or None when it cannot be judged.

    "Matches" and "Doesn't Match" are read as equality and inequality only when the value
    holds no wildcard -- see _GLOB_MARKERS.  Everything else this returns None for is an
    operator two tests genuinely can satisfy together.
    """
    if operator in _EQUALS:
        return (True, operator in _NUMERIC_OPERATORS)
    if operator in _NOT_EQUALS:
        return (False, operator in _NUMERIC_OPERATORS)
    if operator in (_MATCHES, _NOT_MATCHES) and not any(marker in value for marker in _GLOB_MARKERS):
        return (operator == _MATCHES, False)
    return None


def _impossible_pair(left: tuple[str, str], right: tuple[str, str]) -> str:
    """Why these two tests on one variable can never both hold, or "" when they can.

    Only the comparisons whose contradiction is a fact rather than a guess are judged.  Two
    equalities against different values cannot both hold.  An equality and an inequality
    against the SAME value cannot both hold whatever that value is -- the one case a
    %variable does not put out of reach, because whatever it turns out to be, it is the
    same on both sides.

    Two inequalities are not a contradiction at all: "%x != a AND %x != b" is satisfied by
    anything else, which is why only pairs with exactly one equality in them are weighed.
    """
    (left_op, left_value), (right_op, right_value) = left, right

    if {left_op, right_op} == {_IS_SET, _IS_NOT_SET}:
        return "is required to be both set and not set"

    first, second = _comparison(left_op, left_value), _comparison(right_op, right_value)
    if first is None or second is None:
        return ""
    (left_equal, left_numeric), (right_equal, right_numeric) = first, second
    same = _same_value(left_value, right_value, numeric=left_numeric or right_numeric)

    if left_equal and right_equal:
        if same or _VARIABLE_MARKER in left_value or _VARIABLE_MARKER in right_value:
            return ""
        return f"is required to equal both '{left_value}' and '{right_value}'"

    if left_equal != right_equal and same:
        wanted = left_value if left_equal else right_value
        return f"is required to equal '{wanted}' and to not equal it at the same time"

    return ""


def _impossible_condition_list(element: defusedxml.ElementTree.Element) -> str:
    """Why this condition's own <ConditionList> can never be satisfied, or "".

    Judged only when every joiner is a plain "And".  Tasker writes the joiner between a
    pair into <boolN>, and uses "Or" and the suffixed forms ("And2") to express grouping --
    so anything but a bare "And" means the list has a shape this check cannot read, and
    reading it anyway is how a working Profile gets reported as dead.
    """
    condition_list = element.find("ConditionList")
    if condition_list is None:
        return ""
    conditions = condition_list.findall("Condition")
    if len(conditions) < 2:
        return ""
    if any(
        (condition_list.findtext(f"bool{position}") or "").strip() != "And" for position in range(len(conditions) - 1)
    ):
        return ""

    tests: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for condition in conditions:
        left = (condition.findtext("lhs") or "").strip()
        if left:
            tests[left].append(((condition.findtext("op") or "").strip(), (condition.findtext("rhs") or "").strip()))

    for name, pairs in tests.items():
        for first, second in combinations(pairs, 2):
            if reason := _impossible_pair(first, second):
                return f"{name} {reason}"
    return ""


def _impossible_day(element: defusedxml.ElementTree.Element) -> str:
    """Why this <Day> condition names a date that does not exist, or "".

    Only the month/day-of-month pairing is judged, and only when both are given: a day of
    the month with no month beside it happens in some month, and a month with no day in it
    happens every year.  31 September is the one that gets typed by accident.
    """
    days = [int(child.text) for child in element if child.tag.startswith("mday") and (child.text or "").isdigit()]
    months = [int(child.text) for child in element if child.tag.startswith("mnth") and (child.text or "").isdigit()]
    if not days or not months:
        return ""
    months = [month for month in months if 0 <= month < len(_DAYS_IN_MONTH)]
    if not months or any(day <= _DAYS_IN_MONTH[month] for day in days for month in months):
        return ""
    return "names a day of the month that none of the months it names ever reaches"


def _check_never_fires(problems: list[Problem]) -> None:
    """Report Profiles whose conditions cannot all be true at once.

    Three ways that happens, all of them things a backup states outright.  A Profile with
    no condition at all has nothing to become active on.  A Profile holding one condition
    and its exact inverse -- the same State with <pin>true</pin> on one of them -- asks for
    a thing to be true and false together.  And a condition whose own <ConditionList> ANDs
    two tests of one variable that contradict each other can never be satisfied however the
    device is set.

    A disabled Profile is checked like any other: "you turned it off" and "it could not
    have run anyway" are two different repairs, and only one of them is undone by the
    Enabled switch.
    """
    profiles = PrimeItems.tasker_root_elements["all_profiles"]
    owners = _project_owners("pids")

    for profile_id, profile in profiles.items():
        where = _profile_target(profile_id, profile, owners)
        conditions = _conditions(profile)

        if not conditions:
            problems.append(
                Problem(
                    WARNING,
                    "PROFILE-NEVER-FIRES",
                    where,
                    "Has no condition at all -- no time, day, state, event, application or location -- so there is"
                    " nothing for Tasker to make it active on.  Its Tasks can still be run by hand or by a"
                    " Perform Task, but this Profile will never run them itself.",
                ),
            )
            continue

        seen: dict[str, bool] = {}
        for element in conditions:
            base = _signature(element, _UNSIGNED_TAGS | {_INVERT_TAG}, top=True)
            inverted = _inverted(element)
            if seen.get(base, inverted) != inverted:
                problems.append(
                    Problem(
                        WARNING,
                        "PROFILE-NEVER-FIRES",
                        where,
                        f"Holds {_condition_label(element)} and its exact opposite, and Tasker requires every one"
                        " of a Profile's conditions to be true together -- so this Profile can never become active."
                        "  Delete one of the pair, or split them into two Profiles.",
                    ),
                )
                break
            seen[base] = inverted

        for element in conditions:
            reason = _impossible_condition_list(element) or (_impossible_day(element) if element.tag == "Day" else "")
            if reason:
                problems.append(
                    Problem(
                        WARNING,
                        "PROFILE-NEVER-FIRES",
                        where,
                        f"Its {_condition_label(element)} condition {reason}, so it can never be satisfied and this"
                        " Profile can never become active.",
                    ),
                )
                break


def _condition_label(element: defusedxml.ElementTree.Element) -> str:
    """A condition as a finding names it: State 'Wifi Near', Event 'Notification', Time.

    Named through the action table for a State or an Event, because their <code> is a
    number the user has never seen; the other four condition kinds are named by their tag,
    which is the word Tasker's own context picker uses.
    """
    if element.tag in ("State", "Event"):
        code = _text(element, "code")
        suffix = "s" if element.tag == "State" else "e"
        return f"{element.tag} '{_action_name(code, suffix)}'" + (" [inverted]" if _inverted(element) else "")
    return {"Loc": "Location", "App": "Application"}.get(element.tag, element.tag)


# ##################################################################################
# Battery: monitors that never stop, and Profiles that fire on a timer.
# ##################################################################################
def _check_always_on(problems: list[Problem]) -> None:
    """Report the Profile conditions that keep a radio or a sensor running.

    A location Profile and a "Wifi Near" Profile look, in Tasker, exactly like any other
    Profile: one line in a list.  What they actually are is a standing instruction to scan
    until the Profile is turned off, and that is the single most common answer on a forum
    thread titled "why is Tasker eating my battery".  Nothing here is wrong -- these are
    the right tool for what they do -- so the finding says what it costs rather than
    telling anyone to remove it.

    Disabled Profiles are skipped: one that is turned off is not monitoring anything.
    """
    owners = _project_owners("pids")

    for profile_id, profile in PrimeItems.tasker_root_elements["all_profiles"].items():
        if not _is_enabled(profile):
            continue
        where = _profile_target(profile_id, profile, owners)

        for element in _conditions(profile):
            if element.tag == "Loc" and _text(element, "lat"):
                problems.append(
                    Problem(
                        WARNING,
                        "ALWAYS-ON-MONITOR",
                        where,
                        "Is a location Profile, so Tasker keeps asking Android where the device is for as long as"
                        " this Profile is enabled, whatever else is going on.  If a cheaper trigger would do --"
                        " a Wi-Fi network being connected, or a cell tower being near -- it will cost far less.",
                    ),
                )
            elif element.tag == "State" and (cost := _ALWAYS_ON_STATES.get(_text(element, "code"))):
                problems.append(
                    Problem(
                        WARNING,
                        "ALWAYS-ON-MONITOR",
                        where,
                        f"Watches {_condition_label(element)}, which is not a thing Android reports when it"
                        f" changes: {cost} for as long as this Profile is enabled.  Worth keeping only if the"
                        " Profile is earning it.",
                    ),
                )


def _check_frequent_triggers(problems: list[Problem]) -> None:
    """Report Profiles that fire on a short repeating timer.

    A <Time> condition with a repeat is a poll wearing a Profile's clothes: it wakes the
    device on the interval whether or not anything has changed.  Under five minutes it also
    falls inside Android's own doze window, where each wake costs far more than the work
    being done -- so the interval, not the Task, is usually what wants changing.
    """
    owners = _project_owners("pids")

    for profile_id, profile in PrimeItems.tasker_root_elements["all_profiles"].items():
        if not _is_enabled(profile):
            continue
        for element in _conditions(profile):
            if element.tag != "Time" or _text(element, "rep") != _REPEAT_MINUTES:
                continue
            interval = _text(element, "repval")
            if not interval.isdigit() or not 0 < int(interval) < _FREQUENT_MINUTES:
                continue
            problems.append(
                Problem(
                    WARNING,
                    "FREQUENT-TRIGGER",
                    _profile_target(profile_id, profile, owners),
                    f"Repeats every {interval} minute(s), so it wakes the device at least {1440 // int(interval)}"
                    " times a day whether or not there is anything to do.  If something the device already reports"
                    " could trigger it instead -- a state, an event, a variable being set -- that costs nothing"
                    " while nothing is happening.",
                ),
            )


# ##################################################################################
# Tasks: polling loops, monitors left running, collisions and blocking waits.
# ##################################################################################
def _timeout_arguments() -> dict[str, str]:
    """{action code: arg id} for every blocking action that takes a timeout.

    Derived from the action table the way _switch_actions is, so a new Tasker action with
    a timeout is covered without this module being touched.  Matched on the argument's name
    beginning "Timeout", which is how the table spells all of them -- anchored at the start
    so "Last Location If Timeout", a Boolean that decides what to do AFTER one, is not
    mistaken for the timeout itself.

    The dialogs are dropped: a Popup or a Menu with no timeout waits until it is answered,
    which is what a dialog is for.
    """
    codes = {}
    for key, action in action_codes.items():
        if not key.endswith("t") or key[:-1] in _DIALOG_CODES:
            continue
        for argument in action.args or ():
            if (argument.arg_name or "").startswith("Timeout"):
                codes[key[:-1]] = argument.arg_id
                break
    return codes


def _wait_seconds(action: defusedxml.ElementTree.Element) -> float | None:
    """How long a Wait waits, or None when a variable decides.

    None is not zero: a Wait of %Delay may be a millisecond or an hour, and treating it as
    the shorter would report a polling loop that may not be one.  The caller takes None as
    "long enough to matter", which is the safe reading inside a loop.
    """
    total = 0.0
    for arg_id, unit in _WAIT_UNITS.items():
        value = _argument(action, arg_id)
        if not value:
            continue
        if _VARIABLE_MARKER in value:
            return None
        try:
            total += float(value) * unit
        except ValueError:
            return None
    return total


def _describe_wait(action: defusedxml.ElementTree.Element) -> str:
    """A Wait's duration as a finding reads it: "2 seconds", or "" when a variable sets it."""
    seconds = _wait_seconds(action)
    if seconds is None:
        return ""
    if seconds >= 60:
        return f"{seconds / 60:g} minute(s)"
    return f"{seconds:g} second(s)"


@dataclass
class _TaskScan:
    """What one walk over a Task's actions found, for the checks that read more than one thing.

    Gathered in a single pass because a Task on a large backup can hold hundreds of
    actions, and every check below needs the same walk: the loops, the waits, the timeouts
    and the location calls are all read off it.
    """

    polling: list[tuple[int, str]]  # (action number, why) -- a Wait that runs on every lap
    timeouts: list[tuple[int, str]]  # (action number, action name) -- can block for ever
    location: list[tuple[int, str]]  # (action number, what it starts) -- a monitor left on
    long_running: bool  # holds a loop or a wait, so a second trigger can arrive mid-run


def _backward_gotos(steps: list[tuple[int, str, object]]) -> dict[int, int]:
    """{action number: the earlier action it jumps back to} for every backwards Goto.

    A Goto aimed at an earlier action is a loop the block matcher cannot see -- Tasker's
    For is not the only way to write one, and "Wait 1s, Goto 3" is how most polling loops
    in the wild are actually written.  Only "Goto Action Number" is read: a Goto by label
    lands wherever the label is, which taskflow resolves and this module does not need to.
    """
    jumps = {}
    for number, code, action in steps:
        if code != _GOTO or _argument(action, "0") != _GOTO_ACTION_NUMBER:
            continue
        destination = _argument(action, "1")
        if destination.isdigit() and int(destination) < number:
            jumps[number] = int(destination)
    return jumps


def _scan_task(task_element: defusedxml.ElementTree.Element, timeouts: dict[str, str]) -> _TaskScan:
    """Walk one Task's actions once, collecting everything the Task checks need.

    Disabled actions are skipped throughout: Tasker does not run them, so a polling loop
    made of disabled actions is not a polling loop.  Actions are walked in the order the
    Map numbers them (mapjump.actions_in_map_order), so a finding names a number the user
    can actually find -- the file's own order is not it.
    """
    steps = [
        (number, (action.findtext("code") or "").strip(), action)
        for number, action in enumerate(actions_in_map_order(task_element), start=1)
        if action.find("on") is None
    ]
    jumps = _backward_gotos(steps)
    scan = _TaskScan([], [], [], bool(jumps))

    depth = 0
    for number, code, action in steps:
        # Each of these is asked of the action in turn rather than as one chain: "Get
        # Location" is both an action that can block for ever and an action that can leave
        # a monitor running, and an elif would have let the first answer hide the second.
        if code == _FOR:
            depth += 1
            scan.long_running = True
        elif code == _END_FOR:
            depth = max(0, depth - 1)
        elif code in (_WAIT, _WAIT_UNTIL):
            scan.long_running = True
            # Inside a For, or between the target of a backwards Goto and the Goto itself:
            # either way this Wait runs once per lap, which is what makes it a poll rather
            # than a pause.  A Wait Until has no duration to weigh -- it waits as long as
            # it takes -- so it counts inside a loop whatever its poll interval.
            seconds = _wait_seconds(action) if code == _WAIT else None
            inside = depth > 0 or any(target <= number <= source for source, target in jumps.items())
            if inside and (seconds is None or seconds >= _POLL_SECONDS):
                scan.polling.append((number, _describe_wait(action) if code == _WAIT else ""))

        if code in timeouts:
            value = _argument(action, timeouts[code])
            if _VARIABLE_MARKER not in value and value in ("", "0"):
                scan.timeouts.append((number, _action_name(code)))

        if code == _GPS and _argument(action, "0") == _TICKED:
            scan.location.append((number, "GPS"))
        elif code in _KEEP_TRACKING_ARG and _argument(action, _KEEP_TRACKING_ARG[code]) == _TICKED:
            scan.location.append((number, f"{_action_name(code)} with 'Keep Tracking' set"))

    return scan


def _location_is_stopped() -> bool:
    """Whether anything in the whole file ever turns location tracking back off.

    Asked of the configuration rather than of the Task, because the Task that starts a
    monitor is very often not the Task that stops it -- a Profile's entry Task starts it
    and the exit Task stops it, which is the correct way to write it.  One "Stop Location"
    or one "GPS Off" anywhere is enough to keep quiet: the point of the finding is a
    configuration with no off switch in it at all.
    """
    for task in PrimeItems.tasker_root_elements["all_tasks"].values():
        for action in task["xml"].findall("Action"):
            if action.find("on") is not None:
                continue
            code = (action.findtext("code") or "").strip()
            if code == _STOP_LOCATION or (code == _GPS and _argument(action, "0") in ("0", "")):
                return True
    return False


def _profile_triggers() -> dict[str, list[str]]:
    """{task id: the Profiles that run it}, from every enabled Profile's <mid0>/<mid1>.

    Only enabled Profiles: a Task whose only trigger is switched off cannot be run twice at
    once by it.  Both links count -- an entry Task and an exit Task are each started by
    Tasker on its own, and a Task that is both is exactly the one a collision reaches.
    """
    triggers: dict[str, list[str]] = defaultdict(list)
    for profile_id, profile in PrimeItems.tasker_root_elements["all_profiles"].items():
        if not _is_enabled(profile):
            continue
        for tag in ("mid0", "mid1"):
            if task_id := _text(profile["xml"], tag):
                triggers[task_id].append(profile_id)
    return triggers


def _check_task_hygiene(problems: list[Problem]) -> None:
    """Report the Tasks that poll, hang, leave a monitor running, or cannot be re-entered.

    One walk per Task feeds all four (see _scan_task): on a backup of several hundred
    Tasks holding tens of thousands of actions, four separate walks is four times the work
    for the same answers.
    """
    owners = _project_owners("tids")
    timeouts = _timeout_arguments()
    triggers = _profile_triggers()
    location_stopped = _location_is_stopped()

    for task_id, task in PrimeItems.tasker_root_elements["all_tasks"].items():
        where = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        scan = _scan_task(task["xml"], timeouts)

        for number, duration in scan.polling:
            waited = f" of {duration}" if duration else ""
            problems.append(
                Problem(
                    WARNING,
                    "POLLING-LOOP",
                    where.at_action(number),
                    f"A wait{waited} inside a loop, so this Task holds the device awake and runs the loop body"
                    " again and again for as long as it takes.  A Profile watching for the thing being waited"
                    " for costs nothing while nothing is happening, where a loop costs the same whether anything"
                    " happens or not.",
                ),
            )

        for number, name in scan.timeouts:
            problems.append(
                Problem(
                    INFO,
                    "NO-TIMEOUT",
                    where.at_action(number),
                    f"'{name}' has no timeout set, so if it never comes back neither does this Task -- and while"
                    " it is stuck, every later trigger of this Task is dropped or queued behind it.  A timeout"
                    " that is generous is still an exit.",
                ),
            )

        if not location_stopped:
            for number, what in scan.location:
                problems.append(
                    Problem(
                        WARNING,
                        "ALWAYS-ON-MONITOR",
                        where.at_action(number),
                        f"Starts {what}, and nothing anywhere in this file ever stops it -- there is no"
                        " 'Stop Location' and no 'GPS Off' in the whole configuration.  Location stays on until"
                        " something outside Tasker turns it off.",
                    ),
                )

        started_by = triggers.get(task_id, [])
        if scan.long_running and started_by and task["xml"].find("rty") is None:
            problems.append(
                Problem(
                    INFO,
                    "MISSING-COLLISION",
                    where,
                    f"Waits or loops, is started by {len(started_by)} Profile(s), and has no collision handling"
                    " set -- so Tasker uses its default, which silently abandons the new run while the old one is"
                    " still going.  If a trigger arriving mid-run should be honoured, set the Task's Collision"
                    " Handling to 'Abort Existing Task' or 'Run Both Together'.",
                ),
            )


# ##################################################################################
# What healthck calls.
# ##################################################################################
def lint_problems() -> list[Problem]:
    """Every behavioural problem in the loaded configuration.

    What healthck folds into its report.  Ordered by tag and then by location so that the
    findings arrive grouped -- healthck sorts them again for printing, but a stable order
    here is what makes two runs over the same file produce the same list.

    Safe to call with nothing loaded: every pass iterates lookup tables that are empty, and
    an empty list comes back.
    """
    problems: list[Problem] = []

    _check_profile_conflicts(problems)
    _check_never_fires(problems)
    _check_always_on(problems)
    _check_frequent_triggers(problems)
    _check_task_hygiene(problems)

    problems.sort(key=lambda problem: (problem.tag, problem.where.label, problem.where.action))
    return problems
