"""GUI Map"""

#! /usr/bin/env python3

#                                                                                      #
# guimap: reverse engineer the mapped html file and return just the data as a list.    #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import re

# from maptasker.src.debug import format_line_debug
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import pattern8
from maptasker.src.xmldata import remove_html_tags


def cleanup_text_elements(output_lines: dict, line_num: int) -> dict:
    r"""
    Cleanup all of the text elements in the line by fixing html and other stuff.

    Args:
        output_lines (dict): The dictionary containing the output lines.
        line_num (int): The line number to clean up.

    Returns:
        dict: The updated output_lines dictionary.
    """
    # Replace &nbsp. with " " and "\n\n" with "\n" in all text fields.
    text_list = output_lines[line_num]["text"]
    new_text_list = []
    for text in text_list:
        # Note: we can not replace text in-place since strings are immutable.  So we create a new list.
        temp_text = text.replace("&nbsp;", " ")
        temp_text = temp_text.replace("\n\n", "\n")
        temp_text = remove_html_tags(temp_text, "")
        temp_text = temp_text.replace("<DIV", "")
        temp_text = temp_text.replace("&#45;", "-")  # Hyphen
        temp_text = temp_text.replace("&lt;", "<")
        temp_text = temp_text.replace("&gt;", ">")
        temp_text = temp_text.replace("[Launcher Task:", " [Launcher Task:")  # Add a space
        temp_text = temp_text.replace(" --Task:", "--Task:")  # Scene Task
        new_text_list.append(temp_text)
    if new_text_list:
        output_lines[line_num]["text"] = new_text_list

    return output_lines


def next_key(my_dict: dict, key: int) -> any | bool:
    """
    A function that returns the next key from a dictionary iterator, or False if no key is available.

    Args:
        my_dict: The dictionary to iterate over.
        key: The current key to check for the next key.

    Returns:
        any | bool: The next key from the iterator or False if no key is available.
    """
    keys = iter(my_dict)
    # The following line is flagged as a noop but actually does something.
    key in keys  # noqa: B015
    return next(keys, False)


def eliminate_blanks(output_lines: dict) -> dict:
    """Eliminate leading blanks from the top of the output.

    Args:
        output_lines (dict): dictionary of output lines

    Returns:
        output_lines (dict): dictionary of output lines
    """
    # Eliminate leading blanks.  Care must be taken not to iterate over the list we are modifying.
    # Only botherdr with the first text element in each line.
    keys_to_remove = []
    prev_value = None
    # Build a list of keys that have consequtive blanks.
    for key, value in output_lines.items():
        if (value["text"][0] in ("\n", "    \n")) and (
            prev_value is not None and prev_value["text"][0] in ("\n", "    \n")
        ):
            keys_to_remove.append(key)
        elif value["text"][0] not in ("\n", "    \n"):  # Get out if we have a non-blank line.
            break
        prev_value = value

    # Eliminate remaining (e.g. highlighting) stuff from the remaining couple of lines
    cleanup = True
    while cleanup:
        if "MapTasker\n" in output_lines[key]["text"][0]:
            break
        keys_to_remove.append(key)
        key = next_key(output_lines, key)  # Get the next key

    # Remove the keys
    for key in keys_to_remove:
        del output_lines[key]
    return output_lines


