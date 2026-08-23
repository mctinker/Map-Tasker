#! /usr/bin/env python3
#                                                                                      #
# diagintr: what makes the Diagram view interactive.                                   #
#                                                                                      #

"""The Diagram as a thing you can click, rather than a picture of one.

The Diagram is drawn as text -- boxes and connectors made of box-drawing characters, laid
out in columns that only line up because every one of them was computed.  That is what
makes it readable on a large configuration, and it is also why nothing in it was ever
clickable: there are no elements in a wall of text, only characters.

Two records kept while the diagram is drawn are enough to change that without touching a
single character of what is drawn:

  diagram_anchors / diagram_object_targets   where each Project, Profile, Task and Scene
                                             was drawn, and which object it is
  diagram_call_edges / diagram_connector_calls   which two Task lines each connector joins

This module turns those into one model -- nodes, regions and edges, all in the rendered
file's own line/column coordinates -- and into the browser-side code that acts on it.  The
view then wraps the named spans in elements (guiwins._wrap_diagram_line) and everything
else is done against the model: a click resolves to a node, a fold resolves to a region, a
chain is walked over the edges.

The one rule the whole thing lives by: NOTHING here may add or remove a character of the
diagram.  Every column in it was computed against every other, so an inserted fold arrow or
a widened highlight would pull the connectors out of line with the boxes they join.  The
fold markers are drawn in the margin with position:absolute for exactly this reason, and
collapsing hides whole lines rather than reflowing anything.
"""

from __future__ import annotations

import json

from maptasker.src.mapjump import PROJECT, TASK, Target
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import POPOUT_WINDOW_PREFIX

# The class every clickable object name in the Diagram carries, and the ones the
# interactions add to it.  Styled in guiwins.inject_shared_head_styles.
NODE_CLASS = "mt-dnode"  # A clickable object name.
LINE_CLASS = "mt-dline"  # One line of the diagram, its own newline included.
CHAIN_CLASS = "mt-chain"  # A name in the call chain being followed.
CHAIN_CONNECTOR_CLASS = "mt-chain-connector"  # An arrow in that chain.
CHAIN_LINE_CLASS = "mt-chain-line"  # A line the chain runs through, exempt from dimming.
CHAINING_CLASS = "mt-chaining"  # On the container, while a chain is being followed.
HIDDEN_CLASS = "mt-hidden"  # Folded away, or filtered out.

# How wide "└─ " is -- the prefix a Task line is drawn with, and the part of a Task's
# recorded span that is drawing rather than name.  Trimmed off the clickable span so that a
# click lands on the name, and so that the span can never overlap a connector: the "─" in
# that prefix is a connector character, and an element cannot be in two spans at once.
_TASK_PREFIX = 3


# ##################################################################################
# The model, built once as the diagram is written.
# ##################################################################################
def _regions(anchors: dict, targets: dict, line_count: int, tail: int) -> list[dict]:
    """Each Project's stretch of the diagram, top border to the line before the next one.

    A Project is the only object the diagram gives a contiguous run of lines to.  Profiles
    are drawn side by side across a row and their Tasks under their own column, so a
    Profile owns a set of columns as much as a set of lines -- there is no run of lines to
    fold that would not also fold its neighbours.  That is why folding and filtering are
    offered per Project and the call chain (which is not a region at all, but a set of
    Tasks) carries the weight for everything finer.

    The spacer lines written between Projects are left to the Project above, which is what
    makes a collapsed Project take its trailing blank lines down with it rather than leave
    a gap where it used to be.
    """
    starts = sorted(
        (placement[0], anchor)
        for anchor, placement in anchors.items()
        if targets.get(anchor) is not None and targets[anchor].kind == PROJECT
    )
    regions = []
    for index, (line, anchor) in enumerate(starts):
        # The name is on the middle line of the three the box is drawn as, so the region
        # opens one line above it, on the box's top border.
        start = max(line - 1, 0)
        end = starts[index + 1][0] - 2 if index + 1 < len(starts) else line_count - 1 - tail
        regions.append(
            {
                "anchor": anchor,
                "name": targets[anchor].name,
                "line": line,
                "start": start,
                # What a fold takes away: everything under the Project's own box, which is
                # drawn as a top border, the name, and a bottom border.  The box itself stays
                # -- a Project collapsed down to a nameless rectangle would be a fold you
                # could not read, let alone find your way back out of.
                "fold": line + 2,
                "end": max(end, line + 2),
            },
        )
    return regions


