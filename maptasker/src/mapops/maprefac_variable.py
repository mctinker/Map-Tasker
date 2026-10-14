"""maprefac_variable: rename a variable, or change it between global and local, wherever it is used.

Three moves, one machinery: RENAME keeps the variable's scope and changes its name, TO_LOCAL turns a global into
a Task's own local, TO_GLOBAL turns a local into a global.  Where the variable is used -- every action argument,
condition, Scene binding and the Variables tab -- comes from varxref, and how a name is rewritten in a field comes
from mapswap_rename; what is added here is the judgement of whether the change is SAFE, and the Plan that carries
it to maprefac.apply, which makes the whole thing one Undo."""

#! /usr/bin/env python3

#                                                                                        #
# maprefac_variable: the variable rename and scope assistant.                            #
#                                                                                        #
# mapswap_rename already rewrites every use of a variable, one field at a time, with a   #
# tick box per field.  That is the right shape for "say %total where this Task says      #
# %sum".  It is the wrong shape for the question this module answers, which is "is this  #
# variable a global or a local, and should it be the other one" -- because that is not   #
# a rewrite of text, it is a change to WHO CAN SEE THE VALUE:                            #
#                                                                                        #
#   Tasker decides scope from the SPELLING.  %counter (all lower case) is private to    #
#   the running Task; %Counter (any capital) is one variable for the whole file.  So     #
#   changing a variable's case changes which Tasks, Scenes and Profile conditions        #
#   share it, and nothing about the result looks different on screen.                    #
#                                                                                        #
# That is why this is a Refactor and not a Replace, and why it follows maprefac's two    #
# rules rather than mapswap's:                                                           #
#                                                                                        #
#   ALL OR NOTHING.  Half a scope change is not a smaller scope change, it is one        #
#   variable that three Tasks spell two ways.  So there are no tick boxes, and what      #
#   mapswap would call a Skip -- a place that could not be rewritten -- is a WARNING     #
#   here (the plan still stands, and the preview says what it cannot reach).  What       #
#   mapswap would proceed with is a BLOCK when it is a reason not to do this at all.     #
#                                                                                        #
#   ONE UNDO.  apply() runs plan.run inside one sessundo block.                          #
#                                                                                        #
# THE WHOLE CONFIGURATION, ALWAYS.  The Replace tab narrows to whatever single item the  #
# pulldowns select, which is right for a bulk edit the user is steering.  A global       #
# changed in only part of the file is a global spelled two ways, so this reads every     #
# Project, however little is on screen.  (A local never leaves its Task, so for those    #
# the whole-file read costs nothing and hides nothing.)                                  #
#                                                                                        #
# WHAT BLOCKS, AND WHY EACH ONE IS A BLOCK                                               #
#                                                                                        #
#   NAME CLASH.  The new name is already a variable -- another global of that spelling,  #
#   or a local of that name in a Task that uses this one.  The two would silently become #
#   one.  A merge is a real thing to want, and mapswap's Replace does it on purpose, with #
#   a preview that says so; here it is refused, because "rename" must never mean "merge". #
#                                                                                        #
#   A GLOBAL THAT CANNOT BECOME A LOCAL.  A local exists only inside a running Task:     #
#     - A Scene, a Profile's condition or a Project's settings cannot see one.           #
#     - A Task that reads the variable before it has set it is relying on a value left   #
#       behind by an earlier run or by another Task.  A local starts empty every time.   #
#                                                                                        #
#   A NAME TASKER WOULD READ AS SOMETHING ELSE.  A local must be all lower case, a       #
#   global needs a capital, and neither may look like one of Tasker's own (%BATT, %par1). #
#                                                                                        #
# WHAT IS ONLY A WARNING                                                                 #
#                                                                                        #
#   Several Tasks that used to share a global each get a copy of their own.  A local     #
#   promoted to a global keeps its value between runs and is shared by two copies of the #
#   Task running at once.  The Variables tab keeps an entry nothing uses any more.       #
#   Something outside the file -- a widget, another app -- keeps using the global.  An   #
#   action that builds the name at run time might be touching it.  Each of these is a    #
#   consequence of what the user asked for, which they can read and accept.              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from maptasker.src.mapgen import varxref
from maptasker.src.mapops import mapswap_rename, mapswap_sites
from maptasker.src.mapops.maprefac_model import VARIABLE, Block, Plan, Step, blocked
from maptasker.src.mapops.mapswap_model import DECLARATION, Change
from maptasker.src.mapops.mapswap_model import Plan as SwapPlan

