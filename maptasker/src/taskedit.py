"""taskedit: build an editable model of a Task and save it as a standalone .tsk.xml file.

Edit Task: edit an existing Task's name/priority and the values of arguments its
actions already have in the XML. Never touches PrimeItems.xml_tree -- all edits
happen on a deep copy, and the only output is a new standalone file.

Add Task: create a brand-new Task and populate it with newly-synthesized actions.
Only actions whose arguments are all plain numbers/text/checkboxes (or the purely
informational 'Output Variables' Bundle hint) can be synthesized from scratch --
see classify_action_addability() for the exact rule. Never touches the live tree
either; a new Task exists only in memory until saved.
"""

from __future__ import annotations

import copy
import os
import re
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import defusedxml.ElementTree

from maptasker.src.actionc import action_codes
from maptasker.src.actiont import lookup_values
from maptasker.src.primitem import PrimeItems
from maptasker.src.shelsort import shell_sort

XML_DECLARATION = '<?xml version = "1.0" encoding = "UTF-8" standalone = "no" ?>\n'


@dataclass
class EditableArg:
    """One editable (or read-only) argument belonging to an Action."""

    arg_id: str
    arg_name: str
    widget_kind: str  # "checkbox" | "dropdown" | "text" | "raw_fallback" | "readonly"
    backing_tag: str  # "Int" | "Str" | ""
    is_var: bool
    element: defusedxml.ElementTree.Element | None
    current_value: str
    dropdown_options: list[str] | None = None
    readonly_note: str = ""


@dataclass
class EditableAction:
    """One Action element and its editable arguments, in execution order."""

    action_element: defusedxml.ElementTree.Element
    act_number: int
    code: str
    action_name: str
    args: list[EditableArg] = field(default_factory=list)


@dataclass
class EditableTask:
    """A deep-copied Task element plus its editable-action model."""

    task_id: str
    task_element: defusedxml.ElementTree.Element
    actions: list[EditableAction] = field(default_factory=list)


def resolve_task_by_name(task_name: str) -> tuple[str, defusedxml.ElementTree.Element] | None:
    """Look up a Task's id and live XML element by its displayed name.

    Returns (task_id, live_element), or None if not found. Callers must not mutate
    the returned element directly -- go through load_task_for_edit() instead.
    """
    entry = PrimeItems.tasker_root_elements["all_tasks_by_name"].get(task_name)
    if entry is None:
        return None
    return entry["id"], entry["xml"]


def load_task_for_edit(task_name: str) -> EditableTask | None:
    """Resolve a Task by name, deep-copy it, and build its editable-action model.

    This is the one point of contact with the live tree -- everything downstream
    (including Save) operates on the copy, so the in-memory backup is never touched.
    """
    resolved = resolve_task_by_name(task_name)
    if resolved is None:
        return None
    task_id, live_element = resolved
    task_copy = copy.deepcopy(live_element)
    return EditableTask(
        task_id=task_id,
        task_element=task_copy,
        actions=_build_editable_actions(task_copy),
    )


def create_new_task(name: str, priority: str) -> EditableTask | str:
    """Build a brand-new Task element, not tied to any existing one, ready for
    actions to be added to it. Returns an error message string if no backup is
    loaded -- needed both to generate a collision-free id and to source the correct
    Element class (see write_standalone_task_xml's note on class mismatches).
    """
    if PrimeItems.xml_root is None:
        return "Load a Tasker backup file first (Add Task needs it to generate a unique Task ID)."

    existing_ids = [int(k) for k in PrimeItems.tasker_root_elements.get("all_tasks", {}) if k.isdigit()]
    new_id = max(existing_ids, default=0) + 1

    element_cls = type(PrimeItems.xml_root)
    task_element = element_cls("Task", {"sr": f"task{new_id}"})

    now_millis = str(int(time.time() * 1000))
    for tag, text in (
        ("cdate", now_millis),
        ("edate", now_millis),
        ("id", str(new_id)),
        ("nme", name.strip()),
        ("pri", priority.strip() or "100"),
    ):
        child = element_cls(tag)
        child.text = text
        task_element.append(child)

    return EditableTask(task_id=str(new_id), task_element=task_element, actions=[])


