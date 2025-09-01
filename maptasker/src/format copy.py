#! /usr/bin/env python3
"""Text formatter."""
#                                                                                      #
# format: Various formatting functions,                                                #
#                                                                                      #

import html
import re
from html.parser import HTMLParser

from maptasker.src.error import rutroh_error
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import pattern2, pattern8, pattern9, pattern10, pattern15


# Given a line in the output queue, reformat it before writing to file
def format_line(item: str) -> str:
    """
    Given a line in our list of output lines, do some additional formatting
    to clean it up
        :param item: the specific text to reformat from the list of output lines
        :return: the reformatted text line for output
    """
    space = "&nbsp;"
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
        # Handle list markers: ordered and unordered.  Just blank-out the leading lmrk.
        if "lmrk" in output_line:
            output_line = replace_second_and_subsequent(output_line, "lmrk", "<br>").replace("lmrk", "")

    # Not an 'Action:'. No changes needed
    else:
        output_line = item

    # # Format the html...add a number of blanks if some sort of list.
    if "DOCTYPE" in item:  # If imbedded html (e.g. Scene WebElement), add a break and some spacing.
        output_line = pattern15.sub(f"<br>{space * 30}", output_line)

    # Add a carriage return if this is a break: replace("<br>" with "<br>\r"
    output_line = pattern8.sub("<br>\r", output_line)
    # Get rid of trailing blank
    output_line = pattern2.sub("", output_line)  # Get space-commas: " ,"

    # Get rid of extraneous html code that somehow got in to the output
    output_line = pattern9.sub("</span>", output_line)

    return pattern10.sub("</p>", output_line)


def replace_second_and_subsequent(main_string: str, old_substring: str, new_substring: str) -> str:
    """
    Replaces the second and subsequent occurrences of a substring in a string.

    Args:
        main_string (str): The original string to modify.
        old_substring (str): The substring to be replaced.
        new_substring (str): The new substring to use as a replacement.

    Returns:
        str: The modified string with replacements made.
    """
    # Find the starting index of the first occurrence.
    # We use `main_string.find()` because it returns -1 if the substring isn't found,
    # and it's a good way to get the index of the first match.
    first_occurrence_index = main_string.find(old_substring)

    # If the substring is not found or it's the only occurrence,
    # return the original string unchanged.
    if first_occurrence_index == -1:
        return main_string

    # Slice the string into three parts:
    # 1. The part before the first occurrence (which we keep).
    # 2. The first occurrence itself (which we also keep).
    # 3. The rest of the string after the first occurrence (where we will make replacements).

    part_before = main_string[: first_occurrence_index + len(old_substring)]
    part_after = main_string[first_occurrence_index + len(old_substring) :]

    # Use the `replace()` method on the `part_after` string.
    # This will replace all occurrences of `old_substring` within that segment.
    modified_part_after = part_after.replace(old_substring, new_substring)

    # Combine the parts back together to form the final result.
    return part_before + modified_part_after


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
        # another span color...only happens 3 out of 20,000 lines. And leaving it in
        # has no adverse impact to the output other than an extra span that is overridden.
        # text_after = text_after.replace(f'<span class="{color_code}"><span', "<span")

        # Set up the trailing HTML to include
        trailing_span = "</span>" if end_span else ""
        return f'{text_before}<span class="{color_code}">{text_after}{trailing_span}'

    # No text after...just return it.
    return text_after


"""Convert html to text"""


