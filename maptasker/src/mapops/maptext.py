"""maptext: the text a person reads on the phone, as a table to translate or edit, and written back.

A Project shared in one language is shared in one language.  The words in it are scattered over hundreds of
arguments and, worst, inside Scenes -- a Legacy Scene keeps a button's label in an element's argument, a Version 2
Scene keeps it inside a gzipped JSON blob -- so changing them by hand means opening every Task and every Scene.
This gathers them into one table (extract), a spreadsheet or a translator fills the last column in (write_table,
read_table), and plan_apply turns what came back into a Plan that mapswap applies: previewed, undoable, and each
change checked before it is made.

WHAT IS TEXT.  What the phone shows or says, and nothing a script compares against:

  * Task actions: Flash, Notify (and its Sound, Vibrate and LED forms), Say, Popup, Menu, the dialogs (Input, Text/
    Image, Pick Input, Progress, List -- its Title only, since its Items come back as the choice and a Task may test
    them), Authentication, Set Widget Label, and the text an action puts in a Scene element.  ACTION_TEXT is the list.
  * Legacy Scenes: a Text element's text, a Button's label, a Toggle's two labels, a list item's label, a Text Edit's
    text, and the Scene's title, subtitle and tab labels.  Also the actions a list item carries (a Flash on a tap).
  * Version 2 Scenes: a Text's text, a Button's text, a Text Input's, Segmented Button's and Navigation Item's label.

Not text: any name (of a Project, Task, Scene or element -- other places refer to them by it, so a translated name
breaks every Perform Task and Show Scene that names it), a Scene's colours, a Text Edit's variable.  A string with
nothing in it but variables ("%city") is left out as there is nothing to translate.

WHAT COMES BACK IS CHECKED.  A row is applied only if

  * its key is in this configuration (the table is for this backup, or one with the same objects);
  * the text it was made from is still the text there (so a table made last month does not overwrite an edit made
    since -- the row is reported, not applied);
  * it names the same %variables as the text it replaces (a translation that drops or renames one would send the
    wrong thing at run time).

Those that fail are Skips in the Plan, with the reason, never silently dropped.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from maptasker.src.analysis import mapfind
from maptasker.src.core import maputil2, scenelayout
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.editcommon import argument_elements
from maptasker.src.core.mapjump import SCENE, TASK, Target, scene_component_part, scene_element_parts
from maptasker.src.core.outdir import output_path
from maptasker.src.edit import projedit, scenemodel
from maptasker.src.mapgen.varxref import VARIABLE_PATTERN
from maptasker.src.mapops import mapswap
from maptasker.src.mapops.mapswap_model import LEGACY_SCENE, STR_ARG, V2_SCENE, Change, Plan, Site, Skip

if TYPE_CHECKING:
    from collections.abc import Iterable
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# ##################################################################################
# What counts as text
# ##################################################################################
# Action code -> ((argument id, what the argument is called), ...).  The code is the action's <code>, without
# the trailing "t" actionc.py's keys carry.  To make another action's text translatable, add it here.
ACTION_TEXT: dict[str, tuple[tuple[str, str], ...]] = {
    "548": (("0", "Text"), ("3", "Title")),  # Flash
    "523": (("0", "Title"), ("1", "Text")),  # Notify
    "525": (("0", "Title"), ("1", "Text")),  # Notify LED
    "536": (("0", "Title"), ("1", "Text")),  # Notify Vibrate
    "538": (("0", "Title"), ("1", "Text")),  # Notify Sound
    "559": (("0", "Text"),),  # Say
    "699": (("0", "Text"),),  # Say To File
    "550": (("0", "Title"), ("1", "Text")),  # Popup
    "551": (("0", "Title"),),  # Menu
    "552": (("0", "Text"),),  # Popup Task Buttons
    "360": (("1", "Title"), ("2", "Text")),  # Input Dialog
    "377": (
        ("1", "Title"),
        ("2", "Text"),
        ("3", "Button 1"),
        ("4", "Button 2"),
        ("5", "Button 3"),
    ),  # Text/Image Dialog
    "378": (("2", "Title"),),  # List Dialog
    "390": (("2", "Title"), ("3", "Text")),  # Pick Input Dialog
    "391": (("2", "Title"), ("3", "Text")),  # Progress Dialog
    "314": (("1", "Title"), ("2", "Subtitle"), ("3", "Description"), ("4", "Cancel Button Text")),  # Authentication
    "155": (("1", "Label"),),  # Set Widget Label
    "51": (("3", "Text"),),  # Element Text
    "740": (("1", "Text"),),  # Zoom Text
}

# Legacy Scene element tag -> ((argument id, what it is called), ...).
LEGACY_TEXT: dict[str, tuple[tuple[str, str], ...]] = {
    "TextElement": (("1", "Text"),),
    "ButtonElement": (("1", "Label"),),
    "EditTextElement": (("1", "Text"),),
    "ToggleElement": (("2", "Off Label"), ("3", "On Label")),
    "PropertiesElement": (("4", "Title"), ("5", "Subtitle"), ("7", "Tab Labels")),
}

# Version 2 component type -> the property that holds its text.
V2_TEXT: dict[str, tuple[str, ...]] = {
    "Text": ("text",),
    "Button": ("text",),
    "TextInput": ("label",),
    "SegmentedButtonItem": ("label",),
    "NavigationItem": ("label",),
}

# The columns of the table, in order.  `translation` is the one to fill in.
COLUMNS: tuple[str, ...] = ("key", "project", "object", "kind", "text", "translation")
CSV = "csv"
JSON = "json"
FORMATS = (CSV, JSON)


class TextTableError(Exception):
    """A table that cannot be read, with a sentence that says why."""


@dataclass(frozen=True)
class TextItem:
    """One piece of text, and the field that holds it."""

    key: str  # what finds it again: "task:118#act3.arg0", "scene:Reminder#elements4.arg1", ...
    kind: str  # "Flash Text", "Button Label"
    text: str
    site: Site  # the field, ready to be written with a new value

    @property
    def project(self) -> str:
        """The Project the owning Task or Scene is in, "" if none."""
        return self.site.where.project

    @property
    def owner(self) -> str:
        """The object the text is in, as a report names it."""
        where = self.site.where
        what = "Task" if where.kind == TASK else "Scene"
        return f"{what} '{where.name or where.key}'"


@dataclass(frozen=True)
class Row:
    """One line of a table that has been read back: what it was made from and what it is to become."""

    key: str
    object: str
    text: str
    translation: str


# ##################################################################################
# Finding the text
# ##################################################################################
def has_words(text: str) -> bool:
    """Whether there is anything in this to translate: a letter that is not part of a %variable."""
    return any(character.isalpha() for character in VARIABLE_PATTERN.sub("", text))


def extract(state: RunState, project: str = "") -> list[TextItem]:
    """Every piece of text in the loaded configuration, or in one Project's Tasks and Scenes.

    In the order a person would read the Map: Tasks first, then Scenes, each in file order.
    """
    items: list[TextItem] = []
    index = mapfind.build_index(state=state)
    scenes = state.tasker_root_elements.get("all_scenes", {})
    for record in index.objects:
        if project and record.project != project:
            continue
        if record.kind == TASK:
            for found in record.actions:
                if found.element is not None:
                    items.extend(
                        _action_items(
                            found.element,
                            f"task:{record.target.key}#act{found.number}",
                            record.target.at_action(found.number),
                        )
                    )
        elif record.kind == SCENE and (scene := scenes.get(record.target.key)) is not None:
            items.extend(_scene_items(scene["xml"], record.target))
    return _unique(items)


def _unique(items: list[TextItem]) -> list[TextItem]:
    """The items with no two keys alike: a repeat is numbered ("~2"), so every row finds exactly one field."""
    seen: Counter[str] = Counter()
    numbered: list[TextItem] = []
    for item in items:
        seen[item.key] += 1
        numbered.append(item if seen[item.key] == 1 else replace(item, key=f"{item.key}~{seen[item.key]}"))
    return numbered


def _action_items(action: Element, key: str, where: Target) -> list[TextItem]:
    """The text of one action, if it is an action that has any."""
    code = (action.findtext("code") or "").strip()
    spec = ACTION_TEXT.get(code)
    if spec is None:
        return []
    name = action_codes[f"{code}t"].name if f"{code}t" in action_codes else f"code {code}"
    arguments = argument_elements(action)
    found: list[TextItem] = []
    for arg_id, label in spec:
        element = arguments.get(arg_id)
        if element is None or element.tag != "Str" or not has_words(element.text or ""):
            continue
        detail = f"{name}, {label}="
        site = Site(kind=STR_ARG, element=element, where=where, detail=detail)
        found.append(TextItem(f"{key}.arg{arg_id}", f"{name} {label}", element.text or "", site))
    return found


def _scene_items(scene: Element, place: Target) -> list[TextItem]:
    """The text of one Scene, of either kind."""
    if scenemodel.is_v2_scene(scene):
        return _v2_items(scene, place)
    return _legacy_items(scene, place)


def _legacy_items(scene: Element, place: Target) -> list[TextItem]:
    parts = scene_element_parts(scene)
    found: list[TextItem] = []
    number = -1  # which of the Scene's list items this is: two in one list share their parent's anchor
    unanchored: Counter[str] = Counter()
    for element in scene.iter():
        part = parts.get(id(element), "")
        if not part and element.tag in LEGACY_TEXT:
            # The Map anchors no element of a sub-Scene (see scene_element_parts), so a Scene with one has two
            # Properties elements and no part to tell them apart by: they are numbered instead.
            part = f"{element.tag}.{unanchored[element.tag]}"
            unanchored[element.tag] += 1
        if element.tag in LEGACY_TEXT:
            arguments = argument_elements(element)
            for arg_id, label in LEGACY_TEXT[element.tag]:
                text_element = arguments.get(arg_id)
                if text_element is None or text_element.tag != "Str" or not has_words(text_element.text or ""):
                    continue
                kind = f"{element.tag.removesuffix('Element')} {label}"
                where = place.at_part(parts.get(id(element), ""), kind)
                site = Site(kind=LEGACY_SCENE, element=text_element, where=where, detail=kind)
                found.append(TextItem(f"scene:{place.key}#{part}.arg{arg_id}", kind, text_element.text or "", site))
        elif element.tag == "ListElementItem":
            number += 1
            label_element = element.find("label")
            if label_element is not None and has_words(label_element.text or ""):
                where = place.at_part(parts.get(id(element), ""), "List item label")
                site = Site(kind=LEGACY_SCENE, element=label_element, where=where, detail="List item label")
                found.append(
                    TextItem(
                        f"scene:{place.key}#{parts.get(id(element), '') or 'item'}.label.{number}",
                        "List Item Label",
                        label_element.text or "",
                        site,
                    )
                )
    for number, action in enumerate(scene.iter("Action")):
        found.extend(_action_items(action, f"scene:{place.key}#act{number}", place))
    return found


def _v2_items(scene: Element, place: Target) -> list[TextItem]:
    layout = scenelayout.decode_v2_layout(scene)
    if layout is None:
        return []
    found: list[TextItem] = []
    for component in scenemodel.v2_string_properties(layout, V2_TEXT):
        if not has_words(component.value):
            continue
        part = scene_component_part(component.path, component.prop)
        kind = f"{component.component_type} {component.prop.capitalize()}"
        where = place.at_part(part, f"component {component.label} {component.prop}")
        site = Site(kind=V2_SCENE, element=scene, where=where, detail=kind, path=(component.path, component.prop))
        found.append(TextItem(f"scene:{place.key}#{part}", kind, component.value, site))
    return found


# ##################################################################################
# The table
# ##################################################################################
def table_rows(items: Iterable[TextItem]) -> list[dict[str, str]]:
    """The items as rows: the last column empty, for the translation."""
    return [
        {
            "key": item.key,
            "project": item.project,
            "object": item.owner,
            "kind": item.kind,
            "text": item.text,
            "translation": "",
        }
        for item in items
    ]


def write_table(items: Iterable[TextItem], path: Path, file_format: str = CSV) -> int:
    """Write the table as CSV (opens in a spreadsheet, UTF-8 with the mark Excel needs) or JSON.  Returns how many rows."""
    rows = table_rows(items)
    if file_format == JSON:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    return len(rows)


def _clean(value: object) -> str:
    """A cell as text, with the line ends a spreadsheet writes made the one a Tasker string holds."""
    return str(value if value is not None else "").replace("\r\n", "\n").replace("\r", "\n")


def read_table(path: Path) -> list[Row]:
    """Read a table back, as written by write_table or saved from a spreadsheet.

    Raises:
        TextTableError: if the file cannot be read or has no `key`, `text` and `translation` columns.
    """
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        message = f"{path} could not be read: {error}"
        raise TextTableError(message) from error

    records: list[dict[str, object]]
    if path.suffix.lower() == ".json" or raw.lstrip().startswith(("[", "{")):
        try:
            loaded = json.loads(raw)
        except ValueError as error:
            message = f"{path} is not valid JSON: {error}"
            raise TextTableError(message) from error
        if not isinstance(loaded, list):
            message = f"{path} should hold a list of rows."
            raise TextTableError(message)
        records = [
            cast("dict[str, object]", record) for record in cast("list[object]", loaded) if isinstance(record, dict)
        ]
    else:
        reader = csv.DictReader(io.StringIO(raw, newline=""))
        records = [cast("dict[str, object]", record) for record in reader]
        missing = {"key", "text", "translation"} - set(reader.fieldnames or ())
        if missing:
            message = f"{path} has no {', '.join(sorted(missing))} column."
            raise TextTableError(message)

    return [
        Row(
            _clean(record.get("key")),
            _clean(record.get("object")),
            _clean(record.get("text")),
            _clean(record.get("translation")),
        )
        for record in records
        if record.get("key")
    ]


# ##################################################################################
# Writing it back
# ##################################################################################
def _variables(text: str) -> Counter[str]:
    """The %variables a string names, counted."""
    return Counter(VARIABLE_PATTERN.findall(text))


def _unplaced(row: Row) -> Target:
    """A place to point at for a row whose key is not in this configuration."""
    return Target(kind=TASK, key="", name=row.object or row.key)


def plan_apply(rows: Iterable[Row], state: RunState, project: str = "") -> Plan:
    """What putting these translations back would do.  Nothing is changed here.

    A row with no translation, or one the same as its text, is not a change and is not mentioned.  Every other row
    becomes a Change, or -- when it cannot be applied -- a Skip saying why.
    """
    by_key = {item.key: item for item in extract(state, project=project)}
    plan = Plan(what="Apply translated text" + (f" in Project '{project}'" if project else ""))
    for row in rows:
        if not row.translation or row.translation == row.text:
            continue
        item = by_key.get(row.key)
        if item is None:
            plan.skips.append(
                Skip(
                    _unplaced(row),
                    "unknown",
                    f"'{row.key}' is not in this configuration"
                    + (f" (or not in Project '{project}')" if project else "")
                    + ".",
                ),
            )
            continue
        if item.text != row.text:
            plan.skips.append(
                Skip(
                    item.site.where,
                    "changed",
                    f"The text is now '{item.text}', not what the table was made from ('{row.text}'); left alone.",
                ),
            )
            continue
        if _variables(row.translation) != _variables(item.text):
            plan.skips.append(
                Skip(
                    item.site.where,
                    "variables",
                    f"The translation names {_describe(_variables(row.translation))} where the text names "
                    f"{_describe(_variables(item.text))}; a translation has to keep the same %variables.",
                ),
            )
            continue
        site = Site(
            kind=item.site.kind,
            element=item.site.element,
            where=item.site.where,
            detail=item.site.detail,
            path=item.site.path,
            new_value=row.translation,
        )
        plan.changes.append(Change(site=site, before=item.text, after=row.translation))
    plan.selected = set(range(len(plan.changes)))
    return plan


def _describe(counts: Counter[str]) -> str:
    """ "%name, %city" -- or "no variables"."""
    return (
        ", ".join(f"%{name}" + (f" x{number}" if number > 1 else "") for name, number in sorted(counts.items()))
        or "no variables"
    )


def table_summary(items: list[Any]) -> str:
    """One line for what an export found."""
    owners = {item.owner for item in items}
    return f"{len(items)} piece(s) of text in {len(owners)} Task(s) and Scene(s)"


# ##################################################################################
# The two commands, as the command line runs them
# ##################################################################################
TABLE_FILE = "MapTasker_Text"
APPLIED_FILE = "MapTasker_Text_Applied"


@dataclass(frozen=True)
class Applied:
    """What putting a table back did: how many texts, what was left alone and why, and the file written."""

    changed: int
    notes: list[str]
    written: Path

    @property
    def left_alone(self) -> int:
        """How many rows were not applied."""
        return len(self.notes)


def export_table(state: RunState, project: str = "", file_format: str = CSV) -> tuple[Path, str]:
    """Write the table of the loaded configuration to the output folder.  Returns (the file, a line about it).

    Raises:
        OSError: if the file cannot be written.
    """
    items = extract(state, project=project)
    path = Path(output_path(f"{TABLE_FILE}.{file_format}", state=state))
    write_table(items, path, file_format)
    return path, table_summary(items)


def apply_table(table: Path, state: RunState, project: str = "") -> Applied:
    """Put a table's translations into the loaded configuration, and write the result to the output folder.

    The whole configuration is written as a backup, or -- with a Project -- that Project alone as a .prj.xml, the form
    to share.  The file the configuration came from is never touched.

    Raises:
        TextTableError: if the table cannot be read.
        OSError: if the result cannot be written.
    """
    plan = plan_apply(read_table(table), state, project=project)
    changed, problems = mapswap.apply(plan, state)
    notes = [f"{skip.where.label}: {skip.explanation}" for skip in plan.skips] + problems
    if project:
        xml = projedit.render_standalone_project_xml(project, state=state)
        name = f"{APPLIED_FILE}.prj.xml"
    else:
        xml = maputil2.render_full_backup_xml(state=state)
        name = f"{APPLIED_FILE}.xml"
    written = Path(output_path(name, state=state))
    written.write_text(xml, encoding="utf-8")
    return Applied(changed, notes, written)
