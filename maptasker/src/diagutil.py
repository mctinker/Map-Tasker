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

from maptasker.src.nameattr import get_tk
from maptasker.src.primitem import PrimeItems

bar = "│"
blank = " "
box_line = "═"
down_arrow = "▼"
up_arrow = "▲"
left_arrow = "◄"
right_arrow = "►"
straight_line = "─"
task_delimeter = "¥"
line_right_arrow = f"{straight_line*2}▶"
line_left_arrow = f"◄{straight_line*2}"
right_arrow_corner_down = "╰"
right_arrow_corner_up = "╯"
left_arrow_corner_down = "╭"
left_arrow_corner_up = "╮"
angle = "└─ "

arrows = f"{down_arrow}{up_arrow}{left_arrow}{right_arrow}{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}"
directional_arrows = f"{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}{up_arrow}{down_arrow}"

# Define additional "printable" characters to allow.
# extra_cars: set[str] = set(f"│└─╔═║╚╝╗▶◄{arrows}")
# List of printable ASCII characters
# printable_chars: set[str] = set(string.printable)
# printable_chars = printable_chars.union(extra_cars)
icon_regex = re.compile(r"\s*[\U0001F300-\U0001F7FF]\s*")


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
    filler = f"{blank*len(header)}"
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
    blanks = f"{blank*5}"
    filler = f"{blanks*indent}"
    full_name = f"{title} {name}"
    box = ["", "", ""]
    box[0] = f"{filler}╔═{box_line*len(full_name)}═╗"  # Box top
    box[1] = f"{filler}║ {full_name} ║"  # Box middle
    box[2] = f"{filler}╚═{box_line*len(full_name)}═╝"  # Box bottom
    print_3_lines(box)


# Get the dimensions of a text string using tkinter to calculate the width needed.
def width_and_height_calculator_in_pixel(txt: str, fontname: str, fontsize: int) -> list:
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


# Wew have an icon in our name.  Remove any padding as necessary
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
            char_dimension = width_and_height_calculator_in_pixel(char, "Courier New", 12)
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
    return text[:index] + text[index + 1 :]


# Count the number of icons (non-alphanumeric chars) in the line of text
def count_icons(text: str) -> int:
    """Returns the number of icons in the text string.

    Args:
      text: A string.

    Returns:
      An integer representing the number of icons in the text string.
    """
    matches = icon_regex.findall(text)
    return len(matches)


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
    arrow_position: int = next((text.index(char) for char in arrows + bar if char in text), 0)
    if arrow_position == 0:
        return text

    # Remove a blank for every icon found on line with an arrow.
    output: str = text

    # If there are icons in the text...
    icon_count = count_icons(text)
    if icon_count > 0:
        # Drop here if there is at least one icon.
        for find_arrow in directional_arrows + bar:
            found_arrow = text.find(find_arrow)
            if found_arrow != -1:
                # Remove the icon return the modified string
                return remove_char(text, found_arrow - 1)

        # No icon found
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

    filler = trailer = blank

    # Deal with icon in the name
    if set(name).difference(printable):
        trailer = fix_icon(name)

    # Build top and bottom box lines
    box_line_length = len(name)
    box_top = f"╔═{box_line*box_line_length}═╗"
    box_bottom = f"╚═{box_line*box_line_length}═╝"

    # Add box lines to output
    output_lines[0] += f"{filler}{box_top}"
    output_lines[1] += f"{filler}║{blank}{name}{trailer}║"
    output_lines[2] += f"{filler}{box_bottom}"

    # Calculate anchor position
    position_for_anchor = len(output_lines[0]) - len(name) // 2 - 4

    return output_lines, position_for_anchor