def _project_at(regions: list[dict], line: int) -> str:
    """The name of the Project whose region holds this line, or "" for none.

    Linear because a configuration has Projects in the dozens, not the thousands, and this
    runs once per drawn object rather than once per line.
    """
    for region in regions:
        if region["start"] <= line <= region["end"]:
            return region["name"]
    return ""


def _char_span(line: str, column: int, length: int) -> tuple[int, int]:
    """A recorded span, in the units the renderer slices by.

    Positions are recorded in UTF-16 code units, because that is what the browser counts a
    string index in and the jump into the Diagram hands them straight to it (see
    diagram._place).  The renderer, though, slices the Python string, which counts code
    points -- and the two differ by one for every emoji in a Task name.  Converted here,
    once, rather than leaving two column systems in play in the same line of markup.
    """
    units = line.encode("utf-16-le")
    start = len(units[: column * 2].decode("utf-16-le", "ignore"))
    end = len(units[: (column + length) * 2].decode("utf-16-le", "ignore"))
    return start, end - start


def _nodes(lines: list[str], placements: list, targets: dict, regions: list[dict]) -> list[dict]:
    """Every DRAWING of every object, as a span the browser can wrap and a token to jump with.

    One per drawing and not one per object, which is the difference between "the first
    'Wear Location Menu' in this Project is clickable" and "every one of them is".  The
    Diagram draws a Task once per Profile that runs it and again under any Scene that fires
    it, and there is nothing about the second drawing that makes it less the Task than the
    first.  They share an anchor, so they share a token and a chain and a jump; what differs
    is only where each one sits.

    An object the diagram recorded but could not place on its line (see diagram._place,
    which answers (0, 0) when icon trimming rubbed out part of the name it was looking for)
    is left out rather than given the whole line: a whole-line click target would swallow
    clicks meant for the connectors and the other objects drawn on that same line.

    The owning Project is filled in from the region the object was drawn in rather than
    carried on the Target.  It is what decides which Map a click can be answered by (see
    mapjump.scope_for), and the drawing code would have to thread it through four call
    layers to get it here any other way.  Read per drawing, since a Task drawn under one
    Project can be drawn again under another.
    """
    nodes = []
    for anchor, line, column, length in placements:
        target = targets.get(anchor)
        if target is None or length <= 0 or line >= len(lines):
            continue
        column, length = _char_span(lines[line], column, length)
        if target.kind == TASK:
            # Past the "└─ " the line is drawn with -- see _TASK_PREFIX.
            if length <= _TASK_PREFIX:
                continue
            column, length = column + _TASK_PREFIX, length - _TASK_PREFIX
        if length <= 0:
            continue
        project = target.key if target.kind == PROJECT else _project_at(regions, line)
        nodes.append(
            {
                "anchor": anchor,
                "kind": target.kind,
                "name": target.name,
                "line": line,
                "col": column,
                "len": length,
                "project": project,
                "token": Target(
                    kind=target.kind,
                    key=target.key,
                    name=target.name,
                    project=project,
                ).token(),
            },
        )
    nodes.sort(key=lambda node: (node["line"], node["col"]))
    # Numbered after sorting, because the number is how the rendered element names WHICH
    # drawing it is.  The anchor alone cannot say: it is shared by every drawing of the
    # object, and the drawings can differ in the one thing a click needs -- the Project
    # they were drawn under, which decides the Map that can answer.
    for index, node in enumerate(nodes):
        node["index"] = index
    return nodes


