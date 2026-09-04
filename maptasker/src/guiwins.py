"""GUI Window Classes and Definitions (NiceGUI Version).

What is left here after the split: the popup and "Changes Pending" scaffolding every editor
shares, the session Undo controls, the Project and Scene dialogs, the Object Properties
form, the three views (Tree, Scene, Text), and the screen's own initialization and layout.

The dialog families that were taking this file past 14,500 lines now live beside it, one
module per family:

    guiwins_taskedit.py         Edit/Add/Delete Task, the Action editor and its pickers
    guiwins_profedit.py         Edit/Add/Delete Profile and its Save To Android panel
    guiwins_designer_legacy.py  the Legacy Scene designer and its element dialogs
    guiwins_designer_v2.py      the Version 2 Scene designer and its property fields
    guiwins_canvas.py           the Scene canvas JavaScript both designers draw through
    guiwins2.py                 the AI API Keys dialog

Each imports what it needs from this file; the few that this file calls back into are
imported at the top, below.  A family that had to reach back for editor scaffolding does so
inside the function that needs it, which is the one thing to know before moving code between
these modules -- see any of their docstrings for which calls those are and why.
"""

from __future__ import annotations

import asyncio
import contextlib
import html
import json
import os
import re
import weakref
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to serialize, never to parse
from typing import TYPE_CHECKING

from nicegui import Event, app, context, ui

from maptasker.src import (
    diagintr,
    mapfind,
    mapjump,
    mapswap,
    objprops,
    projedit,
    roundtrip,
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

# The dialog families split out of this file, which had grown past 14,500 lines.  Each is
# imported for the handful of names this module still calls into: the Scene canvas the
# Preview draws through, the two designers the Scene editor body mounts, and the Action
# editor and pickers the Scene Event tab reuses.  guiwins_profedit is not among them --
# nothing here calls it; userintr reaches it directly.
from maptasker.src.guiwins_canvas import (
    _ACTIVE_CANVASES,
    CANVAS_PREVIEW_ROOT,
    FIELD_COMMIT_DEBOUNCE_MS,
    _emit_canvas_editing,
    _emit_canvas_fit,
    _emit_v2_dragging,
    _emit_v2_hull,
    _register_canvas_events,
)
from maptasker.src.guiwins_designer_legacy import (
    _build_legacy_designer,
    _legacy_canvas_size,
    _render_legacy_arg,
)
from maptasker.src.guiwins_designer_v2 import _build_v2_designer
from maptasker.src.guiwins_taskedit import (
    _build_task_action_editor,
    _build_tasker_icon_picker_dialog,
    _render_addability_reason,
)
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    DIAGRAM_FILE,
    DIAGRAM_PROFILES_PER_LINE,
    NOTIFY_TIMEOUT_DEFAULT,
    VIEW_LIMIT_DEFAULT,
    logger,
)

if TYPE_CHECKING:
    import collections
    from collections.abc import Callable, Coroutine, Iterator

    import defusedxml.ElementTree

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


def _create_refactor_button(self: MyGui) -> None:
    """The Refactor button, in the 'Specific Name' tab's Editing group.

    Here rather than on the Map/Diagram toolbar, where it started, because a refactor is an
    EDIT and belongs with the Edit/Add buttons and the Undo that takes it back.  Three of
    its four operations -- inline a call, move to another Project, duplicate an object --
    name an object and act on it whole; nothing about them depends on what is drawn, so
    hanging them off a view meant a Map had to be built before any of them could be reached.

    NOT one of the per-kind Edit/Add pairs, and so not hidden with them: one dialog covers
    Projects, Profiles, Tasks and Scenes together, and which of them is selected decides
    only what Extract offers (see maprefac.extract_scope), never whether the button works.
    """
    self.refactor_button = ui.button(
        translate_string("Refactor"),
        color="teal",
        icon="account_tree",
        on_click=self.event_handlers.refactor_event,
    ).classes("w-full justify-center")
    with self.refactor_button:
        ui.tooltip(
            translate_string(
                "The structural changes that Add, Edit and Delete cannot make: pull a run of a "
                "Task's actions out into a Task of their own, fold a Perform Task back into its "
                "caller, move a Task or Profile to another Project, or duplicate any object.\n\n"
                "Nothing is changed until you press Preview and then Apply, and the preview says "
                "what will happen step by step -- or why it will not.\n\n"
                "The whole of a refactor is one press of Undo afterwards.\n\n",
            ),
        ).style("white-space: pre-wrap")


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


