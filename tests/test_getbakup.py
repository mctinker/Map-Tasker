"""Getting a backup off the Android device, and checking that what arrived is Tasker XML.

No device and no network: maputil2's http_request is replaced with a function that answers
what a device would, and every file is written to a temporary directory the test is in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from maptasker.src import getbakup
from maptasker.src.primitem import RunState

if TYPE_CHECKING:
    from pathlib import Path

_ANDROID_FILE = "/Tasker/configs/user/backup.xml"
_GOOD = b'<?xml version="1.0" encoding="UTF-8"?><TaskerData sr="" dvi="1" tv="6.3.13"></TaskerData>'


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunState:
    """A RunState asking for the standard backup path, working in an empty directory."""
    monkeypatch.chdir(tmp_path)
    run = RunState()
    run.program_arguments.android_file = _ANDROID_FILE
    run.program_arguments.android_ipaddr = "192.168.0.210"
    run.program_arguments.android_port = "1821"
    return run


def _device_answers(monkeypatch: pytest.MonkeyPatch, return_code: int, contents: object) -> list:
    """Make http_request answer (return_code, contents), and keep what it was asked."""
    asked: list = []

    def fake(*args: object, **_kwargs: object) -> tuple:
        asked.append(args)
        return return_code, contents

    monkeypatch.setattr(getbakup, "http_request", fake)
    return asked


def _fail_with(monkeypatch: pytest.MonkeyPatch) -> list:
    """Make error_handler record instead of ending the program."""
    said: list = []
    monkeypatch.setattr(getbakup, "error_handler", lambda message, code, state: said.append((message, code)))
    return said


# ##################################################################################
# Small pieces
# ##################################################################################
@pytest.mark.parametrize(
    ("path", "after"),
    [("/Tasker/configs/user/backup.xml", "backup.xml"), ("backup.xml", ""), ("", ""), ("/", "")],
)
def test_the_file_name_is_what_follows_the_last_slash(path: str, after: str) -> None:
    """A bare name has no slash, so it has nothing after one -- callers pass full paths."""
    assert getbakup.substring_after_last(path, "/") == after


def test_the_fetched_backup_is_written_under_its_own_name(state: RunState, tmp_path: Path) -> None:
    """In the working directory, flagged as fetched so later steps know where it came from."""
    getbakup.write_out_backup_file("héllo <TaskerData/>".encode(), state=state)
    assert (tmp_path / "backup.xml").read_text(encoding="utf-8") == "héllo <TaskerData/>"
    assert state.program_arguments.fetched_backup_from_android is True


def test_a_backup_already_there_is_replaced_not_appended_to(state: RunState, tmp_path: Path) -> None:
    """Yesterday's backup must not survive in the middle of today's."""
    (tmp_path / "backup.xml").write_text("yesterday, and a good deal longer than today", encoding="utf-8")
    getbakup.write_out_backup_file(b"today", state=state)
    assert (tmp_path / "backup.xml").read_text(encoding="utf-8") == "today"


# ##################################################################################
# Fetching
# ##################################################################################
def test_the_gui_has_already_fetched_so_only_the_name_is_returned(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From the window the file is on disk already; asking the device again would be a second prompt."""
    state.program_arguments.gui = True
    asked = _device_answers(monkeypatch, 0, _GOOD)
    assert getbakup.get_backup_file(state=state) == "backup.xml"
    assert asked == []


