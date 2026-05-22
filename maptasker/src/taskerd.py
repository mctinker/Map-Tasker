"""Read in XML"""

#! /usr/bin/env python3

#                                                                                      #
# taskerd: get Tasker data from backup xml                                             #
#                                                                                      #
import re

import pygixml

from maptasker.src import condition
from maptasker.src.action import get_conditions
from maptasker.src.actione import get_action_code
from maptasker.src.error import error_handler
from maptasker.src.maputil2 import strip_html_tags, truncate_string
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
        name_temp = item.child(name_qualifier).text()
        name = name_temp.strip() if name_temp is not None and name_temp else ""

        # Get the Profile/Task identifier: id=number for Profiles and Tasks,
        id_element = item.child("id").text()
        item_id = id_element if get_id and id_element is not None else name

        new_table[item_id] = {"xml": item, "name": name}

    all_xml.clear()  # Ok, we're done with the list
    return new_table


def get_the_xml_data() -> int:
    """Gets the XML data from a Tasker backup file and returns it in a dictionary.
    Returns:
        - int: 0 if successful, 1 if bad XML, 2 if not a Tasker backup file, 3 if not a valid Tasker backup file.
    """
    file_to_parse = PrimeItems.file_to_get.name
    counter = 0
    anchor = "Anchor ...with label:\n"

    _rewrite_xml = rewrite_xml

    # Validate the XML file using pygixml
    while True:
        try:
            # pygixml automatically handles encoding; if it fails, it returns an empty doc
            PrimeItems.xml_tree = pygixml.parse_file(file_to_parse)

            # Check if parsing actually succeeded
            if not PrimeItems.xml_tree:
                error_handler(f"Error in {file_to_parse}: unable to parse the date.", 1)
                return 1
            break

        except pygixml.PygiXMLError:
            counter += 1
            # If error, rewrite the file with correct encoding (UTF-8) and try again.
            if counter > 2:
                error_handler(f"Error in {file_to_parse}: failed to parse the XML file.", 1)
                return 1
            _rewrite_xml(file_to_parse)

    # In pygixml, we get the root node directly from the document object
    PrimeItems.xml_root = PrimeItems.xml_tree.root.xml

    # Check for valid Tasker backup file .
    if PrimeItems.xml_tree.root.name != "TaskerData":
        return _handle_gui_error("Invalid Tasker backup XML file", code=3)

    # Extract and transform data
    _move_xml_to_table = move_xml_to_table

    # pygixml.select_nodes returns a list of xpath_node objects;
    # we pass the node itself to move_xml_to_table
    PrimeItems.tasker_root_elements = {
        "all_projects": _move_xml_to_table(
            [res.node for res in PrimeItems.xml_tree.root.select_nodes("Project")],
            False,
            "name",
        ),
        "all_profiles": _move_xml_to_table(
            [res.node for res in PrimeItems.xml_tree.root.select_nodes("Profile")],
            True,
            "nme",
        ),
        "all_tasks": _move_xml_to_table(
            [res.node for res in PrimeItems.xml_tree.root.select_nodes("Task")],
            True,
            "nme",
        ),
        "all_scenes": _move_xml_to_table(
            [res.node for res in PrimeItems.xml_tree.root.select_nodes("Scene")],
            False,
            "nme",
        ),
        "all_services": [res.node for res in PrimeItems.xml_tree.root.select_nodes("Setting")],
    }

    # Assign names to Profiles that have no name
    all_profiles = PrimeItems.tasker_root_elements["all_profiles"]
    _parse_condition = condition.parse_profile_condition
    _conditions_to_name = conditions_to_name
    unnamed_label = UNNAMED_ITEM
    tag_cleaner = re.compile(r"</?em>")

    for profile in all_profiles.values():
        if not profile.get("name"):
            xml_content = profile["xml"]
            conditions = _parse_condition(xml_content)
            current_name = unnamed_label

            if conditions:
                _, current_name, _ = _conditions_to_name(xml_content, conditions, unnamed_label, "")

            if "<em>" in current_name:
                current_name = tag_cleaner.sub("", current_name)

            profile["name"] = current_name

    # Get Tasks by name and handle unnamed Tasks
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = {}
    _get_first_action = get_first_action
    for key, value in PrimeItems.tasker_root_elements["all_tasks"].items():
        if not value["name"]:
            first_action = _get_first_action(value["xml"])
            if anchor in first_action:
                first_action = 'Anchor "' + first_action.split(anchor, 1)[1]

            value["name"] = f"{first_action.rstrip()}.{key!s} ({unnamed_label})"

        PrimeItems.tasker_root_elements["all_tasks_by_name"][value["name"]] = {
            "xml": value["xml"],
            "id": key,
        }

    # Sort results
    PrimeItems.tasker_root_elements["all_tasks"] = dict(sorted(PrimeItems.tasker_root_elements["all_tasks"].items()))
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = dict(
        sorted(PrimeItems.tasker_root_elements["all_tasks_by_name"].items()),
    )

    return 0


