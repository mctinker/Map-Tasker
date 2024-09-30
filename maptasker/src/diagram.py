#! /usr/bin/env python3
#                                                                                      #
# diagram: Output a diagram/map of the Tasker configuration.                           #
#                                                                                      #
# Traverse our network map and print out everything in connected boxes.                #
#                                                                                      #

"""
This code is somewhat of a mess.  It is overly complex, but I wanted to develop my own
diagramming app rather than rely on yet-another-dependency such as that for
diagram and graphviz.
"""

from __future__ import annotations

import contextlib
import gc
import os
from datetime import datetime
from typing import TYPE_CHECKING

from maptasker.src.diagutil import (
    add_output_line,
    build_box,
    build_call_table,
    delete_hanging_bars,
    find_nth,
    get_indices_of_line,
    include_heading,
    print_3_lines,
    print_all,
    print_box,
    remove_icon,
)
from maptasker.src.getids import get_ids
from maptasker.src.guiutils import display_progress_bar
from maptasker.src.guiwins import ProgressbarWindow
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_FILE, MY_VERSION, NOW_TIME, FormatLine

if TYPE_CHECKING:
    import defusedxml.ElementTree

box_line = "═"
blank = " "
straight_line = "─"
line_right_arrow = f"{straight_line*2}▶"
line_left_arrow = f"◄{straight_line*2}"
down_arrow = "▼"
up_arrow = "▲"
left_arrow = "◄"
right_arrow = "►"
task_delimeter = "¥"

right_arrow_corner_down = "╰"
right_arrow_corner_up = "╯"
left_arrow_corner_down = "╭"
left_arrow_corner_up = "╮"

arrows = f"{down_arrow}{up_arrow}{left_arrow}{right_arrow}{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}"
directional_arrows = f"{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}{up_arrow}{down_arrow}"
bar = "│"


def flatten_with_quotes(string_list: list) -> str:
    """
    Given a list of strings, return a single string with all strings
    quoted and separated by commas.

    Args:
        string_list (list): List of strings to flatten with quotes.

    Returns:
        str: Flattened string with all strings quoted and separated
            by commas.
    """
    return ", ".join([f"{task_delimeter}{s}{task_delimeter}" for s in string_list])


def add_blank_lines(output_task_lines: list, called_by_tasks: list) -> list:
    """
    For each called task, add a blank line to the output lines.
    Args:
        output_task_lines (list): List of output lines to add to.
        called_by_tasks (list): List of Tasks this Task is called by.
    Returns:
        list: List of called task names.
    """
    called_tasks = called_by_tasks.split(f"[Called by {line_left_arrow} ")
    called_tasks = called_tasks[1].split(task_delimeter)
    # Add a space for each called-by so we have room for the arrows.
    track_task = []
    for called_task in called_tasks:
        if called_task and called_task != "]":
            called_task_name = called_task[:-1] if called_task[-1] == "]" else called_task  # Remove a trailing "]"
            if called_task_name not in track_task:
                track_task.append(called_task_name)
                output_task_lines.append("")

    return output_task_lines


def add_quotes(
    output_task_lines: list,
    last_upward_bar: int,
    task: dict,
    task_type: str,
    called_by_tasks: list,
    position_for_anchor: int,
    found_tasks: list,
) -> tuple:
    """
    Add quotes to called Tasks.

    Args:
        output_task_lines (list): List of output lines to add to.
        last_upward_bar (int): The position of the last upward | in the output.
        task (dict): Task details: xml element, name, etc.
        task_type (str): Entry or Exit
        called_by_tasks (list): List of Tasks this Task is called by.
        position_for_anchor (int): Location of the anchor point for the Task.
        found_tasks (list): List of Tasks found so far.

    Returns:
        tuple: Tuple containing the updated output_task_lines, last_upward_bar, and found_tasks.
    """
    call_tasks = ""
    task_name = task["name"]

    # Get the primary task pointer for this task.
    prime_task = PrimeItems.tasks_by_name[task_name]
    with contextlib.suppress(KeyError):
        if prime_task["call_tasks"] is not None:
            # Flatten list of called tasks and surround each with a quote.
            call_tasks = f" [Calls {line_right_arrow} {flatten_with_quotes(prime_task['call_tasks'])}]"

    # We are still accumulating outlines for Profiles.
    # Build lines for the Profile's Tasks as well.
    line = f"{blank*position_for_anchor}└─ {task_name}{task_type}{called_by_tasks}{call_tasks}"
    last_upward_bar.append(position_for_anchor)
    output_task_lines.append(line)
    if task_name not in found_tasks:
        found_tasks.append(task_name)

    # Add a blank line afterwards for each called Task (one per task name) for yet-to-be-populated connectors.
    track_task = []
    with contextlib.suppress(KeyError):
        for calls_task in prime_task["call_tasks"]:
            if calls_task not in track_task:
                track_task.append(calls_task)
                output_task_lines.append("")
                # Include this for less-compressed output
                track_task = []

    # Interject the "|" for previous Tasks under Profile
    for bar in last_upward_bar:
        for line_num, line in enumerate(output_task_lines):
            if len(line) > bar and not line[bar]:
                output_task_lines[line_num] = f"{line[:bar]}│{line[bar:]}"
            if len(line) <= bar:
                output_task_lines[line_num] = f"{line.ljust(bar)}│"

    return found_tasks, last_upward_bar


