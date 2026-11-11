"""mapreddit: the Map's Projects, Profiles, Tasks and Scenes as Tasker's own text, ready to paste into a Reddit post."""

#! /usr/bin/env python3

#                                                                                        #
# mapreddit: what the Map shows, written the way people post Tasker on r/tasker.            #
#                                                                                        #
# The Tasker forums and r/tasker share configurations as text, in the layout Tasker itself   #
# uses when it describes a Task or a Profile:                                               #
#                                                                                        #
#     Profile: TetheredDevices                                                           #
#         Event: Logcat Entry [ Output Variables:* Component:SoftApManager ]                #
#                                                                                        #
#     Enter Task: Tethered Devices                                                       #
#                                                                                        #
#     A1: Variable Search Replace [                                                      #
#          Variable: %lc_text                                                            #
#          Store Matches In Array: %mac ]                                                #
#                                                                                        #
# The Map cannot be turned into that by rearranging its text: it is drawn for reading on      #
# screen, one run of "Name=value, To=value" to an action, and its arguments are not split   #
# apart again anywhere.  So this is built from the loaded file, with the same argument model   #
# the Task editor uses -- the labels are Tasker's own -- and only the SCOPE is the Map's:     #
# whatever the Map is showing (the whole file, one Project, one Profile, one Task or one Scene)  #
# is what is written (see mapjump.current_scope).                                            #
#                                                                                        #
# WHAT IS LEFT OUT, as Tasker leaves it out: an argument the file does not hold at all, and a   #
# text argument that is empty.  An Off switch is written as Off, and a number as it is.        #
#                                                                                        #
# A Scene is not rebuilt: its layout has no one-line-per-argument form, so it is written as    #
# the Map draws it (the Map's own words for its elements, one per line), under a "Scene:" line.  #
#                                                                                        #
# THE CODE BLOCK.  Reddit has two ways to write one.  Fencing the text in three backticks works  #
# on the new site and in its Markdown editor and nowhere else; indenting every line four spaces   #
# works on old Reddit, new Reddit, the apps and the Markdown editor alike.  So the text is        #
# indented (see as_code_block).                                                           #
#                                                                                        #
# The words here ("Profile:", "Enter Task:", "On", "Off") are Tasker's, in English, and are NOT     #
# translated: they are written for the people reading a post, whatever language this runs in.      #
#                                                                                        #
# Read-only: nothing here changes the configuration.                                       #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import html
import os
import re
from typing import TYPE_CHECKING, Any

from maptasker.src.core.action import evaluate_condition
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.condjoin import boolean_operators, join_conditions
from maptasker.src.core.mapjump import (
    PROFILE,
    PROJECT,
    SCENE,
    TASK,
    Scope,
    actions_in_map_order,
    current_scope,
)
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.outdir import output_directory
from maptasker.src.core.sysconst import REDDIT_EXPORT_FILE, logger
from maptasker.src.edit.taskedit_args import build_editable_args
from maptasker.src.mapgen import condition, mapexport

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit.taskedit_model import EditableArg

# Reddit's code block: every line starts with this.
CODE_INDENT = "    "
# How far an argument hangs under its action, and how far each If/For nests its contents.
ARGUMENT_INDENT = " " * 5
NEST_INDENT = "    "
# What Tasker writes under a Profile in front of each of its conditions.
CONDITION_INDENT = "\t"
# The most Reddit will take in a post's text.
POST_LIMIT = 40000

# Flow control, by action code: the actions that open a block, close one, or close one and open the next.
_OPENS = {"37", "39"}  # If, For
_CLOSES = {"38", "40"}  # End If, End For
_ELSE = "43"  # Else, and Else If
_IF = "37"

_TAG = re.compile(r"<[^>]+>")
# A Tasker boolean the file holds: 1 is On.
_ON = {"1", "true"}


class RedditError(Exception):
    """There is nothing to write.  The message is written for the user."""


def plain(text: str) -> str:
    """`text` as the person who wrote it typed it: no tags, and no HTML entities."""
    return html.unescape(_TAG.sub("", text.replace("<br>", "\n"))).replace("\xa0", " ")


