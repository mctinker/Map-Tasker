"""mapscope: the fix for a variable whose spelling breaks Tasker's case rule, as a plan with a preview and one Undo."""

#! /usr/bin/env python3

#                                                                                        #
# mapscope: turn what scopecheck found into a change.                                      #
#                                                                                        #
# scopecheck reads the configuration and says "%aab_animsteps is a lower case LOCAL, and    #
# the file has a global %AAB_AnimSteps".  This is the other half: the Plan that makes the   #
# spelling say what the variable is, written by the machinery that already renames a        #
# variable everywhere -- every action argument, condition, Scene binding, plugin setting      #
# and the Variables tab entry -- with maprefac_variable's blocks and warnings, and applied    #
# by maprefac.apply as ONE Undo.                                                            #
#                                                                                        #
# Nothing here is new machinery, and that is the point.  Two kinds of fix, and both are       #
# maprefac_variable's own:                                                                  #
#                                                                                        #
#   Make it global   (TO_GLOBAL)  a local becomes the global spelling -- one Task's local, or   #
#                    every Task's local of that name -- and when that spelling is a global     #
#                    that already exists the two MERGE, which the plan says in its first        #
#                    warning, because "rename" must never silently mean "merge".                #
#   Rename           (RENAME)     a global keeps its scope and takes the spelling that says so,   #
#                    which is the fix for a name in the Variables tab with no capital in it.     #
#                                                                                        #
# The new name is the finding's suggestion unless the person types another, and whether it      #
# merges is decided from the name actually used, not from the finding: typing a name nothing     #
# has is a rename, typing one something has is a merge, and a name that would not change the      #
# scope is a block that says so.                                                                   #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src.analysis import scopecheck
from maptasker.src.mapgen import varxref
from maptasker.src.mapops import maprefac_variable
from maptasker.src.mapops.maprefac_model import VARIABLE, Block, Plan, blocked

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

# What each kind of finding is fixed with.
_OPERATION = {
    scopecheck.CASE_MISMATCH: maprefac_variable.TO_GLOBAL,
    scopecheck.DECLARED_LOWERCASE: maprefac_variable.RENAME,
    scopecheck.LOCAL_NEVER_SET: maprefac_variable.TO_GLOBAL,
}


def fix_name(issue: scopecheck.ScopeIssue) -> str:
    """What the fix would be called: "Make %aab_animsteps global as %AAB_AnimSteps"."""
    operation = _OPERATION[issue.kind]
    verb = "Rename" if operation == maprefac_variable.RENAME else "Make global"
    return f"{verb} {issue.name}"


def plan_fix(
    issue: scopecheck.ScopeIssue,
    state: RunState,
    new_name: str = "",
    index: varxref.VariableIndex | None = None,
) -> Plan:
    """What fixing this finding would do, or why it cannot be done.

    `new_name` is the spelling to use; empty means the finding's own suggestion.  A finding with no suggestion --
    two globals fold to the same letters, so which was meant is not for this to say -- needs one given.
    """
    chosen = new_name.strip() or issue.suggestion
    if not chosen:
        return blocked(
            VARIABLE,
            fix_name(issue),
            Block(
                "NO-SUGGESTION",
                f"The file has more than one global spelled with the letters of {issue.name}, so which one it was meant "
                "to be is not something this can guess.  Type the spelling you want and preview that.",
            ),
        )

    index = index if index is not None else varxref.build_index(state=state)
    chosen = maprefac_variable.percent(chosen)
    merge = (chosen, "") in index.variables and chosen != issue.name
    return maprefac_variable.plan_variable(
        _OPERATION[issue.kind], issue.name, issue.owner, chosen, state, index, merge=merge
    )
