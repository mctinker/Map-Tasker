"""Stopping the run without stopping the process.

Library modules used to call sys.exit().  That raises SystemExit, which inherits from
BaseException and therefore travels through every `except Exception` between the failure
and the top of the interpreter -- correct only when MapTasker is the whole program.  It is
not: the same modules run inside a NiceGUI `run.io_bound` worker (where it takes the
server down instead of the one failed build) and inside this test suite (where it ends the
session instead of the test).

They raise MapTaskerError now, and mapit_all -- the top of the process, and the only place
that knows MapTasker really IS the program -- turns it back into an exit status.  These
tests pin both halves of that: the raising, and the translation.
"""

from __future__ import annotations

import logging
import subprocess
import sys

import pytest

from maptasker.src import console
from maptasker.src.mtexcept import MapTaskerError


# ##################################################################################
# The exception itself
# ##################################################################################
def test_it_is_an_ordinary_exception_not_a_baseexception() -> None:
    """The entire point.  SystemExit is a BaseException and cannot be contained; this can.

    A `except Exception` between a failure and the top of the stack has to be able to see
    this, or every caller that guards itself is still being terminated from underneath.
    """
    assert issubclass(MapTaskerError, Exception)
    assert not issubclass(MapTaskerError, SystemExit)


def test_the_exit_code_travels_with_it() -> None:
    """The code is the payload: it is what the process ends on and what the GUI branches on."""
    assert MapTaskerError("no file", exit_code=6).exit_code == 6


def test_a_message_is_never_empty() -> None:
    """str() of it lands in logs and in message boxes, so a bare stop still has to read."""
    assert str(MapTaskerError(exit_code=5))
    assert str(MapTaskerError("Task not found", exit_code=5)) == "Task not found"


def test_it_defaults_to_a_failing_code() -> None:
    """Raised without saying, "cannot carry on" means failure, not success."""
    assert MapTaskerError().exit_code == 1


# ##################################################################################
# exit_program -- the funnel nearly every stop goes through
# ##################################################################################
def test_exit_program_raises_rather_than_exiting() -> None:
    """The one change that fixes the whole class of problem.

    Imported inside the test because maputils pulls in a large part of the package.
    """
    from maptasker.src.maputils import exit_program  # noqa: PLC0415

    with pytest.raises(MapTaskerError) as raised:
        exit_program(5)
    assert raised.value.exit_code == 5


def test_a_clean_shutdown_raises_too() -> None:
    """Code 0 is still a request to stop unwinding -- the GUI's Exit button is exactly that.

    If this returned normally instead, every caller written as "exit_program(0)" followed
    by unreachable code would run that code.
    """
    from maptasker.src.maputils import exit_program  # noqa: PLC0415

    with pytest.raises(MapTaskerError) as raised:
        exit_program(0)
    assert raised.value.exit_code == 0


def test_a_caller_can_contain_it() -> None:
    """What a GUI button handler and diffload.load_for_comparison both rely on."""
    from maptasker.src.maputils import exit_program  # noqa: PLC0415

    def guarded() -> str:
        try:
            exit_program(2)
        except Exception:  # noqa: BLE001
            return "still running"
        return "unreachable"

    assert guarded() == "still running"


# ##################################################################################
# mapit_all -- where it becomes an exit status again
# ##################################################################################
@pytest.mark.parametrize("code", [0, 1, 5, 6])
def test_mapit_all_returns_the_code_it_was_stopped_with(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    """The translation back to a process exit status happens once, at the top, and nowhere else."""
    from maptasker.src import mapit  # noqa: PLC0415

    def stop() -> None:
        raise MapTaskerError("stopped", exit_code=code)

    monkeypatch.setattr(mapit, "initialize_everything", stop)
    with console.muted():
        assert mapit.mapit_all() == code


def test_mapit_all_returns_zero_when_nothing_went_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ordinary path still reports success."""
    from maptasker.src import mapit  # noqa: PLC0415

    monkeypatch.setattr(mapit, "initialize_everything", lambda: ([], [], []))
    assert mapit.mapit_all() == 0


def test_a_real_bug_is_not_turned_into_an_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only MapTaskerError means "stop deliberately".

    Anything else is a defect and must keep going up to the crash handler, not be quietly
    converted into a process exit status that looks like an orderly shutdown.
    """
    from maptasker.src import mapit  # noqa: PLC0415

    def boom() -> None:
        raise ValueError("a genuine bug")

    monkeypatch.setattr(mapit, "initialize_everything", boom)
    with pytest.raises(ValueError, match="a genuine bug"):
        mapit.mapit_all()


# ##################################################################################
# console -- the one place library output reaches a terminal
# ##################################################################################
def test_say_writes_to_stdout_and_logs_it(capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture) -> None:
    """Console output is recorded as well as shown, so a support log has what the user saw."""
    with caplog.at_level(logging.INFO, logger="MapTasker"):
        console.say("hello")
    assert capsys.readouterr().out == "hello\n"
    assert "hello" in caplog.text


def test_error_goes_to_stderr(capsys: pytest.CaptureFixture) -> None:
    """So it survives a redirected stdout -- which is where the map itself can end up."""
    console.error("broken")
    captured = capsys.readouterr()
    assert captured.err == "broken\n"
    assert captured.out == ""


def test_a_message_is_shown_once_not_twice() -> None:
    """Guards the NullHandler on the MapTasker logger.

    Without it, logging's "last resort" handler writes every WARNING and above to stderr
    on top of what console printed, so warnings appeared twice outside debug mode.

    Run in a subprocess, and it has to be: "last resort" only fires when no handler is
    configured anywhere up the chain, and pytest's own logging plugin attaches handlers to
    the root logger -- which suppresses the very thing this is testing.  Asserted with
    capsys in-process, this test passes whether the NullHandler is there or not.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "from maptasker.src import console; console.warn('careful')"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "careful\n"
    assert "careful" not in result.stderr, "the message was written twice -- see the NullHandler in sysconst"


def test_debug_output_is_logged_but_not_shown(capsys: pytest.CaptureFixture, caplog: pytest.LogCaptureFixture) -> None:
    """What most of the package's bare print() calls really were: notes to a developer.

    They stay in the log, where they are useful afterwards, and off the user's terminal.
    """
    from maptasker.src.primitem import PrimeItems  # noqa: PLC0415

    PrimeItems.program_arguments = {"debug": False}
    with caplog.at_level(logging.DEBUG, logger="MapTasker"):
        console.debug("internal detail")
    assert capsys.readouterr().out == ""
    assert "internal detail" in caplog.text


def test_debug_output_is_shown_when_debugging(capsys: pytest.CaptureFixture) -> None:
    """And it does appear for whoever asked for it."""
    from maptasker.src.primitem import PrimeItems  # noqa: PLC0415

    PrimeItems.program_arguments = {"debug": True}
    console.debug("internal detail")
    assert capsys.readouterr().out == "internal detail\n"


def test_muting_silences_the_terminal_but_not_the_log(
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """What an embedder gets: MapTasker's console output stops, its record does not."""
    with caplog.at_level(logging.INFO, logger="MapTasker"), console.muted():
        console.say("quiet please")
    assert capsys.readouterr().out == ""
    assert "quiet please" in caplog.text


def test_muting_restores_the_previous_state_rather_than_unmuting() -> None:
    """Nesting must not hand the terminal back to an embedder that had already muted it."""
    console.mute()
    try:
        with console.muted():
            assert console.is_muted()
        assert console.is_muted(), "the outer mute was cancelled by the inner block"
    finally:
        console.unmute()
    assert not console.is_muted()
