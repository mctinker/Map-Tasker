"""Add required formatting CSS to HTML output"""

#! /usr/bin/env python3

#                                                                                      #
# addcss: Add formatting CSS to output HTML for the colors and font to use             #
#                                                                                      #
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from maptasker.src.core import assettext
from maptasker.src.core.htmlsafe import darker, is_dark_color
from maptasker.src.core.sysconst import FONT_FAMILY, SPACE_COUNT1, SPACE_COUNT2, SPACE_COUNT3, FormatLine

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig


def box_colors(background: str) -> tuple[str, str]:
    """(the background, the border) of the box around a TaskerNet description or a Task label.

    The background is a slightly darker tone of the output's own, as the user assigned it, so the box is the page's
    colour and still stands out from it; the border is chosen to show against that: light on a dark page, dark on a
    light one.  With no background assigned (or one that is not a colour) there is no page colour to follow, and the
    box keeps the shades it has always had.
    """
    dark = is_dark_color(background)
    border = "#8a8f98" if dark else "#333"
    if shaded := darker(background):
        return shaded, border
    return ("#2c3138" if dark else "#f9f9f9"), border


def add_css(config: RunConfig, state: RunState) -> None:
    """
    Add formatting CSS to output HTML for the colors and font to use.
    We must re-add the font each time in case a Tasker element overrides the font.
        Args:
            config (RunConfig): the run's settings, for the colors and the output font.
    """

    # Start the style css for the tabs
    state.output_lines.add_line_to_output(
        5,
        '\n<style  type="text/css">\n',
        FormatLine.dont_format_line,
    )

    # Go through all colors

    # First, get the liost of colors and reverse the dictionary
    if config.colors:
        for color_argument_name in config.colors:
            with contextlib.suppress(KeyError):
                if config.colors[color_argument_name]:
                    our_html = f"color: {config.colors[color_argument_name]}{FONT_FAMILY}{config.font}"
                    state.output_lines.add_line_to_output(
                        5,
                        f".{color_argument_name} {{{our_html}}}",
                        FormatLine.dont_format_line,
                    )

    # Add css for Tasker Project/Profile/Task/Scene/SceneTask tabs
    tabs = assettext.render(
        "css/map_tabs.css",
        BLANK_TAB_1=SPACE_COUNT1[1],
        BLANK_TAB_2=SPACE_COUNT2[1],
        BLANK_TAB_3=SPACE_COUNT3[1],
    )

    # The box drawn around a TaskerNet description or a Task label is a slightly darker tone of the colour the user
    # assigned to "Background", rather than a shade of its own: every colour inside it was picked against that
    # background, so the box has to be recognisably the same colour.
    box_background, box_border = box_colors(config.color("background_color", ""))
    # The vertical spacing is deliberately tight.  The box already stands out by its border
    # and its background, and a paragraph's own margin inside it -- a full line top and
    # bottom, on top of the box's margin and padding -- used to leave three and four blank
    # lines around every Task label and TaskerNet description in the Map.
    box = assettext.render("css/map_text_box.css", BOX_BORDER=box_border, BOX_BACKGROUND=box_background)

    fontsize = assettext.text("css/map_font_sizes.css")
    resize_image = assettext.text("css/map_image.css")

    # Fast-appearing tooltip used in place of the native "title" attribute, whose
    # browser-imposed show delay (a second or more) can't be shortened via HTML/CSS.
    # The font is the one to use for the rest of the output -- the tooltip has to render in the
    # same monospaced font, since build_two_column_tooltip_lines() (format.py) pads its columns
    # by character count and relies on that to line up.  Only the font-family takes it: the
    # text color stays #fff (the font name used to be written into that too, leaving an invalid
    # color that the browser dropped).
    tooltip = assettext.render("css/map_tooltip.css", FONT=config.font)

    # Add the tabs
    state.output_lines.add_line_to_output(5, tabs, FormatLine.dont_format_line)

    # End the style css
    state.output_lines.add_line_to_output(5, "</style>\n", FormatLine.dont_format_line)

    # Add the box
    state.output_lines.add_line_to_output(5, box, FormatLine.dont_format_line)

    # Add the fontsizes
    state.output_lines.add_line_to_output(5, fontsize, FormatLine.dont_format_line)

    # Add image resize
    state.output_lines.add_line_to_output(5, resize_image, FormatLine.dont_format_line)

    # Add the fast-appearing hover tooltip, rendered in the font the user selected.
    state.output_lines.add_line_to_output(5, tooltip, FormatLine.dont_format_line)
