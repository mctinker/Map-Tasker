"""projedit: build an editable model of a Project and apply Add/Rename/Enable/Delete to it.

Unlike a Profile or Task, a Project has no content of its own to author --
just a name, whether it is enabled (see is_project_enabled/set_project_enabled,
which read and write the <enbl> child Tasker marks a disabled Project with --
NOT the <limit> a Profile uses, and the opposite polarity), and the
Profiles/Tasks attached to it via <pids>/<tids> (see
profedit.add_profile_to_project/add_task_to_project) -- Add/Rename/Enable apply
straight to the live in-memory backup, same as every other in-app edit.

Delete needs its own care: a Project's <pids>/<tids> is the only place that
lists which Profiles/Tasks belong to it (getids.get_ids, and every view --
Map/Diagram/Tree -- walk exactly that to find them). delete_project lets the
caller choose between deleting the Project's contents too (cascade) or
keeping them by moving them into Tasker's default "Base" project (see
move_project_contents_to_base) -- either way, nothing is left orphaned.

Never touches PrimeItems.xml_tree -- edits happen on a deep copy (Add/Rename)
or directly on the live tasker_root_elements tables (Delete, same as every
other table mutation in profedit.py/taskedit.py), mirroring their design.

render_standalone_project_xml/write_standalone_project_xml don't add any new
editable field -- they just export a Project's existing Profiles (its <pids>)
plus every Task those Profiles actually use, as one standalone file, the way
Tasker's own Project export does -- see build_edit_project_dialog's "Export
Project" button. Note this is not simply the Project's own <tids>: a Profile's
Entry/Exit Task can be "owned" (per <tids>) by a completely different Project,
so render_standalone_project_xml resolves Tasks the same ownership-independent
way profiles.get_profile_tasks does for the Map/Diagram/Tree views -- see that
function's own comment for a real example from this repo's sample data.
save_project_to_android reuses the same render, writing the result onto the
device's storage under /Tasker/projects instead of locally -- see that
function's docstring, and profedit.save_profile_to_android which it mirrors,
for why this does not import into Tasker's live configuration.
"""

from __future__ import annotations

import copy
import os
import re
import time
import uuid
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import defusedxml.ElementTree

from maptasker.src import sessundo
from maptasker.src.presave import backup_local_file
from maptasker.src.primitem import PrimeItems

BASE_PROJECT_NAME = "Base"
# Destination folder on the Android device for Save To Android -- see android_project_path.
ANDROID_PROJECT_LOCATION = "Tasker/projects"
# A Project's identity children, which an export must carry.
#
# These used to be STRIPPED, on the belief that Tasker's own single-Project export leaves
# them out.  It does not, and the belief came from too small a sample: the derivation diffed
# four Tasker-produced .prj.xml files that happened to have no <id>, but eight of the
# eighteen in this repo's sample data do carry one (Ah Ah Ah, Custom Theme, EveryGesture,
# Flashlight Slider, Scene v2 Dialog, Smart Reminders, Strip Metadata, TAGLY).  The ones
# without are TaskerNet downloads, which strip identity on the way through the service --
# not what a device writes.
#
# Measured on a real device: Tasker REFUSES to import a Project with no <id>.  Every Project
# in a full backup has one (83 of 83), every Project this program creates has one
# (create_new_project mints a UUID), so there is nothing to gain by removing it and an
# import to lose.  <mdate> travels with it (83 of 83) and <clr>, the Project's UI tab
# colour, is kept when the Project has one (77 of 83 do; the rest simply have no colour set,
# which is not the same as needing one invented).
#
# Synthesized only when genuinely absent -- see _ensure_project_identity.
_PROJECT_IDENTITY_TAGS = ("id", "mdate")
# The child Tasker writes on a Project it has disabled, and the value that means it.
# Deliberately NOT the <limit>true</limit> a Profile uses -- different tag, and the
# opposite polarity (see is_project_enabled).
PROJECT_ENABLED_TAG = "enbl"
DISABLED_PROJECT_VALUE = "false"
_PROJECT_SR_RE = re.compile(r"^proj(\d+)$")


@dataclass
class EditableProject:
    """A deep-copied Project element plus the name it was loaded under (the
    live all_projects dict key -- may differ from the copy's own <name> text
    once the user has typed a new one but not yet applied it).
    """

    project_name: str
    project_element: defusedxml.ElementTree.Element


def resolve_project_by_name(project_name: str) -> defusedxml.ElementTree.Element | None:
    """Look up a Project's live XML element by its name (also its all_projects key).

    Callers must not mutate the returned element directly -- go through
    load_project_for_edit() instead.
    """
    entry = PrimeItems.tasker_root_elements.get("all_projects", {}).get(project_name)
    return None if entry is None else entry["xml"]


