"""guiwins_trend: the Trend Dashboard -- is the configuration getting healthier or messier?"""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_trend: where trend hangs off the GUI.                                           #
#                                                                                        #
# Along the top, which family of file to follow (the one open, to start with) and how far    #
# through measuring the kept snapshots it is.  Underneath, in the order they are wanted:     #
#                                                                                        #
#   the verdict    "healthier" or "messier", for the whole history and for the last step.      #
#   the cards      each number with its latest value, how far it has moved, and a sparkline.    #
#   the table      one row per kept snapshot, for reading the actual figures.                   #
#   the movers     the Projects that changed most in each direction, one click from their own    #
#                  numbers.                                                                 #
#                                                                                        #
# Measuring is the slow part -- a second or two per snapshot the first time, and nothing after   #
# (see trend: MEASURED ONCE) -- so it runs on a worker thread and the dialog watches a Progress.   #
# It starts as the dialog opens: a user looking at a dashboard wants it filled in.              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import run, ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import trend

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

_BLURB = (
    "Every configuration you load is kept (see Changes Since...).  This measures each one -- Task length, nesting "
    "depth, how deep Perform Task calls go, and what the Health Check finds -- and shows which way those are going, "
    "for the whole configuration and for each Project.  A number that falls is good; size is shown but never judged."
)

_EVERYTHING = "\x00everything"
_WHOLE = "\x00whole"

# (heading, the Measures field, whether lower is better).  Size is neither good nor bad.
_CARDS = (
    ("Errors", "errors", True),
    ("Warnings", "warnings", True),
    ("Longest Task", "longest_task", True),
    (f"Tasks over {trend.LONG_TASK_ACTIONS} actions", "long_tasks", True),
    ("Deepest nesting", "max_depth", True),
    ("Longest call chain", "call_depth", True),
    ("Actions", "actions", False),
)

_TABLE_COLUMNS = (
    ("Profiles", "profiles"),
    ("Tasks", "tasks"),
    ("Actions", "actions"),
    ("Longest", "longest_task"),
    (f">{trend.LONG_TASK_ACTIONS}", "long_tasks"),
    ("Depth", "max_depth"),
    ("Calls", "call_depth"),
    ("Errors", "errors"),
    ("Warnings", "warnings"),
    ("Info", "infos"),
)

_VERDICT_CLASSES = {
    trend.HEALTHIER: "text-green-700 dark:text-green-400",
    trend.MESSIER: "text-red-600 dark:text-red-400",
    trend.STEADY: "text-gray-600 dark:text-gray-300",
    trend.TOO_FEW: "text-gray-500",
}

_GOOD, _BAD, _NEUTRAL = "#2e7d32", "#c62828", "#757575"
_SPARK_WIDTH, _SPARK_HEIGHT, _SPARK_PAD = 130, 30, 3


def sparkline_svg(values: list[int | None], colour: str = _NEUTRAL) -> str:
    """A small line chart of `values`, as an SVG string.  A None is a gap: the Project was not there then.

    Evenly spaced by position, not by date: the history is a list of loads, and a week of nothing is not worth a
    week of blank.  A flat series is drawn flat in the middle, and the last point is marked so the eye finds
    where "now" is.
    """
    present = [value for value in values if value is not None]
    if not present:
        return f'<svg width="{_SPARK_WIDTH}" height="{_SPARK_HEIGHT}"></svg>'
    low, high = min(present), max(present)
    span = (high - low) or 1
    step = (_SPARK_WIDTH - 2 * _SPARK_PAD) / max(len(values) - 1, 1)

    def point(index: int, value: int) -> tuple[float, float]:
        flat = high == low
        y = (
            _SPARK_HEIGHT / 2
            if flat
            else _SPARK_HEIGHT - _SPARK_PAD - (value - low) / span * (_SPARK_HEIGHT - 2 * _SPARK_PAD)
        )
        return _SPARK_PAD + index * step, y

    runs: list[list[tuple[float, float]]] = [[]]
    for index, value in enumerate(values):
        if value is None:
            runs.append([])
        else:
            runs[-1].append(point(index, value))
    lines = "".join(
        f'<polyline fill="none" stroke="{colour}" stroke-width="1.5" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in line)}"/>'
        for line in runs
        if len(line) > 1
    )
    last = next(
        (point(index, value) for index in range(len(values) - 1, -1, -1) if (value := values[index]) is not None), None
    )
    dot = f'<circle cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="2.5" fill="{colour}"/>' if last else ""
    return f'<svg width="{_SPARK_WIDTH}" height="{_SPARK_HEIGHT}" viewBox="0 0 {_SPARK_WIDTH} {_SPARK_HEIGHT}">{lines}{dot}</svg>'


