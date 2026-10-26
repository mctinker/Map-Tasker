"""maprefac_move: a Task or a Profile changes which Project owns it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from maptasker.src.core.mapjump import PROFILE, PROJECT, TASK, Target
from maptasker.src.edit import projedit
from maptasker.src.mapops.maprefac_model import (
    MOVE,
    Block,
    Plan,
    Step,
    blocked,
    members,
    object_table,
    perform_task_callers,
    profile_target,
    profile_task_ids,
    projects_listing,
    task_target,
)

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# ##################################################################################
# Move: a Task or a Profile changes which Project owns it.
#
# The smallest of the four, and the one whose smallness is the surprise.  A Task is not
# INSIDE a Project in the file -- every Task is a top-level element, and a Project owns
# one by naming its id in <tids>.  So moving a Task between Projects moves no XML at
# all; it edits two lists.  profedit.add_task_to_project and taskedit_save.delete_task are
# the two halves of that already, from the add and the delete side.
#
# What makes it worth a preview anyway is what a Project's membership decides: it is
# what the Map, the Diagram, the Tree and every pulldown walk (elemvals.get_ids), and it
# is what a single-Project export writes.  A Task quietly filed under the wrong Project
# is a Task the user cannot find and an export that does not carry it.
# ##################################################################################


def _relocate(tag: str, member: str, to_project: str, from_projects: list[str], state: RunState) -> None:
    """Take a member out of every Project listing it and put it in one.

    Every Project, not the first: see projects_listing on why two of them can hold the
    same id, and taskedit_save.delete_task, which scans them all for the same reason.
    """
    projects = object_table("all_projects", state=state)
    for project_name in from_projects:
        entry = projects.get(project_name)
        if entry is None or project_name == to_project:
            continue
        projedit.set_project_members(
            entry["xml"],
            tag,
            [existing for existing in members(entry["xml"], tag) if existing != member],
        )

    entry = projects.get(to_project)
    if entry is not None:
        existing = members(entry["xml"], tag)
        if member not in existing:
            projedit.set_project_members(entry["xml"], tag, [*existing, member])


def _namesake_in(table: str, tag: str, member: str, name: str, project: str, state: RunState) -> str:
    """The id of ANOTHER object in `project` that has this name, or "" for none.

    The "does it already exist there?" half of a move that projects_listing cannot answer:
    that one asks whether this very id is listed, and a second Task or Profile of the same
    name under a different id is just as much a collision.  Perform Task and every pulldown
    find a Task by name, so two of them in one Project make the move silently change which
    one a call reaches.  An unnamed object has no name to collide on, so it never matches.
    """
    if not name:
        return ""
    entry = object_table("all_projects", state=state).get(project)
    if entry is None:
        return ""
    objects = object_table(table, state=state)
    for other_id in members(entry["xml"], tag):
        if other_id != member and objects.get(other_id, {}).get("name", "") == name:
            return other_id
    return ""


def plan_move(kind: str, key: str, to_project: str, state: RunState) -> Plan:
    """Move a Task (kind=TASK, key=its id) or a Profile (kind=PROFILE, key=its id) to a Project.

    A Profile takes its Entry and Exit Tasks with it, EXCEPT any that another Profile left
    behind still runs.  That exception is not an edge case: a Task shared between two
    Profiles of one Project is ordinary, and moving it would take it out from under the
    Profile that stayed -- turning one deliberate move into a second, invisible one.  The
    Tasks that do not travel are named in a warning rather than passed over in silence.
    """
    if to_project not in object_table("all_projects", state=state):
        return blocked(
            MOVE,
            "Move to another Project",
            Block("NO-PROJECT", f"'{to_project}' is not a Project in this file."),
        )

    if kind == TASK:
        return _plan_move_task(key, to_project, state=state)
    if kind == PROFILE:
        return _plan_move_profile(key, to_project, state=state)
    return blocked(
        MOVE,
        "Move to another Project",
        Block("NOT-MOVABLE", f"A {kind} cannot be moved between Projects."),
    )


def _plan_move_task(task_id: str, to_project: str, state: RunState) -> Plan:
    """Move one Task's Project membership."""
    entry = object_table("all_tasks", state=state).get(task_id)
    if entry is None:
        return blocked(MOVE, "Move a Task to another Project", Block("NO-TASK", "That Task is not in this file."))

    task_name = entry.get("name", "") or task_id
    where = task_target(task_id, state=state)
    owners = projects_listing("tids", task_id, state=state)
    what = f"Move Task '{task_name}' to Project '{to_project}'"

    if owners == [to_project]:
        return blocked(
            MOVE,
            what,
            Block(
                "ALREADY-THERE",
                f"Task '{task_name}' already belongs to Project '{to_project}' and to no other, so there "
                f"is nothing to move.",
                where,
            ),
        )

    namesake = _namesake_in("all_tasks", "tids", task_id, entry.get("name", ""), to_project, state=state)
    if namesake:
        return blocked(
            MOVE,
            what,
            Block(
                "NAME-TAKEN",
                f"Project '{to_project}' already has a different Task named '{task_name}'.  Perform Task calls "
                f"a Task by name, so two of them in one Project would leave every call to either ambiguous.  "
                f"Rename one of them first.",
                task_target(namesake, state=state),
            ),
        )

    plan = Plan(kind=MOVE, what=what, elements=(entry["xml"],))
    plan.steps = [
        *(
            Step(f"Remove Task '{task_name}' from Project '{owner}'", Target(kind=PROJECT, key=owner))
            for owner in owners
            if owner != to_project
        ),
        *(
            []
            if to_project in owners
            else [Step(f"Add Task '{task_name}' to Project '{to_project}'", Target(kind=PROJECT, key=to_project))]
        ),
    ]
    plan.warnings = _move_task_warnings(task_id, task_name, owners, to_project, state=state)
    if to_project in owners:
        plan.warnings.insert(
            0,
            f"Task '{task_name}' is already listed by Project '{to_project}', so this only removes it from "
            f"the other Project{'s' if len(owners) > 2 else ''} that list{'' if len(owners) > 2 else 's'} it.",
        )

    def run() -> list[str]:
        _relocate("tids", task_id, to_project, owners, state=state)
        return []

    plan.run = run
    return plan


