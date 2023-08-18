#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# format_line: Format the output line before it gets written to file                   #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.sysconst import pattern5, pattern6, pattern7, pattern8, pattern9, pattern10


def format_line(primary_items: dict, num: int, item: str) -> str:
    """
    Given a line in our list of output lines, do some additional formatting
    to clean it up
        :param primary_items:  program registry.  See mapit.py for details.
        :param num: the numeric line number from the list of output lines
        :param item: the specific text to reformat from the list of output lines
        :return: the reformatted text line for output
    """
    output_obj = primary_items["output_lines"]
    output_lines = output_obj.output_lines      
    blank = " "
    # If item is a list, then get the actual output line
    if type(item) is list:
        item = item[1]
    # Get rid of trailing blanks
    item.rstrip()
    # Ignore lines with "</ul></ul></ul><br>"
    if (
        num > 3
        and item[:5] == "</ul>"
        and (
            output_lines[num - 1][:5] == "</ul>"
            and output_lines[num - 2][:5] == "</ul>"
            and output_lines[num + 1][:4] == "<ul>"
        )
    ):
        return ""

    # Change "Action: nn ..." to "Action nn: ..." (i.e. move the colon)
    action_position = item.find("Action: ")
    if action_position != -1:
        action_number_list = item[action_position + 8 :].split(" ")
        action_number = action_number_list[0]
        temp = "".join([item[:action_position], action_number, ":",
                item[action_position + 8 + len(action_number):]])
        output_line = temp
    # No changes needed
    else:
        output_line = item

    # Format the html...add a numbre of blanks if some sort of list
    # output_line = output_line.replace("<ul>", f"{blank*5}<ul>\r")
    # Replace "<ul>" with "    <ul>\r"
    output_line = pattern5.sub(f"{blank*5}<ul>\r", output_line)
    # replace("</ul>" with f"{blank*5}</ul>\r"
    output_line = pattern6.sub(f"{blank*5}</ul>\r", output_line)
    # replace("<li" with f"{blank*8}<li"
    output_line = pattern7.sub(f"{blank*8}<li", output_line)
    # Add a carriage return if this is a break
    # replace("<br>" with "<br>\r"
    output_line = pattern8.sub("<br>\r", output_line)

    # Get rid of extraneous html code that somehow got in to the output
    # replace("</span></span>" with "</span>"
    output_line = pattern9.sub("</span>", output_line)
    # replace("</p></p>" with "</p>"
    output_line = pattern10.sub("</p>", output_line)

    return output_line
