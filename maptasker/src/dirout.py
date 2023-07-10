#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# dirout: Add the directory to the output queue                                      #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import darkdetect
import math
from maptasker.src.frmthtml import format_html

period = "."


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

    The function takes two parameters: `primary_items` and `hyperlinks`. It outputs a table based on the provided primary items and hyperlinks.

    Args:
        primary_items (list): A list of primary items for the table.
        hyperlinks (bool): A boolean value indicating whether hyperlinks should be included in the table.
        max_columns: Integer for the number of columns to make the table.

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
        format_html(
            primary_items["colors_to_use"],
            "profile_color",
            "",
            html_table,
            True,
        ),
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
    html = f'{border}<table style="width:100%;text-align:left;background-color:{color_to_use};">\n'
    index = 0
    data.sort()

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
        primary_items (dict):dictionary of the primary items used throughout the module.  See mapit.py for details

    Returns:
        None

    """
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        format_html(
            primary_items["colors_to_use"],
            "project_color",
            "",
            f"<br><br>Trailing Information{period*50}<br><br>",
            True,
        ),
    )

    # Do Tasks that are not associated with any Profile, Projects without Tasks and without Profiles
    trailing_matter = [
        "<a href=#tasks_no_profile>Named Tasks that are not called by any Profile</a>",
        "<a href=#projects_wo_tasks>Projects without Tasks</a>",
        "<a href=#projects_wo_profiles>Projects without Profiles</a>",
        "<a href=#grand_totals>Grand Totals</a>",
    ]

    # Output the table
    output_table(primary_items, trailing_matter, 4)

    return


#######################################################################################
# Output table for specific Tasker element: Projects, Profiles, Tasks, Scenes
#######################################################################################
def do_tasker_element(primary_items: dict, name: str) -> None:
    """
    Build an html table and output it for the given Tasker element: Project, Profile, or Task

    This function adds project information to the output lines of primary_items.
    It generates hyperlinks for each project and builds an HTML table with the hyperlinks.

    Args:
        primary_items (dict):dictionary of the primary items used throughout the module.  See mapit.py for details
        name: element name: "project", "profile", "task", "scene"

    Returns:
        None

    """
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        format_html(
            primary_items["colors_to_use"],
            "project_color",
            "<br><br>",
            f"{name.capitalize()}s{period*60}<br><br>",
            True,
        ),
    )

    doing_project = False
    key_to_find = "nme"
    number_of_columns = 6
    match name:
        case "project":
            root = primary_items["tasker_root_elements"]["all_projects"]
            key_to_find = "name"
            doing_project = True
        case "profile":
            root = primary_items["tasker_root_elements"]["all_profiles"]
        case "task":
            root = primary_items["tasker_root_elements"]["all_tasks"]
            number_of_columns = 5
        case "scene":
            root = primary_items["tasker_root_elements"]["all_scenes"]
        case _:
            return

    # Go through each item and accumulate the names to be used for the directory hyperlinks
    directory_hyperlinks = []
    for item in root:
        if not doing_project:
            item = root[item]
        if item.find(key_to_find) is None:
            continue

        # Hyperlink name can not have any embedded blanks.  Substitute a dash for each blank
        display_name = item.find(key_to_find).text
        hyperlink_name = display_name.replace(" ", "_")
        # Append our hyperlink to this Project to the list
        directory_hyperlinks.append(
            f"<a href=#{name}_{hyperlink_name}>{display_name}</a>"
        )

    output_table(primary_items, directory_hyperlinks, number_of_columns)

    return


#######################################################################################
# Output directory by appending it to our output queue
#######################################################################################
def output_directory(primary_items: dict) -> None:
    """
    Writes the directory to the output queue.

    Args:
        primary_items (dict): dictionary of the primary items used throughout the module.  See mapit.py for details

    Returns:
        None
    """

    # Add heading
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        format_html(
            primary_items["colors_to_use"],
            "profile_color",
            "",
            "<h2>directory</h2><br><br>",
            True,
        ),
    )
    # Ok, run through the Tasker key elements and output the directory for each
    do_tasker_element(primary_items, "project")
    do_tasker_element(primary_items, "profile")
    do_tasker_element(primary_items, "task")
    do_tasker_element(primary_items, "scene")

    do_trailing_matters(primary_items)
    
     # Add final rule and break
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        "<hr><br><br>\n",
    )

    return
