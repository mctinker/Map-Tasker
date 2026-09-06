"""guiwins_refactor: the Refactor dialog -- the four structural moves, with a preview."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_refactor: where maprefac hangs off the GUI.                                    #
#                                                                                        #
# One dialog, four modes, one preview area.  Extract a run of a Task's actions into a    #
# Task of its own; inline a Perform Task; move a Task or a Profile to another Project;   #
# duplicate a Project, Profile, Task or Scene.                                           #
#                                                                                        #
# EVERYTHING BELOW IS ARRANGED AROUND ONE RULE, the same one the Replace tab is built    #
# around: the Apply button is disabled until a preview exists FOR THE VALUES CURRENTLY   #
# IN THE FIELDS, and touching any field clears the preview and disables it again.  There #
# is then no path through these widgets that reaches maprefac.apply without the user     #
# having seen maprefac.report_rows first.  That is the design made structural rather     #
# than left to the dialog to remember -- and it matters more here than it does for a     #
# Replace, because a refactor is all-or-nothing: there are no tick boxes to walk, so the #
# preview is the only place the user gets to disagree with it.                           #
#                                                                                        #
# WHY THIS IS ITS OWN DIALOG AND NOT A TAB OF Find/Replace                               #
#                                                                                        #
# Replace is a tab of Find because it asks the same question Find does -- "where is this #
# action" -- and then changes the answers, so the two share an index and a pulldown.     #
# A refactor asks nothing.  It is told a Task and a range of actions, and none of the    #
# four modes has any use for mapfind's index, which is the whole thing that dialog is    #
# built around.  Sharing it would mean paying for a 60ms scan on every open to use none  #
# of it.                                                                                 #
#                                                                                        #
# WHY THE PREVIEW IS RENDERED FROM Rows RATHER THAN LAID OUT AS WIDGETS                  #
#                                                                                        #
# maprefac.report_rows already decides what a preview says and in what order -- blocks   #
# instead of steps, warnings above steps, wrapped prose -- and the same rows are what    #
# gets written to a file by Save Preview.  Laying the same thing out a second time in    #
# widgets is how the file and the screen come to disagree about what a refactor would    #
# do, which is the one disagreement this feature cannot afford.                          #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import maprefac
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

# The four modes, in the order they are offered.  Extract first because it is the one
# people come here for -- a Task that has grown too long is the reason anybody opens this.
EXTRACT, INLINE, MOVE, DUPLICATE = "extract", "inline", "move", "duplicate"

_MODE_LABELS = {
    EXTRACT: "Extract actions",
    INLINE: "Inline a call",
    MOVE: "Move to a Project",
    DUPLICATE: "Duplicate",
}

# One line under the toggle saying what the chosen mode does.  Worth the space: "Extract"
# and "Inline" are the names of the operations to somebody who already knows them, and
# these are the only place the dialog says what they mean.
_MODE_BLURBS = {
    EXTRACT: (
        "Move a run of a Task's actions into a new Task of its own, and put a Perform Task "
        "in their place.  What runs, and in what order, is unchanged."
    ),
    INLINE: (
        "Replace a Perform Task with a copy of the actions of the Task it calls.  The called "
        "Task is left where it is -- anything else calling it keeps working."
    ),
    MOVE: (
        "Change which Project owns a Task or a Profile.  A Profile takes its Tasks with it, "
        "except any that a Profile left behind still runs."
    ),
    DUPLICATE: (
        "Copy an object under a new name.  A Profile's Tasks and a Project's whole contents "
        "are copied too, and the copies' Perform Task calls point at the copies."
    ),
}

# What a Duplicate can be asked about.  Project first: it is the one whose result is least
# obvious and most useful, and the one people mean by "duplicate" more often than not.
_DUPLICATE_KINDS = {
    PROJECT: "Project",
    PROFILE: "Profile",
    TASK: "Task",
    SCENE: "Scene",
}

# Only two things can move between Projects, because only two things a Project lists have
# an owner in any meaningful sense.  A Scene is listed by <scenes> too, and is left out
# deliberately: nothing in this program edits a Scene's Project membership except by
# adding or deleting the Scene, and a half-supported move is worse than none.
_MOVE_KINDS = {TASK: "Task", PROFILE: "Profile"}

# How many preview lines are drawn.  A Project duplication of a large Project runs to a
# few dozen; nothing produces hundreds, unlike a Replace, so this is a guard against a
# pathological configuration rather than a routine cut.
_PREVIEW_LINE_LIMIT = 400


def build_refactor_dialog(
    title: str,
    make_jump: Callable,
    rebuild_view: Callable[[], Coroutine],
) -> ui.dialog | None:
    """Build and return the Refactor dialog, or None if there is nothing loaded to refactor.

    Takes the three things it needs from the view and nothing else -- what the view is
    called, how to follow a preview row to the object it names, and how to redraw the view
    once something has changed.  Passed in rather than imported: this module is reached
    FROM guiwins, and reaching back into it for go_to_target would be a circular import for
    two functions' worth of behaviour.
    """
    if not PrimeItems.tasker_root_elements.get("all_tasks"):
        ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
        return None

    # `persistent`, by the same rule as the Find/Replace dialog: a dialog holding work in
    # progress or asking for a decision leaves on a button and nothing else.  A preview is
    # both, and the pulldowns make it acute -- Quasar renders a select's popup OUTSIDE the
    # card, so the click that picks a Task would otherwise be the click that closes this.
    with ui.dialog().props("persistent") as dialog, ui.card().classes("w-[900px] max-w-full p-6"):
        # `title` names the view when this is opened from one and is empty from the main
        # window, which is the ordinary case now -- so the heading is just "Refactor" there
        # rather than "Refactor -- " trailing off into nothing.
        heading = f"{translate_string('Refactor')} -- {title}" if title else translate_string("Refactor")
        ui.label(heading).classes("text-lg font-bold text-blue-600")

        # The plan on screen, and the field values it was built from.  Held in a dict
        # rather than as locals because every closure below both reads and writes it, and
        # a Plan cannot be remembered on the view the way a Find query can -- it holds live
        # elements, and holding them across a reopen is the stale-handle case
        # maprefac.apply's attachment check exists to catch.
        held: dict = {"plan": None, "inputs": None}

        mode = ui.toggle({key: translate_string(label) for key, label in _MODE_LABELS.items()}, value=EXTRACT).props(
            "dense",
        )
        # One tooltip for the whole toggle rather than one per option: ui.toggle renders its
        # options itself, so there is nothing to hang four separate tooltips on.  It earns
        # its length by describing the three modes you are NOT on -- the line under the
        # toggle only ever describes the one you are.
        _tip(
            mode,
            "Which structural move to make.\n\n"
            "Extract actions -- pull a run of a Task's actions out into a Task of their own, "
            "leaving a 'Perform Task' in their place.\n\n"
            "Inline a call -- the reverse: replace a 'Perform Task' with a copy of the actions "
            "of the Task it calls, leaving that Task where it is.\n\n"
            "Move to a Project -- change which Project owns a Task or a Profile.\n\n"
            "Duplicate -- copy a Project, Profile, Task or Scene under a new name.\n\n",
        )
        blurb = ui.label(translate_string(_MODE_BLURBS[EXTRACT])).classes(
            "text-xs text-gray-500 italic mb-3 mt-1",
        )

        widgets = _build_mode_rows()
        summary = ui.label("").classes("text-sm font-bold text-orange-500 mt-3")
        preview_area = ui.scroll_area().classes("w-full h-80 border rounded dark:border-gray-700 mt-1")

        def current_inputs() -> tuple:
            """Every field that feeds a plan, as one comparable value.

            What "the preview matches the fields" is checked against.  Every field of every
            mode, not just the visible ones: the mode itself is part of it, so switching
            away and back cannot leave a preview from the other mode looking current.
            """
            return (
                mode.value,
                widgets["extract_task"].value,
                widgets["extract_from"].value,
                widgets["extract_to"].value,
                (widgets["extract_name"].value or "").strip(),
                widgets["inline_task"].value,
                widgets["inline_call"].value,
                widgets["move_kind"].value,
                widgets["move_object"].value,
                widgets["move_project"].value,
                widgets["duplicate_kind"].value,
                widgets["duplicate_object"].value,
                (widgets["duplicate_name"].value or "").strip(),
            )

        def invalidate() -> None:
            """Throw away the preview and disable Apply.  Every field change comes here.

            The whole of the rule this dialog is built around.  Nothing else disables the
            button, and nothing re-enables it except a preview being drawn.
            """
            held.update(plan=None, inputs=None)
            apply_button.disable()
            preview_area.clear()
            summary.set_text("")

        def draw(plan: maprefac.Plan) -> None:
            """Draw the plan, from the same Rows that Save Preview writes to a file.

            Every row that points at something is a link, because the only way to judge a
            refactor is to go and look at what it names -- and on the two operations that
            refuse most often, the block's explanation names the actions that would have to
            be selected differently.
            """
            preview_area.clear()
            summary.set_text(
                f"{plan.what} -- "
                + (
                    translate_string("cannot be done")
                    if plan.is_blocked
                    else f"{len(plan.steps)} {translate_string('steps')}"
                ),
            )

            with preview_area, ui.column().classes("w-full gap-0 p-2"):
                for row in maprefac.report_rows(plan)[:_PREVIEW_LINE_LIMIT]:
                    if row.target is not None:
                        ui.link(row.text, "#").on("click", make_jump(row.target)).classes(
                            "text-blue-600 dark:text-blue-400 font-mono text-xs whitespace-pre "
                            "decoration-dotted hover:underline",
                        )
                    else:
                        ui.label(row.text).classes(
                            "font-mono text-xs whitespace-pre " + _row_classes(row.text),
                        )

        def preview() -> None:
            """Build the plan for what is in the fields, and show it.

            A blocked plan is drawn like any other and leaves Apply disabled.  It is not an
            error and must not be notified as one: the user asked whether this could be
            done, and the block is the answer to that question, printed where they are
            already looking.
            """
            plan = plan_for(mode.value, widgets)
            if plan is None:
                ui.notify(translate_string("Fill in every box first."), type="warning")
                return
            held.update(plan=plan, inputs=current_inputs())
            draw(plan)
            if plan.can_apply:
                apply_button.enable()
            else:
                apply_button.disable()

        async def do_apply() -> None:
            """The Apply button.  Only ever applies the plan on screen.

            Re-checks that the plan matches the fields even though every field invalidates
            it: this is the last point at which the check is cheap, and the cost of it
            being wrong is a configuration restructured in a way nobody previewed.
            """
            plan = held["plan"]
            if plan is None or held["inputs"] != current_inputs():
                ui.notify(translate_string("Press Preview first."), type="warning")
                invalidate()
                return

            done, errors = maprefac.apply(plan)
            for message in errors[:4]:
                ui.notify(message, type="negative")
            if not done:
                return

            ui.notify(
                f"{plan.what}. {translate_string('Undo is available.')}",
                type="positive",
                position="top",
            )
            invalidate()
            dialog.close()
            # Refill the pulldowns before redrawing: a refactor is the one operation here
            # that ADDS and REMOVES objects, so unlike a Replace, every option in every
            # pulldown may now be stale -- a Task extracted into is not in the Task list,
            # and a Project duplicated is not in the Project list.  _stale's record is
            # cleared first, because this is the one refill that must happen even though
            # nothing the user chose has changed: what changed is the configuration.
            widgets["filled"].clear()
            fill_options(widgets)
            await rebuild_view()

        def save_preview() -> None:
            """Write the preview to a file.

            Worth having for the refactor the user decided NOT to do as much as the one
            they did: a block's explanation names the actions that would have to be selected
            differently, and that is a work list which does not survive closing this.
            """
            plan = held["plan"]
            if plan is None:
                ui.notify(translate_string("Press Preview first."), type="warning")
                return
            file_name = maprefac.write_refactor_report(maprefac.report_rows(plan))
            if file_name:
                ui.notify(f"{translate_string('Refactor preview saved as')} {file_name}", type="positive")
            else:
                ui.notify(translate_string("Refactor preview could not be saved."), type="negative")

        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            preview_button = ui.button(translate_string("Preview"), on_click=preview).classes(
                "bg-blue-600 text-white px-4",
            )
            _tip(
                preview_button,
                "Work out what this refactor would do, and show it -- step by step, or the reason "
                "it will not be done at all.\n\n"
                "Nothing is changed by pressing this.\n\n"
                "Every place the preview names is a link: click one to open it in a tab of its own "
                "and look at it before you decide.\n\n",
            )
            apply_button = ui.button(translate_string("Apply"), on_click=do_apply).classes(
                "bg-orange-600 text-white px-4",
            )
            apply_button.disable()
            _tip(
                apply_button,
                "Carry out the refactor exactly as the preview describes it.\n\n"
                "Greyed out until a preview exists for what is in the boxes right now -- changing "
                "any box clears the preview, so what you apply is always what you were shown.\n\n"
                "However many objects it touches, the whole refactor is one press of Undo "
                "afterwards.\n\n",
            )
            save_button = ui.button(translate_string("Save Preview"), on_click=save_preview).classes(
                "bg-blue-600 text-white px-4",
            )
            _tip(
                save_button,
                "Write the preview to a text file in the working folder.\n\n"
                "Worth having for the refactor you decide NOT to do as much as the one you do: a "
                "refusal names the actions that would have to be selected differently, and that "
                "list does not survive closing this window.\n\n",
            )
            close_button = ui.button(translate_string("Close"), on_click=dialog.close).classes(
                "bg-red-500 text-white px-4",
            )
            _tip(
                close_button,
                "Close this window.\n\n"
                "Nothing is changed: a refactor happens when Apply is pressed and at no other "
                "time, so there is never anything left pending here.\n\n",
            )

        def mode_changed() -> None:
            """Show one mode's fields and hide the rest, and start it with no preview."""
            blurb.set_text(translate_string(_MODE_BLURBS.get(mode.value, "")))
            for key, row in widgets["rows"].items():
                row.set_visibility(key == mode.value)
            invalidate()

        fill_options(widgets)
        mode.on_value_change(mode_changed)
        # The two pulldowns whose CONTENTS depend on another pulldown, rather than merely
        # invalidating with it: which actions there are to extract, and which of them are
        # calls, are facts about the Task chosen above.
        widgets["extract_task"].on_value_change(lambda: (_fill_actions(widgets), invalidate()))
        widgets["inline_task"].on_value_change(lambda: (_fill_calls(widgets), invalidate()))
        widgets["move_kind"].on_value_change(lambda: (_fill_move_objects(widgets), invalidate()))
        widgets["duplicate_kind"].on_value_change(lambda: (_fill_duplicate_objects(widgets), invalidate()))
        for key in (
            "extract_from",
            "extract_to",
            "extract_name",
            "inline_call",
            "move_object",
            "move_project",
            "duplicate_object",
            "duplicate_name",
        ):
            widgets[key].on_value_change(invalidate)
        mode_changed()

    return dialog


