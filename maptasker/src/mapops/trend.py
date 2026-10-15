"""trend: is the configuration getting healthier or messier?  Measure each kept snapshot and compare them."""

#! /usr/bin/env python3

#                                                                                        #
# trend: read every configuration the history (timeline) has kept, measure each one, and   #
#        say which way things are going -- per Project and for the whole configuration.   #
#                                                                                        #
# timeline keeps the configurations and Changes Since says WHAT differs between two of      #
# them.  Neither answers the question people ask about a configuration that has grown for    #
# years: is it getting better or worse?  That is a question about a number moving over time,  #
# so each snapshot is boiled down to a handful of numbers and the numbers are lined up.     #
#                                                                                        #
# WHAT IS MEASURED, FOR EACH PROJECT AND FOR THE WHOLE                                      #
#                                                                                        #
#   size           Profiles, Tasks, Scenes and actions.  Reported, never judged: a bigger       #
#                  configuration is not a worse one.                                        #
#   Task length    the longest Task, and how many Tasks are over LONG_TASK_ACTIONS (Tasker's    #
#                  own default warning limit for "too many actions").                         #
#   nesting depth  how deep the If/For blocks of the most nested Task go -- taskflow's own      #
#                  reading of each Task, so it agrees with the Task Flow check.                #
#   call depth     how many Perform Tasks deep the longest chain of calls goes.  Only calls by     #
#                  name are followed: one whose name is built from a variable is decided on the   #
#                  device, and a Task that (through others) calls itself is counted, not walked.   #
#   findings       the Health Check's, as errors, warnings and information -- with one pass left    #
#                  out, the check for plugins missing from the device's app list.  That one asks    #
#                  the DEVICE, not the snapshot, so its answer would move from day to day while the  #
#                  configuration stood still, and a trend has to move only when the file does.       #
#                                                                                        #
# Lower is better for everything but size, so "healthier" means those went down and "messier"     #
# means they went up; where some rose and some fell it says about the same rather than netting     #
# unlike things against each other.                                                         #
#                                                                                        #
# MEASURED ONCE                                                                           #
#                                                                                        #
# Reading a snapshot back and running the Health Check on it takes a second or two, and thirty    #
# of them is a minute.  A snapshot never changes -- the history names it by a digest of its        #
# content -- so what is measured is kept beside the history and reused, and a later look costs     #
# only the snapshots made since.  The numbers carry METRICS_VERSION: a release that measures one    #
# more thing bumps it, and the old ones are measured again rather than shown with a gap.          #
#                                                                                        #
# WHICH CONFIGURATIONS TO COMPARE                                                          #
#                                                                                        #
# The history holds every file loaded, and people load more than one -- a phone, a tablet, a        #
# test file.  A trend across files that are not versions of one another is noise, so a Series is     #
# made from the snapshots of one `source` (the file's name) when asked, and the dialog starts on    #
# the source of the file that is open.                                                      #
#                                                                                        #
# Same contract as healthck and taskflow: no GUI, nothing in PrimeItems written.  Reading a snapshot  #
# goes through timecomp, and so through diffload's isolation, which is not safe to run twice at     #
# once -- hence the lock.                                                                  #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from maptasker.src.analysis import healthck, plugchk, taskflow, timecomp
from maptasker.src.core import timeline
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.mapjump import actions_in_map_order
from maptasker.src.core.primitem import RunState
from maptasker.src.core.sysconst import logger
from maptasker.src.mapops import tnupdate

if TYPE_CHECKING:
    from collections.abc import Iterable

# Bumped when a release measures something more (or measures something differently).
METRICS_VERSION = 2
METRICS_FOLDER = "trend_metrics"

# A Task with more actions than this is "long".  Tasker's own default for the warning limit the Health
# Check's LARGE-TASK uses, so the two agree on a default configuration.
LONG_TASK_ACTIONS = 100

# Perform Task's code, and the argument that names the Task it calls.
_PERFORM_TASK = "130"
_PERFORM_NAME_ARG = "0"

# What a verdict can be.
HEALTHIER = "healthier"
MESSIER = "messier"
STEADY = "about the same"
TOO_FEW = "not enough history"

# How many Projects the 'biggest movers' lists name in each direction.
MOVERS_SHOWN = 5

# How many of a messier Project's new problems are spelled out under it.
NEW_PROBLEMS_SHOWN = 5

# One measure at a time, so two dashboards (or a dashboard and a CLI run) cannot be inside diffload's
# isolation window together.
_LOCK = threading.Lock()


