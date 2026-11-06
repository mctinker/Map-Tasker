"""scopecheck: variable names that break Tasker's case rule -- lower case is local, a capital makes it global."""

#! /usr/bin/env python3

#                                                                                        #
# scopecheck: find the variables whose SPELLING says one thing and whose use says another. #
#                                                                                        #
# Tasker decides a variable's scope from its name and nothing else: all lower case is      #
# local to the running Task, and a single capital makes it global to the whole file.  So   #
# changing one letter's case changes WHO CAN SEE THE VALUE, silently, and nothing on the   #
# screen looks different.  That is the commonest way a Tasker configuration comes to be    #
# subtly wrong -- a Task sets %counter and the next one reads %Counter, or a global is     #
# typed in lower case in one Task and so becomes a private copy -- and nothing in a backup #
# reports it, because every spelling is a perfectly legal variable.                        #
#                                                                                        #
# What can be seen is the evidence.  Three kinds, strongest first:                         #
#                                                                                        #
#   SCOPE-CASE-MISMATCH      A Task uses a lower case name that is the same letters as a   #
#                            global the file also uses -- %aab_animsteps beside             #
#                            %AAB_AnimSteps.  Tasker reads them as two variables.  The      #
#                            global exists, so it is almost certainly the one meant.        #
#   SCOPE-DECLARED-LOWERCASE A name in Tasker's Variables tab, which holds globals only,     #
#                            that has no capital.  Every action that writes it as %name     #
#                            is using a LOCAL of that name, never the one in the tab.       #
#   SCOPE-LOCAL-NEVER-SET    A local a Task reads and never sets, in a Task nothing         #
#                            performs, while another Task sets a local of the same name.    #
#                            A local is empty when its Task starts, so this reads nothing   #
#                            -- the pattern of a variable meant to be shared, spelled      #
#                            as one that cannot be.                                         #
#                                                                                        #
# Every one of them is a judgement, not a fact: a configuration can use %total in two       #
# Tasks on purpose, and two spellings of a name can be two things a person chose.  So the   #
# report says what it saw and what it would change, and the change is the user's to make     #
# (mapscope builds it, with a preview and one Undo).                                       #
#                                                                                        #
# Same contract as healthck, errcheck and proflint: reads PrimeItems.tasker_root_elements   #
# and state.xml_root and nothing else -- no GUI, no output_lines, no device -- and the     #
# dependency runs healthck -> scopecheck, never the other way, so the severity words and    #
# the record are spelled out again here.                                                    #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.core.mapjump import VARIABLE, Target
from maptasker.src.mapgen import varxref

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# Two of healthck's three grading words, spelled out rather than imported (see the header).
WARNING = "WARNING"
INFO = "INFO"

CASE_MISMATCH = "SCOPE-CASE-MISMATCH"
DECLARED_LOWERCASE = "SCOPE-DECLARED-LOWERCASE"
LOCAL_NEVER_SET = "SCOPE-LOCAL-NEVER-SET"
TAGS = frozenset({CASE_MISMATCH, DECLARED_LOWERCASE, LOCAL_NEVER_SET})

# The word a Perform Task action is, in Tasker's own numbering.
_PERFORM_TASK_CODE = "130"

# How many Tasks a finding names before "and N more".
_TASKS_NAMED = 3


@dataclass
class ScopeIssue:
    """One variable whose spelling and use disagree, and the spelling that would settle it.

    `owner` is varxref's: a Task id for one local, "" for a global, and None for every Task's local of the name --
    the way maprefac_variable says it, so this can be handed straight to it.  `suggestion` is "" when there is no
    single answer (two globals fold to the same letters, so which was meant is not for this to say).
    """

    kind: str
    name: str  # "%aab_animsteps"
    owner: str | None
    suggestion: str  # "%AAB_AnimSteps", or "" when there is no one answer
    merge: bool  # the suggestion is a variable that already exists: the fix folds this one into it
    where: Target  # the first place it is used, to jump to
    detail: str
    uses: int
    places: list[Target] = field(default_factory=list[Target])

    @property
    def severity(self) -> str:
        """A global in the Variables tab spelled as a local is certainly wrong; the rest are judgements, worth a look."""
        return WARNING if self.kind == DECLARED_LOWERCASE else INFO


