"""userintr_fields: reading an editor dialog's fields back, and the checks made before anything is applied.

Task arguments, Profile conditions, Scene fields and Object Properties values, the redaction request, the
Project edits an Apply would lose, and the owning Project a new object goes into.  userintr_android reads
the same fields for Save To Android."""

from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.core import scenelayout
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.maputils import find_owning_project, find_owning_project_for_scene, find_owning_project_for_task
from maptasker.src.core.sysconst import logger
from maptasker.src.edit import profedit, sceneedit, sessundo, taskedit
from maptasker.src.gui.guiutils import is_no_selection, refresh_tasker_object_pulldowns, select_pulldown_option
from maptasker.src.gui.guiwins_editor import REDACT_FIELD
from maptasker.src.gui.guiwins_project import EDIT_PROJECT_INERT_FIELDS

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


def confirmed_single_project_name(gui: MyGui) -> str:
    """Returns gui.single_project_name, but only if the Specific Name tab's own
    Project pulldown currently lists it among its options -- not just because
    the cached attribute happens to be set.

    gui.single_project_name can be set (e.g. restored from a previous
    session's saved settings, via process_single_name_restore) before that
    pulldown's own options list has been populated with real Project names --
    it starts as a placeholder ["None"] and only gets replaced once
    refresh_tasker_object_pulldowns runs, which happens *after* settings
    restore in MyGui.__init__. The pulldown then keeps showing nothing/"None"
    selected even though the cached name is still set underneath, silently
    satisfying the Add Task/Add Profile "select a Project first" gate despite
    the user seeing no selection at all in that pulldown. Requiring the name
    to actually appear in the pulldown's current options closes that gap.

    Each Project option is f"{translate_string('Project:')} {name}" (see
    MyGui.build_the_tree), so its prefix is whatever the current language calls
    a Project -- "Projekt: " in German, "Projet: " in French, "プロジェクト" and a
    fullwidth colon (U+FF1A) in Japanese. This gate used to look for a hardcoded "Project: ", which
    matched nothing in any other language, so it closed on a Project that was
    plainly selected and Edit Project/Add Profile/Add Task refused to open.

    The option is rebuilt through translate_string here rather than parsed
    apart, because parsing means picking a separator and the separator is
    itself translated -- Japanese uses a fullwidth colon, so splitting on ": "
    silently fails for exactly the languages this is meant to fix.
    """
    name = getattr(gui, "single_project_name", "")
    if not name:
        return ""
    widget = getattr(gui, "specific_project_optionmenu", None)
    options = getattr(widget, "options", None) if widget is not None else None
    # No pulldown yet is not evidence of a bad name -- only a populated list is.
    if options is None:
        return name
    # Bare name covers the pulldown's unprefixed form; the second is how the
    # Project list itself is built.
    return name if name in options or f"{translate_string('Project:')} {name}" in options else ""


def confirmed_single_scene_name(gui: MyGui) -> str:
    """Returns gui.single_scene_name, but only if the Specific Name tab's own
    Scene pulldown currently lists it -- the Scene twin of
    confirmed_single_project_name, guarding the identical gap (a name restored
    from a previous session's settings before the pulldown was ever populated,
    see that function for the full account).

    Simpler than its Project counterpart in one way: the Scene pulldown lists
    bare names, not "Scene: name" (guiutils.get_tasker_objects builds it straight
    from all_scenes' keys, the same way it builds the Task list), so there is no
    translated prefix to reconstruct.
    """
    name = getattr(gui, "single_scene_name", "")
    if not name:
        return ""
    widget = getattr(gui, "specific_scene_optionmenu", None)
    options = getattr(widget, "options", None) if widget is not None else None
    # No pulldown yet is not evidence of a bad name -- only a populated list is.
    if options is None:
        return name
    return name if name in options else ""


