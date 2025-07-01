"""Task "Action" and Profile "condition" dictionary"""

#                                                                                      #
# actionc: Task "Action" and Profile "condition" dictionary                            #
#                                                                                      #
#  Provide the master lookup for a given <code>nnn</code> xml statement                #
#  level 1 key = the code (nnn, above) or screen element type                          #
#       If a code, the last character is 't' for 't', 'e' for event, 's' for state     #
#   numargs subkey = the maximum number of argn xml lines in the action                #
#      if it = 99, then this is a referral to another entry, which is identified       #
#      in 'args'                                                                       #
#   args subkey = the specific arg number  keys with a 's' or 'e' are Profile          #
#    conditions                                                                        #
#        ...'e'=event, 's'=state, 't'=task                                             #
#   display subkey = the name to output - required                                     #
#   reqargs subkey = the requirement arg statement numbers for evaluation - optional   #
#   evalargs subkey = formula for evaluation - optional                                #
#      'some_string:' for str or int xml values                                        #
#      ["e", ", name"] ...evaluate value to determine if it is 'selected'.             #
#                                                                                      #
#      ['some_string:', 'l', 'lookup-code] for actiont dictionary lookup for specific  #
#       code.                                                                          #
#                                                                                      #
from collections import namedtuple

# Define the namedtuples
ActionCode = namedtuple(
    "ActionCode",
    ["redirect", "args", "name", "category", "canfail"],
)
ArgumentCode = namedtuple(
    "ArgumentCode",
    ["arg_id", "arg_required", "arg_name", "arg_type", "arg_eval"],
)

