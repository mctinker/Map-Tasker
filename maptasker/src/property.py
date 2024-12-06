"""Handle Object Properties"""

#! /usr/bin/env python3

#                                                                                      #
# property: get Project/Profile/Task properties and output them                        #
#                                                                                      #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.actione import fix_json
from maptasker.src.maputils import rutroh_error
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


# Parse Property's variable and output it
def parse_variable(
    property_tag: str,
    css_attribute: str,
    variable_header: defusedxml.ElementTree,
    cooldown: int,
    limit: int,
) -> None:
    """
    Parses the variable header of a property tag and outputs the properties of the variable.
    Properties are identied in the XML with the tag: <xxxxVariable>, where xxxx is Project/Profile/Task

    Args:
        property_tag (str): The property tag of the variable.
        css_attribute (str): The CSS attribute of the variable.
        variable_header (defusedxml.ElementTree): The XML element representing the variable header.
        cooldown (int): The cooldown time in seconds.
        limit (int): Limit repeats.

    Returns:
        None
    """
    # Variable type definitions
    variable_type_lookup = {
        "yn": "Yes or No",
        "t": "Text",
        "b": "True or False",
        "f": "File",
        "n": "Number",
        "onoff": "On or Off",
        "fs": "File (System)",
        "fss": "Files (System)",
        "i": "Image",
        "is": "Images",
        "d": "Directory",
        "ds": "Directory (System)",
        "ws": "WiFi SSID",
        "wm": "WiFi MAC",
        "bn": "Bluetooth device's name",
        "bm": "Bluetooth device's MAC",
        "c": "Contact",
        "cn": "Contact Number",
        "cg": "Contact or Contact Group",
        "ti": "Time",
        "da": "Date",
        "a": "App",
        "as": "Apps",
        "la": "Launcher",
        "cl": "Color",
        "ln": "Language",
        "ttsv": "Text to Speech voice",
        "can": "Calendar",
        "cae": "Calendar Entry",
        "tz": "Time Zone",
        "ta": "Task",
        "prf": "Profile",
        "prj": "Project",
        "scn": "Scene",
        "cac": "User Certificate",
    }
    # Get the various property. TBD: pvid (int), pvit (str), pvt
    clearout = variable_header.find("clearout").text
    immutable = variable_header.find("immutable").text
    configure_on_import = variable_header.find("pvci").text
    prompt = variable_header.find("pvd").text
    value_element = variable_header.find("pvv")
    value = "" if value_element is None else value_element.text
    display_name = variable_header.find("pvdn").text
    structured_variable = variable_header.find("strout").text
    variable_name = variable_header.find("pvn").text
    if variable_header.find("pvn").text == "1":
        exported_value = "Same as Value"
    else:
        exported_value = variable_header.find("exportval").text
    # Get the variable type
    variable_type_code = variable_header.find("pvt").text
    try:
        variable_type = variable_type_lookup[variable_type_code]
    except KeyError:
        variable_type = variable_type_code
        rutroh_error(f"Unknown variable type: {variable_type_code}")
    limit_repeats = f"Limiit Repeats:{limit}, " if limit else ""
    cooldown = f"Cooldown Time (seconds):{cooldown}, " if cooldown else ""

    # Put together everything
    out_string = f"<br>{property_tag} Properties...{cooldown}, {limit_repeats}Variable Title:{display_name}, Variable:{variable_name}, type: {variable_type}, clear-out:{clearout}, Configure on Import:{configure_on_import}, Structured Variable (JSON, etc.):{structured_variable}, Immutable:{immutable}, Value:{value}, Display Name:{display_name}, Prompt:{prompt}, Exported Value:{exported_value}<br>\n"

    # Make it pretty
    blank = "&nbsp;"
    if PrimeItems.program_arguments["pretty"]:
        number_of_blanks = 20 if out_string.startswith("<br>Task") else 23
        out_string = out_string.replace(",", f"<br>{blank*number_of_blanks}")

    # Put the line '"Structure Output (JSON, etc)' back together.
    out_string = fix_json(out_string, " Structured Variable")

    # Ok, output the line.
    PrimeItems.output_lines.add_line_to_output(2, out_string, ["", css_attribute, FormatLine.add_end_span])


# Figure out which CSS attribute to insert into the output
def get_css_attributes(property_tag: str) -> str:
    """
    Get the CSS attribute based on the property tag.

    Args:
        property_tag (str): The property tag to determine the CSS attribute for.

    Returns:
        str: The CSS attribute corresponding to the property tag.
    """
    if property_tag == "Project:":
        css_attribute = "project_color"
    elif property_tag == "Task:":
        css_attribute = "task_color"
    else:
        css_attribute = "profile_color"

    return css_attribute


# Given the xml header to the Project/Profile/Task, get the properties belonging
# to this header and write them out.
def get_properties(property_tag: str, header: defusedxml.ElementTree) -> None:
    """

    Args:
        property_tag (str): Either "Project:", "Profile:", or "Task:"
        header (defusedxml.ElementTree): xml header to Project/Profile/Task

    Returns:
        nothing
    """
    collision = ["Abort New Task", "Abort Existing Task", "Run Both Together"]
    have_property = False

    # Get our HTML / CSS attributes
    css_attribute = get_css_attributes(property_tag)

    # Get the item comment, if any.  Don't process it if we already have it
    comment_xml = header.find("pc")
    if comment_xml is not None:
        out_string = f"<br>{property_tag} Properties comment: {comment_xml.text}"
        PrimeItems.output_lines.add_line_to_output(2, out_string, ["", css_attribute, FormatLine.add_end_span])
        have_property = True

    keep_alive = header.find("stayawake")
    if keep_alive is not None:
        out_string = f"<br>{property_tag} Properties Keep Device Awake: {keep_alive.text}"
        PrimeItems.output_lines.add_line_to_output(2, out_string, ["", css_attribute, FormatLine.add_end_span])
        have_property = True

    collision_handling = header.find("rty")
    if collision_handling is not None:
        out_string = f"<br>{property_tag} Properties Collision Handling: {collision[int(collision_handling.text)]}"
        PrimeItems.output_lines.add_line_to_output(2, out_string, ["", css_attribute, FormatLine.add_end_span])
        have_property = True

    # Look for variables in the head XML object (Project/Profile/Task).
    cooldown = ""
    limit = ""
    for item in header:
        if item.tag == "cldm":
            cooldown = item.text
        if item.tag == "limit":
            limit = item.text
        if item.tag == "ProfileVariable":
            parse_variable(property_tag, css_attribute, item, cooldown, limit)
            have_property = True

    # Force a new line if we output any properties.
    if have_property:
        PrimeItems.output_lines.add_line_to_output(5, "<br>", FormatLine.dont_format_line)
