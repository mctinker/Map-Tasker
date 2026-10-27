"""guiwins_project: the Project dialogs -- Add, Edit, and Save To Android.

Each is built into a NiceGUI dialog the Project's own editor opens; the property fields and the Save-To-Android
panel share the scaffolding guiwins holds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core import objprops
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.edit import projedit
from maptasker.src.gui.guiwins import android_device_fields
from maptasker.src.gui.guiwins_editor import (
    PROJECT_REDACT_FIELD,
    PendingChangesBanner,
    _build_properties_button,
    editor_state,
)
from maptasker.src.gui.guiwins_readiness import build_share_checks
from maptasker.src.mapops import readiness

if TYPE_CHECKING:
    from maptasker.src.gui.userintr import MyGui


def build_add_project_dialog(self: MyGui, edited_project: projedit.EditableProject) -> None:
    """Builds and opens the Add Project dialog: create a brand-new Project with
    just a name -- unlike Add Profile/Add Task, there's no parent to attach to
    (a Project is the top of the hierarchy) and no Save/Save To Android surface,
    since a brand-new Project has no Profiles/Tasks attached to it yet -- both
    Save actions export a Project's *existing* <pids>/<tids> contents (see
    projedit.py's module docstring), so there is nothing to export until it's
    been created and has something attached (see build_edit_project_dialog).
    """
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(translate_string("Add Project")).classes("text-xl font-bold text-blue-600")

        field_refs["name"] = ui.input(translate_string("Project Name"), value="").classes("w-full")

        # No on_applied, unlike Edit Project: a Project that does not exist yet has no live
        # element to mirror onto, and register_new_project stores THIS element object
        # rather than a copy of it -- so properties set before the Project exists are
        # already on it once it does.
        _build_properties_button(self, objprops.KIND_PROJECT, edited_project.project_element, dialog)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            add_project_ok = ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.editors.keep_new_project_event(edited_project, field_refs, dialog),
            ).classes("bg-blue-600")
            with add_project_ok:
                ui.tooltip(
                    translate_string(
                        "Adds the new Project to the loaded backup, right now, selects it in the Project pulldown "
                        "and closes this dialog.\n\n"
                        "It is kept for this session only: no file is written and nothing is sent to your Android "
                        "device. To keep it, use 'Save To Current File' in any Edit dialog, which saves the whole "
                        "backup. One press of Undo takes it back.\n\n"
                        "If the name is empty or another Project already has it, the dialog stays open and says "
                        "why, so your work is not lost.",
                    ),
                ).style("white-space: pre-wrap")

    dialog.open()


# The Edit Project dialog's field_refs keys that hold no editable Project state, and so
# need nothing applied before a save.  "name" is read-only (Rename is its own operation),
# and "project_save_path" is where the export goes rather than anything about the Project.
#
# THIS IS A LIST OF WHAT IS SAFE, checked at save time by userintr_fields.unapplied_project_edits,
# because both of this dialog's saves render the Project from the LIVE TREE by name --
# projedit.write_standalone_project_xml(project_name, ...) and .save_project_to_android(
# project_name, ...).  A field added here that edits the Project would therefore be dropped
# silently from the exported file and the upload, which is the bug Scene had (see
# userintr_android.save_scene_to_android_event).  Anything added to field_refs and not named here
# fails the save with a message naming the field, rather than writing an incomplete Project.
#
# Adding a real editable field means applying it before those two saves -- follow what the
# Scene handlers do -- and only then listing its key here.
EDIT_PROJECT_INERT_FIELDS: frozenset[str] = frozenset({"name", "project_save_path", PROJECT_REDACT_FIELD})


def _build_edit_project_fields(
    self: MyGui,
    edited_project: projedit.EditableProject,
    field_refs: dict[str, Any],
    dialog: ui.dialog,
) -> None:
    """The Edit Project dialog's title and fields: Name, the Enabled switch, Properties, Save as and the share checks.

    Built into whatever card is open when this is called; the by-name save buttons that follow
    (see _build_edit_project_buttons) read field_refs, so the fields register themselves in it.
    """
    project_name = edited_project.project_name
    ui.label(f"{translate_string('Edit Project')}: {project_name}").classes("text-xl font-bold text-blue-600")

    # Read-only -- renamed only through the Rename button's prompt; see
    # guiwins_taskedit.build_edit_task_dialog's identical Name field for why.
    field_refs["name"] = (
        ui.input(translate_string("Project Name"), value=project_name).props("readonly").classes("w-full")
    )

    # Enabled/Disabled, presented exactly as Edit Profile offers it (see
    # guiwins_profedit._build_profile_editor_body's identical switch).  What it writes is not the
    # same though: a Project is disabled by <enbl>false</enbl>, not by the
    # <limit>true</limit> a Profile uses -- see projedit.is_project_enabled.
    #
    # Deliberately NOT registered in field_refs: projedit.set_project_enabled writes
    # straight through to the live Project element the moment the switch is flipped,
    # the way Rename and Delete here already do, so there is nothing left for a save
    # to apply.  Putting it in field_refs would instead trip _unapplied_project_edits
    # (see EDIT_PROJECT_INERT_FIELDS above) -- correctly, since that guard has no way
    # to tell an already-applied field from an unapplied one.
    enabled_switch = ui.switch(
        value=projedit.is_project_enabled(edited_project),
        on_change=lambda e: self.event_handlers.editors.set_project_enabled_event(edited_project, bool(e.value)),
    ).classes("mt-2")
    enabled_switch.bind_text_from(enabled_switch, "value", backward=lambda v: "Enabled" if v else "Disabled")
    with enabled_switch:
        ui.tooltip(
            translate_string(
                "Disables the Project in the loaded backup, right now -- like Rename, this takes "
                "effect immediately rather than waiting for a save, and Cancel does not undo it.",
            ),
        )

    # Applied to the working copy AND mirrored onto the live element the moment Ok is
    # pressed -- see projedit.apply_properties_to_live_tree for why both, and why this
    # cannot wait for a save the way Task's and Profile's do.  That immediacy is what
    # keeps it out of field_refs and therefore clear of _unapplied_project_edits: by
    # the time either by-name save runs, there is nothing left unapplied.
    _build_properties_button(
        self,
        objprops.KIND_PROJECT,
        edited_project.project_element,
        dialog,
        on_applied=lambda: self.event_handlers.editors.apply_project_properties_event(edited_project),
    )

    field_refs["project_save_path"] = ui.input(
        translate_string("Save as"),
        value=projedit.default_project_save_path(project_name, self.state),
    ).classes("w-full mt-2")
    build_share_checks(field_refs, PROJECT_REDACT_FIELD, readiness.check_project, project_name, self.state)

    # This dialog has no field that waits for a save -- the Name is read-only and the
    # "Save as" path is not part of the Project (see PENDING_CHANGES_IGNORED_FIELDS) --
    # so what raises the message here is the Enabled toggle, which writes <enbl> onto
    # the copy as it is flipped.  That is still something to save: it is in the loaded
    # backup and in no file, which is what the message says.  Rename is the other
    # immediate change and cannot leave one behind, because it closes this dialog
    # (confirm_rename_project_event).
    pending_changes = PendingChangesBanner()
    pending_changes.watch(dialog, lambda: editor_state(edited_project.project_element, field_refs))


def _build_edit_project_buttons(
    self: MyGui,
    edited_project: projedit.EditableProject,
    field_refs: dict[str, Any],
    dialog: ui.dialog,
) -> None:
    """The Edit Project dialog's button row: Cancel, Delete, Rename, the two saves and Export."""
    with ui.row().classes("w-full justify-end gap-2 mt-4"):
        ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
        ui.button(
            translate_string("Delete Project"),
            on_click=lambda: self.event_handlers.editors.delete_project_event(edited_project, dialog),
        ).classes("bg-red-500 text-white")
        rename_project_button = ui.button(
            translate_string("Rename"),
            on_click=lambda: self.event_handlers.editors.rename_project_event(edited_project, dialog),
        ).classes("bg-blue-600")
        with rename_project_button:
            ui.tooltip(
                translate_string(
                    "Prompts for a new name and applies it to the loaded backup, right now. "
                    "The Project Name field above is read-only -- this is the only way to change it.",
                ),
            )
        project_to_current_file = ui.button(
            translate_string("Save To Current File"),
            on_click=lambda: self.event_handlers.editors.save_project_to_current_file_event(
                edited_project,
                field_refs,
                dialog,
            ),
        ).props("outline")
        with project_to_current_file:
            ui.tooltip(
                translate_string(
                    "Saves the entire backup -- every Project, Profile and Task in it, not just this Project -- "
                    "including every edit made anywhere in this session.\n"
                    "It is written to a new, timestamped copy of the file currently loaded: "
                    "backup.xml becomes backup_20260728_143005.xml.\n"
                    "The file you loaded is never written to, so it is left exactly as it was.\n"
                    "The app then switches to the new copy, which becomes the current file for any further "
                    "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                    "This writes to this computer only -- nothing is sent to your Android device.",
                ),
            ).style("white-space: pre-wrap")
        project_to_android = ui.button(
            translate_string("Save To Android"),
            on_click=lambda: self.event_handlers.android.open_save_project_to_android_dialog_event(
                edited_project,
                field_refs,
                dialog,
            ),
        ).props("outline")
        with project_to_android:
            ui.tooltip(
                translate_string(
                    "This will write the Project, and everything in it -- every Profile and Task -- as a "
                    "standalone file onto your Android device, under /Tasker/projects -- it does not import "
                    "it into Tasker's live configuration.\n\n"
                    "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                    "device, with the server running.\n\n"
                    "The Android device must be on the same network, and the IP Address and Port must "
                    "match its Tasker server settings.\n\n"
                    "Watch the Android device while this runs: Tasker asks you to authorize the "
                    "connection several times for one save, and a prompt left untapped fails it.",
                ),
            ).style("white-space: pre-wrap")
        save_single_project = ui.button(
            translate_string("Export Project"),
            on_click=lambda: self.event_handlers.editors.save_project_event(edited_project, field_refs, dialog),
        ).classes("bg-blue-600")
        with save_single_project:
            ui.tooltip(
                translate_string(
                    "Saves this Project, and everything in it -- every Profile and Task -- as one standalone file.",
                ),
            )


