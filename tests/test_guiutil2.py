"""The GUI's plain helpers: language order, the changelog fetch, the font list and the debug tracer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import requests
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiutil2


@pytest.fixture
def reported(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    messages: list[str] = []
    monkeypatch.setattr(guiutil2, "rutroh_error", messages.append)
    return messages


# ##################################################################################
# Languages
# ##################################################################################
def test_english_leads_the_list_and_the_rest_are_in_order() -> None:
    assert guiutil2.sort_languages_with_priority(["Spanish", "Arabic", "English", "French"]) == [
        "English",
        "Arabic",
        "French",
        "Spanish",
    ]


def test_a_list_without_english_is_just_sorted() -> None:
    assert guiutil2.sort_languages_with_priority(["b", "a"]) == ["a", "b"]


# ##################################################################################
# The changelog
# ##################################################################################
class _Reply:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text = text
        self.status = status

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise requests.exceptions.HTTPError(f"{self.status} error")


_CHANGELOG = "# Change Log\n\n## [2.0] new\n- Added: a\n\n- Fixed: b\n## [1.0] old\n- Added: c\n## [0.9] older\n- x\n"


def test_the_changelog_is_read_down_to_the_nth_heading(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutil2.requests, "get", lambda url, timeout: _Reply(_CHANGELOG))
    lines = guiutil2.get_changelog_file("http://example/changelog", "##", 3)
    assert lines == ["# Change Log", "## [2.0] new", "- Added: a", "- Fixed: b", "## [1.0] old", "- Added: c"]
    assert "- x" not in lines  # the third heading, and all after it, are left out


def test_blank_lines_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutil2.requests, "get", lambda url, timeout: _Reply(_CHANGELOG))
    assert "" not in guiutil2.get_changelog_file("http://example/changelog", "##", 2)


def test_the_first_heading_stops_the_reading_at_the_top(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutil2.requests, "get", lambda url, timeout: _Reply(_CHANGELOG))
    assert guiutil2.get_changelog_file("http://example/changelog", "##", 1) == ["# Change Log"]


@pytest.mark.parametrize("n", [0, -1])
def test_a_count_that_makes_no_sense_gives_nothing(reported: list[str], n: int) -> None:
    assert guiutil2.get_changelog_file("http://example/changelog", "##", n) == []
    assert "Invalid integer value" in reported[0]


def test_a_failed_fetch_gives_nothing_and_says_why(monkeypatch: pytest.MonkeyPatch, reported: list[str]) -> None:
    monkeypatch.setattr(guiutil2.requests, "get", lambda url, timeout: _Reply("", status=404))
    assert guiutil2.get_changelog_file("http://example/changelog", "##", 2) == []
    assert "404" in reported[0]


def test_no_network_gives_nothing_and_says_why(monkeypatch: pytest.MonkeyPatch, reported: list[str]) -> None:
    def offline(url: str, timeout: int) -> None:
        raise requests.exceptions.ConnectionError("no route")

    monkeypatch.setattr(guiutil2.requests, "get", offline)
    assert guiutil2.get_changelog_file("http://example/changelog", "##", 2) == []
    assert "no route" in reported[0]


# ##################################################################################
# Fonts
# ##################################################################################
def test_the_font_choices_are_what_the_font_module_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutil2, "get_font_selections", lambda proportional: {"Menlo": "Menlo"})
    assert guiutil2.get_font_choices() == {"Menlo": "Menlo"}


def test_a_font_search_that_fails_never_takes_the_window_down(
    monkeypatch: pytest.MonkeyPatch, reported: list[str]
) -> None:
    def broken(_proportional: bool) -> dict:
        raise RuntimeError("fontconfig exploded")

    monkeypatch.setattr(guiutil2, "get_font_selections", broken)
    assert guiutil2.get_font_choices() == {"Courier New": "Courier New", "Courier": "Courier"}
    assert "fontconfig exploded" in reported[0]


# ##################################################################################
# The tracer
# ##################################################################################
@pytest.fixture
def tracing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "trace_log.txt"
    monkeypatch.setattr(guiutil2, "TRACE_LOG_FILE", str(log))
    monkeypatch.setattr(PrimeItems, "trace", True, raising=False)
    return log


def _frame() -> object:
    """The frame of whoever called this."""
    return sys._getframe(1)


def test_a_tracer_that_has_not_been_switched_on_writes_nothing(tracing: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "trace", False, raising=False)
    assert guiutil2.my_trace_function(_frame(), "line", None) is guiutil2.my_trace_function
    assert not tracing.exists()


def test_a_line_is_logged_with_its_source(tracing: Path) -> None:
    assert guiutil2.my_trace_function(_frame(), "line", None) is guiutil2.my_trace_function
    logged = tracing.read_text(encoding="utf-8")
    assert logged.startswith("LINE: test_guiutil2.py:")
    assert "test_a_line_is_logged_with_its_source" in logged


def test_a_call_and_a_return_are_logged(tracing: Path) -> None:
    guiutil2.my_trace_function(_frame(), "call", None)
    guiutil2.my_trace_function(_frame(), "return", 42)
    logged = tracing.read_text(encoding="utf-8")
    assert "CALL:" in logged
    assert "(Returned: 42)" in logged


def test_an_exception_is_logged_by_type_and_message(tracing: Path) -> None:
    guiutil2.my_trace_function(_frame(), "exception", (ValueError, ValueError("bad"), None))
    assert "ValueError: bad" in tracing.read_text(encoding="utf-8")


def test_code_that_is_not_a_file_is_not_traced(tracing: Path) -> None:
    frame = eval("sys._getframe()", {"sys": sys})
    assert guiutil2.my_trace_function(frame, "line", None) is guiutil2.my_trace_function
    assert not tracing.exists()


def test_a_source_file_that_vanished_is_reported_not_fatal(
    tracing: Path, monkeypatch: pytest.MonkeyPatch, reported: list[str]
) -> None:
    real_open = open

    def refuse(path: object, *args: Any, **kwargs: Any) -> object:
        if str(path).endswith("test_guiutil2.py"):
            raise OSError("gone")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", refuse)
    guiutil2.my_trace_function(_frame(), "line", None)
    assert "Could not read source" in reported[0]
    assert "<ERROR READING CODE" in tracing.read_text(encoding="utf-8")


def test_an_event_that_is_none_of_these_logs_nothing(tracing: Path) -> None:
    assert guiutil2.my_trace_function(_frame(), "opcode", None) is guiutil2.my_trace_function
    assert not tracing.exists()
