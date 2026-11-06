"""mapvars: the Variable Manager -- every global with its value, where it is used, and what can be done to it."""

#! /usr/bin/env python3

#                                                                                        #
# mapvars: one table of the configuration's global variables, and the changes that can    #
#          be made to one of them.                                                        #
#                                                                                        #
# varxref already knows where every variable is set and read, and maprefac_variable can   #
# rename one everywhere with a preview and one Undo.  What was missing is the place that   #
# puts them side by side: the variables as a TABLE -- name, value, type, how often it is   #
# set and read, what the phone holds -- with the ones worth a look marked, and the three   #
# things a person does with such a table: change a value, rename, delete.                  #
#                                                                                        #
# WHAT A GLOBAL IS HERE.  Tasker keeps its global variables in the Variables tab, which a   #
# backup holds as <Variable><n>%Name</n><v>value</v></Variable> and nothing else about      #
# them -- no type, no description.  A name that actions set or read but the tab does not    #
# hold is still a global (a capital in the name makes it one), and is listed with no value.  #
#                                                                                        #
# TYPE.  A backup records none, so there is nothing to read and nothing to write back.  The  #
# type shown is INFERRED from the value (a number, true/false, JSON, or text) and the type   #
# a person picks when changing a value is a CHECK, applied before the value is written, so   #
# "Number" will not accept "twelve".  Tasker itself treats every value as text.             #
#                                                                                        #
# THE FLAGS, from varxref's own counts so this and the Variable Xref report cannot disagree:  #
#                                                                                        #
#   SET-NEVER-READ   something sets it and nothing in the file reads it.  A declared one is    #
#                    flagged too, with the difference said: it is in the Variables tab, where  #
#                    a person may look at it on the device, so it is a question not a finding.  #
#   READ-NEVER-SET   something reads it, nothing sets it and the tab does not hold it, so a    #
#                    read sees an empty value.                                              #
#   UNUSED           in the Variables tab and used nowhere -- the safe one to delete.        #
#                                                                                        #
# EVERY CHANGE IS A Plan, the shape maprefac already uses: a preview that can say what it      #
# will do and what it will leave alone, blocks that refuse it, warnings that qualify it, and    #
# apply() making the whole thing one Undo and refusing a plan whose elements have gone.       #
#                                                                                        #
# Same contract as varxref and proflint: reads PrimeItems.tasker_root_elements and             #
# state.xml_root and nothing else -- no GUI, no device.  The phone enters only as the           #
# LiveValues a caller already read (livevars), and is never written to from here.             #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from maptasker.src.mapgen import varxref
from maptasker.src.mapops import maprefac_variable
from maptasker.src.mapops.maprefac_model import VARIABLE, Block, Plan, Step, blocked

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.livevars import LiveValues

# What a table row can be marked with, in the order a person should look at them.
NEVER_READ = "SET-NEVER-READ"
NEVER_SET = "READ-NEVER-SET"
UNUSED = "UNUSED"

# What a value is, as far as anything can tell.  EMPTY is only ever inferred, never chosen.
TEXT = "Text"
NUMBER = "Number"
TRUE_FALSE = "True/False"
JSON = "JSON"
EMPTY = "Empty"
CHOOSABLE_TYPES = (TEXT, NUMBER, TRUE_FALSE, JSON)

_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_BOOLEANS = {"true": "true", "false": "false"}

# How many of a variable's uses are named in a preview before "and N more".
_USES_NAMED = 5


