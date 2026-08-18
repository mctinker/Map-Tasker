"""Compare two Tasker configurations and report what changed between them."""

#! /usr/bin/env python3

#                                                                                      #
# xmldiff: Diff two Tasker configurations -- what was added, removed, renamed or        #
#          edited between them -- and report it as plain text.                          #
#                                                                                      #
# No global state at all.  Both sides arrive as Configuration records and are only read #
# from, which is what makes this testable from XML text and reusable from a CLI.        #
# Getting the second file INTO a Configuration without disturbing the one the user has  #
# open is the hard half, and it lives in diffload.py -- see that module's header.       #
#                                                                                      #
# The report is plain text.  The caller writes it to a file as-is and escapes a COPY of #
# it for display -- see userintr.compare_files_event, the same split healthck.py uses.  #
#                                                                                      #
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, NamedTuple

from maptasker.src.actionc import action_codes
from maptasker.src.sysconst import MY_VERSION, SCENE_TASK_TYPES

if TYPE_CHECKING:
    import defusedxml.ElementTree

# The four things that can happen to an object, and the order their sections appear in.
ADDED = "ADDED"
REMOVED = "REMOVED"
RENAMED = "RENAMED"
CHANGED = "CHANGED"
_CATEGORIES = (ADDED, REMOVED, RENAMED, CHANGED)

_SECTION_HEADINGS = {
    ADDED: "ADDED -- in the newer file only",
    REMOVED: "REMOVED -- in the older file only",
    RENAMED: "RENAMED -- same object, different name",
    CHANGED: "CHANGED",
}

_REPORT_WIDTH = 78

# How many detail lines one entry may print before the rest is summarised.  A Task with
# forty rewritten actions would otherwise bury every other entry; the number left out is
# still shown, so nothing is dropped silently.
_MAX_DETAILS = 12

# Timestamps, not content.  Tasker rewrites these on every save, so counting them would
# report every object in the file as changed and make the whole feature useless.
_VOLATILE_TAGS = frozenset({"cdate", "mdate", "edate"})

# Objects sharing an id but with a different name and nothing in common are not two
# versions of one object -- an id is unique within a file, not across two.  Below this
# similarity they are reported as a removal plus an addition instead.
_SAME_OBJECT_RATIO = 0.5

# Enough of those and the two files are probably unrelated.  Warned about at the top of
# the report, and only when they are also most of what matched: a handful of heavily
# rewritten objects in two genuine versions of one file must not trip it.
_COLLISION_WARNING_FLOOR = 5

# The object kinds compared, in report order.
#
# 'by_id' says whether the PrimeItems table is already keyed by the object's <id>.
# all_profiles and all_tasks are; all_projects is keyed by NAME
# (taskerd.move_xml_to_table(..., get_id=False, "name")), so a Project's identity is read
# out of its own <id> child instead -- keying by name would report every rename as a
# deletion plus an unrelated addition, the one answer a user least wants.
#
# A Scene has no <id> at all, so it can only be matched by name.  _limitations() says so.
_KINDS = (
    ("Project", "all_projects", False, "name"),
    ("Profile", "all_profiles", True, "nme"),
    ("Task", "all_tasks", True, "nme"),
    ("Scene", "all_scenes", False, "nme"),
)

# Which kinds show their id in the report.  A Project's id is a UUID nobody recognises
# and a Scene has none, so both read better by name alone.
_KINDS_SHOWING_ID = frozenset({"Profile", "Task"})

# A Project's membership lists, and what each holds.  <pids>/<tids> hold ids, which is
# what all_profiles/all_tasks are keyed by; <scenes> holds names, which is what
# all_scenes is keyed by.  Every entry is therefore already the right identity.
_MEMBERSHIP_TAGS = (("pids", "Profile", "Profiles"), ("tids", "Task", "Tasks"), ("scenes", "Scene", "Scenes"))
_MEMBERSHIP_LIST_TAGS = frozenset(tag for tag, _, _ in _MEMBERSHIP_TAGS)

# A Profile's own children.  Anything else it carries is one of its conditions.
_PROFILE_OWN_TAGS = frozenset({"nme", "id", "mid0", "mid1", "limit", "flags", "pri", *_VOLATILE_TAGS})

# A Project's own children, membership aside.
_PROJECT_OWN_TAGS = frozenset({"name", "id", "pids", "tids", "scenes", *_VOLATILE_TAGS})

# A Scene's dimensions, and how each reads in the report.
_SCENE_DIMENSIONS = (
    ("widthPort", "portrait width"),
    ("heightPort", "portrait height"),
    ("widthLand", "landscape width"),
    ("heightLand", "landscape height"),
)


