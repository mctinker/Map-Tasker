"""livemon: what is running on the phone, as a stream of events -- and whether What Fires When said it would."""

#! /usr/bin/env python3

#                                                                                        #
# livemon: the model behind the Live Run Monitor.                                         #
#                                                                                        #
# The device answers one question, over and over: which Tasks are running and which        #
# Profiles are active RIGHT NOW (Tasker's own %TRUN and %PACTIVE; see devicemonitor).  A    #
# stream is made of the differences between answers, and that is all this module does:     #
#                                                                                        #
#   parse_window   a run of samples the device wrote, back into Samples                    #
#   Tracker        consecutive samples in, events out -- a Profile became active, a Task     #
#                  started, a Task finished -- and which objects are lit at this moment      #
#   lights_js      those objects, as the browser-side code that lights them in the Diagram   #
#   compare        what the device had active against what What Fires When predicted for    #
#                  that moment                                                             #
#                                                                                        #
# Same contract as firesim and taskstep: reads PrimeItems.tasker_root_elements and nothing  #
# else -- no network, no GUI -- so all of it is tested without a phone.                     #
#                                                                                        #
# WHAT A SAMPLE CAN AND CANNOT SEE, SAID PLAINLY BECAUSE A MONITOR GETS TRUSTED               #
#                                                                                        #
#   * It is polling.  A Task that starts and ends between two samples is not seen at all;    #
#     one seen in a single sample is marked brief, and its length is not known.  The device   #
#     samples every few hundred milliseconds, so a Task that runs for a moment is usually      #
#     caught -- usually.                                                                    #
#   * It sees names, not objects.  Two Tasks with one name light together, and a Task with    #
#     no name cannot be matched to anything in the backup.                                    #
#   * Tasker lists names separated by commas, and a name may hold one: the known names are     #
#     used to put such a name back together, and a name that is not in the backup is taken       #
#     as written.                                                                         #
#   * A Profile is ACTIVE for as long as its conditions hold.  One that fires on an Event       #
#     and ends at once is a Task start, not a state, and is only seen if its Task is.          #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from maptasker.src.core import assettext
from maptasker.src.core.mapjump import PROFILE, TASK, Row, Target

if TYPE_CHECKING:
    from collections.abc import Iterable

    from maptasker.src.analysis import firesim
    from maptasker.src.core.primitem import RunState

# How the device writes a window of samples: fields within a sample, and samples within the window.  Spelled
# unlikely enough that neither can be in a Task or Profile name, and written here so the Task that makes
# them and the code that reads them cannot disagree.
FIELD_SEPARATOR = "|~|"
SAMPLE_SEPARATOR = "|#|"

# What the saved log is called.
MONITOR_FILE = "MapTasker_Monitor.txt"

# What happened.
PROFILE_ACTIVE = "profile active"
PROFILE_INACTIVE = "profile inactive"
TASK_STARTED = "task started"
TASK_FINISHED = "task finished"

# How the Diagram lights an object: running or active now, or only just now.
LIT_ON = "on"
LIT_RECENT = "recent"

# How long an object stays marked after it stops, by default.
RECENT_SECONDS = 10

# How many names a comma-split may glue back together to find a name that holds commas.
_MAX_GLUED = 6

# What Tasker writes for a built-in variable that has no value: its own name.
_UNSET = {"%TRUN", "%PACTIVE", "%BATT", "%TIMEMS"}

# How many fields a sample must have (time, running, active), and where the optional battery is.
_REQUIRED_FIELDS = 3
_BATTERY_FIELD = 3


def local_time(when_ms: int) -> datetime:
    """An epoch time in milliseconds as a local time of day, with no zone attached.

    Tasker's %TIMEMS is the same instant everywhere; what is shown is that instant in THIS computer's zone, which
    is the phone's whenever the two are in the same place.  A prediction made for it is only as right as that.
    """
    return datetime.fromtimestamp(when_ms / 1000, tz=UTC).astimezone().replace(tzinfo=None)