# ##################################################################################
# What is measured.
# ##################################################################################
@dataclass
class Measures:
    """The numbers for one Project, or for the whole configuration."""

    profiles: int = 0
    tasks: int = 0
    scenes: int = 0
    actions: int = 0
    longest_task: int = 0
    longest_task_name: str = ""
    long_tasks: int = 0
    max_depth: int = 0
    deepest_task: str = ""
    call_depth: int = 0
    call_chain: list[str] = field(default_factory=list)
    recursive: int = 0
    errors: int = 0
    warnings: int = 0
    infos: int = 0

    @property
    def problems(self) -> int:
        """Errors and warnings: what is wrong, as opposed to what is merely worth knowing."""
        return self.errors + self.warnings


@dataclass
class Problem:
    """One error or warning the Health Check found in a Project, kept so a later look can say which ones are new."""

    severity: str
    tag: str
    where: str
    detail: str
    key: str  # what makes it the same problem in another snapshot: its tag and the object it is about

    @property
    def is_error(self) -> bool:
        """True for an error, false for a warning."""
        return self.severity == healthck.ERROR


@dataclass
class SnapshotMetrics:
    """One kept configuration, measured."""

    digest: str
    when: str  # ISO 8601, local time with its offset
    source: str
    total: Measures = field(default_factory=Measures)
    projects: dict[str, Measures] = field(default_factory=dict)
    version: int = METRICS_VERSION
    # Each Project's errors and warnings (not the information findings, which are not "problems").
    problems: dict[str, list[Problem]] = field(default_factory=dict)

    @property
    def moment(self) -> datetime:
        """When the snapshot was taken, as a datetime."""
        return datetime.fromisoformat(self.when)

    def to_json(self) -> str:
        """The metrics as text, for keeping."""
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str) -> SnapshotMetrics:
        """Metrics read back.  Raises ValueError, KeyError or TypeError for text that is not them."""
        raw = json.loads(text)
        return cls(
            digest=raw["digest"],
            when=raw["when"],
            source=raw["source"],
            total=Measures(**raw["total"]),
            projects={name: Measures(**values) for name, values in raw["projects"].items()},
            version=raw["version"],
            problems={name: [Problem(**values) for values in found] for name, found in raw.get("problems", {}).items()},
        )


# ##################################################################################
# Measuring one configuration.
# ##################################################################################
@dataclass
class _TaskFacts:
    """What is known of one Task from reading it once."""

    name: str
    actions: int
    depth: int
    calls: list[str]  # names of the Tasks it performs, in order, without those that are built from variables


def _task_facts(state: RunState) -> dict[str, _TaskFacts]:
    """{Task id: facts}, reading each Task's flow once."""
    facts: dict[str, _TaskFacts] = {}
    for task_id, entry in state.tasker_root_elements.get("all_tasks", {}).items():
        flow = taskflow.analyze_task_flow(task_id, state=state)
        if flow is None:
            continue
        facts[task_id] = _TaskFacts(
            name=entry["name"],
            actions=len(flow.steps),
            depth=max(flow.depth, default=0),
            calls=_calls_of(entry["xml"]),
        )
    return facts


def _calls_of(task_element: object) -> list[str]:
    """The Tasks a Task performs by name.  A switched-off action is not a call, and a name with a variable in it is not followed."""
    calls = []
    for action in actions_in_map_order(task_element):
        if (action.findtext("code") or "").strip() != _PERFORM_TASK or action.find("on") is not None:
            continue
        name = taskflow.action_argument(action, _PERFORM_NAME_ARG)
        if name and "%" not in name:
            calls.append(name)
    return calls


def _call_depths(facts: dict[str, _TaskFacts], by_name: dict[str, str]) -> tuple[dict[str, list[str]], set[str]]:
    """({Task id: the longest chain of Tasks it starts, itself first}, the ids of Tasks caught in a loop of calls).

    A call back into a Task still being walked ends that chain there and marks the Task as recursive; it is
    counted once, rather than followed round for ever.
    """
    chains: dict[str, list[str]] = {}
    recursive: set[str] = set()
    walking: set[str] = set()

    def chain(task_id: str) -> list[str]:
        if task_id in chains:
            return chains[task_id]
        walking.add(task_id)
        longest: list[str] = []
        for name in facts[task_id].calls:
            callee = by_name.get(name)
            if callee is None or callee not in facts:
                continue
            if callee in walking:
                recursive.add(callee)
                continue
            candidate = chain(callee)
            if len(candidate) > len(longest):
                longest = candidate
        walking.discard(task_id)
        chains[task_id] = [facts[task_id].name, *longest]
        return chains[task_id]

    for task_id in facts:
        chain(task_id)
    return chains, recursive