def _move_task_warnings(task_id: str, task_name: str, owners: list[str], to_project: str, state: RunState) -> list[str]:
    """What a Task's move leaves behind that the user should know about."""
    warnings = []
    if not owners:
        warnings.append(
            f"Task '{task_name}' is not currently listed by any Project, so this files it under one for the "
            f"first time rather than moving it.",
        )

    stranded = []
    for profile_id, profile in object_table("all_profiles", state=state).items():
        if task_id not in profile_task_ids(profile["xml"]):
            continue
        profile_projects = projects_listing("pids", profile_id, state=state)
        if to_project not in profile_projects:
            stranded.append(f"'{profile.get('name', '') or profile_id}'")
    if stranded:
        warnings.append(
            f"{', '.join(stranded[:6])} {'runs' if len(stranded) == 1 else 'run'} this Task and "
            f"{'is' if len(stranded) == 1 else 'are'} not in Project '{to_project}'.  Tasker allows that and "
            f"real backups contain it, so nothing breaks -- but the Task will no longer appear beside the "
            f"Profile that runs it, and a single-Project export of that Profile's Project will not carry it.",
        )

    callers = perform_task_callers(task_name, state=state)
    outside = [target for target in callers if target.project and target.project != to_project]
    if outside:
        warnings.append(
            f"{len(outside)} Perform Task {'call' if len(outside) == 1 else 'calls'} to '{task_name}' "
            f"{'is' if len(outside) == 1 else 'are'} in other Projects.  Perform Task calls by name and does "
            f"not care which Project a Task is in, so those keep working.",
        )
    return warnings


def _move_name_collisions(
    profile_id: str, entry: dict[str, Any], travelling: list[str], to_project: str, state: RunState
) -> list[Block]:
    """What stops the move: a Profile or a travelling Task that would arrive under a name the Project has.

    Nothing may arrive in the Project under a name something there already has: not the Profile, and not
    any Task that travels with it.  A Task already listed by the target is not arriving, so it is not a
    collision with itself.
    """
    profile_name = entry.get("name", "") or profile_id
    tasks = object_table("all_tasks", state=state)
    blocks: list[Block] = []
    profile_namesake = _namesake_in("all_profiles", "pids", profile_id, entry.get("name", ""), to_project, state=state)
    if profile_namesake:
        blocks.append(
            Block(
                "NAME-TAKEN",
                f"Project '{to_project}' already has a different Profile named '{profile_name}'.  Rename one "
                f"of them first.",
                profile_target(profile_namesake, state=state),
            ),
        )
    for task_id in travelling:
        task_name = tasks.get(task_id, {}).get("name", "")
        task_namesake = _namesake_in("all_tasks", "tids", task_id, task_name, to_project, state=state)
        if task_namesake:
            blocks.append(
                Block(
                    "NAME-TAKEN",
                    f"Profile '{profile_name}' runs Task '{task_name}', which would move with it, and Project "
                    f"'{to_project}' already has a different Task of that name.  Perform Task calls a Task by "
                    f"name, so two of them in one Project would leave every call to either ambiguous.  Rename "
                    f"one of them first.",
                    task_target(task_namesake, state=state),
                ),
            )
    return blocks


