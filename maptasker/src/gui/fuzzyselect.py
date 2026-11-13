"""fuzzyselect: a NiceGUI dropdown that finds options by fuzzy match as you type."""

#! /usr/bin/env python3

#                                                                                        #
# fuzzyselect: ui.select with a filter box that ranks, rather than keeps.                #
#                                                                                        #
# NiceGUI's own select, given with_input=True, keeps the options that CONTAIN what is typed  #
# and drops the rest, in the order they were in.  For a list as long as the installed fonts,   #
# that means typing 'ari' offers whatever has 'ari' inside it, with Arial wherever it happened     #
# to fall.  This one ranks instead: what starts with it first, then what has a word that starts     #
# with it, then what has it inside, then a near miss ('ariel' still finds Arial), then letters       #
# that appear in order close together.  fuzzy_match.js says exactly how; it is linked in the page's  #
# head (webassets.head_html), and the component below is NiceGUI's select.js with its filter swapped. #
#                                                                                        #
# Everything else is ui.select's: the options, the value, on_change, tooltips, the keyboard.          #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

from nicegui import ui

from maptasker.src.core import assettext

COMPONENT = assettext.ASSETS_DIR / "components" / "fuzzy_select.js"


class FuzzySelect(ui.select, component=COMPONENT):
    """A ui.select whose filter box fills the list with fuzzy matches, best first.

    Made the way ui.select is, and with with_input=True: without the input field there is nothing to type into.
    """
