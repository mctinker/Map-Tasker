"""ProcessProject's scenes"""

#! /usr/bin/env python3

#                                                                                      #
# scenes: Process the Tasker Scene passed as input                                     #
#                                                                                      #
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from maptasker.src import tasks
from maptasker.src.actionc import action_codes
from maptasker.src.actione import action_results
from maptasker.src.dirout import add_directory_item
from maptasker.src.primitem import PrimeItems
from maptasker.src.proclist import process_list
from maptasker.src.sysconst import (
    SCENE_TASK_TYPES,
    TASK_NAME_MAX_LENGTH,
    UNNAMED_ITEM,
    FormatLine,
)
from maptasker.src.tasks import get_actions
from maptasker.src.xmldata import tag_in_type

if TYPE_CHECKING:
    import defusedxml.ElementTree

SCENE_TAGS_TO_IGNORE = [
    "cdate",
    "edate",
    "flags",
    "heightLand",
    "nme",
    "widthLand",
]
blank = "&nbsp;"


# Get the Scene's geometry
def get_geometry(scene_element: defusedxml.ElementTree) -> tuple[str, str]:
    """
    Get the Scene's geometry
        :param scene_element: xml element of the Scene <Scene sr="scene...
        :return: width and height
    """
    height = width = "none"
    height = scene_element.find("heightPort")
    if height is not None:
        height = height.text
    width = scene_element.find("widthPort")
    if width is not None:
        width = width.text
    return width, height


# Get the Scene's elements
def get_scene_elements(
    child: defusedxml.ElementTree,
    indentation: int,
) -> None:
    """Get_scene_elements function processes an XML element and its sub-elements to retrieve their names, geometry, and layout information if applicable.
    Parameters:
        - child (defusedxml.ElementTree): The XML element to be processed.
        - indentation (int): The number of spaces to indent the output lines.
    Returns:
        - None: This function does not return any value.
    Processing Logic:
        - Split the element's tag to get its type.
        - Find the element's name and geometry.
        - Add the element's information to the output lines.
        - Check if the element has a sub-scene and process it if so."""
    element_type = child.tag.split("Element")
    # First string is the name of the element
    name_xml_element = child.find("Str")
    # Get the element's geometry
    geom = child.find("geom")
    if geom is not None:
        geometry_xml_element = child.find("geom").text
        geometry = geometry_xml_element.split(",")
        geometry_text = f" ...with geometry {geometry[0]}x{geometry[1]} {geometry[2]}x{geometry[3]}"
    else:
        geometry_text = ""

    # Get the element name
    element_name = "" if element_type[0] == "Properties" else f"'{name_xml_element.text}' "

    PrimeItems.output_lines.add_line_to_output(
        0,
        (f"{blank * (3 + indentation)}{element_name}Element of type {element_type[0]}{geometry_text}"),
        ["", "scene_color", FormatLine.add_end_span],
    )


# Handle sub-lements of the element we are doing.
def process_sub_elements(child: defusedxml.ElementTree, indentation: int) -> None:
    """
    Process the sub-elements of the given child ElementTree.

    Args:
        child (defusedxml.ElementTree): The child ElementTree to process.
        indentation (int): The indentation level to use for output.

    Returns:
        None

    This function iterates over each subchild of the given child ElementTree. If the subchild is an xxxElement,
    it recursively calls the `process_arguments` function with the subchild, its tag, and an increased indentation
    level. If the subchild's tag is "LinkClickFilter", it checks for the presence of "stopEvent" and "urlMatch"
    elements within the subchild. If either element is found, it constructs a line of output with the corresponding
    values. The constructed line is then added to the output lines using the `add_line_to_output` method of the
    `PrimeItems.output_lines` object, with a level of 2, indentation of 12 spaces, and a color of "scene_color".
    """
    original_indentation = indentation
    for subchild in child:
        indentation = original_indentation
        # If it is an xxxElement, then process it by recursing.
        if tag_in_type(subchild.tag, True):
            process_arguments(subchild, subchild.tag, indentation + 5)
        # Handle Properties KEY Tab
        elif subchild.tag == "LinkClickFilter":
            line_out = ""
            stopbottom_event_element = subchild.find("stopEvent")
            if stopbottom_event_element is not None:
                line_out = f"Stop Event={stopbottom_event_element.text},"
            url_match_element = subchild.find("urlMatch")
            if url_match_element is not None:
                line_out = f"{line_out} URL Match={url_match_element.text}"
            if line_out:
                PrimeItems.output_lines.add_line_to_output(
                    2,
                    f"<br>{blank * 12}KEY Tab {line_out}<br>",
                    ["", "scene_color", FormatLine.add_end_span],
                )
    return  # noqa: PLR1711


