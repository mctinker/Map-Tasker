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

    # Start the style css for the tabs
    PrimeItems.output_lines.add_line_to_output(
        5,
        '\n<style  type="text/css">\n',
        FormatLine.dont_format_line,
    )

    # Go through all colors

    # First, get the liost of colors and reverse the dictionary
    if PrimeItems.colors_to_use:
        for color_argument_name in PrimeItems.colors_to_use:
            with contextlib.suppress(KeyError):
                if PrimeItems.colors_to_use[color_argument_name]:
                    our_html = f"color: {PrimeItems.colors_to_use[color_argument_name]}{FONT_FAMILY}{PrimeItems.program_arguments['font']}"
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

    box = """
    <style>
    .text-box {
        border: 2px solid #333;
        padding-left: 10px;    /* Keeps the existing left padding */
        padding-right: 10px;   /* Keeps the existing right padding */
        padding-top: 0px;     /* Increases the space at the top */
        padding-bottom: 10px;  /* Increases the space at the bottom */
        margin: 10px;
        width: 100%;
        background-color: #f9f9f9;
    }
</style>
    """

    fontsize = """
<style>
    .h0-text { font-size: 16px; line-height: 1.00}
    .h1-text { font-size: 24px; line-height: 1.00}
    .h2-text { font-size: 22px; line-height: 1.00}
    .h3-text { font-size: 20px; line-height: 1.00}
    .h4-text { font-size: 18px; line-height: 1.00}
    .h5-text { font-size: 16px; line-height: 1.00}
    .h6-text { font-size: 15px; line-height: 1.00}
</style>
    """
    resize_image = """
<style>
    .image-small {
        width: 300px;
        height: auto; /* Maintains the aspect ratio */
    }
</style>"""

    # Modsify the tabs with appropriate spacing.
    tabs = tabs.replace("xxx", SPACE_COUNT1[1])
    tabs = tabs.replace("yyy", SPACE_COUNT2[1])
    tabs = tabs.replace("zzz", SPACE_COUNT3[1])
    # Add the tabs
    PrimeItems.output_lines.add_line_to_output(5, tabs, FormatLine.dont_format_line)

    # End the style css
    PrimeItems.output_lines.add_line_to_output(5, "</style>\n", FormatLine.dont_format_line)

    # Add the box
    PrimeItems.output_lines.add_line_to_output(5, box, FormatLine.dont_format_line)

    # Add the fontsizes
    PrimeItems.output_lines.add_line_to_output(5, fontsize, FormatLine.dont_format_line)

    # Add image resize
    PrimeItems.output_lines.add_line_to_output(5, resize_image, FormatLine.dont_format_line)
