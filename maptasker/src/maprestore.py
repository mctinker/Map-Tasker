"""maprestore: bring one object back from the configuration history, or put it back as it was."""

#! /usr/bin/env python3

#                                                                                        #
# maprestore: restore from history, one object at a time.                                #
#                                                                                        #
# timeline keeps every configuration that has been loaded, and Changes Since reports what #
# differs between one of those and what is open now.  Until this, that is where it        #
# stopped: a Task deleted by mistake could be SEEN in last Tuesday's configuration and    #
# not brought back from it.  This is the missing half, and it does two things:            #
#                                                                                        #
#   BRING BACK   an object the history has and the configuration no longer does -- a       #
#                Task, a Profile or a Scene the report lists as REMOVED.                 #
#   REVERT       an object both have, put back as it stood then -- one the report lists   #
#                as CHANGED or RENAMED.                                                  #
#                                                                                        #
# Same contract as maprefac / mapfix / mapswap: reads and writes                          #
# PrimeItems.tasker_root_elements and nothing else, no GUI import, identity from mapjump. #
# And it IS maprefac, in the part that matters: a restore is one change made of steps     #
# that are meaningless apart (put the Task back, and put it back in its Project), so it   #
# is planned as a maprefac.Plan, previewed through maprefac.report_rows, and applied by   #
# maprefac.apply -- nothing applied unseen, blocks refused twice, attachment re-checked,  #
# and the whole restore one press of Undo.  A second copy of that machinery here is how   #
# the two would come to disagree about what "safe to apply" means.                        #
#                                                                                        #
# ONE OBJECT AT A TIME, AND NEVER A MERGE                                                 #
#                                                                                        #
# The Compare design (xmldiff_design.md) put merging out of scope, and this keeps it out. #
# Restoring a Task restores THAT Task and the Project membership it had -- which is where #
# it lives rather than something else -- and touches nothing more.  The Profile that ran  #
# it is not relinked, the Perform Task calls that named it are not rewritten, and a       #
# Project deleted with it is not rebuilt.  Each of those is a separate object with its    #
# own state today, and deciding that its state then was the right one is a decision this #
# makes one object at a time, in front of the user, or not at all.  What is left undone   #
# is said, specifically, in the preview -- never left for the user to discover.           #
#                                                                                        #
# WHAT DUPLICATE'S CHECKS ARE DOING HERE                                                  #
#                                                                                        #
# Bringing an object back is putting an object into a configuration that has moved on     #
# without it, which is the same problem Duplicate solves: its id may have been handed to  #
# something else since, and its name certainly may have.  So the answers are Duplicate's: #
# the id space is Tasks' and Profiles' together (taskedit.next_unique_task_or_profile_id), #
# and a name already taken gets maprefac.unique_name's treatment rather than a second     #
# owner -- two Tasks sharing a name is a finding the Health Check exists to report.  The  #
# one difference is that a restore KEEPS the old id when it is free, where a copy never   #
# does: that id is the one Tasker on the device last knew the object by.                  #
#                                                                                        #
# WHAT IS NOT OFFERED                                                                     #
#                                                                                        #
# Projects, because a Project is its members -- bringing one back is bringing back every  #
# Profile, Task and Scene in it, which is the merge.  Global Variables and Settings,      #
# because they are values rather than objects and the Variable editor already sets one.   #
# And objects ADDED since, because undoing an addition is a delete, and deleting belongs  #
# to the Edit dialogs, where the delete checks are.  candidates() counts all three so the  #
# dialog can say they were left out on purpose.                                           #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- only for its Element class
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src import maprefac, profedit, projedit, taskedit, xmldiff
from maptasker.src.editcommon import set_child_text as _set_child_text
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK, Target
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    import defusedxml.ElementTree

    from maptasker.src.xmldiff import Configuration


# ##################################################################################
# What can be restored.
# ##################################################################################

# The two things a restore can be.  Carried on a Candidate so the dialog can label its
# button and the plan can word its heading without either re-deriving it from the diff.
BRING_BACK = "bring back"
REVERT = "revert"

# maprefac.Plan.kind for every plan built here.  maprefac's own four are what its dialog
# switches on; this is a fifth that only this module and its dialog ever see.
RESTORE = "restore"

# The kinds that can be restored, keyed by xmldiff's names for them, with the table each
# lives in, mapjump's name for it, and the Project membership list that owns it.
#
# Keyed by xmldiff's kind because a Candidate starts life as an xmldiff Entry, and its key
# is already the key of the table named here: xmldiff identifies Tasks and Profiles by the
# id their tables are keyed by, and Scenes by the name theirs is.
_KINDS = {
    "Task": ("all_tasks", TASK, "tids"),
    "Profile": ("all_profiles", PROFILE, "pids"),
    "Scene": ("all_scenes", SCENE, "scenes"),
}