# Process the Properties ListElementItem element.
def process_list_element(
    child: defusedxml.ElementTree,
    indentation: int,
    element_name: str,
) -> None:
    """
    Process the list element associated with the given child element.

    Args:
        child (defusedxml.ElementTree): The child element to process.
        indentation (int): The indentation level of the child element.
        element_name (str): The name of the element.

    Returns:
        None: This function does not return anything.

    This function processes the list element associated with the given child element. It first checks if the child element
    has an action associated with it. If it does, it retrieves the label and action line for the element. Then, it fixes
    the indentation level and adds the action and action details to the output lines.
    """
    # Get the task Action associated with this listitem
    action = child.find("Action")
    if action is not None:
        label = child.find("label").text
        action_line = get_actions(child)

        # Now fix our indentation
        subline_indentation = f"{blank * len(element_name)}{blank * (9 + indentation)}"
        PrimeItems.output_lines.add_line_to_output(
            2,
            f"{subline_indentation}Action={label}",
            ["", "scene_color", FormatLine.add_end_span],
        )
        # Output the action details
        PrimeItems.output_lines.add_line_to_output(
            2,
            f"<br>{subline_indentation}{action_line[0]}",
            ["", "scene_color", FormatLine.add_end_span],
        )


# Get the xxxElement arguments, format and output them.  Recurse for more sub-elements.
def format_and_output_arguments(
    child: defusedxml.ElementTree,
    element_type: str,
    indentation: int,
) -> None:
    """
    Formats and outputs the arguments for the given child element, element type, and indentation level.

    Parameters:
        child (Element): The child element to format and output arguments for.
        element_type (str): The type of the element.
        indentation (int): The indentation level.

    Returns:
        None
    """
    # Remove "Element" from the name and set up the indetation spacing.
    element_name = element_type.replace("Element", "")
    line_indentation = f"{blank * len(element_name)}{blank * (18 + indentation)}"

    # Get the internal element name
    internal_name = child.attrib.get("sr")

    # Extract argument and translate it.
    the_result = action_results.get_action_results(
        element_type,
        action_codes,  # from actionc.py
        child,
        True,
    )
    # Sub-element probably doesn't have a name.
    the_result = the_result.replace("&nbsp;&nbsp;,", "&nbsp;&nbsp;(no name),")
    # Add the internal name
    end_of_name = the_result.find(",")
    temp = f"{the_result[: end_of_name + 1]} Internal Name={internal_name},{the_result[end_of_name + 1 :]}"
    the_result = temp

    # Modify UI detail line as needed.
    # Make sure this goes down as a Scene line and not a Task line.add
    line_out = the_result.replace("action_color", "scene_color")
    # Fix 'Maximum Characters" in EditTextElement
    line_out = line_out.replace(
        "Maximum Characters:1000",
        "Maximum Characters:Unlimited",
    )
    # Fix CheckBox 'Maximum Characters" in EditTextElement
    line_out = line_out.replace("Checkbox, Checked0", ", Checked=False")
    # Remove 'Rounded Corners' if no 'Corner Radius'
    if "Corner Radius:0" in line_out:
        line_out = line_out.replace("Rounded Corners:All", "")

    # If we have a list element, then it represents a series of task Actions in the scene Properties.
    if element_type == "ListElementItem":
        title = "ACTIONS Tab "
        element_name = ""
    else:
        title = "UI for  "
        # indentation = 0

    # Make pretty
    if PrimeItems.program_arguments["pretty"]:
        line_out = line_out.replace(", ", f"<br>{line_indentation}")

    # Output the element line details.
    PrimeItems.output_lines.add_line_to_output(
        2,
        f"{blank * (6 + indentation)}{title}{element_name}...{line_out}<br>",
        ["", "scene_color", FormatLine.add_end_span],
    )

    # If the element is a ListElementItem, get it's Task Action (in Properties) and output it.
    if element_type == "ListElementItem":
        process_list_element(child, indentation, element_name)

    # Handle sub-elements
    process_sub_elements(child, indentation)


