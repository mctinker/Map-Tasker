"""tndesc: the TaskerNet description of a Project, Profile or Task -- reading it, writing it, and checking its HTML."""

#! /usr/bin/env python3

#                                                                                       #
# tndesc: what Tasker keeps in <Share><d> -- the description shown to anybody who is    #
#         about to import a Project, Profile or Task from TaskerNet -- and the means to #
#         write one: the element, the HTML a description can carry, and a check of it.  #
#                                                                                       #
# WHAT THE ELEMENT LOOKS LIKE.  Every <Share> in the 2,396 descriptions of the sample   #
# backups has the same children, in the same order: <b>, <d>, optionally <g>, <p>, <t>. #
# <d> is the description, <g> the TaskerNet search categories, and b, p and t are       #
# Tasker's own bookkeeping, which this module never changes on an existing <Share> and  #
# writes as false/false/empty on a new one -- the most common shape of a share that has #
# a description and no tags (793 of them).  <Share> itself sits after an object's       #
# lowercase children and its <Kid>, and before <Img>, <ProfileVariable> and the actions, #
# conditions and so on: Tasker's own order, kept so what is written looks like what is  #
# exported.                                                                             #
#                                                                                       #
# WHAT HTML A DESCRIPTION MAY CARRY.  Tasker's own page says only that "HTML formatting #
# can be used, and even some small images".  It does not say which tags, so there is no #
# list to quote, and none is claimed here.  What this module offers is the tags real    #
# shares use -- counted over the sample backups -- and that MapTasker's own Map renders: #
# htmlsafe.ALLOWED_ELEMENTS, plus <font>, which 130 of those descriptions use for color. #
# A tag outside that set is not an error, because TaskerNet's own rules are not known   #
# to us; it is reported as one the checker has no evidence for, and the report says so. #
# What is reported as a WARNING is what a browser would be unsafe to run (script, an    #
# event handler, a javascript: link) or what cannot be taken at its word (an image      #
# whose bytes are in the description itself, against "small images").                   #
#                                                                                       #
# Same contract as objprops: nothing here touches the GUI.  The edit lands on whatever  #
# element it is handed; which element that should be is the caller's decision, and for  #
# a Project it is both the working copy and the live one (see mirror_share).            #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING

from maptasker.src.core.htmlsafe import ALLOWED_ELEMENTS, ALLOWED_URL_SCHEMES, DROPPED_ELEMENTS, VOID_ELEMENTS

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

SHARE_TAG = "Share"
DESCRIPTION_TAG = "d"

# What a <Share> that has just been given a description is made of: Tasker's own bookkeeping
# children, at the values most descriptions without search tags carry.
_NEW_SHARE_CHILDREN = (("b", "false"), ("d", ""), ("p", "false"), ("t", ""))
_BOOKKEEPING_TAGS = frozenset({"b", "d", "p", "t"})

# Written by a person at a keyboard, in any of three conventions.  What is stored is the text
# as typed, with the line ends Tasker itself writes.
_LINE_ENDS = re.compile(r"\r\n?")


# ##################################################################################
# The element.
# ##################################################################################
def description_of(element: Element) -> str:
    """The description an object carries, as typed -- "" when it has none."""
    return element.findtext(f"{SHARE_TAG}/{DESCRIPTION_TAG}") or ""


def has_description(element: Element) -> bool:
    """Whether the object has a description worth showing."""
    return bool(description_of(element).strip())


def _share_position(element: Element) -> int:
    """Where a new <Share> goes: after every lowercase child and every <Kid>, ahead of the rest."""
    last = -1
    for index, child in enumerate(element):
        if not child.tag[:1].isupper() or child.tag == "Kid":
            last = index
    return last + 1


def _is_bare(share: Element) -> bool:
    """Whether a <Share> says nothing at all: no description, no tags, nothing made public."""
    for child in share:
        text = (child.text or "").strip()
        if child.tag not in _BOOKKEEPING_TAGS:
            return False
        if text and text != "false":
            return False
    return True


