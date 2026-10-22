"""diagclean: tidying a drawn Diagram.

Marking calls to Tasks that were not found, trimming a Diagram to the view limit, repairing elbows, bars and
straight lines the arrows left broken, and opening the blank lines the call arrows are drawn into."""

from __future__ import annotations

import gc
import re
from typing import TYPE_CHECKING

from maptasker.src.core import console
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import logger
from maptasker.src.mapgen.diagarrows import bracket_list_end
from maptasker.src.mapgen.diagcnst import (
    angle,
    angle_elbow,
    bar,
    blank,
    box_line,
    left_arrow_corner_down,
    left_arrow_corner_up,
    line_left_arrow,
    line_right_arrow,
    right_arrow_corner_down,
    right_arrow_corner_up,
    straight_line,
    task_delimeter,
)
from maptasker.src.mapgen.diagrecord import remap_object_seeds
from maptasker.src.mapgen.diagutil import delete_hanging_bars, find_nth

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig


# Find and flag in the output those called Tasks that don't exist.
def mark_tasks_not_found(output_lines: list) -> None:
    """
    Mark tasks not found in output lines
    Args:
        output_lines: List of output lines to search
    Returns:
        None: Function does not return anything
    - Iterate through each line in output lines
    - Check if line contains "Task not found" string
    - If found, mark line number in a list for later processing
    """
    for caller_line_num, line in enumerate(output_lines):
        if line_right_arrow in line:
            # Get the called Task name.
            start_position = line.index(line_right_arrow) + 4
            called_task_names = line[start_position:].split(", ")

            # Go through list of calls to Tasks from this caller Task.
            track_task_name = []
            # The line as it reads once earlier calls on it have been marked, which is what
            # the nth-occurrence search below has to count in.
            current_line = line
            for called_task_name in called_task_names:
                # Get the called Task name.
                called_task = called_task_name.lstrip().split("]")
                # Track the number of instances of the called Task.
                called_name = called_task[0].replace("]", "")
                called_name_no_delimeter = called_name.replace(task_delimeter, "")
                # Add the task name to track it, and get the count of the number of times it appears in the line.
                track_task_name.append(called_name_no_delimeter)
                num_called_task = track_task_name.count(called_name_no_delimeter)

                # Don't bother with variables since we know these won't be found.
                if called_task[0][1] == "%":
                    continue

                #  Find the "Called" Task line for the caller Task.
                search_name = f"{angle}{called_name_no_delimeter}"

                # Make sure the called Task exists.
                found_called_task = False
                for check_line in output_lines:
                    if search_name in check_line:
                        found_called_task = True
                        called_task_position = check_line.index(
                            called_name_no_delimeter,
                        )
                        break

                # If Task doesn't exist, mark it as such.
                not_found = " (Not Found!)"
                if not found_called_task:
                    # Find the nth occurance of the called Task
                    called_task_position = find_nth(
                        current_line,
                        called_name,
                        num_called_task,
                        0,
                    )
                    end_of_called_task_position = called_task_position + len(
                        called_task[0],
                    )

                    # Reconstruct the line
                    output_lines[caller_line_num] = (
                        output_lines[caller_line_num][:called_task_position]
                        + called_task[0]
                        + not_found
                        + output_lines[caller_line_num][end_of_called_task_position:]
                    )
                    current_line = output_lines[caller_line_num]


def mysizeof(my_dict: dict) -> int:
    """
    Count the entries in a dictionary.

    Args:
        my_dict (dict): The dictionary to count.

    Returns:
        int: The number of entries.
    """
    total = 0
    for _, _ in my_dict.items():
        total += 1
    return total


def furthest_connector_line(connector: dict) -> int:
    """The last diagram line a connector touches -- it needs every line between its two ends."""
    return max(connector["caller_line_num"], connector["called_line_num"])


