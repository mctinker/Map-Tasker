"""Help content for the graphical user interface."""

#! /usr/bin/env python3

#                                                                                      #
# userintr: provide GUI and process input for program arguments                        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from maptasker.src.guiutils import CHANGELOG
from maptasker.src.sysconst import VERSION

# NOTE: The textbox is used for help information via new_message_box, normal one-liner messages via display_message_box
#       and multi-line messages via display_multiple_message.
# Help Text
INFO_TEXT = (
    "MapTasker displays your Android Tasker configuration based on your uploaded Tasker XML "
    "file (e.g. 'backup.xml'). The display will optionally include all Projects, Profiles, Tasks "
    "and their actions, Profile/Task conditions and other Profile/Task related information.\n\n"
    "* Display options are:\n"
    "    Level 0: display first Task action only, for unnamed Tasks only (silent).\n"
    "    Level 1 = display all Task action details for unknown Tasks only (default).\n"
    "    Level 2 = display full Task action name on every Task.\n"
    "    Level 3 = display full Task action details on every Task with action details.\n"
    "    Level 4 = display level of 3 plus Project's global variables.\n\n"
    "    Level 5 = display level of 4 plus Scene argument details.\n\n"
    "* Just Display Everything: Turns on the display of "
    "conditions, TaskerNet information, preferences, pretty output, directory, and configuration outline.\n\n"
    "* Display Conditions: Turn on the display of Profile and Task conditions.\n\n"
    "* Display TaskerNet Info - If available, display TaskerNet publishing information.\n\n"
    "* Display Tasker Preferences - display Tasker's system Preferences.\n\n"
    "* Hide Task Details under Twisty: hide Task information within ► and click to display.\n\n"
    "* Display Directory of hyperlinks at beginning.\n\n"
    "* Display Configuration Outline and Map of your Projects/Profiles/Tasks/Scenes.\n\n"
    "* Display Prettier Output: Make the output more human-readable by adding newlines and indentation for all arguments.\n\n"
    "* Project/Profile/Task/Scene Names options to italicize, bold, underline and/or highlight their names.\n\n"
    "* Task Action Limit: display a warning if the Task has more than the specified number of actions.\n\n"
    "* Indentation amount for If/Then/Else Task Actions.\n\n"
    "* Save Settings - Save these settings for later use.\n\n"
    "* Restore Settings - Restore the settings from a previously saved session.\n\n"
    "* Report Issue - This will bring up your browser to the issue reporting site, and you can use this to "
    "either report a bug or request a new feature ( [Feature Request] )\n\n"
    "* Appearance Mode: Dark, Light, or System default.\n\n"
    "* Views: Display your configuration Map, Diagram, or Tree view of your Projects, Profiles, Tasks and Scenes directly in the GUI.\n\n"
    "* View Limit: Control the amount of processing time used when generating the view.\n\n"
    "* Reset Options: Clear everything and start anew.\n\n"
    "* Clear Messages: Clear any messages in the textbox.\n\n"
    "* Font To Use: Change the monospace font used for the output.\n\n"
    "* Display Outline: Display Projects/Profiles/Tasks/Scenes configuration outline.\n\n"
    "* Get XML from Android Device: fetch the backup/exported "
    "XML file from Androiddevice.  You will be asked for the IP address and port number for your"
    " Android device, as well as the file location on the device.\n\n"
    "* Get Local XML: fetch the backup/exported XML file from your local drive.\n\n"
    "* Run and Exit: Run the program with the settings provided, display the results in the web browser and then exit.\n"
    "* ReRun: Run multiple times (each time with new settings) without exiting, displaying the results in the browser.\n\n"
    "* Specific Name tab: enter a single, specific named item to display...\n"
    "   - Project Name: enter a specific Project to display.\n"
    "   - Profile Name: enter a specific Profile to display.\n"
    "   - Task Name: enter a specific Task to display.\n"
    "   (These three are exclusive: enter one only)\n\n"
    "* Colors tab: select colors for various elements of the display.\n"
    "              (e.g. color for Projects, Profiles, Tasks, etc.).\n\n"
    "* Analyze tab: Run the analysis for a Project, Profile or Task against an Ai model.\n\n"
    "* Debug tab: Display Runtime Settings option and turn on Debug mode.\n\n"
    "* Exit: Exit the program (quit).\n\n"
    "Notes:\n\n"
    "- You will be prompted to identify your Tasker XML file once you hit the 'Run and Exit' or 'ReRun' button if you have not yet done so.\n\n"
    "- If you receive any of the following the runtime errors, you can ignore them:\n"
    "      '[CATransaction synchronize] called within transaction'.\n"
    "      'IMKClient Stall detected...'.\n\n"
    "- Drag the window to expand the text as desired.\n\n"
    "- View the entire change log history at https://github.com/mctinker/Map-Tasker/blob/Master/Changelog.md\n\n"
    "- Changing the appearance mode will change the colors used for the output to their default values.\n\n"
)
BACKUP_HELP_TEXT = (
    "The following steps are required in order to fetch a Tasker XML file directly"
    " from your Android device.\n\n"
    "1- Both this device and the Android device must be on the same named network.\n\n"
    "2- The Tasker Project 'HTTP Server Example' or identical function must be"
    " installed and active on the Android device (the server must be running):\n\n"
    "    https://shorturl.at/bwCD4\n\n"
    "3- If you want to use the 'List XML Files' option, then you must also import the following profile "
    "into the Android device and make sure the imported profile 'MapTasker List' is enabled:\n\n"
    "    https://shorturl.at/sGS08\n\n"
    "You will be asked for the IP address, the port number for your Android device,"
    " as well as the file location on the Android device.  Default values are supplied, where...\n\n"
    "'192.168.0.210' is the default IP address,\n\n'1821' is the default port number for the Tasker HTTP"
    " Server Example running on your Android device\n\n'/Tasker/configs/user/backup.xml' is the default file location.  "
    "If you don't know the file location and have already entered your IP address and port, then you can select "
    "the 'List XML Files' button to get a list of available XML files on your Android device for selection.\n\n"
    "Usage Notes:\n\n"
    "The IP address and port can be obtained by installing the 'HTTP Server Example' project from the above URL "
    "on your Android device. Then run the task named 'Update GD HTTP Info' to get the Android notification:\n\n"
    "HTTP Server Info\n"
    'Server info updated {"device name":"http://192.168.0.49:1821"}\n\n'
    "- To fetch the XML file, click on the button\n\n 'Get XML from Android Device'\n\n"
    "Then modify the default values presented in the input fields below this button, and then"
    " click on the button 'Enter and Click Here to Set XML Details' or 'List XML Files'.\n\n"
    "- Hitting either button will ping the Android device to see if it is available.  The ping will timeout after"
    " 10 seconds if the device is not reachable.  Make sure that the IP address is correct.\n\n"
    "Click on the 'Cancel Entry' button to back out of this fetch process.\n\n"
)
LISTFILES_HELP_TEXT = (
    "Clicking this button will result in the following actions:\n\n"
    "- The IP Address will be used to ping the Android device.\n\n"
    "- The IP Address and port number will be used to query the Android device and get a list of available XML files "
    "found in the Tasker folder.\n\n"
    "- The list of found XML files will be presented in a pulldown menu from which you can select the one you want "
    "to use.\n\n"
    "- Once you have selected the XML file, it will be fetched and verified as valid XML which is then used as "
    "input to the program once you subsequently click on the 'Run' or 'ReRun' button.\n\n"
    "In order for this to work, you MUST have already imported the 'MapTasker List' profile into Tasker running "
    "on your Android device.  This profile can be found at the following URL:\n\n"
    "    https://t.ly/8vI1f\n\n"
)