# The by-name table each kind keeps alongside its main one, where it keeps one.  A Scene's
# main table is already keyed by name.
_BY_NAME = {"Task": "all_tasks_by_name", "Profile": "all_profiles_by_name"}

# A Profile's two links to the Tasks it runs, and what each is called in prose.
_TASK_LINKS = (("mid0", "Entry"), ("mid1", "Exit"))

# "Perform Task" -- arg0 is the Task's NAME.  The one by-name reference to a Task, and so
# the one a restore under a different name, or a revert to an older name, changes the
# meaning of.
_PERFORM_TASK_CODE = taskedit.PERFORM_TASK_ACTION_CODE
_PERFORM_TASK_NAME_ARG = f"arg{taskedit.PERFORM_TASK_NAME_ARG_ID}"

# The word unique_name puts in brackets after a name something else has taken since.
_RESTORED_SUFFIX = "restored"

# Said on every revert.  A revert is the whole object as it was, and the one thing worth
# being sure of before pressing it is that it takes EVERY later edit with it, not a chosen one.
_UNDONE_WHOLE = (
    "Every edit made to it since then is undone with this -- the ones listed above, all of them, not one "
    "at a time.  Undo puts it back as it is now."
)


@dataclass(frozen=True)
class Candidate:
    """One object the history can restore, as the dialog lists it.

    Built from xmldiff entries rather than from a second comparison, so what the list
    offers is exactly what the Changes Since report showed -- see candidates().

    `where` is the report's own location line for it: the older side's for something
    removed, since that is the only side it is on, and the newer side's otherwise.
    `target` is where a click goes, and is None for an object that is not in the
    configuration to be gone to -- which is every object waiting to be brought back.
    """

    kind: str  # xmldiff's: "Task", "Profile", "Scene"
    key: str
    action: str  # BRING_BACK or REVERT
    where: str
    details: tuple[str, ...] = ()
    target: Target | None = None
    # xmldiff's category for the row -- REMOVED, CHANGED, or RENAMED for a rename and nothing
    # else -- so the row carries the same bracketed tag the Changes Since report printed.
    category: str = xmldiff.CHANGED

    @property
    def tag(self) -> str:
        """The report's own bracketed tag for this row -- TASK-REMOVED, PROFILE-RENAMED."""
        return f"{self.kind.upper()}-{self.category}"

    @property
    def identity(self) -> tuple[str, str, str]:
        """What this candidate points at, independent of where it sits in any list."""
        return (self.kind, self.key, self.action)


@dataclass
class Offer:
    """What a snapshot can restore, and what it deliberately does not offer.

    `left_out` counts each kind of difference the list does not offer, by the reason it is
    not offered, so the dialog can say "3 Projects changed -- a Project is restored one
    member at a time" rather than letting a short list look like a short comparison.
    """

    candidates: list[Candidate] = field(default_factory=list)
    left_out: dict[str, int] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Nothing to offer.  Not the same as "nothing differs" -- see left_out."""
        return not self.candidates


# Why a difference is not offered, in the words the dialog uses.  Keyed by reason rather
# than by kind because two kinds can share one reason, and the dialog lists reasons.
LEFT_OUT_ADDED = "Added since -- undoing an addition is a delete; use the object's own Edit dialog."
LEFT_OUT_PROJECT = (
    "Project changes -- a Project is its Profiles, Tasks and Scenes, and restoring it whole would be a merge.  "
    "Restore its members one at a time instead."
)
LEFT_OUT_VALUE = "Global Variables and Tasker settings -- values rather than objects; set them in the Variable editor."


def candidates(older: Configuration, newer: Configuration) -> Offer:
    """Everything `older` can restore into `newer`, one row per object.

    One row per object rather than per entry: xmldiff reports a Task that was renamed AND
    edited as two entries, RENAMED and CHANGED, and both are undone by the one revert.
    Offering them as two rows would offer two buttons that do the same thing, the second of
    which would then find nothing left to do.

    Removed objects first, then changed ones: bringing back something deleted by mistake is
    the reason anybody opens this, and it is the row they are looking for.
    """
    offer = Offer()
    brought_back: list[Candidate] = []
    reverted: dict[tuple[str, str], Candidate] = {}

    for entry in xmldiff.differences(older, newer):
        if entry.kind not in _KINDS:
            reason = LEFT_OUT_PROJECT if entry.kind == "Project" else LEFT_OUT_VALUE
            offer.left_out[reason] = offer.left_out.get(reason, 0) + 1
            continue
        if entry.category == xmldiff.ADDED:
            offer.left_out[LEFT_OUT_ADDED] = offer.left_out.get(LEFT_OUT_ADDED, 0) + 1
            continue

        if entry.category == xmldiff.REMOVED:
            brought_back.append(
                Candidate(entry.kind, entry.key, BRING_BACK, entry.where, tuple(entry.details), None, xmldiff.REMOVED),
            )
            continue

        # RENAMED or CHANGED: one revert covers both.  The location line is the CHANGED
        # entry's when there is one -- a rename's own entry says only what the name was.
        identity = (entry.kind, entry.key)
        previous = reverted.get(identity)
        details = (*(previous.details if previous else ()), *entry.details)
        # A rename and an edit together read as CHANGED: the edit is the larger fact.
        category = (
            xmldiff.CHANGED
            if xmldiff.CHANGED in (entry.category, getattr(previous, "category", ""))
            else xmldiff.RENAMED
        )
        reverted[identity] = Candidate(
            entry.kind,
            entry.key,
            REVERT,
            entry.where,
            details,
            _live_target(entry.kind, entry.key),
            category,
        )

    useful = [candidate for candidate in reverted.values() if not _rename_is_blocked(older, candidate)]
    offer.candidates = sorted(brought_back, key=_order) + sorted(useful, key=_order)
    return offer


def _rename_is_blocked(older: Configuration, candidate: Candidate) -> bool:
    """Whether a rename-only revert could do nothing, because its old name is someone else's now.

    A revert keeps the current name when the old one is taken (see _plan_revert_named), so a
    row whose ONLY difference is the name would be a button that changes nothing.  The
    commonest way to get one is the restore just made: a Task brought back as 'Morning
    (restored)', because another 'Morning' is here, differs from the history by its name
    alone -- and offering to "put it back" the moment it arrives would be noise.
    """
    if candidate.category != xmldiff.RENAMED or candidate.kind not in _BY_NAME:
        return False
    table, _, _ = _KINDS[candidate.kind]
    old_name = _text((_old_table(older, table).get(candidate.key) or {}).get("xml"), "nme")
    holder = (_live_table(_BY_NAME[candidate.kind]).get(old_name) or {}).get("id") if old_name else None
    return holder is not None and holder != candidate.key


def _order(candidate: Candidate) -> tuple[int, str]:
    """Tasks, then Profiles, then Scenes -- the report's own order -- and by location within."""
    return (list(_KINDS).index(candidate.kind), candidate.where)


