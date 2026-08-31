"""GUI Window Classes and Definitions (NiceGUI Version)"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import copy
import html
import itertools
import json
import os
import re
import weakref
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to serialize, never to parse
from typing import TYPE_CHECKING

from nicegui import Event, app, context, run, ui

from maptasker.src import (
    deviceinv,
    diagintr,
    mapfind,
    mapjump,
    mapswap,
    profedit,
    projedit,
    sceneedit,
    sceneview,
    sessundo,
    taskedit,
    varxref,
)
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import EDIT_SCENE
from maptasker.src.format import css_color
from maptasker.src.guiutil2 import get_font_choices, sort_languages_with_priority
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    DIAGRAM_FILE,
    DIAGRAM_PROFILES_PER_LINE,
    NOTIFY_TIMEOUT_DEFAULT,
    SCENE_TASK_TYPES,
    VIEW_LIMIT_DEFAULT,
    logger,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    import defusedxml.ElementTree
    from nicegui.elements.select import Select

    from maptasker.src.userintr import MyGui


# The mode the GUI opens in.  Single source of truth for the three things that have to agree
# about it: NiceGUI's dark-mode controller, the "Dark Mode" switch's initial position, and
# self.dark_mode (which views read to colour themselves before the switch is ever clicked).
# They did not agree before -- the switch came up reading "dark" over a light page -- because
# the switch's initial value never fires its on_change handler.  See initialize_screen().
STARTUP_DARK_MODE = False

# ==========================================
# How long a notification stays up.
#
# ui.notify takes a `timeout` in milliseconds -- it is not in the signature, but NiceGUI
# merges **kwargs straight into the options it hands Quasar, so any Quasar Notify option
# works.  0 is Quasar's "stays until dismissed".
#
# The setting is applied by wrapping ui.notify once rather than by touching the 162 call
# sites that would otherwise each have to pass it.  That is a monkeypatch, and the honest
# argument for it is that the alternative is 162 edits to express one default -- and that
# every one of them would have to be found again the next time someone adds a notification.
# Wrapping puts the default at the seam where a default belongs, and leaves the call sites
# saying only what is unusual about them.
#
# A call that passes its own timeout keeps it.  That is not politeness to existing code: the
# reference warnings on Scene delete and rename run to 8-10 seconds *because* they list Task
# names the user has to read, and collapsing those to a global default would make the one
# notification that must be read the first to vanish.
# ==========================================
# The choices offered, as (label, milliseconds).  A pulldown rather than a number box: the
# only values that mean anything here are "long enough to read" and "don't take it away", and
# a free field invites 250ms.
NOTIFY_TIMEOUT_CHOICES: tuple[tuple[str, int], ...] = (
    ("1/2 second", 500),
    ("1 second", 1000),
    ("2 seconds", 2000),
    ("5 seconds", 5000),
    ("10 seconds", 10000),
    ("30 seconds", 30000),
    ("Until dismissed", 0),
)
# Mutable so the pulldown can change it live; read at notify time, not at install time.
_NOTIFY_TIMEOUT = {"ms": NOTIFY_TIMEOUT_DEFAULT}
_NOTIFY_WRAPPED = False


def set_notification_timeout(milliseconds: int) -> None:
    """Set how long a notification stays up from now on, in milliseconds (0 = until
    dismissed).  Takes effect on the next notification; nothing already on screen moves.
    """
    _NOTIFY_TIMEOUT["ms"] = max(0, int(milliseconds))


def install_notification_timeout() -> None:
    """Wrap ui.notify so every notification honours the user's chosen duration.

    Idempotent, and it has to be: this is called from GUI start-up, which a "Reset Settings"
    can run through again, and wrapping a wrapper would stack another closure on every pass.

    Only ui.notify is covered.  A ui.notification object has its own lifecycle and an
    'ongoing' notification is indefinite by design; neither is touched, which is right --
    an ongoing notification that timed out would be a progress indicator that lied.
    """
    global _NOTIFY_WRAPPED  # noqa: PLW0603
    if _NOTIFY_WRAPPED:
        return

    original = ui.notify

    def notify(message: object, **kwargs: object) -> None:
        kwargs.setdefault("timeout", _NOTIFY_TIMEOUT["ms"])
        if not kwargs["timeout"]:
            # "Until dismissed" with no way to dismiss it is a notification that covers the
            # window forever, so the close button comes with the choice rather than being a
            # second thing to remember.
            kwargs.setdefault("close_button", True)
        original(message, **kwargs)

    ui.notify = notify
    _NOTIFY_WRAPPED = True


# ==========================================
# 2. DIALOGS & POPUPS
#
# Every dialog that holds work in progress or asks for a decision is built with Quasar's
# `persistent` prop, which is what stops it closing when the backdrop is clicked or Esc is
# pressed: it leaves on a button and nothing else.  Without it a stray click anywhere outside
# an Add or Edit dialog silently discarded everything typed into it, with no warning and no
# undo -- and the bigger the dialog, the more of the screen is a mine.  The Cancel button is
# still there and still discards; the point is that discarding is now something the user
# chose rather than something that happened to them.
#
# Read-only dialogs deliberately do NOT carry it -- create_popup_window's message box, the
# search results view, the colour picker.  Nothing is lost by dismissing those, and making a
# message you have finished reading demand a button press is just friction.
# ==========================================
# The whole of the markup a popup message may carry, for `rich=True` below.
#
# Deliberately NOT Markdown, even though ui.markdown() is right there.  The help text is
# built out of lines that begin with "* " as bullets and carries paths like
# 'MapTasker_Backups' (userhelp.py); Markdown would turn the first into list items and the
# second into an italic run, and -- the reason that matters most here -- it re-flows text,
# which would undo the leading indentation whitespace-pre-wrap exists to preserve.
#
# So the markers are DOUBLED, which is what keeps them clear of the help text's own single
# "*" bullets, and the conversion is this one pass and nothing else.  A run may not cross a
# line break: an unclosed "**" then spoils at most its own line rather than swallowing the
# rest of the screen as bold.
RICH_TEXT_MARKUP = (
    (re.compile(r"\*\*([^\n]+?)\*\*"), r"<b>\1</b>"),
    (re.compile(r"__([^\n]+?)__"), r"<i>\1</i>"),
)


def rich_text_to_html(message: str) -> str:
    """Escape `message`, then turn its **bold** and __italic__ markers into HTML.

    The escape is not optional and has to come first.  The help screen has the fetched
    changelog appended to it (userintr.query_event) and that is text off the network -- it
    reaches the browser as characters to draw, never as markup to run.  Escaping first also
    means the markers are the only markup that can survive, so help text that says "<b>"
    displays "<b>".
    """
    html_text = html.escape(message)
    for pattern, replacement in RICH_TEXT_MARKUP:
        html_text = pattern.sub(replacement, html_text)
    return html_text


def create_popup_window(title: str, message: str = "", close_button: bool = False, rich: bool = False) -> ui.dialog:
    """Creates a modal dialog. Replaces PopupWindow and CTkToplevel.

    Modified to expand width constraints allowing long text arrays
    and log data streams more horizontal breathing room.
    """
    # CHANGED: Increased max-w-[500px] to max-w-[800px] (or use w-[700px] / w-full)
    with ui.dialog() as dialog, ui.card().classes("min-w-[400px] max-w-[800px] w-full items-center p-6"):
        ui.label(title).classes("text-xl font-bold text-blue-600 text-center")
        if message:
            # The 'w-full' ensures the text block utilizes 100% of the wider card frame
            text_classes = "mt-2 text-left whitespace-pre-wrap break-words w-full text-base"
            # ui.html only where the caller asked for it: every other message goes through
            # ui.label, which cannot render markup at all, so a message that happens to
            # contain "**" or "<" is still drawn exactly as it reads.
            if rich:
                # ui.html(rich_text_to_html(message)).classes(text_classes)
                ui.markdown(message).classes(text_classes)
            else:
                ui.label(message).classes(text_classes)
        if close_button:
            ui.button(translate_string("Close"), on_click=dialog.close).classes("mt-6 bg-red-500 text-white w-full")

    dialog.open()
    return dialog


# ==========================================
# 2b. "CHANGES PENDING"
#
# The one indicator the four Edit dialogs -- Project, Profile, Task and Scene -- share: a
# line that appears as soon as the item has been changed, and is gone again once there is
# nothing left to save.
#
# WHY IT IS A COMPARISON AND NOT A FLAG.  The obvious build is a boolean every handler that
# changes something sets, and it would have started lying within a week, because a change
# reaches these dialogs by three completely different routes:  through widget values that
# are only read at save time (an action's arguments, a condition's fields, a Scene's
# dimensions); through handlers that hit the working copy the moment they run (Add/Copy/
# Move/Delete Action, Add/Delete Condition, Link/Unlink Task, the Enabled toggles, Rename);
# and -- in a Scene -- through a Preview window that goes on dragging elements about while
# this dialog is closed.  That is dozens of separate places, across guiwins.py and
# userintr.py, each of which would have to remember to set the flag, and the first one that
# forgot would leave the message off after a real edit.
#
# So the dialog remembers what it opened with and keeps asking whether it still matches:
# the edited element, serialized, plus the value of every field widget the dialog registered
# in field_refs.  Nothing has to announce a change, so nothing can fail to -- an edit made
# anywhere reaches the message by the same route as an edit made anywhere else.
#
# It only ever errs one way, and that is the way to err: it can say there is something to
# save when what is left of the edit is trivial, and it cannot say there is nothing to save
# when there is.  Typing a field back to what it was does take the message down again, which
# a flag could not do -- but undoing by *button* often will not, because the undo is not a
# byte-for-byte one: flipping a Project's Enabled switch off and back on restamps its
# <mdate> (projedit.touch_project_mdate), and a Profile's leaves <limit> at the end of the
# element rather than where it started.  The message stays up in both cases, correctly:
# saving really would write a different file than the one that was loaded.
#
# WHAT COUNTS AS SAVED.  The message is measured against the state the dialog opened with,
# not against the file, so a change that was applied to the loaded backup the moment it was
# made -- a Rename, an Enabled toggle -- still counts as pending: it is in memory and not in
# any file, and the buttons that put it in one are the ones this message is pointing at.
# Every Ok/Save/Export path closes its dialog on success and so takes the message with it;
# the ones that fail deliberately leave the dialog open, and the message with it, because
# there is still something unsaved.
# ==========================================
# How often an open Edit dialog re-checks itself, in seconds.  Comfortably faster than anyone
# can notice the message is missing, and each check is one Project/Profile/Task/Scene element
# serialized -- not the backup, and not the Map.
PENDING_CHANGES_POLL_SECONDS = 1.0

# field_refs keys that say where a save GOES rather than what is being saved.  Typing a
# different export path is not an edit to the item -- there would be nothing for Cancel to
# discard -- so it must not raise the message.  Every other key in field_refs is content.
PENDING_CHANGES_IGNORED_FIELDS: frozenset[str] = frozenset(
    {"save_path", "project_save_path", "scene_save_path"},
)


def editor_state(
    element: defusedxml.ElementTree.Element,
    field_refs: dict,
    *extra: object,
) -> tuple:
    """Everything about an Edit dialog that a change could show up in, as one comparable
    value -- see the section comment above for what this is for.

    `element` is the working copy the dialog edits (never the live tree's), which is where
    every immediately-applied change lands, and `field_refs` the dialog's own widget table,
    which is where the rest of them wait until a save reads it.  Read afresh on every call
    rather than held: field_refs is rebuilt from scratch by the Task and Profile dialogs'
    render passes, and a Scene's element is re-pointed at the live one once it is applied.

    `extra` is for state that is neither -- pass anything a dialog keeps outside its element
    and its widgets, already reduced to something comparable (the Version 2 Scene designer's
    decoded layout and the Legacy designer's queued element renames are the only two; see
    build_edit_scene_dialog).

    Entries in field_refs that aren't widgets are skipped, not guessed at: the Scene dialog
    parks its designers' callback tables in there too, and those are not values a user typed.
    """
    return (
        ETW.tostring(element),
        tuple(
            (key, str(field_refs[key].value))
            for key in sorted(field_refs)
            if key not in PENDING_CHANGES_IGNORED_FIELDS and hasattr(field_refs[key], "value")
        ),
        *extra,
    )


# How much of a Replace preview's non-list matter is drawn before it is summarized.  A
# rename of a variable a plugin produces can skip hundreds of places for the same reason,
# and a list of hundreds of identical explanations pushes the changes off the screen --
# which is the half the user has to read.
_REPLACE_SKIP_LIMIT = 20

# Errors from one apply are notifications, and a notification per failed site would bury
# the screen.  The rest are in the log; this is the "something went wrong, and here is the
# shape of it" cap.
_REPLACE_ERROR_LIMIT = 5


class PendingChangesBanner:
    """The "Changes Pending" line itself: built hidden, wherever the dialog wants it, then
    told what to watch once the dialog's body is finished -- see watch().

    Two calls rather than one because the two happen at different times.  Where the message
    belongs is above the button row, but what counts as "unchanged" cannot be read until
    everything below it has been built, since building is what fills field_refs.
    """

    def __init__(self) -> None:
        """Initialize pending changes banner, but do not start watching yet -- see watch()."""
        with ui.row().classes("w-full items-center gap-2 mt-2") as self.row:
            ui.icon("pending_actions").classes("text-orange-600")
            ui.label(translate_string("Changes Pending")).classes("text-sm font-bold text-orange-600")
            ui.label(
                translate_string("Nothing is saved until you press Ok, Save or Export."),
            ).classes("text-xs text-gray-500 italic")
        self.row.visible = False

    def watch(self, dialog: ui.dialog, state: Callable[[], object]) -> None:
        """Start watching `state`, which is whatever editor_state() says about this dialog.

        Call it once the dialog's body is fully built: what `state` returns at that moment is
        the "unchanged" everything afterwards is measured against.
        """
        opened_as = state()

        def refresh() -> None:
            # A NiceGUI dialog is hidden rather than destroyed, so this timer outlives the
            # dialog being closed, and a closed dialog has no message to show.  Skipping is
            # right where cancelling would not be: Preview closes the Edit Scene dialog to
            # get at the screen behind it and re-opens that same dialog afterwards (see
            # suspended_scene_editor), and what was dragged about in the preview meanwhile
            # is exactly what this has to report when it comes back.
            if dialog.value:
                # Assigning the value it already has is a no-op in NiceGUI -- a bindable
                # property drops an unchanged set before it reaches the client -- so this
                # sends nothing over the wire on the ticks where nothing has changed.
                self.row.visible = state() != opened_as

        ui.timer(PENDING_CHANGES_POLL_SECONDS, refresh)


# ==========================================
# 2c. SESSION UNDO
#
# The drawer's Undo/Redo pair and the history behind them.  What they act on lives in
# sessundo.py; this is only the three controls, and the one thing they have to get right is
# never offering an Undo that would not do anything -- see _refresh below.
# ==========================================
# How often the Undo/Redo buttons re-read whether there is anything to undo.
#
# Polled rather than pushed, for the same reason "Changes Pending" is a comparison rather
# than a flag (see section 2b): an edit reaches the history from eighteen mutators across
# four modules, several of them nested inside each other, and each one of those would have
# to remember to refresh these buttons.  Asking sessundo four times a second costs two list
# lookups and cannot be forgotten.
UNDO_BUTTONS_POLL_SECONDS = 0.25


def build_edit_history_dialog() -> None:
    """Lists what the session's Undo would step back through, most recent first.

    Read-only, and deliberately so.  Jumping straight to an arbitrary point in the list is
    the obvious next feature and is not this one: every entry is a whole configuration, so
    "go back four steps" would silently discard three edits that are not on screen.  Undo,
    one press at a time, keeps the user looking at what each press actually did.
    """
    entries = sessundo.history()

    with ui.dialog() as history_dialog, ui.card().classes("min-w-[420px] max-w-[680px] w-full p-6"):
        ui.label(translate_string("Edit History")).classes("text-lg font-bold")
        ui.label(
            translate_string(
                "Changes made to the loaded XML this session, newest first.  Undo steps back "
                "through them one at a time.  Nothing here has been written to a file.",
            ),
        ).classes("text-xs text-gray-500")

        if not entries:
            ui.label(translate_string("Nothing has been changed yet.")).classes("mt-3 italic text-gray-500")
        else:
            with ui.column().classes("w-full gap-0 mt-3 max-h-80 overflow-auto"):
                for position, (label, when) in enumerate(entries, start=1):
                    with ui.row().classes("w-full items-baseline gap-2 py-1 border-b"):
                        # The next press of Undo takes the first one back, which is worth
                        # saying outright -- the list is otherwise just a list.
                        ui.label("<" if position == 1 else f"{position}.").classes(
                            "text-xs font-mono text-gray-400 w-8 shrink-0",
                        )
                        ui.label(label).classes("text-sm grow break-all")
                        ui.label(when.strftime("%H:%M:%S")).classes("text-xs font-mono text-gray-400 shrink-0")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Close"), on_click=history_dialog.close).props("outline")

    history_dialog.open()


def _create_undo_section(self: MyGui) -> None:
    """The Undo/Redo pair and the Edit History button, in the 'Specific Name' tab's
    Editing group -- alongside the Edit/Add buttons whose work they take back.

    Undo lives out here rather than in the Edit dialogs because what it takes back is not
    one dialog's business: deleting a Project reaches its Profiles and their Tasks, and the
    dialog that started it is closed by the time the user wants it back.  It is also why
    these are safe to press from here -- a NiceGUI dialog covers the page while it is
    open, so an Undo cannot land underneath an editor still holding the elements it would
    replace.
    """
    with ui.row().classes("w-full justify-center gap-2 gap-y-0 mt-0"):
        self.undo_edit_button = ui.button(
            translate_string("Undo"),
            icon="undo",
            on_click=self.event_handlers.undo_edit_event,
        ).classes("bg-blue-500")
        self.redo_edit_button = ui.button(
            translate_string("Redo"),
            icon="redo",
            on_click=self.event_handlers.redo_edit_event,
        ).classes("bg-blue-500")
    with self.undo_edit_button:
        ui.tooltip(
            translate_string(
                "Take back the last change made to the loaded XML -- an edit, an Add, a "
                "Delete or a Rename, in any of the Edit panels.\n\nThis changes what is "
                "loaded, not any file: nothing on disk or on the Android device is touched.",
            ),
        ).style("white-space: pre-wrap")

    # What the next press would do.  A button that says only "Undo" is a button most people
    # will not press, because they cannot tell what they are about to lose.
    self.undo_next_label = ui.label().classes("w-full text-xs text-gray-500 italic text-center")

    self.edit_history_button = ui.button(
        translate_string("Edit History"),
        color="teal",
        icon="history",
        on_click=build_edit_history_dialog,
    ).classes("w-full justify-center")
    with self.edit_history_button:
        ui.tooltip(
            translate_string(
                "List every change made to the loaded XML this session, newest first.",
            ),
        ).style("white-space: pre-wrap")

    def _refresh() -> None:
        # Assigning a value a NiceGUI element already has is dropped before it reaches the
        # client, so the ticks where nothing has changed send nothing over the wire -- the
        # same property "Changes Pending" leans on.
        self.undo_edit_button.set_enabled(sessundo.can_undo())
        self.redo_edit_button.set_enabled(sessundo.can_redo())
        if next_undo := sessundo.next_undo_label():
            self.undo_next_label.text = f"{translate_string('Undo')}: {next_undo}"
        elif next_redo := sessundo.next_redo_label():
            self.undo_next_label.text = f"{translate_string('Redo')}: {next_redo}"
        else:
            self.undo_next_label.text = translate_string("No changes to undo.")

    _refresh()
    ui.timer(UNDO_BUTTONS_POLL_SECONDS, _refresh)


def _refresh_position_options(
    edited_task: taskedit.EditableTask,
    position_select: ui.select,
    position_labels: dict[str, int | None],
) -> None:
    """Rebuilds an Add/Edit Task dialog's "Position" dropdown from the task's
    current actions -- called after every Add/Copy/Move/Delete/Remove, since
    act_numbers and names shift and stale labels would insert at the wrong
    spot. Keeps the user's current choice if it still exists, else falls back
    to "At the End". position_labels maps each label to the act_number to
    insert at (None for "At the End") -- see build_edit_task_dialog's note on
    why that map is kept out-of-band.
    """
    position_labels.clear()
    options = []
    for action in edited_task.actions:
        before_label = f"Before {action.act_number}: {action.action_name}"
        after_label = f"After {action.act_number}: {action.action_name}"
        position_labels[before_label] = action.act_number
        position_labels[after_label] = action.act_number + 1
        options.extend((before_label, after_label))
    options.append("At the End")
    position_labels["At the End"] = None
    previous = position_select.value
    position_select.set_options(options, value=previous if previous in options else "At the End")


def _action_indent_spaces(self: MyGui) -> int:
    """The user's "If/Then/Else Indentation Amount" setting as an int (default
    4) -- the same amount the Map view indents If blocks by. Restored settings
    can hold it as a string, hence the coercion.
    """
    try:
        return int(getattr(self, "indent", 4) or 4)
    except (TypeError, ValueError):
        return 4


def _dropdown_current_label(arg: taskedit.EditableArg) -> str:
    """The option to preselect for a dropdown arg: current_value is the index
    into dropdown_options (If Operator, Int lookups -- every dropdown in this
    codebase).
    """
    options = arg.dropdown_options or []
    try:
        return options[int(arg.current_value)]
    except (ValueError, IndexError):
        return options[0] if options else ""


def _render_task_name_field(
    _self: MyGui,
    _action: taskedit.EditableAction,
    arg: taskedit.EditableArg,
    key: str,
    field_refs: dict,
) -> None:
    """Renders the 'Perform Task' action's Name field: an ordinary text input
    the user can key any string into, plus a companion "Pick a Task" dropdown
    that -- when an option is chosen -- overwrites the text input with that
    Task's name. Either/or: whichever the user touches last is what's saved,
    since Save only ever reads the text input's own field_refs entry (this
    dropdown is deliberately never added to field_refs, so _task_arg_values
    can't see it).

    A plain ui.select with Quasar's "new-value-mode" was tried first so a
    single widget could both pick and free-type, but it only accepts a typed
    value when the user presses Enter -- clicking away (the far more likely
    action) silently reverts the field to its first option, which is exactly
    the "grabs the first task" bug this two-widget design avoids entirely.
    """
    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")

    task_names = taskedit.get_all_task_names()
    if not task_names:
        return

    def fill_in_picked_task(e: ui.event) -> None:
        if e.value:
            field_refs[key].value = e.value

    ui.select(
        task_names,
        label=translate_string("Pick a Task"),
        with_input=True,
        on_change=fill_in_picked_task,
    ).classes("flex-1").props("dense").tooltip(translate_string("Pick a Task which will be called by this action."))


# How many rows either pick-from-the-inventory dialog draws at once.  A real backup
# harvests ~50 Applications and ~140 icons (see deviceinv.py), but a large configuration
# holds more, and the list is rebuilt on every keystroke of the search box -- the same
# reasoning behind _ICON_PREVIEW_LIMIT, which the Scene designer's own picker uses.
_PICKER_ROW_LIMIT = 200


def _picker_search_input(on_change: Callable[[str], None], placeholder: str) -> ui.input:
    """The search box both pickers below open with."""
    search_input = (
        ui
        .input(placeholder=translate_string(placeholder), on_change=lambda e: on_change(str(e.value or "")))
        .props("outlined dense clearable autofocus")
        .classes("w-full mt-2")
    )
    with search_input.add_slot("prepend"):
        ui.icon("search")
    return search_input


async def _build_fetch_apps_dialog(gui: MyGui, on_fetched: Callable[[], None], for_icons: bool = False) -> None:
    """Ask an Android device for the full list of installed Applications.

    Offered from inside the Application pickers rather than from the sidebar, because
    inside them is where the gap is felt: the list holds what this configuration already
    names, and the moment a user notices the app they want is missing is the moment they
    are looking at it.

    Prompts for the device the same way every other Save To Android does
    (build_save_to_android_dialog), defaults from the same remembered address, and writes
    the address back on success so the next one is pre-filled.

    The fetch itself installs a helper Task on the device, runs it, and waits for the file
    it writes -- seconds, not milliseconds -- so it goes through run.io_bound and the
    button says what it is doing while it happens.  See deviceinv.fetch_apps_from_device.

    for_icons says the user came here wanting icons rather than Applications, which changes
    what this says and nothing about what it does.  It is the same fetch either way: an
    app's own icon is its package plus its launcher activity, so the Application list is an
    icon list too (deviceinv._merged_with_device_icons).  Saying so is the point -- a dialog
    headed "Fetch Applications" in answer to "there are no icons" looks like the wrong
    button, and the two kinds of icon the fetch cannot bring back have to be said out loud
    rather than left to be discovered in the picker afterwards.

    Deliberately does NOT pre-flight with guiutils.ping_android_device, which every other
    Android dialog here does.  That probe used to be disqualifying -- it was a GET on the
    'maplist' route, served by the 'MapTasker List' TaskerNet profile rather than by the
    HTTP Server Example project, so a user who had the server running but had never
    imported that profile failed it despite needing nothing it tested.  The probe no longer
    depends on that profile (nothing does), but skipping it is still the better answer
    here: this fetch's own first step is a GET /api/auth against the very API it goes on to
    use, which is both the right thing to test and the thing whose failure message is worth
    showing.
    """
    default_ip = getattr(gui, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(gui, "android_port", "") or "1821"

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[460px] p-6"):
        title = "Fetch Icons From Android Device" if for_icons else "Fetch Applications From Android Device"
        ui.label(translate_string(title)).classes("text-lg font-bold text-blue-600")
        if for_icons:
            ui.label(
                translate_string(
                    "Icons come from the same place Applications do: Tasker identifies an application's "
                    "own icon by its package and launcher activity, so every application found on the "
                    "device becomes an icon you can pick.\n\n"
                    "Tasker's own built-in icons cannot be fetched -- they live inside Tasker itself -- "
                    "and neither can the icons inside an icon pack, which have to be typed by name.",
                ),
            ).classes("text-sm text-gray-500 italic whitespace-pre-wrap")
        # The Task's name comes from deviceinv rather than being spelled out here: it is
        # versioned, and backing out deviceinv.PAIR_LABELS_ON_DEVICE changes which version
        # gets installed.  A hardcoded name would go on naming the wrong one.
        ui.label(
            translate_string(
                f"MapTasker will install a small Task named '{deviceinv.HELPER_TASK_NAME}' on the device, run "
                "it to list every installed application, and read the answer back.  Tasker must be running, "
                "with the 'HTTP Server Example' project active -- the same requirement 'Save to Android' has.",
            ),
        ).classes("text-sm text-gray-500 italic")
        # The two things that make a working fetch look like a broken one.  Both are said
        # here, before the button is pressed, and again on screen while it runs (see
        # progress_label): a prompt nobody knows to expect is a prompt nobody answers, and a
        # wait nobody was warned about is a wait people give up on.
        ui.label(
            translate_string(
                "Watch your Android device: Tasker will ask you to authorize the connection, and the "
                "fetch cannot go on until you accept.  Allow 30 seconds or more once you have -- longer "
                "on a device with several hundred applications, since each one's name is looked up "
                "individually.",
            ),
        ).classes("text-sm text-amber-700 dark:text-amber-500 mt-2")

        for device, when, count in deviceinv.fetched_devices():
            ui.label(f"{device}: {count} {translate_string('applications, fetched')} {when}").classes(
                "text-xs text-gray-500 mt-1",
            )

        ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full")
        port_field = ui.input(translate_string("Port"), value=default_port).classes("w-full")

        # Hidden until the fetch starts.  The button going grey and saying 'Fetching...' is
        # not enough on its own: what the user has to do next is happening on the phone, not
        # here, and nothing on this screen would otherwise say to go and look at it.
        progress_row = ui.row().classes("w-full items-center gap-2 mt-3")
        progress_row.set_visibility(False)
        with progress_row:
            ui.spinner(size="sm")
            ui.label(
                translate_string(
                    "Waiting on the Android device -- accept the authorization prompt there if one "
                    "appears.  This can take 30 seconds or more.",
                ),
            ).classes("text-sm text-amber-700 dark:text-amber-500")

        async def fetch() -> None:
            ip_address = str(ip_field.value or "").strip()
            ip_port = str(port_field.value or "").strip()

            fetch_button.set_text(translate_string("Fetching..."))
            fetch_button.set_enabled(False)
            progress_row.set_visibility(True)
            try:
                return_code, message = await run.io_bound(deviceinv.fetch_apps_from_device, ip_address, ip_port)
            finally:
                fetch_button.set_text(translate_string("Fetch"))
                fetch_button.set_enabled(True)
                progress_row.set_visibility(False)

            if return_code != 0:
                ui.notify(message, type="negative", timeout=8000)
                return

            # Remembered for next time, same as the Get XML and Save To Android dialogs do.
            gui.android_ipaddr = ip_address
            gui.android_port = ip_port
            ui.notify(message, type="positive", timeout=6000)
            dialog.close()
            on_fetched()

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            fetch_button = ui.button(translate_string("Fetch"), on_click=fetch).classes("bg-blue-600")
            fetch_button.tooltip(
                translate_string("Fetch the full list of installed Applications from the Android device."),
            )

    dialog.open()


def _render_variable_entry(on_variable: Callable[[str], None], button_text: str) -> None:
    """A row for naming a Tasker variable instead of an installed application.

    An <appPkg> is legitimately a variable -- this repo's own backup has eleven of them,
    including '%app_package(%ld_selected_index)' -- and until now the only way to say so was
    to close the picker and type into the field behind it.  The field is still there and
    still works; this just means the picker no longer has to be got out of the way first.

    Validation is deviceinv.is_variable_reference: a leading '%' and something after it, and
    nothing more, since what follows the '%' can be an array index or a function call and is
    Tasker's business rather than this tool's.
    """
    variable_input = ui.input(placeholder=translate_string("%variable_name")).props("outlined dense").classes("flex-1")

    def use_variable() -> None:
        text = str(variable_input.value or "").strip()
        if not deviceinv.is_variable_reference(text):
            ui.notify(
                translate_string("A variable name has to start with '%' -- for example %app_package."),
                type="warning",
            )
            return
        on_variable(text)
        variable_input.set_value("")

    variable_input.on("keydown.enter", use_variable)
    ui.button(translate_string(button_text), on_click=use_variable).props("flat dense color=primary")


def _build_app_picker_dialog(field: ui.input, gui: MyGui) -> None:
    """Pick Applications for a field holding package names.

    Multi-select, rather than the replace-on-click of the Scene designer's icon picker
    (_build_icon_dialog): an <App> argument really can name several apps at once --
    backups in this repo carry <appPkg>com.whatsapp, com.whatsapp.w4b</appPkg> -- so
    "and this one too" is an ordinary thing to want here in a way it is not for one
    component's one icon.

    Whatever is already in the field but not in the inventory -- a package typed by hand,
    a %variable -- is kept, and put back at the front.  The picker is a convenience laid
    over the field, never a replacement for it, so it must not be able to quietly delete a
    value merely because it doesn't recognise it.
    """
    entries = deviceinv.apps()
    known_packages = {entry.pkg for entry in entries}
    current = [token.strip() for token in str(field.value or "").split(",") if token.strip()]
    unknown = [token for token in current if token not in known_packages]
    chosen = {token for token in current if token in known_packages}
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[760px] p-6"):
        ui.label(translate_string("Pick an Application")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string(
                "The Applications named somewhere in the loaded configuration.  Tick every one this "
                "argument should match.  Anything already in the field that isn't listed stays.",
            ),
        ).classes("text-sm text-gray-500 italic")

        # What is in the field but not in the list -- a package typed by hand, or a variable.
        # Shown because 'anything else stays' is a promise the user cannot otherwise check,
        # and because it is the only feedback that adding a variable below took effect.
        unlisted_label = ui.label("").classes("text-xs text-blue-600 mt-1")

        def show_unlisted() -> None:
            unlisted_label.set_text(
                f"{translate_string('Also in this field')}: {', '.join(unknown)}" if unknown else "",
            )

        def toggle(package: str, ticked: bool) -> None:
            if ticked:
                chosen.add(package)
            else:
                chosen.discard(package)

        def render() -> None:
            results.clear()
            text = search["text"].strip().lower()
            visible = [
                entry for entry in entries if not text or text in entry.pkg.lower() or text in entry.label.lower()
            ]
            with results:
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                for entry in visible[:_PICKER_ROW_LIMIT]:
                    ui.checkbox(
                        entry.display,
                        value=entry.pkg in chosen,
                        on_change=lambda e, pkg=entry.pkg: toggle(pkg, bool(e.value)),
                    ).props("dense")
                if len(visible) > _PICKER_ROW_LIMIT:
                    ui.label(
                        f"{translate_string('More matches than can be shown -- narrow the search.')} ({len(visible)})",
                    ).classes("text-xs italic text-gray-500 mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value
            render()

        _picker_search_input(search_changed, "Search Applications")
        results = ui.column().classes("w-full gap-0 mt-2 max-h-96 overflow-auto")
        render()
        show_unlisted()

        def add_variable(name: str) -> None:
            if name not in unknown:
                unknown.append(name)
            show_unlisted()

        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.label(translate_string("Or a Tasker variable:")).classes("text-xs text-gray-500")
            _render_variable_entry(add_variable, "Add")

        def apply_selection() -> None:
            # Inventory order for the picked ones, so the field reads the same way twice
            # running; the unrecognised ones first, where they were.
            field.set_value(", ".join(unknown + [entry.pkg for entry in entries if entry.pkg in chosen]))

        def use_selected() -> None:
            apply_selection()
            dialog.close()

        async def fetch_then_reopen() -> None:
            # The ticks are written into the field before reopening, and the fresh dialog
            # reads its ticks back out of the field -- so a fetch part-way through choosing
            # apps does not throw away what has been chosen so far.
            apply_selection()
            dialog.close()
            await _build_fetch_apps_dialog(gui, lambda: _build_app_picker_dialog(field, gui))

        with ui.row().classes("w-full justify-between items-center gap-2 mt-3"):
            _render_fetch_apps_button(fetch_then_reopen)
            with ui.row().classes("gap-2"):
                ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")
                ui.button(translate_string("Use Selected"), on_click=use_selected).props("color=primary")

    dialog.open()


def _render_fetch_apps_button(on_click: Callable[[], object], for_icons: bool = False) -> None:
    """The 'Not listed?' button the Application and icon pickers carry, in the same place
    in each.

    Worded as the question the user is actually asking at that moment.  A button labelled
    'Fetch' would be answering a question they have not thought to ask yet -- the list in
    front of them looks complete until the one app they want turns out not to be in it.

    The icon wording asks the icon question, but the button does the same thing: see
    _build_fetch_apps_dialog's for_icons.
    """
    fetch_button = ui.button(
        translate_string("Icon not listed?" if for_icons else "App not listed?"),
        icon="cloud_download",
        on_click=on_click,
    ).props("flat dense color=primary")
    with fetch_button:
        ui.tooltip(
            translate_string(
                "Fetch every installed application's own icon from your Android device.  What is "
                "listed now is only the icons this configuration already uses.  Tasker's built-in "
                "icons and the contents of an icon pack cannot be fetched, and are typed by name."
                if for_icons
                else "Fetch the full list of installed applications from your Android device.  "
                "What is listed now is only what this configuration already names.",
            ),
        ).style("white-space: pre-wrap")


def _build_app_entry_picker_dialog(on_pick: Callable[[deviceinv.AppEntry], None], gui: MyGui) -> None:
    """Pick one Application, handing the whole triple to the caller.

    The single-pick sibling of _build_app_picker_dialog, for the Profile App condition,
    whose entries are three separate fields per app (profedit.get_app_entries) rather than
    one comma-joined list -- so what it needs back is the package, the label *and* the
    class, not just a package name to write into a field.  Filling all three is the point:
    that condition's class field is the one nobody can be expected to know by heart.
    """
    entries = deviceinv.apps()
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[760px] p-6"):
        ui.label(translate_string("Pick an Application")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string(
                "The Applications named somewhere in the loaded configuration -- or name a Tasker "
                "variable, which fills the Package and Label fields with it and leaves the Class empty, "
                "the way Tasker writes one.",
            ),
        ).classes("text-sm text-gray-500 italic")

        def pick(entry: deviceinv.AppEntry) -> None:
            on_pick(entry)
            dialog.close()

        def render() -> None:
            results.clear()
            text = search["text"].strip().lower()
            visible = [
                entry for entry in entries if not text or text in entry.pkg.lower() or text in entry.label.lower()
            ]
            with results:
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                for entry in visible[:_PICKER_ROW_LIMIT]:
                    ui.button(
                        entry.display,
                        on_click=lambda _e=None, chosen=entry: pick(chosen),
                    ).props("flat dense no-caps align=left").classes("w-full")

        def search_changed(value: str) -> None:
            search["text"] = value
            render()

        _picker_search_input(search_changed, "Search Applications")
        results = ui.column().classes("w-full gap-0 mt-2 max-h-96 overflow-auto")
        render()

        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.label(translate_string("Or a Tasker variable:")).classes("text-xs text-gray-500")
            _render_variable_entry(lambda name: pick(deviceinv.variable_app_entry(name)), "Use")

        async def fetch_then_reopen() -> None:
            dialog.close()
            await _build_fetch_apps_dialog(gui, lambda: _build_app_entry_picker_dialog(on_pick, gui))

        with ui.row().classes("w-full justify-between items-center mt-3"):
            _render_fetch_apps_button(fetch_then_reopen)
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


def _render_app_entry_pick_button(
    gui: MyGui,
    field_refs: dict,
    pkg_key: str,
    label_key: str,
    cls_key: str,
) -> None:
    """The 'Pick' button beside one App condition entry's Package/Label/Class fields.

    Writes into the three inputs rather than into the condition, exactly like every other
    field in that dialog: Save reads field_refs, so a picked app is staged and cancellable
    on the same terms as a typed one.  Absent entirely when there is nothing to pick from,
    which leaves the three fields precisely as they were before this existed.
    """
    if not deviceinv.have_apps():
        return

    def fill_in(entry: deviceinv.AppEntry) -> None:
        field_refs[pkg_key].value = entry.pkg
        field_refs[label_key].value = entry.label
        field_refs[cls_key].value = entry.cls

    pick_button = ui.button(
        translate_string("Pick"),
        icon="apps",
        on_click=lambda: _build_app_entry_picker_dialog(fill_in, gui),
    ).props("flat dense size=sm")
    with pick_button:
        ui.tooltip(translate_string("Fill all three fields in from the loaded configuration."))


def _build_tasker_icon_picker_dialog(field: ui.input, gui: MyGui) -> None:
    """Pick one icon for a field holding an <Img> reference.

    Replaces what the field holds rather than adding to it -- an action has one icon, so a
    second pick is a correction.  'No icon' is offered explicitly: an empty <Img> is what
    an action whose icon was never set has always carried, and it has to stay reachable
    once a picker exists.
    """
    icons = deviceinv.icons()
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[760px] p-6"):
        ui.label(translate_string("Pick an icon")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string(
                "The icons used somewhere in the loaded configuration, plus every application's own "
                "icon if you have fetched them from your device.  What you pick replaces what the "
                "field holds.  An icon from an icon pack that isn't listed has to be typed: its "
                "names live inside the pack.",
            ),
        ).classes("text-sm text-gray-500 italic")

        def pick(value: str) -> None:
            field.set_value(value)
            dialog.close()

        def render() -> None:
            results.clear()
            text = search["text"].strip().lower()
            visible = [
                icon
                for icon in icons
                if not text or text in icon.display.lower() or text in deviceinv.format_icon_value(icon).lower()
            ]
            with results:
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                for icon in visible[:_PICKER_ROW_LIMIT]:
                    reference = deviceinv.format_icon_value(icon)
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.button(
                            icon.display,
                            on_click=lambda _e=None, value=reference: pick(value),
                        ).props("flat dense no-caps align=left").classes("flex-1")
                        # pr-4 keeps the kind clear of the list's own scrollbar, which
                        # otherwise sits on top of it and clips the word.
                        ui.label(icon.kind).classes("text-xs text-gray-500 w-20 text-right pr-4")
                if len(visible) > _PICKER_ROW_LIMIT:
                    ui.label(
                        f"{translate_string('More matches than can be shown -- narrow the search.')} ({len(visible)})",
                    ).classes("text-xs italic text-gray-500 mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value
            render()

        _picker_search_input(search_changed, "Search icons")
        results = ui.column().classes("w-full gap-0 mt-2 max-h-96 overflow-auto")
        render()

        async def fetch_then_reopen() -> None:
            # Closed and reopened rather than re-rendered in place, exactly as the
            # Application picker does it: the list is read once, at the top of this
            # function, and a fetch is precisely the thing that makes that reading stale.
            dialog.close()
            await _build_fetch_apps_dialog(gui, lambda: _build_tasker_icon_picker_dialog(field, gui), for_icons=True)

        with ui.row().classes("w-full justify-between items-center gap-2 mt-3"):
            _render_fetch_apps_button(fetch_then_reopen, for_icons=True)
            with ui.row().classes("gap-2"):
                ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")
                temp = ui.button(translate_string("No Icon"), on_click=lambda: pick("")).props("flat color=negative")
                temp.tooltip(translate_string("Clear the field, leaving the action with no icon."))

    dialog.open()


def _render_inventory_fetch(gui: MyGui, reason: str, on_fetched: Callable[[], None]) -> None:
    """The fetch button, for the two refusals a fetch from the device can lift.

    'No Applications were found...' and 'No icons were found...' are the only two things
    the editor says no to that the user can do something about without leaving the dialog,
    and one fetch answers both: the Application list the device sends back is also a list
    of app icons (deviceinv._merged_with_device_icons).  Every other refusal is a statement
    about the action itself and gets no button, which is why this is an equality test
    against taskedit's two named constants rather than a guess at the wording.

    on_fetched re-draws whatever showed the refusal.  A fetch bumps deviceinv's generation,
    so a re-draw is enough for the caller that re-asks the question -- see
    taskedit.list_addable_actions' memo, and reclassify_action_args for the callers whose
    models were built before the fetch and have to be rebuilt rather than merely redrawn.
    """
    if reason not in (taskedit.NO_APPS_REASON, taskedit.NO_ICONS_REASON):
        return
    for_icons = reason == taskedit.NO_ICONS_REASON

    async def fetch() -> None:
        await _build_fetch_apps_dialog(gui, on_fetched, for_icons=for_icons)

    _render_fetch_apps_button(fetch, for_icons=for_icons)


def _after_inventory_fetch(redraw: Callable[[], None], action: taskedit.EditableAction) -> Callable[[], None]:
    """What to do once a fetch has filled the inventory: re-ask this action's arguments
    what kind of widget they are, and then draw them again.

    Re-drawing alone would not do it.  A read-only App or Icon field is read-only because
    _classify_arg_widget said so when the model was built, and that answer is kept in the
    EditableArg -- so without the rebuild the field would come back grey, still carrying a
    reason that had just stopped being true.
    """

    def refresh() -> None:
        taskedit.reclassify_action_args(action)
        redraw()

    return refresh


def _after_condition_fetch(
    redraw: Callable[[], None],
    condition: profedit.EditableCondition,
) -> Callable[[], None]:
    """_after_inventory_fetch's counterpart for a Profile State/Event condition's arguments."""

    def refresh() -> None:
        profedit.reclassify_condition_args(condition)
        redraw()

    return refresh


def _render_readonly_note(gui: MyGui, note: str, on_fetched: Callable[[], None]) -> None:
    """The italic note beside an argument that cannot be edited -- and, when the note is one
    of the two a fetch can lift, the fetch beside it.

    This is where 'No icons were found in the loaded configuration to choose from.' is most
    often read: not in the Add Action picker, but on a greyed-out Icon field in an action
    that is already there.  Until now it was a dead end wherever it appeared, and the way
    out existed only inside a picker the empty inventory stopped from opening.
    """
    ui.label(note).classes("text-xs text-gray-500 italic")
    _render_inventory_fetch(gui, note, on_fetched)


def _render_addability_reason(gui: MyGui, reason: str, on_fetched: Callable[[], None]) -> None:
    """Why an action can't be added -- and, for the one reason that has a way out, the way
    out.

    'No Applications were found in the loaded configuration to choose from' and its icon
    counterpart are the refusals a user can do something about without leaving this dialog,
    and until now each was a dead end in the most literal way: with nothing in the
    inventory, 'Launch App' is not addable, so the picker never opens, so the picker's own
    'not listed?' button -- the thing that would fix it -- could not be reached.  Same
    button, same fetch, offered at the point where the user actually hits the wall.

    on_fetched re-runs whatever drew this row.  A fetch bumps deviceinv's generation, which
    is what makes taskedit.list_addable_actions rebuild rather than answer from its memo,
    so re-running the picker is all it takes for the greyed-out row to turn into a button.
    """
    ui.label(reason).classes("text-xs text-gray-500 italic")
    _render_inventory_fetch(gui, reason, on_fetched)


def _render_app_arg_field(
    gui: MyGui,
    arg: taskedit.EditableArg,
    key: str,
    field_refs: dict,
    value: str | None = None,
) -> None:
    """An App argument: an ordinary text input holding the package names, and a button
    that opens the picker beside it.

    Typed into as well as picked from, for the same reason _build_icon_field is: an
    <appPkg> is legitimately a %variable, and the inventory only knows the apps this
    configuration already names.  What is typed is what is saved -- Save reads the text
    input's own field_refs entry and nothing else, and the picker's only power is to write
    into it (the same either/or as _render_task_name_field).
    """
    field_refs[key] = ui.input(
        translate_string(arg.arg_name),
        value=arg.current_value if value is None else value,
    ).classes("flex-1")
    pick_button = ui.button(
        translate_string("Pick"),
        icon="apps",
        on_click=lambda _e=None, f=field_refs[key]: _build_app_picker_dialog(f, gui),
    ).props("flat dense size=sm")
    with pick_button:
        ui.tooltip(translate_string("Choose from the Applications named in the loaded configuration."))


def _render_icon_arg_field(
    gui: MyGui,
    arg: taskedit.EditableArg,
    key: str,
    field_refs: dict,
    value: str | None = None,
) -> None:
    """An Icon argument: the same two-widget arrangement as _render_app_arg_field, holding
    one icon reference -- see deviceinv.format_icon_value for how each of the four kinds of
    one is spelled into a single field.
    """
    field_refs[key] = ui.input(
        translate_string(arg.arg_name),
        value=arg.current_value if value is None else value,
    ).classes("flex-1")
    pick_button = ui.button(
        translate_string("Pick"),
        icon="image",
        on_click=lambda _e=None, f=field_refs[key]: _build_tasker_icon_picker_dialog(f, gui),
    ).props("flat dense size=sm")
    with pick_button:
        ui.tooltip(
            translate_string(
                "Choose from the icons used in the loaded configuration, and from your device's "
                "applications if you have fetched them.",
            ),
        )


def build_action_condition_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    act_number: int,
    checkbox: ui.checkbox,
    condition_cache: dict[int, tuple[str, str, str]],
) -> None:
    """Prompts for a per-action If condition (Target/Operator/Value) when the
    action's "If" checkbox is checked -- see _render_action_condition_checkbox.
    Prefills from the values cached by the last uncheck (so toggling off and
    on edits rather than starts over), else from the action's current XML. Ok
    validates and writes the <ConditionList> (dialog stays open on errors);
    Cancel unchecks the checkbox, adding nothing.
    """
    action = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if action is None:
        return

    prefill = condition_cache.get(act_number) or taskedit.get_action_condition_values(action)
    operator_labels = [label for _code, label in taskedit.IF_CONDITION_OPERATORS]

    with ui.dialog().props("persistent") as condition_dialog, ui.card().classes("min-w-[400px] p-6"):
        ui.label(f"If Condition -- {act_number}: {action.action_name}").classes("text-lg font-bold text-blue-600")
        target_input = ui.input(translate_string("Target"), value=prefill[0]).classes("w-full")
        operator_select = ui.select(
            operator_labels,
            value=prefill[1] if prefill[1] in operator_labels else operator_labels[0],
            label=translate_string("Operator"),
        ).classes("w-full")
        value_input = ui.input(translate_string("Value"), value=prefill[2]).classes("w-full")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(
                translate_string("Cancel"),
                on_click=lambda: (condition_dialog.close(), checkbox.set_value(False)),
            ).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.set_action_condition_event(
                    edited_task,
                    act_number,
                    target_input,
                    operator_select,
                    value_input,
                    condition_dialog,
                    checkbox,
                ),
            ).classes("bg-blue-600")

    condition_dialog.open()


def _render_action_condition_checkbox(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    action: taskedit.EditableAction,
    condition_cache: dict[int, tuple[str, str, str]],
) -> None:
    """Renders an action's per-action "If" checkbox in the Add/Edit Task action
    lists (every action except the 'If' action itself -- callers skip that).
    Checked state mirrors whether the action currently has a <ConditionList>;
    checking prompts for the condition (build_action_condition_dialog),
    unchecking removes it (stashing its values in condition_cache so a
    re-check prefills them). An action with multiple chained conditions gets a
    read-only note instead -- replacing those from this single-condition
    prompt would silently drop the rest.
    """
    condition_count = taskedit.action_condition_count(action)
    if condition_count > 1:
        ui.label(
            f"Has {condition_count} chained If conditions -- not editable here.",
        ).classes("text-xs text-gray-500 italic")
        return

    target, operator_label, value = taskedit.get_action_condition_values(action)
    text = f"If: {target} {operator_label} {value}".rstrip() if condition_count else "If"
    checkbox = ui.checkbox(text, value=condition_count == 1).props("dense")

    def on_toggle(e: ui.event, act_number: str = action.act_number, cb: ui.checkbox = checkbox) -> None:
        if e.value:
            build_action_condition_dialog(self, edited_task, act_number, cb, condition_cache)
            return
        current = next((a for a in edited_task.actions if a.act_number == act_number), None)
        if current is not None and taskedit.action_has_condition(current):
            condition_cache[act_number] = taskedit.get_action_condition_values(current)
        self.event_handlers.remove_action_condition_event(edited_task, act_number)
        cb.set_text(translate_string("If"))

    checkbox.on_value_change(on_toggle)


def _render_continue_after_error_checkbox(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    action: taskedit.EditableAction,
) -> None:
    """Renders an action's 'Continue Task After Error' checkbox in the Add/Edit
    Task action lists -- only for actions Tasker considers able to fail
    (actionc.py's canfail flag, see taskedit.action_can_fail). Checked writes
    <se>false</se> on the action; unchecking removes the element (Tasker's
    stop-on-error default). Applied immediately, same as the Enabled switch.
    """
    if not taskedit.action_can_fail(action):
        return

    ui.checkbox(
        translate_string("Continue Task After Error"),
        value=taskedit.action_continues_after_error(action),
        on_change=lambda e, n=action.act_number: self.event_handlers.set_action_continue_after_error_event(
            edited_task,
            n,
            e.value,
        ),
    ).props("dense")


def _render_plugin_configuration_warning(element: object, name: str) -> None:
    """Renders the standing "configure this in Tasker" warning on an action's or a
    condition's own panel, for a third-party plugin whose payload this tool can't
    edit -- nothing at all for anything else (see
    taskedit.tasker_configuration_warning). Shown in all three action/condition
    lists (Edit Task, Add Task, Edit Profile's State/Event conditions), whether the
    item was just added from bundle.py or read from the loaded backup.
    """
    warning = taskedit.tasker_configuration_warning(element, name)
    if not warning:
        return

    with ui.row().classes(
        "w-full items-center gap-2 p-2 mb-1 rounded bg-amber-100 dark:bg-amber-900 border border-amber-400",
    ):
        ui.icon("warning").classes("text-amber-700 dark:text-amber-300")
        ui.label(warning).classes("text-xs text-amber-900 dark:text-amber-100")


def build_if_variant_dialog(on_choice: Callable[[str], None]) -> None:
    """Prompts for how much of an If block to insert when the user picks the
    "If" action in an Add/Edit Task action picker: just the "If", "If" plus a
    matching "End If", or a full "If"/"Else"/"End If" skeleton -- see
    taskedit.IF_BLOCK_VARIANTS/add_if_block_to_task. Fires on_choice(variant)
    only when one is clicked; Cancel inserts nothing.
    """
    with ui.dialog().props("persistent") as variant_dialog, ui.card().classes("min-w-[300px] p-6"):
        ui.label(translate_string("Add 'If' Action")).classes("text-lg font-bold text-blue-600")
        ui.label(translate_string("Insert just the 'If', or a complete block?")).classes("text-sm mb-2")
        for variant in taskedit.IF_BLOCK_VARIANTS:
            ui.button(
                variant,
                on_click=lambda v=variant: (variant_dialog.close(), on_choice(v)),
            ).classes("w-full")
        with ui.row().classes("w-full justify-end mt-2"):
            ui.button(translate_string("Cancel"), on_click=variant_dialog.close).props("outline")

    variant_dialog.open()


def build_edit_task_dialog(self: MyGui, edited_task: taskedit.EditableTask) -> None:
    """Builds and opens the Edit Task dialog (Phase 1: name/priority; an "Add an
    action" search/filter picker -- the same one Add Task uses -- that can insert
    the new action before/after any existing one or at the end, not just append;
    per-action Copy/Move/Delete; and the values of an action's existing arguments
    -- see taskedit.py for what's editable and why). The Task Name field itself is
    read-only: Rename prompts for a new one and applies it on its own, immediately
    (see build_rename_dialog); Delete Task removes the Task and every reference to
    it (see build_delete_task_dialog).

    Built fresh each call rather than reused, since its content is entirely different
    per Task. Field widgets are kept in a plain dict (matching this file's existing
    ad-hoc widget-ref pattern) and read at Save time rather than using NiceGUI bindings.
    """
    task_name = edited_task.task_element.findtext("nme", "")
    field_refs: dict = {}
    # Last-known per-action If condition values, keyed by act_number -- lets an
    # uncheck/re-check of the "If" checkbox edit instead of starting over.
    condition_cache: dict[int, tuple[str, str, str]] = {}
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions()})
    # Maps each "Position" dropdown label to the act_number to insert at (None
    # for "At the End") -- kept out-of-band rather than as the ui.select's own
    # value/options dict, since "Before N" and "After N-1" resolve to the exact
    # same act_number and a dict's keys (which NiceGUI's dict-options form uses
    # as the value) must be unique, but the two need to stay distinct, readable
    # menu entries.
    position_labels: dict[str, int | None] = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        # Kept as a local (not in field_refs -- _task_arg_values reads .value off
        # every entry there, which a ui.label doesn't have) so Rename can retitle
        # the still-open dialog: see rename_task_event.
        title_label = ui.label(f"{translate_string('Edit Task')}: {task_name}").classes(
            "text-xl font-bold text-blue-600",
        )

        with ui.row().classes("w-full gap-4"):
            # Read-only: an existing Task is renamed only through the Rename
            # button's prompt (build_rename_dialog), which is the one path that
            # rejects a name another Task already has. Rename writes the new
            # name back into this field so Ok/Save, which still read it, don't
            # apply the pre-rename name over the top.
            field_refs["name"] = (
                ui.input(translate_string("Task Name"), value=task_name).props("readonly").classes("flex-1")
            )
            field_refs["priority"] = ui.input(
                translate_string("Priority"),
                value=edited_task.task_element.findtext("pri", ""),
            ).classes("w-32")

        ui.label(translate_string("Add an action")).classes("text-sm font-bold mt-2")
        with ui.row().classes("w-full gap-4"):
            search_input = ui.input(translate_string("Search actions")).classes("flex-1")
            category_select = ui.select(["All", *category_names], value="All").classes("w-48")
        position_select = (
            ui.select([], label=translate_string("Position"), with_input=True).classes("w-full").props("dense")
        )

        picker_container = ui.column().classes("w-full")
        ui.label(translate_string("Actions in this Task")).classes("text-sm font-bold mt-2")
        actions_container = ui.column().classes("w-full")
        # act_number of the action most recently added in this dialog session --
        # render_actions highlights it so it's easy to spot in a long list.
        last_added_act_number: int | None = None

        def clear_last_added() -> None:
            # Copy/Move/Delete all renumber the list, so a stale act_number here
            # would risk highlighting the wrong action -- drop the highlight
            # instead of letting it follow whatever action inherits the number.
            nonlocal last_added_act_number
            last_added_act_number = None

        def refresh_position_options() -> None:
            _refresh_position_options(edited_task, position_select, position_labels)

        def add_picked_action(action_key: str) -> None:
            nonlocal last_added_act_number
            # "If" gets an extra prompt (just the If, or a whole If/Else/End If
            # block?) before anything is inserted; every other action goes in
            # directly. Position is resolved when the choice lands, not at
            # picker-click time -- same value, and the variant dialog is modal.
            if action_key == taskedit.IF_ACTION_KEY:

                def _add_if_block(variant: str) -> None:
                    nonlocal last_added_act_number
                    act_number = self.event_handlers.add_if_block_to_edit_task_event(
                        edited_task,
                        variant,
                        position_labels.get(position_select.value),
                    )
                    if act_number is not None:
                        last_added_act_number = act_number
                    render_actions()
                    refresh_position_options()

                build_if_variant_dialog(_add_if_block)
                return
            act_number = self.event_handlers.add_action_to_edit_task_event(
                edited_task,
                action_key,
                position_labels.get(position_select.value),
            )
            if act_number is not None:
                last_added_act_number = act_number
            render_actions()
            refresh_position_options()

        def refresh_picker(_e: ui.event | None = None) -> None:
            picker_container.clear()
            rows = taskedit.search_addable_actions(search_input.value, category_select.value)
            with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
                for row in rows:
                    if row["addable"]:
                        ui.button(
                            f"{row['name']} ({row['category_name']})",
                            on_click=lambda r=row: add_picked_action(r["action_key"]),
                        ).props("flat align=left dense").classes("w-full justify-start")
                    else:
                        with ui.column().classes("w-full gap-0"):
                            ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                            _render_addability_reason(self, row["reason"], refresh_picker)

        search_input.on_value_change(refresh_picker)
        category_select.on_value_change(refresh_picker)

        def render_actions() -> None:
            # Rebuild from scratch -- Copy/Move/Delete all renumber every action, so
            # stale act*_arg* keys must not survive into the next Save.
            for key in [k for k in field_refs if k.startswith("act")]:
                del field_refs[key]
            actions_container.clear()
            with actions_container, ui.scroll_area().classes("w-full h-96 border rounded p-2"):
                if not edited_task.actions:
                    ui.label(translate_string("No actions in this Task.")).classes("text-xs text-gray-500 italic")
                last_position = len(edited_task.actions) - 1
                indent_spaces = _action_indent_spaces(self)
                display_levels = taskedit.action_display_levels(edited_task.actions)
                for action, nest_level in zip(edited_task.actions, display_levels, strict=True):
                    # Indent with non-breaking spaces -- plain ones collapse in the rendered header.
                    indent_pad = "\u00a0" * (indent_spaces * nest_level)
                    is_last_added = action.act_number == last_added_act_number
                    header = f"{indent_pad}{action.act_number}: {action.action_name}"
                    if is_last_added:
                        header += "  \u2190 just added"
                    action_expansion = ui.expansion(header, value=is_last_added).classes("w-full")
                    if is_last_added:
                        action_expansion.classes("bg-amber-100 dark:bg-amber-900 border-2 border-amber-400 rounded")
                    with action_expansion:
                        with ui.row().classes("w-full items-center gap-2 mb-2"):
                            ui.button(
                                translate_string("Copy"),
                                on_click=lambda n=action.act_number: (
                                    clear_last_added(),
                                    self.event_handlers.copy_action_in_edit_task_event(edited_task, n),
                                    render_actions(),
                                    refresh_position_options(),
                                ),
                            ).props("flat color=blue dense")
                            move_to_input = (
                                ui
                                .number(
                                    translate_string("Move to #"),
                                    value=action.act_number,
                                    min=0,
                                    max=last_position,
                                )
                                .classes("w-24")
                                .props("dense")
                            )
                            ui.button(
                                translate_string("Move"),
                                on_click=lambda n=action.act_number, target=move_to_input: (
                                    clear_last_added(),
                                    self.event_handlers.move_action_in_edit_task_event(
                                        edited_task,
                                        n,
                                        int(target.value) if target.value is not None else n,
                                    ),
                                    render_actions(),
                                    refresh_position_options(),
                                ),
                            ).props("flat color=orange dense")
                            ui.button(
                                translate_string("Delete"),
                                on_click=lambda n=action.act_number: (
                                    clear_last_added(),
                                    self.event_handlers.delete_action_in_edit_task_event(edited_task, n),
                                    render_actions(),
                                    refresh_position_options(),
                                ),
                            ).props("flat color=red dense")

                        action_enabled_switch = ui.switch(
                            value=taskedit.is_action_enabled(action),
                            on_change=lambda e, n=action.act_number: self.event_handlers.set_action_enabled_event(
                                edited_task,
                                n,
                                e.value,
                            ),
                        ).classes("mb-2")
                        action_enabled_switch.bind_text_from(
                            action_enabled_switch,
                            "value",
                            backward=lambda v: "Enabled" if v else "Disabled",
                        )

                        field_refs[taskedit.label_key(action.act_number)] = ui.input(
                            translate_string("Label"),
                            value=taskedit.get_action_label(action),
                        ).classes("w-full")

                        if action.code != taskedit.IF_ACTION_CODE:
                            _render_action_condition_checkbox(self, edited_task, action, condition_cache)
                        _render_continue_after_error_checkbox(self, edited_task, action)
                        _render_plugin_configuration_warning(action.action_element, action.action_name)

                        if not action.args:
                            ui.label(translate_string("No editable arguments.")).classes("text-xs text-gray-500 italic")
                        for arg in action.args:
                            key = taskedit.arg_key(action.act_number, arg.arg_id)
                            with ui.row().classes("w-full items-center gap-2"):
                                if arg.widget_kind == "checkbox":
                                    field_refs[key] = ui.checkbox(arg.arg_name, value=arg.current_value == "1")
                                elif arg.widget_kind == "dropdown":
                                    options = arg.dropdown_options or []
                                    field_refs[key] = ui.select(
                                        options,
                                        value=_dropdown_current_label(arg),
                                        label=arg.arg_name,
                                    ).classes(
                                        "flex-1",
                                    )
                                elif taskedit.is_perform_task_name_arg(action.code, arg):
                                    _render_task_name_field(self, action, arg, key, field_refs)
                                elif arg.widget_kind == "app_picker":
                                    _render_app_arg_field(self, arg, key, field_refs)
                                elif arg.widget_kind == "icon_picker":
                                    _render_icon_arg_field(self, arg, key, field_refs)
                                elif arg.widget_kind in ("text", "raw_fallback"):
                                    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_inventory_fetch(render_actions, action),
                                        )
                                else:  # readonly
                                    ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes("flex-1")
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_inventory_fetch(render_actions, action),
                                        )

        refresh_picker()
        refresh_position_options()
        render_actions()

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=taskedit.default_save_path(task_name),
        ).classes("w-full mt-2")

        # Everything a change to this Task can be in is either the working copy's element --
        # every Add/Copy/Move/Delete Action, an action's Enabled switch, its If condition,
        # a Rename -- or a widget in field_refs, which is where the Priority, labels and
        # argument values sit until a save reads them.  See editor_state.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(edited_task.task_element, field_refs))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            delete_task_button = ui.button(
                translate_string("Delete Task"),
                on_click=lambda: self.event_handlers.delete_task_event(edited_task, dialog),
            ).classes("bg-red-500 text-white")
            with delete_task_button:
                ui.tooltip(
                    translate_string(
                        "Deletes this Task and every reference to it: it is removed from the Tasks of every "
                        "Project that owns it, and from any Profile that runs it as its Entry/Exit Task. "
                        "The Profiles themselves are kept.",
                    ),
                )
            rename_task_button = ui.button(
                translate_string("Rename"),
                on_click=lambda: self.event_handlers.rename_task_event(edited_task, field_refs, title_label),
            ).classes("bg-blue-600")
            with rename_task_button:
                ui.tooltip(
                    translate_string(
                        "Prompts for a new name and applies just that to the loaded backup, right now. "
                        "Everything else in this dialog stays pending until Ok/Save, and the dialog stays "
                        "open so you can carry on editing.",
                    ),
                )
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_edited_task_event(edited_task, field_refs, dialog),
            ).props("outline")
            task_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_edited_task_to_current_file_event(
                    edited_task,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with task_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this Task -- "
                        "with this dialog's edits applied, the same ones 'Ok' would keep.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            task_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_to_android_dialog_event(
                    edited_task,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with task_to_android:
                ui.tooltip(
                    translate_string(
                        "This opens a choice of two: write the Task as a standalone file onto your Android "
                        "device under /Tasker/tasks, or import it straight into Tasker's live "
                        "configuration.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                        "device, with the server running (see the README's Direct XML Retrieval notes), and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings.\n\n"
                        "The file write needs no authorization prompt; the import asks for one, and you must "
                        "exit and restart Tasker to see an imported Task in the Tasker UI.",
                    ),
                ).style("white-space: pre-wrap")
            task_save = ui.button(
                translate_string("Export Task"),
                on_click=lambda: self.event_handlers.save_edited_task_event(edited_task, field_refs, dialog),
            ).classes("bg-blue-600")
            with task_save:
                ui.tooltip(
                    translate_string("This will save the Task directly to your current drive.\n\n"),
                ).style("white-space: pre-wrap")

    dialog.open()


def build_save_to_android_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    field_refs: dict,
    parent_dialog: ui.dialog,
    on_created: Callable[[str], None] | None = None,
) -> None:
    """Prompts for the Android device's IP address and port, then either writes the
    current Task (name/priority/args as they stand in the parent dialog's fields)
    onto the device's storage under /Tasker/tasks as a standalone .tsk.xml file --
    see taskedit.save_task_to_android_file -- or imports it directly into Tasker via
    the HTTP API's POST /api/import -- see taskedit.save_task_to_android.  The same
    two-button shape build_save_profile_to_android_dialog has, for the same reason.
    On success both this prompt and the parent (Edit/Add Task) dialog are closed.

    The Task is the one kind where the import half needs no tap on the device:
    api/import is documented Task-only and imports headlessly, where a Profile, a
    Project and a Scene all have to go through Tasker's own import screen.

    on_created is threaded through from build_add_task_dialog's own
    on_task_created -- see that parameter's docstring.
    """
    default_ip = getattr(self, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(self, "android_port", "") or "1821"

    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Task To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = {
            "ip_address": ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full"),
            "ip_port": ui.input(translate_string("Port"), value=default_port).classes("w-full"),
        }
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.save_task_to_android_file_event(
                    edited_task,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                    on_created=on_created,
                ),
            ).props("outline")
            with save_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Task as a standalone file onto the Android device, "
                        "under /Tasker/tasks.\n\n"
                        "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                        "No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            # The other half of the same dialog, and a genuinely different outcome -- see
            # build_save_profile_to_android_dialog for why these are two buttons and not a
            # checkbox.  A Task's import half is the one that needs no tap on the device.
            import_into_tasker = ui.button(
                translate_string("Import Into Tasker"),
                on_click=lambda: self.event_handlers.save_task_to_android_event(
                    edited_task,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                    on_created=on_created,
                ),
            ).classes("bg-blue-600")
            with import_into_tasker:
                ui.tooltip(
                    translate_string(
                        "This puts the Task straight into Tasker's live configuration on the Android "
                        "device.  Unlike a Profile, a Project or a Scene, no import screen and no tap "
                        "on the device are needed -- Tasker's api/import takes a Task directly.\n\n"
                        "The Task is copied to /Tasker/tasks on the device first and imported from "
                        "there, so the copy stays behind as a record of exactly what was imported.  "
                        "You will be asked before it replaces a file already at that path.\n\n"
                        "If Tasker does not report the Task after two attempts, that copy is handed to "
                        "Android's 'Open with...' chooser instead, so you can import it by picking "
                        "Tasker.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and running, and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The device will ask you to authorize MapTasker the first time.",
                    ),
                ).style("white-space: pre-wrap")

    android_dialog.open()


def set_weekday_checkboxes(boxes: dict[int, ui.checkbox], selected: set[int]) -> None:
    """Sets a Day condition's weekday checkboxes (1=Sunday..7=Saturday, keyed the
    same way as profedit.WEEKDAY_NAMES) to match `selected` -- backs the
    All/None/Odd quick-select buttons in build_edit_profile_dialog. Purely a
    client-side widget update; the actual condition isn't touched until Save
    reads these checkboxes' values like any other field.
    """
    for day_number, checkbox in boxes.items():
        checkbox.value = day_number in selected


def _mark_unsupported_options(select_widget: ui.select, unsupported_values: set) -> None:
    """Greys out and blocks selection of any option in select_widget whose
    underlying value is in unsupported_values -- e.g. an Event/State condition
    code this tool can't synthesize from scratch (see
    taskedit.classify_action_addability). NiceGUI's ui.select has no public
    Python API for disabling individual options, so this reaches into the
    Quasar QSelect props it builds internally: each option becomes
    {"value": index, "label": ...}, and adding a "disable": True key there
    (plus the "option-disable" prop telling QSelect which key to read) makes
    Quasar itself refuse the click -- the popup entry renders greyed out and
    unclickable, not just visually different.

    Must be called right after construction, before anything else touches the
    widget's options -- ui.select regenerates self._props["options"] from
    scratch on every .update()/.set_options() call (dropping any "disable" key
    added here), and this codebase's condition pickers are always freshly
    built per render rather than updated in place, so that's a non-issue here.

    Mutating a nested prop (each option dict, here) fires the *same*
    props-changed signal as a top-level one -- which normally triggers exactly
    that regeneration, self-defeating the mutation before it's ever read back.
    suspend_updates() defers that signal until the whole batch (every
    "disable" flag plus the "option-disable" prop) is in place.
    """
    with select_widget._props.suspend_updates():  # noqa: SLF001
        for option, value in zip(select_widget._props["options"], select_widget._values, strict=True):  # noqa: SLF001
            if value in unsupported_values:
                option["disable"] = True
        select_widget.props('option-disable="disable"')


def _build_profile_editor_body(self: MyGui, edited_profile: profedit.EditableProfile, field_refs: dict) -> None:
    """Renders a Profile's Enabled/Disabled toggle, Entry/Exit Task Link/Unlink
    controls, and its conditions section (per-condition Add/Edit/Delete for the
    flat condition types -- Time, Day, App, Loc; Event/State's own code
    pickers; and editing a State/Event condition's plugin/built-in arguments,
    reusing the same arg-widget rendering as Task Action editing) -- shared by
    build_edit_profile_dialog and build_add_profile_dialog, since a brand-new
    Profile being added from scratch needs the exact same Task-linking and
    condition-editing machinery as one already in the backup; only the dialog
    chrome around it (title, Name field, Save-path field, and button row)
    differs between the two. Must be called inside the caller's own
    `with ui.dialog(), ui.card():` block, after field_refs["name"] is set.
    """
    enabled_switch = ui.switch(
        value=profedit.is_profile_enabled(edited_profile),
        on_change=lambda e: self.event_handlers.set_profile_enabled_event(edited_profile, e.value),
    )
    enabled_switch.bind_text_from(enabled_switch, "value", backward=lambda v: "Enabled" if v else "Disabled")

    tasks_container = ui.column().classes("w-full")

    def render_task_links() -> None:
        # Rebuild from scratch so the Link/Unlink controls always reflect the
        # profile's current entry_task_id/exit_task_id after a Link or Unlink.
        tasks_container.clear()
        all_tasks_by_name = PrimeItems.tasker_root_elements.get("all_tasks_by_name", {})
        task_names = sorted(all_tasks_by_name)
        with tasks_container:
            for link_type, task_id in (
                ("Entry", edited_profile.entry_task_id),
                ("Exit", edited_profile.exit_task_id),
            ):
                with ui.row().classes("w-full items-center gap-2 mt-2"):
                    current_name = (
                        next(
                            (name for name, entry in all_tasks_by_name.items() if entry["id"] == task_id),
                            "",
                        )
                        if task_id
                        else ""
                    )
                    ui.label(f"{link_type} Task:").classes("font-bold w-24")
                    if current_name:
                        ui.label(current_name).classes("flex-1")
                        ui.button(
                            translate_string("Unlink"),
                            on_click=lambda lt=link_type: (
                                self.event_handlers.unlink_task_from_profile_event(edited_profile, lt),
                                render_task_links(),
                            ),
                        ).props("flat color=red dense")
                    else:
                        picker = (
                            ui
                            .select(task_names, label=translate_string("Choose a Task"), with_input=True)
                            .classes("flex-1")
                            .props("dense")
                        )
                        # Registered under a fixed key (not cleared/rebuilt like the cond*
                        # keys) so Save/Ok/Save To Android can link in whatever's currently
                        # picked here even if the user never clicked "Link" separately --
                        # see userintr._link_pending_task_pickers.
                        field_refs[f"{link_type.lower()}_task_picker"] = picker
                        ui.button(
                            translate_string("Link"),
                            on_click=lambda lt=link_type, p=picker: (
                                self.event_handlers.link_task_to_profile_event(edited_profile, lt, p.value),
                                render_task_links(),
                            ),
                        ).props("flat color=blue dense")
                        # Alternative to picking an existing Task: build a brand-new one
                        # inline (the same Add Task dialog the top-level "Add Task" button
                        # opens) and link it in as this Profile's Entry/Exit Task the
                        # moment it's created -- see open_add_task_for_profile_link_event.
                        ui.button(
                            translate_string("Add Task"),
                            on_click=lambda lt=link_type: self.event_handlers.open_add_task_for_profile_link_event(
                                edited_profile,
                                lt,
                                render_task_links,
                            ),
                        ).props("flat color=blue dense")

    render_task_links()

    ui.label(translate_string("Conditions")).classes("text-sm font-bold mt-4")
    conditions_container = ui.column().classes("w-full")

    def render_conditions() -> None:
        # Rebuild from scratch -- Add/Delete Condition and an App condition's
        # Add/Remove App Entry all change what field_refs keys are valid, so
        # stale cond*_* keys must not survive into the next Save. But field
        # values (Time/Loc/Day/App/State/Event) are only ever written back
        # onto the XML at Save time -- they're not applied immediately like
        # Add/Delete Condition or Link/Unlink Task are -- so rebuilding from
        # the XML alone would silently discard whatever the user had already
        # entered elsewhere in this same dialog but hadn't saved yet (most
        # noticeable on Day, with its 51 checkboxes, but the same gap exists
        # for every field here). Snapshot the current widget values first
        # (same string coercion save_edited_profile_event uses) so each
        # widget below can prefer its own not-yet-saved value over the one
        # freshly read from the XML.
        unsaved = {
            key: ("1" if widget.value is True else "0" if widget.value is False else str(widget.value))
            for key, widget in field_refs.items()
            if key.startswith("cond")
        }

        def checkbox_initial(key: str, default: bool) -> bool:
            return unsaved[key] in ("1", "true", "True") if key in unsaved else default

        def text_initial(key: str, default: str) -> str:
            return unsaved.get(key, default)

        for key in [k for k in field_refs if k.startswith("cond")]:
            del field_refs[key]
        conditions_container.clear()
        with conditions_container:
            if not edited_profile.conditions:
                ui.label(translate_string("No conditions on this Profile.")).classes("text-xs text-gray-500 italic")
            for condition in edited_profile.conditions:
                header = f"{condition.cond_index}: {profedit.get_condition_display_name(condition)}"
                with ui.expansion(header).classes("w-full"):
                    ui.button(
                        translate_string("Delete Condition"),
                        on_click=lambda ci=condition.cond_index: (
                            self.event_handlers.remove_condition_from_profile_event(edited_profile, ci),
                            render_conditions(),
                        ),
                    ).props("flat color=red dense").classes("mb-2")

                    if condition.cond_type in ("State", "Event"):
                        _render_plugin_configuration_warning(
                            condition.condition_element,
                            profedit.get_condition_display_name(condition),
                        )
                        if not condition.args:
                            ui.label(
                                translate_string(
                                    "No editable arguments (code not mapped, or this condition has none).",
                                ),
                            ).classes("text-xs text-gray-500 italic")
                        for arg in condition.args:
                            key = profedit.condition_arg_key(condition.cond_index, arg.arg_id)
                            with ui.row().classes("w-full items-center gap-2"):
                                if arg.widget_kind == "checkbox":
                                    field_refs[key] = ui.checkbox(
                                        arg.arg_name,
                                        value=checkbox_initial(key, arg.current_value == "1"),
                                    )
                                elif arg.widget_kind == "dropdown":
                                    options = arg.dropdown_options or []
                                    try:
                                        current_label = options[int(arg.current_value)]
                                    except (ValueError, IndexError):
                                        current_label = options[0] if options else ""
                                    field_refs[key] = ui.select(
                                        options,
                                        value=text_initial(key, current_label),
                                        label=arg.arg_name,
                                    ).classes("flex-1")
                                elif arg.widget_kind == "app_picker":
                                    _render_app_arg_field(
                                        self,
                                        arg,
                                        key,
                                        field_refs,
                                        text_initial(key, arg.current_value),
                                    )
                                elif arg.widget_kind == "icon_picker":
                                    _render_icon_arg_field(
                                        self,
                                        arg,
                                        key,
                                        field_refs,
                                        text_initial(key, arg.current_value),
                                    )
                                elif arg.widget_kind in ("text", "raw_fallback"):
                                    field_refs[key] = ui.input(
                                        arg.arg_name,
                                        value=text_initial(key, arg.current_value),
                                    ).classes("flex-1")
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_condition_fetch(render_conditions, condition),
                                        )
                                else:  # readonly
                                    ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes(
                                        "flex-1",
                                    )
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_condition_fetch(render_conditions, condition),
                                        )

                    elif condition.cond_type == "Time":
                        values = profedit.get_time_field_values(condition)
                        start_key = profedit.condition_field_key(condition.cond_index, "start_time")
                        end_key = profedit.condition_field_key(condition.cond_index, "end_time")
                        rep_value_key = profedit.condition_field_key(condition.cond_index, "rep_value")
                        rep_unit_key = profedit.condition_field_key(condition.cond_index, "rep_unit")
                        with ui.row().classes("w-full gap-2 items-end"):
                            # Plain text, not type=time: a native time input can't hold a
                            # %variable value (see profedit.get_time_field_values), only
                            # "hh:mm AM/PM", so this field needs to accept either form as free text.
                            field_refs[start_key] = ui.input(
                                translate_string("Start Time"),
                                value=text_initial(start_key, values["start_time"]),
                                placeholder=translate_string("hh:mm AM/PM or %variable"),
                            ).classes("flex-1")
                            field_refs[end_key] = ui.input(
                                translate_string("End Time"),
                                value=text_initial(end_key, values["end_time"]),
                                placeholder=translate_string("hh:mm AM/PM or %variable"),
                            ).classes("flex-1")
                        with ui.row().classes("w-full gap-2 items-end mt-2"):
                            field_refs[rep_value_key] = ui.input(
                                translate_string("Every"),
                                value=text_initial(rep_value_key, values["rep_value"]),
                            ).classes("w-24")
                            field_refs[rep_unit_key] = (
                                ui
                                .select(
                                    ["Hours", "Minutes"],
                                    value=text_initial(rep_unit_key, values["rep_unit"]),
                                )
                                .classes("w-32")
                                .props("dense")
                            )

                    elif condition.cond_type == "Loc":
                        values = profedit.get_loc_field_values(condition)
                        with ui.row().classes("w-full gap-2"):
                            for key, label in (
                                ("lat", "Latitude"),
                                ("long", "Longitude"),
                                ("rad", "Radius (m)"),
                            ):
                                field_key = profedit.condition_field_key(condition.cond_index, key)
                                field_refs[field_key] = ui.input(
                                    label,
                                    value=text_initial(field_key, values[key]),
                                ).classes("flex-1")

                    elif condition.cond_type == "Day":
                        weekday_checkboxes: dict[int, ui.checkbox] = {}

                        ui.label(translate_string("Week-Day")).classes("text-xs font-bold text-gray-500")
                        selected_weekdays = set(profedit.get_day_selected_weekdays(condition))
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            for day_number in range(1, 8):
                                day_key = profedit.condition_field_key(condition.cond_index, f"wday{day_number}")
                                checkbox = ui.checkbox(
                                    profedit.WEEKDAY_NAMES[day_number],
                                    value=checkbox_initial(day_key, day_number in selected_weekdays),
                                )
                                weekday_checkboxes[day_number] = checkbox
                                field_refs[day_key] = checkbox
                        with ui.row().classes("w-full gap-2 mb-2"):
                            ui.button(
                                translate_string("All"),
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(
                                    boxes,
                                    set(range(1, 8)),
                                ),
                            ).props("flat dense")
                            ui.button(
                                translate_string("None"),
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(boxes, set()),
                            ).props("flat dense")
                            ui.button(
                                translate_string("Odd"),
                                on_click=lambda boxes=weekday_checkboxes: set_weekday_checkboxes(
                                    boxes,
                                    {1, 3, 5, 7},
                                ),
                            ).props("flat dense")

                        ui.label(translate_string("Month")).classes("text-xs font-bold text-gray-500")
                        selected_months = set(profedit.get_day_selected_months(condition))
                        with ui.row().classes("w-full gap-2 flex-wrap mb-2"):
                            for month_number in range(12):
                                month_key = profedit.condition_field_key(condition.cond_index, f"mnth{month_number}")
                                field_refs[month_key] = ui.checkbox(
                                    profedit.MONTH_NAMES[month_number],
                                    value=checkbox_initial(month_key, month_number in selected_months),
                                )

                        ui.label(translate_string("Day of Month")).classes("text-xs font-bold text-gray-500")
                        selected_month_days = set(profedit.get_day_selected_month_days(condition))
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            for day_of_month in range(1, 32):
                                mday_key = profedit.condition_field_key(condition.cond_index, f"mday{day_of_month}")
                                field_refs[mday_key] = ui.checkbox(
                                    str(day_of_month),
                                    value=checkbox_initial(mday_key, day_of_month in selected_month_days),
                                )
                            last_day_key = profedit.condition_field_key(
                                condition.cond_index,
                                f"mday{profedit.DAY_OF_MONTH_LAST_DAY}",
                            )
                            field_refs[last_day_key] = ui.checkbox(
                                translate_string("Last Day Of Month"),
                                value=checkbox_initial(
                                    last_day_key,
                                    profedit.DAY_OF_MONTH_LAST_DAY in selected_month_days,
                                ),
                            )

                    elif condition.cond_type == "App":
                        for entry_index, entry in enumerate(profedit.get_app_entries(condition)):
                            with ui.row().classes("w-full items-center gap-2"):
                                pkg_key = profedit.condition_field_key(condition.cond_index, f"app{entry_index}_pkg")
                                label_key = profedit.condition_field_key(
                                    condition.cond_index,
                                    f"app{entry_index}_label",
                                )
                                cls_key = profedit.condition_field_key(condition.cond_index, f"app{entry_index}_cls")
                                field_refs[pkg_key] = ui.input(
                                    translate_string("Package"),
                                    value=text_initial(pkg_key, entry["pkg"]),
                                ).classes("flex-1")
                                field_refs[label_key] = ui.input(
                                    translate_string("Label"),
                                    value=text_initial(label_key, entry["label"]),
                                ).classes("flex-1")
                                field_refs[cls_key] = ui.input(
                                    translate_string("Class (optional)"),
                                    value=text_initial(cls_key, entry["cls"]),
                                ).classes("flex-1")
                                _render_app_entry_pick_button(self, field_refs, pkg_key, label_key, cls_key)
                                ui.button(
                                    translate_string("Remove"),
                                    on_click=lambda ci=condition.cond_index, ei=entry_index: (
                                        self.event_handlers.remove_app_entry_event(edited_profile, ci, ei),
                                        render_conditions(),
                                    ),
                                ).props("flat color=red dense")
                        ui.button(
                            translate_string("Add App Entry"),
                            on_click=lambda ci=condition.cond_index: (
                                self.event_handlers.add_app_entry_event(edited_profile, ci),
                                render_conditions(),
                            ),
                        ).props("flat color=blue dense")

            with ui.row().classes("w-full items-center gap-2 mt-2"):
                add_type_picker = (
                    ui
                    .select(list(profedit.CONDITION_TYPES_ADDABLE), label=translate_string("Condition Type"))
                    .classes("w-48")
                    .props("dense")
                )
                # Only shown once "Event"/"State" is picked above -- unlike Time/Day/App/
                # Loc, an Event/State condition's fields depend on which of the ~60-100+
                # codes was chosen (see profedit.list_addable_events/list_addable_states),
                # so each needs its own second, searchable picker (with_input=True) rather
                # than being addable from the type name alone. Every code is listed (not
                # just the addable ones) so the user can see what exists, but any not
                # addable (e.g. a third-party plugin needing a Bundle/App payload this
                # tool can't synthesize -- see taskedit.classify_action_addability) is
                # labeled "(Not Supported)" and greyed out/unselectable -- see
                # _mark_unsupported_options.
                event_rows = profedit.list_addable_events()
                event_options = {
                    row["condition_key"]: row["name"] if row["addable"] else f"{row['name']} (Not Supported)"
                    for row in event_rows
                }
                event_type_picker = (
                    ui
                    .select(event_options, label=translate_string("Event Type"), with_input=True)
                    .classes("flex-1")
                    .props("dense")
                )
                _mark_unsupported_options(
                    event_type_picker,
                    {row["condition_key"] for row in event_rows if not row["addable"]},
                )
                event_type_picker.bind_visibility_from(add_type_picker, "value", backward=lambda v: v == "Event")

                state_rows = profedit.list_addable_states()
                state_options = {
                    row["condition_key"]: row["name"] if row["addable"] else f"{row['name']} (Not Supported)"
                    for row in state_rows
                }
                state_type_picker = (
                    ui
                    .select(state_options, label=translate_string("State Type"), with_input=True)
                    .classes("flex-1")
                    .props("dense")
                )
                _mark_unsupported_options(
                    state_type_picker,
                    {row["condition_key"] for row in state_rows if not row["addable"]},
                )
                state_type_picker.bind_visibility_from(add_type_picker, "value", backward=lambda v: v == "State")

                def add_condition_clicked(
                    type_picker: Select = add_type_picker,
                    event_picker: Select = event_type_picker,
                    state_picker: Select = state_type_picker,
                ) -> None:
                    if type_picker.value == "Event":
                        self.event_handlers.add_event_condition_to_profile_event(edited_profile, event_picker.value)
                    elif type_picker.value == "State":
                        self.event_handlers.add_state_condition_to_profile_event(edited_profile, state_picker.value)
                    else:
                        self.event_handlers.add_condition_to_profile_event(edited_profile, type_picker.value)
                    render_conditions()

                ui.button(translate_string("Add Condition"), on_click=add_condition_clicked).props(
                    "flat color=blue dense",
                )

    render_conditions()


def build_edit_profile_dialog(self: MyGui, edited_profile: profedit.EditableProfile) -> None:
    """Builds and opens the Edit Profile dialog: Rename (the Name field is
    read-only -- Rename prompts for a new one and applies it on its own,
    immediately; see build_rename_dialog), Delete Profile, Enabled/Disabled
    toggle, Entry/Exit Task Link/Unlink, and per-condition Add/Edit/Delete
    (see _build_profile_editor_body for the shared body this and
    build_add_profile_dialog both render).

    Built fresh each call rather than reused, since its content is entirely different
    per Profile. Field widgets are kept in a plain dict (matching this file's existing
    ad-hoc widget-ref pattern) and read at Save time rather than using NiceGUI bindings.
    """
    profile_name = edited_profile.profile_element.findtext("nme", "")
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        # Kept as a local (not in field_refs, which is scanned by key for widgets
        # to read .value off) so Rename can retitle the still-open dialog --
        # see build_edit_task_dialog's identical note and rename_profile_event.
        title_label = ui.label(f"Edit Profile: {profile_name}").classes("text-xl font-bold text-blue-600")

        # Read-only -- renamed only through the Rename button's prompt; see
        # build_edit_task_dialog's identical Name field for why.
        field_refs["name"] = (
            ui.input(translate_string("Profile Name"), value=profile_name).props("readonly").classes("w-full")
        )

        _build_profile_editor_body(self, edited_profile, field_refs)

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=profedit.default_save_path(profile_name),
        ).classes("w-full mt-2")

        # Add/Delete Condition, Link/Unlink Task, the Enabled toggle and a Rename all land on
        # the working copy's element as they happen; every condition's own fields wait in
        # field_refs until a save reads them, as does whatever is sitting picked but not yet
        # linked in an Entry/Exit Task picker (see userintr._link_pending_task_pickers) --
        # which is a pending change too, since a save would apply it.  See editor_state.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(edited_profile.profile_element, field_refs))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            delete_profile_button = ui.button(
                translate_string("Delete Profile"),
                on_click=lambda: self.event_handlers.delete_profile_event(edited_profile, dialog),
            ).classes("bg-red-500 text-white")
            with delete_profile_button:
                ui.tooltip(
                    translate_string(
                        "Deletes only this Profile. Its Entry/Exit Tasks are kept -- a Task is owned by "
                        "the Project, not by the Profile, and the same Task can be used by other Profiles.",
                    ),
                )
            rename_profile_button = ui.button(
                translate_string("Rename"),
                on_click=lambda: self.event_handlers.rename_profile_event(edited_profile, field_refs, title_label),
            ).classes("bg-blue-600")
            with rename_profile_button:
                ui.tooltip(
                    translate_string(
                        "Prompts for a new name and applies just that to the loaded backup, right now. "
                        "Everything else in this dialog stays pending until Ok/Save, and the dialog stays "
                        "open so you can carry on editing.",
                    ),
                )
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_edited_profile_event(edited_profile, field_refs, dialog),
            ).props("outline")
            profile_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_edited_profile_to_current_file_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this Profile -- "
                        "with this dialog's edits applied, the same ones 'Ok' would keep.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            profile_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_profile_to_android_dialog_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Profile as a standalone file onto your Android device, "
                        "under /Tasker/profiles -- it does not import it into Tasker's live configuration.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                        "device, with the server running (see the README's Direct XML Retrieval notes).\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings. No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            export = ui.button(
                translate_string("Export Profile"),
                on_click=lambda: self.event_handlers.save_edited_profile_event(edited_profile, field_refs, dialog),
            ).classes("bg-blue-600")
            with export:
                ui.tooltip(
                    translate_string("Saves this Profile as a standalone .prf.xml file on this computer."),
                ).style("white-space: pre-wrap")

    dialog.open()


def build_save_profile_to_android_dialog(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    field_refs: dict,
    parent_dialog: ui.dialog,
) -> None:
    """Prompts for the Android device's IP address and port, then writes the
    current Profile (name as it stands in the parent dialog's fields) as a
    standalone .prf.xml file onto the device's storage under /Tasker/profiles,
    via the Tasker HTTP Server Example's /upload endpoint -- see
    profedit.save_profile_to_android. This does not import it into Tasker's
    live configuration. On success both this prompt and the parent (Edit/Add
    Profile) dialog are closed.
    """
    default_ip = getattr(self, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(self, "android_port", "") or "1821"

    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Profile To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = {
            "ip_address": ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full"),
            "ip_port": ui.input(translate_string("Port"), value=default_port).classes("w-full"),
        }
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.save_profile_to_android_event(
                    edited_profile,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            with save_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Profile as a standalone file onto the Android device, "
                        "under /Tasker/profiles.\n\n"
                        "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                        "No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            # The other half of the same dialog, and a genuinely different outcome: 'Save'
            # leaves a file the user can do something with, this one puts the Profile in
            # front of Tasker to be imported.  Two buttons rather than a checkbox because
            # what they produce, what they can fail at and what the user has to do next all
            # differ -- a ticked box would hide all three.
            import_into_tasker = ui.button(
                translate_string("Import Into Tasker"),
                on_click=lambda: self.event_handlers.import_profile_into_tasker_event(
                    edited_profile,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with import_into_tasker:
                ui.tooltip(
                    translate_string(
                        "This copies the Profile to the device and opens Android's 'Open with...' "
                        "chooser for it.  Pick Tasker, and its own import screen comes up; you then tap "
                        "Import to finish -- nothing is imported until you do.\n\n"
                        "The Profile is copied to /Tasker/profiles under its own name first and offered "
                        "from there, so it stays behind under a name you can find -- import it by hand "
                        "from Tasker if the import screen does not come up.  You will be asked before it "
                        "replaces a file already at that path.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and running, and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The device will ask you to authorize MapTasker the first time.",
                    ),
                ).style("white-space: pre-wrap")

    android_dialog.open()


def build_add_project_dialog(self: MyGui, edited_project: projedit.EditableProject) -> None:
    """Builds and opens the Add Project dialog: create a brand-new Project with
    just a name -- unlike Add Profile/Add Task, there's no parent to attach to
    (a Project is the top of the hierarchy) and no Save/Save To Android surface,
    since a brand-new Project has no Profiles/Tasks attached to it yet -- both
    Save actions export a Project's *existing* <pids>/<tids> contents (see
    projedit.py's module docstring), so there is nothing to export until it's
    been created and has something attached (see build_edit_project_dialog).
    """
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(translate_string("Add Project")).classes("text-xl font-bold text-blue-600")

        field_refs["name"] = ui.input(translate_string("Project Name"), value="").classes("w-full")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_project_event(edited_project, field_refs, dialog),
            ).classes("bg-blue-600")

    dialog.open()


# The Edit Project dialog's field_refs keys that hold no editable Project state, and so
# need nothing applied before a save.  "name" is read-only (Rename is its own operation),
# and "project_save_path" is where the export goes rather than anything about the Project.
#
# THIS IS A LIST OF WHAT IS SAFE, checked at save time by userintr._unapplied_project_edits,
# because both of this dialog's saves render the Project from the LIVE TREE by name --
# projedit.write_standalone_project_xml(project_name, ...) and .save_project_to_android(
# project_name, ...).  A field added here that edits the Project would therefore be dropped
# silently from the exported file and the upload, which is the bug Scene had (see
# userintr.save_scene_to_android_event).  Anything added to field_refs and not named here
# fails the save with a message naming the field, rather than writing an incomplete Project.
#
# Adding a real editable field means applying it before those two saves -- follow what the
# Scene handlers do -- and only then listing its key here.
EDIT_PROJECT_INERT_FIELDS: frozenset[str] = frozenset({"name", "project_save_path"})


def build_edit_project_dialog(self: MyGui, edited_project: projedit.EditableProject) -> None:
    """Builds and opens the Edit Project dialog: Rename the Project (the Name
    field is read-only -- Rename prompts for the new one, see build_rename_dialog),
    enable/disable it (projedit.set_project_enabled, the Project counterpart of the
    Enabled/Disabled switch Edit Profile has), delete it -- with a choice of what
    happens to the Profiles/Tasks it owns, see
    build_delete_project_dialog -- or save it, and everything it owns, as one
    standalone .prj.xml file, either locally (projedit.write_standalone_project_xml)
    or onto the Android device under /Tasker/projects (projedit.save_project_to_android,
    see build_save_project_to_android_dialog). Unlike Add Project, there IS content to
    save here -- an already-registered Project has whatever Profiles/Tasks are attached
    to it, which is exactly why Add Project has no equivalent button (see its docstring).
    """
    project_name = edited_project.project_name
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Edit Project')}: {project_name}").classes("text-xl font-bold text-blue-600")

        # Read-only -- renamed only through the Rename button's prompt; see
        # build_edit_task_dialog's identical Name field for why.
        field_refs["name"] = (
            ui.input(translate_string("Project Name"), value=project_name).props("readonly").classes("w-full")
        )

        # Enabled/Disabled, presented exactly as Edit Profile offers it (see
        # _build_profile_editor_body's identical switch).  What it writes is not the
        # same though: a Project is disabled by <enbl>false</enbl>, not by the
        # <limit>true</limit> a Profile uses -- see projedit.is_project_enabled.
        #
        # Deliberately NOT registered in field_refs: projedit.set_project_enabled writes
        # straight through to the live Project element the moment the switch is flipped,
        # the way Rename and Delete here already do, so there is nothing left for a save
        # to apply.  Putting it in field_refs would instead trip _unapplied_project_edits
        # (see EDIT_PROJECT_INERT_FIELDS above) -- correctly, since that guard has no way
        # to tell an already-applied field from an unapplied one.
        enabled_switch = ui.switch(
            value=projedit.is_project_enabled(edited_project),
            on_change=lambda e: self.event_handlers.set_project_enabled_event(edited_project, e.value),
        ).classes("mt-2")
        enabled_switch.bind_text_from(enabled_switch, "value", backward=lambda v: "Enabled" if v else "Disabled")
        with enabled_switch:
            ui.tooltip(
                translate_string(
                    "Disables the Project in the loaded backup, right now -- like Rename, this takes "
                    "effect immediately rather than waiting for a save, and Cancel does not undo it.",
                ),
            )

        field_refs["project_save_path"] = ui.input(
            translate_string("Save as"),
            value=projedit.default_project_save_path(project_name),
        ).classes("w-full mt-2")

        # This dialog has no field that waits for a save -- the Name is read-only and the
        # "Save as" path is not part of the Project (see PENDING_CHANGES_IGNORED_FIELDS) --
        # so what raises the message here is the Enabled toggle, which writes <enbl> onto
        # the copy as it is flipped.  That is still something to save: it is in the loaded
        # backup and in no file, which is what the message says.  Rename is the other
        # immediate change and cannot leave one behind, because it closes this dialog
        # (confirm_rename_project_event).
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(edited_project.project_element, field_refs))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Delete Project"),
                on_click=lambda: self.event_handlers.delete_project_event(edited_project, dialog),
            ).classes("bg-red-500 text-white")
            rename_project_button = ui.button(
                translate_string("Rename"),
                on_click=lambda: self.event_handlers.rename_project_event(edited_project, dialog),
            ).classes("bg-blue-600")
            with rename_project_button:
                ui.tooltip(
                    translate_string(
                        "Prompts for a new name and applies it to the loaded backup, right now. "
                        "The Project Name field above is read-only -- this is the only way to change it.",
                    ),
                )
            project_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_project_to_current_file_event(
                    edited_project,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with project_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this Project -- "
                        "including every edit made anywhere in this session.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            project_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_project_to_android_dialog_event(
                    edited_project,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with project_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Project, and everything in it -- every Profile and Task -- as a "
                        "standalone file onto your Android device, under /Tasker/projects -- it does not import "
                        "it into Tasker's live configuration.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                        "device, with the server running.\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings. No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            save_single_project = ui.button(
                translate_string("Export Project"),
                on_click=lambda: self.event_handlers.save_project_event(edited_project, field_refs, dialog),
            ).classes("bg-blue-600")
            with save_single_project:
                ui.tooltip(
                    translate_string(
                        "Saves this Project, and everything in it -- every Profile and Task -- as one standalone file.",
                    ),
                )

    dialog.open()


def build_save_project_to_android_dialog(
    self: MyGui,
    edited_project: projedit.EditableProject,
    field_refs: dict,
    parent_dialog: ui.dialog,
) -> None:
    """Prompts for the Android device's IP address and port, then writes the
    Project -- under its current, already-applied name (edited_project.project_name,
    same convention as save_project_event's local export; a not-yet-applied Rename
    edit doesn't carry through) -- as a standalone .prj.xml file onto the device's
    storage under /Tasker/projects, via the Tasker HTTP Server Example's /upload
    endpoint -- see projedit.save_project_to_android. This does not import it into
    Tasker's live configuration. On success both this prompt and the parent (Edit
    Project) dialog are closed.

    field_refs is the parent dialog's, carried through only so the save handler can
    check it for editable fields this by-name upload would drop -- see
    EDIT_PROJECT_INERT_FIELDS. Nothing here reads it.
    """
    default_ip = getattr(self, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(self, "android_port", "") or "1821"

    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Project To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = {
            "ip_address": ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full"),
            "ip_port": ui.input(translate_string("Port"), value=default_port).classes("w-full"),
        }
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.save_project_to_android_event(
                    edited_project,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            with save_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Project, and everything in it, as a standalone file onto the "
                        "Android device, under /Tasker/projects.\n\n"
                        "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                        "No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            # The Profile dialog's pair, for a Project -- see
            # build_save_profile_to_android_dialog for why these are two buttons and not one
            # with a checkbox.
            import_into_tasker = ui.button(
                translate_string("Import Into Tasker"),
                on_click=lambda: self.event_handlers.import_project_into_tasker_event(
                    edited_project,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with import_into_tasker:
                ui.tooltip(
                    translate_string(
                        "This copies the Project -- and every Profile and Task in it -- to the device and "
                        "opens Android's 'Open with...' chooser for it.  Pick Tasker, and its own import "
                        "screen comes up; you then tap Import to finish, and nothing is imported until you "
                        "do.\n\n"
                        "The Project is copied to /Tasker/projects under its own name first and offered "
                        "from there, so it stays behind under a name you can find -- import it by hand "
                        "from Tasker if the import screen does not come up.  You will be asked before it "
                        "replaces a file already at that path.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and running, and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The device will ask you to authorize MapTasker the first time.",
                    ),
                ).style("white-space: pre-wrap")

    android_dialog.open()


# ==========================================
# 2a. SCENE DIALOGS
#
# The Scene arm of the Project/Profile/Task editing family.  Everything here is
# reachable only when config.EDIT_SCENE is True -- that switch decides whether the
# "Edit Scene"/"Add Scene" buttons are built at all (see initialize_gui's Specific
# Name tab), and these dialogs have no other entry point.
#
# What is here is the whole Scene *envelope*: name, size, which Project owns it,
# and every Save/Export path.  What is not here yet is the Scene's own contents --
# its UI elements and the Tasks they fire.  _build_scene_editor_body is the single
# seam that part drops into, and both dialogs call it, so filling it in lights up
# Add and Edit together.
# ==========================================
def _build_add_element_dialog(layout: dict, path: tuple, on_pick: Callable[[str], None]) -> None:
    """Tasker's own "Add Element" sheet, as a dialog: a search box, then every element the
    palette offers as a chip, grouped and named the way the Screen Builder groups and names
    them (see sceneedit.V2_PALETTE -- "Vertical Column", not "Column").

    Replaces the cascading Add menu this used to be, because a menu can do only one of the
    three things this needs.  It can list types; it cannot describe them, and it cannot show
    an element that is *visible but not addable here* -- the old menu let you pick a
    Navigation Item anywhere and reported the mistake afterwards, as a notification, once
    the chance to explain had passed.

    Nothing here reasons about the tree.  Which elements exist, which are blocked, and why,
    all come from sceneedit.v2_palette_for; this renders the answer.

    Blocked chips stay clickable rather than being disabled.  A disabled Quasar button eats
    its own tooltip, so disabling would hide the very sentence that explains the block; a
    click on one notifies the reason instead of inserting.
    """
    relation, target_name = sceneedit.v2_insert_destination(layout, path)
    groups = sceneedit.v2_palette_for(layout, path)
    search = {"text": ""}

    def tooltip_for(entry: sceneedit.V2PaletteEntry, reason: str) -> str:
        lines = [translate_string(entry.description)]
        if reason:
            lines.append(reason)
        if not entry.verified:
            lines.append(
                translate_string(
                    "Tasker lists this element, but MapTasker has never seen one in a saved Scene -- "
                    "so it is added carrying nothing but its type and id, and even the type is inferred "
                    'from the name above (written as type: "{node_type}"). '
                    "If Tasker doesn't recognise it, press Undo.",
                ).format(node_type=entry.node_type),
            )
        return "\n\n".join(lines)

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[640px] max-w-[760px] p-6"):
        ui.label(translate_string("Add Element")).classes("text-lg font-bold text-blue-600")
        if target_name:
            # The destination stated up front rather than left to a tooltip -- this is
            # v2_insert_node's inside-vs-after rule, resolved against the current selection.
            ui.label(
                translate_string("Adds inside {name}" if relation == "inside" else "Adds after {name}").format(
                    name=target_name,
                ),
            ).classes("text-sm text-gray-500 italic")

        def pick(entry: sceneedit.V2PaletteEntry, reason: str) -> None:
            if reason:
                ui.notify(reason, type="warning")
                return
            dialog.close()
            on_pick(entry.node_type)

        def matches(entry: sceneedit.V2PaletteEntry) -> bool:
            """Substring, case-insensitive, over the label, its translation and the JSON
            type -- so "row" finds Horizontal Row, and someone who knows the format can
            still type "FlowRow" and get there.
            """
            text = search["text"].strip().lower()
            if not text:
                return True
            return any(
                text in candidate.lower() for candidate in (entry.label, translate_string(entry.label), entry.node_type)
            )

        def chip(entry: sceneedit.V2PaletteEntry, reason: str) -> None:
            # The icon and colour go on as Quasar props rather than as ui.button arguments:
            # ui.button takes `icon` but has no icon_right, and the colour is state-dependent
            # (grey = blocked, orange = unverified, default otherwise).
            props = ["outline", "rounded", "no-caps", "dense"]
            props.append("icon-right=help_outline" if not entry.verified else "icon-right=info_outline")
            if reason:
                props.append("color=grey")
            elif not entry.verified:
                props.append("color=orange")
            button = ui.button(
                translate_string(entry.label),
                on_click=lambda _e=None, x=entry, r=reason: pick(x, r),
            ).props(" ".join(props))
            if reason:
                button.classes("opacity-70")
            with button:
                ui.tooltip(tooltip_for(entry, reason)).style("white-space: pre-wrap").classes("max-w-sm")

        # Created before `results` because NiceGUI lays widgets out in creation order, and the
        # search box belongs above the chips it filters.  Its on_change closes over
        # search_changed, which is defined below -- resolved at call time, not at creation.
        search_input = (
            ui
            .input(placeholder=translate_string("Search elements"), on_change=lambda e: search_changed(e.value))
            .props("outlined dense clearable autofocus")
            .classes("w-full mt-2")
        )
        with search_input.add_slot("prepend"):
            ui.icon("search")

        results = ui.column().classes("w-full gap-0 mt-1 max-h-96 overflow-auto")

        def render() -> None:
            results.clear()
            shown = 0
            with results:
                for group, entries in groups:
                    visible = [(entry, reason) for entry, reason in entries if matches(entry)]
                    if not visible:
                        continue
                    shown += len(visible)
                    ui.label(translate_string(group)).classes("text-xs uppercase text-blue-400 mt-3 mb-1")
                    with ui.row().classes("w-full gap-2 flex-wrap"):
                        for entry, reason in visible:
                            chip(entry, reason)
                if not shown:
                    ui.label(translate_string("No element matches that.")).classes(
                        "text-sm italic text-gray-500 mt-3",
                    )

        def search_changed(value: str) -> None:
            search["text"] = value or ""
            render()

        def enter_pressed() -> None:
            """Enter picks the search's one remaining match -- the fast path for someone who
            knows what they want.  Deliberately silent when the search still matches several
            elements: guessing which of them was meant would insert the wrong component.
            """
            hits = [(entry, reason) for _group, entries in groups for entry, reason in entries if matches(entry)]
            if len(hits) == 1:
                pick(*hits[0])

        search_input.on("keydown.enter", lambda _e=None: enter_pressed())

        render()

        with ui.row().classes("w-full items-center justify-between mt-4 pt-3 border-t"):
            ui.label(
                translate_string(
                    "Amber: Tasker lists it, but MapTasker has no confirmed sample of it. "
                    "Grey: can't go where the selection would put it.",
                ),
            ).classes("text-xs text-gray-500 italic")
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


def _build_rename_legacy_element_dialog(
    edited_scene: sceneedit.EditableScene,
    element: object,
    on_renamed: Callable[[str, str, bool], None],
) -> None:
    """Rename one Legacy element, having first said what else in the backup is relying on
    its current name.

    THE POINT OF THIS DIALOG IS THE LIST, not the text field.  Renaming an element is a
    one-word edit with consequences that are invisible from the Scene: 18 Task action codes
    address an element by name, so a rename either brings those Tasks along or quietly stops
    them working, and nothing in the Scene itself would ever show it.

    Three separate things are reported, because they can be acted on to three different
    degrees:

      * The Task actions that WILL be rewritten -- matched strictly, on the arg0/arg1 shape
        all 18 codes declare (find_element_name_actions).  Offered as a checkbox, on by
        default, because leaving them behind is almost never what anyone wants.

      * Tasks that mention both this Scene and this element but not in that shape -- listed
        so the count cannot silently differ from what was warned about, and not rewritten,
        because this app cannot tell what they meant by it.

      * Tasks that address elements by a match *pattern* (Element Visibility, code 65).
        Never rewritten and never can be: the pattern is evaluated by Tasker at run time, so
        whether it currently catches this element is not a question the file can answer.
    """
    old_name = (
        (element.find("Str[@sr='arg0']").text or "").strip() if element.find("Str[@sr='arg0']") is not None else ""
    )
    rewritable = sceneedit.find_element_name_actions(edited_scene.scene_name, old_name)
    rewritable_tasks = sorted({task_name for task_name, _argument in rewritable})
    loose_tasks = sceneedit.find_element_name_references(edited_scene.scene_name, old_name)
    unmatched = [task for task in loose_tasks if task not in rewritable_tasks]
    patterns = sceneedit.find_element_match_references(edited_scene.scene_name)

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[520px] max-w-[720px] p-6"):
        ui.label(f"{translate_string('Rename Element')}: {old_name}").classes("text-lg font-bold text-blue-600")
        name_input = ui.input(translate_string("New name"), value=old_name).props("dense autofocus").classes("w-full")

        update_tasks = {"value": bool(rewritable)}
        if rewritable:
            checkbox = ui.checkbox(
                f"{translate_string('Also update')} {len(rewritable)} "
                f"{translate_string('Task action(s) in')} {len(rewritable_tasks)} {translate_string('Task(s)')}",
                value=True,
                on_change=lambda event: update_tasks.__setitem__("value", bool(event.value)),
            )
            with checkbox:
                ui.tooltip(
                    translate_string(
                        "Applied when this Scene is saved, not now -- Cancel on the Scene dialog "
                        "leaves both the element and the Tasks exactly as they were.",
                    ),
                ).style("white-space: pre-wrap")
            ui.label(", ".join(rewritable_tasks)).classes("text-xs text-gray-500 ml-8")
        else:
            ui.label(translate_string("No Task addresses this element by name.")).classes(
                "text-sm text-gray-500 italic",
            )

        if unmatched:
            ui.label(
                f"{translate_string('Not updated -- these name both this Scene and this element, but not as a')} "
                f"Scene Name / Element {translate_string('pair')}: {', '.join(unmatched)}",
            ).classes("text-xs text-orange-600 italic mt-2")
        if patterns:
            ui.label(
                f"{translate_string('Never updated')}: {len(patterns)} "
                f"{translate_string('Task(s) address this Scene by a match pattern (Element Visibility). Check them yourself')}: "
                f"{', '.join(patterns)}",
            ).classes("text-xs text-orange-600 italic mt-1")

        def apply() -> None:
            on_renamed(old_name, str(name_input.value or ""), update_tasks["value"])

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(translate_string("Rename"), on_click=lambda: (apply(), dialog.close())).classes("bg-blue-600")

    dialog.open()


def _build_add_legacy_element_dialog(
    _scene_element: object,
    on_pick: Callable[[str], None],
) -> None:
    """The Legacy Scene's "Add Element" dialog -- the same shape as the Version 2 one above,
    and deliberately so: a search box, then every element as a chip with a description, and
    anything that cannot be created greyed out with the reason rather than hidden.

    Two honest differences from the V2 dialog, both stated on screen rather than buried here:

      * THE GROUPING IS THIS APP'S.  V2's headings were taken from a screenshot of Tasker's
        own Add Element sheet; no such evidence exists for the Legacy editor, so these four
        are a convenience and are not claimed to be Tasker's (see LEGACY_PALETTE_GROUPS).

      * THERE IS NO DESTINATION TO STATE.  A V2 component goes inside or after whatever is
        selected, which is worth saying up front; a Legacy element has no parent to go into.
        It goes on top of the stack, which the header says once.
    """
    search = {"text": ""}
    blocked = {entry.element_type: sceneedit.legacy_can_add(entry.element_type) for entry in sceneedit.LEGACY_PALETTE}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[640px] max-w-[760px] p-6"):
        ui.label(translate_string("Add Element")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string("Adds it on top of the stack, in the middle of the Scene. Drag it where you want it."),
        ).classes("text-sm text-gray-500 italic")

        def pick(entry: sceneedit.LegacyPaletteEntry) -> None:
            reason = blocked.get(entry.element_type, "")
            if reason:
                ui.notify(reason, type="warning", multi_line=True)
                return
            dialog.close()
            on_pick(entry.element_type)

        def matches(entry: sceneedit.LegacyPaletteEntry) -> bool:
            """Substring, case-insensitive, over the label, its translation and the XML tag --
            so "map" finds the Map element whose tag is SceneElement, and someone who knows
            the format can type "SceneElement" and still get there.
            """
            text = search["text"].strip().lower()
            if not text:
                return True
            return any(
                text in candidate.lower()
                for candidate in (entry.label, translate_string(entry.label), entry.element_type)
            )

        def chip(entry: sceneedit.LegacyPaletteEntry) -> None:
            reason = blocked.get(entry.element_type, "")
            props = ["outline", "rounded", "no-caps", "dense", "icon-right=info_outline"]
            if reason:
                props.append("color=grey")
            button = ui.button(
                translate_string(entry.label),
                on_click=lambda _e=None, x=entry: pick(x),
            ).props(" ".join(props))
            if reason:
                button.classes("opacity-70")
            with button:
                # Blocked chips stay clickable rather than disabled, for the reason the V2
                # dialog gives: a disabled Quasar button eats its own tooltip, which is the
                # one place the block is explained.
                lines = [translate_string(entry.description)]
                if reason:
                    lines.append(translate_string(reason))
                ui.tooltip("\n\n".join(lines)).style("white-space: pre-wrap").classes("max-w-sm")

        search_input = (
            ui
            .input(placeholder=translate_string("Search elements"), on_change=lambda e: search_changed(e.value))
            .props("outlined dense clearable autofocus")
            .classes("w-full mt-2")
        )
        with search_input.add_slot("prepend"):
            ui.icon("search")

        results = ui.column().classes("w-full gap-0 mt-1 max-h-96 overflow-auto")

        def render() -> None:
            results.clear()
            shown = 0
            with results:
                for group in sceneedit.LEGACY_PALETTE_GROUPS:
                    visible = [entry for entry in sceneedit.LEGACY_PALETTE if entry.group == group and matches(entry)]
                    if not visible:
                        continue
                    shown += len(visible)
                    ui.label(translate_string(group)).classes("text-xs uppercase text-blue-400 mt-3 mb-1")
                    with ui.row().classes("w-full gap-2 flex-wrap"):
                        for entry in visible:
                            chip(entry)
                if not shown:
                    ui.label(translate_string("No element matches that.")).classes(
                        "text-sm italic text-gray-500 mt-3",
                    )

        def search_changed(value: str) -> None:
            search["text"] = value or ""
            render()

        def enter_pressed() -> None:
            """Enter picks the search's one remaining match -- silent while several still
            match, since guessing would add the wrong element.
            """
            hits = [entry for entry in sceneedit.LEGACY_PALETTE if matches(entry)]
            if len(hits) == 1:
                pick(hits[0])

        search_input.on("keydown.enter", lambda _e=None: enter_pressed())
        render()

        with ui.row().classes("w-full items-center justify-between mt-4 pt-3 border-t"):
            ui.label(
                translate_string(
                    "Grey: MapTasker has no argument table for it, so it can't be created without "
                    "guessing what Tasker expects inside. Headings are MapTasker's own grouping.",
                ),
            ).classes("text-xs text-gray-500 italic")
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


# How many entries of one category the Show When picker lists before it stops and asks for a
# search.  User Globals runs to several hundred on a real backup and Built-in Globals is a
# hundred on any backup; drawing all of them makes a dialog nobody can read and a page that
# takes a visible moment to build.  Forty is enough to browse a category and see what kind of
# thing is in it, which is what an unsearched list is for.
_SHOW_WHEN_PREVIEW_LIMIT = 40


def _build_show_when_dialog(
    field: ui.input,
    groups: list[tuple[str, list[sceneedit.V2ShowWhenChoice]]] | None = None,
    title: str = "Insert into Show When",
) -> None:
    """The Show When picker: choose variables to build the condition out of, from the three
    categories in sceneedit.v2_show_when_choices -- the Screen Builder's own environment
    values, the loaded backup's own global variables, and Tasker's built-in globals.

    Appends rather than replaces, and stays open after a pick, because a Show When is an
    expression and usually wants more than one: "%sv2_render_width > %sv2_display_width / 2"
    is two picks and some typing.  Writing through `field.value` rather than onto the node
    directly is what keeps the inspector's own on_change in charge of storing it, so this
    needs to know nothing about the component being edited.

    `groups` and `title` are what let a Dynamic state field reuse all of this: the same
    insert, search and caret handling over a shorter list (no operators -- see
    sceneedit.v2_dynamic_variable_choices), under its own heading.
    """
    groups = sceneedit.v2_show_when_choices() if groups is None else groups
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[620px] max-w-[740px] p-6"):
        ui.label(translate_string(title)).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string("What you pick goes in at the cursor. Open this again to add the next piece."),
        ).classes("text-sm text-gray-500 italic")

        # Reaching the field's native <input>.  getHtmlElement() hands back whatever element
        # carries the NiceGUI id, and for ui.input that IS the <input> -- not a wrapper around
        # one -- so this has to cope with both rather than assuming a wrapper to search
        # inside.  (Assuming the wrapper is exactly the bug this replaced: querySelector found
        # nothing, every read came back null, and every pick silently fell back to the end.)
        _native_input = (
            f"const el = (() => {{ const r = getHtmlElement({field.id});"
            f" return r && r.matches('input, textarea') ? r : r && r.querySelector('input, textarea'); }})();"
        )

        async def caret_position() -> int | None:
            """Where the cursor is sitting in the Show When field, asked of the browser.

            It has to be asked for rather than remembered: the caret lives in the DOM, and
            NiceGUI's own value binding knows nothing about it.  Asking while this dialog has
            focus still works -- a blurred input keeps its selection.  None (a field never
            clicked into, or a browser that declines) means "the end", which is what
            v2_insert_show_when does with it.
            """
            with contextlib.suppress(Exception):
                return await ui.run_javascript(
                    f"(() => {{ {_native_input} return el ? el.selectionStart : null; }})()",
                    timeout=3.0,
                )
            return None

        async def pick(choice: sceneedit.V2ShowWhenChoice) -> None:
            text, caret = sceneedit.v2_insert_show_when(
                str(field.value or ""),
                choice.value,
                await caret_position(),
            )
            field.value = text
            # Put the caret back where the insert left it, so re-opening the picker adds the
            # next piece after this one rather than back at the same spot.
            with contextlib.suppress(Exception):
                ui.run_javascript(
                    f"(() => {{ {_native_input} if (el) {{ el.setSelectionRange({caret}, {caret}); }} }})()",
                )
            # Close on the pick.  A condition is built out of several of these, so staying
            # open to save a click is the obvious thing to do and the wrong one: the dialog
            # covers the very field it is filling in, so every pick landed unseen and there
            # was no way to check the expression without dismissing the picker anyway.
            # Closing shows the result, which is what makes the next pick an informed one.
            dialog.close()

        def matches(choice: sceneedit.V2ShowWhenChoice) -> bool:
            text = search["text"].strip().lower()
            return not text or text in choice.label.lower() or text in choice.value.lower()

        # Created before `results`: NiceGUI lays widgets out in creation order, and a search
        # box below the list it filters is a search box nobody finds.  Its on_change closes
        # over search_changed, defined below and resolved at call time.
        search_input = (
            ui
            .input(placeholder=translate_string("Search variables"), on_change=lambda e: search_changed(e.value))
            .props("outlined dense clearable autofocus")
            .classes("w-full mt-2")
        )
        with search_input.add_slot("prepend"):
            ui.icon("search")

        results = ui.column().classes("w-full gap-0 mt-1 max-h-96 overflow-auto")

        def render() -> None:
            results.clear()
            with results:
                for group, choices in groups:
                    visible = [choice for choice in choices if matches(choice)]
                    ui.label(f"{translate_string(group)} ({len(visible)})").classes(
                        "text-xs uppercase text-blue-400 mt-3 mb-1",
                    )
                    if not visible:
                        ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                        continue
                    with ui.row().classes("w-full gap-2 flex-wrap"):
                        for choice in visible[:_SHOW_WHEN_PREVIEW_LIMIT]:
                            button = ui.button(
                                choice.label,
                                on_click=lambda _e=None, c=choice: pick(c),
                            ).props("outline rounded no-caps dense")
                            if choice.label != choice.value:
                                # Only the named entries need this -- a user global is
                                # already showing the exact text it inserts.
                                with button:
                                    ui.tooltip(choice.value)
                    if len(visible) > _SHOW_WHEN_PREVIEW_LIMIT:
                        ui.label(
                            translate_string("...and {count} more -- type above to narrow it down.").format(
                                count=len(visible) - _SHOW_WHEN_PREVIEW_LIMIT,
                            ),
                        ).classes("text-xs text-gray-500 italic mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value or ""
            render()

        render()

        with ui.row().classes("w-full justify-end mt-4 pt-3 border-t"):
            ui.button(translate_string("Close"), on_click=dialog.close).props("flat")

    dialog.open()


# How big the swatch beside a Version 2 colour field is, and in the menu beside each Material
# role.  Small enough to sit inside a dense field, big enough to tell two greys apart.
_V2_SWATCH_STYLE = (
    "width: 18px; height: 18px; border-radius: 3px; flex: none;"
    "border: 1px solid rgba(120,120,120,0.55); box-sizing: border-box;"
)

# A glyph for each of sceneedit.V2_TEXT_CATEGORIES, so a closed section is recognisable at a
# glance rather than being one of eight identical grey bars.  Here rather than beside the
# categories themselves because what a section is called is the Scene's business and what it
# looks like is this pane's.  A category with no entry falls back to the Modifiers section's
# own "tune", which is what a group of settings looks like everywhere else in this designer.
_V2_CATEGORY_ICONS: dict[str, str] = {
    "General": "settings",
    "Content": "short_text",
    "Appearance": "palette",
    "Behavior": "rule",
    "Font": "text_fields",
    "Spacing": "format_line_spacing",
    "Decoration and effects": "auto_fix_high",
    "Paragraph": "notes",
    "Other": "more_horiz",
}


def _variable_picker_button(field: ui.input, label: str) -> None:
    """The Select Variable half of a property that can either be filled in or pointed at a
    variable -- a Text's own text, a max lines of %line_budget, a shadow the theme decides.

    Only the button.  Which slot it goes in is the caller's, because ui.color_input arrives
    with an append slot already holding its wheel: adding one there takes the wheel away (see
    _build_colour_field), so a colour field has to put this *into* that slot instead.

    Writes through `field.value`, so the field's own on_change is still what stores it and this
    knows nothing about the component being edited -- the same division the Show When picker
    and the state fields' own variable box keep to.
    """
    picker = ui.button(
        icon="playlist_add",
        on_click=lambda _e=None: _build_show_when_dialog(
            field,
            sceneedit.v2_dynamic_variable_choices(),
            f"Select a variable for {label}",
        ),
    ).props("flat dense round size=sm")
    with picker:
        ui.tooltip(translate_string("Pick from the Scene's environment and global variables."))


def _build_colour_field(item: dict, prop: sceneedit.V2Prop) -> None:
    """A Version 2 colour property: type a name or a #hex value, pick one off the wheel, or
    take one of Material's own roles from the menu.  A "colorvar" property adds a fourth way --
    point it at a variable and let the phone decide.

    The three ways matter because a V2 Scene's colours are of two kinds.  Most are ordinary
    values -- "#64B5F6", "red" -- and those want the wheel.  But Tasker also writes *role*
    names ("onPrimaryFixed", "surfaceContainerHigh"), which are not colours at all until the
    phone resolves them against its own theme, and which no colour wheel can offer because
    picking the swatch they happen to look like here would store the wrong thing entirely.
    Picking one from the menu stores the name, which is the whole point of naming it.

    The swatch is drawn here rather than through ui.color_input's own `preview`, which knows
    only hex: this one shows what a role name and an HTML colour name look like too, and goes
    blank -- rather than misleading -- for a %variable or a spelling this app cannot resolve.

    What the field does NOT do is refuse a value it doesn't recognise.  It marks it (Quasar's
    own error state, so it reads as a warning rather than a rejection) and stores it anyway:
    the Scene belongs to the user, the property may well be one a newer Tasker understands,
    and silently dropping what they typed would be worse than showing it in red.
    """
    field = (
        ui
        .color_input(
            label=translate_string(prop.label),
            value=str(item.get(prop.key, "")),
            on_change=lambda e, k=prop.key, d=item: colour_changed(d, k, str(e.value or "")),
        )
        .props("dense")
        .classes("w-full")
    )
    with field.add_slot("prepend"):
        swatch = ui.element("div").style(_V2_SWATCH_STYLE)
    # Into the append slot ui.color_input already made, NOT a fresh one: add_slot REPLACES a
    # slot of the same name, and the slot this field arrives with is the one holding its
    # colour wheel.  Making a new one here takes the wheel away, which is the opposite of
    # what this button is for -- the roles are offered *as well as* the wheel, not instead.
    with field.slots["append"]:
        palette_button = ui.button(icon="palette").props("flat dense round size=sm")
        with palette_button:
            ui.tooltip(translate_string("Pick one of Material's own colour roles."))
            _build_material_colour_menu(field)
        if prop.kind == "colorvar":
            _variable_picker_button(field, prop.label)

    def colour_changed(node: dict, key: str, text: str) -> None:
        sceneedit.v2_set_prop(node, key, text)
        resolved = sceneview.v2_swatch_colour(text)
        swatch.style(f"background: {resolved or 'transparent'};")
        if sceneedit.v2_is_colour(text):
            field.props(remove="error")
        else:
            message = translate_string("Not an HTML colour name or #hex value.")
            field.props(f'error error-message="{message}"')

    colour_changed(item, prop.key, str(item.get(prop.key, "")))


# How many icons the picker draws before it stops and asks for a search.  Same bargain the
# Show When picker strikes at _SHOW_WHEN_PREVIEW_LIMIT, at a size that suits a grid of glyphs:
# enough to browse and see what kind of thing is in there, not so many that opening the dialog
# builds several hundred widgets nobody scrolled to.
_ICON_PREVIEW_LIMIT = 120


def _build_icon_field(item: dict, prop: sceneedit.V2Prop) -> None:
    """A Version 2 icon property: type a reference, or pick a Material icon by its picture.

    Typed into as well as picked from, because an icon reference is not only ever a Material
    name -- a Scene can point at a Material Symbol ("symbol:cloud_upload;opsz:24") or at an
    installed app's own icon, and neither is something this picker can offer.  What is typed
    is stored exactly as typed.

    The glyph on the left is the field showing its own value back: it resolves all three forms
    through the same sceneview.v2_icon the preview draws by, so what is in the field and what
    the component will show are the same answer.
    """
    field = (
        ui
        .input(
            translate_string(prop.label),
            value=str(item.get(prop.key, "")),
            on_change=lambda e, k=prop.key, d=item: icon_changed(d, k, str(e.value or "")),
        )
        .props("dense")
        .classes("w-full")
    )
    with field.add_slot("prepend"):
        glyph = ui.icon("").style("font-size: 22px;")
    with field.add_slot("append"):
        pick_button = ui.button(
            icon="apps",
            on_click=lambda _e=None, w=field: _build_icon_dialog(w),
        ).props("flat dense round size=sm")
        with pick_button:
            ui.tooltip(translate_string("Pick a Material icon."))

    def icon_changed(node: dict, key: str, text: str) -> None:
        sceneedit.v2_set_prop(node, key, text)
        glyph.name = sceneview.v2_icon(text)

    icon_changed(item, prop.key, str(item.get(prop.key, "")))


def _build_icon_dialog(field: ui.input) -> None:
    """The Material icon picker: a grid of the glyphs themselves, because an icon is chosen by
    looking at it -- "AcUnit" is a snowflake, and nobody browses a list of names for that.

    The name goes under each glyph anyway.  It is what gets stored (sceneedit
    .v2_icon_reference turns "ac_unit" into "icon:AcUnit"), and two icons that look alike at
    22px are told apart by it.

    Replaces the field rather than inserting into it, unlike the Show When picker: a component
    has one icon, so a second pick is a correction and not an addition.
    """
    names = sceneedit.v2_icon_names()
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[640px] max-w-[760px] p-6"):
        ui.label(translate_string("Pick an icon")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string("What you pick replaces what the field holds. Type to narrow the list down."),
        ).classes("text-sm text-gray-500 italic")

        def pick(name: str) -> None:
            field.set_value(sceneedit.v2_icon_reference(name))
            dialog.close()

        search_input = (
            ui
            .input(placeholder=translate_string("Search icons"), on_change=lambda e: search_changed(e.value))
            .props("outlined dense clearable autofocus")
            .classes("w-full mt-2")
        )
        with search_input.add_slot("prepend"):
            ui.icon("search")

        results = ui.column().classes("w-full gap-1 mt-2 max-h-96 overflow-auto")

        def render() -> None:
            results.clear()
            text = search["text"].strip().lower().replace(" ", "_")
            visible = [name for name in names if text in name] if text else names
            with results:
                if not names:
                    ui.label(
                        translate_string("The Material icon list could not be read, so type the name instead."),
                    ).classes("text-sm italic text-orange-600")
                    return
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                with ui.row().classes("w-full gap-1 flex-wrap"):
                    for name in visible[:_ICON_PREVIEW_LIMIT]:
                        # "stack" is Quasar's own glyph-above-label layout.  Doing it with flex
                        # classes on the button does not work: they land on the button, while
                        # the row that needs turning is the .q-btn__content inside it, so the
                        # tiles come out half stacked and half side by side.
                        tile = (
                            ui
                            .button(on_click=lambda _e=None, n=name: pick(n))
                            .props(
                                "flat dense no-caps stack",
                            )
                            .classes("w-24 h-20")
                        )
                        with tile:
                            ui.icon(name).style("font-size: 24px;")
                            ui.label(name).style(
                                "font: 9px/1.1 monospace; max-width: 84px; overflow: hidden;"
                                "text-overflow: ellipsis; white-space: nowrap;",
                            )
                            ui.tooltip(sceneedit.v2_icon_reference(name))
                if len(visible) > _ICON_PREVIEW_LIMIT:
                    ui.label(
                        translate_string("...and {count} more -- type above to narrow it down.").format(
                            count=len(visible) - _ICON_PREVIEW_LIMIT,
                        ),
                    ).classes("text-xs text-gray-500 italic mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value or ""
            render()

        render()

        with ui.row().classes("w-full justify-end mt-4 pt-3 border-t"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


def _build_material_colour_menu(field: ui.color_input) -> None:
    """The menu of Material role names, each beside a swatch of what it resolves to.

    Both halves are needed to choose one: the name is what gets stored and the colour is what
    it will look like, and neither on its own tells you whether onSecondaryContainer is the
    dark one.  The colours are Material 3's baseline (sceneview.V2_MATERIAL_PALETTE) -- what a
    device without Material You shows, and an indication rather than a promise on one with it.

    Writing through `field.value` leaves the field's own on_change to store it, so this needs
    to know nothing about the component being edited -- the same division the Show When picker
    keeps to.
    """
    with ui.menu().props("auto-close").classes("max-h-96"), ui.column().classes("gap-0 p-1"):
        for name, css in sceneview.V2_MATERIAL_PALETTE.items():
            with ui.item(on_click=lambda _e=None, n=name: field.set_value(n)).props("dense clickable"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.element("div").style(f"{_V2_SWATCH_STYLE} background: {css};")
                    ui.label(name).classes("text-sm font-mono")
                    ui.space()
                    ui.label(css).classes("text-xs text-gray-500 font-mono")


def _build_state_field(item: dict, field: sceneedit.V2StateField) -> None:
    """One of the Screen Builder's state properties -- Enabled, Content format: a pulldown of
    its states, and, for Dynamic only, the text or %variable to be evaluated when the Scene is
    shown.

    Two widgets rather than one list of everything, because the settling states and the value
    behind Dynamic are not alternatives to each other: On *is* the answer, Dynamic says where
    the answer will come from.  The value box is shown and hidden rather than created and
    destroyed, so that switching to Off to try something and back to Dynamic doesn't lose what
    was typed.

    Each box writes the whole property on every change (sceneedit.v2_set_state takes the state
    and the value together), since neither the state nor the box alone says what to store.
    """
    stored = item.get(field.key, "")
    state = sceneedit.v2_state_of(field, stored)
    # Guards the prompt below against firing while this field is still being built.  Nothing
    # in NiceGUI 3.15 raises on_change from a constructor, so this is belt and braces -- but
    # the cost of being wrong is a picker dialog opening by itself every time a component that
    # happens to hold a variable is selected in the tree.
    ready = {"user": False}

    def value_of(state_name: str) -> str:
        return str((dynamic_input if state_name == sceneedit.V2_DYNAMIC_STATE else variable_input).value or "")

    def write() -> None:
        chosen = str(state_select.value or "")
        sceneedit.v2_set_state(field, item, chosen, value_of(chosen))

    def state_changed() -> None:
        """Write the new state, and -- this being what Select Variable *is* -- put the picker
        up as soon as it is chosen, rather than making the user find a button afterwards.
        """
        write()
        if ready["user"] and state_select.value == sceneedit.V2_VARIABLE_STATE:
            pick_variable()

    def pick_variable() -> None:
        _build_show_when_dialog(
            variable_input,
            sceneedit.v2_dynamic_variable_choices(),
            f"Select a variable for {field.label}",
        )

    state_select = (
        ui
        .select(
            list(field.states),
            value=state or None,
            label=translate_string(field.label),
            clearable=True,
            on_change=lambda _e=None: state_changed(),
        )
        .props("dense")
        .classes("w-full")
    )
    with state_select:
        ui.tooltip(
            translate_string("Dynamic and Select Variable are worked out when the Scene is shown."),
        )

    dynamic_input = (
        ui
        .input(
            translate_string("Dynamic value"),
            value=sceneedit.v2_state_value(field, stored, sceneedit.V2_DYNAMIC_STATE),
            on_change=lambda _e=None: write(),
        )
        .props("dense")
        .classes("w-full")
    )
    dynamic_input.bind_visibility_from(
        state_select,
        "value",
        backward=lambda value: value == sceneedit.V2_DYNAMIC_STATE,
    )

    variable_input = (
        ui
        .input(
            translate_string("Variable"),
            value=sceneedit.v2_state_value(field, stored, sceneedit.V2_VARIABLE_STATE),
            on_change=lambda _e=None: write(),
        )
        .props("dense")
        .classes("w-full")
    )
    variable_input.bind_visibility_from(
        state_select,
        "value",
        backward=lambda value: value == sceneedit.V2_VARIABLE_STATE,
    )
    # Shows what was picked, and re-opens the picker: the prompt on choosing the state is the
    # way in, but a variable chosen by mistake needs a way back that isn't "select a different
    # state and select this one again".
    with variable_input.add_slot("append"):
        variable_button = ui.button(icon="playlist_add", on_click=lambda _e=None: pick_variable()).props(
            "flat dense round size=sm",
        )
        with variable_button:
            ui.tooltip(translate_string("Pick from the Scene's environment and global variables."))

    ready["user"] = True


def _build_v2_designer(
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    layout: dict,
) -> None:
    """The Version 2 Scene designer -- phase 1: pick a component out of the tree on the
    left, edit its properties on the right.

    Two panes rather than the read-only outline this replaces, because a component tree is
    navigated and a property sheet is filled in, and those want different shapes.  Both are
    rebuilt wholesale on every selection (`.clear()` then repopulate): the tree because the
    highlight moves, the inspector because a different component has entirely different
    fields.  Rebuilding is why selection is held as a *path* (see sceneedit.v2_flatten) and
    not as a widget reference -- the widgets do not survive, the path does.

    Edits write straight through to the layout dict as they are typed
    (sceneedit.v2_set_prop), rather than being collected from widgets at save time.  The
    inspector's widgets are destroyed on every selection change, so there would be nothing
    left to collect from; and the dict being edited belongs to the dialog's own deep copy of
    the Scene, so nothing reaches the loaded backup until a save button re-encodes it (see
    userintr._apply_scene_field_values).  Cancel discards it by simply not encoding.

    NOT in this phase: adding, deleting, reordering or reparenting components, and editing
    modifiers or event handlers.  Those are carried through untouched -- see sceneedit.py's
    designer section on why in-place editing is what keeps an unchanged Scene re-encoding
    byte-identically.
    """
    # The dict every edit lands in, and the one _apply_scene_field_values re-encodes.
    field_refs["v2_layout"] = layout
    # What is selected: a *run* of adjacent siblings, as the path of its first component and
    # how many of them there are.  One component is the run of one, so nothing here has a
    # single-selection case to special-case.
    #
    # The invariant, which sceneedit.v2_selection_run is what enforces: every component in a
    # run shares a parent and a slot, and their indices are consecutive.  That is what makes
    # a run something a single splice can move, and a selection reaching across two parents
    # something no drag could carry out -- so one is never allowed to exist.
    selection: dict = {"path": (), "count": 1}
    # Snapshots taken before each structural edit. Deep copies of the whole tree, which is
    # affordable at this size (the largest Scene in this repo's backup is 13 components)
    # and far simpler than modelling an inverse for every operation.
    history: list[dict] = []
    scene_name = edited_scene.scene_name
    # Whether the Modifiers / Event handlers sections are open, kept out here because the
    # inspector is rebuilt on every edit -- without this, adding a modifier would collapse
    # the very section you are working in, and adding two in a row would mean re-opening it
    # each time.
    expanded = {"modifiers": False, "handlers": False}
    # The tree's rendered rows, path -> (label widget, depth), rebuilt by render_tree.  Held
    # so retitle_node_labels can reach the selected row's label without a full re-render.
    tree_rows: dict[tuple, tuple] = {}
    # The inspector's own heading for the selected component, held for the same reason.
    inspector_heading: dict = {"label": None}

    if not sceneedit.v2_flatten(layout):
        # No root component at all -- not something Tasker writes, and there is nothing for
        # the tree to hang off, so say so rather than showing an empty designer.
        ui.label(
            translate_string("This Scene's Version 2 layout has no root component, so there is nothing to design."),
        ).classes("text-sm text-orange-600 mt-2")
        return

    _register_canvas_events()
    # This designer's own reorder surface -- unique for the reason _ACTIVE_CANVASES gives:
    # ui.on subscribes app-wide, and the Preview is a second surface over this same layout.
    tree_root = f"mt-v2-tree-{next(_DESIGNER_SEQUENCE)}"

    header = ui.row().classes("w-full items-center gap-2 mt-2")
    with ui.row().classes("w-full gap-3 items-start no-wrap mt-1"):
        tree_pane = ui.column().classes(f"{tree_root} w-2/5 gap-0 p-2 border rounded max-h-80 overflow-auto")
        inspector_pane = ui.column().classes("w-3/5 gap-2 p-2 border rounded max-h-80 overflow-auto")
    toolbar = ui.row().classes("w-full gap-1 items-center mt-1 flex-wrap")

    def snapshot() -> None:
        history.append(copy.deepcopy(layout))

    def restore() -> None:
        if not history:
            return
        previous = history.pop()
        # Replace the contents rather than rebinding: field_refs and the save path hold
        # *this* dict object, so swapping in a new one would leave them on the old tree.
        layout.clear()
        layout.update(previous)
        if not sceneedit.v2_run_is_valid(layout, selection["path"], selection["count"]):
            select_only(())
        render()

    def select_only(path: tuple, count: int = 1) -> None:
        """Set the selection without re-rendering -- for the callers that render anyway."""
        selection["path"] = path
        selection["count"] = max(1, count)

    def select(path: tuple, count: int = 1) -> None:
        select_only(path, count)
        render()

    def select_from_surface(payload: dict) -> None:
        """A click on a tree row or on a component in the Preview.

        Shift extends the selection into a run, but only where a run is a thing that could
        exist: shift-clicking into another container starts a fresh selection there instead
        of refusing the click, because the user is plainly pointing at that component and
        selecting it is the reading that gives them something.
        """
        path = sceneview.v2_decode_path(str(payload.get("path", "")))
        if sceneedit.v2_node_at(layout, path) is None:
            return
        if payload.get("extend"):
            run = sceneedit.v2_selection_run(layout, selection["path"], path)
            if run is not None:
                select(*run)
                return
        select(path)

    def reorder_from_surface(payload: dict) -> None:
        """A run dropped in one of the gaps between its siblings, from either surface."""
        path = sceneview.v2_decode_path(str(payload.get("path", "")))
        count = max(1, int(payload.get("count", 1) or 1))
        if not sceneedit.v2_run_is_valid(layout, path, count):
            return
        snapshot()
        new_path = sceneedit.v2_drop_run(layout, path, count, int(payload.get("before", 0) or 0))
        if new_path is None:
            # The drop landed where the run already was.  Nothing was changed and nothing is
            # said about it -- putting something back where it came from is a thing users do
            # on purpose, not a failed operation.
            history.pop()
            select(path, count)
            return
        select(new_path, count)

    def add_component(node_type: str) -> None:
        snapshot()
        new_path = sceneedit.v2_insert_node(layout, selection["path"], sceneedit.v2_new_node(layout, node_type))
        if new_path is None:
            history.pop()
            ui.notify(translate_string("That component can't go there."), type="warning")
            return
        select(new_path)

    def structural(operation: Callable[[], tuple | None], failure: str, count: int = 1) -> None:
        """Run a move/duplicate that returns a new path, keeping the moved component
        selected -- so a run of Move Up clicks walks one component up the tree instead of
        losing it after the first.

        `count` is what to re-select: the whole run for the operations that move one (Up and
        Down), one component for those that do not.
        """
        snapshot()
        new_path = operation()
        if new_path is None:
            history.pop()
            ui.notify(translate_string(failure), type="warning")
            return
        select(new_path, count)

    def delete_selected() -> None:
        node = sceneedit.v2_node_at(layout, selection["path"])
        node_id = (node or {}).get("id", "")
        references = sceneedit.find_component_id_references(scene_name, node_id)
        snapshot()
        errors = sceneedit.v2_delete_node(layout, selection["path"])
        if errors:
            history.pop()
            for error in errors:
                ui.notify(error, type="negative")
            return
        if references:
            # Warn rather than block: the Task may be obsolete, and the user can undo.
            ui.notify(
                f"Deleted '{node_id}'. {len(references)} Task(s) address it by id: "
                f"{', '.join(references)}. They will no longer find it.",
                type="warning",
                multi_line=True,
                timeout=10000,
            )
        select_only(())
        render()

    def render_tree() -> None:
        tree_rows.clear()
        rows = sceneedit.v2_flatten(layout)
        # How many components share each slot, which is the number of gaps a drop can aim at.
        # Counted off the flattened tree rather than looked up per row: every sibling is a row
        # here, and rows that are siblings are exactly the rows whose paths agree but for
        # their last element.
        siblings = collections.Counter(row.path[:-1] for row in rows if row.path)
        selected = sceneedit.v2_run_paths(selection["path"], selection["count"])
        for row in rows:
            classes = "mt-v2-row text-sm font-mono whitespace-pre cursor-pointer rounded px-1 py-0.5 w-full"
            classes += (
                " bg-blue-600 text-white" if row.path in selected else " hover:bg-blue-100 dark:hover:bg-blue-900"
            )
            # The indent is drawn rather than nested so every row stays one flat, clickable
            # strip -- nested containers would make the click target of a deep node a sliver.
            label = (
                ui
                .label(f"{'  ' * row.depth}{row.label}")
                .classes(classes)
                .on("click", lambda _e=None, path=row.path: select(path))
            )
            # The same two attributes the Preview's components carry, so one script drags
            # both -- where this row sits, and how many gaps its slot has to drop into.
            label.props(
                f'data-path="{sceneview.v2_encode_path(row.path)}" data-sibs="{siblings.get(row.path[:-1], 0)}"',
            )
            tree_rows[row.path] = (label, row.depth)
        tree_pane.props(_v2_selection_props(selection))
        _emit_v2_dragging(
            tree_root,
            f".{tree_root}",
            "mt-v2-row",
            # The rows select themselves through NiceGUI; see _emit_v2_dragging.
            select_on_click=False,
        )

    def retitle_node_labels(node: dict) -> None:
        """Keep both places a component is named by -- its tree row and the inspector's own
        heading -- reading correctly as its Tree label is typed.  Both, because they show the
        same v2_node_label and would otherwise disagree with each other until the next
        re-render.

        A no-op for any other dict prop_input is editing: a modifier or an action can carry a
        treeLabel key of its own and names nothing in the tree.
        """
        if node is not sceneedit.v2_node_at(layout, selection["path"]):
            return
        text = sceneedit.v2_node_label(node)
        row = tree_rows.get(selection["path"])
        if row is not None:
            label, depth = row
            label.set_text(f"{'  ' * depth}{text}")
        if inspector_heading.get("label") is not None:
            inspector_heading["label"].set_text(text)

    def prop_input(item: dict, prop: sceneedit.V2Prop) -> None:
        """One editable field for any dict the designer edits -- a component, a modifier,
        an event or an action.  They all store scalars under named keys, so they all get
        the same handful of widget kinds and the same write-through to sceneedit.v2_set_prop.

        `item` is the thing being edited; `target` is where this particular property is kept,
        which for most of them is the same object and for a Text's styling is the nested one
        it names (sceneedit.v2_prop_dict).  Everything that reads or writes the value goes
        through `target`; the two things that need the component itself -- what type it is, and
        retitling its tree row -- keep using `item`.
        """
        target = sceneedit.v2_prop_dict(item, prop)
        value = target.get(prop.key, "")
        if prop.kind == "task":
            # RunTask names a Task in the loaded backup, so offer the real list rather than
            # a free field -- with_input still allows a name that isn't loaded yet.
            task_names = sorted(PrimeItems.tasker_root_elements.get("all_tasks_by_name", {}))
            ui.select(
                task_names,
                value=str(value) if value != "" else None,
                label=translate_string(prop.label),
                with_input=True,
                on_change=lambda e, k=prop.key, d=target: sceneedit.v2_set_prop(d, k, str(e.value or "")),
            ).props("dense").classes("w-full")
        elif prop.kind == "choice":
            ui.select(
                list(prop.choices),
                value=str(value) if value != "" else None,
                label=translate_string(prop.label),
                with_input=True,
                on_change=lambda e, k=prop.key, d=target: sceneedit.v2_set_prop(d, k, str(e.value or "")),
            ).props("dense").classes("w-full")
        elif prop.kind == "state" and (state_field := sceneedit.v2_state_field(prop.key)) is not None:
            _build_state_field(target, state_field)
        elif prop.kind in ("color", "colorvar"):
            _build_colour_field(target, prop)
        elif prop.kind == "icon":
            _build_icon_field(target, prop)
        else:
            text_input = (
                ui
                .input(
                    translate_string(prop.label),
                    value=str(value),
                    on_change=lambda e, k=prop.key, d=target: sceneedit.v2_set_prop(d, k, str(e.value or "")),
                )
                .props("dense")
                .classes("w-full")
            )
            if prop.key == "showWhen":
                # A Show When is built out of variables nobody remembers the spelling of --
                # %sv2_render_is_landscape is not something to type from memory, and a
                # misspelling doesn't fail, it just silently never matches.  So the field
                # carries a picker for all three categories of them.
                with text_input.add_slot("append"):
                    show_when_button = ui.button(
                        icon="playlist_add",
                        on_click=lambda _e=None, w=text_input: _build_show_when_dialog(w),
                    ).props("flat dense round size=sm")
                    with show_when_button:
                        ui.tooltip(translate_string("Pick from the Scene's environment and global variables."))
            elif prop.kind in ("textvar", "numvar"):
                # Fill it in, or point it at a variable.  One field for both, rather than the
                # state fields' pulldown-and-box, because there is nothing to choose between:
                # a max lines of "2" and a max lines of "%line_budget" are the same property
                # written two ways, and neither is a state the other isn't.
                with text_input.add_slot("append"):
                    _variable_picker_button(text_input, prop.label)
            # Either of the two properties a component can be named by: its treeLabel, or --
            # for a Text, which is named by what it says -- its own text (see
            # sceneedit.v2_node_name).  A change to whichever names *this* node has to reach
            # the tree row.  The row is retitled in place rather than the panes being
            # re-rendered, for two reasons: a rebuild on every keystroke would destroy the
            # field being typed into and take the caret with it, and deferring the rebuild to
            # the field's blur doesn't work -- Quasar's blur does not reach a NiceGUI
            # .on("blur") handler here, so the row would simply sit stale until the next click.
            names_node = prop.key in ("treeLabel", sceneedit.V2_LABEL_FALLBACK.get(str(item.get("type", "")), ""))
            if names_node:
                text_input.on_value_change(lambda _e=None, d=item: retitle_node_labels(d))

    def structural_edit(mutate: Callable[[], object]) -> None:
        """Snapshot, mutate, re-render -- the wrapper every add/remove/reorder inside the
        inspector goes through, so all of them land on the same undo stack as the tree's.
        """
        snapshot()
        mutate()
        render()

    def render_binding(node: dict) -> None:
        slot = sceneedit.v2_binding_slot(node)
        if slot is None:
            return
        state_key, binding_key = slot
        ui.label(f"{translate_string('Writes to variable')} ({state_key}.{binding_key})").classes(
            "text-xs uppercase text-gray-500 mt-2",
        )
        ui.input(
            translate_string("Tasker variable(s)"),
            value=sceneedit.v2_get_binding(node, slot),
            on_change=lambda e, n=node, s=slot: sceneedit.v2_set_binding(n, s, str(e.value or "")),
        ).props("dense").classes("w-full").tooltip(
            translate_string(
                "The Tasker variable this component writes its value into. "
                "Separate several with commas. Leave empty to declare the binding without setting it.",
            ),
        )

    def render_modifiers(node: dict) -> None:
        modifiers = sceneedit.v2_modifiers(node)
        with ui.expansion(
            f"{translate_string('Modifiers')} ({len(modifiers)})",
            icon="tune",
            value=expanded["modifiers"],
            on_value_change=lambda e: expanded.__setitem__("modifiers", bool(e.value)),
        ).classes("w-full mt-2"):
            ui.label(
                translate_string("Applied in order — the one at the bottom sits on top."),
            ).classes("text-xs text-gray-500 italic")
            for index, modifier in enumerate(modifiers):
                with ui.card().classes("w-full p-2 gap-1"):
                    with ui.row().classes("w-full items-center gap-1"):
                        ui.label(modifier.get("type", "?")).classes("text-sm font-mono font-semibold")
                        ui.space()
                        ui.button(
                            icon="arrow_upward",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_move_modifier(node, i, -1),
                            ),
                        ).props("dense flat size=sm")
                        ui.button(
                            icon="arrow_downward",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_move_modifier(node, i, 1),
                            ),
                        ).props("dense flat size=sm")
                        ui.button(
                            icon="close",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_delete_modifier(node, i),
                            ),
                        ).props("dense flat size=sm color=negative")
                    for prop in sceneedit.v2_schema_props(
                        sceneedit.V2_MODIFIER_SCHEMA,
                        modifier,
                        sceneedit.V2_MODIFIER_UNIVERSAL_PROPS,
                    ):
                        prop_input(modifier, prop)
            add_modifier = ui.button(translate_string("Add modifier"), icon="add").props("dense flat")
            with add_modifier, ui.menu():
                for modifier_type in sceneedit.V2_MODIFIER_SCHEMA:
                    ui.menu_item(
                        modifier_type,
                        on_click=lambda _e=None, t=modifier_type: structural_edit(
                            lambda: sceneedit.v2_add_modifier(node, t),
                        ),
                    ).props("dense")

    def render_handlers(node: dict) -> None:
        handlers = sceneedit.v2_handlers(node)
        with ui.expansion(
            f"{translate_string('Event handlers')} ({len(handlers)})",
            icon="bolt",
            value=expanded["handlers"],
            on_value_change=lambda e: expanded.__setitem__("handlers", bool(e.value)),
        ).classes("w-full mt-1"):
            for index, handler in enumerate(handlers):
                events = handler.get("events") or []
                with ui.card().classes("w-full p-2 gap-1"):
                    with ui.row().classes("w-full items-center gap-1"):
                        ui.label(
                            translate_string("On") + " " + ", ".join(e.get("type", "?") for e in events),
                        ).classes("text-sm font-mono font-semibold")
                        ui.space()
                        ui.button(
                            icon="close",
                            on_click=lambda _e=None, i=index: structural_edit(
                                lambda: sceneedit.v2_delete_handler(node, i),
                            ),
                        ).props("dense flat size=sm color=negative")
                    for event in events:
                        for prop in sceneedit.v2_schema_props(sceneedit.V2_EVENT_SCHEMA, event):
                            prop_input(event, prop)
                    # A handler-level condition gates the whole thing; the 'V2' Scene uses
                    # one to run only in portrait.
                    ui.input(
                        translate_string("Only when"),
                        value=str(handler.get("condition", "")),
                        on_change=lambda e, h=handler: sceneedit.v2_set_prop(h, "condition", str(e.value or "")),
                    ).props("dense").classes("w-full")

                    actions = handler.get("actions") or []
                    ui.label(f"{translate_string('Actions')} ({len(actions)})").classes(
                        "text-xs uppercase text-gray-500 mt-1",
                    )
                    for action_index, action in enumerate(actions):
                        with ui.row().classes("w-full items-center gap-1"):
                            ui.label(action.get("type", "?")).classes("text-xs font-mono")
                            ui.space()
                            ui.button(
                                icon="arrow_upward",
                                on_click=lambda _e=None, h=handler, a=action_index: structural_edit(
                                    lambda: sceneedit.v2_move_action(h, a, -1),
                                ),
                            ).props("dense flat size=sm")
                            ui.button(
                                icon="arrow_downward",
                                on_click=lambda _e=None, h=handler, a=action_index: structural_edit(
                                    lambda: sceneedit.v2_move_action(h, a, 1),
                                ),
                            ).props("dense flat size=sm")
                            ui.button(
                                icon="close",
                                on_click=lambda _e=None, h=handler, a=action_index: structural_edit(
                                    lambda: sceneedit.v2_delete_action(h, a),
                                ),
                            ).props("dense flat size=sm color=negative")
                        for prop in sceneedit.v2_schema_props(sceneedit.V2_ACTION_SCHEMA, action):
                            prop_input(action, prop)

                    add_action = ui.button(translate_string("Add action"), icon="add").props("dense flat size=sm")
                    with add_action, ui.menu():
                        for action_type in sceneedit.V2_ACTION_TYPES:
                            ui.menu_item(
                                action_type,
                                on_click=lambda _e=None, h=handler, t=action_type: structural_edit(
                                    lambda: sceneedit.v2_add_action(h, t),
                                ),
                            ).props("dense")

            add_handler = ui.button(translate_string("Add handler"), icon="add").props("dense flat")
            with add_handler, ui.menu():
                for event_type in sceneedit.V2_EVENT_TYPES:
                    ui.menu_item(
                        event_type,
                        on_click=lambda _e=None, t=event_type: structural_edit(
                            lambda: sceneedit.v2_add_handler(node, t),
                        ),
                    ).props("dense")

    def render_prop(node: dict, prop: sceneedit.V2Prop) -> None:
        """One property of the selected component.

        Everything goes through prop_input except the component's own id, which is applied by
        v2_rename_id rather than v2_set_prop: an id has to stay unique, and Tasks address
        components by it (see rename_id below).  `prop.container` is what tells that id apart
        from a nested key that merely happens to be called "id".
        """
        if prop.key != "id" or prop.container:
            prop_input(node, prop)
            return

        value = node.get(prop.key, "")
        id_input = ui.input(translate_string(prop.label), value=str(value)).props("dense").classes("w-full")
        id_input.on("blur", lambda _e=None, w=id_input, p=selection["path"]: rename_id(p, w))
        references = sceneedit.find_component_id_references(scene_name, str(value))
        if references:
            ui.label(
                f"{translate_string('Addressed by id from')}: {', '.join(references)}",
            ).classes("text-xs text-orange-600 italic")

    def render_category(node: dict, name: str, props: list) -> None:
        """One named section of the property sheet, for the types that have them.

        Open/closed is remembered in `expanded` for the same reason the Modifiers section's is:
        the inspector is rebuilt on every edit, so a section that didn't remember would shut
        itself the moment you typed in it.  It is keyed by category name rather than by
        component, so walking down a column of Texts keeps the section you are working in open
        instead of making you reopen it at every stop.

        The caption counts what is actually set.  With eight sections and fifty-odd fields
        behind them, "which of these has anything in it" is the question the closed sheet has
        to answer -- otherwise finding the one shadow colour a Scene sets means opening all
        eight.

        It is recounted when the section is toggled rather than on every keystroke, because
        the inspector is not rebuilt as you type (see the treeLabel note in prop_input) and a
        count that never recounted would still read 2/11 after you had filled in a third.
        Toggling is when the number is actually read: an open section shows its own fields, so
        the only caption anyone looks at is one that has just been -- or is about to be --
        closed.
        """
        key = f"category:{name}"
        expanded.setdefault(key, name in sceneedit.V2_OPEN_CATEGORIES)

        def caption() -> str:
            filled = sum(1 for prop in props if str(sceneedit.v2_prop_dict(node, prop).get(prop.key, "")) != "")
            return f"{filled}/{len(props)}"

        def toggled(value: object) -> None:
            expanded[key] = bool(value)
            section.props(f'caption="{caption()}"')

        section = (
            ui
            .expansion(
                translate_string(name),
                icon=_V2_CATEGORY_ICONS.get(name, "tune"),
                caption=caption(),
                value=expanded[key],
                on_value_change=lambda e: toggled(e.value),
            )
            .props("dense")
            .classes("w-full")
        )
        with section, ui.column().classes("w-full gap-2 pb-2"):
            for prop in props:
                render_prop(node, prop)

    def render_inspector() -> None:
        node = sceneedit.v2_node_at(layout, selection["path"])
        if node is None:
            ui.label(translate_string("Select a component on the left.")).classes("text-sm italic text-gray-500")
            return

        inspector_heading["label"] = ui.label(sceneedit.v2_node_label(node)).classes(
            "text-sm font-semibold font-mono",
        )
        for name, props in sceneedit.v2_property_groups(node):
            if not name:
                # The flat list every type but Text still gets -- see v2_property_groups.
                for prop in props:
                    render_prop(node, prop)
                continue
            render_category(node, name, props)

        render_binding(node)
        render_modifiers(node)
        render_handlers(node)

    def rename_id(path: tuple, widget: ui.input) -> None:
        """Applies the id field on blur rather than on every keystroke -- a partially-typed
        id would otherwise be checked for uniqueness mid-word and rejected for colliding
        with itself.
        """
        node = sceneedit.v2_node_at(layout, path)
        if node is None or str(widget.value).strip() == node.get("id", ""):
            return
        snapshot()
        errors = sceneedit.v2_rename_id(layout, path, str(widget.value))
        if errors:
            history.pop()
            for error in errors:
                ui.notify(error, type="negative")
            widget.value = node.get("id", "")
            return
        render()

    def render_header() -> None:
        rows = sceneedit.v2_flatten(layout)
        ui.label(f"{translate_string('Scene Components')} ({len(rows)})").classes("text-sm font-semibold")
        ui.space()
        add_button = ui.button(
            translate_string("Add"),
            icon="add",
            on_click=lambda: _build_add_element_dialog(layout, selection["path"], add_component),
        ).props("dense flat")
        with add_button:
            ui.tooltip(
                translate_string(
                    "Adds inside the selected component if it can hold children, otherwise directly after it.",
                ),
            )
        ui.button(translate_string("Undo"), icon="undo", on_click=restore).props("dense flat").set_enabled(
            bool(history),
        )

    def render_toolbar() -> None:
        """The structural operations.

        Up and Down move the whole selected run; everything else is a one-component
        operation and is switched off while a run is selected, rather than quietly acting on
        the first of them.  Deleting three highlighted components and keeping two is the kind
        of surprise an Undo does not really undo.
        """
        node = sceneedit.v2_node_at(layout, selection["path"])
        is_root = not selection["path"]
        run = selection["count"]
        for label, icon, handler, failure in (
            (
                "Up",
                "arrow_upward",
                lambda: sceneedit.v2_move_run(layout, selection["path"], selection["count"], -1),
                "Already first.",
            ),
            (
                "Down",
                "arrow_downward",
                lambda: sceneedit.v2_move_run(layout, selection["path"], selection["count"], 1),
                "Already last.",
            ),
            (
                "Out",
                "format_indent_decrease",
                lambda: sceneedit.v2_outdent_node(layout, selection["path"]),
                "Nothing to move it out to.",
            ),
            (
                "In",
                "format_indent_increase",
                lambda: sceneedit.v2_indent_node(layout, selection["path"]),
                "The component above it can't hold children.",
            ),
            (
                "Duplicate",
                "content_copy",
                lambda: sceneedit.v2_duplicate_node(layout, selection["path"]),
                "The root component can't be duplicated.",
            ),
        ):
            moves_run = label in ("Up", "Down")
            ui.button(
                translate_string(label),
                icon=icon,
                on_click=lambda _e=None, op=handler, f=failure, c=(run if moves_run else 1): structural(op, f, c),
            ).props("dense flat").set_enabled(node is not None and not is_root and (moves_run or run == 1))
        ui.button(translate_string("Delete"), icon="delete", on_click=delete_selected).props(
            "dense flat color=negative",
        ).set_enabled(node is not None and not is_root and run == 1)
        ui.space()
        ui.label(
            translate_string(
                (
                    "Drag to reorder. Shift-click a component in the same container to take several at once."
                    if run == 1
                    else f"{run} components selected — they move together."
                ),
            ),
        ).classes("text-xs text-gray-500 italic")

    def render() -> None:
        # Re-registered on every render because the handlers close over nothing that changes,
        # but the table is what a re-opened dialog's surface has to be found in again.
        _ACTIVE_CANVASES[tree_root] = {"v2select": select_from_surface, "v2reorder": reorder_from_surface}
        # What the Preview needs to be the second surface over this same layout, and why it
        # is handed these three rather than a copy of them:
        #
        #   handlers  -- the Preview's drags run *these* closures, so a reorder made in the
        #                picture lands on this designer's undo stack instead of a second one
        #                that its Undo button knows nothing about.
        #   selection -- the same dict object, so the run outlined in the picture and the run
        #                highlighted in the tree cannot disagree.
        #
        #   rerender  -- called when the dialog comes back, because re-opening it rebuilds the
        #                tree pane's DOM and the drag handlers have to be put back on the new
        #                one.  See NiceGuiSceneView._back_to_editor.
        #
        # Running this designer's handlers is also what keeps the tree from going stale while
        # it is hidden: they end in render(), so the pane the Preview is covering is rebuilt
        # as the drag lands rather than coming back showing the order from before it.
        field_refs["v2_edit"] = {
            "handlers": _ACTIVE_CANVASES[tree_root],
            "selection": selection,
            "rerender": render,
        }
        header.clear()
        tree_pane.clear()
        inspector_pane.clear()
        toolbar.clear()
        with header:
            render_header()
        with tree_pane:
            render_tree()
        with inspector_pane:
            render_inspector()
        with toolbar:
            render_toolbar()

    render()


# ==========================================
# The Scene canvas, shared by the read-only Preview and the Legacy designer.
#
# Both draw the same thing (sceneview.draw_scene) at the Scene's true pixel size and then
# scale the whole canvas to fit.  The fitting has to happen in the browser -- the width to
# fit into is the viewport's, which the server does not know -- so it goes out as JavaScript,
# and the two callers scope it to their own wrapper class because a Preview and a designer
# can be on the page at the same time (the Preview is in the main column, the designer is in
# a dialog that is only hidden while the Preview is up).  A bare ".mt-scene-wrap" selector
# would have found whichever came first and scaled the wrong one.
# ==========================================
CANVAS_PREVIEW_ROOT = "mt-preview"
CANVAS_DESIGNER_ROOT = "mt-designer"
# How much of the Scene dialog the designer's canvas may take.  It shares that dialog with a
# size row, an element list, a property sheet and a button row, so the canvas is fitted to
# this as well as to the width -- see _emit_canvas_fit's `budget`.  The Preview, which has a
# 70vh scroll area to itself, has no such limit.
DESIGNER_CANVAS_HEIGHT = 300


def _emit_canvas_fit(root: str, width: int, height: int, fixed: str = "null", budget: int = 0) -> None:
    """Scale the canvas under `root` to fit its wrapper, and keep it fitting on resize.

    `fixed` is a scale factor as a JS literal, or "null" for fit-to-width.  `budget` is a
    height in pixels the canvas must also fit inside, or 0 for none -- the Preview has a
    scroll area of its own and wants the full width, but the designer sits in a dialog
    alongside a list, a property sheet and a button row, and a tall Scene scaled to the
    width alone would push all of them off the screen.

    The wrapper's dataset carries the resulting scale, because the pointer handlers need it
    to turn screen pixels into canvas pixels and re-deriving it from the CSS transform would
    be reading back a number this already computed.

    THE SCALE GOES INTO A STYLESHEET RULE, NOT AN INLINE STYLE, and that is not a matter of
    taste.  The canvas element is rebuilt by NiceGUI on every re-render and its inline style
    is patched from the server's own copy of it -- which knows nothing about a transform this
    script added -- so an inline transform survives the first render and is silently wiped by
    the next one.  The symptom is a canvas that quietly reverts to full size after any edit,
    with every coordinate the pointer handlers compute wrong by the scale factor.  A rule in
    a stylesheet is outside what that patching touches, and nothing on the Python side sets
    `transform`, so the two can never fight over it.

    The resize handler is kept on `window` under this root's name and removed before the next
    one is added -- every re-render would otherwise leave another one behind, and after a
    dozen drags the browser would be recomputing the same layout a dozen times per resize.
    """
    ui.run_javascript(
        f"""
        (() => {{
            const root = '{root}', canvasWidth = {width}, canvasHeight = {height};
            const fixed = {fixed}, budget = {budget};
            const styleId = 'mt-scene-fit-' + root;
            let sheet = document.getElementById(styleId);
            if (!sheet) {{
                sheet = document.createElement('style');
                sheet.id = styleId;
                document.head.appendChild(sheet);
            }}
            const apply = () => {{
                const wrap = document.querySelector('.' + root);
                if (!wrap || !wrap.querySelector('.mt-scene-canvas')) return;
                const byWidth = (wrap.clientWidth - 16) / canvasWidth;
                const byHeight = budget ? (budget - 8) / canvasHeight : Infinity;
                const scale = fixed !== null
                    ? fixed
                    : Math.max(0.05, Math.min(1, byWidth, byHeight));
                // flex-shrink: 0 is not decoration.  The wrapper sits in a flex column (a
                // NiceGUI card is one), and a flex item's height is only a basis -- when the
                // dialog's content is taller than the dialog, flex shrinks the item and the
                // stated height is simply ignored.  The symptom is a canvas squashed to a
                // sliver with everything below its clip line unclickable.
                sheet.textContent =
                    '.' + root + ' .mt-scene-canvas {{ transform: scale(' + scale + '); }}' +
                    '.' + root + ' {{ height: ' + (canvasHeight * scale + 8) + 'px;' +
                    ' flex: none;' +
                    ' overflow-x: ' + (canvasWidth * scale > wrap.clientWidth ? 'auto' : 'hidden') + '; }}';
                wrap.dataset.scale = scale;
            }};
            window.__mtSceneFit = window.__mtSceneFit || {{}};
            if (window.__mtSceneFit[root]) window.removeEventListener('resize', window.__mtSceneFit[root]);
            window.__mtSceneFit[root] = apply;
            window.addEventListener('resize', apply);
            apply();
            requestAnimationFrame(apply);
        }})();
        """,
    )


def _emit_v2_hull(root: str, width: int, height: int) -> None:
    """Size the box behind a Version 2 layout to everything that layout occupies on screen.

    THE MEASURING HAS TO HAPPEN IN THE BROWSER, and for the same reason the fitting above
    does: the numbers do not exist anywhere else.  A Legacy element carries its box in the
    XML, so its extent is arithmetic Python can do; a V2 component is a flex item whose size
    and position are whatever the browser works out from its siblings, its text and the width
    of the screen it was dropped into.  Nothing on the server knows where any of it landed.

    WHICH COMPONENTS COUNT: the defined elements, not the space they were handed.  A leaf --
    a component with nothing inside it -- always counts; it is a thing the Scene draws,
    whatever size it is.  A container counts only when it paints something of its own (a
    background, a border, a shadow) AND does not fill the screen.

    Both halves of that are needed, and each was learned from a real Scene.  A container that
    paints has to be counted or the box would cut through the ring it draws round its
    children ($V2 Test's header is an ellipse wider than anything inside it).  But a
    container that fills the screen has to be skipped even when it paints, because a
    container is stretched by its parent rather than sized by its contents -- $V2 Test's root
    Column paints a 1px border and is handed the whole screen, so counting it drew the box
    round the screen and said nothing about where the Scene's elements are.  A leaf that
    happens to fill the screen is a different matter and still counts: a full-screen image is
    the content rather than the room it was given.

    The result is clamped to the screen, because a component that overflows the frame is
    clipped by it (the frame carries overflow: hidden) and a hull round the part nobody can
    see would be drawing the layout the Scene does not have.  V2_HULL_PADDING is added first
    -- see sceneview for why the box needs a rim it can be seen by.

    Measured again on the next frame, when the web fonts settle and once more shortly after:
    text that reflows when Roboto arrives moves the very edges this is measuring, and a box
    left at the pre-font size would be visibly wrong against the layout it encloses.  No
    listener is left behind -- the hull is in canvas coordinates, which the fit's scaling
    does not change -- so nothing here accumulates across renders.
    """
    ui.run_javascript(
        f"""
        (() => {{
            const root = '{root}', canvasWidth = {width}, canvasHeight = {height};
            const pad = {sceneview.V2_HULL_PADDING};
            const compSel = '.{sceneview.V2_COMPONENT_CLASS}';
            const wrap = document.querySelector('.' + root);
            const canvas = wrap && wrap.querySelector('.mt-scene-canvas');
            const hull = canvas && canvas.querySelector('.{sceneview.V2_HULL_CLASS}');
            if (!hull) return;

            // Does this component put anything on the screen itself, beyond its children?
            const paints = (el) => {{
                const style = getComputedStyle(el);
                if (style.backgroundImage !== 'none' || style.boxShadow !== 'none') return true;
                if (parseFloat(style.borderTopWidth) || parseFloat(style.borderRightWidth)
                    || parseFloat(style.borderBottomWidth) || parseFloat(style.borderLeftWidth)) return true;
                // "rgb(...)" is opaque; "rgba(..., 0)" is the transparent default.
                const parts = (style.backgroundColor.match(/[\\d.]+/g) || []).map(Number);
                return parts.length === 3 || (parts.length > 3 && parts[3] > 0.01);
            }};

            const measure = () => {{
                const origin = canvas.getBoundingClientRect();
                // Screen pixels back to canvas pixels: the canvas is drawn at its true size
                // and scaled as a whole by _emit_canvas_fit, which leaves the factor here.
                const scale = parseFloat(wrap.dataset.scale || '1') || 1;
                // A box within a pixel of the screen in both directions is the screen: this
                // component was stretched to what it was given, wherever the elements are.
                const fillsScreen = (box) => box.width / scale >= canvasWidth - 1
                                          && box.height / scale >= canvasHeight - 1;
                let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
                for (const el of canvas.querySelectorAll(compSel)) {{
                    const box = el.getBoundingClientRect();
                    if (el.querySelector(compSel) && (!paints(el) || fillsScreen(box))) continue;
                    if (!box.width && !box.height) continue;
                    left = Math.min(left, box.left); top = Math.min(top, box.top);
                    right = Math.max(right, box.right); bottom = Math.max(bottom, box.bottom);
                }}
                if (!isFinite(left)) {{ hull.style.display = 'none'; return; }}
                const x = Math.max(0, (left - origin.left) / scale - pad);
                const y = Math.max(0, (top - origin.top) / scale - pad);
                const w = Math.min(canvasWidth, (right - origin.left) / scale + pad) - x;
                const h = Math.min(canvasHeight, (bottom - origin.top) / scale + pad) - y;
                if (w <= 0 || h <= 0) {{ hull.style.display = 'none'; return; }}
                hull.style.left = x + 'px';
                hull.style.top = y + 'px';
                hull.style.width = w + 'px';
                hull.style.height = h + 'px';
                hull.style.display = 'block';
            }};

            measure();
            requestAnimationFrame(measure);
            setTimeout(measure, 300);
            if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
        }})();
        """,
    )


def _emit_canvas_editing(root: str, snap: int) -> None:
    """Install the pointer and keyboard handlers that make the canvas draggable.

    THE WHOLE DRAG HAPPENS IN THE BROWSER.  Only the finished geometry is sent back, once,
    on pointer-up: a round trip per mousemove would be unusable over a websocket, and it
    would also put one undo entry on the stack per pixel travelled instead of one per gesture.

    SELECTION IS ALSO REPORTED ON POINTER-UP, not on pointer-down, and that ordering is
    load-bearing rather than incidental.  Selecting re-renders all three panes from Python,
    which replaces the very DOM node the pointer is captured on -- so selecting first and
    dragging second would tear the element out from under the drag on every click. Reporting
    a click only when the pointer did not move keeps the two apart: a click selects, a drag
    moves, and a drag reports the elements it moved so Python can select them afterwards.

    MORE THAN ONE ELEMENT CAN BE SELECTED, and a drag moves all of them by the same delta.
    Which elements those are is read off the canvas rather than held here, for the same
    reason the selected element always was: Python re-renders the canvas on every change and
    a value cached in this closure would be describing the render before last.

    A PRESS ON THE BARE CANVAS IS TWO GESTURES until it ends: released where it started it is
    a click that clears the selection, dragged it is a rubber band that takes everything it
    encloses.  Both leave as mt_scene_select, one carrying an sr and the other a list of them
    -- see the finish() below and select_from_canvas, which is what reads them apart.

    Handlers are attached to the canvas element itself, which draw_scene rebuilds on every
    render, so they are disposed of with it and can never accumulate.  The one exception is
    the resize listener in _emit_canvas_fit, which is on `window` and is removed by name.

    EVERY EVENT CARRIES ITS ROOT.  ui.on subscribes app-wide, and there can be more than one
    designer on the page -- editing a List's item layout opens a second one, on the nested
    Scene, while the first is still mounted behind it.  Without the root in the payload both
    would answer every click, and the outer designer would apply the inner one's drags to
    whatever element of the outer Scene happened to share its sr.
    """
    ui.run_javascript(
        f"""
        (() => {{
            const root = '{root}', snap = {max(1, snap)};
            const wrap = document.querySelector('.' + root);
            const canvas = wrap && wrap.querySelector('.mt-scene-canvas');
            if (!canvas) return;
            const scale = () => parseFloat(wrap.dataset.scale || '1') || 1;
            const round = (value) => Math.round(value / snap) * snap;
            let drag = null;

            // What is selected right now, straight off the canvas -- see the docstring.
            const selected = () => (canvas.dataset.selected || '').split(' ').filter(Boolean);
            const box = (sr) => {{
                const node = canvas.querySelector('.mt-el[data-sr="' + sr + '"]');
                return node && {{
                    sr,
                    x: parseFloat(node.dataset.x), y: parseFloat(node.dataset.y),
                    w: parseFloat(node.dataset.w), h: parseFloat(node.dataset.h),
                }};
            }};

            const place = (next) => {{
                const target = canvas.querySelector('.mt-el[data-sr="' + next.sr + '"]');
                const overlay = canvas.querySelector('.mt-selection[data-sr="' + next.sr + '"]');
                for (const node of [target, overlay]) {{
                    if (!node) continue;
                    node.style.left = next.x + 'px';
                    node.style.top = next.y + 'px';
                    node.style.width = next.w + 'px';
                    node.style.height = next.h + 'px';
                }}
            }};

            // ---- the rubber band ----
            //
            // Where the pointer is in the Scene's own coordinates.  The canvas is scaled by
            // one CSS transform with transform-origin: top left, so its client rect's corner
            // *is* canvas 0,0 and dividing by the scale is the whole conversion.
            let band = null;
            const point = (event) => {{
                const rect = canvas.getBoundingClientRect();
                return {{ x: (event.clientX - rect.left) / scale(), y: (event.clientY - rect.top) / scale() }};
            }};
            const spanned = (from, to) => ({{
                x: Math.min(from.x, to.x), y: Math.min(from.y, to.y),
                w: Math.abs(to.x - from.x), h: Math.abs(to.y - from.y),
            }});

            // WHOLLY INSIDE THE BAND, not merely touched by it -- and that is a fact about
            // Legacy Scenes rather than a preference.  Most real ones are built on a
            // full-canvas RectElement as a background (it is why paint_order exists), and
            // under a touch rule every band anywhere would catch it, so every marquee would
            // quietly pick up the background and drag it along with whatever was wanted.
            // Requiring containment makes that element reachable only by a band drawn round
            // the whole canvas -- which reads as "select everything", and is.
            const enclosed = (area) => [...canvas.querySelectorAll('.mt-el')].filter((node) => {{
                const x = parseFloat(node.dataset.x), y = parseFloat(node.dataset.y);
                const w = parseFloat(node.dataset.w), h = parseFloat(node.dataset.h);
                return x >= area.x && y >= area.y
                    && x + w <= area.x + area.w && y + h <= area.y + area.h;
            }}).map((node) => node.dataset.sr);

            const drawBand = (area) => {{
                if (!band) {{
                    band = document.createElement('div');
                    band.className = 'mt-marquee';
                    band.style.cssText = 'position: absolute; z-index: 11; pointer-events: none;'
                        + 'box-sizing: border-box; border: 1px dashed rgba(37,99,235,0.95);'
                        + 'background: rgba(37,99,235,0.10);';
                    canvas.appendChild(band);
                }}
                band.style.left = area.x + 'px';
                band.style.top = area.y + 'px';
                band.style.width = area.w + 'px';
                band.style.height = area.h + 'px';
            }};

            canvas.addEventListener('pointerdown', (event) => {{
                const handle = event.target.closest('.mt-handle');
                const picked = selected();
                const element = handle ? canvas.querySelector('.mt-el[data-sr="' + picked[picked.length - 1] + '"]')
                                       : event.target.closest('.mt-el');
                event.preventDefault();
                canvas.focus();
                if (!element) {{
                    // The bare canvas -- a press with nothing under it.  It is the start of
                    // both gestures the background has: released where it began it is a click
                    // that clears the selection (the only way back to none once several are
                    // picked), and dragged it is the rubber band.  Which of the two it was is
                    // not known until the pointer comes up, which is where both are reported.
                    //
                    // The modifier travels either way.  Shift-clicking past everything is a
                    // miss rather than an instruction to drop the selection being built, and
                    // Python does nothing with an empty sr it was asked to add; shift-banding
                    // adds what the band caught to what was already picked.
                    drag = {{
                        sr: '', extend: event.shiftKey || event.ctrlKey || event.metaKey,
                        dir: 'move', box: null, boxes: [], moved: false,
                        startX: event.clientX, startY: event.clientY, from: point(event),
                    }};
                    canvas.setPointerCapture(event.pointerId);
                    return;
                }}
                // Grabbing anything inside the selection drags the whole selection; grabbing
                // anything else drags just that one, and drops the old selection with it.
                // The same rule the Version 2 surface uses (see _emit_v2_dragging), so a drag
                // never quietly moves something the user cannot see is picked out.  A handle
                // is always the single selected element: handles are drawn only for one.
                const group = (!handle && picked.includes(element.dataset.sr))
                    ? picked : [element.dataset.sr];
                drag = {{
                    sr: element.dataset.sr,
                    extend: event.shiftKey || event.ctrlKey || event.metaKey,
                    dir: handle ? handle.dataset.dir : 'move',
                    startX: event.clientX,
                    startY: event.clientY,
                    box: box(element.dataset.sr),
                    boxes: group.map(box).filter(Boolean),
                    moved: false,
                }};
                canvas.setPointerCapture(event.pointerId);
            }});

            canvas.addEventListener('pointermove', (event) => {{
                if (!drag) return;
                if (!drag.box) {{
                    // A press that began on the bare canvas: this is the band being drawn.
                    // The threshold is in screen pixels rather than canvas ones so that it
                    // feels the same however far the canvas is scaled down -- 4 canvas px on
                    // a phone-sized Scene fitted to the pane is well under one real pixel.
                    if (!drag.moved
                        && Math.abs(event.clientX - drag.startX) < 4
                        && Math.abs(event.clientY - drag.startY) < 4) return;
                    drag.moved = true;
                    drag.band = spanned(drag.from, point(event));
                    drawBand(drag.band);
                    return;
                }}
                const dx = (event.clientX - drag.startX) / scale();
                const dy = (event.clientY - drag.startY) / scale();
                if (!drag.moved && Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
                drag.moved = true;
                const start = drag.box;
                if (drag.dir === 'move') {{
                    // THE SNAP IS APPLIED TO THE DELTA, ONCE, not to each element in turn.
                    // Rounding every element's own position to the grid would pull a group
                    // that was laid out 3px apart onto 5px boundaries -- destroying the very
                    // spacing the user selected them together to preserve.  Snapping the
                    // element under the pointer and moving the rest by that same offset keeps
                    // the group rigid and still lands the grabbed one on the grid.
                    const ox = round(start.x + dx) - start.x;
                    const oy = round(start.y + dy) - start.y;
                    drag.next = drag.boxes.map((b) => ({{ sr: b.sr, x: b.x + ox, y: b.y + oy, w: b.w, h: b.h }}));
                }} else {{
                    let {{ x, y, w, h }} = start;
                    if (drag.dir.includes('w')) {{ x = round(start.x + dx); w = start.w + (start.x - x); }}
                    if (drag.dir.includes('n')) {{ y = round(start.y + dy); h = start.h + (start.y - y); }}
                    if (drag.dir.includes('e')) {{ w = round(start.w + dx); }}
                    if (drag.dir.includes('s')) {{ h = round(start.h + dy); }}
                    // An element may sit off the canvas -- Tasker allows it -- so nothing is
                    // clamped to the edges; only a collapse to nothing is refused.
                    drag.next = [{{ sr: start.sr, x, y, w: Math.max(1, w), h: Math.max(1, h) }}];
                }}
                drag.next.forEach(place);
            }});

            const finish = (event) => {{
                if (!drag) return;
                const finished = drag;
                drag = null;
                if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
                // Taken away before anything is reported: reporting re-renders the canvas
                // from Python, and a band left behind would be a stray div inside the very
                // element being replaced.
                if (band) {{ band.remove(); band = null; }}
                if (finished.band) {{
                    emitEvent('mt_scene_select', {{ root, srs: enclosed(finished.band), extend: finished.extend }});
                }} else if (finished.moved && finished.next) {{
                    emitEvent('mt_scene_geometry', {{ root, moves: finished.next }});
                }} else {{
                    emitEvent('mt_scene_select', {{ root, sr: finished.sr, extend: finished.extend }});
                }}
            }};
            canvas.addEventListener('pointerup', finish);
            canvas.addEventListener('pointercancel', finish);

            // Give the canvas the focus back, because every edit rebuilds it and the
            // replacement starts unfocused -- so without this the arrow keys would work
            // exactly once, until the first nudge re-rendered the element being nudged.
            //
            // Not while the user is typing: an edit in the Inspector re-renders too, and
            // stealing the focus there would eject them from the field after one keystroke.
            const active = document.activeElement;
            if (!active || !active.closest || !active.closest('input, textarea, select, [contenteditable]')) {{
                canvas.focus({{ preventScroll: true }});
            }}

            canvas.addEventListener('keydown', (event) => {{
                if (event.target.closest('input, textarea, select')) return;
                const step = event.shiftKey ? 10 : 1;
                const moves = {{ ArrowLeft: [-step, 0], ArrowRight: [step, 0],
                                ArrowUp: [0, -step], ArrowDown: [0, step] }};
                const move = moves[event.key];
                if (!move) return;
                event.preventDefault();
                emitEvent('mt_scene_nudge', {{ root, dx: move[0], dy: move[1] }});
            }});
        }})();
        """,  # noqa: S608
    )


def _v2_selection_props(selection: dict) -> str:
    """The selected run, as the two attributes the drag script reads off its host.

    Set as element props rather than written from JavaScript so that a surface which is not
    in the document right now -- a designer behind the Preview, whose dialog has detached its
    contents -- still comes back with the run that is selected *now*.  See _emit_v2_dragging.
    """
    return (
        f'data-mt-v2-sel="{sceneview.v2_encode_path(selection["path"])}" '
        f'data-mt-v2-count="{max(1, int(selection["count"]))}"'
    )


def _emit_v2_dragging(
    root: str,
    container: str,
    node_class: str,
    *,
    select_on_click: bool = True,
) -> None:
    """Install the pointer handlers that let a run of Version 2 components be dragged into a
    new position among its siblings.  Used by both surfaces the tree can be reordered on --
    the designer's tree pane and the Preview's canvas -- because the gesture is the same one.

    SIBLINGS ONLY, AND THE GESTURE SAYS SO.  A drop can land only in a gap between the
    dragged run's own siblings; the insertion line appears in those gaps and nowhere else, so
    a drag over a component in some other container simply shows no line to drop on.  That is
    the constraint being visible during the gesture rather than arriving as an error
    afterwards -- re-nesting is what the In/Out buttons are for, and this cannot do it.

    WHAT THE BROWSER KNOWS is two string tests, which is why paths are sent as strings (see
    sceneview.v2_encode_path): two components are siblings when their paths agree up to the
    last separator, and one is inside another when its path starts with the other's plus a
    separator.  No component types, no slot rules, no schema -- all of that stays in Python.

    A SIBLING'S EXTENT, NOT ITS ROW.  Both surfaces measure a sibling as the union of its own
    box and every box inside it, which is free on the canvas (a component's div contains its
    children) and load-bearing in the tree, where a container's children are separate rows
    below it.  Without it, dropping "after a Column" would draw its line between that Column
    and its first child -- which is where "into it" would go, an operation this does not do.

    Only the finished drop is sent back, once, on pointer-up -- the same bargain
    _emit_canvas_editing makes, for the same two reasons: a round trip per pointermove would
    be unusable, and it would put an undo entry on the stack per pixel travelled.  Selection
    is likewise reported only when the pointer did not move.

    The handlers are delegated to the container and guarded by a flag on it, because the tree
    pane is a widget that outlives its rows: re-rendering replaces every row inside it while
    the pane itself stays, so re-attaching per render would stack up a listener per selection.
    The Preview's canvas is rebuilt whole, arrives without the flag, and is wired afresh.

    `select_on_click` is off where the surface has a click handler of its own.  The tree's
    rows are NiceGUI labels that already select when clicked, and leaving that alone means a
    page where this script never ran -- or ran and found nothing -- is a tree that still
    selects and simply does not drag, rather than one that answers no clicks at all.  A
    shift-click is always reported here, because extending a selection is this script's own.

    WHAT IS SELECTED IS NOT SET HERE.  It arrives on the host as data-mt-v2-sel/-count, put
    there by whoever drew the surface (see _v2_selection_props), because a Quasar dialog
    detaches its contents from the document while it is hidden -- which is exactly what
    Preview does to the designer.  A script that wrote the selection itself would find no
    host at all for every render made behind the Preview, and the tree would come back
    dragging whatever run was selected before it opened.  An attribute is patched onto the
    element whether it is in the document or not, and is right again the moment it returns.
    """
    ui.run_javascript(
        f"""
        (() => {{
            const root = '{root}', nodeSel = '.{node_class}';
            const plainSelect = {"true" if select_on_click else "false"};
            const host = document.querySelector('{container}');
            if (!host) return;
            if (host.dataset.mtV2Drag === '1') return;
            host.dataset.mtV2Drag = '1';

            let drag = null, line = null;

            const clearLine = () => {{ if (line) {{ line.remove(); line = null; }} }};

            // Everything drawn for one component: its own element and everything inside it.
            const extent = (path) => {{
                let box = null;
                for (const el of host.querySelectorAll(nodeSel + '[data-path]')) {{
                    const p = el.dataset.path;
                    if (p !== path && !p.startsWith(path + '|')) continue;
                    const r = el.getBoundingClientRect();
                    if (!r.width && !r.height) continue;
                    box = box ? {{ top: Math.min(box.top, r.top), left: Math.min(box.left, r.left),
                                  bottom: Math.max(box.bottom, r.bottom), right: Math.max(box.right, r.right) }}
                              : {{ top: r.top, left: r.left, bottom: r.bottom, right: r.right }};
                }}
                return box;
            }};

            // The dragged run's siblings, by index, with where each of them is on screen.
            const siblings = (path, total) => {{
                const base = path.slice(0, path.lastIndexOf('|'));
                const found = [];
                for (let i = 0; i < total; i++) {{
                    const box = extent(base + '|' + i);
                    if (box) found.push({{ index: i, box }});
                }}
                return found;
            }};

            // Down the page or across it?  Read off where the siblings actually are rather
            // than from the container's flex-direction, so a Box, a grid or a wrapped row
            // answers for itself and the tree (always a stack of rows) needs no special case.
            const isVertical = (sibs) => {{
                let dx = 0, dy = 0;
                for (const a of sibs) for (const b of sibs) {{
                    dx = Math.max(dx, Math.abs((a.box.left + a.box.right) / 2 - (b.box.left + b.box.right) / 2));
                    dy = Math.max(dy, Math.abs((a.box.top + a.box.bottom) / 2 - (b.box.top + b.box.bottom) / 2));
                }}
                return dy >= dx;
            }};

            const showLine = (sibs, vertical, target) => {{
                const at = sibs.find((s) => s.index === target);
                const last = sibs[sibs.length - 1];
                const edge = at ? at.box : last.box;
                const before = !!at;
                let top = Math.min(...sibs.map((s) => s.box.top));
                let left = Math.min(...sibs.map((s) => s.box.left));
                let bottom = Math.max(...sibs.map((s) => s.box.bottom));
                let right = Math.max(...sibs.map((s) => s.box.right));
                if (!line) {{
                    line = document.createElement('div');
                    line.style.cssText = 'position: fixed; z-index: 9999; background: #2563eb;'
                                       + 'border-radius: 2px; pointer-events: none;';
                    document.body.appendChild(line);
                }}
                if (vertical) {{
                    const y = before ? edge.top : edge.bottom;
                    line.style.left = left + 'px';
                    line.style.width = Math.max(8, right - left) + 'px';
                    line.style.top = (y - 1) + 'px';
                    line.style.height = '3px';
                }} else {{
                    const x = before ? edge.left : edge.right;
                    line.style.top = top + 'px';
                    line.style.height = Math.max(8, bottom - top) + 'px';
                    line.style.left = (x - 1) + 'px';
                    line.style.width = '3px';
                }}
            }};

            host.addEventListener('pointerdown', (event) => {{
                if (event.button !== 0) return;
                const el = event.target.closest(nodeSel + '[data-path]');
                if (!el || !el.dataset.path) return;
                const total = parseInt(el.dataset.sibs || '0', 10);
                if (!(total > 1)) return;   // nothing to reorder it among
                const path = el.dataset.path;
                const base = path.slice(0, path.lastIndexOf('|'));
                const index = parseInt(path.slice(base.length + 1), 10);

                // Grabbing anything inside the selected run drags the whole run; grabbing
                // anything else drags just that one, and drops the old selection with it.
                const sel = host.dataset.mtV2Sel || '';
                const selBase = sel.slice(0, sel.lastIndexOf('|'));
                const selStart = sel ? parseInt(sel.slice(selBase.length + 1), 10) : -1;
                const selCount = parseInt(host.dataset.mtV2Count || '1', 10);
                const inRun = sel && selBase === base && index >= selStart && index < selStart + selCount;

                drag = {{
                    path: inRun ? sel : path, count: inRun ? selCount : 1,
                    clicked: path, total, base,
                    startX: event.clientX, startY: event.clientY, moved: false, target: null,
                }};
                // No pointer capture yet, and not until the drag threshold is crossed: a
                // captured pointer redirects the click that follows it to the capturing
                // element, which would take every plain click away from the tree row that
                // was meant to receive it.
            }});

            host.addEventListener('pointermove', (event) => {{
                if (!drag) return;
                if (!drag.moved
                    && Math.abs(event.clientX - drag.startX) < 4
                    && Math.abs(event.clientY - drag.startY) < 4) return;
                if (!drag.moved) {{
                    drag.moved = true;
                    // Only now, so a plain click is left exactly as it was found.
                    document.body.style.userSelect = 'none';
                    // Capture keeps the drag alive past the edge of the pane.  Guarded
                    // because it throws for a pointer the browser no longer considers
                    // active, and losing the capture is worth far less than losing the drag.
                    try {{ host.setPointerCapture(event.pointerId); }} catch (e) {{ /* not fatal */ }}
                }}
                event.preventDefault();
                const sibs = siblings(drag.path, drag.total);
                if (sibs.length < 2) return;
                const vertical = isVertical(sibs);
                const at = vertical ? event.clientY : event.clientX;
                let target = 0;
                for (const s of sibs) {{
                    const mid = vertical ? (s.box.top + s.box.bottom) / 2 : (s.box.left + s.box.right) / 2;
                    if (at > mid) target = s.index + 1;
                }}
                drag.target = target;
                showLine(sibs, vertical, target);
            }});

            const finish = (event) => {{
                if (!drag) return;
                const done = drag;
                drag = null;
                clearLine();
                document.body.style.userSelect = '';
                if (host.hasPointerCapture(event.pointerId)) host.releasePointerCapture(event.pointerId);
                if (done.moved && done.target !== null) {{
                    emitEvent('mt_v2_reorder',
                              {{ root, path: done.path, count: done.count, before: done.target }});
                }} else if (!done.moved && (plainSelect || event.shiftKey)) {{
                    emitEvent('mt_v2_select', {{ root, path: done.clicked, extend: !!event.shiftKey }});
                }}
            }};
            host.addEventListener('pointerup', finish);
            host.addEventListener('pointercancel', finish);
        }})();
        """,
    )


# Every mounted designer's canvas handlers, keyed by its own root class.
#
# ui.on subscribes app-wide rather than per-widget, so registering a fresh handler on every
# dialog build would leave one behind on every open.  The handlers are therefore registered
# once and dispatch through this table, which each designer registers itself in.
#
# Keyed rather than a single slot because designers nest: "Edit item layout" opens a second
# designer, on the Scene inside a List or Spinner, while the first is still mounted behind
# it.  Both canvases exist in the DOM, both would receive the app-wide event, and an sr means
# something different in each -- so the event says which root it came from and only that
# designer answers.
_ACTIVE_CANVASES: dict[str, dict[str, Callable]] = {}
# How long a typed-into designer field waits, after the last keystroke, before committing.
#
# Quasar's own debounce, so the caret is never involved: it holds the value and emits once the
# typing stops, and QInput flushes anything still pending on blur and on the native change
# event (onFinishEditing/onChange both call the pending emit).  Nothing can be lost by clicking
# Ok, tabbing away or picking another element straight after typing.
#
# It is here because a commit repaints the canvas, and a canvas is not a cheap thing to
# repaint: every element is redrawn, and a Text element holding HTML or a Web element holding a
# page is a sandboxed frame that reloads with it (see sceneview._html_frame).  Doing that once
# per '#FF8800' rather than eight times is the difference between a redraw and a flicker.
FIELD_COMMIT_DEBOUNCE_MS = 350
# Which clients have had the three canvas events subscribed.
#
# Per client rather than per process, because that is what ui.on is: it hands the listener to
# the page's own root element (nicegui.ui.on -> context.client.layout.on), so every page needs
# its own subscription.  A single process-wide flag left a rebuilt window -- a reload, a
# reconnect, a second window, all of which this app really does produce -- believing the job
# was already done, and its designer's canvas then answered no clicks and no drags at all.
#
# Weak, so a client that has gone away is forgotten with it rather than being kept alive here.
_CANVAS_EVENT_CLIENTS: weakref.WeakSet = weakref.WeakSet()
# Hands out a unique root class per designer, so two on one page cannot share a stylesheet
# rule, a resize handler or a pointer target.
_DESIGNER_SEQUENCE = itertools.count(1)


def _register_canvas_events() -> None:
    """Subscribe the three canvas events for this page, once.

    Called from initialize_screen, while the layout is still being built -- not left to the
    first designer that opens.  ui.on adds its listener to client.layout, and by the time a
    dialog opens the browser has long had that element: a listener appearing on an element it
    already knows is what made NiceGUI re-render the whole layout and log "Event listeners
    changed after initial definition.  Re-rendering affected elements." the first time anyone
    clicked "Edit Scene".

    A designer still calls this itself, so a page that builds one without going through
    initialize_screen is not left without the plumbing; the guard makes that call a no-op.
    """
    client = context.client
    if client in _CANVAS_EVENT_CLIENTS:
        return

    def dispatch(name: str, payload: object) -> None:
        """Route one canvas event to the designer whose canvas emitted it.

        A payload without a root is from a designer that has since been torn down, or from a
        build of this app that predates the routing; either way there is nothing to do with
        it but drop it, which is quieter than guessing at a recipient.
        """
        if not isinstance(payload, dict):
            return
        handlers = _ACTIVE_CANVASES.get(str(payload.get("root", "")))
        if handlers and name in handlers:
            handlers[name](payload)

    ui.on("mt_scene_select", lambda event: dispatch("select", event.args))
    ui.on("mt_scene_geometry", lambda event: dispatch("geometry", event.args))
    ui.on("mt_scene_nudge", lambda event: dispatch("nudge", event.args))
    # The Version 2 pair, routed the same way and for the same reason -- a designer's tree
    # pane and the Preview's canvas can both be reordering the same layout, and each has to
    # answer only for its own.
    ui.on("mt_v2_select", lambda event: dispatch("v2select", event.args))
    ui.on("mt_v2_reorder", lambda event: dispatch("v2reorder", event.args))
    _CANVAS_EVENT_CLIENTS.add(client)


def _legacy_canvas_size(
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    landscape: bool,
) -> tuple[int, int] | None:
    """The canvas size to draw a Legacy Scene at: what the dialog's size fields currently
    hold, falling back to what the Scene itself carries.

    Shared by the designer and the Preview so the two never disagree about how big the Scene
    is.  The fields are only present in a dialog that built them, so a missing widget means
    "use the Scene's own value", not an error -- the same contract
    userintr._apply_scene_field_values relies on.
    """
    width_key, height_key = ("widthLand", "heightLand") if landscape else ("widthPort", "heightPort")
    typed: dict[str, int] = {}
    for key in (width_key, height_key):
        widget = field_refs.get(key)
        if widget is None:
            continue
        try:
            typed[key] = int(str(widget.value).strip())
        except (AttributeError, ValueError):
            ui.notify(
                f"{translate_string('Using the saved size')}: "
                f"'{widget.value}' {translate_string('is not a whole number')}.",
                type="warning",
            )
    if width_key in typed and height_key in typed:
        width, height = typed[width_key], typed[height_key]
        return (width, height) if width > 0 and height > 0 else None
    return sceneview.scene_dimensions(edited_scene.scene_element, landscape)


def _build_legacy_designer(
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
) -> None:
    """The Legacy Scene designer: pick an element off the canvas, inspect its properties,
    move and resize it, and add, duplicate, restack or delete it.

    THE CANVAS IS THE EDITOR.  The V2 designer is a tree because a V2 layout is a tree; a
    Legacy Scene is a pixel canvas where every element states its own x,y,w,h, so the natural
    way to edit one is to drag it.  That canvas already existed as the read-only Preview
    (sceneview.draw_scene), and this passes it a CanvasEditing to turn it into a surface --
    the same drawing code, so what the user edits is exactly what the Preview showed them.

    Three panes, all rebuilt on every change: the canvas, an element list in z-order, and a
    property sheet.  Rebuilding wholesale rather than patching is the V2 designer's pattern
    and is here for the same reasons -- a different element has entirely different fields, and
    one render path cannot disagree with itself.  Selection is held as sr strings for the
    same reason V2 holds paths: the widgets do not survive a rebuild, the keys do.

    SEVERAL ELEMENTS CAN BE SELECTED AT ONCE -- shift-, ctrl- or cmd-click, on the canvas or
    in the list, or a rubber band drawn on the canvas background -- and dragging or nudging
    any of them moves all of them by the same delta, in one undo step.  Laying out a Scene is
    mostly moving groups of things that belong together, and doing that one element at a time
    loses their alignment on the first drag.
    Everything else stays deliberately single: see render_toolbar on why the structural
    buttons want exactly one element, and render_inspector on why the property sheet does.

    The list is drawn top-of-stack first, which is the reverse of the XML order.  sr="elementsN"
    is the paint order -- elements0 is painted first and therefore sits at the bottom -- and a
    layers panel that put the bottom element at the top would be describing the Scene upside
    down.

    Every structural edit renumbers every sr, so each of them re-selects by the sr the model
    hands back rather than the one it went in with (see sceneedit._legacy_reindex).  Deleting
    warns about the Tasks that address the element by name -- it does not refuse, because the
    Task may well be the obsolete one, and Undo is right there.

    NOT here yet, and each left alone rather than half-done: renaming an element (18 Task
    action codes address one by name, so a rename has to rewrite them, which is a different
    and more dangerous operation than warning about them); the Tasks an element fires; its
    background sub-element; and the Scene's own PropertiesElement.  Undo covers geometry and
    structure, matching the V2 designer, which likewise does not undo typing in a property
    field.
    """
    scene_element = edited_scene.scene_element
    # What is selected, in two forms that set_selection keeps in step and nothing else writes:
    #
    #   srs -- every element picked out, in the order they were picked.  A drag moves all of
    #          them by one delta, which is the whole point of allowing more than one.
    #   sr  -- the last of them, the anchor: the element the Inspector edits, the one the
    #          resize handles belong to, and the one every structural operation acts on.
    #
    # An anchor rather than a set for those, because they are the operations a set has no
    # single answer for -- what "Bring to Front" means for six elements at once depends on
    # what order they end up in, and this designer would be inventing that order.
    selection: dict = {"sr": "", "srs": ()}
    orientation: dict = {"landscape": False}
    history: list = []
    # Whole-Scene snapshots, as the V2 designer keeps whole-tree ones -- see
    # sceneedit.legacy_snapshot on why an inverse per operation is not worth modelling.
    snap = {"grid": 1}
    # Which sections are open, held out here because the inspector is rebuilt on every edit
    # -- without this, adding a Task binding would collapse the very section it was added in.
    # The V2 designer keeps its modifier/handler sections open the same way.
    expanded = {"tasks": False, "background": False, "properties": False}
    # Events the user has added a row for but not yet chosen a Task for.
    #
    # Held here rather than written into the XML, because a half-made binding is not a thing
    # Tasker writes: every <clickTask> in the sample data holds a real id, and an empty one
    # would be a Scene that says it fires something and names nothing.  The row exists so
    # there is somewhere to pick a Task; the child element appears when one is picked.
    pending_events: dict = {"sr": "", "tags": set()}

    _register_canvas_events()
    has_landscape = sceneview.has_landscape_layout(scene_element)
    # This designer's own canvas identity -- see _ACTIVE_CANVASES on why it cannot be shared.
    root_class = f"{CANVAS_DESIGNER_ROOT}-{next(_DESIGNER_SEQUENCE)}"

    header = ui.row().classes("w-full items-center gap-2 mt-2")
    canvas_pane = (
        ui
        .element("div")
        .classes(
            f"mt-scene-wrap {root_class} w-full border rounded overflow-hidden",
        )
        .style("position: relative;")
    )
    toolbar = ui.row().classes("w-full gap-1 items-center mt-1 flex-wrap")
    with ui.row().classes("w-full gap-3 items-start no-wrap mt-1"):
        list_pane = ui.column().classes("w-2/5 gap-0 p-2 border rounded max-h-64 overflow-auto")
        inspector_pane = ui.column().classes("w-3/5 gap-1 p-2 border rounded max-h-72 overflow-auto")
    properties_pane = ui.column().classes("w-full gap-0")
    status = ui.row().classes("w-full items-center gap-2")

    def snapshot() -> None:
        history.append(sceneedit.legacy_snapshot(scene_element))

    def set_selection(*srs: str) -> None:
        """Pick out zero or more elements, without re-rendering -- for the callers that
        render anyway.  Duplicates are dropped and order is kept, so the anchor is the last
        element the user actually pointed at.
        """
        selection["srs"] = tuple(dict.fromkeys(sr for sr in srs if sr))
        selection["sr"] = selection["srs"][-1] if selection["srs"] else ""

    def restore() -> None:
        if not history:
            return
        sceneedit.legacy_restore(scene_element, history.pop())
        # Undoing an Add takes the added element away with it, so anything the restored Scene
        # no longer has is dropped rather than left selected as a key naming nothing.
        set_selection(*(sr for sr in selection["srs"] if sceneedit.legacy_element_at(scene_element, sr) is not None))
        render()

    def select(*srs: str) -> None:
        set_selection(*srs)
        render()

    def toggle(sr: str) -> None:
        """Add an element to the selection, or take it out again if it is already in.

        Toggling rather than only extending because this is a set, not a run: there is no
        "shrink from the end" to fall back on, and taking one element back out of six is
        otherwise a matter of starting the whole selection again.
        """
        if not sr:
            return
        current = list(selection["srs"])
        if sr in current:
            current.remove(sr)
        else:
            current.append(sr)
        select(*current)

    def select_anchor(sr: str) -> None:
        """Move the anchor onto another already-selected element, leaving the selection
        itself alone -- what the Inspector's "Also selected" names do.  Which element the
        property sheet is showing and which elements are picked out are two different
        questions, and this is the one that answers only the first.
        """
        if sr not in selection["srs"]:
            return
        select(*(key for key in selection["srs"] if key != sr), sr)

    def select_from_canvas(payload: dict) -> None:
        """A click or a rubber band on the canvas.

        Two payloads through one event, because they are one gesture until the pointer comes
        up: `sr` for a click (Shift, Ctrl or Cmd adds to the selection, a plain click replaces
        it, and a plain click on the background clears it), `srs` for a band drawn on the
        background (a list of everything it enclosed, added to the selection with a modifier
        held and replacing it without).
        """
        caught = payload.get("srs")
        if isinstance(caught, list):
            # Nothing caught and no modifier is a band drawn round empty canvas, which
            # clears -- the same answer the plain click it grew out of would have given.
            picked = [
                sr
                for sr in (str(value) for value in caught)
                if sceneedit.legacy_element_at(scene_element, sr) is not None
            ]
            select(*selection["srs"], *picked) if payload.get("extend") else select(*picked)
            return

        sr = str(payload.get("sr", ""))
        if payload.get("extend"):
            toggle(sr)
            return
        select(sr)

    def add_element(element_type: str) -> None:
        """Create an element of this type, in the middle of the canvas, on top of the stack.

        Centred rather than at 0,0 because a Scene's bottom element is very often a
        full-canvas background Rect, and a new element created at the origin under one would
        be invisible -- indistinguishable, to the user, from the Add button not working.
        """
        size = _legacy_canvas_size(edited_scene, field_refs, orientation["landscape"])
        if size is None:
            ui.notify(translate_string("This Scene has no layout for this orientation."), type="warning")
            return
        canvas_width, canvas_height = size
        width, height = min(300, canvas_width), min(120, canvas_height)
        box = ((canvas_width - width) // 2, (canvas_height - height) // 2, width, height)

        snapshot()
        element = sceneedit.legacy_new_element(
            scene_element,
            element_type,
            box,
            landscape=sceneview.has_landscape_layout(scene_element),
        )
        if isinstance(element, str):
            history.pop()
            ui.notify(element, type="negative", multi_line=True)
            return
        # Every structural edit renumbers every sr (see sceneedit._legacy_reindex), so each of
        # them re-selects by the sr the model hands back -- and collapses the selection to
        # that one element, rather than trying to follow a whole set through the renumbering.
        set_selection(sceneedit.legacy_insert_element(scene_element, element))
        render()

    def duplicate_element() -> None:
        snapshot()
        new_sr = sceneedit.legacy_duplicate_element(scene_element, selection["sr"])
        if not new_sr:
            history.pop()
            ui.notify(translate_string("Select an element first."), type="warning")
            return
        set_selection(new_sr)
        render()

    def delete_element() -> None:
        """Delete the selected element, warning about -- but not blocked by -- the Tasks that
        address it.

        Warn rather than refuse, exactly as the V2 designer does when deleting a component
        Tasks address by id: the Task may be the obsolete one, this app cannot know which of
        the two the user meant to keep, and Undo is one button away.
        """
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None:
            ui.notify(translate_string("Select an element first."), type="warning")
            return

        name = sceneedit.legacy_element_label(element)
        element_name = (element.findtext("Str[@sr='arg0']") or "").strip()
        references = sceneedit.find_element_name_references(edited_scene.scene_name, element_name)
        patterns = sceneedit.find_element_match_references(edited_scene.scene_name)

        snapshot()
        set_selection(sceneedit.legacy_delete_element(scene_element, selection["sr"]))
        if references:
            ui.notify(
                f"Deleted {name}. {len(references)} Task(s) address '{element_name}' by name: "
                f"{', '.join(references)}. They will no longer find it.",
                type="warning",
                multi_line=True,
                timeout=10000,
            )
        if patterns:
            ui.notify(
                f"{len(patterns)} Task(s) also address this Scene's elements by a match pattern "
                f"(Element Visibility): {', '.join(patterns)}. Whether they matched '{element_name}' "
                "is decided by Tasker at run time, so check them yourself.",
                type="warning",
                multi_line=True,
                timeout=10000,
            )
        render()

    def restack(position: Callable[[int, int], int], failure: str) -> None:
        """Move the selection through the z-order.  `position` is handed (current index,
        count) and returns where it should end up, which is what makes Forward, Backward,
        To Front and To Back one operation with four callers.
        """
        ordered = sceneedit.legacy_drawable_elements(scene_element)
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None or element not in ordered:
            ui.notify(translate_string("Select an element first."), type="warning")
            return

        snapshot()
        new_sr = sceneedit.legacy_restack(
            scene_element,
            selection["sr"],
            position(ordered.index(element), len(ordered)),
        )
        if not new_sr:
            history.pop()
            ui.notify(translate_string(failure), type="warning")
            return
        set_selection(new_sr)
        render()

    def set_geometry(payload: dict) -> None:
        """Apply a finished drag or resize.

        ONE SNAPSHOT PER GESTURE -- not per pixel, and not per element.  The browser sends
        every moved box once, on pointer-up (see _emit_canvas_editing), and dragging six
        elements across the canvas is one thing the user did and one thing Undo should put
        back.  Everything is worked out before the snapshot is taken so that a payload naming
        nothing this Scene has leaves no empty entry on the stack.
        """
        moves = []
        for move in payload.get("moves") or ():
            sr = str(move.get("sr", ""))
            element = sceneedit.legacy_element_at(scene_element, sr)
            if element is None:
                continue
            try:
                box = (int(move["x"]), int(move["y"]), int(move["w"]), int(move["h"]))
            except (KeyError, TypeError, ValueError):
                continue
            moves.append((element, sr, box))
        if not moves:
            return

        snapshot()
        for element, _sr, box in moves:
            sceneedit.legacy_set_geometry(element, box, landscape=orientation["landscape"])
        # A drag reports the elements it moved rather than assuming they were the selected
        # ones, so dragging something else selects it as a side effect -- which is what makes
        # "click to select, drag to move" work without a mode.
        set_selection(*(sr for _element, sr, _box in moves))
        render()

    def nudge(payload: dict) -> None:
        """Arrow-key move, applied to everything selected -- one snapshot for the whole
        nudge, exactly as one drag of that same group is one snapshot.
        """
        delta_x, delta_y = int(payload.get("dx", 0)), int(payload.get("dy", 0))
        moves = []
        for sr in selection["srs"]:
            element = sceneedit.legacy_element_at(scene_element, sr)
            if element is None:
                continue
            box = sceneview.element_geometry(element, orientation["landscape"])
            if box is None:
                continue
            x, y, width, height = box
            moves.append((element, (x + delta_x, y + delta_y, width, height)))
        if not moves:
            return

        snapshot()
        for element, box in moves:
            sceneedit.legacy_set_geometry(element, box, landscape=orientation["landscape"])
        render()

    def set_orientation(landscape: bool) -> None:
        orientation["landscape"] = landscape
        render()

    def render_canvas() -> None:
        size = _legacy_canvas_size(edited_scene, field_refs, orientation["landscape"])
        if size is None:
            which = "landscape" if orientation["landscape"] else "portrait"
            ui.label(
                translate_string(
                    f"This Scene has no {which} layout: its size is -1, which is Tasker's "
                    "'this orientation has no layout of its own'.",
                ),
            ).classes("text-sm text-orange-600 p-2")
            return
        width, height = size
        options = sceneview.PreviewOptions(landscape=orientation["landscape"], show_tasks=False)
        with canvas_pane:
            sceneview.draw_scene(
                scene_element,
                width,
                height,
                options,
                editing=sceneview.CanvasEditing(selected=selection["srs"], snap=snap["grid"]),
            )
        _emit_canvas_fit(root_class, width, height, budget=DESIGNER_CANVAS_HEIGHT)
        _emit_canvas_editing(root_class, snap["grid"])

    def render_list() -> None:
        elements = sceneview.paint_order(scene_element)
        if not elements:
            ui.label(translate_string("This Scene has no UI elements.")).classes("text-sm italic text-gray-500")
            return
        # Reversed: top of the list is top of the stack.  See this function's docstring.
        for element in reversed(elements):
            sr = element.get("sr", "")
            classes = "text-sm font-mono whitespace-pre cursor-pointer rounded px-1 py-0.5 w-full"
            if sr == selection["sr"]:
                # The anchor is marked apart from the rest of the selection, because it is
                # what the Inspector below is showing and what the toolbar's buttons act on.
                classes += " bg-blue-600 text-white"
            elif sr in selection["srs"]:
                classes += " bg-blue-200 dark:bg-blue-900"
            else:
                classes += " hover:bg-blue-100 dark:hover:bg-blue-900"
            ui.label(sceneedit.legacy_element_label(element)).classes(classes).on(
                "click",
                lambda event, key=sr: click_row(event, key),
                # The modifiers, so a row can extend the selection the way the canvas does.
                # Named here rather than read off a JS event object, because NiceGUI sends
                # only what it is asked for.
                args=["shiftKey", "ctrlKey", "metaKey"],
            )

    def click_row(event: Event, sr: str) -> None:
        """A click in the element list.

        Shift takes the whole range between the anchor and this row; Ctrl or Cmd toggles
        this row alone.  The canvas draws no such distinction -- every modifier toggles
        there -- and the difference is the point rather than an inconsistency: a list is in
        an order, so a range along it is a thing the user can see and mean, while a canvas
        is a plane where the elements between two others are whichever ones happen to lie
        between them, which is not something anyone selects on purpose.
        """
        modifiers = event.args if isinstance(event.args, dict) else {}
        if modifiers.get("shiftKey"):
            select_range(sr)
            return
        if modifiers.get("ctrlKey") or modifiers.get("metaKey"):
            toggle(sr)
            return
        select(sr)

    def select_range(sr: str) -> None:
        """Take everything between the anchor and this element, in paint order.

        Replaces the selection rather than adding to it, which is what shift-click does in
        every list of layers there has ever been -- Ctrl is the one that adds.  With no
        anchor yet there is no range to take, so it falls back to an ordinary click.

        THE ANCHOR STAYS THE ANCHOR: it goes in last, and set_selection reads the last as
        the anchor.  Without that, shift-clicking a second time would range from the row
        just clicked instead of from where the range started, and the selection would walk
        along the list rather than widen and narrow about a fixed end -- which is the whole
        behaviour a shift-click is reached for.
        """
        order = [element.get("sr", "") for element in sceneview.paint_order(scene_element)]
        anchor = selection["sr"]
        if anchor not in order or sr not in order:
            select(sr)
            return
        first, last = sorted((order.index(anchor), order.index(sr)))
        select(*(key for key in order[first : last + 1] if key != anchor), anchor)

    def geometry_input(label: str, index: int, element: object, box: tuple) -> None:
        """One of the four geometry boxes.  Typing a number and dragging the element are the
        same operation on the same value, so they go through the same legacy_set_geometry and
        land on the same undo stack.

        Repaints rather than re-renders, and is debounced, for the reasons on repaint() and
        FIELD_COMMIT_DEBOUNCE_MS -- typing "140" into Width is three keystrokes, and a
        re-render on the first of them would take the box being typed into with it.
        """

        def commit(event: Event, position: int = index) -> None:
            # float() before int(): ui.number hands back a float, and "900.0" is not something
            # int() will parse.  Every typed geometry edit used to be dropped right here, in
            # silence -- the box showed the number, the element never moved, and selecting
            # anything else brought the old value straight back.
            try:
                number = int(float(str(event.value).strip()))
            except (TypeError, ValueError):
                return
            current = sceneview.element_geometry(element, orientation["landscape"])
            if current is None or current[position] == number:
                return
            snapshot()
            values = list(current)
            values[position] = number
            sceneedit.legacy_set_geometry(element, tuple(values), landscape=orientation["landscape"])
            repaint()

        ui.number(translate_string(label), value=box[index], format="%d", on_change=commit).props(
            f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}",
        ).classes("w-1/4")

    def render_inspector() -> None:
        """The anchor's properties -- one element's, however many are selected.

        Editing a set of them together is a bigger and much less obvious thing than moving
        one: several of these fields are geometry, and X on six elements at once could mean
        "put them all at X" or "shift them all to X", which are different edits with the same
        box.  So the property sheet stays on one element and says which, rather than offering
        a group edit whose meaning the user would have to guess at.  Moving the group is what
        the canvas is for.
        """
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None:
            ui.label(translate_string("Select an element on the canvas or in the list.")).classes(
                "text-sm italic text-gray-500",
            )
            return

        others = [sr for sr in selection["srs"] if sr != selection["sr"]]
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.label(sceneedit.legacy_element_label(element)).classes("text-sm font-semibold font-mono")
            if others:
                ui.label(
                    f"{translate_string('editing 1 of')} {len(selection['srs'])} {translate_string('selected')}",
                ).classes("text-xs text-gray-500 italic").tooltip(
                    translate_string(
                        "Properties are edited one element at a time. Dragging and nudging move everything selected.",
                    ),
                )
        if others:
            # Named, and clickable, because otherwise a selection of six is six identical
            # blue rows and no way to say which one this sheet should be showing without
            # taking the other five apart and building the selection again.
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.label(translate_string("Also selected:")).classes("text-xs text-gray-500")
                for other_sr in others:
                    other = sceneedit.legacy_element_at(scene_element, other_sr)
                    if other is None:
                        continue
                    ui.label(sceneedit.legacy_element_label(other)).classes(
                        "text-xs font-mono cursor-pointer underline decoration-dotted text-blue-700 dark:text-blue-300",
                    ).on("click", lambda _e=None, key=other_sr: select_anchor(key)).tooltip(
                        translate_string("Edit this one's properties instead, keeping the selection."),
                    )

        box = sceneview.element_geometry(element, orientation["landscape"])
        if box is None:
            ui.label(
                translate_string("This element has no layout for this orientation."),
            ).classes("text-xs text-orange-600 italic")
        else:
            ui.label(translate_string("Geometry")).classes("text-xs uppercase text-gray-500 mt-1")
            with ui.row().classes("w-full gap-1 no-wrap"):
                for index, label in enumerate(("X", "Y", "Width", "Height")):
                    geometry_input(label, index, element, box)

        args = sceneedit.legacy_element_args(element)
        if not args:
            ui.label(
                translate_string(
                    "This app has no property table for this element type, so only its geometry "
                    "can be edited here. It is otherwise carried through untouched.",
                ),
            ).classes("text-xs text-gray-500 italic mt-2")
            return

        ui.label(translate_string("Properties")).classes("text-xs uppercase text-gray-500 mt-2")
        for arg in args:
            _render_legacy_arg(arg, repaint, on_rename=rename_selected)
        render_tasks(element)
        render_background(element)
        render_item_layout(element)

    def render_item_layout(element: object) -> None:
        """The Scene inside this element, if it has one.

        A List and a Spinner each carry a whole nested Scene that is the layout of one row.
        It is opened in a designer of its own rather than inlined here: it is a Scene, with
        its own canvas, its own stack and its own elements, and squeezing a second canvas
        into this inspector would give it none of that.
        """
        layout = sceneedit.legacy_item_layout(element)
        if layout is None:
            return
        rows = len(sceneedit.legacy_drawable_elements(layout))
        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.label(
                f"{translate_string('Item layout')}: {sceneedit.legacy_item_layout_name(element)} "
                f"({rows} {translate_string('element(s)')})",
            ).classes("text-xs text-gray-500")
            ui.space()
            ui.button(
                translate_string("Edit item layout"),
                icon="open_in_new",
                on_click=lambda _e=None, holder=element: _build_item_layout_dialog(holder, render),
            ).props("dense flat size=sm")

    def rename_selected() -> None:
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None:
            return
        _build_rename_legacy_element_dialog(edited_scene, element, apply_rename)

    def apply_rename(old_name: str, new_name: str, update_tasks: bool) -> None:
        """Take the rename dialog's answer.  The Task rewrite is *recorded*, not performed --
        see sceneedit.EditableScene.element_renames.
        """
        snapshot()
        errors = sceneedit.legacy_rename_element(scene_element, selection["sr"], new_name)
        if errors:
            history.pop()
            for error in errors:
                ui.notify(error, type="negative")
            return
        wanted = new_name.strip()
        if update_tasks and wanted != old_name:
            edited_scene.element_renames.append((old_name, wanted))
            ui.notify(
                translate_string("The Tasks that address it will be updated when this Scene is saved."),
                type="positive",
            )
        render()

    def render_tasks(element: object) -> None:
        """What this element does when it is used.

        A Legacy element's behaviour is entirely in these children -- there is no equivalent
        of a V2 component's eventHandlers block -- so an inspector without them describes
        only half of what the element is.

        An anonymous Task (a negative id) is shown and cannot be repointed.  Tasker stores
        those inside the Scene itself and nowhere else, so replacing one destroys the only
        copy; the offer to do that would be an offer to lose work.
        """
        bindings = sceneedit.legacy_task_bindings(element)
        available = sceneedit.legacy_task_tags_for(element)
        if pending_events["sr"] != selection["sr"]:
            # The pending rows belong to the element they were opened on.
            pending_events["sr"], pending_events["tags"] = selection["sr"], set()
        waiting = sorted(tag for tag in pending_events["tags"] if element.find(tag) is None)
        unused = [tag for tag in available if element.find(tag) is None and tag not in waiting]
        if not bindings and not unused and not waiting:
            return

        with ui.expansion(
            f"{translate_string('Tasks')} ({len(bindings)})",
            icon="bolt",
            value=expanded["tasks"],
            on_value_change=lambda event: expanded.__setitem__("tasks", bool(event.value)),
        ).classes("w-full mt-2"):
            choices = sceneedit.legacy_task_choices()
            for binding in bindings:
                with ui.row().classes("w-full items-center gap-1 no-wrap"):
                    ui.label(translate_string(binding.label)).classes("text-xs w-28 shrink-0")
                    if binding.anonymous:
                        anonymous_field = ui.input(value=binding.task_name).props("readonly dense").classes("flex-1")
                        with anonymous_field:
                            ui.tooltip(
                                translate_string(
                                    "Tasker keeps this Task inside the Scene and nowhere else, so it has no "
                                    "name and cannot be pointed somewhere else without losing it. It is "
                                    "carried through untouched.",
                                ),
                            ).style("white-space: pre-wrap")
                    else:
                        ui.select(
                            choices,
                            value=binding.task_name if binding.task_name in choices else None,
                            with_input=True,
                            on_change=lambda event, tag=binding.tag: set_binding(tag, str(event.value or "")),
                        ).props("dense").classes("flex-1")
                        ui.button(
                            icon="close",
                            on_click=lambda _e=None, tag=binding.tag: clear_binding(tag),
                        ).props("dense flat size=sm color=negative").tooltip(
                            translate_string("Stop firing anything on this event."),
                        )
            for tag in waiting:
                with ui.row().classes("w-full items-center gap-1 no-wrap"):
                    ui.label(translate_string(SCENE_TASK_TYPES.get(tag, tag))).classes("text-xs w-28 shrink-0")
                    ui.select(
                        choices,
                        value=None,
                        with_input=True,
                        label=translate_string("Pick a Task"),
                        on_change=lambda event, t=tag: set_binding(t, str(event.value or "")),
                    ).props("dense").classes("flex-1")
                    ui.button(
                        icon="close",
                        on_click=lambda _e=None, t=tag: discard_pending(t),
                    ).props("dense flat size=sm color=negative")
            if unused:
                add_binding = ui.button(translate_string("Add event"), icon="add").props("dense flat size=sm")
                with add_binding, ui.menu():
                    for tag in unused:
                        ui.menu_item(
                            translate_string(SCENE_TASK_TYPES.get(tag, tag)),
                            on_click=lambda _e=None, t=tag: open_pending(t),
                        ).props("dense")

    def open_pending(tag: str) -> None:
        """Show a row for this event without writing anything yet -- see pending_events."""
        pending_events["sr"] = selection["sr"]
        pending_events["tags"].add(tag)
        expanded["tasks"] = True
        render()

    def discard_pending(tag: str) -> None:
        pending_events["tags"].discard(tag)
        expanded["tasks"] = True
        render()

    def set_binding(tag: str, task_name: str) -> None:
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None or not task_name:
            return
        task_id = sceneedit.legacy_task_id_for_name(task_name)
        if not task_id:
            ui.notify(f"No Task named '{task_name}' in this backup.", type="negative")
            return
        snapshot()
        sceneedit.legacy_set_task_binding(element, tag, task_id)
        pending_events["tags"].discard(tag)
        expanded["tasks"] = True
        render()

    def clear_binding(tag: str) -> None:
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None:
            return
        snapshot()
        sceneedit.legacy_clear_task_binding(element, tag)
        expanded["tasks"] = True
        render()

    def render_background(element: object) -> None:
        """The element's background sub-element -- a whole RectElement inside it, and where
        most of a real Scene's colour lives.

        Offered only for the types Tasker gives one to (sceneedit.LEGACY_BACKGROUND_TYPES);
        a Button, a Rect and an Oval carry their fill in their own arguments and have never
        been seen with one.
        """
        if not sceneedit.legacy_can_have_background(element):
            return
        background = sceneedit.legacy_background(element)

        with ui.expansion(
            translate_string("Background") + ("" if background is not None else f" ({translate_string('none')})"),
            icon="format_paint",
            value=expanded["background"],
            on_value_change=lambda event: expanded.__setitem__("background", bool(event.value)),
        ).classes("w-full mt-1"):
            if background is None:
                ui.button(
                    translate_string("Add a background"),
                    icon="add",
                    on_click=add_background,
                ).props("dense flat")
                return
            # It is a RectElement, so it gets the Rect fields -- the same generated form the
            # inspector gives a real Rect, from the same table.
            for arg in sceneedit.legacy_element_args(background):
                _render_legacy_arg(arg, repaint, name_editable=True)
            ui.button(translate_string("Remove background"), icon="delete", on_click=remove_background).props(
                "dense flat size=sm color=negative",
            )

    def add_background() -> None:
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None:
            return
        snapshot()
        sceneedit.legacy_add_background(element)
        expanded["background"] = True
        render()

    def remove_background() -> None:
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        if element is None:
            return
        snapshot()
        sceneedit.legacy_remove_background(element)
        expanded["background"] = True
        render()

    def render_scene_properties() -> None:
        """The Scene's own settings -- how it is put on screen, which way up, its background,
        its title.  They describe the Scene rather than any element, so they sit below the
        panes rather than in the element inspector, and they were invisible in this dialog
        until now.
        """
        properties = sceneedit.legacy_scene_properties(scene_element)
        with ui.expansion(
            translate_string("Scene Properties") + ("" if properties is not None else f" ({translate_string('none')})"),
            icon="settings",
            value=expanded["properties"],
            on_value_change=lambda event: expanded.__setitem__("properties", bool(event.value)),
        ).classes("w-full mt-1"):
            if properties is None:
                ui.label(
                    translate_string(
                        "This Scene has no properties element. 66 of the 366 Scenes MapTasker has "
                        "seen have none either, so this is ordinary rather than damage.",
                    ),
                ).classes("text-xs text-gray-500 italic")
                ui.button(
                    translate_string("Add scene properties"),
                    icon="add",
                    on_click=add_scene_properties,
                ).props("dense flat")
                return
            for arg in sceneedit.legacy_element_args(properties):
                _render_legacy_arg(arg, repaint, name_editable=True)

    def add_scene_properties() -> None:
        snapshot()
        sceneedit.legacy_add_scene_properties(scene_element)
        expanded["properties"] = True
        render()

    def repaint() -> None:
        """Redraw the canvas, and leave every form on screen exactly as it is.

        WHAT EVERY TYPED-INTO FIELD COMMITS THROUGH, in place of render().  render() clears
        the panes and builds them again, which destroys the widget being typed into and takes
        the caret with it: entering a colour meant typing '#', losing focus, clicking the
        field, typing 'F', losing focus, and so on for every character of '#FF8800'.  The V2
        designer keeps focus the same way -- write the value through, update whatever the
        value changed, do not touch the form (see the treeLabel note in _build_v2_designer).

        The canvas is the only thing that can be showing something the new value contradicts.
        The element list names elements by type and by name, and neither is reachable from a
        field here -- a top-level element's name belongs to the Rename button, never to a text
        box -- while the header counts elements, which no value edit changes.  Structural
        edits (add, delete, restack, background added or removed) do change those, and they
        stay on render(); none of them is a keystroke.
        """
        canvas_pane.clear()
        with canvas_pane:
            render_canvas()

    def render() -> None:
        _ACTIVE_CANVASES[root_class] = {
            "select": select_from_canvas,
            "geometry": set_geometry,
            "nudge": nudge,
        }
        # What the Preview needs to be a second canvas over this same Scene, and why it is
        # handed these rather than copies of them -- the Version 2 designer publishes itself
        # the same way, for the same reasons (see field_refs["v2_edit"]):
        #
        #   handlers    -- the Preview's drags run *these* closures, so a move made in the
        #                  picture lands on this designer's undo stack rather than a second
        #                  one its Undo button knows nothing about.
        #   selection   -- the same dict object, so the elements outlined in the picture and
        #                  the rows highlighted in the list cannot disagree.
        #   snap, orientation
        #               -- likewise the same objects.  Orientation especially: these handlers
        #                  write whichever half of <geom> *this* dict names, so a Preview
        #                  showing the other one would rewrite the layout nobody was looking
        #                  at.  See NiceGuiSceneView._set_option, which keeps them level.
        #   rerender    -- called when the dialog comes back, because re-opening it rebuilds
        #                  these panes' DOM and the canvas handlers have to be put back on
        #                  the new one.  See NiceGuiSceneView._back_to_editor.
        #
        # Running this designer's handlers is also what keeps these panes from going stale
        # while they are hidden: every one of them ends in render(), so the list and the
        # Inspector are rebuilt as the drag lands rather than coming back showing the
        # geometry from before it.
        field_refs["legacy_edit"] = {
            "handlers": _ACTIVE_CANVASES[root_class],
            "selection": selection,
            "snap": snap,
            "orientation": orientation,
            "rerender": render,
        }
        header.clear()
        canvas_pane.clear()
        list_pane.clear()
        inspector_pane.clear()
        toolbar.clear()
        properties_pane.clear()
        status.clear()
        with header:
            picked = len(selection["srs"])
            ui.label(
                f"{translate_string('Scene Elements')} ({len(sceneview.paint_order(scene_element))})"
                + (f" — {picked} {translate_string('selected')}" if picked > 1 else ""),
            ).classes("text-sm font-semibold").tooltip(
                # Where the list's two modifiers are said, because this sits directly above
                # the rows they apply to and the status line below is about the canvas.
                translate_string(
                    "In the list: Shift-click for a range, Ctrl- or Cmd-click to add or remove one.",
                ),
            )
            ui.space()
            orientation_switch = ui.switch(
                translate_string("Landscape"),
                value=orientation["landscape"],
                on_change=lambda event: set_orientation(bool(event.value)),
            ).props("dense")
            orientation_switch.set_enabled(has_landscape)
            if not has_landscape:
                with orientation_switch:
                    ui.tooltip(
                        translate_string("This Scene has no landscape layout of its own (its size is -1)."),
                    )
            ui.select(
                [1, 2, 5, 10],
                value=snap["grid"],
                label=translate_string("Snap"),
                on_change=lambda event: (snap.__setitem__("grid", int(event.value or 1)), render()),
            ).props("dense").classes("w-24").tooltip(
                translate_string("Round dragged positions and sizes to this many pixels."),
            )
            add_button = ui.button(
                translate_string("Add"),
                icon="add",
                on_click=lambda: _build_add_legacy_element_dialog(scene_element, add_element),
            ).props("dense flat")
            with add_button:
                ui.tooltip(translate_string("Adds an element on top of the stack, in the middle of the Scene."))
            ui.button(translate_string("Undo"), icon="undo", on_click=restore).props("dense flat").set_enabled(
                bool(history),
            )
        with canvas_pane:
            render_canvas()
        with list_pane:
            render_list()
        with inspector_pane:
            render_inspector()
        with toolbar:
            render_toolbar()
        with properties_pane:
            render_scene_properties()
        with status:
            picked = len(selection["srs"])
            ui.label(
                (
                    translate_string(
                        "Click an element to select it, drag to move, drag a handle to resize, "
                        "arrow keys to nudge (Shift for 10px). Shift-click, or drag a box on the "
                        "background, to take several at once.",
                    )
                    if picked < 2
                    else (
                        f"{picked} {translate_string('elements selected')} — "
                        f"{translate_string('drag or nudge any of them and they all move together.')}"
                    )
                ),
            ).classes("text-xs text-gray-500 italic")

    def render_toolbar() -> None:
        """The structural operations, all of which need exactly one element selected.

        One rather than any number, because none of these has an obvious meaning for a set.
        "Bring to Front" for six elements has to decide what order they end up in relative to
        each other; Duplicate has to decide where six copies go and what they are called.
        Both are answerable, neither is answerable *obviously*, and a button that quietly
        picks one of the readings is worse than a button that waits for a single selection.

        Restacking is four buttons rather than two because "send this behind everything" is
        a different intent from "send it back one", and on a Scene with a full-canvas
        background Rect the one-step version is a lot of clicking.  They are named for the
        stack rather than for the list -- Front is the top of both, but "Up" would be
        ambiguous the moment someone looks at the canvas instead of the list.
        """
        element = sceneedit.legacy_element_at(scene_element, selection["sr"])
        single = element is not None and len(selection["srs"]) == 1
        count = len(sceneedit.legacy_drawable_elements(scene_element))
        for label, icon, position, failure in (
            ("Front", "flip_to_front", lambda _index, total: total - 1, "Already at the front."),
            ("Forward", "arrow_upward", lambda index, _total: index + 1, "Already at the front."),
            ("Backward", "arrow_downward", lambda index, _total: index - 1, "Already at the back."),
            ("Back", "flip_to_back", lambda _index, _total: 0, "Already at the back."),
        ):
            ui.button(
                translate_string(label),
                icon=icon,
                on_click=lambda _e=None, p=position, f=failure: restack(p, f),
            ).props("dense flat").set_enabled(single and count > 1)
        ui.button(translate_string("Duplicate"), icon="content_copy", on_click=duplicate_element).props(
            "dense flat",
        ).set_enabled(single)
        ui.button(translate_string("Delete"), icon="delete", on_click=delete_element).props(
            "dense flat color=negative",
        ).set_enabled(single)
        if element is not None and not single:
            # Six greyed-out buttons and no reason given is a bug report waiting to happen.
            ui.label(
                translate_string("Select a single element to duplicate, delete or restack it."),
            ).classes("text-xs text-gray-500 italic")

    render()


def _build_item_layout_dialog(holder: object, on_closed: Callable[[], None]) -> None:
    """Edit the Scene inside a List or a Spinner, in a designer of its own.

    The nested thing really is a Scene -- its own <nme>, its own widthPort/heightPort, its
    own elements numbered from elements0, its own PropertiesElement -- so it gets the same
    designer rather than a reduced version of one.  That is the whole reason the canvas
    plumbing is keyed per instance (see _ACTIVE_CANVASES): this dialog sits on top of the
    designer that opened it, and both canvases are mounted at once.

    IT IS NOT A COPY.  The outer dialog is already editing a deep copy of the whole Scene,
    and this nested element is part of it, so edits land in that copy and are kept or
    discarded with it by the outer dialog's own Ok or Cancel.  A second layer of copying
    would need a second layer of Ok/Cancel to reconcile, and "Cancel" on the inner one while
    keeping the outer would be a promise this app could not keep.

    THE RENAME SWEEP IS TURNED OFF IN HERE, and the dialog says so.  find_element_name_actions
    matches a Task action against a *Scene* name, and an item layout is not in the backup's
    Scene table -- it has no name Tasker's Element actions could address it by.  Running the
    sweep against the outer Scene's name instead would be worse than not running it: it would
    rewrite Tasks that address a same-named element of the outer Scene, which is a different
    element.
    """
    layout = sceneedit.legacy_item_layout(holder)
    if layout is None:
        return

    # scene_name deliberately empty: it is what the rename sweep keys on, and an empty one is
    # what makes find_element_name_actions correctly find nothing.  The dialog explains it
    # rather than leaving the user to read "no Task addresses this" as a fact about Tasker.
    nested = sceneedit.EditableScene(scene_name="", scene_element=layout)
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[900px] w-full p-6"):
        ui.label(
            f"{translate_string('Item layout')}: {sceneedit.legacy_item_layout_name(holder) or translate_string('(unnamed)')}",
        ).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string(
                "The layout of one row. Tasker draws it once per entry of whatever fills the list, "
                "so what you see here is a single row rather than the list.",
            ),
        ).classes("text-sm text-gray-500 italic")

        with ui.row().classes("w-full gap-2 mt-2"):
            for key, label in sceneedit.SCENE_DIMENSION_FIELDS[:2]:
                field_refs[key] = (
                    ui
                    .input(translate_string(label), value=layout.findtext(key, sceneedit.UNSET_DIMENSION))
                    .props("dense")
                    .classes("w-36")
                    .on(
                        "blur",
                        lambda _e=None, k=key: _apply_item_layout_size(nested, field_refs, k),
                    )
                )
        ui.label(
            translate_string(
                "Renaming an element in here does not sweep the backup: an item layout has no Scene "
                "name for a Task's Element action to address it by, so there is nothing to rewrite.",
            ),
        ).classes("text-xs text-gray-500 italic mt-1")

        _build_legacy_designer(nested, field_refs)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(
                translate_string("Done"),
                on_click=lambda: (dialog.close(), on_closed()),
            ).classes("bg-blue-600")

    dialog.open()


def _apply_item_layout_size(
    nested: sceneedit.EditableScene,
    field_refs: dict,
    key: str,
) -> None:
    """Write one of the item layout's two size fields through, on blur.

    On blur rather than on every keystroke: a half-typed "10" on the way to "103" is a real
    number and would resize the canvas to it, which makes typing one feel like a fight.

    Written straight through rather than collected at save time because this dialog has no
    save -- it is editing the outer dialog's copy in place (see _build_item_layout_dialog).
    """
    widget = field_refs.get(key)
    if widget is None:
        return
    value = str(widget.value).strip()
    try:
        int(value)
    except ValueError:
        ui.notify(translate_string("Size must be a whole number (-1 for no layout)."), type="negative")
        widget.value = nested.scene_element.findtext(key, sceneedit.UNSET_DIMENSION)
        return
    sceneedit.set_scene_dimensions(nested, {key: value})


def _render_legacy_colour_arg(arg: taskedit.EditableArg, commit: Callable[[Event], None]) -> None:
    """A Legacy element's colour: the same picker the V2 designer's colours use, over a value
    written the other way round.

    Tasker stores #AARRGGBB and every colour picker there is speaks #RRGGBBAA, so the field
    shows the converted value and converts back before committing (see
    sceneedit.legacy_colour_to_css, which is where that ordering is explained).  The picker
    itself is put into "hexa" so it returns the alpha rather than dropping it -- a Scene's
    "#77333333" is a deliberately half-transparent grey, and a picker that answered in plain
    #RRGGBB would quietly make it opaque.

    The committed value is re-shown afterwards.  A pick of an opaque colour comes back as
    eight digits, which stores as #FFRRGGBB and reads back out as six -- so writing that form
    into the field is what lets the swatch preview it.  That write is its own change event,
    which `settling` swallows: it would otherwise commit the identical colour a second time
    and repaint the canvas for it.
    """
    settling = {"busy": False}

    def commit_colour(event: Event) -> None:
        if settling["busy"]:
            return
        stored = sceneedit.legacy_colour_from_css(str(event.value or ""))
        event.value = stored
        commit(event)
        settling["busy"] = True
        try:
            field.value = sceneedit.legacy_colour_to_css(stored)
        finally:
            settling["busy"] = False

    field = (
        ui
        .color_input(
            label=translate_string(arg.arg_name),
            value=sceneedit.legacy_colour_to_css(arg.current_value),
            preview=True,
            on_change=commit_colour,
        )
        .props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}")
        .classes("flex-1")
    )
    field.picker.q_color.props('format-model="hexa"')


def _render_legacy_arg(
    arg: taskedit.EditableArg,
    on_applied: Callable[[], None],
    on_rename: Callable[[], None] | None = None,
    *,
    name_editable: bool = False,
) -> None:
    """One property field, rendered from the same EditableArg model the Task editor uses --
    so a dropdown, a checkbox and a variable-backed field look and behave identically
    wherever they appear in this app.

    Written through on change rather than collected at save time, matching the V2 designer:
    the inspector's widgets are destroyed on every selection change, so there would be
    nothing left to collect from.  Cancel still discards everything, because all of this is
    happening to the dialog's own deep copy of the Scene.

    `on_applied` RUNS WHILE THE FIELD STILL HAS FOCUS, and must therefore not rebuild the
    container these widgets are in -- it would destroy the one being typed into mid-word.  The
    designer passes its repaint(), which redraws the canvas and leaves the forms alone; see
    that function, which is where this used to go wrong.

    THE NAME FIELD IS THE EXCEPTION, and which exception depends on whose name it is:

      * A top-level element's name is what 18 Task action codes look it up by, so it is not
        typed into.  It gets a Rename button (`on_rename`) that opens a dialog naming what
        depends on the current name first -- see _build_rename_legacy_element_dialog.

      * A sub-element's name -- a background RectElement's, a PropertiesElement's -- is
        addressed by nothing at all: Tasker reaches those through their owner and their sr,
        never by name.  Those pass `name_editable` and are typed into like any other field.
    """
    is_name = arg.arg_id == "0" and arg.backing_tag == "Str" and not name_editable

    def commit(event: Event) -> None:
        value = event.value
        if arg.widget_kind == "checkbox":
            value = "1" if value else "0"
        errors = sceneedit.legacy_validate_arg(arg, str(value))
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return
        sceneedit.legacy_set_arg(arg, str(value))
        on_applied()

    with ui.row().classes("w-full items-center gap-2"):
        if is_name:
            ui.input(translate_string(arg.arg_name), value=arg.current_value).props("readonly dense").classes("flex-1")
            rename_button = ui.button(
                translate_string("Rename"),
                icon="drive_file_rename_outline",
                on_click=lambda: on_rename() if on_rename else None,
            ).props("dense flat size=sm")
            rename_button.set_enabled(on_rename is not None)
            with rename_button:
                ui.tooltip(
                    translate_string(
                        "Tasks address this element by name (Element Text, Element Position, ... 18 "
                        "action codes in all), so renaming it is not a field edit. The Rename dialog "
                        "lists what depends on the current name and offers to bring those Tasks along.",
                    ),
                ).style("white-space: pre-wrap")
        elif arg.widget_kind == "checkbox":
            ui.checkbox(translate_string(arg.arg_name), value=arg.current_value == "1", on_change=commit)
        elif arg.widget_kind == "dropdown":
            ui.select(
                arg.dropdown_options or [],
                value=_dropdown_current_label(arg),
                label=translate_string(arg.arg_name),
                on_change=commit,
            ).props("dense").classes("flex-1")
        elif arg.widget_kind == "readonly":
            ui.input(translate_string(arg.arg_name), value=arg.current_value).props("readonly dense").classes("flex-1")
            if arg.readonly_note:
                ui.label(translate_string(arg.readonly_note)).classes("text-xs text-gray-500 italic")
        elif sceneedit.legacy_is_colour_arg(arg):
            _render_legacy_colour_arg(arg, commit)
        else:  # "text" and "raw_fallback"
            # Debounced, unlike the checkbox and the dropdown above: those commit one whole
            # value per click, while this one is typed a character at a time.  See
            # FIELD_COMMIT_DEBOUNCE_MS, and repaint() for why the commit no longer takes the
            # caret with it either way.
            ui.input(translate_string(arg.arg_name), value=arg.current_value, on_change=commit).props(
                f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}",
            ).classes("flex-1")


def _build_scene_editor_body(
    _self: MyGui,
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    dialog: ui.dialog | None = None,
) -> None:
    """Renders the editable body shared by the Add Scene and Edit Scene dialogs --
    the Scene sibling of _build_profile_editor_body/the Task dialog's action list.
    Both callers supply their own Name field and their own button row; everything
    between the two is this.

    Branches on which kind of Scene it was handed (sceneedit.is_v2_scene), because
    the two have almost nothing in common below the name:

      Legacy -- editable size (the four <widthPort>/<heightPort>/<widthLand>/
      <heightLand> children Tasker lays the Scene out on), plus a read-only list
      of its UI elements.  -1 is Tasker's own "not laid out for this orientation"
      and is left alone as such (see sceneedit.UNSET_DIMENSION), which is why
      these are plain text inputs rather than number spinners -- a spinner would
      quietly turn a deliberate -1 into a 0-sized Scene.

      Version 2 -- no size fields at all, and a read-only outline of the component
      tree instead of an element list.  The size fields are omitted rather than
      shown-and-disabled because a V2 layout is declarative: there is no canvas
      to size, every real V2 Scene carries -1 across all four, and offering the
      four boxes would invite someone to set a number that means nothing.  Their
      absence from field_refs is what userintr._apply_scene_field_values reads as
      "nothing to validate here", so no size is ever written to a V2 Scene.

    Each branch then hands off to the designer for its kind -- _build_v2_designer
    for a component tree, _build_legacy_designer for a canvas -- and neither needs
    anything from either dialog beyond the field_refs dict it is already handed.
    What each designer does and does not yet edit is documented on it rather than
    here; both are still filling in, and this function's job is only to pick.

    Every widget it puts in field_refs is read back by
    userintr._apply_scene_field_values, which is the only thing that has to grow
    alongside it.

    `dialog` is the dialog this body is being built into, and is needed only by the
    Preview button: previewing has to close the dialog to get at the screen behind
    it, so it needs something to re-open afterwards (see NiceGuiSceneView).  It is
    optional so that a caller that has no dialog to hand still gets the whole body,
    minus that one button.
    """
    scene_element = edited_scene.scene_element
    is_v2 = sceneedit.is_v2_scene(scene_element)

    with ui.row().classes("w-full items-center gap-2 mt-1"):
        ui.label(
            f"{translate_string('Scene type')}: {translate_string(sceneedit.scene_version(scene_element))}",
        ).classes("text-sm text-gray-500 italic")
        ui.space()
        preview_button = ui.button(
            translate_string("Preview"),
            icon="visibility",
            on_click=lambda: _self.event_handlers.preview_scene_event(edited_scene, field_refs, dialog),
        ).props("dense outline")
        if dialog is not None:
            # Whatever this dialog changes, the picture it opened has to hear about when it
            # closes -- see repaint_scene_previews.  Registered here, beside the button that
            # creates that picture, so the Add and Edit dialogs both get it from the one
            # place that knows a preview is possible at all.
            dialog.on_value_change(lambda event: _scene_dialog_closed(_self, dialog, field_refs, event))
        with preview_button:
            # Two Scenes, two things the preview is drawing from, so two tooltips: a Legacy
            # Scene is previewed at the size typed into the fields below, a V2 Scene at a
            # screen size the preview itself offers, because a V2 layout has none.
            ui.tooltip(
                (
                    translate_string(
                        "Draws this Scene as a picture in the main window -- including the components "
                        "you have added or changed here but not yet saved.\n\n"
                        "A Version 2 layout has no size of its own, so the preview lays it out in a screen "
                        "you pick, and re-flows it when you change that.\n\n"
                        "This dialog closes while the preview is up, with everything in it kept; the "
                        "preview's 'Back to Editor' button brings it back.\n\n"
                        "It is a representation, not Tasker's own renderer: %variables are named rather "
                        "than resolved, Material colours come from the baseline palette rather than the "
                        "device's theme, and images, video and web content are shown as placeholders.",
                    )
                    if is_v2
                    else translate_string(
                        "Draws this Scene as a picture in the main window, at the size typed above -- "
                        "including changes not yet saved.\n\n"
                        "This dialog closes while the preview is up, with everything in it kept; the "
                        "preview's 'Back to Editor' button brings it back.\n\n"
                        "It is a representation, not Tasker's own renderer: %variables are named rather "
                        "than resolved, and images, video and web content are shown as placeholders.",
                    )
                ),
            ).style("white-space: pre-wrap")

    if is_v2:
        layout = sceneedit.decode_v2_layout(scene_element)
        if layout is None:
            ui.label(
                translate_string("This Scene's Version 2 layout could not be read, and will be left exactly as it is."),
            ).classes("text-sm text-orange-600 mt-2")
            return
        _build_v2_designer(edited_scene, field_refs, layout)
        return

    with ui.row().classes("w-full gap-2 mt-2"):
        for key, label in sceneedit.SCENE_DIMENSION_FIELDS:
            field_refs[key] = (
                ui
                .input(
                    translate_string(label),
                    value=scene_element.findtext(key, sceneedit.UNSET_DIMENSION),
                )
                .classes("w-36")
                .props("dense")
            )
    ui.label(translate_string("-1 means this orientation has no layout of its own.")).classes(
        "text-xs text-gray-500 italic",
    )

    _build_legacy_designer(edited_scene, field_refs)


def build_add_scene_version_dialog(self: MyGui, target_project_name: str) -> None:
    """Asks which kind of Scene to add -- Legacy or Version 2 -- and is what the
    "Add Scene" button actually opens; the Add Scene dialog itself comes second,
    once the answer is known (see userintr.add_scene_of_version_event).

    The choice is made up front, in its own prompt, rather than as a toggle
    inside the Add Scene dialog, because it isn't a field of the Scene -- it
    decides what the Scene *is*, and therefore what that dialog can even show:
    a Legacy Scene has a pixel canvas and an element list, a V2 Scene has a
    component tree and no canvas at all (see _build_scene_editor_body, which
    branches on exactly this).  A toggle would have to tear down and rebuild the
    whole dialog body on every flip, and would let someone type a Scene's details
    and then change what kind of Scene they were describing.

    There is no equivalent prompt on Edit Scene: an existing Scene's kind is a
    property of the Scene, not a choice, and Tasker offers no conversion between
    the two -- the layouts have nothing in common (x/y geometry vs. declarative
    components), so there is nothing this app could honestly convert.
    """
    with ui.dialog().props("persistent") as version_dialog, ui.card().classes("min-w-[450px] max-w-[650px] w-full p-6"):
        ui.label(translate_string("Add Scene")).classes("text-xl font-bold text-blue-600")
        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )
        ui.label(translate_string("Which kind of Scene?")).classes("text-base mt-3")

        # Legacy is one choice; Version 2 is four, because for a component tree "what do I
        # start from" is the same question as "which kind" -- an empty Column and a titled
        # dialog are different enough that asking separately, after the fact, would mean
        # answering the more consequential half second.
        ui.label(translate_string("Legacy")).classes("text-sm font-semibold mt-2")
        ui.label(
            translate_string(
                "The original Scene: UI elements placed at fixed positions on a sized canvas "
                "(Text, Button, Rect, Image, Web, ...).",
            ),
        ).classes("text-xs text-gray-500")
        legacy = ui.button(
            translate_string("Legacy Scene"),
            on_click=lambda: self.event_handlers.add_scene_of_version_event(
                sceneedit.SCENE_VERSION_LEGACY,
                "",
                target_project_name,
                version_dialog,
            ),
        ).classes("bg-blue-600 mt-1")
        with legacy:
            ui.tooltip(
                translate_string(
                    "A Legacy Scene has a pixel canvas and a list of UI elements. It is the "
                    "original Scene format, and is what Tasker itself produces.",
                ),
            )

        ui.label(translate_string("Version 2")).classes("text-sm font-semibold mt-4")
        ui.label(
            translate_string(
                "Tasker's Screen Builder: a declarative component tree (Column, Row, Scaffold, ...) "
                "that lays itself out, with no fixed canvas size. Start from:",
            ),
        ).classes("text-xs text-gray-500")
        with ui.column().classes("w-full gap-1 mt-1"):
            for label, description, _builder in sceneedit.V2_TEMPLATES:
                with ui.row().classes("w-full items-center gap-2"):
                    # Bind the loop variable per iteration -- a bare closure over `label`
                    # would hand every button the last one.
                    ui.button(
                        translate_string(label),
                        on_click=lambda _e=None, chosen=label: self.event_handlers.add_scene_of_version_event(
                            sceneedit.SCENE_VERSION_V2,
                            chosen,
                            target_project_name,
                            version_dialog,
                        ),
                    ).classes("bg-blue-600 w-48")
                    ui.label(translate_string(description)).classes("text-xs text-gray-500")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=version_dialog.close).props("outline")

    version_dialog.open()


def build_add_scene_dialog(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    target_project_name: str,
) -> None:
    """Builds and opens the Add Scene dialog for a Scene of the kind already
    chosen in build_add_scene_version_dialog: create it, empty, and attach it to
    the currently selected Project.  edited_scene arrives already built as Legacy
    or V2 (sceneedit.create_new_scene), and the body renders itself accordingly --
    nothing here has to know which it got.

    A Project is required, for the same reason Add Profile/Add Task require one:
    a Scene only shows up in the Map/Diagram/Tree views if some Project's <scenes>
    element names it (scenes.process_project_scenes reads exactly that -- not the
    all_scenes lookup table sceneedit.register_new_scene populates), so a Scene
    registered without one exists but is invisible everywhere except the Scene
    pulldown.  See sceneedit.add_scene_to_project.

    Like Add Project, there is no Save/Export surface here -- a Scene that was
    created a moment ago has nothing in it to export.  Create it, then use Edit
    Scene, which does (see build_edit_scene_dialog).
    """
    field_refs: dict = {"target_project_name": target_project_name}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[800px] w-full p-6"):
        ui.label(
            f"{translate_string('Add Scene')}: {translate_string(sceneedit.scene_version(edited_scene.scene_element))}",
        ).classes("text-xl font-bold text-blue-600")

        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )

        field_refs["name"] = ui.input(translate_string("Scene Name"), value="").classes("w-full")

        _build_scene_editor_body(self, edited_scene, field_refs, dialog)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_scene_event(edited_scene, field_refs, dialog),
            ).classes("bg-blue-600")

    dialog.open()


def repaint_scene_previews(gui: MyGui, dialog: ui.dialog) -> None:
    """Redraw every Scene preview this dialog put on screen.

    WHY A DIALOG CLOSING HAS TO REACH THE PICTURE BEHIND IT.  A preview draws from the
    dialog's live state -- for a Legacy Scene, edited_scene.scene_element itself -- and then
    never looks at it again; it repaints on its own toolbar, its own gestures and its own
    Refresh button, none of which is what just happened.  So the sequence Preview, Back to
    Editor, move something in the designer, Ok leaves the picture the user is returned to
    showing the geometry from before the move, with nothing on screen to say it is out of
    date.  Repainting is a few hundred divs and the state it reads is already in hand.

    Matched on the dialog the view was launched from rather than on the Scene's name,
    because that is the relationship that actually holds: a view holds the dialog it has to
    re-open, names can be changed by the Rename button mid-session, and two dialogs on the
    same Scene are a thing this app can produce (see _build_item_layout_dialog).

    Deliberately not called when Preview is what closed the dialog: that path is on its way
    to building a *new* view over a cleared content_container, and repainting the outgoing
    one into a container about to be emptied is work at best and a draw into a detached
    element at worst.  See preview_scene_event, which marks the session suspended first so
    that _scene_dialog_closed can tell the two apart.
    """
    for view in live_views(gui):
        if isinstance(view, NiceGuiSceneView) and getattr(view, "dialog", None) is dialog:
            view.render()


def _scene_dialog_closed(gui: MyGui, dialog: ui.dialog, field_refs: dict, event: Event) -> None:
    """One place every way of closing a Scene dialog goes through.

    Hung on the dialog's own value rather than on its buttons because there are eight of
    them across the two dialogs -- Cancel, Ok, Delete, Rename, three kinds of Save, Export --
    and they close it through six different event handlers in userintr.  A ninth button
    added later would be one more that forgot to repaint; the value cannot be.

    THE PREVIEW STOPS BEING AN EDITING SURFACE HERE, which is half of drawing the right
    thing rather than merely a fresh thing.  A preview is editable only while the designer
    that opened it is alive to take the edit (see NiceGuiSceneView._legacy_editing), and
    these two keys are how it finds one -- but the closures in them outlive the dialog,
    because NiceGUI hides a dialog rather than destroying it.  Left in place, the repainted
    picture would go on offering drags into an editor the user has just finished with: after
    Cancel they would land on a deep copy that was abandoned by definition, and after Ok on
    one whose contents have already been written to the live tree.  Both would move on
    screen, and neither would reach the Scene.  Dropping the keys turns the picture back
    into a picture, which is what it now is.
    """
    if event.value:
        return  # opening, not closing
    session = getattr(gui, "scene_editor_session", None)
    if session and session.get("dialog") is dialog and session.get("suspended"):
        return  # Preview is holding it hidden -- see repaint_scene_previews
    for key in ("v2_edit", "legacy_edit"):
        field_refs.pop(key, None)
    repaint_scene_previews(gui, dialog)


def suspend_scene_editor_session(gui: MyGui, dialog: ui.dialog) -> None:
    """Mark the Edit Scene dialog as hidden-but-alive, which is what Preview does to it.

    Only the Edit Scene dialog is tracked (build_edit_scene_dialog records it); previewing
    from Add Scene finds no match here and is left alone, so nothing can resume a half-built
    Scene that is not in the tree yet.
    """
    session = getattr(gui, "scene_editor_session", None)
    if session and session.get("dialog") is dialog:
        session["suspended"] = True


def _resume_scene_editor_session(gui: MyGui, dialog: ui.dialog) -> None:
    """Clear the suspended mark -- the dialog is being put back on screen."""
    session = getattr(gui, "scene_editor_session", None)
    if session and session.get("dialog") is dialog:
        session["suspended"] = False


def suspended_scene_editor(gui: MyGui, scene_name: str) -> ui.dialog | None:
    """The Edit Scene dialog for `scene_name` that a preview is currently holding hidden,
    or None if there isn't one.  Resuming is the caller's job; this marks it resumed.

    The mark exists only between Preview closing the dialog and something re-opening it, so
    a dialog closed for good by Cancel/Ok/Delete is never handed back: those all run while
    the dialog is on screen, which by definition is not suspended.
    """
    session = getattr(gui, "scene_editor_session", None)
    if not session or not session.get("suspended") or session.get("name") != scene_name:
        return None
    session["suspended"] = False
    return session["dialog"]


def build_edit_scene_dialog(self: MyGui, edited_scene: sceneedit.EditableScene) -> None:
    """Builds and opens the Edit Scene dialog: edit the Scene's size, rename it
    (the Name field is read-only -- Rename prompts for the new one, see
    build_rename_dialog), delete it -- removing it from every Project that lists
    it, see build_delete_scene_dialog -- or save it, either as a standalone
    .scn.xml file (sceneedit.write_standalone_scene_xml), back into a timestamped
    copy of the whole backup, or onto the Android device under /Tasker/scenes
    (see build_save_scene_to_android_dialog).

    Rename gets its own prompt here rather than a live Name field for the reason
    it does everywhere else, and then some: a Scene's name is its identity in
    four places at once (see sceneedit.py's module docstring), so applying one is
    a real operation across the whole backup, not a field edit.
    """
    scene_name = edited_scene.scene_name
    field_refs: dict = {}
    # The Scene as this session found it.  Taken before the body is built, so it is the
    # state Cancel returns to however much the designers go on to change.  See cancel().
    opened_as = sceneedit.session_snapshot(edited_scene)

    def cancel() -> None:
        """Discard this session's work, then close.

        Reverting rather than only closing, because a Preview holds the same element and
        keeps drawing it: without this, elements dragged in the preview stayed where they
        were dropped after Cancel, which reads as Cancel having failed.  See
        sceneedit.revert_session for what is and is not being undone.

        Ordering matters both ways round it: the revert has to happen before the close,
        because closing is what repaints the preview (_scene_dialog_closed), and the notice
        has to come after, because a dialog closing over a notification hides it.

        Rename cannot have happened first -- it applies to the live backup and closes this
        dialog itself (userintr.confirm_rename_scene_event) -- so there is no applied change
        for a later Cancel to be quietly failing to undo.
        """
        discarded = sceneedit.revert_session(edited_scene, opened_as, field_refs.get("v2_layout"))
        dialog.close()
        if discarded:
            # Only when there was something to discard: a Cancel out of a dialog nobody
            # changed is not an event, and saying so every time would train the notice away.
            ui.notify(
                translate_string("Cancelled. Changes to this Scene were discarded."),
                type="info",
            )

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[800px] w-full p-6"):
        ui.label(f"{translate_string('Edit Scene')}: {scene_name}").classes("text-xl font-bold text-blue-600")
        # The kind of Scene is stated in the body too (see _build_scene_editor_body); it
        # is here as well because it is why the body looks the way it does.

        # Read-only -- renamed only through the Rename button's prompt; see
        # build_edit_project_dialog's identical Name field for why.
        field_refs["name"] = (
            ui.input(translate_string("Scene Name"), value=scene_name).props("readonly").classes("w-full")
        )

        _build_scene_editor_body(self, edited_scene, field_refs, dialog)

        field_refs["scene_save_path"] = ui.input(
            translate_string("Save as"),
            value=sceneedit.default_scene_save_path(scene_name),
        ).classes("w-full mt-2")

        # The two Scene-only pieces of state, for the same reason revert_session has to take
        # them separately: a Version 2 session leaves the element alone from beginning to end
        # -- its work is in the decoded layout dict until a save encodes it back into <lj> --
        # so comparing elements alone would call a reordered, retyped, half-rebuilt V2 Scene
        # unchanged; and element_renames is a list of renames held pending against the live
        # Tasks, which is unsaved work by definition.  Both are reduced to their repr here
        # because the value has to be a snapshot: the dict is the live one the designer goes
        # on editing, so keeping it would only ever be compared against itself.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(
            dialog,
            lambda: editor_state(
                edited_scene.scene_element,
                field_refs,
                repr(field_refs.get("v2_layout")),
                repr(edited_scene.element_renames),
            ),
        )

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            cancel_button = ui.button(translate_string("Cancel"), on_click=cancel).props("outline")
            with cancel_button:
                ui.tooltip(
                    translate_string(
                        "Closes without saving, and puts this Scene back exactly as it was when this "
                        "dialog opened -- including anything moved or resized in the Preview.\n\n"
                        "A Rename is the one thing this cannot take back: it is applied to the loaded "
                        "backup as it is confirmed, and closes this dialog with it.",
                    ),
                ).style("white-space: pre-wrap")
            ui.button(
                translate_string("Delete Scene"),
                on_click=lambda: self.event_handlers.delete_scene_event(edited_scene, dialog),
            ).classes("bg-red-500 text-white")
            rename_scene_button = ui.button(
                translate_string("Rename"),
                on_click=lambda: self.event_handlers.rename_scene_event(edited_scene, dialog),
            ).classes("bg-blue-600")
            with rename_scene_button:
                ui.tooltip(
                    translate_string(
                        "Prompts for a new name and applies it to the loaded backup, right now -- "
                        "renaming the Scene everywhere, including in the Scene list of every Project "
                        "that holds it.\n\n"
                        "Tasks that show or hide this Scene by name are NOT updated; those still name "
                        "the old Scene.\n\n"
                        "The Scene Name field above is read-only -- this is the only way to change it.",
                    ),
                ).style("white-space: pre-wrap")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.save_edited_scene_event(edited_scene, field_refs, dialog),
            ).props("outline")
            scene_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_scene_to_current_file_event(
                    edited_scene,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with scene_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile, Task and Scene in it, not just this "
                        "Scene -- including every edit made anywhere in this session.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            scene_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_scene_to_android_dialog_event(
                    edited_scene,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with scene_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Scene as a standalone file onto your Android device, under "
                        "/Tasker/scenes -- it does not import it into Tasker's live configuration.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                        "device, with the server running.\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings. No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            export_scene = ui.button(
                translate_string("Export Scene"),
                on_click=lambda: self.event_handlers.save_scene_event(edited_scene, field_refs, dialog),
            ).classes("bg-blue-600")
            with export_scene:
                ui.tooltip(
                    translate_string(
                        "Saves this Scene, with all of its elements, as one standalone .scn.xml file -- the same "
                        "format Tasker's own Scene export produces.\n\n"
                        "Tasks the Scene's elements run are not included; they belong to their own Project.",
                    ),
                ).style("white-space: pre-wrap")

    # Preview has to close this dialog to get at the screen behind it, and the work in
    # progress lives in the dialog's widgets and field_refs -- not in the live tree, which
    # nothing writes to until a save button runs.  Remembering the dialog is what lets the
    # "Edit Scene" button resume it (userintr.open_edit_scene_dialog_event) rather than
    # build a second one from the unedited tree, showing none of the pending edits.
    self.scene_editor_session = {"name": scene_name, "dialog": dialog, "suspended": False}
    dialog.open()


def build_delete_scene_dialog(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Scene.  Like the Profile and Task dialogs there is
    no Keep/Delete Contents choice -- a Scene's UI elements are children of the
    Scene element itself and go with it -- but, like a Task, other things point
    *at* a Scene, so the dialog says how many Projects lose it (see
    sceneedit.delete_scene).

    The reference count is read live so it can't go stale between opening Edit
    Scene and clicking Delete, same as the Project/Profile/Task dialogs' counts.
    """
    scene_name = edited_scene.scene_name
    project_count = sceneedit.count_scene_references(scene_name)

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Scene')} '{scene_name}'").classes("text-lg font-bold text-red-600")
        ui.label(
            f"{translate_string('It will be removed from')} {project_count} "
            f"{translate_string('Project(s) that list it.')}",
        ).classes("mt-1")
        ui.label(
            translate_string(
                "Tasks that show or hide this Scene by name are not changed, and are left where they are.",
            ),
        ).classes("text-xs text-gray-500 italic mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Delete Scene"),
                on_click=lambda: self.event_handlers.confirm_delete_scene_event(
                    scene_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_save_scene_to_android_dialog(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    parent_dialog: ui.dialog,
) -> None:
    """Prompts for the Android device's IP address and port, then writes the
    Scene as a standalone .scn.xml file onto the device's storage under
    /Tasker/scenes, via the Tasker HTTP Server Example's /upload endpoint (see
    sceneedit.save_scene_to_android).  This does not import it into Tasker's live
    configuration.  On success both this prompt and the parent (Edit Scene)
    dialog are closed.  Mirrors build_save_project_to_android_dialog.

    field_refs is the parent dialog's, and is carried through for the save
    handler, which applies those edits before uploading -- the upload renders
    from the live tree, so what is not applied is not sent.  The Scene still goes
    up under its current name: a not-yet-applied Rename does not carry through,
    since Rename is its own operation rather than a field on the dialog.
    """
    default_ip = getattr(self, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(self, "android_port", "") or "1821"

    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Scene To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = {
            "ip_address": ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full"),
            "ip_port": ui.input(translate_string("Port"), value=default_port).classes("w-full"),
        }
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.save_scene_to_android_event(
                    edited_scene,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            with save_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Scene as a standalone file onto the Android device, "
                        "under /Tasker/scenes.\n\n"
                        "The IP Address and Port must match the Android device's Tasker server settings.\n\n"
                        "No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            # The Profile and Project dialogs' pair, for a Scene -- see
            # build_save_profile_to_android_dialog for why these are two buttons.
            import_into_tasker = ui.button(
                translate_string("Import Into Tasker"),
                on_click=lambda: self.event_handlers.import_scene_into_tasker_event(
                    edited_scene,
                    field_refs,
                    android_field_refs,
                    android_dialog,
                    parent_dialog,
                ),
            ).classes("bg-blue-600")
            with import_into_tasker:
                ui.tooltip(
                    translate_string(
                        "This sends the Scene -- and every Task its elements fire -- to the Android "
                        "device under its own name, into /Tasker/scenes, and opens Android's "
                        "'Open with...' chooser for it.\n\n"
                        "If Tasker is in that chooser, pick it.  A Scene is the one kind Tasker has been "
                        "seen to refuse when it is handed one, so if it is not there -- or nothing "
                        "happens -- finish it with Tasker's 'Scenes > Import One Scene' and pick the "
                        "Scene by name.  The file is on the device either way, and the message tells you "
                        "its name.\n\n"
                        "You will be asked before it replaces a file already at that path.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and running, and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The device will ask you to authorize MapTasker the first time.",
                    ),
                ).style("white-space: pre-wrap")

    android_dialog.open()


def build_helper_tasks_dialog(stale: list[str], current: list[str], device: str) -> None:
    """Shows which of this program's own helper Tasks are dead on the Android device.

    A LIST, NOT A BUTTON, and that is the whole design: nothing here can delete them.  The
    Tasker HTTP Server Example has no route for deleting a Task -- its Task endpoints are GET
    (list) and POST (run), and its only DELETE removes a file from storage, which a Task in
    Tasker's configuration is not.  So this does the part that can be done: names them
    exactly, so the user works down a list in Tasker instead of guessing which
    'MapTasker Open Profile v2' is safe to remove.

    Why there are any: a helper's name carries a version because its BODY changes between
    releases and Tasker's api/import adds rather than replaces (see
    deviceinv._install_task_on_android), so the previous one is left behind, running fine and
    doing the wrong thing if it were ever used.  Nothing breaks while they sit there; they
    are clutter in a list the user owns.

    The current ones are shown too, and not as a footnote: this dialog is read next to
    Tasker's own Task list, and 'delete everything starting with MapTasker' is exactly the
    conclusion it must not invite.
    """
    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[420px] max-w-[680px] w-full p-6"):
        ui.label(translate_string("MapTasker Helper Tasks")).classes("text-lg font-bold text-blue-600")
        ui.label(f"{translate_string('On')} {device}").classes("text-xs text-gray-500")

        if stale:
            ui.label(
                f"{len(stale)} {translate_string('left over from an earlier version -- safe to delete in Tasker:')}",
            ).classes("mt-3 font-bold text-orange-600")
            with ui.column().classes("gap-0 mt-1"):
                for name in stale:
                    ui.label(name).classes("font-mono text-sm break-all")
            ui.label(
                translate_string(
                    "Delete them from Tasker's Tasks tab -- long-press one, then Delete.  Nothing here can "
                    "do it: Tasker's HTTP API has no way to delete a Task.",
                ),
            ).classes("text-xs text-gray-500 italic mt-2")
        else:
            ui.label(translate_string("Nothing left over -- every MapTasker Task on the device is in use.")).classes(
                "mt-3 text-green-600",
            )

        if current:
            ui.label(translate_string("In use -- leave these alone:")).classes("mt-4 font-bold")
            with ui.column().classes("gap-0 mt-1"):
                for name in current:
                    ui.label(name).classes("font-mono text-sm text-gray-500 break-all")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Close"), on_click=dialog.close).props("outline")

    dialog.open()


def build_overwrite_confirm_dialog(
    what_exists: str,
    on_confirm: Callable[[], None],
    *,
    unknown: bool = False,
) -> None:
    """Confirms overwriting something that is already there, before anything is
    written. Backs every Save/Export path that would otherwise clobber a file
    silently -- the local standalone exports and the Save To Android uploads
    (see userintr's save_* handlers).

    what_exists describes the thing in the user's terms (a full path); on_confirm
    performs the write and is called only if they choose "Overwrite". Cancel
    closes this dialog and leaves the parent Edit/Add dialog open, so nothing
    in progress is lost -- same convention as build_delete_project_dialog.

    unknown=True switches the wording for the case where existence could not be
    determined at all (maputil2.read_android_file returning None -- device
    unreachable mid-check). That is deliberately still a prompt rather than a
    silent write: the honest statement is "this might overwrite something", and
    the user is the one who knows whether that matters.
    """
    title = "Could not check destination" if unknown else "Already exists"
    body = (
        f"Could not confirm whether {what_exists} already exists. Saving may overwrite it."
        if unknown
        else f"{what_exists} already exists and will be replaced."
    )

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(title).classes("text-lg font-bold text-orange-600")
        ui.label(body).classes("mt-1 break-all")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")

            def _confirm() -> None:
                # Close first: on_confirm may open its own dialog (or close the
                # parent), and leaving this one stacked on top would hide it.
                confirm_dialog.close()
                on_confirm()

            ui.button(translate_string("Overwrite"), on_click=_confirm).classes("bg-orange-600 text-white")

    confirm_dialog.open()


def build_rename_dialog(
    self: MyGui,  # noqa: ARG001
    item_type: str,
    current_name: str,
    on_rename: Callable[[str, ui.dialog], None],
) -> None:
    """Prompts for a new name for a Project/Profile/Task, opened by the "Rename"
    button in that item's Edit dialog.

    The Edit dialogs' own Name field is read-only (see build_edit_task_dialog),
    so this prompt is the only place an existing item's name can be typed. That
    makes a rename an explicit, separately-confirmed action instead of a side
    effect of Ok/Save, and it routes every rename through the one path that
    checks the new name doesn't collide with another item's -- see
    taskedit.apply_task_rename/profedit.apply_profile_rename/
    projedit.apply_edits_to_project; Ok/Save's own apply_edits_to_task/
    apply_edits_to_profile deliberately don't look at other items' names, so
    typing into the old editable field could quietly produce two Tasks sharing
    one name.

    on_rename receives the typed name and this dialog, and owns closing it --
    only on success, so a rejected name (empty, or already taken) leaves the
    prompt open with the text still there to fix. Cancel closes just this
    prompt and leaves the parent Edit dialog exactly as it was, same convention
    as build_delete_profile_dialog.
    """
    with ui.dialog().props("persistent") as rename_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Rename')} {translate_string(item_type)} '{current_name}'").classes(
            "text-lg font-bold text-blue-600",
        )
        name_input = ui.input(translate_string("New name"), value=current_name).classes("w-full")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=rename_dialog.close).props("outline")
            ui.button(
                translate_string("Rename"),
                on_click=lambda: on_rename(name_input.value.strip(), rename_dialog),
            ).classes("bg-blue-600")

    rename_dialog.open()


def build_delete_profile_dialog(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Profile. Unlike build_delete_project_dialog there is
    no Keep/Delete Contents choice -- a Profile doesn't own its Entry/Exit Tasks
    (see profedit.delete_profile), so they are always kept, and the dialog says so
    explicitly rather than leaving the user to guess what "delete" reaches.

    The linked-Task count is read live so it can't go stale between opening Edit
    Profile and clicking Delete, same as build_delete_project_dialog's counts.
    """
    profile_name = edited_profile.profile_element.findtext("nme", "")
    task_count = profedit.count_profile_tasks(profile_name)

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Profile')} '{profile_name}'").classes("text-lg font-bold text-red-600")
        if task_count:
            ui.label(
                f"{translate_string('Its')} {task_count} {translate_string('linked Task(s) will be kept -- they belong to the Project, not to this Profile.')}",
            ).classes("mt-1")
        else:
            ui.label(translate_string("It has no linked Tasks.")).classes("mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Delete Profile"),
                on_click=lambda: self.event_handlers.confirm_delete_profile_event(
                    profile_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_delete_task_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Task. Like build_delete_profile_dialog there is no
    Keep/Delete Contents choice -- a Task owns nothing below it -- but unlike a
    Profile, other things point *at* a Task, so the dialog spells out exactly
    which references go away with it (see taskedit.delete_task): the owning
    Project(s)' Task list, and the Entry/Exit link of any Profile that runs it.

    The reference counts are read live so they can't go stale between opening
    Edit Task and clicking Delete, same as the Profile/Project dialogs' counts.
    """
    task_name = edited_task.task_element.findtext("nme", "")
    project_count, profile_count = taskedit.count_task_references(task_name)

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Task')} '{task_name}'").classes("text-lg font-bold text-red-600")
        ui.label(
            f"{translate_string('It will be removed from')} {project_count} {translate_string('Project(s) and unlinked from')}"
            f" {profile_count} {translate_string('Profile(s) that run it. Those Profiles themselves are kept.')}",
        ).classes("mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Delete Task"),
                on_click=lambda: self.event_handlers.confirm_delete_task_event(
                    task_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_delete_project_dialog(
    self: MyGui,
    edited_project: projedit.EditableProject,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Project, offering a choice for what happens to
    the Profiles/Tasks it owns: moved into "Base" (Keep Contents) or deleted
    along with it (Delete Contents) -- see projedit.delete_project. Shown
    before anything is mutated; the Profile/Task counts are read live so they
    can't go stale between opening Edit Project and clicking Delete.
    """
    project_name = edited_project.project_name
    profile_count, task_count = projedit.count_project_contents(project_name)

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Project')} '{project_name}'").classes("text-lg font-bold text-red-600")
        ui.label(
            f"{translate_string('It owns')} {profile_count} {translate_string('Profile(s) and')} {task_count} {translate_string('Task(s).')}",
        ).classes("mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Keep Contents"),
                on_click=lambda: self.event_handlers.keep_contents_delete_project_event(
                    project_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            ui.button(
                translate_string("Delete Contents"),
                on_click=lambda: self.event_handlers.delete_contents_delete_project_event(
                    project_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_add_profile_dialog(
    self: MyGui,
    edited_profile: profedit.EditableProfile,
    target_project_name: str = "",
) -> None:
    """Builds and opens the Add Profile dialog: create a new Profile, then the
    exact same Enabled/Disabled toggle, Entry/Exit Task Link/Unlink, and
    per-condition Add/Edit/Delete as Edit Profile (see
    _build_profile_editor_body, shared by both), plus the same Cancel/Ok/Save
    To Android/Save button row -- mirrors build_add_task_dialog's relationship
    to build_edit_task_dialog.

    target_project_name is the single Project the top-level "Add Profile"
    button requires be selected before this dialog opens (see
    userintr.open_add_profile_dialog_event) -- stored in field_refs (not a
    widget; there's nothing here for the user to change) purely so
    _validate_and_apply_new_profile/save_profile_to_android_event can read it
    back and attach the new Profile to that Project (see
    profedit.add_profile_to_project) once it's registered. A Profile only
    shows up in the Project/Profile/Task pulldowns, Map, Diagram, or Tree
    views if some Project's <pids> element lists its id (see
    userintr.build_the_tree/projects.process_project_profiles, both driven by
    getids.get_ids -- not by the all_profiles lookup table register_new_profile
    populates), which is why a Project is required at all.
    """
    field_refs: dict = {"target_project_name": target_project_name}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label(translate_string("Add Profile")).classes("text-xl font-bold text-blue-600")

        last_auto_path = {"value": profedit.default_save_path("")}

        def sync_save_path(_e: object = None) -> None:
            # Keep "Save as" in sync with the Profile Name as the user types --
            # see build_add_task_dialog's identical sync_save_path for why this
            # only overwrites the path while it still holds what was last auto-computed.
            if field_refs["save_path"].value == last_auto_path["value"]:
                new_path = profedit.default_save_path(field_refs["name"].value)
                field_refs["save_path"].value = new_path
                last_auto_path["value"] = new_path

        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )

        field_refs["name"] = ui.input(translate_string("Profile Name"), value="", on_change=sync_save_path).classes(
            "w-full",
        )

        _build_profile_editor_body(self, edited_profile, field_refs)

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=last_auto_path["value"],
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_profile_event(edited_profile, field_refs, dialog),
            ).props("outline")
            new_profile_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_new_profile_to_current_file_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with new_profile_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this one -- "
                        "with the new Profile added to its Project, the same way 'Ok' adds it.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            profile_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_profile_to_android_dialog_event(
                    edited_profile,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with profile_to_android:
                ui.tooltip(
                    translate_string(
                        "This will write the Profile as a standalone file onto your Android device, "
                        "under /Tasker/profiles -- it does not import it into Tasker's live configuration.\n\n"
                        "The 'Http Server Example' Tasker Project (http://spoo.me/http_svr_example) must be installed and active on the Android "
                        "device, with the server running (see the README's Direct XML Retrieval notes).\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings. No authorization prompt is needed for this.",
                    ),
                ).style("white-space: pre-wrap")
            export_prof = ui.button(
                translate_string("Export Profile"),
                on_click=lambda: self.event_handlers.save_new_profile_event(edited_profile, field_refs, dialog),
            ).classes("bg-blue-600")
            with export_prof:
                ui.tooltip(
                    translate_string(
                        "Saves this Profile, with all of its conditions and linked Tasks, as one standalone .prf.xml file -- the same format Tasker's own Profile export produces.\n\n"
                        "Tasks the Profile runs are not included; they belong to their own Project.",
                    ),
                ).style("white-space: pre-wrap")

    dialog.open()


def build_add_task_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    on_task_created: Callable[[str], None] | None = None,
    target_project_name: str = "",
) -> None:
    """Builds and opens the Add Task dialog: create a new Task, search/filter actions
    by name or category to add to it, edit their synthesized default argument values,
    remove any if needed, then save as a standalone .tsk.xml -- see taskedit.py for
    what's addable and why (roughly 3 in 4 action types; the rest need an App/Icon
    picker or are third-party plugin configs with no generic default, and show up
    greyed out with a reason instead of being clickable).

    Both the action picker and the "added so far" list are rebuilt (not just
    appended to) after every Add/Remove, since removing an action renumbers every
    action after it -- their field_refs keys (which embed act_number) would
    otherwise go stale.

    on_task_created, if given, is called with the new Task's id once Ok/Save/
    Save To Android actually registers it into the live tree -- the hook
    open_add_task_for_profile_link_event uses to link this brand-new Task in
    as a Profile's Entry/Exit Task the moment it exists, without this dialog
    (or its Save/Ok/Save To Android handlers) needing to know anything about
    Profiles itself.

    target_project_name is the single Project the top-level "Add Task" button
    requires be selected before this dialog opens (see
    userintr.open_add_task_dialog_event) -- stored in field_refs (not a widget;
    there's nothing here for the user to change) purely so _finish_new_task can
    read it back and add the new Task's id to that Project's <tids> once it's
    registered. Left "" for open_add_task_for_profile_link_event's nested
    dialog, which doesn't attach to a Project at all.
    """
    field_refs: dict = {"target_project_name": target_project_name}
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions()})
    # Same out-of-band Position-label -> act_number map as build_edit_task_dialog's.
    position_labels: dict[str, int | None] = {}
    # Same per-action If condition value cache as build_edit_task_dialog's.
    condition_cache: dict[int, tuple[str, str, str]] = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label(translate_string("Add Task")).classes("text-xl font-bold text-blue-600")

        last_auto_path = {"value": taskedit.default_save_path("")}

        def sync_save_path(_e: ui.event | None = None) -> None:
            # Keep "Save as" in sync with the Task Name as the user types, so the
            # file actually lands under the name they gave the task -- but only
            # while it still holds what we last auto-computed; if the user has
            # since edited it manually, leave their edit alone. (Can't tell "manual
            # edit" apart via save_path's own on_change: NiceGUI fires that for
            # programmatic value sets too, so it would trip on the very first sync.)
            if field_refs["save_path"].value == last_auto_path["value"]:
                new_path = taskedit.default_save_path(field_refs["name"].value)
                field_refs["save_path"].value = new_path
                last_auto_path["value"] = new_path

        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )

        with ui.row().classes("w-full gap-4"):
            field_refs["name"] = ui.input(translate_string("Task Name"), value="", on_change=sync_save_path).classes(
                "flex-1",
            )
            field_refs["priority"] = ui.input(translate_string("Priority"), value="100").classes("w-32")

        ui.label(translate_string("Add an action")).classes("text-sm font-bold mt-2")
        with ui.row().classes("w-full gap-4"):
            search_input = ui.input(translate_string("Search actions")).classes("flex-1")
            category_select = ui.select(["All", *category_names], value="All").classes("w-48")
        position_select = (
            ui.select([], label=translate_string("Position"), with_input=True).classes("w-full").props("dense")
        )

        picker_container = ui.column().classes("w-full")
        ui.label(translate_string("Actions in this Task")).classes("text-sm font-bold mt-2")
        added_container = ui.column().classes("w-full")
        # act_number of the action most recently added in this dialog session --
        # render_added_actions highlights it so it's easy to spot in a long list.
        last_added_act_number: int | None = None

        def clear_last_added() -> None:
            # Remove renumbers the list, so a stale act_number here would risk
            # highlighting the wrong action -- drop the highlight instead of
            # letting it follow whatever action inherits the number.
            nonlocal last_added_act_number
            last_added_act_number = None

        def refresh_position_options() -> None:
            _refresh_position_options(edited_task, position_select, position_labels)

        def render_added_actions() -> None:
            # Rebuild from scratch -- a Remove renumbers every action after it, so
            # stale act*_arg* keys must not survive into the next Save.
            for key in [k for k in field_refs if k.startswith("act")]:
                del field_refs[key]
            added_container.clear()
            with added_container:
                if not edited_task.actions:
                    ui.label(translate_string("No actions added yet.")).classes("text-xs text-gray-500 italic")
                indent_spaces = _action_indent_spaces(self)
                display_levels = taskedit.action_display_levels(edited_task.actions)
                for action, nest_level in zip(edited_task.actions, display_levels, strict=True):
                    # Indent with non-breaking spaces -- plain ones collapse in the rendered header.
                    indent_pad = "\u00a0" * (indent_spaces * nest_level)
                    is_last_added = action.act_number == last_added_act_number
                    header = f"{indent_pad}{action.act_number}: {action.action_name}"
                    if is_last_added:
                        header += "  \u2190 just added"
                    action_expansion = ui.expansion(header, value=is_last_added).classes("w-full")
                    if is_last_added:
                        action_expansion.classes("bg-amber-100 dark:bg-amber-900 border-2 border-amber-400 rounded")
                    with action_expansion:
                        field_refs[taskedit.label_key(action.act_number)] = ui.input(
                            translate_string("Label"),
                            value=taskedit.get_action_label(action),
                        ).classes("w-full")
                        if action.code != taskedit.IF_ACTION_CODE:
                            _render_action_condition_checkbox(self, edited_task, action, condition_cache)
                        _render_continue_after_error_checkbox(self, edited_task, action)
                        _render_plugin_configuration_warning(action.action_element, action.action_name)
                        for arg in action.args:
                            key = taskedit.arg_key(action.act_number, arg.arg_id)
                            with ui.row().classes("w-full items-center gap-2"):
                                if arg.widget_kind == "checkbox":
                                    field_refs[key] = ui.checkbox(arg.arg_name, value=arg.current_value == "1")
                                elif arg.widget_kind == "dropdown":
                                    options = arg.dropdown_options or []
                                    field_refs[key] = ui.select(
                                        options,
                                        value=_dropdown_current_label(arg),
                                        label=arg.arg_name,
                                    ).classes("flex-1")
                                elif taskedit.is_perform_task_name_arg(action.code, arg):
                                    _render_task_name_field(self, action, arg, key, field_refs)
                                elif arg.widget_kind == "app_picker":
                                    _render_app_arg_field(self, arg, key, field_refs)
                                elif arg.widget_kind == "icon_picker":
                                    _render_icon_arg_field(self, arg, key, field_refs)
                                elif arg.widget_kind == "readonly":
                                    # A newly-added plugin action's payload (see
                                    # taskedit._synthesize_bundle_arg): not editable here,
                                    # and apply_arg_values skips it, so never a field_ref.
                                    ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes(
                                        "flex-1",
                                    )
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_inventory_fetch(render_added_actions, action),
                                        )
                                else:  # "text" or "raw_fallback"
                                    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")
                        ui.button(
                            translate_string("Remove"),
                            on_click=lambda n=action.act_number: (
                                clear_last_added(),
                                self.event_handlers.remove_action_from_new_task_event(edited_task, n),
                                render_added_actions(),
                                refresh_position_options(),
                            ),
                        ).props("flat color=red dense")

        def add_picked_action(action_key: str) -> None:
            nonlocal last_added_act_number
            # Same "If" block prompt and Position handling as
            # build_edit_task_dialog's picker.
            if action_key == taskedit.IF_ACTION_KEY:

                def _add_if_block(variant: str) -> None:
                    nonlocal last_added_act_number
                    act_number = self.event_handlers.add_if_block_to_new_task_event(
                        edited_task,
                        variant,
                        position_labels.get(position_select.value),
                    )
                    if act_number is not None:
                        last_added_act_number = act_number
                    render_added_actions()
                    refresh_position_options()

                build_if_variant_dialog(_add_if_block)
                return
            act_number = self.event_handlers.add_action_to_new_task_event(
                edited_task,
                action_key,
                position_labels.get(position_select.value),
            )
            if act_number is not None:
                last_added_act_number = act_number
            render_added_actions()
            refresh_position_options()

        def refresh_picker(_e: ui.event | None = None) -> None:
            picker_container.clear()
            rows = taskedit.search_addable_actions(search_input.value, category_select.value)
            with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
                for row in rows:
                    if row["addable"]:
                        ui.button(
                            f"{row['name']} ({row['category_name']})",
                            on_click=lambda r=row: add_picked_action(r["action_key"]),
                        ).props("flat align=left dense").classes("w-full justify-start")
                    else:
                        with ui.column().classes("w-full gap-0"):
                            ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                            _render_addability_reason(self, row["reason"], refresh_picker)

        search_input.on_value_change(refresh_picker)
        category_select.on_value_change(refresh_picker)
        refresh_picker()
        refresh_position_options()
        render_added_actions()

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=last_auto_path["value"],
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_task_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            new_task_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_new_task_to_current_file_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            with new_task_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this one -- "
                        "with the new Task added to it, the same way 'Ok' adds it.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_to_android_dialog_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            export_task = ui.button(
                translate_string("Export Task"),
                on_click=lambda: self.event_handlers.save_new_task_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).classes("bg-blue-600")
            with export_task:
                ui.tooltip(
                    translate_string(
                        "Exports the Task as XML to a file on your computer.",
                    ),
                ).style("white-space: pre-wrap")

    dialog.open()


# ==========================================
# 3. VIEWS (Tree and Text)
# ==========================================
# Pre-compile the regex pattern at the module level for maximum execution performance.
# This scans the HTML string and hits all target replacements in a single pass O(N).
HTML_OPTIMIZE_PATTERN = re.compile(
    r"(\n\n\n|\n\n|<br>\n<br><br>|\n<br><br>|<br>\n|<br><br>|<br></span>|\n<br>|<h2>MapTasker</h2>|<h2><span class=\"normtab\"></span>Directory</h2>)",
)

# Map the targeted string matches directly to their optimized counterparts.
HTML_REPLACEMENT_MAP = {
    "\n\n\n": "",
    "\n\n": "",
    "<br>\n<br><br>": "",
    "\n<br><br>": "<br>",
    "<br>\n": "<br>",
    "<br><br>": "<br>",
    "<br></span>": "</span>",
    "\n<br>": "<br>",
    "<h2>MapTasker</h2>": '<a id="the_top"></a><h5>MapTasker</h5>',
    '<h2><span class="normtab"></span>Directory</h2>': '<h6><span class="normtab"></span>Directory</h6>',
}

# How long to wait for the browser to finish a view search (see search_event).  NiceGUI's
# own default is 1 second, which is a reasonable wait for a one-line snippet but far too
# short for the search crawl: it walks every text node of the rendered view, and a Map or
# Diagram of a large Tasker configuration is tens of thousands of lines.
SEARCH_JAVASCRIPT_TIMEOUT = 60.0


def _escape_html_text(text: str) -> str:
    """Escape plain text for safe embedding in HTML (the Diagram file has no markup of its own)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _connectors_by_line() -> dict[int, list[tuple[int, int, int]]]:
    """Invert PrimeItems.diagram_connectors (id -> ranges) into line_num -> (start, end, id)."""
    by_line: dict[int, list[tuple[int, int, int]]] = {}
    for connector_id, ranges in getattr(PrimeItems, "diagram_connectors", {}).items():
        for line_num, col_start, col_end in ranges:
            by_line.setdefault(line_num, []).append((col_start, col_end, connector_id))
    return by_line


def _diagram_spans(
    line_num: int,
    line: str,
    connectors_by_line: dict[int, list[tuple[int, int, int]]],
    nodes_by_line: dict[int, list[dict]],
) -> list[tuple[int, int, str]]:
    """Every span to wrap on this line, in column order and never overlapping.

    Two kinds of span want the same characters now: a connector's run of box-drawing
    characters, and an object's name.  A Task is drawn as "└─ Backup", and the "─" in that
    prefix is a connector character -- so a horizontal run passing close by can, rarely,
    grow into it.  An element cannot be in two spans at once, so the object name wins and
    the connector is clipped around it: losing a character off the end of a connector costs
    a click target that the rest of the same connector still offers, while losing one off a
    name costs the name its click target outright.
    """
    claimed = []
    for node in nodes_by_line.get(line_num, []):
        start, end = node["col"], node["col"] + node["len"]
        if start >= len(line) or end <= start:
            continue
        claimed.append(
            (
                start,
                min(end, len(line)),
                f'<span class="{diagintr.NODE_CLASS}" data-anchor="{node["anchor"]}" '
                f'data-node="{node["index"]}" data-kind="{node["kind"]}" tabindex="0">',
            ),
        )
    claimed.sort()

    spans = list(claimed)
    for col_start, col_end, connector_id in sorted(connectors_by_line.get(line_num, [])):
        start, end = max(col_start, 0), min(col_end, len(line))
        opening = f'<span class="connector" data-connector-id="{connector_id}">'
        # Split around every name this run touches, keeping the pieces that are still the
        # connector's own.  Almost always one piece, unchanged.
        for name_start, name_end, _ in claimed:
            if name_start >= end or name_end <= start:
                continue
            if start < name_start:
                spans.append((start, name_start, opening))
            start = max(start, name_end)
        if start < end:
            spans.append((start, end, opening))
    spans.sort()
    return spans


def _create_diagram_tools(view: NiceGuiTextView) -> None:
    """The Diagram view's own controls: zoom, folding, and a way back to a plain diagram.

    Everything here is a shortcut for something the diagram itself already offers -- a
    Project folds by clicking its top border, a chain lights up by shift-clicking a Task --
    with the exception of zoom, which has nowhere else to live.  They are on the toolbar
    because a diagram of forty Projects is a lot of borders to click, and because a control
    on screen is how anyone finds out that the diagram does this at all.

    The state label is the one thing here that is not a button: it is written to from the
    browser (see diagintr.report) rather than from Python, since every one of these actions
    happens in the page and never comes back.
    """
    ui.separator().props("vertical")
    with ui.row().classes("items-center gap-1"):
        zoom_out = ui.button(
            icon="zoom_out",
            on_click=lambda: view._diagram_command("zoom", 1 / 1.15),
        ).props(
            "flat dense",
        )
        with zoom_out:
            ui.tooltip(translate_string("Zoom out.  Ctrl/⌘ and the scroll wheel does the same."))
        zoom_in = ui.button(icon="zoom_in", on_click=lambda: view._diagram_command("zoom", 1.15)).props(
            "flat dense",
        )
        with zoom_in:
            ui.tooltip(translate_string("Zoom in.  Ctrl/⌘ and the scroll wheel does the same."))
        collapse = ui.button(
            icon="unfold_less",
            on_click=lambda: view._diagram_command("collapse-all"),
        ).props(
            "flat dense",
        )
        with collapse:
            ui.tooltip(
                translate_string(
                    "Collapse every Project down to its title bar.\n\n"
                    "One Project on its own collapses by clicking the top edge of its box.",
                ),
            ).style("white-space: pre-wrap")
        expand = ui.button(icon="unfold_more", on_click=lambda: view._diagram_command("expand-all")).props(
            "flat dense",
        )
        with expand:
            ui.tooltip(translate_string("Expand every collapsed Project."))
        reset = ui.button(icon="restart_alt", on_click=lambda: view._diagram_command("reset")).props(
            "flat dense",
        )
        with reset:
            ui.tooltip(translate_string("Back to the whole diagram: no zoom, nothing folded, nothing filtered."))
        # The one place the gestures are written down.  Everything the diagram does on a
        # click is discoverable by trying it, but only if you already suspect it is there.
        help_button = ui.button(icon="help_outline").props("flat dense")
        with help_button:
            ui.tooltip(
                translate_string(
                    "The diagram is clickable:\n\n"
                    "Click a Project, Profile, Task or Scene name to be taken to it in the Map.\n\n"
                    "Shift-click a Task to light up the whole chain of calls it takes part in -- "
                    "everything it calls, everything that calls it, and the arrows between them.\n\n"
                    "Right-click any name for the rest: collapse its Project, show only that "
                    "Project, follow its chain.\n\n"
                    "Click the ▾ beside a Project to collapse it, and the ▸ to bring it back.\n\n"
                    "Ctrl (or ⌘) and the scroll wheel zooms.  Esc clears a chain.",
                ),
            ).style("white-space: pre-wrap")
    view.diagram_state_label = ui.label("").classes("text-xs text-gray-400 italic ml-1")


def _wrap_diagram_line(
    line_num: int,
    line: str,
    connectors_by_line: dict[int, list[tuple[int, int, int]]],
    nodes_by_line: dict[int, list[dict]],
    folds_by_line: dict[int, str],
) -> str:
    """One Diagram line as its own element, with its connectors and its names inside it.

    A line is an element rather than a run of text between two newlines because the
    interactive view has to be able to take one away -- folding a Project hides its lines,
    and there is no way to hide a stretch of text that is not an element.

    The newline is inside the element and hidden with it, in a span of its own that is
    never displayed: the line elements are blocks, so the browser breaks between them
    anyway, and a newline that rendered as well would double-space the whole diagram.  It
    is still in the text, though, and that is deliberate -- the view's search index and the
    jump into the Diagram both count lines by counting newlines through the text nodes, and
    a document with none would leave both of them measuring one enormous line.  An
    otherwise empty line carries a zero-width space for the same kind of reason: an empty
    block has no height, and the blank lines in a diagram are the ones the connectors are
    drawn down.
    """
    pieces = []
    cursor = 0
    for start, end, opening in _diagram_spans(line_num, line, connectors_by_line, nodes_by_line):
        start = max(start, cursor)  # noqa: PLW2901
        if start >= end:
            continue
        if start > cursor:
            pieces.append(_escape_html_text(line[cursor:start]))
        pieces.append(f"{opening}{_escape_html_text(line[start:end])}</span>")
        cursor = end
    if cursor < len(line):
        pieces.append(_escape_html_text(line[cursor:]))
    if not pieces:
        pieces.append("&#8203;")

    fold = folds_by_line.get(line_num)
    fold_attribute = f' data-fold="{fold}" data-fold-state="open"' if fold else ""
    return (
        f'<span class="{diagintr.LINE_CLASS}" data-line="{line_num}"{fold_attribute}>'
        f'{"".join(pieces)}<span class="mt-dnl">\n</span></span>'
    )


# ##################################################################################
# The rendered-view registry
# ##################################################################################
def element_is_live(element: object) -> bool:
    """Whether a NiceGUI element can still be safely interacted with -- it hasn't
    been deleted, and the client (the browser page) it was built for is still
    around.

    Needed because this app keeps references to elements across events: the rendered
    Map/Diagram/Tree views outlive the event that built them, and anything reaching
    into one later (live re-colouring in handle_color_pick_event, un-highlighting in
    clear_event) is one step removed from whether that view still exists. Three things
    invalidate it -- "Clear" deletes the rendered view's elements (see clear_view_event),
    a browser reload replaces the client outright, and closing a popout tab takes its
    client with it -- and none of them clears the reference, so a plain truthiness check
    passes while the element underneath is dead. Using one then raises
    RuntimeError("The client this element belongs to has been deleted.") from inside
    NiceGUI's own element.client, which reaches the user as a console traceback rather
    than anything actionable.

    element.client raises rather than returning None once the client has been
    garbage-collected, so that access is what has to be guarded; is_deleted covers
    the other case, where the element itself was deleted but its client is still
    alive (exactly what "Clear" leaves behind).
    """
    if not element or getattr(element, "is_deleted", False):
        return False
    try:
        client = element.client
    except RuntimeError:
        return False
    return not getattr(client, "is_deleted", False)


def view_is_live(view: object) -> bool:
    """Whether a rendered view is still on a page we can safely touch."""
    if not view:
        return False
    # The text views hang everything off a scroll_area; the tree view off a tree.
    return element_is_live(getattr(view, "scroll_area", None) or getattr(view, "tree", None))


def register_view(master_gui: MyGui, view: object) -> None:
    """Record a freshly rendered view as the current one, and add it to the live set.

    `master_gui.textview` stays the most recent view, which is what the single-view
    callers want. `master_gui.textviews` additionally keeps every view still open, so
    that with "Open View In New Window" enabled -- where several Map/Diagram tabs can
    be on screen at once -- the handlers that reach back into a rendered view can
    reach all of them rather than only the newest.
    """
    master_gui.textviews = [*live_views(master_gui), view]
    master_gui.textview = view


def live_views(master_gui: MyGui) -> list:
    """Every rendered view still safe to touch, oldest first, pruning any that died."""
    views = [view for view in getattr(master_gui, "textviews", None) or [] if view_is_live(view)]
    master_gui.textviews = views
    return views


def scope_badge_text(built_for: str, now: str) -> tuple[str, str]:
    """What the toolbar badge says: (what this view was drawn for, what has changed since).

    The second half is "" when the two agree, which is what the view shows and hides the
    stale line and the Rebuild button by.  Both halves name the selection in the words the
    pulldowns use ("Project 'Home'", "Task 'Wake Up'"), and the whole configuration is said
    rather than left as a blank, because a badge reading "Drawn for" and then nothing looks
    like something failed to load.
    """
    everything = translate_string("the whole configuration")
    drawn = f"{translate_string('Drawn for')} {built_for or everything}"
    if (built_for or "") == (now or ""):
        return drawn, ""
    return drawn, f"-- {translate_string('now showing')} {now or everything}"


def refresh_scope_badges(master_gui: MyGui) -> None:
    """Tell every open view that the single-item selection has changed.

    Called from the one funnel a changed selection goes through (userintr.process_name_event),
    so a Diagram drawn for the old selection says so the moment the user picks a new one
    rather than the next time they happen to look at its toolbar.

    Touches text and visibility on elements that already exist, which is what makes it safe
    from a pulldown's handler in the MAIN window: those elements belong to the popout's
    client, and NiceGUI sends a property change to whichever client owns the element.
    Creating one there would be the problem -- see register_finding_clicks on what building
    into a live page costs.
    """
    for view in live_views(master_gui):
        try:
            view.refresh_scope_badge()
        except (AttributeError, RuntimeError):
            continue  # A view without a badge, or one whose page went away mid-update.


def forget_views(master_gui: MyGui) -> None:
    """Drop every rendered-view reference -- for when they've all just been deleted."""
    master_gui.textviews = []
    master_gui.textview = False


# Pages whose report rows are already wired to the jump handler.  Same guard, and for the
# same reason, as _CANVAS_EVENT_CLIENTS above: ui.on() subscribes for the page it is called
# from, and a second subscription would run every jump twice.
_FINDING_CLICK_CLIENTS: weakref.WeakSet = weakref.WeakSet()


def _bring_to_front(view: NiceGuiTextView) -> None:
    """Raise the window a jump has just landed in, so the user is looking at the answer.

    Only for a jump answered by a view that was ALREADY open.  The other path --
    rebuild_map_for_jump -- ends in window.open(), which raises the window it opens on its
    own; this is the case that had nothing doing it (see mapjump.bring_to_front_js).

    Not awaited.  The window is being raised for the user's benefit and nothing here
    depends on the outcome, so there is no reason to hold the jump open for a round trip --
    and a browser that declines to raise the window is not a failure to report.  The
    request is still sent: NiceGUI's run_javascript queues the message eagerly and only the
    response needs awaiting.

    A view whose page has gone away raises rather than answering, which is one more window
    that cannot be raised; the caller is already treating that as "not this one".
    """
    view.scroll_area.client.run_javascript(mapjump.bring_to_front_js())


async def jump_map_view(master_gui: MyGui, target: mapjump.Target) -> bool:
    """Scroll an open Map view to a Target and highlight it.  False if none could.

    Only a Map built for the Project this object needs is used.  Merely CONTAINING the
    object is not enough: a Map of the whole file contains everything, so without this a
    click would keep landing in whatever wide Map happened to be open and the user would
    never see the Map of one Project they asked for -- which is exactly what happened the
    first time this shipped.  Nothing is reused across scopes, so the Map on screen after a
    click is always the one that click would have built.

    Tries the most recently opened Map view first.  With "Open View In New Window" on,
    several can be up at once, showing different runs, and the one the user is most likely
    looking at is the last one they asked for.  Any that turns out not to hold this object
    is passed over rather than treated as a failure, so the answer is "no Map on screen has
    it", not "the first one I tried didn't".

    A view whose page has gone away between live_views() pruning it and this reaching it
    raises rather than answering; that is one more Map without the object, not an error to
    report.
    """
    wanted = mapjump.scope_for(target)
    for view in reversed(live_views(master_gui)):
        if not str(getattr(view, "title", "")).startswith("Map"):
            continue
        if getattr(view, "map_scope", "") != wanted:
            continue
        try:
            landed = await view.scroll_area.client.run_javascript(mapjump.jump_js(target.anchor), timeout=5)
            if landed:
                _bring_to_front(view)
        except (TimeoutError, RuntimeError, AttributeError):
            continue
        if landed:
            return True
    return False


def _report_view_failure(task: asyncio.Task) -> None:
    """Log whatever a view's rendering task raised, instead of losing it.

    Cancellation is ordinary -- a view whose page went away mid-render -- and says nothing.
    """
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("Rendering a view failed", exc_info=error)


async def jump_diagram_view(master_gui: MyGui, target: mapjump.Target) -> bool:
    """Scroll an open Diagram view to a Target and highlight it.  False if none could.

    The Diagram's counterpart to jump_map_view.  Where the Map is addressed by the anchor
    ids it carries, the Diagram is addressed by the line the object was drawn on, recorded
    while the diagram was built (see diagram.py's note above flatten_with_quotes) and
    looked up here.  That is what makes the jump land on THIS Task rather than on the first
    Task drawn with the same name, which is ordinary in Tasker.

    Falls back to matching the drawn text when there is no recorded line: a Diagram built
    before this version, or one whose file is on disk from an earlier run.  Weaker, and
    knowingly so -- it cannot tell two copies of a name apart -- but better than refusing
    to move.

    Most recently opened Diagram first, and any that turns out not to hold the object is
    passed over, exactly as jump_map_view treats its Maps: with "Open View In New Window"
    on, several can be up at once showing different runs.
    """
    placement = mapjump.diagram_placement(target)
    patterns = mapjump.diagram_patterns(target)
    anchor = mapjump.diagram_anchor(target)
    # Nothing to go on at all: an object the Diagram neither recorded nor draws a line for
    # -- an unnamed Task, a variable.  Answered here rather than with a match on something
    # else that happens to be nearby.  An anchor counts as something to go on: an
    # interactive Diagram carries one on every name it drew, including the unnamed Task's,
    # which is drawn under a derived name no pattern can reconstruct.
    if placement is None and not patterns and not anchor:
        return False
    for view in reversed(live_views(master_gui)):
        if not str(getattr(view, "title", "")).startswith("Diagram"):
            continue
        try:
            landed = await view.scroll_area.client.run_javascript(
                mapjump.diagram_jump_js(
                    f"c{view.scroll_area.id}",
                    patterns,
                    placement,
                    anchor,
                ),
                timeout=5,
            )
            if landed:
                _bring_to_front(view)
        except (TimeoutError, RuntimeError, AttributeError):
            continue
        if landed:
            return True
    return False


async def go_to_target(master_gui: MyGui, target: mapjump.Target, prefer_diagram: bool = False) -> None:
    """Take one clicked row -- a report finding, or a Find result -- to what it points at.

    The whole of what a click does, in one place, because there are now two things that
    emit one: the reports' clickable rows (see register_finding_clicks) and the Find
    results list, which is a NiceGUI dialog and reaches this directly rather than through
    the browser.

    prefer_diagram is set by a Find run from a Diagram view, where the user is looking at
    the Diagram and expects the answer to appear in it.  It is a preference and not a
    demand: a Diagram that does not hold the object -- or an object the Diagram draws no
    line for at all -- falls through to the Map, which can always be built to show it.
    """
    # A report, and a set of results, are both snapshots.  The object named can have been
    # renamed or deleted in the editor since, so say so rather than scrolling to nothing.
    if not mapjump.exists(target):
        ui.notify(
            f"{target.label} {translate_string('is no longer in the loaded configuration.')}",
            type="warning",
            position="top",
        )
        return

    if prefer_diagram and await jump_diagram_view(master_gui, target):
        return
    if await jump_map_view(master_gui, target):
        return

    # Nothing on screen can show it.  Whether that is because no Map is open, because the
    # one that is covers a single Project, or because its detail level leaves the Tasks and
    # actions out is not worth telling apart here -- the answer to all three is the same
    # Map, so build it (see rebuild_map_for_jump, which says what it is doing and why).
    handlers = getattr(master_gui, "event_handlers", None)
    if handlers is None:
        ui.notify(
            translate_string("No Map view is open.  Run Map View, then click this again."),
            type="warning",
            position="top",
        )
        return
    await handlers.rebuild_map_for_jump(target)


def register_finding_clicks(master_gui: MyGui) -> None:
    """Subscribe this page's report-jump event, once, while the layout is still being built.

    Called from initialize_screen for exactly the reason _register_canvas_events is, and it
    is the whole reason clicking a finding did nothing at first: ui.on adds its listener to
    client.layout, and adding one to an element the browser already has makes NiceGUI
    re-render that element and everything under it.  Registering this from the report view's
    own background task -- later than any dialog -- meant the re-render tore out the click
    listener enable_finding_clicks had just installed on the report's container, so the
    spans were there, styled and focusable, and a click reached nothing at all.

    A report view still calls this itself, so a page built without going through
    initialize_screen is not left without the plumbing; the guard makes that call a no-op.
    """
    client = context.client
    if client in _FINDING_CLICK_CLIENTS:
        return
    _FINDING_CLICK_CLIENTS.add(client)

    async def jump(event: Event) -> None:
        """Take one clicked report row to where it points."""
        target = mapjump.Target.from_token(str((event.args or {}).get("target", "")))
        if target is not None:
            await go_to_target(master_gui, target)

    ui.on("mt_jump", jump)


def enable_finding_clicks(view: NiceGuiTextView) -> None:
    """Install the browser-side click listener for one rendered report.

    DOM work only.  The Python subscription that acts on what this emits is registered at
    page build time instead -- see register_finding_clicks for why it cannot be done from
    here.  The call below is the no-op guard for a page that never went through
    initialize_screen; on the main window it has already happened.
    """
    # Everything here needs an active NiceGUI slot, and this runs from process_data's
    # background task, where there is none: the slot stack is per-task and empty, so
    # ui.run_javascript cannot tell which client to target and context.client -- which
    # register_finding_clicks reads -- raises outright.  Re-entering the scroll area
    # restores both, the same way _enable_connector_highlighting does.
    with view.scroll_area:
        register_finding_clicks(view.master_gui)
        ui.run_javascript(mapjump.click_wiring_js(f"c{view.scroll_area.id}"))


def search_jump_js(target_id: str) -> str:
    """JavaScript that takes a view to one clicked search result and marks it as the current one.

    Lifted out of the results dialog that builds it (see _report_search_results) so that
    what it does can be stated in one place and tested.  A search hit is not an object in
    the configuration -- it is a run of characters on a line -- which is why this lives here
    rather than beside mapjump's jumps to Projects, Profiles, Tasks and Scenes.

    Instant, not smooth, exactly as those are: a match can be forty thousand pixels from
    where the reader is, and an animated scroll over that distance is slow to land and
    distracting rather than helpful.  Landing at the top of the view rather than the middle
    is this one's own choice and deliberate -- a search result is read forwards from the
    line that matched.
    """
    return f"""
{mapjump.REVEAL_ANCESTORS_JS}
        // Restore any previously-clicked match back to the standard highlight color before
        // marking the newly-clicked one, so only the match the user just jumped to stands out.
        document.querySelectorAll('.search-highlight-active').forEach(el => {{
            el.classList.remove('search-highlight-active');
            el.style.backgroundColor = '#ffd941';
            el.style.color = '#000000';
        }});
        const el = document.getElementById("{target_id}");
        if (el) {{
            // As in the Diagram connector jump buttons: a chunk skipped by
            // content-visibility: auto was never laid out, so scrollIntoView() on a
            // descendant of it lands in the wrong place until it's forced to render.
            mtRevealAncestors(el);
            el.classList.add('search-highlight-active');
            el.style.backgroundColor = '#ff5722';
            el.style.color = '#ffffff';
            el.scrollIntoView({{ behavior: 'auto', block: 'start' }});
        }}
    """


def resolve_dark_mode(appearance_mode: str | None) -> bool:
    """Whether the saved appearance mode means "dark" -- "system" asks the OS, as colrmode does."""
    if appearance_mode == "system":
        import darkdetect  # noqa: PLC0415  Only needed on this path, and it is a slow import

        return bool(darkdetect.isDark())
    return appearance_mode == "dark"


def apply_appearance_mode(self: MyGui, is_dark: bool) -> None:
    """Put the whole window into dark or light mode and remember which it is now in.

    Called both by the "Dark Mode" switch and, on start-up, by restore_appearance_mode() with
    whatever the saved settings hold -- the reason this is a function of its own rather than
    the switch's handler: the widgets below are coloured by inline style, so nothing short of
    running this puts a restored mode on the screen.
    """
    self.dm_controller.enable() if is_dark else self.dm_controller.disable()

    # --- 1. Resolve theme colors from a single source of truth ---
    bg = "#1e293b" if is_dark else "#ffffff"
    drawer_bg = "#1f2937" if is_dark else "#ffffff"
    fg = "#ffffff" if is_dark else "#000000"

    # --- 2. Persist state on self ---
    # appearance_mode is what gets written to the settings file (it is in ARGUMENT_NAMES),
    # so setting it here is what makes the choice outlive the session.
    self.appearance_mode = "dark" if is_dark else "light"
    self.dark_mode = is_dark
    self.saved_background_color = bg
    # A settings restore carries its own colors and is mid-way through applying them, so leave
    # them alone -- extract_settings() raises this flag for exactly this reason.
    if not getattr(self, "extract_in_progress", False):
        self.color_lookup = set_color_mode(self.appearance_mode)
    bg = (self.color_lookup or {}).get("background", bg)

    # --- 3. Push background color to the browser body ---
    ui.run_javascript(f"document.body.style.backgroundColor = '{bg}';")

    # --- 4. Apply styles to every named widget that exists ---
    for attr in ("gui_left_drawer", "gui_right_drawer"):
        widget = getattr(self, attr, None)
        if widget:
            widget.style(f"background-color: {drawer_bg} !important; color: {fg} !important;")

    for attr in (
        "gui_main_column",
        "gui_tab_panel",
        "gui_tab_panels",
        "gui_main_tabs_container",
        "gui_color_panel",
        "gui_ai_panel",
        "gui_debug_panel",
        "gui_tasker_object_panel",
        "content_container",
    ):
        widget = getattr(self, attr, None)
        if widget:
            widget.style(f"background-color: {bg} !important; color: {fg} !important;")

    # --- 5. CRITICAL FIX: Force the text view's gui_toolbar color update ---
    # Every open view, not just the newest: "Open View In New Window" can leave
    # several Map/Diagram tabs on screen, and they all have to follow the theme.
    for textview in live_views(self):
        # The Tree view colours its whole container itself (card included) rather than
        # leaving it to the stylesheet -- see NiceGuiTreeView.apply_theme.
        apply_theme = getattr(textview, "apply_theme", None)
        if apply_theme:
            apply_theme(bg, fg)
        scroll_area = getattr(textview, "scroll_area", None)
        if scroll_area and not apply_theme:
            scroll_area.style(f"background-color: {bg} !important;")

        # Map / Diagram / Tree View >  Search / Clear / Top / Bottom Toolbar
        tv_toolbar = getattr(textview, "gui_toolbar", None)
        if tv_toolbar:
            if is_dark:
                tv_toolbar.style("background-color: #1f2937 !important; color: #ffffff !important;")
            else:
                tv_toolbar.style("background-color: #00ffff !important; color: #000000 !important;")

    # --- 6. CRITICAL FIX: Force the main body gui_view_toolbar color update (Current File: backup.xml ...---
    view_toolbar = getattr(self, "gui_view_toolbar", None)
    if view_toolbar:
        if is_dark:
            view_toolbar.style("background-color: #1e293b !important; color: #ffffff !important;")
        else:
            view_toolbar.style("background-color: #00ffff !important; color: #000000 !important;")


def restore_appearance_mode(self: MyGui, appearance_mode: str | None) -> str:
    """Put the window into the appearance mode a restored settings file asks for.

    Runs from restore_display() during start-up, after initialize_screen() has already built
    the window at STARTUP_DARK_MODE.  Moves the switch to match and repaints, so the saved
    choice survives the session rather than being a setting that is written but never read.
    """
    is_dark = resolve_dark_mode(appearance_mode)
    switch = getattr(self, "dark_mode_switch", None)
    if switch is not None:
        # Assigning an unchanged value fires no on_change, so paint by hand rather than
        # relying on the switch to do it -- restoring "light" over a light start-up must
        # still colour the window, since nothing else has yet.
        switch.value = is_dark
    apply_appearance_mode(self, is_dark)
    return f"{translate_string('Appearance Mode')} {translate_string('set to')} {self.appearance_mode}\n"


def view_theme_colors(master_gui: MyGui) -> tuple[str, str]:
    """The (background, foreground) a view should paint itself with right now.

    Same pair the dark-mode toggle hands to the drawers, panels and text views, so a view
    that has to colour itself at build time -- the toggle's on_change only fires when the
    switch is actually clicked -- lands on exactly what the rest of the window is using.
    Defaults to light when the switch has never been touched, which is the state the page
    starts in (ui.dark_mode() mounts disabled regardless of the switch's initial value).
    """
    is_dark = bool(getattr(master_gui, "dark_mode", False))
    bg = "#1e293b" if is_dark else "#ffffff"
    fg = "#ffffff" if is_dark else "#000000"
    return (getattr(master_gui, "color_lookup", None) or {}).get("background", bg), fg


class NiceGuiTreeView:
    """Replaces CTkTreeview. Renders a hierarchical tree representation in the main view column."""

    def __init__(self, master_gui: MyGui, title: str, items: list) -> None:
        """Initialize the Tree view with a title and hierarchical items."""
        self.master_gui = master_gui
        self.title = title
        self.build_ui(items)
        register_view(master_gui, self)

    def build_ui(self, items: list) -> None:
        """Build the base UI layout for the Tree view inside the main content container slot."""

        # 1. Target and clear the dedicated full-width main view column slot
        if hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()  # Fallback context if called standalone

        # 2. Render the layout inside the main application body container
        with container_context:
            self.card = ui.card().classes(
                "maptasker-tree-card w-full max-w-full mx-auto p-6 shadow-md border-2 border-gray-300",
            )
            with self.card:
                # Header row with title and navigation hints
                with ui.row().classes("items-center justify-between w-full border-b pb-3 mb-4"):
                    ui.label(f"{self.title}").classes("text-orange-500 font-bold text-lg")
                    ui.label(translate_string("Click arrows to expand/collapse details.")).classes(
                        "text-xs text-gray-500 italic",
                    )

                # Convert MapTasker nested dictionary list nodes to NiceGUI tree notation
                tree_data = self._format_data(items)

                # 3. Create a scrollable window container for large tree structures
                self.scroll_area = ui.scroll_area().classes("w-full h-[65vh] p-2")
                with self.scroll_area:
                    # Render the native responsive Tree component
                    # Injected custom fonts to preserve monospace formatting matches
                    self.tree = (
                        ui
                        .tree(tree_data, label_key="label", children_key="children", tick_strategy="none")
                        .classes("w-full text-base")
                        .style(f"font-family: '{self.master_gui.font}', monospace;")
                    )

        self.apply_theme(*view_theme_colors(self.master_gui))

    def apply_theme(self, bg: str, fg: str) -> None:
        """Paint this view's card and scroll area for the mode the window is currently in.

        Unlike the Map/Diagram views -- whose scroll area the dark-mode toggle restyles by
        hand -- the Tree view's container used to carry no colours of its own, leaving it to
        whichever stylesheet rule won the cascade for .q-card / .q-scrollarea. That is a
        fragile thing to depend on across browsers and NiceGUI/Quasar releases (it is what
        left this one container white in dark mode), so state the colours outright instead.
        "!important" for the same reason the Map view's background needs it: it has to beat
        the equally-important light/dark overrides injected by inject_shared_head_styles().
        The node labels follow along through the .maptasker-tree-card rule in that same
        stylesheet, which hands them this card's colour instead of Quasar's theme colour.
        """
        style = f"background-color: {bg} !important; color: {fg} !important;"
        self.card.style(style)
        self.scroll_area.style(style)

    def _format_data(self, items: list, parent_id: str = "node") -> list:
        """Converts MapTasker lists/dicts into NiceGUI's strict dict format,

        replacing HTML non-breaking spaces (&nbsp;) with standard spaces
        and cleaning raw arrow entities (&#11013;) into clear symbols.
        """
        formatted_nodes = []
        for i, item in enumerate(items):
            current_id = f"{parent_id}_{i}"
            if isinstance(item, dict):
                # Extract the name and clean out the raw HTML markup fragments
                raw_name = item.get("name", "Unnamed")
                clean_name = (
                    raw_name
                    .replace("&nbsp;", " ")
                    .replace("&#9940;", "⛔")
                    .replace("&#11013;", "⬅️")
                    .replace("&#11157;", "➡️")
                    .ljust(50)
                )

                node = {"id": current_id, "label": clean_name}
                if item.get("children"):
                    node["children"] = self._format_data(item["children"], current_id)
                formatted_nodes.append(node)
            else:
                # Handle raw string line items (like nested Task Actions or standalone strings)
                clean_string = (
                    str(item)
                    .replace("&nbsp;", " ")
                    .replace("&#9940;", "⛔")
                    .replace("&#11013;", "⬅️")
                    .replace("&#11157;", "➡️")
                )
                formatted_nodes.append({"id": current_id, "label": clean_string})
        return formatted_nodes


class NiceGuiSceneView:
    """Draws a Scene as a picture in the main content column -- what the Preview button on
    the Add/Edit Scene dialogs opens.  The drawing itself is sceneview.py; this is the frame
    round it: the toolbar, the scaling, and the way back to the dialog.

    THE DIALOG HAS TO GET OUT OF THE WAY.  content_container sits behind a modal overlay, so
    a preview drawn while the Scene dialog is up would be invisible underneath it.  The
    dialog is therefore closed before this is built and re-opened by this view's own "Back to
    Editor" button.  Closing a NiceGUI dialog only hides it -- its widgets are not destroyed
    -- so every field the user has typed into and not yet saved is still there when they go
    back, which is the entire reason it is closed rather than cancelled.

    That is also why this takes field_refs rather than reading the Scene: the preview shows
    what is currently *typed into* the dialog, not what was last saved.  For a Legacy Scene
    that is the four size fields, so previewing is a way to try a canvas size out; for a
    Version 2 Scene it is the live layout dict the designer edits in place (field_refs
    ["v2_layout"]), so previewing shows components added, moved and retyped a moment ago.
    A Legacy size that isn't a whole number is reported and the saved one used, matching what
    userintr._apply_scene_field_values would say about it at save time rather than inventing a
    second opinion.

    THE PICTURE IS ALSO AN EDITING SURFACE, for both kinds of Scene, whenever the designer
    that opened it is still alive: components are dragged into a new order here (V2) and
    elements are selected, moved and resized here (Legacy).  It edits nothing itself.  Every
    gesture is handed straight to that designer's own closures -- see _v2_from_canvas and
    _legacy_from_canvas -- so an edit made in the picture goes on the same undo stack, and
    through the same code, as the identical edit made in the dialog.  A second implementation
    of "move an element" living here is exactly what this arrangement exists to avoid.

    THE TWO KINDS OF SCENE NEED DIFFERENT CONTROLS, so the toolbar is built per kind rather
    than shown-and-disabled.  A Legacy Scene needs a text density (its canvas size is its own)
    and a Landscape toggle that is meaningless unless it has a second layout; a V2 Scene needs
    a screen size (it has no size at all) and a Landscape toggle that always means something,
    and has no use for a density because dp is already density-independent.  Offering all four
    to both would mean two controls that do nothing on whichever Scene is open.

    Registered with register_view like the Map/Diagram/Tree views, so Clear View disposes of
    it and the dark-mode toggle repaints it.  The canvas itself deliberately does NOT follow
    dark mode: it is painted with the Scene's own background colour (Legacy) or the Material
    palette (V2), and letting this app's appearance change what the Scene appears to look like
    would defeat the point of it.
    """

    # The zoom pulldown.  "Fit" is not a number because the width it has to fit is the
    # browser's, which only the browser knows -- see _apply_scale.
    ZOOM_CHOICES = ("Fit", "25%", "50%", "75%", "100%", "150%", "200%")

    def __init__(
        self,
        master_gui: MyGui,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        dialog: ui.dialog | None = None,
    ) -> None:
        """Build the preview and draw it."""
        self.master_gui = master_gui
        self.edited_scene = edited_scene
        self.field_refs = field_refs
        self.dialog = dialog
        self.title = f"{translate_string('Scene Preview')}: {edited_scene.scene_name}"
        self.is_v2 = sceneedit.is_v2_scene(edited_scene.scene_element)
        self.options = sceneview.PreviewOptions()
        self.zoom = "Fit"
        self.screen = sceneview.V2_DEFAULT_SCREEN
        _register_canvas_events()
        self.build_ui()
        self.render()
        register_view(master_gui, self)

    # ---------- layout ----------
    def build_ui(self) -> None:
        """Toolbar, then the scroll area the canvas is drawn into."""
        if hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()

        with container_context:
            self.card = ui.card().classes("w-full max-w-full mx-auto p-4 shadow-md border-2 border-gray-300")
            with self.card:
                with ui.row().classes("w-full items-center gap-2 flex-wrap") as self.gui_toolbar:
                    ui.label(self.title).classes("text-orange-500 font-bold mr-2")
                    if self.dialog is not None:
                        ui.button(
                            translate_string("Back to Editor"),
                            icon="arrow_back",
                            on_click=self._back_to_editor,
                        ).classes("bg-blue-600")
                    ui.button(translate_string("Refresh"), icon="refresh", on_click=self.render).classes("bg-blue-600")
                    ui.separator().props("vertical")

                    self._build_orientation_control()

                    ui.select(
                        list(self.ZOOM_CHOICES),
                        value=self.zoom,
                        label=translate_string("Zoom"),
                        on_change=self._zoom_selected,
                    ).props("dense").classes("w-28")

                    if self.is_v2:
                        self._build_screen_control()
                    else:
                        self._build_density_control()
                        self._build_snap_control()

                    ui.switch(
                        translate_string("Bounds"),
                        value=self.options.show_bounds,
                        on_change=lambda event: self._set_option("show_bounds", bool(event.value)),
                    ).props("dense").tooltip(
                        (
                            translate_string(
                                "Outline every component and name it, the way the designer's tree names it.",
                            )
                            if self.is_v2
                            else translate_string("Outline every element and name it.")
                        ),
                    )
                    ui.switch(
                        translate_string("Actions") if self.is_v2 else translate_string("Tasks"),
                        value=self.options.show_tasks,
                        on_change=lambda event: self._set_option("show_tasks", bool(event.value)),
                    ).props("dense").tooltip(
                        (
                            translate_string("Show what each component does when tapped, and what it writes to.")
                            if self.is_v2
                            else translate_string("Show the Task each element runs.")
                        ),
                    )

                self.scroll_area = ui.scroll_area().classes("w-full h-[70vh] p-2")
                with self.scroll_area:
                    # Two nested elements on purpose: the outer one is what the fit
                    # calculation measures and what reserves the scaled height in the page's
                    # flow, the inner one is the true-size canvas that gets transformed. A
                    # transform does not affect layout, so without the outer element the page
                    # would reserve room for the canvas at full size however far it is
                    # scaled down.
                    self.canvas_wrap = (
                        ui
                        .element("div")
                        .classes(f"mt-scene-wrap {CANVAS_PREVIEW_ROOT}")
                        .style(
                            "position: relative; width: 100%; overflow: hidden;",
                        )
                    )
                self.caption = ui.column().classes("w-full gap-0 mt-2")

        self.apply_theme(*view_theme_colors(self.master_gui))

    def _build_orientation_control(self) -> None:
        """The Landscape toggle, which means two different things.

        For a Legacy Scene it selects the Scene's *second stored layout* -- the landscape half
        of every <geom> -- and most Scenes do not have one, so it is disabled and says why.
        For a V2 Scene there is no second layout to select: it turns the frame on its side and
        lets the tree re-flow into it, which is exactly what the Scene would do on a phone, so
        it is always available.
        """
        if self.is_v2:
            ui.switch(
                translate_string("Landscape"),
                value=False,
                on_change=lambda event: self._set_option("landscape", bool(event.value)),
            ).props("dense").tooltip(
                translate_string("Turn the screen on its side and let the layout re-flow into it."),
            )
            return

        has_landscape = sceneview.has_landscape_layout(self.edited_scene.scene_element)
        landscape_switch = ui.switch(
            translate_string("Landscape"),
            value=False,
            on_change=lambda event: self._set_option("landscape", bool(event.value)),
        ).props("dense")
        landscape_switch.set_enabled(has_landscape)
        if not has_landscape:
            with landscape_switch:
                ui.tooltip(translate_string("This Scene has no landscape layout of its own (its size is -1)."))

    def _build_density_control(self) -> None:
        """Legacy only: the sp-to-pixel number that is not in the backup file."""
        density_select = (
            ui
            .select(
                list(sceneview.DENSITY_CHOICES),
                value=str(sceneview.DEFAULT_DENSITY),
                label=translate_string("Text density"),
                on_change=self._density_selected,
            )
            .props("dense")
            .classes("w-32")
        )
        with density_select:
            ui.tooltip(
                translate_string(
                    "A Scene's element positions are stored in device pixels, but its text sizes "
                    "are stored in Android's sp units. The number that converts between the two is "
                    "a property of the phone the Scene is shown on, and is not in the backup file.\n\n"
                    "So it is set here. Raise it if the text looks too small for its elements, "
                    "lower it if the text overflows them.",
                ),
            ).style("white-space: pre-wrap")

    def _build_snap_control(self) -> None:
        """Legacy, and only when this Preview is an editing surface: the grid a dragged
        element's position rounds to.

        Built at all only when there is a designer behind this picture, because without one
        there is nothing to drag and a Snap control would be a setting for a gesture the
        Preview does not offer.  It writes the designer's own dict rather than keeping a
        number of its own, so the two canvases cannot end up snapping to different grids --
        the same sharing that puts one selection on both of them.
        """
        editor = self.field_refs.get("legacy_edit")
        if not isinstance(editor, dict):
            return
        ui.select(
            [1, 2, 5, 10],
            value=int(editor["snap"]["grid"]),
            label=translate_string("Snap"),
            on_change=self._snap_selected,
        ).props("dense").classes("w-24").tooltip(
            translate_string("Round dragged positions and sizes to this many pixels."),
        )

    def _snap_selected(self, event: Event) -> None:
        editor = self.field_refs.get("legacy_edit")
        if isinstance(editor, dict):
            editor["snap"]["grid"] = int(event.value or 1)
        self.render()

    def _build_screen_control(self) -> None:
        """Version 2 only: which screen to lay the component tree out in.

        The nearest thing V2 has to the Legacy canvas size, except that it is not a property
        of the Scene at all -- it is the question the Scene answers differently on every
        device, which is why it is a control and not a number in the file.
        """
        screen_select = (
            ui
            .select(
                [name for name, _width, _height in sceneview.V2_SCREENS],
                value=self.screen,
                label=translate_string("Screen"),
                on_change=self._screen_selected,
            )
            .props("dense")
            .classes("w-36")
        )
        with screen_select:
            ui.tooltip(
                translate_string(
                    "A Version 2 Scene has no size of its own -- it lays itself out inside whatever "
                    "screen it is shown on, so there is nothing in the backup file to draw it at.\n\n"
                    "Change this to see the layout re-flow. A Flow Row wraps differently, and any "
                    "'Show when' written against %sv2_render_width is asking about exactly this.",
                ),
            ).style("white-space: pre-wrap")

    def apply_theme(self, bg: str, fg: str) -> None:
        """Paint the card and scroll area for the window's current mode.  The canvas inside
        keeps the Scene's own colours -- see this class's docstring.
        """
        style = f"background-color: {bg} !important; color: {fg} !important;"
        self.card.style(style)
        self.scroll_area.style(style)

    # ---------- toolbar handlers ----------
    def _back_to_editor(self) -> None:
        """Re-open the Scene dialog this preview was launched from, with everything still
        typed into it (see this class's docstring).
        """
        if self.dialog is None:
            return
        _resume_scene_editor_session(self.master_gui, self.dialog)
        self.dialog.open()
        # Re-render whichever designer is behind this preview, which re-installs the pointer
        # handlers on its surface -- the V2 designer's tree, the Legacy designer's canvas.
        #
        # A hidden Quasar dialog does not merely hide its contents, it takes them out of the
        # document, and re-opening it puts back new elements rather than the same ones -- so
        # the handlers installed on the old pane went with it.  Everything else about the
        # designer survives, which is exactly what makes this worth doing here instead of
        # leaving the pane to look right and answer nothing until whatever the user clicked
        # next happened to re-render it.
        #
        # A Scene is one kind or the other, so only one of these two is ever present.
        for key in ("v2_edit", "legacy_edit"):
            editor = self.field_refs.get(key)
            if isinstance(editor, dict):
                editor["rerender"]()

    def _set_option(self, name: str, value: object) -> None:
        setattr(self.options, name, value)
        if name == "landscape" and not self.is_v2:
            # ONE ORIENTATION, TWO SURFACES.  A drag in this picture is applied by the
            # designer's handlers, and they write whichever half of <geom> the designer's own
            # orientation names -- so a Preview showing landscape while the designer sat in
            # portrait would take a landscape drag and rewrite the portrait layout with it,
            # silently, with the evidence on the other toggle.  Moving them together is also
            # the better behaviour on its own terms: going Back to Editor lands on the
            # orientation the user was just looking at.
            editor = self.field_refs.get("legacy_edit")
            if isinstance(editor, dict):
                editor["orientation"]["landscape"] = bool(value)
        self.render()

    def _zoom_selected(self, event: Event) -> None:
        self.zoom = str(event.value or "Fit")
        self.render()

    def _density_selected(self, event: Event) -> None:
        try:
            self.options.density = float(event.value)
        except (TypeError, ValueError):
            self.options.density = sceneview.DEFAULT_DENSITY
        self.render()

    def _screen_selected(self, event: Event) -> None:
        self.screen = str(event.value or sceneview.V2_DEFAULT_SCREEN)
        self.render()

    # ---------- drawing ----------
    def render(self) -> None:
        """Draw (or re-draw) from the dialog's current state.  Every toolbar control lands
        here rather than trying to patch the drawing in place: it is a few hundred divs,
        rebuilding is cheap, and a partial update would be a second code path that could
        disagree with the first.
        """
        self.canvas_wrap.clear()
        self.caption.clear()
        self._render_v2() if self.is_v2 else self._render_legacy()

    def _render_legacy(self) -> None:
        """A Legacy Scene: its own pixel canvas, at the size the dialog currently holds."""
        scene_element = self.edited_scene.scene_element
        dimensions = self._dimensions()
        if dimensions is None:
            orientation = "landscape" if self.options.landscape else "portrait"
            self._say(
                f"This Scene has no {orientation} layout: its size is -1, which is Tasker's "
                "'this orientation has no layout of its own'.",
                "text-orange-600",
            )
            return

        width, height = dimensions
        editing = self._legacy_editing()
        with self.canvas_wrap:
            sceneview.draw_scene(scene_element, width, height, self.options, editing=editing)
        self._apply_scale(width, height)
        if editing is not None:
            _ACTIVE_CANVASES[CANVAS_PREVIEW_ROOT] = {
                name: (lambda payload, which=name: self._legacy_from_canvas(which, payload))
                for name in ("select", "geometry", "nudge")
            }
            _emit_canvas_editing(CANVAS_PREVIEW_ROOT, editing.snap)
        self._draw_legacy_caption(scene_element, width, height)

    def _legacy_editing(self) -> sceneview.CanvasEditing | None:
        """The Preview as the Legacy designer's second canvas, or None for the picture it has
        always been.

        Editing needs the designer to still be there -- and for a different reason than the
        Version 2 half of this class needs it.  There, a Preview opened where no designer was
        built draws a layout dict decoded for this view alone, so a drag on it would look like
        it worked and quietly lose the change.  Here the Preview draws
        edited_scene.scene_element, the very element the dialog saves, so a drag WOULD stick.
        It would stick with no snapshot taken and no designer panes to agree with it: a move
        that really did change the Scene and that Undo cannot take back, which is the worse of
        the two failures rather than the milder one.
        """
        editor = self.field_refs.get("legacy_edit")
        if not isinstance(editor, dict):
            return None
        return sceneview.CanvasEditing(
            selected=tuple(editor["selection"]["srs"]),
            snap=int(editor["snap"]["grid"]),
            # Kept here, unlike on the designer's canvas: the dialog holding the Inspector
            # that made them redundant there is closed while this is up, so the tooltip is
            # the only place an element's variables and Tasks can be read.  The caption below
            # promises exactly that, and this is what keeps the promise.
            tooltips=True,
        )

    def _legacy_from_canvas(self, name: str, payload: object) -> None:
        """A click, a drag or a nudge on the picture: hand it to the designer, then redraw.

        The designer's own handlers do the work -- see the note on field_refs["legacy_edit"]
        -- so an element moved in the Preview is snapshotted, written, selected and re-listed
        by exactly the code the designer's own canvas goes through.  All that is left here is
        the half the designer cannot do, which is repainting this picture.
        """
        editor = self.field_refs.get("legacy_edit")
        if not isinstance(editor, dict):
            return
        handler = editor["handlers"].get(name)
        if handler is None:
            return
        handler(payload)
        self.render()

    def _render_v2(self) -> None:
        """A Version 2 Scene: the component tree, laid out in the chosen screen.

        The layout comes from field_refs first -- that is the dict the designer edits in
        place, so a component added or retyped in the dialog a moment ago is in the picture
        without having been saved.  Decoding the Scene is the fallback for a preview opened
        from somewhere that never built a designer.
        """
        layout = self.field_refs.get("v2_layout")
        if not isinstance(layout, dict):
            layout = sceneedit.decode_v2_layout(self.edited_scene.scene_element)
        if not isinstance(layout, dict):
            self._say(
                "This Scene's Version 2 layout could not be read, so there is nothing to draw.",
                "text-orange-600",
            )
            return

        editing = self._v2_editing()
        width, height = self._screen_size()
        with self.canvas_wrap:
            sceneview.draw_v2_layout(layout, width, height, self.options, editing=editing)
        self._apply_scale(width, height)
        # After the scale, never before: the hull is measured in screen pixels and divided
        # back by the factor _apply_scale leaves on the wrapper, and a hull measured before
        # that factor existed would be sized by whatever the last render happened to set.
        _emit_v2_hull(CANVAS_PREVIEW_ROOT, width, height)
        if editing is not None:
            _ACTIVE_CANVASES[CANVAS_PREVIEW_ROOT] = {
                "v2select": lambda payload: self._v2_from_canvas("v2select", payload),
                "v2reorder": lambda payload: self._v2_from_canvas("v2reorder", payload),
            }
            _emit_v2_dragging(
                CANVAS_PREVIEW_ROOT,
                f".{CANVAS_PREVIEW_ROOT} .mt-scene-canvas",
                "mt-v2-node",
            )
        self._draw_v2_caption(layout, width, height)

    def _v2_editing(self) -> sceneview.V2Editing | None:
        """The Preview as a reorder surface, or None for the picture it has always been.

        Editing needs two things at once, and the absence of either is what makes this a
        read-only preview: the layout being drawn has to be the *live* one the designer edits
        in place, and the designer has to still be there to take the edit -- it owns the undo
        stack a drag has to land on, and the tree that has to agree with the picture
        afterwards.  A Preview opened where no designer was built draws a dict decoded for
        this view alone, which nothing would ever save; a drag on that would look like it
        worked and quietly lose the change.
        """
        editor = self.field_refs.get("v2_edit")
        if not isinstance(editor, dict) or self.field_refs.get("v2_layout") is None:
            return None
        selection = editor["selection"]
        return sceneview.V2Editing(selected=sceneedit.v2_run_paths(selection["path"], selection["count"]))

    def _v2_from_canvas(self, name: str, payload: object) -> None:
        """A click or a drop on the picture: hand it to the designer, then redraw.

        The designer's own handlers do the work -- see the note on field_refs["v2_edit"] --
        so a component dragged in the Preview is snapshotted, moved, selected and re-rendered
        in the tree by exactly the code the tree's own drag goes through.  All that is left
        here is the half the designer cannot do, which is repainting this picture.
        """
        editor = self.field_refs.get("v2_edit")
        if not isinstance(editor, dict):
            return
        handler = editor["handlers"].get(name)
        if handler is None:
            return
        handler(payload)
        self.render()

    def _screen_size(self) -> tuple[int, int]:
        """The frame a V2 layout is drawn in: the chosen screen, on its side when Landscape
        is on -- which for V2 is the whole of what the toggle does, there being no second
        stored layout to switch to.
        """
        for name, width, height in sceneview.V2_SCREENS:
            if name == self.screen:
                return (height, width) if self.options.landscape else (width, height)
        _name, width, height = sceneview.V2_SCREENS[0]
        return (height, width) if self.options.landscape else (width, height)

    def _dimensions(self) -> tuple[int, int] | None:
        """The canvas size to draw at -- the same answer the designer draws at, from the same
        function, so a Scene never previews at one size and edits at another.
        """
        return _legacy_canvas_size(self.edited_scene, self.field_refs, self.options.landscape)

    def _apply_scale(self, width: int, height: int) -> None:
        """Fit the true-size canvas into the space available.

        One transform on the whole canvas, rather than scaling each element's coordinates as
        it is drawn: the DOM then holds the same numbers the XML does, so a misplaced element
        here is a misplaced element in the Scene.  Scoped to this view's own wrapper class,
        because the Legacy designer has a canvas of its own on the same page.
        """
        fixed = "null"
        if self.zoom != "Fit":
            try:
                fixed = str(int(self.zoom.rstrip("%")) / 100)
            except ValueError:
                fixed = "null"
        _emit_canvas_fit(CANVAS_PREVIEW_ROOT, width, height, fixed)

    def _draw_legacy_caption(self, scene_element: object, width: int, height: int) -> None:
        """Under the canvas: the Scene's own settings, the element count, and -- the part
        that matters -- what the drawing above is not able to tell the truth about.
        """
        elements = sceneview.paint_order(scene_element)
        with self.caption:
            summary = (
                f"{width} x {height} {translate_string('pixels')} · {len(elements)} {translate_string('element(s)')}"
            )
            properties = sceneview.scene_properties(scene_element)
            if properties:
                summary += " · " + " · ".join(f"{translate_string(label)}: {value}" for label, value in properties)
            ui.label(summary).classes("text-xs text-gray-500")
            if self._legacy_editing() is not None:
                ui.label(
                    translate_string(
                        "Click an element to select it, Shift-click or drag a box on the background to "
                        "take several, and drag any of them to move them all -- arrow keys nudge, Shift "
                        "for 10px. Drag a handle to resize a single element. Undo, and everything else "
                        "about an element, is back in the editor.",
                    ),
                ).classes("text-xs text-blue-600")
            ui.label(
                translate_string(
                    "Hatched fills and italic underlined text are %variables -- their values live on the "
                    "device, not in the backup, so they are named rather than guessed at. Images, video, "
                    "maps and web content are shown as placeholders. Hover any element for its geometry, "
                    "its variables and the Tasks it runs.",
                ),
            ).classes("text-xs text-gray-500 italic")

    def _draw_v2_caption(self, layout: dict, width: int, height: int) -> None:
        """The V2 counterpart.  Says the screen the layout was drawn in, because unlike a
        Legacy canvas that number is this preview's choice rather than the Scene's -- and
        says where the colours came from, for the same reason.
        """
        with self.caption:
            summary = (
                f"{translate_string('Drawn in')} {self.screen} {width} x {height} dp · "
                f"{sceneview.v2_component_count(layout)} {translate_string('component(s)')}"
            )
            properties = sceneview.v2_layout_summary(layout)
            if properties:
                summary += " · " + " · ".join(f"{translate_string(label)}: {value}" for label, value in properties)
            ui.label(summary).classes("text-xs text-gray-500")
            if self._v2_editing() is not None:
                ui.label(
                    translate_string(
                        "Click a component to select it, shift-click another in the same container to take "
                        "several, and drag to reorder them among their own siblings. Moving a component into "
                        "or out of a container is the editor's In and Out buttons; Undo is there too.",
                    ),
                ).classes("text-xs text-blue-600")
            ui.label(
                translate_string(
                    "The screen size is this preview's, not the Scene's -- a Version 2 layout has no size "
                    "of its own, so change 'Screen' to see it re-flow. Colours named by Material role are "
                    "drawn from the Material 3 baseline palette; the device resolves them against its own "
                    "theme, which under Material You comes from the wallpaper. Hatched fills and italic "
                    "underlined text are %variables. Amber outlines mark components with a 'Show when'. "
                    "Hover any component for its modifiers, variables and actions.",
                ),
            ).classes("text-xs text-gray-500 italic")

    def _say(self, message: str, colour_classes: str) -> None:
        """The stand-in for a canvas that cannot be drawn -- said in the caption area so the
        toolbar stays put and the user can change orientation and try again.
        """
        with self.caption:
            ui.label(translate_string(message)).classes(f"text-sm {colour_classes}")


class NiceGuiTextView:
    """Replaces CTkTextview. Handles rendering MapTasker data using HTML."""

    def __init__(
        self,
        master_gui: MyGui,
        title: str,
        the_data: list | dict,
        container: ui.column | None = None,
        jump_to: str = "",
        map_scope: str = "",
        built_for: str = "",
    ) -> None:
        """Initialize the NiceGuiTextView.

        If `container` is given, the view is built inside it directly instead of the
        master GUI's main content_container -- used to render into a separate popped-out
        browser window/tab without disturbing the main window's layout.

        `jump_to` is a mapjump token this view scrolls to and highlights the moment its
        content has finished streaming in -- how a clicked report finding reaches a Map
        that had to be built for it.  Acted on there and not before, because a chunk that
        has not arrived cannot be scrolled to.

        `map_scope` is the Project a Map view was built for ("" for the whole file).  It is
        what lets a later clicked finding tell a Map that can show what it points at from
        one that merely contains it -- see jump_map_view.

        `built_for` is what the app was displaying when this view was drawn, as the phrase a
        person reads -- "Project 'Home'", "" for the whole configuration.  Only the toolbar
        badge uses it (see _build_scope_badge); nothing decides anything by it.
        """
        self.master_gui = master_gui
        self.title = title
        self.is_map = isinstance(the_data, dict)
        self.external_container = container
        self.jump_to = jump_to
        self.map_scope = map_scope
        self.built_for = built_for
        # The toolbar's "built for" line and the "the selection has moved on" line beside it.
        # Held on the view so refresh_scope_badges can update them later without a slot: an
        # element's text can be changed from anywhere, while CREATING one cannot.
        self.scope_label = None
        self.scope_stale_label = None
        self.scope_rebuild_button = None
        # Search caching (see search_event). The token identifies the content currently in
        # this view: 0 means "not searchable as a stable document yet" -- process_data streams
        # the content in chunk by chunk, so anything cached about the DOM mid-stream would be
        # a snapshot of a partial document. _mark_content_ready() bumps it once streaming ends,
        # and reload_diagram() drops it back to 0 while the content is replaced.
        self._content_token = 0
        self._content_generation = 0
        self._last_search: tuple[str, list, int, bool] | None = None
        # The last structured question asked of this view (see find_event).  Held so that
        # re-opening Find comes back to the query whose result row the user just followed,
        # rather than to an empty dialog they have to fill in again.
        self._find_query: mapfind.Query | None = None
        # The last Replace the user set up on this view -- ("action", old key, new key,
        # project) or ("variable", name, owner, new name).  The INPUTS, not the Plan: a
        # Plan holds live elements, and holding those across a dialog that may have been
        # reopened after another edit is the stale-handle bug apply()'s own attachment
        # check exists to catch.  Reopening rebuilds the plan from these instead.
        self._replace_inputs: tuple | None = None
        # The Find/Replace dialog this view currently has up, or None.  Held because that
        # dialog no longer always takes itself down: following one of its own rows docks it
        # to the right edge and leaves it there (see find_event's dock), so a second press
        # of Find/Replace has to dispose of the one already on screen rather than build a
        # second one over it.
        self._find_dialog: ui.dialog | None = None
        self.build_ui()
        register_view(master_gui, self)
        # Schedule the coroutine into the active event loop safely
        self._task = asyncio.create_task(self.process_data(the_data))
        # A bare create_task drops whatever the coroutine raises on the floor: the view is
        # left half-built and the app says nothing, which is a long way to debug from.  Every
        # failure in here shows up as "the view did not finish", so it is worth a line in the
        # log saying which one it was.
        self._task.add_done_callback(_report_view_failure)

    def _mark_content_ready(self) -> None:
        """Marks this view's content as fully streamed in, under a fresh content token.

        The token is what lets the browser-side search index (and the results cache below)
        be trusted: it changes whenever the content does, so an index built against the
        previous content can never be mistaken for one built against this one.
        """
        self._content_generation += 1
        self._content_token = self._content_generation
        self._last_search = None

    async def _deliver_jump(self) -> None:
        """Take this freshly built Map to the object a clicked report finding asked for.

        Runs once and then forgets the token: this is the delivery of one click, not a
        property of the view, and a later reload of the same page should not silently jump
        somewhere the user has since scrolled away from.

        Says so when the object turns out not to be there after all.  The rebuild that led
        here already went to the whole configuration at a detail level chosen for this
        object, so the remaining explanations are narrow -- the view limit cut the Map short
        before reaching it, or it is one of the things the Map has no line for (a variable
        the Map's own variable table does not list, for one) -- and either way the useful
        thing to say is that it is not there, not to guess which.
        """
        token, self.jump_to = self.jump_to, ""
        target = mapjump.Target.from_token(token) if token else None
        if target is None:
            return

        with self.scroll_area:
            try:
                landed = await ui.run_javascript(mapjump.jump_js(target.anchor), timeout=5)
            except (TimeoutError, RuntimeError):
                # The page went away, or never finished connecting, between the content
                # arriving and this asking it to scroll.  There is nobody left to tell.
                return
            if not landed:
                ui.notify(
                    f"{translate_string('Built the Map, but it has no line for')} {target.label}",
                    type="warning",
                    position="top",
                )

    def invalidate_search_cache(self) -> None:
        """Drops the cached search results, without touching the browser-side text index.

        Called when the highlights the cached results point at are removed from the page
        (the "Clear" button, see clear_event in userintr.py). The results are only reusable
        while their highlight spans are still in the DOM -- each cached row's click handler
        jumps to one by element id.
        """
        self._last_search = None

    def _build_scope_badge(self) -> None:
        """The toolbar line saying what this view was drawn for, and whether that is still
        what the app is showing.

        A Diagram is a SNAPSHOT.  Nothing rebuilds it when the user picks a different single
        Project, Profile, Task or Scene, so it goes on drawing the selection it was built
        for -- and its hotlinks go on pointing at those objects, which is fine until the user
        moves on and then reads the two views as though they agree.  Clicking one of those
        hotlinks then answers with a Map of the object clicked (see rebuild_map_for_jump),
        replacing the Map the user had just built for their new selection, which is a
        surprise precisely because nothing on screen said the Diagram was from another time.

        So it says so, in the one place the clicking happens.  Nothing is disabled and no
        behaviour changes: the hotlinks still work, and the Rebuild button is offered rather
        than done, because a Diagram of a large configuration is slow to draw and the user
        may well want the old one a moment longer.

        Both labels are created here whatever the state, and only their text and visibility
        change afterwards -- see refresh_scope_badges for why that distinction matters.
        """
        self.scope_label = ui.label("").classes("text-xs text-gray-500 italic ml-4")
        self.scope_stale_label = ui.label("").classes("text-xs text-orange-500 font-bold")

        async def rebuild() -> None:
            """Draw this view again for whatever is selected now.

            Through view_event, the same call the Diagram button makes, so the rebuild is
            the view the user would get by pressing it -- this is a shortcut to that button,
            not a second way of building a Diagram.
            """
            handlers = getattr(self.master_gui, "event_handlers", None)
            if handlers is None:
                ui.notify(translate_string("Press Diagram View to rebuild it."), type="info", position="top")
                return
            await handlers.view_event("diagram")

        self.scope_rebuild_button = (
            ui.button(translate_string("Rebuild"), on_click=rebuild).props("dense flat").classes("text-orange-500")
        )
        self.refresh_scope_badge()

    def refresh_scope_badge(self) -> None:
        """Put the current answer into the badge built above.

        Text and visibility only.  Called at build time and again whenever the selection
        changes, from a context that has no NiceGUI slot -- which is exactly why nothing here
        creates an element.
        """
        if self.scope_label is None:
            return
        drawn, changed = scope_badge_text(self.built_for, mapjump.current_scope().phrase)
        self.scope_label.set_text(drawn)
        self.scope_stale_label.set_text(changed)
        self.scope_stale_label.set_visibility(bool(changed))
        self.scope_rebuild_button.set_visibility(bool(changed))

    def build_ui(self) -> None:
        """Builds the UI layout for the various text views, including toolbar and scrollable display area."""

        # A popped-out view (its own browser window/tab, see rungui.py's "/popout/{view_type}"
        # page) has the whole viewport to itself, so its scroll area flex-fills the remaining
        # height after the toolbar instead of the fixed 70vh used when embedded alongside the
        # rest of the main window's layout.
        is_popout = self.external_container is not None

        if is_popout:
            container_context = self.external_container
            container_context.classes("w-full h-screen flex flex-col p-0 m-0 gap-0")
        elif hasattr(self.master_gui, "content_container") and self.master_gui.content_container:
            self.master_gui.content_container.clear()
            container_context = self.master_gui.content_container
        else:
            container_context = ui.column()

        # "Diagram" view intentionally starts unwrapped so ASCII-art connectors stay aligned.
        is_diagram = self.title.startswith("Diagram")

        # Set the main container to a vertical layout with full width and height
        with container_context:
            # Toolbar
            with ui.row().classes("w-full items-center gap-2 p-2 mb-2 shrink-0") as self.gui_toolbar:
                ui.label(f"{self.title}").classes("text-orange-500 font-bold mr-4")
                self.search_input = ui.input(placeholder=translate_string("Search...")).classes("w-48")
                search_button = ui.button(translate_string("Search"), on_click=self.search_event).classes("bg-blue-600")
                with search_button:
                    ui.tooltip(
                        translate_string(
                            "The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data.\n\n"
                            "It will only show the first 200 instances of the search string.\n\n"
                            "Click on the line number to go to that line in the text view box.\n\n"
                            "The 'Clear' button will clear the search results.\n\n",
                        ),
                    ).style("white-space: pre-wrap")
                ui.button(translate_string("Clear"), on_click=self.master_gui.event_handlers.clear_event).classes(
                    "bg-blue-600",
                )
                # Structured search, alongside the text one rather than replacing it: the
                # two answer different questions (see find_event).  Offered on the Map and
                # the Diagram and nowhere else -- it answers with objects in the loaded
                # configuration, which is what those two views draw; the Misc view shows
                # reports, which have their own clickable rows already.
                if self.is_map or is_diagram:
                    find_button = ui.button(translate_string("Find/Replace"), on_click=self.find_event).classes(
                        "bg-blue-600",
                    )
                    with find_button:
                        ui.tooltip(
                            translate_string(
                                "'Find/Replace' asks the loaded configuration a question rather than searching the "
                                "text on screen: every Task performing a given action, every Profile a given "
                                "trigger fires, everything that names a given app or Scene.\n\n"
                                "The boxes combine -- pick a trigger and an action to find the Profiles that "
                                "trigger that way and run a Task that does that.\n\n"
                                "Results come back as a list of objects; click one to be taken to it.\n\n",
                            ),
                        ).style("white-space: pre-wrap")
                ui.separator().props("vertical")
                ui.button(translate_string("Top"), on_click=lambda: self.scroll("top")).classes("bg-blue-600")
                ui.button(translate_string("Bottom"), on_click=lambda: self.scroll("bottom")).classes("bg-blue-600")
                ui.button(translate_string("Toggle Wrap"), on_click=self.toggle_wrap).classes("bg-blue-600")
                if self.is_map:
                    self.map_message_label = ui.label(PrimeItems.view_limit_msg).classes("text-orange-400 italic ml-4")
                if is_diagram:
                    ui.separator().props("vertical")
                    # Held on the view, not left anonymous, so "Reset Options" can move it:
                    # this pulldown lives on the Diagram view's own toolbar rather than in the
                    # settings drawer, and a reset that changed the value without moving the
                    # control would leave the two disagreeing on screen.
                    self.profiles_per_line_select = (
                        ui
                        .select(
                            options=[str(n) for n in range(11)],
                            value=str(self.master_gui.profiles_per_line),
                            label=translate_string("Profiles Per Line"),
                            on_change=self._profiles_per_line_selected,
                        )
                        .classes("w-40")
                        .props("dense")
                    )
                    _create_diagram_tools(self)
                    self.diagram_message_label = ui.label("").classes("text-orange-400 italic ml-4")
                    self._build_scope_badge()

            self.wrap_enabled = "Diagram" not in self.title
            self.wrap_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"

            # min-h-0 lets this flex item shrink below its content's intrinsic size -- without it
            # a flex column's default min-height:auto would keep growing the scroll area (and the
            # page) to fit all the streamed-in content instead of scrolling internally.
            scroll_height_classes = "flex-1 min-h-0" if is_popout else "h-[70vh]"

            # Tailwind's text-sm utility (below) pairs a 14px font with a 20px line-height --
            # comfortable for prose, but visibly loose for a dense box-drawn diagram. Tighten it
            # for the Diagram view only; keep process_data()'s approx_px_per_line chunk-height
            # estimate in sync with this so scrolling doesn't jump around as chunks pop in.
            line_height_style = " line-height: 1.2;" if is_diagram else ""

            # The Map view renders MapTasker.html, every color in which was picked against the
            # configured output background -- the same one frontmtr writes onto that file's
            # <body>. The app's own page background is set from the dark-mode toggle instead,
            # so the two disagreed: open the file and the output sits on Lavender, show the
            # same output here and it sat on white. Anything the output colors near-matches
            # (a TaskerNet description's white headings, say) then disappears. Use the
            # configured background here too, so the view shows what the file shows.
            # "!important" is needed, not decorative: the light-mode overrides injected by
            # inject_shared_head_styles() force "background-color: #ffffff !important" onto
            # every .q-scrollarea to keep macOS's system appearance from bleeding through, and
            # a plain inline style loses to that. An important declaration in the style
            # attribute is the one thing that outranks an important rule in a stylesheet, and
            # it applies to this one scroll area rather than weakening the override for the
            # drawers, cards and tab panels that rely on it.
            background_style = ""
            if self.title.startswith("Map"):
                background = css_color(PrimeItems.colors_to_use.get("background_color", ""))
                if background:
                    background_style = f" background-color: {background} !important;"

            self.scroll_area = (
                ui
                .scroll_area()
                # min-w-0 keeps this a flex child that can't be stretched wider than its container by
                # long unbreakable content; without it the default flex min-width:auto lets the box
                # (and the whole page) grow past the viewport once the full content has streamed in.
                .classes(
                    f"w-full max-w-full min-w-0 block {scroll_height_classes} "
                    f"border-2 border-gray-600 p-4 text-sm {self.wrap_classes}",
                )
                .style(
                    # The font the output was generated with, which process_data() then
                    # reconciles against the file it actually reads. Deliberately not
                    # master_gui.font -- see the note there on why that can be stale.
                    f"width: 100%; max-width: 100%; "
                    f"font-family: '{PrimeItems.program_arguments['font']}', monospace;"
                    f"{line_height_style}{background_style}",
                )
            )

    async def process_data(self, the_data: dict | list) -> None:
        """Converts data to HTML chunks, preventing single-packet WebSocket buffer overruns.

        All ui.html() calls below pass sanitize=False: the content is this program's own
        MapTasker.html/diagram output, not untrusted input. NiceGUI's default client-side
        sanitizer (the browser's Sanitizer API) strips "id", "class", and "data-*" attributes,
        which silently breaks in-page #fragment hyperlinks (e.g. the "Task ... has too many
        actions" links) and the Diagram view's click-to-highlight connectors -- their <a href>
        source tags survive sanitizing, but the <a id="..."> targets and .connector/
        data-connector-id spans they depend on do not.
        """
        is_diagram = self.title.startswith("Diagram")
        # Starting point, used as-is by the Misc view (which has no generated file behind it).
        # The file-backed views replace this below with the font their file actually carries.
        html_style = f"width: 100%; max-width: 100%; font-family: '{PrimeItems.program_arguments['font']}', monospace;"
        if not is_diagram:
            html_style += " word-break: break-word;"

        if self.title.startswith("Map"):
            file_to_read = os.path.join(os.getcwd(), "MapTasker.html")
        elif is_diagram:
            file_to_read = os.path.join(os.getcwd(), DIAGRAM_FILE)
        elif self.title.startswith("Misc"):
            with self.scroll_area:
                content_str = "\n".join(str(line) for line in the_data) if isinstance(the_data, list) else str(the_data)
                ui.html(f"<pre style='{html_style}'>{content_str}</pre>", sanitize=False)
            # A report rendered by mapjump.html_report marks the rows that point at
            # something in the Map (see its FINDING_CLASS).  Tested for rather than assumed,
            # since this branch also shows reports that carry no such rows at all -- the
            # file comparison, and any report from a build before those rows existed.
            if mapjump.FINDING_CLASS in content_str:
                enable_finding_clicks(self)
            self._mark_content_ready()
            return

        try:
            with open(file_to_read, encoding="utf-8") as f:
                final_html = f.read()
                # The diagram file is plain text (no HTML markup), and its line numbers must line
                # up 1:1 with PrimeItems.diagram_connectors (recorded when the diagram was built) so
                # clicking a connector highlights the right one -- so skip the HTML-specific/blank-line
                # collapsing optimizations here; they aren't meaningful for plain text anyway.
                if not is_diagram:
                    final_html = HTML_OPTIMIZE_PATTERN.sub(
                        lambda match: HTML_REPLACEMENT_MAP[match.group(0)],
                        final_html,
                    )

            # Render in whatever font the file we just read was actually generated with,
            # rather than overriding it with the GUI's current selection.
            #
            # This used to rewrite the file's font-family to self.master_gui.font. That is
            # only right while the two agree -- and the popout page resolves its gui through
            # PrimeItems.mygui, which is simply the most recently constructed MyGui, so a
            # main window that got rebuilt (a reload, a reconnect, a second window) leaves a
            # .font behind that never generated anything. Rewriting to it then replaced a
            # correct font with a stale one, which is why the saved MapTasker.html could show
            # the selected font while the Map view of that very same file did not.
            #
            # Reading the font back out of the file removes the disagreement outright: the
            # view can only ever show what the output it is displaying was built with. The
            # Diagram file is plain text with no CSS of its own, hence the fallback to the
            # font that generated this run.
            extracted_font = self.extract_first_font_name(final_html)
            view_font = (
                extracted_font if extracted_font != "Font name not found" else PrimeItems.program_arguments["font"]
            )
            html_style = f"width: 100%; max-width: 100%; font-family: '{view_font}', monospace;"
            if not is_diagram:
                html_style += " word-break: break-word;"
            # build_ui() styled the scroll area before this file had been read, so bring it
            # into step now that the font it is actually holding is known.
            self.scroll_area.style(f"font-family: '{view_font}', monospace;")

            # --- STREAMING CHUNK ENGINE ---
            # Slice the giant HTML text by lines and push them in digestible blocks
            html_lines = final_html.splitlines()
            if html_lines and html_lines[0].strip() == '<span class="normtab"></span><!doctype html>':
                del html_lines[0]  # Remove the first line if it matches the unwanted header

            connectors_by_line = _connectors_by_line() if is_diagram else None
            # What makes the Diagram clickable rather than merely drawn -- see diagintr.
            # Empty for a Diagram file left on disk by an older run, in which case the
            # lines below are wrapped exactly as they always were.
            diagram_model = diagintr.model() if is_diagram else {}
            nodes_by_line = diagintr.nodes_by_line(diagram_model)
            folds_by_line = diagintr.folds_by_line(diagram_model)

            # The Diagram view's click-to-highlight feature wraps every connector character in its
            # own <span> (tens of thousands of them on a large diagram, since a run only merges
            # with its neighbor when they're on the very same line -- see
            # compute_diagram_connector_groups() in diagram.py). That many extra inline elements
            # makes the browser's layout/paint work on scroll noticeably heavier, so the Diagram
            # view is chunked much more finely than other views. Every view's chunks are marked
            # content-visibility: auto though, which lets the browser skip layout and paint
            # entirely for chunks that are scrolled out of view instead of doing that work for the
            # whole document on every frame -- on a very large Map view that's the difference
            # between laying out the whole document up front and only what's on screen.
            # contain-intrinsic-size reserves roughly the right amount of scrollbar space for an
            # unrendered chunk so scrolling doesn't jump around as chunks pop in and out; it
            # doesn't need to be exact, just close. For the Map/Misc views this estimate is fuzzier
            # than for Diagram's plain monospace text, since long lines there can word-wrap
            # (word-break: break-word, set above) into more than one visual line -- a minor
            # scrollbar jitter, not a correctness issue.
            chunk_size = 150 if is_diagram else 2000
            # text-sm is 14px; at the Diagram view's tightened line-height (1.2, set in build_ui)
            # that's ~17px per line instead of Tailwind's default ~20px.
            approx_px_per_line = 17 if is_diagram else 20

            with self.scroll_area:
                for i in range(0, len(html_lines), chunk_size):
                    chunk_lines = html_lines[i : i + chunk_size]
                    if is_diagram:
                        # No separator: each line carries its own newline, hidden inside the
                        # element that can be folded away with it (see _wrap_diagram_line).
                        chunk_content = "".join(
                            _wrap_diagram_line(
                                i + offset,
                                line,
                                connectors_by_line or {},
                                nodes_by_line,
                                folds_by_line,
                            )
                            for offset, line in enumerate(chunk_lines)
                        )
                    else:
                        chunk_content = "\n".join(chunk_lines)
                    chunk_height = len(chunk_lines) * approx_px_per_line
                    chunk_style = (
                        html_style + f" content-visibility: auto; contain-intrinsic-size: auto {chunk_height}px;"
                    )
                    chunk = ui.html(chunk_content, sanitize=False).classes("w-full block max-w-full").style(chunk_style)
                    # How many lines this chunk holds, so that zooming can re-reserve the
                    # right amount of scrollbar space for it while it is still unrendered --
                    # the height above was worked out against the unzoomed line height.
                    if is_diagram:
                        chunk.props(f"data-lines={len(chunk_lines)}")
                    await asyncio.sleep(0.01)  # Yields loop to keep WebSocket alive

            if connectors_by_line:
                self._enable_connector_highlighting()
                if hasattr(self, "diagram_message_label"):
                    self.diagram_message_label.set_text(translate_string("Click on connector to highlight"))
            if diagram_model.get("nodes"):
                self._enable_diagram_interaction(diagram_model)
                # Replaces the connector hint rather than joining it: both are about
                # clicking the diagram, and this one covers the connectors too.
                if hasattr(self, "diagram_message_label"):
                    self.diagram_message_label.set_text(
                        translate_string("Click a name for its Map entry \u00b7 shift-click a Task for its call chain"),
                    )
            # A diagram cut short at the view limit (diagram.check_limit) says so here, in place
            # of the connector hint: that the diagram stops early is the more important of the
            # two things to tell the user, and this is the Map view's view_limit_msg field by
            # another name (see NiceGuiTextView.build_ui).
            if PrimeItems.diagram_limit_msg and hasattr(self, "diagram_message_label"):
                self.diagram_message_label.set_text(PrimeItems.diagram_limit_msg)
            self._mark_content_ready()
            # Everything is on the page now, so a report finding that asked for this Map can
            # finally be taken to.  Last, deliberately: the anchor it wants may be in the
            # chunk that only just arrived.
            await self._deliver_jump()
            return  # noqa: TRY300

        except FileNotFoundError:
            pass

        # Apply the fallback generation if the file does not exist
        self._process_fallback_data(the_data)
        self._mark_content_ready()

    def _enable_diagram_interaction(self, diagram_model: dict) -> None:
        """Wire up the Diagram view's clickable nodes, folds, chains and zoom.

        The DOM half of it.  The Python half is one subscription -- the same "mt_jump" a
        clicked report finding raises -- so that a node click and a report row are answered
        by the very same code (see go_to_target): the Diagram is one more thing that points
        at the Map, not a second way of getting there.

        Needs an active NiceGUI slot for both, and this runs from process_data's background
        task where the slot stack is empty, hence the scroll area re-entry -- the same
        reason, spelled out at greater length, as in _enable_connector_highlighting.
        """
        with self.scroll_area:
            register_finding_clicks(self.master_gui)
            status_id = f"c{self.diagram_state_label.id}" if hasattr(self, "diagram_state_label") else ""
            ui.run_javascript(diagintr.interaction_js(f"c{self.scroll_area.id}", status_id, diagram_model))

    def _diagram_command(self, name: str, argument: float | None = None) -> None:
        """Carry one of the Diagram toolbar's buttons to the view it belongs to."""
        with self.scroll_area:
            ui.run_javascript(diagintr.command_js(f"c{self.scroll_area.id}", name, argument))

    def _enable_connector_highlighting(self) -> None:
        """Wires up click-to-highlight for Diagram view connector spans.

        Clicking a connector span highlights every span sharing its data-connector-id and clears
        any previously-highlighted connector; clicking empty space clears the highlight too. If
        either end of the highlighted connector -- its topmost or bottommost cell, since a
        connector's spans are emitted top-to-bottom in document order -- is scrolled out of the
        visible area, a floating "Jump to Start"/"Jump to End" button appears so the user can
        bring it into view without hunting for it manually; the button hides itself again once
        the user scrolls that end into view (or clicks away). A jump scrolls vertically to that
        end's line and horizontally back to column 1, so the line is read from its beginning
        rather than from wherever the connector happens to sit across a wide diagram.
        """
        # ui.run_javascript() needs an active NiceGUI "slot" to know which client to target.
        # This runs from a background asyncio task (self._task), after the `with self.scroll_area:`
        # block used to stream in the chunks has already closed, so the slot stack is empty here --
        # calling it unguarded raises RuntimeError (silently, since self._task is fire-and-forget)
        # and the click handler never reaches the browser. Re-entering the scroll_area as a context
        # manager restores the slot so the script actually gets sent.
        with self.scroll_area:
            ui.run_javascript(f"""
                const outerContainer = document.getElementById("c{self.scroll_area.id}");
                if (!outerContainer || outerContainer.dataset.connectorClickWired) return;
                outerContainer.dataset.connectorClickWired = "1";
{mapjump.REVEAL_ANCESTORS_JS}

                // Quasar's own q-scroll-area styling sets "contain: strict" on outerContainer,
                // which creates a new containing block for position:fixed descendants -- a button
                // appended inside it would be clipped to and positioned relative to the scroll
                // area's box instead of the viewport. Appending to document.body avoids that, at
                // the cost of needing to clean up by hand: remove any leftover buttons from a
                // previous Diagram view load first (clear()-ing the view's container doesn't touch
                // elements parented directly under body).
                document.querySelectorAll(".connector-jump-button").forEach((el) => el.remove());

                function makeJumpButton(label, bottomOffset) {{
                    const btn = document.createElement("button");
                    btn.textContent = label;
                    btn.className = "connector-jump-button";
                    btn.style.bottom = bottomOffset + "px";
                    btn.addEventListener("click", (event) => {{
                        event.stopPropagation();
                        const target = btn._jumpTarget;
                        if (target) {{
                            // A chunk currently skipped by content-visibility: auto (see
                            // process_data()'s chunking) never got laid out, so its descendants'
                            // getBoundingClientRect() is meaningless and scrollIntoView() would
                            // land in the wrong place. Force that chunk to lay out for real first
                            // -- it's the one we're about to scroll to anyway, so there's no
                            // wasted work, and leaving it visible afterward is harmless.
                            mtRevealAncestors(target);
                            // Instant, not smooth: the jump can cover tens of thousands of pixels
                            // on a large diagram, where an animated scroll would be slow to land
                            // and distracting rather than helpful.
                            //
                            // Vertical placement only. Centering horizontally on the connector
                            // (inline: "center") parked a wide diagram mid-line, so the user
                            // landed on the right line but somewhere out in the middle of it;
                            // "nearest" keeps scrollIntoView from moving sideways on its own and
                            // the loop below then pins every scrollable ancestor back to column 1.
                            target.scrollIntoView({{block: "center", inline: "nearest", behavior: "auto"}});
                            for (let a = target.parentElement; a; a = a.parentElement) {{
                                if (a.scrollWidth > a.clientWidth) {{
                                    a.scrollLeft = 0;
                                }}
                            }}
                            if (document.scrollingElement) {{
                                document.scrollingElement.scrollLeft = 0;
                            }}
                            // Don't wait for the resulting "scroll" event to re-check visibility --
                            // it fires asynchronously, and updateJumpButtons is hoisted so it's
                            // already safe to call here even though it's defined further down.
                            updateJumpButtons();
                        }}
                    }});
                    document.body.appendChild(btn);
                    return btn;
                }}
                const jumpEndBtn = makeJumpButton("Jump to End", 16);
                const jumpStartBtn = makeJumpButton("Jump to Start", 60);

                function isElementVisible(el, container) {{
                    // Vertical only, matching what the jump actually does: it scrolls to the
                    // connector's line and then resets to column 1, so a target sitting off to
                    // the right is not something the button can help with -- testing for it
                    // would leave the button showing forever on a wide diagram. A connector's
                    // run can also be taller than the container, in which case requiring it to
                    // fit entirely inside can never be satisfied even right after a successful
                    // jump; its midpoint landing inside is a better proxy for "you're there".
                    const er = el.getBoundingClientRect();
                    const cr = container.getBoundingClientRect();
                    const midY = er.top + er.height / 2;
                    return midY >= cr.top && midY <= cr.bottom;
                }}

                function positionJumpButtons() {{
                    const rect = outerContainer.getBoundingClientRect();
                    const viewportWidth = document.documentElement.clientWidth;
                    const rightPx = Math.max(8, viewportWidth - rect.right + 16);
                    jumpEndBtn.style.right = rightPx + "px";
                    jumpStartBtn.style.right = rightPx + "px";
                }}
                positionJumpButtons();
                window.addEventListener("resize", positionJumpButtons);

                function updateJumpButtons() {{
                    if (jumpEndBtn._jumpTarget && document.body.contains(jumpEndBtn._jumpTarget)
                        && !isElementVisible(jumpEndBtn._jumpTarget, outerContainer)) {{
                        jumpEndBtn.style.display = "block";
                    }} else {{
                        jumpEndBtn.style.display = "none";
                    }}
                    if (jumpStartBtn._jumpTarget && document.body.contains(jumpStartBtn._jumpTarget)
                        && !isElementVisible(jumpStartBtn._jumpTarget, outerContainer)) {{
                        jumpStartBtn.style.display = "block";
                    }} else {{
                        jumpStartBtn.style.display = "none";
                    }}
                }}

                const scroller = outerContainer.querySelector(".q-scrollarea__container") || outerContainer;
                scroller.addEventListener("scroll", updateJumpButtons);

                outerContainer.addEventListener("click", (event) => {{
                    const target = event.target.closest(".connector");
                    outerContainer.querySelectorAll(".connector-highlight").forEach((el) => {{
                        el.classList.remove("connector-highlight");
                    }});
                    jumpEndBtn._jumpTarget = null;
                    jumpStartBtn._jumpTarget = null;
                    if (target) {{
                        const id = target.dataset.connectorId;
                        const matches = outerContainer.querySelectorAll(`.connector[data-connector-id="${{id}}"]`);
                        matches.forEach((el) => {{
                            el.classList.add("connector-highlight");
                        }});
                        if (matches.length > 0) {{
                            jumpStartBtn._jumpTarget = matches[0];
                            jumpEndBtn._jumpTarget = matches[matches.length - 1];
                        }}
                    }}
                    updateJumpButtons();
                }});
            """)

    def search_event(self) -> None:
        """Search for the input text inside the text views and display a clickable results popup."""
        query = self.search_input.value.strip()
        if not query:
            ui.notify(translate_string("Please enter a search term."), type="warning")
            return

        client = context.client

        # Cached results: re-running the search that is already showing costs nothing but
        # rebuilding the dialog. Deliberately a single entry rather than a query -> results
        # map: only the most recent search's highlight spans are still in the page (each
        # search unwraps the previous one's, as does "Clear"), and every row in the dialog
        # jumps to its match by element id -- so results held for any earlier query would
        # come back with rows that quietly jump nowhere.
        cached = self._last_search
        if cached and self._content_token > 0 and cached[0] == query.lower():
            _, found_items, total_matches, was_truncated = cached
            with self.scroll_area:
                self._report_search_results(query, found_items, total_matches, was_truncated, client)
            return

        # Upgraded JavaScript engine targeting Quasar content nodes and penetrating Shadow Roots
        js_code = f"""
            const outerContainer = document.getElementById("c{self.scroll_area.id}");
            // Shape every return the same way: the Python side reads .get() off this, so
            // handing back a bare list here would swap the timeout for an AttributeError.
            if (!outerContainer) return {{ results: [], totalMatches: 0, truncated: false }};

            const container = outerContainer.querySelector('.q-scrollarea__content') || outerContainer;

            const searchTerm = {json.dumps(query.lower())};
            const termLength = {len(query)};
            // Identifies the content in the view (see _mark_content_ready); 0 while it is
            // still streaming in, in which case nothing may be cached about it.
            const contentToken = {self._content_token};

            // 1. Purge previous search highlights completely across Shadow boundaries.
            //    Used only when there is no usable cached index -- it swaps each highlight
            //    for a brand-new text node, which is exactly what the cached index cannot
            //    survive (it holds references to the nodes themselves). The cached path
            //    below unwraps the very same spans without that.
            function clearPreviousHighlights(root) {{
                const highlights = root.querySelectorAll ? root.querySelectorAll('.search-highlight') : [];
                highlights.forEach(el => {{
                    const textNode = document.createTextNode(el.textContent);
                    el.parentNode.replaceChild(textNode, el);
                }});
                const children = root.querySelectorAll ? root.querySelectorAll('*') : [];
                children.forEach(child => {{
                    if (child.shadowRoot) {{
                        clearPreviousHighlights(child.shadowRoot);
                    }}
                }});
            }}

            const results = [];

            // 2. Recursive text node crawler that only COLLECTS matches (no DOM mutation).
            //    Mutating the DOM (e.g. via surroundContents) while iterating a live
            //    childNodes list causes the newly-inserted split nodes to be picked
            //    back up by the same in-progress loop. On large documents with a
            //    common search term this spirals into extremely expensive (sometimes
            //    effectively endless) work and hangs/crashes the browser tab before
            //    a response is ever sent back to Python. So: collect first, mutate later.
            //
            //    The Map/Diagram/Misc views stream many lines into one element per CHUNK
            //    (joined by literal "\\n", relying on white-space:pre to render them as
            //    separate visual lines -- see process_data() in guiwins.py), not one
            //    element per line. That means a match's immediate parentNode is a whole
            //    chunk (or, in the Diagram view, sometimes just a connector <span>
            //    covering a few characters), not a single line -- so parent.textContent
            //    can't be used to recover "the line the match is on". Instead, build a
            //    linear transcript of the whole container's text up front, recording
            //    each text node's starting offset within it, so each match's line number
            //    and line text can be derived from where its offset falls between
            //    newlines in that transcript.
            //
            //    This whole crawl -- the traversal, the transcript, and the line map built
            //    from it -- depends only on the content of the view, not on what is being
            //    searched for, so it is cached on the container and reused by every later
            //    search of the same content (see the index resolution below).
            function buildIndex() {{
                const textNodes = [];  // {{ node, start }}
                let fullText = '';

                function collectTextNodes(node) {{
                    if (node.shadowRoot) {{
                        collectTextNodes(node.shadowRoot);
                    }}

                    if (node.nodeType === 3) {{
                        if (node.parentNode &&
                            node.parentNode.tagName !== 'SCRIPT' &&
                            node.parentNode.tagName !== 'STYLE') {{
                            textNodes.push({{ node, start: fullText.length }});
                            fullText += node.nodeValue;
                        }}
                    }} else if (node.nodeType === 1 && node.tagName === 'BR') {{
                        // The Diagram view is plain text with literal "\\n" line breaks, but the
                        // Map/Misc/Tree views are real HTML that marks line breaks with <br>
                        // elements instead -- treat each one as a line break in the transcript
                        // too, so line numbers/text line up correctly there as well.
                        fullText += '\\n';
                    }}

                    // Snapshot into a static array so later DOM mutations (done in the
                    // second pass below) can never feed back into this traversal.
                    if (node.childNodes && node.childNodes.length) {{
                        for (const child of Array.from(node.childNodes)) {{
                            collectTextNodes(child);
                        }}
                    }}
                }}

                collectTextNodes(container);

                // Map a global offset into fullText -> 0-based line number, via the offset of
                // every line start (binary search since a large diagram can have many lines).
                const lineStarts = [0];
                for (let i = 0; i < fullText.length; i++) {{
                    if (fullText[i] === '\\n') lineStarts.push(i + 1);
                }}
                return {{ token: contentToken, textNodes, fullText, lineStarts, highlights: [] }};
            }}

            // 3. Resolve the index: reuse the one cached on this container when it was built
            //    against the content that is in it now, otherwise build a fresh one.
            //
            //    What makes this awkward is that highlighting mutates the very nodes the
            //    index points at -- surroundContents() splits a matched text node into
            //    prefix / match / tail -- so a cached index would never survive even its own
            //    first use. Rather than discard it, each search unwraps the spans the previous
            //    one left behind (keeping each match's own text node, unlike the wholesale
            //    purge above, which swaps in new ones) and patches the split entries back into
            //    the index as it makes them, further down. fullText and the line map need no
            //    patching at all: splitting a text node changes no characters.
            let cache = container.__mtSearchIndex;
            let usedCachedIndex = false;
            if (cache && contentToken > 0 && cache.token === contentToken) {{
                for (const span of cache.highlights) {{
                    if (span.parentNode && span.firstChild) {{
                        span.parentNode.replaceChild(span.firstChild, span);
                    }}
                }}
                cache.highlights = [];
                usedCachedIndex = true;
                // A highlight the index has no record of means something outside this routine
                // rewrote the text nodes, so the index can no longer be trusted to match them.
                if (container.querySelector('.search-highlight')) {{
                    clearPreviousHighlights(container);
                    cache = buildIndex();
                    usedCachedIndex = false;
                }}
            }} else {{
                clearPreviousHighlights(container);
                cache = buildIndex();
            }}
            // Keep nothing while the content is still streaming in: the index would describe
            // a document that is only partly there.
            container.__mtSearchIndex = contentToken > 0 ? cache : null;

            const textNodes = cache.textNodes;
            const fullText = cache.fullText;
            const lineStarts = cache.lineStarts;

            function lineNumberForOffset(offset) {{
                let lo = 0, hi = lineStarts.length - 1;
                while (lo < hi) {{
                    const mid = (lo + hi + 1) >> 1;
                    if (lineStarts[mid] <= offset) lo = mid; else hi = mid - 1;
                }}
                return lo;
            }}
            function lineTextForOffset(offset) {{
                const ln = lineNumberForOffset(offset);
                const start = lineStarts[ln];
                const end = ln + 1 < lineStarts.length ? lineStarts[ln + 1] - 1 : fullText.length;
                return fullText.substring(start, end);
            }}

            // 4. Find every occurrence of the term.
            //
            //    This searches the transcript rather than each text node in turn. Scanning
            //    node by node can only ever report the FIRST hit inside any one node, and a
            //    node is not a line: the views stream whole chunks into one element, so in
            //    the Diagram view a single text node routinely holds 150 lines. A term
            //    appearing ten times in a chunk was reported once. The transcript has no
            //    such boundaries, and the cached per-node start offsets map any position in
            //    it back to the node (and offset within it) that has to be wrapped.
            //
            //    Lowercasing the transcript is cached with it -- it depends only on the
            //    content, and it is ~1.5MB of string work on a large Map view.
            function transcriptLower() {{
                if (cache.lowerText === undefined) {{
                    const lower = cache.fullText.toLowerCase();
                    // A handful of characters (e.g. U+0130) lowercase to a different number
                    // of characters, which would shift every offset after them. Rare enough
                    // to detect and step around rather than try to track.
                    cache.lowerText = lower.length === cache.fullText.length ? lower : null;
                }}
                return cache.lowerText;
            }}

            const matches = [];  // {{ pos, index, globalOffset }} -- pos is the index slot to patch
            let spanningSkipped = 0;
            const lowerText = transcriptLower();
            if (lowerText === null) {{
                // Fallback: the transcript's offsets can't be trusted for this content, so
                // take the old per-node scan (first hit in each node) rather than risk
                // wrapping the wrong characters.
                for (let pos = 0; pos < textNodes.length; pos++) {{
                    const entry = textNodes[pos];
                    const value = entry.node.nodeValue;
                    if (!value) continue;
                    const index = value.toLowerCase().indexOf(searchTerm);
                    if (index !== -1) {{
                        matches.push({{ pos, index, globalOffset: entry.start + index }});
                    }}
                }}
            }} else {{
                // Occurrences come out in ascending order, so the index slot for each one can
                // be found by walking a cursor forward instead of searching from scratch.
                let cursor = 0;
                let from = 0;
                for (;;) {{
                    const at = lowerText.indexOf(searchTerm, from);
                    if (at === -1) break;
                    from = at + termLength;

                    while (cursor + 1 < textNodes.length && textNodes[cursor + 1].start <= at) cursor++;
                    const entry = textNodes[cursor];
                    const index = at - entry.start;
                    const value = entry.node.nodeValue;
                    // Skip a match that isn't wholly inside one text node -- it either straddles
                    // two of them (the views split lines across elements for colouring and for
                    // the Diagram's connectors) or crosses one of the newlines the transcript
                    // synthesises for <br>, which exist in no text node at all. A Range over
                    // that can't be wrapped in a single span, so there would be nothing to
                    // highlight or jump to. The per-node scan this replaces could not find
                    // them either, so nothing that used to be reported has been lost.
                    if (index < 0 || !value || index + termLength > value.length) {{
                        spanningSkipped++;
                        continue;
                    }}
                    matches.push({{ pos: cursor, index, globalOffset: at }});
                }}
            }}

            // Cap the number of matches we actually highlight/report. A broad
            // search term (e.g. "Task") against a large rendered document could
            // otherwise still produce thousands of DOM mutations in the pass
            // below, which is slow and unnecessary for a human skimming results.
            const MAX_MATCHES = 200;
            const truncated = matches.length > MAX_MATCHES;
            const matchesToShow = truncated ? matches.slice(0, MAX_MATCHES) : matches;

            // 5. Second pass: now that traversal is fully finished, apply the highlight to
            //    each collected match. Every match's text node is still valid because no
            //    mutation happened during collection.
            //
            //    Matches are grouped by the text node holding them, because one node can now
            //    hold many of them, and wrapping one splits that node: the original keeps
            //    only the text BEFORE the match. Each group is therefore wrapped back to
            //    front, so that every match still to be handled sits at its original offset
            //    in the (progressively shortened) original node. Ids and result rows still
            //    follow document order, via each match's rank in the ascending list.
            const byNode = new Map();  // index slot -> its matches, ascending
            matchesToShow.forEach((match, rank) => {{
                match.rank = rank;
                const group = byNode.get(match.pos);
                if (group) {{ group.push(match); }} else {{ byNode.set(match.pos, [match]); }}
            }});

            const repairs = new Map();  // index slot -> the entries that now replace it
            for (const [pos, group] of byNode) {{
                const entry = textNodes[pos];
                // Entries for the pieces split off this node, kept in document order.
                const pieces = [];
                for (let i = group.length - 1; i >= 0; i--) {{
                    const match = group[i];
                    const span = document.createElement('span');
                    span.className = 'search-highlight';
                    span.id = "search_target_" + (match.rank + 1);
                    span.style.backgroundColor = '#ffd941';
                    span.style.color = '#000000';
                    span.style.fontWeight = 'bold';
                    span.style.display = 'inline';

                    const range = document.createRange();
                    range.setStart(entry.node, match.index);
                    range.setEnd(entry.node, match.index + termLength);
                    range.surroundContents(span);
                    cache.highlights.push(span);

                    // Patch the index for the split just made. The span's own text node holds
                    // the match and the remainder follows it as a new sibling text node --
                    // and both offsets into fullText are already known, so nothing needs
                    // re-crawling. fullText itself is untouched: splitting a text node
                    // changes no characters.
                    const added = [];
                    if (span.firstChild) {{
                        added.push({{ node: span.firstChild, start: entry.start + match.index }});
                    }}
                    const tail = span.nextSibling;
                    if (tail && tail.nodeType === 3) {{
                        added.push({{ node: tail, start: entry.start + match.index + termLength }});
                    }}
                    pieces.unshift(...added);
                }}
                repairs.set(pos, [entry, ...pieces]);
            }}

            for (const match of matchesToShow) {{
                results.push({{
                    elementId: "search_target_" + (match.rank + 1),
                    text: lineTextForOffset(match.globalOffset).trim().substring(0, 100),
                    lineNumber: lineNumberForOffset(match.globalOffset) + 1,
                }});
            }}

            if (container.__mtSearchIndex && repairs.size) {{
                const rebuilt = [];
                for (let pos = 0; pos < textNodes.length; pos++) {{
                    const replacements = repairs.get(pos);
                    if (replacements) {{
                        for (const entry of replacements) rebuilt.push(entry);
                    }} else {{
                        rebuilt.push(textNodes[pos]);
                    }}
                }}
                cache.textNodes = rebuilt;
            }}

            return {{
                results: results,
                totalMatches: matches.length,
                truncated: truncated,
                cachedIndex: usedCachedIndex,
                spanningSkipped: spanningSkipped,
            }};
        """

        async def execute_search() -> None:
            with self.scroll_area:
                # Await the execution of our DOM analyzer script block.
                #
                # Two things this has to survive.  First, the crawl takes as long as it
                # takes -- hence SEARCH_JAVASCRIPT_TIMEOUT rather than NiceGUI's 1-second
                # default, which a Map view of any size blows straight through.  Second,
                # this coroutine is fired off with create_task() and never awaited, so an
                # exception escaping it isn't merely unreported: asyncio prints a bare
                # "Task exception was never retrieved" traceback to the console and the
                # user is left with a search that silently never answers.  Say what
                # happened in the window instead.
                try:
                    search_result = await client.run_javascript(js_code, timeout=SEARCH_JAVASCRIPT_TIMEOUT)
                except TimeoutError:
                    logger.debug(f"guiwins search timed out after {SEARCH_JAVASCRIPT_TIMEOUT} seconds: '{query}'")
                    # The script may or may not have got as far as rearranging the highlights
                    # before it stopped answering, so nothing about this search is reusable.
                    self._last_search = None
                    ui.notify(
                        translate_string(
                            "The search did not finish. The view may be too large, or the browser is busy.",
                        ),
                        type="negative",
                    )
                    return
                found_items = search_result.get("results", [])
                total_matches = search_result.get("totalMatches", len(found_items))
                was_truncated = search_result.get("truncated", False)
                logger.debug(
                    f"guiwins search '{query}': {total_matches} matches, "
                    f"reused text index: {search_result.get('cachedIndex', False)}, "
                    f"unwrappable matches skipped: {search_result.get('spanningSkipped', 0)}",
                )

                # These highlights are now the ones in the page, so this is the one search
                # whose results can be handed back without re-running anything (see above).
                if self._content_token > 0:
                    self._last_search = (query.lower(), found_items, total_matches, was_truncated)

                self._report_search_results(query, found_items, total_matches, was_truncated, client)

        self._search = asyncio.create_task(execute_search())

    def _report_search_results(
        self,
        query: str,
        found_items: list,
        total_matches: int,
        was_truncated: bool,
        client: object,
    ) -> None:
        """Announces a set of search results and builds the clickable results dialog for them.

        Shared by a freshly-run search and a cached one so that re-running the search already
        on screen is indistinguishable from the first run.
        """
        if not found_items:
            ui.notify(f"No matches found for: '{query}'", type="negative")
            return  # Debugging output

        if was_truncated:
            ui.notify(
                f"Showing first {len(found_items)} of {total_matches} matches for: '{query}'",
                type="warning",
            )

        # 3. Create the interactive Search Results Modal Popup Window
        with ui.dialog() as results_dialog, ui.card().classes("w-[750px] max-w-full p-6"):
            header_text = (
                f"Search Results for '{query}' ({len(found_items)} of {total_matches} matches)"
                if was_truncated
                else f"Search Results for '{query}' ({len(found_items)} matches)"
            )
            ui.label(header_text).classes(
                "text-lg font-bold text-blue-600 mb-2",
            )
            ui.label(
                translate_string("Click on a row index line number to jump directly to that match block placement:"),
            ).classes("text-xs text-gray-500 italic mb-4")

            # Create a clear scroll area container for the results rows list matching the active theme font
            with ui.scroll_area().classes(  # noqa: SIM117
                "w-full h-[45vh] border p-2 bg-gray-50 dark:bg-gray-900 rounded",
            ):
                with ui.column().classes("w-full gap-1"):
                    for item in found_items:
                        # Localized function referencing the cross-linked runtime element reference
                        def make_jump_callback(target_id: str = item["elementId"]) -> None:
                            return lambda: (
                                results_dialog.close(),
                                client.run_javascript(search_jump_js(target_id)),
                            )

                        with ui.row().classes(
                            "w-full items-center py-1 border-b dark:border-gray-700 hover:bg-blue-50 dark:hover:bg-blue-950 px-2 rounded transition-colors",
                        ):
                            # Active click hotlink index line label
                            ui.link(f"Line #{item['lineNumber']}", "#").on(
                                "click",
                                make_jump_callback(),
                            ).classes(
                                "text-blue-600 dark:text-blue-400 font-bold font-mono text-sm mr-4 shrink-0 decoration-dotted hover:underline",
                            )
                            # Text context content preview box
                            ui.label(item["text"]).classes(
                                "text-sm font-mono truncate text-gray-800 dark:text-gray-200",
                            )

            # Footer window management close control
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button(translate_string("Close Results Window"), on_click=results_dialog.close).classes(
                    "bg-red-500 text-white px-4",
                )

        results_dialog.open()

    def _build_replace_tab(
        self,
        dialog: ui.dialog,
        index: mapfind.FindIndex,
        jump_to: Callable,
        replace_panel: ui.tab_panel,
    ) -> bool:
        """Build the Find dialog's Replace tab into `replace_panel`.

        Takes the four things it shares with the Find half and nothing else: the dialog to
        close on success, the mapfind index both pulldowns are built from, the jump handler
        a preview row's link uses, and the panel to build into.

        `self` is used only to remember the inputs on the view (see _replace_inputs), which
        is what lets a preview survive a click on one of its own rows.

        Returns whether it restored a previous Replace, so the caller can open the dialog
        on this tab rather than on Find when it did.
        """
        # ##################################################################
        # The Replace tab.
        #
        # Everything below is arranged around one rule: the Replace button is
        # disabled until a preview exists for the values CURRENTLY in the fields,
        # and touching any field clears the preview and disables it again.  There
        # is then no path through these widgets that reaches mapswap.apply without
        # the user having seen mapswap.report_rows first -- which is the whole
        # design, made structural rather than left to the dialog to remember.
        # ##################################################################
        with replace_panel:
            # Built when the Replace tab is first used, not when the dialog opens.
            # It is a second full scan of the XML on top of the one mapfind just
            # did, and most presses of Find never come here at all.
            held: dict = {"variables": None, "plan": None, "inputs": None}

            ui.label(
                translate_string(
                    "Change one thing everywhere it appears. Nothing is altered until you press "
                    "Preview and then Replace, and every change is one Undo away afterwards.",
                ),
            ).classes("text-xs text-gray-500 italic mb-3")

            mode = ui.toggle(
                {
                    "action": translate_string("Task action"),
                    "argument": translate_string("Action argument"),
                    "condition": translate_string("Profile condition"),
                    "variable": translate_string("Variable name"),
                },
                value="action",
            ).props("dense")

            # -- action mode --------------------------------------------------
            with ui.row().classes("w-full items-center gap-2 mt-2") as action_row:
                source_select = (
                    ui
                    .select({}, label=translate_string("Replace this action"), with_input=True)
                    .classes("flex-1 min-w-[220px]")
                    .props("dense")
                )
                target_select = (
                    ui
                    .select({}, label=translate_string("...with this one"), with_input=True)
                    .classes("flex-1 min-w-[260px]")
                    .props("dense")
                )
                # Hidden under a scope, for the reason the Find tab's own gives.
                swap_project = (
                    ui
                    .select(
                        {"": translate_string("Every Project")} | {name: name for name in index.projects},
                        value="",
                        label=translate_string("Narrow to Project"),
                        with_input=True,
                    )
                    .classes("w-56")
                    .props("dense")
                )
                swap_project.set_visibility(index.scope.is_everything)

            # -- argument mode ------------------------------------------------
            # Two rows, because this mode asks for four things and a fifth switch: which
            # action, which of its arguments, which of those actions (by what the argument
            # says now), and what to put there.  One row of five widgets would wrap into an
            # unreadable line on the width this dialog is pinned to.
            with ui.column().classes("w-full gap-2 mt-2") as argument_row:
                with ui.row().classes("w-full items-center gap-2"):
                    arg_action_select = (
                        ui
                        .select({}, label=translate_string("In this action"), with_input=True)
                        .classes("flex-1 min-w-[220px]")
                        .props("dense")
                    )
                    arg_select = (
                        ui
                        .select({}, label=translate_string("...replace this argument"), with_input=True)
                        .classes("flex-1 min-w-[240px]")
                        .props("dense")
                    )
                    arg_project = (
                        ui
                        .select(
                            {"": translate_string("Every Project")} | {name: name for name in index.projects},
                            value="",
                            label=translate_string("Narrow to Project"),
                            with_input=True,
                        )
                        .classes("w-56")
                        .props("dense")
                    )
                    arg_project.set_visibility(index.scope.is_everything)
                with ui.row().classes("w-full items-center gap-2"):
                    arg_match_input = (
                        ui
                        .input(label=translate_string("Only where the value contains (optional)"))
                        .classes("flex-1 min-w-[240px]")
                        .props("dense clearable")
                    )
                    arg_value_input = (
                        ui
                        .input(label=translate_string("...and put this there"))
                        .classes("flex-1 min-w-[240px]")
                        .props("dense clearable")
                    )
                    # Off means the argument is SET to the new value; on means only the
                    # matched text inside it changes.  Both are things people mean by
                    # "replace", and which one they meant cannot be guessed from the two
                    # boxes above -- so it is asked, in the one place where the answer is
                    # visible while the values are being typed.
                    arg_substitute = ui.checkbox(translate_string("Only the matching text")).props("dense")
                    # Tasker leaves out an argument nobody ever set, so this is what makes
                    # "give every Flash a Timeout" reach the Flashes that have none.  Off
                    # by default: adding an argument to a hundred actions is a bigger thing
                    # than editing the ones that already have it, and the preview marks
                    # every row that is an addition rather than a change.
                    arg_add_missing = ui.checkbox(translate_string("Add it where missing")).props("dense")
            argument_row.set_visibility(False)

            # -- condition mode -----------------------------------------------
            # Two pulldowns and a Project, the same shape as the action mode -- and for the
            # same reason: a Profile condition is replaced by KIND, and both halves of that
            # are a choice, one out of what the file holds and one out of what Tasker
            # offers.  Nothing else is asked, because there is nothing else to ask: a
            # condition's settings are its own and do not survive becoming another kind.
            with ui.row().classes("w-full items-center gap-2 mt-2") as condition_row:
                condition_select = (
                    ui
                    .select({}, label=translate_string("Replace this Profile condition"), with_input=True)
                    .classes("flex-1 min-w-[240px]")
                    .props("dense")
                )
                condition_target_select = (
                    ui
                    .select({}, label=translate_string("...with this one"), with_input=True)
                    .classes("flex-1 min-w-[260px]")
                    .props("dense")
                )
                condition_project = (
                    ui
                    .select(
                        {"": translate_string("Every Project")} | {name: name for name in index.projects},
                        value="",
                        label=translate_string("Narrow to Project"),
                        with_input=True,
                    )
                    .classes("w-56")
                    .props("dense")
                )
                condition_project.set_visibility(index.scope.is_everything)
            condition_row.set_visibility(False)

            # -- variable mode ------------------------------------------------
            with ui.row().classes("w-full items-center gap-2 mt-2") as variable_row:
                variable_select = (
                    ui
                    .select({}, label=translate_string("Rename this variable"), with_input=True)
                    .classes("flex-1 min-w-[320px]")
                    .props("dense")
                )
                # A text box with suggestions, NOT a select.  Both jobs have to work here:
                # renaming to a name nothing uses yet, and replacing every use with a
                # variable that already exists ("everywhere this Task says %app_name, say
                # %app_package").  A select with new_value_mode looks like it does both and
                # does the first badly -- a typed name is only committed on Enter, and is
                # thrown away on blur, so the ordinary act of typing a name and reaching for
                # the button loses it.  An input always keeps what was typed, and
                # autocomplete offers the existing variables without ever standing between
                # the user and a name they are inventing.
                new_name_input = (
                    ui
                    .input(label=translate_string("...to this name"))
                    .classes("flex-1 min-w-[260px]")
                    .props("dense clearable")
                )
            variable_row.set_visibility(False)

            replace_summary = ui.label("").classes("text-sm font-bold mt-3")
            replace_area = ui.scroll_area().classes(
                "w-full h-[45vh] border p-2 bg-gray-50 dark:bg-gray-900 rounded",
            )

        def current_inputs() -> tuple:
            """What the Replace fields say right now, in the form the plan is built from.

            One tuple per mode, of whatever length that mode needs.  It is compared whole
            (against the inputs the preview on screen was built from) and unpacked by the
            branch that built it, so the four shapes never meet.
            """
            if mode.value == "action":
                return ("action", source_select.value or "", target_select.value or "", swap_project.value or "")
            if mode.value == "argument":
                return (
                    "argument",
                    arg_action_select.value or "",
                    arg_select.value or "",
                    arg_value_input.value or "",
                    (arg_match_input.value or "").strip(),
                    arg_project.value or "",
                    bool(arg_substitute.value),
                    bool(arg_add_missing.value),
                )
            if mode.value == "condition":
                return (
                    "condition",
                    condition_select.value or "",
                    condition_target_select.value or "",
                    condition_project.value or "",
                )
            # Integer keys into a parallel list, because a select's option keys are
            # serialized to the browser and a variable's identity is the PAIR (name,
            # owner) -- there is no JSON key for a tuple, and flattening the two into
            # one string would need an escape for a separator that a Task name may
            # legitimately contain.  The owner may be mapswap.EVERY_INSTANCE, which is
            # the entry meaning "every instance of this name", and passes straight
            # through to plan_variable_rename as it stands.
            choices = held.get("variable_choices") or []
            position = variable_select.value
            if isinstance(position, int) and 0 <= position < len(choices):
                name, owner = choices[position][0], choices[position][1]
            else:
                name, owner = "", ""
            return ("variable", name, owner, (new_name_input.value or "").strip())

        def variable_index() -> varxref.VariableIndex:
            """The variable cross-reference, built once per dialog and then held."""
            if held["variables"] is None:
                # Scoped, unlike varxref's other callers: a rename WRITES, and what it may
                # write to is what the app is displaying.  See build_index's own note on
                # why whole-file is the default there and this is the exception.
                held["variables"] = varxref.build_index(mapjump.current_scope())
            return held["variables"]

        def invalidate() -> None:
            """A field changed, so whatever is on screen is no longer what would happen.

            Clearing the plan rather than re-running it: re-planning on every keystroke
            of a variable name would scan the file per character, and a preview that
            refreshed itself under the user would make the Replace button's meaning
            depend on when they looked at it.
            """
            if held["plan"] is not None:
                held["plan"] = None
                held["inputs"] = None
                replace_area.clear()
                replace_summary.set_text("")
            # The ticks go with the preview.  They describe changes to a question that is
            # no longer the one on screen, and carrying them into the next preview would
            # tick rows the user never looked at.
            self._replace_ticks = None
            replace_button.disable()

        def fill_targets() -> None:
            """Re-stock the target pulldown for the chosen source action.

            Every candidate is labelled with what choosing it would cost -- what
            carries over and what does not -- so that nothing in this list is a
            surprise, and the pairs that keep the most sit at the top.  Blocked
            targets stay in the list with their reason as the label: a user who
            cannot find an action learns nothing, one who reads why learns the
            answer to the question they were about to ask.
            """
            source = source_select.value
            if not source:
                target_select.set_options({})
                return
            target_select.set_options(
                {key: label for key, label, _fidelity in mapswap.fidelity_choices(source)},
                value=None,
            )

        def fill_arguments() -> None:
            """Re-stock the argument pulldown for the chosen action.

            Every argument is listed, including the ones this cannot write: an App or an
            Icon is a picker's subtree rather than a typed value, and a user who cannot
            find the argument learns nothing while one who reads why learns the answer.
            The refusal rides in the label; the planner says it again in the preview, since
            the pulldown is not where the decision is finally made.
            """
            action = arg_action_select.value
            if not action:
                arg_select.set_options({})
                return
            arg_select.set_options(
                {arg_id: label for arg_id, label, _refusal in mapswap.argument_choices(action)},
                value=None,
            )

        def fill_condition_targets() -> None:
            """Re-stock the target pulldown for the chosen Profile condition.

            Every kind Tasker can watch for is in the list, labelled with what choosing it
            would do -- 'a fresh, empty Day', or the reason a plugin's condition cannot be
            built at all.  Same courtesy fill_targets pays a blocked action target, and the
            same reason: a user who cannot find a condition learns nothing, one who reads
            why learns the answer to the question they were about to ask.
            """
            source = condition_select.value
            if not source:
                condition_target_select.set_options({})
                return
            condition_target_select.set_options(
                {key: label for key, label, _fidelity in mapswap.condition_targets(source)},
                value=None,
            )

        def switch_mode() -> None:
            """Show one mode's fields, hide the others', and drop any preview."""
            action_row.set_visibility(mode.value == "action")
            argument_row.set_visibility(mode.value == "argument")
            condition_row.set_visibility(mode.value == "condition")
            variable_row.set_visibility(mode.value == "variable")
            if mode.value == "argument" and not arg_action_select.options:
                arg_action_select.set_options(
                    {key: label for key, label, _count in mapswap.source_choices(index)},
                )
            if mode.value == "condition" and not condition_select.options:
                condition_select.set_options(
                    {key: label for key, label, _count in mapswap.condition_choices(index)},
                )
            if mode.value == "variable" and not held.get("variable_choices"):
                choices = mapswap.variable_choices(variable_index())
                held["variable_choices"] = choices
                variable_select.set_options(
                    {position: label for position, (_name, _owner, label) in enumerate(choices)},
                )
                # The same variables offered as completions on the target box: a rename
                # target is only ever a name, so two locals sharing one in different Tasks
                # are the same string to write.  Sorted rather than ranked by use like the
                # source list -- this one is looked up, not browsed.
                new_name_input.set_autocomplete(sorted({name for name, _owner, _label in choices}))
            invalidate()

        def ticker(plan: mapswap.Plan, position: int) -> Callable:
            """One preview row's tick box: put this change in or out of what Replace applies.

            A factory rather than a lambda built in the loop, for the usual reason: a
            lambda would close over the loop variable and every box would end up
            ticking the last row.
            """

            def ticked(event: object) -> None:
                if getattr(event, "value", False):
                    plan.selected.add(position)
                else:
                    plan.selected.discard(position)
                # Recorded as it happens rather than on the way out: the way out is a click
                # on one of these rows, which closes the dialog from inside that row's own
                # handler, so there is no later moment reliably reached.
                remember_ticks()

            return ticked

        def draw(plan: mapswap.Plan) -> None:
            """Draw the plan: warnings, then what cannot be changed, then what can.

            Skips before changes because they are the part the user must read and the
            part they will not scroll back up for.  Every location is a link, because
            the only way to judge "should this one change" is to go and look at it.
            """
            replace_area.clear()
            replace_summary.set_text(f"{plan.what} -- {plan.tally()}")

            with replace_area, ui.column().classes("w-full gap-1"):
                for warning in plan.warnings:
                    ui.label(warning).classes(
                        "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1",
                    )

                if plan.skips:
                    ui.label(
                        f"{translate_string('Cannot be changed')} ({len(plan.skips)})",
                    ).classes("text-xs font-bold text-red-500 mt-2")
                    for skip in plan.skips[:_REPLACE_SKIP_LIMIT]:
                        with ui.row().classes("w-full items-baseline gap-2 pl-2"):
                            ui.link(skip.where.label, "#").on("click", jump_to(skip.where)).classes(
                                "text-blue-600 dark:text-blue-400 font-mono text-xs shrink-0 "
                                "decoration-dotted hover:underline",
                            )
                            ui.label(skip.explanation).classes("text-xs text-gray-500 truncate")
                    if len(plan.skips) > _REPLACE_SKIP_LIMIT:
                        ui.label(
                            f"...{len(plan.skips) - _REPLACE_SKIP_LIMIT} {translate_string('more')}",
                        ).classes("text-xs text-gray-500 italic pl-2")

                if not plan.changes:
                    ui.label(
                        translate_string("Nothing here would change."),
                    ).classes("text-sm text-gray-500 italic mt-2")
                    return

                project = None
                for position, change in enumerate(plan.changes):
                    if change.site.where.project != project:
                        project = change.site.where.project
                        ui.label(
                            (
                                f"{translate_string('Project')} '{project}'"
                                if project
                                else translate_string("In no Project")
                            ),
                        ).classes("text-xs font-bold text-orange-500 mt-2")
                    with ui.row().classes(
                        "w-full items-baseline py-1 border-b dark:border-gray-700 px-2 rounded",
                    ):
                        ui.checkbox(
                            value=position in plan.selected,
                            on_change=ticker(plan, position),
                        ).props("dense")
                        ui.link(change.site.where.label, "#").on("click", jump_to(change.site.where)).classes(
                            "text-blue-600 dark:text-blue-400 font-mono text-sm shrink-0 "
                            "decoration-dotted hover:underline",
                        )
                    with ui.row().classes("w-full items-baseline pl-10 pb-1"):
                        ui.label(f"{change.before}  →  {change.after}").classes(
                            "text-xs text-gray-600 dark:text-gray-300 font-mono truncate",
                        )
                        if change.note:
                            ui.label(change.note).classes("text-xs text-orange-600 dark:text-orange-400 truncate")

        def remember_ticks() -> None:
            """Keep the current tick boxes on the view, ready for the next reopen."""
            plan = held["plan"]
            self._replace_ticks = plan.ticked_identities() if plan is not None else None

        def build_preview(restore: collections.Counter | None = None) -> None:
            """Build the plan for whatever the fields say, and show it.

            `restore` re-applies the tick boxes from a previous preview of the same
            question -- the way back from following one of its own rows.  Applied after the
            plan is built and before it is drawn, so what appears on screen is what the
            user left, defaults and all.

            One branch per mode to BUILD the plan, and one tail for all four to show it:
            what a preview is -- held, drawn, ticked, and the only thing the Replace button
            can act on -- is the same whatever question produced it, and a mode with its own
            copy of that tail is a mode that can drift out of step with the rule.
            """
            inputs = current_inputs()
            kind = inputs[0]

            if kind == "action":
                _, source, target, project = inputs
                if not source or not target:
                    ui.notify(
                        translate_string("Choose an action to replace, and one to replace it with."),
                        type="warning",
                    )
                    return
                plan = mapswap.plan_action_swap(source, target, project)
            elif kind == "argument":
                _, action, arg_id, new_value, match, project, substitute, add_missing = inputs
                if not action or not arg_id:
                    ui.notify(
                        translate_string("Choose an action, and which of its arguments to replace."),
                        type="warning",
                    )
                    return
                plan = mapswap.plan_argument_replace(
                    action,
                    arg_id,
                    new_value,
                    match,
                    project,
                    substitute,
                    add_missing,
                )
                if plan.is_empty and not plan.skips and not plan.warnings:
                    # Said out loud rather than left to an empty list: "nothing holds that
                    # value" and "they all hold the new one already" look identical on
                    # screen and mean opposite things.
                    ui.notify(
                        translate_string("Nothing in scope has that argument to change."),
                        type="warning",
                    )
            elif kind == "condition":
                _, source, target, project = inputs
                if not source or not target:
                    ui.notify(
                        translate_string("Choose a Profile condition to replace, and one to replace it with."),
                        type="warning",
                    )
                    return
                plan = mapswap.plan_condition_replace(source, target, project)
            else:
                _, name, owner, new_name = inputs
                if not name or not new_name:
                    ui.notify(translate_string("Choose a variable, and type the new name."), type="warning")
                    return
                plan = mapswap.plan_variable_rename(variable_index(), name, owner, new_name)

            if restore is not None:
                plan.restore_ticks(restore)

            held.update(plan=plan, inputs=inputs)
            self._replace_inputs = inputs
            draw(plan)
            remember_ticks()
            if plan.changes:
                replace_button.enable()
            else:
                replace_button.disable()

        def preview() -> None:
            """The Preview button: a fresh look at the question, tick boxes at their defaults."""
            build_preview()

        async def rebuild_after_replace() -> None:
            """Redraw the view the Replace was launched from, so it shows what just changed.

            The view on screen was rendered from the configuration as it stood BEFORE the
            apply, and every one of these edits is a content change -- an action becomes a
            different action, a variable reads by a different name -- so what the user is
            looking at the moment the dialog closes is, line for line, the thing they just
            replaced.  Leaving that until the next press of Map View invites them to run
            the same Replace again on a preview that says it is still there.

            Whichever view asked, not always the Map: a Replace started from the Diagram
            leaves that just as stale, and rebuilding a Map over it would answer a question
            about one view by switching the user to another.  The view type comes off the
            title, which is what view_event built it from ("Map View", "Diagram View").

            Run through view_event -- the same call the Map/Diagram/Tree buttons make -- so
            the rebuild honours whatever the user currently has selected, including the
            single-item selection the Replace was scoped to.  No overrides: this is the
            view they already had, rebuilt, not a different one.
            """
            handlers = getattr(self.master_gui, "event_handlers", None)
            if handlers is None:
                ui.notify(
                    translate_string("The change is applied.  Press Map View to see it."),
                    type="info",
                    position="top",
                )
                return

            view_type = (self.title.split() or ["Map"])[0].lower()
            if view_type not in ("map", "diagram", "tree"):
                view_type = "map"
            await handlers.view_event(view_type)

        async def do_replace() -> None:
            """The Replace button.  Only ever applies the plan on screen.

            Re-checks that the plan matches the fields even though every field
            invalidates it: the button is the last point at which this is cheap to
            verify, and the cost of the check being wrong is a configuration changed
            in a way nobody previewed.
            """
            plan = held["plan"]
            if plan is None or held["inputs"] != current_inputs():
                ui.notify(translate_string("Press Preview first."), type="warning")
                invalidate()
                return
            if not plan.selected:
                ui.notify(translate_string("Nothing is ticked."), type="warning")
                return

            changed, errors = mapswap.apply(plan)
            for message in errors[:_REPLACE_ERROR_LIMIT]:
                ui.notify(message, type="negative")
            if changed:
                ui.notify(
                    f"{changed} {translate_string('changed')}. {translate_string('Undo is available.')}",
                    type="positive",
                )
                # The variable index this dialog holds describes the file as it was, so
                # it is dropped rather than refreshed -- rebuilding here would hand back a
                # preview of a plan that has already been applied.  The remembered ticks go
                # with it: they belong to a plan there is no longer any reason to restore.
                held.update(variables=None, variable_choices=None, plan=None, inputs=None)
                self._replace_inputs = None
                self._replace_ticks = None
                replace_button.disable()
                dialog.close()

                # Rebuilt inside the VIEW's slot, not the dialog's.  Closing the dialog
                # deletes it, and anything that resolves its client through a deleted slot
                # dies there silently -- the same re-entry, for the same reason, as
                # jump_to's.  The pulldowns are deliberately NOT refreshed: no Project,
                # Profile, Task or Scene was added or removed, so every option in them
                # still resolves.
                with self.scroll_area:
                    await rebuild_after_replace()
            else:
                ui.notify(translate_string("Nothing was changed."), type="warning")

        def save_replace() -> None:
            """Write the preview to a file, ticks and all.

            Worth having for the plan the user did NOT apply as much as the one they
            did: a hundred-row preview is a work list, and which rows they decided to
            leave does not survive closing the dialog otherwise.
            """
            plan = held["plan"]
            if plan is None:
                ui.notify(translate_string("Press Preview first."), type="warning")
                return
            file_name = mapswap.write_swap_report(mapswap.report_rows(plan))
            if file_name:
                ui.notify(f"{translate_string('Replace preview saved as')} {file_name}", type="positive")
            else:
                ui.notify(translate_string("Replace preview could not be saved."), type="negative")

        with replace_panel, ui.row().classes("w-full justify-end mt-4 gap-2"):
            ui.button(translate_string("Preview"), on_click=preview).classes("bg-blue-600 text-white px-4")
            replace_button = ui.button(translate_string("Replace"), on_click=do_replace).classes(
                "bg-orange-600 text-white px-4",
            )
            replace_button.disable()
            ui.button(translate_string("Save Preview"), on_click=save_replace).classes(
                "bg-blue-600 text-white px-4",
            )

        source_select.set_options({key: label for key, label, _count in mapswap.source_choices(index)})
        source_select.on_value_change(lambda: (fill_targets(), invalidate()))
        arg_action_select.on_value_change(lambda: (fill_arguments(), invalidate()))
        condition_select.on_value_change(lambda: (fill_condition_targets(), invalidate()))
        for widget in (
            target_select,
            swap_project,
            condition_target_select,
            condition_project,
            variable_select,
            new_name_input,
            arg_select,
            arg_match_input,
            arg_value_input,
            arg_project,
            arg_substitute,
            arg_add_missing,
        ):
            widget.on_value_change(invalidate)
        mode.on_value_change(switch_mode)

        # Come back to the Replace that was last set up, rather than to empty fields.
        #
        # Following a preview row no longer costs the preview -- the dialog docks to the
        # right edge and stays up (see find_event's dock) -- but everything else that takes
        # this dialog down still ends the same way, and the Close button is pressed between
        # a preview and the decision it leads to often enough to be worth coming back from.
        #
        # The INPUTS were what was remembered, and the plan is rebuilt from them here.
        # That is a second pass over the file, and it is worth paying every time: it makes
        # "the Replace button is only ever enabled for a preview the user is looking at"
        # true by construction rather than by this dialog remembering to enforce it.  A
        # Plan could not be remembered in its place anyway -- its Sites hold live elements,
        # and holding those across a reopen is the stale-handle case apply()'s own
        # attachment check exists to catch.
        previous = self._replace_inputs
        if previous is None:
            return False

        # Taken BEFORE a single widget is touched.  Every set_value below fires
        # on_value_change, which runs invalidate, which clears the remembered ticks --
        # so reading them afterwards would always find nothing, and the restore would
        # silently do half its job.
        remembered = self._replace_ticks

        kind = previous[0]
        mode.set_value(kind)
        switch_mode()
        if kind == "argument":
            _, action, arg_id, new_value, match, project, substitute, add_missing = previous
            arg_action_select.set_value(action or None)
            # Stocked before the argument is chosen, for the reason fill_targets is called
            # here: a select silently drops a value that is not among its options.
            fill_arguments()
            arg_select.set_value(arg_id or None)
            arg_value_input.set_value(new_value)
            arg_match_input.set_value(match)
            arg_project.set_value(project or "")
            arg_substitute.set_value(substitute)
            arg_add_missing.set_value(add_missing)
        elif kind == "action":
            _, first, second, third = previous
            source_select.set_value(first or None)
            fill_targets()
            target_select.set_value(second or None)
            swap_project.set_value(third or "")
        elif kind == "condition":
            _, first, second, third = previous
            condition_select.set_value(first or None)
            # Stocked before the target is chosen, for the reason fill_targets is called
            # here: a select silently drops a value that is not among its options.
            fill_condition_targets()
            condition_target_select.set_value(second or None)
            condition_project.set_value(third or "")
        else:
            _, first, second, third = previous
            choices = held.get("variable_choices") or []
            position = next(
                (at for at, (name, owner, _label) in enumerate(choices) if (name, owner) == (first, second)),
                None,
            )
            variable_select.set_value(position)
            new_name_input.set_value(third)

        # Only when the fields came back intact.  Re-planning is also what notices that an
        # object the old plan pointed at has been deleted since -- which is the case the
        # remembered ticks are matched by identity rather than by position to survive.
        if current_inputs() == previous:
            build_preview(remembered)
        return True

    def _dismiss_find_dialog(self) -> None:
        """Take down the Find/Replace dialog this view has up, if it still has one.

        Deleted rather than closed: a fresh dialog is built per press of Find/Replace, so
        the one being replaced has nothing left to hold, and a closed-but-undeleted dialog
        is exactly the page-growing stack the "hide" handler exists to prevent.

        A dialog whose page has gone away raises rather than answering.  That is one more
        dialog already gone, not an error to report.
        """
        dialog = self._find_dialog
        self._find_dialog = None
        if dialog is not None:
            with contextlib.suppress(Exception):
                dialog.delete()

    def find_event(self) -> None:
        """Open this view's Find dialog: ask the configuration a question, not the page.

        The faceted counterpart to search_event, and the reason both exist.  Search crawls
        the rendered text and highlights every occurrence of a string in place, which
        answers "where does this word appear" and nothing else.  This asks the loaded XML
        for objects -- Tasks that perform an action, Profiles a context triggers, anything
        naming an app or a Scene -- and answers with a list of them, each row a click away
        from the object itself.  On a configuration of 200 Projects that is the difference
        between a Map that can be read and one that can be navigated.

        The index is rebuilt every time this opens rather than cached on the view.  It is
        a single pass over the XML (60ms on an 840-Task backup, against 1.5ms for a query),
        and the configuration underneath can have been edited since the last Find -- a
        cached index would keep offering an action of a Task that has been deleted, and
        keep hiding one just added.
        """
        if not PrimeItems.tasker_root_elements["all_tasks"]:
            ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
            return

        # Whatever this view still has up goes first.  Ordinarily nothing does -- the
        # dialog opens modal, so the button that reaches here cannot be pressed while one
        # is on screen -- but a dialog that has docked itself (see dock) is not modal, and
        # building a second one over it would leave the first in the page, still holding
        # its own results list.
        self._dismiss_find_dialog()

        index = mapfind.build_index()
        # A Find run from the Diagram shows its answers in the Diagram where it can (see
        # go_to_target).  Decided here, from the view the button was pressed on, rather
        # than from whatever view happens to be frontmost when a row is clicked.
        from_diagram = self.title.startswith("Diagram")

        # `persistent`, by the rule in this file's DIALOGS & POPUPS note: a dialog that
        # holds work in progress or asks for a decision leaves on a button and nothing
        # else.  Find alone did not qualify -- a query is cheap to retype and a stray
        # click cost nothing -- but the Replace tab put both on the same card.  A preview
        # is work in progress (a hundred rows, each individually ticked or unticked, and
        # the plan is discarded with the dialog rather than remembered), and Replace is a
        # decision.  Without this, a click anywhere on the backdrop throws that away
        # silently, and the pulldowns are the worst of it: choosing from one means
        # clicking a popup that Quasar renders OUTSIDE the card, so the click that picks
        # a variable can be the click that closes the dialog.
        with ui.dialog().props("persistent") as dialog, ui.card().classes("w-[900px] max-w-full p-6") as card:
            # Whether this dialog has moved out of the middle of the screen and become a
            # panel at the right edge.  Set by the first row that is followed and never
            # unset -- once the user is going back and forth between the list and the view,
            # that is what they are doing until they close it.
            docked = {"yes": False}

            def dock() -> None:
                """Get this dialog out of the view's way instead of taking it down.

                What following one of the rows does now.  It used to close the dialog, and
                had to: a modal dialog sits in the middle of the screen with a backdrop over
                the rest, so the jump behind it scrolled a view the user could not see.  The
                cost was paid on the Replace tab above all -- going to look at one of forty
                places about to change meant pressing Find/Replace again, for every one of
                them, to get the preview back.

                `seamless` is what makes closing unnecessary: it drops the backdrop and the
                body-scroll lock, so the view behind is visible, scrollable and clickable
                while this stays up.  `position=right` pins the dialog to the edge and out
                of the column the Map is read down.  Both are Quasar props on the dialog as
                it stands and both are reactive, so it moves without being rebuilt -- which
                is the point: rebuilding it is what would throw away the preview, the tick
                boxes and the query this exists to keep.
                """
                if docked["yes"]:
                    return
                docked["yes"] = True
                dialog.props(add="seamless position=right")
                # Narrower than the 900px it opens at, because it is now sharing the screen
                # with the view it just sent the user to, and being able to read that view
                # is the whole reason it moved.
                card.classes(remove="w-[900px] p-6", add="w-[620px] p-4")

            ui.label(
                f"{translate_string('Find in')} {self.title}",
            ).classes("text-lg font-bold text-blue-600")

            # Both tabs read and write only what the app is displaying, so the dialog says
            # which that is.  Stated up front rather than left to be inferred from a short
            # answer: "no matches" and "no matches in this one Task" look identical, and
            # the second is the one that sends somebody looking for a bug.
            if not index.scope.is_everything:
                ui.label(
                    f"{translate_string('Limited to')} {index.scope.phrase} "
                    f"-- {translate_string('clear the single-item selection to reach the whole configuration')}.",
                ).classes(
                    "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1 mb-1",
                )
            # Find and Replace share this dialog, and share the index behind it.  Two
            # reasons beyond tidiness, both in find_event's own terms: the index is
            # rebuilt per open rather than cached (see above) and a separate Replace
            # dialog would pay that a second time, or worse, hold one from before an
            # edit; and the natural move is to look for something, see the 37 places it
            # is, and then decide to change them -- which is a tab switch rather than a
            # second window and a re-entered query.
            with ui.tabs().classes("w-full") as tabs:
                find_tab = ui.tab(translate_string("Find"))
                replace_tab = ui.tab(translate_string("Replace"))
            with ui.tab_panels(tabs, value=find_tab).classes("w-full"):
                find_panel = ui.tab_panel(find_tab)
                replace_panel = ui.tab_panel(replace_tab)

            with find_panel:
                ui.label(
                    translate_string(
                        "Each box narrows the answer, and they combine: a trigger and an action together "
                        "find the Profiles that trigger that way AND run a Task that does that. Every entry "
                        "offered is one this configuration actually uses, and the number beside it is how "
                        "many places carry it.",
                    ),
                ).classes("text-xs text-gray-500 italic mb-3")

                pickers = {}
                with ui.row().classes("w-full items-center gap-2"):
                    for facet in mapfind.FACETS:
                        choices = index.choices(facet)
                        pickers[facet] = (
                            ui
                            .select(
                                {choice.value: choice.label for choice in choices},
                                label=translate_string(mapfind.FACET_LABELS[facet]),
                                with_input=True,
                                clearable=True,
                            )
                            .classes("flex-1 min-w-[180px]")
                            .props("dense")
                        )

                with ui.row().classes("w-full items-center gap-2 mt-2"):
                    text_input = (
                        ui
                        .input(label=translate_string("Text (name, label or argument)"))
                        .classes("flex-1")
                        .props("dense clearable")
                    )
                    # Hidden when a single Project/Profile/Task/Scene is selected, because the
                    # scope has already done the narrowing and this can then only mislead.
                    # "Every Project" is the option that goes wrong: with one Task selected it
                    # is the ONLY entry and means that Task, and with one Project selected it
                    # and that Project's own entry mean the same thing.  Either way the label
                    # promises the whole configuration and delivers a corner of it.  Left at ""
                    # rather than removed, so the query still reads a value and no code below
                    # has to care whether the widget is on screen.
                    project_select = (
                        ui
                        .select(
                            {"": translate_string("Every Project")} | {name: name for name in index.projects},
                            value="",
                            label=translate_string("Narrow to Project"),
                            with_input=True,
                        )
                        .classes("w-64")
                        .props("dense")
                    )
                    project_select.set_visibility(index.scope.is_everything)

                summary = ui.label("").classes("text-sm font-bold mt-3")
                results_area = ui.scroll_area().classes(
                    "w-full h-[45vh] border p-2 bg-gray-50 dark:bg-gray-900 rounded",
                )
                # What the last Find produced, so "Save Results" writes exactly the list on
                # screen rather than re-running a query the user may have edited since.
                produced: dict = {"query": None, "hits": [], "total": 0}

                def jump_to(target: mapjump.Target) -> Callable[[], Coroutine]:
                    """One result row's click: dock the list to the right, then go to the object.

                    Docked rather than closed (see dock), so the list the row came from is
                    still there when the user has finished looking -- which is what a Find
                    and a Replace preview are both for: a list of places, walked one at a
                    time.  Shared by both tabs, and the reason the Replace half is handed
                    this rather than writing its own.

                    The jump runs inside the VIEW's slot rather than the dialog's, which is
                    not decoration: everything it does afterwards -- ui.notify above all --
                    resolves its client through whatever slot is active, and the dialog's
                    goes away with the dialog.  Left in the dialog's, the first notification
                    raised "The parent element this slot belongs to has been deleted" from
                    inside NiceGUI and the jump died there, silently.  It survives a docked
                    dialog, which is not deleted, but it did not survive the close this used
                    to do and would not survive the Close button landing mid-jump either.
                    The same re-entry, for the same reason, as
                    _enable_connector_highlighting's.
                    """

                    async def go() -> None:
                        dock()
                        with self.scroll_area:
                            await go_to_target(self.master_gui, target, prefer_diagram=from_diagram)

                    return go

                def show(query: mapfind.Query) -> None:
                    """Run the query and draw its answer."""
                    self._find_query = query
                    produced.update(query=query, hits=[], total=0)
                    results_area.clear()
                    if query.is_empty:
                        summary.set_text("")
                        ui.notify(
                            translate_string("Choose an action, a trigger, an app, a Scene or some text."),
                            type="warning",
                        )
                        return

                    hits, total = mapfind.run_query(index, query)
                    produced.update(hits=hits, total=total)
                    summary.set_text(
                        (
                            f"{len(hits)} {translate_string('of')} {total} {translate_string('found for')}: {query.phrase()}"
                            if total > len(hits)
                            else f"{total} {translate_string('found for')}: {query.phrase()}"
                        ),
                    )

                    with results_area, ui.column().classes("w-full gap-1"):
                        if not hits:
                            ui.label(
                                translate_string("Nothing in the loaded configuration answers this."),
                            ).classes("text-sm text-gray-500 italic")
                            return
                        project = None
                        for hit in hits:
                            if hit.project != project:
                                project = hit.project
                                ui.label(
                                    (
                                        f"{translate_string('Project')} '{project}'"
                                        if project
                                        else translate_string("In no Project")
                                    ),
                                ).classes("text-xs font-bold text-orange-500 mt-2")
                            with ui.row().classes(
                                "w-full items-baseline py-1 border-b dark:border-gray-700 hover:bg-blue-50 "
                                "dark:hover:bg-blue-950 px-2 rounded transition-colors",
                            ):
                                # Two handlers on the one click, and the browser-side one
                                # is not decoration: it raises the Map view the jump is
                                # about to land in, which a browser only permits while the
                                # click's user activation is still alive -- and it has
                                # lapsed by the time jump_to runs (see
                                # mapjump.raise_map_window_js).  It ends in emit(), which
                                # is what carries the click on to jump_to.
                                ui.link(hit.where, "#").on(
                                    "click",
                                    jump_to(hit.target),
                                    js_handler=mapjump.find_result_click_js(
                                        mapjump.diagram_anchor(hit.target) if from_diagram else "",
                                    ),
                                ).classes(
                                    "text-blue-600 dark:text-blue-400 font-mono text-sm shrink-0 "
                                    "decoration-dotted hover:underline",
                                )
                                if hit.detail:
                                    ui.label(hit.detail).classes("text-xs text-gray-500 dark:text-gray-400 truncate")

                def run() -> None:
                    """The Find button: build the query out of the widgets and answer it."""
                    show(
                        mapfind.Query(
                            action=pickers[mapfind.ACTION].value or "",
                            trigger=pickers[mapfind.TRIGGER].value or "",
                            app=pickers[mapfind.APP].value or "",
                            scene=pickers[mapfind.SCENE_FACET].value or "",
                            text=text_input.value or "",
                            project=project_select.value or "",
                        ),
                    )

                def save() -> None:
                    """Write the list on screen to a file, as the other reports do.

                    The same Rows the results list is drawn from, so the file and the screen
                    cannot disagree -- and every location line in it stays clickable if the
                    saved report is ever opened in the Misc view.
                    """
                    query = produced["query"]
                    if query is None:
                        ui.notify(translate_string("Run a Find first."), type="warning")
                        return
                    rows = mapfind.report_rows(query, produced["hits"], produced["total"], index)
                    file_name = mapfind.write_find_report(rows)
                    if file_name:
                        ui.notify(f"{translate_string('Find results saved as')} {file_name}", type="positive")
                    else:
                        ui.notify(translate_string("Find results could not be saved."), type="negative")

                with ui.row().classes("w-full justify-end mt-4 gap-2"):
                    ui.button(translate_string("Find"), on_click=run).classes("bg-blue-600 text-white px-4")
                    ui.button(translate_string("Save Results"), on_click=save).classes(
                        "bg-blue-600 text-white px-4",
                    )

            # The Replace tab is built by its own method rather than inline.  It is the
            # larger half of this dialog and shares only the index, the panel and the jump
            # with the Find half -- which is exactly the seam, so that is where it is cut.
            restored_replace = self._build_replace_tab(dialog, index, jump_to, replace_panel)

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button(translate_string("Close"), on_click=dialog.close).classes("bg-red-500 text-white px-4")

            # A fresh dialog is built per press, so the one being replaced is disposed of
            # rather than left in the page: this is a control the user reaches for over and
            # over while narrowing a search, and a stack of dead dialogs (each holding a
            # results list of up to 500 rows) is a page that grows all afternoon.
            #
            # The view is told as well, so that _dismiss_find_dialog does not later go
            # looking for one that has already taken itself down.  A dialog that docks
            # itself never gets here at all -- it is still open, and the view's handle on
            # it is what the next press disposes of.
            def dispose() -> None:
                """Forget this dialog and take it out of the page."""
                if self._find_dialog is dialog:
                    self._find_dialog = None
                dialog.delete()

            dialog.on("hide", dispose)

            # Come back to the question that was last asked, rather than to a blank dialog.
            # A result row's click no longer costs the list -- the dialog docks instead of
            # closing (see dock) -- but the Close button does, and the next press of Find is
            # nearly always the same query with one more row to look at.
            # Whichever half the user was last using is the one to open on.
            if restored_replace:
                tabs.set_value(replace_tab)

            previous = self._find_query
            if previous is not None:
                pickers[mapfind.ACTION].set_value(previous.action or None)
                pickers[mapfind.TRIGGER].set_value(previous.trigger or None)
                pickers[mapfind.APP].set_value(previous.app or None)
                pickers[mapfind.SCENE_FACET].set_value(previous.scene or None)
                text_input.set_value(previous.text)
                project_select.set_value(previous.project)
                show(previous)

        # Held on the view for as long as it is on screen: this one may outlive the click
        # that dismissed it in every previous version -- a docked dialog stays up until the
        # user closes it -- and the next press of Find/Replace has to be able to find it.
        self._find_dialog = dialog
        dialog.open()

    def extract_first_font_name(self: MyGui, text: str) -> str:
        """
        Scans the given text to identify and return the font name
        following the very first 'font-family:' rule declaration.
        """
        # Regex Breakdown:
        # font-family\s*:\s* -> Matches 'font-family', optional spaces, a colon, and optional spaces
        # ([^,;{}]+)         -> Capture Group 1: the first family in the list, i.e. everything
        #                       up to the comma that starts the fallback stack, or to the end
        #                       of the declaration when there is no fallback
        #
        # The comma has to end the capture rather than be excluded from it.  Every
        # font-family MapTasker writes carries a fallback -- addcss.py emits
        # "font-family:<font>, monospace;" and the view styles below build the same shape --
        # so a pattern that had to reach a ';' or '}' without crossing a comma matched none
        # of them.  This returned "Font name not found" for all real output, and the caller
        # fell back to program_arguments["font"] every single time: exactly the stale-font
        # behaviour that reading the font back out of the file is meant to avoid.
        pattern = re.compile(r"font-family\s*:\s*([^,;{}]+)")

        match = pattern.search(text)

        if match:
            # Return the captured font name, stripping off any outer quotes or accidental whitespace
            return match.group(1).strip().strip("'\"")

        return "Font name not found"

    def _process_fallback_data(self: MyGui, the_data: dict | list) -> None:
        """Fallback logic to assemble HTML content strings when the source file is missing."""
        html_builder = []
        in_style_block = False
        style_buffer = []

        def is_css_line(text: str) -> bool:
            """Helper function to determine if a stray line is actually a CSS rule."""
            clean = text.strip()
            if clean.startswith((".", "#", "}", "{")):
                return True
            return bool(":" in clean and (clean.endswith(";") or "/*" in clean or "*/" in clean))

        def escape_text_except_html(text: str) -> str:
            """Escapes < and > but preserves intended HTML tags like tables and links."""

            parts = re.split(r"(<[^>]+>)", text)

            allowed_tags = {
                "a",
                "table",
                "tr",
                "td",
                "th",
                "tbody",
                "thead",
                "div",
                "span",
                "br",
                "style",
                "b",
                "i",
                "u",
                "strong",
                "em",
                "hr",
                "!doctype",
                "html",
                "head",
                "meta",
                "title",
                "body",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "ul",
                "ol",
                "li",
                # Everything format.py can put in a TaskerNet description or Task label needs
                # to be in this list, or it is escaped and shown as its own markup instead of
                # being rendered.  "img" is the one that shows: a description's picture came
                # out as the literal text of its <img> tag and no image at all.
                "img",
                "figure",
                "figcaption",
                "big",
                "small",
                "code",
                "pre",
                "blockquote",
                "font",
                "mark",
                "sub",
                "sup",
            }

            for i in range(len(parts)):
                if i % 2 == 0:
                    parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
                else:
                    tag_name_match = re.match(r"^</?([!a-zA-Z0-9]+)", parts[i])
                    if tag_name_match and tag_name_match.group(1).lower() in allowed_tags:
                        pass
                    else:
                        parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
            return "".join(parts)

        # --- 2. FALLBACK DICTIONARY PROCESSING (Legacy Map View) ---
        if self.is_map:
            for _num, (_linenum, value) in enumerate(the_data.items()):
                text_list = value.get("text", [])
                color_list = value.get("color", [])
                full_line_text = "".join(str(t) for t in text_list)

                if "<style>" in full_line_text:
                    in_style_block = True

                if in_style_block:
                    clean_line = full_line_text.replace("<style>", "").replace("</style>", "").replace('"""', "")
                    style_buffer.append(clean_line)
                    if "</style>" in full_line_text:
                        in_style_block = False
                        html_builder.append(f"<style>{''.join(style_buffer)}</style>")
                        style_buffer = []
                elif is_css_line(full_line_text):
                    html_builder.append(f"<style>{full_line_text}</style>")
                else:
                    line_html = "<div>"
                    for t_idx, text_segment in enumerate(text_list):
                        if '"""' in str(text_segment):
                            text_segment = str(text_segment).replace('"""', "")  # noqa: PLW2901
                        safe_text = escape_text_except_html(str(text_segment))
                        color = color_list[t_idx] if t_idx < len(color_list) else "inherit"
                        line_html += f"<span style='color: {color};'>{safe_text}</span>"
                    line_html = line_html.rstrip("\r\n")
                    html_builder.append(line_html + "</div>")

        # --- 3. FALLBACK LIST DATA PROCESSING (Other Views) ---
        else:
            for line in the_data:
                if line.strip() == "":
                    html_builder.append("<div>&nbsp;</div>")
                    continue
                if "<br><br>" in line:
                    line = line.replace("<br><br>", "")  # noqa: PLW2901
                if '"""' in line:
                    if line in {"<div>  </tr>\n</div>", "<div>\n</div>"}:
                        continue
                    line = line.replace('"""', "")  # noqa: PLW2901

                if "<style>" in line:
                    in_style_block = True

                if in_style_block:
                    clean_line = line.replace("<style>", "").replace("</style>", "")
                    style_buffer.append(clean_line)
                    if "</style>" in line:
                        in_style_block = False
                        html_builder.append(f"<style>{''.join(style_buffer)}</style>")
                        style_buffer = []
                elif is_css_line(line):
                    html_builder.append(f"<style>{line}</style>")
                else:
                    clean_text_line = line.rstrip("\r\n")
                    safe_line = escape_text_except_html(clean_text_line)
                    html_builder.append(f"<div>{safe_line}</div>")

        # --- 4. COMPRESS MULTIPLE BLANK LINES FOR FALLBACK DATA ---
        final_html = "".join(html_builder)
        empty_div_pattern = r"(<div>(?:\s|&nbsp;|<span[^>]*>(?:\s|&nbsp;)*</span>)*</div>\s*){2,}"
        final_html = re.sub(empty_div_pattern, "", final_html)
        final_html = re.sub(r"\n{3,}", "\n", final_html)
        final_html = re.sub(r"(<br\s*/?>\s*){2,}", "<br>", final_html)

        self.html_display.content = final_html

    def scroll(self, direction: str) -> None:
        """Manages the scroll position of the view's content area based on the specified direction ('top' or 'bottom').

        Also resets horizontal scroll back to column 1, since the view may have been scrolled
        sideways (e.g. via the search feature or a wide diagram) before Top/Bottom is clicked.
        """
        # Reset horizontal scroll back to the leftmost column regardless of direction.
        self.scroll_area.scroll_to(percent=0.0, axis="horizontal")
        if direction == "top":
            # Native NiceGUI scroll to top (0% progress)
            self.scroll_area.scroll_to(percent=0.0)
        else:
            self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """Scroll the view all the way down, with the last line actually on screen.

        scroll_to(percent=1.0) hands Quasar a percentage of the scroll size it currently knows
        about -- and while the chunks process_data() streamed in are still being skipped by
        "content-visibility: auto", that size is the sum of their *estimated* heights
        (contain-intrinsic-size), not their real ones. The estimate runs short on the last chunk,
        so "100%" stopped a line or so above the true end of the content.

        Setting scrollTop past the end instead lets the browser clamp it to the real maximum,
        and doing that again over the next few frames picks up the correction as the chunks
        being scrolled into view get laid out for real and the scroll height grows.
        """
        ui.run_javascript(f"""
            const outerContainer = document.getElementById("c{self.scroll_area.id}");
            if (!outerContainer) return;
            const scroller = outerContainer.querySelector(".q-scrollarea__container") || outerContainer;
            let attempts = 0;
            const toBottom = () => {{
                // Deliberately past the end: the browser clamps this to scrollHeight minus the
                // visible height, which is exactly the bottom, without having to measure either.
                scroller.scrollTop = scroller.scrollHeight;
                // Eight frames is ~130ms at 60fps -- long enough for the last chunks to render
                // and settle, short enough to still read as an instant jump.
                if (++attempts < 8) {{
                    requestAnimationFrame(toBottom);
                }}
            }};
            toBottom();
        """)

    def toggle_wrap(self) -> None:
        """Toggles word-wrap on/off for this view's content, replacing the exact prior classes."""
        self.wrap_enabled = not self.wrap_enabled
        new_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"
        self.scroll_area.classes(remove=self.wrap_classes, add=new_classes)
        self.wrap_classes = new_classes
        ui.notify(f"Word wrap {'enabled' if self.wrap_enabled else 'disabled'} for {self.title}.", type="info")

    def _profiles_per_line_selected(self, event: object) -> None:
        """Fires when the Diagram view's 'Profiles Per Line' pulldown selection changes."""
        new_value = int(event.value if hasattr(event, "value") else event)
        if new_value != self.master_gui.profiles_per_line:
            asyncio.create_task(self.master_gui.event_handlers.profiles_per_line_event(new_value))  # noqa: RUF006

    def reload_diagram(self) -> None:
        """Clears and re-streams the Diagram view's content in place after it has been
        regenerated (e.g. after the 'Profiles Per Line' pulldown changes the diagram's layout).
        """
        # The content this view's cached search index and results were built against is about
        # to be thrown away; process_data() issues a new token once the replacement is fully
        # streamed in. Until then nothing about the old content may be reused.
        self._content_token = 0
        self._last_search = None
        self.scroll_area.clear()
        self._task = asyncio.create_task(self.process_data([]))


# ==========================================
# 4. INITIALIZATION & LAYOUT
# ==========================================
def initialize_gui(self: MyGui) -> None:
    """Initialize state variables. 'self' is the MyGui instance."""
    _initialize_gui_settings(self)
    _initialize_ai_settings(self)
    _initialize_android_settings(self)
    _initialize_display_settings(self)
    _initialize_feature_flags(self)
    _initialize_data_structures(self)
    _initialize_runtime_options(self)


def _initialize_gui_settings(self: MyGui) -> None:
    """Initializes GUI-related appearance and display settings."""
    PrimeItems.program_arguments["gui"] = True
    self.gui = True
    self.guiview = False
    self.appearance_mode = None
    # What the "Dark Mode" switch will be showing when the window opens (see STARTUP_DARK_MODE).
    # Kept in step with it here so a view rendered before the switch is ever clicked colours
    # itself the way the rest of the window is already painted.
    self.dark_mode = STARTUP_DARK_MODE
    self.default_font = ""
    self.font = None
    self.bold = None
    self.italicize = None
    self.underline = None
    self.highlight = None
    self.color_lookup = None
    self.twisty = None
    self.indent = None
    self.display_detail_level = None
    self.everything = None
    self.view_limit = VIEW_LIMIT_DEFAULT
    self.notify_timeout = NOTIFY_TIMEOUT_DEFAULT
    self.profiles_per_line = DIAGRAM_PROFILES_PER_LINE
    self.pretty = False
    self.task_action_warning_limit = 20
    self.language = "English"
    self.initialization = True
    self.textview = False
    # Every rendered view still open, newest last -- see register_view().
    self.textviews = []


def _initialize_ai_settings(self: MyGui) -> None:
    """Initializes AI-related variables."""
    self.ai_analysis = None
    self.ai_analysis_window = None
    self.ai_apikey = None
    self.ai_apikey_window = None
    self.ai_model = ""
    self.ai_name = ""
    self.ai_model_extended_list = False
    self.displaying_extended_list = None
    self.ai_prompt = None


def _initialize_android_settings(self: MyGui) -> None:
    """Initializes Android device connection settings."""
    self.android_file = ""
    self.android_ipaddr = ""
    self.android_port = ""
    self.fetched_backup_from_android = False
    self.android_auth_key = ""  # Cached Tasker HTTP API key for Save To Android (see save_task_to_android_event).
    self.android_auth_key_ipaddr = ""
    self.android_auth_key_port = ""


def _initialize_display_settings(self: MyGui) -> None:
    """Initializes settings related to how data is displayed."""
    self.doing_diagram = False
    self.diagramview_window = None
    self.map_in_progress = False
    self.mapview_window = None
    self.miscview_window = None
    self.treeview_window = None
    self.video_window = None
    self.outline = False
    self.font_table = {}


def _initialize_feature_flags(self: MyGui) -> None:
    """Initializes boolean flags for various features and states."""
    self.extract_in_progress = False
    self.first_time = True
    self.list_files = False
    self.list_unnamed_items = False
    self.reset_debug_at_end = False
    self.restore = False
    self.runtime = False
    self.save = False
    self.close_tabs_on_exit = False
    self.open_view_in_new_window = False


def _initialize_data_structures(self: MyGui) -> None:
    """Initializes data structures used by the application."""
    self.conditions = None  # Consider if this should be initialized to a dict or list
    self.named_item = None  # Consider if this should be initialized to a specific type
    self.single_profile_name = None
    self.single_project_name = None
    self.single_scene_name = None
    self.single_task_name = None
    self.tab_to_use = None  # Consider if this should be initialized to a default tab


def _initialize_runtime_options(self: MyGui) -> None:
    """Initializes variables related to runtime actions and program flow."""
    self.debug = None
    self.exit = None
    self.file = None  # Consider if this should be initialized to an empty string or specific file object
    self.preferences = None
    self.rerun = None
    self.reset = None
    self.taskernet = None


# =========================================================================
# Initialize the GUI screen layout using NiceGUI with split sidebars and main content area.
# =========================================================================
def document_language_html() -> str:
    """Head markup declaring the GUI's language and asking the browser not to translate it.

    Without a lang attribute the browser sniffs the text instead.  With the GUI set to
    German, Chrome detects German, sees a browser configured for English, and helpfully
    translates the entire UI back to English -- undoing every translation MapTasker just
    applied.  That is indistinguishable, on screen, from the translations having failed.

    So state the language outright, and mark the UI as not-to-be-translated: the user
    already chose their language in the sidebar, and that choice should win over the
    browser's guess.  'translate="no"', the notranslate class and the google meta tag are
    all listed because browsers vary in which one they honour.

    Note the lang code is baked in when the page is built.  A language switched at runtime
    rebuilds the layout but not the document, so language_set_event() updates the live
    attributes itself -- see set_document_language_js().
    """
    lang_code = PrimeItems.languages.get(PrimeItems.program_arguments.get("language") or "English", "en")
    return f'<meta name="google" content="notranslate"><script>{set_document_language_js(lang_code)}</script>'


def set_document_language_js(lang_code: str) -> str:
    """The JavaScript that stamps a language onto the live document.

    Shared by the initial page build and the runtime language switch so the two can never
    drift apart.  The lang code comes from PrimeItems.languages, so it is always one of our
    own short ISO codes -- never user text -- and is safe to interpolate.
    """
    return (
        f'document.documentElement.lang = "{lang_code}";'
        'document.documentElement.setAttribute("translate", "no");'
        'document.documentElement.classList.add("notranslate");'
    )


def inject_shared_head_styles() -> None:
    """Injects the CSS shared by every page of the app (scrollbar theming, light-mode overrides,
    Map/Diagram/Tree table layout, and the Diagram view's click-to-highlight connector styling),
    plus the document's language declaration (see document_language_html).

    ui.add_head_html() only affects the page it's called from -- each NiceGUI @ui.page is its own
    independent document. Call this from every page function (the main window's initialize_screen()
    and the "/popout/{view_type}" route in rungui.py), or a popped-out window renders Diagram
    connectors that respond to clicks (the JS wiring is unaffected) but never visibly highlight,
    since the .connector-highlight rule defined here would simply be missing from that page.
    """
    # Every page needs this for the same reason it needs the CSS below: each @ui.page is its
    # own document, so a popped-out Map/Diagram window would otherwise be left for the
    # browser to sniff and translate on its own.
    ui.add_head_html(document_language_html())

    ui.add_head_html("""
        <style>
            /* Force scrollbar tracks to be visible on our target components */
            .force-scrollbar,
            .force-scrollbar .q-drawer__content {
                overflow-y: scroll !important;
                overflow-x: auto !important;
            }

            /* =========================================================================
               NATIVE BROWSER SCROLLBARS (WebKit: Chrome, Safari, Edge) - LIGHT MODE CONTRAST
               ========================================================================= */
            .force-scrollbar::-webkit-scrollbar,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar {
                display: block !important;
                width: 10px !important;
                height: 10px !important;
            }
            .force-scrollbar::-webkit-scrollbar-track,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.08) !important;
                border-radius: 4px !important;
            }
            .force-scrollbar::-webkit-scrollbar-thumb,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb {
                background: #475569 !important;
                border-radius: 4px !important;
                border: 1px solid #ffffff !important;
            }
            .force-scrollbar::-webkit-scrollbar-thumb:hover,
            .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb:hover {
                background: #1e293b !important;
            }

            /* =========================================================================
               QUASAR SCROLL AREA COMPONENT (NiceGUI ui.scroll_area) - LIGHT MODE CONTRAST
               ========================================================================= */
            .q-scrollarea__thumb--v,
            .q-scrollarea__thumb--h {
                background: #475569 !important;
                opacity: 0.95 !important;
                border: 1px solid #ffffff !important;
            }

            .q-scrollarea__thumb--v:hover,
            .q-scrollarea__thumb--h:hover {
                background: #1e293b !important;
                opacity: 1 !important;
            }

            /* =========================================================================
               DARK MODE HIGH-CONTRAST OVERRIDES (Crisp Silver/White on Dark Backgrounds)

               "body.body--dark" is how dark mode is actually marked in the DOM: NiceGUI's
               ui.dark_mode() drives Quasar's dark plugin, which sets body--dark/body--light
               on <body>, and NiceGUI wires Tailwind's own "dark:" variant to that same class.
               Nothing ever puts a "dark" class on <html> -- so the ".dark ..." selectors these
               rules used to carry never matched anything, and the "html:not(.dark) ..." ones
               further down matched in BOTH modes, forcing white onto cards and scroll areas
               even in dark mode. Everything else survived that only because apply_appearance_mode()
               writes inline "!important" styles over it (an inline important declaration
               outranks a stylesheet one); the Tree view's card and scroll area get no such
               inline styles, which is exactly why that one container stayed white.
               ========================================================================= */
            body.body--dark .force-scrollbar::-webkit-scrollbar-track,
            body.body--dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.1) !important;
            }
            body.body--dark .force-scrollbar::-webkit-scrollbar-thumb,
            body.body--dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb,
            body.body--dark .q-scrollarea__thumb--v,
            body.body--dark .q-scrollarea__thumb--h {
                background: #e2e8f0 !important;
                border: 1px solid #1e293b !important;
                opacity: 0.95 !important;
            }
            body.body--dark .force-scrollbar::-webkit-scrollbar-thumb:hover,
            body.body--dark .force-scrollbar .q-drawer__content::-webkit-scrollbar-thumb:hover,
            body.body--dark .q-scrollarea__thumb--v:hover,
            body.body--dark .q-scrollarea__thumb--h:hover {
                background: #ffffff !important;
                opacity: 1 !important;
            }

            /* Firefox Engine Fallback High-Contrast */
            .force-scrollbar,
            .force-scrollbar .q-drawer__content {
                scrollbar-width: auto !important;
                scrollbar-color: #475569 rgba(0, 0, 0, 0.08) !important;
            }
            body.body--dark .force-scrollbar,
            body.body--dark .force-scrollbar .q-drawer__content {
                scrollbar-color: #e2e8f0 rgba(255, 255, 255, 0.1) !important;
            }

            /* =========================================================================
               TARGETED LIGHT MODE OVERRIDES (Completely bypasses macOS System preferences)

               Scoped to "body:not(.body--dark)" -- see the note above on why the old
               "html:not(.dark)" scope leaked these white backgrounds into dark mode.
               ========================================================================= */
            body:not(.body--dark),
            body:not(.body--dark) .q-layout,
            body:not(.body--dark) .q-page-container,
            body:not(.body--dark) main,
            body:not(.body--dark) .q-drawer,
            body:not(.body--dark) .q-tab-panels,
            body:not(.body--dark) .q-tab-panel,
            body:not(.body--dark) .q-card,
            body:not(.body--dark) .q-tabs,
            body:not(.body--dark) .q-scrollarea,
            body:not(.body--dark) .q-scroll-area,
            body:not(.body--dark) .q-textview,
            body:not(.body--dark) .q-content-container,
            body:not(.body--dark) .q-container-context,
            body:not(.body--dark) div.nicegui-content {
                background-color: #ffffff !important;
                color: #000000 !important;
            }

            /* =========================================================================
               CRITICAL FIX: FORCE TOOLBAR ROWS WHITE IN LIGHT MODE
               ========================================================================= */
            body:not(.body--dark) .bg-gray-200,
            body:not(.body--dark) .dark\\:bg-gray-800,
            body:not(.body--dark) .gap-4.mb-6 {
                background-color: #ffffff !important;
                color: #000000 !important;
            }

            /* =========================================================================
               TREE VIEW: LABELS TAKE THEIR COLOUR FROM THE CARD

               NiceGuiTreeView.apply_theme() puts the current mode's foreground colour on
               the card as an inline style; Quasar otherwise colours the node rows from its
               own theme, which is how the labels could end up light-on-light (or dark-on-
               dark) if its idea of the mode ever disagrees with the switch's.  Inheriting
               keeps the two in step no matter which way that disagreement goes.
               ========================================================================= */
            .maptasker-tree-card .q-tree,
            .maptasker-tree-card .q-tree * {
                color: inherit !important;
            }

            /* =========================================================================
               GLOBAL TOOLTIP FONT SIZE ADJUSTMENT
               ========================================================================= */
            .q-tooltip {
                font-size: 14px !important;
                line-height: 1.4 !important;
            }

            /* =========================================================================
               MAP/DIAGRAM/TREE VIEW: KEEP THE GENERATED DIRECTORY TABLES WITHIN THE
               SCROLL AREA. The exported HTML sizes table columns to fit their widest
               unbroken cell (Task/Profile names are often one long unbroken word), which
               is fine in a full-width standalone browser tab but overflows this narrow
               embedded box. Force fixed column widths and let long names wrap instead.
               (Set here rather than injected per-render, since ui.html() sanitizes
               dynamic content client-side via DOMPurify and strips <style> tags.)
               ========================================================================= */
            .q-scrollarea table {
                table-layout: fixed !important;
                width: 100% !important;
            }
            .q-scrollarea table td,
            .q-scrollarea table th {
                overflow-wrap: anywhere !important;
                word-break: break-word !important;
                white-space: normal !important;
            }
            /* <pre> forces its own white-space:pre in the UA stylesheet, which wins over the
               inherited whitespace-pre-wrap Tailwind class on the scroll area itself (e.g. the
               AI-analysis prompt text embedded in the exported HTML). Force it to wrap too. */
            .q-scrollarea pre {
                white-space: pre-wrap !important;
                overflow-wrap: anywhere !important;
                word-break: break-word !important;
            }
            /* Quasar's own QScrollArea stylesheet gives its internal content wrapper
               (".q-scrollarea__content", not directly reachable via ui.scroll_area().classes())
               "min-width: 100%" but no max-width -- so any wide-enough descendant (a table
               whose fixed-width rule above is only 100% of THIS already-oversized box, a long
               line that slips past a narrower fix, etc.) is free to stretch it past the visible
               area. Quasar then just lets you scroll to it horizontally instead of clipping,
               which is indistinguishable from "wrap isn't working". Cap it at 100% -- but only
               while word wrap is on (the "whitespace-pre-wrap" Tailwind class toggled by Toggle
               Wrap lives on the very same .q-scrollarea element, so it doubles as the switch
               here): wrap-off views (Diagram's ASCII art by default) still need to grow past the
               viewport and rely on that same horizontal scrollbar on purpose. */
            .q-scrollarea.whitespace-pre-wrap .q-scrollarea__content {
                max-width: 100% !important;
            }

            /* =========================================================================
               DIAGRAM VIEW: CLICK-TO-HIGHLIGHT CONNECTOR LINES
               ========================================================================= */
            .connector {
                cursor: pointer;
            }
            .connector-highlight {
                background-color: #facc15 !important;
                color: #000000 !important;
                font-weight: bold;
            }
            .connector-jump-button {
                display: none;
                position: fixed;
                z-index: 1000;
                padding: 8px 14px;
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 0.875rem;
                font-weight: 600;
                cursor: pointer;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
            }
            .connector-jump-button:hover {
                background-color: #1d4ed8;
            }

            /* =========================================================================
               DIAGRAM VIEW: THE INTERACTIVE LAYER (see diagintr.py)
               =========================================================================
               The rule everything here obeys: not one of these may change the width of a
               character or the position of a column.  The diagram's boxes and the
               connectors joining them were laid out against each other in Python, so a
               highlight with padding, a fold arrow taking up a column, or a zoom that
               scaled anything but the font would pull the drawing apart. */

            /* Each line is its own element so that folding can take it away.  A block,
               because the browser then breaks between lines by itself -- the newline is
               still in the text (the search index and the jump into the Diagram both count
               lines by counting newlines) but is never displayed, or the diagram would come
               out double-spaced. */
            .mt-dline {
                display: block;
            }
            .mt-dnl {
                display: none;
            }
            .mt-dline.mt-hidden {
                display: none;
            }

            /* The fold arrow for a Project, drawn in the margin: absolutely positioned, so
               it occupies no column, and pulled left into the scroll area's own padding. */
            .mt-dline[data-fold] {
                cursor: pointer;
                /* So the arrow below is positioned against THIS line and nothing else.  Left
                   to find its own containing block it would take whichever ancestor happens
                   to be positioned -- Quasar's scroll content here, the page there -- and
                   land somewhere different in each. */
                position: relative;
            }
            .mt-dline[data-fold]::before {
                /* The character itself, not a CSS "\\25be" escape: this block is an ordinary
                   Python string, in which a backslash and two digits is an OCTAL escape --
                   so the escape never reached the browser, and what did was U+0015 followed
                   by a literal "be" sitting in the margin of every Project. */
                content: "▾";
                /* Out of flow, so it occupies no column: it sits over the five blanks a
                   Project box is always indented by (diagutil.print_box), which is the only
                   place on the line that is guaranteed to be empty.  At a fixed size for the
                   same reason -- a control is not part of the drawing, and one measured in em
                   would grow with the zoom until it covered the box it belongs to. */
                position: absolute;
                font-size: 12px;
                opacity: 0.55;
                font-weight: bold;
            }
            .mt-dline[data-fold][data-fold-state="closed"]::before {
                content: "▸";
                opacity: 1;
                color: #f97316;
            }
            .mt-dline[data-fold]:hover::before {
                opacity: 1;
            }

            /* A clickable object name.  An underline on hover rather than a box: an outline
               would be drawn outside the character cell and overlap the box wall next to
               it, which reads as the diagram having moved. */
            .mt-dnode {
                cursor: pointer;
            }
            .mt-dnode:hover,
            .mt-dnode:focus-visible {
                text-decoration: underline;
                text-underline-offset: 2px;
                outline: none;
            }

            /* Following one chain of calls: the Tasks in it and the arrows between them
               stay lit, and the rest of the diagram is greyed rather than hidden -- where a
               chain runs is as much of the answer as which Tasks are in it.  One class on
               the container does it, so that following a chain costs nothing on a large
               diagram; the exemption is only for the lines the chain's Tasks are drawn on,
               so that their "[Calls ...]" annotations stay readable.

               Greyed by colour and not by opacity, which is what it was at first: opacity
               makes a group, and nothing inside a group can be more opaque than the group
               is -- so the chain's own arrows faded along with the diagram they were drawn
               over.  A colour is inherited instead, and any element setting its own wins. */
            .mt-chaining .mt-dline:not(.mt-chain-line) {
                color: #6b7280 !important;
            }
            .mt-chain {
                background-color: #22c55e !important;
                color: #000000 !important;
                font-weight: bold;
            }
            .mt-chain-connector {
                background-color: #86efac !important;
                color: #000000 !important;
            }

            /* The menu a right-click on a node opens.  Parented to the body, for the reason
               the connector jump buttons are: the scroll area sets "contain: strict", which
               would clip anything positioned inside it to the scroll box. */
            .mt-dmenu {
                position: fixed;
                z-index: 1100;
                min-width: 190px;
                padding: 4px;
                background-color: #1f2937;
                color: #f9fafb;
                border: 1px solid #4b5563;
                border-radius: 6px;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
                font-family: system-ui, sans-serif;
                font-size: 0.8125rem;
            }
            .mt-dmenu-title {
                padding: 4px 10px 6px;
                font-weight: 700;
                color: #fbbf24;
                border-bottom: 1px solid #374151;
                margin-bottom: 4px;
                max-width: 320px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .mt-dmenu-item {
                display: block;
                width: 100%;
                padding: 6px 10px;
                text-align: left;
                background: none;
                border: none;
                color: inherit;
                font: inherit;
                border-radius: 4px;
                cursor: pointer;
            }
            .mt-dmenu-item:hover {
                background-color: #2563eb;
            }

            /* =========================================================================
               MAP VIEW: WHERE A CLICKED REPORT FINDING LANDS (see mapjump.py)
               ========================================================================= */
            /* The anchors themselves are empty and must stay that way -- they mark a
               position between two lines, and anything that gave them a box would push
               the output around. */
            .mt-anchor {
                display: none;
            }
            /* An outline rather than a background: the Map's own colours are the user's,
               picked against their chosen output background, and painting over one of
               them would hide the very line the jump just went to the trouble of finding.
               The pulse runs once and stops -- long enough to catch the eye on a dense
               page, not so long that it becomes the thing you are reading around. */
            .mt-jump-target {
                outline: 2px solid #ff5722;
                outline-offset: 2px;
                border-radius: 3px;
                animation: mt-jump-pulse 0.9s ease-out 2;
            }
            @keyframes mt-jump-pulse {
                0%   { background-color: rgba(255, 87, 34, 0.35); }
                100% { background-color: rgba(255, 87, 34, 0.00); }
            }

            /* A report row that points at something in the Map.  Dotted rather than solid
               underline, and no colour of its own: the reports are read in a <pre> as
               columns of tagged lines, and a row of blue links down the left would fight
               the tags for attention.  It has to LOOK different from the rows that do
               nothing, though -- a click that does nothing reads as a broken feature. */
            .mt-finding {
                cursor: pointer;
                text-decoration: underline dotted;
                text-underline-offset: 3px;
            }
            .mt-finding:hover,
            .mt-finding:focus {
                background-color: rgba(59, 130, 246, 0.18);
                text-decoration: underline solid;
                outline: none;
            }
        </style>
    """)


def initialize_screen(self: MyGui) -> None:
    """Initializes the main GUI screen layout using NiceGUI with split sidebars."""
    logger.info("Building UI Layout...")

    inject_shared_head_styles()
    # Before anything can notify: the wrapper has to be in place for the first message, and
    # start-up is capable of producing several (see restore_settings_event's running report).
    install_notification_timeout()
    set_notification_timeout(getattr(self, "notify_timeout", NOTIFY_TIMEOUT_DEFAULT))
    # While the layout is still being built, rather than when a Scene designer first opens --
    # see _register_canvas_events for why the timing is the whole point.
    _register_canvas_events()
    # Same timing, same reason: a clicked Health Check finding emits an event this has to be
    # subscribed to before the browser has the layout (see register_finding_clicks).
    register_finding_clicks(self)

    # =========================================================================
    # 1. HEADER
    # =========================================================================
    with ui.header().classes("bg-blue-900 text-white p-4 justify-between items-center"):
        ui.label("MapTasker").classes("text-2xl font-bold")

        # Stated outright rather than left to ui.dark_mode()'s own default: ui.run()'s
        # dark=None (auto) is applied before Vue mounts and this element then overrides it,
        # so this -- not the system appearance, and not the switch -- is what the page comes
        # up as. Only the mode the window OPENS in: restore_settings_event() runs after this
        # whole layout is built and puts the saved mode on top (see restore_appearance_mode).
        self.dm_controller = ui.dark_mode(value=STARTUP_DARK_MODE)

        self.dark_mode_switch = ui.switch(
            translate_string("Dark Mode"),
            value=STARTUP_DARK_MODE,
            on_change=lambda e: apply_appearance_mode(self, e.value),
        )

    # =========================================================================
    # 2. LEFT SIDEBAR: CONFIGURATIONS, DROPDOWNS & CHECKBOXES
    # =========================================================================
    with (
        ui
        .left_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-96 force-scrollbar gap-y-0 m-0 p-0 leading-none",
        ) as self.gui_left_drawer
    ):
        from maptasker.src.guiutils import add_logo  # noqa: PLC0415  Avoid circular import

        add_logo(self, "maptasker")

        ui.label(translate_string("Display Options")).classes("text-lg font-bold mb-2 gap-y-0 m-0 p-0 leading-none")

        # Detail level pulldown
        self.sidebar_detail_option = (
            ui
            .select(
                options=["0", "1", "2", "3", "4", "5"],
                value=str(self.display_detail_level),
                label=translate_string("Detail Level"),
                on_change=self.event_handlers.detail_selected_event,
            )
            .tooltip(translate_string("0 = least detail, 5 = most detail."))
            .classes("w-full")
            .props("dense")
        )

        # Core Feature Checkboxes
        self.everything_checkbox = ui.checkbox(
            translate_string("Just Display Everything!"),
            on_change=self.event_handlers.everything_event,
        ).tooltip(
            translate_string(
                "Enables the display of Conditions, TaskerNet Info, Preferences, the Directory, and Prettier Output.",
            ),
        )

        self.conditions_checkbox = ui.checkbox(
            translate_string("Display Conditions"),
            on_change=self.event_handlers.condition_event,
        ).tooltip(
            translate_string(
                "Enables the display of Profile Conditions (e.g. State, Event, etc.) details in the output.",
            ),
        )

        self.taskernet_checkbox = ui.checkbox(
            translate_string("Display TaskerNet Info"),
            on_change=self.event_handlers.taskernet_event,
        ).tooltip(translate_string("Enables the display of TaskerNet Descriptions in the output."))

        self.preferences_checkbox = ui.checkbox(
            translate_string("Display Tasker Preferences"),
            on_change=self.event_handlers.preferences_event,
        ).tooltip(translate_string("Enables the display a breakdown of the Tasker system Preferences in the output."))

        self.twisty_checkbox = ui.checkbox(
            translate_string("Hide Task Details Under Twisty"),
            on_change=self.event_handlers.twisty_event,
        ).tooltip(
            translate_string(
                "When enabled, Task details are hidden under a twisty (expand/collapse) control in the output.",
            ),
        )

        self.directory_checkbox = ui.checkbox(
            translate_string("Display Directory"),
            on_change=self.event_handlers.directory_event,
        ).tooltip(translate_string("Enables the display of the Project/Profile/Task/Scene Directory in the output."))

        self.pretty_checkbox = ui.checkbox(
            translate_string("Display Prettier Output"),
            on_change=self.event_handlers.pretty_event,
        ).tooltip(translate_string("Enables the display of aligned text in the output."))

        _create_name_display_options_section(self)
        _create_task_action_limit_section(self)
        _create_indentation_section(self)
        _create_language_selection_section(self)
        _create_font_section(self)
        _create_view_limit_section(self)
        _create_notification_duration_section(self)

    # =========================================================================
    # 3. RIGHT SIDEBAR: ALL ACTION, HELP & SETTINGS BUTTONS
    # =========================================================================
    with (
        ui
        .right_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-80 force-scrollbar flex flex-col items-center text-center",
        ) as self.gui_right_drawer
    ):
        ui.label(translate_string("Actions & Control")).classes("text-lg font-bold mb-2 self-center")

        ui.label(translate_string("Execution")).classes("text-xs font-bold uppercase text-gray-400 mt-2 self-center")
        get_file_color = "green" if PrimeItems.file_to_get else "red"
        blink_class = "" if PrimeItems.file_to_get else " animate-pulse"

        self.get_xml_button = ui.button(
            translate_string("Get Local XML File"),
            color=get_file_color,
            on_click=self.event_handlers.getxml_event,
            icon="folder",
        ).classes(f"w-full justify-center {blink_class}")
        with self.get_xml_button:
            ui.tooltip(
                translate_string(
                    "Fetch XML from a local drive on this computer.\n\nThe XML fetched will become the current source for MapTasker commands.",
                ),
            ).style("white-space: pre-wrap")

        self.exit_button = ui.button(
            translate_string("Exit"),
            color="orange",
            on_click=lambda: get_rid_of_windows_and_exit(self),
        ).classes(
            "w-full bg-red-600 text-white mt-0 justify-center",
        )

        self.close_tabs_on_exit_checkbox = (
            ui
            .checkbox(translate_string("Close Tabs On Exit"))
            .bind_value(self, "close_tabs_on_exit")
            .props("dense")
            .classes("text-xs mt-0")
        )
        with self.close_tabs_on_exit_checkbox:
            ui.tooltip(
                translate_string(
                    "When enabled, clicking 'Exit' also closes the main MapTasker window and any "
                    "Map/Diagram windows/tabs it opened.\n\nWhen disabled, 'Exit' shuts down MapTasker "
                    "but leaves those windows/tabs open.",
                ),
            ).style("white-space: pre-wrap")

        self.open_view_in_new_window_checkbox = (
            ui
            .checkbox(translate_string("Open View In New Window"))
            .bind_value(self, "open_view_in_new_window")
            .props("dense")
            .classes("text-xs mt-0")
            .style("margin-top:-6px")
        )
        with self.open_view_in_new_window_checkbox:
            ui.tooltip(
                translate_string(
                    "When enabled, each Map/Diagram request opens in its own new window/tab, so you can "
                    "keep earlier ones up alongside it to compare.\n\nWhen disabled, a request reuses "
                    "that view's existing window/tab, replacing what's in it.\n\nLeave it off unless you "
                    "want to compare: a brand new window/tab is the one your browser may block, since "
                    "it gets opened once the view has finished building rather than the instant you click.",
                ),
            ).style("white-space: pre-wrap")

        ui.label(translate_string("File Operations")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-3 self-center",
        ).style("margin-top:5px")
        _create_file_and_message_buttons_section(self)

        ui.label(translate_string("Display Views")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-3 self-center",
        )
        with ui.row().classes("w-full justify-center gap-2 gap-y-0 mt-0"):
            v_map = ui.button(translate_string("Map"), on_click=lambda: self.event_handlers.view_event("map")).classes(
                "bg-blue-500",
            )
            with v_map:
                ui.tooltip(
                    translate_string(
                        "Displays the Map view.\n\nUse this to display the Tasker configuration of your Projects, Profiles, Tasks, and Scenes.",
                    ),
                ).style("white-space: pre-wrap")
            v_diagram = ui.button(
                translate_string("Diagram"),
                on_click=lambda: self.event_handlers.view_event("diagram"),
            ).classes(
                "bg-blue-500",
            )
            with v_diagram:
                ui.tooltip(
                    translate_string(
                        "Displays the Diagram view.\n\nUse this to visualize the relationships between your Projects, Profiles, Tasks, and Scenes.",
                    ),
                ).style("white-space: pre-wrap")
            v_tree = ui.button(
                translate_string("Tree"),
                on_click=lambda: self.event_handlers.view_event("tree"),
            ).classes(
                "bg-blue-500",
            )
            with v_tree:
                ui.tooltip(
                    translate_string(
                        "Displays the Tree view.\n\nUse this to navigate the hierarchical structure of your Projects, Profiles, Tasks, and Scenes.",
                    ),
                ).style("white-space: pre-wrap")
        # Full width rather than a fourth button in the row above: the drawer is w-80, and a
        # fourth button wraps.  The width also leaves room for the longer label this needs.
        # Coloured through the "color" prop rather than a bg-* class, the way the Get XML and
        # Exit buttons are.  Quasar puts its own bg-primary on every button, and that wins over
        # a Tailwind bg-* added here -- a bg-teal-600 class renders plain blue.
        self.health_check_button = (
            ui
            .button(
                translate_string("Health Check"),
                color="teal",
                on_click=self.event_handlers.health_check_event,
                icon="health_and_safety",
            )
            .classes("w-full justify-center mt-0")
            .style("margin-top:-6px")
        )
        with self.health_check_button:
            ui.tooltip(
                translate_string(
                    "Scan the loaded XML for broken references, unreferenced Tasks, Profiles and "
                    "Scenes, and naming problems.\n\nResults are displayed here and saved to a "
                    "text file in the current directory.",
                ),
            ).style("white-space: pre-wrap")

        # Full width and coloured through "color" for the same two reasons the Health Check
        # button above is: the drawer is w-80 and this label is longer still, and Quasar's own
        # bg-primary beats a Tailwind bg-* class added here.
        self.compare_files_button = (
            ui
            .button(
                translate_string("Compare Files"),
                color="teal",
                on_click=self.event_handlers.compare_files_event,
                icon="difference",
            )
            .classes("w-full justify-center")
            .style("margin-top:-6px")
        )
        with self.compare_files_button:
            ui.tooltip(
                translate_string(
                    "Compare another XML file against the loaded one: what was added, removed, "
                    "renamed and changed.\n\nUse it to see what a TaskerNet import brought in, what "
                    "an edit changed, or what is different between two backups.\n\nIf the loaded "
                    "file came from 'Save to Current File', the file it was saved from is offered "
                    "directly.\n\nResults are displayed here and saved to a text file in the "
                    "current directory.",
                ),
            ).style("white-space: pre-wrap")

        # Full width and coloured through "color" for the same two reasons the two buttons
        # above are: the drawer is w-80 and this label will not fit beside another, and
        # Quasar's own bg-primary beats a Tailwind bg-* class added here.
        self.variable_xref_button = (
            ui
            .button(
                translate_string("Variable Xref"),
                color="teal",
                on_click=self.event_handlers.variable_xref_event,
                icon="manage_search",
            )
            .classes("w-full justify-center")
            .style("margin-top:-6px")
        )
        with self.variable_xref_button:
            ui.tooltip(
                translate_string(
                    "Trace every %variable in the loaded XML: where each one is set, where it is "
                    "read, which are read but never set, which are set but never read, and which "
                    "near-identical names (%MyVar against %Myvar) are likely typos.\n\nSearched: "
                    "Task actions and their conditions, plugin configuration, Profile contexts and "
                    "Scenes.\n\nResults are displayed here and saved to a text file in the current "
                    "directory.",
                ),
            ).style("white-space: pre-wrap")

        ui.button(translate_string("Clear"), on_click=self.event_handlers.clear_view_event).classes("bg-blue-500")

        ui.label(translate_string("Application Settings")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-4 self-center",
        ).style("margin-top:5px")
        _create_settings_buttons_section(self)

        ui.label(translate_string("Help & Information")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-4 gap-w-0 m-0 p-0 leading-none self-center",
        ).style("margin-top:5px")
        _create_help_options_section(self)

        # The "Buy Me A Coffee" logo and button close out the drawer.  add_logo() re-enters
        # gui_right_drawer itself rather than nesting inside a wrapper here, so the bottom
        # spacing (mt-auto) lives on the elements it creates, not on a container.
        add_logo(self, "coffee")

    # =========================================================================
    # 4. MAIN BODY CONTENT AREA
    # =========================================================================
    with ui.column().classes("p-6 w-full max-w-full mx-auto") as self.gui_main_column:
        with ui.row().classes("gap-4 mb-6") as self.gui_view_toolbar:
            self.current_file = ui.label(translate_string("No file loaded")).classes("text-gray-500 italic")

        # A tab's *name* -- ui.tab's first argument -- is the value ui.tabs carries, what
        # tab_to_use holds, and what TAB_NAMES and the settings file record, so it has to
        # stay English.  Only the label the user reads is translated.  Handing ui.tab the
        # translated string on its own (which makes it both name and label) meant the tab
        # names changed with the language: after a switch, the set_value(self.tab_to_use)
        # at the end of this function matched no tab at all and left every tab deselected,
        # and switching back to English made a stale tab_to_use match again and jump there.
        with ui.tabs().classes("w-full") as self.gui_main_tabs_container:
            self.tab_specific_name = ui.tab(
                "Specific Name",
                label=translate_string("Specific Name"),
                icon="filter_list",
            )
            self.tab_colors = ui.tab("Colors", label=translate_string("Colors"), icon="palette")
            self.tab_analyze = ui.tab("Analyze", label=translate_string("Analyze"), icon="analytics")
            self.tab_debug = ui.tab("Debug", label=translate_string("Debug"), icon="bug_report")

        with ui.tab_panels(self.gui_main_tabs_container, value=self.tab_specific_name).classes(
            "w-full border rounded shadow-inner p-4 mt-1 gap-y-0 m-0 p-0 leading-none",
        ) as self.gui_tab_panels:
            # --- TAB 1: SPECIFIC NAME (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_specific_name).classes("p-2 m-0") as self.gui_tasker_object_panel:
                ui.label(
                    translate_string("Target specific Projects, Profiles, Tasks or Scenes. (Select only one)"),
                ).classes(
                    "text-base mb-1",
                )
                self.currently_selected_label = ui.label("").classes("text-xs mb-2 text-gray-500 italic")

                # Wrap the pulldowns in a tight row so Project/Profile/Task/Scene sit side by side
                none_translatesd = translate_string("None")
                with ui.row().classes("gap-2 w-full m-0 p-0 items-start"):
                    self.specific_project_optionmenu = (
                        ui
                        .select(
                            [none_translatesd],
                            on_change=lambda e: (
                                self.event_handlers.single_project_name_event(e.value) if e.value else None
                            ),
                            label=translate_string("Project"),
                            with_input=True,
                        )
                        .classes("w-48 mb-0")
                        .props("dense")
                        .tooltip(translate_string("Select a specific Project to target for display or editing."))
                    )

                    self.specific_profile_optionmenu = (
                        ui
                        .select(
                            [none_translatesd],
                            on_change=lambda e: (
                                self.event_handlers.single_profile_name_event(e.value) if e.value else None
                            ),
                            label=translate_string("Profile"),
                            with_input=True,
                        )
                        .classes("w-48 mb-0")
                        .props("dense")
                        .tooltip(translate_string("Select a specific Profile to target for display or editing."))
                    )

                    self.specific_task_optionmenu = (
                        ui
                        .select(
                            [none_translatesd],
                            on_change=lambda e: (
                                self.event_handlers.single_task_name_event(e.value) if e.value else None
                            ),
                            label=translate_string("Task"),
                            with_input=True,
                        )
                        .classes("w-48 mb-0")
                        .props("dense")
                        .tooltip(translate_string("Select a specific Task to target for display or editing."))
                    )

                    self.specific_scene_optionmenu = (
                        ui
                        .select(
                            [none_translatesd],
                            on_change=lambda e: (
                                self.event_handlers.single_scene_name_event(e.value) if e.value else None
                            ),
                            label=translate_string("Scene"),
                            with_input=True,
                        )
                        .classes("w-48 mb-0")
                        .props("dense")
                        .tooltip(translate_string("Select a specific Scene to target for display or editing."))
                    )

                self.specific_name_msg_label = ui.label("").classes("text-xs ml-2 mt-1 text-left")
                self.list_unnamed_items_checkbox = (
                    ui
                    .checkbox(
                        translate_string("List Unnamed Items"),
                        on_change=self.event_handlers.list_unnamed_items_event,
                    )
                    .classes("mt-1 text-xs")
                    .tooltip(
                        translate_string(
                            "Select this to include Profiles and Tasks that do not have a name in the list.",
                        ),
                    )
                )
                # The Edit/Add pairs on the left, the Editing (Undo/Redo/History) group
                # pinned to the right: "justify-between" with nothing between them puts
                # each against its own edge however wide the window is.  Editing sits here
                # rather than in the drawer because it belongs with the buttons whose work
                # it takes back -- an Undo is only ever wanted after one of these was used.
                #
                # wrap=False is what keeps it pinned rather than merely placed: this panel
                # sits between two drawers and is only ~650px wide, so a wrapping row drops
                # the Editing group underneath the Edit/Add pairs as soon as both are shown
                # -- which is most of the time.  The Edit/Add buttons give up their fixed
                # width to pay for it (see their flex-1 below).
                with ui.row(wrap=False).classes("w-full items-start justify-between gap-4 m-0 p-0"):
                    # All eight Edit/Add buttons are built here, but only the ones the
                    # current pulldown selection can actually drive are ever on screen --
                    # guiutils.refresh_object_action_buttons hides the rest (and any row
                    # left with nothing in it) every time the selection changes, starting
                    # with the call at the end of this block.  Each row is held on self so
                    # it can be hidden along with its pair.
                    # flex-1/min-w-0: takes whatever the Editing group leaves rather than
                    # a fixed width, so nothing overflows the panel at any window size.
                    # Each button flexes within it, capped at 12rem -- the cap is what keeps
                    # a row showing one button the same width as each half of a row showing
                    # two, instead of the lone button stretching to the whole column.
                    with ui.column().classes("flex-1 min-w-0 gap-0 m-0 p-0"):
                        with ui.row().classes("w-full gap-2 m-0 p-0") as self.project_buttons_row:
                            self.edit_project_button = (
                                ui
                                .button(
                                    translate_string("Edit Project"),
                                    on_click=self.event_handlers.open_edit_project_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                            self.add_project_button = (
                                ui
                                .button(
                                    translate_string("Add Project"),
                                    on_click=self.event_handlers.open_add_project_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                        with ui.row().classes("w-full gap-2 m-0 p-0") as self.profile_buttons_row:
                            self.edit_profile_button = (
                                ui
                                .button(
                                    translate_string("Edit Profile"),
                                    on_click=self.event_handlers.open_edit_profile_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                            self.add_profile_button = (
                                ui
                                .button(
                                    translate_string("Add Profile"),
                                    on_click=self.event_handlers.open_add_profile_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                        with ui.row().classes("w-full gap-2 m-0 p-0") as self.task_buttons_row:
                            self.edit_task_button = (
                                ui
                                .button(
                                    translate_string("Edit Task"),
                                    on_click=self.event_handlers.open_edit_task_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                            self.add_task_button = (
                                ui
                                .button(
                                    translate_string("Add Task"),
                                    on_click=self.event_handlers.open_add_task_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                        # The Scene pair is the only one of the four behind a switch -- Scene
                        # editing is still filling in (see sceneedit.py).  Not built at all when
                        # config.EDIT_SCENE is False, rather than built-and-hidden: nothing else
                        # reads these two attributes, so leaving them unset is enough, and it
                        # keeps a disabled feature from occupying a row of the tab.
                        if EDIT_SCENE:
                            with ui.row().classes("w-full gap-2 m-0 p-0") as self.scene_buttons_row:
                                self.edit_scene_button = (
                                    ui
                                    .button(
                                        translate_string("Edit Scene"),
                                        on_click=self.event_handlers.open_edit_scene_dialog_event,
                                    )
                                    .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                    .style("max-width:12rem")
                                )
                                self.add_scene_button = (
                                    ui
                                    .button(
                                        translate_string("Add Scene"),
                                        on_click=self.event_handlers.open_add_scene_dialog_event,
                                    )
                                    .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                    .style("max-width:12rem")
                                )

                    # "shrink-0" so the Editing group keeps its width and stays hard against
                    # the right edge instead of being squeezed as the Edit/Add rows come and
                    # go with the selection.
                    with ui.column().classes("w-56 shrink-0 gap-1 m-0 p-0 mt-2 items-center"):
                        ui.label(translate_string("Editing")).classes(
                            "text-xs font-bold uppercase text-gray-400 self-center",
                        )
                        _create_undo_section(self)

                # Set the buttons to match whatever is selected right now, rather than
                # leaving them as built (all eight visible) until the first selection
                # change.  On start-up that means just "Add Project" -- the one action
                # needing no selection, and nothing is selected yet at this point (the
                # restore runs after initialize_screen).  On a rebuild, though -- a
                # language change re-runs this whole function (see reload_gui) -- there
                # very much can be a live selection to match.
                from maptasker.src.guiutils import (  # noqa: PLC0415  Avoid circular import
                    refresh_object_action_buttons,
                )

                refresh_object_action_buttons(self)

            # --- TAB 2: COLORS (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_colors).classes("p-2 m-0") as self.gui_color_panel:
                ui.label(translate_string("Theme Configuration")).classes("text-base mb-1")
                ui.button(
                    translate_string("Reset to Default Colors"),
                    on_click=self.event_handlers.color_reset_event,
                ).classes("bg-blue-500 text-xs py-1")

                self.color_change = ui.label(translate_string("Select a category to modify its color.")).classes(
                    "text-xs mt-2",
                )

                with ui.column().classes("gap-1 w-full mt-1"):
                    self.color_objects_options = (
                        ui
                        .select(
                            options=[
                                "Projects",
                                "Profiles",
                                "Disabled Profiles",
                                "Launcher Tasks",
                                "Profile Conditions",
                                "Tasks",
                                "Unnamed Tasks",
                                "(Task) Actions",
                                "Action Conditions",
                                "Action Labels",
                                "Action Names",
                                "Scenes",
                                "Background",
                                "TaskerNet Information",
                                "Tasker Preferences",
                                "Highlight",
                                "Heading",
                            ],
                            value="Projects",
                            label=translate_string("Select Category to Colorize"),
                        )
                        .classes("w-64 mb-0")
                        .props("dense")
                    )

                    self.color_picker_input = (
                        ui
                        .color_input(
                            label=translate_string("Choose Hex Color"),
                            value="#3f99ff",
                            on_change=lambda e: self.event_handlers.handle_color_pick_event(e.value),
                        )
                        .classes("w-64 mb-0")
                        .props("dense")
                    )

            # --- TAB 3: ANALYZE (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_analyze).classes("p-2 m-0") as self.gui_ai_panel:
                ui.label(translate_string("AI Analysis")).classes("text-base mb-2")
                _create_analyze_tab_content(self, ui.tab_panel(self.tab_analyze))

            # --- TAB 4: DEBUG (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_debug).classes("p-2 m-0") as self.gui_debug_panel:  # noqa: SIM117
                with ui.column().classes("gap-1"):
                    self.debug_checkbox = (
                        ui.checkbox(translate_string("Debug Mode")).bind_value(self, "debug").classes("text-xs")
                    )
                    self.runtime_checkbox = (
                        ui
                        .checkbox(translate_string("Display Runtime Settings"))
                        .bind_value(self, "runtime")
                        .classes("text-xs")
                    )

        self.content_container = ui.column().classes("w-full max-w-full min-w-0 p-0 m-0 mt-6")

        with ui.dialog() as self.picker_dialog, ui.card().classes("p-4 items-center"):
            self.picker_title_label = ui.label("").classes("font-bold text-sm mb-2")
            self.picker_engine = ui.color_picker()
            ui.button(translate_string("Cancel"), on_click=self.picker_dialog.close).classes(
                "mt-4 w-full bg-gray-500 text-white",
            )

    if self.tab_to_use:
        self.gui_main_tabs_container.set_value(self.tab_to_use)


async def get_rid_of_windows_and_exit(self: MyGui, _delete_all: bool = True) -> None:
    """Shuts down the NiceGUI server and exits."""
    if getattr(self, "close_tabs_on_exit", False):
        # Close every Map/Diagram popout this session opened -- the ones this window opened
        # and the ones those opened in turn (see mapjump.close_popouts_js) -- and then this
        # window itself. Browsers only allow script-driven window.close() on tabs/windows the
        # script itself opened, so this window may refuse to close if it wasn't launched via
        # window.open() -- that's an unavoidable browser security restriction, not a bug.
        # Must be awaited: run_javascript() only sends its payload once the event loop gets a
        # chance to run the background task it schedules -- and app.shutdown() below tears down
        # that same event loop. Without awaiting, shutdown can win the race and the browser never
        # receives the command, so the tabs are left open. window.close()-ing this tab itself may
        # tear down the connection before a response comes back, hence the timeout/suppress.
        with contextlib.suppress(Exception):
            await ui.run_javascript(mapjump.close_popouts_js(close_this_window=True), timeout=2.0)
    ui.notify(translate_string("Shutting down MapTasker..."), type="warning")
    app.shutdown()


def _create_analyze_tab_content(self: MyGui, tab: ui.tab_panel) -> None:
    """Populates the 'Analyze' (AI) tab using NiceGUI and colors the analysis button contextually."""
    from maptasker.src.guiutils import (  # noqa: PLC0415  Avoid circular import
        display_model_pulldown,
        update_analysis_button_color,
    )

    # Use the 'with' context manager to place elements inside the passed tab panel
    with tab:
        # 1. Action Buttons Row
        with ui.row().classes("items-center gap-4 mb-4"):
            self.show_apikeys_button = ui.button(
                translate_string("Show/Edit API Key(s)"),
                on_click=self.event_handlers.ai_apikey_event,
            )
            self.change_prompt_button = ui.button(
                translate_string("Change Prompt"),
                on_click=self.event_handlers.ai_prompt_event,
            )

            self.analysis_button = ui.button(
                translate_string("Run Analysis"),
                on_click=self.event_handlers.ai_analyze_event,
            )
            update_analysis_button_color(self)
            self.analysis_query_button = ui.button(
                "?",
                on_click=lambda: self.event_handlers.query_event("ai"),
            ).classes("bg-blue-600 text-white min-w-[40px]")

        # 2. Model Selection Row
        with ui.row().classes("items-center gap-4"):
            self.model_to_use_label = ui.label(translate_string("Model to Use:")).classes("font-bold")

            # Display the default model list
            display_model_pulldown(self)

            # Extra model list checkbox with chained tooltip
            self.aimodel_extend_checkbox = (
                ui
                .checkbox(translate_string("Extended"), on_change=self.event_handlers.extended_models_event)
                .tooltip(
                    translate_string(
                        "Display an extended list of ALL available models.\n\n"
                        "Note: If the API key is not set for OpenAI or Gemini,\n"
                        "      then the default model list for the respective\n"
                        "      AI provider will be displayed.\n\n"
                        "Note: Not all models have been validated and\n"
                        "      one or more may return an error on analysis.\n\n"
                        "Note: Enabling this option for the first time will\n"
                        "      force the installation of the following modules\n"
                        "      and all of their dependencies:\n"
                        "      google-genai, anthropic, openai, ollama",
                    ),
                )
                .style("white-space: pre-wrap")
            )  # Ensures the newline characters format correctly in HTML


def _create_name_display_options_section(self: MyGui) -> None:
    """
    Optimized creation of name display options using NiceGUI.
    Renders a section header and a condensed 2x2 grid of styling checkboxes.
    """
    handlers = self.event_handlers

    # 1. Create the Section Label with an inline native tooltip
    self.display_names_label = (
        ui
        .label(translate_string("Project/Profile/Task/Scene Names:"))
        .classes("text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 leading-none")
        .tooltip(translate_string("Add highlighting to Project, Profile and Task names in the output."))
    )

    # 2. Define Checkbox Configurations
    checkbox_configs = [
        (
            "bold_checkbox",
            handlers.names_bold_event,
            translate_string("Bold"),
            "Bold and Italicize are mutually exclusive in the Map view.",
        ),
        (
            "italicize_checkbox",
            handlers.names_italicize_event,
            translate_string("Italicize"),
            "Italicize and Bold are mutually exclusive in the Map view.",
        ),
        ("highlight_checkbox", handlers.names_highlight_event, translate_string("Highlight"), None),
        ("underline_checkbox", handlers.names_underline_event, translate_string("Underline"), None),
    ]

    # 3. Batch Creation inside a highly condensed 2-Column Grid Layout
    # Changed gap-y-1 to gap-y-0 to completely eliminate grid vertical row spacing
    with ui.grid(columns=2).classes("w-full gap-x-4 py-0 my-0 gap-y-0 pl-2"):
        for attr, event, label, tip in checkbox_configs:
            # Instantiate the checkbox and strip vertical padding/margins via py-0 my-0
            checkbox = ui.checkbox(label, on_change=event).classes("py-0 my-0")

            # Save the reference dynamically to the 'self' instance
            setattr(self, attr, checkbox)

            # Chain the tooltip natively if one is defined
            if tip:
                checkbox.tooltip(tip)


def _create_task_action_limit_section(self: MyGui) -> None:
    """Creates the task 'actions' limit slider in the NiceGUI sidebar."""
    text_to_insert = "Task 'actions' limit"
    text = PrimeItems._(text_to_insert) if hasattr(PrimeItems, "_") else text_to_insert

    # 1. Label tracking the live dynamic value
    self.task_action_label = ui.label(f"{text}: {self.task_action_warning_limit}").classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0",
    )

    # 2. NiceGUI Slider
    # NiceGUI handles styling with Tailwind (e.g., track color tints via accent)
    self.task_action_limit = ui.slider(
        min=10,
        max=100,
        step=1,
        value=100,
        on_change=self.event_handlers.tasklimit_event,
    ).classes(
        "w-full px-2 accent-green-600 py-0 my-0 gap-y-0",
    )
    with self.task_action_limit:
        ui.tooltip(
            translate_string(
                "Select how many actions in a Task before issuing a warning.\n"
                "The warning appears near the bottom of the configuration output,\n"
                "and is intended to help identify Tasks that are too complex\n"
                "and which should potentially be broken up into multiple Tasks.\n"
                "A setting of '100' means there is no limit.",
            ),
        ).style(
            "white-space: pre-wrap",
        )  # Ensures the tooltip text respects newlines for better readability


def _create_indentation_section(self: MyGui) -> None:
    """Creates the If/Then/Else indentation dropdown options in the NiceGUI sidebar."""
    self.indent_label = ui.label(translate_string("If/Then/Else Indentation Amount:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    self.indent_option = ui.select(
        options=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        value="4",  # Default initial value matching your original comments
        on_change=self.event_handlers.indent_selected_event,
    ).classes("w-full leading-none py-0 my-0 gap-y-0")
    with self.indent_option:
        ui.tooltip(
            translate_string(
                "Set the indentation amount for If/Then/Else blocks.\n\n"
                "The default is '4'.\n\n"
                "This affects how the output is formatted in the Map and Diagram views.",
            ),
        ).style(
            "white-space: pre-wrap",
        )  # Ensures the tooltip text respects newlines for better readability


def _create_language_selection_section(self: MyGui) -> None:
    """Creates the language selection dropdown in the NiceGUI sidebar."""
    self.language_label = ui.label(f"{translate_string('Language:')}").classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    # This returns a list of English language keys, e.g., ["English", "German", "French"]
    languages = sort_languages_with_priority(PrimeItems.languages.keys())

    # ui.select's "value" (what on_change reports, and what must be assigned to select
    # a specific entry) is always the dict KEY, never the displayed label -- so map each
    # English key to its translated display label (e.g. "German" -> "Deutsch") here. That
    # keeps the value side in English (matching self.language / PrimeItems.languages) while
    # still showing the user their language's own name instead of always English.
    language_options = {language: translate_string(language) for language in languages}

    self.language_optionmenu = ui.select(
        options=language_options,
        value=self.language,
        on_change=self.event_handlers.language_selected_event,
    ).classes("w-full")


def _create_view_limit_section(self: MyGui) -> None:
    """Creates the view limit dropdown in the sidebar drawer."""
    self.viewlimit_label = ui.label(translate_string("View Limit:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )

    with ui.row().classes("w-full items-center gap-2"):
        temp_view_limit = getattr(self, "view_limit", str(VIEW_LIMIT_DEFAULT))
        if temp_view_limit == 9999999:
            self.view_limit = "Unlimited"
        self.viewlimit_optionmenu = ui.select(
            options=["5000", "10000", "15000", "20000", "25000", "30000", "Unlimited"],
            value=str(getattr(self, "view_limit", VIEW_LIMIT_DEFAULT)),
            on_change=self.event_handlers.viewlimit_event,
        ).classes("flex-grow")
        with self.viewlimit_optionmenu:
            ui.tooltip(
                translate_string(
                    "Select the maximum number of items to display in the view to be allowed.\n\n"
                    "Anything over this amount will stop the generation of the view as a means to throttle the program.\n\n"
                    "Note: This is only for the 'Map' and 'Diagram' views, not the tree view.",
                ),
            ).style(
                "white-space: pre-wrap",
            )  # Ensures the tooltip text respects newlines for better readability
        self.view_limit = int(temp_view_limit) if temp_view_limit != "Unlimited" else 9999999

        # Query help button
        self.viewlimit_query_button = ui.button(
            "?",
            on_click=lambda: self.event_handlers.query_event("viewlimit"),
        ).classes("bg-blue-600 text-white min-w-[40px]")


def _create_notification_duration_section(self: MyGui) -> None:
    """The 'Notification Duration' pulldown in the sidebar drawer.

    Offered as durations rather than milliseconds: the number is an implementation detail of
    Quasar's API, and nobody choosing how long a message should linger is thinking in
    thousandths of a second.  The stored value is still milliseconds, because that is what
    ui.notify wants and what the settings file has always held for numeric settings.
    """
    self.notify_timeout_label = ui.label(translate_string("Notification Duration:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )
    with ui.row().classes("w-full items-center gap-2"):
        current = getattr(self, "notify_timeout", NOTIFY_TIMEOUT_DEFAULT)
        labels = {milliseconds: label for label, milliseconds in NOTIFY_TIMEOUT_CHOICES}
        # Fall back through the default to the first choice: an unlistable value is a settings
        # bug, and the whole GUI failing to build is too high a price for one wrong pulldown.
        fallback = labels.get(NOTIFY_TIMEOUT_DEFAULT, NOTIFY_TIMEOUT_CHOICES[0][0])
        self.notify_timeout_optionmenu = ui.select(
            options=[translate_string(label) for label, _ms in NOTIFY_TIMEOUT_CHOICES],
            value=translate_string(labels.get(current, fallback)),
            on_change=self.event_handlers.notify_timeout_event,
        ).classes("flex-grow")
        with self.notify_timeout_optionmenu:
            ui.tooltip(
                translate_string(
                    "How long a pop-up message stays on screen before it disappears.\n\n"
                    "'Until dismissed' keeps every message up until you close it, which is useful "
                    "when a message scrolls past before you can read it.\n\n"
                    "A few messages set their own longer duration because they list things you "
                    "have to read -- the Tasks affected by deleting or renaming a Scene element, "
                    "for instance. Those keep their own timing whatever is chosen here.",
                ),
            ).style("white-space: pre-wrap")


def _create_settings_buttons_section(self: MyGui) -> None:
    """Creates settings buttons in their respective responsive layout containers."""
    handlers = self.event_handlers

    # 1. Sidebar Buttons (Master: self.gui_left_drawer)
    with self.gui_left_drawer:
        self.reset_button = ui.button(
            translate_string("Reset Options"),
            on_click=handlers.reset_settings_event,
        ).classes(
            "w-full bg-blue-600 text-white mt-2",
        )
        # Nest the tooltip explicitly inside the button context
        with self.reset_button:
            ui.tooltip(
                translate_string(
                    "Reset all of the options to their default values, including colors, font used, and other settings.\n\n"
                    "The currently loaded XML will be cleared out.",
                ),
            ).style(
                "white-space: pre-wrap;",
            )  # Tells the web browser to render \n newlines!

    # 2. Main Window Buttons Layout Area
    with ui.row().classes("w-full gap-2 mt-0 justify-center"):
        self.save_settings_button = ui.button(
            translate_string("Save Settings"),
            on_click=handlers.save_settings_event,
        ).classes(
            "bg-indigo-600 text-white justify-center",
        )

        self.restore_settings_button = ui.button(
            translate_string("Restore Settings"),
            on_click=handlers.restore_settings_event,
        ).classes(
            "bg-indigo-600 text-white justify-center",
        )

        self.report_issue_button = ui.button(
            translate_string("Report Issue"),
            on_click=handlers.report_issue_event,
        ).classes(
            "bg-gray-600 text-white justify-center",
        )
        with self.report_issue_button:
            ui.tooltip(
                translate_string(
                    "Report any issues and/or suggestions to the developer.\n\n"
                    "This will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.",
                ),
            ).style("white-space: pre-wrap;")


def _create_font_section(self: MyGui) -> None:
    """Creates the font selection dropdown inside the content container."""
    self.font_label = ui.label(translate_string("Font To Use In Output:")).classes(
        "text-sm font-semibold mt-4 mb-1 py-0 my-0 gap-y-0 m-0 p-0 leading-none",
    )

    # {font name: label shown}, so the label can mark a font as monospaced while the
    # value carried by the pulldown stays the plain name the output has to reference.
    if not PrimeItems.mono_fonts:
        font_items = get_font_choices()
        PrimeItems.mono_fonts = font_items
    else:
        font_items = PrimeItems.mono_fonts

    font_names = list(font_items)
    default_font = [name for name in font_names if "Courier" in name]
    self.default_font = default_font[0] if default_font else font_names[0]

    # Show the font actually in effect. It comes from the restored settings and, now that
    # proportional fonts can be offered too, may be anything -- but a font that has since
    # been uninstalled is no longer among the choices, and selecting one that isn't there
    # leaves the pulldown blank.
    current_font = self.font if self.font in font_items else self.default_font

    # ui.select manages choices natively
    self.font_optionmenu = ui.select(
        options=font_items,
        value=current_font,
        on_change=self.event_handlers.font_event,
    ).classes("w-64")
    with self.font_optionmenu:
        ui.tooltip(
            translate_string(
                "This is a list of all of the fonts available on your system, monospaced ones first "
                "and marked as such.\n\n"
                "The font selected will be used in all output.\n\n"
                "'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector "
                "alignment. A font that is not monospaced will not hold the Diagram's connectors or the "
                "output's indentation in line.",
            ),
        ).style(
            "white-space: pre-wrap;",
        )  # Ensures newlines render properly in the tooltip


def _create_file_and_message_buttons_section(self: MyGui) -> None:
    """Creates file actions, message configuration button rows, and dynamic android panel containers."""
    with self.gui_right_drawer:
        # This button and its "?" are built once, here, and stay put for the life of the window:
        # opening the Android panel (get_xml_from_android_event in userintr.py) adds a panel
        # below them rather than replacing them, and clear_android_buttons() (guiutils.py) only
        # tears that panel down again.
        with ui.row().classes("w-full flex-nowrap items-center justify-center gap-2 mt-0") as self.android_button_row:
            self.get_backup_button = (
                ui
                .button(
                    translate_string("Get XML from Android Device"),
                    on_click=self.event_handlers.get_xml_from_android_event,
                )
                .style("background-color: #246FB6; border-color: #6563ff; border-width: 2px; color: white;")
                .classes("mt-0 ml-0 font-bold flex-grow text-xs")
            )
            self.android_query_button = ui.button(
                "?",
                on_click=lambda: self.event_handlers.query_event("android"),
            ).classes("bg-blue-600 text-white min-w-[40px] shrink-0")
        with self.get_backup_button:
            ui.tooltip(
                translate_string(
                    "Fetch XML from an Android device.\n\nYou must be on the same network as the Android device, and the device must be running and connected.\n\n",
                ),
            ).style("white-space: pre-wrap")

        # The container panels stay bound right here under the button setup
        self.android_container = ui.column().classes(
            "w-full gap-y-2 mt-4 p-2 bg-gray-50 dark:bg-gray-700 rounded shadow-sm hidden",
        )
        self.upgrade_container = ui.column().classes("w-full gap-y-2 mt-2 items-center text-center hidden")


def _create_help_options_section(self: MyGui) -> None:
    """Creates browser execution panels, help routing shortcuts, and app termination controls."""
    handlers = self.event_handlers

    # 1. Specialized Help Buttons Row
    with ui.row().classes("w-full gap-2 mt-0 self_center justify-center"):
        self.display_help_button = ui.button(
            translate_string("Display Help"),
            on_click=lambda: handlers.query_event("help"),
        ).classes(
            "bg-blue-600 text-white",
        )

        self.get_android_help_button = ui.button(
            translate_string("Get Android Help"),
            on_click=lambda: handlers.query_event("android"),
        ).classes("bg-blue-600 text-white")
