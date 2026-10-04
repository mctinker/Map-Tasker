"""GUI Window Classes and Definitions (NiceGUI Version).

What is left here after the split: the popup and "Changes Pending" scaffolding every editor
shares, the session Undo controls, the Project and Scene dialogs, the Object Properties
form, the light/dark switch, and the screen's own initialization and layout.

The dialog families and views that were taking this file past 14,500 lines now live beside
it, one module per family:

    guiwins_taskedit.py         Edit/Add/Delete Task, the Action editor and its pickers
    guiwins_profedit.py         Edit/Add/Delete Profile and its Save To Android panel
    guiwins_designer_legacy.py  the Legacy Scene designer and its element dialogs
    guiwins_designer_v2.py      the Version 2 Scene designer and its property fields
    guiwins_canvas.py           the Scene canvas JavaScript both designers draw through
    guiwins_views.py            the Map/Diagram/Misc, Tree and Scene Preview views
    guiwins_search.py           Search, Find and Replace on those views
    guiwins_nav.py              the registry of open views, and the jumps into them
    guiwins2.py                 the AI API Keys dialog

Each imports what it needs from this file; the few that this file calls back into are
imported at the top, below.  A family that had to reach back for editor scaffolding does so
inside the function that needs it, which is the one thing to know before moving code between
these modules -- see any of their docstrings for which calls those are and why.
"""

from __future__ import annotations

import contextlib
import html
import inspect
import re
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to serialize, never to parse
from collections import deque
from datetime import date
from typing import TYPE_CHECKING

from nicegui import app, ui

from maptasker.src import (
    appinv,
    clock,
    healthck,
    mapjump,
    objprops,
    projedit,
    roundtrip,
    sceneedit,
    sceneedit_legacy,
    sceneview,
    sessundo,
    taskedit,
    timeline,
    webassets,
)
from maptasker.src.colrmode import set_color_mode
from maptasker.src.config import EDIT_SCENE
from maptasker.src.getputer import save_restore_args
from maptasker.src.guistate import remember_setting
from maptasker.src.guiutil2 import get_font_choices, sort_languages_with_priority
from maptasker.src.guiutils import (
    add_logo,
    android_address_defaults,
    display_model_pulldown,
    refresh_object_action_buttons,
    remember_android_address_fields,
    update_analysis_button_color,
)

