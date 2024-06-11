"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# actionr: process Task "Action" and return the result                                 #
#                                                                                      #

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

import maptasker.src.action as get_action
from maptasker.src.actargs import action_args
from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    DISPLAY_DETAIL_LEVEL_all_tasks,
    DISPLAY_DETAIL_LEVEL_all_variables,
    pattern0,
    pattern1,
    pattern2,
    pattern3,
    pattern4,
    pattern11,
    pattern12,
)

if TYPE_CHECKING:
    import defusedxml.ElementTree


# Given a list of positional items, return a string in the correct order based
# on position
def get_results_in_arg_order(evaluated_results: dict) -> str:
    """
    Get all of the evaluated results into a single list and return results as a string.
    :param evaluated_results: a dictionary containing evaluated results
    :type evaluated_results: dict
    :return: a string containing the evaluated results in order
    :rtype: str
    """

    # Get all of the evaluated results into a single list
    result_parts = []
    for arg in evaluated_results["required_args"]:
        value = evaluated_results[f"arg{arg}"]["value"]
        if value is not None:
            result_parts.append(value)
        # Eliminate empty values
        if result_parts and result_parts[-1] == ", ":
            result_parts.pop()
            continue

    # Return results as a string
    if result_parts:
        return " ".join(result_parts)

    return ""


# Search for and return all substrings in a string that begin with a percent sign and
# have at least one capitalized letter in the substring.
def find_capitalized_percent_substrings(string: str) -> list:
    """
    Searches for and returns all of the occurrences of substrings that begin with a
        percent sign and have at least one capitalized letter in the substring.

    Args:
        string: A string to search.

    Returns:
        A list of all of the occurrences of substrings that begin with a percent sign and
        have at least one capitalized letter in the substring.
    """

    # Create a regular expression to match substrings that begin with a percent sign
    # and have at least one capitalized letter.
    # regex = r".*[A-Z].*"   <<< re.compile(regex) in sysconst.py as pattern11

    # Find all words that begin with a percent sign (%).
    # percent_list = re.findall("[%]\w+", string)  << pattern12 in sysconst.py

    # Create a regular expression to match substrings that begin with a percent sign.
    return [word for word in pattern12.findall(string) if re.match(pattern11, word)]


# Get the variables from this result and save them in the dictionary.
def get_variables(result: str) -> None:
    # Fid all variables with at least one capitalized letter.
    """Get all variables with at least one capitalized letter.
    Parameters:
        - result (str): The string to search for variables.
    Returns:
        - None: This function does not return anything.
    Processing Logic:
        - Find all variables with at least one capitalized letter.
        - Check if the variable is in the variable dictionary.
        - If it is, add the current project name to the list of projects associated with the variable.
        - If it is not, add the variable to the variable dictionary with a default value and the current project name.
        - If the variable is not found in the dictionary, it is considered inactive."""
    if variable_list := find_capitalized_percent_substrings(result):
        # Go thru list of capitalized percent substrings and see if they are
        # in our variable dictionary.  If so, then add the project name to the list.
        for variable in variable_list:
            # Validate that this variable is for the Project we are currently doing.
            try:
                if primary_variable := PrimeItems.variables[variable]:
                    if primary_variable["project"] and PrimeItems.current_project not in primary_variable["project"]:
                        primary_variable["project"].append(PrimeItems.current_project)
                    elif not primary_variable["project"]:
                        primary_variable["project"] = [PrimeItems.current_project]
            except KeyError:  # noqa: PERF203
                # Drop here if variable is not in Tasker's variable list (i.e. the xml)
                PrimeItems.variables[variable] = {
                    "value": "(Inactive)",
                    "project": [PrimeItems.current_project],
                    "verified": False,
                }


# For the given code, save the display_name, required arg list and associated
# type list in dictionary.
# Then evaluate the data against the master dictionary of actions.
def get_action_results(
    the_action_code_plus: str,
    lookup_code_entry: defusedxml.ElementTree.XML,
    code_action: defusedxml.ElementTree.XML,
    action_type: bool,
    arg_list: list[str],
    evaluate_list: list[str],
) -> str:
    """
    For the given code, save the display_name, required arg list and associated type
    list in dictionary.
    Then evaluate the data against the master dictionary of actions
        :param the_action_code_plus: the code found in <code> for the Action (<Action>)
        plus the type (e.g. "861t", where "t" = Task, "s" = State, "e" = Event)
        :param lookup_code_entry: The key to our Action code dictionary in actionc.py
        :param code_action: the <code> xml element
        :param action_type: True if this is for a Task, false if for a Condition
        :param arg_list: list of <argn> statements
        :param evaluate_list: list of argument evaluations
        :return: the output line containing the Action details
    """
    # Setup default dictionary as empty list
    evaluated_results = defaultdict(list)
    evaluated_results["required_args"] = arg_list
    result = ""
    our_action_code = lookup_code_entry[the_action_code_plus]

    program_arguments = PrimeItems.program_arguments
    # If just displaying action names or there are no action details, then just
    # display the name
    if arg_list and program_arguments["display_detail_level"] != DISPLAY_DETAIL_LEVEL_all_tasks:
        # Process the Task action arguments
        evaluated_results = action_args(
            arg_list,
            the_action_code_plus,
            lookup_code_entry,
            evaluate_list,
            code_action,
            evaluated_results,
        )

    # If we have results from evaluation, then go put them in their appropriate order
    if evaluated_results["returning_something"]:
        result = get_results_in_arg_order(evaluated_results)

    elif evaluated_results["error"]:
        result = evaluated_results["error"]

    # Clean up the arguments, if any.  Replace <> so they appear properly
    # Eliminate extra commas
    if result:
        result = pattern3.sub("&lt;", result)  # Replace "<" with "&lt;"
        result = pattern4.sub("&gt;", result)  # Replace ">" with "&gt;"
        result = pattern1.sub(",", result)  # Replace ",  ," with ","
        result = pattern2.sub(",", result)  # Replace " ," with ","
        result = pattern2.sub(",", result)  # Do it again to catch any missed
        result = pattern2.sub(",", result)  # Do it again to catch any missed
        result = pattern0.sub(",", result)  # Catch ",,"
        result = f"&nbsp;&nbsp;{result}"

        # Process variables if display_detail_level is 4
        if program_arguments["display_detail_level"] >= DISPLAY_DETAIL_LEVEL_all_variables:
            get_variables(result)

    # Return the properly formatted HTML (if Task) with the Action name and extra stuff
    if action_type:  # If this is a Task...
        return format_html(
            "action_name_color",
            "",
            our_action_code.display,
            True,
        ) + format_html(
            "action_color",
            "",
            (f"{result}{get_action.get_extra_stuff(code_action, action_type)}"),
            False,
        )

    return f"{our_action_code.display}{result}{get_action.get_extra_stuff(code_action, action_type)}"
