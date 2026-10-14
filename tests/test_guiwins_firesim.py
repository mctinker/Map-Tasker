"""The What Fires When? dialog: its four controls, the answer redrawn under them and what its buttons do.

What is decided is test_firesim's.  What is tested here is the dialog around it -- that it refuses to open
with nothing loaded, that changing a control redraws the answer, that a battery level off the scale is put
right, and that a name in the answer can be clicked.  The dialog is the real one, on a page of NiceGUI's
in-process user simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiwins_firesim
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

from tests.test_firesim import _loaded  # noqa: F401  (_loaded is the fixture)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

pytestmark = pytest.mark.asyncio

_built: dict = {}


def _page() -> None:
    jumps: list = _built.setdefault("jumps", [])
    steps: list = _built.setdefault("steps", [])
    _built["dialog"] = guiwins_firesim.build_firesim_dialog(
        lambda target: (lambda: jumps.append(target.label)),
        PrimeItems,
        step_task=steps.append,
    )
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    _built.clear()
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(60):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _input(user: User, label: str) -> ui.element:
    (element,) = [e for e in user.find(kind=ui.input).elements if e.props.get("label", "") == label]
    return element


def _summary(user: User) -> str:
    return next(text for text in _labels(user) if "collision(s)" in text or text == "Choose a date and a time.")


async def _at_monday_ten(user: User) -> None:
    """Move the dialog to the moment test_firesim's fixture is described for: Monday 28 September 2026, 10:00."""
    _input(user, "Date").set_value("2026-09-28")
    _input(user, "Time").set_value("10:00")
    await _until(lambda: _links(user, "Profile 'Work Hours'"))


def _links(user: User, text: str) -> list:
    """The links whose label (Project > Profile 'name' (id n)) contains this."""
    return [link for link in user.find(kind=ui.link).elements if text in link.text]


async def test_with_nothing_loaded_the_dialog_says_so_and_does_not_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "tasker_root_elements", {"all_profiles": {}})
    async with _open() as user:
        assert _built["dialog"] is None
        await user.should_see("No XML file with Profiles has been loaded")


async def test_the_dialog_opens_with_the_four_controls_and_an_answer() -> None:
    async with _open() as user:
        assert _built["dialog"] is not None
        await user.should_see("What Fires When?")
        for label in ("Date", "Time", "Wi-Fi network", "App in front", "Battery %"):
            await user.should_see(label)
        assert "active" in _summary(user)
        assert "collision(s)" in _summary(user)


async def test_a_moment_that_makes_profiles_active_lists_them_and_where_they_collide() -> None:
    async with _open() as user:
        await _at_monday_ten(user)
        summary = _summary(user)
        assert summary.split(",")[0].split()[0] != "0"  # at least one Profile is active
        await user.should_see("Collisions")
        await user.should_see("Run order")
        assert _links(user, "Profile 'Work Hours'")


async def test_a_date_that_is_not_one_asks_for_a_date_and_time() -> None:
    async with _open() as user:
        _input(user, "Date").set_value("")
        await _until(lambda: _summary(user) == "Choose a date and a time.")


async def test_a_battery_level_off_the_scale_is_put_right() -> None:
    async with _open() as user:
        (battery,) = user.find(kind=ui.number).elements
        battery.set_value(250)
        await _until(lambda: battery.value == 100)
        battery.set_value(-5)
        await _until(lambda: battery.value == 0)


async def test_a_low_battery_makes_the_low_battery_profile_active() -> None:
    async with _open() as user:
        await _at_monday_ten(user)
        (battery,) = user.find(kind=ui.number).elements
        battery.set_value(10)
        await _until(lambda: _links(user, "Profile 'Low Battery'"))


async def test_clicking_a_name_in_the_answer_jumps_to_it() -> None:
    async with _open() as user:
        await _at_monday_ten(user)
        user.find(kind=ui.link, content="Profile 'Work Hours'").click()
        await _until(lambda: _built["jumps"])
        assert "Work Hours" in _built["jumps"][0]


async def test_a_task_in_the_run_order_can_be_walked_in_the_stepper() -> None:
    async with _open() as user:
        await _at_monday_ten(user)
        user.find(content="Step").click()
        await _until(lambda: _built["steps"])
        assert _built["steps"][0]


async def test_now_puts_the_date_and_time_back() -> None:
    async with _open() as user:
        date = _input(user, "Date")
        date.set_value("2001-01-01")
        user.find(content="Now").click()
        await _until(lambda: date.value != "2001-01-01")
        assert len(date.value) == len("2026-09-28")


async def test_close_closes_the_dialog() -> None:
    async with _open() as user:
        user.find(content="Close").click()
        await _until(lambda: not _built["dialog"].value)


async def test_the_pickers_tell_a_skipped_input_from_one_with_nothing_in_it() -> None:
    assert guiwins_firesim._picked(None) is None
    assert guiwins_firesim._picked(guiwins_firesim._SKIP) is None
    assert guiwins_firesim._picked(guiwins_firesim._NONE) == ""
    assert guiwins_firesim._picked(" Office ") == "Office"
