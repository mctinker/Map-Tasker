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
view then wraps the named spans in elements (guiwins_diagram.wrap_diagram_line) and everything
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
from typing import TYPE_CHECKING

from maptasker.src.core import assettext, mapjump
from maptasker.src.core.mapjump import PROJECT, TASK, Target

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# The class every clickable object name in the Diagram carries, and the ones the
# interactions add to it.  Styled in guiwins_drawers.inject_shared_head_styles.
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
    diagrecord.place_in_line).  The renderer, though, slices the Python string, which counts code
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

    An object the diagram recorded but could not place on its line (see diagrecord.place_in_line,
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
        span_column, span_length = _char_span(lines[line], column, length)
        if target.kind == TASK:
            # Past the "└─ " the line is drawn with -- see _TASK_PREFIX.
            if span_length <= _TASK_PREFIX:
                continue
            span_column, span_length = span_column + _TASK_PREFIX, span_length - _TASK_PREFIX
        if span_length <= 0:
            continue
        project = target.key if target.kind == PROJECT else _project_at(regions, line)
        nodes.append(
            {
                "anchor": anchor,
                "kind": target.kind,
                "name": target.name,
                "line": line,
                "col": span_column,
                "len": span_length,
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


def build_model(lines: list[str], state: RunState) -> dict:
    """Assemble the interaction model from what the finished diagram recorded.

    Called at the very end of diagram.network_map, once every position is final: the
    anchors have been resolved onto the written file's lines, and the connectors have been
    grown from their seeds.  Anything earlier would be measuring a diagram that is still
    moving.
    """
    anchors = getattr(state, "diagram_anchors", {}) or {}
    targets = getattr(state, "diagram_object_targets", {}) or {}
    # The "diagram was cut short" message is written past the last drawn line; it belongs to
    # no Project, and folding the last one should not take it away.
    tail = 2 if getattr(state, "diagram_limit_msg", "") else 0
    regions = _regions(anchors, targets, len(lines), tail)
    nodes = _nodes(lines, getattr(state, "diagram_object_placements", []) or [], targets, regions)
    return {
        "nodes": nodes,
        "regions": regions,
        "edges": _edges(
            nodes,
            getattr(state, "diagram_call_edges", {}) or {},
            getattr(state, "diagram_connector_calls", {}) or {},
        ),
    }


# ##################################################################################
# The model, read back by the view.
# ##################################################################################
def model(state: RunState) -> dict:
    """The model the last-built Diagram recorded, or an empty one.

    Empty is ordinary rather than an error: a Diagram file left on disk by an older run of
    MapTasker has no model behind it, and the view then shows exactly what it always did.

    Every column in it counts code points, not the UTF-16 units diagram_anchors is recorded
    in -- this is what the renderer slices Python strings by.  The browser never measures a
    column itself: it finds a node by the element the renderer wrapped it in.
    """
    stored = getattr(state, "diagram_model", None)
    return stored if isinstance(stored, dict) and stored.get("nodes") else {"nodes": [], "regions": [], "edges": []}


def connector_tasks(the_model: dict) -> dict[str, list[str]]:
    """Each connector's id -> the anchors of the Tasks it joins, for the jump buttons.

    Which Task a connector's end belongs to is not something its cells say; the calls do.
    Keyed by the id as text because that is what the browser reads off the page.
    """
    found: dict[str, set[str]] = {}
    for edge in the_model.get("edges", []):
        for group in edge["groups"]:
            found.setdefault(str(group), set()).update((edge["caller"], edge["called"]))
    return {group: sorted(anchors) for group, anchors in found.items()}


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
# The script itself is assets/js/diagram_interaction.js, so that an editor sees it as the JavaScript
# it is; interaction_js fills in the four places it needs something from here.
_INTERACTION_SCRIPT = "js/diagram_interaction.js"


def interaction_js(container_id: str, status_id: str, the_model: dict) -> str:
    """The script that makes one rendered Diagram interactive."""
    return assettext.render(
        _INTERACTION_SCRIPT,
        CONTAINER_ID=json.dumps(container_id),
        STATUS_ID=json.dumps(status_id),
        RAISE_MAP_WINDOW=mapjump.raise_map_window_js().strip(),
        MODEL=model_json(the_model),
    )


def command_js(container_id: str, name: str, argument: float | None = None) -> str:
    """A toolbar button, as the script that carries it to the view it belongs to."""
    return (
        f"const view = (window.mtDiagrams || {{}})[{json.dumps(container_id)}];"
        f"if (view) view.command({json.dumps(name)}, {json.dumps(argument)});"
    )
