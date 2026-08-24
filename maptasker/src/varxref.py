"""Variable cross-reference: where every %VAR is set, and where it is read."""

#! /usr/bin/env python3

#                                                                                      #
# varxref: Build a where-used index of every Tasker variable in the loaded XML -- what  #
#          sets it, what reads it -- and report it as plain text.                       #
#                                                                                      #
# Same contract as healthck.py: everything here reads PrimeItems.tasker_root_elements   #
# and nothing else, so the index can be built the moment an XML file is loaded (no Map  #
# run required) and is testable without standing up a GUI.                              #
#                                                                                      #
# The dependency runs healthck -> varxref, never the other way: healthck calls          #
# suspects() to fold the problem classes into its own report, so nothing in here may    #
# import healthck.  The location helpers the two once each kept a private copy of now   #
# live in mapjump, which neither owns and both import -- they describe an object, and   #
# mapjump is where an object's identity lives.                                          #
#                                                                                      #
# Built in phases.  Done: the recognizer and the set/read tables derived from actionc.py #
# and bundle.py, one pass over Task actions, and the SUSPECTS section that leads the     #
# report -- near-duplicate names, read-but-never-set, set-but-never-read.                #
#                                                                                       #
# Still to come, and named in the report's own limitations so it never overstates        #
# itself: Profiles, Scenes (Legacy and Version 2) and the anonymous Tasks that live      #
# inside a Scene.  Until those land, a variable used only in one of them shows a zero    #
# here -- which is the likeliest explanation for any entry that looks wrong.             #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from maptasker.src.actionc import action_codes
from maptasker.src.bundle import bundles
from maptasker.src.globalvr import tasker_global_variables
from maptasker.src.mapjump import (
    PROFILE,
    SCENE,
    TASK,
    VARIABLE,
    Row,
    Scope,
    Target,
    actions_in_map_order,
    describe,
    text_report,
)
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import MY_VERSION, VARXREF_FILE, logger

if TYPE_CHECKING:
    import defusedxml.ElementTree  # Need for type hints

# A Tasker variable name begins with a letter and continues with letters, digits and
# underscores.  The leading-letter rule is the whole reason this is not sysconst's
# pattern12 ('[%]\w+'): that one accepts the URL percent-escapes sitting inside every
# HTTP Request argument -- '%3A' is ':', '%2F' is '/' -- and actionr's capital-letter
# filter passes the ones followed by a capital, so '%3ADropbox' and '%3AImgur' reach
# PrimeItems.variables today and are printed in the Map's variable table as though they
# were variables somebody declared.
VARIABLE_PATTERN = re.compile(r"%([A-Za-z][A-Za-z0-9_]*)")

# What a name refers to.  Only GLOBAL and LOCAL are the user's to get wrong; the other
# two are Tasker's own and are never reported as unset, however they are used.
GLOBAL = "global"
LOCAL = "local"
BUILTIN = "built-in"
TASKER_SET = "Tasker-set"

# Set by Tasker as a Task runs rather than by anything in the file.  %par1/%par2 are a
# Perform Task's parameters, %caller the Task that called this one, %evtprm the values
# from the Profile event that triggered it, %err/%errmsg the last action's failure.
TASKER_SET_PATTERN = re.compile(r"^(par\d+|caller|evtprm\d*|priority|err|errmsg|arg\d+)$")

# How a reference reads in the report.
SET = "set"
READ = "read"

# The problem classes, in the order they are reported: most trustworthy first.
NEAR_DUPLICATE = "NEAR-DUPLICATE"
NEVER_SET = "NEVER-SET"
NEVER_READ = "NEVER-READ"
_SUSPECT_ORDER = (NEAR_DUPLICATE, NEVER_SET, NEVER_READ)

# Each class's heading and the explanation that applies to every member of it.  Said once
# per class rather than once per finding: the prose does not change between them, and
# repeating it thirty times buries the names it is there to explain.
_SUSPECT_HEADINGS = {
    NEAR_DUPLICATE: (
        "NEAR-DUPLICATE NAMES",
        (
            "Two or more global names differing only in case or underscores.  Tasker",
            "treats them as separate variables, so what one spelling writes another does",
            "not read.",
        ),
    ),
    NEVER_SET: (
        "READ BUT NEVER SET",
        (
            "Something reads these, but nothing in this file sets them and none is among",
            "the output variables an action declares -- so a read sees an empty value.",
        ),
    ),
    NEVER_READ: (
        "SET BUT NEVER READ",
        (
            "Something sets these and nothing reads them, and they are not declared in",
            "Tasker's Variables tab either, so nothing is looking at them on the device.",
        ),
    ),
}

_REPORT_WIDTH = 78

# Column the "set n, read n" counts start in, so they line up down the page.
_NAME_COLUMN = 48

# Names this short collide with things that are not variables at all: strftime letters in
# a Parse/Format DateTime format, '%' wildcards in a SQL Query, printf escapes in a Run
# Shell command.  Indexed like any other name, but held out of the counted totals so they
# cannot pad the report -- see _is_low_confidence.
_LOW_CONFIDENCE_LENGTH = 2

# ##################################################################################
# Which arguments name a variable being SET.
#
# Both tables below are derived from actionc.py rather than listed by hand, the same way
# healthck._scene_name_args() derives its Scene actions, so an action added in a later
# Tasker release is covered when that file is regenerated.  What cannot be derived is
# called out explicitly underneath, with the reason.
# ##################################################################################

# Arguments that name an output variable, whatever action they belong to.  Around 115
# actions across every category carry one of these.
_WRITE_ARG_NAMES = frozenset(
    {
        "Store Result In",
        "Store Output In",
        "Store Errors In",
        "To Var",
        "Output Variable Name",
        "Store Matches In Array",
        "Formatted Variable Names",
        "Variable Array",
    },
)

# Tasker's "Variables" action category.  Within it, an argument called Name/Variable/Names
# is the variable the action acts on -- which is a write for most of them, and the
# exceptions are listed below.
_VARIABLE_CATEGORY = "120"
_CATEGORY_NAME_ARGS = frozenset({"Name", "Variable", "Names"})

# Category 120 actions whose Name/Variable argument is the SOURCE being read, not the
# target: each of these has a separate output argument (already covered by
# _WRITE_ARG_NAMES) and merely reads the variable it is named after.  Without this,
# 'Variable Section %Text From 1 Length 5 Store Result In %Head' would be recorded as
# setting %Text, and a variable that is only ever read would look healthy.
_SOURCE_NOT_TARGET = {
    "393": {"1"},  # Arrays Merge -- 'Names' are the input arrays, output is arg5/arg6.
    "448": {"1"},  # Array Compare -- ditto.
    "596": {"0"},  # Variable Convert -- target is 'Store Result In'.
    "597": {"0"},  # Variable Section -- ditto.
    "598": {"0"},  # Variable Search Replace -- target is 'Store Matches In Array'.
}

# ...except that three of those write back into their source when the output argument is
# left empty (Variable Convert and Variable Section), or when Replace Matches is ticked
# (Variable Search Replace).  {code: (source arg, deciding arg)}: when the deciding
# argument is empty -- or, for 598, when it is NOT empty -- the source is a write too.
_WRITES_BACK_WHEN_EMPTY = {"596": ("0", "2"), "597": ("0", "4")}
_REPLACES_IN_PLACE = ("598", "0", "6")

# Write targets no naming rule can find.
_EXTRA_WRITE_ARGS = {
    # For: the loop variable is assigned on every iteration.  Its argument is called
    # 'Variable', but the action sits in the Task Handling category, not Variables, so
    # the category rule above cannot see it -- and a For loop is one of the commonest
    # ways a variable gets set at all.
    "39": {"0"},
    # Arrays Merge: the merged result and the joined string.  Named 'Output' and 'Join
    # Output', which are too generic to add to _WRITE_ARG_NAMES -- 'Output File',
    # 'Output Format' and 'Output Minimum' are all file names and numbers.
    "393": {"5", "6"},
}

