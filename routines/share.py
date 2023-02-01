# ########################################################################################## #
#                                                                                            #
# share: process TaskerNet 'Share" information                                               #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import xml.etree.ElementTree  # Need for type hints
from routines.outputl import my_output


def share(
    root_element: xml.etree,
    colormap: dict,
    program_args: dict,
    output_list: list,
) -> None:
    # Get the <share> element, if any
    share_element: xml.etree = root_element.find("Share")
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
            my_output(colormap, program_args, output_list, 3, "")  # Force new line
            out_string = f"TaskerNet search on: {search_element.text}"
            my_output(colormap, program_args, output_list, 2, out_string)


# Process the description <d> element
def description_element_output(
    description_element, colormap, program_args, output_list
):
    # We need to properly format this since it has embedded stuff that screws it up
    out_string = f"TaskerNet description: {description_element.text}"
    indent_html = '<p style="margin-left:20px; margin-right:50px;">'

    # Indent the description
    out_string = out_string.replace("<p>", indent_html)
    out_string = out_string.replace("<br/>", indent_html)
    out_string = out_string.replace("<h1>", indent_html)
    # Look for double blanks = line break
    new_line = ""
    if indent_html not in out_string:  # Only if we have not already formatted
        for position, character_index in enumerate(out_string):
            new_line = (
                f'{new_line}<p style="margin-left:20px; margin-right:50px;">'
                if character_index == " " and out_string[position + 1] == " "
                else new_line + character_index
            )
        out_string = new_line

    # Output the description line
    my_output(colormap, program_args, output_list, 2, out_string)
