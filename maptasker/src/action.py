"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# action: Find Task's Action arguments (<argn>) and return as sorted list              #
#                                                                                      #

from __future__ import annotations

from typing import TYPE_CHECKING

# TYPE_CHECKING is a special constant that is assumed to be True by 3rd party static type checkers. It is False at runtime.
if TYPE_CHECKING:
    import defusedxml.ElementTree

from maptasker.src.actiont import lookup_values
from maptasker.src.error import error_handler
from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.shelsort import shell_sort
from maptasker.src.sysconst import (
    DISABLED,
    FONT_FAMILY,
    RE_FONT,
    DISPLAY_DETAIL_LEVEL_all_tasks,
)
from maptasker.src.xmldata import remove_html_tags


# Given a Task's Action, find all 'arg(n)' xml elements and return as a sorted list
#  This is only called if the action code is not already in our master dictionary
#   actionc.py
# Input:
#   action: list of actions or parameters
#   ignore_list: xml to ignore (e.g. label, on, etc.
# Output:
#   arg_lst: list of sorted args as numbers only (e.g. 'arg' removed from 'arg0')
#   type_list: list of sorted types (e.g. 'Int', 'Str', etc.)
def get_args(
    action: defusedxml.ElementTree,
    ignore_list: list,
) -> tuple[list, list, list]:
    """
    Given a Task's Action, find all 'arg(n)' xml elements and return as a sorted list
    This is only called if the action code is not already in our master dictionary actionc.py
        :param action: xml element pointing to <actn> Action element
        :param ignore_list: list of strings/elements to ignore (e.g. "label")
        :return: list of arguments, list of argument types, list of argument position (numeric part of <argn>)
    """
    arguments, argument_types, master_list = [], [], []
    arg_nums = 0
    for child in action:
        if child.tag in ignore_list:  # Ignore certain tags
            continue
        action_arg = child.attrib.get("sr")
        if action_arg is not None:
            master_list.append(child)  # Build out list of args
    # If we have args then sort them and convert to string
    if master_list:
        # Sort args by their number (e.g. arg0, arg1, arg2, ...)
        shell_sort(master_list, True, False)
        # Now go through args and build our "type" and "arg" lists
        for child in master_list:
            argument_types.append(child.tag)  # one of: 'Str' 'Int' 'Bundle' 'App'
            arguments.append(child.attrib.get("sr"))
        # Build list of arg position only (numeric part of argn)
        arg_nums = [
            str(ind) for ind, x in enumerate(arguments)
        ]  # Build list of arg position only (numeric part of argn)

    return arguments, argument_types, arg_nums


# Evaluate the If statement and return the operation
def evaluate_condition(child: defusedxml.ElementTree) -> tuple[str, str, str]:
    """
    Evaluate the If statement and return the operation
        :param child: xml head element containing the <lhs xml element to be evaluated
        :return: the evaluated result based on the <lhs elemental number
    """
    the_operations = {
        "0": " = ",
        "1": " NEQ ",
        "2": " ~ ",
        "3": " !~ ",
        "4": " ~R ",
        "5": " !~R ",
        "6": " < ",
        "7": " > ",
        "8": " = ",
        "9": " != ",
        "12": " is set",
        "13": " not set",
    }

    first_string = child.find("lhs").text
    operation = child.find("op").text
    the_operation = the_operations[operation]
    if "set" not in the_operation and child.find("rhs").text is not None:  # No second string if "set/not" set
        second_operation = child.find("rhs").text
        # Correct any embedded html tags in text string.
        second_operation = second_operation.replace("<", "&lt;")
        second_operation = second_operation.replace(">", "&gt;")
    else:
        second_operation = ""

    return first_string, the_operation, second_operation


# ################################################################################
# Given an action line, remove the last trailing comma.
# ################################################################################
def drop_trailing_comma(match_results: list) -> list:
    """
    Delete any trailing comma from the end of the list of strings.
            :param match_results: a list of strings to check.
            :return: the list without trailing comma.

    """
    # Go thru list in reverse order, looking for the first comma at the end.
    for i in reversed(range(len(match_results))):
        if match_results[i].endswith(", "):
            match_results[i] = match_results[i][:-2]
            break

    return match_results


