#! /usr/bin/env python3

#                                                                                      #
# dirout: Add the directory to the output queue                                        #
#                                                                                      #
#         This code is tricky.  We create the directory as we build the output queue,  #
#         and then print it while processing/writing to file the output queue.         #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import math

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import NO_PROFILE, NORMAL_TAB, TABLE_BACKGROUND_COLOR, TABLE_BORDER, FormatLine
from maptasker.src.xmldata import find_task_by_name

period = "."


# Search a list of lists for a given string.  Return True if found.
def search_lists(search_string: str, list_of_lists: list) -> bool:
    """
    Search a list of lists for a given string.  Return True if found.
        Args:
            search_string (str): string to search for
            list_of_lists (list): pointer to the list of lists to search through

        Returns:
            boolean: True if string found in list of lists, False otherwise
    """
    # Convert list to a set for faster performance.
    lookup = {item[1] for item in list_of_lists}
    return search_string in lookup


# Add directory item (Project/Profile/Task/Scene) to our dictionary of items
def add_directory_item(key: str, name: str) -> None:
    """
    We are doing a directory.  Add the Project/Profile/Task/Scene name and hyperlink name to our dictionary of items
        Args:
            key (str): "project", "profile", "task", or "scene"
            directory_head (list): pointer to
                PrimeItems.directory_items"]["directory_head"]
                where "directory_head is "project", "profile", "task", or "scene"
            name (str): name of the Project/Profile/Task/Scene
    """

    # Only set values if we haven't already done this named item
    if not search_lists(name, PrimeItems.directory_items[key]) and name != NO_PROFILE:
        hyperlink_name = name.replace(" ", "_")
        PrimeItems.directory_items["current_item"] = f"{key}_{hyperlink_name}"
        PrimeItems.directory_items[key].append([hyperlink_name, name])
    else:
        PrimeItems.directory_items["current_item"] = ""


#######################################################################################
# Given a list of hyperlinks,determine the optimum number of rows and columns
#######################################################################################
def calculate_grid_size(items: list, max_columns: int) -> tuple:
    """
    Calculates the size of a grid based on the number of items in a list.
    The column width can be no larger than 6

    Args:
        items (list): A list of items.
        max_columns: maximum width/column size allowed

    Returns:
        tuple: A tuple containing the number of rows and columns in the grid.

    Example:
        ```python
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        num_rows, num_columns = calculate_grid_size(items)
        print(f"Number of rows: {num_rows}")
        print(f"Number of columns: {num_columns}")
        ```
    """
    num_items = len(items)
    num_columns = min(max_columns, num_items)  # Limit the number of columns to 6 at most
    num_rows = math.ceil(num_items / num_columns)
    return num_rows, num_columns


#######################################################################################
# Given a list of hyperlinks, build a table and output the table
#######################################################################################
def output_table(hyperlinks: list, max_columns: int) -> None:
    """
    Generates a Python docstring for the `output_table` function.

    The function takes two parameters: `hyperlinks` and max_columns.
    It outputs a table based on the provided primary items and hyperlinks.

    Args:
        hyperlinks (list): A boolean value indicating whether hyperlinks should be
            included in the table.
        max_columns (int): Integer for the number of columns to make the table.

    Returns:
        None
    """

    # max_columns = 6  # Maximum number of columns
    num_rows, max_columns = calculate_grid_size(hyperlinks, max_columns)

    # Now build the html needed for the table with the hyperlinks in it
    html_table = generate_html_table(hyperlinks, num_rows, max_columns)

    PrimeItems.output_lines.add_line_to_output(
        5,
        html_table,
        ["", "profile_color", FormatLine.add_end_span],
    )


#######################################################################################
# Given a number of rows and columns and data, format it as a table in html
#######################################################################################
def generate_html_table(data: list, rows: int, columns: int) -> str:
    """
    Generates an HTML table from a given data dictionary.

    The function takes a data dictionary and converts it into an HTML table format.

    Args:
        data (dict): A dictionary containing the data for the table.
        rows: number of rows for table
        columns: number of columns for table

    Returns:
        str: The generated HTML table.

    Example:
        ```python
        data = {
            "header": ["Name", "Age", "City"],
            "rows": [["John Doe", 25, "New York"], ["Jane Smith", 30, "Los Angeles"], ["Mike Johnson", 35, "Chicago"]],
        }

        html_table = generate_html_table(data)
        print(html_table)
        ```
    """

    # Set up the variables
    html = f'{TABLE_BORDER}<table style="width:100%;margin-left: 20;text-align:left;background-color:\
    {TABLE_BACKGROUND_COLOR};">\n'
    index = 0
    data.sort()  # Sort the directory by name

    # Build our table
    for _ in range(rows):
        html += "  <tr> \n"
        for _ in range(columns):
            if index < len(data):
                html += f"    <td>{data[index]}</td>\n"
                index += 1
            else:
                html += "    <td></td>\n"
        html += "  </tr>\n"

    html += "</table>"
    return html


