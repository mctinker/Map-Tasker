"""mapswap_rename: renaming every use of a variable, or folding it into another variable."""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

from maptasker.src.core.mapjump import current_scope
from maptasker.src.core.taskervars import tasker_global_variables
from maptasker.src.mapgen import varxref
from maptasker.src.mapgen.varxref import _LOW_CONFIDENCE_LENGTH, VARIABLE_PATTERN
from maptasker.src.mapops.mapswap_model import BLOCKED_INDIRECT, Change, Plan, Site, Skip
from maptasker.src.mapops.mapswap_sites import declaration_site, is_plugin_declaration, rewrite_site, site_kind

if TYPE_CHECKING:
    from maptasker.src.core.mapjump import Scope
    from maptasker.src.core.primitem import RunState


def variable_choices(index: varxref.VariableIndex) -> list[tuple[str, str, str]]:
    """(name, owner, label) for every variable that could be renamed, commonest first.

    Locals carry their Task in the label because they ARE per-Task: two Tasks using
    %counter have two variables, and a pulldown that showed one '%counter' would be
    offering to rename something that does not exist.

    A name used by more than one instance ALSO gets an all-instances entry, carrying
    EVERY_INSTANCE as its owner -- "rename the loop counter throughout" needs a way to be
    said, and typing the name into a box would not distinguish it from picking one of the
    59 Tasks that use %i.  It sits directly above that name's individual entries, sorted
    with them, so the choice between "this one" and "all of them" is made in one place
    rather than by finding a checkbox somewhere else.

    The ones plan_variable_rename would refuse outright are left out rather than offered
    and then rejected -- a built-in and a one-character name cannot become renameable by
    anything the user types in the other box.
    """
    choices = []
    instances: Counter = Counter()
    totals: Counter = Counter()
    for (name, _owner), variable in index.variables.items():
        if _rename_refusal(name, f"{name}_"):
            continue
        instances[name] += 1
        totals[name] += len(variable.sets) + len(variable.reads)

    for (name, owner), variable in index.variables.items():
        if _rename_refusal(name, f"{name}_"):
            continue  # Refused whatever it would be renamed to.
        uses = len(variable.sets) + len(variable.reads)
        where = ""
        if owner:
            location = index.scope_locations.get(owner)
            where = f" in {location.label}" if location else f" in {owner}"
        label = f"{name}  ({variable.scope}{where}: set {len(variable.sets)}, read {len(variable.reads)})"
        # Sunk to the bottom rather than left out: renaming one of these is almost always a
        # mistake -- something outside the file puts the value there, so the new name would
        # never hold anything -- and %err, %errmsg and %priority are among the most used
        # names in any configuration, so ranking purely by use opens the list on three
        # entries nobody wants.  Still offered, because varxref recognises the built-in
        # SHAPE as well as the documented list, and that shape also covers somebody's own
        # SHOUTING global.
        pointless = variable.scope in (varxref.TASKER_SET, varxref.BUILTIN)
        choices.append((name, owner, label, uses, pointless))

    # Ranked by the NAME's total use, not the instance's, so every entry for one name
    # stays together instead of the busiest Task's %i sorting hundreds of rows away from
    # the next Task's.  The all-instances entry leads its group (the -1 ordinal), and
    # within the individual ones the busiest comes first.
    for name, count in instances.items():
        if count < 2:
            continue  # One instance: "all of them" and "this one" are the same entry.
        variable = next(entry for (candidate, _o), entry in index.variables.items() if candidate == name)
        pointless = variable.scope in (varxref.TASKER_SET, varxref.BUILTIN)
        label = f"{name}  (ALL {count} instances: {totals[name]} uses in total)"
        choices.append((name, EVERY_INSTANCE, label, totals[name], pointless))

    choices.sort(
        key=lambda entry: (
            entry[4],  # the ones renaming cannot help, last
            -totals[entry[0]],  # busiest NAME first, so a name's entries stay together
            entry[0],
            entry[1] is not EVERY_INSTANCE,  # "all of them" leads its own group
            -entry[3],
        ),
    )
    return [(name, owner, label) for name, owner, label, _, _ in choices]