# ##################################################################################
# What the device said.
# ##################################################################################
@dataclass(frozen=True)
class Sample:
    """One look at the phone: the moment, which Tasks were running, which Profiles were active, the battery."""

    when_ms: int
    running: frozenset[str]
    active: frozenset[str]
    battery: int | None = None

    @property
    def when(self) -> datetime:
        """The moment as a local time (see local_time)."""
        return local_time(self.when_ms)


def split_names(text: str, known: Iterable[str] = ()) -> set[str]:
    """The names in one of Tasker's comma-separated lists.

    A name may itself hold a comma ('Wake Up, Then Sleep'), which a plain split would tear in two.  So pieces are
    glued back together, longest first, whenever the result is a name from the backup; anything else is taken
    as one piece.  A list Tasker left unset -- the variable's own name -- is empty.
    """
    wanted = set(known)
    pieces = [piece.strip() for piece in text.split(",")]
    names: set[str] = set()
    index = 0
    while index < len(pieces):
        for length in range(min(_MAX_GLUED, len(pieces) - index), 1, -1):
            glued = ", ".join(pieces[index : index + length])
            if glued in wanted:
                names.add(glued)
                index += length
                break
        else:
            if pieces[index]:
                names.add(pieces[index])
            index += 1
    return names


def _number(text: str) -> int | None:
    """An integer out of a field, or None for anything else (an unset variable is its own name)."""
    stripped = text.strip()
    return int(stripped) if stripped.lstrip("-").isdigit() else None


def parse_window(text: str, tasks: Iterable[str] = (), profiles: Iterable[str] = ()) -> list[Sample]:
    """The samples a window of the device's answer holds, oldest first.  A sample that is not one is left out.

    `tasks` and `profiles` are the names in the backup, for putting a name with a comma in it back together.
    Samples whose time cannot be read are dropped rather than guessed at: an event with no moment is no use to
    a log, and a malformed record is the device being interrupted, which the next window makes up for.
    """
    known_tasks, known_profiles = set(tasks), set(profiles)
    samples: list[Sample] = []
    for record in text.split(SAMPLE_SEPARATOR):
        fields = record.strip().split(FIELD_SEPARATOR)
        if len(fields) < _REQUIRED_FIELDS:
            continue
        when = _number(fields[0])
        if when is None:
            continue
        running = "" if fields[1].strip() in _UNSET else fields[1]
        active = "" if fields[2].strip() in _UNSET else fields[2]
        battery = _number(fields[_BATTERY_FIELD]) if len(fields) > _BATTERY_FIELD else None
        samples.append(
            Sample(
                when,
                frozenset(split_names(running, known_tasks)),
                frozenset(split_names(active, known_profiles)),
                battery,
            ),
        )
    return samples


# ##################################################################################
# Which names are which objects.
# ##################################################################################
@dataclass
class NameIndex:
    """The Profiles and Tasks of the backup by name, each a list: names are not unique in Tasker."""

    profiles: dict[str, list[Target]] = field(default_factory=dict[str, list[Target]])
    tasks: dict[str, list[Target]] = field(default_factory=dict[str, list[Target]])
    # Tasks that are MapTasker's own, which are always running when it looks.
    ignored: frozenset[str] = frozenset()

    def duplicated(self, name: str) -> bool:
        """Whether more than one Profile has this name, so that a state of 'it' says nothing about which."""
        return len(self.profiles.get(name, [])) > 1


