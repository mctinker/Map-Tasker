#! /usr/bin/env python3
"""GUI Map"""

#                                                                                      #
# guimap: reverse engineer the mapped html file and return just the data as a list.    #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import re
from html.parser import HTMLParser

from maptasker.src.error import rutroh_error
from maptasker.src.guiutils import align_text
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import pattern8
from maptasker.src.xmldata import remove_html_tags

glob_spacing = 15


# Optimized
def handle_gototop(text_list: list) -> list:
    """
    This function handles the addition of a 'Go to top' string in a given text.

    It checks for specific items in the text and replaces the newline character with 'Go to top' followed by a newline.

    Parameters:
        text_list (list): The input text list to be processed.

    Returns:
        text_list (list): The modified text with 'Go to top' added if the conditions are met.
    """
    gototop_items = {"CAVEATS:", "Profile:", "Task:"}
    gototop = "          Go to top"

    # Check if any of the gototop_items exist in the first element of the list
    if any(item in text_list[0] for item in gototop_items) and "Task: Properties" not in text_list[0]:
        # Replace the last newline character with "Go to top" + newline
        text_list[-1] = text_list[-1].replace("\n", f"{gototop}\n", 1)

    return text_list


class MLStripper(HTMLParser):
    """
    A class to strip HTML tags from a string.

    This class extends the HTMLParser class and overrides the handle_data method to collect data
    between HTML tags. The collected data can be retrieved using the get_data method.
    """

    def __init__(self) -> None:
        """
        Initializes the MLStripper class.
        """
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d: str) -> None:
        """
        Overrides the handle_data method to collect data between HTML tags.

        Args:
            d (str): The data between HTML tags.
        """
        self.fed.append(d)

    def get_data(self) -> str:
        """
        Retrieves the collected data between HTML tags.

        Returns:
            str: The collected data as a single string.
        """
        return "".join(self.fed)


def remove_the_html_tags(text: str) -> str:
    """
    Removes HTML tags from the given text.

    Args:
        text (str): The input text containing HTML tags.

    Returns:
        str: The text with HTML tags removed.
    """
    s = MLStripper()
    s.feed(text)
    return s.get_data()


# Optimized
def cleanup_text_elements(output_lines: dict, line_num: int, remove_html: bool) -> list:
    """
    Cleanup all of the text elements in the line by fixing html and other stuff.

    Args:
        output_lines (list): The dictionary containing the output lines.
        line_num (int): The line number to clean up.
        remove_html (bool): A flag indicating whether to remove HTML tags.

    Returns:
        dict: The updated output_lines dictionary.
    """
    tabs = f"{' ' * 4}"
    text_list = output_lines[line_num]["text"]
    # If nothing, just return.
    if not text_list:
        return output_lines

    text_list = handle_gototop(text_list)

    # Special handling for 'Task xxx has too many actions'.
    # We don't want to strip the html from the Task name.
    # Catch the '>' break before the &gt;' gets replaced.
    too_many_pos = text_list[0].find("Task <a href=#tasks")
    if too_many_pos != -1:
        # Find the first ">"
        break_pos = text_list[0].find(">")
        if break_pos != -1:
            # Remove everything before the first ">"
            text_list[0] = f"Task {text_list[0][break_pos + 1 :].replace('</a>', '')}"
            remove_html = False
        else:
            rutroh_error(f"guimap error: '{text_list[0]}' missing '>'!")

    # Use list comprehension for better performance
    new_text_list = [
        text.replace("&nbsp;", " ")
        .replace("\n\n", "\n")
        .replace("<DIV", "")
        .replace("&#45;", "-")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("[Launcher Task:", " [Launcher Task:")
        .replace(" --Task:", "--Task:")
        .replace("\t", tabs)
        for text in text_list
    ]

    # Remove all the html from the text
    if remove_html:
        new_text_list = [remove_the_html_tags(text) for text in new_text_list]

    if new_text_list:
        output_lines[line_num]["text"] = new_text_list

    return output_lines


