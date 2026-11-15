#! /usr/bin/env python3
#                                                                                      #
# diagmodel: the shapes of the data the interactive Diagram is made of.                #
#                                                                                      #

"""The records behind the interactive Diagram, named, so that a misspelled key is an error and not a quiet None.

The Diagram is drawn as text and made clickable from a model built beside it (see mapgen.diagintr).  That model is
a plain dictionary -- it is sent to the browser as JSON, and the script there reads it by these very key names -- so
each record is a TypedDict: the same dictionary at run time, with its keys and the type of each known to the checker.

The shapes live here, in the core, because the run state (primitem) has to name them and the core may not import
from the layer that builds them.

  CallEdge        one call the Diagram drew a connector for, as it is recorded while the diagram is drawn
  DiagramNode     one drawing of one object: where it sits and what a click on it means
  DiagramRegion   one Project's stretch of lines, what a fold takes away
  DiagramEdge     one call, as the two Tasks it joins and the connector groups drawn for it
  DiagramModel    all of them together, plus the tags in use
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class CallEdge(TypedDict):
    """A call the Diagram drew a connector for, in the rendered file's line numbering."""

    caller_row: int
    called_row: int
    caller_name: str  # carries the "(entry)" / "(exit)" marker the drawn name does not
    called_name: str
    project: str


class DiagramNode(TypedDict):
    """One drawing of one object, as a span the browser can wrap and a token to jump with."""

    anchor: str  # shared by every drawing of the object
    kind: str
    name: str
    line: int
    col: int  # in code points, which is what the renderer slices by
    len: int
    project: str  # the Project it was drawn under, which decides the Map that can answer a click
    token: str
    index: int  # which drawing this is, in reading order
    note: NotRequired[str]  # present only on an object the user has put a note or tags on
    tags: NotRequired[list[str]]


class DiagramRegion(TypedDict):
    """A Project's stretch of the diagram, from its top border to the line before the next Project's."""

    anchor: str
    name: str
    line: int  # the Project's name line
    start: int
    fold: int  # the first line a fold takes away
    end: int


class DiagramEdge(TypedDict):
    """A call, as the anchors of the two Tasks it joins and the connector groups drawn for it."""

    caller: str
    called: str
    groups: list[int]


class DiagramModel(TypedDict):
    """Everything the interactive view acts on, in the rendered file's own line and column coordinates."""

    nodes: list[DiagramNode]
    tags: dict[str, int]  # each tag in use -> how many drawn objects carry it
    regions: list[DiagramRegion]
    edges: list[DiagramEdge]


def empty_model() -> DiagramModel:
    """A model with nothing in it: what a Diagram left on disk by an older run, or any other view, has."""
    return {"nodes": [], "tags": {}, "regions": [], "edges": []}
