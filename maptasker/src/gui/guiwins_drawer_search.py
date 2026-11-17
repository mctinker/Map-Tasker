"""guiwins_drawer_search: the 'Find a command' box of the right drawer -- filter every button as the user types."""

#! /usr/bin/env python3

#                                                                                        #
# guiwins_drawer_search: finding a button among thirty.                                  #
#                                                                                        #
# The right drawer has grown past what grouping alone can keep short, so it has a box     #
# that filters it.  Typing hides every button and checkbox that does not match and        #
# opens the sections that still hold one; clearing the box puts the drawer back exactly   #
# as it was -- every section as the user had left it, and every button as visible or      #
# hidden as it was before the search began, including the ones other code hides on        #
# purpose.                                                                                #
#                                                                                        #
# WHAT A QUERY IS MATCHED AGAINST: the button's label and its tooltip.  The tooltip is    #
# what lets 'password' find the Outbound Inventory and 'undo' find Restore From History:   #
# the name of a command says what it is called and its tooltip says what it is for.       #
#                                                                                        #
# HOW IT MATCHES: each word typed must be somewhere in the label or tooltip, or -- for a   #
# word of three letters or more -- run in order through the label with other letters        #
# between ('xrf' finds Variable Xref, 'cmpf' finds Compare Files).  Every word has to       #
# match, so a second word narrows the list.                                                #
#                                                                                        #
# The elements are found by walking the drawer once, when the first query arrives, rather   #
# than being registered by the thirty places that make them: a button added tomorrow is      #
# searchable without anybody remembering to say so.                                         #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from nicegui import ui

if TYPE_CHECKING:
    from nicegui.element import Element

# A word shorter than this is matched only as a piece of the text: 'ab' running through 'Variable Manager' proves nothing.
MIN_FUZZY_LENGTH = 3


def _in_order(needle: str, haystack: str) -> bool:
    """Whether the letters of `needle` appear in `haystack` in that order, with anything between them."""
    letters = iter(haystack)
    return all(letter in letters for letter in needle)


def matches(query: str, label: str, description: str = "") -> bool:
    """Whether a command matches what was typed: every word is in its label or description, or runs through its label.

    An empty query matches everything.  Case does not matter.
    """
    text = f"{label} {description}".lower()
    name = label.lower()
    return all(
        word in text or (len(word) >= MIN_FUZZY_LENGTH and _in_order(word, name)) for word in query.lower().split()
    )


class DrawerWindow(Protocol):
    """What the search reads and writes of the window that owns the drawer."""

    drawer_sections: dict[str, bool]
    drawer_expansions: dict[str, ui.expansion]
    drawer_searching: bool
    gui_right_drawer: ui.right_drawer


@dataclass
class Command:
    """One thing in the drawer a query can find: a button or a checkbox, and the section it is in."""

    element: Element
    label: str
    description: str
    section: str  # the section's key, or "" for what is outside any section
    was_visible: bool = True


def _tooltip_text(element: Element) -> str:
    """What the tooltips under an element say."""
    return " ".join(
        str(getattr(child, "text", "") or "")
        for child in element.default_slot.children
        if isinstance(child, ui.tooltip)
    )


class DrawerSearch:
    """Filters the commands of one drawer.  Built when the drawer is, used each time the search box changes."""

    def __init__(self, window: DrawerWindow, nothing_found: Element) -> None:
        """`window` holds drawer_sections and drawer_expansions; `nothing_found` is the line shown when nothing matches."""
        self.window = window
        self.nothing_found = nothing_found
        self.commands: list[Command] | None = None
        self.searching = False
        self.sections_before: dict[str, bool] = {}

    # ---------------------------------------------------------------- what there is to find
    def _expansions(self) -> dict[str, ui.expansion]:
        return self.window.drawer_expansions

    def collect(self) -> list[Command]:
        """Every labelled button and checkbox in the drawer, each with the section it sits in."""
        drawer = self.window.gui_right_drawer
        section_of: dict[int, str] = {}
        for key, expansion in self._expansions().items():
            section_of.update({id(child): key for child in expansion.descendants()})
        commands: list[Command] = []
        for element in drawer.descendants():
            label = (
                str(getattr(element, "text", "") or "").strip() if isinstance(element, ui.button | ui.checkbox) else ""
            )
            if label:
                commands.append(Command(element, label, _tooltip_text(element), section_of.get(id(element), "")))
        return commands

    # ---------------------------------------------------------------- filtering
    def filter(self, query: str) -> None:
        """Show what matches `query` and hide the rest -- or, for an empty query, put everything back."""
        query = query.strip()
        if not query:
            self._clear()
            return
        if self.commands is None:
            self.commands = self.collect()
        if not self.searching:
            self._begin()
        found_in: set[str] = set()
        shown = 0
        for command in self.commands:
            hit = matches(query, command.label, command.description)
            command.element.visible = hit and command.was_visible
            if hit:
                shown += 1
                if command.section:
                    found_in.add(command.section)
        for key, expansion in self._expansions().items():
            expansion.visible = key in found_in
            expansion.set_value(value=key in found_in)
        self.nothing_found.visible = shown == 0

    def _begin(self) -> None:
        """Remember what the drawer looked like, so that clearing the box can give it back."""
        self.searching = True
        self.window.drawer_searching = True
        self.sections_before = dict(self.window.drawer_sections)
        for command in self.commands or []:
            command.was_visible = bool(command.element.visible)

    def _clear(self) -> None:
        """Put the drawer back as it was before the search: every button as visible as it was, every section as left."""
        if not self.searching:
            return
        for command in self.commands or []:
            command.element.visible = command.was_visible
        for key, expansion in self._expansions().items():
            expansion.visible = True
            expansion.set_value(value=self.sections_before.get(key, False))
        self.window.drawer_sections.clear()
        self.window.drawer_sections.update(self.sections_before)
        self.nothing_found.visible = False
        self.searching = False
        self.window.drawer_searching = False