def _owners(kind: str, state: RunState) -> dict[str, str]:
    """{member id: owning Project name} for one of a Project's lists (see plugchk._owners)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def build_index(state: RunState, ignore: Iterable[str] = ()) -> NameIndex:
    """Every named Profile and Task of the loaded configuration, ready to be matched against the device's lists."""
    index = NameIndex(ignored=frozenset(ignore))
    root = state.tasker_root_elements
    if not root:
        return index
    for kind, table_name, owner_tag, found in (
        (PROFILE, "all_profiles", "pids", index.profiles),
        (TASK, "all_tasks", "tids", index.tasks),
    ):
        owners = _owners(owner_tag, state=state)
        for item_id, item in root[table_name].items():
            if item["name"]:
                found.setdefault(item["name"], []).append(Target(kind, item_id, item["name"], owners.get(item_id, "")))
    return index


# ##################################################################################
# The stream.
# ##################################################################################
@dataclass
class Event:
    """One thing that changed between two samples."""

    when_ms: int
    kind: str
    name: str
    targets: tuple[Target, ...] = ()
    note: str = ""

    @property
    def clock(self) -> str:
        """The moment as a time of day, with milliseconds -- the unit the samples are taken in."""
        return local_time(self.when_ms).strftime("%H:%M:%S.%f")[:-3]

    def line(self) -> str:
        """The event as one line of a log."""
        what = {
            PROFILE_ACTIVE: "Profile became active",
            PROFILE_INACTIVE: "Profile became inactive",
            TASK_STARTED: "Task started",
            TASK_FINISHED: "Task finished",
        }[self.kind]
        tail = f"  -- {self.note}" if self.note else ""
        return f"{self.clock}  {what}: {self.name}{'' if self.targets else '  (not in this backup)'}{tail}"


class Tracker:
    """Samples in, events out, and a memory of what is lit.

    Holds only what the next sample needs to be understood against: what was running and active before it, when
    each started, and when each name was last seen -- which is what 'only just now' is measured from.
    """

    def __init__(self, index: NameIndex) -> None:
        """`index` says which names are which objects, and which Tasks to pass over."""
        self.index = index
        self.running: frozenset[str] = frozenset()
        self.active: frozenset[str] = frozenset()
        self.battery: int | None = None
        self.now_ms = 0
        self.samples = 0
        self.events: list[Event] = []
        self._started: dict[str, tuple[int, int]] = {}  # name -> (when it was first seen, in how many samples)
        self._last_seen: dict[tuple[str, str], int] = {}  # (kind, name) -> the last sample it was seen in
        self._first = True

    def feed(self, samples: Iterable[Sample]) -> list[Event]:
        """Fold in samples, oldest first, and return the events they made (also kept in `events`)."""
        made: list[Event] = []
        for sample in samples:
            running = sample.running - self.index.ignored
            made.extend(self._profiles(sample))
            made.extend(self._tasks(sample, running))
            self.running, self.active, self.now_ms = running, sample.active, sample.when_ms
            self.battery = sample.battery if sample.battery is not None else self.battery
            self.samples += 1
            self._first = False
            for name in running:
                self._last_seen[(TASK, name)] = sample.when_ms
            for name in sample.active:
                self._last_seen[(PROFILE, name)] = sample.when_ms
        self.events.extend(made)
        return made

    def _profiles(self, sample: Sample) -> list[Event]:
        """Profiles that became active or inactive."""
        began = sorted(sample.active - self.active)
        ended = sorted(self.active - sample.active)
        note = "already active when monitoring began" if self._first else ""
        return [self._event(sample.when_ms, PROFILE_ACTIVE, name, note) for name in began] + [
            self._event(sample.when_ms, PROFILE_INACTIVE, name) for name in ended
        ]

    def _tasks(self, sample: Sample, running: frozenset[str]) -> list[Event]:
        """Tasks that started or finished, and how long a finished one was seen for."""
        events: list[Event] = []
        for name in sorted(running - self.running):
            self._started[name] = (sample.when_ms, 1)
            events.append(
                self._event(
                    sample.when_ms, TASK_STARTED, name, "already running when monitoring began" if self._first else ""
                )
            )
        for name in sorted(running & self.running):
            began, seen = self._started.get(name, (sample.when_ms, 0))
            self._started[name] = (began, seen + 1)
        for name in sorted(self.running - running):
            began, seen = self._started.pop(name, (sample.when_ms, 1))
            note = (
                "seen in one sample only, so shorter than the sampling interval and its length is not known"
                if seen <= 1
                else f"running for about {max(sample.when_ms - began, 0) / 1000:.1f} s"
            )
            events.append(self._event(sample.when_ms, TASK_FINISHED, name, note))
        return events

    def _event(self, when_ms: int, kind: str, name: str, note: str = "") -> Event:
        """An event, with the objects of that name in the backup."""
        table = self.index.profiles if kind in (PROFILE_ACTIVE, PROFILE_INACTIVE) else self.index.tasks
        return Event(when_ms, kind, name, tuple(table.get(name, ())), note)

    def lit(self, recent_seconds: float = RECENT_SECONDS) -> dict[str, str]:
        """{Diagram anchor: LIT_ON or LIT_RECENT} for everything running or active, and what stopped lately.

        Every object of a name is lit, since the device says only the name.  An object that is on now is never
        marked recent, whatever else shares its name.
        """
        marks: dict[str, str] = {}
        window = recent_seconds * 1000
        for (kind, name), seen in self._last_seen.items():
            on = name in (self.active if kind == PROFILE else self.running)
            if not on and self.now_ms - seen > window:
                continue
            table = self.index.profiles if kind == PROFILE else self.index.tasks
            for target in table.get(name, ()):
                anchor = target.anchor
                marks[anchor] = LIT_ON if on or marks.get(anchor) == LIT_ON else LIT_RECENT
        return marks

    def seen_projects(self) -> set[str]:
        """The Projects that everything seen so far belongs to ("" standing for belonging to none)."""
        projects: set[str] = set()
        for kind, name in self._last_seen:
            table = self.index.profiles if kind == PROFILE else self.index.tasks
            projects.update(target.project for target in table.get(name, ()))
        return projects

    def targets_now(self) -> tuple[list[tuple[str, tuple[Target, ...]]], list[tuple[str, tuple[Target, ...]]]]:
        """(active Profiles, running Tasks) as (name, objects of that name), sorted, for listing."""
        return (
            [(name, tuple(self.index.profiles.get(name, ()))) for name in sorted(self.active)],
            [(name, tuple(self.index.tasks.get(name, ()))) for name in sorted(self.running)],
        )

    def as_text(self) -> str:
        """The whole log, for a file or a forum post."""
        return "\n".join(event.line() for event in self.events)


