"""scenelayout: a Version 2 Scene's <lj> child -- decoded, encoded, renamed, and started from a template."""

#! /usr/bin/env python3

#                                                                                      #
# scenelayout: the XML half of a Version 2 Scene's component tree.                       #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# A Version 2 (Screen Builder) Scene is one <lj> child holding the whole component tree as
# JSON, gzipped and Base64'd.  This module is everything that touches that child as XML:
# decode_v2_layout and encode_v2_layout (the only two functions that should ever read or
# write it), rename_v2_layout (the layout carries its own copy of the Scene's name), and the
# starting layouts Add Scene offers.
#
# What it is NOT is the tree's editing.  sceneedit_v2 works on the decoded dict and never
# touches XML; this module is the other side of that line.  This one imports nothing of
# sceneedit_v2's, which takes the one key they share (V2_ROOT_KEY, defined here) from it.
# Both sit below scenemodel, which chooses between the Legacy and the V2 way of doing each
# thing -- so sceneedit, which has to ask scenemodel, never has to know there is a codec to call.
#
# Split out of sceneedit, where it sat among the Scene-as-a-whole functions it had nothing
# in common with and made sceneedit and scenemodel need each other.
from __future__ import annotations

import base64
import gzip
import io
import json
from typing import TYPE_CHECKING

from maptasker.src.editcommon import set_child_text

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

# The layout JSON's top-level key holding the component tree.  (Its sibling, the Scene's
# name, is V2_NAME_KEY below: only a rename ever touches it.)
V2_ROOT_KEY = "root"
# The child holding a V2 Scene's whole component tree -- gzipped, Base64'd JSON.  Its
# presence is the entire difference between the two kinds of Scene.
V2_LAYOUT_TAG = "lj"
# How Tasker itself encodes <lj>, matched byte-for-byte rather than guessed: compact JSON
# separators (no spaces), gzip at level 6 with the mtime header zeroed.  Re-encoding all
# three V2 Scenes in XML/backup.xml with exactly these settings reproduces Tasker's own
# Base64 string character for character, which is the only way to be sure a Scene this app
# rewrites is still the same file Tasker wrote.  (mtime especially: gzip stamps the current
# time into the header by default, so without mtime=0 an untouched Scene's <lj> would come
# out different on every single save.)
_JSON_SEPARATORS = (",", ":")
_GZIP_LEVEL = 6
# The layout JSON's other top-level key beside V2_ROOT_KEY's tree: the Scene's
# own name, duplicated there by Tasker and therefore something a rename has to keep in step.
V2_NAME_KEY = "name"


def decompress_gzip_json(b64_string: str) -> dict | str:
    """Decodes a Base64 string, decompresses it using Gzip, and parses the JSON.

    This function reverses a common data pipeline where a JSON object is
    serialized, compressed to save space, and encoded into Base64 for
    safe transmission as text.

    Args:
        b64_string (str): A Base64-encoded string representing zlib-compressed
            JSON data.

    Returns:
        dict|list|str: The parsed JSON data. The type depends on the structure
            of the original JSON (usually a dictionary or list).
        str: Returns an error message string if decoding, decompression,
            or parsing fails.

    Example:
        >>> example_input = "eJyrViotTi1SslJQcs7PzffLzM8rSyzI0S9ITM5W0lFKzMkMDvIBAL06C9M="
        >>> decompress_json(example_input)
        {'status': 'success', 'data': [1, 2, 3]}
    """
    try:
        # 1. Decode Base64 to bytes
        compressed_data = base64.b64decode(b64_string)

        # 2. Use BytesIO to treat the bytes like a file, then decompress with gzip
        with gzip.GzipFile(fileobj=io.BytesIO(compressed_data)) as f:
            decompressed_data = f.read()

        # 3. Parse JSON
        return json.loads(decompressed_data.decode("utf-8"))

    except (ValueError, OSError, EOFError) as e:
        # The whole of what this decode chain throws on bad input: binascii.Error and
        # json.JSONDecodeError and UnicodeDecodeError are all ValueError, gzip.BadGzipFile
        # is an OSError, and a truncated member is EOFError.  A TypeError here would be a
        # bug in the caller and no longer disappears into this string.
        return f"An error occurred: {e}"