# The dialog families split out of this file, which had grown past 14,500 lines.  Each is
# imported for the handful of names this module still calls into: the Scene canvas the
# Preview draws through, the two designers the Scene editor body mounts, and the Action
# editor and pickers the Scene Event tab reuses.  guiwins_profedit is not among them --
# nothing here calls it; userintr reaches it directly.
from maptasker.src.guiwins_canvas import (
    FIELD_COMMIT_DEBOUNCE_MS,
    _register_canvas_events,
)
from maptasker.src.guiwins_designer_legacy import (
    _build_legacy_designer,
    _render_legacy_arg,
)
from maptasker.src.guiwins_designer_v2 import _build_v2_designer
from maptasker.src.guiwins_impact import build_impact_panel, wire_impact_clicks
from maptasker.src.guiwins_nav import (
    live_views,
    register_finding_clicks,
)
from maptasker.src.guiwins_taskedit import (
    _build_fetch_apps_dialog,
    _build_task_action_editor,
    _build_tasker_icon_picker_dialog,
    _render_addability_reason,
)
from maptasker.src.guiwins_views import (
    _scene_dialog_closed,
)
from maptasker.src.mapjump import PROJECT, SCENE
from maptasker.src.maputil2 import translate_string
from maptasker.src.outdir import default_output_directory
from maptasker.src.sysconst import (
    DIAGRAM_PROFILES_PER_LINE,
    NOTIFY_TIMEOUT_DEFAULT,
    VIEW_LIMIT_DEFAULT,
    logger,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Sequence
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState
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
# The View Limit pulldown's choices, as the strings it shows.  Round numbers and
# "Unlimited": the setting is a throttle, and nobody throttling a report is thinking in
# single lines.
VIEW_LIMIT_CHOICES: tuple[str, ...] = ("5000", "10000", "15000", "20000", "25000", "30000", "Unlimited")


def view_limit_options(current: str) -> list[str]:
    """The View Limit pulldown's choices, with the limit in force among them.

    A limit that is not one of the round numbers offered -- one given on the command line
    with -view_limit, or restored from a settings file that holds one -- still has to be
    offered, or the pulldown shows nothing at all, which reads as "no limit set" when there
    very much is one.  It goes in numeric order, ahead of "Unlimited", where the user would
    look for it.

    Args:
        current (str): the limit in force, as the pulldown would show it.

    Returns:
        list[str]: the choices to offer.
    """
    options = list(VIEW_LIMIT_CHOICES)
    if current in options or not current.isdigit():
        return options
    position = next(
        (index for index, option in enumerate(options) if option.isdigit() and int(option) > int(current)),
        options.index("Unlimited"),
    )
    options.insert(position, current)
    return options


# Mutable so the pulldown can change it live; read at notify time, not at install time.
_NOTIFY_TIMEOUT = {"ms": NOTIFY_TIMEOUT_DEFAULT}
_NOTIFY_WRAPPED = False

# Every ui.notify since start-up (or the last Clear Log), oldest first, as (time, type, message).
# Bounded so a long session cannot grow it without limit; the oldest entries fall off first.
_NOTIFY_LOG_MAX = 500
_NOTIFY_LOG: deque[tuple[str, str, str]] = deque(maxlen=_NOTIFY_LOG_MAX)


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
        _NOTIFY_LOG.append((time.strftime("%H:%M:%S"), str(kwargs.get("type") or "info"), str(message)))
        kwargs.setdefault("timeout", _NOTIFY_TIMEOUT["ms"])
        if not kwargs["timeout"]:
            # "Until dismissed" with no way to dismiss it is a notification that covers the
            # window forever, so the close button comes with the choice rather than being a
            # second thing to remember.
            kwargs.setdefault("close_button", True)
        original(message, **kwargs)

    ui.notify = notify
    _NOTIFY_WRAPPED = True


def display_notification_log() -> None:
    """Show every notification recorded since start-up (or the last Clear Log), newest last.

    Read-only, so -- like the other read-only dialogs -- it is not persistent.  An empty log
    is said inside the dialog rather than with a notification, since that notification would
    itself be the log's first entry.
    """
    with ui.dialog() as dialog, ui.card().classes("min-w-[600px] max-w-[1000px] w-full p-4"):
        ui.label(translate_string("Notification Log")).classes("text-xl font-bold text-blue-600")
        if _NOTIFY_LOG:
            log = ui.log(max_lines=_NOTIFY_LOG_MAX).classes("w-full h-[60vh] text-xs")
            for stamp, kind, message in _NOTIFY_LOG:
                log.push(f"{stamp}  [{kind}]  {message}")
        else:
            ui.label(translate_string("No notifications have been logged."))
        ui.button(translate_string("Close"), on_click=dialog.close).classes("mt-4 bg-red-500 text-white w-full")
    dialog.open()


def clear_notification_log() -> None:
    """Empty the notification log.  The confirmation goes out first so it is not left behind
    as the only entry in a log the user just cleared.
    """
    ui.notify(translate_string("Notification log cleared."), type="positive")
    _NOTIFY_LOG.clear()


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
# <mdate> (editcommon.touch_project_mdate), and a Profile's leaves <limit> at the end of the
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

# The field_refs key each dialog files its Redact tick-box under.  Three of them rather than
# one because the Project and Scene dialogs already name their path field apart from the
# other two, and a key shared between two dialogs open at once would be a key one of them
# read the other's value from.
REDACT_FIELD = "redact_secrets"
PROJECT_REDACT_FIELD = "project_redact_secrets"
SCENE_REDACT_FIELD = "scene_redact_secrets"


def build_redact_checkbox(field_refs: dict, key: str = REDACT_FIELD) -> None:
    """The "Redact secrets" tick-box that sits under an export's "Save as" path.

    One function, called by all four Edit dialogs, so the four exports cannot come to
    describe the same thing four slightly different ways -- and so a rule added to piiscan
    is explained in one place rather than four.

    Off by default, deliberately.  An export is normally a backup or a move between devices,
    where the keys in the file are the keys it needs, and a redaction the user did not ask
    for would be a file that imports and quietly fails.  Redacting is the exception -- the
    export that leaves the user's hands -- so it is the one that has to be asked for.

    Nothing here is remembered between exports for the same reason: "I am about to post this
    on a forum" is true of one save, not of the setting from then on.
    """
    field_refs[key] = ui.checkbox(translate_string("Redact secrets"), value=False).classes("mt-1")
    with field_refs[key]:
        ui.tooltip(
            translate_string(
                "Tick this when the exported file is going to somebody else -- posted on a forum, "
                "or sent to whoever is helping you.\n\n"
                "The API keys, tokens, passwords, phone numbers, email addresses and location "
                "coordinates in it are replaced with [REDACTED:...] markers, and a comment at the "
                "top of the file says what was taken out.  Run Health Check first to see the list.\n\n"
                "It is a first pass, not a guarantee: a password that looks like an ordinary word "
                "has no shape to recognise, and names are never changed, because the file uses them "
                "to refer to itself.  Read what you post.\n\n"
                "Leave it unticked for a backup or a move to another device -- a redacted file "
                "imports with the keys missing.",
            ),
        ).style("white-space: pre-wrap")


# field_refs keys that say where a save GOES, or how, rather than what is being saved.
# Typing a different export path is not an edit to the item -- there would be nothing for
# Cancel to discard -- and neither is ticking Redact, which changes what one exported FILE
# holds and nothing at all about the Task/Profile/Project in the loaded backup.  Every other
# key in field_refs is content.
PENDING_CHANGES_IGNORED_FIELDS: frozenset[str] = frozenset(
    {"save_path", "project_save_path", "scene_save_path", REDACT_FIELD, PROJECT_REDACT_FIELD, SCENE_REDACT_FIELD},
)


def editor_state(
    element: Element,
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
def remember_android_panel_option(gui: MyGui, name: str, value: object) -> None:
    """Keep one of the Save To Android panel's checkboxes -- for the next panel and the next session.

    Written to three places, for the reason userintr_reports.save_health_check_skip gives for its own
    setting: the GUI attribute is what the next panel opens with and what exiting writes back over
    program_arguments (guistate.capture_gui_state); program_arguments is what the settings file is
    written from; and the file is written now rather than at exit, since a session that ends any
    other way would otherwise forget a box ticked in it.
    """
    remember_setting(gui, name, bool(value))
    save_restore_args(gui.state.program_arguments, gui.state.colors_to_use, to_save=True, state=gui.state)


def _android_device_fields(gui: MyGui) -> dict:
    """Where the device is, and whether to check the XML before sending it there.

    The address and port default to the last ones entered, the same way the Get XML and
    Fetch Applications dialogs default, and are kept as soon as either field is left -- the
    panel can be backed out of without saving, and an address typed there should not be lost
    (see guiutils.remember_android_address_fields).

    "Verify" and "Check IDs" are remembered differently: as they are ticked, and in the settings
    file as well, so they hold across sessions (see remember_android_panel_option).  They are
    preferences about how this program behaves rather than facts about a device, so a user who
    wants every save checked should not have to re-tick them on the next panel or the next day --
    and unlike the address, there is no failure that should make them stick less.

    It defaults OFF.  What it does is described in its own tooltip, and what it costs is a
    save it can refuse: a check that could block a save without having been asked for is not
    one to turn on behind the user's back.  See roundtrip.py's header.
    """
    default_ip, default_port = android_address_defaults(gui)

    fields = {
        "ip_address": ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full"),
        "ip_port": ui.input(translate_string("Port"), value=default_port).classes("w-full"),
    }
    remember_android_address_fields(gui, fields["ip_address"], fields["ip_port"])
    verify = (
        ui.checkbox(
            translate_string("Verify"),
            value=bool(getattr(gui, "android_verify", False)),
            on_change=lambda event: remember_android_panel_option(gui, "android_verify", event.value),
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

    # "Check IDs" is remembered on the GUI the same way, and for the same reason.  It defaults OFF
    # for a different one: it is not free -- the device writes out its whole configuration and this
    # reads it back, which is seconds on every save, plus a helper Task installed the first time.
    check_ids = (
        ui.checkbox(
            translate_string("Check IDs"),
            value=bool(getattr(gui, "android_check_ids", False)),
            on_change=lambda event: remember_android_panel_option(gui, "android_check_ids", event.value),
        )
        .props("dense")
        .classes("mt-1")
    )
    with check_ids:
        ui.tooltip(
            translate_string(
                "Has the device make a fresh backup before anything is sent, and compares its IDs with the "
                "ones being sent.\n\n"
                "It reports an ID Tasker has already given to a different Project, Profile or Task, and an "
                "object Tasker has under a different ID.  Tasker can leave an object out of an import when "
                "its ID is already taken -- and IDs for anything added here come from the loaded backup, "
                "which the device may have moved past.\n\n"
                "It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the "
                "device the first time.  The backup is read into memory and deleted from the device; it is "
                "not saved on this computer.",
            ),
        ).style("white-space: pre-wrap")
    fields["check_ids"] = check_ids
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
# THIS IS A LIST OF WHAT IS SAFE, checked at save time by userintr_editors._unapplied_project_edits,
# because both of this dialog's saves render the Project from the LIVE TREE by name --
# projedit.write_standalone_project_xml(project_name, ...) and .save_project_to_android(
# project_name, ...).  A field added here that edits the Project would therefore be dropped
# silently from the exported file and the upload, which is the bug Scene had (see
# userintr_android.save_scene_to_android_event).  Anything added to field_refs and not named here
# fails the save with a message naming the field, rather than writing an incomplete Project.
#
# Adding a real editable field means applying it before those two saves -- follow what the
# Scene handlers do -- and only then listing its key here.
EDIT_PROJECT_INERT_FIELDS: frozenset[str] = frozenset({"name", "project_save_path", PROJECT_REDACT_FIELD})


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
        build_redact_checkbox(field_refs, PROJECT_REDACT_FIELD)

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
# are a <PropertiesElement> generated from action_codes instead and keep their own panel in
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
    element: Element,
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
    userintr_editors._unapplied_project_edits fails the save on.  Nothing needs to be registered
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
    variable: Element,
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
    element: Element,
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
# Properties screen.  Transcribed from action_overlay.json's "PropertiesElement", whose eight
# slots are present in all 538 sample Scenes that have one:
#
#   arg0 Property Type   arg1 Orientation   arg2 Background Colour   arg3 Action Bar Style
#   arg4 Title           arg5 Subtitle      arg6 Icon                arg7 Tab Label
#
# arg3-arg7 describe an Activity's title bar and are shown only when arg0 says Activity,
# which is what Tasker does: a Dialog or an Overlay has no action bar to style and no tab
# to label, so offering the five would invite settings that do nothing.
_SCENE_PROPERTY_TYPE_ARG = sceneedit_legacy.LEGACY_PROPERTY_TYPE_ARG
_SCENE_ALWAYS_ARGS = ("1", "2")
_SCENE_ACTIVITY_ARGS = ("3", "4", "5", "6", "7")
# Indexes into actiont.lookup_values["PropertyElement1"] == ("Overlay", "Dialog", "Activity").
_SCENE_TYPE_OVERLAY = sceneedit_legacy.LEGACY_SCENE_TYPE_OVERLAY
_SCENE_TYPE_ACTIVITY = sceneedit_legacy.LEGACY_SCENE_TYPE_ACTIVITY

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


def _scene_properties_summary(scene_element: Element) -> str:
    """A one-line "this is what is set" for the designer's Scene Properties panel, which is
    a signpost to the form rather than the form (see render_scene_properties).

    Reuses sceneview.scene_properties -- the same (label, value) rows the Preview captions
    its picture with -- so the panel and the picture cannot describe the same Scene
    differently.  What the Event and Actions tabs hold is added on the end -- which events
    fire a Task, whether a key press is swallowed, and how many action bar items there are --
    because none of it is something the Preview reports.
    """
    rows = [f"{translate_string(label)}: {value}" for label, value in sceneview.scene_properties(scene_element)]
    properties = sceneedit_legacy.legacy_scene_properties(scene_element)
    if properties is not None:
        fired = [
            event.label for event in sceneedit_legacy.LEGACY_SCENE_EVENTS if properties.find(event.tag) is not None
        ]
        if fired:
            rows.append(f"{translate_string('fires a Task on')} {', '.join(fired)}")
        if sceneedit_legacy.legacy_stop_event(properties):
            rows.append(translate_string("swallows the key press"))
        if items := sceneedit_legacy.legacy_action_items(properties):
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
    generated from action_codes the same way a Task action's arguments are.  The two have
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
    properties_snapshot = sceneedit_legacy.legacy_properties_snapshot(scene_element)
    geometry_snapshot = {
        key: str(field_refs[key].value) for key, _label in sceneedit.SCENE_DIMENSION_FIELDS if key in field_refs
    }
    # Which tab is on screen, kept across the rebuilds render() does.  Without it, picking a
    # Task or changing Property Type -- both of which rebuild the whole body -- would throw
    # the user back to the UI tab from whichever one they were working in.
    showing = {"tab": _SCENE_TAB_UI, "event": sceneedit_legacy.LEGACY_SCENE_EVENTS[0].label}
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
                properties = sceneedit_legacy.legacy_scene_properties(scene_element)
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

                args = {arg.arg_id: arg for arg in sceneedit_legacy.legacy_element_args(properties, state=self.state)}
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
            sceneedit_legacy.legacy_add_scene_properties(scene_element, state=self.state)
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
            properties = sceneedit_legacy.legacy_scene_properties(scene_element)

            def bind(event_tag: str, new_task_id: str) -> None:
                if properties is not None:
                    sceneedit_legacy.legacy_set_task_binding(properties, event_tag, new_task_id)

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
    scene_element: Element,
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
                if arg_id == sceneedit_legacy.LEGACY_ICON_ARG:
                    ui.label(
                        translate_string(
                            "The home icon at the top left of the action bar. Tapping it fires the "
                            "Event tab's Home Tap Task.",
                        ),
                    ).classes("text-xs text-gray-500 italic")
                elif arg_id == sceneedit_legacy.LEGACY_TAB_LABELS_ARG:
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
    scene_element: Element,
    field_refs: dict,
) -> None:
    """Geometry: the pixel size the Scene is laid out at, in the Portrait/Landscape pairs
    Tasker asks for.

    These are NOT properties of the <PropertiesElement> -- they are the Scene's own
    <widthPort>/<heightPort>/<widthLand>/<heightLand> children, and the Scene dialog behind
    this one already has an input for each.  So these DRIVE THOSE WIDGETS rather than
    writing the XML: userintr_editors._apply_scene_field_values reads exactly those four field_refs
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
        value = (
            str(source.value) if source is not None else scene_element.findtext(key, sceneedit_legacy.UNSET_DIMENSION)
        )
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
    properties: Element,
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
    (sceneedit_legacy.legacy_action_item_args), so its fields behave as they do everywhere else.
    """
    items = sceneedit_legacy.legacy_action_items(properties)
    is_activity = sceneedit_legacy.legacy_scene_type(properties) == _SCENE_TYPE_ACTIVITY

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
                        value=sceneedit_legacy.legacy_action_item_icon(item),
                    )
                    .props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}")
                    .classes("flex-1")
                )
                icon_field.on_value_change(
                    lambda event, it=item: sceneedit_legacy.legacy_set_action_item_icon(it, str(event.value or "")),
                )
                ui.button(
                    translate_string("Pick"),
                    icon="image",
                    on_click=lambda _e=None, field=icon_field: _build_tasker_icon_picker_dialog(field, self),
                ).props("flat dense size=sm")

            ui.input(
                translate_string("Label"),
                value=item.label,
                on_change=lambda event, it=item: sceneedit_legacy.legacy_set_action_item_label(
                    it, str(event.value or "")
                ),
            ).props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}").classes("w-full")

            item_args = sceneedit_legacy.legacy_action_item_args(item, state=self.state)
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
    properties: Element,
    sr: str,
    offset: int,
    rerender: Callable[[], None],
) -> None:
    sceneedit_legacy.legacy_move_action_item(properties, sr, offset)
    rerender()


