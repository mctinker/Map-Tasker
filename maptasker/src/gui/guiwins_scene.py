"""guiwins_scene: the Scene dialogs -- Add, Edit, Delete, and Save To Android.

The Add dialog asks which version of Scene to create (Legacy or Version 2); Edit's body is the same fields for
both.  The designers themselves are guiwins_designer_legacy and guiwins_designer_v2."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core import scenelayout
from maptasker.src.core.mapjump import SCENE
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.edit import sceneedit, sceneedit_legacy, scenemodel
from maptasker.src.gui.guiwins import android_device_fields
from maptasker.src.gui.guiwins_designers import designer_for
from maptasker.src.gui.guiwins_editor import SCENE_REDACT_FIELD, PendingChangesBanner, editor_state
from maptasker.src.gui.guiwins_impact import build_impact_panel
from maptasker.src.gui.guiwins_readiness import build_share_checks
from maptasker.src.gui.guiwins_sceneview import _scene_dialog_closed
from maptasker.src.mapops import readiness

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


# Indexes into actiont.lookup_values["PropertyElement1"] == ("Overlay", "Dialog", "Activity").
_SCENE_TYPE_OVERLAY = sceneedit_legacy.LEGACY_SCENE_TYPE_OVERLAY


def _build_scene_editor_body(
    _self: MyGui,
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    dialog: ui.dialog | None = None,
    *,
    state: RunState,
) -> None:
    """Renders the editable body shared by the Add Scene and Edit Scene dialogs --
    the Scene sibling of _build_profile_editor_body/the Task dialog's action list.
    Both callers supply their own Name field and their own button row; everything
    between the two is this.

    Asks guiwins_designers which designer the Scene's kind gets, and mounts it below the name.
    The two kinds have almost nothing in common there -- a Legacy Scene has editable size fields
    and a canvas, a Version 2 Scene a component tree and no size at all -- so everything that
    differs lives with the designer (see LegacyDesigner and V2Designer), and this function's job
    is only the part both share: the Scene's kind, and the Preview button.

    Every widget it puts in field_refs is read back by
    userintr_fields.apply_scene_field_values, which is the only thing that has to grow
    alongside it.

    `dialog` is the dialog this body is being built into, and is needed only by the
    Preview button: previewing has to close the dialog to get at the screen behind
    it, so it needs something to re-open afterwards (see NiceGuiSceneView).  It is
    optional so that a caller that has no dialog to hand still gets the whole body,
    minus that one button.
    """
    scene_element = edited_scene.scene_element
    designer = designer_for(scene_element)

    with ui.row().classes("w-full items-center gap-2 mt-1"):
        ui.label(
            f"{translate_string('Scene type')}: {translate_string(scenemodel.scene_version(scene_element))}",
        ).classes("text-sm text-gray-500 italic")
        ui.space()
        preview_button = ui.button(
            translate_string("Preview"),
            icon="visibility",
            on_click=lambda: _self.event_handlers.preview_scene_event(edited_scene, field_refs, dialog),
        ).props("dense outline")
        if dialog is not None:
            # Whatever this dialog changes, the picture it opened has to hear about when it
            # closes -- see repaint_scene_previews.  Registered here, beside the button that
            # creates that picture, so the Add and Edit dialogs both get it from the one
            # place that knows a preview is possible at all.
            dialog.on_value_change(lambda event: _scene_dialog_closed(_self, dialog, field_refs, event))
        with preview_button:
            # What the preview is drawing from differs by kind -- the size typed into the fields
            # below, or a screen the preview itself offers -- so each designer says which.
            ui.tooltip(translate_string(designer.preview_tooltip)).style("white-space: pre-wrap")

    designer.build_body(_self, edited_scene, field_refs, dialog, state)


def build_add_scene_version_dialog(self: MyGui, target_project_name: str) -> None:
    """Asks which kind of Scene to add -- Legacy or Version 2 -- and is what the
    "Add Scene" button actually opens; the Add Scene dialog itself comes second,
    once the answer is known (see userintr_editors.add_scene_of_version_event).

    The choice is made up front, in its own prompt, rather than as a toggle
    inside the Add Scene dialog, because it isn't a field of the Scene -- it
    decides what the Scene *is*, and therefore what that dialog can even show:
    a Legacy Scene has a pixel canvas and an element list, a V2 Scene has a
    component tree and no canvas at all (see _build_scene_editor_body, which
    branches on exactly this).  A toggle would have to tear down and rebuild the
    whole dialog body on every flip, and would let someone type a Scene's details
    and then change what kind of Scene they were describing.

    There is no equivalent prompt on Edit Scene: an existing Scene's kind is a
    property of the Scene, not a choice, and Tasker offers no conversion between
    the two -- the layouts have nothing in common (x/y geometry vs. declarative
    components), so there is nothing this app could honestly convert.
    """
    with ui.dialog().props("persistent") as version_dialog, ui.card().classes("min-w-[450px] max-w-[650px] w-full p-6"):
        ui.label(translate_string("Add Scene")).classes("text-xl font-bold text-blue-600")
        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )
        ui.label(translate_string("Which kind of Scene?")).classes("text-base mt-3")

        # Legacy is one choice; Version 2 is four, because for a component tree "what do I
        # start from" is the same question as "which kind" -- an empty Column and a titled
        # dialog are different enough that asking separately, after the fact, would mean
        # answering the more consequential half second.
        ui.label(translate_string("Legacy")).classes("text-sm font-semibold mt-2")
        ui.label(
            translate_string(
                "The original Scene: UI elements placed at fixed positions on a sized canvas "
                "(Text, Button, Rect, Image, Web, ...).",
            ),
        ).classes("text-xs text-gray-500")
        legacy = ui.button(
            translate_string("Legacy Scene"),
            on_click=lambda: self.event_handlers.add_scene_of_version_event(
                scenemodel.SCENE_VERSION_LEGACY,
                "",
                target_project_name,
                version_dialog,
            ),
        ).classes("bg-blue-600 mt-1")
        with legacy:
            ui.tooltip(
                translate_string(
                    "A Legacy Scene has a pixel canvas and a list of UI elements. It is the "
                    "original Scene format, and is what Tasker itself produces.",
                ),
            )

        ui.label(translate_string("Version 2")).classes("text-sm font-semibold mt-4")
        ui.label(
            translate_string(
                "Tasker's Screen Builder: a declarative component tree (Column, Row, Scaffold, ...) "
                "that lays itself out, with no fixed canvas size. Start from:",
            ),
        ).classes("text-xs text-gray-500")
        with ui.column().classes("w-full gap-1 mt-1"):
            for label, description, _builder in scenelayout.V2_TEMPLATES:
                with ui.row().classes("w-full items-center gap-2"):
                    # Bind the loop variable per iteration -- a bare closure over `label`
                    # would hand every button the last one.
                    ui.button(
                        translate_string(label),
                        on_click=lambda _e=None, chosen=label: self.event_handlers.add_scene_of_version_event(
                            scenemodel.SCENE_VERSION_V2,
                            chosen,
                            target_project_name,
                            version_dialog,
                        ),
                    ).classes("bg-blue-600 w-48")
                    ui.label(translate_string(description)).classes("text-xs text-gray-500")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=version_dialog.close).props("outline")

    version_dialog.open()


def build_add_scene_dialog(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    target_project_name: str,
) -> None:
    """Builds and opens the Add Scene dialog for a Scene of the kind already
    chosen in build_add_scene_version_dialog: create it, empty, and attach it to
    the currently selected Project.  edited_scene arrives already built as Legacy
    or V2 (sceneedit.create_new_scene), and the body renders itself accordingly --
    nothing here has to know which it got.

    A Project is required, for the same reason Add Profile/Add Task require one:
    a Scene only shows up in the Map/Diagram/Tree views if some Project's <scenes>
    element names it (scenes.process_project_scenes reads exactly that -- not the
    all_scenes lookup table sceneedit.register_new_scene populates), so a Scene
    registered without one exists but is invisible everywhere except the Scene
    pulldown.  See sceneedit.add_scene_to_project.

    Like Add Project, there is no Save/Export surface here -- a Scene that was
    created a moment ago has nothing in it to export.  Create it, then use Edit
    Scene, which does (see build_edit_scene_dialog).
    """
    field_refs: dict = {"target_project_name": target_project_name}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[800px] w-full p-6"):
        ui.label(
            f"{translate_string('Add Scene')}: {translate_string(scenemodel.scene_version(edited_scene.scene_element))}",
        ).classes("text-xl font-bold text-blue-600")

        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )

        field_refs["name"] = ui.input(translate_string("Scene Name"), value="").classes("w-full")

        _build_scene_editor_body(self, edited_scene, field_refs, dialog, state=self.state)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_scene_event(edited_scene, field_refs, dialog),
            ).classes("bg-blue-600")

    dialog.open()


def _build_edit_scene_fields(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    dialog: ui.dialog,
) -> None:
    """The Edit Scene dialog's title and fields: Name, the designers, Save as and the share checks.

    Built into whatever card is open when this is called; the saves that follow
    (see _build_edit_scene_buttons) read field_refs, so the fields register themselves in it.
    """
    scene_name = edited_scene.scene_name
    ui.label(f"{translate_string('Edit Scene')}: {scene_name}").classes("text-xl font-bold text-blue-600")
    # The kind of Scene is stated in the body too (see _build_scene_editor_body); it
    # is here as well because it is why the body looks the way it does.

    # Read-only -- renamed only through the Rename button's prompt; see
    # build_edit_project_dialog's identical Name field for why.
    field_refs["name"] = ui.input(translate_string("Scene Name"), value=scene_name).props("readonly").classes("w-full")

    _build_scene_editor_body(self, edited_scene, field_refs, dialog, state=self.state)

    field_refs["scene_save_path"] = ui.input(
        translate_string("Save as"),
        value=sceneedit.default_scene_save_path(scene_name, self.state),
    ).classes("w-full mt-2")
    build_share_checks(field_refs, SCENE_REDACT_FIELD, readiness.check_scene, scene_name, self.state)

    # The two Scene-only pieces of state, for the same reason revert_session has to take
    # them separately: a Version 2 session leaves the element alone from beginning to end
    # -- its work is in the decoded layout dict until a save encodes it back into <lj> --
    # so comparing elements alone would call a reordered, retyped, half-rebuilt V2 Scene
    # unchanged; and element_renames is a list of renames held pending against the live
    # Tasks, which is unsaved work by definition.  Both are reduced to their repr here
    # because the value has to be a snapshot: the dict is the live one the designer goes
    # on editing, so keeping it would only ever be compared against itself.
    pending_changes = PendingChangesBanner()
    pending_changes.watch(
        dialog,
        lambda: editor_state(
            edited_scene.scene_element,
            field_refs,
            repr(field_refs.get("v2_layout")),
            repr(edited_scene.element_renames),
        ),
    )


def _build_edit_scene_buttons(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    dialog: ui.dialog,
    cancel: Callable[[], None],
) -> None:
    """The Edit Scene dialog's button row: Cancel, Delete, Rename, Ok, the two saves and Export."""
    with ui.row().classes("w-full justify-end gap-2 mt-4"):
        cancel_button = ui.button(translate_string("Cancel"), on_click=cancel).props("outline")
        with cancel_button:
            ui.tooltip(
                translate_string(
                    "Closes without saving, and puts this Scene back exactly as it was when this "
                    "dialog opened -- including anything moved or resized in the Preview.\n\n"
                    "A Rename is the one thing this cannot take back: it is applied to the loaded "
                    "backup as it is confirmed, and closes this dialog with it.",
                ),
            ).style("white-space: pre-wrap")
        ui.button(
            translate_string("Delete Scene"),
            on_click=lambda: self.event_handlers.delete_scene_event(edited_scene, dialog),
        ).classes("bg-red-500 text-white")
        rename_scene_button = ui.button(
            translate_string("Rename"),
            on_click=lambda: self.event_handlers.rename_scene_event(edited_scene, dialog),
        ).classes("bg-blue-600")
        with rename_scene_button:
            ui.tooltip(
                translate_string(
                    "Prompts for a new name and applies it to the loaded backup, right now -- "
                    "renaming the Scene everywhere, including in the Scene list of every Project "
                    "that holds it.\n\n"
                    "Tasks that show or hide this Scene by name are NOT updated; those still name "
                    "the old Scene.\n\n"
                    "The Scene Name field above is read-only -- this is the only way to change it.",
                ),
            ).style("white-space: pre-wrap")
        ui.button(
            translate_string("Ok"),
            on_click=lambda: self.event_handlers.save_edited_scene_event(edited_scene, field_refs, dialog),
        ).props("outline")
        scene_to_current_file = ui.button(
            translate_string("Save To Current File"),
            on_click=lambda: self.event_handlers.save_scene_to_current_file_event(
                edited_scene,
                field_refs,
                dialog,
            ),
        ).props("outline")
        with scene_to_current_file:
            ui.tooltip(
                translate_string(
                    "Saves the entire backup -- every Project, Profile, Task and Scene in it, not just this "
                    "Scene -- including every edit made anywhere in this session.\n"
                    "It is written to a new, timestamped copy of the file currently loaded: "
                    "backup.xml becomes backup_20260728_143005.xml.\n"
                    "The file you loaded is never written to, so it is left exactly as it was.\n"
                    "The app then switches to the new copy, which becomes the current file for any further "
                    "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                    "This writes to this computer only -- nothing is sent to your Android device.",
                ),
            ).style("white-space: pre-wrap")
        scene_to_android = ui.button(
            translate_string("Save To Android"),
            on_click=lambda: self.event_handlers.open_save_scene_to_android_dialog_event(
                edited_scene,
                field_refs,
                dialog,
            ),
        ).props("outline")
        with scene_to_android:
            ui.tooltip(
                translate_string(
                    "This will write the Scene as a standalone file onto your Android device, under "
                    "/Tasker/scenes -- it does not import it into Tasker's live configuration.\n\n"
                    "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                    "device, with the server running.\n\n"
                    "The Android device must be on the same network, and the IP Address and Port must "
                    "match its Tasker server settings.\n\n"
                    "Watch the Android device while this runs: Tasker asks you to authorize the "
                    "connection several times for one save, and a prompt left untapped fails it.",
                ),
            ).style("white-space: pre-wrap")
        export_scene = ui.button(
            translate_string("Export Scene"),
            on_click=lambda: self.event_handlers.save_scene_event(edited_scene, field_refs, dialog),
        ).classes("bg-blue-600")
        with export_scene:
            ui.tooltip(
                translate_string(
                    "Saves this Scene, with all of its elements, as one standalone .scn.xml file -- the same "
                    "format Tasker's own Scene export produces.\n\n"
                    "Tasks the Scene's elements run are not included; they belong to their own Project.",
                ),
            ).style("white-space: pre-wrap")


