from typing import List, Set, Tuple
#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# netmap: Output a network map of the Tasker configuration.                            #
#                                                                                      #
# Traverse our network map and print out everything in connected boxes.                #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import contextlib
import string
import tkinter
import tkinter.font
from datetime import datetime
from string import printable

from maptasker.src.getids import get_ids
from maptasker.src.sysconst import MY_VERSION, UNKNOWN_TASK_NAME, FormatLine

box_line = "═"
blank = " "
straight_line = "─"
line_right_arrow = f"{straight_line*2}▶"
line_left_arrow = f"◄{straight_line*2}"
down_arrow = "↓"
up_arrow = "↑"
left_arrow = "←"
right_arrow = "→"
right_arrow_corner_down = "↘"
right_arrow_corner_up = "↗"
left_arrow_corner_down = "↙"
left_arrow_corner_up = "↖"
arrows = f"{down_arrow}{up_arrow}{left_arrow}{right_arrow}{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}"
directional_arrows = f"{right_arrow_corner_down}{right_arrow_corner_up}{left_arrow_corner_down}{left_arrow_corner_up}{up_arrow}{down_arrow}"


# ##################################################################################
# Add line to our output queue.
# ##################################################################################
def add_output_line(primary_items, line):
    primary_items["netmap_output"].append(line)


# ##################################################################################
# Given an array of 3 string elements, format them with fillers for headings
# ##################################################################################
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
    - Replaces the third line of output_lines with the filler line"""
    filler = f"{blank*len(header)}"
    output_lines[0] = f"{filler}{output_lines[0]}"
    output_lines[1] = f"{header}{output_lines[1]}"
    output_lines[2] = f"{filler}{output_lines[2]}"


# ##################################################################################
# Given a list of 3 text elements, print them.
# ##################################################################################
def print_3_lines(primary_items, lines):
    """
    Prints 3 lines from a list of items
    Args:
        primary_items: List of items to print from
        lines: List of line numbers to print
    Returns: 
        None: Does not return anything
    - Check if lines is a list
    - Loop through first 3 items of lines list
    - Print corresponding item from primary_items"""
    do_list = isinstance(lines, list)
    for line in range(3):
        if do_list:
            add_output_line(primary_items, lines[line])
        else:
            add_output_line(primary_items, line)


# ##################################################################################
# Given a list of text strings, print all of them.
# ##################################################################################
def print_all(primary_items, lines):
    for line in lines:
        add_output_line(primary_items, line)


# ##################################################################################
# Given a text string and title, enclose them in a box and print the box.
# ##################################################################################
def print_box(primary_items, name, title, indent, counter):
    """
    Prints a box with title, name and counter.
    
    Args:
        primary_items: Primary items to print before the box
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
    print_3_lines(primary_items, box)


# ##################################################################################
# Get the dimensions of a text string using tkinter to calculate the width needed
# ##################################################################################
def width_and_height_calculator_in_pixel(txt, fontname, fontsize):
    font = tkinter.font.Font(family=fontname, size=fontsize)
    return [font.measure(txt), font.metrics("linespace")]


# ##################################################################################
# Wew have an icon in our name.  Remove any padding as necessary
# ##################################################################################
def fix_icon(name):
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
            _ = tkinter.Frame()  # Initialize Tkinter
            # We have the icon.
            char_dimension = width_and_height_calculator_in_pixel(
                char, "Courier New", 12
            )
            trailer = "" if char_dimension[0] > char_dimension[1] else blank
            break
    return trailer


# ##################################################################################
# Remove a character from a string at a specific location and return the modified 
# string.
# ##################################################################################
def remove_char(string, index):
    """
    Remove character from string at given index and return modified string
    
    Args:
        string (str): The input string
        index (int): The index to remove the character at
        
    Returns:
        str: String with character removed at given index
    
    - Check if the index is within the length of the string
    - Slice the string from beginning to index and from index+1 to end 
    - Concatenate both slices to remove the character at index
    - Return the modified string
    """
    """
    Remove character from string at given index and return modified string
    
    Args:
        string (str): The input string
        index (int): The index to remove the character at
        
    Returns:
        str: String with character removed at given index
    """
    return string[:index] + string[index+1:]


