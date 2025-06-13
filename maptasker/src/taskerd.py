"""Read in XML"""

#! /usr/bin/env python3

#                                                                                      #
# taskerd: get Tasker data from backup xml                                             #
#                                                                                      #

import defusedxml.ElementTree as ET  # noqa: N817

from maptasker.src import condition
from maptasker.src.actione import get_action_code
from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.profiles import conditions_to_name
from maptasker.src.sysconst import UNNAMED_ITEM, FormatLine
from maptasker.src.xmldata import rewrite_xml


# Convert list of xml to dictionary
# Optimized
def move_xml_to_table(all_xml: list, get_id: bool, name_qualifier: str) -> dict:
    """
    Given a list of Profile/Task/Scene elements, find each name and store the element and name in a dictionary.
        :param all_xml: the head xml element for Profile/Task/Scene
        :param get_id: True if we are to get the <id>
        :param name_qualifier: the qualifier to find the element's name.
        :return: dictionary that we created
    """
    new_table = {}
    for item in all_xml:
        # Get the element name
        name_element = item.find(name_qualifier)
        name = name_element.text.strip() if name_element is not None and name_element.text else ""

        # Get the Profile/Task identifier: id=number for Profiles and Tasks,
        id_element = item.find("id")
        item_id = id_element.text if get_id and id_element is not None else name

        new_table[item_id] = {"xml": item, "name": name}

    all_xml.clear()  # Ok, we're done with the list
    return new_table


# Load all of the Projects, Profiles and Tasks into a format we can easily
# navigate through.
# Optimized
def get_the_xml_data() -> bool:
    # Put this code into a while loop in the event we have to re-call it again.
    """Gets the XML data from a Tasker backup file and returns it in a dictionary.
    Parameters:
        - None
    Returns:
        - int: 0 if successful, 1 if bad XML, 2 if not a Tasker backup file, 3 if not a valid Tasker backup file.
    Processing Logic:
        - Put code into a while loop in case it needs to be re-called.
        - Defines XML parser with ISO encoding.
        - If encoding error, rewrites XML with proper encoding and tries again.
        - If any other error, logs and exits.
        - Returns 1 if bad XML and not in GUI mode.
        - Returns 1 if bad XML and in GUI mode.
        - Gets XML root.
        - Checks for valid Tasker backup file.
        - Moves all data into dictionaries.
        - Returns all data in a dictionary."""
    file_to_parse = PrimeItems.file_to_get.name
    counter = 0

    while True:
        try:
            xmlp = ET.XMLParser(encoding="utf-8")
            PrimeItems.xml_tree = ET.parse(file_to_parse, parser=xmlp)
            break
        except (ET.ParseError, UnicodeDecodeError) as e:
            counter += 1
            if counter > 2 or isinstance(e, ET.ParseError):
                error_handler(f"Error in {file_to_parse}: {e}", 1)
                return 1
            rewrite_xml(file_to_parse)

    if PrimeItems.xml_tree is None:
        return 1 if not PrimeItems.program_arguments["gui"] else _handle_gui_error("Bad XML file")

    PrimeItems.xml_root = PrimeItems.xml_tree.getroot()
    if PrimeItems.xml_root.tag != "TaskerData":
        return _handle_gui_error("Invalid Tasker backup XML file", code=3)

    # Extract and transform data
    PrimeItems.tasker_root_elements = {
        "all_projects": move_xml_to_table(
            PrimeItems.xml_root.findall("Project"),
            False,
            "name",
        ),
        "all_profiles": move_xml_to_table(
            PrimeItems.xml_root.findall("Profile"),
            True,
            "nme",
        ),
        "all_tasks": move_xml_to_table(
            PrimeItems.xml_root.findall("Task"),
            True,
            "nme",
        ),
        "all_scenes": move_xml_to_table(
            PrimeItems.xml_root.findall("Scene"),
            False,
            "nme",
        ),
        "all_services": PrimeItems.xml_root.findall("Setting"),
    }

    # Assign names to Profiles that have no name = their condition.nnn (Unnamed)
    for key, value in PrimeItems.tasker_root_elements["all_profiles"].items():
        if not value["name"]:
            # The Profile doen't have a name.  Name it using it's conditions.
            profile_name = UNNAMED_ITEM
            profile_xml = value["xml"]
            if profile_conditions := condition.parse_profile_condition(profile_xml):
                # fmt: off
                _, profile_name, profile_conditions = conditions_to_name(
                        profile_xml,
                        profile_conditions,
                        profile_name,
                        "",
                )
            # fmt: on

            # CLean up the new name
            profile_name = profile_name.replace("<em>", "").replace("</em>", "")

            PrimeItems.tasker_root_elements["all_profiles"][key]["name"] = profile_name

    # Get Tasks by name and handle Tasks with no name.
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = {}
    for key, value in PrimeItems.tasker_root_elements["all_tasks"].items():
        if not value["name"]:
            # Get the first Task Action and user it as the Task name.
            first_action = get_first_action(value["xml"])

            # Put the new name back into PrimeItems.tasker_root_elements["all_tasks"]
            value["name"] = f"{first_action.rstrip()}.{key!s} (Unnamed)"

        PrimeItems.tasker_root_elements["all_tasks_by_name"][value["name"]] = {
            "xml": value["xml"],
            "id": key,
        }

    # Sort them for easier debug.
    temp = sorted(PrimeItems.tasker_root_elements["all_tasks"].items())
    PrimeItems.tasker_root_elements["all_tasks"] = dict(temp)
    temp = sorted(PrimeItems.tasker_root_elements["all_tasks_by_name"].items())
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = dict(temp)
    return 0


def _handle_gui_error(message: str, code: int = 1) -> int:
    PrimeItems.output_lines.add_line_to_output(0, message, FormatLine.dont_format_line)
    if PrimeItems.program_arguments["gui"]:
        PrimeItems.error_msg = message
    return code


def get_first_action(task: ET) -> str:
    """
    Retrieve the name of the first action code from a Tasker task XML element.

    Args:
        task (ET.ElementTree): The XML element representing a Tasker task.

    Returns:
        str: The name of the first action's code if found, otherwise an empty string.

    Processing Logic:
        - Finds all "Action" elements within the task.
        - Searches for the first action with attribute sr="act0".
        - If found, retrieves the "code" child element of that action.
        - Looks up the action code in the action_codes dictionary and returns its name.
        - Returns an empty string if no suitable action is found.
    """
    # Build the Taskere argument codes dictionary if we don't yet have it.
    if not PrimeItems.tasker_arg_specs:
        from maptasker.src.proginit import build_action_codes

        build_action_codes(False)

    task_actions = task.findall("Action")
    if task_actions is not None:
        have_first_action = False
        # Go through Actions looking for the first one ("act0")
        for action in task_actions:
            action_number = action.attrib.get("sr")
            if action_number == "act0":
                have_first_action = True
                break

        if not have_first_action:
            return ""

        # Now get the Action code
        child = action.find("code")
        the_result = get_action_code(child, action, True, "t")
        from maptasker.src.maputils import remove_html_tags

        clean_text = remove_html_tags(the_result)
        clean_text = (
            clean_text.replace("&nbsp;&nbsp;", "&nbsp;")
            .replace("( ", "(")
            .replace("(", "")
            .replace(")", "")
            .replace("&nbsp;", " ")
            .replace("...with label: ", "")
            .replace("&lt;", "{")
            .replace("&gt;", "}")
        )
        # Truncate the string at 30 charatcers.
        from maptasker.src.maputils import truncate_string

        return truncate_string(clean_text, 30)
    return ""