# What a resolvable write target looks like: one plain name, optionally with an array
# subscript or a structure member after it.  'Variable Set %Row(%i)' names %Row and can be
# indexed; 'Variable Set %(%which)' and 'Variable Set %pre%post' compute their target on the
# device and name no variable this scan can resolve.
_PLAIN_TARGET = re.compile(r"%[A-Za-z][A-Za-z0-9_]*(\(.*\)|\..*)?$")

# A Profile's own bookkeeping, as opposed to a context that tests something.  Everything
# not listed here is treated as a context and read for its arguments, so a context type
# added in a later Tasker release is covered without this module being touched.
_PROFILE_NON_CONTEXT_TAGS = frozenset(
    {"cdate", "edate", "flags", "id", "limit", "mid0", "mid1", "nme", "pri", "cldm", "pc"},
)

# {Legacy Scene element: the argument holding its value}.  A value field is a two-way
# binding -- the Scene shows what the variable holds and writes back what the user does.
#
# Deliberately short.  EditText's arg1 and Slider's arg4 are the two confirmed by real
# Scenes (an EditText carries '%aab_form2b' there, a Slider '<var>%AAB_ScaleTaperMidpoint');
# CheckBox and Switch are read from their argument shape, a label in arg0 and a single
# state in arg1 and nothing else.  The other input types are left out rather than guessed
# at, because the cost is asymmetric: a wrong entry here records a set that never happens
# and silently suppresses a real "read but never set", while a missing one only leaves a
# variable looking unset, which the limitations already warn about.
_LEGACY_VALUE_ARGS = {
    "EditTextElement": "1",
    "SliderElement": "4",
    "CheckBoxElement": "1",
    "SwitchElement": "1",
}

# Version 2 component properties that bind two-way, the same as a Legacy value field: a
# TextInput's "value" is both what it displays and where what the user types is put.
_V2_VALUE_KEYS = frozenset({"value", "checked"})

# Arguments holding SEVERAL variable names at once, separated by a splitter the user
# chooses.  Everywhere else the first name in a write argument is the target and any
# further ones are subscripts being read (see _record_write); here every name is a target.
_PLURAL_WRITE_ARGS = frozenset({("389", "1"), ("394", "7")})


# A variable named at the very start of a RELEVANT_VARIABLES entry, which is where the
# output variable itself sits: each entry reads "%name\nDisplay Name\nDescription", and the
# description is prose that mentions other variables ("similar to %TIMES").  Anchoring on
# the array element's closing bracket is what keeps those mentions out.
_RELEVANT_VARIABLE = re.compile(r"&gt;%([A-Za-z][A-Za-z0-9_]*)")


def _relevant_variable_blobs(node: object) -> list[str]:
    """Every RELEVANT_VARIABLES value inside one bundle entry, at whatever depth it sits."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key.endswith("RELEVANT_VARIABLES") and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_relevant_variable_blobs(value))
    return found


def _implicit_writes() -> dict[str, set[str]]:
    """{action code: the variables it sets without naming them in any argument}.

    A plugin, and a good many of Tasker's own actions, set their output variables without
    mentioning them anywhere in the action -- an HTTP Request sets %http_data, Get
    Material You Colors sets forty %my_* colours.  What each one produces is declared in
    its <Bundle> as RELEVANT_VARIABLES, which bldbndle.py has already collected into
    bundle.py for 142 action codes and 643 names.

    Without this, every one of those names reads as "used but nothing sets it", and the
    problem list is 499 entries of Tasker working exactly as intended.  With it, 18.
    """
    table = {}
    for key, entry in bundles.items():
        # 'e'/'s' keys are Profile events and states, which set nothing.
        if not key.endswith("t"):
            continue
        names = set()
        for blob in _relevant_variable_blobs(entry):
            names.update(f"%{match.group(1)}" for match in _RELEVANT_VARIABLE.finditer(blob))
        if names:
            table[key[:-1]] = names
    return table


def _write_arguments() -> dict[str, set[str]]:
    """{action code: set of arg ids} for every argument that names a variable being set."""
    table: dict[str, set[str]] = defaultdict(set)

    for key, action in action_codes.items():
        # 'e'/'s' keys are Profile events and states, which set nothing.
        if not key.endswith("t"):
            continue
        code = key[:-1]
        for argument in action.args or ():
            name = argument.arg_name or ""
            in_category = action.category == _VARIABLE_CATEGORY and name in _CATEGORY_NAME_ARGS
            if (name in _WRITE_ARG_NAMES or in_category) and argument.arg_id not in _SOURCE_NOT_TARGET.get(code, ()):
                table[code].add(argument.arg_id)

    for code, arg_ids in _EXTRA_WRITE_ARGS.items():
        table[code].update(arg_ids)

    return table


# ##################################################################################
# The index.
# ##################################################################################
@dataclass
class Reference:
    """One place a variable is set or read."""

    role: str  # SET or READ
    where: str  # "Project 'Home' > Task 'Wake Up' (id 118) action 4"
    detail: str  # "Variable Set, Name=" / "if lhs" / "Flash, Text="
    scope_id: str  # what owns the scope a local here belongs to (see VariableIndex.entry)
    # The same place as `where`, in the form the Map view can find (mapjump).  `where` is
    # what the report prints and what two references are deduplicated on; this is where a
    # click on that line goes.
    target: Target | None = None
    # The element whose .text holds this value.  Nothing in this module reads it -- a
    # report prints `where` and `detail` -- but mapswap rewrites the places this scan
    # finds, and a second walk written to go and fetch the elements again would be a
    # second definition of "everywhere a variable appears" to keep in step with this one.
    # None where there is nothing to rewrite: an output variable a plugin declares through
    # RELEVANT_VARIABLES is named nowhere in the file.
    element: defusedxml.ElementTree.Element | None = None
    # Version 2 Scenes only, whose values live inside a gzipped JSON blob rather than in
    # an element: (component path, property key), which sceneedit.v2_node_at resolves
    # against a freshly decoded layout.  `element` is the <Scene> itself for these.
    path: tuple = ()


@dataclass
class Variable:
    """One variable and everywhere it is used.

    A global is one variable across the whole file.  A local is one variable PER TASK --
    Tasker scopes an all-lowercase name to the running Task, and in a real backup to hand
    525 of 1523 local names appear in more than one Task.  Keying them together would
    merge a few hundred unrelated %i and %result into one entry, and report every one of
    them as healthy.  owner is what keeps them apart.
    """

    name: str
    scope: str
    owner: str = ""  # locals only; "" for everything else
    value: str = ""  # from a top-level <Variable>, when the file declares one
    declared: bool = False
    sets: list[Reference] = field(default_factory=list)
    reads: list[Reference] = field(default_factory=list)


@dataclass
class VariableIndex:
    """Every variable in the file, keyed by scope-aware identity."""

    variables: dict[tuple[str, str], Variable] = field(default_factory=dict)
    # Names carrying a top-level <Variable>.  Tasker's Variables tab holds globals and
    # nothing else, so a declared name is global whatever its spelling -- and it has to be
    # known before the scan starts, or a lower case one would be keyed as a local by the
    # first Task that touched it and split into a separate entry per Task.
    declared_names: set[str] = field(default_factory=set)
    # Actions naming their target through a variable ("Variable Set %(%which)") or
    # building a name at run time.  Any of them could be setting any variable in the
    # file, so a non-zero count qualifies every "never set" answer -- the same way
    # healthck's variable_scene_references qualifies UNUSED-SCENE.
    indirect_references: int = 0
    tasks_scanned: int = 0
    actions_scanned: int = 0
    profiles_scanned: int = 0
    scenes_scanned: int = 0
    # Task id -> the place it is, so the locals section can be grouped by Task without
    # re-deriving the phrase per variable.  Targets rather than phrases since it is both:
    # .label is the phrase, and the Target is what makes the group heading clickable.
    scope_locations: dict[str, Target] = field(default_factory=dict)
    # What the scan was limited to.  Named `scope` to match mapfind.FindIndex; not to be
    # confused with scope_locations or with a VARIABLE's scope (global/local), which is a
    # different thing entirely and older -- this one is "which objects were looked at".
    scope: Scope = field(default_factory=Scope)

    def _scope_for(self, name: str) -> str:
        """This name's scope, with what the file itself says taking precedence.

        Tasker's documented built-in list wins outright -- %BATT is Tasker's whatever a
        file claims.  A declared name comes next: scope_of falls back to the shape of a
        name, and that shape reads an all upper case global somebody wrote themselves
        (%ADSKIPLOOP, %AOD) as a built-in.  A <Variable> element settles it, because
        Tasker's Variables tab holds nothing but globals.
        """
        if name in tasker_global_variables:
            return BUILTIN
        return GLOBAL if name in self.declared_names else scope_of(name)

    def entry(self, name: str, scope_id: str) -> Variable:
        """The Variable record for this name, created on first sight.

        Locals are keyed (name, scope_id); everything else is keyed (name, "").

        scope_id is a Task id for a reference inside a Task, and "scene:<name>" or
        "profile:<id>" for one in a Scene or a Profile context.  A lower case name in a
        Scene is not a Task's local -- no Task owns it, and two Scenes each using %row are
        no more the same variable than two Tasks are.  Keying them to the Scene keeps them
        apart, and lets the report group them under it.
        """
        scope = self._scope_for(name)
        owner = scope_id if scope == LOCAL else ""
        key = (name, owner)
        if key not in self.variables:
            self.variables[key] = Variable(name=name, scope=scope, owner=owner)
        return self.variables[key]


def _looks_built_in(body: str) -> str:
    """Whether an undocumented name still has the shape of one of Tasker's own.

    globalvr's list was transcribed from a page that predates %HUMIDITY, %SDK, %ROOT and
    the %DEV*/%CAL* families, so the all-upper-case shape is needed to catch those.  The
    no-underscore half of the test is what stops the shape swallowing the user's own
    SHOUTING globals: not one of the 101 documented built-ins contains an underscore,
    while %DATA_POINTS, %TIME_LABELS and %BRIGHTNESS_LABELS in a real backup to hand are
    all somebody's own variables.  Misfiling one as a built-in hides it from every check
    here, because a built-in is never reported as unset.
    """
    return len(body) > 1 and body.isupper() and "_" not in body


def scope_of(name: str) -> str:
    """Which kind of variable a name is, by Tasker's own rule.

    Tasker decides scope from the name and nothing else: at least one upper case letter
    makes it global, all lower case makes it local to the running Task.
    """
    body = name[1:] if name.startswith("%") else name
    if f"%{body}" in tasker_global_variables or _looks_built_in(body):
        return BUILTIN
    if TASKER_SET_PATTERN.match(body):
        return TASKER_SET
    return GLOBAL if any(character.isupper() for character in body) else LOCAL


def _is_low_confidence(name: str) -> bool:
    """Whether a name is too short to be told apart from text that merely holds a '%'."""
    return len(name) - 1 <= _LOW_CONFIDENCE_LENGTH


# ##################################################################################
# Reading the XML.
# ##################################################################################
def _element_text(element: defusedxml.ElementTree.Element, tag: str) -> str:
    """The text of a child element, stripped, or "" if it is missing or empty."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _describe_task(name: str, task_id: str) -> str:
    """Task 'Wake Up' (id 118), or Task (id 118) [unnamed]."""
    return describe("Task", name, task_id)


