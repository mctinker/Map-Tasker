#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# proclist: process list - process a list of line items for Tasks and Scenes           #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import defusedxml

from maptasker.src.dirout import add_directory_item
from maptasker.src.nameattr import add_name_attribute
from maptasker.src.property import get_properties
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, FormatLine, logger
from maptasker.src.taskactn import get_task_actions_and_output
from maptasker.src.twisty import add_twisty, remove_twisty


# ################################################################################
# Parse out name and add any attributes to it: spacing and HTML.
# ################################################################################
def adjust_name(primary_items: dict, list_type: str, the_item: str) -> str:
    """_summary_
    Parse out name and add any attributes to it
        Args:
            :param primary_items:  Program registry.  See primitem.py for details.
            list_type (str): The type of the list.
            the_item (str): The text item to process.

        Returns:
            str: The text item altered as necessary with name attributes.
    """
    # The name is either preceeded by "&nbsp;" or "<em>"
    if list_type == "Task:":
        the_name_string = the_item.split("&nbsp;", 1)
        if len(the_name_string) <= 1:
            the_name_string = the_item.split(" <em>", 1)
        the_rest = the_name_string[1]
        the_name = the_name_string[0]
    else:
        the_name = the_item
        the_rest = ""
    altered_name = add_name_attribute(primary_items, the_name)

    return f"{altered_name}{the_rest}"


# ################################################################################
# Given an item, build output line for Task or Scene
# ################################################################################
def format_task_or_scene(
    primary_items: dict, list_type: list, the_item: str
) -> tuple[str, str]:
    """_summary_
    Given an item, build output line for Task or Scene
    Args:
        primary_items (dict): Program registry.  See primitem.py for details.
        list_type (list): Either "Task:" or "Scene:"
        the_item (str): text for Task or Scene

    Returns:
        tuple[str, str]: Our formatted output line and color to user
    """
    # Format the Task/Scene name as needed: spacing and HTML
    if list_type in {"Task:", "Scene:"}:
        the_item_altered = adjust_name(primary_items, list_type, the_item)
    else:
        the_item_altered = the_item

    # Format the output line
    output_line = f"{list_type}&nbsp;{the_item_altered}"

    # Set up the correct color for twisty of needed
    color_to_use = "scene_color" if list_type == "Scene:" else "task_color"

    return output_line, color_to_use


# ################################################################################
# If doing a directory, format and add it.  If doing twisties, add a twisty
# ################################################################################
def add_dictionary_and_twisty(
    primary_items: dict,
    list_type: str,
    the_item: str,
    the_task: defusedxml,
    output_line: str,
    color_to_use: str,
) -> tuple[str, str]:
    """_summary_
    If doing a directory, format and add it.  If doing twisties, add a twisty
        Args:
           primary_items (dict): Program registry.  See primitem.py for details.
            list_type (list): Either "Task:" or "Scene:"
            the_item (str): text for Task or Scene
            the_task (defusedxml): XML pointer to our Task being procesed
            output_line (str): The etxt satring containing the output
            color_to_use (str): The color to use in the output

        Returns:
            tuple[str, str]: Our temporary item and temporary list item
    """
    temp_item = temp_list = ""
    if "&#45;&#45;Task:" in list_type:
        temp_item = the_item
        temp_list = list_type
        the_item = ""
        if primary_items["program_arguments"]["debug"]:  # Get the Task ID
            id_loc = list_type.find("ID:")
            if id_loc != -1:
                list_type = f"{list_type}{id_loc}"

    # Insert directory for Task
    elif primary_items["program_arguments"]["directory"] and "Task:" in list_type:
        # Get the Task name from the line being formatted
        task_id = the_task.attrib.get("sr")[4:]
        task_name = primary_items["tasker_root_elements"]["all_tasks"][task_id]["name"]
        if task_name != "":
            # Handle directory hyperlink
            add_directory_item(primary_items, "tasks", task_name)

    # Insert a hyperlink if this is a Task...it has to go before a twisty
    if (
        primary_items["program_arguments"]["directory"]
        and primary_items["directory_items"]["current_item"]
        and "Task:" in list_type
        and "&#45;&#45;Task:" not in list_type
    ):
        directory_item = f'"{primary_items["directory_items"]["current_item"]}"'
        directory = f"<a id={directory_item}></a>\n"
        primary_items["output_lines"].add_line_to_output(
            primary_items, 5, directory, FormatLine.dont_format_line
        )

    if list_type == "Scene:":
        # Force a line break first
        primary_items["output_lines"].add_line_to_output(
            primary_items, 0, "", FormatLine.dont_format_line
        )

    # Add the "twisty" to hide the Task details
    if primary_items["program_arguments"]["twisty"] and "Task:" in list_type:
        # Add the twisty magic
        add_twisty(primary_items, color_to_use, output_line)

    return temp_item, temp_list