def _new_share(element: Element) -> Element:
    """A <Share> holding only Tasker's bookkeeping, put where Tasker puts it."""
    share = type(element)(SHARE_TAG, {"sr": SHARE_TAG})
    for tag, text in _NEW_SHARE_CHILDREN:
        child = type(element)(tag)
        child.text = text
        share.append(child)
    element.insert(_share_position(element), share)
    return share


def set_description(element: Element, text: str) -> None:
    """Make `text` the object's description.

    Nothing but <d> is touched on an object that already has a <Share>: its search tags and
    Tasker's own flags are somebody else's.  An empty description removes <d>'s text, and a
    <Share> left saying nothing at all is taken away entirely, so clearing a description
    puts the object back exactly as it was before one was added.
    """
    text = _LINE_ENDS.sub("\n", text)
    share = element.find(SHARE_TAG)
    if not text.strip():
        if share is None:
            return
        description = share.find(DESCRIPTION_TAG)
        if description is not None:
            description.text = ""
        if _is_bare(share):
            element.remove(share)
        return
    if share is None:
        share = _new_share(element)
    description = share.find(DESCRIPTION_TAG)
    if description is None:
        description = type(element)(DESCRIPTION_TAG)
        share.insert(next((i + 1 for i, child in enumerate(share) if child.tag == "b"), 0), description)
    description.text = text


def mirror_share(source: Element, target: Element) -> None:
    """Make `target`'s <Share> the same as `source`'s -- or absent, when `source` has none.

    For a Project, whose working copy and live element have to be kept level (see
    projedit.apply_share_to_live_tree for why both are written).  A deep copy of the whole
    <Share> rather than of its description, so the two cannot disagree about the tags either.
    """
    for existing in target.findall(SHARE_TAG):
        target.remove(existing)
    share = source.find(SHARE_TAG)
    if share is not None:
        target.insert(_share_position(target), copy.deepcopy(share))


# ##################################################################################
# The HTML a description can carry, and the buttons that write it.
# ##################################################################################
@dataclass(frozen=True)
class Tool:
    """One button of the description editor: the markup it writes, and what it is for.

    'before' and 'after' wrap whatever is selected; with nothing selected 'placeholder' stands
    between them, selected, so typing replaces it.  A tool with no 'after' is a single thing
    set down at the caret -- a line break, a rule, an image.
    """

    key: str
    label: str
    before: str
    after: str = ""
    placeholder: str = ""
    icon: str = ""
    tooltip: str = ""


# The two values a tool may ask the editor for: an address, and a color.
ADDRESS = "{address}"
COLOR = "{color}"
DEFAULT_ADDRESS = "https://"
COLORS = ("red", "orange", "green", "blue", "purple", "gray", "black")

# In the order the toolbar shows them: the text styles, the blocks, then the things that point
# elsewhere.  The tags are the ones the sample descriptions use most (counted over 2,396).
TOOLS: tuple[Tool, ...] = (
    Tool("bold", "Bold", "<b>", "</b>", "bold text", "format_bold", "Bold:  <b>...</b>"),
    Tool("italic", "Italic", "<i>", "</i>", "italic text", "format_italic", "Italic:  <i>...</i>"),
    Tool("underline", "Underline", "<u>", "</u>", "underlined text", "format_underlined", "Underline:  <u>...</u>"),
    Tool("color", "Color", f'<font color="{COLOR}">', "</font>", "colored text", "palette", "Color:  <font color=...>"),
    Tool("code", "Code", "<code>", "</code>", "code", "code", "Code, in a fixed-width font:  <code>...</code>"),
    Tool("paragraph", "Paragraph", "<p>", "</p>", "paragraph", "notes", "A paragraph:  <p>...</p>"),
    Tool("break", "Line Break", "<br/>", "", "", "keyboard_return", "A line break:  <br/>"),
    Tool("rule", "Rule", "<hr/>", "", "", "horizontal_rule", "A horizontal line:  <hr/>"),
    Tool(
        "bullets", "Bullets", "<ul>\n<li>", "</li>\n</ul>", "item", "format_list_bulleted", "A bulleted list:  <ul><li>"
    ),
    Tool(
        "numbers", "Numbers", "<ol>\n<li>", "</li>\n</ol>", "item", "format_list_numbered", "A numbered list:  <ol><li>"
    ),
    Tool(
        "link",
        "Link",
        f'<a href="{ADDRESS}">',
        "</a>",
        "link text",
        "link",
        "A link to the address typed below:  <a href=...>",
    ),
    Tool(
        "image",
        "Image",
        f'<img src="{ADDRESS}"/>',
        "",
        "",
        "image",
        "An image from the address typed below:  <img src=...>",
    ),
    Tool(
        "table",
        "Table",
        "<table>\n<tr><th>Name</th><th>Description</th></tr>\n<tr><td>",
        "</td><td></td></tr>\n</table>",
        "first cell",
        "table_chart",
        "A table with a heading row:  <table><tr><th>",
    ),
)
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
DEFAULT_HEADING = "h3"