def _measures_for(
    task_ids: Iterable[str],
    facts: dict[str, _TaskFacts],
    chains: dict[str, list[str]],
    recursive: set[str],
) -> Measures:
    """The Task-shaped numbers for a set of Tasks: their count, length, nesting and call depth."""
    measures = Measures()
    for task_id in task_ids:
        info = facts.get(task_id)
        if info is None:
            continue
        measures.tasks += 1
        measures.actions += info.actions
        measures.long_tasks += info.actions > LONG_TASK_ACTIONS
        if info.actions > measures.longest_task:
            measures.longest_task, measures.longest_task_name = info.actions, info.name
        if info.depth > measures.max_depth:
            measures.max_depth, measures.deepest_task = info.depth, info.name
        chain = chains.get(task_id, [])
        if len(chain) - 1 > measures.call_depth:
            measures.call_depth, measures.call_chain = len(chain) - 1, chain
        measures.recursive += task_id in recursive
    return measures


def _count(counts: Measures, severity: str) -> None:
    """Add one finding of this severity to a set of counts."""
    if severity == healthck.ERROR:
        counts.errors += 1
    elif severity == healthck.WARNING:
        counts.warnings += 1
    else:
        counts.infos += 1


def _problem_key(finding: healthck.Finding) -> str:
    """What makes a finding the same one in another snapshot: its tag and the object it is about.

    Not its detail, which can carry a number ("105 actions") that moves while the problem stays put.
    """
    target = finding.target
    if target is None:
        return f"{finding.tag}|{finding.where}"
    return f"{finding.tag}|{target.kind}|{target.key}|{target.action}|{target.part}"


def _findings_by_project(state: RunState) -> tuple[dict[str, Measures], Measures, dict[str, list[Problem]]]:
    """The Health Check's findings counted per Project, and in all, with each Project's errors and warnings kept.

    Findings with no Project go in the total only.
    """
    index = healthck.collect_findings(plugchk.TAGS, state=state)
    per_project: dict[str, Measures] = {}
    problems: dict[str, list[Problem]] = {}
    total = Measures()
    for finding in index.findings:
        _count(total, finding.severity)
        project = finding.target.project if finding.target is not None else ""
        if project:
            _count(per_project.setdefault(project, Measures()), finding.severity)
            if finding.severity in (healthck.ERROR, healthck.WARNING):
                problems.setdefault(project, []).append(
                    Problem(finding.severity, finding.tag, finding.where, finding.detail, _problem_key(finding))
                )
    return per_project, total, problems


def _project_members(name: str, state: RunState) -> tuple[int, int, set[str]]:
    """(Profiles, Scenes, the ids of the Tasks) of a Project -- its Tasks include the anonymous ones its Profiles run."""
    scope = tnupdate.scope_of(tnupdate.PROJECT, name, state.tasker_root_elements)
    if scope is None:
        return 0, 0, set()
    return len(scope["all_profiles"]), len(scope["all_scenes"]), set(scope["all_tasks"])


def measure_state(state: RunState) -> tuple[Measures, dict[str, Measures], dict[str, list[Problem]]]:
    """Measure the configuration in `state`: (the whole of it, each Project, each Project's errors and warnings).

    Reads state.tasker_root_elements and nothing else.  `state` may be a stand-in built for the purpose (see
    measure_snapshot) -- nothing here writes to it.
    """
    tables = state.tasker_root_elements
    facts = _task_facts(state)
    by_name = {entry["name"]: task_id for task_id, entry in tables.get("all_tasks", {}).items() if entry["name"]}
    chains, recursive = _call_depths(facts, by_name)
    per_project_findings, total_findings, problems = _findings_by_project(state)

    projects: dict[str, Measures] = {}
    for name in tables.get("all_projects", {}):
        profiles, scenes, task_ids = _project_members(name, state)
        measures = _measures_for(task_ids, facts, chains, recursive)
        measures.profiles, measures.scenes = profiles, scenes
        found = per_project_findings.get(name, Measures())
        measures.errors, measures.warnings, measures.infos = found.errors, found.warnings, found.infos
        projects[name] = measures

    total = _measures_for(facts, facts, chains, recursive)
    total.profiles, total.scenes = len(tables.get("all_profiles", {})), len(tables.get("all_scenes", {}))
    total.errors, total.warnings, total.infos = total_findings.errors, total_findings.warnings, total_findings.infos
    return total, projects, problems


