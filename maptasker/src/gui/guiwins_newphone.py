"""guiwins_newphone: the New-Phone Checklist window -- what is left to set up after restoring a backup, with ticks."""

#! /usr/bin/env python3

#                                                                                          #
# guiwins_newphone: where mapops.newphone hangs off the GUI.                                  #
#                                                                                          #
# One list, in the order a phone is set up in: the plugins and apps to install, the special    #
# access to grant (with the commands ready to copy), the global variables to type back in (with   #
# their values), and the Profiles to switch on.  Every line has a tick-box, and the ticks are       #
# saved as they are made, so closing the window, closing MapTasker or fetching the phone's app      #
# list again leaves them where they were.                                                         #
#                                                                                          #
# The plugins and apps are crossed with the app list fetched from the phone picked at the top        #
# (the one fetched last, to start with); the ones it does not have are flagged.  Nothing is           #
# fetched from here: the list comes from the 'App not listed?' fetch the editors have, and the       #
# window says so when there is none.                                                              #
#                                                                                          #
# Nothing here changes the configuration, so none of it is on the Undo list.                        #
#                                                                                          #
# MIT License   Refer to https://opensource.org/license/mit                                 #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core.mapjump import LINK_CLICK_JS
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import newphone

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

_NO_PHONE = ""  # the select's value for "do not check the plugins and apps against any phone"
_HEADING_CLASSES = "mt-3 font-bold text-blue-600"
_DETAIL_CLASSES = "text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap pl-8"
_CODE_CLASSES = "font-mono text-xs break-all"


def build_new_phone_window(
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
    state: RunState,
) -> ui.dialog:
    """Build the New-Phone Checklist window.

    `make_jump` turns a place into the click that takes the user to it in the Map, and is passed in rather than
    imported, for the reason build_refactor_dialog gives.
    """
    return NewPhoneWindow(make_jump, state).build()


def _title(kind: str) -> str:
    """A group's heading, in the language in use.  Spelled out so the translation tooling can see each one."""
    if kind == newphone.PLUGINS:
        return translate_string("Plugins to install")
    if kind == newphone.APPS:
        return translate_string("Apps to install")
    if kind == newphone.ACCESS:
        return translate_string("Special access to grant")
    if kind == newphone.VARIABLES:
        return translate_string("Global variables to enter")
    return translate_string("Profiles to enable")


def _empty(kind: str) -> str:
    """What to say under a heading with nothing in it."""
    if kind == newphone.PLUGINS:
        return translate_string("No plugins are used.")
    if kind == newphone.APPS:
        return translate_string("No apps are named.")
    if kind == newphone.ACCESS:
        return translate_string("No special access found.")
    if kind == newphone.VARIABLES:
        return translate_string("No global variable holds a value.")
    return translate_string("No Profile is switched on.")


def _copy(text: str) -> None:
    """Put text on the clipboard and say so."""
    ui.clipboard.write(text)
    ui.notify(translate_string("Copied."), type="positive")