def add_action_to_task(edited_task: EditableTask, action_key: str) -> EditableAction | list[str]:
    """Synthesize a new Action element from scratch and append it to the task.

    Re-checks addability even though the UI shouldn't offer a non-addable action --
    defense in depth, matching apply_edits_to_task's list[str]-errors convention.
    """
    addable, reason = classify_action_addability(action_key)
    if not addable:
        return [reason or f"'{action_key}' is not addable."]

    code = action_key[:-1]
    action_code = action_codes[action_key]
    effective_args = action_codes[action_code.redirect].args if action_code.redirect else action_code.args

    act_number = len(edited_task.actions)
    element_cls = type(edited_task.task_element)

    action_element = element_cls("Action", {"sr": f"act{act_number}", "ve": "7"})
    code_element = element_cls("code")
    code_element.text = code
    action_element.append(code_element)

    args = []
    for arg in effective_args:
        editable_arg = _build_default_arg(arg)
        if editable_arg is None:
            continue  # Output Variables Bundle, or an unsupported category (shouldn't occur here).

        if editable_arg.backing_tag == "Int":
            element = element_cls("Int", {"sr": f"arg{arg.arg_id}", "val": editable_arg.current_value or "0"})
        else:  # "Str"
            element = element_cls("Str", {"sr": f"arg{arg.arg_id}", "ve": "3"})
            element.text = ""
        action_element.append(element)
        editable_arg.element = element
        args.append(editable_arg)

    edited_task.task_element.append(action_element)

    new_action = EditableAction(
        action_element=action_element,
        act_number=act_number,
        code=code,
        action_name=action_code.name,
        args=args,
    )
    edited_task.actions.append(new_action)
    return new_action


def remove_action_from_task(edited_task: EditableTask, act_number: int) -> None:
    """Remove an action (by its current act_number) from both the XML and the
    model, then renumber every remaining action's sr="actN" contiguously from 0 in
    their current order (append order, already correct -- actions are never
    reordered, only appended/removed).
    """
    target = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if target is None:
        return

    edited_task.task_element.remove(target.action_element)
    edited_task.actions = [a for a in edited_task.actions if a is not target]

    for new_number, action in enumerate(edited_task.actions):
        action.action_element.set("sr", f"act{new_number}")
        action.act_number = new_number


def _build_editable_actions(task_copy: defusedxml.ElementTree.Element) -> list[EditableAction]:
    """Find the Task's Actions, sort them into execution order, and build their arg models.

    Execution order is driven by the numeric suffix of sr="actN", not document order
    (Tasker itself writes actions out-of-order in the file), so reuse the same sort
    tasks.get_actions() uses to keep this dialog's ordering identical to the rest of
    the app's views.
    """
    actions = task_copy.findall("Action")
    shell_sort(actions, True, False)

    editable_actions = []
    for action_element in actions:
        code_element = action_element.find("code")
        code = code_element.text if code_element is not None else ""
        act_number = _action_number(action_element)

        action_code = action_codes.get(f"{code}t")
        if action_code is None:
            editable_actions.append(
                EditableAction(
                    action_element=action_element,
                    act_number=act_number,
                    code=code,
                    action_name=f"Code {code} not yet mapped",
                    args=[],
                ),
            )
            continue

        effective_args = action_codes[action_code.redirect].args if action_code.redirect else action_code.args

        editable_actions.append(
            EditableAction(
                action_element=action_element,
                act_number=act_number,
                code=code,
                action_name=action_code.name,
                args=_build_editable_args(action_element, effective_args),
            ),
        )

    return editable_actions


def _action_number(action_element: defusedxml.ElementTree.Element) -> int:
    """Extract the numeric suffix of sr="actN" for display/sort purposes only."""
    sr = action_element.attrib.get("sr", "")
    match = re.search(r"\d+$", sr)
    return int(match.group()) if match else 0


def _build_editable_args(
    action_element: defusedxml.ElementTree.Element,
    effective_args: list,
) -> list[EditableArg]:
    """Classify each of an action's defined arguments into a widget kind, bound to
    whatever Int/Str element already exists in the XML for it (never synthesized).
    """
    editable_args = []
    for arg in effective_args:
        the_arg = f"arg{arg.arg_id}"
        category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")

        if category == "Boolean":
            editable_args.append(_build_boolean_arg(action_element, the_arg, arg))
        elif category == "Int":
            editable_args.append(_build_int_arg(action_element, the_arg, arg))
        elif category in ("String", "Str"):
            editable_args.append(_build_string_arg(action_element, the_arg, arg))
        else:
            editable_args.append(
                _readonly_arg(arg, f"'{category or arg.arg_type}' arguments are not editable in this version."),
            )

    return editable_args


