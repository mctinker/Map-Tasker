#! /usr/bin/env python3

#                                                                                      #
# servicec: Tasker Preferences <Service> Codes                                         #
#                                                                                      #
#  Provide the master lookup for a given <Service> xml statement                       #
#                                                                                      #


service_codes = {
    # service code: name to display, preference section, display order
    "anm": {
        "display": "Animations",
        "section": 0,
        "num": 1,
    },
    "sHapt": {
        "display": "Haptic Feedback",
        "section": 0,
        "num": 2,
    },
    "tpEn": {
        "display": "Tips",
        "section": 0,
        "num": 3,
    },
    "themeMaterial": {
        "display": "Theme",
        "section": 0,
        "num": 4,
        "values": {
            0: "Device Default Dark",
            1: "Device Default Light",
            2: "Dark",
            3: "Light",
            4: "Light With Dark ActionBar",
            5: "Black",
            6: "Cloud",
            7: "Tangerine",
            8: "Device Default Auto",
            9: "Auto",
        },
    },
    "hideStatusBar": {
        "display": "Hide Status Bar",
        "section": 0,
        "num": 5,
        "values": {
            0: "Never",
            1: "When Editing Scenes",
            2: "When Started in Landscape Mode",
            3: "Always",
        },
    },
    "oss": {  # Missing
        "display": "Orientation",
        "section": 0,
        "num": 6,
        "values": {
            0: "User",
            1: "Portrait",
            2: "Landscape",
        },
    },
    "dragModeNew": {  # Missing
        "display": "List Item Dragging",
        "section": 0,
        "num": 7,
        "values": {
            0: "On Right, Visible",
            1: "On Right, Invisible",
            2: "On Left, Visible",
            3: "On Left, Invisible",
            4: "Only When Selecting",
            5: "When Selecting, With Menu Options",
            6: "Disabled",
        },
    },
    "lockIconColour": {
        "display": "Icon Color From Theme",
        "section": 0,
        "num": 8,
    },
    "hardwareAccel": {
        "display": "Hardware Acceleration",
        "section": 0,
        "num": 9,
    },
    "PREF_USE_2024_TASKER": {
        "display": "Use Tasker 2024 UI (Very Early)",
        "section": 1,
        "num": 9.5,
    },
    "mSi": {
        "display": "Always Show Enable Icon",
        "section": 1,
        "num": 10,
    },
    "apn": {
        "display": "Ask For New Profile Name",
        "section": 1,
        "num": 11,
    },
    "???": {
        "display": "Confirm Profile Deletes",
        "section": 1,
        "num": 12,
    },
    "????": {
        "display": "Confirm Other Deletes",
        "section": 1,
        "num": 13,
    },
    "?????": {
        "display": "Share Files After Exporting",
        "section": 1,
        "num": 14,
    },
    "pTs": {
        "display": "Name Text Size",
        "section": 1,
        "num": 15,
    },
    "cmdTs": {
        "display": "Value / Command Text Size",
        "section": 1,
        "num": 16,
    },
    "cmdTmnuw": {
        "display": "VCommand Text Monospaced/Unwrapped",
        "section": 1,
        "num": 16.5,
    },
    "apl": {
        "display": "Profile Auto-Collapse Mania",
        "section": 1,
        "num": 17,
    },
    "PREF_ASK_FOR_PERMISSIONS_ON_APP_EXIT": {
        "display": "Confirm App Exit",
        "section": 1,
        "num": 18,
    },
    "lcD": {
        "display": "Lock Code",
        "section": 2,
        "num": 19,
    },
    "lae": {
        "display": "Lock On Startup",
        "section": 2,
        "num": 20,
    },
    "lang": {
        "display": "Language",
        "section": 3,
        "num": 21,
    },
    "avo": {
        "display": "Always View Help Online",
        "section": 3,
        "num": 22,
    },
    "snopin": {
        "display": "Show Notification Icon",
        "section": 4,
        "num": 23,
    },
    "shinAPr": {
        "display": "Show Notification Icon (No Active Profiles)",
        "section": 4,
        "num": 24,
    },
    "shTDnoAPr": {
        "display": "Show Tasker Disabled Notification",
        "section": 4,
        "num": 25,
    },
    "?": {
        "display": "Show Number Of Profiles",
        "section": 4,
        "num": 26,
    },
    "cust_notification": {
        "display": "Notification Icon",
        "section": 4,
        "num": 27,
    },
    "notactions": {
        "display": "Notification Action Buttons",
        "section": 4,
        "num": 28,
    },
    "clock_alarm": {  # Missing
        "display": "Use Reliable Alarms",
        "section": 4,
        "num": 29,
        "values": {
            0: "Never",
            1: "When Off",
            2: "Always",
        },
    },
    "nfcda": {
        "display": "NFC Detection Enabled",
        "section": 4,
        "num": 30,
    },
    "PREF_START_MONITOR_ON_APP_OPEN": {
        "display": "Start Monitor On App Open",
        "section": 4,
        "num": 30.5,
    },
    "PREF_KEEP_ACCESSIBILITY_SERVICES_RUNNING": {
        "display": "KEEP ACCESSIBILITY RUNNING",
        "section": 4,
        "num": 31,
    },
    "appcheckMethod": {
        "display": "App Check Method",
        "section": 5,
        "num": 32,
        "values": {
            0: "Accessibility",
            1: "App Usage Stats",
        },
    },
    "lperiod": {
        "display": "Application Check MilliSeconds",
        "section": 5,
        "num": 33,
    },
    "btpiod": {
        "display": "BT Scan Seconds",
        "section": 5,
        "num": 34,
    },
    "wfpiod": {
        "display": "Wifi Scan Seconds",
        "section": 5,
        "num": 35,
    },
    "guped": {
        "display": "GPS Check Seconds",
        "section": 5,
        "num": 36,
    },
    "luped": {
        "display": "Network Location Check Seconds",
        "section": 5,
        "num": 37,
    },
    "gupt": {
        "display": "GPS Timeout Seconds",
        "section": 5,
        "num": 38,
    },
    "lfdd": {
        "display": "All Checks Seconds",
        "section": 6,
        "num": 39,
    },
    "sows": {
        "display": "Timeout Seconds",
        "section": 6,
        "num": 40,
    },
    "workForLoc": {
        "display": "Use Motion Detection",
        "section": 6,
        "num": 41,
    },
    "accelWhenOff": {
        "display": "Accelerometer",
        "section": 6,
        "num": 42,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "humidityWhenOff": {
        "display": "Humidity Sensor",
        "section": 6,
        "num": 43,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "lightWhenOff": {
        "display": "Light Sensor",
        "section": 6,
        "num": 44,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "magnetWhenOff": {
        "display": "Magnetic Sensor",
        "section": 6,
        "num": 44.2,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "pressureWhenOff": {
        "display": "Pressure Sensor",
        "section": 6,
        "num": 44.5,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "proxWhenOff": {
        "display": "Proximity Sensor",
        "section": 6,
        "num": 45,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "stepsWhenOff": {
        "display": "Step Sensor",
        "section": 6,
        "num": 46,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "tempWhenOff": {
        "display": "Temperature Sensor",
        "section": 6,
        "num": 47,
        "values": {
            0: "No",
            1: "When Power Connected",
            2: "Yes",
            3: "Yes, And Keep Android Awake",
        },
    },
    "cape": {
        "display": "Cell Workaround",
        "section": 6,
        "num": 48,
    },
    "wakeForLoc": {
        "display": "Net/Cell Wake Screen",
        "section": 6,
        "num": 49,
    },
    "bttp": {
        "display": "BT Minimum Timeout Seconds",
        "section": 7,
        "num": 50,
    },
    "wip": {
        "display": "Wifi Minimum Timeout Seconds",
        "section": 7,
        "num": 51,
    },
    "newCellApi": {
        "display": "Use New Cell API",
        "section": 7,
        "num": 52,
    },
    "adbLogcat": {
        "display": "ADB Wifi Logcat",
        "section": 7,
        "num": 53,
    },
    "acMSr": {
        "display": "Gesture Initial Sample Rate",
        "section": 8,
        "num": 54,
    },
    "accMR": {
        "display": "Gesture Match Radius",
        "section": 8,
        "num": 55,
    },
    "acrmd": {
        "display": "Gesture Match Reset Time",
        "section": 8,
        "num": 56,
    },
    "uiori": {
        "display": "Orientation State Accuracy",
        "section": 8,
        "num": 57,
        "values": {
            0: "Very Low",
            1: "Low",
            2: "Medium",
            3: "High",
            4: "Very High",
        },
    },
    "qst0": {
        "display": "Quick Settings Tasks #1",
        "section": 9,
        "num": 58,
    },
    "qst1": {
        "display": "Quick Settings Tasks #2",
        "section": 9,
        "num": 59,
    },
    "qst2": {
        "display": "Quick Settings Tasks #3",
        "section": 9,
        "num": 60,
    },
    "tEnable": {
        "display": "App Shortcut Tasks",
        "section": 9,
        "num": 61,
    },
    "ast0": {
        "display": "App Shortcut Tasks #1",
        "section": 9,
        "num": 62,
    },
    "ast1": {
        "display": "App Shortcut Tasks #2",
        "section": 9,
        "num": 63,
    },
    "ast2": {
        "display": "App Shortcut Tasks #3",
        "section": 9,
        "num": 64,
    },
    "ast3": {
        "display": "App Shortcut Tasks #4",
        "section": 9,
        "num": 65,
    },
    "saena": {
        "display": "Secondary App Enabled",
        "section": 9,
        "num": 66,
    },
    "csnipD": {
        "display": "Camera Delay",
        "section": 9,
        "num": 67,
    },
    "mFn": {
        "display": "Flash Problems",
        "section": 9,
        "num": 68,
    },
    "PREF_ALLOW_INSECURE_TASK_RUN_REQUESTS": {
        "display": "Allow Running Tasks From Insecure Sources",
        "section": 9,
        "num": 69,
    },
    "mqt": {
        "display": "Maximum Tasks Queued",
        "section": 10,
        "num": 70,
    },
    "lph": {
        "display": "Local Auto-Backup Max Age",
        "section": 11,
        "num": 71,
        "values": {
            0: "No Auto-Backups",
            1: "12 Hours",
            2: "1 Day",
            3: "2 Days",
            4: "1 Week",
            5: "2 Weeks",
            6: "1 Month",
            7: "2 Months",
            8: "6 Months",
        },
    },
    "googleDriveBackups": {
        "display": "Google Drive Backup",
        "section": 11,
        "num": 72,
    },
    "googleDriveBackupsAccount": {
        "display": "Google Drive Backup Account",
        "section": 11,
        "num": 73,
    },
    "bkcuva": {
        "display": "Backup User Vars/Prefs",
        "section": 11,
        "num": 74,
    },
    "kcph": {
        "display": "Google API Key",
        "section": 11,
        "num": 75,
    },
    "adbwp": {
        "display": "Default ADB Wifi Port",
        "section": 11,
        "num": 76,
    },
    "stroutdf": {
        "display": "Structure Output By Default",
        "section": 11,
        "num": 77,
    },
    "aExt": {
        "display": "Allow External Access",
        "section": 11,
        "num": 78,
    },
    "saveMemory": {
        "display": "Reduce Resource Usage",
        "section": 11,
        "num": 79,
    },
    "PREF_ADVANCED_EXPORT_DESCRIPTION": {
        "display": "Advanced Export Options",
        "section": 11,
        "num": 80,
    },
    "PREF_EXPORT_LIGHT": {
        "display": "Compact Exports",
        "section": 11,
        "num": 81,
    },
    "sExps": {
        "display": "Check Permissions On Save",
        "section": 11,
        "num": 82,
    },
    "dsd": {
        "display": "Debug To System Log",
        "section": 12,
        "num": 83,
    },
    "fExtCache": {
        "display": "Debug To Internal Storage",
        "section": 12,
        "num": 84,
    },
    "lEnable": {
        "display": "Popup Errors/Warnings",
        "section": 12,
        "num": 85,
    },
    "PREF_IS_USING_TEST_SERVER": {
        "display": "Use Test Server For Shares",
        "section": 12,
        "num": 86,
    },
    "IS_USING_TASKY": {
        "display": "Using Tasky",
        "section": 13,
        "num": 87,
    },
    "beginnerMode": {
        "display": "Beginner Mode",
        "section": 13,
        "num": 88,
    },
    "runlogProfs": {
        "display": "Log Profiles",
        "section": 13,
        "num": 89,
    },
    "runlogTasks": {
        "display": "Log Tasks",
        "section": 13,
        "num": 90,
    },
    "runlogActions": {
        "display": "Log Actions",
        "section": 13,
        "num": 91,
    },
    "searchFilterText": {
        "display": "Filter Text on Search",
        "section": 13,
        "num": 92,
    },
    "searchFeatures": {
        "display": "Search Features",
        "section": 13,
        "num": 93,
    },
    "sigmotion": {
        "display": "Signal on Motion",
        "section": 13,
        "num": 94,
    },
    "leEnle": {
        "display": "Unknown",
        "section": 13,
        "num": 95,
    },
    "kit": {
        "display": "Unknown",
        "section": 13,
        "num": 96,
    },
    "qstdc0": {
        "display": "Unknown",
        "section": 13,
        "num": 97,
    },
    "qstcommlong0": {
        "display": "Unknown",
        "section": 13,
        "num": 98,
    },
    "qstexcont0": {
        "display": "Unknown",
        "section": 13,
        "num": 99,
    },
    "searchMatchType": {
        "display": "Unknown",
        "section": 13,
        "num": 100,
    },
    "lPdta": {
        "display": "Unknown",
        "section": 13,
        "num": 101,
    },
    "sbl": {
        "display": "Unknown",
        "section": 13,
        "num": 102,
    },
    "qstcanuselockdevice0": {
        "display": "Unknown",
        "section": 13,
        "num": 103,
    },
    "qstcanuselockdevice1": {
        "display": "Unknown",
        "section": 13,
        "num": 104,
    },
    "qstcomm0": {
        "display": "Unknown",
        "section": 13,
        "num": 105,
    },
    "qsts0": {
        "display": "Unknown",
        "section": 13,
        "num": 106,
    },
    "tsRef": {
        "display": "Unknown",
        "section": 13,
        "num": 107,
    },
    "qstst0": {
        "display": "Unknown",
        "section": 13,
        "num": 108,
    },
    "listMarginWidthPercent": {
        "display": "Margin Width Percentage",
        "section": 13,
        "num": 109,
    },
    "tsIndexed": {
        "display": "Unknown",
        "section": 13,
        "num": 110,
    },
}
