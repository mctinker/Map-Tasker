"""profedit: build an editable model of a Profile and save it as a standalone .prf.xml file.

Edit Profile:
  Phase 1: rename a Profile, enable/disable it (<limit>true</limit> -- see
  profiles.py's build_profile_line, which reads the same tag), and link/unlink
  its Entry (mid0) and Exit (mid1) Tasks by an existing Task's name.
  Phase 2: add/edit/delete conditions of the flat, well-known-field-set types
  (Time, Day, App, Loc).
  Phase 3: edit State/Event conditions' plugin/built-in arguments -- these reuse
  the exact same Bundle/Int/Str argument structure as Task Actions (see
  condition.py's condition_state/condition_event, which look up action_codes the
  same way Task Actions do, just with a different code suffix: "s" for State,
  "e" for Event, vs Task Actions' "t"), so this reuses taskedit.py's arg-editing
  machinery (build_editable_args/validate_arg_values/apply_arg_values) directly
  rather than duplicating it. Adding a brand-new Event or State condition from
  scratch is supported too (see list_addable_events/list_addable_states and
  add_event_condition_to_profile/add_state_condition_to_profile, which mirror
  taskedit.py's action code picker -- list_addable_actions/add_action_to_task --
  exactly, since actionc.py's "...e"/"...s"-suffixed keys share the same
  ActionCode/ArgumentCode shape as its "...t"-suffixed ones).

Add Profile: create a brand-new Profile and populate it with conditions, same
as Edit Profile's Phase 2/3 above -- see create_new_profile/register_new_profile,
which mirror taskedit.py's create_new_task/register_new_task 1:1.

Never touches PrimeItems.xml_tree -- all edits happen on a deep copy, and the
only output is a new standalone file (or, via Save To Android, a POST to the
Tasker HTTP API), mirroring taskedit.py's Task-editing design 1:1.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.maputil2 import http_post_request

if TYPE_CHECKING:
    import defusedxml.ElementTree

from maptasker.src import taskedit
from maptasker.src.actionc import action_codes
from maptasker.src.primitem import PrimeItems

XML_DECLARATION = '<?xml version = "1.0" encoding = "UTF-8" standalone = "no" ?>\n'

# Condition types offered in the GUI's "Condition Type" picker. Time/Day/App/Loc
# have simple, well-known field sets, so add_condition_to_profile can add one
# from just the type name. Event and State each need a second pick -- which
# event/state code (see list_addable_events/list_addable_states) -- since their
# fields depend on that choice, exactly like Task Actions' own code picker
# (taskedit.classify_action_addability/list_addable_actions);
# add_event_condition_to_profile/add_state_condition_to_profile handle it
# separately, the GUI showing a second "Event Type"/"State Type" picker
# alongside this one once "Event"/"State" is chosen (see build_edit_profile_dialog).
CONDITION_TYPES_ADDABLE = ("Time", "Day", "App", "Loc", "Event", "State")
# Every condition type this codebase recognizes (see condition.py's parse_profile_condition).
_CONDITION_TAGS = ("Time", "Day", "State", "Event", "App", "Loc")
# Profile children that are metadata, not conditions -- mirrors condition.py's
# ignore_items, but Share/limit are added explicitly rather than relying on
# document-order luck (see that function's own docstring caveat: without those
# two in the skip list, a Share or limit element appearing *after* a real
# condition in a given backup could get miscounted as one there).
_PROFILE_METADATA_TAGS = {"cdate", "edate", "flags", "id", "ProfileVariable", "nme", "pri", "Share", "limit"}

# 1=Sunday..7=Saturday, matching condition.py's own condition_day -- index 0 is
# unused (the day numbers are 1-based) so the GUI can index this directly by day number.
WEEKDAY_NAMES = (None, "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
# 0=January..11=December, matching condition.py's own condition_day (months[int(child.text)],
# no -1 -- unlike weekdays, months are 0-based), so index lines up directly with the mnthN value.
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
# Sentinel mdayN value Tasker uses for "Last day of the month" in its own Day
# condition UI (day-of-month is otherwise 1-31) -- not something this codebase
# had a prior reference for; verify against a real "last day of month" Tasker
# export if one becomes available.
DAY_OF_MONTH_LAST_DAY = 32
_APP_ENTRY_TAG_RE = re.compile(r"^(cls|label|pkg)(\d+)$")
# State conditions look their code up as "{code}s", Event conditions as "{code}e"
# (see condition.py's condition_state/condition_event) -- Task Actions use "t".
_CONDITION_CODE_SUFFIX = {"State": "s", "Event": "e"}


@dataclass
class EditableCondition:
    """One condition element (Time/Day/State/Event/App/Loc), in Profile document order.

    cond_index tracks its position among conditions only (-> sr="conN"), not its
    position among the Profile's other (non-condition) children.

    args is only populated for State/Event conditions (their plugin/built-in
    arguments, via taskedit.EditableArg -- see _build_condition_args); it's
    empty for the other types, which use their own dedicated field
    get/validate/write functions instead (get_time_field_values etc.).
    """

    cond_index: int
    cond_type: str
    condition_element: defusedxml.ElementTree.Element
    args: list[taskedit.EditableArg] = field(default_factory=list)


@dataclass
class EditableProfile:
    """A deep-copied Profile element, its editable-condition model, and its
    linked Entry/Exit Task ids.
    """

    profile_id: str
    profile_element: defusedxml.ElementTree.Element
    conditions: list[EditableCondition] = field(default_factory=list)
    entry_task_id: str = ""
    exit_task_id: str = ""


def resolve_profile_by_name(
    profile_name: str,
) -> tuple[str, defusedxml.ElementTree.Element] | None:
    """Look up a Profile's id and live XML element by its displayed name.

    Returns (profile_id, live_element), or None if not found. Callers must not
    mutate the returned element directly -- go through load_profile_for_edit() instead.
    """
    entry = PrimeItems.tasker_root_elements.get("all_profiles_by_name", {}).get(profile_name)
    if entry is None:
        return None
    return entry["id"], entry["xml"]


def load_profile_for_edit(profile_name: str) -> EditableProfile | None:
    """Resolve a Profile by name, deep-copy it, and build its editable-condition
    model plus its Entry/Exit Task ids.

    This is the one point of contact with the live tree -- everything downstream
    (including Save) operates on the copy, so the in-memory backup is never touched.
    """
    resolved = resolve_profile_by_name(profile_name)
    if resolved is None:
        return None
    profile_id, live_element = resolved
    profile_copy = copy.deepcopy(live_element)
    return EditableProfile(
        profile_id=profile_id,
        profile_element=profile_copy,
        conditions=_build_editable_conditions(profile_copy),
        entry_task_id=profile_copy.findtext("mid0", ""),
        exit_task_id=profile_copy.findtext("mid1", ""),
    )


def create_new_profile(name: str) -> EditableProfile | str:
    """Build a brand-new Profile element, not tied to any existing one, ready
    for conditions to be added to it -- the Profile counterpart of
    taskedit.create_new_task. Returns an error message string if no backup is
    loaded (needed both to generate a collision-free id and to source the
    correct Element class -- see taskedit.create_new_task's identical note).
    """
    if PrimeItems.xml_root is None:
        return "Load a Tasker backup file first (Add Profile needs it to generate a unique Profile ID)."

    existing_ids = [int(k) for k in PrimeItems.tasker_root_elements.get("all_profiles", {}) if k.isdigit()]
    new_id = max(existing_ids, default=0) + 1

    element_cls = type(PrimeItems.xml_root)
    profile_element = element_cls("Profile", {"sr": f"prof{new_id}", "ve": "2"})

    now_millis = str(int(time.time() * 1000))
    for tag, text in (
        ("cdate", now_millis),
        ("edate", now_millis),
        ("id", str(new_id)),
        ("nme", name.strip()),
    ):
        child = element_cls(tag)
        child.text = text
        profile_element.append(child)

    return EditableProfile(profile_id=str(new_id), profile_element=profile_element, conditions=[])


def _build_editable_conditions(profile_copy: defusedxml.ElementTree.Element) -> list[EditableCondition]:
    """Find the Profile's condition children (Time/Day/State/Event/App/Loc), in
    document order, skipping Profile metadata -- see _PROFILE_METADATA_TAGS and
    condition.py's parse_profile_condition, which this mirrors (built explicitly
    here rather than reusing that function's own iteration, whose "AND"-joining
    isn't quite what a structured per-condition list needs).
    """
    conditions = []
    cond_index = 0
    for child in profile_copy:
        if child.tag in _PROFILE_METADATA_TAGS or "mid" in child.tag or child.tag not in _CONDITION_TAGS:
            continue
        conditions.append(
            EditableCondition(
                cond_index=cond_index,
                cond_type=child.tag,
                condition_element=child,
                args=_build_condition_args(child, child.tag) if child.tag in _CONDITION_CODE_SUFFIX else [],
            ),
        )
        cond_index += 1
    return conditions


def _build_condition_args(
    condition_element: defusedxml.ElementTree.Element,
    cond_type: str,
) -> list[taskedit.EditableArg]:
    """Builds the editable-arg model for a State or Event condition's
    plugin/built-in configuration -- see the module docstring for why this
    reuses taskedit.build_editable_args directly. Returns [] if the condition's
    code isn't in action_codes (not yet mapped -- mirrors
    taskedit._build_editable_action's same fallback for an Action).
    """
    suffix = _CONDITION_CODE_SUFFIX[cond_type]
    code_element = condition_element.find("code")
    code = code_element.text if code_element is not None else ""

    action_code = action_codes.get(f"{code}{suffix}")
    if action_code is None:
        return []

    effective_args = action_codes[action_code.redirect].args if action_code.redirect else action_code.args
    return taskedit.build_editable_args(condition_element, effective_args)


def get_condition_display_name(condition: EditableCondition) -> str:
    """A short human-readable label for a condition's expansion header in the
    GUI, e.g. "Event: HTTP Request Received" instead of just "Event". Falls back
    to a "not mapped" note if the code isn't in action_codes (see
    _build_condition_args); other condition types just return their bare type name.
    """
    if condition.cond_type not in _CONDITION_CODE_SUFFIX:
        return condition.cond_type

    suffix = _CONDITION_CODE_SUFFIX[condition.cond_type]
    code_element = condition.condition_element.find("code")
    code = code_element.text if code_element is not None else ""
    action_code = action_codes.get(f"{code}{suffix}")
    if action_code is None:
        return f"{condition.cond_type} (code {code} not mapped)"
    return f"{condition.cond_type}: {action_code.name}"


def condition_arg_key(cond_index: int, arg_id: str) -> str:
    """Key format shared with the dialog builder for a State/Event condition's
    arg_values dict lookups -- mirrors taskedit.arg_key's act{N}_arg{id} format.
    """
    return f"cond{cond_index}_arg{arg_id}"


def find_condition(edited_profile: EditableProfile, cond_index: int) -> EditableCondition | None:
    """Look up a condition by its current cond_index -- a small convenience for
    event handlers that only have the index (from a button click), not the object.
    """
    return next((c for c in edited_profile.conditions if c.cond_index == cond_index), None)


def _renumber_conditions(edited_profile: EditableProfile) -> None:
    """Renumber every condition's sr="conN" (and its cond_index) to match its
    current position in edited_profile.conditions -- shared by
    add_condition_to_profile/remove_condition_from_profile.
    """
    for new_index, condition in enumerate(edited_profile.conditions):
        condition.condition_element.set("sr", f"con{new_index}")
        condition.cond_index = new_index


def remove_condition_from_profile(edited_profile: EditableProfile, cond_index: int) -> None:
    """Remove a condition (by its current cond_index) from both the XML and the
    model, then renumber every remaining condition's sr="conN" contiguously from
    0 in their current order. Works for any condition type, including the
    not-yet-editable State/Event ones.
    """
    target = find_condition(edited_profile, cond_index)
    if target is None:
        return

    edited_profile.profile_element.remove(target.condition_element)
    edited_profile.conditions = [c for c in edited_profile.conditions if c is not target]

    _renumber_conditions(edited_profile)


def add_condition_to_profile(edited_profile: EditableProfile, cond_type: str) -> EditableCondition | list[str]:
    """Synthesize a bare condition element of the given type (Time, Day, App, or
    Loc only -- see CONDITION_TYPES_ADDABLE) with sensible defaults, append it
    to the Profile, and add it to the model.

    Returns the new condition, or a list of error messages if cond_type isn't
    one of the addable types. Event and State, though also in
    CONDITION_TYPES_ADDABLE, are rejected here -- each needs a specific
    event/state code, which only add_event_condition_to_profile/
    add_state_condition_to_profile take; this is just defense in depth, since
    the GUI's "Condition Type" picker routes those picks there instead of here.
    """
    if cond_type not in CONDITION_TYPES_ADDABLE or cond_type in ("Event", "State"):
        return [f"Adding a '{cond_type}' condition isn't supported here."]

    element_cls = type(edited_profile.profile_element)
    cond_index = len(edited_profile.conditions)
    condition_element = element_cls(cond_type, {"sr": f"con{cond_index}", "ve": "2"})

    if cond_type == "Time":
        for tag in ("fh", "fm", "th", "tm"):
            child = element_cls(tag)
            child.text = "0"
            condition_element.append(child)
    elif cond_type == "App":
        flags_child = element_cls("flags")
        flags_child.text = "2"
        condition_element.append(flags_child)
    elif cond_type == "Loc":
        for tag in ("lat", "long", "rad"):
            child = element_cls(tag)
            child.text = ""
            condition_element.append(child)
    # Day starts with no weekdays selected -- the user checks some, then Saves.

    edited_profile.profile_element.append(condition_element)

    new_condition = EditableCondition(
        cond_index=cond_index,
        cond_type=cond_type,
        condition_element=condition_element,
    )
    edited_profile.conditions.append(new_condition)

    _renumber_conditions(edited_profile)
    return new_condition


_ADDABLE_CONDITION_CODES_CACHE: dict[str, list[dict]] = {}


def _list_addable_condition_codes(suffix: str) -> list[dict]:
    """All real numeric Profile-condition entries for a given actionc.py key
    suffix -- "e" for Event (e.g. "1000e"), "s" for State (e.g. "100s") --
    matching condition.py's condition_event/condition_state, whose own
    f"{code}{suffix}" lookups this mirrors -- with their addability, memoized
    per suffix like taskedit.list_addable_actions (same underlying static
    data). Reuses taskedit.classify_action_addability as-is: it's keyed by the
    raw action_codes key regardless of the t/s/e suffix, and its own special
    handling for the Task-only "If" action (see taskedit.IF_ACTION_KEY) is
    keyed on the literal "37t" suffix, which never matches an event/state key.
    """
    cached = _ADDABLE_CONDITION_CODES_CACHE.get(suffix)
    if cached is not None:
        return cached

    rows = []
    for key, action_code in action_codes.items():
        if not (key.endswith(suffix) and key[:-1].isdigit()):
            continue  # Not a real numeric code for this condition type (e.g. a Task-action entry).
        addable, reason = taskedit.classify_action_addability(key)
        category_code = action_code.category
        category_name = "Uncategorized"
        if category_code and category_code.isdigit():
            category_name = PrimeItems.tasker_category_descriptions.get(int(category_code), "Uncategorized")
        rows.append(
            {
                "condition_key": key,
                "code": key[:-1],
                "name": action_code.name,
                "category_name": category_name,
                "addable": addable,
                "reason": reason,
            },
        )
    rows.sort(key=lambda row: row["name"])
    _ADDABLE_CONDITION_CODES_CACHE[suffix] = rows
    return rows


def list_addable_events() -> list[dict]:
    """All real numeric Profile-Event condition entries (actionc.py keys ending
    in "e") with their addability -- see _list_addable_condition_codes.
    """
    return _list_addable_condition_codes("e")


def list_addable_states() -> list[dict]:
    """All real numeric Profile-State condition entries (actionc.py keys ending
    in "s") with their addability -- see _list_addable_condition_codes.
    """
    return _list_addable_condition_codes("s")


def _add_code_condition_to_profile(
    edited_profile: EditableProfile,
    cond_type: str,
    condition_key: str,
    *,
    include_pri: bool,
) -> EditableCondition | list[str]:
    """Synthesize a brand-new Event or State condition element from an
    actionc.py condition key (e.g. "1000e" or "100s", see
    list_addable_events/list_addable_states), append it to the Profile, and
    add it to the model -- the Event/State counterpart of
    add_condition_to_profile's Time/Day/App/Loc handling, kept separate
    because their own fields (arbitrary Int/Str args) depend on which code was
    picked, exactly like taskedit.add_action_to_task for a Task Action; this
    reuses that same Bundle/Int/Str synthesis (taskedit.build_synthesized_args)
    directly. include_pri writes <pri>0</pri> for Event (matching every real
    Event condition's own shape -- see condition.py's condition_event, which
    always reads a pri element); State conditions have no such element (see
    condition.py's condition_state).

    Re-checks addability even though the UI shouldn't offer a non-addable
    code -- defense in depth, matching apply_edits_to_profile's list[str]
    errors convention.

    Returns the new condition, or a list of error messages if condition_key
    isn't a real, addable code.
    """
    addable, reason = taskedit.classify_action_addability(condition_key)
    if not addable:
        return [reason or f"'{condition_key}' is not addable."]

    action_code = action_codes[condition_key]
    effective_args = action_codes[action_code.redirect].args if action_code.redirect else action_code.args

    cond_index = len(edited_profile.conditions)
    element_cls = type(edited_profile.profile_element)

    condition_element = element_cls(cond_type, {"sr": f"con{cond_index}", "ve": "2"})
    code_element = element_cls("code")
    code_element.text = condition_key[:-1]
    condition_element.append(code_element)
    if include_pri:
        pri_element = element_cls("pri")
        pri_element.text = "0"
        condition_element.append(pri_element)

    args = taskedit.build_synthesized_args(element_cls, condition_element, effective_args)

    edited_profile.profile_element.append(condition_element)

    new_condition = EditableCondition(
        cond_index=cond_index,
        cond_type=cond_type,
        condition_element=condition_element,
        args=args,
    )
    edited_profile.conditions.append(new_condition)

    _renumber_conditions(edited_profile)
    return new_condition


def add_event_condition_to_profile(edited_profile: EditableProfile, event_key: str) -> EditableCondition | list[str]:
    """Add a new Event condition from an actionc.py event key (e.g. "1000e") --
    see _add_code_condition_to_profile.
    """
    return _add_code_condition_to_profile(edited_profile, "Event", event_key, include_pri=True)


def add_state_condition_to_profile(edited_profile: EditableProfile, state_key: str) -> EditableCondition | list[str]:
    """Add a new State condition from an actionc.py state key (e.g. "100s") --
    see _add_code_condition_to_profile.
    """
    return _add_code_condition_to_profile(edited_profile, "State", state_key, include_pri=False)


def _set_profile_task_link(profile_element: defusedxml.ElementTree.Element, tag: str, task_id: str) -> None:
    """Sets a Profile's mid0 (Entry Task) or mid1 (Exit Task) child to task_id,
    inserting a brand-new one in the position real Tasker backups always use --
    before <nme> -- rather than _set_child_text's default of appending at the
    very end.

    profiles.get_profile_tasks walks a Profile's children looking for "mid*"
    tags and stops as soon as it hits <nme>, on the assumption that any
    mid0/mid1 already appeared by then -- true of every Profile Tasker itself
    ever writes (mid0/mid1 always precede <nme> there). But a Profile only
    gets <nme> appended once, at creation (create_new_profile), while its
    Entry/Exit Task is often linked in afterward -- appending mid0/mid1 after
    an already-present <nme> would make that walk stop before ever reaching
    it, silently dropping the Task from the Map view's Task list and Directory
    (see dirout.add_directory_item, called from within that same walk).
    """
    child = profile_element.find(tag)
    if child is not None:
        child.text = task_id
        return
    child = type(profile_element)(tag)
    child.text = task_id
    nme_element = profile_element.find("nme")
    if nme_element is not None:
        profile_element.insert(list(profile_element).index(nme_element), child)
    else:
        profile_element.append(child)


def link_task_to_profile(edited_profile: EditableProfile, task_id: str, link_type: str) -> None:
    """Sets the Profile's Entry (mid0) or Exit (mid1) Task reference to task_id,
    replacing whatever was linked there before. link_type is "Entry" or "Exit",
    matching profiles.py's own tag-based discriminator (mid1=Exit, anything else
    matching "mid" i.e. mid0=Entry).
    """
    tag = "mid1" if link_type == "Exit" else "mid0"
    _set_profile_task_link(edited_profile.profile_element, tag, task_id)
    if link_type == "Exit":
        edited_profile.exit_task_id = task_id
    else:
        edited_profile.entry_task_id = task_id


def unlink_task_from_profile(edited_profile: EditableProfile, link_type: str) -> None:
    """Removes the Profile's Entry (mid0) or Exit (mid1) Task reference entirely --
    unlinks the Task from this Profile without deleting the Task itself (Tasks are
    independently addressable and may still be referenced elsewhere).
    """
    tag = "mid1" if link_type == "Exit" else "mid0"
    child = edited_profile.profile_element.find(tag)
    if child is not None:
        edited_profile.profile_element.remove(child)
    if link_type == "Exit":
        edited_profile.exit_task_id = ""
    else:
        edited_profile.entry_task_id = ""


def is_profile_enabled(edited_profile: EditableProfile) -> bool:
    """Whether this Profile is enabled -- mirrors profiles.py's own
    build_profile_line, which treats a <limit>true</limit> child as "disabled"
    and its absence (or any other text) as "enabled".
    """
    limit = edited_profile.profile_element.find("limit")
    return limit is None or limit.text != "true"


def set_profile_enabled(edited_profile: EditableProfile, enabled: bool) -> None:
    """Enables or disables the Profile by removing/setting its <limit> child --
    applied immediately (not staged), same as link_task_to_profile/
    unlink_task_from_profile above.
    """
    if enabled:
        limit = edited_profile.profile_element.find("limit")
        if limit is not None:
            edited_profile.profile_element.remove(limit)
    else:
        _set_child_text(edited_profile.profile_element, "limit", "true")


def apply_edits_to_profile(
    edited_profile: EditableProfile,
    name_value: str,
    condition_values: dict[str, str],
) -> list[str]:
    """Validate all fields, and only if everything's valid, mutate the profile copy.

    All-or-nothing: on any validation error, nothing is mutated and the list of
    error messages is returned. Whole-condition Add/Delete
    (add_condition_to_profile/remove_condition_from_profile), Task linking
    (link_task_to_profile/unlink_task_from_profile), and an App condition's
    entry count (add_app_entry/remove_app_entry) are all applied immediately
    when clicked, not staged here -- this only covers the name and each
    condition's field *values*, keyed condition_field_key(cond_index, ...) (or,
    for State/Event, condition_arg_key(cond_index, arg_id)).
    """
    errors = []

    name_value = name_value.strip()
    if not name_value:
        errors.append("Profile name cannot be empty.")

    # Validate every condition's pending values before mutating anything.
    pending: dict[int, tuple[str, object]] = {}
    for condition in edited_profile.conditions:
        if condition.cond_type == "Time":
            values = {
                key: condition_values.get(condition_field_key(condition.cond_index, key), "") for key in _TIME_FIELDS
            }
            field_errors = _validate_time_field_values(values)
            errors.extend(field_errors)
            if not field_errors:
                pending[condition.cond_index] = ("Time", values)

        elif condition.cond_type == "Loc":
            values = {
                key: condition_values.get(condition_field_key(condition.cond_index, key), "") for key in _LOC_FIELDS
            }
            field_errors = _validate_loc_field_values(values)
            errors.extend(field_errors)
            if not field_errors:
                pending[condition.cond_index] = ("Loc", values)

        elif condition.cond_type == "Day":
            selected_weekdays = [
                day
                for day in range(1, 8)
                if condition_values.get(condition_field_key(condition.cond_index, f"wday{day}"))
                in ("1", "true", "True")
            ]
            selected_months = [
                month
                for month in range(12)
                if condition_values.get(condition_field_key(condition.cond_index, f"mnth{month}"))
                in ("1", "true", "True")
            ]
            selected_month_days = [
                day
                for day in (*range(1, 32), DAY_OF_MONTH_LAST_DAY)
                if condition_values.get(condition_field_key(condition.cond_index, f"mday{day}"))
                in ("1", "true", "True")
            ]
            pending[condition.cond_index] = ("Day", (selected_weekdays, selected_months, selected_month_days))

        elif condition.cond_type == "App":
            entries = [
                {
                    key: condition_values.get(condition_field_key(condition.cond_index, f"app{i}_{key}"), "")
                    for key in ("pkg", "label", "cls")
                }
                for i in range(len(get_app_entries(condition)))
            ]
            field_errors = _validate_app_entries(entries)
            errors.extend(field_errors)
            if not field_errors:
                pending[condition.cond_index] = ("App", entries)

        elif condition.cond_type in _CONDITION_CODE_SUFFIX and condition.args:
            field_errors = taskedit.validate_arg_values(
                condition.args,
                lambda arg, ci=condition.cond_index: condition_arg_key(ci, arg.arg_id),
                condition_values,
            )
            errors.extend(f"{error} ({condition.cond_type} condition {condition.cond_index})" for error in field_errors)
            if not field_errors:
                pending[condition.cond_index] = ("StateEvent", None)

    if errors:
        return errors

    _set_child_text(edited_profile.profile_element, "nme", name_value)

    for condition in edited_profile.conditions:
        update = pending.get(condition.cond_index)
        if update is None:
            continue
        cond_type, payload = update
        if cond_type == "Time":
            _write_time_field_values(condition, payload)
        elif cond_type == "Loc":
            _write_loc_field_values(condition, payload)
        elif cond_type == "Day":
            weekdays, months, month_days = payload
            _write_day_selected_weekdays(condition, weekdays)
            _write_day_selected_months(condition, months)
            _write_day_selected_month_days(condition, month_days)
        elif cond_type == "App":
            _write_app_entries(condition, payload)
        elif cond_type == "StateEvent":
            taskedit.apply_arg_values(
                condition.args,
                lambda arg, ci=condition.cond_index: condition_arg_key(ci, arg.arg_id),
                condition_values,
            )

    return []


def _set_child_text(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    child = parent.find(tag)
    if child is None:
        # Match parent's actual Element class (see render_standalone_profile_xml) --
        # ETW.SubElement() would build a stdlib-class child and fail parent.append().
        child = type(parent)(tag)
        parent.append(child)
    child.text = text


def condition_field_key(cond_index: int, field_name: str) -> str:
    """Key format shared with the dialog builder for condition_values dict lookups."""
    return f"cond{cond_index}_{field_name}"


# --- Time condition (fields: fh/fm=From Hour/Minute, th/tm=To Hour/Minute,
# packaged for the GUI as a single Start Time / End Time each. Each of those can
# hold EITHER a literal "hh:mm AM/PM" 12-hour time OR a "%variable" reference
# (Tasker's own Time condition UI offers the same either/or choice, backed by
# fromvar/tovar -- see condition.py's condition_time, whose
# from_time-vs-from_variable branching this mirrors) -- a %-prefixed value is
# stored in fromvar/tovar instead, and whichever form isn't in use is removed so
# the condition isn't left with both a literal time and a variable set at once.
# The XML itself (fh/fm/th/tm) always stores 24-hour hour/minute -- the
# AM/PM-suffixed form is purely a GUI display/entry convenience, converted at the
# boundary (get_time_field_values / _write_time_or_var). rep/repval (repeat
# interval, "Every" in the GUI) is also editable here. cname (condition name)
# exists in the XML but isn't edited here -- left untouched if already present.
_TIME_FIELDS = ("start_time", "end_time", "rep_unit", "rep_value")
# 12-hour clock: hour 1-12 (optionally zero-padded), minute 00-59, AM/PM suffix
# (with or without a space before it, either case) -- e.g. "8:05am", "08:05 AM".
_TIME_HHMM_RE = re.compile(r"^(0?[1-9]|1[0-2]):([0-5]\d)\s*([AaPp][Mm])$")
_TIME_VAR_RE = re.compile(r"^%\S+$")


def _int_or_zero(text: str | None) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _format_12_hour(hour_24: int, minute: int) -> str:
    """Formats a 24-hour hour/minute pair as a 12-hour "hh:mm AM/PM" string."""
    period = "AM" if hour_24 < 12 else "PM"
    hour_12 = hour_24 % 12 or 12
    return f"{hour_12:02d}:{minute:02d} {period}"


def _classify_time_or_var(raw: str) -> tuple[str, str] | None:
    """Classifies a Start/End Time field's raw input as either a literal
    12-hour "hh:mm AM/PM" time or a "%variable" reference -- also the point
    where a valid time of day is enforced (hour 1-12, minute 00-59, a
    recognizable AM/PM suffix). Returns ("time", "hh:mm AM/PM") normalized to
    a zero-padded hour and upper-case suffix, ("var", "%name"), or None if raw
    is neither.
    """
    raw = raw.strip()
    if raw.startswith("%"):
        return ("var", raw) if _TIME_VAR_RE.match(raw) else None
    match = _TIME_HHMM_RE.match(raw)
    if not match:
        return None
    hour, minute, period = match.groups()
    return ("time", f"{int(hour):02d}:{minute} {period.upper()}")


def get_time_field_values(condition: EditableCondition) -> dict[str, str]:
    """Reads a Time condition's Start/End time and repeat-interval ("Every")
    fields for display. start_time/end_time are either "hh:mm AM/PM" 12-hour
    strings (built from fh/fm and th/tm) or, if fromvar/tovar is set instead,
    that variable's name verbatim (e.g. "%myTimeVar"). rep_unit is "Minutes" if
    rep == "2", else "Hours" (matching condition.py's own condition_time);
    rep_value is the raw repval text, or "" if there's no repeat set.
    """
    element = condition.condition_element

    def start_or_end(var_tag: str, hour_tag: str, minute_tag: str) -> str:
        variable = element.findtext(var_tag, "")
        if variable:
            return variable
        hour, minute = _int_or_zero(element.findtext(hour_tag)), _int_or_zero(element.findtext(minute_tag))
        return _format_12_hour(hour, minute)

    return {
        "start_time": start_or_end("fromvar", "fh", "fm"),
        "end_time": start_or_end("tovar", "th", "tm"),
        "rep_unit": "Minutes" if element.findtext("rep", "") == "2" else "Hours",
        "rep_value": element.findtext("repval", "") or "",
    }


def _validate_time_field_values(values: dict[str, str]) -> list[str]:
    errors = []
    for key, label in (("start_time", "Start Time"), ("end_time", "End Time")):
        if _classify_time_or_var(values.get(key, "")) is None:
            errors.append(f"'{label}' must be a valid time of day (hh:mm AM/PM) or a %variable.")

    rep_value_raw = values.get("rep_value", "").strip()
    if rep_value_raw:
        if not rep_value_raw.isdigit() or int(rep_value_raw) <= 0:
            errors.append("'Every' must be a positive whole number, or blank for no repeat.")
        if values.get("rep_unit", "") not in ("Hours", "Minutes"):
            errors.append("'Every' unit must be Hours or Minutes.")

    return errors


def _write_time_or_var(
    element: defusedxml.ElementTree.Element,
    raw_value: str,
    var_tag: str,
    hour_tag: str,
    minute_tag: str,
) -> None:
    kind, parsed = _classify_time_or_var(raw_value)
    if kind == "var":
        _set_child_text(element, var_tag, parsed)
        for tag in (hour_tag, minute_tag):
            child = element.find(tag)
            if child is not None:
                element.remove(child)
    else:
        hhmm, period = parsed.rsplit(" ", 1)
        hour_12, minute = (int(part) for part in hhmm.split(":"))
        hour_24 = (hour_12 % 12) + (12 if period == "PM" else 0)
        _set_child_text(element, hour_tag, str(hour_24))
        _set_child_text(element, minute_tag, str(minute))
        var_child = element.find(var_tag)
        if var_child is not None:
            element.remove(var_child)


def _write_time_field_values(condition: EditableCondition, values: dict[str, str]) -> None:
    element = condition.condition_element
    _write_time_or_var(element, values["start_time"], "fromvar", "fh", "fm")
    _write_time_or_var(element, values["end_time"], "tovar", "th", "tm")

    rep_value_raw = values.get("rep_value", "").strip()
    if rep_value_raw:
        _set_child_text(element, "rep", "2" if values.get("rep_unit") == "Minutes" else "1")
        _set_child_text(element, "repval", str(int(rep_value_raw)))
    else:
        for tag in ("rep", "repval"):
            child = element.find(tag)
            if child is not None:
                element.remove(child)


# --- Loc condition (fields: lat/long=latitude/longitude in decimal degrees, rad=radius in meters) ---
_LOC_FIELDS = ("lat", "long", "rad")


def get_loc_field_values(condition: EditableCondition) -> dict[str, str]:
    """Reads a Loc condition's latitude/longitude/radius fields for display."""
    element = condition.condition_element
    return {key: element.findtext(key, "") for key in _LOC_FIELDS}


def _validate_loc_field_values(values: dict[str, str]) -> list[str]:
    labels = {"lat": "Latitude", "long": "Longitude", "rad": "Radius"}
    errors = []
    for key, label in labels.items():
        raw = values.get(key, "").strip()
        if not raw:
            errors.append(f"'{label}' cannot be empty.")
            continue
        try:
            number = float(raw)
        except ValueError:
            errors.append(f"'{label}' must be a number.")
            continue
        if key == "rad" and number < 0:
            errors.append("'Radius' must not be negative.")
    return errors


def _write_loc_field_values(condition: EditableCondition, values: dict[str, str]) -> None:
    for key in _LOC_FIELDS:
        _set_child_text(condition.condition_element, key, values[key].strip())


# --- Day condition: three independent sub-selections -- Week-Day (wdayN,
# 1=Sunday..7=Saturday), Month (mnthN, 0=January..11=December), and Day of Month
# (mdayN, 1-31 or DAY_OF_MONTH_LAST_DAY) -- matching condition.py's own
# condition_day. cname (condition name) exists in the XML but isn't edited here
# -- left untouched if present. All three follow the same shape: a tag-prefix
# family of sequentially-indexed elements (mdayN's N is just its position, not
# its value -- see the real "18"/"21" example this mirrors) whose text holds the
# actual selected value, so a single generic helper pair backs all three.
def _get_day_selected_values(condition: EditableCondition, tag_prefix: str) -> list[int]:
    selected = []
    for child in condition.condition_element:
        if child.tag.startswith(tag_prefix) and child.text:
            try:
                selected.append(int(child.text))
            except ValueError:
                continue
    return sorted(set(selected))


def _write_day_selected_values(condition: EditableCondition, tag_prefix: str, selected: list[int]) -> None:
    element = condition.condition_element
    for child in [c for c in element if c.tag.startswith(tag_prefix)]:
        element.remove(child)

    element_cls = type(element)
    for index, value in enumerate(sorted(set(selected))):
        child = element_cls(f"{tag_prefix}{index}")
        child.text = str(value)
        element.append(child)


def get_day_selected_weekdays(condition: EditableCondition) -> list[int]:
    """Reads a Day condition's selected weekdays (1=Sunday..7=Saturday) for display."""
    return _get_day_selected_values(condition, "wday")


def _write_day_selected_weekdays(condition: EditableCondition, selected: list[int]) -> None:
    _write_day_selected_values(condition, "wday", selected)


def get_day_selected_months(condition: EditableCondition) -> list[int]:
    """Reads a Day condition's selected months (0=January..11=December) for display."""
    return _get_day_selected_values(condition, "mnth")


def _write_day_selected_months(condition: EditableCondition, selected: list[int]) -> None:
    _write_day_selected_values(condition, "mnth", selected)


def get_day_selected_month_days(condition: EditableCondition) -> list[int]:
    """Reads a Day condition's selected days-of-month (1-31, or
    DAY_OF_MONTH_LAST_DAY for "Last Day Of Month") for display.
    """
    return _get_day_selected_values(condition, "mday")


def _write_day_selected_month_days(condition: EditableCondition, selected: list[int]) -> None:
    _write_day_selected_values(condition, "mday", selected)


# --- App condition (repeatable app entries: clsN=Activity class, labelN=display
# name, pkgN=package name, matched by index N) -- flags (match state, e.g. "any
# state" vs specific) exists in the XML but isn't edited by Phase 2.
def get_app_entries(condition: EditableCondition) -> list[dict[str, str]]:
    """Reads an App condition's list of app entries (matched clsN/labelN/pkgN
    triples, by index) for display.
    """
    element = condition.condition_element
    entries: dict[int, dict[str, str]] = {}
    for child in element:
        match = _APP_ENTRY_TAG_RE.match(child.tag)
        if match:
            prefix, index = match.group(1), int(match.group(2))
            entries.setdefault(index, {"cls": "", "label": "", "pkg": ""})[prefix] = child.text or ""
    return [entries[index] for index in sorted(entries)]


def _validate_app_entries(entries: list[dict[str, str]]) -> list[str]:
    return [
        f"App entry {i + 1} needs a Package name."
        for i, entry in enumerate(entries)
        if not entry.get("pkg", "").strip()
    ]


def _write_app_entries(condition: EditableCondition, entries: list[dict[str, str]]) -> None:
    element = condition.condition_element
    for child in [c for c in element if _APP_ENTRY_TAG_RE.match(c.tag)]:
        element.remove(child)

    element_cls = type(element)
    for index, entry in enumerate(entries):
        for prefix in ("cls", "label", "pkg"):
            child = element_cls(f"{prefix}{index}")
            child.text = entry.get(prefix, "").strip()
            element.append(child)


def add_app_entry(condition: EditableCondition) -> None:
    """Appends a blank app entry (pkg/label/cls all empty) to an App condition.

    Applied immediately (not staged like the field values above), since it
    changes the entry count -- the Save-time condition_values keys the GUI
    builds for this condition depend on that count matching what's rendered.
    """
    entries = get_app_entries(condition)
    entries.append({"pkg": "", "label": "", "cls": ""})
    _write_app_entries(condition, entries)


def remove_app_entry(condition: EditableCondition, entry_index: int) -> None:
    """Removes one app entry (by its position) from an App condition. Applied
    immediately, same reasoning as add_app_entry.
    """
    entries = get_app_entries(condition)
    if 0 <= entry_index < len(entries):
        del entries[entry_index]
    _write_app_entries(condition, entries)


def sanitize_filename(name: str) -> str:
    """Strip characters illegal in filenames from a Profile name (minimal, not a full slugify)."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "profile"


def default_save_path(profile_name: str) -> str:
    """Default standalone-export path: {current runtime directory}/{sanitized name}.prf.xml."""
    return os.path.join(os.getcwd(), f"{sanitize_filename(profile_name)}.prf.xml")


def profile_name_exists(name: str) -> bool:
    """Whether a Profile with this name already exists in the currently loaded backup."""
    return name.strip() in PrimeItems.tasker_root_elements.get("all_profiles_by_name", {})


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten)."""
    return bool(output_path) and os.path.exists(output_path)


def render_standalone_profile_xml(edited_profile: EditableProfile) -> str:
    """Render the edited Profile as a standalone TaskerData/Profile[/Task...] XML
    string. Unlike a Task, a Profile's own XML only *references* its Entry/Exit
    Tasks by id (mid0/mid1) -- it isn't meaningful to Tasker on its own without
    them, so this bundles in the current (unedited) live copies of whichever of
    those Tasks are still linked, matching the shape Tasker's own single-Profile
    export produces: a Profile element followed by its Task element(s), as
    siblings under one TaskerData root.
    """
    tv = PrimeItems.xml_root.attrib.get("tv", "") if PrimeItems.xml_root is not None else ""
    profile_copy = copy.deepcopy(edited_profile.profile_element)
    # The parsed tree's Element class isn't necessarily xml.etree.ElementTree's own
    # C-accelerated Element (defusedxml's hardened XMLParser forces the pure-Python
    # implementation) -- ET.Element()/.append() enforce an exact type match, so build
    # the wrapper using the same class the parsed elements actually are.
    element_cls = type(profile_copy)
    root = element_cls("TaskerData", {"sr": "", "dvi": "1", "tv": tv})
    root.append(profile_copy)

    all_tasks = PrimeItems.tasker_root_elements.get("all_tasks", {})
    # A Profile can legitimately use the same Task for both Entry and Exit --
    # dict.fromkeys() dedupes while preserving order, so it's only bundled once.
    linked_task_ids = dict.fromkeys(
        task_id for task_id in (edited_profile.entry_task_id, edited_profile.exit_task_id) if task_id
    )
    for task_id in linked_task_ids:
        task_entry = all_tasks.get(task_id)
        if task_entry is not None:
            root.append(copy.deepcopy(task_entry["xml"]))

    ETW.indent(root, space="\t")
    return XML_DECLARATION + ETW.tostring(root, encoding="unicode") + "\n"


def write_standalone_profile_xml(edited_profile: EditableProfile, output_path: str) -> None:
    """Write the edited Profile (plus its linked Task(s)) as a standalone XML file.
    Raises OSError on failure.
    """
    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(render_standalone_profile_xml(edited_profile))


def save_profile_to_android(
    edited_profile: EditableProfile,
    ip_address: str,
    ip_port: str,
    profile_name: str,
    auth_key: str = "",
) -> tuple[int, str, str]:
    """Import the edited Profile (plus its linked Task(s)), rendered as standalone
    XML, onto the Android device via the Tasker HTTP API's POST /api/import
    endpoint. Mirrors taskedit.save_task_to_android exactly, including the
    auth-key caching/retry-on-401 behavior -- see that function's docstring.

    Returns (0, profile_name, auth_key_used) on success, or
    (return_code, error_message, "") on failure.
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from maptasker.src.maputil2 import get_android_auth_key, http_post_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "Android IP address and port are required.", ""

    had_cached_key = bool(auth_key)
    if not auth_key:
        return_code, auth_key = get_android_auth_key(ip_address, ip_port)
        if return_code != 0:
            return return_code, auth_key, ""

    xml_text = render_standalone_profile_xml(edited_profile)

    return_code, response = http_post_request(
        ip_address,
        ip_port,
        "",
        "api/import",
        "",
        xml_text.encode("utf-8"),
        auth_key,
    )

    if return_code == 9 and had_cached_key:
        # Cached key was rejected -- get a fresh one (device prompts once more) and retry.
        return_code, auth_key = get_android_auth_key(ip_address, ip_port)
        if return_code != 0:
            return return_code, auth_key, ""
        return_code, response = http_post_request(
            ip_address,
            ip_port,
            "",
            "api/import",
            "",
            xml_text.encode("utf-8"),
            auth_key,
        )

    if return_code != 0:
        return return_code, str(response), ""
    return 0, profile_name, auth_key


def verify_profile_on_android(ip_address: str, ip_port: str, profile_name: str, auth_key: str) -> bool:
    """Confirms the Profile actually landed in Tasker after a save_profile_to_android
    import, via the Tasker HTTP API's GET /api/profiles?name=<profile_name> (Response:
    profile objects -- a JSON array of {"name": ..., "enabled": ..., "active": ...},
    filtered to Profiles matching the given name). Mirrors taskedit.verify_task_on_android.

    Returns True if the GET succeeded and returned at least one Profile named
    profile_name, False otherwise.
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from urllib.parse import quote  # noqa: PLC0415

    from maptasker.src.maputil2 import http_request  # noqa: PLC0415

    return_code, response = http_request(
        ip_address.strip(),
        ip_port.strip(),
        "",
        "api/profiles",
        f"?name={quote(profile_name)}",
        auth_key,
    )
    if return_code != 0:
        return False

    try:
        profiles = json.loads(response)
    except (ValueError, TypeError):
        return False

    return any(profile.get("name") == profile_name for profile in profiles)


