"""Utilities used by diagram.py."""

#! /usr/bin/env python3
#                                                                                      #
# diagutil: Utilities used by diagram.py.                                              #
#                                                                                      #
# Traverse our network map and print out everything in connected boxes.                #
#                                                                                      #
from __future__ import annotations

import re
from string import printable
from tkinter import font

from maptasker.src.diagcnst import (
    angle,
    bar,
    blank,
    box_line,
    down_arrow,
    left_arrow,
    left_arrow_corner_down,
    left_arrow_corner_up,
    line_right_arrow,
    right_arrow,
    right_arrow_corner_down,
    right_arrow_corner_up,
    straight_line,
    task_delimeter,
    up_arrow,
)
from maptasker.src.nameattr import get_tk
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import icon_pattern

arrows = f"{down_arrow}{up_arrow}{left_arrow}{right_arrow}{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}"
directional_arrows = f"{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}{up_arrow}{down_arrow}"

# Define additional "printable" characters to allow.
# extra_cars: set[str] = set(f"│└─╔═║╚╝╗▶◄{arrows}")
# List of printable ASCII characters
# printable_chars: set[str] = set(string.printable)
# printable_chars = printable_chars.union(extra_cars)
# icon_regex = re.compile(r"\s*[\U0001F300-\U0001F7FF]\s*")


# Add line to our output queue.
def add_output_line(line: str) -> None:
    """
    Adds a line to the output of the netmap report
    Args:
        line (str): The line to add to the output
    Returns:
        None: Does not return anything
    - Appends the given line to the netmap_output list
    - This list contains all the lines that will be written to the final output file
    - By adding lines here they will be included in the generated netmap report
    - The lines are collected and then later joined with newlines and written to the file"""
    PrimeItems.netmap_output.append(line)


# Given an array of 3 string elements, format them with fillers for headings
def include_heading(header: str, output_lines: list) -> None:
    """
    Adds a header to the output lines.
    Args:
        header: The header text to add
        output_lines: The list of output lines
    Returns:
        None: Does not return anything
    - Creates a filler line of "-" characters the same length as the header
    - Replaces the first line of output_lines with the filler line
    - Replaces the second line of output_lines with the header
    - Replaces the third line of output_lines with the filler line
    """
    filler = f"{blank * len(header)}"
    output_lines[0] = f"{filler}{output_lines[0]}"
    output_lines[1] = f"{header}{output_lines[1]}"
    output_lines[2] = f"{filler}{output_lines[2]}"


# Given a list of 3 text elements, print them.
def print_3_lines(lines: list) -> None:
    """
    Prints 3 lines from a list of items
    Args:
        lines: List of line numbers to print
    Returns:
        None: Does not return anything
    - Check if lines is a list
    - Loop through first 3 items of lines list
    - Print corresponding item from PrimesItems.netmap_output
    """
    do_list = isinstance(lines, list)
    for line in range(3):
        if do_list:
            add_output_line(lines[line])
        else:
            add_output_line(line)


# Given a list of text strings, print all of them.
def print_all(lines: list) -> None:
    """
    Print all lines in a list
    Args:
        lines: List of lines to print
    Returns:
        None: No return value
    - Iterate through each line in the lines list
    - Call add_output_line function to print each line
    - No return value as function has side effect of printing lines"""
    for line in lines:
        add_output_line(line)


def count_cjk_characters(string: str) -> int:
    """
    Count the number of Chinese/Japanese/Korean characters in a string.

    Args:
        string (str): The input string to check.

    Returns:
        int: The number of Chinese characters in the string.
    """
    return len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", string))


