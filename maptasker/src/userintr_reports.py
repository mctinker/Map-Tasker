"""Report event handlers: the Health Check, Variable Cross-Reference, Task Flow, Compare and Changes Since reports.

Split out of userintr.py the same way the other userintr_* modules were.  ReportEventHandlers is a
mixin that MapTaskerEventHandlers inherits, so gui.event_handlers keeps every name the report
buttons are wired to.  Each handler gathers what its report needs and hands the work to the module
that builds it: healthck, varxref, taskflow, xmldiff and timeline.

The Task Flow flowchart's own window is not here.  task_flow_event draws it through
_draw_task_flowchart, which stays in userintr beside view_event, because the two open their popout
windows the same way.
"""

from __future__ import annotations

import html
import os
from typing import TYPE_CHECKING

from nicegui import run, ui

from maptasker.src import livevars, mapjump, timeline
from maptasker.src.diffload import (
    current_configuration,
    load_for_comparison,
    loaded_file_path,
    order_by_age,
    original_of,
    write_comparison_report,
)
from maptasker.src.getfile import Local_File_Picker
from maptasker.src.getputer import save_restore_args
from maptasker.src.guistate import remember_setting
from maptasker.src.guiutils import android_address_defaults, remember_android_address, remember_android_address_fields
from maptasker.src.guiwins import build_changes_since_dialog, build_health_check_dialog
from maptasker.src.guiwins_views import NiceGuiTextView
from maptasker.src.healthck import ERROR, WARNING, run_health_check, write_health_check_report
from maptasker.src.maputil2 import translate_string
from maptasker.src.sysconst import TIMELINE_FILE
from maptasker.src.taskflow import run_task_flow_check, write_task_flow_report
from maptasker.src.userintr_loading import local_xml_start_directory
from maptasker.src.varxref import build_report, run_variable_xref, suspects, write_variable_xref_report
from maptasker.src.xmldiff import compare

if TYPE_CHECKING:
    from datetime import date

    from maptasker.src.primitem import RunState
    from maptasker.src.userintr import MapTaskerEventHandlers, MyGui


async def _choose_comparison_file(gui: MyGui) -> str:
    """Which XML file to compare the loaded one against, or "" if the user backed out.

    When the loaded file is a "Save To Current File" copy, the file it was made from is
    still sitting next to it (see diffload.original_of), so the commonest question --
    "what did my own edit change?" -- is offered as a button rather than as a walk through
    the file picker.  Otherwise, and whenever that offer is declined, this is the same
    picker getxml_event opens, started in the same remembered directory.
    """
    original = original_of(loaded_file_path(state=gui.state))

    if original:
        with ui.dialog() as dialog, ui.card().classes("min-w-[420px] p-6"):
            ui.label(translate_string("Compare With")).classes("text-lg font-bold text-blue-600")
            ui.label(
                f"{translate_string('The loaded file was saved from')} {os.path.basename(original)}.",
            ).classes("text-sm mb-2 break-all")
            with ui.column().classes("w-full gap-2"):
                ui.button(
                    f"{translate_string('The original')} ({os.path.basename(original)})",
                    on_click=lambda: dialog.submit(original),
                ).classes("w-full")
                ui.button(
                    translate_string("Choose another file..."),
                    on_click=lambda: dialog.submit("pick"),
                ).props(
                    "outline",
                ).classes("w-full")
                ui.button(
                    translate_string("Cancel"),
                    on_click=lambda: dialog.submit(""),
                ).props(
                    "outline",
                ).classes("w-full")

        choice = await dialog
        if choice != "pick":
            # Covers both the original and Cancel (""), and a dialog dismissed by clicking
            # away, which resolves to None rather than to any of the three buttons.
            return choice or ""

    # The ceiling stays at home no matter where we start, for the same reason getxml_event
    # gives: Local_File_Picker's default upper_limit is whatever directory it opens in,
    # which would leave the user unable to navigate up out of a remembered subdirectory.
    result = await Local_File_Picker(local_xml_start_directory(gui), upper_limit="~", multiple=False)
    if not result:
        return ""
    # Deliberately NOT remember_local_xml_directory: that directory is where the file the
    # user is working ON comes from, and picking something to compare against -- an archive
    # folder, a download -- should not move it.
    return result[0] if isinstance(result, (list, tuple)) else result


