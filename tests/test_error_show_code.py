"""An error's show_code: one whose number means nothing to the user goes without it.

A library that is not installed is fully explained by its message.  The GUI used to add "with
return code 12" to it anyway, and the saved error file carried the 12 on a line of its own.
Every other error keeps its code.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from maptasker.src.core import error
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiutils


@pytest.fixture(autouse=True)
def _gui_run_in_a_scratch_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A GUI run whose error file lands in a temporary directory, with the error fields clean."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", True, raising=False)
    monkeypatch.setattr(PrimeItems.program_arguments, "debug", False, raising=False)
    PrimeItems.error_code = 0
    PrimeItems.error_msg = ""
    PrimeItems.error_show_code = True
    yield
    PrimeItems.error_code = 0
    PrimeItems.error_msg = ""
    PrimeItems.error_show_code = True


class MyGui:
    """Just enough of the window for display_error_file_and_ai_response (it looks at the class name)."""

    def __init__(self) -> None:
        self.boxes: list[tuple[str, str]] = []
        self.state = PrimeItems

    def display_message_box(self, message: str, color: str) -> None:
        self.boxes.append((message, color))


def _raised(message: str, code: int, **kwargs: bool) -> MapTaskerError:
    """The error a library module raises."""
    return MapTaskerError(message, code, **kwargs)


def _the_boxes_after_an_error(**kwargs: bool) -> list[str]:
    """Record an error, then show what the window shows for it on the next run."""
    error.record_error(_raised("Module 'x' not found.", 12, **kwargs))
    window = MyGui()
    guiutils.display_error_file_and_ai_response(window)
    return [message for message, _color in window.boxes]


def test_an_error_keeps_its_code_by_default() -> None:
    boxes = _the_boxes_after_an_error()

    assert "Module 'x' not found. with return code 12." in boxes
    assert PrimeItems.error_code == 12


def test_show_code_false_leaves_the_code_off_the_message() -> None:
    boxes = _the_boxes_after_an_error(show_code=False)

    assert "Module 'x' not found." in boxes
    assert not any("return code" in box for box in boxes)


def test_show_code_false_leaves_the_code_out_of_the_saved_file() -> None:
    error.record_error(_raised("Module 'x' not found.", 12, show_code=False))

    assert Path(error.ERROR_FILE).read_text(encoding="utf-8") == "Module 'x' not found.\n"


def test_the_saved_file_still_carries_the_code_by_default() -> None:
    error.record_error(_raised("Something failed.", 12))

    assert Path(error.ERROR_FILE).read_text(encoding="utf-8") == "Something failed.\n12\n"


def test_the_code_is_still_recorded_for_the_caller() -> None:
    """Hiding the number from the user does not hide it from the program."""
    error.record_error(_raised("Module 'x' not found.", 12, show_code=False))

    assert PrimeItems.error_code == 12
    assert PrimeItems.error_msg == "Module 'x' not found."
    assert PrimeItems.error_show_code is False


def test_the_next_error_shows_its_code_again() -> None:
    _the_boxes_after_an_error(show_code=False)

    assert PrimeItems.error_show_code is True
    assert "Something failed. with return code 5." in _boxes_for("Something failed.", 5)


def _boxes_for(message: str, code: int) -> list[str]:
    error.record_error(_raised(message, code))
    window = MyGui()
    guiutils.display_error_file_and_ai_response(window)
    return [box for box, _color in window.boxes]


# ##################################################################################
# What recording does and does not do
# ##################################################################################
def test_recording_hands_back_the_code_and_raises_nothing() -> None:
    assert error.record_error(_raised("It broke.", 7)) == 7


def test_a_deliberate_stop_is_not_an_error_and_records_nothing() -> None:
    assert error.record_error(_raised("Goodbye.", 0)) == 0

    assert PrimeItems.error_code == 0
    assert not Path(error.ERROR_FILE).exists()


def test_with_no_window_nothing_is_written_for_one_to_find(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", False, raising=False)

    error.record_error(_raised("It broke.", 7))

    assert not Path(error.ERROR_FILE).exists()
    assert PrimeItems.error_code == 0


def test_a_missing_task_is_said_on_the_terminal_even_with_no_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(error.console, "error", said.append)

    error.record_error(_raised('Task "x" not found!!', 5))
    error.record_error(_raised("Something else.", 7))

    assert len(said) == 1 and "not found" in said[0], "code 5 is the one the user asked about and must not be silent"


# ##################################################################################
# report_error: the edge of a load that has a window to go back to
# ##################################################################################
def test_with_a_window_the_edge_records_the_error_and_hands_back_its_code() -> None:
    assert error.report_error(_raised("Not a backup.", 3)) == 3

    assert PrimeItems.error_code == 3 and PrimeItems.error_msg == "Not a backup."


def test_with_no_window_the_edge_lets_the_error_go_on_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems.program_arguments, "gui", False, raising=False)
    failure = _raised("Not a backup.", 3)

    with pytest.raises(MapTaskerError) as raised:
        error.report_error(failure)

    assert raised.value is failure


def test_a_deliberate_stop_is_never_swallowed_by_the_edge() -> None:
    """The window's own Exit is a stop, not a failure to be reported and carried on from."""
    with pytest.raises(MapTaskerError) as raised:
        error.report_error(_raised("Goodbye.", 0))

    assert raised.value.exit_code == 0