def _project_membership(tag: str) -> dict[str, str]:
    """{member: owning Project name} for one of a Project's comma-separated member lists.

    Built in one pass rather than by calling maputils.find_owning_project per object: that
    one walks every Project, which would make the whole scan quadratic on a large backup.

    The filter on empty items matters -- Tasker writes an empty list as an empty element,
    and "".split(",") is [""], which would otherwise claim a Project owns an object whose
    id is the empty string.
    """
    owners = {}
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        text = _element_text(project["xml"], tag)
        for member in (item.strip() for item in text.split(",") if item.strip()):
            owners[member] = project_name
    return owners


def _project_of_task() -> dict[str, str]:
    """{task id: owning Project name}, from each Project's <tids>."""
    return _project_membership("tids")


def _project_of_profile() -> dict[str, str]:
    """{profile id: owning Project name}, from each Project's <pids>."""
    return _project_membership("pids")


def _project_of_scene() -> dict[str, str]:
    """{scene name: owning Project name}.  A Project lists Scenes by NAME, not by id."""
    return _project_membership("scenes")


def _string_arguments(action: defusedxml.ElementTree.Element) -> dict[str, str]:
    """{arg id: text} for one action's or Scene element's arguments.

    Matched on the "sr" attribute rather than child order, which Tasker does not
    guarantee -- the same way taskedit.py and healthck.py reach an argument.

    Covers both shapes an argument can take.  A text argument is <Str sr="argN">, but an
    argument Tasker expects a NUMBER in holds <Int sr="argN"><var>%Volume</var></Int> when
    the user has bound a variable to it instead of typing a figure.  Reading only the <Str>
    children missed 833 of those in a real backup to hand, across 70 names -- every
    variable driving a volume, a delay, a slider position or a screen brightness.
    """
    arguments = {}
    for child in action.findall("Str"):
        sr = child.attrib.get("sr", "")
        if sr.startswith("arg"):
            arguments[sr[3:]] = child.text or ""
    for child in action.findall("Int"):
        sr = child.attrib.get("sr", "")
        bound = child.find("var")
        if sr.startswith("arg") and bound is not None and bound.text:
            # setdefault, not assignment: an argument is one or the other, and the <Str>
            # reading is the one to keep if a file ever carries both.
            arguments.setdefault(sr[3:], bound.text)
    return arguments


def _argument_elements(node: defusedxml.ElementTree.Element) -> dict:
    """{arg id: the element whose .text holds the value} -- what _string_arguments reads.

    Deliberately the same two shapes, in the same precedence, as that function: these two
    have to agree about what an argument is, or a reference would be recorded against one
    element and rewritten in another.

    The <Int> case is why this is not simply "the child carrying that sr": a numeric
    argument the user has bound a variable to holds it in a <var> child, so the <var> is
    the element a rewrite has to touch, not the <Int> around it.
    """
    elements = {}
    for child in node.findall("Str"):
        sr = child.attrib.get("sr", "")
        if sr.startswith("arg"):
            elements[sr[3:]] = child
    for child in node.findall("Int"):
        sr = child.attrib.get("sr", "")
        bound = child.find("var")
        if sr.startswith("arg") and bound is not None and bound.text:
            elements.setdefault(sr[3:], bound)
    return elements


def _argument_label(code: str, arg_id: str) -> str:
    """ "Variable Set, Name=" -- the action and the argument a reference was found in.

    Both halves come out of actionc.py, so a reference names the argument the way Tasker's
    own action editor labels it, rather than as "arg0".
    """
    action = action_codes.get(f"{code}t")
    action_name = action.name if action else f"code {code}"
    if action:
        for argument in action.args or ():
            if argument.arg_id == arg_id:
                return f"{action_name}, {argument.arg_name}=" if argument.arg_name else action_name
    return action_name


# ##################################################################################
# The scan.
# ##################################################################################
def _record_write(
    index: VariableIndex,
    text: str,
    reference: Reference,
    plural: bool,
    also_read: bool = False,
) -> None:
    """Record the variables a write argument names.

    In a plural argument ('Multiple Variables Set', Names=) every name is a target.
    Everywhere else the FIRST name is the target and any further ones are subscripts or
    indirection being read: 'Variable Set %Row(%i)' sets %Row and reads %i.

    An argument whose target is itself a variable ('%(%which)', or a name built from one)
    cannot be resolved here, so it is counted rather than guessed at -- see
    VariableIndex.indirect_references.

    also_read marks the in-place actions, whose target is read as well as written.  It is
    handled here rather than by the caller calling _record_reads over the same text, which
    would count every subscript in it as a read twice over.
    """
    matches = list(VARIABLE_PATTERN.finditer(text))
    if not matches:
        return

    # A plural argument holds a list of targets, so the single-target shape does not apply
    # to it.  Anywhere else, a target that is not one plain name is computed on the device.
    if not plural and not _PLAIN_TARGET.fullmatch(text.strip()):
        index.indirect_references += 1

    for position, match in enumerate(matches):
        name = f"%{match.group(1)}"
        entry = index.entry(name, reference.scope_id)
        read_here = Reference(
            READ,
            reference.where,
            reference.detail,
            reference.scope_id,
            reference.target,
            reference.element,
            reference.path,
        )
        if plural or position == 0:
            entry.sets.append(reference)
            if also_read:
                entry.reads.append(read_here)
        else:
            entry.reads.append(read_here)


