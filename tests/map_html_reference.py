"""The Map's html cleanup written as the single regular expression it started as.

guiwins_mapstream.optimize_map_html makes the same changes faster, in pieces; the tests hold it to this.
"""

from __future__ import annotations

import re

from maptasker.src.gui.guiwins_mapstream import HTML_REPLACEMENT_MAP

HTML_OPTIMIZE_PATTERN = re.compile(
    r"(?P<formatting>(?<=>)[ \t]*[\r\n]+|[\r\n]+[ \t]*(?=<))"
    r"|(?P<written>[\r\n]{2,})"
    r"|(?P<heading><h2>MapTasker</h2>|<h2><span class=\"normtab\"></span>Directory</h2>)",
)


def optimize_html(match: re.Match[str]) -> str:
    """
    What one match of HTML_OPTIMIZE_PATTERN becomes -- see the note above optimize_map_html's regular expressions.

        :param match: the matched formatting, written newlines, or heading
        :return: what to put in its place
    """
    if match.lastgroup == "formatting":
        return ""  # The file's own line endings, which this view would otherwise draw.
    if match.lastgroup == "written":
        return "\n"  # The author's own, and one line break is all they asked for.
    return HTML_REPLACEMENT_MAP[match.group(0)]


def optimized(text: str) -> str:
    """The Map file as the one-pass regular expression leaves it."""
    return HTML_OPTIMIZE_PATTERN.sub(optimize_html, text)
