"""Impact analysis: what a delete will break, worked out before anything is deleted."""

#! /usr/bin/env python3

#                                                                                       #
# impact: Answer "what breaks if I delete this?" for a Project, Profile, Task or Scene. #
#                                                                                       #
# Everything here reads PrimeItems.tasker_root_elements and nothing else -- no GUI, no  #
# mutation of any kind.  The point of the module is to be run BEFORE the delete, from   #
# the confirmation dialog, so it cannot be allowed to touch what it is describing.      #
#                                                                                       #
# The scan itself is healthck's.  That module already walks the whole file for what     #
# points at what -- it is how BROKEN-PERFORM-TASK is found -- and this runs the same    #
# index forward instead of backward: healthck asks which references are already broken, #
# and this asks which ones a delete is about to break.  A scan of its own here is how   #
# the two would come to disagree about what counts as a reference, so there is not one. #
#                                                                                       #
# What separates a reference that breaks from one that does not is whether the delete   #
# rewrites it, and that is a fact about the delete rather than about the reference --   #
# see _REWRITTEN_BY, which is this module's one piece of knowledge about the four       #
# delete functions it describes.                                                        #
#                                                                                       #
from __future__ import annotations

from dataclasses import dataclass, field

from maptasker.src import healthck, varxref
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK, Row, Target
from maptasker.src.primitem import PrimeItems

# Severity ordering is the order consequences are reported in, worst first.
BREAKS = "BREAKS"
CHANGES = "CHANGES"
_SEVERITY_ORDER = (BREAKS, CHANGES)

_SEVERITY_HEADINGS = {
    BREAKS: "WILL BREAK -- these will point at something that is no longer there",
    CHANGES: "WILL CHANGE -- nothing dangles, but it will not behave as it does now",
}

_REPORT_WIDTH = 78

# Which references each delete rewrites for itself.  Everything absent from this table is
# left exactly as it is, pointing at what is about to stop existing.
#
# Deleting a Task unlinks it from every Profile's <mid0>/<mid1> (taskedit.delete_task), so
# a Profile link is repaired rather than broken.  Deleting a PROJECT with its contents does
# not: projedit.delete_profiles_and_tasks_of_project drops the Profiles and Tasks from the
# lookup tables and stops there, so a Profile in some other Project that runs one of the
# deleted Tasks is left holding its id.  That asymmetry is the reason this is a table
# keyed by what is being deleted rather than a property of the reference.
#
# A Project's own <tids>/<pids>/<scenes> are not in here because they are not in the
# reference index at all: healthck records ownership separately from use, deliberately --
# see _index_projects.  What a delete does to those lists is reported by _what_goes below.
_REWRITTEN_BY = {
    TASK: frozenset({healthck.BY_PROFILE_LINK}),
    PROFILE: frozenset(),
    SCENE: frozenset(),
    PROJECT: frozenset(),
}

# What each sort of dangling reference is called, and how the report explains it.  Keyed by
# healthck's BY_ constants so that a new sort of reference added to the index arrives here
# as a KeyError rather than as a silently unreported consequence.
_DANGLING = {
    healthck.BY_PERFORM_TASK: (
        "DANGLING-PERFORM-TASK",
        "Calls it by name.  The action is left exactly as it is and will find nothing to run.",
    ),
    healthck.BY_SCENE_ELEMENT: (
        "DANGLING-SCENE-TASK",
        "This Scene element fires it by id.  The binding is left as it is and will fire nothing.",
    ),
    healthck.BY_SCENE_COMPONENT: (
        "DANGLING-SCENE-TASK",
        "This Scene component runs it by name.  The handler is left as it is and will run nothing.",
    ),
    healthck.BY_WIDGET: (
        "DANGLING-WIDGET",
        (
            "Names it as a home screen widget, and a Tasker widget is named for the Task it "
            "launches -- so a widget on the home screen will stop working."
        ),
    ),
    healthck.BY_PROFILE_LINK: (
        "DANGLING-PROFILE-LINK",
        (
            "Runs the Task here.  Deleting a Project's contents does not unlink the Profiles "
            "outside it, so this link will be left pointing at a Task that is gone."
        ),
    ),
    healthck.BY_SCENE_ACTION: (
        "DANGLING-SCENE-ACTION",
        (
            "Names the Scene.  Deleting a Scene never rewrites the actions that show, hide or "
            "destroy it, so this one will act on a Scene that is not there."
        ),
    ),
}