class HTMLTextFormatter(HTMLParser):
    """
    A custom HTML parser that extracts text content along with
    associated formatting (like color and heading status) into a
    list of structured text segments.
    """

    def __init__(self) -> None:
        """Initialize the formatter"""
        super().__init__()
        self.formatted_segments = []  # Stores (text, {'color': color, 'is_heading': bool})
        self.current_styles = {
            "color": None,
            "is_h1": False,
            "is_h2": False,
            "is_h3": False,
            "is_h4": False,
            "is_h5": False,
            "is_h6": False,
            "is_underline": False,  # NEW: Add underline style
        }
        self.tag_stack = []  # To keep track of active tags and their influence
        self.list_indent_level = 0
        self.list_counter = []
        self.list_types = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """
        Processes an opening HTML tag and updates the current formatting state.
        """
        self.tag_stack.append(tag)

        if tag == "br":
            # Insert a newline segment
            self._add_segment("\n")
            return

        if tag == "font":
            attrs_dict = dict(attrs)
            if "color" in attrs_dict:
                self.current_styles["color"] = attrs_dict["color"].lower()

        # NEW: Handle underline tags
        elif tag == "u":
            self.current_styles["is_underline"] = True

        # Handle list tags
        # tag = "li"
        elif tag == "ul":
            self.list_indent_level += 1
            self.list_types.append("ul")
            self._add_segment("\n")  # Add a newline before the list starts
        elif tag == "ol":
            self.list_indent_level += 1
            self.list_types.append("ol")
            self.list_counter.append(0)
            self._add_segment("\n")  # Add a newline before the list starts
        elif tag == "li":
            indent = "  " * (self.list_indent_level - 1)
            list_marker = ""
            if self.list_types and self.list_types[-1] == "ul":
                list_marker = "lmrk* "
            elif self.list_types and self.list_types[-1] == "ol":
                self.list_counter[-1] += 1
                list_marker = f"lmrk{self.list_counter[-1]}. "

            self._add_segment(f"\n{indent}{list_marker}")

        # Handle new heading tags
        if tag == "h1":
            self.current_styles["is_h1"] = True
        elif tag == "h2":
            self.current_styles["is_h2"] = True
        elif tag == "h3":
            self.current_styles["is_h3"] = True
        elif tag == "h4":
            self.current_styles["is_h4"] = True
        elif tag == "h5":
            self.current_styles["is_h5"] = True
        elif tag == "h6":
            self.current_styles["is_h6"] = True

    def handle_endtag(self, tag: str) -> None:
        """
        Processes a closing HTML tag and reverts the formatting state.
        """
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

        if tag == "font":
            # Find the last 'font' tag in the stack to determine the previous color
            # or reset if no other font tag is active.
            found_font = False
            for t_in_stack in reversed(self.tag_stack):
                if t_in_stack == "font":
                    found_font = True
                    self.current_styles["color"] = None
                    break
            if not found_font:
                self.current_styles["color"] = None

        # NEW: Revert underline tag
        elif tag == "u":
            self.current_styles["is_underline"] = False

        # Revert list tags
        if tag in {"ul", "ol"}:
            if self.list_indent_level > 0:
                self.list_indent_level -= 1
            if self.list_types:
                self.list_types.pop()
            if tag == "ol" and self.list_counter:
                self.list_counter.pop()

        # Revert new heading tags
        if tag == "h1":
            self.current_styles["is_h1"] = False
        elif tag == "h2":
            self.current_styles["is_h2"] = False
        elif tag == "h3":
            self.current_styles["is_h3"] = False
        elif tag == "h4":
            self.current_styles["is_h4"] = False
        elif tag == "h5":
            self.current_styles["is_h5"] = False
        elif tag == "h6":
            self.current_styles["is_h6"] = False

    def handle_data(self, data: str) -> None:
        """
        Processes character data (plain text) and adds it as a formatted segment.
        """
        if data.strip():
            decoded_data = html.unescape(data)
            self._add_segment(decoded_data)

    def handle_entityref(self, name: str) -> None:
        """
        Handle character entity references (e.g., &).
        """
        self._add_segment(html.entities.html5.get(name, f"&{name};"))

    def handle_charref(self, name: str) -> None:
        """
        Handle numeric character references (e.g., {).
        """
        try:
            char_code = int(name[1:], 16) if name.startswith("x") else int(name)
            self._add_segment(chr(char_code))
        except ValueError:
            self._add_segment(f"&#{name};")

    def _add_segment(self, text: str) -> None:
        """
        Adds a text segment with the current styles to the list.
        """
        styles_copy = self.current_styles.copy()

        # Determine if it's a heading and which level
        is_heading = False
        heading_level = None

        if styles_copy["is_h1"]:
            is_heading = True
            heading_level = 1
        elif styles_copy["is_h2"]:
            is_heading = True
            heading_level = 2
        elif styles_copy["is_h3"]:
            is_heading = True
            heading_level = 3
        elif styles_copy["is_h4"]:
            is_heading = True
            heading_level = 4
        elif styles_copy["is_h5"]:
            is_heading = True
            heading_level = 5
        elif styles_copy["is_h6"]:
            is_heading = True
            heading_level = 6

        styles_copy["is_heading"] = is_heading
        if heading_level:
            styles_copy["heading_level"] = heading_level

        # Remove individual heading flags from the final output styles
        styles_copy.pop("is_h1", None)
        styles_copy.pop("is_h2", None)
        styles_copy.pop("is_h3", None)
        styles_copy.pop("is_h4", None)
        styles_copy.pop("is_h5", None)
        styles_copy.pop("is_h6", None)

        self.formatted_segments.append({"text": text, "styles": styles_copy})

    def get_formatted_text(self) -> list[dict]:
        """
        Returns the list of formatted text segments.
        """
        return self.formatted_segments