def project_for_new_object(gui: MyGui, item_label: str) -> tuple[str, str]:
    """The Project a new Profile/Task/Scene should be attached to, given whatever the
    'Specific Name' tab currently has selected, plus the message to tell the user when
    there isn't one.

    Returns (project_name, "") when a Project was worked out, or ("", message) when
    none could be -- callers notify with the message and go no further.

    A selected Project is used as-is.  The other three selections are mutually exclusive
    with it (see process_name_event), so with a Profile, Task or Scene selected there is
    no Project selection to read -- but there is still exactly one Project that owns the
    selected object, and that is the one the new object belongs in.  Resolving it here is
    what lets "Add Profile"/"Add Task"/"Add Scene" work straight off a Profile/Task/Scene
    selection instead of stopping to demand a Project the user has already implied.

    item_label names the *new* object ("Profile"/"Task"/"Scene") purely for the message.

    An object with no owning Project is a real possibility rather than an oversight -- a
    Task attached to no Project at all, a Scene no Project lists -- so that case keeps
    asking for a Project, naming the object that led nowhere so it is clear why.
    """
    if project_name := confirmed_single_project_name(gui):
        return project_name, ""

    select_a_project = translate_string("Select a single Project first (Project pulldown above).")

    # Whichever of the other three is selected, and how to get from it to its Project.
    for label, resolve in (
        ("Profile", find_owning_project),
        ("Task", find_owning_project_for_task),
        ("Scene", find_owning_project_for_scene),
    ):
        selected_name = getattr(gui, f"single_{label.lower()}_name", "")
        if is_no_selection(selected_name):
            continue
        if owning_project := resolve(selected_name, state=gui.state):
            return owning_project, ""
        no_owner = translate_string("does not belong to a Project, so there is nowhere to attach a new")
        return "", (
            f"{translate_string(label)} '{selected_name}' {no_owner} "
            f"{translate_string(item_label)}.  {select_a_project}"
        )

    return "", select_a_project


def redact_requested(field_refs: dict, key: str = REDACT_FIELD) -> bool:
    """Whether this export's "Redact secrets" box is ticked.

    Read through a helper rather than off the widget, because the four Edit dialogs file
    the box under three different keys (see guiwins_editor.build_redact_checkbox) and because a
    dialog that has not been given one at all -- Add Task and Add Profile, which export
    something the user has only just typed in -- must read as "no" rather than raise.
    """
    checkbox = field_refs.get(key)
    return bool(getattr(checkbox, "value", False))


def redacted_note(redact: bool) -> str:
    """The sentence a save adds to its "saved" message when it redacted on the way out.

    Worth saying every time.  A redacted file is one the user is about to hand to somebody
    else, and the two things they need to know -- that it is not importable as-is, and that
    the redaction is a first pass rather than a promise -- are exactly the things that are
    invisible once the dialog has closed.
    """
    if not redact:
        return ""
    return (
        " Secrets and personal details were redacted: the comment at the top of the file "
        "lists what went. Read it before sharing -- a secret that looks like an ordinary "
        "word cannot be recognized."
    )


def unapplied_project_edits(field_refs: dict) -> list[str]:
    """Guards the Edit Project dialog's two by-name saves against a field being added to
    it without the apply step those saves would then need.  Returns error strings, empty
    when there is nothing to worry about -- same contract as apply_scene_field_values.

    Both Project saves render from the live tree by name (projedit.write_standalone_
    project_xml and .save_project_to_android each take project_name, not the edited copy),
    so anything the dialog holds that has not been written back to that tree does not reach
    the file.  Today nothing does: the dialog has a read-only Name and an export path, both
    listed in guiwins_project.EDIT_PROJECT_INERT_FIELDS, and this returns nothing.

    It exists for the next editable field added there.  That field will work everywhere it
    is visible -- typed into, previewed, read back -- and be quietly missing from the
    exported .prj.xml and the upload, with no error to trace, exactly as an added Scene
    component was missing from both before those handlers learned to apply first.  Failing
    the save and naming the field turns half a day of that into one message.

    Deliberately a deny-list of what is known inert rather than an allow-list of what looks
    editable: a new field is caught by being unrecognised, so nothing has to predict what
    kind of widget it will be, and silence here always means "somebody checked".
    """
    unknown = sorted(set(field_refs) - EDIT_PROJECT_INERT_FIELDS)
    if not unknown:
        return []

    logger.error(f"Edit Project dialog has unapplied editable field(s): {', '.join(unknown)}")
    return [
        (
            f"Cannot save Project: the field(s) {', '.join(unknown)} are edited in this dialog but "
            "are not written to the Project before it is saved, so saving now would leave them out. "
            "See guiwins_project.EDIT_PROJECT_INERT_FIELDS."
        ),
    ]


