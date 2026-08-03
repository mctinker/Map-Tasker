"""Format output lines and html content"""

import html
import re
from html.parser import HTMLParser
from itertools import zip_longest

from PIL import ImageColor

from maptasker.src.error import rutroh_error
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import HOTLINK_STYLE, logger, pattern2, pattern8, pattern9, pattern10, pattern15


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
        _count_trailing_blanks = count_trailing_blanks
        lmrk = output_line.find("lmrk")
        if lmrk != -1:
            leading_space_count = _count_trailing_blanks(output_line, lmrk)
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


# Wrap a label (e.g. "Task:", "Profile:", "Project:") with a fast-appearing CSS tooltip.
def build_tooltip_span(label: str, tooltip_lines: list[str]) -> str:
    """
    Wrap a label in a <span class="hover-tooltip" data-tooltip="..."> so hovering over it shows
    a tooltip. This uses a custom CSS tooltip (see add_css()) rather than the native "title"
    attribute, since browsers impose a multi-second delay before showing native tooltips that
    can't be shortened via HTML/CSS.

        :param label: the literal text to wrap (e.g. "Task:")
        :param tooltip_lines: lines of plain text to join (newline-separated) into the tooltip.
            Falsy lines are dropped. If the resulting list is empty, the label is returned unwrapped.
        :return: the label wrapped in a <span class="hover-tooltip" data-tooltip="..."> tag,
            or the bare label if no tooltip lines
    """
    lines = [line for line in tooltip_lines if line]
    if not lines:
        return label

    # Use the "&#10;" entity rather than a raw newline so the tag doesn't get split
    # across multiple lines when the output is later read back in line-by-line
    # (e.g. by guimap.py's Map-view parser). Browsers resolve the entity back to a
    # real line break for the CSS "white-space: pre" tooltip in add_css().
    tooltip_text = "&#10;".join(html.escape(line) for line in lines)
    return f'<span class="hover-tooltip" data-tooltip="{tooltip_text}">{label}</span>'


# Build monospace-aligned, two-column lines (e.g. Profiles next to Tasks) for build_tooltip_span().
def build_two_column_tooltip_lines(
    left_header: str,
    left_items: list[str],
    right_header: str,
    right_items: list[str],
) -> list[str]:
    """
    Lay out two lists side by side, one item per line, as plain-text lines suitable for
    build_tooltip_span(). Relies on the tooltip being rendered in a monospace font
    (see the ".hover-tooltip" CSS rule in add_css()) so the columns actually line up.

        :param left_header: header for the left column (e.g. "Profiles:")
        :param left_items: left column's items, one per line
        :param right_header: header for the right column (e.g. "Tasks (sorted):")
        :param right_items: right column's items, one per line
        :return: list of pre-formatted two-column lines, or [] if both columns are empty
    """
    if not left_items and not right_items:
        return []

    col_width = max([len(left_header), *(len(item) for item in left_items)]) + 3
    lines = [f"{left_header:<{col_width}}{right_header}"]
    lines.extend(f"{left:<{col_width}}{right}" for left, right in zip_longest(left_items, right_items, fillvalue=""))
    return lines


# Make a color setting safe to hand to a browser (or to Pillow) as CSS.
def css_color(color: str) -> str:
    """
    Normalize a color the way CSS wants it.

    The colors in colrmode are mostly names ("Lavender", "Magenta"), but the dark mode's
    background is written as bare hex -- "222623", no "#".  CSS does not accept that: a
    browser drops the whole declaration, which is why the generated file's dark background
    silently comes out white.  Put the "#" back; leave names and anything else alone.

        :param color: a color as configured, e.g. "Lavender", "222623", "#0096ff"
        :return: the same color in a form CSS accepts
    """
    if not color:
        return ""
    color = color.strip()
    if BARE_HEX_COLOR.fullmatch(color):
        return f"#{color}"
    return color


"""Pass an authored HTML document through, rather than flattening it to text"""

# What marks a label as a whole HTML document of its own -- written and laid out by its
# author, not a line of text with a little markup in it.  Those get passed through with
# their styling intact (see embed_html_document); everything else is flattened to text
# segments as before.
HTML_DOCUMENT_MARKER = re.compile(r"<!doctype\s+html|<html[\s>]|<body[\s>]", re.IGNORECASE)