def check_limit(
    call_table: dict, output_lines: list, _progress_bar: dict, config: RunConfig, state: RunState
) -> tuple[int | None, dict]:
    """
    Cut the diagram short at the view limit rather than refusing to draw it at all.

    This used to bail out entirely -- error message, everything thrown away, no diagram -- which
    left a large configuration with nothing to look at.  The Map view has always handled its own
    limit by writing out as much as the limit allows and saying so (bildhtml.write_out_the_file),
    and this now does the same: the diagram is drawn from the top down to the point where the
    limit is reached, and PrimeItems.diagram_limit_msg says how much was left off.

    The call table is what the limit is measured against, since every entry in it is a connector
    that has to be drawn across the diagram -- so the budget is spent in connectors, and the
    diagram is cut at the last line the affordable ones reach.  That keeps the work this limit
    exists to cap capped, while still showing the user the part of the diagram it paid for.

    Args:
        call_table (dict): The caller/called connectors, keyed by an arbitrary unique key.
        output_lines (list): The diagram built so far, one string per line.
        _progress_bar (dict): The progress bar to update.

    Returns:
        tuple: (line to cut the finished diagram at or None to keep all of it, the connectors to
            draw).  The cut is applied by the caller once the arrows are drawn, not here: the
            drawing routines reach a few lines beyond a connector's own two ends (see
            add_down_and_up_arrows), so the lines have to still be there while it works.
    """
    # Only the GUI's views are limited; a command-line run writes the whole thing to a file.
    if not config.guiview:
        return None, call_table

    # Cleared per run: a diagram that fits must not inherit the message from one that did not.
    state.diagram_limit_msg = ""

    # size = mysizeof(call_table)
    # size = getSize(call_table)
    size = mysizeof(call_table) * 67
    view_limit = config.view_limit
    if size <= view_limit:
        return None, call_table

    # Over the limit.  Work out how many connectors that budget buys, and keep the ones nearest
    # the top of the diagram: a connector is only drawable if both of its ends survive the cut,
    # so ordering by the furthest line each one reaches is what makes the kept set contiguous
    # from the top rather than scattered down a diagram whose lower half has been removed.
    max_connectors = max(1, view_limit // 67)
    by_position = sorted(call_table.items(), key=lambda item: furthest_connector_line(item[1]))
    kept = dict(by_position[:max_connectors])

    # Cut just past the last line the kept connectors need, so none of them is left dangling.
    cut_at = max(furthest_connector_line(connector) for connector in kept.values()) + 1
    total_connectors = mysizeof(call_table)
    lines_dropped = max(0, len(output_lines) - cut_at)

    state.diagram_limit_msg = (
        f"{translate_string('MapTasker: view limit reached, diagram truncated')}: "
        f"{translate_string('connectors')}={len(kept)}/{total_connectors}, "
        f"{translate_string('lines dropped')}={lines_dropped}, "
        f"{translate_string('View Limit')}={view_limit}.  "
        f"{translate_string('Select a larger View Limit or a single Project / Profile / Task to see the rest.')}"
    )
    logger.info(state.diagram_limit_msg)

    # The connectors being dropped can be a lot of memory on the configurations that get here,
    # and nothing refers to them once this returns.
    gc.collect()

    return cut_at, kept


def cleanup_task_names(output_lines: list, num: int, line: str) -> list:
    """
    Handle special character around Task names.  Remove all quotes and add equivelent spaces after last '].

    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.
        line (str): The current line.

    Returns:
        list: The modified list of strings.
    """
    occurences = [i for i, c in enumerate(line) if c == task_delimeter]

    # Add a space beyond last ] for each occurenceof the task delimiter.
    if occurences:
        # Replace task_delimeter only if there are occurrences
        output_lines[num] = output_lines[num].replace(task_delimeter, "")

        # Find call position more efficiently
        call_position = output_lines[num].find(f" [Calls {line_right_arrow}")
        if call_position == -1:
            call_position = output_lines[num].find(f" [Called by {line_left_arrow}")

        if call_position != -1:
            # Find the position of the closing bracket efficiently
            list_end = bracket_list_end(output_lines[num][call_position + 8 :])
            brackets_position = call_position + 8 + list_end if list_end != -1 else -1

            if brackets_position != -1:
                # Calculate the number of occurrences and construct the new line
                num_occurences = len(occurences)
                output_lines[num] = (
                    output_lines[num][: brackets_position + 1]
                    + (blank * num_occurences)
                    + output_lines[num][brackets_position + 1 :]
                )
        else:
            # Always recorded, shown only when debugging.  It used to be printed OR logged
            # depending on the debug flag, so the non-debug run had no record of it at all
            # beyond a line on a terminal nobody was reading.
            console.debug(f"Rutroh!  Diagram: No call position found in line {num} {line}")
    return output_lines


def cleanup_dangling_elbows(output_lines: list, num: int) -> list:
    """
    Check for dangling elbows and fix them.

    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.

    Returns:
        list: The modified list of strings.
    """
    elbow = output_lines[num].find(left_arrow_corner_up)
    if elbow != -1 and output_lines[num][elbow - 1] == " ":  # Check for dangling elbows
        output_lines[num] = output_lines[num][: elbow - 1] + right_arrow_corner_down + output_lines[num][elbow:]

    elbow = output_lines[num].find(" ───╯")
    if elbow != -1:  # Check for dangling elbows
        output_lines[num] = output_lines[num][:elbow] + left_arrow_corner_down + output_lines[num][elbow + 1 :]
    return output_lines


# Pre-compile the regex pattern outside the function to maximize performance.
# This matches: "straight_line" followed by a space, followed by "straight_line"
# Using a lookahead (?=...) ensures overlapping matches are caught cleanly.
MISSING_BAR_PATTERN = re.compile(f"({re.escape(straight_line)}) (?={re.escape(straight_line)})")


def cleanup_missing_straight_lines(output_lines: list, num: int, line: str) -> list:
    """
    Add missing straight lines in which there is one or more blanks before "╯" or missing bars: "straight_line space straight_line".
    Replace the space with a straight line and replace all single-quotes with a blank.
    If last position is a bracket, just continue.
    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.
        line (str): The current line string.
    Returns:
        list: The modified list of strings.

    Optimized version utilizing native string methods and regex to eliminate the while loop.
    """
    # 1. Handle "straight_line space straight_line" pattern using regex
    # Replaces the space with the straight_line variable
    line = MISSING_BAR_PATTERN.sub(rf"\1{straight_line}", line)

    # 2. Handle "space right_arrow_corner_up" pattern using native string replace
    # Equivalent to checking new_string[i] == corner and new_string[i-1] == " "
    line = line.replace(f" {right_arrow_corner_up}", f"{straight_line}{right_arrow_corner_up}")

    # 3. Handle the hardcoded block replace
    line = line.replace("  ─╯", "───╯")

    # 4. If the last position is a bracket, strip out the task_delimeter
    if line.endswith("]"):
        line = line.replace(task_delimeter, "")

    output_lines[num] = line

    return output_lines


def _adjust_position_for_arrow(output_lines: list, num: int, position: int) -> int:
    """Adjust position if there's a right arrow corner down to the left."""
    if output_lines[num][position - 1] == right_arrow_corner_down:
        return position - 1
    return position


def _insert_bar_if_blank(new_line: str, position: int) -> str:
    """Insert a bar at the position if there are two blank spaces."""
    if new_line[position - 1] == " " and new_line[position] == " ":
        return new_line[:position] + bar + new_line[position + 1 :]
    return new_line


def _process_elbows(output_lines: list, num: int, previous_line_num: int, position: int) -> int:
    """Handle cases where the current character is an elbow."""
    new_line = output_lines[previous_line_num]
    while output_lines[num][position] == angle_elbow:
        if len(new_line) <= position:
            new_line = new_line.ljust(position + 1, " ")
        if new_line[position] == straight_line or new_line[position] == " ":
            output_lines[previous_line_num] = _insert_bar_if_blank(
                new_line,
                position,
            )
            previous_line_num -= 1
            new_line = output_lines[previous_line_num]
        elif new_line[position] == box_line:
            return -1
        else:
            previous_line_num -= 1
            if previous_line_num == -1:
                break
            new_line = output_lines[previous_line_num]
    return previous_line_num


def cleanup_missing_bars(output_lines: list, num: int, position: int) -> list:
    """
    Cleanup missing bars in the diagram.

    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.
        position (int): The current position in the substring.

    Returns:
        list: The modified list of strings.
    """
    previous_line_num = num - 1

    # Backup a position if "╰" is found just before position.
    position = _adjust_position_for_arrow(output_lines, num, position)

    # Now go through and insert a bars as necessary
    while previous_line_num >= 0:
        new_line = output_lines[previous_line_num]

        # Pad line if necessary
        if len(new_line) < position:
            new_line = new_line.ljust(position + 1, " ")

        # Check for blank spaces to insert bar
        if new_line[position - 1] == " " and new_line[position] == " ":
            output_lines[previous_line_num] = _insert_bar_if_blank(new_line, position)
            previous_line_num -= 1
        elif output_lines[num][position] == angle_elbow:
            previous_line_num = _process_elbows(output_lines, num, previous_line_num, position)
            if previous_line_num == -1:
                break
        else:
            break

    return output_lines


# Go through the diagram looking for and fixing misc. screwed-up stuff.
def cleanup_diagram(
    output_lines: list,
    progress: dict,
) -> list:
    """
    Cleanup the diagram by adding missing straight lines and replacing spaces.
    """
    total_lines = len(output_lines)

    for num, line in enumerate(output_lines):
        # Add missing straight lines in which there is one or more blanks before "╯".
        output_lines = cleanup_missing_straight_lines(output_lines, num, line)

        # Cleanup Task names.
        output_lines = cleanup_task_names(output_lines, num, line)

        # Cleanup dangling elbow " ╮"
        output_lines = cleanup_dangling_elbows(output_lines, num)

        # Cleanup missing bars above Task angles.
        special_deliminaters = [
            angle_elbow,
            right_arrow_corner_down,
            left_arrow_corner_up,
        ]
        _substr, position = find_first_substring_position(line, special_deliminaters)
        if position != -1 and line[position - 1][0] == " ":
            output_lines = cleanup_missing_bars(output_lines, num, position)

        # OPTIMIZED: Update progress text smoothly during large operations without crashing performance
        if "progress_bar" in progress and num % 50 == 0:
            progress["status_label"].set_text(f"Cleaning layout structures: line {num} / {total_lines}")

    # Delete hanging bars "│" and substitute every arrow with beginning and end arrows only.
    return delete_hanging_bars(output_lines)


def find_first_substring_position(string: str, substrings: list) -> tuple:
    """
    Finds the first occurrence of a substring in a string from a list of substrings.

    Args:
        string (str): The string to search in.
        substrings (list): A list of substrings to search for.

    Returns:
        tuple: A tuple where the first item is the substring found and the second item is the index of the substring found.
        If no substrings are found, the first item is None and the second item is -1.
    """
    for substr in substrings:
        index = string.find(substr)
        if index != -1:  # If the substring is found
            return substr, index
    return None, -1


def add_blanks_above_called_tasks(output_lines: list, state: RunState) -> list:
    # Go through and add blanks above called tasks, one for each caller.
    """
    Goes through the output lines and adds a blank line above each called task line
    for each caller task.  The number of blank lines added is determined by the
    number of times each Task is called.  The new output lines are returned.
    """
    name_stoppers = ["(entry)", "(exit)", "[Called by ", "[Calls "]
    new_output_lines = []
    # Where each line ends up once the blanks have been inserted above it.  Every object
    # recorded while the diagram was drawn is sitting on one of these lines, and this is the
    # first of the four steps that move it (see the note above flatten_with_quotes).
    old_to_new = {}
    for old_row, line in enumerate(output_lines):
        task_line = line.find(angle)
        if task_line != -1:
            # We have a task line.  Now get the Task name.
            _, end_name = find_first_substring_position(line, name_stoppers)
            task_name = line[task_line + 3 : end_name - 1] if end_name != -1 else line[task_line + 3 : len(line) - 1]
            # Do we have a task that has been called by another task?
            # One extra for a blank line between upper and previous called task lower connectors.
            if task_name in state.called_task_tracker:
                new_output_lines.extend(
                    [
                        ""
                        for _ in range(
                            state.called_task_tracker[task_name]["total_number"] + 2,
                        )
                    ],
                )

        # Add the original line to the new output lines.
        old_to_new[old_row] = len(new_output_lines)
        new_output_lines.append(line)

    output_lines.clear()
    remap_object_seeds(old_to_new, state=state)
    return new_output_lines