# Define a class for converting string '1' setting to its value
# code_flag identifies the type of xml data to go after based on the specific code
#   in <code>xxx</code>
# *args is an undetermined number of lists, each consisting of 3 pairs:
#   0: True=it is a string, False it is an integer,
#   1: the value to test
#   2: the value to plug in if it meets the test
def evaluate_action_setting(*args: list) -> list:
    """Evaluates action settings and returns results.
    Define a class for converting string '1' setting to its value.
    Args:
        args: Variable length argument list of item lists
    Returns:
        list: List of evaluated results
    - Loops through each item list in args
    - Checks if first element is True and second element is not empty string
    - If so, appends second and third elements joined to results
    - Else if first element is True or second element is not "1"
       appends empty string to results
    - Else appends third element to results
    - Returns the results list"""
    results = []
    for item in args:
        if item[0] and item[1] != "":
            results.append(f"{item[2]}{item[1]}")
        elif item[0] or item[1] != "1":
            results.append("")
        else:
            results.append(item[2])

    return results


## Given a required value logic and its position, evaluate the found integer and add
def process_xml_list(
    names: list,
    arg_location: int,
    the_int_value: str,
    match_results: list,
    arguments: defusedxml.ElementTree,
) -> None:
    """
    Evaluates an argument from an XML list and adds the processed result to match_results.
    Given a required value logic and its position, evaluate the found integer and add
        to match_results.
    The incoming list (names) looks something like the following:
    [
            ["Test:", "l", "235"],
            ", Name:",
            ", Value:",
            ["", "e", "Use Root"],
            ", Read Setting To:",
        ]
    arg_location points to the specific item in the above list that we are to process here.
    # code_flag identifies the type of xml data to go after based on the specific code
    #   in <code>xxx</code>
    # *args is an undetermined number of lists, each consisting of 3 pairs:
    #   1: True=it is a string, False it is an integer,
    #   2: the value to test
    #   3: the value to plug in if it meets the test

    Args:
        names (list): List of entries to substitute the argn value against.
        arg_location (int): The position of the argument in the lookup table.
        the_int_value (str): The integer value found in the <argn> XML element.
        match_results (list): List to store evaluated values.
        arguments (ElementTree): XML element containing argument definitions.

    Returns:
        None
    """
    the_list = names[arg_location]  # Retrieve the specific evaluation argument
    idx, len_of_list = 0, len(the_list)

    while True:
        idx = (idx + 1) % len_of_list  # Cycle through elements
        this_element = the_list[idx]

        if this_element in {"e", "if"}:
            idx = (idx + 1) % len_of_list
            next_element = the_list[idx]
            include_negative = the_list[0] == "1" if this_element == "e" else False
            evaluated_value = evaluate_action_setting(
                [include_negative, the_int_value, next_element],
            )
            match_results.append(
                f"{evaluated_value[0]} {'(selected)' if evaluated_value[0] else ''}, ",
            )
            break

        if this_element == "l":
            idx = (idx + 1) % len_of_list  # Move to lookup key
            lookup_key = the_list[idx]

            if lookup_key in lookup_values:
                try:
                    mapped_value = lookup_values[lookup_key][int(the_int_value)]
                    match_results.append(f"{the_list[idx - 2]}{mapped_value}, ")
                except (KeyError, IndexError):
                    match_results.append(
                        f"MapTasker 'mapped' error: int {the_int_value} not in lookup_values "
                        f"for item {lookup_key} ({lookup_values.get(lookup_key, [])})",
                    )
                break

            match_results.append(
                f"MapTasker 'mapped' error: {lookup_key} not in lookup table for {names}",
            )
            break

        error_handler(
            f"action.py get_xml_int_argument_to_value failed - this_element:{this_element} {arguments}",
            1,
        )
        break