# ==========================================
# 2b-pre. THE SAVE TO ANDROID PANEL'S OWN FIELDS
#
# All four Save To Android panels -- Task, Profile, Project, Scene -- open with the same
# three controls, and they are built here rather than four times over so that they cannot
# drift apart.  They were already identical; "Verify" is the first thing added to them
# since, and adding it in one place is the whole reason this exists.
# ==========================================
def _android_device_fields(gui: MyGui) -> dict:
    """Where the device is, and whether to check the XML before sending it there.

    The address and port default to the last ones that worked, the same way the Get XML and
    Fetch Applications dialogs default -- and are written back by the save handlers, not
    here, because a device that was never reached is not one to remember.

    "Verify" is remembered differently: on the checkbox itself, as it is ticked.  It is a
    preference about how this program behaves rather than a fact about a device, so a user
    who wants every save checked should not have to re-tick it on the next panel -- and
    unlike the address, there is no failure that should make it stick less.

    It defaults OFF.  What it does is described in its own tooltip, and what it costs is a
    save it can refuse: a check that could block a save without having been asked for is not
    one to turn on behind the user's back.  See roundtrip.py's header.
    """
    default_ip = getattr(gui, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(gui, "android_port", "") or "1821"

    fields = {
        "ip_address": ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full"),
        "ip_port": ui.input(translate_string("Port"), value=default_port).classes("w-full"),
    }
    verify = (
        ui.checkbox(
            translate_string("Verify"),
            value=bool(getattr(gui, "android_verify", False)),
            on_change=lambda event: setattr(gui, "android_verify", bool(event.value)),
        )
        .props("dense")
        .classes("mt-2")
    )
    with verify:
        ui.tooltip(
            translate_string(
                "Reads the XML back before it is sent, and refuses the save if anything changed on "
                "the way through.\n\n"
                "What this catches is the class of failure nothing else in the save path can: a value "
                "that this program's own writer and reader disagree about -- a carriage return inside "
                "a name, say, which is written out as typed and read back as a newline.  The upload "
                "answers 200 and the file on the device matches the file that was sent, because both "
                "are already wrong.\n\n"
                "Every object going up is compared against the one in the loaded configuration, "
                "including the Profiles, Scenes and Tasks bundled in that you did not edit.  Nothing "
                "is sent if any of them differs; you get a report saying which and where.\n\n"
                "It costs a fraction of a second and contacts nothing -- the whole check runs here, "
                "before the device is touched.",
            ),
        ).style("white-space: pre-wrap")
    fields["verify"] = verify
    return fields


def build_round_trip_report_dialog(report: roundtrip.RoundTripReport) -> None:
    """What "Verify" found, when what it found stopped a save.

    A dialog rather than a notification because the useful part is a list -- which object,
    where inside it, and the two values -- and because this is a save that did NOT happen,
    which is not something to say in a message that fades.  Shaped like
    build_helper_tasks_dialog, and for the same reason: a list the user reads next to
    something else, with no button on it that does anything but close.

    Deliberately offers no "send it anyway".  The whole claim of the checkbox is that
    nothing goes to the device when the check fails; a button undoing that would make it a
    warning, which the user could already have had by leaving the box unticked.
    """
    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[480px] max-w-[760px] w-full p-6"):
        ui.label(translate_string("Verify Failed -- Nothing Was Sent")).classes("text-lg font-bold text-red-600")
        ui.label(report.summary()).classes("mt-1 text-sm")
        with ui.column().classes("gap-0 mt-3"):
            for line in report.detail():
                ui.label(line).classes("font-mono text-xs break-all whitespace-pre-wrap")
        ui.label(
            translate_string(
                "Your Android device was not contacted and nothing on it was changed.  The loaded "
                "configuration is untouched as well -- this is a check on what was about to be "
                "written, not on what is on the device.",
            ),
        ).classes("text-xs text-gray-500 italic mt-3")
        with ui.row().classes("w-full justify-end mt-4"):
            ui.button(translate_string("Close"), on_click=dialog.close).classes("bg-blue-600")

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
    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Task To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = _android_device_fields(self)
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
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            # The other half of the same dialog, and a genuinely different outcome -- see
            # guiwins_profedit.build_save_profile_to_android_dialog for why these are two buttons and not a
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

        # No on_applied, unlike Edit Project: a Project that does not exist yet has no live
        # element to mirror onto, and register_new_project stores THIS element object
        # rather than a copy of it -- so properties set before the Project exists are
        # already on it once it does.
        _build_properties_button(self, objprops.KIND_PROJECT, edited_project.project_element, dialog)

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
        # guiwins_taskedit.build_edit_task_dialog's identical Name field for why.
        field_refs["name"] = (
            ui.input(translate_string("Project Name"), value=project_name).props("readonly").classes("w-full")
        )

        # Enabled/Disabled, presented exactly as Edit Profile offers it (see
        # guiwins_profedit._build_profile_editor_body's identical switch).  What it writes is not the
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

        # Applied to the working copy AND mirrored onto the live element the moment Ok is
        # pressed -- see projedit.apply_properties_to_live_tree for why both, and why this
        # cannot wait for a save the way Task's and Profile's do.  That immediacy is what
        # keeps it out of field_refs and therefore clear of _unapplied_project_edits: by
        # the time either by-name save runs, there is nothing left unapplied.
        _build_properties_button(
            self,
            objprops.KIND_PROJECT,
            edited_project.project_element,
            dialog,
            on_applied=lambda: self.event_handlers.apply_project_properties_event(edited_project),
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
                        "match its Tasker server settings.\n\n"
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
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
    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Project To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = _android_device_fields(self)
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
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            # The Profile dialog's pair, for a Project -- see
            # guiwins_profedit.build_save_profile_to_android_dialog for why these are two buttons and not one
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
# 2b-pre. OBJECT PROPERTIES
#
# The Properties editor a Project, Profile, Task and Scene all reach from their own
# Add/Edit dialog, through the one button _build_properties_button makes.  What the
# properties ARE lives in objprops.py; this is the form over it.
#
# One dialog rather than four because the three non-Scene kinds differ only in which
# scalars they show, and objprops.OBJECT_PROPERTIES is that difference -- so adding a
# field to a kind is a row in that table and nothing here changes.  A Scene's properties
# are a <PropertiesElement> generated from arg_dict instead and keep their own panel in
# the Scene designer (render_scene_properties); only the button is shared.
#
# WHICH ELEMENT THE CALLER HANDS OVER decides whether the edit survives its save, and it
# is not the same for every kind -- the live element for a Project, the working copy for
# the rest.  objprops.py's module docstring is the long version; do not wire a new caller
# up without reading it.
# ==========================================
def _build_properties_button(
    self: MyGui,
    kind: str,
    element: defusedxml.ElementTree.Element,
    parent_dialog: ui.dialog,
    on_applied: Callable[[], None] | None = None,
    opener: Callable[[], None] | None = None,
) -> ui.button:
    """The one button an Add/Edit dialog grows.  Reads "Add Properties" for an object
    that has none yet and "Edit Properties" for one that has.

    `opener` replaces what the button opens.  Only a Scene passes one: its properties are
    a <PropertiesElement>'s arguments rather than the scalars-and-variables the other
    three share, so it has its own form (_build_scene_properties_dialog) and shares only
    this button.  See that function for why the two could not be one.

    Deliberately NOT registered in the caller's field_refs.  The Task dialog's
    _task_arg_values reads .value off every entry there and a button has none; and for
    the Project dialog an unrecognised field_refs entry is what
    userintr._unapplied_project_edits fails the save on.  Nothing needs to be registered
    anyway -- the properties dialog applies onto the element itself, which is what both
    the save and editor_state() already read.

    `on_applied` runs after a successful Ok, for a caller whose element is not the whole
    story.  Edit Project is the only one: its saves render from the live tree by name, so
    it passes projedit.apply_properties_to_live_tree to carry the edit across.  Everything
    else leaves it None, because the element handed over IS what gets saved.
    """
    label = "Edit Properties" if objprops.has_properties(kind, element) else "Add Properties"
    button = ui.button(
        translate_string(label),
        icon="tune",
        on_click=opener
        or (
            lambda: self.event_handlers.open_object_properties_event(
                kind,
                element,
                parent_dialog,
                on_applied,
            )
        ),
    ).props("outline")
    with button:
        # Edit Project's properties reach the loaded backup as soon as Ok is pressed,
        # because that is the only way they can reach its by-name saves at all -- so it
        # says so, in the words its Rename and Enabled controls already use.
        applies_immediately = on_applied is not None
        ui.tooltip(
            translate_string(
                f"The comments and variables Tasker keeps against this {kind}, and its own settings.\n"
                + (
                    "Changes here are applied to the loaded backup as soon as you press Ok in the "
                    "Properties window -- like Rename and the Enabled switch, Cancel does not undo them."
                    if applies_immediately
                    else "Changes here are kept when you press Ok in this window, and are saved along "
                    "with everything else when you save."
                ),
            ),
        ).style("white-space: pre-wrap")
    return button


def _build_property_widget(spec: objprops.PropField, value: str) -> object:
    """One scalar property's widget, per objprops.PropField.kind.

    Every one of them carries Tasker's own wording as its tooltip -- these are settings
    whose names give nothing away ("Collision Handling", "Cooldown Time"), and the
    sentence explaining each is the same one Tasker shows.
    """
    if spec.kind == "checkbox":
        widget = ui.checkbox(translate_string(spec.label), value=value == "true")
    elif spec.kind == "choice":
        widget = ui.select(
            list(spec.choices),
            value=value or spec.choices[0],
            label=translate_string(spec.label),
        ).classes("w-full")
    elif spec.kind == "slider":
        # Number rather than a bare slider: the value has to be readable and typeable,
        # and a 0-50 slider alone gives no way to land on an exact one.
        widget = ui.number(
            translate_string(spec.label),
            value=int(value) if value.isdigit() else None,
            min=0,
            max=spec.maximum,
            format="%.0f",
        ).classes("w-full")
    elif spec.kind == "number":
        # The slider's widget without the ceiling: a repeat count has no maximum Tasker
        # documents, and 0-50 is Launch Task Priority's range rather than a shared one.
        # Empty means "no value", which is what removes the tag -- see PropField.default.
        widget = ui.number(
            translate_string(spec.label),
            value=int(value) if value.isdigit() else None,
            min=0,
            format="%.0f",
        ).classes("w-full")
    elif spec.kind == "duration":
        widget = ui.input(
            f"{translate_string(spec.label)} ({objprops.COOLDOWN_FORMAT})",
            value=objprops.format_cooldown(value),
        ).classes("w-full")
    else:
        widget = ui.input(translate_string(spec.label), value=value).props("autogrow").classes("w-full")

    if spec.tooltip:
        with widget:
            ui.tooltip(translate_string(spec.tooltip)).style("white-space: pre-wrap; max-width: 32rem")
    return widget


# The three checkboxes on a variable, with the explanations Tasker itself gives for them
# -- transcribed from the Project Variables help screens (Properties1.png/Properties2.png).
# Kept together because all three are the same shape and the wording is the point.
_VARIABLE_CHECKBOXES: tuple[tuple[str, str, str], ...] = (
    (
        "pvci",
        "Configure On Import",
        "If you enable the option to configure on import you need to fill in a question that the "
        "user will be asked when importing this into Tasker.  The value of this variable will "
        "also be cleared when you export it so that private data is not mistakenly sent to other "
        "users.",
    ),
    (
        "strout",
        "Structured Variables (JSON, etc)",
        "Enable the 'Structured Variable' option if the variable is either JSON, HTML or XML so "
        "that you can easily read its contents via the dot or square brackets notations.\n"
        "For example if there's a %json variable and its contents are in the JSON format you "
        "could use '%json.info' or '%json[info]' to get the value for the 'info' field.",
    ),
    (
        "immutable",
        "Immutable",
        "If you enable the 'Immutable' option, the variable can be changed in Tasks, but will "
        "reset to the value here when the Task ends.",
    ),
)


def _build_variable_panel(
    props: objprops.EditableProperties,
    index: int,
    variable: defusedxml.ElementTree.Element,
    field_refs: dict,
    rerender: Callable[[], None],
) -> None:
    """One <ProfileVariable>, as an expansion titled by its name.

    Field order follows Tasker's own, which is the order property.py already prints them
    in on the read side: Type, Name, the three checkboxes, then Value / Display Name /
    Prompt, then Exported Value with "Same as Value" beside it.
    """
    values = objprops.variable_values(variable)
    key = lambda field: f"var{index}_{field}"

    title = objprops.variable_display_name(variable) or translate_string("(new variable)")
    with ui.expansion(title, icon="data_object", value=not values["pvn"]).classes("w-full"):
        # Codes are what the XML holds, labels are what a person can pick -- so a
        # {code: label} select, sorted by label.  A code this build does not know about
        # (a newer Tasker type) is added to the options as itself rather than dropped,
        # so opening and closing this panel cannot silently retype the variable.
        options = dict(sorted(objprops.VARIABLE_TYPES.items(), key=lambda pair: pair[1]))
        if values["pvt"] and values["pvt"] not in options:
            options[values["pvt"]] = values["pvt"]
        field_refs[key("pvt")] = ui.select(
            options,
            value=values["pvt"] or objprops.DEFAULT_VARIABLE_TYPE,
            label=translate_string("Type"),
        ).classes("w-full")

        field_refs[key("pvn")] = ui.input(translate_string("Name"), value=values["pvn"]).classes("w-full")

        for tag, label, tooltip in _VARIABLE_CHECKBOXES:
            field_refs[key(tag)] = ui.checkbox(translate_string(label), value=values[tag] == "true")
            with field_refs[key(tag)]:
                ui.tooltip(translate_string(tooltip)).style("white-space: pre-wrap; max-width: 32rem")

        field_refs[key("pvv")] = ui.input(translate_string("Value"), value=values["pvv"]).classes("w-full")
        field_refs[key("pvdn")] = ui.input(translate_string("Display Name"), value=values["pvdn"]).classes("w-full")
        field_refs[key("pvd")] = ui.input(translate_string("Prompt"), value=values["pvd"]).classes("w-full")

        with ui.row().classes("w-full items-center gap-2"):
            exported = ui.input(translate_string("Exported Value"), value=values["exportval"]).classes("flex-1")
            same_as_value = ui.checkbox(
                translate_string("Same as Value"),
                value=values["same_as_value"] == "true",
            )
            field_refs[key("exportval")] = exported
            field_refs[key("same_as_value")] = same_as_value
            with same_as_value:
                ui.tooltip(
                    translate_string(
                        "Under 'Exported Value' if you disable the 'Same as Value' option, you can "
                        "customize what value gets exported when you share the variable with other "
                        "users.\n"
                        "You can keep the 'Exported Value' field blank if you want the export to not "
                        "have a value at all, or you can set the value you wish to always use for "
                        "exports.\n"
                        "If you enable the 'Same as Value' option, the current variable value will be "
                        "used when exporting.",
                    ),
                ).style("white-space: pre-wrap; max-width: 32rem")

            # "Same as Value" is derived rather than stored -- Tasker just writes
            # <exportval> equal to <pvv> (see objprops.variable_values).  Mirroring here,
            # and disabling the field while it is on, is what keeps the two from being
            # made to disagree on screen and then disagreeing again in the XML.
            def mirror() -> None:
                exported.set_enabled(not same_as_value.value)
                if same_as_value.value:
                    exported.value = field_refs[key("pvv")].value

            same_as_value.on_value_change(mirror)
            field_refs[key("pvv")].on_value_change(mirror)
            mirror()

        ui.button(
            translate_string("Remove Variable"),
            icon="delete",
            on_click=lambda: (objprops.remove_variable(props, index), rerender()),
        ).props("flat dense color=negative")


def build_object_properties_dialog(
    self: MyGui,
    kind: str,
    element: defusedxml.ElementTree.Element,
    parent_dialog: ui.dialog,
    on_applied: Callable[[], None] | None = None,
) -> None:
    """The Properties editor, shared by every Add/Edit dialog -- see the section comment.

    Opens OVER the parent, which stays open behind it: the parent still owns the save,
    and closing it out from under the user would lose whatever else they had typed into
    it.  Ok applies onto `element` and closes; Cancel closes, writes nothing, and drops
    any variable that was added but never named (objprops.discard_unnamed_variables --
    Add Variable puts a real element on straight away, the way every other structural
    edit in this app does).
    """
    props = objprops.load_properties(kind, element)
    field_refs: dict = {}
    values = objprops.scalar_values(props)

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[860px] w-full p-6"):
        ui.label(f"{translate_string(kind)} {translate_string('Properties')}").classes(
            "text-xl font-bold text-blue-600",
        )

        for spec in objprops.OBJECT_PROPERTIES.get(kind, ()):
            field_refs[spec.key] = _build_property_widget(spec, values[spec.key])

        ui.label(translate_string(f"{kind} Variables")).classes("text-sm font-bold mt-4")
        ui.label(
            translate_string(
                "The variables you add here will be available in all the profiles and tasks in this "
                "project but will not be available in other projects."
                if kind == objprops.KIND_PROJECT
                else "If there are multiple project/profile/task variables with the same name available "
                "in the same task, the inner-most variable will take precedence.  The order of "
                "precedence is Task > Profile > Project.",
            ),
        ).classes("text-xs text-gray-500 italic")

        variables_container = ui.column().classes("w-full")

        def render_variables() -> None:
            # Rebuilt from scratch after every Add/Remove, not appended to: removing a
            # variable renumbers every one after it, so its field_refs keys (which embed
            # the index) would otherwise go stale and a save would read the wrong panel's
            # values into it.  Same reason guiwins_taskedit.build_edit_task_dialog rebuilds its actions.
            variables_container.clear()
            for stale in [name for name in field_refs if name.startswith("var")]:
                del field_refs[stale]
            with variables_container:
                if not props.variables:
                    ui.label(translate_string("No variables.")).classes("text-xs text-gray-500 italic")
                for index, variable in enumerate(props.variables):
                    _build_variable_panel(props, index, variable, field_refs, render_variables)

        render_variables()

        ui.button(
            translate_string("Add Variable"),
            icon="add",
            on_click=lambda: (objprops.add_variable(props), render_variables()),
        ).props("flat dense")

        # Everything a change here can be in is either the element -- which Add/Remove
        # Variable write to as they happen -- or a widget in field_refs, where the scalars
        # and every variable field wait until Ok reads them.  See editor_state.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(props.element, field_refs))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(
                translate_string("Cancel"),
                on_click=lambda: self.event_handlers.cancel_object_properties_event(props, dialog),
            ).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_object_properties_event(
                    props,
                    field_refs,
                    dialog,
                    on_applied,
                ),
            ).classes("bg-blue-600")

    dialog.open()


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
#
# The two designers that seam mounts are their own modules now -- guiwins_designer_legacy
# and guiwins_designer_v2, over the shared canvas in guiwins_canvas -- and so are the
# element and Show When dialogs each of them opens.  What stays here is the envelope and
# the Scene Properties form below, which renders Legacy argument fields through the Legacy
# designer's own _render_legacy_arg.
# ==========================================
# Which <PropertiesElement> argument slots belong to which part of Tasker's own Scene
# Properties screen.  Transcribed from arg_dict.py's "PropertiesElement" entry, whose eight
# slots are present in all 538 sample Scenes that have one:
#
#   arg0 Property Type   arg1 Orientation   arg2 Background Colour   arg3 Action Bar Style
#   arg4 Title           arg5 Subtitle      arg6 Icon                arg7 Tab Label
#
# arg3-arg7 describe an Activity's title bar and are shown only when arg0 says Activity,
# which is what Tasker does: a Dialog or an Overlay has no action bar to style and no tab
# to label, so offering the five would invite settings that do nothing.
_SCENE_PROPERTY_TYPE_ARG = sceneedit.LEGACY_PROPERTY_TYPE_ARG
_SCENE_ALWAYS_ARGS = ("1", "2")
_SCENE_ACTIVITY_ARGS = ("3", "4", "5", "6", "7")
# Indexes into actiont.lookup_values["PropertyElement1"] == ("Overlay", "Dialog", "Activity").
_SCENE_TYPE_OVERLAY = sceneedit.LEGACY_SCENE_TYPE_OVERLAY
_SCENE_TYPE_ACTIVITY = sceneedit.LEGACY_SCENE_TYPE_ACTIVITY

