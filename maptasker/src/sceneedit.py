"""sceneedit: build an editable model of a Scene and apply Add/Rename/Delete to it.

The Scene counterpart of projedit.py/profedit.py/taskedit.py, and deliberately
shaped like projedit.py rather than the other two, because a Scene is keyed the
same way a Project is: taskerd.get_the_xml_data builds all_scenes with
move_xml_to_table(..., get_id=False, "nme"), so the dict key IS the Scene's name.

A Scene's identity is its name, and unlike a Project it is its name in three
places at once, which is what makes Rename the interesting operation here:

  1. the all_scenes key,
  2. the <nme> child,
  3. the element's own sr attribute -- sr="sceneGarden Lights", not the
     sr="scene0" positional index every other Tasker element uses (confirmed
     against this repo's own backup.xml and a single-Scene export: every
     single Scene in both is sr="scene<name>"),

plus, outside the Scene itself, every owning Project's <scenes> element, which
is a comma-separated list of Scene *names* (not ids -- a Scene has no <id> at
all, again unlike Project/Profile/Task). scenes.process_project_scenes reads
exactly that list, so a rename that misses it leaves the Project pointing at a
Scene name that no longer exists and the Scene stops appearing in every view.
apply_edited_scene_to_live_tree updates all four together; nothing else should
touch any of them on its own.

TWO KINDS OF SCENE, and every function here has to know which it is holding:

  Legacy (https://tasker.joaoapps.com/userguide/en/scenes.html) -- the original
  kind. Its UI is a flat list of <TextElement>/<RectElement>/<ButtonElement>/...
  children, each with its own <geom> geometry, and the Scene's <widthPort>/
  <heightPort>/<widthLand>/<heightLand> are the real pixel canvas those are laid
  out on.

  Version 2 (https://tasker.joaoapps.com/userguide/en/scenes_v2.html -- Tasker's
  own "Screen Builder") -- one <lj> child and no element children at all. <lj> is
  a whole component tree serialized as JSON, gzipped, then Base64'd; see
  decode_v2_layout/encode_v2_layout, which are the only two functions that should
  ever touch it. The layout is declarative (Column/Row/Scaffold with modifiers
  and event handlers, not x/y geometry), so all four size children are -1 on
  every V2 Scene -- confirmed across all three in XML/backup.xml, which belong to
  a test Project, a dialog-builder Project and a torch-brightness Project.

  is_v2_scene() is the check; scene_version() gives the display name. The two
  are told apart purely by whether <lj> is there, which is also how
  scenes.get_scene_elements decides how to render one.

  What each designer edits inside a Scene of its kind lives in a module of its own:
  sceneedit_legacy.py for the elements of a Legacy canvas, sceneedit_v2.py for the
  component tree of a V2 layout.  This module is the Scene as a whole -- loading,
  creating, renaming, saving, deleting, reverting -- and imports both; neither of them
  imports it.

The V2 layout JSON carries its own copy of the Scene's name, as a top-level
"name" key alongside "root" -- so a V2 rename is not just an XML edit; the JSON
has to be decoded, renamed, and re-encoded or the two disagree. apply_edits_to_scene
does this; see _rename_v2_layout.

NOT YET HANDLED, and the reason config.EDIT_SCENE defaults to False: a Scene's
own contents -- a Legacy Scene's UI elements and the Tasks they fire (ClickTask
and friends, see scenes.get_scene_elements), or a V2 Scene's component tree --
are carried along verbatim by every function here but cannot be edited. Renaming
a Scene also does not rewrite Task actions that name it (Show Scene, Hide Scene,
Destroy Scene all take the Scene name as a string argument); those keep pointing
at the old name. Both are the "details to be provided later" this sketch leaves
room for -- see guiwins._build_scene_editor_body, the one place a dialog body
for them has to go.

Never touches PrimeItems.xml_tree -- edits happen on a deep copy (Add/Rename) or
directly on the live tasker_root_elements tables (Delete), mirroring projedit.py.
"""

from __future__ import annotations

import base64
import copy
import gzip
import io
import json
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

from maptasker.src import editcommon, piiscan, sessundo
from maptasker.src.editcommon import set_child_text as _set_child_text
from maptasker.src.presave import backup_local_file
from maptasker.src.primitem import PrimeItems
from maptasker.src.editcommon import touch_project_mdate
from maptasker.src.sysconst import SCENE_TASK_TYPES
from maptasker.src.sceneedit_legacy import UNSET_DIMENSION, apply_element_renames_to_tasks, legacy_restore
from maptasker.src.sceneedit_v2 import _V2_ROOT_KEY

