"""The Android XML check in userintr_android: validate the chosen file, or offer the device's list.

validate_or_filelist_xml was one 115-line function with two unrelated halves; it is now a dispatcher over
_validate_chosen_file and _offer_file_list.  What is tested is that the split changed nothing a caller can see:
the same return codes for the same inputs, the same messages shown, and the same decision about which half runs.
The device and the page are faked -- run.io_bound just calls what it is given -- so no NiceGUI page is needed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from maptasker.src import userintr_android

IP, PORT, FILE = "192.168.0.5", "1821", "/sdcard/backup.xml"


@pytest.fixture
def gui(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A stand-in window that records the messages shown, with run.io_bound calling straight through."""

    async def io_bound(function: object, *arguments: object, **keywords: object) -> object:
        return function(*arguments, **keywords)

    monkeypatch.setattr(userintr_android, "run", SimpleNamespace(io_bound=io_bound))
    shown: list[tuple[str, str]] = []
    return SimpleNamespace(
        shown=shown,
        list_files=False,
        state=SimpleNamespace(program_arguments=SimpleNamespace(gui=False), backup_fetch_path=""),
        display_message_box=lambda message, colour: shown.append((message, colour)),
    )


def _device(monkeypatch: pytest.MonkeyPatch, *, fetch: object, validate: object) -> None:
    monkeypatch.setattr(userintr_android, "http_request", lambda *_a, **_k: fetch)
    monkeypatch.setattr(userintr_android, "validate_xml_file", lambda *_a, **_k: validate)


@pytest.mark.asyncio
async def test_a_good_file_returns_zero_and_the_same_details(
    gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _device(monkeypatch, fetch=(0, b""), validate=(0, ""))

    result = await userintr_android.validate_or_filelist_xml(gui, IP, PORT, FILE)

    assert result == (0, IP, PORT, FILE)
    assert gui.state.program_arguments.gui is True
    assert gui.shown == []


@pytest.mark.asyncio
async def test_a_saved_backup_says_where_it_was_saved(gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    gui.state.backup_fetch_path = "/Users/me/MapTasker/backup.xml"
    _device(monkeypatch, fetch=(0, b""), validate=(0, ""))

    result = await userintr_android.validate_or_filelist_xml(gui, IP, PORT, FILE)

    assert result[0] == 0
    assert gui.shown == [("Backup file saved to /Users/me/MapTasker/backup.xml", "Green")]


@pytest.mark.asyncio
async def test_a_file_that_cannot_be_fetched_returns_one(gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    _device(monkeypatch, fetch=(1, b"unreachable"), validate=pytest.fail)

    assert await userintr_android.validate_or_filelist_xml(gui, IP, PORT, FILE) == (1, IP, PORT, FILE)


@pytest.mark.asyncio
async def test_a_cancelled_fetch_or_check_returns_one_quietly(
    gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _device(monkeypatch, fetch=None, validate=(0, ""))
    assert await userintr_android.validate_or_filelist_xml(gui, IP, PORT, FILE) == (1, IP, PORT, FILE)

    _device(monkeypatch, fetch=(0, b""), validate=None)
    assert await userintr_android.validate_or_filelist_xml(gui, IP, PORT, FILE) == (1, IP, PORT, FILE)
    assert gui.shown == []


@pytest.mark.asyncio
async def test_a_file_that_is_not_valid_xml_shows_why_in_red_and_returns_one(
    gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _device(monkeypatch, fetch=(0, b""), validate=(3, "not a Tasker backup"))

    assert await userintr_android.validate_or_filelist_xml(gui, IP, PORT, FILE) == (1, IP, PORT, FILE)
    assert gui.shown == [("not a Tasker backup", "Red")]


@pytest.mark.asyncio
@pytest.mark.parametrize(("file", "listing"), [("", False), (FILE, True)])
async def test_no_file_or_an_explicit_list_request_offers_the_list_instead(
    gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, file: str, listing: bool
) -> None:
    """Whichever half runs is decided exactly as it was: no file, or 'list files' asked for."""
    gui.list_files = listing
    asked: list[tuple] = []

    async def offer(_gui: object, *details: str) -> tuple:
        asked.append(details)
        return (2, "", "", "")

    monkeypatch.setattr(userintr_android, "_offer_file_list", offer)
    monkeypatch.setattr(userintr_android, "_validate_chosen_file", pytest.fail)

    assert await userintr_android.validate_or_filelist_xml(gui, IP, PORT, file) == (2, "", "", "")
    assert asked == [(IP, PORT, file)]


@pytest.mark.asyncio
async def test_a_listing_that_fails_shows_the_reason_and_returns_one(
    gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(userintr_android, "clear_android_buttons", lambda _gui: None)
    monkeypatch.setattr(userintr_android, "ui", SimpleNamespace(notify=lambda *_a, **_k: None))
    monkeypatch.setattr(userintr_android.devicefiles, "get_list_of_files", lambda *_a, **_k: (1, "device not found"))

    result = await userintr_android.validate_or_filelist_xml(gui, IP, PORT, "")

    assert result == (1, IP, PORT, "")
    assert gui.shown == [("device not found", "Red")]


@pytest.mark.asyncio
async def test_a_listing_that_works_mounts_the_picker_and_suspends_the_fetch(
    gui: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    mounted: list[list] = []
    monkeypatch.setattr(userintr_android, "clear_android_buttons", lambda _gui: None)
    monkeypatch.setattr(userintr_android, "ui", SimpleNamespace(notify=lambda *_a, **_k: None))
    monkeypatch.setattr(userintr_android.devicefiles, "get_list_of_files", lambda *_a, **_k: (0, ["a.xml", "b.xml"]))
    monkeypatch.setattr(userintr_android, "_mount_file_picker", lambda _gui, files: mounted.append(files))

    result = await userintr_android.validate_or_filelist_xml(gui, IP, PORT, "")

    assert result == (2, "", "", ""), "2 means: wait for the user to pick a file"
    assert mounted == [["a.xml", "b.xml"]]
    assert (gui.android_ipaddr, gui.android_port) == (IP, PORT)
