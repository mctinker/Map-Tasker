"""guiwins_carry: the Import With Dependencies dialog -- bring something in from another backup, with what it needs."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_carry: where mapcarry hangs off the GUI.                                       #
#                                                                                        #
# The other backup has already been read when this opens (see userintr_carry), so the dialog's   #
# first act is to list what is in it: every Project, Profile, Task and Scene, filtered by kind   #
# and by what is typed.  A row's "Preview" plans the import against the configuration as it is   #
# NOW and draws it; Apply makes that plan and no other, and is only there while the preview is.  #
#                                                                                        #
# THE RULE THIS IS BUILT AROUND is the Refactor and Restore dialogs': nothing is applied unseen.  #
# The preview is maprefac.report_rows -- the same rows they draw -- so a refusal, a warning and  #
# a list of steps read exactly as theirs do.  Where the import is to go, and whether the global   #
# variables it uses are brought too, are chosen above the preview, and changing either takes the   #
# preview away: a plan describes one choice of them.                                              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from nicegui import ui

from maptasker.src.core.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui.guiwins_restore import draw_preview, tip
from maptasker.src.mapops import mapcarry, maprefac_model

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from maptasker.src.analysis.xmldiff import Configuration
    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

    # How a row's click is made: given the place a row names, the handler that opens it.
    MakeJump = Callable[[Target], Callable[[], Coroutine[Any, Any, None]]]
    # Something the window does for the dialog, off the dialog's own business.
    WindowAction = Callable[[], Coroutine[Any, Any, None]]
    # Saving the configuration, which says whether it did.
    SaveAction = Callable[[], Coroutine[Any, Any, bool]]

# How many rows are drawn.  A file of a thousand Tasks has more than anyone scrolls; the filter is how
# to find the rest, and the dialog says so rather than silently cutting the list.
_ROW_LIMIT = 150

# The toggle above the list: the word shown, and the kind it selects ("" is all of them).
_FILTERS = {
    "": "All",
    PROJECT: "Projects",
    PROFILE: "Profiles",
    TASK: "Tasks",
    SCENE: "Scenes",
}

# What each kind is called on its row.
_TAGS = {PROJECT: "PROJECT", PROFILE: "PROFILE", TASK: "TASK", SCENE: "SCENE"}

# The one destination that is not a Project of this file.
_NEW_PROJECT_LABEL = "A new Project"

_BLURB = (
    "Bring a Project, Profile, Task or Scene in from another backup together with everything it needs: the "
    "Tasks it performs, the Scenes it shows and the Tasks those run, and the global variables they use.  "
    "Press 'Preview' on a row to see exactly what would be copied, renamed and left alone before anything "
    "happens.  Nothing already in this file is changed, and the whole import is one press of Undo."
)


@dataclass
class _Held:
    """What the dialog is holding: the other file, what is typed, the plan on screen.

    One object rather than a nest of closures' locals, because every handler reads and writes it -- and
    because the plan on screen is only valid for the choices it was planned with, which is what `plan`
    living beside them makes plain.
    """

    source: Configuration
    picks: list[mapcarry.Pick] = field(default_factory=list[mapcarry.Pick])
    kind: str = ""
    text: str = ""
    into: str = mapcarry.NEW_PROJECT
    carry_variables: bool = True
    plan: maprefac_model.Plan | None = None
    previewed: mapcarry.Pick | None = None
    applied: set[tuple[str, str]] = field(default_factory=set[tuple[str, str]])


def build_carry_dialog(
    source: Configuration,
    make_jump: MakeJump,
    choose_another: WindowAction,
    refresh_after_apply: WindowAction,
    save_configuration: SaveAction,
    state: RunState,
) -> ui.dialog | None:
    """Build and return the Import With Dependencies dialog, or None if there is nothing to import into or from.

    Takes what it needs from the window and nothing else, for guiwins_restore's reason: this module is
    reached FROM guiwins, and reaching back into it would be a circular import.
    """
    if not state.tasker_root_elements.get("all_tasks") and not state.tasker_root_elements.get("all_projects"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None

    held = _Held(source=source, picks=mapcarry.picks(source))
    if not held.picks:
        ui.notify(
            f"{os.path.basename(source.path)} {translate_string('has no Projects, Profiles, Tasks or Scenes to bring in.')}",
            type="warning",
        )
        return None

    return _CarryDialog(held, make_jump, choose_another, refresh_after_apply, save_configuration, state).build()


class _CarryDialog:
    """The Import With Dependencies dialog: its widgets, and the handlers that work on them."""

    def __init__(
        self,
        held: _Held,
        make_jump: MakeJump,
        choose_another: WindowAction,
        refresh_after_apply: WindowAction,
        save_configuration: SaveAction,
        state: RunState,
    ) -> None:
        """
        Args:
            held: What the dialog is holding, which starts out as the other file's picks.
            make_jump: How to follow a row to the object it names in this file.
            choose_another: How to pick a different file to import from.
            refresh_after_apply: How to bring the rest of the window up to date once something has changed.
            save_configuration: How to write the configuration to a file.
            state: The run's state.
        """
        self.held = held
        self.make_jump = make_jump
        self.choose_another = choose_another
        self.refresh_after_apply = refresh_after_apply
        self.save_configuration = save_configuration
        self.state = state
        self.dialog: ui.dialog
        self.summary: ui.label
        self.list_area: ui.scroll_area
        self.destination: ui.select
        self.preview_heading: ui.label
        self.preview_area: ui.scroll_area
        self.apply_button: ui.button

    def build(self) -> ui.dialog:
        """Draw the dialog and the first list."""
        # `persistent`, by the Refactor and Restore dialogs' rule: a dialog holding a preview leaves on a
        # button and nothing else.  The pulldown makes it acute -- Quasar renders a select's popup outside
        # the card, so the click that picks a Project would otherwise be the click that closes the dialog.
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[1000px] max-w-full p-6"):
            ui.label(translate_string("Import With Dependencies")).classes("text-lg font-bold text-blue-600")
            ui.label(translate_string(_BLURB)).classes("text-xs text-gray-500 italic mb-2 mt-1")
            self._build_source_row()
            self._build_filter_row()
            self.summary = ui.label("").classes("text-sm font-bold text-orange-500 mt-2")
            self.list_area = ui.scroll_area().classes(
                "w-full h-[28vh] min-h-[110px] border rounded dark:border-gray-700 mt-1"
            )
            self._build_destination_row()
            self.preview_heading = ui.label("").classes("text-sm font-bold text-blue-600 mt-3")
            self.preview_area = ui.scroll_area().classes(
                "w-full h-[26vh] min-h-[110px] border rounded dark:border-gray-700 mt-1"
            )
            self._build_buttons()
        self.draw_list()
        return self.dialog

    def _build_source_row(self) -> None:
        """Which file this is importing from, and the button to change it."""
        with ui.row().classes("w-full items-center gap-2"):
            ui.label(translate_string("Importing from")).classes("text-sm text-gray-500")
            ui.label(self.held.source.path).classes("text-sm font-mono break-all flex-1 min-w-0")
            tip(
                ui.button(translate_string("Choose another file..."), on_click=self.change_file).props("outline dense"),
                "Pick a different backup to import from.  This window closes and opens again on that file.",
            )

    def _build_filter_row(self) -> None:
        """The kind toggle and the search box."""
        with ui.row().classes("w-full items-center gap-4 mt-2"):
            ui.toggle(
                {kind: translate_string(label) for kind, label in _FILTERS.items()},
                value=self.held.kind,
                on_change=lambda event: self.set_filter(kind=event.value),
            ).props("dense no-caps")
            ui.input(
                label=translate_string("Find by name"),
                on_change=lambda event: self.set_filter(text=event.value or ""),
            ).props("dense clearable").classes("flex-1")

    def _build_destination_row(self) -> None:
        """Where it goes in this file, and whether the global variables come too."""
        projects = mapcarry_projects(self.state)
        options = {mapcarry.NEW_PROJECT: translate_string(_NEW_PROJECT_LABEL), **{name: name for name in projects}}
        with ui.row().classes("w-full items-center gap-4 mt-2"):
            self.destination = ui.select(
                options,
                value=mapcarry.NEW_PROJECT,
                label=translate_string("Put a Task, Profile or Scene in"),
                on_change=lambda event: self.set_destination(event.value),
            ).classes("w-[320px]")
            tip(
                self.destination,
                "Where the Tasks, Profiles and Scenes brought in are listed.  'A new Project' makes one, named for "
                "the Project they were in; a Project that is imported always gets one of its own.",
            )
            tip(
                ui.checkbox(
                    translate_string("Bring the global variables this file lacks"),
                    value=True,
                    on_change=lambda event: self.set_carry_variables(bool(event.value)),
                ).props("dense"),
                "A global variable the objects use that this file has no value for is added with the other "
                "file's value.  One this file already has keeps its own value, whatever this says.",
            )

    def _build_buttons(self) -> None:
        """The row along the bottom: Apply, Cancel Preview, Save To Current File and Close."""
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            self.apply_button = ui.button(translate_string("Apply"), on_click=self.do_apply).classes("px-4")
            self.apply_button.props("color=orange")
            self.apply_button.disable()
            tip(
                self.apply_button,
                "Make the import the preview describes, and nothing else.\n\n"
                "Greyed out until a row's 'Preview' has drawn a preview that can be applied.\n\n"
                "One press of Undo afterwards puts the configuration back as it is now.\n\n",
            )
            ui.button(translate_string("Cancel Preview"), on_click=self.clear_preview).props("outline")
            tip(
                ui.button(translate_string("Save To Current File"), color="green", on_click=self.do_save).classes(
                    "text-white px-4",
                ),
                "Write the whole configuration -- what you have imported and every other edit made this session "
                "-- to a new, timestamped copy of the file you loaded.  The file you loaded is never written "
                "to.\n\nUntil you press this, an import exists only in memory and is lost on exit.\n\n",
            )
            ui.button(translate_string("Close"), on_click=self.dialog.close).props("color=red").classes(
                "text-white px-4",
            )

    # ----------------------------------------------------------------------------
    # What is typed and chosen.  Each of these takes the preview away: a plan describes one choice.
    # ----------------------------------------------------------------------------
    def set_filter(self, *, kind: str | None = None, text: str | None = None) -> None:
        """The kind toggle or the search box changed: list again."""
        if kind is not None:
            self.held.kind = kind
        if text is not None:
            self.held.text = text
        self.draw_list()

    def set_destination(self, into: str) -> None:
        self.held.into = into or mapcarry.NEW_PROJECT
        self.clear_preview()

    def set_carry_variables(self, value: bool) -> None:
        self.held.carry_variables = value
        self.clear_preview()

    async def change_file(self) -> None:
        """Close this and open the dialog again on another file."""
        self.dialog.close()
        await self.choose_another()

    # ----------------------------------------------------------------------------
    # The list.
    # ----------------------------------------------------------------------------
    def matching(self) -> list[mapcarry.Pick]:
        """The picks the toggle and the search box let through."""
        held = self.held
        needle = held.text.strip().lower()
        return [
            pick
            for pick in held.picks
            if (not held.kind or pick.kind == held.kind) and (not needle or needle in pick.label.lower())
        ]

    def draw_list(self) -> None:
        """Draw the rows that match, each with a button that previews its import."""
        shown = self.matching()
        self.summary.set_text(
            f"{len(shown)} {translate_string('of')} {len(self.held.picks)} {translate_string('offered')}"
        )
        self.list_area.clear()
        with self.list_area, ui.column().classes("w-full gap-0 p-1"):
            for pick in shown[:_ROW_LIMIT]:
                self._draw_row(pick)
            if len(shown) > _ROW_LIMIT:
                ui.label(
                    f"...{len(shown) - _ROW_LIMIT} {translate_string('more.  Choose a kind or type part of a name to narrow the list.')}",
                ).classes("text-xs text-gray-500 italic mt-2")
            if not shown:
                ui.label(translate_string("Nothing matches.")).classes("text-sm text-gray-500 italic p-2")

    def _draw_row(self, pick: mapcarry.Pick) -> None:
        """One pick: its kind, its name, and 'Preview'."""
        done = (pick.kind, pick.key) in self.held.applied
        with ui.row().classes("w-full items-center gap-2 border-b dark:border-gray-700 py-1 px-2 no-wrap"):
            ui.label(_TAGS[pick.kind]).classes("font-mono text-xs font-bold text-orange-500 shrink-0 w-[70px]")
            ui.label(pick.label).classes("font-mono text-sm break-all flex-1 min-w-0")
            button = ui.button(translate_string("Preview"), on_click=lambda: self.show_preview(pick)).classes(
                "shrink-0"
            )
            button.props("dense color=green" if done else "dense outline")

    # ----------------------------------------------------------------------------
    # The preview, and Apply.
    # ----------------------------------------------------------------------------
    def clear_preview(self) -> None:
        """Throw the preview away and take Apply with it -- the Refactor dialog's one rule."""
        self.held.plan = None
        self.held.previewed = None
        self.preview_heading.set_text("")
        self.preview_area.clear()
        self.apply_button.disable()

    def show_preview(self, pick: mapcarry.Pick) -> None:
        """Plan one pick's import against the configuration as it is NOW, and draw it.

        Planned at the click, not when the list was drawn: another dialog can have edited since, and every
        check the plan makes -- is the name taken, is the Project here -- is only true for a moment.
        """
        held = self.held
        plan = mapcarry.plan_carry(
            held.source, pick.kind, pick.key, held.into, carry_variables=held.carry_variables, state=self.state
        )
        held.plan = plan
        held.previewed = pick
        self.preview_heading.set_text(translate_string("Preview -- nothing has changed yet"))
        draw_preview(self.preview_area, plan, self.make_jump)
        if plan.can_apply:
            self.apply_button.enable()
        else:
            self.apply_button.disable()

    async def do_apply(self) -> None:
        """Apply exactly the plan on screen.  One press of Undo takes it back."""
        held = self.held
        plan = held.plan
        if plan is None:
            ui.notify(translate_string("Press 'Preview' on a row first."), type="warning")
            return
        done, errors = mapcarry.carry(plan, state=self.state)
        for message in errors[:4]:
            ui.notify(message, type="negative")
        if not done:
            return
        if held.previewed is not None:
            held.applied.add((held.previewed.kind, held.previewed.key))
        ui.notify(f"{plan.what}.  {translate_string('Undo is available.')}", type="positive", position="top")
        await self.refresh_after_apply()
        self.clear_preview()
        self._refresh_destinations()
        self.draw_list()

    def _refresh_destinations(self) -> None:
        """The destination list again: an import can have made a Project, and the next one may want to go in it."""
        projects = mapcarry_projects(self.state)
        options = {mapcarry.NEW_PROJECT: translate_string(_NEW_PROJECT_LABEL), **{name: name for name in projects}}
        cast("Any", self.destination).set_options(options)

    async def do_save(self) -> None:
        """Write the whole configuration to a timestamped copy -- see guiwins_restore's own.

        The switch to the saved copy reloads the whole configuration, so the preview (which holds
        elements of the one before) is taken away and the Projects offered are read again.
        """
        if await self.save_configuration():
            self.clear_preview()
            self._refresh_destinations()


def mapcarry_projects(state: RunState) -> list[str]:
    """The Projects of the open file, sorted -- where an import can be filed."""
    return sorted(state.tasker_root_elements.get("all_projects", {}), key=str.lower)
