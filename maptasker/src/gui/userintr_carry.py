"""userintr_carry: the Import With Dependencies button's half of the event handlers."""

#! /usr/bin/env python3

#                                                                                        #
# userintr_carry: pick the other backup, read it, and open the dialog that imports from it.   #
#                                                                                        #
# A mixin that MapTaskerEventHandlers inherits, like the report handlers, so the button is wired to   #
# gui.event_handlers.import_with_dependencies_event.  The work is mapcarry's and the dialog is       #
# guiwins_carry's; this is only what neither of them can do -- ask for a file, and hand the dialog    #
# the ways to follow a row, bring the window up to date and save.                                    #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

from nicegui import ui

from maptasker.src.analysis.diffload import load_for_comparison, loaded_file_path
from maptasker.src.core.maputil2 import suppress_logged, translate_string
from maptasker.src.gui.getfile import LocalFilePicker
from maptasker.src.gui.guiutils import refresh_tasker_object_pulldowns
from maptasker.src.gui.guiwins_carry import build_carry_dialog
from maptasker.src.gui.guiwins_nav import go_to_target, opening_view_in_a_new_window
from maptasker.src.gui.userintr_loading import local_xml_start_directory

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.core import mapjump
    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


class CarryEventHandlers:
    """The Import With Dependencies handlers MapTaskerEventHandlers inherits: self.gui is the window."""

    state: RunState
    gui: MyGui

    if TYPE_CHECKING:

        async def wait_for_prebuild(self) -> None:
            """PrebuildEventHandlers's: return when no Map is being built ahead of time."""

        async def save_whole_configuration(self) -> bool:
            """MapTaskerEventHandlers's: write the whole configuration to a new copy and switch to it."""
            raise NotImplementedError

    async def import_with_dependencies_event(self) -> None:
        """Ask which backup to import from, read it, and open the dialog that lists what it holds.

        Rebuilt on every press, for restore_history_event's reason: a preview closes over live elements,
        and holding one across a reopen is the stale-handle case maprefac.apply's attachment check exists
        to catch.
        """
        gui = self.gui
        if not self.state.tasker_root_elements.get("all_tasks") and not self.state.tasker_root_elements.get(
            "all_projects"
        ):
            gui.display_message_box(
                translate_string("No XML file has been loaded.  Get an XML file first."),
                "Red",
            )
            return

        # Reading another file borrows the program's shared tables for a moment (see diffload), which is
        # not something to do under a Map that is being built ahead of time on another thread.
        await self.wait_for_prebuild()

        path = await _choose_file_to_import_from(gui)
        if not path:
            return

        # Never the file already loaded: importing a configuration into itself brings in a copy of whatever is
        # picked, which is Duplicate's job and not a thing anybody means by this.  Said plainly instead.
        loaded = loaded_file_path(state=self.state)
        if loaded and os.path.realpath(path) == os.path.realpath(loaded):
            gui.display_message_box(
                translate_string("That is the file already loaded.  Choose a different one to import from."),
                "Red",
            )
            return

        source, problem = load_for_comparison(path, state=self.state)
        if source is None:
            gui.display_message_box(problem, "Red")
            return

        self._dismiss_carry_dialog()

        def make_jump(target: mapjump.Target) -> Callable[[], Coroutine[Any, Any, None]]:
            """One row's click: open what it names in a window of its own, keeping this one up."""

            async def go() -> None:
                with opening_view_in_a_new_window(self.gui):
                    await go_to_target(self.gui, target)

            return go

        async def refresh_after_apply() -> None:
            """The pulldowns: an import adds whole objects, so an option list built before one is short."""
            refresh_tasker_object_pulldowns(self.gui)

        dialog = build_carry_dialog(
            source,
            make_jump,
            self.import_with_dependencies_event,
            refresh_after_apply,
            self.save_whole_configuration,
            state=self.state,
        )
        if dialog is None:
            return
        self.gui.carry_dialog = dialog
        dialog.open()

    def _dismiss_carry_dialog(self) -> None:
        """Take down the Import With Dependencies dialog if one is still up -- see _dismiss_restore_dialog."""
        dialog = getattr(self.gui, "carry_dialog", None)
        self.gui.carry_dialog = None
        if dialog is not None:
            with suppress_logged("Deleting the Import With Dependencies dialog"):
                dialog.delete()


async def _choose_file_to_import_from(gui: MyGui) -> str:
    """Which backup to import from, or "" if the user backed out.

    The same picker Get Local XML File opens and Compare Files uses, started in the same remembered
    directory.  The ceiling stays at home no matter where it starts, for the reason getxml_event gives.
    Deliberately NOT remember_local_xml_directory: that is where the file being worked ON comes from, and a
    backup picked to import from -- an archive, a download -- should not move it.
    """
    result = await LocalFilePicker(local_xml_start_directory(gui), upper_limit="~", multiple=False)
    if not result:
        ui.notify(translate_string("Import cancelled."), type="warning")
        return ""
    chosen = cast("object", result[0] if isinstance(result, (list, tuple)) else result)
    return str(chosen)
