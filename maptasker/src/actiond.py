#! /usr/bin/env python3
"""Action dictionary functions."""

#                                                                                      #
# actiond: Task Action dictionary functions for MapTasker                              #
#                                                                                      #
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import maptasker.src.action as get_action
from maptasker.src.actionc import action_codes
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    import defusedxml.ElementTree

IGNORE_ITEMS = ["code", "label", "se", "on", "ListElementItem", "pri", "pin"]


# Given a child xml element, determine if it is a boolean of condtion
# add return if in a list
def get_boolean_or_condition(
    child: defusedxml.ElementTree,
    condition_list: list,
    boolean_list: list,
) -> tuple[list, list]:
    """
    Evaluates the condition/boolean and updates the condition_list and boolean_list.

    Args:
        child (Element): The XML element to evaluate.
        condition_list (list): The list of conditions.
        boolean_list (list): The list of booleans.

    Returns:
        tuple: A tuple containing the updated condition_list and boolean_list.
    """

    if "bool" in child.tag:
        boolean_list.append(child.text.upper())
    elif child.tag == "Condition":
        (
            first_string,
            the_operation,
            second_string,
        ) = get_action.evaluate_condition(child)
        condition_list.append([first_string, the_operation, second_string])
    return condition_list, boolean_list


# Trundle through ConditionList "If" conditions
# Return the list of conditions and list of associated booleans
def process_condition_list(
    code_action: defusedxml.ElementTree,
) -> tuple[list[list[Any]], list[str]]:
    """
    Extracts conditions and their associated booleans from the <ConditionList> element.

    Args:
        code_action (ElementTree): XML element containing conditions.

    Returns:
        tuple[list[list[Any]], list[str]]: List of conditions and their associated booleans.
    """
    condition_list_str = code_action.find("ConditionList")
    if condition_list_str is None:
        return [], []

    condition_list, boolean_list = [], []
    for child in condition_list_str:
        condition_list, boolean_list = get_boolean_or_condition(child, condition_list, boolean_list)

    return condition_list, boolean_list


# Update the dictionary for the Action code
#  This is only called if the action code is already in our master
#  dictionary of codes.
def update_action_codes(
    action: defusedxml.ElementTree,
    the_action_code_plus: defusedxml.ElementTree,
) -> defusedxml.ElementTree:
    """
    Update the dictionary for the Action code
        :param action: <Action> xml element
        :param the_action_code_plus: the Action code with "action type"
                (e.g. 861t, t=Task, e=Event, s=State)
        :return: nothing
    """
    # Update dictionary entry for this code in the format of an output line
    # dict = { 'the_code':
    #               {num_args: num,
    #                args: arg0, arg1, ... type: Int/Str  }
    arg_list, type_list, arg_nums = get_action.get_args(action, IGNORE_ITEMS)
    arg_count = len(arg_list)

    # Compare this Actions num of args to dictionary's
    if arg_count > action_codes[the_action_code_plus].numargs:
        with contextlib.suppress(Exception):
            action_codes[the_action_code_plus].numargs = arg_count
            action_codes[the_action_code_plus].args = arg_nums
            action_codes[the_action_code_plus].types = type_list

        logger.debug(
            "update_action_codes:"
            f" {the_action_code_plus} {action_codes[the_action_code_plus]!s} numargs of {action_codes[the_action_code_plus].numargs} update to {arg_count}:  needs to be updated in actionc.py!",
        )
    return


# Build the dictionary for the Action code.  Only called if the action code is not
#   in our master dictionary of codes.
def build_new_action_codes(
    action: defusedxml.ElementTree,
    the_action_code_plus: defusedxml.ElementTree,
) -> defusedxml.ElementTree:
    """
    Build the dictionary for the Action code
        :param action: <Action> xml element
        :param the_action_code_plus: the Action code with "action type" (e.g. 861t, t=Task, e=Event, s=State)
        :return: nothing
    """
    logger.info(f"...for {the_action_code_plus}")

    # Create a dictionary entry for this code in the format of an output line
    # dict = { 'the_code':
    #               {num_args: num, args: ['arg0', 'arg1', ...], types: ['Str', 'Int', ...]
    arg_list, type_list, arg_nums = get_action.get_args(action, IGNORE_ITEMS)
    arg_count = len(arg_list)
    with contextlib.suppress(Exception):
        action_codes[the_action_code_plus].numargs = arg_count
        action_codes[the_action_code_plus].args = arg_nums
        action_codes[the_action_code_plus].types = type_list
    return


# Build the dictionary for each Action code
#  This is only called if the action code is not already in our master dictionary of codes
# child = pointer to <code> xml
# action = pointer to root xml (<Action> or <Profile>)
# adder = empty if <action>.  Else it is a Profile condition, and we need to make key unique
def build_action_codes(
    action: defusedxml.ElementTree,
    child: defusedxml.ElementTree,
) -> defusedxml.ElementTree:
    """
    Build the dictionary for each Action code
    We first check if the_action_code_plus is already in action_codes.
    If it is, we call the update_action_codes() function. Otherwise, we call the
    build_new_action_codes() function followed by some logging and debugging output
    (if debug mode is enabled) as before.

        :param action: xml element with Task action's "<code>nnn</code>"
        :param child: xml root element of Task action
        :return:
    """
    #  Get the actual dictionary/action code
    the_action_code_plus = child.text
    if the_action_code_plus in action_codes:
        update_action_codes(action, the_action_code_plus)
    else:
        build_new_action_codes(action, the_action_code_plus)

    return
