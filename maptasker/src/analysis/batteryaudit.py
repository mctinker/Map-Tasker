"""batteryaudit: what in a configuration keeps the phone busy, and a score for each Project."""

#! /usr/bin/env python3

#                                                                                       #
# batteryaudit: find the things in a configuration that make the phone wake up, stay    #
#               awake or run flat out -- a Time condition repeating every minute, a      #
#               Task looping on a short Wait, Keep Device Awake on a Task that loops,    #
#               a repeating Profile whose Task goes online -- and add them up, by        #
#               Project.                                                                #
#                                                                                       #
# What it reads, and from where.  Nothing here is measured, and the report says so:     #
#                                                                                       #
#   repeats    A <Time> condition's <repval>/<rep>, read by firesim.repeat_minutes so the #
#              Fire Simulator and this audit cannot disagree about "every 12 minutes".   #
#              How many times a day that is comes from the condition's own window.       #
#   loops      taskflow.analyze_task_flow's resolved Gotos: a Goto that lands on or above #
#              itself is a loop, and the Waits between its target and itself are the      #
#              loop's pace.  A For loop is bounded by its list and is not counted; a Goto  #
#              to the top or end of one is a For's own and is not either.  Whether the     #
#              loop can END is asked of taskflow.successors: a loop with a way out (an     #
#              If that Stops, a Goto that leaves, a condition on the Goto itself) is a     #
#              loop that does a job and finishes -- every array walk in a big Task is one  #
#              -- and is scored only when a Wait shows it pacing itself, and at half.  One  #
#              with no way out runs until something outside stops the Task.               #
#   awake      <stayawake>, the "Keep Device Awake" Task property.  Tasker's own text for  #
#              it (objprops._KEEP_AWAKE) says what to be careful of: "a task with a loop,  #
#              it can very quickly drain the battery".  That is the one combination this   #
#              audit scores as severe on Tasker's word rather than its own.              #
#   polling    A repeating Profile whose Task -- or a Task that Task performs -- goes      #
#              online, by outbound.py's reading of what goes online.                      #
#                                                                                       #
# THE SCORE IS A JUDGEMENT, NOT A MEASUREMENT.  What a wake-up costs depends on the        #
# phone, the radio, how long the Task runs and what else is awake at the time, none of     #
# which is in a backup.  The points below are weights somebody chose to put the worst on   #
# top, they are printed in the report, and the report ends by saying what they are not.    #
# What IS exact is the arithmetic that feeds them: how often a Profile repeats, how many   #
# times that is in its window, and what the shortest Wait in a loop is.                   #
#                                                                                       #
# Same contract as healthck.py, taskflow.py and outbound.py: reads PrimeItems and nothing  #
# else, no GUI, no device, and is testable on its own.                                    #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from maptasker.src.analysis import firesim, outbound, taskflow
from maptasker.src.core import clock
from maptasker.src.core.mapjump import PROFILE, PROJECT, TASK, Row, Target, actions_in_map_order, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import BATTERY_FILE, MY_VERSION, logger

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# ##################################################################################
# The weights.  Printed in the report; change them here and nowhere else.
# ##################################################################################
# A repeating Time condition, by how often it repeats: (longest interval in minutes, points).
REPEAT_POINTS: tuple[tuple[int, int], ...] = ((1, 40), (5, 25), (15, 12), (60, 5))
REPEAT_POINTS_OTHER = 1
# A loop that cannot be left, by the shortest Wait in it, in seconds.  One with no Wait at all runs flat out.
LOOP_POINTS: tuple[tuple[float, int], ...] = ((1, 35), (5, 30), (60, 15), (900, 5))
LOOP_POINTS_OTHER = 1
LOOP_POINTS_NO_WAIT = 40
LOOP_POINTS_UNKNOWN_WAIT = 8
# A loop that can be left is scored only when a Wait shows it pacing itself, and at this fraction of the above.
GUARDED_FRACTION = 0.5
# Keep Device Awake: on its own, with a long Wait in the Task, and with a loop (Tasker's own warning).
AWAKE_POINTS = 4
AWAKE_WAIT_POINTS = 12
AWAKE_LOOP_POINTS = 40
# A Wait this long, with Keep Device Awake on, holds the CPU awake through it.
AWAKE_LONG_WAIT_SECONDS = 60
# A repeating Profile whose Task goes online, by how often it repeats: (longest interval in minutes, points).
POLL_POINTS: tuple[tuple[int, int], ...] = ((1, 20), (5, 12), (15, 6), (60, 3))
POLL_POINTS_OTHER = 0

