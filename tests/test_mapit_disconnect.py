"""A browser tab that stops answering (mapit's disconnect handling) Unit Tests

A tab the browser has suspended looks to NiceGUI like a dropped websocket, and the page then retries in a loop -- a disconnect
every few seconds.  What is tested is that the server side of that is calm: a wait for the tab to come back, one per tab and
never a pile of them; a tab that does come back is left alone; and one that does not has the work MapTasker started for it
(the Live Run Monitor asking the phone) stopped, without that work being asked to touch a page that is gone.

No browser is involved.  A client is a stand-in with the three things the handler reads, and the waits are shortened.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from maptasker.src import mapit
from maptasker.src.core.primitem import RunState
from nicegui import app

from tests.doubles import fake_state


class _Client:
    """The three things the handler reads of a NiceGUI client."""

    def __init__(self, client_id: str = "c1", *, connected: bool = False, deleted: bool = False) -> None:
        self.id = client_id
        self.has_socket_connection = connected
        self.is_deleted = deleted


class _Monitor:
    """A Live Run Monitor, in the one respect the handler cares about: whose page it is on, and being told to give up."""

    def __init__(self, client: _Client) -> None:
        self.dialog = SimpleNamespace(client=client)
        self.abandoned = 0

    def abandon(self) -> None:
        self.abandoned += 1


def _state(monitor: _Monitor | None) -> RunState:
    dialog = SimpleNamespace(monitor=monitor) if monitor is not None else None
    return fake_state(mygui=SimpleNamespace(monitor_dialog=dialog))


@pytest.fixture(autouse=True)
def _short_waits(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(mapit, "DISCONNECT_GRACE_SECONDS", 0.05)
    monkeypatch.setattr(mapit, "_reconnect_timeout", lambda: 0.05)
    mapit._waiting.clear()
    yield
    for task in list(mapit._waiting.values()):
        task.cancel()
    mapit._waiting.clear()


async def _settle() -> None:
    await asyncio.sleep(0.25)


@pytest.mark.asyncio
async def test_a_tab_that_does_not_come_back_has_its_monitor_stopped() -> None:
    client = _Client()
    monitor = _Monitor(client)

    await mapit._on_client_disconnect(client, _state(monitor))

    assert monitor.abandoned == 1


@pytest.mark.asyncio
async def test_a_tab_that_is_back_when_the_wait_ends_is_left_alone() -> None:
    client = _Client()
    monitor = _Monitor(client)
    task = asyncio.create_task(mapit._on_client_disconnect(client, _state(monitor)))
    await asyncio.sleep(0.01)
    client.has_socket_connection = True
    await task

    assert monitor.abandoned == 0


@pytest.mark.asyncio
async def test_a_tab_that_connects_again_cancels_the_wait() -> None:
    client = _Client()
    monitor = _Monitor(client)
    task = asyncio.create_task(mapit._on_client_disconnect(client, _state(monitor)))
    await asyncio.sleep(0.01)
    assert "c1" in mapit._waiting

    mapit._on_client_connect(client)
    with pytest.raises(asyncio.CancelledError):
        await task

    assert monitor.abandoned == 0
    assert mapit._waiting == {}


@pytest.mark.asyncio
async def test_a_connection_that_flaps_leaves_one_wait_not_a_pile() -> None:
    client = _Client()
    monitor = _Monitor(client)
    tasks = []
    for _ in range(6):
        tasks.append(asyncio.create_task(mapit._on_client_disconnect(client, _state(monitor))))
        await asyncio.sleep(0.005)

    assert len(mapit._waiting) == 1
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert sum(isinstance(result, asyncio.CancelledError) for result in results) == 5
    assert monitor.abandoned == 1, "the monitor is stopped once, by the last wait"


@pytest.mark.asyncio
async def test_each_tab_has_its_own_wait() -> None:
    first, second = _Client("a"), _Client("b")
    tasks = [asyncio.create_task(mapit._on_client_disconnect(client, _state(None))) for client in (first, second)]
    await asyncio.sleep(0.01)

    assert set(mapit._waiting) == {"a", "b"}
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_another_tabs_monitor_is_not_stopped() -> None:
    gone, other = _Client("gone"), _Client("other", connected=True)
    monitor = _Monitor(other)

    await mapit._on_client_disconnect(gone, _state(monitor))

    assert monitor.abandoned == 0


@pytest.mark.asyncio
async def test_a_client_that_is_already_deleted_is_left_alone() -> None:
    client = _Client(deleted=True)
    monitor = _Monitor(client)

    await mapit._on_client_disconnect(client, _state(monitor))

    assert monitor.abandoned == 0


@pytest.mark.asyncio
async def test_with_no_monitor_or_no_window_a_disconnect_is_just_a_wait() -> None:
    await mapit._on_client_disconnect(_Client(), _state(None))
    await mapit._on_client_disconnect(_Client("x"), fake_state(mygui=None))


def test_the_wait_is_longer_than_nicegus_own_reconnect_timeout() -> None:
    """So NiceGUI has deleted the client by the time this looks: it adds to the timeout rather than replacing it."""
    source = inspect.getsource(mapit._on_client_disconnect)

    assert "_reconnect_timeout() + DISCONNECT_GRACE_SECONDS" in source


def test_the_timeout_is_the_one_ui_run_was_given_or_nicegus_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # the autouse fixture replaced it
    assert mapit._reconnect_timeout() > 0
    monkeypatch.setattr(app.config, "reconnect_timeout", 10.0, raising=False)
    assert mapit._reconnect_timeout() == 10.0


def test_the_handlers_are_registered_once_and_nicegui_can_call_them() -> None:
    before = (len(app._disconnect_handlers), len(app._connect_handlers))

    mapit.install_disconnect_handling(fake_state(mygui=None))
    mapit.install_disconnect_handling(fake_state(mygui=None))

    after = (len(app._disconnect_handlers), len(app._connect_handlers))
    assert after[0] - before[0] <= 1
    assert after[1] - before[1] <= 1
    registered = app._disconnect_handlers[-1]
    # NiceGUI passes the client only to a handler of exactly one parameter (a functools.partial with the state bound
    # counts two, and was called with none).
    assert [p.name for p in inspect.signature(registered).parameters.values()] == ["client"]


@pytest.mark.asyncio
async def test_a_real_nicegui_disconnect_reaches_the_handler_with_its_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """NiceGUI itself, not a stand-in: dropping a page's socket calls the registered handler with that page's client."""
    import contextlib

    from maptasker.src.core.primitem import PrimeItems
    from nicegui import Client, core, ui
    from nicegui.testing.user_simulation import user_simulation

    monkeypatch.setattr(mapit, "_installed", {"done": False})

    def page() -> None:
        ui.label("hello")

    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
            mapit.install_disconnect_handling(PrimeItems)  # the simulation starts with an app of its own
            client = list(Client.instances.values())[-1]
            # What Client.handle_disconnect does for each registered handler (the simulated user has no socket).
            for handler in core.app._disconnect_handlers:
                client.safe_invoke(handler)
            await asyncio.sleep(0.05)

            assert client.id in mapit._waiting
            mapit._on_client_connect(client)
    finally:
        with contextlib.suppress(Exception):
            if core.app.is_started:
                await core.app.stop()