# ##################################################################################
# Reading the two sides.
# ##################################################################################


def _live_table(name: str) -> dict:
    """One table of the configuration that is open now -- the table itself, so it can be written.

    setdefault rather than `.get(name) or {}`, which is the difference between a restore and
    nothing: a configuration with no Scenes has an EMPTY all_scenes, an empty dict is falsy,
    and `or {}` would hand back a new dict nobody holds -- a Scene brought back into it would
    vanish without a word.
    """
    return PrimeItems.tasker_root_elements.setdefault(name, {})


def _old_table(older: Configuration, name: str) -> dict:
    """One table of the snapshot, or {}."""
    return (older.tables or {}).get(name) or {}


def _text(element: defusedxml.ElementTree.Element | None, tag: str) -> str:
    """A child's stripped text, or ""."""
    child = element.find(tag) if element is not None else None
    return (child.text or "").strip() if child is not None else ""


def _members(project: defusedxml.ElementTree.Element, tag: str) -> list[str]:
    """A Project's <pids>/<tids>/<scenes> as a list."""
    raw = _text(project, tag)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _live_owner(tag: str, key: str) -> str:
    """The first Project open now that lists this object, or ""."""
    return next(
        (name for name, entry in _live_table("all_projects").items() if key in _members(entry["xml"], tag)),
        "",
    )


def _live_target(kind: str, key: str) -> Target | None:
    """Where a click on this object's row goes, or None when it is not here to go to."""
    table, jump_kind, tag = _KINDS[kind]
    entry = _live_table(table).get(key)
    if entry is None:
        return None
    name = entry.get("name", "") or (key if kind == "Scene" else "")
    return Target(kind=jump_kind, key=key, name=name, project=_live_owner(tag, key))


def _old_owners(older: Configuration, kind: str, key: str) -> list[tuple[str, str]]:
    """(Project <id>, Project name) for every Project in the snapshot that listed this object."""
    _, _, tag = _KINDS[kind]
    return [
        (_text(entry["xml"], "id"), name)
        for name, entry in _old_table(older, "all_projects").items()
        if key in _members(entry["xml"], tag)
    ]


def _live_project_for(project_id: str, project_name: str) -> str:
    """The Project open now that IS the snapshot's Project, by name as the tables key it.

    Matched on <id> first, the way xmldiff matches Projects -- a Project renamed since is
    still the Project the object was in.  By name only when the snapshot's Project has no
    <id>, which a hand-made export can lack.  "" when it is not here at all.
    """
    projects = _live_table("all_projects")
    if project_id:
        for name, entry in projects.items():
            if _text(entry["xml"], "id") == project_id:
                return name
        return ""
    return project_name if project_name in projects else ""


