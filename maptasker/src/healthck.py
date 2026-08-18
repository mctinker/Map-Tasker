"""Health check: scan the loaded Tasker configuration for problems."""

#! /usr/bin/env python3

#                                                                                      #
# healthck: Scan the loaded XML for broken references, unreferenced objects and naming #
#           problems, and report them as plain text.                                    #
#                                                                                      #
# Everything here reads PrimeItems.tasker_root_elements and nothing else -- no GUI, no  #
# output_lines, no generated HTML.  That is deliberate: the checks are pure functions   #
# over the lookup tables taskerd.get_the_xml_data builds, so they run the moment an XML #
# file is loaded (no Map run required) and they are testable without standing up a GUI. #
#                                                                                      #
# The report is plain text.  The caller writes it to a file as-is and escapes a COPY of #
# it for display -- see userintr.health_check_event, which explains why.                #
#                                                                                      #
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from maptasker.src.actionc import action_codes
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    HEALTHCHECK_FILE,
    MY_VERSION,
    SCENE_TASK_TYPES,
    logger,
)

if TYPE_CHECKING:
    import defusedxml.ElementTree  # Need for type hints

# Severity ordering is the order findings are reported in, worst first.
ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"
_SEVERITY_ORDER = (ERROR, WARNING, INFO)

_SEVERITY_HEADINGS = {
    ERROR: "ERRORS -- these will misbehave on the device",
    WARNING: "WARNINGS -- probably not what you intended",
    INFO: "INFO -- worth a look",
}

_REPORT_WIDTH = 78

# A Task that fires from a Scene element and lives only inside that Scene carries a
# negative id (see sceneedit.LEGACY_ANONYMOUS_TASK_PREFIX).  It is not in all_tasks and
# never will be, so it is neither a broken reference nor an unreferenced Task.
_ANONYMOUS_TASK_PREFIX = "-"

# "Perform Task" -- arg0 is the Task *name*.  The one Task-by-name reference in the
# action set; every other Task reference in a backup is by id.
_PERFORM_TASK_CODE = "130"

# Create/Show/Hide/Destroy Scene.  These name a Scene in arg0, but their argument is
# called "Name" rather than "Scene Name", so _scene_name_args() below cannot find them
# by name the way it finds the twenty-odd "Element ..." actions.
_SCENE_LIFECYCLE_CODES = {"46": "0", "47": "0", "48": "0", "49": "0"}

# Set Widget Icon / Set Widget Label.  Their arg0 is a home screen widget's name, and a
# Tasker widget is named for the Task it launches -- so a Task named here almost certainly
# has a widget on the home screen, and a widget is a way to run it that leaves no other
# trace in the backup.  Counted as a reference so those Tasks are not reported dead: the
# evidence is circumstantial, but a false "unreferenced" on a Task the user taps daily is a
# much worse answer than staying quiet about one.
_WIDGET_NAME_CODES = {"152": "0", "155": "0"}


@dataclass
class Finding:
    """One problem found.

    'tag' is a stable, deliberately un-translated identifier (e.g. BROKEN-TASK-REF).  It
    stays English in every language so that two reports can be diffed and a tag can be
    searched for; only the surrounding prose is translated.
    """

    severity: str
    tag: str
    where: str
    detail: str


@dataclass
class _Index:
    """Everything the checks need, gathered in one pass over the XML.

    Built once rather than answered per-finding: maputils' find_owning_project and
    friends each walk every Project, so calling them from inside a loop over Tasks would
    make the whole check quadratic on a large backup.  They are also name-based, which
    cannot describe a backup holding two Profiles of the same name -- exactly the case
    DUPLICATE-NAME exists to report.
    """

    # Which Project lists this object.  Absent means no Project does -- an orphan.
    project_of_profile: dict[str, str] = field(default_factory=dict)
    project_of_task: dict[str, str] = field(default_factory=dict)
    project_of_scene: dict[str, str] = field(default_factory=dict)
    # Who refers to each Task/Scene, as human-readable phrases ("Profile 'Wake' entry
    # Task").  A Task with no entry here is unreferenced; the phrases are what make an
    # unreferenced-Task report explain itself rather than just assert.
    task_referrers: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    scene_referrers: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    # Task ids sharing a name, and the same for Profiles and Scenes.  Built from
    # all_tasks rather than all_tasks_by_name: the by-name table silently overwrites a
    # collision (taskerd.py), so it can never show the duplicate that caused it.
    task_ids_by_name: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    # How many actions name a Scene through a variable rather than by name.  Each one is a
    # Scene this check cannot identify, and so a Scene it cannot rule out -- see
    # _index_one_action and the caveat _check_reachability attaches to UNUSED-SCENE.
    variable_scene_references: int = 0
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity: str, tag: str, where: str, detail: str) -> None:
        """Record one finding."""
        self.findings.append(Finding(severity, tag, where, detail))


