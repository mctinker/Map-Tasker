"""GUI Map"""

#! /usr/bin/env python3

#                                                                                      #
# guimap: reverse engineer the mapped html file and return just the data as a list.    #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import contextlib
import re

from maptasker.src.maputils import count_consecutive_substr
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import pattern8
from maptasker.src.xmldata import remove_html_tags

glob_spacing = 15


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
    """Eliminate consequtive blanks from the output.

    Args:
        output_lines (dict): dictionary of output lines

    Returns:
        output_lines (dict): dictionary of output lines
    """
    # Eliminate consequtive blanks.  Care must be taken not to iterate over the list we are modifying.
    prev_value = None
    items_to_remove = []
    # Build a list of keys that have consequtive blanks.
    for key, value in output_lines.items():
        # One or more text items in the list.
        new_list = []
        # Igfnore dictionarys.
        with contextlib.suppress(KeyError):
            if value["directory"]:
                prev_value = None
                continue
        for item in value["text"]:
            if item in ("\n", "    \n") and (prev_value is not None and prev_value in ("\n", "    \n")):
                prev_value = item
                continue
            new_list.append(item)
            prev_value = item

        # Update or remove the text list.
        if new_list:
            value["text"] = new_list
        else:
            items_to_remove.append(key)

    # Remove the consequtive blank keys.
    for item in items_to_remove:
        output_lines.pop(item)

    return output_lines


# def remove_html_tags(text, replacement=""):
#     return re.sub(r"<[^>]+>", replacement, text)


def extract_colors(line: str) -> list:
    """
    Extracts the starting positions of all color classes in the given line.

    Args:
        line (str): The line of text to search for color classes.

    Returns:
        list: A list of integers representing the starting positions of all color classes found in the line.
    """
    return [m.start() for m in re.finditer(r'class="([^"]*_color[^"]*)"', line)]


def process_color_string(line: str, color_pos: int) -> tuple:
    """
    Extracts the color string from the given line based on the color position.

    Args:
        line (str): The line containing the color string
        color_pos (int): The starting position of the color string

    Returns:
        tuple: A tuple containing the extracted color string and the split result
    """
    temp = line[color_pos:].split('"')
    if len(temp) > 1:
        return temp[1].split(), temp
    return [], temp


def extract_working_text(temp: list) -> str:
    """
    Extracts the working text from the given list of strings.

    Args:
        temp (list): A list of strings containing HTML tags and text.

    Returns:
        str: The extracted working text, with double newlines replaced by single newlines.
    """
    if temp[2].startswith("><h2><span class=") or temp[2].startswith("><span class="):
        return temp[4].replace("\n\n", "\n")
    return temp[2].replace("\n\n", "\n")


def handle_continued_text(line: str, working_text: str) -> str:
    """
    Extracts the text between "continued >>>" and "<" in the given line and returns it.

    Args:
        line (str): The line of text to search for "continued >>>" and "<".
        working_text (str): The text to search for "continued >>>".

    Returns:
        str: The extracted text between "continued >>>" and "<", or the original working_text if "continued >>>" is not found.
    """
    if "continued >>>" in working_text:
        continued_start = line.find(">")
        continued_end = line.find("<", continued_start)
        return line[continued_start:continued_end]
    return working_text


def remove_html_spans(working_text: str) -> str:
    """
    Removes HTML spans from the working_text and returns the modified text.

    Parameters:
        - working_text (str): The text containing HTML spans to be processed.

    Returns:
        - str: The working_text with HTML spans removed.
    """
    return re.sub(r"</span.*?>", "", working_text.lstrip(">"))


def extract_highlights(working_text: str, highlight_tags: list) -> list:
    """
    Extracts highlights from the working text based on the provided highlight tags.

    Args:
        working_text (str): The text to extract highlights from
        highlight_tags (list): A list of tags to search for in the working text

    Returns:
        list: A list of strings representing the extracted highlights
    """
    name_end_position = working_text.find("</")
    temp_string = working_text[:name_end_position]
    name_start_position = temp_string.rfind(">")
    highlight_name = temp_string[name_start_position + 1 :]

    highlights = []
    for tag, style in highlight_tags.items():
        if tag in working_text[:name_end_position]:
            highlights.append(f"{style},{highlight_name}")
    return highlights