def save_profile_to_android_directory(
    edited_profile: EditableProfile,
    ip_address: str,
    ip_port: str,
    profile_name: str,
    auth_key: str = "",
) -> tuple[int, str]:
    """Fallback for save_profile_to_android when verify_profile_on_android can't
    confirm the import landed in Tasker: retries the same POST /api/import once
    more, rather than falling back to a different endpoint. api/import is the only
    documented way to actually get a Profile into Tasker over HTTP -- /api/file
    only supports GET/DELETE (no way to write a file with it), and even if it
    did, Tasker doesn't watch that directory for files to auto-import -- so a
    second attempt at the real thing is the only fallback that can plausibly
    help, e.g. if the first POST/GET-verify pair hit a transient network blip.
    Mirrors taskedit.save_task_to_android_directory.

    The name is now a misnomer (nothing is written to a directory), kept only
    because userintr's Save-Profile-to-Android handler calls it by this name.

    Returns (0, profile_name) on success, or (return_code, error_message).
    """
    # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
    from maptasker.src.maputil2 import http_post_request  # noqa: PLC0415

    xml_text = render_standalone_profile_xml(edited_profile)

    # file_location is "" so this reproduces save_profile_to_android's request byte for
    # byte -- a retry that posted to a different URL would not be testing the same thing.
    return_code, response = http_post_request(
        ip_address.strip(),
        ip_port.strip(),
        "",
        "api/import",
        "",
        xml_text.encode("utf-8"),
        auth_key,
    )
    if return_code != 0:
        return return_code, str(response)

    return 0, profile_name