def parse_html_to_text_segments(html_string: str) -> list[dict]:
    """
    Parses an HTML string and converts it into a list of text segments,
    each with associated style information (color, heading status).

    Args:
        html_string: The input HTML string.

    Returns:
        A list of dictionaries, where each dictionary has:
        - 'text': The extracted text string.
        - 'styles': A dictionary containing styling information, e.g.,
                    {'color': 'yellow', 'is_heading': True, 'heading_level': 3}.
    """
    parser = HTMLTextFormatter()
    parser.feed(html_string)
    return parser.get_formatted_text()


class HTMLTagDetector(HTMLParser):
    """
    A simple HTML parser designed to detect the presence of any HTML tags.
    """

    def __init__(self) -> None:
        """Initialize html detector"""
        super().__init__()
        self.found_html_tags = False

    def handle_starttag(self, tag: str, attrs: str) -> None:
        """Called when an opening tag is encountered."""
        self.found_html_tags = True

    def handle_endtag(self, tag: str) -> None:
        """Called when a closing tag is encountered."""
        self.found_html_tags = True

    def reset_detector(self) -> None:
        """Resets the detector for reuse."""
        self.found_html_tags = False


def contains_html(text_string: str) -> bool:
    """
    Determines if a given text string contains HTML.

    This function attempts to parse the string as HTML. If any HTML
    start or end tags are found during parsing, it indicates the presence
    of HTML.

    Args:
        text_string: The string to check for HTML content.

    Returns:
        True if the string contains HTML, False otherwise.
    """
    if not isinstance(text_string, str):
        rutroh_error("Input must be a string.")

    # A quick initial check using regex for common HTML tag patterns.
    # This can catch simple cases quickly without full parsing overhead.
    # This regex looks for:
    # < followed by one or more word characters (for the tag name)
    # optionally followed by any characters (for attributes)
    # followed by >
    if re.search(r"<[a-zA-Z][^>]*>", text_string):
        return True

    # For more robust detection, especially for malformed HTML or entities,
    # we use the HTML parser.
    parser = HTMLTagDetector()
    try:
        parser.feed(text_string)
    except Exception:  # noqa: BLE001
        # If parsing itself throws an error, it's likely malformed HTML
        # or something that resembles HTML but isn't well-formed.
        # For the purpose of "contains HTML", we can assume it does.
        return True
    finally:
        parser.close()  # Ensure resources are released

    return parser.found_html_tags


