"""projdeps: which Projects use Tasks, Scenes and global variables that live in other Projects -- the dependency graph between Projects."""

#! /usr/bin/env python3

#                                                                                        #
# projdeps: the Project dependency graph.                                                #
#                                                                                        #
# A Project is where Tasker files things, not a wall around them.  A Task in 'Home' can     #
# perform a Task in 'Utilities', a Profile can run a Task that lives in another Project,    #
# a Scene button can run one too, and a global variable is one variable for the whole       #
# configuration whichever Project sets it.  None of that is visible from inside a Project,  #
# and all of it matters the day somebody wants to export one Project to a friend, split a   #
# big one in two, or delete one: the others quietly stop working.                           #
#                                                                                        #
# This reads the configuration once and draws the lines between Projects.  A LINE FROM A     #
# TO B means A uses something B provides, and it is made of the individual uses, each one    #
# kept so that a click can go and look at it.                                               #
#                                                                                        #
# WHAT COUNTS AS A USE, and it is Import With Dependencies' own list (mapcarry), read by     #
# the same functions, because "what does this need" has to have one answer:                  #
#                                                                                        #
#   Task      a Perform Task action (by name), and a Profile's Entry or Exit Task and the    #
#             Task a Scene element runs (by id).                                           #
#   Scene     the Show, Create, Hide, Destroy and Scene Element actions (by Scene name).    #
#   Variable  a global that a Project reads and does not set itself, which another Project  #
#             sets.  A global belongs to no Project, so the Project that SETS it is the one   #
#             that provides it.                                                            #
#                                                                                        #
# Not followed, and said so in the help: a name assembled at run time ('%which'), which can   #
# not be resolved from a file; what is inside a Version 2 Scene's layout; and a global that    #
# nothing sets (it has no Project to depend on).                                           #
#                                                                                        #
# A NAME TWO PROJECTS BOTH HAVE.  Two Tasks called 'Setup' in different Projects is ordinary. #
# A Perform Task of 'Setup' inside a Project that has its own 'Setup' is not a use of the     #
# other one -- it is the likeliest reading and it is the one that cannot hurt.  From a Project  #
# with none of its own it is a use of every Project that has one, and none of those is the sole  #
# provider: deleting one still leaves the name resolvable.                                  #
#                                                                                        #
# WHAT "SOLE" MEANS.  A use is the sole one when the provider is the only Project that has    #
# what it uses.  Those are the uses that would be left dangling if the provider were deleted    #
# with its contents, so they are what the "if you delete this" answer is made of.            #
#                                                                                        #
# Read-only: nothing here changes the configuration.                                       #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.analysis import healthck
from maptasker.src.core import clock
from maptasker.src.core.mapjump import PROJECT, SCENE, TASK, VARIABLE, Row, Target, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import PROJDEPS_FILE, logger
from maptasker.src.mapgen import varxref
from maptasker.src.mapops.mapcarry import scene_references, scene_task_ids
from maptasker.src.mapops.maprefac_model import (
    actions_of,
    members,
    object_table,
    profile_target,
    profile_task_ids,
    task_target,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# How a Project stands, for the table: it needs nothing from another Project, it needs some, or it needs
# some that need it back.
SELF_CONTAINED = "self-contained"
NEEDS_OTHERS = "needs-others"
IN_A_LOOP = "in-a-loop"


# ##################################################################################
# What is found.
# ##################################################################################


@dataclass(frozen=True)
class Link:
    """One use: something in `user_project` uses something that `provider` has."""

    kind: str  # TASK, SCENE or VARIABLE -- what is used
    user_project: str
    provider: str
    user: Target  # the place that uses it: a Task's action, a Scene, a Profile
    used: str  # its name: "Setup", "Panel", "%Alarm"
    verb: str  # "performs", "shows", "runs" or "reads"
    used_at: Target | None = None  # the thing used, in the provider, when there is one place to point at
    sole: bool = True  # whether the provider is the only Project that has it
    count: int = 1  # how many places in the user Project use it (a variable is one link, however often it is read)


@dataclass
class Edge:
    """Every use one Project makes of another."""

    user: str
    provider: str
    links: list[Link] = field(default_factory=list[Link])

    def count(self, kind: str) -> int:
        """How many different things of this kind the user Project takes from the provider."""
        return len({link.used for link in self.links if link.kind == kind})

    @property
    def summary(self) -> str:
        """'3 Tasks, 1 Scene, 2 variables', for a label."""
        parts: list[str] = []
        for kind, one, many in (
            (TASK, "Task", "Tasks"),
            (SCENE, "Scene", "Scenes"),
            (VARIABLE, "variable", "variables"),
        ):
            number = self.count(kind)
            if number:
                parts.append(f"{number} {one if number == 1 else many}")
        return ", ".join(parts)


@dataclass
class ProjectGraph:
    """The Projects and the uses between them."""

    projects: list[str] = field(default_factory=list[str])
    edges: dict[tuple[str, str], Edge] = field(default_factory=dict[tuple[str, str], Edge])
    # Groups of Projects that each need another in the group, however indirectly: the ones that cannot be
    # separated from one another by cutting one line.
    loops: list[list[str]] = field(default_factory=list[list[str]])

    def uses(self, project: str) -> list[Edge]:
        """The Projects this one takes from, the most used first."""
        found = [edge for (user, _), edge in self.edges.items() if user == project]
        return sorted(found, key=lambda edge: (-len(edge.links), edge.provider.lower()))

    def used_by(self, project: str) -> list[Edge]:
        """The Projects that take from this one, the most using first."""
        found = [edge for (_, provider), edge in self.edges.items() if provider == project]
        return sorted(found, key=lambda edge: (-len(edge.links), edge.user.lower()))

    def needs(self, project: str) -> list[str]:
        """Every Project this one needs, directly or through the ones it needs: what it takes to stand alone."""
        return self._reach(project, forward=True)

    def needed_by(self, project: str) -> list[str]:
        """Every Project that needs this one, directly or through others."""
        return self._reach(project, forward=False)

    def _reach(self, project: str, *, forward: bool) -> list[str]:
        """The Projects reached by following the lines from `project`, not counting itself."""
        step: dict[str, list[str]] = {}
        for user, provider in self.edges:
            near, far = (user, provider) if forward else (provider, user)
            step.setdefault(near, []).append(far)
        seen: set[str] = set()
        queue = [project]
        while queue:
            for nxt in step.get(queue.pop(), ()):
                if nxt not in seen and nxt != project:
                    seen.add(nxt)
                    queue.append(nxt)
        return sorted(seen, key=str.lower)

    def would_break(self, project: str) -> list[Link]:
        """The uses that would be left with nothing if this Project were deleted with its contents."""
        return [link for edge in self.used_by(project) for link in edge.links if link.sole]

    def loop_of(self, project: str) -> list[str]:
        """The Projects in the loop this one is in, itself included, or [] when it is in none."""
        for loop in self.loops:
            if project in loop:
                return loop
        return []

    def standing(self, project: str) -> str:
        """SELF_CONTAINED, NEEDS_OTHERS or IN_A_LOOP."""
        if self.loop_of(project):
            return IN_A_LOOP
        return NEEDS_OTHERS if self.uses(project) else SELF_CONTAINED


# ##################################################################################
# Reading the configuration.
# ##################################################################################


def _owners(tag: str, state: RunState) -> dict[str, list[str]]:
    """{member: every Project that lists it} for a Project's <pids>, <tids> or <scenes>."""
    owners: dict[str, list[str]] = {}
    for project_name, entry in object_table("all_projects", state=state).items():
        for member in members(entry["xml"], tag):
            owners.setdefault(member, []).append(project_name)
    return owners


class _Scan:
    """One pass over the configuration, collecting the uses that cross from one Project to another."""

    def __init__(self, state: RunState) -> None:
        self.state = state
        self.scene_args = healthck.scene_name_args()
        self.task_owners = _owners("tids", state)
        self.scene_owners = _owners("scenes", state)
        self.profile_owners = _owners("pids", state)
        self.tasks = object_table("all_tasks", state=state)
        # Which Projects have a Task of each name, and which Task it is there.
        self.holders: dict[str, dict[str, str]] = {}
        for task_id, entry in self.tasks.items():
            name = entry.get("name", "")
            for project in self.task_owners.get(task_id, ()):
                self.holders.setdefault(name, {}).setdefault(project, task_id)
        self.links: list[Link] = []

    def add(
        self,
        kind: str,
        user: Target,
        user_projects: list[str],
        used: str,
        verb: str,
        providers: dict[str, Target | None],
    ) -> None:
        """Record a use from each Project the user is in, unless that Project has what is used itself."""
        for user_project in user_projects:
            if user_project in providers:
                continue
            self.links.extend(
                Link(kind, user_project, provider, user, used, verb, used_at, sole=len(providers) == 1)
                for provider, used_at in providers.items()
            )

    def task_providers(self, task_ids: list[str]) -> dict[str, Target | None]:
        """{Project: the Task there} for a set of Task ids."""
        found: dict[str, Target | None] = {}
        for task_id in task_ids:
            for project in self.task_owners.get(task_id, ()):
                found.setdefault(project, task_target(task_id, state=self.state))
        return found

    def uses_in(self, element: Element, user: Target, user_projects: list[str]) -> None:
        """Every Perform Task and Scene action under this element, as uses."""
        for kind, name, _code in scene_references(element, self.scene_args):
            if kind == "task":
                providers = {
                    project: task_target(task_id, state=self.state)
                    for project, task_id in self.holders.get(name, {}).items()
                }
                self.add(TASK, user, user_projects, name, "performs", dict(providers))
            else:
                scene = Target(SCENE, name, name)
                self.add(
                    SCENE, user, user_projects, name, "shows", dict.fromkeys(self.scene_owners.get(name, ()), scene)
                )

    def tasks_and_scenes(self) -> None:
        """The Perform Task and Scene actions of every Task, and of every Scene's own inline Tasks."""
        for task_id, entry in self.tasks.items():
            projects = self.task_owners.get(task_id, [])
            if not projects:
                continue
            place = task_target(task_id, state=self.state)
            for number, action in enumerate(actions_of(entry["xml"]), start=1):
                self.uses_in(action, place.at_action(number), projects)
        for scene_name, entry in object_table("all_scenes", state=self.state).items():
            projects = self.scene_owners.get(scene_name, [])
            if not projects:
                continue
            place = Target(SCENE, scene_name, scene_name, projects[0])
            self.uses_in(entry["xml"], place, projects)
            for task_id in scene_task_ids(entry["xml"]):
                self.add(
                    TASK,
                    place,
                    projects,
                    self.tasks.get(task_id, {}).get("name", "") or task_id,
                    "runs",
                    self.task_providers([task_id]),
                )

    def profiles(self) -> None:
        """The Entry and Exit Task of every Profile."""
        for profile_id, entry in object_table("all_profiles", state=self.state).items():
            projects = self.profile_owners.get(profile_id, [])
            place = profile_target(profile_id, state=self.state)
            for task_id in profile_task_ids(entry["xml"]):
                if projects:
                    self.add(
                        TASK,
                        place,
                        projects,
                        self.tasks.get(task_id, {}).get("name", "") or task_id,
                        "runs",
                        self.task_providers([task_id]),
                    )

    def variables(self) -> None:
        """A global that one Project reads and another sets, when the reader does not set it itself."""
        index = varxref.build_index(state=self.state)
        for variable in index.variables.values():
            if variable.scope != varxref.GLOBAL:
                continue
            setters = {project for ref in variable.sets if (project := _project_of(ref.target))}
            if not setters:
                continue
            reads: dict[str, list[varxref.Reference]] = {}
            for ref in variable.reads:
                if (project := _project_of(ref.target)) and project not in setters:
                    reads.setdefault(project, []).append(ref)
            for user_project, refs in reads.items():
                first = refs[0].target
                if first is None:
                    continue
                self.links.extend(
                    Link(
                        VARIABLE,
                        user_project,
                        provider,
                        first,
                        variable.name,
                        "reads",
                        None,
                        len(setters) == 1,
                        len(refs),
                    )
                    for provider in sorted(setters)
                )


def _project_of(place: Target | None) -> str:
    """The Project a variable reference sits in: the one its Target names, or the Project itself for a Project's own."""
    if place is None:
        return ""
    return place.project or (place.key if place.kind == PROJECT else "")


def _loops(edges: dict[tuple[str, str], Edge], projects: list[str]) -> list[list[str]]:
    """The groups of Projects that each reach every other, through the lines between them."""
    step: dict[str, list[str]] = {}
    for user, provider in edges:
        step.setdefault(user, []).append(provider)

    def reach(start: str) -> set[str]:
        seen: set[str] = set()
        queue = [start]
        while queue:
            for nxt in step.get(queue.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    reaches = {project: reach(project) for project in projects if project in step}
    loops: list[list[str]] = []
    placed: set[str] = set()
    for project in projects:
        if project in placed or project not in reaches.get(project, ()):
            continue
        group = sorted((other for other in reaches[project] if project in reaches.get(other, ())), key=str.lower)
        group = sorted({project, *group}, key=str.lower)
        placed.update(group)
        loops.append(group)
    return loops


def build_graph(state: RunState) -> ProjectGraph:
    """Read the loaded configuration and return the Projects and the uses between them.

    Safe with nothing loaded: there are no Projects, and the graph is empty.
    """
    scan = _Scan(state)
    scan.tasks_and_scenes()
    scan.profiles()
    scan.variables()

    graph = ProjectGraph(projects=sorted(object_table("all_projects", state=state), key=str.lower))
    for link in scan.links:
        graph.edges.setdefault((link.user_project, link.provider), Edge(link.user_project, link.provider)).links.append(
            link
        )
    graph.loops = _loops(graph.edges, graph.projects)
    return graph


# ##################################################################################
# Saying it.
# ##################################################################################


def _link_row(link: Link, *, from_side: bool) -> Row:
    """One use as a line of a report: who uses what, with each end a click.

    `from_side` is True when the line is in the section of the Project that USES: it then names the Project the thing
    is in. In the provider's section the user's own label already says which Project it is in.
    """
    used_label = (
        f"{link.used}" if link.kind == VARIABLE else f"{'Task' if link.kind == TASK else 'Scene'} '{link.used}'"
    )
    where = f" in '{link.provider}'" if from_side else ""
    times = f" ({link.count} places)" if link.count > 1 else ""
    return Row.of_pieces(
        [
            ("      ", None),
            (link.user.label, link.user),
            (f" {link.verb} ", None),
            (used_label, link.used_at),
            (f"{where}{times}", None),
        ],
    )


def _needed_together(graph: ProjectGraph, project: str) -> str:
    """The Projects to take along with this one, those it needs directly first and then those it needs only through them.

    'Media (through Utilities)' says why a Project that nothing here uses itself is in the list.
    """
    direct = [edge.provider for edge in graph.uses(project)]
    through = {name: graph.needs(name) for name in direct}
    parts = list(direct)
    for name in graph.needs(project):
        if name not in direct:
            via = ", ".join(each for each in direct if name in through[each])
            parts.append(f"{name} (through {via})")
    return ", ".join(parts)


def project_rows(graph: ProjectGraph, project: str) -> list[Row]:
    """Everything the graph says about one Project: what it needs, what needs it, and what deleting it would break."""
    rows: list[Row] = [Row(f"Project '{project}'", Target(PROJECT, project, project))]
    uses, used_by = graph.uses(project), graph.used_by(project)
    loop = graph.loop_of(project)

    if not uses and not used_by:
        rows.append(Row("  Nothing crosses into or out of this Project."))
        return rows
    if loop:
        others = ", ".join(f"'{other}'" for other in loop if other != project)
        rows.append(Row(f"  In a loop with {others}: each needs another, so they can only be split out together."))

    if uses:
        rows.extend((Row(""), Row(f"  Needs {len(uses)} other {'Project' if len(uses) == 1 else 'Projects'}:")))
        for edge in uses:
            rows.append(Row(f"    '{edge.provider}' -- {edge.summary}", Target(PROJECT, edge.provider, edge.provider)))
            rows.extend(_link_row(link, from_side=True) for link in edge.links)
        rows.append(Row(f"  To use it on its own you would need: {_needed_together(graph, project)}."))
    else:
        rows.extend((Row(""), Row("  Needs nothing from another Project: it can be split out or shared as it is.")))

    if used_by:
        rows.extend((Row(""), Row(f"  Used by {len(used_by)} other {'Project' if len(used_by) == 1 else 'Projects'}:")))
        for edge in used_by:
            rows.append(Row(f"    '{edge.user}' -- {edge.summary}", Target(PROJECT, edge.user, edge.user)))
            rows.extend(_link_row(link, from_side=False) for link in edge.links)
        indirect = [name for name in graph.needed_by(project) if name not in {edge.user for edge in used_by}]
        if indirect:
            rows.append(Row(f"  Through those, also leaned on by: {', '.join(indirect)}."))
        broken = graph.would_break(project)
        rows.append(Row(""))
        if broken:
            rows.append(
                Row(
                    f"  If this Project were deleted with its contents, {len(broken)} of those would be left with nothing:"
                )
            )
            rows.extend(_link_row(link, from_side=False) for link in broken)
        else:
            rows.append(
                Row(
                    "  Deleting this Project would leave nothing dangling: everything others take from it is also elsewhere."
                )
            )
    return rows


def report_rows(graph: ProjectGraph) -> list[Row]:
    """The whole graph as a report: a line per Project, then the detail of each one that crosses into another."""
    linked = [name for name in graph.projects if graph.uses(name) or graph.used_by(name)]
    rows = [
        Row("PROJECT DEPENDENCIES"),
        Row(f"{len(graph.projects)} Projects, {len(graph.edges)} lines between them, {len(graph.loops)} loops."),
        Row(""),
    ]
    rows.extend(_standing_row(graph, name) for name in graph.projects)
    for name in linked:
        rows.extend((Row(""), *project_rows(graph, name)))
    return rows


def _standing_row(graph: ProjectGraph, project: str) -> Row:
    """One Project, one line: how it stands and how many Projects it needs and is needed by."""
    words = {SELF_CONTAINED: "self-contained", NEEDS_OTHERS: "needs others", IN_A_LOOP: "in a loop"}
    return Row(
        f"  {project}: {words[graph.standing(project)]}; needs {len(graph.uses(project))}, "
        f"needed by {len(graph.used_by(project))}",
        Target(PROJECT, project, project),
    )


# ##################################################################################
# Drawing it.
# ##################################################################################

# The most lines drawn in the graph; past this a picture is a hairball and the table says it better.
MAX_DRAWN_LINES = 80


def mermaid(graph: ProjectGraph) -> tuple[str, dict[str, str]]:
    """The graph as a Mermaid flowchart, and which Project each node is: {node id: Project name}.

    An arrow from each Project to each Project it needs, labelled with what.  Only Projects with a line to or from
    them are drawn.  Those in a loop are outlined in red.  The heaviest lines are kept when there are more than
    MAX_DRAWN_LINES.  The names of the nodes are what a click on one hands back, so the window can select that Project.
    """
    edges = sorted(graph.edges.values(), key=lambda edge: (-len(edge.links), edge.user.lower(), edge.provider.lower()))
    edges = edges[:MAX_DRAWN_LINES]
    names = sorted({name for edge in edges for name in (edge.user, edge.provider)}, key=str.lower)
    ids = {name: f"p{number}" for number, name in enumerate(names)}

    def label(text: str) -> str:
        return text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")

    lines = ["flowchart LR"]
    lines.extend(f'  {ids[name]}["{label(name)}"]' for name in names)
    lines.extend(f'  {ids[edge.user]} -->|"{label(edge.summary)}"| {ids[edge.provider]}' for edge in edges)
    in_loop = [ids[name] for name in names if graph.standing(name) == IN_A_LOOP]
    lines.extend(f"  style {each} stroke:#e53935,stroke-width:3px" for each in in_loop)
    return "\n".join(lines), {node: name for name, node in ids.items()}


def write_report(rows: list[Row], state: RunState) -> str:
    """Save the report as text, the way the other reports are saved.  Returns the file's path, or "" if it could not be."""
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(PROJDEPS_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"The Project dependencies report could not be written: {error}")
        return ""
    return file_path
