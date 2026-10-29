"""guiwins_resources: Missing Resources -- do the files, folders, images, sounds, Scenes and apps still exist?"""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_resources: where resrefs and deviceresource hang off the GUI.                  #
#                                                                                        #
# Along the top, the device to ask (the address every other Android dialog opens with)     #
# and what asking involves, then a button.  Underneath, the report: what is missing and    #
# where each is used (every place a link into the Map), what could not be checked, and     #
# which device said so and when.                                                          #
#                                                                                        #
# THE REPORT IS DRAWN BEFORE ANYTHING IS ASKED.  What the last check found is kept         #
# (resstore), so the dialog opens on it -- the user sees what they were told last time and   #
# when, and can decide whether to ask again.  Checking is slow (the phone runs a helper     #
# Task, and the app list is fetched), so it is always the user's choice.                    #
#                                                                                        #
# THE PHONE IS ASKED ON A WORKER THREAD.  deviceresource blocks until the device answers;   #
# the dialog shows a spinner and says what the user has to do on the phone (accept the      #
# authorization prompt), because a wait nobody was warned about is a wait people give up on.  #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import run, ui

from maptasker.src.analysis import resrefs
from maptasker.src.core.mapjump import LINK_CLICK_JS
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.device import deviceresource
from maptasker.src.gui.guiutils import (
    android_address_defaults,
    remember_android_address,
    remember_android_address_fields,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    from maptasker.src.core.mapjump import Row, Target
    from maptasker.src.gui.userintr import MyGui

    # How a report row's click is made: given the place a row names, the handler that opens it.
    MakeJump = Callable[[Target], Callable[[], Coroutine[Any, Any, None]]]

_BLURB = (
    "Checks that the files, folders, images, sounds, Scenes and apps your Tasks and Profiles use are still on your "
    "Android device.  Where a path is built from a variable, or is a web address, it cannot be checked and is "
    "listed as such."
)
_WHAT_HAPPENS = (
    "MapTasker installs a small helper Task on the device, gives it the list of paths, and reads back which "
    "exist.  It also fetches the device's application list and asks Tasker for its Scenes.  Tasker must be "
    "running with the 'HTTP Server Example' project active -- the same requirement 'Save to Android' has."
)
_WATCH_THE_PHONE = (
    "Watch your Android device: Tasker will ask you to authorize the connection, and the check cannot go on until "
    "you accept."
)

# How many report lines are drawn.  A configuration with a great many missing files can list hundreds of places;
# Save Report writes them all.
_LINE_LIMIT = 500


def build_resources_dialog(gui: MyGui, make_jump: MakeJump) -> ui.dialog | None:
    """Build and return the Missing Resources dialog, or None if there is nothing loaded to check."""
    if not gui.state.tasker_root_elements.get("all_tasks"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None
    return _ResourcesDialog(gui, make_jump).build()


class _ResourcesDialog:
    """The dialog: its widgets, the references on screen, and the handlers that work on them."""

    def __init__(self, gui: MyGui, make_jump: MakeJump) -> None:
        """
        Args:
            gui: The application window, which holds the run's state and the remembered address.
            make_jump: How to follow a report row to the object it names.
        """
        self.gui = gui
        self.state = gui.state
        self.make_jump = make_jump
        self.references = resrefs.References()
        self.problems: list[str] = []
        self.dialog: ui.dialog
        self.ip_field: ui.input
        self.port_field: ui.input
        self.refresh_apps: ui.checkbox
        self.summary: ui.label
        self.progress_row: ui.row
        self.report_area: ui.scroll_area
        self.check_button: ui.button

    def build(self) -> ui.dialog:
        """Draw the dialog, with the last check's report showing."""
        default_ip, default_port = android_address_defaults(self.gui)
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[900px] max-w-full p-6"):
            ui.label(translate_string("Missing Resources")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-sm text-gray-500 italic")
            ui.label(
                f"{translate_string(_WHAT_HAPPENS)}  {translate_string('Helper Task')}: {deviceresource.CHECK_TASK_NAME}",
            ).classes("text-xs text-gray-500 italic mt-1")
            ui.label(translate_string(_WATCH_THE_PHONE)).classes("text-xs text-amber-700 dark:text-amber-500 mt-1")

            with ui.row().classes("w-full items-center gap-2 mt-2"):
                self.ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes(
                    "flex-1 min-w-[200px]",
                )
                self.port_field = ui.input(translate_string("Port"), value=default_port).classes("w-32")
                remember_android_address_fields(self.gui, self.ip_field, self.port_field, self.dialog)
                self.refresh_apps = ui.checkbox(translate_string("Fetch the app list first"), value=True)
                self.refresh_apps.tooltip(
                    translate_string(
                        "Ask the device which apps are installed right now.  Turn this off to use the list fetched "
                        "earlier, which is quicker and as old as that fetch.",
                    ),
                )

            self._build_progress_row()
            self.summary = ui.label("").classes("text-sm font-bold text-orange-500 mt-2")
            self.report_area = ui.scroll_area().classes("w-full h-96 border rounded dark:border-gray-700 mt-1")
            self._build_buttons()

        self.reload_report()
        return self.dialog

    def _build_progress_row(self) -> None:
        """The spinner and message shown while the device is being asked, hidden until it starts."""
        self.progress_row = ui.row().classes("w-full items-center gap-2 mt-2")
        self.progress_row.set_visibility(False)
        with self.progress_row:
            ui.spinner(size="sm")
            ui.label(
                translate_string(
                    "Waiting on the Android device -- accept the authorization prompt there if one appears.  "
                    "This can take a minute.",
                ),
            ).classes("text-sm text-amber-700 dark:text-amber-500")

    def _build_buttons(self) -> None:
        """Check Device, Save Report and Close."""
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            self.check_button = ui.button(translate_string("Check Device"), on_click=self.check_the_device).classes(
                "bg-blue-600 text-white px-4",
            )
            self.check_button.tooltip(
                translate_string(
                    "Ask the device about every file, folder, image, sound, Scene and app your Tasks and Profiles "
                    "use, and list the ones it does not have.  Nothing on the device is changed except the helper "
                    "Task and two small files MapTasker leaves in its Tasker folder.",
                ),
            ).style("white-space: pre-wrap")
            ui.button(translate_string("Save Report"), on_click=self.save_the_report).classes(
                "bg-blue-600 text-white px-4",
            ).tooltip(translate_string("Write this report to a text file in the Output Folder."))
            ui.button(translate_string("Close"), on_click=self.dialog.close).classes("bg-red-500 text-white px-4")

    def report_lines(self) -> list[Row]:
        """The report as it stands: what the last check found, and any problem this one met."""
        return resrefs.report_rows(self.references, errors=self.problems)

    def reload_report(self) -> None:
        """Re-read the configuration and the stored answers, and draw the report."""
        self.references = resrefs.collect(self.state)
        gone = resrefs.missing(self.references)
        asked = len(self.references.questions())
        if resrefs.unchecked(self.references) == asked and asked:
            self.summary.set_text(f"{asked} {translate_string('things are used.  None has been checked yet.')}")
        elif asked:
            self.summary.set_text(f"{len(gone)} {translate_string('missing, of')} {asked} {translate_string('used')}")
        else:
            self.summary.set_text(translate_string("Nothing the Tasks or Profiles use needs checking."))
        self.draw_report()

    def draw_report(self) -> None:
        """Draw the report, every row that points at something a link into the Map."""
        self.report_area.clear()
        rows = self.report_lines()
        with self.report_area, ui.column().classes("w-full gap-0 p-2"):
            for row in rows[:_LINE_LIMIT]:
                if row.target is not None:
                    ui.link(row.text, "#").on("click", self.make_jump(row.target), js_handler=LINK_CLICK_JS).classes(
                        "text-blue-600 dark:text-blue-400 font-mono text-xs whitespace-pre "
                        "decoration-dotted hover:underline",
                    )
                else:
                    ui.label(row.text).classes("font-mono text-xs whitespace-pre " + _row_classes(row.text))
            if len(rows) > _LINE_LIMIT:
                ui.label(
                    f"... {len(rows) - _LINE_LIMIT} more lines.  {translate_string('Save Report writes them all')}.",
                ).classes("font-mono text-xs text-orange-600 dark:text-orange-400")

    async def check_the_device(self) -> None:
        """Ask the device, then redraw from what it said."""
        ip_address = str(self.ip_field.value or "").strip()
        ip_port = str(self.port_field.value or "").strip()
        remember_android_address(self.gui, ip_address, ip_port)

        references = resrefs.collect(self.state)
        if not references.questions():
            ui.notify(translate_string("Nothing the Tasks or Profiles use needs checking."), type="info")
            return

        self.check_button.set_text(translate_string("Checking..."))
        self.check_button.set_enabled(False)
        self.progress_row.set_visibility(True)
        try:
            outcome = await run.io_bound(
                deviceresource.check_device,
                ip_address,
                ip_port,
                references,
                refresh_apps=bool(self.refresh_apps.value),
                state=self.state,
            )
        finally:
            self.check_button.set_text(translate_string("Check Device"))
            self.check_button.set_enabled(True)
            self.progress_row.set_visibility(False)

        # None rather than an outcome: nicegui answers that when the wait is cancelled or the app is stopping
        # (see nicegui.run._run).  There is no page left to report to.
        if outcome is None:
            return
        self.problems = outcome.errors
        self.reload_report()
        if outcome.could_not_save:
            ui.notify(
                f"{translate_string('The answers could not be saved for the Health Check')}: {outcome.could_not_save}",
                type="warning",
            )
        if outcome.answered:
            ui.notify(
                f"{outcome.missing} {translate_string('missing')} -- {translate_string('checked against')} {outcome.device}",
                type="warning" if outcome.missing else "positive",
            )
        else:
            ui.notify(translate_string("The device did not answer.  See the problems listed."), type="negative")

    async def save_the_report(self) -> None:
        """Write the report to a file in the Output Folder."""
        path = await run.io_bound(resrefs.write_report, self.report_lines(), self.state)
        if path:
            ui.notify(f"{translate_string('Report saved as')} {path}", type="positive")
        else:
            ui.notify(translate_string("The report could not be saved."), type="negative")


def _row_classes(text: str) -> str:
    """How one report line is coloured, from what it says."""
    if text.startswith("MISSING"):
        return "font-bold text-red-500"
    if text.startswith("NOT CHECKED"):
        return "font-bold text-orange-600 dark:text-orange-400"
    if text.startswith("  Problem"):
        return "text-red-500"
    return "text-gray-700 dark:text-gray-300"
