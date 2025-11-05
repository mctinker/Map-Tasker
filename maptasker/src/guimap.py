#! /usr/bin/env python3
"""GUI Map"""

#                                                                                      #
# guimap: reverse engineer the mapped html file and return just the data as a list.    #
#         This data is then to be processed by guiwins for the map configuration.      #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import contextlib
import re

from maptasker.src.error import rutroh_error
from maptasker.src.guiutils import align_text
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import pattern8
from maptasker.src.xmldata import remove_html_tags

r"""
The data consists of a list of dictionary values (formatted by guimap)...
        'text': list of text values
                special flag of '\nn' in front of text element indicates that this is a directory heading.
        'color': list of colors to apply to each element in 'text'
        'directory' (optional): list [element 0=Tasker object type ('projects', 'profiles', 'tasks', 'scenes'),
                                        element 1=object name]
                    'text' and 'color' are empty if directory is present.
        'highlights': list of highlights to apply to the text elements (e.g. bold, underline, etc..)
"""
glob_spacing = 15


def process_label_html(lines: list, output_lines: dict, line_num: int, spacing: int) -> int:
    """
    Parses HTML content from a list of strings, extracting text, color, and font information.

    This function iterates through a list of HTML lines, specifically looking for `<span>`
    tags to extract text content, a 7-character color code from the 'style' attribute,
    and a 7-character font class from the 'class' attribute. It processes lines until
    it encounters a `<div>` tag, and populates a dictionary with the extracted data.

    This modified version processes and concatenates text chunks with the same color
    and font within a single HTML line before adding it to the output dictionary.

    Args:
        lines (list): A list of strings, where each string is a line of HTML content.
        output_lines (dict): A dictionary to store the extracted information. The
                             keys are line numbers and the values are dictionaries
                             containing lists for "text", "color", and "highlights".
        line_num (int): The starting line number (index) in `lines` to begin parsing from.
        spacing (int): The initial spacing value.


    Returns:
        int: The number of lines that were processed (skipped) by this function.

    Note: This code is really ugly!
    """
    lines_to_skip = 0
    # Determine if there is html in current line (typically it is in the line after the current line)
    temp = lines[line_num].split("text-box")
    if "style=" not in temp[1]:
        line_num += 1
        line_num_to_add = line_num
    else:
        line_num_to_add = line_num + 1

    # A new flag to control the flow of the outer while loop
    continue_processing = True
    # This will hold the processed data for the current logical line
    processed_line_data = []
    in_style = False
    table = False
    previous_style = []
    _add_line_data = add_line_data  # Cache the routine

    # Go through all of the data
    while line_num < len(lines) and continue_processing:
        # Check if the line starts with <div> and if so, stop processing.
        if lines[line_num].startswith("<div "):
            continue_processing = False
            continue

        # Breakout the html spans
        html_lines = lines[line_num].split("<span ")

        last_item = {}
        # Set the end of label flag
        lblend = False

        for num, line in enumerate(html_lines):
            # Skip empty lines or lines that are just closing span tags
            if not line or line == "</span>" or line.endswith('text-box"><p>'):
                continue

            # Special hadnling for style details
            if "Style tag details" in line:
                in_style = True
            elif "Style tag end." in line:
                in_style = False

            font = ""
            decor = ""
            # Check if table start or end or middle
            temp = line.replace("\n", "")
            if line == "<table>\n":
                table = True
                font = "h0-text"
                text = "<table>"
            elif "</table>" in line:
                text = "</table>"
            elif table:
                font = "h0-text"
                text = temp
            # Only deal with lines that have a style and class, or a 'Style tag details'
            elif (line and "style=" in line and "class=" in line) or in_style:
                try:
                    # Get the style details: color font, heading size, bold, italicised.
                    temp = line.replace("&nbsp;", " ").split('style="')
                    style = previous_style if in_style else temp[1].split(";")

                    # Determine what this content is and process accordingly.
                    # Precompile constants and use direct substring lookups for speed
                    for specific_style in style:
                        if "color:" in specific_style:
                            color = specific_style.partition("color:")[2]
                            continue

                        if "text-decoration:" in specific_style:
                            decor = specific_style.partition("text-decoration:")[2].lstrip()
                            continue

                        if "font-style:" in specific_style:
                            font = f"{font};italic" if font else "italic"
                            continue

                        if "font-weight:" in specific_style:
                            if "bold" in specific_style:
                                font = f"{font};bold" if font else "bold"
                            else:
                                font = f"{font};normal" if font else "normal"
                            continue

                        if "class=" in specific_style:
                            if not font:
                                # faster than split() for short patterns
                                start = specific_style.find('class="') + 7
                                end = specific_style.find('"', start)
                                font = specific_style[start:end][:7]

                            # minimize intermediate objects
                            idx = specific_style.find('-text">')
                            if idx != -1:
                                temp = specific_style[idx + 7 :].replace("</span>", "").replace("<br>\n", "\n\n")
                            else:
                                temp = ""

                            text = line.replace("<br>", "\n") if in_style else "\n\n" if temp == "<p>" else temp
                            continue

                        if specific_style == "is_table":
                            table = True
                            font = "h0-text"
                            continue

                        if ";" in specific_style:
                            # Only do this fallback if style label includes ';'
                            part_idx = line.find('class="h6-text">')
                            if part_idx != -1:
                                text = line[part_idx + 16 :].replace("</span>", "")

                    previous_style = style

                    # Cleanup the text line...possible left over garbage at end.
                    if ":lblend" in text:
                        lblend_pos = text.find('":lblend">')
                        text = text[: lblend_pos + 10]

                    # Handle newline overflow at end
                    if text.endswith("</span><br>\n"):
                        text = text + "\n\n"
                except IndexError:
                    rutroh_error(f"Skipping malformed line: {line}")
                    continue

            # Slightly malformed html...the text has split away from style and class or there simply is no class/style.
            else:
                temp = line.split("</span>")
                # If there is no /span, then this must be text only...no html whatsoever.
                if len(temp) == 1:
                    continue
                text = temp[0]

                if last_item:
                    color = last_item["color"]
                    font = last_item["highlights"]
                else:
                    # Get the color from the next line.
                    if ":lblend" not in line:
                        # If index error, then the style was in previous line.  Just use existing color.
                        with contextlib.suppress(IndexError):
                            color = (
                                html_lines[num + 1]
                                .split('style="')[1]
                                .split(":")[1]
                                .split('"')[0]
                                .replace(";text-decoration", "")
                            )
                    else:
                        color = ""
                    font = "h0-text"
                    # Handle as a list item
                    if text == "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;* ":
                        decor = "list"

            # Check for the end of label flag
            lblend = ":lblend" in line

            # Check if there's a previous element in processed_line_data
            if processed_line_data and not table:
                last_item = processed_line_data[-1]
                # Compare the current color and font with the last one
                if (
                    last_item["color"] == color
                    and last_item["highlights"] == font
                    and last_item["decor"] == decor
                    and not ("<a href=" in text or "<a href=" in last_item["text"])
                    and not table
                ):
                    # If they match, concatenate the text in the processed_line_data list
                    last_item["text"] += text
                    last_item["end"] = lblend

                    # Process next line if this isn't the end.
                    if not lblend:
                        continue
                elif lblend:
                    processed_line_data = _add_line_data(
                        processed_line_data,
                        text,
                        color,
                        font,
                        spacing,
                        lblend,
                        decor,
                        table,
                    )
                    break

                # Reset spacing since we're now adding to an existing line,
                spacing = 0

                # Get out if this is the end of the label.
                if lblend:
                    break

            # If they don't match or it's the first element or the color/font don't match previous...
            # add a new entry to processed_line_data
            processed_line_data = _add_line_data(
                processed_line_data,
                text,
                color,
                font,
                spacing,
                lblend,
                decor,
                table,
            )

            # Close out possible table
            if text == "</table>":
                table = False

        line_num += 1
        lines_to_skip += 1

        # Check if we should continue processing the next line or stop.
        # This is where your requested logic is implemented.
        if not lblend:
            continue_processing = True
            continue
        continue_processing = False

        # Now, add the processed data for this line to the output_lines dictionary
        # We need to restructure the data to match the expected format
        if processed_line_data:
            # Add all of the info to the output
            output_lines[line_num_to_add] = {
                "text": [item["text"] for item in processed_line_data],
                "color": [item["color"] for item in processed_line_data],
                "highlights": [item["highlights"] for item in processed_line_data],
                # Spacing needs to be handled on an element-by-element basis.
                # The 'spacing' key in the outer dict might not be what you need
                # if you have multiple text chunks per line. I'll include it here
                # but you might want to reconsider its placement.
                "spacing": processed_line_data[0]["spacing"],
                "end": [item["end"] for item in processed_line_data],
                "decor": [item["decor"] for item in processed_line_data],
                "table": [item["table"] for item in processed_line_data],
            }
            # Bump our line numbers to point to next line.
            processed_line_data = []
            line_num_to_add += 1

    # End of 'While'...
    # Now, add the last processed data for this line to the output_lines dictionary
    # We need to restructure the data to match the expected format
    if processed_line_data:
        # Add all of the info to the output
        output_lines[line_num_to_add] = {
            "text": [item["text"] for item in processed_line_data],
            "color": [item["color"] for item in processed_line_data],
            "highlights": [item["highlights"] for item in processed_line_data],
            # Spacing needs to be handled on an element-by-element basis.
            # The 'spacing' key in the outer dict might not be what you need
            # if you have multiple text chunks per line. I'll include it here
            # but you might want to reconsider its placement.
            "spacing": processed_line_data[0]["spacing"],
            "end": [item["end"] for item in processed_line_data],
            "decor": [item["decor"] for item in processed_line_data],
            "table": [item["table"] for item in processed_line_data],
        }

    return lines_to_skip