# Optimized
def eliminate_blanks(output_lines: dict) -> dict:
    """Eliminate consecutive blank lines from the output.

    Args:
        output_lines (dict): dictionary of output lines

    Returns:
        output_lines (dict): dictionary of output lines
    """
    blank_lines = {"", "    \n"}

    for key, value in output_lines.items():
        try:
            if value["directory"]:
                continue  # Skip directories
        except KeyError:
            pass

        prev_value = None
        new_text_list = []
        for item in value["text"]:
            if item in blank_lines and prev_value in blank_lines:
                continue
            new_text_list.append(item)
            prev_value = item

        if new_text_list:
            value["text"] = new_text_list
        else:
            output_lines.pop(key)

    return output_lines


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
    highlights = []
    # Search for highlight in string, and if found, get the highlight object's name and return it.
    for tag, style in highlight_tags.items():
        if tag in working_text:
            tag_name = tag.split(">")[0]
            end_tag = f"</{tag_name[1:]}>"
            work_name = working_text.split(tag)
            highlight_name = work_name[1].split(end_tag)[0]
            highlights.append(f"{style},{highlight_name}")

    return highlights


def process_line(
    output_lines: list,
    line: str,
    line_num: int,
    highlight_tags: list,
) -> list:
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

                # If this is the first color in the list, then extract highlights.
                if color_pos == color_list[0]:
                    highlights = extract_highlights(working_text, highlight_tags)
                    if "highlights" in output_lines[line_num]:
                        output_lines[line_num]["highlights"].extend(highlights)
                    else:
                        output_lines[line_num]["highlights"] = highlights

                # Remove HTML tags and replace with spaces
                raw_text = remove_html_tags(working_text, "").replace("<span class=", " ").replace("\n\n", "\n")

                # Indicate a directory header
                if (
                    "Projects..........................." in raw_text
                    or "Profiles..........................." in raw_text
                    or "Tasks..........................." in raw_text
                    or "Scenes..........................." in raw_text
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
) -> int:
    """
    Calculates the spacing for a given line of text in the output lines dictionary.

    Args:
        spacing (int): The initial spacing value.
        output_lines (dict): A dictionary of output lines.
        line_num (int): The line number of the line being processed.
        doing_global_variables (bool): A flag indicating if global variables are being processed.
        previous_line (str): The text of the previous line.

    Returns:
        int: The calculated spacing value.
    """
    text = output_lines[line_num]["text"][0]

    # Direct returns for common conditions
    if doing_global_variables or text.startswith(("Project:", "Scene:")):
        return 0

    if any(keyword in text for keyword in ("Project Global Variables", "Unreferenced Global Variables")):
        return 0

    if text.startswith(("Profile:", "TaskerNet")):
        return 5

    if text.startswith(("Task:", "- Project '", "   The following Tasks in Project ")) or "--Task:" in text[:7]:
        return 7 if text.startswith("   The following Tasks in Project ") else 10

    # General spacing conditions
    if spacing == 61 or (text and text[0].isdigit()) or " continued >>>" in text:
        return 15

    # Default spacing
    return spacing


def handle_disabled_objects(output_lines: list, line_num: int) -> list:
    """
    Handles disabled objects in the output lines.

    This function checks for the presence of "[⛔ DISABLED]" in the output lines and moves it up to the profile line if found.
    It also blanks out the original line.

    Args:
        output_lines (list): A list of output lines.
        line_num (int): The current line number.

    Returns:
        list: The updated output lines.
    """
    # Find the previous output line in prep for checking disabled.
    prev_line_num = line_num - 1
    keep_going = True
    while keep_going:
        try:
            if output_lines[prev_line_num]:
                keep_going = False
                break
        except KeyError:
            prev_line_num -= 1
            if prev_line_num < 0:
                prev_line_num = 0
                break

    # If [⛔ DISABLED] is in the line for a Profile, then move it up to the profile line and blank out the original.
    if (
        "[⛔ DISABLED]" in output_lines[line_num]["text"][0]
        and output_lines[prev_line_num]["color"] == ["profile_color"]
        and output_lines[prev_line_num]["text"][1] == "\n"
    ):
        output_lines[prev_line_num]["text"][1] = "  [⛔ DISABLED]\n"
        # This blank line will be ignored by guiwins.py output_map_text_lines
        output_lines[line_num]["text"][0] = " "
        output_lines[line_num]["color"] = {}
    return output_lines


