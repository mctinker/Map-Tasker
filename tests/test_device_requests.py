"""Android device requests (maputil2) Unit Tests

Every request to the Android device blocks until the device answers or times out, and the GUI
runs on a single event loop -- so a request made there freezes the whole window.  The GUI
hands them to run.io_bound instead.  maputil2 logs any request that arrives on a running event
loop, naming the caller that should have handed it off; these tests pin down when it does and
when it does not.  No device is involved: requests.get answers 404 at once.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from maptasker.src import maputil2

_WARNING = "made on the GUI event loop"


@pytest.fixture(autouse=True)
def no_device(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Every GET answers 404 straight away, and MapTasker's warnings are captured."""
    monkeypatch.setattr(
        maputil2.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=404, content=b""),
    )
    caplog.set_level(logging.WARNING, logger="MapTasker")


def _read_the_device() -> tuple:
    """What a Save To Android does first: ask whether its destination is already there."""
    return maputil2.read_android_file("192.168.0.210", "1821", "/Tasker/tasks/Opener.tsk.xml")


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if _WARNING in record.getMessage()]


def test_a_request_made_on_the_event_loop_is_logged_with_its_caller(caplog: pytest.LogCaptureFixture) -> None:
    """The message names the request and the first caller outside maputil2 -- the line to fix."""

    async def handler() -> tuple:
        return _read_the_device()

    assert asyncio.run(handler()) == (False, b"")

    [message] = _warnings(caplog)
    assert "/Tasker/tasks/Opener.tsk.xml" in message
    assert "test_device_requests.py" in message
    assert "_read_the_device" in message


def test_a_request_handed_to_a_worker_thread_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """What run.io_bound does: the request runs on a thread with no event loop of its own."""

    async def handler() -> tuple:
        return await asyncio.to_thread(_read_the_device)

    assert asyncio.run(handler()) == (False, b"")
    assert _warnings(caplog) == []


def test_a_request_with_no_event_loop_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """The command line has no event loop, so blocking is simply how it works."""
    assert _read_the_device() == (False, b"")
    assert _warnings(caplog) == []
