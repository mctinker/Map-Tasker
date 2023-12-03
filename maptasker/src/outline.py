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

from maptasker.src.diagram import network_map
from maptasker.src.format import format_html
from maptasker.src.getids import get_ids
from maptasker.src.primitem import PrimeItems
from maptasker.src.profiles import get_profile_tasks
from maptasker.src.sysconst import NO_PROFILE, FormatLine

blank = "&nbsp;"
list_of_found_tasks = []
line = "─"
arrow = f"├{line*3}▶"


# ##################################################################################
# Go through all Tasks for Profile and see if any have a "Perform Task" action.
# If so, save the link to the other Task to be displayed in the outline.
# ##################################################################################
def get_perform_task_actions(profile: defusedxml.ElementTree, the_tasks: list) -> None:
    """
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
                # Have action: go through it looking for a "Perform Task"
                for child in action:
                    if child.tag == "code" and child.text == "130":
                        # We have a Perform Task.  Get the Task name to be performed.
                        all_strings = action.findall("Str")
                        perform_task_name = all_strings[0].text
                        # Add it to the list of Tasks called by this Task
                        task["call_tasks"].append(perform_task_name)

                        # Find the Task xml element to which this Perform Task refers.
                        for task_id in PrimeItems.tasker_root_elements["all_tasks"]:
                            task_called = PrimeItems.tasker_root_elements["all_tasks"][task_id]

                            # If we found the referring Task, add it to the list of
                            # "called_by" Tasks
                            if task_called["name"] and task_called["name"] == perform_task_name:
                                try:
                                    if task_called["called_by"] and task["name"] not in task_called["called_by"]:
                                        task_called["called_by"].append(task["name"])
                                    elif not task_called["called_by"]:
                                        task_called["called_by"] = [task["name"]]
                                except KeyError:
                                    task_called["called_by"] = [task["name"]]
                                break
                    break


# ##################################################################################
# Output the Tasks that are not in any Profile
# ##################################################################################
def tasks_not_in_profile(tasks_processed, task_ids):
    # Now process all Tasks under Project that are not called by any Profile
    # task_ids is a list of strings, each string is a Task id.
    task_line = ""
    no_profile_tasks = no_profile_task_lines = []
    for task in task_ids:
        if PrimeItems.tasker_root_elements["all_tasks"][task]["xml"] not in tasks_processed:
            # The Task has not been processed = not in any Profile.
            the_task_element = PrimeItems.tasker_root_elements["all_tasks"][task]
            task_name = the_task_element
            no_profile_tasks.append(task_name)
            no_profile_task_lines.append({"xml": task_name["xml"], "name": task_name["name"]})
    # Format the output line
    if no_profile_tasks:
        task_line = f"{blank*5}÷{line*5}▶ Tasks not in any Profile:"
        for task in no_profile_tasks:
            task_line = f'{task_line} {task["name"]},'

        # Remove trailing comma: ",&nbsp;&nbsp;"
        task_line = task_line.rstrip(task_line[-1])

        # Output the line
        PrimeItems.output_lines.add_line_to_output(
            0,
            task_line,
            ["", "task_color", FormatLine.add_end_span],
        )

        # Get any/all "Perform Task" links back to other Tasks
        get_perform_task_actions("", no_profile_task_lines)


# ##################################################################################
# Outline the Scenes under the Project
# ##################################################################################
def outline_scenes(project_name: str, network: dict) -> None:
    """
    Outline the Scenes under the Project
        Args:

            project_name (str): name of the Project to which these Scenes belong.
            network (dict): Dictionary structure for our network pointiog to
                    the owning Project.
    """
    scene_names = ""
    project = PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"]
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
            PrimeItems.output_lines.add_line_to_output(
                0,
                f"{blank*5}{arrow_to_use}{blank*2}Scene: {scene}",
                ["", "scene_color", FormatLine.add_end_span],
            )


# ##################################################################################
# Go through the Tasks in the Profile and output them.
# ##################################################################################
def do_profile_tasks(
    project_name: str,
    profile_name: str,
    the_tasks: list,
    task_output_line: list,
    network: dict,
) -> list:
    """
    Go through the Tasks in the Profile and output them.
        Args:

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

        # Correct the leading edge
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
        PrimeItems.output_lines.add_line_to_output(
            0,
            task_line,
            ["", "task_color", FormatLine.add_end_span],
        )
    return tasks_processed