def _perform_task_calls(task_name: str) -> int:
    """How many Perform Task actions in the configuration open now call this name."""
    if not task_name:
        return 0
    calls = 0
    for entry in _live_table("all_tasks").values():
        for action in entry["xml"].iter("Action"):
            if _text(action, "code") != _PERFORM_TASK_CODE:
                continue
            for argument in action.findall("Str"):
                if argument.attrib.get("sr") == _PERFORM_TASK_NAME_ARG and (argument.text or "").strip() == task_name:
                    calls += 1
    return calls


def _snapshot_profiles_running(older: Configuration, task_id: str) -> list[tuple[str, str, str]]:
    """(Profile id, Profile name, "Entry"/"Exit") for every snapshot Profile that ran this Task."""
    running = []
    for profile_id, entry in _old_table(older, "all_profiles").items():
        for tag, role in _TASK_LINKS:
            if _text(entry["xml"], tag) == task_id:
                running.append((profile_id, entry.get("name", "") or profile_id, role))
    return running


# ##################################################################################
# Writing elements that came from somewhere else.
# ##################################################################################


def _element_class() -> type:
    """The Element class the open configuration is built of.

    A snapshot is parsed by a second parse (diffload's), and an element appended into the
    live tree has to be of the live tree's own class -- the reason objprops'
    set_child_text_in_tag_order and editcommon.set_child_text both build children with
    type(parent) rather than whatever class came to hand.  Taken from the root when there is
    one, which there always is once a file is loaded.
    """
    root = PrimeItems.xml_root
    return type(root) if root is not None else ETW.Element


def _clone(source: defusedxml.ElementTree.Element, element_cls: type) -> defusedxml.ElementTree.Element:
    """A deep copy of `source` built entirely of `element_cls` elements.

    Not copy.deepcopy: that keeps the source's own class, and the source is the snapshot's.
    Text and tail are both carried so the restored object pretty-prints the way it did.
    """
    clone = element_cls(source.tag, dict(source.attrib))
    clone.text, clone.tail = source.text, source.tail
    for child in source:
        clone.append(_clone(child, element_cls))
    return clone


def _replace_contents(target: defusedxml.ElementTree.Element, source: defusedxml.ElementTree.Element) -> None:
    """Make `target` hold what `source` holds, in place, keeping its own sr and tail.

    IN PLACE, not by swapping a new element into the tables, and that is the decision this
    whole revert rests on.  The element the tables hold is the element the tree holds (see
    maputil2.render_full_backup_xml on why that identity is what a save reconciles by), and
    it is the element every open preview in every other dialog is holding too.  Changing
    what is inside it keeps all three pointing at the same object; swapping it would leave
    the tree holding a detached original and every other preview holding a stale one.

    `sr` is kept because it is a POSITION in the file (see xmldiff._canonical), not part of
    the object -- the snapshot's is where the object sat then.
    """
    sr, tail = target.attrib.get("sr"), target.tail
    target.clear()
    target.attrib.update(source.attrib)
    if sr is not None:
        target.set("sr", sr)
    target.text, target.tail = source.text, tail
    for child in list(source):
        target.append(child)


def _set_link(profile: defusedxml.ElementTree.Element, tag: str, task_id: str) -> None:
    """Point a Profile's <mid0>/<mid1> at a Task, or take the link away when `task_id` is ""."""
    existing = profile.find(tag)
    if not task_id:
        if existing is not None:
            profile.remove(existing)
        return
    _set_child_text(profile, tag, task_id)


# ##################################################################################
# A Profile's Task links, which are the one thing a restore cannot take on trust.
# ##################################################################################


@dataclass
class _Links:
    """What each of a restored Profile's Task links will point at, and what to say about it."""

    ids: dict[str, str] = field(default_factory=dict)  # "mid0"/"mid1" -> live Task id, "" to drop
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _resolve_links(older: Configuration, old_profile: defusedxml.ElementTree.Element) -> _Links:
    """Decide what each of a snapshot Profile's Task links becomes in the configuration now.

    A link is an id, and the id the snapshot holds names a Task in the snapshot.  Three
    outcomes, tried in order:

      THE ID IS HERE.  Kept.  If the Task has been renamed since, the step says so -- it is
      the same Task, and the Profile runs it under its new name.

      THE ID IS NOT, BUT THE NAME IS.  Relinked by name.  This is the case that matters
      most: bring back a deleted Task whose old id had been taken, and it comes back under
      a new one -- so the Profile brought back after it must find it by name, or it would
      come back pointing at whatever now holds the old id.

      NEITHER.  Dropped, and said so.  Bringing the Task back too would be restoring a
      second object, which is the merge this module does not do; the warning says which
      Task, so the user can bring it back first and then restore the Profile again.
    """
    links = _Links()
    old_tasks = _old_table(older, "all_tasks")
    live_tasks = _live_table("all_tasks")
    live_by_name = _live_table("all_tasks_by_name")

    for tag, role in _TASK_LINKS:
        old_id = _text(old_profile, tag)
        if not old_id:
            continue
        old_name = (old_tasks.get(old_id) or {}).get("name", "")

        relinked = live_by_name.get(old_name) if old_name else None
        # The id wins unless the name says otherwise.  A Task on its old id under another
        # name is the same Task renamed -- Tasker never reuses an id, and neither does
        # next_unique_task_or_profile_id -- EXCEPT when the old name is on a different Task
        # now, which is what a Task brought back under a new id looks like from here.
        if old_id in live_tasks and (relinked is None or relinked["id"] == old_id):
            links.ids[tag] = old_id
            live_name = live_tasks[old_id].get("name", "")
            if old_name and live_name and live_name != old_name:
                links.steps.append(f"Its {role} Task stays Task id {old_id}, which is now called '{live_name}'")
            continue

        if relinked is not None:
            links.ids[tag] = relinked["id"]
            links.steps.append(f"Link its {role} Task to '{old_name}', which is now id {relinked['id']}")
            continue

        links.ids[tag] = ""
        links.warnings.append(
            f"Its {role} Task, '{old_name or old_id}', is not in the configuration now, so the Profile comes "
            f"back without one.  Bring that Task back first, then restore this Profile again and the link "
            f"will be made.",
        )
    return links