# Refactored action_codes dictionary with explicit keyword arguments
action_codes = {
    "1000e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Priority=", "l", "4s"]),
        ],
        name="Display Unlocked",
        category="",
        canfail="",
    ),
    "1000s": ActionCode(
        redirect="",
        args=[],
        name="Plugin",
        category="",
        canfail="",
    ),
    "1000t": ActionCode(
        redirect="",
        args=[],
        name="Plugin",
        category="",
        canfail="",
    ),
    "100s": ActionCode(
        redirect="",
        args=[],
        name="Airplane Mode",
        category="",
        canfail="",
    ),
    "100t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="For", arg_type="1", arg_eval="Number="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Web Search", arg_type="3", arg_eval=["e", "Info"]),
        ],
        name="Search",
        category="104",
        canfail="False",
    ),
    "101t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Camera", arg_type="0", arg_eval="Camera"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Filename", arg_type="1", arg_eval="Filename"),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Naming Sequence", arg_type="0", arg_eval="Naming Sequence"
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Insert In Gallery", arg_type="3", arg_eval="Insert In Gallery"
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Discreet", arg_type="3", arg_eval="Discreet"),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Resolution", arg_type="1", arg_eval="Resolution"),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Scene Mode", arg_type="0", arg_eval="Scene Mode"),
            ArgumentCode(
                arg_id="7", arg_required=True, arg_name="White Balance", arg_type="0", arg_eval="White Balance"
            ),
            ArgumentCode(arg_id="8", arg_required=True, arg_name="Flash Mode", arg_type="0", arg_eval="Flash Mode"),
            ArgumentCode(arg_id="9", arg_required=True, arg_name="Focus Mode", arg_type="0", arg_eval="Focus Mode"),
        ],
        name="Take Photo",
        category="65",
        canfail="True",
    ),
    "102t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File"),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Mime Type", arg_type="1", arg_eval="Mime Type"),
        ],
        name="Open File",
        category="50",
        canfail="True",
    ),
    "103s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval="Level="),
        ],
        name="Light Level",
        category="",
        canfail="",
    ),
    "1040876951t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval="Timeout="),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ",Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoInput UI Query",
        category="",
        canfail="",
    ),
    "1040969826t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Muzei Wallpaper: Next Artwork",
        category="",
        canfail="",
    ),
    "104s": ActionCode(
        redirect="",
        args=[],
        name="Pressure",
        category="",
        canfail="",
    ),
    "104t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="URL", arg_type="1", arg_eval="URL="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Package/App Name", arg_type="2", arg_eval="Package/App Name="
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="'Open With' Dialog",
                arg_type="3",
                arg_eval=["e", ", 'Open With' Dialog"],
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="'Open With' Title",
                arg_type="1",
                arg_eval=", 'Open With' Title=",
            ),
        ],
        name="Browse URL",
        category="80",
        canfail="True",
    ),
    "105s": ActionCode(
        redirect="",
        args=[],
        name="Media Button",
        category="",
        canfail="",
    ),
    "105t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Text", arg_type="1", arg_eval="Text="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Add", arg_type="3", arg_eval=["e", ", Add"]),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Image", arg_type="1", arg_eval="Image="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Is Sensitive Data", arg_type="3", arg_eval="Is Sensitive Data"
            ),
        ],
        name="Set Clipboard",
        category="104",
        canfail="True",
    ),
    "106s": ActionCode(
        redirect="",
        args=[],
        name="Magnetic Field",
        category="",
        canfail="",
    ),
    "107361459t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Actions V2",
        category="",
        canfail="",
    ),
    "107s": ActionCode(
        redirect="",
        args=[],
        name="Missed Call",
        category="",
        canfail="",
    ),
    "1094115366t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast Device Settings",
        category="",
        canfail="",
    ),
    "1099157652t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Json Write",
        category="",
        canfail="",
    ),
    "109t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "109"]),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Image", arg_type="1", arg_eval="Image"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Scale", arg_type="3", arg_eval=["e", ", Scale"]),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Crop", arg_type="3", arg_eval=["e", ", Crop"]),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Center", arg_type="3", arg_eval=["e", ", Center"]),
        ],
        name="Set Wallpaper",
        category="40",
        canfail="True",
    ),
    "10s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Set=", "l", "10s"]),
        ],
        name="Power",
        category="",
        canfail="",
    ),
    "110s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", "2G"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", "3G"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", "3G-HSPA"]),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", "4G"]),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", "5G"]),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Active=", "l", "160"]),
        ],
        name="Mobile Network",
        category="",
        canfail="",
    ),
    "111t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=False, arg_name="Recipient(s)", arg_type="1", arg_eval="Recipient(s)"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Subject", arg_type="1", arg_eval="Subject"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Message", arg_type="1", arg_eval="Message"),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Attachment", arg_type="1", arg_eval="Attachment"),
        ],
        name="Compose MMS",
        category="90",
        canfail="False",
    ),
    "1120274117t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Locus Map",
        category="",
        canfail="",
    ),
    "112t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Terminal", arg_type="3", arg_eval="Terminal"),
            ArgumentCode(
                arg_id="2", arg_required=False, arg_name="Pass Variables", arg_type="1", arg_eval="Pass Variables"
            ),
        ],
        name="Run SL4A Script",
        category="35",
        canfail="True",
    ),
    "1130446693t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Launcher",
        category="",
        canfail="",
    ),
    "1132319851t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Add Sheet",
        category="",
        canfail="",
    ),
    "1133159835e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoShare Process Text",
        category="",
        canfail="",
    ),
    "1138194991s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", "Structure Output (JSON (etc)"],
            ),
        ],
        name="AutoWear State",
        category="",
        canfail="",
    ),
    "1138588429t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Join Send Query",
        category="",
        canfail="",
    ),
    "113t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Keep Wi-Fi when turning on",
                arg_type="3",
                arg_eval="Keep Wi-Fi when turning on",
            ),
        ],
        name="WiFi Tether (Hotspot)",
        category="80",
        canfail="True",
    ),
    "114t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="USB Tether",
        category="80",
        canfail="False",
    ),
    "1150542767e": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Tap Tap Plugin",
        category="",
        canfail="",
    ),
    "115t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=""),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=""),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=""),
        ],
        name="Test",
        category="140",
        canfail="True",
    ),
    "1164968315t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Play Media",
        category="",
        canfail="",
    ),
    "1165325195t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Web Screen",
        category="",
        canfail="",
    ),
    "116t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Server:Port", arg_type="1", arg_eval="Server:Port"),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Path", arg_type="1", arg_eval="Path"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Data / File", arg_type="1", arg_eval="Data / File"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Cookies", arg_type="1", arg_eval="Cookies"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="User Agent", arg_type="1", arg_eval="User Agent"),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Timeout", arg_type="0", arg_eval="Timeout"),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="Content Type", arg_type="1", arg_eval="Content Type"
            ),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Output File", arg_type="1", arg_eval="Output File"),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Trust Any Certificate",
                arg_type="3",
                arg_eval="Trust Any Certificate",
            ),
        ],
        name="HTTP Post",
        category="80",
        canfail="True",
    ),
    "117240295t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Input",
        category="",
        canfail="",
    ),
    "117t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Server:Port", arg_type="1", arg_eval="Server:Port"),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Path", arg_type="1", arg_eval="Path"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Attributes", arg_type="1", arg_eval="Attributes"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Cookies", arg_type="1", arg_eval="Cookies"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="User Agent", arg_type="1", arg_eval="User Agent"),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Timeout", arg_type="0", arg_eval="Timeout"),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Trust Any Certificate",
                arg_type="3",
                arg_eval="Trust Any Certificate",
            ),
        ],
        name="HTTP Head",
        category="80",
        canfail="True",
    ),
    "1186637727t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="KWGT Kustom Widget Maker",
        category="",
        canfail="",
    ),
    "118t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Server:Port", arg_type="1", arg_eval="Server:Port"),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Path", arg_type="1", arg_eval="Path"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Attributes", arg_type="1", arg_eval="Attributes"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Cookies", arg_type="1", arg_eval="Cookies"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="User Agent", arg_type="1", arg_eval="User Agent"),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Timeout", arg_type="0", arg_eval="Timeout"),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Mime Type", arg_type="1", arg_eval="Mime Type"),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Output File", arg_type="1", arg_eval="Output File"),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Trust Any Certificate",
                arg_type="3",
                arg_eval="Trust Any Certificate",
            ),
        ],
        name="HTTP Get",
        category="80",
        canfail="True",
    ),
    "119t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "119"]),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Address", arg_type="1", arg_eval=", Address="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Lat,Long", arg_type="1", arg_eval=", Lat, Long="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Zoom", arg_type="0", arg_eval=", Zoom="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Label", arg_type="1", arg_eval=", Label="),
        ],
        name="Open Map",
        category="60",
        canfail="True",
    ),
    "120s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Is=", "l", "120s"]),
        ],
        name="Orientation",
        category="",
        canfail="",
    ),
    "122375409t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWeb Web Services",
        category="",
        canfail="",
    ),
    "122s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Is=", "l", "122s"]),
        ],
        name="Display Orientation",
        category="",
        canfail="",
    ),
    "123s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval=["", "e", "switch_set"]),
        ],
        name="Display State",
        category="",
        canfail="",
    ),
    "123t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Command", arg_type="1", arg_eval="Command="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Timeout="
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="3", arg_required=False, arg_name="Store Output In", arg_type="1", arg_eval=", Store Output In="
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Store Errors In", arg_type="1", arg_eval=", Store Errors In="
            ),
            ArgumentCode(
                arg_id="5", arg_required=False, arg_name="Store Result In", arg_type="1", arg_eval=", Timeout="
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Use Tasker Settings",
                arg_type="3",
                arg_eval="Use Tasker Settings",
            ),
        ],
        name="Run Shell",
        category="35",
        canfail="True",
    ),
    "1246578872t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Notification",
        category="",
        canfail="",
    ),
    "124t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Path", arg_type="0", arg_eval="Path"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Writeable", arg_type="3", arg_eval="Writeable"),
        ],
        name="Remount",
        category="50",
        canfail="False",
    ),
    "1250249549t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Screen Off/On",
        category="",
        canfail="",
    ),
    "1256900802t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Termux",
        category="",
        canfail="",
    ),
    "125s": ActionCode(
        redirect="",
        args=[],
        name="Proximity Sensor",
        category="",
        canfail="",
    ),
    "125t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=False, arg_name="Recipient(s)", arg_type="1", arg_eval="Recipient(s)="
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Subject", arg_type="1", arg_eval=", Subject="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Message", arg_type="1", arg_eval=", Message="),
        ],
        name="Compose Email",
        category="80",
        canfail="False",
    ),
    "1269159260t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Calendar Task",
        category="",
        canfail="",
    ),
    "126t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Value", arg_type="1", arg_eval="Value="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Stop", arg_type="3", arg_eval=["e", ", Stop"]),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Local Variable Passthrough",
                arg_type="3",
                arg_eval=["e", ", Local Variable Passthrough"],
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Replace On Passthrough",
                arg_type="3",
                arg_eval=["e", ", Replace On Passthrough"],
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=False,
                arg_name="Limit Passthrough To",
                arg_type="1",
                arg_eval=", Limit Passthrough To=",
            ),
        ],
        name="Return",
        category="105",
        canfail="False",
    ),
    "129t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Code", arg_type="1", arg_eval="Code="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Libraries", arg_type="1", arg_eval=", Libraries="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Auto Exit", arg_type="3", arg_eval=["e", ", Auto Exit"]
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Timeout="
            ),
        ],
        name="JavaScriptlet",
        category="35",
        canfail="True",
    ),
    "12s": ActionCode(
        redirect="",
        args=[],
        name="HDMI Plugged",
        category="",
        canfail="",
    ),
    "1304982781t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Dialog",
        category="",
        canfail="",
    ),
    "130t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Priority", arg_type="0", arg_eval=", Priority="),
            ArgumentCode(
                arg_id="2", arg_required=False, arg_name="Parameter 1 (%par1)", arg_type="1", arg_eval=", Parameter 1="
            ),
            ArgumentCode(
                arg_id="3", arg_required=False, arg_name="Parameter 2 (%par2)", arg_type="1", arg_eval=", Parameter 2="
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=False,
                arg_name="Return Value Variable",
                arg_type="1",
                arg_eval=", Return Value Variable=",
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Stop", arg_type="3", arg_eval=["e", ", Stop"]),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Local Variable Passthrough",
                arg_type="3",
                arg_eval=["e", ", Local Variable Passthrough"],
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=False,
                arg_name="Limit Passthrough To",
                arg_type="1",
                arg_eval=", Limit Passthrough To=",
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Reset Return Variable",
                arg_type="3",
                arg_eval=["e", ", Reset Return Variable"],
            ),
            ArgumentCode(
                arg_id="9",
                arg_required=True,
                arg_name="Allow Overwrite Variables",
                arg_type="3",
                arg_eval=["e", ", Allow Overwrite Variables"],
            ),
            ArgumentCode(
                arg_id="10",
                arg_required=True,
                arg_name="Structure Output (JSON, etc)",
                arg_type="3",
                arg_eval=["e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="Perform Task",
        category="105",
        canfail="True",
    ),
    "131t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Path", arg_type="1", arg_eval="Path="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Libraries", arg_type="1", arg_eval=", Libraries="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Auto Exit", arg_type="3", arg_eval=["e", ", Auto Exit"]
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval="Timeout (Seconds)"
            ),
        ],
        name="JavaScript",
        category="35",
        canfail="True",
    ),
    "1339291165t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWeb Download",
        category="",
        canfail="",
    ),
    "1339942270t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="SharpTools Thing",
        category="",
        canfail="",
    ),
    "133t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="0", arg_eval=["Set=", "l", "133"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Value", arg_type="0", arg_eval="Value"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Value", arg_type="3", arg_eval=["e", ", Value"]),
        ],
        name="Set Tasker Pref",
        category="110",
        canfail="True",
    ),
    "1344888481e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="Notification Listener",
        category="",
        canfail="",
    ),
    "134e": ActionCode(
        redirect="",
        args=[],
        name="Card Mounted",
        category="",
        canfail="",
    ),
    "134t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Action", arg_type="1", arg_eval="Action="),
        ],
        name="Query Action",
        category="110",
        canfail="True",
    ),
    "135e": ActionCode(
        redirect="",
        args=[],
        name="Card Unmounted",
        category="",
        canfail="",
    ),
    "135s": ActionCode(
        redirect="",
        args=[],
        name="Auto-Sync",
        category="",
        canfail="",
    ),
    "135t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Set=", "l", "135"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Number", arg_type="0", arg_eval=", Number="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Label", arg_type="1", arg_eval=", Label="),
        ],
        name="Goto",
        category="105",
        canfail="True",
    ),
    "136e": ActionCode(
        redirect="",
        args=[],
        name="Card Removed",
        category="",
        canfail="",
    ),
    "136s": ActionCode(
        redirect="",
        args=[],
        name="VPN Connected",
        category="",
        canfail="",
    ),
    "136t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Sound Effects",
        category="20",
        canfail="False",
    ),
    "137t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="With Error", arg_type="3", arg_eval=["e", "Stop"]),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Task", arg_type="1", arg_eval=" Task="),
        ],
        name="Stop",
        category="105",
        canfail="False",
    ),
    "1384093265t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Calendar Task",
        category="",
        canfail="",
    ),
    "138t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Icon", arg_type="4", arg_eval="Icon="),
        ],
        name="Set Tasker Icon",
        category="110",
        canfail="False",
    ),
    "139t": ActionCode(
        redirect="",
        args=[],
        name="Disable",
        category="110",
        canfail="False",
    ),
    "140618776t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Toast",
        category="",
        canfail="",
    ),
    "140s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval="From="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=", To="),
        ],
        name="Battery Level",
        category="",
        canfail="",
    ),
    "140t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Old", arg_type="1", arg_eval="Old="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="New", arg_type="1", arg_eval=", New="),
        ],
        name="Change Icon Set",
        category="110",
        canfail="False",
    ),
    "1410790256t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Floating Icon",
        category="",
        canfail="",
    ),
    "1411074191t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Add Rows",
        category="",
        canfail="",
    ),
    "141s": ActionCode(
        redirect="",
        args=[],
        name="Battery Temperature",
        category="",
        canfail="",
    ),
    "142s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
        ],
        name="Profile Active",
        category="",
        canfail="",
    ),
    "142t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Task", arg_type="1", arg_eval="Task="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Action", arg_type="1", arg_eval=", Action="),
        ],
        name="Edit Task",
        category="110",
        canfail="False",
    ),
    "143s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
        ],
        name="Task Running",
        category="",
        canfail="",
    ),
    "143t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Element", arg_type="1", arg_eval=", Element="),
        ],
        name="Edit Scene",
        category="110",
        canfail="False",
    ),
    "1446679033t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Time",
        category="",
        canfail="",
    ),
    "1446697909t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Dialog",
        category="",
        canfail="",
    ),
    "1446874931t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Json Read",
        category="",
        canfail="",
    ),
    "1447159672t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Text",
        category="",
        canfail="",
    ),
    "1447244736t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Action Wait",
        category="",
        canfail="",
    ),
    "144741820t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Hide Notification Icons",
        category="",
        canfail="",
    ),
    "1452528931t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoContacts Query 2.0",
        category="",
        canfail="",
    ),
    "145s": ActionCode(
        redirect="",
        args=[],
        name="Signal Strength",
        category="",
        canfail="",
    ),
    "1461810131t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Update Cells",
        category="",
        canfail="",
    ),
    "147s": ActionCode(
        redirect="",
        args=[],
        name="Unread Text",
        category="",
        canfail="",
    ),
    "147t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Section", arg_type="0", arg_eval=["Section=", "l", "147"]
            ),
        ],
        name="Show Prefs",
        category="110",
        canfail="False",
    ),
    "1482108003t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Player State",
        category="",
        canfail="",
    ),
    "148s": ActionCode(
        redirect="",
        args=[],
        name="Pen Out",
        category="",
        canfail="",
    ),
    "148t": ActionCode(
        redirect="",
        args=[],
        name="Show Runlog",
        category="110",
        canfail="False",
    ),
    "149s": ActionCode(
        redirect="",
        args=[],
        name="Pen Menu",
        category="",
        canfail="",
    ),
    "14s": ActionCode(
        redirect="",
        args=[],
        name="Power Save Mode",
        category="",
        canfail="",
    ),
    "1508929357t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Array",
        category="",
        canfail="",
    ),
    "150s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Is=", "l", "150s"]),
        ],
        name="USB Connected",
        category="",
        canfail="",
    ),
    "150t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="Keyguard",
        category="40",
        canfail="False",
    ),
    "1520257414e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoNotification Intercept",
        category="",
        canfail="",
    ),
    "152t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Icon", arg_type="4", arg_eval=", Icon="),
        ],
        name="Set Widget Icon",
        category="110",
        canfail="False",
    ),
    "153t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "153"]),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Source", arg_type="0", arg_eval=["Source=", "l", "153a"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Variable", arg_type="1", arg_eval=", Variable="),
        ],
        name="Import Data",
        category="110",
        canfail="True",
    ),
    "154s": ActionCode(
        redirect="",
        args=[],
        name="Active User",
        category="",
        canfail="",
    ),
    "155t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Label", arg_type="1", arg_eval=", Label="),
        ],
        name="Set Widget Label",
        category="110",
        canfail="False",
    ),
    "1563355455t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Buttons Notification",
        category="",
        canfail="",
    ),
    "1563799945t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Secure Settings",
        category="",
        canfail="",
    ),
    "156t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Format", arg_type="0", arg_eval=["Format=", "l", "156"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Locality", arg_type="0", arg_eval=["Locality=", "l", "156a"]
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Beat Timing", arg_type="0", arg_eval=", Best Timing="
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Score", arg_type="1", arg_eval=", Score="),
        ],
        name="MIDI Play",
        category="65",
        canfail="False",
    ),
    "157t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Label", arg_type="1", arg_eval="Label"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Icon", arg_type="4", arg_eval="Icon"),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Collapse Panel On Click",
                arg_type="3",
                arg_eval="Collapse Panel On Click",
            ),
        ],
        name="Quick Setting Add",
        category="104",
        canfail="False",
    ),
    "158t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Label", arg_type="1", arg_eval="Label"),
        ],
        name="Quick Setting Remove",
        category="104",
        canfail="False",
    ),
    "159t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Set", arg_type="0", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Profile Status",
        category="110",
        canfail="True",
    ),
    "15t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Code", arg_type="1", arg_eval="Code"),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Allow Cancel", arg_type="3", arg_eval=["e", "Allow Cancel"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Remember Till Off",
                arg_type="3",
                arg_eval=["e", "Remember Till Off"],
            ),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Full Screen", arg_type="3", arg_eval=["e", "Full Screen"]
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Background Image",
                arg_type="1",
                arg_eval=", Background Image=",
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Layout", arg_type="1", arg_eval=", Layout="),
        ],
        name="Lock",
        category="40",
        canfail="False",
    ),
    "1600958131t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoBubbles Create Bubble",
        category="",
        canfail="",
    ),
    "160s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="SSID="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", MAC="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", IP"),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["Active=", "l", "160"]),
        ],
        name="Wifi Connected",
        category="",
        canfail="",
    ),
    "161s": ActionCode(
        redirect="",
        args=[],
        name="Ethernet Connect",
        category="",
        canfail="",
    ),
    "161t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Task", arg_type="1", arg_eval="Task="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
        ],
        name="Setup App Shortcuts",
        category="110",
        canfail="False",
    ),
    "1620773086t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="SharpTools A Thing",
        category="",
        canfail="",
    ),
    "162t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Number", arg_type="0", arg_eval=["Number=", "l", "162"]
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Status", arg_type="0", arg_eval=[", Status=", "l", "162a"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Can Use On Locked Device",
                arg_type="3",
                arg_eval=["e", ", Can Use On Locked Device"],
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Long Click Task", arg_type="1", arg_eval=", Long Click Task="
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Double Click Task",
                arg_type="1",
                arg_eval=", Double Click Task=",
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Subtitle", arg_type="1", arg_eval=", Subtitle="),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Icon", arg_type="1", arg_eval=", Icon="),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Label", arg_type="1", arg_eval=", Label="),
            ArgumentCode(arg_id="9", arg_required=False, arg_name="Command", arg_type="1", arg_eval=", Command="),
            ArgumentCode(
                arg_id="10",
                arg_required=False,
                arg_name="Long Click Command",
                arg_type="1",
                arg_eval=", Long Click Command=",
            ),
            ArgumentCode(
                arg_id="11",
                arg_required=False,
                arg_name="Double Click Command",
                arg_type="1",
                arg_eval=", Double Click Command=",
            ),
            ArgumentCode(
                arg_id="12", arg_required=False, arg_name="Command Prefix", arg_type="1", arg_eval=", Command Prefix="
            ),
        ],
        name="Set up Quick Setting Tile",
        category="110",
        canfail="False",
    ),
    "1643249237t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Tools & AmazFit",
        category="",
        canfail="",
    ),
    "1644316156t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Reply",
        category="",
        canfail="",
    ),
    "1645272907e": ActionCode(
        redirect="",
        args=[],
        name="CalendarTask",
        category="",
        canfail="",
    ),
    "1646792910t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Secure Settings",
        category="",
        canfail="",
    ),
    "165s": ActionCode(
        redirect="",
        args=[],
        name="Variable Value",
        category="",
        canfail="",
    ),
    "165t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "165"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Hours", arg_type="0", arg_eval=", Minutes="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Minutes", arg_type="0", arg_eval="Minutes"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Label", arg_type="1", arg_eval="Label"),
        ],
        name="Cancel Alarm",
        category="104",
        canfail="False",
    ),
    "166160670t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoVoice Natural Language",
        category="",
        canfail="",
    ),
    "1664218170e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="5",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoVoice Natural Language",
        category="",
        canfail="",
    ),
    "1668911626e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="Join",
        category="",
        canfail="",
    ),
    "166t": ActionCode(
        redirect="",
        args=[],
        name="Show Alarms",
        category="104",
        canfail="False",
    ),
    "1677547919t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Actions",
        category="",
        canfail="",
    ),
    "1687767515t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoInput Modes",
        category="",
        canfail="",
    ),
    "1691829355e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
        ],
        name="SharpTools Thing",
        category="",
        canfail="",
    ),
    "16s": ActionCode(
        redirect="",
        args=[],
        name="Device Idle",
        category="",
        canfail="",
    ),
    "16t": ActionCode(
        redirect="",
        args=[],
        name="System Lock",
        category="40",
        canfail="False",
    ),
    "170s": ActionCode(
        redirect="",
        args=[],
        name="Wifi Near",
        category="",
        canfail="",
    ),
    "171109731t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWeb Authentication",
        category="",
        canfail="",
    ),
    "171t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Frequency", arg_type="0", arg_eval="Frequency="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Duration", arg_type="0", arg_eval=", Duration="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Amplitude", arg_type="0", arg_eval=", Amplitude"),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Stream", arg_type="0", arg_eval=["Stream=", "l", "171"]
            ),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Do At Time", arg_type="1", arg_eval="Do At Time"),
        ],
        name="Beep",
        category="10",
        canfail="False",
    ),
    "172t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Text", arg_type="1", arg_eval="Text="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Frequency", arg_type="0", arg_eval=", Frequency="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Speed", arg_type="0", arg_eval=", Speed="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Amplitude", arg_type="0", arg_eval=", Amplitude="),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Stream", arg_type="0", arg_eval=[", Stream=", "l", "171"]
            ),
        ],
        name="Morse",
        category="10",
        canfail="False",
    ),
    "1732635924t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Action",
        category="",
        canfail="",
    ),
    "173t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "173"]),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Package/App Name", arg_type="2", arg_eval="Package/App Name"
            ),
        ],
        name="Network Access",
        category="80",
        canfail="False",
    ),
    "1754437993t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoVoice Recognition",
        category="",
        canfail="",
    ),
    "175s": ActionCode(
        redirect="",
        args=[],
        name="Dreaming",
        category="",
        canfail="",
    ),
    "175t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "175"]),
        ],
        name="Power Mode",
        category="104",
        canfail="False",
    ),
    "1764880755t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast Best Guess",
        category="",
        canfail="",
    ),
    "176t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Insert In Gallery",
                arg_type="3",
                arg_eval=["e", ", Insert In Gallery"],
            ),
        ],
        name="Take Screenshot",
        category="40",
        canfail="True",
    ),
    "177t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Haptic Feedback",
        category="20",
        canfail="False",
    ),
    "1788518030e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoInput Key",
        category="",
        canfail="",
    ),
    "1795842217t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoLaunch",
        category="",
        canfail="",
    ),
    "1804737413t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Secure Settings",
        category="",
        canfail="",
    ),
    "180s": ActionCode(
        redirect="",
        args=[],
        name="Temperature",
        category="",
        canfail="",
    ),
    "1810865467t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Get Data",
        category="",
        canfail="",
    ),
    "1810891651t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Get Cell",
        category="",
        canfail="",
    ),
    "1825107102e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoNotification",
        category="",
        canfail="",
    ),
    "1828597236t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast App",
        category="",
        canfail="",
    ),
    "182s": ActionCode(
        redirect="",
        args=[],
        name="Heart Rate",
        category="",
        canfail="",
    ),
    "1830656901t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear List Screens",
        category="",
        canfail="",
    ),
    "1830829821t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear 4 Screen",
        category="",
        canfail="",
    ),
    "1831781712t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast Settings",
        category="",
        canfail="",
    ),
    "185s": ActionCode(
        redirect="",
        args=[],
        name="Humidity",
        category="",
        canfail="",
    ),
    "185t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "185"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Value", arg_type="0", arg_eval=", Threshold="),
        ],
        name="Filter Image",
        category="52",
        canfail="True",
    ),
    "1861978578e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoWear Command/Command Filter",
        category="",
        canfail="",
    ),
    "186700340e": ActionCode(
        redirect="1040876951t",
        args=[],
        name="SecureTask",
        category="",
        canfail="",
    ),
    "186s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Test=", "l", "235"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Name="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Value="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", "Use Root"]),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Read Setting To="),
        ],
        name="Custom Setting",
        category="",
        canfail="",
    ),
    "1879487834t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoLocation Geofences",
        category="",
        canfail="",
    ),
    "187s": ActionCode(
        redirect="",
        args=[],
        name="Room",
        category="",
        canfail="",
    ),
    "187t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Image Quality", arg_type="0", arg_eval=", Image Quality="
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Delete From Memory After",
                arg_type="3",
                arg_eval=["e", ", Delete From Memory After"],
            ),
        ],
        name="Save Image",
        category="52",
        canfail="True",
    ),
    "188s": ActionCode(
        redirect="",
        args=[],
        name="Dark Mode",
        category="",
        canfail="",
    ),
    "188t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Source", arg_type="4", arg_eval="Source="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Max Width Or Height",
                arg_type="0",
                arg_eval=", Max Width or Height=",
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Respect EXIF Orientation",
                arg_type="3",
                arg_eval=["e", ", Respect EXIF Orientation"],
            ),
        ],
        name="Load Image",
        category="52",
        canfail="True",
    ),
    "18927444e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="5",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoApps Command",
        category="",
        canfail="",
    ),
    "189s": ActionCode(
        redirect="",
        args=[],
        name="Reaching",
        category="",
        canfail="",
    ),
    "189t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="From Left (%)", arg_type="0", arg_eval="From Left (%)="
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="From Right (%)", arg_type="0", arg_eval=", From Right (%)="
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="From Top (%)", arg_type="0", arg_eval=", From Top (%)="
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="From Bottom (%)", arg_type="0", arg_eval=", From Bottom (%)="
            ),
        ],
        name="Crop Image",
        category="52",
        canfail="True",
    ),
    "18t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="App", arg_type="2", arg_eval=["a", "", "App="]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", "Use Root"]),
        ],
        name="Kill App",
        category="15",
        canfail="True",
    ),
    "190s": ActionCode(
        redirect="",
        args=[],
        name="Any Sensor",
        category="",
        canfail="",
    ),
    "190t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Direction", arg_type="0", arg_eval=["Direction=", "l", "190"]
            ),
        ],
        name="Flip Image",
        category="52",
        canfail="True",
    ),
    "1910383148t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Regex",
        category="",
        canfail="",
    ),
    "1912522764t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Toast",
        category="",
        canfail="",
    ),
    "191971507t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="5",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoWear ADB Wifi",
        category="",
        canfail="",
    ),
    "191s": ActionCode(
        redirect="",
        args=[],
        name="Physical Activity",
        category="",
        canfail="",
    ),
    "191t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Direction", arg_type="0", arg_eval=["Direction=", "l", "191"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Degrees", arg_type="0", arg_eval=[", Degrees=", "l", "191a"]
            ),
        ],
        name="Rotate Image",
        category="52",
        canfail="True",
    ),
    "1928381944t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast Control Media",
        category="",
        canfail="",
    ),
    "192s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Device IDs/Names="),
        ],
        name="Matter Light (Experimental)",
        category="",
        canfail="",
    ),
    "192t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Direction=", "l", "192"]
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Sound", arg_type="1", arg_eval=", Sound="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Stream", arg_type="0", arg_eval=[", Stream=", "l", "171"]
            ),
        ],
        name="Play Ringtone",
        category="65",
        canfail="False",
    ),
    "193s": ActionCode(
        redirect="",
        args=[],
        name="Matter Light",
        category="",
        canfail="",
    ),
    "193t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Width", arg_type="0", arg_eval="Width="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Height", arg_type="0", arg_eval=", Height="),
        ],
        name="Resize Image",
        category="52",
        canfail="True",
    ),
    "194s": ActionCode(
        redirect="",
        args=[],
        name="Work Profile",
        category="",
        canfail="",
    ),
    "194t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Test", arg_type="0", arg_eval=[", Test=", "l", "194"]
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Test Scene",
        category="102",
        canfail="True",
    ),
    "1957670352t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear App",
        category="",
        canfail="",
    ),
    "1957681000e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoInput Gesture",
        category="",
        canfail="",
    ),
    "195s": ActionCode(
        redirect="",
        args=[],
        name="NFC Status",
        category="",
        canfail="",
    ),
    "195t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Test", arg_type="0", arg_eval=[", Test=", "l", "195"]
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Test Element",
        category="102",
        canfail="True",
    ),
    "196s": ActionCode(
        redirect="",
        args=[],
        name="Data Usage",
        category="",
        canfail="",
    ),
    "197s": ActionCode(
        redirect="",
        args=[],
        name="Compass Orientation",
        category="",
        canfail="",
    ),
    "197t": ActionCode(
        redirect="",
        args=[],
        name="Developer Settings",
        category="30",
        canfail="False",
    ),
    "198t": ActionCode(
        redirect="",
        args=[],
        name="Device Info Settings",
        category="30",
        canfail="False",
    ),
    "199558826t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="TouchTask Gestures",
        category="",
        canfail="",
    ),
    "199t": ActionCode(
        redirect="",
        args=[],
        name="Add Account Settings",
        category="30",
        canfail="False",
    ),
    "2000e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="2", arg_eval="Owner Application="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Title="),
        ],
        name="Notification Click",
        category="",
        canfail="",
    ),
    "2003e": ActionCode(
        redirect="",
        args=[],
        name="Missed Call",
        category="",
        canfail="",
    ),
    "2005e": ActionCode(
        redirect="",
        args=[],
        name="SMS Success",
        category="",
        canfail="",
    ),
    "200t": ActionCode(
        redirect="",
        args=[],
        name="All Settings",
        category="30",
        canfail="False",
    ),
    "2010186613t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Delete Cell Content",
        category="",
        canfail="",
    ),
    "2010e": ActionCode(
        redirect="",
        args=[],
        name="SMS Failure",
        category="",
        canfail="",
    ),
    "201e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="2", arg_eval="App="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", URL="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Texts="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", Extras="),
        ],
        name="Assistance Request",
        category="",
        canfail="",
    ),
    "201t": ActionCode(
        redirect="",
        args=[],
        name="Airplane Mode Settings",
        category="30",
        canfail="False",
    ),
    "2022280279t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Media",
        category="",
        canfail="",
    ),
    "202t": ActionCode(
        redirect="",
        args=[],
        name="APN Settings",
        category="30",
        canfail="False",
    ),
    "203e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval=["Priority=", "l", "4s"]),
        ],
        name="Battery Changed",
        category="",
        canfail="",
    ),
    "203t": ActionCode(
        redirect="",
        args=[],
        name="Date Settings",
        category="30",
        canfail="False",
    ),
    "2041559229t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Playlists",
        category="",
        canfail="",
    ),
    "2046367074t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Cancel",
        category="",
        canfail="",
    ),
    "204t": ActionCode(
        redirect="",
        args=[],
        name="Internal Storage Settings",
        category="30",
        canfail="False",
    ),
    "2050e": ActionCode(
        redirect="",
        args=[],
        name="Quick Setting Clicked",
        category="",
        canfail="",
    ),
    "2051074546t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Control Media",
        category="",
        canfail="",
    ),
    "205e": ActionCode(
        redirect="",
        args=[],
        name="Battery Full",
        category="",
        canfail="",
    ),
    "2063919988t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools System State",
        category="",
        canfail="",
    ),
    "206e": ActionCode(
        redirect="",
        args=[],
        name="Battery Overheating",
        category="",
        canfail="",
    ),
    "206t": ActionCode(
        redirect="",
        args=[],
        name="WIFI Settings",
        category="30",
        canfail="False",
    ),
    "2075e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Type=", "l", "235"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Name="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Value="),
        ],
        name="Custom Setting",
        category="",
        canfail="",
    ),
    "2076e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="ID="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Content="),
        ],
        name="NFC Tag",
        category="",
        canfail="",
    ),
    "2077e": ActionCode(
        redirect="",
        args=[],
        name="Secondary App Opened",
        category="",
        canfail="",
    ),
    "2078e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Package="),
        ],
        name="App Changed",
        category="",
        canfail="",
    ),
    "2079e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Type=", "l", "2079e"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Additional Time="),
        ],
        name="Volume Long Press",
        category="",
        canfail="",
    ),
    "2080e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Name="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Address="),
        ],
        name="BT Connected",
        category="",
        canfail="",
    ),
    "2081e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Track="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Album="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", Artist"),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Package="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=[", Type=", "l", "2081e"]),
        ],
        name="Music Track Changed",
        category="",
        canfail="",
    ),
    "2082e": ActionCode(
        redirect="",
        args=[],
        name="Network Changed",
        category="",
        canfail="",
    ),
    "2083e": ActionCode(
        redirect="",
        args=[],
        name="Significant Motion",
        category="",
        canfail="",
    ),
    "2084e": ActionCode(
        redirect="",
        args=[],
        name="Alarm Changed",
        category="",
        canfail="",
    ),
    "2085e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval="Component="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Filter="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Grep Filter"]),
        ],
        name="Logcat Entry",
        category="",
        canfail="",
    ),
    "2086e": ActionCode(
        redirect="",
        args=[],
        name="Pick Up Gesture",
        category="",
        canfail="",
    ),
    "2088e": ActionCode(
        redirect="",
        args=[],
        name="Any Sensor",
        category="",
        canfail="",
    ),
    "2089e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Port="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Method="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", Path="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Quick Response"),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Timeout="),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Only On Wifi"]
            ),
            ArgumentCode(
                arg_id="7", arg_required=True, arg_name="", arg_type="0", arg_eval=", Network Name/MAC Address="
            ),
        ],
        name="HTTP Request",
        category="",
        canfail="",
    ),
    "208e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval=["Priority=", "l", "4s"]),
        ],
        name="Display On",
        category="",
        canfail="",
    ),
    "208t": ActionCode(
        redirect="",
        args=[],
        name="Location Settings",
        category="30",
        canfail="False",
    ),
    "2090e": ActionCode(
        redirect="",
        args=[],
        name="Physical Activity",
        category="",
        canfail="",
    ),
    "2091e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval="Component="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Variables="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Last Variable Is Array"]
            ),
        ],
        name="Command",
        category="",
        canfail="",
    ),
    "2092e": ActionCode(
        redirect="",
        args=[],
        name="Power Menu Shown",
        category="",
        canfail="",
    ),
    "2093e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="2", arg_eval="Command="),
        ],
        name="Assistant Action",
        category="",
        canfail="",
    ),
    "2094e": ActionCode(
        redirect="",
        args=[],
        name="Call Screened",
        category="",
        canfail="",
    ),
    "2095e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Interval (ms)="),
        ],
        name="Tick",
        category="",
        canfail="",
    ),
    "2096e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval="Minimum Confidence="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Maximum Light="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=", Maximum Motion="),
        ],
        name="Sleeping",
        category="",
        canfail="",
    ),
    "2097e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="5", arg_eval=["", "e", "Ignore Set By Tasker"]
            ),
        ],
        name="Clipboard Changed",
        category="",
        canfail="",
    ),
    "2098e": ActionCode(
        redirect="",
        args=[],
        name="Accessibility Services Changed",
        category="",
        canfail="",
    ),
    "2099e": ActionCode(
        redirect="",
        args=[],
        name="Device Unlock Failed",
        category="",
        canfail="",
    ),
    "20t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Package/App Name", arg_type="2", arg_eval=["a", "", "App="]
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Exclude From Recent Apps",
                arg_type="3",
                arg_eval=["e", "Exclude From Recent Apps"],
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Always Start New Copy",
                arg_type="3",
                arg_eval=["e", "Always Start New Copy"],
            ),
        ],
        name="Launch App",
        category="15",
        canfail="True",
    ),
    "2100e": ActionCode(
        redirect="",
        args=[],
        name="Remote Action Token Changed",
        category="",
        canfail="",
    ),
    "2101e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="", arg_type="1", arg_eval=", Package Name"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="", arg_type="1", arg_eval=", Share Trigger"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="", arg_type="1", arg_eval=", Subject"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="", arg_type="1", arg_eval=", Text"),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="", arg_type="1", arg_eval=", Files"),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="", arg_type="1", arg_eval=", Mime Type"),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="", arg_type="1", arg_eval=", Action"),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="", arg_type="1", arg_eval=", Category"),
        ],
        name="Received Share",
        category="",
        canfail="",
    ),
    "2102e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="", arg_type="0", arg_eval=["e", "Added"]),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="", arg_type="0", arg_eval=["e", "Updated"]),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="", arg_type="0", arg_eval=["e", "Deleted"]),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="", arg_type="0", arg_eval=["e", "Other"]),
        ],
        name="Calendar Changed",
        category="",
        canfail="",
    ),
    "210e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval=["Priority=", "l", "4s"]),
        ],
        name="Display Off",
        category="",
        canfail="",
    ),
    "210t": ActionCode(
        redirect="",
        args=[],
        name="InputMethod Settings",
        category="30",
        canfail="False",
    ),
    "2114100406t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoLaunch Query",
        category="",
        canfail="",
    ),
    "211707263t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Global Actions",
        category="",
        canfail="",
    ),
    "211905330t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoContacts",
        category="",
        canfail="",
    ),
    "211t": ActionCode(
        redirect="",
        args=[],
        name="Sync Settings",
        category="30",
        canfail="False",
    ),
    "2123721228e": ActionCode(
        redirect="",
        args=[],
        name="AutoTools Assistant",
        category="",
        canfail="",
    ),
    "2124887619t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools OCR",
        category="",
        canfail="",
    ),
    "212t": ActionCode(
        redirect="",
        args=[],
        name="WIFI IP Settings",
        category="30",
        canfail="False",
    ),
    "2132875086t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Delete Rows/Columns",
        category="",
        canfail="",
    ),
    "2142731215t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Duplicate Sheet",
        category="",
        canfail="",
    ),
    "214t": ActionCode(
        redirect="",
        args=[],
        name="Wireless Settings",
        category="30",
        canfail="False",
    ),
    "215e": ActionCode(
        redirect="",
        args=[],
        name="Button: Camera",
        category="",
        canfail="",
    ),
    "216e": ActionCode(
        redirect="",
        args=[],
        name="Button: Long Search",
        category="",
        canfail="",
    ),
    "216t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="App", arg_type="1", arg_eval="App"),
        ],
        name="App Settings",
        category="30",
        canfail="False",
    ),
    "218t": ActionCode(
        redirect="",
        args=[],
        name="Bluetooth Settings",
        category="30",
        canfail="False",
    ),
    "219t": ActionCode(
        redirect="",
        args=[],
        name="Quick Settings",
        category="30",
        canfail="True",
    ),
    "220e": ActionCode(
        redirect="",
        args=[],
        name="File Moved",
        category="",
        canfail="",
    ),
    "220t": ActionCode(
        redirect="",
        args=[],
        name="Mobile Data Settings",
        category="30",
        canfail="False",
    ),
    "222e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name=", File", arg_type="1", arg_eval="File="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Event", arg_type="1", arg_eval=", Event="),
        ],
        name="File Modified",
        category="",
        canfail="",
    ),
    "222t": ActionCode(
        redirect="",
        args=[],
        name="Display Settings",
        category="30",
        canfail="False",
    ),
    "224e": ActionCode(
        redirect="",
        args=[],
        name="File Closed",
        category="",
        canfail="",
    ),
    "224t": ActionCode(
        redirect="",
        args=[],
        name="Locale Settings",
        category="30",
        canfail="False",
    ),
    "226e": ActionCode(
        redirect="",
        args=[],
        name="File Opened",
        category="",
        canfail="",
    ),
    "226t": ActionCode(
        redirect="",
        args=[],
        name="App Manage Settings",
        category="30",
        canfail="False",
    ),
    "227t": ActionCode(
        redirect="",
        args=[],
        name="Memory Card Settings",
        category="30",
        canfail="False",
    ),
    "228e": ActionCode(
        redirect="",
        args=[],
        name="File Deleted",
        category="",
        canfail="",
    ),
    "228t": ActionCode(
        redirect="",
        args=[],
        name="Network Operator Settings",
        category="30",
        canfail="False",
    ),
    "229t": ActionCode(
        redirect="",
        args=[],
        name="Quick Launch Settings",
        category="30",
        canfail="False",
    ),
    "22t": ActionCode(
        redirect="",
        args=[],
        name="Load Last App",
        category="15",
        canfail="True",
    ),
    "230e": ActionCode(
        redirect="",
        args=[],
        name="File Attribute Change",
        category="",
        canfail="",
    ),
    "230t": ActionCode(
        redirect="",
        args=[],
        name="Security Settings",
        category="30",
        canfail="False",
    ),
    "231t": ActionCode(
        redirect="",
        args=[],
        name="Search Settings",
        category="30",
        canfail="False",
    ),
    "232t": ActionCode(
        redirect="",
        args=[],
        name="Sound Settings",
        category="30",
        canfail="False",
    ),
    "234244923t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Unlock Screen",
        category="",
        canfail="",
    ),
    "234t": ActionCode(
        redirect="",
        args=[],
        name="Dictionary Settings",
        category="30",
        canfail="False",
    ),
    "235t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Test=", "l", "235"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Name", arg_type="1", arg_eval=", Name="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Value", arg_type="1", arg_eval=", Value="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", "Use Root"]),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Read Setting To", arg_type="1", arg_eval=", Read Setting To="
            ),
        ],
        name="Custom Setting",
        category="30",
        canfail="True",
    ),
    "236t": ActionCode(
        redirect="",
        args=[],
        name="Accessibility Settings",
        category="30",
        canfail="False",
    ),
    "237t": ActionCode(
        redirect="",
        args=[],
        name="Notification Listener Settings",
        category="30",
        canfail="False",
    ),
    "238t": ActionCode(
        redirect="",
        args=[],
        name="Privacy Settings",
        category="30",
        canfail="False",
    ),
    "239t": ActionCode(
        redirect="",
        args=[],
        name="Print Settings",
        category="30",
        canfail="False",
    ),
    "24081025t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Snooze",
        category="",
        canfail="",
    ),
    "244t": ActionCode(
        redirect="",
        args=[],
        name="Toggle Split Screen",
        category="15",
        canfail="True",
    ),
    "245t": ActionCode(
        redirect="",
        args=[],
        name="Back Button",
        category="55",
        canfail="True",
    ),
    "246t": ActionCode(
        redirect="",
        args=[],
        name="Long Power Button",
        category="55",
        canfail="True",
    ),
    "247t": ActionCode(
        redirect="",
        args=[],
        name="Show Recents",
        category="15",
        canfail="True",
    ),
    "248t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Dim", arg_type="3", arg_eval="File="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Lock", arg_type="3", arg_eval=["e", "Dim"]),
        ],
        name="Turn Off",
        category="40",
        canfail="True",
    ),
    "249t": ActionCode(
        redirect="",
        args=[],
        name="System Screenshot",
        category="55",
        canfail="True",
    ),
    "250t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=False, arg_name="Recipient(s)", arg_type="1", arg_eval="Recipient(s)="
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Message", arg_type="1", arg_eval="Message="),
        ],
        name="Compose SMS",
        category="90",
        canfail="False",
    ),
    "251t": ActionCode(
        redirect="",
        args=[],
        name="Battery Settings",
        category="30",
        canfail="False",
    ),
    "252t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="App", arg_type="2", arg_eval="App="),
        ],
        name="Set SMS App",
        category="90",
        canfail="False",
    ),
    "254t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Speakerphone",
        category="20",
        canfail="False",
    ),
    "256t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Vibrate On Ringer",
        category="20",
        canfail="False",
    ),
    "257t": ActionCode(
        redirect="",
        args=[],
        name="Power Usage Settings",
        category="30",
        canfail="False",
    ),
    "258t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="Vibrate On Notify",
        category="20",
        canfail="False",
    ),
    "259t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Notification Pulse",
        category="20",
        canfail="False",
    ),
    "25t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Page", arg_type="0", arg_eval="Page"),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Package", arg_type="1", arg_eval="Package"),
        ],
        name="Go Home",
        category="15",
        canfail="False",
    ),
    "260559060t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Block",
        category="",
        canfail="",
    ),
    "263029931t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Unlock Screen",
        category="",
        canfail="",
    ),
    "268157305t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Tiles",
        category="",
        canfail="",
    ),
    "294t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Bluetooth",
        category="80",
        canfail="True",
    ),
    "295t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
        ],
        name="Bluetooth ID",
        category="80",
        canfail="False",
    ),
    "296t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Bluetooth Voice",
        category="90",
        canfail="False",
    ),
    "2e": ActionCode(
        redirect="",
        args=[],
        name="Phone Offhook",
        category="",
        canfail="",
    ),
    "2s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Status=", "l", "switch_set"]
            ),
        ],
        name="BT Status",
        category="",
        canfail="",
    ),
    "3000e": ActionCode(
        redirect="",
        args=[],
        name="Gesture",
        category="",
        canfail="",
    ),
    "3001e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Axis=", "l", "3001e"]),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=["Sensitivity=", "l", "3001ea"]
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=["Duration=", "l", "3001eb"]
            ),
        ],
        name="Shake",
        category="",
        canfail="",
    ),
    "300e": ActionCode(
        redirect="",
        args=[],
        name="Date Set",
        category="",
        canfail="",
    ),
    "300t": ActionCode(
        redirect="",
        args=[],
        name="Anchor",
        category="105",
        canfail="False",
    ),
    "301t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="Mic Mute",
        category="20",
        canfail="False",
    ),
    "302e": ActionCode(
        redirect="",
        args=[],
        name="Time/Date Set",
        category="",
        canfail="",
    ),
    "303e": ActionCode(
        redirect="",
        args=[],
        name="Timer Change",
        category="",
        canfail="",
    ),
    "303t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval=["e", ", Display"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
        ],
        name="Alarm Volume",
        category="20",
        canfail="False",
    ),
    "304e": ActionCode(
        redirect="",
        args=[],
        name="Timezone Set",
        category="",
        canfail="",
    ),
    "304t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval=["e", ", Display"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
        ],
        name="Ringer Volume",
        category="20",
        canfail="False",
    ),
    "3050e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval=", Variable="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Value="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", User Variables Only"]
            ),
        ],
        name="Variable Set",
        category="",
        canfail="",
    ),
    "305e": ActionCode(
        redirect="",
        args=[],
        name="Alarm Clock",
        category="",
        canfail="",
    ),
    "305t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval=["e", ", Display"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
        ],
        name="Notification Volume",
        category="20",
        canfail="False",
    ),
    "3060e": ActionCode(
        redirect="",
        args=[],
        name="Variable Cleared",
        category="",
        canfail="",
    ),
    "306e": ActionCode(
        redirect="",
        args=[],
        name="Alarm Done",
        category="",
        canfail="",
    ),
    "306t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval="Display"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval="Sound"),
        ],
        name="In-Call Volume",
        category="20",
        canfail="False",
    ),
    "3071e": ActionCode(
        redirect="",
        args=[],
        name="Zoom Click",
        category="",
        canfail="",
    ),
    "307e": ActionCode(
        redirect="",
        args=[],
        name="Monitor Start",
        category="",
        canfail="",
    ),
    "307t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval=["e", ", Display"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
        ],
        name="Media Volume",
        category="20",
        canfail="False",
    ),
    "308t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval=["e", ", Display"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
        ],
        name="System Volume",
        category="20",
        canfail="False",
    ),
    "309e": ActionCode(
        redirect="",
        args=[],
        name="Steps Taken",
        category="",
        canfail="",
    ),
    "309t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval="Display"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval="Sound"),
        ],
        name="DTMF Volume",
        category="20",
        canfail="False",
    ),
    "30s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Type=", "l", "30s"]),
        ],
        name="Headset Plugged",
        category="",
        canfail="",
    ),
    "30t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="MS", arg_type="0", arg_eval="MS="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Seconds", arg_type="0", arg_eval=", Seconds="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Minutes", arg_type="0", arg_eval=", Minutes="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Hours", arg_type="0", arg_eval=", Hours="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Days", arg_type="0", arg_eval=", Days="),
        ],
        name="Wait",
        category="105",
        canfail="True",
    ),
    "310t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "310"]),
        ],
        name="Silent Mode",
        category="20",
        canfail="False",
    ),
    "311t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval=["e", ", Display"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
        ],
        name="BT Voice Volume",
        category="20",
        canfail="False",
    ),
    "312t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "312"]),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Allow Callers", arg_type="0", arg_eval="Allow Callers"
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Allow Repeat Callers",
                arg_type="3",
                arg_eval="Allow Repeat Callers",
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Allow SMS Senders", arg_type="0", arg_eval="Allow SMS Senders"
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Allow Categories", arg_type="1", arg_eval="Allow Categories"
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Suppressed Effects",
                arg_type="1",
                arg_eval="Suppressed Effects",
            ),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Interrupt Mode",
        category="20",
        canfail="True",
    ),
    "313t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "313"]),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Ignore DND", arg_type="3", arg_eval=["e", ", Ignore DND"]
            ),
        ],
        name="Sound Mode",
        category="20",
        canfail="False",
    ),
    "314t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "314"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Subtitle", arg_type="1", arg_eval=", Subtitle="),
            ArgumentCode(
                arg_id="3", arg_required=False, arg_name="Description", arg_type="1", arg_eval=", Description="
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=False,
                arg_name="Cancel Button Text",
                arg_type="1",
                arg_eval=", Cancel Button Text=",
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Number Of Attempts",
                arg_type="0",
                arg_eval=", Number of Attempts=",
            ),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="Read Result To", arg_type="1", arg_eval=", Read Result Into="
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Timeout (Seconds)",
                arg_type="0",
                arg_eval=", Timeout (Seconds)=",
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Confirmation Required",
                arg_type="3",
                arg_eval=["e", ", Confirmation Required"],
            ),
            ArgumentCode(
                arg_id="9",
                arg_required=True,
                arg_name="Device Credentials Allowed",
                arg_type="3",
                arg_eval=["e", ", Device Credentials Allowed"],
            ),
        ],
        name="Authentication Dialog",
        category="55",
        canfail="True",
    ),
    "316t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Size", arg_type="0", arg_eval=["Size=", "l", "316"]),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Manual", arg_type="1", arg_eval=", Manual="),
        ],
        name="Display Size",
        category="40",
        canfail="True",
    ),
    "317t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="NFC",
        category="80",
        canfail="True",
    ),
    "318t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "318"]),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Alternative Method (Check Help)",
                arg_type="3",
                arg_eval=["e", ", Alternative Method (Check Help)"],
            ),
        ],
        name="Force Rotation",
        category="40",
        canfail="True",
    ),
    "319692633t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoShare Process Text",
        category="",
        canfail="",
    ),
    "319t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0",
                arg_required=True,
                arg_name="Required Permissions",
                arg_type="1",
                arg_eval="Required Permissions=",
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=False,
                arg_name="Prompt If Not Granted",
                arg_type="1",
                arg_eval=", Prompt If Not Granted=",
            ),
        ],
        name="Ask Permissions",
        category="104",
        canfail="True",
    ),
    "320t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Host", arg_type="1", arg_eval=", Host="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Number", arg_type="0", arg_eval=", Number="),
            ArgumentCode(
                arg_id="2",
                arg_required=False,
                arg_name="Average Result Variable",
                arg_type="1",
                arg_eval=", Average Result Variable=",
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=False,
                arg_name="Min Result Variable",
                arg_type="1",
                arg_eval=", Min Result Variable=",
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=False,
                arg_name="Max Result Variable",
                arg_type="1",
                arg_eval=", Max Result Variable=",
            ),
        ],
        name="Ping",
        category="80",
        canfail="True",
    ),
    "321t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Google Drive Account",
                arg_type="1",
                arg_eval="Google Drive/Account=",
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Data / File", arg_type="1", arg_eval=", Data/File="),
            ArgumentCode(
                arg_id="3",
                arg_required=False,
                arg_name="Remote File Name",
                arg_type="1",
                arg_eval=", Remote File Name=",
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Remote Folder", arg_type="1", arg_eval=", Remote Folder="
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Content Description",
                arg_type="1",
                arg_eval=", Content Description=",
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Overwrite If Exists",
                arg_type="3",
                arg_eval=["e", ", Overwrite If Exists"],
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Publicly Share File",
                arg_type="3",
                arg_eval=["e", ", Publicly Share File"],
            ),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Mime Type", arg_type="1", arg_eval=", Mime Type="),
        ],
        name="GD Upload",
        category="51",
        canfail="True",
    ),
    "322t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Path", arg_type="1", arg_eval="Path="),
            ArgumentCode(
                arg_id="1",
                arg_required=False,
                arg_name="Google Drive Account",
                arg_type="1",
                arg_eval=", Google Drive Account=",
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Include User Vars/Prefs",
                arg_type="3",
                arg_eval=["e", ", Include User Vars/Prefs"],
            ),
        ],
        name="Data Backup",
        category="110",
        canfail="True",
    ),
    "323t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Bluetooth", arg_type="3", arg_eval=["e", "Bluetooth"]
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Cell", arg_type="3", arg_eval=["e", ", Cell"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="NFC", arg_type="3", arg_eval=["e", ", NFC"]),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Wifi", arg_type="3", arg_eval=["e", ", Wifi"]),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Wimax", arg_type="3", arg_eval=["e", ", Wimax"]),
        ],
        name="Airplane Radios",
        category="80",
        canfail="False",
    ),
    "324t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Google Drive Account",
                arg_type="1",
                arg_eval="Google Drive Account=",
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Type=", "l", "324"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Files or Folders",
                arg_type="0",
                arg_eval=[", Files or Folders=", "l", "324a"],
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Remote Folder", arg_type="1", arg_eval="Remote Folder"
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Query", arg_type="1", arg_eval=", Query="),
        ],
        name="GD List",
        category="51",
        canfail="True",
    ),
    "325t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Google Drive Account",
                arg_type="1",
                arg_eval="Google Drive Account=",
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Trash Value",
                arg_type="0",
                arg_eval=[", Trash Value=", "l", "325"],
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Type=", "l", "325a"]
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="File Id", arg_type="1", arg_eval=", File ID="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Remote Folder", arg_type="1", arg_eval=", Path="),
            ArgumentCode(
                arg_id="6",
                arg_required=False,
                arg_name="Remote File Name",
                arg_type="1",
                arg_eval=", Remote File Name=",
            ),
            ArgumentCode(arg_id="7", arg_required=True, arg_name="Remote Name", arg_type="1", arg_eval="Remote Name"),
        ],
        name="GD Trash",
        category="51",
        canfail="True",
    ),
    "326t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Google Drive Account",
                arg_type="1",
                arg_eval="Google Drive Account=",
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Type=", "l", "325a"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="File Id", arg_type="1", arg_eval=", File ID="),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Remote Folder", arg_type="1", arg_eval=", Remote Folder="
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Remote File Name",
                arg_type="1",
                arg_eval=", Remote File Name=",
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Local Path", arg_type="1", arg_eval=", Local Path="),
        ],
        name="GD Download",
        category="51",
        canfail="True",
    ),
    "327t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=False,
                arg_name="Google Drive Account",
                arg_type="1",
                arg_eval="Google Drive Account=",
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Full Access", arg_type="3", arg_eval=["e", ", Full Access"]
            ),
        ],
        name="GD Sign In",
        category="51",
        canfail="True",
    ),
    "328t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Input", arg_type="1", arg_eval="Input"),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Time Between Inputs",
                arg_type="0",
                arg_eval=", Time Between Inputs=",
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Don't Restore Keyboard",
                arg_type="3",
                arg_eval=["e", ", Don't Restore Keyboard"],
            ),
        ],
        name="Keyboard",
        category="55",
        canfail="True",
    ),
    "329t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Left", arg_type="1", arg_eval="Left="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Center", arg_type="1", arg_eval="Center="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Right", arg_type="1", arg_eval="Right="),
        ],
        name="Navigation Bar",
        category="55",
        canfail="True",
    ),
    "330t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=False, arg_name="Payload To Write", arg_type="1", arg_eval="Payload To Write="
            ),
            ArgumentCode(
                arg_id="2", arg_required=False, arg_name="Payload Type", arg_type="1", arg_eval=", Payload Type="
            ),
        ],
        name="NFC Tag",
        category="80",
        canfail="True",
    ),
    "331t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Auto-Sync",
        category="80",
        canfail="False",
    ),
    "332t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="GPS",
        category="60",
        canfail="True",
    ),
    "333t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Airplane Mode",
        category="80",
        canfail="True",
    ),
    "334t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Text/SSML", arg_type="1", arg_eval="Test/SSML="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Voice", arg_type="1", arg_eval=", Voice="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Stream", arg_type="0", arg_eval=[", Type=", "l", "171"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Pitch", arg_type="0", arg_eval=", Pitch="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Speed", arg_type="0", arg_eval=", Speed="),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="File", arg_type="1", arg_eval=", File="),
            ArgumentCode(
                arg_id="7",
                arg_required=False,
                arg_name="Override API Key",
                arg_type="1",
                arg_eval=", Override API Key=",
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Respect Audio Focus",
                arg_type="3",
                arg_eval="Respect Audio Focus",
            ),
        ],
        name="Say WaveNet",
        category="10",
        canfail="True",
    ),
    "335t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=False, arg_name="Package/App Name", arg_type="1", arg_eval="Package/App Name="
            ),
            ArgumentCode(
                arg_id="2", arg_required=False, arg_name="Ignore Packages", arg_type="1", arg_eval=", Ignore Packages="
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Ignore Unlaunchable Apps",
                arg_type="3",
                arg_eval=["e", ", Ignore Unlaunchable Apps"],
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Get All Details",
                arg_type="3",
                arg_eval=["e", ", Get All Details"],
            ),
        ],
        name="App Info",
        category="15",
        canfail="True",
    ),
    "337t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Package", arg_type="1", arg_eval="Package="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Category", arg_type="1", arg_eval=", Category="),
        ],
        name="Notification Settings",
        category="30",
        canfail="False",
    ),
    "338t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Category", arg_type="1", arg_eval="Category="),
        ],
        name="Notification Category Info",
        category="30",
        canfail="True",
    ),
    "339t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Method", arg_type="0", arg_eval=["Method=", "l", "339"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="URL", arg_type="1", arg_eval=", URL="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Headers", arg_type="1", arg_eval=", Headers="),
            ArgumentCode(
                arg_id="4",
                arg_required=False,
                arg_name="Query Parameters",
                arg_type="1",
                arg_eval=", Query Parameters=",
            ),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Body", arg_type="1", arg_eval=", Body="),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="File To Send", arg_type="1", arg_eval=", File To Send="
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=False,
                arg_name="File/Directory To Save With Output",
                arg_type="1",
                arg_eval=", File/Directory To Save With Output=",
            ),
            ArgumentCode(
                arg_id="8", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Timeout="
            ),
            ArgumentCode(
                arg_id="9",
                arg_required=True,
                arg_name="Trust Any Certificate",
                arg_type="3",
                arg_eval=["e", ", Trust Any Certificate"],
            ),
            ArgumentCode(
                arg_id="10",
                arg_required=True,
                arg_name="Automatically Follow Redirects",
                arg_type="3",
                arg_eval=["e", ", Automatically Follow Redirects"],
            ),
            ArgumentCode(
                arg_id="11", arg_required=True, arg_name="Use Cookies", arg_type="3", arg_eval=["e", ", Use Cookies"]
            ),
            ArgumentCode(
                arg_id="12",
                arg_required=True,
                arg_name="Structure Output (JSON, etc)",
                arg_type="3",
                arg_eval=["e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="HTTP Request",
        category="80",
        canfail="True",
    ),
    "340t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Action", arg_type="0", arg_eval=["Action=", "l", "340"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Device", arg_type="1", arg_eval=", Device="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Timeout="
            ),
        ],
        name="Bluetooth Connection",
        category="80",
        canfail="True",
    ),
    "341t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "341"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval="Data"),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Test Net",
        category="80",
        canfail="True",
    ),
    "342t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "342"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="Test File",
        category="50",
        canfail="True",
    ),
    "343t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "343"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Test Media",
        category="65",
        canfail="True",
    ),
    "344636446t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoVoice Trigger Alexa Routine",
        category="",
        canfail="",
    ),
    "344t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "344"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Test App",
        category="15",
        canfail="True",
    ),
    "345t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "345"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Results In="
            ),
        ],
        name="Test Variable",
        category="120",
        canfail="True",
    ),
    "346t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "346"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Test Phone",
        category="90",
        canfail="True",
    ),
    "347t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "347"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Test Tasker",
        category="110",
        canfail="False",
    ),
    "34829087e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="Tools & AmazFit",
        category="",
        canfail="",
    ),
    "348t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "348"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Store Result In="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval="Store Result In"
            ),
        ],
        name="Test Display",
        category="40",
        canfail="False",
    ),
    "349t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "349"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Store Result In="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval="Store Result In"
            ),
        ],
        name="Test System",
        category="104",
        canfail="False",
    ),
    "351t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Method", arg_type="0", arg_eval=["Method=", "l", "351"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Client ID", arg_type="1", arg_eval=", Client ID="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Client Secret", arg_type="1", arg_eval=", Client Secret="
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Endpoint To Get Code",
                arg_type="1",
                arg_eval=", Endpoint To Get Code=",
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Endpoint To Get Refresh Token",
                arg_type="1",
                arg_eval=", Endpoint To Get Refresh Token=",
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Scopes", arg_type="1", arg_eval=", Scopes="),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Force Re-Authentication",
                arg_type="3",
                arg_eval=["e", "Force Re-Authentication"],
            ),
            ArgumentCode(
                arg_id="8", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Timeout="
            ),
            ArgumentCode(arg_id="9", arg_required=True, arg_name="Username", arg_type="1", arg_eval=", Username="),
            ArgumentCode(arg_id="10", arg_required=True, arg_name="Password", arg_type="1", arg_eval=", Password="),
        ],
        name="HTTP Auth",
        category="80",
        canfail="True",
    ),
    "352t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Network Type",
                arg_type="0",
                arg_eval=["Network Type=", "l", "352"],
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="From", arg_type="1", arg_eval=", From="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="To", arg_type="1", arg_eval=", To="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Package", arg_type="1", arg_eval=", Package="),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="SIM Card", arg_type="1", arg_eval="SIM Card"),
        ],
        name="Get Network Data Usage",
        category="80",
        canfail="True",
    ),
    "354t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Variable Array", arg_type="1", arg_eval="Variable Array="
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Values", arg_type="1", arg_eval=", Values="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Splitter", arg_type="1", arg_eval=", Splitter="),
        ],
        name="Array Set",
        category="120",
        canfail="True",
    ),
    "355t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Variable Array", arg_type="1", arg_eval="Variable Array="
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Position", arg_type="0", arg_eval=", Position="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Value", arg_type="1", arg_eval=", Value="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Fill Spaces", arg_type="3", arg_eval=["e", ", Fill Spaces"]
            ),
        ],
        name="Array Push",
        category="120",
        canfail="False",
    ),
    "356t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Variable Array", arg_type="1", arg_eval="Variable Array="
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Position", arg_type="0", arg_eval=", Position="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="To Var", arg_type="1", arg_eval=", To Var="),
        ],
        name="Array Pop",
        category="120",
        canfail="False",
    ),
    "357t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Variable Array", arg_type="1", arg_eval="Variable Array="
            ),
        ],
        name="Array Clear",
        category="120",
        canfail="False",
    ),
    "358t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "358"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Device", arg_type="1", arg_eval=", Device="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Timeout="
            ),
        ],
        name="Bluetooth Info",
        category="80",
        canfail="True",
    ),
    "35t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="MS", arg_type="0", arg_eval=["if"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Seconds", arg_type="0", arg_eval="MS="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Minutes", arg_type="0", arg_eval=", Seconds="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Hours", arg_type="0", arg_eval=", Minutes="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Days", arg_type="0", arg_eval=", Hours="),
        ],
        name="Wait Until",
        category="105",
        canfail="False",
    ),
    "360t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(
                arg_id="3", arg_required=False, arg_name="Default Input", arg_type="1", arg_eval=", Default Input="
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Close After (Seconds)",
                arg_type="0",
                arg_eval=", Close After (Seconds)=",
            ),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Input Type", arg_type="1", arg_eval=", Input Type="),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="Use HTML", arg_type="3", arg_eval=["e", ", Use HTML"]
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Pre-Select Input",
                arg_type="3",
                arg_eval=["e", ", Pre-Select Input"],
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=False,
                arg_name="Output Variable Name",
                arg_type="1",
                arg_eval="Output Variable Name",
            ),
        ],
        name="Input Dialog",
        category="55",
        canfail="True",
    ),
    "361t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Dark Mode",
        category="40",
        canfail="True",
    ),
    "362t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Assistant", arg_type="1", arg_eval="Assistant="),
        ],
        name="Set Assistant",
        category="104",
        canfail="True",
    ),
    "363t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="SIM Card", arg_type="1", arg_eval="SIM Card"),
        ],
        name="Mobile Network Type",
        category="80",
        canfail="True",
    ),
    "364t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Minutes Difference",
                arg_type="0",
                arg_eval="Minutes Difference=",
            ),
        ],
        name="Test Next Alarm",
        category="104",
        canfail="True",
    ),
    "365t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Function", arg_type="1", arg_eval="Function="),
        ],
        name="Tasker Function",
        category="110",
        canfail="True",
    ),
    "366t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval="Timeout (Seconds)="
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=False,
                arg_name="Minimum Accuracy (meters)",
                arg_type="1",
                arg_eval=", Minimum Accuracy (meters)=",
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=False,
                arg_name="Speed (meters/second)",
                arg_type="1",
                arg_eval=", Speed (meters/second)=",
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=False,
                arg_name="Altitude (meters)",
                arg_type="1",
                arg_eval=", Altitude (meters)=",
            ),
            ArgumentCode(
                arg_id="5", arg_required=False, arg_name="Near Location", arg_type="1", arg_eval=", Near Location="
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Enable Location If Needed",
                arg_type="3",
                arg_eval=["e", ", Enable Location If Needed"],
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Last Location If Timeout",
                arg_type="3",
                arg_eval=["e", ", Last Location If Timeout"],
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=False,
                arg_name="Min Speed Accuracy (m/s)",
                arg_type="1",
                arg_eval=", Min Speed Accuracy (m/s)=",
            ),
            ArgumentCode(
                arg_id="9",
                arg_required=True,
                arg_name="Force High Accuracy",
                arg_type="3",
                arg_eval=["e", ", Force High Accuracy"],
            ),
        ],
        name="Get Location v2",
        category="60",
        canfail="True",
    ),
    "367t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Camera",
        category="15",
        canfail="True",
    ),
    "368t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Select Radius", arg_type="3", arg_eval=["e", ", Select Radius"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=False,
                arg_name="Initial Location",
                arg_type="1",
                arg_eval=", Initial Location=",
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Set=", "l", "368"]),
        ],
        name="Pick Location",
        category="60",
        canfail="True",
    ),
    "369t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Variable Array", arg_type="1", arg_eval="Variable Array="
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Type=", "l", "369"]
            ),
        ],
        name="Array Process",
        category="120",
        canfail="False",
    ),
    "370t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Shortcut="
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Shortcut", arg_type="1", arg_eval="Shortcut"),
        ],
        name="Shortcut",
        category="15",
        canfail="True",
    ),
    "371t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval="Cmd"),
        ],
        name="Astrid",
        category="130",
        canfail="False",
    ),
    "372t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Type", arg_type="1", arg_eval="Type="),
        ],
        name="Sensor Info",
        category="104",
        canfail="True",
    ),
    "373t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Type", arg_type="1", arg_eval="Type="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Timeout (Seconds)",
                arg_type="0",
                arg_eval=", Timeout (Seconds)=",
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Convert Orientation",
                arg_type="3",
                arg_eval=["e", ", Convert Orientation"],
            ),
        ],
        name="Test Sensor",
        category="104",
        canfail="True",
    ),
    "374t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Type=", "l", "374"]),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Output File", arg_type="1", arg_eval=", Output File="
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Video Encoder", arg_type="1", arg_eval=", Video Encoder="
            ),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Resolution", arg_type="1", arg_eval=", Resolution="),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="Video Bitrate", arg_type="1", arg_eval=", Video Bitrate="
            ),
            ArgumentCode(
                arg_id="7", arg_required=False, arg_name="Video Framerate", arg_type="1", arg_eval="Video Framerate"
            ),
        ],
        name="Screen Capture",
        category="40",
        canfail="True",
    ),
    "375t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Command", arg_type="1", arg_eval="Command"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Host", arg_type="1", arg_eval="Host"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Port", arg_type="1", arg_eval="Port"),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval="Timeout (Seconds)"
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Enable Debugging (Check Help)",
                arg_type="3",
                arg_eval="Enable Debugging (Check Help)",
            ),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="Result Encoding", arg_type="1", arg_eval="Result Encoding"
            ),
        ],
        name="ADB Wifi",
        category="35",
        canfail="True",
    ),
    "376t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Mime Type", arg_type="1", arg_eval=", Mime Type="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Show Chooser Dialog",
                arg_type="3",
                arg_eval=["e", ", Show Chooser Dialog"],
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=False,
                arg_name="Chooser Dialog Title",
                arg_type="1",
                arg_eval=", Chooser Dialog Title=",
            ),
        ],
        name="Share File",
        category="50",
        canfail="True",
    ),
    "377t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Button 1", arg_type="1", arg_eval=", Button 1="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Button 2", arg_type="1", arg_eval=", Button 2="),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Button 3", arg_type="1", arg_eval=", Button 3="),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Close After (Seconds)",
                arg_type="0",
                arg_eval=", Close After (Seconds)=",
            ),
            ArgumentCode(
                arg_id="7", arg_required=True, arg_name="Use HTML", arg_type="3", arg_eval=["e", ", Use HTML"]
            ),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Image", arg_type="1", arg_eval=", Image="),
            ArgumentCode(
                arg_id="9",
                arg_required=False,
                arg_name="Max Width Or Height",
                arg_type="1",
                arg_eval=", Max Width or Height=",
            ),
        ],
        name="Text/Image Dialog",
        category="55",
        canfail="True",
    ),
    "378t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "378"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Items", arg_type="1", arg_eval=", Items="),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Selected Items", arg_type="1", arg_eval=", Long Click Task="
            ),
            ArgumentCode(
                arg_id="5", arg_required=False, arg_name="Long Click Task", arg_type="1", arg_eval="Long Click Task"
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Button 1", arg_type="1", arg_eval=", Button 1="),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Button 2", arg_type="1", arg_eval=", Button 2="),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Button 3", arg_type="1", arg_eval=", Button 3="),
            ArgumentCode(
                arg_id="9",
                arg_required=True,
                arg_name="Close After (Seconds)",
                arg_type="0",
                arg_eval=", Close After (Seconds)=",
            ),
            ArgumentCode(
                arg_id="10", arg_required=True, arg_name="Use HTML", arg_type="3", arg_eval=["e", ", Use HTML"]
            ),
            ArgumentCode(
                arg_id="11",
                arg_required=True,
                arg_name="First Visible Index",
                arg_type="0",
                arg_eval=", First Visible Index=",
            ),
            ArgumentCode(
                arg_id="12", arg_required=True, arg_name="Hide Filter", arg_type="3", arg_eval=["e", ", Hide Filter"]
            ),
            ArgumentCode(arg_id="13", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
        ],
        name="List Dialog",
        category="55",
        canfail="True",
    ),
    "379t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Action", arg_type="0", arg_eval=["Action=", "l", "379"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Package/App Name", arg_type="2", arg_eval=", App="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Function", arg_type="1", arg_eval=", Function="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Enable", arg_type="3", arg_eval=["e", ", Enable"]),
            ArgumentCode(
                arg_id="5", arg_required=False, arg_name="User Restrictions", arg_type="1", arg_eval=", Restrictions="
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Permission", arg_type="1", arg_eval="Permission"),
        ],
        name="Device Admin/Owner",
        category="104",
        canfail="True",
    ),
    "37s": ActionCode(
        redirect="",
        args=[],
        name="Variable Set",
        category="",
        canfail="",
    ),
    "37t": ActionCode(
        redirect="",
        args=[],
        name="If",
        category="105",
        canfail="False",
    ),
    "380t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Request ID", arg_type="1", arg_eval="Request ID="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Status Code", arg_type="1", arg_eval=", Status Code="
            ),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Headers", arg_type="1", arg_eval=", Headers="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "380"]),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Body", arg_type="1", arg_eval=""),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="File", arg_type="1", arg_eval=", File="),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Mime Type", arg_type="1", arg_eval=", Mime Type="),
            ArgumentCode(
                arg_id="8", arg_required=True, arg_name="File Inline", arg_type="3", arg_eval=["e", ", File Inline"]
            ),
            ArgumentCode(arg_id="9", arg_required=True, arg_name="URL", arg_type="1", arg_eval="URL"),
        ],
        name="HTTP Response",
        category="80",
        canfail="True",
    ),
    "381t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Contact="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Contact", arg_type="1", arg_eval=", App="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="App", arg_type="1", arg_eval="App"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Text", arg_type="1", arg_eval="Text"),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Back Out", arg_type="3", arg_eval="Back Out"),
        ],
        name="Contact Via App",
        category="90",
        canfail="True",
    ),
    "383t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Contact=", "l", "383"]
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval="Continue Task Immediately",
            ),
        ],
        name="Settings Panel",
        category="30",
        canfail="False",
    ),
    "384t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="ID", arg_type="1", arg_eval="ID="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Action", arg_type="0", arg_eval=[", Action=", "l", "384"]
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Type=", "l", "384a"]
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Subtitle", arg_type="1", arg_eval=", Subtitle="),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Icon", arg_type="1", arg_eval=", Icon="),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Command", arg_type="1", arg_eval=", Command="),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Active", arg_type="1", arg_eval=", Active="),
            ArgumentCode(arg_id="9", arg_required=False, arg_name="Range Min", arg_type="1", arg_eval=", Range Min="),
            ArgumentCode(arg_id="10", arg_required=False, arg_name="Range Max", arg_type="1", arg_eval=", Range Max="),
            ArgumentCode(
                arg_id="11", arg_required=False, arg_name="Range Current", arg_type="1", arg_eval=", Range Current="
            ),
            ArgumentCode(arg_id="12", arg_required=False, arg_name="Range Step", arg_type="1", arg_eval="Range Step="),
            ArgumentCode(
                arg_id="13", arg_required=False, arg_name="Range Format", arg_type="1", arg_eval=", Range Format="
            ),
            ArgumentCode(
                arg_id="14",
                arg_required=True,
                arg_name="Can Use On Locked Device",
                arg_type="3",
                arg_eval=["e", ", Can Use On Locked Device"],
            ),
        ],
        name="Device Control (Power Menu Action)",
        category="55",
        canfail="True",
    ),
    "385t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Command", arg_type="1", arg_eval="Command="),
        ],
        name="Command",
        category="110",
        canfail="True",
    ),
    "386t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=["ID=", "l", "386"]
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Disallow/Allow",
                arg_type="0",
                arg_eval=["e", ", Skip Call Log"],
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Reject", arg_type="3", arg_eval=["e", ", Skip Notification"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Silence", arg_type="3", arg_eval="Silence"),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Skip Call Log", arg_type="3", arg_eval="Skip Call Log"
            ),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Skip Notification", arg_type="3", arg_eval="Skip Notification"
            ),
        ],
        name="Call Screening",
        category="90",
        canfail="True",
    ),
    "387t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Display", arg_type="3", arg_eval=["e", ", Display"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Sound", arg_type="3", arg_eval=["e", ", Sound"]),
        ],
        name="Accessibility Volume",
        category="20",
        canfail="True",
    ),
    "388543774t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Insert Empty Rows/Columns",
        category="",
        canfail="",
    ),
    "389t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Names", arg_type="1", arg_eval="Names="),
            ArgumentCode(
                arg_id="2",
                arg_required=False,
                arg_name="Variable Names Splitter",
                arg_type="1",
                arg_eval=", Variable Name Splitter=",
            ),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Values", arg_type="1", arg_eval=", Values="),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Values Splitter", arg_type="1", arg_eval=", Values Splitter="
            ),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Do Maths", arg_type="3", arg_eval=["e", ", Do Maths"]
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Max Rounding Digits",
                arg_type="0",
                arg_eval=["e", ", Keep Existing"],
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Keep Existing",
                arg_type="3",
                arg_eval=["e", ", Structure Output (JSON, etc)"],
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Structure Output (JSON, etc)",
                arg_type="3",
                arg_eval="Structure Output (JSON, etc)",
            ),
        ],
        name="Multiple Variables Set",
        category="120",
        canfail="True",
    ),
    "38t": ActionCode(
        redirect="",
        args=[],
        name="End If",
        category="105",
        canfail="False",
    ),
    "390t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Type", arg_type="1", arg_eval="Type="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Default Input", arg_type="1", arg_eval=", Default Input="
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Close After (Seconds)",
                arg_type="0",
                arg_eval=", Close After (Seconds)=",
            ),
        ],
        name="Pick Input Dialog",
        category="55",
        canfail="True",
    ),
    "391t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Action", arg_type="0", arg_eval=["Action=", "l", "391"]
            ),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Type=", "l", "391a"]
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Animation Images",
                arg_type="1",
                arg_eval=", Animation Images=",
            ),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="Animation Tint", arg_type="1", arg_eval=", Animation Tint="
            ),
            ArgumentCode(
                arg_id="7", arg_required=True, arg_name="Frame Duration", arg_type="0", arg_eval=", Frame Duration="
            ),
            ArgumentCode(arg_id="8", arg_required=True, arg_name="Progress", arg_type="0", arg_eval=", Progress="),
            ArgumentCode(arg_id="9", arg_required=True, arg_name="Max", arg_type="0", arg_eval=", Max="),
            ArgumentCode(arg_id="10", arg_required=True, arg_name="Use HTML", arg_type="3", arg_eval="Use HTML"),
        ],
        name="Progress Dialog",
        category="55",
        canfail="True",
    ),
    "392t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Structure Type", arg_type="1", arg_eval=", Structure Type="
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Prevent JSON Smart Search",
                arg_type="3",
                arg_eval="Prevent JSON Smart Search",
            ),
        ],
        name="Set Variable Structure Type",
        category="120",
        canfail="True",
    ),
    "393t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Names", arg_type="1", arg_eval="Names="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Merge Type", arg_type="0", arg_eval=[", Title=", "l", "393"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Joiner", arg_type="1", arg_eval=", Joiner="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Format", arg_type="1", arg_eval=", Format="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Output", arg_type="1", arg_eval=", Output="),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="Join Output", arg_type="1", arg_eval=", Join Output="
            ),
        ],
        name="Arrays Merge",
        category="120",
        canfail="True",
    ),
    "394t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Input Type", arg_type="0", arg_eval=["Input Type=", "l", "394"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Input", arg_type="1", arg_eval=", Input="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Input Format", arg_type="1", arg_eval=", Input Format="
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Input Separator", arg_type="1", arg_eval=", Input Separator="
            ),
            ArgumentCode(
                arg_id="5", arg_required=False, arg_name="Output Format", arg_type="1", arg_eval=", Output Format="
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=False,
                arg_name="Output Format Separator",
                arg_type="1",
                arg_eval="Output Format Separator",
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=False,
                arg_name="Formatted Variable Names",
                arg_type="1",
                arg_eval=", Formatted Value Names=",
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Get All Details",
                arg_type="3",
                arg_eval=["e", ", Get All Details"],
            ),
            ArgumentCode(
                arg_id="9", arg_required=True, arg_name="Do Maths", arg_type="3", arg_eval=["e", ", Do Maths"]
            ),
            ArgumentCode(
                arg_id="10",
                arg_required=True,
                arg_name="Output Offset Type",
                arg_type="0",
                arg_eval=[", Output Offset Type=", "l", "394a"],
            ),
            ArgumentCode(
                arg_id="11", arg_required=True, arg_name="Output Offset", arg_type="1", arg_eval=", Output Offset="
            ),
            ArgumentCode(arg_id="12", arg_required=False, arg_name="Time Zone", arg_type="1", arg_eval=", Time Zone="),
        ],
        name="Parse/Format DateTime",
        category="120",
        canfail="True",
    ),
    "395t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="JD Status",
        category="130",
        canfail="False",
    ),
    "396t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "396"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Regex", arg_type="1", arg_eval=", Match Pattern/Regex="
            ),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Match Pattern", arg_type="1", arg_eval="Match Pattern"
            ),
        ],
        name="Simple Match/Regex",
        category="120",
        canfail="True",
    ),
    "397t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Output Hashtags",
                arg_type="3",
                arg_eval=["e", "Output Hashtags"],
            ),
        ],
        name="Get Material You Colors",
        category="104",
        canfail="True",
    ),
    "398t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="SSID", arg_type="1", arg_eval="SSID="),
        ],
        name="Connect To WiFi",
        category="80",
        canfail="True",
    ),
    "399t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Input", arg_type="1", arg_eval="Input="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Input Minimum", arg_type="1", arg_eval=", Input Minimum="
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Input Maximum", arg_type="1", arg_eval=", Input Maximum="
            ),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Output Minimum", arg_type="1", arg_eval=", Output Minimum="
            ),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Output Maximum", arg_type="1", arg_eval=", Output Maximum="
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Invert", arg_type="3", arg_eval="Invert"),
            ArgumentCode(
                arg_id="7", arg_required=True, arg_name="Restrict Range", arg_type="3", arg_eval=["e", ", Invert"]
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Max Rounding Digits",
                arg_type="0",
                arg_eval=["e", ", Restrict Range"],
            ),
            ArgumentCode(
                arg_id="9",
                arg_required=False,
                arg_name="Output Variable Name",
                arg_type="1",
                arg_eval=", Max Rounding Digits=",
            ),
        ],
        name="Variable Map",
        category="120",
        canfail="True",
    ),
    "39t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Variable", arg_type="1", arg_eval="Variable="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Items", arg_type="1", arg_eval=", Items="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Structure Output (JSON, etc)",
                arg_type="3",
                arg_eval=["e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="For",
        category="105",
        canfail="False",
    ),
    "3s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Address="),
        ],
        name="BT Connected",
        category="",
        canfail="",
    ),
    "400t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="From", arg_type="1", arg_eval="From="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To", arg_type="1", arg_eval=", To="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="Move",
        category="50",
        canfail="True",
    ),
    "402t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Get Clipboard",
        category="104",
        canfail="True",
    ),
    "404t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="From", arg_type="1", arg_eval="From="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To", arg_type="1", arg_eval=", To="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="Copy File",
        category="50",
        canfail="True",
    ),
    "405t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="From", arg_type="1", arg_eval="From="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To", arg_type="1", arg_eval=", To="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="Copy Dir",
        category="50",
        canfail="True",
    ),
    "406t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Shred Level", arg_type="0", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval="Use Root"),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="Delete File",
        category="50",
        canfail="True",
    ),
    "407t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Max Number", arg_type="1", arg_eval=",Max Number="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Mime Type", arg_type="1", arg_eval=", Mime Type="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Copy To Cache", arg_type="3", arg_eval=["e", ", Copy To Cache"]
            ),
        ],
        name="Pick Photos",
        category="55",
        canfail="True",
    ),
    "40830242s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval="Configuration="),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON (etc)"],
            ),
        ],
        name="AutoNotification Intercept",
        category="",
        canfail="",
    ),
    "408t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Directory", arg_type="1", arg_eval="Directory="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Recurse", arg_type="3", arg_eval=["e", ", Recurse"]),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="Delete Directory",
        category="50",
        canfail="True",
    ),
    "40966172t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast",
        category="",
        canfail="",
    ),
    "409t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Directory", arg_type="1", arg_eval="Directory="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Create All", arg_type="3", arg_eval=["e", ", Create All"]
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="Create Directory",
        category="50",
        canfail="True",
    ),
    "40s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval="Type="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Number="),
        ],
        name="Call",
        category="",
        canfail="",
    ),
    "40t": ActionCode(
        redirect="",
        args=[],
        name="End For",
        category="105",
        canfail="False",
    ),
    "410t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Append", arg_type="3", arg_eval=["e", ", Append"]),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Add Newline", arg_type="3", arg_eval=["e", ", Add New Line"]
            ),
        ],
        name="Write File",
        category="50",
        canfail="True",
    ),
    "411e": ActionCode(
        redirect="",
        args=[],
        name="Device Boot",
        category="",
        canfail="",
    ),
    "412t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Directory", arg_type="1", arg_eval="Directory="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Match", arg_type="1", arg_eval=", Match="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Include Hidden Files",
                arg_type="3",
                arg_eval=["e", ", Include Hidden Files"],
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval=["e", ", Use Root"]
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Sort Select",
                arg_type="0",
                arg_eval=[", Sort Selection=", "l", "412"],
            ),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Variable Array", arg_type="1", arg_eval=", Variable Array="
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="List Files",
        category="50",
        canfail="True",
    ),
    "413e": ActionCode(
        redirect="",
        args=[],
        name="Device Shutdown",
        category="",
        canfail="",
    ),
    "413t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Tile To Add", arg_type="1", arg_eval="Tile To Add="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Icon", arg_type="1", arg_eval="Icon="),
        ],
        name="Request Add Tile",
        category="55",
        canfail="True",
    ),
    "414549629t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Search",
        category="",
        canfail="",
    ),
    "414t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Image", arg_type="1", arg_eval="Image="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Pixel Coordinates",
                arg_type="1",
                arg_eval=", Pixel Coordinates=",
            ),
        ],
        name="Get Pixel Colors",
        category="52",
        canfail="True",
    ),
    "415t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File"),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Line", arg_type="1", arg_eval="Line"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="To Var", arg_type="1", arg_eval="To Var"),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Structure Output (JSON, etc)",
                arg_type="3",
                arg_eval="Structure Output (JSON, etc)",
            ),
        ],
        name="Read Line",
        category="50",
        canfail="True",
    ),
    "41628340e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="5",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoVoice Intercept",
        category="",
        canfail="",
    ),
    "416t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Para", arg_type="1", arg_eval=", Para="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="To Var", arg_type="1", arg_eval=", To Var="),
        ],
        name="Read Paragraph",
        category="50",
        canfail="True",
    ),
    "417t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To Var", arg_type="1", arg_eval=", To Var="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Structure Output (JSON, etc)",
                arg_type="3",
                arg_eval=["e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="Read File",
        category="50",
        canfail="True",
    ),
    "418t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Event ID", arg_type="1", arg_eval=", Calendar"),
            ArgumentCode(
                arg_id="2", arg_required=False, arg_name="Number Of Events", arg_type="1", arg_eval=", Start Time"
            ),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Calendar", arg_type="1", arg_eval=", End Time"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Start Time", arg_type="1", arg_eval=""),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="End Time", arg_type="1", arg_eval=""),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Title", arg_type="1", arg_eval=""),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Description", arg_type="1", arg_eval=""),
        ],
        name="Get Calendar Events",
        category="142",
        canfail="True",
    ),
    "41t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Number", arg_type="1", arg_eval="Number="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Message", arg_type="1", arg_eval=", Message="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Store In Messaging App",
                arg_type="3",
                arg_eval="Store In Messaging App",
            ),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="SIM Card", arg_type="1", arg_eval=", SIM Card="),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Wait For Result",
                arg_type="3",
                arg_eval=["e", ", Wait For Result"],
            ),
        ],
        name="Send SMS",
        category="90",
        canfail="True",
    ),
    "420t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Delete Orig", arg_type="3", arg_eval=["e", ", Delete Dialog"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Level", arg_type="0", arg_eval=", Level="),
            ArgumentCode(
                arg_id="3", arg_required=False, arg_name="Output File", arg_type="1", arg_eval=", Output File="
            ),
        ],
        name="Zip",
        category="50",
        canfail="True",
    ),
    "421t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Get Screen Info (Assistant)",
        category="40",
        canfail="True",
    ),
    "422e": ActionCode(
        redirect="",
        args=[],
        name="Device Storage Low",
        category="",
        canfail="",
    ),
    "422t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Delete Zip", arg_type="3", arg_eval=["e", ", Delete Zip"]
            ),
        ],
        name="UnZip",
        category="50",
        canfail="True",
    ),
    "424867932t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoBubbles Manage Bubble",
        category="",
        canfail="",
    ),
    "424e": ActionCode(
        redirect="",
        args=[],
        name="Screebl / TSC",
        category="",
        canfail="",
    ),
    "424t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Get Battery Info",
        category="104",
        canfail="True",
    ),
    "425e": ActionCode(
        redirect="",
        args=[],
        name="K9 Email Received",
        category="",
        canfail="",
    ),
    "425t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="WiFi",
        category="80",
        canfail="True",
    ),
    "426e": ActionCode(
        redirect="",
        args=[],
        name="Widget Locker",
        category="",
        canfail="",
    ),
    "426t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Action", arg_type="0", arg_eval=["Action=", "l", "426"]
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Force", arg_type="3", arg_eval=["e", ", Force"]),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Report Failure",
                arg_type="3",
                arg_eval=["e", ", Report Failure"],
            ),
        ],
        name="WiFi Net",
        category="80",
        canfail="False",
    ),
    "427019141t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Replace Gmail Notifications",
        category="",
        canfail="",
    ),
    "427e": ActionCode(
        redirect="",
        args=[],
        name="OpenWatch",
        category="",
        canfail="",
    ),
    "427t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Policy", arg_type="0", arg_eval=["Policy=", "l", "427"]
            ),
        ],
        name="WiFi Sleep",
        category="80",
        canfail="False",
    ),
    "428e": ActionCode(
        redirect="",
        args=[],
        name="Kaloer Clock",
        category="",
        canfail="",
    ),
    "429032033t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoContacts Details",
        category="",
        canfail="",
    ),
    "42924197t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Notification Listener",
        category="",
        canfail="",
    ),
    "429e": ActionCode(
        redirect="",
        args=[],
        name="Locale Changed",
        category="",
        canfail="",
    ),
    "42t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Number", arg_type="1", arg_eval="Number="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Port", arg_type="0", arg_eval=", Port="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Data", arg_type="1", arg_eval=", Data="),
        ],
        name="Send Data SMS",
        category="90",
        canfail="True",
    ),
    "430t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0",
                arg_required=True,
                arg_name="Output Variables",
                arg_type="5",
                arg_eval=["e", ", Only Monitor"],
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Only Monitor", arg_type="3", arg_eval="Only Monitor"),
        ],
        name="Restart Tasker",
        category="110",
        canfail="False",
    ),
    "431t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Action", arg_type="0", arg_eval=["Action=", "l", "431"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Services", arg_type="1", arg_eval=", Services"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Services", arg_type="1", arg_eval="Services"),
        ],
        name="Accessibility Services",
        category="104",
        canfail="True",
    ),
    "432t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Get Network Info",
        category="80",
        canfail="True",
    ),
    "433t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Mobile Data",
        category="80",
        canfail="True",
    ),
    "438t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Device IDs/Names", arg_type="1", arg_eval="Device IDs/Name="
            ),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Set", arg_type="1", arg_eval=", Set="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Colour", arg_type="1", arg_eval=", Color="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Brightness", arg_type="1", arg_eval=", Brightness="),
        ],
        name="Matter Light (Experimental)",
        category="141",
        canfail="True",
    ),
    "439t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="WiMax",
        category="80",
        canfail="False",
    ),
    "43t": ActionCode(
        redirect="",
        args=[],
        name="Else",
        category="105",
        canfail="False",
    ),
    "440t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="To", arg_type="1", arg_eval="To"),
        ],
        name="Set Timezone",
        category="104",
        canfail="False",
    ),
    "441t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Work Profile",
        category="104",
        canfail="True",
    ),
    "442t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Punch", arg_type="0", arg_eval="Punch"),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Note", arg_type="1", arg_eval="Note"),
        ],
        name="SleepBot",
        category="130",
        canfail="False",
    ),
    "443t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval=["Cmd=", "l", "443"]),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Simulate Media Button",
                arg_type="3",
                arg_eval=["e", ", Simulate Media Button"],
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Package/App Name", arg_type="2", arg_eval=", Package/App Name="
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Use Notification If Available",
                arg_type="3",
                arg_eval=["e", ", Use Notification If Available"],
            ),
        ],
        name="Media Control",
        category="65",
        canfail="False",
    ),
    "444e": ActionCode(
        redirect="",
        args=[],
        name="Pomodroido",
        category="",
        canfail="",
    ),
    "444t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="0", arg_eval="Set"),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Strobe (Hertz)", arg_type="0", arg_eval="Strobe (Hertz)"
            ),
        ],
        name="TeslaLED",
        category="130",
        canfail="False",
    ),
    "445e": ActionCode(
        redirect="",
        args=[],
        name="Radardroid",
        category="",
        canfail="",
    ),
    "445t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Start", arg_type="0", arg_eval=", Start="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Loop", arg_type="3", arg_eval=["e", ", Loop"]),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Stream", arg_type="0", arg_eval=["Cmd=", "l", "171"]),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
        ],
        name="Music Play",
        category="65",
        canfail="True",
    ),
    "446e": ActionCode(
        redirect="",
        args=[],
        name="Gentle Alarm",
        category="",
        canfail="",
    ),
    "446t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Path", arg_type="1", arg_eval="Path="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Type", arg_type="1", arg_eval=", Type="),
            ArgumentCode(
                arg_id="3",
                arg_required=False,
                arg_name="Name/Path Filter",
                arg_type="1",
                arg_eval=", Name/Path Filter=",
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Other Filters", arg_type="1", arg_eval=", Other Filters="
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Recurse", arg_type="3", arg_eval=["e", ", Recurse"]),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Sort", arg_type="1", arg_eval="Sort"),
        ],
        name="Get Files/Folders Properties",
        category="50",
        canfail="True",
    ),
    "447e": ActionCode(
        redirect="",
        args=[],
        name="Reddit Notify",
        category="",
        canfail="",
    ),
    "447t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Directory", arg_type="1", arg_eval="Directory="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Subdirs", arg_type="3", arg_eval=["e", ", Subdirs"]),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Audio Only", arg_type="3", arg_eval=["e", ", Audio Only"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Random", arg_type="3", arg_eval=["e", ", Random"]),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Flash", arg_type="3", arg_eval=["e", ", Flash"]),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Maximum Tracks", arg_type="0", arg_eval=", Maximum Tracks="
            ),
        ],
        name="Music Play Dir",
        category="65",
        canfail="True",
    ),
    "448e": ActionCode(
        redirect="",
        args=[],
        name="Notify My Android",
        category="",
        canfail="",
    ),
    "448t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Names", arg_type="1", arg_eval="Names="),
        ],
        name="Array Compare",
        category="120",
        canfail="False",
    ),
    "449t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Clear Dir", arg_type="3", arg_eval=["e", ", Clear Dir"]
            ),
        ],
        name="Music Stop",
        category="65",
        canfail="True",
    ),
    "450e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval=",Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Package="),
        ],
        name="New Package",
        category="",
        canfail="",
    ),
    "450t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Enable", arg_type="3", arg_eval="Enable"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Keep MMS", arg_type="3", arg_eval="Keep MMS"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Notify", arg_type="3", arg_eval="Notify"),
        ],
        name="APN Droid",
        category="130",
        canfail="False",
    ),
    "451e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Package="),
        ],
        name="Package Removed",
        category="",
        canfail="",
    ),
    "451t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Jump", arg_type="0", arg_eval="Jump="),
        ],
        name="Music Skip",
        category="65",
        canfail="True",
    ),
    "452t": ActionCode(
        redirect="",
        args=[],
        name="Show Running Tasks",
        category="110",
        canfail="False",
    ),
    "453e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Package="),
        ],
        name="Package Updated",
        category="",
        canfail="",
    ),
    "453t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Jump", arg_type="0", arg_eval="Jump="),
        ],
        name="Music Back",
        category="65",
        canfail="True",
    ),
    "454t": ActionCode(
        redirect="",
        args=[],
        name="Show Active Profiles",
        category="110",
        canfail="False",
    ),
    "455t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Source", arg_type="0", arg_eval=[", Source=", "l", "455"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="MaxSize", arg_type="0", arg_eval=", MaxSize="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Codec", arg_type="0", arg_eval=[", Format=", "l", "455a"]
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Format", arg_type="0", arg_eval="Format"),
        ],
        name="Record Audio",
        category="65",
        canfail="True",
    ),
    "456t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="0", arg_eval="Set"),
        ],
        name="JD APN",
        category="130",
        canfail="False",
    ),
    "457t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval="Type"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Sound", arg_type="1", arg_eval="Sound"),
        ],
        name="Default Ringtone",
        category="20",
        canfail="False",
    ),
    "458t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval="Cmd"),
        ],
        name="WidgetLocker",
        category="130",
        canfail="False",
    ),
    "459t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="File", arg_type="1", arg_eval="File="),
        ],
        name="Scan Media",
        category="65",
        canfail="False",
    ),
    "460e": ActionCode(
        redirect="",
        args=[],
        name="Wallpaper Changed",
        category="",
        canfail="",
    ),
    "460t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Grayscale", arg_type="3", arg_eval=["e", ", 'Grayscale' On"]
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Dim Wallpaper",
                arg_type="3",
                arg_eval=["e", ", 'Wallpaper' On"],
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Disable Always On Display",
                arg_type="3",
                arg_eval=["e", ", 'Disable Always On Display' On"],
            ),
        ],
        name="Set Device Effects",
        category="104",
        canfail="True",
    ),
    "461e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="2", arg_eval="Owner Application="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", Subtext="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Messages="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Other Text="),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="", arg_type="1", arg_eval=", Cat="),
            ArgumentCode(arg_id="7", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", New Only"]),
        ],
        name="Notification",
        category="",
        canfail="",
    ),
    "461t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Widget Name", arg_type="1", arg_eval="Widget Name="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Layout", arg_type="1", arg_eval=", Layout="),
            ArgumentCode(
                arg_id="3",
                arg_required=False,
                arg_name="Background Colour",
                arg_type="1",
                arg_eval=", Background Color=",
            ),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Texts", arg_type="1", arg_eval=", Texts="),
            ArgumentCode(
                arg_id="6", arg_required=False, arg_name="Text Styles", arg_type="1", arg_eval=", Text Styles="
            ),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Images", arg_type="1", arg_eval=", Images="),
            ArgumentCode(
                arg_id="8", arg_required=False, arg_name="Image Tints", arg_type="1", arg_eval=", Image Tint="
            ),
            ArgumentCode(
                arg_id="9", arg_required=False, arg_name="Image Sizes", arg_type="1", arg_eval=", Image Sizes="
            ),
            ArgumentCode(arg_id="10", arg_required=False, arg_name="Tasks", arg_type="1", arg_eval=", Tasks="),
            ArgumentCode(arg_id="11", arg_required=False, arg_name="Commands", arg_type="1", arg_eval=", Commands="),
            ArgumentCode(
                arg_id="12", arg_required=False, arg_name="Command Prefix", arg_type="1", arg_eval=", Command Prefix="
            ),
            ArgumentCode(
                arg_id="13", arg_required=False, arg_name="Custom Layout", arg_type="1", arg_eval=", Command Layout="
            ),
            ArgumentCode(
                arg_id="14",
                arg_required=True,
                arg_name="Material You Colors",
                arg_type="3",
                arg_eval=["e", ", Material You Colors"],
            ),
            ArgumentCode(
                arg_id="15",
                arg_required=True,
                arg_name="Number of Columns",
                arg_type="1",
                arg_eval=", Number of Columns=",
            ),
            ArgumentCode(
                arg_id="16",
                arg_required=True,
                arg_name="Ask To Add If Not Present",
                arg_type="3",
                arg_eval="Ask To Add If Not Present",
            ),
        ],
        name="Widget v2",
        category="110",
        canfail="True",
    ),
    "462e": ActionCode(
        redirect="",
        args=[],
        name="Button Widget Clicked",
        category="",
        canfail="",
    ),
    "462t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "462"]),
        ],
        name="Remote Action Execution",
        category="110",
        canfail="True",
    ),
    "463e": ActionCode(
        redirect="",
        args=[],
        name="New Window",
        category="",
        canfail="",
    ),
    "463t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=", Continue Task Immediately",
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Action", arg_type="1", arg_eval=", Action"),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Event ID", arg_type="1", arg_eval=", Event ID"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Title", arg_type="1", arg_eval=", Title"),
            ArgumentCode(
                arg_id="5", arg_required=False, arg_name="Description", arg_type="1", arg_eval=", Description"
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Start Time", arg_type="1", arg_eval=", Start Time"),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="End Time", arg_type="1", arg_eval=", End Time"),
        ],
        name="Edit Calendar Via App",
        category="142",
        canfail="True",
    ),
    "464e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="2", arg_eval="Owner Application="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", Subtext="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Messages="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Other Text="),
        ],
        name="Notification Removal",
        category="",
        canfail="",
    ),
    "464t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Action", arg_type="1", arg_eval=", Calendar"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Calendar", arg_type="1", arg_eval=", Action"),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Event ID", arg_type="1", arg_eval=", Event ID"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Title", arg_type="1", arg_eval=", Title"),
            ArgumentCode(
                arg_id="5", arg_required=False, arg_name="Description", arg_type="1", arg_eval=", Description"
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="All Day", arg_type="1", arg_eval=", All Day"),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Start Time", arg_type="1", arg_eval=", Start Time"),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="End Time", arg_type="1", arg_eval=", End Time"),
            ArgumentCode(arg_id="9", arg_required=False, arg_name="Organizer", arg_type="1", arg_eval=", Organizer"),
            ArgumentCode(arg_id="10", arg_required=False, arg_name="Location", arg_type="1", arg_eval=", Location"),
            ArgumentCode(
                arg_id="11", arg_required=False, arg_name="Availability", arg_type="1", arg_eval=", Availability"
            ),
            ArgumentCode(arg_id="12", arg_required=False, arg_name="Colour", arg_type="1", arg_eval=""),
        ],
        name="Edit Calendar Event",
        category="142",
        canfail="True",
    ),
    "465t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Action", arg_type="1", arg_eval=", Action"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Event ID", arg_type="1", arg_eval=", Event ID"),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Reminder ID", arg_type="1", arg_eval=", Reminder ID"),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Minutes Prior", arg_type="1", arg_eval=", Minutes Prior"
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Method", arg_type="1", arg_eval=", Method"),
        ],
        name="Edit Calendar Reminder",
        category="142",
        canfail="True",
    ),
    "466t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Reminder ID", arg_type="1", arg_eval=", Calendar"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Event ID", arg_type="1", arg_eval=", Event ID"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Calendar", arg_type="1", arg_eval=", Reminder ID"),
        ],
        name="Get Calendar Reminders",
        category="142",
        canfail="True",
    ),
    "467t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Action", arg_type="1", arg_eval=", Action"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Event ID", arg_type="1", arg_eval=", Event ID"),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Attendee ID", arg_type="1", arg_eval=", Attendee ID"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Name", arg_type="1", arg_eval=", Name"),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Email", arg_type="1", arg_eval=", Email"),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Status", arg_type="1", arg_eval=", Status"),
            ArgumentCode(
                arg_id="7", arg_required=False, arg_name="Relationship", arg_type="1", arg_eval=", Relationship"
            ),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Type", arg_type="1", arg_eval=", Type"),
        ],
        name="Edit Calendar Attendee",
        category="142",
        canfail="True",
    ),
    "468t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Attendee ID", arg_type="1", arg_eval=", Calendar"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Event ID", arg_type="1", arg_eval=", Event ID"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Calendar", arg_type="1", arg_eval=", Attendee ID"),
        ],
        name="Get Calendar Attendees",
        category="142",
        canfail="True",
    ),
    "469t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Keyboard", arg_type="1", arg_eval=", Keyboard"),
        ],
        name="Set Keyboard",
        category="104",
        canfail="True",
    ),
    "46t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
        ],
        name="Create Scene",
        category="102",
        canfail="True",
    ),
    "470t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
        ],
        name="Get Keyboard Info",
        category="104",
        canfail="True",
    ),
    "473t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval=", Output Variables"
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Latitude", arg_type="1", arg_eval=", Latitude"),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Longitude", arg_type="1", arg_eval=", Longitude"),
        ],
        name="Get Sunrise/Sunset Times",
        category="60",
        canfail="True",
    ),
    "475t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Delete Orig", arg_type="3", arg_eval=["e", ", Delete Orig"]
            ),
        ],
        name="GZip",
        category="50",
        canfail="True",
    ),
    "476t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Delete Zip", arg_type="3", arg_eval=["e", ", Delete Zip"]
            ),
        ],
        name="GUnzip",
        category="50",
        canfail="True",
    ),
    "47t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Display As",
                arg_type="0",
                arg_eval=[", Display As=", "l", "47"],
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Horizontal Position",
                arg_type="0",
                arg_eval="Horizontal Position",
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Vertical Position", arg_type="0", arg_eval="Vertical Position"
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Animation", arg_type="0", arg_eval="Animation"),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Show Exit Button", arg_type="3", arg_eval="Show Exit Button"
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Show Over Keyguard",
                arg_type="3",
                arg_eval=["e", ", Show Exit Button"],
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Allow Outside Boundaries",
                arg_type="3",
                arg_eval=["e", ", Allow Outside Boundaries"],
            ),
            ArgumentCode(
                arg_id="9",
                arg_required=True,
                arg_name="Blocking Overlay +",
                arg_type="3",
                arg_eval=["e", ", Blocking Overlay +"],
            ),
            ArgumentCode(arg_id="10", arg_required=True, arg_name="Overlay +", arg_type="3", arg_eval="Overlay +"),
        ],
        name="Show Scene",
        category="102",
        canfail="True",
    ),
    "48t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Animation", arg_type="0", arg_eval=["Animation=", "l", "48"]
            ),
        ],
        name="Hide Scene",
        category="102",
        canfail="True",
    ),
    "490t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Action", arg_type="0", arg_eval=["File=", "l", "490"]
            ),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Use New API", arg_type="3", arg_eval=["e", ", Use New API"]
            ),
        ],
        name="Media Button Events",
        category="65",
        canfail="False",
    ),
    "49t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
        ],
        name="Destroy Scene",
        category="102",
        canfail="True",
    ),
    "4e": ActionCode(
        redirect="",
        args=[],
        name="Phone Idle",
        category="",
        canfail="",
    ),
    "4s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval="Address"),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=["Major Device Class=", "l", "4"]
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["e", ", Standard Devices"]
            ),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=["e", ", Low Energy (LE) Devices"]
            ),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="", arg_type="0", arg_eval=["e", ", Unpaired Devices"]
            ),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="", arg_type="0", arg_eval=["e", ", Toggle Bluetooth"]
            ),
        ],
        name="BT Near",
        category="",
        canfail="",
    ),
    "502102143t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Get Spreadsheet",
        category="",
        canfail="",
    ),
    "502807688t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoAppsHub SendCommand",
        category="",
        canfail="",
    ),
    "50s": ActionCode(
        redirect="",
        args=[],
        name="Keyboard Out",
        category="",
        canfail="",
    ),
    "50t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element Match", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Value", arg_type="0", arg_eval=", Value="),
        ],
        name="Element Value",
        category="102",
        canfail="True",
    ),
    "511t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=[", File=", "l", "switch_set"]
            ),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Level", arg_type="1", arg_eval="Level"),
        ],
        name="Torch",
        category="10",
        canfail="False",
    ),
    "512t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="0", arg_eval=[", File=", "l", "512"]),
        ],
        name="Status Bar",
        category="40",
        canfail="True",
    ),
    "513t": ActionCode(
        redirect="",
        args=[],
        name="Close System Dialogs",
        category="55",
        canfail="True",
    ),
    "51t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Position", arg_type="0", arg_eval=[", Position=", "l", "51"]
            ),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Selection", arg_type="1", arg_eval=", Selection="),
        ],
        name="Element Text",
        category="102",
        canfail="True",
    ),
    "523t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Icon", arg_type="4", arg_eval=", Icon="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Number", arg_type="0", arg_eval="Number"),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Permanent", arg_type="3", arg_eval=["e", ", Permanent"]
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Priority", arg_type="0", arg_eval=", Priority="),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="Repeat Alert", arg_type="3", arg_eval=["e", ", Repeat Alert"]
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="LED Colour",
                arg_type="0",
                arg_eval=[", LED Color=", "l", "523"],
            ),
            ArgumentCode(arg_id="8", arg_required=True, arg_name="LED Rate", arg_type="0", arg_eval=", LED Rate="),
            ArgumentCode(arg_id="9", arg_required=False, arg_name="Sound File", arg_type="1", arg_eval=", Sound File="),
            ArgumentCode(
                arg_id="10",
                arg_required=False,
                arg_name="Vibration Pattern",
                arg_type="1",
                arg_eval=", Vibration Pattern=",
            ),
            ArgumentCode(arg_id="11", arg_required=False, arg_name="Category", arg_type="1", arg_eval=", Category="),
            ArgumentCode(
                arg_id="12",
                arg_required=False,
                arg_name="Intensity Pattern",
                arg_type="1",
                arg_eval=", Intensity Pattern=",
            ),
        ],
        name="Notify",
        category="10",
        canfail="False",
    ),
    "525t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Title", arg_type="1", arg_eval=":Title="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Icon", arg_type="4", arg_eval=", Icon="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Number", arg_type="0", arg_eval=""),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Colour", arg_type="0", arg_eval=[", LED Color=", "l", "523"]
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Rate", arg_type="0", arg_eval=", Rate="),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Priority", arg_type="0", arg_eval=", Priority="),
            ArgumentCode(
                arg_id="7", arg_required=True, arg_name="Repeat Alert", arg_type="3", arg_eval=["e", ", Repeat Alert"]
            ),
        ],
        name="Notify LED",
        category="10",
        canfail="False",
    ),
    "536t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Icon", arg_type="4", arg_eval=", Icon="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Number", arg_type="0", arg_eval="Number"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Pattern", arg_type="1", arg_eval=", Pattern="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Priority", arg_type="0", arg_eval=", Priority="),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="Repeat Alert", arg_type="3", arg_eval=["e", ", Repeat Alert"]
            ),
        ],
        name="Notify Vibrate",
        category="10",
        canfail="False",
    ),
    "538t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Icon", arg_type="4", arg_eval=", Icon="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Number", arg_type="0", arg_eval="Number"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Sound File", arg_type="1", arg_eval=", Sound File="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Priority", arg_type="0", arg_eval=", Priority="),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Repeat Alert", arg_type="3", arg_eval="Repeat Alert"),
        ],
        name="Notify Sound",
        category="10",
        canfail="False",
    ),
    "53t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=[", Mode=", "l", "53"]),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Value", arg_type="1", arg_eval="Value"),
        ],
        name="Element Web Control",
        category="102",
        canfail="True",
    ),
    "543t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Seconds", arg_type="0", arg_eval="Seconds="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Message", arg_type="1", arg_eval=", Message="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Show UI", arg_type="3", arg_eval=["e", ", Show UI"]),
        ],
        name="Start System Timer",
        category="104",
        canfail="False",
    ),
    "544t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Type=", "l", "544"]
            ),
        ],
        name="Timer Widget Control",
        category="110",
        canfail="False",
    ),
    "545t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Min", arg_type="0", arg_eval=", Min="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Max", arg_type="0", arg_eval=", Max="),
        ],
        name="Variable Randomize",
        category="120",
        canfail="False",
    ),
    "546t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Seconds", arg_type="0", arg_eval=", Seconds="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Minutes", arg_type="0", arg_eval=", Minutes="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Hours", arg_type="0", arg_eval=", Hours="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Days", arg_type="0", arg_eval=", Days="),
        ],
        name="Timer Widget Set",
        category="110",
        canfail="False",
    ),
    "547t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To", arg_type="1", arg_eval=", To="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Recurse Variables",
                arg_type="3",
                arg_eval=["e", ", Recursive Variables"],
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Do Maths", arg_type="3", arg_eval=["e", ", Do Maths"]
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Append", arg_type="3", arg_eval=["e", ", Append"]),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Max Rounding Digits",
                arg_type="0",
                arg_eval=", Max Rounding Digits=",
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Structure Output (JSON, etc)",
                arg_type="3",
                arg_eval=["e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="Variable Set",
        category="120",
        canfail="True",
    ),
    "548t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Text", arg_type="1", arg_eval="Text="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Long", arg_type="3", arg_eval=["e", ", Long"]),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Tasker Layout", arg_type="3", arg_eval=["e", ", Tasker Layout"]
            ),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Icon", arg_type="1", arg_eval=", Icon="),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Icon Size", arg_type="1", arg_eval=" Icon Size="),
            ArgumentCode(
                arg_id="6",
                arg_required=False,
                arg_name="Background Colour",
                arg_type="1",
                arg_eval=", Background Color=",
            ),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Timeout", arg_type="1", arg_eval=", Timeout="),
            ArgumentCode(
                arg_id="9",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
            ArgumentCode(
                arg_id="10", arg_required=False, arg_name="Text Colour", arg_type="1", arg_eval=", Text Color="
            ),
            ArgumentCode(
                arg_id="11",
                arg_required=True,
                arg_name="Dismiss On Click",
                arg_type="3",
                arg_eval=["e", ", Dismiss On Click"],
            ),
            ArgumentCode(
                arg_id="12",
                arg_required=True,
                arg_name="Show Over Everything",
                arg_type="3",
                arg_eval=["e", ", Show Over Everything"],
            ),
            ArgumentCode(arg_id="13", arg_required=False, arg_name="Position", arg_type="1", arg_eval=", Position="),
            ArgumentCode(
                arg_id="14", arg_required=True, arg_name="Use HTML", arg_type="3", arg_eval=["e", ", Use HTML"]
            ),
            ArgumentCode(arg_id="15", arg_required=False, arg_name="ID", arg_type="1", arg_eval="ID"),
        ],
        name="Flash",
        category="10",
        canfail="True",
    ),
    "549t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Pattern Matching",
                arg_type="3",
                arg_eval=["e", ", Pattern Matching"],
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Local Variables Only",
                arg_type="3",
                arg_eval=["e", ", Clear All Variables"],
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Clear All Variables",
                arg_type="3",
                arg_eval="Clear All Variables",
            ),
        ],
        name="Variable Clear",
        category="120",
        canfail="False",
    ),
    "54t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Colour", arg_type="1", arg_eval=" Colour="),
        ],
        name="Element Text Colour",
        category="102",
        canfail="True",
    ),
    "550t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Text", arg_type="1", arg_eval=", Text="),
            ArgumentCode(
                arg_id="2",
                arg_required=False,
                arg_name="Background Image",
                arg_type="1",
                arg_eval=", Background Image=",
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Layout", arg_type="1", arg_eval="Layout"),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Layout="
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Show Over Keyguard",
                arg_type="3",
                arg_eval=", Timeout (Seconds)=",
            ),
        ],
        name="Popup",
        category="10",
        canfail="False",
    ),
    "551t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title"),
            ArgumentCode(
                arg_id="1", arg_required=False, arg_name="Background Image", arg_type="1", arg_eval="Background Image"
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Layout", arg_type="1", arg_eval="Layout"),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval="Timeout (Seconds)"
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Show Over Keyguard",
                arg_type="3",
                arg_eval="Show Over Keyguard",
            ),
        ],
        name="Menu",
        category="10",
        canfail="False",
    ),
    "552t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Text", arg_type="1", arg_eval="Text="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=[", Mode=", "l", "552"]
            ),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Task", arg_type="1", arg_eval=", Task="),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Background Image",
                arg_type="1",
                arg_eval=", Background Image=",
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Layout", arg_type="1", arg_eval=", Layout="),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Timeout (Seconds)",
                arg_type="0",
                arg_eval=", Timeout (Seconds)=",
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="Show Over Keyguard",
                arg_type="3",
                arg_eval=["e", ", Show Over Keyguard"],
            ),
        ],
        name="Popup Task Buttons",
        category="10",
        canfail="False",
    ),
    "553t": ActionCode(
        redirect="",
        args=[],
        name="SMS Backup+",
        category="130",
        canfail="False",
    ),
    "555t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval="Cmd"),
        ],
        name="BeyondPod",
        category="130",
        canfail="False",
    ),
    "556t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval="Cmd"),
        ],
        name="GrazeRSS",
        category="130",
        canfail="False",
    ),
    "557649458t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Time",
        category="",
        canfail="",
    ),
    "558t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Title", arg_type="1", arg_eval="Title"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Message", arg_type="1", arg_eval="Message"),
        ],
        name="Android Notifier",
        category="130",
        canfail="False",
    ),
    "559t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Text", arg_type="1", arg_eval="Text="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Engine:Voice", arg_type="1", arg_eval=", Engine Voice="
            ),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Stream", arg_type="0", arg_eval=[", Stream=", "l", "171"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Pitch", arg_type="0", arg_eval=", Pitch="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Speed", arg_type="0", arg_eval=", Speed="),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Respect Audio Focus",
                arg_type="3",
                arg_eval=["e", ", Respect Audio Focus"],
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="Network", arg_type="3", arg_eval=["e", ", Network"]),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
        ],
        name="Say",
        category="10",
        canfail="True",
    ),
    "55t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Colour", arg_type="1", arg_eval=" Colour="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="End Colour", arg_type="1", arg_eval=" End Colour="),
        ],
        name="Element Back Colour",
        category="102",
        canfail="True",
    ),
    "563213414t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Table",
        category="",
        canfail="",
    ),
    "565385068t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Query",
        category="",
        canfail="",
    ),
    "566t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Hours", arg_type="0", arg_eval="Hours="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Minutes", arg_type="0", arg_eval=", Minutes="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Label", arg_type="1", arg_eval=", Label="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Sound", arg_type="1", arg_eval=", Sound="),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Vibrate", arg_type="0", arg_eval=[", Vibrate=", "l", "566"]
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Confirm", arg_type="3", arg_eval=["e", ", Confirm"]),
        ],
        name="Set Alarm",
        category="104",
        canfail="False",
    ),
    "567t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=False, arg_name="In / For (Minutes)", arg_type="1", arg_eval="In/For Minutes="
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Calendar", arg_type="1", arg_eval=", Calendar="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Title", arg_type="1", arg_eval=", Title="),
            ArgumentCode(
                arg_id="3", arg_required=False, arg_name="Description", arg_type="1", arg_eval=", Description="
            ),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Location", arg_type="1", arg_eval=", Location="),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Available", arg_type="3", arg_eval=["e", ", Available"]
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="All Day", arg_type="3", arg_eval=["e", ", All Day"]),
        ],
        name="Calendar Insert",
        category="142",
        canfail="True",
    ),
    "5683503e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval=""),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoInput UI Action",
        category="",
        canfail="",
    ),
    "568t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval="Cmd"),
        ],
        name="DailyRoads Voyager",
        category="130",
        canfail="False",
    ),
    "56t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Width", arg_type="0", arg_eval=", Width="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Colour", arg_type="1", arg_eval=", Colour="),
        ],
        name="Element Border",
        category="102",
        canfail="True",
    ),
    "570237327t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Format Cells",
        category="",
        canfail="",
    ),
    "57t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Orientation",
                arg_type="0",
                arg_eval=[", Orientation=", "l", "57"],
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="X", arg_type="0", arg_eval=", X="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Y", arg_type="0", arg_eval=", Y="),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Animation Time (MS)",
                arg_type="0",
                arg_eval=", Animation Time (MS)=",
            ),
        ],
        name="Element Position",
        category="102",
        canfail="True",
    ),
    "580953799e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="5",
                arg_eval=["", "e", ", Structure Output (JSON, etc)"],
            ),
        ],
        name="AutoShare",
        category="",
        canfail="",
    ),
    "58t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Orientation",
                arg_type="0",
                arg_eval=[", Orientation=", "l", "57"],
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Width", arg_type="0", arg_eval=", Width="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Height", arg_type="0", arg_eval=", Height="),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="Animation Time (MS)",
                arg_type="0",
                arg_eval=", Animation Time (MS)=",
            ),
        ],
        name="Element Size",
        category="102",
        canfail="True",
    ),
    "590t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Splitter", arg_type="1", arg_eval=", Splitter="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Delete Base", arg_type="3", arg_eval=["e", ", Delete Base"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Regex", arg_type="3", arg_eval=["e", ", Regex"]),
        ],
        name="Variable Split",
        category="120",
        canfail="True",
    ),
    "592t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Joiner", arg_type="1", arg_eval=", Joiner="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Delete Parts", arg_type="3", arg_eval=["e", ", Delete Parts"]
            ),
        ],
        name="Variable Join",
        category="120",
        canfail="False",
    ),
    "595t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Variable", arg_type="1", arg_eval=", Variable="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Input Type",
                arg_type="0",
                arg_eval=[", Input Type=", "l", "595"],
            ),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Default", arg_type="1", arg_eval=", Default="),
            ArgumentCode(
                arg_id="4",
                arg_required=False,
                arg_name="Background Image",
                arg_type="1",
                arg_eval=", Background Image=",
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Layout", arg_type="1", arg_eval=", Layout="),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Timeout (Seconds)",
                arg_type="0",
                arg_eval=", Timeout (Seconds)=",
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="Show Over Keyguard",
                arg_type="3",
                arg_eval=["e", ", Show Over Keyguard"],
            ),
        ],
        name="Variable Query",
        category="120",
        canfail="False",
    ),
    "596t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Function", arg_type="0", arg_eval=[", Function=", "l", "596"]
            ),
            ArgumentCode(
                arg_id="2", arg_required=False, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Mode", arg_type="0", arg_eval="Mode"),
        ],
        name="Variable Convert",
        category="120",
        canfail="True",
    ),
    "597t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="From", arg_type="0", arg_eval=", From="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Length", arg_type="0", arg_eval=", Length="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Adapt To Fit", arg_type="3", arg_eval=["e", ", Adopt To Fit"]
            ),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="Variable Section",
        category="120",
        canfail="False",
    ),
    "598t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Variable", arg_type="1", arg_eval="Variable="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Search", arg_type="1", arg_eval=", Search="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Ignore Case", arg_type="3", arg_eval=["e", ", Ignore Case"]
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Multi-Line", arg_type="3", arg_eval=["e", ", Multi-Line"]
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="One Match Only",
                arg_type="3",
                arg_eval=["e", ", One Match Only"],
            ),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Store Matches In Array",
                arg_type="1",
                arg_eval=", Show Matches In Array=",
            ),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Replace Matches",
                arg_type="3",
                arg_eval=["e", ", Replace Matches"],
            ),
            ArgumentCode(
                arg_id="7", arg_required=False, arg_name="Replace With", arg_type="1", arg_eval="Replace With"
            ),
        ],
        name="Variable Search Replace",
        category="120",
        canfail="True",
    ),
    "599e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Action="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Cat=", "l", "877"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Cat=", "l", "877"]),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="", arg_type="1", arg_eval=", Schema="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="", arg_type="1", arg_eval=", Mime Type="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="0", arg_eval=", Priority="),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="", arg_type="1", arg_eval=["", "e", ", Stop Event"]),
        ],
        name="Intent Received",
        category="",
        canfail="",
    ),
    "599t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval="Cmd"),
        ],
        name="Due Today",
        category="130",
        canfail="False",
    ),
    "59t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval="Type"),
        ],
        name="Reboot",
        category="104",
        canfail="True",
    ),
    "5s": ActionCode(
        redirect="",
        args=[],
        name="Calendar Entry",
        category="",
        canfail="",
    ),
    "60t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Lat,Long", arg_type="1", arg_eval=", Lat,Long="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Label", arg_type="1", arg_eval=", Label="),
            ArgumentCode(
                arg_id="4", arg_required=False, arg_name="Text Colour", arg_type="1", arg_eval=", Spot Radius (Meters)="
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Text Size", arg_type="0", arg_eval=", Spot Color="),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Spot Radius (Metres)",
                arg_type="0",
                arg_eval="Spot Radius (Metres)",
            ),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Spot Colour", arg_type="1", arg_eval="Spot Colour"),
            ArgumentCode(arg_id="8", arg_required=True, arg_name="Icon", arg_type="4", arg_eval="Icon"),
        ],
        name="Element Add GeoMarker",
        category="102",
        canfail="True",
    ),
    "610246503t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast Query",
        category="",
        canfail="",
    ),
    "611944049t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoCast Speak",
        category="",
        canfail="",
    ),
    "612t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=[", Mode=", "l", "612"]
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Value", arg_type="1", arg_eval=", MilliSeconds="),
        ],
        name="Element Video Control",
        category="102",
        canfail="True",
    ),
    "61t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Time", arg_type="0", arg_eval="Time="),
        ],
        name="Vibrate",
        category="10",
        canfail="True",
    ),
    "62t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Pattern", arg_type="1", arg_eval="Pattern="),
            ArgumentCode(
                arg_id="1", arg_required=False, arg_name="Intensity Pattern", arg_type="1", arg_eval="Intensity Pattern"
            ),
        ],
        name="Vibrate Pattern",
        category="10",
        canfail="True",
    ),
    "63t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Lat,Long", arg_type="1", arg_eval=" Lat,Long="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Label", arg_type="1", arg_eval=" Label="),
        ],
        name="Element Delete GeoMarker",
        category="102",
        canfail="True",
    ),
    "643t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Cmd", arg_type="0", arg_eval="Cmd"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Status", arg_type="0", arg_eval="Status"),
        ],
        name="OfficeTalk",
        category="130",
        canfail="False",
    ),
    "64t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=[", Mode=", "l", "64"]),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Value", arg_type="1", arg_eval="Value"),
        ],
        name="Element Map Control",
        category="102",
        canfail="True",
    ),
    "657t": ActionCode(
        redirect="",
        args=[],
        name="Record Audio Stop",
        category="65",
        canfail="True",
    ),
    "658527372t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools HTML Read",
        category="",
        canfail="",
    ),
    "65t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Element Match", arg_type="1", arg_eval=", Element Match="
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Set", arg_type="3", arg_eval=[", Set=", "l", "65"]),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Animation Time (MS)",
                arg_type="0",
                arg_eval="Animation Time (MS)=",
            ),
            ArgumentCode(
                arg_id="4",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
        ],
        name="Element Visibility",
        category="102",
        canfail="True",
    ),
    "664t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Return", arg_type="1", arg_eval="Class or Object="),
            ArgumentCode(
                arg_id="1", arg_required=False, arg_name="Class Or Object", arg_type="1", arg_eval=", Function="
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Function", arg_type="1", arg_eval="Function"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Param", arg_type="1", arg_eval="Param"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Param", arg_type="1", arg_eval="Param"),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Param", arg_type="1", arg_eval="Param"),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Param", arg_type="1", arg_eval="Param"),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Param", arg_type="1", arg_eval="Param"),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Param", arg_type="1", arg_eval="Param"),
            ArgumentCode(arg_id="9", arg_required=False, arg_name="Param", arg_type="1", arg_eval="Param"),
        ],
        name="Java Function",
        category="35",
        canfail="True",
    ),
    "665t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "665"]),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Name", arg_type="1", arg_eval=", Name="),
        ],
        name="Java Object",
        category="35",
        canfail="False",
    ),
    "667t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval="Mode"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="File", arg_type="1", arg_eval="File"),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Table", arg_type="1", arg_eval="Table"),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Columns", arg_type="1", arg_eval="Columns"),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Query", arg_type="1", arg_eval="Query"),
            ArgumentCode(
                arg_id="5",
                arg_required=False,
                arg_name="Selection Parameters",
                arg_type="1",
                arg_eval="Selection Parameters",
            ),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Order By", arg_type="1", arg_eval="Order By"),
            ArgumentCode(
                arg_id="7",
                arg_required=False,
                arg_name="Output Column Divider",
                arg_type="1",
                arg_eval="Output Column Divider",
            ),
            ArgumentCode(
                arg_id="8", arg_required=True, arg_name="Variable Array", arg_type="1", arg_eval="Variable Array"
            ),
            ArgumentCode(arg_id="9", arg_required=True, arg_name="Use Root", arg_type="3", arg_eval="Use Root"),
            ArgumentCode(
                arg_id="10",
                arg_required=True,
                arg_name="Use Global Namespace",
                arg_type="3",
                arg_eval="Use Global Namespace",
            ),
        ],
        name="SQL Query",
        category="50",
        canfail="True",
    ),
    "66t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Image", arg_type="4", arg_eval=", Image="),
        ],
        name="Element Image",
        category="102",
        canfail="True",
    ),
    "67t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Set Depth", arg_type="0", arg_eval=", Set Depth="),
        ],
        name="Element Depth",
        category="102",
        canfail="True",
    ),
    "68t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["e", ", Set"]),
        ],
        name="Element Focus",
        category="102",
        canfail="True",
    ),
    "697t": ActionCode(
        redirect="",
        args=[],
        name="Shut Up",
        category="10",
        canfail="False",
    ),
    "699t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Text", arg_type="1", arg_eval="Text="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Engine:Voice", arg_type="1", arg_eval=", Engine/Voice="
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="File", arg_type="1", arg_eval=", File="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Pitch", arg_type="0", arg_eval=", Pitch="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="Speed", arg_type="0", arg_eval=", Speed="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="Network", arg_type="3", arg_eval=["e", ", Network"]),
            ArgumentCode(
                arg_id="6",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
        ],
        name="Say To File",
        category="10",
        canfail="True",
    ),
    "69t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Type", arg_type="0", arg_eval=[", Set=", "l", "69"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Visible", arg_type="3", arg_eval=["e", ", Visible"]),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Content", arg_type="1", arg_eval=", Content="),
        ],
        name="Element Create",
        category="102",
        canfail="True",
    ),
    "6e": ActionCode(
        redirect="",
        args=[],
        name="Phone Ringing",
        category="",
        canfail="",
    ),
    "6s": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Contact="),
        ],
        name="Phone Ringing",
        category="",
        canfail="",
    ),
    "701t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Button", arg_type="0", arg_eval="Button"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Repeat Times", arg_type="0", arg_eval="Repeat Times"),
        ],
        name="Dpad",
        category="55",
        canfail="True",
    ),
    "702624035e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="5", arg_eval="Gesture"),
        ],
        name="Fingerprint Gesture",
        category="",
        canfail="",
    ),
    "702t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Text", arg_type="1", arg_eval="Text"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Repeat Times", arg_type="0", arg_eval="Repeat Times"),
        ],
        name="Type",
        category="55",
        canfail="True",
    ),
    "703953103t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="KLWP Live Wallpaper",
        category="",
        canfail="",
    ),
    "703t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Button", arg_type="0", arg_eval="Button"),
        ],
        name="Button",
        category="55",
        canfail="True",
    ),
    "71t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Text Size", arg_type="0", arg_eval=", Text Size="),
        ],
        name="Element Text Size",
        category="102",
        canfail="True",
    ),
    "721t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["e", ", Set"]),
        ],
        name="Zoom Visibility",
        category="125",
        canfail="False",
    ),
    "731t": ActionCode(
        redirect="",
        args=[],
        name="Take Call",
        category="90",
        canfail="False",
    ),
    "732t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="Radio",
        category="90",
        canfail="False",
    ),
    "733t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="End Call",
        category="90",
        canfail="False",
    ),
    "734t": ActionCode(
        redirect="",
        args=[],
        name="Silence Ringer",
        category="90",
        canfail="False",
    ),
    "735t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval="Mode"),
        ],
        name="Mobile Data 2G/3G",
        category="80",
        canfail="False",
    ),
    "73t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Scene Name", arg_type="1", arg_eval="Scene Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Element", arg_type="1", arg_eval=", Element="),
        ],
        name="Element Destroy",
        category="102",
        canfail="True",
    ),
    "740t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Text", arg_type="1", arg_eval=", Text="),
        ],
        name="Zoom Text",
        category="125",
        canfail="False",
    ),
    "741t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Text Size", arg_type="0", arg_eval=", Text Size="),
        ],
        name="Zoom Text Size",
        category="125",
        canfail="False",
    ),
    "742t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Colour", arg_type="1", arg_eval=", Text Color="),
        ],
        name="Zoom Text Colour",
        category="125",
        canfail="False",
    ),
    "760t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Set", arg_type="0", arg_eval=", Set="),
        ],
        name="Zoom Alpha",
        category="125",
        canfail="False",
    ),
    "761t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="URI", arg_type="1", arg_eval=", URL="),
        ],
        name="Zoom Image",
        category="125",
        canfail="False",
    ),
    "762t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Colour", arg_type="1", arg_eval=", Color="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="End Colour", arg_type="1", arg_eval=", End Color="),
        ],
        name="Zoom Colour",
        category="125",
        canfail="False",
    ),
    "774351906t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Join Action",
        category="",
        canfail="",
    ),
    "775t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Variable", arg_type="1", arg_eval="Variable="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="File", arg_type="1", arg_eval=", File="),
        ],
        name="Write Binary",
        category="50",
        canfail="True",
    ),
    "776t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="File", arg_type="1", arg_eval="File"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To Var", arg_type="1", arg_eval="To Var"),
        ],
        name="Read Binary",
        category="50",
        canfail="True",
    ),
    "778682267t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Gestures",
        category="",
        canfail="",
    ),
    "779t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Warn Not Exist", arg_type="3", arg_eval="Warn Not Exist"
            ),
        ],
        name="Notify Cancel",
        category="10",
        canfail="False",
    ),
    "793t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="State", arg_type="0", arg_eval=", State="),
        ],
        name="Zoom State",
        category="125",
        canfail="False",
    ),
    "794294329t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSheets Add Sheet",
        category="",
        canfail="",
    ),
    "794t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Orientation",
                arg_type="0",
                arg_eval=[", Orientation=", "l", "57"],
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="X", arg_type="0", arg_eval=", X="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Y", arg_type="0", arg_eval=", Y="),
        ],
        name="Zoom Position",
        category="125",
        canfail="False",
    ),
    "795t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Element", arg_type="1", arg_eval="Element="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Orientation",
                arg_type="0",
                arg_eval=[", Orientation=", "l", "57"],
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Width", arg_type="0", arg_eval=", Width="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="Height", arg_type="0", arg_eval=", Height="),
        ],
        name="Zoom Size",
        category="125",
        canfail="False",
    ),
    "7e": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="0", arg_eval=["Type=", "l", "7e"]),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Sender="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Content="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", SIM Card="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", MMS Body="),
        ],
        name="Received Text",
        category="",
        canfail="",
    ),
    "7s": ActionCode(
        redirect="",
        args=[],
        name="Cell Near",
        category="",
        canfail="",
    ),
    "801498676t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Albums",
        category="",
        canfail="",
    ),
    "804t": ActionCode(
        redirect="",
        args=[],
        name="Input Method Select",
        category="55",
        canfail="False",
    ),
    "806t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Block Time (Check Help)", arg_type="0", arg_eval="Block Time="
            ),
        ],
        name="Turn On",
        category="40",
        canfail="False",
    ),
    "808t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Auto Brightness",
        category="40",
        canfail="False",
    ),
    "80s": ActionCode(
        redirect="",
        args=[],
        name="Docked",
        category="",
        canfail="",
    ),
    "810t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Level", arg_type="0", arg_eval="Level="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Disable Safeguard",
                arg_type="3",
                arg_eval=["e", ", Disable Safeguard"],
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Ignore Current Level",
                arg_type="3",
                arg_eval=["e", ", Ignore Current Level"],
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Immediate Effect", arg_type="3", arg_eval="Immediate Effect"
            ),
        ],
        name="Display Brightness",
        category="40",
        canfail="False",
    ),
    "811079103t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Global Action",
        category="",
        canfail="",
    ),
    "812t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Secs", arg_type="0", arg_eval="Secs="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Mins", arg_type="0", arg_eval=", Mins="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Hours", arg_type="0", arg_eval=", Hours="),
        ],
        name="Display Timeout",
        category="40",
        canfail="False",
    ),
    "815t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Type=", "l", "815"]),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Match", arg_type="1", arg_eval=", Match="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Store Result In", arg_type="1", arg_eval=", Store Result In="
            ),
        ],
        name="List Apps",
        category="15",
        canfail="False",
    ),
    "819222800t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Tracks",
        category="",
        canfail="",
    ),
    "820t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "820"]),
        ],
        name="Stay On",
        category="40",
        canfail="False",
    ),
    "822t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
        ],
        name="Display AutoRotate",
        category="40",
        canfail="False",
    ),
    "8618362t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Notification",
        category="",
        canfail="",
    ),
    "864692752t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Join",
        category="",
        canfail="",
    ),
    "877t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Action", arg_type="1", arg_eval="Action="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Cat", arg_type="0", arg_eval=[", Mode=", "l", "877"]),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Mime Type", arg_type="1", arg_eval=", Mime Type="),
            ArgumentCode(arg_id="3", arg_required=False, arg_name="Data", arg_type="1", arg_eval=", Data="),
            ArgumentCode(arg_id="4", arg_required=False, arg_name="Extra", arg_type="1", arg_eval=", Extra="),
            ArgumentCode(arg_id="5", arg_required=False, arg_name="Extra", arg_type="1", arg_eval=", Extra="),
            ArgumentCode(arg_id="6", arg_required=False, arg_name="Extra", arg_type="1", arg_eval=", Extra="),
            ArgumentCode(arg_id="7", arg_required=False, arg_name="Package", arg_type="1", arg_eval=", Package="),
            ArgumentCode(arg_id="8", arg_required=False, arg_name="Class", arg_type="1", arg_eval=", Class="),
            ArgumentCode(
                arg_id="9", arg_required=True, arg_name="Target", arg_type="0", arg_eval=[", Target=", "l", "877a"]
            ),
        ],
        name="Send Intent",
        category="104",
        canfail="True",
    ),
    "888t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Value", arg_type="0", arg_eval=", Value="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Wrap Around", arg_type="0", arg_eval=", Wrap Around="
            ),
        ],
        name="Variable Add",
        category="120",
        canfail="False",
    ),
    "890t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Name", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Value", arg_type="0", arg_eval=", Value="),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Wrap Around", arg_type="0", arg_eval=", Wrap Around="
            ),
        ],
        name="Variable Subtract",
        category="120",
        canfail="False",
    ),
    "8e": ActionCode(
        redirect="",
        args=[],
        name="Received Data SMS",
        category="",
        canfail="",
    ),
    "900t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Directory", arg_type="1", arg_eval="Directory="),
            ArgumentCode(arg_id="1", arg_required=False, arg_name="Match", arg_type="1", arg_eval=", Match="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Include Hidden Files",
                arg_type="3",
                arg_eval=["e", ", Include Hidden Files"],
            ),
        ],
        name="Browse Files",
        category="50",
        canfail="False",
    ),
    "901t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Source", arg_type="0", arg_eval=["Set=", "l", "901"]),
        ],
        name="Stop Location",
        category="60",
        canfail="False",
    ),
    "902t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Source", arg_type="0", arg_eval=["Set=", "l", "901"]),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="Timeout (Seconds)",
                arg_type="0",
                arg_eval=", Timeout (Seconds)=",
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Continue Task Immediately",
                arg_type="3",
                arg_eval=["e", ", Continue Task Immediately"],
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Keep Tracking", arg_type="3", arg_eval=["e", ", Keep Tracking"]
            ),
        ],
        name="Get Location",
        category="60",
        canfail="True",
    ),
    "903t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Title", arg_type="1", arg_eval="Title="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Language Model", arg_type="0", arg_eval=[", Mode=", "l", "903"]
            ),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="Language", arg_type="1", arg_eval=", Language="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Maximum Results", arg_type="0", arg_eval=", Maximum Results="
            ),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="Timeout (Seconds)", arg_type="0", arg_eval=", Timeout="
            ),
            ArgumentCode(
                arg_id="5", arg_required=True, arg_name="Hide Dialog", arg_type="3", arg_eval=["e", ", Hide Dialog"]
            ),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="Output Variables", arg_type="5", arg_eval="Output Variables"
            ),
        ],
        name="Get Voice",
        category="55",
        canfail="True",
    ),
    "904t": ActionCode(
        redirect="",
        args=[],
        name="Voice Command",
        category="55",
        canfail="False",
    ),
    "905t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "905"]),
        ],
        name="Location Mode",
        category="60",
        canfail="True",
    ),
    "906355163t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Voice Screen",
        category="",
        canfail="",
    ),
    "906686306e": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoLocation Geofences",
        category="",
        canfail="",
    ),
    "906t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval=["Mode=", "l", "906"]),
        ],
        name="Immersive Mode",
        category="40",
        canfail="True",
    ),
    "907418897t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoTools Action Report",
        category="",
        canfail="",
    ),
    "907t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=False, arg_name="Icons To Hide", arg_type="1", arg_eval="Icons To Hide="
            ),
        ],
        name="Status Bar Icons",
        category="40",
        canfail="True",
    ),
    "909t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Type", arg_type="0", arg_eval=["Mode=", "l", "909"]),
        ],
        name="Contacts",
        category="90",
        canfail="False",
    ),
    "90t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Number", arg_type="1", arg_eval="Number="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="Auto Dial", arg_type="3", arg_eval=["e", ", Auto Dial"]
            ),
            ArgumentCode(arg_id="2", arg_required=False, arg_name="SIM Card", arg_type="1", arg_eval=", Sim Card="),
        ],
        name="Call",
        category="90",
        canfail="False",
    ),
    "910t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Action", arg_type="0", arg_eval=["Mode=", "l", "910"]
            ),
        ],
        name="Call Log",
        category="90",
        canfail="False",
    ),
    "911t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Name", arg_type="1", arg_eval="Name"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Set", arg_type="3", arg_eval="Set"),
        ],
        name="Gentle Alarm",
        category="130",
        canfail="False",
    ),
    "915t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="CPU", arg_type="0", arg_eval="CPU"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Governor", arg_type="1", arg_eval="Governor"),
            ArgumentCode(
                arg_id="2", arg_required=True, arg_name="Min. Frequency", arg_type="0", arg_eval="Min. Frequency"
            ),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="Max. Frequency", arg_type="0", arg_eval="Max. Frequency"
            ),
        ],
        name="CPU",
        category="104",
        canfail="True",
    ),
    "917310686t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoSpotify Artists",
        category="",
        canfail="",
    ),
    "918403287t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoNotification Categories",
        category="",
        canfail="",
    ),
    "921575593t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoInput Keyguard",
        category="",
        canfail="",
    ),
    "940160580t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoShare",
        category="",
        canfail="",
    ),
    "941t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Code", arg_type="1", arg_eval="Code="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Layout", arg_type="1", arg_eval=", Layout="),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="Timeout (Seconds)",
                arg_type="0",
                arg_eval=", Timeout (Seconds)",
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="Show Over Keyguard",
                arg_type="3",
                arg_eval=["e", ", Show Over Keyguard"],
            ),
        ],
        name="HTML Popup",
        category="10",
        canfail="False",
    ),
    "956t": ActionCode(
        redirect="",
        args=[],
        name="NFC Settings",
        category="30",
        canfail="False",
    ),
    "957t": ActionCode(
        redirect="",
        args=[],
        name="Android Beam Settings",
        category="30",
        canfail="False",
    ),
    "958t": ActionCode(
        redirect="",
        args=[],
        name="NFC Payment Settings",
        category="30",
        canfail="False",
    ),
    "959t": ActionCode(
        redirect="",
        args=[],
        name="Dream Settings",
        category="30",
        canfail="False",
    ),
    "95t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=False, arg_name="Number Match", arg_type="1", arg_eval="Number Match="
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Info", arg_type="3", arg_eval=["e", "Info"]),
        ],
        name="Call Block",
        category="90",
        canfail="False",
    ),
    "96135575t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoLocation Info",
        category="",
        canfail="",
    ),
    "96585332t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="AutoWear Settings",
        category="",
        canfail="",
    ),
    "97t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="From Match", arg_type="1", arg_eval="From Match="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To", arg_type="1", arg_eval=", To="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="Info", arg_type="3", arg_eval=["e", ", Info"]),
        ],
        name="Call Divert",
        category="90",
        canfail="False",
    ),
    "985050481t": ActionCode(
        redirect="1040876951t",
        args=[],
        name="Actions",
        category="",
        canfail="",
    ),
    "987t": ActionCode(
        redirect="",
        args=[],
        name="Soft Keyboard",
        category="55",
        canfail="False",
    ),
    "988t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0", arg_required=True, arg_name="Set", arg_type="3", arg_eval=["Set=", "l", "switch_set"]
            ),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Go Home", arg_type="3", arg_eval=["e", ", Go Home"]),
        ],
        name="Car Mode",
        category="40",
        canfail="False",
    ),
    "989t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Mode", arg_type="0", arg_eval="Mode"),
        ],
        name="Night Mode",
        category="40",
        canfail="False",
    ),
    "999t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="Set", arg_type="1", arg_eval="Set"),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="To", arg_type="0", arg_eval="To"),
        ],
        name="Set Light",
        category="10",
        canfail="False",
    ),
    "99t": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=False, arg_name="Number", arg_type="1", arg_eval="Number="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="Info", arg_type="3", arg_eval=["e", "Info"]),
        ],
        name="Call Revert",
        category="90",
        canfail="False",
    ),
    "ButtonElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Label="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Label Size="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=", Label Width Scale %="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Label Color="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Font="),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Position=", "l", "TextElement1"]
            ),
            ArgumentCode(arg_id="7", arg_required=True, arg_name="", arg_type="8", arg_eval=", Icon="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "CheckBoxElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=["1", "e", ", Checked"]),
        ],
        name="",
        category="",
        canfail="",
    ),
    "DoodleElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=", Doodle="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Alpha="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "EditTextElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Text Size="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=", Text Width Scale Percent="
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Text Color="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Font="),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Position=", "l", "TextElement1"]
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Input Type=", "l", "EditTextElement"],
            ),
            ArgumentCode(arg_id="8", arg_required=True, arg_name="", arg_type="0", arg_eval=", Maximum Characters="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "ImageElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="8", arg_eval=", Image="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Alpha="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "ListElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Source=", "l", "ListElement1"]
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="",
                arg_type="1",
                arg_eval=[", Selection Mode=", "l", "ListElement2"],
            ),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Selection Mode=", "l", "ListElement2"],
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="0", arg_eval=", Horizontal Space="),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="", arg_type="0", arg_eval=", Vertical Space="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "ListElementItem": ActionCode(
        redirect="",
        args=[],
        name="",
        category="",
        canfail="",
    ),
    "MenuElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Source=", "l", "ListElement1"]
            ),
            ArgumentCode(
                arg_id="2",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Selection Mode=", "l", "ListElement2"],
            ),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=", Horizontal Space="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=", Vertical Space="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "OvalElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Shader=", "l", "RectElement1"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Color="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", End Color="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=", Border Width="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Border Color="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "PickerElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Min="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Max="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", Default="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Wrap Around"]),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Format=", "l", "NumberPickerElement"],
            ),
        ],
        name="",
        category="",
        canfail="",
    ),
    "PropertiesElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(
                arg_id="0",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Property Type=", "l", "PropertyElement1"],
            ),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Orientation=", "l", "PropertyElement2"],
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Background_Color="),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Property Type=", "l", "PropertyElement3"],
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Title="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Subtitle="),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="", arg_type="8", arg_eval=", Icon="),
            ArgumentCode(arg_id="7", arg_required=True, arg_name="", arg_type="1", arg_eval=", Tab Labels="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "RectElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Shader=", "l", "RectElement1"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Color="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", End Color="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=", Border Width="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Border XColor="),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="", arg_type="0", arg_eval=", Corner Radius="),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Rounded Corners=", "l", "RectElement2"],
            ),
        ],
        name="",
        category="",
        canfail="",
    ),
    "SceneElement": ActionCode(
        redirect="Map",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Lat/Long="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Zoom="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Show Traffic"]
            ),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Show Satellite"]
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Show Roads"]),
        ],
        name="Map",
        category="",
        canfail="",
    ),
    "SliderElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Orientation=", "l", "SliderElement1"],
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Min="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=", Max="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=", Default="),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Show Indicators=", "l", "SliderElement2"],
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="", arg_type="8", arg_eval=", Icon="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "SpinnerElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Source=", "l", "ListElement1"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Variable="),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="", arg_type="None", arg_eval=", Popup Background Color="
            ),
        ],
        name="",
        category="",
        canfail="",
    ),
    "SwitchElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Checked"]),
        ],
        name="",
        category="",
        canfail="",
    ),
    "TextElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="1", arg_eval=", Text="),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="0", arg_eval=", Text Size="),
            ArgumentCode(
                arg_id="3",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=", Text Width Scale Percent (100=0%)=",
            ),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=", Text Color="),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=", Font="),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Position=", "l", "TextElement1"]
            ),
            ArgumentCode(
                arg_id="7",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Vertical Fit Mode=", "l", "TextElement2"],
            ),
            ArgumentCode(
                arg_id="8",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=[", Text Format=", "l", "TextElement3"],
            ),
        ],
        name="",
        category="",
        canfail="",
    ),
    "ToggleElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", On"]),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Off Label="),
            ArgumentCode(arg_id="3", arg_required=True, arg_name="", arg_type="1", arg_eval=", On Label="),
            ArgumentCode(arg_id="4", arg_required=True, arg_name="", arg_type="0", arg_eval=", Label Size="),
            ArgumentCode(
                arg_id="5",
                arg_required=True,
                arg_name="",
                arg_type="0",
                arg_eval=", Label Width Width Scale Percent (100=0%)=",
            ),
            ArgumentCode(arg_id="6", arg_required=True, arg_name="", arg_type="1", arg_eval=", Label Color="),
        ],
        name="",
        category="",
        canfail="",
    ),
    "WebElement": ActionCode(
        redirect="",
        args=[
            ArgumentCode(arg_id="0", arg_required=True, arg_name="", arg_type="1", arg_eval="Name="),
            ArgumentCode(
                arg_id="1", arg_required=True, arg_name="", arg_type="0", arg_eval=[", Mode=", "l", "WebElement"]
            ),
            ArgumentCode(arg_id="2", arg_required=True, arg_name="", arg_type="1", arg_eval=", Source="),
            ArgumentCode(
                arg_id="3", arg_required=True, arg_name="", arg_type="0", arg_eval=["", "e", ", Allow Phone Access"]
            ),
            ArgumentCode(
                arg_id="4", arg_required=True, arg_name="", arg_type="1", arg_eval=["", "e", ", Self Handle Links"]
            ),
            ArgumentCode(arg_id="5", arg_required=True, arg_name="", arg_type="1", arg_eval=["", "e", ", DB API"]),
            ArgumentCode(
                arg_id="6", arg_required=True, arg_name="", arg_type="1", arg_eval=["", "e", ", Support Popups"]
            ),
            ArgumentCode(arg_id="7", arg_required=True, arg_name="", arg_type="0", arg_eval=", User Agent="),
        ],
        name="",
        category="",
        canfail="",
    ),
}
