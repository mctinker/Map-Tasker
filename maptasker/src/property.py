#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# property: get Project/Profile/Task properties and output them                        #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


# ##################################################################################
# Parse Property's variable and output it
# ##################################################################################
def parse_variable(property_tag: str, variable_header: defusedxml.ElementTree) -> None:
    """
    Parse Property's variable and output it
        Args:
            property_tag (str): Either "Project:", "Profile:", or "Task:"
            variable_header (_type_): xml header of property's variable
    """

    # Get the various property
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

    # If doing Projeect properties, we need to add the tab since this is the first thing output for the Project.
    if property_tag == "Project:":
        tab = '<span class="project_color">'
        endtab = "</span>"
    else:
        tab = ""
        endtab = ""

    # Output the results
    out_string = f"<br>{tab}{property_tag} Properties.... Variable Title:{display_name}, Variable:{variable_name}, clear-out:{clearout}, Configure on Import:{configure_on_import}, Structured Variable (JSON, etc.):{structured_variable}, Immutable:{immutable}, Value:{value}, Display Name:{display_name}, Prompt:{prompt}, Exported Value:{exported_value}{endtab}<br>\n"
    PrimeItems.output_lines.add_line_to_output(2, out_string, FormatLine.dont_format_line)


# ##################################################################################
# Given the xml header to the Project/Profile/Task, get the properties belonging
# to this header and write them out.
# ##################################################################################
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

    # Get the item comment, if any
    comment_xml = header.find("pc")
    if comment_xml is not None:
        out_string = f"<br>{property_tag} Properties comment: {comment_xml.text}"
        PrimeItems.output_lines.add_line_to_output(2, out_string, FormatLine.dont_format_line)
        have_property = True

    keep_alive = header.find("stayawake")
    if keep_alive is not None:
        out_string = f"<br>{property_tag} Properties Keep Device Awake: {keep_alive.text}"
        PrimeItems.output_lines.add_line_to_output(2, out_string, FormatLine.dont_format_line)
        have_property = True

    collision_handling = header.find("rty")
    if collision_handling is not None:
        out_string = f"<br>{property_tag} Properties Collision Handling: {collision[int(collision_handling.text)]}"
        PrimeItems.output_lines.add_line_to_output(2, out_string, FormatLine.dont_format_line)
        have_property = True

    # Look for variables in the head XML object (Projectc/Profile/Task).
    for item in header:
        if item.tag == "ProfileVariable":
            parse_variable(property_tag, item)
            have_property = True

    # Force a new line if we output any properties.
    if have_property:
        PrimeItems.output_lines.add_line_to_output(5, "<br>", FormatLine.dont_format_line)
