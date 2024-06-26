"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# outline: Output the Tasker configuration in outline format                           #
#                                                                                      #


# Our network dictionary looks like the following...

# network = {
#   "Project 1": {
#     "Profile 1": [
#       {"Task 1": "xml": xml, "name": "Task 1", "call_tasks": ["Task 2", "Task 3"]}
#       {"Task 2": "xml": xml, "name": "Task 1", "call_tasks": []}
#     ],
#     "Profile 1": [
#       {"Task 1": "xml": xml, "name": "Task 3", "call_tasks": ["Task 8"]}
#       {"Task 2": "xml": xml, "name": "Task 4", "call_tasks": []}
#     ],
#     "Scenes": ["Scene 1", "Scene 2"] # List of Scenes for this Project
#   },
#   "Project 2": {
#     "Profile 1": {
#       [{"Task 1": {"xml": xml, "name": "Task 4", "call_tasks": []}
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
from maptasker.src.sysconst import FormatLine

blank = "&nbsp;"
list_of_found_tasks = []
line = "─"
arrow = f"├{line*3}▶"


# Update Task with calls and called_by details
def update_caller_and_called_tasks(task: defusedxml.ElementTree, perform_task_name: str) -> None:
    # Find the Task xml element to which this Perform Task refers.
    """
    Updates the caller and called tasks lists
    Args:
        task: {Task xml element}: Task xml element
        perform_task_name: {str}: Name of the task being performed
    Returns:
        None
    Processing Logic:
        - Finds the task element referred to by perform_task_name
        - Adds perform_task_name to the caller task's call_tasks list
        - Finds the task element for the perform_task_name
        - Adds the caller task's name to the performed task's called_by list
    """
    if PrimeItems.tasks_by_name[task["name"]]:
        task_called = PrimeItems.tasks_by_name[task["name"]]

        # Add it to the list of Tasks this Task calls.
        try:
            if task_called["call_tasks"]:
                task_called["call_tasks"].append(perform_task_name)
        except KeyError:
            task_called["call_tasks"] = [perform_task_name]
        except AttributeError:
            task_called["call_tasks"] = [perform_task_name]

    # Find the Task xml element to which this Perform Task refers.  Set up the called by Task list.
    with contextlib.suppress(KeyError):
        if PrimeItems.tasks_by_name[perform_task_name]:
            task_called = PrimeItems.tasks_by_name[perform_task_name]

            # Add it to the list of Tasks that call this Task.
            try:
                if task_called["called_by"] and task["name"] not in task_called["called_by"]:
                    task_called["called_by"].append(task["name"])
                elif not task_called["called_by"]:
                    task_called["called_by"] = [task["name"]]
            except KeyError:
                task_called["called_by"] = [task["name"]]


# Go through the Task's Actions looking for any Perform Task actions.
def do_task_actions(task_actions: defusedxml.ElementTree, task: defusedxml.ElementTree) -> None:
    """
    Parses task action elements and updates task call relationships
    Args:
        task_actions: defusedxml.ElementTree - Task action elements
        task: defusedxml.ElementTree - Task element
    Returns:
        None
    Processing Logic:
        - Loops through each action element
        - Checks for "Perform Task" code
        - Gets task name from action
        - Finds called task element
        - Adds caller task to called task's call_tasks
        - Adds called task to caller task's called_by
    """
    for action in task_actions:
        # Have action: go through it looking for a "Perform Task"
        for child in action:
            if child.tag == "code" and child.text == "130":
                # We have a Perform Task.  Get the Task name to be performed.
                all_strings = action.findall("Str")
                perform_task_name = all_strings[0].text

                update_caller_and_called_tasks(task, perform_task_name)


# Go through all Tasks for Profile and see if any have a "Perform Task" action.
# If so, save the link to the other Task to be displayed in the outline.
def get_perform_task_actions(the_tasks: list) -> None:
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
        # Get Task's Actions
        try:
            task_actions = task["xml"].findall("Action")
        except defusedxml.DefusedXmlException:
            task_actions = ""
            continue
        # Go through Actions and see if any are "Perform Task"
        if task_actions:
            do_task_actions(task_actions, task)


# Output the Tasks that are not in any Profile
def tasks_not_in_profile(all_profiles_tasks: list, tasks_in_project: list) -> None:
    # Now process all Tasks under Project that are not called by any Profile
    # task_ids is a list of strings, each string is a Task id.
    """
    Find tasks not processed by any profile
    Args:
        tasks_processed: list - Tasks already processed
        task_ids: defusedxml - All tasks in the project
    Returns:
        None
    1. Loop through all tasks in the project
    2. Check if the task XML is not in the already processed tasks
    3. If not processed, add it to the list of tasks not in any profile
    4. Format and output the tasks not in any profile line
    5. Get any linked "Perform Task" actions for these uncovered tasks
    """

    task_line = ""
    all_profiles_tasks = list(dict.fromkeys(all_profiles_tasks))  # Remove dups
    no_profile_tasks = []
    no_profile_task_lines = []
    # Go through all Tasks in the Project
    for task in tasks_in_project:
        profile_task = f"task{task}"
        # Go through all Tasks in the Profiles for this Project
        if profile_task not in all_profiles_tasks:
            # The Task has not been processed = not in any Profile.
            the_task_element = PrimeItems.tasker_root_elements["all_tasks"][task]
            no_profile_task = the_task_element
            # Add it to the list of Tasks not in any Profile if not already in the list.
            if no_profile_task not in no_profile_tasks:
                no_profile_tasks.append(no_profile_task)
                no_profile_task_lines.append({"xml": no_profile_task["xml"], "name": no_profile_task["name"]})
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
        get_perform_task_actions(no_profile_task_lines)


