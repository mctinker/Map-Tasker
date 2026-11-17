"""guiwins_namerules: the Naming Rules window -- set the house style, see what breaks it, and rename with a preview."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_namerules: where mapops.namerules and mapops.namefix hang off the GUI.         #
#                                                                                        #
# Three tabs over one set of rules.  RULES is where the style is written down: a prefix    #
# per kind of name, no default names, a label on every action of a long Task, a longest   #
# Task.  BREACHES is the report -- every place the loaded file breaks the rules, each a    #
# click into the Map.  RENAMES lists the breaches that have a new name to give, and        #
# renames the ones that are ticked.                                                       #
#                                                                                        #
# THE RENAMES FOLLOW THE REFACTOR DIALOG'S RULE, and for its reason: Apply is disabled      #
# until a preview exists for what is ticked right now, and ticking or unticking anything    #
# clears the preview and disables it again.  There is then no way to reach namefix's apply   #
# without having been shown what it would do -- the Tasks and Profiles it renames, the        #
# calls it rewrites, and the ones it left alone and why.                                    #
#                                                                                        #
# All the knowledge is in namerules and namefix; this is the drawing and the buttons.        #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from nicegui import ui

from maptasker.src.core.mapjump import LINK_CLICK_JS, Row, Target
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import maprefac, namefix, namerules
from maptasker.src.mapops.namerules import Breach, Rules

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core.primitem import RunState

# How many lines are drawn.  A prefix rule on a large file can have thousands of breaches, and a widget per line is
# what makes a window slow; the report file holds them all, and the window says so.
_LINE_LIMIT = 600
_ROW_LIMIT = 2000
_LINK_CLASSES = "text-blue-600 dark:text-blue-400 font-mono text-xs whitespace-pre decoration-dotted hover:underline"


def build_naming_rules_window(
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
    refresh: Callable[[], Coroutine[Any, Any, None]],
    save_configuration: Callable[[], Coroutine[Any, Any, bool]],
    state: RunState,
) -> ui.dialog:
    """Build the Naming Rules window.

    `make_jump` turns a place into the click that takes the user to it in the Map, `refresh` brings the
    pulldowns up to date after a rename, and `save_configuration` writes the whole configuration to a file and
    returns whether what the window holds must be read again; all three are passed in rather than imported, for
    the reason build_refactor_dialog gives.  It opens with nothing loaded: the rules can be set before any file is.
    """
    return NamingRulesWindow(make_jump, refresh, save_configuration, state).build()


class NamingRulesWindow:
    """The window: the rules, the breaches drawn for the loaded file, and the renames offered for them."""

    def __init__(
        self,
        make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
        refresh: Callable[[], Coroutine[Any, Any, None]],
        save_configuration: Callable[[], Coroutine[Any, Any, bool]],
        state: RunState,
    ) -> None:
        """Remember where to send a click, and read the rules that were saved."""
        self.make_jump = make_jump
        self.refresh = refresh
        self.save_configuration = save_configuration
        self.state = state
        self.rules = namerules.load()
        self.breaches: list[Breach] = []
        self.renamable: list[Breach] = []
        self.held: dict[str, Any] = {"plan": None, "chosen": None}
        self.fields: dict[str, Any] = {}
        self.dialog: ui.dialog
        self.tabs: ui.tabs
        self.breaches_tab: ui.tab
        self.summary: ui.label
        self.breach_area: ui.column
        self.table: ui.table
        self.preview_area: ui.column
        self.apply_button: ui.button
        self.summary_of_preview: ui.label

    # ---------------------------------------------------------------- drawing
    def build(self) -> ui.dialog:
        """Draw the window and fill it from the saved rules."""
        with (
            ui.dialog().props("persistent maximized") as self.dialog,
            ui.card().classes("w-full h-full p-4 no-wrap gap-2"),
        ):
            ui.label(translate_string("Naming Rules")).classes("text-lg font-bold text-blue-600")
            ui.label(
                translate_string(
                    "Set the house style for names and Task length, and see what breaks it.  A rule left empty or "
                    "at zero is off.",
                ),
            ).classes("text-sm text-gray-600 dark:text-gray-300")
            with ui.tabs().classes("w-full") as self.tabs:
                rules_tab = ui.tab(translate_string("Rules"))
                self.breaches_tab = ui.tab(translate_string("Breaches"))
                renames_tab = ui.tab(translate_string("Renames"))
            with ui.tab_panels(self.tabs, value=rules_tab).classes("w-full").style("flex: 1 1 0; min-height: 8rem"):
                with ui.tab_panel(rules_tab).classes("p-2 h-full"), ui.scroll_area().classes("w-full h-full"):
                    self._build_rules()
                with ui.tab_panel(self.breaches_tab).classes("p-0 h-full"):
                    self._build_breaches()
                with ui.tab_panel(renames_tab).classes("p-0 h-full"):
                    self._build_renames()
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(translate_string("Check"), on_click=self.check_now).props("outline")
                ui.button(translate_string("Save Report"), on_click=self.save_report).props("outline")
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")
        self.draw()
        return self.dialog

    def _build_rules(self) -> None:
        """The inputs, one per rule, filled from what was saved."""
        rules = self.rules
        with ui.column().classes("w-full max-w-xl gap-1"):
            ui.label(translate_string("A name must start with")).classes("font-bold")
            for key, label in (
                ("profile_prefix", "Profile prefix"),
                ("task_prefix", "Task prefix"),
                ("scene_prefix", "Scene prefix"),
                ("global_variable_prefix", "Global variable prefix (needs a capital letter)"),
                ("local_variable_prefix", "Local variable prefix (lower case only)"),
            ):
                self.fields[key] = (
                    ui.input(translate_string(label), value=getattr(rules, key)).props("dense").classes("w-full")
                )
            ui.label(translate_string("Structure")).classes("font-bold mt-2")
            self.fields["no_default_names"] = ui.checkbox(
                translate_string("No leftover default names like “Task 12”."),
                value=rules.no_default_names,
            )
            self.fields["label_after"] = (
                ui.number(
                    translate_string("In a Task of more than this many actions, label every action (0 is off)"),
                    value=rules.label_after,
                    min=0,
                    precision=0,
                )
                .props("dense")
                .classes("w-full")
            )
            self.fields["max_task_length"] = (
                ui.number(
                    translate_string("No Task may have more than this many actions (0 is off)"),
                    value=rules.max_task_length,
                    min=0,
                    precision=0,
                )
                .props("dense")
                .classes("w-full")
            )
            ui.button(translate_string("Clear Rules"), on_click=self.clear_rules).props("flat dense")

    def _build_breaches(self) -> None:
        self.summary = ui.label("").classes("text-sm px-2 pt-2")
        with ui.scroll_area().classes("w-full").style("flex: 1 1 0; min-height: 8rem"):
            self.breach_area = ui.column().classes("w-full gap-0 p-2")

    def _build_renames(self) -> None:
        """The breaches that have a new name: a table to tick, Preview and Apply, and the preview."""
        ui.label(
            translate_string(
                "Tick the names to change, then Preview.  Apply stays off until a preview exists for what is "
                "ticked.  Scenes are not renamed here.",
            ),
        ).classes("text-sm px-2 pt-2")
        self.table = (
            ui.table(
                columns=[
                    {"name": "kind", "label": translate_string("Kind"), "field": "kind", "align": "left"},
                    {"name": "name", "label": translate_string("Name"), "field": "name", "align": "left"},
                    {"name": "new", "label": translate_string("New name"), "field": "new", "align": "left"},
                ],
                rows=[],
                row_key="key",
                selection="multiple",
                on_select=lambda _event: self.invalidate(),
            )
            .props("dense flat")
            .classes("w-full")
            .style("max-height: 16rem")
        )
        with ui.row().classes("w-full items-center gap-2 px-2"):
            ui.button(translate_string("Tick All"), on_click=self.tick_all).props("outline dense")
            ui.button(translate_string("Preview"), on_click=self.preview).classes("bg-blue-600 text-white")
            self.apply_button = ui.button(translate_string("Apply"), on_click=self.do_apply).classes(
                "bg-orange-600 text-white",
            )
            self.apply_button.disable()
            save_file_button = ui.button(translate_string("Save To Current File"), on_click=self.do_save).classes(
                "bg-green-600 text-white",
            )
            with save_file_button:
                ui.tooltip(
                    translate_string(
                        "Write the renames made so far -- and every other edit this session -- to a file.\n\n"
                        "Apply changes the loaded configuration and no file.  This writes the whole "
                        "configuration to a new, timestamped copy of the loaded file and switches to that copy; "
                        "the original file is never written to.",
                    ),
                ).style("white-space: pre-wrap")
            self.summary_of_preview = ui.label("").classes("text-sm")
        with ui.scroll_area().classes("w-full").style("flex: 1 1 0; min-height: 6rem"):
            self.preview_area = ui.column().classes("w-full gap-0 p-2")

    def _draw_rows(self, area: ui.column, rows: list[Row]) -> None:
        """Rows as lines: a link where one points somewhere, plain text where not.  Said, not cut, when there are many."""
        area.clear()
        with area:
            for row in rows[:_LINE_LIMIT]:
                if row.target is not None:
                    ui.link(row.text, "#").on("click", self.make_jump(row.target), js_handler=LINK_CLICK_JS).classes(
                        _LINK_CLASSES,
                    )
                else:
                    ui.label(row.text).classes("font-mono text-xs whitespace-pre text-gray-700 dark:text-gray-300")
            if len(rows) > _LINE_LIMIT:
                ui.label(
                    f"... {len(rows) - _LINE_LIMIT} {translate_string('more lines.  Save Report writes them all.')}",
                ).classes("font-mono text-xs text-orange-600 dark:text-orange-400")

    def draw(self) -> None:
        """Draw the breaches and fill the table of renames."""
        loaded = self.state.backup_loaded
        rows = namerules.report_rows(self.rules, self.breaches, loaded=loaded)
        real = [breach for breach in self.breaches if breach.rule != namerules.BAD_RULE]
        self.summary.set_text(
            translate_string("Press Check to read the loaded file against the rules.")
            if not self.breaches and not self.rules.is_empty
            else f"{len(real)} {translate_string('breaches')}",
        )
        self._draw_rows(self.breach_area, rows)
        self.renamable = [breach for breach in self.breaches if breach.can_rename][:_ROW_LIMIT]
        self.table.rows = [
            {"key": str(number), "kind": breach.kind, "name": breach.name, "new": breach.suggestion}
            for number, breach in enumerate(self.renamable)
        ]
        self.table.selected = []
        self.table.update()
        self.invalidate()

    # ---------------------------------------------------------------- the rules
    def read_rules(self) -> Rules:
        """The rules as the inputs hold them now.  A prefix is kept exactly: a trailing space is the point of 'Z '."""

        def number(key: str) -> int:
            try:
                return max(0, int(self.fields[key].value or 0))
            except (TypeError, ValueError):
                return 0

        return Rules(
            profile_prefix=self.fields["profile_prefix"].value or "",
            task_prefix=self.fields["task_prefix"].value or "",
            scene_prefix=self.fields["scene_prefix"].value or "",
            global_variable_prefix=self.fields["global_variable_prefix"].value or "",
            local_variable_prefix=self.fields["local_variable_prefix"].value or "",
            no_default_names=bool(self.fields["no_default_names"].value),
            label_after=number("label_after"),
            max_task_length=number("max_task_length"),
        )

    def check_now(self) -> None:
        """Keep the rules as written, read the loaded file against them, and show what breaks them."""
        self.rules = self.read_rules()
        if not namerules.save(self.rules):
            ui.notify(translate_string("The rules could not be saved."), type="negative")
        self.breaches = namerules.check(self.rules, self.state)
        self.draw()
        self.tabs.set_value(self.breaches_tab)
        if not self.state.backup_loaded:
            ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        elif self.rules.is_empty:
            ui.notify(translate_string("No rule has been set."), type="info")
        elif not [breach for breach in self.breaches if breach.rule != namerules.BAD_RULE]:
            ui.notify(translate_string("Nothing breaks the rules."), type="positive")

    def clear_rules(self) -> None:
        """Turn every rule off."""
        blank = Rules()
        for key, widget in self.fields.items():
            widget.set_value(getattr(blank, key))

    # ---------------------------------------------------------------- renaming
    def chosen(self) -> list[Breach]:
        """The breaches whose rows are ticked, in the table's order."""
        selected = cast("list[dict[str, str]]", self.table.selected)  # pyright: ignore[reportUnknownMemberType]
        keys = {row["key"] for row in selected}
        return [breach for number, breach in enumerate(self.renamable) if str(number) in keys]

    def tick_all(self) -> None:
        """Tick every row."""
        self.table.selected = list(cast("list[dict[str, str]]", self.table.rows))  # pyright: ignore[reportUnknownMemberType]
        self.table.update()
        self.invalidate()

    def invalidate(self) -> None:
        """Throw away the preview and disable Apply.  Every change to what is ticked comes here."""
        self.held.update(plan=None, chosen=None)
        self.apply_button.disable()
        self.preview_area.clear()
        self.summary_of_preview.set_text("")

    def preview(self) -> None:
        """Work out what renaming the ticked names would do, and show it.  Changes nothing."""
        chosen = self.chosen()
        if not chosen:
            ui.notify(translate_string("Tick the names to change first."), type="warning")
            return
        plan = namefix.plan_renames(chosen, self.state)
        self.held.update(plan=plan, chosen=[id(breach) for breach in chosen])
        self._draw_rows(self.preview_area, maprefac.report_rows(plan))
        self.summary_of_preview.set_text(
            translate_string("cannot be done")
            if not plan.can_apply
            else f"{len(plan.steps)} {translate_string('steps')}",
        )
        if plan.can_apply:
            self.apply_button.enable()
        else:
            self.apply_button.disable()

    async def do_apply(self) -> None:
        """The Apply button.  Only ever applies the plan on screen."""
        plan = self.held["plan"]
        if plan is None or self.held["chosen"] != [id(breach) for breach in self.chosen()]:
            ui.notify(translate_string("Press Preview first."), type="warning")
            self.invalidate()
            return
        done, errors = maprefac.apply(plan, state=self.state)
        for message in errors[:4]:
            ui.notify(message, type="negative")
        if not done:
            return
        ui.notify(f"{plan.what}. {translate_string('Undo is available.')}", type="positive", position="top")
        await self.refresh()
        self.breaches = namerules.check(self.rules, self.state)
        self.draw()

    async def do_save(self) -> None:
        """The Save To Current File button: write the renames -- and every other edit this session -- to a file.

        Applying changes the loaded configuration and no file.  When the save switches to the new copy the whole
        configuration is reloaded, so every breach the window holds belongs to a tree nothing renders from any
        more: the file is read against the rules again and the window redrawn, which also clears the preview.
        """
        if await self.save_configuration():
            self.breaches = namerules.check(self.rules, self.state)
            self.draw()

    # ---------------------------------------------------------------- saving
    def save_report(self) -> None:
        """Write the breaches as a text report, and say where it went."""
        rows = namerules.report_rows(self.rules, self.breaches, loaded=self.state.backup_loaded)
        file_path = namerules.write_report(rows, self.state)
        if file_path:
            ui.notify(f"{translate_string('Report saved as')} {file_path}", type="positive")
        else:
            ui.notify(translate_string("The report could not be saved."), type="negative")