def _scene_name_args() -> dict[str, str]:
    """{action code: arg id} for every action that names a Scene.

    Derived from the action table rather than listed here, so an action added to
    actionc.py in a later Tasker release is covered without this module being touched.
    The twenty-odd "Element ..." actions all declare an argument literally named
    "Scene Name"; the four lifecycle actions that do not are added from
    _SCENE_LIFECYCLE_CODES.
    """
    codes = dict(_SCENE_LIFECYCLE_CODES)
    for key, action in action_codes.items():
        if not key.endswith("t"):  # 'e' keys are Profile events/states, not Task actions.
            continue
        for argument in action.args or ():
            if argument.arg_name == "Scene Name":
                codes[key[:-1]] = argument.arg_id
                break
    return codes


def _string_argument(action: defusedxml.ElementTree.Element, arg_id: str) -> str:
    """The text of an action's <Str sr="argN">, or "" if it has none.

    Mirrors taskedit.py's own way of reaching an argument: match the "sr" attribute
    rather than relying on child order, which Tasker does not guarantee.
    """
    target = f"arg{arg_id}"
    for child in action.findall("Str"):
        if child.attrib.get("sr") == target:
            return (child.text or "").strip()
    return ""


def _is_resolvable(name: str) -> bool:
    """Whether a name can be checked against the backup at all.

    A name holding a variable ("%Scene" or "Menu %Which") is decided on the device at
    run time and cannot be resolved here.  Reporting one as a broken reference would be
    a false alarm on a configuration that is working perfectly, so these are skipped --
    the check reports what it is sure of and stays quiet about the rest.
    """
    return bool(name) and "%" not in name


def _element_text(element: defusedxml.ElementTree.Element, tag: str) -> str:
    """The text of a child element, stripped, or "" if it is missing or empty."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _describe(kind: str, name: str, identifier: str = "") -> str:
    """An object's name for the report: Task 'Wake Up' (id 118), or Task (id 118) unnamed."""
    if name:
        return f"{kind} '{name}'" + (f" (id {identifier})" if identifier else "")
    return f"{kind} (id {identifier}) [unnamed]" if identifier else f"{kind} [unnamed]"


def _in_project(where: str, project_name: str | None) -> str:
    """Put the owning Project in front of an object's name, when a Project owns it.

    Every finding's location reads the same way because of this -- "Project 'Home' >
    Task 'Wake Up' (id 118)" -- which is what lets the report be sorted by location and
    come out grouped by Project.

    Silent when nothing owns the object, rather than saying so: a Task in no Project is
    ordinary (Tasker keeps unassigned Tasks in its own Tasks tab), and a location is the
    wrong place to raise it.  Where that fact actually matters -- an unreferenced Task
    someone may be about to delete -- the check says so in the finding's detail instead.
    """
    return f"Project '{project_name}' > {where}" if project_name else where


def _split_ids(element: defusedxml.ElementTree.Element, tag: str) -> list[str]:
    """A Project's <pids>/<tids> as a list of ids.

    Tasker writes an empty list as an empty (or absent) element, so the filter matters:
    "".split(",") is [""], which would otherwise be reported as a broken reference to a
    Profile whose id is the empty string.
    """
    text = _element_text(element, tag)
    return [item.strip() for item in text.split(",") if item.strip()] if text else []


