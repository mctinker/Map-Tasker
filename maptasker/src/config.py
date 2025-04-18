"""User Modifiable Configutration File"""

#! /usr/bin/env python3

#                                                                                      #
# config: Configuration file for MapTasker                                             #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

#  START User-modifiable global constants

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

# This is used as the default display detail level.  It does not override the runtime option.
# This value is used if the runtime option is not set.
DEFAULT_DISPLAY_DETAIL_LEVEL = 5

# Ai Analysis prompt...This will be proceeded by 'Given the following (Project/Profile/Task) in Tasker, '
AI_PROMPT = "suggest improvements for performance and readability:"

#  END User-modifiable global constants