@dataclass
class Row:
    """One global variable, as the table shows it."""

    name: str  # "%Mode"
    value: str  # what the file's Variables tab holds, "" when it holds nothing or has no entry
    declared: bool  # whether the Variables tab has an entry for it
    value_type: str
    sets: int
    reads: int
    tasks: int  # distinct Tasks (and other places) that set or read it
    flag: str  # NEVER_READ, NEVER_SET, UNUSED or ""
    # What the phone holds, when it was asked: None when it was not asked, and `on_device` says whether the phone
    # has it at all -- present and empty is a different answer from absent.
    live: str | None = None
    on_device: bool = False
    variable: varxref.Variable | None = field(default=None, repr=False)

    @property
    def differs(self) -> bool:
        """Whether the phone holds a different value from the file's, for a variable the phone has."""
        return self.live is not None and self.on_device and " ".join(self.live.split()) != " ".join(self.value.split())

    def uses(self) -> list[Target]:
        """Every place that sets or reads it, each once, the places that set it first."""
        seen: dict[str, Target] = {}
        for reference in [
            *(self.variable.sets if self.variable else []),
            *(self.variable.reads if self.variable else []),
        ]:
            if reference.target is not None:
                seen.setdefault(reference.where, reference.target)
        return list(seen.values())


# ##################################################################################
# Types: what a value looks like, and whether it is what was asked for.
# ##################################################################################
def infer_type(value: str) -> str:
    """What this value looks like: empty, true/false, a number, JSON (an object or a list), or text."""
    text = value.strip()
    if not text:
        return EMPTY
    if text.lower() in _BOOLEANS:
        return TRUE_FALSE
    if _NUMBER.fullmatch(text):
        return NUMBER
    if text[0] in "{[" and _is_json(text):
        return JSON
    return TEXT


def _is_json(text: str) -> bool:
    """Whether the text is a JSON object or array."""
    try:
        return isinstance(json.loads(text), (dict, list))
    except ValueError:
        return False


def check_value(value_type: str, value: str) -> str:
    """Why this value is not of that type, or "" when it is.  Text takes anything."""
    text = value.strip()
    if value_type == NUMBER and not _NUMBER.fullmatch(text):
        return f"'{_short(value)}' is not a number."
    if value_type == TRUE_FALSE and text.lower() not in _BOOLEANS:
        return f"'{_short(value)}' is not true or false."
    if value_type == JSON and not (text[:1] in "{[" and _is_json(text)):
        return f"'{_short(value)}' is not a JSON object or list."
    return ""


def tidy_value(value_type: str, value: str) -> str:
    """The value as it is written once it has passed check_value: trimmed for the typed kinds, and true/false in lower case.

    Text is left exactly as typed, spaces and all -- a value is whatever the person means it to be.
    """
    if value_type == TRUE_FALSE:
        return _BOOLEANS[value.strip().lower()]
    if value_type in (NUMBER, JSON):
        return value.strip()
    return value


def _short(text: str, limit: int = 40) -> str:
    """A value as one short line for a message."""
    folded = " ".join(text.split())
    return folded if len(folded) <= limit else f"{folded[: limit - 3]}..."


# ##################################################################################
# The table.
# ##################################################################################
def _flag(variable: varxref.Variable) -> str:
    """Which mark this global earns, from the same counts the Variable Xref report is built on."""
    if variable.sets and not variable.reads:
        return NEVER_READ
    if variable.reads and not variable.sets and not variable.declared:
        return NEVER_SET
    if variable.declared and not variable.sets and not variable.reads:
        return UNUSED
    return ""


def build_rows(
    state: RunState, live: LiveValues | None = None, index: varxref.VariableIndex | None = None
) -> list[Row]:
    """Every global variable in the configuration, by name.

    The ones in the Variables tab and the ones only actions name, and none of Tasker's own (%BATT, %TIME).  The
    index is varxref's, of the WHOLE configuration, so a count here is the count the Xref report prints.
    """
    index = index if index is not None else varxref.build_index(state=state)
    rows: list[Row] = []
    for variable in index.variables.values():
        if variable.scope != varxref.GLOBAL:
            continue
        places = {reference.scope_id for reference in (*variable.sets, *variable.reads)}
        held = live is not None and live.has(variable.name)
        rows.append(
            Row(
                name=variable.name,
                value=variable.value,
                declared=variable.declared,
                value_type=infer_type(variable.value),
                sets=len(variable.sets),
                reads=len(variable.reads),
                tasks=len(places),
                flag=_flag(variable),
                live=live.value(variable.name) if live is not None and held else (None if live is None else ""),
                on_device=held,
                variable=variable,
            ),
        )
    return sorted(rows, key=lambda row: row.name.casefold())


