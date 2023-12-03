#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# addcss: Add formatting CSS to output HTML for the colors and font to use             #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

from maptasker.src.sysconst import FONT_FAMILY, FormatLine
from maptasker.src.primitem import PrimeItems


def add_css() -> None:
    """
    Add formatting CSS to output HTML for the colors and font to use.
    We must re-add the font each time in case a Tasker element overrides the font.
        Args:
            None
    """

    # Start the style css
    PrimeItems.output_lines.add_line_to_output(
        5,
        '<style  type="text/css">\n',
        FormatLine.dont_format_line,
    )

    # Go through all colors

    # First, get the liost of colors and reverse the dictionary
    if PrimeItems.colors_to_use:
        for color_argument_name in PrimeItems.colors_to_use:
            try:
                if PrimeItems.colors_to_use[color_argument_name]:
                    our_html = f'color: {PrimeItems.colors_to_use[color_argument_name]}{FONT_FAMILY}{PrimeItems.program_arguments["font"]}'
                    PrimeItems.output_lines.add_line_to_output(
                        5,
                        f".{color_argument_name} {{{our_html}}}",
                        FormatLine.dont_format_line,
                    )
            except KeyError:
                continue

    # Add CSS for Bullet color
    bullet_color = PrimeItems.colors_to_use["bullet_color"]
    bullet_css = """ul {list-style: none;}

ul li::before {
    content: "\\2756";
    color: red;
    font-weight: bold;
    display: inline-block;
    width: 1em;
    margin-left: -1em;
}"""
    bullet_css = bullet_css.replace("red", bullet_color)
    PrimeItems.output_lines.add_line_to_output(5, bullet_css, FormatLine.dont_format_line)

    # End the style css
    PrimeItems.output_lines.add_line_to_output(5, "</style>\n", FormatLine.dont_format_line)