if TYPE_CHECKING:
    import re
    from collections.abc import Callable

    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

# What can be asked of a variable.
RENAME = "rename"
TO_LOCAL = "local"
TO_GLOBAL = "global"

# Passed as the owner to mean every instance of a local's name, one per Task.
EVERY_INSTANCE = mapswap_rename.EVERY_INSTANCE

# How many blocks of one kind are written out before the rest are counted.  A global used by sixty Tasks that
# cannot become a local is one answer, not sixty.
_BLOCK_LIMIT = 12
# How many changed fields are listed under one object before the rest are counted.
_DETAIL_LIMIT = 6
# How much of a changed field is shown either side of the variable.
_CONTEXT = 28

_KEY_SEPARATOR = "|"
_ALL_INSTANCES = "*"


# ##################################################################################
# Names, and the keys the dialog's pulldown uses.
# ##################################################################################


def percent(name: str) -> str:
    """A variable name with its one leading '%', whether or not it came with one."""
    return f"%{name.strip().lstrip('%')}"


def suggested_name(operation: str, name: str) -> str:
    """The new name a scope change implies: lower case for a local, a leading capital for a global.

    Empty for a rename, which has no implied name.  Tasker takes the scope from the spelling, so changing the
    scope IS changing the spelling -- the user is only ever choosing between the obvious spelling and one of their
    own.
    """
    full = percent(name)
    if operation == TO_LOCAL:
        return full.lower()
    if operation == TO_GLOBAL:
        return f"%{full[1:2].upper()}{full[2:]}"
    return ""


def choice_key(name: str, owner: str | None) -> str:
    """A pulldown key for a variable: its name and its owner, as one string.

    The owner is a Task id for a local, "" for a global and "*" for every instance of a local's name.  A name
    cannot contain the separator (Tasker names are letters, digits and underscores), so the first one splits it.
    """
    return f"{name}{_KEY_SEPARATOR}{_ALL_INSTANCES if owner is EVERY_INSTANCE else owner}"


def split_key(key: str) -> tuple[str, str | None]:
    """The (name, owner) a choice_key was made from."""
    name, _, owner = key.partition(_KEY_SEPARATOR)
    return name, EVERY_INSTANCE if owner == _ALL_INSTANCES else owner


def variable_choices(index: varxref.VariableIndex, operation: str) -> list[tuple[str, str]]:
    """The variables worth offering for an operation, as (key, label), busiest first.

    A scope change is offered only the variables it can be asked of -- a local to make global, a global to make
    local -- rather than listing everything and refusing the rest in the preview.  The ones Tasker supplies
    (%par1, %err) are left out of every list: no spelling of them is yours to choose.
    """
    wanted = {RENAME: (varxref.GLOBAL, varxref.LOCAL), TO_LOCAL: (varxref.GLOBAL,), TO_GLOBAL: (varxref.LOCAL,)}[
        operation
    ]
    choices: list[tuple[str, str]] = []
    for name, owner, label in mapswap_rename.variable_choices(index):
        if index.scope_for(name) in wanted:
            choices.append((choice_key(name, owner), label))
    return choices


# ##################################################################################
# Reading the index.
# ##################################################################################


def _is_task(owner: str) -> bool:
    """Whether a varxref scope id is a Task (a bare id) rather than a Scene, Profile or Project (prefixed)."""
    return bool(owner) and ":" not in owner


def _is_one_of(variable: varxref.Variable, entries: list[varxref.Variable]) -> bool:
    """Whether a variable is itself one of those being changed -- identity, since two records can be equal."""
    return any(variable is entry for entry in entries)


def _places(entries: list[varxref.Variable]) -> list[varxref.Reference]:
    """Every reference of every entry, sets first, in scan order."""
    return [reference for entry in entries for reference in entry.sets + entry.reads]


def _owners(entries: list[varxref.Variable]) -> list[str]:
    """The Tasks (and Scenes, Profiles) whose copy of the variable this change reaches, in the order met.

    A local has exactly one owner.  A global has none of its own, so its owners are whoever uses it.
    """
    found: dict[str, None] = {}
    for entry in entries:
        if entry.scope == varxref.LOCAL:
            found[entry.owner] = None
            continue
        for reference in entry.sets + entry.reads:
            found[reference.scope_id] = None
    return list(found)


