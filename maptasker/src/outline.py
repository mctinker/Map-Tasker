#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# outline: Output the Tasker configuration in outline format                           #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

# Our network dictionary looks like the following...

# network = {
#   "Project 1": {
#     "Profile 1": [
#       {"Task 1": "xml": xml, "name": "Task 1", "calls_tasks": ["Task 2", "Task 3"]}
#       {"Task 2": "xml": xml, "name": "Task 1", "calls_tasks": []}
#     ],
#     "Profile 1": [
#       {"Task 1": "xml": xml, "name": "Task 3", "calls_tasks": ["Task 8"]}
#       {"Task 2": "xml": xml, "name": "Task 4", "calls_tasks": []}
#     ],
#     "Scenes": ["Scene 1", "Scene 2"] # List of Scenes for this Project
#   },
#   "Project 2": {
#     "Profile 1": {
#       [{"Task 1": {"xml": xml, "name": "Task 4", "calls_tasks": []}
#     }
#   }
# }

import contextlib

import defusedxml.ElementTree  # Need for type hints

from maptasker.src.frmthtml import format_html
from maptasker.src.getids import get_ids
from maptasker.src.netmap import network_map
from maptasker.src.profiles import get_profile_tasks
from maptasker.src.sysconst import NO_PROFILE

blank = "&nbsp;"
list_of_found_tasks = []
line = "─"
arrow = f"├{line*3}▶"


# ##################################################################################
# Go through all Tasks for Profile and see if any have a "Perform Task" action.
# If so, save the link to the other Task to be displayed in the outline.
# ##################################################################################
def get_perform_task_actions(
    primary_item: dict, profile: defusedxml.ElementTree, the_tasks: list
) -> None:
    """_summary_
    Go through all Tasks for Profile and see if any have a "Perform Task" action.
    If so, save the link to the other Task to be displayed in the outline.
        Args:
            primary_item (dict): Program registry.  See primitem.py for details.
            profile (defusedxml.ElementTree): Profile that owns these Tasks
            the_tasks (list): List of Task xml elements under this Profile.
    """
    # Go through each Task to find out if this Task is calling other Tasks.
    for task in the_tasks:
        # Start with no "Perform Tasks" for this Task
        task["call_tasks"] = []
        # Get Task's Actions
        try:
            task_actions = task["xml"].findall("Action")
        except defusedxml.DefusedXmlException:
            task_actions = ""
            continue
        # Go through Actions and see if any are "Perform Task"
        if task_actions:
            for action in task_actions:
                for child in action:
                    if child.tag == "code" and child.text == "130":
                        # We have a Perform Task.  Get the Task name to be performed.
                        all_strings = action.findall("Str")
                        perform_task_name = all_strings[0].text
                        task["call_tasks"].append(perform_task_name)
                    break


# ##################################################################################
# Output the Tasks that are not in any Profile
# ##################################################################################
def tasks_not_in_profile(primary_items, tasks_processed, task_ids):
    # Now process all Tasks under Project that are not called by any Profile
    # task_ids is a list of strings, each string is a Task id.
    task_line = ""
    no_profile_tasks = []
    for task in task_ids:
        if (
            primary_items["tasker_root_elements"]["all_tasks"][task]["xml"]
            not in tasks_processed
        ):
            # The Task has not been processed = not in any Profile.
            task_name = primary_items["tasker_root_elements"]["all_tasks"][task]["name"]
            no_profile_tasks.append(task_name)

    if no_profile_tasks:
        task_line = f"{blank*5}÷{line*5}▶ Tasks not in any Profile:"
        for task in no_profile_tasks:
            task_line = f"{task_line} {task},"
        # Remove trailing comma: ",&nbsp;&nbsp;"
        task_line = task_line.rstrip(task_line[-1])

        # Output the line
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            0,
            format_html(primary_items, "task_color", "", task_line, True),
        )


# ##################################################################################
# Outline the Scenes under the Project
# ##################################################################################
def outline_scenes(primary_items: dict, project_name: str, network: dict) -> None:
    """_summary_
    Outline the Scenes under the Project
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
            project_name (str): name of the Project to which these Scenes belong.
            network (dict): Dictionary structure for our network pointiog to
                    the owning Project.
    """
    scene_names = ""
    project = primary_items["tasker_root_elements"]["all_projects"][project_name]["xml"]
    with contextlib.suppress(Exception):
        scene_names = project.find("scenes").text
    if scene_names != "":
        scene_list = scene_names.split(",")

        # Add Scenes to our network
        network[project_name]["Scenes"] = scene_list

        arrow_to_use = arrow
        for scene in scene_list:
            # If last Scene for Project, put an elbow in instead of full bracket
            if scene == scene_list[-1]:
                arrow_to_use = arrow_to_use.replace("├", "└")
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                0,
                format_html(
                    primary_items,
                    "scene_color",
                    "",
                    f"{blank*5}{arrow_to_use}{blank*2}Scene: {scene}",
                    True,
                ),
            )