def process_line(output_lines: list, line: str, line_num: int, highlight_tags: list) -> list:
    """
    A function to process a line of text, extract colors, working text, and highlights.

    Parameters:
        - output_lines (list): A list containing the processed output lines.
        - line (str): The input line of text to process.
        - line_num (int): The line number corresponding to the input line.
        - highlight_tags (list): A list of highlight tags to be applied to the text.

    Returns:
        - list: The updated output lines list after processing the input line.
    """
    color_list = extract_colors(line)
    previous_line = ""

    for color_pos in color_list:
        # Break up line into color and text (temp)
        color_to_use, temp = process_color_string(line, color_pos)

        if color_to_use:
            color = color_to_use[0]
            if "_color" in color:
                # Get the text
                working_text = extract_working_text(temp)
                # Special handling if a Tasker preferencews key.
                if PrimeItems.program_arguments["preferences"] and (
                    "Key Service Account" in temp[2] or "Google Cloud Firebase" in temp[2]
                ):
                    working_text = line.split('preferences_color">')[1]

                # Ignore duplicate lines due to multiple colors and only one text item.
                if working_text == previous_line:
                    continue
                previous_line = working_text
                working_text = handle_continued_text(line, working_text)
                working_text = remove_html_spans(working_text)

                # Get the color
                if line_num not in output_lines:
                    output_lines[line_num] = {"color": [], "text": [], "highlights": []}
                output_lines[line_num]["color"].append(color)

                if color_pos == color_list[0]:
                    highlights = extract_highlights(working_text, highlight_tags)
                    if "highlights" in output_lines[line_num]:
                        output_lines[line_num]["highlights"].extend(highlights)
                    else:
                        output_lines[line_num]["highlights"] = highlights

                raw_text = remove_html_tags(working_text, "").replace("<span class=", " ").replace("\n\n", "\n")

                # Indicate a directory header
                if (
                    "Projects..........................." in raw_text
                    or "Profiles..........................." in raw_text
                    or "Tasks..........................." in raw_text
                ):
                    raw_text = f"\nn{raw_text}"

                output_lines[line_num]["text"].append(raw_text)

    return output_lines


def coloring_and_highlights(output_lines: list, line: str, line_num: int) -> list:
    """
    Given a dictionary of output lines, a line of text, and a line number, this function adds color and highlighting
    information to the output lines.

    Args:
        output_lines (dict): A dictionary of output lines, where each line is represented as a dictionary with
        keys "color" and "text".
        line (str): The line of text to process.
        line_num (int): The line number of the line.

    Returns:
        output_lines (dict): The updated output lines dictionary with added color and highlighting information.
    """
    highlight_tags = {
        "<b>": "bold",
        "<em>": "italic",
        "<u>": "underline",
        "<mark>": "mark",
    }
    return process_line(output_lines, line, line_num, highlight_tags)


