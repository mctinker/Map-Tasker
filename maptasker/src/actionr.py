#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# actionr: process Task "Action" and return the result                                 #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
# #################################################################################### #
import contextlib
import re
from collections import defaultdict

import defusedxml.ElementTree

import maptasker.src.action as get_action
from maptasker.src.actargs import action_args
from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    logger,
    pattern0,
    pattern1,
    pattern2,
    pattern3,
    pattern4,
)
from maptasker.src.xmldata import (
    get_xml_int_argument_to_value,
    get_xml_str_argument_to_value,
)


# ##################################################################################
# Given a list of positional items, return a string in the correct order based
# on position
# ##################################################################################
def get_results_in_arg_order(evaluated_results: dict) -> str:
    """
    Given a list of positional items, return a string in the correct order based
    on position.
        :param evaluated_results: dictionary of the argument <argn> evaluated results
        :return: all the evaluated results for Action
    """
    return_result = ""
    for arg in evaluated_results["position_arg_type"]:
        the_item = ""
        match arg:
            case "Str":
                if evaluated_results["result_str"]:
                    the_item = evaluated_results["result_str"][0]  # Grab the result
                    evaluated_results["result_str"].pop(
                        0
                    )  # Delete from list so we don't re-grab it.
            case "Int":
                if evaluated_results["result_int"]:
                    the_item = evaluated_results["result_int"][0]
                    evaluated_results["result_int"].pop(0)
            case "App":
                if evaluated_results["result_app"]:
                    the_item = evaluated_results["result_app"][0]
                    evaluated_results["result_app"].pop(0)
            case "ConditionList":
                if evaluated_results["result_con"]:
                    the_item = evaluated_results["result_con"][0]
                    evaluated_results["result_con"].pop(0)
            case "Img":
                if evaluated_results["result_img"]:
                    the_item = evaluated_results["result_img"][0]
                    evaluated_results["result_img"].pop(0)
            case "Bundle":  # Plugin bundle
                if evaluated_results["result_bun"]:
                    the_item = evaluated_results["result_bun"][0]
                    evaluated_results["result_bun"].pop(0)
            case _:
                error_msg = (
                    "Function get_results_in_arg_order mapped error: no match for"
                    f' "arg":{arg}'
                )
                logger.debug(error_msg)
                the_item = error_msg
        # Eliminate empty values
        if the_item == ", ":
            continue
        return_result = f"{return_result} {the_item}"  # Get the appropriate item
    return return_result


# ##################################################################################
# For the given code, save the display_name, required arg list and associated
# type list in dictionary
# Then evaluate the data against the master dictionary of actions
# ##################################################################################
def evaluate_action_args(
    the_action_code_plus: defusedxml.ElementTree.XML,
    arg_list: list,
    code_action: defusedxml.ElementTree.XML,
    action_type: bool,
    lookup_code_entry: dict,
    evaluate_list: list,
    evaluated_results: dict,
) -> object:
    """
    For the given code, save the display_name, required arg list and associated type
    list in dictionary. Then evaluate the data against the master dictionary of actions.

        :param the_action_code_plus: the code found in <code> for the Action (<Action>)
            plus the type (e.g. "861t", where "t" = Task, "s" = State, "e" = Event)
        :param arg_list: list of arguments (<argn>) under Action
        :param code_action: Action code found in <code>
        :param action_type: True if this is for a Task, False if for a Condition
        :param lookup_code_entry: The key to our Action code dictionary in actionc.py
        :param evaluate_list: list of arguments to evaluate
        :param evaluated_results: a list into which to put the evaluated results
        :return: the evaluated results as a list
    """
    # Process the Task action arguments
    evaluated_results = action_args(
        arg_list,
        the_action_code_plus,
        lookup_code_entry,
        evaluate_list,
        code_action,
        action_type,
        evaluated_results,
    )

    # If we had at least one Int or Str then deal with them

    # If TypeError, then we haven't properly mapped the action code in actionc.py.
    #   evaluated_results["error"] will have been filled with an error msg by actarg.py
    #   ...just return with error msg
    # Otherwise, get the results by evaluating and formatting the str arguments and
    # int arguments from xml
    with contextlib.suppress(TypeError):
        if evaluated_results["get_xml_flag"]:
            if evaluated_results["strargs"]:
                evaluated_results["result_str"] = get_xml_str_argument_to_value(
                    code_action,
                    evaluated_results["strargs"],
                    evaluated_results["streval"],
                )
            if evaluated_results["intargs"]:
                evaluated_results["result_int"] = get_xml_int_argument_to_value(
                    code_action,
                    evaluated_results["intargs"],
                    evaluated_results["inteval"],
                )

    return evaluated_results


# ##################################################################################
# Search for and return all substrings in a string that begin with a percent sign and
# have at least one capitalized letter in the substring.
# ##################################################################################
def find_capitalized_percent_substrings(string):
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
    # regex = r"%.*[A-Z]+"
    # regex = r".*[A-Z].*"
    regex = r".*[A-Z].*"

    # Find all words that begin with a percent sign (%).
    percent_list = re.findall("[%]\w+", string)

    return [word for word in percent_list if re.match(regex, word)]


# ##################################################################################
# Get the variables from this result and save them in the dictionary.
# ##################################################################################
def get_variables(result: str) -> None:
    """
    Get the variables from this result and save them in the dictionary.
        Args:

            result (str): The text string containing the Task variable(s)
    """

    # Fid all variables with at least one capitalized letter.
    if variable_list := find_capitalized_percent_substrings(result):
        # Go thru list of capitalized percent substrings and see if they are
        # in our variable dictionary.  If so, then add the project name to the list.
        for variable in variable_list:
            # Validate that this variable is for the Project we are currently doing.
            try:
                if primary_variable := PrimeItems.variables[variable]:
                    if (
                        primary_variable["project"]
                        and PrimeItems.current_project
                        not in primary_variable["project"]
                    ):
                        primary_variable["project"].append(PrimeItems.current_project)
                    elif not primary_variable["project"]:
                        primary_variable["project"] = [PrimeItems.current_project]
            except KeyError:
                # Drop here if variable is not in Tasker's variable list (i.e. the xml)
                PrimeItems.variables[variable] = {
                    "value": "(Inactive)",
                    "project": [PrimeItems.current_project],
                    "verified": False,
                }


# ##################################################################################
# For the given code, save the display_name, required arg list and associated
# type list in dictionary.
# Then evaluate the data against the master dictionary of actions.
# ##################################################################################
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
    result = ""
    our_action_code = lookup_code_entry[the_action_code_plus]

    # Save the associated data, in the event
    # our_action_code.reqargs = arg_list
    # our_action_code.evalargs = evaluate_list
    program_arguments = PrimeItems.program_arguments
    # If just displaying action names or there are no action details, then just
    # display the name
    if arg_list and program_arguments["display_detail_level"] != 2:
        # Evaluate the required args per arg_list
        evaluated_results = evaluate_action_args(
            the_action_code_plus,
            arg_list,
            code_action,
            action_type,
            lookup_code_entry,
            evaluate_list,
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
        result = pattern0.sub(",", result)  # Catch ",,"
        result = f"&nbsp;&nbsp{result}"

        # Process variables if display_detail_level is 4
        if program_arguments["display_detail_level"] == 4:
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
    else:
        return f"{our_action_code.display}{result}{get_action.get_extra_stuff(code_action, action_type)}"
