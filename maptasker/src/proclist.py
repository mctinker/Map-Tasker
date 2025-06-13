#! /usr/bin/env python3
"""
proclist: process list - process a list of line items for Tasks and Scenes

MIT License   Refer to https://opensource.org/license/mit
"""

#                                                                                      #
# proclist: process list - process a list of line items for Tasks and Scenes           #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import defusedxml

from maptasker.src.dirout import add_directory_item
from maptasker.src.nameattr import add_name_attribute
from maptasker.src.primitem import PrimeItems
from maptasker.src.property import get_properties
from maptasker.src.sysconst import FormatLine, logger
from maptasker.src.taskactn import get_task_actions_and_output
from maptasker.src.twisty import add_twisty, remove_twisty


# ################################################################################
# Parse out name and add any attributes to it: spacing and HTML.
# ################################################################################
def adjust_name(list_type: str, the_item: str) -> str:
    """
    Parse out name and add any attributes to it
        Args:

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
    altered_name = add_name_attribute(the_name)

    return f"{altered_name}{the_rest}"


# ################################################################################
# Given an item, build output line for Task or Scene
# ################################################################################
def format_task_or_scene(list_type: list, the_item: str) -> tuple:
    """
    Given an item, build output line for Task or Scene
    Args:

        list_type (list): Either "Task:" or "Scene:"
        the_item (str): text for Task or Scene

    Returns:
        tuple[str, str]: Our formatted output line and color to user
    """
    # Format the Task/Scene name as needed: spacing and HTML
    the_item_altered = adjust_name(list_type, the_item) if list_type in {"Task:", "Scene:"} else the_item

    # If Scene Task, add 'ID:' to the Task number and reformat the string.
    if "&#45;&#45;Task:" in list_type:
        the_item_altered = f"ID:{the_item_altered}"
        list_type = list_type.replace("&#45;&#45;Task: ", "&#45;&#45;Task: '").replace(
            "&nbsp;&nbsp;",
            "'&nbsp;&nbsp;",
        )

    # Format the output line
    output_line = f"{list_type}&nbsp;{the_item_altered}"

    # Set up the correct color for twisty of needed
    color_to_use = "scene_color" if list_type == "Scene:" else "task_color"

    return output_line, color_to_use


# ################################################################################
# If doing a directory, format and add it.  If doing twisties, add a twisty.
# ################################################################################
def add_dictionary_and_twisty(
    list_type: str,
    the_item: str,
    the_task: defusedxml,
    output_line: str,
    color_to_use: str,
) -> tuple[str, str]:
    """
    If doing a directory, format and add it. If not doing directory and we have a Task, add a link.
    If doing twisties, add a twisty.

    Args:
        list_type (str): Either "Task:" or "Scene:"
        the_item (str): Task ID for Task or Scene
        the_task (defusedxml): XML pointer to the Task being processed
        output_line (str): The text string containing the output
        color_to_use (str): The color to use in the output

    Returns:
        tuple[str, str]: Temporary item and temporary list item
    """
    temp_item, temp_list = "", ""
    blank = "&nbsp;"

    if "&#45;&#45;Task:" in list_type:
        temp_item, temp_list = handle_task(list_type, the_item, blank)
    elif PrimeItems.program_arguments["directory"]:
        handle_directory(list_type, the_item, the_task)
    elif "Task:" in list_type:
        handle_task_hyperlink(the_item, blank)

    if should_add_directory_hyperlink(list_type):
        add_directory_hyperlink()

    if list_type == "Scene:":
        PrimeItems.output_lines.add_line_to_output(0, "", FormatLine.dont_format_line)

    if PrimeItems.program_arguments["twisty"] and "Task:" in list_type:
        handle_twisty(color_to_use, output_line)

    return temp_item, temp_list


def handle_task(list_type: str, the_item: str, blank: str) -> tuple[str, str]:
    """
    Handle the task by adding a task hyperlink and debugging the task ID.

    Args:
        list_type (str): The type of the list.
        the_item (str): The text item to process.
        blank (str): A blank string for formatting.

    Returns:
        tuple[str, str]: The processed item and list type.
    """
    task_name = PrimeItems.tasker_root_elements["all_tasks"][the_item]["name"]
    add_task_hyperlink(task_name, True, blank)
    temp_item, temp_list = the_item, list_type
    list_type = debug_task_id(list_type)
    return temp_item, temp_list


def handle_directory(list_type: str, the_item: str, the_task: defusedxml) -> None:
    """
    Handle the directory by processing tasks or adding scene directories.

    Args:
        list_type (str): The type of the list.
        the_item (str): The text item to process.
        the_task (defusedxml): The task XML element.

    Returns:
        None
    """
    if "Task:" in list_type:
        process_task_directory(the_task)
    elif list_type == "Scene:":
        add_scene_directory(the_item)


def handle_task_hyperlink(the_item: str, blank: str) -> None:
    """
    Handle the task hyperlink by adding a hyperlink to the task name.

    Args:
        the_item (str): The text item to process.
        blank (str): A blank string for formatting.

    Returns:
        None
    """
    task_name = the_item.split("&nbsp;")[0]
    add_task_hyperlink(task_name, False, blank)


def should_add_directory_hyperlink(list_type: str) -> bool:
    """
    Determine if a directory hyperlink should be added.

    Args:
        list_type (str): The type of the list.

    Returns:
        bool: True if a directory hyperlink should be added, False otherwise.
    """
    return (
        PrimeItems.program_arguments["directory"]
        and PrimeItems.directory_items["current_item"]
        and "Task:" in list_type
        and "&#45;&#45;Task:" not in list_type
    )


def add_task_hyperlink(task_name: str, display_name: bool, blank: str) -> None:
    """
    Add a hyperlink to the task name.

    Args:
        task_name (str): The name of the task.
        display_name (bool): Whether to display the task name.
        blank (str): A blank string for formatting.

    Returns:
        None
    """
    hyperlink_name = task_name.replace(" ", "_")
    name = f"{blank * 8}{task_name}" if display_name else ""
    PrimeItems.output_lines.add_line_to_output(
        2,
        f'<a id="tasks_{hyperlink_name}"><br>{name}</a>',
        FormatLine.dont_format_line,
    )


def process_task_directory(the_task: defusedxml) -> None:
    """
    Process the task directory by adding the task name to the directory items.

    Args:
        the_task (defusedxml): The task XML element.

    Returns:
        None
    """
    task_id = the_task.attrib.get("sr", "")[4:]
    task_name = PrimeItems.tasker_root_elements["all_tasks"].get(task_id, {}).get("name", "")
    if task_name:
        add_directory_item("tasks", task_name)


def add_scene_directory(the_item: str) -> None:
    """
    Add a scene directory item.

    Args:
        the_item (str): The scene item to add to the directory.
    """
    add_directory_item("scenes", the_item)


def add_directory_hyperlink() -> None:
    """
    Add a hyperlink to the current directory item.

    Returns:
        None
    """
    directory_item = f"{PrimeItems.directory_items['current_item']}"
    directory = f'<a id="{directory_item}"</a>\n'
    PrimeItems.output_lines.add_line_to_output(
        5,
        directory,
        FormatLine.dont_format_line,
    )


def handle_twisty(color_to_use: str, output_line: str) -> None:
    """
    Handle the twisty by adding a twisty to the output line.

    Args:
        color_to_use (str): The color to use for the twisty.
        output_line (str): The output line to add the twisty to.

    Returns:
        None
    """
    add_twisty(color_to_use, output_line)


def debug_task_id(list_type: str) -> str:
    """
    Debug the task ID by appending the ID location to the list type if in debug mode.

    Args:
        list_type (str): The type of the list.

    Returns:
        str: The modified list type with the ID location appended if in debug mode.
    """
    if PrimeItems.program_arguments["debug"]:
        id_loc = list_type.find("ID:")
        if id_loc != -1:
            return f"{list_type}{id_loc}"
    return list_type


# ################################################################################
# Given an item, format it with all of the particulars and add to output.
# ################################################################################
def format_item(
    list_type: str,
    the_item: str,
    the_list: list,
    the_task: defusedxml,
) -> None:
    """
    Given an item, format it with all of the particulars:
        Proper html/color/font, twisty, directory, properties, etc.
        Args:
            list_type (str): Either "Task:" or "Scene:"
            the_item (str): The string for the above type
            the_list (list): List of Tasks or Scenes
            the_task (defusedxml): The Task XML element
    """
    # Log if in debug mode
    if PrimeItems.program_arguments["debug"]:
        logger.debug(
            f"process_list  the_item:{the_item} the_list:{the_list} list_type:\
            {list_type}",
        )

    # Format the Task or Scene
    output_line, color_to_use = format_task_or_scene(list_type, the_item)

    # If "--Task:" then this is a Task under a Scene.
    # Need to temporarily save the_item since add_line_to_output changes the_item
    temp_item, temp_list = add_dictionary_and_twisty(
        list_type,
        the_item,
        the_task,
        output_line,
        color_to_use,
    )

    # Add this Task/Scene to the output as a list item
    PrimeItems.output_lines.add_line_to_output(
        2,
        output_line,
        FormatLine.dont_format_line,
    )

    # Put the_item back with the 'ID: nnn' portion included.
    if temp_item:
        the_item = temp_item
        list_type = temp_list

    # Process Task Properties if this is a Task, display level is 3 and
    # we are not at the end dispaying Tasks that are not in any Profile
    if (
        the_task is not None
        and "Task:" in list_type
        and PrimeItems.program_arguments["display_detail_level"] > 2
        and not PrimeItems.displaying_named_tasks_not_in_profile
    ):
        get_properties("Task:", the_task)


# Process Given a Task/Scene, process it.
def process_item(
    the_item: str,
    list_type: str,
    the_task: defusedxml.ElementTree,
    tasks_found: list,
) -> None:
    """
    Process the item and add it to the output.

    Args:
        the_item (str): The text item to process.
        list_type (str): The type of the list.
        the_task (xml element): The task to process.
        tasks_found (list): The list of tasks found.

    Returns:
        None
    """
    # This import must stay here to avoid error
    from maptasker.src.scenes import process_scene

    # Given an item, format it with all of the particulars and add to output.
    format_item(list_type, the_item, the_item, the_task)

    # If just displaying basic details, get out.
    if PrimeItems.program_arguments["display_detail_level"] == 0:
        return

    # Output Actions for this Task...
    # If the Task is unnamed and we are listing unnamed tasks or...
    # the Task is not unnamed.
    task_in_list_type = "Task:" in list_type
    if task_in_list_type:
        # We have a Task, so get its Actions
        get_task_actions_and_output(
            the_task,
            list_type,
            the_item,
            tasks_found,
        )

        # End the twisty hidden lines if not a Task in a Scene
        if PrimeItems.program_arguments["twisty"]:
            remove_twisty()

    elif list_type == "Scene:" and PrimeItems.program_arguments["display_detail_level"] > 1:
        # We have a Scene: process its details
        process_scene(
            the_item,
            tasks_found,
            None,
            0,
        )

    # Remove twisty if not displaying level 0
    elif PrimeItems.program_arguments["twisty"]:
        if PrimeItems.program_arguments["display_detail_level"] > 0:
            remove_twisty()
        else:
            # End list if doing twisty and displaying level 0
            PrimeItems.output_lines.add_line_to_output(
                3,
                "",
                FormatLine.dont_add_end_span,
            )

    return


# Process Task/Scene text/line item: call recursively for Tasks within Scenes
def process_list(
    list_type: str,
    the_list: list,
    the_task: defusedxml.ElementTree,
    tasks_found: list,
) -> None:
    """
    Process Task/Scene text/line item: call recursively for Tasks within Scenes

        :param list_type: Task or Scene
        :param the_list: list of Task names tro process
        :param the_task: Task/Scene xml element
        :param tasks_found: list of Tasks found so far
        :return:
    """

    # Go through all Tasks/Scenes in the list
    # The list looks like...
    # 'Battery Full Alert&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task&nbsp;&nbsp;Task ID: 18 &nbsp;&nbsp;[Priority: 6]&nbsp;&nbsp;')
    for the_item in the_list:
        # Process the item (list of items)
        process_item(the_item, list_type, the_task, tasks_found)