# ##################################################################################
# Arguments
# ##################################################################################
def _argument_value(arg: EditableArg) -> str | None:
    """What an argument is set to, as Tasker writes it, "" when it is empty, or None when the file does not hold it."""
    if arg.element is None:
        return None
    value = plain(arg.current_value)
    if arg.widget_kind == "checkbox":
        return "On" if value in _ON else "Off"
    options = arg.dropdown_options
    if arg.widget_kind == "dropdown" and options and not arg.is_var and value.isdigit() and int(value) < len(options):
        return plain(options[int(value)])
    return value


def argument_pairs(args: list[EditableArg]) -> list[tuple[str, str]]:
    """The (label, value) of each argument the file holds, in the order Tasker lists them."""
    pairs: list[tuple[str, str]] = []
    for arg in args:
        value = _argument_value(arg)
        if value:  # None (not in the file) and "" (nothing typed) are both left out.
            pairs.append((plain(arg.arg_name), value))
    return pairs


def bracketed(head: str, pairs: list[tuple[str, str]], indent: str = "") -> list[str]:
    """`head` followed by its arguments in square brackets, one to a line.

    No arguments is no brackets.  One short argument stays on the head's line, the way Tasker writes
    an action such as If.  A value of several lines hangs under its label.
    """
    if not pairs:
        return [f"{indent}{head}"]
    if len(pairs) == 1 and "\n" not in pairs[0][1]:
        label, value = pairs[0]
        return [f"{indent}{head} [ {label}: {value} ]"]
    lines = [f"{indent}{head} ["]
    hang = f"{indent}{ARGUMENT_INDENT}"
    for position, (label, value) in enumerate(pairs):
        first, *rest = value.split("\n")
        lines.append(f"{hang}{label}: {first}")
        lines.extend(f"{hang}{line}" for line in rest)
        if position == len(pairs) - 1:
            lines[-1] += " ]"
    return lines


def one_line(head: str, pairs: list[tuple[str, str]]) -> str:
    """`head` and its arguments on a single line, as Tasker writes a Profile's condition: "State: X [ A:1 B:2 ]"."""
    if not pairs:
        return head
    return f"{head} [ {' '.join(f'{label}:{value}'.replace(chr(10), ' ') for label, value in pairs)} ]"


# ##################################################################################
# Conditions on an action, and an If's own
# ##################################################################################
def condition_text(owner: Element) -> str:
    """The Conditions of an element's <ConditionList> as one line: "%a = 1 And %b ~ x"."""
    condition_list = owner.find("ConditionList")
    if condition_list is None:
        return ""
    texts: list[str] = []
    for item in condition_list.findall("Condition"):
        try:
            left, operator, right = evaluate_condition(item)
        except KeyError:
            logger.debug("mapreddit: a Condition with an operator that is not known")
            continue
        texts.append(plain(f"{left}{operator}{right}").strip())
    return plain(join_conditions(texts, boolean_operators(condition_list, len(texts)))).replace("AND", "and")


def _label(action: Element) -> str:
    """The label the author gave an action, or ""."""
    label = action.find("label")
    return plain(label.text or "") if label is not None else ""


# ##################################################################################
# A Task
# ##################################################################################
def _action_head(number: int, name: str, label: str) -> str:
    """ "A3: Flash", or "A3: Flash <the label>"."""
    return f"A{number}: {name} <{label}>" if label else f"A{number}: {name}"


def action_lines(action: Element, number: int, state: RunState) -> list[str]:
    """One action as Tasker writes it: its name, its label, its arguments, and a condition on it."""
    code = (action.findtext("code") or "").strip()
    entry = action_codes.get(f"{code}t")
    if entry is None:
        return [f"A{number}: Code {code}"]
    wanted = condition_text(action)
    if code in (_IF, _ELSE):
        # The test is the action's own, so it goes in the brackets rather than after them.
        name = "Else If" if code == _ELSE and wanted else entry.name
        head = _action_head(number, name, _label(action))
        return [f"{head} [ {wanted} ]" if wanted else head]
    head = _action_head(number, entry.name, _label(action))
    arguments = action_codes[entry.redirect].args if entry.redirect else entry.args
    lines = bracketed(head, argument_pairs(build_editable_args(action, arguments, state=state)))
    if wanted:
        lines[-1] += f" If [ {wanted} ]"
    return lines