# The three tabs of Tasker's Scene Properties screen, in its order.  Used as the tabs' NAMES
# (their labels are these run through translate_string), so the selected-tab bookkeeping and
# the tab_panels lookups stay in one language whatever the GUI is showing.
_SCENE_TAB_UI = "UI"
_SCENE_TAB_ACTIONS = "Actions"
_SCENE_TAB_EVENT = "Event"
_SCENE_TABS = (_SCENE_TAB_UI, _SCENE_TAB_ACTIONS, _SCENE_TAB_EVENT)

# Shorter than the Edit Task dialog's own action list: an Event tab's is the bottom half of a
# sub-tab, in a tab, in a dialog that is itself on top of the Scene editor, and a full-height
# list would push the Ok and Cancel buttons off the screen.
_SCENE_EVENT_ACTION_LIST_CLASSES = "w-full h-64 border rounded p-2"


def _scene_properties_summary(scene_element: defusedxml.ElementTree.Element) -> str:
    """A one-line "this is what is set" for the designer's Scene Properties panel, which is
    a signpost to the form rather than the form (see render_scene_properties).

    Reuses sceneview.scene_properties -- the same (label, value) rows the Preview captions
    its picture with -- so the panel and the picture cannot describe the same Scene
    differently.  What the Event and Actions tabs hold is added on the end -- which events
    fire a Task, whether a key press is swallowed, and how many action bar items there are --
    because none of it is something the Preview reports.
    """
    rows = [f"{translate_string(label)}: {value}" for label, value in sceneview.scene_properties(scene_element)]
    properties = sceneedit.legacy_scene_properties(scene_element)
    if properties is not None:
        fired = [event.label for event in sceneedit.LEGACY_SCENE_EVENTS if properties.find(event.tag) is not None]
        if fired:
            rows.append(f"{translate_string('fires a Task on')} {', '.join(fired)}")
        if sceneedit.legacy_stop_event(properties):
            rows.append(translate_string("swallows the key press"))
        if items := sceneedit.legacy_action_items(properties):
            counted = "action bar item" if len(items) == 1 else "action bar items"
            rows.append(f"{len(items)} {translate_string(counted)}")
    return ", ".join(rows) if rows else translate_string("Nothing set.")


