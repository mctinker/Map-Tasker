"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# format: Various formatting functions,                                                #
#                                                                                      #

from maptasker.src.sysconst import (
    pattern2,
    # pattern5,
    # pattern6,
    # pattern7,
    pattern8,
    pattern9,
    pattern10,
)

THREE_LINES = 3


# Given a line in the output queue, reformat it before writing to file
def format_line(item: str) -> str:
    """
    Given a line in our list of output lines, do some additional formatting
    to clean it up
        :param item: the specific text to reformat from the list of output lines
        :return: the reformatted text line for output
    """

    # output_lines = output_obj.output_lines
    # blank = " "

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
        output_line = item.replace(f"Action: {action_number[0]}", f"{action_number[0]}:")

    # No changes needed
    else:
        output_line = item

    # # Format the html...add a number of blanks if some sort of list.

    # Add a carriage return if this is a break: replace("<br>" with "<br>\r"
    output_line = pattern8.sub("<br>\r", output_line)
    # Get rid of trailing blank
    output_line = pattern2.sub("", output_line)  # Get space-commas: " ,"

    # Get rid of extraneous html code that somehow got in to the output
    # replace("</span></span>" with "</span>"
    output_line = pattern9.sub("</span>", output_line)
    # replace("</p></p>" with "</p>"
    # output_line = pattern10.sub("</p>", output_line)

    return pattern10.sub("</p>", output_line)


# Plug in the html for color along with the text
def format_html(
    color_code: str,
    text_before: str,
    text_after: str,
    end_span: bool,
) -> str:
    """
    Plug in the html for color and font, along with the text
        :param color_code: the code to use to find the color in colormap
        :param text_before: text to insert before the color/font html
        :param text_after: text to insert after the color/font html
        :param end_span: True=add </span> at end, False=don't add </span> at end
        :return: string with text formatted with color and font
    """

    # Determine and get the color to use.
    # Return completed HTML with color, font and text with text after
    if text_after:
        # The following line eliminates a <span color that is immediately followed by
        # another span color...only happens 3 out of 20,000 lines.  And leaving it in
        # has no adverse impact to the output other than an extra span that is overridden.
        # text_after = text_after.replace(f'<span class="{color_code}"><span', "<span")

        # Set up the trailing HTML to include
        trailing_span = "</span>" if end_span else ""
        return f'{text_before}<span class="{color_code}">{text_after}{trailing_span}'

    # No text after...just return it.
    return text_after