def load_project_for_edit(project_name: str) -> EditableProject | None:
    """Resolve a Project by name and deep-copy it -- the one point of contact
    with the live tree, so the in-memory backup is never touched until Rename
    is applied. Mirrors profedit.load_profile_for_edit.
    """
    live_element = resolve_project_by_name(project_name)
    if live_element is None:
        return None
    return EditableProject(project_name=project_name, project_element=copy.deepcopy(live_element))


def create_new_project(name: str) -> EditableProject | str:
    """Build a brand-new Project element, not tied to any existing one. Returns
    an error message string if no backup is loaded (needed to source the
    correct Element class -- see profedit.create_new_profile's identical note).
    all_projects is keyed by name, not by <id>, so the new element's own
    sr="projN" attribute (below) is a *separate*, internal-only counter for
    just that attribute -- unrelated to the <id> child this function also sets.

    <id> is a UUID, not a small integer -- matching every real Project in this
    repo's own sample backup, all 78 of which use UUIDs, never small integers
    (unlike Task/Profile, whose <id> is a shared-counter integer -- see
    taskedit.next_unique_task_or_profile_id). This isn't just fidelity to
    Tasker's own format: it's what makes a new Project's <id> unconditionally
    collision-free against every Task/Profile <id> too, since a UUID string can
    never equal a small integer's string form.

    Sets <cdate> and <mdate> to the same creation timestamp -- real Tasker
    Projects use <mdate> for their last-modified time, not <edate> the way
    Task/Profile do (confirmed against this repo's own sample backup: every
    Project has <cdate>+<mdate>, none has <edate>) -- see _touch_mdate, called
    by every function that mutates a Project afterward, for how it's kept current.
    """
    if PrimeItems.xml_root is None:
        return "Load a Tasker backup file first (Add Project needs it to generate a unique Project ID)."

    existing_sr_ids = [
        int(match.group(1))
        for entry in PrimeItems.tasker_root_elements.get("all_projects", {}).values()
        if (match := _PROJECT_SR_RE.match(entry["xml"].attrib.get("sr", "")))
    ]
    new_sr_id = max(existing_sr_ids, default=0) + 1

    element_cls = type(PrimeItems.xml_root)
    project_element = element_cls("Project", {"sr": f"proj{new_sr_id}", "ve": "2"})

    now_millis = str(int(time.time() * 1000))
    for tag, text in (
        ("cdate", now_millis),
        ("id", str(uuid.uuid4())),
        ("mdate", now_millis),
        ("name", name.strip()),
    ):
        child = element_cls(tag)
        child.text = text
        project_element.append(child)

    return EditableProject(project_name=name.strip(), project_element=project_element)


def project_name_exists(name: str) -> bool:
    """Whether a Project with this name already exists in the currently loaded backup."""
    return name.strip() in PrimeItems.tasker_root_elements.get("all_projects", {})


def apply_edits_to_project(edited_project: EditableProject, new_name: str) -> list[str]:
    """Validate the new name, and only if valid, mutate the Project copy's
    <name> child. All-or-nothing, mirrors profedit.apply_edits_to_profile's
    shape but with a single field.

    A no-op rename (new_name == edited_project.project_name) is allowed
    through -- it's not a conflict with itself.
    """
    errors = []

    new_name = new_name.strip()
    if not new_name:
        errors.append("Project name cannot be empty.")
    elif new_name != edited_project.project_name and project_name_exists(new_name):
        errors.append(f"A Project named '{new_name}' already exists in this backup. Choose a different name.")

    if errors:
        return errors

    _set_child_text(edited_project.project_element, "name", new_name)
    touch_project_mdate(edited_project.project_element)
    # Keep project_name in sync with the applied <name> -- register_new_project
    # keys all_projects by it, so a brand-new Project (created with name "")
    # would otherwise be registered under "" and show up nameless in the
    # Project pulldown.
    edited_project.project_name = new_name
    return []