def format_label(lbl: str) -> str:
    """
    Formats a given label string, potentially containing HTML, into an HTML-formatted
    task label with specific styling based on its content.

    This function first checks if the input `lbl` contains HTML.
    - If it does, the HTML content is parsed into segments, and each segment's
      text, color, and heading level are used to construct a new HTML string.
      Text within headings will have an indentation based on the heading level.
      Line breaks within the parsed HTML are skipped. Special characters like
      '[' and ']' are replaced with '{' and '}' respectively.
    - If the input `lbl` does not contain HTML, it is directly embedded into
      a simple HTML paragraph with default styling.

    The primary goal is to take a potentially rich text label and convert it
    into a consistently styled HTML output suitable for display in an application.

    Args:
        lbl: The input label string, which may or may not contain HTML.

    Returns:
        A string containing the HTML-formatted task label.
    """
    blank = "&nbsp;"

    # Only process labels with html here.
    if contains_html(lbl):
        task_label = format_html(
            "action_label_color",
            "",
            " ...with label:",
            True,
        )

        # Parse the HTML string
        formatted_lbl = parse_html_to_text_segments(lbl)
        num_items = len(formatted_lbl)

        # Go through each item in the formatted list and break it into html.
        have_paren = False
        previous_heading = 0
        previous_text = ""

        # Go through the lines in this formatted html
        for num, action_label in enumerate(formatted_lbl):
            # Add end-of-label flag as a commented flag to the last piece of the label.
            label_end = '<data-flag=":lblend">' if num + 1 == num_items else ""

            # Get the label verbage
            lbl_text = action_label["text"].replace("[", "{").replace("]", "}")

            # Handle situation in which a "\n" preceeds a name. The \n screws up the html
            if lbl_text.startswith("\n%"):
                lbl_text = lbl_text[1:]

            # Get the label details for this item in them label.
            lbl_style = action_label["styles"]
            lbl_color = lbl_style["color"] if lbl_style["color"] else PrimeItems.colors_to_use["action_label_color"]
            lbl_underline = (
                ";text-decoration: underline;" if lbl_style.get("is_underline") else ";text-decoration: none;"
            )

            # lbl_heading = (lbl_style["heading_level"] * 2) if lbl_style["is_heading"] else 0
            lbl_heading = lbl_style["heading_level"] if lbl_style["is_heading"] else 0

            # If we have back-to-back headings, then force a new line.
            if (lbl_heading > 0 and previous_heading > 0) and (lbl_heading != previous_heading):
                # Concatenate a newline.
                task_label = (
                    task_label
                    + '<span style="color:'
                    + lbl_color
                    + lbl_underline
                    + '" class="h0-text">'
                    + "<p>"
                    + "</span>"
                )
            # If we have a color, then format it accordingly.
            if lbl_color:
                if not have_paren:
                    task_label = task_label + '<div class="text-box"><p>\n'
                # Reset fontsize back to normal if we have a new heading and this is a \n.
                if lbl_text == "\n" and lbl_heading != previous_heading:
                    lbl_text = " "
                    lbl_heading = 0
                    task_label = task_label + "<br><span class='h0-text'>\n</span>"
                    previous_heading = 0
                    continue
                # Remove leading newline...causes problems with it there.
                if lbl_text != "\n" and lbl_text.startswith("\n"):
                    lbl_text = lbl_text[1:]

                # If we have a new heading, force a break if we didn't just do one.
                if lbl_heading != previous_heading and previous_text != "\n" and not task_label.endswith("\n"):
                    task_label = task_label + "<br>"

                # Concatenate all of the text lines with the color.
                task_label = (
                    task_label
                    + '<span style="color:'
                    + lbl_color
                    + lbl_underline
                    + f'" class="h{lbl_heading}-text">'
                    + f"{lbl_text}{label_end}"
                    + "</span>"
                )
                have_paren = True
                previous_heading = lbl_heading
                previous_text = lbl_text

            # No color
            else:
                task_label = task_label + f"{blank * lbl_heading}" + f"{lbl_text}{label_end}"
        if have_paren:
            task_label = task_label + "</p></div>"

    # No embedded html
    else:
        task_label = format_html(
            "action_label_color",
            "",
            f" ...with label: {lbl}",
            True,
        )

    return task_label
