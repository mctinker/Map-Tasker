"""errcheck: risky actions that carry on after a failure with nothing looking at what went wrong."""

#! /usr/bin/env python3

#                                                                                       #
# errcheck: find the Tasks where an action that fails now and then -- a web request, a #
#           shell command, a Perform Task, a write to a file -- is set to carry on     #
#           after an error, and nothing after it reads %err.                            #
#                                                                                       #
# What Tasker does when an action fails depends on one box on the action, "Continue     #
# Task After Error".  Unticked (Tasker's default) the Task stops there, which is loud   #
# and leaves the person looking at a Task that did not finish.  Ticked, Tasker sets     #
# %err and %errmsg and carries on as if nothing had happened -- which is what the        #
# person wanted only if something after the action looks at them.  When nothing does,   #
# the failure is swallowed: the Task goes on to report success, write the file it       #
# never got the data for, or turn Wi-Fi back on after a request that never went out.    #
# Nothing in a Tasker backup says whether that was meant, but the box and the reads of   #
# %err are both in the file, so the question "is this failure being thrown away?" can    #
# be answered without a phone.                                                            #
#                                                                                       #
# Same contract as healthck.py, proflint.py and plugchk.py: everything here reads       #
# PrimeItems.tasker_root_elements and nothing else -- no GUI, no output_lines, no       #
# device.  The dependency runs healthck -> errcheck, never the other way, so the        #
# severity word and the Problem record are spelled out again here for proflint's        #
# reason.                                                                                 #
#                                                                                       #
# What this cannot see, and the report says so (healthck._limitations):                 #
#                                                                                       #
#   * Whether a read of %err really covers the action.  Any enabled action after it in   #
#     the Task that mentions %err or %errmsg -- in an argument, a label or an If        #
#     condition -- counts as looking, wherever it sits and however many risky actions   #
#     stand between.                                                                      #
#   * Whether ignoring the failure was the point.  A request that is only a courtesy      #
#     ping is fine to lose, and so is the output of a shell command nobody needs.        #
#   * Actions of a plugin: which of them can fail, and how, is the plugin's to say.       #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import TASK, Target, actions_in_map_order

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# One of healthck's three grading words, spelled out rather than imported (see the header).
# A failure thrown away is something to look at, not a defect: the configuration is
# well-formed and Tasker runs it exactly as written.
WARNING = "WARNING"

IGNORED_ERROR = "ERROR-IGNORED"
TAGS = frozenset({IGNORED_ERROR})

# What kind of risk each action carries, by Tasker's action code.  The four kinds are the
# ones whose failure is common and whose silence costs something: the network is down, the
# command is not there, the Task it calls was deleted, the storage is full or read-only.
WEB = "web request"
SHELL = "shell command"
TASK_CALL = "Perform Task"
FILE_WRITE = "file write"

_RISKY: dict[str, str] = {
    "116": WEB,  # HTTP Post
    "117": WEB,  # HTTP Head
    "118": WEB,  # HTTP Get
    "339": WEB,  # HTTP Request
    "123": SHELL,  # Run Shell
    "130": TASK_CALL,  # Perform Task
    "404": FILE_WRITE,  # Copy File
    "405": FILE_WRITE,  # Copy Dir
    "406": FILE_WRITE,  # Delete File
    "408": FILE_WRITE,  # Delete Directory
    "409": FILE_WRITE,  # Create Directory
    "410": FILE_WRITE,  # Write File
}

# %err and %errmsg, the two variables Tasker sets when an action that is allowed to fail does.
# Matched whatever the case and not as the front of a longer name (%error_count is the
# person's own).  A read anywhere in the text of an action counts: its arguments, its label
# and the If condition it carries.
_READS_ERROR = re.compile(r"%err(?:msg)?(?![A-Za-z0-9_])", re.IGNORECASE)

# How many of a Task's unhandled actions its finding names before "and N more".
_ACTIONS_NAMED = 4


@dataclass
class Problem:
    """One finding, in the shape healthck folds into its report (see proflint.Problem).

    'where' is the first unhandled action, so a click lands on it; 'related' holds the
    Task's other unhandled actions, one jump each.
    """

    severity: str
    tag: str
    where: Target
    detail: str
    related: list[Target] = field(default_factory=list[Target])