def _build_scene_properties_dialog(
    self: MyGui,
    edited_scene: sceneedit.EditableScene,
    field_refs: dict,
    on_closed: Callable[[], None] | None = None,
) -> None:
    """The Scene's own Properties -- its <PropertiesElement> -- laid out the way Tasker's
    own "Scene Properties Edit" screen is: UI, Actions and Event, with Event holding Key,
    Home Tap and Tab Tap.

    THE TABS ARE TASKER'S, NOT THE XML'S.  Nothing in the file is arranged this way -- the
    UI tab is eight <Int/Str/Img sr="argN"> children, Actions is a run of
    <ListElementItem>s, and the three Event tabs are three unrelated tags plus half of a
    <LinkClickFilter>.  sceneedit's LEGACY_SCENE_EVENTS block is where that mapping is
    written down and where the evidence for it sits; this file only draws it.

    SEPARATE FROM build_object_properties_dialog, and not for want of trying to share it.
    A Project/Profile/Task's properties are scalar children plus <ProfileVariable>s, which
    is what objprops models; a Scene's are the eight arguments of a <PropertiesElement>,
    generated from arg_dict.py the same way a Task action's arguments are.  The two have
    no field in common -- no comments, no variables, no shared tag -- so the only honest
    thing to share is the button that opens them (see _build_properties_button's `opener`).

    Everything here writes through to the Scene copy as it is typed, which is what
    _render_legacy_arg does everywhere else in the Legacy designer -- so OK IS NOT WHAT
    MAKES THESE EDITS AND CANCEL CANNOT SIMPLY WALK AWAY FROM THEM.  Ok keeps what is
    already written and applies the one part that is held back: the Event tabs' Task copies
    (see _render_scene_event_task_actions).  Cancel puts the whole <PropertiesElement> back
    the way this dialog found it -- from the snapshot taken below -- and drops those copies
    unapplied.  The four geometry boxes are reverted beside it because they are not in that
    element at all: they drive the Scene dialog's own inputs (see _render_scene_geometry).

    WHAT CANCEL CANNOT TAKE BACK is whatever has already reached the loaded configuration
    under its own button.  "Apply to Task" and "Create Task" both write there when pressed,
    and both say so; Undo is what takes those back.  The Scene dialog behind this one still
    owns the copy either way, so its Cancel discards everything kept here.

    Legacy only.  A Version 2 Scene has no <PropertiesElement> at all -- its equivalents
    live in the declarative layout -- so the button that opens this is not built for one.
    """
    scene_element = edited_scene.scene_element
    # WHAT CANCEL PUTS BACK, taken once, before anything can have been typed.  The
    # properties element carries every field in this dialog except the geometry, and the
    # geometry is not in the element at all -- those boxes write into the Scene dialog's own
    # four inputs -- so it takes a value snapshot of its own.
    properties_snapshot = sceneedit.legacy_properties_snapshot(scene_element)
    geometry_snapshot = {
        key: str(field_refs[key].value) for key, _label in sceneedit.SCENE_DIMENSION_FIELDS if key in field_refs
    }
    # Which tab is on screen, kept across the rebuilds render() does.  Without it, picking a
    # Task or changing Property Type -- both of which rebuild the whole body -- would throw
    # the user back to the UI tab from whichever one they were working in.
    showing = {"tab": _SCENE_TAB_UI, "event": sceneedit.LEGACY_SCENE_EVENTS[0].label}
    # THE TASK EDITS THIS DIALOG IS HOLDING, and why it holds them rather than the panels.
    #
    # The Event panel is rebuilt constantly -- every sub-tab switch, every binding change,
    # every Property Type change goes through render() -- and each rebuild destroys the
    # editor's widgets and, before this, the Task copy behind them.  So an action added under
    # Key and then a click on Tab Tap was an action thrown away, and the only exit this
    # dialog then had threw away whatever was still on screen.  That was the whole of the
    # "actions do not stick" bug.  Ok is that exit now, and it keeps the lot; Cancel is the
    # other one, and dropping these copies is the whole of what it does to them.
    #
    # Both dicts are keyed so that the right copy is found again on the next render, and both
    # hold (EditableTask, field_refs): the copy carries the actions, the widgets carry the
    # argument values until flush_event_task_edits snapshots them onto it.
    pending_tasks: dict[str, tuple] = {}  # events with nothing bound: Tasks not created yet
    bound_tasks: dict[str, tuple] = {}  # events with a Task bound: working copies of it
    # Snapshot callables for the editors CURRENTLY on screen, refilled by every render.
    flushers: list[Callable[[], None]] = []

    def flush_event_task_edits() -> None:
        """Move what is in the Event tab's widgets onto the Task copies behind them.

        Called before anything that destroys those widgets, and before Ok reads the copies.
        The copies outlive the widgets; the widgets do not survive a rebuild.  Not called by
        Cancel: the copies it would write onto are the ones being dropped.
        """
        for flush in flushers:
            flush()
        flushers.clear()

    def scene_task_state() -> dict:
        """What the Event panels are handed so they can find their held copies and register
        their own flusher -- one bundle rather than four parameters threaded three deep.
        """
        return {"pending": pending_tasks, "bound": bound_tasks, "flushers": flushers}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[860px] w-full p-6"):
        ui.label(f"{translate_string('Scene Properties')}: {edited_scene.scene_name}").classes(
            "text-xl font-bold text-blue-600",
        )
        # Built and first filled inside the card, the way every other dialog in this file
        # does it -- a container filled after the `with` block has closed is not attached to
        # the dialog being opened.  It is emptied and refilled rather than rebuilt, because
        # Property Type changes what is in it (see render).
        dialog_body = ui.column().classes("w-full")

        def render() -> None:
            """Rebuilt in full whenever Property Type changes, because that is what decides
            which fields exist at all.  Safe to do from a dropdown's own handler -- there is
            no caret to lose, and the Legacy designer's Task-binding selects already rebuild
            themselves the same way; a text field could not (see _render_legacy_arg).
            """
            flush_event_task_edits()
            dialog_body.clear()
            with dialog_body:
                properties = sceneedit.legacy_scene_properties(scene_element)
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
                        on_click=add_properties,
                    ).props("dense flat")
                    return

                args = {arg.arg_id: arg for arg in sceneedit.legacy_element_args(properties)}
                property_type = args.get(_SCENE_PROPERTY_TYPE_ARG)

                # Named tabs, not label-valued ones: ui.tab's value defaults to its label,
                # and a translated label would make `showing` unreadable in every language
                # but English and stop matching the moment the language changed.
                with ui.tabs(
                    value=showing["tab"],
                    on_change=lambda event: showing.__setitem__("tab", str(event.value)),
                ).classes("w-full") as tabs:
                    for name in _SCENE_TABS:
                        ui.tab(name, label=translate_string(name))
                with ui.tab_panels(tabs, value=showing["tab"]).classes("w-full"):
                    with ui.tab_panel(_SCENE_TAB_UI):
                        _render_scene_ui_tab(args, property_type, scene_element, field_refs, render)
                    with ui.tab_panel(_SCENE_TAB_ACTIONS):
                        _render_scene_actions_tab(self, properties, render)
                    with ui.tab_panel(_SCENE_TAB_EVENT):
                        _render_scene_event_tab(
                            self,
                            properties,
                            showing,
                            render,
                            scene_task_state(),
                            edited_scene.scene_name,
                        )

        def add_properties() -> None:
            sceneedit.legacy_add_scene_properties(scene_element)
            render()

        render()

        def keep_and_close() -> None:
            """Ok keeps everything: the Scene's own fields are already written through, and the
            Task edits -- the one part that could not be, since a Task is not the Scene and the
            action editor collects its argument values in widgets -- are applied here.

            Stays open if anything is rejected, with the errors notified and the edits still on
            screen to fix.  Closing on a rejection would be the same bug in a new place.
            """
            flush_event_task_edits()
            properties = sceneedit.legacy_scene_properties(scene_element)

            def bind(event_tag: str, new_task_id: str) -> None:
                if properties is not None:
                    sceneedit.legacy_set_task_binding(properties, event_tag, new_task_id)

            if not self.event_handlers.keep_scene_event_task_edits(bound_tasks, pending_tasks, bind):
                render()
                return
            dialog.close()
            if on_closed:
                on_closed()

        def discard_and_close() -> None:
            """Cancel puts the properties back as they were and closes, applying nothing.

            The Task copies are dropped simply by never being applied -- they are held here and
            nowhere else, so letting them go is the whole of it.  Their flushers go with them:
            each one writes widget values onto a copy that is about to be thrown away, and
            running them first would only make the discarding slower.
            """
            flushers.clear()
            bound_tasks.clear()
            pending_tasks.clear()
            self.event_handlers.discard_scene_properties_event(
                scene_element,
                properties_snapshot,
                geometry_snapshot,
                field_refs,
            )
            dialog.close()
            if on_closed:
                on_closed()

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            cancel_button = ui.button(translate_string("Cancel"), on_click=discard_and_close).props("outline")
            with cancel_button:
                ui.tooltip(
                    translate_string(
                        "Puts these properties back the way they were when this window opened, and "
                        "drops the actions of any Task edited under the Event tab.\n"
                        "A Task already put into the configuration by its own button -- 'Apply to "
                        "Task', or 'Create Task' -- stays there. Undo takes those back.",
                    ),
                ).style("white-space: pre-wrap")
            ok_button = ui.button(translate_string("Ok"), on_click=keep_and_close).classes("bg-blue-600")
            with ok_button:
                ui.tooltip(
                    translate_string(
                        "Keeps everything, including the actions of any Task edited under the Event "
                        "tab.\n"
                        "A Task composed under an event that had none is created and bound if you put "
                        "any actions in it. Undo takes a Task edit back.",
                    ),
                ).style("white-space: pre-wrap")

    dialog.open()


def _render_scene_ui_tab(
    args: dict,
    property_type: taskedit.EditableArg | None,
    scene_element: defusedxml.ElementTree.Element,
    field_refs: dict,
    rerender: Callable[[], None],
) -> None:
    """The UI tab: how the Scene is put on screen, which way up, and what it is dressed in.

    Property Type comes first and re-renders the tab, because it decides which of the rest
    are shown -- which is what the guide means by "the Property Type parameter in the UI tab
    determines which properties are shown for configuration".

    Geometry is shown for EVERY type.  The guide restricts exactly one group -- "the Action
    Bar Style, Title, Subtitle, Icon and Tab Labels are only relevant to Activity scenes" --
    and says nothing of the sort about Geometry, which used to be hidden for anything but an
    Overlay here.  Hiding it left a Dialog's size editable only from the Scene dialog behind
    this one, which is the same four numbers by another route.
    """
    if property_type is not None:
        _render_legacy_arg(property_type, rerender, name_editable=True)

    current_type = property_type.current_value if property_type is not None else ""

    _render_scene_geometry(scene_element, field_refs)

    for arg_id in _SCENE_ALWAYS_ARGS:
        if arg_id in args:
            _render_legacy_arg(args[arg_id], lambda: None, name_editable=True)

    if current_type == _SCENE_TYPE_ACTIVITY:
        ui.label(translate_string("Action bar")).classes("text-sm font-bold mt-3")
        for arg_id in _SCENE_ACTIVITY_ARGS:
            if arg_id in args:
                _render_legacy_arg(args[arg_id], lambda: None, name_editable=True)
                # The two that are not just decoration: each of them turns an Event tab on.
                if arg_id == sceneedit.LEGACY_ICON_ARG:
                    ui.label(
                        translate_string(
                            "The home icon at the top left of the action bar. Tapping it fires the "
                            "Event tab's Home Tap Task.",
                        ),
                    ).classes("text-xs text-gray-500 italic")
                elif arg_id == sceneedit.LEGACY_TAB_LABELS_ARG:
                    ui.label(
                        translate_string(
                            "A comma-separated list of the tabs to show in the action bar. Selecting "
                            "one fires the Event tab's Tab Tap Task.",
                        ),
                    ).classes("text-xs text-gray-500 italic")
    elif any(arg_id in args for arg_id in _SCENE_ACTIVITY_ARGS):
        ui.label(
            translate_string(
                "Action Bar Style, Title, Subtitle, Icon and Tab Labels apply to an Activity only. "
                "They are still stored, and are shown if you switch Property Type to Activity.",
            ),
        ).classes("text-xs text-gray-500 italic mt-2")