# ##################################################################################
# If an icon is found in the string passed in, remove it and return modified string.
# ##################################################################################
def remove_icon(text: str) -> str:
    """
    Remove any icon characters from a string
    
    Args:
        text (str): The input string
        
    Returns: 
        str: The string with icon characters removed
    """
    arrow_position: int = next((text.index(char) for char in arrows if char in text), 0)
    if arrow_position == 0:
        return text

    # Define additional "printable" characters to allow.
    extra_cars: str = f"│└─╔═║╚╝╗▶◄{arrows}"
    # List of printable ASCII characters
    printable: Set[str] = set(string.printable)
    for char in extra_cars:
        printable.add(char)

        # Remove a blank for every incon found on line with an arrow.
    output: str = text
    blanks: int = sum(char not in printable for char in text)
    if blanks != 0:

        # Drop here if there is at least one icon.
        for find_arrow in directional_arrows:
            found_arrow = text.find(find_arrow)
            if found_arrow != -1:
                # Remove the icon and any blanks
                output = remove_char(text, found_arrow-1)
                return output + blank*blanks
        
        output = text[:arrow_position - blanks] + text[arrow_position:]

    # Remove any icon characters from the string
    return output


# ##################################################################################
# Given a name, enclose it in a text box
# ##################################################################################
def build_box(name, counter, output_lines):
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


# ##################################################################################
# Print the specific Task.
# ##################################################################################
def output_the_task(
    primary_items: dict,
    print_tasks: bool,
    found_tasks: list,
    task: dict,
    output_task_lines: list,
    last_upward_bar: list,
    task_type: str,
    called_by_tasks: list,
    position_for_anchor: int,
) -> tuple[bool, int]:
    """_summary_
    Add the Task to the output list.
        Args:
            primary_items (dict): _description_
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
    # We have a full row of Profiles.  Print the Tasks out.
    if print_tasks:
        if output_task_lines:
            print_all(primary_items, output_task_lines)
        output_task_lines = []
        last_upward_bar = []
    else:
        # Is this Task calling other Tasks?
        call_tasks = ""
        with contextlib.suppress(KeyError):
            if task["call_tasks"]:
                call_tasks = (
                    f" [Calls {line_right_arrow} {', '.join(task['call_tasks'])}]"
                )

        # We are still accumating outlines for Profiles.
        # Build lines for the Profile's Tasks as well.
        line = f'{blank*position_for_anchor}└─ {task["name"]}{task_type}{called_by_tasks}{call_tasks}'
        last_upward_bar.append(position_for_anchor)
        output_task_lines.append(line)
        if task["name"] not in found_tasks:
            found_tasks.append(task["name"])

        # Interject the "|" for previous Tasks under Profile
        for bar in last_upward_bar:
            for line_num, line in enumerate(output_task_lines):
                if len(line) > bar and not line[bar]:
                    output_task_lines[line_num] = f"{line[:bar]}│{line[bar:]}"
                if len(line) <= bar:
                    output_task_lines[line_num] = f"{line.ljust(bar)}│"

    return found_tasks, last_upward_bar


# ##################################################################################
# Process all Tasks in the Profile
# ##################################################################################
def print_all_tasks(
    primary_items,
    project_name,
    tasks,
    position_for_anchor,
    output_task_lines,
    print_tasks,
    found_tasks,
    ):
    """
    Print all tasks in a profile
    
    Args:
        primary_items: Primary profile items
        project_name: Name of the project
        tasks: List of tasks
        position_for_anchor: Position for anchor 
        output_task_lines: Output task lines  
        print_tasks: Print tasks flag
        found_tasks: Found tasks
    
    Returns: 
        found_tasks: Updated found tasks
    
    Processing Logic:
    - Loop through each task in tasks list
    - Rename unnamed tasks to "Anonymous" + number  
    - Determine if task is entry/exit
    - Find real task element that matches and check if task is called by any other
    - Output the task details
    - Return updated found tasks
    """

    # Keep track of the "|" bars in the output lines.
    last_upward_bar = []
    tasks_length = len(tasks)

    # Now process each Task in the Profile.
    for num, task in enumerate(tasks):
        # Rename unnamed/anonymous Tasks to "Anonymous" + number
        if task["name"] == UNKNOWN_TASK_NAME:
            task["name"] = "Anonymous"

        # Determine if this is an entry/exit combo.
        if tasks_length == 2:
            task_type = " (entry)" if num == 0 else " (exit)"
        else:
            task_type = ""

        # See if this Task is called by anyone else.  If so, add it to our list
        called_by_tasks = ""

        # First we must find our real Task element that matches this "task".
        for temp_task_id in primary_items["tasker_root_elements"]["all_tasks"]:
            temp_task = primary_items["tasker_root_elements"]["all_tasks"][temp_task_id]
            if task["xml"] == temp_task["xml"]:
                # Now see if this Task has any "called_bvy" Tasks.
                with contextlib.suppress(KeyError):
                    called_by_tasks = f" [Called by {line_left_arrow} {', '.join(temp_task['called_by'])}]"
                    called_by_tasks = called_by_tasks.replace(
                        UNKNOWN_TASK_NAME, "Anonymous"
                    )
                break

        # We have a full row of Profiles.  Print the Tasks out.
        found_tasks, last_upward_bar = output_the_task(
            primary_items,
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


# ##################################################################################
# Process all Scenes in the Project
# ##################################################################################
def print_all_scenes(primary_items, scenes):
    """
    Prints all scenes in a project.
    
    Args:
        primary_items: Primary items to print.
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
    add_output_line(primary_items, " ")

    # Do all of the Scenes for the given Project
    for scene in scenes:
        scene_counter += 1
        if scene_counter > 8:
            # We have 6 columns.  Print them out and reset.
            include_heading(f"{blank*7}Scenes:", output_scene_lines)

            header = True
            print_3_lines(primary_items, output_scene_lines)
            scene_counter = 1
            output_scene_lines = [filler, filler, filler]

        # Start/continue building our outlines
        output_scene_lines, position_for_anchor = build_box(
            scene, scene_counter, output_scene_lines
        )

    # Print anyn remaining Scenes
    if not header:
        include_heading(f"{blank*7}Scenes:", output_scene_lines)

    print_3_lines(primary_items, output_scene_lines)