# ##################################################################################
# Measuring a snapshot, once.
# ##################################################################################
def _metrics_path(snapshot: timeline.Snapshot) -> Path | None:
    """Where a snapshot's measurements are kept: beside the history, under its digest.  None if there is no history folder."""
    folder = timeline.history_folder(create=False)
    return folder / METRICS_FOLDER / f"{snapshot.digest}.json" if folder is not None else None


def _kept(snapshot: timeline.Snapshot) -> SnapshotMetrics | None:
    """The measurements kept for a snapshot, or None if there are none or they are from an older release."""
    path = _metrics_path(snapshot)
    if path is None or not path.is_file():
        return None
    try:
        metrics = SnapshotMetrics.from_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.error(f"Trend metrics could not be read: {error}")
        return None
    return metrics if metrics.version == METRICS_VERSION else None


def _keep(metrics: SnapshotMetrics, snapshot: timeline.Snapshot) -> None:
    """Keep a snapshot's measurements.  A failure is logged and costs only the time to measure it again."""
    path = _metrics_path(snapshot)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(metrics.to_json())
        Path(temporary).replace(path)
    except OSError as error:
        logger.error(f"Trend metrics could not be kept: {error}")


def measure_snapshot(snapshot: timeline.Snapshot, state: RunState) -> tuple[SnapshotMetrics | None, str]:
    """Measure a snapshot, from what is kept if it has been measured before.  (metrics, "") or (None, why not).

    `state` is the run's, used only to read the snapshot back in (diffload's isolation needs it); what is
    measured is a stand-in built from the snapshot's own tables, so the loaded configuration is untouched.
    """
    kept = _kept(snapshot)
    if kept is not None:
        # The numbers are the content's; when it was loaded, and as what, are this snapshot's.  The same
        # content can be loaded twice -- a backup restored from last month -- and both are points in time.
        kept.when, kept.source = snapshot.when.isoformat(), snapshot.source
        return kept, ""
    with _LOCK:
        configuration, problem = timecomp.configuration_of(snapshot, state=state)
    if configuration is None:
        return None, problem
    stand_in = RunState()
    stand_in.tasker_root_elements = configuration.tables
    # xml_root is declared as None-only on RunState; the loaded value is an Element, set the way a load sets it.
    vars(stand_in).update(xml_root=configuration.root)
    stand_in.program_arguments = ProgramArguments(task_action_warning_limit=LONG_TASK_ACTIONS)
    total, projects, problems = measure_state(stand_in)
    metrics = SnapshotMetrics(
        snapshot.digest, snapshot.when.isoformat(), snapshot.source, total, projects, problems=problems
    )
    _keep(metrics, snapshot)
    return metrics, ""


# ##################################################################################
# A run of snapshots.
# ##################################################################################
@dataclass
class Progress:
    """What building a Series is doing, for a dialog to read from another thread.  One writer, one reader."""

    text: str = ""
    done: int = 0
    total: int = 0


@dataclass
class Series:
    """The measured snapshots, oldest first, and why any were left out."""

    points: list[SnapshotMetrics] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    stopped: bool = False

    def project_names(self) -> list[str]:
        """Every Project that appears in any snapshot, alphabetically."""
        return sorted({name for point in self.points for name in point.projects}, key=str.casefold)

    def of_project(self, name: str) -> list[tuple[SnapshotMetrics, Measures | None]]:
        """(snapshot, the Project's numbers there) for each snapshot; None where the Project did not exist yet, or no longer does."""
        return [(point, point.projects.get(name)) for point in self.points]


# The timestamp Tasker's own automatic backups put in a file's name: backup_20261011_111635.xml.
_STAMP = re.compile(r"[_-]?\d{8}[_-]\d{6}")


def family(source: str) -> str:
    """A snapshot's source with any timestamp taken out, so successive backups of one phone are one family: 'backup.xml'."""
    return _STAMP.sub("", source)


def families() -> list[str]:
    """The families of file the history holds snapshots of, the one with most snapshots first."""
    counts: dict[str, int] = {}
    for snapshot in timeline.snapshots():
        counts[family(snapshot.source)] = counts.get(family(snapshot.source), 0) + 1
    return sorted(counts, key=lambda name: (-counts[name], name.casefold()))


