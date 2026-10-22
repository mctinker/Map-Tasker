"""guiwins_sceneview: the Scene Preview view, and the hand-off from the Edit Scene dialog to it.

NiceGuiSceneView hosts the picture sceneview draws (toolbar, scroll area, theming, canvas editing).  The Edit Scene
dialog steps aside for a Preview and its 'Back to Editor' brings it back: suspend_scene_editor_session and
repaint_scene_previews are that hand-off."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core import scenelayout
from maptasker.src.core.maputil2 import suppress_logged, translate_string
from maptasker.src.edit import sceneedit, sceneedit_v2nodes, scenemodel
from maptasker.src.gui import sceneview, sceneview_legacy, sceneview_v2, sceneview_v2base
from maptasker.src.gui.guiwins_canvas import (
    CANVAS_PREVIEW_ROOT,
    _emit_canvas_editing,
    _emit_canvas_fit,
    _emit_v2_dragging,
    _emit_v2_hull,
    _register_canvas_events,
    register_canvas,
)
from maptasker.src.gui.guiwins_designer_legacy import _legacy_canvas_size
from maptasker.src.gui.guiwins_nav import live_views, register_view
from maptasker.src.gui.guiwins_views import view_theme_colors

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from nicegui.events import ValueChangeEventArguments

    from maptasker.src.gui.userintr import MyGui


# ==========================================
# THE SCENE EDITOR SESSION
# ==========================================
# How the Edit Scene dialog and a Scene Preview hand the screen back and forth: the dialog
# steps aside for the picture, and the picture's "Back to Editor" brings it back.
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


def _scene_dialog_closed(gui: MyGui, dialog: ui.dialog, field_refs: dict, event: ValueChangeEventArguments) -> None:
    """One place every way of closing a Scene dialog goes through.

    Hung on the dialog's own value rather than on its buttons because there are eight of
    them across the two dialogs -- Cancel, Ok, Delete, Rename, three kinds of Save, Export --
    and they close it through six different event handlers in userintr_editors.  A ninth button
    added later would be one more that forgot to repaint; the value cannot be.

    THE PREVIEW STOPS BEING AN EDITING SURFACE HERE, which is half of drawing the right
    thing rather than merely a fresh thing.  A preview is editable only while the designer
    that opened it is alive to take the edit (see NiceGuiSceneView._legacy_editing), and
    these two keys are how it finds one -- but the handlers in them outlive the dialog,
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
    # And the dialog itself goes, which is what lets its designer go with it.  Hiding it left
    # the whole page of elements in the client for good -- every Edit Scene ever opened -- and
    # the designer's canvas entry (see guiwins_canvas._ACTIVE_CANVASES) with it.  Nothing
    # comes back to a dialog closed for good: Edit Scene builds a fresh one from the Scene.
    if session and session.get("dialog") is dialog:
        gui.scene_editor_session = None
    with suppress_logged("Deleting a closed Scene dialog"):
        dialog.delete()


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
    userintr_fields.apply_scene_field_values would say about it at save time rather than inventing a
    second opinion.

    THE PICTURE IS ALSO AN EDITING SURFACE, for both kinds of Scene, whenever the designer
    that opened it is still alive: components are dragged into a new order here (V2) and
    elements are selected, moved and resized here (Legacy).  It edits nothing itself.  Every
    gesture is handed straight to that designer's own handlers -- see _v2_from_canvas and
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
        self.is_v2 = scenemodel.is_v2_scene(edited_scene.scene_element)
        self.options = sceneview.PreviewOptions()
        self.zoom = "Fit"
        self.screen = sceneview_v2base.V2_DEFAULT_SCREEN
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

    def _snap_selected(self, event: ValueChangeEventArguments) -> None:
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
                [name for name, _width, _height in sceneview_v2base.V2_SCREENS],
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

    def _zoom_selected(self, event: ValueChangeEventArguments) -> None:
        self.zoom = str(event.value or "Fit")
        self.render()

    def _density_selected(self, event: ValueChangeEventArguments) -> None:
        try:
            self.options.density = float(event.value)
        except (TypeError, ValueError):
            self.options.density = sceneview.DEFAULT_DENSITY
        self.render()

    def _screen_selected(self, event: ValueChangeEventArguments) -> None:
        self.screen = str(event.value or sceneview_v2base.V2_DEFAULT_SCREEN)
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
            sceneview_legacy.draw_scene(
                scene_element, width, height, self.options, editing=editing, state=self.master_gui.state
            )
        self._apply_scale(width, height)
        if editing is not None:
            # Kept on the view: the registry only holds the table weakly.
            self._preview_handlers = register_canvas(
                CANVAS_PREVIEW_ROOT,
                {
                    name: (lambda payload, which=name: self._legacy_from_canvas(which, payload))
                    for name in ("select", "geometry", "nudge")
                },
            )
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
            layout = scenelayout.decode_v2_layout(self.edited_scene.scene_element)
        if not isinstance(layout, dict):
            self._say(
                "This Scene's Version 2 layout could not be read, so there is nothing to draw.",
                "text-orange-600",
            )
            return

        editing = self._v2_editing()
        width, height = self._screen_size()
        with self.canvas_wrap:
            sceneview_v2.draw_v2_layout(layout, width, height, self.options, editing=editing)
        self._apply_scale(width, height)
        # After the scale, never before: the hull is measured in screen pixels and divided
        # back by the factor _apply_scale leaves on the wrapper, and a hull measured before
        # that factor existed would be sized by whatever the last render happened to set.
        _emit_v2_hull(CANVAS_PREVIEW_ROOT, width, height)
        if editing is not None:
            # Kept on the view: the registry only holds the table weakly.
            self._preview_handlers = register_canvas(
                CANVAS_PREVIEW_ROOT,
                {
                    "v2select": lambda payload: self._v2_from_canvas("v2select", payload),
                    "v2reorder": lambda payload: self._v2_from_canvas("v2reorder", payload),
                },
            )
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
        return sceneview.V2Editing(selected=sceneedit_v2nodes.v2_run_paths(selection["path"], selection["count"]))

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
        for name, width, height in sceneview_v2base.V2_SCREENS:
            if name == self.screen:
                return (height, width) if self.options.landscape else (width, height)
        _name, width, height = sceneview_v2base.V2_SCREENS[0]
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
        fixed = None
        if self.zoom != "Fit":
            try:
                fixed = int(self.zoom.rstrip("%")) / 100
            except ValueError:
                fixed = None
        _emit_canvas_fit(CANVAS_PREVIEW_ROOT, width, height, fixed)

    def _draw_legacy_caption(self, scene_element: Element, width: int, height: int) -> None:
        """Under the canvas: the Scene's own settings, the element count, and -- the part
        that matters -- what the drawing above is not able to tell the truth about.
        """
        elements = sceneview.paint_order(scene_element)
        with self.caption:
            summary = (
                f"{width} x {height} {translate_string('pixels')} · {len(elements)} {translate_string('element(s)')}"
            )
            properties = sceneview_legacy.scene_properties(scene_element)
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
                f"{sceneview_v2.v2_component_count(layout)} {translate_string('component(s)')}"
            )
            properties = sceneview_v2.v2_layout_summary(layout)
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