# ##################################################################################
# Planning.
# ##################################################################################


def plan_restore(candidate: Candidate, older: Configuration, from_when: str) -> maprefac.Plan:
    """The maprefac.Plan for one candidate: what it would do, or why it will not.

    `from_when` is how the snapshot names itself in prose ("backup.xml, 15-Sep-2026
    14:29:18") -- the heading says where the old version comes from, because "restore
    Task 'Morning'" without "as it stood when" is the one thing the user has to be sure of.

    Built against the configuration as it stands NOW, not as it stood when the list was
    drawn: the list can sit on screen while another dialog edits, and every check below --
    is the id free, is the name taken, is the Project still here -- is only true for a
    moment.  maprefac.apply re-checks the elements this closes over for the same reason.
    """
    if candidate.kind not in _KINDS:
        return maprefac.Plan(
            kind=RESTORE,
            what=f"Restore {candidate.where}",
            blocks=[maprefac.Block("NOT-RESTORABLE", f"A {candidate.kind} cannot be restored from the history.")],
        )

    table, _, _ = _KINDS[candidate.kind]
    old_entry = _old_table(older, table).get(candidate.key)
    if old_entry is None:
        return maprefac.Plan(
            kind=RESTORE,
            what=f"Restore {candidate.where}",
            blocks=[maprefac.Block("NOT-IN-SNAPSHOT", "That object is not in the configuration history being read.")],
        )

    if candidate.action == BRING_BACK:
        planners = {"Task": _plan_bring_back_task, "Profile": _plan_bring_back_profile, "Scene": _plan_bring_back_scene}
    else:
        planners = {"Task": _plan_revert_named, "Profile": _plan_revert_named, "Scene": _plan_revert_scene}
    return planners[candidate.kind](candidate, older, old_entry, from_when)


def _restored_name(kind: str, wanted: str) -> tuple[str, str]:
    """(the name it can have, the warning if that is not the one it had).

    Duplicate's answer to a name somebody else holds: keep the name when it is free, and
    give it maprefac.unique_name's '(restored)' variant when it is not -- never a second
    object answering to the same name.
    """
    if not wanted:
        return wanted, ""
    taken = set(_live_table(_BY_NAME[kind])) if kind in _BY_NAME else set(_live_table("all_scenes"))
    if wanted not in taken:
        return wanted, ""
    new_name = maprefac.unique_name(wanted, taken, _RESTORED_SUFFIX)
    warning = f"Another {kind} is called '{wanted}' now, so this one comes back as '{new_name}'."
    if kind == "Task":
        warning += "  Every Perform Task that calls it by name still reaches the other one."
    return new_name, warning


def _restored_id(key: str, older: Configuration) -> tuple[str, str]:
    """(the id a brought-back Task or Profile gets, the step saying why if it is not its own).

    Its own when nothing holds it now -- the id Tasker on the device last knew it by, and
    below the device's counter, so the device will never hand it to something new.  Tasks
    and Profiles share one id space (see next_unique_task_or_profile_id), so "nothing" means
    neither table; a free id taken from the Profiles' side would be a collision the file
    only discovers when the device imports it.
    """
    in_use = set(_live_table("all_tasks")) | set(_live_table("all_profiles"))
    if key not in in_use:
        return key, ""
    # A new id steers clear of every id the SNAPSHOT uses as well as every one in use now.
    # Otherwise a Task brought back on a new id can be handed the very id a Profile deleted
    # alongside it still needs -- and that Profile, restored next, would lose its own id for
    # no reason but the order the two were restored in.
    reserved = set(_old_table(older, "all_tasks")) | set(_old_table(older, "all_profiles"))
    new_id = str(taskedit.next_unique_task_or_profile_id(reserved))
    return new_id, f"Its old id, {key}, belongs to something else now, so it comes back as id {new_id}"