FLAG_ORDER = (NEVER_READ, NEVER_SET, UNUSED)


def flag_counts(rows: list[Row]) -> dict[str, int]:
    """How many rows carry each mark."""
    return {flag: sum(1 for row in rows if row.flag == flag) for flag in FLAG_ORDER}


# ##################################################################################
# Changes: each one a Plan.
# ##################################################################################
def _root(state: RunState) -> Element | None:
    """The loaded file's root, or None when nothing is loaded -- which the type says cannot be, and a fresh start can."""
    return cast("Element | None", state.xml_root)


def _declaration(name: str, state: RunState) -> Element | None:
    """The top-level <Variable> for this name, or None when the Variables tab has none."""
    root = _root(state)
    if root is None:
        return None
    for element in root.findall("Variable"):
        children = list(element)
        if children and (children[0].text or "").strip() == name:
            return element
    return None


def _held_value(declaration: Element) -> str:
    """The value an entry of the Variables tab holds, "" for one that holds none."""
    children = list(declaration)
    return (children[1].text or "") if len(children) > 1 else ""


def _uses_sentence(row_or_variable: varxref.Variable | None) -> str:
    """ "set in 3 places and read in 2", for a message about what a change leaves alone."""
    if row_or_variable is None:
        return "not used anywhere"
    sets, reads = len(row_or_variable.sets), len(row_or_variable.reads)
    parts = [f"set in {sets} place{'s' if sets != 1 else ''}"] if sets else []
    parts += [f"read in {reads} place{'s' if reads != 1 else ''}"] if reads else []
    return " and ".join(parts) if parts else "not used anywhere"


def plan_rename(name: str, new_name: str, state: RunState, index: varxref.VariableIndex | None = None) -> Plan:
    """Rename a global everywhere it is written -- maprefac_variable's own plan, so the two cannot disagree."""
    return maprefac_variable.plan_variable(maprefac_variable.RENAME, name, "", new_name, state, index)


def plan_set_value(
    name: str, value: str, value_type: str, state: RunState, index: varxref.VariableIndex | None = None
) -> Plan:
    """Give the Variables tab's entry for this global a new value, adding the entry if it has none.

    The value is checked against the type first; a value of the wrong type is a block, not a surprise afterwards.
    """
    name = maprefac_variable.percent(name)
    what = f"Set {name} to '{_short(value)}'"
    if problem := check_value(value_type, value):
        return blocked(VARIABLE, what, Block("WRONG-TYPE", f"{problem}  Choose Text, or change the value."))
    if _root(state) is None:
        return blocked(VARIABLE, what, Block("NO-FILE", "No XML file has been loaded."))

    tidy = tidy_value(value_type, value)
    existing = _declaration(name, state)
    index = index if index is not None else varxref.build_index(state=state)
    plan = Plan(kind=VARIABLE, what=what)

    if existing is None:
        plan.steps = [Step(f"Add {name} to the Variables tab, holding '{_short(tidy)}'")]
        plan.elements = (cast("Element", _root(state)),)
        plan.run = _adder(name, tidy, state)
    else:
        plan.steps = [Step(f"Change the value of {name} in the Variables tab to '{_short(tidy)}'")]
        plan.elements = (existing,)
        plan.run = _setter(existing, tidy)
    plan.warnings = ["This changes the backup being edited, not the phone.  Use Push to put a value on the device."]
    return plan


def _setter(declaration: Element, value: str) -> Callable[[], list[str]]:
    """The closure that writes the value into an existing entry's <v>."""

    def run() -> list[str]:
        children = list(declaration)
        if len(children) < 2:
            return [f"The Variables tab entry for {(children[0].text if children else '?')} has no value to change."]
        children[1].text = value
        return []

    return run