def _label(index: varxref.VariableIndex, owner: str) -> str:
    """How an owner is named in a sentence: "Project 'Home' > Task 'Morning' (id 20)"."""
    location = index.scope_locations.get(owner)
    return location.label if location else f"Task {owner}"


def _first_target(references: list[varxref.Reference]) -> Target | None:
    """The first place in a list that a click can jump to."""
    return next((reference.target for reference in references if reference.target is not None), None)


def _where_phrase(index: varxref.VariableIndex, old: str, owners: list[str]) -> str:
    """Where a local's change applies: " in Task X", " in 3 Tasks", or nothing for a global."""
    if index.scope_for(old) != varxref.LOCAL or not owners:
        return ""
    return f" in {_label(index, owners[0])}" if len(owners) == 1 else f" in {len(owners)} Tasks"


def _headline(operation: str, old: str, new: str, index: varxref.VariableIndex, owners: list[str]) -> str:
    """The plan's one-line title: the preview's heading, the report's title and the Undo label."""
    if operation == TO_LOCAL:
        return f"Make {old} a local variable ({new})"
    where = _where_phrase(index, old, owners)
    if operation == TO_GLOBAL:
        return f"Make {old} a global variable ({new}){where}"
    return f"Rename {old} to {new}{where}"


# ##################################################################################
# What stops it.
# ##################################################################################


def _kind_blocks(operation: str, entries: list[varxref.Variable], old: str) -> list[Block]:
    """A variable this cannot be asked of: one Tasker supplies, or one already the scope it is being made."""
    scopes = {entry.scope for entry in entries}
    if scopes & {varxref.BUILTIN, varxref.TASKER_SET}:
        return [
            Block(
                "TASKER-VARIABLE",
                f"{old} is one of Tasker's own variables, or has the shape of one.  Tasker sets it, so no "
                f"spelling of it is yours to choose.",
            ),
        ]
    already = {TO_LOCAL: varxref.LOCAL, TO_GLOBAL: varxref.GLOBAL}.get(operation)
    if already in scopes:
        return [Block("WRONG-SCOPE", f"{old} is already a {already} variable.")]
    return []


def _spelling_blocks(
    operation: str,
    index: varxref.VariableIndex,
    entries: list[varxref.Variable],
    new: str,
) -> list[Block]:
    """A new name Tasker would read as a different scope from the one asked for.

    Tasker takes the scope from the spelling, so this is the check that the name does what the user thinks.
    """
    kept = next((entry.scope for entry in entries), varxref.GLOBAL)
    wanted = {RENAME: kept, TO_LOCAL: varxref.LOCAL, TO_GLOBAL: varxref.GLOBAL}[operation]
    if index.scope_for(new) == wanted:
        return []
    if operation == RENAME:
        how = (
            f"A rename keeps the variable {wanted}, and Tasker would read {new} as something else.  To change "
            f"the scope, use 'Make local' or 'Make global'."
        )
    elif wanted == varxref.LOCAL:
        how = f"A local variable's name is all lower case; {new} has a capital, which Tasker reads as a global."
    else:
        how = (
            f"A global variable's name has at least one capital; {new} is all lower case, which Tasker reads "
            f"as a local."
        )
    return [Block("SPELLING", how)]


def _clash_block(index: varxref.VariableIndex, clash: varxref.Variable, old: str, new: str, owner: str) -> Block:
    """A new name that is already a variable in the place the change would put it."""
    where = "the configuration" if clash.scope != varxref.LOCAL else _label(index, owner)
    return Block(
        "NAME-CLASH",
        f"{where} already has a variable named {new}: it is set in {len(clash.sets)} and read in "
        f"{len(clash.reads)} place(s).  Changing {old} to {new} would make the two ONE variable, so everything "
        f"that read one would start reading what the other holds.  Choose a name nothing uses, or merge them on "
        f"purpose with Replace in Find (its Variable mode previews a merge).",
        _first_target(clash.sets + clash.reads),
    )


def _clash_blocks(index: varxref.VariableIndex, entries: list[varxref.Variable], old: str, new: str) -> list[Block]:
    """Every place the new name is already taken.

    For a global that is one place, the whole file.  For a local it is every Task the change reaches: %total
    free in one Task is no use to a Task that already has a %total of its own.
    """
    if index.scope_for(new) != varxref.LOCAL:
        clash = index.variables.get((new, ""))
        if clash is None or _is_one_of(clash, entries):
            return []
        return [_clash_block(index, clash, old, new, "")]

    blocks: list[Block] = []
    for owner in _owners(entries):
        clash = index.variables.get((new, owner))
        if clash is not None and not _is_one_of(clash, entries):
            blocks.append(_clash_block(index, clash, old, new, owner))
    return blocks