def _render_scene_geometry(
    scene_element: defusedxml.ElementTree.Element,
    field_refs: dict,
) -> None:
    """Geometry: the pixel size the Scene is laid out at, in the Portrait/Landscape pairs
    Tasker asks for.

    These are NOT properties of the <PropertiesElement> -- they are the Scene's own
    <widthPort>/<heightPort>/<widthLand>/<heightLand> children, and the Scene dialog behind
    this one already has an input for each.  So these DRIVE THOSE WIDGETS rather than
    writing the XML: userintr._apply_scene_field_values reads exactly those four field_refs
    entries at save time, so a value written straight to the element here would be
    overwritten by whatever the dialog's own boxes still held.  One source of truth, and
    the two stay level whichever is typed into.

    Shown for every Property Type -- see _render_scene_ui_tab, which is where that decision
    is argued.  Tasker itself hides this pair in Beginner Mode; MapTasker has no such mode,
    and an editor that hid the numbers a Scene is actually laid out at would be hiding the
    thing its canvas is drawn from.
    """
    ui.label(translate_string("Geometry")).classes("text-sm font-bold mt-3")
    ui.label(translate_string("-1 means this orientation has no layout of its own.")).classes(
        "text-xs text-gray-500 italic",
    )

    labels = dict(sceneedit.SCENE_DIMENSION_FIELDS)

    def bind(key: str) -> None:
        # field_refs always carries all four for a Legacy Scene -- _build_scene_editor_body
        # builds them before the designer this dialog is reached from, and only that path
        # opens it.  Falling back to the element's own text keeps the box showing the truth
        # if that ever stops being so, rather than showing a blank.
        source = field_refs.get(key)
        value = str(source.value) if source is not None else scene_element.findtext(key, sceneedit.UNSET_DIMENSION)
        box = ui.input(translate_string(labels[key]), value=value).classes("w-40").props("dense")
        if source is not None:
            box.on_value_change(lambda event, widget=source: setattr(widget, "value", str(event.value)))

    for orientation, keys in (
        ("Portrait", ("widthPort", "heightPort")),
        ("Landscape", ("widthLand", "heightLand")),
    ):
        with ui.row().classes("w-full items-center gap-2"):
            ui.label(translate_string(orientation)).classes("text-xs w-24 shrink-0")
            for key in keys:
                bind(key)


def _render_scene_actions_tab(
    self: MyGui,
    properties: defusedxml.ElementTree.Element,
    rerender: Callable[[], None],
) -> None:
    """The Actions tab: the items on an Activity's action bar.

    Each row is one <ListElementItem> and carries the guide's three controls -- an icon, a
    label, and the action to run when the item is tapped -- plus the reordering and deletion
    Tasker does by dragging.  Buttons rather than a drag handle: the rest of this dialog is
    a form, and a drag target inside a scrolled tab panel inside a dialog inside the Scene
    editor is a lot of nesting for a list that is never more than a handful of rows.

    ONLY RELEVANT FOR ACTIVITY SCENES, as the guide says -- but existing items are shown
    whatever the Property Type is, with a note.  An Overlay that once was an Activity still
    has its items in the file, and an editor that hid them would quietly drop them on the
    next save.

    Everything here writes through to the Scene copy as it is typed, like the UI tab.  The
    item's action is edited through the same EditableArg model the element inspector uses
    (sceneedit.legacy_action_item_args), so its fields behave as they do everywhere else.
    """
    items = sceneedit.legacy_action_items(properties)
    is_activity = sceneedit.legacy_scene_type(properties) == _SCENE_TYPE_ACTIVITY

    if not is_activity:
        ui.label(
            translate_string(
                "Action bar items apply to an Activity only. They are still stored, and are shown "
                "if you switch Property Type to Activity.",
            ),
        ).classes("text-xs text-gray-500 italic")

    ui.label(
        translate_string(
            "Where an item ends up is decided by what you give it: an icon alone is always in the "
            "main bar, an icon and a label are shown there if there is room, and a label alone is "
            "always in the overflow menu (the 3 dots at the top right in Tasker).",
        ),
    ).classes("text-xs text-gray-500 italic")

    if not items:
        ui.label(translate_string("No action bar items.")).classes("text-xs text-gray-500 italic mt-2")

    last = len(items) - 1
    for item in items:
        header = f"{item.index}: {item.label or translate_string('(no label)')} -- {item.action_name}"
        with ui.expansion(header).classes("w-full"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(
                    icon="arrow_upward",
                    on_click=lambda _e=None, sr=item.sr: _move_scene_action_item(properties, sr, -1, rerender),
                ).props("dense flat size=sm").set_enabled(item.index > 0)
                ui.button(
                    icon="arrow_downward",
                    on_click=lambda _e=None, sr=item.sr: _move_scene_action_item(properties, sr, 1, rerender),
                ).props("dense flat size=sm").set_enabled(item.index < last)
                ui.button(
                    translate_string("Delete"),
                    icon="delete",
                    on_click=lambda _e=None, sr=item.sr: _remove_scene_action_item(properties, sr, rerender),
                ).props("dense flat size=sm color=negative")
                ui.label(translate_string(item.placement)).classes("text-xs text-gray-500 italic")

            with ui.row().classes("w-full items-center gap-2"):
                icon_field = (
                    ui.input(
                        translate_string("Icon"),
                        value=sceneedit.legacy_action_item_icon(item),
                    )
                    .props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}")
                    .classes("flex-1")
                )
                icon_field.on_value_change(
                    lambda event, it=item: sceneedit.legacy_set_action_item_icon(it, str(event.value or "")),
                )
                ui.button(
                    translate_string("Pick"),
                    icon="image",
                    on_click=lambda _e=None, field=icon_field: _build_tasker_icon_picker_dialog(field, self),
                ).props("flat dense size=sm")

            ui.input(
                translate_string("Label"),
                value=item.label,
                on_change=lambda event, it=item: sceneedit.legacy_set_action_item_label(it, str(event.value or "")),
            ).props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}").classes("w-full")

            item_args = sceneedit.legacy_action_item_args(item)
            if item.action_element is None:
                ui.label(translate_string("This item has no action.")).classes("text-xs text-gray-500 italic")
            elif not item_args:
                ui.label(
                    f"{item.action_name}: {translate_string('no editable arguments.')}",
                ).classes("text-xs text-gray-500 italic")
            else:
                ui.label(f"{translate_string('Action')}: {item.action_name}").classes("text-sm font-bold mt-2")
                for arg in item_args:
                    _render_legacy_arg(arg, lambda: None, name_editable=True)

    _render_scene_action_item_picker(self, properties, rerender)


def _move_scene_action_item(
    properties: defusedxml.ElementTree.Element,
    sr: str,
    offset: int,
    rerender: Callable[[], None],
) -> None:
    sceneedit.legacy_move_action_item(properties, sr, offset)
    rerender()


def _remove_scene_action_item(
    properties: defusedxml.ElementTree.Element,
    sr: str,
    rerender: Callable[[], None],
) -> None:
    sceneedit.legacy_remove_action_item(properties, sr)
    rerender()


def _render_scene_action_item_picker(
    self: MyGui,
    properties: defusedxml.ElementTree.Element,
    rerender: Callable[[], None],
) -> None:
    """Tasker's plus button at the bottom of the Actions tab: pick the action the new item
    runs, and the item is built around it.

    The same search/filter picker the Task editors use, over the same list -- what can go on
    an action bar is what can be added to a Task, because it is synthesized by the same code
    (sceneedit.legacy_add_action_item -> taskedit.build_synthesized_args).  An action that
    cannot be synthesized is greyed out with its reason, exactly as it is there.
    """
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions()})

    ui.label(translate_string("Add an action bar item")).classes("text-sm font-bold mt-3")
    with ui.row().classes("w-full gap-4"):
        search_input = ui.input(translate_string("Search actions")).classes("flex-1")
        category_select = ui.select(["All", *category_names], value="All").classes("w-48")
    picker_container = ui.column().classes("w-full")

    def add_item(action_key: str) -> None:
        added = sceneedit.legacy_add_action_item(properties, action_key)
        if isinstance(added, list):
            for error in added:
                ui.notify(error, type="negative")
            return
        rerender()

    def refresh_picker(_event: ui.event | None = None) -> None:
        picker_container.clear()
        rows = taskedit.search_addable_actions(search_input.value, category_select.value)
        with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
            for row in rows:
                if row["addable"]:
                    ui.button(
                        f"{row['name']} ({row['category_name']})",
                        on_click=lambda r=row: add_item(r["action_key"]),
                    ).props("flat align=left dense").classes("w-full justify-start")
                else:
                    with ui.column().classes("w-full gap-0"):
                        ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                        _render_addability_reason(self, row["reason"], refresh_picker)

    search_input.on_value_change(refresh_picker)
    category_select.on_value_change(refresh_picker)
    refresh_picker()