def add_line_data(
    processed_line_data: list,
    text: str,
    color: str,
    font: str,
    spacing: int,
    lblend: bool,
    decor: str,
    table: bool,
) -> None:
    r"""
    Splits a string by newline characters and appends a dictionary for each
    substring to a list.

    This function iterates through a given string, splits it into multiple
    substrings based on newline characters ('\\n'), and for each substring,
    it creates and appends a dictionary with text, color, font, spacing,
    and end-of-label information to a provided list.

    Args:
        processed_line_data (list): The list to which the processed data
                                     dictionaries will be appended.
        text (str): The input string, which may contain newline characters.
        color (str): The color code associated with the text.
        font (str): The font class associated with the text.
        spacing (int): The spacing value for the text.
        lblend (bool): A flag indicating if this is the end of a label.
        decor (str): The text decoration style (e.g., "underline").
        table (bool): A flag indicating if the text is part of a table.

    Return:
        The list with the line(s) added.
    """
    for subtext in text.split("\n"):
        text_to_add = text if text in {"\n", "\n\n"} else subtext
        # if not subtext:
        #     text_to_add = text
        if subtext or text:
            processed_line_data.append(
                {
                    "text": text_to_add,
                    "color": color,
                    "highlights": font,
                    "spacing": spacing,
                    "end": lblend,
                    "decor": decor,
                    "table": table,
                },
            )
        if not subtext:
            break
    return processed_line_data