def _find_int_element(action_element: defusedxml.ElementTree.Element, the_arg: str) -> defusedxml.ElementTree.Element | None:
    return action_element.find(f"./Int[@sr='{the_arg}']")


def _find_str_element(action_element: defusedxml.ElementTree.Element, the_arg: str) -> defusedxml.ElementTree.Element | None:
    return next(
        (child for child in action_element.findall("Str") if child.attrib.get("sr") == the_arg),
        None,
    )


def _readonly_arg(arg, note: str) -> EditableArg:
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=arg.arg_name,
        widget_kind="readonly",
        backing_tag="",
        is_var=False,
        element=None,
        current_value="",
        readonly_note=note,
    )


def _lookup_key(arg) -> str | None:
    """If this arg's eval is ['prefix', 'l', lookupkey], return the lookup key."""
    if isinstance(arg.arg_eval, list) and len(arg.arg_eval) > 2 and arg.arg_eval[1] == "l":  # noqa: PLR2004
        return arg.arg_eval[2]
    return None


def _classify_arg_widget(arg) -> tuple[str, str, list[str] | None]:
    """Pure schema classification of an ArgumentCode -- no XML/value involved.

    Returns (widget_kind, backing_tag, dropdown_options). Shared between reading an
    existing arg's value (Edit Task) and seeding a default for a brand-new one (Add
    Task); value-sourcing details that only make sense for an *existing* element
    (e.g. a var-backed Int downgrading a dropdown to raw_fallback) stay in the
    individual _build_*_arg functions rather than here.
    """
    category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")

    if category == "Boolean":
        return "checkbox", "Int", None
    if category == "Int":
        lookup_key = _lookup_key(arg)
        if lookup_key is not None and lookup_key in lookup_values:
            return "dropdown", "Int", lookup_values[lookup_key]
        return "text", "Int", None
    if category in ("String", "Str"):
        widget_kind = "text" if isinstance(arg.arg_eval, str) else "raw_fallback"
        return widget_kind, "Str", None
    return "readonly", "", None


def _build_boolean_arg(action_element: defusedxml.ElementTree.Element, the_arg: str, arg) -> EditableArg:
    int_element = _find_int_element(action_element, the_arg)
    if int_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")
    widget_kind, backing_tag, _ = _classify_arg_widget(arg)
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=arg.arg_name,
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=int_element,
        current_value=int_element.attrib.get("val", "0"),
    )


def _build_int_arg(action_element: defusedxml.ElementTree.Element, the_arg: str, arg) -> EditableArg:
    int_element = _find_int_element(action_element, the_arg)
    if int_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    var_element = int_element.find("var")
    is_var = var_element is not None
    raw_value = var_element.text or "" if is_var else int_element.attrib.get("val", "")

    widget_kind, backing_tag, dropdown_options = _classify_arg_widget(arg)

    if widget_kind == "dropdown":
        if is_var:
            # A formula, not an index -- can't safely represent it as a dropdown.
            return EditableArg(
                arg_id=arg.arg_id,
                arg_name=arg.arg_name,
                widget_kind="raw_fallback",
                backing_tag="Int",
                is_var=True,
                element=int_element,
                current_value=raw_value,
                readonly_note="Variable expression -- edited as raw text.",
            )
        return EditableArg(
            arg_id=arg.arg_id,
            arg_name=arg.arg_name,
            widget_kind="dropdown",
            backing_tag="Int",
            is_var=False,
            element=int_element,
            current_value=raw_value or "0",
            dropdown_options=dropdown_options,
        )

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=arg.arg_name,
        widget_kind="text",
        backing_tag=backing_tag,
        is_var=is_var,
        element=int_element,
        current_value=raw_value,
    )


def _build_string_arg(action_element: defusedxml.ElementTree.Element, the_arg: str, arg) -> EditableArg:
    str_element = _find_str_element(action_element, the_arg)
    if str_element is None:
        return _readonly_arg(arg, "Not present in this action's XML.")

    widget_kind, backing_tag, _ = _classify_arg_widget(arg)
    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=arg.arg_name,
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=str_element,
        current_value=str_element.text or "",
    )


