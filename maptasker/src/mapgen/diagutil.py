"""Utilities used by diagram.py."""

#! /usr/bin/env python3
#                                                                                      #
# diagutil: Utilities used by diagram.py.                                              #
#                                                                                      #
# Traverse our network map and print out everything in connected boxes.                #
#                                                                                      #
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from maptasker.src.core.mapfonts import is_double_width
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import icon_pattern
from maptasker.src.mapgen.diagcnst import (
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

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig

arrows = f"{down_arrow}{up_arrow}{left_arrow}{right_arrow}{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}"
directional_arrows = f"{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}{up_arrow}{down_arrow}"


# Define additional "printable" characters to allow.
# extra_cars: set[str] = set(f"│└─╔═║╚╝╗▶◄{arrows}")
# List of printable ASCII characters
# printable_chars: set[str] = set(string.printable)
# printable_chars = printable_chars.union(extra_cars)
# icon_regex = re.compile(r"\s*[\U0001F300-\U0001F7FF]\s*")


# Add line to our output queue.
def add_output_line(line: str, state: RunState) -> None:
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
    state.netmap_output.append(line)


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
def print_3_lines(lines: list, state: RunState) -> None:
    """
    Prints 3 lines from a list of items
    Args:
        lines: The three lines of text to add
    Returns:
        None: Does not return anything
    - Add each of the first 3 items of lines to the netmap output
    """
    for line in range(3):
        add_output_line(lines[line], state=state)


# Given a list of text strings, print all of them.
def print_all(lines: list, state: RunState) -> None:
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
        add_output_line(line, state=state)


# Given a text string and title, enclose them in a box and print the box.
def print_box(name: str, title: str, indent: int, config: RunConfig, state: RunState) -> None:
    """
    Given a text string and title, enclose them in a box and print the box.

    Args:
        name: Name to display in the box
        title: Title to display before the name: Project:, Profile:, Task:
        indent: Number of blanks for indentation of the box
        config: the run's settings (language)
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
    # Do the box for the length of the name
    blanks = f"{blank * 5}"
    filler = f"{blanks * indent}"

    # Deal with translations
    if config.language not in ("Arabic", "English"):
        title = translate_string(title)

    full_name = f"{title} {name}"

    box = ["", "", ""]
    # An icon or a Chinese/Japanese/Korean character is drawn two columns wide but is one
    # character, so the borders need the difference.
    border_length = len(full_name) + icon_columns(full_name)
    box[0] = f"{filler}╔═{box_line * border_length}═╗"  # Box top
    box[1] = f"{filler}║ {full_name} ║"  # Box middle
    box[2] = f"{filler}╚═{box_line * border_length}═╝"  # Box bottom
    print_3_lines(box, state=state)


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


# The characters that have to stay in their column so a connector lines up with the one
# above and/or below it.
_vertical_connectors = f"{bar}{up_arrow}{down_arrow}{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}"


# What can follow the character an icon starts with and still be part of the same icon: the
# variation selector that turns a symbol into a picture, a skin tone, a keycap, or a joiner
# followed by the next picture of a sequence.
_icon_modifiers = "\ufe0f\u20e3\U0001f3fb\U0001f3fc\U0001f3fd\U0001f3fe\U0001f3ff"


def icon_spans(text: str) -> list[tuple[int, int]]:
    """Find the icons in a line, each as the (start, end) of the characters that draw it.

    An icon is drawn as a picture two columns wide.  That is a wide character, or a narrow
    symbol followed by the selector that asks for its picture (a gear, or an arrow turned
    around), along with whatever is joined onto it.

    Args:
        text (str): The line to look through.

    Returns:
        list[tuple[int, int]]: The start and the position just past the end of each icon, in order.
    """
    spans = []
    position = 0
    while position < len(text):
        char = text[position]
        following = text[position + 1 : position + 2]
        if char not in _icon_modifiers and ((char.strip() and is_double_width(char)) or following == "\ufe0f"):
            end = position + 1
            while end < len(text) and (text[end] in _icon_modifiers or text[end] == "\u200d"):
                # A joiner brings the next picture along with it.
                end += 2 if text[end] == "\u200d" else 1
            end = min(end, len(text))
            spans.append((position, end))
            position = end
        else:
            position += 1
    return spans


def icon_columns(text: str) -> int:
    """Count the columns the wide characters in a string are drawn wider than it is long.

    Args:
        text (str): The string, such as the name that goes in a box.

    Returns:
        int: How much wider than len(text) the string is drawn: one for each icon and each
        Chinese/Japanese/Korean character.
    """
    return sum(2 - (end - start) for start, end in icon_spans(text))


def _extra_columns(text: str) -> list[tuple[int, int]]:
    """Find where a line is wider or narrower on screen than it is long.

    An icon, or a Chinese/Japanese/Korean character, is drawn two columns wide.  When it is a
    single character it is one column short of that, so everything to its right is drawn one
    column further over than the same character on a line without one.  A picture made of a
    symbol and its selector (a turned-around arrow) is already two characters long and needs
    nothing, and one with a joiner in it is longer than it is wide.

    Args:
        text (str): The line to look through.

    Returns:
        list[tuple[int, int]]: The position just past each such character, and how many columns
        short of its length it is drawn -- negative if it is longer -- in order.
    """
    return [(end, 2 - (end - start)) for start, end in icon_spans(text) if end - start != 2]


# Characters a blank can sit next to without being the space between two words.
_punctuation = ",[]\u25c4\u25b6\u2500"


def _take_blanks(segment: str, count: int) -> tuple[str, int]:
    """Rub out up to `count` blanks from a stretch of a line, preferring ones that cost nothing.

    Args:
        segment (str): The stretch of the line, ending just before a connector.
        count (int): How many blanks to rub out.

    Returns:
        tuple[str, int]: The stretch, and how many blanks were taken.  They come from the blanks
        just before the connector first, then from any gap of two or more blanks further back,
        which are cut down to one.  If that is not enough, the blanks beside punctuation are
        taken, and then the spaces between words -- but only if that is enough to put the connector
        in line, since a line with its words run together and its connector still out of line is
        worse than one that is just out of line.
    """
    stripped = segment.rstrip(blank)
    taken = min(count, len(segment) - len(stripped))
    segment = segment[: len(segment) - taken]
    for match in reversed(list(re.finditer(r"  +", segment))):
        if taken >= count:
            return segment, taken
        cut = min(match.end() - match.start() - 1, count - taken)
        segment = segment[: match.start() + 1] + segment[match.start() + 1 + cut :]
        taken += cut
    if taken >= count or "\u2551" in segment:
        return segment, taken

    # A box is never touched; otherwise, the last resort.
    lone = [i for i, char in enumerate(segment) if char == blank and "\u2551" not in segment[i - 1 : i + 2]]
    beside_punctuation = [
        i for i in lone if segment[i - 1 : i] in _punctuation or segment[i + 1 : i + 2] in _punctuation
    ]
    between_words = [i for i in lone if i not in beside_punctuation]
    chosen = (beside_punctuation[::-1] + between_words[::-1])[: count - taken]
    if len(chosen) < count - taken:
        return segment, taken
    keep = set(range(len(segment))) - set(chosen)
    return "".join(segment[i] for i in sorted(keep)), taken + len(chosen)


# An icon takes two columns on screen but only one character in the line, and so does a Chinese/
# Japanese/Korean character.  That pushes every connector to the right of it out of line with the
# connector above and below.  Take the blanks in front of each connector back out to put them in line.
def remove_icon(text: str) -> str:
    """
    Make up for the width of the wide characters in a line, so its connectors line up.

    Args:
        text (str): The input string

    Returns:
        str: The string with blanks taken out in front of each connector by as many columns as
        the wide characters before it are drawn wider than they are long (or put in, for ones
        drawn narrower).  Connectors with no wide character before them are not moved, and
        no text is removed.
    """
    extras = _extra_columns(text)
    if not extras:
        return text

    pieces = []
    previous = 0
    net_taken = 0
    for position, char in enumerate(text):
        if char not in _vertical_connectors:
            continue
        # How far over this connector is drawn, less what has already been taken back.
        need = sum(extra for end, extra in extras if end <= position) - net_taken
        segment = text[previous:position]
        if need > 0:
            segment, taken = _take_blanks(segment, need)
            net_taken += taken
        elif need < 0:
            # Drawn narrower than it is long: give the connector the columns back.
            segment += blank * -need
            net_taken += need
        pieces.extend((segment, char))
        previous = position + 1
    pieces.append(text[previous:])
    return "".join(pieces)


# Given a name, enclose it in a text box
def build_box(name: str, output_lines: list, config: RunConfig) -> tuple:
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

    if name == "No Profile" and config.language not in ("English", "Arabic"):
        name = translate_string(name)

    # Set the box line length based on the (translated) name.  An icon or a Chinese/Japanese/
    # Korean character is one character but is drawn two columns wide, so the borders have
    # to be longer than the name by the difference for the right wall to sit under them.
    box_line_length = len(name) + icon_columns(name)

    # Build top and bottom box lines
    box_top = f"╔═{box_line * box_line_length}═╗"
    box_bottom = f"╚═{box_line * box_line_length}═╝"

    # Add box lines to output
    output_lines[0] += f"{filler}{box_top}"
    output_lines[1] += f"{filler}║{blank}{name}{trailer}║"
    output_lines[2] += f"{filler}{box_bottom}"

    # Calculate anchor position
    position_for_anchor = len(output_lines[0]) - box_line_length // 2 - 4

    return output_lines, position_for_anchor


# Trace backwards in the output, inserting a bar (|) through right arrows.
def add_bar_above_lines(
    output_lines: list,
    line_to_modify: int,
    called_task_position: int,
) -> None:
    """
    Adds a bar above the specified line in the output lines.
    Args:
        output_lines: List of output lines
        line_to_modify: Line number to add bar above
        called_task_position: Position of calling task
    Returns:
        None: output_lines is changed in place
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
    _add_bar_above_lines = add_bar_above_lines
    while line_num > 0:
        # Add bar(s) (|) above right-down arrow as necessary.
        arrow_position = output_lines[line_num].find(right_arrow_corner_down)
        if arrow_position != -1:
            _add_bar_above_lines(output_lines, line_num, arrow_position)

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
def build_call_table(output_lines: list, config: RunConfig) -> dict:
    """
    Build a sorted list of all caller Tasks and their called Tasks.
        Args:
            output_lines (list): List of output lines
            config (RunConfig): the run's settings (language)
        Returns:
            dict: The connectors, keyed by caller and called Task.
    Processing Logic:
    - Go through all output lines looking for caller Tasks.
    - Check each line for a "Calls" indicator to find caller Tasks
    - Process the caller and called Tasks found on each line, adding them to a call table
    - Return the call table sorted by location from inner to outer Tasks
    """
    # Go through all output lines looking for caller Tasks.
    call_table = {}
    project_text = translate_string("Project:") if config.language not in ("Arabic", "English") else "Project:"
    for caller_line_num, line in enumerate(output_lines):
        # Get the Project name if we have one
        project_name_start = line.find(f"║ {project_text} ")
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


#     return up_down_location
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

    Optimized version utilizing O(1) set lookups to eliminate nested loop bottlenecks.
    """
    # Step 1: Pre-calculate sets for O(1) lookups instead of repeatedly scanning call_table
    global_locations = set()
    project_locations = set()

    # A mapping to quickly find the project_name of any caller_task_name in O(1) time
    task_project_map = {}

    for details in call_table.values():
        loc = details.get("up_down_location")
        if loc is not None:
            global_locations.add(loc)
            if details.get("project_name") == project_name:
                project_locations.add(loc)

        # Cache task-to-project relationships
        caller = details.get("caller_task_name")
        p_name = details.get("project_name")
        if caller and p_name:
            task_project_map[caller] = p_name

    # Step 2: Gather unique caller tasks inside THIS project
    # (Matches the original logic's intent for project_keys_values)
    this_project_callers = {
        details["caller_task_name"]
        for details in call_table.values()
        if details.get("project_name") == project_name and "caller_task_name" in details
    }

    # Step 3: Determine if we need a globally unique or project-unique location
    is_outside_project = False
    for task_to_find in this_project_callers:
        # Get the project of the caller task using our fast O(1) map
        caller_project = task_project_map.get(task_to_find)

        if caller_project and caller_project != project_name:
            is_outside_project = True
            break  # If even one is outside, global rules apply, no need to keep checking

    # Step 4: Resolve collisions instantly using the appropriate pre-built set
    target_set = global_locations if is_outside_project else project_locations

    while up_down_location in target_set:
        up_down_location += 2

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
def _find_called_task_line(
    output_lines: list,
    caller_line_num: int,
    called_task_name: str,
    called_task_index: int,
) -> tuple[int, int, int] | None:
    """Find the "Called" Task's own line, and where on each line the connector arrows will meet the names.

    Args:
        output_lines: the Diagram's output lines.
        caller_line_num: the line of the Task doing the calling.
        called_task_name: the name of the Task being called.
        called_task_index: which call to this Task from the caller this is (1 for the first).

    Returns:
        (the called Task's line number, the caller-side position of the name, the called-side
        position of the name), or None if the called Task has no line of its own.
    """
    #  Find the "Called" Task line for the caller Task.
    search_name = f"{angle}{called_task_name}"

    # Make sure the called Task exists.
    for called_line_num, check_line in enumerate(output_lines):
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
            return called_line_num, caller_task_position, called_task_position
    return None


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

        found = _find_called_task_line(output_lines, caller_line_num, called_task_name, called_task_index)

        # If called Task found, then save everything (only do it once) in the call table.
        if found:
            called_line_num, caller_task_position, called_task_position = found
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