# Optimized
def handle_gototop(text_list: list) -> list:
    """
    This function handles the addition of a 'Go to top' string in a given text.

    It checks for specific items in the text and replaces the newline character with 'Go to top' followed by a newline.

    Parameters:
        text_list (list): The input text list to be processed.

    Returns:
        text_list (list): The modified text with 'Go to top' added if the conditions are met.
    """
    gototop_items = {"CAVEATS:", "Profile:", "Task:", "Scenes:"}
    gototop = "          Go to top"

    # Check if any of the gototop_items exist in the first element of the list
    if any(item in text_list[0] for item in gototop_items) and "Task: Properties" not in text_list[0]:
        # Replace the last newline character with "Go to top" + newline
        text_list[-1] = text_list[-1].replace("\n", f"{gototop}\n", 1)

    return text_list


def remove_the_html_tags(text: str) -> str:
    """
    Removes HTML tags from the given text.

    Args:
        text (str): The input text containing HTML tags.

    Returns:
        str: The text with HTML tags removed.
    """
    # Just replace the stuff we don't weant to see.
    return (
        text.replace("<span style=", "")
        .replace("<div class=", "")
        .replace("<em>", "")
        .replace("</em>", "")
        .replace("<data-flag=", "")
        .replace("<a href='#'></a>", "")
    )


# Optimized
def cleanup_text_elements(output_lines: dict, line_num: int, remove_html: bool) -> list:
    """
    Cleanup all of the text elements in the line by fixing html and other stuff.

    Args:
        output_lines (list): The dictionary containing the output lines.
        line_num (int): The line number to clean up.
        remove_html (bool): A flag indicating whether to remove HTML tags.

    Returns:
        dict: The updated output_lines dictionary.
    """
    tabs = f"{' ' * 4}"
    text_list = output_lines[line_num]["text"]

    # If nothing, just return.
    if not text_list:
        return output_lines

    # The following allows the unnamed Task hotlinks to work.
    text_list = handle_gototop(text_list)

    # Special handling for 'Task xxx has too many actions'.
    # We don't want to strip the html from the Task name.
    # Catch the '>' break before the &gt;' gets replaced.
    too_many_pos = text_list[0].find("Task <a href=#tasks")
    if too_many_pos != -1:
        # Find the first ">"
        break_pos = text_list[0].find(">")
        if break_pos != -1:
            # Remove everything before the first ">"
            text_list[0] = f"Task {text_list[0][break_pos + 1 :].replace('</a>', '')}"
            remove_html = False
        else:
            rutroh_error(
                f"guimap error: '{text_list[0]}' missing '>' in line {line_num}: {output_lines[line_num]['text']}!",
            )

    # Cleanup all of the text elements.
    new_text_list = [
        text.replace("&nbsp;", " ")
        .replace("\n\n", "\n")
        .replace("<DIV", "")
        .replace("</div>", "")
        .replace("&#45;", "-")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("[Launcher Task:", " [Launcher Task:")
        .replace(" --Task:", "--Task:")
        .replace("<a href='#'>", "")
        .replace("</a>", "")
        .replace("\t", tabs)
        for text in text_list
    ]

    # Handle special situations

    # Remove all the html from the text
    if remove_html:
        new_text_list = [remove_the_html_tags(text) for text in new_text_list]

    if new_text_list:
        output_lines[line_num]["text"] = new_text_list

    return output_lines


