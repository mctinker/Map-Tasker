"""namerules: the house style for names and Task shape, and every place the loaded configuration breaks it."""

#! /usr/bin/env python3

#                                                                                        #
# namerules: naming and structure rules.                                                 #
#                                                                                        #
# The Health Check finds an object with no name.  It cannot find one named the wrong     #
# way, because "wrong" is a matter of style and the style is the user's: Tasks that      #
# start with 'Z ' so they sort together, globals that start with 'App', no Task still    #
# called 'Task 12', no Task so long that nobody reads it.  So the user says what the    #
# style is, once, and this reads the loaded configuration against it.                   #
#                                                                                        #
# THE RULES, each off until it is set, so a file is never reported against a style the   #
# user has not chosen:                                                                   #
#                                                                                        #
#   Prefix        a Profile, Task or Scene name must start with its prefix; a global or     #
#                 a local variable's name must start with its own (after the '%').         #
#   No default    no Profile, Task or Scene still carries the name Tasker gave it:          #
#                 'Task 12', 'New Task 12', 'Profile 3', 'Scene 2'.                          #
#   Labels        in a Task of more than N actions, every action carries a label.          #
#                 Where the flow only closes a block (End If, Else, End For) a label says    #
#                 nothing, so those are not asked to have one.                              #
#   Length        no Task has more than N actions.                                          #
#                                                                                        #
# WHAT A PREFIX RULE CANNOT BE TRUSTED TO DO TO A VARIABLE: Tasker decides whether a      #
# variable is global or local by its spelling -- a capital letter anywhere makes it        #
# global.  A prefix that would change which of the two a name is would silently change     #
# what the variable IS, so a global prefix must hold a capital and a local one must not,   #
# and a rule that does not is reported as a problem with the rule, not applied.            #
#                                                                                        #
# Where a name can be fixed by adding the prefix the breach carries the name it would      #
# become.  A default name has no suggestion: what the Task is for is not in the file.      #
# What a rename does to the rest of the configuration is namefix's, not this module's;     #
# this one only reads.                                                                     #
#                                                                                        #
# The rules live beside the settings, in the current directory, and never in the backup,   #
# like the notes and the Task tests.                                                       #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import asdict, dataclass, field, fields
from typing import TYPE_CHECKING, Any, cast

from maptasker.src.core import clock
from maptasker.src.core.mapjump import PROFILE, SCENE, TASK, Row, Target, actions_in_map_order, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import NAMING_RULES_FILE, NAMING_RULES_REPORT_FILE, logger
from maptasker.src.mapgen import varxref

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# Which rule a breach is of.  Stable, un-translated tags, for the reason healthck's are.
PREFIX = "PREFIX"
DEFAULT_NAME = "DEFAULT-NAME"
UNLABELED = "UNLABELED"
TOO_LONG = "TOO-LONG"
BAD_RULE = "BAD-RULE"

# The kinds of thing a name rule applies to.
GLOBAL_VARIABLE = "global variable"
LOCAL_VARIABLE = "local variable"

# Control flow that only closes a block: a label on it says nothing the block's opener does not.
_CLOSERS = frozenset({"38", "43", "40"})
_DEFAULT_NAME = {
    PROFILE: re.compile(r"^(?:new\s+)?profile\s*\d*$", re.IGNORECASE),
    TASK: re.compile(r"^(?:new\s+)?task\s*\d*$", re.IGNORECASE),
    SCENE: re.compile(r"^(?:new\s+)?scene\s*\d*$", re.IGNORECASE),
}
_KIND_WORD = {PROFILE: "Profile", TASK: "Task", SCENE: "Scene"}
_FIRST_ACTIONS_SHOWN = 3
_REPORT_WIDTH = 78
_WRAP = 74


