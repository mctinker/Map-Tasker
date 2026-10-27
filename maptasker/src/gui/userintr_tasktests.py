"""userintr_tasktests: the Task Tests button's half of the event handlers -- and running them after an edit."""

#! /usr/bin/env python3

#                                                                                        #
# userintr_tasktests: open the Task Tests dialog, and run every saved test again whenever the        #
# configuration changes.                                                                  #
#                                                                                        #
# WHEN IS "AN EDIT".  There are some twenty-five places that change the configuration -- the Task,    #
# Profile, Scene and Project editors, Fix Findings, the four refactors, Restore, TaskerNet updates,       #
# Import With Dependencies, Undo and Redo -- and every one of them goes through sessundo, which keeps    #
# the history Undo steps back through.  So the window does not ask each of them to announce itself and      #
# one that forgot is a test that is never run: it watches that history, and when it is not what it was a      #
# moment ago, something was edited.  The same reasoning as the Undo and Redo buttons, which poll it too.       #
#                                                                                        #
# It says something only when a test no longer passes.  A test whose Task is not in the open file is not a       #
# failure -- another backup is not a regression in this one -- and a run in which everything passes is silent.    #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.analysis import taskcases
from maptasker.src.core.maputil2 import suppress_logged
from maptasker.src.edit import sessundo
from maptasker.src.gui.guiwins_nav import go_to_target, opening_view_in_a_new_window
from maptasker.src.gui.guiwins_taskcases import build_taskcases_dialog, notice_after_edit
from maptasker.src.gui.userintr_group import HandlerGroup

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core import mapjump


class TaskTestEventHandlers(HandlerGroup):
    """The Task Tests handlers: reached as hub.tasktests; self.hub is the rest of the window's handlers."""

    # What the edit history looked like at the last look, or None before the first.
    seen: tuple[Any, ...] | None = None
    # Brings the Task Tests dialog up to date, for the one that is up; None until one has been opened.
    refresh_dialog: Callable[[], None] | None = None

    def task_tests_event(self) -> None:
        """Open the Task Tests dialog, which lists every saved test and runs them.

        Rebuilt on every press, for fire_simulator_event's reason: it holds the results of a run against the
        configuration as it was at the press.
        """
        dialog = getattr(self.gui, "tasktests_dialog", None)
        self.gui.tasktests_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Task Tests dialog"):
                dialog.delete()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One link's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        def open_in_stepper(case: taskcases.Case) -> None:
            self.hub.task_stepper_event(case.task, case)

        dialog, self.refresh_dialog = build_taskcases_dialog(make_jump, open_in_stepper, self.state)
        self.gui.tasktests_dialog = dialog
        dialog.open()

    def _refresh_open_dialog(self) -> None:
        """If the Task Tests dialog is open, run its tests again and redraw them: it is showing the Tasks as they were."""
        dialog = getattr(self.gui, "tasktests_dialog", None)
        if dialog is not None and dialog.value and self.refresh_dialog is not None:
            with suppress_logged("Refreshing the Task Tests dialog"):
                self.refresh_dialog()

    def edit_tick(self) -> None:
        """One look at the edit history: if it has moved, run every test again and say if one no longer passes.

        Called by a timer on the window.  Cheap when nothing has changed -- a list of a few tuples compared --
        which is what lets it run all the time.
        """
        history = tuple(sessundo.history(self.state))
        if self.seen is None:
            self.seen = history
            return
        if history == self.seen:
            return
        self.seen = history
        self._refresh_open_dialog()
        book, _ = taskcases.load_book()
        if not book.cases or not book.after_edit:
            return
        notice = notice_after_edit(taskcases.run_all(book, self.state))
        if notice:
            ui.notify(notice, type="warning", position="top", multi_line=True, close_button=True)
