"""profconflict: Profiles that can be active together and leave the same thing set two ways."""

#! /usr/bin/env python3

#                                                                                       #
# profconflict: find the pairs of Profiles that nothing stops being active at the same   #
#               time and whose entry Tasks set the same thing differently -- a volume,   #
#               the brightness, a switch such as Wi-Fi, a global variable -- and say     #
#               which of them the device is left with.                                   #
#                                                                                       #
# proflint reports the pairs that watch EXACTLY the same trigger, and firesim reports    #
# the pairs a chosen moment makes active together.  What neither can say is the one a    #
# person actually worries about: "my Home Profile sets the volume to 3 and my Night      #
# Profile sets it to 7 -- will they ever fight?"  Those two watch different things, so    #
# they share no trigger, and no single moment was asked about.  This asks the question  #
# of the whole configuration: for every setting that two Profiles' Tasks leave different, #
# can the Profiles both be active at once (firesim.active_together)?  What each Task      #
# leaves is effects.py's reading, which follows the Task through its If blocks and the    #
# Tasks it performs, the way the Task Stepper does.                                       #
#                                                                                       #
# WHICH ONE WINS.  The same rule firesim's queue uses: when two Profiles start together, #
# the one with the higher priority runs its Task first, so the LOWER one runs last and     #
# the device keeps its value; equal priorities have no fixed order.  A Profile that       #
# becomes active later than the other sets its value later whatever the priorities say,   #
# and the finding says so -- a file cannot tell which of them becomes active first.       #
#                                                                                       #
# Same contract as healthck.py, proflint.py and errcheck.py: everything here reads        #
# PrimeItems.tasker_root_elements and nothing else -- no GUI, no device.  The dependency  #
# runs healthck -> profconflict, never the other way, so the severity words and the        #
# Problem record are spelled out again here for proflint's reason.                        #
#                                                                                       #
# What this cannot see, and the report says so (healthck._limitations):                   #
#                                                                                       #
#   * Whether two Profiles really do overlap.  It finds that nothing in the file rules     #
#     it out; an Event, a location or a state it cannot judge is never a reason to say     #
#     two Profiles are exclusive.                                                         #
#   * Profiles that fire at an instant (an Event, a single time, a repeat) are left out:   #
#     they run their Task and are done, so they are never "active together" with another.  #
#   * Exit Tasks, and anything a Task sets only after a decision that depends on a         #
#     variable the device holds.  Both are real, and neither is read.                      #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.analysis import effects, firesim, proflint
from maptasker.src.core.mapjump import PROFILE, Target

if TYPE_CHECKING:
    from maptasker.src.analysis.effects import Subject
    from maptasker.src.core.primitem import RunState

# Two of healthck's three grading words, spelled out rather than imported (see the header).  Nothing here is
# broken: both Profiles run exactly as written.  WARNING is for a pair that watches something in common and
# overlaps there, which is evidence; INFO is for a pair whose triggers are independent, where the only thing the
# file shows is that nothing stops them meeting.
WARNING = "WARNING"
INFO = "INFO"

OVERLAP = "PROFILE-OVERLAP"
TAGS = frozenset({OVERLAP})

# How many of the settings a pair disagrees about its finding names before "and N more".
_SETTINGS_NAMED = 3


@dataclass
class Problem:
    """One finding, in the shape healthck folds into its report (see proflint.Problem).

    'where' is the first Profile of the pair and 'related' holds the other, so each is one jump away.
    """

    severity: str
    tag: str
    where: Target
    detail: str
    related: list[Target] = field(default_factory=list[Target])


@dataclass
class _Entry:
    """One Profile that can take part: where it is, what it starts, and what that leaves set."""

    profile_id: str
    target: Target
    task_id: str
    priority: int
    effects: dict[Subject, str]


