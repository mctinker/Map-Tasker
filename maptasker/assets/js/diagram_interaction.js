
    return (() => {
        const container = document.getElementById(__CONTAINER_ID__);
        if (!container) return false;
        const model = __MODEL__;
        const cls = model.classes;
        const statusId = __STATUS_ID__;

        // Re-entered whenever the Diagram is re-streamed into the same view (the "Profiles
        // Per Line" pulldown does exactly that), so the old index and the old state have to
        // go: they describe elements that are no longer in the document.
        const registry = (window.mtDiagrams = window.mtDiagrams || {});
        const state = {
            lines: null,
            nodes: null,
            hidden: new Set(),
            folded: new Set(),
            filter: null,
            chain: null,
            marked: [],
            adjacency: null,
            zoom: 1,
        };

        // The Diagram can be re-streamed into this same container (the "Profiles Per Line"
        // pulldown does exactly that), and the container survives it while everything in it
        // is replaced.  So anything left on the container itself by the previous run has to
        // go, or a diagram rebuilt mid-chain comes back greyed with no chain in it.
        container.classList.remove(cls.chaining);
        container.style.fontSize = "";
        document.querySelectorAll(".mt-dmenu").forEach((el) => el.remove());

        const regionByAnchor = {};
        model.regions.forEach((region) => { regionByAnchor[region.anchor] = region; });
        // By anchor, every drawing of it -- an object the Diagram drew more than once has
        // more than one, and a chain running through it has to light all of them.
        const nodesByAnchor = {};
        model.nodes.forEach((node) => {
            (nodesByAnchor[node.anchor] = nodesByAnchor[node.anchor] || []).push(node);
        });

        // ------------------------------------------------------------------
        // Indexes, built on first use.
        // ------------------------------------------------------------------
        function lineIndex() {
            if (!state.lines) {
                state.lines = [];
                container.querySelectorAll("." + cls.line).forEach((el) => {
                    state.lines[parseInt(el.dataset.line, 10)] = el;
                });
            }
            return state.lines;
        }

        // The rendered elements for each anchor, in document order.  A list for the same
        // reason nodesByAnchor is one: the first drawing is where a jump lands, and all of
        // them are what a chain lights up.
        function nodeIndex() {
            if (!state.nodes) {
                state.nodes = {};
                container.querySelectorAll("." + cls.node).forEach((el) => {
                    (state.nodes[el.dataset.anchor] = state.nodes[el.dataset.anchor] || []).push(el);
                });
            }
            return state.nodes;
        }

        // Which calls run into and out of each Task, as indexes into model.edges.  Built
        // once: a chain walk asks this of every Task it reaches, and rescanning the edge
        // list for each would make a long chain quadratic.
        function adjacency() {
            if (!state.adjacency) {
                const out = {}, into = {};
                model.edges.forEach((edge, index) => {
                    (out[edge.caller] = out[edge.caller] || []).push(index);
                    (into[edge.called] = into[edge.called] || []).push(index);
                });
                state.adjacency = { out: out, into: into };
            }
            return state.adjacency;
        }

        // ------------------------------------------------------------------
        // What is on screen.
        // ------------------------------------------------------------------
        function computeHidden() {
            const lines = lineIndex();
            const hidden = new Set();
            const focus = state.filter ? regionByAnchor[state.filter] : null;
            if (focus) {
                for (let i = 0; i < focus.start; i++) hidden.add(i);
                for (let i = focus.end + 1; i < lines.length; i++) hidden.add(i);
            }
            state.folded.forEach((anchor) => {
                const region = regionByAnchor[anchor];
                if (!region) return;
                // From under the Project's own box: the box stays on screen, still naming
                // the Project and still carrying the arrow that unfolds it.
                for (let i = region.fold; i <= region.end; i++) hidden.add(i);
            });
            return hidden;
        }

        function applyVisibility() {
            const lines = lineIndex();
            const next = computeHidden();
            state.hidden.forEach((n) => {
                if (!next.has(n) && lines[n]) lines[n].classList.remove(cls.hidden);
            });
            next.forEach((n) => {
                if (!state.hidden.has(n) && lines[n]) lines[n].classList.add(cls.hidden);
            });
            state.hidden = next;
            model.regions.forEach((region) => {
                const el = lines[region.line];
                if (el) el.dataset.foldState = state.folded.has(region.anchor) ? "closed" : "open";
            });
            report();
        }

        function report() {
            const el = statusId ? document.getElementById(statusId) : null;
            if (!el) return;
            const parts = [];
            if (state.zoom !== 1) parts.push(Math.round(state.zoom * 100) + "%");
            if (state.filter && regionByAnchor[state.filter]) {
                parts.push("only " + regionByAnchor[state.filter].name);
            }
            if (state.folded.size) parts.push(state.folded.size + " collapsed");
            if (state.chain) parts.push("chain of " + state.chain.size);
            el.textContent = parts.join("  \u00b7  ");
        }

        // ------------------------------------------------------------------
        // Following a chain of calls.
        // ------------------------------------------------------------------
        // Both directions from the Task clicked: everything it reaches through its calls,
        // and everything that reaches it.  That is what "this Task's chain" means to
        // someone looking at a diagram -- the run of Tasks this one takes part in, not just
        // the ones downstream of it.
        function chainFrom(anchor) {
            const links = adjacency();
            const nodes = new Set([anchor]);
            const groups = new Set();
            const queue = [anchor];
            while (queue.length) {
                const at = queue.pop();
                (links.out[at] || []).forEach((index) => {
                    const edge = model.edges[index];
                    edge.groups.forEach((group) => groups.add(group));
                    if (!nodes.has(edge.called)) { nodes.add(edge.called); queue.push(edge.called); }
                });
                (links.into[at] || []).forEach((index) => {
                    const edge = model.edges[index];
                    edge.groups.forEach((group) => groups.add(group));
                    if (!nodes.has(edge.caller)) { nodes.add(edge.caller); queue.push(edge.caller); }
                });
            }
            return { nodes: nodes, groups: groups };
        }

        function clearChain() {
            state.marked.forEach((entry) => entry.el.classList.remove(entry.name));
            state.marked = [];
            state.chain = null;
            container.classList.remove(cls.chaining);
            report();
        }

        function mark(el, name) {
            if (!el) return;
            el.classList.add(name);
            state.marked.push({ el: el, name: name });
        }

        function showChain(anchor) {
            clearChain();
            // A selection made before this gesture is left over from something else, and a
            // blue block across the diagram is the one thing that reads like a highlight
            // when a highlight is exactly what this is about to draw.  (The gesture's own
            // selection never happens -- see onMouseDown.)
            const selection = window.getSelection();
            if (selection && !selection.isCollapsed) selection.removeAllRanges();
            const found = chainFrom(anchor);
            // A Task nothing calls and that calls nothing is not a chain; saying so is more
            // use than lighting up one name and dimming the whole diagram behind it.
            if (found.nodes.size < 2) {
                state.chain = null;
                flash("Nothing calls this Task, and it calls nothing.");
                return;
            }
            const lines = lineIndex();
            const nodes = nodeIndex();
            state.chain = found.nodes;
            found.nodes.forEach((each) => {
                (nodes[each] || []).forEach((el) => mark(el, cls.chain));
                (nodesByAnchor[each] || []).forEach((node) => mark(lines[node.line], cls.chainLine));
            });
            // The arrows themselves, and only they.  Marking every LINE one of them crosses
            // as part of the chain was the first attempt, and on a real diagram it exempts
            // most of the page: a connector between two distant Tasks passes through
            // everything in between, none of which is in the chain.  A line is in the chain
            // when a Task in the chain is drawn on it; a connector is in the chain on its
            // own account, and stays lit because it carries its own colour (see the CSS).
            found.groups.forEach((group) => {
                container.querySelectorAll('.connector[data-connector-id="' + group + '"]').forEach((el) => {
                    mark(el, cls.chainConnector);
                });
            });
            container.classList.add(cls.chaining);
            report();
            const first = (nodes[anchor] || [])[0];
            if (first) reveal(first);
        }

        // ------------------------------------------------------------------
        // Getting somewhere.
        // ------------------------------------------------------------------
        function reveal(element) {
            const line = element.closest ? element.closest("." + cls.line) : null;
            if (line) {
                const number = parseInt(line.dataset.line, 10);
                // Whatever is hiding it gives way -- the fold it is inside, and the filter
                // if it is outside that.  Asked for by mapjump's mtRevealAncestors as well
                // as used here, so a Find result lands on its line rather than on nothing.
                if (state.filter) {
                    const focus = regionByAnchor[state.filter];
                    if (!focus || number < focus.start || number > focus.end) state.filter = null;
                }
                state.folded.forEach((anchor) => {
                    const region = regionByAnchor[anchor];
                    if (region && number >= region.fold && number <= region.end) state.folded.delete(anchor);
                });
                applyVisibility();
            }
            for (let box = element; box; box = box.parentElement) {
                if (getComputedStyle(box).contentVisibility === "auto") box.style.contentVisibility = "visible";
            }
            element.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
            for (let box = element.parentElement; box; box = box.parentElement) {
                if (box.scrollWidth > box.clientWidth) box.scrollLeft = 0;
            }
        }

        function flash(message) {
            const el = statusId ? document.getElementById(statusId) : null;
            if (!el) return;
            const held = el.textContent;
            el.textContent = message;
            setTimeout(() => { if (el.textContent === message) el.textContent = held; }, 2500);
        }

        // ------------------------------------------------------------------
        // Zoom.
        // ------------------------------------------------------------------
        // The diagram is monospaced text, so this really is a font size and not a transform:
        // scaling the glyphs keeps every column exactly as wide as every other, which a
        // CSS transform would too but at the cost of blurring the box-drawing characters
        // the whole diagram is made of.
        function setZoom(zoom) {
            state.zoom = Math.min(3, Math.max(0.4, Math.round(zoom * 20) / 20));
            container.style.fontSize = (14 * state.zoom).toFixed(2) + "px";
            // The reserved height of a chunk that has not been laid out yet, which was
            // worked out in Python against the unzoomed line height (see process_data).
            container.querySelectorAll("[data-lines]").forEach((chunk) => {
                const rows = parseInt(chunk.dataset.lines, 10);
                chunk.style.containIntrinsicSize = "auto " + Math.round(rows * 17 * state.zoom) + "px";
            });
            report();
        }

        // ------------------------------------------------------------------
        // The menu of everything a node can do.
        // ------------------------------------------------------------------
        // Appended to the body rather than into the diagram: the scroll area sets
        // "contain: strict", which would clip a positioned element inside it to the scroll
        // box -- the same reason the connector jump buttons live there (see guiwins).
        function closeMenu() {
            document.querySelectorAll(".mt-dmenu").forEach((el) => el.remove());
        }

        function openMenu(node, x, y) {
            closeMenu();
            const menu = document.createElement("div");
            menu.className = "mt-dmenu";
            const region = node.kind === "project" ? regionByAnchor[node.anchor] : null;
            const owning = model.regions.find((each) => each.name === node.project);
            const items = [["Go to Map entry", () => jump(node)]];
            if (node.kind === "task") items.push(["Highlight call chain", () => showChain(node.anchor)]);
            if (region) {
                items.push([
                    state.folded.has(region.anchor) ? "Expand this Project" : "Collapse this Project",
                    () => toggleFold(region.anchor),
                ]);
            }
            if (owning) {
                items.push([
                    state.filter === owning.anchor ? "Stop filtering" : "Show only " + owning.name,
                    () => { state.filter = state.filter === owning.anchor ? null : owning.anchor; applyVisibility(); },
                ]);
            }
            items.push(["Reset the view", () => command("reset")]);
            items.forEach(([label, action]) => {
                const item = document.createElement("button");
                item.className = "mt-dmenu-item";
                item.textContent = label;
                item.addEventListener("click", (event) => { event.stopPropagation(); closeMenu(); action(); });
                menu.appendChild(item);
            });
            const title = document.createElement("div");
            title.className = "mt-dmenu-title";
            title.textContent = node.name || node.kind;
            menu.insertBefore(title, menu.firstChild);
            document.body.appendChild(menu);
            // Nudged back inside the window when it would otherwise open off the edge.
            const box = menu.getBoundingClientRect();
            menu.style.left = Math.max(4, Math.min(x, window.innerWidth - box.width - 8)) + "px";
            menu.style.top = Math.max(4, Math.min(y, window.innerHeight - box.height - 8)) + "px";
        }

        // The Map window, raised from inside the click that asked for it.  What it does,
        // and why raising it cannot be left to the Python side that answers the click, is
        // in mapjump.raise_map_window_js -- which a report finding's click and a Find
        // result's click run too, so all three behave alike.
        function raiseMapWindow() {
            return __RAISE_MAP_WINDOW__;
        }

        function jump(node) {
            raiseMapWindow();
            if (typeof emitEvent === "function") emitEvent("mt_jump", { target: node.token });
        }

        function toggleFold(anchor) {
            if (state.folded.has(anchor)) state.folded.delete(anchor); else state.folded.add(anchor);
            applyVisibility();
        }

        // ------------------------------------------------------------------
        // What a click means.
        // ------------------------------------------------------------------
        function nodeOf(element) {
            const span = element.closest ? element.closest("." + cls.node) : null;
            if (!span) return null;
            // THIS drawing, by its number, rather than any drawing of the same object: the
            // Project a drawing sits in is what decides the Map a click can be answered by,
            // and the same Task can be drawn under more than one.
            const node = model.nodes[parseInt(span.dataset.node, 10)];
            return node || (nodesByAnchor[span.dataset.anchor] || [])[0] || null;
        }

        function onClick(event) {
            closeMenu();
            const node = nodeOf(event.target);
            if (node) {
                event.preventDefault();
                // Shift for the chain, plain for the Map.  The chain is the answer to
                // "what runs with this", which is a question about the diagram, so it
                // stays inside it; the plain click leaves for the Map, which is the
                // heavier thing to do and so is the one you have to mean.
                if (event.shiftKey && node.kind === "task") showChain(node.anchor);
                else jump(node);
                return;
            }
            // A click on a Project's top border folds it -- the border carries the fold
            // arrow in the margin, and there is nothing else on that line to hit.
            const line = event.target.closest ? event.target.closest("." + cls.line) : null;
            if (line && line.dataset.fold && !event.target.closest(".connector")) {
                toggleFold(line.dataset.fold);
            }
        }

        function onMouseDown(event) {
            // Shift-click is the browser's own "extend the selection to here" gesture, and it
            // makes that selection on MOUSEDOWN -- so by the time the click arrives and is
            // read as "show me this chain", the diagram is already painted blue from
            // wherever the caret happened to be down to the name just clicked, competing
            // with the green the chain is about to be drawn in.
            //
            // Taken over only for a name, and only with shift held.  Selecting and copying
            // text anywhere else in the diagram is left exactly as it was; a diagram is
            // still text, and people copy it.
            if (event.shiftKey && event.target.closest && event.target.closest("." + cls.node)) {
                event.preventDefault();
            }
        }

        function onContextMenu(event) {
            const node = nodeOf(event.target);
            if (!node) return;
            event.preventDefault();
            openMenu(node, event.clientX, event.clientY);
        }

        function onWheel(event) {
            if (!event.ctrlKey && !event.metaKey) return;
            event.preventDefault();
            setZoom(state.zoom * (event.deltaY < 0 ? 1.1 : 1 / 1.1));
        }

        // The listeners are installed once and never replaced, but this script runs again
        // every time the Diagram is re-streamed into the same view -- so they must not close
        // over the state of the run that installed them, which by then describes elements
        // that have been thrown away.  Each one goes through the registry to reach whichever
        // run is current.  (Re-adding them instead would be worse: removeEventListener needs
        // the very function object that was added, and that is exactly what is lost.)
        function current() {
            return registry[__CONTAINER_ID__];
        }

        if (!container.dataset.mtDiagramWired) {
            container.dataset.mtDiagramWired = "1";
            container.addEventListener("mousedown", (event) => current().onMouseDown(event));
            container.addEventListener("click", (event) => current().onClick(event));
            container.addEventListener("contextmenu", (event) => current().onContextMenu(event));
            container.addEventListener("wheel", (event) => current().onWheel(event), { passive: false });
            document.addEventListener("click", closeMenu);
            document.addEventListener("keydown", (event) => {
                if (event.key !== "Escape") return;
                closeMenu();
                const view = current();
                if (view) view.clearChain();
            });
        }

        // ------------------------------------------------------------------
        // What the toolbar asks for.
        // ------------------------------------------------------------------
        function command(name, argument) {
            if (name === "collapse-all") { model.regions.forEach((r) => state.folded.add(r.anchor)); applyVisibility(); }
            else if (name === "expand-all") { state.folded.clear(); applyVisibility(); }
            else if (name === "zoom") setZoom(state.zoom * argument);
            else if (name === "zoom-reset") setZoom(1);
            else if (name === "reset") {
                state.folded.clear();
                state.filter = null;
                clearChain();
                setZoom(1);
                applyVisibility();
            }
            return true;
        }

        const api = {
            command: command,
            reveal: reveal,
            clearChain: clearChain,
            onMouseDown: onMouseDown,
            onClick: onClick,
            onContextMenu: onContextMenu,
            onWheel: onWheel,
            state: state,
        };
        registry[__CONTAINER_ID__] = api;
        // How mapjump's mtRevealAncestors opens a folded line back up before scrolling to
        // it.  One hook for however many Diagram views are open: each finds its own by the
        // container the element it was handed sits in.
        window.mtDiagramReveal = (element) => {
            Object.keys(registry).forEach((id) => {
                const box = document.getElementById(id);
                if (box && box.contains(element)) registry[id].reveal(element);
            });
        };
        report();
        return true;
    })();
