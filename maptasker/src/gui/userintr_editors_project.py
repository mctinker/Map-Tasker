"""The Project editor handlers (and the Properties panel all four kinds share): Add, Edit, Rename, Delete and the saves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core import objprops, tndesc
from maptasker.src.core.maputil2 import translate_string, write_full_backup_to_current_file
from maptasker.src.edit import (
    projedit,
)
from maptasker.src.gui.guiutils import (
    get_xml,
    refresh_tasker_object_pulldowns,
)
from maptasker.src.gui.guiwins_dialogs import (
    build_delete_project_dialog,
    build_overwrite_confirm_dialog,
    build_rename_dialog,
)
from maptasker.src.gui.guiwins_editor import PROJECT_REDACT_FIELD
from maptasker.src.gui.guiwins_project import (
    build_add_project_dialog,
    build_edit_project_dialog,
)
from maptasker.src.gui.guiwins_props import build_object_properties_dialog
from maptasker.src.gui.userintr_fields import (
    confirmed_single_project_name,
    object_property_values,
    redact_requested,
    redacted_note,
    unapplied_project_edits,
)
from maptasker.src.gui.userintr_finish import (
    finish_new_project,
    reload_saved_copy_and_refresh,
    reset_specific_name_selection,
    select_renamed_item,
    show_save_in_progress_notice,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element
from maptasker.src.gui.userintr_editors_base import EditorHandlerBase


class ProjectEditorHandlers(EditorHandlerBase):
    """The Project editor handlers (and the Properties panel all four kinds share): Add, Edit, Rename, Delete and the saves."""

    def open_add_project_dialog_event(self) -> None:
        """Opens the Add Project dialog for a brand-new Project. Unlike Add
        Profile/Add Task, there's no "select a parent first" gate -- a
        Project is the top of the hierarchy, so there's nothing to attach it to.
        """
        the_view = self.gui
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

        new_project = projedit.create_new_project("", state=self.state)
        if isinstance(new_project, str):
            ui.notify(new_project, type="warning")
            return

        build_add_project_dialog(self.gui, new_project)

    def keep_new_project_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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

    def keep_edited_project_event(
        self,
        field_refs: dict[str, Any],
        dialog: ui.dialog,
    ) -> None:
        """Ok in the Edit Project dialog: confirm there is nothing left unapplied, then close.

        Everything this dialog edits -- the Enabled switch, Properties, the TaskerNet description and
        the Launcher Task -- is written to the loaded backup the moment it is changed, so there is
        nothing for Ok to apply.  What it keeps is the guard the dialog's saves have (see
        unapplied_project_edits): a field added later without its apply step fails here with a
        message rather than being closed over.  The dialog stays open on any error.
        """
        if errors := unapplied_project_edits(field_refs):
            for error in errors:
                ui.notify(error, type="negative")
            return
        ui.notify(translate_string("Changes kept."), type="positive")
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

    def keep_taskernet_description_event(
        self,
        element: Element,
        text: str,
        dialog: ui.dialog,
        on_applied: Callable[[], None] | None = None,
        on_kept: Callable[[], None] | None = None,
    ) -> None:
        """Ok in the TaskerNet Description editor: write it onto the element, run the caller's follow-up, close.

        Nothing blocks the Ok -- a description with an unclosed tag is still a description, and
        the editor has been saying so as it was typed -- but a WARNING-grade problem is said
        again here, so it is not walked away from.  No undo checkpoint is taken for a Task or a
        Profile, for the Properties editor's reason: the edit lands on the working copy, where
        the live configuration has not changed yet.  `on_applied` is where Edit Project's
        checkpoint is taken (projedit.apply_share_to_live_tree).
        """
        tndesc.set_description(element, text)
        if on_applied is not None:
            on_applied()
        if on_kept is not None:
            on_kept()

        problems = [issue for issue in tndesc.check(text) if issue.severity == tndesc.WARNING]
        if problems:
            ui.notify(
                translate_string("TaskerNet description kept, but check its HTML:") + f" {problems[0].message}",
                type="warning",
            )
        else:
            ui.notify(translate_string("TaskerNet description kept."), type="positive")
        dialog.close()

    def apply_project_share_event(self, edited_project: projedit.EditableProject) -> None:
        """Edit Project's on_applied for the TaskerNet description: carry it through to the live element.

        Immediate, as apply_project_properties_event is and for the same reason: there is no later
        moment at which a by-name save could pick it up.  See projedit.apply_share_to_live_tree.
        """
        projedit.apply_share_to_live_tree(edited_project, state=self.state)

    def set_project_launcher_event(self, edited_project: projedit.EditableProject, name: str) -> None:
        """Edit Project's Launcher Task pulldown: make `name` the Project's launcher Task, right now.

        Immediate, as set_project_enabled_event is and for the same reason -- see
        projedit.set_project_launcher.  An empty name is the (none) entry and removes it.
        """
        projedit.set_project_launcher(edited_project, name, state=self.state)
        if name:
            ui.notify(f"{translate_string('Launcher Task set to')} '{name}'.", type="positive")
        else:
            ui.notify(translate_string("Launcher Task removed."), type="positive")

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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