# Given a text string and title, enclose them in a box and print the box.
def print_box(name: str, title: str, indent: int) -> None:
    """
    Given a text string and title, enclose them in a box and print the box.

    Args:
        name: Name to display in the box
        title: Title to display before the name
        indent: Number of blanks for indentation of the box
        counter: Counter to display after the box
    Returns:
        None: Does not return anything, just prints to console
    Processing Logic:
        - Creates a filler string with given number of blanks for indentation
        - Creates a full name string by joining title and name
        - Initializes a box with top, middle and bottom lines
        - Prints the primary items, box lines with indentation
        - Does not return anything, just prints to console
    """
    # Handle Chinese, Korean and Japanese characters.
    chinese_char_count = count_cjk_characters(name)
    if chinese_char_count > 0:
        adder_space_boxline = f"{blank * (((chinese_char_count) // 2) + 1)}"
        adder_space_name = f"{blank * (((chinese_char_count) // 2) - 1)}"
    else:
        adder_space_boxline = ""
        adder_space_name = ""

    blanks = f"{blank * 5}"
    filler = f"{blanks * indent}"
    full_name = f"{title} {name}{adder_space_name}"
    box = ["", "", ""]
    box[0] = f"{filler}╔═{box_line * (len(full_name) + len(adder_space_boxline))}═╗"  # Box top
    box[1] = f"{filler}║ {full_name} ║"  # Box middle
    box[2] = f"{filler}╚═{box_line * (len(full_name) + len(adder_space_boxline))}═╝"  # Box bottom
    print_3_lines(box)


# Get the dimensions of a text string using tkinter to calculate the width needed.
def width_and_height_calculator_in_pixel(
    txt: str,
    fontname: str,
    fontsize: int,
) -> list:
    """
    Calculates the width and height of the given text in pixels.

    Args:
        txt: The text to calculate the width and height for.
        fontname: The name of the font to be used.
        fontsize: The size of the font in points.

    Returns:
        A list containing the width and height of the text in pixels.

    Examples:
        >>> width_and_height_calculator_in_pixel("Hello", "Arial", 12)
        [30, 16]
    """
    # Get the Tkinter window
    get_tk()
    the_font = font.Font(family=fontname, size=fontsize)
    return [the_font.measure(txt), the_font.metrics("linespace")]


# We have an icon in our name.  Remove any padding as necessary
def fix_icon(name: str) -> str:
    """
    Fixes icon characters in a name string.
    Args:
        name: The name string to fix icons in
    Returns:
        trailer: The fixed name string with icons handled
    - Check each character in the name for icon characters
    - If an icon character is found, initialize Tkinter
    - Calculate the width and height of the icon character
    - Return an empty string or a blank string trailer depending on if the icon is wider or taller
    """
    # We have at least one character that is probably an icon.
    for char in name:
        if char.strip() and set(char).difference(printable):
            # tkframe = PrimeItems.tkroot.frame()  # Initialize Tkinter
            # We have the icon.
            char_dimension = width_and_height_calculator_in_pixel(
                char,
                "Courier New",
                12,
            )
            trailer = "" if char_dimension[0] > char_dimension[1] else blank
            break
    return trailer


# Remove a character from a string at a specific location and return the modified
# string.
def remove_char(text: str, index: int) -> str:
    """
    Remove character from string at given index and return modified string

    Args:
        text (str): The input string
        index (int): The index to remove the character at

    Returns:
        str: String with character removed at given index
    """
    if text[:index].endswith(
        "]",
    ):  # If we hit a close bracket (valid char), don't truncate it.
        return text[: index + 1] + text[index + 1 :]
    return text[:index] + text[index + 1 :]


def count_icons(text: str) -> int:
    # Define a regex pattern for icons (emojis and symbols)
    """
    Count the number of icons in the text string.

    Args:
        text (str): The input string

    Returns:
        int: The number of icons in the text string

    Icons are defined as any character in the following Unicode ranges:

    - Emoticons, Transport & Map Symbols (U0001F300-U0001F5FF)
    - Emoticons (U0001F600-U0001F64F)
    - Transport & Map Symbols (U0001F680-U0001F6FF)
    - Alchemical Symbols (U0001F700-U0001F77F)
    - Geometric Shapes Extended (U0001F780-U0001F7FF)
    - Supplemental Arrows-C (U0001F800-U0001F8FF)
    - Supplemental Symbols and Pictographs (U0001F900-U0001F9FF)
    - Chess Symbols (U0001FA00-U0001FA6F)
    - Symbols and Pictographs Extended-A (U0001FA70-U0001FAFF)

    This function returns the count of all characters in the input string
    that match any of these ranges.
    """
    return len(icon_pattern.findall(text))


