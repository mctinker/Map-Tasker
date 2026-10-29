"""The Ok button of the Add and Edit panels for Projects, Profiles and Tasks says what it does when hovered.

Ok in these panels is the one button that is easy to misread: it does not save a file and it does not send anything to
the phone, it puts the change into the backup that is open and closes the panel.  So each of the five says that, says
what is different about its own panel, and says what happens when it cannot do it -- and the sixth, Edit
Project, says its changes are already in the backup.

Each panel is the real one, built over the fixture backup on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import profedit, projedit, taskedit
from maptasker.src.gui import guiwins_profedit, guiwins_project, guiwins_taskedit
from nicegui import ui

from tests.nicegui_harness import button, found, open_page
from tests.test_mapswap import _load
from tests.test_profedit import _XML

if TYPE_CHECKING:
    from collections.abc import Callable

    from nicegui.testing.user import User


@pytest.fixture(autouse=True)
def _configuration() -> None:
    """The fixture backup loaded: Projects Home and Work, Profile Triggers, Tasks Entry, Exit and Other."""
    _load(_XML)


def _gui() -> SimpleNamespace | MagicMock:
    """The window as far as these panels use it while they are being drawn."""
    window = MagicMock()
    window.state = PrimeItems
    window.indent = 4
    return window


def _hover(element: ui.element) -> str:
    """The text of the tooltip attached to this element, or "" when it has none."""
    return " ".join(child.text for child in element.default_slot.children if isinstance(child, ui.tooltip))


def _ok(user: User) -> str:
    """The hover text of the one Ok button on the page."""
    return _hover(button(user, "Ok"))


def _add_project() -> Callable[[], None]:
    def page() -> None:
        created = projedit.create_new_project("", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_project.build_add_project_dialog(_gui(), created)

    return page


def _edit_profile() -> Callable[[], None]:
    def page() -> None:
        edited = profedit.load_profile_for_edit("Triggers", state=PrimeItems)
        assert edited is not None
        guiwins_profedit.build_edit_profile_dialog(_gui(), edited)

    return page


def _add_profile() -> Callable[[], None]:
    def page() -> None:
        created = profedit.create_new_profile("", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_profedit.build_add_profile_dialog(_gui(), created, "Home")

    return page


def _edit_task() -> Callable[[], None]:
    def page() -> None:
        edited = taskedit.load_task_for_edit("Entry", state=PrimeItems)
        assert edited is not None
        guiwins_taskedit.build_edit_task_dialog(_gui(), edited)

    return page


def _add_task() -> Callable[[], None]:
    def page() -> None:
        created = taskedit.create_new_task("", "5", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_taskedit.build_add_task_dialog(_gui(), created, None, "Home")

    return page


# ##################################################################################
# What every Ok says
# ##################################################################################
_PANELS = {
    "Add Project": _add_project,
    "Edit Profile": _edit_profile,
    "Add Profile": _add_profile,
    "Edit Task": _edit_task,
    "Add Task": _add_task,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("panel", list(_PANELS))
async def test_every_ok_says_it_keeps_the_change_for_this_session_and_can_be_undone(panel: str) -> None:
    async with open_page(_PANELS[panel]()) as user:
        text = _ok(user)

    assert text, f"the Ok of {panel} has no hover text"
    assert "kept for this session only" in text
    assert "no file is written and nothing is sent to your Android device" in text
    assert "One press of Undo" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("panel", list(_PANELS))
async def test_every_ok_says_the_panel_stays_open_when_it_cannot_do_it(panel: str) -> None:
    async with open_page(_PANELS[panel]()) as user:
        text = _ok(user)

    assert "the dialog stays open and says why" in text
    assert "not lost" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("panel", ["Edit Profile", "Add Profile", "Edit Task", "Add Task"])
async def test_ok_points_to_the_buttons_that_do_keep_it_permanently(panel: str) -> None:
    async with open_page(_PANELS[panel]()) as user:
        text = _ok(user)

    assert "'Save To Current File'" in text and "'Save To Android'" in text


# ##################################################################################
# What is different about each
# ##################################################################################
@pytest.mark.asyncio
async def test_add_project_ok_says_it_adds_and_selects_the_project_and_how_to_keep_it() -> None:
    async with open_page(_add_project()) as user:
        text = _ok(user)

    assert text.startswith("Adds the new Project to the loaded backup")
    assert "selects it in the Project pulldown" in text
    assert "'Save To Current File' in any Edit dialog" in text
    assert "empty or another Project already has it" in text


@pytest.mark.asyncio
@pytest.mark.parametrize(("panel", "kind"), [("Edit Profile", "Profile"), ("Edit Task", "Task")])
async def test_edit_ok_says_it_applies_the_changes_and_names_the_clash(panel: str, kind: str) -> None:
    async with open_page(_PANELS[panel]()) as user:
        text = _ok(user)

    assert text.startswith("Applies the changes made in this dialog to the loaded backup, right now")
    assert f"a name another {kind} already has" in text


@pytest.mark.asyncio
async def test_add_profile_ok_says_which_project_and_what_it_checks() -> None:
    async with open_page(_add_profile()) as user:
        text = _ok(user)

    assert text.startswith("Adds the new Profile to the loaded backup, in the Project you chose")
    assert "already used by another Profile, or no Project was chosen" in text


@pytest.mark.asyncio
async def test_add_task_ok_says_it_is_listed_under_the_selected_project() -> None:
    async with open_page(_add_task()) as user:
        text = _ok(user)

    assert text.startswith("Adds the new Task to the loaded backup")
    assert "listed under the Project you had selected" in text
    assert "already used by another Task" in text


# ##################################################################################
# Edit Project
# ##################################################################################
@pytest.mark.asyncio
async def test_edit_project_ok_says_the_changes_are_already_in_the_backup() -> None:
    def page() -> None:
        edited = projedit.load_project_for_edit("Home", state=PrimeItems)
        assert edited is not None
        guiwins_project.build_edit_project_dialog(_gui(), edited)

    async with open_page(page) as user:
        labels = {b.text for b in found(user, ui.button)}
        text = _ok(user)

    assert {"Ok", "Cancel", "Delete Project", "Rename", "Save To Current File"} <= labels
    assert text.startswith("Closes this dialog, keeping the changes made in it.")
    assert "applied to the loaded backup as you make them" in text
    assert "Undo" in text
