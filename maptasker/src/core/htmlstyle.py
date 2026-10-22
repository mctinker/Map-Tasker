"""htmlstyle: reading the stylesheet of an authored HTML document.

Selector parsing, specificity and matching: which of a document's rules applies to which element, so htmltext
can carry the colour and weight a <style> block gives an element and not only what its own attributes say."""

from __future__ import annotations

import re

# A <style> element's rules are resolved as the description is parsed: each rule is matched
# against the elements it selects and folded into their styles, exactly as an inline "style="
# attribute is (see _push_inline_styles).  There is nowhere for a real stylesheet to go --
# the parser flattens the markup to colored text segments carrying no tags, classes or ids
# for a selector to reach -- so the matching has to happen here, while the elements the rules
# name still exist.  Only the four properties a segment can represent survive; backgrounds,
# spacing and layout are passed over the same way they are in an inline style.
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


# The <br> that parse_html_to_text_segments puts in place of every newline before feeding the
# parser.  A <style> element's content is CDATA, so those arrive as literal text in the middle
# of the CSS and have to be turned back into the line breaks they stand for.
CSS_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


# One compound selector: an optional tag name followed by any run of ".class" and "#id".
# Anything else -- an attribute selector, a pseudo-class, a sibling combinator -- cannot be
# decided about an element as it is parsed, and the rule carrying it is dropped rather than
# guessed at.
COMPOUND_SELECTOR = re.compile(r"(\*|[a-zA-Z][\w-]*)?((?:[.#][\w-]+)*)$")


SELECTOR_NAME = re.compile(r"[.#][\w-]+")


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


def _matching_brace(css: str, opening: int) -> int:
    """
    The offset of the "}" closing the block that opens at "opening", counting nested blocks.

    A rule's own block holds no braces, but an at-rule's holds whole rules -- so the first
    "}" is not necessarily the end of the block.  A block left unclosed runs to the end of
    the stylesheet, which is what a browser does with it too.

        :param css: the stylesheet text
        :param opening: offset of the "{" that opens the block
        :return: offset of the matching "}", or the length of the text if there isn't one
    """
    depth = 0
    for position in range(opening, len(css)):
        if css[position] == "{":
            depth += 1
        elif css[position] == "}":
            depth -= 1
            if depth == 0:
                return position
    return len(css)


def parse_selector(text: str) -> tuple | None:
    """
    Break a single selector into the compounds to match, or None if it isn't one we can.

    Each compound is paired with the combinator joining it to the one on its left: None for
    the leftmost, ">" for a child, " " for a descendant.  Only those two combinators are
    read; a selector using any other, or naming anything COMPOUND_SELECTOR doesn't cover, is
    refused whole rather than approximated.

        :param text: one selector, e.g. ".card h2" or "#notes > p"
        :return: a tuple of (combinator, (tag, classes, id)) pairs, or None
    """
    pieces = text.replace(">", " > ").split()
    parts = []
    combinator = None
    for piece in pieces:
        if piece == ">":
            # A child combinator with nothing to its left is malformed (CSS nesting writes
            # rules that way, and those belong to a parent rule we are not tracking).
            if not parts:
                return None
            combinator = ">"
            continue
        compound = COMPOUND_SELECTOR.fullmatch(piece)
        if not compound:
            return None
        tag = (compound.group(1) or "").lower()
        names = SELECTOR_NAME.findall(compound.group(2) or "")
        ids = [name[1:] for name in names if name.startswith("#")]
        classes = frozenset(name[1:] for name in names if name.startswith("."))
        # "*" matches everything, which comes to the same thing as naming no tag at all.
        parts.append((combinator, (tag if tag and tag != "*" else None, classes, ids[-1] if ids else None)))
        combinator = " "
    return tuple(parts) if parts else None


def selector_specificity(selector: tuple) -> tuple[int, int, int]:
    """
    A selector's specificity as (ids, classes, tags), which sorts the way CSS ranks rules.

        :param selector: a selector as returned by parse_selector
        :return: the number of ids, classes and tag names it names
    """
    ids = sum(1 for _, (_, _, element_id) in selector if element_id)
    classes = sum(len(class_names) for _, (_, class_names, _) in selector)
    tags = sum(1 for _, (tag, _, _) in selector if tag)
    return (ids, classes, tags)


def parse_stylesheet(css: str) -> list[tuple[tuple[int, int, int], tuple, str]]:
    """
    Pull the usable rules out of a stylesheet, as (specificity, selector, declarations).

    At-rules are skipped along with everything inside them: @media's condition can't be
    evaluated here (a description written for a dark theme states its dark colors inside one,
    and applying those unconditionally would be a guess at which theme is in force), and
    @import, @font-face and @keyframes carry nothing a text segment could use.

        :param css: the text content of a <style> element
        :return: one entry per selector of every rule we can evaluate, in source order
    """
    css = CSS_COMMENT.sub(" ", CSS_LINE_BREAK.sub("\n", css))
    rules = []
    position = 0
    while (opening := css.find("{", position)) != -1:
        # A statement at-rule ("@import ...;", "@charset ...;") ends at its semicolon rather
        # than at a block, so everything up to the last one belongs to it and not to the rule
        # about to open -- take only what follows, or an @import at the top of a stylesheet
        # swallows the first real rule after it.
        prelude = css[position:opening].rpartition(";")[2].strip()
        closing = _matching_brace(css, opening)
        declarations = css[opening + 1 : closing]
        position = closing + 1
        if prelude.startswith("@"):
            continue
        for selector_text in prelude.split(","):
            selector = parse_selector(selector_text)
            if selector:
                rules.append((selector_specificity(selector), selector, declarations))
    return rules


def _compound_matches(compound: tuple, element: tuple) -> bool:
    """
    Whether one compound selector describes one open element.

        :param compound: (tag, classes, id) from a parsed selector
        :param element: (tag, classes, id) of the element to test
        :return: True if the element is one the compound selects
    """
    tag, class_names, element_id = compound
    element_tag, element_classes, element_element_id = element
    if tag and tag != element_tag:
        return False
    if element_id and element_id != element_element_id:
        return False
    return class_names <= element_classes


def selector_matches(selector: tuple, element_stack: list[tuple]) -> bool:
    """
    Whether a selector matches the innermost open element, given everything it sits inside.

    Matched right to left, the way a browser does it: the last compound has to describe the
    element itself, and each one before it has to be found among that element's ancestors --
    the nearest one for a child combinator, any of them for a descendant.

        :param selector: a selector as returned by parse_selector
        :param element_stack: the open elements as (tag, classes, id), innermost last
        :return: True if the selector selects the innermost open element
    """
    index = len(element_stack) - 1
    if index < 0 or not _compound_matches(selector[-1][1], element_stack[index]):
        return False

    # Walk leftward through the selector and outward through the ancestors together.
    for position in range(len(selector) - 1, 0, -1):
        combinator, compound = selector[position][0], selector[position - 1][1]
        index -= 1
        if combinator == ">":
            if index < 0 or not _compound_matches(compound, element_stack[index]):
                return False
        else:
            while index >= 0 and not _compound_matches(compound, element_stack[index]):
                index -= 1
            if index < 0:
                return False
    return True
