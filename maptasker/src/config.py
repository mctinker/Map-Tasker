#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# config: Configuration file for MapTasker                                             #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

# ##################################################################################
#  START User-modifiable global constants
# ##################################################################################

# Define the maximum number of Action lines to continue to avoid runaway for the display
# of huge binary files
CONTINUE_LIMIT = 75
# Monospace fonts work best for if/then/else/end indentation alignment
OUTPUT_FONT = "Courier"  # OS X Default monospace font

# Graphical User Interface (True) vs. CLI Command Line Interface (False)
GUI = False
# Light vs Dark Mode (refer to colrmode.py to hardcode the output colors)
DARK_MODE = True

#
# Set up to fetch the backup file from Android device running the Tasker server.
#
# In addition, the Tasker HTTP sample Project must be installed on the Android device,
# found at...
#  (https://shorturl.at/bwCD4),
# and the server must be active on the Android device.

# This is the HTTP IP address of the Android device from which to fetch the backup.
# Example: ANDROID_IPADDR = "192.168.0.210"

ANDROID_IPADDR = ""

# This is the port number for the Android device from which to fetch the backup,
# and is specified in the Tasker HTTP Server Example project notification.
# From notification: HTTP Server Info  {"device_name":"http://192.168.0.49:1821"}
# Example: ANDROID_PORT = "1821"

ANDROID_PORT = ""

# This is the location on the Android device from which to pull the backup file
# Example: ANDROID_FILE = "/Tasker/configs/user/backup.xml"

ANDROID_FILE = ""

# ##################################################################################
#  END User-modifiable global constants
# ##################################################################################