def task_actions(task: Element, state: RunState) -> list[str]:
    """A Task's actions, a blank line between them, each If and For nesting what is inside it."""
    out: list[str] = []
    depth = 0
    for number, action in enumerate(actions_in_map_order(task), start=1):
        code = (action.findtext("code") or "").strip()
        if code in _CLOSES or code == _ELSE:
            depth = max(depth - 1, 0)
        indent = NEST_INDENT * depth
        out.extend(f"{indent}{line}" for line in action_lines(action, number, state=state))
        out.append("")
        if code in _OPENS or code == _ELSE:
            depth += 1
    while out and not out[-1]:
        out.pop()
    return out


def task_text(heading: str, name: str, task: Element, state: RunState) -> list[str]:
    """A Task: "Task: Name" (or "Enter Task: Name"), then its actions."""
    lines = [f"{heading}: {name}"]
    actions = task_actions(task, state=state)
    if actions:
        lines.extend(["", *actions])
    return lines


# ##################################################################################
# A Profile
# ##################################################################################
def _code_condition(item: Element, state: RunState) -> list[str]:
    """A State or an Event: its name and its arguments on one line, and a note when it is inverted."""
    code = (item.findtext("code") or "").strip()
    suffix = "s" if item.tag == "State" else "e"
    entry = action_codes.get(f"{code}{suffix}")
    if entry is None:
        return [f"{item.tag}: Code {code}"]
    arguments = action_codes[entry.redirect].args if entry.redirect else entry.args
    pairs = argument_pairs(build_editable_args(item, arguments, state=state))
    inverted = " (Inverted)" if (item.findtext("pin") or "") == "true" else ""
    return [one_line(f"{item.tag}: {entry.name}{inverted}", pairs)]


def _other_condition(item: Element) -> list[str]:
    """A Time, Day, Application or Location condition, in the words the Map uses for it."""
    writers = {
        "Time": condition.condition_time,
        "Day": condition.condition_day,
        "App": condition.condition_app,
        "Loc": condition.condition_loc,
    }
    text = " ".join(plain(writers[item.tag](item, "")).split())
    return [text] if text else []


def profile_conditions(profile: Element, state: RunState) -> list[str]:
    """Each condition a Profile starts on, one under another."""
    lines: list[str] = []
    for item in profile:
        if item.tag in ("State", "Event"):
            lines.extend(_code_condition(item, state=state))
        elif item.tag in ("Time", "Day", "App", "Loc"):
            lines.extend(_other_condition(item))
    return lines


def _task_ids(profile: Element) -> tuple[str, str]:
    """The ids of a Profile's Entry and Exit Tasks, or "" for one it does not have."""
    return (profile.findtext("mid0") or "").strip(), (profile.findtext("mid1") or "").strip()


