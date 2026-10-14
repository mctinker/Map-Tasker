"""The Refactor dialog's Variable mode: the operation, the variable, the name, the preview and the Apply.

What is decided is test_maprefac_variable's.  What is tested here is the dialog around it: that the pulldown offers
only what the chosen operation can be asked of, that a scope change fills in the spelling it implies, that a refusal
leaves Apply disabled, that changing a box throws the preview away, and that Apply writes the change and nothing else.
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
from maptasker.src.mapops.maprefac_variable import RENAME, TO_GLOBAL, TO_LOCAL, choice_key
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_maprefac_variable import _FIXTURE_XML, _load, _texts

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

_built: dict = {}
_redrawn: list[bool] = []


async def _rebuild_view() -> None:
    _redrawn.append(True)


def _make_jump(_target: object) -> Callable[[], None]:
    return lambda: None


@pytest.fixture(autouse=True)
def _configuration():
    """The variable fixture loaded, with an empty undo history, and nothing selected on screen."""
    _built.clear()
    _redrawn.clear()
    sessundo.clear(PrimeItems)
    _load(_FIXTURE_XML)
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    _built["dialog"] = guiwins_refactor.build_refactor_dialog("", _make_jump, _rebuild_view, PrimeItems)
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


def _toggle(user: User, option: str) -> ui.toggle:
    """The toggle that offers this option -- the mode toggle, or the variable operation, which share nothing."""
    (element,) = [e for e in user.find(kind=ui.toggle).elements if option in e.options]
    return element


def _select(user: User, label: str) -> ui.select:
    (element,) = [e for e in user.find(kind=ui.select).elements if e.props.get("label", "") == label]
    return element


def _name_box(user: User) -> ui.input:
    (element,) = [e for e in user.find(kind=ui.input).elements if e.props.get("label", "") == "New name"]
    return element


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


async def _variable_mode(user: User, operation: str = RENAME) -> None:
    """Switch to the Variable mode and then to an operation, the way a user would."""
    _toggle(user, "variable").set_value("variable")
    _toggle(user, TO_LOCAL).set_value(operation)
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_each_operation_offers_only_the_variables_it_can_be_asked_of() -> None:
    async with _open() as user:
        await _variable_mode(user, TO_LOCAL)
        offered = set(_select(user, "Variable").options)
        assert choice_key("%Solo", "") in offered
        assert choice_key("%tally", "40") not in offered

        _toggle(user, TO_LOCAL).set_value(TO_GLOBAL)
        await asyncio.sleep(0)
        offered = set(_select(user, "Variable").options)
        assert choice_key("%tally", "40") in offered
        assert choice_key("%Solo", "") not in offered


@pytest.mark.asyncio
async def test_a_scope_change_fills_in_the_spelling_it_implies() -> None:
    async with _open() as user:
        await _variable_mode(user, TO_LOCAL)
        _select(user, "Variable").set_value(choice_key("%Solo", ""))
        await asyncio.sleep(0)

        assert _name_box(user).value == "%solo"


@pytest.mark.asyncio
async def test_a_rename_with_no_name_is_a_nudge_not_a_preview() -> None:
    async with _open() as user:
        await _variable_mode(user, RENAME)
        _select(user, "Variable").set_value(choice_key("%Count", ""))
        await asyncio.sleep(0)
        UserInteraction(user, {_button(user, "Preview")}, None).click()

        assert user.notify.contains("Fill in every box first")
        assert not _button(user, "Apply").enabled


@pytest.mark.asyncio
async def test_a_rename_previews_then_applies_and_redraws_the_view() -> None:
    async with _open() as user:
        await _variable_mode(user, RENAME)
        _select(user, "Variable").set_value(choice_key("%Count", ""))
        _name_box(user).set_value("%Tally")
        await asyncio.sleep(0)
        UserInteraction(user, {_button(user, "Preview")}, None).click()

        assert _button(user, "Apply").enabled
        assert any(text.startswith("WHAT WILL HAPPEN") for text in _shown(user))

        UserInteraction(user, {_button(user, "Apply")}, None).click()
        await _until(lambda: _redrawn)

        assert _texts("41") == ["see %Tally"]
        assert user.notify.contains("Undo is available")


@pytest.mark.asyncio
async def test_a_refused_change_says_why_and_leaves_apply_disabled() -> None:
    async with _open() as user:
        await _variable_mode(user, TO_LOCAL)
        _select(user, "Variable").set_value(choice_key("%Count", ""))
        await asyncio.sleep(0)
        UserInteraction(user, {_button(user, "Preview")}, None).click()

        assert any(text.startswith("CANNOT BE DONE") for text in _shown(user))
        assert not _button(user, "Apply").enabled
        assert _texts("41") == ["see %Count"]


@pytest.mark.asyncio
async def test_changing_a_box_throws_the_preview_away() -> None:
    async with _open() as user:
        await _variable_mode(user, RENAME)
        _select(user, "Variable").set_value(choice_key("%Count", ""))
        _name_box(user).set_value("%Tally")
        await asyncio.sleep(0)
        UserInteraction(user, {_button(user, "Preview")}, None).click()
        assert _button(user, "Apply").enabled

        _name_box(user).set_value("%Other")
        await asyncio.sleep(0)

        assert not _button(user, "Apply").enabled
        assert not any(text.startswith("WHAT WILL HAPPEN") for text in _shown(user))