def _remove_scene_action_item(
    properties: Element,
    sr: str,
    rerender: Callable[[], None],
) -> None:
    sceneedit_legacy.legacy_remove_action_item(properties, sr)
    rerender()


def _render_scene_action_item_picker(
    self: MyGui,
    properties: Element,
    rerender: Callable[[], None],
) -> None:
    """Tasker's plus button at the bottom of the Actions tab: pick the action the new item
    runs, and the item is built around it.

    The same search/filter picker the Task editors use, over the same list -- what can go on
    an action bar is what can be added to a Task, because it is synthesized by the same code
    (sceneedit_legacy.legacy_add_action_item -> taskedit.build_synthesized_args).  An action that
    cannot be synthesized is greyed out with its reason, exactly as it is there.
    """
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions(state=self.state)})

    ui.label(translate_string("Add an action bar item")).classes("text-sm font-bold mt-3")
    with ui.row().classes("w-full gap-4"):
        search_input = ui.input(translate_string("Search actions")).classes("flex-1")
        category_select = ui.select(["All", *category_names], value="All").classes("w-48")
    picker_container = ui.column().classes("w-full")

    def add_item(action_key: str) -> None:
        added = sceneedit_legacy.legacy_add_action_item(properties, action_key, state=self.state)
        if isinstance(added, list):
            for error in added:
                ui.notify(error, type="negative")
            return
        rerender()

    def refresh_picker(_event: ui.event | None = None) -> None:
        picker_container.clear()
        rows = taskedit.search_addable_actions(search_input.value, category_select.value, state=self.state)
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
    properties: Element,
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
    for name, meaning in sceneedit_legacy.LEGACY_SCENE_EVENT_COMMON_VARIABLES:
        ui.label(f"{name} -- {translate_string(meaning)}").classes("text-xs text-gray-500 italic")

    events = {event.label: event for event in sceneedit_legacy.LEGACY_SCENE_EVENTS}
    if showing["event"] not in events:
        showing["event"] = sceneedit_legacy.LEGACY_SCENE_EVENTS[0].label

    with ui.tabs(value=showing["event"]).classes("w-full mt-2") as event_tabs:
        for event in sceneedit_legacy.LEGACY_SCENE_EVENTS:
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
    properties: Element,
    event: sceneedit_legacy.LegacySceneEvent,
    rerender: Callable[[], None],
    task_state: dict | None = None,
    scene_name: str = "",
) -> None:
    """One Event sub-tab: when it fires, the Task it fires, and what that Task can read.

    The Task binding is the same model the element inspector's Tasks section uses
    (sceneedit_legacy.legacy_set_task_binding / legacy_clear_task_binding) rather than a second way
    of pointing at a Task -- these three tags are ordinary Scene Task bindings that happen to
    hang off the Scene's properties instead of one of its elements.

    WHICH TASK IS BOUND, and picking a different one, are two rows rather than one control:
    a read-only field naming what fires now, and _render_task_picker below it.  See that
    function for why a dropdown was the wrong shape for a list this size.

    A binding is shown and editable even when Tasker would not offer this event for this
    Scene (an <iconclickTask> on something that is no longer an Activity, say); the reason
    is printed above it instead.  Hiding what the file holds is how an editor comes to
    disagree with the file -- see sceneedit_legacy.legacy_scene_event_availability.
    """
    if unavailable := sceneedit_legacy.legacy_scene_event_availability(properties, event):
        ui.label(translate_string(unavailable)).classes("text-xs text-amber-600 italic")
    ui.label(translate_string(event.description)).classes("text-xs text-gray-500 italic")

    bound = properties.find(event.tag)
    task_id = (bound.text or "").strip() if bound is not None else ""
    anonymous = task_id.startswith(sceneedit_legacy.LEGACY_ANONYMOUS_TASK_PREFIX)
    # Named off the id rather than off the tables' name, so a Task whose entry carries a
    # blank name still reads as bound.  taskerd normally fills a made-up display name in for
    # an unnamed Task, but a caller that built the tables without that pass would otherwise
    # make a real binding read as "Nothing".
    all_tasks = self.state.tasker_root_elements.get("all_tasks", {})
    entry = all_tasks.get(task_id)
    task_name = ((entry or {}).get("name") or f"Task {task_id}") if task_id else ""

    def set_binding(picked: str) -> None:
        if not picked:
            return
        picked_id = sceneedit_legacy.legacy_task_id_for_name(picked, state=self.state)
        if not picked_id:
            ui.notify(f"No Task named '{picked}' in this backup.", type="negative")
            return
        sceneedit_legacy.legacy_set_task_binding(properties, event.tag, picked_id)
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
                    sceneedit_legacy.legacy_clear_task_binding(properties, event.tag),
                    rerender(),
                ),
            ).props("dense flat size=sm color=negative").tooltip(
                translate_string("Stop firing anything on this event."),
            )

    if not anonymous:
        _render_task_picker(set_binding, state=self.state)

    if event.tag == sceneedit_legacy.LEGACY_KEY_TASK_TAG:
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


