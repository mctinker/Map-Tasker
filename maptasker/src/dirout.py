#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# dirout: Add the directory to the output queue                                        #
#                                                                                      #
#         This code is tricky.  We create the directory as we build the output queue,  #
#         and then print it while processing/writing to file the output queue.         #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import math

import darkdetect

from maptasker.src.sysconst import NO_PROFILE, FormatLine

period = "."


# ##################################################################################
# Search a list of lists for a given string.  Return True if found.
# ##################################################################################
def search_lists(search_string: str, list_of_lists: list) -> bool:
    """_summary_
    Search a list of lists for a given string.  Return True if found.
        Args:
            search_string (str): string to search for
            list_of_lists (list): pointer to the list of lists to search through

        Returns:
            boolean: True if string found in list of lists, False otherwise
    """
    return any(search_string == item[1] for item in list_of_lists)


# ##################################################################################
# Add directory item (Project/Profile/Task/Scene) to our dictionary of items
# ##################################################################################
def add_directory_item(primary_items: dict, key: str, name: str):
    """_summary_
    We are doing a directory.  Add the Project/Profile/Task/Scene name and hyperlink name to our dictionary of items
        Args:
            primary_items (dict): Program registry. See primitem.py for details.
            key (str): "project", "profile", "task", or "scene"
            directory_head (list): pointer to
                primary_items["directory_items"]["directory_head"]
                where "directory_head is "project", "profile", "task", or "scene"
            name (str): name of the Project/Profile/Task/Scene
    """

    # Only set values if we haven't already done this named item
    if (
        not search_lists(name, primary_items["directory_items"][key])
        and name != NO_PROFILE
    ):
        hyperlink_name = name.replace(" ", "_")
        primary_items["directory_items"]["current_item"] = f"{key}_{hyperlink_name}"
        primary_items["directory_items"][key].append([hyperlink_name, name])
    else:
        primary_items["directory_items"]["current_item"] = ""


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
        ```"""
    num_items = len(items)
    num_columns = min(
        max_columns, num_items
    )  # Limit the number of columns to 6 at most
    num_rows = math.ceil(num_items / num_columns)
    return num_rows, num_columns


#######################################################################################
# Given a list of hyperlinks, build a table and output the table
#######################################################################################
def output_table(primary_items: dict, hyperlinks: list, max_columns: int) -> None:
    """
    Generates a Python docstring for the `output_table` function.

    The function takes two parameters: `primary_items` and `hyperlinks`.
    It outputs a table based on the provided primary items and hyperlinks.

    Args:
        primary_items (dict): Program registry. See primitem.py for details.
        hyperlinks (list): A boolean value indicating whether hyperlinks should be
            included in the table.
        max_columns (int): Integer for the number of columns to make the table.

    Returns:
        None

    Example:
        ```python
        primary_items = ["Item 1", "Item 2", "Item 3"]
        hyperlinks = True

        output_table(primary_items, hyperlinks)
        ```
    """

    # max_columns = 6  # Maximum number of columns
    num_rows, max_columns = calculate_grid_size(hyperlinks, max_columns)

    # Now build the html needed for the table with the hyperlinks in it
    html_table = generate_html_table(hyperlinks, num_rows, max_columns)

    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        html_table,
        ["", "profile_color", FormatLine.add_end_span],
    )
    return


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
            "rows": [
                ["John Doe", 25, "New York"],
                ["Jane Smith", 30, "Los Angeles"],
                ["Mike Johnson", 35, "Chicago"]
            ]
        }

        html_table = generate_html_table(data)
        print(html_table)
        ```"""
    # Set up background color
    color_to_use = "LightSteelBlue" if darkdetect.isDark() else "DarkTurquoise"
    border = (
        "\n"
        "<style> \
            table, \
            td, \
            th { \
            padding: 5px; \
            border: 2px solid #1c87c9; \
            border-radius: 3px; \
            background-color: #128198; \
            text-align: center; \
            } \
        </style>"
    )

    # Set up the variables
    html = f'{border}<table style="width:100%;text-align:left;background-color:\
    {color_to_use};">\n'
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
def do_trailing_matters(primary_items: dict) -> None:
    """
    Create a hyperlinks for key items that are at the bottom of the output

    Args:
        primary_items (dict): Program registry. See primitem.py for details.

    Returns:
        None

    """
    trailing_matter = []
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        f"<br><br>Trailing Information{period*50}<br><br>",
        ["", "project_color", FormatLine.add_end_span],
    )

    # Do the Configuration Variables
    if primary_items["program_arguments"]["display_detail_level"] == 4:
        trailing_matter.append(
            "<a href=#unreferenced_variables>Unreferenced Global Variables</a>"
        )

    # Do Configuration Outline
    if primary_items["program_arguments"]["outline"]:
        trailing_matter.append(
            "<a href=#configuration_outline>Configuration Outline</a>"
        )

    # Add Grand Totals.
    trailing_matter.append("<a href=#grand_totals>Grand Totals</a>")

    # Output the table
    output_table(primary_items, trailing_matter, 4)

    return


# ##################################################################################
# Determinme if an item is in a specific a specific Project.
# ##################################################################################
def find_task_in_project(
    primary_items: dict, start_index: object, item_to_match: str, items_to_search: str
) -> bool:
    """_summary_
    Determinme if an item is in a specific a specific Project.
        Args:
            primary_items (dict): Program registry. See primitem.py for details.
            start_index (object): Which index to start our search within
                primary_items["tasker_root_elements"]["all_projects"]
            item_to_match (str): item to look for within Project
            items_to_search (str): Project item to search: "scenes", "pids", "tids"

        Returns:
            bool: True if found, False otherwise
    """
    if start_index:
        begin_search_at = primary_items["tasker_root_elements"]["all_projects"][
            start_index
        ]
    else:
        begin_search_at = primary_items["tasker_root_elements"]["all_projects"]
    for project_item in begin_search_at:
        project = primary_items["tasker_root_elements"]["all_projects"][project_item][0]
        items_in_project = project.find(items_to_search)
        if (
            items_in_project is not None
            and item_to_match in items_in_project.text.split(",")
        ):
            return True, project
    return False, ""


# ##################################################################################
# Doing Scene hyperlink.  Make sure it is okay to do this Scene hyperlink.
# ##################################################################################
def check_scene(primary_items: dict, item: str) -> bool:
    """_summary_
    Check to make sure this Scene should be included in the output
        Args:
            primary_items (dict): Program registry. See primitem.py for details.
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    # Single Project?
    if primary_items["program_arguments"]["single_project_name"]:
        found, project = find_task_in_project(primary_items, "", item["name"], "scenes")
        return found

    # Single Profile?
    if profile_name := primary_items["program_arguments"]["single_profile_name"]:
        # Find out if this Scene is in the single Project's Profile' we are looking for.
        # Get the Profile ID for the single Profile we are looking for
        for profile_id in primary_items["tasker_root_elements"]["all_profiles"]:
            if (
                primary_items["tasker_root_elements"]["all_profiles"][profile_id][
                    "name"
                ]
                == profile_name
            ):
                found, project = find_task_in_project(
                    primary_items, "", profile_id, "pids"
                )
                if found:
                    scenes = project.find("scenes")
                    if scenes is not None and item["name"] in scenes.text.split(","):
                        return True

        return False
    # Single Task?
    if profile_name := primary_items["program_arguments"]["single_task_name"]:
        # Get this Task's ID.
        if this_task_id := next(
            (
                task_item
                for task_item in primary_items["tasker_root_elements"]["all_tasks"]
                if primary_items["tasker_root_elements"]["all_tasks"][task_item]["name"]
                == primary_items["program_arguments"]["single_task_name"]
            ),
            "",
        ):
            # Find the Project this single Task belongs to.
            found, project = find_task_in_project(
                primary_items, "", this_task_id, "tids"
            )
            if found:
                # Found Project with Profile, now check If Scenes in Project
                scenes = project.find("scenes")
                if scenes is not None and item["name"] in scenes.text.split(","):
                    return True
            return False

    # Not doing single name...Scene hyperlink is okay to include.
    return True