# ##################################################################################
# Process Tasks not in any Profile
# ##################################################################################
def do_tasks_with_no_profile(
    primary_items,
    project_name,
    output_profile_lines,
    output_task_lines,
    found_tasks,
    profile_counter,
    ):
    """
    Performs tasks with no associated profile
    Args:
        primary_items: Primary items from the tasker data
        project_name: Name of the project
        output_profile_lines: Output lines for profiles
        output_task_lines: Output lines for tasks 
        found_tasks: Tasks already found
        profile_counter: Counter for profiles
    Returns: 
        output_profile_lines, output_task_lines: Updated output lines
    Processing Logic:
        - Gets task IDs not in any profile for the given project
        - Prints "No Profile" profile box
        - Prints all tasks not in any profile
    """

    project_root = primary_items["tasker_root_elements"]["all_projects"][project_name][
        "xml"
    ]
    tasks_not_in_any_profile = []
    if task_ids := get_ids(primary_items, False, project_root, project_name, []):
        tasks_not_in_any_profile.extend(
            primary_items["tasker_root_elements"]["all_tasks"][task_id]
            for task_id in task_ids
            if primary_items["tasker_root_elements"]["all_tasks"][task_id]["name"]
            not in found_tasks
        )
    if tasks_not_in_any_profile:
        profile = "No Profile"
        print_tasks = False
        (
            output_profile_lines,
            output_task_lines,
            position_for_anchor,
            print_tasks,
            profile_counter,
        ) = build_profile_box(
            primary_items,
            profile,
            profile_counter,
            output_profile_lines,
            output_task_lines,
            print_tasks,
        )

        # Go through the Tasks not in any profile
        print_tasks = False
        found_tasks = print_all_tasks(
            primary_items,
            project_name,
            tasks_not_in_any_profile,
            position_for_anchor,
            output_task_lines,
            print_tasks,
            found_tasks,
        )

    return output_profile_lines, output_task_lines


# ##################################################################################
# Replace all characters after the "]" with arrow, except "│".
# ##################################################################################
def replace_after_bracket(line: str, arrow: str, line_length) -> str:
    """_summary_
    Replace all characters after the "]" with specified arrow, except "│".
        Args:
            line (str): Line to process
            arrow (str): Arrow character to insert

        Returns:
            str: Resulting changed line
    """
    # Find the end of the string.
    end_string = line.rfind("]")
    output = line[: end_string + 1]
    line = line.ljust(line_length)

    # Fill spaces with arrows, as long as it isn't a bar.
    for char_pos in range(end_string + 1, len(line)):
        if line[char_pos] == " " and "│" not in line[char_pos]:
            output += arrow
        else:
            output += line[char_pos]

    return output


