#! /usr/bin/env python3
"""Povide the highlighting attribute(s) based on the settings."""

#                                                                                      #
# nameattr: Format the Project/Profile/Task/Scene name with bold, highlighting or      #
#            italisized.  Also used for some utility functions.                        #
#                                                                                      #

from maptasker.src.primitem import PrimeItems


def add_name_attribute(name: str) -> str:
    """
    Format the Project/Profile?Task/Scene name with bold and/or highlighting
        Args:

            name (str): the Project/Profile/Task/Scene name

        Returns:
            str: the name with bold and/or highlighting added
    """

    # Set default values
    italicize = end_italicize = highlight = end_highlight = bold = end_bold = underline = end_underline = ""

    # Make the name bold if requested
    if PrimeItems.program_arguments["bold"]:
        bold = "<b>"
        end_bold = "</b>"

    # Make the name highlighted if requested
    if PrimeItems.program_arguments["highlight"]:
        highlight = "<mark>"
        end_highlight = "</mark>"

    # Make the name italicized if requested
    if PrimeItems.program_arguments["italicize"]:
        italicize = "<em>"
        end_italicize = "</em>"

    # Make the name underlined if requested
    if PrimeItems.program_arguments["underline"]:
        underline = "<u>"
        end_underline = "</u>"

    return f"{underline}{highlight}{bold}{italicize}{name}{end_italicize}{end_bold}{end_highlight}{end_underline}"
