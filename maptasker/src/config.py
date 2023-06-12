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

# Define the maximum number of Action lines to continue to avoid runaway for the display of huge binary files
CONTINUE_LIMIT = 50
# Monospace fonts work best for if/then/else/end indentation alignment
OUTPUT_FONT = "Courier"  # OS X Default monospace font
# OUTPUT_FONT = 'Roboto Regular'    # Google monospace font

# Graphical User Interface (True) vs. CLI Command Line Interface (False)
GUI = False

# Light vs Dark Mode (refer to colrmode.py to hardcode the output colors)
DARK_MODE = True

#
# Set up to fetch the backup file from Android device running the Tasker server
#
# The following two parameters must both be filled in for the fetch to work:
#   BACKUP_FILE_HTTP is the Tasker server ip address and port number on the Android device from which to fetch the file
#   BACKUP_FILE_LOCATION is the location of the backup file on the Android device
#
# In addition, the Tasker HTTP sample Project must be active on the Android device
#  (https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example),
# and the server must be active.

# This is the HTTP IP address and port number (e.g. 1821) that Tasker assigns to the server on the device containing the backup file to get.
# Example: BACKUP_FILE_HTTP = "http://192.168.0.210:1821" (note: not "https")

BACKUP_FILE_HTTP = ""

# This is the location on the Android device from which to pull the backup file
# Example: BACKUP_FILE_LOCATION = "/Tasker/configs/user/backup.xml"

BACKUP_FILE_LOCATION = ""

# ####################################################################################################
#  END User-modifiable global constants
# ####################################################################################################
