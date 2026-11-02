"""The Scene editor handlers: Add, Edit, Preview, Rename, Delete and the saves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core import scenelayout
from maptasker.src.core.maputil2 import translate_string, write_full_backup_to_current_file
from maptasker.src.edit import (
    sceneedit,
    sceneedit_legacy,
)
from maptasker.src.gui.guiutils import (
    get_xml,
    refresh_tasker_object_pulldowns,
)
from maptasker.src.gui.guiwins_dialogs import (
    build_overwrite_confirm_dialog,
    build_rename_dialog,
)
from maptasker.src.gui.guiwins_editor import SCENE_REDACT_FIELD
from maptasker.src.gui.guiwins_scene import (
    build_add_scene_dialog,
    build_add_scene_version_dialog,
    build_delete_scene_dialog,
    build_edit_scene_dialog,
)
from maptasker.src.gui.guiwins_sceneview import NiceGuiSceneView, suspend_scene_editor_session, suspended_scene_editor
from maptasker.src.gui.userintr_editors_base import EditorHandlerBase
from maptasker.src.gui.userintr_fields import (
    apply_scene_field_values,
    confirmed_single_scene_name,
    finish_new_scene,
    project_for_new_object,
    redact_requested,
    redacted_note,
)
from maptasker.src.gui.userintr_finish import (
    reload_saved_copy_and_refresh,
    reset_specific_name_selection,
    select_renamed_item,
    show_save_in_progress_notice,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


class SceneEditorHandlers(EditorHandlerBase):
    """The Scene editor handlers: Add, Edit, Preview, Rename, Delete and the saves."""

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
        if not self.state.backup_loaded:
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
            # screen (guiwins_sceneview.scene_dialog_closed).  Marking afterwards would leave it looking
            # at a session that still said "not suspended", so it would take a close *on its
            # way to building a new preview* for a close that had finished with one, and
            # repaint the outgoing view into a container about to be cleared.
            suspend_scene_editor_session(self.gui, dialog)
            dialog.close()
        self.gui.textview = NiceGuiSceneView(self.gui, edited_scene, field_refs, dialog)

    def save_edited_scene_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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
        field_refs: dict[str, Any],
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

    def discard_scene_properties_event(
        self,
        scene_element: Element,
        properties_snapshot: Element | None,
        geometry_snapshot: dict[str, Any],
        field_refs: dict[str, Any],
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
