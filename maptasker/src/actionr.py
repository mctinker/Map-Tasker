#! /usr/bin/env python3

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
import contextlib
import sys
from collections import defaultdict

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.action as get_action
from maptasker.src.actargs import action_args
from maptasker.src.actionc import action_codes
from maptasker.src.frmthtml import format_html
from maptasker.src.sysconst import logger
from maptasker.src.xmldata import get_xml_int_argument_to_value
from maptasker.src.xmldata import get_xml_str_argument_to_value


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
            case "Bundle":  # Plugin bundle
                if evaluated_results["result_bun"]:
                    the_item = evaluated_results["result_bun"][0]
                    evaluated_results["result_bun"].pop(0)
            case _:
                logger.debug(
                    f'Function get_results_in_arg_order: no match for "arg":{arg}'
                )
                the_item = (
                    f'Function get_results_in_arg_order: no match for "arg":{arg}'
                )
        return_result = f"{return_result} {the_item}"  # Get the appropriate item
    return return_result


# ####################################################################################################
# For the given code, save the display_name, required arg list and associated type list in dictionary
# Then evaluate the data against the master dictionary of actions
# ####################################################################################################
def evaluate_action_args(
    primary_items: dict,
    dict_code: defusedxml.ElementTree.XML,
    arg_list: list,
    code_action: defusedxml.ElementTree.XML,
    action_type: bool,
    lookup_code_entry: dict,
    evaluate_list: list,
    evaluated_results: dict,
) -> tuple:
    # Process the Task action arguments
    evaluated_results = action_args(
        primary_items,
        arg_list,
        dict_code,
        lookup_code_entry,
        evaluate_list,
        code_action,
        action_type,
        evaluated_results,
    )

    # If we had at least one Int or Str then deal with them

    # If TypeError, then we haven't properly mapped the action code in actionc.py.
    #   evaluated_results["error"] will have been filled with an error msg by actarg.py...just return with error msg
    # Otherwise, get the results by evaluating and formatting the str arguments and int arguments from xml
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


# ####################################################################################################
# For the given code, save the display_name, required arg list and associated type list in dictionary
# Then evaluate the data against the master dictionary of actions
# ####################################################################################################
def get_action_results(
    primary_items: dict,
    dict_code: str,
    lookup_code_entry: defusedxml.ElementTree.XML,
    code_action: defusedxml.ElementTree.XML,
    action_type: bool,
    arg_list: list[str],
    evaluate_list: list[str],
) -> str:
    evaluated_results = defaultdict(
        lambda: []
    )  # Setup default dictionary as empty list
    result = ""

    # Save the associated data
    lookup_code_entry[dict_code]["reqargs"] = arg_list
    lookup_code_entry[dict_code]["evalargs"] = evaluate_list
    # If just displaying action names or there are no action details, then just display the name
    if arg_list and primary_items["program_arguments"]["display_detail_level"] != 2:
        # Evaluate the required args per arg_list
        evaluated_results = evaluate_action_args(
            primary_items,
            dict_code,
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

    # Clean up the arguments, if any.  Replace <> so they appear properly and by remove any html
    if result:
        result = result.replace("<", "&lt;")
        result = result.replace(">", "&gt;")
        two_blanks = "&nbsp;&nbsp;"
        result = format_html(
            primary_items["colors_to_use"],
            "action_color",
            "",
            f"{two_blanks}{result}",
            True,
        )

    # Return the properly formatted HTML with the Action name and extra stuff
    return format_html(
        primary_items["colors_to_use"],
        "action_name_color",
        "",
        action_codes[dict_code]["display"],
        True,
    ) + format_html(
        primary_items["colors_to_use"],
        "action_color",
        "",
        (
            # f"<span>{two_blanks}{result}</span>"
            f"{result}{get_action.get_extra_stuff(primary_items, code_action, action_type)}"
        ),
        False,
    )
