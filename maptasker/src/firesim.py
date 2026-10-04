"""firesim: "What fires when?" -- which Profiles a given moment makes active, and what follows."""

#! /usr/bin/env python3

#                                                                                       #
# firesim: pick a moment -- a time and date, the Wi-Fi network the device is on, the    #
#          app in front, the battery level -- and read off which Profiles that moment   #
#          makes active, the order their entry Tasks are queued in, and where two of    #
#          them collide.                                                                #
#                                                                                       #
# proflint asks the same questions of the configuration as a whole: two Profiles that   #
# watch the SAME trigger and disagree, a Profile whose conditions can never all be      #
# true.  This asks them of one moment, which reaches the pairs proflint cannot: two     #
# Profiles watching entirely different things that happen to be true together at 08:30  #
# on a Monday on the office Wi-Fi.  What a Task switches, and how a condition is named,  #
# are proflint's own readings, imported rather than repeated, so the two never disagree  #
# about the same pair of Tasks.                                                          #
#                                                                                       #
# Same contract as proflint: everything here reads PrimeItems.tasker_root_elements and   #
# nothing else -- no GUI, no generated HTML -- so it is testable without a window and     #
# guiwins_firesim is only the drawing.                                                   #
#                                                                                       #
# THREE ANSWERS, NOT TWO.  A condition is judged yes, no, or "cannot tell from here".    #
# The inputs describe four things about the device; a Profile can watch hundreds of     #
# others (an Event, a location, a %variable, the screen), and calling one of those false #
# would hide a Profile that may well fire, while calling it true would report a         #
# collision that may never happen.  So a Profile is ACTIVE only when every condition is  #
# a yes, INACTIVE when any is a no, and POSSIBLE otherwise -- and a POSSIBLE Profile says #
# exactly which conditions it is waiting on.  The same rule as proflint's: reading a     #
# thing this module cannot read is how a working Profile gets reported as dead.          #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING

from maptasker.src import proflint
from maptasker.src.mapjump import PROFILE, TASK, Target
from maptasker.src.objprops import APP_MATCH_FOREGROUND_APP_BIT, flag_bits

if TYPE_CHECKING:
    from datetime import datetime
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

# What a single condition, and then a whole Profile, comes out as.
YES = "yes"
NO = "no"
UNKNOWN = "unknown"

ACTIVE = "active"
POSSIBLE = "possible"
INACTIVE = "inactive"

# The two collision kinds.  SETTING is proflint's PROFILE-CONFLICT, found between Profiles
# active together rather than Profiles sharing a trigger; SAME-TASK is one Task started by
# two Profiles at once, which is where its collision handling decides what happens.
SETTING = "SETTING"
SAME_TASK = "SAME-TASK"

# The Profile children that are conditions -- proflint's list, and condition.py's.
_CONDITION_TAGS = ("Time", "Day", "State", "Event", "App", "Loc")

# The State codes this module can judge from the inputs.  Everything else is UNKNOWN.
_WIFI_CONNECTED = "160"
_BATTERY_LEVEL = "140"

# A Profile's priority when it names none: Tasker's default, the middle of its 0-50 range.
# The priority is carried by the Tasks the Profile starts, and a higher one runs first.
DEFAULT_PRIORITY = 5

# A <Time> field Tasker writes as -1 is one that was left unset.
_UNSET = -1
# <rep>2</rep> is a repeat counted in minutes; anything else is hours (proflint, condition.py).
_REPEAT_MINUTES = "2"
_MINUTES_IN_DAY = 24 * 60

# A value holding a %variable is decided on the device at run time.
_VARIABLE_MARKER = "%"

# <rty> -- what Tasker does when a Task is started again while it is still running.  No
# <rty> at all is the default, which is the first of these (elemvals.get_collision).
_COLLISION = {
    "0": "Tasker's default, 'Abort New Task': the second start is dropped, so this Task runs once, not once"
    " for each Profile",
    "1": "'Abort Existing Task': the second start kills the first, so the Task is cut off part-way and started again",
    "2": "'Run Both Together': both copies run side by side, each on its own",
}

_WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


@dataclass(frozen=True)
class Scenario:
    """The moment being simulated.

    None for wifi, app or battery means "not simulated": every condition on it is then a
    thing this module cannot tell, which is what makes it possible to ask "what fires at
    08:30 on a Monday, whatever else is going on".  An empty string for wifi or app is not
    the same thing -- it is the answer "not connected" or "nothing in front".
    """

    when: datetime
    wifi: str | None = None
    app: str | None = None
    battery: int | None = None