def _tip(element: ui.element, text: str) -> None:
    """Attach one of this dialog's explanatory tooltips to a control.

    Same shape as the Find/Replace button's on the Map toolbar: the text is translated, and
    pre-wrap is what makes the blank lines in it survive -- without it Quasar collapses the
    whole thing into one paragraph and the tooltip becomes the wall of text it was written
    not to be.

    A tooltip here is not a restatement of the label.  Each says the thing the label cannot:
    what Preview does NOT do, why Apply is greyed out, what an empty name box means.
    """
    with element:
        ui.tooltip(translate_string(text)).style("white-space: pre-wrap")


def _row_classes(text: str) -> str:
    """How one preview line is coloured, from what it says.

    Read off the text rather than passed down from report_rows, because the Rows are
    shared with the file that Save Preview writes and a colour is not a property of a
    report -- it is a property of this screen.
    """
    if text.startswith("CANNOT BE DONE"):
        return "font-bold text-red-500"
    if text.startswith("BEFORE YOU DO THIS"):
        return "font-bold text-orange-600 dark:text-orange-400"
    if text.startswith("WHAT WILL HAPPEN"):
        return "font-bold text-green-600 dark:text-green-400"
    return "text-gray-700 dark:text-gray-300"


def _build_mode_rows() -> dict:
    """Every mode's fields, built once and shown one row at a time.

    All four rows exist from the start rather than being rebuilt on each mode change, so
    that switching modes and switching back finds the boxes as they were left.  Somebody
    who goes to look at a Project's contents before deciding on a name should not come back
    to an empty form.
    """
    # What each dependent pulldown was last filled from -- see _stale.
    widgets: dict = {"rows": {}, "filled": {}}

    with ui.column().classes("w-full gap-0 mt-2") as widgets["rows"][EXTRACT]:
        with ui.row().classes("w-full items-center gap-2"):
            widgets["extract_task"] = _select(
                translate_string("From Task"),
                "flex-1 min-w-[240px]",
                "The Task to take actions out of.  Only the Task the pulldowns behind this window "
                "select is offered -- the same rule the Edit buttons follow.",
            )
            widgets["extract_from"] = _select(
                translate_string("First action"),
                "flex-1 min-w-[180px]",
                "The first action of the run to move, numbered exactly as the Map numbers it.",
            )
            widgets["extract_to"] = _select(
                translate_string("Last action"),
                "flex-1 min-w-[180px]",
                "The last action of the run.  Everything between the two ends moves, so the run "
                "has to be unbroken -- and has to take whole If and For blocks with it.",
            )
            widgets["extract_name"] = (
                ui.input(label=translate_string("New Task name"))
                .classes("flex-1 min-w-[180px]")
                .props("dense")
                .tooltip(
                    translate_string(
                        "What to call the new Task.  The 'Perform Task' left behind calls it by "
                        "this name, so it has to be a name no other Task already has.",
                    ),
                )
            )
        # Why the Task list is short, stated where the short list is.  Without this the
        # pulldown looks broken rather than narrowed -- "my Task is not in here" is the
        # first thing somebody thinks, and the reason is two rooms away in the main window.
        # Same wording as the Find dialog's own scope note, because it is the same fact.
        widgets["extract_scope_note"] = ui.label("").classes(
            "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1 mt-2",
        )

    with ui.row().classes("w-full items-center gap-2 mt-2") as widgets["rows"][INLINE]:
        widgets["inline_task"] = _select(
            translate_string("In Task"),
            "flex-1 min-w-[260px]",
            "The Task holding the call you want to fold back in.",
        )
        widgets["inline_call"] = _select(
            translate_string("Inline this call"),
            "flex-1 min-w-[300px]",
            "Which 'Perform Task' to replace with a copy of the actions of the Task it calls.  "
            "Only the calls in the Task chosen alongside are offered.",
        )

    with ui.row().classes("w-full items-center gap-2 mt-2") as widgets["rows"][MOVE]:
        widgets["move_kind"] = ui.toggle(
            {key: translate_string(label) for key, label in _MOVE_KINDS.items()},
            value=TASK,
        ).props("dense")
        _tip(
            widgets["move_kind"],
            "Whether you are moving a Task or a Profile.\n\n"
            "A Profile takes the Tasks it runs with it -- except any that a Profile staying "
            "behind also runs, which would be taken out from under it.  The preview names any "
            "that stay, and why.\n\n"
            "A Scene is not offered: nothing else in this program moves a Scene between "
            "Projects, and a half-supported move is worse than none.\n\n",
        )
        widgets["move_object"] = _select(
            translate_string("Move this"),
            "flex-1 min-w-[260px]",
            "The Task or Profile whose owning Project is to change.",
        )
        widgets["move_project"] = _select(
            translate_string("...to this Project"),
            "flex-1 min-w-[220px]",
            "The Project that will own it afterwards.  It is removed from every Project that "
            "lists it now, not just the first.",
        )

    with ui.row().classes("w-full items-center gap-2 mt-2") as widgets["rows"][DUPLICATE]:
        widgets["duplicate_kind"] = ui.toggle(
            {key: translate_string(label) for key, label in _DUPLICATE_KINDS.items()},
            value=PROJECT,
        ).props("dense")
        _tip(
            widgets["duplicate_kind"],
            "What kind of object to copy.\n\n"
            "A Task and a Scene own nothing, so each is copied alone.  A Profile's Tasks are "
            "copied with it, and a Project's whole contents are -- otherwise the copy would "
            "share the original's insides and editing one would change both.\n\n"
            "Inside a copied Project, 'Perform Task' and Show/Hide Scene actions are pointed at "
            "the copies rather than back at the originals.  Global variables are shared, not "
            "copied; the preview says so up front.\n\n",
        )
        widgets["duplicate_object"] = _select(
            translate_string("Duplicate this"),
            "flex-1 min-w-[240px]",
            "The object to copy.  The copy is filed under the same Projects as the original.",
        )
        widgets["duplicate_name"] = (
            ui.input(label=translate_string("New name (optional)"))
            .classes("flex-1 min-w-[200px]")
            .props("dense")
            .tooltip(
                translate_string(
                    "What to call the copy.  Left empty, a free name is chosen for you -- the "
                    "original's with '(copy)' after it.",
                ),
            )
        )

    return widgets


