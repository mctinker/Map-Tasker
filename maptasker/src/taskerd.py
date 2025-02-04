"""Read in XML"""

#! /usr/bin/env python3

#                                                                                      #
# taskerd: get Tasker data from backup xml                                             #
#                                                                                      #
import defusedxml.ElementTree as ET  # noqa: N817

from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, FormatLine
from maptasker.src.xmldata import rewrite_xml


# Convert list of xml to dictionary
# Optimized
def move_xml_to_table(all_xml: list, get_id: bool, name_qualifier: str) -> dict:
    """
    Given a list of Profile/Task/Scene elements, find each name and store the element and name in a dictionary.
        :param all_xml: the head xml element for Profile/Task/Scene
        :param get_id: True if we are to get the <id>
        :param ame_qualifier: the qualifier to find the element's name.
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
        "all_projects": move_xml_to_table(PrimeItems.xml_root.findall("Project"), False, "name"),
        "all_profiles": move_xml_to_table(PrimeItems.xml_root.findall("Profile"), True, "nme"),
        "all_tasks": move_xml_to_table(PrimeItems.xml_root.findall("Task"), True, "nme"),
        "all_scenes": move_xml_to_table(PrimeItems.xml_root.findall("Scene"), False, "nme"),
        "all_services": PrimeItems.xml_root.findall("Setting"),
    }
    # Get Tasks by name and handle Tasks with no name.
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = {}
    for key, value in PrimeItems.tasker_root_elements["all_tasks"].items():
        if not value["name"]:
            # Assign unknown task name if none
            value["name"] = f"{UNKNOWN_TASK_NAME}{key!s}"
        PrimeItems.tasker_root_elements["all_tasks_by_name"][value["name"]] = {"xml": value["xml"], "id": key}

    return 0


def _handle_gui_error(message: str, code: int = 1) -> int:
    PrimeItems.output_lines.add_line_to_output(0, message, FormatLine.dont_format_line)
    if PrimeItems.program_arguments["gui"]:
        PrimeItems.error_msg = message
    return code