# The document's <body>, whose contents are what actually gets rendered.
BODY_ELEMENT = re.compile(r"<body([^>]*)>(.*)</body>", re.IGNORECASE | re.DOTALL)
STYLE_ATTRIBUTE = re.compile(r"""\bstyle\s*=\s*("([^"]*)"|'([^']*)')""", re.IGNORECASE)

# Elements dropped along with everything inside them.  A shared TaskerNet description is
# downloaded from the internet and is no more trustworthy than any other web page, so the
# things that would let one run code, phone home, or collect input do not come through.
DROPPED_ELEMENTS = {
    "base",
    "button",
    "embed",
    "form",
    "iframe",
    "input",
    "link",
    "math",
    "meta",
    "noscript",
    "object",
    "script",
    "select",
    "style",
    "svg",
    "template",
    "textarea",
    "title",
}

# Elements kept.  Anything not listed and not dropped above is unwrapped -- its tags go, its
# text stays -- so an unfamiliar tag costs its styling, never its content.
ALLOWED_ELEMENTS = {
    "a", "article", "aside", "b", "big", "blockquote", "br", "code", "dd", "div", "dl", "dt", "em", "figcaption",
    "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "i", "img", "li", "main", "mark", "nav",
    "ol", "p", "pre", "section", "small", "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th",
    "thead", "tr", "u", "ul",
}  # fmt: skip

# Attributes kept on those elements.  Deliberately excludes every "on*" handler, and "id"
# and "class", which would collide with the ids and classes of the output around it.
ALLOWED_ATTRIBUTES = {"align", "alt", "colspan", "height", "href", "rowspan", "span", "src", "style", "title", "width"}

# URL schemes a passed-through link or image may use.
ALLOWED_URL_SCHEMES = ("http:", "https:", "mailto:", "#", "/", "./", "../")

# CSS that reaches outside the declaration it sits in -- fetching a resource, or (in museum
# pieces of a browser) running script.  Any declaration containing one is dropped.
UNSAFE_CSS = re.compile(r"url\s*\(|expression\s*\(|javascript:|@import|behavior\s*:", re.IGNORECASE)

# A run of whitespace, which outside a <pre> is worth exactly one space (see handle_data).
WHITESPACE_RUN = re.compile(r"\s+")

# Text colors for a passed-through document that never states one, picked to be readable on
# whatever background it does state (see embed_html_document).
LIGHT_TEXT = "#e8e8ea"
DARK_TEXT = "#101014"


# Resolve a CSS color to RGB, coping with the forms Pillow won't take.
def _color_to_rgb(color: str) -> tuple[int, int, int]:
    """
    Turn a CSS color into an (R, G, B) triple, raising ValueError if it isn't one.

    Pillow's ImageColor handles the hex, rgb() and named forms; rgba() it refuses, so drop
    the alpha and hand it the rgb() underneath.  Alpha would matter to how the color looks,
    but not enough to be worth compositing it against the background for a legibility check.

        :param color: a CSS color, e.g. "#0096ff", "white", "rgb(0, 150, 255)"
        :return: the color as an (R, G, B) triple
    """
    color = css_color(color)
    if color.lower().startswith("rgba(") and color.endswith(")"):
        components = [component.strip() for component in color[5:-1].split(",")]
        if len(components) == 4:
            color = f"rgb({', '.join(components[:3])})"
    return ImageColor.getrgb(color)[:3]