# ##################################################################################
# Draw arrows to called Task from Task doing the calling.
# ##################################################################################
def draw_arrows_to_called_task(
    up_down_location: int,
    value: list,
    output_lines: list,
) -> None:
    """_summary_
    Draw arrows to called Task from Task doing the calling.
        Args:
            up_down_location (int): Position on line where the up or down arrow should be drawn.
            value (list): List of all call table values.
            output_task_lines (list): List of all output lines.

        Returns:
            None: None
                            called_task_name,
                            called_line_num,
                            called_task_position,
                            arrow,
                            upper_corner_arrow,
                            lower_corner_arrow,
                            fill_arrow,
                            start_line,
                            line_count,
    """
    # Get values for caller and called Task.
    caller_task_name = value[0]
    caller_line_num = value[1]
    caller_task_position = value[2]
    caller_task_name = value[3]
    called_line_num = value[4]
    called_task_position = value[5]
    arrow = value[6]
    upper_corner_arrow = value[7]
    lower_corner_arrow = value[8]
    fill_arrow = value[9]
    start_line = value[10]
    line_count = value[11]

    # Add right arrows to caller Task line.
    output_lines[caller_line_num] = replace_after_bracket(
        output_lines[caller_line_num], right_arrow, up_down_location
    )

    # Add left arrows to called Task line.
    output_lines[called_line_num] = replace_after_bracket(
        output_lines[called_line_num], left_arrow, up_down_location
    )

    # Fill called line with left arrows.
    output_lines[called_line_num] = output_lines[called_line_num].ljust(
        up_down_location, left_arrow
    )

    # Now traverse the output list from the calling Task to the called Task,
    # inserting a backward arrow along the way.
    for x in range(line_count+1):
        if x == 0:
            use_arrow = upper_corner_arrow
            # Fill with the arrow first.
            output_lines[start_line + x] = output_lines[start_line + x].ljust(
                up_down_location, fill_arrow
            )
        elif x == line_count:
            use_arrow = lower_corner_arrow
        else:
            use_arrow = arrow
        # use_arrow = corner_arrow if x in [0, line_count] else arrow
        output_lines[start_line + x] = output_lines[start_line + x].ljust(
            up_down_location
        )
        new_line = f"{output_lines[start_line+x][:up_down_location]}{use_arrow}{output_lines[start_line+x][up_down_location+1:]}"
        output_lines[start_line + x] = new_line


# ##################################################################################
# Complete Task details and save them in call_table
# ##################################################################################
def get_task_details_and_save(
                output_lines,
                call_table,
                caller_task_name,
                caller_line_num,
                caller_task_position,
                called_task_name,
                called_line_num,
                called_task_position,
            ):
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
        upper_corner_arrow = right_arrow_corner_down
        lower_corner_arrow = left_arrow_corner_down
        fill_arrow = right_arrow
        start_line = caller_line_num
        line_count = called_line_num - caller_line_num
    else:
        # Going up.
        arrow = up_arrow
        upper_corner_arrow = left_arrow_corner_up
        lower_corner_arrow = right_arrow_corner_up
        fill_arrow = left_arrow
        start_line = called_line_num
        line_count = caller_line_num - called_line_num

    # Find the outside boundary for the range of lines to traverse.
    up_down_location = 0
    for x in range(line_count + 1):
        up_down_location = max(
            up_down_location, len(output_lines[start_line + x])
        )
    up_down_location = up_down_location + 5

    # If this up_down value is already in our table, increment it until
    # it isn't.
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