# Trace backwards in the output, inserting a bar (|) through right arrows.
def add_bar_above_lines(output_lines: list, line_to_modify: str, called_task_position: int) -> list:
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
            if output_lines[line_num][called_task_position] in (right_arrow, straight_line) or (
                output_lines[line_num][called_task_position] == " "
                and output_lines[line_num][called_task_position - 1] == " "
            ):
                output_lines[line_num] = (
                    f"{output_lines[line_num][:called_task_position]}{bar}{output_lines[line_num][called_task_position + 1:]}"
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
                    if char_position + 1 < next_string_len and next_string[char_position + 1] in (
                        " ",
                        box_line,
                        right_arrow_corner_down,
                    ):
                        # Perform the string replacement
                        strings[i] = strings[i][:char_position] + replacement_char + strings[i][char_position + 1 :]
    return strings


# Go through output and delete all occurances of hanging bars |
def delete_hanging_bars(
    output_lines: list,
    progress_counter: int,
) -> list:
    """
    Go through output and delete all occurances of hanging bars |

    Args:
        output_lines (list): List of strings, where each string is a line of output.
        progress_bar (object): The progress bar object.
        progress_counter (int): Counter for progress bar.
        max_data (int): The maximum amount of data for the progress bar.
        tenth_increment (int): The increment for updating the progress bar.

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

    return output_lines, progress_counter


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
        # Do we have a "Calls" line (caller Task)?
        if line_right_arrow in line:
            # Handle all of the caller and called Tasks.
            call_table = process_callers_and_called_tasks(output_lines, call_table, caller_line_num, line)

    # Return the call table sorted by up_down_location ((inner locations before outer))
    return dict(sorted(call_table.items()))


# Complete Task details and save them in call_table
def get_task_details_and_save(
    output_lines: list,
    call_table: dict,
    caller_task_name: str,
    caller_line_num: int,
    caller_task_position: int,
    called_task_name: str,
    called_line_num: int,
    called_task_position: int,
) -> dict:
    """
    Saves task call details and returns updated call table
    Args:
        output_lines: Lines of output text
        call_table: Existing call table
        caller_task_name: Name of calling task
        caller_line_num: Line number of calling task
        caller_task_position: Position of calling task
        called_task_name: Name of called task
        called_line_num: Line number of called task
        called_task_position: Position of called task
    Returns:
        call_table: Updated call table with new task call details
    Processing Logic:
        1. Determine if called task is above or below calling task
        2. Calculate arrow type and positions
        3. Find range of lines for call
        4. Add new task call details to call table
    """
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
    # Note: The task_delimeter pushes the position to the right by the number of delimeters / 2
    up_down_location = max(caller_task_position, called_task_position)  # Starting outer position (col)
    for x in range(line_range):
        line_to_compare = output_lines[up_down_start + x].rstrip()
        up_down_location = max(up_down_location, len(line_to_compare))

    # If this up_down value is already in our table, increment it until it isn't.
    if call_table is not None:
        while up_down_location in call_table:
            up_down_location += 2

    # Okay, we have everything we need.  Add it all to our call table.
    call_table[up_down_location] = [
        caller_task_name,
        caller_line_num,
        caller_task_position,
        called_task_name,
        called_line_num,
        called_task_position,
        arrow,
        upper_corner_arrow,
        lower_corner_arrow,
        fill_arrow,
        start_line,
        line_count,
    ]
    return call_table


# Go through all caller and called Tasks and build the call table based on the
# input line passed in.
def process_callers_and_called_tasks(output_lines: list, call_table: dict, caller_line_num: int, line: str) -> dict:
    """
    Processes caller and called tasks by parsing the diagram line from the output lines.
    Args:
        output_lines: List of output lines from profiler
        call_table: Table to store caller and called task details
        caller_line_num: Line number of caller task
        line: Line containing call information
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
                string_position = check_line.find(f"{search_name} [", str_pos)
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
                break

        # If called Task found, then save everything (only do it once) in the call table.
        # if found_called_task and called_task_name not in processed_tasks:
        if found_called_task:
            call_table = get_task_details_and_save(
                output_lines,
                call_table,
                caller_task_name,
                caller_line_num,
                caller_task_position,
                called_task_name,
                called_line_num,
                called_task_position,
                # called_task_line_num,
            )
            processed_tasks.append(called_task_name)

    return call_table


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
