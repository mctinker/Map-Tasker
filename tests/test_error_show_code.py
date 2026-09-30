"""error_handler's show_code: an error whose number means nothing to the user goes without it.

A library that is not installed is fully explained by its message.  The GUI used to add "with
return code 12" to it anyway, and the saved error file carried the 12 on a line of its own.
Every other error keeps its code.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src import error, guiutils
from maptasker.src.primitem import PrimeItems


@pytest.fixture(autouse=True)
def _gui_run_in_a_scratch_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def display_message_box(self, message: str, color: str) -> None:
        self.boxes.append((message, color))


def _the_boxes_after_an_error(**kwargs: bool) -> list[str]:
    """Raise an error, then show what the window shows for it on the next run."""
    error.error_handler("Module 'x' not found.", 12, **kwargs)
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
    error.error_handler("Module 'x' not found.", 12, show_code=False)

    assert Path(error.ERROR_FILE).read_text(encoding="utf-8") == "Module 'x' not found.\n"


def test_the_saved_file_still_carries_the_code_by_default() -> None:
    error.error_handler("Something failed.", 12)

    assert Path(error.ERROR_FILE).read_text(encoding="utf-8") == "Something failed.\n12\n"


def test_the_code_is_still_recorded_for_the_caller() -> None:
    """Hiding the number from the user does not hide it from the program."""
    error.error_handler("Module 'x' not found.", 12, show_code=False)

    assert PrimeItems.error_code == 12
    assert PrimeItems.error_show_code is False


def test_the_next_error_shows_its_code_again() -> None:
    _the_boxes_after_an_error(show_code=False)

    assert PrimeItems.error_show_code is True
    assert "Something failed. with return code 5." in _boxes_for("Something failed.", 5)


def _boxes_for(message: str, code: int) -> list[str]:
    error.error_handler(message, code)
    window = MyGui()
    guiutils.display_error_file_and_ai_response(window)
    return [box for box, _color in window.boxes]