def _owners_for(older: Configuration, candidate: Candidate) -> tuple[list[str], list[str]]:
    """(the Projects open now it goes back into, a warning for each that has gone)."""
    projects, warnings = [], []
    for project_id, project_name in _old_owners(older, candidate.kind, candidate.key):
        live = _live_project_for(project_id, project_name)
        if live:
            projects.append(live)
        else:
            warnings.append(
                f"It was in Project '{project_name}', which is not in the configuration now.  It comes back in no "
                f"Project, so it will not appear in the Map, the Diagram or the Tree until one lists it.",
            )
    return projects, warnings


def _into_projects(tag: str, key: str, projects: list[str]) -> None:
    """Add a restored object to each Project's membership list -- the write half of _owners_for."""
    for project_name in projects:
        entry = _live_table("all_projects").get(project_name)
        if entry is None:
            continue
        members = _members(entry["xml"], tag)
        if key not in members:
            projedit.set_project_members(entry["xml"], tag, [*members, key])


def _project_elements(projects: list[str]) -> tuple:
    """The live elements of the Projects a restore writes to, for maprefac.apply's check."""
    return tuple(_live_table("all_projects")[name]["xml"] for name in projects if name in _live_table("all_projects"))


def _project_steps(kind: str, projects: list[str]) -> list[maprefac.Step]:
    """One step per Project the restored object goes back into, each a link to that Project."""
    return [
        maprefac.Step(f"Add the {kind} back to Project '{name}'", Target(kind=PROJECT, key=name, name=name))
        for name in projects
    ]


def _plan_bring_back_task(
    candidate: Candidate,
    older: Configuration,
    old_entry: dict,
    from_when: str,
) -> maprefac.Plan:
    """Put a deleted Task back, as it stood in the snapshot, in the Projects that held it."""
    old_element = old_entry["xml"]
    old_name = _text(old_element, "nme")
    table_name = old_entry.get("name", "") or old_name or candidate.key
    new_id, id_step = _restored_id(candidate.key, older)
    new_name, name_warning = _restored_name("Task", old_name)
    shown = new_name or table_name
    projects, project_warnings = _owners_for(older, candidate)

    plan = maprefac.Plan(
        kind=RESTORE,
        what=f"Bring back Task '{table_name}' from {from_when}",
        elements=_project_elements(projects),
    )
    plan.steps = [
        maprefac.Step(f"Bring back Task '{shown}' with its {len(old_element.findall('Action'))} actions"),
        *([maprefac.Step(id_step)] if id_step else []),
        *_project_steps("Task", projects),
    ]
    plan.warnings = [w for w in (name_warning, *project_warnings) if w]

    # Said, not done: relinking a Profile is restoring a second object.
    for profile_id, profile_name, role in _snapshot_profiles_running(older, candidate.key):
        here = profile_id in _live_table("all_profiles")
        plan.warnings.append(
            f"Profile '{profile_name}' ran it as its {role} Task then, and is not relinked -- a restore brings "
            f"back one object.  "
            + (
                "Link it again from Edit Profile, or restore that Profile too."
                if here
                else "That Profile is not in the configuration either; restore it next and the link comes back with it."
            ),
        )
    calls = _perform_task_calls(new_name) if new_name == old_name else 0
    if calls:
        plan.warnings.append(
            f"{calls} Perform Task action{'s' if calls != 1 else ''} in the configuration call '{new_name}' by name "
            f"and will reach it again.",
        )

    def run() -> list[str]:
        element = _clone(old_element, _element_class())
        element.set("sr", f"task{new_id}")
        _set_child_text(element, "id", new_id)
        if new_name != old_name:
            _set_child_text(element, "nme", new_name)
        taskedit.register_new_task(taskedit.EditableTask(task_id=new_id, task_element=element), new_name or table_name)
        _into_projects("tids", new_id, projects)
        return []

    plan.run = run
    return plan


