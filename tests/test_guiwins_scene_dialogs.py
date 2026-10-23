"""The Scene dialogs: which kind to add, the Add and Edit forms, Delete, and Save To Android.

The designers that fill a Scene's body are guiwins_designer_legacy's and guiwins_designer_v2's, and what a button
finally does to the loaded backup is the editors handler's; both have tests of their own.  Here it is what the
dialogs put on screen and which handler each button is wired to, including the one thing Cancel does that the
other dialogs do not -- put the Scene back as it was found, and say so only when there was something to put back.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from maptasker.src.core import scenelayout
from maptasker.src.gui import guiwins_scene
from nicegui import ui

from tests.nicegui_harness import click, dialogs, found, label_texts, open_page

if TYPE_CHECKING:
    pass


def _window() -> tuple[SimpleNamespace, SimpleNamespace]:
    handlers = SimpleNamespace(editors=MagicMock(), android=MagicMock())
    return SimpleNamespace(event_handlers=handlers, state=SimpleNamespace(), scene_editor_session=None), handlers


def _scene(name: str = "Dialog") -> SimpleNamespace:
    return SimpleNamespace(scene_name=name, scene_element=ET.Element("Scene"), element_renames=[])


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The designer, the preview hand-off and the rest of what the body reaches for, replaced."""
    record = SimpleNamespace(body=[], closed=[], reverted=[], snapshots=[], revert_result=True)

    class _Designer:
        preview_tooltip = "Draws from the size typed below"

        def build_body(self, window: object, scene: object, field_refs: dict, dialog: object, state: object) -> None:
            record.body.append((scene, dialog))
            ui.label("designer body")

    monkeypatch.setattr(guiwins_scene, "designer_for", lambda element: _Designer())
    monkeypatch.setattr(guiwins_scene.scenemodel, "scene_version", lambda element: "Legacy")
    monkeypatch.setattr(
        guiwins_scene, "_scene_dialog_closed", lambda window, dialog, field_refs, event: record.closed.append(event)
    )
    monkeypatch.setattr(guiwins_scene, "build_impact_panel", lambda window, kind, name: ui.label(f"impact of {name}"))
    monkeypatch.setattr(guiwins_scene, "build_share_checks", lambda *a, **k: None)
    monkeypatch.setattr(guiwins_scene, "PendingChangesBanner", MagicMock())
    monkeypatch.setattr(guiwins_scene.sceneedit, "default_scene_save_path", lambda name, state: f"/out/{name}.scn.xml")
    monkeypatch.setattr(
        guiwins_scene.sceneedit, "session_snapshot", lambda scene: record.snapshots.append(scene) or "snap"
    )
    monkeypatch.setattr(
        guiwins_scene.sceneedit,
        "revert_session",
        lambda scene, snapshot, layout: record.reverted.append((snapshot, layout)) or record.revert_result,
    )
    monkeypatch.setattr(guiwins_scene, "android_device_fields", lambda window: {"ip": "1.2.3.4"})
    return record


# ##################################################################################
# Which kind of Scene
# ##################################################################################
@pytest.mark.asyncio
async def test_the_legacy_button_adds_a_legacy_scene_to_the_project(stubs: SimpleNamespace) -> None:
    window, handlers = _window()
    async with open_page(lambda: guiwins_scene.build_add_scene_version_dialog(window, "Home")) as user:  # type: ignore[arg-type]
        assert "Adding to Project: Home" in label_texts(user)
        await click(user, "Legacy Scene")
        handlers.editors.add_scene_of_version_event.assert_called_once()
        assert handlers.editors.add_scene_of_version_event.call_args.args[:3] == ("Legacy", "", "Home")


@pytest.mark.asyncio
async def test_each_version_two_template_button_passes_its_own_label(stubs: SimpleNamespace) -> None:
    window, handlers = _window()
    templates = [label for label, _description, _builder in scenelayout.V2_TEMPLATES]
    async with open_page(lambda: guiwins_scene.build_add_scene_version_dialog(window, "Home")) as user:  # type: ignore[arg-type]
        for label in templates:
            await click(user, label)
        chosen = [call.args[1] for call in handlers.editors.add_scene_of_version_event.call_args_list]
        assert chosen == templates, "a closure over the loop variable would hand every button the last one"


