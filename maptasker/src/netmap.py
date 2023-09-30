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
import tkinter
import tkinter.font
from datetime import datetime
from string import printable

from maptasker.src.sysconst import MY_VERSION

box_line = "═"
blank = " "


# ##################################################################################
# Given an array of 3 string elements, format them with fillers for headings
# ##################################################################################
def include_heading(header, output_lines):
    filler = f"{blank*len(header)}"
    output_lines[0] = f"{filler}{output_lines[0]}"
    output_lines[1] = f"{header}{output_lines[1]}"
    output_lines[2] = f"{filler}{output_lines[2]}"


# ##################################################################################
# Given a list of 3 text elements, print them.
# ##################################################################################
def print_3_lines(primary_items, lines):
    do_list = isinstance(lines, list)
    for line in range(3):
        if do_list:
            print(lines[line], file=primary_items["printfile"])
        else:
            print(line, file=primary_items["printfile"])


# ##################################################################################
# Given a list of text strings, print all of them.
# ##################################################################################
def print_all(primary_items, lines):
    for line in lines:
        print(line, file=primary_items["printfile"])


# ##################################################################################
# Given a text string and title, enclose them in a box and print the box.
# ##################################################################################
def print_box(primary_items, name, title, indent, counter):
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
# Given a name, enclose it in a text box
# ##################################################################################
def build_box(name, counter, output_lines):
    name = name.rstrip()
    filler = trailer = blank
    # Deal with icon in the name
    if set(name).difference(printable):
        trailer = fix_icon(name)

    # Build the box
    box_top = f"╔═{box_line*len(name)}═╗"
    box_bottom = f"╚═{box_line*len(name)}═╝"
    output_lines[0] = f"{output_lines[0]}{filler}{box_top}"
    output_lines[1] = f"{output_lines[1]}{filler}║{blank}{name}{trailer}║"
    output_lines[2] = f"{output_lines[2]}{filler}{box_bottom}"
    position_for_anchor = len(output_lines[0]) - len(name) // 2 - 4
    return output_lines, position_for_anchor


# ##################################################################################
# Process all Tasks in the Profile
# ##################################################################################
def print_all_tasks(
    primary_items, tasks, position_for_anchor, output_task_lines, print_tasks
):
    last_upward_bar = []  # Keep track of the "|" bars in the output lines
    for task in tasks:
        # We have a full row of Profiles.  Print the Tasks out.
        if print_tasks:
            print_all(primary_items, output_task_lines)
            output_task_lines = []
            last_upward_bar = []
        else:
            # We are still accumating outlines for Profiles.
            # Build lines for the Profile's Tasks as well.
            line = f'{blank*position_for_anchor}└─ {task["name"]}'
            last_upward_bar.append(position_for_anchor)
            output_task_lines.append(line)

            # Interject the "|" for previous Tasks under Profile
            for bar in last_upward_bar:
                for line_num, line in enumerate(output_task_lines):
                    if len(line) > bar and not line[bar]:
                        output_task_lines[line_num] = f"{line[:bar]}│{line[bar:]}"
                    if len(line) <= bar:
                        output_task_lines[line_num] = f"{line.ljust(bar)}│"

        # Is this Task calling other Tasks?
        # with contextlib.suppress(KeyError):
        #     if task["calls_tasks"]:
        #         print(f"| Calls tasks: {', '.join(task['calls_tasks'])}")


# ##################################################################################
# Process all Scenes in the Project
# ##################################################################################
def print_all_scenes(primary_items, scenes):
    # Set up for Scenes
    filler = f"{blank*2}"
    scene_counter = 0
    output_scene_lines = [filler, filler, filler]
    header = False
    # Empty line to start
    print(" ", file=primary_items["printfile"])

    # Do all of the Scenes for the given Project
    for scene in scenes:
        scene_counter += 1
        if scene_counter > 8:
            # We have 6 columns.  Print them out and reset.
            include_heading(f"{blank*7}Scenes:", output_scene_lines)
            # print("      Scenes...")
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
        # print("      Scenes...")
    print_3_lines(primary_items, output_scene_lines)


# ##################################################################################
# Process all Profiles and their Tasks for the given Project
# ##################################################################################
def print_profiles_and_tasks(primary_items, profiles):
    filler = f"{blank*8}"
    # Go through each Profile in the Project
    profile_counter = 0
    print_tasks = print_scenes = False
    output_profile_lines = [filler, filler, filler]
    output_task_lines = []
    for profile, tasks in profiles.items():
        if profile != "Scenes":
            profile_counter += 1
            if profile_counter > 6:
                # We have 6 columns.  Print them
                print_3_lines(primary_items, output_profile_lines)
                profile_counter = 1
                print_tasks = True
                output_profile_lines = [filler, filler, filler]

                # Print the Task lines assoxciated with these 6 Profiles
                print_all(primary_items, output_task_lines)
                output_task_lines = []
            else:
                print_tasks = False
            # Start/continue building our outlines
            output_profile_lines, position_for_anchor = build_box(
                profile, profile_counter, output_profile_lines
            )

            # Go through the Profile's Tasks
            print_all_tasks(
                primary_items,
                tasks,
                position_for_anchor,
                output_task_lines,
                print_tasks,
            )

            # Print the Scenes: 6 columns
        else:
            print_scenes = True
            scenes = tasks

    # Print any remaining Profile boxes and their associated Tasks
    if output_profile_lines[0] != filler:
        print_all(primary_items, output_profile_lines)
        print_all(primary_items, output_task_lines)

    # Map the Scenes
    if print_scenes:
        print_all_scenes(primary_items, scenes)

        # print(f"\n{profile}: {', '.join(tasks)}")
    # Add a blank line
    print(" ", file=primary_items["printfile"])


# ##################################################################################
# Process all Projects
# ##################################################################################
def print_network(primary_items, data):
    # Go through each project
    for project, profiles in data.items():
        # Print Project as a box
        print_box(primary_items, project, "Project:", 1, 0)
        # Print all of the Profject's Profiles and their Tasks
        print_profiles_and_tasks(primary_items, profiles)


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
    primary_items["output_lines"].add_line_to_output(primary_items, 1, "<hr>")

    # Redirect print to a file
    with open("MapTasker_Map.txt", "w") as mapfile:
        primary_items["printfile"] = mapfile

        # Print a heading
        print(
            f"{MY_VERSION}{blank*5}Configuration Map{blank*5}{str(datetime.now())}",
            file=mapfile,
        )
        print(" ", file=mapfile)
        print(
            "Display with a monospaced font (e.g. Courier New) for accurate column alignment.",
            file=mapfile,
        )
        print(" ", file=mapfile)
        print(" ", file=mapfile)

        # Print the configuration
        print_network(primary_items, network)

        # Close the output print file
        mapfile.close()