def apply_scene_field_values(edited_scene: sceneedit.EditableScene, field_refs: dict) -> list[str]:
    """Writes the Add/Edit Scene dialog's non-name widgets back onto the Scene
    copy, and returns a list of error strings (empty on success, and nothing is
    written when it is non-empty -- the same all-or-nothing contract
    sceneedit.apply_edits_to_scene uses).

    Today that is the four size fields guiwins_scene._build_scene_editor_body puts up
    for a Legacy Scene.  A Version 2 Scene has no size at all -- its layout is
    declarative, so that function builds no size inputs for one -- and this
    silently writes nothing for it: the widgets simply aren't in field_refs, and
    the loop skips what isn't there.  That is the intended contract between the
    two, not an oversight; it means a V2 Scene can never be given a canvas size
    by this path, however the dialog changes.

    They are validated here rather than in the dialog builder because that runs
    once, when the dialog opens, and what needs checking is what the user typed
    afterward.  Anything that function grows later is read back here -- these two
    are a matched pair and the only two places the Scene body's widgets are known
    by name.

    Sizes must be whole numbers; -1 is allowed and meaningful (Tasker's "this
    orientation has no layout of its own", see sysconst.UNSET_DIMENSION), so the
    check is "integer", not "positive integer".
    """
    errors = []
    pending: dict[str, str] = {}

    for key, label in sceneedit.SCENE_DIMENSION_FIELDS:
        widget = field_refs.get(key)
        if widget is None:
            continue
        value = str(widget.value).strip()
        try:
            int(value)
        except ValueError:
            errors.append(f"{translate_string(label)} must be a whole number (-1 for no layout).")
            continue
        pending[key] = value

    if errors:
        return errors

    sceneedit.set_scene_dimensions(edited_scene, pending)
    _encode_v2_layout_if_edited(edited_scene, field_refs)
    return []


def _encode_v2_layout_if_edited(edited_scene: sceneedit.EditableScene, field_refs: dict) -> None:
    """Writes the Version 2 designer's live layout dict back into the Scene's <lj>.

    The designer edits that dict in place as the user types (guiwins_designer_v2._build_v2_designer),
    so by the time a save button runs, every property change is already in it and this is
    the single step that makes them real.  A Legacy Scene has no "v2_layout" in field_refs
    and this does nothing.

    Re-syncs the layout's embedded "name" from <nme> first, because both this and
    sceneedit.apply_edits_to_scene write to <lj> and the save handlers call them in
    different orders: Rename applies the name (which re-encodes the layout it decodes
    itself) and then lands here, so encoding a stale in-memory copy would put the old name
    straight back. Taking the name from the element -- the one place both agree on -- makes
    the two orderings equivalent.

    Encoding an untouched layout is a no-op in the only sense that matters: it reproduces
    the original <lj> byte for byte (see scenelayout._GZIP_LEVEL), so a dialog opened and
    saved with nothing changed leaves the file exactly as it was.
    """
    layout = field_refs.get("v2_layout")
    if not isinstance(layout, dict):
        return
    layout["name"] = edited_scene.scene_element.findtext("nme", "") or layout.get("name", "")
    scenelayout.encode_v2_layout(edited_scene.scene_element, layout)