# ##################################################################################
# Variable for variable.
#
# Textual, and therefore easy to get 95% right and hard to get right.  Four things
# below are each individually capable of quietly corrupting a configuration, and each
# is handled here rather than left to the user to notice.
# ##################################################################################

# 1. BOUNDARY.  '%Time' must not match inside '%TimeStamp', and str.replace does exactly
#    that.  varxref.VARIABLE_PATTERN already knows what a name is; this anchors on the
#    whole name and refuses a partial.  The trailing lookahead is the entire point.
# Passed as `owner` to mean "every instance of this name", as against one particular
# instance.  None rather than "" because "" is already a real owner -- varxref keys
# everything that is not a Task's local under it -- so the two must not be the same value.
EVERY_INSTANCE = None


def _rename_pattern(old_name: str) -> re.Pattern:
    """A pattern matching this name and nothing that merely starts with it.

    Also matches the subscripted and member forms, which are the same variable:
    '%Row(3)', '%Row(%i)' and '%Row.length' all name %Row and all keep their suffix.
    """
    return re.compile(rf"%{re.escape(old_name.lstrip('%'))}(?![A-Za-z0-9_])")


# 2. SCOPE.  Tasker scopes a variable by its SPELLING: all lower case is local to the
#    running Task, anything with a capital is global.  Two consequences, and the second
#    one is the one that bites:
#
#      A local is one variable PER TASK.  varxref keys them (name, owner) for this
#      reason and its own note counts 525 of 1523 local names appearing in more than one
#      Task in a real backup.  Renaming '%i' file-wide would rewrite a few hundred
#      unrelated loop counters.  So a rename of a local takes the OWNER as well as the
#      name and never leaves that Task.
#
#      Changing the case CHANGES THE SCOPE.  '%counter' -> '%Counter' is not a rename,
#      it is a promotion from local to global, and it silently makes every Task that
#      used its own %counter share one.  Detected and warned about explicitly; not
#      blocked, because promoting a local to a global on purpose is a real thing to want.
#
# 3. COLLISION.  If the new name is already in use, this is a MERGE, not a rename: two
#    variables become one, and everything that read the old one now reads whatever the
#    other one happens to hold.  Warned about with the existing name's own set/read
#    counts, so 'and %Count is already set in 4 places and read in 19' is on screen
#    before the button is pressed.
#
# 4. WHAT IS NOT REWRITABLE.  varxref.indirect_references counts the actions that build
#    their target name at run time ('Variable Set %(%which)').  Any of them could be
#    touching this variable and none of them can be rewritten.  They become Skips with
#    BLOCKED_INDIRECT, listed with their Targets so the user can go and read them.


def _rename_scope_phrase(index: varxref.VariableIndex, owner: str | None, entries: list) -> str:
    """What the plan's title says about where the rename applies: " (3 instances)", " in Task X", or nothing."""
    scope_phrase = ""
    if owner is EVERY_INSTANCE and len(entries) > 1:
        scope_phrase = f" ({len(entries)} instances)"
    elif owner:
        location = index.scope_locations.get(owner)
        scope_phrase = f" in {location.label}" if location else f" in Task {owner}"
    return scope_phrase


def _scope_limit_warning(displaying: Scope, old_name: str, new_name: str) -> str:
    """The warning for a rename made while the app is displaying only part of the configuration."""
    return (
        f"Limited to {displaying.phrase}, which is what the app is displaying.  Uses of {old_name} "
        f"anywhere else keep the old name -- which for a GLOBAL means the two halves stop agreeing.  "
        f"Nor can {new_name} be checked for a clash outside this scope.  "
        f"Clear the single-item selection to rename across the whole configuration."
    )