@dataclass
class Verdict:
    """One condition, judged against the scenario."""

    label: str
    outcome: str
    reason: str


@dataclass
class ProfileResult:
    """One enabled Profile, and what the scenario makes of it."""

    target: Target
    state: str
    verdicts: list[Verdict]
    priority: int
    instant: bool  # fires at a moment (an Event, a single time) rather than staying active
    entry: Target | None
    exit: Target | None

    @property
    def waiting_on(self) -> list[Verdict]:
        """The conditions this Profile's answer depends on and the scenario cannot settle."""
        return [verdict for verdict in self.verdicts if verdict.outcome == UNKNOWN]

    @property
    def ruled_out_by(self) -> Verdict | None:
        """The first condition that is certainly false, for an INACTIVE Profile."""
        return next((verdict for verdict in self.verdicts if verdict.outcome == NO), None)


@dataclass
class Run:
    """One Task start in the queue the scenario produces."""

    position: int
    task: Target
    profile: ProfileResult
    tied: bool  # shares its priority with another start, so its place among them is not fixed


@dataclass
class Collision:
    """Two starts that interfere with each other."""

    kind: str
    where: Target
    detail: str
    certain: bool  # both Profiles ACTIVE, rather than one of them only POSSIBLE


@dataclass
class Simulation:
    """Everything one scenario produces."""

    scenario: Scenario
    active: list[ProfileResult] = field(default_factory=list)
    possible: list[ProfileResult] = field(default_factory=list)
    inactive: list[ProfileResult] = field(default_factory=list)
    disabled: int = 0
    queue: list[Run] = field(default_factory=list)
    collisions: list[Collision] = field(default_factory=list)


# ##################################################################################
# Reading the XML.
# ##################################################################################
def _text(element: Element, tag: str) -> str:
    """The text of a child element, stripped, or "" if it is missing or empty."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _argument(element: Element, arg_id: str) -> str:
    """One of a State's arguments, <Str> or <Int>, whichever Tasker wrote (see proflint._argument)."""
    wanted = f"arg{arg_id}"
    for child in element:
        if child.attrib.get("sr") != wanted:
            continue
        if child.tag == "Int":
            variable = child.find("var")
            return (variable.text or "").strip() if variable is not None else (child.attrib.get("val") or "").strip()
        return (child.text or "").strip()
    return ""


def _number(element: Element, tag: str) -> int:
    """A numeric child, or _UNSET when it is missing or not a number."""
    value = _text(element, tag)
    return int(value) if value.lstrip("-").isdigit() else _UNSET


def _inverted(element: Element) -> bool:
    """Whether this condition is the NOT of itself -- Tasker's <pin>true</pin>."""
    return _text(element, "pin") == "true"


def _flip(verdict: Verdict, element: Element) -> Verdict:
    """Apply a condition's Invert, which turns yes into no and no into yes and leaves the rest."""
    if not _inverted(element) or verdict.outcome == UNKNOWN:
        return verdict
    outcome = NO if verdict.outcome == YES else YES
    return Verdict(verdict.label, outcome, f"{verdict.reason}, and the condition is inverted")


