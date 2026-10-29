"""guiwins_taskstep: the Task Stepper dialog -- taskstep, with the Task and its starting values as controls."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_taskstep: where taskstep hangs off the GUI.                                    #
#                                                                                        #
# Along the top: which Task, and what its variables hold when it starts.  'Suggest        #
# inputs' lists the variables the Task reads before it sets them, so the box does not     #
# start empty and the user does not have to read the Task to find out what to type.        #
# Underneath, once Step is pressed: how the walk ended and what it needed, then one line  #
# per action it met -- indented as the Task is, coloured by what happened, with what       #
# changed -- and the actions it never reached.  Clicking a line shows every variable as    #
# it stood after that step.                                                              #
#                                                                                        #
# Run when Step is pressed, not on every keystroke, unlike What Fires When: a walk can be    #
# hundreds of lines, and the starting values are typed over several lines.                  #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.analysis import taskcases, taskstep
from maptasker.src.core.mapjump import LINK_CLICK_JS
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui.guiwins_taskcases import ask_to_save_test

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

_BLURB = (
    "Pick a Task, say what its variables hold when it starts, and see which If, Else If, For and Goto branches it "
    "takes and what every variable holds after each action.  Actions that talk to the outside world are listed as "
    "'not simulated', and a variable one of them may have set is unknown rather than guessed -- a condition that "
    "depends on it stops the walk, or is treated the way you choose below.  A Perform Task is walked into, so you "
    "see the called Task's own actions, what it was given and what it hands back."
)

_POLICIES = {
    taskstep.POLICY_STOP: "Stop and tell me what it needs",
    taskstep.POLICY_UNSET: "Treat it as not set (as Tasker does)",
    taskstep.POLICY_TRUE: "Assume the condition is true",
    taskstep.POLICY_FALSE: "Assume the condition is false",
}

_STATUS_CLASSES = {
    taskstep.RAN: "text-gray-800 dark:text-gray-200",
    taskstep.TAKEN: "text-green-700 dark:text-green-400",
    taskstep.NOT_TAKEN: "text-amber-600 dark:text-amber-400",
    taskstep.SKIPPED: "text-gray-500",
    taskstep.DISABLED: "text-gray-400 italic",
    taskstep.NOT_SIMULATED: "text-purple-600 dark:text-purple-400",
    taskstep.ASSUMED: "text-purple-600 dark:text-purple-400",
    taskstep.ENDED: "text-blue-600 dark:text-blue-400 font-bold",
    taskstep.UNDECIDED: "text-red-600 dark:text-red-400 font-bold",
}

_OUTCOME_CLASSES = {
    taskstep.FINISHED: "text-green-700 dark:text-green-400",
    taskstep.STOPPED: "text-blue-600 dark:text-blue-400",
    taskstep.RETURNED: "text-blue-600 dark:text-blue-400",
    taskstep.NEEDS_VALUE: "text-red-600 dark:text-red-400",
    taskstep.STEP_LIMIT: "text-amber-600 dark:text-amber-400",
    taskstep.FAILED: "text-red-600 dark:text-red-400",
}

# How many lines of a long walk are drawn, and how many changes a line shows.  Every line is a row of widgets.
_STEP_LIMIT = 600
_CHANGES_SHOWN = 6
_VALUE_WIDTH = 70


def build_taskstep_dialog(
    make_jump: Callable,
    state: RunState,
    task: str = "",
    case: taskcases.Case | None = None,
) -> ui.dialog | None:
    """Build and return the Task Stepper dialog, or None if there are no Tasks loaded.

    `make_jump` turns a Target into a click handler, passed in rather than imported for guiwins_fix's reason.
    `task` is the Task to start with, when the dialog is opened from somewhere that knows which.  `case` is a saved
    test to open it on: its Task, and the values it starts with, filled in and ready to step.
    """
    names = taskstep.named_tasks(state)
    if not names:
        ui.notify(translate_string("No XML file with Tasks has been loaded.  Get an XML file first."), type="warning")
        return None
    wanted = case.task if case is not None else task
    return _Stepper(make_jump, state, names, wanted if wanted in names else names[0], case).build()


class _Stepper:
    """The Task Stepper dialog: its widgets, and the handlers that work on them."""

    def __init__(
        self,
        make_jump: Callable,
        state: RunState,
        names: list[str],
        task: str,
        case: taskcases.Case | None = None,
    ) -> None:
        """
        Args:
            make_jump: How to follow a line to the action it names.
            state: The run's state.
            names: The Tasks that can be picked.
            task: The one picked to start with.
            case: A saved test to fill the controls in from, if the dialog was opened on one.
        """
        self.make_jump = make_jump
        self.state = state
        self.names = names
        self.task = task
        self.case = case
        self.trace: taskstep.Trace | None = None
        # The Task and the starting values the walk on screen was made with -- what Save As Test keeps.
        self.walked: tuple[str, taskcases.Setup] | None = None
        self.save_button: ui.button
        self.touched: list[str] = []
        self.dialog: ui.dialog
        self.picker: ui.select
        self.starting: ui.textarea
        self.assumed: ui.textarea
        self.globals_box: ui.checkbox
        self.follow_box: ui.checkbox
        self.policy: ui.select
        self.limit: ui.number
        self.summary: ui.label
        self.needed_row: ui.column
        self.walk_area: ui.scroll_area
        self.variables_heading: ui.label
        self.variables_area: ui.scroll_area

    def build(self) -> ui.dialog:
        """Draw the dialog."""
        with ui.dialog() as self.dialog, ui.card().classes("w-[1100px] max-w-full p-6"):
            ui.label(translate_string("Task Stepper")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mb-2 mt-1")
            self._build_inputs()
            self.summary = ui.label("").classes("text-sm font-bold mt-2")
            self.needed_row = ui.column().classes("w-full gap-0")
            self.walk_area = ui.scroll_area().classes("w-full h-[300px] border rounded dark:border-gray-700 mt-1")
            self.variables_heading = ui.label("").classes("text-xs font-bold text-blue-600 mt-2")
            self.variables_area = ui.scroll_area().classes("w-full h-[110px] border rounded dark:border-gray-700")
            with ui.row().classes("w-full justify-end mt-3 gap-2"):
                self.save_button = ui.button(
                    translate_string("Save As Test"), icon="fact_check", on_click=self.save_test
                )
                self.save_button.props("outline").disable()
                self.save_button.tooltip(
                    translate_string(
                        "Keep this run as a named test: the Task, the values it started with and what it did.  "
                        "Task Tests runs every saved test again after each edit.",
                    ),
                )
                ui.button(translate_string("Copy As Text"), on_click=self.copy).props("outline")
                ui.button(translate_string("Close"), on_click=self.dialog.close).classes("bg-red-500 text-white px-4")
        if self.case is not None:
            self.fill_from(self.case)
        return self.dialog

    def _build_inputs(self) -> None:
        """The Task, the starting variables, what an unsimulated action leaves, and how to treat what is unknown."""
        with ui.row().classes("w-full items-end gap-3 no-wrap"):
            self.picker = (
                ui.select(self.names, value=self.task, label=translate_string("Task"), with_input=True)
                .props("dense options-dense")
                .classes("flex-1 min-w-[260px]")
            )
            ui.button(translate_string("Suggest Inputs"), on_click=self.suggest).props("outline dense").tooltip(
                translate_string("List the variables this Task reads before it sets them, for you to fill in."),
            )
            self.globals_box = ui.checkbox(translate_string("Use the globals saved in the backup"), value=True).classes(
                "text-xs",
            )
            self.follow_box = ui.checkbox(translate_string("Follow Perform Task"), value=True).classes("text-xs")
            self.follow_box.tooltip(
                translate_string(
                    "Walk into each Task that a Perform Task calls, showing its actions indented under the call.  "
                    "Turn it off to step over the calls: their results are then unknown.",
                ),
            )
        with ui.row().classes("w-full gap-3 no-wrap"):
            self.starting = (
                ui.textarea(
                    translate_string("Starting variables (one per line:  %name = value)"),
                    placeholder="%par1 = hello\n%count = 3",
                )
                .props("dense outlined rows=4")
                .classes("flex-1")
            )
            self.assumed = (
                ui.textarea(
                    translate_string("What an action that is not simulated leaves (one per line:  5: %name = value)"),
                    placeholder="5: %http_response_code = 200",
                )
                .props("dense outlined rows=4")
                .classes("flex-1")
            )
        with ui.row().classes("w-full items-end gap-3 no-wrap"):
            self.policy = (
                ui.select(
                    {key: translate_string(label) for key, label in _POLICIES.items()},
                    value=taskstep.POLICY_STOP,
                    label=translate_string("When a condition depends on a variable with no value"),
                )
                .props("dense options-dense")
                .classes("flex-1")
            )
            self.limit = (
                ui.number(
                    translate_string("Longest walk (actions)"), value=taskstep.DEFAULT_MAX_STEPS, min=1, format="%d"
                )
                .props("dense")
                .classes("w-44")
            )
            ui.button(translate_string("Step"), icon="skip_next", on_click=self.step).classes("px-4")

    # ##############################################################################
    # Inputs.
    # ##############################################################################

    def suggest(self) -> None:
        """Put the variables the Task reads before it sets them into the starting box, for the user to fill in."""
        wanted = taskstep.inputs_needed(self.picker.value, self.state)
        typed, _ = taskstep.parse_assignments(self.starting.value or "")
        lines = [line for line in (self.starting.value or "").splitlines() if line.strip()]
        lines += [
            f"%{name} = "
            for name in wanted
            if name not in typed and not any(line.lstrip("% ").startswith(name) for line in lines)
        ]
        self.starting.set_value("\n".join(lines))
        if not wanted:
            ui.notify(translate_string("This Task reads no variable before it sets it."), type="info")

    def _setup(self) -> taskcases.Setup | None:
        """What the controls say as a Setup, or None -- with a message -- when a line of them cannot be read."""
        starting, bad_start = taskstep.parse_assignments(self.starting.value or "")
        assumed, bad_assumed = taskstep.parse_assumed(self.assumed.value or "")
        if bad_start or bad_assumed:
            shown = "; ".join((bad_start + bad_assumed)[:3])
            ui.notify(f"{translate_string('These lines could not be read')}: {shown}", type="warning")
            return None
        return taskcases.Setup(
            variables=starting,
            assumed=assumed,
            policy=str(self.policy.value),
            follow_calls=bool(self.follow_box.value),
            use_globals=bool(self.globals_box.value),
            max_steps=int(self.limit.value or taskstep.DEFAULT_MAX_STEPS),
        )

    def fill_from(self, case: taskcases.Case) -> None:
        """Put a saved test's values in the controls, ready to step."""
        setup = case.setup
        self.starting.set_value(taskstep.format_assignments(setup.variables))
        self.assumed.set_value(taskstep.format_assumed(setup.assumed))
        self.policy.set_value(setup.policy)
        self.follow_box.set_value(setup.follow_calls)
        self.globals_box.set_value(setup.use_globals)
        self.limit.set_value(setup.max_steps)

    # ##############################################################################
    # Walking, and showing the walk.
    # ##############################################################################

    def step(self) -> None:
        """Walk the chosen Task and draw what it did."""
        setup = self._setup()
        if setup is None:
            return
        task = str(self.picker.value)
        trace = taskstep.step_task(task, self.state, setup.options(self.state))
        if trace is None:
            ui.notify(translate_string("That Task is not in the configuration that is loaded."), type="negative")
            return
        self.trace = trace
        self.walked = (task, setup)
        self.save_button.enable()
        self._draw(trace)

    def save_test(self) -> None:
        """Keep the walk on screen as a test."""
        if self.trace is None or self.walked is None:
            ui.notify(translate_string("Press Step first."), type="warning")
            return
        ask_to_save_test(self.walked[0], self.walked[1], self.trace)

    def _draw(self, trace: taskstep.Trace) -> None:
        """The outcome, what it needed, and the walk."""
        self.summary.set_text(f"{translate_string(trace.outcome.capitalize())}.  {trace.message}")
        self.summary.classes(replace="text-sm font-bold mt-2 " + _OUTCOME_CLASSES.get(trace.outcome, ""))
        self.needed_row.clear()
        with self.needed_row:
            if trace.needed:
                ui.label(
                    f"{translate_string('Needs a value for')}: " + ", ".join(f"%{name}" for name in trace.needed)
                ).classes(
                    "text-xs text-red-600 dark:text-red-400",
                )
            if trace.not_reached:
                ui.label(
                    f"{translate_string('Never reached')}: " + ", ".join(str(n) for n in trace.not_reached[:30])
                ).classes(
                    "text-xs text-gray-500",
                )
            for name, numbers in trace.callee_not_reached.items():
                ui.label(
                    f"{translate_string('Never reached in Task')} '{name}': " + ", ".join(str(n) for n in numbers[:30])
                ).classes("text-xs text-gray-500")
        self.walk_area.clear()
        with self.walk_area, ui.column().classes("w-full gap-0 p-1"):
            inside = ""
            for step in trace.steps[:_STEP_LIMIT]:
                if step.task != inside:
                    inside = step.task
                    self._heading(step, trace)
                self._row(step, step.where or trace.target)
            if len(trace.steps) > _STEP_LIMIT:
                ui.label(
                    f"...{len(trace.steps) - _STEP_LIMIT} {translate_string('more actions -- Copy As Text has them all')}"
                ).classes(
                    "text-xs text-gray-500 italic",
                )
        # What the Task itself changed, first, in the order it first did: the backup's globals can be hundreds.
        self.touched = list(dict.fromkeys(change.name for step in trace.steps for change in step.changes))
        self._show_variables(trace.steps[-1] if trace.steps else None, trace.variables)

    def _heading(self, step: taskstep.Step, trace: taskstep.Trace) -> None:
        """The line that says the walk has gone into a performed Task, or come back out of it."""
        text = (
            f"{translate_string('in Task')} '{step.task}'"
            if step.task
            else f"{translate_string('back in Task')} '{trace.task}'"
        )
        ui.label(text).classes("text-[11px] font-bold uppercase text-blue-600 dark:text-blue-400 mt-1").style(
            f"padding-left:{max(step.depth - 1, 0) * 18 + 36}px",
        )

    def _row(self, step: taskstep.Step, target: Target | None) -> None:
        """One action the walk met: where it is, what happened, and what changed.  Click it for the variables after it."""
        with (
            ui.column()
            .classes(
                "w-full gap-0 border-b dark:border-gray-800 py-1 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800",
            )
            .on("click", lambda _event, step=step: self._show_variables(step, step.variables))
        ):
            with ui.row().classes("items-baseline gap-2 no-wrap").style(f"padding-left:{step.depth * 18}px"):
                if target is not None:
                    ui.link(str(step.number), "#").on(
                        "click", self.make_jump(target.at_action(step.number)), js_handler=LINK_CLICK_JS
                    ).classes(
                        "font-mono text-xs text-blue-600 dark:text-blue-400 w-8 shrink-0 text-right",
                    )
                else:
                    ui.label(str(step.number)).classes("font-mono text-xs text-gray-400 w-8 shrink-0 text-right")
                ui.label(step.status.upper()).classes("font-mono text-[10px] text-gray-500 w-24 shrink-0")
                ui.label(step.text).classes(f"text-sm break-all {_STATUS_CLASSES.get(step.status, '')}")
            padding = f"padding-left:{step.depth * 18 + 140}px"
            if step.detail:
                ui.label(step.detail).classes("text-xs text-gray-500 break-all").style(padding)
            for change in step.changes[:_CHANGES_SHOWN]:
                ui.label(f"%{change.name}:  '{_cut(change.before)}'  ->  '{_cut(change.after)}'").classes(
                    "font-mono text-xs text-teal-700 dark:text-teal-300 break-all",
                ).style(padding)
            if len(step.changes) > _CHANGES_SHOWN:
                ui.label(f"...{len(step.changes) - _CHANGES_SHOWN} {translate_string('more')}").classes(
                    "text-xs text-gray-500 italic",
                ).style(padding)

    def _show_variables(self, step: taskstep.Step | None, variables: dict[str, str]) -> None:
        """Every variable as it stood after a step (or at the end)."""
        where = (
            f"{translate_string('after action')} {step.number}" if step is not None else translate_string("at the end")
        )
        self.variables_heading.set_text(f"{translate_string('Variables')} {where}")
        self.variables_area.clear()
        mine = [name for name in self.touched if name in variables]
        others = [name for name in variables if name not in self.touched]
        with self.variables_area, ui.column().classes("w-full gap-0 p-1"):
            if not variables:
                ui.label(translate_string("None.")).classes("text-xs text-gray-500 italic")
            for name in mine:
                _variable_line(name, variables[name])
            if others:
                with ui.expansion(f"{translate_string('Other variables')} ({len(others)})").classes("w-full text-xs"):
                    for name in others:
                        _variable_line(name, variables[name])

    def copy(self) -> None:
        """Put the walk on the clipboard as text."""
        if self.trace is None:
            ui.notify(translate_string("Press Step first."), type="warning")
            return
        ui.clipboard.write(self.trace.as_text())
        ui.notify(translate_string("Copied."), type="positive")


def _cut(value: str) -> str:
    """One line of a value, cut short -- a variable can hold a whole web page."""
    single = " ".join(value.split())
    return single if len(single) <= _VALUE_WIDTH else f"{single[: _VALUE_WIDTH - 3]}..."


def _variable_line(name: str, value: str) -> None:
    """One variable and what it holds; one the walk cannot know is in the colour of 'not simulated'."""
    ui.label(f"%{name} = '{_cut(value)}'").classes(
        "font-mono text-xs " + ("text-purple-600 dark:text-purple-400" if value == taskstep.UNKNOWN_TEXT else ""),
    )
