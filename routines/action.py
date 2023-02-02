# ########################################################################################## #
#                                                                                            #
# action: Task Action functions for MapTasker                                                #
#                                                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

from config import *
from routines.shellsort import shell_sort
from routines.sysconst import logger
import re
import sys

pattern = re.compile(r"<.*?>")


# #######################################################################################
# Given a Task's Action, find all 'arg(n)' xml elements and return as a sorted list
# Input:
#   action: list of actions or parameters
#   ignore_list: xml to ignore (e.g. label, on, etc.
# Output:
#   arg_lst: list of sorted args as numbers only (e.g. 'arg' removed from 'arg0')
#   type_list: list of sorted types (e.g. 'Int', 'Str', etc.)


# #######################################################################################
def get_args(action, ignore_list):
    arg_list, type_list, master_list = [], [], []
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
        shell_sort(
            master_list, True, False
        )  # Sort args by their number (e.g. arg0, arg1, arg2, ...)
        for child in master_list:
            type_list.append(child.tag)  # one of: 'Str' 'Int' 'Bundle' 'App'
            arg_list.append(child.attrib.get("sr"))
        arg_nums = [
            str(ind) for ind, x in enumerate(arg_list)
        ]  # Build list of arg position only (numeric part of argn)

    return arg_list, type_list, arg_nums


# ####################################################################################################
# Check a value for '0' and return the appropriate string if it is/isn't
# ####################################################################################################
def if_zero_else(the_value, if_zero_string, if_not_zero_string):
    return if_zero_string if the_value == "0" else if_not_zero_string


# ####################################################################################################
# Evaluate the If statement and return the operation
# ####################################################################################################
def evaluate_condition(child):
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
    ):  # No second string fort set/not set
        second_string = child.find("rhs").text
    else:
        second_string = ""

    return first_string, the_operation, second_string


# ####################################################################################################
# Delete any trailing comma in output line
# ####################################################################################################
def drop_trailing_comma(match_results):
    last_valid_entry = len(match_results) - 1  # Point to last item in list
    if last_valid_entry > 0:
        for item in reversed(match_results):
            if item == "":
                last_valid_entry = last_valid_entry - 1
            elif item[len(item) - 2 :] == ", ":
                match_results[last_valid_entry] = item[: len(item) - 2]
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
def evaluate_action_setting(*args):
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
# given a required value logic and its position, evaluate the found integer and add to match_results
# code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
# *args is an undetermined number of lists, each consisting of 3 pairs:
#   1: True=it is a string, False it is an integer,
#   2: the value to test
#   3: the value to plug in if it meets the test
# ####################################################################################################
def process_xml_list(names, arg_location, the_int_value, match_results, arguments):
    # NOTE: Do NOT move this import statement to avoid recursion
    from routines.actiont import lookup_values

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
                evaluated_value = [lookup_values[the_list[idx]][int(the_int_value)]]
                evaluated_value = the_list[idx - 2] + evaluated_value[0] + ", "
                match_results.append(evaluated_value)
            else:
                error_msg = f"Program error: {the_list[idx]} is not in actiont (lookup table) for name:{names}"
                logger.debug(error_msg)
                print(error_msg)
                sys.exit(1)
            break
        else:
            msg = (
                f"get_xml_int_argument_to_value failed- this_element:{this_element} {arguments}",
                names,
            )
            logger.debug(msg)
            exit(8)  # Rutroh...not an even pair of elements
    return


# ####################################################################################################
#  Given an action code (xml), find Int (integer) args and match with names
#  Example:
#  3 Ints with arg0, arg1 and arg2, to be filled in with their matching name0, name1 and name2 + the associated text
#  action = xml element for Action <code>
#  arguments = list of Int arguments to look for (e.g. arg1,arg5,arg9)
#  names = list of entries to substitute the argn value against.
#    ...It can be a list, which signifies a pull-down list of options to map against:
#         [ preceding_text1, value1, evaluated_text1, preceding_text2, value2, evaluated_text2, ...]
#         ['', 'e', 'name'] > Test for '1' and plug in 'name' if '1'
#         ['some_text', 'l', lookup_code] > use lookup_values dictionary to translate code and plug in value
# ####################################################################################################
def get_xml_int_argument_to_value(action, arguments, names):
    match_results = []

    for child in action:
        if child.tag == "Int":
            the_arg = child.attrib.get("sr")
            for arg in arguments:
                if arg == the_arg:
                    arg_location = arguments.index(arg)
                    the_int_value = ""
                    if child.attrib.get("val") is not None:
                        the_int_value = child.attrib.get(
                            "val"
                        )  # There a numeric value as a string?
                    elif child.find("var") is not None:  # There is a variable name?
                        the_int_value = child.find("var").text
                    if the_int_value:  # If we have an integer or variable name
                        # List of options for this Int?
                        if type(names[arg_location]) is list:
                            process_xml_list(
                                names,
                                arg_location,
                                the_int_value,
                                match_results,
                                arguments,
                            )
                        else:  # Not a list
                            match_results.append(
                                names[arg_location] + the_int_value
                            )  # Just grab the integer value
                        break  # Get out of arg loop and get next child
                    else:
                        match_results.append(
                            ""
                        )  # No Integer value or variable found...return empty

    return drop_trailing_comma(match_results)