def _colour(delta: int, *, lower_is_better: bool) -> str:
    """Green for a judged number that fell, red for one that rose, grey for the rest."""
    if not delta or not lower_is_better:
        return _NEUTRAL
    return _GOOD if delta < 0 else _BAD


def build_trend_dialog(state: RunState) -> ui.dialog | None:
    """Build and return the Trend Dashboard dialog, or None if there is no history to look at."""
    if not trend.families():
        ui.notify(
            translate_string(
                "No configuration history has been recorded yet -- every file you load is kept from now on."
            ),
            type="warning",
        )
        return None
    return _Dashboard(state).build()


class _Dashboard:
    """The Trend Dashboard: its widgets, and the handlers that work on them."""

    def __init__(self, state: RunState) -> None:
        """`state` is the run's; it is used to read snapshots back in, never changed."""
        self.state = state
        self.families = trend.families()
        self.series = trend.Series()
        self.progress = trend.Progress()
        self.stop_event = threading.Event()
        self.running = False
        self.dialog: ui.dialog
        self.family: ui.select
        self.scope: ui.select
        self.status: ui.label
        self.bar: ui.linear_progress
        self.verdict_area: ui.column
        self.cards_area: ui.row
        self.table_area: ui.scroll_area
        self.movers_area: ui.column
        self.timer: ui.timer

    def build(self) -> ui.dialog:
        """Draw the dialog and start measuring."""
        with ui.dialog() as self.dialog, ui.card().classes("w-[1150px] max-w-full p-6"):
            ui.label(translate_string("Trend Dashboard")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mt-1 mb-2")
            self._build_controls()
            self.status = ui.label("").classes("text-xs text-orange-500")
            self.verdict_area = ui.column().classes("w-full gap-0 mt-1")
            self.cards_area = ui.row().classes("w-full gap-2 mt-2")
            self.table_area = ui.scroll_area().classes("w-full h-[210px] border rounded dark:border-gray-700 mt-2")
            self.movers_area = ui.column().classes("w-full gap-0 mt-1")
            with ui.row().classes("w-full justify-end mt-3 gap-2"):
                ui.button(translate_string("Copy As Text"), on_click=self.copy).props("outline")
                ui.button(translate_string("Close"), on_click=self.close).classes("bg-red-500 text-white px-4")
            self.timer = ui.timer(0.3, self._tick, active=False)
            ui.timer(0.1, self.measure, once=True)
        return self.dialog

    def _build_controls(self) -> None:
        """Which file to follow, which Project to look at, and the progress of the measuring."""
        options = {family: family for family in self.families}
        options[_EVERYTHING] = translate_string("(everything kept)")
        with ui.row().classes("w-full items-end gap-3 no-wrap"):
            self.family = (
                ui.select(options, value=self._starting_family(), label=translate_string("Follow this file"))
                .props("dense options-dense")
                .classes("min-w-[240px]")
            )
            self.family.on_value_change(self.measure)
            self.scope = (
                ui.select(
                    {_WHOLE: translate_string("The whole configuration")},
                    value=_WHOLE,
                    label=translate_string("Look at"),
                    with_input=True,
                )
                .props("dense options-dense")
                .classes("flex-1")
            )
            self.scope.on_value_change(self.redraw)
            ui.button(translate_string("Measure Again"), on_click=self.measure).props("outline dense").tooltip(
                translate_string("Look for configurations kept since this was last measured."),
            )
            ui.button(translate_string("Stop"), on_click=self.stop).props("outline dense")
        self.bar = ui.linear_progress(value=0, show_value=False).classes("w-full mt-1")

    def _starting_family(self) -> str:
        """The family of the file that is open if the history has it, else the one with the most snapshots."""
        opened = getattr(self.state.file_to_get, "name", self.state.file_to_get)
        if isinstance(opened, str) and opened:
            wanted = trend.family(Path(opened).name)
            if wanted in self.families:
                return wanted
        return self.families[0]

    # ##############################################################################
    # Measuring.
    # ##############################################################################

    def _tick(self) -> None:
        """Show how far the measuring has got."""
        self.status.set_text(self.progress.text)
        if self.progress.total:
            self.bar.set_value(self.progress.done / self.progress.total)

    async def measure(self) -> None:
        """Measure what has not been measured, off the event loop, and draw the result."""
        if self.running:
            return
        self.running = True
        self.stop_event = threading.Event()
        self.progress = trend.Progress(text=translate_string("Measuring..."))
        self.timer.activate()
        wanted = None if self.family.value == _EVERYTHING else str(self.family.value)
        try:
            series = await run.io_bound(trend.build_series, self.state, wanted, self.progress, self.stop_event)
        finally:
            self.running = False
            self.timer.deactivate()
        if series is None:
            return
        self.series = series
        self.bar.set_value(1.0)
        self.status.set_text(
            translate_string("Stopped early.")
            if series.stopped
            else f"{len(series.points)} {translate_string('configurations measured.')}",
        )
        self._fill_scope()
        self.redraw()

    def stop(self) -> None:
        """Stop measuring after the snapshot in hand."""
        self.stop_event.set()

    def close(self) -> None:
        """Close, and stop any measuring under way."""
        self.stop_event.set()
        self.dialog.close()

    def _fill_scope(self) -> None:
        """Offer the whole configuration and every Project that appears in the series."""
        options = {_WHOLE: translate_string("The whole configuration")}
        options.update({name: name for name in self.series.project_names()})
        keep = self.scope.value if self.scope.value in options else _WHOLE
        self.scope.set_options(options, value=keep)

    # ##############################################################################
    # Drawing.
    # ##############################################################################

    def _project(self) -> str | None:
        """The Project being looked at, or None for the whole configuration."""
        return None if self.scope.value in (_WHOLE, None) else str(self.scope.value)

    def _rows(self) -> list[tuple[trend.SnapshotMetrics, trend.Measures | None]]:
        """(snapshot, numbers) for the scope: a Project's, or the whole configuration's."""
        project = self._project()
        if project is None:
            return [(point, point.total) for point in self.series.points]
        return self.series.of_project(project)

    def redraw(self) -> None:
        """Draw the verdict, the cards, the table and the movers for the scope."""
        self._draw_verdict()
        self._draw_cards()
        self._draw_table()
        self._draw_movers()

    def _draw_verdict(self) -> None:
        """'Messier since the first kept: ...' and the same for the last step."""
        self.verdict_area.clear()
        project = self._project()
        rows = [measures for _, measures in self._rows() if measures is not None]
        with self.verdict_area:
            if len(rows) < 2:
                ui.label(
                    translate_string("Not enough history: a trend needs at least two kept configurations.")
                ).classes(
                    "text-sm text-gray-500 italic",
                )
                return
            first = trend.judge(rows[0], rows[-1])
            last = trend.judge(rows[-2], rows[-1])
            self._verdict_line(
                translate_string("Since the first" if project is None else "Since it first appeared"), first
            )
            self._verdict_line(translate_string("Since the one before"), last)

    @staticmethod
    def _verdict_line(heading: str, verdict: trend.Verdict) -> None:
        """One line of the verdict."""
        with ui.row().classes("items-baseline gap-2 no-wrap"):
            ui.label(f"{heading}:").classes("text-xs text-gray-500 w-36 shrink-0")
            ui.label(verdict.summary()).classes(f"text-sm font-bold {_VERDICT_CLASSES.get(verdict.label, '')}")

    def _draw_cards(self) -> None:
        """One card per measure: its latest value, how far it has moved since the first, and a sparkline."""
        self.cards_area.clear()
        rows = self._rows()
        with self.cards_area:
            for heading, key, lower_is_better in _CARDS:
                values = [None if measures is None else getattr(measures, key) for _, measures in rows]
                present = [value for value in values if value is not None]
                if not present:
                    continue
                delta = present[-1] - present[0]
                colour = _colour(delta, lower_is_better=lower_is_better)
                with ui.card().classes("p-2 gap-0 w-[150px]"):
                    ui.label(translate_string(heading)).classes("text-[10px] text-gray-500")
                    with ui.row().classes("items-baseline gap-2 no-wrap"):
                        ui.label(str(present[-1])).classes("text-lg font-bold")
                        if delta:
                            ui.label(f"{delta:+d}").classes("text-xs font-bold").style(f"color:{colour}")
                    ui.html(sparkline_svg(values, colour), sanitize=False)

    def _draw_table(self) -> None:
        """One row per snapshot."""
        self.table_area.clear()
        with self.table_area, ui.column().classes("w-full gap-0 p-1"):
            with ui.row().classes("w-full gap-0 no-wrap font-mono text-[10px] text-gray-500"):
                ui.label(translate_string("Date")).classes("w-36 shrink-0")
                for title, _key in _TABLE_COLUMNS:
                    ui.label(translate_string(title)).classes("w-16 shrink-0 text-right")
            for point, measures in reversed(self._rows()):
                with ui.row().classes("w-full gap-0 no-wrap font-mono text-xs border-b dark:border-gray-800"):
                    ui.label(f"{point.moment:%d-%b-%Y %H:%M}").classes("w-36 shrink-0")
                    if measures is None:
                        ui.label(translate_string("(not in this configuration)")).classes("text-gray-400 italic")
                        continue
                    for _title, key in _TABLE_COLUMNS:
                        ui.label(str(getattr(measures, key))).classes("w-16 shrink-0 text-right")
            for problem in self.series.problems:
                ui.label(f"{translate_string('Not measured')}: {problem}").classes("text-xs text-red-500")

    def _draw_movers(self) -> None:
        """The Projects that changed most in each direction, each a click away from its own numbers."""
        self.movers_area.clear()
        if self._project() is not None:
            return
        worse, better = trend.movers(self.series)
        with self.movers_area:
            for heading, movers, colour in (
                (translate_string("Messier"), worse, _BAD),
                (translate_string("Healthier"), better, _GOOD),
            ):
                for mover in movers:
                    with ui.row().classes("items-baseline gap-2 no-wrap"):
                        ui.label(heading).classes("text-xs font-bold w-20 shrink-0").style(f"color:{colour}")
                        ui.link(mover.name, "#").on(
                            "click", lambda _event, name=mover.name: self.scope.set_value(name)
                        ).classes(
                            "text-sm font-mono text-blue-600 dark:text-blue-400",
                        )
                        ui.label(
                            f"{translate_string('problems')} {mover.problem_delta:+d}, "
                            f"{translate_string('longest Task')} {mover.longest_delta:+d}",
                        ).classes("text-xs text-gray-500")

    def copy(self) -> None:
        """Put the dashboard on the clipboard as text."""
        ui.clipboard.write(trend.as_text(self.series, self._project()))
        ui.notify(translate_string("Copied."), type="positive")