def finish_new_scene(gui: MyGui, edited_scene: sceneedit.EditableScene, project_name: str) -> None:
    """Registers a validated, applied new Scene into the live in-memory backup,
    attaches it to its Project, and refreshes the pulldowns -- the Add Scene
    counterpart of finish_new_profile, and attaching for the same reason: a
    Scene the owning Project's <scenes> doesn't name is invisible to every view
    (see sceneedit.add_scene_to_project).
    """
    # One step to take back, not two: registering the Scene and attaching it to its
    # Project are one thing the user did.  undoable is re-entrant, so the mutators'
    # own blocks inside this one add nothing to the history.
    with sessundo.undoable(f"Add Scene '{edited_scene.scene_name}'", state=gui.state):
        sceneedit.register_new_scene(edited_scene, state=gui.state)
        sceneedit.add_scene_to_project(edited_scene.scene_name, project_name, state=gui.state)
    refresh_tasker_object_pulldowns(gui)

    # Select the new Scene as the app-wide single-Scene filter and show it in the
    # pulldown -- also clears any stale single Project/Profile/Task selection.
    select_pulldown_option(gui.specific_scene_optionmenu, edited_scene.scene_name)


def task_arg_values(field_refs: dict) -> dict[str, str]:
    """Snapshots field_refs' action-argument widgets into the string-keyed dict
    taskedit_apply.apply_edits_to_task expects -- shared by every Task-editing entry
    point (Save, Save To Android, Ok, and Add Task's own Save/Ok), which all
    read the same live NiceGUI widget values the same way.
    """
    arg_values = {}
    for key, widget in field_refs.items():
        # Everything in field_refs that is NOT an action argument has to be named here --
        # this sweeps the whole dict, so a widget added to the dialog and forgotten below
        # is applied to the Task as an argument called whatever its key happens to be.
        # REDACT_FIELD is one of those: it says how this export is written, not what the
        # Task holds.
        if key in ("name", "priority", "save_path", "target_project_name", REDACT_FIELD):
            continue
        value = widget.value
        arg_values[key] = "1" if value is True else "0" if value is False else str(value)
    return arg_values


def object_property_values(field_refs: dict) -> dict[str, str]:
    """Snapshots the Properties dialog's widgets into the string-keyed dict
    objprops.apply_properties expects.

    Booleans become "true"/"false" rather than task_arg_values' "1"/"0": these go
    straight into tags Tasker writes as the words (<immutable>false</immutable>,
    <stayawake>true</stayawake>), and objprops compares them against PropField.default,
    which is in the same spelling.

    A ui.number left empty has value None, which has to read back as "" (no priority
    set) rather than the string "None".
    """
    values = {}
    for key, widget in field_refs.items():
        value = widget.value
        if value is True or value is False:
            values[key] = "true" if value else "false"
        elif value is None:
            values[key] = ""
        elif isinstance(value, float) and value.is_integer():
            # ui.number hands back a float even with format="%.0f" -- 50.0 must not
            # become "50.0" in <pri>.
            values[key] = str(int(value))
        else:
            values[key] = str(value)
    return values


def profile_condition_values(field_refs: dict) -> dict[str, str]:
    """Snapshots field_refs' condition-field widgets into the string-keyed dict
    profedit.apply_edits_to_profile expects -- shared by every Profile-editing
    entry point (Save, Save To Android, Ok), same reasoning as task_arg_values.
    """
    condition_values = {}
    for key, widget in field_refs.items():
        if not key.startswith("cond"):
            continue
        value = widget.value
        condition_values[key] = "1" if value is True else "0" if value is False else str(value)
    return condition_values


def link_pending_task_pickers(edited_profile: profedit.EditableProfile, field_refs: dict, state: RunState) -> None:
    """Links in whatever's currently picked in the Entry/Exit "Choose a Task"
    dropdown even if the user never clicked its separate "Link" button --
    picking a Task in that dropdown reads as "done" to a user, so Save/Ok/
    Save To Android shouldn't silently discard it and then complain the
    Entry/Exit Task is missing (see profedit.validate_new_profile_requirements)
    just because the extra confirmation click didn't happen. field_refs only
    has "{entry,exit}_task_picker" while that Task is still unlinked (see
    guiwins_profedit._build_profile_editor_body) -- already-linked ones have nothing to do here.
    """
    for link_type in ("Entry", "Exit"):
        picker = field_refs.get(f"{link_type.lower()}_task_picker")
        if picker is None or not picker.value:
            continue
        resolved = taskedit.resolve_task_by_name(picker.value, state=state)
        if resolved is not None:
            task_id, _ = resolved
            profedit.link_task_to_profile(edited_profile, task_id, link_type)