# If an icon is found in the string passed in, remove it and return modified string.
def remove_icon(text: str) -> str:
    """
    Remove any icon characters from a string

    Args:
        text (str): The input string

    Returns:
        str: The string with icon characters removed
    """

    # If no arrow found in text, just return the line as is.
    arrow_position: int = next(
        (text.index(char) for char in arrows + bar if char in text),
        0,
    )
    if arrow_position == 0:
        return text

    # Remove a blank for every icon found on line with an arrow.
    output: str = text

    # If there are icons in the text...
    icon_count = count_icons(text)

    # Handle Chinese, Korean and Japanese characters.
    cjk_count = count_cjk_characters(text)
    icon_count += cjk_count // 2

    if icon_count > 0:
        got_it = False
        for _ in range(icon_count):
            # Drop here if there is at least one icon.  This will handle a single icon.
            for find_arrow in directional_arrows + bar:
                found_arrow = text.find(find_arrow)
                if found_arrow != -1:
                    # Remove the icon return the modified string
                    text = remove_char(text, found_arrow - 1)
                    got_it = True
                    if cjk_count == 0:
                        break
                    # Make an effort to deal with chinese/etc.
                    if find_arrow == bar:
                        found_arrow = text.find(find_arrow, found_arrow + 1)
                        if found_arrow != -1:
                            # Remove the icon return the modified string
                            text = remove_char(text, found_arrow - 1)
                    # break
        if got_it:
            return text

        # No arrows/bars found.  Just remove the first icon.
        output = text[: arrow_position - icon_count] + text[arrow_position:]

    return output


# Given a name, enclose it in a text box
def build_box(name: str, output_lines: list) -> tuple:
    """
    Builds a box around the given name.
    Args:
        name: The name to put in the box in one line
        counter: Counter variable in one line
        output_lines: Lines of output text in one line
    Returns:
        output_lines, position_for_anchor: Updated output lines and anchor position in one line
    Processing Logic:
    - Strips whitespace from name
    - Deals with icons in name
    - Builds top and bottom box lines
    - Adds box lines to output
    - Calculates anchor position
    """
    name = name.rstrip()

    # Handle Chinese, Korean and Japanese characters.
    chinese_char_count = count_cjk_characters(name)
    if chinese_char_count > 0:
        adder_space_boxline = f"{blank * (((chinese_char_count) // 2) + 2)}"
        adder_space_name = f"{blank * (((chinese_char_count) // 2) - 1)}"
    else:
        adder_space_boxline = ""
        adder_space_name = ""

    filler = trailer = blank

    # Deal with icon in the name
    if set(name).difference(printable):
        trailer = fix_icon(name)

    # Build top and bottom box lines
    box_line_length = len(name)
    box_top = f"╔═{box_line * (box_line_length + len(adder_space_boxline))}═╗"
    box_bottom = f"╚═{box_line * (box_line_length + len(adder_space_boxline))}═╝"

    # Add box lines to output
    output_lines[0] += f"{filler}{box_top}"
    output_lines[1] += f"{filler}║{blank}{name}{trailer}{adder_space_name}║"
    output_lines[2] += f"{filler}{box_bottom}"

    # Calculate anchor position
    position_for_anchor = len(output_lines[0]) - (len(name) + len(adder_space_name)) // 2 - 4

    return output_lines, position_for_anchor


# Trace backwards in the output, inserting a bar (|) through right arrows.
def add_bar_above_lines(
    output_lines: list,
    line_to_modify: str,
    called_task_position: int,
) -> list:
    """
    Adds a bar above the specified line in the output lines.
    Args:
        output_lines: List of output lines
        line_to_modify: Line number to add bar above
        called_task_position: Position of calling task
    Returns:
        output_lines: Output lines with bar added above specified line
    - Find the line number to insert bar above by subtracting 1 from input line number
    - Iterate through output lines from beginning
    - When line number matches specified line, insert bar string above it
    - Return modified output lines
    """
    line_num = line_to_modify - 1
    check_line = True
    while check_line:
        if len(output_lines[line_num]) >= called_task_position:
            # Only insert bar if previous line character is a right arrow or two blanks.
            if output_lines[line_num][called_task_position] in (
                right_arrow,
                straight_line,
            ) or (
                output_lines[line_num][called_task_position] == " "
                and output_lines[line_num][called_task_position - 1] == " "
            ):
                output_lines[line_num] = (
                    f"{output_lines[line_num][:called_task_position]}{bar}{output_lines[line_num][called_task_position + 1 :]}"
                )
                line_num -= 1
            else:
                check_line = False
        else:
            break


