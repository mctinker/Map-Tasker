#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# xmldata: deal with the xml data                                                            #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #


# #######################################################################################
# See if the xml tag is one of the predefined types and return result
# #######################################################################################
def tag_in_type(tag: str, flag: bool) -> bool:
    """evaluate the xml tag to see if it is one of our predefined types

    Parameters: the tag to evaluate, and whether this is a Scene or not (which
            determines which list of types to look for)

    Returns: True if tag found, False otherwise

    """
    scene_task_element_types = [
        "ListElement",
        "TextElement",
        "ImageElement",
        "ButtonElement",
        "OvalElement",
        "EditTextElement",
        "RectElement",
        "WebElement",
        "CheckBoxElement",
        "DoodleElement",
        "PickerElement",
        "SceneElement",
        "SliderElement",
        "SpinnerElement",
        "SwitchElement",
        "ToggleElement",
        "VideoElement",
        # "PropertiesElement",  this element doesn't contain anything of value/import
    ]
    scene_task_click_types = [
        "checkchangeTask",
        "clickTask",
        "focuschangeTask",
        "itemselectedTask",
        "keyTask",
        "linkclickTask",
        "longclickTask",
        "mapclickTask",
        "maplongclickTask",
        "pageloadedTask",
        "strokeTask",
        "valueselectedTask",
        "videoTask",
        "itemclickTask",
        "itemlongclickTask",
    ]

    return (
        flag
        and tag in scene_task_element_types
        or not flag
        and tag in scene_task_click_types
    )  # Boolean


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
    # These imports MUST be here and not at top to avoid circular import error
    from maptasker.src.action import process_xml_list
    from maptasker.src.action import drop_trailing_comma

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
    from maptasker.src.action import drop_trailing_comma

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


def remove_html_tags(text: str, replacement: str) -> str:
    """Remove html tags from a string
    :param text: text from which HTML is to be removed
    :param replacement: text to replace HTML with, if any
    :return: the text with HTML removed
    """
    import re

    clean = re.compile('<.*?>')
    return re.sub(clean, replacement, text)