@dataclass
class Consequence:
    """One thing the delete will do beyond removing the object itself.

    'tag' is a stable, deliberately un-translated identifier (DANGLING-PERFORM-TASK), for
    healthck.Finding's reason: it stays English in every language so two runs can be
    compared and a tag can be searched for.
    """

    severity: str
    tag: str
    where: str
    detail: str
    # Where clicking this consequence goes in the Map view: the place that will be left
    # broken, not the object being deleted.  That object is named once at the top of the
    # report, and it is about to be gone -- the places to go and look at are these.
    target: Target | None = None


@dataclass
class Impact:
    """What deleting one object will do to the rest of the configuration."""

    subject: str  # "Project 'Home' > Task 'Wake Up' (id 118)"
    consequences: list[Consequence] = field(default_factory=list)
    # What the delete takes with it and what it leaves behind, in prose -- the sentences
    # the confirmation dialogs used to work out for themselves.
    goes: list[str] = field(default_factory=list)
    # What this analysis could not be sure of.  Printed rather than left implied, for the
    # reason healthck._limitations gives: a report that invites someone to delete
    # something, without saying what it cannot see, is worse than no report.
    caveats: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        """How many consequences of each severity."""
        return {
            severity: sum(1 for item in self.consequences if item.severity == severity) for severity in _SEVERITY_ORDER
        }

    @property
    def breaks(self) -> int:
        """How many places will be left pointing at something that is gone."""
        return self.counts[BREAKS]

    def summary(self) -> str:
        """The one line a confirmation dialog leads with."""
        counts = self.counts
        if not self.consequences:
            return "Nothing else in this configuration points at it -- nothing will be left dangling."
        parts = []
        if counts[BREAKS]:
            parts.append(f"{counts[BREAKS]} place(s) will be left pointing at something that is gone")
        if counts[CHANGES]:
            parts.append(f"{counts[CHANGES]} thing(s) will change")
        return f"{' and '.join(parts)}."


# ##################################################################################
# Reading the file.  Deliberately direct rather than through the editors: those
# mutate, and every one of them imports the others, while this has to stay a pure
# reader that healthck's own tests can stand up without a GUI.
# ##################################################################################
def _list_of(project_element: object, tag: str) -> list[str]:
    """A Project's <pids>/<tids>/<scenes> as a list ([] when it holds none).

    The filter is what stops an empty element being read as one member whose name is the
    empty string -- healthck._split_ids makes the same point at more length.
    """
    child = project_element.find(tag)
    text = (child.text or "").strip() if child is not None else ""
    return [item.strip() for item in text.split(",") if item.strip()] if text else []


def _projects_listing(tag: str, value: str) -> list[str]:
    """Every Project whose <tag> list holds this value, by name."""
    return sorted(
        name
        for name, entry in PrimeItems.tasker_root_elements.get("all_projects", {}).items()
        if value in _list_of(entry["xml"], tag)
    )


def _profile_task_ids(profile_element: object) -> list[str]:
    """The Task ids a Profile links as its Entry/Exit Task, deduplicated, in order.

    dict.fromkeys rather than a set: a Profile may legitimately use one Task for both its
    Entry and its Exit (see profedit.render_standalone_profile_xml), and the order is the
    order Tasker wrote them in.
    """
    return list(dict.fromkeys(child.text for child in profile_element if "mid" in child.tag and child.text))