def _hhmm(minutes: int) -> str:
    """Minutes past midnight as 08:05."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def tasker_matches(pattern: str, value: str) -> bool:
    """Tasker's simple pattern matching, which is what a Wi-Fi SSID field is compared with.

    "/" separates alternatives, "*" is any run of characters and "+" is at least one, a
    leading "!" negates the whole thing, and the match ignores case.  Everything else is
    literal -- which is why this is not fnmatch, where "[" and "?" mean something.
    """
    pattern = pattern.strip()
    negate = pattern.startswith("!")
    if negate:
        pattern = pattern[1:]
    hit = False
    for alternative in pattern.split("/"):
        regex = "".join(".*" if char == "*" else ".+" if char == "+" else re.escape(char) for char in alternative)
        if re.fullmatch(regex, value, re.IGNORECASE | re.DOTALL):
            hit = True
            break
    return hit != negate


# ##################################################################################
# Judging one condition.
# ##################################################################################
def _judge_time(element: Element, scenario: Scenario) -> tuple[Verdict, bool]:
    """A <Time> condition, and whether it is an instant one (fires at a moment, then is gone).

    Tasker's shapes: a window (from .. to, wrapping past midnight when to is earlier), a
    single moment (from only), and either of those with a repeat, which makes the Profile
    fire on each tick of the repeat rather than stay active across the window.  A repeat
    counts from the window's start, so a tick can be worked out; one with no start counts
    from whenever the Profile was last enabled, which is not in the file.
    """
    label = "Time"
    if _text(element, "fromvar") or _text(element, "tovar"):
        return Verdict(label, UNKNOWN, "its window is set by a variable, which is decided on the device"), False

    from_h, from_m, to_h, to_m = (_number(element, tag) for tag in ("fh", "fm", "th", "tm"))
    start = from_h * 60 + max(from_m, 0) if from_h != _UNSET else None
    end = to_h * 60 + max(to_m, 0) if to_h != _UNSET else None
    now = scenario.when.hour * 60 + scenario.when.minute

    interval = _number(element, "repval")
    if interval > 0:
        interval *= 1 if _text(element, "rep") == _REPEAT_MINUTES else 60
    else:
        interval = 0
    every = f"every {interval // 60} hour(s)" if interval and interval % 60 == 0 else f"every {interval} minute(s)"

    if start is None and end is None:
        if interval:
            return Verdict(
                label,
                UNKNOWN,
                f"repeats {every} all day, counted from when the Profile was enabled -- so it fires within"
                f" {interval} minute(s) of any time, but not at a minute that can be worked out",
            ), True
        return Verdict(label, UNKNOWN, "has no time set"), False

    if start is None:
        start = 0
    if end is None:
        # A start and no end is a single moment -- unless it repeats, and then it repeats
        # until midnight.
        end = _MINUTES_IN_DAY - 1 if interval else start

    inside = start <= now <= end if start <= end else (now >= start or now <= end)
    window = _hhmm(start) if start == end else f"{_hhmm(start)}-{_hhmm(end)}"
    if not inside:
        return Verdict(label, NO, f"{_hhmm(now)} is outside {window}"), start == end or bool(interval)
    if not interval:
        if start == end:
            return Verdict(label, YES, f"fires at {window}, which is this minute"), True
        return Verdict(label, YES, f"{_hhmm(now)} is inside {window}"), False

    since = (now - start) % _MINUTES_IN_DAY
    if since % interval == 0:
        return Verdict(label, YES, f"repeats {every} from {_hhmm(start)}, and {_hhmm(now)} is one of its ticks"), True
    following = start + (since // interval + 1) * interval
    after = (
        f"next at {_hhmm(following % _MINUTES_IN_DAY)}"
        if (following - start) <= (end - start) % _MINUTES_IN_DAY
        else "and that was its last tick today"
    )
    return Verdict(label, NO, f"repeats {every} from {_hhmm(start)}, and {_hhmm(now)} is not a tick -- {after}"), True


def _judge_day(element: Element, scenario: Scenario) -> Verdict:
    """A <Day> condition: days of the week, days of the month, months.

    <wday> counts from 1 = Sunday and <mnth> from 0 = January (condition.condition_day).
    Where both days of the week AND days of the month are given and only one of them
    matches, the answer is left open: Tasker's Day context can combine the two either way,
    and which way is not something this has seen written down in the file.
    """
    label = "Day"
    when = scenario.when
    weekday = when.isoweekday() % 7 + 1  # Sunday -> 1 .. Saturday -> 7

    def values(prefix: str) -> list[int]:
        return [
            int(text)
            for child in element
            if child.tag.startswith(prefix) and (text := (child.text or "").strip()).isdigit()
        ]

    weekdays, monthdays, months = values("wday"), values("mday"), values("mnth")
    today = f"{_WEEKDAYS[weekday - 1]} {when.day} {when.strftime('%B')}"

    if months and when.month - 1 not in months:
        return Verdict(label, NO, f"{when.strftime('%B')} is not one of its months")
    on_weekday = weekday in weekdays if weekdays else None
    on_monthday = when.day in monthdays if monthdays else None

    if on_weekday is None and on_monthday is None:
        return Verdict(label, YES, f"{today} is in one of its months")
    if on_weekday is not None and on_monthday is not None and on_weekday != on_monthday:
        return Verdict(label, UNKNOWN, f"{today} matches its days of the week or of the month, but not both")
    if on_weekday is False or on_monthday is False:
        return Verdict(label, NO, f"{today} is not one of its days")
    return Verdict(label, YES, f"{today} is one of its days")


def _judge_wifi(element: Element, scenario: Scenario) -> Verdict:
    """State 'Wifi Connected': an SSID pattern, and optionally a MAC and an IP."""
    label = proflint.condition_label(element)
    ssid, mac, address = (_argument(element, arg) for arg in ("0", "1", "2"))
    if scenario.wifi is None:
        return Verdict(label, UNKNOWN, "Wi-Fi is not being simulated")
    if not scenario.wifi:
        return _flip(Verdict(label, NO, "the device is not connected to Wi-Fi"), element)
    if _VARIABLE_MARKER in ssid:
        return Verdict(label, UNKNOWN, f"the network it wants, {ssid}, is decided on the device")
    if ssid and not tasker_matches(ssid, scenario.wifi):
        return _flip(Verdict(label, NO, f"'{scenario.wifi}' is not '{ssid}'"), element)
    matched = f"'{scenario.wifi}' matches '{ssid}'" if ssid else f"it accepts any network, and '{scenario.wifi}' is one"
    if mac or address:
        return Verdict(label, UNKNOWN, f"{matched}, but it also names a MAC or IP address")
    return _flip(Verdict(label, YES, matched), element)


def _judge_battery(element: Element, scenario: Scenario) -> Verdict:
    """State 'Battery Level': From and To, both inclusive."""
    label = proflint.condition_label(element)
    low, high = _argument(element, "0"), _argument(element, "1")
    if scenario.battery is None:
        return Verdict(label, UNKNOWN, "the battery level is not being simulated")
    if not (low.isdigit() and high.isdigit()):
        return Verdict(label, UNKNOWN, "its range is set by a variable, which is decided on the device")
    level = scenario.battery
    inside = int(low) <= level <= int(high)
    return _flip(
        Verdict(label, YES if inside else NO, f"{level}% is {'inside' if inside else 'outside'} {low}-{high}%"),
        element,
    )


def _judge_app(element: Element, scenario: Scenario) -> Verdict:
    """An <App> condition: one of its apps is the one in front.

    Matched on the package, which is the identity (see appinv.AppEntry), or on the label for
    a scenario typed by hand.  An App condition set to match running services rather than
    the foreground app is left open: a service is not something the scenario describes.
    """
    label = "Application"
    bits = flag_bits(element)
    if bits and not bits & (1 << APP_MATCH_FOREGROUND_APP_BIT):
        return Verdict(label, UNKNOWN, "it matches running services, which are not being simulated")
    if scenario.app is None:
        return Verdict(label, UNKNOWN, "the app in front is not being simulated")

    packages = [_text(element, child.tag) for child in element if child.tag.startswith("pkg")]
    labels = [(child.text or "").strip() for child in element if child.tag.startswith("label")]
    names = ", ".join(name for name in labels if name) or ", ".join(packages)
    if not scenario.app:
        return _flip(Verdict(label, NO, f"no app is in front, and it wants {names}"), element)
    wanted = scenario.app.casefold()
    hit = any(wanted == item.casefold() for item in packages + labels if item)
    return _flip(
        Verdict(label, YES if hit else NO, f"'{scenario.app}' {'is' if hit else 'is not'} one of {names}"),
        element,
    )


def _judge(element: Element, scenario: Scenario) -> tuple[Verdict, bool]:
    """One condition, and whether it makes the Profile an instant one."""
    if element.tag == "Time":
        return _judge_time(element, scenario)
    if element.tag == "Day":
        verdict = _judge_day(element, scenario)
    elif element.tag == "App":
        verdict = _judge_app(element, scenario)
    elif element.tag == "Event":
        return Verdict(
            proflint.condition_label(element),
            UNKNOWN,
            "fires the moment the event happens, which the scenario does not say",
        ), True
    elif element.tag == "Loc":
        return Verdict("Location", UNKNOWN, "where the device is is not being simulated"), False
    elif element.tag == "State" and (code := _text(element, "code")) in (_WIFI_CONNECTED, _BATTERY_LEVEL):
        verdict = _judge_wifi(element, scenario) if code == _WIFI_CONNECTED else _judge_battery(element, scenario)
    else:
        return Verdict(
            proflint.condition_label(element), UNKNOWN, "this is not one of the things being simulated"
        ), False

    # A condition carrying variable tests of its own is only as settled as those tests, and
    # they are decided on the device.  A NO stays a NO: the rest cannot rescue it.
    if verdict.outcome == YES and element.find("ConditionList") is not None:
        verdict = Verdict(verdict.label, UNKNOWN, f"{verdict.reason}, but it also tests variables")
    return verdict, False


# ##################################################################################
# Profiles.
# ##################################################################################
def _project_owners(state: RunState) -> dict[str, str]:
    """{Profile or Task id: owning Project name} -- see proflint._project_owners for why one pass."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for kind in ("pids", "tids"):
            for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
                if member:
                    owners[f"{kind}:{member}"] = project_name
    return owners