#######################################################################################
# Output directory for information at the bottom of the output
#######################################################################################
def do_trailing_matters() -> None:
    """
    Create a hyperlinks for key items that are at the bottom of the output

    Args:
        None

    Returns:
        None
    """
    trailing_matter = []
    PrimeItems.output_lines.add_line_to_output(
        5,
        f"<br><br>{NORMAL_TAB}Trailing Information{period*50}<br><br>",
        ["", "project_color", FormatLine.add_end_span],
    )

    # Do the Configuration Variables
    if PrimeItems.program_arguments["display_detail_level"] == 4:
        trailing_matter.append("<a href=#unreferenced_variables>Unreferenced Global Variables</a>")

    # Do Configuration Outline
    if PrimeItems.program_arguments["outline"]:
        trailing_matter.append("<a href=#configuration_outline>Configuration Outline</a>")

    # Add Grand Totals.
    trailing_matter.append("<a href=#grand_totals>Grand Totals</a>")

    # Output the table
    output_table(trailing_matter, 4)


# Determinme if an item is in a specific a specific Project.
def find_task_in_project(start_index: object, item_to_match: str, items_to_search: str) -> bool:
    """
    Determinme if an item is in a specific a specific Project.
        Args:
            start_index (object): Which index to start our search within
                PrimeItems.tasker_root_elements["all_projects"]
            item_to_match (str): item to look for within Project
            items_to_search (str): Project item to search: "scenes", "pids", "tids"

        Returns:
            bool: True if found, False otherwise
    """
    if start_index:
        begin_search_at = PrimeItems.tasker_root_elements["all_projects"][start_index]
    else:
        begin_search_at = PrimeItems.tasker_root_elements["all_projects"]
    for project_item in begin_search_at:
        project = PrimeItems.tasker_root_elements["all_projects"][project_item]["xml"]
        items_in_project = project.find(items_to_search)
        if items_in_project is not None and item_to_match in items_in_project.text.split(","):
            return True, project
    return False, ""


# Doing Scene hyperlink.  Make sure it is okay to do this Scene hyperlink.
def check_scene(item: str) -> bool:
    """
    Check to make sure this Scene should be included in the output
        Args:
            item (str): directory hyperlink item we are processing

        Returns:20.
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    # Single Project?
    if PrimeItems.program_arguments["single_project_name"]:
        found, project = find_task_in_project("", item[1], "scenes")
        return found

    # Single Profile?
    if profile_name := PrimeItems.program_arguments["single_profile_name"]:
        # Find out if this Scene is in the single Project's Profile' we are looking for.
        # Get the Profile ID for the single Profile we are looking for
        for profile_id in PrimeItems.tasker_root_elements["all_profiles"]:
            if PrimeItems.tasker_root_elements["all_profiles"][profile_id]["name"] == profile_name:
                found, project = find_task_in_project("", profile_id, "pids")
                if found:
                    scenes = project.find("scenes")
                    if scenes is not None and item[1] in scenes.text.split(","):
                        return True

        return False
    # Single Task?
    if (profile_name := PrimeItems.program_arguments["single_task_name"]) and (
        this_task_id := find_task_by_name(PrimeItems.program_arguments["single_task_name"])
    ):
        # Find the Project this single Task belongs to.
        found, project = find_task_in_project("", this_task_id, "tids")
        if found:
            # Found Project with Profile, now check If Scenes in Project
            scenes = project.find("scenes")
            if scenes is not None and item[1] in scenes.text.split(","):
                return True
        return False

    # Not doing single name...Scene hyperlink is okay to include.
    return True


# Doing Task hyperlink.  Make sure it is okay to do this Task hyperlink.
def check_task(item: str) -> bool:
    """
    Check to make sure this Task should be included in the output
        Args:
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hyperlink, False if it is to be ingored.
    """
    if PrimeItems.program_arguments["single_task_name"] and item[1] != PrimeItems.program_arguments["single_task_name"]:
        return False
    # Doing a single Profile?
    if PrimeItems.program_arguments["single_profile_name"]:
        # Get this Task's ID.
        if this_task_id := find_task_by_name(item[1]):
            # Find the Project that belongs to the Profile we are looking for.
            for project_item in PrimeItems.tasker_root_elements["all_projects"]:
                project = PrimeItems.tasker_root_elements["all_projects"][project_item]["xml"]
                pids = project.find("pids")
                # See if the Profile we are looking for is in this Project
                if pids is not None:
                    for profile_id in pids.text.split(","):
                        if (
                            PrimeItems.program_arguments["single_profile_name"]
                            == PrimeItems.tasker_root_elements["all_profiles"][profile_id]["name"]
                        ):
                            # Get the Project's Task IDs
                            tids = project.find("tids")
                            if tids is not None and this_task_id in tids.text.split(","):
                                return True
        return False
    return True


# Doing Profile hyperlink.  Make sure it is okay to do this Profile hyperlink.
def check_profile(item: str) -> bool:
    """
    Check to make sure this Profile should be included in the output
        Args:
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    if (
        PrimeItems.program_arguments["single_profile_name"]
        and item[1] != PrimeItems.program_arguments["single_profile_name"]
    ):
        return False
    return not PrimeItems.program_arguments["single_task_name"]