# ##################################################################################
# Reference gathering -- one pass each over Projects, Profiles, Scenes and Tasks.
# ##################################################################################
def _index_projects(index: _Index) -> None:
    """Walk every Project: record what it owns, and report what it names but does not have."""
    all_projects = PrimeItems.tasker_root_elements["all_projects"]
    all_profiles = PrimeItems.tasker_root_elements["all_profiles"]
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]
    all_scenes = PrimeItems.tasker_root_elements["all_scenes"]

    for project_name, project in all_projects.items():
        where = _describe("Project", project_name)

        for profile_id in _split_ids(project["xml"], "pids"):
            if profile_id in all_profiles:
                index.project_of_profile[profile_id] = project_name
            else:
                index.add(
                    ERROR,
                    "BROKEN-PROFILE-REF",
                    where,
                    f"lists Profile id {profile_id} in <pids>, which is not in this file.",
                )

        for task_id in _split_ids(project["xml"], "tids"):
            if task_id in all_tasks:
                # Ownership only -- deliberately NOT a task_referrers entry.  <tids> says
                # which Project a Task filed under, not that anything runs it, and counting
                # it as a reference would make UNREFERENCED-TASK unable to fire at all: every
                # Task a Project owns would look reachable purely by being owned.
                index.project_of_task[task_id] = project_name
            else:
                index.add(
                    ERROR,
                    "BROKEN-TID-REF",
                    where,
                    f"lists Task id {task_id} in <tids>, which is not in this file.",
                )

        # A Project lists its Scenes by name, comma separated, not by id.
        scene_names = _element_text(project["xml"], "scenes")
        for scene_name in (item.strip() for item in scene_names.split(",") if item.strip()):
            if scene_name in all_scenes:
                # Ownership, not use -- same distinction as <tids> above.  A Project owning
                # a Scene says nothing about whether any action ever shows it.
                index.project_of_scene[scene_name] = project_name
            else:
                index.add(
                    ERROR,
                    "BROKEN-SCENE-REF",
                    where,
                    f"lists Scene '{scene_name}' in <scenes>, which is not in this file.",
                )


def _index_profiles(index: _Index) -> None:
    """Walk every Profile: record the Tasks it runs, and report the ones that are missing."""
    all_profiles = PrimeItems.tasker_root_elements["all_profiles"]
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]

    for profile_id, profile in all_profiles.items():
        where = _in_project(
            _describe("Profile", profile["name"], profile_id),
            index.project_of_profile.get(profile_id),
        )

        # <mid0> is the entry Task, <mid1> the exit Task (see profiles.get_profile_tasks).
        for tag, task_type in (("mid0", "entry"), ("mid1", "exit")):
            task_id = _element_text(profile["xml"], tag)
            if not task_id:
                continue
            if task_id in all_tasks:
                index.task_referrers[task_id].append(f"{where} {task_type} Task")
            else:
                index.add(
                    ERROR,
                    "BROKEN-TASK-REF",
                    where,
                    f"{task_type.capitalize()} Task (<{tag}>) id {task_id} is not in this file.",
                )


def _index_scene_tasks(index: _Index, scene_name: str, scene: dict, sceneedit: object) -> None:
    """Record the Tasks a Legacy Scene's elements fire, reporting any that are missing."""
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]
    # project_of_scene is filled by _index_projects, which run_health_check calls first.
    where = _in_project(_describe("Scene", scene_name), index.project_of_scene.get(scene_name))

    # .iter() rather than a walk over direct children: a Legacy element can hold another
    # (a WebElement carrying a RectElement, for one), and a binding on a nested element is
    # every bit as real as one at the top.  Every backup to hand happens to keep them all
    # at the top level, which is exactly why this is worth not assuming.
    for element in scene["xml"].iter():
        if not element.tag.endswith("Element"):
            continue
        # legacy_element_label reads the element's own name from arg0 and renders it the
        # way the designer's tree does ("Button 'Cancel'"), so a finding names the element
        # by what the user will see when they go to fix it.
        label = sceneedit.legacy_element_label(element)
        for binding in element:
            if binding.tag not in SCENE_TASK_TYPES:
                continue
            task_id = (binding.text or "").strip()
            # An anonymous Task lives inside the Scene itself and is in no table.
            if not task_id or task_id.startswith(_ANONYMOUS_TASK_PREFIX):
                continue
            event = SCENE_TASK_TYPES[binding.tag]
            if task_id in all_tasks:
                index.task_referrers[task_id].append(f"{where} {label} {event}")
            else:
                index.add(
                    ERROR,
                    "BROKEN-SCENE-TASK",
                    where,
                    f"{label} '{event}' fires Task id {task_id}, which is not in this file.",
                )