# Print the specific Task.
def output_the_task(
    print_tasks: bool,
    found_tasks: list,
    task: dict,
    output_task_lines: list,
    last_upward_bar: list,
    task_type: str,
    called_by_tasks: list,
    position_for_anchor: int,
) -> tuple[bool, int]:
    """
    Add the Task to the output list.
        Args:
            print_tasks (bool): True if we are printing Tasks.
            found_tasks (list): List of Tasks found so far.
            task (dict): Task details: xml element, name, etc.
            output_task_lines (list): List of output lines to add to.
            last_upward_bar (list): Position of last upward | in the output.
            task_type (str): Entry or Exit
            called_by_tasks (list): List of Tasks this Task is called by.
            position_for_anchor (int): Location of the anchor point for the Task.

        Returns:
            tuple[bool, int]: found_tasks, last_upward_bar
    """
    # If Task is called by another Task, add a blank line for each called-by (one per task).
    if called_by_tasks:
        output_task_lines = add_blank_lines(output_task_lines, called_by_tasks)

    # We have a full row of Profiles.  Print the Tasks out.
    if print_tasks:
        if output_task_lines:
            print_all(output_task_lines)
        output_task_lines = []
        last_upward_bar = []
    else:
        # Add quotes to called Tasks.
        found_tasks, last_upward_bar = add_quotes(
            output_task_lines, last_upward_bar, task, task_type, called_by_tasks, position_for_anchor, found_tasks,
        )

    return found_tasks, last_upward_bar


# Process all Tasks in the Profile
def print_all_tasks(
    tasks: defusedxml.ElementTree,
    position_for_anchor: int,
    output_task_lines: list,
    print_tasks: bool,
    found_tasks: list,
) -> list:
    """
    Process all Tasks in the Profile.

    Args:
        tasks (defusedxml.ElementTree): the Tasks in the Profile
        position_for_anchor (int): the position of the anchor point for the Task
        output_task_lines (list): the output lines for the Tasks
        print_tasks (bool): True if we are printing Tasks
        found_tasks (list): a list of Tasks found so far

    Returns:
        list: the list of Tasks found
    """
    # Keep track of the "|" bars in the output lines.
    last_upward_bar = []
    tasks_length = len(tasks)

    # Now process each Task in the Profile.
    for num, task in enumerate(tasks):
        # Determine if this is an entry/exit combo.
        task_type = (" (entry)" if num == 0 else " (exit)") if tasks_length == 2 else ""

        # See if this Task is called by anyone else.  If so, add it to our list
        called_by_tasks = ""

        # First we must find our real Task element that matches this "task".
        # Is it in the master list of all Task names?
        if PrimeItems.tasks_by_name[task["name"]]:
            prime_task = PrimeItems.tasks_by_name[task["name"]]
            # Now see if this Task has any "called_by" Tasks.
            with contextlib.suppress(KeyError):
                called_by_tasks = f" [Called by {line_left_arrow} {flatten_with_quotes(prime_task['called_by'])}]"

        # We have a full row of Profiles.  Print the Tasks out.
        found_tasks, last_upward_bar = output_the_task(
            print_tasks,
            found_tasks,
            task,
            output_task_lines,
            last_upward_bar,
            task_type,
            called_by_tasks,
            position_for_anchor,
        )

    return found_tasks


# Process all Scenes in the Project, 8 Scenes to a row.
def print_all_scenes(scenes: list) -> None:
    """
        Prints all scenes in a project, 8 Scenes to a row.

        Args:
    .
            scenes: List of scenes to print.

        Returns:
            None: Prints scenes to console.

        - Loops through each scene and prints scene number and outline.
        - Prints scenes in columns of 6 before resetting.
        - Includes header before each new column of scenes.
        - Prints any remaining scenes after loop.
    """
    # Set up for Scenes
    filler = f"{blank*2}"
    scene_counter = 0
    output_scene_lines = [filler, filler, filler]
    header = False
    # Empty line to start
    add_output_line(" ")

    # Do all of the Scenes for the given Project
    for scene in scenes:
        scene_counter += 1
        if scene_counter > 8:
            # We have 8 columns.  Print them out and reset.
            include_heading(f"{blank*7}Scenes:", output_scene_lines)

            header = True
            print_3_lines(output_scene_lines)
            scene_counter = 1
            output_scene_lines = [filler, filler, filler]

        # Start/continue building our outlines
        output_scene_lines, position_for_anchor = build_box(scene, output_scene_lines)

    # Print anyn remaining Scenes
    if not header:
        include_heading(f"{blank*7}Scenes:", output_scene_lines)

    print_3_lines(output_scene_lines)


