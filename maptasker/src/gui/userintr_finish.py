"""userintr_finish: putting an edited or new object into the loaded configuration, and showing it.

Validating and applying an edited or new Task or Profile, finishing a new Scene or Project, reloading the saved
copy, and reselecting an object after a rename so the pulldowns follow it."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.edit import (
    profedit,
    projedit,
    sessundo,
    taskedit,
    taskedit_addable,
    taskedit_apply,
    taskedit_model,
    taskedit_save,
)
from maptasker.src.gui.guiutils import (
    clear_single_item_view_names,
    display_current_file,
    refresh_tasker_object_pulldowns,
    reset_single_item_pulldowns,
    select_pulldown_option,
)
from maptasker.src.gui.userintr_fields import link_pending_task_pickers, profile_condition_values, task_arg_values
from maptasker.src.mapgen.taskerd import get_the_xml_data

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


def notify_if_plugin_needs_configuration(element: Element, name: str) -> None:
    """Warns, as a just-added Action/Event/State goes in, that it is a third-party
    plugin whose own configuration can only be set inside Tasker -- see
    taskedit_addable.tasker_configuration_warning, which decides whether one is warranted
    (nothing is shown for anything that isn't a plugin). The item's own panel in
    the dialog carries the same warning standing (guiwins.
    _render_plugin_configuration_warning); this is the moment-of-adding nudge, so
    it isn't missed in a long action list.
    """
    warning = taskedit_addable.tasker_configuration_warning(element, name)
    if warning:
        ui.notify(warning, type="warning", multi_line=True, timeout=8000)


async def show_save_in_progress_notice() -> ui.notification:
    """Tell the user a Save To Current File has started, before the (blocking) save does.

    A large configuration can take a few seconds to render, write and reload, and every step
    of that runs on NiceGUI's event loop: a notification only queued before it would not
    reach the browser until the whole save was over.  The short sleep hands the loop back
    long enough for the message to be sent first.  The caller dismisses the returned
    notification once the save has finished or failed, so it never outlives the work.
    """
    notice = ui.notification(
        translate_string("Save to current file in progress"),
        type="ongoing",
        spinner=True,
        timeout=None,
        position="top",
    )
    await asyncio.sleep(0.15)
    return notice


def reload_saved_copy_and_refresh(gui: MyGui, new_file_path: str) -> tuple[bool, str]:
    """After Save To Current File writes a new, timestamped copy of the backup
    (see maputil2.write_full_backup_to_current_file -- the original file it
    was loaded from is never touched), switches the app over to that copy so
    it -- not the untouched original -- becomes "the current file" for any
    further editing/saving: re-parses it through the same load path
    open_and_get_backup_xml_file uses (open() the file, then
    taskerd.get_the_xml_data()), updates the Current File display, and
    refreshes the Project/Profile/Task pulldowns from the freshly loaded data.

    Public because the Fix Findings dialog saves the same way the four Edit
    dialogs do (see userintr.fix_findings_event).  It is the same two steps in
    the same order there; what differs is only what each caller does between
    them and afterwards, which is why this is shared and the sequence around
    it is not.

    Returns (True, "") on success, or (False, error_message) if the reload
    itself fails -- the copy was still written to disk either way; only the
    app's in-memory state failed to switch over to it.
    """
    try:
        gui.state.file_to_get = open(new_file_path, encoding="utf-8")
    except OSError as e:
        return False, str(e)

    gui.state.program_arguments.file = new_file_path
    return_code = get_the_xml_data(state=gui.state)
    if return_code != 0:
        return False, f"Failed to load '{new_file_path}' (code {return_code})."

    gui.file = new_file_path
    display_current_file(gui, new_file_path)
    refresh_tasker_object_pulldowns(gui)
    return True, ""


def apply_edited_task(edited_task: taskedit_model.EditableTask, field_refs: dict, state: RunState) -> bool:
    """Validates and applies an existing Task's field values into the live
    in-memory backup -- the shared body of keep_edited_task_event ("Ok") and
    save_edited_task_to_current_file_event ("Save To Current File"), which
    differ only in what happens after this succeeds. Any error is already
    notified to the user; returns False so the caller knows to stop there.
    """
    arg_values = task_arg_values(field_refs)
    errors = taskedit_apply.apply_edits_to_task(
        edited_task,
        field_refs["name"].value,
        field_refs["priority"].value,
        arg_values,
        state,
    )
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False
    taskedit_save.apply_edited_task_to_live_tree(edited_task, state=state)
    return True


def validate_and_apply_new_task(
    edited_task: taskedit_model.EditableTask,
    field_refs: dict,
    state: RunState,
    *,
    check_save_path: bool = False,
) -> tuple[bool, str]:
    """Validates a brand-new Task's Name (and, if check_save_path, its Save
    path) for conflicts, then applies its field values -- the shared
    validation+apply step of every Add Task success path (Ok, Save, Save To
    Current File), before each goes on to do its own thing with the result
    (see finish_new_task). Returns (True, name_value) on success, or
    (False, "") if anything failed (errors already notified).
    """
    if not edited_task.actions:
        ui.notify(translate_string("This Task has no actions yet."), type="warning")

    name_value = field_refs["name"].value.strip()
    conflict_errors = []
    if taskedit.task_name_exists(name_value, state=state):
        conflict_errors.append(f"A Task named '{name_value}' already exists in this backup. Choose a different name.")
    if check_save_path:
        save_path = field_refs["save_path"].value.strip()
        if taskedit_save.save_path_exists(save_path):
            conflict_errors.append(f"A file already exists at '{save_path}'. Choose a different name or location.")
    if conflict_errors:
        for error in conflict_errors:
            ui.notify(error, type="negative")
        return False, ""

    arg_values = task_arg_values(field_refs)
    errors = taskedit_apply.apply_edits_to_task(
        edited_task, name_value, field_refs["priority"].value, arg_values, state
    )
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False, ""

    return True, name_value


def finish_new_task(
    gui: MyGui,
    edited_task: taskedit_model.EditableTask,
    name_value: str,
    on_created: Callable[[str], None] | None,
    field_refs: dict | None = None,
) -> None:
    """Registers a validated, applied new Task into the live in-memory backup,
    fires on_created (see build_add_task_dialog), attaches it to the target
    Project's <tids> if one was required and selected before the top-level
    "Add Task" dialog opened (field_refs["target_project_name"] -- see
    userintr.open_add_task_dialog_event and profedit.add_task_to_project;
    empty for the nested-in-Profile-edit Add Task flow, which doesn't attach
    to a Project at all), and refreshes the Project/Profile/Task pulldowns --
    the common tail of every Add Task success path, run once
    validate_and_apply_new_task has succeeded (and, for Save, only after its
    standalone file write has too).
    """
    target_project_name = field_refs.get("target_project_name") if field_refs else None

    # One step to take back, not two or three: registering the Task, whatever on_created
    # links it to, and attaching it to its Project are one thing the user did.  undoable is
    # re-entrant, so the mutators' own blocks inside this one add nothing to the history.
    with sessundo.undoable(f"Add Task '{name_value}'", state=gui.state):
        taskedit_save.register_new_task(edited_task, name_value, state=gui.state)
        if on_created is not None:
            on_created(edited_task.task_id)
        if target_project_name:
            profedit.add_task_to_project(edited_task.task_id, target_project_name, state=gui.state)

    refresh_tasker_object_pulldowns(gui)

    # Only for the top-level Add Task flow (target_project_name set, see
    # open_add_task_dialog_event) -- the nested Entry/Exit Task picker inside
    # Add/Edit Profile (open_add_task_for_profile_link_event) never sets it,
    # and selecting the new Task as the app-wide single-Task filter there
    # would be a surprising side effect of just picking an Entry/Exit Task.
    if target_project_name:
        select_pulldown_option(gui.specific_task_optionmenu, name_value)


def apply_edited_profile(edited_profile: profedit.EditableProfile, field_refs: dict, state: RunState) -> bool:
    """Validates and applies an existing Profile's field values into the live
    in-memory backup -- the shared body of keep_edited_profile_event ("Ok")
    and save_edited_profile_to_current_file_event ("Save To Current File"),
    which differ only in what happens after this succeeds. Any error is
    already notified to the user; returns False so the caller knows to stop there.
    """
    link_pending_task_pickers(edited_profile, field_refs, state=state)
    condition_values = profile_condition_values(field_refs)
    errors = profedit.apply_edits_to_profile(edited_profile, field_refs["name"].value, condition_values, state=state)
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False
    profedit.apply_edited_profile_to_live_tree(edited_profile, state=state)
    return True


def validate_and_apply_new_profile(
    edited_profile: profedit.EditableProfile,
    field_refs: dict,
    state: RunState,
    *,
    check_save_path: bool = False,
) -> tuple[bool, str, str]:
    """Validates a brand-new Profile's Name and Project (and, if
    check_save_path, its Save path) for conflicts, then applies its field
    values -- the shared validation+apply step of every Add Profile success
    path (Ok, Save, Save To Current File), before each goes on to do its own
    thing with the result (see finish_new_profile). Returns
    (True, name_value, project_name) on success, or (False, "", "") if
    anything failed (errors already notified).
    """
    link_pending_task_pickers(edited_profile, field_refs, state=state)

    name_value = field_refs["name"].value.strip()
    project_name = field_refs.get("target_project_name", "")

    conflict_errors = []
    if profedit.profile_name_exists(name_value, state=state):
        conflict_errors.append(
            f"A Profile named '{name_value}' already exists in this backup. Choose a different name.",
        )
    if check_save_path:
        save_path = field_refs["save_path"].value.strip()
        if profedit.save_path_exists(save_path):
            conflict_errors.append(f"A file already exists at '{save_path}'. Choose a different name or location.")
    if not project_name:
        conflict_errors.append(
            "Choose a Project first -- a Profile has to belong to one to show up anywhere in the app.",
        )
    conflict_errors.extend(profedit.validate_new_profile_requirements(edited_profile))
    if conflict_errors:
        for error in conflict_errors:
            ui.notify(error, type="negative")
        return False, "", ""

    condition_values = profile_condition_values(field_refs)
    errors = profedit.apply_edits_to_profile(edited_profile, name_value, condition_values, state=state)
    if errors:
        for error in errors:
            ui.notify(error, type="negative")
        return False, "", ""

    return True, name_value, project_name


def finish_new_profile(
    gui: MyGui,
    edited_profile: profedit.EditableProfile,
    name_value: str,
    project_name: str,
) -> None:
    """Registers a validated, applied new Profile into the live in-memory
    backup, attaches it to its Project, and refreshes the Project/Profile/
    Task pulldowns -- the common tail of every Add Profile success path, run
    once validate_and_apply_new_profile has succeeded (and, for Save, only
    after its standalone file write has too).
    """
    # One step to take back, not two: registering the Profile and attaching it to its
    # Project are one thing the user did.  undoable is re-entrant, so the mutators'
    # own blocks inside this one add nothing to the history.
    with sessundo.undoable(f"Add Profile '{name_value}'", state=gui.state):
        profedit.register_new_profile(edited_profile, name_value, state=gui.state)
        profedit.add_profile_to_project(edited_profile, project_name, state=gui.state)
    refresh_tasker_object_pulldowns(gui)

    # Select the new Profile as the app-wide single-Profile filter and show it
    # in the pulldown -- also clears any stale single Project/Task selection.
    select_pulldown_option(gui.specific_profile_optionmenu, name_value)


def finish_new_project(gui: MyGui, edited_project: projedit.EditableProject) -> None:
    """Registers a validated, applied new Project into the live in-memory
    backup and refreshes the Project/Profile/Task pulldowns -- the Add
    Project counterpart of finish_new_profile. No Project-attachment step
    (unlike finish_new_profile's add_profile_to_project) -- a Project has no
    parent of its own.
    """
    projedit.register_new_project(edited_project, state=gui.state)
    refresh_tasker_object_pulldowns(gui)

    # Select the new Project as the app-wide single-Project filter and show it
    # in the pulldown -- also clears any stale single Profile/Task selection.
    select_pulldown_option(gui.specific_project_optionmenu, edited_project.project_name)


def reset_specific_name_selection(gui: MyGui) -> None:
    """Clears the single Project/Profile/Task selection and resets all three
    'Specific Name' pulldowns to "None" -- for when a Delete removes the
    currently-selected name out from under them. Anything that merely *renames*
    it uses select_renamed_item instead: the object is still there, so it stays
    selected under its new name.
    Mirrors the identical guarded reset in process_single_name_restore's
    invalid-name branch: the is_updating guard stops setting .value here from
    re-entering the single_xxx_name_event handlers for a name that no longer
    resolves to anything.
    """
    clear_single_item_view_names(gui)
    try:
        gui.is_updating = True
        reset_single_item_pulldowns(gui)
    finally:
        gui.is_updating = False


def _pulldown_option_for_name(optionmenu: ui.select, item_type: str, new_name: str) -> str:
    """The exact option string this 'Specific Name' pulldown lists for a
    Project/Profile/Task called new_name -- what its .value has to be set to for
    the selection to actually show.

    The three pulldowns don't label their entries the same way. The Task one
    lists plain names (guiutils.get_tasker_objects builds it straight from
    all_tasks_by_name's keys), but the Project and Profile ones list them
    prefixed with the item type -- "Project: $NewProject1", "Profile: My
    Profile" -- built by MyGui.build_the_tree and guiutils.build_profiles
    respectively. Assigning the bare name to those two sets a value that isn't
    among the select's options, and NiceGUI then renders nothing at all, leaving
    just the widget's own "Project"/"Profile" label showing as though nothing
    were selected. (process_single_name_event strips that same prefix back off
    when the user picks one by hand, which is the mirror image of this.)

    Resolved against the widget's live options rather than by rebuilding the
    prefix here, so it stays right whatever those two functions do with it --
    including translation (both build their heads through translate_string).
    Exact match first, then the translated "<type>: <name>" form, then any
    option whose tail is exactly ": <name>". Falls back to the bare name if the
    options don't have it at all -- no worse than not looking.
    """
    options = [option for option in (getattr(optionmenu, "options", None) or []) if isinstance(option, str)]
    if new_name in options:
        return new_name

    prefixed = f"{translate_string(f'{item_type}:')} {new_name}"
    if prefixed in options:
        return prefixed

    tail = f": {new_name}"
    return next((option for option in options if option.endswith(tail)), new_name)


def select_renamed_item(gui: MyGui, item_type: str, new_name: str) -> None:
    """Makes a just-renamed Project/Profile/Task the current single item and
    points its 'Specific Name' pulldown at the new name -- the Rename
    counterpart to reset_specific_name_selection, which the rename handlers
    used to call. Clearing the selection was only ever right because the
    pulldown still held the *old* name; the object itself is still there and
    still the one the user is working on, so following the rename is the
    better answer than dropping the selection on the floor.

    Also called by the three Save To Current File handlers, which apply the
    Name field the same way "Ok" does and then rebuild the pulldowns by
    re-parsing the file they just wrote -- so they must re-select *after* that
    reload, and with the name that was actually applied. A save that didn't
    change the name re-selects the same name, which is a harmless no-op.

    item_type is "Project"/"Profile"/"Task", matching process_name_event's own
    vocabulary and the specific_{project,profile,task}_optionmenu attribute names.

    Two steps, in this order:

    1. Point the pulldown at the new name -- as the option string that pulldown
       actually lists it under, which for Project/Profile is not the bare name
       (see _pulldown_option_for_name). It has to be set directly -- nothing
       else does it (process_name_event only ever resets the *other* two, since
       normally the user picking the name is what set this one). Guarded by
       is_updating for the usual reason (see reset_specific_name_selection):
       assigning .value fires the select's on_change, which would re-enter
       single_*_name_event for the name we're about to hand to
       process_name_event anyway. The option lists must already have been
       rebuilt (refresh_tasker_object_pulldowns) or the new name isn't among
       this select's options yet and the assignment shows blank.

    2. Run the rename through process_name_event, exactly as if the user had
       just picked the new name from that pulldown -- it re-validates the name,
       sets single_{project,profile,task}_name plus the matching
       PrimeItems.program_arguments entry that the Map/Diagram/Tree runs read,
       clears the other two selections (single-item selection is mutually
       exclusive), and refreshes the "Display only ..." label.

    No-op if the pulldown widget doesn't exist yet (defense in depth -- by the
    time an Edit dialog is open the 'Specific Name' tab has long been built).
    """
    optionmenu = getattr(gui, f"specific_{item_type.lower()}_optionmenu", None)
    if optionmenu is None:
        return

    try:
        gui.is_updating = True
        optionmenu.value = _pulldown_option_for_name(optionmenu, item_type, new_name)
        optionmenu.update()
    finally:
        gui.is_updating = False

    # The bare name, not the pulldown's prefixed label -- process_name_event
    # stores it in single_{project,profile,task}_name/PrimeItems.program_arguments,
    # where every consumer expects the name on its own.
    gui.event_handlers.process_name_event(item_type, new_name)