def _render_task_picker(on_pick: Callable[[str], None], state: RunState) -> None:
    """ "Pick a Task", built the way "Add an action" is: a search box, a filter, and a
    scrolling list of one clickable row per match.

    IT REPLACED A DROPDOWN, and the list is why.  A `ui.select` of every Task in the backup
    is one control holding several hundred entries -- 352 in one of this repo's sample backups
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
    sceneedit_legacy.legacy_task_id_for_name and every other Task-by-name path in this app take, and
    resolving it at the callback keeps this function ignorant of what the caller does with it.
    """
    rows = taskedit.list_pickable_tasks(state=state)
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
        matches = taskedit.search_pickable_tasks(search_input.value, project_select.value, state=state)
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


def _render_scene_key_filter(properties: Element) -> None:
    """The Key event's own filter: which keys the Scene handles, and whether it swallows them.

    Both live in the Scene's <LinkClickFilter> -- see sceneedit_legacy.legacy_set_key_filter, which
    also explains why a tag named urlMatch is holding a list of key names.
    """
    keys = (
        ui.input(
            translate_string("Keys"),
            value=sceneedit_legacy.legacy_key_filter(properties),
        )
        .props(f"dense debounce={FIELD_COMMIT_DEBOUNCE_MS}")
        .classes("w-full mt-2")
    )
    keys.on_value_change(lambda event: sceneedit_legacy.legacy_set_key_filter(properties, str(event.value or "")))
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
        value=sceneedit_legacy.legacy_stop_event(properties),
        on_change=lambda event: sceneedit_legacy.legacy_set_stop_event(properties, enabled=bool(event.value)),
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
    properties: Element,
    event: sceneedit_legacy.LegacySceneEvent,
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
    (userintr_editors.keep_scene_event_task_edits), and "Apply to Task" does the same for this one
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

    if task_id.startswith(sceneedit_legacy.LEGACY_ANONYMOUS_TASK_PREFIX):
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
        edited_task = taskedit.load_task_for_edit_by_id(task_id, state=self.state)
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
    properties: Element,
    event: sceneedit_legacy.LegacySceneEvent,
    task_state: dict,
    scene_name: str,
    rerender: Callable[[], None],
) -> None:
    """Compose a brand-new Task for an event that has none, and create it in place.

    Add Task's own two halves without Add Task's dialog: a Name and the action editor over an
    UNREGISTERED EditableTask, then a button that registers it and points the event at it in
    one undo step (userintr_editors.create_scene_event_task_event).  Ok does the same for any such
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
    if self.state.xml_root is None:
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
            default_name, "100", reserved_ids={task.task_id for task, _refs in pending.values()}, state=self.state
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
        "target_project_name": sceneedit.project_owning_scene(scene_name, state=self.state),
    }
    pending[event.tag] = (edited_task, field_refs)
    task_state["flushers"].append(
        lambda: self.event_handlers.stash_scene_event_task_edits(edited_task, field_refs),
    )

    _build_task_action_editor(self, edited_task, field_refs, list_classes=_SCENE_EVENT_ACTION_LIST_CLASSES)

    def create_task() -> None:
        def bind(new_task_id: str) -> None:
            sceneedit_legacy.legacy_set_task_binding(properties, event.tag, new_task_id)

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
    *,
    state: RunState,
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
      and is left alone as such (see sceneedit_legacy.UNSET_DIMENSION), which is why
      these are plain text inputs rather than number spinners -- a spinner would
      quietly turn a deliberate -1 into a 0-sized Scene.

      Version 2 -- no size fields at all, and a read-only outline of the component
      tree instead of an element list.  The size fields are omitted rather than
      shown-and-disabled because a V2 layout is declarative: there is no canvas
      to size, every real V2 Scene carries -1 across all four, and offering the
      four boxes would invite someone to set a number that means nothing.  Their
      absence from field_refs is what userintr_editors._apply_scene_field_values reads as
      "nothing to validate here", so no size is ever written to a V2 Scene.

    Each branch then hands off to the designer for its kind -- _build_v2_designer
    for a component tree, _build_legacy_designer for a canvas -- and neither needs
    anything from either dialog beyond the field_refs dict it is already handed.
    What each designer does and does not yet edit is documented on it rather than
    here; both are still filling in, and this function's job is only to pick.

    Every widget it puts in field_refs is read back by
    userintr_editors._apply_scene_field_values, which is the only thing that has to grow
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
        _build_v2_designer(edited_scene, field_refs, layout, state=state)
        return

    with ui.row().classes("w-full gap-2 mt-2"):
        for key, label in sceneedit.SCENE_DIMENSION_FIELDS:
            field_refs[key] = (
                ui.input(
                    translate_string(label),
                    value=scene_element.findtext(key, sceneedit_legacy.UNSET_DIMENSION),
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
    once the answer is known (see userintr_editors.add_scene_of_version_event).

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

        _build_scene_editor_body(self, edited_scene, field_refs, dialog, state=self.state)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_scene_event(edited_scene, field_refs, dialog),
            ).classes("bg-blue-600")

    dialog.open()


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
        dialog itself (userintr_editors.confirm_rename_scene_event) -- so there is no applied change
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

        _build_scene_editor_body(self, edited_scene, field_refs, dialog, state=self.state)

        field_refs["scene_save_path"] = ui.input(
            translate_string("Save as"),
            value=sceneedit.default_scene_save_path(scene_name),
        ).classes("w-full mt-2")
        build_redact_checkbox(field_refs, SCENE_REDACT_FIELD)

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
    # "Edit Scene" button resume it (userintr_editors.open_edit_scene_dialog_event) rather than
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
    *at* a Scene, so the dialog says what loses it (see sceneedit.delete_scene).

    Says it through guiwins_impact.build_impact_panel, as the other three Delete
    dialogs do.  This dialog used to note in passing that the Tasks which show or
    hide the Scene by name are not changed; the panel names them, one clickable line
    each, which is the difference between being told there may be a problem and
    being handed the list of it.  Read live, so it cannot go stale while the editor
    sits open.
    """
    scene_name = edited_scene.scene_name

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Scene')} '{scene_name}'").classes("text-lg font-bold text-red-600")
        build_impact_panel(self, SCENE, scene_name)
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


def _app_list_status() -> str:
    """What the plugin check will be compared against, for the Health Check panel.

    One line per fetched device, dated, because the date is the thing to judge it by: a
    plugin installed since then is reported missing, and one uninstalled since is not.
    """
    devices = appinv.fetched_devices()
    if not devices:
        return translate_string(
            "No app list has been fetched from the device, so plugins cannot be checked for being installed.",
        )
    lines = [f"{device}: {count} {translate_string('applications, fetched')} {when}" for device, when, count in devices]
    heading = translate_string(
        "Plugins are checked against the app list from"
        if len(lines) == 1
        else "Plugins are checked against the app lists from"
    )
    return f"{heading} {lines[0]}" if len(lines) == 1 else "\n".join([f"{heading}:", *lines])