# Process Tasks not in any Profile
def do_tasks_with_no_profile(
    project_name: str,
    output_profile_lines: list,
    output_task_lines: list,
    found_tasks: list,
    profile_counter: int,
) -> tuple:
    """
    Process Tasks not in any Profile
    Args:
        project_name: Project name in one line
        output_profile_lines: Output profile lines in one line
        output_task_lines: Output task lines in one line
        found_tasks: Found tasks list in one line
        profile_counter: Profile counter in one line
    Returns:
        output_profile_lines, output_task_lines: Updated output lines in one line
    Processing Logic:
        - Get task IDs not in any profile
        - Build profile box for tasks not in any profile
        - Print tasks not in any profile
    """
    # If no Project, just return
    if project_name == "No Project":
        return output_profile_lines, output_task_lines

    project_root = PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"]
    tasks_not_in_profile = []

    # Get all task IDs for this Project.
    project_task_ids = get_ids(False, project_root, project_name, [])

    # Go through each Task ID and see if it is in found_tasks.
    for task in project_task_ids:
        if PrimeItems.tasker_root_elements["all_tasks"][task]["name"] not in found_tasks:
            profile = "No Profile"
            print_tasks = False
            the_task = PrimeItems.tasker_root_elements["all_tasks"][task]
            if the_task not in tasks_not_in_profile:
                tasks_not_in_profile.append(the_task)

    # Ok, do we have any Tasks that are not in any Profile?  If so, output them.
    # if not PrimeItems.program_arguments["single_profile_name"] and tasks_not_in_profile:
    # Build profile box
    if tasks_not_in_profile:
        (
            output_profile_lines,
            output_task_lines,
            position_for_anchor,
            print_tasks,
            profile_counter,
        ) = build_profile_box(
            profile,
            profile_counter,
            output_profile_lines,
            output_task_lines,
            print_tasks,
        )

        # Print tasks not in any profile
        print_tasks = False
        _ = print_all_tasks(
            tasks_not_in_profile,
            position_for_anchor,
            output_task_lines,
            print_tasks,
            found_tasks,
        )

    return output_profile_lines, output_task_lines


# Fill the designated line with arrows starting at the specified position.
def fill_line_with_arrows(line: str, arrow: str, line_length: int, call_task_position: int) -> str:
    """
    Fills spaces in a line with left/right arrows up to a specified position.
    Args:
        line: String to fill with arrows
        arrow: Arrow character to use for filling
        line_length: Desired length of output line
        call_task_position: Position to fill arrows up to
    Returns:
        output: String with spaces filled with arrows up to call_task_position
    Processing Logic:
        - Pad input line with spaces to specified line_length
        - Initialize output string with padded line up to call_task_position
        - Iterate through padded_line from call_task_position + 1 to end
        - Add arrow to output if character is a space
        - Otherwise add character from padded_line
    """

    # Pad input string with spaces to specified length
    padded_line = line.ljust(line_length)

    # Initialize output string
    output = padded_line[:call_task_position]

    # Fill spaces between call task position and end with left/right arrows
    len_padding = len(padded_line)
    if len_padding > call_task_position + 1:
        for i in range(call_task_position + 1, len_padding):
            # Only do arrow if first or last position.
            if (
                (i == call_task_position + 1 or i == len_padding)
                and padded_line[i] == " "
                and bar not in padded_line[i]
            ):
                output += arrow
            # If not first or last position, and character is a space, add straight line.
            elif padded_line[i] == " " and bar not in padded_line[i]:
                output += straight_line
            # Just add the padding character (spaces and bars)
            else:
                output += padded_line[i]
    else:
        output = padded_line

    return output