class Configuration(NamedTuple):
    """One side of a comparison: a whole Tasker configuration and where it came from.

    'tables' is a PrimeItems.tasker_root_elements-shaped dict -- either the live one (for
    the configuration MapTasker has open) or one parsed in isolation by diffload.  'root'
    is the XML root, needed for the global <Variable> and <Setting> elements, which are
    not in the tables.  Both are only ever read here.

    'when' is the file's modification time, or None when there is not one to be had; it
    is what lets the caller decide which side is the older.  See diffload.order_by_age.
    """

    path: str
    tables: dict
    # Both default so a caller that only needs the object tables -- diffload's own
    # order_by_age, which just reads 'when' -- can build one without them.  A missing
    # root simply means the global Variables and Settings are not compared.
    root: object | None = None
    when: datetime | None = None


@dataclass
class Entry:
    """One difference between the two configurations.

    'tag' is a stable, deliberately un-translated identifier (TASK-CHANGED and friends),
    for the same reason healthck.py's are: it stays greppable in every language, and two
    reports from different runs stay comparable.
    """

    kind: str
    category: str
    where: str
    details: list[str] = field(default_factory=list)

    @property
    def tag(self) -> str:
        """"TASK-CHANGED" -- what the report prints in brackets."""
        return f"{self.kind.upper()}-{self.category}"


@dataclass
class _Side:
    """One configuration, indexed the way the comparison needs it."""

    objects: dict[str, dict] = field(default_factory=dict)  # kind -> {identity: element}
    names: dict[str, dict] = field(default_factory=dict)  # kind -> {identity: name}
    # kind -> {identity: owning Project ID}.  Keyed by the Project's id and not its name
    # on purpose: renaming a Project would otherwise report every Profile, Task and Scene
    # inside it as having moved -- 17 of them at once, measured on two real backups.
    project_of: dict[str, dict] = field(default_factory=dict)
    project_names: dict[str, str] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    settings: dict[str, str] = field(default_factory=dict)

    def project_name_of(self, kind: str, key: str) -> str:
        """The name of the Project owning this object, or "" if none does."""
        project_id = self.project_of[kind].get(key)
        return self.project_names.get(project_id, "") if project_id else ""

    def name_of(self, kind: str, key: str) -> str:
        """This object's name, or its key when it has none of its own."""
        return self.names[kind].get(key) or key


# ##################################################################################
# Reading one side.
# ##################################################################################
def _text(element: defusedxml.ElementTree.Element | None, tag: str) -> str:
    """The stripped text of a child element, or "" when it is missing or empty."""
    if element is None:
        return ""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _split_list(element: defusedxml.ElementTree.Element, tag: str) -> set[str]:
    """A Project's comma-separated <pids>/<tids>/<scenes>, as a SET.

    A set because Tasker reorders these freely and the order carries no meaning -- as a
    list, moving one Profile up the list would report the Project as changed.
    """
    text = _text(element, tag)
    return {item.strip() for item in text.split(",") if item.strip()} if text else set()


def _canonical(element: defusedxml.ElementTree.Element, *, is_object_root: bool = False) -> str:
    """A comparable rendering of an element: same content, same string.

    Two things are deliberately dropped, and the first is the difference between a usable
    report and an unusable one.

    'sr' on the object itself and on <Action> is a POSITION in the file ("proj57",
    "act5"), not an identity.  Inserting one Project renumbers the sr of every Project
    after it -- measured on a real pair of backups, keeping it reported 76 of 83 Projects
    as changed where only 4 had actually changed.  It is kept everywhere else, because on
    <Str sr="arg0"> it names WHICH argument and is pure content.

    Attributes are sorted, so an attribute order differing between two Tasker versions is
    not mistaken for an edit.
    """
    parts: list[str] = []

    def walk(node: defusedxml.ElementTree.Element, *, root: bool) -> None:
        if node.tag in _VOLATILE_TAGS:
            return
        parts.append(f"<{node.tag}")
        for key in sorted(node.attrib):
            if key == "sr" and (root or node.tag == "Action"):
                continue
            parts.append(f" {key}={node.attrib[key]!r}")
        parts.append(">")
        if node.text and node.text.strip():
            text = node.text.strip()
            # A Project's membership lists are sets, not sequences: Tasker reorders them
            # freely and the order carries no meaning, so sorting here is what stops a
            # reshuffled <pids> from reporting the Project as changed.
            if node.tag in _MEMBERSHIP_LIST_TAGS:
                text = ",".join(sorted(item.strip() for item in text.split(",") if item.strip()))
            parts.append(text)
        for child in node:
            walk(child, root=False)
        parts.append(f"</{node.tag}>")

    walk(element, root=is_object_root)
    return "".join(parts)


