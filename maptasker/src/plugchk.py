"""plugchk: plugins the configuration uses that the device does not have."""

#! /usr/bin/env python3

#                                                                                       #
# plugchk: cross the plugins a configuration uses against the list of apps fetched     #
#          from the device ('App not listed?' in the Task and Profile editors), and    #
#          report every plugin that is not on it.                                       #
#                                                                                       #
# A plugin action whose plugin is not installed does not fail loudly.  Tasker keeps it, #
# shows it, and at run time skips it with an error the Task may well be set to ignore  #
# -- so a configuration restored onto a new phone, or shared with somebody, runs with   #
# holes in it and nothing says where.  The backup names every plugin it depends on (see #
# plugset.plugin_package), and the fetched app list names every package on the device;  #
# the difference between the two is exactly the list of holes.                           #
#                                                                                       #
# Same contract as healthck.py, proflint.py and codelint.py: everything here reads      #
# PrimeItems.tasker_root_elements, plus the app list appinv keeps on disk, and nothing  #
# else -- no device is contacted.  A check that went to the phone would make the Health #
# Check wait on the network; this one says what the last fetch said, and says when that #
# was.  The dependency runs healthck -> plugchk, never the other way; the severity word #
# and the Problem record are spelled out again here for proflint's reason.              #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src import appinv
from maptasker.src.actionc import action_codes
from maptasker.src.mapjump import PROFILE, TASK, Target, actions_in_map_order
from maptasker.src.plugset import plugin_package

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

WARNING = "WARNING"

NOT_INSTALLED = "PLUGIN-NOT-INSTALLED"
TAGS = frozenset({NOT_INSTALLED})

# How many of the places using a missing plugin its finding names before "and N more".
# Each is a link of its own, and a plugin used forty times needs its first few found, not
# a paragraph.
_PLACES_NAMED = 5


@dataclass
class Problem:
    """One finding, in the shape healthck folds into its report (see proflint.Problem).

    Unlike the other passes' findings, the subject is a plugin rather than an object in the
    file, so 'where' is prose and 'target' is where a click goes: the first place using it.
    The detail line names the rest, each a link of its own (see healthck.Finding).
    """

    severity: str
    tag: str
    where: str
    target: Target
    detail: list[tuple[str, Target | None]]
    related: list[Target] = field(default_factory=list)


@dataclass
class Use:
    """One place a plugin is used: which one, and what it is called there."""

    where: Target
    name: str


def _item_name(code: str, suffix: str) -> str:
    """What Tasker calls a plugin action, event or state.

    Its own entry's name, and the redirect's only when it has none.  actionc.py points 145
    plugin codes at one shared entry, 1040876951t, for their ARGUMENTS -- and that entry is
    named 'AutoInput UI Query', so following the redirect first names every one of them that.
    """
    entry = action_codes.get(f"{code}{suffix}")
    if entry is not None and not entry.name and entry.redirect:
        entry = action_codes.get(entry.redirect, entry)
    return entry.name if entry is not None and entry.name else f"code {code}"


def _owners(kind: str, state: RunState) -> dict[str, str]:
    """{member id: owning Project name} for one of a Project's lists (see proflint._project_owners)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def plugin_uses(state: RunState) -> dict[str, list[Use]]:
    """{package: every place it is used} for every plugin in the configuration.

    Task actions, in the order the Map numbers them, then Profile conditions -- the two
    places a plugin can be put to work.  A Scene element's inline Task can hold a plugin
    action too, and is not walked: the Map gives those actions no anchor to jump to, and a
    plugin used only there is vanishingly rare.
    """
    uses: dict[str, list[Use]] = {}
    root = state.tasker_root_elements

    task_owners = _owners("tids", state=state)
    for task_id, task in root["all_tasks"].items():
        where = Target(TASK, task_id, task["name"], task_owners.get(task_id, ""))
        for number, action in enumerate(actions_in_map_order(task["xml"]), start=1):
            package = plugin_package(action)
            if package:
                name = _item_name(action.findtext("code") or "", "t")
                uses.setdefault(package, []).append(Use(where.at_action(number), name))

    profile_owners = _owners("pids", state=state)
    for profile_id, profile in root["all_profiles"].items():
        where = Target(PROFILE, profile_id, profile["name"], profile_owners.get(profile_id, ""))
        condition: Element
        for condition in profile["xml"]:
            if condition.tag not in ("Event", "State"):
                continue
            package = plugin_package(condition)
            if package:
                name = _item_name(condition.findtext("code") or "", condition.tag[0].lower())
                uses.setdefault(package, []).append(Use(where.with_text(f"{condition.tag} '{name}'"), name))

    return uses


def _checked_against(devices: dict[str, tuple[str, frozenset[str]]]) -> str:
    """ "the app list fetched from 192.168.0.59:1821 on 2026-08-31 09:39:37" -- or several."""
    lists = [f"{device} on {when}" if when else device for device, (when, _) in devices.items()]
    if len(lists) == 1:
        return f"the app list fetched from {lists[0]}"
    return f"any of the app lists fetched from {', '.join(lists[:-1])} and {lists[-1]}"


def _detail(uses: list[Use], checked: str) -> list[tuple[str, Target | None]]:
    """The finding's detail line: what it was checked against, and where the plugin is used."""
    count = len(uses)
    things = "the one place that uses it" if count == 1 else f"all {count} places that use it"
    pieces: list[tuple[str, Target | None]] = [
        (f"Not on {checked}, so {things} will fail when run: ", None),
    ]
    for position, use in enumerate(uses[:_PLACES_NAMED]):
        if position:
            pieces.append(("; ", None))
        pieces.append((f"{use.where.label} ({use.name})", use.where))
    left = count - _PLACES_NAMED
    pieces.append((f"; and {left} more." if left > 0 else ".", None))
    return pieces


def lint_problems(state: RunState) -> list[Problem]:
    """One finding per plugin the configuration uses and no fetched app list has.

    Nothing at all when no list has been fetched: with nothing to check against, every
    plugin would be "missing", which is not what anyone needs told.  healthck says instead
    that the check did not run, and how to make it (see plugins_unchecked).

    A plugin is reported only when it is on none of the lists.  The backup does not say
    which phone it came from, and a plugin that is on the tablet the user fetched last
    month may be exactly where this configuration runs.

    Safe to call with nothing loaded: an empty list comes back.
    """
    devices = appinv.fetched_packages()
    if not devices:
        return []

    installed = frozenset().union(*(packages for _, packages in devices.values()))
    checked = _checked_against(devices)
    problems = []
    for package, uses in sorted(plugin_uses(state=state).items()):
        if package in installed:
            continue
        problems.append(
            Problem(
                WARNING,
                NOT_INSTALLED,
                f"Plugin {package}",
                uses[0].where,
                _detail(uses, checked),
                [use.where for use in uses[1:]],
            ),
        )
    return problems


def plugins_unchecked(state: RunState) -> int:
    """How many plugins the configuration uses, when no app list has been fetched to check them.

    0 when there is a list (the check ran) or no plugin to check.  healthck prints a note
    when this is not 0, so a report with no PLUGIN-NOT-INSTALLED in it cannot be read as
    "every plugin is installed" when nothing was ever compared.
    """
    if appinv.fetched_packages():
        return 0
    return len(plugin_uses(state=state))
