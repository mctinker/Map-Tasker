"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# xmldata: deal with the xml data                                                      #
#                                                                                      #
import os
import re
import shutil

import defusedxml.ElementTree


# See if the xml tag is one of the predefined types and return result
def tag_in_type(tag: str, flag: bool) -> bool:
    """
    Evaluate the xml tag to see if it is one of our predefined types

    Parameters: the tag to evaluate, and whether this is a Scene or not (which
            determines which list of types to look for)

    Returns: True if tag found, False otherwise
    """
    scene_task_element_types = {
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
    }
    scene_task_click_types = {
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
    }
    # Return a boolean: True if tag found in the appropriate list, False otherwise
    return (flag and tag in scene_task_element_types) or (not flag and tag in scene_task_click_types)  # Boolean


# We have an integer.  Evaluaate it's value based oon the code's evaluation parameters.
def extract_integer(
    code_action: defusedxml.ElementTree,
    the_arg: str,
    argeval: str,
    arg: list,
) -> str:
    """
    Extract an integer value from an XML action element.

    Args:
        code_action (XML element): The XML action element to search.
        arg (str): The name of the argument to search for.
        argeval (str | list): The evaluation to perform on the integer.
        arg: (list): The list of arguments for this action from action_codes.

    Returns:
        str: The result of the integer evaluation.
    """
    from maptasker.src.action import drop_trailing_comma, process_xml_list  # noqa: PLC0415

    # Find the first matching <Int> element with the desired 'sr' attribute
    int_element = next(
        (child for child in code_action if child.tag == "Int" and child.attrib.get("sr") == the_arg),
        None,
    )
    if int_element is None:
        return ""  # No matching <Int> element found

    # Extract value or variable
    the_int_value = int_element.attrib.get("val") or (
        int_element.find("var").text if int_element.find("var") is not None else ""
    )

    if not the_int_value:
        return ""  # No valid integer or variable name found

    # Aeguement evaluation is a list
    if isinstance(argeval, list):
        result = []
        if len(argeval) > 1:
            # Handle the special case of "e" by adding a space before the value..expects a blank in element 0.
            new_argeval = ["", "e", argeval[1]] if argeval[0] == "e" else argeval
            # Handle special case of 'l' lookup.
            new_argeval = [f"{arg[2]}=", "l", argeval[2]] if arg[2] and argeval[1] == "l" else new_argeval
        else:
            new_argeval = argeval

        # Process the argument evaluation
        process_xml_list([new_argeval], 0, the_int_value, result, [the_arg])
        final_result = " ".join(result)

    # Argument evaluation is a string.
    elif isinstance(argeval, str):
        # If eval is missing, just use the argujment name.
        if not argeval:
            argeval = arg.arg_name

        # If boolean and this is a plain text string, then determine if 'selected' or 'Set'
        if arg.arg_type == "3":
            # Selected
            if the_int_value == "1":
                final_result = argeval + " (selected)" if argeval != "Set" else ",Set"
            # Unselected
            elif argeval == "Set":
                final_result = ",Unset"
            else:
                final_result = ""
        else:
            # If it doesn't have an '=', then. add it.
            if argeval[-1] != "=":
                argeval += "="
            final_result = argeval + the_int_value
    else:
        final_result = argeval + the_int_value

    # Drop trailing comma if necessary
    return drop_trailing_comma([final_result])[0] if final_result else ""


# Extracts and returns the text from the given argument as a string.
def extract_string(action: defusedxml.ElementTree, arg: str, argeval: str) -> str:
    """
    Extracts a string from an XML action element.

    Args:
        action (XML element): The XML action element to search.
        arg (str): The name of the string argument to search for.
        argeval (str): The prefix to add to the matched string.

    Returns:
        str: Extracted string with prefix or an empty string.
    """
    from maptasker.src.action import drop_trailing_comma  # noqa: PLC0415

    # Find the first matching <Str> element with the desired 'sr' attribute
    str_element = next(
        (child for child in action.findall("Str") if child.attrib.get("sr") == arg),
        None,
    )

    if str_element is None or str_element.text is None:
        return ""  # No matching element found

    # Extract text value with prefix
    new_argeval = f"{argeval}=" if argeval[-1] != "=" else argeval
    extracted_text = (
        f"{argeval}(carriage return)" if str_element.text == "\n" else f"{new_argeval}{str_element.text or ''}"
    )

    # Drop trailing comma if necessary
    return drop_trailing_comma([extracted_text])[0] if extracted_text else ""


def tasker_object(text: str, blank_trailer: bool) -> bool:
    """
    Checks if the input string contains any of the following keywords,
    where spaces are replaced with '&nbsp;':
    'Task:&nbsp;', 'Profile:&nbsp;', 'Profile:$nbsp;', or 'Scene:&nbsp;'.

    Args:
        text: The string to be tested.
        blank_trailer: True if keyword followed by space, otherwise followed by '&nbsp;'

    Returns:
        True if any of the modified keywords are found in the text, False otherwise.
    """
    keywords_nbsp = [
        "Task:&nbsp;",
        "Profile:&nbsp;",
        "Profile:$nbsp;",
        "Scene:&nbsp;",
        "Task <a href=#tasks_",
    ]
    if blank_trailer:
        keywords_nbsp = [keyword.replace("&nbsp;", " ") for keyword in keywords_nbsp]
    return any(keyword in text for keyword in keywords_nbsp)


# Given a string, remove all HTML (anything between < >) tags from it
# Precompile regex for maximum performance
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def remove_html_tags(text: str, replacement: str) -> str:
    """
    Remove HTML tags from a string efficiently.
    Keeps strings untouched if they appear to be Tasker/Title text.
    NOTE: Optimized for performance.
    """
    # Skip HTML stripping for specific conditions
    if tasker_object(text, False) or "&nbsp;&nbsp;Title=" in text:
        return text

    # If there's no '<', skip regex completely (fast path)
    if "<" not in text:
        return text

    # Use precompiled regex substitution (C-level speed)
    cleaned = _HTML_TAG_RE.sub(replacement, text)

    # Return cleaned text or replacement if empty
    return cleaned if cleaned.strip() else replacement


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
    with open(file1_path) as file1, open(file2_path, "a") as file2:
        shutil.copyfileobj(file1, file2)


# The XML file has incorrect encoding.  Let's read it in and rewrite it correctly.
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
