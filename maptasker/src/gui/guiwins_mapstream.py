"""guiwins_mapstream: getting the Map's html to the browser -- cleaned up, cut into chunks, or rebuilt as a fallback.

optimize_map_html does what HTML_OPTIMIZE_PATTERN says to the Map file; split_for_streaming cuts it into socket-sized
chunks without leaving an element open across a cut; the fallback functions show a Map the browser could not take
whole as plain escaped lines."""

from __future__ import annotations

import re

# ==========================================
# STREAMING THE MAP INTO THE TEXT VIEW
# ==========================================
# Pre-compile the regex pattern at the module level for maximum execution performance.
# This scans the HTML string and hits all target replacements in a single pass O(N).
#
# Most of what it does is about newlines, because this view shows the Map as preformatted
# text (see the wrap classes in build_ui) and a browser draws every newline in
# preformatted text as a line break.  A browser opening the saved file draws none of them:
# they are the file's own formatting, one after every <br> and one between the tags of
# each line, and there are tens of thousands.  Drawn, each one is an extra line -- and a
# blank line wherever the Map had already ended that line with a <br>, which is why a
# section heading in this view sat three and four blank lines below the section above it
# while the same file opened in a browser showed one.
#
# So a newline that touches a tag goes: it is the file's formatting, not the Map's.  A
# newline with text on both sides is the author's -- a Tasker value written over several
# lines -- and stays, as the one line break it asks for.  What this no longer does is
# throw <br>s away: it used to fold "<br><br>" down to one, from the days when the file
# arrived with gap after gap of blank lines in it.  bildhtml now writes that file through
# format.BlankLineLimiter, which keeps every gap to MAX_BLANK_LINES, so a second squeeze
# here only fought the first.
HTML_OPTIMIZE_PATTERN = re.compile(
    r"(?P<formatting>(?<=>)[ \t]*[\r\n]+|[\r\n]+[ \t]*(?=<))"
    r"|(?P<written>[\r\n]{2,})"
    r"|(?P<heading><h2>MapTasker</h2>|<h2><span class=\"normtab\"></span>Directory</h2>)",
)


# Map the targeted string matches directly to their optimized counterparts.
HTML_REPLACEMENT_MAP = {
    "<h2>MapTasker</h2>": '<a id="the_top"></a><h5>MapTasker</h5>',
    '<h2><span class="normtab"></span>Directory</h2>': '<h6><span class="normtab"></span>Directory</h6>',
}


def optimize_html(match: re.Match) -> str:
    """
    What one match of HTML_OPTIMIZE_PATTERN becomes -- see the note above it.

        :param match: the matched formatting, written newlines, or heading
        :return: what to put in its place
    """
    if match.lastgroup == "formatting":
        return ""  # The file's own line endings, which this view would otherwise draw.
    if match.lastgroup == "written":
        return "\n"  # The author's own, and one line break is all they asked for.
    return HTML_REPLACEMENT_MAP[match.group(0)]


# The pieces HTML_OPTIMIZE_PATTERN is made of, taken one at a time -- see optimize_map_html.
TAG_THEN_NEWLINES = re.compile(r">[ \t]*[\r\n]+")


NEWLINES_THEN_TAG = re.compile(r"[\r\n]+[ \t]*(?=<)")


SEVERAL_NEWLINES = re.compile(r"[\r\n]{2,}")


# What a browser makes of "&nbsp;", written as the character itself.
NO_BREAK_SPACE = "\u00a0"


def _join_lines_next_to_tags(text: str) -> str:
    """What NEWLINES_THEN_TAG and SEVERAL_NEWLINES do to `text`, in one pass over its lines.

    Both are scans for a newline, and the Map has a hundred thousand of them in twenty
    megabytes of text, so the regular expressions spent their time looking.  str.split finds
    the same newlines at the speed of memchr; what is left is a loop over the lines.

    Only for text without a carriage return, which the Map has none of -- the caller sends
    anything else to the regular expressions.

    :param text: the Map's html, with the newlines that follow a tag already gone
    :return: the text with every newline that precedes a tag gone, and each other run of newlines
        down to one
    """
    lines = text.split("\n")
    kept = [lines[0]]
    pending = False  # newlines seen since the last line that had something on it
    for line in lines[1:]:
        pending = True
        if not line:
            continue
        pending = False
        # A newline that touches a tag goes, along with the white space between them;
        # anything else is the author's own and stays, as the one line break it asks for.
        stripped = line.lstrip(" \t")
        if stripped.startswith("<"):
            kept.append(stripped)
        else:
            kept.append("\n")
            kept.append(line)
    if pending:
        kept.append("\n")
    return "".join(kept)