def _select(label: str, classes: str, tip: str = "") -> ui.select:
    """One pulldown, typable, with the one-line tooltip the app's other pulldowns carry.

    with_input on every one of them: a configuration with 800 Tasks makes a plain pulldown
    unusable, and which Task is being refactored is the first thing every mode asks.

    The short .tooltip() form rather than _tip's: these say what the box is for in a line,
    which is the same job -- and the same wording -- as the Project/Profile/Task/Scene
    pulldowns behind this dialog ("Select a specific Scene to target for display or
    editing").  The long form is for the buttons, where what is NOT obvious takes a
    paragraph.
    """
    pulldown = ui.select({}, label=label, with_input=True).classes(classes).props("dense")
    if tip:
        pulldown.tooltip(translate_string(tip))
    return pulldown


def fill_options(widgets: dict) -> None:
    """Fill every pulldown from the loaded configuration.

    Public for the same reason plan_for is: which pulldown gets what, and when one is filled
    in for the user rather than left to them, is a decision rather than a layout -- so it is
    worth testing without a browser.

    Called when the dialog is built and again after an Apply, because a refactor is the one
    operation in this program that both adds and removes objects -- see do_apply.

    Extract's Task pulldown is the one that is NARROWED to the single-item selection -- and
    filled in outright when that leaves only one Task; every other pulldown here offers the
    whole file and chooses nothing.  maprefac.extract_scope has the reasoning --
    in short, Extract is the only operation that reaches inside a Task, so it keeps the same
    contract as the Edit buttons beside this dialog, while the three that act on an object
    as a whole have no business being tied to what is selected for display.
    """
    tasks = dict(maprefac.task_choices())

    # Extract's Task, chosen for the user when the selection leaves nothing to choose.
    #
    # A single Task selected narrows this pulldown to that one Task, and then asks the user
    # to pick it out of a list of one -- a step that cannot go any other way and so is not a
    # decision at all.  Filling it in is the whole of what that step was worth, and it
    # cascades: the First/Last action pulldowns are filled from it by _fill_actions just
    # below, so the dialog opens ready to be asked a question rather than ready to be told
    # something it already knows.
    #
    # Keyed on "exactly one offered" rather than on "a Task is selected", because those are
    # the same thing wherever it matters and the first also covers a Profile that runs only
    # one Task.  It can never guess: where there is a choice to make, it makes none.
    scoped = maprefac.task_choices(maprefac.extract_scope())
    only_task = scoped[0][0] if len(scoped) == 1 else None
    widgets["extract_task"].set_options(dict(scoped), value=only_task)

    widgets["inline_task"].set_options(tasks, value=None)
    widgets["move_project"].set_options({name: name for name in maprefac.project_choices()}, value=None)
    _fill_actions(widgets)
    _fill_calls(widgets)
    _fill_move_objects(widgets)
    _fill_duplicate_objects(widgets)
    _describe_extract_scope(widgets)


