"""A simulated NiceGUI window to put one dialog or drawing in, and the few ways tests look at what it holds.

A test hands `open_page` a function that builds some UI -- a dialog, a drawer, a canvas -- and gets back a user
looking at a page that ran it.  `found` is user.find without its assertion for "nothing there", and typed, which
the library's own is not; `button`, `click` and `labels` are the three things nearly every such test does.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import TYPE_CHECKING, Any, TypeVar, cast

from nicegui import background_tasks, core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

T = TypeVar("T")


_build: dict[str, Callable[[], None]] = {}


def _page() -> None:
    _build["page"]()


@contextlib.asynccontextmanager
async def open_page(build: Callable[[], None]) -> AsyncIterator[User]:
    """Open a window whose page is whatever `build` puts up, and close the app afterwards."""
    _build["page"] = build
    _waited_for.clear()
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            stop_waiting_for_what_is_running()  # what the page started while it was built is not a click's doing
            yield user
    finally:
        _waited_for.clear()
        if core.app.is_started:
            await core.app.stop()


def found(user: User, kind: type[T]) -> list[T]:
    """Every visible element of this kind on the page, in the order they were built -- an empty list when none.

    NiceGUI hands back a set, whose order differs from one run (and one platform, and one Python) to the next, so
    a test that took the last of them was taking an arbitrary one.  An element's id counts up as the page is built.
    """
    try:
        elements = cast("set[T]", cast("Any", user).find(kind=kind).elements)
        return sorted(elements, key=lambda element: cast("ui.element", element).id)
    except AssertionError:
        return []


def button(user: User, text: str) -> ui.button:
    """The one button with exactly this text."""
    (element,) = [e for e in found(user, ui.button) if e.text == text]
    return element


# The longest `idle` waits for the work a click set going.  Nothing a test clicks takes anywhere near this; it is the
# bound on a task that never ends (a poll, a monitor) so that waiting for it cannot hang a test.
IDLE_CAP_SECONDS = 5.0
# What NiceGUI itself keeps running for as long as a page is up: a timer's loop, the outbox, the client refresh.  They
# are in `background_tasks.running_tasks` and they never finish, so waiting for them would be waiting out the cap.
_FOR_AS_LONG_AS_THE_PAGE_IS_UP = ("Timer._run_in_loop", "refresh_loop", "Outbox.loop")


# Tasks `idle` has already waited for (or given up on), so that one that is parked on a person -- a confirmation put
# up and `await`ed -- costs the wait once and not on every click after it.
_waited_for: set[asyncio.Task[Any]] = set()


def _doing_something() -> set[asyncio.Task[Any]]:
    """The tasks NiceGUI is running for a handler: not the page's own, and not any already waited for."""
    me = asyncio.current_task()
    return {
        task
        for task in background_tasks.running_tasks
        if not task.done()
        and task is not me
        and task not in _waited_for
        and not str(getattr(task.get_coro(), "__qualname__", "")).endswith(_FOR_AS_LONG_AS_THE_PAGE_IS_UP)
    }


def stop_waiting_for_what_is_running() -> None:
    """From here on `idle` waits only for what starts after this: the page's own tasks, and a handler left waiting."""
    _waited_for.update(_doing_something())


async def idle(seconds: float | None = None) -> None:
    """Wait until what the last click or change set going has finished, however long the machine takes over it.

    A handler that is `async`, or that hands work to a thread, runs as a task NiceGUI keeps in
    `background_tasks.running_tasks` until it is done.  Waiting for those, rather than for a fixed tenth of a second,
    is the difference between a test that passes because the machine is quick and one that passes because the thing
    happened: the Android panel's tests failed on a slow Windows runner and on a loaded macOS one for this reason.

    A task that is started and never ends (a poll, a monitor) is waited for only up to `seconds`, so it costs a test
    that long and cannot hang it, and is not waited for again.
    """
    seconds = IDLE_CAP_SECONDS if seconds is None else seconds
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    await asyncio.sleep(0)  # the click has queued its handler's task; let it start
    while loop.time() < deadline:
        if not (pending := _doing_something()):
            break
        await asyncio.wait(pending, timeout=min(0.1, max(0.0, deadline - loop.time())))
    else:
        _log_cap(seconds)
    stop_waiting_for_what_is_running()
    await asyncio.sleep(0)  # and one more turn for what the last of them scheduled


def _log_cap(seconds: float) -> None:
    """For finding the tasks that never end: set MAPTASKER_IDLE_LOG to a file and each wait that ran out is added."""
    path = os.environ.get("MAPTASKER_IDLE_LOG")
    if not path:
        return
    pending = [repr(task.get_coro()) for task in _doing_something()]
    with open(path, "a", encoding="utf-8") as log:
        log.write(f"{os.environ.get('PYTEST_CURRENT_TEST', '?')} waited {seconds}s for {pending}\n")


async def press(user: User, element: ui.button, *, wait: bool = True) -> None:
    """Press this button, and wait for what it starts to finish.

    `wait=False` for a handler that ends by waiting on the person -- a confirmation it has put up and `await`s -- which
    would otherwise be waited for until the cap: the handler has built what it shows by the time it first waits, and
    that is all this gives it.
    """
    UserInteraction(user, {element}, None).click()
    if wait:
        await idle()
        return
    await asyncio.sleep(0)  # the handler's task starts on the next turn and builds its dialog before it first waits
    await asyncio.sleep(0)
    stop_waiting_for_what_is_running()


async def settled(condition: Callable[[], object], seconds: float = 15.0) -> None:
    """Wait until this is true, for as long as `seconds`: a refused connection takes Windows about two seconds."""
    deadline = asyncio.get_running_loop().time() + seconds
    while not condition() and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.1)


async def click(user: User, text: str) -> None:
    """Press the button with this text."""
    await press(user, button(user, text))


def label_texts(user: User) -> list[str]:
    """The text of every label on the page."""
    return [e.text for e in found(user, ui.label)]


def inputs(user: User) -> dict[str, ui.input]:
    """Every input on the page, by its label."""
    return {str(e.props.get("label")): e for e in found(user, ui.input)}


def dialogs(user: User) -> list[ui.dialog]:
    """Every dialog on the page."""
    return found(user, ui.dialog)


def all_elements(user: User) -> list[Any]:
    """Every element the page holds, visible or not -- for the ones user.find would not report."""
    assert user.client is not None
    return list(user.client.elements.values())