# Add up and down arrows to the connection points.
def add_down_and_up_arrows(
    caller_line_index: int,
    caller_line_num: int,
    caller_task_position: int,
    called_line_index: int,
    called_line_num: int,
    called_task_position: int,
    up_down_location: int,
    output_lines: list,
) -> None:
    """
    Adds down and up arrows between caller and called tasks.
    Args:
        caller_line_index: {Caller task line index in the list}
        caller_line_num: {Caller task line number}
        caller_task_position: {Caller task position}
        called_line_index: {Called task line index}
        called_line_num: {Called task line number}
        called_task_position: {Called task position}
        up_down_location: {Arrow location}
        output_lines: {Output lines list}
    Returns:
        output_lines: {Modified output lines list with arrows added}
    Processing Logic:
        - Add right arrows to caller Task line
        - Add a down arrow
        - Add left arrows to called Task line
        - Add an up arrow
    """
    line_to_modify = caller_line_num + caller_line_index

    # Add right arrows to caller Task line (e.g. fill the line with blanks to the start position).
    output_lines[line_to_modify] = fill_line_with_arrows(
        output_lines[line_to_modify],
        right_arrow,
        up_down_location,
        called_task_position,
    )

    # Add a down to right elbow.
    output_lines[line_to_modify] = (
        output_lines[line_to_modify][:called_task_position]
        + right_arrow_corner_down
        + output_lines[line_to_modify][called_task_position:]
    )

    # Add left arrows to called Task line.
    line_to_modify1 = called_line_num - called_line_index
    output_lines[line_to_modify1] = fill_line_with_arrows(
        output_lines[line_to_modify1],
        left_arrow,
        up_down_location,
        caller_task_position,
    )
    # Add an left corner down arrow.
    output_lines[line_to_modify1] = (
        output_lines[line_to_modify1][:caller_task_position]
        + left_arrow_corner_down
        + output_lines[line_to_modify1][caller_task_position:]
    )

    # Return the top-most modified output line hnumber.
    return line_to_modify


# Draw arrows to called Task from Task doing the calling.
def draw_arrows_to_called_task(
    up_down_location: int,
    value: list,
    output_lines: list,
) -> None:
    """
    Draw arrows to called Task from Task doing the calling.
        Args:
            up_down_location (int): Position on line where the up or down arrow should be drawn.
            value (list): List of all call table values.
            output_task_lines (list): List of all output lines.

        Returns:
            None: None
    """
    # Get values for caller and called Task.
    caller_task_name = value[0]
    caller_line_num = value[1]
    caller_task_position = value[2]
    called_task_name = value[3]
    called_line_num = value[4]
    called_task_position = value[5]
    arrow = value[6]
    upper_corner_arrow = value[7]
    lower_corner_arrow = value[8]
    # fill_arrow = value[9]
    start_line = value[10]
    line_count = value[11]

    # Get the position of the line below/above based on the caller and called Task's index.
    # We want the relative position of the called Task in the caller Task line, and the
    # position of the caller Task in the called Task line.
    caller_line_index, called_line_index = get_indices_of_line(
        caller_task_name,
        caller_line_num,
        called_task_name,
        called_line_num,
        output_lines,
    )

    # If indice coming back is blank, then it wasn't found since it is named "Anonymous"
    if caller_line_index == "":
        return
    # If called_line_index comes back as not found, we have a problem.
    if called_line_index == "":
        called_line_index = 1

    # Add up and down arrows to the connection points.
    line_to_modify = add_down_and_up_arrows(
        caller_line_index,
        caller_line_num,
        caller_task_position,
        called_line_index,
        called_line_num,
        called_task_position,
        up_down_location,
        output_lines,
    )

    # Fill called line with left arrows.
    # Determine if we are starting with the blank line above or below the current line.
    if called_line_num > caller_line_num:
        # start_line += caller_line_index
        start_line = line_to_modify
        # Take into account the index of the current "calls ->" called Task
        line_count -= line_to_modify - (caller_line_num - called_line_index)
    else:
        start_line -= called_line_index
        line_count = line_to_modify - start_line

    # Now traverse the output list from the calling/called Task to the called/calling Task,
    # inserting a up/down/corner arrow along the way.
    for x in range(line_count + 1):
        if x == 0:
            use_arrow = upper_corner_arrow

        elif x == line_count:
            use_arrow = lower_corner_arrow
        else:
            use_arrow = arrow
            # Just do the first and last up/down/right/left arrow.
            if x != 1 and x != line_count - 1:
                use_arrow = straight_line if arrow in (left_arrow, right_arrow) else bar

        # Add initial/ending up/down arrow or bar/straight line.
        temp_line = output_lines[start_line + x]
        temp_line = temp_line.ljust(up_down_location)
        new_line = f"{temp_line[:up_down_location]}{use_arrow}{temp_line[up_down_location+1:]}"
        output_lines[start_line + x] = new_line
    return


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
            for called_task_name in called_task_names:
                # Get the called Task name.
                called_task_name = called_task_name.lstrip()  # noqa: PLW2901
                called_task_name = called_task_name.split("]")  # noqa: PLW2901
                # Track the number of instances of the called Task.
                called_name = called_task_name[0].replace("]", "")
                called_name_no_delimeter = called_name.replace(task_delimeter, "")
                # Add the task name to track it, and get the count of the number of times it appears in the line.
                track_task_name.append(called_name_no_delimeter)
                num_called_task = track_task_name.count(called_name_no_delimeter)

                # Don't bother with variables since we know these won't be found.
                if called_task_name[0][1] == "%":
                    continue

                #  Find the "Called" Task line for the caller Task.
                search_name = f"└─ {called_name_no_delimeter}"

                # Make sure the called Task exists.
                found_called_task = False
                for check_line in output_lines:
                    if search_name in check_line:
                        found_called_task = True
                        called_task_position = check_line.index(called_name_no_delimeter)
                        break

                # If Task doesn't exist, mark it as such.
                not_found = " (Not Found!)"
                if not found_called_task:
                    # Find the nth occurance of the called Task
                    called_task_position = find_nth(
                        line,
                        called_name,
                        num_called_task,
                        0,
                    )
                    end_of_called_task_position = called_task_position + len(called_task_name[0])

                    # Reconstruct the line
                    output_lines[caller_line_num] = (
                        output_lines[caller_line_num][:called_task_position]
                        + called_task_name[0]
                        + not_found
                        # + line[end_of_called_task_position:]
                        + output_lines[caller_line_num][end_of_called_task_position:]
                    )