# ##################################################################################
# Doing Task hyperlink.  Make sure it is okay to do this Task hyperlink.
# ##################################################################################
def check_task(primary_items: dict, item: str) -> bool:
    """_summary_
    Check to make sure this Task should be included in the output
        Args:
            primary_items (dict): Program registry. See primitem.py for details.
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    if (
        primary_items["program_arguments"]["single_task_name"]
        and item["name"] != primary_items["program_arguments"]["single_task_name"]
    ):
        return False
    # Doing a single Profile?
    if primary_items["program_arguments"]["single_profile_name"]:
        # Get this Task's ID.
        if this_task_id := next(
            (
                task_item
                for task_item in primary_items["tasker_root_elements"]["all_tasks"]
                if primary_items["tasker_root_elements"]["all_tasks"][task_item]["name"]
                == item["name"]
            ),
            "",
        ):
            # Find the Project that belongs to the Profile we are looking for.
            for project_item in primary_items["tasker_root_elements"]["all_projects"]:
                project = primary_items["tasker_root_elements"]["all_projects"][
                    project_item
                ][0]
                pids = project.find("pids")
                # See if the Profile we are looking for is in this Project
                if pids is not None:
                    for profile_id in pids.text.split(","):
                        if (
                            primary_items["program_arguments"]["single_profile_name"]
                            == primary_items["tasker_root_elements"]["all_profiles"][
                                profile_id
                            ]["name"]
                        ):
                            # Get the Project's Task IDs
                            tids = project.find("tids")
                            if tids is not None and this_task_id in tids.text.split(
                                ","
                            ):
                                return True
        return False
    return True


# ##################################################################################
# Doing Profile hyperlink.  Make sure it is okay to do this Profile hyperlink.
# ##################################################################################
def check_profile(primary_items: dict, item: str) -> bool:
    """_summary_
    Check to make sure this Profile should be included in the output
        Args:
            primary_items (dict): Program registry. See primitem.py for details.
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    if (
        primary_items["program_arguments"]["single_profile_name"]
        and item["name"] != primary_items["program_arguments"]["single_profile_name"]
    ):
        return False
    return not primary_items["program_arguments"]["single_task_name"]