def heading_tool(level: str) -> Tool:
    """The tool for one heading level: 'h1' to 'h6'."""
    tag = level if level in HEADINGS else DEFAULT_HEADING
    return Tool(tag, tag.upper(), f"<{tag}>", f"</{tag}>", "heading", "title", f"A heading:  <{tag}>...</{tag}>")


@dataclass(frozen=True)
class Edit:
    """What a tool did to the text: the new text, and what to leave selected in it."""

    text: str
    start: int
    end: int


def _quote(value: str) -> str:
    """A value fit to sit inside a double-quoted attribute."""
    return value.replace('"', "%22")


def apply_tool(text: str, start: int, end: int, tool: Tool, *, address: str = "", color: str = "") -> Edit:
    """Put a tool's markup into `text` at the selection `start`..`end`.

    The selection is clamped to the text, so a caret the browser reported for a stale value
    cannot cut a tag in two.  A selection is wrapped; an empty one gets the tool's
    placeholder, selected.  A tool with nothing to close is set down after the selection.
    """
    length = len(text)
    start = max(0, min(start, length))
    end = max(start, min(end, length))
    before = tool.before.replace(ADDRESS, _quote(address.strip() or DEFAULT_ADDRESS)).replace(
        COLOR,
        _quote(color.strip() or COLORS[0]),
    )
    if not tool.after:
        caret = end + len(before)
        return Edit(f"{text[:end]}{before}{text[end:]}", caret, caret)
    chosen = text[start:end] or tool.placeholder
    inserted = f"{before}{chosen}{tool.after}"
    first = start + len(before)
    return Edit(f"{text[:start]}{inserted}{text[end:]}", first, first + len(chosen))


def add_line_breaks(text: str) -> str:
    """Put a <br/> on the end of every line that does not already end a tag.

    For a description written as plain text: in HTML a line end is only a space, so text that
    reads as a list in a text box runs together as a paragraph on a web page.  A line that
    already ends in a tag -- most often a <br/> -- is left alone, so running it twice changes
    nothing.
    """
    lines = _LINE_ENDS.sub("\n", text).split("\n")
    done = [line if line.rstrip().endswith(">") else f"{line}<br/>" for line in lines[:-1]]
    return "\n".join([*done, lines[-1]])


# ##################################################################################
# The check.
# ##################################################################################
WARNING = "WARNING"
INFO = "INFO"

# Elements HTML lets a page leave unclosed, and descriptions in the sample backups routinely do.
_OPTIONAL_END = frozenset({"p", "li", "td", "th", "tr", "thead", "tbody", "tfoot", "dt", "dd"})
_RECOGNIZED = ALLOWED_ELEMENTS | {"font"}
# Written as a unit by authors who mean the page around the description, and carrying nothing of it.
_DOCUMENT_ELEMENTS = frozenset({"html", "head", "body"})
# The link scheme TaskerNet itself writes, to open a share in Tasker: 'taskershare://<user>/Project:Name'.
# 19 of the sample descriptions use it, and a check that warned about them would be wrong.
TASKERNET_SCHEME = "taskershare:"
_LINK_SCHEMES = (*ALLOWED_URL_SCHEMES, TASKERNET_SCHEME)
# "Small images": Tasker's wording, with no number.  Past this many characters of image data
# inside the description itself, the check says so.
EMBEDDED_IMAGE_LIMIT = 20_000
_ISSUES_SHOWN = 8