@pytest.mark.asyncio
async def test_without_a_project_the_dialog_does_not_claim_one_and_cancel_closes_it(stubs: SimpleNamespace) -> None:
    window, handlers = _window()
    async with open_page(lambda: guiwins_scene.build_add_scene_version_dialog(window, "")) as user:  # type: ignore[arg-type]
        assert not any(text.startswith("Adding to Project") for text in label_texts(user))
        await click(user, "Cancel")
        assert not dialogs(user)[0].value
        handlers.editors.add_scene_of_version_event.assert_not_called()


# ##################################################################################
# The body shared by Add and Edit
# ##################################################################################
@pytest.mark.asyncio
async def test_the_body_states_the_kind_and_hands_the_rest_to_the_designer(stubs: SimpleNamespace) -> None:
    window, handlers = _window()
    scene = _scene()
    refs: dict[str, Any] = {}

    def page() -> None:
        with ui.dialog() as dialog:
            guiwins_scene._build_scene_editor_body(window, scene, refs, dialog, state=window.state)  # type: ignore[arg-type]

    async with open_page(page) as user:
        assert "Scene type: Legacy" in label_texts(user)
        assert "designer body" in label_texts(user)
        assert stubs.body and stubs.body[0][0] is scene
        await click(user, "Preview")
        handlers.editors.preview_scene_event.assert_called_once()
        assert handlers.editors.preview_scene_event.call_args.args[:2] == (scene, refs)


@pytest.mark.asyncio
async def test_a_body_with_no_dialog_still_has_everything_but_the_dialog_hook(stubs: SimpleNamespace) -> None:
    window, _handlers = _window()

    def page() -> None:
        guiwins_scene._build_scene_editor_body(window, _scene(), {}, None, state=window.state)  # type: ignore[arg-type]

    async with open_page(page) as user:
        assert "designer body" in label_texts(user)
        assert stubs.closed == []


@pytest.mark.asyncio
async def test_closing_the_dialog_tells_the_preview_it_opened(stubs: SimpleNamespace) -> None:
    window, _handlers = _window()
    made: list[ui.dialog] = []

    def page() -> None:
        with ui.dialog() as dialog:
            made.append(dialog)
            guiwins_scene._build_scene_editor_body(window, _scene(), {}, dialog, state=window.state)  # type: ignore[arg-type]

    async with open_page(page):
        made[0].open()
        await asyncio.sleep(0.05)
        made[0].close()
        await asyncio.sleep(0.05)
        assert stubs.closed, "the preview hears about the change when the dialog closes"


# ##################################################################################
# Add
# ##################################################################################
@pytest.mark.asyncio
async def test_the_add_form_names_the_kind_and_the_project_and_ok_hands_over_what_was_typed(
    stubs: SimpleNamespace,
) -> None:
    window, handlers = _window()
    scene = _scene()

    async with open_page(lambda: guiwins_scene.build_add_scene_dialog(window, scene, "Home")) as user:  # type: ignore[arg-type]
        assert "Add Scene: Legacy" in label_texts(user)
        assert "Adding to Project: Home" in label_texts(user)
        (name,) = [e for e in found(user, ui.input) if e.props.get("label") == "Scene Name"]
        name.value = "Fresh"
        await click(user, "Ok")
        edited, refs, dialog = handlers.editors.keep_new_scene_event.call_args.args
        assert edited is scene
        assert refs["name"].value == "Fresh" and refs["target_project_name"] == "Home"
        assert isinstance(dialog, ui.dialog)
        await click(user, "Cancel")
        assert not dialogs(user)[0].value


