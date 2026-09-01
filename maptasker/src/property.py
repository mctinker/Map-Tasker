"""Handle Object Properties"""

#! /usr/bin/env python3

#                                                                                      #
# property: get Project/Profile/Task properties and output them                        #
#                                                                                      #
import html

import defusedxml.ElementTree  # Need for type hints

from maptasker.src.error import rutroh_error
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


# Helper function to get text safely
def get_text(element: defusedxml.ElementTree) -> str:
    """Return value or"""
    return element.text if element is not None else ""


# Helper function to get text safely, as display data rather than as markup
def get_display_text(element: defusedxml.ElementTree) -> str:
    """Return the element's text with any markup in it escaped so it displays as itself.

    A variable's name/prompt/value is data a person typed into Tasker, not markup meant to
    be rendered, and Tasker users routinely park a whole HTML document in one (a Scene V2
    WebView's page, for instance).  Written into the map as-is, that document's own
    '<style>' rules restyle the map itself -- one project variable holding a WebView page
    whose CSS says 'body {display: flex; height: 100vh; background-color: transparent}'
    was enough to collapse the entire Map view for its Project to a blank page -- and its
    '<script>' runs in the map.  Escaping keeps the value visible as the text it is.

    Args:
        element (defusedxml.ElementTree): the xml element holding the text, or None

    Returns:
        str: the element's text, safe to embed in the output
    """
    # get_text hands back the element's text verbatim, which is None for an empty tag
    # (<pvd></pvd>, of which every variable in a backup has several).
    return html.escape(get_text(element) or "")


# Parse Property's variable and return its properties as a list of items
def parse_variable(variable_header: defusedxml.ElementTree) -> list:
    """
    Parses the variable header of a property tag and returns the properties of the variable.
    Properties are identied in the XML with the tag: <xxxxVariable>, where xxxx is Project/Profile/Task

    The items are returned rather than written out, so that get_properties() can fold them in
    with the object's other properties (comment, keep-awake, collision handling) and output the
    lot as a single "...Properties..." line.

    Args:
        variable_header (defusedxml.ElementTree): The XML element representing the variable header.

    Returns:
        list: this variable's properties, one "Name:value" item per element, in the order Tasker
            displays them
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
        "pvit": variable_header.find("pvt"),
    }

    # Mapping field values to output strings.  They are in the order as displayed in Tasker.
    # Note: Task properties also show up in '<ProfileVariable' underneath the '<Task'.
    components = [
        "Show in Notification" if get_text(fields["pvit"]) == "t" else "",
        f"Variable:{get_display_text(fields['pvn'])}" if get_text(fields["pvn"]) else "",
        "Configure on Import" if get_text(fields["pvci"]) != "false" else "",
        "Structured Variable (JSON, etc.)" if get_text(fields["strout"]) != "false" else "",
        "Immutable" if get_text(fields["immutable"]) != "false" else "",
        f"Clear Out:{get_display_text(fields['clearout'])}" if get_text(fields["clearout"]) != "false" else "",
        f"Prompt:{get_display_text(fields['pvd'])}" if get_text(fields["pvd"]) else "",
        f"Value:{get_display_text(fields['pvv'])}" if get_text(fields["pvv"]) else "",
        f"Display Name:{get_display_text(fields['pvdn'])}" if get_text(fields["pvdn"]) else "",
    ]

    # Determine exported value
    exported_value = "Same as Value" if get_text(fields["pvn"]) == "1" else get_display_text(fields["exportval"])
    components.append(f"Exported Value:{exported_value}" if exported_value else "")

    # Get the variable type
    variable_type_code = get_text(fields["pvt"])
    variable_type = variable_type_lookup.get(variable_type_code, variable_type_code)
    if variable_type_code not in variable_type_lookup:
        rutroh_error(f"Unknown variable type: {variable_type_code}")
    # Make sure the 'type' goes at the beginning.
    components.insert(0, f"Variable Type:{variable_type}" if variable_type else "")

    # Drop the properties this variable doesn't have.
    return [component for component in components if component]


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

    # Get our HTML / CSS attributes
    css_attribute = get_css_attributes(property_tag)

    # Gather every property of this object -- its comment, keep-awake and collision handling
    # settings, and the properties of each of its variables -- into one list of items.  They
    # all belong to the same "...Properties..." block, and go out as a single output line.
    properties = []

    # Get the item comment, if any.  Don't process it if we already have it
    comment_xml = header.find("pc")
    if comment_xml is not None:
        properties.append(f"Comment:{comment_xml.text}")

    keep_alive = header.find("stayawake")
    if keep_alive is not None:
        properties.append(f"Keep Device Awake:{keep_alive.text}")

    collision_handling = header.find("rty")
    if collision_handling is not None:
        properties.append(f"Collision Handling:{collision[int(collision_handling.text)]}")

    # Look for variables in the head XML object (Project/Profile/Task).
    cooldown = ""
    limit = ""
    have_variable = False
    _parse_variable = parse_variable
    for item in header:
        if item.tag == "cldm":
            cooldown = item.text
        if item.tag == "limit":
            limit = item.text
        if item.tag == "ProfileVariable":
            properties.extend(_parse_variable(item))
            have_variable = True

    # Limit/cooldown belong to the object rather than to any one of its variables, so they go
    # at the end of the block, listed once no matter how many variables it has (they used to be
    # repeated for every one of them).  Still only reported alongside variables, as before:
    # <limit>true</limit> is on most Profiles (228 of them in the sample backup), so listing it
    # for its own sake would put a Properties line on nearly every Profile in the map.
    if have_variable:
        if limit:
            properties.append(f"Limit Repeats:{limit}")
        if cooldown:
            properties.append(f"Cooldown Time (seconds):{cooldown}")

    if not properties:
        return

    # Make it pretty: one property per line, lined up under the "...Properties..." header.
    # Joining the items rather than replacing every "," in the finished line (which is what
    # this used to do) keeps a comma belonging to the text itself -- one inside a comment or a
    # variable's value, or the one in "Structured Variable (JSON, etc.)" -- from being turned
    # into a line break.
    if PrimeItems.program_arguments["pretty"]:
        blank = "&nbsp;"
        number_of_blanks = 20 if property_tag == "Task:" else 23
        separator = f"<br>{blank * number_of_blanks}"
    else:
        separator = ", "

    # Ok, output the properties as a single line.
    out_string = f"<br>{property_tag} Properties..." + separator.join(properties) + "<br>"
    PrimeItems.output_lines.add_line_to_output(
        2,
        out_string,
        ["", css_attribute, FormatLine.add_end_span],
    )