MAX_SCORE = 100
# What the findings after a Project's worst add to its score, as a fraction of their points.
REST_FRACTION = 0.25
# Where each band begins; below the first is "None".
BANDS: tuple[tuple[int, str], ...] = ((70, "Severe"), (40, "Heavy"), (15, "Moderate"), (1, "Light"))
NO_BAND = "None"
HEAVY = 40

REPEAT = "REPEAT"
LOOP = "LOOP"
AWAKE = "AWAKE"
POLL = "POLL"

_NOT_IN_A_PROJECT = ""
_MINUTES_IN_DAY = 24 * 60
_WAIT = "30"
_PERFORM_TASK = "130"
# How many Perform Tasks deep a repeating Profile's Task is followed.
_CALL_DEPTH = 4
# Goto types that belong to a For loop (taskflow's "top of loop" and "end of loop"): a For is bounded by its list.
_FOR_GOTOS = frozenset({"2", "3"})
# Actions that stop a Task until something outside it happens: a person answers a dialog or a menu, speaks, or a command or
# Scene result arrives.  A loop with one of these in it is paced by that, not by the CPU, so it is not a busy loop however
# little Wait it has -- the chat-with-an-input-dialog Task that goes round once per message is the commonest case.  Held by
# NAME and resolved through Task Flow's own names, so a test notices if Tasker renames one.
PACING_ACTIONS = frozenset(
    {
        "Input Dialog",
        "Text/Image Dialog",
        "List Dialog",
        "Pick Input Dialog",
        "Authentication Dialog",
        "Menu",
        "Get Voice",
        "Wait Until",
        "Wait For Command",
        "Wait For Scene v2 Result",
    },
)
_WAIT_UNITS = (("0", 0.001), ("1", 1.0), ("2", 60.0), ("3", 3600.0), ("4", 86400.0))
_REPORT_WIDTH = 78
_CLOUD = frozenset({outbound.WEB, outbound.PLUGIN})


@dataclass(frozen=True)
class Finding:
    """One thing that keeps the phone busy, where it is, and what it is worth."""

    project: str
    kind: str
    where: Target
    points: int
    summary: str
    detail: str = ""
    # For a repeating Profile: how many times a day it wakes the phone.
    wakeups: int = 0


@dataclass
class ProjectScore:
    """One Project's findings, and what they add up to."""

    name: str
    findings: list[Finding] = field(default_factory=list[Finding])

    @property
    def points(self) -> int:
        """The worst finding's points plus a quarter of the rest, held to MAX_SCORE.

        Not a plain sum: a big Project with a dozen mild findings would outscore a small one with one terrible one, and
        the score is there to say which to look at first.  A quarter is enough that two bad things are worse than one.
        """
        ranked = sorted((finding.points for finding in self.findings), reverse=True)
        return min(MAX_SCORE, round(sum(ranked[:1]) + REST_FRACTION * sum(ranked[1:])))

    @property
    def band(self) -> str:
        """The word for the score."""
        return band_of(self.points)

    @property
    def wakeups(self) -> int:
        """How many times a day the Project's repeating Profiles wake the phone, at the most."""
        return sum(finding.wakeups for finding in self.findings)


def band_of(points: int) -> str:
    """The word for a score: None, Light, Moderate, Heavy or Severe."""
    return next((name for start, name in BANDS if points >= start), NO_BAND)


def _points_for(table: tuple[tuple[float, int], ...], value: float, other: int) -> int:
    """The points of the first row whose limit `value` is within, else `other`."""
    return next((points for limit, points in table if value <= limit), other)


def _every(minutes: int) -> str:
    """ "1 minute", "12 minutes", "2 hours" -- how often, in the words a person says it."""
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def _seconds(seconds: float) -> str:
    """ "0.5 seconds", "1 second", "90 seconds", "2 minutes" -- a Wait as a person says it."""
    if seconds >= 120 and seconds % 60 == 0:
        return f"{int(seconds // 60)} minutes"
    if seconds == 1:
        return "1 second"
    return f"{seconds:g} seconds"