def _plan_bring_back_profile(
    candidate: Candidate,
    older: Configuration,
    old_entry: dict,
    from_when: str,
) -> maprefac.Plan:
    """Put a deleted Profile back, with whichever of its Tasks are still here to run."""
    old_element = old_entry["xml"]
    old_name = _text(old_element, "nme")
    table_name = old_entry.get("name", "") or old_name or candidate.key
    new_id, id_step = _restored_id(candidate.key, older)
    new_name, name_warning = _restored_name("Profile", old_name)
    links = _resolve_links(older, old_element)
    projects, project_warnings = _owners_for(older, candidate)

    plan = maprefac.Plan(
        kind=RESTORE,
        what=f"Bring back Profile '{table_name}' from {from_when}",
        elements=_project_elements(projects),
    )
    plan.steps = [
        maprefac.Step(f"Bring back Profile '{new_name or table_name}' with the conditions it had"),
        *([maprefac.Step(id_step)] if id_step else []),
        *(maprefac.Step(step) for step in links.steps),
        *_project_steps("Profile", projects),
    ]
    plan.warnings = [w for w in (name_warning, *links.warnings, *project_warnings) if w]
    if _text(old_element, "limit") != "true":
        plan.warnings.append(
            "It comes back enabled, as it was then -- it will start firing on the device as soon as this "
            "configuration is imported.",
        )

    def run() -> list[str]:
        element = _clone(old_element, _element_class())
        element.set("sr", f"prof{new_id}")
        _set_child_text(element, "id", new_id)
        if new_name != old_name:
            _set_child_text(element, "nme", new_name)
        for tag, task_id in links.ids.items():
            _set_link(element, tag, task_id)
        editable = profedit.EditableProfile(
            profile_id=new_id,
            profile_element=element,
            entry_task_id=links.ids.get("mid0", ""),
            exit_task_id=links.ids.get("mid1", ""),
        )
        profedit.register_new_profile(editable, new_name or table_name)
        _into_projects("pids", new_id, projects)
        return []

    plan.run = run
    return plan


def _plan_bring_back_scene(
    candidate: Candidate,
    older: Configuration,
    old_entry: dict,
    from_when: str,
) -> maprefac.Plan:
    """Put a deleted Scene back, under its own name or not at all.

    NOT renamed when its name is taken, unlike a Task or a Profile.  A Scene has no id: its
    name is its identity, and every Show Scene, every element action, and every Project's
    <scenes> list reaches it by that name -- so a Scene brought back as 'Menu (restored)'
    would be one nothing anywhere could show.  Blocked instead, and the block says what to
    rename first.
    """
    scene_name = candidate.key
    what = f"Bring back Scene '{scene_name}' from {from_when}"
    if scene_name in _live_table("all_scenes"):
        return maprefac.Plan(
            kind=RESTORE,
            what=what,
            blocks=[
                maprefac.Block(
                    "NAME-TAKEN",
                    f"A Scene called '{scene_name}' is in the configuration now.  A Scene is known by its name "
                    f"alone, so this one cannot come back beside it under another -- nothing would ever show "
                    f"it.  Rename the Scene that is here first, then restore this one.",
                    _live_target("Scene", scene_name),
                ),
            ],
        )

    old_element = old_entry["xml"]
    projects, project_warnings = _owners_for(older, candidate)
    missing = _missing_scene_tasks(old_element)

    plan = maprefac.Plan(kind=RESTORE, what=what, elements=_project_elements(projects))
    plan.steps = [
        maprefac.Step(f"Bring back Scene '{scene_name}' with its elements"),
        *_project_steps("Scene", projects),
    ]
    plan.warnings = list(project_warnings)
    if missing:
        plan.warnings.append(
            f"{missing} of its elements run a Task that is not in the configuration now.  Those elements come back "
            f"doing nothing when touched until the Task is brought back too.",
        )

    def run() -> list[str]:
        element = _clone(old_element, _element_class())
        _live_table("all_scenes")[scene_name] = {"xml": element, "name": scene_name}
        _into_projects("scenes", scene_name, projects)
        return []

    plan.run = run
    return plan


def _missing_scene_tasks(scene: defusedxml.ElementTree.Element) -> int:
    """How many of a Legacy Scene's element Task links name a Task id not here now.

    A Legacy element's <clickTask>, <longclickTask> and the rest hold a Task id; a negative
    one is the element's own inline anonymous Task, which travels inside the Scene and is
    never missing.  A Version 2 Scene names its Tasks inside a JSON layout, which is not
    read here -- the warning is what can be said for certain, not everything there is.
    """
    live = _live_table("all_tasks")
    return sum(
        1
        for node in scene.iter()
        if node.tag.endswith("Task") and (node.text or "").strip().isdigit() and (node.text or "").strip() not in live
    )


