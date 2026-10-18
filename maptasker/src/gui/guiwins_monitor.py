"""guiwins_monitor: the Live Run Monitor -- which Profiles and Tasks fire on the phone, as they do."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_monitor: where livemon and devicemonitor hang off the GUI.                       #
#                                                                                        #
# Along the top, the device to watch and how it is sampled.  Underneath, in the order they   #
# are wanted: what is active and running right now, the log of what changed (newest first,   #
# every line a link into the Map), and the buttons that act on them -- compare what the      #
# device has active with what What Fires When predicted for this moment, and save the log.   #
#                                                                                        #
# AND IN THE DIAGRAM.  Every sample, the objects that are on are lit in every open Diagram     #
# view -- green while they run or are active, amber for a few seconds after they stop -- by   #
# the same data-anchor the click-to-jump uses (see livemon.lights_js).  Nothing is added to    #
# the Diagram's text, so no column moves.  A Diagram that is not the interactive one has no     #
# elements to light, and the monitor says so rather than lighting nothing in silence.          #
#                                                                                        #
# THE DIALOG DOES NOT GET IN THE WAY.  It is seamless -- no backdrop, nothing behind it blocked --  #
# and docked to the LEFT, over the Display Options, because the right-hand panel is where the Diagram #
# button is: docked there it covered the very button needed to open what it was going to light.  An     #
# Open Diagram button is in it too.  Closing it stops the monitoring -- a monitor nobody can see or     #
# stop is the wrong thing to leave running on a phone.                                                 #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, cast

from nicegui import Client, run, ui

from maptasker.src.analysis import diffload, firesim, livemon
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import logger
from maptasker.src.device import devicemonitor
from maptasker.src.gui.guiutils import (
    android_address_defaults,
    remember_android_address,
    remember_android_address_fields,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    from maptasker.src.core.mapjump import Target
    from maptasker.src.gui.userintr import MyGui

    # How a row's click is made: given the place a row names, the handler that opens it.
    MakeJump = Callable[[Target], Callable[[], Coroutine[Any, Any, None]]]

_BLURB = (
    "Watch which Profiles and Tasks fire on your Android device as they do.  MapTasker asks the device every "
    "few seconds -- for a burst of looks taken several times a second -- and lists what became active, what "
    "started and what finished.  With the Diagram open, each of them lights up there while it is on."
)
_LIMITS = (
    "This is sampling, not a feed: a Task that runs for less than the gap between looks can be missed, and "
    "Tasker reports names, so two objects with one name light together."
)

# Roughly how many log lines are kept and drawn; the saved log holds them all.
_LOG_LINES = 300
# How many failed windows in a row end the monitoring.
_FAILURES_ALLOWED = 3
# Seconds to wait before trying again after a window failed.
_RETRY_SECONDS = 2.0

_KIND_CLASSES = {
    livemon.PROFILE_ACTIVE: "text-green-700 dark:text-green-400",
    livemon.PROFILE_INACTIVE: "text-gray-500",
    livemon.TASK_STARTED: "text-blue-600 dark:text-blue-400",
    livemon.TASK_FINISHED: "text-gray-500",
}


def build_monitor_dialog(
    gui: MyGui,
    make_jump: MakeJump,
    open_diagram: Callable[[set[str]], Coroutine[Any, Any, None]],
) -> ui.dialog | None:
    """Build and return the Live Run Monitor dialog, or None if there is nothing loaded to watch."""
    if not gui.state.tasker_root_elements.get("all_tasks"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None
    monitor = _Monitor(gui, make_jump, open_diagram)
    dialog = monitor.build()
    # Kept on the dialog so that whoever takes it down can stop it first (see userintr.live_monitor_event).
    dialog.monitor = monitor  # type: ignore[attr-defined]
    return dialog


class _Monitor:
    """The dialog: its widgets, the tracker of what the device did, and the loop that asks it."""

    def __init__(
        self,
        gui: MyGui,
        make_jump: MakeJump,
        open_diagram: Callable[[set[str]], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Args:
            gui: The application window, which holds the run's state, the open views and the remembered address.
            make_jump: How to follow a log line to the object it names.
            open_diagram: How to open the Diagram view, for the button that does so.  It is told which Projects
                everything seen so far belongs to, so the Diagram can be built to hold it.
        """
        self.gui = gui
        self.state = gui.state
        self.make_jump = make_jump
        self.monitor_diagram_opener = open_diagram
        self.tracker: livemon.Tracker | None = None
        self.running = False
        self.worker: asyncio.Task[None] | None = None
        self.dialog: ui.dialog
        self.ip_field: ui.input
        self.port_field: ui.input
        self.samples_field: ui.number
        self.recent_field: ui.number
        self.light_box: ui.checkbox
        self.follow_box: ui.checkbox
        self.start_button: ui.button
        self.stop_button: ui.button
        self.status: ui.label
        self.diagram_note: ui.label
        self.active_column: ui.column
        self.running_column: ui.column
        self.log_area: ui.scroll_area

    # ##############################################################################
    # Drawing the dialog.
    # ##############################################################################
    def build(self) -> ui.dialog:
        """Draw the dialog, stopped, with nothing in the log."""
        default_ip, default_port = android_address_defaults(self.gui)
        with (
            ui.dialog().props("seamless persistent position=left") as self.dialog,
            ui.card().classes("w-[420px] max-w-full p-4").style("max-height: 96vh; overflow-y: auto"),
        ):
            ui.label(translate_string("Live Run Monitor")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic")
            ui.label(translate_string(_LIMITS)).classes("text-xs text-amber-700 dark:text-amber-500 mt-1")
            with ui.row().classes("w-full items-center gap-2 mt-2 no-wrap"):
                self.ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes("flex-1")
                self.port_field = ui.input(translate_string("Port"), value=default_port).classes("w-24")
                remember_android_address_fields(self.gui, self.ip_field, self.port_field, self.dialog)
            self._build_options()
            self._build_controls()
            self._build_now()
            ui.label(translate_string("What changed")).classes("text-xs font-bold uppercase text-gray-400 mt-2")
            self.log_area = (
                ui.scroll_area()
                .classes("w-full border rounded dark:border-gray-700")
                .style("height: 220px; min-height: 120px; flex-shrink: 0")
            )
            self._build_buttons()
        return self.dialog

    def _build_options(self) -> None:
        """How often the device is asked, how long a stopped object stays marked, and whether the Diagram lights up."""
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            self.samples_field = (
                ui.number(
                    translate_string("Looks per request"),
                    value=devicemonitor.DEFAULT_SAMPLES,
                    min=1,
                    max=devicemonitor.MAX_SAMPLES,
                    format="%d",
                )
                .props("dense")
                .classes("flex-1")
                .tooltip(
                    translate_string(
                        "How many times the device looks at what is running during each request, a fifth of "
                        "a second apart.  More looks catch shorter Tasks and make each request take longer.",
                    ),
                )
            )
            self.recent_field = (
                ui.number(
                    translate_string("Keep lit (seconds)"), value=livemon.RECENT_SECONDS, min=0, max=600, format="%d"
                )
                .props("dense")
                .classes("flex-1")
                .tooltip(translate_string("How long something stays marked in amber in the Diagram after it stops."))
            )
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            self.light_box = ui.checkbox(translate_string("Light up the Diagram"), value=True).classes("text-xs flex-1")
            ui.button(
                translate_string("Open Diagram"), icon="account_tree", on_click=self.show_the_diagram_for_what_fired
            ).props(
                "outline dense",
            ).tooltip(
                translate_string(
                    "Open the Diagram in a window of its own, to watch Profiles and Tasks light up in it.  It is "
                    "built for the one Project everything seen so far belongs to, or for the whole configuration "
                    "when that is more than one Project or nothing has fired yet -- whatever is selected in the "
                    "main window is left as it was.",
                ),
            )
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            self.follow_box = ui.checkbox(translate_string("Scroll the Diagram to what fires"), value=True).classes(
                "text-xs",
            )

    def _build_controls(self) -> None:
        """Start and Stop, and the status line."""
        with ui.row().classes("w-full items-center gap-2 mt-1"):
            self.start_button = ui.button(
                translate_string("Start"), icon="play_arrow", on_click=self.start_monitoring
            ).classes(
                "bg-blue-600 text-white",
            )
            self.stop_button = ui.button(translate_string("Stop"), icon="stop", on_click=self.stop_monitoring).props(
                "outline"
            )
            self.stop_button.disable()
        self.status = ui.label(translate_string("Not monitoring.")).classes("text-sm font-bold")
        self.diagram_note = ui.label("").classes("text-xs text-amber-700 dark:text-amber-500")

    def _build_now(self) -> None:
        """The two lists of what is active and running this moment."""
        with ui.row().classes("w-full gap-4 no-wrap mt-1"):
            with ui.column().classes("flex-1 gap-0"):
                ui.label(translate_string("Active Profiles")).classes("text-xs font-bold uppercase text-gray-400")
                self.active_column = ui.column().classes("w-full gap-0")
            with ui.column().classes("flex-1 gap-0"):
                ui.label(translate_string("Running Tasks")).classes("text-xs font-bold uppercase text-gray-400")
                self.running_column = ui.column().classes("w-full gap-0")

    def _build_buttons(self) -> None:
        """Compare, Save Log and Close."""
        with ui.row().classes("w-full justify-end mt-2 gap-2"):
            ui.button(translate_string("Compare With What Fires When"), on_click=self.compare_with_prediction).props(
                "outline dense",
            ).tooltip(
                translate_string(
                    "Ask What Fires When which Profiles it says are active at the moment of the last look, and show "
                    "where the device disagrees.  Only what the prediction was sure of is judged.",
                ),
            )
            ui.button(translate_string("Save Log"), on_click=self.save_the_log).props("outline dense")
            ui.button(translate_string("Close"), on_click=self.close_monitor).classes("bg-red-500 text-white px-4")

    # ##############################################################################
    # Starting, stopping and the loop.
    # ##############################################################################
    async def start_monitoring(self) -> None:
        """Install the helper Task if need be, then ask the device over and over until told to stop."""
        if self.running:
            return
        ip_address = str(self.ip_field.value or "").strip()
        ip_port = str(self.port_field.value or "").strip()
        remember_android_address(self.gui, ip_address, ip_port)

        self.start_button.disable()
        self.status.set_text(translate_string("Installing the monitor on the device..."))
        installed = await run.io_bound(devicemonitor.install_monitor, ip_address, ip_port, state=self.state)
        if installed is None:
            return
        return_code, message = installed
        if return_code != 0:
            self.start_button.enable()
            self.status.set_text(translate_string("Could not start."))
            ui.notify(message, type="negative", timeout=8000)
            return

        index = livemon.build_index(self.state, ignore=[devicemonitor.MONITOR_TASK_NAME])
        self.tracker = livemon.Tracker(index)
        self.running = True
        self.stop_button.enable()
        self.log_area.clear()
        self.worker = asyncio.create_task(self._watch(ip_address, ip_port))
        self.worker.add_done_callback(_report_failure)

    def abandon(self) -> None:
        """Give up without touching a widget: the page this monitor was drawn on is gone.

        What stop_monitoring does to the buttons and the status line would raise on a deleted client, and
        there is nobody to show them to; all that is needed is that nothing goes on asking the phone.
        """
        self.running = False
        if self.worker is not None:
            self.worker.cancel()
            self.worker = None

    async def stop_monitoring(self) -> None:
        """Stop asking, and put the Diagram's lights out."""
        self.running = False
        if self.worker is not None:
            self.worker.cancel()
            self.worker = None
        self.start_button.enable()
        self.stop_button.disable()
        self.status.set_text(translate_string("Stopped."))
        await self._light({})

    async def show_the_diagram_for_what_fired(self) -> None:
        """Open the Diagram, built to hold what has fired so far."""
        projects: set[str] = self.tracker.seen_projects() if self.tracker is not None else set[str]()
        await self.monitor_diagram_opener(projects)

    async def close_monitor(self) -> None:
        """Stop, and close the dialog."""
        await self.stop_monitoring()
        self.dialog.close()

    async def _watch(self, ip_address: str, ip_port: str) -> None:
        """One window after another, until stopped or the device keeps failing."""
        failures = 0
        while self.running:
            window = await run.io_bound(
                devicemonitor.sample_window,
                ip_address,
                ip_port,
                int(self.samples_field.value or devicemonitor.DEFAULT_SAMPLES),
                state=self.state,
            )
            if window is None:  # The page is going away.
                return
            if not window.ok:
                failures += 1
                self.status.set_text(f"{translate_string('The device did not answer')}: {window.error}")
                if failures >= _FAILURES_ALLOWED:
                    ui.notify(window.error, type="negative", timeout=8000)
                    await self.stop_monitoring()
                    return
                await asyncio.sleep(_RETRY_SECONDS)
                continue
            failures = 0
            await self._take(window)

    async def _take(self, window: devicemonitor.Window) -> None:
        """Fold one window into the tracker and show what it made."""
        tracker = self.tracker
        if tracker is None:
            return
        samples = livemon.parse_window(window.text, tracker.index.tasks, tracker.index.profiles)
        events = tracker.feed(samples)
        self._show_log()
        self._show_now(tracker)
        if samples:
            battery = f", {translate_string('battery')} {tracker.battery}%" if tracker.battery is not None else ""
            self.status.set_text(
                f"{translate_string('Monitoring')} {self.ip_field.value} -- {tracker.samples} "
                f"{translate_string('looks')}, {translate_string('last at')} "
                f"{livemon.local_time(tracker.now_ms).strftime('%H:%M:%S')}{battery}",
            )
        follow = livemon.started_anchors(events) if self.follow_box.value else []
        await self._light(tracker.lit(float(self.recent_field.value or 0)), follow)

    # ##############################################################################
    # Showing it.
    # ##############################################################################
    def _show_log(self) -> None:
        """Redraw the log, newest first.  Every line that names an object is a link into the Map."""
        tracker = self.tracker
        events = tracker.events[-_LOG_LINES:][::-1] if tracker is not None else []
        self.log_area.clear()
        with self.log_area, ui.column().classes("w-full gap-0 p-1"):
            for event in events:
                classes = "font-mono text-xs break-all " + _KIND_CLASSES.get(event.kind, "")
                if event.targets:
                    ui.link(event.line(), "#").on("click", self.make_jump(event.targets[0])).classes(classes)
                else:
                    ui.label(event.line()).classes(classes + " italic")

    def _show_now(self, tracker: livemon.Tracker) -> None:
        """Redraw the two lists of what is on this moment."""
        active, running = tracker.targets_now()
        for column, items in ((self.active_column, active), (self.running_column, running)):
            column.clear()
            with column:
                if not items:
                    ui.label(translate_string("None")).classes("text-xs text-gray-400 italic")
                for name, targets in items:
                    if targets:
                        ui.link(name, "#").on("click", self.make_jump(targets[0])).classes("text-xs break-all")
                    else:
                        ui.label(f"{name} ({translate_string('not in this backup')})").classes(
                            "text-xs break-all italic text-gray-500",
                        )

    async def _light(self, lit: dict[str, str], follow: list[str] | None = None) -> None:
        """Light these objects in the Diagram of every window that has one, and say if there is none to light them in.

        Sent to EVERY connected window, not to the views the app has kept track of: a Diagram opened in another
        tab, or before the page this monitor is on was last loaded, is a window the app's own list may not
        hold -- and it is the window the user is looking at.  A window with no interactive Diagram answers
        that it has no named objects, and nothing happens in it.
        """
        if not self.light_box.value and lit:
            self.diagram_note.set_text("")
            return
        script = livemon.lights_js(lit, follow=follow or [])
        answers = await asyncio.gather(*(_ask(client, script) for client in _clients()))
        nodes = sum(answer[0] for answer in answers)
        lit_somewhere = sum(answer[1] for answer in answers)
        if not nodes:
            self.diagram_note.set_text(
                translate_string("No Diagram is open.  Use Open Diagram, and its Profiles and Tasks will light up.")
                if self.running
                else "",
            )
        elif lit and not lit_somewhere:
            self.diagram_note.set_text(
                translate_string(
                    "The Diagram on screen has none of these to light.  Rebuild it from the loaded file, "
                    "and use the interactive Diagram.",
                ),
            )
        else:
            self.diagram_note.set_text("")

    # ##############################################################################
    # The buttons.
    # ##############################################################################
    def compare_with_prediction(self) -> None:
        """Show where the device's active Profiles differ from What Fires When's prediction for the last look."""
        tracker = self.tracker
        if tracker is None or not tracker.samples:
            ui.notify(translate_string("Start the monitor first."), type="warning")
            return
        moment = livemon.local_time(tracker.now_ms)
        simulation = firesim.simulate(firesim.Scenario(moment, battery=tracker.battery), state=self.state)
        comparison = livemon.compare(simulation, tracker.active, tracker.index, tracker.battery)
        with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-full p-4"):
            ui.label(translate_string("Device against What Fires When")).classes("text-lg font-bold text-blue-600")
            with (
                ui.scroll_area().classes("w-full h-96 border rounded dark:border-gray-700"),
                ui.column().classes("w-full gap-0 p-2"),
            ):
                for row in comparison.rows():
                    if row.target is not None:
                        ui.link(row.text, "#").on("click", self.make_jump(row.target)).classes(
                            "font-mono text-xs whitespace-pre text-blue-600 dark:text-blue-400",
                        )
                    else:
                        ui.label(row.text).classes("font-mono text-xs whitespace-pre")
            ui.button(translate_string("Close"), on_click=dialog.close).classes("bg-red-500 text-white px-4")
        dialog.open()

    async def save_the_log(self) -> None:
        """Write the whole log to a file in the Output Folder."""
        tracker = self.tracker
        if tracker is None or not tracker.events:
            ui.notify(translate_string("There is nothing in the log yet."), type="warning")
            return
        path = await run.io_bound(
            diffload.write_comparison_report, tracker.as_text(), livemon.MONITOR_FILE, state=self.state
        )
        if path:
            ui.notify(f"{translate_string('Log saved as')} {path}", type="positive")
        else:
            ui.notify(translate_string("The log could not be saved."), type="negative")


def _clients() -> list[Client]:
    """Every browser window connected to the app right now.  A seam, so a test can say which windows there are."""
    return [client for client in Client.instances.values() if client.has_socket_connection]


async def _ask(client: Client, script: str) -> tuple[int, int]:
    """(named objects, how many were lit) from one window, or (0, 0) if it did not answer.

    A window that has gone away, or is too busy to answer in time, is one more window with nothing to light.
    """
    with contextlib.suppress(TimeoutError, RuntimeError, AttributeError, KeyError, ValueError):
        reply = cast("object", await client.run_javascript(script, timeout=5))
        if isinstance(reply, dict):
            found = cast("dict[str, object]", reply)
            nodes, lit = found.get("nodes"), found.get("lit")
            return (nodes if isinstance(nodes, int) else 0, lit if isinstance(lit, int) else 0)
    return 0, 0


def _report_failure(task: asyncio.Task[None]) -> None:
    """Log whatever the monitoring loop raised, instead of losing it.  Cancelling it is ordinary."""
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("The Live Run Monitor stopped", exc_info=error)