def calculate_spacing(
    spacing: int,
    output_lines: dict,
    line_num: int,
    doing_global_variables: bool,
    previous_line: str,
) -> int:
    """
    Calculate initial spacer based on specific conditions.

    Args:
        spacing (int): The initial spacing value.
        output_lines (dict): Dictionary containing output lines.
        line_num (int): The line number.
        doing_global_variables (bool): Indicates if global variables are present.
        previous_line (str): The previous line of text.

    Returns:
        int: The calculated spacing value.
    """

    text = output_lines[line_num]["text"][0]

    if text.startswith(("Project:", "Scene:")) or doing_global_variables or "Project Global Variables" in text:
        return 0

    if text.startswith(("Profile:", "TaskerNet")):
        return 5

    if text.startswith(("Task:", "- Project '")) or "--Task:" in text[:7]:
        return 10

    # Handle dangling Task action parameters
    if ("Configuration Parameter(s):" in previous_line or "Timeout=" in text) and PrimeItems.program_arguments[
        "pretty"
    ]:
        # Cleanup "Timeout=" parameter of Task action
        if "Timeout=" in text:
            temp = output_lines[line_num]["text"][0].replace(" Timeout=", "Timeout=")
            output_lines[line_num]["text"][0] = temp
            return count_consecutive_substr(previous_line, "&nbsp;") + spacing
        return 61
    # Add spacing for "Structure Output (JSON, etc)"
    if "Timeout=" in previous_line and "Structure Output (JSON, etc)" in text:
        output_lines[line_num]["text"][0] = "Structure Output (JSON, etc)\n"
        return spacing
    # Add spacing for "[Continue Task After Error])"
    if "[Continue Task After Error]" in text:
        output_lines[line_num]["text"][0] = "[Continue Task After Error]\n"
        previous_formatted_line = output_lines[line_num - 1]["text"][0]
        return len(previous_formatted_line) - len(previous_formatted_line.lstrip())

    if spacing == 61:
        return 15

    if text[0].isdigit() or " continued >>>" in text:
        return 15

    return spacing


def additional_formatting(
    doing_global_variables: bool,
    line: str,
    output_lines: dict,
    line_num: int,
    spacing: int,
    previous_line: str,
) -> tuple:
    """
    Applies special formatting to a given line of text and appends the formatted line to an output list.

    Args:
        doing_global_variables (bool): Whether or not the line contains global variables.
        lines (list): A list of lines of HTML code.
        line (str): The line of text to be formatted.
        output_lines (dict): The dictionary to which the formatted line will be appended.
        line_num (int): The line number of the line in the output dictionary.
        spacing (int): The number of spaces to be inserted at the beginning of the formatted line.
        last_line (str): The previous line of the output list.

    Returns:
        tuple: output_lines and spacing.
    """

    line = pattern8.sub("\n", line)

    # Fix icons
    line = line.replace("&#9940;", "⛔")
    line = line.replace("&#11013;", "⫷⇦") if "Entry" in line else line.replace("&#11013;", "⇨⫸")

    output_lines[line_num] = {"text": [], "color": []}

    # Capture any text before the first color tags
    color_location = line.find("_color")
    if color_location != -1 and line.startswith("&nbsp;"):
        color_location = line.find("<span class=")
        output_lines[line_num]["text"] = [line[:color_location]]
        # Assign the last color used as the default color
        for output_line_num in reversed(output_lines):
            if output_lines[output_line_num]["color"]:
                output_lines[line_num]["color"] = [output_lines[output_line_num]["color"][-1]]
                break

    # Build coloring
    if "<span class=" in line and "_color" in line:
        output_lines = coloring_and_highlights(output_lines, line, line_num)

    # Extract global variable from table definition
    elif line.startswith("<tr><td"):
        temp1 = line.split('text-align:left">')
        global_var_name = temp1[1].split("<")[0]
        global_var_value = temp1[2].split("<")[0]
        output_lines[line_num]["text"] = [f"{global_var_name.ljust(25, '.')}{global_var_value.rjust(15, '.')}"]
        output_lines[line_num]["color"] = ["Turquoise"]

    # Handle the rest of the lines
    else:
        temp_line = remove_html_tags(line, "")
        output_lines[line_num]["text"].append(temp_line.replace("Go to top", ""))
        if doing_global_variables:
            spacing = glob_spacing

    output_lines = cleanup_text_elements(output_lines, line_num)

    # If [⛔ DISABLED] is in the line for a Profile, then move it up to the profile line and blank out the original.
    if (
        "[⛔ DISABLED]" in output_lines[line_num]["text"][0]
        and output_lines[line_num - 1]["color"][0] == "profile_color"
        and output_lines[line_num - 1]["text"][1] == "\n"
    ):
        output_lines[line_num - 1]["text"][1] = "  [⛔ DISABLED]\n"
        # This blank line will be ignored by guiwins.py output_map_text_lines
        output_lines[line_num]["text"][0] = " "
        output_lines[line_num]["color"] = {}

    spacing = calculate_spacing(spacing, output_lines, line_num, doing_global_variables, previous_line)

    output_lines[line_num]["text"][0] = f'{spacing * " "}{output_lines[line_num]["text"][0]}'

    return output_lines, spacing