def _plan_revert_named(
    candidate: Candidate,
    older: Configuration,
    old_entry: dict,
    from_when: str,
) -> maprefac.Plan:
    """Put a Task or a Profile back as it stood in the snapshot, in place, under its own id."""
    kind = candidate.kind
    table, _, _ = _KINDS[kind]
    live_entry = _live_table(table).get(candidate.key)
    old_element = old_entry["xml"]
    current_name = (live_entry or {}).get("name", "") or candidate.key
    what = f"Put {kind} '{current_name}' back as it was on {from_when}"

    if live_entry is None:
        return maprefac.Plan(
            kind=RESTORE,
            what=what,
            blocks=[
                maprefac.Block(
                    "NOT-HERE",
                    f"That {kind} is no longer in the configuration -- it was deleted after this list was made.  "
                    f"Scan again and it will be offered to bring back instead.",
                ),
            ],
        )

    live_element = live_entry["xml"]
    old_name = _text(old_element, "nme")
    live_own_name = _text(live_element, "nme")
    # The old name, unless something else has it now -- in which case this keeps the name it
    # has, rather than taking a name another object answers to.
    by_name = _live_table(_BY_NAME[kind])
    holder = (by_name.get(old_name) or {}).get("id") if old_name else None
    keep_current_name = bool(old_name) and old_name != live_own_name and holder not in (None, candidate.key)
    final_name = live_own_name if keep_current_name else old_name

    plan = maprefac.Plan(kind=RESTORE, what=what, elements=(live_element,))
    plan.steps = [
        maprefac.Step(
            f"Put everything about {kind} '{current_name}' back as it stood then", _live_target(kind, candidate.key)
        ),
        *(maprefac.Step(f"    {detail}") for detail in candidate.details),
    ]
    plan.warnings = [_UNDONE_WHOLE]
    if keep_current_name:
        plan.warnings.append(
            f"It was called '{old_name}' then, but another {kind} is called that now, so it keeps the name "
            f"'{live_own_name}'.",
        )
    elif kind == "Task" and final_name != live_own_name:
        calls = _perform_task_calls(live_own_name)
        if calls:
            plan.warnings.append(
                f"It goes back to being called '{final_name}'.  {calls} Perform Task "
                f"action{'s' if calls != 1 else ''} call it as '{live_own_name}' and will reach nothing.",
            )

    links = _resolve_links(older, old_element) if kind == "Profile" else None
    if links is not None:
        plan.steps.extend(maprefac.Step(step) for step in links.steps)
        plan.warnings.extend(links.warnings)

    def run() -> list[str]:
        restored = _clone(old_element, type(live_element))
        _replace_contents(live_element, restored)
        _set_child_text(live_element, "id", candidate.key)
        if keep_current_name:
            _set_child_text(live_element, "nme", live_own_name)
        if links is not None:
            for tag, task_id in links.ids.items():
                _set_link(live_element, tag, task_id)
        _rename_in_tables(kind, candidate.key, live_element, current_name, final_name)
        return []

    plan.run = run
    return plan


def _rename_in_tables(kind: str, key: str, element: object, table_name: str, new_name: str) -> None:
    """Bring a reverted Task's or Profile's two tables into line with the name it now has.

    The by-name table is keyed by name, so a revert that changes the name has to move the
    entry -- and an object with no name of its own keeps the made-up display name the tables
    already give it (taskerd names an unnamed Task after its first action), since there is no
    name in the element to replace it with.
    """
    table, _, _ = _KINDS[kind]
    entry = _live_table(table)[key]
    shown = new_name or table_name
    entry["xml"] = element
    entry["name"] = shown
    by_name = _live_table(_BY_NAME[kind])
    if by_name.get(table_name, {}).get("id") == key and table_name != shown:
        del by_name[table_name]
    by_name[shown] = {"xml": element, "id": key}


def _plan_revert_scene(
    candidate: Candidate,
    _older: Configuration,  # The planners share one signature; a Scene revert has no links to resolve.
    old_entry: dict,
    from_when: str,
) -> maprefac.Plan:
    """Put a Scene back as it stood in the snapshot, in place.

    Never a rename: xmldiff matches Scenes by name, so a Scene on both sides has the same one
    on both, and there is nothing to put back but what is inside it.
    """
    live_entry = _live_table("all_scenes").get(candidate.key)
    what = f"Put Scene '{candidate.key}' back as it was on {from_when}"
    if live_entry is None:
        return maprefac.Plan(
            kind=RESTORE,
            what=what,
            blocks=[
                maprefac.Block(
                    "NOT-HERE",
                    "That Scene is no longer in the configuration -- it was deleted after this list was made.  "
                    "Scan again and it will be offered to bring back instead.",
                ),
            ],
        )

    live_element = live_entry["xml"]
    old_element = old_entry["xml"]
    plan = maprefac.Plan(kind=RESTORE, what=what, elements=(live_element,))
    plan.steps = [
        maprefac.Step(
            f"Put every element of Scene '{candidate.key}' back as it stood then", _live_target("Scene", candidate.key)
        ),
        *(maprefac.Step(f"    {detail}") for detail in candidate.details),
    ]
    plan.warnings = [_UNDONE_WHOLE]
    missing = _missing_scene_tasks(old_element)
    if missing:
        plan.warnings.append(
            f"{missing} of its elements, as they were then, run a Task that is not in the configuration now.",
        )

    def run() -> list[str]:
        _replace_contents(live_element, _clone(old_element, type(live_element)))
        return []

    plan.run = run
    return plan


def restore(plan: maprefac.Plan) -> tuple[bool, list[str]]:
    """Apply a restore.  maprefac.apply, under this module's name so the dialog reads right.

    Everything that makes apply() safe is maprefac's -- the blocks refused again, every
    element the plan closes over re-checked as still attached, the whole of it one undo
    labelled with the plan's own heading.  See its docstring; there is no second version.
    """
    return maprefac.apply(plan)