def _index(configuration: Configuration) -> _Side:
    """Index one configuration by each object's identity.

    Reads the tables as they are; nothing here writes to them, which is what lets
    diffload hand over the live PrimeItems tables rather than copying a whole backup.
    """
    side = _Side()
    for kind, table_name, keyed_by_id, name_tag in _KINDS:
        table = configuration.tables.get(table_name) or {}
        objects, names = {}, {}
        for table_key, entry in table.items():
            element = entry["xml"] if isinstance(entry, dict) else entry
            identity = table_key if keyed_by_id else (_text(element, "id") or table_key)
            objects[identity] = element
            names[identity] = _text(element, name_tag)
        side.objects[kind] = objects
        side.names[kind] = names
        side.project_of[kind] = {}

    for project_id, project in side.objects["Project"].items():
        side.project_names[project_id] = side.names["Project"].get(project_id, "")
        for list_tag, kind, _ in _MEMBERSHIP_TAGS:
            for key in _split_list(project, list_tag):
                side.project_of[kind][key] = project_id

    root = configuration.root
    if root is not None:
        # Global variables and Tasker preferences live at the top level, not in any table.
        side.variables = {_text(item, "n"): _text(item, "v") for item in root.findall("Variable") if _text(item, "n")}
        side.settings = {_text(item, "n"): _text(item, "v") for item in root.findall("Setting") if _text(item, "n")}
    return side


def _describe(kind: str, side: _Side, key: str) -> str:
    """Task 'Wake Up' (id 118) -- an object as the report names it."""
    name = side.name_of(kind, key)
    if kind in _KINDS_SHOWING_ID:
        return f"{kind} '{name}' (id {key})" if name else f"{kind} (id {key}) [unnamed]"
    return f"{kind} '{name}'"


def _where(kind: str, side: _Side, key: str) -> str:
    """An object's location: "Project 'Home' > Task 'Wake Up' (id 23)".

    The owning Project is silent when nothing owns it -- a Task in no Project is
    ordinary, and a location is the wrong place to raise it.  Same convention healthck
    uses, so the two reports read alike.
    """
    described = _describe(kind, side, key)
    project_name = side.project_name_of(kind, key) if kind != "Project" else ""
    return f"Project '{project_name}' > {described}" if project_name else described


# ##################################################################################
# Actions.
# ##################################################################################
def _action_code_name(code: str) -> str:
    """An action code as the name MapTasker shows everywhere else, e.g. "Flash"."""
    entry = action_codes.get(f"{code}t")
    return entry.name if entry else f"code {code}"


def _action_at(action: defusedxml.ElementTree.Element, position: int) -> str:
    """"2. Say" -- one action, numbered as the user sees it in Tasker."""
    return f"{position}. {_action_code_name(_text(action, 'code'))}"


def _argument_names(code: str) -> dict[str, str]:
    """{arg id: argument name} for one action code, e.g. {"0": "Text"}.

    From actionc.action_codes, which is a static table.  The richer renderer in actione.py
    needs a live program_arguments and would make this module untestable.
    """
    entry = action_codes.get(f"{code}t")
    return {argument.arg_id: argument.arg_name for argument in (entry.args or ())} if entry else {}


def _action_arguments(action: defusedxml.ElementTree.Element) -> dict[str, str]:
    """{arg id: value} for one action, across whichever element types hold its arguments."""
    arguments = {}
    for child in action:
        sr = child.attrib.get("sr", "")
        if not sr.startswith("arg"):
            continue
        value = child.attrib.get("val") if child.tag == "Int" else (child.text or "")
        if value is None:
            value = _text(child, "var")
        arguments[sr[3:]] = (value or "").strip()
    return arguments


def _action_detail(
    before: defusedxml.ElementTree.Element,
    after: defusedxml.ElementTree.Element,
    position: int,
) -> list[str]:
    """What changed inside one action that kept its place."""
    before_code, after_code = _text(before, "code"), _text(after, "code")
    if before_code != after_code:
        # Stop at the code.  The same argument id means something different either side --
        # Flash's arg0 is its text where Notify's arg0 is its title -- so comparing the
        # values would report a change of meaning as a change of value.
        return [f"{position}. {_action_code_name(before_code)}  ->  {_action_code_name(after_code)}"]

    details = []
    before_label, after_label = _text(before, "label"), _text(after, "label")
    if before_label != after_label:
        details.append(f"{position}. {_action_code_name(after_code)} label: '{before_label}' -> '{after_label}'")

    names = _argument_names(after_code)
    before_arguments, after_arguments = _action_arguments(before), _action_arguments(after)
    for arg_id in sorted(before_arguments.keys() | after_arguments.keys(), key=lambda item: (len(item), item)):
        was, now = before_arguments.get(arg_id, ""), after_arguments.get(arg_id, "")
        if was == now:
            continue
        # Named ("Text"), not numbered ("arg0") -- a bare arg number tells nobody anything.
        label = names.get(arg_id, f"argument {arg_id}")
        details.append(f"{position}. {_action_code_name(after_code)} {label}: '{was}' -> '{now}'")
    return details