def build_edit_scene_dialog(self: MyGui, edited_scene: sceneedit.EditableScene) -> None:
    """Builds and opens the Edit Scene dialog: edit the Scene's size, rename it
    (the Name field is read-only -- Rename prompts for the new one, see
    build_rename_dialog), delete it -- removing it from every Project that lists
    it, see build_delete_scene_dialog -- or save it, either as a standalone
    .scn.xml file (sceneedit.write_standalone_scene_xml), back into a timestamped
    copy of the whole backup, or onto the Android device under /Tasker/scenes
    (see build_save_scene_to_android_dialog).

    Rename gets its own prompt here rather than a live Name field for the reason
    it does everywhere else, and then some: a Scene's name is its identity in
    four places at once (see sceneedit.py's module docstring), so applying one is
    a real operation across the whole backup, not a field edit.
    """
    scene_name = edited_scene.scene_name
    field_refs: dict = {}
    # The Scene as this session found it.  Taken before the body is built, so it is the
    # state Cancel returns to however much the designers go on to change.  See cancel().
    opened_as = sceneedit.session_snapshot(edited_scene)

    def cancel() -> None:
        """Discard this session's work, then close.

        Reverting rather than only closing, because a Preview holds the same element and
        keeps drawing it: without this, elements dragged in the preview stayed where they
        were dropped after Cancel, which reads as Cancel having failed.  See
        sceneedit.revert_session for what is and is not being undone.

        Ordering matters both ways round it: the revert has to happen before the close,
        because closing is what repaints the preview (_scene_dialog_closed), and the notice
        has to come after, because a dialog closing over a notification hides it.

        Rename cannot have happened first -- it applies to the live backup and closes this
        dialog itself (userintr_editors.confirm_rename_scene_event) -- so there is no applied change
        for a later Cancel to be quietly failing to undo.
        """
        discarded = sceneedit.revert_session(edited_scene, opened_as, field_refs.get("v2_layout"))
        dialog.close()
        if discarded:
            # Only when there was something to discard: a Cancel out of a dialog nobody
            # changed is not an event, and saying so every time would train the notice away.
            ui.notify(
                translate_string("Cancelled. Changes to this Scene were discarded."),
                type="info",
            )

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[800px] w-full p-6"):
        _build_edit_scene_fields(self, edited_scene, field_refs, dialog)
        _build_edit_scene_buttons(self, edited_scene, field_refs, dialog, cancel)

    # Preview has to close this dialog to get at the screen behind it, and the work in
    # progress lives in the dialog's widgets and field_refs -- not in the live tree, which
    # nothing writes to until a save button runs.  Remembering the dialog is what lets the
    # "Edit Scene" button resume it (userintr_editors.open_edit_scene_dialog_event) rather than
    # build a second one from the unedited tree, showing none of the pending edits.
    self.scene_editor_session = {"name": scene_name, "dialog": dialog, "suspended": False}
    dialog.open()