# ##################################################################################
# Find and flag in the output those called Tasks that don't exist.
# ##################################################################################
def mark_tasks_not_found(output_lines):
    """
    Mark tasks not found in output lines
    Args:
        output_lines: List of output lines to search
    Returns: 
        None: Function does not return anything
    - Iterate through each line in output lines
    - Check if line contains "Task not found" string
    - If found, mark line number in a list for later processing
    - Return after completely iterating through lines"""
    for caller_line_num, line in enumerate(output_lines):

        if line_right_arrow in line:
            # Get the called Task name.
            start_position = line.index(line_right_arrow) + 4
            called_task_names = line[start_position:].split(",")

            # Go through list of calls to Tasks from this caller Task.
            for called_task_name in called_task_names:

                # Get the called Task name.
                called_task_name = called_task_name.lstrip()
                called_task_name = called_task_name.split("]")
                # Don't bother with variables.
                if called_task_name[0][0] == "%":
                    continue

                #  Find the "Called" Task line for the caller Task.
                search_name = f"└─ {called_task_name[0]}"

                # Make sure the called Task exists.
                found_called_task = False
                for called_line_num, check_line in enumerate(output_lines):
                    if search_name in check_line:
                        found_called_task = True
                        called_task_position = output_lines[called_line_num].index(
                            called_task_name[0]
                        )
                        break

                # If Task doesn't exist, mark it as such.
                if not found_called_task:
                    called_task_position = output_lines[caller_line_num].index(
                        called_task_name[0]
                    )
                    end_of_called_task_position = called_task_position + len(
                        called_task_name[0]
                    )
                    output_lines[caller_line_num] = (
                        output_lines[caller_line_num][:called_task_position]
                        + called_task_name[0]
                        + " (Not Found!)"
                        + output_lines[caller_line_num][end_of_called_task_position:]
                    )


# ##################################################################################
# Go through all caller and called Tasks and build the call table based on the
# input line passed in.
# ##################################################################################
def process_callers_and_called_tasks(output_lines, call_table, caller_line_num, line):
    """
    Processes caller and called tasks
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
    """

    # Get this Task's name
    caller_task_name = line.split("└─")
    caller_task_name = caller_task_name[1].split("[")[0].lstrip()
    caller_task_name = caller_task_name.rstrip()
    caller_task_position = output_lines[caller_line_num].index(caller_task_name)

    # Get the called Task name.
    start_position = line.index(line_right_arrow) + 4
    called_task_names = line[start_position:].split(",")

    # Go through list of calls to Tasks from this caller Task.
    for called_task_name in called_task_names:

        # Get the called Task name.
        called_task_name = called_task_name.lstrip()
        called_task_name = called_task_name.split("]")
        called_task_name = called_task_name[0]

        #  Find the "Called" Task line for the caller Task.
        search_name = f"└─ {called_task_name}"

        # Make sure the called Task exists.
        found_called_task = False
        for called_line_num, check_line in enumerate(output_lines):
            if search_name in check_line:
                found_called_task = True
                called_task_position = output_lines[called_line_num].index(
                    called_task_name
                )
                break

        # If called Task found, then save everything.
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
            )
            
    return call_table


# ##################################################################################
# Build a sorted list of all caller Tasks and their called Tasks.
# ##################################################################################
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
    """_summary_
    Build a sorted list of all caller Tasks and their called Tasks.
        Args:
            output_lines (list): List of output lines

        Returns:
            list: Caller/Called Task list.
    """
    # Go through all output lines looking for caller Tasks.
    call_table = {}
    for caller_line_num, line in enumerate(output_lines):
        
        # Do we have a "Calls" line (caller Task)?
        if line_right_arrow in line:
            
            # Handle all of the caller and called Tasks.
            call_table = process_callers_and_called_tasks(
                output_lines, call_table, caller_line_num, line
            )

    # Return the call table sorted by up_down_location ((inner locations before outer))
    return dict(sorted(call_table.items()))


# ##################################################################################
# If Task line has a "Calls", fill it with arrows.
# ##################################################################################
def handle_calls(output_lines):
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
    # Identify called Tasks that don't exist.
    mark_tasks_not_found(output_lines)
    
    # Create the table of caller/called Tasks and their pointers.
    call_table = build_call_table(output_lines)

    # Now traverse the call table and add arrows to the output lines.
    for up_down_location, value in call_table.items():
        draw_arrows_to_called_task(up_down_location, value, output_lines)
    
    # Remove all icons from the names to ensure arrow alignment.
    for line_num, line in enumerate(output_lines):
        if "PT View Spreadsheet" in line:
            print("kaka")
        for char in arrows:
            if char in line:
                output_lines[line_num] = remove_icon(line)
                break
  
    return output_lines


