"""htmlsafe: making an authored HTML document safe to show, and legible on the Map's background.

The allow-lists of elements, attributes, URL schemes and CSS, the contrast arithmetic that picks a readable
colour against a dark or light page, and the sanitizer that applies them to a document a user wrote as a
Task's or Profile's HTML.  Nothing here reads a stylesheet (htmlstyle) or flattens markup to text (htmltext)."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING

from PIL import ImageColor

from maptasker.src.core.sysconst import logger

if TYPE_CHECKING:
    from collections.abc import Mapping


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


# Tags authors write that are not HTML, and the element a browser would have been given had they
# spelled it right.
TAG_ALIASES = {"bold": "b"}


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
        channel / 12.92 if (channel := value / 255) <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4 for value in rgb
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


# Whether a color is a dark one, i.e. whether what sits on it has to be light to be seen.
def is_dark_color(color: str) -> bool:
    """
    True if the color is dark enough that light text belongs on it.

    Used wherever something has to be picked to suit the background rather than stated
    outright: the text color for a passed-through document that named a background but no
    color, and the description box's own background in the generated HTML (see addcss).

        :param color: a color as configured, e.g. "Lavender", "222623", "#0096ff"
        :return: True if the color is dark, False if it is light or can't be resolved
    """
    try:
        return _relative_luminance(_color_to_rgb(color)) < 0.5
    except (ValueError, AttributeError, TypeError):
        # An unknown color name, a gradient, a variable reference: nothing to reason about,
        # so treat it as light -- the same assumption every browser default makes.
        return False


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
def legible_color(color: str | None, default_color: str, colors: Mapping[str, str]) -> str:
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
        :param colors: the run's colors by argument name (RunConfig.colors); the background is read from it
        :return: the color to use
    """
    if not color:
        return default_color

    background = colors.get("background_color", "")
    if not background:
        return color

    ratio = contrast_ratio(color, background)
    if ratio is not None and ratio < MINIMUM_CONTRAST_RATIO:
        logger.debug(f"format: dropping unreadable label color {color} on {background} (contrast {ratio:.2f}).")
        return default_color
    return color


def escaped_text(text: str) -> str:
    """
    Text made safe to write into the page: "<", ">" and "&" become entities, so it can only be shown.

    A description's own markup is read by the parser and comes through as tags and styling;
    what is left is words.  Those words can still contain characters that are markup once
    written into HTML -- most simply a description that spells a tag as "&lt;script&gt;",
    which the parser turns back into "<script>".  Written out as it stands, that is a script
    element in the Map, put there by a file downloaded from the internet.

        :param text: words, as the parser decoded them
        :return: the same words, escaped
    """
    return html.escape(text, quote=False)


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


def image_source(url: str) -> str:
    """
    An <img src> value if we are willing to hand it to the browser, otherwise empty.

    safe_url() is the general rule, with one exception: it refuses "data:", and a data URI is
    exactly how a description embeds an image with no server to fetch it from.  An image data
    URI is inert -- the browser decodes it as pixels, never as code -- so dropping it would
    only lose a picture that renders perfectly well today.  Every other "data:" payload, and
    every scheme safe_url() turns down, still goes.

        :param url: the src as written in the description
        :return: the URL, or "" if it isn't one we will load
    """
    cleaned = url.strip().replace("\n", "").replace("\t", "")
    if cleaned.lower().startswith("data:image/"):
        return cleaned
    return safe_url(cleaned)


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
        self.parts: list[str] = []
        # Depth of nesting inside a dropped element, whose content goes with it.
        self.dropped_depth = 0
        # Tags left open, so the result can be closed off properly however ragged the input.
        self.open_tags: list[str] = []
        # Depth of nesting inside <pre>, where whitespace is content rather than layout.
        self.preformatted_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Emit an allowed tag with its safe attributes; drop or unwrap anything else."""
        tag = TAG_ALIASES.get(tag, tag)
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

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """A self-closing tag opens and closes in one go, so it never joins the open list."""
        tag = TAG_ALIASES.get(tag, tag)
        if tag in DROPPED_ELEMENTS or self.dropped_depth or tag not in ALLOWED_ELEMENTS:
            return
        self.parts.append(f"<{tag}{self._safe_attributes(attrs)}>")

    def handle_endtag(self, tag: str) -> None:
        """Close the tag, along with anything left open inside it."""
        tag = TAG_ALIASES.get(tag, tag)
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
        r"""
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

    def _safe_attributes(self, attrs: list[tuple[str, str | None]]) -> str:
        """Render the attributes worth keeping, as a string ready to follow a tag name."""
        kept: list[str] = []
        for name, value in attrs:
            attribute = name.lower()
            if attribute not in ALLOWED_ATTRIBUTES or value is None:
                continue
            cleaned = value
            if attribute == "style":
                cleaned = safe_style(value)
            elif attribute in ("href", "src"):
                cleaned = safe_url(value)
            if cleaned:
                kept.append(f'{attribute}="{html.escape(cleaned, quote=True)}"')
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
            container_style += f"; color: {LIGHT_TEXT if is_dark_color(background) else DARK_TEXT}"

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