# ##################################################################################
# Reading the configuration.
# ##################################################################################
def _owners(state: RunState, tag: str) -> dict[str, str]:
    """{member id: Project name} for a Project's <pids> or <tids>."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(tag) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def _project_is_on(project_name: str, state: RunState) -> bool:
    """Whether a Project is enabled: <enbl>false</enbl> is how Tasker switches one off (see projedit)."""
    project = state.tasker_root_elements["all_projects"].get(project_name)
    return project is None or (project["xml"].findtext("enbl") or "").strip().lower() != "false"


def _profile_is_on(profile: Element) -> bool:
    """Whether a Profile is enabled: <limit>true</limit> is how Tasker records one that is not (see firesim)."""
    return (profile.findtext("limit") or "").strip() != "true"


def _entry_tasks(profile: Element) -> list[str]:
    """The ids of the Tasks a Profile runs when it becomes active: <mid0>, the entry Task."""
    return [(child.text or "").strip() for child in profile if child.tag == "mid0" and (child.text or "").strip()]


def ticks_per_day(element: Element, interval: int) -> int:
    """How many times a day a repeating <Time> condition fires, at the most: its window divided by its interval.

    The window is from <fh>:<fm> to <th>:<tm>, wrapping past midnight when the end is earlier.  A condition with a start
    and no end repeats until midnight, one with neither repeats all day, and one whose window is set by a variable is
    taken as all day, since what the variable holds is not in the file.  A repeat counts from the window's start, and a
    window that is not a whole number of intervals gets the tick at its start as well.
    """
    unset = -1

    def number(tag: str) -> int:
        text = (element.findtext(tag) or "").strip()
        return int(text) if text.lstrip("-").isdigit() else unset

    if (element.findtext("fromvar") or "").strip() or (element.findtext("tovar") or "").strip():
        return _MINUTES_IN_DAY // interval
    from_hour, from_minute, to_hour, to_minute = (number(tag) for tag in ("fh", "fm", "th", "tm"))
    start = from_hour * 60 + max(from_minute, 0) if from_hour != unset else None
    end = to_hour * 60 + max(to_minute, 0) if to_hour != unset else None
    if start is None and end is None:
        return _MINUTES_IN_DAY // interval
    start = 0 if start is None else start
    end = _MINUTES_IN_DAY - 1 if end is None else end
    length = (end - start) % _MINUTES_IN_DAY if end != start else 0
    return length // interval + 1


def _wait_seconds(action: Element) -> float | None:
    """How long a Wait action waits, in seconds -- None when any part of it is set by a variable."""
    total = 0.0
    for argument, scale in _WAIT_UNITS:
        text = taskflow.action_argument(action, argument)
        if not text:
            continue
        if "%" in text:
            return None
        try:
            total += float(text) * scale
        except ValueError:
            return None
    return total


@dataclass(frozen=True)
class _Loop:
    """A Goto that lands on or above itself, and what it goes round."""

    goto: int  # the Goto's own Map number
    first: int  # where it lands, as a Map number
    shortest_wait: float | None  # seconds; None when the loop has no Wait at all
    unknown_wait: bool  # a Wait in it is set by a variable
    endless: bool  # nothing in it can end it: no Stop, no way out, no condition on the Goto
    paced: bool = False  # something in it waits for the outside world, so it is not going round on the CPU

    @property
    def points(self) -> int:
        """What the loop is worth, by the shortest Wait in it -- and at half when it can be left, and nothing when paced."""
        if self.paced:
            return 0
        if self.shortest_wait is not None:
            points = _points_for(LOOP_POINTS, self.shortest_wait, LOOP_POINTS_OTHER)
        elif self.unknown_wait:
            points = LOOP_POINTS_UNKNOWN_WAIT
        else:
            points = LOOP_POINTS_NO_WAIT
        if self.endless:
            return points
        # A loop that can be left and has no Wait is a loop that does a job and finishes, not one that polls.
        return max(1, round(points * GUARDED_FRACTION)) if self.shortest_wait is not None or self.unknown_wait else 0


def _loops(flow: taskflow.Flow, task_element: Element) -> list[_Loop]:
    """Every loop made by a Goto in a Task, with the shortest Wait it goes through and whether it can be left.

    A For loop is not one: its list bounds it.  Nor is a Goto to the top or the end of one (taskflow's two block-jump types),
    which is a For's own continue and break.  A Goto that is switched off, or that lands nowhere that can be worked out, is
    not one either.  A loop can be left when any action in it can be followed by one outside it, or by none at all (a Stop,
    a Return, the end of the Task) -- which is what taskflow.successors says.
    """
    actions = actions_in_map_order(task_element)
    graph = taskflow.successors(flow)
    loops: list[_Loop] = []
    for jump in flow.jumps.values():
        if not jump.resolved or jump.target is None or jump.target > jump.source:
            continue
        goto = flow.steps[jump.source]
        if goto.disabled or (goto.goto is not None and goto.goto[0] in _FOR_GOTOS):
            continue
        region = range(jump.target, jump.source + 1)
        waits: list[float] = []
        unknown = False
        paced = any(flow.steps[i].name in PACING_ACTIONS and not flow.steps[i].disabled for i in region)
        for index in region:
            step = flow.steps[index]
            if step.code != _WAIT or step.disabled or index >= len(actions):
                continue
            seconds = _wait_seconds(actions[index])
            if seconds is None:
                unknown = True
            elif seconds > 0:
                waits.append(seconds)
        # A way out is any of: the Goto itself having a condition (when it does not hold, the Task goes on past it, or
        # ends if it is the last action); a Stop or Return in the loop, even one with a condition of its own; an action
        # that can be followed by none, or by one outside the loop.  The Task ending is not an index in the graph, which
        # is why the first two are stated and not left to it.
        leaves = jump.conditional or any(
            flow.steps[i].terminates or not graph.get(i) or any(j not in region for j in graph[i]) for i in region
        )
        loops.append(
            _Loop(
                goto.number,
                flow.steps[jump.target].number,
                min(waits) if waits else None,
                unknown,
                not leaves,
                paced,
            )
        )
    return loops


def _performed(task_element: Element, by_name: dict[str, list[str]]) -> list[str]:
    """The ids of the Tasks this Task performs by a name written out in full."""
    found: list[str] = []
    for action in task_element.findall("Action"):
        if (action.findtext("code") or "").strip() != _PERFORM_TASK or action.find("on") is not None:
            continue
        name = taskflow.action_argument(action, "0")
        if name and "%" not in name:
            found += by_name.get(name, [])
    return found


# ##################################################################################
# The audit.
# ##################################################################################
class _Audit:
    """One pass over a configuration: what it holds, and the findings made so far."""

    def __init__(self, state: RunState) -> None:
        self.state = state
        tables = state.tasker_root_elements
        self.profiles: dict[str, dict[str, Any]] = tables.get("all_profiles", {})
        self.tasks: dict[str, dict[str, Any]] = tables.get("all_tasks", {})
        self.profile_owner = _owners(state, "pids")
        self.task_owner = _owners(state, "tids")
        self.by_name: dict[str, list[str]] = {}
        for task_id, task in self.tasks.items():
            self.by_name.setdefault(task["name"], []).append(task_id)
        # {task id: the names of the actions in it that go online}, for what is enabled.
        self.online: dict[str, list[str]] = {}
        for use in outbound.outbound_uses(state):
            if use.category in _CLOUD and use.enabled:
                self.online.setdefault(use.where.key, []).append(use.what)
        self.findings: list[Finding] = []
        self.profiles_checked = 0
        self.tasks_checked = 0

    def project_of_profile(self, profile_id: str) -> str:
        return self.profile_owner.get(profile_id, _NOT_IN_A_PROJECT)

    def project_of_task(self, task_id: str) -> str:
        return self.task_owner.get(task_id, _NOT_IN_A_PROJECT)

    def _goes_online(self, task_id: str, seen: set[str], depth: int = 0) -> list[tuple[str, list[str]]]:
        """[(Task name, what in it goes online)] for this Task and the Tasks it performs, a few levels down."""
        task = self.tasks.get(task_id)
        if task is None or task_id in seen or depth > _CALL_DEPTH:
            return []
        seen.add(task_id)
        found = [(task["name"], self.online[task_id])] if task_id in self.online else []
        for called in _performed(task["xml"], self.by_name):
            found += self._goes_online(called, seen, depth + 1)
        return found

    # ---------------------------------------------------------------- Profiles
    def read_profiles(self) -> None:
        for profile_id, profile in self.profiles.items():
            project = self.project_of_profile(profile_id)
            if not _profile_is_on(profile["xml"]) or not _project_is_on(project, self.state):
                continue
            self.profiles_checked += 1
            where = Target(PROFILE, profile_id, profile["name"], project)
            for condition in profile["xml"].findall("Time"):
                interval = firesim.repeat_minutes(condition)
                if interval > 0:
                    self._repeat(project, where, profile["xml"], condition, interval)

    def _repeat(self, project: str, where: Target, profile: Element, condition: Element, interval: int) -> None:
        ticks = ticks_per_day(condition, interval)
        points = _points_for(REPEAT_POINTS, interval, REPEAT_POINTS_OTHER)
        runs = [self.tasks[i]["name"] for i in _entry_tasks(profile) if i in self.tasks]
        detail = f"Runs Task '{runs[0]}' each time." if len(runs) == 1 else ""
        self.findings.append(
            Finding(
                project,
                REPEAT,
                where,
                points,
                f"Repeats every {_every(interval)}: up to {ticks:,} wake-ups a day.",
                detail,
                ticks,
            ),
        )
        polled = _points_for(POLL_POINTS, interval, POLL_POINTS_OTHER)
        for task_id in _entry_tasks(profile):
            for name, actions in self._goes_online(task_id, set()):
                if polled:
                    shown = ", ".join(dict.fromkeys(actions))
                    self.findings.append(
                        Finding(
                            project,
                            POLL,
                            where,
                            polled,
                            f"Goes online every {_every(interval)}: Task '{name}' uses {shown}.",
                            "A repeating Profile that calls the web or a plugin is a poll, and the radio wakes for each one.",
                        ),
                    )

    # ---------------------------------------------------------------- Tasks
    def read_tasks(self) -> None:
        for task_id, task in self.tasks.items():
            project = self.project_of_task(task_id)
            if not _project_is_on(project, self.state):
                continue
            self.tasks_checked += 1
            flow = taskflow.analyze_task_flow(task_id, project, state=self.state)
            if flow is None:
                continue
            self._task(project, task_id, task, flow)

    def _task(self, project: str, task_id: str, task: dict[str, Any], flow: taskflow.Flow) -> None:
        element: Element = task["xml"]
        where = Target(TASK, task_id, task["name"], project)
        loops = _loops(flow, element)
        scored = sorted((loop for loop in loops if loop.points), key=lambda loop: -loop.points)
        if scored:
            self.findings.append(self._loop_finding(project, where, scored[0], len(scored) - 1))
        if (element.findtext("stayawake") or "").strip().lower() == "true":
            self.findings.append(self._awake_finding(project, where, element, flow, bool(loops)))

    @staticmethod
    def _loop_finding(project: str, where: Target, loop: _Loop, others: int) -> Finding:
        """One finding for a Task's worst loop, which says how many more like it there are."""
        at = where.at_action(loop.goto)
        also = f"  {others} other loop{'s' if others != 1 else ''} in this Task." if others else ""
        kind = "Loops" if loop.endless else "Can loop"
        goes = f"action {loop.goto} goes back to action {loop.first}"
        ending = (
            "Nothing in the loop can end it, so it runs until something else stops the Task."
            if loop.endless
            else "Something in the loop can end it, so how long it runs depends on what it is waiting for."
        )
        if loop.shortest_wait is None and not loop.unknown_wait:
            summary = f"{kind} with no Wait: {goes}, so it runs flat out."
            detail = "Nothing in the loop waits, so Tasker keeps the CPU busy for as long as it goes round."
        elif loop.shortest_wait is None:
            summary = f"{kind} on a Wait set by a variable: {goes}."
            detail = "How long the Wait is is decided on the device, so how often this wakes the phone cannot be told from the file."
        else:
            summary = f"{kind} every {_seconds(loop.shortest_wait)} or so: {goes}."
            detail = f"The shortest Wait in the loop is {_seconds(loop.shortest_wait)}."
        return Finding(project, LOOP, at, loop.points, summary, f"{detail}  {ending}{also}")

    @staticmethod
    def _awake_finding(project: str, where: Target, element: Element, flow: taskflow.Flow, looped: bool) -> Finding:
        if looped:
            return Finding(
                project,
                AWAKE,
                where,
                AWAKE_LOOP_POINTS,
                "Keep Device Awake is on for a Task that loops.",
                "Tasker's own warning for this property: with a loop it can very quickly drain the battery.",
            )
        longest = 0.0
        actions = actions_in_map_order(element)
        for index, step in enumerate(flow.steps):
            if step.code == _WAIT and not step.disabled and index < len(actions):
                longest = max(longest, _wait_seconds(actions[index]) or 0.0)
        if longest >= AWAKE_LONG_WAIT_SECONDS:
            return Finding(
                project,
                AWAKE,
                where,
                AWAKE_WAIT_POINTS,
                f"Keep Device Awake is on through a Wait of {_seconds(longest)}.",
                "The CPU is held awake for the whole wait.",
            )
        return Finding(
            project,
            AWAKE,
            where,
            AWAKE_POINTS,
            "Keep Device Awake is on.",
            "By default Tasker keeps a Task running for about a minute; this holds the phone awake for as long as it runs.",
        )


@dataclass
class Audit:
    """The whole answer: every Project's score, and how much was looked at."""

    projects: list[ProjectScore]
    profiles_checked: int
    tasks_checked: int

    @property
    def findings(self) -> int:
        """How many things were found, across every Project."""
        return sum(len(project.findings) for project in self.projects)


def audit(state: RunState) -> Audit:
    """Read the loaded configuration for what keeps the phone busy, and score each Project.

    Only Profiles that are on, in Projects that are on, count for the Profile findings; a Task is read whether or not
    something that is on starts it, since a Task can be run by hand, a shortcut or another app.  Projects are in order of
    score, worst first, and a Project with nothing found is not in the list.  Safe to call with nothing loaded.
    """
    run = _Audit(state)
    run.read_profiles()
    run.read_tasks()
    grouped: dict[str, ProjectScore] = {}
    for finding in run.findings:
        grouped.setdefault(finding.project, ProjectScore(finding.project)).findings.append(finding)
    for score in grouped.values():
        score.findings.sort(key=lambda found: (-found.points, found.where.label))
    ordered = sorted(grouped.values(), key=lambda score: (-score.points, score.name.casefold()))
    logger.debug(f"batteryaudit: {run.profiles_checked} Profiles, {run.tasks_checked} Tasks, {len(ordered)} Projects")
    return Audit(ordered, run.profiles_checked, run.tasks_checked)


# ##################################################################################
# The report.
# ##################################################################################
def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _current_xml_file(state: RunState) -> str:
    """The path of the XML file being read (see taskflow._current_xml_file)."""
    file_to_get = state.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) and path else "(unknown)"