def build_health_check_dialog(
    on_run: Callable[[list[str]], None],
    on_save: Callable[[list[str]], None],
    gui: MyGui,
    state: RunState,
) -> None:
    """Ask which categories of finding the Health Check should report, then run it.

    A panel rather than a settings screen because the answer is a property of the QUESTION
    being asked, not of the program: the check reports forty-five kinds of thing, and a
    user chasing one broken Perform Task does not want to read two hundred findings about
    variables that are set and never read.  Every box starts ticked, so the default is
    still "tell me everything" and nothing is quietly left out of a report unless somebody
    chose to leave it out.

    What is remembered between sessions is the UNTICKED set (program_arguments
    ["health_check_skip"]).  Storing it that way round is what lets a category added in a
    later release arrive already ticked -- see healthck.CATEGORIES.

    on_run is handed the list to leave out when Run is pressed.  on_save is handed it every
    time a choice changes -- one box, or all of them through Select All or Deselect All --
    so what is ticked is never lost to a Cancel or an exit.  The caller does the running and
    the saving: this module builds windows and knows nothing about what a health check is.

    'Refresh App List' is here because PLUGIN-NOT-INSTALLED is only as current as the list
    it is checked against, and the only other way to fetch one is from inside an editor's
    Application picker.  It opens the same fetch dialog those do, over this panel, and the
    panel stays open so Run is one click away once the list is in.
    """
    skip = set(state.program_arguments.health_check_skip or [])
    boxes: dict[str, ui.checkbox] = {}
    # Select All and Deselect All set every box in turn, and each of those would otherwise
    # save the settings file on its own: forty-five writes for one click.
    setting_all = False

    def skipped() -> list[str]:
        """The categories currently unticked."""
        return [tag for tag, box in boxes.items() if not box.value]

    def box_changed() -> None:
        """Remember a single box being ticked or unticked, as it happens."""
        if not setting_all:
            on_save(skipped())

    def set_all(ticked: bool) -> None:
        """Tick or untick every category at once, and remember that with a single save."""
        nonlocal setting_all
        setting_all = True
        try:
            for box in boxes.values():
                box.value = ticked
        finally:
            setting_all = False
        on_save(skipped())

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[520px] max-w-[720px] w-full p-6"):
        ui.label(translate_string("Health Check")).classes("text-lg font-bold text-blue-600")
        ui.label(translate_string("Report these categories:")).classes("text-sm text-gray-500")

        # Scrolled rather than fitted: the list is forty-five entries and grows with every
        # check added, and a dialog taller than the window is one whose buttons cannot be
        # reached.  The headings are just headings -- a group is not itself a choice, so
        # there is nothing here that can be ticked but does not correspond to a finding.
        with ui.scroll_area().classes("w-full h-[420px] mt-2 border rounded"):
            group = ""
            for category in healthck.CATEGORIES:
                if category.group != group:
                    group = category.group
                    ui.label(translate_string(group)).classes("font-bold text-sm mt-3 mb-1")
                with ui.row().classes("items-center gap-2 ml-2 no-wrap"):
                    boxes[category.tag] = ui.checkbox(
                        value=category.tag not in skip,
                        on_change=box_changed,
                    ).props("dense")
                    with ui.column().classes("gap-0"):
                        ui.label(category.tag).classes("font-mono text-xs")
                        ui.label(translate_string(category.what)).classes("text-xs text-gray-500")

        def run() -> None:
            """Close the panel, then run the check for whatever is still ticked."""
            dialog.close()
            on_run(skipped())

        async def refresh_apps() -> None:
            """Fetch the app list from the device, then say what the plugins will be checked against."""
            await _build_fetch_apps_dialog(gui, show_app_status)

        def show_app_status() -> None:
            app_status.set_text(_app_list_status())

        with ui.row().classes("w-full items-center justify-between gap-2 mt-3 no-wrap"):
            app_status = ui.label(_app_list_status()).classes("text-xs text-gray-500 whitespace-pre-line")
            refresh_button = ui.button(
                translate_string("Refresh App List"),
                icon="cloud_download",
                on_click=refresh_apps,
            ).props("flat dense color=primary no-caps")
            refresh_button.tooltip(
                translate_string(
                    "Fetch the list of installed applications from your Android device, so the check for "
                    "plugins that are not installed is up to date.",
                ),
            )

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(translate_string("Select All"), on_click=lambda: set_all(True)).props("outline")
            ui.button(translate_string("Deselect All"), on_click=lambda: set_all(False)).props("outline")
            ui.button(translate_string("Run"), on_click=run).classes("bg-blue-600")

    dialog.open()


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
                    "do it: Tasker's HTTP API has no way to delete a Task.  To make the next cleanup a single "
                    "delete, put the helper Tasks in the 'MapTasker' Project from the Android panel.",
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


def build_helpers_in_the_way_dialog(present: list[str], device: str, project_exists: bool | None = None) -> None:
    """Names the helper Tasks that must be deleted before the 'MapTasker' Project can be imported.

    Tasker rejects a whole Project with 'Import failed.' if it already has any Task in it (see
    deviceinv.stage_helper_project), so the file is not even written until these are gone.

    project_exists says whether Tasker already has the 'MapTasker' Project, which changes what
    the user actually does: deleting that one Project takes the Tasks in it with it.  None means
    it could not be asked -- the helper that answers it was not on the device to run -- and then
    the Project is mentioned as a possibility rather than as a fact.
    """
    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[420px] max-w-[680px] w-full p-6"):
        ui.label(translate_string("Delete These Helper Tasks First")).classes("text-lg font-bold text-blue-600")
        ui.label(f"{translate_string('On')} {device}").classes("text-xs text-gray-500")
        ui.label(
            translate_string(
                "Tasker refuses to import a Project that contains a Task it already has, so the 'MapTasker' "
                "Project cannot be imported while these are in Tasker:",
            ),
        ).classes("mt-3")
        with ui.column().classes("gap-0 mt-1"):
            for name in present:
                ui.label(name).classes("font-mono text-sm break-all")
        if project_exists:
            advice = (
                "Tasker already has a 'MapTasker' Project.  Delete that Project -- which deletes the Tasks "
                "in it -- along with any of the Tasks above that are outside it, and then try again."
            )
        elif project_exists is None:
            advice = (
                "Delete them in Tasker -- or delete the 'MapTasker' Project, if they are already in it -- "
                "and then try again."
            )
        else:
            advice = "Delete them from Tasker's Tasks tab -- long-press one, then Delete -- and try again."
        ui.label(translate_string(advice)).classes("text-xs text-gray-500 italic mt-2")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Close"), on_click=dialog.close).props("outline")

    dialog.open()


def build_overwrite_confirm_dialog(
    what_exists: str,
    on_confirm: Callable[[], object],
    *,
    unknown: bool = False,
    file_absent: bool = False,
    tasker_lines: Sequence[str] = (),
) -> None:
    """Confirms overwriting something that is already there, before anything is
    written. Backs every Save/Export path that would otherwise clobber a file
    silently -- the local standalone exports and the Save To Android uploads
    (see the save_* handlers in userintr and userintr_android).

    tasker_lines is what Tasker itself already has of the objects being sent (see
    userintr_android._what_tasker_already_has), shown under the file's own line so a save that both
    replaces a file and re-sends objects Tasker has asks once rather than twice.
    file_absent=True is a prompt raised by those lines alone: there is no file to name and
    nothing here is overwritten, so it says neither and offers Continue, not Overwrite.

    what_exists describes the thing in the user's terms (a full path); on_confirm
    performs the write and is called only if they choose "Overwrite". It may be a
    coroutine function, and is then awaited to the end: a write to the Android device
    hands its requests to a worker thread and has to wait for them. Cancel
    closes this dialog and leaves the parent Edit/Add dialog open, so nothing
    in progress is lost -- same convention as build_delete_project_dialog.

    unknown=True switches the wording for the case where existence could not be
    determined at all (maputil2.read_android_file returning None -- device
    unreachable mid-check). That is deliberately still a prompt rather than a
    silent write: the honest statement is "this might overwrite something", and
    the user is the one who knows whether that matters.
    """
    if file_absent:
        title, body = "Already in Tasker", ""
    else:
        title = "Could not check destination" if unknown else "Already exists"
        body = (
            f"Could not confirm whether {what_exists} already exists. Saving may overwrite it."
            if unknown
            else f"{what_exists} already exists and will be replaced."
        )

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(title).classes("text-lg font-bold text-orange-600")
        if body:
            ui.label(body).classes("mt-1 break-all")
        for line in tasker_lines:
            ui.label(line).classes("mt-2 break-words")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")

            async def _confirm() -> None:
                # Close first: on_confirm may open its own dialog (or close the
                # parent), and leaving this one stacked on top would hide it.
                confirm_dialog.close()
                # Awaited when it is a coroutine.  nicegui runs an async click handler inside
                # the button's slot, so the notifications a save makes still have a place to go.
                result = on_confirm()
                if inspect.isawaitable(result):
                    await result

            ui.button(translate_string("Continue" if file_absent else "Overwrite"), on_click=_confirm).classes(
                "bg-orange-600 text-white",
            )

    confirm_dialog.open()