# Optimized
def eliminate_blanks(output_lines: dict) -> dict:
    """Eliminate consecutive blank lines from the output.

    Args:
        output_lines (dict): dictionary of output lines

    Returns:
        output_lines (dict): dictionary of output lines
    """
    blank_lines = {"", "    \n"}

    # Create a list of keys *before* starting the loop.

    # We iterate over this fixed list of keys, allowing us to safely modify the original dictionary.
    for key in list(output_lines.keys()):
        # Get the value using the key from the original dictionary
        # NOTE: You must check if the key still exists, as another part of your logic might
        # implicitly handle a key before it gets to this loop, though it's less common here.
        if key not in output_lines:
            continue

        value = output_lines[key]

        try:
            if value["directory"]:
                continue  # Skip directories
        except KeyError:
            pass

        prev_value = None
        new_text_list = []

        # Inner loop for processing the 'text' list (this is fine, it's not the dictionary)
        for item in value["text"]:
            # Assuming 'blank_lines' is defined in the scope (e.g., a set or list of blank line markers)
            if item in blank_lines and prev_value in blank_lines:
                continue
            new_text_list.append(item)
            prev_value = item

        if new_text_list:
            # We are modifying the *value* of the dictionary item, not the size, so this is safe.
            output_lines[key]["text"] = new_text_list
        else:
            # **SAFE REMOVAL:** This is now safe because we are iterating over a copy of the keys.
            output_lines.pop(key)

    return output_lines


def extract_colors(line: str) -> list:
    """
    Extracts the starting positions of all color classes in the given line.

    Args:
        line (str): The line of text to search for color classes.

    Returns:
        list: A list of integers representing the starting positions of all color classes found in the line.
    """
    return [m.start() for m in re.finditer(r'class="([^"]*_color[^"]*)"', line)]


def process_color_string(line: str, color_pos: int) -> tuple:
    """
    Extracts the color string from the given line based on the color position.

    Args:
        line (str): The line containing the color string
        color_pos (int): The starting position of the color string

    Returns:
        tuple: A tuple containing the extracted color string and the split result
    """
    temp = line[color_pos:].split('"')
    if len(temp) > 1:
        return temp[1].split(), temp  # split() splits at white-space (spaces, tabs, newlines)
    return [], temp


def extract_working_text(temp: list) -> str:
    """
    Extracts the working text from the given list of strings.

    Args:
        temp (list): A list of strings containing HTML tags and text.

    Returns:
        str: The extracted working text, with double newlines replaced by single newlines.
    """
    # If this is a hotlink reference, then the text string is a bit more complex to extract.
    # Only if it is not a goto href and there is a 4th element in temp.  Yes, very unique!
    if "<a href=" in temp[2] and "<a href='#'>" not in temp[2] and len(temp) >= 5:
        first_part_end_pos = temp[2].find("<a href")
        first_part = temp[2][1:first_part_end_pos]
        second_par = temp[4]
        return f"{first_part}{second_par}"
    if temp[2].startswith("><h2><span class=") or temp[2].startswith("><span class="):
        return temp[4].replace("\n\n", "\n")
    return temp[2].replace("\n\n", "\n")


def remove_html_spans(working_text: str) -> str:
    """
    Removes HTML spans from the working_text and returns the modified text.

    Parameters:
        - working_text (str): The text containing HTML spans to be processed.

    Returns:
        - str: The working_text with HTML spans removed.
    """
    return re.sub(r"</span.*?>", "", working_text.lstrip(">"))


def extract_highlights(working_text: str, highlight_tags: list) -> list:
    """
    Extracts highlights from the working text based on the provided highlight tags.

    Args:
        working_text (str): The text to extract highlights from
        highlight_tags (list): A list of tags to search for in the working text

    Returns:
        list: A list of strings representing the extracted highlights
    """
    highlights = []
    # Search for highlight in string, and if found, get the highlight object's name and return it.
    for tag, style in highlight_tags.items():
        if tag in working_text:
            tag_name = tag.split(">")[0]
            end_tag = f"</{tag_name[1:]}>"
            work_name = working_text.split(tag)
            highlight_name = work_name[1].split(end_tag)[0]
            highlights.append(f"{style},{highlight_name}")
    return highlights