# ##################################################################################
# Go through the Tasks in the Profile and output them.
# ##################################################################################
def do_profile_tasks(
    primary_items: dict,
    project_name: str,
    profile_name: str,
    the_tasks: list,
    task_output_line: list,
    network: dict,
) -> list:
    """_summary_
    Go through the Tasks in the Profile and output them.
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
            project_name (str): Name of the Project
            profile_name (str): Name of the Profile
            the_tasks (list): list of Tasks in Profile ("xml" and "name")
            task_output_line (list): The list of Task output lines
            network (dict): Dictionary structure for our network pointiog to
                    the owning Profile.

        Returns:
            list: List of Tasks within the Profile being processed.
    """

    arrow1 = f"├{line*5}▶"
    # elbow = f"└{line*5}▶"
    arrow_to_use = arrow1

    tasks_processed = []
    network[project_name][profile_name] = []

    # Go through Task's output lines and Tasks, and add arrows as appropriate.
    for task_line, task in zip(task_output_line, the_tasks):
        # Keep track of Tasks processed.
        tasks_processed.append(task["xml"])

        # Add Task to the network
        network[project_name][profile_name].append(task)

        # Fix the leading edge
        if task_line == task_output_line[-1]:
            arrow_to_use = arrow_to_use.replace("├", "└")

        # Get just the name
        task_line = task_line.split("&nbsp;")

        # Add any/all "Perform Task" indicators
        call_task = ""
        try:
            for perform_task in task["call_tasks"]:
                call_task = f"{call_task} {perform_task},"
        except KeyError:
            call_task = ""
        if call_task:
            call_task = f"{blank*3}{line*3} calls {line*2}▶ {call_task.rstrip(call_task[-1])}"  # Get rid of last comma

        # Add the Task output line
        task_line = f"{blank*5}{arrow_to_use}{blank*2}Task: {task_line[0]}{call_task}"
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            0,
            format_html(primary_items, "task_color", "", task_line, True),
        )
    return tasks_processed


# ##################################################################################
# Given a Project, outline it's Profiles, Tasks and Scenes
# ##################################################################################
def outline_profiles_tasks_scenes(
    primary_items: dict,
    project: defusedxml.ElementTree,
    project_name: str,
    profile_ids: list,
    task_ids: list,
    network: dict,
) -> None:
    """_summary_
    Given a Project, outline it's Profiles, Tasks and Scenes
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
            project (defusedxml.ElementTree): The xml head element for the Project we are processing
            project_name (str): name of the Project we are currently outlining
            profile_ids (list): liost of Profiles under this Project
            task_ids (list): liost of Tasks under this Project
            network (dict): Dictionary structure for our network
    """

    # Delete the <ul> inserted by get_ids for Profile
    primary_items["output_lines"].delete_last_line(primary_items)
    for item in profile_ids:
        # Get the Profile element
        profile = primary_items["tasker_root_elements"]["all_profiles"][item]["xml"]
        # Get the Profile name
        if not (
            profile_name := primary_items["tasker_root_elements"]["all_profiles"][item][
                "name"
            ]
        ):
            profile_name = NO_PROFILE

        # Add Profile to our network
        # network[project_name][profile_name] = []

        profile_line = f"{blank*5}{arrow}{blank*2}Profile: {profile_name}"
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            0,
            format_html(primary_items, "profile_color", "", profile_line, True),
        )

        # Get Tasks for this Profile and output them
        task_output_line = []  # Profile's Tasks will be filled in here
        tasks_processed = []  # Keep track of Tasks processed/output.

        the_tasks = get_profile_tasks(
            primary_items,
            profile,
            list_of_found_tasks,
            task_output_line,
        )

        # Get any/all "Perform Task" links back to other Tasks
        get_perform_task_actions(primary_items, profile, the_tasks)

        # Output the Profile's Tasks
        tasks_processed = do_profile_tasks(
            primary_items,
            project_name,
            profile_name,
            the_tasks,
            task_output_line,
            network,
        )

    # List the Tasks not in anyn Profile for this Project
    tasks_not_in_profile(primary_items, tasks_processed, task_ids)

    # Get the Scenes for this Project
    outline_scenes(primary_items, project_name, network)

    return


# ##################################################################################
# Start outline beginning with the Projects
# ##################################################################################
def do_the_outline(primary_items: dict, network: dict) -> None:
    """_summary_
    Start outline beginning with the Projects
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
            network (dict): Dictionary structure for our network
    """

    for project_item in primary_items["tasker_root_elements"]["all_projects"]:
        # Get the Project XML element
        project = primary_items["tasker_root_elements"]["all_projects"][project_item][
            "xml"
        ]
        # Get the Project name formatted for the directory hotlink (with +++s)
        project_name = project_item

        # Add Project to our network
        network[project_name] = {}

        # Format Project name
        format_html(
            primary_items,
            "project_color",
            "",
            f"Project: {project_name}",
            True,
        )
        # Output the final Project text
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            0,
            format_html(
                primary_items,
                "project_color",
                "",
                f"{blank*3}Project: {project_name}",
                True,
            ),
        )

        # Get Task IDs for this Project.
        task_ids = get_ids(primary_items, False, project, project_name, [])

        # Get the Profile IDs for this Project and process them
        # True if we have Profiles for this Project
        if profile_ids := get_ids(primary_items, True, project, project_name, []):
            outline_profiles_tasks_scenes(
                primary_items, project, project_name, profile_ids, task_ids, network
            )

        # No Profiles for Project
        if not profile_ids:
            # End ordered list since lineout.py added a <ul> for Project
            primary_items["output_lines"].add_line_to_output(primary_items, 3, "")


# ##################################################################################
# Outline the Tasker Configuration
# ##################################################################################
def outline_the_configuration(primary_items: dict) -> None:
    """_summary_
    Outline the Tasker Configuration
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
    """

    # Start with a ruler line
    primary_items["output_lines"].add_line_to_output(primary_items, 1, "<hr>")

    # Define our network
    network = {}

    # Output the directory link
    if primary_items["program_arguments"]["directory"]:
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            5,
            '<a id="configuration_outline"></a>',
        )
    # Output the header
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        0,
        format_html(
            primary_items,
            "trailing_comments_color",
            "",
            "<em>Configuration Outline</em>",
            True,
        ),
    )

    # Go do it!
    do_the_outline(primary_items, network)

    # End the list
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        3,
        "",
    )

    network_map(primary_items, network)
