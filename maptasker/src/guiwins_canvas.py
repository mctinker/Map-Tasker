"""The Scene canvas: the JavaScript both designers and the read-only Preview draw through.

Split out of guiwins.py, which had grown to 14,500 lines.  This is the layer underneath
guiwins_designer_legacy and guiwins_designer_v2 rather than a dialog family of its own:
every function here emits a script that scales, selects, drags or nudges a canvas, and it
is shared by the Legacy designer, the Version 2 designer and NiceGuiSceneView's Preview.

It imports nothing from guiwins or from either designer, deliberately -- it is the leaf of
the Scene half of the GUI, so the two designers can be separate modules without either one
having to reach through the other for the plumbing they both stand on.
"""

from __future__ import annotations

import itertools
import json
import weakref
from typing import TYPE_CHECKING

from nicegui import context, ui

from maptasker.src import sceneview

if TYPE_CHECKING:
    from collections.abc import Callable


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


def _call_canvas(name: str, *args: object) -> None:
    """Run one of the canvas functions in maptasker/assets/js/scene_canvas.js.

    The script itself is linked once per page (webassets.head_html), so what goes over the
    websocket on each render is this one short call rather than the whole script.  Arguments
    are JSON-encoded, which quotes strings and turns None into null.
    """
    ui.run_javascript(f"mtCanvas.{name}({', '.join(json.dumps(arg) for arg in args)});")


def _emit_canvas_fit(root: str, width: int, height: int, fixed: float | None = None, budget: int = 0) -> None:
    """Scale the canvas under `root` to fit its wrapper, and keep it fitting on resize.

    `fixed` is a scale factor, or None for fit-to-width.  `budget` is a
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
    _call_canvas("fit", root, width, height, fixed, budget)


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
    children (one sample V2 Scene's header is an ellipse wider than anything inside it).  But a
    container that fills the screen has to be skipped even when it paints, because a
    container is stretched by its parent rather than sized by its contents -- that Scene's root
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
    _call_canvas(
        "hull", root, width, height, sceneview.V2_HULL_PADDING, sceneview.V2_COMPONENT_CLASS, sceneview.V2_HULL_CLASS
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
    _call_canvas("editing", root, max(1, snap))


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
    _call_canvas("v2Drag", root, container, node_class, select_on_click)


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

    Called from guiwins.initialize_screen, while the layout is still being built -- not left to the
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