def _render_scene_event_tab(
    self: MyGui,
    properties: defusedxml.ElementTree.Element,
    showing: dict,
    rerender: Callable[[], None],
    task_state: dict,
    scene_name: str,
) -> None:
    """The Event tab: Key, Home Tap and Tab Tap, as Tasker's own sub-tabs.

    ONE SUB-TAB IS BUILT AT A TIME, into a container this refills, rather than three
    ui.tab_panels.  Each one carries the bound Task's whole action editor
    (_build_task_action_editor -- a picker over every addable action plus a row per
    argument), and building three of those to show one of them would cost three times the
    widgets and put three "Add an action" pickers on the page at once.

    `showing` carries the selected sub-tab out to the caller so it survives the full-body
    rebuild that binding a Task triggers, and `task_state` carries the Task copies for the
    same reason: switching sub-tab destroys this panel, and everything edited in it would go
    too.  See _build_scene_properties_dialog, which owns both.
    """
    for name, meaning in sceneedit.LEGACY_SCENE_EVENT_COMMON_VARIABLES:
        ui.label(f"{name} -- {translate_string(meaning)}").classes("text-xs text-gray-500 italic")

    events = {event.label: event for event in sceneedit.LEGACY_SCENE_EVENTS}
    if showing["event"] not in events:
        showing["event"] = sceneedit.LEGACY_SCENE_EVENTS[0].label

    with ui.tabs(value=showing["event"]).classes("w-full mt-2") as event_tabs:
        for event in sceneedit.LEGACY_SCENE_EVENTS:
            ui.tab(event.label, label=translate_string(event.label))
    event_body = ui.column().classes("w-full")

    def render_event() -> None:
        # The widgets about to be destroyed are the only place this sub-tab's argument edits
        # live; the Task copy behind them survives, so move them onto it first.
        for flush in task_state["flushers"]:
            flush()
        task_state["flushers"].clear()
        event_body.clear()
        with event_body:
            _render_scene_event(
                self,
                properties,
                events[showing["event"]],
                rerender,
                task_state,
                scene_name,
            )

    event_tabs.on_value_change(
        lambda event: (showing.__setitem__("event", str(event.value)), render_event()),
    )
    render_event()


def _render_scene_event(
    self: MyGui,
    properties: defusedxml.ElementTree.Element,
    event: sceneedit.LegacySceneEvent,
    rerender: Callable[[], None],
    task_state: dict | None = None,
    scene_name: str = "",
) -> None:
    """One Event sub-tab: when it fires, the Task it fires, and what that Task can read.

    The Task binding is the same model the element inspector's Tasks section uses
    (sceneedit.legacy_set_task_binding / legacy_clear_task_binding) rather than a second way
    of pointing at a Task -- these three tags are ordinary Scene Task bindings that happen to
    hang off the Scene's properties instead of one of its elements.

    WHICH TASK IS BOUND, and picking a different one, are two rows rather than one control:
    a read-only field naming what fires now, and _render_task_picker below it.  See that
    function for why a dropdown was the wrong shape for a list this size.

    A binding is shown and editable even when Tasker would not offer this event for this
    Scene (an <iconclickTask> on something that is no longer an Activity, say); the reason
    is printed above it instead.  Hiding what the file holds is how an editor comes to
    disagree with the file -- see sceneedit.legacy_scene_event_availability.
    """
    if unavailable := sceneedit.legacy_scene_event_availability(properties, event):
        ui.label(translate_string(unavailable)).classes("text-xs text-amber-600 italic")
    ui.label(translate_string(event.description)).classes("text-xs text-gray-500 italic")

    bound = properties.find(event.tag)
    task_id = (bound.text or "").strip() if bound is not None else ""
    anonymous = task_id.startswith(sceneedit.LEGACY_ANONYMOUS_TASK_PREFIX)
    # Named off the id rather than off the tables' name, so a Task whose entry carries a
    # blank name still reads as bound.  taskerd normally fills a made-up display name in for
    # an unnamed Task, but a caller that built the tables without that pass would otherwise
    # make a real binding read as "Nothing".
    all_tasks = PrimeItems.tasker_root_elements.get("all_tasks", {})
    entry = all_tasks.get(task_id)
    task_name = ((entry or {}).get("name") or f"Task {task_id}") if task_id else ""

    def set_binding(picked: str) -> None:
        if not picked:
            return
        picked_id = sceneedit.legacy_task_id_for_name(picked)
        if not picked_id:
            ui.notify(f"No Task named '{picked}' in this backup.", type="negative")
            return
        sceneedit.legacy_set_task_binding(properties, event.tag, picked_id)
        rerender()

    with ui.row().classes("w-full items-center gap-2 mt-2"):
        ui.label(translate_string("Task")).classes("text-xs w-28 shrink-0")
        if anonymous:
            showing = translate_string("(anonymous Task, stored in the Scene)")
        elif task_id:
            showing = task_name
        else:
            showing = translate_string("Nothing -- this event fires no Task.")
        current = ui.input(value=showing).props("readonly dense").classes("flex-1")
        if anonymous:
            with current:
                ui.tooltip(
                    translate_string(
                        "Tasker keeps this Task inside the Scene and nowhere else, so it has no name "
                        "and cannot be pointed somewhere else without losing it. It is carried "
                        "through untouched.",
                    ),
                ).style("white-space: pre-wrap")
        elif task_id:
            ui.button(
                icon="close",
                on_click=lambda _e=None: (
                    sceneedit.legacy_clear_task_binding(properties, event.tag),
                    rerender(),
                ),
            ).props("dense flat size=sm color=negative").tooltip(
                translate_string("Stop firing anything on this event."),
            )

    if not anonymous:
        _render_task_picker(set_binding)

    if event.tag == sceneedit.LEGACY_KEY_TASK_TAG:
        _render_scene_key_filter(properties)

    for name, meaning in event.variables:
        ui.label(f"{name} -- {translate_string(meaning)}").classes("text-xs text-gray-500 italic")

    _render_scene_event_task_actions(
        self,
        properties,
        event,
        {"pending": {}, "bound": {}, "flushers": []} if task_state is None else task_state,
        scene_name,
        rerender,
    )


def _render_task_picker(on_pick: Callable[[str], None]) -> None:
    """ "Pick a Task", built the way "Add an action" is: a search box, a filter, and a
    scrolling list of one clickable row per match.

    IT REPLACED A DROPDOWN, and the list is why.  A `ui.select` of every Task in the backup
    is one control holding several hundred entries -- 352 in this repo's own backup_full.xml
    -- with the owning Project nowhere in sight, so two Tasks called "Setup" in different
    Projects are indistinguishable and the only way through is to already know the name.  The
    action picker solved the same problem for the ~500 action types, and this is that
    solution applied to the other long list: type part of a name, or narrow to one Project,
    and click the row.

    The Project filter is the Task-side counterpart of the action picker's Category filter
    -- taskedit.search_pickable_tasks does the matching, on the same terms.  A Task no
    Project owns is listed and filterable under "No Project", the same words
    tasks.get_project_for_solo_task uses.

    `on_pick` is handed the chosen Task's NAME, not its id: that is what
    sceneedit.legacy_task_id_for_name and every other Task-by-name path in this app take, and
    resolving it at the callback keeps this function ignorant of what the caller does with it.
    """
    rows = taskedit.list_pickable_tasks()
    projects = sorted({row["project_name"] for row in rows})

    ui.label(translate_string("Pick a Task")).classes("text-sm font-bold mt-2")
    if not rows:
        ui.label(translate_string("There are no Tasks in this configuration.")).classes(
            "text-xs text-gray-500 italic",
        )
        return

    with ui.row().classes("w-full gap-4"):
        search_input = ui.input(translate_string("Search Tasks")).classes("flex-1")
        project_select = ui.select(["All", *projects], value="All").classes("w-48")
    picker_container = ui.column().classes("w-full")

    def refresh_picker(_event: ui.event | None = None) -> None:
        picker_container.clear()
        matches = taskedit.search_pickable_tasks(search_input.value, project_select.value)
        with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
            if not matches:
                ui.label(translate_string("No Task matches.")).classes("text-xs text-gray-500 italic")
            for row in matches:
                ui.button(
                    f"{row['name']} ({row['project_name']})",
                    on_click=lambda r=row: on_pick(r["name"]),
                ).props("flat align=left dense").classes("w-full justify-start")

    search_input.on_value_change(refresh_picker)
    project_select.on_value_change(refresh_picker)
    refresh_picker()


def _render_scene_key_filter(properties: defusedxml.ElementTree.Element) -> None:
    """The Key event's own filter: which keys the Scene handles, and whether it swallows them.

    Both live in the Scene's <LinkClickFilter> -- see sceneedit.legacy_set_key_filter, which
    also explains why a tag named urlMatch is holding a list of key names.
    """
    keys = (
        ui.input(
            translate_string("Keys"),
            value=sceneedit.legacy_key_filter(properties),
        )
        .props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}")
        .classes("w-full mt-2")
    )
    keys.on_value_change(lambda event: sceneedit.legacy_set_key_filter(properties, str(event.value or "")))
    with keys:
        ui.tooltip(
            translate_string(
                "A slash-separated list of the keys to handle -- by name or by code, e.g. "
                "back/78/a. Any other key is passed on to the system.\n"
                "Leave it empty to handle every key.",
            ),
        ).style("white-space: pre-wrap")

    stop_event = ui.checkbox(
        translate_string("Stop Event"),
        value=sceneedit.legacy_stop_event(properties),
        on_change=lambda event: sceneedit.legacy_set_stop_event(properties, enabled=bool(event.value)),
    )
    with stop_event:
        ui.tooltip(
            translate_string(
                "Any key handled by the scene is not passed on to the system -- how a Scene keeps "
                "the back key from closing it.\n"
                "Written the way Tasker writes it: a <stopEvent> inside the Scene's "
                "<LinkClickFilter>, created when this is ticked and taken away again when it is "
                "unticked and nothing else is left in it.",
            ),
        ).style("white-space: pre-wrap")