def decode_v2_layout(scene_element: Element) -> dict | None:
    """The V2 Scene's component tree, decoded from <lj> into plain Python.

    Returns None for a Legacy Scene (no <lj>), and also for an <lj> that won't
    decode -- a corrupt or truncated one, or a future encoding this doesn't know.
    Callers treat None as "nothing to show/change here" and leave the element
    untouched, which is the safe answer either way: a layout that can't be read
    certainly shouldn't be re-encoded over the top of the original.

    Decoding itself is decompress_gzip_json, above, which the Map's Scene output
    (scenes) decodes with too.  The encode half is encode_v2_layout, below.
    """
    layout_element = scene_element.find(V2_LAYOUT_TAG)
    if layout_element is None or not layout_element.text:
        return None

    decoded = decompress_gzip_json(layout_element.text)
    # decompress_gzip_json reports failure by returning its error message as a
    # string rather than raising, so anything that isn't a dict is a failure.
    return decoded if isinstance(decoded, dict) else None


def encode_v2_layout(scene_element: Element, layout: dict) -> None:
    """Writes a component tree back into the Scene's <lj>, encoded the way Tasker
    itself does (see _GZIP_LEVEL and the note above it -- this reproduces
    Tasker's own output byte for byte, which is what makes an edit that changes
    nothing leave the file unchanged).  Creates the <lj> child if it isn't there,
    so this doubles as "make this a V2 Scene" for create_new_scene.
    """
    payload = json.dumps(layout, separators=_JSON_SEPARATORS, ensure_ascii=False).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=_GZIP_LEVEL, mtime=0) as gzip_file:
        gzip_file.write(payload)
    set_child_text(scene_element, V2_LAYOUT_TAG, base64.b64encode(buffer.getvalue()).decode("ascii"))


def rename_v2_layout(scene_element: Element, new_name: str) -> None:
    """Keeps a V2 Scene's embedded layout name in step with its <nme>.

    Tasker stores the Scene's name twice -- once as the <nme> child, once as the
    layout JSON's top-level "name" (all three V2 Scenes in XML/backup.xml carry
    both, always agreeing).  Renaming only the XML leaves the two disagreeing
    inside a single file, so this decodes, sets, and re-encodes.

    No-op for a Legacy Scene, and for a V2 Scene whose <lj> won't decode -- see
    decode_v2_layout on why a layout that can't be read is left alone rather than
    overwritten.
    """
    layout = decode_v2_layout(scene_element)
    if layout is None:
        return
    layout[V2_NAME_KEY] = new_name
    encode_v2_layout(scene_element, layout)


def new_v2_layout(name: str) -> dict:
    """The component tree a brand-new Version 2 Scene starts with: a single
    centred Column holding nothing, plus the Scene's name.

    Modelled on the smallest real V2 Scene in XML/backup.xml (a torch-brightness
    slider) with its one child removed -- same root
    type, same keys, same order -- rather than invented, so what Tasker's Screen
    Builder opens is a shape it already writes itself.  Deliberately no
    "defaultDisplayMode": only one of the three real V2 Scenes sets it, so it is
    optional and Tasker's own default is the right thing for a new Scene.
    """
    return {
        V2_ROOT_KEY: {
            "type": "Column",
            "id": "Column1",
            "horizontalAlignment": "Center",
            "verticalArrangement": "Center",
            "children": [],
        },
        V2_NAME_KEY: name,
    }


def _v2_dismiss_actions(label: str) -> list[dict]:
    """The action list a dialog button runs: record which button was pressed, then close.

    Copied from the 'Dialog' Scene's own close button rather than invented -- it writes
    sd_button_index and sd_button before DismissLayout, and those two names are what the
    dialog-builder Project's Task reads back afterwards. A template that used different
    variable names would look right and return nothing.
    """
    return [
        {"type": "SetVariable", "variable": "sd_button", "value": label},
        {"type": "DismissLayout"},
    ]