def _outside_a_task_block(index: varxref.VariableIndex, references: list[varxref.Reference], old: str) -> list[Block]:
    """A global used where no Task runs -- a Scene, a Profile condition, a Project's settings."""
    outside = [reference for reference in references if not _is_task(reference.scope_id)]
    if not outside:
        return []
    owners = list(dict.fromkeys(reference.scope_id for reference in outside))
    named = ", ".join(_label(index, owner) for owner in owners[:3]) + (", ..." if len(owners) > 3 else "")
    return [
        Block(
            "USED-OUTSIDE-A-TASK",
            f"{old} is used by {named}.  A local variable exists only inside a running Task, so a Scene, a "
            f"Profile's condition or a Project's settings cannot see one -- they would go on reading {old} "
            f"while every Task wrote somewhere else.",
            _first_target(outside),
        ),
    ]


def _stale_read_block(
    index: varxref.VariableIndex,
    owner: str,
    references: list[varxref.Reference],
    old: str,
) -> Block | None:
    """A Task that reads the variable before anything in it has set it.

    That read is getting its value from somewhere else -- an earlier run, another Task, the Variables tab -- and a
    local starts empty every time the Task runs.  Judged by action number, so a read in the same action as the
    first set counts as before it: 'Variable Add %n 1' reads %n before it writes it.
    """
    located = [
        (reference.target.action, reference)
        for reference in references
        if reference.scope_id == owner and reference.target is not None and reference.target.action
    ]
    first_set = min((action for action, reference in located if reference.role == varxref.SET), default=None)
    early = [
        (action, reference)
        for action, reference in located
        if reference.role == varxref.READ and (first_set is None or action <= first_set)
    ]
    if not early:
        return None
    number, first = early[0]
    return Block(
        "READ-BEFORE-SET",
        f"{_label(index, owner)} reads {old} at action {number} "
        f"{'before anything in it has set it' if first_set else 'and never sets it'}, so it relies on a value "
        f"left by an earlier run or by another Task.  A local variable starts out empty every time the Task "
        f"runs, so that action would no longer do what it does now.",
        first.target,
    )


def _localising_blocks(
    index: varxref.VariableIndex,
    entries: list[varxref.Variable],
    old: str,
) -> list[Block]:
    """Everything that stops a global becoming a local, other than its new name."""
    references = _places(entries)
    blocks = _outside_a_task_block(index, references, old)
    stale = [
        block
        for owner in _owners(entries)
        if _is_task(owner) and (block := _stale_read_block(index, owner, references, old)) is not None
    ]
    blocks.extend(stale[:_BLOCK_LIMIT])
    if len(stale) > _BLOCK_LIMIT:
        blocks.append(
            Block(
                "READ-BEFORE-SET", f"... and {len(stale) - _BLOCK_LIMIT} more Tasks that read {old} before setting it."
            ),
        )
    return blocks


def _blocks(
    operation: str,
    index: varxref.VariableIndex,
    entries: list[varxref.Variable],
    old: str,
    new: str,
) -> list[Block]:
    """Every reason this change will not be made, or an empty list.

    A name that cannot be used at all is the whole answer: the clashes and the stale reads of a name that was
    never going to be written are not worth the user's scroll.
    """
    if not entries:
        return [Block("NOT-USED", f"{old} is not used anywhere in this configuration.")]

    problems = _kind_blocks(operation, entries, old)
    if problems:
        return problems

    refusal = mapswap_rename.rename_refusal(old, new)
    if refusal:
        return [Block("NAME", refusal)]

    problems = _spelling_blocks(operation, index, entries, new)
    if problems:
        return problems

    blocks = _clash_blocks(index, entries, old, new)
    if operation == TO_LOCAL:
        blocks.extend(_localising_blocks(index, entries, old))
    return blocks


# ##################################################################################
# What it will do, and what to read first.
# ##################################################################################