VIEW_HELP_TEXT = (
    "Display the 'Map', 'Diagram' or 'Tree' view of your configuration directly within the GUI.\n\n"
    "XML must first be obtained from the either local drive or Android device for the views to work.\n\n"
    "All view windows can be stretched and moved as needed.  Rerun the specific view command to refresh the view with the new size and position.\n\n"
    "If the XML has already been fetched, it will be used as input to the view.  Hitting the 'Reset' button will clear the view data.\n\n"
    "Very large configurations will incur extended run times for Maps and Diagrams.  For best performance, select a single Project or Profile to map.\n\n"
    "\nThe Map View has the following behavior:\n\n"
    " - While the browser is not invoked directly, the map can be displayed in the browser by opening the local 'MapTasker.html' file.\n\n"
    " - The 'Display Configuration Outline' setting is ignored since it does not work in the Map view.\n\n"
    " - Going up one or two levels using the directory hyperlink will result in the generation of a new map view.\n\n"
    "\nThe Diagram View has the following behavior:\n\n"
    " - Only Projects and Profiles can be displayed. XML consisting of only a single Task or Scene will not be displayed.\n\n"
    " - Click on a horizontal connector to highlight the entire connection in the diagram.\n\n"
    "\nThe Tree View has the following behavior:\n\n"
    "- Huge configurations that scroll beyond the bottom of the screen are not viewable in their entirety yet.\n\n"
    "- Only Projects can be displayed. XML consisting of only a single Profile or Task or Scene will not be displayed.\n\n"
    "- All Projects, Profiles, Tasks and Scenes are displayed regardless of the single name setting.\n\n"
)
AI_HELP_TEXT = (
    "The Analyze tab is used to run the Ai analysis on your Profile, using either the local llama model or the server-based Open AI, Claude or DeepSeek models.\n\n"
    "The following steps are required in order to run AI against your Profile.\n\n"
    "1- If using a server-based AI, you must have a valid API key from the provider (e.g. OpenAI).  You can use the 'Show/Edit API Key(s)' button to enter your key(s).\n\n"
    "2- The default prompt is: 'suggest improvements in performance and readibility: (your project/profile/task)', and is automatically preceded by: 'Given the following (Project/Profile/Task) in Tasker, '.  If modifying the prompt, you are only modifing the 'suggest improvements...' portion.\n\n"
    "3- Select the model you want to use.\n\n"
    "   o The model selected will determine with which AI the analysis is to be performed.\n\n"
    "4- Click the 'Run Analysis' button.  It will turn pink when all of the necessary data has been entered.\n\n"
    "   o If you have not yet selected a model, prompt or single Project, Profile or Task, or valid API key, then you will be prompted to do so first.\n\n"
    "   o The process may take some time and runs in the background.  The results will appear in a separate window.\n\n"
    "   o Local models not yet loaded onto your computer will be loaded in the background once the analysis begins.\n\n"
    "Your designated api-keys (if any), model, selected Project, Profile or Task and Ai prompt will all be saved across sessions.\n\n"
    "The 'Rerun' feature will be used under-the-covers to display the results of the analysis in a new window.\n\n"
)

