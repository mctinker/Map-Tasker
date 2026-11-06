"""guiwins_varman: the Variable Manager window -- a table of every global variable, and what can be done to one."""

#! /usr/bin/env python3

#                                                                                       #
# guiwins_varman: draw mapvars's table of global variables, and the dialogs for the      #
#                 things done to one of them.  All the knowledge is in mapvars (what the  #
#                 rows are, which are flagged, what each change would do) and livevars   #
#                 (the phone); this is only the drawing and the buttons.                 #
#                                                                                       #
# EVERY CHANGE GOES THROUGH A PREVIEW, the way Refactor's do: a plan that says what it will #
# do and what it will leave alone, an Apply that is enabled only while the preview on      #
# screen is of what is in the fields, and one Undo for the whole of it.  Rename, change a   #
# value and delete change the LOADED CONFIGURATION, and nothing on disk or on the phone    #
# until it is saved.  Pushing a value to the phone is the one thing here that touches the   #
# device, and it asks which phone first, sends one value, and reads it back.               #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from nicegui import run, ui

from maptasker.src.core.mapjump import LINK_CLICK_JS
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui import livevars
from maptasker.src.gui.guiutils_android import (
    android_address_defaults,
    remember_android_address,
    remember_android_address_fields,
)
from maptasker.src.mapops import maprefac, mapvars

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from nicegui.events import TableSelectionEventArguments

    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui
    from maptasker.src.mapops.maprefac_model import Plan


def _flag_words() -> dict[str, str]:
    """The marks, in words a person reads in a table cell.  Looked up when asked, in whatever language is on."""
    return {
        mapvars.NEVER_READ: translate_string("Is set but never read"),
        mapvars.NEVER_SET: translate_string("Is read but never set"),
        mapvars.UNUSED: translate_string("Unused"),
    }


def _flag_help() -> dict[str, str]:
    """What each mark means, as a sentence."""
    return {
        mapvars.NEVER_READ: translate_string("Something sets this and nothing in the file reads it."),
        mapvars.NEVER_SET: translate_string(
            "Something reads this, nothing sets it and the Variables tab does not hold it, so a read sees an empty value.",
        ),
        mapvars.UNUSED: translate_string(
            "In the Variables tab and used nowhere in the file -- the safe one to delete."
        ),
    }


_T = TypeVar("_T")

_PREVIEW_LINE_LIMIT = 200
_NAMES_SHOWN = 6
_VALUE_SHOWN = 60
_USES_SHOWN = 400


def _shown(value: str) -> str:
    """A value as one short line for a table cell."""
    folded = " ".join(value.split())
    return folded if len(folded) <= _VALUE_SHOWN else f"{folded[: _VALUE_SHOWN - 3]}..."