def process_line(
    output_lines: list,
    line: str,
    line_num: int,
    highlight_tags: list,
) -> list:
    """
    A function to process a line of text, extract colors, working text, and highlights.

    Parameters:
        - output_lines (list): A list containing the processed output lines.
        - line (str): The input line of text to process.
        - line_num (int): The line number corresponding to the input line.
        - highlight_tags (list): A list of highlight tags to be applied to the text.

    Returns:
        - list: The updated output lines list after processing the input line.
    """
    color_list = extract_colors(line)
    _process_color_string = process_color_string
    _extract_working_text = extract_working_text
    _remove_html_spans = remove_html_spans
    _extract_highlights = extract_highlights
    previous_line = ""

    for color_pos in color_list:
        # Break up line into color and text (temp)
        color_to_use, temp = _process_color_string(line, color_pos)

        if color_to_use:
            color = color_to_use[0]
            if "_color" in color:
                # Get the text
                working_text = _extract_working_text(temp)

                # Ignore unique situation in which there is a color and no text.
                if (
                    "...with label:" in working_text and color_to_use[0] != "action_label_color"
                ) and "Anchor" not in working_text:
                    continue

                # Special handling if a Tasker preferencews key.
                if PrimeItems.program_arguments["preferences"] and (
                    "Key Service Account" in temp[2] or "Google Cloud Firebase" in temp[2]
                ):
                    working_text = line.split('preferences_color">')[1]

                # Ignore duplicate lines due to multiple colors and only one text item.
                if working_text == previous_line:
                    continue
                previous_line = working_text
                working_text = _remove_html_spans(working_text)

                # Get the color
                if line_num not in output_lines:
                    output_lines[line_num] = {"color": [], "text": [], "highlights": []}
                output_lines[line_num]["color"].append(color)

                # If this is the first color in the list, then extract highlights.
                if color_pos == color_list[0]:
                    highlights = _extract_highlights(working_text, highlight_tags)
                    if "highlights" in output_lines[line_num]:
                        output_lines[line_num]["highlights"].extend(highlights)
                    else:
                        output_lines[line_num]["highlights"] = highlights

                # Remove HTML tags and replace with spaces
                raw_text = remove_html_tags(working_text, "").replace("<span class=", " ").replace("\n\n", "\n")

                # Indicate a directory header
                if (
                    "Projects..........................." in raw_text
                    or "Profiles..........................." in raw_text
                    or "Tasks..........................." in raw_text
                    or "Scenes..........................." in raw_text
                ):
                    raw_text = f"\nn{raw_text}"

                output_lines[line_num]["text"].append(raw_text)

    return output_lines


def coloring_and_highlights(output_lines: list, line: str, line_num: int) -> list:
    """
    Given a dictionary of output lines, a line of text, and a line number, this function adds color and highlighting
    information to the output lines.

    Args:
        output_lines (dict): A dictionary of output lines, where each line is represented as a dictionary with
        keys "color" and "text".
        line (str): The line of text to process.
        line_num (int): The line number of the line.

    Returns:
        output_lines (dict): The updated output lines dictionary with added color and highlighting information.
    """
    highlight_tags = {
        "<b>": "bold",
        "<em>": "italic",
        "<u>": "underline",
        "<mark>": "mark",
    }
    return process_line(output_lines, line, line_num, highlight_tags)


def calculate_spacing(
    spacing: int,
    output_lines: dict,
    line_num: int,
    doing_global_variables: bool,
) -> int:
    """
    Calculates the spacing for a given line of text in the output lines dictionary.

    Args:
        spacing (int): The initial spacing value.
        output_lines (dict): A dictionary of output lines.
        line_num (int): The line number of the line being processed.
        doing_global_variables (bool): A flag indicating if global variables are being processed.
        previous_line (str): The text of the previous line.

    Returns:
        int: The calculated spacing value.
    """
    text = output_lines[line_num]["text"][0]

    # Direct returns for common conditions
    if doing_global_variables or text.startswith(("Project:", "Scene:")):
        return 0

    if any(keyword in text for keyword in ("Project Global Variables", "Unreferenced Global Variables")):
        return 0

    if text.startswith(("Profile:", "TaskerNet")):
        return 5

    if text.startswith(("Task:", "- Project '", "   The following Tasks in Project ")) or "--Task:" in text[:7]:
        return 7 if text.startswith("   The following Tasks in Project ") else 10

    # General spacing conditions
    if spacing == 61 or (text and text[0].isdigit()):
        return 15

    # Default spacing
    return spacing


def handle_disabled_objects(output_lines: list, line_num: int) -> list:
    """
    Handles disabled objects in the output lines.

    This function checks for the presence of "[⛔ DISABLED]" in the output lines and moves it up to the profile line if found.
    It also blanks out the original line.

    Args:
        output_lines (list): A list of output lines.
        line_num (int): The current line number.

    Returns:
        list: The updated output lines.
    """
    # Find the previous output line in prep for checking disabled.
    prev_line_num = line_num - 1
    keep_going = True
    while keep_going:
        try:
            if output_lines[prev_line_num]:
                keep_going = False
                break
        except KeyError:
            prev_line_num -= 1
            if prev_line_num < 0:
                prev_line_num = 0
                break

    # If [⛔ DISABLED] is in the line for a Profile, then move it up to the profile line and blank out the original.
    if (
        "[⛔ DISABLED]" in output_lines[line_num]["text"][0]
        and output_lines[prev_line_num]["color"] == ["profile_color"]
        and output_lines[prev_line_num]["text"][1] == "\n"
    ):
        output_lines[prev_line_num]["text"][1] = "  [⛔ DISABLED]\n"
        # This blank line will be ignored by guiwins.py output_map_text_lines
        output_lines[line_num]["text"][0] = " "
        output_lines[line_num]["color"] = {}
    return output_lines