def _describe_extract_scope(widgets: dict) -> None:
    """Say what Extract has been narrowed to, or nothing at all when it has not been.

    Three states rather than two.  The empty one matters: a Scene selected puts no Tasks in
    scope, so the pulldown is not merely short but empty, and an empty pulldown with no
    explanation reads as a bug in the dialog rather than as an answer about the selection.
    """
    scope = maprefac.extract_scope()
    note = widgets["extract_scope_note"]
    if scope.is_everything:
        note.set_text("")
        note.set_visibility(False)
        return

    note.set_visibility(True)
    # Worded as a statement about the SELECTION, not about what is drawn.  current_scope
    # reads the single-item pulldowns, and this dialog now opens from the panel those
    # pulldowns are in -- where there may well be no Map on screen at all, so "the Map is
    # showing" would be a claim about something that is not there.  It is the same sentence
    # the Edit buttons beside it use ("Select a single Task first (Task pulldown above)"),
    # said from the other side: here one IS selected, and this is what that means.
    if widgets["extract_task"].options:
        note.set_text(
            f"{translate_string('Extract works on')} {scope.phrase}, "
            f"{translate_string('selected in the pulldowns above')}. "
            f"{translate_string('Change or clear that selection to reach other Tasks')}.",
        )
    else:
        note.set_text(
            f"{scope.phrase} {translate_string('is selected above and has no Tasks to extract from')}. "
            f"{translate_string('Change or clear that selection to reach other Tasks')}.",
        )


