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

from maptasker.src.sysconst import FONT_FAMILY


def add_css(primary_items: dict) -> None:
    """_summary_
    Add formatting CSS to output HTML for the colors and font to use.
    We must re-add the font each time in case a Tasker element overrides the font.
        Args:
            primary_items (dict): Program registry.  See primitem.py for details
    """

    # Start the style css
    primary_items["output_lines"].add_line_to_output(
        primary_items, 5, '<style  type="text/css">\n'
    )

    # Go through all colors

    # First, get the liost of colors and reverse the dictionary
    if primary_items["colors_to_use"]:
        for color_argument_name in primary_items["colors_to_use"]:
            try:
                if primary_items["colors_to_use"][color_argument_name]:
                    our_html = f'color: {primary_items["colors_to_use"][color_argument_name]}{FONT_FAMILY}{primary_items["program_arguments"]["font"]}'
                    primary_items["output_lines"].add_line_to_output(
                        primary_items, 5, f".{color_argument_name} {{{our_html}}}"
                    )
            except KeyError:
                continue

    # Add CSS for Bullet color
    bullet_color = primary_items["colors_to_use"]["bullet_color"]
    bullet_css = """ul {
  list-style: none;
}

ul li::before {
  content: "\\2756";
  color: red;
  font-weight: bold;
  display: inline-block; 
  width: 1em;
  margin-left: -1em;
}"""
    bullet_css = bullet_css.replace("red", bullet_color)
    primary_items["output_lines"].add_line_to_output(primary_items, 5, bullet_css)

    # End the style css
    primary_items["output_lines"].add_line_to_output(primary_items, 5, "</style>\n")
