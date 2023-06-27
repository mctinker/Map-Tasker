import contextlib


def format_line(primary_items: dict, num: int, item: str) -> str:
    """
    Given a line in our list of output lines, do some additional formatting to clean it up
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param num: the numeric line number from the list of output lines
        :param item: the specific text to reformat from the list of output lines
        :return: the reformatted text line for output
    """
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
            primary_items["output_lines"].output_lines[num - 1][:5] == "</ul>"
            and primary_items["output_lines"].output_lines[num - 2][:5] == "</ul>"
            and primary_items["output_lines"].output_lines[num + 1][:4] == "<br>"
        )
    ):
        return ""

    # Change "Action: nn ..." to "Action nn: ..." (i.e. move the colon)
    action_position = item.find("Action: ")
    if action_position != -1:
        action_number_list = item[action_position + 8 :].split(" ")
        action_number = action_number_list[0]
        temp = (
            item[:action_position]
            + action_number
            + ":"
            + item[action_position + 8 + len(action_number) :]
        )
        output_line = temp
    else:
        output_line = item

    # Format the html...add a numbre of blanks if some sort of list
    output_line = output_line.replace("<ul>", f"{blank*5}<ul>\r")
    output_line = output_line.replace("</ul>", f"{blank*5}</ul>\r")
    output_line = output_line.replace("<li", f"{blank*8}<li")
    # Add a carriage return if this is a break
    output_line = output_line.replace("<br>", "<br>\r")

    # Get rid of extraneous html code that somehow got in to the output
    output_line = output_line.replace("</span></span>", "</span>")
    output_line = output_line.replace("</p></p>", "</p>")

    return output_line