def build_changes_since_dialog(on_choose: Callable[[str, date | None], Coroutine]) -> None:
    """Asks how far back "Changes Since..." should look, then hands the answer over.

    The periods and what they resolve to are timeline's (see timeline.PERIOD_LABELS and
    cutoff_for) -- this only shows them.  Keeping the vocabulary there is what stops the
    label and the date it means from drifting apart.

    The date picker is built once and hidden, rather than created when the choice lands
    on "Since a specific date...".  A calendar appearing where a pulldown used to be
    resizes the dialog under the pointer; hiding it keeps the dialog one shape.

    on_choose is awaited with the period key and, for that one option, the date -- and
    only once the choice is complete, so it never has to re-check it.  Awaited rather than
    called because producing the report means expanding and re-parsing a snapshot, which is
    megabytes of work that has to go off the event loop.  Cancel calls nothing, the same
    convention as build_overwrite_confirm_dialog.
    """
    options = {key: translate_string(label) for key, label in timeline.PERIOD_LABELS.items()}

    with ui.dialog().props("persistent") as period_dialog, ui.card().classes("min-w-[420px] max-w-[560px] w-full p-6"):
        ui.label(translate_string("Changes Since")).classes("text-lg font-bold")
        ui.label(
            translate_string(
                "Compare what you have open now against your configuration as it stood then.",
            ),
        ).classes("text-sm opacity-70 mt-1")

        period = ui.select(
            options,
            value=timeline.THIS_WEEK,
            label=translate_string("Period"),
        ).classes("w-full mt-3")

        # Quasar's own calendar.  landscape=False keeps it portrait, which fits the
        # dialog's width without the card growing sideways on a narrow drawer.
        date_holder = ui.column().classes("w-full items-center mt-3")
        with date_holder:
            picked_date = ui.date().props("minimal")
        date_holder.bind_visibility_from(period, "value", lambda value: value == timeline.ON_DATE)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=period_dialog.close).props("outline")

            async def _confirm() -> None:
                chosen = period.value
                on_date = None
                if chosen == timeline.ON_DATE:
                    on_date = _parse_picked_date(picked_date.value)
                    if on_date is None:
                        ui.notify(translate_string("Choose a date first."), type="warning")
                        return
                    if on_date > clock.now().date():
                        ui.notify(
                            translate_string("That date is in the future.  Choose a day that has happened."),
                            type="warning",
                        )
                        return
                # Closed before the work starts: the report opens its own view, and
                # leaving this dialog stacked on top would hide it.  Same reasoning as
                # build_overwrite_confirm_dialog's _confirm.
                period_dialog.close()
                await on_choose(chosen, on_date)

            ui.button(translate_string("Show Changes"), on_click=_confirm).classes("bg-teal-600 text-white")

    period_dialog.open()


def _parse_picked_date(value: object) -> date | None:
    """ui.date's "YYYY-MM-DD" as a date, or None when nothing usable was picked.

    None rather than an exception for an empty or malformed value: the picker starts
    empty, so "nothing chosen yet" is the ordinary state, not a fault.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


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
    before anything is mutated.

    The only Delete dialog with two buttons, and so the only one that shows two
    analyses: guiwins_impact.build_impact_panel is asked about each choice, because
    the two have genuinely different consequences.  Keeping the contents breaks
    nothing and quietly leaves the Project's Scenes in no Project at all; deleting
    them leaves every Profile OUTSIDE this Project that runs one of its Tasks
    pointing at a Task that is gone (projedit.delete_profiles_and_tasks_of_project
    unlinks nothing).  Neither was said here before, and neither is guessable from
    the button.  Both are read live, as the counts they replace were.
    """
    project_name = edited_project.project_name

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[500px] max-w-[700px] w-full p-6"):
        ui.label(f"{translate_string('Delete Project')} '{project_name}'").classes("text-lg font-bold text-red-600")
        # One element around both panels, wired once: a tab's content is not in the DOM
        # until that tab is first opened, so the clicks have to be delegated from an
        # ancestor that is (see guiwins_impact.wire_impact_clicks).
        impact_area = ui.element("div").classes("w-full")
        with impact_area:
            with ui.tabs().classes("w-full mt-2") as choice_tabs:
                keep_tab = ui.tab(translate_string("If you keep the contents"))
                delete_tab = ui.tab(translate_string("If you delete them too"))
            with ui.tab_panels(choice_tabs, value=keep_tab).classes("w-full"):
                with ui.tab_panel(keep_tab):
                    build_impact_panel(self, PROJECT, project_name, keep_contents=True, wire=False)
                with ui.tab_panel(delete_tab):
                    build_impact_panel(self, PROJECT, project_name, keep_contents=False, wire=False)
        wire_impact_clicks(self, impact_area)
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
# 3. APPEARANCE
# ==========================================
# The views that used to be section 3 are in guiwins_views.py; what stays here is the
# window-wide light/dark switch, which recolours them from above.
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
    self.state.program_arguments.gui = True
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
    self.output_directory = ""
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
    self.android_last_ipaddr = ""
    self.android_last_port = ""
    self.fetched_backup_from_android = False


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
    # The Save To Android panels' checkboxes.  Set here because every whole-settings save reads
    # each ARGUMENT_NAMES entry straight off the GUI, and a missing one would stop the save.
    self.android_verify = False
    self.android_check_ids = False


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
def document_language_html(state: RunState) -> str:
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
    lang_code = state.languages.get(state.program_arguments.language or "English", "en")
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


def inject_shared_head_styles(state: RunState) -> None:
    """Links the stylesheet and script shared by every page of the app (maptasker/assets/css and
    maptasker/assets/js: scrollbar theming, light-mode overrides, Map/Diagram/Tree table layout,
    the Diagram view's click-to-highlight connector styling, and the Scene canvas's handlers),
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
    ui.add_head_html(document_language_html(state=state))

    ui.add_head_html(webassets.head_html())


def initialize_screen(self: MyGui) -> None:
    """Initializes the main GUI screen layout using NiceGUI with split sidebars."""
    logger.info("Building UI Layout...")

    inject_shared_head_styles(state=self.state)
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
    _create_header(self)

    # =========================================================================
    # 2. LEFT SIDEBAR: CONFIGURATIONS, DROPDOWNS & CHECKBOXES
    # =========================================================================
    _create_left_drawer(self)

    # =========================================================================
    # 3. RIGHT SIDEBAR: ALL ACTION, HELP & SETTINGS BUTTONS
    # =========================================================================
    _create_right_drawer(self)

    # =========================================================================
    # 4. MAIN BODY CONTENT AREA
    # =========================================================================
    _create_main_body(self)

    if self.tab_to_use:
        self.gui_main_tabs_container.set_value(self.tab_to_use)


def _create_header(self: MyGui) -> None:
    """The title bar: the app's name, the MapTasker logo and the Dark Mode switch."""
    with ui.header().classes("bg-blue-900 text-white p-4 justify-between items-center") as self.gui_header:
        ui.label("MapTasker").classes("text-2xl font-bold")
        add_logo(self, "maptasker")

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


def _create_left_drawer(self: MyGui) -> None:
    """The left drawer: every option that decides what the output shows and how."""
    with (
        ui.left_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-96 force-scrollbar gap-y-0 m-0 p-0 leading-none",
        ) as self.gui_left_drawer
    ):
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
        _create_output_directory_section(self)