# Capture text and it's colring and highlighting
def coloring_and_highlights(output_lines: str, line: str, line_num: int) -> dict:
    """
    Given a dictionary of output lines, a line of text, and a line number, this function adds color and highlighting information to the output lines.

    Args:
        output_lines (dict): A dictionary of output lines, where each line is represented as a dictionary with keys "color" and "text".
        line (str): The line of text to process.
        line_num (int): The line number of the line.

    Returns:
        dict: The updated output lines dictionary with added color and highlighting information.

    Description:
        This function searches for occurrences of the string "class=" in the given line. For each occurrence, it splits the line starting from that occurrence and extracts the color string. If the color string contains the substring "_color", it adds the color string to the "color" key of the line dictionary in the output lines. It then removes any HTML tags from the text portion of the line and appends it to the "text" key of the line dictionary.

        If the line dictionary already has a color value, the new color value is appended to the existing color list.

        The function returns the updated output lines dictionary.
    """
    color_list = [m.start() for m in re.finditer("class=", line)]
    for color in color_list:
        temp = line[color:].split('"')

        # If we have a color string, then we need to add it to the output lines
        if len(temp) > 1 and "_color" in temp[1]:
            color_to_use = temp[1].split(" ")
            # Grab the color string
            if not output_lines[line_num]["color"]:
                output_lines[line_num]["color"] = [color_to_use[0]]
            else:
                output_lines[line_num]["color"].append(color_to_use[0])

            # If 'conmtinued >>>' is in the text, then we need to get all of the text
            if "continued >>>" in temp[2]:
                continued_start = line.find(">")
                continued_end = line.find("<", continued_start)
                temp[2] = line[continued_start:continued_end]

            # Remove html before appending text
            if temp[2][0] == ">":  # Drop first character if it's a ">"
                temp[2] = temp[2][1:]

            # Get rid of any html tags in the text
            html_start = temp[2].find("</span")
            if html_start != -1:
                temp[2] = temp[2][0:html_start]
            # Remove rest of html tags
            text = remove_html_tags(temp[2], "").replace("<span class=", " ")
            text = text.replace("\n\n", "\n")
            output_lines[line_num]["text"].append(text)

    return output_lines


def additional_formatting(
    doing_global_variables: bool,
    line: str,
    output_lines: dict,
    line_num: int,
    spacing: int,
) -> str:
    """
    Applies special formatting to a given line of text and appends the formatted line to an output list.

    Args:
        doing_global_variables (bool): Whether or not the line contains global variables.
        line (str): The line of text to be formatted.
        output_lines (dict): The dictionary to which the formatted line will be appended.
        line_num (int): The line number of the line in the output dictionary.
        spacing (int): The number of spaces to be inserted at the beginning of the formatted line.

    Returns:
        list: The updated output list.
    """

    # replace "<br>" with "\n"
    line = pattern8.sub("\n", line)

    # Fix icons
    line = line.replace("&#9940;", "⛔")
    line = line.replace("&#11013;", "⫷⇦") if "Entry" in line else line.replace("&#11013;", "⇨⫸")

    # Initialize the output_lines fields
    output_lines[line_num] = {"text": [], "color": []}

    # Capture any text before the first color tags
    color_location = line.find("_color")
    if color_location != -1 and (line[0:6] == "&nbsp;"):
        color_location = line.find("<span class=")
        output_lines[line_num]["text"] = [line[0:color_location]]
        output_lines[line_num]["color"] = ["n/a"]

    # Build coloring
    if "<span class=" in line and "_color" in line:
        # Get the color(s) and highlights
        output_lines = coloring_and_highlights(output_lines, line, line_num)

    # Extract global variable from table definition
    elif line[0:7] == "<tr><td":
        temp1 = line.split('text-align:left">')
        global_var_name = temp1[1].split("<")[0]
        # global_var_name = format_line_debug(global_var_name, 34) # Different kind of formatting
        global_var_value = temp1[2].split("<")[0]
        output_lines[line_num]["text"] = [f"{global_var_name.ljust(25, '.')}{global_var_value.rjust(15, '.')}"]
        # temp_line = f"{global_var_name}{global_var_value}"  # Different kind of formatting
        output_lines[line_num]["color"] = ["Turquoise"]

    # Handle the rest of the lines
    else:
        # Remove all HTML
        temp_line = remove_html_tags(line, "")
        output_lines[line_num]["text"].append(temp_line.replace("Go to top", ""))

    output_lines = cleanup_text_elements(output_lines, line_num)

    # Calculate initial spacer by evaluating the first text file in the list of text
    if (
        output_lines[line_num]["text"][0][0:8] == "Project:"
        or doing_global_variables
        or "Project Global Variables" in output_lines[line_num]["text"][0]
        or output_lines[line_num]["text"][0][0:6] == "Scene:"
    ):
        spacing = 0
    elif output_lines[line_num]["text"][0][0:8] == "Profile:" or output_lines[line_num]["text"][0][0:9] == "TaskerNet":
        spacing = 5
    elif (
        output_lines[line_num]["text"][0][0:5] == "Task:"
        or "--Task:" in output_lines[line_num]["text"][0][0:7]
        or output_lines[line_num]["text"][0][0:11] == "- Project '"
    ):
        spacing = 10
    elif output_lines[line_num]["text"][0][0].isdigit() or " continued >>>" in output_lines[line_num]["text"][0]:
        spacing = 15
    else:
        pass

    # Put it all together with the spacing.
    output_lines[line_num]["text"][0] = f'{spacing*" "}{output_lines[line_num]["text"][0]}'

    return output_lines, spacing


