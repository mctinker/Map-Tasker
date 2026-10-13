"""The scripts and stylesheets MapTasker sends to the browser, kept as files rather than strings."""

#! /usr/bin/env python3

#                                                                                      #
# assettext: read a text asset (maptasker/assets/js, assets/css) and fill in its holes. #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# WHY THESE ARE FILES
#
# A few hundred lines of JavaScript inside a Python string are not JavaScript to anything
# that looks at them: an editor does not highlight them, a linter does not parse them, a
# syntax slip is found by a user clicking in a browser, and the Python functions that carry
# them are as long as the script is, which is what the complexity ratchet then counts.  As
# files under maptasker/assets they are all of those things, and the Python side shrinks to
# the part that is Python: what goes into the holes.
#
# THE HOLES
#
# A script that needs a value from Python -- an element id, a JSON model, a CSS class --
# carries a placeholder spelled __LIKE_THIS__ where the value goes.  That is a valid
# JavaScript identifier, so the file still parses as it stands, and nothing else in the
# scripts is spelled that way.  render() fills them in ONE pass: a value that itself happens
# to contain something shaped like a placeholder (a Task named "__ID__", a search term) is
# left exactly as it is, which a chain of str.replace calls cannot promise.
#
# render() insists that the placeholders the file has and the values it is handed are the
# same set, in both directions.  A placeholder nobody fills would reach the browser as an
# undefined variable; a value nobody asked for is a script and a caller that have drifted
# apart.  Either is an error here, at the call, rather than a blank panel later.
#
# COST
#
# The file is read once per process and the text kept (text() is cached), and it is cut at its
# placeholders once as well, so after the first use a script costs a join over pieces already in
# memory -- no more than the string constant it replaced cost to fill in.  This module imports
# nothing from the rest of MapTasker and nothing from NiceGUI, so the core (mapjump, diagintr)
# can use it as it can any other low-level helper.
from __future__ import annotations

import re
from functools import cache
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"

_PLACEHOLDER = re.compile(r"__([A-Z][A-Z0-9_]*[A-Z0-9])__")


@cache
def text(relative: str) -> str:
    """The text of one asset, as it is on disk -- read once, then kept.

    Args:
        relative (str): the path under maptasker/assets, e.g. "js/diagram_jump.js".

    Returns:
        str: the file's content, unchanged.
    """
    return (ASSETS_DIR / relative).read_text(encoding="utf-8")


@cache
def _pieces(relative: str) -> tuple[str, ...]:
    """A file cut at its placeholders: literal text at the even positions, a placeholder's name at the odd.

    Done once per file, so that filling it in is a join over pieces already in memory rather
    than a regular-expression search over the whole text every time.
    """
    return tuple(_PLACEHOLDER.split(text(relative)))


@cache
def placeholders(relative: str) -> frozenset[str]:
    """The names of the placeholders a file carries, without their underscores."""
    return frozenset(_pieces(relative)[1::2])


def render(relative: str, **values: str) -> str:
    """One asset with every placeholder replaced by the value of the same name.

    Args:
        relative (str): the path under maptasker/assets.
        **values (str): the text for each placeholder, by name -- ``ANCHOR_ID='"c12"'`` fills
            ``__ANCHOR_ID__``.  The caller makes each one safe for where it lands (json.dumps
            for a JavaScript literal), exactly as it did when it built the string itself.

    Returns:
        str: the finished script or stylesheet.

    Raises:
        KeyError: if the values and the file's placeholders are not the same set.
    """
    wanted = placeholders(relative)
    if wanted != values.keys():
        missing, extra = sorted(wanted - values.keys()), sorted(values.keys() - wanted)
        msg = f"{relative}: placeholders without a value {missing}, values without a placeholder {extra}"
        raise KeyError(msg)
    pieces = _pieces(relative)
    return "".join([values[piece] if position & 1 else piece for position, piece in enumerate(pieces)])
