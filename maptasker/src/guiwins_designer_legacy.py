"""The Legacy Scene designer: the canvas, the element list and the argument fields.

Split out of guiwins.py, which had grown to 14,500 lines.  A Legacy Scene is Tasker's older
Scene format, and it is edited as a picture -- _build_legacy_designer draws the Scene at its
true pixel size and lets elements be clicked, dragged and resized on it -- so this module is
the Add/Rename element dialogs, the nested "Edit item layout" designer, and the widgets that
render one <Arg> of an element.

It stands on guiwins_canvas for the drawing and dragging, which the Version 2 designer
stands on too.  Its two calls back into guiwins -- the Scene Properties dialog and its
one-line summary -- are made inside the function that needs them: Scene Properties renders
Legacy argument fields through _render_legacy_arg below, so the two modules genuinely refer
to each other and a module-level import would be a cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import Event, ui

from maptasker.src import sceneedit, sceneview, taskedit
from maptasker.src.guiwins_canvas import (
    _ACTIVE_CANVASES,
    _DESIGNER_SEQUENCE,
    CANVAS_DESIGNER_ROOT,
    DESIGNER_CANVAS_HEIGHT,
    FIELD_COMMIT_DEBOUNCE_MS,
    _emit_canvas_editing,
    _emit_canvas_fit,
    _register_canvas_events,
)
from maptasker.src.guiwins_taskedit import _dropdown_current_label
from maptasker.src.maputil2 import translate_string
from maptasker.src.sysconst import SCENE_TASK_TYPES

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.userintr import MyGui


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
            ui.input(placeholder=translate_string("Search elements"), on_change=lambda e: search_changed(e.value))
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
    self: MyGui,
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
    # Imported here rather than at the top of the file: guiwins imports this module, so a
    # module-level import would be a cycle.  See this module's docstring.
    from maptasker.src.guiwins import _build_scene_properties_dialog, _scene_properties_summary  # noqa: PLC0415

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
        ui.element("div")
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
                on_click=lambda _e=None, holder=element: _build_item_layout_dialog(self, holder, render),
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
        panes rather than in the element inspector.

        A SIGNPOST RATHER THAN THE FORM ITSELF.  The form moved into
        _build_scene_properties_dialog when it grew Tasker's UI/KEY tabs and the
        Property-Type gating that decides which fields even apply, and it is reached from the
        "Edit Properties" button at the top of this dialog.  Rendering it here as well would
        mean two forms over one <PropertiesElement>: edit either and the other is stale until
        something rebuilds it, which is the sort of disagreement this panel exists to avoid.
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
            else:
                ui.label(_scene_properties_summary(scene_element)).classes("text-xs text-gray-500 italic")
            ui.button(
                translate_string("Add scene properties" if properties is None else "Edit scene properties"),
                icon="add" if properties is None else "tune",
                on_click=open_scene_properties,
            ).props("dense flat")

    def open_scene_properties() -> None:
        """Open the Properties form, and rebuild this panel when it closes so the summary
        line agrees with what was just changed.
        """
        _build_scene_properties_dialog(self, edited_scene, field_refs, on_closed=render)

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


def _build_item_layout_dialog(self: MyGui, holder: object, on_closed: Callable[[], None]) -> None:
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
                    ui.input(translate_string(label), value=layout.findtext(key, sceneedit.UNSET_DIMENSION))
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

        _build_legacy_designer(self, nested, field_refs)

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
        ui.color_input(
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
