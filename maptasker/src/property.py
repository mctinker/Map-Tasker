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

from maptasker.src.format import format_html
from maptasker.src.sysconst import FormatLine


# ##################################################################################
# Parse Property's variable and output it
# ##################################################################################
def parse_variable(
    primary_items: dict, variable_header: defusedxml.ElementTree, color_to_use: str
) -> None:
    """_summary_
    Parse Property's variable and output it
        Args:
            primary_items (_type_):  dictionary of the primary items used throughout
                                    the module.  See primitem.py for details
            variable_header (_type_): xml header of property's variable
            color_to_use (_type_): the color to use in the output
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

    # Output the results
    out_string = format_html(
        primary_items,
        color_to_use,
        "",
        f"<br>Properties.... Variable Title:{display_name}, Variable:{variable_name}, \
        clear-out:{clearout}, \
        Configure on Import:{configure_on_import}, Structured Variable (JSON, etc.):{structured_variable}, Immutable:{immutable}, Value:{value}, Display Name:{display_name}, Prompt:{prompt}, Exported Value:{exported_value}",
        True,
    )
    primary_items["output_lines"].add_line_to_output(
        primary_items, 5, out_string, FormatLine.dont_format_line
    )


# Given the xml header to the Project/Profile/Task, get the properties belonging
# to this header and write them out
def get_properties(
    primary_items: dict, header: defusedxml.ElementTree, color_to_use: str
) -> None:
    """_summary_

    Args:
        :param primary_items:  Program registry.  See primitem.py for details.
        header (defusedxml.ElementTree): xml header to Project/Profile/Task
        color_to_use: the color to output the property with

    Returns:
        nothing
    """

    have_property = False
    # Get the item comment, if any
    comment_xml = header.find("pc")
    if comment_xml is not None:
        out_string = format_html(
            primary_items,
            color_to_use,
            "",
            f"<br>Properties comment: {comment_xml.text}",
            True,
        )
        primary_items["output_lines"].add_line_to_output(
            primary_items, 5, out_string, FormatLine.dont_format_line
        )
        have_property = True

    # Look for variables
    for item in header:
        if item.tag == "ProfileVariable":
            parse_variable(primary_items, item, color_to_use)
            have_property = True

    if have_property:
        primary_items["output_lines"].add_line_to_output(
            primary_items, 5, "<br><br>", FormatLine.dont_format_line
        )
    return