def capture_front_text(output_lines: list, line: str, line_num: int) -> list:
    """
    Captures the front text from a given line and updates the output lines with the extracted text and default color.

    Parameters:
        output_lines (list): A list of output lines.
        line (str): The line from which to capture the front text.
        line_num (int): The line number in the output lines.

    Returns:
        list: The updated output lines with the extracted text and default color.
    """
    # Find the color location
    color_location = line.find("<span class=")
    # If we don't have '<span class=', then the _color is part of the text rather than part of our _color.
    if color_location == -1:
        output_lines[line_num]["text"] = [line]
    else:
        output_lines[line_num]["text"] = [line[:color_location]]

    # Assign the last color used as the default color
    for output_line_num in reversed(output_lines):
        if output_lines[output_line_num]["color"]:
            output_lines[line_num]["color"] = [
                output_lines[output_line_num]["color"][-1],
            ]
            break
    return output_lines


def additional_formatting(
    doing_global_variables: bool,
    line: str,
    output_lines: dict,
    line_num: int,
    spacing: int,
    remove_html: bool,
) -> tuple:
    """
    Applies special formatting to a given line of text and appends the formatted line to an output list.

    Args:
        doing_global_variables (bool): Whether or not the line contains global variables.
        line (str): The line of text to be formatted.
        output_lines (dict): The dictionary to which the formatted line will be appended.
        line_num (int): The line number of the line in the output dictionary.
        spacing (int): The number of spaces to be inserted at the beginning of the formatted line.
        last_line (str): The previous line of the output list.
        remove_html (bool): Whether or not to remove HTML tags from the line.

    Returns:
        tuple: output_lines, spacing and whether to ingore the line (True).
    """
    line = pattern8.sub("\n", line)

    # Correct bad class statement
    line = line.replace("class='\\blanktab1\\'", "class='blanktab1'")

    # Correct icons
    line = line.replace("&#9940;", "⛔")
    line = line.replace("&#11013;", "⫷⇦") if "Entry" in line else line.replace("&#11013;", "⇨⫸")

    output_lines[line_num] = {"text": [], "color": [], "highlights": []}

    # Capture any text before the first color tags
    color_location = line.find("_color")
    if color_location != -1 and line.startswith("&nbsp;") and "<span class=" in line:
        output_lines = capture_front_text(output_lines, line, line_num)
        output_lines[line_num]["highlights"] = [""]

    # Build coloring and highlights
    if "<span class=" in line and "_color" in line:
        output_lines = coloring_and_highlights(output_lines, line, line_num)

    # If color is already embedded (TaskerNet description or label)...
    elif '<span style="color:' in line:
        temp1 = line.split('<span style="color:')
        for item in temp1:
            if item and item != "</span>":
                output_lines[line_num]["color"].append(item.split(";text-decoration:")[0])
                # output_lines[line_num]["text"].append(item.split('-text">')[1])
                temp_text = item.split('-text">')[1].replace("Go to top", "")
                output_lines[line_num]["text"] = [remove_html_tags(temp_text, "")]

    # Extract global variable from table definition
    elif line.startswith("<tr><td"):
        temp1 = line.split('text-align:left">')
        global_var_name = temp1[1].split("<")[0]
        temp2 = temp1[2].split("<")
        global_var_value = temp2[0] if temp2[0] else temp2[1][3:]
        output_lines[line_num]["text"] = [
            f"{global_var_name.ljust(25, '.')}{global_var_value.rjust(15, '.')}",
        ]
        output_lines[line_num]["color"] = ["Turquoise"]

    # Just a plain line of text
    # Check top see if we have already added this text, which is the case if '_color' in line but not our '_color'.
    else:
        temp_line = remove_html_tags(line, "")
        if not temp_line.strip():
            return output_lines, spacing, True
        output_lines[line_num]["text"].append(temp_line.replace("Go to top", ""))
        if doing_global_variables:
            spacing = glob_spacing

    # Cleanup the line
    output_lines = cleanup_text_elements(output_lines, line_num, remove_html)
    for text_num, temp in enumerate(output_lines[line_num]["text"]):
        if "...with label:" in temp:
            output_lines[line_num]["text"][text_num] = output_lines[line_num]["text"][text_num].replace(
                "...with label:<div  class=",
                "...with label:",
            )
            break

    # Handle disabled objects
    output_lines = handle_disabled_objects(output_lines, line_num)

    # Determine how much spacing to add to the front of the line.
    spacing = calculate_spacing(
        spacing,
        output_lines,
        line_num,
        doing_global_variables,
    )
    output_lines[line_num]["text"][0] = f"{spacing * ' '}{output_lines[line_num]['text'][0]}"

    return output_lines, spacing, False


def parse_name(input_string: str) -> str:
    """
    Parses out the desired name from the input string by splitting based on '>'.

    Parameters:
        input_string (str): The string to parse.

    Returns:
        str or None: The extracted name if found, else None.
    """
    # Split the string by '>'
    parts = input_string.split(">")

    # Debug: Show the split parts
    # print(f"Split parts: {parts}")

    # Check if there are enough parts to extract the name
    if len(parts) < 3:
        print("Not enough parts to extract the name.")
        return None

    if parts[2] == "</td":
        return parts[1].split("</a")[0]

    # The desired name is after the second '>'
    # Join the remaining parts in case there are multiple '>' in the name
    return ">".join(parts[2:]).strip()


