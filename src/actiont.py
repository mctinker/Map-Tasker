#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# actiont: Task Action table/dictionary of keywords for MapTasker                            #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
# The following dictionary provides the strings for various specific code Actions which need to be looked up.
# Example: xml code '175' (Power Mode) Int value of '2' = 'Toggle' in list of strings 'Normal', 'Battery Saver', 'Toggle'
lookup_values = {
    "4s": {0: "Highest", 1: "High", 2: "Normal", 3: "Low", 4: "Lowest"},
    "7e": {0: "Any", 1: "MMS", 2: "SMS"},
    "10s": {0: "Any", 1: "AC", 2: "USB", 3: "Wireless", 4: "Other"},
    "30s": {0: "Any", 1: "Mic", 2: "No Mic"},
    "40s": {0: "Incoming", 1: "Outgoing", 2: "Any"},
    "47": {
        0: "Overlay",
        1: "Overlay, Blocking",
        2: "Overlay, Blocking, Full Window",
        3: "Dialog",
        4: "Dialog, Dim Behind Heavy",
        5: "Dialog, Dim Behind",
        6: "Activity",
        7: "Activity, No Bar",
        8: "Activity, No Status",
        9: "Activity, No Bar, No Status, No Nav",
    },
    "48": {
        0: "System",
        1: "None",
        2: "Fade",
        3: "Bottom Fade",
        4: "Left",
        5: "Right",
        6: "Top",
        7: "Bottom",
        8: "Left Roll",
        9: "Right Roll",
        10: "Scale",
    },
    "51": {0: "Replace Existing", 1: "Start", 2: "End"},
    "53": {
        0: "Clear Cache",
        1: "Clear History",
        2: "Find",
        3: "Find Next",
        4: "Go Back",
        5: "Go Forward",
        6: "Load URL",
        7: "Page Button",
        8: "Page Down",
        9: "Page Top",
        10: "Page Up",
        11: "Reload",
        12: "Show Zoom Controls",
        13: "Stop Loading",
        14: "Zoom In",
        15: "Zoom Out",
    },
    "57": {0: "All", 1: "Portrait", 2: "Landscape"},
    "64": {
        0: "Disable Compass",
        1: "Disable Rotation Gestures",
        2: "Disable Tilt Gestures",
        3: "Disable Zoom Gestures",
        4: "Enable Compass",
        5: "Enable Rotation Gestures",
        6: "Enable Tilt Gestures",
        7: "Enable Zoom Gestures",
        8: "Hide Roads",
        9: "Hide Satellite",
        10: "Hide Traffic",
        11: "Hide Zoom Controls",
        12: "Move To Marker",
        13: "Move To Marker Animated",
        14: "Move To Point",
        15: "Move To Point Animated",
        16: "Set Zoom",
        17: "Show Roads",
        18: "Show Satellite",
        19: "Show Traffic",
        20: "Show Zoom Controls",
        21: "Zoom In",
        22: "Zoom Out",
    },
    "65": {0: "False", 1: "True", 2: "Toggle"},
    "69": {
        0: "Button",
        1: "Checkbox",
        2: "Image",
        3: "Text",
        4: "TextEdit",
        5: "Doodle",
        6: "Map",
        7: "Menu",
        8: "Number Picker",
        9: "Oval",
        10: "Rectangle",
        11: "Slider",
        12: "Spinner",
        13: "Switch",
        14: "Toggle",
        15: "Video",
        16: "Webview",
    },
    "109": {0: "Launcher", 1: "Lockscreen", 2: "All"},
    "119": {0: "Point", 1: "StreetView", 2: "Navigate To"},
    "120s": {
        0: "Face Up",
        1: "Face Down",
        2: "Standing Up",
        3: "Upside Down",
        4: "Left Side",
        5: "Right Side",
    },
    "122s": {0: "Portrait", 1: "Landscape"},
    "133": {
        0: "Service Check (MS)",
        1: "BT Scan Period",
        2: "Wifi Scan Period",
        3: "GPS Check Period",
        4: "Net Location Period",
        5: "GPS Check Timeout",
        6: "Display Off, All Checks",
        7: "Display Off, All Checks Timeout",
        8: "BT Check Min Timeout",
        9: "Wifi Check Min Timeout",
        10: "Camera Delay (MS)",
        11: "Cell Workaround",
        12: "Net/Cell Wake Screen",
        13: "Run In Foreground",
        14: "Accelerometer",
        15: "Proximity Sensor",
        16: "Light Sensor",
        17: "Pressure Sensor",
        18: "Temperature Sensor",
        19: "Humidity Sensor",
        20: "Magnetic Sensor",
        21: "Step Sensor",
        22: "Use Reliable Alarms",
        23: "Run Log",
        24: "Debug To System Log",
        25: "Debug To Internal Storage",
        26: "Lock Code",
        27: "App Check Method",
        28: "Use Motion Detection",
    },
    "135": {
        0: "Action Number",
        1: "Action Label",
        2: "Top of Loop",
        3: "End of Loop",
        4: "End of If",
    },
    "147": {0: "UI", 1: "Monitor", 2: "Action", 3: "Misc"},
    "150s": {
        0: "Any",
        1: "Application Specific",
        2: "Audio",
        3: "CDC",
        4: "Communications",
        5: "Content Security",
        6: "Content Smart Card",
        7: "HID / Keyboartd",
        8: "HID / Mouse",
        9: "HID / Other",
        10: "Mass Storage",
        11: "Wireless Miscellaneous",
        12: "Per Interface",
        13: "Physical",
        14: "Printer",
        15: "Digital Camera",
        16: "Vendor Specific",
        17: "Video",
        18: "Wireless Controller",
    },
    "153": {0: "Task", 1: "Configuration"},
    "153a": {0: "Source"},
    "156": {0: "Tasker"},
    "156a": {0: "English", 1: "German"},
    "160": {0: "Yes", 1: "No", 2: "Any"},
    "162": {0: "1st", 1: "2nd", 2: "3rd"},
    "162a": {0: "Active", 1: "Inactive", 2: "Disabled"},
    "165": {
        0: "Snooze Current",
        1: "Disable Current",
        2: "Disable By Label",
        3: "Disable By Time",
        4: "Disable Any",
    },
    "171": {
        0: "Call",
        1: "System",
        2: "Ringer",
        3: "Media",
        4: "Alarm",
        5: "Notification",
    },
    "173": {0: "Allow All", 1: "Allow", 2: "Deny All", 3: "Deny"},
    "175": {0: "Normal", 1: "Battery Saver", 2: "Toggle"},
    "185": {
        0: "Black and White",
        1: "Enhance Blue",
        2: "Enhance Green",
        3: "Greyscale",
        4: "Set Alpha",
    },
    "190": {0: "Horizontal", 1: "Vertical"},
    "191": {0: "Left", 1: "Right"},
    "191a": {0: "45", 1: "90", 2: "135", 3: "180"},
    "192": {0: "Alarm", 1: "Notification", 2: "Ringer"},
    "194": {
        0: "Status",
        1: "Horizontal Position",
        2: "Vertical Position",
        3: "Width",
        4: "Height",
    },
    "195": {
        0: "Element Position",
        1: "Element Size",
        2: "Value",
        3: "Element Visibility",
        4: "Element Depth",
        5: "Maximum Value",
    },
    "235": {0: "Global", 1: "Secure", 2: "System"},
    "310": {0: "Off", 1: "Vibrate"},
    "312": {
        0: "No Interruptions",
        1: "Priority",
        2: "Allow All",
        3: "Alarms",
        4: "Custom Setting",
        5: "Query",
    },
    "313": {0: "Mode", 1: "Vibrate", 2: "Sound"},
    "314": {0: "Credentials", 1: "Biometric"},
    "316": {
        0: "Normal",
        1: "Small",
        2: "Smaller",
        3: "Smallest",
        4: "Large",
        5: "Larger",
        6: "Largest",
    },
    "318": {
        0: "Off",
        1: "Portrait",
        2: "Portrait Reverse",
        3: "Landscape",
        4: "Landscape Reverse",
    },
    "324": {0: "Remote Folder", 1: "Query"},
    "324a": {0: "Both", 1: "Files", 2: "Folders"},
    "325": {0: "Trash", 1: "Remove From Trash"},
    "325a": {0: "File ID", 1: "Remote Path"},
    "339": {
        0: "GET",
        1: "POST",
        2: "HEAD",
        3: "PUT",
        4: "PATCH",
        5: "Delete",
        6: "OPTIONS",
        7: "TRACE",
    },
    "340": {0: "Connect", 1: "Disconnect", 2: "Pair", 3: "Unpair (Forget)"},
    "341": {
        0: "Connection Type",
        1: "Mobile Data Enabled",
        2: "Wifi Hidden",
        3: "Wifi MAC",
        4: "Wifi RSSI",
        5: "Wifi SSID",
        6: "BT Paired Addresses",
        7: "BT Device Connected",
        8: "BT Device Name",
        9: "BT Device Class Name",
        10: "Auto Sync",
        11: "Wifi IP Address",
    },
    "342": {
        0: "Parent Dir",
        1: "Mopdified",
        2: "Name",
        3: "Size",
        4: "Type",
        5: "Exists",
        6: "MD5",
        7: "Base 64",
    },
    "343": {
        0: "Music File Artist Tag",
        1: "Music File Duration Tag",
        2: "Music File Title Tag",
        3: "Music Playing Position",
        4: "Music Playing Position Millis",
    },
    "344": {
        0: "Calendar Calendar",
        1: "Calendar Title",
        2: "Calendar Description",
        3: "Calendar Location",
        4: "Calendar Start",
        5: "Calendar End",
        6: "Calendar All Day",
        7: "Calendar Available",
        8: "App Name",
        9: "Package Version",
        10: "Package Version Label",
        11: "Time Package",
    },
    "345": {0: "Length"},
    "346": {
        0: "Contact Address, Home",
        1: "Contact Address, Work",
        2: "Contact Birthday",
        3: "Contact Email",
        4: "Contact Name",
        5: "Contact Nickname",
        6: "Contact Organization",
        7: "Contact Photo URl",
        8: "Contact Thumb URl",
    },
    "347": {
        0: "Action",
        1: "Event",
        2: "State",
        3: "Global",
        4: "Local",
        5: "Profiles",
        6: "Scenes",
        7: "Tasks",
        8: "Timer Widget Remaining",
        9: "Current Task Name",
    },
    "348": {
        0: "AutoRotate",
        1: "Orientation",
        2: "DPI",
        3: "Available Resolution",
        4: "Hardware Resolution",
        5: "Is Locked",
        6: "Is Securely Locked",
        7: "Display Density",
        8: "Navigation Bar Height",
        9: "Navigation Bar Top Offset",
        10: "Navigation Bar Top Offset",
        11: "Status Bar Offset",
    },
    "349": {0: "Android ID", 1: "User ID"},
    "351": {0: "OAuth 2.0", 1: "Username and Password"},
    "358": {0: "Single Device", 1: "Paired Devices", 2: "Scan Devices"},
    "363": {
        0: "Auto",
        1: "2G",
        2: "3G",
        3: "4G",
        4: "2G and 3G",
        5: "3G and 4G",
        6: "5G",
        7: "3G and 4G and 5G",
        8: "4G and 5G",
    },
    "368": {0: "Normal", 1: "Satellite", 2: "Terrain", 3: "Hybrid", 4: "None"},
    "369": {
        0: "Remove Duplicates",
        1: "Reverse",
        2: "Rotate Left",
        3: "Rotate Right",
        4: "Shuffle",
        5: "Sort Alpha",
        6: "Sort Alpha, Reverse",
        7: "Sort Alpha Caseless",
        8: "Sort Alpha Caseless, Reverse",
        9: "Sort Shortest First",
        10: "Sort Longest First",
        11: "Sort Numeric, Integer",
        12: "Sort Numeric",
        13: "Floating-Point",
        14: "Squash",
    },
    "374": {0: "Start", 1: "Stop", 2: "Query"},
    "378": {0: "Select Single Item", 1: "Multiple Choices"},
    "383": {0: "Connectivity", 1: "NFC", 2: "Volume", 3: "WiFi", 4: "Media Output"},
    "384": {0: "Add/Edit", 1: "Delete"},
    "384a": {0: "Button", 1: "Toggle", 2: "Range", 3: "Toggle Range", 4: "No Action"},
    "386": {0: "Disallow", 1: "Allow"},
    "391": {0: "Show/Update", 1: "Dismiss"},
    "391a": {0: "Animation", 1: "Progress Bar"},
    "393": {0: "Simple", 1: "Format"},
    "394": {
        0: "Custom",
        1: "Now (Current Date and Time)",
        2: "Milliseconds Since Epoch",
        3: "Seconds Since Epoch",
        4: "ISO 8601",
        5: "Milliseconds Since Epoch UTC",
        6: "Seconds Since Epoch UTC",
    },
    "394a": {0: "None", 1: "Seconds", 2: "Minutes", 3: "Hours", 4: "Days"},
    "396": {0: "Simple", 1: "Regex"},
    "412": {
        0: "Alphabetic",
        1: "Alphabetic, Reverse",
        2: "Directory Then File",
        3: "File Extension",
        4: "File Extension, Reverse",
        5: "File Then Directory",
        6: "Modification Date",
        7: "Modification Date, Reverse",
        8: "Size",
        9: "Size Reverse",
    },
    "426": {0: "Disconnect", 1: "Reassociate", 2: "Reconnect"},
    "427": {0: "Default", 1: "Never While Plugged", 2: "Never"},
    "431": {
        0: "Start",
        1: "Stop",
        2: "Stop All",
        3: "Add To Keep Running",
        4: "Remove From Keep Running",
        5: "Query",
        6: "Toggle",
    },
    "443": {
        0: "Next",
        1: "Pause",
        2: "Previous",
        3: "Toggle Pause",
        4: "Stop",
        5: "Play [Simulated Only]",
        6: "Rewind",
        7: "Fast Forward",
    },
    "455": {
        0: "Default",
        1: "Microphone",
        2: "Call Outgoing",
        3: "Call Incoming",
        4: "Call",
    },
    "455a": {0: "MP4", 1: "3GPP", 2: "AMR Narrowband", 3: "AMR Wideband"},
    "490": {0: "Grab", 1: "Release"},
    "512": {0: "Expanded", 1: "Collapsed"},
    "523": {
        0: "Red",
        1: "Green",
        2: "Blue",
        3: "Yellow",
        4: "Turquoise",
        5: "Purple",
        6: "Orange",
        7: "Pink",
        8: "White",
    },
    "544": {0: "End", 1: "Pause", 2: "Resume", 3: "Reset", 4: "Update"},
    "552": {0: "Icon", 1: "Text", 2: "Icon and Text"},
    "566": {0: "Default", 1: "Off", 2: "On"},
    "595": {
        0: "Normal Text",
        1: "Caps / Word",
        2: "Caps / All",
        3: "Numeric / Decimal",
        4: "Numeric / Integer",
        5: "Password",
        6: "Phone Number",
        7: "Passcode",
    },
    "596": {
        0: "Bytes to Kilobytes",
        1: "Bytes to Megabytes",
        2: "Bytes to Gigabytes",
        3: "Date Time to Seconds",
        4: "Seconds to Date Time",
        5: "Seconds to Medium Date Time",
        6: "Seconds to Long Date Time",
        7: "HTML to Text",
        8: "Celsius to Fahrenheit",
        9: "Fahrenheit to Celsius",
        10: "Centimeters to Inches",
        11: "Inches to Centimeters",
        12: "Meters to Feet",
        13: "Feet to Meters",
        14: "Kilograms to Pounds",
        15: "Pounds to Kilograms",
        16: "Kilometers to Miles",
        17: "Miles to Kilometers",
        18: "URL Decode",
        19: "URL Encode",
        20: "Binary to Decimal",
        21: "Decimal to Binary",
        22: "Hex to Decimal",
        23: "Decimal to Hex",
        24: "Base65 Encode",
        25: "Base65 Decode",
        26: "To MD5 Digest",
        27: "To SHA1 Digest",
        28: "To Lower Case",
        29: "To Upper Case",
        30: "To Uppercase First",
    },
    "612": {
        0: "Goto",
        1: "Load",
        2: "Pause",
        3: "Play",
        4: "Resume",
        5: "Set Zoom",
        6: "Back",
        7: "Forward",
        8: "Stop",
        9: "Toggle",
    },
    "665": {0: "Delete"},
    "815": {
        0: "Package",
        1: "App",
        2: "Activity",
        3: "Receiver",
        4: "Services",
        5: "Provider",
    },
    "820": {
        0: "Never",
        1: "With AC Power",
        2: "With USB Power",
        3: "With AC or USB Power",
        4: "With Wireless Power",
        5: "With Wireless or AC Power",
        6: "With Wireless or USB Power",
        7: "With Wireless",
        8: "AC or USB Power",
    },
    "877": {
        0: "None",
        1: "Default",
        2: "Alt",
        3: "Browsable",
        4: "Car Dock",
        5: "Desk Dock",
        6: "Home",
        7: "Info",
        8: "Launcher",
        9: "Preference",
        10: "Selected Alt",
        11: "Tab",
        12: "Text",
        13: "Cardboard",
    },
    "877a": {0: "Broadcast Receiver", 1: "Activity", 2: "Service"},
    "901": {0: "GPS", 1: "Net", 2: "Any"},
    "903": {0: "Free Form", 1: "Web Search"},
    "905": {0: "Off", 1: "Device Only", 2: "Battery Saving", 3: "High Accuracy"},
    "906": {
        0: "Off",
        1: "Hide Status Bar",
        2: "Hide Navigation Bar",
        3: "Hide Both",
        4: "Toggle Last",
    },
    "909": {0: "Starred", 1: "Frequent", 2: "Starred, Frequent"},
    "910": {
        0: "View",
        1: "Clear Missed Calls",
        2: "Clear Incoming Calls",
        3: "Clear Outgoing Calls",
        4: "Clear All",
        5: "Mark All Acknowledged",
        6: "Mark All Read",
    },
    "2079e": {0: "Volume Up", 1: "Volume Down", 2: "Volume Up Or Down"},
    "2081e": {0: "Playing or Not Playing", 1: "Playing", 2: "Not Playing"},
    "3001e": {0: "Left-Right", 1: "Up-Down", 2: "Backwards-Forwards"},
    "3001ea": {0: "Very Low", 1: "Low", 2: "Medium", 3: "High", 4: "Very High"},
    "3001eb": {0: "Very Short", 1: "Short", 2: "Medium", 3: "Long", 4: "Very Long"},
    "switch_set": {0: "Off", 1: "On", 2: "Toggle"},
}
