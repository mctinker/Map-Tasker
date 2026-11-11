"""The test harness waits for what a click starts, not for a guess at how long it takes.

A fixed tenth of a second after every click passed on a quick machine and failed on a slow CI runner (Windows once,
macOS once, for the Android panel's tests), because the handler under test hands work to a thread or awaits something.
`idle` waits for the tasks NiceGUI is running for a handler instead.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import pytest
from nicegui import ui

from tests.nicegui_harness import IDLE_CAP_SECONDS, button, idle, open_page, press

if TYPE_CHECKING:
    from collections.abc import Callable


def _page(done: list[str], *, took: float = 0.5, forever: asyncio.Future[None] | None = None) -> Callable[[], None]:
    def build() -> None:
        async def slow() -> None:
            await asyncio.sleep(took)
            done.append("slow")

        async def ask_and_wait() -> None:
            done.append("asked")
            await (forever or asyncio.get_running_loop().create_future())

        def quick() -> None:
            done.append("quick")

        ui.button("slow", on_click=slow)
        ui.button("ask", on_click=ask_and_wait)
        ui.button("quick", on_click=quick)

    return build


@pytest.mark.asyncio
async def test_pressing_waits_for_a_handler_that_takes_longer_than_a_tenth_of_a_second() -> None:
    done: list[str] = []
    async with open_page(_page(done)) as user:
        await press(user, button(user, "slow"))

        assert done == ["slow"], "the press returned before the handler had finished"


@pytest.mark.asyncio
async def test_pressing_a_quick_handler_does_not_wait_out_a_cap() -> None:
    done: list[str] = []
    async with open_page(_page(done)) as user:
        started = time.monotonic()
        await press(user, button(user, "quick"))

        assert done == ["quick"]
        assert time.monotonic() - started < IDLE_CAP_SECONDS / 5, "the pages's own tasks were waited for"


@pytest.mark.asyncio
async def test_a_handler_left_waiting_on_a_person_is_given_what_it_built_and_no_more() -> None:
    done: list[str] = []
    async with open_page(_page(done)) as user:
        started = time.monotonic()
        await press(user, button(user, "ask"), wait=False)
        await press(user, button(user, "quick"))

        assert done == ["asked", "quick"]
        assert time.monotonic() - started < IDLE_CAP_SECONDS / 5, "the second press waited for the first's handler"


@pytest.mark.asyncio
async def test_a_task_that_never_ends_costs_the_cap_once_and_not_on_every_press(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tests.nicegui_harness as harness

    monkeypatch.setattr(harness, "IDLE_CAP_SECONDS", 0.4)
    done: list[str] = []
    async with open_page(_page(done)) as user:
        started = time.monotonic()
        await press(user, button(user, "ask"))  # waited for, up to the cap
        first = time.monotonic() - started
        await press(user, button(user, "quick"))  # not waited for again
        second = time.monotonic() - started - first

        assert 0.3 <= first < 2
        assert second < 0.3


@pytest.mark.asyncio
async def test_idle_with_nothing_running_returns_at_once() -> None:
    done: list[str] = []
    async with open_page(_page(done)):
        started = time.monotonic()
        await idle()

        assert time.monotonic() - started < 0.2
