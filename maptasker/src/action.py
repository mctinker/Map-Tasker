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
from maptasker.src.sysconst import DISABLED, FONT_FAMILY, RE_FONT, DISPLAY_DETAIL_LEVEL_all_tasks
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
def get_args(action: defusedxml.ElementTree, ignore_list: list) -> tuple[list, list, list]:
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
    # Go thru list in reevers order, looking for the first comma at the end.
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


# Given a required value logic and its position, evaluate the found integer and add
#   to match_results
# code_flag identifies the type of xml data to go after based on the specific code
#   in <code>xxx</code>
# *args is an undetermined number of lists, each consisting of 3 pairs:
#   1: True=it is a string, False it is an integer,
#   2: the value to test
#   3: the value to plug in if it meets the test
def process_xml_list(
    names: list,
    arg_location: int,
    the_int_value: str,
    match_results: list,
    arguments: defusedxml.ElementTree,
) -> None:
    """
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
        :param names: list of entries to substitute the argn value against from actionc.
        :param arg_location: the location of the argument in the lookup table
        :param the_int_value: tha integer value found in the <argn> xml element
        :param match_results: list in which to return the evaluated values
        :param arguments: list of arguments to look for (e.g. arg1,arg5,arg9)
        :return: nothing
    """

    the_list = names[arg_location]  # Point to the specific evaluation argument
    # the_title = the_list[0]  # Title is first element in the list
    idx = 0
    running = True
    # Loop through list two items at a time: 1st element is digit,
    #   2nd element is the name
    # to apply if it matches.
    len_of_list = len(the_list)
    while running:
        idx = (idx + 1) % len_of_list  # Get next element = first element in pair
        this_element = the_list[idx]

        # Are we to just evaluate for 0 or 1?
        if this_element in ["e", "if"]:
            idx = (idx + 1) % len_of_list
            next_element = the_list[idx]  # Second element in pair
            # Determine whether we are to include the negative value.
            # This will equate to True or False, depending on 1 or 0.
            # The next line equates to the followinbg commented-out lines.
            include_negative = the_list[0] == "1" if this_element == "e" else False
            # if this_element == "e":
            #    include_negative = the_list[0] == "1"  # This will equate to True or False, depending on 1 or 0.
            # else:
            #    include_negative = False  # The default
            evaluated_value = evaluate_action_setting([include_negative, the_int_value, next_element])
            evaluated_value = f"{evaluated_value[0]}, "
            match_results.append(evaluated_value)
            break

        # Are we to do a table lookup for the value?
        if this_element == "l":
            idx = (idx + 1) % len_of_list  # Point to the lookup key
            if the_list[idx] in lookup_values:
                try:
                    evaluated_value = [lookup_values[the_list[idx]][int(the_int_value)]]
                    evaluated_value = f"{the_list[idx - 2]}{evaluated_value[0]}, "
                    match_results.append(evaluated_value)
                except (KeyError, IndexError):
                    match_results.append(
                        f"MapTasker 'mapped' error in action: int {the_int_value} not"
                        f" in lookup_values (actiont) for item {the_list[idx]} which is"
                        f" {[lookup_values[the_list[idx]]]}",
                    )
                break

            # Error: the element is not in the lookup table.
            match_results.append(
                f"MapTasker 'mapped' error in action: {the_list[idx]} is not in"
                f" actiont (lookup table) for name:{names}",
            )
            # Get out of loop
            break

        # Not doing a table lookup.  Flag it as an error.
        error_handler(
            (
                "get_xml_int_argument_to_value failed-"
                f" this_element:{this_element} {arguments} for element"
                f" {this_element}"
            ),
            1,
        )


# Get Task's label, disabled flag and any conditions
def get_label_disabled_condition(child: defusedxml.ElementTree.XML) -> str:
    """
    Get Task's label, disabled flag and any conditions
        :param child: head Action xml element
        :return: the string containing any found label, disabled flag and conditions
    """
    task_label = ""
    task_conditions = ""

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
        task_conditions = format_html("action_condition_color", "", task_conditions, True)

    # Return the lot
    return f"{task_conditions}{action_disabled}{task_label}"


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
        elif children.tag == "Condition" and the_action_code != "37":
            # Evaluate the condition to add to output
            string1, operator, string2 = evaluate_condition(children)
            if condition_count != 0:
                boolean_to_inject = f" {booleans[condition_count - 1].upper()} "
                # Add this conditional statement to the chain of conditional statements
            result = f"{result}{boolean_to_inject} condition: If {string1}{operator} {string2}"
            condition_count += 1
    if the_action_code == "35":  # Wait Until?
        result = result.replace(" condition: If", "<em>UNTIL</em>")
        # Just make all ":condition: If" as "IF"
    if result:
        result = f' ({result.replace(" condition: If", "<em>IF</em>")})'

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
- 'colormap': a dictionary containing colors to use in output
- 'program_args': a dictionary containing runtime arguments

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

    # If no code, just bail out.add
    if code_action.find("code") is None:
        return ""

    program_arguments = PrimeItems.program_arguments
    colors_to_use = PrimeItems.colors_to_use

    # Only get extras if this is a Task action (vs. a Profile condition)
    if action_type and program_arguments["display_detail_level"] > DISPLAY_DETAIL_LEVEL_all_tasks:
        # Look for extra Task stuff: label, disabled, conditions
        extra_stuff = get_label_disabled_condition(code_action)

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
            f'&nbsp;&nbsp;code: {code_action.find("code").text}-',
            True,
        )

    # See if Task action is to be continued after error
    if program_arguments["display_detail_level"] > DISPLAY_DETAIL_LEVEL_all_tasks:
        child = code_action.find("se")
        if child is not None and child.text == "false":
            extra_stuff = f'{format_html("action_color",""," [Continue Task After Error]",True)}{extra_stuff}'

    # For some reason, we're left with an empty "<span..." element.  Remove it.
    extra_stuff = extra_stuff.replace(
        f'<span style="color:{colors_to_use["action_color"]};{FONT_FAMILY}{program_arguments["font"]}"><span ',
        "<span ",
    )

    return f"{extra_stuff}"


# Get the application specifics for the given code
def get_app_details(code_child: defusedxml.ElementTree.XML) -> tuple[str, str, str, str]:
    """
    Get the application specifics for the given code (<App>)

        :param code_child: Action xml element
        :return: the aplication specifics - class, package name, app name, extra stuff
    """
    # extra_stuff = get_extra_stuff(code_child, action_type)
    app_class, app_pkg, app = "", "", ""
    child = code_child.find("App")
    if child is not None and child.tag == "App":
        if child.find("appClass") is None:
            # return "", "", "", extra_stuff
            return "", "", ""
        if child.find("appClass").text is not None:
            app_class = f'Class:{child.find("appClass").text}'
        if child.find("appPkg").text is not None:
            app_pkg = f', Package:{child.find("appPkg").text}'
        if child.find("label").text is not None:
            app = f', App:{child.find("label").text}'
    # return app_class, app_pkg, app, extra_stuff
    return app_class, app_pkg, app