class NewPhoneWindow:
    """The window: the phone checked against, the list drawn for it, the ticks and the handlers."""

    def __init__(
        self,
        make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
        state: RunState,
    ) -> None:
        """Read the saved ticks, and build the list against the phone whose app list was fetched last."""
        self.make_jump = make_jump
        self.state = state
        self.book = newphone.load_ticks()
        self.device = newphone.default_device()
        self.show_values = True
        self.only_left = False
        self.checklist = newphone.build(state, self.device)
        self.dialog: ui.dialog
        self.body: ui.column
        self.progress: ui.label
        self.headings: dict[str, ui.label] = {}

    # ---------------------------------------------------------------- drawing
    def build(self) -> ui.dialog:
        """Draw the window and fill the list."""
        with (
            ui.dialog().props("persistent maximized") as self.dialog,
            ui.card().classes("w-full h-full p-4 no-wrap gap-2"),
        ):
            ui.label(translate_string("New-Phone Checklist")).classes("text-lg font-bold text-blue-600")
            ui.label(self._subtitle()).classes("text-sm text-gray-600 dark:text-gray-300")
            if self.book.unreadable:
                ui.label(translate_string("The saved ticks could not be read, so they start again.")).classes(
                    "text-sm text-red-600",
                )
            with ui.row().classes("w-full items-center gap-4"):
                phones = {_NO_PHONE: translate_string("None"), **{device: device for device in newphone.devices()}}
                ui.select(
                    phones,
                    value=self.device,
                    label=translate_string("Check plugins and apps against"),
                    on_change=lambda event: self.pick(str(event.value or "")),
                ).classes("w-72").props("dense")
                ui.switch(
                    translate_string("Show values"),
                    value=True,
                    on_change=lambda event: self.set_show_values(bool(event.value)),
                )
                ui.switch(
                    translate_string("Only what is left"),
                    value=False,
                    on_change=lambda event: self.set_only_left(bool(event.value)),
                )
                self.progress = ui.label().classes("font-bold")
            with ui.scroll_area().classes("w-full").style("flex: 1 1 0; min-height: 8rem"):
                self.body = ui.column().classes("w-full gap-0 p-2")
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(translate_string("Copy as text"), on_click=self.copy_text).props("outline")
                ui.button(translate_string("Save Report"), on_click=self.save_report).props("outline")
                ui.button(translate_string("Clear ticks"), on_click=self.clear_ticks).props("outline")
                ui.space()
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")
        self.draw()
        return self.dialog

    def _subtitle(self) -> str:
        """The line under the title: what is being set up from, and what the plugins and apps were checked against."""
        if not self.state.backup_loaded:
            return translate_string("No XML file has been loaded.  Get an XML file first.")
        if not newphone.devices():
            return translate_string(
                "No app list has been fetched from the new phone, so plugins and apps are not checked.  "
                "Fetch one with 'App not listed?' in a Task or Profile editor.",
            )
        return translate_string(
            "Tick each thing off as it is done.  The ticks are saved, so you can stop and come back.",
        )

    def draw(self) -> None:
        """Draw every group, with a tick-box on each line."""
        self.body.clear()
        self.headings = {}
        with self.body:
            for group in self.checklist.groups:
                self.headings[group.kind] = ui.label().classes(_HEADING_CLASSES)
                if not group.items:
                    ui.label(_empty(group.kind)).classes("text-sm italic text-gray-500")
                for item in group.items:
                    if not (self.only_left and item.key in self.book.keys):
                        self._draw_item(item)
        self.update_counts()

    def _draw_item(self, item: newphone.Item) -> None:
        """One line: its tick-box and flag, then what it is for, the commands to copy and the value to enter."""
        with ui.row().classes("w-full items-center gap-2 mt-1"):
            ui.checkbox(
                item.text,
                value=item.key in self.book.keys,
                on_change=lambda event, key=item.key: self.tick(key, bool(event.value)),
            ).classes("font-semibold")
            if item.status == newphone.MISSING:
                ui.badge(translate_string("Not on the phone"), color="red")
            elif item.status == newphone.HAVE:
                ui.badge(translate_string("On the phone"), color="green")
            if item.target is not None:
                ui.link(translate_string("Show in Map"), "#").on(
                    "click",
                    self.make_jump(item.target),
                    js_handler=LINK_CLICK_JS,
                ).classes("text-xs text-blue-600 dark:text-blue-400 decoration-dotted hover:underline")
        if item.detail:
            ui.label(item.detail).classes(_DETAIL_CLASSES)
        for command in item.commands:
            with ui.row().classes("items-center gap-1 pl-8"):
                ui.label(command).classes(_CODE_CLASSES)
                ui.button(icon="content_copy", on_click=lambda _event, text=command: _copy(text)).props(
                    "flat dense size=sm"
                )
        if item.value:
            with ui.row().classes("items-center gap-1 pl-8"):
                shown = item.value if self.show_values else "•" * 8
                ui.label(f"{translate_string('Value')}: {shown}").classes(_CODE_CLASSES)
                ui.button(icon="content_copy", on_click=lambda _event, text=item.value: _copy(text)).props(
                    "flat dense size=sm",
                )

    def update_counts(self) -> None:
        """Redraw the heading counts and the total after a tick."""
        for group in self.checklist.groups:
            heading = self.headings.get(group.kind)
            if heading is not None:
                ticked = sum(1 for item in group.items if item.key in self.book.keys)
                heading.set_text(f"{_title(group.kind)} ({ticked}/{len(group.items)})")
        done, total = self.checklist.counts(self.book.keys)
        self.progress.set_text(f"{done}/{total} {translate_string('done')}")

    # ---------------------------------------------------------------- handlers
    def tick(self, key: str, ticked: bool) -> None:
        """A box was ticked or cleared: remember it, at once."""
        if ticked:
            self.book.keys.add(key)
        else:
            self.book.keys.discard(key)
        error = newphone.save_ticks(self.book)
        if error:
            ui.notify(f"{translate_string('The ticks could not be saved')}: {error}", type="negative")
        self.update_counts()

    def pick(self, device: str) -> None:
        """A different phone was picked: cross the plugins and apps with its app list and redraw."""
        self.device = device
        self.checklist = newphone.build(self.state, device)
        self.draw()

    def set_show_values(self, show: bool) -> None:
        """Show or hide the variables' values."""
        self.show_values = show
        self.draw()

    def set_only_left(self, only_left: bool) -> None:
        """Show everything, or only what has not been ticked."""
        self.only_left = only_left
        self.draw()

    def clear_ticks(self) -> None:
        """Forget every tick, to start the next phone."""
        self.book.keys.clear()
        error = newphone.save_ticks(self.book)
        if error:
            ui.notify(f"{translate_string('The ticks could not be saved')}: {error}", type="negative")
        self.draw()

    def copy_text(self) -> None:
        """Put the checklist on the clipboard as text."""
        _copy(newphone.as_text(self.checklist, self.book.keys, self.show_values))

    def save_report(self) -> None:
        """Write the checklist as a text report, and say where it went."""
        file_path = newphone.write_report(self.checklist, self.book.keys, self.show_values, self.state)
        if file_path:
            ui.notify(f"{translate_string('Report saved as')} {file_path}", type="positive")
        else:
            ui.notify(translate_string("The report could not be saved."), type="negative")