def replace_diff_char(strings: list, char: str, replacement_char: str) -> list:
    # Looping backwards through the list of strings
    """
    Replace all occurrences of a character in a list of strings with the character from the next string in the list.

    Args:
        strings (list): List of strings to replace character in
        char (str): Character to replace
        replacement_char (str): Character to replace with

    Returns:
        list: Modified list of strings
    """
    for i in range(len(strings) - 2, -1, -1):
        # Cache the next string to avoid repeated access
        next_string = strings[i + 1]
        # Ignore lines with icons
        # icon_count = len(icon_pattern.findall(next_string))

        next_string_len = len(next_string)

        # Find all occurrences of 'char' in the current string
        num_chars = [i for i, c in enumerate(strings[i]) if c == char]

        # Process each character position found
        for char_position in num_chars:
            # Check if char_position is within bounds of the next string
            if char_position < next_string_len:
                next_char = next_string[char_position]

                # Check if the next string has the right pattern (" ", box_line, right_arrow_corner_down)
                if next_char in (" ", box_line, right_arrow_corner_down):  # noqa: SIM102
                    if (
                        char_position + 1 < next_string_len
                        and next_string[char_position + 1]
                        in (
                            " ",
                            box_line,
                            right_arrow_corner_down,
                        )
                        and next_string[char_position - 1] != up_arrow
                    ):
                        # Perform the string replacement
                        strings[i] = strings[i][:char_position] + replacement_char + strings[i][char_position + 1 :]
    return strings


# Go through output and delete all occurances of hanging bars |
def delete_hanging_bars(
    output_lines: list,
) -> list:
    """
    Go through output and delete all occurances of hanging bars |

    Args:
        output_lines (list): List of strings, where each string is a line of output.
        progress_counter (int): Counter for progress bar.

    Returns:
        list: The modified list of strings.
    """
    # Go through output and delete all occurances of hanging bars |
    output_lines = replace_diff_char(output_lines, bar, " ")

    # Now let's make sure there is a bar connecting right down arrow to Task.
    line_num = len(output_lines) - 1
    while line_num > 0:
        # Add bar(s) (|) above right-down arrow as necessary.
        arrow_position = output_lines[line_num].find(right_arrow_corner_down)
        if arrow_position != -1:
            add_bar_above_lines(output_lines, line_num, arrow_position)

        line_num -= 1

    return output_lines


def fix_duplicate_up_down_locations(call_table: dict) -> dict:
    # Get a list of duplicate up-down locations
    """
    Fixes duplicate up-down locations in the call table by adjusting connectors to avoid overlaps.

    Args:
        call_table (dict): A dictionary containing caller and called task connections with their line numbers
                           and up_down_locations.

    Returns:
        dict: The modified call table with unique up_down_locations for each connection.

    Processing Logic:
    - Identify duplicate up_down_locations in the call table.
    - For each pair of duplicates, determine the top and bottom line numbers for both connectors.
    - Check for overlap situations between the connectors, including complete, lower boundary, inner, or upper boundary overlaps.
    - Adjust the up_down_location of the second connector if an overlap is detected.
    - Recursively process the call table until all duplicates are resolved.
    """
    # Get a list of duplicate up-down locations
    duplicates = find_duplicate_up_down_locations(call_table)
    up_down_modified = False

    # Go through duplicates, two elements at a time: 1st = first up_down_location, 2nd = the duplicate up_down_location.
    for i in range(0, len(duplicates), 2):
        first_connector = duplicates[i]
        second_connector = duplicates[i + 1] if i + 1 < len(duplicates) else None
        if second_connector is None:
            break

        # Get the first connector's top and bottom line numbers.
        if first_connector[1]["caller_line_num"] > first_connector[1]["called_line_num"]:
            first_connector_top_line = first_connector[1]["called_line_num"]
            first_connector_bottom_line = first_connector[1]["caller_line_num"]
        else:
            first_connector_top_line = first_connector[1]["caller_line_num"]
            first_connector_bottom_line = first_connector[1]["called_line_num"]

        # Get the second connector's top and bottom line numbers.
        if second_connector[1]["caller_line_num"] > second_connector[1]["called_line_num"]:
            second_connector_top_line = second_connector[1]["called_line_num"]
            second_connector_bottom_line = second_connector[1]["caller_line_num"]
        else:
            second_connector_top_line = second_connector[1]["caller_line_num"]
            second_connector_bottom_line = second_connector[1]["called_line_num"]

        # Test for overlap situations: complete, lower boundary, inner or upper boundary overlap.
        if (
            (
                second_connector_top_line <= first_connector_top_line
                and second_connector_bottom_line >= first_connector_bottom_line
            )
            or (
                second_connector_top_line >= first_connector_top_line
                and second_connector_top_line <= first_connector_bottom_line
            )
            or (
                second_connector_bottom_line <= first_connector_bottom_line
                and second_connector_bottom_line >= first_connector_top_line
            )
        ):
            second_connector[1]["up_down_location"] += 2
            up_down_modified = True

    # Recurse until they have all been processed.
    if up_down_modified:
        call_table = fix_duplicate_up_down_locations(call_table)

    return call_table