# ##################################################################################
# The rules, and keeping them.
# ##################################################################################
@dataclass
class Rules:
    """The user's house style.  An empty prefix, a zero or a False means that rule is off."""

    profile_prefix: str = ""
    task_prefix: str = ""
    scene_prefix: str = ""
    global_variable_prefix: str = ""
    local_variable_prefix: str = ""
    no_default_names: bool = False
    label_after: int = 0  # Tasks of MORE actions than this must label every action
    max_task_length: int = 0  # no Task may have MORE actions than this

    @property
    def is_empty(self) -> bool:
        """Whether every rule is off."""
        return self == Rules()

    def problems(self) -> list[str]:
        """What is wrong with the rules themselves, in a sentence each -- see this module's note on variable prefixes."""
        found: list[str] = []
        if self.global_variable_prefix and not re.search(r"[A-Z]", self.global_variable_prefix):
            found.append(
                f"The global variable prefix '{self.global_variable_prefix}' has no capital letter, so a global "
                "given it would become a local variable.  Start it with a capital.",
            )
        if self.local_variable_prefix and re.search(r"[A-Z]", self.local_variable_prefix):
            found.append(
                f"The local variable prefix '{self.local_variable_prefix}' has a capital letter, so a local "
                "given it would become a global variable.  Keep it lower case.",
            )
        for name in ("global_variable_prefix", "local_variable_prefix"):
            if re.search(r"[^A-Za-z0-9_]", getattr(self, name)):
                found.append("A variable prefix may hold only letters, digits and underscores.")
                break
        for name in ("label_after", "max_task_length"):
            if getattr(self, name) < 0:
                found.append("A number of actions cannot be below zero.")
                break
        return found

    def usable(self) -> Rules:
        """These rules with each variable prefix that would change a variable's scope, or is not a name, switched off."""
        kept = Rules(**asdict(self))
        if not re.fullmatch(r"[A-Za-z0-9_]*[A-Z][A-Za-z0-9_]*", self.global_variable_prefix):
            kept.global_variable_prefix = ""
        if not re.fullmatch(r"[a-z0-9_]*", self.local_variable_prefix):
            kept.local_variable_prefix = ""
        return kept

    def prefix_for(self, kind: str) -> str:
        """The prefix this kind of object must start with, or "" when it has none."""
        return {
            PROFILE: self.profile_prefix,
            TASK: self.task_prefix,
            SCENE: self.scene_prefix,
            GLOBAL_VARIABLE: self.global_variable_prefix,
            LOCAL_VARIABLE: self.local_variable_prefix,
        }.get(kind, "")


def rules_path() -> str:
    """Where the rules are kept -- in the current directory, beside the settings."""
    return os.path.join(os.getcwd(), NAMING_RULES_FILE)


def _number(value: object) -> int:
    """A rule's count from whatever the file held: a whole number of zero or more, else 0 (off)."""
    try:
        return max(0, int(cast("Any", value)))
    except (TypeError, ValueError):
        return 0


def load(file_path: str | None = None) -> Rules:
    """The saved rules.  Every rule off when there is no file or it cannot be read.

    A field that is not what it should be is left off and the rest are kept, so a hand-edited mistake costs only itself.
    """
    where = file_path or rules_path()
    try:
        with open(where, encoding="utf-8") as handle:
            data: object = json.load(handle)
    except FileNotFoundError:
        return Rules()
    except (OSError, ValueError) as error:
        logger.error(f"The naming rules could not be read from {where}: {error}")
        return Rules()
    raw = cast("dict[str, Any]", data) if isinstance(data, dict) else {}
    rules = Rules()
    for item in fields(Rules):
        if item.name not in raw:
            continue
        value = raw[item.name]
        if isinstance(getattr(rules, item.name), bool):
            setattr(rules, item.name, bool(value))
        elif isinstance(getattr(rules, item.name), int):
            setattr(rules, item.name, _number(value))
        else:
            setattr(rules, item.name, str(value or ""))
    return rules


def save(rules: Rules, file_path: str | None = None) -> bool:
    """Keep the rules.  Whether that worked."""
    where = file_path or rules_path()
    try:
        with open(where, "w", encoding="utf-8") as handle:
            json.dump(asdict(rules), handle, indent=2, ensure_ascii=False)
    except OSError as error:
        logger.error(f"The naming rules could not be saved to {where}: {error}")
        return False
    return True


# ##################################################################################
# The breaches.
# ##################################################################################
@dataclass
class Breach:
    """One place the configuration breaks a rule."""

    rule: str  # PREFIX, DEFAULT-NAME, UNLABELED, TOO-LONG or BAD-RULE
    kind: str  # PROFILE, TASK, SCENE, GLOBAL_VARIABLE, LOCAL_VARIABLE -- or "" for a problem with a rule
    name: str  # what it is called now
    where: Target | None
    message: str
    suggestion: str = ""  # the name it would become, when there is one
    owner: str = ""  # a local variable's Task id -- varxref's own key
    detail: list[str] = field(default_factory=list[str])

    @property
    def can_rename(self) -> bool:
        """Whether there is a new name to offer."""
        return bool(self.suggestion) and self.suggestion != self.name