def _pair_replaced_actions(
    before_actions: list,
    after_actions: list,
    i1: int,
    i2: int,
    j1: int,
    j2: int,
) -> list[str]:
    """Resolve one difflib 'replace' block into edits, insertions and removals.

    Matched a second time on the action CODES rather than paired off positionally.  An
    action inserted in the middle of a rewritten run would otherwise be paired with a
    completely different action beside it, and both would be reported as edited -- where
    what happened was one insertion and one edit.
    """
    details: list[str] = []
    before_codes = [_text(action, "code") for action in before_actions[i1:i2]]
    after_codes = [_text(action, "code") for action in after_actions[j1:j2]]

    for opcode, a1, a2, b1, b2 in SequenceMatcher(a=before_codes, b=after_codes, autojunk=False).get_opcodes():
        if opcode == "equal":
            for offset in range(a2 - a1):
                details.extend(
                    _action_detail(
                        before_actions[i1 + a1 + offset],
                        after_actions[j1 + b1 + offset],
                        j1 + b1 + offset + 1,
                    ),
                )
        elif opcode == "delete":
            details.extend(
                f"- removed from {i1 + index + 1}:  {_action_at(before_actions[i1 + index], i1 + index + 1)}"
                for index in range(a1, a2)
            )
        elif opcode == "insert":
            details.extend(
                f"+ inserted at {j1 + index + 1}:  {_action_at(after_actions[j1 + index], j1 + index + 1)}"
                for index in range(b1, b2)
            )
        else:  # replace -- pair what lines up, report the remainder either side.
            paired = min(a2 - a1, b2 - b1)
            for offset in range(paired):
                details.extend(
                    _action_detail(
                        before_actions[i1 + a1 + offset],
                        after_actions[j1 + b1 + offset],
                        j1 + b1 + offset + 1,
                    ),
                )
            details.extend(
                f"- removed from {i1 + index + 1}:  {_action_at(before_actions[i1 + index], i1 + index + 1)}"
                for index in range(a1 + paired, a2)
            )
            details.extend(
                f"+ inserted at {j1 + index + 1}:  {_action_at(after_actions[j1 + index], j1 + index + 1)}"
                for index in range(b1 + paired, b2)
            )
    return details


def _task_details(
    before: defusedxml.ElementTree.Element,
    after: defusedxml.ElementTree.Element,
) -> list[str]:
    """What changed in a Task's action list.

    A sequence diff rather than a position-by-position walk: inserting one action at the
    top shifts every action below it, which pairwise comparison would report as "every
    action changed" instead of "one action added".  Actions are matched on their
    canonical text, which is why _canonical drops <Action>'s own sr -- that IS the
    position, and keeping it would make every shifted action look different.
    """
    before_actions = before.findall("Action")
    after_actions = after.findall("Action")
    matcher = SequenceMatcher(
        a=[_canonical(action) for action in before_actions],
        b=[_canonical(action) for action in after_actions],
        autojunk=False,
    )

    details: list[str] = []
    unchanged = 0
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            unchanged += i2 - i1
        elif opcode == "delete":
            details.extend(
                f"- removed from {index + 1}:  {_action_at(before_actions[index], index + 1)}"
                for index in range(i1, i2)
            )
        elif opcode == "insert":
            details.extend(
                f"+ inserted at {index + 1}:  {_action_at(after_actions[index], index + 1)}"
                for index in range(j1, j2)
            )
        else:
            details.extend(_pair_replaced_actions(before_actions, after_actions, i1, i2, j1, j2))

    if details and unchanged:
        # How much stayed put is what makes a long entry readable at a glance.
        details.append(f"{unchanged} of {len(before_actions)} actions unchanged.")
    return details


# ##################################################################################
# Profiles, Projects and Scenes.
# ##################################################################################
def _conditions(profile: defusedxml.ElementTree.Element) -> dict[str, list[str]]:
    """{condition type: canonical text of each}, e.g. {"Event": ["<Event>...</Event>"]}.

    Anything a Profile carries that is not one of its own fields is a condition -- the
    types are open-ended (App, Time, State, Event, Loc, ...) and a newer Tasker may add
    one, so they are recognised by exclusion rather than by a list that would go stale.
    """
    grouped: dict[str, list[str]] = {}
    for child in profile:
        if child.tag in _PROFILE_OWN_TAGS:
            continue
        grouped.setdefault(child.tag, []).append(_canonical(child))
    return grouped