def _adder(name: str, value: str, state: RunState) -> Callable[[], list[str]]:
    """The closure that adds a new <Variable> to the end of the file's Variables tab entries."""

    def run() -> list[str]:
        root = _root(state)
        if root is None:
            return ["No XML file has been loaded."]
        existing = root.findall("Variable")
        cls = type(root)
        entry = cls("Variable", {"sr": f"vars{len(existing)}"})
        for tag, text in (("n", name), ("v", value)):
            child = cls(tag)
            child.text = text
            entry.append(child)
        position = list(root).index(existing[-1]) + 1 if existing else len(root)
        root.insert(position, entry)
        return []

    return run


def _names_shown(names: list[str], limit: int = _USES_NAMED) -> str:
    """ "%A, %B and 3 more", for a sentence about several variables."""
    shown = ", ".join(names[:limit])
    return f"{shown} and {len(names) - limit} more" if len(names) > limit else shown


def plan_delete_many(names: list[str], state: RunState, index: varxref.VariableIndex | None = None) -> Plan:
    """Remove these globals' entries from the Variables tab, all of them as one change and one Undo.

    What is removed is the STORED VALUE.  Actions that set or read a variable are left exactly as they are --
    they are Tasks the person wrote -- so the plan says how many variables are still used, as a warning rather than a
    block: a variable set by one Task and read by none is the very thing this is for.

    A name the Variables tab does not hold has no stored value to remove and is left out, said in a warning; only when
    none of them is held is there nothing to do, and that is a block.
    """
    wanted = list(dict.fromkeys(maprefac_variable.percent(name) for name in names))
    what = (
        f"Delete {wanted[0]} from the Variables tab"
        if len(wanted) == 1
        else f"Delete {len(wanted)} variables from the Variables tab"
    )
    held = [(name, declaration) for name in wanted if (declaration := _declaration(name, state)) is not None]
    missing = [name for name in wanted if name not in {name for name, _ in held}]
    if not held:
        which = f"{wanted[0]} is" if len(wanted) == 1 else "None of these variables is"
        return blocked(
            VARIABLE,
            what,
            Block(
                "NOT-DECLARED",
                f"{which} in the Variables tab, so there is no stored value to delete.  They exist only because "
                "actions use them, and deleting those is a change to the Tasks themselves, which this does not make.",
            ),
        )

    index = index if index is not None else varxref.build_index(state=state)
    plan = Plan(kind=VARIABLE, what=what)
    plan.steps = [
        Step(f"Remove {name} (holding '{_short(_held_value(declaration))}') from the Variables tab")
        for name, declaration in held
    ]
    plan.elements = tuple(declaration for _, declaration in held)
    used = [
        name for name, _ in held if (variable := index.variables.get((name, ""))) and (variable.sets or variable.reads)
    ]
    if len(held) == 1 and used:
        plan.warnings.append(
            f"{used[0]} is {_uses_sentence(index.variables.get((used[0], '')))}.  Those actions are left as they are; "
            "the variable simply starts empty the next time Tasker meets it."
        )
    elif used:
        plan.warnings.append(
            f"{len(used)} of these variables ({_names_shown(used)}) are still set or read by actions.  Those actions "
            "are left as they are; each variable simply starts empty the next time Tasker meets it."
        )
    if missing:
        plan.warnings.append(
            f"{len(missing)} of the chosen variables ({_names_shown(missing)}) are not in the Variables tab, so there "
            "is nothing to remove for them; they are left as they are."
        )
    plan.warnings.append("This changes the backup being edited, not the phone.")
    plan.run = _remover([declaration for _, declaration in held], state)
    return plan


def _remover(declarations: list[Element], state: RunState) -> Callable[[], list[str]]:
    """The closure that takes the entries out of the file."""

    def run() -> list[str]:
        root = _root(state)
        if root is None:
            return ["No XML file has been loaded."]
        present = list(root)
        gone = [declaration for declaration in declarations if declaration not in present]
        for declaration in declarations:
            if declaration in present:
                root.remove(declaration)
        return [f"{len(gone)} of the entries were no longer in the configuration."] if gone else []

    return run
