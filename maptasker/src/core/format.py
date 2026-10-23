"""format: formatting one line of the Map, and the html that goes into it.

format_line and format_html are what the rest of the program calls.  The work behind them is in htmlsafe
(a document made safe and legible), htmlstyle (its stylesheet), htmltext (flattened to text segments),
htmllabel (labels built from those) and mapwriter (the Map's blank-line and span rules)."""

from __future__ import annotations

import html
from itertools import zip_longest

from maptasker.src.core.mapwriter import count_trailing_blanks
from maptasker.src.core.sysconst import FormatLine, pattern2, pattern8, pattern10, pattern15


# Given a line in the output queue, reformat it before writing to file
def format_line(item: str) -> str:
    """
    Given a line in our list of output lines, do some additional formatting
    to clean it up
        :param item: the specific text to reformat from the list of output lines
        :return: the reformatted text line for output
    """
    space = "&nbsp;"
    three_spaces = f"{space * 3}"
    # If item is a list, then get the actual output line
    if isinstance(item, list):
        item = item[1]

    # Get rid of trailing blanks
    item.rstrip()

    # Change "Action: nn ..." to "Action nn: ..." (i.e. move the colon)
    action_position = item.find("Action: ")
    if action_position != -1:
        action_number_list = item[action_position + 8 :].split(" ")
        action_number = action_number_list[0]
        action_number = action_number.split("<")
        output_line = item.replace(
            f"Action: {action_number[0]}",
            f"{action_number[0]}:",
        )

    # Not an 'Action:'. No changes needed
    else:
        output_line = item

    # Handle list markers: ordered and unorderedby including leading blanks.
    while True:
        _count_trailing_blanks = count_trailing_blanks
        lmrk = output_line.find("lmrk")
        if lmrk != -1:
            leading_space_count = _count_trailing_blanks(output_line, lmrk)
            leading_spaces = space * leading_space_count
            new_line = output_line[: (lmrk - leading_space_count)]
            new_line1 = f"{three_spaces}{leading_spaces}"
            new_line2 = output_line[(lmrk + 4) :]
            output_line = new_line + new_line1 + new_line2
        else:
            break

    # # Format the html...add a number of blanks if some sort of list.
    if "DOCTYPE" in item:  # If imbedded html (e.g. Scene WebElement), add a break and some spacing.
        # From the document onwards, and no earlier.  The newlines inside it are the
        # author's, and breaking them out is what makes an embedded document readable as
        # the source it is; the ones before it are the Map's own -- the newline after a
        # directory anchor, say -- and turning those into breaks put a blank line and
        # thirty spaces into the middle of a line that had asked for neither.
        document_start = max(output_line.find("DOCTYPE"), 0)
        output_line = output_line[:document_start] + pattern15.sub(
            f"<br>{space * 30}",
            output_line[document_start:],
        )

    # Add a carriage return if this is a break: replace("<br>" with "<br>\r"
    output_line = pattern8.sub("<br>\r", output_line)
    # Get rid of trailing blank
    output_line = pattern2.sub("", output_line)  # Get space-commas: " ,"

    # "</span></span>" used to be folded down to one here, on the grounds that the second
    # was extraneous.  Once it was: format_html put an end tag on every line whether or not
    # the line had asked for one, and this swept some of them up.  With that fixed at the
    # source, a pair of end tags is two spans genuinely closing, and folding them left the
    # outer one open -- thousands of them across a Map -- for the browser to guess at.
    #
    # Replace double paragraph with single paragraph
    return pattern10.sub("</p>", output_line)


# Plug in the html for color along with the text
def format_html(
    color_code: str,
    text_before: str,
    text_after: str,
    end_span: bool | FormatLine,
) -> str:
    """
    Plug in the html for color and font, along with the text
        :param color_code: the code to use to find the color in colormap
        :param text_before: text to insert before the color/font html
        :param text_after: text to insert after the color/font html
        :param end_span: True or FormatLine.add_end_span=add </span> at end, False or FormatLine.dont_add_end_span=don't
        :return: string with text formatted with color and font
    """
    # Determine and get the color to use.
    # Return completed HTML with color, font and text with text after
    if text_after:
        # The following line eliminates a <span color that is immediately followed by
        # another span color...only happens 3 out of 20,000 lines. And leaving it in
        # has no adverse impact to the output other than an extra span that is overridden.

        # Set up the trailing HTML to include
        trailing_span = "</span>" if end_span in {True, FormatLine.add_end_span} else ""
        return f'{text_before}<span class="{color_code}">{text_after}{trailing_span}'

    # No text after...just return it.
    return text_after


# Wrap a label (e.g. "Task:", "Profile:", "Project:") with a fast-appearing CSS tooltip.
def build_tooltip_span(label: str, tooltip_lines: list[str]) -> str:
    """
    Wrap a label in a <span class="hover-tooltip" data-tooltip="..."> so hovering over it shows
    a tooltip. This uses a custom CSS tooltip (see add_css()) rather than the native "title"
    attribute, since browsers impose a multi-second delay before showing native tooltips that
    can't be shortened via HTML/CSS.

        :param label: the literal text to wrap (e.g. "Task:")
        :param tooltip_lines: lines of plain text to join (newline-separated) into the tooltip.
            Falsy lines are dropped. If the resulting list is empty, the label is returned unwrapped.
        :return: the label wrapped in a <span class="hover-tooltip" data-tooltip="..."> tag,
            or the bare label if no tooltip lines
    """
    lines = [line for line in tooltip_lines if line]
    if not lines:
        return label

    # Use the "&#10;" entity rather than a raw newline so the tag doesn't get split
    # across multiple lines when the output is later read back in line-by-line
    # (e.g. by guimap.py's Map-view parser). Browsers resolve the entity back to a
    # real line break for the CSS "white-space: pre" tooltip in add_css().
    tooltip_text = "&#10;".join(html.escape(line) for line in lines)
    return f'<span class="hover-tooltip" data-tooltip="{tooltip_text}">{label}</span>'


# Build monospace-aligned, two-column lines (e.g. Profiles next to Tasks) for build_tooltip_span().
def build_two_column_tooltip_lines(
    left_header: str,
    left_items: list[str],
    right_header: str,
    right_items: list[str],
) -> list[str]:
    """
    Lay out two lists side by side, one item per line, as plain-text lines suitable for
    build_tooltip_span(). Relies on the tooltip being rendered in a monospace font
    (see the ".hover-tooltip" CSS rule in add_css()) so the columns actually line up.

        :param left_header: header for the left column (e.g. "Profiles:")
        :param left_items: left column's items, one per line
        :param right_header: header for the right column (e.g. "Tasks (sorted):")
        :param right_items: right column's items, one per line
        :return: list of pre-formatted two-column lines, or [] if both columns are empty
    """
    if not left_items and not right_items:
        return []

    col_width = max([len(left_header), *(len(item) for item in left_items)]) + 3
    lines = [f"{left_header:<{col_width}}{right_header}"]
    lines.extend(f"{left:<{col_width}}{right}" for left, right in zip_longest(left_items, right_items, fillvalue=""))
    return lines
