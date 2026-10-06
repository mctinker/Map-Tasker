"""maputils: the small utilities the rest of the program leans on.

None of them is large, but each one has an answer the callers depend on that is not the one
the signature suggests -- validate_port returns 0 for success and says bool, rename_file
reports failure with a message and a False, a '#' goes on a six-digit color and comes off a
three-digit one -- so these pin the answers down.

Network and process calls (PyPI, the IP-geolocation service, restarting the program) are
replaced with functions; nothing here reaches out.
"""

from __future__ import annotations

import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from maptasker.src import clock, console, maputils
from maptasker.src.primitem import PrimeItems

from tests.test_mapswap import _FIXTURE_XML, _load


@pytest.fixture
def backup() -> None:
    """test_mapswap's fixture: Projects Home (Profiles 100-102, Tasks 20-22) -- see _FIXTURE_XML."""
    _load(_FIXTURE_XML)


# ##################################################################################
# Addresses and ports.
# ##################################################################################
@pytest.mark.parametrize(
    ("address", "valid"),
    [
        ("192.168.0.210", True),
        ("0.0.0.0", True),
        ("::1", True),
        ("fe80::1", True),
        ("256.1.1.1", False),
        ("1.2.3", False),
        ("host.local", False),
        ("", False),
        (" 1.2.3.4", False),
    ],
)
def test_an_ip_address_is_valid_or_it_is_not(address: str, valid: bool) -> None:
    assert maputils.validate_ip_address(address) is valid


def test_a_port_is_zero_when_it_is_fine_and_nonzero_when_it_is_not() -> None:
    """The callers test '!= 0', so 0 means valid -- the opposite of what a bool return would say."""
    assert maputils.validate_port("", "1821") == 0
    assert maputils.validate_port("", "65535") == 0
    assert maputils.validate_port("", "1024") == 0
    for bad in ("1023", "65536", "0", "abc", "", "18.2", "-5"):
        assert maputils.validate_port("", bad) == 1, bad


def test_a_port_with_an_address_is_tried_and_the_socket_result_is_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    tried = []

    class FakeSocket:
        def __init__(self, *_: object) -> None:
            self.closed = False

        def connect_ex(self, server: tuple[str, int]) -> int:
            tried.append(server)
            return 111

        def close(self) -> None:
            tried.append("closed")

    monkeypatch.setattr(maputils.socket, "socket", FakeSocket)

    assert maputils.validate_port("192.168.0.2", "1821") == 111
    assert tried == [("192.168.0.2", 1821), "closed"]


def test_a_port_that_is_out_of_range_is_not_tried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(maputils.socket, "socket", lambda *_: pytest.fail("a socket was opened"))

    assert maputils.validate_port("192.168.0.2", "80") == 1


