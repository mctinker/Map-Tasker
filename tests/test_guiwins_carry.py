"""The Import With Dependencies dialog: list what the other backup holds, preview one import, apply it.

What an import does is test_mapcarry's.  What is tested here is the dialog around it: that nothing is
applied unseen, that Apply is there only while a preview is, that a choice a plan depended on takes the
preview away, that the list can be narrowed, and that the window is brought up to date afterwards.

The other file is the one test_mapcarry builds; the dialog is the real one, on a page of NiceGUI's in-process
user simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_carry
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests import test_mapcarry
from tests.test_mapcarry import _source

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from nicegui.testing.user import User

_built: dict = {}


@pytest.fixture
def loaded() -> Iterator[None]:
    """The configuration open -- test_mapcarry's -- with an empty undo history."""
    sessundo.clear(PrimeItems)
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    test_mapcarry._open(test_mapcarry._TARGET_XML)
    yield
    sessundo.clear(PrimeItems)


@pytest.fixture(autouse=True)
def _reset() -> None:
    _built.clear()
    _built.update(rebuilt=0, saved=0, save_answer=False, another=0)


def _page() -> None:
    async def rebuild() -> None:
        _built["rebuilt"] += 1

    async def save() -> bool:
        _built["saved"] += 1
        return _built["save_answer"]

    async def another() -> None:
        _built["another"] += 1

    def jump(target: object) -> Callable:
        return lambda *_args: None

    _built["dialog"] = guiwins_carry.build_carry_dialog(_source(), jump, another, rebuild, save, PrimeItems)
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _buttons(user: User, label: str) -> list[ui.button]:
    return [element for element in user.find(kind=ui.button).elements if element.text == label]


def _press(user: User, button: ui.button) -> None:
    UserInteraction(user, {button}, None).click()


def _only(user: User, label: str) -> ui.button:
    (button,) = _buttons(user, label)
    return button


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


async def _until(condition: Callable[[], object]) -> None:
    """Wait, up to two seconds, for something the dialog does on a timer."""
    for _ in range(40):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


def _row_button(user: User, label: str) -> ui.button:
    """The 'Preview' button on the row of this name: the one beside the label that is next to it in the list."""
    labels = user.find(kind=ui.label).elements
    row_labels = [element for element in labels if element.text == label]
    assert row_labels, f"no row called {label!r}"
    parent_slot = row_labels[0].parent_slot
    assert parent_slot is not None
    row = parent_slot.parent
    (button,) = [element for element in row.descendants() if isinstance(element, ui.button)]
    return button


# ##################################################################################
# Opening
# ##################################################################################
@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_dialog_and_a_message() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}, "all_projects": {}}
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No XML file has been loaded.  Get an XML file first.")


@pytest.mark.asyncio
async def test_every_pick_is_listed_with_a_preview_button(loaded: None) -> None:
    async with _open() as user:
        assert "8 of 8 offered" in _labels(user)
        assert len(_buttons(user, "Preview")) == 8
        assert "Lights On  (Lights)" in _labels(user)


@pytest.mark.asyncio
async def test_the_file_being_imported_from_is_named(loaded: None) -> None:
    async with _open() as user:
        assert "/backups/tablet.xml" in _labels(user)


# ##################################################################################
# Narrowing the list
# ##################################################################################
@pytest.mark.asyncio
async def test_the_kind_toggle_narrows_the_list(loaded: None) -> None:
    async with _open() as user:
        (toggle,) = user.find(kind=ui.toggle).elements

        toggle.value = "task"

        await _until(lambda: "5 of 8 offered" in _labels(user))
        assert len(_buttons(user, "Preview")) == 5


@pytest.mark.asyncio
async def test_typing_part_of_a_name_narrows_the_list(loaded: None) -> None:
    async with _open() as user:
        (box,) = user.find(kind=ui.input).elements

        box.value = "fade"

        await _until(lambda: "1 of 8 offered" in _labels(user))
        assert len(_buttons(user, "Preview")) == 1


@pytest.mark.asyncio
async def test_a_search_that_matches_nothing_says_so(loaded: None) -> None:
    async with _open() as user:
        (box,) = user.find(kind=ui.input).elements

        box.value = "zzz"

        await _until(lambda: "Nothing matches." in _labels(user))


# ##################################################################################
# Previewing: nothing is applied unseen
# ##################################################################################
@pytest.mark.asyncio
async def test_apply_is_greyed_out_until_a_preview_is_up(loaded: None) -> None:
    async with _open() as user:
        assert not _only(user, "Apply").enabled


