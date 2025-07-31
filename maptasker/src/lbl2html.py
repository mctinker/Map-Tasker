"""Convert html to text"""

import html
import re
from html.parser import HTMLParser

from maptasker.src.error import rutroh_error


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
        }
        self.tag_stack = []  # To keep track of active tags and their influence

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

        styles_copy["is_heading"] = is_heading
        if heading_level:
            styles_copy["heading_level"] = heading_level

        # Remove individual heading flags from the final output styles
        styles_copy.pop("is_h1", None)
        styles_copy.pop("is_h2", None)
        styles_copy.pop("is_h3", None)
        styles_copy.pop("is_h4", None)
        styles_copy.pop("is_h5", None)

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