def _record_reads(index: VariableIndex, text: str, reference: Reference) -> None:
    """Record every variable named in a plain argument, a condition side or a Bundle."""
    for match in VARIABLE_PATTERN.finditer(text):
        index.entry(f"%{match.group(1)}", reference.scope_id).reads.append(reference)


def _scan_action(
    index: VariableIndex,
    action: defusedxml.ElementTree.Element,
    place: Target,
    scope_id: str,
    write_arguments: dict[str, set[str]],
    implicit_writes: dict[str, set[str]],
) -> None:
    """Record every variable one action sets or reads.

    'place' is where this action is, as both the phrase the report prints (its .label) and
    the identity a click on that line jumps to.
    """
    where = place.label
    code = _element_text(action, "code")
    if not code:
        return

    # The output variables this action produces without naming them anywhere.  Marked as
    # such in the report: "set by" pointing at an action that never mentions the variable
    # is otherwise the sort of claim a user has no way to check.
    for name in implicit_writes.get(code, ()):
        index.entry(name, scope_id).sets.append(
            Reference(SET, where, f"{_argument_label(code, '')} (output variable)", scope_id, place),
        )

    arguments = _string_arguments(action)
    argument_elements = _argument_elements(action)
    targets = write_arguments.get(code, set())

    # An in-place action writes back into the variable it reads, but only in one
    # configuration of its own arguments -- so the deciding argument has to be looked at
    # before its source can be called a write.
    writes_back = set()
    if code in _WRITES_BACK_WHEN_EMPTY:
        source, decider = _WRITES_BACK_WHEN_EMPTY[code]
        if not arguments.get(decider, "").strip():
            writes_back.add(source)
    if code == _REPLACES_IN_PLACE[0] and arguments.get(_REPLACES_IN_PLACE[2], "").strip():
        writes_back.add(_REPLACES_IN_PLACE[1])

    for arg_id, text in arguments.items():
        if not text:
            continue
        detail = _argument_label(code, arg_id)
        if arg_id in targets or arg_id in writes_back:
            # A source that is written back is read as well -- that is what "in place"
            # means, and recording only the write would make it look like a variable that
            # springs from nowhere.
            _record_write(
                index,
                text,
                Reference(SET, where, detail, scope_id, place, argument_elements.get(arg_id)),
                plural=(code, arg_id) in _PLURAL_WRITE_ARGS,
                also_read=arg_id in writes_back,
            )
        else:
            _record_reads(index, text, Reference(READ, where, detail, scope_id, place, argument_elements.get(arg_id)))

    # A plugin action keeps its configuration in a <Bundle> rather than in <Str> arguments,
    # and 1741 actions in a real backup to hand carry one.  Every variable named in there is
    # something the plugin reads when it runs, so a global referenced only from a plugin's
    # configuration would otherwise read as never used.  Reads only: what a plugin SETS it
    # does not name here, it declares through RELEVANT_VARIABLES (phase 3).
    bundle = action.find("Bundle")
    if bundle is not None:
        label = f"{_argument_label(code, '')} (plugin configuration)"
        for element in bundle.iter():
            if element.text:
                _record_reads(index, element.text, Reference(READ, where, label, scope_id, place, element))

    # The action's own condition -- 'If %HearMute Is Not Set'.  These live in <lhs>/<rhs>
    # rather than in an <Str sr="argN">, and skipping them loses a large share of every
    # read in a real configuration.
    for condition in action.iter("Condition"):
        for tag in ("lhs", "rhs"):
            side_element = condition.find(tag)
            side = (side_element.text or "").strip() if side_element is not None else ""
            if side:
                _record_reads(index, side, Reference(READ, where, f"if {tag}", scope_id, place, side_element))

    index.actions_scanned += 1


# ##################################################################################
# Profiles and Scenes.
# ##################################################################################
def _scan_conditions(
    index: VariableIndex,
    element: defusedxml.ElementTree.Element,
    where: str,
    scope_id: str,
    place: Target | None = None,
) -> None:
    """Record the variables named on either side of every condition under an element."""
    for condition in element.iter("Condition"):
        for tag in ("lhs", "rhs"):
            side_element = condition.find(tag)
            side = (side_element.text or "").strip() if side_element is not None else ""
            if side:
                _record_reads(index, side, Reference(READ, where, f"condition {tag}", scope_id, place, side_element))


def _scan_profiles(index: VariableIndex, owners: dict[str, str], scope: Scope) -> None:
    """Record what a Profile's contexts read.

    A Profile context tests the world; it does not assign to anything, so everything here
    is a read.  The one exception is <ProfileVariable>, Tasker's Profile Variables feature,
    which declares a variable and gives it a value -- that is recorded as a set.

    Contexts are walked generically rather than by tag (<State>, <Event>, <App>, <Time>,
    <Day>, <Share>...): they all hold their arguments the same way, a new Tasker release
    can add another, and a context this app has never heard of still reads its variables
    out of <Str sr="argN"> like every other.
    """
    for profile_id, profile in PrimeItems.tasker_root_elements["all_profiles"].items():
        if not scope.allows(PROFILE, profile_id):
            continue
        place = Target(PROFILE, profile_id, profile["name"], owners.get(profile_id, ""))
        where = place.label
        scope_id = f"profile:{profile_id}"
        index.scope_locations[scope_id] = place
        index.profiles_scanned += 1

        for context in profile["xml"]:
            if context.tag in _PROFILE_NON_CONTEXT_TAGS:
                continue
            if context.tag == "ProfileVariable":
                name = _element_text(context, "pvn")
                if VARIABLE_PATTERN.fullmatch(name):
                    entry = index.entry(name, scope_id)
                    entry.sets.append(Reference(SET, where, "Profile Variable", scope_id, place))
                continue

            label = f"{context.tag} context"
            context_elements = _argument_elements(context)
            for arg_id, text in _string_arguments(context).items():
                if text:
                    _record_reads(
                        index,
                        text,
                        Reference(READ, where, label, scope_id, place, context_elements.get(arg_id)),
                    )
            _scan_conditions(index, context, where, scope_id, place)


def _scan_legacy_scene(
    index: VariableIndex,
    scene: dict,
    place: Target,
    scope_id: str,
    sceneedit: object,
) -> None:
    """Record what a Legacy Scene's elements read, and what its input elements write.

    An input element's value field is a TWO-WAY binding: the Scene shows what the variable
    holds and writes back what the user types or slides.  Recording only the read would
    leave a variable that a Scene is the only setter of looking as though nothing sets it,
    which is exactly the false alarm this whole section exists to remove.

    .iter() rather than direct children, for the reason healthck gives: a Legacy element
    can hold another (every element here carries a RectElement background), and a binding
    on a nested one is every bit as real.
    """
    where = place.label
    for element in scene["xml"].iter():
        if not element.tag.endswith("Element"):
            continue
        label = sceneedit.legacy_element_label(element)
        value_arg = _LEGACY_VALUE_ARGS.get(element.tag)
        value_elements = _argument_elements(element)
        for arg_id, text in _string_arguments(element).items():
            if not text:
                continue
            if arg_id == value_arg:
                detail = f"{label} value (two-way)"
                _record_write(
                    index,
                    text,
                    Reference(SET, where, detail, scope_id, place, value_elements.get(arg_id)),
                    plural=False,
                    also_read=True,
                )
            else:
                _record_reads(index, text, Reference(READ, where, label, scope_id, place, value_elements.get(arg_id)))