def _project_name(name: str) -> str:
    return f"Project '{name}'" if name != _NOT_IN_A_PROJECT else "Not in any Project"


def _score_rows(result: Audit) -> list[Row]:
    rows = [
        Row("SCORE BY PROJECT"),
        Row("-" * _REPORT_WIDTH),
        Row(f"  {'Score':>5}  {'Band':<9}{'Wake-ups/day':>13}  Project"),
    ]
    for score in result.projects:
        wakeups = f"{score.wakeups:,}" if score.wakeups else "-"
        target = Target(PROJECT, score.name, score.name) if score.name != _NOT_IN_A_PROJECT else None
        rows.append(Row(f"  {score.points:>5}  {score.band:<9}{wakeups:>13}  {_project_name(score.name)}", target))
    return [*rows, Row("")]


def _finding_rows(result: Audit) -> list[Row]:
    rows = [Row("FINDINGS"), Row("-" * _REPORT_WIDTH)]
    for score in result.projects:
        target = Target(PROJECT, score.name, score.name) if score.name != _NOT_IN_A_PROJECT else None
        rows.append(Row(f"{_project_name(score.name)}   (score {score.points}, {score.band})", target))
        for finding in score.findings:
            rows.append(Row(f"  +{finding.points:<3} {finding.where.label}", finding.where))
            rows.append(Row(f"        {finding.summary}"))
            if finding.detail:
                rows.append(Row(f"        {finding.detail}"))
        rows.append(Row(""))
    return rows