def _create_right_drawer(self: MyGui) -> None:
    """The right drawer: every action, report, setting and help button."""
    with (
        ui.right_drawer(value=True, fixed=True)
        .props("breakpoint=0")
        .classes(
            "bg-gray-100 dark:bg-gray-800 p-4 w-80 force-scrollbar flex flex-col items-center text-center",
        ) as self.gui_right_drawer
    ):
        ui.label(translate_string("Actions & Control")).classes("text-lg font-bold mb-2 self-center")

        ui.label(translate_string("Execution")).classes("text-xs font-bold uppercase text-gray-400 mt-2 self-center")
        _create_execution_section(self)

        ui.label(translate_string("File Operations")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-3 self-center",
        ).style("margin-top:5px")
        _create_file_and_message_buttons_section(self)

        ui.label(translate_string("Display Views")).classes(
            "text-xs font-bold uppercase text-gray-400 mt-3 self-center",
        )
        _create_view_buttons_section(self)
        _create_health_check_row(self)

        _create_history_buttons_section(self)

        _create_analysis_buttons_section(self)

        ui.button(translate_string("Clear"), on_click=self.event_handlers.clear_view_event).classes(
            "bg-blue-500"
        ).style("margin-top:-6px")

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


def _create_execution_section(self: MyGui) -> None:
    """The Execution group: Get Local XML File, Exit, and the two checkboxes that shape what Exit and a new view do."""
    get_file_color = "green" if self.state.file_to_get else "red"
    blink_class = "" if self.state.file_to_get else " animate-pulse"

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


def _create_view_buttons_section(self: MyGui) -> None:
    """The Map, Diagram and Tree buttons, side by side."""
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