def build_series(
    state: RunState,
    source: str | None = None,
    progress: Progress | None = None,
    stop: threading.Event | None = None,
) -> Series:
    """Measure every snapshot (of one family -- see family() -- if `source` is given) not yet measured, and return them in order.

    Slow only the first time, and only for snapshots not seen before: see "MEASURED ONCE" above.  `stop` ends it
    between snapshots with what has been measured so far.
    """
    wanted = [
        snapshot for snapshot in timeline.snapshots() if source is None or family(snapshot.source) == family(source)
    ]
    series = Series()
    progress = progress or Progress()
    progress.total, progress.done = len(wanted), 0
    for snapshot in wanted:
        if stop is not None and stop.is_set():
            series.stopped = True
            break
        progress.text = f"Measuring {snapshot.described()} ({progress.done + 1} of {progress.total})..."
        metrics, problem = measure_snapshot(snapshot, state)
        progress.done += 1
        if metrics is None:
            series.problems.append(f"{snapshot.described()}: {problem}")
        else:
            series.points.append(metrics)
    return series


# ##################################################################################
# Which way is it going?
# ##################################################################################
@dataclass(frozen=True)
class Measure:
    """One number that is judged: what it is called, how to read it off the metrics, and that lower is better."""

    key: str
    label: str


# Everything judged is better lower.  Size is deliberately not in here.
JUDGED = (
    Measure("errors", "Errors"),
    Measure("warnings", "Warnings"),
    Measure("long_tasks", f"Tasks over {LONG_TASK_ACTIONS} actions"),
    Measure("longest_task", "Longest Task (actions)"),
    Measure("max_depth", "Deepest nesting"),
    Measure("call_depth", "Longest call chain"),
)


@dataclass
class Move:
    """One judged number, before and after."""

    label: str
    before: int
    after: int

    @property
    def delta(self) -> int:
        """After minus before."""
        return self.after - self.before


@dataclass
class Verdict:
    """Which way it went between two points, and the numbers behind it."""

    label: str
    moves: list[Move]

    @property
    def worse(self) -> list[Move]:
        """The judged numbers that went up."""
        return [move for move in self.moves if move.delta > 0]

    @property
    def better(self) -> list[Move]:
        """The judged numbers that went down."""
        return [move for move in self.moves if move.delta < 0]

    def summary(self) -> str:
        """One sentence: the verdict and what moved most."""
        moved = sorted((move for move in self.moves if move.delta), key=lambda move: -abs(move.delta))
        if not moved:
            return f"{self.label.capitalize()}: none of the numbers changed."
        parts = ", ".join(f"{move.label.lower()} {move.delta:+d}" for move in moved[:3])
        return f"{self.label.capitalize()}: {parts}."


def judge(before: Measures | None, after: Measures | None) -> Verdict:
    """Compare two sets of numbers.  Healthier if some fell and none rose, messier if some rose and none fell.

    Where some rose and some fell the answer is "about the same": a Project with one fewer error and one more
    long Task is not clearly either, and netting unlike things against each other would pretend it was.
    """
    if before is None or after is None:
        return Verdict(TOO_FEW, [])
    moves = [Move(measure.label, getattr(before, measure.key), getattr(after, measure.key)) for measure in JUDGED]
    verdict = Verdict(STEADY, moves)
    if verdict.better and not verdict.worse:
        verdict.label = HEALTHIER
    elif verdict.worse and not verdict.better:
        verdict.label = MESSIER
    return verdict


def overall(series: Series) -> tuple[Verdict, Verdict]:
    """(the whole history, the last step): the first snapshot against the last, and the one before the last against the last."""
    if len(series.points) < 2:
        return Verdict(TOO_FEW, []), Verdict(TOO_FEW, [])
    first, previous, last = series.points[0], series.points[-2], series.points[-1]
    return judge(first.total, last.total), judge(previous.total, last.total)


@dataclass
class Mover:
    """A Project and how its problems and its longest Task changed over the whole history."""

    name: str
    problems_before: int
    problems_after: int
    longest_before: int
    longest_after: int
    new_problems: list[Problem] = field(default_factory=list)  # errors first; all of them, not just those shown

    @property
    def problem_delta(self) -> int:
        """Errors plus warnings, after minus before."""
        return self.problems_after - self.problems_before

    @property
    def longest_delta(self) -> int:
        """The longest Task's length, after minus before."""
        return self.longest_after - self.longest_before