def _tasks_that_are_performed(state: RunState) -> set[str]:
    """The ids of the Tasks some Perform Task action names.

    A Task that is performed can be handed local variables by its caller ('Pass Through Local Variables' on the
    action), so a read of a local it never sets is not evidence of anything: the value came with the call.
    """
    tables = state.tasker_root_elements
    by_name = {task["name"]: task_id for task_id, task in tables["all_tasks"].items() if task["name"]}
    performed: set[str] = set()
    for task in tables["all_tasks"].values():
        for action in task["xml"].findall("Action"):
            if (action.findtext("code") or "").strip() != _PERFORM_TASK_CODE:
                continue
            name = next((child.text or "" for child in action if child.attrib.get("sr") == "arg0"), "").strip()
            if name in by_name:
                performed.add(by_name[name])
    return performed


def _use_count(variable: varxref.Variable) -> int:
    """How many places set or read it."""
    return len(variable.sets) + len(variable.reads)


def _first_place(variables: list[varxref.Variable]) -> Target | None:
    """The first place any of these is used, or None for a name used nowhere a click can go."""
    for variable in variables:
        for reference in (*variable.sets, *variable.reads):
            if reference.target is not None:
                return reference.target
    return None


def _task_owners(index: varxref.VariableIndex, owners: list[str]) -> str:
    """ "Task 'A', Task 'B' and 2 more" for the Tasks a local is used in."""
    labels = [location.label for owner in owners if (location := index.scope_locations.get(owner)) is not None]
    shown = ", ".join(labels[:_TASKS_NAMED])
    return f"{shown} and {len(labels) - _TASKS_NAMED} more" if len(labels) > _TASKS_NAMED else shown


def _globals_by_letters(index: varxref.VariableIndex) -> dict[str, list[str]]:
    """{the letters, in lower case: every spelling of a global that has them}.  Too-short names are left out."""
    found: dict[str, set[str]] = {}
    for (name, owner), variable in index.variables.items():
        if variable.scope == varxref.GLOBAL and not owner and len(name) - 1 > varxref.LOW_CONFIDENCE_LENGTH:
            found.setdefault(name.casefold(), set()).add(name)
    return {letters: sorted(spellings) for letters, spellings in found.items()}


def _task_ids_using(variable: varxref.Variable | None) -> set[str]:
    """The ids of the Tasks (and Scenes, and Profiles) that set or read this variable."""
    return {reference.scope_id for reference in (*variable.sets, *variable.reads)} if variable else set()


def _case_mismatches(
    index: varxref.VariableIndex, globals_by_letters: dict[str, list[str]], performed: set[str]
) -> list[ScopeIssue]:
    """Lower case names, one per Task, that are the same letters as a global and are used in a lopsided way.

    Two things keep this from reporting a deliberate habit.  A Task that spells BOTH ways has plainly seen the
    difference -- `%aab_animsteps=%AAB_AnimSteps` copies a global into a local on purpose, and is how a lot of
    Tasks are written -- so it is left alone.  And a local the Task both sets and reads is a local doing its job.
    A Task that something performs is left out of the read-only case for the reason _tasks_that_are_performed gives.
    What is left is the evidence of a slip: a name only ever read (a value nothing in the Task put there, from a
    global it was never spelled to reach), or only ever set (a write that is lost when the Task ends).
    """
    issues: list[ScopeIssue] = []
    for (name, owner), variable in index.variables.items():
        if variable.scope != varxref.LOCAL or len(name) - 1 <= varxref.LOW_CONFIDENCE_LENGTH:
            continue
        if owner not in index.scope_locations or (spellings := globals_by_letters.get(name.casefold())) is None:
            continue
        if bool(variable.sets) == bool(variable.reads):
            continue  # both, or neither: a local doing its job
        if variable.reads and owner in performed:
            continue  # a performed Task is handed locals by its caller, so a read of one proves nothing
        if any(owner in _task_ids_using(index.variables.get((spelling, ""))) for spelling in spellings):
            continue  # the Task spells the global too: a copy made on purpose
        where = _first_place([variable])
        if where is None:
            continue
        task = index.scope_locations[owner].label
        way = "reads" if variable.reads else "sets"
        lost = (
            "nothing in this Task ever put a value there" if variable.reads else "the value is gone when the Task ends"
        )
        if len(spellings) == 1:
            suggestion = spellings[0]
            detail = (
                f"{task} {way} {name}, which Tasker reads as a LOCAL of that Task, and the Task never spells the global "
                f"{suggestion} -- the same letters -- that the rest of the file uses.  They are two variables, so "
                f"{lost}.  If {suggestion} was meant, spell it that way."
            )
        else:
            suggestion = ""
            detail = (
                f"{task} {way} {name}, which Tasker reads as a LOCAL of that Task, and the file has globals of the same "
                f"letters spelled {', '.join(spellings)}.  Which was meant is not something the file says."
            )
        issues.append(
            ScopeIssue(CASE_MISMATCH, name, owner, suggestion, bool(suggestion), where, detail, _use_count(variable))
        )
    return issues