def _create_health_check_row(self: MyGui) -> None:
    """Health Check and Fix Findings, sharing one row."""
    # Health Check and Fix Findings share a row, each taking half of it: Fix Findings is the
    # answer to the report Health Check produces, so it sits beside it.  Not a fourth button
    # in the row above: the drawer is w-80, and a fourth button wraps.  At half width a
    # label beside its icon wraps ("HEALTH / CHECK"), so the icon goes above the label and
    # the side padding is halved, which leaves each label room for one line.
    # Coloured through the "color" prop rather than a bg-* class, the way the Get XML and
    # Exit buttons are.  Quasar puts its own bg-primary on every button, and that wins over
    # a Tailwind bg-* added here -- a bg-teal-600 class renders plain blue.
    health_row = ui.row().classes("w-full no-wrap gap-2").style("margin-top:-6px")
    with health_row:
        self.health_check_button = (
            ui.button(
                translate_string("Health Check"),
                color="teal",
                on_click=self.event_handlers.health_check_event,
                icon="health_and_safety",
            )
            .classes("flex-1 justify-center")
            .props("stack")
            .style("padding-left:8px; padding-right:8px")
        )
    with self.health_check_button:
        ui.tooltip(
            translate_string(
                "Scan the loaded XML for broken references, unreferenced Tasks, Profiles and "
                "Scenes, naming problems, Task flow, variables, behaviour on the device, and "
                "secrets.\n\nYou choose which of those to report before it runs, and that "
                "choice is remembered.\n\nResults are displayed here and saved to a text file "
                "in the Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    # Beside Health Check, because it is the answer to the report that button produces and
    # is useless anywhere else.  Its own button rather than something inside the report:
    # the report is displayed as one escaped blob of text in a <pre> (see
    # userintr_reports.health_check_event on why), and a tick box cannot be put into one.
    with health_row:
        self.fix_findings_button = (
            ui.button(
                translate_string("Fix Findings"),
                color="teal",
                on_click=self.event_handlers.fix_findings_event,
                icon="build",
            )
            .classes("flex-1 justify-center")
            .props("stack")
            .style("padding-left:8px; padding-right:8px")
        )
    with self.fix_findings_button:
        ui.tooltip(
            translate_string(
                "Repair the Health Check findings that have an obvious fix: set a long Task's "
                "collision handling, give a blocking action a timeout, close an 'If' that is never "
                "closed, point a broken 'Goto' at a label that exists, delete a Task nothing "
                "runs.\n\nEverything is shown before anything is done, you tick what you want, and "
                "the whole lot is one press of Undo afterwards.\n\nMost kinds of finding are not "
                "offered here -- a broken 'Perform Task' or a password written into an action is a "
                "decision only you can make.",
            ),
        ).style("white-space: pre-wrap")


def _create_history_buttons_section(self: MyGui) -> None:
    """The reports that compare the loaded configuration with another one: Compare Files, Changes Since and Restore From History."""
    # Full width, because the drawer is w-80 and this label is too long to share a row, and
    # coloured through "color" because Quasar's own bg-primary beats a Tailwind bg-* class.
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
                "Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    # The comparison above needs two files and the user to know which two.  This one
    # needs neither: every configuration loaded is kept (see timeline.py), so the
    # older side is already on disk and picked by date.
    self.timeline_button = (
        ui.button(
            translate_string("Changes Since..."),
            color="teal",
            on_click=self.event_handlers.timeline_event,
            icon="history",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.timeline_button:
        ui.tooltip(
            translate_string(
                "What has changed in your configuration since a moment you choose: today, "
                "this week, this month, everything kept, or a specific date.\n\nNo file to "
                "pick -- every configuration you load is kept, compressed, in a "
                "MapTasker_Timeline folder in the current directory, and the one from back "
                "then is compared against what you have open now.\n\nResults are displayed "
                "here and saved to a text file in the Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    # Directly under Changes Since, because it is that report's other half: the report says
    # what was deleted or changed since a configuration in the history, and this puts one
    # of those objects back.  Same width and colouring as the buttons around it, for their
    # reasons (see the Health Check button).
    self.restore_history_button = (
        ui.button(
            translate_string("Restore From History"),
            color="teal",
            on_click=self.event_handlers.restore_history_event,
            icon="restore",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with self.restore_history_button:
        ui.tooltip(
            translate_string(
                "Bring back a Task, Profile or Scene that has been deleted, or put one back as it "
                "was before it was edited -- from any configuration kept in the history that "
                "'Changes Since...' reads.\n\nOne object at a time, never a merge: every restore "
                "is shown before anything happens, says what it leaves for you to do (a Profile "
                "to relink, say), and is one press of Undo afterwards.",
            ),
        ).style("white-space: pre-wrap")


def _create_analysis_buttons_section(self: MyGui) -> None:
    """The reports that read the configuration's behaviour: Variable Xref, Task Flow and What Fires When."""
    # Full width and coloured through "color" for the same two reasons the two buttons
    # above are: the drawer is w-80 and this label will not fit beside another, and
    # Quasar's own bg-primary beats a Tailwind bg-* class added here.
    # Variable Xref and its live twin share a row.  Each grows to half of it ("flex-grow"
    # rather than w-full, which would push the second onto a line of its own), and the row
    # carries the negative margin the lone button used to.
    with ui.row().classes("w-full no-wrap gap-1").style("margin-top:-6px"):
        self.variable_xref_button = ui.button(
            translate_string("Variable Xref"),
            color="teal",
            on_click=self.event_handlers.variable_xref_event,
            icon="manage_search",
        ).classes("flex-grow justify-center")
        with self.variable_xref_button:
            ui.tooltip(
                translate_string(
                    "Trace every %variable in the loaded XML: where each one is set, where it is "
                    "read, which are read but never set, which are set but never read, and which "
                    "near-identical names (%MyVar against %Myvar) are likely typos.\n\nSearched: "
                    "Task actions and their conditions, plugin configuration, Profile contexts and "
                    "Scenes.\n\nResults are displayed here and saved to a text file in the Output "
                    "Folder.",
                ),
            ).style("white-space: pre-wrap")

        self.variable_xref_live_button = ui.button(
            translate_string("Xref Live"),
            color="teal",
            on_click=self.event_handlers.variable_xref_live_event,
            icon="sensors",
        ).classes("flex-grow justify-center")
        with self.variable_xref_live_button:
            ui.tooltip(
                translate_string(
                    "The Variable Xref, plus what each global variable holds right now on the Android "
                    "device, read through Tasker's HTTP API.\n\nIt also checks the 'read but never set' "
                    "and 'set but never read' findings against the device: a variable the device does "
                    "not have is a confirmed problem, and one it does have was set or read by something "
                    "outside this file.\n\nNothing on the device is changed.  Values appear in the "
                    "saved report.",
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
                "in the Output Folder.",
            ),
        ).style("white-space: pre-wrap")

    # Under the other reports that read the configuration's behaviour, full width and
    # coloured through "color" for the reasons the buttons above give.
    fire_simulator_button = (
        ui.button(
            translate_string("What Fires When?"),
            color="teal",
            on_click=self.event_handlers.fire_simulator_event,
            icon="schedule",
        )
        .classes("w-full justify-center")
        .style("margin-top:-6px")
    )
    with fire_simulator_button:
        ui.tooltip(
            translate_string(
                "Pick a moment -- a date and time, the Wi-Fi network the device is on, the app in "
                "front and the battery level -- and see which Profiles it makes active, the order "
                "their Tasks start in, and where they collide.\n\nAnything the inputs do not "
                "describe, such as an Event or a location, is treated as unknown, so a Profile that "
                "depends on it is shown as possible and says what it is waiting on.",
            ),
        ).style("white-space: pre-wrap")


def _create_main_body(self: MyGui) -> None:
    """The middle of the window: the four tabs, the view underneath them, and the colour picker."""
    with ui.column().classes("p-6 w-full max-w-full mx-auto") as self.gui_main_column:
        with ui.row().classes("gap-4 mb-6") as self.gui_view_toolbar:
            self.current_file = ui.label(translate_string("No file loaded")).classes("text-gray-500 italic")

        # A tab's *name* -- ui.tab's first argument -- is the value ui.tabs carries, what
        # tab_to_use holds, and what TAB_NAMES and the settings file record, so it has to
        # stay English.  Only the label the user reads is translated.  Handing ui.tab the
        # translated string on its own (which makes it both name and label) meant the tab
        # names changed with the language: after a switch, the set_value(self.tab_to_use)
        # at the end of initialize_screen matched no tab at all and left every tab deselected,
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
                _create_specific_name_tab(self)

            # --- TAB 2: COLORS (MINIMIZED SPACING) ---
            with ui.tab_panel(self.tab_colors).classes("p-2 m-0") as self.gui_color_panel:
                _create_colors_tab(self)

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
                    with ui.row().classes("gap-2 mt-2"):
                        ui.button(translate_string("Display Log"), on_click=display_notification_log)
                        ui.button(translate_string("Clear Log"), on_click=clear_notification_log)

        self.content_container = ui.column().classes("w-full max-w-full min-w-0 p-0 m-0 mt-6")

        with ui.dialog() as self.picker_dialog, ui.card().classes("p-4 items-center"):
            self.picker_title_label = ui.label("").classes("font-bold text-sm mb-2")
            self.picker_engine = ui.color_picker()
            ui.button(translate_string("Cancel"), on_click=self.picker_dialog.close).classes(
                "mt-4 w-full bg-gray-500 text-white",
            )


def _create_specific_name_tab(self: MyGui) -> None:
    """The Specific Name tab: pick one Project, Profile, Task or Scene, and edit or add one."""
    ui.label(
        translate_string("Target specific Projects, Profiles, Tasks or Scenes. (Select only one)"),
    ).classes(
        "text-base mb-1",
    )
    self.currently_selected_label = ui.label("").classes("text-xs mb-2 text-gray-500 italic")

    _create_specific_name_pulldowns(self)

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
    _create_object_action_buttons(self)


def _create_specific_name_pulldowns(self: MyGui) -> None:
    """The Project, Profile, Task and Scene pulldowns, side by side."""
    # Wrap the pulldowns in a tight row so Project/Profile/Task/Scene sit side by side
    none_translatesd = translate_string("None")
    with ui.row().classes("gap-2 w-full m-0 p-0 items-start"):
        self.specific_project_optionmenu = (
            ui.select(
                [none_translatesd],
                on_change=lambda e: self.event_handlers.single_project_name_event(e.value) if e.value else None,
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
                on_change=lambda e: self.event_handlers.single_profile_name_event(e.value) if e.value else None,
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
                on_change=lambda e: self.event_handlers.single_task_name_event(e.value) if e.value else None,
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
                on_change=lambda e: self.event_handlers.single_scene_name_event(e.value) if e.value else None,
                label=translate_string("Scene"),
                with_input=True,
            )
            .classes("w-48 mb-0")
            .props("dense")
            .tooltip(translate_string("Select a specific Scene to target for display or editing."))
        )


def _create_object_action_buttons(self: MyGui) -> None:
    """The Edit/Add buttons for whatever is selected, and the Editing group pinned beside them."""
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
        # All the Edit/Add buttons (and Run On Android) are built here, but only the ones the
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
                self.run_task_button = (
                    ui.button(
                        translate_string("Run On Android"),
                        on_click=self.event_handlers.open_run_task_on_android_dialog_event,
                    )
                    .classes("flex-1 min-w-0 mt-2 bg-blue-500")
                    .style("max-width:12rem")
                    .tooltip(
                        translate_string(
                            "Run the selected Task on your Android device and see what it returned.",
                        ),
                    )
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
    # language change re-runs initialize_screen (see reload_gui) -- there
    # very much can be a live selection to match.
    refresh_object_action_buttons(self)


def _create_colors_tab(self: MyGui) -> None:
    """The Colors tab: pick a category of the output and give it a colour."""
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
                ui.checkbox(
                    translate_string("Extended"), on_change=lambda: self.event_handlers.extended_models_changed(self)
                )
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
    text = self.state._(text_to_insert) if hasattr(self.state, "_") else text_to_insert

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
    languages = sort_languages_with_priority(self.state.languages.keys())

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
        current_choice = str(getattr(self, "view_limit", VIEW_LIMIT_DEFAULT))
        self.viewlimit_optionmenu = ui.select(
            options=view_limit_options(current_choice),
            value=current_choice,
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


def _create_output_directory_section(self: MyGui) -> None:
    """The 'Output Folder' box in the sidebar drawer: where reports, exports and views go.

    Taken on Enter or on leaving the box rather than on every keystroke -- each half-typed
    path would otherwise be made as a folder on the way to the one the user meant.  Empty
    means the default, which the box shows as its placeholder so the user can see where
    that is without looking it up.
    """
    handlers = self.event_handlers
    ui.label(translate_string("Output Folder:")).classes(
        "text-sm font-semibold mt-4 mb-1 leading-none py-0 my-0 gap-y-0",
    )
    with ui.row().classes("w-full items-center gap-2 no-wrap"):
        self.output_directory_input = (
            ui.input(
                value=getattr(self, "output_directory", ""),
                placeholder=str(default_output_directory()),
            )
            .props("dense clearable")
            .classes("flex-grow")
            .on("keydown.enter", handlers.output_directory_event)
            .on("blur", handlers.output_directory_event)
        )
        with self.output_directory_input:
            ui.tooltip(
                translate_string(
                    "The folder MapTasker writes its reports (Health Check, Fix, Find, Compare and the "
                    "rest), view exports, the Map and Diagram files, and standalone exports to.\n\n"
                    "Leave it empty to use a MapTasker folder in your Documents folder.  The folder is "
                    "created if it does not exist.",
                ),
            ).style("white-space: pre-wrap")
        ui.button(
            translate_string("Default"),
            on_click=lambda: handlers.output_directory_event(""),
        ).props("dense").classes("bg-blue-600 text-white")


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
    # Save and Restore side by side, on a row of their own.  Short labels because the drawer is
    # too narrow for "Save Settings" and "Restore Settings" in one row; the "Application
    # Settings" heading above them says what they act on, and the tooltips say it again.
    with ui.row().classes("w-full gap-2 mt-0 justify-center no-wrap"):
        self.save_settings_button = ui.button(
            translate_string("Save"),
            on_click=handlers.save_settings_event,
        ).classes(
            "bg-indigo-600 text-white justify-center",
        )
        with self.save_settings_button:
            ui.tooltip(translate_string("Save these settings for later use."))

        self.restore_settings_button = ui.button(
            translate_string("Restore"),
            on_click=handlers.restore_settings_event,
        ).classes(
            "bg-indigo-600 text-white justify-center",
        )
        with self.restore_settings_button:
            ui.tooltip(translate_string("Restore the settings from a previously saved session."))

    with ui.row().classes("w-full gap-2 mt-0 justify-center"):
        self.report_issue_button = (
            ui.button(
                translate_string("Report Issue"),
                on_click=handlers.report_issue_event,
            )
            .classes(
                "bg-gray-600 text-white justify-center",
            )
            .style("margin-top:-6px")
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
    if not self.state.mono_fonts:
        font_items = get_font_choices()
        self.state.mono_fonts = font_items
    else:
        font_items = self.state.mono_fonts

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
        # opening the Android panel (get_xml_from_android_event in userintr_android.py) adds a panel
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
