#! /usr/bin/env python3
from maptasker.src.sysconst import FONT_TO_USE


# ########################################################################################## #
#                                                                                            #
# format_html: Format HTML based on input arguments                                          #
#                                                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #


def format_html(
    colormap: dict, color_code: str, text_before: str, text_after: str, end_span: bool
) -> str:
    """
    Plug in the html for color and font, along with the text
        :param colormap: dictionary from which to pull the appropriate color based on color_code
        :param color_code: the code to use to find the color in colormap
        :param text_before: text to insert before the color/font html
        :param text_after: text to insert after the color/font html
        :param end_span: True=add </span> at end, False=don't add </span> at end
        :return: string with text formatted with color and font
    """

    trailing_span = "</span>" if end_span else ""
    try:
        color_to_use = colormap[color_code]
    except KeyError:
        color_to_use = color_code

    # Return completed HTML with color, font and text
    if text_after:
        text_after = text_after.replace(
            f'<span style="color:{color_to_use};font-family:Courier"><span', "<span"
        )
        return (
            f'{text_before}<span'
            f' style="color:{color_to_use}{FONT_TO_USE}">{text_after}{trailing_span}'
        )
    else:
        return text_after