def _v2_strings(value: object) -> list[str]:
    """Every string inside one V2 property's value, however deeply it nests."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _v2_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _v2_strings(item)]
    return []


def _scan_v2_scene(
    index: VariableIndex,
    scene: dict,
    place: Target,
    scope_id: str,
    sceneedit: object,
) -> None:
    """Record what a Version 2 Scene's components read and write.

    A V2 Scene keeps its components in a gzipped JSON blob rather than in child elements,
    so this walks the decoded layout.  Each component is scanned for its OWN properties
    only -- child slots are skipped, because a node's dict contains its whole subtree and
    counting that would report every variable once per ancestor, which on a 53-component
    Scene means a variable read once looking read six times.
    """
    layout = sceneedit.decode_v2_layout(scene["xml"])
    # None means an <lj> that would not decode.  Guessing at a corrupt layout would
    # invent references, so there is nothing to do here.
    if layout is None:
        return

    where = place.label
    for row in sceneedit.v2_flatten(layout):
        child_slots = {slot for slot, _ in sceneedit.v2_child_slots(row.node)}
        for key, value in row.node.items():
            if key in child_slots:
                continue
            for text in _v2_strings(value):
                if "%" not in text:
                    continue
                label = f"component '{row.label}' {key}"
                # (component path, property key) rather than an element: the value sits
                # inside the gzipped JSON of <lj>, and the decoded layout this loop is
                # walking is a throwaway -- a reference into it would address nothing by
                # the time anybody wanted to write to it.  The path survives a re-decode.
                where_in_layout = (row.path, key)
                if key in _V2_VALUE_KEYS:
                    # Same two-way binding as a Legacy input element: a TextInput's value
                    # is both what it shows and where what the user types goes.
                    _record_write(
                        index,
                        text,
                        Reference(SET, where, label, scope_id, place, scene["xml"], where_in_layout),
                        plural=False,
                        also_read=True,
                    )
                else:
                    _record_reads(
                        index,
                        text,
                        Reference(READ, where, label, scope_id, place, scene["xml"], where_in_layout),
                    )


def _scan_scenes(index: VariableIndex, write_arguments: dict, implicit_writes: dict, scope: Scope) -> None:
    """Walk every Scene: its elements, and the anonymous Tasks living inside it.

    sceneedit is imported here rather than at module scope, and passed down rather than
    re-imported per Scene, for the reason healthck._index_scenes gives: it is the Scene
    editor, nothing else here needs it, and keeping the dependency inside the one function
    that uses it leaves varxref importable on its own.
    """
    from maptasker.src import sceneedit  # noqa: PLC0415

    owners = _project_of_scene()
    for scene_name, scene in PrimeItems.tasker_root_elements["all_scenes"].items():
        if not scope.allows(SCENE, scene_name):
            continue
        place = Target(SCENE, scene_name, scene_name, owners.get(scene_name, ""))
        scope_id = f"scene:{scene_name}"
        index.scope_locations[scope_id] = place
        index.scenes_scanned += 1

        # <lj> is the whole V2 test, in both directions (see sceneedit.is_v2_scene).
        if scene["xml"].find("lj") is not None:
            _scan_v2_scene(index, scene, place, scope_id, sceneedit)
        else:
            _scan_legacy_scene(index, scene, place, scope_id, sceneedit)

        # A truly anonymous task -- one created inline on a Scene element -- lives inside
        # the Scene as <Action> children rather than as a top-level <Task>, so the walk
        # over all_tasks never sees it.  Its actions set and read variables exactly as a
        # named Task's do.
        inline = place.with_text("inline Task")
        for number, action in enumerate(scene["xml"].iter("Action"), start=1):
            _scan_action(
                index,
                action,
                inline.at_action(number),
                scope_id,
                write_arguments,
                implicit_writes,
            )


def _scan_declarations(index: VariableIndex) -> None:
    """Record the top-level <Variable> elements: a name exists, with a value.

    Neither a set nor a read.  A declared variable holds whatever Tasker last stored in
    it, which is why a global that nothing in the file sets is still not necessarily a
    mistake -- it may simply have been given its value by hand in Tasker's Variables tab.
    """
    root = PrimeItems.xml_root
    if root is None:
        return
    for element in root.findall("Variable"):
        children = list(element)
        if not children:
            continue
        name = (children[0].text or "").strip()
        if not VARIABLE_PATTERN.fullmatch(name):
            continue
        index.declared_names.add(name)
        entry = index.entry(name, "")
        entry.declared = True
        entry.value = (children[1].text or "").strip() if len(children) > 1 and children[1].text else ""


def build_index(scope: Scope | None = None) -> VariableIndex:
    """Scan the loaded configuration and return the where-used index.

    Scans EVERYTHING by default, and that default is load-bearing rather than merely
    convenient.  Two of the three callers must see the whole file whatever the app happens
    to be displaying:

      healthck folds suspects() into its own report, and its report is about the whole
      configuration.  Worse than the inconsistency, a scoped index would make its findings
      wrong: "read but never set" is decided by not having seen a setter, and narrowed to
      one Task nearly every global in the file becomes a false alarm.

      globalvr builds the standalone Variable Cross-Reference report, which is a
      whole-file document by definition.

    Only the rename passes a scope, because only the rename is about to WRITE, and what it
    may write to is what the user can see.  Pass mapjump.current_scope() for that.

    Safe to call with nothing loaded -- the tables are empty and the report says so.
    """
    scope = scope if scope is not None else Scope()
    index = VariableIndex(scope=scope)
    write_arguments = _write_arguments()
    implicit_writes = _implicit_writes()
    owners = _project_of_task()

    _scan_declarations(index)

    for task_id, task in PrimeItems.tasker_root_elements["all_tasks"].items():
        if not scope.allows(TASK, task_id):
            continue
        place = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        index.scope_locations[task_id] = place
        index.tasks_scanned += 1

        for number, action in enumerate(actions_in_map_order(task["xml"]), start=1):
            _scan_action(
                index,
                action,
                place.at_action(number),
                task_id,
                write_arguments,
                implicit_writes,
            )

    _scan_profiles(index, _project_of_profile(), scope)
    _scan_scenes(index, write_arguments, implicit_writes, scope)

    _reclassify_written_built_ins(index)
    return index


def _reclassify_written_built_ins(index: VariableIndex) -> None:
    """Promote a shape-guessed built-in that this file writes to into a plain global.

    Tasker's own variables are things it reports, not things a configuration assigns, so a
    name only GUESSED to be built-in from its upper case shape cannot be one if an action
    in this very file sets it -- %AOD and %BODY in a real backup to hand are set twice and
    once, and are plainly somebody's own.  Names on the documented list are left alone
    however they are used: %BATT is Tasker's whatever a file does with it.

    Done after the scan rather than during it, which is safe here and only here: both
    scopes key on (name, ""), so nothing has to be re-keyed.  A local could not be
    reclassified this way -- it is keyed per Task.
    """
    for variable in index.variables.values():
        if variable.scope == BUILTIN and variable.sets and variable.name not in tasker_global_variables:
            variable.scope = GLOBAL


# ##################################################################################
# The problem classes.
#
# Every one of these is a filter over the finished index, and every filter here exists to
# throw away a kind of finding that is technically true and useless.  A section a user
# learns to skip is worse than no section, so the thresholds below are chosen from what a
# real configuration actually contains rather than from what is easy to compute.
# ##################################################################################
@dataclass
class Suspect:
    """One reportable problem.

    Carries both shapes it gets rendered in.  'summary' is the one-line form the report
    uses where a class has many members and one shared explanation -- thirty NEVER-SET
    entries each repeating the same three lines of prose is ninety lines saying one thing.
    'detail' is the block form, for a finding whose evidence is the point.
    """

    tag: str
    subject: str  # "%SheetID / %SheetId" or "%wDND"
    summary: str  # "read 6 times in 3 Tasks"
    detail: list[str]  # evidence, one line each, rendered under the subject
    sentence: str = ""  # the whole finding on one line, for a caller with no room for a block
    # Every variable this finding is about, in subject order -- one for most classes, two
    # for a near-duplicate.  What a click on the subject line goes to.
    variables: list[Target] = field(default_factory=list)
    # Where the "first at" evidence lines point, one per line of `detail` that names a
    # place (None for a line that is prose).  Kept parallel to `detail` so the renderer
    # can pair them off without parsing the text back.
    places: list[Target | None] = field(default_factory=list)


@dataclass
class _Totals:
    """One name's counts, added up across every entry carrying it.

    Locals are indexed once per Task, so a name used in five Tasks is five entries and the
    problem classes, which ask about the NAME, need them added up.

    read_tasks/set_tasks count distinct Tasks rather than references, which is the number
    worth printing: "read 5 times" could be one Task in a loop, while "read in 4 Tasks" is
    four places a person has to go and look.
    """

    scope: str
    sets: int = 0
    reads: int = 0
    declared: bool = False
    read_tasks: set[str] = field(default_factory=set)
    set_tasks: set[str] = field(default_factory=set)
    first_set: str = ""
    first_read: str = ""
    # The same two places, in the form the Map view can find (mapjump), so a report line
    # reading "first at Task 'Wake Up' (id 118) action 4" can be clicked.
    first_set_target: Target | None = None
    first_read_target: Target | None = None


def _totals_by_name(index: VariableIndex) -> dict[str, _Totals]:
    """Every distinct NAME in the file, with its counts added up across scopes."""
    totals: dict[str, _Totals] = {}
    for variable in sorted(index.variables.values(), key=lambda item: item.owner):
        total = totals.setdefault(variable.name, _Totals(scope=variable.scope))
        total.sets += len(variable.sets)
        total.reads += len(variable.reads)
        total.declared = total.declared or variable.declared
        total.read_tasks.update(reference.scope_id for reference in variable.reads)
        total.set_tasks.update(reference.scope_id for reference in variable.sets)
        if not total.first_set and variable.sets:
            total.first_set = variable.sets[0].where
            total.first_set_target = variable.sets[0].target
        if not total.first_read and variable.reads:
            total.first_read = variable.reads[0].where
            total.first_read_target = variable.reads[0].target
    return totals


def _sentence_case(text: str) -> str:
    """Upper case the first letter and leave the rest alone.

    str.capitalize() lower cases everything after the first character, which turns
    "read 6 times in 3 Tasks" into "...3 tasks" -- Tasker's objects are capitalised
    throughout this app's output, and demoting them mid-sentence reads as a typo.
    """
    return text[:1].upper() + text[1:]


def _times(references: int, tasks: int, role: str) -> str:
    """ "read 5 times in 4 Tasks" -- or just "read 5 times" when they are all in one.

    The Task count is the number that says how much work a fix is; the reference count on
    its own cannot tell one Task looping from four Tasks each doing it once.
    """
    plural = "" if references == 1 else "s"
    return f"{role} {references} time{plural}" + (f" in {tasks} Tasks" if tasks > 1 else "")


def _fold(name: str) -> str:
    """The key two names collide under: case and underscores ignored.

    Underscores go too, so %track_id and %trackId land together -- switching between
    snake_case and camelCase half way through a Project is the same mistake as switching
    case, and produces the same silently empty variable.
    """
    return name.lower().replace("_", "")


def _near_duplicates(totals: dict[str, _Totals]) -> list[Suspect]:
    """Names that differ only in case or underscores, where that is likely a mistake.

    The threshold is the whole check.  Folding names case-insensitively finds 87 clusters
    in a real backup to hand, and 83 of them are Tasker's own documented idiom: a global
    and the lower case local a Task copies it into, %AAB_AnimSteps beside %aab_animsteps,
    deliberately, dozens of times.  Reporting those would bury the two genuine bugs and
    teach the user to skip the section.

    So a cluster is only reported when TWO OR MORE of its names are global.  A global with
    its own local is idiom; two globals differing only in case are two variables where the
    user believes there is one.  That takes 87 clusters to 4, of which two are real bugs.
    Built-ins deliberately do not count toward the threshold: all 17 clusters containing
    one in that same backup are %TIMES beside %times -- the identical idiom.
    """
    clusters: dict[str, list[str]] = defaultdict(list)
    for name, total in totals.items():
        if total.scope in (GLOBAL, LOCAL):
            clusters[_fold(name)].append(name)

    suspects = []
    for names in clusters.values():
        globals_here = sorted(name for name in names if totals[name].scope == GLOBAL)
        if len(globals_here) < 2:
            continue

        detail = []
        # One entry per line of detail, so the renderer can pair them off: the Target the
        # line points at, or None where the line is prose or a count.
        places: list[Target | None] = []
        for name in sorted(names, key=lambda item: (totals[item].scope != GLOBAL, item)):
            total = totals[name]
            detail.append(f"{name:<24}{total.scope:<9}set {total.sets}, read {total.reads}")
            places.append(Target(VARIABLE, name, name))
            # Where it happens, for the global members only.  A local in one of these
            # clusters is background -- it is the copy the idiom makes, and its locations
            # are per Task and many.
            if total.scope == GLOBAL:
                detail.append(f"    set at   {total.first_set}" if total.first_set else "    never set")
                places.append(total.first_set_target if total.first_set else None)
                detail.append(f"    read at  {total.first_read}" if total.first_read else "    never read")
                places.append(total.first_read_target if total.first_read else None)

        # A cluster nobody uses is a different problem from a live one, and the class's
        # own explanation -- what one spelling writes another does not read -- describes a
        # bug that cannot happen to two variables neither written nor read.  Said here,
        # per cluster, because it is the one thing that does vary between them.
        live = any(totals[name].sets or totals[name].reads for name in globals_here)
        summary = f"{len(globals_here)} global names" + ("" if live else ", none of them set or read anywhere")
        if not live:
            detail += ["", "Leftovers rather than a live mismatch: neither is used here at all."]
            places += [None, None]
        counted = ", ".join(f"{name} (set {totals[name].sets}, read {totals[name].reads})" for name in globals_here)
        sentence = (
            f"{counted} differ only in case or underscores.  Tasker treats them as different variables."
            if live
            else f"{counted} differ only in case or underscores, and neither is set or read anywhere here."
        )
        suspects.append(
            Suspect(
                NEAR_DUPLICATE,
                " / ".join(sorted(names)),
                summary,
                detail,
                sentence,
                [Target(VARIABLE, name, name) for name in sorted(names)],
                places,
            ),
        )

    return sorted(suspects, key=lambda item: item.subject.lower())


def _never_set(totals: dict[str, _Totals]) -> list[Suspect]:
    """Globals something reads that nothing in the file ever sets.

    Globals only.  A local read before it is set is usually a Perform Task parameter or a
    plugin's own output landing in a lower case name, and there are 1387 of them in a real
    backup to hand -- a list that size is not a finding, it is a haystack.

    A declared name is excluded too: it exists in Tasker's Variables tab holding a value
    somebody typed, which is a perfectly good way for a variable to get one.
    """
    suspects = []
    for name, total in sorted(totals.items()):
        if total.scope != GLOBAL or total.declared or total.sets or not total.reads:
            continue
        if _is_low_confidence(name):
            continue
        suspects.append(
            Suspect(
                NEVER_SET,
                name,
                _times(total.reads, len(total.read_tasks), READ),
                [total.first_read],
                f"{_sentence_case(_times(total.reads, len(total.read_tasks), READ))}, first at {total.first_read}.  "
                "Nothing here sets it, so a read sees an empty value.",
                [Target(VARIABLE, name, name)],
                [total.first_read_target],
            ),
        )
    return suspects


def _never_read(totals: dict[str, _Totals]) -> list[Suspect]:
    """Globals something sets that nothing in the file ever reads.

    Undeclared names only, and that filter is what makes the class worth printing: 325
    globals in a real backup to hand are set and never read, but 283 of them are declared,
    sitting in Tasker's Variables tab because the user put them there and looks at them on
    the device.  Saying those are unused would be wrong.  The 42 that remain exist only
    because an action creates them, and nothing consumes them.
    """
    suspects = []
    for name, total in sorted(totals.items()):
        if total.scope != GLOBAL or total.declared or total.reads or not total.sets:
            continue
        if _is_low_confidence(name):
            continue
        suspects.append(
            Suspect(
                NEVER_READ,
                name,
                _times(total.sets, len(total.set_tasks), SET),
                [total.first_set],
                f"{_sentence_case(_times(total.sets, len(total.set_tasks), SET))}, first at {total.first_set}.  "
                "Nothing here reads it, and it is not declared in Tasker's Variables tab.",
                [Target(VARIABLE, name, name)],
                [total.first_set_target],
            ),
        )
    return suspects


def suspects(index: VariableIndex) -> list[Suspect]:
    """Every problem class, worst first.

    Split out from the report so healthck can fold these into its own findings without
    building the index twice -- see the module header.
    """
    totals = _totals_by_name(index)
    found = _near_duplicates(totals) + _never_set(totals) + _never_read(totals)
    return sorted(found, key=lambda item: (_SUSPECT_ORDER.index(item.tag), item.subject.lower()))


# ##################################################################################
# Report construction.
# ##################################################################################
def _current_xml_file() -> str:
    """The path of the XML file being indexed.

    PrimeItems.file_to_get is sometimes an open file object and sometimes the path as a
    plain string -- resolved the same way healthck._current_xml_file resolves it.
    """
    file_to_get = PrimeItems.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) and path else "(unknown)"


def _reference_lines(references: list[Reference], role: str) -> list[Row]:
    """The 'set' or 'read' block of one variable's entry, one place per pair of lines.

    Sorted and de-duplicated: an action that names a variable in three of its arguments is
    one place the user has to go and look, not three.
    """
    seen = {}
    for reference in references:
        seen.setdefault((reference.where, reference.detail), reference.target)

    rows = []
    for position, (where, detail) in enumerate(sorted(seen)):
        label = f"    {role:<7}" if position == 0 else " " * 11
        # The place is the clickable half; the argument that named the variable is not a
        # place of its own and stays plain.
        rows.append(Row.of_pieces([(label, None), (where, seen[(where, detail)])]))
        rows.append(Row(f"{' ' * 13}{detail}"))
    return rows


def _variable_block(variable: Variable) -> list[Row]:
    """One variable's whole entry."""
    counts = f"set {len(variable.sets)}, read {len(variable.reads)}"
    place = Target(VARIABLE, variable.name, variable.name)
    # Padded to a column so the counts line up down the page and the eye can run straight
    # down them looking for a zero.  A name too long for the column takes a line of its own
    # rather than pushing its counts out of line with everything above it.
    if len(variable.name) < _NAME_COLUMN:
        padding = " " * (_NAME_COLUMN - len(variable.name))
        rows = [Row.of_pieces([(variable.name, place), (f"{padding}{counts}", None)])]
    else:
        rows = [Row(variable.name, place), Row(f"{'':<{_NAME_COLUMN}}{counts}")]

    if variable.declared:
        value = variable.value or "(empty)"
        if len(value) > 60:
            value = f"{value[:57]}..."
        rows.append(Row(f"    value  {value}"))
    rows += _reference_lines(variable.sets, SET)
    rows += _reference_lines(variable.reads, READ)
    rows.append(Row(""))
    return rows