def _subject(kind: str, name: str, index: healthck.ReferenceIndex) -> Target | None:
    """The object about to be deleted, as somewhere the Map can find -- None if it is gone.

    None is not a program error: the delete dialogs are opened from an editor that has been
    sitting there while the configuration could have changed underneath it, which is the
    same staleness the reference counts they show are re-read to avoid.
    """
    root = PrimeItems.tasker_root_elements
    if kind == TASK:
        entry = root.get("all_tasks_by_name", {}).get(name)
        return Target(TASK, entry["id"], name, index.project_of_task.get(entry["id"], "")) if entry else None
    if kind == PROFILE:
        entry = root.get("all_profiles_by_name", {}).get(name)
        return Target(PROFILE, entry["id"], name, index.project_of_profile.get(entry["id"], "")) if entry else None
    if kind == SCENE:
        return (
            Target(SCENE, name, name, index.project_of_scene.get(name, ""))
            if name in root.get("all_scenes", {})
            else None
        )
    return Target(PROJECT, name, name) if name in root.get("all_projects", {}) else None


def _doomed(subject: Target, *, keep_contents: bool) -> set[tuple[str, str]]:
    """Every object that will no longer be in the file, as (kind, key) pairs.

    One pair for a Task, Profile or Scene.  A Project is the whole of the reason this is a
    set: "Delete Contents" takes its Profiles and Tasks with it
    (projedit.delete_profiles_and_tasks_of_project), and a reference from one of THOSE to
    another of them is not a consequence of anything -- both ends are going.

    Its Scenes are not in here under either choice, and that is not an oversight: a Project
    delete leaves its Scenes in the file whichever button is pressed.  What it does to them
    is reported by _left_adrift.
    """
    doomed = {(subject.kind, subject.key)}
    if subject.kind != PROJECT or keep_contents:
        return doomed

    project = PrimeItems.tasker_root_elements["all_projects"][subject.key]["xml"]
    doomed.update((PROFILE, profile_id) for profile_id in _list_of(project, "pids"))
    doomed.update((TASK, task_id) for task_id in _list_of(project, "tids"))
    return doomed


def _owner(target: Target | None) -> tuple[str, str]:
    """The object a place is inside, as the same (kind, key) pair _doomed deals in.

    An action's Target carries the Task it is in, a Scene element's the Scene, so the
    action number and the element name fall away here and only the object remains.
    """
    return (target.kind, target.key) if target is not None else ("", "")


# ##################################################################################
# The consequences themselves.
# ##################################################################################
def _referrers_of(kind: str, key: str, index: healthck.ReferenceIndex) -> list[healthck.Referrer]:
    """Everything that points at one doomed object.  Empty for kinds nothing refers to."""
    if kind == TASK:
        return index.task_referrers.get(key, [])
    if kind == SCENE:
        return index.scene_referrers.get(key, [])
    # A Profile is named only by the <pids> of the Project that owns it, and a Project by
    # nothing at all -- neither is in the reference index, and neither can be left dangling
    # by its own delete.  What each takes down with it is _left_dead's and _left_adrift's.
    return []


def _dangling(
    impact: Impact,
    doomed: set[tuple[str, str]],
    index: healthck.ReferenceIndex,
    rewritten: frozenset[str],
) -> None:
    """Report every reference the delete will leave pointing at nothing."""
    for kind, key in sorted(doomed):
        for referrer in _referrers_of(kind, key, index):
            # A reference made from inside something that is also being deleted is not a
            # consequence: both ends go together.
            if _owner(referrer.where) in doomed or referrer.kind in rewritten:
                continue
            tag, detail = _DANGLING[referrer.kind]
            impact.consequences.append(Consequence(BREAKS, tag, referrer.label, detail, referrer.where))


def _left_without_a_task(impact: Impact, doomed: set[tuple[str, str]], subject: Target) -> None:
    """Report a surviving Profile whose every Entry/Exit Task is being deleted.

    Only when it is left with NONE.  A Profile that loses one of two links still runs, and
    saying so would bury the case that matters -- a Profile that is kept, still triggers,
    and now has nothing to run -- among notes about links the dialog already counts.

    Only for a delete that unlinks as it goes, which is the Task delete: where the link is
    left in place instead, the Profile is reported as a dangling reference and this would
    say the same thing twice.
    """
    if subject.kind != TASK:
        return

    for profile_id, profile in PrimeItems.tasker_root_elements.get("all_profiles", {}).items():
        if (PROFILE, profile_id) in doomed:
            continue
        task_ids = _profile_task_ids(profile["xml"])
        if task_ids and all((TASK, task_id) in doomed for task_id in task_ids):
            impact.consequences.append(
                Consequence(
                    CHANGES,
                    "PROFILE-WITHOUT-TASK",
                    Target(PROFILE, profile_id, profile["name"]).label,
                    "Every Task it runs is being deleted and the links removed with them.  The "
                    "Profile is kept, and will go on triggering without running anything.",
                    Target(PROFILE, profile_id, profile["name"]),
                ),
            )