def _plan_rename_sites(plan: Plan, entries: list, old_name: str, pattern: re.Pattern, new_name: str) -> None:
    """Add to the plan a change for every field the rename would rewrite, and a skip for every one it cannot.

    `entries` are the cross-reference entries being renamed (see _entries_to_rename).
    """
    seen: set[tuple[int, tuple]] = set()

    # sets before reads, and both in scan order, so the preview reads down the file the
    # way the Map does.  Deduplicated on (element, path) because one field can be recorded
    # twice over: an in-place action records its target as a set AND a read, and a field
    # naming the variable more than once is one field to rewrite either way.
    for reference in [ref for entry in entries for ref in entry.sets + entry.reads]:
        if reference.element is None:
            plan.skips.append(
                Skip(
                    where=reference.target,
                    reason=BLOCKED_INDIRECT,
                    explanation=(
                        f"{reference.detail} -- this action produces {old_name} without naming it anywhere, "
                        f"so there is nothing here to rewrite."
                    ),
                ),
            )
            continue

        if is_plugin_declaration(reference.element):
            plan.skips.append(
                Skip(
                    where=reference.target,
                    reason=BLOCKED_INDIRECT,
                    explanation=(
                        "this is the plugin's own declaration of the variables it produces, not a use of "
                        f"{old_name} -- renaming it here would not change what the plugin sets."
                    ),
                ),
            )
            continue

        key = (id(reference.element), reference.path)
        if key in seen:
            continue
        seen.add(key)

        site = Site(
            kind=site_kind(reference),
            element=reference.element,
            where=reference.target,
            detail=reference.detail,
            path=reference.path,
            rename=(pattern, new_name),
        )
        before, after = rewrite_site(site, pattern, new_name)
        if before == after:
            continue  # The name is in this field's record but not in this particular value.
        plan.changes.append(Change(site=site, before=before, after=after))


def plan_variable_rename(
    index: varxref.VariableIndex,
    old_name: str,
    owner: str | None,
    new_name: str,
    state: RunState,
) -> Plan:
    """Every place this variable is set or read, and what renaming it would do.

    (old_name, owner) is varxref's own key: owner is the Task id for a local, "" for a
    global.  Naming the instance is what makes the local case safe by default -- %i is a
    different variable in each of the 59 Tasks that use it, and a rename that took only a
    name would rewrite all 59 the first time somebody meant one.

    Pass EVERY_INSTANCE as the owner to mean exactly that, on purpose: every instance of
    the name in scope, however many Tasks they belong to.  "Rename the loop counter
    throughout" is a real thing to want and the only way to say it -- but it is spelled
    differently from the safe case rather than reachable by leaving an argument out.

    Sites come from index.variables[(old_name, owner)].sets + .reads, which is one list
    of every place the cross-reference already knows about: Task arguments, plugin
    Bundles, action and Profile conditions, Legacy and Version 2 Scene bindings, and the
    top-level <Variable> declaration.  That last one is why a rename cannot be done by
    walking Tasks alone: leaving the declaration behind orphans the value in Tasker's
    Variables tab.

    Refuses outright, rather than warning:
      - a new name that is not a legal Tasker name (VARIABLE_PATTERN must match the whole)
      - a built-in (%BATT, %TIME) as either side; Tasker owns those
      - a name of one or two characters, either side.  varxref holds these out of its own
        totals as low-confidence for good reason: '%d' matches a strftime format inside a
        Parse/Format DateTime and a printf escape inside a Run Shell, and a rename that
        rewrote those would break a Task in a way no reading of the Map would reveal.

    Warns, and proceeds:
      - the scope change of item 2 above
      - the merge of item 3
      - a Tasker-set name (%par1, %err): renaming the reference does not rename what
        Tasker sets, so the new name is simply never populated.
    """
    old_name = f"%{old_name.lstrip('%')}"
    new_name = f"%{new_name.lstrip('%')}"

    entries = _entries_to_rename(index, old_name, owner)

    scope_phrase = _rename_scope_phrase(index, owner, entries)
    plan = Plan(what=f"Rename {old_name} to {new_name}{scope_phrase}")

    # Worth more here than on a swap.  A rename that stops at the scope's edge leaves the
    # configuration half-renamed -- the places inside still read the new name, the places
    # outside still read the old one -- and unlike a swap, that is a broken configuration
    # rather than a partly-done job.  So it is said as a warning, not just in the title.
    displaying = current_scope(state=state)
    if not displaying.is_everything:
        plan.warnings.append(_scope_limit_warning(displaying, old_name, new_name))

    refusal = _rename_refusal(old_name, new_name)
    if refusal:
        plan.warnings.append(refusal)
        return plan

    if not entries:
        # "in this configuration" would be a lie under a scope -- the variable may be used
        # in a hundred places the scan was told not to look at.
        where = displaying.phrase if not displaying.is_everything else "this configuration"
        plan.warnings.append(f"{old_name} is not used anywhere in {where}.")
        return plan

    plan.warnings.extend(_rename_warnings(index, entries, old_name, new_name, owner))

    pattern = _rename_pattern(old_name)
    _plan_rename_sites(plan, entries, old_name, pattern, new_name)

    declaration = declaration_site(old_name, entries, (pattern, new_name), state=state)
    if declaration is not None:
        before, after = rewrite_site(declaration, pattern, new_name)
        if before != after:
            plan.changes.append(Change(site=declaration, before=before, after=after))

    if index.indirect_references:
        plan.warnings.append(
            f"{index.indirect_references} actions in this configuration build the name of the variable they "
            f"set at run time ('Variable Set %(%which)').  Any of them could be setting {old_name}, and none "
            f"of them can be rewritten -- check them by hand.",
        )

    plan.selected = set(range(len(plan.changes)))
    return plan