def _warnings(
    operation: str,
    index: varxref.VariableIndex,
    entries: list[varxref.Variable],
    old: str,
    new: str,
) -> list[str]:
    """What the user should read before pressing Apply.  Each of these proceeds."""
    warnings: list[str] = []
    owners = _owners(entries)
    tasks = [owner for owner in owners if _is_task(owner)]

    if operation == TO_LOCAL:
        warnings.extend(_localising_warnings(entries, old, new, tasks))
    elif operation == TO_GLOBAL:
        warnings.extend(_globalising_warnings(index, entries, old, new, tasks))

    warnings.extend(mapswap_rename.side_effect_warnings(entries, old, new))
    if index.indirect_references:
        warnings.append(
            f"{index.indirect_references} actions in this configuration build the name of the variable they use "
            f"at run time ('Variable Set %(%which)').  Any of them could be touching {old}, and none of them can "
            f"be rewritten -- check them by hand.",
        )
    return warnings


def _localising_warnings(entries: list[varxref.Variable], old: str, new: str, tasks: list[str]) -> list[str]:
    """The consequences of a global becoming a local that are not reasons to refuse."""
    warnings: list[str] = []
    if len(tasks) > 1:
        warnings.append(
            f"{len(tasks)} Tasks use {old}.  Each gets a {new} of its own, so they stop sharing one value -- "
            f"which is the point of a global, and exactly what is being given up.",
        )
    entry = entries[0]
    if entry.declared:
        value = f" (it holds {entry.value!r})" if entry.value else ""
        warnings.append(
            f"Tasker's Variables tab keeps its entry for {old}{value}.  Nothing reads it once the Tasks use {new}, "
            f"so delete it there.",
        )
    if not entry.reads and entry.sets:
        warnings.append(
            f"Nothing in this configuration reads {old}.  If something outside it does -- a home-screen "
            f"widget, another app -- it will stop seeing the value.",
        )
    warnings.append(f"Anything outside this file that uses the global {old} keeps using it.")
    return warnings


def _globalising_warnings(
    index: varxref.VariableIndex,
    entries: list[varxref.Variable],
    old: str,
    new: str,
    tasks: list[str],
) -> list[str]:
    """The consequences of a local becoming a global that are not reasons to refuse."""
    warnings = [
        (
            f"{new} will be ONE variable for the whole configuration.  It keeps its value after the Task ends, "
            f"every Task or Scene that spells it that way shares it, and two copies of the Task running at once "
            f"overwrite each other."
        ),
    ]
    if len(tasks) > 1:
        named = ", ".join(_label(index, owner) for owner in tasks[:3]) + (", ..." if len(tasks) > 3 else "")
        warnings.append(
            f"{old} is a LOCAL, so these are {len(tasks)} separate variables, one per Task ({named}).  All of "
            f"them become the same {new}, and each Task will see what the others leave in it.",
        )
    if any(entry.scope == varxref.LOCAL and entry.owner and not _is_task(entry.owner) for entry in entries):
        warnings.append(f"{old} is used in a Scene or a Profile, which will now read the global {new}.")
    return warnings


def _around(value: str, pattern: re.Pattern[str]) -> str:
    """A field's value cut down to the variable and what is next to it, with an ellipsis where it was cut."""
    flat = " ".join(value.split())
    found = pattern.search(flat)
    if found is None or len(flat) <= 2 * _CONTEXT + len(found.group(0)):
        return flat
    start, end = max(0, found.start() - _CONTEXT), min(len(flat), found.end() + _CONTEXT)
    return f"{'...' if start else ''}{flat[start:end]}{'...' if end < len(flat) else ''}"


def _object_target(target: Target) -> Target:
    """The Task, Scene or Profile a place is in -- the place with its action and part taken off."""
    return dataclasses.replace(target, action=0, part="", within="")


def _steps(changes: list[Change], old: str, new: str) -> list[Step]:
    """The changes as numbered steps, one per object, with the fields it touches listed beneath.

    An object's own line is the step (and is what gets numbered); the fields under it are indented, which
    maprefac.report_rows treats as a continuation.  Each is a link to the action itself.
    """
    before_pattern, after_pattern = mapswap_rename.rename_pattern(old), mapswap_rename.rename_pattern(new)
    groups: dict[tuple[str, str], list[Change]] = {}
    for change in changes:
        where = change.site.where
        groups.setdefault((where.kind, where.key), []).append(change)

    steps: list[Step] = []
    for members in groups.values():
        target = _object_target(members[0].site.where)
        count = len(members)
        steps.append(Step(f"{target.label}: {count} place{'s' if count != 1 else ''}", target))
        steps.extend(_detail_steps(members, before_pattern, after_pattern))
    return steps