# ################################################################################
# Given an item, format it with all of the particulars and add to output.
# ################################################################################
def format_item(
    primary_items: dict,
    list_type: str,
    the_item: str,
    the_list: list,
    the_task: defusedxml,
):
    """_summary_
    Given an item, format it with all of the particulars:
        Proper html/color/font, twisty, directory, properties, etc.
        Args:
            primary_items (dict): Program registry.  See primitem.py for details
            list_type (str): Either "Task:" or "Scene:"
            the_item (str): The string for the above type
            the_list (list): List of Tasks or Scenes
            the_task (defusedxml): The Task XML element
    """
    # Log if in debug mode
    if primary_items["program_arguments"]["debug"]:
        logger.debug(
            f"process_list  the_item:{the_item} the_list:{the_list} list_type:\
            {list_type}"
        )

    # Format the Task or Scene
    output_line, color_to_use = format_task_or_scene(primary_items, list_type, the_item)

    # If "--Task:" then this is a Task under a Scene.
    # Need to temporarily save the_item since add_line_to_output changes the_item
    temp_item, temp_list = add_dictionary_and_twisty(
        primary_items, list_type, the_item, the_task, output_line, color_to_use
    )

    # Add this Task/Scene to the output as a list item
    primary_items["output_lines"].add_line_to_output(
        primary_items, 2, output_line, FormatLine.dont_format_line
    )

    # Put the_item back with the 'ID: nnn' portion included.
    if temp_item:
        the_item = temp_item
        list_type = temp_list

    # Process Task Properties if this is a Task, display level is 3 and
    # we are not at the end dispaying Tasks that are not in any Profile
    if (
        the_task
        and "Task:" in list_type
        and primary_items["program_arguments"]["display_detail_level"] > 2
        and not primary_items["displaying_named_tasks_not_in_profile"]
    ):
        get_properties(
            primary_items,
            the_task,
            "task_color",
        )


# ##################################################################################
# Process Given a Task/Scene, process it.
# ##################################################################################
def process_item(
    primary_items: dict,
    the_item: str,
    list_type: str,
    the_task: defusedxml.ElementTree.XML,
    tasks_found: list,
) -> None:
    """
    Process the item and add it to the output.

    Args:
        :param primary_items:  Program registry.  See primitem.py for details.
        the_item (str): The text item to process.
        list_type (str): The type of the list.
        the_list (list): The list to process.
        the_task (xml element): The task to process.
        tasks_found (list): The list of tasks found.

    Returns:
        None

    """
    # This import must stay here to avoid error
    from maptasker.src.scenes import process_scene

    # Given an item, format it with all of the particulars and add to output.
    format_item(primary_items, list_type, the_item, the_item, the_task)

    # If just displaying basic details, get out.
    if primary_items["program_arguments"]["display_detail_level"] == 0:
        return

    # Output Actions for this Task if Task is unknown
    #   and not part of output for Tasks with no Profile(s)
    # Do we get the Task's Actions?
    if (
        (the_task and "Task:" in list_type and UNKNOWN_TASK_NAME in the_item)
        or ("Task:" in list_type)
    ) and "<em>No Profile" not in the_item:
        get_task_actions_and_output(
            primary_items,
            the_task,
            list_type,
            the_item,
            tasks_found,
        )

        # End the twisty hidden lines if not a Task in a Scene
        if primary_items["program_arguments"]["twisty"]:
            remove_twisty(primary_items)
        # If not a twisty but is a digit, then this is a Scene's Task...
        # delete previous </ul>
        elif the_item.isdigit:
            primary_items["output_lines"].delete_last_line(primary_items)

    elif (
        list_type == "Scene:"
        and primary_items["program_arguments"]["display_detail_level"] > 1
    ):
        # We have a Scene: process its details
        process_scene(
            primary_items,
            the_item,
            tasks_found,
        )

    # Remove twisty if not displaying level 0
    elif primary_items["program_arguments"]["twisty"]:
        if primary_items["program_arguments"]["display_detail_level"] > 0:
            remove_twisty(primary_items)
        else:
            # End list if doing twisty and displaying level 0
            primary_items["output_lines"].add_line_to_output(
                primary_items, 3, "", FormatLine.dont_add_end_span
            )

    return


# ##################################################################################
# Process Task/Scene text/line item: call recursively for Tasks within Scenes
# ##################################################################################
def process_list(
    primary_items: dict,
    list_type: str,
    the_list: list,
    the_task: defusedxml.ElementTree.XML,  # type: ignore
    tasks_found: list,
) -> None:
    """
    Process Task/Scene text/line item: call recursively for Tasks within Scenes
        :param primary_items:  Program registry.  See primitem.py for details.
        :param list_type: Task or Scene
        :param the_list: list of Task names tro process
        :param the_task: Task/Scene xml element
        :param tasks_found: list of Tasks found so far
        :return:
    """

    # Go through all Tasks in the list
    for the_item in the_list:
        # Process the item (list of items)
        process_item(primary_items, the_item, list_type, the_task, tasks_found)

    return