# ##################################################################################
# The Diagram.
# ##################################################################################
def lights_js(lit: dict[str, str], container_id: str = "", follow: Iterable[str] = ()) -> str:
    """JavaScript that lights the named objects in an interactive Diagram and puts out the rest.

    With a container it works on that element; without one, on the whole page -- the monitor sends it to every
    window the app has open, and a window with no Diagram simply has nothing to light.  Evaluates to
    {nodes, lit}: how many named objects the page's Diagram has, and how many of the names asked for it lit.
    So "no Diagram open" (no nodes anywhere) can be told from "a Diagram without these" (nodes, none lit).

    `follow` are anchors to scroll to, in order of preference -- what has only just started -- so that a Diagram
    too big for its window shows the thing that fired.  The first one the page draws is centred; the rest are
    ignored.
    """
    return assettext.render(
        "js/live_lights.js",
        CONTAINER_ID=json.dumps(container_id),
        LIT=json.dumps(lit),
        FOLLOW=json.dumps(list(follow)),
    )


def started_anchors(events: Iterable[Event]) -> list[str]:
    """The anchors of what has just become active or started, in the order it happened -- what a Diagram should scroll to."""
    return [
        event.targets[0].anchor for event in events if event.kind in (PROFILE_ACTIVE, TASK_STARTED) and event.targets
    ]