# Doing Project hyperlinks.  Make sure it is okay to do this Project hyperlink.
def check_project(item: str) -> bool:
    """
    Check to make sure this Project should be included in the output
        Args:
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    project = PrimeItems.tasker_root_elements["all_projects"][item[1]]["xml"]
    project_id = project.attrib.get("sr")
    project_id = project_id[4:]
    # Are we looking for specific Preoject and this is it?
    if PrimeItems.program_arguments["single_project_name"]:
        if item[1] != PrimeItems.program_arguments["single_project_name"]:
            return False
    # Single Profile?
    elif PrimeItems.program_arguments["single_profile_name"]:
        pids = project.find("pids")
        if pids is None or project_id not in pids.text.split(","):
            return False
    # Single Task?
    elif PrimeItems.program_arguments["single_task_name"]:
        return False
    return True


# Check to make sure this directory item should be included in the output.
def check_item(name: str, item: str) -> bool:
    """
    Check to make sure this item should be included in the output
        Args:
            name: element name: directory we are doing:
                    "projects", "profiles", "tasks", "scenes"
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hyperlink, False if it is to be ingored.
    """
    function_mappings = {
        "projects": check_project,
        "profiles": check_profile,
        "tasks": check_task,
        "scenes": check_scene,
    }
    # Check if doing a single item...only build directory for that item.
    return function_mappings[name](item)


#######################################################################################
# Output table for specific Tasker element: Projects, Profiles, Tasks, Scenes
#######################################################################################
def do_tasker_element(name: str) -> None:
    """
    Build an html table and output it for the given Tasker element: Project, Profile,
        Scene or Task.  DO this by traversing the entire xml trees.

    This function adds project information to the output lines.
    It generates hyperlinks for each project and builds an HTML table with hyperlinks.

    Args:
        name: element name: directory we are doing:
                "projects", "profiles", "tasks", "scenes"

    Returns:
        None
    """
    # Output the table header
    if PrimeItems.directory_items[name]:
        # Go through each item and accumulate the names to be used for
        # the directory hyperlinks
        directory_hyperlinks = []

        for item in PrimeItems.directory_items[name]:
            if check_item(name, item):
                # Directory item is valid for this name.
                # Get the name and display name for this item
                hyperlink_name = item[0]
                display_name = item[1]
                # Append our hyperlink to this Project to the list
                directory_hyperlinks.append(f"<a href=#{name}_{hyperlink_name}>{display_name}</a>")

        if directory_hyperlinks:
            # Output the name title: Project, Profile, Task, Scene
            PrimeItems.output_lines.add_line_to_output(
                5,
                f"{NORMAL_TAB}{name.capitalize()}{period*60}<br><br>",
                ["<br><br>", "project_color", FormatLine.add_end_span],
            )
            # 6 columns for projects, 5 columns for tasks
            number_of_columns = 5 if name == "tasks" else 6
            output_table(directory_hyperlinks, number_of_columns)


#######################################################################################
# Output directory by appending it to our output queue
#######################################################################################
def output_directory() -> None:
    """
    Writes the directory to the output queue.

    Args:
        None

    Returns:
        None
    """

    # Add heading
    PrimeItems.output_lines.add_line_to_output(
        5,
        f"<h2>{NORMAL_TAB}Directory</h2><br><br>",
        ["<br><br>", "profile_color", FormatLine.add_end_span],
    )
    # Ok, run through the Tasker key elements and output the directory for each
    # Only do Projects and Profiles if not looking for a single Project or Profile
    if not (PrimeItems.program_arguments["single_profile_name"] or PrimeItems.program_arguments["single_task_name"]):
        do_tasker_element("projects")
    do_tasker_element("profiles")
    if PrimeItems.program_arguments["display_detail_level"] != 0:
        do_tasker_element("tasks")
    do_tasker_element("scenes")

    do_trailing_matters()

    # Add final rule and break
    PrimeItems.output_lines.add_line_to_output(5, "<hr><br><br>\n", FormatLine.dont_format_line)