# ##################################################################################
# The newest version on PyPI.
# ##################################################################################
class _Reply:
    def __init__(self, payload: object = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def json(self) -> object:
        if self.error:
            raise self.error
        return self.payload

    def raise_for_status(self) -> None:
        return None


def test_the_pypi_version_comes_back_ready_to_hand_to_pip(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def get(url: str, timeout: float) -> _Reply:
        seen.update(url=url, timeout=timeout)
        return _Reply({"info": {"version": "14.2.0"}})

    monkeypatch.setattr(maputils.requests, "get", get)

    assert maputils.get_pypi_version() == "==14.2.0"
    assert seen == {"url": "https://pypi.org/pypi/maptasker/json", "timeout": maputils.PYPI_TIMEOUT_SECONDS}


@pytest.mark.parametrize(
    "reply",
    [_Reply(error=ValueError("not json")), _Reply({"info": {}}), _Reply({}), _Reply(["info"]), _Reply(None)],
)
def test_a_pypi_answer_that_is_not_pypis_is_no_version(monkeypatch: pytest.MonkeyPatch, reply: _Reply) -> None:
    monkeypatch.setattr(maputils.requests, "get", lambda *_, **__: reply)

    assert maputils.get_pypi_version() == ""


def test_pypi_not_answering_is_no_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise requests.ConnectionError("down")

    monkeypatch.setattr(maputils.requests, "get", refuse)

    assert maputils.get_pypi_version() == ""


# ##################################################################################
# The time, by way of the IP address.
# ##################################################################################
def test_the_timezone_comes_from_the_geolocation_service(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def get(url: str, timeout: float) -> _Reply:
        seen.update(url=url, timeout=timeout)
        return _Reply({"timezone": "America/Mexico_City", "city": "x"})

    monkeypatch.setattr(maputils.requests, "get", get)

    assert maputils.get_timezone_from_ip() == "America/Mexico_City"
    assert seen["url"] == "https://ipinfo.io/json"
    assert seen["timeout"] == 5


@pytest.mark.parametrize(
    "reply",
    [
        _Reply({}),
        _Reply({"timezone": ""}),
        _Reply({"timezone": None}),
        _Reply(error=ValueError("x")),
        _Reply(["timezone"]),
    ],
)
def test_a_reply_without_a_timezone_is_none(monkeypatch: pytest.MonkeyPatch, reply: _Reply) -> None:
    monkeypatch.setattr(maputils.requests, "get", lambda *_, **__: reply)

    assert maputils.get_timezone_from_ip() is None


def test_a_service_that_is_down_is_no_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise requests.Timeout("slow")

    monkeypatch.setattr(maputils.requests, "get", refuse)

    assert maputils.get_timezone_from_ip() is None


def test_a_bad_status_is_no_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    class Failing(_Reply):
        def raise_for_status(self) -> None:
            raise requests.HTTPError("503")

    monkeypatch.setattr(maputils.requests, "get", lambda *_, **__: Failing({"timezone": "Europe/Paris"}))

    assert maputils.get_timezone_from_ip() is None


def test_the_local_time_is_in_the_timezone_the_address_says(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(maputils, "get_timezone_from_ip", lambda: "Asia/Tokyo")

    moment = maputils.get_current_local_time_auto_timezone()

    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(hours=9)


@pytest.mark.parametrize("zone", [None, "", "Not/AZone", "bad zone!!"])
def test_a_timezone_that_is_missing_or_unknown_falls_back_to_the_system_clock(
    monkeypatch: pytest.MonkeyPatch, zone: str | None
) -> None:
    fixed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)  # noqa: UP017
    monkeypatch.setattr(maputils, "get_timezone_from_ip", lambda: zone)
    monkeypatch.setattr(clock, "now", lambda: fixed)

    assert maputils.get_current_local_time_auto_timezone() == fixed


# ##################################################################################
# Strings.
# ##################################################################################
@pytest.mark.parametrize(
    ("text", "sub", "expected"),
    [
        ("", "a", 0),
        ("abc", "", 0),
        ("aaabaa", "a", 3),
        ("ababab", "ab", 3),
        ("abxab", "ab", 1),
        ("<br><br><br>x<br>", "<br>", 3),
        ("abcabc", "abcd", 0),
        ("aaaa", "aa", 2),
        ("xaay", "aa", 1),
        ("a", "ab", 0),
        ("ab", "ab", 1),
    ],
)
def test_the_longest_run_of_a_substring_is_counted(text: str, sub: str, expected: int) -> None:
    assert maputils.count_consecutive_substr(text, sub) == expected


def test_all_the_positions_of_a_substring_are_found_even_when_they_overlap() -> None:
    assert maputils.find_all_positions("abcabcab", "ab") == [0, 3, 6]
    assert maputils.find_all_positions("aaa", "aa") == [0, 1]
    assert maputils.find_all_positions("abcabcab", "ab", 1) == [3, 6]
    assert maputils.find_all_positions("abc", "z") == []
    assert maputils.find_all_positions("", "a") == []


def test_a_suffix_goes_before_the_extension() -> None:
    assert maputils.append_to_filename("report.pdf", "_new") == "report_new.pdf"
    assert maputils.append_to_filename("archive.tar.gz", "_2") == "archive.tar_2.gz"
    assert maputils.append_to_filename("noext", "_x") == "noext_x"
    assert maputils.append_to_filename("/a/b.c/file.txt", "!") == "/a/b.c/file!.txt"
    assert maputils.append_to_filename(".hidden", "_x") == ".hidden_x"


def test_a_filename_that_is_not_text_is_refused() -> None:
    assert maputils.append_to_filename(None, "_x") is None
    assert maputils.append_to_filename("a.txt", 5) is None


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("00ff20", "#00ff20"),
        ("#33AAFF", "#33aaff"),
        ("  #33aaff  ", "#33aaff"),
        ("F00", "f00"),
        ("#f00", "f00"),
        ("green", "green"),
        ("  Lavender ", "Lavender"),
        ("12345", "12345"),
        ("1234567", "1234567"),
        ("ggg", "ggg"),
        ("", ""),
    ],
)
def test_a_six_digit_color_gets_its_hash_and_a_three_digit_one_loses_it(given: str, expected: str) -> None:
    assert maputils.make_hex_color(given) == expected


def test_a_dictionary_is_printed_with_its_nesting_as_tabs(monkeypatch: pytest.MonkeyPatch) -> None:
    shown = []
    monkeypatch.setattr(console, "debug", shown.append)

    maputils.pretty({"a": 1, "b": {"c": 2, "d": {"e": 3}}})

    assert shown == ["a", "\t1", "b", "\tc", "\t\t2", "\td", "\t\te", "\t\t\t3"]


# ##################################################################################
# Who owns what.
# ##################################################################################
def test_a_profile_is_owned_by_the_project_that_lists_it(backup: None) -> None:
    assert maputils.find_owning_project("Morning", state=PrimeItems) == "Home"
    assert maputils.find_owning_project("Nobody", state=PrimeItems) == ""


def test_a_task_is_owned_by_the_project_that_lists_it_directly(backup: None) -> None:
    assert maputils.find_owning_project_for_task("Noisy", state=PrimeItems) == "Home"
    assert maputils.find_owning_project_for_task("Nobody", state=PrimeItems) == ""


def test_a_task_in_no_project_is_owned_through_the_profile_that_runs_it(backup: None) -> None:
    home = PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"]
    home.find("tids").text = "21,22"  # Task 20 ('Noisy') is no longer listed, but Profile 100 runs it.

    assert maputils.find_owning_profile("Noisy", state=PrimeItems) == "Morning"
    assert maputils.find_owning_project_for_task("Noisy", state=PrimeItems) == "Home"


def test_a_profile_is_found_from_its_entry_or_exit_task(backup: None) -> None:
    PrimeItems.tasker_root_elements["all_profiles"]["100"]["xml"].find("mid0").text = "99"
    ET_exit = PrimeItems.tasker_root_elements["all_profiles"]["100"]["xml"]
    child = type(ET_exit)("mid1")
    child.text = "21"
    ET_exit.append(child)

    assert maputils.find_owning_profile("Opener", state=PrimeItems) == "Morning"  # Task 21, as its Exit.
    assert maputils.find_owning_profile("Nobody", state=PrimeItems) == ""


def test_a_scene_is_owned_by_the_project_that_lists_it_by_name(backup: None) -> None:
    home = PrimeItems.tasker_root_elements["all_projects"]["Home"]["xml"]
    child = type(home)("scenes")
    child.text = "MainMenu,Settings"
    home.append(child)

    assert maputils.find_owning_project_for_scene("Settings", state=PrimeItems) == "Home"
    # A substring is not a match: "Main" is not "MainMenu".
    assert maputils.find_owning_project_for_scene("Main", state=PrimeItems) == ""
    assert maputils.find_owning_project_for_scene("Nobody", state=PrimeItems) == ""


def test_the_single_name_is_reset_for_whichever_was_asked_for(backup: None, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(maputils, "clear_single_items", lambda **kwargs: calls.append(kwargs["keep"]))
    arguments = {"single_task_name": "", "single_profile_name": "P"}
    monkeypatch.setattr(PrimeItems, "program_arguments", arguments)

    maputils.reset_named_objects(state=PrimeItems)
    assert calls == ["single_profile_name"]

    arguments["single_task_name"] = "T"
    maputils.reset_named_objects(state=PrimeItems)
    assert calls == ["single_profile_name", "single_task_name"]  # The Task wins.

    arguments.update(single_task_name="", single_profile_name="")
    maputils.reset_named_objects(state=PrimeItems)
    assert len(calls) == 2


# ##################################################################################
# Files and processes.
# ##################################################################################
def test_a_file_is_renamed(tmp_path: Path) -> None:
    old = tmp_path / "old.txt"
    old.write_text("x", encoding="utf-8")

    assert maputils.rename_file(str(old), str(tmp_path / "new.txt")) is True

    assert not old.exists()
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "x"


def test_a_file_that_is_not_there_is_not_renamed(tmp_path: Path) -> None:
    assert maputils.rename_file(str(tmp_path / "nope"), str(tmp_path / "new")) is False
    assert not (tmp_path / "new").exists()


def test_a_rename_that_the_system_refuses_is_reported_not_raised(tmp_path: Path) -> None:
    old = tmp_path / "old.txt"
    old.write_text("x", encoding="utf-8")

    assert maputils.rename_file(str(old), str(tmp_path / "no" / "such" / "dir" / "new.txt")) is False
    assert old.exists()


def test_a_rename_needs_two_names() -> None:
    assert maputils.rename_file(None, "x") is False
    assert maputils.rename_file("x", None) is False


def _restart_harness(monkeypatch: pytest.MonkeyPatch) -> dict:
    started: dict = {}
    monkeypatch.setattr(maputils.subprocess, "Popen", lambda args: started.setdefault("args", args))
    monkeypatch.setattr(maputils.time, "sleep", lambda seconds: started.setdefault("slept", seconds))
    monkeypatch.setattr(maputils.console, "say", lambda text: started.setdefault("said", text))
    monkeypatch.setattr(sys, "argv", ["maptasker", "-debug", "-detail", "2"])
    return started


def test_restarting_starts_a_new_copy_with_the_same_arguments_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    started = _restart_harness(monkeypatch)
    state = types.SimpleNamespace(slash=os.sep)

    with pytest.raises(SystemExit) as stopped:
        maputils.restart_program_subprocess(state)

    assert stopped.value.code == 0
    interpreter, script, *arguments = started["args"]
    assert interpreter == sys.executable
    assert script.endswith("main.py")
    assert "maputils.py" not in script
    assert arguments == ["-debug", "-detail", "2"]
    assert "Restarting" in started["said"]


@pytest.mark.asyncio
async def test_restarting_from_inside_the_event_loop_stops_the_server_on_another_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nicegui.core  # noqa: PLC0415

    started = _restart_harness(monkeypatch)
    stopped = []
    monkeypatch.setattr(nicegui.core, "stop_and_exit", lambda: stopped.append(1))
    threads = []
    real_thread = maputils.threading.Thread
    monkeypatch.setattr(maputils.threading, "Thread", lambda **kwargs: threads.append(kwargs) or real_thread(**kwargs))

    maputils.restart_program_subprocess(types.SimpleNamespace(slash=os.sep))  # Must not raise SystemExit here.

    assert started["args"][0] == sys.executable
    assert threads and threads[0]["daemon"] is True
    # It was handed to a thread rather than called here, where it would deadlock the loop.
    for _ in range(50):
        if stopped:
            break
        import asyncio  # noqa: PLC0415

        await asyncio.sleep(0.02)
    assert stopped == [1]


def test_console_scripts_are_not_moved_off_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "maptasker.exe").write_text("x", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))

    assert maputils.move_locked_scripts_aside() == []
    assert (tmp_path / "maptasker.exe").exists()


def test_a_script_that_cannot_be_renamed_is_left_for_the_installer_to_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = tmp_path / "maptasker.exe"
    script.write_text("x", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    real_rename = Path.rename

    def refuse(self: Path, target: Path) -> Path:
        if self == script:
            raise PermissionError("in use")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", refuse)

    assert maputils.move_locked_scripts_aside() == []
    assert script.exists()
