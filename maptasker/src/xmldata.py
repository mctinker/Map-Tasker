"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# xmldata: deal with the xml data                                                      #
#                                                                                      #
import os
import shutil

import defusedxml.ElementTree

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import clean


# See if the xml tag is one of the predefined types and return result
def tag_in_type(tag: str, flag: bool) -> bool:
    """
    Evaluate the xml tag to see if it is one of our predefined types

    Parameters: the tag to evaluate, and whether this is a Scene or not (which
            determines which list of types to look for)

    Returns: True if tag found, False otherwise
    """
    scene_task_element_types = [
        "ListElementItem",
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
        "PropertiesElement",  # this element doesn't contain anything of value/import
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
    # Return a boolean: True if tag found in the appropriate list, False otherwise
    return flag and tag in scene_task_element_types or not flag and tag in scene_task_click_types  # Boolean


# We have an integer.  Evaluaate it's value based oon the code's evaluation parameters.
def extract_integer(action: defusedxml.ElementTree.XML, arg: str, argeval: str) -> str:
    # Don't move import to avoid cirtcular import
    """
    Extract an integer value from an XML action element
    Args:
        action: {XML element}: The XML action element to search
        arg: {str}: The name of the argument to search for
        argeval: {str}: The evaluation to perform on the integer
    Returns:
        {str}: The result of the integer evaluation
    {Processes the XML action element to find the integer value associated with the given argument name.
    If found, performs the specified evaluation on the integer and returns the result. Returns an empty string if no integer is found.}
    - Searches child elements of the action for an 'Int' element matching the given argument name
    - Extracts the integer value or variable name if found
    - Performs the specified evaluation on the integer/variable, joining results into a string if a list
    - Returns the result of the evaluation or an empty string if no integer was found
    """
    from maptasker.src.action import drop_trailing_comma, process_xml_list

    the_int_value = ""
    result = []
    # Find the arg we are looking for.
    for child in action:
        if child.tag == "Int":
            the_arg = child.attrib.get("sr")
            # Is this our arg?
            if arg == the_arg:
                # We have the arg we are looking for.
                if child.attrib.get("val") is not None:
                    the_int_value = child.attrib.get("val")  # There a numeric value as a string?
                elif child.find("var") is not None:  # There is a variable name?
                    the_int_value = child.find("var").text
                if the_int_value:  # If we have an integer or variable name
                    # List of options for this Int?
                    if isinstance(argeval, list):
                        process_xml_list(
                            [argeval],
                            0,
                            the_int_value,
                            result,
                            [arg],
                        )
                        result = " ".join(result)
                    else:  # Not a list
                        result = argeval + the_int_value  # Just grab the integer value
                        break

                # No integer value or variable name found
                else:
                    result = ""

    # If we have a result, get rid of the trailing comma if there is one.
    if result:
        return drop_trailing_comma([result])[0]

    return ""  # No Integer value or variable found...return empty


# Extracts and returns the text from the given argument as a string.
def extract_string(action: defusedxml.ElementTree.XML, arg: str, argeval: str) -> str:
    """
    Extracts a string from an XML action element.
    Args:
        action: XML element to search in one line
        arg: Name of string argument to search for in one line
        argeval: Prefix to add to matched string in one line
    Returns:
        str: Extracted string with prefix or empty string in one line
    Processes the XML action element:
    - Loops through child elements looking for matching "Str" tag
    - Checks if tag attribute matches arg
    - Appends child text to list with argeval prefix
    - Returns first item after processing or empty string
    """
    from maptasker.src.action import drop_trailing_comma

    match_results = []
    all_strings = action.findall("Str")
    for child in all_strings:
        the_arg = child.attrib.get("sr")
        if arg == the_arg:
            if child.text is not None:
                # Catch the situation in which a newline has been entered for the value (carriage return)
                if child.text == "\n":
                    match_results.append(f"{argeval}(carriage return)")
                else:
                    match_results.append(f"{argeval}{child.text}")
            else:
                match_results.append("")
            break  # We have what we want.  Go to next child
    if match_results:
        return drop_trailing_comma(match_results)[0]
    return ""


# Given a string, remove all HTML (anything between < >) tags from it
def remove_html_tags(text: str, replacement: str) -> str:
    """
    Remove html tags from a string
    :param text: text from which HTML is to be removed
    :param replacement: text to replace HTML with, if any
    :return: the text with HTML removed
    """
    import re

    return re.sub(clean, replacement, text)


# Find Task by name in PrimeItems.tasker_root_elements["all_tasks"]
def find_task_by_name(task_name: str) -> defusedxml.ElementTree.XML:
    """
    Find a task by name in the tasker_root_elements["all_tasks"] list
    :param task_name: name of task to find
    :return: the task's (root) dictionary pointer, else None
    """
    for task in PrimeItems.tasker_root_elements["all_tasks"]:
        if PrimeItems.tasker_root_elements["all_tasks"][task]["name"] == task_name:
            return task
    return None


# Append file1 to file2
def append_files(file1_path: str, file2_path: str) -> None:
    """Appends the contents of file1 to file2.
    Parameters:
        - file1_path (str): Path to file1.
        - file2_path (str): Path to file2.
    Returns:
        - None: No return value.
    Processing Logic:
        - Open file1 in read mode.
        - Open file2 in append mode.
        - Copy contents of file1 to file2."""
    with open(file1_path, "r") as file1, open(file2_path, "a") as file2:
        shutil.copyfileobj(file1, file2)


# The XML file hs incorrect encoding.  Let's read it in and rewrite it correctly.
def rewrite_xml(file_to_parse: str) -> None:
    """Rewrite XML file with UTF-8 encoding.
    Parameters:
        - file_to_parse (str): Name of the file to be parsed.
    Returns:
        - None: No return value.
    Processing Logic:
        - Create new file with UTF-8 encoding.
        - Append, rename, and remove files.
        - Remove temporary file."""
    utf_xml = '<?xml version = "1.0" encoding = "UTF-8" standalone = "no" ?>\n'

    # Create the XML file with the encoding we want
    with open(".maptasker_tmp.xml", "w") as new_file:
        new_file.write(utf_xml)
        new_file.close()

    # Append, rename and remove.
    append_files(file_to_parse, ".maptasker_tmp.xml")
    os.remove(file_to_parse)
    os.rename(".maptasker_tmp.xml", file_to_parse)
    os.remove(".maptasker_tmp.xml")
