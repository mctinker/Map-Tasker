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

# Whether the GUI's "Font To Use In Output" list offers every installed font, with the
# monospaced ones sorted to the top and marked as such, or only the monospaced ones.
# Set this to False to go back to offering monospaced fonts alone -- it is the single
# switch for that behavior, and nothing else needs changing.
# Note that a proportional font will not hold the Diagram's box-drawing connectors or the
# output's indentation in alignment; that is the trade-off this opens up.
INCLUDE_PROPORTIONAL_FONTS = True

# Graphical User Interface (True) vs. CLI Command Line Interface (False)
GUI = True
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

# Whether the GUI's 'Specific Name' tab offers the "Edit Scene" and "Add Scene" buttons,
# alongside the Project/Profile/Task ones.  Set it to False and neither button is built at
# all -- the Scene pulldown itself is unaffected, since it is what every view already
# filters on.  Being a constant in this file is what makes the choice stick from one run to
# the next: nothing in the app writes it, so it stays whatever it is here until edited.
#
# Scene editing is the newest of the four and is still filling in (the Scene's own UI
# elements are not editable yet -- see sceneedit.py), which is why it is the one that ships
# behind a switch.
EDIT_SCENE = True

#  END User-modifiable global constants
