"""guiwins_retire: the Plugin Retirement Advisor window -- which plugins Tasker now does itself, and where the file uses them."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_retire: where mapops.retire hangs off the GUI.                                      #
#                                                                                        #
# Two tabs over one table.  PLUGINS answers the question the window is opened with: of the     #
# plugins the loaded file uses, which has a built-in in Tasker, which built-in and since which     #
# version, and where the file uses the plugin -- each place a click into the Map.  TABLE is the     #
# short list the advisor works from, every plugin Tasker has taken over from with the link to        #
# where that was said; it is worth reading with no file open at all, which is why this window        #
# opens without one.                                                                              #
#                                                                                        #
# All the knowledge is in retire; this is the drawing and the buttons.                             #
#                                                                                        #
# Nothing here changes the configuration, so none of it is on the Undo list.                       #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core.mapjump import LINK_CLICK_JS, Row, Target
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import retire

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core.primitem import RunState

# How a finding's tag is coloured: green where the plugin can simply go, orange where it depends on what it is used for.
_TAG_CLASSES = {
    retire.REPLACED: "font-bold text-green-700 dark:text-green-400",
    retire.PARTLY_REPLACED: "font-bold text-orange-600 dark:text-orange-400",
}


def build_retirement_window(
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
    state: RunState,
) -> ui.dialog:
    """Build the Plugin Retirement Advisor window.

    `make_jump` turns a place into the click that takes the user to it in the Map, and is passed in rather than
    imported, for the reason build_refactor_dialog gives.  It opens with nothing loaded: the table is worth reading
    without a file, and the Plugins tab says what is missing.
    """
    return RetirementWindow(make_jump, state).build()


class RetirementWindow:
    """The window: the advice drawn for the loaded file, the table behind it, and the Save Report handler."""

    def __init__(
        self,
        make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
        state: RunState,
    ) -> None:
        """Remember where to send a click, and work out the advice for the file as it is now."""
        self.make_jump = make_jump
        self.state = state
        self.result = retire.advise(state)
        self.dialog: ui.dialog
        self.advice: ui.column

    # ---------------------------------------------------------------- drawing
    def build(self) -> ui.dialog:
        """Draw the window and fill both tabs."""
        with (
            ui.dialog().props("persistent maximized") as self.dialog,
            ui.card().classes("w-full h-full p-4 no-wrap gap-2"),
        ):
            ui.label(translate_string("Plugin Retirement Advisor")).classes("text-lg font-bold text-blue-600")
            ui.label(self._subtitle()).classes("text-sm text-gray-600 dark:text-gray-300")
            with ui.tabs().classes("w-full") as tabs:
                plugins_tab = ui.tab(translate_string("Plugins"))
                table_tab = ui.tab(translate_string("Table"))
            with ui.tab_panels(tabs, value=plugins_tab).classes("w-full").style("flex: 1 1 0; min-height: 8rem"):
                with ui.tab_panel(plugins_tab).classes("p-0 h-full"), ui.scroll_area().classes("w-full h-full"):
                    self.advice = ui.column().classes("w-full gap-0 p-2")
                with ui.tab_panel(table_tab).classes("p-0 h-full"):
                    self._build_table()
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(translate_string("Save Report"), on_click=self.save_report).props("outline")
                ui.space()
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")
        self.draw()
        return self.dialog

    def _subtitle(self) -> str:
        """The line under the title: what this is for, or why there is nothing to show."""
        if not self.state.backup_loaded:
            return translate_string("No XML file has been loaded.  Get an XML file first.")
        return translate_string("Plugins this file uses that Tasker can now do itself.")

    def _build_table(self) -> None:
        """The table the advisor works from: a search box and every plugin it knows."""
        filter_box = ui.input(translate_string("Search")).props("dense clearable").classes("w-64")

        def column(name: str, label: str) -> dict[str, Any]:
            return {"name": name, "label": label, "field": name, "sortable": True, "align": "left"}

        rows = [
            {
                "key": str(number),
                "plugin": row.plugin,
                "package": row.package,
                "covers": row.covers,
                "replaced_by": row.replaced_by,
                "since": row.since,
                "note": row.note,
                "used": "" if row.used is None else row.used,
                "source": row.source,
            }
            for number, row in enumerate(retire.table(self.state))
        ]
        table = (
            ui.table(
                columns=[
                    column("plugin", translate_string("Plugin")),
                    column("covers", translate_string("Type")),
                    column("replaced_by", translate_string("Replaced by")),
                    column("since", translate_string("Since Tasker")),
                    column("note", translate_string("Note")),
                    column("used", translate_string("Used here")),
                    {**column("source", translate_string("Link")), "sortable": False},
                ],
                rows=rows,
                row_key="key",
            )
            .props("dense flat")
            .classes("w-full")
        )
        # Where the pairing was said, as a link that opens in a tab of its own.
        table.add_slot(
            "body-cell-source",
            '<q-td :props="props"><a v-if="props.value" :href="props.value" target="_blank" rel="noopener">&#8599;</a></q-td>',
        )
        filter_box.bind_value(table, "filter")

    def draw(self) -> None:
        """Draw the advice for the file, every place a click into the Map."""
        self.advice.clear()
        with self.advice:
            if not self.state.backup_loaded:
                ui.label(translate_string("No XML file has been loaded.  Get an XML file first.")).classes(
                    "text-sm italic text-gray-500",
                )
                return
            for row in retire.report_rows(self.result):
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
            f"font-mono text-xs whitespace-pre {_TAG_CLASSES.get(tag, 'text-gray-700 dark:text-gray-300')}",
        )

    # ---------------------------------------------------------------- saving
    def save_report(self) -> None:
        """Write the advice as a text report, and say where it went."""
        file_path = retire.write_report(retire.report_rows(self.result, loaded=self.state.backup_loaded), self.state)
        if file_path:
            ui.notify(f"{translate_string('Report saved as')} {file_path}", type="positive")
        else:
            ui.notify(translate_string("The report could not be saved."), type="negative")