def _stale(widgets: dict, slot: str, key: object) -> bool:
    """Whether a dependent pulldown needs refilling, and record that it has been.

    THE GUARD THAT MAKES THE DEPENDENT PULLDOWNS USABLE, and it is not an optimisation.
    Refilling a select clears what is chosen in it -- that is the point, since the old
    choice names an action of a Task nobody is looking at any more -- but a Quasar select
    built with_input re-emits its value on events that are not changes at all, blur among
    them.  Left ungated, choosing the Last action and then clicking into the name box fires
    the Task select's on_value_change, refills both action pulldowns, and silently empties
    the choice just made.  Observed exactly that way; the box goes blank and Preview then
    says the form is not filled in, about a form that plainly is.

    So the fill is keyed on what it was built FROM, and a value-change that did not change
    the value does nothing.
    """
    if widgets["filled"].get(slot) == key:
        return False
    widgets["filled"][slot] = key
    return True


def _fill_actions(widgets: dict) -> None:
    """The chosen Task's actions, in both of Extract's two pulldowns."""
    task_id = widgets["extract_task"].value or ""
    if not _stale(widgets, "actions", task_id):
        return
    choices = {str(number): label for number, label in maprefac.action_choices(task_id)}
    # A dict each, not one shared between them.  Two selects holding the same object is
    # asking for one's filtering to be visible in the other, and these two are the pair
    # most likely to be filtered at the same moment -- they are the two ends of one range.
    widgets["extract_from"].set_options(dict(choices), value=None)
    widgets["extract_to"].set_options(dict(choices), value=None)