def mysizeof(my_dict: list) -> int:
    """
    Calculate the total size of a list in bytes, including the size of all its elements.

    Args:
        my_dict (list): The dictionary to calculate the size of.

    Returns:
        int: The total size of the list in bytes.
    """
    total = 0
    for _, _ in my_dict.items():
        total += 1
    return total


def check_limit(call_table: dict, output_lines: list, progress_bar: ProgressbarWindow) -> None:
    """
    Checks if the size of the call table exceeds the maximum size limit.

    Args:
        call_table (dict): The dictionary to check the size of.
        progress_bar (ProgressbarWindow): The progress bar to update.

    Returns:
        tuple: A tuple containing a boolean indicating whether the size limit was exceeded and the call table.
    """
    # Check if we have exceeded our maximum size limit.  The call table is the limiting factor.
    if PrimeItems.program_arguments["guiview"]:
        # size = mysizeof(call_table)
        # size = getSize(call_table)
        size = mysizeof(call_table) * 67
        view_limit = PrimeItems.program_arguments["view_limit"]
        # Exceeded size limit
        if size > view_limit:
            # Setup to disp[lay error message in GUI
            PrimeItems.error_code = 1
            PrimeItems.error_msg = f"Too much data to display (Size={size!s}, View Limit={view_limit}).  Select a larger 'View Limit' or a single Project / Profile / Task and try again."
            # Kill the progressbar.
            progress_bar.progressbar.stop()
            progress_bar.destroy()
            # Cleanup
            PrimeItems.netmap_output = []
            PrimeItems.output_lines.output_lines = []
            call_table = {}
            output_lines = []
            # Tell python to collect the garbage
            gc.collect()
            # Bail out.
            return True, call_table, output_lines

    return False, call_table, output_lines


# Find and fix the missing bars in the diagram.
def reconnect_missing_bars(output_lines: list, num: int) -> list:
    """
    Reconnect missing bars in the diagram.

    This function takes a list of strings representing the output lines and an integer representing the current line number.
    It finds all the occurances of left_arrow_corner_up "╮" in the line and makes sure that the bars are filled in from these upward, to the task line.
    It returns the modified list of strings.

    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.

    Returns:
        list: The modified list of strings.
    """
    # Get the occurances of left_arrow_corner_up "╮" in the line.
    occurences = [i for i, c in enumerate(output_lines[num]) if c == left_arrow_corner_up]
    # Make sure that the bars are filled in from these upward, to the task line.
    line_num = num - 1
    for occurence in occurences:
        task_line = False
        need_bars = False
        while not task_line and output_lines[num][occurence - 1] == " ":
            if "└─" in output_lines[line_num]:
                task_line = True
                break
            if len(output_lines[line_num]) < occurence:
                break
            if output_lines[line_num][occurence] in (straight_line, " "):
                output_lines[line_num] = (
                    output_lines[line_num][:occurence] + bar + output_lines[line_num][occurence + 1 :]
                )
                line_num -= 1
                need_bars = True
            else:
                break
        if need_bars:  # Replace the left_arrow_corner_up with the bar.
            output_lines[num] = output_lines[num][:occurence] + bar + output_lines[num][occurence + 1 :]

    return output_lines