def _set_child_text(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    child = parent.find(tag)
    if child is None:
        # Match parent's actual Element class (see create_new_project) --
        # ETW.SubElement() would build a stdlib-class child and fail parent.append().
        child = type(parent)(tag)
        parent.append(child)
    child.text = text


def _set_child_text_in_tag_order(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    """_set_child_text, but a child being created for the first time is inserted in
    Tasker's own child order instead of appended.

    A Project's lowercase children run strictly alphabetically in every backup --
    all 876 Project elements across this repo's 42 sample XML files, without
    exception (cdate, clr, enbl, id, mdate, name, pc, pids, scenes, tids) -- with
    the uppercase-tagged ones (Img, Kid, Share, ProfileVariable) after them all.
    So the insertion point is the first sibling that either sorts after this tag or
    is one of those uppercase children; appending only happens when there is
    neither.

    Same reasoning as render_standalone_project_xml's pids-before-tids fix-up: what
    is exported has to look like what Tasker writes.  Existing children are left
    where they are -- only the text is updated -- since anything already in the
    element is already in Tasker's order.
    """
    child = parent.find(tag)
    if child is None:
        # Match parent's actual Element class -- see _set_child_text's identical note.
        child = type(parent)(tag)
        position = next(
            (index for index, sibling in enumerate(parent) if not sibling.tag.islower() or sibling.tag > tag),
            len(parent),
        )
        parent.insert(position, child)
    child.text = text


def touch_project_mdate(project_element: defusedxml.ElementTree.Element) -> None:
    """Stamps a Project's <mdate> with the current time -- real Tasker Projects
    use <mdate> for "last modified", not <edate> the way Task/Profile do (see
    create_new_project's docstring for the confirmation). Call this from
    anything that mutates an already-registered Project's element:
    apply_edits_to_project (Rename), and profedit.add_profile_to_project/
    add_task_to_project (Add Profile/Add Task attaching to this Project) --
    imported there rather than duplicated the way _set_child_text is per-module,
    since unlike that one-line body, "how the timestamp is formatted" is worth
    keeping in one place.
    """
    _set_child_text(project_element, "mdate", str(int(time.time() * 1000)))


def register_new_project(edited_project: EditableProject) -> None:
    """Adds a new Project to the in-memory backup's all_projects table so it
    behaves like any other Project loaded from the backup -- e.g. so it shows
    up in the Project pulldown and so a second Add Project with the same name
    is caught by project_name_exists(). Call once, right after a successful
    Add Project (see userintr.keep_new_project_event) -- there's no
    standalone-file/Save-To-Android path to also call this from, unlike
    profedit.register_new_profile/taskedit.register_new_task.
    """
    with sessundo.undoable(f"Add Project '{edited_project.project_name}'"):
        PrimeItems.tasker_root_elements.setdefault("all_projects", {})[edited_project.project_name] = {
            "xml": edited_project.project_element,
            "name": edited_project.project_name,
        }


def is_project_enabled(edited_project: EditableProject) -> bool:
    """Whether this Project is enabled -- reads its <enbl> child: "false" means
    disabled, and the tag's absence (or any other value, "true" included) means
    enabled.

    Note this is the INVERSE of how a Profile records the same thing, and a
    different tag: a Profile is disabled by the PRESENCE of <limit>true</limit>
    (profedit.is_profile_enabled, profiles.build_profile_line), whereas a Project
    is disabled by an <enbl> that says false.  Neither tag appears on the other
    kind of element, so the polarity is per-tag, not something to normalize away.

    Matching what Tasker itself writes: across this repo's 42 sample XML files,
    exactly one of 876 Project elements carries <enbl> at all -- backup.xml's
    disabled "Test", carrying "false" -- so Tasker emits the tag only for a
    Project it has disabled, which is why absence has to read as enabled.

    projects.get_extra_and_output_project reads the same tag its own way to put
    the '[DISABLED]' marker on a disabled Project's Map view line -- the same
    split profiles.build_profile_line and profedit.is_profile_enabled have for a
    Profile's <limit>.  Change the tag or its polarity here and that reader has
    to change with it.
    """
    enbl = edited_project.project_element.find(PROJECT_ENABLED_TAG)
    return enbl is None or enbl.text != DISABLED_PROJECT_VALUE


def set_project_enabled(edited_project: EditableProject, enabled: bool) -> None:
    """Enables or disables the Project by removing/setting its <enbl>false</enbl>
    child -- the Project counterpart of profedit.set_profile_enabled, though the
    tag and its polarity differ (see is_project_enabled).

    Enabling REMOVES the tag rather than writing <enbl>true</enbl>.  Both read as
    enabled, but absence is what Tasker's own backups show for an enabled Project
    (875 of 876 sample Project elements have no <enbl>), so a Project toggled off
    and back on ends up byte-identical to one that was never touched, instead of
    carrying a tag no Tasker-produced file would have there.

    Unlike its Profile counterpart, this writes through to the LIVE Project
    element as well as the edited copy, and does it the moment the toggle is
    flipped rather than at save time.  Both of Edit Project's saves render from
    the live tree by name (write_standalone_project_xml/save_project_to_android
    take project_name, not this copy -- see guiwins.EDIT_PROJECT_INERT_FIELDS and
    userintr._unapplied_project_edits for the trap that creates), and "Save To
    Current File" writes the whole live backup, so a disable left on the copy
    alone would be missing from all three.  Applying immediately also matches
    what the rest of this dialog already does: Rename and Delete both hit the
    live tree as soon as they are confirmed.

    The copy is still updated so is_project_enabled -- which reads it -- keeps
    reporting what the switch shows.  After a Rename the two are the same object
    (rename_project_in_live_tree registers the copy as the live element), which
    is why this is written to be idempotent rather than assuming two distinct
    elements.

    A brand-new Project that has not been registered yet (Add Project) has no
    live element to write to; only its copy is updated, and register_new_project
    carries the <enbl> in with it.
    """
    elements = [edited_project.project_element]
    live_element = resolve_project_by_name(edited_project.project_name)
    if live_element is not None and live_element is not edited_project.project_element:
        elements.append(live_element)

    for element in elements:
        if enabled:
            enbl = element.find(PROJECT_ENABLED_TAG)
            if enbl is not None:
                element.remove(enbl)
        else:
            _set_child_text_in_tag_order(element, PROJECT_ENABLED_TAG, DISABLED_PROJECT_VALUE)
        touch_project_mdate(element)


def rename_project_in_live_tree(old_name: str, edited_project: EditableProject) -> None:
    """Writes an edited (pre-existing) Project's new name back into the
    in-memory backup's all_projects table. Unlike
    profedit.apply_edited_profile_to_live_tree's id-keyed object swap, a
    Project's identity *is* its all_projects key (see taskerd.py's
    move_xml_to_table(..., get_id=False, "name")), so this has to move the
    dict entry to the new key, not just update a field in place.

    No-op if old_name isn't registered (defense in depth; the GUI should only
    ever pass a name that was just loaded via load_project_for_edit).
    """
    with sessundo.undoable(f"Rename Project '{old_name}'"):
        all_projects = PrimeItems.tasker_root_elements.get("all_projects", {})
        if old_name not in all_projects:
            return

        new_name = edited_project.project_element.findtext("name", "") or old_name
        del all_projects[old_name]
        all_projects[new_name] = {"xml": edited_project.project_element, "name": new_name}


def _project_child_ids(project_element: defusedxml.ElementTree.Element, tag: str) -> list[str]:
    """Reads a Project's <pids> or <tids> as a list of id strings, empty-safe."""
    child = project_element.find(tag)
    return child.text.split(",") if child is not None and child.text else []


def project_profile_names(project_name: str) -> list[str]:
    """The names of the Profiles this Project owns, read off its live <pids>.

    For confirming a Project import.  Tasker's HTTP API has no /api/projects -- it can
    report Profiles, Tasks, Scenes and Globals by name and nothing else -- so 'did the
    Project arrive' cannot be asked directly.  What it brings with it can be: a Project
    export bundles its Profiles (see render_standalone_project_xml), so those names are the
    question that stands in for the one the API will not answer.  See
    deviceinv.offer_to_tasker, which takes exactly this list.

    Read off each Profile's own <nme>, NOT off the all_profiles table's "name" -- that one
    holds a name MAPTASKER made up for an unnamed Profile, built from its conditions
    ('*Display Off.25 Unnamed'; see taskerd.build_tasker_tables and
    profiles.conditions_to_name).  39 of the 293 Profiles in this repo's own sample backup
    have one.  Tasker will never report a Profile by a name it has never heard of, so
    including them would make every Project that owns an unnamed Profile time out waiting
    for something that cannot arrive.  An unnamed Profile is simply not confirmable, and
    leaving it out is what lets the rest of the Project still be.

    Ids with no Profile behind them are dropped for a related reason -- a dangling id in
    <pids> means the Project references a Profile this backup does not have, so an import
    would not bring it either.
    """
    live_element = resolve_project_by_name(project_name)
    if live_element is None:
        return []

    all_profiles = PrimeItems.tasker_root_elements.get("all_profiles", {})
    names = []
    for profile_id in _project_child_ids(live_element, "pids"):
        entry = all_profiles.get(profile_id.strip())
        if not isinstance(entry, dict) or entry.get("xml") is None:
            continue
        name = (entry["xml"].findtext("nme") or "").strip()
        if name:
            names.append(name)
    return names


def count_project_contents(project_name: str) -> tuple[int, int]:
    """Returns (Profile count, Task count) currently owned by this Project --
    for the Delete confirmation dialog's "it owns N Profile(s) and M Task(s)"
    message, read straight off the live <pids>/<tids> before anything is mutated.
    """
    live_element = resolve_project_by_name(project_name)
    if live_element is None:
        return 0, 0
    return len(_project_child_ids(live_element, "pids")), len(_project_child_ids(live_element, "tids"))


def sanitize_filename(name: str) -> str:
    """Strip characters illegal in filenames from a Project name (minimal, not a full slugify).

    Mirrors profedit.sanitize_filename/taskedit.sanitize_filename exactly -- kept as its own
    copy rather than a shared import since each already stands alone with its own
    type-appropriate fallback ("project" here vs. "profile"/"task").
    """
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "project"


def default_project_save_path(project_name: str) -> str:
    """Default standalone-export path: {current runtime directory}/{sanitized name}.prj.xml."""
    return os.path.join(os.getcwd(), f"{sanitize_filename(project_name)}.prj.xml")


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten).
    Mirrors profedit.save_path_exists/taskedit.save_path_exists.
    """
    return bool(output_path) and os.path.exists(output_path)


def android_project_path(project_name: str) -> str:
    """The absolute path a Save To Android of this Project would write to on the
    device. Single source of truth for that path -- save_project_to_android
    writes here, and the GUI's overwrite check reads it back through
    maputil2.read_android_file, so the two must never drift apart.

    Note the path is derived from the *sanitized* name, so two differently-named
    Projects can map to the same file (e.g. "Home/Work" and "Home_Work" both
    become "Home_Work.prj.xml"), and a name that is empty or entirely illegal
    characters falls back to "project.prj.xml" -- the overwrite prompt this
    feeds is the only thing standing between those collisions and silent data
    loss, since /upload itself reports success either way.
    """
    return f"/{ANDROID_PROJECT_LOCATION}/{sanitize_filename(project_name)}.prj.xml"


# The device screen size an export was written on, as "width,height" floats -- Tasker's own
# top-level <dmetric>.  It is Scene metadata: Scene elements are laid out in device pixels,
# so an importing device needs to know what screen those pixels were measured on.
#
# That is not a guess.  Across the eighteen sample .prj.xml files in this repo the
# correlation is exact and has no exceptions: all eleven that contain <Scene> elements carry
# a <dmetric>, and all seven that contain none carry none.  It shows up in .scn.xml exports
# too (3 of 5) and in NO .prf.xml or .tsk.xml export at all -- which is why the Profile
# import never needed one.
#
# Copied from the loaded backup rather than invented.  The right value is the screen the
# Scenes were actually laid out on, which is the device the backup came from, and that is
# exactly what its own <dmetric> holds.  A backup without one exports without one -- making
# up a screen size would be worse than saying nothing, since Tasker would scale Scenes to a
# device that never existed.
#
# Written only when the export actually carries Scenes, because that is what Tasker does.
# The correlation is not confounded by anything else in the sample: <id> presence cuts
# across it in both directions (EveryGesture and Strip Metadata have an <id> and no
# <dmetric>; Chat_GPT, Scan and Pocc have a <dmetric> and no <id>), so this is a real rule
# about Scenes rather than a side effect of which files came from a device and which from
# TaskerNet.  A Project with no Scenes that still needs one would be new evidence.
_DISPLAY_METRIC_TAG = "dmetric"


def _project_scene_names(project_element: defusedxml.ElementTree.Element) -> list[str]:
    """The Scenes this Project owns, by name, from its <scenes> child.

    Scenes are referenced by NAME here, unlike Profiles and Tasks, which <pids>/<tids>
    reference by id -- see all_scenes, which taskerd keys by name for the same reason.
    """
    child = project_element.find("scenes")
    return [name.strip() for name in child.text.split(",")] if child is not None and child.text else []


def _ensure_project_identity(project_copy: defusedxml.ElementTree.Element) -> None:
    """Give the copy an <id> and an <mdate> if it has none, in place.

    A safety net, not the normal path: every Project in a real backup has both, and
    create_new_project mints both.  It exists because the failure it prevents is silent and
    total -- Tasker refuses the whole import of a Project with no <id>, and the file looks
    perfectly well-formed from this end.

    Inserted in alphabetical position among the Project's simple metadata children (cdate,
    clr, enbl, id, mdate, name, pc, pids, scenes, tids), which is the order real Tasker
    Projects use and the order the pids-before-tids fix-up below already assumes.  Appending
    instead would put them after <Share>/<Img>/<ProfileVariable>, which no Tasker-written
    Project does.

    The <id> is a UUID, matching create_new_project and every real Project -- see that
    function for why a UUID rather than the small integer a Task or Profile uses.
    """
    for tag in _PROJECT_IDENTITY_TAGS:
        if project_copy.find(tag) is not None:
            continue
        child = type(project_copy)(tag)
        child.text = str(uuid.uuid4()) if tag == "id" else str(int(time.time() * 1000))
        # The first simple child that sorts after this one is where it goes.  A child whose
        # tag starts upper-case is a compound element (Share, Img, ProfileVariable, Kid) and
        # is never a candidate -- landing before one of those is right, landing after them
        # is what appending would do.  With no later simple child, it goes just past the
        # last one, which still keeps it ahead of the compound elements.
        simple = [index for index, existing in enumerate(project_copy) if existing.tag[:1].islower()]
        later = [index for index in simple if project_copy[index].tag > tag]
        project_copy.insert(later[0] if later else (simple[-1] + 1 if simple else 0), child)


def render_standalone_project_xml(project_name: str) -> str:
    """Render a Project as a standalone TaskerData XML string, in the order Tasker's own
    single-Project export uses: <dmetric>, every Profile the Project owns, the Project
    element itself, every Scene it owns, then every Task those Profiles use.  Mirrors
    profedit.render_standalone_profile_xml's TaskerData-wrapping approach, just scoped to a
    whole Project's contents instead of one Profile's linked Entry/Exit Task(s).

    Tasks come from three places: the Project's own <tids>, its Profiles' Entry/Exit
    <mid0>/<mid1>, and the handlers on its Scenes' elements (see _scene_task_ids) -- that
    last one reachable from nothing else, so a Scene exported without it imports with dead
    buttons.

    Deliberately does NOT recurse into Tasks a bundled Task calls via "Perform Task".

    Raises ValueError if project_name isn't a currently-loaded Project.
    """
    project_entry = PrimeItems.tasker_root_elements.get("all_projects", {}).get(project_name)
    if project_entry is None:
        msg = f"Project '{project_name}' no longer exists in this backup."
        raise ValueError(msg)

    project_element = project_entry["xml"]
    tv = PrimeItems.xml_root.attrib.get("tv", "") if PrimeItems.xml_root is not None else ""
    project_copy = copy.deepcopy(project_element)
    # <id>, <mdate> and <clr> come through untouched -- Tasker will not import a Project
    # without an <id>, and this used to remove one.  See _PROJECT_IDENTITY_TAGS.  Safe to
    # mutate project_copy below because it is a deep copy; the pids/tids reads go through
    # project_element (the live one) regardless.
    _ensure_project_identity(project_copy)

    # Renumber the Project to sr="proj0". The sr attribute is a per-document 0-based
    # serial index, not a stable identity: backup.xml's 78 Projects carry exactly
    # proj0..proj77, and every Tasker-produced .prj.xml in this repo's sample data uses
    # proj0 -- all six of them -- because a standalone export holds exactly one Project,
    # which is therefore index 0.
    #
    # Without this the export inherits whatever index the Project happened to hold in
    # the backup it came from (create_new_project hands a brand-new Project max+1, so a
    # Project added to a 78-Project backup gets proj78). Tasker's importer then looks for
    # the Project at index 0, finds nothing there, and fails the whole import with
    # "no Project found" -- the Project element is plainly present in the file, just
    # filed under an index that only meant anything inside its original backup.
    #
    # Only the Project is renumbered: genuine exports keep their Profiles' and Tasks'
    # original sr values (e.g. Chat_GPT.prj.xml ships prof590 and task242, not prof0/
    # task0), since those are resolved by <id> through <pids>/<tids> rather than by index.
    project_copy.set("sr", "proj0")

    # Emit <pids> before <tids>, the order real Tasker Projects use (their simple
    # metadata children run alphabetically: cdate, clr, id, mdate, name, pids, scenes,
    # tids -- so pids naturally precedes tids in every backup-sourced Project).
    #
    # A Project built in-app can end up the other way round: <tids> and <pids> are
    # created lazily by profedit.add_task_to_project/add_profile_to_project, each
    # appending its element the first time it is needed, so adding a Task before a
    # Profile leaves tids first and the export inherits that order. Normalizing here
    # rather than at creation time keeps this a property of the exported document,
    # which is what has to match Tasker's format -- and costs nothing when the order
    # is already right, which it is for every Project read from a backup.
    pids_element = project_copy.find("pids")
    tids_element = project_copy.find("tids")
    if pids_element is not None and tids_element is not None:
        children = list(project_copy)
        if children.index(pids_element) > children.index(tids_element):
            project_copy.remove(pids_element)
            project_copy.insert(list(project_copy).index(tids_element), pids_element)

    # Match the parsed tree's actual Element class (see profedit.render_standalone_profile_xml's
    # identical note) -- defusedxml's hardened parser isn't necessarily xml.etree's own
    # C-accelerated Element, and ET.Element()/.append() enforce an exact type match.
    element_cls = type(project_copy)
    root = element_cls("TaskerData", {"sr": "", "dvi": "1", "tv": tv})

    # The Scenes are gathered before anything is appended, because whether there are any
    # decides whether <dmetric> is written -- and <dmetric> has to go first.
    all_scenes = PrimeItems.tasker_root_elements.get("all_scenes", {})
    scene_elements = [
        copy.deepcopy(all_scenes[scene_name]["xml"])
        for scene_name in _project_scene_names(project_element)
        # Missing ones are skipped rather than faked, the same way a dangling <pids> id is.
        if scene_name in all_scenes
    ]

    # <dmetric> first, exactly where Tasker puts it (Scan.prj.xml, Custom Theme.prj.xml and
    # backup.xml all lead with it), and only alongside Scenes -- see _DISPLAY_METRIC_TAG for
    # the measured correlation and for why the value is copied rather than invented.
    source_metric = PrimeItems.xml_root.find(_DISPLAY_METRIC_TAG) if PrimeItems.xml_root is not None else None
    if scene_elements and source_metric is not None:
        root.append(copy.deepcopy(source_metric))

    # Element order matters here -- matched against this repo's own sample .prj.xml files
    # (Tasker's actual single-Project export format): <dmetric>, then every Profile, then
    # the Project element itself, then every Scene, then every Task -- not Project-first,
    # which is what you'd expect from <pids>/<tids> being *inside* <Project>.
    all_profiles = PrimeItems.tasker_root_elements.get("all_profiles", {})
    profile_ids = _project_child_ids(project_element, "pids")
    for profile_id in profile_ids:
        profile_entry = all_profiles.get(profile_id)
        if profile_entry is not None:
            root.append(copy.deepcopy(profile_entry["xml"]))

    root.append(project_copy)

    # The Scenes the Project owns, gathered above.  Without these the exported <scenes>
    # names Scenes that are not in the file -- 'Base' in this repo's own backup declares
    # four of them and shipped none -- and an import has nothing to resolve them against.
    root.extend(scene_elements)

    all_tasks = PrimeItems.tasker_root_elements.get("all_tasks", {})
    # A Project's own <tids> only lists Tasks created *directly* inside it (no attached
    # Profile) -- a Profile's Entry/Exit Task (<mid0>/<mid1>) is looked up globally by id
    # and can belong to a completely different Project's own <tids>.  Confirmed against a
    # real backup: a Profile owned by "Test" here had Entry Tasks whose own <tids>
    # membership was "Base" and "Adaptive Brightness Quick Setting".  Restricting to the
    # Project's own <tids> (the old behavior) silently dropped every such Task from the
    # export -- see profiles.get_profile_tasks, which resolves mid0/mid1 the same
    # ownership-independent way for the Map/Diagram/Tree views.
    task_ids = list(_project_child_ids(project_element, "tids"))
    seen_task_ids = set(task_ids)
    for profile_id in profile_ids:
        profile_entry = all_profiles.get(profile_id)
        if profile_entry is None:
            continue
        for child in profile_entry["xml"]:
            if "mid" in child.tag and child.text and child.text not in seen_task_ids:
                seen_task_ids.add(child.text)
                task_ids.append(child.text)

    # And the Tasks the Project's Scenes fire.  A Scene button's Task is reached from
    # neither <tids> nor a Profile's <mid0>/<mid1> -- nothing links to it but the Scene
    # element itself -- so without this the Scene imports and its buttons do nothing.  The
    # walk lives in sceneedit (sceneedit.scene_task_ids) because it is a fact about Scenes,
    # and the standalone Scene export needs exactly the same thing.  Last,
    # after the two id sources above, so a Task that is already coming keeps its place
    # rather than being re-ordered by which Scene happens to mention it.
    # Lazily imported: sceneedit imports touch_project_mdate from here, so the cycle is
    # real -- same shape as taskedit reaching back into maputil2.
    from maptasker.src.sceneedit import scene_task_ids  # noqa: PLC0415

    for scene_element in scene_elements:
        for task_id in scene_task_ids(scene_element):
            if task_id not in seen_task_ids:
                seen_task_ids.add(task_id)
                task_ids.append(task_id)

    for task_id in task_ids:
        task_entry = all_tasks.get(task_id)
        if task_entry is not None:
            root.append(copy.deepcopy(task_entry["xml"]))

    ETW.indent(root, space="\t")
    # No <?xml ...?> declaration -- see profedit.render_standalone_profile_xml.
    return ETW.tostring(root, encoding="unicode") + "\n"


def write_standalone_project_xml(project_name: str, output_path: str) -> str:
    """Write a Project (plus every Profile/Task it owns) as a standalone XML
    file. Raises OSError on failure, ValueError if the Project no longer exists.

    A safety copy of anything already at `output_path` is taken first, into a
    MapTasker_Backups folder beside it -- see presave.backup_local_file.  Taken here
    rather than at the buttons that call this, so no export path can be added later that
    quietly skips it.  Returns the copy's path, or "" if there was nothing to copy or the
    copy failed (which does not stop the write -- see presave's module comment).
    """
    rendered = render_standalone_project_xml(project_name)
    _, safety_copy = backup_local_file(output_path)
    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(rendered)
    return safety_copy


def save_project_to_android(project_name: str, ip_address: str, ip_port: str) -> tuple[int, str]:
    """Writes the Project -- every Profile and Task it owns -- onto the Android
    device's storage under /Tasker/projects, via the same POST /upload mechanism
    as profedit.save_profile_to_android (see that function's docstring for why a
    readback-verify is required, and why this does not touch Tasker's live
    configuration). Mirrors it exactly, except a Project has no separate "edited"
    model to render from -- render_standalone_project_xml reads the live
    all_projects/all_profiles/all_tasks tables directly by name, same as
    write_standalone_project_xml (the local-file "Export Project" button).

    Returns (0, device_file_path) on success, or (return_code, error_message).
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from maptasker.src.maputil2 import http_upload_request, read_back_uploaded_file  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "Android IP address and port are required."

    try:
        xml_bytes = render_standalone_project_xml(project_name).encode("utf-8")
    except ValueError as e:
        return 8, str(e)

    device_path = android_project_path(project_name)
    filename = device_path.rsplit("/", 1)[-1]

    return_code, response = http_upload_request(ip_address, ip_port, ANDROID_PROJECT_LOCATION, filename, xml_bytes)
    if return_code != 0:
        return return_code, str(response)

    # Retried rather than trusted: /upload is a Tasker Task writing to storage and this read
    # is a second request answered by a second Task, so a write still settling answers 404 to
    # a read that arrives too soon -- and failing on the first miss aborts a save whose file
    # is on the device a moment later.  See maputil2.read_back_uploaded_file.
    verify_code, verify_content = read_back_uploaded_file(ip_address, ip_port, device_path, xml_bytes)
    if verify_code != 0:
        return 8, str(verify_content)

    return 0, device_path


def delete_profiles_and_tasks_of_project(project_name: str) -> None:
    """Deletes every Profile/Task this Project owns (per its live <pids>/<tids>)
    from the in-memory backup's lookup tables -- the "Delete Contents" half of
    delete_project. First delete-a-Profile/Task primitive in the app; scoped
    to this cascade only, not exposed as a standalone button.
    """
    with sessundo.undoable(f"Delete the contents of Project '{project_name}'"):
        live_element = resolve_project_by_name(project_name)
        if live_element is None:
            return

        all_profiles = PrimeItems.tasker_root_elements.get("all_profiles", {})
        all_profiles_by_name = PrimeItems.tasker_root_elements.get("all_profiles_by_name", {})
        for profile_id in _project_child_ids(live_element, "pids"):
            entry = all_profiles.pop(profile_id, None)
            if entry is not None:
                all_profiles_by_name.pop(entry["name"], None)

        all_tasks = PrimeItems.tasker_root_elements.get("all_tasks", {})
        all_tasks_by_name = PrimeItems.tasker_root_elements.get("all_tasks_by_name", {})
        for task_id in _project_child_ids(live_element, "tids"):
            entry = all_tasks.pop(task_id, None)
            if entry is not None:
                all_tasks_by_name.pop(entry["name"], None)


def move_project_contents_to_base(project_name: str) -> str:
    """Moves this Project's Profiles/Tasks into Tasker's default "Base"
    Project -- the "Keep Contents" half of delete_project. Creates a "Base"
    Project on the fly if this backup doesn't already have one (not
    guaranteed -- a backup can be exported without it). Returns the resolved
    target name ("Base") for the caller's confirmation toast.

    Same append-dedup <pids>/<tids> logic as
    profedit.add_profile_to_project/add_task_to_project, just batched over a
    list of already-registered ids instead of one newly-created one -- the
    Profiles/Tasks themselves aren't touched, only which Project references them.
    """
    all_projects = PrimeItems.tasker_root_elements.setdefault("all_projects", {})
    if BASE_PROJECT_NAME not in all_projects:
        base_project = create_new_project(BASE_PROJECT_NAME)
        if isinstance(base_project, str):
            # No backup loaded -- can't happen in practice (a Project to delete
            # implies one is), but keeps this function total.
            return BASE_PROJECT_NAME
        register_new_project(base_project)

    live_element = resolve_project_by_name(project_name)
    base_element = all_projects[BASE_PROJECT_NAME]["xml"]

    for tag in ("pids", "tids"):
        moving_ids = _project_child_ids(live_element, tag) if live_element is not None else []
        if not moving_ids:
            continue
        existing_ids = _project_child_ids(base_element, tag)
        for moving_id in moving_ids:
            if moving_id not in existing_ids:
                existing_ids.append(moving_id)
        _set_child_text(base_element, tag, ",".join(existing_ids))

    return BASE_PROJECT_NAME


def delete_project(project_name: str, *, keep_contents: bool) -> list[str]:
    """Deletes a Project, either moving its contents into "Base" (keep_contents)
    or deleting them too (cascade) -- see move_project_contents_to_base /
    delete_profiles_and_tasks_of_project. Returns [] on success, else a list
    of error strings (mirrors apply_edits_to_project's convention), and
    mutates nothing on error.

    Guards against deleting "Base" itself with keep_contents=True: the target
    and source would be the same Project, so there's nothing meaningful to
    move -- Base can only be deleted with its contents (or renamed first).
    """
    with sessundo.undoable(f"Delete Project '{project_name}'"):
        if project_name == BASE_PROJECT_NAME and keep_contents:
            return [
                f"'{BASE_PROJECT_NAME}' can't be deleted with 'Keep Contents' -- "
                f"there's no other default Project to move its contents into. "
                f"Use 'Delete Contents', or rename it first.",
            ]

        all_projects = PrimeItems.tasker_root_elements.get("all_projects", {})
        if project_name not in all_projects:
            return [f"Project '{project_name}' no longer exists."]

        if keep_contents:
            move_project_contents_to_base(project_name)
        else:
            delete_profiles_and_tasks_of_project(project_name)

        del all_projects[project_name]
        return []