def build_variable_manager(
    gui: MyGui,
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
    save_configuration: Callable[[], Coroutine[Any, Any, Any]],
    state: RunState,
) -> ui.dialog | None:
    """Build the Variable Manager, or None when there is nothing loaded to manage.

    `make_jump` turns a place into the click that takes the user to it in the Map, and `save_configuration` writes
    the loaded configuration to a file; both come from the window and are passed in rather than imported, for the
    reason build_refactor_dialog gives.
    """
    if not state.tasker_root_elements.get("all_tasks"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None
    return VariableManager(gui, make_jump, save_configuration, state).build()


class VariableManager:
    """The window: the rows on screen, which one is chosen, what the phone said, and the handlers."""

    def __init__(
        self,
        gui: MyGui,
        make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
        save_configuration: Callable[[], Coroutine[Any, Any, Any]],
        state: RunState,
    ) -> None:
        """Remember what the window needs from the view: where to send a click, how to save, and the run's state."""
        self.gui = gui
        self.make_jump = make_jump
        self.save_configuration = save_configuration
        self.state = state
        self.live: livevars.LiveValues | None = None
        self.rows: list[mapvars.Row] = []
        # What the table was last given to show: its own rows, kept here because the table's are untyped.
        self.shown_rows: list[dict[str, Any]] = []
        # The rows ticked in the table, in table order.  Delete acts on all of them; every other change needs exactly one.
        self.picked: list[mapvars.Row] = []
        self.dialog: ui.dialog
        self.table: ui.table
        self.summary: ui.label
        self.uses_area: ui.scroll_area
        self.uses_heading: ui.label
        # Which mark the table is limited to, or "" for every variable.
        self.show: str = ""
        self.filter_buttons: dict[str, ui.button] = {}
        self.buttons: dict[str, ui.button] = {}

    # ---------------------------------------------------------------- drawing
    def build(self) -> ui.dialog:
        """Draw the window and fill the table."""
        with (
            ui.dialog().props("persistent maximized") as self.dialog,
            ui.card().classes("w-full h-full p-4 no-wrap gap-2"),
        ):
            ui.label(translate_string("Variable Manager")).classes("text-lg font-bold text-blue-600")
            self.summary = ui.label("").classes("text-sm text-gray-600 dark:text-gray-300")

            with ui.row().classes("w-full items-center gap-4"):
                filter_box = ui.input(translate_string("Search")).props("dense clearable").classes("w-64")
                ui.space()
                ui.button(translate_string("Get From Phone"), icon="sensors", on_click=self.read_live).props("outline")

            with ui.row().classes("w-full items-center gap-2"):
                self._filter_button("", translate_string("Show All"))
                for flag, label in (
                    (mapvars.NEVER_READ, translate_string("Is set but never read")),
                    (mapvars.NEVER_SET, translate_string("Is read but never set")),
                    (mapvars.UNUSED, translate_string("Unused")),
                ):
                    self._filter_button(flag, label)

            self.table = (
                ui.table(columns=self._columns(), rows=[], row_key="name", selection="multiple", on_select=self.chose)
                .props("dense flat virtual-scroll")
                .classes("w-full")
                # Every spare line of the window, so more rows show on a taller one and the buttons below stay at
                # the bottom.  A zero height with a flex grow is what lets a virtual-scroll table fill what is left.
                .style("flex: 1 1 0; min-height: 8rem")
            )
            filter_box.bind_value(self.table, "filter")

            with ui.row().classes("w-full items-center gap-2"):
                self._action("rename", translate_string("Rename"), "drive_file_rename_outline", self.rename)
                self._action("change", translate_string("Change Value"), "edit", self.change_value)
                self._action("delete", translate_string("Delete"), "delete", self.delete)
                self._action("push", translate_string("Send To Phone"), "upload", self.push)
                self._action("unpush", translate_string("Delete On Phone"), "phonelink_erase", self.delete_from_phone)
            self.uses_heading = ui.label("").classes("text-sm font-bold text-orange-500")
            self.uses_area = ui.scroll_area().classes("w-full h-40 shrink-0 border rounded dark:border-gray-700")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button(translate_string("Save To Current File"), on_click=self.save).props("outline")
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")

        self.refresh()
        self.choose(None)
        return self.dialog

    @staticmethod
    def _columns() -> list[dict[str, Any]]:
        """The table's columns."""

        def column(name: str, label: str, *, numeric: bool = False) -> dict[str, Any]:
            return {
                "name": name,
                "label": label,
                "field": name,
                "sortable": True,
                "align": "right" if numeric else "left",
            }

        return [
            column("name", translate_string("Variable")),
            column("value", translate_string("Value")),
            column("type", translate_string("Type")),
            column("sets", translate_string("Places that set it"), numeric=True),
            column("reads", translate_string("Places that read it"), numeric=True),
            column("flag", translate_string("Status")),
            column("phone", translate_string("On the phone")),
        ]

    def _filter_button(self, flag: str, label: str) -> None:
        """One of the buttons that limit the table to a mark; the one in force is filled in, the rest outlined."""
        button = ui.button(label, on_click=lambda: self.limit_to(flag)).props("dense no-caps")
        self.filter_buttons[flag] = button
        self._style_filter_button(flag)

    def _style_filter_button(self, flag: str) -> None:
        """Fill the button for the mark in force, outline the others."""
        button = self.filter_buttons[flag]
        if flag == self.show:
            button.props(remove="outline")
        else:
            button.props("outline")

    def limit_to(self, flag: str) -> None:
        """Show only the variables with this mark -- or every one, for "" and for the mark already in force."""
        self.show = "" if flag == self.show else flag
        for each in self.filter_buttons:
            self._style_filter_button(each)
        self.refresh()

    def _action(self, key: str, label: str, icon: str, handler: Callable[[], Any]) -> None:
        """One of the buttons that act on the chosen variable or variables."""
        self.buttons[key] = ui.button(label, icon=icon, on_click=handler)

    @property
    def chosen(self) -> mapvars.Row | None:
        """The variable the buttons act on when exactly one is ticked, else None."""
        return self.picked[0] if len(self.picked) == 1 else None

    def _table_rows(self) -> list[dict[str, Any]]:
        """What the table shows for each row of the model."""
        shown = [row for row in self.rows if row.flag == self.show] if self.show else self.rows
        return [
            {
                "name": row.name,
                "value": _shown(row.value) if row.declared else "",
                "type": row.value_type if row.declared else "",
                "sets": row.sets,
                "reads": row.reads,
                "flag": _flag_words()[row.flag] if row.flag else "",
                "phone": self._phone_text(row),
            }
            for row in shown
        ]

    def _phone_text(self, row: mapvars.Row) -> str:
        """What the phone holds for this variable, or what it says about it."""
        if row.live is None:
            return ""
        if not row.on_device:
            return translate_string("not found on the phone")
        text = _shown(row.live) or translate_string("(empty)")
        return f"{text}  ({translate_string('differs from the file')})" if row.differs else text

    def refresh(self, *_args: object) -> None:
        """Rebuild the model from the loaded configuration and redraw the table, keeping what is ticked if it survives."""
        keep = {row.name for row in self.picked}
        self.rows = mapvars.build_rows(self.state, self.live)
        self.shown_rows = self._table_rows()
        self.table.rows = self.shown_rows
        self.table.update()
        counts = mapvars.flag_counts(self.rows)
        marked = ", ".join(f"{counts[flag]} {_flag_words()[flag].lower()}" for flag in mapvars.FLAG_ORDER)
        self.summary.set_text(f"{len(self.rows)} {translate_string('global variables')}.  {marked}.")
        for flag, button in self.filter_buttons.items():
            if flag:
                button.set_text(f"{_flag_words()[flag]} ({counts[flag]})")
            else:
                button.set_text(f"{translate_string('Show All')} ({len(self.rows)})")
        self.choose_many([row for row in self.rows if row.name in keep])

    def chose(self, event: TableSelectionEventArguments) -> None:
        """A row was ticked or unticked in the table: what is ticked now is what the buttons act on."""
        names = {item["name"] for item in event.selection}
        self.choose_many([row for row in self.rows if row.name in names], sync=False)

    def choose(self, row: mapvars.Row | None) -> None:
        """Make this the one variable the buttons act on."""
        self.choose_many([row] if row is not None else [])

    def choose_many(self, rows: list[mapvars.Row], *, sync: bool = True) -> None:
        """Make these the variables the buttons act on, tick them in the table, and show where they are used.

        Delete takes one or more; Rename, Change Value and Send To Phone are about one variable and wait for exactly one.
        """
        self.picked = rows
        if sync:
            names = {row.name for row in rows}
            self.table.selected = [item for item in self.shown_rows if item["name"] in names]
        one = len(rows) == 1
        self.buttons["rename"].set_enabled(one)
        self.buttons["change"].set_enabled(one)
        self.buttons["push"].set_enabled(one)
        self.buttons["delete"].set_enabled(bool(rows))
        self.buttons["unpush"].set_enabled(bool(rows))
        self.uses_area.clear()
        if len(rows) > 1:
            self._show_several(rows)
        elif one:
            self._show_uses(rows[0])
        else:
            self.uses_heading.set_text(translate_string("Choose a variable to see where it is used."))

    def _show_several(self, rows: list[mapvars.Row]) -> None:
        """What to say when more than one is ticked: how many, and which."""
        self.uses_heading.set_text(f"{len(rows)} {translate_string('global variables')}")
        with self.uses_area, ui.column().classes("w-full gap-0 p-2"):
            for row in rows[:_USES_SHOWN]:
                ui.label(row.name).classes("font-mono text-xs")

    def _show_uses(self, row: mapvars.Row) -> None:
        """Where one variable is set and read, each place a link to it in the Map."""
        self.uses_heading.set_text(f"{row.name}  --  {self._flag_help(row)}".rstrip(" -"))
        references = [("set", ref) for ref in row.variable.sets] if row.variable else []
        references += [("read", ref) for ref in row.variable.reads] if row.variable else []
        seen: set[tuple[str, str, str]] = set()
        with self.uses_area, ui.column().classes("w-full gap-0 p-2"):
            for role, reference in references[:_USES_SHOWN]:
                key = (role, reference.where, reference.detail)
                if key in seen:
                    continue
                seen.add(key)
                text = f"{role:<5} {reference.where}   {reference.detail}"
                if reference.target is not None:
                    ui.link(text, "#").on("click", self.make_jump(reference.target), js_handler=LINK_CLICK_JS).classes(
                        "text-blue-600 dark:text-blue-400 font-mono text-xs whitespace-pre decoration-dotted"
                    )
                else:
                    ui.label(text).classes("font-mono text-xs whitespace-pre")
            if not references:
                ui.label(translate_string("Nothing in this file sets or reads it.")).classes("text-xs italic")

    @staticmethod
    def _flag_help(row: mapvars.Row) -> str:
        """The sentence for a variable's mark, with what the file adds when the variable is declared."""
        if not row.flag:
            return ""
        extra = ""
        if row.flag == mapvars.NEVER_READ and row.declared:
            extra = "  " + translate_string("It is in the Variables tab, so you may look at it on the phone.")
        return _flag_help()[row.flag] + extra

    # ---------------------------------------------------------------- the phone
    async def read_live(self) -> None:
        """Ask which phone, read every global from it, and show what it holds beside what the file says."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(translate_string("Get From Phone")).classes("text-lg font-bold")
            ui.label(
                translate_string("Reads the current value of every global variable.  Nothing on the phone is changed."),
            ).classes("text-sm text-gray-500")
            ip_field, port_field = self._address_fields(dialog)
            progress = self._progress_row()

            async def read() -> None:
                ip_address, ip_port = str(ip_field.value or "").strip(), str(port_field.value or "").strip()
                remember_android_address(self.gui, ip_address, ip_port)
                fetched = await self._while_waiting(
                    progress, run.io_bound(livevars.fetch_live_values, ip_address, ip_port)
                )
                if fetched is None:
                    return
                return_code, message, live = fetched
                if return_code != 0 or live is None:
                    ui.notify(message, type="negative", timeout=8000)
                    return
                self.live = live
                dialog.close()
                self.refresh()

            self._dialog_buttons(dialog, translate_string("Get Values"), read)
        dialog.open()

    def _address_fields(self, dialog: ui.dialog) -> tuple[ui.input, ui.input]:
        """The IP address and port boxes, opened on the address last used and kept like every other dialog's."""
        default_ip, default_port = android_address_defaults(self.gui)
        ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full")
        port_field = ui.input(translate_string("Port"), value=default_port).classes("w-full")
        remember_android_address_fields(self.gui, ip_field, port_field, dialog)
        return ip_field, port_field

    @staticmethod
    def _progress_row() -> ui.row:
        """The line that says the phone is being waited on, hidden until it is."""
        row = ui.row().classes("w-full items-center gap-2 mt-3")
        row.set_visibility(False)
        with row:
            ui.spinner(size="sm")
            ui.label(
                translate_string(
                    "Waiting on the Android device -- accept the authorization prompt there if one appears."
                ),
            ).classes("text-sm text-amber-700 dark:text-amber-500")
        return row

    @staticmethod
    async def _while_waiting(progress: ui.row, call: Coroutine[Any, Any, _T]) -> _T:
        """Await a call to the phone with the waiting line showing, and take it down afterwards."""
        progress.set_visibility(True)
        try:
            return await call
        finally:
            progress.set_visibility(False)

    @staticmethod
    def _dialog_buttons(dialog: ui.dialog, label: str, handler: Callable[[], Any]) -> ui.button:
        """Cancel, and the one button that does the dialog's work."""
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            return ui.button(label, on_click=handler).classes("bg-blue-600")

    def push(self) -> None:
        """Send one value for the chosen variable to the phone, and read it back."""
        row = self.chosen
        if row is None:
            return
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(f"{translate_string('Send To Phone')}: {row.name}").classes("text-lg font-bold")
            ui.label(
                translate_string(
                    "Sets this global variable on the Android device to the value below, then reads it back to "
                    "confirm.  This changes the phone, not the file.",
                ),
            ).classes("text-sm text-gray-500")
            value_field = ui.textarea(translate_string("Value"), value=row.value).classes("w-full")
            ip_field, port_field = self._address_fields(dialog)
            progress = self._progress_row()

            async def send() -> None:
                ip_address, ip_port = str(ip_field.value or "").strip(), str(port_field.value or "").strip()
                remember_android_address(self.gui, ip_address, ip_port)
                done = await self._while_waiting(
                    progress,
                    run.io_bound(livevars.set_global, ip_address, ip_port, row.name, str(value_field.value or "")),
                )
                if done is None:
                    return
                return_code, message = done
                ui.notify(message, type="positive" if return_code == 0 else "negative", timeout=8000)
                if return_code == 0:
                    dialog.close()
                    self._remember_pushed(row.name, str(value_field.value or ""), f"{ip_address}:{ip_port}")

            self._dialog_buttons(dialog, translate_string("Send Value"), send)
        dialog.open()

    def delete_from_phone(self) -> None:
        """Remove the ticked variables from the phone itself, one at a time, reading each back.

        Apart from Delete, which changes the file: a variable can be on one and not the other, and which to clear is
        for the person to say.  Nothing is sent until the button in the dialog is pressed.
        """
        rows = list(self.picked)
        if not rows:
            return
        subject = rows[0].name if len(rows) == 1 else f"{len(rows)} {translate_string('global variables')}"
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(translate_string("Delete On Phone") + ": " + subject).classes("text-lg font-bold")
            ui.label(
                translate_string(
                    "Removes these global variables from the Android device, then asks the device whether each is "
                    "gone.  This changes the phone, not the file.",
                ),
            ).classes("text-sm text-gray-500")
            ui.label(
                ", ".join(row.name for row in rows[:_NAMES_SHOWN])
                + (f" ... +{len(rows) - _NAMES_SHOWN}" if len(rows) > _NAMES_SHOWN else "")
            ).classes("text-xs font-mono")
            ip_field, port_field = self._address_fields(dialog)
            progress = self._progress_row()

            async def remove() -> None:
                ip_address, ip_port = str(ip_field.value or "").strip(), str(port_field.value or "").strip()
                remember_android_address(self.gui, ip_address, ip_port)
                gone: list[str] = []
                failures: list[str] = []
                progress.set_visibility(True)
                try:
                    for row in rows:
                        done = await run.io_bound(livevars.delete_global, ip_address, ip_port, row.name)
                        if done is None:
                            return
                        if done[0] == 0:
                            gone.append(row.name)
                        else:
                            failures.append(done[1])
                finally:
                    progress.set_visibility(False)
                self._forget_on_phone(gone, f"{ip_address}:{ip_port}")
                if failures:
                    ui.notify(failures[0], type="negative", timeout=8000)
                if gone:
                    ui.notify(f"{len(gone)} {translate_string('removed from the phone')}.", type="positive")
                if not failures:
                    dialog.close()

            self._dialog_buttons(dialog, translate_string("Delete On Phone"), remove)
        dialog.open()

    def _forget_on_phone(self, names: list[str], address: str) -> None:
        """Show these as not on the phone: each was read back from it, and was not there."""
        if not names:
            return
        if self.live is None:
            self.live = livevars.LiveValues(address=address)
        for name in names:
            self.live.values.pop(name, None)
        self.refresh()

    def _remember_pushed(self, name: str, value: str, address: str) -> None:
        """Show the phone's new value in the table: it was read back, so it is what the phone holds."""
        if self.live is None:
            self.live = livevars.LiveValues(address=address)
        self.live.values[name] = value
        self.refresh()

    # ---------------------------------------------------------------- the changes
    def _plan_dialog(
        self,
        heading: str,
        fields: Callable[[], None],
        make_plan: Callable[[], Plan | None],
        apply_label: str,
    ) -> None:
        """A dialog that previews a change and applies it: the fields, a preview, and Apply that follows the preview."""
        held: dict[str, Any] = {"plan": None}
        with ui.dialog().props("persistent") as dialog, ui.card().classes("w-[700px] max-w-full p-4"):
            ui.label(heading).classes("text-lg font-bold text-blue-600")
            fields()
            summary = ui.label("").classes("text-sm font-bold text-orange-500 mt-2")
            area = ui.scroll_area().classes("w-full h-56 border rounded dark:border-gray-700")

            def preview() -> None:
                plan = make_plan()
                if plan is None:
                    ui.notify(translate_string("Fill in every box first."), type="warning")
                    return
                held["plan"] = plan
                summary.set_text(
                    f"{plan.what} -- "
                    + (translate_string("cannot be done") if plan.is_blocked else translate_string("ready to apply"))
                )
                area.clear()
                with area, ui.column().classes("w-full gap-0 p-2"):
                    for line in maprefac.report_rows(plan)[:_PREVIEW_LINE_LIMIT]:
                        ui.label(line.text).classes("font-mono text-xs whitespace-pre")
                apply_button.set_enabled(plan.can_apply)

            def apply_plan() -> None:
                plan = held["plan"]
                if plan is None:
                    ui.notify(translate_string("Press Preview first."), type="warning")
                    return
                done, errors = maprefac.apply(plan, state=self.state)
                for message in errors[:4]:
                    ui.notify(message, type="negative")
                if not done:
                    return
                ui.notify(f"{plan.what}. {translate_string('Undo is available.')}", type="positive")
                dialog.close()
                self.refresh()

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button(translate_string("Close"), on_click=dialog.close).props("outline")
                ui.button(translate_string("Preview"), on_click=preview).props("outline")
                apply_button = ui.button(apply_label, on_click=apply_plan).classes("bg-blue-600")
                apply_button.set_enabled(False)
        dialog.open()

    def rename(self) -> None:
        """Rename the chosen variable everywhere it is written."""
        row = self.chosen
        if row is None:
            return
        name_field: dict[str, ui.input] = {}

        def fields() -> None:
            name_field["box"] = ui.input(translate_string("New name"), value=row.name).classes("w-full")

        def make_plan() -> Plan | None:
            new_name = str(name_field["box"].value or "").strip()
            if not new_name.lstrip("%"):
                return None
            return mapvars.plan_rename(row.name, new_name, self.state)

        self._plan_dialog(f"{translate_string('Rename')} {row.name}", fields, make_plan, translate_string("Rename"))

    def change_value(self) -> None:
        """Change the value the Variables tab holds for the chosen variable, checked against the type picked."""
        row = self.chosen
        if row is None:
            return
        widgets: dict[str, Any] = {}

        def fields() -> None:
            start = row.value_type if row.value_type in mapvars.CHOOSABLE_TYPES else mapvars.TEXT
            widgets["type"] = ui.select(
                list(mapvars.CHOOSABLE_TYPES), value=start, label=translate_string("Type")
            ).classes("w-48")
            widgets["value"] = ui.textarea(translate_string("Value"), value=row.value).classes("w-full")
            ui.label(
                translate_string(
                    "Tasker keeps every value as text.  The type is a check: Number will not take 'twelve'.",
                ),
            ).classes("text-xs text-gray-500")

        def make_plan() -> Plan | None:
            return mapvars.plan_set_value(
                row.name, str(widgets["value"].value or ""), str(widgets["type"].value), self.state
            )

        self._plan_dialog(
            f"{translate_string('Change Value')}: {row.name}", fields, make_plan, translate_string("Apply")
        )

    def delete(self) -> None:
        """Delete the ticked variables' entries from the Variables tab, all of them as one change."""
        rows = list(self.picked)
        if not rows:
            return

        def fields() -> None:
            ui.label(
                translate_string(
                    "Removes the stored value from the Variables tab.  Actions that use it are left alone."
                ),
            ).classes("text-sm text-gray-500")

        subject = rows[0].name if len(rows) == 1 else f"{len(rows)} {translate_string('global variables')}"
        self._plan_dialog(
            f"{translate_string('Delete')} {subject}",
            fields,
            lambda: mapvars.plan_delete_many([row.name for row in rows], self.state),
            translate_string("Delete"),
        )

    async def save(self) -> None:
        """Write the loaded configuration, with every change made here, to a file."""
        if await self.save_configuration():
            self.refresh()
