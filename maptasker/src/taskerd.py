"""Read in XML"""

#! /usr/bin/env python3

#                                                                                      #
# taskerd: get Tasker data from backup xml                                             #
#                                                                                      #
import defusedxml.ElementTree as ET  # noqa: N817

from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine, logger
from maptasker.src.xmldata import rewrite_xml


# Convert list of xml to dictionary
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
        try:
            name = item.find(name_qualifier).text
        except AttributeError:
            name = ""
        # Get the Profile/Task identifier: id=number for Profiles and Tasks,
        item_id = item.find("id").text if get_id else name
        new_table[item_id] = {"xml": item, "name": name}

    all_xml.clear()  # Ok, we're done with the list
    return new_table


# Load all of the Projects, Profiles and Tasks into a format we can easily
# navigate through.
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
    process_file = True
    counter = 0
    error_message = ""

    while process_file:
        # Import xml...
        # Define the XML parser with ISO encoding since that is what Joao outputs his XML with.
        # # If we still get an encoding error then rewrite the XML with proper ISO encoding and try again.
        file_to_parse = PrimeItems.file_to_get.name
        try:
            xmlp = ET.XMLParser(encoding="utf-8")
            PrimeItems.xml_tree = ET.parse(file_to_parse, parser=xmlp)
            process_file = False  # Get out of while/loop
        except ET.ParseError:  # Parsing error
            PrimeItems.xml_tree = None
            error_message = f"Improperly formatted XML in {file_to_parse}"
            error_handler(error_message, 1)  # Error out and exit
            process_file = False  # Get out of while/loop
        except UnicodeDecodeError:  # Unicode error
            PrimeItems.file_to_get.close()
            counter += 1
            if counter > 2:
                error_message = f"Unicode error in {file_to_parse}"
                error_handler(error_message, 1)  # Error out and exit
                break  # Get out of while/loop
            rewrite_xml(file_to_parse)  # Rewrite with proper encoding
            process_file = True
        except Exception as e:  # any other error  # noqa: BLE001
            error_message = f"Parsing error {e} in taskerd {file_to_parse}"
            error_handler(error_message, 1)
            process_file = False  # Get out of while/loop

    # If bad XML, just return.
    if PrimeItems.xml_tree is None and not PrimeItems.program_arguments["gui"]:
        return 1

    # Return to GUI if came from there.
    if PrimeItems.xml_tree is None and PrimeItems.program_arguments["gui"]:
        logger.debug(f"taskerd bad xml: {error_message}")
        PrimeItems.error_msg = error_message
        return 1

    # Get the xml root
    PrimeItems.xml_root = PrimeItems.xml_tree.getroot()

    # Check for valid Tasker backup.xml file
    if PrimeItems.xml_root.tag != "TaskerData":
        error_message = "You did not select a Tasker backup XML file...exit 2"
        PrimeItems.output_lines.add_line_to_output(0, error_message, FormatLine.dont_format_line)
        logger.debug(f"{error_message} exit 3")
        if PrimeItems.program_arguments["gui"]:
            PrimeItems.error_msg = error_message
        return 3

    all_services = PrimeItems.xml_root.findall("Setting")
    all_projects_list = PrimeItems.xml_root.findall("Project")
    all_profiles_list = PrimeItems.xml_root.findall("Profile")
    all_scenes_list = PrimeItems.xml_root.findall("Scene")
    all_tasks_list = PrimeItems.xml_root.findall("Task")

    # We now have what we need as lists.  Now move all into dictionaries.
    all_projects = move_xml_to_table(all_projects_list, False, "name")
    all_profiles = move_xml_to_table(all_profiles_list, True, "nme")
    all_tasks = move_xml_to_table(all_tasks_list, True, "nme")
    all_scenes = move_xml_to_table(all_scenes_list, False, "nme")

    # Return all data in a dictionary for easier access
    PrimeItems.tasker_root_elements = {
        "all_projects": all_projects,
        "all_profiles": all_profiles,
        "all_scenes": all_scenes,
        "all_tasks": all_tasks,
        "all_services": all_services,
    }
    return 0