def test_a_command_line_fetch_downloads_then_saves(
    state: RunState, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET <file>?download=1 from the device's own address, and the answer lands on disk."""
    asked = _device_answers(monkeypatch, 0, _GOOD)
    assert getbakup.get_backup_file(state=state) == "backup.xml"
    assert asked == [("192.168.0.210", "1821", _ANDROID_FILE, "file", "?download=1")]
    assert (tmp_path / "backup.xml").read_bytes() == _GOOD


def test_a_failed_download_ends_the_run_with_the_devices_reason(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit code 8 and the message the device layer produced, not a vague 'failed'."""
    _device_answers(monkeypatch, 8, "Unable to get XML from Android device.")
    said = _fail_with(monkeypatch)
    # error_handler really exits; here it returns, so the write that follows gets the message text.
    monkeypatch.setattr(getbakup, "write_out_backup_file", lambda *_args, **_kwargs: None)
    getbakup.get_backup_file(state=state)
    assert said == [("Unable to get XML from Android device.", 8)]


# ##################################################################################
# Validating
# ##################################################################################
def _validate(state: RunState, contents: bytes = _GOOD, return_code: int = 0, ip: str = "192.168.0.210") -> tuple:
    return getbakup.validate_xml(ip, _ANDROID_FILE, return_code, contents, state=state)


def test_good_xml_validates_and_comes_back_parsed(state: RunState, tmp_path: Path) -> None:
    """The file is written locally, then parsed from there."""
    error, tree = _validate(state)
    assert error == ""
    assert tree.getroot().tag == "TaskerData"
    assert (tmp_path / "backup.xml").exists()


def test_improperly_formed_xml_is_reported_by_name(state: RunState) -> None:
    """The message names the file so a person with several knows which one."""
    error, tree = _validate(state, contents=b"<TaskerData><unclosed></TaskerData>")
    assert tree is None
    assert f"Improperly formatted XML in {_ANDROID_FILE}" in error


def test_a_file_that_cannot_be_read_is_an_error_not_a_crash(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    """An OSError while parsing becomes a message the window can show."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        msg = "Permission denied"
        raise OSError(msg)

    monkeypatch.setattr(getbakup, "parse_tasker_xml", refuse)
    error, tree = _validate(state)
    assert tree is None
    assert "XML parsing error Permission denied" in error


def test_an_encoding_the_file_will_not_decode_is_rewritten_then_given_up_on(
    state: RunState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two rewrites are tried; the third failure is reported, so a bad file cannot loop forever."""
    rewrites: list = []

    def undecodable(*_args: object, **_kwargs: object) -> None:
        msg = "utf-8"
        raise UnicodeDecodeError(msg, b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(getbakup, "parse_tasker_xml", undecodable)
    monkeypatch.setattr(getbakup, "rewrite_xml", rewrites.append)

    error, tree = _validate(state)

    assert tree is None
    assert f"Unicode error in {_ANDROID_FILE}" in error
    assert rewrites == ["backup.xml"] * 3


def test_a_file_that_decodes_after_a_rewrite_is_accepted(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    """The second try works once the file has been rewritten -- the reason for the loop."""
    calls = {"parsed": 0}
    sentinel = object()

    def parse(*_args: object, **_kwargs: object) -> object:
        calls["parsed"] += 1
        if calls["parsed"] == 1:
            msg = "utf-8"
            raise UnicodeDecodeError(msg, b"\xff", 0, 1, "invalid start byte")
        return sentinel

    monkeypatch.setattr(getbakup, "parse_tasker_xml", parse)
    monkeypatch.setattr(getbakup, "rewrite_xml", lambda _name: None)

    assert _validate(state) == ("", sentinel)
    assert calls["parsed"] == 2


# ##################################################################################
# The whole check, as the window runs it
# ##################################################################################
def test_a_valid_backup_passes_the_whole_check(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    """(0, "") is a pass; this is what the window waits for before loading."""
    _device_answers(monkeypatch, 0, _GOOD)
    assert getbakup.validate_xml_file("192.168.0.210", "1821", _ANDROID_FILE, state=state) == (0, "")


def test_an_unreachable_device_fails_the_check_with_its_reason(
    state: RunState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """1 and the device layer's own words; nothing is validated."""
    _device_answers(monkeypatch, 8, "Unable to get XML from Android device.")
    assert getbakup.validate_xml_file("192.168.0.210", "1821", _ANDROID_FILE, state=state) == (
        1,
        "Unable to get XML from Android device.",
    )


def test_broken_xml_fails_the_check(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    """1 and the formatting message."""
    _device_answers(monkeypatch, 0, b"<TaskerData>")
    code, message = getbakup.validate_xml_file("192.168.0.210", "1821", _ANDROID_FILE, state=state)
    assert code == 1
    assert "Improperly formatted XML" in message


def test_xml_that_is_not_tasker_xml_is_called_out(state: RunState, monkeypatch: pytest.MonkeyPatch) -> None:
    """Well-formed but some other document -- the message says so and the caller shows it."""
    _device_answers(monkeypatch, 0, b"<html></html>")
    _code, message = getbakup.validate_xml_file("192.168.0.210", "1821", _ANDROID_FILE, state=state)
    assert "is not valid Tasker XML" in message
