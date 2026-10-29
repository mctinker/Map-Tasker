"""guiwins_taskcases: the Task Tests dialog, and the small dialog that saves a Stepper run as a test."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_taskcases: where taskcases hangs off the GUI.                                  #
#                                                                                        #
# SAVING.  The Task Stepper has the run on screen; "Save As Test" asks what to keep of it --   #
# which of the variables the Task changed, whether to hold what it shows and sends, and whether  #
# to hold the route it took -- and a name, and writes it.  Everything is ticked that is safe to     #
# tick; the route is not, for the reason taskcases gives.                                      #
#                                                                                        #
# RUNNING.  The Task Tests dialog lists every saved test and runs them all when it opens, since a     #
# run is a few milliseconds each.  A row says how it came out and, when it failed, each way it       #
# differs from what was saved -- in words, not as a diff of two walks.  Each row can be run again, opened  #
# in the Stepper with its values filled in, deleted, or told that what the Task does now is what is wanted    #
# ("Keep New Result"), which saves the run as it is now in the test's place.                              #
#                                                                                        #
# The same run happens by itself after every edit, from the window's own timer (see userintr_tasktests), and  #
# says so only when something fails.                                                        #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.analysis import taskcases, taskstep
from maptasker.src.core import clock
from maptasker.src.core.mapjump import LINK_CLICK_JS
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import TASK_TESTS_REPORT_FILE, logger
from maptasker.src.gui.guiwins_restore import tip

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterable

    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

    # How a link's click is made: given the place it names, the handler that opens it.
    MakeJump = Callable[[Target], Callable[[], Coroutine[Any, Any, None]]]

_BLURB = (
    "Every test is a Task, the values it starts with, and what it did when you saved it: how it ended, the "
    "variables it set, and what it showed, said and sent.  They are all run again whenever you edit the "
    "configuration, so a Fix Findings pass or a refactor that changes what a Task does is caught at once.  To make "
    "one, step a Task in the Task Stepper and press 'Save As Test'."
)

_STATUS_LABELS = {
    taskcases.PASSED: "PASSED",
    taskcases.FAILED: "FAILED",
    taskcases.MISSING: "NOT HERE",
}

_STATUS_CLASSES = {
    taskcases.PASSED: "text-green-700 dark:text-green-400",
    taskcases.FAILED: "text-red-600 dark:text-red-400",
    taskcases.MISSING: "text-gray-500",
}

# How many differing lines a failed row shows; the saved report has every one.
_DIFFERENCES_SHOWN = 4
# How long a variable's value may be on the save dialog's list.
_VALUE_WIDTH = 50
# How many failing tests a notice after an edit names.
_NAMED_IN_NOTICE = 3


def summary_text(results: list[taskcases.Result]) -> str:
    """'12 passed, 1 failed, 2 not in this file' -- or that there are no tests."""
    if not results:
        return translate_string("There are no tests yet.")
    passed, failed, missing = taskcases.counts(results)
    noun = translate_string("test" if len(results) == 1 else "tests")
    return (
        f"{len(results)} {noun}: {passed} {translate_string('passed')}, "
        f"{failed} {translate_string('failed')}, {missing} {translate_string('not in this file')}"
    )


def notice_after_edit(results: list[taskcases.Result]) -> str:
    """The sentence that tells somebody an edit broke tests, or "" when it did not."""
    broken = taskcases.failing(results)
    if not broken:
        return ""
    names = ", ".join(f"'{result.case.name}'" for result in broken[:_NAMED_IN_NOTICE])
    more = (
        f" {translate_string('and')} {len(broken) - _NAMED_IN_NOTICE} {translate_string('more')}"
        if len(broken) > _NAMED_IN_NOTICE
        else ""
    )
    verb = translate_string(
        "Task tests no longer behaves the way it did when you saved the test"
        if len(broken) == 1
        else "Task tests no longer behave the way they did when you saved them"
    )
    return (
        f"{len(broken)} {translate_string('of')} {len(results)} {verb}: "
        f"{names}{more}.  {translate_string('Open Task Tests to see what changed.')}"
    )


# ##################################################################################
# The Task Tests dialog.
# ##################################################################################
def build_taskcases_dialog(
    make_jump: MakeJump,
    open_in_stepper: Callable[[taskcases.Case], None],
    state: RunState,
) -> tuple[ui.dialog, Callable[[], None]]:
    """Build the Task Tests dialog, and the way to bring what it shows up to date.

    `open_in_stepper` opens a test in the Task Stepper, with its values filled in.  The second thing returned runs
    every test again and redraws, for the window to call when the configuration is edited while the dialog is up.
    """
    tests = _Tests(make_jump, open_in_stepper, state)
    return tests.build(), tests.refresh


class _Tests:
    """The Task Tests dialog: its widgets, and the handlers that work on them."""

    def __init__(self, make_jump: MakeJump, open_in_stepper: Callable[[taskcases.Case], None], state: RunState) -> None:
        """
        Args:
            make_jump: How to follow a Task's name to it in the Map.
            open_in_stepper: How to open a test in the Task Stepper.
            state: The run's state.
        """
        self.make_jump = make_jump
        self.open_in_stepper = open_in_stepper
        self.state = state
        self.book, self.unreadable = taskcases.load_book()
        self.results: dict[str, taskcases.Result] = {}
        # When each test was last run, as the time of day, and which was the latest of them.
        self.ran_at: dict[str, str] = {}
        self.last_run = ""
        self.dialog: ui.dialog
        self.summary: ui.label
        self.ran_label: ui.label
        self.list_area: ui.scroll_area
        self.delete_all_button: ui.button

    def build(self) -> ui.dialog:
        """Draw the dialog and run what it lists."""
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[1000px] max-w-full p-6"):
            ui.label(translate_string("Task Tests")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mb-2 mt-1")
            with ui.row().classes("w-full items-baseline gap-4"):
                self.summary = ui.label("").classes("text-sm font-bold")
                self.ran_label = ui.label("").classes("text-xs text-gray-500")
            if self.unreadable:
                ui.label(
                    f"{self.unreadable} {translate_string('entries in the saved tests could not be read and were left out.')}"
                ).classes("text-xs text-red-600")
            self._build_options()
            self.list_area = ui.scroll_area().classes(
                "w-full h-[40vh] min-h-[160px] border rounded dark:border-gray-700 mt-1"
            )
            self._build_buttons()
        self.run_all()
        return self.dialog

    def refresh(self) -> None:
        """Run every test again and redraw, quietly -- for when the configuration changed under the open dialog."""
        self.book, self.unreadable = taskcases.load_book()
        self.run_all()

    def _build_options(self) -> None:
        """The one setting: whether the tests run again by themselves after every edit."""
        tip(
            ui.checkbox(
                translate_string("Run all the tests after every edit"),
                value=self.book.after_edit,
                on_change=lambda event: self.set_after_edit(bool(event.value)),
            ).props("dense"),
            "When on, every test is run again each time the configuration changes -- an edit, Undo or Redo, Fix "
            "Findings, a refactor, a restore or an import -- and you are told only if one no longer passes.\n\n"
            "A test takes a few milliseconds.",
        )

    def _build_buttons(self) -> None:
        """The row along the bottom."""
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            tip(
                ui.button(translate_string("Run All"), icon="play_arrow", on_click=self.press_run_all).classes("px-4"),
                "Run every saved test again against the configuration as it is now, and show how each one "
                "came out.\n\nEach test walks its Task in the Task Stepper with the values it was saved with and "
                "compares the result with what was saved.  Nothing is run on your phone and nothing in the "
                "configuration changes.",
            )
            tip(
                ui.button(translate_string("Save Report"), on_click=self.save_report).props("outline"),
                "Write the result of every test, and each way a failed one differs, to a text file in the Output Folder.",
            )
            self.delete_all_button = ui.button(
                translate_string("Delete All"), icon="delete_sweep", on_click=self.delete_all
            ).props("outline color=red")
            tip(
                self.delete_all_button,
                "Delete every test listed here, from this window and from the saved file.\n\nYou are asked to "
                "confirm first, because this cannot be undone.  The Tasks themselves are not touched.",
            )
            ui.button(translate_string("Close"), on_click=self.dialog.close).props("color=red").classes(
                "text-white px-4"
            )

    # ----------------------------------------------------------------------------
    # Running.
    # ----------------------------------------------------------------------------
    def run_all(self) -> None:
        """Run every test and draw how each came out."""
        self.results = {result.case.name: result for result in taskcases.run_all(self.book, self.state)}
        self._stamp(self.results)
        self.draw()

    def _run(self, case: taskcases.Case) -> taskcases.Result:
        """Run one test again and keep the result, without drawing -- see press_run on why that is separate."""
        result = taskcases.run_case(case, self.state)
        self.results[case.name] = result
        self._stamp([case.name])
        return result

    def press_run_all(self) -> None:
        """Run All pressed: run them, and SAY so -- a run that comes out as it did before changes nothing on screen."""
        self.run_all()
        passed, failed, missing = taskcases.counts(list(self.results.values()))
        noun = translate_string("test" if len(self.results) == 1 else "tests")
        ui.notify(
            f"{translate_string('Ran')} {len(self.results)} {noun}: {passed} {translate_string('passed')}, "
            f"{failed} {translate_string('failed')}, {missing} {translate_string('not in this file')}.",
            type="warning" if failed else "positive",
            position="top",
        )

    def press_run(self, case: taskcases.Case) -> None:
        """Run pressed on a row: run that test, say how it came out, and then draw.

        In that order, and it matters: drawing clears the list, which deletes the button that was pressed, and a
        notification made from a deleted button's handler has no window left to go to and raises.  So everything
        said to the user is said before the list is redrawn.
        """
        result = self._run(case)
        if result.status == taskcases.PASSED:
            ui.notify(f"'{case.name}' {translate_string('passed')}.", type="positive", position="top")
        elif result.status == taskcases.MISSING:
            ui.notify(f"'{case.name}': {result.differences[0]}", type="info", position="top")
        else:
            ui.notify(
                f"'{case.name}' {translate_string('does not pass')}: {result.differences[0]}",
                type="warning",
                position="top",
            )
        self.draw()

    def _stamp(self, names: Iterable[str]) -> None:
        """Note that these tests were run just now."""
        now = clock.now().strftime("%H:%M:%S")
        self.last_run = now
        self.ran_at.update(dict.fromkeys(names, now))

    def keep_new_result(self, case: taskcases.Case) -> None:
        """Say that what the Task does now is what is wanted: save the run as it is in the test's place."""
        result = self.results.get(case.name)
        if result is None or result.trace is None:
            ui.notify(translate_string("Run the test first."), type="warning")
            return
        pins = taskcases.Pins(
            variables=list(case.expected.variables),
            effects=case.expected.effects is not None,
            path=case.expected.path is not None,
        )
        try:
            kept = taskcases.capture(case.name, case.task, case.setup, result.trace, pins)
        except ValueError as error:
            ui.notify(str(error), type="warning")
            return
        kept.note = case.note
        self.book.put(kept)
        self._save()
        self._run(kept)
        ui.notify(f"{translate_string('Kept the new result of')} '{case.name}'.", type="positive", position="top")
        self.draw()

    def delete(self, case: taskcases.Case) -> None:
        """Drop a test."""
        self.book.remove(case.name)
        self.results.pop(case.name, None)
        self._save()
        self.draw()

    async def delete_all(self) -> None:
        """Delete every test, once the user has said they mean it.

        Asked first because it cannot be taken back -- the tests live in a file, not in the Undo history -- and
        because it is one press from the button beside Run All.
        """
        count = len(self.book.cases)
        if not count:
            return
        noun = translate_string("test" if count == 1 else "tests")
        with ui.dialog().props("persistent") as confirm, ui.card().classes("w-[460px] max-w-full p-6"):
            ui.label(translate_string("Delete All Tests")).classes("text-lg font-bold text-red-600")
            ui.label(f"{translate_string('Delete all')} {count} {noun}?  {translate_string('This cannot be undone.')}")
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button(translate_string("Delete"), on_click=lambda: confirm.submit(True)).props("color=red")
                ui.button(translate_string("Cancel"), on_click=lambda: confirm.submit(False)).props("outline")
        answer = await confirm
        confirm.delete()
        if not answer:
            return
        self.book.cases = []
        self.results.clear()
        self.ran_at.clear()
        self.last_run = ""
        self._save()
        ui.notify(f"{translate_string('Deleted')} {count} {noun}.", type="positive", position="top")
        self.draw()

    def set_after_edit(self, value: bool) -> None:
        """Remember whether to run the tests after every edit."""
        self.book.after_edit = value
        self._save()

    def _save(self) -> None:
        """Write the tests, and say so when they could not be."""
        problem = taskcases.save_book(self.book)
        if problem:
            ui.notify(f"{translate_string('The tests could not be saved:')} {problem}", type="negative")

    def save_report(self) -> None:
        """Write the results to a text file in the Output Folder."""
        text = taskcases.report(list(self.results.values()))
        where = output_path(TASK_TESTS_REPORT_FILE, state=self.state)
        try:
            with open(where, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as error:
            logger.error(f"Task test report could not be written: {error}")
            ui.notify(f"{translate_string('The report could not be saved:')} {error}", type="negative")
            return
        ui.notify(f"{translate_string('Report saved as')} {where}", type="positive")

    # ----------------------------------------------------------------------------
    # Drawing.
    # ----------------------------------------------------------------------------
    def draw(self) -> None:
        """The summary and a row per test."""
        self.summary.set_text(summary_text(list(self.results.values())))
        self.ran_label.set_text(f"{translate_string('Last run')} {self.last_run}" if self.last_run else "")
        self.delete_all_button.set_enabled(bool(self.book.cases))
        self.list_area.clear()
        with self.list_area, ui.column().classes("w-full gap-0 p-1"):
            if not self.book.cases:
                ui.label(translate_string("Step a Task in the Task Stepper and press 'Save As Test'.")).classes(
                    "text-sm text-gray-500 italic p-2"
                )
            for case in self.book.cases:
                self._draw_row(case, self.results.get(case.name))

    def _draw_row(self, case: taskcases.Case, result: taskcases.Result | None) -> None:
        """One test: how it came out, its name and Task, why it failed, and its buttons."""
        status = result.status if result is not None else ""
        with ui.row().classes("w-full items-start gap-2 border-b dark:border-gray-700 py-1 px-2 no-wrap"):
            ui.label(translate_string(_STATUS_LABELS.get(status, "NOT RUN"))).classes(
                f"font-mono text-xs font-bold shrink-0 w-[70px] {_STATUS_CLASSES.get(status, 'text-gray-500')}"
            )
            with ui.column().classes("flex-1 min-w-0 gap-0"):
                ui.label(case.name).classes("text-sm font-bold break-all")
                self._draw_task_line(case, result)
                if case.name in self.ran_at:
                    ui.label(f"{translate_string('Ran at')} {self.ran_at[case.name]}").classes(
                        "text-[11px] text-gray-500"
                    )
                if result is not None and result.status != taskcases.PASSED:
                    for line in result.differences[:_DIFFERENCES_SHOWN]:
                        ui.label(line).classes("text-xs text-gray-700 dark:text-gray-300 font-mono pl-3 break-all")
                    if len(result.differences) > _DIFFERENCES_SHOWN:
                        ui.label(
                            f"...{len(result.differences) - _DIFFERENCES_SHOWN} {translate_string('more -- Save Report has them all')}"
                        ).classes("text-xs text-gray-500 italic pl-3")
            self._draw_buttons(case, result)

    def _draw_task_line(self, case: taskcases.Case, result: taskcases.Result | None) -> None:
        """'Task Name', as a link to it in the Map when the walk found it."""
        target = result.trace.target if result is not None and result.trace is not None else None
        if target is not None:
            ui.link(f"{translate_string('Task')} '{case.task}'", "#").on(
                "click", self.make_jump(target), js_handler=LINK_CLICK_JS
            ).classes("text-xs font-mono text-blue-600 dark:text-blue-400 decoration-dotted hover:underline break-all")
        else:
            ui.label(f"{translate_string('Task')} '{case.task}'").classes("text-xs font-mono text-gray-500 break-all")

    def _draw_buttons(self, case: taskcases.Case, result: taskcases.Result | None) -> None:
        """Run, open in the Stepper, keep the new result, delete."""
        with ui.row().classes("shrink-0 gap-1 no-wrap"):
            tip(
                ui.button(translate_string("Run"), on_click=lambda: self.press_run(case)).props("dense outline"),
                "Run just this test again, against the configuration as it is now.\n\nUse it after putting a "
                "Task right, to see whether this test passes again without running the others.",
            )
            tip(
                ui.button(translate_string("Step"), on_click=lambda: self.open_in_stepper(case)).props("dense outline"),
                "Open this test in the Task Stepper with its values filled in, to see what the Task does now.",
            )
            if result is not None and result.status == taskcases.FAILED:
                tip(
                    ui.button(translate_string("Keep New Result"), on_click=lambda: self.keep_new_result(case)).props(
                        "dense outline color=orange"
                    ),
                    "What the Task does now is what is wanted.  Save this run in the test's place.",
                )
            ui.button(icon="delete", on_click=lambda: self.delete(case)).props("dense flat color=red")


# ##################################################################################
# Saving a Stepper run as a test.
# ##################################################################################
def ask_to_save_test(
    task: str,
    setup: taskcases.Setup,
    trace: taskstep.Trace,
    on_saved: Callable[[taskcases.Case], None] | None = None,
) -> None:
    """Ask what to keep of the run on screen and what to call it, and save it as a test.

    Says why, and asks nothing, when the run cannot be kept -- one that stopped for want of a value.
    """
    problem = taskcases.problem_with(trace)
    if problem:
        ui.notify(translate_string(problem), type="warning")
        return
    _SaveTest(task, setup, trace, on_saved).build().open()


class _SaveTest:
    """The Save As Test dialog: a name, a note, and what to keep."""

    def __init__(
        self,
        task: str,
        setup: taskcases.Setup,
        trace: taskstep.Trace,
        on_saved: Callable[[taskcases.Case], None] | None,
    ) -> None:
        self.task = task
        self.setup = setup
        self.trace = trace
        self.on_saved = on_saved
        self.book, _ = taskcases.load_book()
        self.ticked = dict.fromkeys(taskcases.touched(trace), True)
        self.dialog: ui.dialog
        self.name: ui.input
        self.note: ui.input
        self.effects: ui.checkbox
        self.route: ui.checkbox

    def build(self) -> ui.dialog:
        """Draw the dialog."""
        wanted = self.book.unused_name(f"{self.task} test")
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[640px] max-w-full p-6"):
            ui.label(translate_string("Save As Test")).classes("text-lg font-bold text-blue-600")
            ui.label(f"{translate_string('Task')} '{self.task}'").classes("text-xs font-mono text-gray-500")
            self.name = ui.input(translate_string("Name of the test"), value=wanted).props("dense").classes("w-full")
            self.note = ui.input(translate_string("Note (optional)")).props("dense").classes("w-full")
            ui.label(translate_string("It is expected to end like this, and to leave these variables:")).classes(
                "text-sm font-bold mt-2"
            )
            ui.label(f"{translate_string(self.trace.outcome.capitalize())}.  {self.trace.message}").classes(
                "text-xs text-gray-600 dark:text-gray-300"
            )
            self._build_variables()
            self._build_pins()
            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button(translate_string("Save"), on_click=self.save).classes("px-4")
                ui.button(translate_string("Cancel"), on_click=self.dialog.close).props("outline")
        return self.dialog

    def _build_variables(self) -> None:
        """A tick box per variable the Task changed, with its value."""
        if not self.ticked:
            ui.label(translate_string("The Task changed no variable the walk could work out.")).classes(
                "text-xs text-gray-500 italic"
            )
        with ui.scroll_area().classes("w-full max-h-[160px] border rounded dark:border-gray-700"):
            for name in self.ticked:
                value = " ".join(self.trace.variables[name].split())
                shown = value if len(value) <= _VALUE_WIDTH else f"{value[: _VALUE_WIDTH - 3]}..."
                ui.checkbox(
                    f"%{name} = '{shown}'",
                    value=True,
                    on_change=lambda event, name=name: self.tick(name, bool(event.value)),
                ).props("dense").classes("text-xs font-mono")

    def _build_pins(self) -> None:
        """What else to keep: what it shows and sends, and the route."""
        self.effects = ui.checkbox(translate_string("What it shows, says and sends"), value=True).props("dense")
        tip(
            self.effects,
            "Keep the text of every Flash, notification, web request and other action that talks to the outside "
            "world, with the variables filled in.  A test fails if one of them changes, appears or goes.",
        )
        self.route = ui.checkbox(translate_string("The route it took"), value=False).props("dense")
        tip(
            self.route,
            "Keep which branches were taken, by action number.  Off by default: it also fails when an action is "
            "added above a branch, which is a refactor and not a regression.",
        )

    def tick(self, name: str, value: bool) -> None:
        """A variable was ticked or unticked."""
        self.ticked[name] = value

    def save(self) -> None:
        """Keep the run as a test."""
        name = str(self.name.value or "").strip()
        if not name:
            ui.notify(translate_string("Give the test a name."), type="warning")
            return
        pins = taskcases.Pins(
            variables=[variable for variable, on in self.ticked.items() if on],
            effects=bool(self.effects.value),
            path=bool(self.route.value),
        )
        try:
            case = taskcases.capture(name, self.task, self.setup, self.trace, pins)
        except ValueError as error:
            ui.notify(str(error), type="warning")
            return
        case.note = str(self.note.value or "").strip()
        replaced = self.book.put(case)
        problem = taskcases.save_book(self.book)
        if problem:
            ui.notify(f"{translate_string('The test could not be saved:')} {problem}", type="negative")
            return
        verb = translate_string("replaced") if replaced else translate_string("saved")
        ui.notify(f"{translate_string('Test')} '{name}' {verb}.", type="positive")
        self.dialog.close()
        if self.on_saved is not None:
            self.on_saved(case)