def _weights_rows() -> list[Row]:
    def table(rows: tuple[tuple[float, int], ...], other: int, unit: str) -> str:
        return "; ".join([*(f"up to {limit:g} {unit}: {points}" for limit, points in rows), f"longer: {other}"])

    items = (
        ("A Time condition that repeats, by how often", table(REPEAT_POINTS, REPEAT_POINTS_OTHER, "minutes")),
        (
            "A loop that cannot end, by the shortest Wait in it",
            (
                f"{table(LOOP_POINTS, LOOP_POINTS_OTHER, 'seconds')}; no Wait at all: {LOOP_POINTS_NO_WAIT}; "
                f"a Wait set by a variable: {LOOP_POINTS_UNKNOWN_WAIT}"
            ),
        ),
        (
            "A loop that can be left (a Stop, a way out, or a condition on its Goto)",
            f"{GUARDED_FRACTION:.0%} of the above, and only when it has a Wait -- one without is a loop that finishes",
        ),
        (
            "Keep Device Awake",
            (
                f"on its own: {AWAKE_POINTS}; through a Wait of {_seconds(AWAKE_LONG_WAIT_SECONDS)} or more: "
                f"{AWAKE_WAIT_POINTS}; on a Task that loops, the combination Tasker warns about: {AWAKE_LOOP_POINTS}"
            ),
        ),
        (
            "A repeating Profile whose Task goes online, by how often",
            table(POLL_POINTS, POLL_POINTS_OTHER, "minutes"),
        ),
    )
    rows = [
        Row("HOW THE SCORE IS WORKED OUT"),
        Row("-" * _REPORT_WIDTH),
        Row("Each finding is worth points.  A Project scores its worst finding plus a quarter of the points of"),
        Row("the rest, held to 100, so one terrible thing outweighs a pile of mild ones.  The band is Light from"),
        Row("1, Moderate from 15, Heavy from 40 and Severe from 70.  The weights are a judgement, chosen to put"),
        Row("the worst on top; they are not a measurement of any battery."),
        Row(""),
    ]
    for label, points in items:
        rows += [Row(f"  {label}"), Row(f"      {points}")]
    return [*rows, Row("")]


