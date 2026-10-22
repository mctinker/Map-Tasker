"""GUI Window Classes and Definitions (NiceGUI Version).

What is left here: the popup and "Changes Pending" scaffolding every editor shares, the
session Undo controls, the Save To Android panel, the light/dark switch, and the screen's
own initialization.

The dialog families and views that were taking this file past 14,500 lines now live beside
it, one module per family:

    guiwins_taskedit.py         Edit/Add/Delete Task, the Action editor and its pickers
    guiwins_profedit.py         Edit/Add/Delete Profile and its Save To Android panel
    guiwins_project.py          the Project dialogs: Add, Edit, Save To Android
    guiwins_scene.py            the Scene dialogs: Add, Edit, Delete, Save To Android
    guiwins_props.py            the Object Properties form
    guiwins_dialogs.py          Health Check, helper Tasks, Overwrite, Changes Since, Rename, Delete Project
    guiwins_drawers.py          the screen's frame: header, drawers, main body
    guiwins_tabs.py             the main body's tabs and the option sections in them
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

import html
import re
import time
from collections import deque
from typing import TYPE_CHECKING, Any, cast

from nicegui import ui

from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.getputer import save_restore_args
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import (
    DIAGRAM_PROFILES_PER_LINE,
    NOTIFY_TIMEOUT_DEFAULT,
    VIEW_LIMIT_DEFAULT,
)
from maptasker.src.edit import roundtrip, sessundo, taskedit_model
from maptasker.src.gui.guistate import remember_setting
from maptasker.src.gui.guiutils import (
    android_address_defaults,
    remember_android_address_fields,
)

# The dialog families split out of this file, which had grown past 14,500 lines.  Each is
# imported for the handful of names this module still calls into: the Scene canvas the
# Preview draws through, the two designers the Scene editor body mounts, and the Action
# editor and pickers the Scene Event tab reuses.  guiwins_profedit is not among them --
# nothing here calls it; userintr reaches it directly.
from maptasker.src.gui.guiwins_nav import (
    live_views,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


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
        original(message, **cast("dict[str, Any]", kwargs))

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


# Run in the browser when text in a rich popup is clicked: a link goes to a new tab, anything else is left alone.
OPEN_LINKS_IN_NEW_TAB = """(event) => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    event.preventDefault();
    window.open(link.href, '_blank', 'noopener,noreferrer');
}"""


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
                # An underscore inside a word (the 'MapTasker_Timeline' and 'MapTasker_Backups' folder
                # names) is an italic marker to the Markdown renderer, which then italicized everything
                # between the two.  Escape those, and only those: a real __italic__ run is untouched.
                markdown = ui.markdown(re.sub(r"(?<=[A-Za-z0-9])_(?=[A-Za-z0-9])", r"\\_", message))
                markdown.classes(text_classes)
                # A link in the help (the Command Reference wiki, for one) opens in a tab of its
                # own: following it in this one would take the browser away from the running GUI.
                # Done as a click handler because the Markdown is sanitized in the browser, and
                # that strips a target="_blank" written into the link itself.
                markdown.on("click", js_handler=OPEN_LINKS_IN_NEW_TAB)
            else:
                ui.label(message).classes(text_classes)
        if close_button:
            ui.button(translate_string("Close"), on_click=dialog.close).classes("mt-6 bg-red-500 text-white w-full")

    dialog.open()
    return dialog


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


# How often the Pre-Build The Map checkbox looks for a configuration that has just been loaded.
PREBUILD_POLL_SECONDS = 1.0


def build_edit_history_dialog(state: RunState) -> None:
    """Lists what the session's Undo would step back through, most recent first.

    Read-only, and deliberately so.  Jumping straight to an arbitrary point in the list is
    the obvious next feature and is not this one: every entry is a whole configuration, so
    "go back four steps" would silently discard three edits that are not on screen.  Undo,
    one press at a time, keeps the user looking at what each press actually did.
    """
    entries = sessundo.history(state)

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


def create_refactor_button(self: MyGui) -> None:
    """The Refactor button, in the 'Specific Name' tab's Editing group.

    Here rather than on the Map/Diagram toolbar, where it started, because a refactor is an
    EDIT and belongs with the Edit/Add buttons and the Undo that takes it back.  Three of
    its four operations -- inline a call, move to another Project, duplicate an object --
    name an object and act on it whole; nothing about them depends on what is drawn, so
    hanging them off a view meant a Map had to be built before any of them could be reached.

    NOT one of the per-kind Edit/Add pairs, and so not hidden with them: one dialog covers
    Projects, Profiles, Tasks and Scenes together, and which of them is selected decides
    only what Extract offers (see maprefac_model.extract_scope), never whether the button works.
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


def create_undo_section(self: MyGui) -> None:
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
        on_click=lambda: build_edit_history_dialog(self.state),
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
        self.undo_edit_button.set_enabled(sessundo.can_undo(self.state))
        self.redo_edit_button.set_enabled(sessundo.can_redo(self.state))
        if next_undo := sessundo.next_undo_label(self.state):
            self.undo_next_label.text = f"{translate_string('Undo')}: {next_undo}"
        elif next_redo := sessundo.next_redo_label(self.state):
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


def android_device_fields(gui: MyGui) -> dict:
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

    ip_address = ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full")
    ip_port = ui.input(translate_string("Port"), value=default_port).classes("w-full")
    fields: dict[str, ui.element] = {"ip_address": ip_address, "ip_port": ip_port}
    remember_android_address_fields(gui, ip_address, ip_port)
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
    edited_task: taskedit_model.EditableTask,
    field_refs: dict,
    parent_dialog: ui.dialog,
    on_created: Callable[[str], None] | None = None,
) -> None:
    """Prompts for the Android device's IP address and port, then either writes the
    current Task (name/priority/args as they stand in the parent dialog's fields)
    onto the device's storage under /Tasker/tasks as a standalone .tsk.xml file --
    see taskedit_save.save_task_to_android_file -- or imports it directly into Tasker via
    the HTTP API's POST /api/import -- see taskedit_save.save_task_to_android.  The same
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
        android_field_refs = android_device_fields(self)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=android_dialog.close).props("outline")
            save_to_android = ui.button(
                translate_string("Save As File"),
                on_click=lambda: self.event_handlers.android.save_task_to_android_file_event(
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
                on_click=lambda: self.event_handlers.android.save_task_to_android_event(
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
    self.prebuild_map = False
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
