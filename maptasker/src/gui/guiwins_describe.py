"""guiwins_describe: the "Draft with AI" row of the TaskerNet Description editor.

mapdescribe does the drafting: it builds the facts, asks the model and makes what comes back safe.  This is the
dialog's half of it -- a button, the question put to the model as a task that can be taken back, and a line saying
plainly what is sent, which can be opened to read in full before anything is.

The draft goes into the editor's own text box and is kept or dropped by the editor's own Ok and Cancel, with one
Undo Draft in between: a draft that replaces what the author wrote must be easy to take back.  What is in the
requirements block is never sent and never rewritten -- it is a list of facts worked out from the file, not prose.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.analysis import mapask
from maptasker.src.core import tndesc
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.mapops import mapdescribe

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.gui.userintr import MyGui

# Said under the button, where the user is looking when they wonder what pressing it does.  The list of what is sent
# is the one at the top of mapdescribe.py, and the box under "What will be sent" shows it for this object.
_WHAT_IS_SENT = (
    "Sends the names of this {kind}'s Profiles, Tasks, Scenes and actions, and what it needs on another phone -- "
    "never an action's settings, a value, a key or a message -- with the description you have written so far, to "
    "the AI model chosen on the Analyze tab.  Nothing is sent until you press Draft with AI.  The draft is put in "
    "the box below, unsaved."
)
_LOCAL = "That model runs on this computer, so nothing leaves it."


class DescribeRow:
    """The button, and the question it asks, for one description editor.

    Held as an object because the question outlives the click that asked it: it is a task that closing the
    dialog has to be able to cancel, and the answer needs the editor's text box to land in.
    """

    def __init__(
        self,
        gui: MyGui,
        kind: str,
        element: Element,
        name: str,
        text: ui.textarea,
        dialog: ui.dialog,
    ) -> None:
        """
        Args:
            gui: The application window, whose Analyze tab says which AI model to ask.
            kind: "Project", "Profile" or "Task".
            element: The working copy the editor is open over, which the facts are read from.
            name: The object's name, "" for one that has none yet.
            text: The editor's description box, which the draft is put into.
            dialog: The editor's dialog, whose closing takes back a question still out.
        """
        self.gui = gui
        self.kind = kind
        self.element = element
        self.name = name
        self.text = text
        self.dialog = dialog
        self.pending: asyncio.Task[mapdescribe.Described] | None = None
        self.before_draft: str | None = None
        self.button: ui.button
        self.stop: ui.button
        self.undo: ui.button
        self.sent: ui.label
        self.progress: ui.label
        self.notes: ui.label

    def build(self) -> None:
        """Draw the row, and have closing the dialog take back a question still out."""
        with ui.column().classes("w-full gap-1 mt-2"):
            with ui.row().classes("w-full items-center gap-2"):
                self.button = ui.button(translate_string("Draft with AI"), icon="auto_awesome", on_click=self.draft)
                self.button.props("outline")
                self.stop = ui.button(translate_string("Stop"), on_click=self.cancel).props("flat dense")
                self.stop.classes("text-red-600")
                self.stop.set_visibility(False)
                self.undo = ui.button(translate_string("Undo Draft"), on_click=self.undo_draft).props("flat dense")
                self.undo.set_visibility(False)
            ui.label(translate_string(_WHAT_IS_SENT.format(kind=self.kind))).classes("text-xs text-gray-500 italic")
            with ui.expansion(translate_string("What will be sent"), icon="visibility").classes(
                "w-full text-xs"
            ) as box:
                self.sent = ui.label("").classes("font-mono text-xs whitespace-pre-wrap break-words")
            # Read when it is opened, not when the dialog is: the Project may have changed behind it, and what is
            # shown has to be what would go.
            box.on_value_change(lambda event: self.refresh_sent() if event.value else None)
            self.progress = ui.label("").classes("text-xs text-gray-600 dark:text-gray-400 italic")
            self.progress.set_visibility(False)
            self.notes = ui.label("").classes(
                "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1 whitespace-pre-line",
            )
            self.notes.set_visibility(False)
        self.dialog.on_value_change(lambda event: None if event.value else self.cancel())

    # ---------------------------------------------------------------- what is sent
    def _facts(self) -> mapdescribe.Facts:
        return mapdescribe.gather(self.kind, self.element, self.name, self.gui.state)

    def _prose(self) -> str:
        """What the author has written, without the requirements block, which is not theirs to have rewritten."""
        return tndesc.split_requirements(str(self.text.value or ""))[0]

    def refresh_sent(self) -> None:
        """Show, word for word, the message that pressing the button would send."""
        _system, user = mapdescribe.build_prompt(self._facts(), self._prose())
        self.sent.set_text(user)

    # ---------------------------------------------------------------- the question
    def cancel(self) -> None:
        """Take back the question the model is working on, if there is one."""
        task = self.pending
        self.pending = None
        if task is not None and not task.done():
            task.cancel()

    async def draft(self) -> None:
        """The button: have the selected model describe this object, and put what survives the check in the box."""
        gui = self.gui
        try:
            settings = mapask.model_settings(getattr(gui, "ai_name", ""), getattr(gui, "ai_model", ""), state=gui.state)
        except mapask.AskError as error:
            ui.notify(str(error), type="warning", multi_line=True)
            return

        facts = self._facts()
        prose = self._prose()
        self._say([])
        self.cancel()  # one question at a time: pressing it again replaces the one still out
        task = asyncio.create_task(mapdescribe.draft_description(facts, prose, settings))
        self.pending = task
        self.button.props(add="loading")
        self._working(True, settings)
        try:
            described = await task
        except asyncio.CancelledError:
            # This handler being cancelled itself is not ours to swallow.
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
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
        # Closed while the model was thinking: there is nowhere left to put it.
        if not self.dialog.value:
            return
        self.show(described)

    def show(self, described: mapdescribe.Described) -> None:
        """Put a finished draft in the box -- keeping the requirements block -- and say what is wrong with it."""
        current = str(self.text.value or "")
        block = tndesc.split_requirements(current)[1]
        self.before_draft = current
        self.text.set_value(f"{described.html}\n\n{block}" if block else described.html)
        self.undo.set_visibility(True)
        self._say(list(described.notes))
        ui.notify(
            translate_string("Drafted.  Read it and change what is wrong; nothing is kept until you press Ok."),
            type="positive",
            multi_line=True,
        )

    def undo_draft(self) -> None:
        """Put back what was in the box before the last draft."""
        if self.before_draft is None:
            return
        self.text.set_value(self.before_draft)
        self.before_draft = None
        self.undo.set_visibility(False)
        self._say([])

    # ---------------------------------------------------------------- showing it
    def _working(self, working: bool, settings: mapask.ModelSettings | None = None) -> None:
        """Show that a question is out, and to whom, or that it no longer is."""
        self.stop.set_visibility(working)
        self.progress.set_visibility(working)
        if working and settings is not None:
            where = translate_string(_LOCAL) if settings.provider == mapask.LLAMA else ""
            self.progress.set_text(
                f"{translate_string('Asking')} {settings.provider} ({settings.model})... "
                f"{translate_string('Press Stop to give up.')} {where}".strip(),
            )

    def _say(self, notes: list[str]) -> None:
        """Show the notes under the row, or hide it if there are none."""
        self.notes.set_text("\n".join(notes))
        self.notes.set_visibility(bool(notes))
