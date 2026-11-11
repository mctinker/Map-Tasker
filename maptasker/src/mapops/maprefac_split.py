"""maprefac_split: choose some Tasks and Profiles and move them, with what they need, into a Project of their own."""

#! /usr/bin/env python3

#                                                                                        #
# maprefac_split: Split Project.                                                         #
#                                                                                        #
# Project Dependencies says what is safe to split out of a Project.  This does the       #
# splitting: pick some Tasks and Profiles, and they -- with everything they need -- are  #
# moved into a Project of their own, and what is left joining the two is reported.       #
#                                                                                        #
# IT IS TWO THINGS THAT ALREADY EXISTED, JOINED                                          #
#                                                                                        #
#   WHAT TO MOVE  is Import With Dependencies' walk (mapcarry), run on the loaded file   #
#                 rather than on another one: the Tasks a Task performs, the Scenes it   #
#                 shows and the Tasks those run, and for a Profile its Entry and Exit    #
#                 Tasks.  "What does this need" has one answer in this program, so      #
#                 Project Dependencies, Import and this all ask the same question.      #
#   HOW TO MOVE   is Move's (maprefac_move): a Task, a Profile or a Scene is not inside  #
#                 a Project in the file, a Project owns it by naming it in <tids>,       #
#                 <pids> or <scenes>.  So nothing is copied and nothing gets a new id:   #
#                 the objects are the same ones, with another Project listing them.      #
#                                                                                        #
# WHAT IS DIFFERENT FROM A MOVE                                                          #
#                                                                                        #
# Move leaves behind a Task that a Profile which is staying still runs, because taking   #
# it would pull it out from under that Profile.  A split cannot make that choice for the #
# user: a Task the chosen Profile runs IS part of what the chosen Profile needs, and the #
# point is a Project that works on its own.  So everything needed moves, and the join    #
# that leaves -- the Profile that stayed behind, running a Task that is now in the new   #
# Project -- is reported rather than prevented.  Perform Task calls by name and does not  #
# care which Project a Task is in, so nothing stops working; the report is what the user #
# needs to know before the new Project is exported, shared or deleted.                   #
#                                                                                        #
# THE REPORT IS PROJECT DEPENDENCIES' OWN, READ AS IT WILL BE AFTERWARDS                  #
#                                                                                        #
# Each of those joins is a use that Project Dependencies would show between the new      #
# Project and another.  Rather than work them out a second time -- and risk saying one   #
# thing here and another there -- the graph is built over a copy of the Projects as they  #
# will be once the split is done, and every line of it that touches the new Project is   #
# the report.  Project Dependencies, opened after Apply, shows the same lines.           #
#                                                                                        #
# NOTHING IS APPLIED UNSEEN, and it is one Undo, as every refactor is: the plan is        #
# maprefac_model's, applied by maprefac.apply.                                           #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element

