#! /usr/bin/env python3
"""Action dictionary functions."""

#                                                                                      #
# actiond: Task Action dictionary functions for MapTasker                              #
#                                                                                      #
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import maptasker.src.action as get_action

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
        condition_list, boolean_list = get_boolean_or_condition(
            child,
            condition_list,
            boolean_list,
        )

    return condition_list, boolean_list
