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
from tkinter import Tk, font


# Get all monospace ("f"=fixed) fonts
def get_fonts(primary_items: dict, save_fonts: bool) -> dict:
    """_summary_
    Get and set up the available monospace fonts and optionally save them
        Args:
            primary_items (dict): Our key program items.  See mapit.py for details
            save_fonts (bool): True if we are to save the fonts

        Returns:
            dict: list of avilable monospace fonts
    """
    _ = Tk()
    fonts = [font.Font(family=f) for f in font.families()]
    our_font = primary_items["program_arguments"]["font"]

    # Set up our list of fonts, including Courier
    mono_fonts = ["Courier"]
    
    # If the font requested is 'help', then just display the fonts and exit
    if our_font == "help":
        print("Valid monospace fonts...")
        print('  "Courier" is the default')
        
    # Go thru list of fonts from tkinter
    for f in fonts:
        # Monospace only
        if f.metrics("fixed") and "Wingding" not in f.actual("family"):
            if our_font == "help":
                print(f'  "{f.actual("family")}"')
            elif save_fonts:
                primary_items["mono_fonts"][f.name] = f.actual("family")
            mono_fonts.append(f.actual("family"))
    if our_font == "help":
        exit(0)
    return mono_fonts