from maptasker.src.analysis.xmldiff import Configuration
from maptasker.src.core.editcommon import name_problem
from maptasker.src.core.mapjump import PROFILE, PROJECT, SCENE, TASK, VARIABLE, Target
from maptasker.src.edit import projedit
from maptasker.src.mapops import mapcarry, maprefac, projdeps
from maptasker.src.mapops.maprefac_model import (
    SPLIT,
    Block,
    Plan,
    Step,
    blocked,
    members,
    object_table,
    profile_target,
    projects_listing,
    task_target,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from maptasker.src.core.primitem import RunState

# How many of the lines that still cross the boundary the preview prints.  A split that leaves hundreds
# is not one to go ahead with, and the preview says how many there are rather than listing them all.
_CROSSINGS_SHOWN = 150


# ##################################################################################
# What can be chosen.
# ##################################################################################
def pick_choices(state: RunState) -> list[tuple[str, str]]:
    """Every Task and Profile as (key, label), Profiles first, each by Project and name.

    The key is 'task:12' or 'profile:5', so one list can hold both and still say which is which.  The label
    names the Project, since two Tasks called 'Setup' in different Projects is ordinary.
    """
    profiles = [(f"{PROFILE}:{key}", f"Profile: {label}") for key, label in maprefac.profile_choices(state=state)]
    tasks = [(f"{TASK}:{key}", f"Task: {label}") for key, label in maprefac.task_choices(state=state)]
    return profiles + tasks


def split_pick(key: str) -> tuple[str, str]:
    """('task', '12') from 'task:12'.  A key that is not one gives ('', '')."""
    kind, _, identifier = key.partition(":")
    return (kind, identifier) if kind in {TASK, PROFILE} and identifier else ("", "")


# ##################################################################################
# The Projects as they will be.
# ##################################################################################
def _after_the_split(
    state: RunState, project: str, tasks: Sequence[str], profiles: Sequence[str], scenes: Sequence[str]
) -> RunState:
    """A copy of the state whose Projects are as they will be once these have moved into the new one.

    Only the Projects are copied, and only as far as their lists of members: the Tasks, Profiles and Scenes are
    the live ones, since they are the same objects afterwards.  Nothing is written to the live configuration.
    """
    moved = {"tids": set(tasks), "pids": set(profiles), "scenes": set(scenes)}
    projects: dict[str, dict[str, Any]] = {}
    for name, entry in object_table("all_projects", state=state).items():
        element = copy.deepcopy(entry["xml"])
        for tag, going in moved.items():
            kept = [member for member in members(element, tag) if member not in going]
            if kept != members(element, tag):
                projedit.set_project_members(element, tag, kept)
        projects[name] = {**entry, "xml": element}

    new_element = Element("Project")
    for tag, text in (
        ("name", project),
        ("tids", ",".join(tasks)),
        ("pids", ",".join(profiles)),
        ("scenes", ",".join(scenes)),
    ):
        child = Element(tag)
        child.text = text
        new_element.append(child)
    projects[project] = {"xml": new_element, "name": project}

    after = copy.copy(state)
    after.tasker_root_elements = {**state.tasker_root_elements, "all_projects": projects}
    return after


def _kind_word(kind: str) -> str:
    """'Task', 'Scene' or 'global variable', for a line about a use."""
    return {TASK: "Task", SCENE: "Scene", VARIABLE: "global variable"}.get(kind, kind)


def _crossing_line(link: projdeps.Link, project: str) -> str:
    """One use that joins the new Project to another, in words, saying which side is which."""
    thing = link.used if link.kind == VARIABLE else f"{_kind_word(link.kind)} '{link.used}'"
    if link.user_project == project:
        where = (
            f"which is set only in Project '{link.provider}'"
            if link.kind == VARIABLE
            else f"which stays in Project '{link.provider}'"
        )
    else:
        where = (
            "which is set only in the new Project" if link.kind == VARIABLE else "which has moved to the new Project"
        )
    return f"{link.user.label} {link.verb} {thing}, {where}"


def crossings_after(
    state: RunState, project: str, tasks: Sequence[str], profiles: Sequence[str], scenes: Sequence[str]
) -> tuple[list[Step], list[str]]:
    """What still joins the new Project to the rest, as clickable lines, and the Projects it is in a loop with.

    The lines about what the rest takes from the new Project come first -- those are what somebody who stayed
    behind will meet, and the ones that stop the new Project being used without them are the second half.
    """
    after = _after_the_split(state, project, tasks, profiles, scenes)
    graph = projdeps.build_graph(after)

    into_new = [link for edge in graph.used_by(project) for link in edge.links]
    out_of_new = [link for edge in graph.uses(project) for link in edge.links]
    steps = [Step(_crossing_line(link, project), link.user) for link in (*into_new, *out_of_new)]
    loop = [other for other in graph.loop_of(project) if other != project]
    return steps, loop


# ##################################################################################
# Planning it.
# ##################################################################################
def _names(table: str, keys: Sequence[str], state: RunState) -> dict[str, str]:
    """{id: name} for these members of a table, falling back to the id for one that has no name."""
    objects = object_table(table, state=state)
    return {key: objects.get(key, {}).get("name", "") or key for key in keys}


def _owners_text(owners: list[str]) -> str:
    """'Project 'Home'', 'Projects 'A' and 'B'', or 'no Project'."""
    if not owners:
        return "no Project"
    quoted = " and ".join(f"'{owner}'" for owner in owners[:4])
    return f"Project{'s' if len(owners) > 1 else ''} {quoted}"


def _steps(project: str, needs: mapcarry.Needs, state: RunState) -> list[Step]:
    """What will happen, one line each: the Project, then Profiles, Tasks and Scenes, each with why it comes."""
    steps = [Step(f"Create Project '{project}'")]
    names = {
        "pids": _names("all_profiles", list(needs.profiles), state),
        "tids": _names("all_tasks", list(needs.tasks), state),
    }
    for profile_id, why in needs.profiles.items():
        owners = projects_listing("pids", profile_id, state=state)
        steps.append(
            Step(
                f"Move Profile '{names['pids'][profile_id]}' out of {_owners_text(owners)} -- {why}",
                profile_target(profile_id, state=state),
            ),
        )
    for task_id, why in needs.tasks.items():
        owners = projects_listing("tids", task_id, state=state)
        steps.append(
            Step(
                f"Move Task '{names['tids'][task_id]}' out of {_owners_text(owners)} -- {why}",
                task_target(task_id, state=state),
            ),
        )
    for scene_name, why in needs.scenes.items():
        owners = projects_listing("scenes", scene_name, state=state)
        steps.append(
            Step(
                f"Move Scene '{scene_name}' out of {_owners_text(owners)} -- {why}",
                Target(kind=SCENE, key=scene_name, name=scene_name),
            ),
        )
    return steps


def _warnings(project: str, needs: mapcarry.Needs, loop: list[str], state: RunState) -> list[str]:
    """What the preview has to say before Apply: what could not be followed, and what is left behind."""
    warnings = [f"{line}  It stays as it is -- it will not run." for line in needs.unresolved]

    unfiled = [
        *(
            f"Task '{name}'"
            for key, name in _names("all_tasks", list(needs.tasks), state).items()
            if not projects_listing("tids", key, state=state)
        ),
        *(
            f"Profile '{name}'"
            for key, name in _names("all_profiles", list(needs.profiles), state).items()
            if not projects_listing("pids", key, state=state)
        ),
        *(f"Scene '{name}'" for name in needs.scenes if not projects_listing("scenes", name, state=state)),
    ]
    if unfiled:
        warnings.append(
            f"{', '.join(unfiled[:6])}{' and more' if len(unfiled) > 6 else ''} "
            f"{'is' if len(unfiled) == 1 else 'are'} not listed by any Project, so {'it is' if len(unfiled) == 1 else 'they are'} "
            f"filed under '{project}' for the first time rather than moved.",
        )

    emptied = _emptied_projects(project, needs, state)
    if emptied:
        warnings.append(
            f"{', '.join(f'Project {name!r}' for name in emptied[:4])} will be left with nothing in "
            f"{'it' if len(emptied) == 1 else 'them'}.  Tasker keeps an empty Project; delete it yourself if you do not want it.",
        )

    shared_names = _names_left_behind(needs, state)
    if shared_names:
        warnings.append(
            f"Another Task is called {', '.join(repr(name) for name in shared_names[:6])}, and stays behind.  "
            f"Perform Task calls by name across the whole file, so a call to {'it' if len(shared_names) == 1 else 'any of them'} "
            f"reaches whichever one Tasker finds first, in either Project.",
        )

    if loop:
        warnings.append(
            f"The new Project and {', '.join(repr(name) for name in loop)} use each other, so neither can be "
            f"exported, shared or deleted without the other.  The lines below say where.",
        )

    if needs.layouts:
        warnings.append(
            "Version 2 Scene "
            + ", ".join(f"'{name}'" for name in needs.layouts)
            + ": the Tasks and Scenes its layout names are inside its own data and are not followed, so any that "
            "are not chosen stay where they are.",
        )
    return warnings


def _emptied_projects(project: str, needs: mapcarry.Needs, state: RunState) -> list[str]:
    """The Projects that every member of is moving, so would be left empty."""
    moving = {"tids": set(needs.tasks), "pids": set(needs.profiles), "scenes": set(needs.scenes)}
    emptied: list[str] = []
    for name, entry in object_table("all_projects", state=state).items():
        if name == project:
            continue
        held = {tag: set(members(entry["xml"], tag)) for tag in moving}
        if any(held.values()) and all(held[tag] <= moving[tag] for tag in moving):
            emptied.append(name)
    return emptied


def _names_left_behind(needs: mapcarry.Needs, state: RunState) -> list[str]:
    """The names a moving Task shares with a Task that is not moving."""
    tasks = object_table("all_tasks", state=state)
    moving_names = {tasks[key].get("name", "") for key in needs.tasks if key in tasks} - {""}
    return sorted(
        {entry.get("name", "") for key, entry in tasks.items() if key not in needs.tasks} & moving_names,
        key=str.lower,
    )


def _check(picks: Sequence[tuple[str, str]], project: str, state: RunState) -> list[Block]:
    """What stops the split before anything is worked out: nothing chosen, a name that cannot be used, a missing object."""
    blocks: list[Block] = []
    if not picks:
        blocks.append(Block("NOTHING-CHOSEN", "Choose at least one Task or Profile to split out."))
    if not project:
        blocks.append(Block("NO-NAME", "Give the new Project a name."))
    elif problem := name_problem(project, "Project"):
        blocks.append(Block("BAD-NAME", problem))
    elif project in object_table("all_projects", state=state):
        blocks.append(
            Block(
                "NAME-TAKEN",
                f"There is already a Project called '{project}'.  Splitting into it would be a move, not a split: "
                f"use Move to a Project, or give the new Project another name.",
                Target(kind=PROJECT, key=project, name=project),
            ),
        )

    tasks, profiles = object_table("all_tasks", state=state), object_table("all_profiles", state=state)
    for kind, key in picks:
        if kind == TASK and key not in tasks:
            blocks.append(Block("NO-TASK", f"Task id {key} is not in this file any more."))
        elif kind == PROFILE and key not in profiles:
            blocks.append(Block("NO-PROFILE", f"Profile id {key} is not in this file any more."))
    return blocks


def plan_split(picks: Sequence[tuple[str, str]], new_project: str, state: RunState) -> Plan:
    """Plan moving these Tasks and Profiles, and what they need, into a new Project called `new_project`.

    `picks` is (kind, id) pairs, TASK or PROFILE.  The plan carries the Project that will be created, what moves
    into it and why, what could not be followed, and -- as `crossings` -- every use that still joins the new
    Project to the rest, so the user chooses knowing what they are leaving connected.
    """
    project = new_project.strip()
    chosen = list(dict.fromkeys(picks))
    what = f"Split into new Project '{project}'" if project else "Split into a new Project"

    if blocks := _check(chosen, project, state=state):
        return blocked(SPLIT, what, *blocks)

    # This very file, read as the walk reads another one.  The path is what its sentences call the file.
    source = Configuration(path="this file", tables=state.tasker_root_elements, root=state.xml_root)
    needs = mapcarry.needs_of_many(source, chosen, project)

    tasks, profiles, scenes = list(needs.tasks), list(needs.profiles), list(needs.scenes)
    crossings, loop = crossings_after(state, project, tasks, profiles, scenes)

    plan = Plan(kind=SPLIT, what=what)
    plan.steps = _steps(project, needs, state)
    plan.warnings = _warnings(project, needs, loop, state)
    plan.crossings = crossings[:_CROSSINGS_SHOWN]
    if len(crossings) > _CROSSINGS_SHOWN:
        plan.crossings.append(
            Step(f"...and {len(crossings) - _CROSSINGS_SHOWN} more, which Project Dependencies lists.")
        )

    live = [
        *(object_table("all_tasks", state=state)[key]["xml"] for key in tasks),
        *(object_table("all_profiles", state=state)[key]["xml"] for key in profiles),
        *(object_table("all_scenes", state=state)[key]["xml"] for key in scenes),
    ]
    owners = {
        owner
        for tag, keys in (("tids", tasks), ("pids", profiles), ("scenes", scenes))
        for key in keys
        for owner in projects_listing(tag, key, state=state)
    }
    projects = object_table("all_projects", state=state)
    plan.elements = (*live, *(projects[owner]["xml"] for owner in sorted(owners)))
    plan.run = lambda: _split(project, tasks, profiles, scenes, state=state)
    return plan


# ##################################################################################
# Doing it.
# ##################################################################################
def _split(
    project: str, tasks: Sequence[str], profiles: Sequence[str], scenes: Sequence[str], state: RunState
) -> list[str]:
    """Create the Project and list everything in it -- and take it out of every Project that listed it.

    Out of every Project, not the first: see projects_listing on why two can list the same Task.  Each Project
    is written once, with its new list of members, rather than once per member.
    """
    created = projedit.create_new_project(project, state=state)
    if isinstance(created, str):
        return [created]
    projedit.register_new_project(created, state=state)
    new_element = created.project_element

    projects = object_table("all_projects", state=state)
    for tag, moving in (("tids", tasks), ("pids", profiles), ("scenes", scenes)):
        going = set(moving)
        for name, entry in projects.items():
            if name == project:
                continue
            current = members(entry["xml"], tag)
            kept = [member for member in current if member not in going]
            if kept != current:
                projedit.set_project_members(entry["xml"], tag, kept)
        projedit.set_project_members(new_element, tag, list(moving))
    return []