def _profile_summary(side: _Side, profile: defusedxml.ElementTree.Element) -> list[str]:
    """What an added or removed Profile was, so the entry means something on its own."""
    details = []
    condition_types = sorted(_conditions(profile))
    if condition_types:
        details.append(f"Conditions: {', '.join(condition_types)}.")
    entry_task = _text(profile, "mid0")
    if entry_task:
        details.append(f"Entry Task: '{side.name_of('Task', entry_task)}'.")
    return details


def _profile_details(older: _Side, newer: _Side, key: str) -> list[str]:
    """What changed about a Profile: whether it is on, the Tasks it runs, its conditions."""
    before, after = older.objects["Profile"][key], newer.objects["Profile"][key]
    details = []

    was_disabled = _text(before, "limit") == "true"
    now_disabled = _text(after, "limit") == "true"
    if was_disabled != now_disabled:
        details.append("disabled (was enabled)" if now_disabled else "enabled (was disabled)")

    # Each id is resolved on its own side: the name for one id can differ between the two
    # files, which is the whole point of reporting a rename separately.
    for tag, label in (("mid0", "entry Task"), ("mid1", "exit Task")):
        was, now = _text(before, tag), _text(after, tag)
        if was == now:
            continue
        was_name = f"'{older.name_of('Task', was)}'" if was else "none"
        now_name = f"'{newer.name_of('Task', now)}'" if now else "none"
        details.append(f"{label}: {was_name} -> {now_name}")

    before_conditions, after_conditions = _conditions(before), _conditions(after)
    for condition_type in sorted(before_conditions.keys() | after_conditions.keys()):
        was = before_conditions.get(condition_type, [])
        now = after_conditions.get(condition_type, [])
        if was == now:
            continue
        if not was:
            details.append(f"{condition_type} condition added ({len(now)}).")
        elif not now:
            details.append(f"{condition_type} condition removed ({len(was)}).")
        else:
            details.append(f"{condition_type} condition edited.")
    return details


def _project_details(older: _Side, newer: _Side, key: str) -> list[str]:
    """What changed about a Project: what is in it, its variables, anything else."""
    before, after = older.objects["Project"][key], newer.objects["Project"][key]
    details = []

    for list_tag, kind, plural in _MEMBERSHIP_TAGS:
        was, now = _split_list(before, list_tag), _split_list(after, list_tag)
        # Named, not numbered: an id tells the reader nothing about what moved.
        if added := sorted(f"'{newer.name_of(kind, item)}'" for item in now - was):
            details.append(f"{plural} added:   {', '.join(added)}")
        if removed := sorted(f"'{older.name_of(kind, item)}'" for item in was - now):
            details.append(f"{plural} removed: {', '.join(removed)}")

    details.extend(_project_variable_details(before, after))

    own = set(_PROJECT_OWN_TAGS) | {"ProfileVariable"}
    if _children_canonical(before, own) != _children_canonical(after, own):
        details.append("Other Project properties changed.")
    return details


def _project_variable_details(
    before: defusedxml.ElementTree.Element,
    after: defusedxml.ElementTree.Element,
) -> list[str]:
    """Project variables added, removed or given a new value.

    Named explicitly rather than swept into "other properties changed", which is what a
    Project variable gaining a value looked like the first time this ran against two real
    backups -- accurate, and no use to anybody.
    """
    def variables(project: defusedxml.ElementTree.Element) -> dict[str, str]:
        return {
            _text(item, "pvn"): _text(item, "pvv")
            for item in project.findall("ProfileVariable")
            if _text(item, "pvn")
        }

    was, now = variables(before), variables(after)
    details = [f"Project variable {name} added: '{now[name]}'" for name in sorted(now.keys() - was.keys())]
    details += [f"Project variable {name} removed" for name in sorted(was.keys() - now.keys())]
    details += [
        f"Project variable {name}: '{was[name]}' -> '{now[name]}'"
        for name in sorted(was.keys() & now.keys())
        if was[name] != now[name]
    ]
    return details


def _children_canonical(element: defusedxml.ElementTree.Element, exclude: set[str]) -> str:
    """The canonical text of an element's children, skipping the named tags."""
    return "".join(_canonical(child) for child in element if child.tag not in exclude)


