"""The program's top level: what happens when it crashes, how it starts up and what it does with a report request."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from maptasker.src import mapit
from maptasker.src.core import console
from maptasker.src.core.primitem import PrimeItems


def _crash() -> tuple[type, BaseException, object]:
    try:
        raise ValueError("a genuine bug")
    except ValueError as error:
        return type(error), error, error.__traceback__


@pytest.fixture
def quiet_console(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Console output captured, so a crash report does not land in the test run's own output."""
    heard: dict[str, list[str]] = {"error": [], "say": []}
    monkeypatch.setattr(console, "error", heard["error"].append)
    monkeypatch.setattr(console, "say", lambda text, **_kw: heard["say"].append(text))
    return heard


# ##################################################################################
# A crash
# ##################################################################################
def test_a_crash_is_a_plain_message_and_a_log_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet_console: dict
) -> None:
    """Someone running MapTasker is not shown a stack trace; it goes in a file they can send."""
    log = tmp_path / "maptasker_debug.log"
    monkeypatch.setattr(mapit, "debug_file", str(log))
    monkeypatch.setattr(mapit, "crash_debug", False)
    monkeypatch.setattr(sys, "stderr", sys.stderr)  # on_crash re-points it at the log; undo that afterwards

    mapit.on_crash(*_crash(), state=PrimeItems)

    assert "runtime error" in quiet_console["error"][0]
    assert str(log) in quiet_console["error"][1]
    assert "a genuine bug" in log.read_text(encoding="utf-8")
    assert "\a" in quiet_console["say"]


def test_a_crash_while_debugging_shows_the_stack_trace(
    monkeypatch: pytest.MonkeyPatch, quiet_console: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(mapit, "crash_debug", True)
    monkeypatch.setattr(sys, "__excepthook__", lambda *_args: print("TRACE"))

    mapit.on_crash(*_crash(), state=PrimeItems)

    assert "TRACE" in capsys.readouterr().out
    assert "maptasker_debug.log" in quiet_console["error"][0]


def test_an_ai_model_without_chat_turns_analysis_off_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, quiet_console: dict
) -> None:
    class DoesNotSupportChat(Exception):
        error = "this model does not support chat"

    monkeypatch.setattr(mapit, "crash_debug", True)
    monkeypatch.setattr(PrimeItems.program_arguments, "ai_analyze", True)

    mapit.on_crash(DoesNotSupportChat, DoesNotSupportChat(), None, state=PrimeItems)

    assert PrimeItems.program_arguments.ai_analyze is False
    assert quiet_console["error"] == ["this model does not support chat"]


# ##################################################################################
# A background task that fails
# ##################################################################################
def test_a_background_failure_is_logged_with_its_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(mapit.logger, "error", logged.append)
    monkeypatch.setattr(console, "debug", lambda _text: None)

    mapit.handle_async_exceptions(None, {"exception": RuntimeError("lost the socket")})

    assert logged == ["Async Background Task aborted: lost the socket"]


