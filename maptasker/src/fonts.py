#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# fonts:Get/set up fonts to use in output                                              #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import sys
from tkinter import Tk, font

# from maptasker.src.nameattr import get_tk
from maptasker.src.primitem import PrimeItems


# Get all monospace ("f"=fixed) fonts
def get_fonts(save_fonts: bool) -> dict:
    """
    Get and set up the available monospace fonts and optionally save them
        Args:
            save_fonts (bool): True if we are to save the fonts

        Returns:
            dict: list of avilable monospace fonts
    """
    # get_tk()  # Get the Tkinter root window
    _ = Tk()
    fonts = [font.Font(family=f) for f in font.families()]
    our_font = PrimeItems.program_arguments["font"]

    # Set up our list of fonts, including Courier
    mono_fonts = ["Courier"]

    # If the font requested is 'help', then just display the fonts and exit
    if our_font == "help":
        print("Valid monospace fonts...")
        print('  "Courier" is the default')

    # Go thru list of fonts from tkinter
    PrimeItems.mono_fonts = {}
    for f in fonts:
        # Monospace only
        if f.metrics("fixed") and "Wingding" not in f.actual("family"):
            if our_font == "help":
                print(f'  "{f.actual("family")}"')
            elif save_fonts:
                PrimeItems.mono_fonts[f.name] = f.actual("family")
            mono_fonts.append(f.actual("family"))
    if our_font == "help":
        sys.exit(0)

    del fonts
    return mono_fonts
