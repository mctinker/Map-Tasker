#! /usr/bin/env python3
"""Task "Action" and Profile "condition" dictionary"""

#                                                                                      #
# actionc: Task "Action" and Profile "condition" dictionary                            #
#                                                                                      #
#  Provide the master lookup for a given <code>nnn</code> xml statement                #
#                                                                                      #
#  The table is built at import time from two files, not written out by hand:          #
#                                                                                      #
#   assets/json/task_all_actions.json  Tasker's own published table, vendored as-is.   #
#      It defines 418 Task actions: name, category, canFail, and each argument's id,   #
#      name, type and mandatory-ness.  Never edit it; replace it wholesale when a new  #
#      Tasker release publishes a new one.                                             #
#                                                                                      #
#   assets/json/action_overlay.json  everything that file does not carry -- arg_eval   #
#      for the published codes, plus the 325 entries Tasker does not publish at all    #
#      (Events, States, plugin actions and Scene element types) with their arguments   #
#      and redirects.  This is the file to edit, and the one bldargs.py adds to.       #
#                                                                                      #
#  Level 1 key = the code (nnn, above) or screen element type                          #
#       If a code, the last character is 't' for task, 'e' for event, 's' for state    #
#   redirect subkey = another key to borrow this entry's arguments from - optional      #
#   args subkey = the arguments, in arg_id order                                       #
#   name subkey = the name to output - required                                        #
#   category subkey = Tasker's action category code - optional                          #
#   canfail subkey = whether Tasker lets the action fail - optional                     #
#                                                                                      #
#   Within an argument, arg_eval is the formula for evaluation - optional              #
#      'some_string:' for str or int xml values                                        #
#      ["e", ", name"] ...evaluate value to determine if it is 'selected'.             #
#                                                                                      #
#      ['some_string:', 'l', 'lookup-code] for actiont dictionary lookup for specific  #
#       code.                                                                          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from __future__ import annotations

import json
import os
from collections import namedtuple

# Define the namedtuples
ActionCode = namedtuple(  # noqa: PYI024
    "ActionCode",
    ["redirect", "args", "name", "category", "canfail"],
)
ArgumentCode = namedtuple(  # noqa: PYI024
    "ArgumentCode",
    ["arg_id", "arg_required", "arg_name", "arg_type", "arg_eval"],
)

# Resolved off this file rather than the working directory: proginit chdir's into the
# assets directory during start-up and several callers import this module from a test
# run rooted somewhere else again.
_JSON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "json")

PUBLISHED_ACTIONS_FILE = os.path.join(_JSON_DIR, "task_all_actions.json")
OVERLAY_FILE = os.path.join(_JSON_DIR, "action_overlay.json")


def _read(path: str) -> dict | list:
    """Load one of the two table files.

    Args:
        path (str): file to read.
    Returns:
        dict | list: its parsed contents.
    """
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as error:  # A missing table is fatal: every lookup returns
        message = f"actionc: {path} is missing.  MapTasker cannot map anything without it."
        raise RuntimeError(message) from error  # 'not mapped', which would look like data.
    except json.JSONDecodeError as error:
        message = f"actionc: {path} is not valid JSON ({error})."
        raise RuntimeError(message) from error


def _published_entry(action: dict, arg_evals: dict) -> ActionCode:
    """One ActionCode out of a task_all_actions.json entry.

    Arguments are ordered by arg_id, which is what the table has always used and what
    actargs indexes by.  The file's own order and its sortOrder field both disagree with
    it for three codes, so neither can stand in.

    Args:
        action (dict): one entry of task_all_actions.json.
        arg_evals (dict): {arg id: arg_eval} for this code, from the overlay's 'eval'.
    Returns:
        ActionCode: the assembled entry.
    """
    return ActionCode(
        redirect="",  # No published code redirects; all 133 redirects live in the overlay.
        args=[
            ArgumentCode(
                arg_id=str(arg["id"]),
                arg_required=bool(arg["isMandatory"]),
                arg_name=arg["name"],
                arg_type=str(arg["type"]),
                arg_eval=arg_evals.get(str(arg["id"]), ""),
            )
            for arg in sorted(action["args"], key=lambda arg: int(arg["id"]))
        ],
        name=action["name"],
        category=str(action["categoryCode"]),
        canfail=str(action.get("canFail", False)),
    )


def _overlay_entry(entry: dict) -> ActionCode:
    """One ActionCode out of an action_overlay.json 'extra' entry.

    Args:
        entry (dict): the overlay's record for one code.
    Returns:
        ActionCode: the assembled entry.
    """
    return ActionCode(
        redirect=entry.get("redirect", ""),
        args=[ArgumentCode(*arg) for arg in entry.get("args", [])],
        name=entry["name"],
        category=entry.get("category", ""),
        canfail=entry.get("canfail", ""),
    )


def build_action_codes() -> dict:
    """The master action/condition table, assembled from the two json files.

    Sorted at the end because callers iterate this table to build user-facing pickers
    and then sort only on the action's display name -- 29 names are shared by more than
    one code -- so iteration order decides how those ties break and reaches the screen.

    Args:
        None
    Returns:
        dict: {code key: ActionCode}, in sorted key order.
    """
    overlay = _read(OVERLAY_FILE)
    arg_evals = overlay["eval"]

    codes = {}
    for action in _read(PUBLISHED_ACTIONS_FILE):
        key = f"{action['code']}t"
        codes[key] = _published_entry(action, arg_evals.get(key, {}))

    # Applied second so an 'extra' entry can override a published code outright, which
    # is how a published code would be given a redirect if one ever needed it.
    for key, entry in overlay["extra"].items():
        codes[key] = _overlay_entry(entry)

    return dict(sorted(codes.items()))


action_codes = build_action_codes()