@dataclass
class Unhandled:
    """One action that can fail, is allowed to carry on, and has nothing after it reading %err."""

    number: int
    name: str
    kind: str


def _action_name(code: str) -> str:
    """What Tasker calls this action code."""
    entry = action_codes.get(f"{code}t")
    return entry.name if entry is not None and entry.name else f"code {code}"


def _is_enabled(action: Element) -> bool:
    """Tasker writes <on>false</on> on an action that is switched off, and nothing on one that is on."""
    return action.find("on") is None


def _carries_on_after_error(action: Element) -> bool:
    """Whether 'Continue Task After Error' is ticked -- <se>false</se>, the opposite of what it reads like.

    No <se> (or any other text) is Tasker's default, which stops the Task on an error.
    """
    flag = action.find("se")
    return flag is not None and flag.text == "false"


def _reads_error(action: Element) -> bool:
    """Whether anything written in this action mentions %err or %errmsg.

    The pieces of text are joined with a separator: run together, "%errmsg" and the "3" of the field after it would read as
    one longer name.
    """
    return _READS_ERROR.search("\n".join(action.itertext())) is not None


def _project_owners(state: RunState) -> dict[str, str]:
    """{Task id: owning Project name}, built in one pass (see proflint._project_owners for why)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext("tids") or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def unhandled_actions(task_element: Element) -> list[Unhandled]:
    """The actions of one Task that can fail, carry on if they do, and are not followed by a read of %err.

    Walked in the order the Map numbers the actions, so a number in a finding is one the user
    can find.  Disabled actions are skipped on both sides: Tasker does not run them, so a
    disabled request cannot fail and a disabled If cannot be looking at anything.
    """
    steps = [
        (number, (action.findtext("code") or "").strip(), action)
        for number, action in enumerate(actions_in_map_order(task_element), start=1)
        if _is_enabled(action)
    ]
    # Whether anything at or after each position reads the error: built from the end, so each
    # action asks "does something later look?" in one step rather than rescanning the Task.
    read_later = [False] * (len(steps) + 1)
    for position in range(len(steps) - 1, -1, -1):
        read_later[position] = read_later[position + 1] or _reads_error(steps[position][2])

    found: list[Unhandled] = []
    for position, (number, code, action) in enumerate(steps):
        kind = _RISKY.get(code)
        if kind and _carries_on_after_error(action) and not read_later[position + 1]:
            found.append(Unhandled(number, _action_name(code), kind))
    return found


def _detail(found: list[Unhandled]) -> str:
    """The finding's sentence: what is set to carry on, which actions, and what to do about it."""
    named = ", ".join(f"{item.number} {item.name} ({item.kind})" for item in found[:_ACTIONS_NAMED])
    left = len(found) - _ACTIONS_NAMED
    more = f" and {left} more" if left > 0 else ""
    many = len(found) > 1
    return (
        f"{'These actions are' if many else 'This action is'} set to 'Continue Task After Error' and nothing after "
        f"{'them' if many else 'it'} in this Task reads %err or %errmsg, so if {'one fails' if many else 'it fails'} "
        f"the Task carries on as though it had not: {named}{more}.  Check %err afterwards, or untick the box so the "
        "Task stops where it failed."
    )


def lint_problems(state: RunState) -> list[Problem]:
    """One finding per Task that throws a failure away, naming the actions that do.

    One per Task rather than one per action: a Task that fires six requests the same way
    has one thing to decide, and a report with six lines for it would bury everything else.
    The first action is where the click goes and the others are 'related', so each is still
    one jump away.

    Safe to call with nothing loaded: an empty list comes back.
    """
    owners = _project_owners(state=state)
    problems: list[Problem] = []
    for task_id, task in state.tasker_root_elements["all_tasks"].items():
        found = unhandled_actions(task["xml"])
        if not found:
            continue
        where = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        problems.append(
            Problem(
                WARNING,
                IGNORED_ERROR,
                where.at_action(found[0].number),
                _detail(found),
                [where.at_action(item.number) for item in found[1:]],
            ),
        )

    problems.sort(key=lambda problem: (problem.where.label, problem.where.action))
    return problems
