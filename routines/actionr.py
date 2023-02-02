# ########################################################################################## #
#                                                                                            #
# actionr: process Task "Action" and return the result                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
# ########################################################################################## #
import sys
import xml.etree.ElementTree  # Need for type hints

import routines.action as get_action
from routines.actargs import action_args
from routines.sysconst import logger
from routines.actionc import *
from collections import defaultdict


# ####################################################################################################
# Given a list of positional items, return a string in the correct order based on position
# ####################################################################################################
def get_results_in_arg_order(evaluated_results: dict) -> str:
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
            case "Bundle":  # Ignore for now
                if evaluated_results["result_bun"]:
                    the_item = evaluated_results["result_bun"][0]
                    evaluated_results["result_bun"].pop(0)
            case _:
                logger.debug(
                    f'Function get_results_in_arg_order: no match for "arg":{arg}'
                )
                sys.exit(8)
        return_result = f"{return_result} {the_item}"  # Get the appropriate item
    return return_result


# ####################################################################################################
# For the given code, save the display_name, required arg list and associated type list in dictionary
# Then evaluate the data against the master dictionary of actions
# ####################################################################################################
def evaluate_action_args(
    dict_code: xml.etree.ElementTree,
    arg_list: list,
    code_action: xml.etree.ElementTree,
    action_type: bool,
    colormap: dict,
    program_args: dict,
    lookup_code_entry: dict,
    evaluate_list: list,
    evaluated_results: dict,
) -> tuple:
    # Process the Task action arguments
    evaluated_results = action_args(
        arg_list,
        dict_code,
        lookup_code_entry,
        evaluate_list,
        code_action,
        action_type,
        colormap,
        program_args,
        evaluated_results,
    )
    # If we had at least one Int or Str then deal with them
    if evaluated_results["get_xml_flag"]:
        if evaluated_results["strargs"]:
            evaluated_results["result_str"] = get_action.get_xml_str_argument_to_value(
                code_action, evaluated_results["strargs"], evaluated_results["streval"]
            )
        if evaluated_results["intargs"]:
            evaluated_results["result_int"] = get_action.get_xml_int_argument_to_value(
                code_action, evaluated_results["intargs"], evaluated_results["inteval"]
            )

    return evaluated_results


# ####################################################################################################
# For the given code, save the display_name, required arg list and associated type list in dictionary
# Then evaluate the data against the master dictionary of actions
# ####################################################################################################
def get_action_results(
    dict_code: str,
    lookup_code_entry: xml.etree.ElementTree,
    code_action: xml.etree.ElementTree,
    action_type: bool,
    colormap: xml.etree.ElementTree,
    arg_list: list[str],
    evaluate_list: list[str],
    program_args: xml.etree.ElementTree,
) -> str:
    evaluated_results = defaultdict(
        lambda: []
    )  # Setup default dictionary as empty list
    two_blanks = "&nbsp;&nbsp;"
    result = ""
    returning_something = False
    if "s" in dict_code or "e" in dict_code:
        display_name_color = ""
        display_detail_color = ""
    else:
        display_name_color = (
            '<span style="color:' + colormap["action_name_color"] + '"</span>'
        )
        display_detail_color = (
            '<span style="color:' + colormap["action_color"] + '"</span>'
        )

    # Save the associated data
    # action_codes[dict_code]['display'] = display_name
    lookup_code_entry[dict_code]["reqargs"] = arg_list
    lookup_code_entry[dict_code]["evalargs"] = evaluate_list
    # If just displaying action names or there are no action details, then just display the name
    if arg_list and program_args["display_detail_level"] != 2:
        # Evaluate the required args per arg_list
        evaluated_results = evaluate_action_args(
            dict_code,
            arg_list,
            code_action,
            action_type,
            colormap,
            program_args,
            lookup_code_entry,
            evaluate_list,
            evaluated_results,
        )
    # Evaluate the required args

    # If we have results from evaluation, then go put them in their appropriate order
    if evaluated_results["returning_something"]:
        result = get_results_in_arg_order(evaluated_results)
    return (
        display_name_color
        + action_codes[dict_code]["display"]
        + display_detail_color
        + two_blanks
        + result
        + get_action.get_extra_stuff(code_action, action_type, colormap, program_args)
    )