def _scene_elements(scene: defusedxml.ElementTree.Element) -> dict[str, defusedxml.ElementTree.Element]:
    """{label: element} for a Scene's drawable elements.

    Keyed by the label the designer shows ("Text 'Ok'") rather than by the element's sr:
    an sr is a slot, so renaming an element in place would read as that slot changing
    into something else, where by name it reads as one element gone and another arrived.
    """
    return {_scene_element_label(child): child for child in scene if child.tag.endswith("Element")}


def _scene_element_label(element: defusedxml.ElementTree.Element) -> str:
    """"Button 'Cancel'" -- a Scene element as its designer names it.

    The name is arg0, the same place sceneedit.legacy_element_label reads it from; it is
    reproduced here rather than imported so this module stays free of the Scene editor.
    """
    name = element.find("Str[@sr='arg0']")
    name_text = (name.text or "").strip() if name is not None and name.text else ""
    element_type = element.tag.replace("Element", "")
    return f"{element_type} '{name_text}'" if name_text else element_type


def _scene_details(older: _Side, newer: _Side, key: str) -> list[str]:
    """What changed about a Scene: its size, its elements, and what they run."""
    before, after = older.objects["Scene"][key], newer.objects["Scene"][key]

    # A Version 2 Scene keeps its whole layout in one gzipped, base64'd JSON blob.  Saying
    # it changed, and saying plainly that nothing looked inside, beats both a silent
    # "Changed." and a decode that would tie this module to the Scene editor.
    if before.find("lj") is not None or after.find("lj") is not None:
        if _text(before, "lj") != _text(after, "lj"):
            return ["Version 2 layout changed (not compared in detail)."]
        return []

    details = []
    for tag, label in _SCENE_DIMENSIONS:
        was, now = _text(before, tag), _text(after, tag)
        if was != now and (was or now):
            details.append(f"{label}: '{was}' -> '{now}'")

    was_elements, now_elements = _scene_elements(before), _scene_elements(after)
    details += [f"- removed: {label}" for label in sorted(was_elements.keys() - now_elements.keys())]
    details += [f"+ added:   {label}" for label in sorted(now_elements.keys() - was_elements.keys())]

    for label in sorted(was_elements.keys() & now_elements.keys()):
        details.extend(_scene_element_details(older, newer, label, was_elements[label], now_elements[label]))
    return details


def _scene_element_details(
    older: _Side,
    newer: _Side,
    label: str,
    before: defusedxml.ElementTree.Element,
    after: defusedxml.ElementTree.Element,
) -> list[str]:
    """What changed about one Scene element that is on both sides."""
    if _canonical(before) == _canonical(after):
        return []

    details = []
    if _text(before, "geom") != _text(after, "geom"):
        details.append(f"{label} moved.")

    # Which Task an element fires is the part of a Scene that actually does something.
    for tag, event in SCENE_TASK_TYPES.items():
        was, now = _text(before, tag), _text(after, tag)
        if was == now:
            continue
        was_name = f"'{older.name_of('Task', was)}'" if was else "none"
        now_name = f"'{newer.name_of('Task', now)}'" if now else "none"
        details.append(f"{label} {event}: {was_name} -> {now_name}.")

    if not details:
        details.append(f"{label} changed.")
    return details


# ##################################################################################
# The comparison.
# ##################################################################################
def _details_for(kind: str, older: _Side, newer: _Side, key: str) -> list[str]:
    """The per-kind sub-diff for one object present on both sides."""
    if kind == "Task":
        return _task_details(older.objects[kind][key], newer.objects[kind][key])
    if kind == "Profile":
        return _profile_details(older, newer, key)
    if kind == "Project":
        return _project_details(older, newer, key)
    return _scene_details(older, newer, key)


def _summary_for(kind: str, side: _Side, key: str) -> list[str]:
    """What an added or removed object was, so its entry means something on its own."""
    element = side.objects[kind][key]
    if kind == "Task":
        return [f"{len(element.findall('Action'))} actions."]
    if kind == "Profile":
        return _profile_summary(side, element)
    if kind == "Scene":
        return [f"{len(_scene_elements(element))} elements."]
    return []


def _content_signature(element: defusedxml.ElementTree.Element, name_tag: str) -> set[str]:
    """The values an object holds -- its content with the markup thrown away.

    Text and 'val' attributes only.  Comparing canonical XML instead does not work: two
    Tasks with nothing whatever in common still score 0.92 against each other, because
    almost all of both strings is the tags and attributes every Task carries.  Stripped
    to the values, the same pair scores 0.2 and a pure rename scores 1.0 -- a margin wide
    enough to decide on.

    The name is left out because this is only ever asked about a pair whose names already
    differ; including it would count that difference twice.
    """
    values: set[str] = set()

    def walk(node: defusedxml.ElementTree.Element, *, root: bool) -> None:
        if node.tag in _VOLATILE_TAGS or (root and node.tag == name_tag):
            return
        if node.text and node.text.strip():
            values.add(node.text.strip())
        if "val" in node.attrib:
            values.add(node.attrib["val"])
        for child in node:
            walk(child, root=False)

    for child in element:
        walk(child, root=True)
    return values