def optimize_map_html(text: str) -> str:
    """Make the Map file ready for the browser: HTML_OPTIMIZE_PATTERN's changes, and shorter spaces.

    The text this returns is the text HTML_OPTIMIZE_PATTERN.sub(optimize_html, text) returns,
    with the indentation's "&nbsp;"s written as the character they stand for.  Two reasons for
    each change, and both are about how long a large Map takes to appear:

      * The pattern is an alternation that starts with a look-behind, which leaves the regular
        expression engine no character to search for, so it tried every position of twenty
        megabytes: over a second.  Cut into its three pieces, each with a character to look
        for, and with the newlines left to str.split, the same changes take about a tenth of it.

      * Sixty percent of the Map is "&nbsp;" -- its indentation is spelled that way, at six
        bytes a space.  The character itself is two bytes, and is what the browser makes of the
        entity, so the page that comes of it is the same one, from half the text to send and
        to parse: the Map reaches the screen in about half the time.

    :param text: the Map's html, as it was written
    :return: the html to hand to the browser
    """
    for heading, replacement in HTML_REPLACEMENT_MAP.items():
        text = text.replace(heading, replacement)
    text = TAG_THEN_NEWLINES.sub(">", text)
    if "\r" in text:
        text = SEVERAL_NEWLINES.sub("\n", NEWLINES_THEN_TAG.sub("", text))
    else:
        text = _join_lines_next_to_tags(text)
    return text.replace("&nbsp;", NO_BREAK_SPACE)


# How the Map is cut up for the browser (see split_for_streaming).
#
# 256KB a piece, which on a large configuration is of the order of fifty pieces (the Map has
# had its "&nbsp;"s shortened by then, see optimize_map_html): small
# enough that the browser can put the top of the Map on screen while the rest is still
# arriving, and few enough that the per-piece cost -- an element, a websocket message and
# the tags re-stated across the cut -- stays in the noise.
STREAM_CHUNK_BYTES = 262144


HTML_ELEMENT = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)[^>]*?(/?)>")


# Elements with no end tag of their own; nothing is left open by one.
VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"},
)


# The page's own frame, which the view never sees the end of and must not try to re-state.
FRAME_ELEMENTS = frozenset({"html", "head", "body"})


# Starting one of these closes an open <p>, which is a thing a browser does and the Map's
# html relies on: a TaskerNet description writes "<p>" and leaves it to the next block.
CLOSE_AN_OPEN_PARAGRAPH = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "details",
        "div",
        "dl",
        "fieldset",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "ul",
    },
)


# An id belongs to the element where it opened.  Where a cut re-states that element in the
# next piece, the id is dropped, so that a Task action's anchor stays the one place in the
# document it names (see split_for_streaming).
ELEMENT_ID = re.compile(r'\s+id="[^"]*"')


def split_for_streaming(html: str, budget: int = STREAM_CHUNK_BYTES) -> list[str]:
    """Cut the Map into pieces the browser can render one at a time.

    WHY THIS IS NOT A SPLIT ON LINES.  It was, and the line it split on had already been
    taken out.  The view splits the file after optimize_map_html has run over it, and
    what that pattern removes is precisely the newline between one tag and the next -- so
    a Map of twenty megabytes arrived here as a couple of hundred "lines" and left as a
    single piece.  One element holding the whole Map is the worst shape it could be in:
    the browser parses all of it before it shows any of it, lays out every one of its two
    hundred thousand elements because "content-visibility: auto" can only skip an element
    whole, and it all crosses the socket in one message.  That is the wait.

    WHAT A CUT COSTS.  The Map's colours are <span>s that are opened on one line and
    closed several lines later, so at most points in the document something is open.  A
    piece therefore ends by closing what is open and the next begins by opening it again,
    which is why this returns pieces that do not concatenate back into the original text
    -- they render as it, which is the thing that has to be true.  On a large Map the
    re-stated tags come to well under a tenth of its size.

    :param html: the whole Map, as the view has optimized it
    :param budget: how many bytes to aim for in a piece
    :return: the pieces, in order
    """
    open_elements: list[tuple[str, str]] = []  # (tag name, the markup that opened it)
    pieces: list[str] = []
    start = 0
    carried = ""  # the tags this piece has to re-state because a cut fell inside them

    for element in HTML_ELEMENT.finditer(html):
        closing, name, self_closing = element.group(1), element.group(2).lower(), element.group(3)
        if name in FRAME_ELEMENTS or name in VOID_ELEMENTS or self_closing:
            pass
        elif closing:
            # Everything opened inside the element being closed is closed with it, which
            # is what the browser does with markup that never closed it explicitly.
            for index in range(len(open_elements) - 1, -1, -1):
                if open_elements[index][0] == name:
                    del open_elements[index:]
                    break
        else:
            if open_elements and open_elements[-1][0] == "p" and name in CLOSE_AN_OPEN_PARAGRAPH:
                open_elements.pop()
            open_elements.append((name, element.group(0)))

        if element.end() - start >= budget:
            closers = "".join(f"</{tag}>" for tag, _ in reversed(open_elements))
            pieces.append(f"{carried}{html[start : element.end()]}{closers}")
            carried = "".join(ELEMENT_ID.sub("", markup, count=1) for _, markup in open_elements)
            start = element.end()

    if start < len(html):
        pieces.append(f"{carried}{html[start:]}")
    return pieces