def _detail_steps(members: list[Change], before_pattern: re.Pattern[str], after_pattern: re.Pattern[str]) -> list[Step]:
    """The indented lines under an object: where in it, and what the field says before and after."""
    steps: list[Step] = []
    for change in members[:_DETAIL_LIMIT]:
        where = change.site.where
        place = f"action {where.action}" if where.action else (where.within or where.part or "")
        place = f"{place}, " if place else ""
        steps.append(
            Step(
                f"    {place}{change.site.detail}  {_around(change.before, before_pattern)}  ->  "
                f"{_around(change.after, after_pattern)}",
                where,
            ),
        )
    if len(members) > _DETAIL_LIMIT:
        steps.append(Step(f"    ... and {len(members) - _DETAIL_LIMIT} more here"))
    return steps


def _declaration_last(change: Change) -> bool:
    """Sort key putting the Variables tab entry after every use.

    If it went first and something later failed, the file would hold a declaration for a name nothing uses and
    none for the name everything does -- the one half-done state that still looks like a configuration.
    """
    return change.site.kind == DECLARATION


def _collect_changes(
    operation: str,
    entries: list[varxref.Variable],
    old: str,
    new: str,
    state: RunState,
) -> list[Change]:
    """Every field the change rewrites, from mapswap_rename's own scan, and the Variables tab entry if there is one.

    The declaration is only renamed by a RENAME: a global becoming a local leaves its entry behind (see
    _localising_warnings), and a local has none.
    """
    swap = SwapPlan(what="")
    pattern = mapswap_rename.rename_pattern(old)
    mapswap_rename.plan_rename_sites(swap, entries, old, pattern, new)
    changes = list(swap.changes)
    if operation == RENAME:
        declaration = mapswap_sites.declaration_site(old, entries, (pattern, new), state=state, everywhere=True)
        if declaration is not None:
            before, after = mapswap_sites.rewrite_site(declaration, pattern, new)
            if before != after:
                changes.append(Change(site=declaration, before=before, after=after))
    return changes


def _runner(changes: list[Change], state: RunState) -> Callable[[], list[str]]:
    """The change itself, as the closure maprefac.apply runs inside its one undo block.

    Each field is written from what it holds NOW (write_site computes that), so a field edited since the preview
    is rewritten correctly rather than overwritten with a stale value.  The Variables tab entry goes last.
    """
    ordered = sorted(changes, key=_declaration_last)

    def run() -> list[str]:
        errors: list[str] = []
        for change in ordered:
            try:
                mapswap_sites.write_site(change.site, state=state)
            except (AttributeError, KeyError, ValueError) as failure:
                errors.append(f"{change.site.where.label}: {failure}")
        return errors

    return run


def plan_variable(
    operation: str,
    name: str,
    owner: str | None,
    new_name: str,
    state: RunState,
    index: varxref.VariableIndex | None = None,
) -> Plan:
    """Everything this change to a variable would do, or the reasons it cannot be done.

    `owner` is varxref's own: a Task id for one local, "" for a global, EVERY_INSTANCE for every Task's local of
    that name.  An empty `new_name` means the one the scope implies (see suggested_name).  `index` is the
    cross-reference to read, built here if not given; it should describe the WHOLE configuration.
    """
    old = percent(name)
    new = percent(new_name) if new_name.strip() else suggested_name(operation, old)
    index = index if index is not None else varxref.build_index(state=state)
    entries = mapswap_rename.entries_to_rename(index, old, owner)
    what = _headline(operation, old, new, index, _owners(entries))

    problems = _blocks(operation, index, entries, old, new)
    if problems:
        return blocked(VARIABLE, what, *problems)

    changes = _collect_changes(operation, entries, old, new, state)
    if not changes:
        return blocked(
            VARIABLE,
            what,
            Block(
                "NOTHING-TO-REWRITE",
                f"{old} is not written anywhere that this can change: it is only declared in Tasker's Variables tab, "
                f"or produced by a plugin that never names it.  There is no text in a Task, condition or Scene to "
                f"rewrite.",
            ),
        )
    plan = Plan(kind=VARIABLE, what=what)
    plan.warnings = _warnings(operation, index, entries, old, new)
    plan.steps = _steps(changes, old, new)
    plan.elements = tuple(change.site.element for change in changes)
    plan.run = _runner(changes, state)
    return plan