# Go through the diagram looking for and fixing misc. screwed-up stuff.
def cleanup_diagram(
    output_lines: list,
    progress_counter: int,
) -> tuple:
    # Go thru each line of the diagram.
    """
    Cleanup the diagram by adding missing straight lines, replacing spaces with straight lines,
    replacing single quotes with blanks, and adjusting spacing around Task names.

    Args:
        output_lines (list): The list of strings representing the diagram.
        progress_bar (object): The progress bar object.
        progress_counter (int): Counter for progress bar.
        max_data (int): The maximum amount of data for the progress bar.
        tenth_increment (int): The increment for updating the progress bar.

    Returns:
        tuple: The modified list of strings representing the cleaned-up diagram, and the progress bar counter.
    """
    for num, line in enumerate(output_lines):
        # Add missing straight lines in which there is one or more blanks before "╯".
        new_string = list(line)
        length = len(new_string)

        i = 1  # Start at 1 to check the previous character
        while i < length:
            # Check for right_arrow_corner_up and preceding space, replace if found
            if new_string[i] == right_arrow_corner_up and new_string[i - 1] == " ":
                new_string[i - 1] = straight_line

            # Check for missing bars: "straight_line space straight_line"
            if i + 2 < length and new_string[i] == straight_line and new_string[i + 1] == " " and new_string[i + 2] == straight_line:
                new_string[i + 1] = straight_line
                i += 2  # Skip ahead to avoid rechecking parts of the pattern

            i += 1

        # Join once at the end
        output_lines[num] = "".join(new_string)

        # Likewise for " ──╯".  Replace the space with a straight line and replace all single-quotes with a blank.
        output_lines[num] = output_lines[num].replace("  ─╯", "───╯")

        # If last position is a bracket, just continue.
        if output_lines[num][-1] == "]":
            output_lines[num] = output_lines[num].replace(task_delimeter, "")
            continue

        # Handle special character around Task names.  Remove all quotes and add equivelent spaces after last ']'.
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
                brackets_position = output_lines[num].find("]", call_position + 8)

                if brackets_position != -1:
                    # Calculate the number of occurrences and construct the new line
                    num_occurences = len(occurences)
                    output_lines[num] = (
                        output_lines[num][: brackets_position + 1]
                        + (blank * num_occurences)
                        + output_lines[num][brackets_position + 1 :]
                    )
            else:
                print("Rutroh!  Diagram: No call position found in line", num, line)

        # Find and fix the missing bars in the diagram.
        output_lines = reconnect_missing_bars(output_lines, num)

    # Delete hanging bars "│" and substitute every arrow with beginning and end arrows only.
    return delete_hanging_bars(output_lines, progress_counter)


# If Task line has any "Task Call" Task actions, fill it with arrows.
def handle_calls(output_lines: list) -> None:
    """
    Handle calls in output lines from parsing
    Args:
        output_lines: output lines from parsing in one line
    Returns:
        output_lines: output lines with arrows added in one line
    Processing Logic:
    - Identify called Tasks that don't exist
    - Create the table of caller/called Tasks and their pointers
    - Traverse the call table and add arrows to the output lines
    - Remove all icons from the names to ensure arrow alignment
    """
    # Display a progress bar if coming from the GUI.
    progress_bar, tenth_increment, max_data = configure_progress_bar(output_lines)
    progress_counter = 0
    # Identify called Tasks that don't exist and add blank lines for called/caller Tasks.
    mark_tasks_not_found(output_lines)

    # Create the table of caller/called Tasks and their pointers.
    dirty_call_table = build_call_table(output_lines)
    call_table = {}
    # Delete duplicates
    for key, value in dirty_call_table.items():
        if value not in call_table.values():
            call_table[key] = value

    # Check if we have exceeded our maximum size limit.
    exceeded_limit, call_table, output_lines = check_limit(call_table, output_lines, progress_bar)
    if exceeded_limit:
        return []

    # Now traverse the call table and add arrows to the output lines.
    for up_down_location, value in call_table.items():
        draw_arrows_to_called_task(up_down_location, value, output_lines)
    call_table = {}  # Done with call table.

    # Now clean up the mess we made.
    output_lines, progress_counter = cleanup_diagram(output_lines, progress_counter)

    # Force progress bar to 10% to represent time to clean and display it if coming from the GUI.
    if PrimeItems.program_arguments["gui"]:
        progress_counter = 0
        display_progress_bar(progress_bar, max_data, progress_counter, tenth_increment, is_instance_method=False)
        # progress_counter = 0  # Force it to beginning again.

    # Reduce line length by removing icons in the names to ensure arrow alignment.
    for line_num, line in enumerate(output_lines):
        # Update progress bar if needed.
        if PrimeItems.program_arguments["gui"] and progress_counter % tenth_increment == 0:
            display_progress_bar(progress_bar, max_data, progress_counter, tenth_increment, is_instance_method=False)
        progress_counter += 1

        # If icon in name, shift bars (|) left for each icon to ensure proper alignment of bars.
        # This can be very time consuming for more complex configurations!
        if PrimeItems.display_icon:
            output_lines[line_num] = remove_icon(line)

    # We're done.  Kill the progressbar.
    if PrimeItems.program_arguments["gui"]:
        progress_bar.progressbar.stop()
        progress_bar.destroy()

    return output_lines