def _v2_template_dialog(name: str, *, with_buttons: bool) -> dict:
    """A titled dialog: header row with a title and a close button, then a content column.

    This is the 'Dialog' Scene of the dialog-builder Project, reduced to its frame --
    same root Column with the rounded border, same SpaceBetween header, same close button
    behaviour -- with its runtime-injected body replaced by an ordinary Text the user can
    edit or delete.
    """
    children: list[dict] = [
        {
            "type": "Row",
            "id": "header",
            "horizontalArrangement": "SpaceBetween",
            "verticalAlignment": "Center",
            "modifiers": [{"type": "FillWidth"}, {"type": "Padding", "all": "8"}],
            "children": [
                {"type": "Text", "id": "title_text", "text": "Title", "textSize": "22"},
                {
                    "type": "IconButton",
                    "id": "close_button",
                    "icon": "icon:Close",
                    "contentScale": "FillBounds",
                    "eventHandlers": {
                        "handlers": [{"events": [{"type": "click"}], "actions": _v2_dismiss_actions("Close")}],
                    },
                },
            ],
        },
        {
            "type": "Column",
            "id": "content",
            "horizontalAlignment": "Center",
            "verticalArrangement": "Center",
            "spacing": "8",
            "modifiers": [{"type": "FillWidth"}, {"type": "Padding", "horizontal": "16", "bottom": "8"}],
            "children": [{"type": "Text", "id": "body_text", "text": "Body text"}],
        },
    ]

    if with_buttons:
        children.append(
            {
                "type": "Row",
                "id": "button_row",
                "horizontalArrangement": "End",
                "verticalAlignment": "Center",
                "spacing": "8",
                "modifiers": [{"type": "FillWidth"}, {"type": "Padding", "all": "8"}],
                "children": [
                    {
                        "type": "Button",
                        "id": f"button_{index}",
                        "text": label,
                        "eventHandlers": {
                            "handlers": [{"events": [{"type": "click"}], "actions": _v2_dismiss_actions(label)}],
                        },
                    }
                    for index, label in enumerate(("Cancel", "OK"), start=1)
                ],
            },
        )

    return {
        V2_ROOT_KEY: {
            "type": "Column",
            "id": "root_column",
            "horizontalAlignment": "Center",
            "verticalArrangement": "Center",
            "modifiers": [
                {"type": "FillWidth"},
                {"type": "Border", "color": "outline", "shape": "Rounded", "radius": "16"},
            ],
            "children": children,
        },
        V2_NAME_KEY: name,
    }


def _v2_template_full_screen(name: str) -> dict:
    """A full-screen app frame: top bar, bottom navigation, and a content column.

    Modelled on the 'V2' Scene of a test Project -- the only real example of a Scaffold
    in this repo's backup -- so the slot names (topBar / bottomBar / content) and the
    NavigationItem shape match something Tasker demonstrably opens.
    """
    return {
        V2_ROOT_KEY: {
            "type": "Scaffold",
            "id": "Scaffold1",
            "topBar": [
                {
                    "type": "TopAppBar",
                    "id": "TopAppBar1",
                    "title": [{"type": "Text", "id": "Text1", "text": "Title", "textSize": "22"}],
                },
            ],
            "bottomBar": [
                {
                    "type": "NavigationBar",
                    "id": "NavBar1",
                    "content": [
                        {"type": "NavigationItem", "id": f"NavItem{index}", "icon": icon, "label": label}
                        for index, (icon, label) in enumerate(
                            (("icon:Home", "Home"), ("icon:Search", "Search"), ("icon:Settings", "Settings")),
                            start=1,
                        )
                    ],
                },
            ],
            "content": [
                {
                    "type": "Column",
                    "id": "Column1",
                    "horizontalAlignment": "Center",
                    "verticalArrangement": "Center",
                    "children": [{"type": "Text", "id": "Text2", "text": "Content"}],
                },
            ],
        },
        V2_NAME_KEY: name,
    }


# The starting points Add Scene offers for a Version 2 Scene, in the order it lists them.
# Each entry is (label, description, builder).  Every one of these is traced to a Scene in
# XML/backup.xml rather than composed from the schema, because the schema says what is
# *possible* and these Scenes are evidence of what Tasker actually opens.
V2_TEMPLATES: tuple[tuple[str, str, object], ...] = (
    ("Empty", "A single centred Column to build in.", new_v2_layout),
    (
        "Titled dialog",
        "Header with a title and close button, and a content area.",
        lambda name: _v2_template_dialog(name, with_buttons=False),
    ),
    (
        "Dialog with buttons",
        "A titled dialog plus a Cancel / OK row that reports which was pressed.",
        lambda name: _v2_template_dialog(name, with_buttons=True),
    ),
    ("Full screen", "Scaffold with a top bar, bottom navigation and content.", _v2_template_full_screen),
)
V2_DEFAULT_TEMPLATE = V2_TEMPLATES[0][0]


def v2_template_layout(name: str, template: str) -> dict:
    """Build the named template's component tree.  Falls back to the empty one for a name
    that isn't offered, so a stale caller degrades to "blank Scene" rather than failing.
    """
    for label, _description, builder in V2_TEMPLATES:
        if label == template:
            return builder(name)
    return new_v2_layout(name)
