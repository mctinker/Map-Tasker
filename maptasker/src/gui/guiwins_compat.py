"""guiwins_compat: the Compatibility Check window -- what in the file breaks on which Tasker version, and the table behind it."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_compat: where mapops.compat hangs off the GUI.                                   #
#                                                                                        #
# Two tabs over one table.  FINDINGS answers the question the window is opened with: for the #
# Tasker version (and, if you say, the Android) picked at the top, what in the loaded file     #
# does not survive -- each line a click into the Map.  TABLE is the curated table itself,       #
# every action, event, state and behaviour change from Tasker 5.0 on, release by release, with  #
# how many places the loaded file uses each; it is worth reading with no file open at all,        #
# which is why this window opens without one.                                                #
#                                                                                        #
# Picking a different version redraws the findings at once; nothing is slow enough to need a     #
# button.  All the knowledge is in compat; this is the drawing and the buttons.                   #
#                                                                                        #
# Nothing here changes the configuration, so none of it is on the Undo list.                      #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core.mapjump import LINK_CLICK_JS, Row, Target
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import compat

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core.primitem import RunState

# The Android versions the window offers, as API levels: the ones the table has something to say about.
_ANDROID_CHOICES = (26, 27, 28, 29, 30, 31, 33, 34, 35, 36)

# How a finding's tag is coloured.
_TAG_CLASSES = {
    compat.NEWER_TASKER: "font-bold text-red-600 dark:text-red-400",
    compat.NEWER_ANDROID: "font-bold text-red-600 dark:text-red-400",
    compat.REMOVED: "font-bold text-orange-600 dark:text-orange-400",
    compat.CHANGED: "font-bold text-orange-600 dark:text-orange-400",
    compat.GENERAL: "font-bold text-gray-600 dark:text-gray-300",
}


def build_compatibility_window(
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
    state: RunState,
) -> ui.dialog:
    """Build the Compatibility Check window.

    `make_jump` turns a place into the click that takes the user to it in the Map, and is passed in rather than
    imported, for the reason build_refactor_dialog gives.  It opens with nothing loaded: the table is worth reading
    without a file, and the Findings tab says what is missing.
    """
    return CompatibilityWindow(make_jump, state).build()


class CompatibilityWindow:
    """The window: the version asked about, the findings drawn for it, and the handlers."""

    def __init__(
        self,
        make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
        state: RunState,
    ) -> None:
        """Remember where to send a click, and start from the newest release and any Android."""
        self.make_jump = make_jump
        self.state = state
        self.releases = list(reversed(compat.releases()))
        self.versions = [release.version for release in self.releases]
        self.target = self.versions[0]
        self.android = 0
        self.result = compat.check(state, self.target, self.android)
        self.dialog: ui.dialog
        self.findings: ui.column

    # ---------------------------------------------------------------- drawing
    def build(self) -> ui.dialog:
        """Draw the window and fill both tabs."""
        with (
            ui.dialog().props("persistent maximized") as self.dialog,
            ui.card().classes("w-full h-full p-4 no-wrap gap-2"),
        ):
            ui.label(translate_string("Compatibility Check")).classes("text-lg font-bold text-blue-600")
            ui.label(self._written_by()).classes("text-sm text-gray-600 dark:text-gray-300")
            with ui.row().classes("w-full items-center gap-4"):
                ui.select(
                    {
                        release.version: f"{release.version} ({translate_string('beta')})"
                        if release.beta
                        else release.version
                        for release in self.releases
                    },
                    value=self.target,
                    label=translate_string("Tasker version"),
                    on_change=lambda event: self.pick(target=str(event.value)),
                ).classes("w-48").props("dense")
                ui.select(
                    {0: translate_string("Any"), **{api: compat.android_name(api) for api in _ANDROID_CHOICES}},
                    value=0,
                    label=translate_string("Android version"),
                    on_change=lambda event: self.pick(android=int(event.value or 0)),
                ).classes("w-48").props("dense")
            with ui.tabs().classes("w-full") as tabs:
                findings_tab = ui.tab(translate_string("Findings"))
                table_tab = ui.tab(translate_string("Table"))
            with ui.tab_panels(tabs, value=findings_tab).classes("w-full").style("flex: 1 1 0; min-height: 8rem"):
                with ui.tab_panel(findings_tab).classes("p-0 h-full"), ui.scroll_area().classes("w-full h-full"):
                    self.findings = ui.column().classes("w-full gap-0 p-2")
                with ui.tab_panel(table_tab).classes("p-0 h-full"):
                    self._build_table()
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(translate_string("Save Report"), on_click=self.save_report).props("outline")
                ui.space()
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")
        self.draw()
        return self.dialog

    def _written_by(self) -> str:
        """The line under the title: which Tasker wrote the file, or why that is not known."""
        if not self.state.backup_loaded:
            return translate_string("No XML file has been loaded.  Get an XML file first.")
        written = compat.written_by(self.state)
        if written:
            return f"{translate_string('Written by Tasker')} {written}"
        return translate_string("The file does not say which Tasker wrote it.")

    def _build_table(self) -> None:
        """The curated table: a search box and every row, newest release first."""
        filter_box = ui.input(translate_string("Search")).props("dense clearable").classes("w-64")

        def column(name: str, label: str) -> dict[str, Any]:
            return {"name": name, "label": label, "field": name, "sortable": True, "align": "left"}

        rows = [
            {
                "key": str(number),
                "release": row.release,
                "what": row.what,
                "name": row.name,
                "note": row.note,
                "used": "" if row.used is None else row.used,
                "post": row.source,
            }
            for number, row in enumerate(compat.table(self.state))
        ]
        table = (
            ui.table(
                columns=[
                    column("release", translate_string("Release")),
                    column("what", translate_string("Type")),
                    column("name", translate_string("Name")),
                    column("note", translate_string("Note")),
                    column("used", translate_string("Used here")),
                    {**column("post", translate_string("Link")), "sortable": False},
                ],
                rows=rows,
                row_key="key",
            )
            .props("dense flat virtual-scroll")
            .classes("w-full")
            .style("height: 60vh")
        )
        # The post that announced it, as a link that opens in a tab of its own; blank where the release notes are the source.
        table.add_slot(
            "body-cell-post",
            '<q-td :props="props"><a v-if="props.value" :href="props.value" target="_blank" rel="noopener">&#8599;</a></q-td>',
        )
        filter_box.bind_value(table, "filter")

    # ---------------------------------------------------------------- the findings
    def pick(self, target: str | None = None, android: int | None = None) -> None:
        """A version was picked: check again and redraw."""
        if target is not None:
            self.target = target
        if android is not None:
            self.android = android
        self.result = compat.check(self.state, self.target, self.android)
        self.draw()

    def draw(self) -> None:
        """Draw the findings for the version picked, every place a click into the Map."""
        self.findings.clear()
        with self.findings:
            if not self.state.backup_loaded:
                ui.label(translate_string("No XML file has been loaded.  Get an XML file first.")).classes(
                    "text-sm italic text-gray-500",
                )
                return
            for row in compat.report_rows(self.result):
                self._draw_row(row)

    def _draw_row(self, row: Row) -> None:
        """One line: a link where it points somewhere, text coloured by its tag where not."""
        if row.target is not None:
            ui.link(row.text, "#").on("click", self.make_jump(row.target), js_handler=LINK_CLICK_JS).classes(
                "text-blue-600 dark:text-blue-400 font-mono text-xs whitespace-pre decoration-dotted hover:underline",
            )
            return
        tag = row.text.strip().split(" ", 1)[0]
        ui.label(row.text).classes(
            f"font-mono text-xs whitespace-pre {_TAG_CLASSES.get(tag, 'text-gray-700 dark:text-gray-300')}"
        )

    # ---------------------------------------------------------------- saving
    def save_report(self) -> None:
        """Write the findings as a text report, and say where it went."""
        file_path = compat.write_report(compat.report_rows(self.result), state=self.state)
        if file_path:
            ui.notify(f"{translate_string('Report saved as')} {file_path}", type="positive")
        else:
            ui.notify(translate_string("The report could not be saved."), type="negative")