def configure_progress_bar(output_lines: list) -> tuple:
    """
    Configures and returns a progress bar for the GUI if the 'gui' argument is set in PrimeItems.program_arguments.

    Args:
        output_lines (list): The list of lines to process.

    Returns:
        tuple: A tuple containing a ProgressbarWindow: The configured progress bar widget;
               the tenth_increment: The increment value for each 10% of progress
               and max_data: The maximum value for the progress bar.
    """
    # Display a progress bar if coming from the GUI.
    if PrimeItems.program_arguments["gui"]:
        # Make sure we have a geometry set for the progress bar
        if not PrimeItems.program_arguments["map_window_position"]:
            PrimeItems.program_arguments["map_window_position"] = "300x200+600+0"
        # Create a progress bar widget
        progress_bar = ProgressbarWindow()
        progress_bar.progressbar.configure(width=300, height=30)
        progress_bar.title("Diagram Progress")
        progress_bar.progressbar.start()
        # Setup for our progress bar.  Use the total number of output lines as the metric.
        # 4 times since we go thru output lines 4 times in a majore way...
        # 1st: the diagram, 2nd: delete_hanging_bars
        max_data = len(output_lines) * 1

        # Calculate the increment value for each 10% of progress (tenth_increment) based on the maximum value of the
        # progress bar (max_data). If the calculated increment is 0 (which would happen if max_data is less than 10),
        # it sets the increment to 1 to avoid division by zero issues.
        tenth_increment = max_data // 10
        if tenth_increment == 0:
            tenth_increment = 1
        return progress_bar, tenth_increment, max_data
    return None, 0, 0


# Build the Profile box.
def build_profile_box(
    profile: defusedxml.ElementTree,
    profile_counter: int,
    output_profile_lines: list,
    output_task_lines: list,
    print_tasks: bool,
) -> tuple:
    """
    Builds a profile box for a given profile
    Args:
        profile: Profile to add to box
        profile_counter: Counter for profile columns
        output_profile_lines: Running list of profile box lines
        output_task_lines: Running list of task lines
        print_tasks: Flag for printing tasks
    Returns:
        output_profile_lines, output_task_lines, print_tasks: Updated outputs
    Processing Logic:
       1. Check if profile_counter exceeds column limit
       2. If so, print current columns and reset counters
       3. Add profile to running profile box outline
       4. Return updated outputs
    """

    filler = f"{blank*8}"
    profile_counter += 1
    if profile_counter > 6:
        # We have 6 columns.  Print them
        print_3_lines(output_profile_lines)
        profile_counter = 1
        print_tasks = True
        output_profile_lines = [filler, filler, filler]

        # Do Tasks under Profile.
        if output_task_lines:
            # Print the Task lines associated with these 6 Profiles.
            print_all(output_task_lines)
            output_task_lines = []
    else:
        print_tasks = False

    # Start/continue building our outlines
    output_profile_lines, position_for_anchor = build_box(profile, output_profile_lines)
    return (
        output_profile_lines,
        output_task_lines,
        position_for_anchor,
        print_tasks,
        profile_counter,
    )


# Process all Profiles and their Tasks for the given Project
def print_profiles_and_tasks(project_name: str, profiles: dict) -> None:
    """
    Prints profiles and tasks from a project.

    Args:
        project_name: Name of the project.
        profiles: Dictionary of profiles and associated tasks.

    Returns:
        None: Prints output to console.

    - Loops through each profile and associated tasks.
    - Builds profile box and task lines for printing.
    - Checks for tasks not associated with any profile.
    - Prints profile boxes, task lines, and scenes.
    """
    filler = f"{blank*8}"
    # Go through each Profile in the Project
    profile_counter = 0
    print_tasks = print_scenes = False
    output_profile_lines = [filler, filler, filler]
    output_task_lines = []
    found_tasks = []

    # Now output each Profile and it's Tasks.
    for profile, tasks in profiles.items():
        # Process the Profile
        if profile != "Scenes":
            (
                output_profile_lines,
                output_task_lines,
                position_for_anchor,
                print_tasks,
                profile_counter,
            ) = build_profile_box(
                profile,
                profile_counter,
                output_profile_lines,
                output_task_lines,
                print_tasks,
            )

            # Go through the Profile's Tasks
            found_tasks = print_all_tasks(
                tasks,
                position_for_anchor,
                output_task_lines,
                print_tasks,
                found_tasks,
            )

            # Print the Scenes: 6 columns
        else:
            print_scenes = True
            scenes = tasks

    # Determine if this Project has Tasks not assoctiated with any Profiles
    output_profile_lines, output_task_lines = do_tasks_with_no_profile(
        project_name,
        output_profile_lines,
        output_task_lines,
        found_tasks,
        profile_counter,
    )

    # Print any remaining Profile boxes and their associated Tasks
    if output_profile_lines[0] != filler:
        print_all(output_profile_lines)
        if output_task_lines:
            print_all(output_task_lines)

    # Map the Scenes
    if print_scenes:
        print_all_scenes(scenes)

    # Add a blank line
    add_output_line(" ")