def _task_target(task_id: str, owners: dict[str, str], state: RunState) -> Target | None:
    """Somewhere to go and look at one Task, or None when the link names no Task in the file."""
    task = state.tasker_root_elements["all_tasks"].get(task_id)
    if task is None:
        return None
    return Target(TASK, task_id, task["name"], owners.get(f"tids:{task_id}", ""))


def _priority(profile_xml: Element) -> int:
    """The priority this Profile's Tasks are started at."""
    value = _text(profile_xml, "pri")
    return int(value) if value.isdigit() else DEFAULT_PRIORITY


def evaluate_profile(
    profile_id: str, profile: dict, scenario: Scenario, owners: dict[str, str], state: RunState
) -> ProfileResult:
    """One Profile against the scenario: every condition judged, and the three-way answer.

    Tasker ANDs a Profile's conditions, so one certain NO is the end of it, and a Profile is
    ACTIVE only when every condition is a certain YES.  A Profile with no condition at all
    is INACTIVE: there is nothing for Tasker to make it active on (proflint reports it).
    """
    element = profile["xml"]
    verdicts: list[Verdict] = []
    instant = False
    for condition in (child for child in element if child.tag in _CONDITION_TAGS):
        verdict, is_instant = _judge(condition, scenario)
        verdicts.append(verdict)
        instant = instant or is_instant

    if not verdicts:
        verdicts.append(Verdict("No condition", NO, "there is nothing for Tasker to make it active on"))
    outcomes = {verdict.outcome for verdict in verdicts}
    result_state = INACTIVE if NO in outcomes else POSSIBLE if UNKNOWN in outcomes else ACTIVE

    return ProfileResult(
        target=Target(PROFILE, profile_id, profile["name"], owners.get(f"pids:{profile_id}", "")),
        state=result_state,
        verdicts=verdicts,
        priority=_priority(element),
        instant=instant,
        entry=_task_target(_text(element, "mid0"), owners, state=state),
        exit=_task_target(_text(element, "mid1"), owners, state=state),
    )