def _task_on_row(by_row: dict, row: int, name: str) -> str:
    """The anchor of the Task drawn on this row, by name where the row holds several.

    Several Tasks share a row whenever their Profiles are drawn side by side, so the row
    alone is not always an answer.  The name settles it -- with a prefix match, since the
    caller's name as the call table read it off the line carries the "(entry)"/"(exit)"
    marker the drawn name does not.
    """
    candidates = by_row.get(row, [])
    if len(candidates) == 1:
        return candidates[0]["anchor"]
    for node in candidates:
        if node["name"] == name:
            return node["anchor"]
    for node in candidates:
        if node["name"] and name.startswith(node["name"]):
            return node["anchor"]
    return candidates[0]["anchor"] if candidates else ""


def _edges(nodes: list[dict], call_edges: dict, connector_calls: dict) -> list[dict]:
    """Every call, as the two Tasks it joins and the connectors drawn for it.

    This is the whole of the call graph the Diagram draws, in the Diagram's own terms: not
    "Task 118 calls Task 204" but "the Task on line 412 calls the Task on line 380, and
    these are the characters joining them".  Following it is what a chain highlight does.

    A call whose Tasks cannot both be identified is dropped.  It would otherwise be an edge
    into nothing, and a chain walked through it would light up an arbitrary Task.
    """
    by_row: dict = {}
    for node in nodes:
        if node["kind"] == TASK:
            by_row.setdefault(node["line"], []).append(node)

    groups_by_call: dict = {}
    for group_id, calls in connector_calls.items():
        for call_index in calls:
            groups_by_call.setdefault(call_index, []).append(group_id)

    edges = []
    for index, edge in call_edges.items():
        caller = _task_on_row(by_row, edge["caller_row"], edge.get("caller_name", ""))
        called = _task_on_row(by_row, edge["called_row"], edge.get("called_name", ""))
        if not caller or not called:
            continue
        edges.append(
            {
                "caller": caller,
                "called": called,
                "groups": sorted(groups_by_call.get(index, [])),
            },
        )
    return edges


def build_model(lines: list[str]) -> dict:
    """Assemble the interaction model from what the finished diagram recorded.

    Called at the very end of diagram.network_map, once every position is final: the
    anchors have been resolved onto the written file's lines, and the connectors have been
    grown from their seeds.  Anything earlier would be measuring a diagram that is still
    moving.
    """
    anchors = getattr(PrimeItems, "diagram_anchors", {}) or {}
    targets = getattr(PrimeItems, "diagram_object_targets", {}) or {}
    # The "diagram was cut short" message is written past the last drawn line; it belongs to
    # no Project, and folding the last one should not take it away.
    tail = 2 if getattr(PrimeItems, "diagram_limit_msg", "") else 0
    regions = _regions(anchors, targets, len(lines), tail)
    nodes = _nodes(lines, getattr(PrimeItems, "diagram_object_placements", []) or [], targets, regions)
    return {
        "nodes": nodes,
        "regions": regions,
        "edges": _edges(
            nodes,
            getattr(PrimeItems, "diagram_call_edges", {}) or {},
            getattr(PrimeItems, "diagram_connector_calls", {}) or {},
        ),
    }


# ##################################################################################
# The model, read back by the view.
# ##################################################################################
def model() -> dict:
    """The model the last-built Diagram recorded, or an empty one.

    Empty is ordinary rather than an error: a Diagram file left on disk by an older run of
    MapTasker has no model behind it, and the view then shows exactly what it always did.

    Every column in it counts code points, not the UTF-16 units diagram_anchors is recorded
    in -- this is what the renderer slices Python strings by.  The browser never measures a
    column itself: it finds a node by the element the renderer wrapped it in.
    """
    stored = getattr(PrimeItems, "diagram_model", None)
    return stored if isinstance(stored, dict) and stored.get("nodes") else {"nodes": [], "regions": [], "edges": []}


def nodes_by_line(the_model: dict) -> dict[int, list[dict]]:
    """The model's nodes grouped by the line they were drawn on, for the renderer."""
    by_line: dict[int, list[dict]] = {}
    for node in the_model.get("nodes", []):
        by_line.setdefault(node["line"], []).append(node)
    return by_line


def folds_by_line(the_model: dict) -> dict[int, str]:
    """Which lines carry a Project's fold control: {line: region anchor}.

    The Project's name line, which is the one line of the box that says which Project this
    is -- and the one still on screen when it is folded, since a fold only takes what is
    under the box (see _regions).
    """
    return {region["line"]: region["anchor"] for region in the_model.get("regions", [])}