def _fill_calls(widgets: dict) -> None:
    """The chosen Task's Perform Task actions, and only those -- see maprefac.call_choices."""
    task_id = widgets["inline_task"].value or ""
    if not _stale(widgets, "calls", task_id):
        return
    widgets["inline_call"].set_options(
        {str(number): label for number, label in maprefac.call_choices(task_id)},
        value=None,
    )


def _fill_move_objects(widgets: dict) -> None:
    """Tasks or Profiles, depending on which kind is being moved."""
    kind = widgets["move_kind"].value
    if not _stale(widgets, "move", kind):
        return
    choices = maprefac.profile_choices() if kind == PROFILE else maprefac.task_choices()
    widgets["move_object"].set_options(dict(choices), value=None)


def _fill_duplicate_objects(widgets: dict) -> None:
    """Whatever kind of object is being duplicated, keyed the way its table keys it.

    Projects and Scenes by name, Profiles and Tasks by id -- the same split every table in
    this program uses, and the one maprefac.plan_duplicate's `key` expects.
    """
    kind = widgets["duplicate_kind"].value
    if not _stale(widgets, "duplicate", kind):
        return
    if kind == PROJECT:
        choices = {name: name for name in maprefac.project_choices()}
    elif kind == SCENE:
        choices = {name: name for name in maprefac.scene_choices()}
    elif kind == PROFILE:
        choices = dict(maprefac.profile_choices())
    else:
        choices = dict(maprefac.task_choices())
    widgets["duplicate_object"].set_options(choices, value=None)


