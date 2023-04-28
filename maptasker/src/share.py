#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# share: process TaskerNet "Share" information                                               #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import defusedxml.ElementTree  # Need for type hints


from maptasker.src.outputl import my_output
from maptasker.src.sysconst import FONT_TO_USE
from maptasker.src.frmthtml import format_html


def share(
    root_element: defusedxml.ElementTree.XML,
    colormap: dict,
    program_args: dict,
    output_list: list,
) -> None:
    """
    Go through xml <Share> elements to grab and output TaskerNet description and search-on lines
        :param root_element: beginning xml element (e.g. Project or Task)
        :param colormap: colors to use in output
        :param program_args: runtime arguments
        :param output_list: where all output lines are added to
    """
    # Get the <share> element, if any
    share_element: defusedxml.ElementTree = root_element.find("Share")
    if share_element is not None:
        #  We have a <Share> .  Find the description
        description_element = share_element.find("d")
        # Process the description
        if description_element is not None:
            description_element_output(
                description_element, colormap, program_args, output_list
            )
        # Look for search parameters
        search_element = share_element.find("g")
        if search_element is not None and search_element.text:
            # Found search...format and output
            # my_output(colormap, program_args, output_list, 4, "")  # Force new line
            out_string = f"&nbsp;&nbsp;TaskerNet search on: {search_element.text}"
            my_output(colormap, program_args, output_list, 2, out_string)


# Process the description <d> element
def description_element_output(
    description_element: defusedxml.ElementTree,
    colormap: dict,
    program_args: dict,
    output_list: list,
) -> None:
    """
    We have a Taskernet description (<Share>).  Clean it uip and add it to the output list
        :param description_element: the xml element with the description
        :param colormap: the colors to use for the output
        :param program_args: the runtime arguments
        :param output_list: the output lines thus far
    """
    # We need to properly format this since it has embedded stuff that screws it up
    out_string = format_html(
        colormap,
        "taskernet_color",
        "",
        f"TaskerNet description: {description_element.text}",
        True,
    )
    indent_html = (
        '</p><p'
        f' style="margin-left:20px;margin-right:50px;color:{colormap["taskernet_color"]}{FONT_TO_USE}">'
    )

    # Indent the description and override various embedded HTML attributes
    out_string = out_string.replace("<p>", indent_html)
    out_string = out_string.replace("<P>", indent_html)
    out_string = out_string.replace("</p>", "")
    out_string = out_string.replace("</P>", "")
    out_string = out_string.replace("<br/>", indent_html)
    out_string = out_string.replace("<h1>", indent_html)
    out_string = out_string.replace("\r", indent_html)
    out_string = out_string.replace("<li>", f'{indent_html}')
    out_string = out_string.replace("</li>", "")
    # out_string = remove_html_tags(out_string, indent_html)

    # Look for double blanks = line break
    new_line = ""
    if indent_html not in out_string:  # Only if we have not already formatted
        for position, character_index in enumerate(out_string):
            new_line = (
                f'{new_line}<p style="margin-left:20px;'
                f'margin-right:50px;color:{colormap["taskernet_color"]}{FONT_TO_USE}">'
                if (character_index == " " and out_string[position + 1] == " ")
                or (character_index == "-" and out_string[position + 1] == " ")
                else new_line + character_index
            )

        # Make certain we have proper html in front of string
        # if indent_html not in out_string:
        if "<span " not in out_string:
            out_string = format_html(colormap, "taskernet_color", "", new_line, True)
        else:
            out_string = new_line

    # Output the description line
    my_output(colormap, program_args, output_list, 2, out_string)
