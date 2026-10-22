"""mapwriter: the Map's writing rules -- how many blank lines in a row, and spans that are always closed.

MapWriter applies both in one pass over the html as it goes to the file; BlankLineLimiter and SpanBalancer
are the two rules it drives.  The scan is done once per tag on purpose: a Map is several million characters."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from typing import TextIO


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
    # Input validation.  These used to be returned as text from a function whose callers multiply the
    # answer by a string, so a bad call ended in a confusing TypeError further on.
    if not isinstance(text_string, str):
        message = "The first argument must be a string."
        raise TypeError(message)
    if not isinstance(position, int) or position < 0 or position > len(text_string):
        message = "The second argument must be a valid integer position within the string."
        raise ValueError(message)

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


# The most blank lines the Map is allowed to draw in a row.
MAX_BLANK_LINES = 2


# Tags that draw nothing of their own and do not end the line they are on.  A <br> on
# either side of one of these is still part of the same gap.
INLINE_TAGS = frozenset(
    {"a", "b", "big", "code", "em", "font", "i", "small", "span", "strong", "sub", "sup", "u"},
)


# Elements that are something to look at in their own right, and take a line plus the
# white space around them to do it in: the gap after one starts again from that line.
VISIBLE_TAGS = frozenset({"canvas", "hr", "iframe", "img", "input", "svg", "video"})


# Blocks the browser puts white space above and below of its own accord, whatever the
# Map asks for -- a heading, a table and a paragraph each read as a blank line's worth.
SPACED_TAGS = frozenset({"blockquote", "dl", "h1", "h2", "h3", "h4", "h5", "h6", "ol", "p", "pre", "table", "ul"})


# A tag, and only a tag: a "<" that starts no name is text (a browser reads "a < b" as
# text too), and a ">" inside a quoted attribute value -- a tooltip's own text, say --
# does not end one.
HTML_TAG = re.compile(r"""<[a-zA-Z!/](?:[^>"']|"[^"]*"|'[^']*')*>""")


HTML_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


HTML_TAG_NAME = re.compile(r"</?\s*([a-zA-Z][a-zA-Z0-9]*)")


# The indentation spans (normtab, proftab, actiontab and the rest of addcss's family) are
# inline blocks, so one of them sitting between two <br>s is on a line of its own.
HTML_INDENT_CLASS = re.compile(r'class\s*=\s*"[^"]*?[a-z]*tab\d*\s*"', re.IGNORECASE)


# Whitespace and non-breaking spaces alike: a line holding nothing else still looks blank.
NOTHING_TO_SEE = re.compile(r"^(?:\s|&nbsp;|&#160;)*$")


# How much of a gap between sections a tag takes up by itself -- what count_tag acts on,
# worked out once per distinct piece of markup rather than every time one turns up.
GAP_DRAWS_NOTHING = 0  # inline, draws nothing: <span>, <b>, <a> ...


GAP_HOLDS_THE_LINE = 1  # an indentation span: inline, but an inline BLOCK


GAP_OWN_LINE = 2  # <img>, <hr>: a line of its own, and white space around it


GAP_SPACED_BLOCK = 3  # <h2>, <table>, <ul>: the browser spaces these itself


GAP_PLAIN_BLOCK = 4  # <div>, <tr>, <details>: ends its line, adds no blank one


class TagFacts(NamedTuple):
    """Everything the Map's writers need to know about one tag, read off it once."""

    is_break: bool  # a <br> in any of its spellings
    name: str  # "span", "div", "" for markup with no name at all
    closing: bool  # an end tag
    self_closing: bool  # written as <tag/>
    gap: int  # one of the GAP_ values above


@lru_cache(maxsize=4096)
def tag_facts(markup: str) -> TagFacts:
    """What one tag is, worked out once and then remembered.

    The Map is written with the same handful of tags over and over -- one configuration
    puts out ninety-odd thousand of them between fewer than two thousand distinct pieces
    of markup, half of them "<br>" and "</span>" -- and reading each one meant running
    two or three regular expressions over it every time.  Reading it once per distinct
    piece of markup and remembering the answer turns nearly all of that into a lookup.

    Bounded rather than unbounded: an attribute can carry text of its own (a tooltip
    naming a Task), so the number of distinct tags rises with the size of the
    configuration, and the least useful entries are better dropped than kept for ever.
    """
    name_match = HTML_TAG_NAME.match(markup)
    name = name_match.group(1).lower() if name_match else ""
    if name in INLINE_TAGS:
        gap = GAP_HOLDS_THE_LINE if HTML_INDENT_CLASS.search(markup) else GAP_DRAWS_NOTHING
    elif name in VISIBLE_TAGS:
        gap = GAP_OWN_LINE
    elif name in SPACED_TAGS:
        gap = GAP_SPACED_BLOCK
    else:
        gap = GAP_PLAIN_BLOCK
    return TagFacts(
        is_break=bool(HTML_BREAK.fullmatch(markup)),
        name=name,
        closing=markup.startswith("</"),
        self_closing=markup.endswith("/>"),
        gap=gap,
    )


class BlankLineLimiter:
    """Stand in front of the Map's output file and cap how many blank lines it may write.

    The Map is written a piece at a time by many different places, none of which can see
    what the one before it left behind, so the gaps between sections used to pile up: a
    section's trailing <br>s, then the heading's own, then the leading ones of whatever
    came next, drawing anything up to half a screen of nothing.  Every piece of the file
    passes through here, which makes this the one place that sees a gap whole.

    It counts line endings rather than <br>s, because they are not the same thing.  The
    first <br> after some text only ends that text's line.  A heading, a table or a rule
    has already ended the line it sat on before the next <br> arrives, and the browser
    sets its own white space around those -- a blank line's worth, near enough -- with no
    <br> involved at all.  An indentation span is an inline block, so it too holds a line
    open.  Only the <br>s that would draw one blank line too many are dropped; everything
    else, every tag and every space, is written through exactly as it came in.
    """

    def __init__(self, out_file: TextIO, max_blank_lines: int = MAX_BLANK_LINES) -> None:
        """
        Wrap the file the Map is being written to.
            :param out_file: the open file to write through to
            :param max_blank_lines: the most blank lines in a row to let through
        """
        self.out_file = out_file
        # One line ending is the end of a line of text; each one after that is a blank line.
        self.max_endings = max_blank_lines + 1
        # The file starts on a fresh line, so leading <br>s are blank lines from the first one.
        self.endings = 1

    def write(self, text: str) -> None:
        """
        Write a piece of the Map, minus any <br> that would draw one blank line too many.
            :param text: the html to write
            :return: nothing
        """
        if not text:
            return

        pieces = []
        position = 0
        for tag in HTML_TAG.finditer(text):
            between = text[position : tag.start()]
            self.saw_text(between)
            pieces.append(between)
            position = tag.end()

            markup = tag.group(0)
            if self.keep_tag(markup):
                pieces.append(markup)

        trailing = text[position:]
        self.saw_text(trailing)
        pieces.append(trailing)

        self.out_file.write("".join(pieces))

    def saw_text(self, between: str) -> None:
        """
        Take account of the text between two tags.
            :param between: the text, which may be empty
            :return: nothing
        """
        # Anything there is to see puts us back on a line with something on it; spaces and
        # non-breaking spaces alone still read as blank.
        if between and not NOTHING_TO_SEE.match(between):
            self.endings = 0

    def keep_tag(self, markup: str) -> bool:
        """
        Take account of one tag, and say whether it is to be written at all.
            :param markup: the tag, as it stands in the output
            :return: False for a <br> that would draw one blank line too many, else True
        """
        if tag_facts(markup).is_break:
            self.endings += 1
            if self.endings > self.max_endings:
                self.endings = self.max_endings
                return False  # One blank line too many -- leave this <br> out.
        else:
            self.count_tag(markup)
        return True

    def count_tag(self, markup: str) -> None:
        """
        Note how much of the gap a tag other than <br> has already taken up itself.
            :param markup: the tag, as it will be written
            :return: nothing
        """
        gap = tag_facts(markup).gap
        if gap == GAP_DRAWS_NOTHING:
            # Inline and draws nothing: the gap carries on through it.
            return
        if gap == GAP_HOLDS_THE_LINE:
            # An indentation span is an inline block, so it occupies the line it is on.
            self.endings = 0
        elif gap == GAP_OWN_LINE:
            # Something to see, on a line of its own, with its own white space around it.
            self.endings = 2
        elif gap == GAP_SPACED_BLOCK:
            self.endings = max(self.endings, 2)
        else:
            # A plain block (a division, a row, a twisty).  It ends the line it is on, but
            # adds no blank one of its own to a gap that is already open.
            self.endings = max(self.endings, 1)


# The elements a browser treats as containers: meeting one of their end tags closes
# whatever <span>s were opened inside them, whether the markup said so or not.
BLOCK_TAGS = frozenset(
    {
        "blockquote",
        "body",
        "dd",
        "details",
        "div",
        "dl",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "html",
        "li",
        "ol",
        "p",
        "pre",
        "section",
        "summary",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    },
)


class SpanBalancer:
    """Write the Map's html with its <span>s opened and closed in step.

    The Map's colors are <span>s, and which of them is open at any point is worked out
    between a dozen different places, none of which can see what the others left behind.
    They do not always agree: some lines close a span that was never opened, and some open
    one and leave it, and both of those have been in the file for as long as there has been
    a file.  A browser is forgiving about it -- it ignores an end tag that closes nothing,
    and closes what is still open when the block around it ends -- so the Map has always
    looked right, and anything reading it as markup rather than displaying it (the exports,
    the PDF, a validator) has had to be as forgiving.

    This writes what the browser would have made of it: an end tag that closes nothing is
    dropped, and a span still open when its block ends is closed there, in the place the
    browser would have closed it.  Nothing else changes, and nothing about how the Map
    looks changes -- the same DOM is reached either way, just written down properly.
    """

    def __init__(self, out_file: TextIO) -> None:
        """
        Wrap the file the Map is being written to.
            :param out_file: the open file to write through to
        """
        self.out_file = out_file
        self.blocks: list[str] = []  # the containers we are inside, outermost first
        self.spans: list[int] = [0]  # spans opened inside each of them, plus the file itself

    def write(self, text: str) -> None:
        """
        Write a piece of the Map with its spans brought into step.
            :param text: the html to write
            :return: nothing
        """
        if not text:
            return

        pieces = []
        position = 0
        for tag in HTML_TAG.finditer(text):
            pieces.append(text[position : tag.start()])
            position = tag.end()
            pieces.append(self.balanced(tag.group(0)))

        pieces.append(text[position:])
        self.out_file.write("".join(pieces))

    def balanced(self, markup: str) -> str:
        """
        One tag as the browser would have it, with the spans around it brought into step.
            :param markup: the tag, as it stands in the output
            :return: what to write in its place -- "" for a tag that closes nothing, and
                the tag with any "</span>"s that its block owes written in front of it
        """
        facts = tag_facts(markup)
        tag_name = facts.name
        closing = facts.closing

        if tag_name == "span":
            if not closing:
                self.spans[-1] += 1
            elif self.spans[-1] == 0:
                return ""  # Closes nothing: the browser ignores it, and so does the file.
            else:
                self.spans[-1] -= 1
        elif tag_name in BLOCK_TAGS and not facts.self_closing:
            if closing:
                owed = self.close_block(tag_name)
                if not self.blocks or tag_name not in self.blocks:
                    return owed  # An end tag for a block that was never opened.
                self.open_block_end(tag_name)
                return f"{owed}{markup}"
            self.blocks.append(tag_name)
            self.spans.append(0)
        return markup

    def close_block(self, tag_name: str) -> str:
        """
        The end tags for every span still open inside the block now ending.
            :param tag_name: the block being closed
            :return: the "</span>"s to write before its own end tag
        """
        if tag_name not in self.blocks:
            return ""
        depth = len(self.blocks) - 1 - self.blocks[::-1].index(tag_name)
        return "</span>" * sum(self.spans[depth + 1 :])

    def open_block_end(self, tag_name: str) -> None:
        """
        Step back out to whatever contained the block now ending.
            :param tag_name: the block being closed
            :return: nothing
        """
        depth = len(self.blocks) - 1 - self.blocks[::-1].index(tag_name)
        del self.blocks[depth:]
        del self.spans[depth + 1 :]

    def finish(self) -> None:
        """
        Close whatever the file still has open, once there is nothing more to write.
            :return: nothing
        """
        still_open = sum(self.spans)
        if still_open:
            self.out_file.write("</span>" * still_open)
            self.spans = [0] * len(self.spans)


class MapWriter:
    """Both of the Map's writing rules, applied in one pass over the html.

    The Map used to be written through a BlankLineLimiter standing in front of a
    SpanBalancer, which is the honest way to say what happens to it -- and meant every
    tag in a document of several million characters was found by a regular expression
    twice and had its name taken twice, once by each of them.  On a large configuration
    that was the single most expensive thing in the build after the Map's own content.

    So the scan happens once here, and each tag is put to both rules in the order the two
    writers stood in: the limiter first, because a <br> it drops never reached the
    balancer either; then the balancer, whose own "</span>"s were never seen by the
    limiter and still are not.  Both classes keep their own write() for everything else
    that uses them, and both keep the rules themselves -- this drives them, it does not
    restate them.
    """

    def __init__(self, out_file: TextIO, max_blank_lines: int = MAX_BLANK_LINES) -> None:
        """
        Wrap the file the Map is being written to.
            :param out_file: the open file to write through to
            :param max_blank_lines: the most blank lines in a row to let through
        """
        self.out_file = out_file
        self.limiter = BlankLineLimiter(out_file, max_blank_lines)
        self.balancer = SpanBalancer(out_file)

    def write(self, text: str) -> None:
        """
        Write a piece of the Map: blank lines capped, spans balanced.
            :param text: the html to write
            :return: nothing
        """
        if not text:
            return

        limiter = self.limiter
        balancer = self.balancer
        pieces = []
        position = 0
        for tag in HTML_TAG.finditer(text):
            between = text[position : tag.start()]
            limiter.saw_text(between)
            pieces.append(between)
            position = tag.end()

            markup = tag.group(0)
            if limiter.keep_tag(markup):
                pieces.append(balancer.balanced(markup))

        trailing = text[position:]
        limiter.saw_text(trailing)
        pieces.append(trailing)

        self.out_file.write("".join(pieces))

    def finish(self) -> None:
        """
        Close whatever the file still has open, once there is nothing more to write.
            :return: nothing
        """
        self.balancer.finish()