# Outline the Scenes under the Project
def outline_scenes(project_name: str, network: dict) -> None:
    """
    Outline the Scenes under the Project
        Args:

            project_name (str): name of the Project to which these Scenes belong.
            network (dict): Dictionary structure for our network pointiog to
                    the owning Project.
    """
    scene_names = ""
    if PrimeItems.tasker_root_elements["all_projects"]:
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


# Go through the Tasks in the Profile and output them.
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

    tasks_in_profile = []
    # If no Project, then this XML only has a Profile or Task
    if not project_name:
        project_name = "No Project"
        network[project_name] = {}
    network[project_name][profile_name] = []

    # Go through Task's output lines and Tasks, and add arrows as appropriate.
    for task_line, task in zip(task_output_line, the_tasks):
        # Keep track of Tasks processed.
        taskid = task["xml"].attrib.get("sr")
        if taskid not in tasks_in_profile:
            tasks_in_profile.append(taskid)

        # Add Task to the network
        network[project_name][profile_name].append(task)

        # Correct the leading edge
        if task_line == task_output_line[-1]:
            arrow_to_use = arrow_to_use.replace("├", "└")

        # Get just the name
        task_line = task_line.split("&nbsp;")  # noqa: PLW2901

        # Add any/all "Perform Task" indicators
        call_task = ""
        prime_task = ""

        with contextlib.suppress(KeyError):
            if PrimeItems.tasks_by_name[task["name"]]:
                prime_task = PrimeItems.tasks_by_name[task["name"]]
                try:
                    for perform_task in prime_task["call_tasks"]:
                        call_task = f"{call_task} {perform_task},"
                except KeyError:
                    call_task = ""
        if call_task:
            call_task = f"{blank*3}{line*3} calls {line*2}▶ {call_task.rstrip(call_task[-1])}"  # Get rid of last comma

        # Add the Task output line
        task_line = f"{blank*5}{arrow_to_use}{blank*2}Task: {task_line[0]}{call_task}"  # noqa: PLW2901
        PrimeItems.output_lines.add_line_to_output(
            0,
            task_line,
            ["", "task_color", FormatLine.add_end_span],
        )
    return tasks_in_profile