# ##################################################################################
# The scope: which objects, in which order
# ##################################################################################
class _Writer:
    """Walks the Projects the Map shows and writes each object once."""

    def __init__(self, state: RunState, scope: Scope) -> None:
        """Remember the file's tables and what is in scope."""
        roots: dict[str, Any] = state.tasker_root_elements
        self.state = state
        self.scope = scope
        self.projects: dict[str, Any] = roots.get("all_projects") or {}
        self.profiles: dict[str, Any] = roots.get("all_profiles") or {}
        self.tasks: dict[str, Any] = roots.get("all_tasks") or {}
        self.scenes: dict[str, Any] = roots.get("all_scenes") or {}
        self.scene_text: dict[str, list[str]] | None = None
        self.sections: list[list[str]] = []
        self.written: set[str] = set()

    # ------------------------------------------------------------ the walk
    def write(self) -> list[list[str]]:
        """Every object in scope as a section of lines, in the Map's order."""
        for name, project in self.projects.items():
            self._project(name, project["xml"])
        return self.sections

    def _members(self, project: Element, tag: str) -> list[str]:
        """A Project's comma-separated member list: Profile ids, Task ids or Scene names."""
        return [piece.strip() for piece in (project.findtext(tag) or "").split(",") if piece.strip()]

    def _project(self, name: str, project: Element) -> None:
        """A Project's heading, its Profiles with their Tasks, the Tasks no Profile runs, and its Scenes."""
        if self.scope.allows(PROJECT, name):
            self.sections.append([f"Project: {name}"])
        for profile_id in self._members(project, "pids"):
            self._profile(profile_id)
        for task_id in self._members(project, "tids"):
            if task_id in self.tasks and self.scope.allows(TASK, task_id) and task_id not in self.written:
                self._task("Task", task_id)
        for scene_name in self._members(project, "scenes"):
            if self.scope.allows(SCENE, scene_name):
                self.sections.append(self._scene(scene_name))

    def _profile(self, profile_id: str) -> None:
        """A Profile, its conditions, and the Tasks it runs."""
        profile = self.profiles.get(profile_id)
        if profile is None or not self.scope.allows(PROFILE, profile_id):
            return
        element: Element = profile["xml"]
        head = [f"Profile: {profile['name']}"]
        head.extend(f"{CONDITION_INDENT}{line}" for line in profile_conditions(element, state=self.state))
        self.sections.append(head)
        entry, leave = _task_ids(element)
        for heading, task_id in (("Enter Task", entry), ("Exit Task", leave)):
            if task_id in self.tasks and self.scope.allows(TASK, task_id):
                self._task(heading, task_id)

    def _task(self, heading: str, task_id: str) -> None:
        """One Task, however many Profiles run it: written the first time, and named after that."""
        task = self.tasks[task_id]
        name = task["name"] or "(no name)"
        if task_id in self.written:
            self.sections.append([f"{heading}: {name}", "", f"{NEST_INDENT}(written above)"])
            return
        self.written.add(task_id)
        self.sections.append(task_text(heading, name, task["xml"], state=self.state))

    # ------------------------------------------------------------ scenes
    def _scene(self, name: str) -> list[str]:
        """A Scene: its name, and what the Map shows of it."""
        if self.scene_text is None:
            self.scene_text = scene_lines(self.state)
        lines = self.scene_text.get(name, [])
        return [f"Scene: {name}", *([""] if lines else []), *lines]


def scene_lines(state: RunState) -> dict[str, list[str]]:
    """{Scene name: the lines the Map draws under it}, or nothing when the Map has not been drawn."""
    path = os.path.join(str(output_directory(state=state)), mapexport.MAP_SOURCE)
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as source:
            document = source.read()
    except OSError:
        return {}
    found: dict[str, list[str]] = {}

    def visit(blocks: list[mapexport.Block]) -> None:
        for block in blocks:
            if block.kind == SCENE and block.name not in found:
                found[block.name] = _scene_body(block)
            visit(block.children)

    visit(mapexport.map_tree(mapexport.map_blocks(document)))
    return found


def _scene_body(block: mapexport.Block) -> list[str]:
    """The lines of a Scene's entry after its heading and of everything under it, with their shared indent removed."""
    lines = [*block.lines[1:]]
    for child in block.children:
        lines.extend(child.lines)
    lines = [line.rstrip() for line in lines]
    indent = min((len(line) - len(line.lstrip(" ")) for line in lines if line.strip()), default=0)
    body = [line[indent:] for line in lines]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return body


# ##################################################################################
# The whole text
# ##################################################################################
def build(state: RunState) -> str:
    """The Map's objects as Tasker's text.  Raises RedditError when there is nothing to write."""
    if not state.backup_loaded:
        message = translate_string("No XML file has been loaded.  Get an XML file first.")
        raise RedditError(message)
    sections = _Writer(state, current_scope(state)).write()
    if not sections:
        message = translate_string("There is nothing in the Map to export.")
        raise RedditError(message)
    return "\n\n".join("\n".join(section) for section in sections) + "\n"


def as_code_block(text: str) -> str:
    """`text` as a Reddit code block: every line indented four spaces, blank ones too, so the block is not cut short."""
    return "\n".join(f"{CODE_INDENT}{line}" for line in text.splitlines()) + "\n"


def export(state: RunState) -> tuple[str, str]:
    """Write the Reddit text to the Output Folder.  Answers (the path written, the text to paste)."""
    post = as_code_block(build(state))
    path = os.path.join(str(output_directory(state=state)), REDDIT_EXPORT_FILE)
    with open(path, "w", encoding="utf-8", newline="\n") as output:
        output.write(post)
    return path, post