# ####################################################################################################
#  Given an action code (xml), find Str (string) args and match with names
#  Example:
#  3 Strs with arg0, arg1 and arg2, to be filled in with their matching name0, name1 and name2 + the associated text
# ####################################################################################################
def get_xml_str_argument_to_value(action, arguments, names) -> list:
    match_results = []
    for child in action:
        if child.tag == "Str":
            the_arg = child.attrib.get("sr")
            for arg in arguments:
                if arg == the_arg:
                    arg_location = arguments.index(arg)
                    if child.text is not None:
                        match_results.append(names[arg_location] + child.text + ", ")
                    else:
                        match_results.append("")
                    break  # We have what we want.  Go to next child
    return drop_trailing_comma(match_results)


# ####################################################################################################
# Get Task's label, disabled flag and any conditions
# ####################################################################################################
def get_label_disabled_condition(child, colormap):
    disabled_action_html = (
        ' <span style = "color:'
        + colormap["disabled_action_color"]
        + '"</span>[DISABLED]'
    )

    task_label = ""
    task_conditions = ""
    the_action_code = child.find("code").text
    if child.find("label") is not None:
        lbl = child.find("label").text
        # We have to be careful what we strip out and what we replace for the label to maintain
        #  as much of the visual context as possible without blowing-up everything else that follows.
        if lbl not in ["", "\n"]:
            task_label = clean_label(lbl, colormap)

    action_disabled = disabled_action_html if child.find("on") is not None else ""
    if child.find("ConditionList") is not None:  # If condition on Action?
        condition_count = 0
        boolean_to_inject = ""
        booleans = []
        for children in child.find("ConditionList"):
            if "bool" in children.tag:
                booleans.append(children.text)
            elif children.tag == "Condition" and the_action_code != "37":
                string1, operator, string2 = evaluate_condition(children)
                if condition_count != 0:
                    boolean_to_inject = f"{booleans[condition_count - 1].upper()} "
                task_conditions = f'{task_conditions} <span style = "color:{action_condition_color}"</span> ({boolean_to_inject}condition:  If {string1}{operator}{string2})'
                condition_count += 1
        if the_action_code == "35":  # Wait Until?
            task_conditions = task_conditions.replace(
                "condition:  If", "<em>UNTIL</em>"
            )

    return task_conditions + action_disabled + task_label


# ####################################################################################################
# Given the Task action's label, get rid of anything that could be problematic for the output format
# ####################################################################################################
def clean_label(lbl, colormap):
    # Look for label with <font color=...> embedded
    lbl = lbl.replace("\n", "")
    lbl = lbl.replace("</font>", "")
    lbl = lbl.replace("</big>", "")
    lbl = lbl.replace("</font></font>", "</font>")
    font_count = lbl.count("<font")
    if (
        font_count > 0
    ):  # Make sure we end with the same number combination of <font> and </font>
        end_font_count = lbl.count("/font")
        if font_count > end_font_count:
            label_color = colormap["action_label_color"]
            lbl = f'{lbl}<font "color:{label_color}"</font>'

    return f' <span style = "color:{action_label_color}"</span>...with label: {lbl}'


# ####################################################################################################
# Chase after relevant data after <code> Task action
# code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
# Get the: label, whether to continue Task after error, etc.
# ####################################################################################################
def get_extra_stuff(code_action, action_type, colormap, program_args):
    if (
        action_type
    ):  # Only get extras if this is a Task action (vs. a Profile condition)
        extra_stuff = get_label_disabled_condition(
            code_action, colormap
        )  # Look for extra Task stiff: label, disabled, conditions
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
        program_args["debug"] and action_type
    ):  # Add the code if this is an Action and in debug mode
        extra_stuff = (
            f'{extra_stuff}<span style="color:Red"</span>&nbsp;&nbsp;code:'
            + code_action.find("code").text
            + "-"
        )

    # See if Task action is to be continued after error
    child = code_action.find("se")
    if child is not None and child.text == "false":
        extra_stuff = f" [Continue Task After Error]{extra_stuff}"
    return extra_stuff


# ####################################################################################################
# Get the application specifics for the given code
# ####################################################################################################
def get_app_details(code_child, action_type, colormap, program_args):
    extra_stuff = get_extra_stuff(code_child, action_type, colormap, program_args)
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