def test_a_background_failure_with_only_a_message_is_logged_with_that(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(mapit.logger, "error", logged.append)
    monkeypatch.setattr(console, "debug", lambda _text: None)

    mapit.handle_async_exceptions(None, {"message": "task was destroyed"})

    assert logged == ["Async Loop Error: task was destroyed"]


def test_the_handler_is_attached_to_the_running_loop() -> None:
    async def attach() -> object:
        mapit._install_async_exception_handler()
        return asyncio.get_running_loop().get_exception_handler()

    assert asyncio.run(attach()) is mapit.handle_async_exceptions


# ##################################################################################
# Starting up
# ##################################################################################
@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """start_up with everything it calls out to replaced by a note that it was called."""
    calls: list[str] = []
    monkeypatch.setattr(mapit, "log_startup_values", lambda state: calls.append("log"))
    monkeypatch.setattr(mapit, "check_versions", lambda: calls.append("versions"))
    monkeypatch.setattr(mapit, "load_arg_specs", lambda: calls.append("specs"))
    monkeypatch.setattr(mapit, "get_program_arguments", lambda state: calls.append("arguments"))
    monkeypatch.setattr(mapit, "setup_colors", lambda state: calls.append("colors") or {"c": "x"})
    monkeypatch.setattr(mapit, "get_data_and_output_intro", lambda force, state: calls.append("data") or 0)
    monkeypatch.setattr(sys, "argv", ["maptasker"])
    return calls


def _fresh_state() -> SimpleNamespace:
    return SimpleNamespace(
        slash="",
        colors_to_use={},
        file_to_get=None,
        program_arguments=SimpleNamespace(gui=False, doing_diagram=False, file=""),
    )


def test_startup_forces_the_window_and_picks_the_colours(started: list[str]) -> None:
    state = _fresh_state()
    mapit.start_up(state)
    assert state.program_arguments.gui is True
    assert state.colors_to_use == {"c": "x"}
    assert started == ["versions", "specs", "arguments", "colors"]  # no file yet, so no data read


def test_startup_keeps_colours_it_already_has(started: list[str]) -> None:
    state = _fresh_state()
    state.colors_to_use = {"kept": "yes"}
    mapit.start_up(state)
    assert state.colors_to_use == {"kept": "yes"}
    assert "colors" not in started


def test_startup_reads_the_backup_when_it_is_already_named(started: list[str]) -> None:
    state = _fresh_state()
    state.program_arguments.file = "backup.xml"
    mapit.start_up(state)
    assert started[-1] == "data"


def test_startup_clears_a_diagram_request_left_over_from_a_previous_run(started: list[str]) -> None:
    state = _fresh_state()
    state.program_arguments.doing_diagram = True
    mapit.start_up(state)
    assert state.program_arguments.doing_diagram is False


@pytest.mark.parametrize(("system", "slash"), [("Windows", "\\"), ("Darwin", "/"), ("Linux", "/")])
def test_startup_works_out_the_path_separator(started: list[str], monkeypatch: pytest.MonkeyPatch, system: str, slash: str) -> None:
    monkeypatch.setattr(mapit.platform, "system", lambda: system)
    state = _fresh_state()
    mapit.start_up(state)
    assert state.slash == slash


@pytest.mark.parametrize("flag", ["-d", "-debug"])
def test_a_debug_flag_logs_the_startup_values(
    started: list[str], monkeypatch: pytest.MonkeyPatch, quiet_console: dict, flag: str
) -> None:
    monkeypatch.setattr(sys, "argv", ["maptasker", flag])
    mapit.start_up(_fresh_state())
    assert started[0] == "log"
    assert "Debug turned on" in quiet_console["say"][0]


# ##################################################################################
# Setting everything up
# ##################################################################################
def test_a_report_request_runs_without_starting_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["maptasker", "-healthcheck"])
    monkeypatch.setattr(mapit.clireports, "wants_report", lambda _args: True)
    monkeypatch.setattr(mapit.clireports, "run", lambda args, state: 7)
    monkeypatch.setattr(mapit, "initialize_everything", lambda **_kw: pytest.fail("the window must not start"))
    assert mapit.mapit_all() == 7


def test_a_crash_hook_is_installed_with_the_state_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapit, "start_up", lambda state: None)
    monkeypatch.setattr(mapit, "PrimeItemsReset", lambda state: None)
    monkeypatch.setattr(mapit.app, "on_startup", lambda _handler: None)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(mapit, "crash_debug", False)
    state = SimpleNamespace(colors_to_use=[], program_arguments=SimpleNamespace(debug=True), output_lines=None)

    assert mapit.initialize_everything(state) == ([], [], [])

    assert mapit.crash_debug is True  # debugging shows the trace rather than the friendly message
    assert sys.excepthook.func is mapit.on_crash
    assert sys.excepthook.keywords == {"state": state}


def test_a_unit_test_run_starts_with_no_colours(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapit, "start_up", lambda state: None)
    monkeypatch.setattr(mapit, "PrimeItemsReset", lambda state: None)
    monkeypatch.setattr(mapit.app, "on_startup", lambda _handler: None)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(sys, "argv", ["maptasker", "-test=yes"])
    state = SimpleNamespace(colors_to_use=["leftover"], program_arguments=SimpleNamespace(debug=False), output_lines=None)

    mapit.initialize_everything(state)

    assert state.colors_to_use == []