def _is_the_same_object(kind: str, older: _Side, newer: _Side, key: str) -> bool:
    """Whether an id-matched pair really is one object in two states.

    An id is unique within a file, not across two.  When a pair shares nothing but its id
    -- a different name AND unrecognisably different content -- calling it one heavily
    edited object produces nonsense, and a removal plus an addition is truer.

    The name test comes first and is what keeps this narrow: a Task rewritten from
    scratch under the SAME name is a change, and reporting it as a replacement would be
    actively wrong.
    """
    if older.name_of(kind, key) == newer.name_of(kind, key):
        return True

    name_tag = next(tag for object_kind, _, _, tag in _KINDS if object_kind == kind)
    before = _content_signature(older.objects[kind][key], name_tag)
    after = _content_signature(newer.objects[kind][key], name_tag)
    if not before and not after:
        # Two empty objects that differ only in name: a rename, nothing else to go on.
        return True
    shared = len(before & after) / len(before | after)
    return shared >= _SAME_OBJECT_RATIO


def _compare_kind(kind: str, older: _Side, newer: _Side, entries: list[Entry]) -> int:
    """Compare every object of one kind.  Returns how many id collisions were found."""
    was, now = older.objects[kind], newer.objects[kind]
    added, removed = set(now) - set(was), set(was) - set(now)
    collisions = 0

    for key in sorted(set(was) & set(now)):
        if _is_the_same_object(kind, older, newer, key):
            _compare_one(kind, older, newer, key, entries)
        else:
            # Same id, different object.  Reported as both, and counted so the report can
            # warn at the top when it happens often enough to mean the files are unrelated.
            collisions += 1
            added.add(key)
            removed.add(key)

    entries.extend(
        Entry(kind, ADDED, _where(kind, newer, key), _summary_for(kind, newer, key)) for key in sorted(added)
    )
    entries.extend(
        Entry(kind, REMOVED, _where(kind, older, key), _summary_for(kind, older, key)) for key in sorted(removed)
    )
    return collisions


def _compare_one(kind: str, older: _Side, newer: _Side, key: str, entries: list[Entry]) -> None:
    """Compare one object present, and genuinely the same object, on both sides."""
    old_name, new_name = older.name_of(kind, key), newer.name_of(kind, key)
    where = _where(kind, newer, key)

    if old_name != new_name:
        entries.append(Entry(kind, RENAMED, where, [f"'{old_name}' -> '{new_name}'"]))

    before = _canonical(older.objects[kind][key], is_object_root=True)
    after = _canonical(newer.objects[kind][key], is_object_root=True)
    if before == after:
        return

    details = _details_for(kind, older, newer, key)
    # A rename already has its own entry.  Without this, renaming a Task would be reported
    # twice: once as the rename, and once as a change with nothing to say.
    if not details and old_name != new_name:
        return
    if len(details) > _MAX_DETAILS:
        details = [*details[:_MAX_DETAILS], f"...and {len(details) - _MAX_DETAILS} more differences."]
    entries.append(Entry(kind, CHANGED, where, details or ["Changed."]))


def _compare_named_values(kind: str, was: dict[str, str], now: dict[str, str], entries: list[Entry]) -> None:
    """Compare the global <Variable>/<Setting> name-value pairs.

    An object-level comparison would miss these entirely -- they sit at the top level of
    the file, in no Project and no table.
    """
    entries.extend(
        Entry(kind, ADDED, f"{kind} {name}", [f"'{now[name]}'"]) for name in sorted(now.keys() - was.keys())
    )
    entries.extend(
        Entry(kind, REMOVED, f"{kind} {name}", [f"'{was[name]}'"]) for name in sorted(was.keys() - now.keys())
    )
    entries.extend(
        Entry(kind, CHANGED, f"{kind} {name}", [f"'{was[name]}'  ->  '{now[name]}'"])
        for name in sorted(was.keys() & now.keys())
        if was[name] != now[name]
    )


def _counts(entries: list[Entry]) -> dict:
    """How many entries of each category."""
    return {category: sum(1 for entry in entries if entry.category == category) for category in _CATEGORIES}