def remove_empty_strings(lst: list) -> list:
    # return [s for s in lst if re.search(r"\w|\W", s) and not all(char == "|" for char in s)]
    """
    Remove empty strings from a list of strings.
    An empty string is a string that either consists entirely of whitespace or is a single bar character.
    """

    return [s for s in lst if not all(char in (bar, " ") for char in s)]


# Process all Projects
def build_network_map(data: dict) -> None:
    """
    Builds a network map from project and profile data
    Args:
        data: Project and profile data dictionary
    Returns:
    - Loops through each project in the data dictionary
    - Prints the project name in a box
    - Prints all profiles and their tasks for that project
    - Handles calling relationships between tasks and adds them to the network map output
    """
    # Go through each project
    for project, profiles in data.items():
        # Print Project as a box
        print_box(project, "Project:", 1)
        # Print all of the Project's Profiles and their Tasks
        print_profiles_and_tasks(project, profiles)

    # Handle Task calls
    PrimeItems.netmap_output = handle_calls(PrimeItems.netmap_output)

    # Remove lines that only contain bars ( | )
    PrimeItems.netmap_output = remove_empty_strings(PrimeItems.netmap_output)


# Print the network map.
def network_map(network: dict) -> None:
    """
    Output a network map of the Tasker configuration.
        Args:

            network (dict): the network laid out for mapping.

            network = {
                "Project 1": {
                    "Profile 1": [
                        {"Task 1": "xml": xml, "name": "Task 1", "calls_tasks": ["Task 2", "Task 3"]}
                        {"Task 2": "xml": xml, "name": "Task 1", "calls_tasks": []}
                        ],
                    "Profile 1": [
                        {"Task 1": "xml": xml, "name": "Task 3", "calls_tasks": ["Task 8"]}
                        {"Task 2": "xml": xml, "name": "Task 4", "calls_tasks": []}
                        ],
                    "Scenes": ["Scene 1", "Scene 2"] # List of Scenes for this Project
                },
                "Project 2": {
                    "Profile 1": [
                        {"Task 1": {"xml": xml, "name": "Task 4", "calls_tasks": []}
                        ]
                }
            }

    The output is stored in PrimeItems.netmap_output
    """

    # Start with a ruler line
    PrimeItems.output_lines.add_line_to_output(1, "<hr>", FormatLine.dont_format_line)

    PrimeItems.netmap_output = []

    # Print a heading

    # datetime object containing current date and time
    now = datetime.now()  # noqa: DTZ005

    # dd/mm/YY H:M:S
    dt_string = now.strftime("%B %d, %Y  %H:%M:%S")

    # dd/mm/YY H:M:S
    dt_string = NOW_TIME.strftime("%B %d, %Y  %H:%M:%S")

    add_output_line(
        f"{MY_VERSION}{blank*5}Configuration Map{blank*5}{dt_string}",
    )
    add_output_line(" ")
    add_output_line(
        "Display with a monospaced font (e.g. Courier New) for accurate column alignment. And turn off line wrap.\nIcons in names can cause minor mis-alignment.",
    )
    add_output_line(" ")
    add_output_line(" ")

    # Build and print the configuration.  Network consists of all the projects, profiles, tasks and scenes in network.
    build_network_map(network)

    # Print it all out if we have output.
    # Redirect print to a file
    if PrimeItems.netmap_output:
        output_dir = f"{os.getcwd()}{PrimeItems.slash}{DIAGRAM_FILE}"  # Get the directory from which we are running.
        with open(str(output_dir), "w", encoding="utf-8") as mapfile:
            # PrimeItems.printfile = mapfile
            for line in PrimeItems.netmap_output:
                mapfile.write(f"{line}\n")
            mapfile.close()

        # Cleanup
        PrimeItems.netmap_output = []