def model_json(the_model: dict) -> str:
    """The model as the browser receives it, with the class names it acts through."""
    return json.dumps(
        {
            **the_model,
            "classes": {
                "node": NODE_CLASS,
                "line": LINE_CLASS,
                "chain": CHAIN_CLASS,
                "chainConnector": CHAIN_CONNECTOR_CLASS,
                "chainLine": CHAIN_LINE_CLASS,
                "chaining": CHAINING_CLASS,
                "hidden": HIDDEN_CLASS,
            },
        },
    )


# ##################################################################################
# The browser side.
# ##################################################################################
# One script, installed once per rendered Diagram, holding everything the view does after
# it has been drawn.  It is long because the diagram is: every interaction here has to work
# on a hundred thousand lines of text without the browser noticing, which rules out the
# obvious implementations.  The three that matter:
#
#   Folding and filtering keep an index of the line elements and touch only the range that
#   changed, rather than re-querying or re-styling the document.
#
#   Dimming for a call chain is done with one class on the container and an exemption class
#   on the handful of lines the chain runs through -- the alternative, dimming every other
#   line, is a class change per line of the diagram for every click.
#
#   Nothing is ever re-rendered.  The diagram's columns are computed against each other, so
#   a reflow would pull the connectors out of line with the boxes they join; a fold hides
#   whole lines, and the fold arrows are drawn in the margin with position:absolute so they
#   occupy no column at all.
_INTERACTION_JS = """
    return (() => {
        const container = document.getElementById(CONTAINER_ID);
        if (!container) return false;
        const model = MODEL;
        const cls = model.classes;
        const statusId = STATUS_ID;
        const MAP_WINDOW_PREFIX = MAP_PREFIX;

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
            el.textContent = parts.join("  \\u00b7  ");
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

        // The Map window, raised from inside the click that asked for it.
        //
        // This is here rather than left to the Python side because of WHEN it runs, not
        // what it does.  A browser lets a page raise another window while it has user
        // activation -- during a click -- and refuses once that has lapsed.  Answering the
        // click means a round trip to Python and back, and the script that comes back has
        // no activation at all: the Map scrolls to the object and stays behind the Diagram,
        // so the click reads as having done nothing until the user thinks to switch tabs.
        //
        // Only a window that already exists is raised.  The handles are the opener's --
        // every popout is opened by the main window, which keeps them (see
        // _open_popout_window) -- so this asks that list rather than opening anything by
        // name, which for a name nothing has claimed would conjure a blank window.  When
        // there is no Map open, nothing happens here and the rebuild that follows opens one
        // and raises it on its own.
        function raiseMapWindow() {
            try {
                const opener = window.opener;
                if (!opener || opener.closed) return;
                for (const other of opener.mapTaskerPopouts || []) {
                    if (other && !other.closed && (other.name || "").startsWith(MAP_WINDOW_PREFIX)) {
                        other.focus();
                        return;
                    }
                }
            } catch (error) {
                // A window that has gone away, or one the browser will not let us touch.
                // The jump itself is unaffected, so there is nothing to report.
            }
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
            return registry[CONTAINER_ID];
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
        registry[CONTAINER_ID] = api;
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
"""


def interaction_js(container_id: str, status_id: str, the_model: dict) -> str:
    """The script that makes one rendered Diagram interactive."""
    return (
        _INTERACTION_JS.replace("CONTAINER_ID", json.dumps(container_id))
        .replace("STATUS_ID", json.dumps(status_id))
        .replace("MAP_PREFIX", json.dumps(f"{POPOUT_WINDOW_PREFIX}map"))
        .replace("MODEL", model_json(the_model))
    )


def command_js(container_id: str, name: str, argument: float | None = None) -> str:
    """A toolbar button, as the script that carries it to the view it belongs to."""
    return (
        f"const view = (window.mtDiagrams || {{}})[{json.dumps(container_id)}];"
        f"if (view) view.command({json.dumps(name)}, {json.dumps(argument)});"
    )
