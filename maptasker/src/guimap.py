"""GUI Map"""

#! /usr/bin/env python3

#                                                                                      #
# guimap: reverse engineer the mapped html file and return just the data as a list.    #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import re

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import pattern8
from maptasker.src.xmldata import remove_html_tags


def additional_formatting(doing_global_variables: bool, line: str, output_list: list, spacing: int) -> str:
    """
    Applies special formatting to a given line of text and appends the formatted line to an output list.

    Args:
        doing_global_variables (bool): Whether or not the line contains global variables.
        line (str): The line of text to be formatted.
        output_list (list): The list to which the formatted line will be appended.
        spacing (int): The number of spaces to be inserted at the beginning of the formatted line.

    Returns:
        list: The updated output list.
    """
    # replace "<br>" with "\n"
    output_line = pattern8.sub("\n", line)

    # Extract global variable from table definition
    if output_line[0:7] == "<tr><td":
        temp1 = output_line.split('text-align:left">')
        global_var_name = temp1[1].split("<")[0]
        global_var_value = temp1[2].split("<")[0]
        temp_line = f"{global_var_name.ljust(20, '.')} = {global_var_value.rjust(15, '.')}"

    # Handle the rest of the lines
    else:
        # Remove all HTML
        temp_line = remove_html_tags(output_line, "")

        # Strip out icons: strings that contain something like: &#11013;
        indices = [i.start() for i in re.finditer("&#", temp_line)]
        for icon in indices:
            if temp_line[icon + 7] == ";":
                temp_line = temp_line[:icon] + temp_line[icon + 14 :]  # Bypass #nnnnn; and &nbsp.
            elif temp_line[icon + 6] == ";":
                temp_line = temp_line[:icon] + temp_line[icon + 13 :]  # Bypass #nnnn; and &nbsp.

        temp_line = temp_line.replace("Go to top", "")

    # Insert spacing.
    final_line = temp_line.replace("&nbsp;", " ")
    if final_line[0:8] == "Profile:":
        spacing = 5
    elif final_line[0:5] == "Task:" or final_line[0:11] == "- Project '":
        spacing = 10
    elif final_line[0].isdigit() or " continued >>>" in final_line:
        spacing = 15
    elif doing_global_variables and final_line[0] != "%":
        spacing = 30
    else:
        spacing = 0

    output_list.append(f"{spacing*' '}{final_line}")

    return output_list


# Formats the output HTML by processing each line of the input list.
def format_output(lines: list, output_list: list, spacing: int, iterate: bool) -> list:
    r"""
    Formats the output HTML by processing each line of the input list.

    Args:
        lines (list): A list of lines of HTML code.
        output_list (list): A list to store the formatted output.
        spacing (int): The amount of spacing to be added before each line.
        iterate (bool): A flag indicating whether to skip the next line.

    Returns:
        list: The formatted output list.

    Description:
        This function processes each line of the input list and applies specific formatting rules.
        It checks if the line is a table definition and appends a formatted string to the output list.
        It ignores lines containing non-text data and applies special formatting rules based on the line content.

        The function takes the following parameters:
        - lines (list): A list of lines of HTML code.
        - output_list (list): A list to store the formatted output.
        - spacing (int): The amount of spacing to be added before each line.
        - iterate (bool): A flag indicating whether to skip the next line.

        The function returns the formatted output list.

    """
    doing_global_variables = False
    # Format the html
    for num, line in enumerate(lines):
        # If we are to skip the next line, then skip it.
        if iterate:
            iterate = False
            continue

        # Check if the line is a table definition for Unreferenced Global Variables: Name and Value
        if line == "<th>Name</th>\n" and lines[num + 1] == "<th>Value</th>\n":
            iterate = True
            output_list.append("Variable Name....... = .....Variable Value")
            doing_global_variables = True
            continue

        # End of global variables
        if doing_global_variables and line == "</table><br>\n":
            doing_global_variables = False

        # Ignore non-text data
        if "{color: " in line or "{display: " in line or "padding: 5px;" in line:
            continue

        # Handle special formatting
        output_list = additional_formatting(doing_global_variables, line, output_list, spacing)

    # Elliminate leading blanks.  Care must be taken not to iterate over the list we are modifying.
    i = 0
    n = len(output_list)
    while i < n:
        element = output_list[i]
        if i + 1 >= len(output_list):
            break  # exit the loop if we are at the end of the list
        element2 = output_list[i + 1]
        if element == "\n" and element2 in ("\n", "    \n"):
            del output_list[i]
            n = n - 1
        else:
            i = i + 1
        if element not in ("\n", "    \n"):
            break  # exit the loop if we no longer have any blanks

    return output_list


def parse_html() -> list:
    """
    Parses the HTML file "MapTasker.html" and formats the content into a list of lines.

    Returns:
        list: A list of formatted lines from the parsed HTML file.
    """
    output_list = []
    iterate = False

    # Read the mapped html file
    with open("MapTasker.html") as html:
        lines = html.readlines()

        # Establish base spacing
        spacing = 0

        # Format the html
        return format_output(lines, output_list, spacing, iterate)


def get_the_map() -> list:
    r"""
    Reads the contents of the "MapTasker.html" file and processes each line to generate a list of cleaned-up lines.

    Returns:
        list: A list of cleaned-up lines from the "MapTasker.html" file.

    This function reads the contents of the "MapTasker.html" file line by line to parse the data.

    The cleaned-up lines are then appended to the `output_list` and returned as the result.
    """

    output_list = parse_html()

    PrimeItems.program_arguments["mapgui"] = False
    return output_list