# Break down the UI aspects and output them based on it's arguments.
def process_arguments(
    child: defusedxml.ElementTree,
    element_type: str,
    indentation: int,
) -> None:
    """
    Process the arguments of a given child element in a scene.

    Args:
        child (defusedxml.ElementTree): The child element to process.
        element_type (str): The type of the child element.
        indentation (int): The indentation level of the child element.

    Returns:
        None: This function does not return anything.

    This function processes the arguments of a given child element in a scene. It checks if the element type has an
    action code definition and if not, it returns early. It also ignores certain elements like PropertiesElement and
    ListElementItems based on the indentation level. Finally, it formats and outputs the arguments of the child element.
    """
    # Only processs the arguments if we have the element type's action code definition.
    try:
        _ = action_codes[element_type]
    except KeyError:
        return

    # Ignore Scene's PropertiesElement and it's ListElementItems if primary element (minimum indentation).
    if (element_type == "PropertiesElement" and indentation == 0) or (
        element_type == "ListElementItem" and indentation == 5
    ):
        return

    # Format and output the xxxElement arguments
    format_and_output_arguments(child, element_type, indentation)


# Go through Scene's XML looking for Tasks (e.g. ClickTask) and output if found
def process_tasks(child: defusedxml.ElementTree, tasks_found: list) -> None:
    """Parameters:
        - child (defusedxml.ElementTree): The element to be processed.
        - tasks_found (list): A list of tasks that have been found.
        - indentation (int): The number of spaces to indent the output.
    Returns:
        - None: This function does not return anything.
    Processing Logic:
        - Look for Tasks associated with element.
        - Go through element sub-items.
        - Check if Task is associated with this Scene's element.
        - Start a list.
        - Process Task if it is not a fake Task.
        - Start a list.
        - Get the name of Task.
        - Reset to task name.
        - Set extra string for output.
        - Set task type string for output.
        - Process the Scene's Task.
        - If we hit the arguments, then break out of loop looking for tasks.add."""

    # xxxElement: Look for Tasks associated with this element
    for sub_child in child:  # Go through Element sub-items
        # Task-Click (<xxxClick>, <xxxTask>, etc.) associated with this
        #  Scene's element?
        if tag_in_type(sub_child.tag, False):  # e.g. clickTask?
            # Start Scene's Task list
            temp_task_list = [sub_child.text]

            # Only process Task if it is not a fake Task.
            if temp_task_list[0][0] != "-":
                # Start a list
                PrimeItems.output_lines.add_line_to_output(
                    1,
                    "",
                    FormatLine.dont_format_line,
                )
                # Get the name of Task
                task_element, task_name = tasks.get_task_name(
                    sub_child.text,
                    tasks_found,
                    temp_task_list,
                    "",
                )

                # reset to task name since get_task_name changes its value
                temp_task_list = [sub_child.text]

                # Add the Scene Task to the directory if unnamed.
                if "(Unnamed)" in task_name:
                    task_name = adjust_name_and_add_to_directory(
                        task_name,
                        temp_task_list[0],
                        TASK_NAME_MAX_LENGTH,
                    )

                # If Task is related to the scene Properties, some of the names change.
                task_title = SCENE_TASK_TYPES[sub_child.tag]  # Pick up title from xxxTask element.
                if child.tag == "PropertiesElement":
                    preamble = "  Properties "
                    if sub_child.tag == "itemselectedTask":
                        task_title = "TAB TAP"
                else:
                    preamble = ""

                # Ok, process the task (e.g. output it).  "&#45;" = hyphen
                extra = f"{blank * 2}{task_name}"
                task_type = f"<br>{blank}{preamble}&#45;&#45;Task: {task_title}{extra}"
                PrimeItems.named_task_count_total += 1

                # process the Scene's Task
                process_list(
                    task_type,
                    temp_task_list,
                    task_element,
                    tasks_found,
                )

        # If we hit the arguments, then break out of loop looking for tasks.add
        elif sub_child.tag in ["Str", "Int"]:
            break

    # Add a break after last Task.
    PrimeItems.output_lines.add_line_to_output(5, "<br>", FormatLine.dont_format_line)