def _owners(kind: str, state: RunState) -> dict[str, str]:
    """{member id: owning Project name} for one of a Project's lists (see plugchk._owners)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def _own_name(item: dict[str, Any]) -> str:
    """The name an object has in the file itself, or "" when it has none.

    The tables hold a made-up name for an unnamed Profile or Task ('*Maps.102 Unnamed') so that it can be listed and
    found; that is not a name it has, and reporting it against a prefix would invite renaming something to a
    made-up name.
    """
    return str(item["xml"].findtext("nme") or "").strip()


def _name_breaches(rules: Rules, state: RunState) -> list[Breach]:
    """The prefix and default-name breaches of Profiles, Tasks and Scenes."""
    root = state.tasker_root_elements
    breaches: list[Breach] = []
    profile_owner, task_owner, scene_owner = _owners("pids", state), _owners("tids", state), _owners("scenes", state)
    sources = (
        (PROFILE, {key: (_own_name(item), profile_owner.get(key, "")) for key, item in root["all_profiles"].items()}),
        (TASK, {key: (_own_name(item), task_owner.get(key, "")) for key, item in root["all_tasks"].items()}),
        (SCENE, {name: (name, scene_owner.get(name, "")) for name in root["all_scenes"]}),
    )
    for kind, objects in sources:
        prefix = rules.prefix_for(kind)
        word = _KIND_WORD[kind]
        for key, (name, project) in objects.items():
            if not name:
                continue  # No name at all is the Health Check's finding.
            where = Target(kind, key, name, project)
            if rules.no_default_names and _DEFAULT_NAME[kind].match(name.strip()):
                breaches.append(
                    Breach(DEFAULT_NAME, kind, name, where, f"{word} '{name}' still has the name Tasker gave it."),
                )
            elif prefix and not name.startswith(prefix):
                breaches.append(
                    Breach(
                        PREFIX,
                        kind,
                        name,
                        where,
                        f"{word} '{name}' does not start with '{prefix}'.",
                        suggestion=f"{prefix}{name}",
                    ),
                )
    return breaches


def _variable_breaches(rules: Rules, state: RunState) -> list[Breach]:
    """The prefix breaches of global and local variables, one per variable (a local per Task that has it)."""
    if not (rules.global_variable_prefix or rules.local_variable_prefix):
        return []
    index = varxref.build_index(state=state)
    breaches: list[Breach] = []
    for (name, owner), variable in index.variables.items():
        if variable.scope == varxref.GLOBAL:
            kind = GLOBAL_VARIABLE
        elif variable.scope == varxref.LOCAL:
            kind = LOCAL_VARIABLE
        else:
            continue  # Tasker's own names are not the user's to rename.
        prefix = rules.prefix_for(kind)
        bare = name.lstrip("%")
        if not prefix or bare.startswith(prefix) or len(bare) <= varxref.LOW_CONFIDENCE_LENGTH:
            continue
        places = variable.sets + variable.reads
        where = next((place.target for place in places if place.target is not None), None)
        breaches.append(
            Breach(
                PREFIX,
                kind,
                f"%{bare}",
                where,
                f"The {kind} %{bare} does not start with '{prefix}'.",
                suggestion=f"%{prefix}{bare}",
                owner=owner,
            ),
        )
    return breaches


def _structure_breaches(rules: Rules, state: RunState) -> list[Breach]:
    """The Tasks too long, and the Tasks long enough that every action should be labelled and are not."""
    if not (rules.max_task_length or rules.label_after):
        return []
    owners = _owners("tids", state)
    breaches: list[Breach] = []
    for task_id, task in state.tasker_root_elements["all_tasks"].items():
        actions = actions_in_map_order(task["xml"])
        count = len(actions)
        where = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        if rules.max_task_length and count > rules.max_task_length:
            breaches.append(
                Breach(
                    TOO_LONG,
                    TASK,
                    task["name"],
                    where,
                    f"Task '{task['name']}' has {count} actions, more than the {rules.max_task_length} allowed.",
                ),
            )
        if rules.label_after and count > rules.label_after:
            bare = [
                number
                for number, action in enumerate(actions, start=1)
                if (action.findtext("code") or "").strip() not in _CLOSERS
                and not (action.findtext("label") or "").strip()
            ]
            if bare:
                first = ", ".join(str(number) for number in bare[:_FIRST_ACTIONS_SHOWN])
                more = "" if len(bare) <= _FIRST_ACTIONS_SHOWN else " ..."
                breaches.append(
                    Breach(
                        UNLABELED,
                        TASK,
                        task["name"],
                        where.at_action(bare[0]),
                        f"Task '{task['name']}' has {count} actions, more than {rules.label_after}, and "
                        f"{len(bare)} of them have no label (action {first}{more}).",
                    ),
                )
    return breaches


def check(rules: Rules, state: RunState) -> list[Breach]:
    """Every breach of the rules in the loaded configuration.

    Problems with the rules come first and stop the rules they spoil: a variable prefix that would change a
    variable's scope is reported and not applied.  Safe with nothing loaded, and with every rule off: an empty list.
    """
    if not state.backup_loaded or rules.is_empty:
        return []
    breaches = [Breach(BAD_RULE, "", "", None, problem) for problem in rules.problems()]
    usable = rules.usable()
    breaches += _name_breaches(usable, state)
    breaches += _variable_breaches(usable, state)
    breaches += _structure_breaches(usable, state)
    return breaches


# ##################################################################################
# The report.
# ##################################################################################
_TITLES: dict[str, str] = {
    PREFIX: "NAMES THAT DO NOT START WITH THEIR PREFIX",
    DEFAULT_NAME: "NAMES TASKER GAVE AND NOBODY CHANGED",
    UNLABELED: "TASKS WITH ACTIONS THAT HAVE NO LABEL",
    TOO_LONG: "TASKS THAT ARE TOO LONG",
}


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}{'es' if word.endswith('ch') else 's'}"


def _rules_rows(rules: Rules) -> list[Row]:
    """The rules as the report states them, so a report says what it was measured against."""
    rows = [Row("THE RULES"), Row("-" * _REPORT_WIDTH)]
    for kind, label in (
        (PROFILE, "Profile names start with"),
        (TASK, "Task names start with"),
        (SCENE, "Scene names start with"),
        (GLOBAL_VARIABLE, "Global variables start with"),
        (LOCAL_VARIABLE, "Local variables start with"),
    ):
        prefix = rules.prefix_for(kind)
        rows.append(Row(f"  {label + ':':<32}{f'{prefix}' if prefix else '(no rule)'}"))
    rows.append(Row(f"  {'No default names:':<32}{'on' if rules.no_default_names else '(no rule)'}"))
    rows.append(
        Row(
            f"  {'Label every action in Tasks over:':<32}{f'{rules.label_after} actions' if rules.label_after else '(no rule)'}"
        ),
    )
    rows.append(
        Row(
            f"  {'No Task longer than:':<32}{f'{rules.max_task_length} actions' if rules.max_task_length else '(no rule)'}"
        ),
    )
    return [*rows, Row("")]


def report_rows(rules: Rules, breaches: list[Breach], *, loaded: bool = True) -> list[Row]:
    """The breaches as a report: the rules, a count of each, then every breach with where it is."""
    rows = [Row("NAMING AND STRUCTURE RULES"), Row("=" * _REPORT_WIDTH), Row("")]
    if not loaded:
        return [*rows, Row("No XML file has been loaded.  Get an XML file first.")]
    rows += _rules_rows(rules)
    if rules.is_empty:
        return [*rows, Row("No rule has been set, so there is nothing to check.  Set a rule and check again.")]
    problems = [breach for breach in breaches if breach.rule == BAD_RULE]
    if problems:
        rows += [Row("PROBLEMS WITH THE RULES"), Row("-" * _REPORT_WIDTH)]
        for problem in problems:
            rows += [Row(f"  {line}") for line in textwrap.wrap(problem.message, _WRAP)]
        rows.append(Row(""))
    real = [breach for breach in breaches if breach.rule != BAD_RULE]
    if not real:
        return [*rows, Row("Nothing breaks the rules."), Row("")]
    rows.append(Row(f"Found:  {_plural(len(real), 'breach')}"))
    rows.append(Row(""))
    for rule, title in _TITLES.items():
        mine = [breach for breach in real if breach.rule == rule]
        if not mine:
            continue
        rows += [Row(f"{title} -- {len(mine)}"), Row("-" * _REPORT_WIDTH)]
        for breach in mine:
            rows += [Row(f"  {line}", breach.where) for line in textwrap.wrap(breach.message, _WRAP)[:1]]
            rows += [Row(f"  {line}") for line in textwrap.wrap(breach.message, _WRAP)[1:]]
            if breach.can_rename:
                rows.append(Row(f"      could be renamed {breach.suggestion}"))
        rows.append(Row(""))
    return rows


def write_report(rows: list[Row], state: RunState) -> str:
    """Save the report as text, the way the other reports are saved.  Returns the file's path, or "" if it could not be."""
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(NAMING_RULES_REPORT_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"The naming rules report could not be written: {error}")
        return ""
    return file_path