def _left_dead(impact: Impact, doomed: set[tuple[str, str]], index: healthck.ReferenceIndex) -> None:
    """Report a surviving Task that everything now running it is being deleted.

    The Task itself is kept -- no delete in this program reaches through an object to the
    Tasks it merely calls -- so this is not a broken reference.  It is the Task becoming
    what healthck reports as UNREFERENCED-TASK, said before the fact rather than after.

    A Task nothing runs already is left alone: it is not being made dead by this delete, and
    naming it here would put the file's existing problems in front of somebody who asked a
    question about one object.
    """
    for task_id, task in PrimeItems.tasker_root_elements.get("all_tasks", {}).items():
        if (TASK, task_id) in doomed:
            continue
        referrers = index.task_referrers.get(task_id, [])
        if not referrers or not all(_owner(referrer.where) in doomed for referrer in referrers):
            continue
        surviving = sorted({referrer.label for referrer in referrers})
        impact.consequences.append(
            Consequence(
                CHANGES,
                "TASK-LEFT-DEAD",
                Target(TASK, task_id, task["name"], index.project_of_task.get(task_id, "")).label,
                f"It is kept, but the only thing that runs it is going: {'; '.join(surviving)}.",
                Target(TASK, task_id, task["name"], index.project_of_task.get(task_id, "")),
            ),
        )


def _left_adrift(impact: Impact, subject: Target) -> None:
    """Report the Scenes a deleted Project leaves in no Project at all.

    A Project delete moves its Profiles and Tasks into "Base" or deletes them, and does
    neither to its Scenes: move_project_contents_to_base walks <pids> and <tids> only, and
    the cascade deletes only what those two name.  The Scenes stay in the file, listed by
    nothing -- healthck's ORPHAN-SCENE, arriving as a surprise.  Worth saying out loud
    precisely because neither button on the dialog mentions Scenes at all.
    """
    if subject.kind != PROJECT:
        return

    project = PrimeItems.tasker_root_elements["all_projects"][subject.key]["xml"]
    for scene_name in _list_of(project, "scenes"):
        if scene_name not in PrimeItems.tasker_root_elements.get("all_scenes", {}):
            continue  # Already broken -- healthck's BROKEN-SCENE-REF, not this delete's doing.
        if [name for name in _projects_listing("scenes", scene_name) if name != subject.key]:
            continue  # Another Project lists it too, so it keeps a home.
        impact.consequences.append(
            Consequence(
                CHANGES,
                "SCENE-LEFT-ADRIFT",
                Target(SCENE, scene_name, scene_name, subject.key).label,
                "It is neither deleted nor moved -- a Project's Scenes go with neither choice -- "
                "so it will be left in the file with no Project listing it.",
                Target(SCENE, scene_name, scene_name),
            ),
        )