def _index_v2_scene_tasks(index: _Index, scene_name: str, scene: dict, sceneedit: object) -> None:
    """Record the Tasks a Version 2 Scene's event handlers run.

    A V2 Scene keeps its components in a gzipped JSON blob rather than in child elements,
    and a RunTask handler names its Task rather than pointing at an id -- so this resolves
    through all_tasks_by_name where the Legacy walk above resolves through all_tasks.
    """
    layout = sceneedit.decode_v2_layout(scene["xml"])
    # None means a Legacy Scene or an <lj> that would not decode.  Either way there is
    # nothing here to check, and guessing at a corrupt layout would invent findings.
    if layout is None:
        return

    all_tasks_by_name = PrimeItems.tasker_root_elements["all_tasks_by_name"]
    where = _in_project(_describe("Scene", scene_name), index.project_of_scene.get(scene_name))

    for row in sceneedit.v2_flatten(layout):
        for handler in sceneedit.v2_handlers(row.node):
            for action in handler.get("actions") or ():
                if not isinstance(action, dict) or action.get("type") != "RunTask":
                    continue
                task_name = (action.get("task") or "").strip()
                if not _is_resolvable(task_name):
                    continue
                entry = all_tasks_by_name.get(task_name)
                if entry:
                    index.task_referrers[entry["id"]].append(f"{where} component '{row.label}'")
                else:
                    index.add(
                        ERROR,
                        "BROKEN-SCENE-TASK",
                        where,
                        f"component '{row.label}' runs Task '{task_name}', which is not in this file.",
                    )


def _index_scenes(index: _Index) -> None:
    """Walk every Scene, Legacy or Version 2, for the Tasks it fires.

    sceneedit is imported here rather than at module scope, and passed down rather than
    re-imported per Scene: it is the Scene editor, and nothing else in this module needs
    it.  Keeping the dependency inside the one function that uses it leaves healthck
    importable on its own -- which is what lets the checks be tested without the editor,
    and keeps a future import the other way from becoming a cycle.
    """
    from maptasker.src import sceneedit  # noqa: PLC0415

    for scene_name, scene in PrimeItems.tasker_root_elements["all_scenes"].items():
        # <lj> is the whole V2 test, in both directions (see sceneedit.is_v2_scene).
        if scene["xml"].find("lj") is not None:
            _index_v2_scene_tasks(index, scene_name, scene, sceneedit)
        else:
            _index_scene_tasks(index, scene_name, scene, sceneedit)