@pytest.mark.asyncio
async def test_preview_draws_what_would_happen_and_changes_nothing(loaded: None) -> None:
    tasks_before = dict(PrimeItems.tasker_root_elements["all_tasks"])
    async with _open() as user:
        _press(user, _row_button(user, "Lights On  (Lights)"))

        labels = _labels(user)
        assert "Preview -- nothing has changed yet" in labels
        assert any("Copy Task 'Fade' (1 actions) as 'Fade (imported)'" in label for label in labels)
        assert _only(user, "Apply").enabled
    assert PrimeItems.tasker_root_elements["all_tasks"] == tasks_before
    assert _built["rebuilt"] == 0


@pytest.mark.asyncio
async def test_a_preview_that_cannot_be_applied_leaves_apply_greyed_out_and_says_why(loaded: None) -> None:
    async with _open() as user:
        (box,) = user.find(kind=ui.input).elements
        box.value = "Broken"
        await _until(lambda: "1 of 8 offered" in _labels(user))
        PrimeItems.tasker_root_elements["all_projects"].pop("Home")  # the Project everything would be filed in
        select = user.find(kind=ui.select).elements.pop()
        select.value = "Home"

        _press(user, _buttons(user, "Preview")[0])

        assert not _only(user, "Apply").enabled
        assert any("CANNOT BE DONE" in label for label in _labels(user))


@pytest.mark.asyncio
async def test_cancel_preview_takes_the_preview_and_apply_away(loaded: None) -> None:
    async with _open() as user:
        _press(user, _row_button(user, "Lights On  (Lights)"))

        _press(user, _only(user, "Cancel Preview"))

        assert "Preview -- nothing has changed yet" not in _labels(user)
        assert not _only(user, "Apply").enabled


@pytest.mark.asyncio
async def test_changing_where_it_goes_takes_the_preview_away(loaded: None) -> None:
    """A plan describes one choice of destination."""
    async with _open() as user:
        _press(user, _row_button(user, "Lights On  (Lights)"))
        (select,) = user.find(kind=ui.select).elements

        select.value = "Home"

        assert not _only(user, "Apply").enabled
        assert "Preview -- nothing has changed yet" not in _labels(user)


@pytest.mark.asyncio
async def test_changing_whether_variables_come_takes_the_preview_away(loaded: None) -> None:
    async with _open() as user:
        _press(user, _row_button(user, "Lights On  (Lights)"))
        (box,) = user.find(kind=ui.checkbox).elements

        box.value = False

        assert not _only(user, "Apply").enabled


# ##################################################################################
# Applying
# ##################################################################################
@pytest.mark.asyncio
async def test_apply_imports_refreshes_the_window_and_undo_is_there(loaded: None) -> None:
    async with _open() as user:
        _press(user, _row_button(user, "Lights On  (Lights)"))

        _press(user, _only(user, "Apply"))
        await _until(lambda: _built["rebuilt"])

        assert _built["rebuilt"] == 1
        assert any("Undo is available." in message for message in user.notify.messages)
        assert not _only(user, "Apply").enabled
        assert "Fade (imported)" in PrimeItems.tasker_root_elements["all_tasks_by_name"]
        # The Project the import made is offered as a place for the next one.
        (select,) = user.find(kind=ui.select).elements
        assert "Lights" in select.options
    assert sessundo.can_undo(PrimeItems)


@pytest.mark.asyncio
async def test_the_row_that_was_imported_keeps_its_place_with_a_green_button(loaded: None) -> None:
    async with _open() as user:
        _press(user, _row_button(user, "Lights On  (Lights)"))
        _press(user, _only(user, "Apply"))
        await _until(lambda: _built["rebuilt"])

        button = _row_button(user, "Lights On  (Lights)")

        assert "color=green" in str(button.props) or button.props.get("color") == "green"


# ##################################################################################
# The other buttons
# ##################################################################################
@pytest.mark.asyncio
async def test_save_to_current_file_asks_the_window_to_save(loaded: None) -> None:
    async with _open() as user:
        _press(user, _only(user, "Save To Current File"))
        await _until(lambda: _built["saved"])

        assert _built["saved"] == 1


@pytest.mark.asyncio
async def test_choose_another_file_closes_this_and_asks_for_one(loaded: None) -> None:
    async with _open() as user:
        _press(user, _only(user, "Choose another file..."))
        await _until(lambda: _built["another"])

        assert _built["another"] == 1
