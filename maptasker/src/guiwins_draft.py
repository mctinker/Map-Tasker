"""The "Draft with AI" row of the Add Task dialog: a description in plain words, drafted into actions.

mapdraft does the drafting -- the model is shown the actions this tool can build and the
arguments they have, and what it proposes is checked before any of it is used.  This is the
dialog's half of it: a box and a button, the question put to the model as a task that can be
taken back, and the draft handed to the dialog's own working copy of the Task.

The draft is NOT saved.  It goes into the same EditableTask the picker adds to, shows in the
same list, and is kept or dropped by the dialog's own Ok and Cancel -- which is what makes it
safe to ask for one and look.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import mapask, mapdraft, taskedit, taskedit_model
from maptasker.src.maputil2 import translate_string

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.userintr import MyGui


class DraftRow:
    """A description box and a button that drafts a Task into an Add Task dialog.

    Held as an object because the question outlives the click that asked it: it is a task
    that closing the dialog has to be able to cancel, and the answer needs the dialog's
    Task, its Name field and its list of actions to land in.
    """

    def __init__(
        self,
        gui: MyGui,
        edited_task: taskedit_model.EditableTask,
        field_refs: dict,
        dialog: ui.dialog,
        on_drafted: Callable[[int | None], None],
    ) -> None:
        """
        Args:
            gui: The application window, whose Analyze tab says which AI model to ask.
            edited_task: The dialog's working copy of the Task, which the draft is added to.
            field_refs: The dialog's widgets by key; "name" is filled in from the draft if empty.
            dialog: The dialog this row is in.
            on_drafted: Called with the act_number of the first drafted action once they are in the
                Task, to redraw the list -- see _NewTaskActionList.on_added.
        """
        self.gui = gui
        self.edited_task = edited_task
        self.field_refs = field_refs
        self.dialog = dialog
        self.on_drafted = on_drafted
        self.pending: asyncio.Task | None = None
        self.description: ui.input
        self.button: ui.button
        self.stop: ui.button
        self.progress: ui.label
        self.notes: ui.label

    def build(self) -> None:
        """Draw the row, and have closing the dialog take back a question still out."""
        # Alongside the picker rather than in place of it: the draft is a starting point,
        # and the picker is how it is finished.  Said under the box, where the user is
        # looking when they wonder whether pressing it will change anything.
        with ui.row().classes("w-full items-center gap-2 mt-2"):
            self.description = (
                ui.input(
                    label=translate_string("Draft with AI"),
                    placeholder=translate_string("e.g. flash 'Hello' if %WIFI is on"),
                )
                .classes("flex-1")
                .props("dense clearable")
            )
            self.button = ui.button(translate_string("Draft")).classes("bg-blue-600 text-white px-4")
            # Only while a question is out: the way to give up on a slow model without closing the dialog.
            self.stop = ui.button(translate_string("Stop")).props("flat dense").classes("text-red-600")
            self.stop.set_visibility(False)
        ui.label(
            translate_string(
                "The AI model chosen on the Analyze tab drafts actions from the ones this editor can build. "
                "They are added below, unsaved, for you to review and edit.",
            ),
        ).classes("text-xs text-gray-500 italic")
        # Said while the model works, since a slow one looks no different from a stuck one.
        self.progress = ui.label("").classes("text-xs text-gray-600 dark:text-gray-400 italic")
        self.progress.set_visibility(False)
        # What the model proposed that could not be used, or could not say.  On screen for as
        # long as the draft is, since it qualifies it: a Task quietly missing half of what was
        # asked for looks exactly like a complete one.
        self.notes = ui.label("").classes(
            "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1 whitespace-pre-line",
        )
        self.notes.set_visibility(False)

        self.button.on_click(self.draft)
        self.stop.on_click(self.cancel)
        self.description.on("keydown.enter", self.draft)
        # The box's own 'X' takes the request back, and so does closing the dialog.
        self.description.on("clear", self.cancel)
        self.dialog.on_value_change(lambda event: None if event.value else self.cancel())

    def cancel(self) -> None:
        """Take back the question the model is working on, if there is one.

        Cancelling the task drops the request where it waits (see mapask) rather than letting
        it run on to a reply that has nowhere left to go.
        """
        task = self.pending
        self.pending = None
        if task is not None and not task.done():
            task.cancel()

    async def draft(self) -> None:
        """The Draft button: have the selected model propose actions, and add what survives the check."""
        description = (self.description.value or "").strip()
        if not description:
            ui.notify(translate_string("Describe the Task first."), type="warning")
            return
        gui = self.gui
        try:
            settings = mapask.model_settings(getattr(gui, "ai_name", ""), getattr(gui, "ai_model", ""), state=gui.state)
        except mapask.AskError as error:
            ui.notify(str(error), type="warning", multi_line=True)
            return

        self.notes.set_visibility(False)
        # One question at a time: pressing Draft again replaces the one still out.
        self.cancel()
        task = asyncio.create_task(mapdraft.draft_task(description, settings, gui.state))
        self.pending = task
        self.button.props(add="loading")
        self._working(True, settings)
        try:
            draft = await task
        except asyncio.CancelledError:
            # This handler being cancelled itself is not ours to swallow.
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
            # Taken back, or replaced by a newer question.  A dialog that has closed has
            # nowhere left to say so.
            if self.dialog.value:
                ui.notify(translate_string("The request to the AI model was cancelled."), type="info")
            return
        except mapask.AskError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        finally:
            if self.pending is task:
                self.pending = None
            self.button.props(remove="loading")
            self._working(False)
        # Closed while the model was thinking: there is nothing left to draft into.
        if not self.dialog.value:
            return
        self.show(draft)

    def show(self, draft: mapdraft.Draft) -> None:
        """Put a finished draft into the dialog and say what was left out of it."""
        notes = self._left_out(draft)
        if draft.is_empty:
            self._say(notes)
            ui.notify(
                translate_string(
                    "Nothing could be drafted from that.  Try describing what the Task should do, step by step.",
                ),
                type="warning",
                multi_line=True,
            )
            return

        applied = mapdraft.apply_draft(self.edited_task, draft, self.gui.state)
        notes += list(applied.notes)
        self._fill_name(draft.name, notes)
        self.on_drafted(applied.first_act_number)
        self._say(notes)
        ui.notify(
            f"{translate_string('Drafted')} {applied.added} {translate_string('actions')}.  "
            f"{translate_string('Nothing is saved until you press Ok.')}",
            type="positive",
            multi_line=True,
        )

    def _working(self, working: bool, settings: mapask.ModelSettings | None = None) -> None:
        """Show that a question is out, and to whom, or that it no longer is."""
        self.stop.set_visibility(working)
        self.progress.set_visibility(working)
        if working and settings is not None:
            self.progress.set_text(
                f"{translate_string('Asking')} {settings.provider} ({settings.model})... "
                f"{translate_string('A larger model is usually faster and better at this. Press Stop to give up.')}",
            )

    def _fill_name(self, suggested: str, notes: list[str]) -> None:
        """Offer the draft's name for the Task -- unless there is already one, or it is taken."""
        name_field = self.field_refs.get("name")
        if not suggested or name_field is None or (name_field.value or "").strip():
            return
        if taskedit.task_name_exists(suggested, state=self.gui.state):
            notes.append(f"{translate_string('Not used as the name, as a Task has it already')}: {suggested}")
            return
        name_field.value = suggested

    def _left_out(self, draft: mapdraft.Draft) -> list[str]:
        """What the model offered that could not be used, in the words the dialog says them in."""
        notes = []
        if draft.unknown:
            notes.append(
                f"{translate_string('Left out, as this editor cannot build it')}: {', '.join(draft.unknown)}",
            )
        notes += [translate_string(note) for note in draft.adjusted]
        notes += list(draft.dropped)
        if draft.unexpressed:
            notes.append(f"{translate_string('Not expressible as actions')}: {draft.unexpressed}")
        return notes

    def _say(self, notes: list[str]) -> None:
        """Show the notes under the row, or hide it if there are none."""
        self.notes.set_text("\n".join(notes))
        self.notes.set_visibility(bool(notes))