def _index_one_action(
    index: _Index,
    action: defusedxml.ElementTree.Element,
    number: int,
    where: str,
    scene_args: dict[str, str],
) -> None:
    """Record what one action refers to, wherever that action lives.

    Split out from the walk over Tasks because an action is not always inside a <Task>: a
    Legacy Scene can carry an anonymous task's actions inline (see
    _index_scene_inline_actions), and those refer to Tasks and Scenes exactly as a named
    Task's actions do.  Scanning them with a second, parallel copy of this logic is how
    the two would drift apart.
    """
    all_tasks_by_name = PrimeItems.tasker_root_elements["all_tasks_by_name"]
    all_scenes = PrimeItems.tasker_root_elements["all_scenes"]

    code = _element_text(action, "code")
    if not code:
        return

    if code == _PERFORM_TASK_CODE:
        called = _string_argument(action, "0")
        if _is_resolvable(called):
            entry = all_tasks_by_name.get(called)
            if entry:
                index.task_referrers[entry["id"]].append(f"{where} action {number}")
            else:
                index.add(
                    ERROR,
                    "BROKEN-PERFORM-TASK",
                    where,
                    f"action {number} (Perform Task) calls '{called}', which is not in this file.",
                )

    elif code in _WIDGET_NAME_CODES:
        widget_name = _string_argument(action, _WIDGET_NAME_CODES[code])
        if _is_resolvable(widget_name):
            entry = all_tasks_by_name.get(widget_name)
            if entry:
                index.task_referrers[entry["id"]].append(f"{where} action {number} (home screen widget)")

    elif code in scene_args:
        scene_name = _string_argument(action, scene_args[code])
        if not scene_name:
            return
        if not _is_resolvable(scene_name):
            # A Scene named by a variable ("%Which_Scene") is chosen on the device, so this
            # action could be showing ANY Scene in the file.  That makes it impossible to
            # prove a Scene unused, which is why the count is kept: UNUSED-SCENE reports
            # itself as unreliable when this is non-zero rather than quietly listing Scenes
            # that are shown every day under a name only Tasker can work out.
            index.variable_scene_references += 1
            return
        if scene_name in all_scenes:
            index.scene_referrers[scene_name].append(f"{where} action {number}")
        else:
            index.add(
                ERROR,
                "BROKEN-SCENE-ACTION",
                where,
                f"action {number} refers to Scene '{scene_name}', which is not in this file.",
            )


def _index_actions(index: _Index) -> None:
    """Walk every action of every Task for Task and Scene references.

    The only pass here that is O(actions) rather than O(objects), and the reason the
    reference index is built once up front rather than recomputed per check.

    Every Task is walked, named or not.  An unnamed Task is a full Task in every way that
    matters here -- it has an id, it holds actions, and a Profile runs it through <mid0>/
    <mid1> like any other -- so the Scenes it shows and the Tasks it calls count exactly
    the same.  Skipping them would make a Scene shown only by a Profile's anonymous entry
    Task look unused.
    """
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]
    scene_args = _scene_name_args()

    for task_id, task in all_tasks.items():
        where = _in_project(_describe("Task", task["name"], task_id), index.project_of_task.get(task_id))

        for number, action in enumerate(task["xml"].findall("Action"), start=1):
            _index_one_action(index, action, number, where, scene_args)


def _index_scene_inline_actions(index: _Index) -> None:
    """Walk the actions of anonymous tasks that live inside a Scene.

    Tasker keeps a truly anonymous task -- one created inline on a Scene element and named
    nowhere -- inside the Scene itself rather than as a top-level <Task>, as <Action>
    children hanging off the element that fires them (a ListElementItem's, for one).  They
    are in no lookup table, so the walk over all_tasks above never sees them, and every
    Task and Scene they refer to was invisible to this check: a Scene destroyed only by a
    Scene button's inline task read as unused, and a Task called only from one read as
    unreferenced.
    """
    scene_args = _scene_name_args()

    for scene_name, scene in PrimeItems.tasker_root_elements["all_scenes"].items():
        scene_where = _in_project(_describe("Scene", scene_name), index.project_of_scene.get(scene_name))
        where = f"{scene_where} anonymous Task"
        # .iter() from the Scene root: these sit at whatever depth the element that owns
        # them sits, and are not confined to one element type.
        for number, action in enumerate(scene["xml"].iter("Action"), start=1):
            _index_one_action(index, action, number, where, scene_args)


