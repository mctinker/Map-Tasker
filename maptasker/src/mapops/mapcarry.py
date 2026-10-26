"""mapcarry: bring a Project, Profile, Task or Scene in from another backup, with everything it needs."""

#! /usr/bin/env python3

#                                                                                        #
# mapcarry: Import With Dependencies.                                                    #
#                                                                                        #
# Pick a Task in a backup that is not the one open -- a tablet's, a friend's, last year's -- and   #
# this works out what it takes to make that Task work HERE, and brings all of it: the Tasks it    #
# performs, the Scenes it shows and the Tasks those run, the global variables they use, and for   #
# a Profile the Entry and Exit Tasks it runs.  Tasker's own export of a Task or a Profile leaves  #
# every one of those behind, and a Task that performs a Task that is not there is a Task that     #
# quietly does half its job.                                                                      #
#                                                                                        #
# WHAT "NEEDS" MEANS, AND WHAT IT DOES NOT                                                        #
#                                                                                        #
# A thing is needed when the chosen object, or something already needed, REFERS to it in a way     #
# the file states plainly:                                                                        #
#                                                                                        #
#   Task     Perform Task (by name), and the Show/Create/Hide/Destroy Scene and Scene Element      #
#            actions (by Scene name -- healthck.scene_name_args has the list).                    #
#   Scene    the Task each element runs, which a Scene holds by Task ID, and the same two kinds    #
#            of action inside the Scene's own inline Tasks.                                       #
#   Profile  its Entry and Exit Task (<mid0>, <mid1>), which are Task ids.                         #
#   Project  everything it lists.                                                                #
#                                                                                        #
# Not followed, and said so in the preview: a name assembled at run time ('%which'), which cannot   #
# be resolved from a file, and what is inside a Version 2 Scene's layout.  A Profile is never      #
# needed by a Task -- Profile Status only reads one.                                              #
#                                                                                        #
# WHAT IS DONE ABOUT A NAME THIS FILE ALREADY HAS                                                  #
#                                                                                        #
# Two Tasks called 'Setup' are the commonest thing in two backups.  A Task or Scene that is here   #
# already AND is the same thing -- the same actions, whose own needs are in turn the same -- is     #
# used, not copied: importing twice, or importing two things that share a helper, must not pile    #
# up copies of it.  One that is here with the same name and is different is brought in under      #
# 'name (imported)' and every call inside what is being brought is repointed at it, because the     #
# point is that what was imported behaves as it did where it came from.  It is never merged into      #
# what is here: nothing already in this file is changed, apart from the one Project it is filed      #
# in gaining members.                                                                              #
#                                                                                        #
# IDS ARE NEW.  Tasker hands out ids from one counter that the device has also been drawing on      #
# since the backup was taken, so an id that is free in this FILE is not safe to keep (see           #
# taskedit.next_unique_task_or_profile_id for the headroom it leaves).  Every Task and Profile      #
# brought in is given a fresh one and every link that named the old one -- a Profile's Entry and     #
# Exit Task, a Scene element's Task -- follows it.                                                #
#                                                                                        #
# THE REFACTOR MACHINERY, NOT A COPY OF IT                                                          #
#                                                                                        #
# This is one change made of steps that mean nothing apart, so it is a maprefac_model.Plan: planned    #
# and previewed before anything happens, refused with blocks when it cannot be done, applied by      #
# maprefac.apply -- the attachment re-checked, one press of Undo.  Registration is Duplicate's own   #
# (taskedit_save.register_new_task and its siblings).  What is new is only where the objects come    #
# from, which is another file, and the walk that decides which of them to take.                     #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import copy
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from maptasker.src.analysis import healthck
from maptasker.src.core import scenelayout
from maptasker.src.core.editcommon import set_child_text
from maptasker.src.core.mapjump import PROFILE, PROJECT, SCENE, TASK, Target
from maptasker.src.core.plugset import plugin_package
from maptasker.src.edit import profedit, projedit, taskedit, taskedit_model, taskedit_save
from maptasker.src.mapgen import varxref
from maptasker.src.mapgen.taskertables import get_first_action
from maptasker.src.mapops import maprefac
from maptasker.src.mapops.maprefac_duplicate import unique_name
from maptasker.src.mapops.maprefac_model import (
    Block,
    Plan,
    Step,
    action_code,
    actions_of,
    blocked,
    members,
    now_millis,
    object_table,
    profile_task_ids,
    string_argument,
    task_target,
    variable_names,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.analysis.xmldiff import Configuration
    from maptasker.src.core.primitem import RunState

# maprefac_model.Plan.kind for the plans built here: a fifth kind that only this module and its dialog see.
CARRY = "carry"

# What unique_name puts in brackets after a name this file already has for something different.
IMPORTED = "imported"

# The destination that means "a Project of its own", for a Task, Profile or Scene.  A Project that is
# imported is always given one.
NEW_PROJECT = ""

# The kinds a pick can be, in the order a list offers them.
KINDS = (PROJECT, PROFILE, TASK, SCENE)
_KIND_WORDS = {PROJECT: "Project", PROFILE: "Profile", TASK: "Task", SCENE: "Scene"}

# What a copy of an object is no longer the same thing for, when two are compared: its own id and name (the
# name is how one is looked up, and a copy made here is called something else), its dates, and the TaskerNet
# description, none of which is what it does.
_IGNORED_WHEN_COMPARING = frozenset({"id", "nme", "edate", "cdate", "mdate", "Share"})

# The suffix this module itself puts on a name: "Fade (imported)", "Fade (imported 2)".
_IMPORTED_SUFFIX = re.compile(rf" \({IMPORTED}(?: \d+)?\)$")

# What a plan says about how an object will be dealt with.
COPY = "copy"
REUSE = "reuse"

_PERFORM_TASK = taskedit_model.PERFORM_TASK_ACTION_CODE
_PERFORM_TASK_NAME_ARG = taskedit_model.PERFORM_TASK_NAME_ARG_ID

# How many words of the "needs" a one-line heading names before it counts them instead.
_VARIABLES_SHOWN = 8

# How many earlier imports of one name are looked through for a copy that is the same thing.
_EARLIER_COPIES = 20


# ##################################################################################
# What can be picked.
# ##################################################################################


@dataclass(frozen=True)
class Pick:
    """One object the other file offers, as a list shows it.

    `key` is the Task's or Profile's id and the Project's or Scene's name -- the split every table in
    this program makes -- and `label` is what a person reads, with the Project it is in, since two Tasks
    called 'Setup' in different Projects are ordinary.
    """

    kind: str
    key: str
    label: str
    project: str = ""

    @property
    def word(self) -> str:
        """'Task', 'Profile', 'Scene' or 'Project'."""
        return _KIND_WORDS[self.kind]


def _table(source: Configuration, name: str) -> dict[str, Any]:
    """One of the other file's object tables, or {} when it has none."""
    return cast("dict[str, Any]", (source.tables or {}).get(name) or {})


def _owners(source: Configuration, tag: str) -> dict[str, str]:
    """{member: the first Project of the other file that lists it}, for <pids>, <tids> or <scenes>."""
    owners: dict[str, str] = {}
    for project_name, entry in _table(source, "all_projects").items():
        for member in members(entry["xml"], tag):
            owners.setdefault(member, project_name)
    return owners


def picks(source: Configuration) -> list[Pick]:
    """Everything the other file holds that can be brought in, Projects first, then by Project and name."""
    found: list[Pick] = [Pick(PROJECT, name, name) for name in _table(source, "all_projects")]
    for kind, table_name, tag, fallback in (
        (PROFILE, "all_profiles", "pids", "Profile"),
        (TASK, "all_tasks", "tids", "Task"),
        (SCENE, "all_scenes", "scenes", "Scene"),
    ):
        owners = _owners(source, tag)
        for key, entry in _table(source, table_name).items():
            name = entry.get("name", "") or f"{fallback} {key}"
            project = owners.get(key, "")
            found.append(Pick(kind, key, f"{name}  ({project})" if project else name, project))
    order = {kind: position for position, kind in enumerate(KINDS)}
    found.sort(key=lambda pick: (order[pick.kind], pick.project.lower(), pick.label.lower()))
    return found


# ##################################################################################
# What a pick needs.
# ##################################################################################


@dataclass
class Needs:
    """Everything one pick takes with it, in the other file's own terms and in the order found.

    Each of the three dictionaries maps what is needed to WHY, in words ("run by Profile 'Wake'",
    "performed by Task 'Setup'"), so the preview can say what pulled a thing in -- the line that tells
    somebody a Task they never heard of is coming along because the one they chose calls it.
    """

    pick: Pick
    tasks: dict[str, str] = field(default_factory=dict[str, str])  # Task id -> why
    profiles: dict[str, str] = field(default_factory=dict[str, str])  # Profile id -> why
    scenes: dict[str, str] = field(default_factory=dict[str, str])  # Scene name -> why
    # Global variables the objects use that the other file gives a value to: name -> that value.
    variables: dict[str, str] = field(default_factory=dict[str, str])
    # Plugin packages the objects use, and how many places use each.
    plugins: dict[str, int] = field(default_factory=dict[str, int])
    # What could not be followed, one sentence each.
    unresolved: list[str] = field(default_factory=list[str])
    # The Version 2 Scenes among them, whose layouts name Tasks and Scenes that are not rewritten.
    layouts: list[str] = field(default_factory=list[str])

    @property
    def is_empty(self) -> bool:
        """Whether there is nothing at all to bring."""
        return not (self.tasks or self.profiles or self.scenes)


def _scene_references(element: Element, scene_args: dict[str, str]) -> list[tuple[str, str, str]]:
    """Every (kind, name, code) an element's actions name by name: 'task' for a Perform Task, 'scene' for a Scene action.

    Walks every Action anywhere beneath the element, which reaches a Scene's own inline Tasks as well
    as a Task's -- the reason maprefac_duplicate and healthck do.  A name with a variable in it is
    chosen on the device and cannot be resolved here, so it is left out; so is a Version 2 Scene given
    as a whole layout rather than a name.
    """
    found: list[tuple[str, str, str]] = []
    for action in element.iter("Action"):
        code = action_code(action)
        if code == _PERFORM_TASK:
            name = string_argument(action, _PERFORM_TASK_NAME_ARG)
            kind = "task"
        elif code in scene_args:
            name = string_argument(action, scene_args[code])
            kind = "scene"
        else:
            continue
        if name and "%" not in name and not name.startswith(("{", "[")):
            found.append((kind, name, code))
    return found


def _scene_task_ids(scene: Element) -> list[str]:
    """The Task ids a Scene's elements run: every '<clickTask>939</clickTask>' beneath it, whatever the event."""
    ids = [
        (node.text or "").strip()
        for node in scene.iter()
        if node is not scene and node.tag.endswith("Task") and (node.text or "").strip().isdigit()
    ]
    return list(dict.fromkeys(ids))


def _source_variables(source: Configuration) -> dict[str, Element]:
    """The other file's global variables, by name -- the <Variable> elements directly under its root."""
    root = source.root
    if root is None:
        return {}
    return {(child.findtext("n") or "").strip(): child for child in root.findall("Variable")}


class _Walk:
    """The walk over what a pick needs: a queue of Tasks and Scenes to read, and what has been found."""

    def __init__(self, source: Configuration, pick: Pick) -> None:
        self.source = source
        self.needs = Needs(pick=pick)
        self.scene_args = healthck.scene_name_args()
        self.tasks = _table(source, "all_tasks")
        self.scenes = _table(source, "all_scenes")
        self.by_name = _table(source, "all_tasks_by_name")
        self.profiles = _table(source, "all_profiles")
        self.projects = _table(source, "all_projects")
        self.file = os.path.basename(source.path) or "the other file"
        self.queue: list[tuple[str, str]] = []

    def add_task(self, task_id: str, why: str) -> None:
        """Need this Task, unless it is already needed.  One the file does not hold is said, not followed."""
        if task_id in self.needs.tasks:
            return
        if task_id not in self.tasks:
            self.needs.unresolved.append(f"Task id {task_id} ({why}) is not in {self.file}.")
            return
        self.needs.tasks[task_id] = why
        self.queue.append((TASK, task_id))

    def add_scene(self, scene_name: str, why: str) -> None:
        """Need this Scene, unless it is already needed."""
        if scene_name in self.needs.scenes:
            return
        if scene_name not in self.scenes:
            self.needs.unresolved.append(f"Scene '{scene_name}' ({why}) is not in {self.file}.")
            return
        self.needs.scenes[scene_name] = why
        self.queue.append((SCENE, scene_name))

    def add_profile(self, profile_id: str, why: str) -> None:
        """Need this Profile and the Tasks it runs."""
        if profile_id in self.needs.profiles or profile_id not in self.profiles:
            return
        self.needs.profiles[profile_id] = why
        name = self.profiles[profile_id].get("name", "") or profile_id
        for task_id in profile_task_ids(self.profiles[profile_id]["xml"]):
            self.add_task(task_id, f"run by Profile '{name}'")

    def start(self) -> None:
        """Seed the queue with the pick itself."""
        pick = self.needs.pick
        if pick.kind == TASK:
            self.add_task(pick.key, "chosen")
        elif pick.kind == SCENE:
            self.add_scene(pick.key, "chosen")
        elif pick.kind == PROFILE:
            self.add_profile(pick.key, "chosen")
        elif pick.kind == PROJECT and pick.key in self.projects:
            element = self.projects[pick.key]["xml"]
            for profile_id in members(element, "pids"):
                self.add_profile(profile_id, f"in Project '{pick.key}'")
            for task_id in members(element, "tids"):
                self.add_task(task_id, f"in Project '{pick.key}'")
            for scene_name in members(element, "scenes"):
                self.add_scene(scene_name, f"in Project '{pick.key}'")

    def follow(self) -> None:
        """Read each Task and Scene queued, queueing what it names, until nothing new turns up."""
        while self.queue:
            kind, key = self.queue.pop(0)
            if kind == TASK:
                entry = self.tasks[key]
                owner = f"Task '{entry.get('name', '') or key}'"
                self._read(entry["xml"], owner)
            else:
                self._read(self.scenes[key]["xml"], f"Scene '{key}'")
                for task_id in _scene_task_ids(self.scenes[key]["xml"]):
                    self.add_task(task_id, f"run by Scene '{key}'")

    def _read(self, element: Element, owner: str) -> None:
        """Queue every Task and Scene an element's actions name."""
        for kind, name, _code in _scene_references(element, self.scene_args):
            if kind == "task":
                entry = self.by_name.get(name)
                if entry is None:
                    self.needs.unresolved.append(f"{owner} performs Task '{name}', which is not in {self.file}.")
                else:
                    self.add_task(entry["id"], f"performed by {owner}")
            elif name in self.scenes:
                self.add_scene(name, f"shown by {owner}")
            else:
                self.needs.unresolved.append(f"{owner} uses Scene '{name}', which is not in {self.file}.")

    def inventory(self) -> None:
        """Count the plugins used, find the global variables with a value, and note the Version 2 Scenes."""
        elements: list[Element] = [self.tasks[key]["xml"] for key in self.needs.tasks]
        elements += [self.scenes[key]["xml"] for key in self.needs.scenes]
        elements += [self.profiles[key]["xml"] for key in self.needs.profiles]

        for element in elements:
            for node in element.iter():
                if node.tag in {"Action", "Event", "State"}:
                    package = plugin_package(node)
                    if package:
                        self.needs.plugins[package] = self.needs.plugins.get(package, 0) + 1

        defined = _source_variables(self.source)
        for name in sorted(variable_names(elements)):
            if varxref.scope_of(name) == varxref.GLOBAL and name in defined:
                self.needs.variables[name] = (defined[name].findtext("v") or "").strip()

        self.needs.layouts = [
            scene_name
            for scene_name in self.needs.scenes
            if scenelayout.decode_v2_layout(self.scenes[scene_name]["xml"]) is not None
        ]


def needs_of(source: Configuration, kind: str, key: str) -> Needs | None:
    """What bringing this object in from `source` takes, or None when `source` has no such object."""
    table_name = {PROJECT: "all_projects", PROFILE: "all_profiles", TASK: "all_tasks", SCENE: "all_scenes"}.get(kind)
    if table_name is None or key not in _table(source, table_name):
        return None
    entry = _table(source, table_name)[key]
    label = entry.get("name", "") or key
    tag = {PROFILE: "pids", TASK: "tids", SCENE: "scenes"}.get(kind, "")
    owner = _owners(source, tag).get(key, "") if tag else ""
    walk = _Walk(source, Pick(kind, key, label, owner))
    walk.start()
    walk.follow()
    walk.inventory()
    return walk.needs


# ##################################################################################
# What is already here, and is it the same thing.
# ##################################################################################


def _is_named(element: Element) -> bool:
    """Whether an object's own XML gives it a name -- Tasker leaves one out for an unnamed Task or Profile."""
    return bool((element.findtext("nme") or "").strip())


def _fingerprint(
    element: Element, task_names: dict[str, str] | None = None, scene_args: dict[str, str] | None = None
) -> str:
    """What an object IS, as text, for telling whether two are the same.

    Everything it is made of except its own id, its dates and its TaskerNet description.  A Scene holds
    the Tasks it runs by ID, and ids differ from one file to the next for the same Task, so
    `task_names` -- {id: name}, from the file the Scene is in -- puts the Task's name there instead.

    A call's name is read without the suffix this module puts on a name it had to change: a Task imported
    before calls 'Fade (imported)' where the one it came from calls 'Fade', and they are still the same Task.
    """
    call_args = scene_args if scene_args is not None else healthck.scene_name_args()
    parts: list[str] = []

    def walk(node: Element, *, is_top: bool, call_arg: str = "") -> None:
        attributes = "" if is_top else ",".join(f"{name}={value}" for name, value in sorted(node.attrib.items()))
        text = (node.text or "").strip()
        if task_names is not None and node.tag.endswith("Task") and text.isdigit():
            if text not in task_names:
                return  # An element's Task that its own file does not hold: dropped on import, so not part of it.
            text = f"task:{task_names[text]}"
        if call_arg and node.tag == "Str" and node.attrib.get("sr") == call_arg:
            text = _IMPORTED_SUFFIX.sub("", text)
        parts.append(f"<{node.tag} {attributes}>{text}")
        arg = ""
        if node.tag == "Action":
            code = action_code(node)
            if code == _PERFORM_TASK:
                arg = f"arg{_PERFORM_TASK_NAME_ARG}"
            elif code in call_args:
                arg = f"arg{call_args[code]}"
        for child in node:
            if is_top and child.tag in _IGNORED_WHEN_COMPARING:
                continue
            walk(child, is_top=False, call_arg=arg)
        parts.append("/")

    walk(element, is_top=True)
    return "\n".join(parts)


def _imported_names(name: str) -> list[str]:
    """The names this module has given a copy of `name` before: 'name', 'name (imported)', 'name (imported 2)' ..."""
    return [
        name,
        f"{name} ({IMPORTED})",
        *(f"{name} ({IMPORTED} {number})" for number in range(2, _EARLIER_COPIES + 2)),
    ]


def _id_names(tables: dict[str, Any]) -> dict[str, str]:
    """{Task id: name} for one file's Tasks."""
    all_tasks = cast("dict[str, Any]", tables.get("all_tasks") or {})
    return {key: entry.get("name", "") for key, entry in all_tasks.items()}


@dataclass
class _Decision:
    """What is to be done with one Task or Scene: use the one that is here, or copy it under a name."""

    action: str
    name: str = ""  # a copy's name ("" for one that has none of its own)
    target_key: str = ""  # a reused object's id (Task) or name (Scene) in this file


class _Decisions:
    """Settle, before anything is touched, which Tasks and Scenes are used and which are copied, and what the copies are called.

    Worked out at PLAN time because the preview has to show it: "copy Task 'Setup' as 'Setup (imported)'"
    is the line that tells somebody the naming is not what they wanted, and it can only say that once the
    name is chosen.
    """

    def __init__(self, source: Configuration, needs: Needs, state: RunState) -> None:
        self.source = source
        self.needs = needs
        self.state = state
        self.scene_args = healthck.scene_name_args()
        self.tasks: dict[str, _Decision] = {}
        self.scenes: dict[str, _Decision] = {}
        self.profiles: dict[str, _Decision] = {}
        self._decide()

    def _tentative(self) -> None:
        """Mark as reused whatever is here under the same name and is identical, and everything else as a copy."""
        here_tasks = object_table("all_tasks_by_name", state=self.state)
        here_scenes = object_table("all_scenes", state=self.state)
        source_tasks = _table(self.source, "all_tasks")
        source_scenes = _table(self.source, "all_scenes")
        names_there = _id_names(self.source.tables)
        names_here = _id_names(self.state.tasker_root_elements)

        # A Project that is imported is brought whole, so the Tasks and Scenes it lists are always copied:
        # one it shared with a Project here would be listed by both, and deleting either's Tasks would take it.
        own_tasks, own_scenes = self._members_of_a_project()

        for task_id in self.needs.tasks:
            element = source_tasks[task_id]["xml"]
            name = source_tasks[task_id].get("name", "")
            decision = _Decision(COPY)
            if _is_named(element) and task_id not in own_tasks:
                for candidate in _imported_names(name):
                    present = here_tasks.get(candidate)
                    if present is None:
                        break
                    if _fingerprint(present["xml"]) == _fingerprint(element):
                        decision = _Decision(REUSE, name=candidate, target_key=present["id"])
                        break
            self.tasks[task_id] = decision

        for scene_name in self.needs.scenes:
            element = source_scenes[scene_name]["xml"]
            decision = _Decision(COPY)
            for candidate in () if scene_name in own_scenes else _imported_names(scene_name):
                present_scene = here_scenes.get(candidate)
                if present_scene is None:
                    break
                if _fingerprint(present_scene["xml"], names_here) == _fingerprint(element, names_there):
                    decision = _Decision(REUSE, name=candidate, target_key=candidate)
                    break
            self.scenes[scene_name] = decision

    def _members_of_a_project(self) -> tuple[set[str], set[str]]:
        """The (Task ids, Scene names) the picked Project lists, or two empty sets for anything else."""
        pick = self.needs.pick
        projects = _table(self.source, "all_projects")
        if pick.kind != PROJECT or pick.key not in projects:
            return set(), set()
        element = projects[pick.key]["xml"]
        return set(members(element, "tids")), set(members(element, "scenes"))

    def _dependencies(self, element: Element, *, is_scene: bool) -> tuple[list[str], list[str]]:
        """The (Task ids, Scene names) of the objects being brought that this element depends on."""
        by_name = _table(self.source, "all_tasks_by_name")
        task_ids: list[str] = []
        scene_names: list[str] = []
        for kind, name, _code in _scene_references(element, self.scene_args):
            if kind == "task" and name in by_name and by_name[name]["id"] in self.needs.tasks:
                task_ids.append(by_name[name]["id"])
            elif kind == "scene" and name in self.needs.scenes:
                scene_names.append(name)
        if is_scene:
            task_ids.extend(task_id for task_id in _scene_task_ids(element) if task_id in self.needs.tasks)
        return task_ids, scene_names

    def _settle(self) -> None:
        """Take back any reuse whose own needs are not reused.

        A Task here that reads the same as the one being brought but performs a DIFFERENT Task of the
        name it calls is not the same Task, and using it would run the wrong helper.  Demoting one
        can demote its callers, so this goes round until nothing moves.
        """
        source_tasks = _table(self.source, "all_tasks")
        source_scenes = _table(self.source, "all_scenes")
        changed = True
        while changed:
            changed = False
            for task_id, decision in self.tasks.items():
                if decision.action != REUSE:
                    continue
                task_ids, scene_names = self._dependencies(source_tasks[task_id]["xml"], is_scene=False)
                if any(self.tasks[other].action == COPY for other in task_ids) or any(
                    self.scenes[other].action == COPY for other in scene_names
                ):
                    self.tasks[task_id] = _Decision(COPY)
                    changed = True
            for scene_name, decision in self.scenes.items():
                if decision.action != REUSE:
                    continue
                task_ids, scene_names = self._dependencies(source_scenes[scene_name]["xml"], is_scene=True)
                if any(self.tasks[other].action == COPY for other in task_ids) or any(
                    self.scenes[other].action == COPY for other in scene_names
                ):
                    self.scenes[scene_name] = _Decision(COPY)
                    changed = True

    def _name_the_copies(self) -> None:
        """Give each copy a name nothing here has, and nothing chosen for another copy has either."""
        source_tasks = _table(self.source, "all_tasks")
        taken = set(object_table("all_tasks_by_name", state=self.state))
        for task_id, decision in self.tasks.items():
            if decision.action == REUSE:
                continue
            if not _is_named(source_tasks[task_id]["xml"]):
                continue
            decision.name = unique_name(source_tasks[task_id].get("name", ""), taken, IMPORTED)
            taken.add(decision.name)

        taken = set(object_table("all_scenes", state=self.state))
        for scene_name, decision in self.scenes.items():
            if decision.action == COPY:
                decision.name = unique_name(scene_name, taken, IMPORTED)
                taken.add(decision.name)

        source_profiles = _table(self.source, "all_profiles")
        taken = set(object_table("all_profiles_by_name", state=self.state))
        for profile_id in self.needs.profiles:
            decision = _Decision(COPY)
            if _is_named(source_profiles[profile_id]["xml"]):
                decision.name = unique_name(source_profiles[profile_id].get("name", ""), taken, IMPORTED)
                taken.add(decision.name)
            self.profiles[profile_id] = decision

    def _decide(self) -> None:
        self._tentative()
        self._settle()
        self._name_the_copies()

    def task_name_map(self) -> dict[str, str]:
        """{name in the other file: name here} for every Task whose name is not the same here."""
        source_tasks = _table(self.source, "all_tasks")
        return {
            source_tasks[task_id].get("name", ""): decision.name
            for task_id, decision in self.tasks.items()
            if decision.name and decision.name != source_tasks[task_id].get("name", "")
        }

    def scene_name_map(self) -> dict[str, str]:
        """{Scene name in the other file: name here} for every Scene whose name is not the same here."""
        return {
            name: decision.name for name, decision in self.scenes.items() if decision.name and decision.name != name
        }


# ##################################################################################
# The plan.
# ##################################################################################


def _destination(pick: Pick, into: str, state: RunState) -> tuple[str, bool]:
    """(the Project everything is filed in, whether it is a new one).  A new one is named for what it holds."""
    projects = object_table("all_projects", state=state)
    if pick.kind == PROJECT or into == NEW_PROJECT:
        base = pick.key if pick.kind == PROJECT else (pick.project or "Imported")
        return unique_name(base, set(projects), IMPORTED), True
    return into, False


def _steps(
    source: Configuration,
    needs: Needs,
    decisions: _Decisions,
    destination: tuple[str, bool],
    new_variables: dict[str, str],
    state: RunState,
) -> list[Step]:
    """What will happen, one line each: the Project, then Profiles, Tasks and Scenes, then variables."""
    project_name, is_new = destination
    source_tasks = _table(source, "all_tasks")
    steps: list[Step] = []
    project_target = Target(kind=PROJECT, key=project_name, name=project_name)

    steps.append(
        Step(f"Create Project '{project_name}' to hold what is brought in")
        if is_new
        else Step(f"File what is brought in under Project '{project_name}'", project_target)
    )

    for profile_id, why in needs.profiles.items():
        entry = _table(source, "all_profiles")[profile_id]
        original = entry.get("name", "") or profile_id
        chosen = decisions.profiles[profile_id].name
        renamed = f" as '{chosen}'" if chosen and chosen != original else ""
        steps.append(Step(f"Copy Profile '{original}'{renamed} -- {why}"))

    for task_id, why in needs.tasks.items():
        decision = decisions.tasks[task_id]
        original = source_tasks[task_id].get("name", "") or task_id
        if decision.action == REUSE:
            steps.append(
                Step(
                    f"Use Task '{decision.name}', which this file already has"
                    f"{'' if decision.name == original else f' from an earlier import of {original!r}'}"
                    f" and which is identical -- {why}",
                    task_target(decision.target_key, state=state),
                ),
            )
            continue
        actions = len(actions_of(source_tasks[task_id]["xml"]))
        renamed = (
            f" as '{decision.name}', because this file already has a different Task called '{original}'"
            if decision.name and decision.name != original
            else ""
        )
        steps.append(Step(f"Copy Task '{original}' ({actions} actions){renamed} -- {why}"))

    for scene_name, why in needs.scenes.items():
        decision = decisions.scenes[scene_name]
        if decision.action == REUSE:
            steps.append(
                Step(
                    f"Use Scene '{decision.name}', which this file already has"
                    f"{'' if decision.name == scene_name else f' from an earlier import of {scene_name!r}'}"
                    f" and which is identical -- {why}",
                    Target(kind=SCENE, key=decision.name, name=decision.name),
                ),
            )
            continue
        renamed = (
            f" as '{decision.name}', because this file already has a different Scene called '{scene_name}'"
            if decision.name != scene_name
            else ""
        )
        steps.append(Step(f"Copy Scene '{scene_name}'{renamed} -- {why}"))

    steps.extend(Step(f"Add global variable {name} with the value '{value}'") for name, value in new_variables.items())
    return steps


def _warnings(
    needs: Needs,
    decisions: _Decisions,
    new_variables: dict[str, str],
    *,
    carry_variables: bool,
    state: RunState,
) -> list[str]:
    """What the preview has to say before the user presses Apply."""
    warnings: list[str] = []
    here = object_table("all_tasks_by_name", state=state)

    # A call this file can answer even though the other file could not.
    for line in needs.unresolved:
        called = _called_name(line)
        if called and called in here:
            continue
        warnings.append(f"{line}  Neither this file nor that one has it, so it stays as it is -- it will not run.")

    renamed_tasks = decisions.task_name_map()
    if renamed_tasks:
        listed = ", ".join(f"'{old}'" for old in list(renamed_tasks)[:_VARIABLES_SHOWN])
        warnings.append(
            f"Tasks brought in under a new name because this file has a different one of the same name: {listed}.  "
            "Every call inside what is brought in is repointed at them, so what you import behaves as it did where "
            "it came from.  To use your own Task of that name instead, change the call afterwards."
        )

    if needs.plugins:
        listed = ", ".join(sorted(needs.plugins))
        warnings.append(
            f"These need a plugin on the device, which this cannot check: {listed}.  Tasker shows a plugin "
            "action it cannot find as an error."
        )

    different = [
        name
        for name, value in needs.variables.items()
        if name not in new_variables and _here_value(name, state) not in {None, value}
    ]
    if different:
        warnings.append(
            "This file already gives these global variables a different value, and keeps its own: "
            + ", ".join(
                f"{name} (here '{_here_value(name, state)}', there '{needs.variables[name]}')"
                for name in different[:_VARIABLES_SHOWN]
            )
            + "."
        )
    missing = [name for name in needs.variables if name not in new_variables and _here_value(name, state) is None]
    if missing and not carry_variables:
        warnings.append(
            "These global variables are used, and this file has no value for them: "
            + ", ".join(missing[:_VARIABLES_SHOWN])
            + ".  Their value will be empty until something sets them."
        )

    if needs.layouts:
        warnings.append(
            "Version 2 Scene "
            + ", ".join(f"'{name}'" for name in needs.layouts)
            + ": the Tasks and Scenes its layout names are inside its own data and are not followed or renamed."
        )

    warnings.append(
        "Tasks and Profiles are given new ids, and every link to them is followed.  A call built from a variable "
        "('%which') is chosen on the device and cannot be followed from a file."
    )
    return warnings


def _called_name(line: str) -> str:
    """The Task name a 'performs Task 'X', which is not in ...' line is about, or ""."""
    marker = "performs Task '"
    if marker not in line:
        return ""
    return line.split(marker, 1)[1].split("'", 1)[0]


def _here_value(name: str, state: RunState) -> str | None:
    """The value this file gives a global variable, or None when it does not have one."""
    root = cast("Element | None", state.xml_root)
    for child in root.findall("Variable") if root is not None else ():
        if (child.findtext("n") or "").strip() == name:
            return (child.findtext("v") or "").strip()
    return None


def plan_carry(
    source: Configuration,
    kind: str,
    key: str,
    into: str = NEW_PROJECT,
    *,
    carry_variables: bool = True,
    state: RunState,
) -> Plan:
    """Plan bringing `kind` `key` in from `source` with what it needs, into Project `into` (or a new one).

    `into` is the name of a Project in the loaded file, or NEW_PROJECT.  A Project that is imported is
    always given a Project of its own, so `into` is ignored for one.
    """
    word = _KIND_WORDS.get(kind, kind)
    needs = needs_of(source, kind, key)
    if needs is None:
        return blocked(CARRY, f"Import {word}", Block("NOT-THERE", f"That {word} is not in the other file."))

    file = os.path.basename(source.path) or "the other file"
    what = f"Import {word} '{needs.pick.label}' from {file}"
    if needs.is_empty:
        return blocked(CARRY, what, Block("NOTHING-TO-BRING", f"{word} '{needs.pick.label}' holds nothing to bring."))

    projects = object_table("all_projects", state=state)
    if kind != PROJECT and into != NEW_PROJECT and into not in projects:
        return blocked(CARRY, what, Block("NO-PROJECT", f"Project '{into}' is not in this file."))

    decisions = _Decisions(source, needs, state)
    destination = _destination(needs.pick, into, state)
    new_variables = (
        {name: value for name, value in needs.variables.items() if _here_value(name, state) is None}
        if carry_variables
        else {}
    )

    brings_something = (
        destination[1]
        or new_variables
        or any(decision.action == COPY for decision in (*decisions.tasks.values(), *decisions.scenes.values()))
        or decisions.profiles
    )
    if not brings_something:
        return blocked(
            CARRY,
            what,
            Block(
                "ALREADY-HERE",
                "Everything this needs is already in this file, and identical.  There is nothing to bring.",
            ),
        )

    plan = Plan(kind=CARRY, what=what)
    if not destination[1]:
        plan.elements = (projects[destination[0]]["xml"],)
    plan.steps = _steps(source, needs, decisions, destination, new_variables, state)
    plan.warnings = _warnings(needs, decisions, new_variables, carry_variables=carry_variables, state=state)
    plan.run = _Carrier(source, needs, decisions, destination, new_variables, state).run
    return plan


# ##################################################################################
# Doing it.
# ##################################################################################


def _next_project_sr(state: RunState) -> str:
    """The next free 'projN' attribute -- projedit.create_new_project's numbering, so the two cannot clash."""
    prefix = "proj"
    used = [
        int(entry["xml"].attrib.get("sr", "")[len(prefix) :])
        for entry in object_table("all_projects", state=state).values()
        if entry["xml"].attrib.get("sr", "").startswith(prefix)
        and entry["xml"].attrib.get("sr", "")[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(used, default=0) + 1}"


class _Carrier:
    """What applying a plan does: copy, link and register, in the order that lets each step find what it needs.

    Tasks first, since Profiles and Scenes name them by id; then Scenes; then every by-name call inside
    all that was copied is repointed, once all of it exists; then Profiles; then the Project that lists
    them, and last the global variables.
    """

    def __init__(
        self,
        source: Configuration,
        needs: Needs,
        decisions: _Decisions,
        destination: tuple[str, bool],
        new_variables: dict[str, str],
        state: RunState,
    ) -> None:
        self.source = source
        self.needs = needs
        self.decisions = decisions
        self.project_name, self.is_new_project = destination
        self.new_variables = new_variables
        self.state = state
        self.reserved: set[str] = set()
        self.task_ids: dict[str, str] = {}  # id in the other file -> id here, reused or copied
        self.copied_tasks: list[str] = []  # ids here of the Tasks that were copied, in order
        self.copied_profiles: list[str] = []
        self.copied_scenes: list[str] = []

    def run(self) -> list[str]:
        """Make the import.  Returns the errors, and there are none a plan could not see coming."""
        self._copy_tasks()
        self._copy_scenes()
        self._repoint()
        self._copy_profiles()
        self._file_them()
        self._add_variables()
        return []

    def _next_id(self) -> str:
        """An id no Task or Profile has, and none this import has taken."""
        new_id = str(taskedit.next_unique_task_or_profile_id(self.reserved, state=self.state))
        self.reserved.add(new_id)
        return new_id

    def _copy_tasks(self) -> None:
        """Copy each Task the plan copies, under its new id and name; note the id a reused one already has."""
        source_tasks = _table(self.source, "all_tasks")
        for task_id, decision in self.decisions.tasks.items():
            if decision.action == REUSE:
                self.task_ids[task_id] = decision.target_key
                continue
            new_id = self._next_id()
            element = copy.deepcopy(source_tasks[task_id]["xml"])
            element.set("sr", f"task{new_id}")
            set_child_text(element, "id", new_id)
            set_child_text(element, "edate", now_millis())
            if _is_named(element):
                set_child_text(element, "nme", decision.name)
                table_name = decision.name
            else:
                table_name = f"{get_first_action(element, state=self.state).rstrip()}.{new_id} (Unnamed)"
            taskedit_save.register_new_task(
                taskedit_model.EditableTask(task_id=new_id, task_element=element), table_name, state=self.state
            )
            self.task_ids[task_id] = new_id
            self.copied_tasks.append(new_id)

    def _copy_scenes(self) -> None:
        """Copy each Scene the plan copies, its elements' Tasks pointed at the Tasks here."""
        source_scenes = _table(self.source, "all_scenes")
        # The live table itself: object_table answers a fresh {} for an empty one, and a Scene added to that
        # would be lost -- which is every file that has no Scenes yet.
        here = self.state.tasker_root_elements.setdefault("all_scenes", {})
        for scene_name, decision in self.decisions.scenes.items():
            if decision.action == REUSE:
                continue
            element = copy.deepcopy(source_scenes[scene_name]["xml"])
            element.set("sr", f"scene{decision.name}")
            set_child_text(element, "nme", decision.name)
            if decision.name != scene_name:
                scenelayout.rename_v2_layout(element, decision.name)
            # An element's Task that the other file did not hold is dropped rather than left naming an id
            # that, here, belongs to something unrelated -- the plan has said it is not there.
            for parent in list(element.iter()):
                for node in list(parent):
                    text = (node.text or "").strip()
                    if not (node.tag.endswith("Task") and text.isdigit()):
                        continue
                    if text in self.task_ids:
                        node.text = self.task_ids[text]
                    else:
                        parent.remove(node)
            here[decision.name] = {"xml": element, "name": decision.name}
            self.copied_scenes.append(decision.name)

    def _repoint(self) -> None:
        """Every by-name call inside what was copied, repointed at the names chosen -- once all of it exists."""
        task_names = self.decisions.task_name_map()
        scene_names = self.decisions.scene_name_map()
        if not (task_names or scene_names):
            return
        scene_args = healthck.scene_name_args()
        elements: list[Element] = [
            object_table("all_tasks", state=self.state)[task_id]["xml"] for task_id in self.copied_tasks
        ]
        elements += [object_table("all_scenes", state=self.state)[name]["xml"] for name in self.copied_scenes]
        for element in elements:
            for action in element.iter("Action"):
                code = action_code(action)
                if code == _PERFORM_TASK:
                    mapping, arg_id = task_names, _PERFORM_TASK_NAME_ARG
                elif code in scene_args:
                    mapping, arg_id = scene_names, scene_args[code]
                else:
                    continue
                for child in action.findall("Str"):
                    if child.attrib.get("sr") == f"arg{arg_id}" and (child.text or "").strip() in mapping:
                        child.text = mapping[(child.text or "").strip()]

    def _copy_profiles(self) -> None:
        """Copy each Profile, its Entry and Exit Task links pointed at the Tasks here."""
        source_profiles = _table(self.source, "all_profiles")
        for profile_id, decision in self.decisions.profiles.items():
            new_id = self._next_id()
            element = copy.deepcopy(source_profiles[profile_id]["xml"])
            element.set("sr", f"prof{new_id}")
            set_child_text(element, "id", new_id)
            table_name = source_profiles[profile_id].get("name", "") or new_id
            if _is_named(element):
                set_child_text(element, "nme", decision.name)
                table_name = decision.name
            for child in list(element):
                if child.tag in {"mid0", "mid1"}:
                    current = (child.text or "").strip()
                    if current in self.task_ids:
                        child.text = self.task_ids[current]
                    else:
                        element.remove(child)  # The other file did not have it; here that id is something else.
            profedit.register_new_profile(
                profedit.EditableProfile(
                    profile_id=new_id,
                    profile_element=element,
                    entry_task_id=element.findtext("mid0", "") or "",
                    exit_task_id=element.findtext("mid1", "") or "",
                ),
                table_name,
                state=self.state,
            )
            self.copied_profiles.append(new_id)

    def _file_them(self) -> None:
        """List everything that was copied in the Project, making the Project first when it is a new one."""
        projects = object_table("all_projects", state=self.state)
        if self.is_new_project:
            element = self._new_project_element()
            projedit.register_new_project(
                projedit.EditableProject(project_name=self.project_name, project_element=element), state=self.state
            )
            for tag in ("tids", "pids", "scenes"):
                projedit.set_project_members(element, tag, [])
        else:
            element = projects[self.project_name]["xml"]

        for tag, new in (
            ("tids", self.copied_tasks),
            ("pids", self.copied_profiles),
            ("scenes", self.copied_scenes),
        ):
            existing = members(element, tag)
            projedit.set_project_members(element, tag, [*existing, *(item for item in new if item not in existing)])

    def _new_project_element(self) -> Element:
        """The Project everything is filed in when it is a new one.

        The other file's own Project for a Project import -- its colour, icon and so on come with it -- and
        a blank one, built the way Add Project builds it, for anything else.
        """
        pick = self.needs.pick
        source_projects = _table(self.source, "all_projects")
        if pick.kind == PROJECT and pick.key in source_projects:
            element = copy.deepcopy(source_projects[pick.key]["xml"])
            element.set("sr", _next_project_sr(self.state))
            set_child_text(element, "id", str(uuid.uuid4()))
        else:
            created = projedit.create_new_project(self.project_name, state=self.state)
            if isinstance(created, str):
                msg = created
                raise ValueError(msg)
            element = created.project_element
        set_child_text(element, "name", self.project_name)
        return element

    def _add_variables(self) -> None:
        """Add the global variables this file lacks, after the last one it has -- or before its Settings."""
        root = cast("Element | None", self.state.xml_root)
        if not self.new_variables or root is None:
            return
        source_variables = _source_variables(self.source)
        used = [
            int(sr[len("vars") :])
            for sr in (child.attrib.get("sr", "") for child in root.findall("Variable"))
            if sr.startswith("vars") and sr[len("vars") :].isdigit()
        ]
        number = max(used, default=-1) + 1
        children = list(root)
        position = len(children)
        last_variable = max((index for index, child in enumerate(children) if child.tag == "Variable"), default=-1)
        if last_variable >= 0:
            position = last_variable + 1
        else:
            position = next((index for index, child in enumerate(children) if child.tag == "Setting"), len(children))
        for name in self.new_variables:
            variable = copy.deepcopy(source_variables[name])
            variable.set("sr", f"vars{number}")
            root.insert(position, variable)
            position += 1
            number += 1


def carry(plan: Plan, state: RunState) -> tuple[bool, list[str]]:
    """Apply an import.  maprefac.apply, under this module's name so the dialog reads right.

    Everything that makes apply() safe is maprefac's -- the blocks refused again, the one Project the plan
    adds to re-checked as still attached, the whole of it one undo labelled with the plan's own heading.
    """
    return maprefac.apply(plan, state=state)
