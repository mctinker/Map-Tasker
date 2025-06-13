"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# actargs: process Task "Action" arguments                                             #
#                                                                                      #

import contextlib
import html

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.action as get_action
from maptasker.src.actiond import process_condition_list
from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine, logger
from maptasker.src.xmldata import extract_integer, extract_string

blank = "&nbsp;"


def process_clean_string(
    clean_string: bool,
    code_action: defusedxml.ElementTree,
    arg: tuple,
    evaluated_results: dict,
    blank: str,
) -> None:
    """
    Processes and formats the clean_string based on program arguments and code action.

    Args:
        clean_string (str): The string to process.
        code_action: An object with a 'tag' attribute.
        arg (tuple): A tuple where the first element is used as an argument key.
        evaluated_results (dict): The dictionary to update with results.
        blank (str): A string containing a single blank space.
    """
    if not clean_string:
        evaluated_results[f"arg{arg[0]}"] = {"value": ""}
        evaluated_results["returning_something"] = False
        return

    pretty_print = PrimeItems.program_arguments.get("pretty", False)

    if pretty_print:
        clean_string = clean_string.replace("\n\n", "\n")
        clean_string = clean_string.replace("\n", ",")

        if code_action.tag == "Event":
            padding = blank * 50
            clean_string = f"{padding}{clean_string}"
            clean_string = clean_string.replace(",", f"\n{blank * 49}")

    evaluated_results[f"arg{arg[0]}"] = {
        "value": f"Configuration Parameter(s):\n{clean_string}\n",
    }


# Usage within your original context:
# process_clean_string(clean_string, code_action, arg, evaluated_results, blank)
## We have a <bundle>.   Process it
def get_bundle(
    code_action: defusedxml.ElementTree,
    evaluated_results: dict,
    arg: str,
) -> dict:
    """
    Extracts a bundle value from an XML code action.

    Args:
        code_action (ElementTree.XML): The XML code action.
        evaluated_results (dict): Dictionary to store results.
        arg (str): Argument name.

    Returns:
        dict: Updated evaluated results.

    evaluated_results["returning_something"] = True coming into this function
    """
    bundle = code_action.find("Bundle")
    if bundle is None:
        evaluated_results[f"arg{arg}"] = {"value": ""}
        evaluated_results["returning_something"] = False
        return evaluated_results

    # Handle any pref = Output Variables name
    pref_tag = bundle.find("pref")
    pref = pref_tag.text if pref_tag is not None else ""

    # Handle the twofortyfouram.locale.intent.extra.BLURB tag
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

    # If we have a <pref> tag, add it to the clean_string
    if pref:
        clean_string = f"Output Variables={pref}{clean_string}"

    # Separate configuration parameter arguments by commas.
    process_clean_string(clean_string, code_action, arg, evaluated_results, blank)

    return evaluated_results


