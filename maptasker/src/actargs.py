#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# actargs: process Task "Action" arguments                                             #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
# #################################################################################### #
import contextlib

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.action as get_action
from maptasker.src.actiond import process_condition_list
from maptasker.src.format import format_html
from maptasker.src.sysconst import FormatLine, logger


# ##################################################################################
# We have a <bundle>.   Process it
# ##################################################################################
def get_bundle(
    code_action: defusedxml.ElementTree.XML, evaluated_results: dict
) -> dict:
    """_summary_
    Get the details regarding the <bundle> action argument type
        Args:
            code_action (defusedxml.ElementTree.XML): XML element of the action code <code>
            evaluated_results (dict): We stuff the findings in here for passing to the caller

        Returns:
            dict: The results from the <bundle> argument
    """
    child1 = code_action.find("Bundle")
    child2 = child1.find("Vals")
    child3 = child2.find(
        "com.twofortyfouram.locale.intent.extra.BLURB"
    )  # 2:40 am...funny!
    if child3 is not None and child3.text is not None:
        # Get rid of extraneous html in Action's label
        # clean_string = child3.text.replace("</font><br><br>", "<br><br>")
        # clean_string = clean_string.replace("&lt;", "<")
        # clean_string = clean_string.replace("&gt;", ">")
        clean_string = child3.text
        evaluated_results["result_bun"].append(clean_string)
    else:
        evaluated_results["returning_something"] = False
    return evaluated_results


# ##################################################################################
# Given an <argn> element, evaluate it's contents based on our Action code dictionary
# ##################################################################################
def get_action_arguments(
    primary_items: dict,
    evaluated_results: dict,
    arg: object,
    argeval: list,
    argtype: list,
    code_action: defusedxml.ElementTree.XML,
    action_type: defusedxml.ElementTree.XML,
) -> dict:
    """
    Given an <argn> element, evaluate it's contents based on our Action code dictionary
    (actionc.py)
        :param primary_items:  Program registry.  See primitem.py for details.
        :param evaluated_results: all the Action argument "types" and "arguments" as
            a dictionary
        :param arg: the incoming argument location/number (e.g. "0" for <arg0>)
        :param argeval: the evaluation argument from our action code table (actionc.py)
            e.g. "Timeout:" in "evalargs": ["", "Timeout:", ["", "e", ",
            Structure Output (JSON, etc)"]],
        :param argtype: the argument "type"- Str, Int, App, ConditionList, Bundle, Img
        :param code_action: xml element of the Action code (<code>nnn</code>)
        :param action_type: the Action type = True if this is a Task, False if it is
        a condition
        :return:  of results
    """

    # Assume we are returing something and that we have a <str> or <int> argument to get
    evaluated_results["returning_something"] = True
    evaluated_results["get_xml_flag"] = True

    # Evaluate the argument based on its type
    match argtype:
        case "Str":
            evaluated_results["strargs"].append(f"arg{str(arg)}")
            evaluated_results["streval"].append(argeval)

        case "Int":
            evaluated_results["intargs"].append(f"arg{str(arg)}")
            evaluated_results["inteval"].append(argeval)

        case "App":
            extract_argument(evaluated_results, arg, argeval)
            app_class, app_pkg, app, extra = get_action.get_app_details(
                primary_items, code_action, action_type
            )
            evaluated_results["result_app"].append(f"{app_class}, {app_pkg}, {app}")

        case "ConditionList":
            extract_condition(evaluated_results, arg, argeval, code_action)

        case "Img":
            extract_image(evaluated_results, code_action, argeval)
        case "Bundle":  # It's a plugin
            evaluated_results["get_xml_flag"] = False
            evaluated_results = get_bundle(code_action, evaluated_results)

        case _:
            print("rutroh!")
            evaluated_results["get_xml_flag"] = False
            logger.debug(f"get_action_results  unknown argtype:{argtype}!!!!!")
            evaluated_results["returning_something"] = False
    return evaluated_results