# Build a sorted list of all caller Tasks and their called Tasks.
def build_call_table(output_lines: list) -> list:
    """
    Build a sorted list of all caller Tasks and their called Tasks.
        Args:
            output_lines (list): List of output lines
        Returns:
            list: Caller/Called Task list.
    Processing Logic:
    - Go through all output lines looking for caller Tasks.
    - Check each line for a "Calls" indicator to find caller Tasks
    - Process the caller and called Tasks found on each line, adding them to a call table
    - Return the call table sorted by location from inner to outer Tasks
    """
    # Go through all output lines looking for caller Tasks.
    call_table = {}
    for caller_line_num, line in enumerate(output_lines):
        # Get the Project name if we have one
        project_name_start = line.find("║ Project: ")
        if project_name_start != -1:
            project_name = line[project_name_start + 11 : len(line) - 2]

        # Do we have a "Calls" line (caller Task)?
        elif line_right_arrow in line:
            # Handle all of the caller and called Tasks.
            call_table = process_callers_and_called_tasks(
                output_lines,
                call_table,
                caller_line_num,
                line,
                project_name,
            )

    return call_table


def unique_up_down_location_by_project(call_table: dict, up_down_location: int) -> int:
    # Collect all existing up_down_location values in the call_table
    """
    Ensure that the given up_down_location is not already in use in the call_table by
    incrementing or decrementing it until it is unique for the given project.

    Args:
        call_table (dict): The dictionary of caller/called Task connections.
        up_down_location (int): The up_down_location to check for uniqueness.

    Returns:
        int: A unique up_down_location value.
    """
    existing_locations = {entry["up_down_location"] for entry in call_table.values()}

    # Check if the given up_down_location is already in use
    while up_down_location in existing_locations:
        # Increment or decrement to find a unique value
        up_down_location += 2  # You could change to -1 if decrementing is preferred

    # Return a unique up_down_location value
    return up_down_location


def ensure_unique_up_down_location(
    call_table: dict,
    up_down_location: int,
    project_name: str,
) -> int:
    """
    Ensure that the given up_down_location is not already in use in the call_table by
    incrementing or decrementing it until it is unique for the given project.  If the
    called Task is not in this project, then make sure the up_down_location is not in use
    in any Project.  If the called Task is in this project, then make sure the
    up_down_location is not in use in this project.

    Args:
        call_table (dict): The dictionary of caller/called Task connections.
        up_down_location (int): The up_down_location to check for uniqueness.
        project_name (str): The name of the current Project.

    Returns:
        int: A unique up_down_location value.
    """
    project_keys_values = [
        (key, details) for key, details in call_table.items() if details.get("project_name") == project_name
    ]

    # Make sure this called Task is in this Project.
    for key_value in project_keys_values:
        task_to_find = key_value[1]["caller_task_name"]
        caller_keys_values = [
            (key, details) for key, details in call_table.items() if details.get("caller_task_name") == task_to_find
        ]

        # If the caller task's project is not this called task project, then the called task project is outside this project.
        if caller_keys_values and caller_keys_values[0][1]["project_name"] != project_name:
            restart = True
            while restart:
                restart = False
                for value in call_table.values():
                    if value["up_down_location"] == up_down_location:
                        up_down_location += 2
                        restart = True
                        break

        # Caller and called tasks are in same project.  Just make sure up_down_location is unique for this project.
        else:
            mini_call_table = {}
            for key_value in project_keys_values:  # noqa: PLW2901
                mini_call_table[key_value[0]] = call_table[key_value[0]]
            up_down_location = unique_up_down_location_by_project(
                mini_call_table,
                up_down_location,
            )

    return up_down_location