def adjust_name_and_add_to_directory(
    task_name: str,
    task_id: str,
    max_length: int,
) -> str:
    """
    Adjusts the task name to fit within the specified maximum length and adds it to the directory with '(Scene)' appended.

    Args:
        task_name (str): The name of the task.
        task_id (str): The unique identifier for the task.
        max_length (int): The maximum allowed length for the task name.

    Returns:
        str: The adjusted task name.
    """
    # If the name is too long, adjust iot so that '(Scene)' will fit in the directory.
    if len(task_name) > max_length:
        orig_name = task_name

        # Get just the 'name.id'
        task_name = task_name.replace(f" {UNNAMED_ITEM}", "").replace("...", "")
        last_period = task_name.rfind(".")
        if last_period != -1:
            task_name = task_name[:last_period]

        # Now truncate it.
        task_name = f"{task_name[: max_length - 8].rstrip()}.{task_id} (Unnamed)"

        # Update the task name in our master dictionary
        PrimeItems.tasker_root_elements["all_tasks"][task_id]["name"] = task_name
        # Update the name in our 'by name' directory
        for key, value in PrimeItems.tasker_root_elements["all_tasks_by_name"].items():
            # If the task name really hasn't changed (new name = old name), bail out.
            if key == task_name:
                break
            if value["id"] == task_id:
                PrimeItems.tasker_root_elements["all_tasks"][task_id]["name"] = task_name

                # Add the new name / values
                PrimeItems.tasker_root_elements["all_tasks_by_name"][task_name] = {
                    "xml": value["xml"],
                    "id": task_id,
                }

                # Delete the original
                del PrimeItems.tasker_root_elements["all_tasks_by_name"][orig_name]
                # Get out of loop
                break

    # Add the Task to the directory with '(Scene)' appended.
    add_directory_item(
        "tasks",
        f"{task_name} (Scene)",
    )
    return task_name


# Pull out the screen width and height
def get_details(
    scene: defusedxml.ElementTree,
    tasks_found: defusedxml.ElementTree,
    indentation: int = 0,
) -> None:
    """
    Go through Scene to obtain it's height and width and output.

    Args:
        scene (defusedxml.ElementTree): Scene xml element to trundle through.
        tasks_found (defusedxml.ElementTree): List of Tasks found so far.
        indentation (int): Indentation number of blanks to add to output lines.

    Returns:
        Nothing
    """
    element_type = ""
    original_indent = indentation
    for child in scene:
        if child.tag in SCENE_TAGS_TO_IGNORE:
            continue
        indentation = original_indent

        # Is this an xxxElement?
        if tag_in_type(child.tag, True):  # xxxElement (e.g. RectElement)?
            element_type = child.tag
            # Display the Element details
            if PrimeItems.program_arguments["display_detail_level"] > 2:
                get_scene_elements(child, indentation)

            # Are we to display Scene element details?
            if PrimeItems.program_arguments["display_detail_level"] == 5:
                # Get the element type's arguments and process them
                process_arguments(child, element_type, indentation)

            # Check to see if this Scene has a layout Scene, and deal with it if so.
            sub_scenes = child.find("Scene")
            if sub_scenes is not None:
                for sub_scene_element in sub_scenes:
                    width, height = get_geometry(sub_scene_element)
                    PrimeItems.output_lines.add_line_to_output(
                        0,
                        f"{blank * (4 + indentation)}Element has an item 'Layout' (Scene) with width/height {width} X {height}",
                        ["", "scene_color", FormatLine.add_end_span],
                    )

                    # Okay, process this sub-scene
                    process_scene(scene.find("nme").text, [], sub_scene_element, 9)

            # Process any Tasks as part of this Scene
            process_tasks(child, tasks_found)

    # Add a break if end of Scene elements (but not doing a Properties element)
    if PrimeItems.program_arguments["display_detail_level"] != 2 and element_type != "PropertiesElement":
        PrimeItems.output_lines.output_lines.append("<br>")


