"""Handle Object Properties"""

#! /usr/bin/env python3

#                                                                                      #
# property: get Project/Profile/Task properties and output them                        #
#                                                                                      #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.actione import fix_json
from maptasker.src.error import rutroh_error
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


# Helper function to get text safely
def get_text(element: defusedxml.ElementTree) -> str:
    """Return value or"""
    return element.text if element is not None else ""


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
    # Extract values from XML once
    fields = {
        "clearout": variable_header.find("clearout"),
        "immutable": variable_header.find("immutable"),
        "pvci": variable_header.find("pvci"),
        "pvd": variable_header.find("pvd"),
        "pvv": variable_header.find("pvv"),
        "pvdn": variable_header.find("pvdn"),
        "strout": variable_header.find("strout"),
        "pvn": variable_header.find("pvn"),
        "exportval": variable_header.find("exportval"),
        "pvt": variable_header.find("pvt"),
    }

    # Mapping field values to output strings.  They are in the order as displayed in Tasker.
    components = [
        f"Variable:{get_text(fields['pvn'])}, " if get_text(fields["pvn"]) else "",
        "Configure on Import, " if get_text(fields["pvci"]) != "false" else "",
        "Structured Variable (JSON, etc.), " if get_text(fields["strout"]) != "false" else "",
        "Immutable, " if get_text(fields["immutable"]) != "false" else "",
        f"Clear Out:{get_text(fields['clearout'])}, " if get_text(fields["clearout"]) != "false" else "",
        f"Prompt:{get_text(fields['pvd'])}, " if get_text(fields["pvd"]) else "",
        f"Value:{get_text(fields['pvv'])}, " if get_text(fields["pvv"]) else "",
        f"Display Name:{get_text(fields['pvdn'])}, " if get_text(fields["pvdn"]) else "",
    ]

    # Determine exported value
    exported_value = "Same as Value" if get_text(fields["pvn"]) == "1" else get_text(fields["exportval"])
    components.append(f"Exported Value:{exported_value}, " if exported_value else "")

    # Get the variable type
    variable_type_code = get_text(fields["pvt"])
    variable_type = variable_type_lookup.get(variable_type_code, variable_type_code)
    if variable_type_code not in variable_type_lookup:
        rutroh_error(f"Unknown variable type: {variable_type_code}")
    # Make sure the 'type' goes at the beginning.
    components.insert(0, f"Variable Type:{variable_type}, " if variable_type else "")

    # Additional attributes
    if limit:
        components.append(f"Limit Repeats:{limit}, ")
    if cooldown:
        components.append(f"Cooldown Time (seconds):{cooldown}, ")

    # Final output string
    out_string = f"<br>{property_tag} Properties..." + "".join(components) + "<br>\n"

    # Make it pretty
    blank = "&nbsp;"
    if PrimeItems.program_arguments["pretty"]:
        number_of_blanks = 20 if out_string.startswith("<br>Task") else 23
        out_string = out_string.replace(",", f"<br>{blank * number_of_blanks}")

    # Put the line '"Structure Output (JSON, etc)' back together.
    out_string = fix_json(out_string, " Structured Variable")

    # Ok, output the line.
    PrimeItems.output_lines.add_line_to_output(
        2,
        out_string,
        ["", css_attribute, FormatLine.add_end_span],
    )


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
        PrimeItems.output_lines.add_line_to_output(
            2,
            out_string,
            ["", css_attribute, FormatLine.add_end_span],
        )
        have_property = True

    keep_alive = header.find("stayawake")
    if keep_alive is not None:
        out_string = f"{property_tag} Properties Keep Device Awake: {keep_alive.text}"
        PrimeItems.output_lines.add_line_to_output(
            2,
            out_string,
            ["", css_attribute, FormatLine.add_end_span],
        )
        have_property = True

    collision_handling = header.find("rty")
    if collision_handling is not None:
        out_string = f"{property_tag} Properties Collision Handling: {collision[int(collision_handling.text)]}"
        PrimeItems.output_lines.add_line_to_output(
            2,
            out_string,
            ["", css_attribute, FormatLine.add_end_span],
        )
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
        PrimeItems.output_lines.add_line_to_output(
            5,
            "<br>",
            FormatLine.dont_format_line,
        )