# ##################################################################################
# Checks that read the finished index.
# ##################################################################################
def _check_reachability(index: _Index) -> None:
    """Report objects nothing can reach: dead Tasks, unowned Profiles and Scenes, empty Projects."""
    all_projects = PrimeItems.tasker_root_elements["all_projects"]
    all_profiles = PrimeItems.tasker_root_elements["all_profiles"]
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]
    all_scenes = PrimeItems.tasker_root_elements["all_scenes"]

    for task_id, task in all_tasks.items():
        if index.task_referrers.get(task_id):
            continue
        owning_project = index.project_of_task.get(task_id)
        index.add(
            WARNING,
            "UNREFERENCED-TASK",
            _in_project(_describe("Task", task["name"], task_id), owning_project),
            "Nothing in this file runs it: no Profile, no Scene, no Perform Task action"
            # Said here rather than in the location (see _in_project): for a Task someone
            # may be about to delete, belonging to no Project at all is part of the case.
            + ("" if owning_project else ", and no Project lists it")
            + ".  It may still be launched from outside the backup -- see the note at the end.",
        )

    for profile_id, profile in all_profiles.items():
        if profile_id not in index.project_of_profile:
            index.add(
                WARNING,
                "ORPHAN-PROFILE",
                _describe("Profile", profile["name"], profile_id),
                "No Project lists it in <pids>, so Tasker will not run it.",
            )

    # Two different problems, kept apart because the fixes differ.  An unowned Scene is
    # structurally adrift -- no Project holds it.  An owned Scene nothing ever shows is
    # structurally fine and merely dead, which is a note rather than a warning.
    for scene_name in all_scenes:
        if scene_name not in index.project_of_scene:
            index.add(
                WARNING,
                "ORPHAN-SCENE",
                _describe("Scene", scene_name),
                "No Project lists it in <scenes>.",
            )
        elif not index.scene_referrers.get(scene_name):
            # Named with its owning Project, the way a Task or Profile finding is.  The
            # Project is always known here -- this is the branch where one lists the Scene,
            # which is what separates it from the ORPHAN-SCENE case above -- and it is what
            # tells the user where to go and look.
            index.add(
                INFO,
                "UNUSED-SCENE",
                _in_project(_describe("Scene", scene_name), index.project_of_scene[scene_name]),
                "No action shows, hides, destroys or changes an element of it"
                + (
                    "."
                    if not index.variable_scene_references
                    else " under that name -- but see the note at the end, this file shows Scenes by variable too."
                ),
            )

    for project_name, project in all_projects.items():
        if not _split_ids(project["xml"], "pids") and not _split_ids(project["xml"], "tids"):
            index.add(
                WARNING,
                "EMPTY-PROJECT",
                _describe("Project", project_name),
                "Holds no Profiles and no Tasks.",
            )


def _check_duplicate_names(index: _Index) -> None:
    """Report two objects of the same kind sharing a name.

    Tasker allows it, but every reference by name -- Perform Task, a V2 Scene's RunTask,
    MapTasker's own single-item pulldowns -- then picks one of them arbitrarily, and it
    is unlikely to be the one that was meant.
    """
    for task_name, task_ids in sorted(index.task_ids_by_name.items()):
        if len(task_ids) > 1:
            index.add(
                INFO,
                "DUPLICATE-NAME",
                _describe("Task", task_name),
                f"{len(task_ids)} Tasks share this name: {_where_each_is(task_ids, index.project_of_task)}."
                + (
                    "  Two of them are in the same Project."
                    if _has_repeat_project(task_ids, index.project_of_task)
                    else ""
                )
                # Worth saying for Tasks and not for Profiles: a Perform Task resolves by
                # name, so a duplicate here is not just hard to tell apart in Tasker's
                # list, it silently decides which of them every caller actually runs.
                + "  A Perform Task naming it will run only one of them.",
            )

    profiles_by_name = defaultdict(list)
    for profile_id, profile in PrimeItems.tasker_root_elements["all_profiles"].items():
        if profile["name"]:
            profiles_by_name[profile["name"]].append(profile_id)
    for profile_name, profile_ids in sorted(profiles_by_name.items()):
        if len(profile_ids) > 1:
            index.add(
                INFO,
                "DUPLICATE-NAME",
                _describe("Profile", profile_name),
                f"{len(profile_ids)} Profiles share this name: {_where_each_is(profile_ids, index.project_of_profile)}."
                # Which Project each copy sits in is what says whether this is a problem.
                # Two Profiles of one name in two Projects is a naming habit; two in the
                # same Project is the case where the user cannot tell them apart in Tasker.
                + (
                    "  Two of them are in the same Project."
                    if _has_repeat_project(profile_ids, index.project_of_profile)
                    else ""
                ),
            )