# ##################################################################################
# The report.
# ##################################################################################
def _totals(side: _Side) -> str:
    """"4 Projects, 7 Profiles, 6 Tasks, 3 Scenes"."""
    return ", ".join(f"{len(side.objects[kind])} {kind}s" for kind, _, _, _ in _KINDS)


def _limitations(entries: list[Entry]) -> list[str]:
    """The closing section on what this comparison cannot see.

    Not optional, and not conditional on anything having gone wrong.  A renamed Scene
    genuinely does come out as one removal and one addition -- a Scene carries no id, so
    a rename and a replacement are indistinguishable in the file.  Unsaid, that reads as
    a bug in the comparison rather than a limit of the format.
    """
    lines = [
        "",
        "WHAT THIS COMPARISON CANNOT SEE",
        "-" * _REPORT_WIDTH,
        "A renamed Scene appears above as one removed Scene and one added Scene.",
        "Scenes are the one object Tasker stores with no id, so they can only be matched",
        "by name; Projects, Profiles and Tasks all carry ids and are matched by those.",
        "",
        "Creation and modification dates are ignored throughout.  Tasker rewrites them",
        "on every save, whether or not anything about the object actually changed.",
    ]
    if any("Version 2 layout" in detail for entry in entries for detail in entry.details):
        lines += [
            "Scenes that hold a Version 2 layout are reported as changed without detail:",
            "the whole layout is one compressed block in the file rather than separate",
            "elements, so there is nothing in it to compare piece by piece.",
        ]
    lines.append("")
    return lines


def _build_report(
    older: Configuration,
    newer: Configuration,
    older_side: _Side,
    newer_side: _Side,
    entries: list[Entry],
    collisions: int,
    when: datetime,
) -> str:
    """Render the comparison as the plain text that is both saved and displayed."""
    counts = _counts(entries)
    lines = [
        "MapTasker Compare",
        "=" * _REPORT_WIDTH,
        f"Older file:  {older.path}" + (f"   ({older.when:%d-%b-%Y %H:%M:%S})" if older.when else ""),
        f"Newer file:  {newer.path}" + (f"   ({newer.when:%d-%b-%Y %H:%M:%S})" if newer.when else ""),
        f"Generated:   {when:%d-%b-%Y %H:%M:%S}",
        f"Version:     {MY_VERSION}",
        "",
        f"Older:       {_totals(older_side)}",
        f"Newer:       {_totals(newer_side)}",
        "Changes:     " + ", ".join(f"{counts[category]} {category.lower()}" for category in _CATEGORIES),
        "",
    ]

    if collisions >= _COLLISION_WARNING_FLOOR:
        lines += [
            "",
            "WARNING",
            "-" * _REPORT_WIDTH,
            f"{collisions} objects share an id between these two files while being entirely",
            "different objects.  These are probably not two versions of one configuration.",
            "Each such object is reported below as one removed and one added.",
            "",
        ]

    if not entries:
        lines += ["", "The two files hold the same configuration -- nothing differs.", ""]
        lines += _limitations(entries)
        return "\n".join(lines)

    kind_order = {kind: index for index, (kind, _, _, _) in enumerate(_KINDS)}
    for category in _CATEGORIES:
        of_this_category = [entry for entry in entries if entry.category == category]
        if not of_this_category:
            continue
        lines += ["", _SECTION_HEADINGS[category], "-" * _REPORT_WIDTH]
        # Kind first so the section reads Projects, Profiles, Tasks, Scenes; then by
        # location, which puts everything about one Project together.
        for entry in sorted(of_this_category, key=lambda item: (kind_order.get(item.kind, 99), item.where)):
            lines.append(f"[{entry.tag}]  {entry.where}")
            lines += [f"    {detail}" for detail in entry.details]
            lines.append("")

    lines += _limitations(entries)
    return "\n".join(lines)


def compare(older: Configuration, newer: Configuration) -> tuple[str, dict]:
    """Compare two configurations.  Returns (report text, counts by category).

    "Added" means present in 'newer', so the caller is expected to have sorted the two by
    age already (diffload.order_by_age).  The report header names which file is which
    either way, so a wrong guess is visible rather than misleading.
    """
    older_side, newer_side = _index(older), _index(newer)

    entries: list[Entry] = []
    collisions = 0
    for kind, _, _, _ in _KINDS:
        collisions += _compare_kind(kind, older_side, newer_side, entries)

    _compare_named_values("Variable", older_side.variables, newer_side.variables, entries)
    _compare_named_values("Setting", older_side.settings, newer_side.settings, entries)

    report = _build_report(older, newer, older_side, newer_side, entries, collisions, datetime.now())  # noqa: DTZ005
    return report, _counts(entries)