def _entries_to_rename(
    index: varxref.VariableIndex,
    old_name: str,
    owner: str | None,
) -> list[varxref.Variable]:
    """The variable record(s) this rename covers -- one instance, or every one of the name.

    Ordered as varxref found them, so a plan over several instances still reads down the
    file the way the Map does rather than jumping between Tasks.
    """
    if owner is not EVERY_INSTANCE:
        entry = index.variables.get((old_name, owner))
        return [entry] if entry is not None else []
    return [entry for (name, _owner), entry in index.variables.items() if name == old_name]


def _rename_refusal(old_name: str, new_name: str) -> str:
    """Why this rename must not be attempted at all, or "" if it may be.

    Refusals rather than warnings, because each of these produces a configuration that is
    wrong in a way no reading of the Map would reveal.
    """
    if not VARIABLE_PATTERN.fullmatch(new_name):
        return (
            f"'{new_name}' is not a name Tasker would accept.  A variable name begins with a letter and "
            f"continues with letters, digits and underscores."
        )

    # globalvr's list carries the leading '%', so these are compared whole.  Getting that
    # wrong is silent: every built-in passes the test and %BATT becomes renameable.
    for name, side in ((old_name, "renamed"), (new_name, "renamed to")):
        if name in tasker_global_variables:
            return f"{name} is one of Tasker's own built-in variables and cannot be {side}."
        if len(name) - 1 <= _LOW_CONFIDENCE_LENGTH:
            # varxref holds these out of its own totals for the same reason.
            return (
                f"{name} is too short to rename safely.  A name this short collides with things that are not "
                f"variables at all -- a strftime letter in a Parse/Format DateTime, a printf escape in a Run "
                f"Shell, a '%' wildcard in a SQL Query -- and rewriting one of those would break a Task in a "
                f"way nothing in the Map would show."
            )

    if old_name == new_name:
        return "The old and new names are the same."
    return ""


