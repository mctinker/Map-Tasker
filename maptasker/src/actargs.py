"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# actargs: process Task "Action" arguments                                             #
#                                                                                      #

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


# The <Vals> entries that belong to Tasker and the plugin FRAMEWORK rather than to the
# plugin's own configuration: the blurb, the list of fields Tasker may substitute a
# variable into, the "subbundled" flag, and the rest of the locale-plugin plumbing.  Left
# out because none of them is a setting the user made -- they are how the two programs talk
# to each other -- and on this repo's reference backup they are two thirds of everything a
# <Vals> holds.
BUNDLE_HOUSEKEEPING = ("net.dinglisch.android.tasker.", "com.twofortyfouram.locale.")

# Every value in a <Vals> is written twice: the value, and a "<name>-type" beside it saying
# what Java class it is.  The class is the plugin's business, not the reader's.
BUNDLE_TYPE_SUFFIX = "-type"

# What Tasker writes for a plugin field the user never filled in.  Shown as nothing at all
# rather than as the word, the same rule the icon arguments follow below.
BUNDLE_UNSET = "<null>"


def get_plugin_settings(vals: defusedxml.ElementTree, already_shown: str = "") -> str:
    """A plugin action's own configuration, as "Name=value" lines.

    The blurb a plugin writes is a sentence for a person to read ("Push a note titled
    'Tect' with the message 'This'."), and it is all the Map used to show of a plugin
    action.  What the blurb leaves out is not minor: the PushBullet action above is
    configured with the Google account it pushes from, and that account -- an email address
    -- appears nowhere in its blurb.  A health check that reports the email then points at
    an action whose every displayed word is innocent, which reads as the check being wrong
    rather than the Map being incomplete.

    Named by the last dotted part of the tag, since a plugin prefixes every field with its
    own package: "com.pushbullet.android.tasker.ACCOUNT_NAME" is ACCOUNT_NAME, and the
    package is already on the line as the action's own Arg 1.

    Joined with newlines because that is what a blurb uses, and what the two formatters
    downstream expect: without "pretty" they become ", " (actionr.fix_config_parameters),
    and with it, one setting per line.

    already_shown is the tag the blurb itself came from, left out so it is not printed
    twice.  It is a parameter rather than a constant because one of the two tags a blurb
    can come from -- "Configcommand" -- is a field of the plugin's own like any other, and
    only the caller knows whether this bundle's blurb was taken from it.
    """
    settings = []
    for child in vals:
        if child.tag == already_shown or child.tag.endswith(BUNDLE_TYPE_SUFFIX):
            continue
        if child.tag.startswith(BUNDLE_HOUSEKEEPING):
            continue
        value = (child.text or "").strip()
        if not value or value == BUNDLE_UNSET:
            continue
        settings.append(f"{child.tag.rsplit('.', 1)[-1]}={value}")
    return "\n".join(settings)


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

    clean_string, blurb_tag = next(
        (
            (node.text, tag)
            for tag in ["com.twofortyfouram.locale.intent.extra.BLURB", "Configcommand"]
            if (node := vals.find(tag)) is not None and node.text
        ),
        ("", ""),
    )

    # If we have a <pref> tag, add it to the clean_string
    if pref:
        clean_string = f"Output Variables={pref}{clean_string}"

    # Then the plugin's own settings, which the blurb does not necessarily mention at all.
    settings = get_plugin_settings(vals, blurb_tag)
    if settings:
        clean_string = f"{clean_string}\n{settings}" if clean_string else settings

    # Separate configuration parameter arguments by commas.
    save_returning = evaluated_results["returning_something"]
    process_clean_string(clean_string, code_action, arg, evaluated_results, blank)
    evaluated_results["returning_something"] = save_returning

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
            # Every Str argument lives in its own <Str sr="argn">, including the ones Tasker
            # happens to name "Label" -- Goto's label, Set Widget Label's label, and so on.
            # The action's *own* <label> element is a different thing entirely and is already
            # displayed alongside the action by action.py, so nothing here reads it: doing so
            # used to swallow those arguments whole and show the action's label (usually
            # nothing at all) in their place.
            evaluated_string = extract_string(code_action, the_arg, argeval)
            evaluated_results[the_arg] = {
                "value": html.escape(evaluated_string),
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
def format_image(child: defusedxml) -> str:
    """
    The icon an <Img> points at, spelled out for the map.

    Tasker writes an icon in six shapes, and only two of them carry an <nme>:

        <var>          a %variable, resolved on the phone.  It wins over anything else left
                       in the element -- the same rule deviceinv.read_icon_element applies
                       for the editor.
        <nme>          alone: one of Tasker's own built-in icons.
        <nme> + <pkg>  a named icon inside an installed icon pack.
        <pkg>          alone, usually with the launcher <cls> beside it: an installed app's
                       own icon.  This is the shape 'Set Tasker Icon' (138) writes, and
                       carrying no <nme> is exactly why it used to map as nothing at all.
        <fle>          an image file on the device, named by its path.
        <sym>          a Material symbol name.

    An <Img> holding none of those is an icon that was never set -- Tasker writes the empty
    element anyway -- and maps as an empty string.

    Args:
        child: defusedxml - the <Img> element

    Returns:
        str - the icon it names, or "" if it names none
    """
    if variable := child.findtext("var", default="").strip():
        return variable

    name = child.findtext("nme", default="").strip()
    package = child.findtext("pkg", default="").strip()
    activity_class = child.findtext("cls", default="").strip()

    if name:
        # An icon pack's icon: the name only means anything alongside the pack holding it.
        return f"{name}, Package:{package}" if package else name
    if package:
        # An app's own icon.  The class names the activity Tasker takes the icon from.
        return f"Package:{package}, Class:{activity_class}" if activity_class else f"Package:{package}"

    return child.findtext("fle", default="").strip() or child.findtext("sym", default="").strip()


def extract_image(
    evaluated_results: dict,
    code_action: defusedxml,
    argeval: str,
    arg: str,
) -> None:
    """
    Extract this argument's icon into the evaluated results.

    Args:
        evaluated_results: dict - The dictionary containing the evaluation results
        code_action: defusedxml - The parsed defusedxml object
        argeval: str - The argument evaluation string
        arg: str - The argument number
    Returns:
        None - No return value
    Processing Logic:
        - Find this argument's <Img> element
        - Format whichever of Tasker's icon shapes it holds (see format_image)
        - Store it against the argument, or a blank if the icon was never set
    """
    the_arg = f"arg{arg[0]}"
    # Pair the element with the argument by its sr=, the way every other argument type here
    # is read.  No action declares two Icon arguments today, so the first <Img> would do,
    # but it costs nothing to be right if one ever does.  The fallback covers xml written
    # without an sr= at all.
    child = code_action.find(f"Img[@sr='{the_arg}']")
    if child is None:
        child = code_action.find("Img")

    image = format_image(child) if child is not None else ""
    if not image:
        evaluated_results[the_arg]["value"] = " "
        return

    # Separate the label from the value.  action_args hands over the argument's *name*
    # ("Icon") whenever it has one, not its arg_eval ("Icon="), which is why this has to add
    # the "=" the way extract_string and extract_integer do for Str and Int arguments --
    # without it the icon runs straight into its label as "Iconmw_navigation_apps".
    label = argeval if argeval.endswith("=") else f"{argeval}="
    evaluated_results[the_arg]["value"] = f"{label}{html.escape(image)}"


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
        (f"MapTasker actionc error the_action_code_plus {the_action_code_plus} 'types' for index {index} not mapped!"),
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
        argeval = (arg[2] if arg[2] and isinstance(arg[4], str) else arg[4]) if len(arg) > 4 else arg[2]

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

        # Evaluate the argument.
        evaluated_results = evaluate_argument(
            evaluated_results,
            arg,
            argeval,
            argtype,
            code_action,
        )

    return evaluated_results