def capture_front_text(output_lines: list, line: str, line_num: int) -> list:
    """
    Captures the front text from a given line and updates the output lines with the extracted text and default color.

    Parameters:
        output_lines (list): A list of output lines.
        line (str): The line from which to capture the front text.
        line_num (int): The line number in the output lines.

    Returns:
        list: The updated output lines with the extracted text and default color.
    """
    color_location = line.find("<span class=")
    output_lines[line_num]["text"] = [line[:color_location]]
    # Assign the last color used as the default color
    for output_line_num in reversed(output_lines):
        if output_lines[output_line_num]["color"]:
            output_lines[line_num]["color"] = [
                output_lines[output_line_num]["color"][-1],
            ]
            break
    return output_lines


def additional_formatting(
    doing_global_variables: bool,
    line: str,
    output_lines: dict,
    line_num: int,
    spacing: int,
    remove_html: bool,
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
        remove_html (bool): Whether or not to remove HTML tags from the line.

    Returns:
        tuple: output_lines and spacing.
    """
    line = pattern8.sub("\n", line)

    # Correct bad class statement
    line = line.replace("class='\\blanktab1\\'", "class='blanktab1'")

    # Correct icons
    line = line.replace("&#9940;", "⛔")
    line = line.replace("&#11013;", "⫷⇦") if "Entry" in line else line.replace("&#11013;", "⇨⫸")

    output_lines[line_num] = {"text": [], "color": []}

    # Capture any text before the first color tags
    color_location = line.find("_color")
    if color_location != -1 and line.startswith("&nbsp;"):
        output_lines = capture_front_text(output_lines, line, line_num)

    # Build coloring
    if "<span class=" in line and "_color" in line:
        output_lines = coloring_and_highlights(output_lines, line, line_num)

    # Extract global variable from table definition
    elif line.startswith("<tr><td"):
        temp1 = line.split('text-align:left">')
        global_var_name = temp1[1].split("<")[0]
        temp2 = temp1[2].split("<")
        global_var_value = temp2[0] if temp2[0] else temp2[1][3:]
        output_lines[line_num]["text"] = [
            f"{global_var_name.ljust(25, '.')}{global_var_value.rjust(15, '.')}",
        ]
        output_lines[line_num]["color"] = ["Turquoise"]

    # Handle the rest of the lines
    else:
        temp_line = remove_html_tags(line, "")
        output_lines[line_num]["text"].append(temp_line.replace("Go to top", ""))
        if doing_global_variables:
            spacing = glob_spacing

    output_lines = cleanup_text_elements(output_lines, line_num, remove_html)

    # Handle disabled objects
    output_lines = handle_disabled_objects(output_lines, line_num)
    # Determine how much spacing to add to the front of the line.
    spacing = calculate_spacing(
        spacing,
        output_lines,
        line_num,
        doing_global_variables,
    )
    output_lines[line_num]["text"][0] = f"{spacing * ' '}{output_lines[line_num]['text'][0]}"

    return output_lines, spacing


def parse_name(input_string: str) -> str:
    """
    Parses out the desired name from the input string by splitting based on '>'.

    Parameters:
        input_string (str): The string to parse.

    Returns:
        str or None: The extracted name if found, else None.
    """
    # Split the string by '>'
    parts = input_string.split(">")

    # Debug: Show the split parts
    # print(f"Split parts: {parts}")

    # Check if there are enough parts to extract the name
    if len(parts) < 3:
        print("Not enough parts to extract the name.")
        return None

    if parts[2] == "</td":
        return parts[1].split("</a")[0]

    # The desired name is after the second '>'
    # Join the remaining parts in case there are multiple '>' in the name
    return ">".join(parts[2:]).strip()


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

    # Get the tasker object name and type (projects, profiles, tasks, scenes)
    name = parse_name(temp[1]).replace("</a></td>", "")
    start_pos = temp[1].find("#")
    end_pos = temp[1].find("_", 1)
    tasker_type = temp[1][start_pos + 1 : end_pos]

    # Add the directory entry
    if name is not None:
        output_lines[line_num] = {
            "directory": [tasker_type, name],
            "text": [],
            "color": [],
        }
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
        # "<style>",
        "<tr>",
        "<table>",
        "<td></td>",
        "<a id=",
        "Trailing Information...",
        "mark {",
        "background-color: ",
        "{color: ",
        "padding: 5px;",
        "{display: ",
        "></span><!doctype html>\n",
    ]
    # Ignore certain lines
    return any(ignore_str in line for ignore_str in text_to_ignore)


# Loop through html and format ourput
def process_html_lines(
    lines: list,
    output_lines: list,
    spacing: int,
    iterate: bool,
) -> list:
    """
    Processes HTML lines and adds them to the output_lines list.

    Args:
        lines (list): A list of HTML lines to be processed.
        output_lines (list): A list to store the processed lines.
        spacing (int): The spacing value for formatting.
        iterate (bool): A flag indicating whether to iterate through the lines.

    Returns:
        list: The updated output_lines list.
    """
    doing_global_variables = False
    remove_html = True

    for line_num, line in enumerate(lines):
        # Ignore lines that match the criteria
        if ignore_line(line) and not doing_global_variables:
            continue

        # Process directory entries
        if "<td>" in line:
            output_lines = add_directory_entry(
                line.split("<td>"),
                output_lines,
                line_num,
            )
            iterate = True
            continue

        # Skip processing if flagged
        if iterate:
            iterate = False
            continue

        # Handle Unreferenced Global Variables table
        if line == "<th>Name</th>\n" and line_num + 1 < len(lines) and lines[line_num + 1] == "<th>Value</th>\n":
            output_lines[line_num] = {
                "text": ["Variable Name...............Variable Value"],
                "color": ["turquoise1"],
                "highlight_color": [],
                "highlights": [],
                "directory": [],
            }
            doing_global_variables = True
            iterate = True
            continue

        # End of global variables table
        if doing_global_variables and line == "</table><br>\n":
            doing_global_variables = False
            spacing = 0
            continue

        # Reset spacing if this is a Scene element
        if "Element of type" in line:
            spacing = 0

        # If we are doing html such as from a screen WebElement or variable set, then provide appropriate spacing.
        if not remove_html:
            line = align_text(line, 30)  # noqa: PLW2901

        # Check for valid lines in which we don't want to remove the html...
        # Lines with imbedded html text from scripts and too many task action lines.
        if "!DOCTYPE" in line or "&lt;style&gt;" in line or "&lt;script" in line:
            remove_html = False

        # Apply additional formatting
        output_lines, spacing = additional_formatting(
            doing_global_variables,
            line,
            output_lines,
            line_num,
            spacing,
            remove_html,
        )

        # If at end of valid html, start removing html again
        if "/html" in line or "<div <span" in line:
            remove_html = True

        # Validate and update profile name if missing
        if "Profile:" in line:
            current_text = output_lines[line_num].get("text", [""])[0]
            if current_text == "     Profile: \n":
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

    # Read the mapped html file
    with open("MapTasker.html", encoding="utf8") as html:
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

    # PrimeItems.program_arguments["guiview"] = False
    return output_lines