# ##################################################################################
# Edit
# ##################################################################################
@pytest.mark.asyncio
async def test_the_edit_form_shows_the_name_read_only_and_the_default_save_path(stubs: SimpleNamespace) -> None:
    window, _handlers = _window()

    async with open_page(lambda: guiwins_scene.build_edit_scene_dialog(window, _scene("Panel"))) as user:  # type: ignore[arg-type]
        assert "Edit Scene: Panel" in label_texts(user)
        (name,) = [e for e in found(user, ui.input) if e.props.get("label") == "Scene Name"]
        assert name.value == "Panel" and "readonly" in name.props
        (path,) = [e for e in found(user, ui.input) if e.props.get("label") == "Save as"]
        assert path.value == "/out/Panel.scn.xml"
        assert window.scene_editor_session["name"] == "Panel", (
            "Preview can resume this dialog rather than build a second"
        )
        assert window.scene_editor_session["suspended"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("button", "group", "method"),
    [
        ("Delete Scene", "editors", "delete_scene_event"),
        ("Rename", "editors", "rename_scene_event"),
        ("Ok", "editors", "save_edited_scene_event"),
        ("Save To Current File", "editors", "save_scene_to_current_file_event"),
        ("Save To Android", "android", "open_save_scene_to_android_dialog_event"),
        ("Export Scene", "editors", "save_scene_event"),
    ],
)
async def test_each_edit_button_is_wired_to_its_handler_with_the_scene_and_the_form(
    stubs: SimpleNamespace, button: str, group: str, method: str
) -> None:
    window, handlers = _window()
    scene = _scene()

    async with open_page(lambda: guiwins_scene.build_edit_scene_dialog(window, scene)) as user:  # type: ignore[arg-type]
        await click(user, button)
        handler = getattr(getattr(handlers, group), method)
        handler.assert_called_once()
        assert handler.call_args.args[0] is scene


@pytest.mark.asyncio
async def test_cancel_puts_the_scene_back_closes_and_says_what_it_discarded(stubs: SimpleNamespace) -> None:
    window, _handlers = _window()
    async with open_page(lambda: guiwins_scene.build_edit_scene_dialog(window, _scene())) as user:  # type: ignore[arg-type]
        await click(user, "Cancel")
        assert stubs.reverted and stubs.reverted[0][0] == "snap"
        assert not dialogs(user)[0].value
        assert user.notify.contains("Cancelled. Changes to this Scene were discarded.")


@pytest.mark.asyncio
async def test_cancel_out_of_a_dialog_nobody_changed_is_not_an_event(stubs: SimpleNamespace) -> None:
    stubs.revert_result = False
    window, _handlers = _window()
    async with open_page(lambda: guiwins_scene.build_edit_scene_dialog(window, _scene())) as user:  # type: ignore[arg-type]
        await click(user, "Cancel")
        assert not dialogs(user)[0].value
        assert not user.notify.contains("Cancelled")


# ##################################################################################
# Delete
# ##################################################################################
@pytest.mark.asyncio
async def test_delete_names_the_scene_what_loses_it_and_confirms_with_bothdialogs(stubs: SimpleNamespace) -> None:
    window, handlers = _window()
    parent = MagicMock()

    async with open_page(lambda: guiwins_scene.build_delete_scene_dialog(window, _scene("Panel"), parent)) as user:  # type: ignore[arg-type]
        assert "Delete Scene 'Panel'" in label_texts(user)
        assert "impact of Panel" in label_texts(user)
        buttons = [e.text for e in found(user, ui.button)]
        assert buttons.count("Delete Scene") == 1
        await click(user, "Delete Scene")
        args = handlers.editors.confirm_delete_scene_event.call_args.args
        assert args[0] == "Panel" and args[2] is parent
        await click(user, "Cancel")
        assert not dialogs(user)[0].value


# ##################################################################################
# Save To Android
# ##################################################################################
@pytest.mark.asyncio
async def test_the_android_dialog_hands_both_forms_and_both_dialogs_to_either_save(stubs: SimpleNamespace) -> None:
    window, handlers = _window()
    scene = _scene()
    parent = MagicMock()
    refs: dict[str, Any] = {"name": "x"}

    def page() -> None:
        guiwins_scene.build_save_scene_to_android_dialog(window, scene, refs, parent)  # type: ignore[arg-type]

    async with open_page(page) as user:
        assert "Save Scene To Android Device" in label_texts(user)
        await click(user, "Save As File")
        await click(user, "Import Into Tasker")
        for method in (handlers.android.save_scene_to_android_event, handlers.android.import_scene_into_tasker_event):
            method.assert_called_once()
            edited, form, android_form, android_dialog, parent_dialog = method.call_args.args
            assert (edited, form, android_form, parent_dialog) == (scene, refs, {"ip": "1.2.3.4"}, parent)
            assert isinstance(android_dialog, ui.dialog), "the prompt itself is handed over so the handler can close it"
        await click(user, "Cancel")
        assert not dialogs(user)[0].value