# Process the Scene's Properties
def process_properties(scene: defusedxml.ElementTree, indentation: int) -> None:
    # Get the PropertiesElement
    """Returns:
        - None: No return value.
    Processing Logic:
        - Get PropertiesElement.
        - Format and output xxxElement arguments.
        - Increment indentation by 1."""
    properties = scene.find("PropertiesElement")
    if properties is not None:
        # Format and output the xxxElement arguments
        format_and_output_arguments(properties, "PropertiesElement", indentation + 5)

        # Process any Tasks as part of this Scene Properties
        # process_tasks(properties, [])


# Process the Scene
def process_scene(
    my_scene: str,
    tasks_found: list[str],
    scene_xml: defusedxml.ElementTree,
    indentation: int,
) -> None:
    """
    Process the Project's Scene(s), one at a time

        :param my_scene: name of Scene to process
        :param tasks_found: list of Tasks found so far
        :param scene_xml: Scene xml element to process for sub-scene, or None if this is a valid Scene being passed in.
        :param indentation: Indentation number of blanks to add to output

        # Get the Scene's geometry and display it
        :return:
    """
    # Get the Scene's XML pointer.  If scene_xml being passed in is None, then use the name passed in to get the XML.
    scene = PrimeItems.tasker_root_elements["all_scenes"][my_scene]["xml"] if scene_xml is None else scene_xml

    # Get the Scene's geometry and display it
    height, width = get_geometry(scene)
    PrimeItems.output_lines.add_line_to_output(
        0,
        f"{blank * (indentation + 2)}Width/Height: {width} X {height}<br>",
        ["", "scene_color", FormatLine.add_end_span],
    )

    # Handle directory hyperlink
    if PrimeItems.program_arguments["directory"]:
        add_directory_item("scenes", my_scene)

    # Go through all the children of the Scene looking for width/height, 'click' tasks and other details.
    get_details(scene, tasks_found, indentation)

    # Process Properties if we are at the head Scene
    if indentation == 0:
        process_properties(scene, indentation)

    # If we are doing twisties, then we need to close the unordered list.
    if PrimeItems.program_arguments["twisty"]:
        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# Go through all Scenes for Project, get their detail and output it
def process_project_scenes(
    project: defusedxml.ElementTree,
    our_task_element: defusedxml.ElementTree,
    found_tasks: list,
) -> bool:
    """
    Go through all Scenes for Project, get their detail and output it
        :param project: xml element of Project we are processing
        :param our_task_element: xml element pointing to our Task
        :param found_tasks: list of Tasks found so far
        :return: True if a Scene was output, False if not
    """
    scene_names = None
    PrimeItems.scene_count = 0
    with contextlib.suppress(Exception):
        scene_names = project.find("scenes").text
    if scene_names is not None:
        scene_list = scene_names.split(",")

        # If we have at least one Scene, process it
        if scene_list[0]:
            PrimeItems.scene_count = len(scene_list)
            process_list(
                "Scene:",
                scene_list,
                our_task_element,
                found_tasks,
            )

            # Force a line break
            PrimeItems.output_lines.add_line_to_output(
                0,
                "",
                FormatLine.dont_format_line,
            )

            if PrimeItems.program_arguments["display_detail_level"] == 0:
                # End list if displaying level 0
                PrimeItems.output_lines.add_line_to_output(
                    3,
                    "",
                    FormatLine.dont_format_line,
                )

    return bool(scene_names)