def new_problems(before: SnapshotMetrics, after: SnapshotMetrics, project: str) -> list[Problem]:
    """The Project's errors and warnings in `after` that were not in `before`, errors first, as `after` words them.

    Matched by tag and object, a copy at a time: a Project that had two of one finding and now has three has one new.
    """
    unmatched = Counter(problem.key for problem in before.problems.get(project, []))
    new = []
    for problem in after.problems.get(project, []):
        if unmatched[problem.key] > 0:
            unmatched[problem.key] -= 1
        else:
            new.append(problem)
    return sorted(new, key=lambda problem: not problem.is_error)


def movers(series: Series) -> tuple[list[Mover], list[Mover]]:
    """(the Projects that got messier, the ones that got healthier), most-moved first, of those in the first and last snapshot."""
    if len(series.points) < 2:
        return [], []
    first, last = series.points[0], series.points[-1]
    moved = [
        Mover(
            name,
            first.projects[name].problems,
            last.projects[name].problems,
            first.projects[name].longest_task,
            last.projects[name].longest_task,
            new_problems(first, last, name),
        )
        for name in sorted(first.projects.keys() & last.projects.keys(), key=str.casefold)
    ]
    worse = sorted(
        (item for item in moved if item.problem_delta > 0 or (item.problem_delta == 0 and item.longest_delta > 0)),
        key=lambda item: (-item.problem_delta, -item.longest_delta),
    )
    better = sorted(
        (item for item in moved if item.problem_delta < 0), key=lambda item: (item.problem_delta, item.longest_delta)
    )
    return worse[:MOVERS_SHOWN], better[:MOVERS_SHOWN]


# ##################################################################################
# Saying it.
# ##################################################################################
def new_problem_lines(mover: Mover) -> list[str]:
    """The Project's new problems, one line each, up to NEW_PROBLEMS_SHOWN, then '... and N more'."""
    lines = [
        f"{problem.severity} {problem.tag}: {problem.where}" for problem in mover.new_problems[:NEW_PROBLEMS_SHOWN]
    ]
    if len(mover.new_problems) > NEW_PROBLEMS_SHOWN:
        lines.append(f"... and {len(mover.new_problems) - NEW_PROBLEMS_SHOWN} more")
    return lines


_COLUMNS = (
    ("Date", None),
    ("Prof", "profiles"),
    ("Task", "tasks"),
    ("Actions", "actions"),
    ("Longest", "longest_task"),
    (f">{LONG_TASK_ACTIONS}", "long_tasks"),
    ("Depth", "max_depth"),
    ("Calls", "call_depth"),
    ("Err", "errors"),
    ("Warn", "warnings"),
    ("Info", "infos"),
)


def as_text(series: Series, project: str | None = None) -> str:
    """The trend as plain text -- the verdict, then one row per snapshot -- for a forum post or a nightly job's log."""
    scope = f"Project '{project}'" if project else "The whole configuration"
    lines = [f"MapTasker trend: {scope}", "=" * 78]
    if len(series.points) < 2:
        lines.append("Not enough history: a trend needs at least two kept configurations.")
    elif project is None:
        whole, last_step = overall(series)
        lines += [f"Since the first kept:   {whole.summary()}", f"Since the one before:   {last_step.summary()}"]
        worse, better = movers(series)
        for mover in worse:
            lines.append(
                f"Messier:   {mover.name} (problems {mover.problem_delta:+d}, longest Task {mover.longest_delta:+d})"
            )
            lines += [f"             new: {line}" for line in new_problem_lines(mover)]
        lines += [
            f"Healthier: {mover.name} (problems {mover.problem_delta:+d}, longest Task {mover.longest_delta:+d})"
            for mover in better
        ]
    else:
        points = series.of_project(project)
        present = [measures for _, measures in points if measures is not None]
        if len(present) >= 2:
            lines.append(f"Since it first appeared:   {judge(present[0], present[-1]).summary()}")
    lines += ["", "  ".join(f"{title:>7}" if key else f"{title:<17}" for title, key in _COLUMNS)]
    for point, measures in series.of_project(project) if project else [(p, p.total) for p in series.points]:
        row = f"{point.moment:%d-%b-%Y %H:%M}".ljust(17)
        if measures is None:
            lines.append(f"{row}  (not in this configuration)")
            continue
        lines.append(row + "  " + "  ".join(f"{getattr(measures, key):>7}" for _, key in _COLUMNS[1:]))
    lines += [f"\nNot measured: {problem}" for problem in series.problems]
    return "\n".join(lines)
