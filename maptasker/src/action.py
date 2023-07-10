#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# action: Find Task's Action arguments (<argn>) and return as sorted list                    #
#                                                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import defusedxml.ElementTree

from maptasker.src.shellsort import shell_sort
from maptasker.src.frmthtml import format_html
from maptasker.src.xmldata import remove_html_tags
from maptasker.src.error import error_handler


# #######################################################################################
# Given a Task's Action, find all 'arg(n)' xml elements and return as a sorted list
#  This is only called if the action code is not already in our master dictionary actionc.py
# Input:
#   action: list of actions or parameters
#   ignore_list: xml to ignore (e.g. label, on, etc.
# Output:
#   arg_lst: list of sorted args as numbers only (e.g. 'arg' removed from 'arg0')
#   type_list: list of sorted types (e.g. 'Int', 'Str', etc.)


# #######################################################################################
def get_args(
    action: defusedxml.ElementTree, ignore_list: list
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
        if action_arg is None:
            continue
        else:
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


# ####################################################################################################
# Check a value for '0' and return the appropriate string if it is/isn't
# ####################################################################################################
def if_zero_else(the_value: str, if_zero_string: str, if_not_zero_string: str) -> str:
    """
    Returns string #1 if the value is 0, otherwise return string #2
        :param the_value: the value to evaluate
        :param if_zero_string: the string to return if the value to evaluate is zero
        :param if_not_zero_string: the string to return if the value to evaluate is not zero
        :return: the value set by the above evaluation
    """
    return if_zero_string if the_value == "0" else if_not_zero_string


# ####################################################################################################
# Evaluate the If statement and return the operation
# ####################################################################################################
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
        "4": " !~R ",
        "5": " ~R ",
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
    if (
        "set" not in the_operation and child.find("rhs").text is not None
    ):  # No second string if "set/not" set
        second_operation = child.find("rhs").text
    else:
        second_operation = ""

    return first_string, the_operation, second_operation


def drop_trailing_comma(match_results: str) -> str:
    """
    Delete any trailing comma in output line
        :param match_results: the string to check
        :return: the string without trailing blanks
    """
    last_valid_entry = len(match_results) - 1  # Point to last item in list
    if last_valid_entry > 0:
        for i in range(last_valid_entry, -1, -1):
            item = match_results[i]
            if item == "":
                last_valid_entry = last_valid_entry - 1
            elif item.endswith(", "):
                match_results[i] = item[:-2]
                return match_results
            else:
                break
    return match_results


# ####################################################################################################
# Define a class for converting string '1' setting to its value
# code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
# *args is an undetermined number of lists, each consisting of 3 pairs:
#   1: True=it is a string, False it is an integer,
#   2: the value to test
#   3: the value to plug in if it meets the test
# ####################################################################################################
def evaluate_action_setting(*args: list) -> list:
    """
    Define a class for converting string '1' setting to its value
        :param args: list of arguments (<argn>)
        :return: list of found results contained in arguments
    """
    results = []

    for item in args:
        if item[0] and item[1] != "":
            results.append(item[2] + item[1])
        elif item[0] or item[1] != "1":
            results.append("")
        else:
            results.append(item[2])
    return results


# ####################################################################################################
# Given a required value logic and its position, evaluate the found integer and add to match_results
# code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
# *args is an undetermined number of lists, each consisting of 3 pairs:
#   1: True=it is a string, False it is an integer,
#   2: the value to test
#   3: the value to plug in if it meets the test
# ####################################################################################################
def process_xml_list(
    names: list,
    arg_location: int,
    the_int_value: str,
    match_results: list,
    arguments: defusedxml.ElementTree,
) -> None:
    """
    Given a required value logic and its position, evaluate the found integer and add to match_results
    # code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
    # *args is an undetermined number of lists, each consisting of 3 pairs:
    #   1: True=it is a string, False it is an integer,
    #   2: the value to test
    #   3: the value to plug in if it meets the test
        :param names: list of entries to substitute the argn value against.
        :param arg_location: the location of the argument in the lookup table
        :param the_int_value: tha integer value found in the <argn> xml element
        :param match_results: list in which to return the evaluated values
        :param arguments: list of Int arguments to look for (e.g. arg1,arg5,arg9)
        :return: nothing
    """
    # list of entries to substitute the argn value against.
    # NOTE: Do NOT move this import statement to avoid recursion
    from maptasker.src.actiont import lookup_values

    the_list = names[arg_location]
    the_title = the_list[0]  # Title is first element in the list
    idx = 0
    running = True
    # Loop through list two items at a time: 1st element is digit, 2nd element is the name
    # to apply if it matches.
    while running:
        idx = (idx + 1) % len(the_list)  # Get next element = first element in pair
        this_element = the_list[idx]
        if this_element.isdigit():  # First element of pair a digit?
            # Compare digit to that
            idx = (idx + 1) % len(the_list)
            next_element = the_list[idx]  # Second element in pair
            if this_element == the_int_value:
                match_results.append(the_title + next_element + ", ")
                break
            # idx = (idx + 1) % len(the_list)
            if idx > len(the_list):
                break
        elif this_element in ["e", "if"]:  # Are we to just evaluate for 0 or 1?
            idx = (idx + 1) % len(the_list)
            next_element = the_list[idx]  # Second element in pair
            evaluated_value = evaluate_action_setting(
                [False, the_int_value, next_element]
            )
            evaluated_value = f"{evaluated_value[0]}, "
            match_results.append(evaluated_value)
            break
        elif this_element == "l":  # Are we to do a table lookup for the value?
            idx = (idx + 1) % len(the_list)
            # next_element = the_list[idx]  # Second element in pair
            if the_list[idx] in lookup_values:
                try:
                    evaluated_value = [lookup_values[the_list[idx]][int(the_int_value)]]
                    evaluated_value = the_list[idx - 2] + evaluated_value[0] + ", "
                    match_results.append(evaluated_value)
                except KeyError:
                    match_results.append(
                        f"MapTasker 'mapped' error in action: int {the_int_value} not"
                        f" in lookup_values (actiont) for item {the_list[idx]} which is"
                        f" {[lookup_values[the_list[idx]]]}"
                    )
            # Error: the element is not in the lookup table.  OHandle the error and exit.
            else:
                match_results.append(
                    f"MapTasker 'mapped' error in action: {the_list[idx]} is not in"
                    f" actiont (lookup table) for name:{names}"
                )
            # Get out of loop
            break
        else:
            # Not a valid entry in the lookup table
            error_handler(
                (
                    "get_xml_int_argument_to_value failed-"
                    f" this_element:{this_element} {arguments} for element"
                    f" {this_element}"
                ),
                1,
            )

    return


# ####################################################################################################
# Get Task's label, disabled flag and any conditions
# ####################################################################################################
def get_label_disabled_condition(
    child: defusedxml.ElementTree.XML, colormap: dict
) -> str:
    """
    Get Task's label, disabled flag and any conditions
        :param child: head Action xml element
        :param colormap: the colors to use in the output
        :return: the string containing any found label, disabled flag and conditions
    """
    task_label = ""
    task_conditions = ""
    the_action_code = child.find("code").text
    # Get the label, if any
    if child.find("label") is not None:
        lbl = child.find("label").text
        # Make sure the label doesn't have any HTML crap in it
        task_label = clean_label(lbl, colormap)
    # See if Action is disabled
    action_disabled = (
        format_html(colormap, "disabled_action_color", "", " [DISABLED]", True)
        if child.find("on") is not None
        else ""
    )
    # Look for any conditions
    if child.find("ConditionList") is not None:  # If condition on Action?
        condition_count = 0
        boolean_to_inject = ""
        booleans = []
        # Go through <ConditionList> sub-elements
        for children in child.find("ConditionList"):
            if "bool" in children.tag:
                booleans.append(children.text)
            # We have a condition and this is not an "If" condition
            elif children.tag == "Condition" and the_action_code != "37":
                # Evaluate the condition to add to output
                string1, operator, string2 = evaluate_condition(children)
                if condition_count != 0:
                    boolean_to_inject = f"{booleans[condition_count - 1].upper()} "
                task_conditions = format_html(
                    colormap,
                    "action_condition_color",
                    "",
                    (
                        f' ({boolean_to_inject}condition:  '
                        f'If {string1}{operator}'
                        f'{string2})'
                    ),
                    True,
                )
                condition_count += 1
        if the_action_code == "35":  # Wait Until?
            task_conditions = task_conditions.replace(
                "condition:  If", "<em>UNTIL</em>"
            )
        # Just make all "":conditional: If" as "IF"
        task_conditions = task_conditions.replace(
                "condition:  If", "<em>IF</em>"
            )

    return task_conditions + action_disabled + task_label


# ####################################################################################################
# Given the Task action's label, get rid of anything that could be problematic for the output format
# ####################################################################################################
def clean_label(lbl: str, colormap: dict) -> str:
    """
    Given the Task action's label, get rid of anything that could be problematic for the output format
        :param lbl: the label to clean up
        :param colormap: the colors to use in the output
        :return: the cleaned up label with added html tags for a label's color
    """
    # Look for label with <font color=...> embedded
    lbl = remove_html_tags(lbl, "")

    return format_html(
        colormap, "action_label_color", "", f" ...with label: {lbl}", True
    )


# ####################################################################################################
# Chase after relevant data after <code> Task action
# code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
# Get the: label, whether to continue Task after error, etc.
# ####################################################################################################
'''
Objective:
- The objective of the 'get_extra_stuff' function is to retrieve extra details about a Task Action, such as its label, disabled status, and conditions, and format them for output.

Inputs:
- 'code_action': an xml element representing the Task Action code
- 'action_type': a boolean indicating whether the code represents a Task Action or a Profile condition
- 'colormap': a dictionary containing colors to use in output
- 'program_args': a dictionary containing runtime arguments

Flow:
- Check if the code represents a Task Action and if the display detail level is set to 3.
- If so, retrieve the label, disabled status, and conditions of the Task Action using the 'get_label_disabled_condition' function and format them for output.
- Check if the debug mode is enabled and if the code represents a Task Action.
- If so, add the code to the output.
- Check if the display detail level is set to 3.
- If so, check if the Task Action is set to continue after an error and add it to the output.
- Remove any empty '<span>' elements from the output.
- Return the formatted output.

Outputs:
- A string containing the formatted extra details about the Task Action.

Additional aspects:
- The function uses the 'get_label_disabled_condition' function to retrieve the label, disabled status, and conditions of the Task Action.
- The function formats the output using the 'format_html' function.
- The function removes any empty '<span>' elements from the output.
- The function only retrieves extra details if the code represents a Task Action and the display detail level is set to 3.
'''


def get_extra_stuff(
    primary_items: dict,
    code_action: defusedxml.ElementTree,
    action_type: bool,
) -> str:
    """
    # Chase after relevant data after <code> Task action
    # code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
    # Get the: label, whether to continue Task after error, etc.
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param code_action: action code (e.g. "543") xml element
        :param action_type: True if this is a Task Action, otherwise False
        :return: formatted line of extra details about Task Action
    """
    # Only get extras if this is a Task action (vs. a Profile condition)
    if action_type and primary_items["program_arguments"]["display_detail_level"] == 3:
        # Look for extra Task stiff: label, disabled, conditions
        extra_stuff = get_label_disabled_condition(
            code_action, primary_items["colors_to_use"]
        )
        if (
            "<font" in extra_stuff and "</font>" not in extra_stuff
        ):  # Make sure we terminate any fonts
            extra_stuff = f"{extra_stuff}</font>"
        if (
            "&lt;font" in extra_stuff and "&lt;/font&gt;" not in extra_stuff
        ):  # Make sure we terminate any fonts
            extra_stuff = f"{extra_stuff}</font>"
        if (
            "<b>" in extra_stuff and "</b>" not in extra_stuff
        ):  # Make sure we terminate any bold
            extra_stuff = f"{extra_stuff}</b>"
    else:
        extra_stuff = ""

    if (
        primary_items["program_arguments"]["debug"] and action_type
    ):  # Add the code if this is an Action and in debug mode
        extra_stuff = extra_stuff + format_html(
            primary_items["colors_to_use"],
            "Red",
            "",
            f'&nbsp;&nbsp;code: {code_action.find("code").text}-',
            True,
        )

    # See if Task action is to be continued after error
    if primary_items["program_arguments"]["display_detail_level"] == 3: 
        child = code_action.find("se")
        if child is not None and child.text == "false":
            extra_stuff = (
                format_html(
                    primary_items["colors_to_use"],
                    "action_color",
                    "",
                    " [Continue Task After Error]",
                    True,
                )
                + f"{extra_stuff}"
            )

    # For some reason, we're left with an empty "<span..." element.  Remove it.
    extra_stuff = extra_stuff.replace(
        '<span style="color:Yellow;font-family:Courier"><span ',
        '<span ',
    )

    return f"{extra_stuff}"


# ####################################################################################################
# Get the application specifics for the given code
# ####################################################################################################
def get_app_details(
    primary_items: dict, code_child: defusedxml.ElementTree.XML, action_type: bool
) -> tuple[str, str, str, str]:
    """
    Get the application specifics for the given code (<App>)
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param code_child: Action xml element
        :param action_type: True if this is a Task, False if a condition
        :return: the aplication specifics - class, package name, app name, extra stuff
    """
    extra_stuff = get_extra_stuff(primary_items, code_child, action_type)
    app_class, app_pkg, app = "", "", ""
    child = code_child.find("App")
    if child is not None and child.tag == "App":
        if child.find("appClass") is None:
            return "", "", "", extra_stuff
        if child.find("appClass").text is not None:
            app_class = "Class:" + child.find("appClass").text
        if child.find("appPkg").text is not None:
            app_pkg = ", Package:" + child.find("appPkg").text
        if child.find("label").text is not None:
            app = ", App:" + child.find("label").text
    return app_class, app_pkg, app, extra_stuff