# Complete Task details and save them in call_table
def get_task_details_and_save(
    output_lines: list,
    call_table: dict,
    connectors: dict,
) -> dict:
    """
    Saves task call details and returns updated call table
    Args:
        output_lines: Lines of output text
        call_table: Existing call table
        connectors: Dictionary of connectors...
            caller_task_name: Name of calling task
            caller_line_num: Line number of calling task
            caller_task_position: Position of calling task
            called_task_name: Name of called task
            called_line_num: Line number of called task
            called_task_position: Position of called task
            project_name: Name of project
    Returns:
        call_table: Updated call table with new task call details
    Processing Logic:
        1. Determine if called task is above or below calling task
        2. Calculate arrow type and positions
        3. Find range of lines for call
        4. Add new task call details to call table
    """
    # Get our arguments.
    caller_task_name = connectors["caller_task_name"]
    caller_line_num = connectors["caller_line_num"]
    caller_task_position = connectors["caller_task_position"]
    called_task_name = connectors["called_task_name"]
    called_line_num = connectors["called_line_num"]
    called_task_position = connectors["called_task_position"]
    project_name = connectors["project_name"]

    # Determine if the called Task is below or above the calling Task and set
    # the arrow location accordingly.
    if called_line_num > caller_line_num:
        # Going down.
        arrow = down_arrow
        upper_corner_arrow = left_arrow_corner_up
        lower_corner_arrow = right_arrow_corner_up
        fill_arrow = right_arrow
        start_line = caller_line_num
        line_count = called_line_num - caller_line_num
        up_down_start = start_line + 1
        line_range = line_count - 1
    else:
        # Going up.
        arrow = up_arrow
        upper_corner_arrow = left_arrow_corner_up
        lower_corner_arrow = right_arrow_corner_up
        fill_arrow = left_arrow
        start_line = called_line_num
        line_count = caller_line_num - called_line_num
        up_down_start = start_line
        line_range = line_count + 1

    # Find the outside boundary for the range of lines to traverse between "caller" and "called".
    # Up_down location is the pos of the "called" Task name "calls ..."
    up_down_location = max(
        caller_task_position,
        called_task_position,
    )  # Starting outer position (col)
    for x in range(line_range):
        line_to_compare = output_lines[up_down_start + x].rstrip().replace(task_delimeter, "")
        up_down_location = max(up_down_location, len(line_to_compare))
    up_down_location += 2

    # The key is insignificant, but must be unique.
    call_table_key = caller_task_position + called_task_position
    if call_table is not None:
        while call_table_key in call_table:
            call_table_key += 1

    # Ensure a unique up_down_location for the given project.
    up_down_location = ensure_unique_up_down_location(
        call_table,
        up_down_location,
        project_name,
    )

    # Okay, we have everything we need.  Add it all to our call table.
    call_table[call_table_key] = {
        "caller_task_name": caller_task_name,
        "caller_line_num": caller_line_num,
        "caller_task_position": caller_task_position,
        "called_task_name": called_task_name,
        "called_line_num": called_line_num,
        "called_task_position": called_task_position,
        "arrow": arrow,
        "upper_corner_arrow": upper_corner_arrow,
        "lower_corner_arrow": lower_corner_arrow,
        "fill_arrow": fill_arrow,
        "start_line": start_line,
        "line_count": line_count,
        "up_down_location": up_down_location,
        "project_name": project_name,
    }

    return call_table