# Formats the output HTML by processing each line of the input list.
def format_output(lines: list, output_lines: dict, spacing: int, iterate: bool) -> list:
    r"""
    Formats the output HTML by processing each line of the input list.

    Args:
        lines (list): A list of lines of HTML code.
        output_lines (dict): A list to store the formatted output.
        spacing (int): The amount of spacing to be added before each line.
        iterate (bool): A flag indicating whether to skip the next line.

    Returns:
        list: The formatted output list.

    Description:
        This function processes each line of the input list and applies specific formatting rules.
        It checks if the line is a table definition and appends a formatted string to the output list.
        It ignores lines containing non-text data and applies special formatting rules based on the line content.

        The function returns the formatted output list.

    """
    doing_global_variables = False
    # Format the html
    for line_num, line in enumerate(lines):
        # If we are to skip the next line, then skip it.
        if iterate:
            iterate = False
            continue

        # Check if the line is a table definition for Unreferenced Global Variables: Name and Value
        if line == "<th>Name</th>\n" and lines[line_num + 1] == "<th>Value</th>\n":
            iterate = True
            output_lines[line_num] = {
                "text": ["Variable Name...............Variable Value"],
                "color": ["turquoise1"],
                "highlight_color": "",
                "highlight_position": "",
            }
            doing_global_variables = True
            continue

        # End of global variables if we hit the end of the table.
        if doing_global_variables and line == "</table><br>\n":
            doing_global_variables = False

        # Ignore non-text data
        if "{color: " in line or "{display: " in line or "padding: 5px;" in line:
            continue

        # Handle special formatting
        output_lines, spacing = additional_formatting(doing_global_variables, line, output_lines, line_num, spacing)

    # Eliminate consequtive blank lines and return our dictionary.
    return eliminate_blanks(output_lines)


def parse_html() -> dict:
    r"""
    Parses the HTML file "MapTasker.html" and formats the content into a list of lines.

    Returns:
        output_lines (dict): A dictionary of formatted lines from the parsed HTML file.

        Dictionary structure:
        output_lines[line_num] = {
            "text": [f"{message}\n, messqage2\n, etc."],
            "color": [color1, color2, color3, etc.],
            "highlight_color": [""],
            "highlight_position": "",
        }
    """
    output_lines = {}
    iterate = False

    # Read the mapped html file
    with open("MapTasker.html") as html:
        lines = html.readlines()

        # Establish base spacing
        spacing = 0

        # Format the html
        output_lines = format_output(lines, output_lines, spacing, iterate)
        lines = []  # No longer need the lines list.
        html.close()

    return output_lines
    # Reorganize the lines
    # return reorganize_lines(output_lines)


def get_the_map() -> dict:
    r"""
    Reads the contents of the "MapTasker.html" file and processes each line to generate a list of cleaned-up lines.

    Returns:
        output_lines (dict): A dictionary of cleaned-up lines from the "MapTasker.html" file.

    This function reads the contents of the "MapTasker.html" file line by line to parse the data.

    The cleaned-up lines are then appended to the `output_lines` and returned as the result.
    """

    output_lines = parse_html()

    PrimeItems.program_arguments["guiview"] = False
    return output_lines