def _build_default_arg(arg) -> EditableArg | None:
    """Seed a default EditableArg for a brand-new action being synthesized (Add Task).

    Returns None for any Bundle-category arg -- on an addable action (see
    classify_action_addability) the only Bundle that can appear is the informational
    'Output Variables' hint, which is safe to omit entirely (no row, no element
    written) -- and for any other unsupported category (defense in depth; the action
    shouldn't have been offered as addable if this is reached). The returned arg's
    `element` is left None -- add_action_to_task() builds and attaches the real XML
    element afterward, keeping this function pure/schema-only.
    """
    category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")
    if category == "Bundle":
        return None

    widget_kind, backing_tag, dropdown_options = _classify_arg_widget(arg)
    if widget_kind == "readonly":
        return None

    if widget_kind in ("checkbox", "dropdown"):
        current_value = "0"
    else:  # "text" or "raw_fallback"
        current_value = "0" if backing_tag == "Int" else ""

    return EditableArg(
        arg_id=arg.arg_id,
        arg_name=arg.arg_name,
        widget_kind=widget_kind,
        backing_tag=backing_tag,
        is_var=False,
        element=None,
        current_value=current_value,
        dropdown_options=dropdown_options,
    )


_SAFE_CATEGORIES = ("Int", "Str", "String", "Boolean")


def classify_action_addability(action_key: str) -> tuple[bool, str]:
    """Whether a real numeric Task-action key (e.g. '104t') can be synthesized from
    scratch, and why not if not.

    Only args that are plain numbers/text/checkboxes, or the informational 'Output
    Variables' Bundle hint, can be safely synthesized; anything else (App/Icon/Image
    pickers, or a Bundle that's actually an opaque third-party plugin payload) has no
    generic default. Code '37' (If) is excluded separately -- its real condition
    lives in a sibling <ConditionList> this tool doesn't build.
    """
    if action_key == "37t":
        return False, "The 'If' action's condition can't be built by this tool yet."

    action_code = action_codes[action_key]
    if action_code.redirect:
        target = action_codes.get(action_code.redirect)
        if target is None:
            return False, "Unresolvable action definition."
        effective_args = target.args
    else:
        effective_args = action_code.args

    if not effective_args:
        return True, ""

    for arg in effective_args:
        category = PrimeItems.tasker_arg_specs.get(arg.arg_type, "")
        if category in _SAFE_CATEGORIES:
            continue
        if category == "Bundle" and arg.arg_name == "Output Variables":
            continue
        reason = (
            f"Requires a '{category or arg.arg_type}' value for "
            f"'{arg.arg_name or 'plugin payload'}' that this tool can't generate yet."
        )
        return False, reason

    return True, ""


_ADDABLE_ACTIONS_CACHE: list[dict] | None = None


def list_addable_actions() -> list[dict]:
    """All real numeric Task-action entries with their addability, memoized -- the
    underlying data (actionc.py, arg_specs.json, category_descriptions.json) is
    static for the process lifetime.
    """
    global _ADDABLE_ACTIONS_CACHE  # noqa: PLW0603
    if _ADDABLE_ACTIONS_CACHE is not None:
        return _ADDABLE_ACTIONS_CACHE

    rows = []
    for key, action_code in action_codes.items():
        if not (key.endswith("t") and key[:-1].isdigit()):
            continue  # Not a real numeric Task-action code (e.g. Scene-widget entries).
        addable, reason = classify_action_addability(key)
        category_code = action_code.category
        category_name = "Uncategorized"
        if category_code and category_code.isdigit():
            category_name = PrimeItems.tasker_category_descriptions.get(int(category_code), "Uncategorized")
        rows.append(
            {
                "action_key": key,
                "code": key[:-1],
                "name": action_code.name,
                "category_name": category_name,
                "addable": addable,
                "reason": reason,
            },
        )
    rows.sort(key=lambda row: row["name"])
    _ADDABLE_ACTIONS_CACHE = rows
    return rows


def search_addable_actions(query: str = "", category_name: str = "All") -> list[dict]:
    """Filter the memoized action list by name substring and/or exact category name."""
    query = query.strip().lower()
    rows = list_addable_actions()
    if query:
        rows = [r for r in rows if query in r["name"].lower()]
    if category_name and category_name != "All":
        rows = [r for r in rows if r["category_name"] == category_name]
    return rows


def arg_key(act_number: int, arg_id: str) -> str:
    """Key format shared with the dialog builder for arg_values dict lookups."""
    return f"act{act_number}_arg{arg_id}"