def _declared_lowercase(index: varxref.VariableIndex) -> list[ScopeIssue]:
    """Names in the Variables tab with no capital in them."""
    issues: list[ScopeIssue] = []
    for name in sorted(index.declared_names):
        if any(character.isupper() for character in name) or len(name) - 1 <= varxref.LOW_CONFIDENCE_LENGTH:
            continue
        variable = index.variables.get((name, ""))
        if variable is None or not _use_count(variable):
            where = Target(VARIABLE, name, name)
        else:
            where = _first_place([variable]) or Target(VARIABLE, name, name)
        suggestion = f"%{name[1:2].upper()}{name[2:]}"
        detail = (
            f"{name} is in Tasker's Variables tab, which holds globals only -- but Tasker takes scope from the "
            f"spelling, so an action that writes {name} is using a LOCAL of that name and never reaches the one in "
            f"the tab.  Spelled {suggestion}, both would be the same global."
        )
        issues.append(
            ScopeIssue(
                DECLARED_LOWERCASE, name, "", suggestion, False, where, detail, _use_count(variable) if variable else 0
            ),
        )
    return issues


def _never_set(index: varxref.VariableIndex, performed: set[str], covered: set[str]) -> list[ScopeIssue]:
    """Locals read and never set in a Task nothing performs, that another Task sets."""
    by_name: dict[str, list[varxref.Variable]] = {}
    for (name, owner), variable in index.variables.items():
        long_enough = len(name) - 1 > varxref.LOW_CONFIDENCE_LENGTH
        if variable.scope == varxref.LOCAL and owner in index.scope_locations and name not in covered and long_enough:
            by_name.setdefault(name, []).append(variable)

    issues: list[ScopeIssue] = []
    for name, instances in sorted(by_name.items()):
        readers = [item for item in instances if item.reads and not item.sets and item.owner not in performed]
        setters = [item for item in instances if item.sets and item not in readers]
        if not readers or not setters:
            continue
        where = _first_place(readers)
        if where is None:
            continue
        suggestion = f"%{name[1:2].upper()}{name[2:]}"
        detail = (
            f"{_task_owners(index, [item.owner for item in readers])} read{'s' if len(readers) == 1 else ''} {name} "
            f"and never set{'s' if len(readers) == 1 else ''} it, and nothing performs "
            f"{'that Task' if len(readers) == 1 else 'those Tasks'} to hand it one.  {name} is a LOCAL, empty "
            f"when its Task starts -- yet {_task_owners(index, [item.owner for item in setters])} set"
            f"{'s' if len(setters) == 1 else ''} one of the same name.  If they were meant to share it, it has to be "
            f"global: {suggestion}."
        )
        issues.append(
            ScopeIssue(
                LOCAL_NEVER_SET,
                name,
                None,
                suggestion,
                False,
                where,
                detail,
                sum(_use_count(item) for item in instances),
            ),
        )
    return issues


def find_issues(state: RunState, index: varxref.VariableIndex | None = None) -> list[ScopeIssue]:
    """Every variable in the configuration whose spelling and use disagree, worst first, then by name.

    The index is varxref's, of the WHOLE configuration.  Safe to call with nothing loaded: an empty list comes back.
    """
    index = index if index is not None else varxref.build_index(state=state)
    performed = _tasks_that_are_performed(state)
    mismatches = _case_mismatches(index, _globals_by_letters(index), performed)
    declared = _declared_lowercase(index)
    # A name already reported as a mis-cased global is not also reported as a local that is never set.
    covered = {issue.name for issue in mismatches}
    never_set = _never_set(index, performed, covered)
    order = {CASE_MISMATCH: 0, DECLARED_LOWERCASE: 1, LOCAL_NEVER_SET: 2}
    return sorted([*mismatches, *declared, *never_set], key=lambda issue: (order[issue.kind], issue.name.casefold()))
