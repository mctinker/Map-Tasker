"""guiwins_notes: the Notes & Tags window -- the user's own notes and tags on Projects, Profiles and Tasks."""

#! /usr/bin/env python3

#                                                                                       #
# guiwins_notes: draw objnotes's book as a table, and the dialog that adds or changes a   #
#                note.  All the knowledge is in objnotes (what a tag is, what is kept and #
#                where); this is only the drawing and the buttons.                        #
#                                                                                       #
# THE FILTER is here: the tags in use are buttons above the table, and pressing one limits  #
# the table to the objects that carry it (pressing several limits it to those carrying all   #
# of them).  The same tags light up objects in the Diagram (its toolbar), and are written     #
# '#like-this' in the Map, where its search finds them.                                      #
#                                                                                       #
# Nothing here touches the configuration, so none of it is on the Undo list: a note is not     #
# in the backup and is not lost with an edit that is undone.                                  #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.core import objnotes
from maptasker.src.core.dirout import profile_id, task_id
from maptasker.src.core.mapjump import PROFILE, PROJECT, TASK, Target
from maptasker.src.core.maputil2 import translate_string

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from nicegui.events import TableSelectionEventArguments

    from maptasker.src.core.primitem import RunState

# How much of a note one cell of the table shows.
_NOTE_SHOWN = 120


def _kind_words() -> dict[str, str]:
    """What each kind of object is called, in whatever language is on."""
    return {
        PROJECT: translate_string("Project"),
        PROFILE: translate_string("Profile"),
        TASK: translate_string("Task"),
    }


def _shown(text: str) -> str:
    """A note as one short line for a table cell."""
    folded = " ".join(text.split())
    return folded if len(folded) <= _NOTE_SHOWN else f"{folded[: _NOTE_SHOWN - 3]}..."


def build_notes_window(
    make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
    state: RunState,
) -> ui.dialog:
    """Build the Notes & Tags window.

    `make_jump` turns a place into the click that takes the user to it in the Map, and is passed in rather than
    imported, for the reason build_refactor_dialog gives.  Unlike the other windows this one opens with nothing
    loaded: the notes are in a file of their own, and are worth reading and tidying without a backup.
    """
    return NotesWindow(make_jump, state).build()


