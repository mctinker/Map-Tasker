"""Add required formatting CSS to HTML output"""

#! /usr/bin/env python3

#                                                                                      #
# addcss: Add formatting CSS to output HTML for the colors and font to use             #
#                                                                                      #
import contextlib

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FONT_FAMILY, FormatLine


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
            with contextlib.suppress(KeyError):
                if PrimeItems.colors_to_use[color_argument_name]:
                    our_html = f'color: {PrimeItems.colors_to_use[color_argument_name]}{FONT_FAMILY}{PrimeItems.program_arguments["font"]}'
                    PrimeItems.output_lines.add_line_to_output(
                        5,
                        f".{color_argument_name} {{{our_html}}}",
                        FormatLine.dont_format_line,
                    )

    #     # Add CSS for Bullet color
    #     bullet_color = PrimeItems.colors_to_use["bullet_color"]
    #     bullet_css = """ul {list-style: none;}

    # ul li::before {
    #     content: "\\2756";
    #     color: red;
    #     font-weight: bold;
    #     display: inline-block;
    #     width: 1em;
    #     margin-left: -1em;
    # }"""
    #     bullet_css = bullet_css.replace("red", bullet_color)
    #     PrimeItems.output_lines.add_line_to_output(5, bullet_css, FormatLine.dont_format_line)

    # Add css for Tasker Project/Profile/Task/Scene/SceneTask tabs
    tabs = """
.resettab {display: inline-block; margin-left: 0;}
.normtab {display: inline-block; margin-left: 20;}
.projtab {display: inline-block; margin-left: 20;}
.proftab {display: inline-block; margin-left: 40;}
.tasktab {display: inline-block; margin-left: 70;}
.actiontab {display: inline-block; margin-left: 80;}
.scenetab {display: inline-block; margin-left: 20;}
.scenetasktab {display: inline-block; margin-left: 30;}
    """
    PrimeItems.output_lines.add_line_to_output(5, tabs, FormatLine.dont_format_line)

    # End the style css
    PrimeItems.output_lines.add_line_to_output(5, "</style>\n", FormatLine.dont_format_line)
