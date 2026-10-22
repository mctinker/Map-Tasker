"""Editor event handlers: the Task, Profile, Scene and Project editors and the Object Properties form.

Split out of userintr.py the same way userintr_android.py and userintr_ai.py were.
EditorEventHandlers is a group of MapTaskerEventHandlers (gui.event_handlers.editors) that holds
every name the dialogs are wired to -- Add, Edit, Rename, Delete, Ok, Save and Save To Current
File for each kind of object, the action and condition editors inside them, and Object Properties.

The four editors moved together because they share their helpers, which are now modules of their own:
userintr_fields reads a dialog's fields back (task_arg_values, profile_condition_values,
apply_scene_field_values), and userintr_finish puts a new object into the loaded configuration
(finish_new_task and its siblings) and reselects an object after a rename (select_renamed_item).
The Save To Android handlers in userintr_android import the field readers from userintr_fields.

The dialogs themselves are built in guiwins and its guiwins_* modules, and the edits are made
to the XML by taskedit, profedit, sceneedit and projedit.  This is what the dialogs' buttons do.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core import objprops, scenelayout
from maptasker.src.core.maputil2 import translate_string, write_full_backup_to_current_file
from maptasker.src.edit import (
    profedit,
    projedit,
    sceneedit,
    sceneedit_legacy,
    sessundo,
    taskedit,
    taskedit_apply,
    taskedit_model,
    taskedit_save,
)
from maptasker.src.gui.guiutils import (
    get_xml,
    refresh_tasker_object_pulldowns,
)
from maptasker.src.gui.guiwins_dialogs import (
    build_delete_project_dialog,
    build_overwrite_confirm_dialog,
    build_rename_dialog,
    build_unsaved_deletion_dialog,
)
from maptasker.src.gui.guiwins_editor import PROJECT_REDACT_FIELD, SCENE_REDACT_FIELD
from maptasker.src.gui.guiwins_profedit import (
    build_add_profile_dialog,
    build_delete_profile_dialog,
    build_edit_profile_dialog,
)
from maptasker.src.gui.guiwins_project import (
    build_add_project_dialog,
    build_edit_project_dialog,
)
from maptasker.src.gui.guiwins_props import build_object_properties_dialog
from maptasker.src.gui.guiwins_scene import (
    build_add_scene_dialog,
    build_add_scene_version_dialog,
    build_delete_scene_dialog,
    build_edit_scene_dialog,
)
from maptasker.src.gui.guiwins_sceneview import NiceGuiSceneView, suspend_scene_editor_session, suspended_scene_editor
from maptasker.src.gui.guiwins_taskedit import (
    build_add_task_dialog,
    build_delete_task_dialog,
    build_edit_task_dialog,
    build_run_task_on_android_dialog,
)
from maptasker.src.gui.userintr_fields import (
    apply_scene_field_values,
    confirmed_single_project_name,
    confirmed_single_scene_name,
    finish_new_scene,
    link_pending_task_pickers,
    object_property_values,
    profile_condition_values,
    project_for_new_object,
    redact_requested,
    redacted_note,
    task_arg_values,
    unapplied_project_edits,
)
from maptasker.src.gui.userintr_finish import (
    apply_edited_profile,
    apply_edited_task,
    finish_new_profile,
    finish_new_project,
    finish_new_task,
    notify_if_plugin_needs_configuration,
    reload_saved_copy_and_refresh,
    reset_specific_name_selection,
    select_renamed_item,
    show_save_in_progress_notice,
    validate_and_apply_new_profile,
    validate_and_apply_new_task,
)
from maptasker.src.gui.userintr_group import HandlerGroup

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element


class EditorEventHandlers(HandlerGroup):
    """The editor handlers: reached as hub.editors; self.hub is the rest of the window's handlers, self.gui the window."""

    def _offer_save_after_delete(self, message: str) -> None:
        """Offer Save To Current File once a delete has closed the dialog that held the only one."""
        build_unsaved_deletion_dialog(message, self.hub.save_whole_configuration)

    def open_edit_task_dialog_event(self) -> None:
        """Opens the Edit Task dialog for the currently selected single Task name."""
        the_view = self.gui
        task_name = getattr(the_view, "single_task_name", "")
        if not task_name:
            ui.notify(translate_string("Select a single Task first (Task pulldown above)."), type="warning")
            return

        edited_task = taskedit.load_task_for_edit(task_name, state=self.state)
        if edited_task is None:
            ui.notify(f"Could not find Task '{task_name}'.", type="negative")
            return

        build_edit_task_dialog(the_view, edited_task)

    def open_run_task_on_android_dialog_event(self) -> None:
        """Opens the Run Task On Android dialog for the currently selected single Task name.

        Nothing is loaded for edit: the device runs the Task Tasker already has, so the name is
        all the run needs.
        """
        task_name = getattr(self.gui, "single_task_name", "")
        if not task_name:
            ui.notify(translate_string("Select a single Task first (Task pulldown above)."), type="warning")
            return
        build_run_task_on_android_dialog(self.gui, task_name)

    def rename_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        title_label: ui.label,
    ) -> None:
        """Opens the Rename prompt for this Task, nested inside Edit Task -- see
        build_rename_dialog. Backs the "Rename" button; mirrors
        rename_profile_event/rename_project_event. The dialog's own Name field
        is read-only, so the prompt is where the new name comes from.
        """
        build_rename_dialog(
            self.gui,
            "Task",
            edited_task.task_element.findtext("nme", ""),
            lambda new_name, rename_dialog: self.confirm_rename_task_event(
                edited_task,
                field_refs,
                title_label,
                new_name,
                rename_dialog,
            ),
        )

    def confirm_rename_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        title_label: ui.label,
        new_name: str,
        rename_dialog: ui.dialog,
    ) -> None:
        """Validates the name typed into the Rename prompt and, if it's good,
        renames the Task in the live in-memory backup right away (see
        taskedit.rename_task_in_live_tree), then refreshes the pulldowns and
        re-selects the Task under its new name, so it stays the current single
        Task and its pulldown follows the rename (see select_renamed_item).
        Backs the prompt's "Rename" button; mirrors
        confirm_rename_profile_event. The prompt stays open on any error, with
        what was typed still in it to fix.

        Renames *only* the name, and leaves the Edit Task dialog open: it holds
        far more in-progress state than a name (every action's arguments, plus
        any action Add/Copy/Move/Delete already applied to the working copy),
        and closing here would throw the argument edits away. So Rename is a
        self-contained commit of one field the user can keep editing around --
        the title, the read-only Name field and the default export path are all
        brought up to date, and everything else stays pending until Ok/Save.
        """
        errors = taskedit.apply_task_rename(edited_task, new_name, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        old_name = taskedit.rename_task_in_live_tree(edited_task, state=self.state)
        refresh_tasker_object_pulldowns(self.gui)
        select_renamed_item(self.gui, "Task", new_name)

        title_label.set_text(f"Edit Task: {new_name}")
        # Ok/Save still read this field and apply whatever is in it, so leaving
        # the pre-rename name sitting there would let the next Ok rename the
        # Task straight back.
        field_refs["name"].value = new_name
        # Only re-derive the export path if it's still the one this dialog
        # defaulted to for the old name -- a path the user typed themselves is
        # their choice and shouldn't be silently rewritten by a rename.
        save_path_field = field_refs.get("save_path")
        if save_path_field is not None and save_path_field.value == taskedit_save.default_save_path(
            old_name, self.state
        ):
            save_path_field.value = taskedit_save.default_save_path(new_name, self.state)

        ui.notify(f"Renamed to '{new_name}'.", type="positive")
        rename_dialog.close()

    def delete_task_event(self, edited_task: taskedit_model.EditableTask, dialog: ui.dialog) -> None:
        """Opens the Delete Task confirmation dialog, nested inside Edit Task --
        see build_delete_task_dialog. Mirrors delete_profile_event/delete_project_event.
        """
        build_delete_task_dialog(self.gui, edited_task, dialog)

    def confirm_delete_task_event(
        self,
        task_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Task, along with every reference to it from the Projects
        that own it and the Profiles that run it (see taskedit_save.delete_task) --
        then refreshes the pulldowns, resets the now-stale single-name selection,
        and closes both dialogs. Backs the confirmation dialog's "Delete Task"
        button; mirrors confirm_delete_profile_event. Both dialogs stay open on
        error so nothing is lost.

        The selection reset is required, not cosmetic: the Task pulldown is still
        pointing at the name just deleted, and leaving it there would let Edit
        Task reopen on a Task that no longer resolves.
        """
        errors = taskedit_save.delete_task(task_name, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        refresh_tasker_object_pulldowns(self.gui)
        reset_specific_name_selection(self.gui)

        ui.notify(f"Deleted Task '{task_name}'.", type="positive")
        confirm_dialog.close()
        parent_dialog.close()
        self._offer_save_after_delete(f"Deleted Task '{task_name}'.")

    def save_edited_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Task dialog's field values, then writes the
        edited Task out as a standalone .tsk.xml file. Dialog stays open on any error
        so the user's in-progress edits aren't lost.
        """
        arg_values = task_arg_values(field_refs)

        errors = taskedit_apply.apply_edits_to_task(
            edited_task,
            field_refs["name"].value,
            field_refs["priority"].value,
            arg_values,
            self.state,
        )
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        save_path = field_refs["save_path"].value
        redact = redact_requested(field_refs)

        def _write() -> None:
            try:
                safety_copy = taskedit_save.write_standalone_task_xml(
                    edited_task, save_path, redact=redact, state=self.state
                )
            except OSError as e:
                ui.notify(f"Could not save file: {e}", type="negative")
                return

            taskedit_save.apply_edited_task_to_live_tree(edited_task, state=self.state)

            # The write took a copy of anything already at that path (see presave);
            # say so, so the user knows where it went.
            replaced_note = f" The file it replaced was copied to {safety_copy}." if safety_copy else ""
            ui.notify(f"Saved to {save_path}.{replaced_note}{redacted_note(redact)}", type="positive")
            dialog.close()

        # Unlike Add Task's Save, this export had no up-front save_path_exists
        # check (see validate_and_apply_new_task) -- confirm rather than clobber.
        if taskedit_save.save_path_exists(save_path):
            build_overwrite_confirm_dialog(f"'{save_path}'", _write)
            return
        _write()

    def stash_scene_event_task_edits(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
    ) -> None:
        """Snapshot an Event tab's argument and label widgets into the Task copy they belong
        to, WITHOUT touching the loaded configuration.

        Called whenever the panel holding those widgets is about to be torn down -- a sub-tab
        switch, a Property Type change, or Ok (see guiwins_sceneprops._build_scene_properties_dialog's
        flush_event_task_edits).  The copy outlives the widgets; the widgets do not survive
        the rebuild, so anything typed and not snapshotted here is gone.  Cancel does not run
        it: the copies it would write onto are the ones being thrown away.

        Errors are swallowed rather than notified.  This runs on navigation, not on a save:
        complaining about a half-typed number because the user clicked another sub-tab would
        be noise, and the same validation runs again -- and does report -- when the edits are
        actually applied.
        """
        taskedit_apply.apply_action_edits_to_task(edited_task, task_arg_values(field_refs), self.state)

    def keep_scene_event_task_edits(
        self,
        bound_tasks: dict,
        pending_tasks: dict,
        bind: Callable[[str, str], None],
    ) -> bool:
        """Put every Task edited under a Scene Properties Event tab into the loaded
        configuration -- what Ok does, so that nothing done in there is silently dropped.

        THIS IS THE HALF OF THAT DIALOG THAT DOES NOT WRITE THROUGH.  Everything else in it
        reaches the Scene copy as it is typed, so an exit that discarded the Task half was a
        trap: add an action, press the only button there was, and the action was gone.  Ok now
        keeps the lot, and Cancel drops it deliberately rather than by omission (see
        discard_scene_properties_event).

        Two kinds are kept, and each already has a path of its own:

          * a copy of a Task that was already bound -- applied over the live one
            (apply_scene_key_task_event's half), and
          * a Task composed under an event that had none -- registered and bound
            (create_scene_event_task_event's half), but only if it has actions in it.  An
            empty one is what an untouched sub-tab leaves behind, and creating a Task nobody
            put anything in would be an odd thing for a Close to do.

        `bind` is handed (event tag, new Task id) for each Task created, so this stays out of
        the business of what a Scene event binding looks like.

        Returns False if anything was rejected -- the caller keeps the dialog open, since the
        errors are already notified and the edits are still there to fix.
        """
        kept = True
        for edited_task, field_refs in bound_tasks.values():
            arg_values = task_arg_values(field_refs)
            errors = taskedit_apply.apply_action_edits_to_task(edited_task, arg_values, self.state)
            if errors:
                for error in errors:
                    ui.notify(error, type="negative")
                kept = False
                continue
            taskedit_save.apply_edited_task_to_live_tree(edited_task, state=self.state)

        for tag, (edited_task, field_refs) in list(pending_tasks.items()):
            if not edited_task.actions:
                continue
            if self.create_scene_event_task_event(
                edited_task,
                field_refs,
                lambda new_id, event_tag=tag: bind(event_tag, new_id),
            ):
                pending_tasks.pop(tag, None)
            else:
                kept = False

        return kept

    def discard_scene_properties_event(
        self,
        scene_element: Element,
        properties_snapshot: Element | None,
        geometry_snapshot: dict,
        field_refs: dict,
    ) -> None:
        """Cancel in the Scene Properties dialog: put the Scene's <PropertiesElement> back the
        way that dialog found it, and its geometry boxes with it.

        A REVERT RATHER THAN A "DON'T APPLY", because there is nothing waiting to be applied.
        Every field in there writes through to the Scene copy as it is typed -- which is what
        the Legacy designer does everywhere -- so the only way for Cancel to mean anything is
        to put the snapshot taken when the dialog opened back over the top.  See
        sceneedit_legacy.legacy_properties_restore, which also explains why the snapshot is of the
        properties alone and not of the whole Scene.

        The geometry is separate because it is not in that element: those four boxes drive the
        Scene dialog's own inputs (guiwins_sceneprops._render_scene_geometry), and a value written into
        one of those is what the save would read, so reverting the element alone would leave a
        cancelled size change still in force.

        The Task edits the dialog was holding are dropped by its own Cancel, which lets go of
        the copies; nothing here can reach them.  Whatever has already been put into the loaded
        configuration by "Apply to Task" or "Create Task" stays there -- Undo takes those back.
        """
        reverted = sceneedit_legacy.legacy_properties_restore(scene_element, properties_snapshot)
        for key, value in geometry_snapshot.items():
            widget = field_refs.get(key)
            if widget is not None and str(widget.value) != value:
                widget.value = value
                reverted = True

        # Silent when there was nothing to take back, the same as every other Cancel in this
        # app: a notification for closing a window that was only looked at is noise.
        if reverted:
            ui.notify(translate_string("Scene properties changes discarded."), type="info")

    def create_scene_event_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        on_created: Callable[[str], None],
    ) -> bool:
        """Registers the Task being composed under a Scene Properties Event tab and hands
        its id to `on_created`, which is what binds it to the event -- what "Create Task"
        does (see guiwins_sceneprops._render_scene_event_task_actions).

        Add Task's Ok (keep_new_task_event) for a Task that has no dialog of its own: same
        validation, same registration, same pulldown refresh, and the binding takes the
        place of Add Task's Project attachment inside the one undo step, so creating the
        Task and pointing the event at it are a single thing to take back.

        Returns True if the Task now exists; False leaves the panel alone with the errors
        already notified, so nothing typed is lost.
        """
        applied, name_value = validate_and_apply_new_task(edited_task, field_refs, state=self.state)
        if not applied:
            return False
        finish_new_task(self.gui, edited_task, name_value, on_created, field_refs)
        ui.notify(f"{translate_string('Created Task')} '{name_value}'.", type="positive")
        return True

    def apply_scene_key_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
    ) -> None:
        """Applies the Scene Properties KEY tab's Task action edits into the live
        in-memory backup -- what "Apply to Task" does (see
        guiwins._render_scene_key_task_actions).

        Ok's job (keep_edited_task_event) minus the two things that tab has no
        business doing: it never touches the Task's Name or Priority -- it shows
        neither, and a Task bound by id can be an unnamed one whose displayed name
        was invented by taskerd -- and it closes no dialog, since the Scene
        Properties dialog is still being used and the Scene's own edits are still
        pending in it.
        """
        errors = taskedit_apply.apply_action_edits_to_task(edited_task, task_arg_values(field_refs), self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return
        taskedit_save.apply_edited_task_to_live_tree(edited_task, state=self.state)
        task_name = edited_task.task_element.findtext("nme", "") or edited_task.task_id
        ui.notify(f"{translate_string('Changes kept for Task')} '{task_name}'.", type="positive")

    def keep_edited_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Task dialog's field values into the live
        in-memory backup (same as Save's apply_edited_task_to_live_tree), without
        writing a standalone file or touching Android, then closes the dialog --
        backs the "Ok" button, which keeps the edit for this session only. Dialog
        stays open on any error so the user's in-progress edits aren't lost.
        """
        if not apply_edited_task(edited_task, field_refs, state=self.state):
            return
        ui.notify(translate_string("Changes kept."), type="positive")
        dialog.close()

    async def save_edited_task_to_current_file_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Task dialog's field values (same as
        Ok), then writes the *entire* current backup -- not just this Task --
        out to a new, timestamped copy of whatever file it was loaded from
        (see maputil2.write_full_backup_to_current_file) and switches the app
        over to that copy (see reload_saved_copy_and_refresh) -- the original
        file is left untouched. Backs the "Save To Current File" button.
        Dialog stays open on any error so the user's in-progress edits aren't
        lost.

        The Name field is applied here just as "Ok" applies it, so this can be a
        rename too -- and the reload rebuilds the pulldowns from the file, which
        would leave the Task pulldown on the old name. Re-selects the Task under
        whatever name was actually applied, after the reload, the same way the
        Rename button does (see select_renamed_item).
        """
        if not apply_edited_task(edited_task, field_refs, state=self.state):
            return
        notice = await show_save_in_progress_notice()
        success, result = write_full_backup_to_current_file(state=self.state)
        if not success:
            notice.dismiss()
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = reload_saved_copy_and_refresh(self.gui, result)
        notice.dismiss()
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return
        # Read back off the element rather than the Name field: this is the name
        # apply_edits_to_task actually wrote (stripped), i.e. the one now in the
        # reloaded tables and the pulldown's options.
        if applied_name := edited_task.task_element.findtext("nme", ""):
            select_renamed_item(self.gui, "Task", applied_name)
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def keep_task_in_loaded_config(
        self,
        edited_task: taskedit_model.EditableTask,
        task_name: str,
        is_new_task: bool,
        on_created: Callable[[str], None] | None,
    ) -> None:
        """Put the saved Task into the loaded configuration: registered if it is new, written
        back over its old copy if it is not, and the pulldowns refreshed either way.

        Both of the dialog's buttons end here, and they have to: what the device was asked to
        do differs, what the edit means to the loaded backup does not.  A Task registered by
        one path and not the other would show up in the Edit Task picker only sometimes.
        """
        if is_new_task:
            taskedit_save.register_new_task(edited_task, task_name, state=self.state)
            if on_created is not None:
                on_created(edited_task.task_id)
        else:
            taskedit_save.apply_edited_task_to_live_tree(edited_task, state=self.state)
        refresh_tasker_object_pulldowns(self.gui)

    def open_add_project_dialog_event(self) -> None:
        """Opens the Add Project dialog for a brand-new Project. Unlike Add
        Profile/Add Task, there's no "select a parent first" gate -- a
        Project is the top of the hierarchy, so there's nothing to attach it to.
        """
        the_view = self.gui
        # See open_add_task_dialog_event's identical self-healing load: the toolbar's
        # "Current File" only means a filename is known, not that it's been parsed
        # into PrimeItems.xml_root yet.
        if self.state.xml_root is None:
            if not self.state.file_to_get and getattr(the_view, "file", ""):
                self.state.file_to_get = the_view.file
            if not self.state.file_to_get or get_xml(the_view.debug, the_view.appearance_mode, state=self.state) != 0:
                ui.notify(
                    translate_string("No backup file is currently loaded. Use 'Get Local XML' first."),
                    type="warning",
                )
                return

        new_project = projedit.create_new_project("", state=self.state)
        if isinstance(new_project, str):
            ui.notify(new_project, type="warning")
            return

        build_add_project_dialog(self.gui, new_project)

    def keep_new_project_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Project dialog's Name field, registers
        the new Project into the live in-memory backup, then closes the
        dialog -- the Add Project dialog's only save action (no standalone
        file or Save To Android surface, see projedit.py's module docstring).
        Dialog stays open on any error so the user's in-progress work isn't lost.
        """
        name_value = field_refs["name"].value.strip()
        if projedit.project_name_exists(name_value, state=self.state):
            ui.notify(
                f"A Project named '{name_value}' already exists in this backup. Choose a different name.",
                type="negative",
            )
            return

        errors = projedit.apply_edits_to_project(edited_project, name_value, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        finish_new_project(self.gui, edited_project)

        ui.notify(translate_string("Project added."), type="positive")
        dialog.close()

    def open_edit_project_dialog_event(self) -> None:
        """Opens the Edit Project dialog for the currently selected single Project name."""
        the_view = self.gui
        project_name = confirmed_single_project_name(the_view)
        if not project_name:
            ui.notify(translate_string("Select a single Project first (Project pulldown above)."), type="warning")
            return

        edited_project = projedit.load_project_for_edit(project_name, state=self.state)
        if edited_project is None:
            ui.notify(f"Could not find Project '{project_name}'.", type="negative")
            return

        build_edit_project_dialog(the_view, edited_project)

    def rename_project_event(
        self,
        edited_project: projedit.EditableProject,
        dialog: ui.dialog,
    ) -> None:
        """Opens the Rename prompt for this Project, nested inside Edit Project
        -- see build_rename_dialog. Backs the "Rename" button; mirrors
        rename_task_event/rename_profile_event. The dialog's own Name field is
        read-only, so the prompt is where the new name comes from.
        """
        build_rename_dialog(
            self.gui,
            "Project",
            edited_project.project_name,
            lambda new_name, rename_dialog: self.confirm_rename_project_event(
                edited_project,
                new_name,
                rename_dialog,
                dialog,
            ),
        )

    def confirm_rename_project_event(
        self,
        edited_project: projedit.EditableProject,
        new_name: str,
        rename_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Validates the name typed into the Rename prompt and applies it,
        renaming the Project in the live in-memory backup (moving its
        all_projects entry to the new name -- see
        projedit.rename_project_in_live_tree), making it the current single
        Project under that name (see select_renamed_item), then closing both
        the prompt and the Edit Project dialog. The prompt stays open on any
        error, with what was typed still in it to fix.

        Closes the Edit Project dialog on success, unlike its Task/Profile
        counterparts, which keep theirs open: those hold a dialog full of
        in-progress editing a rename shouldn't discard, whereas Edit Project's
        remaining content is derived from the name (its title and its "Save as"
        path), and this is the behavior that button has always had.
        """
        old_name = edited_project.project_name

        errors = projedit.apply_edits_to_project(edited_project, new_name, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        projedit.rename_project_in_live_tree(old_name, edited_project, state=self.state)
        refresh_tasker_object_pulldowns(self.gui)
        select_renamed_item(self.gui, "Project", new_name)

        ui.notify(f"Renamed to '{new_name}'.", type="positive")
        rename_dialog.close()
        parent_dialog.close()

    def set_project_enabled_event(self, edited_project: projedit.EditableProject, enabled: bool) -> None:
        """Enables or disables the Project being edited. Unlike its Profile
        counterpart (set_profile_enabled_event), this reaches the live
        in-memory backup immediately -- see projedit.set_project_enabled for
        why the Edit Project dialog has to work that way.
        """
        projedit.set_project_enabled(edited_project, enabled, state=self.state)

    # ----------------------------------------------------------------------------------
    # Object Properties -- the panel Project/Profile/Task/Scene share.  What it edits is
    # in objprops.py and the form is guiwins_props.build_object_properties_dialog; these three
    # are the whole of the wiring.
    # ----------------------------------------------------------------------------------
    def open_object_properties_event(
        self,
        kind: str,
        element: Element,
        parent_dialog: ui.dialog | None,
        on_applied: Callable[[], None] | None = None,
    ) -> None:
        """Open the Properties editor over whichever Add/Edit dialog asked for it."""
        build_object_properties_dialog(self.gui, kind, element, parent_dialog, on_applied)

    def keep_object_properties_event(
        self,
        props: objprops.EditableProperties,
        field_refs: dict,
        dialog: ui.dialog,
        on_applied: Callable[[], None] | None = None,
    ) -> None:
        """Ok: validate, apply onto the element, run the caller's follow-up, close.

        Nothing is written when validation fails and the dialog stays open with the
        messages on it, so a mistyped variable name is corrected rather than retyped from
        scratch -- same contract as keep_edited_task_event.

        No undo checkpoint is taken here.  For a Task or a Profile the edit lands on the
        working copy, where the live configuration has not changed yet and the parent's
        own save is already wrapped.  `on_applied` is where a caller whose element is not
        the whole story puts the rest -- only Edit Project has one, and the checkpoint for
        that path is taken inside it (projedit.apply_properties_to_live_tree).
        """
        values = object_property_values(field_refs)
        errors = objprops.apply_properties(props, values)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        for warning in objprops.warnings(props, values):
            ui.notify(warning, type="warning")

        if on_applied is not None:
            on_applied()

        ui.notify(translate_string("Properties kept."), type="positive")
        dialog.close()

    def apply_project_properties_event(self, edited_project: projedit.EditableProject) -> None:
        """Edit Project's on_applied: carry the properties just written onto the Project
        copy through to the live element, so its two by-name saves and "Save To Current
        File" all see them.  See projedit.apply_properties_to_live_tree, which is where
        the undo checkpoint for this path is taken.

        The Project counterpart of set_project_enabled_event, and immediate for the same
        reason: there is no later moment at which a by-name save could pick this up.
        """
        projedit.apply_properties_to_live_tree(edited_project, state=self.state)

    def cancel_object_properties_event(
        self,
        props: objprops.EditableProperties,
        dialog: ui.dialog,
    ) -> None:
        """Cancel: close without applying, and drop any variable that was added but never
        named -- see objprops.discard_unnamed_variables for why one can be left behind.
        """
        if discarded := objprops.discard_unnamed_variables(props):
            ui.notify(
                translate_string(f"Discarded {discarded} unnamed variable(s)."),
                type="info",
            )
        dialog.close()

    async def save_project_to_current_file_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Project dialog's Name field (same as
        Rename), then writes the *entire* current backup -- not just this
        Project -- out to a new, timestamped copy of whatever file it was
        loaded from (see maputil2.write_full_backup_to_current_file) and
        switches the app over to that copy (see reload_saved_copy_and_refresh)
        -- the original file is left untouched. Mirrors
        save_edited_profile_to_current_file_event/
        save_edited_task_to_current_file_event. Backs the "Save To Current
        File" button. Dialog stays open on any error so the user's
        in-progress edit isn't lost.

        Follows the rename the same way the Rename button does
        (select_renamed_item), so the Project stays selected under its new
        name -- but only after the reload, never before: this path replaces
        every table wholesale by re-parsing the file it just wrote (see
        reload_saved_copy_and_refresh), so a selection made beforehand would
        be pointing at state that no longer exists a moment later. Re-selecting
        matters most here of the three: a Project's identity is its name (see
        rename_project_in_live_tree), so a rename through this button would
        otherwise leave the Project pulldown's .value on a name that's gone.

        Guarded like the dialog's other two saves: the apply below covers the Name and
        nothing else, so a field added without extending it would be left out of the
        backup this writes -- see unapplied_project_edits.
        """
        errors = unapplied_project_edits(field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        old_name = edited_project.project_name
        name_value = field_refs["name"].value.strip()

        errors = projedit.apply_edits_to_project(edited_project, name_value, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        projedit.rename_project_in_live_tree(old_name, edited_project, state=self.state)

        notice = await show_save_in_progress_notice()
        success, result = write_full_backup_to_current_file(state=self.state)
        if not success:
            notice.dismiss()
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = reload_saved_copy_and_refresh(self.gui, result)
        notice.dismiss()
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return

        select_renamed_item(self.gui, "Project", name_value)
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def save_project_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Writes the Project -- every Profile and Task it owns -- out as a
        standalone .prj.xml file (see projedit.write_standalone_project_xml).
        Backs the "Export Project" button.

        Exports under the Project's current, already-applied name
        (edited_project.project_name) regardless of any not-yet-applied edit
        sitting in the Name field -- unlike Rename, this is a read-only export
        and deliberately doesn't also rename the live Project as a side
        effect; use "Rename" first if the new name should carry through.
        Dialog stays open on any error so the user's in-progress edit isn't lost.

        Guarded against a field being added to the dialog without the apply that a
        by-name render would then need -- see unapplied_project_edits.
        """
        errors = unapplied_project_edits(field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        save_path = field_refs["project_save_path"].value.strip()
        redact = redact_requested(field_refs, PROJECT_REDACT_FIELD)

        def _write() -> None:
            try:
                safety_copy = projedit.write_standalone_project_xml(
                    edited_project.project_name, save_path, redact=redact, state=self.state
                )
            except (OSError, ValueError) as e:
                ui.notify(f"Could not save file: {e}", type="negative")
                return

            # The write took a copy of anything already at that path (see presave);
            # say so, so the user knows where it went.
            replaced_note = f" The file it replaced was copied to {safety_copy}." if safety_copy else ""
            ui.notify(
                f"Saved Project '{edited_project.project_name}' to {save_path}.{replaced_note}{redacted_note(redact)}",
                type="positive",
            )
            dialog.close()

        if projedit.save_path_exists(save_path):
            build_overwrite_confirm_dialog(f"'{save_path}'", _write)
            return
        _write()

    def delete_project_event(self, edited_project: projedit.EditableProject, dialog: ui.dialog) -> None:
        """Opens the Delete Project confirmation dialog (Keep Contents / Delete
        Contents), nested inside Edit Project -- see build_delete_project_dialog.
        """
        build_delete_project_dialog(self.gui, edited_project, dialog)

    def keep_contents_delete_project_event(
        self,
        project_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Project, moving its Profiles/Tasks into 'Base'. Backs
        the confirmation dialog's "Keep Contents" button.
        """
        self._finish_delete_project(
            project_name,
            keep_contents=True,
            confirm_dialog=confirm_dialog,
            parent_dialog=parent_dialog,
        )

    def delete_contents_delete_project_event(
        self,
        project_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Project and everything it owns. Backs the confirmation
        dialog's "Delete Contents" button.
        """
        self._finish_delete_project(
            project_name,
            keep_contents=False,
            confirm_dialog=confirm_dialog,
            parent_dialog=parent_dialog,
        )

    def _finish_delete_project(
        self,
        project_name: str,
        *,
        keep_contents: bool,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Shared tail of keep_contents_delete_project_event/
        delete_contents_delete_project_event: applies projedit.delete_project,
        refreshes the pulldowns, resets the (now possibly stale) single-name
        selection, and closes both dialogs. Both dialogs stay open on error
        (e.g. "Base" with keep_contents) so nothing is lost/hidden.
        """
        errors = projedit.delete_project(project_name, keep_contents=keep_contents, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        refresh_tasker_object_pulldowns(self.gui)
        reset_specific_name_selection(self.gui)

        if keep_contents:
            said = f"Deleted '{project_name}'. Its Profiles and Tasks were moved to '{projedit.BASE_PROJECT_NAME}'."
        else:
            said = f"Deleted '{project_name}' and everything it owned."
        ui.notify(said, type="positive")

        confirm_dialog.close()
        parent_dialog.close()
        self._offer_save_after_delete(said)

    # -------------------------------------------------------------------------
    # Scene editing.
    #
    # The Scene arm of the Project/Profile/Task handlers above, and shaped after the
    # Project ones throughout, since a Scene is name-keyed the same way (see
    # sceneedit.py's module docstring).  Every one of these is reachable only when
    # config.EDIT_SCENE is True -- guiwins only builds the two buttons that call in
    # here when it is, and nothing else calls them.
    # -------------------------------------------------------------------------
    def open_add_scene_dialog_event(self) -> None:
        """Backs the "Add Scene" button.  Checks the two things that have to be
        true before a Scene can be added at all -- a Project is selected to attach
        it to (same requirement as Add Profile/Add Task, see
        sceneedit.add_scene_to_project) and a backup is actually parsed -- and then
        asks which kind of Scene to add.

        The Scene itself isn't built here: which kind it is decides how it is
        built, so creation waits for the answer, in add_scene_of_version_event.
        Checking the preconditions first means the user is never asked to choose a
        Scene type only to be told afterwards that nothing was loaded.
        """
        the_view = self.gui
        project_name, no_project_message = project_for_new_object(the_view, "Scene")
        if not project_name:
            ui.notify(no_project_message, type="warning")
            return

        # See open_add_task_dialog_event's identical self-healing load: the toolbar's
        # "Current File" only means a filename is known, not that it's been parsed
        # into PrimeItems.xml_root yet.
        if self.state.xml_root is None:
            if not self.state.file_to_get and getattr(the_view, "file", ""):
                self.state.file_to_get = the_view.file
            if not self.state.file_to_get or get_xml(the_view.debug, the_view.appearance_mode, state=self.state) != 0:
                ui.notify(
                    translate_string("No backup file is currently loaded. Use 'Get Local XML' first."),
                    type="warning",
                )
                return

        build_add_scene_version_dialog(the_view, project_name)

    def add_scene_of_version_event(
        self,
        version: str,
        template: str,
        project_name: str,
        version_dialog: ui.dialog,
    ) -> None:
        """Builds a brand-new Scene of the chosen kind -- and, for Version 2, from the
        chosen template -- then opens the Add Scene dialog on it, closing the prompt behind
        it.  Backs every button on that prompt (see build_add_scene_version_dialog).

        template is ignored for a Legacy Scene, which has only one possible starting shape.

        The prompt stays open if the Scene can't be built, so the choice isn't lost along
        with the error.
        """
        new_scene = sceneedit.create_new_scene(
            "", version, template or scenelayout.V2_DEFAULT_TEMPLATE, state=self.state
        )
        if isinstance(new_scene, str):
            ui.notify(new_scene, type="warning")
            return

        version_dialog.close()
        build_add_scene_dialog(self.gui, new_scene, target_project_name=project_name)

    def keep_new_scene_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Scene dialog's fields, registers the new
        Scene into the live in-memory backup, attaches it to its Project, then
        closes the dialog -- the Add Scene dialog's only save action (no
        standalone file or Save To Android surface, see build_add_scene_dialog).
        Dialog stays open on any error so the user's in-progress work isn't lost.
        """
        name_value = field_refs["name"].value.strip()
        if sceneedit.scene_name_exists(name_value, state=self.state):
            ui.notify(
                f"A Scene named '{name_value}' already exists in this backup. Choose a different name.",
                type="negative",
            )
            return

        errors = sceneedit.apply_edits_to_scene(edited_scene, name_value, state=self.state) + apply_scene_field_values(
            edited_scene,
            field_refs,
        )
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        finish_new_scene(self.gui, edited_scene, field_refs["target_project_name"])

        ui.notify(translate_string("Scene added."), type="positive")
        dialog.close()

    def open_edit_scene_dialog_event(self) -> None:
        """Opens the Edit Scene dialog for the currently selected single Scene name."""
        the_view = self.gui
        scene_name = confirmed_single_scene_name(the_view)
        if not scene_name:
            ui.notify(translate_string("Select a single Scene first (Scene pulldown above)."), type="warning")
            return

        # A preview may be holding this Scene's dialog hidden with edits in it that have not
        # been saved -- an added component lives in the designer's layout dict, not in the
        # tree load_scene_for_edit copies from.  Resume that dialog rather than build a
        # second one, so this button and the preview's "Back to Editor" both come back to
        # the same work in progress instead of disagreeing about what the Scene contains.
        suspended = suspended_scene_editor(the_view, scene_name)
        if suspended is not None:
            suspended.open()
            return

        edited_scene = sceneedit.load_scene_for_edit(scene_name, state=self.state)
        if edited_scene is None:
            ui.notify(f"Could not find Scene '{scene_name}'.", type="negative")
            return

        build_edit_scene_dialog(the_view, edited_scene)

    def preview_scene_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog | None = None,
    ) -> None:
        """Draws the Scene being edited as a picture in the main content column.  Backs the
        "Preview" button on both Scene dialogs (guiwins_scene._build_scene_editor_body).

        The dialog is closed first and handed to the view, which puts a "Back to Editor"
        button up to re-open it.  It has to be: content_container is behind the dialog's
        modal overlay, so a preview drawn with the dialog still up would be invisible.
        Closing a NiceGUI dialog hides it without destroying its widgets, so nothing typed
        into it is lost in the round trip -- which is what makes previewing a size the user
        has typed but not saved worth doing at all.

        Nothing is written to the Scene here, and nothing is validated beyond what the view
        needs to pick a canvas size: this is a read-only look at work in progress, and it
        stays available even while the dialog holds something that would fail to save.
        """
        if dialog is not None:
            # Hidden, not finished: the "Edit Scene" button has to resume this dialog rather
            # than open a fresh one on the unedited tree.  See suspend_scene_editor_session.
            #
            # MARKED BEFORE THE CLOSE, NOT AFTER.  Closing fires the dialog's own value-change
            # handler synchronously, and that handler repaints any preview this dialog left on
            # screen (guiwins_sceneview._scene_dialog_closed).  Marking afterwards would leave it looking
            # at a session that still said "not suspended", so it would take a close *on its
            # way to building a new preview* for a close that had finished with one, and
            # repaint the outgoing view into a container about to be cleared.
            suspend_scene_editor_session(self.gui, dialog)
            dialog.close()
        self.gui.textview = NiceGuiSceneView(self.gui, edited_scene, field_refs, dialog)

    def save_edited_scene_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Applies the Edit Scene dialog's editable fields to the live in-memory
        backup and closes the dialog.  Backs the "Ok" button.

        The Name field is read-only here, so this never renames anything -- Rename
        is its own operation (see confirm_rename_scene_event).  What it does have
        to do, which the Project equivalent does not, is write the edited *copy*
        back into the live tree: the dialog edits a deep copy
        (sceneedit.load_scene_for_edit), so without this the size changes stay in
        the copy and vanish with the dialog.
        """
        errors = apply_scene_field_values(edited_scene, field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        sceneedit.apply_edited_scene_to_live_tree(edited_scene.scene_name, edited_scene, state=self.state)

        ui.notify(f"Saved Scene '{edited_scene.scene_name}'.", type="positive")
        dialog.close()

    def rename_scene_event(
        self,
        edited_scene: sceneedit.EditableScene,
        dialog: ui.dialog,
    ) -> None:
        """Opens the Rename prompt for this Scene, nested inside Edit Scene -- see
        build_rename_dialog.  Backs the "Rename" button; mirrors
        rename_project_event.  The dialog's own Name field is read-only, so the
        prompt is where the new name comes from.
        """
        build_rename_dialog(
            self.gui,
            "Scene",
            edited_scene.scene_name,
            lambda new_name, rename_dialog: self.confirm_rename_scene_event(
                edited_scene,
                new_name,
                rename_dialog,
                dialog,
            ),
        )

    def confirm_rename_scene_event(
        self,
        edited_scene: sceneedit.EditableScene,
        new_name: str,
        rename_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Validates the name typed into the Rename prompt and applies it,
        renaming the Scene in the live in-memory backup -- moving its all_scenes
        entry and rewriting the <scenes> list of every Project that named it (see
        sceneedit.apply_edited_scene_to_live_tree) -- making it the current single
        Scene under that name, then closing both the prompt and the Edit Scene dialog.
        The prompt stays open on any error, with what was typed still in it to fix.

        Closes the Edit Scene dialog on success, for the same reason Edit Project
        does (see confirm_rename_project_event): what remains in it is either
        derived from the name (its title, its "Save as" path) or already applied.
        """
        old_name = edited_scene.scene_name

        errors = sceneedit.apply_edits_to_scene(edited_scene, new_name, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        sceneedit.apply_edited_scene_to_live_tree(old_name, edited_scene, state=self.state)
        refresh_tasker_object_pulldowns(self.gui)
        select_renamed_item(self.gui, "Scene", new_name)

        ui.notify(f"Renamed to '{new_name}'.", type="positive")
        rename_dialog.close()
        parent_dialog.close()

    async def save_scene_to_current_file_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Applies the dialog's editable fields, then writes the *entire* current
        backup -- not just this Scene -- out to a new, timestamped copy of
        whatever file it was loaded from (see
        maputil2.write_full_backup_to_current_file, whose reconciliation now
        covers Scenes too) and switches the app over to that copy (see
        reload_saved_copy_and_refresh) -- the original file is left untouched.
        Mirrors save_project_to_current_file_event.  Dialog stays open on any
        error so the user's in-progress edit isn't lost.

        Re-selects the Scene after the reload, never before: this path replaces
        every table wholesale by re-parsing the file it just wrote, so a selection
        made beforehand would point at state that no longer exists a moment later.
        """
        errors = apply_scene_field_values(edited_scene, field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        sceneedit.apply_edited_scene_to_live_tree(edited_scene.scene_name, edited_scene, state=self.state)

        notice = await show_save_in_progress_notice()
        success, result = write_full_backup_to_current_file(state=self.state)
        if not success:
            notice.dismiss()
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = reload_saved_copy_and_refresh(self.gui, result)
        notice.dismiss()
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return

        select_renamed_item(self.gui, "Scene", edited_scene.scene_name)
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def save_scene_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Applies the Edit Scene dialog's edits, then writes the Scene out as a
        standalone .scn.xml file (see sceneedit.write_standalone_scene_xml).  Backs
        the "Export Scene" button.  Dialog stays open on any error so the user's
        in-progress edit isn't lost.

        THE APPLY IS WHAT MAKES THE FILE CARRY THE USER'S WORK, for the same reason
        it is needed on the Android upload (see save_scene_to_android_event): the
        write renders from the live tree by name, and the dialog edits a deep copy
        whose V2 layout lives in a dict nothing writes back until a save handler
        runs.  Without it a component added a moment ago is simply missing from the
        exported file, with nothing to say so.

        Validating before the overwrite check means a bad field cannot get as far as
        prompting to replace a file it was never going to write.  The Scene is still
        exported under its current name: Rename is its own operation, not a field on
        this dialog, so there is no such thing as an unapplied rename to carry.
        """
        save_path = field_refs["scene_save_path"].value.strip()

        errors = apply_scene_field_values(edited_scene, field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        sceneedit.apply_edited_scene_to_live_tree(edited_scene.scene_name, edited_scene, state=self.state)

        redact = redact_requested(field_refs, SCENE_REDACT_FIELD)

        def _write() -> None:
            try:
                safety_copy = sceneedit.write_standalone_scene_xml(
                    edited_scene.scene_name, save_path, redact=redact, state=self.state
                )
            except (OSError, ValueError) as e:
                ui.notify(f"Could not save file: {e}", type="negative")
                return

            # The write took a copy of anything already at that path (see presave);
            # say so, so the user knows where it went.
            replaced_note = f" The file it replaced was copied to {safety_copy}." if safety_copy else ""
            ui.notify(
                f"Saved Scene '{edited_scene.scene_name}' to {save_path}.{replaced_note}{redacted_note(redact)}",
                type="positive",
            )
            dialog.close()

        if sceneedit.save_path_exists(save_path):
            build_overwrite_confirm_dialog(f"'{save_path}'", _write)
            return
        _write()

    def delete_scene_event(self, edited_scene: sceneedit.EditableScene, dialog: ui.dialog) -> None:
        """Opens the Delete Scene confirmation dialog, nested inside Edit Scene --
        see build_delete_scene_dialog.
        """
        build_delete_scene_dialog(self.gui, edited_scene, dialog)

    def confirm_delete_scene_event(
        self,
        scene_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Scene, along with its entry in every Project that lists it
        (see sceneedit.delete_scene), then refreshes the pulldowns, resets the
        now-stale single-name selection, and closes both dialogs.  Mirrors
        confirm_delete_task_event; both dialogs stay open on error.

        The selection reset is required, not cosmetic: the Scene pulldown is still
        pointing at the name just deleted, and leaving it there would let Edit
        Scene reopen on a Scene that no longer resolves.
        """
        errors = sceneedit.delete_scene(scene_name, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        refresh_tasker_object_pulldowns(self.gui)
        reset_specific_name_selection(self.gui)

        ui.notify(f"Deleted Scene '{scene_name}'.", type="positive")
        confirm_dialog.close()
        parent_dialog.close()
        self._offer_save_after_delete(f"Deleted Scene '{scene_name}'.")

    def open_edit_profile_dialog_event(self) -> None:
        """Opens the Edit Profile dialog for the currently selected single Profile name."""
        the_view = self.gui
        profile_name = getattr(the_view, "single_profile_name", "")
        if not profile_name:
            ui.notify(translate_string("Select a single Profile first (Profile pulldown above)."), type="warning")
            return

        edited_profile = profedit.load_profile_for_edit(profile_name, state=self.state)
        if edited_profile is None:
            ui.notify(f"Could not find Profile '{profile_name}'.", type="negative")
            return

        build_edit_profile_dialog(the_view, edited_profile)

    def rename_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        title_label: ui.label,
    ) -> None:
        """Opens the Rename prompt for this Profile, nested inside Edit Profile
        -- see build_rename_dialog. Backs the "Rename" button; mirrors
        rename_task_event. The dialog's own Name field is read-only, so the
        prompt is where the new name comes from.
        """
        build_rename_dialog(
            self.gui,
            "Profile",
            edited_profile.profile_element.findtext("nme", ""),
            lambda new_name, rename_dialog: self.confirm_rename_profile_event(
                edited_profile,
                field_refs,
                title_label,
                new_name,
                rename_dialog,
            ),
        )

    def confirm_rename_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        title_label: ui.label,
        new_name: str,
        rename_dialog: ui.dialog,
    ) -> None:
        """Validates the name typed into the Rename prompt and, if it's good,
        renames the Profile in the live in-memory backup right away (see
        profedit.rename_profile_in_live_tree), then refreshes the pulldowns and
        re-selects the Profile under its new name, so it stays the current
        single Profile and its pulldown follows the rename (see
        select_renamed_item). Backs the prompt's "Rename" button; mirrors
        confirm_rename_task_event exactly, including leaving the Edit Profile
        dialog open and renaming *only* the name, so the conditions and
        Entry/Exit Task links still being edited stay pending until Ok/Save.
        """
        errors = profedit.apply_profile_rename(edited_profile, new_name, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        old_name = profedit.rename_profile_in_live_tree(edited_profile, state=self.state)
        refresh_tasker_object_pulldowns(self.gui)
        select_renamed_item(self.gui, "Profile", new_name)

        title_label.set_text(f"{translate_string('Edit Profile')}: {new_name}")
        # Keeps Ok/Save from re-applying the pre-rename name -- see
        # confirm_rename_task_event's identical note.
        field_refs["name"].value = new_name
        # Only re-derive the export path if it's still this dialog's default for
        # the old name -- see confirm_rename_task_event's identical guard.
        save_path_field = field_refs.get("save_path")
        if save_path_field is not None and save_path_field.value == profedit.default_save_path(old_name, self.state):
            save_path_field.value = profedit.default_save_path(new_name, self.state)

        ui.notify(f"Renamed to '{new_name}'.", type="positive")
        rename_dialog.close()

    def delete_profile_event(self, edited_profile: profedit.EditableProfile, dialog: ui.dialog) -> None:
        """Opens the Delete Profile confirmation dialog, nested inside Edit
        Profile -- see build_delete_profile_dialog. Mirrors delete_project_event.
        """
        build_delete_profile_dialog(self.gui, edited_profile, dialog)

    def confirm_delete_profile_event(
        self,
        profile_name: str,
        confirm_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Deletes the Profile -- and only the Profile, its Entry/Exit Tasks are
        kept (see profedit.delete_profile) -- then refreshes the pulldowns,
        resets the now-stale single-name selection, and closes both dialogs.
        Backs the confirmation dialog's "Delete Profile" button; mirrors
        _finish_delete_project. Both dialogs stay open on error so nothing is lost.

        The selection reset is required, not cosmetic: the Profile pulldown is
        still pointing at the name just deleted, and leaving it there would let
        Edit Profile reopen on a Profile that no longer resolves.
        """
        errors = profedit.delete_profile(profile_name, state=self.state)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        refresh_tasker_object_pulldowns(self.gui)
        reset_specific_name_selection(self.gui)

        said = f"Deleted Profile '{profile_name}'. Its Tasks were kept."
        ui.notify(said, type="positive")
        confirm_dialog.close()
        parent_dialog.close()
        self._offer_save_after_delete(said)

    def open_add_profile_dialog_event(self) -> None:
        """Opens the Add Profile dialog for a brand-new Profile, attached to the
        currently selected single Project (see the Project pulldown in the
        Specific Name tab, mirrors open_add_task_dialog_event exactly). A
        Project must already be selected -- the new Profile is attached
        directly to it (added to its <pids>, see profedit.add_profile_to_project)
        rather than picked from within the dialog, so there's no other way to
        know which Project it belongs to.
        """
        the_view = self.gui
        project_name, no_project_message = project_for_new_object(the_view, "Profile")
        if not project_name:
            ui.notify(no_project_message, type="warning")
            return

        # See open_add_task_dialog_event's identical self-healing load: the toolbar's
        # "Current File" only means a filename is known, not that it's been parsed
        # into PrimeItems.xml_root yet.
        if self.state.xml_root is None:
            if not self.state.file_to_get and getattr(the_view, "file", ""):
                self.state.file_to_get = the_view.file
            if not self.state.file_to_get or get_xml(the_view.debug, the_view.appearance_mode, state=self.state) != 0:
                ui.notify(
                    translate_string("No backup file is currently loaded. Use 'Get Local XML' first."),
                    type="warning",
                )
                return

        new_profile = profedit.create_new_profile("", state=self.state)
        if isinstance(new_profile, str):
            ui.notify(new_profile, type="warning")
            return

        build_add_profile_dialog(self.gui, new_profile, target_project_name=project_name)

    def link_task_to_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        link_type: str,
        task_name: str,
    ) -> None:
        """Links an existing Task (by name) to the Profile as its Entry or Exit Task."""
        if not task_name:
            ui.notify(translate_string("Choose a Task first."), type="warning")
            return
        resolved = taskedit.resolve_task_by_name(task_name, state=self.state)
        if resolved is None:
            ui.notify(f"Could not find Task '{task_name}'.", type="negative")
            return
        task_id, _ = resolved
        profedit.link_task_to_profile(edited_profile, task_id, link_type)

    def unlink_task_from_profile_event(self, edited_profile: profedit.EditableProfile, link_type: str) -> None:
        """Unlinks the Profile's current Entry or Exit Task."""
        profedit.unlink_task_from_profile(edited_profile, link_type)

    def open_add_task_for_profile_link_event(
        self,
        edited_profile: profedit.EditableProfile,
        link_type: str,
        on_linked: Callable[[], None],
    ) -> None:
        """Opens the Add Task dialog nested inside Edit/Add Profile's Entry/Exit
        Task picker -- the alternative to link_task_to_profile_event picking an
        existing Task. On successful creation (Ok/Save/Save To Android in that
        nested dialog), the new Task is linked in as this Profile's Entry/Exit
        Task and on_linked (the picker's own render_task_links) is called to
        refresh the display -- see build_add_task_dialog's on_task_created.
        """
        new_task = taskedit.create_new_task("", "100", state=self.state)
        if isinstance(new_task, str):
            ui.notify(new_task, type="warning")
            return

        def link_new_task(task_id: str) -> None:
            profedit.link_task_to_profile(edited_profile, task_id, link_type)
            on_linked()

        build_add_task_dialog(self.gui, new_task, on_task_created=link_new_task)

    def set_profile_enabled_event(self, edited_profile: profedit.EditableProfile, enabled: bool) -> None:
        """Enables or disables the Profile being edited."""
        profedit.set_profile_enabled(edited_profile, enabled)

    def add_condition_to_profile_event(self, edited_profile: profedit.EditableProfile, cond_type: str) -> None:
        """Adds a new condition (Time/Day/App/Loc) to the Profile being edited."""
        if not cond_type:
            ui.notify(translate_string("Choose a condition type first."), type="warning")
            return
        result = profedit.add_condition_to_profile(edited_profile, cond_type)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")

    def remove_condition_from_profile_event(self, edited_profile: profedit.EditableProfile, cond_index: int) -> None:
        """Removes a condition from the Profile being edited and renumbers the rest."""
        profedit.remove_condition_from_profile(edited_profile, cond_index)

    def add_event_condition_to_profile_event(self, edited_profile: profedit.EditableProfile, event_key: str) -> None:
        """Synthesizes and appends a new Event condition to the Profile being edited."""
        if not event_key:
            ui.notify(translate_string("Choose an Event type first."), type="warning")
            return
        result = profedit.add_event_condition_to_profile(edited_profile, event_key, state=self.state)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return
        notify_if_plugin_needs_configuration(result.condition_element, profedit.get_condition_display_name(result))

    def add_state_condition_to_profile_event(self, edited_profile: profedit.EditableProfile, state_key: str) -> None:
        """Synthesizes and appends a new State condition to the Profile being edited."""
        if not state_key:
            ui.notify(translate_string("Choose a State type first."), type="warning")
            return
        result = profedit.add_state_condition_to_profile(edited_profile, state_key, state=self.state)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return
        notify_if_plugin_needs_configuration(result.condition_element, profedit.get_condition_display_name(result))

    def add_app_entry_event(self, edited_profile: profedit.EditableProfile, cond_index: int) -> None:
        """Adds a blank app entry to an App condition being edited."""
        condition = profedit.find_condition(edited_profile, cond_index)
        if condition is not None:
            profedit.add_app_entry(condition)

    def remove_app_entry_event(
        self,
        edited_profile: profedit.EditableProfile,
        cond_index: int,
        entry_index: int,
    ) -> None:
        """Removes one app entry from an App condition being edited."""
        condition = profedit.find_condition(edited_profile, cond_index)
        if condition is not None:
            profedit.remove_app_entry(condition, entry_index)

    def save_edited_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Profile dialog's field values, then writes
        the edited Profile out as a standalone .prf.xml file. Dialog stays open on
        any error so the user's in-progress edits aren't lost.
        """
        link_pending_task_pickers(edited_profile, field_refs, state=self.state)
        condition_values = profile_condition_values(field_refs)

        errors = profedit.apply_edits_to_profile(
            edited_profile, field_refs["name"].value, condition_values, state=self.state
        )
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        save_path = field_refs["save_path"].value
        redact = redact_requested(field_refs)

        def _write() -> None:
            try:
                safety_copy = profedit.write_standalone_profile_xml(
                    edited_profile, save_path, redact=redact, state=self.state
                )
            except OSError as e:
                ui.notify(f"Could not save file: {e}", type="negative")
                return

            profedit.apply_edited_profile_to_live_tree(edited_profile, state=self.state)

            # The write took a copy of anything already at that path (see presave);
            # say so, so the user knows where it went.
            replaced_note = f" The file it replaced was copied to {safety_copy}." if safety_copy else ""
            ui.notify(f"Saved to {save_path}.{replaced_note}{redacted_note(redact)}", type="positive")
            dialog.close()

        # Unlike Add Profile's Save, this export had no up-front save_path_exists
        # check (see validate_and_apply_new_profile) -- confirm rather than clobber.
        if profedit.save_path_exists(save_path):
            build_overwrite_confirm_dialog(f"'{save_path}'", _write)
            return
        _write()

    def keep_edited_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Profile dialog's field values into the
        live in-memory backup (same as Save's apply_edited_profile_to_live_tree),
        without writing a standalone file or touching Android, then closes the
        dialog -- backs the "Ok" button, which keeps the edit for this session
        only. Dialog stays open on any error so the user's in-progress edits aren't lost.
        """
        if not apply_edited_profile(edited_profile, field_refs, state=self.state):
            return
        ui.notify(translate_string("Changes kept."), type="positive")
        dialog.close()

    async def save_edited_profile_to_current_file_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Edit Profile dialog's field values (same as
        Ok), then writes the *entire* current backup -- not just this Profile
        -- out to a new, timestamped copy of whatever file it was loaded from
        (see maputil2.write_full_backup_to_current_file) and switches the app
        over to that copy (see reload_saved_copy_and_refresh) -- the original
        file is left untouched. Backs the "Save To Current File" button.
        Dialog stays open on any error so the user's in-progress edits aren't
        lost.

        Re-selects the Profile under whatever name was actually applied, after
        the reload -- same reasoning as
        save_edited_task_to_current_file_event's.
        """
        if not apply_edited_profile(edited_profile, field_refs, state=self.state):
            return
        notice = await show_save_in_progress_notice()
        success, result = write_full_backup_to_current_file(state=self.state)
        if not success:
            notice.dismiss()
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = reload_saved_copy_and_refresh(self.gui, result)
        notice.dismiss()
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return
        if applied_name := edited_profile.profile_element.findtext("nme", ""):
            select_renamed_item(self.gui, "Profile", applied_name)
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def save_new_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Profile dialog's field values, then writes
        the new Profile out as a standalone .prf.xml file. Mirrors
        save_new_task_event exactly. Dialog stays open on any error so the user's
        in-progress work isn't lost.
        """
        ok, name_value, project_name = validate_and_apply_new_profile(
            edited_profile, field_refs, check_save_path=True, state=self.state
        )
        if not ok:
            return

        save_path = field_refs["save_path"].value.strip()
        try:
            safety_copy = profedit.write_standalone_profile_xml(edited_profile, save_path, state=self.state)
        except OSError as e:
            ui.notify(f"Could not save file: {e}", type="negative")
            return

        finish_new_profile(self.gui, edited_profile, name_value, project_name)

        # The write took a copy of anything already at that path (see presave);
        # say so, so the user knows where it went.
        replaced_note = f" The file it replaced was copied to {safety_copy}." if safety_copy else ""
        ui.notify(f"Saved to {save_path}.{replaced_note}", type="positive")
        dialog.close()

    def keep_new_profile_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Profile dialog's field values, then
        registers the new Profile into the live in-memory backup (same as Save's
        register_new_profile), without writing a standalone file, then closes the
        dialog -- backs the "Ok" button, which keeps the new Profile for this
        session only. Mirrors keep_new_task_event exactly. Dialog stays open on
        any error so the user's in-progress work isn't lost. Still checks the
        Profile name for a conflict and that a Project was chosen (needed for
        live-tree registration and Project attachment to make sense -- see
        profedit.add_profile_to_project) but not the save path, since no file
        is written.
        """
        ok, name_value, project_name = validate_and_apply_new_profile(edited_profile, field_refs, state=self.state)
        if not ok:
            return

        finish_new_profile(self.gui, edited_profile, name_value, project_name)

        ui.notify(
            translate_string(
                "Profile kept for this session only -- use 'Save To Current File' to keep it permanently.",
            ),
            type="positive",
        )
        dialog.close()

    async def save_new_profile_to_current_file_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        dialog: ui.dialog,
    ) -> None:
        """Validates and applies the Add Profile dialog's field values,
        registers the new Profile into the live in-memory backup and attaches
        it to its Project, then writes the *entire* current backup out to a
        new, timestamped copy of whatever file it was loaded from (see
        maputil2.write_full_backup_to_current_file) and switches the app over
        to that copy (see reload_saved_copy_and_refresh) -- the original file
        is left untouched -- unlike Save, which exports just this one Profile
        as a standalone file. Backs the "Save To Current File" button. Dialog
        stays open on any error so the user's in-progress work isn't lost; a
        failed disk write is reported but doesn't undo the registration
        already done (same as Ok, which never touches disk at all).
        """
        ok, name_value, project_name = validate_and_apply_new_profile(edited_profile, field_refs, state=self.state)
        if not ok:
            return

        finish_new_profile(self.gui, edited_profile, name_value, project_name)

        notice = await show_save_in_progress_notice()
        success, result = write_full_backup_to_current_file(state=self.state)
        if not success:
            notice.dismiss()
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return
        reload_ok, reload_error = reload_saved_copy_and_refresh(self.gui, result)
        notice.dismiss()
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return
        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()

    def keep_profile_in_loaded_config(
        self,
        edited_profile: profedit.EditableProfile,
        profile_name: str,
        is_new_profile: bool,
        project_name: str,
    ) -> None:
        """Put the edit into MapTasker's own loaded configuration, once the device has it.

        Grouped into one undo step so registering a Profile and attaching it to its Project
        are one thing to take back rather than two -- same reason finish_new_profile does.
        """
        with sessundo.undoable(
            f"Add Profile '{profile_name}'" if is_new_profile else f"Edit Profile '{profile_name}'", state=self.state
        ):
            if is_new_profile:
                profedit.register_new_profile(edited_profile, profile_name, state=self.state)
                profedit.add_profile_to_project(edited_profile, project_name, state=self.state)
            else:
                profedit.apply_edited_profile_to_live_tree(edited_profile, state=self.state)
        refresh_tasker_object_pulldowns(self.gui)

    def open_add_task_dialog_event(self) -> None:
        """Opens the Add Task dialog for a brand-new Task, attached to the
        currently selected single Project (see the Project pulldown in the
        Specific Name tab). A Project must already be selected -- the new
        Task is attached directly to it (added to its <tids>, see
        finish_new_task) rather than through a Profile, so there's no other
        way to know which Project it belongs to.
        """
        the_view = self.gui
        project_name, no_project_message = project_for_new_object(the_view, "Task")
        if not project_name:
            ui.notify(no_project_message, type="warning")
            return

        # The toolbar's "Current File" only means a filename is known (see
        # display_and_set_file) -- it doesn't guarantee the backup has actually been
        # parsed into PrimeItems.xml_root yet (see the same self-healing load in
        # MyGui.__init__). Load it now rather than let create_new_task below
        # confusingly report "no file loaded" while a file is plainly shown.
        if self.state.xml_root is None:
            if not self.state.file_to_get and getattr(the_view, "file", ""):
                self.state.file_to_get = the_view.file
            if not self.state.file_to_get or get_xml(the_view.debug, the_view.appearance_mode, state=self.state) != 0:
                ui.notify(
                    translate_string("No backup file is currently loaded. Use 'Get Local XML' first."),
                    type="warning",
                )
                return

        new_task = taskedit.create_new_task("", "100", state=self.state)
        if isinstance(new_task, str):
            ui.notify(new_task, type="warning")
            return

        build_add_task_dialog(self.gui, new_task, target_project_name=project_name)

    def add_action_to_new_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        action_key: str,
        position: int | None = None,
    ) -> int | None:
        """Synthesizes and inserts a new action into the in-progress new Task,
        at `position` (before/after a specific already-added action) or at the
        end if None -- see build_add_task_dialog's "Position" picker, same as
        add_action_to_edit_task_event's.

        Returns the new action's act_number (so the dialog can highlight it as
        the most recently added), or None if it failed.
        """
        result = taskedit.add_action_to_task(edited_task, action_key, position, state=self.state)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        notify_if_plugin_needs_configuration(result.action_element, result.action_name)
        return result.act_number

    def add_if_block_to_new_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        variant: str,
        position: int | None = None,
    ) -> int | None:
        """Inserts an "If" action -- plus the "Else"/"End If" companions the
        chosen variant calls for (see guiwins_taskedit.build_if_variant_dialog) -- as
        consecutive actions into the in-progress new Task, at `position` or at
        the end if None.

        Returns the new "If" action's act_number (so the dialog can highlight
        it as the most recently added), or None if it failed.
        """
        result = taskedit.add_if_block_to_task(edited_task, variant, position, state=self.state)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        return result.act_number

    def remove_action_from_new_task_event(self, edited_task: taskedit_model.EditableTask, act_number: int) -> None:
        """Removes an action from the in-progress new Task and renumbers the rest."""
        taskedit.remove_action_from_task(edited_task, act_number)

    def delete_action_in_edit_task_event(self, edited_task: taskedit_model.EditableTask, act_number: int) -> None:
        """Removes an action from an existing Task being edited and renumbers the rest."""
        taskedit.remove_action_from_task(edited_task, act_number)

    def add_action_to_edit_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        action_key: str,
        position: int | None,
    ) -> int | None:
        """Synthesizes and inserts a new action into a Task being edited, at
        `position` (before/after a specific existing action) or at the end if
        None -- see taskedit.add_action_to_task and build_edit_task_dialog's
        "Add an action" Position picker.

        Returns the new action's act_number (so the dialog can highlight it as
        the most recently added), or None if it failed.
        """
        result = taskedit.add_action_to_task(edited_task, action_key, position, state=self.state)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        notify_if_plugin_needs_configuration(result.action_element, result.action_name)
        return result.act_number

    def add_if_block_to_edit_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        variant: str,
        position: int | None,
    ) -> int | None:
        """Inserts an "If" action -- plus the "Else"/"End If" companions the
        chosen variant calls for (see guiwins_taskedit.build_if_variant_dialog) -- as
        consecutive actions into a Task being edited, at `position` or at the
        end if None (same semantics as add_action_to_edit_task_event's).

        Returns the new "If" action's act_number (so the dialog can highlight
        it as the most recently added), or None if it failed.
        """
        result = taskedit.add_if_block_to_task(edited_task, variant, position, state=self.state)
        if isinstance(result, list):
            for error in result:
                ui.notify(error, type="negative")
            return None
        return result.act_number

    def copy_action_in_edit_task_event(self, edited_task: taskedit_model.EditableTask, act_number: int) -> None:
        """Duplicates an action (inserted right after the original) in a Task being edited."""
        taskedit.copy_action_in_task(edited_task, act_number, state=self.state)

    def move_action_in_edit_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        act_number: int,
        new_position: int,
    ) -> None:
        """Moves an action to a new position among a Task's other actions."""
        taskedit.move_action_in_task(edited_task, act_number, new_position)

    def set_action_enabled_event(
        self,
        edited_task: taskedit_model.EditableTask,
        act_number: int,
        enabled: bool,
    ) -> None:
        """Enables or disables an action in a Task being edited."""
        taskedit.set_action_enabled(edited_task, act_number, enabled)

    def set_action_continue_after_error_event(
        self,
        edited_task: taskedit_model.EditableTask,
        act_number: int,
        continue_after_error: bool,
    ) -> None:
        """Sets or clears an action's <se>false</se> ('Continue Task After
        Error') -- backs the checkbox of the same name (see
        guiwins_taskedit._render_continue_after_error_checkbox).
        """
        taskedit.set_action_continue_after_error(edited_task, act_number, continue_after_error)

    def set_action_condition_event(
        self,
        edited_task: taskedit_model.EditableTask,
        act_number: int,
        target_input: ui.input,
        operator_select: ui.select,
        value_input: ui.input,
        condition_dialog: ui.dialog,
        checkbox: ui.checkbox,
    ) -> None:
        """Validates and writes a per-action If condition from the prompt's
        field values (see guiwins_taskedit.build_action_condition_dialog), updates the
        "If" checkbox's text to show it, then closes the prompt. The prompt
        stays open on any validation error so the user can correct the fields.
        """
        target = target_input.value or ""
        operator_label = operator_select.value or ""
        value = value_input.value or ""
        errors = taskedit_apply.set_action_condition(edited_task, act_number, target, operator_label, value)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        checkbox.set_text(f"If: {target.strip()} {operator_label} {value.strip()}".rstrip())
        ui.notify(translate_string("If condition set."), type="positive")
        condition_dialog.close()

    def remove_action_condition_event(self, edited_task: taskedit_model.EditableTask, act_number: int) -> None:
        """Removes an action's per-action If condition -- backs unchecking the
        "If" checkbox (idempotent; a no-op if the action has none).
        """
        taskedit_apply.remove_action_condition(edited_task, act_number)

    def save_new_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the Add Task dialog's field values, then writes the
        new Task out as a standalone .tsk.xml file. Dialog stays open on any error
        so the user's in-progress work isn't lost.

        on_created, if given, is called with the new Task's id once it's
        registered -- see build_add_task_dialog's on_task_created.
        """
        ok, name_value = validate_and_apply_new_task(edited_task, field_refs, check_save_path=True, state=self.state)
        if not ok:
            return

        save_path = field_refs["save_path"].value.strip()
        try:
            safety_copy = taskedit_save.write_standalone_task_xml(edited_task, save_path, state=self.state)
        except OSError as e:
            ui.notify(f"Could not save file: {e}", type="negative")
            return

        finish_new_task(self.gui, edited_task, name_value, on_created, field_refs)

        # The write took a copy of anything already at that path (see presave);
        # say so, so the user knows where it went.
        replaced_note = f" The file it replaced was copied to {safety_copy}." if safety_copy else ""
        ui.notify(f"Saved to {save_path}.{replaced_note}", type="positive")
        dialog.close()

    def keep_new_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the Add Task dialog's field values, then registers
        the new Task into the live in-memory backup (same as Save's
        register_new_task), without writing a standalone file, then closes the
        dialog -- backs the "Ok" button, which keeps the new Task for this
        session only. Dialog stays open on any error so the user's in-progress
        work isn't lost. Still checks the Task name for a conflict (needed for
        live-tree registration to make sense) but not the save path, since no
        file is written.

        on_created, if given, is called with the new Task's id once it's
        registered -- see build_add_task_dialog's on_task_created.
        """
        ok, name_value = validate_and_apply_new_task(edited_task, field_refs, state=self.state)
        if not ok:
            return

        finish_new_task(self.gui, edited_task, name_value, on_created, field_refs)

        ui.notify(
            translate_string("Task kept for this session only -- use 'Save To Current File' to keep it permanently."),
            type="positive",
        )
        dialog.close()

    async def save_new_task_to_current_file_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the Add Task dialog's field values, registers
        the new Task into the live in-memory backup, then writes the *entire*
        current backup out to a new, timestamped copy of whatever file it was
        loaded from (see maputil2.write_full_backup_to_current_file) and
        switches the app over to that copy (see
        reload_saved_copy_and_refresh) -- the original file is left
        untouched -- unlike Save, which exports just this one Task as a
        standalone file. Backs the "Save To Current File" button. Dialog
        stays open on any error so the user's in-progress work isn't lost; a
        failed disk write is reported but doesn't undo the registration
        already done (same as Ok, which never touches disk at all).
        """
        ok, name_value = validate_and_apply_new_task(edited_task, field_refs, state=self.state)
        if not ok:
            return

        finish_new_task(self.gui, edited_task, name_value, on_created, field_refs)

        notice = await show_save_in_progress_notice()
        success, result = write_full_backup_to_current_file(state=self.state)
        if not success:
            notice.dismiss()
            ui.notify(f"Could not save to current file: {result}", type="negative")
            return

        reload_ok, reload_error = reload_saved_copy_and_refresh(self.gui, result)
        notice.dismiss()
        if not reload_ok:
            ui.notify(f"Saved a copy to {result}, but failed to load it: {reload_error}", type="warning")
            return

        ui.notify(f"Saved a copy to {result} and loaded it. The original file was left unchanged.", type="positive")
        dialog.close()