def register_new_profile(edited_profile: EditableProfile, profile_name: str) -> None:
    """Adds a new Profile to the in-memory backup's Profile tables (all_profiles,
    all_profiles_by_name) so it behaves like any other Profile loaded from the
    backup -- e.g. so it shows up in the Edit Profile picker and so a second Add
    Profile with the same name is caught by profile_name_exists(). Mirrors
    taskedit.register_new_task exactly. Call once, always paired with
    add_profile_to_project (this alone doesn't make the Profile visible in the
    Project/Profile/Task pulldowns, Map, Diagram, or Tree views -- see that
    function's own docstring): right after the standalone .prf.xml write
    succeeds (see userintr.save_new_profile_event), for a
    keep-without-saving-to-disk Ok without one (see userintr.keep_new_profile_event),
    or after a successful Save To Android import (see
    userintr.save_profile_to_android_event's is_new_profile branch).
    """
    PrimeItems.tasker_root_elements["all_profiles"][edited_profile.profile_id] = {
        "xml": edited_profile.profile_element,
        "name": profile_name,
    }
    PrimeItems.tasker_root_elements["all_profiles_by_name"][profile_name] = {
        "xml": edited_profile.profile_element,
        "id": edited_profile.profile_id,
    }


def add_profile_to_project(edited_profile: EditableProfile, project_name: str) -> None:
    """Attaches a newly-registered Profile to a Project by appending its id to
    that Project's <pids> element -- the actual mechanism Tasker (and every
    view this app generates) uses to know which Profiles belong to which
    Project: getids.get_ids reads exactly this element, and both
    userintr.build_the_tree (the GUI's Project/Profile/Task pulldowns) and
    projects.process_project_profiles (Map/Diagram/Tree output) call it the
    same way. Without this, register_new_profile alone leaves a Profile
    sitting only in the all_profiles/all_profiles_by_name lookup tables,
    which nothing else walks directly -- so it exists, but is invisible
    everywhere in the app except Edit Profile's own picker (which does read
    all_profiles_by_name).

    Mutates the Project's XML element in place (not a copy, unlike Profile
    editing's own deep-copy-then-apply flow) -- PrimeItems.tasker_root_elements
    already holds the live Project table, so this takes effect immediately for
    every other view in the same session. No-op if project_name isn't a known
    Project (defense in depth; the GUI should only offer real Project names).
    """
    project_entry = PrimeItems.tasker_root_elements.get("all_projects", {}).get(project_name)
    if project_entry is None:
        return

    project_element = project_entry["xml"]
    pids_element = project_element.find("pids")
    existing_ids = pids_element.text.split(",") if pids_element is not None and pids_element.text else []
    if edited_profile.profile_id not in existing_ids:
        existing_ids.append(edited_profile.profile_id)
    _set_child_text(project_element, "pids", ",".join(existing_ids))