def _counts_by_scope(index: VariableIndex) -> dict[str, int]:
    """How many variables of each scope, ignoring the too-short names."""
    counts = dict.fromkeys((GLOBAL, LOCAL, BUILTIN, TASKER_SET), 0)
    for variable in index.variables.values():
        if not _is_low_confidence(variable.name):
            counts[variable.scope] += 1
    return counts


def build_report(index: VariableIndex, when: datetime | None = None, include_index: bool = True) -> list[Row]:
    """Render the index as plain text.

    Rows rather than finished text, for the reason healthck._build_report gives: the
    report is written twice over, as the plain text that is saved and as the HTML the GUI
    shows with its places clickable, and one list of rows is what keeps the two the same.

    include_index=False leaves out the where-used listing and keeps the header, the
    suspects and the limitations.  That is the form the GUI displays: on a real backup the
    full report is 18,000 lines and a megabyte, of which 188 lines are the part anybody
    acts on, and dropping the rest into a <pre> costs the browser a great deal to render
    something nobody scrolls through on screen.  The SAVED file always has everything --
    the index is a reference document, and the point of it is to be searched.
    """
    when = when or datetime.now()  # noqa: DTZ005
    counts = _counts_by_scope(index)
    declared = sum(1 for variable in index.variables.values() if variable.declared)
    rule = "=" * _REPORT_WIDTH
    thin_rule = "-" * _REPORT_WIDTH

    lines = [
        "MapTasker Variable Cross-Reference",
        rule,
        f"XML file:    {_current_xml_file()}",
        f"Generated:   {when.strftime('%d-%b-%Y %H:%M:%S')}",
        f"Version:     {MY_VERSION}",
        "",
        (
            f"Scanned:     {index.tasks_scanned} Tasks, {index.actions_scanned} actions, "
            f"{index.profiles_scanned} Profiles, {index.scenes_scanned} Scenes"
        ),
        f"Variables:   {counts[GLOBAL]} global, {counts[BUILTIN]} built-in, {declared} declared in this file",
        # Counted per owner rather than per name, because that is the scope Tasker gives
        # them: the same %i in two Tasks is two variables, and this number says so.
        f"             {counts[LOCAL]} local, counted once per Task, Profile or Scene using one",
        "",
    ]

    found = suspects(index)
    tallies = {tag: sum(1 for item in found if item.tag == tag) for tag in _SUSPECT_ORDER}
    lines.insert(
        len(lines) - 1,
        f"Suspects:    {tallies[NEAR_DUPLICATE]} near-duplicate name(s), "
        f"{tallies[NEVER_SET]} read but never set, {tallies[NEVER_READ]} set but never read",
    )

    if not index.variables:
        return [Row(line) for line in [*lines, "No variables found.", ""]]

    rows = [Row(line) for line in lines]
    rows += _suspects_section(found, thin_rule)
    if include_index:
        rows += _global_section(index, thin_rule)
        rows += _local_section(index, thin_rule)
    else:
        rows += [
            Row(""),
            Row("WHERE USED"),
            Row(thin_rule),
            Row(f"The full where-used index -- every one of the {len(index.variables)} variables, and"),
            Row("every place each is set and read -- is in the saved report named above."),
            Row(""),
        ]
    return rows + [Row(line) for line in _limitations(index, thin_rule)]


