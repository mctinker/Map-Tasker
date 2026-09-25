/*
 * The Scene canvas: what both Scene designers and the read-only Preview draw through.
 *
 * Linked from every page's <head> by webassets.head_html(), and called from Python by
 * guiwins_canvas, one short `mtCanvas.<name>(...)` call per render.  The docstrings of the
 * Python functions that make those calls explain *why* each of these works the way it does;
 * the comments here are about the how.
 *
 * `emitEvent` is NiceGUI's own page global, looked up when a handler fires rather than when
 * this file loads.
 */
(() => {
    'use strict';

    // Scale the canvas under `root` to fit its wrapper, and keep it fitting on resize.
    // `fixed` is a scale factor, or null for fit-to-width; `budget` is a height in pixels the
    // canvas must also fit inside, or 0 for none.  See guiwins_canvas._emit_canvas_fit.
    const fit = (root, canvasWidth, canvasHeight, fixed, budget) => {
        const styleId = 'mt-scene-fit-' + root;
        let sheet = document.getElementById(styleId);
        if (!sheet) {
            sheet = document.createElement('style');
            sheet.id = styleId;
            document.head.appendChild(sheet);
        }
        const apply = () => {
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
                '.' + root + ' .mt-scene-canvas { transform: scale(' + scale + '); }' +
                '.' + root + ' { height: ' + (canvasHeight * scale + 8) + 'px;' +
                ' flex: none;' +
                ' overflow-x: ' + (canvasWidth * scale > wrap.clientWidth ? 'auto' : 'hidden') + '; }';
            wrap.dataset.scale = scale;
        };
        window.__mtSceneFit = window.__mtSceneFit || {};
        if (window.__mtSceneFit[root]) window.removeEventListener('resize', window.__mtSceneFit[root]);
        window.__mtSceneFit[root] = apply;
        window.addEventListener('resize', apply);
        apply();
        requestAnimationFrame(apply);
    };

    // Size the box behind a Version 2 layout to everything that layout occupies on screen.
    // See guiwins_canvas._emit_v2_hull.
    const hull = (root, canvasWidth, canvasHeight, pad, componentClass, hullClass) => {
        const compSel = '.' + componentClass;
        const wrap = document.querySelector('.' + root);
        const canvas = wrap && wrap.querySelector('.mt-scene-canvas');
        const box = canvas && canvas.querySelector('.' + hullClass);
        if (!box) return;

        // Does this component put anything on the screen itself, beyond its children?
        const paints = (el) => {
            const style = getComputedStyle(el);
            if (style.backgroundImage !== 'none' || style.boxShadow !== 'none') return true;
            if (parseFloat(style.borderTopWidth) || parseFloat(style.borderRightWidth)
                || parseFloat(style.borderBottomWidth) || parseFloat(style.borderLeftWidth)) return true;
            // "rgb(...)" is opaque; "rgba(..., 0)" is the transparent default.
            const parts = (style.backgroundColor.match(/[\d.]+/g) || []).map(Number);
            return parts.length === 3 || (parts.length > 3 && parts[3] > 0.01);
        };

        const measure = () => {
            const origin = canvas.getBoundingClientRect();
            // Screen pixels back to canvas pixels: the canvas is drawn at its true size
            // and scaled as a whole by fit(), which leaves the factor here.
            const scale = parseFloat(wrap.dataset.scale || '1') || 1;
            // A box within a pixel of the screen in both directions is the screen: this
            // component was stretched to what it was given, wherever the elements are.
            const fillsScreen = (rect) => rect.width / scale >= canvasWidth - 1
                                       && rect.height / scale >= canvasHeight - 1;
            let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
            for (const el of canvas.querySelectorAll(compSel)) {
                const rect = el.getBoundingClientRect();
                if (el.querySelector(compSel) && (!paints(el) || fillsScreen(rect))) continue;
                if (!rect.width && !rect.height) continue;
                left = Math.min(left, rect.left); top = Math.min(top, rect.top);
                right = Math.max(right, rect.right); bottom = Math.max(bottom, rect.bottom);
            }
            if (!isFinite(left)) { box.style.display = 'none'; return; }
            const x = Math.max(0, (left - origin.left) / scale - pad);
            const y = Math.max(0, (top - origin.top) / scale - pad);
            const w = Math.min(canvasWidth, (right - origin.left) / scale + pad) - x;
            const h = Math.min(canvasHeight, (bottom - origin.top) / scale + pad) - y;
            if (w <= 0 || h <= 0) { box.style.display = 'none'; return; }
            box.style.left = x + 'px';
            box.style.top = y + 'px';
            box.style.width = w + 'px';
            box.style.height = h + 'px';
            box.style.display = 'block';
        };

        measure();
        requestAnimationFrame(measure);
        setTimeout(measure, 300);
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
    };

    // Install the pointer and keyboard handlers that make a Legacy canvas draggable.
    // See guiwins_canvas._emit_canvas_editing.
    const editing = (root, snap) => {
        const wrap = document.querySelector('.' + root);
        const canvas = wrap && wrap.querySelector('.mt-scene-canvas');
        if (!canvas) return;
        const scale = () => parseFloat(wrap.dataset.scale || '1') || 1;
        const round = (value) => Math.round(value / snap) * snap;
        let drag = null;

        // What is selected right now, straight off the canvas -- see the docstring.
        const selected = () => (canvas.dataset.selected || '').split(' ').filter(Boolean);
        const box = (sr) => {
            const node = canvas.querySelector('.mt-el[data-sr="' + sr + '"]');
            return node && {
                sr,
                x: parseFloat(node.dataset.x), y: parseFloat(node.dataset.y),
                w: parseFloat(node.dataset.w), h: parseFloat(node.dataset.h),
            };
        };

        const place = (next) => {
            const target = canvas.querySelector('.mt-el[data-sr="' + next.sr + '"]');
            const overlay = canvas.querySelector('.mt-selection[data-sr="' + next.sr + '"]');
            for (const node of [target, overlay]) {
                if (!node) continue;
                node.style.left = next.x + 'px';
                node.style.top = next.y + 'px';
                node.style.width = next.w + 'px';
                node.style.height = next.h + 'px';
            }
        };

        // ---- the rubber band ----
        //
        // Where the pointer is in the Scene's own coordinates.  The canvas is scaled by
        // one CSS transform with transform-origin: top left, so its client rect's corner
        // *is* canvas 0,0 and dividing by the scale is the whole conversion.
        let band = null;
        const point = (event) => {
            const rect = canvas.getBoundingClientRect();
            return { x: (event.clientX - rect.left) / scale(), y: (event.clientY - rect.top) / scale() };
        };
        const spanned = (from, to) => ({
            x: Math.min(from.x, to.x), y: Math.min(from.y, to.y),
            w: Math.abs(to.x - from.x), h: Math.abs(to.y - from.y),
        });

        // WHOLLY INSIDE THE BAND, not merely touched by it -- and that is a fact about
        // Legacy Scenes rather than a preference.  Most real ones are built on a
        // full-canvas RectElement as a background (it is why paint_order exists), and
        // under a touch rule every band anywhere would catch it, so every marquee would
        // quietly pick up the background and drag it along with whatever was wanted.
        // Requiring containment makes that element reachable only by a band drawn round
        // the whole canvas -- which reads as "select everything", and is.
        const enclosed = (area) => [...canvas.querySelectorAll('.mt-el')].filter((node) => {
            const x = parseFloat(node.dataset.x), y = parseFloat(node.dataset.y);
            const w = parseFloat(node.dataset.w), h = parseFloat(node.dataset.h);
            return x >= area.x && y >= area.y
                && x + w <= area.x + area.w && y + h <= area.y + area.h;
        }).map((node) => node.dataset.sr);

        const drawBand = (area) => {
            if (!band) {
                band = document.createElement('div');
                band.className = 'mt-marquee';
                band.style.cssText = 'position: absolute; z-index: 11; pointer-events: none;'
                    + 'box-sizing: border-box; border: 1px dashed rgba(37,99,235,0.95);'
                    + 'background: rgba(37,99,235,0.10);';
                canvas.appendChild(band);
            }
            band.style.left = area.x + 'px';
            band.style.top = area.y + 'px';
            band.style.width = area.w + 'px';
            band.style.height = area.h + 'px';
        };

        canvas.addEventListener('pointerdown', (event) => {
            const handle = event.target.closest('.mt-handle');
            const picked = selected();
            const element = handle ? canvas.querySelector('.mt-el[data-sr="' + picked[picked.length - 1] + '"]')
                                   : event.target.closest('.mt-el');
            event.preventDefault();
            canvas.focus();
            if (!element) {
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
                drag = {
                    sr: '', extend: event.shiftKey || event.ctrlKey || event.metaKey,
                    dir: 'move', box: null, boxes: [], moved: false,
                    startX: event.clientX, startY: event.clientY, from: point(event),
                };
                canvas.setPointerCapture(event.pointerId);
                return;
            }
            // Grabbing anything inside the selection drags the whole selection; grabbing
            // anything else drags just that one, and drops the old selection with it.
            // The same rule the Version 2 surface uses (see v2Drag), so a drag never
            // quietly moves something the user cannot see is picked out.  A handle is
            // always the single selected element: handles are drawn only for one.
            const group = (!handle && picked.includes(element.dataset.sr))
                ? picked : [element.dataset.sr];
            drag = {
                sr: element.dataset.sr,
                extend: event.shiftKey || event.ctrlKey || event.metaKey,
                dir: handle ? handle.dataset.dir : 'move',
                startX: event.clientX,
                startY: event.clientY,
                box: box(element.dataset.sr),
                boxes: group.map(box).filter(Boolean),
                moved: false,
            };
            canvas.setPointerCapture(event.pointerId);
        });

        canvas.addEventListener('pointermove', (event) => {
            if (!drag) return;
            if (!drag.box) {
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
            }
            const dx = (event.clientX - drag.startX) / scale();
            const dy = (event.clientY - drag.startY) / scale();
            if (!drag.moved && Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
            drag.moved = true;
            const start = drag.box;
            if (drag.dir === 'move') {
                // THE SNAP IS APPLIED TO THE DELTA, ONCE, not to each element in turn.
                // Rounding every element's own position to the grid would pull a group
                // that was laid out 3px apart onto 5px boundaries -- destroying the very
                // spacing the user selected them together to preserve.  Snapping the
                // element under the pointer and moving the rest by that same offset keeps
                // the group rigid and still lands the grabbed one on the grid.
                const ox = round(start.x + dx) - start.x;
                const oy = round(start.y + dy) - start.y;
                drag.next = drag.boxes.map((b) => ({ sr: b.sr, x: b.x + ox, y: b.y + oy, w: b.w, h: b.h }));
            } else {
                let { x, y, w, h } = start;
                if (drag.dir.includes('w')) { x = round(start.x + dx); w = start.w + (start.x - x); }
                if (drag.dir.includes('n')) { y = round(start.y + dy); h = start.h + (start.y - y); }
                if (drag.dir.includes('e')) { w = round(start.w + dx); }
                if (drag.dir.includes('s')) { h = round(start.h + dy); }
                // An element may sit off the canvas -- Tasker allows it -- so nothing is
                // clamped to the edges; only a collapse to nothing is refused.
                drag.next = [{ sr: start.sr, x, y, w: Math.max(1, w), h: Math.max(1, h) }];
            }
            drag.next.forEach(place);
        });

        const finish = (event) => {
            if (!drag) return;
            const finished = drag;
            drag = null;
            if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
            // Taken away before anything is reported: reporting re-renders the canvas
            // from Python, and a band left behind would be a stray div inside the very
            // element being replaced.
            if (band) { band.remove(); band = null; }
            if (finished.band) {
                emitEvent('mt_scene_select', { root, srs: enclosed(finished.band), extend: finished.extend });
            } else if (finished.moved && finished.next) {
                emitEvent('mt_scene_geometry', { root, moves: finished.next });
            } else {
                emitEvent('mt_scene_select', { root, sr: finished.sr, extend: finished.extend });
            }
        };
        canvas.addEventListener('pointerup', finish);
        canvas.addEventListener('pointercancel', finish);

        // Give the canvas the focus back, because every edit rebuilds it and the
        // replacement starts unfocused -- so without this the arrow keys would work
        // exactly once, until the first nudge re-rendered the element being nudged.
        //
        // Not while the user is typing: an edit in the Inspector re-renders too, and
        // stealing the focus there would eject them from the field after one keystroke.
        const active = document.activeElement;
        if (!active || !active.closest || !active.closest('input, textarea, select, [contenteditable]')) {
            canvas.focus({ preventScroll: true });
        }

        canvas.addEventListener('keydown', (event) => {
            if (event.target.closest('input, textarea, select')) return;
            const step = event.shiftKey ? 10 : 1;
            const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0],
                            ArrowUp: [0, -step], ArrowDown: [0, step] };
            const move = moves[event.key];
            if (!move) return;
            event.preventDefault();
            emitEvent('mt_scene_nudge', { root, dx: move[0], dy: move[1] });
        });
    };

    // Install the pointer handlers that let a run of Version 2 components be dragged into a
    // new position among its siblings.  See guiwins_canvas._emit_v2_dragging.
    const v2Drag = (root, container, nodeClass, plainSelect) => {
        const nodeSel = '.' + nodeClass;
        const host = document.querySelector(container);
        if (!host) return;
        if (host.dataset.mtV2Drag === '1') return;
        host.dataset.mtV2Drag = '1';

        let drag = null, line = null;

        const clearLine = () => { if (line) { line.remove(); line = null; } };

        // Everything drawn for one component: its own element and everything inside it.
        const extent = (path) => {
            let box = null;
            for (const el of host.querySelectorAll(nodeSel + '[data-path]')) {
                const p = el.dataset.path;
                if (p !== path && !p.startsWith(path + '|')) continue;
                const r = el.getBoundingClientRect();
                if (!r.width && !r.height) continue;
                box = box ? { top: Math.min(box.top, r.top), left: Math.min(box.left, r.left),
                              bottom: Math.max(box.bottom, r.bottom), right: Math.max(box.right, r.right) }
                          : { top: r.top, left: r.left, bottom: r.bottom, right: r.right };
            }
            return box;
        };

        // The dragged run's siblings, by index, with where each of them is on screen.
        const siblings = (path, total) => {
            const base = path.slice(0, path.lastIndexOf('|'));
            const found = [];
            for (let i = 0; i < total; i++) {
                const box = extent(base + '|' + i);
                if (box) found.push({ index: i, box });
            }
            return found;
        };

        // Down the page or across it?  Read off where the siblings actually are rather
        // than from the container's flex-direction, so a Box, a grid or a wrapped row
        // answers for itself and the tree (always a stack of rows) needs no special case.
        const isVertical = (sibs) => {
            let dx = 0, dy = 0;
            for (const a of sibs) for (const b of sibs) {
                dx = Math.max(dx, Math.abs((a.box.left + a.box.right) / 2 - (b.box.left + b.box.right) / 2));
                dy = Math.max(dy, Math.abs((a.box.top + a.box.bottom) / 2 - (b.box.top + b.box.bottom) / 2));
            }
            return dy >= dx;
        };

        const showLine = (sibs, vertical, target) => {
            const at = sibs.find((s) => s.index === target);
            const last = sibs[sibs.length - 1];
            const edge = at ? at.box : last.box;
            const before = !!at;
            const top = Math.min(...sibs.map((s) => s.box.top));
            const left = Math.min(...sibs.map((s) => s.box.left));
            const bottom = Math.max(...sibs.map((s) => s.box.bottom));
            const right = Math.max(...sibs.map((s) => s.box.right));
            if (!line) {
                line = document.createElement('div');
                line.style.cssText = 'position: fixed; z-index: 9999; background: #2563eb;'
                                   + 'border-radius: 2px; pointer-events: none;';
                document.body.appendChild(line);
            }
            if (vertical) {
                const y = before ? edge.top : edge.bottom;
                line.style.left = left + 'px';
                line.style.width = Math.max(8, right - left) + 'px';
                line.style.top = (y - 1) + 'px';
                line.style.height = '3px';
            } else {
                const x = before ? edge.left : edge.right;
                line.style.top = top + 'px';
                line.style.height = Math.max(8, bottom - top) + 'px';
                line.style.left = (x - 1) + 'px';
                line.style.width = '3px';
            }
        };

        host.addEventListener('pointerdown', (event) => {
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

            drag = {
                path: inRun ? sel : path, count: inRun ? selCount : 1,
                clicked: path, total, base,
                startX: event.clientX, startY: event.clientY, moved: false, target: null,
            };
            // No pointer capture yet, and not until the drag threshold is crossed: a
            // captured pointer redirects the click that follows it to the capturing
            // element, which would take every plain click away from the tree row that
            // was meant to receive it.
        });

        host.addEventListener('pointermove', (event) => {
            if (!drag) return;
            if (!drag.moved
                && Math.abs(event.clientX - drag.startX) < 4
                && Math.abs(event.clientY - drag.startY) < 4) return;
            if (!drag.moved) {
                drag.moved = true;
                // Only now, so a plain click is left exactly as it was found.
                document.body.style.userSelect = 'none';
                // Capture keeps the drag alive past the edge of the pane.  Guarded
                // because it throws for a pointer the browser no longer considers
                // active, and losing the capture is worth far less than losing the drag.
                try { host.setPointerCapture(event.pointerId); } catch (e) { /* not fatal */ }
            }
            event.preventDefault();
            const sibs = siblings(drag.path, drag.total);
            if (sibs.length < 2) return;
            const vertical = isVertical(sibs);
            const at = vertical ? event.clientY : event.clientX;
            let target = 0;
            for (const s of sibs) {
                const mid = vertical ? (s.box.top + s.box.bottom) / 2 : (s.box.left + s.box.right) / 2;
                if (at > mid) target = s.index + 1;
            }
            drag.target = target;
            showLine(sibs, vertical, target);
        });

        const finish = (event) => {
            if (!drag) return;
            const done = drag;
            drag = null;
            clearLine();
            document.body.style.userSelect = '';
            if (host.hasPointerCapture(event.pointerId)) host.releasePointerCapture(event.pointerId);
            if (done.moved && done.target !== null) {
                emitEvent('mt_v2_reorder',
                          { root, path: done.path, count: done.count, before: done.target });
            } else if (!done.moved && (plainSelect || event.shiftKey)) {
                emitEvent('mt_v2_select', { root, path: done.clicked, extend: !!event.shiftKey });
            }
        };
        host.addEventListener('pointerup', finish);
        host.addEventListener('pointercancel', finish);
    };

    window.mtCanvas = { fit, hull, editing, v2Drag };
})();