# ##################################################################################
# The queue, and where it collides.
# ##################################################################################
def _build_queue(starters: list[ProfileResult]) -> list[Run]:
    """The entry Tasks of every Profile that is, or may be, active -- highest priority first.

    Tasker runs the start with the higher priority first.  Between starts of EQUAL priority
    the order is whichever Profile Tasker happened to check first, which is not a thing the
    file says or the user controls; those are marked tied rather than given an order that
    would look like a promise.  Within a tie they are listed by Profile id only so that the
    same scenario always draws the same list.
    """
    ordered = sorted(
        ((result, result.entry) for result in starters if result.entry is not None),
        key=lambda pair: (-pair[0].priority, int(pair[0].target.key) if pair[0].target.key.isdigit() else 0),
    )
    counts: dict[int, int] = defaultdict(int)
    for result, _entry in ordered:
        counts[result.priority] += 1
    return [
        Run(position, entry, result, counts[result.priority] > 1)
        for position, (result, entry) in enumerate(ordered, start=1)
    ]


def _both(first: ProfileResult, second: ProfileResult) -> str:
    """How sure a collision between these two is, as a closing clause."""
    if first.state == ACTIVE and second.state == ACTIVE:
        return ""
    return "  This happens only if the Profiles still waiting on something turn out to be active as well."


def _setting_collisions(queue: list[Run], state: RunState) -> list[Collision]:
    """Two Profiles active together whose entry Tasks set the same switch opposite ways.

    proflint's PROFILE-CONFLICT, asked of Profiles that are active at the same moment
    instead of Profiles that share a trigger.  The device is left with whichever Task runs
    last -- which, between two starts of equal priority, is not fixed.
    """
    switches = proflint.switch_actions()
    tasks = state.tasker_root_elements["all_tasks"]
    settings = {run.position: proflint.settings_set(tasks[run.task.key]["xml"], switches) for run in queue}

    collisions: list[Collision] = []
    for first, second in combinations(queue, 2):
        if first.task.key == second.task.key:
            continue  # one Task started twice is _same_task_collisions', and cannot disagree with itself
        for subject, mine, theirs in proflint.setting_conflicts(settings[first.position], settings[second.position]):
            if first.profile.priority != second.profile.priority:
                outcome = f"{second.task.label} runs later, so the device is left {theirs}."
            else:
                outcome = "They have the same priority, so which one the device is left with is not fixed."
            collisions.append(
                Collision(
                    SETTING,
                    first.profile.target,
                    f"Is active together with {second.profile.target.label}, and their entry Tasks disagree:"
                    f" {first.task.label} sets {proflint.subject_label(subject)} {mine}, {second.task.label}"
                    f" sets it {theirs}.  {outcome}{_both(first.profile, second.profile)}",
                    first.profile.state == ACTIVE and second.profile.state == ACTIVE,
                ),
            )
    return collisions


