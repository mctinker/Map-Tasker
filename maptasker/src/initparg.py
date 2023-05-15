#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# runcli: process command line interface arguments for MapTasker                            #
#                                                                                            #
# Add the following statement (without quotes) to your Terminal Shell configuration file     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                          #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                           #
#  "export TK_SILENCE_DEPRECATION = 1"                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from maptasker.src.sysconst import FONT_TO_USE


#######################################################################################
# Initialize Program runtime arguments to default values
# #######################################################################################
# Command line parameters
def initialize_runtime_arguments() -> dict:
    """
    Initialize the program's runtime arguments...as a dictionary of options
        :return: runtime arguments in dictionary
    """
    return {
        "display_detail_level": 1,
        "single_task_name": "",
        "single_profile_name": "",
        "single_project_name": "",
        "display_profile_conditions": False,
        "display_preferences": False,
        "display_taskernet": False,
        "debug": False,
        "font_to_use": FONT_TO_USE,
        "gui": False,
    }