def build_edit_project_dialog(self: MyGui, edited_project: projedit.EditableProject) -> None:
    """Builds and opens the Edit Project dialog: Rename the Project (the Name
    field is read-only -- Rename prompts for the new one, see build_rename_dialog),
    enable/disable it (projedit.set_project_enabled, the Project counterpart of the
    Enabled/Disabled switch Edit Profile has), delete it -- with a choice of what
    happens to the Profiles/Tasks it owns, see
    build_delete_project_dialog -- or save it, and everything it owns, as one
    standalone .prj.xml file, either locally (projedit.write_standalone_project_xml)
    or onto the Android device under /Tasker/projects (projedit.save_project_to_android,
    see build_save_project_to_android_dialog). Unlike Add Project, there IS content to
    save here -- an already-registered Project has whatever Profiles/Tasks are attached
    to it, which is exactly why Add Project has no equivalent button (see its docstring).
    """
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        _build_edit_project_fields(self, edited_project, field_refs, dialog)
        _build_edit_project_buttons(self, edited_project, field_refs, dialog)

    dialog.open()


def build_save_project_to_android_dialog(
    self: MyGui,
    edited_project: projedit.EditableProject,
    field_refs: dict[str, Any],
    parent_dialog: ui.dialog,
) -> None:
    """Prompts for the Android device's IP address and port, then writes the
    Project -- under its current, already-applied name (edited_project.project_name,
    same convention as save_project_event's local export; a not-yet-applied Rename
    edit doesn't carry through) -- as a standalone .prj.xml file onto the device's
    storage under /Tasker/projects, via the Tasker HTTP Server Example's /upload
    endpoint -- see projedit.save_project_to_android. This does not import it into
    Tasker's live configuration. On success both this prompt and the parent (Edit
    Project) dialog are closed.

    field_refs is the parent dialog's, carried through only so the save handler can
    check it for editable fields this by-name upload would drop -- see
    EDIT_PROJECT_INERT_FIELDS. Nothing here reads it.
    """
    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Project To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = android_device_fields(self)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.android.save_project_to_android_event(
                    edited_project,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            with save_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Project, and everything in it, as a standalone file onto the "
                        "Android device, under /Tasker/projects.\n\n"
                        "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            # The Profile dialog's pair, for a Project -- see
            # guiwins_profedit.build_save_profile_to_android_dialog for why these are two buttons and not one
            # with a checkbox.
            import_into_tasker = ui.button(
                translate_string("Import Into Tasker"),
                on_click=lambda: self.event_handlers.android.import_project_into_tasker_event(
                    edited_project,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with import_into_tasker:
                ui.tooltip(
                    translate_string(
                        "This copies the Project -- and every Profile and Task in it -- to the device and "
                        "opens Android's 'Open with...' chooser for it.  Pick Tasker, and its own import "
                        "screen comes up; you then tap Import to finish, and nothing is imported until you "
                        "do.\n\n"
                        "The Project is copied to /Tasker/projects under its own name first and offered "
                        "from there, so it stays behind under a name you can find -- import it by hand "
                        "from Tasker if the import screen does not come up.  You will be asked before it "
                        "replaces a file already at that path.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and running, and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The device will ask you to authorize MapTasker the first time.",
                    ),
                ).style("white-space: pre-wrap")

    android_dialog.open()