def add_directory_entry(temp: list, output_lines: dict, line_num: int) -> dict:
    """
    Adds a directory entry to the output lines dictionary.

    Args:
        temp (list): A list containing the directory information.
        output_lines (dict): A dictionary containing the output lines.
        line_num (int): The line number.

    Returns:
        output_lines (dict): The updated output lines dictionary.

    """
    # Ignore garbage
    if temp[1] == "</td>\n":
        return output_lines

    # Get the tasker object name and type (projects, profiles, tasks, scenes)
    name = parse_name(temp[1]).replace("</a></td>", "")
    start_pos = temp[1].find("#")
    end_pos = temp[1].find("_", 1)
    tasker_type = temp[1][start_pos + 1 : end_pos]

    # Add the directory entry
    if name is not None:
        output_lines[line_num] = {
            "directory": [tasker_type, name],
            "text": [],
            "color": [],
        }
    return output_lines


def ignore_line(line: str) -> bool:
    """
    Check if a given line of HTML should be ignored.

    Args:
        line (str): The line of HTML to check.

    Returns:
        bool: True if the line should be ignored, False otherwise.
    """
    text_to_ignore = [
        # "<style>",
        "<tr>",
        "<table>",
        "<td></td>",
        "<a id=",
        "Trailing Information...",
        "mark {",
        "background-color: ",
        "{color: ",
        "padding: 5px;",
        "{display: ",
        "></span><!doctype html>\n",
        '<meta charset="UTF-8"><title>MapTasker</title>\n',
    ]
    # Ignore certain lines
    return any(ignore_str in line for ignore_str in text_to_ignore)


# Loop through html and format ourput
def process_html_lines(
    lines: list,
    output_lines: dict,  # Changed to dict for performance
    spacing: int,
    iterate: bool,
) -> dict:  # Return type changed to dict
    """
    Processes HTML lines and adds them to the output_lines dictionary.

    Args:
        lines (list): A list of HTML lines to be processed.
        output_lines (dict): A dictionary to store the processed lines.
        spacing (int): The initial spacing value for formatting.
        iterate (bool): A flag indicating whether to skip the next line.

    Returns:
        dict: The updated output_lines dictionary.
        NOTE: Optimized for performance
    """
    doing_global_variables = False
    remove_html = True
    lines_to_skip = 0

    # Pre-calculate common strings for faster membership checking
    unreferenced_globals = "Unreferenced Global Variables"
    project_globals = "Project Global Variables"
    profile_taskernet = ("Profile:", "TaskerNet")
    task_project = (
        "Task:",
        "- Project '",
        "   The following Tasks in Project ",
    )
    task_project_start = "   The following Tasks in Project "
    # Cache the function references for minor performance gain
    _ignore_line = ignore_line
    _add_directory_entry = add_directory_entry
    _additional_formatting = additional_formatting
    _remove_html_tags = remove_html_tags
    _cleanup_text_elements = cleanup_text_elements
    _handle_disabled_objects = handle_disabled_objects
    _process_label_html = process_label_html

    # --- Start Processing Loop ---
    for line_num, line in enumerate(lines):
        # 1. Handle skipped lines (Label HTML processing)
        if lines_to_skip > 0:
            lines_to_skip -= 1
            if not line.startswith("<div "):
                continue

        # 2. Early exit for common ignored lines
        if _ignore_line(line) and not doing_global_variables:
            continue

        # 3. Handle Directory Entries
        if "<td>" in line:
            # Add directory entry and mark next line for skipping (if part of a multi-line structure)
            output_lines = _add_directory_entry(
                line.split("<td>"),
                output_lines,
                line_num,
            )
            iterate = True
            continue

        # 4. Handle 'iterate' flag (Skip line)
        if iterate:
            iterate = False
            continue

        # 5. Determine the key for the current line's output
        # Using line_num as a key, since lines are processed in order
        insert_key = line_num

        # --- Handle Global Variables Table Start ---
        if line == "<th>Name</th>\n" and line_num + 1 < len(lines) and lines[line_num + 1] == "<th>Value</th>\n":
            output_lines[insert_key] = {
                "text": ["Variable Name...............Variable Value"],
                "color": ["turquoise1"],
                "highlight_color": [],
                "highlights": [],
                "directory": [],
            }
            doing_global_variables = True
            # Set to iterate to skip the next line ("<th>Value</th>\n")
            iterate = True
            continue

        # --- Handle Global Variables Table End ---
        if doing_global_variables and line == "</table><br>\n":
            doing_global_variables = False
            spacing = 0
            continue

        # 6. Pre-processing for the current line
        if "Element of type" in line:
            spacing = 0

        # Check for valid lines in which we don't want to remove the html
        if "!DOCTYPE" in line or "&lt;style&gt;" in line or "&lt;script" in line:
            remove_html = False

        # If we are doing html from a screen WebElement/variable set, provide appropriate spacing.
        if not remove_html:
            # Using tuple-assignment to avoid reassignment warning.
            line = align_text(line, 30)  # noqa: PLW2901

        # 7. Apply additional formatting (The core processing)
        # Only call the heavy function if we don't have the simple TaskerNet/label inline color
        if ";text-decoration:" not in line:
            # additional_formatting will create the dict entry at insert_key
            output_lines, spacing, ignore_the_line = _additional_formatting(
                doing_global_variables,
                line,
                output_lines,
                insert_key,
                spacing,
                remove_html,
            )
            if ignore_the_line:
                continue
        else:
            # Simple case: TaskerNet description or label with embedded color style
            output_lines[insert_key] = {"text": [], "color": [], "highlights": []}
            # The logic to handle this is now moved inline for minor performance gain
            temp1 = line.split('<span style="color:')
            for item in temp1:
                # Get the pertinent info for the output line.
                if item and item != "</span>" and not item.endswith('label:</span><div  class="text-box"><p>'):
                    output_lines[insert_key]["color"].append(item.split(";text-decoration:")[0])
                    temp_text = item.split('-text">')[1].replace("Go to top", "")
                    output_lines[insert_key]["text"] = [_remove_html_tags(temp_text, "")]
            # We still need to cleanup text elements and calculate spacing for this line
            output_lines = _cleanup_text_elements(output_lines, insert_key, remove_html)
            output_lines = _handle_disabled_objects(output_lines, insert_key)

            # Determine how much spacing to add to the front of the line.
            text = output_lines[insert_key]["text"][0]

            # Re-implementing simplified calculate_spacing logic inline
            if (
                doing_global_variables
                or text.startswith(("Project:", "Scene:"))
                or any(keyword in text for keyword in (project_globals, unreferenced_globals))
            ):
                current_spacing = 0
            elif text.startswith(profile_taskernet):
                current_spacing = 5
            elif any(keyword in text for keyword in task_project) or "--Task:" in text[:7]:
                current_spacing = 7 if text.startswith(task_project_start) else 10
            elif spacing == 61 or (text and text[0].isdigit()):
                current_spacing = 15
            else:
                current_spacing = spacing
            spacing = current_spacing

            output_lines[insert_key]["text"][0] = f"{spacing * ' '}{output_lines[insert_key]['text'][0]}"

        # 8. Post-processing
        if "/html" in line or "<div <span" in line:
            remove_html = True

        # Validate and update profile name if missing
        if "Profile:" in line:
            # Use .get() and check the default value for safer access
            current_text = output_lines.get(insert_key, {}).get("text", [""])[0]
            if current_text == "     Profile: \n":
                output_lines[insert_key]["text"][0] = "     Profile: (no name)\n"

        # 9. Handle labels/descriptions with full HTML (the biggest performance impact)
        # Check for 'text-box' but ignore the style class '.text-box'
        if "text-box" in line and ".text-box" not in line:
            # Find the actual key that was last inserted before the 'text-box' line
            # This is necessary because some lines are just skipped.
            # Using the last key of the dictionary is a safe way to find the insertion point.
            if output_lines:
                insert_key = next(reversed(output_lines))
                # See if additional_formatting added junk and remove it if so.
                if output_lines[insert_key]["text"] and output_lines[insert_key]["text"][0] == "     <div class=":
                    del output_lines[insert_key]

            # Go process the html in label/description
            # process_label_html updates output_lines directly
            lines_to_skip = _process_label_html(lines, output_lines, line_num, spacing)
            continue

    return output_lines


