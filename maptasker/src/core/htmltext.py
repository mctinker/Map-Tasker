"""htmltext: flattening HTML to the text segments a label is built from.

HTMLTextFormatter walks a document and records each run of text with the colour, weight and heading level in
effect; parse_html_to_text_segments and contains_html are the entry points.  htmllabel turns the segments
back into the html of one label."""

from __future__ import annotations

import html
import html.entities
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING, ClassVar

from maptasker.src.core.error import rutroh_error
from maptasker.src.core.htmlsafe import VOID_ELEMENTS, escaped_text, image_source, safe_url
from maptasker.src.core.htmlstyle import (
    DIV_INDENT,
    MAX_INDENT_LEVELS,
    NEWLINE_AFTER_BLOCK_TAG,
    NEWLINE_BEFORE_BLOCK_TAG,
    parse_stylesheet,
    selector_matches,
)
from maptasker.src.core.mapwriter import count_trailing_blanks
from maptasker.src.core.sysconst import logger

if TYPE_CHECKING:
    from collections.abc import Callable


"""Convert html to text"""
# The styles an inline "style=" attribute can turn on or off, and which therefore have to be
# put back the way they were when the element carrying them closes (see HTMLTextFormatter).
INLINE_STYLE_KEYS = ("color", "is_bold", "is_italic", "is_underline")


# CSS font-weight values that mean bold.  The numeric weights are the ones at or above
# 600 -- CSS treats those as bold, and Tasker's own label editor writes "font-weight: 700"
# rather than the keyword.
BOLD_FONT_WEIGHTS = {"bold", "bolder", "600", "700", "800", "900"}


# Color values that name no color of their own.  "transparent" in particular has to be
# dropped rather than honored: the fashionable way to draw a gradient headline is to paint
# the text with a clipped background image and set "color: transparent" so the real color
# doesn't cover it.  We can't reproduce the gradient, so obeying the color would render
# the headline invisible.  Falling back to the label's default color keeps it readable.
UNRENDERABLE_COLORS = {"transparent", "inherit", "currentcolor", "initial", "unset", "revert", "auto", "none"}


# What would let a value written into our own style="..." attribute get out of it: close the
# attribute, open a tag, or begin another declaration.
STYLE_ESCAPE_CHARACTERS = ('"', "<", ">", ";")


# Tags whose own handlers already set and clear the styles they imply (see handle_endtag).
# Leaving them off the style stack keeps one mechanism in charge of each style, rather than
# having the stack restore a value the tag's own end-tag handler is about to overwrite.
SELF_MANAGED_STYLE_TAGS = {"b", "em", "font", "i", "strong", "u"}


# How the tags HTMLTextFormatter knows about are handled, as tables so that handle_starttag
# and handle_endtag stay a lookup rather than a ladder of one branch per tag.
#
# Tags that do nothing but switch one style on at the start tag and off again at the end tag.
STYLE_FLAG_TAGS = {
    "u": "is_underline",
    "i": "is_italic",
    "em": "is_italic",
    "b": "is_bold",
    "bold": "is_bold",  # not HTML, but authors write it, and mean <b>
    "strong": "is_bold",
    "h1": "is_h1",
    "h2": "is_h2",
    "h3": "is_h3",
    "h4": "is_h4",
    "h5": "is_h5",
    "h6": "is_h6",
}


# Tags passed straight through to the output rather than turned into styling of their own.
# <blockquote> and the definition list (<dl>, <dt>, <dd>), like the list and table tags, are
# block-level containers whose whole job -- setting the quoted run off from the text around it --
# is the browser's to do when it renders the output.  <br> is the one that becomes a newline, and a <p> is only marked: the paragraph
# break itself is handled in formatting.  <hr> has no end tag of its own to close.
START_TAG_SEGMENTS = {
    "br": "\n",
    "p": "<p>",
    "hr": "<hr>",
    "thead": "<thead>",
    "tr": "<tr>",
    "td": "<td>",
    "big": "<big>",
    "small": "<small>",
    "sub": "<sub>",
    "sup": "<sup>",
    "blockquote": "<blockquote>",
    "dl": "<dl>",
    "dt": "<dt>",
    "dd": "<dd>",
}