# ##################################################################################
# Get image details from <img> sub-elements.
# ##################################################################################
# Get image related details from action xml
def extract_image(evaluated_results, code_action, argeval):
    evaluated_results["get_xml_flag"] = False
    image, package = "", ""
    child = code_action.find("Img")
    # Image name
    with contextlib.suppress(Exception):
        image = child.find("nme").text
    if child.find("pkg") is not None:
        package = f'", Package:"{child.find("pkg").text}'
    elif child.find("var") is not None:  # There is a variable name?
        image = child.find("var").text
    if image:
        evaluated_results["result_img"].append(f"{argeval}{image}{package}")
    else:
        evaluated_results["result_img"].append(" ")
        evaluated_results["returning_something"] = False


# Get condition releated details from action xml
def extract_condition(evaluated_results, arg, argeval, code_action):
    # Get argument
    extract_argument(evaluated_results, arg, argeval)

    # Get the conditions
    condition_list, boolean_list = process_condition_list(code_action)

    # Go through all conditions
    conditions = []
    for numx, condition in enumerate(condition_list):
        # Add the condition 0 1 2: a = x
        conditions.append(f" {condition[0]}{condition[1]}{condition[2]}")
        # Add the boolean operator if it exists
        if boolean_list and len(boolean_list) > numx:
            conditions.append(f" {boolean_list[numx]}")
    seperator = ""
    evaluated_results["result_con"].append(seperator.join(conditions))


# Get the argument details from action xml
def extract_argument(evaluated_results, arg, argeval):
    evaluated_results["get_xml_flag"] = False
    evaluated_results["strargs"].append(f"arg{str(arg)}")
    evaluated_results["streval"].append(argeval)


# ##################################################################################
# Action code not found...let user know
# ##################################################################################
def handle_missing_code(primary_items, the_action_code_plus, index):
    error_message = format_html(
        primary_items,
        "action_color",
        "",
        (
            "MapTasker actionc error the_action_code_plus"
            f" {the_action_code_plus} 'types' for index {index} not mapped!"
        ),
        True,
    )
    logger.debug(error_message)
    primary_items["output_lines"].add_line_to_output(
        primary_items, 4, error_message, FormatLine.dont_format_line
    )
    return ""


# ##################################################################################
# Go through the arguments and parse each one based on its argument 'type'
# ##################################################################################
def action_args(
    primary_items: dict,
    arg_list: list,
    the_action_code_plus: str,
    lookup_code_entry: dict,
    evaluate_list: list,
    code_action: defusedxml.ElementTree.XML,
    action_type: defusedxml.ElementTree.XML,
    evaluated_results: dict,
) -> object:
    """
    Go through the arguments and parse each one based on its argument 'type'
        :param primary_items:  Program registry.  See primitem.py for details.
        :param arg_list: list of arguments (xml "<argn>") to process
        :param the_action_code_plus: the lookup the Action code from actionc with
            "action type" (e.g. 861t, t=Task, e=Event, s=State)
        :param lookup_code_entry: dictionary entry for code nnnx (e.g. for entry "846t")
        :param evaluate_list: dictionary into which we are supplying the results
        :param code_action: xml element of the action code (<code>)
        :param action_type: True if this is for a Task, False if for a condition
            (State, Event, etc.)
        :param evaluated_results: dictionary into which to store the results
        :return: dictionary of the stored results
    """
    our_action_code = lookup_code_entry[the_action_code_plus]
    our_action_args = our_action_code["args"]

    # Go through each <arg> in list of args
    for num, arg in enumerate(arg_list):
        # Find the location for this arg in dictionary key "types' since they can be
        # non-sequential (e.g. '1', '3', '4', '6')
        index = num if arg == "if" else our_action_args.index(arg)

        # Get the arg name and type
        try:
            argeval = evaluate_list[num]
        except IndexError:
            evaluated_results["returning_something"] = False
            evaluated_results["error"] = (
                "MapTasker mapped IndexError error in action_args...action details not"
                " displayed"
            )
            return evaluated_results
        try:
            argtype = our_action_code["types"][index]
        except IndexError:
            argtype = handle_missing_code(primary_items, the_action_code_plus, index)

        # Get the Action arguments
        evaluated_results["position_arg_type"].append(argtype)
        evaluated_results = get_action_arguments(
            primary_items,
            evaluated_results,
            arg,
            argeval,
            argtype,
            code_action,
            action_type,
        )

    return evaluated_results