# Destination folder on the Android device for Save To Android -- the Scene sibling of
# projedit.ANDROID_PROJECT_LOCATION ("Tasker/projects"); see android_scene_path.
ANDROID_SCENE_LOCATION = "Tasker/scenes"
# What this editor's exports need that the other three's don't -- see editcommon.EditorKind.
EXPORT = editcommon.EditorKind(
    fallback="scene",
    extension=".scn.xml",
    android_location=ANDROID_SCENE_LOCATION,
)
# A brand-new *Legacy* Scene's size, in the same units Tasker itself writes.  Portrait gets
# a real default so a new Scene is visible at all; landscape gets -1, which is what Tasker
# uses for "not laid out for this orientation" (every Scene in this repo's sample data that
# has never been opened in landscape carries -1 for both landscape dimensions).  A Version 2
# Scene gets -1 for all four instead -- it has no canvas to size; see create_new_scene.
NEW_SCENE_WIDTH_PORTRAIT = "600"
NEW_SCENE_HEIGHT_PORTRAIT = "800"
# The Scene's four size children, paired with the label the dialog shows for each.
# The label lives here, next to the tag, rather than in guiwins, because three places
# have to agree on this list and would otherwise drift: guiwins._build_scene_editor_body
# builds one input per entry, userintr_editors._apply_scene_field_values validates them and names
# them in its error messages, and set_scene_dimensions writes them back.  The labels are
# English source strings -- every consumer runs them through translate_string.
SCENE_DIMENSION_FIELDS = (
    ("widthPort", "Width (portrait)"),
    ("heightPort", "Height (portrait)"),
    ("widthLand", "Width (landscape)"),
    ("heightLand", "Height (landscape)"),
)

# The two kinds of Scene (see this module's docstring).  These strings are what the Add
# Scene version picker shows and what create_new_scene takes, so they are display names,
# not internal codes -- there is no third value and nothing parses them.
SCENE_VERSION_LEGACY = "Legacy"
SCENE_VERSION_V2 = "Version 2"
SCENE_VERSIONS = (SCENE_VERSION_LEGACY, SCENE_VERSION_V2)
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
_V2_JSON_SEPARATORS = (",", ":")
_V2_GZIP_LEVEL = 6
# The layout JSON's other top-level key beside sceneedit_v2._V2_ROOT_KEY's tree: the Scene's
# own name, duplicated there by Tasker and therefore something a rename has to keep in step.
_V2_NAME_KEY = "name"


@dataclass
class EditableScene:
    """A deep-copied Scene element plus the name it was loaded under (the live
    all_scenes dict key -- may differ from the copy's own <nme> text once the
    user has typed a new one but not yet applied it).  Mirrors
    projedit.EditableProject, for the same reason: name-keyed table, so the
    key it came in under has to be remembered separately from the element.

    element_renames records (old name, new name) for every Legacy element the
    designer has renamed, in the order they were renamed, when the user asked for
    the Tasks that address them to be brought along.  It is deliberately a
    *pending* list rather than an edit already made: renaming an element inside
    this dialog changes a deep copy that Cancel throws away, but the Tasks it
    would rewrite are the live ones, so rewriting them as the rename is typed
    would leave a cancelled edit half-applied to the backup.  They are applied by
    apply_edited_scene_to_live_tree -- the single point at which this copy becomes
    the real Scene -- and by nothing else.
    """

    scene_name: str
    scene_element: Element
    element_renames: list[tuple[str, str]] = field(default_factory=list)


def is_v2_scene(scene_element: Element) -> bool:
    """Whether this is a Version 2 (Screen Builder) Scene rather than a Legacy one.

    The <lj> child is the whole test, and it is a reliable one in both directions:
    every V2 Scene has exactly one and no element children, every Legacy Scene has
    element children and no <lj>.  scenes.get_scene_elements branches on the same
    tag to decide how to render a Scene, so the two agree by construction.
    """
    return scene_element.find(V2_LAYOUT_TAG) is not None