def diagram_scope(projects: Iterable[str]) -> str:
    """The one Project a Diagram can be built for to show everything seen so far, or "" for the whole configuration.

    A Diagram is built for one Project or for everything.  If all that has fired belongs to a single Project, that
    Project is the answer -- a Diagram of it is quick to build and is what the user wants to look at.  If it
    spans several, or any of it belongs to no Project, or nothing has fired yet, only the whole configuration
    holds it all.
    """
    found = set(projects)
    return next(iter(found)) if len(found) == 1 and "" not in found else ""


# ##################################################################################
# The prediction.
# ##################################################################################
AGREES = "agrees"
UNEXPECTED = "unexpected"
MISSING = "missing"


@dataclass
class Difference:
    """One Profile where the device and What Fires When disagree."""

    kind: str
    target: Target | None
    name: str
    why: str


@dataclass
class Comparison:
    """What the device had active, against what What Fires When said for the same moment."""

    moment: datetime
    battery: int | None
    agreed: int = 0
    differences: list[Difference] = field(default_factory=list[Difference])
    # Active on the device, with no Profile of that name that the prediction judged.
    unjudged: list[str] = field(default_factory=list[str])
    # How many Profiles the prediction could not call either way (it was waiting on something it cannot read).
    undecided: int = 0

    def rows(self) -> list[Row]:
        """The comparison as report rows, each Profile a link."""
        shown = self.moment.strftime("%A %d-%b-%Y %H:%M:%S")
        battery = f", battery {self.battery}%" if self.battery is not None else ""
        rows = [Row(f"What Fires When for {shown}{battery}, against what the device had active"), Row("")]
        rows.append(
            Row(
                f"{self.agreed} Profiles were as predicted; {len(self.differences)} were not; {self.undecided} could not be called."
            )
        )
        for item in self.differences:
            label = "ACTIVE, PREDICTED INACTIVE" if item.kind == UNEXPECTED else "INACTIVE, PREDICTED ACTIVE"
            rows += [Row(""), Row(f"{label}: {item.name}", item.target), Row(f"    {item.why}")]
        if self.unjudged:
            rows += [Row(""), Row("Active on the device but not predicted either way:")]
            rows += [Row(f"    {name}") for name in self.unjudged]
        return rows


def compare(
    simulation: firesim.Simulation, active: frozenset[str], index: NameIndex, battery: int | None = None
) -> Comparison:
    """Judge the device's active Profiles against a prediction made for the same moment.

    Only what the prediction was SURE of is judged: an ACTIVE Profile that is not active, or an INACTIVE one that
    is.  A POSSIBLE one is waiting on something the prediction cannot read (a location, an Event, the screen), so
    either state is consistent with it, and it is counted as undecided.  A Profile that fires at a moment rather
    than staying active is not judged either -- it is never 'active' to be seen -- and neither is one whose name
    another Profile shares, since a state of 'it' says nothing about which.
    """
    result = Comparison(simulation.scenario.when, battery)
    judged: set[str] = set()
    for profile in simulation.active:
        if profile.instant or index.duplicated(profile.target.name):
            continue
        judged.add(profile.target.name)
        if profile.target.name in active:
            result.agreed += 1
        else:
            result.differences.append(
                Difference(
                    MISSING,
                    profile.target,
                    profile.target.name,
                    "every condition holds for this moment, yet Tasker does not list it as active",
                ),
            )
    for profile in simulation.inactive:
        judged.add(profile.target.name)
        if profile.target.name not in active:
            result.agreed += 1
            continue
        blocker = profile.ruled_out_by
        why = (
            f"the prediction ruled it out: {blocker.label} -- {blocker.reason}"
            if blocker
            else "the prediction ruled it out"
        )
        result.differences.append(Difference(UNEXPECTED, profile.target, profile.target.name, why))
    judged |= {profile.target.name for profile in simulation.possible}
    result.undecided = len(simulation.possible)
    result.unjudged = sorted(name for name in active if name not in judged)
    return result
