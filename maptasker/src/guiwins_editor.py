"""The scaffolding every Edit dialog is built on: the Properties button, the pending-changes banner and the Redact tick box."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_editor: what the Edit dialogs share, in a module of its own so that every one of     #
#                 them can import it at the top of its file.                                   #
#                                                                                        #
# These lived in guiwins, which imports the Task, Profile and Scene editor modules -- so those   #
# modules could only reach them from inside a function, and every such import was a cycle held  #
# off by hand.  Nothing here imports guiwins or any editor, so the cycle is gone rather than      #
# deferred.                   #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import xml.etree.ElementTree as ETW
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import objprops
from maptasker.src.maputil2 import translate_string

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.userintr import MyGui


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
