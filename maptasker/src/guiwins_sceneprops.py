"""The Scene Properties dialog: a Scene's UI, Actions and Event tabs, built from the Scene's own XML."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_sceneprops: the Scene Properties dialog and everything it draws.                       #
#                                                                                        #
# Moved out of guiwins for the reason guiwins_editor gives: guiwins imports the Legacy Scene      #
# designer, and the designer opens this dialog -- so it could only reach it from inside a         #
# function.  Nothing here imports guiwins.                                                        #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import sceneedit, sceneedit_legacy, sceneview, taskedit
from maptasker.src.guiwins_canvas import FIELD_COMMIT_DEBOUNCE_MS
from maptasker.src.guiwins_legacyarg import _render_legacy_arg
from maptasker.src.guiwins_taskedit import (
    _build_task_action_editor,
    _build_tasker_icon_picker_dialog,
    _render_addability_reason,
)
from maptasker.src.maputil2 import translate_string

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState
    from maptasker.src.userintr import MyGui


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
# designer's own _render_legacy_arg (guiwins_legacyarg).
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