# ##################################################################################
# Doing Project hyperlinks.  Make sure it is okay to do this Project hyperlink.
# ##################################################################################
def check_project(primary_items: dict, item: str) -> bool:
    """_summary_
    Check to make sure this Project should be included in the output
        Args:
            primary_items (dict): Program registry. See primitem.py for details.
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hperlink, False if it is to be ingored.
    """
    project = primary_items["tasker_root_elements"]["all_projects"][item[1]]["xml"]
    project_id = project.attrib.get("sr")
    project_id = project_id[4:]
    # Are we looking for specific Preoject and this is it?
    if primary_items["program_arguments"]["single_project_name"]:
        if item["name"] != primary_items["program_arguments"]["single_project_name"]:
            return False
    # Single Profile?
    elif primary_items["program_arguments"]["single_profile_name"]:
        pids = project.find("pids")
        if pids is None or project_id not in pids.text.split(","):
            return False
    # Single Task?
    elif primary_items["program_arguments"]["single_task_name"]:
        return False
    return True


# ##################################################################################
# Check to make sure this item should be included in the output
# ##################################################################################
def check_item(primary_items: dict, name: str, item: str) -> bool:
    """_summary_
    Check to make sure this item should be included in the output
        Args:
            primary_items (dict): Program registry. See primitem.py for details.
            name: element name: directory we are doing:
                    "projects", "profiles", "tasks", "scenes"
            item (str): directory hyperlink item we are processing

        Returns:
            bool: True if we should output this hyperlink, False if it is to be ingored.
    """
    # Check if doing a single item...only build directory for that item
    match name:
        # Doing Project hyperlink...
        case "projects":
            return check_project(primary_items, item)

        # Doing Profile hyperlink..
        case "profiles":
            return check_profile(primary_items, item)

        case "tasks":
            return check_task(primary_items, item)

        case "scenes":
            return check_scene(primary_items, item)

        case _:
            return True
    return True


#######################################################################################
# Output table for specific Tasker element: Projects, Profiles, Tasks, Scenes
#######################################################################################
def do_tasker_element(primary_items: dict, name: str) -> None:
    """
    Build an html table and output it for the given Tasker element: Project, Profile,
        Scene or Task.  DO this by traversing the entire xml trees.

    This function adds project information to the output lines of primary_items.
    It generates hyperlinks for each project and builds an HTML table with hyperlinks.

    Args:
        primary_items (dict): Program registry. See primitem.py for details.
        name: element name: directory we are doing:
                "projects", "profiles", "tasks", "scenes"

    Returns:
        None

    """
    # Output the table header
    if primary_items["directory_items"][name]:
        # Go through each item and accumulate the names to be used for
        # the directory hyperlinks
        directory_hyperlinks = []
        for item in primary_items["directory_items"][name]:
            if check_item(primary_items, name, item):
                # Directory item is valid for this name.
                # Get the name and display name for this item
                hyperlink_name = item[0]
                display_name = item[1]
                # Append our hyperlink to this Project to the list
                directory_hyperlinks.append(
                    f"<a href=#{name}_{hyperlink_name}>{display_name}</a>"
                )

        if directory_hyperlinks:
            # Output the name title: Project, Profile, Task, Scene
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                5,
                f"{name.capitalize()}{period*60}<br><br>",
                ["<br><br>", "project_color", FormatLine.add_end_span],
            )
            # 6 columns for projects, 5 columns for tasks
            number_of_columns = 5 if name == "tasks" else 6
            output_table(primary_items, directory_hyperlinks, number_of_columns)

    return


#######################################################################################
# Output directory by appending it to our output queue
#######################################################################################
def output_directory(primary_items: dict) -> None:
    """
    Writes the directory to the output queue.

    Args:
        :param primary_items:  Program registry.  See primitem.py for details.

    Returns:
        None
    """

    # Add heading
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        "<h2>Directory</h2><br><br>",
        ["<br><br>", "profile_color", FormatLine.add_end_span],
    )
    # Ok, run through the Tasker key elements and output the directory for each
    # Only do Projects and Profiles if not looking for a single Project or Profile
    if not (
        primary_items["program_arguments"]["single_profile_name"]
        or primary_items["program_arguments"]["single_task_name"]
    ):
        do_tasker_element(primary_items, "projects")
    do_tasker_element(primary_items, "profiles")
    if primary_items["program_arguments"]["display_detail_level"] != 0:
        do_tasker_element(primary_items, "tasks")
    do_tasker_element(primary_items, "scenes")

    do_trailing_matters(primary_items)

    # Add final rule and break
    primary_items["output_lines"].add_line_to_output(
        primary_items, 5, "<hr><br><br>\n", FormatLine.dont_format_line
    )

    return

    return