def add_task_to_project(task_id: str, project_name: str) -> None:
    """Attaches a newly-registered Task to a Project by appending its id to that
    Project's <tids> element -- the <pids>/<tids> counterpart of
    add_profile_to_project, for Tasks instead of Profiles. Call once, right
    after taskedit.register_new_task, for the top-level "Add Task" button
    (see userintr.open_add_task_dialog_event, which requires a single Project
    already be selected, and userintr._finish_new_task, which calls this with
    it).

    Real Tasker backups list every Task belonging to a Project in <tids> --
    and several of this app's own features assume that's always true for a
    Project-owned Task: dirout.check_task's single-Task-selected filter checks
    the owning Project's <tids>, and projects.do_tasks_in_project's "Tasks not
    in any Profile" listing walks <tids> directly. Without this, a brand-new
    Task would have no <tids> entry anywhere, silently breaking both:
    selecting it as the single Task to display would leave the Map view's
    Directory "Tasks" section empty.

    Mutates the Project's XML element in place, same as add_profile_to_project.
    No-op if project_name isn't a known Project (defense in depth; the GUI
    should only offer real Project names).
    """
    project_entry = PrimeItems.tasker_root_elements.get("all_projects", {}).get(project_name)
    if project_entry is None:
        return

    project_element = project_entry["xml"]
    tids_element = project_element.find("tids")
    existing_ids = tids_element.text.split(",") if tids_element is not None and tids_element.text else []
    if task_id not in existing_ids:
        existing_ids.append(task_id)
    _set_child_text(project_element, "tids", ",".join(existing_ids))


