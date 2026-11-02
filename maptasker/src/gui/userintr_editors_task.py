"""The Task editor handlers: Edit, Add, Rename, Delete, and the action list they work on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string, write_full_backup_to_current_file
from maptasker.src.edit import (
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
    build_overwrite_confirm_dialog,
    build_rename_dialog,
)
from maptasker.src.gui.guiwins_taskedit import build_add_task_dialog, build_delete_task_dialog, build_edit_task_dialog
from maptasker.src.gui.guiwins_taskpickers import build_run_task_on_android_dialog
from maptasker.src.gui.userintr_fields import (
    project_for_new_object,
    redact_requested,
    redacted_note,
    task_arg_values,
)
from maptasker.src.gui.userintr_finish import (
    apply_edited_task,
    finish_new_task,
    notify_if_plugin_needs_configuration,
    reload_saved_copy_and_refresh,
    reset_specific_name_selection,
    select_renamed_item,
    show_save_in_progress_notice,
    validate_and_apply_new_task,
)

if TYPE_CHECKING:
    from collections.abc import Callable
from maptasker.src.gui.userintr_editors_base import EditorHandlerBase


class TaskEditorHandlers(EditorHandlerBase):
    """The Task editor handlers: Edit, Add, Rename, Delete, and the action list they work on."""

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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        bound_tasks: dict[str, Any],
        pending_tasks: dict[str, Any],
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

    def create_scene_event_task_event(
        self,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        if not self.state.backup_loaded:
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
