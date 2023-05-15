#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# config: Configuration file for MapTasker                                                   #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

# Add the following statement to your Terminal Shell configuration file (BASH, Fish, etc.
#  to eliminate the runtime msg: DEPRECATION WARNING: The system version of Tk is deprecated and may be removed...
#  'export TK_SILENCE_DEPRECATION = 1' (without quotes)


# ####################################################################################################
#  START User-modifiable global constants
# ####################################################################################################

CONTINUE_LIMIT = 50  # Define the maximum number of Action lines to continue to avoid runaway for huge binary files
# Monospace fonts work best for if/then/else/end indentation alignment
OUTPUT_FONT = "Courier"  # OS X Default monospace font
# OUTPUT_FONT = 'Roboto Regular'    # Google monospace font
GUI = False  # Graphical User Interface (True) vs. CLI Command Line Interface (False)
DARK_MODE = (
    True  # Light vs Dark Mode (refer to colrmode.py to hardcode the output colors)
)

# ####################################################################################################
#  END User-modifiable global constants
# ####################################################################################################