def apply_edits_to_task(
    edited_task: EditableTask,
    name_value: str,
    priority_value: str,
    arg_values: dict[str, str],
) -> list[str]:
    """Validate all fields, and only if everything's valid, mutate the task copy.

    All-or-nothing: on any validation error, nothing is mutated and the list of
    error messages is returned.
    """
    errors = []

    name_value = name_value.strip()
    if not name_value:
        errors.append("Task name cannot be empty.")

    priority_value = priority_value.strip()
    if priority_value and not priority_value.isdigit():
        errors.append("Priority must be a non-negative whole number.")

    for action in edited_task.actions:
        for arg in action.args:
            if arg.widget_kind != "text" or arg.backing_tag != "Int" or arg.is_var:
                continue
            key = arg_key(action.act_number, arg.arg_id)
            value = arg_values.get(key, "")
            if value and not value.lstrip("-").isdigit():
                errors.append(f"'{arg.arg_name}' (Action {action.act_number}) must be a whole number.")

    if errors:
        return errors

    _set_child_text(edited_task.task_element, "nme", name_value)
    if priority_value:
        _set_child_text(edited_task.task_element, "pri", priority_value)

    for action in edited_task.actions:
        for arg in action.args:
            if arg.widget_kind == "readonly" or arg.element is None:
                continue
            key = arg_key(action.act_number, arg.arg_id)
            if key not in arg_values:
                continue
            value = arg_values[key]

            if arg.widget_kind == "checkbox":
                arg.element.set("val", "1" if value in ("1", "true", "True") else "0")
            elif arg.widget_kind == "dropdown":
                index = arg.dropdown_options.index(value) if value in arg.dropdown_options else 0
                arg.element.set("val", str(index))
            elif arg.backing_tag == "Int" and arg.is_var:
                var_element = arg.element.find("var")
                var_element.text = value
            elif arg.backing_tag == "Int":
                arg.element.set("val", value)
            elif arg.backing_tag == "Str":
                arg.element.text = value

    return []


def _set_child_text(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    child = parent.find(tag)
    if child is None:
        # Match parent's actual Element class (see write_standalone_task_xml) --
        # ETW.SubElement() would build a stdlib-class child and fail parent.append().
        child = type(parent)(tag)
        parent.append(child)
    child.text = text


def _loaded_backup_dir() -> str:
    """Directory of the currently-loaded backup file, always absolute.

    PrimeItems.file_to_get is sometimes a path string and sometimes an open file
    object depending on how it was set -- handle both, mirroring frontmtr.py. Always
    resolve to an absolute path (falling back to the current directory if there's no
    file loaded) so a save never silently lands in whatever directory the process
    happens to be running from.
    """
    file_to_get = PrimeItems.file_to_get
    path = file_to_get if isinstance(file_to_get, str) else getattr(file_to_get, "name", "")
    return os.path.dirname(os.path.abspath(path)) if path else os.getcwd()


def sanitize_filename(name: str) -> str:
    """Strip characters illegal in filenames from a Task name (minimal, not a full slugify)."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "task"


def default_save_path(task_name: str) -> str:
    """Default standalone-export path: {loaded backup's directory}/{sanitized name}.tsk.xml."""
    return os.path.join(_loaded_backup_dir(), f"{sanitize_filename(task_name)}.tsk.xml")


def task_name_exists(name: str) -> bool:
    """Whether a Task with this name already exists in the currently loaded backup."""
    return name.strip() in PrimeItems.tasker_root_elements.get("all_tasks_by_name", {})


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten)."""
    return bool(output_path) and os.path.exists(output_path)


def write_standalone_task_xml(edited_task: EditableTask, output_path: str) -> None:
    """Write the edited Task as a standalone TaskerData/Task XML file, matching
    Tasker's own single-task export/import format. Raises OSError on failure.
    """
    tv = PrimeItems.xml_root.attrib.get("tv", "") if PrimeItems.xml_root is not None else ""
    task_copy = copy.deepcopy(edited_task.task_element)
    # The parsed tree's Element class isn't necessarily xml.etree.ElementTree's own
    # C-accelerated Element (defusedxml's hardened XMLParser forces the pure-Python
    # implementation) -- ET.Element()/.append() enforce an exact type match, so build
    # the wrapper using the same class the parsed elements actually are.
    root = type(task_copy)("TaskerData", {"sr": "", "dvi": "1", "tv": tv})
    root.append(task_copy)
    ETW.indent(root, space="\t")

    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(XML_DECLARATION)
        out_file.write(ETW.tostring(root, encoding="unicode"))
        out_file.write("\n")
