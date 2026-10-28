"""The Fetch Applications (or Icons) From Android Device dialog, as the Application and Icon pickers open it.

What a fetch installs on the device and what it reads back is deviceinv's; the list it fills is appinv's.  Here it
is the dialog: it says whether it is fetching Applications or Icons, lists each device already fetched from with a
Forget button, spins while the phone is waited on, remembers the address it worked with, and tells its caller to
redraw whenever the list has changed -- by a fetch, or by a device being forgotten and the dialog then cancelled.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core import appinv
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import guiwins_taskedit
from nicegui import ui

from tests.nicegui_harness import button, click, found, inputs, label_texts, open_page

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def fetch(monkeypatch: pytest.MonkeyPatch) -> Any:
    from types import SimpleNamespace

    record = SimpleNamespace(
        devices=[],
        forgotten=[],
        remembered=[],
        fetched=[],
        answer=(0, "Fetched 31 applications."),
        changed=[],
        forget_error="",
    )
    monkeypatch.setattr(appinv, "fetched_devices", lambda: list(record.devices))
    monkeypatch.setattr(appinv, "forget_device", lambda device: record.forgotten.append(device) or record.forget_error)
    monkeypatch.setattr(guiwins_taskedit, "android_address_defaults", lambda gui: ("192.168.1.9", "1821"))
    monkeypatch.setattr(
        guiwins_taskedit, "remember_android_address", lambda gui, ip, port: record.remembered.append((ip, port))
    )
    monkeypatch.setattr(guiwins_taskedit, "remember_android_address_fields", lambda *a: None)

    async def io_bound(function: Any, *args: Any, **kwargs: Any) -> object:
        record.fetched.append(args)
        return record.answer

    monkeypatch.setattr(guiwins_taskedit.run, "io_bound", io_bound)
    record.window = SimpleNamespace(state=RunState(), android_ipaddr="", android_port="")
    return record


def _dialog(record: Any, *, for_icons: bool = False) -> Callable[[], None]:
    def page() -> None:
        guiwins_taskedit._FetchAppsDialog(record.window, lambda: record.changed.append(True), for_icons).build()

    return page


@pytest.mark.asyncio
async def test_the_dialog_for_applications_says_what_the_fetch_will_install_and_read(fetch: Any) -> None:
    async with open_page(_dialog(fetch)) as user:
        labels = label_texts(user)
        assert "Fetch Applications From Android Device" in labels
        assert any("will install a small Task named" in text for text in labels)
        assert any(text.startswith("Watch your Android device") for text in labels)
        assert not any(text.startswith("Icons come from the same place") for text in labels)


@pytest.mark.asyncio
async def test_the_dialog_for_icons_says_which_icons_cannot_be_fetched(fetch: Any) -> None:
    async with open_page(_dialog(fetch, for_icons=True)) as user:
        labels = label_texts(user)
        assert "Fetch Icons From Android Device" in labels
        assert any("Tasker's own built-in icons cannot be fetched" in text for text in labels)


@pytest.mark.asyncio
async def test_the_remembered_address_is_what_the_fields_start_with(fetch: Any) -> None:
    async with open_page(_dialog(fetch)) as user:
        fields = inputs(user)
        assert fields["Android IP Address"].value == "192.168.1.9"
        assert fields["Port"].value == "1821"


@pytest.mark.asyncio
async def test_a_successful_fetch_remembers_the_address_closes_and_tells_the_caller(fetch: Any) -> None:
    async with open_page(_dialog(fetch)) as user:
        fields = inputs(user)
        fields["Android IP Address"].value = "  10.0.0.5 "
        await click(user, "Fetch")
        assert fetch.fetched == [("10.0.0.5", "1821")]
        assert fetch.remembered == [("10.0.0.5", "1821")]
        assert (fetch.window.android_ipaddr, fetch.window.android_port) == ("10.0.0.5", "1821")
        assert user.notify.contains("Fetched 31 applications.")
        assert fetch.changed == [True]
        (dialog,) = found(user, ui.dialog)
        assert not dialog.value
        assert button(user, "Fetch").enabled, "the button is put back whatever happened"


@pytest.mark.asyncio
async def test_a_fetch_that_failed_keeps_the_dialog_for_another_try_and_does_not_remember_the_address(
    fetch: Any,
) -> None:
    fetch.answer = (2, "The device did not answer.")
    async with open_page(_dialog(fetch)) as user:
        await click(user, "Fetch")
        assert user.notify.contains("The device did not answer.")
        assert fetch.changed == []
        assert fetch.window.android_ipaddr == ""
        (dialog,) = found(user, ui.dialog)
        assert dialog.value
        assert button(user, "Fetch").enabled


@pytest.mark.asyncio
async def test_a_wait_that_was_cancelled_has_no_page_left_to_report_to(fetch: Any) -> None:
    fetch.answer = None
    async with open_page(_dialog(fetch)) as user:
        await click(user, "Fetch")
        assert fetch.changed == []
        assert user.notify.messages == []


@pytest.mark.asyncio
async def test_each_device_already_fetched_from_is_listed_with_a_way_to_forget_it(fetch: Any) -> None:
    fetch.devices = [("Pixel", "2026-10-01", 120), ("Tablet", "2026-09-02", 80)]
    async with open_page(_dialog(fetch)) as user:
        labels = label_texts(user)
        assert "Pixel: 120 applications, fetched 2026-10-01" in labels
        assert "Tablet: 80 applications, fetched 2026-09-02" in labels
        assert len([b for b in found(user, ui.button) if b.text == "Forget"]) == 2


@pytest.mark.asyncio
async def test_forgetting_a_device_redraws_the_list_and_cancel_then_tells_the_caller(fetch: Any) -> None:
    fetch.devices = [("Pixel", "2026-10-01", 120)]
    async with open_page(_dialog(fetch)) as user:
        fetch.devices = []
        await click(user, "Forget")
        assert fetch.forgotten == ["Pixel"]
        assert user.notify.contains("Forgot the applications fetched from Pixel")
        assert "Pixel: 120 applications, fetched 2026-10-01" not in label_texts(user)
        await click(user, "Cancel")
        assert fetch.changed == [True], "a forgotten device has changed the list all the same"


@pytest.mark.asyncio
async def test_a_forget_that_could_not_be_saved_says_so(fetch: Any) -> None:
    fetch.devices = [("Pixel", "2026-10-01", 120)]
    fetch.forget_error = "read-only file system"
    async with open_page(_dialog(fetch)) as user:
        await click(user, "Forget")
        assert user.notify.contains("Forgotten for now, but could not be saved: read-only file system")


@pytest.mark.asyncio
async def test_cancel_with_nothing_forgotten_changes_nothing(fetch: Any) -> None:
    async with open_page(_dialog(fetch)) as user:
        await click(user, "Cancel")
        assert fetch.changed == []
        (dialog,) = found(user, ui.dialog)
        assert not dialog.value


@pytest.mark.asyncio
async def test_the_public_entry_point_builds_the_same_dialog(fetch: Any) -> None:
    def page() -> None:
        # The entry point awaits nothing, so stepping the coroutine once builds the dialog inside this page's slot.
        coroutine = guiwins_taskedit._build_fetch_apps_dialog(fetch.window, lambda: None, for_icons=True)
        with contextlib.suppress(StopIteration):
            coroutine.send(None)

    async with open_page(page) as user:
        assert "Fetch Icons From Android Device" in label_texts(user)


@pytest.mark.parametrize(
    ("output", "shown"),
    [
        ('{"a": 1}', '{\n  "a": 1\n}'),
        ("[1, 2]", "[\n  1,\n  2\n]"),
        ("plain text", "plain text"),
        ("42", "42"),
        ('"café"', '"café"'),
    ],
)
def test_a_tasks_return_value_is_laid_out_as_json_only_when_it_is_a_container(output: str, shown: str) -> None:
    assert guiwins_taskedit._format_task_output(output) == shown
