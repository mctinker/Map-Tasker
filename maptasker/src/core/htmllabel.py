"""htmllabel: building the html of one label out of the text segments htmltext parsed.

format_label is what a Task, Action or TaskerNet description goes through on its way to the Map: it keeps the
colours, headings and links, drops the layout, and balances any tag the parsing left open."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from maptasker.src.core.format import format_html
from maptasker.src.core.htmlsafe import embed_html_document, html_document_start, legible_color
from maptasker.src.core.htmltext import contains_html, parse_html_to_text_segments
from maptasker.src.core.sysconst import HOTLINK_STYLE

if TYPE_CHECKING:
    from collections.abc import Mapping


# Segments that are markup rather than words.  parse_html_to_text_segments passes a label's
# own list, table and block tags through as segments of their own, and the loop below wraps
# every segment it is given in a <span> of the label's color.  A tag wrapped that way crosses
# the tags around it -- the <li> ends up inside one span and its </li> inside the next -- so
# these are written as they stand, with the spans left to the words between them.
STRUCTURAL_SEGMENTS = frozenset(
    {
        "<blockquote>",
        "</blockquote>",
        "<big>",
        "</big>",
        "<li>",
        "</li>",
        "<ol>",
        "</ol>",
        "<p>",
        "</p>",
        "<pre>",
        "</pre>",
        "<small>",
        "</small>",
        "<table>",
        "</table>",
        "<tbody>",
        "</tbody>",
        "<td>",
        "</td>",
        "<thead>",
        "</thead>",
        "<tr>",
        "</tr>",
        "<ul>",
        "</ul>",
    },
)


# The markup of those passed-through tags an author can leave open, and which has to be
# closed before the box around the label is -- a description is downloaded from TaskerNet
# and is often sloppy HTML.  Left open, it does not stay in the box.  <small> and <big> are
# formatting elements, which a browser reopens after the block they were left open in, so
# a description with an unclosed <small> drew every line of the Map after it at four-fifths
# the size.  And a <table>, list or <pre> left open swallows the box's own </div>, pulling
# the rest of the Map inside it.  <p> is not here: a paragraph ends where the next block
# starts, and an extra </p> would draw an empty paragraph of its own.
LEFT_OPEN_TAG = re.compile(
    r"<(/?)(big|blockquote|li|ol|pre|small|table|tbody|td|tfoot|th|thead|tr|ul)\b[^>]*>",
    re.IGNORECASE,
)


def close_left_open_tags(label_html: str) -> str:
    """
    The end tags for whatever passed-through markup a formatted label leaves open.

        :param label_html: the label as format_label has built it so far
        :return: the end tags, innermost first, or "" if everything is closed
    """
    still_open: list[str] = []
    for tag in LEFT_OPEN_TAG.finditer(label_html):
        name = tag.group(2).lower()
        if not tag.group(1):
            still_open.append(name)
        elif name in still_open:
            # Closing an element closes everything opened inside it, as the browser does.
            del still_open[len(still_open) - 1 - still_open[::-1].index(name) :]
    return "".join(f"</{name}>" for name in reversed(still_open))


def _segment_css(lbl_style: dict) -> str:
    """
    The inline CSS for the underline, italic, bold and table styles of one label segment.

    Args:
        lbl_style: The styles of the segment, as HTMLTextFormatter recorded them.

    Returns:
        The CSS declarations to put on the span that carries the segment's text.
    """
    css_styles = ";text-decoration: none;"
    if lbl_style.get("is_underline"):
        css_styles += ";text-decoration: underline;"
    if lbl_style.get("is_italic"):
        css_styles += "font-style: italic;"
    if lbl_style.get("is_bold"):
        css_styles += ";font-weight: bold;"
    if lbl_style.get("is_table_cell"):
        css_styles += ";is_table;"
    return css_styles.replace(";;", ";")


def _link_segment(lbl_text: str, lbl_style: dict) -> str:
    """
    A label segment's text, wrapped in an anchor if the segment is a link.

    Style the link explicitly rather than leaving it to the browser's default: the
    anchor is about to be wrapped in a span carrying this segment's color and
    "text-decoration: none", and the Map view's Tailwind reset makes an <a> inherit
    both, which renders the link exactly like the text around it -- see
    sysconst.HOTLINK_STYLE. Same styling the directory and Task warning links use, so
    every hotlink in the output looks the same.

    An external link also opens in a new tab: in the Map view the output is rendered
    inside the running app's own page, so following a TaskerNet link in place would
    navigate away from MapTasker itself. In-page targets (href="#...", e.g. the
    directory's own anchors) deliberately stay in this tab -- that is the whole point
    of them.

    Args:
        lbl_text: The segment's text.
        lbl_style: The styles of the segment, as HTMLTextFormatter recorded them.

    Returns:
        The text, as a link if it is one.
    """
    if not lbl_style.get("is_link", False):
        return lbl_text
    lbl_href = str(lbl_style.get("href"))
    new_tab = "" if lbl_href.startswith("#") else ' target="_blank" rel="noopener noreferrer"'
    return f'<a href="{html.escape(lbl_href, quote=True)}" style="{HOTLINK_STYLE}"{new_tab}>{lbl_text}</a>'


class _LabelBuilder:
    """
    Builds the html of one label out of its parsed segments, one at a time.

    What each segment adds depends on the ones before it -- whether the text box has been
    opened, the heading level last seen, and the last text written -- so that is kept here
    between calls to add().
    """

    def __init__(self, task_label: str, colors: Mapping[str, str], color_to_use: str) -> None:
        """
        Args:
            task_label: The html the label starts with.
            colors: The run's colors by argument name (RunConfig.colors).
            color_to_use: The name of the color the label is written in by default.
        """
        self.task_label = task_label
        self.colors = colors
        self.color_to_use = color_to_use
        self.have_paren = False
        self.previous_heading = 0
        self.previous_text = ""

    def add(self, action_label: dict) -> None:
        """
        Add one parsed segment of the label to the html.

        Args:
            action_label: The segment, as parse_html_to_text_segments returned it.
        """
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
            return

        # Fall back to the label's default color when the label asked for one that would
        # be unreadable on our background (see legible_color), as well as when it asked
        # for none at all.
        lbl_color = legible_color(lbl_style["color"], self.colors[self.color_to_use], self.colors)
        css_styles = _segment_css(lbl_style)
        lbl_text = _link_segment(lbl_text, lbl_style)

        lbl_heading = lbl_style["heading_level"] if lbl_style["is_heading"] else 0
        if lbl_style.get("is_table_cell"):
            lbl_heading = 0

        # If we have back-to-back headings, then force a new line.
        if (lbl_heading > 0 and self.previous_heading > 0) and (lbl_heading != self.previous_heading):
            # Start the next paragraph.  The <p> used to be written inside a <span> of
            # its own, which put a block inside an inline element and left the span with
            # no end tag of its own; a paragraph needs neither, since one <p> ends the
            # one before it.
            self.task_label = self.task_label + "<p>"

        # If we have a color, then format it accordingly.
        if lbl_color:
            self._add_colored(lbl_text, lbl_color, css_styles, lbl_heading, lbl_style)
        # No color
        else:
            self.task_label = self.task_label + f"{'&nbsp;' * lbl_heading}" + lbl_text

    def _add_colored(self, lbl_text: str, lbl_color: str, css_styles: str, lbl_heading: int, lbl_style: dict) -> None:
        """
        Add a segment that has a color: in a span of that color, or as it stands if it is markup.

        Args:
            lbl_text: The segment's text, already wrapped as a link if it is one.
            lbl_color: The color to write it in.
            css_styles: The inline CSS for its underline, italic, bold and table styles.
            lbl_heading: The heading level it is written at, 0 for none.
            lbl_style: The styles of the segment, as HTMLTextFormatter recorded them.
        """
        if not self.have_paren:
            self.task_label = self.task_label + '<div class="text-box"><p>\n'
        # Reset fontsize back to normal if we have a new heading and this is a \n.
        if lbl_text == "\n" and lbl_heading != self.previous_heading:
            self.task_label = self.task_label + "<br><span class='h0-text'>\n</span>"
            self.previous_heading = 0
            return
        # Remove leading newline...causes problems with it there.
        if lbl_text != "\n" and lbl_text.startswith("\n"):
            lbl_text = lbl_text[1:]

        # If we have a new heading, force a break if we didn't just do one and it isn't a table cell.
        if (
            lbl_heading != self.previous_heading
            and self.previous_text not in ("\n", "<br>")
            and self.previous_text != "<br>"
            and not self.task_label.endswith("\n")
            and not lbl_style["is_table_cell"]
        ):
            self.task_label = self.task_label + "<br>"

        # If this is a table, then just output the table details without any heading spaces.
        if lbl_style.get("is_table_cell"):
            # Ignore breaks within table entries.
            if lbl_text == "<br>":
                return
            self.task_label = self.task_label + "\r" + lbl_text
        elif lbl_text.strip() in STRUCTURAL_SEGMENTS:
            # Markup rather than words: in as it stands, outside any span.
            self.task_label = self.task_label + lbl_text
        else:
            # Concatenate all of the text lines with the color.
            # Use the combined css_styles string and data_href_attribute
            self.task_label = (
                self.task_label
                + f'<span style="color:{lbl_color}{css_styles}" class="h{lbl_heading}-text">'
                + lbl_text
                + "</span>"
            )
        self.have_paren = True
        self.previous_heading = lbl_heading
        self.previous_text = lbl_text

    def finish(self) -> str:
        """
        The label's html, with anything the author left open closed off.

        Returns:
            The finished html.
        """
        # Nothing the author left open may outlast the label (see LEFT_OPEN_TAG).
        label = self.task_label + close_left_open_tags(self.task_label)
        if self.have_paren:
            label = label + "</p></div>"
        return label


def format_label(lbl: str, colors: Mapping[str, str]) -> str:
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
        colors: The run's colors by argument name (RunConfig.colors).

    Returns:
        A string containing the HTML-formatted task label.
    """
    color_to_use = "taskernet_color" if "TaskerNet description" in lbl else "action_label_color"

    # A label that is a whole HTML document was laid out by its author -- render it as
    # written rather than flattening it (see embed_html_document).  Split it off here: what
    # comes before it is MapTasker's own lead-in (share.py prefixes descriptions with
    # "TaskerNet description:"), which still goes through the usual formatting below.
    document_html = ""
    document_start = html_document_start(lbl)
    if document_start != -1:
        document_html = embed_html_document(lbl[document_start:])
        lbl = lbl[:document_start]

    # Do this for all labels:  Leave as is for now in case we change it in the future.
    if contains_html(lbl) or lbl:
        builder = _LabelBuilder(
            format_html(
                color_to_use,
                "",
                " ...with label:",
                True,
            ),
            colors,
            color_to_use,
        )

        # Go through the lines in the parsed html, adding each to the label.
        for action_label in parse_html_to_text_segments(lbl):
            builder.add(action_label)
        task_label = builder.finish()

    # No embedded html
    else:
        task_label = format_html(
            color_to_use,
            "",
            f" ...with label: {lbl}",
            True,
        )

    # The author's own document, if there was one, follows the lead-in.
    return task_label + document_html
