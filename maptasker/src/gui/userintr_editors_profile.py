"""The Profile editor handlers: Add, Edit, Rename, Delete, its conditions, linked Tasks and the saves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string, write_full_backup_to_current_file
from maptasker.src.edit import (
    profedit,
    sessundo,
    taskedit,
)
from maptasker.src.gui.guiutils import (
    get_xml,
    refresh_tasker_object_pulldowns,
)
from maptasker.src.gui.guiwins_dialogs import (
    build_overwrite_confirm_dialog,
    build_rename_dialog,
)
from maptasker.src.gui.guiwins_profedit import (
    build_add_profile_dialog,
    build_delete_profile_dialog,
    build_edit_profile_dialog,
)
from maptasker.src.gui.guiwins_taskedit import build_add_task_dialog
from maptasker.src.gui.userintr_fields import (
    link_pending_task_pickers,
    profile_condition_values,
    project_for_new_object,
    redact_requested,
    redacted_note,
)
from maptasker.src.gui.userintr_finish import (
    apply_edited_profile,
    finish_new_profile,
    notify_if_plugin_needs_configuration,
    reload_saved_copy_and_refresh,
    reset_specific_name_selection,
    select_renamed_item,
    show_save_in_progress_notice,
    validate_and_apply_new_profile,
)

if TYPE_CHECKING:
    from collections.abc import Callable
from maptasker.src.gui.userintr_editors_base import EditorHandlerBase


class ProfileEditorHandlers(EditorHandlerBase):
    """The Profile editor handlers: Add, Edit, Rename, Delete, its conditions, linked Tasks and the saves."""

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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        if not self.state.backup_loaded:
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
