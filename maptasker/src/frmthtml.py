#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# format_html: Format HTML based on input arguments                                    #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.sysconst import FONT_FAMILY


def format_html(
    primary_items: dict,
    color_code: str,
    text_before: str,
    text_after: str,
    end_span: bool,
) -> str:
    """
    Plug in the html for color and font, along with the text
        :param primary_items: Program registry.  See primitem.py for details
        :param color_code: the code to use to find the color in colormap
        :param text_before: text to insert before the color/font html
        :param text_after: text to insert after the color/font html
        :param end_span: True=add </span> at end, False=don't add </span> at end
        :return: string with text formatted with color and font
    """

    # Determine and get the color to use
    color_to_use = primary_items.get("colors_to_use", {}).get(color_code, color_code)

    # Return completed HTML with color, font and text with text after
    if text_after:
        font = f'{FONT_FAMILY}{primary_items["program_arguments"]["font"]}'
        text_after = text_after.replace(
            f'<span style="color:{color_to_use}{font}"><span', "<span"
        )
        # Set up the trailing HTML to include
        trailing_span = "</span>" if end_span else ""
        return f'{text_before}<span style="color:{color_to_use}{font}">{text_after}{trailing_span}'

    # No text after...just return it.
    else:
        return text_after