def _owners(state: RunState) -> dict[str, str]:
    """{Profile id: owning Project name}, in one pass (see proflint._project_owners for why)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext("pids") or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def _candidates(state: RunState) -> dict[str, _Entry]:
    """Every enabled, state-like Profile whose entry Task sets something, by Profile id.

    An enabled Profile only: a switched-off one becomes active on nothing.  A Profile that fires at an instant is
    left out for the header's reason.  The entry Task's effects are read once per Task, however many Profiles
    start it.
    """
    owners = _owners(state)
    tasks = state.tasker_root_elements["all_tasks"]
    read: dict[str, dict[Subject, str]] = {}
    found: dict[str, _Entry] = {}
    for profile_id, profile in state.tasker_root_elements["all_profiles"].items():
        element = profile["xml"]
        task_id = (element.findtext("mid0") or "").strip()
        if (element.findtext("limit") or "").strip() == "true" or task_id not in tasks:
            continue
        if not any(child.tag in firesim.CONDITION_TAGS for child in element) or firesim.fires_at_a_moment(element):
            continue
        if task_id not in read:
            read[task_id] = effects.entry_effects(task_id, state)
        if read[task_id]:
            target = Target(PROFILE, profile_id, profile["name"], owners.get(profile_id, ""))
            found[profile_id] = _Entry(profile_id, target, task_id, firesim.profile_priority(element), read[task_id])
    return found


def _pairs(entries: dict[str, _Entry]) -> dict[tuple[str, str], list[tuple[Subject, str, str]]]:
    """{(first id, second id): [(setting, first's value, second's value)]} for every pair that disagrees somewhere."""
    by_setting: dict[Subject, list[tuple[str, str]]] = defaultdict(list)
    for profile_id, entry in entries.items():
        for subject, value in entry.effects.items():
            by_setting[subject].append((profile_id, value))

    pairs: dict[tuple[str, str], list[tuple[Subject, str, str]]] = defaultdict(list)
    for subject, setters in by_setting.items():
        for position, (first, mine) in enumerate(setters):
            for second, theirs in setters[position + 1 :]:
                if mine != theirs and entries[first].task_id != entries[second].task_id:
                    low, high = sorted((first, second), key=lambda item: (len(item), item))
                    values = (mine, theirs) if low == first else (theirs, mine)
                    pairs[(low, high)].append((subject, *values))
    return pairs


def _who_wins(first: _Entry, second: _Entry, disagreements: list[tuple[Subject, str, str]]) -> str:
    """Which of the two the device is left with, in the rule the header gives."""
    if first.priority == second.priority:
        return (
            "They have the same priority, so which of them the device is left with when they start together is not"
            " fixed."
        )
    later, earlier = (first, second) if first.priority < second.priority else (second, first)
    kept = ", ".join(
        f"{effects.describe(subject)} {mine if later is first else theirs}"
        for subject, mine, theirs in disagreements[:_SETTINGS_NAMED]
    )
    return (
        f"When they start together {earlier.target.label} (priority {earlier.priority}) runs first and"
        f" {later.target.label} (priority {later.priority}) runs last, so the device is left with {later.target.label}'s"
        f" values: {kept}."
    )


def _detail(
    first: _Entry, second: _Entry, disagreements: list[tuple[Subject, str, str]], together: firesim.Together
) -> str:
    """The finding's sentence: how they overlap, what they disagree about, and who wins."""
    named = "; ".join(
        f"{effects.describe(subject)}: {mine} here, {theirs} there"
        for subject, mine, theirs in disagreements[:_SETTINGS_NAMED]
    )
    left = len(disagreements) - _SETTINGS_NAMED
    more = f"; and {left} more" if left > 0 else ""
    example = f" (for instance {together.example})" if together.example else ""
    watch = (
        "They watch something in common and it overlaps."
        if together.shared
        else "They watch different things, so nothing says they ever meet -- only that nothing says they cannot."
    )
    return (
        f"Can be active together with {second.target.label}{example}, and their entry Tasks leave a setting different: {named}{more}.  {watch}  "
        f"{_who_wins(first, second, disagreements)}  If one of them becomes active after the other, it sets its value "
        "later whatever the priorities say, and nothing here restores the earlier one when it ends."
    )


def lint_problems(state: RunState) -> list[Problem]:
    """One finding per pair of Profiles that can be active together and leave something set two ways.

    Left to proflint: the pairs that watch exactly the same trigger (PROFILE-CONFLICT already says so), so a
    pair is never reported twice.  One finding per pair, however many settings they disagree about, with each
    Profile one jump from the other.

    Safe to call with nothing loaded: an empty list comes back.
    """
    entries = _candidates(state)
    profiles = state.tasker_root_elements["all_profiles"]

    problems: list[Problem] = []
    for (first_id, second_id), disagreements in _pairs(entries).items():
        first_xml, second_xml = profiles[first_id]["xml"], profiles[second_id]["xml"]
        if proflint.same_trigger(first_xml, second_xml):
            continue
        together = firesim.active_together(first_xml, second_xml)
        if together is None:
            continue
        first, second = entries[first_id], entries[second_id]
        problems.append(
            Problem(
                WARNING if together.shared else INFO,
                OVERLAP,
                first.target,
                _detail(first, second, sorted(disagreements), together),
                [second.target],
            ),
        )

    problems.sort(key=lambda problem: (problem.severity != WARNING, problem.where.label))
    return problems