class ReportEventHandlers:
    """The report handlers MapTaskerEventHandlers inherits: self.gui is the window, and every other
    handler is reached through self, just as it was before these moved here."""

    # The run state the window shows: MapTaskerEventHandlers, which inherits this class, answers with
    # its window's.
    state: RunState

    def health_check_event(self: MapTaskerEventHandlers) -> None:
        """Ask which categories to report, then scan, display and save.

        The panel comes first rather than after the scan for two reasons: it is the answer
        to "what am I looking for", which the user has in mind before they press the
        button; and unticking a whole family lets the scan skip that walk over the
        configuration altogether (healthck.run_health_check), which is most of the time it
        takes on a large backup.
        """
        gui = self.gui
        if not self.state.tasker_root_elements["all_tasks"]:
            gui.display_message_box(
                translate_string("No XML file has been loaded.  Get an XML file first."),
                "Red",
            )
            return

        build_health_check_dialog(self.run_health_check_for, self.save_health_check_skip, gui, state=self.state)

    def save_health_check_skip(self: MapTaskerEventHandlers, skip: list[str]) -> None:
        """Remember which Health Check categories to leave out, in the settings file.

        The GUI's own copy is updated along with program_arguments: the GUI was handed the
        settings when they were read, and exiting writes its attributes back over
        program_arguments (guistate.capture_gui_state), so a choice stored in only one of the
        two would be put back to what it was at startup.
        """
        remember_setting(self.gui, "health_check_skip", skip)
        save_restore_args(self.state.program_arguments, self.state.colors_to_use, to_save=True, state=self.state)

    def run_health_check_for(self: MapTaskerEventHandlers, skip: list[str]) -> None:
        """Run the check for the categories the panel left ticked, and show the report.

        Nothing is saved here: the panel has already saved every change as it was made,
        through save_health_check_skip, so what is ticked now is what the settings file holds.
        """
        gui = self.gui

        rows, counts = run_health_check(skip, state=self.state)
        file_name = write_health_check_report(rows, state=self.state)

        if file_name:
            gui.display_message_box(f"{translate_string('Health Check saved as')} {file_name}", "Green")
        else:
            gui.display_message_box(translate_string("Health Check report could not be saved."), "Red")

        # The same report, written a second way: the file above holds the plain text, this
        # holds the HTML, and both come from the one list of rows so the two can never
        # disagree.  html_report does the escaping -- NiceGuiTextView's Misc branch drops
        # its content into a <pre> with sanitize=False, so a Tasker name holding '<', '>'
        # or '&' would otherwise be read as markup rather than shown as the name it is
        # (the failure the 12.1.1 fix addressed for variable values).  It also wraps the
        # row naming each finding's location so that clicking it takes the user to that
        # object in the Map view; guiwins_nav.enable_finding_clicks wires the click up.
        self.gui.textview = NiceGuiTextView(
            gui,
            title="Misc View",
            the_data=mapjump.html_report(rows),
        )

        # A clean bill of health is worth saying out loud: an empty-looking report should not
        # leave the user wondering whether the check actually ran.
        if not counts[ERROR] and not counts[WARNING]:
            ui.notify(translate_string("Health Check found no errors or warnings."), type="positive")
        elif any(row.target for row in rows):
            ui.notify(
                translate_string("Click a finding to see it in the Map view."),
                type="info",
                position="bottom",
            )

    def variable_xref_event(self: MapTaskerEventHandlers) -> None:
        """Build the variable where-used index, display it and save it to a file."""
        if not self.state.tasker_root_elements["all_tasks"]:
            self.gui.display_message_box(
                translate_string("No XML file has been loaded.  Get an XML file first."),
                "Red",
            )
            return
        self.show_variable_xref()

    def variable_xref_live_event(self: MapTaskerEventHandlers) -> None:
        """Ask which phone to read, then build the index with what its globals hold right now.

        The address comes first, as it does for every other Android dialog, and is kept like
        theirs.  The read is the only part that touches the phone; if it fails the report is
        not built from a half answer -- the user is told why and the dialog stays up to retry.
        """
        gui = self.gui
        if not self.state.tasker_root_elements["all_tasks"]:
            gui.display_message_box(
                translate_string("No XML file has been loaded.  Get an XML file first."),
                "Red",
            )
            return

        default_ip, default_port = android_address_defaults(gui)
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(translate_string("Variable Xref with Live Values")).classes("text-lg font-bold")
            ui.label(
                translate_string(
                    "Reads the current value of every global variable from Tasker on the Android device and "
                    "sets it beside what this file says.  Nothing on the device is changed.",
                ),
            ).classes("text-sm text-gray-500")
            ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full")
            port_field = ui.input(translate_string("Port"), value=default_port).classes("w-full")
            remember_android_address_fields(gui, ip_field, port_field, dialog)

            progress_row = ui.row().classes("w-full items-center gap-2 mt-3")
            progress_row.set_visibility(False)
            with progress_row:
                ui.spinner(size="sm")
                ui.label(
                    translate_string(
                        "Waiting on the Android device -- accept the authorization prompt there if one appears.",
                    ),
                ).classes("text-sm text-amber-700 dark:text-amber-500")

            async def read_live() -> None:
                ip_address = str(ip_field.value or "").strip()
                ip_port = str(port_field.value or "").strip()
                remember_android_address(gui, ip_address, ip_port)

                read_button.set_enabled(False)
                progress_row.set_visibility(True)
                try:
                    fetched = await run.io_bound(livevars.fetch_live_values, ip_address, ip_port)
                finally:
                    read_button.set_enabled(True)
                    progress_row.set_visibility(False)

                # None when the wait was cancelled or the app is stopping (nicegui.run._run).
                if fetched is None:
                    return
                return_code, message, live = fetched
                if return_code != 0 or live is None:
                    ui.notify(message, type="negative", timeout=8000)
                    return

                dialog.close()
                self.show_variable_xref(live)

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
                read_button = ui.button(translate_string("Read Live Values"), on_click=read_live).classes(
                    "bg-blue-600",
                )
        dialog.open()

    def show_variable_xref(self: MapTaskerEventHandlers, live: livevars.LiveValues | None = None) -> None:
        """Build the index, save the report, and show it -- with the phone's values when live is given."""
        gui = self.gui
        rows, index = run_variable_xref(state=self.state, live=live)
        file_name = write_variable_xref_report(rows, state=self.state)

        if file_name:
            gui.display_message_box(f"{translate_string('Variable Cross-Reference saved as')} {file_name}", "Green")
        else:
            gui.display_message_box(translate_string("Variable Cross-Reference report could not be saved."), "Red")

        # Displayed without the where-used index, which the saved file above keeps in
        # full: on a large configuration the whole report is 18,000 lines and a megabyte,
        # and it is the reference half rather than the part anybody reads on screen.
        #
        # html_report does the escaping (see health_check_event) and marks every place the
        # report names -- the variables themselves, and the action each is first set or
        # read at -- so clicking one takes the user there in the Map view.
        shown = build_report(index, include_index=False, live=live, state=self.state)
        self.gui.textview = NiceGuiTextView(
            gui,
            title="Misc View",
            the_data=mapjump.html_report(shown),
        )

        # A configuration with nothing wrong in it produces a report whose first section
        # says so and then 10,000 lines of index.  Worth saying out loud, so a clean result
        # is not mistaken for the feature having failed to run.
        if not suspects(index, live):
            ui.notify(
                translate_string("Variable Cross-Reference found no suspect variables."),
                type="positive",
            )
        elif any(row.target or row.pieces for row in shown):
            ui.notify(
                translate_string("Click a variable or a place to see it in the Map view."),
                type="info",
                position="bottom",
            )

    def task_flow_event(self: MapTaskerEventHandlers) -> None:
        """Read every Task's control flow, display the report, and draw the chosen Task.

        Two things from one button, because they are two halves of one question.  The
        report answers "is anything wrong with how my Tasks branch and jump" across the
        whole configuration; the flowchart answers "what does THIS Task actually do", and
        is only meaningful once the user has said which Task they mean.  The report is
        therefore unconditional and the chart rides along with the single-Task selection
        the Map and Diagram views already honour.
        """
        gui = self.gui
        if not self.state.tasker_root_elements["all_tasks"]:
            gui.display_message_box(
                translate_string("No XML file has been loaded.  Get an XML file first."),
                "Red",
            )
            return

        rows, counts = run_task_flow_check(state=self.state)
        file_name = write_task_flow_report(rows)

        if file_name:
            gui.display_message_box(f"{translate_string('Task Flow report saved as')} {file_name}", "Green")
        else:
            gui.display_message_box(translate_string("Task Flow report could not be saved."), "Red")

        # The same report written a second way -- the file above holds the plain text, this
        # the HTML -- both from the one list of rows, so the two cannot disagree.  The
        # escaping and the clickable location lines are html_report's; the reasoning is
        # spelled out in health_check_event above.
        self.gui.textview = NiceGuiTextView(
            gui,
            title="Misc View",
            the_data=mapjump.html_report(rows),
        )

        self._draw_task_flowchart(gui)

        if not counts[ERROR] and not counts[WARNING]:
            ui.notify(translate_string("Task Flow found no control-flow problems."), type="positive")
        elif any(row.target for row in rows):
            ui.notify(
                translate_string("Click a finding to see it in the Map view."),
                type="info",
                position="bottom",
            )

    async def compare_files_event(self: MapTaskerEventHandlers) -> None:
        """Compare another XML file against the loaded one, display the report and save it."""
        gui = self.gui
        if not self.state.tasker_root_elements["all_tasks"]:
            gui.display_message_box(
                translate_string("No XML file has been loaded.  Get an XML file first."),
                "Red",
            )
            return

        other_path = await _choose_comparison_file(gui)
        if not other_path:
            ui.notify(translate_string("Comparison cancelled."), type="warning")
            return

        # Never the file already loaded: comparing a configuration with itself is a report
        # saying nothing differs, which is a confusing way to find out you picked the wrong
        # file.  Said plainly instead.  Guarded on there being a loaded path at all --
        # abspath("") is the current directory, which would match a file picked from it.
        # realpath rather than abspath so a symlink, or a path through /tmp on a Mac (where
        # it is a link to /private/tmp), is still recognised as the same file.
        loaded = loaded_file_path(state=self.state)
        if loaded and os.path.realpath(other_path) == os.path.realpath(loaded):
            gui.display_message_box(
                translate_string("That is the file already loaded.  Choose a different one to compare against."),
                "Red",
            )
            return

        other, error_message = load_for_comparison(other_path, state=self.state)
        if other is None:
            gui.display_message_box(error_message, "Red")
            return

        # Ordered by file date so "added" means added in the newer file, whichever way round
        # the user picked them.  The report header names both files either way.
        older, newer = order_by_age(other, current_configuration(state=self.state))
        report, counts = compare(older, newer)

        file_name = write_comparison_report(report, state=self.state)
        if file_name:
            gui.display_message_box(f"{translate_string('Comparison saved as')} {file_name}", "Green")
        else:
            gui.display_message_box(translate_string("Comparison report could not be saved."), "Red")

        # Escaped for display only -- the file above keeps the plain text.  Same reasoning as
        # health_check_event above: NiceGuiTextView's Misc branch drops its content into a
        # <pre> with sanitize=False, so a Tasker name holding '<', '>' or '&' would otherwise
        # be read as markup rather than shown as the name it is.
        self.gui.textview = NiceGuiTextView(
            gui,
            title="Misc View",
            the_data=html.escape(report),
        )

        # Two identical files produce a report that looks empty.  Worth saying out loud, so
        # nobody is left wondering whether the comparison actually ran.
        if not any(counts.values()):
            ui.notify(translate_string("The two files hold the same configuration."), type="positive")

    async def timeline_event(self: MapTaskerEventHandlers) -> None:
        """Ask how far back to look, then report what has changed since then.

        The "nothing loaded" guard is here rather than in the report below, and rather
        than left to timeline's own: asking someone to choose a period and only then
        telling them there is nothing to compare it against wastes the choice.  Same
        check, and the same wording, as compare_files_event.
        """
        if not self.state.tasker_root_elements["all_tasks"]:
            self.gui.display_message_box(
                translate_string("No XML file has been loaded.  Get an XML file first."),
                "Red",
            )
            return

        build_changes_since_dialog(self.report_changes_since)

    async def report_changes_since(
        self: MapTaskerEventHandlers,
        period: str,
        on_date: date | None = None,
    ) -> None:
        """Produce the report for one chosen period -- what build_changes_since_dialog calls.

        The same report compare_files_event produces, with the older side taken from the
        history timeline.py keeps rather than from a file the user has to find -- which is
        the whole point: the question is asked precisely when nobody remembers which file
        on disk was the configuration last Tuesday.

        A period of ALL resolves to no cutoff at all, which is how timeline is told to
        reach back as far as it holds rather than to a date.
        """
        gui = self.gui
        cutoff = timeline.cutoff_for(period, on_date=on_date)
        result = await run.io_bound(timeline.changes_since, cutoff, state=self.state)
        # None, not a report: nicegui answers that when the wait is cancelled or the app is
        # stopping (see nicegui.run._run), and there is no page left to write the report to.
        if result is None:
            return

        if result.problem:
            gui.display_message_box(translate_string(result.problem), "Red")
            return

        # Said before the report is displayed, not after: it changes what the report means.
        if result.note:
            ui.notify(translate_string(result.note), type="warning")

        file_name = write_comparison_report(result.report, TIMELINE_FILE, state=self.state)
        if file_name:
            gui.display_message_box(f"{translate_string('Timeline saved as')} {file_name}", "Green")
        else:
            gui.display_message_box(translate_string("Timeline report could not be saved."), "Red")

        # Escaped for display only -- the file above keeps the plain text.  Same reasoning as
        # compare_files_event above: a Tasker name holding '<', '>' or '&' would otherwise be
        # read as markup rather than shown as the name it is.
        self.gui.textview = NiceGuiTextView(
            gui,
            title="Misc View",
            the_data=html.escape(result.report),
        )

        if result.nothing_changed:
            ui.notify(
                translate_string("Nothing has changed in your configuration over that period."),
                type="positive",
            )