def _suspects_section(found: list[Suspect], thin_rule: str) -> list[Row]:
    """The problems, ahead of the index.

    First in the report because it is the answer to the question that brought the user
    here.  The index behind it is the reference they consult once they know what to look
    for, not the thing they came to read.
    """
    if not found:
        return [
            Row(""),
            Row("SUSPECTS"),
            Row(thin_rule),
            Row("Nothing to report: no near-duplicate names, and every global is both set and"),
            Row("read somewhere in this file."),
            Row(""),
        ]

    rows = [Row(""), Row("SUSPECTS -- most likely to be a bug"), Row(thin_rule)]
    for tag in _SUSPECT_ORDER:
        of_this_tag = [suspect for suspect in found if suspect.tag == tag]
        if not of_this_tag:
            continue
        heading, explanation = _SUSPECT_HEADINGS[tag]
        rows += [Row(""), Row(f"{heading} -- {len(of_this_tag)}"), *[Row(line) for line in explanation], Row("")]
        # A near-duplicate's evidence IS the finding -- which spelling is written, which
        # is read -- so it keeps the block form.  The other two classes say the same thing
        # about every member, so one line each is the whole finding.
        if tag == NEAR_DUPLICATE:
            for suspect in of_this_tag:
                rows.append(_subject_row("  ", suspect))
                rows += _detail_rows(suspect)
                rows.append(Row(""))
        else:
            for suspect in of_this_tag:
                rows.append(_subject_row("  ", suspect, suspect.summary))
                rows += [
                    Row.of_pieces([("      first at ", None), (line, place)])
                    for line, place in zip(suspect.detail, _padded_places(suspect), strict=False)
                    if line
                ]
            rows.append(Row(""))
    return rows