def _dangling_variables(impact: Impact, doomed: set[tuple[str, str]]) -> None:
    """Report the globals that only what is being deleted ever sets.

    A read of a variable nothing sets is not an error Tasker will report: it comes back
    empty, and the Task carries on with an empty string where a value should have been.
    That is the quietest way a delete can break something, which is why it is worth the
    second walk over the file that varxref's index costs.

    Globals only.  A local belongs to the Task it is in -- Tasker scopes it there, and
    varxref keys it per Task for that reason -- so it goes with the Task that owns it and
    can leave nothing behind.  Built-in and Tasker-set names are set by Tasker itself.
    """
    index = varxref.build_index()
    found = False

    for variable in index.variables.values():
        if variable.scope != varxref.GLOBAL or not variable.sets:
            continue
        if any(_owner(reference.target) not in doomed for reference in variable.sets):
            continue
        readers = [reference for reference in variable.reads if _owner(reference.target) not in doomed]
        if not readers:
            continue
        found = True
        first = readers[0]
        # Distinct places, not references: one action reading %Name twice is one place to
        # go and look at, and counting it twice would overstate the damage.
        places = len({reference.where for reference in readers})
        impact.consequences.append(
            Consequence(
                BREAKS,
                "DANGLING-VARIABLE",
                first.where,
                f"Reads {variable.name}, which nothing but what you are deleting ever sets"
                + (f" ({places} places read it)." if places > 1 else ".")
                + "  Those reads will come back empty rather than fail.",
                first.target,
            ),
        )

    if not found:
        return

    # Said for the reason healthck says the same sort of thing about an unreferenced Task: a
    # backup records what is inside Tasker, and a global can be given a value from outside it.
    impact.caveats.append(
        "A global variable can also be set from Tasker's Variables tab, by a home screen "
        "widget or by another app through Tasker's API, none of which appear in this file.",
    )
    if index.indirect_references:
        impact.caveats.append(
            f"{index.indirect_references} action(s) in this configuration name the variable they "
            "set through another variable, so which one each sets is decided on the device.  Any "
            "of them may in fact be setting a variable reported above.",
        )


# ##################################################################################
# What goes and what stays -- the prose half, which is not a consequence of anything.
# ##################################################################################
def _what_goes(subject: Target, *, keep_contents: bool) -> list[str]:
    """What the delete takes with it and what it deliberately leaves behind.

    The sentences each confirmation dialog used to work out for itself from its own count
    function, gathered here so that the four say the same kind of thing in the same order,
    and so that what is KEPT is stated as plainly as what is broken -- a delete dialog that
    lists only damage reads as a warning not to press the button.
    """
    root = PrimeItems.tasker_root_elements

    if subject.kind == TASK:
        projects = _projects_listing("tids", subject.key)
        profiles = [
            entry["name"]
            for entry in root.get("all_profiles", {}).values()
            if subject.key in _profile_task_ids(entry["xml"])
        ]
        return [
            (
                f"Removed from {len(projects)} Project(s) that list it, and unlinked from "
                f"{len(profiles)} Profile(s) that run it."
            ),
            "Those Profiles themselves are kept.",
        ]

    if subject.kind == PROFILE:
        profile = root["all_profiles"][subject.key]["xml"]
        linked = len(_profile_task_ids(profile))
        return [
            f"Removed from {len(_projects_listing('pids', subject.key))} Project(s) that list it.",
            (
                f"Its {linked} linked Task(s) are kept -- they belong to the Project, not to this Profile."
                if linked
                else "It has no linked Tasks."
            ),
        ]

    if subject.kind == SCENE:
        return [
            f"Removed from {len(_projects_listing('scenes', subject.key))} Project(s) that list it.",
            "Its elements go with it; the Tasks they fire are kept.",
        ]

    project = root["all_projects"][subject.key]["xml"]
    profiles, tasks = len(_list_of(project, "pids")), len(_list_of(project, "tids"))
    return [
        (
            f"Its {profiles} Profile(s) and {tasks} Task(s) move into 'Base'."
            if keep_contents
            else f"Its {profiles} Profile(s) and {tasks} Task(s) are deleted with it."
        ),
        f"Its {len(_list_of(project, 'scenes'))} Scene(s) are neither moved nor deleted.",
    ]


# ##################################################################################
# Entry point and report.
# ##################################################################################
def _order(item: Consequence) -> tuple:
    """Where one consequence sorts: worst first, then grouped by tag, then by place.

    The place is taken from the Target rather than from the printed line, which is the
    whole point of this being a function.  A line reads "... Task 'Call Log' (id 502)
    action 127", and sorting on that text puts action 127 ahead of action 33 -- which, in a
    list somebody is working down to fix each one in turn, reads as a bug rather than as an
    ordering.  The action number is sorted as the number it is.
    """
    target = item.target
    place = (target.project, target.name or target.key, target.action) if target else (item.where, "", 0)
    # The detail settles the last tie, and settles a real one: every variable a delete
    # strands is read from somewhere, and several are routinely read from the SAME action,
    # so without this the list of them comes out in whatever order the scan happened to
    # meet the names in.  It sorts by variable name because the detail line opens with it.
    return (_SEVERITY_ORDER.index(item.severity), item.tag, *place, item.detail)