# Formats the output HTML by processing each line of the input list.
def format_output(lines: list, output_lines: dict, spacing: int, iterate: bool) -> list:
    r"""
    Formats the output HTML by processing each line of the input list.

    Args:
        lines (list): A list of lines of HTML code.
        output_lines (dict): A list to store the formatted output.
        spacing (int): The amount of spacing to be added before each line.
        iterate (bool): A flag indicating whether to skip the next line.

    Returns:
        list: The formatted output list.

    Description:
        This function processes each line of the input list and applies specific formatting rules.
        It checks if the line is a table definition and appends a formatted string to the output list.
        It ignores lines containing non-text data and applies special formatting rules based on the line content.

        The function returns the formatted output list.

    """

    # Format the lines in the html
    output_lines = process_html_lines(lines, output_lines, spacing, iterate)

    # Eliminate consequtive blank lines and return our dictionary.
    return eliminate_blanks(output_lines)


def parse_html() -> dict:
    r"""
    Parses the HTML file "MapTasker.html" and formats the content into a list of lines.

    Returns:
        output_lines (dict): A dictionary of formatted lines from the parsed HTML file.

        Dictionary structure:
        output_lines[line_num] = {
            "text": [f"{message}\n, messqage2\n, etc."],
            "color": [color1, color2, color3, etc.],
            "highlight_color": [""],
            "highlights": [highlight, string],
        }
    """
    output_lines = {}
    iterate = False

    # Read the mapped html file
    with open("MapTasker.html", encoding="utf8") as html:
        lines = html.readlines()

        # Establish base spacing
        spacing = 0

        # Format the html
        output_lines = format_output(lines, output_lines, spacing, iterate)
        lines = []  # No longer need the lines list.
        html.close()

    return output_lines
