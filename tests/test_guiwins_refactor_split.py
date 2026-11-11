"""The Refactor dialog's Split Project mode: choosing Tasks and Profiles, the preview, and the Apply.

What is decided is test_maprefac_split's.  What is tested here is the dialog around it: that the choice offers every
Task and Profile, that nothing is previewed until something is chosen and the Project is named, that a name that is
taken is refused and leaves Apply disabled, that changing a choice throws a preview away, and that Apply moves the
objects, forgets what was chosen, and leaves the view to be redrawn.  The dialog is the real one, on a page of NiceGUI's
in-process user simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_refactor
from maptasker.src.mapops.maprefac_model import members, object_table
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_maprefac import _load
from tests.test_projdeps import _XML

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from nicegui.testing.user import User

_built: dict = {}
_redrawn: list[bool] = []


async def _rebuild_view() -> None:
    _redrawn.append(True)


async def _save_configuration() -> bool:
    return True


def _make_jump(_target: object) -> Callable[[], None]:
    return lambda: None


@pytest.fixture(autouse=True)
def _configuration_loaded() -> Iterator[None]:
    """Project Dependencies' fixture loaded, with an empty undo history."""
    _built.clear()
    _redrawn.clear()
    sessundo.clear(PrimeItems)
    _load(_XML)
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    _built["dialog"] = guiwins_refactor.build_refactor_dialog(
        "", _make_jump, _rebuild_view, _save_configuration, PrimeItems
    )
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


def _picks(user: User) -> ui.select:
    (element,) = [
        e for e in user.find(kind=ui.select).elements if e.props.get("label", "") == "Tasks and Profiles to split out"
    ]
    return element


def _name_box(user: User) -> ui.input:
    (element,) = [e for e in user.find(kind=ui.input).elements if e.props.get("label", "") == "New Project name"]
    return element


def _button(user: User, text: str) -> ui.button:
    (element,) = [e for e in user.find(kind=ui.button).elements if e.text == text]
    return element


def _shown(user: User) -> list[str]:
    """Every line of the preview: the plain ones are labels, and the ones that point at something are links."""
    return [element.text for kind in (ui.label, ui.link) for element in user.find(kind=kind).elements]


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(60):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


async def _split_mode(user: User) -> None:
    (toggle,) = [e for e in user.find(kind=ui.toggle).elements if "split" in e.options]
    toggle.set_value("split")
    await asyncio.sleep(0)


async def _choose(user: User, keys: list[str], name: str) -> None:
    _picks(user).set_value(keys)
    _name_box(user).set_value(name)
    await asyncio.sleep(0)


def _members(project: str, tag: str) -> list[str]:
    return members(object_table("all_projects", state=PrimeItems)[project]["xml"], tag)


@pytest.mark.asyncio
async def test_the_choice_offers_every_task_and_profile_and_nothing_is_chosen() -> None:
    async with _open() as user:
        await _split_mode(user)

        options = _picks(user).options
        assert "profile:100" in options
        assert len([key for key in options if key.startswith("task:")]) == len(
            object_table("all_tasks", state=PrimeItems),
        )
        assert not _picks(user).value


@pytest.mark.asyncio
async def test_nothing_is_previewed_until_something_is_chosen_and_the_project_is_named() -> None:
    async with _open() as user:
        await _split_mode(user)

        UserInteraction(user, {_button(user, "Preview")}, None).click()
        assert user.notify.contains("Fill in every box first.")

        _picks(user).set_value(["task:10"])
        await asyncio.sleep(0)
        UserInteraction(user, {_button(user, "Preview")}, None).click()
        assert not _button(user, "Apply").enabled


@pytest.mark.asyncio
async def test_a_preview_says_what_comes_along_and_what_still_crosses() -> None:
    async with _open() as user:
        await _split_mode(user)
        await _choose(user, ["task:10"], "Morning Stuff")
        UserInteraction(user, {_button(user, "Preview")}, None).click()

        shown = _shown(user)
        assert _button(user, "Apply").enabled
        assert any(text.startswith("WHAT WILL HAPPEN") for text in shown)
        assert any(text.startswith("STILL CROSSING THE NEW BOUNDARY") for text in shown)
        assert any("Move Task 'Setup' out of Project 'Utilities'" in text for text in shown)


@pytest.mark.asyncio
async def test_a_name_another_project_has_is_refused_and_leaves_apply_disabled() -> None:
    async with _open() as user:
        await _split_mode(user)
        await _choose(user, ["task:10"], "Home")
        UserInteraction(user, {_button(user, "Preview")}, None).click()

        assert any(text.startswith("CANNOT BE DONE") for text in _shown(user))
        assert not _button(user, "Apply").enabled
        assert "Morning Stuff" not in object_table("all_projects", state=PrimeItems)


@pytest.mark.asyncio
async def test_changing_what_is_chosen_throws_the_preview_away() -> None:
    async with _open() as user:
        await _split_mode(user)
        await _choose(user, ["task:10"], "Morning Stuff")
        UserInteraction(user, {_button(user, "Preview")}, None).click()
        assert _button(user, "Apply").enabled

        _picks(user).set_value(["task:10", "task:11"])
        await asyncio.sleep(0)

        assert not _button(user, "Apply").enabled


@pytest.mark.asyncio
async def test_apply_moves_the_objects_forgets_the_choice_and_redraws_the_view() -> None:
    async with _open() as user:
        await _split_mode(user)
        await _choose(user, ["task:10"], "Morning Stuff")
        UserInteraction(user, {_button(user, "Preview")}, None).click()
        UserInteraction(user, {_button(user, "Apply")}, None).click()
        await _until(lambda: _redrawn)

        assert set(_members("Morning Stuff", "tids")) == {"10", "20", "12", "22"}
        assert _members("Home", "tids") == ["11"]
        assert user.notify.contains("Undo is available")
        assert not _picks(user).value, "what was chosen has moved"
        assert not _button(user, "Apply").enabled
        assert "Morning Stuff" in str(object_table("all_projects", state=PrimeItems).keys())