END_TAG_SEGMENTS = {
    "li": "</li>",
    "thead": "</thead>",
    "tr": "</tr>",
    "td": "</td>",
    "big": "</big>",
    "small": "</small>",
    "sub": "</sub>",
    "sup": "</sup>",
    "blockquote": "</blockquote>",
    "dl": "</dl>",
    "dt": "</dt>",
    "dd": "</dd>",
}


# Tags with nothing to contribute of their own.  <span> lands here because it is purely a
# carrier for the "style=" attribute applied in handle_starttag and taken back off in
# handle_endtag.
TAGS_WITH_NO_START_ACTION = {"tbody", "body", "html", "fieldset", "meta", "head", "figure", "span"}


TAGS_WITH_NO_END_ACTION = {
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
    "span",
}


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
        # The open elements as (tag, classes, id), innermost last, for matching the rules of
        # any <style> the description carries against the element currently being opened.
        self.element_stack = []
        # Every rule collected so far, in source order, as (specificity, selector,
        # declarations) -- see parse_stylesheet.
        self.stylesheet = []
        # The text of the <style> element being read, which arrives in as many pieces as the
        # parser cares to hand over and is only parseable once all of it is in.
        self.style_text = []
        # (tag, styles-before) for every open element carrying an inline style, innermost
        # last.  Elements nest, so a closing tag has to put back exactly what the element it
        # belongs to changed rather than reset to the defaults -- otherwise an inner <span>
        # wipes the styling the <div> around it is still applying to the text that follows.
        self.style_stack = []
        # How deeply nested in <div>/<section> elements we currently are, for indenting.
        self.div_depth = 0
        # Whether the next segment starts a line.  True at the outset: there is nothing to
        # be after yet.  Keeps block boundaries from stacking up blank lines, and marks
        # where an indent belongs.
        self.at_line_start = True
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
        # A void element has no end tag, so an entry here would never come off again -- and a
        # stale entry on top is one the next real end tag fails to match, which leaves that
        # tag unpopped too and walks the stack steadily out of step with the document.  <img>
        # in particular was pushed and then returned past, despite the comment below saying
        # it wasn't.
        if tag not in VOID_ELEMENTS:
            self.tag_stack.append(tag)

        # Put this element on the stack of open elements before any styling is worked out:
        # a stylesheet's selectors are matched against the element itself and the ones it
        # sits inside, so it has to be there to be selected.
        self._push_element(tag, attrs)

        # Fold in whatever this element's "style=" attribute says before dealing with the
        # tag itself, so the styling covers everything the element contains -- and record
        # what to put back when it closes.  Modern HTML carries nearly all of its formatting
        # this way (<div style="...">, <span style="...">) rather than in <font>/<b>/<i>.
        self._push_inline_styles(tag, attrs)

        if tag in START_TAG_SEGMENTS:
            self._add_segment(START_TAG_SEGMENTS[tag])
        elif tag in STYLE_FLAG_TAGS:
            self.current_styles[STYLE_FLAG_TAGS[tag]] = True
        elif tag in self.START_HANDLERS:
            self.START_HANDLERS[tag](self, tag, attrs)
        elif tag not in TAGS_WITH_NO_START_ACTION:
            self.handle_unknown_starttag(tag, attrs)

    def _start_block(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """
        Handle the <div> and <section> tags.  Both are block-level containers: their own
        contribution is to start their contents on a fresh line, indented one level deeper
        than the element they sit in.  Any styling they carry was applied in handle_starttag
        and is taken back off by the matching end tag.
        """
        self.div_depth += 1
        self._start_new_line()

    def _start_image(self, _tag: str, attrs: list[tuple[str, str]]) -> None:
        """
        Handle the <img> tag.

        Look the attributes up by name rather than by position.  attrs is a list of
        (name, value) pairs, and taking them positionally got both cases wrong: an
        <img> carrying only a src (no alt -- which is how TaskerNet descriptions embed
        YouTube thumbnails) fell into a branch that interpolated the whole ('src', url)
        tuple as the URL, and one whose attributes came in another order, or which
        carried a width/class as well, took whatever happened to be second as its alt
        text.  A mangled src is not merely wrong in the page: the browser reads it as a
        relative URL and requests it, which is where the "/popout/('src', 'https://...')
        not found" console messages came from.
        """
        attributes = dict(attrs)
        source = image_source(attributes.get("src") or "")
        # Nothing useful to render without a source, and emitting the tag anyway would
        # send the browser off after another bogus relative URL.
        if not source:
            logger.warning(f"Ignoring <img> with no usable src attribute: {attrs}")
            return
        # Escape both values into the tag being built rather than dropping them in as
        # written.  A src or alt carrying a double quote closed its attribute early, and
        # what followed was read as further attributes -- which for a src means the
        # browser is handed a truncated URL and the image simply does not appear.  The
        # same goes for a bare "&", which an unescaped URL is full of.
        alt_text = attributes.get("alt")
        alt_attribute = f' alt="{html.escape(alt_text, quote=True)}"' if alt_text else ""
        # "referrerpolicy=no-referrer" asks the browser not to say where the request came
        # from.  An image host that turns down hotlinking decides that on the referrer,
        # and what it would be told here -- a "localhost:<port>" page, or a "file://" one
        # for the saved output -- is exactly the sort it turns down, which shows up as a
        # broken-image icon for a URL that loads perfectly well on its own.  Nothing is
        # lost by withholding it: these are someone else's images on someone else's host.
        self._add_segment(
            f'<img src="{html.escape(source, quote=True)}"{alt_attribute} '
            f'referrerpolicy="no-referrer" class="image-small"/>',
        )

    def _start_style(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <style> tag: what follows is a stylesheet, not text."""
        self.is_in_style = True

    def _start_pre(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <pre> tag, adding the opening tag for clean formatting."""
        self.is_preformatted = True
        self._add_segment("<pre>")

    def _start_font(self, _tag: str, attrs: list[tuple[str, str]]) -> None:
        """Handle the <font> tag, taking its color if it has one and it is one that stays in its attribute."""
        attrs_dict = dict(attrs)
        color = (attrs_dict.get("color") or "").lower()
        # Written into a style="..." attribute of our own (see _LabelBuilder.add), so a value that
        # could close that attribute, or start another declaration, is not a color.
        if color and not any(character in color for character in STYLE_ESCAPE_CHARACTERS):
            self.current_styles["color"] = color

    def _start_link(self, _tag: str, attrs: list[tuple[str, str]]) -> None:
        """Handle the <a> tag.  An anchor without an href, or with one that is not safe to follow, is not a link."""
        href = safe_url(dict(attrs).get("href") or "")
        if href:
            self.current_styles["is_link"] = True
            self.current_styles["href"] = href

    def _start_list(self, tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <ul> and <ol> tags, which open a list one level deeper."""
        self.list_indent_level += 1
        self.list_types.append(tag)
        if tag == "ol":
            self.list_counter.append(0)
        self._add_segment(f"<{tag}>")

    def _start_list_item(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <li> tag, indenting it to the depth of its list."""
        leading_spaces = " " * count_trailing_blanks(self.rawdata, self.offset)
        indent = "  " * (self.list_indent_level - 1)
        self._add_segment(f"{indent}{leading_spaces}<li>")

    def _start_table(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <table> tag."""
        self.current_styles["is_table_cell"] = True
        self._add_segment("<table>")

    def _start_table_heading(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <th> tag: the next piece of text is the heading's."""
        self.table_th = True

    def _start_code(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <code> tag: the next piece of text is the code."""
        self.code_tag = True

    def _start_title(self, _tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <title> tag, labeling its text -- but only if the tag is ever closed."""
        if self.rawdata.find("</title>", self.offset) != -1:
            self._add_segment("Title: ")

    def _start_italic_caption(self, tag: str, _attrs: list[tuple[str, str]]) -> None:
        """Handle the <legend> and <figcaption> tags: italic text, but only if the tag is ever closed."""
        if self.rawdata.find(f"</{tag}>", self.offset) != -1:
            self.current_styles["is_italic"] = True

    def handle_endtag(self, tag: str) -> None:
        """
        Processes a closing HTML tag and reverts the formatting state.
        """
        # Take this element's inline styling back off.  First thing done, so it still
        # happens for the tags that return early below.
        self._pop_inline_styles(tag)
        self._pop_element(tag)

        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

        if tag in END_TAG_SEGMENTS:
            self._add_segment(END_TAG_SEGMENTS[tag])
        elif tag in STYLE_FLAG_TAGS:
            self.current_styles[STYLE_FLAG_TAGS[tag]] = False
        elif tag in self.END_HANDLERS:
            self.END_HANDLERS[tag](self, tag)
        elif tag not in TAGS_WITH_NO_END_ACTION:
            self.handle_unknown_endtag(tag)

    def _end_block(self, _tag: str) -> None:
        """
        Handle the </div> and </section> tags: end the content with a line of its own, and
        step the indent back out to the level of whatever contains it.
        """
        self._start_new_line()
        self.div_depth = max(self.div_depth - 1, 0)

    def _end_style(self, _tag: str) -> None:
        """
        Handle the </style> tag.  The rules gathered up are now complete, so work out what
        they select and add them to the ones in force for the rest of the description.
        Nothing is emitted: a stylesheet is instructions for drawing the text, not text.
        """
        self.is_in_style = False
        self.stylesheet.extend(parse_stylesheet("".join(self.style_text)))
        self.style_text = []

    def _end_pre(self, _tag: str) -> None:
        """Handle the </pre> tag, closing the preformatted block."""
        self.is_preformatted = False
        self._add_segment("</pre>")

    def _end_font(self, _tag: str) -> None:
        """Handle the </font> tag.  The color is cleared whether or not another <font> is still open."""
        self.current_styles["color"] = None

    def _end_link(self, _tag: str) -> None:
        """Handle the </a> tag."""
        self.current_styles["is_link"] = False
        self.current_styles["href"] = None

    def _end_list(self, tag: str) -> None:
        """Handle the </ul> and </ol> tags, which close a list."""
        if self.list_indent_level > 0:
            self.list_indent_level -= 1
        if self.list_types:
            self.list_types.pop()
        self._add_segment(f"</{tag}>")

    def _end_table(self, _tag: str) -> None:
        """Handle the </table> tag."""
        self._add_segment("</table>")
        self.current_styles["is_table_cell"] = False

    def _end_table_heading(self, _tag: str) -> None:
        """Handle the </th> tag."""
        self.table_th = False

    def _end_code(self, _tag: str) -> None:
        """Handle the </code> tag."""
        self.code_tag = False

    def handle_data(self, data: str) -> None:
        """
        Processes character data (plain text) and adds it as a formatted segment.
        """
        # Inside a <style>, this is the stylesheet rather than anything to show.  Save it up
        # for </style> to parse -- CDATA content can arrive in several pieces, and a rule
        # split across two of them is only readable once they are back together.
        if self.is_in_style:
            self.style_text.append(data)
            return

        # If we are in a preformatted block, handle the data separately
        if self.is_preformatted:
            self._add_preformatted_segment(data)
        elif data.strip():
            # The parser has already turned character references into the characters they stand
            # for, so "&lt;b&gt;" arrives here as "<b>": text, which has to stay text when it is
            # written into the page (see escaped_text).
            decoded_data = escaped_text(data)
            if self.table_th:
                decoded_data = "<th>" + decoded_data + "</th>"
                self.table_th = False
            elif self.code_tag:
                decoded_data = "<code>" + decoded_data + "</code>"
                self.table_td = False
            self._add_segment(decoded_data)

    def handle_unknown_starttag(self, tag: str, _attrs: list[tuple[str, str]]) -> None:
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
        self._add_segment(escaped_text(html.entities.html5.get(name, f"&{name};")))

    def handle_charref(self, name: str) -> None:
        """
        Handle numeric character references (e.g., {).
        """
        try:
            char_code = int(name[1:], 16) if name.startswith("x") else int(name)
            self._add_segment(escaped_text(chr(char_code)))
        except ValueError:
            self._add_segment(f"&#{name};")

    def _push_inline_styles(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """
        Apply an element's inline "style=" attribute, remembering what to restore when it closes.

        Every element that can close gets an entry, whether or not it carries a style: the
        entries are matched by tag name on the way out, so an unstyled </div> that left no
        entry of its own would otherwise find, and wrongly restore, the entry belonging to a
        styled <div> further out.

            :param tag: the element's tag name
            :param attrs: the element's attributes as parsed
        """
        # A void element never closes, so an entry for it would sit on the stack forever --
        # and the tags that manage their own styles keep doing so (see SELF_MANAGED_STYLE_TAGS).
        if tag in VOID_ELEMENTS or tag in SELF_MANAGED_STYLE_TAGS:
            return

        self.style_stack.append((tag, {key: self.current_styles[key] for key in INLINE_STYLE_KEYS}))

        # The description's own stylesheet first, weakest rule to strongest, then the
        # element's "style=" attribute -- which is how CSS ranks them, an inline style
        # outranking any rule that merely selected the element.
        for declarations in self._matched_declarations():
            self._apply_inline_style(declarations)

        style = dict(attrs).get("style", "")
        if style:
            self._apply_inline_style(style)

    def _push_element(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """
        Note an element as open, with the class and id a selector might reach it by.

        Void elements are left off: they contain nothing, so nothing is ever inside them for
        a descendant selector to find, and there is no end tag to take them off again.

            :param tag: the element's tag name
            :param attrs: the element's attributes as parsed
        """
        if tag in VOID_ELEMENTS:
            return
        attributes = dict(attrs)
        classes = frozenset((attributes.get("class") or "").split())
        element_id = (attributes.get("id") or "").strip() or None
        self.element_stack.append((tag, classes, element_id))

    def _pop_element(self, tag: str) -> None:
        """
        Close an element, along with anything still open inside it.

        The same tolerance _pop_inline_styles needs, for the same reason: descriptions leave
        tags unclosed, and an entry left behind would go on selecting text that is no longer
        inside it.

            :param tag: tag name of the element being closed
        """
        for index in range(len(self.element_stack) - 1, -1, -1):
            if self.element_stack[index][0] == tag:
                del self.element_stack[index:]
                return

    def _matched_declarations(self) -> list[str]:
        """
        The declaration blocks of every rule selecting the innermost open element.

        Ordered the way the cascade resolves them -- least specific first, and source order
        breaking a tie -- so that applying them in turn leaves the winning rule's value in
        place, without any of them having to know what the others said.

            :return: the matching declaration blocks, weakest first
        """
        if not self.stylesheet:
            return []
        matched = [
            (specificity, order, declarations)
            for order, (specificity, selector, declarations) in enumerate(self.stylesheet)
            if selector_matches(selector, self.element_stack)
        ]
        matched.sort(key=lambda rule: (rule[0], rule[1]))
        return [declarations for _, _, declarations in matched]

    def _pop_inline_styles(self, tag: str) -> None:
        """
        Restore the styles that were in force before the element being closed opened.

        Real-world HTML does not always close what it opens, so search down for the entry
        this end tag belongs to rather than assuming it is on top.  Everything above it was
        left open inside the element and closes with it, whatever the markup says -- dropping
        those entries stops them being matched later by some unrelated end tag.  An end tag
        with no entry at all (a stray </span>, of which a label's own html may hold a few)
        changed nothing, so there is nothing to put back.

            :param tag: tag name of the element being closed
        """
        for index in range(len(self.style_stack) - 1, -1, -1):
            if self.style_stack[index][0] == tag:
                self.current_styles.update(self.style_stack[index][1])
                del self.style_stack[index:]
                return

    def _start_new_line(self) -> None:
        """
        Begin a new line for a block-level boundary, without stacking up blank lines.

        A layout built out of nested <div>s closes several of them in a row, and opens
        several more, with no text in between.  A newline per boundary would turn every one
        of those into a blank line -- so only break the line if something is actually on it.
        """
        if not self.at_line_start:
            self._add_segment("\n")

    def _current_indent(self) -> str:
        """The indent for text at the current <div> nesting depth (see DIV_INDENT)."""
        return DIV_INDENT * min(self.div_depth, MAX_INDENT_LEVELS)

    def _apply_inline_style(self, style: str) -> None:
        """
        Fold a block of CSS declarations into the current styles.

        Used for an element's inline "style=" attribute and for the body of a rule out of the
        description's own <style> (see _matched_declarations) -- by the time either gets here
        it is the same thing, a list of declarations to apply to the text being read.

        Only the four properties this formatter can actually represent are read (see
        INLINE_STYLE_KEYS); everything else in the declaration -- font sizes, margins,
        backgrounds -- has no equivalent in a text segment and is passed over.  Properties
        are applied rather than merely turned on, so "font-weight: normal" inside a bold
        run correctly un-bolds it for the length of the element.

            :param style: the declarations, e.g. "color: #ff0000; font-weight: bold"
        """
        for declaration in style.split(";"):
            prop, _, value = declaration.partition(":")
            prop = prop.strip().lower()
            value = value.strip().lower()
            if not prop or not value:
                continue

            # The color goes on to be written into a style="..." attribute of our own (see
            # format_label).  No color contains a quote or an angle bracket, so a value that
            # does is one trying to get out of that attribute, and is dropped.
            if any(character in value for character in STYLE_ESCAPE_CHARACTERS[:3]):
                continue

            if prop == "color":
                # A value naming no usable color leaves the text on the label's default
                # color rather than an unpaintable one (see UNRENDERABLE_COLORS).
                self.current_styles["color"] = None if value in UNRENDERABLE_COLORS else value
            elif prop == "font-weight":
                self.current_styles["is_bold"] = value in BOLD_FONT_WEIGHTS
            elif prop == "font-style":
                self.current_styles["is_italic"] = value in ("italic", "oblique")
            # "text-decoration" is the shorthand ("underline solid red"), so match on the
            # word rather than the whole value.
            elif prop in ("text-decoration", "text-decoration-line"):
                self.current_styles["is_underline"] = "underline" in value

    def _add_segment(self, text: str) -> None:
        """
        Adds a text segment with the current styles to the list.
        """
        # Indent whatever lands first on a line to the depth of the <div>s around it.  Done
        # here, at the point text is actually emitted, rather than when a <div> opens: a
        # layout opens several <div>s before any of them has content, and indenting each
        # opening would add up the levels instead of standing at the innermost one.
        if self.at_line_start and text and not text.startswith("\n"):
            text = self._current_indent() + text
        if text:
            self.at_line_start = text.endswith("\n")

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
        self.formatted_segments.append({"text": escaped_text(text), "styles": styles_copy})

    def get_formatted_text(self) -> list[dict]:
        """
        Returns the list of formatted text segments.
        """
        return self.formatted_segments

    # The tags that need more than a flag or a fixed segment, each with the method that deals
    # with it.  Defined last because they name the methods above.
    START_HANDLERS: ClassVar[dict[str, Callable[..., None]]] = {
        "div": _start_block,
        "section": _start_block,
        "img": _start_image,
        "style": _start_style,
        "pre": _start_pre,
        "font": _start_font,
        "a": _start_link,
        "ul": _start_list,
        "ol": _start_list,
        "li": _start_list_item,
        "table": _start_table,
        "th": _start_table_heading,
        "code": _start_code,
        "title": _start_title,
        "legend": _start_italic_caption,
        "figcaption": _start_italic_caption,
    }
    END_HANDLERS: ClassVar[dict[str, Callable[..., None]]] = {
        "div": _end_block,
        "section": _end_block,
        "style": _end_style,
        "pre": _end_pre,
        "font": _end_font,
        "a": _end_link,
        "ul": _end_list,
        "ol": _end_list,
        "table": _end_table,
        "th": _end_table_heading,
        "code": _end_code,
    }


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

    # Drop the newlines that are only pretty-printing the markup before the conversion
    # below turns newlines into breaks.  A hierarchical layout is written one tag per
    # indented line, and every one of those line endings sits next to a tag that lays out
    # its own break -- turning them all into <br> as well is what buries such a label in
    # blank lines.  A newline in among actual text is content and is left alone.
    html_string = NEWLINE_AFTER_BLOCK_TAG.sub(r"\1", html_string)
    html_string = NEWLINE_BEFORE_BLOCK_TAG.sub("", html_string)

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

    def handle_starttag(self, _tag: str, _attrs: str) -> None:
        """Called when an opening tag is encountered."""
        self.found_html_tags = True

    def handle_endtag(self, _tag: str) -> None:
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
        parser.close()  # Parses whatever feed() left buffered.
    except AssertionError:
        # HTMLParser's only complaint about its input: a malformed '<!' declaration or
        # marked section.  Something that resembles HTML but isn't well-formed still
        # counts, for the purpose of "contains HTML".
        return True

    return parser.found_html_tags