# The WCAG relative luminance of a color, used to compare two colors' contrast.
def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """
    Relative luminance of an 8-bit RGB color, 0.0 (black) to 1.0 (white).

    The WCAG definition: undo the sRGB gamma encoding on each channel, then weight the
    three by how much the eye takes them in -- green far more than red, red more than blue.

        :param rgb: the color as an (R, G, B) triple
        :return: relative luminance between 0.0 and 1.0
    """
    linear = [
        channel / 12.92 if (channel := value / 255) <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        for value in rgb
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


# How far apart two colors are, as the WCAG contrast ratio.
def contrast_ratio(color: str, background: str) -> float | None:
    """
    The WCAG contrast ratio between two CSS colors: 1.0 for identical, 21.0 for black on white.

        :param color: the text color
        :param background: the color it is being drawn on
        :return: the contrast ratio, or None if either color can't be resolved
    """
    try:
        text_luminance = _relative_luminance(_color_to_rgb(color))
        background_luminance = _relative_luminance(_color_to_rgb(background))
    except (ValueError, AttributeError, TypeError):
        # Not something we can reason about -- an unknown color name, a gradient, a variable
        # reference.  The caller treats that as "leave the author's color alone".
        return None
    lighter = max(text_luminance, background_luminance)
    darker = min(text_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


# Swap out a color that would be unreadable on our background for the default.
def legible_color(color: str | None, default_color: str) -> str:
    """
    The color to actually draw a label's text in.

    A label carries whatever colors its author wrote for their own background, which is not
    ours -- see MINIMUM_CONTRAST_RATIO.  Anything that would come out unreadable against the
    output's background falls back to the label's default color, which the user chose and
    can see.  Colors that can't be resolved, and the default color itself, are left alone:
    guessing at an unknown color is worse than showing it, and the default is the user's own
    setting rather than something the label asked for.

        :param color: the color the label asked for, if any
        :param default_color: the label's default color, used when there is nothing better
        :return: the color to use
    """
    if not color:
        return default_color

    background = PrimeItems.colors_to_use.get("background_color", "") if PrimeItems.colors_to_use else ""
    if not background:
        return color

    ratio = contrast_ratio(color, background)
    if ratio is not None and ratio < MINIMUM_CONTRAST_RATIO:
        logger.debug(f"format: dropping unreadable label color {color} on {background} (contrast {ratio:.2f}).")
        return default_color
    return color


def safe_url(url: str) -> str:
    """
    An href/src value if its scheme is one we allow, otherwise empty.

        :param url: the URL as written in the document
        :return: the URL, or "" if it isn't one we will pass through
    """
    cleaned = url.strip().replace("\n", "").replace("\t", "")
    if cleaned.lower().startswith(ALLOWED_URL_SCHEMES) or not cleaned.startswith(("javascript:", "data:", "vbscript:")):
        # Relative URLs (no scheme at all) are fine; a scheme we don't know is not.
        if ":" in cleaned.split("/")[0] and not cleaned.lower().startswith(ALLOWED_URL_SCHEMES):
            return ""
        return cleaned
    return ""


def safe_style(style: str) -> str:
    """
    An inline style with any declaration that reaches outside itself removed.

    The styling is the whole point of passing a document through, so this keeps everything
    it can: only the declarations matching UNSAFE_CSS -- the ones that fetch a resource or,
    historically, run script -- are dropped, and the rest of the attribute survives intact.

        :param style: the raw style attribute
        :return: the style attribute with unsafe declarations removed
    """
    kept = [
        declaration.strip()
        for declaration in style.split(";")
        if declaration.strip() and not UNSAFE_CSS.search(declaration)
    ]
    return "; ".join(kept)


class HTMLDocumentSanitizer(HTMLParser):
    """
    Rebuilds an authored HTML document keeping its structure and styling, minus anything
    that could act on its own behalf.

    An allowlist rather than a blocklist: elements and attributes are dropped unless they
    are known to be inert.  Elements that are merely unrecognized are unwrapped instead of
    removed, so unfamiliar markup loses its formatting but never its words.
    """

    def __init__(self) -> None:
        """Initialize the sanitizer."""
        super().__init__()
        self.parts = []
        # Depth of nesting inside a dropped element, whose content goes with it.
        self.dropped_depth = 0
        # Tags left open, so the result can be closed off properly however ragged the input.
        self.open_tags = []
        # Depth of nesting inside <pre>, where whitespace is content rather than layout.
        self.preformatted_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """Emit an allowed tag with its safe attributes; drop or unwrap anything else."""
        if tag in DROPPED_ELEMENTS:
            if tag not in VOID_ELEMENTS:
                self.dropped_depth += 1
            return
        if self.dropped_depth or tag not in ALLOWED_ELEMENTS:
            return

        attributes = self._safe_attributes(attrs)
        if tag in VOID_ELEMENTS:
            self.parts.append(f"<{tag}{attributes}>")
        else:
            if tag == "pre":
                self.preformatted_depth += 1
            self.open_tags.append(tag)
            self.parts.append(f"<{tag}{attributes}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        """A self-closing tag opens and closes in one go, so it never joins the open list."""
        if tag in DROPPED_ELEMENTS or self.dropped_depth or tag not in ALLOWED_ELEMENTS:
            return
        self.parts.append(f"<{tag}{self._safe_attributes(attrs)}>")

    def handle_endtag(self, tag: str) -> None:
        """Close the tag, along with anything left open inside it."""
        if self.dropped_depth:
            if tag in DROPPED_ELEMENTS:
                self.dropped_depth -= 1
            return
        if tag in VOID_ELEMENTS or tag not in self.open_tags:
            return
        # Close down to the matching tag: real documents do not always close what they open,
        # and leaving those tags open would let the document's markup run on into the output
        # around it.
        while self.open_tags:
            open_tag = self.open_tags.pop()
            if open_tag == "pre":
                self.preformatted_depth = max(self.preformatted_depth - 1, 0)
            self.parts.append(f"</{open_tag}>")
            if open_tag == tag:
                break

    def handle_data(self, data: str) -> None:
        """
        Keep the text, escaped so it can only ever be text -- and carrying no raw newline.

        Two later stages rewrite newlines and <br> out from under us: share.py turns every
        "\\n" in a finished description into "<br>", and format_line turns every "<br>" into
        "<br>\\r".  Inside a <pre>, where a line break is content, either rewrite lands an
        extra break in the text and the code block comes out double-spaced.  So say it in the
        one form neither stage touches: "&#10;", the same escape build_tooltip_span() uses,
        which the browser reads back as the newline it is.

        Outside a <pre> the newlines are only the document's own indentation.  Collapse
        whitespace the way a browser would, so nothing downstream can promote it to a
        visible break -- that is what was prising the author's cards apart.
        """
        if self.dropped_depth:
            return
        text = html.escape(data, quote=False)
        if self.preformatted_depth:
            text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "&#10;")
        else:
            text = WHITESPACE_RUN.sub(" ", text)
        self.parts.append(text)

    def _safe_attributes(self, attrs: list[tuple[str, str]]) -> str:
        """Render the attributes worth keeping, as a string ready to follow a tag name."""
        kept = []
        for name, value in attrs:
            attribute = name.lower()
            if attribute not in ALLOWED_ATTRIBUTES or value is None:
                continue
            if attribute == "style":
                value = safe_style(value)  # noqa: PLW2901
            elif attribute in ("href", "src"):
                value = safe_url(value)  # noqa: PLW2901
            if value:
                kept.append(f'{attribute}="{html.escape(value, quote=True)}"')
        return f" {' '.join(kept)}" if kept else ""

    def sanitized(self) -> str:
        """The rebuilt HTML, with every still-open tag closed."""
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


# Where a label stops being a line of text and starts being a document of its own.
def html_document_start(text: str) -> int:
    """
    The offset at which an embedded HTML document begins, or -1 if there isn't one.

        :param text: the label to examine
        :return: index of the start of the document, or -1
    """
    match = HTML_DOCUMENT_MARKER.search(text)
    return match.start() if match else -1


# The background color a style attribute sets, if any.
def _background_from_style(style: str) -> str:
    """
    The color out of a "background" or "background-color" declaration, or "".

    "background" is a shorthand and can carry a good deal besides the color, so each of its
    words is tried in turn and the first that names a color wins.

        :param style: an inline style attribute
        :return: the background color, or "" if the style doesn't set one
    """
    for declaration in reversed(style.split(";")):
        prop, _, value = declaration.partition(":")
        if prop.strip().lower() not in ("background", "background-color"):
            continue
        for word in reversed(value.split()):
            try:
                _color_to_rgb(word)
            except (ValueError, AttributeError, TypeError):
                continue
            return word.strip()
    return ""


# Render an authored HTML document as itself, instead of flattening it into text.
def embed_html_document(document: str) -> str:
    """
    Pass a whole HTML document through, keeping the layout and styling its author gave it.

    A label that is a complete document was designed, not typed: it carries its own
    background, spacing and color scheme, and flattening it to colored text throws all of
    that away.  So take the <body>'s contents, sanitize them (see HTMLDocumentSanitizer),
    and wrap them in a container carrying the <body>'s own style -- which is what puts the
    design back on the background it was drawn for.

    Everything before the <body> is dropped: <head> holds no content to show, and its
    <title> is a browser tab caption rather than part of the page.

        :param document: the label text from the start of the HTML document onward
        :return: the document as HTML ready to place in the output, or "" if it is empty
    """
    body = BODY_ELEMENT.search(document)
    if body:
        body_attributes, contents = body.group(1), body.group(2)
    else:
        # A document with no <body> of its own (or one left unclosed) -- take it as it is.
        body_attributes, contents = "", document

    sanitizer = HTMLDocumentSanitizer()
    sanitizer.feed(contents)
    sanitizer.close()
    sanitized = sanitizer.sanitized()
    if not sanitized.strip():
        return ""

    style_match = STYLE_ATTRIBUTE.search(body_attributes)
    container_style = safe_style(style_match.group(2) or style_match.group(3) or "") if style_match else ""

    # A document that sets a background but no text color was relying on the browser's
    # default of black.  Dropped onto MapTasker's output that is a coin toss -- black text
    # on this one's near-black background would be unreadable -- so state a color that suits
    # the background it brought with it.
    declarations = [declaration.split(":")[0].strip().lower() for declaration in container_style.split(";")]
    if "color" not in declarations:
        background = _background_from_style(container_style)
        if background:
            is_dark = _relative_luminance(_color_to_rgb(background)) < 0.5
            container_style += f"; color: {LIGHT_TEXT if is_dark else DARK_TEXT}"

    # The document lays out its own width; the container just has to leave room for it and
    # keep anything too wide (a long <pre> line) from stretching the page around it.
    #
    # "white-space: normal" restores ordinary HTML whitespace collapsing for the document.
    # It is written one indented tag per line, and the Map view renders the output around it
    # with "white-space: pre-wrap" (see NiceGuiTextView) -- which turns every one of those
    # line endings into a visible blank line, prising the author's layout apart from the
    # inside. The <pre> blocks within keep their own whitespace: that is their UA default and
    # is not inherited from here.
    container_style = f"{container_style}; white-space: normal; max-width: 100%; overflow-x: auto".lstrip("; ")
    return f'<div style="{html.escape(container_style, quote=True)}">{sanitized}</div>'


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

# Text whose color comes within this contrast ratio of the background can't be read, so it
# is dropped in favor of the label's default color (see legible_color).  The case this is
# here for: a TaskerNet description written for a dark theme sets its headings to white,
# which lands on MapTasker's own light background and vanishes -- the same disappearing act
# as "color: transparent" above, just arrived at by a different route.  The threshold sits
# well below WCAG's 4.5:1 readability bar on purpose.  The job is to rescue text that has
# effectively disappeared, not to second-guess every color an author chose: a mid-tone like
# #9090aa on white comes to about 2.9 and is left alone.
MINIMUM_CONTRAST_RATIO = 2.0

# A hex color written without its leading "#", the way colrmode stores the dark background.
BARE_HEX_COLOR = re.compile(r"[0-9a-fA-F]{3}|[0-9a-fA-F]{6}")

# Elements that never have an end tag, and so must not put anything on the style stack --
# nothing would ever take it off again.
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

# Tags whose own handlers already set and clear the styles they imply (see handle_endtag).
# Leaving them off the style stack keeps one mechanism in charge of each style, rather than
# having the stack restore a value the tag's own end-tag handler is about to overwrite.
SELF_MANAGED_STYLE_TAGS = {"b", "em", "font", "i", "strong", "u"}

# How far to indent the contents of each nested <div>.  Empty -- the setting we want -- means
# no indenting: a nested layout is flattened to plain lines, the <div> nesting showing only in
# where the lines break.  Set it to some whitespace (e.g. "&nbsp;&nbsp;") to step each level
# in instead; nesting deeper than MAX_INDENT_LEVELS then stops gaining indent, so a deeply
# wrapped layout can't march its own text off the right-hand side.
DIV_INDENT = ""
MAX_INDENT_LEVELS = 6

# Tags that lay out a line break of their own.  A newline pretty-printing the markup next to
# one of these is formatting rather than content -- the browser collapses it, and so do we
# (see parse_html_to_text_segments), or a nested layout ends up one blank line per tag.
# A newline anywhere else, including between two inline tags, still means a line break: that
# is how a plain Tasker label written across several lines gets its breaks.
_BLOCK_TAGS = r"div|section|p|h[1-6]|ul|ol|li|table|thead|tbody|tr|td|th|blockquote|pre|hr|br|figure|figcaption"
NEWLINE_AFTER_BLOCK_TAG = re.compile(rf"(</?(?:{_BLOCK_TAGS})\b[^>]*>)[^\S\n]*\n\s*", re.IGNORECASE)
NEWLINE_BEFORE_BLOCK_TAG = re.compile(rf"\s*\n[^\S\n]*(?=</?(?:{_BLOCK_TAGS})\b)", re.IGNORECASE)


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
        self.tag_stack.append(tag)

        # Fold in whatever this element's "style=" attribute says before dealing with the
        # tag itself, so the styling covers everything the element contains -- and record
        # what to put back when it closes.  Modern HTML carries nearly all of its formatting
        # this way (<div style="...">, <span style="...">) rather than in <font>/<b>/<i>.
        self._push_inline_styles(tag, attrs)

        # Handle the <div> and <section> tags.  Both are block-level containers: their own
        # contribution is to start their contents on a fresh line, indented one level deeper
        # than the element they sit in.  Any styling they carry was applied just above and is
        # taken back off by the matching end tag.
        if tag in ("div", "section"):
            self.div_depth += 1
            self._start_new_line()
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
            self._add_segment("<p>")
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

        # Handle the <blockquote> tag.  Like the list and table tags above, it is passed
        # straight through rather than turned into styling of its own: it is a block-level
        # container whose whole job -- setting the quoted run off from the text around it --
        # is the browser's to do when it renders the output.
        elif tag == "blockquote":
            self._add_segment("<blockquote>")

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

        # Tags with nothing to contribute of their own.  <span> lands here because it is
        # purely a carrier for the "style=" attribute already applied above.
        elif tag in ("tbody", "body", "html", "fieldset", "meta", "head", "figure", "span"):
            return
        # Unrecognized tag
        else:
            self.handle_unknown_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        """
        Processes a closing HTML tag and reverts the formatting state.
        """
        # Take this element's inline styling back off.  First thing done, so it still
        # happens for the tags that return early below.
        self._pop_inline_styles(tag)

        # Handle the </div> and </section> tags
        if tag in ("div", "section"):
            # End the div's/section's content with a line of its own, and step the indent
            # back out to the level of whatever contains it.
            self._start_new_line()
            self.div_depth = max(self.div_depth - 1, 0)
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
        elif tag == "blockquote":
            self._add_segment("</blockquote>")
        # End tags with nothing left to do.  </span> lands here: the styling it carried was
        # already taken back off at the top of this method.
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
            "span",
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
        style = dict(attrs).get("style", "")
        if style:
            self._apply_inline_style(style)

    def _pop_inline_styles(self, tag: str) -> None:
        """
        Restore the styles that were in force before the element being closed opened.

        Real-world HTML does not always close what it opens, so search down for the entry
        this end tag belongs to rather than assuming it is on top.  Everything above it was
        left open inside the element and closes with it, whatever the markup says -- dropping
        those entries stops them being matched later by some unrelated end tag.  An end tag
        with no entry at all (a stray </span>, of which the output has had a few -- see
        pattern9 in format_line) changed nothing, so there is nothing to put back.

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
        Fold an element's inline "style=" attribute into the current styles.

        Only the four properties this formatter can actually represent are read (see
        INLINE_STYLE_KEYS); everything else in the declaration -- font sizes, margins,
        backgrounds -- has no equivalent in a text segment and is passed over.  Properties
        are applied rather than merely turned on, so "font-weight: normal" inside a bold
        run correctly un-bolds it for the length of the element.

            :param style: the raw value of the style attribute, e.g. "color: #ff0000; font-weight: bold"
        """
        for declaration in style.split(";"):
            prop, _, value = declaration.partition(":")
            prop = prop.strip().lower()
            value = value.strip().lower()
            if not prop or not value:
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
            # Fall back to the label's default color when the label asked for one that would
            # be unreadable on our background (see legible_color), as well as when it asked
            # for none at all.
            lbl_color = legible_color(lbl_style["color"], PrimeItems.colors_to_use[color_to_use])
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
            # Style the link explicitly rather than leaving it to the browser's default: the
            # anchor is about to be wrapped in a span carrying this segment's color and
            # "text-decoration: none", and the Map view's Tailwind reset makes an <a> inherit
            # both, which renders the link exactly like the text around it -- see
            # sysconst.HOTLINK_STYLE. Same styling the directory and Task warning links use, so
            # every hotlink in the output looks the same.
            #
            # An external link also opens in a new tab: in the Map view the output is rendered
            # inside the running app's own page, so following a TaskerNet link in place would
            # navigate away from MapTasker itself. In-page targets (href="#...", e.g. the
            # directory's own anchors) deliberately stay in this tab -- that is the whole point
            # of them.
            if lbl_link:
                new_tab = "" if str(lbl_href).startswith("#") else ' target="_blank" rel="noopener noreferrer"'
                lbl_text = f'<a href="{lbl_href}" style="{HOTLINK_STYLE}"{new_tab}>{lbl_text}</a>'

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

    # The author's own document, if there was one, follows the lead-in.
    return task_label + document_html


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