# Given a Project, outline it's Profiles, Tasks and Scenes
def outline_profiles_tasks_scenes(
    project_name: str,
    profile_ids: list,
    tasks_in_project: list,
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
    all_profiles_tasks = []

    # Go thru all Profiles
    no_name_counter = 1
    for item in profile_ids:
        # Get the Profile element
        profile = PrimeItems.tasker_root_elements["all_profiles"][item]["xml"]
        # Get the Profile name
        if not (profile_name := PrimeItems.tasker_root_elements["all_profiles"][item]["name"]):
            profile_name = f"Anonymous#{no_name_counter!s}"
            no_name_counter += 1

        # Doing all Projects or single Project and this is our Project...
        if (
            not PrimeItems.program_arguments["single_profile_name"]
            or PrimeItems.program_arguments["single_profile_name"] == profile_name
        ):
            # Add Profile to our network
            profile_line = f"{blank*5}{arrow}{blank*2}Profile: {profile_name}"
            PrimeItems.output_lines.add_line_to_output(
                0,
                profile_line,
                ["", "profile_color", FormatLine.add_end_span],
            )

            # Get Tasks for this Profile and output them
            task_output_line = []  # Profile's Tasks will be filled in here
            tasks_in_profile = []  # Keep track of Tasks processed/output.
            list_of_found_tasks = []

            the_tasks = get_profile_tasks(
                profile,
                list_of_found_tasks,
                task_output_line,
            )

            # Get any/all "Perform Task" links back to other Tasks
            get_perform_task_actions(the_tasks)

            # Output the Profile's Tasks
            tasks_in_profile = do_profile_tasks(
                project_name,
                profile_name,
                the_tasks,
                task_output_line,
                network,
            )
            all_profiles_tasks.extend(tasks_in_profile)

    # List the Tasks not in any Profile for this Project
    if not PrimeItems.program_arguments["single_profile_name"]:
        tasks_not_in_profile(all_profiles_tasks, tasks_in_project)

    # Get the Scenes for this Project
    outline_scenes(project_name, network)


# Name anonymous Tasks as "anonymous#1", "anonymous#2", etc.
def assign_names_to_anonymous_tasks() -> None:
    """Assign names to anonymous tasks in the task list
    Args:
        None
    Returns:
        None: Assign names to anonymous tasks
    - Count number of anonymous tasks
    - Iterate through all tasks
    - Check if task name is empty
    - If empty, assign default name "Anonymous#{counter}"
    - Increment counter"""
    no_name_counter = 1
    PrimeItems.tasks_by_name = {}
    for value in PrimeItems.tasker_root_elements["all_tasks"].values():
        if not value["name"]:
            value["name"] = f"Anonymous#{no_name_counter!s}"
            no_name_counter += 1

        # From this point on, we only need to find Tasks by Name.  So create a dict of all Tasks by name.
        # PrimeItems.tasks_by_name[value["name"]] = {"id": key, "name": value["name"], "xml": value["xml"]}
        PrimeItems.tasks_by_name[value["name"]] = value


# Start outline beginning with the Projects
def do_the_outline(network: dict) -> None:
    """
    Start outline beginning with the Projects
        Args:
            network (dict): Dictionary structure for our network
    """
    # Name anonymous Tasks as "anonymous#1", "anonymous#2", etc.
    assign_names_to_anonymous_tasks()

    # If no projects and a profile or task, just display profile or task rather than going through this loop.
    if not PrimeItems.tasker_root_elements["all_projects"] and (
        PrimeItems.tasker_root_elements["all_profiles"] or PrimeItems.tasker_root_elements["all_tasks"]
    ):
        pids = []
        tids = []
        # Get the Profile and Task IDs
        for key in PrimeItems.tasker_root_elements["all_profiles"]:
            pids.append(key)  # noqa: PERF402
        for key in PrimeItems.tasker_root_elements["all_tasks"]:
            tids.append(key)
            # If no Profile at this point, let user know and return.
            if not pids:
                PrimeItems.output_lines.add_line_to_output(
                    0,
                    f"{blank*3}Task only...nothing to outline",
                    ["", "project_color", FormatLine.add_end_span],
                )
                return
        outline_profiles_tasks_scenes("", pids, tids, network)
        return

    # Go thru all Projects
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
                outline_profiles_tasks_scenes(project_name, profile_ids, task_ids, network)

            # No Profiles for Project
            if not profile_ids:
                # Add blank line since lineout.py added a completion for Project
                PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# Get the Project for the single named item (Profile or Task)
def check_for_single_name(root: dict, single_name: str, do_pids: bool) -> bool:
    """
    Get the Project for the single named item (Profile or Task)

    Args:
        root (dict): The root of the tasker XML objects (e.g. PrimeItems.tasker_root_elements["all_tasks"])
        single_name (str): The name of the object (Task or Profile) to get the Project for.
        do_pids (bool): True if we are doing Profiles, False if we are doing Tasks

    REturns:
        bool: True if the Project was found, False if not.
    """
    item_id = ""
    if single_name:
        for key, value in root.items():
            if value["name"] == single_name:
                item_id = key
                break
        # We have the Profile/Task ID for the single name
        if item_id:
            for key, value in PrimeItems.tasker_root_elements["all_projects"].items():
                item_ids = get_ids(do_pids, value["xml"], single_name, [])
                # Is our single named object in this project?
                if item_id in item_ids:
                    PrimeItems.program_arguments["single_project_name"] = key
                    return True
    return False


# If doing a single named item (Profile or Task), then get the Project associated with the named item.
def fix_project_name_for_single_name() -> None:
    """
    Set the project name for a single profile/task name.

    This function checks if the single profile name is valid by calling the `check_for_single_name` function with the `single_profile_name` parameter set to `PrimeItems.program_arguments["single_profile_name"]` and the `do_pids` parameter set to `True`. If the single profile name is not valid, it calls the `check_for_single_name` function again with the `single_task_name` parameter set to `PrimeItems.program_arguments["single_task_name"]` and the `do_pids` parameter set to `False`.

    Parameters:
        None

    Returns:
        None
    """
    if not check_for_single_name(
        PrimeItems.tasker_root_elements["all_profiles"],
        PrimeItems.program_arguments["single_profile_name"],
        do_pids=True,
    ):
        _ = check_for_single_name(
            PrimeItems.tasker_root_elements["all_tasks"],
            PrimeItems.program_arguments["single_task_name"],
            do_pids=False,
        )


# Outline the Tasker Configuration
def outline_the_configuration() -> None:
    """
    Outline the Tasker Configuration
        Args:

    """

    # Start with a ruler line
    PrimeItems.output_lines.add_line_to_output(1, "<hr>", FormatLine.dont_format_line)

    # Define our network.
    network = {}

    # If doing a single profile or task, set single project to this profile/task's project
    fix_project_name_for_single_name()

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

    # Make sure there is something to outline
    if (
        not PrimeItems.tasker_root_elements["all_tasks"]
        and not PrimeItems.tasker_root_elements["all_profiles"]
        and not PrimeItems.tasker_root_elements["all_projects"]
    ):
        PrimeItems.output_lines.add_line_to_output(
            0,
            "Nothing to outline",
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )
        return

    # Go do it!  Generate the outline near the bottom of the output.
    do_the_outline(network)

    # End the list
    PrimeItems.output_lines.add_line_to_output(
        3,
        "",
        FormatLine.dont_format_line,
    )

    # Now generate the outline diagram text file.
    if network:
        network_map(network)
