# ########################################################################################## #
#                                                                                            #
# actiond: Task Action dictionary functions for MapTasker                                    #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import xml.etree.ElementTree  # Need for type hints
from typing import Any

import routines.action as get_action
from routines.actionc import *
from routines.sysconst import logger
from config import *

ignore_list = ["code", "label", "se", "on", "ListElementItem", "pri", "pin"]


# #######################################################################################
# Provide the Action dictionary to the caller
# #######################################################################################
def get_dict() -> xml.etree.ElementTree:
    return action_codes


# #######################################################################################
# Update the dictionary for the Action code
# #######################################################################################
def update_action_codes(
    action: xml.etree.ElementTree, dict_code: xml.etree.ElementTree
) -> xml.etree.ElementTree:
    # #######################################################################################
    # Update dictionary entry for this code in the format of an output line
    # dict = { 'the_code':
    #               {num_args: num,
    #                args: arg0, arg1, ... type: Int/Str  }
    # #######################################################################################
    arg_list, type_list, arg_nums = get_action.get_args(action, ignore_list)
    arg_count = len(arg_list)

    if (
        arg_count > action_codes[dict_code]["numargs"]
    ):  # Compare this Actions num of args to dictionary's
        action_codes[dict_code]["numargs"] = arg_count
        action_codes[dict_code]["args"] = arg_nums
        action_codes[dict_code]["types"] = type_list
        logger.debug(f"update_action_codes: {dict_code} {str(action_codes[dict_code])}")
    return


# #######################################################################################
# Build the dictionary for the Action code
# #######################################################################################
def build_new_action_codes(
    action: xml.etree.ElementTree, dict_code: xml.etree.ElementTree
) -> xml.etree.ElementTree:
    logger.info(f"...for {dict_code}")

    # #######################################################################################
    # Create a dictionary entry for this code in the format of an output line
    # dict = { 'the_code':
    #               {num_args: num, args: ['arg0', 'arg1', ...], types: ['Str', 'Int', ...]
    # #######################################################################################
    arg_list, type_list, arg_nums = get_action.get_args(action, ignore_list)
    arg_count = len(arg_list)
    action_codes[dict_code] = {
        "numargs": arg_count,
        "args": arg_nums,
        "types": type_list,
    }
    return


# #######################################################################################
# Build the dictionary for each Action code
# child = pointer to <code> xml
# action = pointer to root xml (<Action> or <Profile>)
# adder = empty if <action>.  Else it is a Profile condition, and we need to make key unique
# #######################################################################################
def build_action_codes(
    child: xml.etree.ElementTree,
    action: xml.etree.ElementTree,
    adder: xml.etree.ElementTree,
    program_args: xml.etree.ElementTree,
) -> xml.etree.ElementTree:
    #  multiplier = 10 if adder else 1
    dict_code = child.text + adder
    if (
        dict_code not in action_codes
    ):  # We have a code that is not yet in the dictionary?
        build_new_action_codes(action, dict_code)
        logger.debug(f"build_new_action_codes: {dict_code} ", action_codes[dict_code])
        if program_args["debug"]:
            print("build_new_action_codes: ", dict_code, " ", action_codes[dict_code])
    else:
        update_action_codes(action, dict_code)
    return


# ####################################################################################################
# See if the display name is already in our Action dictionary.  If not, add it.
# ####################################################################################################
def add_name_to_action_codes(
    dict_code: xml.etree.ElementTree, display_name: xml.etree.ElementTree
) -> xml.etree.ElementTree:
    if dict_code not in action_codes:
        build_new_action_codes("", dict_code)
    if display_name not in action_codes[dict_code]:
        action_codes[dict_code]["display"] = display_name
    return


# ####################################################################################################
# Trundle through ConditionList "If" conditions
# Return the list of conditions and list of associated booleans
# ####################################################################################################
def process_condition_list(
    code_action: xml.etree.ElementTree.Element,
) -> tuple[list[list[Any]], list[str]]:
    condition_list, boolean_list = [], []
    condition_list_str = code_action.find("ConditionList")
    if condition_list_str is not None:
        for child in condition_list_str:
            if "bool" in child.tag:
                operation = child.text.upper()
                boolean_list.append(operation)
            elif child.tag == "Condition":
                (
                    first_string,
                    the_operation,
                    second_string,
                ) = get_action.evaluate_condition(child)
                condition_list.append([first_string, the_operation, second_string])
    return condition_list, boolean_list