# Tags the fallback rendering lets through unescaped; everything else <like this> is shown as text.
FALLBACK_ALLOWED_TAGS = frozenset(
    {
        "a",
        "table",
        "tr",
        "td",
        "th",
        "tbody",
        "thead",
        "div",
        "span",
        "br",
        "style",
        "b",
        "i",
        "u",
        "strong",
        "em",
        "hr",
        "!doctype",
        "html",
        "head",
        "meta",
        "title",
        "body",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "ul",
        "ol",
        "li",
        # Everything format.py can put in a TaskerNet description or Task label needs
        # to be in this list, or it is escaped and shown as its own markup instead of
        # being rendered.  "img" is the one that shows: a description's picture came
        # out as the literal text of its <img> tag and no image at all.
        "img",
        "figure",
        "figcaption",
        "big",
        "small",
        "code",
        "pre",
        "blockquote",
        "dl",
        "dt",
        "dd",
        "font",
        "mark",
        "sub",
        "sup",
    },
)


def _is_css_line(text: str) -> bool:
    """Whether a stray line of the fallback data is actually a CSS rule."""
    clean = text.strip()
    if clean.startswith((".", "#", "}", "{")):
        return True
    return bool(":" in clean and (clean.endswith(";") or "/*" in clean or "*/" in clean))


def _escape_text_except_html(text: str) -> str:
    """Escapes < and > but preserves intended HTML tags like tables and links."""
    parts = re.split(r"(<[^>]+>)", text)

    for i in range(len(parts)):
        if i % 2 == 0:
            parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
        else:
            tag_name_match = re.match(r"^</?([!a-zA-Z0-9]+)", parts[i])
            if not (tag_name_match and tag_name_match.group(1).lower() in FALLBACK_ALLOWED_TAGS):
                parts[i] = parts[i].replace("<", "&lt;").replace(">", "&gt;")
    return "".join(parts)


class _StyleCollector:
    """Folds the lines of a <style> block, and stray lines of CSS, into <style> elements.

    A stylesheet arrives a line at a time, so a block is gathered up until the line that closes
    it.  A line of CSS with no block around it is wrapped on its own.
    """

    def __init__(self, html_builder: list[str]) -> None:
        """
        Args:
            html_builder: The HTML being assembled; each finished <style> element is appended to it.
        """
        self.html_builder = html_builder
        self.in_style_block = False
        self.style_buffer: list[str] = []

    def consume(self, text: str) -> bool:
        """Take the line if it is CSS, either inside a <style> block or on its own.

        Returns:
            True if it was taken, False if it is a line of content for the caller to deal with.
        """
        if "<style>" in text:
            self.in_style_block = True

        if self.in_style_block:
            clean_line = text.replace("<style>", "").replace("</style>", "").replace('"""', "")
            self.style_buffer.append(clean_line)
            if "</style>" in text:
                self.in_style_block = False
                self.html_builder.append(f"<style>{''.join(self.style_buffer)}</style>")
                self.style_buffer = []
            return True
        if _is_css_line(text):
            self.html_builder.append(f"<style>{text}</style>")
            return True
        return False


def fallback_map_html(the_data: dict) -> list[str]:
    """The Map's output lines, as they are held in memory, as HTML: a <div> per line, a <span> per colour."""
    html_builder: list[str] = []
    styles = _StyleCollector(html_builder)
    for value in the_data.values():
        text_list = value.get("text", [])
        color_list = value.get("color", [])
        full_line_text = "".join(str(t) for t in text_list)

        if styles.consume(full_line_text):
            continue
        line_html = "<div>"
        for t_idx, text_segment in enumerate(text_list):
            segment = str(text_segment).replace('"""', "")
            safe_text = _escape_text_except_html(segment)
            color = color_list[t_idx] if t_idx < len(color_list) else "inherit"
            line_html += f"<span style='color: {color};'>{safe_text}</span>"
        line_html = line_html.rstrip("\r\n")
        html_builder.append(line_html + "</div>")
    return html_builder


def fallback_lines_html(the_data: list[str]) -> list[str]:
    """The lines of every view but the Map, as HTML: a <div> per line."""
    html_builder: list[str] = []
    styles = _StyleCollector(html_builder)
    for line in the_data:
        if line.strip() == "":
            html_builder.append("<div>&nbsp;</div>")
            continue
        text = line.replace("<br><br>", "") if "<br><br>" in line else line
        if '"""' in text:
            if text in {"<div>  </tr>\n</div>", "<div>\n</div>"}:
                continue
            text = text.replace('"""', "")

        if styles.consume(text):
            continue
        clean_text_line = text.rstrip("\r\n")
        safe_line = _escape_text_except_html(clean_text_line)
        html_builder.append(f"<div>{safe_line}</div>")
    return html_builder


def compress_blank_lines(final_html: str) -> str:
    """Squeeze runs of empty <div>s, blank lines and <br>s in the fallback HTML down to one."""
    empty_div_pattern = r"(<div>(?:\s|&nbsp;|<span[^>]*>(?:\s|&nbsp;)*</span>)*</div>\s*){2,}"
    final_html = re.sub(empty_div_pattern, "", final_html)
    final_html = re.sub(r"\n{3,}", "\n", final_html)
    return re.sub(r"(<br\s*/?>\s*){2,}", "<br>", final_html)