def _rename_warnings(
    index: varxref.VariableIndex,
    entries: list[varxref.Variable],
    old_name: str,
    new_name: str,
    owner: str | None,
) -> list[str]:
    """What the user should read before pressing Replace.  Each of these proceeds."""
    warnings = []

    # Renaming every instance of a LOCAL is the case that needs saying out loud.  Each of
    # those instances is a separate variable -- Tasker scopes a lower-case name to the
    # running Task -- so this is not one rename but as many as there are Tasks, and the
    # count is the only thing on screen that says how far it reaches.
    locals_covered = [entry for entry in entries if entry.scope == varxref.LOCAL]
    if owner is EVERY_INSTANCE and len(locals_covered) > 1:
        where = ", ".join(
            (index.scope_locations[entry.owner].label if entry.owner in index.scope_locations else entry.owner)
            for entry in locals_covered[:3]
        )
        warnings.append(
            f"{old_name} is a LOCAL, so these are {len(locals_covered)} separate variables, one per Task "
            f"({where}{', ...' if len(locals_covered) > 3 else ''}).  Every one of them is renamed.",
        )

    # A scope change.  Tasker scopes by SPELLING, so this is not cosmetic: '%counter' ->
    # '%Counter' promotes a variable that was private to each Task into one global that
    # every Task then shares.  A real thing to want, and never a thing to do by accident.
    was, becomes = varxref.scope_of(old_name), varxref.scope_of(new_name)
    if was != becomes:
        warnings.append(
            f"This changes the variable's SCOPE, not just its name: {old_name} is {was} and {new_name} would "
            f"be {becomes}.  Tasker decides scope from the spelling -- all lower case is local to the running "
            f"Task, anything with a capital is global.",
        )

    # The target already exists.  Said plainly rather than as an alarm: picking an
    # existing variable is a supported thing to do -- "everywhere this Task says
    # %app_name, say %app_package" consolidates two variables into one, and the target
    # pulldown offers exactly these.  What the user still has to be told is the
    # consequence, because it is not what the word "rename" suggests.
    # Looked up per instance when every instance is in play: a local's target is keyed to
    # the same Task, so "does %tally already exist" has a different answer in each of them
    # and the first one that says yes is worth reporting.
    if becomes == varxref.LOCAL:
        owners = [entry.owner for entry in entries] if owner is EVERY_INSTANCE else [owner]
        existing = next(
            (found for key in owners if (found := index.variables.get((new_name, key))) is not None),
            None,
        )
    else:
        existing = index.variables.get((new_name, ""))
    if existing is not None:
        warnings.append(
            f"{new_name} already exists -- set in {len(existing.sets)} places and read in "
            f"{len(existing.reads)}.  This MERGES the two rather than renaming one: afterwards there is a "
            f"single variable, and everything that read {old_name} reads whatever {new_name} holds.",
        )

    # Something produces it that this rename cannot reach.
    producers = {reference.detail for entry in entries for reference in entry.sets if reference.element is None}
    if producers:
        warnings.append(
            f"{old_name} is produced by an action that never names it ({', '.join(sorted(producers)[:3])}).  "
            f"That action will go on producing {old_name}, so after this rename nothing will set {new_name}.",
        )

    # Tasker-set (%par1, %err) and the built-in SHAPE both mean "something outside this
    # file puts the value there".  The documented built-ins are refused outright; this
    # catches the ones varxref recognises by shape alone -- globalvr's list was transcribed
    # from a page that predates %HUMIDITY, %SDK and the %DEV*/%CAL* families -- where a
    # refusal would be wrong, since the same shape covers somebody's own SHOUTING global.
    outside_scopes = {entry.scope for entry in entries} & {varxref.TASKER_SET, varxref.BUILTIN}
    if outside_scopes:
        source = "Tasker itself as a Task runs" if varxref.TASKER_SET in outside_scopes else "Tasker, by the look of it"
        warnings.append(
            f"{old_name} is set by {source}.  Renaming the places that read it does not change what sets it, "
            f"so {new_name} would never hold anything.  Ignore this if {old_name} is your own variable.",
        )

    return warnings