def build_delete_scene_dialog(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Scene.  Like the Profile and Task dialogs there is
    no Keep/Delete Contents choice -- a Scene's UI elements are children of the
    Scene element itself and go with it -- but, like a Task, other things point
    *at* a Scene, so the dialog says what loses it (see sceneedit.delete_scene).

    Says it through guiwins_impact.build_impact_panel, as the other three Delete
    dialogs do.  This dialog used to note in passing that the Tasks which show or
    hide the Scene by name are not changed; the panel names them, one clickable line
    each, which is the difference between being told there may be a problem and
    being handed the list of it.  Read live, so it cannot go stale while the editor
    sits open.
    """
    scene_name = edited_scene.scene_name

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Scene')} '{scene_name}'").classes("text-lg font-bold text-red-600")
        build_impact_panel(self, SCENE, scene_name)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Delete Scene"),
                on_click=lambda: self.event_handlers.confirm_delete_scene_event(
                    scene_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_save_scene_to_android_dialog(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    parent_dialog: ui.dialog,
) -> None:
    """Prompts for the Android device's IP address and port, then writes the
    Scene as a standalone .scn.xml file onto the device's storage under
    /Tasker/scenes, via the Tasker HTTP Server Example's /upload endpoint (see
    sceneedit.save_scene_to_android).  This does not import it into Tasker's live
    configuration.  On success both this prompt and the parent (Edit Scene)
    dialog are closed.  Mirrors build_save_project_to_android_dialog.

    field_refs is the parent dialog's, and is carried through for the save
    handler, which applies those edits before uploading -- the upload renders
    from the live tree, so what is not applied is not sent.  The Scene still goes
    up under its current name: a not-yet-applied Rename does not carry through,
    since Rename is its own operation rather than a field on the dialog.
    """
    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Scene To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = android_device_fields(self)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.save_scene_to_android_event(
                    edited_scene,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            with save_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Scene as a standalone file onto the Android device, "
                        "under /Tasker/scenes.\n\n"
                        "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            # The Profile and Project dialogs' pair, for a Scene -- see
            # guiwins_profedit.build_save_profile_to_android_dialog for why these are two buttons.
            import_into_tasker = ui.button(
                translate_string("Import Into Tasker"),
                on_click=lambda: self.event_handlers.import_scene_into_tasker_event(
                    edited_scene,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with import_into_tasker:
                ui.tooltip(
                    translate_string(
                        "This sends the Scene -- and every Task its elements fire -- to the Android "
                        "device under its own name, into /Tasker/scenes, and opens Android's "
                        "'Open with...' chooser for it.\n\n"
                        "If Tasker is in that chooser, pick it.  A Scene is the one kind Tasker has been "
                        "seen to refuse when it is handed one, so if it is not there -- or nothing "
                        "happens -- finish it with Tasker's 'Scenes > Import One Scene' and pick the "
                        "Scene by name.  The file is on the device either way, and the message tells you "
                        "its name.\n\n"
                        "You will be asked before it replaces a file already at that path.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and running, and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The device will ask you to authorize MapTasker the first time.",
                    ),
                ).style("white-space: pre-wrap")

    android_dialog.open()
