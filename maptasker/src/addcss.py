"""Add required formatting CSS to HTML output"""

#! /usr/bin/env python3

#                                                                                      #
# addcss: Add formatting CSS to output HTML for the colors and font to use             #
#                                                                                      #
import contextlib

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FONT_FAMILY, SPACE_COUNT1, SPACE_COUNT2, SPACE_COUNT3, FormatLine


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
.blanktab1 {display: inline-block; margin-right: xxx;}
.blanktab2 {display: inline-block; margin-right: yyy;}
.blanktab3 {display: inline-block; margin-right: zzz;}
    """
    tabs = tabs.replace("xxx", SPACE_COUNT1[1])
    tabs = tabs.replace("yyy", SPACE_COUNT2[1])
    tabs = tabs.replace("zzz", SPACE_COUNT3[1])
    PrimeItems.output_lines.add_line_to_output(5, tabs, FormatLine.dont_format_line)

    # End the style css
    PrimeItems.output_lines.add_line_to_output(5, "</style>\n", FormatLine.dont_format_line)
