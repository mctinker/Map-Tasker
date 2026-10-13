"""maprefac_duplicate: a Project, Profile, Task or Scene is copied under a name of its own."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src import profedit, projedit, taskedit, taskedit_model, taskedit_save
from maptasker.src.editcommon import set_child_text as _set_child_text
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK, Target
from maptasker.src.maprefac_model import (
    DUPLICATE,
    Block,
    Plan,
    Step,
    action_code,
    actions_of,
    blocked,
    display_project,
    members,
    now_millis,
    object_table,
    profile_target,
    profile_task_ids,
    projects_listing,
    task_target,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

# ##################################################################################
# Duplicate: a copy of an object, under a name of its own.
#
# Trivial for a Task and a Scene, which own nothing.  The whole difficulty is that a
# Profile owns Tasks and a Project owns everything, and a copy that shares its original's
# children is not a copy -- it is a second name for the same thing, and the first edit
# the user makes to "the copy" changes the original too.
#
# So a Profile and a Project are copied DEEP, and the ids and names of everything
# underneath are made new.  That in turn creates the only genuinely hard problem in this
# module: a Tasker configuration refers to Tasks and Scenes BY NAME, in the arguments of
# ordinary actions, and a deep copy that does not repoint those names produces a second
# Project whose actions all reach back into the first one.  It looks right in every view
# and is wrong the moment it runs.
#
# What is repointed is what the file states plainly: Perform Task's Name argument, and
# the Create/Show/Hide/Destroy Scene actions' own.  What is not is listed in the
# warnings, because a reference this cannot see is exactly the one the user has to check.
# ##################################################################################

# Create / Show / Hide / Destroy Scene.  Their arg0 is a Scene NAME -- the only other
# by-name reference in the action set besides Perform Task's.  The same four codes
# healthck names, for the same reason it has to name them: their argument is called "Name"
# rather than "Scene Name", so nothing can find them by looking at argument names.
_SCENE_NAME_CODES = {"46": "0", "47": "0", "48": "0", "49": "0"}


def unique_name(base: str, taken: set[str], suffix: str = "copy") -> str:
    """`base` if nothing has it, else 'base (copy)', 'base (copy 2)' and so on.

    Used for the children of a deep copy, whose names the user never chose.  Uniqueness is
    not cosmetic for a Task: Perform Task resolves a call by name across the whole file, so
    two Tasks sharing a name make every call to either of them ambiguous -- which is why
    healthck reports duplicate names as a finding of its own.

    Public, with the word in brackets a parameter, because maprestore has the same problem
    for the same reason: an object brought back from the history whose name has since been
    given to something else.  There it reads 'base (restored)', which says what happened
    where "(copy)" would say something that did not.
    """
    if base not in taken:
        return base
    candidate = f"{base} ({suffix})"
    counter = 2
    while candidate in taken:
        candidate = f"{base} ({suffix} {counter})"
        counter += 1
    return candidate


def _copy_task_element(task_element: Element, new_id: str, new_name: str) -> object:
    """A deep copy of a Task, under a new id and name, ready to register.

    <cdate> is left as the original's -- when this Task's actions were first written is a
    fact about them and copying does not change it -- while <edate> is stamped now, which
    is what every other write in this program does to a Task it has just produced.
    """
    element = copy.deepcopy(task_element)
    element.set("sr", f"task{new_id}")
    _set_child_text(element, "id", str(new_id))
    _set_child_text(element, "nme", new_name)
    _set_child_text(element, "edate", now_millis())
    return element


def _copy_profile_element(profile_element: Element, new_id: str, new_name: str) -> object:
    """A deep copy of a Profile, under a new id and name.  The Task links are left for the caller."""
    element = copy.deepcopy(profile_element)
    element.set("sr", f"prof{new_id}")
    _set_child_text(element, "id", str(new_id))
    _set_child_text(element, "nme", new_name)
    return element


def _copy_scene_element(scene_element: Element, new_name: str) -> object:
    """A deep copy of a Scene under a new name.

    A Scene's own sr is 'scene<its name>' rather than 'sceneN' -- unlike every other object
    in the format, which numbers them.  Measured across this repo's sample XML, where every
    Scene carries the name it is called; a copy keeping the original's sr would be the one
    place in the file that still says the old name.
    """
    element = copy.deepcopy(scene_element)
    element.set("sr", f"scene{new_name}")
    _set_child_text(element, "nme", new_name)
    return element


def _repoint_names(element: object, tasks: dict[str, str], scenes: dict[str, str]) -> int:
    """Rewrite by-name references inside a copied object to point at the copies.  Returns how many.

    Walks every <Action> anywhere beneath, which reaches a Scene's own inline anonymous
    Tasks as well as a Task's -- healthck makes the same point about its scan: those inline
    actions refer to Tasks and Scenes exactly as a named Task's do, and a second copy of
    this logic for them is how the two would drift apart.

    Only exact matches are rewritten.  A name assembled at run time ('%which') is not a
    reference this can resolve, and guessing at one would repoint a call the user meant to
    leave alone.
    """
    rewritten = 0
    for action in element.iter("Action"):
        code = action_code(action)
        if code == taskedit_model.PERFORM_TASK_ACTION_CODE:
            mapping, arg_id = tasks, taskedit_model.PERFORM_TASK_NAME_ARG_ID
        elif code in _SCENE_NAME_CODES:
            mapping, arg_id = scenes, _SCENE_NAME_CODES[code]
        else:
            continue
        for child in action.findall("Str"):
            if child.attrib.get("sr") != f"arg{arg_id}":
                continue
            current = (child.text or "").strip()
            if current in mapping:
                child.text = mapping[current]
                rewritten += 1
    return rewritten


def plan_duplicate(kind: str, key: str, new_name: str = "", *, state: RunState) -> Plan:
    """Copy a Project, Profile, Task or Scene under a new name.

    `key` is the Task's or Profile's id, and the Project's or Scene's name -- the same
    split every table in this program uses.  `new_name` empty means "choose one", which is
    the original's with '(copy)' appended and a number after that if it is taken too.
    """
    planners = {
        TASK: _plan_duplicate_task,
        PROFILE: _plan_duplicate_profile,
        SCENE: _plan_duplicate_scene,
        PROJECT: _plan_duplicate_project,
    }
    planner = planners.get(kind)
    if planner is None:
        return blocked(DUPLICATE, "Duplicate", Block("NOT-COPYABLE", f"A {kind} cannot be duplicated."))
    return planner(key, (new_name or "").strip(), state=state)


def _plan_duplicate_task(task_id: str, new_name: str, state: RunState) -> Plan:
    """Copy one Task, into the same Projects as the original."""
    entry = object_table("all_tasks", state=state).get(task_id)
    if entry is None:
        return blocked(DUPLICATE, "Duplicate a Task", Block("NO-TASK", "That Task is not in this file."))

    task_name = entry.get("name", "") or task_id
    new_name = new_name or unique_name(task_name, set(object_table("all_tasks_by_name", state=state)))
    what = f"Duplicate Task '{task_name}' as '{new_name}'"
    where = task_target(task_id, state=state)

    if taskedit.task_name_exists(new_name, state=state):
        return blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(TASK, new_name), where))

    owners = projects_listing("tids", task_id, state=state)
    actions = actions_of(entry["xml"])

    plan = Plan(kind=DUPLICATE, what=what, elements=(entry["xml"],))
    plan.steps = [
        Step(
            f"Create Task '{new_name}' with all {len(actions)} of Task '{task_name}'s actions",
            where,
        ),
        *(Step(f"Add Task '{new_name}' to Project '{owner}'", Target(kind=PROJECT, key=owner)) for owner in owners),
    ]
    plan.warnings = [
        (
            f"Nothing calls '{new_name}' yet.  A copy of a Task is not a copy of the calls to it: every "
            f"existing Perform Task still runs '{task_name}'."
        ),
    ]

    def run() -> list[str]:
        new_id = str(taskedit.next_unique_task_or_profile_id(state=state))
        element = _copy_task_element(entry["xml"], new_id, new_name)
        taskedit_save.register_new_task(
            taskedit_model.EditableTask(task_id=new_id, task_element=element), new_name, state=state
        )
        for project_name in owners:
            profedit.add_task_to_project(new_id, project_name, state=state)
        return []

    plan.run = run
    return plan


def _plan_duplicate_profile(profile_id: str, new_name: str, state: RunState) -> Plan:
    """Copy one Profile, and the Tasks it runs, into the same Projects as the original.

    Its Tasks are copied too, and that is the decision worth arguing.  A Profile sharing
    its original's Entry Task is a Profile that cannot be edited: change what the copy does
    and the original does it too, which is precisely what somebody duplicating a Profile in
    order to vary it does not want.  The cost is a second Task per copy, which is what
    Tasker's own "Duplicate" does on the device.
    """
    entry = object_table("all_profiles", state=state).get(profile_id)
    if entry is None:
        return blocked(DUPLICATE, "Duplicate a Profile", Block("NO-PROFILE", "That Profile is not in this file."))

    profile_element = entry["xml"]
    profile_name = entry.get("name", "") or profile_id
    new_name = new_name or unique_name(profile_name, set(object_table("all_profiles_by_name", state=state)))
    what = f"Duplicate Profile '{profile_name}' as '{new_name}'"
    where = profile_target(profile_id, state=state)

    if profedit.profile_name_exists(new_name, state=state):
        return blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(PROFILE, new_name), where))

    owners = projects_listing("pids", profile_id, state=state)
    task_ids = profile_task_ids(profile_element)
    taken = set(object_table("all_tasks_by_name", state=state))
    task_names = {}
    for task_id in task_ids:
        original = object_table("all_tasks", state=state).get(task_id, {}).get("name", "") or task_id
        task_names[task_id] = unique_name(original, taken)
        taken.add(task_names[task_id])

    plan = Plan(kind=DUPLICATE, what=what, elements=(profile_element,))
    plan.steps = [
        Step(f"Create Profile '{new_name}' with the same conditions as '{profile_name}'", where),
        *(
            Step(
                f"Copy its Task '{object_table('all_tasks', state=state).get(task_id, {}).get('name', '') or task_id}' as "
                f"'{task_names[task_id]}', and point the new Profile at that",
                task_target(task_id, state=state),
            )
            for task_id in task_ids
        ),
        *(Step(f"Add Profile '{new_name}' to Project '{owner}'", Target(kind=PROJECT, key=owner)) for owner in owners),
    ]
    plan.warnings = _duplicate_profile_warnings(new_name, task_ids, owners)

    def run() -> list[str]:
        reserved: set[str] = set()
        copied_task_ids = {}
        for task_id in task_ids:
            source = object_table("all_tasks", state=state).get(task_id)
            if source is None:
                continue
            new_task_id = str(taskedit.next_unique_task_or_profile_id(reserved, state=state))
            reserved.add(new_task_id)
            element = _copy_task_element(source["xml"], new_task_id, task_names[task_id])
            taskedit_save.register_new_task(
                taskedit_model.EditableTask(task_id=new_task_id, task_element=element), task_names[task_id], state=state
            )
            copied_task_ids[task_id] = new_task_id

        new_profile_id = str(taskedit.next_unique_task_or_profile_id(reserved, state=state))
        element = _copy_profile_element(profile_element, new_profile_id, new_name)
        for child in element:
            if child.tag in ("mid0", "mid1"):
                child.text = copied_task_ids.get((child.text or "").strip(), (child.text or "").strip())

        editable = profedit.EditableProfile(
            profile_id=new_profile_id,
            profile_element=element,
            entry_task_id=element.findtext("mid0", "") or "",
            exit_task_id=element.findtext("mid1", "") or "",
        )
        profedit.register_new_profile(editable, new_name, state=state)
        # add_profile_to_project files the copied Tasks under the Project too -- see its
        # own docstring on why a Project-linked Task with no <tids> entry is invisible.
        for project_name in owners:
            profedit.add_profile_to_project(editable, project_name, state=state)
        return []

    plan.run = run
    return plan


def _duplicate_profile_warnings(new_name: str, task_ids: list[str], owners: list[str]) -> list[str]:
    """What a duplicated Profile does and does not carry with it."""
    warnings = []
    if not task_ids:
        warnings.append(
            f"Profile '{new_name}' has no Entry or Exit Task to copy, because the original has none.  A "
            f"Profile with nothing to run is valid in the file and does nothing on the device.",
        )
    if not owners:
        warnings.append(
            "The original Profile is not listed by any Project, so the copy is not either -- neither of "
            "them will appear in the Map, the Diagram or the Tree until one is.",
        )
    warnings.append(
        "The copy is enabled or disabled exactly as the original is, and its conditions are the same ones.  "
        "Two Profiles watching for the same event both fire on it.",
    )
    return warnings


def _plan_duplicate_scene(scene_name: str, new_name: str, state: RunState) -> Plan:
    """Copy one Scene, into the same Projects as the original."""
    entry = object_table("all_scenes", state=state).get(scene_name)
    if entry is None:
        return blocked(DUPLICATE, "Duplicate a Scene", Block("NO-SCENE", "That Scene is not in this file."))

    new_name = new_name or unique_name(scene_name, set(object_table("all_scenes", state=state)))
    what = f"Duplicate Scene '{scene_name}' as '{new_name}'"
    where = Target(
        kind=SCENE, key=scene_name, name=scene_name, project=display_project("scenes", scene_name, state=state)
    )

    if new_name in object_table("all_scenes", state=state):
        return blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(SCENE, new_name), where))

    owners = projects_listing("scenes", scene_name, state=state)

    plan = Plan(kind=DUPLICATE, what=what, elements=(entry["xml"],))
    plan.steps = [
        Step(f"Create Scene '{new_name}' with all of Scene '{scene_name}'s elements", where),
        *(Step(f"Add Scene '{new_name}' to Project '{owner}'", Target(kind=PROJECT, key=owner)) for owner in owners),
    ]
    plan.warnings = [
        (
            "The copy's elements fire the same Tasks the original's do -- a Scene names the Task an element "
            "runs, and those Tasks are not copied.  Editing one of them changes what both Scenes do."
        ),
        f"Nothing shows '{new_name}' yet: every existing Show Scene action still names '{scene_name}'.",
    ]

    def run() -> list[str]:
        element = _copy_scene_element(entry["xml"], new_name)
        object_table("all_scenes", state=state)[new_name] = {"xml": element, "name": new_name}
        for project_name in owners:
            project_entry = object_table("all_projects", state=state).get(project_name)
            if project_entry is not None:
                projedit.set_project_members(
                    project_entry["xml"],
                    "scenes",
                    [*members(project_entry["xml"], "scenes"), new_name],
                )
        return []

    plan.run = run
    return plan


def _name_taken(kind: str, new_name: str) -> str:
    """The refusal for a name something else already has."""
    if kind == TASK:
        return (
            f"A Task named '{new_name}' is already in this file.  Perform Task calls a Task by name, so two "
            f"of them sharing one leaves every call to either ambiguous."
        )
    return f"A {kind.capitalize()} named '{new_name}' is already in this file.  Choose a different name."


# ##################################################################################
# Duplicating a Project: the deep one.
#
# A Project owns Profiles, Tasks and Scenes by listing their ids and names, so a copy has
# to produce a new one of each and a membership list pointing at those rather than at the
# originals.  Three things have to be right together, and each has its own failure:
#
#   NEW IDS.  A copy sharing the original's Task ids is not a copy at all -- both
#   Projects' <tids> then name the same Tasks, and the second Project is a second view of
#   the first.
#
#   NEW NAMES, AND THE LINKS THAT USE THEM REPOINTED.  A Task's id is private to the file;
#   its NAME is what Perform Task calls and what a Scene element runs.  Copy a Project
#   whose Tasks call one another and leave the names alone, and every call in the copy
#   reaches back into the original.
#
#   THE PROFILES' TASK LINKS REPOINTED, which are by id rather than by name and so need
#   doing separately from everything above.
#
# WHAT THIS DELIBERATELY DOES NOT COPY: global variables.  A Project does not own them --
# they are one namespace across the whole file, which is Tasker's design and not an
# oversight here -- so the copy reads and writes the same %Globals the original does.
# That is the single most likely surprise in this operation and it is the first warning.
# ##################################################################################

_PROJECT_SR_PREFIX = "proj"


def _next_project_sr(state: RunState) -> str:
    """The next free 'projN' attribute.

    A Project's sr is an internal counter unrelated to its <id> (which is a UUID) -- see
    projedit.create_new_project, whose own numbering this mirrors so that a duplicated
    Project and an added one cannot be handed the same one.
    """
    used = [
        int(entry["xml"].attrib.get("sr", "")[len(_PROJECT_SR_PREFIX) :])
        for entry in object_table("all_projects", state=state).values()
        if entry["xml"].attrib.get("sr", "").startswith(_PROJECT_SR_PREFIX)
        and entry["xml"].attrib.get("sr", "")[len(_PROJECT_SR_PREFIX) :].isdigit()
    ]
    return f"{_PROJECT_SR_PREFIX}{max(used, default=0) + 1}"


@dataclass(frozen=True)
class _ProjectCopy:
    """The names and ids a Project duplication has decided on, before any of it exists.

    Worked out at PLAN time rather than at apply time, because the preview has to show them:
    "copy its Task 'Wake Up' as 'Wake Up (copy)'" is the line that tells a user the naming
    is not what they wanted, and it can only say that if the name is already chosen.  The
    ids are the exception -- those are drawn when the copy is made, since a Task added in
    another dialog between the preview and the Apply would otherwise take the id this had
    reserved.
    """

    task_names: dict[str, str]  # old Task id -> the copy's name
    profile_names: dict[str, str]  # old Profile id -> the copy's name
    scene_names: dict[str, str]  # old Scene name -> the copy's name


def _plan_project_copy(project_element: Element, state: RunState) -> _ProjectCopy:
    """Choose a free name for every child of a Project about to be duplicated.

    Each kind is checked against its own table AND against the names chosen earlier in this
    same call: two Tasks of one Project called 'Setup' and 'Setup (copy)' would otherwise
    both be offered 'Setup (copy)', and the second registration would silently overwrite
    the first in all_tasks_by_name.
    """
    task_names, taken_tasks = {}, set(object_table("all_tasks_by_name", state=state))
    for task_id in members(project_element, "tids"):
        original = object_table("all_tasks", state=state).get(task_id, {}).get("name", "") or task_id
        task_names[task_id] = unique_name(original, taken_tasks)
        taken_tasks.add(task_names[task_id])

    profile_names, taken_profiles = {}, set(object_table("all_profiles_by_name", state=state))
    for profile_id in members(project_element, "pids"):
        original = object_table("all_profiles", state=state).get(profile_id, {}).get("name", "") or profile_id
        profile_names[profile_id] = unique_name(original, taken_profiles)
        taken_profiles.add(profile_names[profile_id])

    scene_names, taken_scenes = {}, set(object_table("all_scenes", state=state))
    for scene_name in members(project_element, "scenes"):
        scene_names[scene_name] = unique_name(scene_name, taken_scenes)
        taken_scenes.add(scene_names[scene_name])

    return _ProjectCopy(task_names=task_names, profile_names=profile_names, scene_names=scene_names)


def _plan_duplicate_project(project_name: str, new_name: str, state: RunState) -> Plan:
    """Copy a Project and everything it owns."""
    entry = object_table("all_projects", state=state).get(project_name)
    if entry is None:
        return blocked(DUPLICATE, "Duplicate a Project", Block("NO-PROJECT", "That Project is not in this file."))

    project_element = entry["xml"]
    new_name = new_name or unique_name(project_name, set(object_table("all_projects", state=state)))
    what = f"Duplicate Project '{project_name}' as '{new_name}'"
    where = Target(kind=PROJECT, key=project_name, name=project_name)

    if projedit.project_name_exists(new_name, state=state):
        return blocked(DUPLICATE, what, Block("NAME-TAKEN", _name_taken(PROJECT, new_name), where))

    chosen = _plan_project_copy(project_element, state=state)
    task_ids = members(project_element, "tids")
    profile_ids = members(project_element, "pids")
    scene_names = members(project_element, "scenes")

    plan = Plan(kind=DUPLICATE, what=what, elements=(project_element,))
    plan.steps = _duplicate_project_steps(new_name, chosen, task_ids, profile_ids, scene_names, where, state=state)
    plan.warnings = _duplicate_project_warnings(project_name, chosen, task_ids, state=state)

    plan.run = _ProjectDuplicator(project_element, new_name, chosen, task_ids, profile_ids, scene_names, state).run
    return plan


class _ProjectDuplicator:
    """The copying a Project duplication does when it is applied.

    What is copied is decided at plan time and held here: the Tasks, then the Profiles that
    point at them, then the Scenes, then the by-name references inside all of it, then the
    Project that lists them.  The ids of the new Tasks and Profiles are drawn as they are
    made, which is why they are state of this object rather than of the plan.
    """

    def __init__(
        self,
        project_element: Element,
        new_name: str,
        chosen: _ProjectCopy,
        task_ids: list[str],
        profile_ids: list[str],
        scene_names: list[str],
        state: RunState,
    ) -> None:
        """
        Args:
            project_element: The Project being copied.
            new_name: The copy's name.
            chosen: The names decided for the copies of everything it owns.
            task_ids: The ids of its Tasks.
            profile_ids: The ids of its Profiles.
            scene_names: The names of its Scenes.
            state: The run's state.
        """
        self.project_element = project_element
        self.new_name = new_name
        self.chosen = chosen
        self.task_ids = task_ids
        self.profile_ids = profile_ids
        self.scene_names = scene_names
        self.state = state
        self.reserved: set[str] = set()
        self.new_task_ids: dict[str, str] = {}
        self.new_profile_ids: dict[str, str] = {}

    def run(self) -> list[str]:
        """Make the copy, and return the errors (none, as nothing here can fail part-way)."""
        self._copy_tasks()
        self._copy_profiles()
        self._copy_scenes()
        self._repoint_copies()
        self._register_project()
        return []

    def _next_id(self) -> str:
        """An id no Task or Profile has, and none this copy has taken either."""
        new_id = str(taskedit.next_unique_task_or_profile_id(self.reserved, state=self.state))
        self.reserved.add(new_id)
        return new_id

    def _copy_tasks(self) -> None:
        """Tasks first: the Profiles copied next point at them by id, and the Project's own
        <tids> is the list those ids go into.
        """
        for task_id in self.task_ids:
            source = object_table("all_tasks", state=self.state).get(task_id)
            if source is None:
                continue
            new_id = self._next_id()
            self.new_task_ids[task_id] = new_id
            taskedit_save.register_new_task(
                taskedit_model.EditableTask(
                    task_id=new_id,
                    task_element=_copy_task_element(source["xml"], new_id, self.chosen.task_names[task_id]),
                ),
                self.chosen.task_names[task_id],
                state=self.state,
            )

    def _copy_profiles(self) -> None:
        """Copy each Profile, pointing its Entry and Exit Task links at the copies of those Tasks."""
        for profile_id in self.profile_ids:
            source = object_table("all_profiles", state=self.state).get(profile_id)
            if source is None:
                continue
            new_id = self._next_id()
            self.new_profile_ids[profile_id] = new_id
            element = _copy_profile_element(source["xml"], new_id, self.chosen.profile_names[profile_id])
            for child in element:
                if child.tag in ("mid0", "mid1"):
                    current = (child.text or "").strip()
                    child.text = self.new_task_ids.get(current, current)
            profedit.register_new_profile(
                profedit.EditableProfile(
                    profile_id=new_id,
                    profile_element=element,
                    entry_task_id=element.findtext("mid0", "") or "",
                    exit_task_id=element.findtext("mid1", "") or "",
                ),
                self.chosen.profile_names[profile_id],
                state=self.state,
            )

    def _copy_scenes(self) -> None:
        """Copy each Scene under the name chosen for it."""
        for scene_name in self.scene_names:
            source = object_table("all_scenes", state=self.state).get(scene_name)
            if source is None:
                continue
            copied = self.chosen.scene_names[scene_name]
            object_table("all_scenes", state=self.state)[copied] = {
                "xml": _copy_scene_element(source["xml"], copied),
                "name": copied,
            }

    def _repoint_copies(self) -> None:
        """Every by-name reference inside everything just copied, repointed at the copies --
        after all of them exist, so a Task calling a Task copied later is still caught.
        """
        state = self.state
        name_map = {
            object_table("all_tasks", state=state).get(old, {}).get("name", "") or old: self.chosen.task_names[old]
            for old in self.new_task_ids
        }
        for new_id in self.new_task_ids.values():
            _repoint_names(object_table("all_tasks", state=state)[new_id]["xml"], name_map, self.chosen.scene_names)
        for scene_name in self.scene_names:
            copied = self.chosen.scene_names.get(scene_name)
            if copied in object_table("all_scenes", state=state):
                _repoint_names(
                    object_table("all_scenes", state=state)[copied]["xml"], name_map, self.chosen.scene_names
                )

    def _register_project(self) -> None:
        """Register the Project that lists the copies, with an id of its own."""
        chosen = self.chosen
        element = copy.deepcopy(self.project_element)
        element.set("sr", _next_project_sr(state=self.state))
        _set_child_text(element, "id", str(uuid.uuid4()))
        _set_child_text(element, "name", self.new_name)
        projedit.register_new_project(
            projedit.EditableProject(project_name=self.new_name, project_element=element), state=self.state
        )
        # Written through set_project_members rather than by hand, so a Project that had no
        # <scenes> of its own gets one in Tasker's child order, and the <mdate> is stamped.
        for tag, ids in (
            ("tids", [self.new_task_ids[old] for old in self.task_ids if old in self.new_task_ids]),
            ("pids", [self.new_profile_ids[old] for old in self.profile_ids if old in self.new_profile_ids]),
            ("scenes", [chosen.scene_names[old] for old in self.scene_names if old in chosen.scene_names]),
        ):
            projedit.set_project_members(element, tag, ids)


def _duplicate_project_steps(
    new_name: str,
    chosen: _ProjectCopy,
    task_ids: list[str],
    profile_ids: list[str],
    scene_names: list[str],
    where: Target,
    state: RunState,
) -> list[Step]:
    """What a Project duplication will do.  Counts, then the renamings, which are the surprise."""
    steps = [Step(f"Create Project '{new_name}'", where)]
    for label, count in (
        ("Profile", len(profile_ids)),
        ("Task", len(task_ids)),
        ("Scene", len(scene_names)),
    ):
        if count:
            steps.append(Step(f"Copy its {count} {label}{'' if count == 1 else 's'}, each under a new name"))

    renamed = [
        (original, copied)
        for original, copied in (
            *(
                (object_table("all_tasks", state=state).get(old, {}).get("name", "") or old, new)
                for old, new in chosen.task_names.items()
            ),
            *(
                (object_table("all_profiles", state=state).get(old, {}).get("name", "") or old, new)
                for old, new in chosen.profile_names.items()
            ),
            *chosen.scene_names.items(),
        )
        if original != copied
    ]
    steps.extend(Step(f"    '{original}' becomes '{copied}'") for original, copied in renamed[:12])
    if len(renamed) > 12:
        steps.append(Step(f"    ...and {len(renamed) - 12} more"))

    steps.append(
        Step("Point the copies' Perform Task and Show/Hide Scene actions at the copies rather than the originals"),
    )
    return steps


def _duplicate_project_warnings(
    project_name: str, chosen: _ProjectCopy, task_ids: list[str], state: RunState
) -> list[str]:
    """What a duplicated Project shares with its original whether the user wants it to or not."""
    warnings = [
        (
            "Global variables are not copied and cannot be: Tasker keeps one set of them for the whole "
            "configuration, so the copy reads and writes exactly the same %Globals the original does.  Two "
            "Projects both setting %Mode will overwrite each other."
        ),
    ]

    shared_tasks = [task_id for task_id in task_ids if len(projects_listing("tids", task_id, state=state)) > 1]
    if shared_tasks:
        named = ", ".join(
            f"'{object_table('all_tasks', state=state).get(task_id, {}).get('name', '') or task_id}'"
            for task_id in shared_tasks[:5]
        )
        warnings.append(
            f"{named} {'is' if len(shared_tasks) == 1 else 'are'} listed by other Projects as well as "
            f"'{project_name}'.  A copy is made for the new Project regardless, so those Projects keep the "
            f"original and are not affected.",
        )

    warnings.append(
        "References this cannot see are not repointed: a home screen widget, a Tasker shortcut, or a Task "
        "name built out of a variable at run time still names the original.  Only Perform Task's Name and "
        "the Create/Show/Hide/Destroy Scene actions' own are rewritten.",
    )

    if any(name.endswith(")") for name in chosen.task_names.values()):
        warnings.append(
            "The copied Tasks are renamed because Perform Task resolves a call by name across the whole "
            "file, and two Tasks sharing a name make every call to either of them ambiguous.  Rename them "
            "afterwards if the suffix is not what you want -- Edit Task's Rename repoints the calls with it.",
        )
    return warnings