def _move_steps(
    profile_name: str, owners: list[str], to_project: str, travelling: list[str], state: RunState
) -> list[Step]:
    """What moving the Profile does, in the order it is told to the user."""
    return [
        *(
            Step(f"Remove Profile '{profile_name}' from Project '{owner}'", Target(kind=PROJECT, key=owner))
            for owner in owners
            if owner != to_project
        ),
        *(
            []
            if to_project in owners
            else [
                Step(f"Add Profile '{profile_name}' to Project '{to_project}'", Target(kind=PROJECT, key=to_project)),
            ]
        ),
        *(
            Step(
                f"Move its Task '{object_table('all_tasks', state=state).get(task_id, {}).get('name', '') or task_id}' "
                f"to Project '{to_project}' as well",
                task_target(task_id, state=state),
            )
            for task_id in travelling
        ),
    ]


def _plan_move_profile(profile_id: str, to_project: str, state: RunState) -> Plan:
    """Move one Profile's Project membership, and its Tasks' with it where that is safe."""
    entry = object_table("all_profiles", state=state).get(profile_id)
    if entry is None:
        return blocked(
            MOVE,
            "Move a Profile to another Project",
            Block("NO-PROFILE", "That Profile is not in this file."),
        )

    profile_element = entry["xml"]
    profile_name = entry.get("name", "") or profile_id
    where = profile_target(profile_id, state=state)
    owners = projects_listing("pids", profile_id, state=state)
    what = f"Move Profile '{profile_name}' to Project '{to_project}'"

    if owners == [to_project]:
        return blocked(
            MOVE,
            what,
            Block(
                "ALREADY-THERE",
                f"Profile '{profile_name}' already belongs to Project '{to_project}' and to no other, so there "
                f"is nothing to move.",
                where,
            ),
        )

    # A Task travels with its Profile unless a Profile that is staying behind also runs it.
    task_ids = profile_task_ids(profile_element)
    staying = {
        other_id: other
        for other_id, other in object_table("all_profiles", state=state).items()
        if other_id != profile_id and set(projects_listing("pids", other_id, state=state)) & set(owners)
    }
    shared = {
        task_id: sorted(
            other.get("name", "") or other_id
            for other_id, other in staying.items()
            if task_id in profile_task_ids(other["xml"])
        )
        for task_id in task_ids
    }
    travelling = [task_id for task_id in task_ids if not shared[task_id]]

    if blocks := _move_name_collisions(profile_id, entry, travelling, to_project, state=state):
        return blocked(MOVE, what, *blocks)

    plan = Plan(kind=MOVE, what=what, elements=(profile_element,))
    plan.steps = _move_steps(profile_name, owners, to_project, travelling, state=state)
    plan.warnings = _move_profile_warnings(shared, to_project, state=state)

    def run() -> list[str]:
        _relocate("pids", profile_id, to_project, owners, state=state)
        for task_id in travelling:
            _relocate("tids", task_id, to_project, projects_listing("tids", task_id, state=state), state=state)
        return []

    plan.run = run
    return plan


def _move_profile_warnings(shared: dict[str, list[str]], to_project: str, state: RunState) -> list[str]:
    """Which of a moving Profile's Tasks are staying, and why."""
    left = {task_id: users for task_id, users in shared.items() if users}
    if not left:
        return []

    tasks = object_table("all_tasks", state=state)
    described = [
        f"'{tasks.get(task_id, {}).get('name', '') or task_id}' (also run by {', '.join(users[:3])})"
        for task_id, users in left.items()
    ]
    return [
        (
            f"{len(left)} of this Profile's {'Task stays' if len(left) == 1 else 'Tasks stay'} where "
            f"{'it is' if len(left) == 1 else 'they are'}: {'; '.join(described)}.  Moving "
            f"{'it' if len(left) == 1 else 'them'} to '{to_project}' would take "
            f"{'it' if len(left) == 1 else 'them'} out from under a Profile that is not moving."
        ),
    ]