def _render_scene_event_task_actions(
    self: MyGui,
    properties: defusedxml.ElementTree.Element,
    event: sceneedit.LegacySceneEvent,
    task_state: dict,
    scene_name: str,
    rerender: Callable[[], None],
) -> None:
    """The actions this event runs, edited here rather than in a dialog of its own -- the
    same editor the Edit Task dialog is made of.

    THERE IS ALWAYS AN EDITOR, whether or not a Task is bound yet.  An event with nothing
    bound gets a brand-new Task, composed in place -- see _render_scene_event_new_task.

    NOTHING TYPED IN HERE IS THROWN AWAY BY NAVIGATION.  The Task copy is held by the dialog
    (task_state), not by this panel, so it survives the rebuild that every sub-tab switch,
    binding change and Property Type change causes -- and the widgets' own values are moved
    onto it by the flusher registered below, just before they are destroyed.  Both halves are
    needed: the copy carries the actions, the widgets carry the argument values.

    WHICH TASK, when one is bound.  Whatever the event's tag points at, resolved BY ID
    (taskedit.load_task_for_edit_by_id): the binding stores an id, and an unnamed Task's
    displayed name is one taskerd invented from its first action, which is not a name to look
    a Task up by.  The copy is keyed by tag AND id, so repointing the event at a different
    Task starts a fresh copy instead of showing the old Task's actions under the new name.

    An ANONYMOUS Task (a negative id, kept inside the Scene and nowhere else) gets no editor.
    It is not in the Task tables, so there is nothing to load, nothing to write back into, and
    replacing it would destroy the only copy.

    WHERE IT LANDS.  Ok applies every held copy over the live Task
    (userintr.keep_scene_event_task_edits), and "Apply to Task" does the same for this one
    without closing; Cancel drops the copies unapplied.  Either way it is the loaded
    configuration that changes, not the Scene: neither this dialog's Cancel nor the Scene
    dialog's takes back an edit that has already landed there, and Undo does.
    """
    bound = properties.find(event.tag)
    task_id = (bound.text or "").strip() if bound is not None else ""

    ui.separator().classes("mt-3")
    ui.label(
        f"{translate_string('Actions of the')} {translate_string(event.label)} {translate_string('Task')}",
    ).classes("text-sm font-bold mt-2")

    if task_id.startswith(sceneedit.LEGACY_ANONYMOUS_TASK_PREFIX):
        ui.label(
            translate_string(
                "This Task is stored inside the Scene and is not in the Task list, so its actions "
                "cannot be edited here. It is carried through untouched.",
            ),
        ).classes("text-xs text-gray-500 italic")
        return

    if not task_id:
        _render_scene_event_new_task(self, properties, event, task_state, scene_name, rerender)
        return

    held_key = f"{event.tag}:{task_id}"
    held = task_state["bound"].get(held_key)
    if held is None:
        edited_task = taskedit.load_task_for_edit_by_id(task_id)
        if edited_task is None:
            ui.label(
                f"{translate_string('Task')} {task_id} "
                f"{translate_string('is not in this backup, so there are no actions to show.')}",
            ).classes("text-xs text-gray-500 italic")
            return
    else:
        edited_task = held[0]

    field_refs: dict = {}
    task_state["bound"][held_key] = (edited_task, field_refs)
    task_state["flushers"].append(
        lambda: self.event_handlers.stash_scene_event_task_edits(edited_task, field_refs),
    )

    _build_task_action_editor(self, edited_task, field_refs, list_classes=_SCENE_EVENT_ACTION_LIST_CLASSES)

    apply_button = (
        ui.button(
            translate_string("Apply to Task"),
            icon="task_alt",
            on_click=lambda: self.event_handlers.apply_scene_key_task_event(edited_task, field_refs),
        )
        .props("dense")
        .classes("mt-2 bg-blue-600")
    )
    with apply_button:
        ui.tooltip(
            translate_string(
                "Puts these action edits into the loaded configuration now, without closing -- the "
                "same as 'Ok' in the Edit Task dialog.  Ok does it for you here too, so this is "
                "only for keeping them mid-edit.\n"
                "Nothing is written to a file and nothing is sent to Android. This Task is not part "
                "of the Scene, so neither this window's Cancel nor the Scene dialog's takes these "
                "edits back once they have landed. Undo does.",
            ),
        ).style("white-space: pre-wrap")


