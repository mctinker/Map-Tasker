"""The Task Tests handlers: opening the dialog, and running every test again after an edit.

What the tests do is test_taskcases', and the dialogs are test_guiwins_taskcases'.  What is tested here is the
window's half: that the edit history is how an edit is noticed -- so that the editors, Fix Findings, a refactor, Undo
and the rest are all covered by one thing, none of them having to announce itself -- that a look at an unchanged
history costs nothing and says nothing, and that the only thing said is that a test no longer passes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from maptasker.src.analysis import taskcases, taskstep
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import userintr_tasktests
from maptasker.src.gui.userintr_tasktests import TaskTestEventHandlers

from tests.shared_fixtures import _load_local
from tests.test_taskstep import _xml, else_, end_if, flash, if_, set_

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("_runtime")

_CHECKER = (if_("%n", 7, "3"), set_("%r", "big"), flash("big %n"), else_(), set_("%r", "small"), end_if())
_OTHER = (flash("hello"),)


def _handlers() -> tuple[TaskTestEventHandlers, SimpleNamespace]:
    """The handlers over a hub that is only what they ask of it."""
    hub = SimpleNamespace(gui=MagicMock(), state=PrimeItems, task_stepper_event=MagicMock())
    hub.gui.tasktests_dialog = None
    return TaskTestEventHandlers(hub), hub  # type: ignore[arg-type]


def _keep_a_test(*, after_edit: bool = True) -> None:
    setup = taskcases.Setup(variables={"n": "5"})
    trace = taskstep.step_task("Checker", PrimeItems, setup.options(PrimeItems))
    assert trace is not None
    book = taskcases.CaseBook(cases=[taskcases.capture("big", "Checker", setup, trace)], after_edit=after_edit)
    assert taskcases.save_book(book) == ""


def _edit(*, break_it: bool) -> None:
    """One edit, as the editors make it: inside an undoable block, so it is a checkpoint in the history.

    Either one that breaks the test -- Checker's condition now wants a number over 9 -- or one that does not: a
    different Task's text.
    """
    with sessundo.undoable("Edit a Task", state=PrimeItems):
        task, find, replace = ("Checker", "3", "9") if break_it else ("Other", "hello", "goodbye")
        for node in PrimeItems.tasker_root_elements["all_tasks_by_name"][task]["xml"].iter():
            if node.text and node.text.strip() == find:
                node.text = replace


@pytest.fixture
def notified(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    notify = MagicMock()
    monkeypatch.setattr(userintr_tasktests.ui, "notify", notify)
    return notify


@pytest.fixture
def checker(tmp_path: Path) -> None:
    _load_local(tmp_path, _xml(Checker=_CHECKER, Other=_OTHER))


# ##################################################################################
# Noticing an edit
# ##################################################################################


def test_the_first_look_only_remembers_the_history(checker: None, notified: MagicMock) -> None:
    _keep_a_test()
    handlers, _ = _handlers()

    handlers.edit_tick()

    notified.assert_not_called()
    assert handlers.seen == ()


def test_a_look_at_a_history_that_has_not_moved_runs_nothing(
    checker: None, notified: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _keep_a_test()
    handlers, _ = _handlers()
    handlers.edit_tick()
    ran = MagicMock()
    monkeypatch.setattr(userintr_tasktests.taskcases, "run_all", ran)

    handlers.edit_tick()
    handlers.edit_tick()

    ran.assert_not_called()


def test_an_edit_that_breaks_a_test_is_said(checker: None, notified: MagicMock) -> None:
    _keep_a_test()
    handlers, _ = _handlers()
    handlers.edit_tick()

    _edit(break_it=True)
    handlers.edit_tick()

    notified.assert_called_once()
    message = notified.call_args.args[0]
    assert message == (
        "1 of 1 Task tests no longer behaves the way it did when you saved the test: 'big'.  "
        "Open Task Tests to see what changed."
    )
    assert notified.call_args.kwargs["type"] == "warning"


def test_an_edit_that_breaks_nothing_says_nothing(checker: None, notified: MagicMock) -> None:
    _keep_a_test()
    handlers, _ = _handlers()
    handlers.edit_tick()

    _edit(break_it=False)  # an edit to another Task: the history moves, and the test still passes
    handlers.edit_tick()

    notified.assert_not_called()
    assert handlers.seen is not None and len(handlers.seen) == 1, "the edit was a checkpoint, so the tests were run"


def test_undo_is_an_edit_too(checker: None, notified: MagicMock) -> None:
    _keep_a_test()
    _edit(break_it=True)
    handlers, _ = _handlers()
    handlers.edit_tick()

    done, _ = sessundo.undo(PrimeItems)
    handlers.edit_tick()

    assert done
    notified.assert_not_called()  # undone: it passes again, so there is nothing to say


def test_redo_into_a_break_is_said(checker: None, notified: MagicMock) -> None:
    _edit(break_it=True)
    sessundo.undo(PrimeItems)  # back to the Task as it was
    _keep_a_test()
    handlers, _ = _handlers()
    handlers.edit_tick()

    done, _ = sessundo.redo(PrimeItems)  # forward to the broken one
    handlers.edit_tick()

    assert done
    notified.assert_called_once()


def test_nothing_is_run_with_no_tests_or_with_the_setting_off(
    checker: None, notified: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = MagicMock()
    monkeypatch.setattr(userintr_tasktests.taskcases, "run_all", ran)
    handlers, _ = _handlers()
    handlers.edit_tick()

    _edit(break_it=True)
    handlers.edit_tick()  # no tests at all
    sessundo.undo(PrimeItems)
    _keep_a_test(after_edit=False)
    _edit(break_it=True)
    handlers.edit_tick()  # tests, but the box is off

    ran.assert_not_called()
    notified.assert_not_called()


def test_a_test_for_a_task_not_in_the_file_is_never_said(checker: None, notified: MagicMock) -> None:
    book = taskcases.CaseBook(cases=[taskcases.Case(name="elsewhere", task="Nowhere")])
    assert taskcases.save_book(book) == ""
    handlers, _ = _handlers()
    handlers.edit_tick()

    _edit(break_it=True)
    handlers.edit_tick()

    notified.assert_not_called()


# ##################################################################################
# The button
# ##################################################################################


def test_the_button_builds_the_dialog_and_opens_it(checker: None, monkeypatch: pytest.MonkeyPatch) -> None:
    dialog = MagicMock()
    build = MagicMock(return_value=(dialog, MagicMock()))
    monkeypatch.setattr(userintr_tasktests, "build_taskcases_dialog", build)
    handlers, hub = _handlers()

    handlers.task_tests_event()

    dialog.open.assert_called_once()
    assert hub.gui.tasktests_dialog is dialog


def test_a_dialog_still_up_is_taken_down_first(checker: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        userintr_tasktests, "build_taskcases_dialog", MagicMock(return_value=(MagicMock(), MagicMock()))
    )
    handlers, hub = _handlers()
    old = MagicMock()
    hub.gui.tasktests_dialog = old

    handlers.task_tests_event()

    old.delete.assert_called_once()


def test_stepping_a_test_opens_the_stepper_on_it(checker: None, monkeypatch: pytest.MonkeyPatch) -> None:
    build = MagicMock(return_value=(MagicMock(), MagicMock()))
    monkeypatch.setattr(userintr_tasktests, "build_taskcases_dialog", build)
    handlers, hub = _handlers()
    handlers.task_tests_event()
    case = taskcases.Case(name="big", task="Checker")

    build.call_args.args[1](case)

    hub.task_stepper_event.assert_called_once_with("Checker", case)


# ##################################################################################
# A dialog that is open while the configuration is edited
# ##################################################################################


def _open_dialog(monkeypatch: pytest.MonkeyPatch, *, is_open: bool) -> tuple[TaskTestEventHandlers, MagicMock]:
    """Handlers whose Task Tests dialog is up (or closed), and the function that refreshes it."""
    refresh = MagicMock()
    dialog = MagicMock()
    dialog.value = is_open
    monkeypatch.setattr(userintr_tasktests, "build_taskcases_dialog", MagicMock(return_value=(dialog, refresh)))
    handlers, _ = _handlers()
    handlers.task_tests_event()
    return handlers, refresh


def test_an_edit_while_the_dialog_is_open_brings_it_up_to_date(
    checker: None, notified: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers, refresh = _open_dialog(monkeypatch, is_open=True)
    handlers.edit_tick()

    _edit(break_it=False)
    handlers.edit_tick()

    refresh.assert_called_once()


def test_an_edit_while_the_dialog_is_closed_does_not_touch_it(
    checker: None, notified: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers, refresh = _open_dialog(monkeypatch, is_open=False)
    handlers.edit_tick()

    _edit(break_it=False)
    handlers.edit_tick()

    refresh.assert_not_called()


def test_the_open_dialog_is_refreshed_even_with_the_run_after_every_edit_box_off(
    checker: None, notified: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The box is about being told; a dialog on screen should never be showing a Task as it no longer is."""
    _keep_a_test(after_edit=False)
    handlers, refresh = _open_dialog(monkeypatch, is_open=True)
    handlers.edit_tick()

    _edit(break_it=True)
    handlers.edit_tick()

    refresh.assert_called_once()
    notified.assert_not_called()