def validate_new_profile_requirements(edited_profile: EditableProfile) -> list[str]:
    """Checks the two things a brand-new Profile (Add Profile) must have before
    it can be saved/kept/uploaded: an Entry Task and at least one condition --
    without either, it's a Profile with nothing to run and/or nothing to
    trigger it, i.e. exactly the state create_new_profile leaves a fresh
    Profile in before the user has done anything with it.

    Only for adding a Profile from scratch -- not applied when editing an
    existing one (build_edit_profile_dialog), since an already-saved Profile
    that happens to be missing one of these should still be freely editable.
    """
    errors = []
    if not edited_profile.entry_task_id:
        errors.append("Add an Entry Task before saving -- a Profile needs one to run anything.")
    if not edited_profile.conditions:
        errors.append("Add at least one condition before saving -- a Profile needs one to trigger it.")
    return errors


def apply_edited_profile_to_live_tree(edited_profile: EditableProfile) -> None:
    """Writes an edited (pre-existing) Profile's changes back into the in-memory
    backup's Profile tables (all_profiles, all_profiles_by_name) so views
    generated from them -- Map, Diagram, Tree -- reflect the edit right away
    instead of the Profile's original, unedited content. Mirrors
    taskedit.apply_edited_task_to_live_tree exactly (same id-keyed object swap;
    the actual XML tree's document structure doesn't need touching since every
    view reads Profile content through these tables, not by re-walking the tree for it).

    No-op if the Profile's id isn't registered -- e.g. a brand-new Profile
    (Add Profile) whose Save To Android succeeded without going through
    register_new_profile first; same as apply_edited_task_to_live_tree's
    identical no-op for a brand-new Task.
    """
    all_profiles = PrimeItems.tasker_root_elements["all_profiles"]
    entry = all_profiles.get(edited_profile.profile_id)
    if entry is None:
        return

    old_name = entry["name"]
    new_name = edited_profile.profile_element.findtext("nme", "") or old_name

    all_profiles[edited_profile.profile_id] = {"xml": edited_profile.profile_element, "name": new_name}

    all_profiles_by_name = PrimeItems.tasker_root_elements.setdefault("all_profiles_by_name", {})
    if old_name in all_profiles_by_name and old_name != new_name:
        del all_profiles_by_name[old_name]
    all_profiles_by_name[new_name] = {"xml": edited_profile.profile_element, "id": edited_profile.profile_id}