# Go through all caller and called Tasks and build the call table based on the
# input line passed in.
def process_callers_and_called_tasks(
    output_lines: list,
    call_table: dict,
    caller_line_num: int,
    line: str,
    project_name: str,
) -> dict:
    """
    Processes caller and called tasks by parsing the diagram line from the output lines and saving the call details
    in the call table.
    Args:
        output_lines: List of output lines from profiler
        call_table: Table to store caller and called task details
        caller_line_num: Line number of caller task
        line: Line containing call information
        project_name: Name of project
    Returns:
        call_table: Updated call table with caller and called task details
    Processes Logic:
        - Gets caller task name from line
        - Gets called task name(s) from line
        - Searches for called task line in output_lines
        - If called task found, saves details to call_table
    "└─" = caller_task  and "[call -->" = called_task
    """

    # Get this Task's name
    caller_task_name = line.split("└─")
    caller_task_name = caller_task_name[1].split("[")[0].lstrip()
    caller_task_name = caller_task_name.rstrip()

    # Get the position in the line of of the caller Task name.
    caller_task_position = output_lines[caller_line_num].index(caller_task_name) + (len(caller_task_name) // 2)

    # Get the called Task name.
    start_position = line.index(line_right_arrow) + 4
    called_task_names = line[start_position:].split(task_delimeter)
    processed_tasks = []

    # Go through list of calls to Tasks from this caller Task (e.g. after ""[Calls ──▶").
    called_names = []  # Keep track of called task names.

    for called_task_name in called_task_names:
        if not called_task_name or called_task_name in (", ", "]"):
            continue

        # Get the index of the called Task name.
        called_task_index = 1 if called_task_name not in called_names else called_names.count(called_task_name) + 1
        called_names.append(called_task_name)

        #  Find the "Called" Task line for the caller Task.
        search_name = f"{angle}{called_task_name}"

        # Make sure the called Task exists.
        found_called_task = False
        for called_line_num, check_line in enumerate(output_lines):  # noqa: B007
            # See if the task name is in the line: "└─ {called_task_name}".
            if search_name in check_line:
                # Make certain that this is the exact string we want and not a substr match.
                # If search_name as a substr of the task name we are looking for, then erroneously gets a match and we
                # must continue the search!
                str_pos = check_line.find(search_name)

                # Find the "[" bracket and make sure it is the next valid character after the name.
                modified_check_line = check_line.replace("(entry) ", "").replace(
                    "(exit) ",
                    "",
                )
                string_position = modified_check_line.find(f"{search_name} [", str_pos)
                # Keep searching if this is not the valid caller Task name.
                if string_position == -1:
                    continue

                # Find the position of the "[Calls -->" task name on the called line immediately after "└─ ".
                found_called_task = True
                # caller_task_position = check_line.index(called_task_name) + (len(called_task_name) // 2)
                caller_task_position = str_pos + (len(called_task_name) // 2)
                # Find the position of the "Called by" task name on the caller by line
                temp_line = output_lines[caller_line_num].replace(task_delimeter, "")
                start_find_nth = temp_line.find("[Calls ──▶")
                called_task_position = (
                    find_nth(
                        temp_line,
                        called_task_name,
                        called_task_index,
                        start_find_nth,
                    )
                    + len(called_task_name) // 2
                )
                # Get out of loop.
                break

        # If called Task found, then save everything (only do it once) in the call table.
        # if found_called_task and called_task_name not in processed_tasks:
        if found_called_task:
            connectors = {
                "caller_task_name": caller_task_name,
                "caller_line_num": caller_line_num,
                "caller_task_position": caller_task_position,
                "called_task_name": called_task_name,
                "called_line_num": called_line_num,
                "called_task_position": called_task_position,
                "project_name": project_name,
            }
            call_table = get_task_details_and_save(output_lines, call_table, connectors)
            processed_tasks.append(called_task_name)

    return call_table  # Return call table with new entry.


def find_nth(haystack: str, needle: str, n: int, starting_position: int = 0) -> int:
    """
    Finds the nth occurrence of a substring in a string.

    Args:
        haystack (str): The string to search in.
        needle (str): The substring to search for.
        n (int): The occurrence to find. 1 is the first occurrence.
        starting_position: The starting position to search from.

    Returns:
        int: The index of the nth occurrence of the substring. -1 if not found.
    """
    start = haystack.find(needle, starting_position)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start + len(needle))
        n -= 1
    return start


from collections import defaultdict


def find_duplicate_up_down_locations(call_table: dict) -> list:
    # Dictionary to collect items by their 'up_down_location' values
    """
    Finds items in the given data dictionary with duplicate 'up_down_location' values.

    Args:
        call_table (dict): The dictionary of connectors.

    Returns:
        list: A list of tuples, where each tuple contains the key and value of an item with a duplicate 'up_down_location'.
    """
    location_map = defaultdict(list)

    # Populate the location_map with items indexed by 'up_down_location'
    for key, value in call_table.items():
        location = value.get("up_down_location")
        if location is not None:
            location_map[location].append((key, value))

    # Extract and return only the items with duplicate 'up_down_location'
    return [item for items in location_map.values() if len(items) > 1 for item in items]
