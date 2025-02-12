"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# actargs: process Task "Action" arguments                                             #
#                                                                                      #

import contextlib

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.action as get_action
from maptasker.src.actiond import process_condition_list
from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine, logger
from maptasker.src.xmldata import extract_integer, extract_string


## We have a <bundle>.   Process it
def get_bundle(code_action: defusedxml.ElementTree, evaluated_results: dict, arg: str) -> dict:
    """
    Extracts a bundle value from an XML code action.

    Args:
        code_action (ElementTree.XML): The XML code action.
        evaluated_results (dict): Dictionary to store results.
        arg (str): Argument name.

    Returns:
        dict: Updated evaluated results.
    """
    bundle = code_action.find("Bundle")
    if bundle is None:
        evaluated_results[f"arg{arg}"] = {"value": ""}
        evaluated_results["returning_something"] = False
        return evaluated_results

    vals = bundle.find("Vals")
    if vals is None:
        evaluated_results[f"arg{arg}"] = {"value": ""}
        evaluated_results["returning_something"] = False
        return evaluated_results

    clean_string = next(
        (
            node.text
            for tag in ["com.twofortyfouram.locale.intent.extra.BLURB", "Configcommand"]
            if (node := vals.find(tag)) is not None and node.text
        ),
        "",
    )

    if clean_string:
        if PrimeItems.program_arguments.get("pretty", False):
            clean_string = clean_string.replace("\n\n", "\n").replace("\n", ",")

        evaluated_results[f"arg{arg}"] = {"value": f"Configuration Parameter(s):\n{clean_string}\n"}
    else:
        evaluated_results[f"arg{arg}"] = {"value": ""}
        evaluated_results["returning_something"] = False

    return evaluated_results


# Given an <argn> element, evaluate it's contents based on our Action code dictionary
def get_action_arguments(
    evaluated_results: dict,
    arg: object,
    argeval: list,
    argtype: str,
    code_action: defusedxml.ElementTree,
) -> dict:
    """
    Extracts action arguments from an XML code action.

    Args:
        evaluated_results (dict): Stores evaluation results.
        arg (object): Argument object.
        argeval (list): Argument evaluation criteria.
        argtype (str): Argument type.
        code_action (defusedxml.ElementTree.XML): XML code action.

    Returns:
        dict: Updated evaluated results.
    """
    evaluated_results["returning_something"] = True
    the_arg = f"arg{arg}"

    match argtype:
        case "Int":
            evaluated_results[the_arg] = {"value": extract_integer(code_action, the_arg, argeval)}

        case "Str":
            if argeval == "Label":
                label = next((child.text for child in code_action if child.tag == "label"), None)
                evaluated_results[the_arg] = {"value": label or ""}
            else:
                evaluated_results[the_arg] = {"value": extract_string(code_action, the_arg, argeval)}

        case "App":
            extract_argument(evaluated_results, arg, argeval)
            app_class, app_pkg, app = get_action.get_app_details(code_action)
            evaluated_results[the_arg] = {"value": f"{app_class}, {app_pkg}, {app}"}

        case "ConditionList":
            extract_condition(evaluated_results, arg, argeval, code_action)

        case "Img":
            extract_image(evaluated_results, code_action, argeval, arg)

        case "Bundle":
            get_bundle(code_action, evaluated_results, arg)

        case _:
            logger.debug(f"actargs get_action_results error: unknown argtype '{argtype}'")
            evaluated_results["returning_something"] = False

    return evaluated_results


# Get image related details from action xml
def extract_image(evaluated_results: dict, code_action: defusedxml, argeval: str, arg: str) -> None:
    """
    Extract image from evaluated results
    Args:
        evaluated_results: dict - The dictionary containing the evaluation results
        code_action: defusedxml - The parsed defusedxml object
        argeval: str - The argument evaluation string
        arg: str - The argument number
    Returns:
        None - No return value
    Processing Logic:
        - Find the <Img> tag in the code_action
        - Extract the image name and package if present
        - Append the image details to the result_img list in evaluated_results dictionary
        - Set returning_something to False if no image is found
    """
    image, package = "", ""
    child = code_action.find("Img")
    if child is None:
        return
    # Image name
    with contextlib.suppress(Exception):
        image = child.find("nme").text
    if child.find("pkg") is not None:
        package = f'", Package:"{child.find("pkg").text}'
    elif child.find("var") is not None:  # There is a variable name?
        image = child.find("var").text
    if image:
        evaluated_results[f"arg{arg}"]["value"] = f"{argeval}{image}{package}"

    else:
        evaluated_results[f"arg{arg}"]["value"] = " "


# Get condition releated details from action xml
def extract_condition(evaluated_results: dict, arg: str, argeval: str, code_action: str) -> None:
    # Get argument
    """
    Extracts the condition from the code action.
    Args:
        evaluated_results: dict - The dictionary containing the evaluated results
        arg: str - The argument to extract
        argeval: str - The argument evaluation
        code_action: str - The code action string
    Returns:
        None - No return, modifies evaluated_results in place
    Processing Logic:
        - Get the argument from evaluated_results
        - Process the condition list and boolean list from the code action
        - Iterate through conditions and boolean operators, appending to a list
        - Join the condition list with separators and add to evaluated_results
    """
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

    evaluated_results[f"arg{arg}"]["value"] = seperator.join(conditions)


# Get the argument details from action xml
# Get the argument details from action xml
def extract_argument(evaluated_results: dict, arg: str, argeval: str) -> None:
    """
    Extracts an argument from evaluated results
    Args:
        evaluated_results: Dictionary containing evaluated results
        arg: Argument name
        argeval: Argument evaluation
    Returns:
        None: Function does not return anything
    - Appends argument name to strargs list in evaluated_results
    - Appends argument evaluation to streval list in evaluated_results
    - Sets get_xml_flag to False"""
    evaluated_results[f"arg{arg}"]["value"] = argeval


# Action code not found...let user know
def handle_missing_code(the_action_code_plus: str, index: int) -> str:
    """
    Handle missing action code in MapTasker.
    Args:
        the_action_code_plus: Action code string to check (in one line)
        index: Index being processed (in one line)
    Returns:
        str: Empty string (in one line)
    - Format error message for missing action code
    - Log error message
    - Add error message to output
    - Return empty string
    """
    error_message = format_html(
        "action_color",
        "",
        (
            "MapTasker actionc error the_action_code_plus"
            f" {the_action_code_plus} 'types' for index {index} not mapped!"
        ),
        True,
    )
    logger.debug(error_message)
    PrimeItems.output_lines.add_line_to_output(0, error_message, FormatLine.dont_format_line)
    return ""


# Go through the arguments and parse each one based on its argument 'type'
def action_args(
    arg_list: list,
    the_action_code_plus: str,
    lookup_code_entry: dict,
    evaluate_list: list,
    code_action: defusedxml,
    evaluated_results: dict,
) -> object:
    """
    Go through the arguments and parse each one based on its argument 'type'

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
    our_action_args = our_action_code.args

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
                "MapTasker mapped IndexError error in action_args...action details not displayed"
            )
            return evaluated_results
        try:
            argtype = our_action_code.types[index]
        except IndexError:
            argtype = handle_missing_code(the_action_code_plus, index)

        # Get the Action arguments
        evaluated_results[f"arg{arg}"] = {}
        evaluated_results[f"arg{arg}"]["type"] = argtype
        evaluated_results = get_action_arguments(
            evaluated_results,
            arg,
            argeval,
            argtype,
            code_action,
        )

    return evaluated_results