# ##################################################################################
# Build the Profile box.
# ##################################################################################
def build_profile_box(
    primary_items,
    profile,
    profile_counter,
    output_profile_lines,
    output_task_lines,
    print_tasks,
    ):
    """Builds a profile box for a given profile
    Args:
        primary_items: Primary items to print
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
        print_3_lines(primary_items, output_profile_lines)
        profile_counter = 1
        print_tasks = True
        output_profile_lines = [filler, filler, filler]

        # Do Tasks under Profile.
        if output_task_lines:
            # Print the Task lines associated with these 6 Profiles.
            print_all(primary_items, output_task_lines)
            output_task_lines = []
    else:
        print_tasks = False
    # Start/continue building our outlines
    output_profile_lines, position_for_anchor = build_box(
        profile, profile_counter, output_profile_lines
    )
    return (
        output_profile_lines,
        output_task_lines,
        position_for_anchor,
        print_tasks,
        profile_counter,
    )


# ##################################################################################
# Process all Profiles and their Tasks for the given Project
# ##################################################################################
def print_profiles_and_tasks(primary_items, project_name, profiles):
    """
    Prints profiles and tasks from a project.
    
    Args:
        primary_items: Items to print.
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

    # ow output each Profile and it's Tasks.
    for profile, tasks in profiles.items():
        if profile != "Scenes":
            (
                output_profile_lines,
                output_task_lines,
                position_for_anchor,
                print_tasks,
                profile_counter,
            ) = build_profile_box(
                primary_items,
                profile,
                profile_counter,
                output_profile_lines,
                output_task_lines,
                print_tasks,
            )

            # Go through the Profile's Tasks
            found_tasks = print_all_tasks(
                primary_items,
                project_name,
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
        primary_items,
        project_name,
        output_profile_lines,
        output_task_lines,
        found_tasks,
        profile_counter,
    )

    # Print any remaining Profile boxes and their associated Tasks
    if output_profile_lines[0] != filler:
        print_all(primary_items, output_profile_lines)
        if output_task_lines:
            print_all(primary_items, output_task_lines)

    # Map the Scenes
    if print_scenes:
        print_all_scenes(primary_items, scenes)

    # Add a blank line
    add_output_line(primary_items, " ")


# ##################################################################################
# Process all Projects
# ##################################################################################
def build_network_map(primary_items, data):
    """
    Builds a network map from project and profile data
    Args: 
        primary_items: Primary items dictionary
        data: Project and profile data dictionary
    Returns: 
        primary_items: Updated primary items dictionary with network map output
    - Loops through each project in the data dictionary
    - Prints the project name in a box
    - Prints all profiles and their tasks for that project  
    - Handles calling relationships between tasks and adds them to the network map output
    """
    # Go through each project
    for project, profiles in data.items():
        # Print Project as a box
        print_box(primary_items, project, "Project:", 1, 0)
        # Print all of the Project's Profiles and their Tasks
        print_profiles_and_tasks(primary_items, project, profiles)

    # Handle Task calls
    primary_items["netmap_output"] = handle_calls(primary_items["netmap_output"])


# ##################################################################################
# Print the network map.
# ##################################################################################
def network_map(primary_items: dict, network: dict) -> None:
    """_summary_
    Output a network map of the Tasker configuration.
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
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
    """

    # Start with a ruler line
    primary_items["output_lines"].add_line_to_output(
        primary_items, 1, "<hr>", FormatLine.dont_format_line
    )

    primary_items["netmap_output"] = []

    # Print a heading
    add_output_line(
        primary_items,
        f"{MY_VERSION}{blank*5}Configuration Map{blank*5}{str(datetime.now())}",
    )
    add_output_line(primary_items, " ")
    add_output_line(
        primary_items,
        "Display with a monospaced font (e.g. Courier New) for accurate column alignment. And turn off line wrap.\nIcons in names can cause minor mis-alignment.",
    )
    add_output_line(primary_items, " ")
    add_output_line(primary_items, " ")

    # Print the configuration
    build_network_map(primary_items, network)

    # Print it all out.
    # Redirect print to a file
    with open("MapTasker_Map.txt", "w") as mapfile:
        primary_items["printfile"] = mapfile
        for line in primary_items["netmap_output"]:
            print(line, file=mapfile)

    # Close the output print file
    mapfile.close()