VIEWLIMIT_HELP_TEXT = (
    "The 'View Limit' is a means to control the amount of processing time used when generating the view.\n\n"
    "- The numbers represent the relative amount of output lines to be generated.\n\n"
    "- The larger the limit, the larger the output that will be allowed to be mapped.  The more output that is generated, the greater the processing time.\n\n"
    "- Very large configurations will generate very large output maps and will cause greater processing time.  On older devices, this can take up to 30 seconds or more.\n\n"
    "- By setting a limit, you can control the processing time used when mapping a configuration by not allowing longer durations.\n\n"
    "- If the limit is hit when calculating the map, no output map will be generated.\n\n"
    "- You can experiment with this setting to see which setting is best for your use case.\n\n"
    "- Selecting a single Project, Profile or Task is another means to limit the processing time.\n\n"
)

SEARCH_HELP_TEXT = (
    "The 'Search' button will search for and highlight every instance of the string entered in the search box.\n\n"
    "Hover over any of the highlighted matching strings to see all matches.\n\n"
    "The 'Next' and 'Prev' buttons will try to make the next and previous occurrence of the search string visible in the text view box, and highlight them in a different color.\n\n"
    "The accuracy of making the search string visible is not always perfect and is out of the control of the this program.\n\n"
    "When the end or beginning of the text view box is reached, the search will stop and a message will be displayed for several seconds.\n\n"
    "The 'Clear' button will clear the search results.\n\n"
)

PPP_HELP_TEXT = (
    "The 'Profiles Per Line' setting is used to control the number of Profiles to be displayed per line when diagramming the configuration.\n\n"
    "The smaller the number, the narrower the diagram and vice versa.\n\n"
    "Fewer Profiles per line may make it easier too view the diagram connectors that extend to the right, while at the same time the Diagram wil be longer.\n\n"
    "Selecting a number will automatically re-generate the diagram with the new setting.\n\n"
    "This setting is only valid for the currrent Diagram view, and will be reset back to the default value when the Diagram view is closed.\n\n"
)
APIKEY_HELP_TEXT = (
    "This menu is where you define your AI API keys for use by the AI 'Analyze' button.\n\n"
    "The keys are saved across sessions.\n\n"
    "The keys are used to access the OpenAI, Claude AI, Gemini AI, and DeepSeek AI server-based models.\n\n"
    "Click on the 'Clear' button to clear a specific API key entry.\n\n"
    "Select 'Ok' to save the changes or 'Cancel' to back out of the changes.\n\n"
)
HELP = f"MapTasker {VERSION} Help\n\n{INFO_TEXT}{CHANGELOG}"