def _render_scene_event_new_task(
    self: MyGui,
    properties: defusedxml.ElementTree.Element,
    event: sceneedit.LegacySceneEvent,
    task_state: dict,
    scene_name: str,
    rerender: Callable[[], None],
) -> None:
    """Compose a brand-new Task for an event that has none, and create it in place.

    Add Task's own two halves without Add Task's dialog: a Name and the action editor over an
    UNREGISTERED EditableTask, then a button that registers it and points the event at it in
    one undo step (userintr.create_scene_event_task_event).  Ok does the same for any such
    Task that has actions in it, so the button is for creating one without closing -- and
    Cancel does not, so an unpressed button is a Task that never existed.

    Until it is created the Task exists nowhere but this dialog -- nothing is in the Task
    tables and nothing is bound -- and an empty one is never created, since that is what an
    untouched sub-tab leaves behind.

    THE TASK IS HELD BY THE DIALOG, not built here, so the actions added to it survive this
    panel being rebuilt -- and it is rebuilt often.  Keyed by event tag, so composing a Key
    Task and a Tab Tap Task at the same time keeps them apart.

    A DEFAULT NAME rather than a blank one, because a name is required and "Reminder Key" is
    what this Task is.  It is a plain field: a name another Task already has is refused by
    create_scene_event_task_event rather than quietly given a suffix.
    """
    if PrimeItems.xml_root is None:
        ui.label(
            translate_string("Load a Tasker configuration first -- a new Task needs one to get an id."),
        ).classes("text-xs text-gray-500 italic")
        return

    pending = task_state["pending"]
    held = pending.get(event.tag)
    if held is None:
        default_name = f"{scene_name} {event.label}".strip() or event.label
        # The ids of the other sub-tabs' Tasks-in-progress are spoken for even though nothing
        # has registered them: without this all three would be handed the same id, and
        # creating the second would overwrite the first in the Task tables.
        created = taskedit.create_new_task(
            default_name,
            "100",
            reserved_ids={task.task_id for task, _refs in pending.values()},
        )
        if isinstance(created, str):  # No backup loaded -- create_new_task's own message.
            ui.label(translate_string(created)).classes("text-xs text-gray-500 italic")
            return
        edited_task = created
    else:
        edited_task = held[0]

    ui.label(
        translate_string(
            "Nothing is bound yet, so these actions go into a new Task. It is created, and this "
            "event pointed at it, when you press the button below or Ok. Cancel discards it.",
        ),
    ).classes("text-xs text-gray-500 italic")

    field_refs: dict = {
        "name": ui.input(
            translate_string("New Task Name"),
            value=(held[1]["name"].value if held else edited_task.task_element.findtext("nme", "")),
        ).classes("w-full"),
        "priority": ui.input(
            translate_string("Priority"),
            value=(held[1]["priority"].value if held else edited_task.task_element.findtext("pri", "100")),
        ).classes("w-32"),
        # Attach it to the Project the Scene itself belongs to, the way the top-level Add Task
        # attaches to the Project that was selected before it opened.  A Task in no Project's
        # <tids> runs but appears in no generated view of any Project.  "" when the Scene
        # belongs to none, which _finish_new_task reads as "nothing to attach to".
        "target_project_name": sceneedit.project_owning_scene(scene_name),
    }
    pending[event.tag] = (edited_task, field_refs)
    task_state["flushers"].append(
        lambda: self.event_handlers.stash_scene_event_task_edits(edited_task, field_refs),
    )

    _build_task_action_editor(self, edited_task, field_refs, list_classes=_SCENE_EVENT_ACTION_LIST_CLASSES)

    def create_task() -> None:
        def bind(new_task_id: str) -> None:
            sceneedit.legacy_set_task_binding(properties, event.tag, new_task_id)

        if self.event_handlers.create_scene_event_task_event(edited_task, field_refs, bind):
            # It is a real Task now and the event points at it, so the next render loads it
            # from the tables like any other binding.
            pending.pop(event.tag, None)
            rerender()

    create_button = (
        ui.button(
            translate_string("Create Task"),
            icon="add_task",
            on_click=create_task,
        )
        .props("dense")
        .classes("mt-2 bg-blue-600")
    )
    with create_button:
        ui.tooltip(
            translate_string(
                "Adds this Task to the loaded configuration and points this event at it, the same "
                "as 'Ok' in the Add Task dialog -- nothing is written to a file and nothing is sent "
                "to Android.  Ok does it for you too, so this is only for creating it without "
                "closing.\n"
                "Until then the Task exists only in this window and Cancel discards it. Afterwards "
                "it is a Task like any other -- Cancel takes the binding back but not the Task, and "
                "Undo takes both.",
            ),
        ).style("white-space: pre-wrap")


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
                ui.input(
                    translate_string(label),
                    value=scene_element.findtext(key, sceneedit.UNSET_DIMENSION),
                )
                .classes("w-36")
                .props("dense")
            )
    ui.label(translate_string("-1 means this orientation has no layout of its own.")).classes(
        "text-xs text-gray-500 italic",
    )

    # The same button Project/Profile/Task grow, opening the Scene's own form -- see
    # _build_scene_properties_dialog for why the form could not be shared even though the
    # button is.  Legacy only: a V2 Scene has no <PropertiesElement>, and the V2 branch
    # above has already returned by here.
    #
    # No on_applied: every Scene save path calls sceneedit.apply_edited_scene_to_live_tree
    # BEFORE rendering by name, so the working copy this writes to is what gets saved.  That
    # is the difference from Edit Project, whose by-name saves do not apply first and so
    # need the live-tree mirror.
    _build_properties_button(
        _self,
        objprops.KIND_SCENE,
        scene_element,
        dialog,
        opener=lambda: _build_scene_properties_dialog(_self, edited_scene, field_refs),
    )

    _build_legacy_designer(_self, edited_scene, field_refs)


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
                        "match its Tasker server settings.\n\n"
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
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
    with ui.dialog().props("persistent") as android_dialog, ui.card().classes("min-w-[350px] p-6"):
        ui.label(translate_string("Save Scene To Android Device")).classes("text-lg font-bold text-blue-600")
        android_field_refs = _android_device_fields(self)
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
                        "Watch the Android device while this runs: Tasker asks you to authorize the "
                        "connection several times for one save, and a prompt left untapped fails it.",
                    ),
                ).style("white-space: pre-wrap")
            # The Profile and Project dialogs' pair, for a Scene -- see
            # guiwins_profedit.build_save_profile_to_android_dialog for why these are two buttons.
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
    self: MyGui,
    item_type: str,
    current_name: str,
    on_rename: Callable[[str, ui.dialog], None],
) -> None:
    """Prompts for a new name for a Project/Profile/Task, opened by the "Rename"
    button in that item's Edit dialog.

    The Edit dialogs' own Name field is read-only (see guiwins_taskedit.build_edit_task_dialog),
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


@contextlib.contextmanager
def opening_view_in_a_new_window(gui: MyGui) -> Iterator[None]:
    """Turn "Open View In New Window" on for the duration of one jump, then put it back.

    WHAT IT IS FOR.  A Map view IS a popout window, opened by userintr._open_popout_window
    under a name popout_window_name keeps STABLE while that option is off.  A stable name is
    what makes window.open reuse a tab -- which is the whole point of the option, and the
    wrong behaviour for a jump launched from a dialog, because the tab it reuses is the tab
    the dialog is in.  The dialog goes, and with it whatever it was holding.

    THE REAL SETTING, and it does survive being put back.  The attribute is bound two-way to
    its checkbox, so the obvious worry is that the restore loses a race with NiceGUI's
    binding loop.  It does not, and the reason is the order bind() registers its two links:
    bind_from goes first, so _refresh_step propagates gui-attribute -> checkbox BEFORE the
    checkbox -> gui-attribute link is reached.  The attribute is therefore always the winner
    of a disagreement, which is exactly what a restore needs.  Pinned by a test that drives
    the real nicegui.binding rather than a stand-in, because a stand-in cannot answer this.

    The checkbox does visibly tick for as long as the jump takes.  That is the option being
    on, honestly shown, rather than a hidden mode.

    The one way it can outlive the jump is the process dying mid-jump -- kill the app while
    a Map is building and the finally never runs, so the option is saved on as if it had
    been chosen.  Losing a setting to a kill is what a kill does; it is not worth a second,
    unbound flag to guard against.
    """
    remembered = getattr(gui, "open_view_in_new_window", False)
    gui.open_view_in_new_window = True
    try:
        yield
    finally:
        gui.open_view_in_new_window = remembered


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

    Called from initialize_screen for exactly the reason guiwins_canvas._register_canvas_events is, and it
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
                        ui.tree(tree_data, label_key="label", children_key="children", tick_strategy="none")
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
                    raw_name.replace("&nbsp;", " ")
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
                        ui.element("div")
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
            ui.select(
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
            ui.select(
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
        # The Task Flow view is a drawing too -- one Task's control flow, box-drawn by
        # taskflow.py -- so it inherits the Diagram's unwrapped, tightly-led layout without
        # inheriting the Diagram's toolbar, none of which (Profiles Per Line, folding, the
        # call chain) means anything for a single Task.
        is_flow = self.title.startswith("Task Flow")

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
                        ui.select(
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

            self.wrap_enabled = not (is_diagram or is_flow)
            self.wrap_classes = "whitespace-pre-wrap break-words" if self.wrap_enabled else "whitespace-pre"

            # min-h-0 lets this flex item shrink below its content's intrinsic size -- without it
            # a flex column's default min-height:auto would keep growing the scroll area (and the
            # page) to fit all the streamed-in content instead of scrolling internally.
            scroll_height_classes = "flex-1 min-h-0" if is_popout else "h-[70vh]"

            # Tailwind's text-sm utility (below) pairs a 14px font with a 20px line-height --
            # comfortable for prose, but visibly loose for a dense box-drawn diagram. Tighten it
            # for the Diagram view only; keep process_data()'s approx_px_per_line chunk-height
            # estimate in sync with this so scrolling doesn't jump around as chunks pop in.
            line_height_style = " line-height: 1.2;" if is_diagram or is_flow else ""

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
                ui.scroll_area()
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
        is_flow = self.title.startswith("Task Flow")
        # Starting point, used as-is by the Misc and Task Flow views (neither of which has a
        # generated file behind it).  The file-backed views replace this below with the font
        # their file actually carries.
        html_style = f"width: 100%; max-width: 100%; font-family: '{PrimeItems.program_arguments['font']}', monospace;"
        if not (is_diagram or is_flow):
            html_style += " word-break: break-word;"

        if self.title.startswith("Map"):
            file_to_read = os.path.join(os.getcwd(), "MapTasker.html")
        elif is_diagram:
            file_to_read = os.path.join(os.getcwd(), DIAGRAM_FILE)
        elif self.title.startswith("Misc") or is_flow:
            # The Task Flow view is this renderer with the Diagram's habits: rows mapjump has
            # already made clickable, but a drawing rather than prose, so nothing may wrap
            # (see build_ui).  Its content comes off PrimeItems rather than through the_data
            # because a popped-out window builds itself from a URL and is handed nothing --
            # the same reason the Diagram popout re-reads its own file (rungui.popout_view).
            with self.scroll_area:
                content_str = (
                    mapjump.html_report(PrimeItems.taskflow_rows)
                    if is_flow
                    else ("\n".join(str(line) for line in the_data) if isinstance(the_data, list) else str(the_data))
                )
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
                    ui.select({}, label=translate_string("Replace this action"), with_input=True)
                    .classes("flex-1 min-w-[220px]")
                    .props("dense")
                )
                target_select = (
                    ui.select({}, label=translate_string("...with this one"), with_input=True)
                    .classes("flex-1 min-w-[260px]")
                    .props("dense")
                )
                # Hidden under a scope, for the reason the Find tab's own gives.
                swap_project = (
                    ui.select(
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
                        ui.select({}, label=translate_string("In this action"), with_input=True)
                        .classes("flex-1 min-w-[220px]")
                        .props("dense")
                    )
                    arg_select = (
                        ui.select({}, label=translate_string("...replace this argument"), with_input=True)
                        .classes("flex-1 min-w-[240px]")
                        .props("dense")
                    )
                    arg_project = (
                        ui.select(
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
                        ui.input(label=translate_string("Only where the value contains (optional)"))
                        .classes("flex-1 min-w-[240px]")
                        .props("dense clearable")
                    )
                    arg_value_input = (
                        ui.input(label=translate_string("...and put this there"))
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
                    ui.select({}, label=translate_string("Replace this Profile condition"), with_input=True)
                    .classes("flex-1 min-w-[240px]")
                    .props("dense")
                )
                condition_target_select = (
                    ui.select({}, label=translate_string("...with this one"), with_input=True)
                    .classes("flex-1 min-w-[260px]")
                    .props("dense")
                )
                condition_project = (
                    ui.select(
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
                    ui.select({}, label=translate_string("Rename this variable"), with_input=True)
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
                    ui.input(label=translate_string("...to this name"))
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
                            ui.select(
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
                        ui.input(label=translate_string("Text (name, label or argument)"))
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
                        ui.select(
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
    # see guiwins_canvas._register_canvas_events for why the timing is the whole point.
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
        ui.left_drawer(value=True, fixed=True)
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
            ui.select(
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
        ui.right_drawer(value=True, fixed=True)
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
            ui.checkbox(translate_string("Close Tabs On Exit"))
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
            ui.checkbox(translate_string("Open View In New Window"))
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
            ui.button(
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
            ui.button(
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
            ui.button(
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

        # Full width and coloured through "color" for the same two reasons the three buttons
        # above are: the drawer is w-80, this label will not fit beside another, and Quasar's
        # own bg-primary beats a Tailwind bg-* class added here.
        self.task_flow_button = (
            ui.button(
                translate_string("Task Flow"),
                color="teal",
                on_click=self.event_handlers.task_flow_event,
                icon="account_tree",
            )
            .classes("w-full justify-center")
            .style("margin-top:-6px")
        )
        with self.task_flow_button:
            ui.tooltip(
                translate_string(
                    "Read every Task's control flow -- its If/Else/End If, For/End For, Goto and "
                    "Stop -- and report what does not hold together: a block that is never closed, "
                    "a Goto aimed at a label no action carries, and actions nothing can ever "
                    "reach.\n\nWith a single Task chosen in the 'Specific Name' tab, that Task is "
                    "also drawn as a flowchart in its own window, with an arrow from every Goto to "
                    "the action it lands on.\n\nResults are displayed here and saved to a text file "
                    "in the current directory.",
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
                        ui.select(
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
                        ui.select(
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
                        ui.select(
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
                        ui.select(
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
                    ui.checkbox(
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
                                ui.button(
                                    translate_string("Edit Project"),
                                    on_click=self.event_handlers.open_edit_project_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                            self.add_project_button = (
                                ui.button(
                                    translate_string("Add Project"),
                                    on_click=self.event_handlers.open_add_project_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                        with ui.row().classes("w-full gap-2 m-0 p-0") as self.profile_buttons_row:
                            self.edit_profile_button = (
                                ui.button(
                                    translate_string("Edit Profile"),
                                    on_click=self.event_handlers.open_edit_profile_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                            self.add_profile_button = (
                                ui.button(
                                    translate_string("Add Profile"),
                                    on_click=self.event_handlers.open_add_profile_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                        with ui.row().classes("w-full gap-2 m-0 p-0") as self.task_buttons_row:
                            self.edit_task_button = (
                                ui.button(
                                    translate_string("Edit Task"),
                                    on_click=self.event_handlers.open_edit_task_dialog_event,
                                )
                                .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                .style("max-width:12rem")
                            )
                            self.add_task_button = (
                                ui.button(
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
                                    ui.button(
                                        translate_string("Edit Scene"),
                                        on_click=self.event_handlers.open_edit_scene_dialog_event,
                                    )
                                    .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                                    .style("max-width:12rem")
                                )
                                self.add_scene_button = (
                                    ui.button(
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
                        _create_refactor_button(self)
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
                        ui.select(
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
                        ui.color_input(
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
                        ui.checkbox(translate_string("Display Runtime Settings"))
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
                ui.checkbox(translate_string("Extended"), on_change=self.event_handlers.extended_models_event)
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
        ui.label(translate_string("Project/Profile/Task/Scene Names:"))
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
                ui.button(
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
