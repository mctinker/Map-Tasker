"""guiwins_projdeps: the Project Dependencies window -- the graph between Projects, a table of them, and each one's detail."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_projdeps: where mapops.projdeps hangs off the GUI.                               #
#                                                                                        #
# Three views of one thing.  A GRAPH, for the shape: an arrow from each Project to each      #
# Project it takes something from, loops outlined in red.  A TABLE, for finding one Project  #
# among eighty and for sorting by who is leaned on most.  And a DETAIL pane for the one       #
# chosen, which says what it needs, what needs it, and what deleting it would leave dangling  #
# -- every line a click into the Map, because "a Task in Home performs a Task in Utilities"    #
# is not something to take on trust.                                                         #
#                                                                                        #
# Choosing is shared: a click on a node of the graph chooses that Project in the table, and   #
# the table's choice is what the detail shows.  All the knowledge -- what a use is, what a     #
# loop is, what "sole" means -- is in projdeps; this is the drawing and the buttons.         #
#                                                                                        #
# Nothing here changes the configuration, so none of it is on the Undo list.                 #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core.mapjump import LINK_CLICK_JS, Row, Target
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import projdeps

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from nicegui.events import MermaidNodeClickEventArguments, TableSelectionEventArguments

    from maptasker.src.core.primitem import RunState

# The graph opens drawn when it has no more Projects than this; a bigger one is a hairball that the table says
# better, so it opens folded and is there to be opened.
_DRAWN_OPEN_UP_TO = 30


def build_project_dependencies_window(
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
    state: RunState,
) -> ui.dialog | None:
    """Build the window, or return None (after saying why) when there is no configuration to read.

    `make_jump` turns a place into the click that takes the user to it in the Map, and is passed in rather than
    imported, for the reason build_refactor_dialog gives.
    """
    if not state.tasker_root_elements.get("all_projects"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None
    return ProjectDependenciesWindow(make_jump, state).build()


class ProjectDependenciesWindow:
    """The window: the graph read from the configuration, which Project is chosen, and the handlers."""

    def __init__(
        self,
        make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
        state: RunState,
    ) -> None:
        """Read the configuration into a graph."""
        self.make_jump = make_jump
        self.state = state
        self.graph = projdeps.build_graph(state)
        self.drawing, self.node_names = projdeps.mermaid(self.graph)
        # The table's own rows, kept here because the table's are untyped.
        self.shown_rows: list[dict[str, Any]] = []
        self.dialog: ui.dialog
        self.table: ui.table
        self.detail: ui.column

    # ---------------------------------------------------------------- drawing
    def build(self) -> ui.dialog:
        """Draw the window, with nothing chosen."""
        with (
            ui.dialog().props("persistent maximized") as self.dialog,
            ui.card().classes("w-full h-full p-4 no-wrap gap-2"),
        ):
            ui.label(translate_string("Project Dependencies")).classes("text-lg font-bold text-blue-600")
            ui.label(self._summary()).classes("text-sm text-gray-600 dark:text-gray-300")
            self._build_graph()
            with ui.row().classes("w-full no-wrap gap-4").style("flex: 1 1 0; min-height: 8rem"):
                self._build_table()
                with ui.scroll_area().classes("flex-1 h-full border rounded dark:border-gray-700"):
                    self.detail = ui.column().classes("w-full gap-0 p-2")
            self._show_nothing()
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(translate_string("Save Report"), on_click=self.save_report).props("outline")
                ui.space()
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")
        return self.dialog

    def _summary(self) -> str:
        """One line: how many Projects there are."""
        return f"{translate_string('Projects')}: {len(self.graph.projects)}"

    def _build_graph(self) -> None:
        """The graph, in a section that can be folded away; or a line saying there is nothing to draw."""
        if not self.node_names:
            ui.label(translate_string("No Project uses anything that is in another Project.")).classes(
                "text-sm italic text-gray-500",
            )
            return
        with (
            ui.expansion(translate_string("Graph"), value=len(self.node_names) <= _DRAWN_OPEN_UP_TO).classes("w-full"),
            ui.scroll_area().classes("w-full h-80"),
        ):
            ui.mermaid(self.drawing, on_node_click=self.node_clicked)

    def _build_table(self) -> None:
        """The table of Projects, with a search box over it."""
        with ui.column().classes("h-full gap-1").style("flex: 0 0 45%; min-width: 0"):
            filter_box = ui.input(translate_string("Search")).props("dense clearable").classes("w-full")

            def column(name: str, label: str) -> dict[str, Any]:
                return {"name": name, "label": label, "field": name, "sortable": True, "align": "left"}

            self.shown_rows = self._rows()
            self.table = (
                ui.table(
                    columns=[
                        column("project", translate_string("Project")),
                        column("needs", translate_string("Needs")),
                        column("needed_by", translate_string("Needed by")),
                        column("status", translate_string("Status")),
                    ],
                    rows=self.shown_rows,
                    row_key="project",
                    selection="single",
                    on_select=self.chose,
                )
                .props("dense flat virtual-scroll")
                .classes("w-full")
                .style("flex: 1 1 0; min-height: 6rem")
            )
            filter_box.bind_value(self.table, "filter")

    def _rows(self) -> list[dict[str, Any]]:
        """One table row per Project."""
        words = {
            projdeps.SELF_CONTAINED: translate_string("Self-contained"),
            projdeps.NEEDS_OTHERS: translate_string("Needs others"),
            projdeps.IN_A_LOOP: translate_string("In a loop"),
        }
        return [
            {
                "project": name,
                "needs": len(self.graph.uses(name)),
                "needed_by": len(self.graph.used_by(name)),
                "status": words[self.graph.standing(name)],
            }
            for name in self.graph.projects
        ]

    # ---------------------------------------------------------------- choosing
    def node_clicked(self, event: MermaidNodeClickEventArguments) -> None:
        """A node of the graph was clicked: choose that Project in the table."""
        name = self.node_names.get(str(event.node_id))
        if name is None:
            return
        row = next((each for each in self.shown_rows if each["project"] == name), None)
        if row is not None:
            self.table.selected = [row]
            self.table.update()
            self.show(name)

    def chose(self, event: TableSelectionEventArguments) -> None:
        """The table's choice changed."""
        if event.selection:
            self.show(str(event.selection[0]["project"]))
        else:
            self._show_nothing()

    def _show_nothing(self) -> None:
        """Nothing is chosen: say what to do."""
        self.detail.clear()
        with self.detail:
            ui.label(translate_string("Choose a Project to see what it needs and what needs it.")).classes(
                "text-sm italic text-gray-500",
            )

    def show(self, project: str) -> None:
        """Draw what the graph says about one Project, every line that points somewhere a click into the Map."""
        self.detail.clear()
        with self.detail:
            for row in projdeps.project_rows(self.graph, project):
                self._draw(row)

    def _draw(self, row: Row) -> None:
        """One line of the detail: its pieces as links where they point somewhere and as text where not."""
        pieces = row.pieces or [(row.text, row.target)]
        with ui.row().classes("gap-0 items-baseline no-wrap"):
            for text, target in pieces:
                if target is None:
                    ui.label(text).classes(f"font-mono text-xs whitespace-pre {_emphasis(text)}")
                else:
                    ui.link(text, "#").on("click", self.make_jump(target), js_handler=LINK_CLICK_JS).classes(
                        "text-blue-600 dark:text-blue-400 font-mono text-xs whitespace-pre "
                        "decoration-dotted hover:underline",
                    )

    # ---------------------------------------------------------------- saving
    def save_report(self) -> None:
        """Write the whole graph as a text report, and say where it went."""
        file_path = projdeps.write_report(projdeps.report_rows(self.graph), state=self.state)
        if file_path:
            ui.notify(f"{translate_string('Report saved as')} {file_path}", type="positive")
        else:
            ui.notify(translate_string("The report could not be saved."), type="negative")


def _emphasis(text: str) -> str:
    """How a line that is not a link is coloured: the headings of a Project's detail stand out from its lines."""
    stripped = text.strip()
    if stripped.startswith(("If this Project", "Deleting this Project")):
        return "font-bold text-orange-600 dark:text-orange-400"
    if stripped.startswith(("Needs ", "Used by ", "In a loop")):
        return "font-bold text-gray-800 dark:text-gray-200"
    return "text-gray-700 dark:text-gray-300"