def _padded_places(suspect: Suspect) -> list[Target | None]:
    """suspect.places, made exactly as long as suspect.detail.

    The two are built together and should already match; padding rather than trusting that
    means a class that later adds a line of prose without a place beside it loses a link,
    not the line itself.
    """
    places = list(suspect.places)
    return places + [None] * (len(suspect.detail) - len(places))


def _subject_row(indent: str, suspect: Suspect, summary: str = "") -> Row:
    """The line naming what a suspect is about, with each variable in it clickable.

    A near-duplicate names two ("%SheetID / %SheetId"), and both are worth going to -- the
    whole finding is that they are different variables -- so the subject is rebuilt from
    its parts rather than linked as one lump.  Reassembled with the same " / " the subject
    was joined with, so the text is unchanged.
    """
    names = [name.strip() for name in suspect.subject.split("/")] if len(suspect.variables) > 1 else [suspect.subject]
    pieces: list[tuple[str, Target | None]] = [(indent, None)]
    for position, name in enumerate(names):
        if position:
            pieces.append((" / ", None))
        place = suspect.variables[position] if position < len(suspect.variables) else None
        pieces.append((name, place))
    if summary:
        # Padded to the column the plain-text report uses, measured over the subject as a
        # whole rather than the piece just added.
        pieces.append((" " * max(1, 38 - len(suspect.subject)) + summary, None))
    return Row.of_pieces(pieces)


def _detail_rows(suspect: Suspect) -> list[Row]:
    """A near-duplicate's evidence block, each "set at"/"read at" line clickable."""
    return [
        Row.of_pieces([("    ", None), (line, place)]) if line else Row("")
        for line, place in zip(suspect.detail, _padded_places(suspect), strict=False)
    ]


def _global_section(index: VariableIndex, thin_rule: str) -> list[Row]:
    """Every global, built-in and Tasker-set name, A-Z."""
    wanted = sorted(
        (variable for variable in index.variables.values() if variable.scope != LOCAL),
        key=lambda variable: variable.name.lower(),
    )
    if not wanted:
        return []

    rows = [Row(""), Row("WHERE USED -- global variables"), Row(thin_rule)]
    for variable in wanted:
        # Said once, on the entry itself, rather than left for the reader to work out from
        # the name: a built-in with no 'set' block is Tasker doing its job, not a fault.
        block = _variable_block(variable)
        if variable.scope in (BUILTIN, TASKER_SET):
            block.insert(1, Row(f"    ({variable.scope} -- Tasker sets this one)"))
        rows += block
    return rows


def _local_section(index: VariableIndex, thin_rule: str) -> list[Row]:
    """Every local, grouped under the Task it belongs to.

    Grouped rather than listed A-Z because a local only means anything inside the thing
    that owns it: twenty Tasks each with their own %i is twenty variables, and a flat list
    of them twenty times over says nothing.  Scenes and Profiles group here too -- their
    lower case names are no more Task locals than they are each other's.
    """
    by_scope = defaultdict(list)
    for variable in index.variables.values():
        if variable.scope == LOCAL:
            by_scope[variable.owner].append(variable)
    if not by_scope:
        return []

    rows = [Row(""), Row("WHERE USED -- local variables, by Task, Profile and Scene"), Row(thin_rule)]
    for scope_id in sorted(by_scope, key=lambda item: _scope_label(index, item)):
        # The group heading is the Task, Profile or Scene these locals belong to, so it is
        # a place in its own right -- and the one worth going to, since a local means
        # nothing outside the thing that owns it.
        rows.append(Row(_scope_label(index, scope_id) or f"(id {scope_id})", index.scope_locations.get(scope_id)))
        for variable in sorted(by_scope[scope_id], key=lambda item: item.name.lower()):
            counts = f"set {len(variable.sets)}, read {len(variable.reads)}"
            rows.append(Row(f"  {variable.name:<{_NAME_COLUMN - 2}}{counts}"))
        rows.append(Row(""))
    return rows


def _scope_label(index: VariableIndex, scope_id: str) -> str:
    """The phrase naming what owns a scope -- "" when nothing recorded one."""
    place = index.scope_locations.get(scope_id)
    return place.label if place else ""


def _limitations(index: VariableIndex, thin_rule: str) -> list[str]:
    """What this index cannot see, said plainly.

    Printed rather than left implied for the same reason healthck prints its own: the
    entries most worth acting on are the ones with a zero in them, and a zero here can
    mean "nothing uses this" or it can mean "this scan does not yet look there".  A report
    that does not say which would invite someone to delete a variable their configuration
    depends on.
    """
    lines = ["", "LIMITATIONS", thin_rule]

    # First, because it changes what every other number in the report means: a variable
    # showing "set 0, read 3" in a scoped run is set nowhere IN THAT OBJECT, which is not
    # the same claim at all, and the suspects section leans on exactly those zeroes.
    if not index.scope.is_everything:
        lines += [
            f"Limited to {index.scope.phrase}, which is what the app is displaying.  Nothing",
            "outside it was read, so every count here is a count within that one object --",
            "a variable set elsewhere and only read here will show 'set 0'.",
            "",
        ]

    if index.indirect_references:
        lines += [
            f"{index.indirect_references} action(s) name their target variable through another variable",
            "(%(%which), or a name built at run time).  Any of them could be setting any",
            "variable in this file, so treat a count of 'set 0' as somewhere to start",
            "looking rather than as proof that nothing sets it.",
            "",
        ]

    lines += [
        "Read for this index: every Task action (its arguments, its conditions and its",
        "plugin configuration), the output variables each action declares, every Profile",
        "context, and every Scene -- Legacy elements, Version 2 layouts, and the",
        "anonymous Tasks that live inside a Scene.",
        "",
        "A Scene input element's value is treated as both read and written, since Tasker",
        "writes back what the user types or slides.  That mapping is known for EditText,",
        "Slider, CheckBox and Switch; for other input types the value is counted only as",
        "a read, so a variable a Scene alone sets through one of those can still appear",
        "under READ BUT NEVER SET.",
        "",
        "SUSPECTS reports global variables only.  A local read before it is set is",
        "usually a Perform Task parameter or a plugin output, and there are too many to",
        "be a finding; a global already declared in Tasker's Variables tab is left out",
        "because a value typed there is a perfectly good way for one to get set.",
        "",
        "Nothing outside the backup is visible at all: an intent from another app, a",
        "Tasker Function, or a variable set by hand on the device leaves no trace here.",
        "Nor does anything inside a script: a WebView Scene whose HTML sets variables from",
        "JavaScript, or an AutoTools/Java action doing the same, is opaque to this index.",
        "A family of related names that are all read and never set usually means one of",
        "those, rather than a family of mistakes.",
        "",
    ]
    return lines


def run_variable_xref() -> tuple[list[Row], VariableIndex]:
    """Build the index and render it.  Returns (report rows, index)."""
    index = build_index()
    return build_report(index), index


def write_variable_xref_report(rows: list[Row]) -> str:
    """Write the report to a timestamped file in the current runtime directory.

    Returns the file name written, or "" if the write failed -- the caller reports the
    file name to the user, and an index that displayed fine is still worth showing when
    only the save went wrong.  Named and timestamped exactly as the Health Check report
    is, so successive runs from one day sort by when they were run.
    """
    stamp = datetime.now().strftime("_%m-%d-%Y_%H-%M-%S")  # noqa: DTZ005
    file_name = append_to_filename(VARXREF_FILE, stamp)
    if not file_name:
        return ""
    try:
        with open(os.path.join(os.getcwd(), file_name), "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Variable Cross-Reference report could not be written: {error}")
        return ""
    return file_name