# Get Task's label, disabled flag and any conditions
def get_label_disabled_condition(child: defusedxml.ElementTree) -> str:
    """
    Get Task's label, disabled flag and any conditions
        :param child: head Action xml element
        :return: the string containing any found label, disabled flag and conditions
    """
    task_label = ""
    task_conditions = ""
    remote_execution = ""
    remote_timeout = ""

    # If no code found, bail.
    if child.find("code") is not None:
        the_action_code = child.find("code").text
    else:
        return ""

    # Get the label, if any
    if child.find("label") is not None:
        lbl = child.find("label").text
        # Make sure the label doesn't have any HTML crap in it
        task_label = clean_label(lbl)
    # See if Action is disabled
    action_disabled = (
        format_html(
            "disabled_action_color",
            "",
            DISABLED,
            True,
        )
        if child.find("on") is not None
        else ""
    )
    # Look for any conditions:  <ConditionList sr="if">
    if child.find("ConditionList") is not None:  # If condition on Action?
        task_conditions = get_conditions(child, the_action_code)

    # Format conditions if any
    if task_conditions:
        task_conditions = format_html(
            "action_condition_color",
            "",
            task_conditions,
            True,
        )

    # See if this is a remote action
    if child.find("remoteDevice") is not None:
        # remote_execution = format_html("action_condition_color", "", ", Remote Device/Execution", True)
        remote_execution = ", Remote Device/Execution"

    # See if this is a remote timeout value
    if child.find("remoteTimeout") is not None:
        timout = child.find("remoteTimeout").text
        remote_timeout = ", Remote Timeout (Seconds): " + timout + "\n"

    # Return the lot
    return f"{task_conditions}{action_disabled}{task_label}{remote_execution}{remote_timeout}"


# Get any/all conditions associated wwith this Task.
# Get any/all conditions associated with Action
def get_conditions(child: defusedxml, the_action_code: str) -> str:
    """
    Generates conditional statements for an action.

    Args:
        child: {The XML element containing conditions}
        the_action_code: {The action code to check conditions against}

    Returns:
        result: {A string of concatenated conditional statements}

    1. Counts the number of conditions
    2. Initializes variables to store booleans and result
    3. Loops through <ConditionList> sub-elements
    4. Evaluates each <Condition> and adds to result string
    5. Returns the concatenated conditional statements or empty string
    """
    condition_count = 0
    boolean_to_inject = result = ""
    booleans = []
    # Go through <ConditionList sr="if"> sub-elements
    for children in child.find("ConditionList"):
        if "bool" in children.tag:
            booleans.append(children.text)
        # elif children.tag == "Condition" and the_action_code != "37":
        elif children.tag == "Condition":
            # Evaluate the condition to add to output
            string1, operator, string2 = evaluate_condition(children)
            if condition_count != 0:
                boolean_to_inject = f" {booleans[condition_count - 1].upper()} "
                # Add this conditional statement to the chain of conditional statements
            result = f"{result}{boolean_to_inject} condition: If {string1}{operator}{string2}"
            condition_count += 1
    if the_action_code == "35":  # Wait Until?
        result = result.replace(" condition: If", "<em>UNTIL</em>")
        # Just make all ":condition: If" as "IF"
    if result:
        result = f" ({result.replace(' condition: If', '<em>IF</em>')})"

    return result


# Given the Task action's label, get rid of anything that could be problematic
# for the output format
def clean_label(lbl: str) -> str:
    """
    Given the Task action's label, get rid of anything that could be problematic
    for the output format
        :param primary_iterms: dict contining all primary items.
            See primitem.py for details
        :param lbl: the label to clean up
        :return: the cleaned up label with added html tags for a label's color
    """
    # Remove html tags associated with label, and then add our own.
    lbl = lbl.replace("<", "&lt;").replace(">", "&gt;")
    lbl = remove_html_tags(lbl, "")
    return format_html(
        "action_label_color",
        "",
        f" ...with label: {lbl}",
        True,
    )


# Chase after relevant data after <code> Task action
# code_flag identifies the type of xml data to go after based on the specific code
# in <code>xxx</code>
# Get the: label, whether to continue Task after error, etc.
"""
Objective:
- The objective of the 'get_extra_stuff' function is to retrieve extra details about
    a Task Action, such as its label, disabled status, and conditions, and format
    them for output.

Inputs:
- 'code_action': an xml element representing the Task Action code
- 'action_type': a boolean indicating whether the code represents a Task Action or
                    a Profile condition

Flow:
- Check if the code represents a Task Action and if the display detail level
    is set to 3.
- If so, retrieve the label, disabled status, and conditions of the Task Action using
    the 'get_label_disabled_condition' function and format them for output.
- Check if the debug mode is enabled and if the code represents a Task Action.
- If so, add the code to the output.
- Check if the display detail level is set to 3.
- If so, check if the Task Action is set to continue after an error and add it
    to the output.
- Remove any empty '<span>' elements from the output.
- Return the formatted output.

Outputs:
- A string containing the formatted extra details about the Task Action.

Additional aspects:
- The function uses the 'get_label_disabled_condition' function to retrieve the label,
    disabled status, and conditions of the Task Action.
- The function formats the output using the 'format_html' function.
- The function removes any empty '<span>' elements from the output.
- The function only retrieves extra details if the code represents a Task Action and
    the display detail level is set to 3.
"""