def _handle_gui_error(message: str, code: int = 1) -> int:
    PrimeItems.output_lines.add_line_to_output(0, message, FormatLine.dont_format_line)
    if PrimeItems.program_arguments["gui"]:
        PrimeItems.error_msg = message
    return code


def get_first_action(task: pygixml.XPathNode) -> str:
    """
    Retrieve the name of the first action code from a Tasker task XML element.

    Args:
        task (pygixml.XPathNode): The XML element representing a Tasker task.

    Returns:
        str: The name of the first action's code if found, otherwise an empty string.

    Processing Logic:
        - Finds all "Action" elements within the task.
        - Searches for the first action with attribute sr="act0".
        - If found, retrieves the "code" child element of that action.
        - Looks up the action code in the action_codes dictionary and returns its name.
        - Returns an empty string if no suitable action is found.
    """
    # Build the Tasker argument codes dictionary if we don't yet have it.
    if not PrimeItems.tasker_arg_specs:
        from maptasker.src.proginit import build_action_codes_from_json  # noqa: PLC0415

        build_action_codes_from_json(False)

    # Get all of the Action statements.
    first_action = task.child("Action")
    if first_action is not None:
        # Parse the incoming string buffer into an internal memory XML document layout
        doc = pygixml.parse_string(first_action.xml)

        # Get the root element node of our document tree (the <Task> tag context)
        root_node = doc.root
        # Query the node tree utilizing full XPath 1.0 syntax.
        # '//Str[@sr="arg0"]' scans globally for any <Str> element where the 'sr' attribute is exactly "arg0"
        arg0_path = root_node.select_node('//Str[@sr="arg0"]')
        arg0_node = arg0_path.node if arg0_path else None

        # If we don't have an arg0, then get any conditions on the Action and return those instead.
        if arg0_node is None or arg0_node.value is None:  # If no arg0 (i.e. State/Event/etc.)
            # Look for any conditions:  <ConditionList sr="if">
            cond_list = first_action.child("ConditionList")
            if cond_list is not None:  # If condition on Action?
                code_node = first_action.child("code")
                task_conditions = get_conditions(first_action, code_node.value)
                if task_conditions:
                    tc = task_conditions.replace("<em>", "").replace("</em>", "").replace("(", "").replace(")", "")
                    arg0_value = tc.strip()
                    get_arg0 = False
                else:
                    return ""
        else:
            get_arg0 = True

        if get_arg0:
            arg0_value = arg0_node.text()
            if arg0_value is None or arg0_value.strip() == "":
                return ""

        # Now get the Action code
        code_node = first_action.child("code")
        the_result = get_action_code(code_node, arg0_node, True, "t") if get_arg0 else arg0_value
        clean_text = strip_html_tags(the_result)
        clean_text = (
            clean_text
            .replace("&nbsp;&nbsp;", "&nbsp;")
            .replace("( ", "(")
            .replace("(", "")
            .replace(")", "")
            .replace("&nbsp;", " ")
            .replace("...with label: ", "")
            .replace("&lt;", "{")
            .replace("&gt;", "}")
        )
        # Truncate the string at 30 charatcers.
        return truncate_string(clean_text, 30)
    return ""