def add_directory_entry(temp: list, output_lines: dict, line_num: int) -> dict:
    """
    Adds a directory entry to the output lines dictionary.

    Args:
        temp (list): A list containing the directory information.
        output_lines (dict): A dictionary containing the output lines.
        line_num (int): The line number.

    Returns:
        output_lines (dict): The updated output lines dictionary.

    """
    # Ignore garbage
    if temp[1] == "</td>\n":
        return output_lines

    # Get the tasker object type (projects, profiles, tasks, scenes)
    tasker_type = temp[1].split("_")[0]
    tasker_type = tasker_type.replace("<a href=#", "")

    # Get the object name
    name = temp[1].split("<a href=#")[1]
    name = name.split("</a")[0]
    name = name.split(">")[1]
    # If name is blank, then the name has ">>" in it (double ">")
    if name == "":
        newname = temp[1].split(">>")
        name = newname[2].split("</a>")[0].lstrip()

    # Add the directory entry
    output_lines[line_num] = {"directory": [tasker_type, name], "text": [], "color": []}
    return output_lines


def ignore_line(line: str) -> bool:
    """
    Check if a given line of HTML should be ignored.

    Args:
        line (str): The line of HTML to check.

    Returns:
        bool: True if the line should be ignored, False otherwise.
    """
    text_to_ignore = [
        "<style>",
        "<tr> ",
        "<table>",
        "<td></td>",
        "<a id=",
        "Trailing Information...",
        "Scenes",
        "mark {",
        "background-color: ",
        "{color: ",
        "padding: 5px;",
        "{display: ",
    ]
    # Ignore certain lines
    return any(ignore_str in line for ignore_str in text_to_ignore)


# Loop through html and format ourput
def process_html_lines(lines: list, output_lines: list, spacing: int, iterate: bool) -> list:
    """
    Processes HTML lines and adds them to the output_lines list.

    Args:
        lines (list): A list of HTML lines to be processed.
        output_lines (list): A list to store the processed lines.
        spacing (int): The spacing value for formatting.
        iterate (bool): A flag indicating whether to iterate through the lines.

    Returns:
        list: The updated output_lines list.

    Description:
        This function processes a list of HTML lines and adds them to the output_lines list. It performs the following tasks:
        - Ignores certain lines.
        - Processes directory entries.
        - Ignores non-text data.
        - Handles special formatting.
        - Validates the profile name.

        The function modifies the output_lines list in place.
    """
    doing_global_variables = False
    previous_line = ""

    # Reformat the html by going through each line
    for line_num, line in enumerate(lines):
        # Ignore certain lines
        if ignore_line(line):
            continue

        # Process directory entries
        if "<td>" in line:
            temp = line.split("<td>")
            output_lines = add_directory_entry(temp, output_lines, line_num)
            iterate = True

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
                "highlight_color": [],
                "highlights": [],
                "directory": [],
            }
            doing_global_variables = True
            continue

        # End of global variables if we hit the end of the table.
        if doing_global_variables and line == "</table><br>\n":
            doing_global_variables = False
            spacing = 0
            continue

        # Handle special formatting
        output_lines, spacing = additional_formatting(
            doing_global_variables,
            line,
            output_lines,
            line_num,
            spacing,
            previous_line,
        )
        previous_line = line

        # Validate Profile name.  If no name then say so.
        if "Profile:" in line and output_lines[line_num]["text"][0] == "     Profile: \n":
            output_lines[line_num]["text"][0] = "     Profile: (no name)\n"

    return output_lines


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

    # Format the lines in the html
    output_lines = process_html_lines(lines, output_lines, spacing, iterate)

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
            "highlights": [highlight, string],
        }
    """
    output_lines = {}
    iterate = False
    # PrimeItems.tab_table = {}  # Tabs table

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