def _same_task_collisions(queue: list[Run], state: RunState) -> list[Collision]:
    """One Task started by two or more Profiles at once: its collision handling decides what happens."""
    by_task: dict[str, list[Run]] = defaultdict(list)
    for run in queue:
        by_task[run.task.key].append(run)

    tasks = state.tasker_root_elements["all_tasks"]
    collisions: list[Collision] = []
    for runs in by_task.values():
        if len(runs) < 2:
            continue
        task = runs[0].task
        handling = _text(tasks[task.key]["xml"], "rty") or "0"
        names = ", ".join(run.profile.target.label for run in runs)
        certain = all(run.profile.state == ACTIVE for run in runs)
        collisions.append(
            Collision(
                SAME_TASK,
                task,
                f"Is the entry Task of {len(runs)} Profiles active at once ({names}).  Its collision handling is"
                f" {_COLLISION.get(handling, _COLLISION['0'])}."
                + (
                    ""
                    if certain
                    else "  This happens only if the Profiles still waiting on something turn out to be active as well."
                ),
                certain,
            ),
        )
    return collisions


# ##################################################################################
# What the dialog calls.
# ##################################################################################
def simulate(scenario: Scenario, state: RunState) -> Simulation:
    """Run one scenario over every enabled Profile in the loaded configuration.

    Disabled Profiles are counted and otherwise left out: a Profile that is switched off
    becomes active on nothing.  Safe to call with nothing loaded -- every table is empty
    and so is the answer.
    """
    result = Simulation(scenario)
    owners = _project_owners(state=state)
    for profile_id, profile in state.tasker_root_elements.get("all_profiles", {}).items():
        if _text(profile["xml"], "limit") == "true":
            result.disabled += 1
            continue
        evaluated = evaluate_profile(profile_id, profile, scenario, owners, state=state)
        {ACTIVE: result.active, POSSIBLE: result.possible, INACTIVE: result.inactive}[evaluated.state].append(
            evaluated,
        )

    for group in (result.active, result.possible, result.inactive):
        group.sort(key=lambda item: (-item.priority, item.target.label))

    result.queue = _build_queue(result.active + result.possible)
    result.collisions = _same_task_collisions(result.queue, state=state) + _setting_collisions(
        result.queue, state=state
    )
    result.collisions.sort(key=lambda item: (not item.certain, item.kind, item.where.label))
    return result


def wifi_networks(state: RunState) -> list[str]:
    """Every SSID a 'Wifi Connected' condition in the configuration names, for the picker.

    Split on "/" because that is how one condition names several networks, and variables
    and patterns are left out -- "Home*" is not a network anyone can be connected to.
    """
    networks: set[str] = set()
    for profile in state.tasker_root_elements.get("all_profiles", {}).values():
        for element in profile["xml"].findall("State"):
            if _text(element, "code") != _WIFI_CONNECTED:
                continue
            for alternative in _argument(element, "0").lstrip("!").split("/"):
                name = alternative.strip()
                if name and not any(marker in name for marker in "*+%"):
                    networks.add(name)
    return sorted(networks, key=str.casefold)


def condition_apps(state: RunState) -> dict[str, str]:
    """{package: label} for every app an App condition names, for the picker.

    The Profiles' own apps rather than everything installed: those are the only apps whose
    being in front changes the answer.  Anything else can still be typed in.
    """
    found: dict[str, str] = {}
    for profile in state.tasker_root_elements.get("all_profiles", {}).values():
        for element in profile["xml"].findall("App"):
            for child in element:
                if child.tag.startswith("pkg") and (package := (child.text or "").strip()):
                    found.setdefault(package, _text(element, f"label{child.tag[3:]}") or package)
    return dict(sorted(found.items(), key=lambda item: item[1].casefold()))
