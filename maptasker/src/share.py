#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# share: process TaskerNet "Share" information                                         #
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
from maptasker.src.sysconst import FONT_FAMILY, FormatLine
from maptasker.src.primitem import PrimeItems


# ##################################################################################
# Go through xml <Share> elements to grab and output TaskerNet description and
# search-on lines.
# ##################################################################################
def share(
    root_element: defusedxml.ElementTree.XML,
) -> None:
    """
    Go through xml <Share> elements to grab and output TaskerNet description and search-on lines
        :param root_element: beginning xml element (e.g. Project or Task)
    """
    # Get the <share> element, if any
    share_element: defusedxml.ElementTree = root_element.find("Share")
    if share_element is not None:
        #  We have a <Share> .  Find the description
        description_element = share_element.find("d")
        # Process the description
        if description_element is not None:
            description_element_output(
                description_element,
            )

        # Look for TaskerNet search parameters
        search_element = share_element.find("g")
        if search_element is not None and search_element.text:
            # Found search...format and output
            out_string = format_html(
                "taskernet_color",
                "",
                f"\n<br><br>TaskerNet search on: {search_element.text}",
                True,
            )
            PrimeItems.output_lines.add_line_to_output(2, out_string, FormatLine.dont_format_line)


# ################################################################################
# Process the description <d> element
# ################################################################################
def description_element_output(
    description_element: defusedxml.ElementTree,
) -> None:
    """
    We have a Taskernet description (<Share>).  Clean it uip and add it to
    the output list.

        :param description_element: xml element <d> TaskerNet description
    """
    # We need to properly format this since it has embedded stuff that screws it up
    out_string = format_html(
        "taskernet_color",
        "",
        f"TaskerNet description: {description_element.text}",
        True,
    )
    indent_html = (
        "</p><p"
        f' style="margin-left:20px;margin-right:50px;color:'
        f'{PrimeItems.colors_to_use["taskernet_color"]}'
        f'{FONT_FAMILY}{PrimeItems.program_arguments["font"]}">'
    )

    # Indent the description and override various embedded HTML attributes
    out_string = out_string.replace("<p>", indent_html)
    out_string = out_string.replace("<P>", indent_html)
    out_string = out_string.replace("</p>", "")
    out_string = out_string.replace("</P>", "")
    out_string = out_string.replace("<b>", "")
    out_string = out_string.replace("<br>", indent_html)
    out_string = out_string.replace("<h1>", indent_html)
    out_string = out_string.replace("\r", indent_html)
    out_string = out_string.replace("<li>", indent_html)
    out_string = out_string.replace("</li>", "")
    out_string = out_string.replace("<strong>", "")
    out_string = out_string.replace("\n", indent_html)

    out_string = out_string.replace(
        "<table>",
        (
            "\n<style>\n.myTable2 {\n color:"
            + PrimeItems.colors_to_use["taskernet_color"]
            + ';}\n</style>\n<table class="myTable2">'
        ),
    )

    # Look for double blanks = line break
    new_line = ""
    if indent_html not in out_string:  # Only if we have not already formatted
        for position, character_index in enumerate(out_string):
            new_line = (
                f'{new_line}<p style="margin-left:20px;'
                f"margin-right:50px;color:"
                f'{PrimeItems.colors_to_use["taskernet_color"]}'
                f'{FONT_FAMILY}{PrimeItems.program_arguments["font"]}">'
                if (character_index == " " and out_string[position + 1] == " ")
                or (character_index == "-" and out_string[position + 1] == " ")
                else new_line + character_index
            )

        # Make certain we have proper html in front of string
        if "<span " not in out_string:
            out_string = format_html("taskernet_color", "", new_line, True)
        else:
            out_string = new_line

    # Output the description line.
    PrimeItems.output_lines.add_line_to_output(2, f"{out_string}", FormatLine.dont_format_line)