class NotesWindow:
    """The window: the notes on screen, which are chosen, which tags limit them, and the handlers."""

    def __init__(
        self,
        make_jump: Callable[[Target], Callable[[], Coroutine[Any, Any, None]]],
        state: RunState,
    ) -> None:
        """Remember where to send a click and the run's state, and read the notes."""
        self.make_jump = make_jump
        self.state = state
        self.book = objnotes.load()
        # The tags the table is limited to.
        self.limit: set[str] = set()
        # What the table was last given to show: its own rows, kept here because the table's are untyped.
        self.shown_rows: list[dict[str, Any]] = []
        # The notes ticked in the table.
        self.picked: list[objnotes.Note] = []
        self.dialog: ui.dialog
        self.table: ui.table
        self.summary: ui.label
        self.tag_row: ui.row
        self.buttons: dict[str, ui.button] = {}

    # ---------------------------------------------------------------- drawing
    def build(self) -> ui.dialog:
        """Draw the window and fill the table."""
        with (
            ui.dialog().props("persistent maximized") as self.dialog,
            ui.card().classes("w-full h-full p-4 no-wrap gap-2"),
        ):
            ui.label(translate_string("Notes & Tags")).classes("text-lg font-bold text-blue-600")
            self.summary = ui.label("").classes("text-sm text-gray-600 dark:text-gray-300")

            with ui.row().classes("w-full items-center gap-4"):
                filter_box = ui.input(translate_string("Search")).props("dense clearable").classes("w-64")
                ui.switch(
                    translate_string("Show In Map And Diagram"),
                    value=self.book.show_in_map,
                    on_change=lambda event: self.show_in_map(bool(event.value)),
                )
            self.tag_row = ui.row().classes("w-full items-center gap-1")

            self.table = (
                ui.table(columns=self._columns(), rows=[], row_key="key", selection="multiple", on_select=self.chose)
                .props("dense flat virtual-scroll")
                .classes("w-full")
                # Every spare line of the window, so more rows show on a taller one and the buttons stay at the bottom.
                .style("flex: 1 1 0; min-height: 8rem")
            )
            filter_box.bind_value(self.table, "filter")
            self.table.on("rowDblclick", lambda event: self.edit_row(event.args[1]["key"]))

            with ui.row().classes("w-full items-center gap-2"):
                self._action("add", translate_string("Add"), "add", self.add)
                self._action("edit", translate_string("Edit"), "edit", self.edit)
                self._action("delete", translate_string("Delete"), "delete", self.delete)
                self._action("show", translate_string("Show In Map"), "travel_explore", self.show)
                ui.space()
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")

        if self.book.unreadable:
            ui.notify(translate_string("The notes file could not be read."), type="warning")
        self.refresh()
        return self.dialog

    @staticmethod
    def _columns() -> list[dict[str, Any]]:
        """The table's columns."""

        def column(name: str, label: str) -> dict[str, Any]:
            return {"name": name, "label": label, "field": name, "sortable": True, "align": "left"}

        return [
            column("kind", translate_string("Type")),
            column("name", translate_string("Name")),
            column("tags", translate_string("Tags")),
            column("note", translate_string("Note")),
            column("status", translate_string("Status")),
        ]

    def _action(self, key: str, label: str, icon: str, handler: Callable[[], Any]) -> None:
        """One of the buttons under the table."""
        self.buttons[key] = ui.button(label, icon=icon, on_click=handler)

    # ---------------------------------------------------------------- the table
    @staticmethod
    def _key(note: objnotes.Note) -> str:
        """A row's identity: the kind and the name."""
        return f"{note.kind}|{note.name}"

    def _shown_notes(self) -> list[objnotes.Note]:
        """The notes the table shows: those carrying every tag it is limited to."""
        return self.book.find(tags=sorted(self.limit))

    def refresh(self) -> None:
        """Redraw the tag buttons, the table and the summary from the book, keeping what is ticked if it survives."""
        counts = self.book.tag_counts()
        # A tag no note carries any more cannot limit anything.
        self.limit &= set(counts)
        keep = {self._key(note) for note in self.picked}
        kinds = _kind_words()
        missing = translate_string("Not in this file")
        loaded = bool(self.state.tasker_root_elements.get("all_tasks"))
        notes = self._shown_notes()
        self.shown_rows = [
            {
                "key": self._key(note),
                "kind": kinds[note.kind],
                "name": note.name,
                "tags": note.hashtags,
                "note": _shown(note.text),
                # Said only when a file is open to be not in: with none open, every note would be.
                "status": "" if not loaded or objnotes.in_file(note, self.state) else missing,
            }
            for note in notes
        ]
        self.table.rows = self.shown_rows
        self.table.update()
        self.summary.set_text(
            f"{translate_string('Note')}: {len(self.book.notes)}    {translate_string('Tags')}: {len(counts)}"
        )
        self._draw_tags(counts)
        self.choose_many([note for note in notes if self._key(note) in keep])

    def _draw_tags(self, counts: dict[str, int]) -> None:
        """One button per tag in use; the ones the table is limited to are filled in, the rest outlined."""
        self.tag_row.clear()
        with self.tag_row:
            if not counts:
                return
            all_button = ui.button(translate_string("Show All"), on_click=lambda: self.limit_to(None)).props(
                "dense no-caps",
            )
            if self.limit:
                all_button.props("outline")
            for tag, count in counts.items():
                button = ui.button(
                    f"#{tag}  ({count})", on_click=lambda _event=None, chosen=tag: self.limit_to(chosen)
                ).props(
                    "dense no-caps",
                )
                if tag not in self.limit:
                    button.props("outline")

    def limit_to(self, tag: str | None) -> None:
        """Add this tag to the ones the table is limited to -- or take it off if it is there; None takes them all off."""
        if tag is None:
            self.limit.clear()
        elif tag in self.limit:
            self.limit.discard(tag)
        else:
            self.limit.add(tag)
        self.refresh()

    def chose(self, event: TableSelectionEventArguments) -> None:
        """A row was ticked or unticked in the table: what is ticked now is what the buttons act on."""
        keys = {item["key"] for item in event.selection}
        self.choose_many([note for note in self.book.notes.values() if self._key(note) in keys], sync=False)

    def choose_many(self, notes: list[objnotes.Note], *, sync: bool = True) -> None:
        """Make these the notes the buttons act on, and tick them in the table.

        Delete takes one or more; Edit and Show In Map are about one note and wait for exactly one.
        """
        self.picked = notes
        if sync:
            keys = {self._key(note) for note in notes}
            self.table.selected = [row for row in self.shown_rows if row["key"] in keys]
        one = len(notes) == 1
        self.buttons["edit"].set_enabled(one)
        self.buttons["delete"].set_enabled(bool(notes))
        self.buttons["show"].set_enabled(one and self._target(notes[0]) is not None)

    # ---------------------------------------------------------------- the handlers
    def _persist(self) -> bool:
        """Write the book.  True when it was written; otherwise the reason is on screen."""
        error = objnotes.save(self.book)
        if error:
            ui.notify(error, type="negative")
            return False
        # The Map and Diagram of this run read the notes again the next time they are built.
        objnotes.forget(self.state)
        return True

    def show_in_map(self, shown: bool) -> None:
        """Switch the Map's and the Diagram's showing of the notes on or off; the notes themselves are untouched."""
        self.book.show_in_map = shown
        self._persist()

    def add(self) -> None:
        """Open the dialog to add a note."""
        self._note_dialog(None)

    def edit(self) -> None:
        """Open the dialog to change the chosen note."""
        if len(self.picked) == 1:
            self._note_dialog(self.picked[0])

    def edit_row(self, key: str) -> None:
        """Open the dialog to change the note on the row that was double-clicked."""
        note = next((found for found in self.book.notes.values() if self._key(found) == key), None)
        if note is not None:
            self._note_dialog(note)

    def delete(self) -> None:
        """Ask, and then take the chosen notes away."""
        chosen = list(self.picked)
        if not chosen:
            return
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label(translate_string("Delete the chosen notes?")).classes("font-bold")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
                ui.button(translate_string("Delete"), icon="delete", on_click=lambda: self._deleted(dialog, chosen))
        dialog.open()

    def _deleted(self, dialog: ui.dialog, chosen: list[objnotes.Note]) -> None:
        """The deletion was confirmed."""
        dialog.close()
        for note in chosen:
            self.book.remove(note.kind, note.name)
        if self._persist():
            self.picked = []
            self.refresh()

    def _target(self, note: objnotes.Note) -> Target | None:
        """Where this note's object is in the Map, or None when it is not in the file that is open."""
        if note.kind == PROJECT:
            return Target(PROJECT, note.name, note.name) if objnotes.in_file(note, self.state) else None
        found = (profile_id if note.kind == PROFILE else task_id)(note.name, state=self.state)
        return Target(note.kind, found, note.name) if found else None

    async def show(self) -> None:
        """Take the person to the chosen note's object, in the Map."""
        target = self._target(self.picked[0]) if len(self.picked) == 1 else None
        if target is not None:
            await self.make_jump(target)()

    # ---------------------------------------------------------------- adding and changing
    def _note_dialog(self, existing: objnotes.Note | None) -> None:
        """The dialog that adds a note, or changes `existing`: what it is on, its tags, and what it says."""
        kinds = _kind_words()
        counts = self.book.tag_counts()
        with (
            ui.dialog().props("persistent") as dialog,
            ui.card().classes("gap-2").style("width: 38rem; max-width: 95vw"),
        ):
            ui.label(translate_string("Edit") if existing else translate_string("Add")).classes(
                "text-lg font-bold text-blue-600",
            )
            kind = ui.select(kinds, value=existing.kind if existing else TASK, label=translate_string("Type")).classes(
                "w-full",
            )
            name = (
                ui.select(
                    sorted(objnotes.known_names(kind.value, self.state)),
                    value=existing.name if existing else None,
                    label=translate_string("Name"),
                    with_input=True,
                    new_value_mode="add-unique",
                )
                .props("use-input hide-selected fill-input input-debounce=0 stack-label")
                .classes("w-full")
            )
            kind.on_value_change(lambda event: self._offer_names(name, str(event.value)))
            tags = ui.input(translate_string("Tags"), value=" ".join(existing.tags) if existing else "").classes(
                "w-full"
            )
            ui.label(translate_string("Separate tags with spaces or commas.")).classes("text-xs text-gray-500")
            if counts:
                with ui.row().classes("w-full gap-1"):
                    for tag in counts:
                        ui.button(
                            f"#{tag}",
                            on_click=lambda _event=None, chosen=tag: tags.set_value(
                                self._with_tag(str(tags.value or ""), chosen)
                            ),
                        ).props("dense flat no-caps size=sm")
            text = (
                ui.textarea(translate_string("Note"), value=existing.text if existing else "")
                .props(f"autogrow maxlength={objnotes.MAX_NOTE_LENGTH}")
                .classes("w-full")
            )
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
                ui.button(
                    translate_string("Save"),
                    icon="save",
                    on_click=lambda: self._keep(
                        dialog,
                        existing,
                        str(kind.value),
                        str(name.value or ""),
                        str(tags.value or ""),
                        str(text.value or ""),
                    ),
                )
        dialog.open()

    def _offer_names(self, field: ui.select, kind: str) -> None:
        """Offer the names of the objects of this kind in the open file for the dialog's Name field."""
        field.options = sorted(objnotes.known_names(kind, self.state))
        field.update()

    @staticmethod
    def _with_tag(typed: str, tag: str) -> str:
        """The typed tags with this one added, unless it is there already."""
        present = objnotes.parse_tags(typed)
        return " ".join([*present, tag]) if tag not in present else " ".join(present)

    def _keep(
        self, dialog: ui.dialog, existing: objnotes.Note | None, kind: str, name: str, tags: str, text: str
    ) -> None:
        """Save what the dialog holds: put the note on its object, moving it off the object it was on if that changed."""
        name = name.strip()
        if not name:
            ui.notify(translate_string("Choose the object this note is on."), type="warning")
            return
        target = (kind, name)
        if (existing is None or existing.key != target) and target in self.book.notes:
            ui.notify(translate_string("That object already has a note.  Edit that one instead."), type="warning")
            return
        try:
            moved = existing is not None and existing.key != target
            self.book.put(objnotes.Note(kind, name, text, objnotes.parse_tags(tags)))
        except ValueError as error:
            ui.notify(str(error), type="warning")
            return
        if moved and existing is not None:
            self.book.remove(*existing.key)
        if self._persist():
            dialog.close()
            ui.notify(translate_string("Saved.  Build the Map or Diagram again to show it."), type="positive")
            self.picked = []
            self.refresh()