# Chase after relevant data after <code> Task action
def get_extra_stuff(
    code_action: defusedxml.ElementTree,
    action_type: bool,
) -> str:
    """
    # Chase after relevant data after <code> Task action
    # code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
    # Get the: label, whether to continue Task after error, etc.

        :param code_action: action code (e.g. "543") xml element
        :param action_type: True if this is a Task Action, otherwise False
        :return: formatted line of extra details about Task Action
    """

    # If no code, just bail out.
    action_code_xml = code_action.find("code")
    if action_code_xml is None:
        return ""

    action_code = action_code_xml.text if action_code_xml is not None and not isinstance(action_code_xml, int) else ""

    program_arguments = PrimeItems.program_arguments
    colors_to_use = PrimeItems.colors_to_use

    # Only get extras if this is a Task action (vs. a Profile condition)
    if action_type and program_arguments["display_detail_level"] > DISPLAY_DETAIL_LEVEL_all_tasks:
        # Look for extra Task stuff: label, disabled, conditions
        extra_stuff = get_label_disabled_condition(code_action)
        # If this is an 'If' action, remove the 'IF' from the label since we already have it.
        if action_code == "37":
            extra_stuff = extra_stuff.replace("IF", "").replace("( ", "(")
        # Get rid of html that might screw up our output
        extra_stuff = (
            RE_FONT.sub("", extra_stuff)
            # extra_stuff.replace("</font>", "")
            if "<font" in extra_stuff and "</font>" not in extra_stuff
            else extra_stuff
        )
        extra_stuff = (
            extra_stuff.replace("</b>", "") if "<b>" in extra_stuff and "</b>" not in extra_stuff else extra_stuff
        )

    else:
        extra_stuff = ""

    if program_arguments["debug"] and action_type:  # Add the code if this is an Action and in debug mode
        extra_stuff = extra_stuff + format_html(
            "disabled_action_color",
            "",
            f"&nbsp;&nbsp;code: {code_action.find('code').text}-",
            True,
        )

    # See if Task action is to be continued after error
    if program_arguments["display_detail_level"] > DISPLAY_DETAIL_LEVEL_all_tasks:
        child = code_action.find("se")
        if child is not None and child.text == "false":
            extra_stuff = f"{format_html('action_color', '', ' [Continue Task After Error]', True)}{extra_stuff}"

    # For some reason, we're left with an empty "<span..." element.  Remove it.
    extra_stuff = extra_stuff.replace(
        f'<span style="color:{colors_to_use["action_color"]};{FONT_FAMILY}{program_arguments["font"]}"><span ',
        "<span ",
    )

    return f"{extra_stuff}"


def replace_newline(string: str) -> str:
    """Replace newlines with ';' in case there is more than one name in the string.

    Args:
        string (str): String to be formatted

    Returns:
        str: Formatted string with class information

    Note: we can not use an f-string with a backslash in it in Python 3.11.
    """
    if string:
        string = string.replace(",\n", "; ")  # Replace first
        string = f"Class:{string}"  # Then format
    else:
        string = ""
    return string


# Get the application specifics for the given code
def get_app_details(code_child: defusedxml.ElementTree) -> tuple[str, str, str]:
    """
    Extracts application details from the given XML code element.

    Args:
        code_child (ElementTree): XML element containing application details.

    Returns:
        tuple[str, str, str]: Class, package name, and app name.
    """
    app_class = app_pkg = app = ""

    child = code_child.find("App")
    if child is not None:
        app_class = child.findtext("appClass", default="")
        app_pkg = child.findtext("appPkg", default="")
        app = child.findtext("label", default="")
        # .replace(',\n', ';') is for handling multple names.
        app_class = replace_newline(app_class)
        app_pkg = replace_newline(app_pkg)
        app = replace_newline(app)

    return app_class, app_pkg, app