def _limitations() -> list[Row]:
    return [
        Row("NOTE ON WHAT THIS CANNOT TELL"),
        Row("-" * _REPORT_WIDTH),
        Row("This reads the file, not the phone.  How much a wake-up costs depends on the phone, the radio, how long"),
        Row("the Task runs and what else is awake, so the score ranks what to look at first and is not a measurement."),
        Row("Wake-ups a day are the most a Profile's window allows, and count from the window's start; a Profile with"),
        Row("no start repeats from whenever it was enabled.  Only Profiles that are on, in Projects that are on, are"),
        Row("counted; a Task is read whether or not something that is on starts it.  A loop is a Goto that goes back,"),
        Row("and runs until something ends the Task.  Conditions that make Tasker watch a sensor, a Wi-Fi scan or the"),
        Row("location are not scored, nor is anything a plugin does by itself."),
        Row(""),
    ]


def run_battery_audit(state: RunState) -> tuple[list[Row], dict[str, int]]:
    """Read the configuration and return (report rows, counts).

    The counts are "projects" (with something found), "heavy" (Projects scoring 40 or more), "findings", and what was
    looked at.  Rows rather than finished text, for healthck's reason: the caller saves them as plain text and shows them
    as HTML, and the two must be one report.
    """
    result = audit(state)
    counts = {
        "projects": len(result.projects),
        "heavy": sum(score.points >= HEAVY for score in result.projects),
        "findings": result.findings,
        "profiles": result.profiles_checked,
        "tasks": result.tasks_checked,
    }
    rows = [
        Row("MapTasker Battery and Wake-up Audit"),
        Row("=" * _REPORT_WIDTH),
        Row(f"XML file:    {_current_xml_file(state)}"),
        Row(f"Generated:   {clock.now().strftime('%d-%b-%Y %H:%M:%S')}"),
        Row(f"Version:     {MY_VERSION}"),
        Row(""),
        Row(f"Scanned:     {_plural(counts['profiles'], 'Profile')} that are on, {_plural(counts['tasks'], 'Task')}"),
        Row(
            f"Found:       {_plural(counts['findings'], 'thing')} in {_plural(counts['projects'], 'Project')}, "
            f"{counts['heavy']} scoring Heavy or worse"
        ),
        Row(""),
    ]
    if not result.projects:
        return [
            *rows,
            Row("Nothing to report -- no Time condition repeats, no Task loops and none keeps the device awake."),
            Row(""),
            *_limitations(),
        ], counts
    return [*rows, *_score_rows(result), *_finding_rows(result), *_weights_rows(), *_limitations()], counts


def write_battery_report(rows: list[Row], state: RunState) -> str:
    """Write the audit to a timestamped file in the output folder.

    Returns the path written, or "" if the write failed -- named, stamped and handled exactly as outbound's is.
    """
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(BATTERY_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Battery audit could not be written: {error}")
        return ""
    return file_path