def analyze_delete(kind: str, name: str, *, keep_contents: bool = True) -> Impact:
    """What deleting this Project, Profile, Task or Scene will do to the rest of the file.

    'kind' is one of mapjump's PROJECT/PROFILE/TASK/SCENE, and 'name' the displayed name --
    the same pair every delete function in the editors is called with.  keep_contents is
    read for a Project and ignored for everything else, matching projedit.delete_project's
    own signature: it is the only delete with two buttons, and the two have very different
    consequences.

    Read live, at the moment the confirmation is put up, for the reason the counts it
    replaces are read live: the editor may have been open a while, and a report worked out
    when the editor opened would describe a file that has since changed underneath it.

    Costs one whole-file reference scan plus one variable scan -- measured at well under a
    second on the largest backup to hand (846 Tasks), which is the right side of the trade
    for a question asked once, immediately before something irreversible.
    """
    index = healthck.build_reference_index()
    subject = _subject(kind, name, index)
    if subject is None:
        return Impact(subject=name, caveats=[f"'{name}' is no longer in the loaded configuration."])

    impact = Impact(subject=subject.label, goes=_what_goes(subject, keep_contents=keep_contents))
    doomed = _doomed(subject, keep_contents=keep_contents)

    _dangling(impact, doomed, index, _REWRITTEN_BY[subject.kind])
    _left_without_a_task(impact, doomed, subject)
    _left_dead(impact, doomed, index)
    _left_adrift(impact, subject)
    _dangling_variables(impact, doomed)

    # Sorted by tag so every instance of one consequence reads as a group, which is what
    # makes a long list skimmable and two runs comparable -- healthck._build_report's
    # ordering, and for its reason.
    impact.consequences.sort(key=_order)

    if any(item.tag == "DANGLING-PERFORM-TASK" for item in impact.consequences):
        impact.caveats.append(
            "A Perform Task names the Task it runs by name, so another Task of the same name "
            "would satisfy these -- rename a replacement into place and they mend themselves.",
        )
    return impact


def consequence_rows(impact: Impact) -> list[Row]:
    """Just the consequences and the caveats, as Rows -- what the confirmation dialog shows.

    Without the heading and the "what goes" sentences report_rows puts above them: the
    dialog has its own title naming the object, and shows those sentences as labels of its
    own, so a report carrying them again would say everything twice.

    Empty when nothing follows from the delete, which is what lets the panel leave the list
    out altogether rather than draw an empty box under a line saying nothing will break.
    """
    rows: list[Row] = []

    for severity in _SEVERITY_ORDER:
        of_this_severity = [item for item in impact.consequences if item.severity == severity]
        if not of_this_severity:
            continue
        if rows:
            rows.append(Row(""))
        rows += [Row(_SEVERITY_HEADINGS[severity]), Row("-" * _REPORT_WIDTH)]
        for item in of_this_severity:
            # The location line is the clickable one, not the detail -- the detail says what
            # is wrong and the location is the thing to go and look at (see healthck).
            rows += [Row(f"[{item.tag}]  {item.where}", item.target), Row(f"    {item.detail}"), Row("")]

    for caveat in impact.caveats:
        rows += [Row(caveat), Row("")]
    return rows


def report_rows(impact: Impact) -> list[Row]:
    """The whole analysis as Rows, one per line, each carrying where clicking it goes.

    Rows rather than finished text for healthck._build_report's reason: this is rendered as
    the HTML the confirmation dialog shows with its places clickable, and it should stay
    renderable as the plain text a report would save without being written twice.
    """
    rows = [Row(f"Deleting {impact.subject}"), Row("=" * _REPORT_WIDTH)]
    rows += [Row(f"  {sentence}") for sentence in impact.goes]
    rows += [Row(""), Row(impact.summary()), Row("")]
    return rows + consequence_rows(impact)