def _where_each_is(identifiers: list[str], project_of: dict[str, str]) -> str:
    """ "id 42 in Project 'Home', id 91 in Project 'Work'" -- each copy and where it lives.

    Sorted by Project so copies sharing one are named together, which is what makes the
    same-Project case readable at a glance.
    """
    return ", ".join(
        f"id {identifier} in " + (f"Project '{project_of[identifier]}'" if identifier in project_of else "no Project")
        for identifier in sorted(identifiers, key=lambda item: (project_of.get(item, ""), item))
    )


def _has_repeat_project(identifiers: list[str], project_of: dict[str, str]) -> bool:
    """Whether two of these objects sit in the same Project.

    Only counts objects a Project actually owns: several unowned ones are not "in the same
    Project", they are in none.
    """
    owners = [project_of[identifier] for identifier in identifiers if identifier in project_of]
    return len(owners) != len(set(owners))


def _check_hygiene(index: _Index) -> None:
    """Report the things that are legal, and working, but worth knowing about."""
    all_profiles = PrimeItems.tasker_root_elements["all_profiles"]
    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]

    for profile_id, profile in all_profiles.items():
        # <limit>true</limit> is how Tasker records a disabled Profile (profiles.py).
        if _element_text(profile["xml"], "limit") == "true":
            index.add(
                INFO,
                "DISABLED-PROFILE",
                _in_project(
                    _describe("Profile", profile["name"], profile_id),
                    index.project_of_profile.get(profile_id),
                ),
                "Disabled in Tasker, so none of its Tasks will run.",
            )

    # Counted here rather than read from PrimeItems.task_action_warnings, which is only
    # populated while the Map output is being built (taskactn.py).  A health check run
    # straight after loading a file would otherwise silently report nothing.
    limit = PrimeItems.program_arguments.get("task_action_warning_limit", 100)
    if limit < 100:
        for task_id, task in all_tasks.items():
            count = len(task["xml"].findall("Action"))
            if count > limit:
                index.add(
                    INFO,
                    "LARGE-TASK",
                    _in_project(_describe("Task", task["name"], task_id), index.project_of_task.get(task_id)),
                    f"{count} actions, above your warning limit of {limit}. "
                    "Consider splitting it into several Tasks.",
                )

    _check_duplicate_names(index)


# ##################################################################################
# Report construction.
# ##################################################################################
def _current_xml_file() -> str:
    """The path of the XML file being checked.

    PrimeItems.file_to_get is sometimes an open file object and sometimes the path as a
    plain string -- the same ambiguity maputil2.write_full_backup_to_current_file
    handles, resolved the same way.
    """
    file_to_get = PrimeItems.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) and path else "(unknown)"


def _counts(findings: list[Finding]) -> dict:
    """How many findings of each severity."""
    return {severity: sum(1 for item in findings if item.severity == severity) for severity in _SEVERITY_ORDER}


def _build_report(index: _Index, when: datetime) -> str:
    """Render the findings as the plain text that is both saved and displayed."""
    root = PrimeItems.tasker_root_elements
    counts = _counts(index.findings)
    rule = "=" * _REPORT_WIDTH
    thin_rule = "-" * _REPORT_WIDTH

    lines = [
        "MapTasker Health Check",
        rule,
        f"XML file:    {_current_xml_file()}",
        f"Generated:   {when.strftime('%d-%b-%Y %H:%M:%S')}",
        f"Version:     {MY_VERSION}",
        "",
        (
            "Scanned:     "
            f"{len(root['all_projects'])} Projects, "
            f"{len(root['all_profiles'])} Profiles, "
            f"{len(root['all_tasks'])} Tasks, "
            f"{len(root['all_scenes'])} Scenes"
        ),
        f"Findings:    {counts[ERROR]} Errors, {counts[WARNING]} Warnings, {counts[INFO]} Info",
        "",
    ]

    if not index.findings:
        lines += ["Nothing to report -- no broken references, unreferenced objects or", "naming problems found.", ""]
        return "\n".join(lines)

    for severity in _SEVERITY_ORDER:
        of_this_severity = [item for item in index.findings if item.severity == severity]
        if not of_this_severity:
            continue
        lines += ["", _SEVERITY_HEADINGS[severity], thin_rule]
        # Sorted by tag so every instance of one problem reads as a group, which is what
        # makes a long report skimmable -- and what makes two reports diff cleanly.
        for item in sorted(of_this_severity, key=lambda finding: (finding.tag, finding.where)):
            lines += [f"[{item.tag}]  {item.where}", f"    {item.detail}", ""]

    lines += _limitations(index)
    return "\n".join(lines)


