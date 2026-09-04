#! /usr/bin/env python3
"""Povide the highlighting attribute(s) based on the settings."""

#                                                                                      #
# nameattr: Format the Project/Profile/Task/Scene name with bold, highlighting or      #
#            italisized.  Also used for some utility functions.                        #
#                                                                                      #
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maptasker.src.runcfg import RunConfig


def add_name_attribute(name: str, config: RunConfig) -> str:
    """
    Format the Project/Profile?Task/Scene name with bold and/or highlighting
        Args:

            name (str): the Project/Profile/Task/Scene name
            config (RunConfig): the run's settings, for the name-styling options.

        Returns:
            str: the name with bold and/or highlighting added
    """

    # Set default values
    italicize = end_italicize = highlight = end_highlight = bold = end_bold = underline = end_underline = ""

    # Make the name bold if requested
    if config.bold:
        bold = "<b>"
        end_bold = "</b>"

    # Make the name highlighted if requested
    if config.highlight:
        highlight = "<mark>"
        end_highlight = "</mark>"

    # Make the name italicized if requested
    if config.italicize:
        italicize = "<em>"
        end_italicize = "</em>"

    # Make the name underlined if requested
    if config.underline:
        underline = "<u>"
        end_underline = "</u>"

    return f"{underline}{highlight}{bold}{italicize}{name}{end_italicize}{end_bold}{end_highlight}{end_underline}"