@dataclass(frozen=True)
class Issue:
    """One thing the check has to say about a description."""

    severity: str
    message: str


class _Checker(HTMLParser):
    """Walks a description's tags and notes what is unclosed, unfamiliar or unsafe."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.issues: list[Issue] = []
        self._seen: set[tuple[str, str]] = set()

    def _note(self, severity: str, message: str, key: str = "") -> None:
        """Record an issue once: forty <script> tags are one finding."""
        marker = (severity, key or message)
        if marker not in self._seen:
            self._seen.add(marker)
            self.issues.append(Issue(severity, message))

    def _check_tag(self, tag: str) -> None:
        if tag in DROPPED_ELEMENTS:
            self._note(
                WARNING,
                f"<{tag}> is removed by MapTasker's views and by most web pages, and TaskerNet is "
                "likely to remove it too.",
                tag,
            )
        elif tag not in _RECOGNIZED and tag not in _DOCUMENT_ELEMENTS and tag not in VOID_ELEMENTS:
            self._note(
                INFO,
                f"<{tag}> is not a tag the descriptions of other shares use, so it may not be shown as written.",
                tag,
            )

    def _check_attributes(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        for name, value in attributes:
            text = (value or "").strip()
            if name.startswith("on"):
                self._note(WARNING, f"<{tag} {name}=...> runs script, which no description should carry.", name)
            elif name in {"href", "src"} and text:
                self._check_address(tag, name, text)

    def _check_address(self, tag: str, name: str, address: str) -> None:
        lowered = address.lower()
        if lowered.startswith("data:") and tag == "img":
            if len(address) > EMBEDDED_IMAGE_LIMIT:
                self._note(
                    WARNING,
                    f"An image is stored inside the description ({len(address):,} characters).  Tasker says "
                    "'small images': link to a picture instead.",
                    "embedded",
                )
        elif ":" in lowered.split("/", 1)[0] and not lowered.startswith(_LINK_SCHEMES):
            self._note(
                WARNING,
                f'{name}="{address[:40]}" is not a link to a web page, an email address or a TaskerNet share, so it is not kept.',
                lowered.split(":", 1)[0],
            )

    def _open(self, tag: str, attributes: list[tuple[str, str | None]], *, push: bool) -> None:
        self._check_tag(tag)
        self._check_attributes(tag, attributes)
        if push and tag not in VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, push=True)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, push=False)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_ELEMENTS:
            return  # '</img>' appears in real shares, and means nothing
        if tag not in self.stack:
            if tag not in _OPTIONAL_END:
                self._note(WARNING, f"</{tag}> closes nothing: there is no <{tag}> before it.", f"close {tag}")
            return
        while self.stack:
            open_tag = self.stack.pop()
            if open_tag == tag:
                break
            if open_tag not in _OPTIONAL_END:
                self._note(WARNING, f"<{open_tag}> is never closed.", f"open {open_tag}")

    def finish(self) -> list[Issue]:
        """The issues, once the whole description has been fed in."""
        self.close()
        for open_tag in self.stack:
            if open_tag not in _OPTIONAL_END and open_tag not in _DOCUMENT_ELEMENTS:
                self._note(WARNING, f"<{open_tag}> is never closed.", f"open {open_tag}")
        return self.issues


def check(text: str) -> list[Issue]:
    """What is wrong with, or worth knowing about, the HTML in a description.

    Nothing for plain text, and nothing for a description that is sound.  Capped, with the
    count of the rest, because a description pasted from a web page can have hundreds.
    """
    checker = _Checker()
    checker.feed(text)
    issues = checker.finish()
    if len(issues) > _ISSUES_SHOWN:
        issues = [*issues[:_ISSUES_SHOWN], Issue(INFO, f"...and {len(issues) - _ISSUES_SHOWN} more.")]
    return issues
