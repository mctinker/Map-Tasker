"""Silent exception handling: what is swallowed, what is narrowed, and what is logged.

Each of these used to hide a real bug behind a handler meant for one expected case:
a blanket `suppress(Exception)` around a one-line lookup, a `try/except KeyError`
wrapped around code that could raise KeyError for other reasons.  The tests pin the
expected case (still quietly handled) and the unexpected one (no longer hidden).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from maptasker.src.mapgen.actionr import get_results_in_arg_order
from maptasker.src.gui.guiutils import _set_single_item_name
from maptasker.src.core.maputil2 import suppress_logged


# ---------------------------------------------------------------- suppress_logged
def test_suppress_logged_swallows_and_records_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="MapTasker"), suppress_logged("Doing the thing"):
        raise RuntimeError("boom")

    record = next(r for r in caplog.records if "Doing the thing" in r.getMessage())
    assert record.levelno == logging.DEBUG
    assert record.exc_info is not None, "the traceback is the point of logging it"


def test_suppress_logged_only_swallows_what_it_is_told_to() -> None:
    with pytest.raises(KeyError), suppress_logged("Doing the thing", ValueError):
        raise KeyError("not expected")


def test_suppress_logged_lets_a_clean_block_through(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="MapTasker"), suppress_logged("Doing the thing"):
        pass
    assert not caplog.records


def test_suppress_logged_does_not_swallow_a_keyboard_interrupt() -> None:
    # The default is Exception, not BaseException: Ctrl-C has to get through.
    with pytest.raises(KeyboardInterrupt), suppress_logged("Doing the thing"):
        raise KeyboardInterrupt


# ---------------------------------------------------------------- get_results_in_arg_order
def test_an_argument_with_no_value_is_skipped() -> None:
    results = {
        "arg0": {"type": "Str"},  # present, never evaluated (see actargs.action_args)
        "arg1": {"value": "kept"},
        "returning_something": True,
    }
    assert get_results_in_arg_order(results) == "kept"


def test_empty_values_are_dropped_from_the_result() -> None:
    results = {"arg0": {"value": "a"}, "arg1": {"value": ""}, "arg2": {"value": "b"}}
    assert get_results_in_arg_order(results) == "a, b"


def test_a_malformed_value_is_no_longer_taken_for_a_missing_one() -> None:
    # A value that is neither text nor None has to be a {"value": ...} of its own; one that is
    # not used to vanish into the missing-argument handler.
    with pytest.raises(KeyError):
        get_results_in_arg_order({"arg0": {"value": {"unexpected": 1}}})


# ---------------------------------------------------------------- the single-item pulldowns
def test_no_pulldown_yet_is_a_quiet_return(caplog: pytest.LogCaptureFixture) -> None:
    window = SimpleNamespace(specific_name_msg="")  # a window whose widgets are not built
    defaults = {"display_only": "Display only ", "project": "None", "profile": "None", "task": "None", "scene": "None"}

    with caplog.at_level(logging.DEBUG, logger="MapTasker"):
        _set_single_item_name(window, "Task", "My Task", defaults)

    assert "My Task" in window.specific_name_msg
    assert any("not built yet" in r.getMessage() for r in caplog.records)


def test_an_error_inside_the_pulldown_is_no_longer_hidden() -> None:
    class Broken:
        @property
        def options(self) -> list[str]:
            msg = "a real bug"
            raise AttributeError(msg)

    window = SimpleNamespace(specific_name_msg="", specific_task_optionmenu=Broken())
    defaults = {"display_only": "Display only ", "project": "None", "profile": "None", "task": "None", "scene": "None"}

    with pytest.raises(AttributeError, match="a real bug"):
        _set_single_item_name(window, "Task", "My Task", defaults)