def scene_version(scene_element: Element) -> str:
    """SCENE_VERSION_V2 or SCENE_VERSION_LEGACY -- the display name of what
    is_v2_scene() decides.  Used for dialog titles and the pulldown-free "this is
    what you are editing" line in the editor body.
    """
    return SCENE_VERSION_V2 if is_v2_scene(scene_element) else SCENE_VERSION_LEGACY


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
    itself does (see _V2_GZIP_LEVEL and the note above it -- this reproduces
    Tasker's own output byte for byte, which is what makes an edit that changes
    nothing leave the file unchanged).  Creates the <lj> child if it isn't there,
    so this doubles as "make this a V2 Scene" for create_new_scene.
    """
    payload = json.dumps(layout, separators=_V2_JSON_SEPARATORS, ensure_ascii=False).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=_V2_GZIP_LEVEL, mtime=0) as gzip_file:
        gzip_file.write(payload)
    _set_child_text(scene_element, V2_LAYOUT_TAG, base64.b64encode(buffer.getvalue()).decode("ascii"))


def _rename_v2_layout(scene_element: Element, new_name: str) -> None:
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
    layout[_V2_NAME_KEY] = new_name
    encode_v2_layout(scene_element, layout)


def resolve_scene_by_name(scene_name: str) -> Element | None:
    """Look up a Scene's live XML element by its name (also its all_scenes key).

    Callers must not mutate the returned element directly -- go through
    load_scene_for_edit() instead.
    """
    entry = PrimeItems.tasker_root_elements.get("all_scenes", {}).get(scene_name)
    return None if entry is None else entry["xml"]


def load_scene_for_edit(scene_name: str) -> EditableScene | None:
    """Resolve a Scene by name and deep-copy it -- the one point of contact with
    the live tree, so the in-memory backup is never touched until Rename is
    applied.  Mirrors projedit.load_project_for_edit.
    """
    live_element = resolve_scene_by_name(scene_name)
    if live_element is None:
        return None
    return EditableScene(scene_name=scene_name, scene_element=copy.deepcopy(live_element))


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
        _V2_ROOT_KEY: {
            "type": "Column",
            "id": "Column1",
            "horizontalAlignment": "Center",
            "verticalArrangement": "Center",
            "children": [],
        },
        _V2_NAME_KEY: name,
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
        _V2_ROOT_KEY: {
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
        _V2_NAME_KEY: name,
    }


def _v2_template_full_screen(name: str) -> dict:
    """A full-screen app frame: top bar, bottom navigation, and a content column.

    Modelled on the 'V2' Scene of a test Project -- the only real example of a Scaffold
    in this repo's backup -- so the slot names (topBar / bottomBar / content) and the
    NavigationItem shape match something Tasker demonstrably opens.
    """
    return {
        _V2_ROOT_KEY: {
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
        _V2_NAME_KEY: name,
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


def create_new_scene(
    name: str,
    version: str = SCENE_VERSION_LEGACY,
    template: str = V2_DEFAULT_TEMPLATE,
) -> EditableScene | str:
    """Build a brand-new, empty Scene element of either kind, not tied to any
    existing one.  Returns an error message string if no backup is loaded (needed
    to source the correct Element class -- see projedit.create_new_project's
    identical note).

    version is SCENE_VERSION_LEGACY or SCENE_VERSION_V2 -- the choice the Add
    Scene button prompts for before this is ever called (see
    guiwins.build_add_scene_version_dialog).  It decides two things, and they go
    together:

      * V2 gets an <lj> child holding new_v2_layout(); Legacy gets none.
      * V2's size children are all -1, Legacy's get a real portrait canvas.
        A V2 layout is declarative -- Column/Row/modifiers, not x/y geometry --
        so there is no canvas to size, and every real V2 Scene carries -1 across
        all four (see this module's docstring).  Handing a V2 Scene 600x800 would
        be inventing a constraint Tasker doesn't use.

    No <id> child, and no id counter to consult: unlike Task/Profile (a shared
    integer counter, see taskedit.next_unique_task_or_profile_id) and unlike
    Project (a UUID), a Scene has no <id> element at all in any Tasker backup --
    its name is its identity.  That is also why sr is "scene<name>" rather than
    a "sceneN" index; see this module's docstring.

    Children are emitted in the alphabetical order real Tasker Scenes use
    (cdate, edate, heightLand, heightPort, [lj,] nme, widthLand, widthPort) --
    note <lj> falls between heightPort and nme, exactly where all three real V2
    Scenes carry it -- so a round-trip through render_standalone_scene_xml
    matches what Tasker writes.  The Scene starts empty either way: adding
    elements/components is the part still to come (see this module's docstring).
    """
    if PrimeItems.xml_root is None:
        return "Load a Tasker backup file first (Add Scene needs it to build the Scene)."
    if version not in SCENE_VERSIONS:
        return f"'{version}' is not a kind of Scene. Choose {' or '.join(SCENE_VERSIONS)}."

    element_cls = type(PrimeItems.xml_root)
    clean_name = name.strip()
    is_v2 = version == SCENE_VERSION_V2
    scene_element = element_cls("Scene", {"sr": f"scene{clean_name}"})

    now_millis = str(int(time.time() * 1000))
    portrait_width = UNSET_DIMENSION if is_v2 else NEW_SCENE_WIDTH_PORTRAIT
    portrait_height = UNSET_DIMENSION if is_v2 else NEW_SCENE_HEIGHT_PORTRAIT
    for tag, text in (
        ("cdate", now_millis),
        ("edate", now_millis),
        ("heightLand", UNSET_DIMENSION),
        ("heightPort", portrait_height),
        ("nme", clean_name),
        ("widthLand", UNSET_DIMENSION),
        ("widthPort", portrait_width),
    ):
        child = element_cls(tag)
        child.text = text
        scene_element.append(child)

    if is_v2:
        # encode_v2_layout appends <lj> at the end; move it into alphabetical
        # position (after heightPort) so the child order matches a real V2 Scene's.
        encode_v2_layout(scene_element, v2_template_layout(clean_name, template))
        layout_element = scene_element.find(V2_LAYOUT_TAG)
        scene_element.remove(layout_element)
        scene_element.insert(list(scene_element).index(scene_element.find("nme")), layout_element)

    return EditableScene(scene_name=clean_name, scene_element=scene_element)


def scene_name_exists(name: str) -> bool:
    """Whether a Scene with this name already exists in the currently loaded backup."""
    return name.strip() in PrimeItems.tasker_root_elements.get("all_scenes", {})


def apply_edits_to_scene(edited_scene: EditableScene, new_name: str) -> list[str]:
    """Validate the new name, and only if valid, write it into the Scene copy's
    <nme> child AND its sr attribute (both carry the name -- see this module's
    docstring).  All-or-nothing, mirrors projedit.apply_edits_to_project.

    A no-op rename (new_name == edited_scene.scene_name) is allowed through --
    it's not a conflict with itself.

    A comma in the name is rejected, which no other object type has to care
    about: a Project lists the Scenes it owns as one comma-separated <scenes>
    string, so a Scene called "Big,Red" would read back as two Scenes named
    "Big" and "Red" and neither would resolve.

    For a Version 2 Scene there is a third place the name lives -- inside the
    <lj> layout JSON -- and _rename_v2_layout keeps it in step.  Nothing else in
    this module has to know: for a Legacy Scene that call does nothing.
    """
    errors = []

    new_name = new_name.strip()
    if not new_name:
        errors.append("Scene name cannot be empty.")
    elif "," in new_name:
        errors.append(
            "Scene name cannot contain a comma -- a Project lists its Scenes as one comma-separated name list.",
        )
    elif new_name != edited_scene.scene_name and scene_name_exists(new_name):
        errors.append(f"A Scene named '{new_name}' already exists in this backup. Choose a different name.")

    if errors:
        return errors

    _set_child_text(edited_scene.scene_element, "nme", new_name)
    edited_scene.scene_element.set("sr", f"scene{new_name}")
    _rename_v2_layout(edited_scene.scene_element, new_name)
    touch_scene_edate(edited_scene.scene_element)
    # Keep scene_name in sync with the applied <nme> -- register_new_scene keys
    # all_scenes by it, so a brand-new Scene (created with name "") would
    # otherwise be registered under "" and show up nameless in the Scene pulldown.
    edited_scene.scene_name = new_name
    return []


def touch_scene_edate(scene_element: Element) -> None:
    """Stamps a Scene's <edate> with the current time.  A Scene uses <edate> for
    "last modified", the way Task/Profile do -- not <mdate>, which is the
    Project-only spelling (see editcommon.touch_project_mdate).  Confirmed against
    this repo's own backup.xml: every Scene has <cdate>+<edate>, none has <mdate>.
    """
    _set_child_text(scene_element, "edate", str(int(time.time() * 1000)))


def set_scene_dimensions(edited_scene: EditableScene, dimensions: dict[str, str]) -> None:
    """Writes the Scene copy's size children (see SCENE_DIMENSION_FIELDS) and
    stamps <edate>.  Separate from apply_edits_to_scene because the two answer to
    different buttons -- the name is applied by Rename/Ok, the size by every save
    path -- and because unlike the name, a size can't collide with anything, so
    there is nothing here to validate against the rest of the backup.  Whether
    the values are well-formed is the caller's business (see
    userintr_editors._apply_scene_field_values, which checks them before calling this).
    """
    for tag, value in dimensions.items():
        _set_child_text(edited_scene.scene_element, tag, value)
    touch_scene_edate(edited_scene.scene_element)


def register_new_scene(edited_scene: EditableScene) -> None:
    """Adds a new Scene to the in-memory backup's all_scenes table so it behaves
    like any other Scene loaded from the backup -- so it shows up in the Scene
    pulldown, and so a second Add Scene with the same name is caught by
    scene_name_exists().  Call once, right after a successful Add Scene, and
    follow it with add_scene_to_project: registration alone leaves the Scene in
    a table nothing walks (see that function).
    """
    with sessundo.undoable(f"Add Scene '{edited_scene.scene_name}'"):
        PrimeItems.tasker_root_elements.setdefault("all_scenes", {})[edited_scene.scene_name] = {
            "xml": edited_scene.scene_element,
            "name": edited_scene.scene_name,
        }


def add_scene_to_project(scene_name: str, project_name: str) -> None:
    """Attaches a newly-registered Scene to a Project by appending its *name* to
    that Project's <scenes> element -- the mechanism Tasker, and every view this
    app generates, uses to know which Scenes belong to which Project:
    scenes.process_project_scenes splits exactly this element, and
    projects.process_project_scenes' caller walks it for the Map/Diagram/Tree
    output.  Names, not ids -- a Scene has no <id>; see this module's docstring.

    Without this, register_new_scene alone leaves a Scene sitting only in the
    all_scenes lookup table, which only the Scene pulldown reads -- so it exists
    and can be selected, but appears in no generated view at all.  This is the
    exact Scene analogue of profedit.add_profile_to_project's <pids> append.

    Mutates the Project's XML element in place (not a copy) -- the live Project
    table is already in PrimeItems.tasker_root_elements, so this takes effect
    immediately for every other view in the same session.  No-op if project_name
    isn't a known Project (defense in depth; the GUI only offers real names).
    """
    with sessundo.undoable(f"Add Scene '{scene_name}' to Project '{project_name}'"):
        project_entry = PrimeItems.tasker_root_elements.get("all_projects", {}).get(project_name)
        if project_entry is None:
            return

        project_element = project_entry["xml"]
        existing_names = _project_scene_names(project_element)
        if scene_name not in existing_names:
            existing_names.append(scene_name)
        _set_child_text(project_element, "scenes", ",".join(existing_names))
        touch_project_mdate(project_element)


def _project_scene_names(project_element: Element) -> list[str]:
    """Reads a Project's <scenes> as a list of Scene names, empty-safe.  The
    element is one comma-separated string; an empty or absent one is no Scenes.
    """
    child = project_element.find("scenes")
    if child is None or not child.text:
        return []
    return [name for name in child.text.split(",") if name]


def project_owning_scene(scene_name: str) -> str:
    """The name of the Project whose <scenes> lists this Scene, or "".

    Used when a Task is created from inside a Scene -- the Scene Properties Event tabs -- so
    the new Task can be attached to the same Project the Scene belongs to.  A Task in no
    Project's <tids> is an orphan: it runs, but it appears in no generated view of any
    Project, which is the Task analogue of what add_scene_to_project's docstring describes.

    The first Project that claims it wins.  A Scene listed by two Projects is not something
    Tasker writes, and picking the first is what every other by-name lookup here does.
    """
    if not scene_name:
        return ""
    for name, entry in PrimeItems.tasker_root_elements.get("all_projects", {}).items():
        if scene_name in _project_scene_names(entry["xml"]):
            return name
    return ""


def _set_project_scene_names(
    project_element: Element,
    scene_names: list[str],
) -> None:
    """Writes a Project's <scenes> back, removing the element entirely when the
    last Scene is gone rather than leaving an empty one behind -- an empty
    <scenes/> is not something Tasker itself ever writes, and
    scenes.process_project_scenes' own `if scene_list[0]` guard exists precisely
    because an empty string splits to [""] and would otherwise be processed as a
    Scene with no name.
    """
    child = project_element.find("scenes")
    if not scene_names:
        if child is not None:
            project_element.remove(child)
        return
    _set_child_text(project_element, "scenes", ",".join(scene_names))


def apply_edited_scene_to_live_tree(old_name: str, edited_scene: EditableScene) -> None:
    """Writes an edited (pre-existing) Scene back into the in-memory backup: its
    contents onto the live element, its all_scenes entry under whatever name it
    now carries, and -- if that name changed -- the <scenes> list of every
    Project that referenced the old one.

    The first of those three is the part that has to be a transplant, and is the
    one place this deliberately diverges from
    profedit.apply_edited_profile_to_live_tree/projedit.rename_project_in_live_tree,
    both of which simply swap the edited deep copy into the table in place of the
    old object.  Those get away with it because maputil2.write_full_backup_to_
    current_file reconciles by <id>, which survives a rename.  A Scene has no
    <id>, so that same function has to match it by <nme> -- and an object swap
    plus a rename means the tree's element still says the old name while the
    table's says the new one, so nothing matches: the old element is orphaned
    into the saved file and the renamed one is appended alongside it, leaving two
    Scenes where there was one.  (Observed, not theorized -- 50 Scenes in, 52
    out.)  Copying the edit *onto* the live element instead keeps one object
    carrying one name, so the deep copy the save takes of the tree and the entry
    in the table are the same Scene under the same name, whatever it was renamed
    to.

    The <scenes> sweep is the part with no Project/Profile/Task equivalent at
    all: those are referenced by id, which a rename doesn't change, whereas every
    reference to a Scene is by name and so goes stale the moment the name does.

    Safe to call when nothing was renamed -- that is the ordinary "Ok" path,
    which lands the size edits and leaves the name where it was.

    No-op if old_name isn't registered (defense in depth; the GUI should only
    ever pass a name that was just loaded via load_scene_for_edit).
    """
    with sessundo.undoable(f"Edit Scene '{old_name}'"):
        all_scenes = PrimeItems.tasker_root_elements.get("all_scenes", {})
        entry = all_scenes.get(old_name)
        if entry is None:
            return

        # Element renames the designer deferred, applied here because here is where this copy
        # stops being a copy.  Matched against old_name: a Task that addresses this Scene names
        # it as it was, and renaming a Scene has never rewritten those (see this module's
        # docstring), so the Scene name in a Task action is still the one it came in under.
        if edited_scene.element_renames:
            apply_element_renames_to_tasks(old_name, edited_scene.element_renames)
            edited_scene.element_renames.clear()

        live_element = entry["xml"]
        edited_element = edited_scene.scene_element
        if live_element is not edited_element:
            live_element.attrib.clear()
            live_element.attrib.update(edited_element.attrib)
            for child in list(live_element):
                live_element.remove(child)
            for child in list(edited_element):
                live_element.append(child)
        # From here on the model and the tree are the same element, so a second save
        # from the still-open dialog transplants onto itself and is a no-op.
        edited_scene.scene_element = live_element

        new_name = live_element.findtext("nme", "") or old_name
        if new_name != old_name:
            del all_scenes[old_name]
            for project_entry in PrimeItems.tasker_root_elements.get("all_projects", {}).values():
                project_element = project_entry["xml"]
                scene_names = _project_scene_names(project_element)
                if old_name not in scene_names:
                    continue
                # Positional replace, not remove-then-append: a Project's <scenes>
                # order is the order its Scenes are listed in every view, and a
                # rename is not a reordering.
                scene_names[scene_names.index(old_name)] = new_name
                _set_project_scene_names(project_element, scene_names)
                touch_project_mdate(project_element)

        all_scenes[new_name] = {"xml": live_element, "name": new_name}
        edited_scene.scene_name = new_name


def delete_scene(scene_name: str) -> list[str]:
    """Deletes a Scene from the in-memory backup and removes it from every
    Project's <scenes> list.  Returns [] on success, else a list of error
    strings (mirrors projedit.delete_project's convention), and mutates nothing
    on error.

    Nothing is deleted below it: a Scene's elements live inside the Scene
    element itself and go with it, and any Task those elements fire is a
    top-level Task owned by a Project, which is left exactly where it is (the
    same call the Delete Task dialog spells out in reverse).
    """
    with sessundo.undoable(f"Delete Scene '{scene_name}'"):
        all_scenes = PrimeItems.tasker_root_elements.get("all_scenes", {})
        if scene_name not in all_scenes:
            return [f"Scene '{scene_name}' no longer exists."]

        for project_entry in PrimeItems.tasker_root_elements.get("all_projects", {}).values():
            project_element = project_entry["xml"]
            scene_names = _project_scene_names(project_element)
            if scene_name not in scene_names:
                continue
            scene_names.remove(scene_name)
            _set_project_scene_names(project_element, scene_names)
            touch_project_mdate(project_element)

        del all_scenes[scene_name]
        return []


def sanitize_filename(name: str) -> str:
    """Strip characters illegal in filenames from a Scene name, falling back to "scene"."""
    return EXPORT.sanitize_filename(name)


def default_scene_save_path(scene_name: str) -> str:
    """Default standalone-export path: {output folder}/{sanitized name}.scn.xml."""
    return EXPORT.default_save_path(scene_name)


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten)."""
    return editcommon.save_path_exists(output_path)


def android_scene_path(scene_name: str) -> str:
    """The absolute path a Save To Android of this Scene would write to on the device.

    See EditorKind.android_path for the sanitized-name collision the overwrite prompt
    this feeds exists to catch.
    """
    return EXPORT.android_path(scene_name)


# The device screen size an export was written on, as "width,height" floats -- Tasker's own
# top-level <dmetric>.  Scene elements are laid out in device pixels, so an importing device
# needs to know what screen those pixels were measured on; see projedit's copy of this note
# for the measurement behind it.  All three genuine Tasker .scn.xml exports in this repo
# carry one (tv=6.3.x); the two without are this program's own earlier output (tv=6.7.6-beta,
# the loaded backup's own version), which is the bug rather than the counter-example.
_DISPLAY_METRIC_TAG = "dmetric"


def scene_task_ids(scene_element: Element) -> list[str]:
    """The ids of the Tasks this Scene's elements fire, in document order.

    A Scene element (RectElement, TextElement and the rest) hangs its handlers off children
    named in sysconst.SCENE_TASK_TYPES -- <clickTask>, <longclickTask>, <strokeTask> and so
    on -- each holding a Task id.  Same table sceneview.element_tasks reads to label them in
    the Scene view, so the two cannot disagree about what counts as firing a Task.

    Walked with iter() rather than over direct children, for two reasons: the handlers hang
    off the ELEMENTS inside a Scene rather than off the Scene itself, and a Scene can
    contain another Scene (eight of them do in this repo's own backup), whose elements fire
    Tasks just the same.

    Negative ids are dropped.  Those are Tasker's anonymous inline Tasks (scenes.process_tasks
    calls them "fake"): there is no <Task> element anywhere in the backup with such an id --
    measured, all 18 of them -- because the Task lives inside the Scene already and travels
    with it.

    Lives here rather than in projedit, which also needs it (a Project bundles its Scenes,
    so it bundles their Tasks too), because it is a fact about Scenes.  projedit imports it;
    nothing here imports projedit, so the direction is safe.
    """
    found = []
    for element in scene_element.iter():
        if element.tag not in SCENE_TASK_TYPES:
            continue
        task_id = (element.text or "").strip()
        if task_id and not task_id.startswith("-"):
            found.append(task_id)
    return found


def render_standalone_scene_xml(scene_name: str, *, redact: bool = False) -> str:
    """Render a Scene as a standalone TaskerData/Scene XML string, matching the
    shape Tasker's own Scene export produces (verified against a single-Scene
    export in this repo's sample data: a TaskerData root holding one <Scene>, which keeps
    its sr="scene<name>" and all of its UI elements).

    Emits <dmetric>, the Scene, then every Task the Scene's elements fire -- the shape
    another sample Scene export has exactly ('dmetric', 'Scene', 'Task', 'Task').  The
    Tasks used to be left out on the reasoning that a Scene's UI elements are children of
    the Scene element, so one deep copy was the whole export; that is true of the LAYOUT and
    false of the behaviour.  A <clickTask> holds an id and nothing else, so a Scene exported
    alone arrives on the device with its buttons wired to Tasks that are not there.

    Nothing is stripped -- a Scene has no <id>/<clr>/<mdate> to omit, and its sr carries the
    name rather than a document position, so unlike a Project's sr="proj0" there is nothing
    to renumber.

    Still deliberately NOT recursive: a Task reached only through another Task's "Perform
    Task" action is not chased, the same limit projedit.render_standalone_project_xml has.

    Raises ValueError if scene_name isn't a currently-loaded Scene.

    `redact` runs the export through piiscan first, replacing the API keys, tokens,
    passwords, phone numbers, email addresses and coordinates in it with markers and
    writing a comment above the file saying what went -- what "Redact secrets" on the
    export button does.  Off by default, so nothing that already calls this changes.
    """
    scene_entry = PrimeItems.tasker_root_elements.get("all_scenes", {}).get(scene_name)
    if scene_entry is None:
        msg = f"Scene '{scene_name}' no longer exists in this backup."
        raise ValueError(msg)

    scene_copy = copy.deepcopy(scene_entry["xml"])
    tv = PrimeItems.xml_root.attrib.get("tv", "") if PrimeItems.xml_root is not None else ""

    # Match the parsed tree's actual Element class (see projedit's identical note).
    element_cls = type(scene_copy)
    root = element_cls("TaskerData", {"sr": "", "dvi": "1", "tv": tv})

    # <dmetric> first, where Tasker puts it.  Copied from the loaded backup rather than
    # invented: the right value is the screen these elements were laid out on, which is the
    # device the backup came from.  A backup without one exports without one -- inventing a
    # screen size would have Tasker scale the Scene to a device that never existed.
    source_metric = PrimeItems.xml_root.find(_DISPLAY_METRIC_TAG) if PrimeItems.xml_root is not None else None
    if source_metric is not None:
        root.append(copy.deepcopy(source_metric))

    root.append(scene_copy)

    # Then the Tasks its elements fire.  Nothing but the Scene points at these, so without
    # them the Scene imports and its buttons do nothing -- a failure that looks like a
    # successful import.  Ids that resolve to no Task are skipped rather than faked.
    all_tasks = PrimeItems.tasker_root_elements.get("all_tasks", {})
    seen: set[str] = set()
    for task_id in scene_task_ids(scene_copy):
        task_entry = all_tasks.get(task_id)
        if task_entry is not None and task_id not in seen:
            seen.add(task_id)
            root.append(copy.deepcopy(task_entry["xml"]))

    # Redacting happens HERE, on the tree that is about to be serialized, rather than at
    # the button that asked for it: this is the one line every export of this kind passes
    # through, so an export path added later cannot quietly skip it.  See piiscan.
    notice = piiscan.redact_rendered(root) if redact else ""

    ETW.indent(root, space="\t")
    # No <?xml ...?> declaration -- see profedit.render_standalone_profile_xml.
    return notice + ETW.tostring(root, encoding="unicode") + "\n"


def write_standalone_scene_xml(scene_name: str, output_path: str, *, redact: bool = False) -> str:
    """Write a Scene as a standalone .scn.xml file.  Raises OSError on failure,
    ValueError if the Scene no longer exists.

    A safety copy of anything already at `output_path` is taken first, into a
    MapTasker_Backups folder beside it -- see presave.backup_local_file.  Taken here
    rather than at the buttons that call this, so no export path can be added later that
    quietly skips it.  Returns the copy's path, or "" if there was nothing to copy or the
    copy failed (which does not stop the write -- see presave's module comment).

    `redact` is passed straight through to the render (see it for what goes).  Only the
    local exports offer it: "Save To Android" puts the configuration back on the user's own
    device, where the keys in it are the keys it needs to work, and a redacted upload would
    be an import that silently stopped functioning.
    """
    rendered = render_standalone_scene_xml(scene_name, redact=redact)
    _, safety_copy = backup_local_file(output_path)
    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(rendered)
    return safety_copy


def save_scene_to_android(scene_name: str, ip_address: str, ip_port: str) -> tuple[int, str]:
    """Writes the Scene onto the Android device's storage under /Tasker/scenes.  The
    upload and its readback-verify are EditorKind.upload_and_verify, shared with the
    other three editors; see it for why a 200 from /upload proves nothing on its own,
    and why this does not touch Tasker's live configuration.

    Returns (0, device_file_path) on success, or (return_code, error_message).
    """
    # render_standalone_scene_xml raises where the Scene has been deleted since the
    # dialog opened; upload_and_verify calls it only once the address checks out.
    try:
        return_code, result, _on_device = EXPORT.upload_and_verify(
            ip_address,
            ip_port,
            scene_name,
            lambda: render_standalone_scene_xml(scene_name).encode("utf-8"),
        )
    except ValueError as e:
        return 8, str(e)
    return return_code, result


def session_snapshot(edited_scene: EditableScene) -> Element:
    """The Scene as the Edit dialog found it, kept for the whole edit session so Cancel has
    something to put back.  One deep copy per dialog, taken once -- see revert_session.
    """
    return copy.deepcopy(edited_scene.scene_element)


def revert_session(
    edited_scene: EditableScene,
    snapshot: Element,
    layout: dict | None = None,
) -> bool:
    """Undo everything an edit session did to the Scene, and say whether there was anything
    to undo.

    WHAT THIS IS AND IS NOT UNDOING.  The dialog edits a deep copy (load_scene_for_edit), and
    that copy reaches the real backup at exactly one point, apply_edited_scene_to_live_tree,
    which Cancel never goes near -- so cancelling was already safe for the *file*.  What it
    was not was safe for what is on *screen*: a Preview holds this very element and goes on
    drawing whatever the designer did to it, so a Scene dragged about in the preview and then
    cancelled kept showing the new positions, which reads as Cancel having done nothing.
    Putting the copy back is what makes the two agree.

    In place, and for the reason legacy_restore gives: EditableScene, the dialog's field_refs
    and the Preview all hold this element object.

    `layout` is the Version 2 designer's decoded tree (field_refs["v2_layout"]).  It has to be
    reverted as well as the element, and cannot be reverted *from* it without a step: that
    dict is the thing V2 edits, and it is only encoded back into <lj> when a save runs, so a
    session's V2 work lives entirely in the dict and not at all in the element that was just
    restored.  Re-decoding the restored element is what turns one back into the other.

    element_renames goes too.  It is a list of renames *pending* against the live Tasks, held
    precisely because they must not happen until the copy is applied -- so a cancelled session
    has to leave none of them queued for a session that is applied later.
    """
    changed = ETW.tostring(edited_scene.scene_element) != ETW.tostring(snapshot) or bool(
        edited_scene.element_renames,
    )
    # Decoded from the snapshot rather than from the restored element, which is the same
    # content one step later, so the layout is read once and answers both questions below.
    original_layout = decode_v2_layout(snapshot) if layout is not None else None
    if not changed and isinstance(original_layout, dict):
        # A Version 2 session leaves the element alone from beginning to end -- its work is
        # in the dict until a save encodes it -- so comparing elements calls a reordered,
        # retyped, half-rebuilt V2 layout "unchanged".  Asking the dict is what makes Cancel
        # able to say it discarded something on the one kind of Scene where it always had.
        changed = original_layout != layout

    legacy_restore(edited_scene.scene_element, snapshot)
    edited_scene.element_renames.clear()
    if isinstance(original_layout, dict):
        layout.clear()
        layout.update(original_layout)
    return changed