def plan_for(mode_value: str, widgets: dict) -> maprefac.Plan | None:
    """Build the plan the fields describe, or None if they do not describe one yet.

    Public because it is the only part of this module that is a decision rather than a
    layout, and so the only part worth testing without a browser: everything else here is
    widgets and wiring.

    None means "not enough has been filled in", which is a different thing from a plan that
    is blocked -- one is answered by a nudge, the other by a preview -- and the two must not
    be collapsed.  An empty box is the user's turn; a block is the tool's answer.
    """
    if mode_value == EXTRACT:
        task_id = widgets["extract_task"].value
        first, last = widgets["extract_from"].value, widgets["extract_to"].value
        if not task_id or first is None or last is None:
            return None
        first, last = sorted((int(first), int(last)))
        return maprefac.plan_extract(task_id, list(range(first, last + 1)), widgets["extract_name"].value or "")

    if mode_value == INLINE:
        task_id, call = widgets["inline_task"].value, widgets["inline_call"].value
        if not task_id or call is None:
            return None
        return maprefac.plan_inline(task_id, int(call))

    if mode_value == MOVE:
        key, project = widgets["move_object"].value, widgets["move_project"].value
        if not key or not project:
            return None
        return maprefac.plan_move(widgets["move_kind"].value, key, project)

    if mode_value == DUPLICATE:
        key = widgets["duplicate_object"].value
        if not key:
            return None
        return maprefac.plan_duplicate(widgets["duplicate_kind"].value, key, widgets["duplicate_name"].value or "")

    return None
