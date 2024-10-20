# sourcery skip: avoid-global-variables
#! /usr/bin/env python3

#                                                                                      #
# actiont: Task Action table/dictionary of keywords for MapTasker                      #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
# The following dictionary provides the strings for various specific code Actions which
# need to be looked up.
# actionc.py entries that have a [xx, l, xx] represent a lookup (l entry) into this
# dictionary.
# The entries in each list is the value for Int of 0, 1, 2, etc. .
# Example: xml code '175' (Power Mode) Int value of '2' = 'Toggle' in list of strings
# 'Normal', 'Battery Saver', 'Toggle'.
lookup_values = {
    "4s": ["Highest", "High", "Normal", "Low", "Lowest"],
    "7e": ["Any", "MMS", "SMS"],
    "10s": ["Any", "AC", "USB", "Wireless", "Other"],
    "30s": ["Any", "Mic", "No Mic"],
    "40s": ["Incoming", "Outgoing", "Any"],
    "47": [
        "Overlay",
        "Overlay, Blocking",
        "Overlay, Blocking, Full Window",
        "Dialog",
        "Dialog, Dim Behind Heavy",
        "Dialog, Dim Behind",
        "Activity",
        "Activity, No Bar",
        "Activity, No Status",
        "Activity, No Bar, No Status",
        "Activity, No Bar, No Status, No Nav",
    ],
    "48": [
        "System",
        "None",
        "Fade",
        "Bottom Fade",
        "Left",
        "Right",
        "Top",
        "Bottom",
        "Left Roll",
        "Right Roll",
        "Scale",
    ],
    "51": ["Replace Existing", "Start", "End"],
    "53": [
        "Clear Cache",
        "Clear History",
        "Find",
        "Find Next",
        "Go Back",
        "Go Forward",
        "Load URL",
        "Page Button",
        "Page Down",
        "Page Top",
        "Page Up",
        "Reload",
        "Show Zoom Controls",
        "Stop Loading",
        "Zoom In",
        "Zoom Out",
    ],
    "57": ["All", "Portrait", "Landscape"],
    "64": [
        "Disable Compass",
        "Disable Rotation Gestures",
        "Disable Tilt Gestures",
        "Disable Zoom Gestures",
        "Enable Compass",
        "Enable Rotation Gestures",
        "Enable Tilt Gestures",
        "Enable Zoom Gestures",
        "Hide Roads",
        "Hide Satellite",
        "Hide Traffic",
        "Hide Zoom Controls",
        "Move To Marker",
        "Move To Marker Animated",
        "Move To Point",
        "Move To Point Animated",
        "Set Zoom",
        "Show Roads",
        "Show Satellite",
        "Show Traffic",
        "Show Zoom Controls",
        "Zoom In",
        "Zoom Out",
    ],
    "65": ["False", "True", "Toggle"],
    "69": [
        "Button",
        "Checkbox",
        "Image",
        "Text",
        "TextEdit",
        "Doodle",
        "Map",
        "Menu",
        "Number Picker",
        "Oval",
        "Rectangle",
        "Slider",
        "Spinner",
        "Switch",
        "Toggle",
        "Video",
        "Webview",
    ],
    "109": ["Launcher", "Lockscreen", "All"],
    "119": ["Point", "StreetView", "Navigate To"],
    "120s": [
        "Face Up",
        "Face Down",
        "Standing Up",
        "Upside Down",
        "Left Side",
        "Right Side",
    ],
    "122s": ["Portrait", "Landscape"],
    "133": [
        "Service Check (MS)",
        "BT Scan Period",
        "Wifi Scan Period",
        "GPS Check Period",
        "Net Location Period",
        "GPS Check Timeout",
        "Display Off, All Checks",
        "Display Off, All Checks Timeout",
        "BT Check Min Timeout",
        "Wifi Check Min Timeout",
        "Camera Delay (MS)",
        "Cell Workaround",
        "Net/Cell Wake Screen",
        "Run In Foreground",
        "Accelerometer",
        "Proximity Sensor",
        "Light Sensor",
        "Pressure Sensor",
        "Temperature Sensor",
        "Humidity Sensor",
        "Magnetic Sensor",
        "Step Sensor",
        "Use Reliable Alarms",
        "Run Log",
        "Debug To System Log",
        "Debug To Internal Storage",
        "Lock Code",
        "App Check Method",
        "Use Motion Detection",
    ],
    "135": ["Action Number", "Action Label", "Top of Loop", "End of Loop", "End of If"],
    "147": ["UI", "Monitor", "Action", "Misc"],
    "150s": [
        "Any",
        "Application Specific",
        "Audio",
        "CDC",
        "Communications",
        "Content Security",
        "Content Smart Card",
        "HID / Keyboartd",
        "HID / Mouse",
        "HID / Other",
        "Mass Storage",
        "Wireless Miscellaneous",
        "Per Interface",
        "Physical",
        "Printer",
        "Digital Camera",
        "Vendor Specific",
        "Video",
        "Wireless Controller",
    ],
    "153": ["Task", "Configuration"],
    "153a": ["Source"],
    "156": ["Tasker"],
    "156a": ["English", "German"],
    "160": ["Yes", "No", "Any"],
    "162": ["1st", "2nd", "3rd"],
    "162a": ["Active", "Inactive", "Disabled"],
    "165": [
        "Snooze Current",
        "Disable Current",
        "Disable By Label",
        "Disable By Time",
        "Disable Any",
    ],
    "171": ["Call", "System", "Ringer", "Media", "Alarm", "Notification"],
    "173": ["Allow All", "Allow", "Deny All", "Deny"],
    "175": ["Normal", "Battery Saver", "Toggle"],
    "185": [
        "Black and White",
        "Enhance Blue",
        "Enhance Green",
        "Greyscale",
        "Set Alpha",
    ],
    "190": ["Horizontal", "Vertical"],
    "191": ["Left", "Right"],
    "191a": ["45", "90", "135", "180"],
    "192": ["Alarm", "Notification", "Ringer"],
    "194": ["Status", "Horizontal Position", "Vertical Position", "Width", "Height"],
    "195": [
        "Element Position",
        "Element Size",
        "Value",
        "Element Visibility",
        "Element Depth",
        "Maximum Value",
    ],
    "235": ["Global", "Secure", "System"],
    "310": ["Off", "Vibrate"],
    "312": [
        "No Interruptions",
        "Priority",
        "Allow All",
        "Alarms",
        "Custom Setting",
        "Query",
    ],
    "313": ["Mode", "Vibrate", "Sound"],
    "314": ["Credentials", "Biometric"],
    "316": ["Normal", "Small", "Smaller", "Smallest", "Large", "Larger", "Largest"],
    "318": ["Off", "Portrait", "Portrait Reverse", "Landscape", "Landscape Reverse"],
    "324": ["Remote Folder", "Query"],
    "324a": ["Both", "Files", "Folders"],
    "325": ["Trash", "Remove From Trash"],
    "325a": ["File ID", "Remote Path"],
    "339": ["GET", "POST", "HEAD", "PUT", "PATCH", "Delete", "OPTIONS", "TRACE"],
    "340": ["Connect", "Disconnect", "Pair", "Unpair (Forget)"],
    "341": [
        "Connection Type",
        "Mobile Data Enabled",
        "Wifi Hidden",
        "Wifi MAC",
        "Wifi RSSI",
        "Wifi SSID",
        "BT Paired Addresses",
        "BT Device Connected",
        "BT Device Name",
        "BT Device Class Name",
        "Auto Sync",
        "Wifi IP Address",
    ],
    "342": [
        "Parent Dir",
        "Mopdified",
        "Name",
        "Size",
        "Type",
        "Exists",
        "MD5",
        "Base 64",
    ],
    "343": [
        "Music File Artist Tag",
        "Music File Duration Tag",
        "Music File Title Tag",
        "Music Playing Position",
        "Music Playing Position Millis",
    ],
    "344": [
        "Calendar Calendar",
        "Calendar Title",
        "Calendar Description",
        "Calendar Location",
        "Calendar Start",
        "Calendar End",
        "Calendar All Day",
        "Calendar Available",
        "App Name",
        "Package Version",
        "Package Version Label",
        "Time Package",
    ],
    "345": ["Length"],
    "346": [
        "Contact Address, Home",
        "Contact Address, Work",
        "Contact Birthday",
        "Contact Email",
        "Contact Name",
        "Contact Nickname",
        "Contact Organization",
        "Contact Photo URl",
        "Contact Thumb URl",
    ],
    "347": [
        "Action",
        "Event",
        "State",
        "Global",
        "Local",
        "Profiles",
        "Scenes",
        "Tasks",
        "Timer Widget Remaining",
        "Current Task Name",
        "Used Memory",
    ],
    "348": [
        "AutoRotate",
        "Orientation",
        "DPI",
        "Available Resolution",
        "Hardware Resolution",
        "Is Locked",
        "Is Securely Locked",
        "Display Density",
        "Navigation Bar Height",
        "Navigation Bar Top Offset",
        "Navigation Bar Top Offset",
        "Status Bar Offset",
    ],
    "349": ["Android ID", "User ID"],
    "351": ["OAuth 2.0", "Username and Password"],
    "352": ["Mobile", "Wifi", "Bluetooth", "Ethernet", "VPN", "MMS"],
    "358": ["Single Device", "Paired Devices", "Scan Devices"],
    "363": [
        "Auto",
        "2G",
        "3G",
        "4G",
        "2G and 3G",
        "3G and 4G",
        "5G",
        "3G and 4G and 5G",
        "4G and 5G",
    ],
    "368": ["Normal", "Satellite", "Terrain", "Hybrid", "None"],
    "369": [
        "Remove Duplicates",
        "Reverse",
        "Rotate Left",
        "Rotate Right",
        "Shuffle",
        "Sort Alpha",
        "Sort Alpha, Reverse",
        "Sort Alpha Caseless",
        "Sort Alpha Caseless, Reverse",
        "Sort Shortest First",
        "Sort Longest First",
        "Sort Numeric, Integer",
        "Sort Numeric",
        "Floating-Point",
        "Squash",
    ],
    "374": ["Start", "Stop", "Query"],
    "378": ["Select Single Item", "Multiple Choices"],
    "379": [
        "Custom",
        "Freeze App",
        "Suspend App",
        "Kill App",
        "Clear App Data",
        "Reboot",
        "User Restrictions",
        "Backup Service",
        "Uninstall App",
        "Permission",
        "Clear Device Owner",
        "Check Device Owner",
    ],
    "380": ["Text", "File", "Redirect"],
    "383": ["Connectivity", "NFC", "Volume", "WiFi", "Media Output"],
    "384": ["Add/Edit", "Delete"],
    "384a": ["Button", "Toggle", "Range", "Toggle Range", "No Action"],
    "386": ["Disallow", "Allow"],
    "391": ["Show/Update", "Dismiss"],
    "391a": ["Animation", "Progress Bar"],
    "393": ["Simple", "Format"],
    "394": [
        "Custom",
        "Now (Current Date and Time)",
        "Milliseconds Since Epoch",
        "Seconds Since Epoch",
        "ISO 8601",
        "Milliseconds Since Epoch UTC",
        "Seconds Since Epoch UTC",
    ],
    "394a": ["None", "Seconds", "Minutes", "Hours", "Days"],
    "396": ["Simple", "Regex"],
    "412": [
        "Alphabetic",
        "Alphabetic, Reverse",
        "Directory Then File",
        "File Extension",
        "File Extension, Reverse",
        "File Then Directory",
        "Modification Date",
        "Modification Date, Reverse",
        "Size",
        "Size Reverse",
    ],
    "426": ["Disconnect", "Reassociate", "Reconnect"],
    "427": ["Default", "Never While Plugged", "Never"],
    "431": [
        "Start",
        "Stop",
        "Stop All",
        "Add To Keep Running",
        "Remove From Keep Running",
        "Query",
        "Toggle",
    ],
    "443": [
        "Next",
        "Pause",
        "Previous",
        "Toggle Pause",
        "Stop",
        "Play [Simulated Only]",
        "Rewind",
        "Fast Forward",
    ],
    "455": ["Default", "Microphone", "Call Outgoing", "Call Incoming", "Call"],
    "455a": ["MP4", "3GPP", "AMR Narrowband", "AMR Wideband"],
    "446": ["Directories", "Files"],
    "490": ["Grab", "Release"],
    "512": ["Expanded", "Collapsed"],
    "523": [
        "Red",
        "Green",
        "Blue",
        "Yellow",
        "Turquoise",
        "Purple",
        "Orange",
        "Pink",
        "White",
    ],
    "544": ["End", "Pause", "Resume", "Reset", "Update"],
    "552": ["Icon", "Text", "Icon and Text"],
    "566": ["Default", "Off", "On"],
    "595": [
        "Normal Text",
        "Caps / Word",
        "Caps / All",
        "Numeric / Decimal",
        "Numeric / Integer",
        "Password",
        "Phone Number",
        "Passcode",
    ],
    "596": [
        "Bytes to Kilobytes",
        "Bytes to Megabytes",
        "Bytes to Gigabytes",
        "Date Time to Seconds",
        "Seconds to Date Time",
        "Seconds to Medium Date Time",
        "Seconds to Long Date Time",
        "HTML to Text",
        "Celsius to Fahrenheit",
        "Fahrenheit to Celsius",
        "Centimeters to Inches",
        "Inches to Centimeters",
        "Meters to Feet",
        "Feet to Meters",
        "Kilograms to Pounds",
        "Pounds to Kilograms",
        "Kilometers to Miles",
        "Miles to Kilometers",
        "URL Decode",
        "URL Encode",
        "Binary to Decimal",
        "Decimal to Binary",
        "Hex to Decimal",
        "Decimal to Hex",
        "Base65 Encode",
        "Base65 Decode",
        "To MD5 Digest",
        "To SHA1 Digest",
        "To Lower Case",
        "To Upper Case",
        "To Uppercase First",
    ],
    "612": [
        "Goto",
        "Load",
        "Pause",
        "Play",
        "Resume",
        "Set Zoom",
        "Back",
        "Forward",
        "Stop",
        "Toggle",
    ],
    "665": ["Delete"],
    "815": ["Package", "App", "Activity", "Receiver", "Services", "Provider"],
    "820": [
        "Never",
        "With AC Power",
        "With USB Power",
        "With AC or USB Power",
        "With Wireless Power",
        "With Wireless or AC Power",
        "With Wireless or USB Power",
        "With Wireless",
        "AC or USB Power",
    ],
    "877": [
        "None",
        "Default",
        "Alt",
        "Browsable",
        "Car Dock",
        "Desk Dock",
        "Home",
        "Info",
        "Launcher",
        "Preference",
        "Selected Alt",
        "Tab",
        "Text",
        "Cardboard",
    ],
    "877a": ["Broadcast Receiver", "Activity", "Service"],
    "901": ["GPS", "Net", "Any"],
    "903": ["Free Form", "Web Search"],
    "905": ["Off", "Device Only", "Battery Saving", "High Accuracy"],
    "906": [
        "Off",
        "Hide Status Bar",
        "Hide Navigation Bar",
        "Hide Both",
        "Toggle Last",
    ],
    "909": ["Starred", "Frequent", "Starred, Frequent"],
    "910": [
        "View",
        "Clear Missed Calls",
        "Clear Incoming Calls",
        "Clear Outgoing Calls",
        "Clear All",
        "Mark All Acknowledged",
        "Mark All Read",
    ],
    "2079e": ["Volume Up", "Volume Down", "Volume Up Or Down"],
    "2081e": ["Playing or Not Playing", "Playing", "Not Playing"],
    "3001e": ["Left-Right", "Up-Down", "Backwards-Forwards"],
    "3001ea": ["Very Low", "Low", "Medium", "High", "Very High"],
    "3001eb": ["Very Short", "Short", "Medium", "Long", "Very Long"],
    "switch_set": ["Off", "On", "Toggle"],
    # Scene elements
    "TextElement1": [
        "Center",
        "Top",
        "Bottom",
        "Left",
        "Right",
        "Top Left",
        "Top Right",
        "Bottom Left",
        "Bottom Right",
    ],
    "TextElement2": [
        "None",
        "Reduce Text Size",
        "Allow Scrolling",
    ],
    "TextElement3": [
        "Plain Text",
        "Text With Links",
        "HTML",
    ],
    "EditTextElement": [
        "Caps / Word",
        "Caps / All",
        "Numeric / Decimal",
        "Numeic / Integer",
        "Password",
        "Phone Number",
        "Passcode",
    ],
    "RectElement1": [
        "None",
        "Horizontal",
        "Vertical",
        "Diagonal, Top Left",
        "Diagonal, Bottom Left",
        "Radial",
    ],
    "RectElement2": [
        "All",
        "Top",
        "Bottom",
        "Left",
        "Right",
    ],
    "WebElement": ["URL", "File", "Direct"],
    "ListElement1": ["Manual", "Variable Array", "Variable"],
    "ListElement2": ["None", "Single", "Multiple"],
    "NumberPickerElement": ["Normal", "Prefixed Zeroes"],
    "PropertyElement1": ["Overlay", "Dialog", "Activity"],
    "PropertyElement2": [
        "System",
        "Landscape",
        "Portrait",
        "User",
        "Behind",
        "Sensor",
        "No Sensor",
        "Sensor Landscape",
        "Sensor Portrait",
        "Reverse Landscape",
        "Reverse Portrait",
        "Full Sensor",
    ],
    "PropertyElement3": ["System", "Dark", "Light"],
    "SliderElement1": ["Horizontal", "Rotated Left", "rotated Right"],
    "SliderElement2": ["Never", "While Changing", "Always"],
}