# Given an <argn> element, evaluate it's contents based on our Action code dictionary
def evaluate_argument(
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
        code_action (defusedxml.ElementTree): XML code action.

    Returns:
        dict: Updated evaluated results.
    """
    evaluated_results["returning_something"] = True
    the_arg = f"arg{arg[0]}"

    match argtype:
        case "Int":
            if isinstance(argeval, str) and argeval[-1] != "=":
                argeval = argeval + "="
            evaluated_results[the_arg] = {
                "value": extract_integer(code_action, the_arg, argeval, arg),
            }

        case "Str":
            if argeval == "Label":
                label = next(
                    (child.text for child in code_action if child.tag == "label"),
                    None,
                )
                evaluated_results[the_arg] = {"value": label or ""}
            else:
                evaluated_string = extract_string(code_action, the_arg, argeval)
                # Convert any embedded html to plain text so it can be embedded ion our HTML.
                evaluated_string = html.escape(evaluated_string)
                evaluated_results[the_arg] = {
                    "value": evaluated_string,
                }

        case "Boolean":
            argeval = arg[4]  # Reform the eval: name, 'e', ''
            evaluated_results[the_arg] = {
                "value": extract_integer(code_action, the_arg, argeval, arg).strip(),
            }

        case "App":
            extract_argument(evaluated_results, arg, argeval)
            app_class, app_pkg, app = get_action.get_app_details(code_action)
            # join handles empty strings.
            evaluated_results[the_arg] = {
                "value": f"{', '.join(filter(None, [app_class, app_pkg, app]))}",
            }

        case "ConditionList":
            extract_condition(evaluated_results, arg, argeval, code_action)

        case "Img":
            extract_image(evaluated_results, code_action, argeval, arg)

        case "Icon":
            extract_image(evaluated_results, code_action, argeval, arg)

        case "Bundle":
            get_bundle(code_action, evaluated_results, arg)

        case _:
            logger.debug(
                f"actargs get_action_results error: unknown argtype '{argtype}'",
            )
            evaluated_results["returning_something"] = False

    return evaluated_results


# Get image related details from action xml
def extract_image(
    evaluated_results: dict,
    code_action: defusedxml,
    argeval: str,
    arg: str,
) -> None:
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
        evaluated_results[f"arg{arg[0]}"]["value"] = " "
        return
    # Image name
    with contextlib.suppress(Exception):
        image = child.find("nme").text
    if child.find("pkg") is not None:
        package = f'", Package:"{child.find("pkg").text}'
    elif child.find("var") is not None:  # There is a variable name?
        image = child.find("var").text
    if image:
        evaluated_results[f"arg{arg[0]}"]["value"] = f"{argeval}{image}{package}"

    else:
        evaluated_results[f"arg{arg[0]}"]["value"] = " "


# Get condition releated details from action xml
def extract_condition(
    evaluated_results: dict,
    arg: str,
    argeval: str,
    code_action: str,
) -> None:
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

    if f"arg{arg[0]}" not in evaluated_results:
        evaluated_results[f"arg{arg[0]}"] = {}

    evaluated_results[f"arg{arg[0]}"]["value"] = argeval


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
    PrimeItems.output_lines.add_line_to_output(
        0,
        error_message,
        FormatLine.dont_format_line,
    )
    return ""


# Go through the arguments and parse each one based on its argument 'type'
def action_args(
    the_action_code_plus: str,
    action_codes: list,
    code_action: defusedxml,
    evaluated_results: dict,
) -> list:
    """
    Go through the arguments and parse each one based on its argument 'type'

        #:param arg_list: list of arguments (xml "<argn>") to process
        :param the_action_code_plus: the lookup the Action code from actionc with
            "action type" (e.g. 861t, t=Task, e=Event, s=State)
        :param action_codes: Task action codes dictionary.
        :param code_action: xml element of the action code (<code>)
        :param evaluated_results: dictionary of the stored results
        :return evaluated_results: dictionary of the stored results
    """

    # Get the action code and arguments
    our_action_code = action_codes[the_action_code_plus]
    our_action_args = our_action_code.args

    # Go through each <arg> in list of args
    for num, arg in enumerate(our_action_args):
        # Find the location for this arg in dictionary key "types' since they can be
        # non-sequential (e.g. '1', '3', '4', '6')
        index = num if arg == "if" else our_action_args.index(arg)

        # If this is just a string, use Tasker's argument 'name'.  Otherwise, use the evalarg value in the argument.
        argeval = arg[2] if arg[2] and isinstance(arg[4], str) else arg[4]

        # Get the argument type: Int, Str, etc.
        try:
            # Make sure the argument 'type' is a digit = 0-9
            if not arg[3].isdigit():
                evaluated_results["error"] = (
                    "MapTasker mapped IndexError error in action_args...action details not displayed"
                )
                return evaluated_results
            argtype = PrimeItems.tasker_arg_specs[arg[3]]
        except IndexError:
            argtype = handle_missing_code(the_action_code_plus, index)

        # Get the Action arguments
        evaluated_results[f"arg{arg[0]}"] = {}
        evaluated_results[f"arg{arg[0]}"]["type"] = argtype
        evaluated_results = evaluate_argument(
            evaluated_results,
            arg,
            argeval,
            argtype,
            code_action,
        )

    return evaluated_results