def _limitations(index: _Index) -> list[str]:
    """The closing note on what this check cannot see.

    Printed rather than left implied because the one finding most worth acting on --
    UNREFERENCED-TASK -- is also the one whose false positives are unavoidable: a Task can
    be started by a home screen widget, a Quick Settings tile, a launcher shortcut or
    another app entirely, and none of those live in a Tasker backup.  A report that
    invited someone to delete a Task they tap every morning, without saying so, would be
    worse than no report.
    """
    notes = []

    if any(item.tag == "UNREFERENCED-TASK" for item in index.findings):
        notes += [
            "",
            "NOTE ON UNREFERENCED TASKS",
            "-" * _REPORT_WIDTH,
            "A backup records what is inside Tasker, not what points at it from outside.",
            "A Task reported unreferenced may still be started by a home screen widget, a",
            "Quick Settings tile, a launcher shortcut, an intent from another app, or a",
            "plugin -- none of which appear in this file.  Check how you run it before",
            "deleting anything.  (A Task named by a Set Widget Icon/Label action is",
            "already treated as having a widget and is not reported here.)",
            "",
        ]

    # Only worth saying when both halves are true: there are Scenes on the list, and there
    # is something in the file that could account for them.
    if index.variable_scene_references and any(item.tag == "UNUSED-SCENE" for item in index.findings):
        notes += [
            "",
            "NOTE ON UNUSED SCENES",
            "-" * _REPORT_WIDTH,
            f"{index.variable_scene_references} action(s) in this configuration name the Scene they act on",
            "with a variable (e.g. Show Scene %Which_Menu) rather than by name.  Which",
            "Scene each one means is decided on the device, so any of the Scenes listed",
            "above may in fact be shown that way.  Treat that list as somewhere to start",
            "looking rather than as a list of Scenes that are safe to delete.",
            "",
        ]

    return notes


def run_health_check() -> tuple[str, dict]:
    """Scan the loaded configuration and return (report text, counts by severity).

    Safe to call with nothing loaded -- the tables are empty and the report says so --
    but the GUI checks first so it can say something more useful than "0 Projects".
    """
    index = _Index()

    for task_id, task in PrimeItems.tasker_root_elements["all_tasks"].items():
        if task["name"]:
            index.task_ids_by_name[task["name"]].append(task_id)

    # Order matters: _index_projects fills in the project_of_* maps that the passes after
    # it use to say which Project a finding is in.
    _index_projects(index)
    _index_profiles(index)
    _index_scenes(index)
    _index_actions(index)
    _index_scene_inline_actions(index)

    _check_reachability(index)
    _check_hygiene(index)

    return _build_report(index, datetime.now()), _counts(index.findings)  # noqa: DTZ005


def write_health_check_report(report: str) -> str:
    """Write the report to a timestamped file in the current runtime directory.

    Returns the file name written, or "" if the write failed -- the caller reports the
    file name to the user, and a health check whose findings displayed fine is still
    worth showing when only the save went wrong.

    Named date-then-time (MapTasker_HealthCheck_08-17-2026_14-52-07.txt), zero padded so
    the name is a fixed width and successive reports from the same day sort by when they
    were run.  datetime.now() rather than maputils'
    get_current_local_time_auto_timezone: that one geolocates by IP with a five second
    timeout, which is a strange thing to make a local button click wait for.
    """
    stamp = datetime.now().strftime("_%m-%d-%Y_%H-%M-%S")  # noqa: DTZ005
    file_name = append_to_filename(HEALTHCHECK_FILE, stamp)
    if not file_name:
        return ""
    try:
        with open(os.path.join(os.getcwd(), file_name), "w", encoding="utf-8") as output_file:
            output_file.write(report)
    except OSError as error:
        logger.error(f"Health Check report could not be written: {error}")
        return ""
    return file_name
