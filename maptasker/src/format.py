"""Format output lines and html content"""

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
        lmrk = output_line.find("lmrk")
        if lmrk != -1:
            leading_space_count = count_trailing_blanks(output_line, lmrk)
            leading_spaces = space * leading_space_count
            new_line = output_line[: (lmrk - leading_space_count)]
            new_line1 = f"{three_spaces}{leading_spaces}"
            new_line2 = output_line[(lmrk + 4) :]
            output_line = new_line + new_line1 + new_line2
        else:
            break

    # # Format the html...add a number of blanks if some sort of list.
    if "DOCTYPE" in item:  # If imbedded html (e.g. Scene WebElement), add a break and some spacing.
        output_line = pattern15.sub(f"<br>{space * 30}", output_line)

    # Add a carriage return if this is a break: replace("<br>" with "<br>\r"
    output_line = pattern8.sub("<br>\r", output_line)
    # Get rid of trailing blank
    output_line = pattern2.sub("", output_line)  # Get space-commas: " ,"

    # Get rid of extraneous html code (double-/span) that somehow got in to the output
    output_line = pattern9.sub("</span>", output_line)

    # Replace double paragraph with single paragraph
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
        # another span color...only happens 3 out of 20,000 lines. And leaving it in
        # has no adverse impact to the output other than an extra span that is overridden.

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
            "is_underline": False,
            "is_italic": False,
            "is_bold": False,
            "is_link": False,
            "href": None,
            "is_table_cell": False,  # New flag to track if we're in a table cell
        }
        self.tag_stack = []  # To keep track of active tags and their influence
        self.list_indent_level = 0
        self.list_counter = []
        self.list_types = []
        # New attribute to track if we are inside a <pre> tag
        self.is_preformatted = False
        # New attribute to track if we are inside a <style> tag
        self.is_in_style = False
        # Table heading and cell tracking
        self.table_th = False
        self.code_tag = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """
        Processes an opening HTML tag and updates the current formatting state.
        """
        self.tag_stack.append(tag)

        # Handle the <div> tag
        if tag == "div":
            # Add a newline before the content of the div for better separation
            # self._add_segment("\n")
            return

        # Handle the <img> tag
        if tag == "img":
            if len(attrs) > 1:
                string_to_add = f'<img src="{attrs[0][1]}" alt="{attrs[1][1]}" class="image-small"/>'
            else:
                string_to_add = f'<img src="{attrs[0]}" class="image-small"/>'
            self._add_segment(string_to_add)
            # Return to prevent it from being added to the tag stack
            return

        # Handle the <style> tag
        if tag == "style":
            self.is_in_style = True
            return

        # Handle the <pre> tag
        if tag == "pre":
            self.is_preformatted = True
            # Add a newline before the preformatted block for clean formatting
            self._add_segment("<pre>")
            return

        if tag == "br":
            # Insert a newline segment
            self._add_segment("\n")
            return

        if tag == "p":
            # Ignore <p> tags, as they are handled in formatting
            return

        if tag == "font":
            attrs_dict = dict(attrs)
            if "color" in attrs_dict:
                self.current_styles["color"] = attrs_dict["color"].lower()

        # Handle underline tags
        elif tag == "u":
            self.current_styles["is_underline"] = True

        # Handle italic/emphasis tags
        elif tag in ["i", "em"]:
            self.current_styles["is_italic"] = True

        # Handle bold tag
        elif tag in ("b", "strong"):
            self.current_styles["is_bold"] = True

        # Handle anchor (link) tags
        elif tag == "a":
            attrs_dict = dict(attrs)
            if "href" in attrs_dict:
                self.current_styles["is_link"] = True
                self.current_styles["href"] = attrs_dict["href"]

        # Handle list tags
        # tag = "li"
        elif tag == "ul":
            self.list_indent_level += 1
            self.list_types.append("ul")
            self._add_segment("<ul>")  # Add a newline before the list starts
        elif tag == "ol":
            self.list_indent_level += 1
            self.list_types.append("ol")
            self.list_counter.append(0)
            self._add_segment("<ol>")  # Add a newline before the list starts
        elif tag == "li":
            leading_spaces = " " * count_trailing_blanks(self.rawdata, self.offset)
            indent = "  " * (self.list_indent_level - 1)
            self._add_segment(f"{indent}{leading_spaces}<li>")

        # New: Handle table tags
        elif tag == "table":
            self.current_styles["is_table_cell"] = True
            self._add_segment("<table>")
        elif tag == "thead":
            self._add_segment("<thead>")
        elif tag == "tr":
            self._add_segment("<tr>")
        elif tag == "th":
            self.table_th = True
        elif tag == "td":
            self._add_segment("<td>")
        elif tag == "big":
            self._add_segment("<big>")
        elif tag == "small":
            self._add_segment("<small>")

        elif tag == "code":
            self.code_tag = True

        # Handle new heading tags
        elif tag == "h1":
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
        elif tag == "title":
            end_title = self.rawdata.find("</title>", self.offset)
            if end_title != -1:
                self._add_segment("Title: ")
        elif tag == "legend":
            end_legend = self.rawdata.find("</legend>", self.offset)
            if end_legend != -1:
                self.current_styles["is_italic"] = True
        elif tag == "figcaption":
            end_caption = self.rawdata.find("</figcaption>", self.offset)
            if end_caption != -1:
                self.current_styles["is_italic"] = True
        elif tag == "hr":
            self._add_segment("<hr>")

        # Tags to ignore
        elif tag in ("tbody", "body", "html", "fieldset", "meta", "head", "figure"):
            return
        # Unrecognized tag
        else:
            self.handle_unknown_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        """
        Processes a closing HTML tag and reverts the formatting state.
        """
        # Handle the </div> tag
        if tag == "div":
            # Add a newline after the div's content
            self._add_segment("\n")
            if self.tag_stack and self.tag_stack[-1] == tag:
                self.tag_stack.pop()
            return

        # Handle the </style> tag
        if tag == "style":
            self.is_in_style = False
            if self.tag_stack and self.tag_stack[-1] == tag:
                self.tag_stack.pop()
                self._add_segment("......Style tag end.<br>")
            return

        # Handle the </pre> tag
        if tag == "pre":
            self.is_preformatted = False
            # Add a newline after the preformatted block
            self._add_segment("</pre>")
            if self.tag_stack and self.tag_stack[-1] == tag:
                self.tag_stack.pop()
            return

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

        # Revert underline tag
        elif tag == "u":
            self.current_styles["is_underline"] = False

        # Revert italic/emphasis tags
        elif tag in ["i", "em"]:
            self.current_styles["is_italic"] = False

        # Revert bold tag
        elif tag in ("b", "strong"):
            self.current_styles["is_bold"] = False

        # Revert anchor tags
        elif tag == "a":
            self.current_styles["is_link"] = False
            self.current_styles["href"] = None

        # Revert list tags
        elif tag in {"ul", "ol"}:
            if self.list_indent_level > 0:
                self.list_indent_level -= 1
            if self.list_types:
                self.list_types.pop()
            if tag == "ul":
                self._add_segment("</ul>")
            else:
                self._add_segment("</ol>")
        elif tag == "li":
            self._add_segment("</li>")

        elif tag == "code":
            self.code_tag = False

        # New: Revert table tags
        elif tag == "table":
            # self._add_segment("\n" + "=" * 40 + "\n")  # End of table visual indicator
            self._add_segment("</table>")
            self.current_styles["is_table_cell"] = False
        elif tag == "thead":
            self._add_segment("</thead>")
        elif tag == "tr":
            self._add_segment("</tr>")
        elif tag == "th":
            self.table_th = False
        elif tag == "td":
            self._add_segment("</td>")

        # Revert new heading tags
        elif tag == "h1":
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
        elif tag == "big":
            self._add_segment("</big>")
        elif tag == "small":
            self._add_segment("</small>")
        # End tags to ignore
        elif tag in (
            "br",
            "h",
            "img",
            "tbody",
            "head",
            "body",
            "html",
            "fieldset",
            "meta",
            "title",
            "legend",
            "figure",
            "figcaption",
            "p",
        ):
            return
        # Unrecognized tag
        else:
            self.handle_unknown_endtag(tag)

    def handle_data(self, data: str) -> None:
        """
        Processes character data (plain text) and adds it as a formatted segment.
        """
        # If we are inside a style tag, ignore the data
        if self.is_in_style:
            self._add_segment(f"<br>Style tag details......{data}")
            return

        # If we are in a preformatted block, handle the data separately
        if self.is_preformatted:
            self._add_preformatted_segment(data)
        elif data.strip():
            decoded_data = html.unescape(data)
            if self.table_th:
                decoded_data = "<th>" + decoded_data + "</th>"
                self.table_th = False
            elif self.code_tag:
                decoded_data = "<code>" + decoded_data + "</code>"
                self.table_td = False
            self._add_segment(decoded_data)

    def handle_unknown_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """
        Called when the parser finds a start tag that is not recognized by the
        other methods. Prints a message for debugging.
        """
        rutroh_error(f"DEBUG: Unrecognized start tag found: <{tag}>")
        self.handle_data(f"HTML start tag '{tag}' not yet mapped")

    def handle_unknown_endtag(self, tag: str) -> None:
        """
        Called when the parser finds an end tag that is not recognized by the
        other methods. Prints a message for debugging.
        """
        rutroh_error(f"DEBUG: Unrecognized end tag found: </{tag}>")
        self.handle_data(f"HTML end tag '/{tag}' not yet mapped")

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
        # if self.is_in_style:
        #     self.formatted_segments.append({"text": text})
        #     return

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

    def _add_preformatted_segment(self, text: str) -> None:
        """
        Adds a text segment for preformatted text, preserving newlines.
        """
        # We need to preserve all whitespace and newlines, so we don't
        # strip the text and we don't convert newlines to breaks.
        styles_copy = self.current_styles.copy()
        # Indicate that this is a preformatted segment
        styles_copy["is_preformatted"] = True
        styles_copy["is_heading"] = False
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

    # The parser will ignore '\n'.  Use '<br>', and the parser will convert it back to '\n'.
    parser.feed(html_string.replace("\n", "<br>"))
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

    This function first checks if the input `lbl` or 'TaskerNet description' contains HTML.
    - If it does, the HTML content is parsed into segments, and each segment's
      text, color, and heading level, etc. are used to construct a new HTML string.
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
    color_to_use = "taskernet_color" if "TaskerNet description" in lbl else "action_label_color"

    # Do this for all labels:  Leave as is for now in case we change it in the future.
    if contains_html(lbl) or lbl:
        task_label = format_html(
            color_to_use,
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

            # Convert newlines to breaks
            if lbl_text == "\n":
                lbl_text = "<br>"

            # Handle situation in which a "\n" preceeds a name. The \n screws up the html
            if lbl_text.startswith("\n%"):
                lbl_text = lbl_text[1:]

            # Get the label details for this item in them label.  If no 'styles', then ignore the line
            try:
                lbl_style = action_label["styles"]
            except KeyError:
                continue

            # Get link details
            lbl_color = lbl_style["color"] if lbl_style["color"] else PrimeItems.colors_to_use[color_to_use]
            lbl_link = lbl_style.get("is_link", False)
            lbl_href = lbl_style.get("href", None)

            # Create CSS for underline, italic, and bold styles
            css_styles = ";text-decoration: none;"
            if lbl_style.get("is_underline"):
                css_styles += ";text-decoration: underline;"
            if lbl_style.get("is_italic"):
                css_styles += "font-style: italic;"
            if lbl_style.get("is_bold"):
                css_styles += ";font-weight: bold;"
            if lbl_style.get("is_table_cell"):
                css_styles += ";is_table;"
            # Add default link styling if is_link is True. The text-decoration is already handled by the underline check.
            if lbl_link:
                lbl_text = f'<a href="{lbl_href}">{lbl_text}</a>'

            css_styles = css_styles.replace(";;", ";")

            lbl_heading = lbl_style["heading_level"] if lbl_style["is_heading"] else 0
            if lbl_style.get("is_table_cell"):
                lbl_heading = 0

            # If we have back-to-back headings, then force a new line.
            if (lbl_heading > 0 and previous_heading > 0) and (lbl_heading != previous_heading):
                # Concatenate a newline.
                task_label = (
                    task_label
                    + '<span style="color:'
                    + lbl_color
                    + css_styles
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

                # If we have a new heading, force a break if we didn't just do one and it isn't a table cell.
                if (
                    lbl_heading != previous_heading
                    and previous_text not in ("\n", "<br>")
                    and previous_text != "<br>"
                    and not task_label.endswith("\n")
                    and not lbl_style["is_table_cell"]
                ):
                    task_label = task_label + "<br>"

                # If this is a table, then just output the table details without any heading spaces.
                if lbl_style.get("is_table_cell"):
                    # Ignore breaks within table entries.
                    if lbl_text == "<br>":
                        continue
                    task_label = task_label + "\r" + f"{lbl_text}{label_end}"
                else:
                    # Concatenate all of the text lines with the color.
                    # Use the combined css_styles string and data_href_attribute
                    task_label = (
                        task_label
                        + f'<span style="color:{lbl_color}{css_styles}" class="h{lbl_heading}-text">'
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
            color_to_use,
            "",
            f" ...with label: {lbl}",
            True,
        )

    return task_label


def count_trailing_blanks(text_string: str, position: int) -> int:
    """
    Counts the number of blank spaces in a string, starting at the character
    before the specified position and working backward until a non-blank
    character is found.

    Args:
        text_string: The input string.
        position: The integer position to start counting from (exclusive).

    Returns:
        The total number of blank spaces found.
    """
    # Input validation
    if not isinstance(text_string, str):
        return "Error: The first argument must be a string."
    if not isinstance(position, int) or position < 0 or position > len(text_string):
        return "Error: The second argument must be a valid integer position within the string."

    blank_count = 0
    # Start the loop from the character just before the given position
    # The range function works like this: range(start, stop, step)
    for i in range(position - 1, -1, -1):
        # Check if the character is a space
        if text_string[i] == " ":
            blank_count += 1
        else:
            # We found a non-blank character, so we stop counting
            break

    return blank_count