# ##################################################################################
# Given a Project, outline it's Profiles, Tasks and Scenes
# ##################################################################################
def outline_profiles_tasks_scenes(
    project: defusedxml.ElementTree,
    project_name: str,
    profile_ids: list,
    task_ids: list,
    network: dict,
) -> None:
    """
    Given a Project, outline it's Profiles, Tasks and Scenes
        Args:

            project (defusedxml.ElementTree): The xml head element for the Project we are processing
            project_name (str): name of the Project we are currently outlining
            profile_ids (list): liost of Profiles under this Project
            task_ids (list): liost of Tasks under this Project
            network (dict): Dictionary structure for our network
    """

    # Delete the <ul> inserted by get_ids for Profile
    PrimeItems.output_lines.delete_last_line()
    for item in profile_ids:
        # Get the Profile element
        profile = PrimeItems.tasker_root_elements["all_profiles"][item]["xml"]
        # Get the Profile name
        if not (profile_name := PrimeItems.tasker_root_elements["all_profiles"][item]["name"]):
            profile_name = NO_PROFILE

        # Doing all Projects or single Project and this is our Project...
        if (
            not PrimeItems.program_arguments["single_profile_name"]
            or PrimeItems.program_arguments["single_profile_name"] == profile_name
        ):
            # Add Profile to our network
            # network[project_name][profile_name] = []

            profile_line = f"{blank*5}{arrow}{blank*2}Profile: {profile_name}"
            PrimeItems.output_lines.add_line_to_output(
                0,
                profile_line,
                ["", "profile_color", FormatLine.add_end_span],
            )

            # Get Tasks for this Profile and output them
            task_output_line = []  # Profile's Tasks will be filled in here
            tasks_processed = []  # Keep track of Tasks processed/output.

            the_tasks = get_profile_tasks(
                profile,
                list_of_found_tasks,
                task_output_line,
            )

            # Get any/all "Perform Task" links back to other Tasks
            get_perform_task_actions(profile, the_tasks)

            # Output the Profile's Tasks
            tasks_processed = do_profile_tasks(
                project_name,
                profile_name,
                the_tasks,
                task_output_line,
                network,
            )

    # List the Tasks not in any Profile for this Project
    if not PrimeItems.program_arguments["single_profile_name"]:
        tasks_not_in_profile(tasks_processed, task_ids)

    # Get the Scenes for this Project
    outline_scenes(project_name, network)

    return


# ##################################################################################
# Start outline beginning with the Projects
# ##################################################################################
def do_the_outline(network: dict) -> None:
    """
    Start outline beginning with the Projects
        Args:

            network (dict): Dictionary structure for our network
    """

    for project_item in PrimeItems.tasker_root_elements["all_projects"]:
        # Get the Project XML element
        project = PrimeItems.tasker_root_elements["all_projects"][project_item]["xml"]
        # Get the Project name formatted for the directory hotlink (with +++s)
        project_name = project_item

        # Doing all Projects or single Project and this is our Project...
        if (
            not PrimeItems.program_arguments["single_project_name"]
            or PrimeItems.program_arguments["single_project_name"] == project_name
        ):
            # Add Project to our network
            network[project_name] = {}

            # Format Project name
            format_html(
                "project_color",
                "",
                f"Project: {project_name}",
                True,
            )
            # Output the final Project text
            PrimeItems.output_lines.add_line_to_output(
                0,
                f"{blank*3}Project: {project_name}",
                ["", "project_color", FormatLine.add_end_span],
            )

            # Get Task IDs for this Project.
            task_ids = get_ids(False, project, project_name, [])

            # Get the Profile IDs for this Project and process them
            # True if we have Profiles for this Project
            if profile_ids := get_ids(True, project, project_name, []):
                outline_profiles_tasks_scenes(project, project_name, profile_ids, task_ids, network)

            # No Profiles for Project
            if not profile_ids:
                # End ordered list since lineout.py added a <ul> for Project
                PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# ##################################################################################
# Outline the Tasker Configuration
# ##################################################################################
def outline_the_configuration() -> None:
    """
    Outline the Tasker Configuration
        Args:

    """

    # Start with a ruler line
    PrimeItems.output_lines.add_line_to_output(1, "<hr>", FormatLine.dont_format_line)

    # Define our network.
    network = {}

    # Output the directory link
    if PrimeItems.program_arguments["directory"]:
        PrimeItems.output_lines.add_line_to_output(
            5,
            '<a id="configuration_outline"></a>',
            FormatLine.dont_format_line,
        )
    # Output the header
    PrimeItems.output_lines.add_line_to_output(
        0,
        "<em>Configuration Outline</em>",
        ["", "trailing_comments_color", FormatLine.add_end_span],
    )

    # Go do it!
    do_the_outline(network)

    # End the list
    PrimeItems.output_lines.add_line_to_output(
        3,
        "",
        FormatLine.dont_format_line,
    )

    network_map(network)
