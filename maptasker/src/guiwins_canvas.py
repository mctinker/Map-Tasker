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
