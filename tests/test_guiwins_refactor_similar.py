"""The Refactor dialog's Near-duplicates mode: finding the shared runs, choosing one, the preview and the Apply.

What is decided is test_maprefac_similar's.  What is tested here is the dialog around it: that nothing is offered until
Find is pressed, that choosing a run fills in a name no Task has, that a Task which is already the run needs none,
that a refusal leaves Apply disabled, and that Apply writes the change, looks again, and leaves the view to be redrawn.
The dialog is the real one, on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_refactor
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_maprefac import _load
from tests.test_maprefac_similar import _FIXTURE_XML, _RUN, _codes, _configuration, _flash, _task

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

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
def _configuration_loaded():
    """The near-duplicate fixture loaded, with an empty undo history."""
    _built.clear()
    _redrawn.clear()
    sessundo.clear(PrimeItems)
    _load(_FIXTURE_XML)
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


def _select(user: User, label: str) -> ui.select:
    (element,) = [e for e in user.find(kind=ui.select).elements if e.props.get("label", "") == label]
    return element


def _name_box(user: User) -> ui.input:
    """This mode's name box: Extract has one of the same label, built first and hidden while this mode shows."""
    return [e for e in user.find(kind=ui.input).elements if e.props.get("label", "") == "New Task name"][-1]


def _button(user: User, text: str) -> ui.button:
    (element,) = [e for e in user.find(kind=ui.button).elements if e.text == text]
    return element


def _shown(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(60):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


async def _near_duplicates(user: User) -> None:
    """Switch to the mode and press Find, the way a user would."""
    (toggle,) = [e for e in user.find(kind=ui.toggle).elements if "similar" in e.options]
    toggle.set_value("similar")
    await asyncio.sleep(0)
    UserInteraction(user, {_button(user, "Find")}, None).click()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_nothing_is_offered_until_find_is_pressed() -> None:
    async with _open() as user:
        (toggle,) = [e for e in user.find(kind=ui.toggle).elements if "similar" in e.options]
        toggle.set_value("similar")
        await asyncio.sleep(0)

        assert not _select(user, "Shared actions").options


@pytest.mark.asyncio
async def test_find_offers_the_run_the_tasks_share_and_says_how_many() -> None:
    async with _open() as user:
        await _near_duplicates(user)

        offered = _select(user, "Shared actions")
        assert len(offered.options) == 1
        assert "4 actions in 3 Tasks" in str(offered.props["options"])
        assert "Groups of shared actions found: 1" in _shown(user)


@pytest.mark.asyncio
async def test_choosing_a_run_suggests_a_name_no_task_has() -> None:
    async with _open() as user:
        await _near_duplicates(user)
        key = next(iter(_select(user, "Shared actions").options))
        _select(user, "Shared actions").set_value(key)
        await asyncio.sleep(0)

        assert _name_box(user).value == "Evening - shared part"


@pytest.mark.asyncio
async def test_a_run_previews_then_applies_looks_again_and_redraws_the_view() -> None:
    async with _open() as user:
        await _near_duplicates(user)
        _select(user, "Shared actions").set_value(next(iter(_select(user, "Shared actions").options)))
        await asyncio.sleep(0)
        UserInteraction(user, {_button(user, "Preview")}, None).click()

        assert _button(user, "Apply").enabled
        assert any(text.startswith("WHAT WILL HAPPEN") for text in _shown(user))

        UserInteraction(user, {_button(user, "Apply")}, None).click()
        await _until(lambda: _redrawn)

        assert _codes("30") == ["548", "130", "548"]
        assert user.notify.contains("Undo is available")
        assert not _select(user, "Shared actions").options, "the run is now one Task, so it is no longer shared"


@pytest.mark.asyncio
async def test_a_name_that_is_taken_is_refused_and_leaves_apply_disabled() -> None:
    async with _open() as user:
        await _near_duplicates(user)
        _select(user, "Shared actions").set_value(next(iter(_select(user, "Shared actions").options)))
        await asyncio.sleep(0)
        _name_box(user).set_value("Morning")
        await asyncio.sleep(0)
        UserInteraction(user, {_button(user, "Preview")}, None).click()

        assert any(text.startswith("CANNOT BE DONE") for text in _shown(user))
        assert not _button(user, "Apply").enabled
        assert _codes("30") == ["548", "547", "548", "547", "548", "548"]


@pytest.mark.asyncio
async def test_changing_the_smallest_run_forgets_what_was_found() -> None:
    async with _open() as user:
        await _near_duplicates(user)
        assert _select(user, "Shared actions").options

        _select(user, "Fewest actions").set_value(5)
        await asyncio.sleep(0)

        assert not _select(user, "Shared actions").options


@pytest.mark.asyncio
async def test_a_task_that_is_only_the_run_needs_no_name() -> None:
    sessundo.clear(PrimeItems)
    _load(
        _configuration(
            [
                _task("50", "Core", *_RUN),
                _task("51", "Before", _flash("first"), *_RUN),
                _task("52", "After", *_RUN, _flash("last")),
            ],
            "50,51,52",
        ),
    )
    async with _open() as user:
        await _near_duplicates(user)
        _select(user, "Shared actions").set_value(next(iter(_select(user, "Shared actions").options)))
        await asyncio.sleep(0)

        assert not _name_box(user).enabled
        assert any("made of nothing else" in text for text in _shown(user))
        UserInteraction(user, {_button(user, "Preview")}, None).click()
        assert _button(user, "Apply").enabled
