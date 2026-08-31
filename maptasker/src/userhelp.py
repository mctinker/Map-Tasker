"""Help content for the graphical user interface."""

#! /usr/bin/env python3

#                                                                                      #
# userintr: provide GUI and process input for program arguments                        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from collections.abc import Callable

from maptasker.src.sysconst import VERSION

# NOTE: The textbox is used for help information via new_message_box, normal one-liner messages via display_message_box
#       and multi-line messages via display_multiple_message.
# Help Text
INFO_TEXT = (
    "MapTasker displays your Android Tasker configuration based on your uploaded Tasker XML "
    "file (e.g. 'backup.xml'). The display will optionally include all Projects, Profiles, Tasks "
    "and their actions, Profile/Task conditions and other Profile/Task related information.  \n"
    "Once the XML file is loaded, you can optionally edit your Projects, Profiles, Tasks, and Scenes.  \n"
    "* Display options are:\n"
    "    Level 0: display first Task action only, for unnamed Tasks only (silent).\n"
    "    Level 1 = display all Task action details for unknown Tasks only (default).\n"
    "    Level 2 = display full Task action name on every Task.\n"
    "    Level 3 = display full Task action details on every Task with action details.\n"
    "    Level 4 = display level of 3 plus Project's global variables.\n"
    "    Level 5 = display level of 4 plus Scene argument details.  \n"
    "* Just Display Everything: Turns on the display of "
    "conditions, TaskerNet information, preferences, pretty output, directory, and configuration outline.  \n"
    "* Display Conditions: Turn on the display of Profile and Task conditions.  \n"
    "* Display TaskerNet Info - If available, display TaskerNet publishing information.  \n"
    "* Display Tasker Preferences - display Tasker's system Preferences.  \n"
    "* Hide Task Details under Twisty: hide Task information within ► and click to display.  \n"
    "* Display Directory of hyperlinks at beginning.  \n"
    "* Display Prettier Output: Make the output more human-readable by adding newlines and indentation for all arguments.  \n"
    "* Project/Profile/Task/Scene Names options to italicize, bold, underline and/or highlight their names.  \n"
    "* Task Action Limit: display a warning if the Task has more than the specified number of actions.  \n"
    "* Indentation amount for If/Then/Else Task Actions.  \n"
    "* Language: Select the language to be used for the output.  The default is English.  \n"
    "* Font To Use: Change the monospace font used for the output.  \n"
    "* View Limit: Control the amount of processing time used when generating the view.  \n"
    "* Notification Duration: How long a pop-up message stays on screen before it disappears.  'Until dismissed' keeps every message up until you close it.  \n"
    "* Dark Mode: Switch the GUI between light and dark appearance.  \n"
    "* Reset Options: Clear everything and start anew.  \n"
    "* Get Local XML File: fetch the backup/exported XML file from your local drive.  \n"
    "* Save Settings - Save these settings for later use.  \n"
    "* Restore Settings - Restore the settings from a previously saved session.  \n"
    "* Report Issue: Open the GitHub Issues page in your browser to report a problem or suggestion to the developer.  \n"
    "* Display Views: Display your configuration Map, Diagram, or Tree view of your Projects, Profiles, Tasks and Scenes directly in the GUI.  \n"
    "* Clear: Clear the Map/Diagram/Tree view data currently held and displayed.  \n"
    "* Health Check: Scan the loaded XML for broken references, unreferenced Tasks, Profiles and Scenes, and naming problems.  Click a finding to be taken to it in the Map.  \n"
    "* Compare Files: Compare another XML file against the loaded one to see what was added, removed, renamed and changed.  \n"
    "* Variable Xref: Trace every %variable in the loaded XML: where each one is set, where it is read, which are read but never set, which are set but never read, and which near-identical names are likely typos.  \n"
    "* Open View In New Window: Open each Map/Diagram request in its own new window/tab rather than reusing that view's existing one.  \n"
    "* Close Tabs On Exit: Have 'Exit' also close the main MapTasker window and any Map/Diagram windows/tabs it opened.  \n"
    "* Get XML from Android Device: fetch the backup/exported "
    "XML file from Android device.  You will be asked for the IP address and port number for your"
    " Android device, as well as the file location on the device.  \n"
    "   - List XML Files: List the XML files found on the Android device so you can select one rather than typing its location.\n"
    "   - Cancel Entry: Back out of the Android fetch process.  \n"
    "* Specific Name tab: enter a single, specific named item to display...\n"
    "   - Project Name: enter a specific Project to display.\n"
    "   - Profile Name: enter a specific Profile to display.\n"
    "   - Task Name: enter a specific Task to display.\n"
    "   - Scene Name: enter a specific Scene to display.  Its owning Project's heading and the\n"
    "                 Scene's elements (plus any Tasks those elements invoke) are displayed;\n"
    "                 the Project's Profiles and its other Scenes are not.\n"
    "   (These four are exclusive: enter one only)\n"
    "   - List Unnamed Items: Include unnamed Profiles and Tasks in the four pulldowns above.  \n"
    "   Add and Edit Projects, Profiles, Tasks and Scenes directly in the GUI, with various save options...\n"
    "   - Add Project/Profile/Task/Scene: Create a new object and add it to the loaded XML.\n"
    "   - Edit Project/Profile/Task/Scene: Modify the object currently selected in the pulldowns above.\n"
    "   - Rename: Give the object being edited a new name.\n"
    "   - Delete: Remove the object being edited from the loaded XML.\n"
    "   - Duplicate: Make a copy of the selected Scene element.\n"
    "   - Preview: Display the Scene being edited as it will appear.\n"
    "   - Save / Export: Write the object out to a standalone XML file of your choosing.\n"
    "   - Save To Current File: Write the entire configuration to a new, timestamped file beside the loaded one.\n"
    "   - Save To Android: Write the object back to your Android device.\n"
    "     (A safety copy of anything a save is about to overwrite is kept in the 'MapTasker_Backups' folder.)  \n"
    "   Editing commands...\n"
    "   - Undo: Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML.  This changes what is loaded, not any file.\n"
    "   - Redo: Reapply the change most recently backed out by 'Undo'.\n"
    "   - Edit History: List every change made to the loaded XML this session, newest first.  \n"
    "* Colors tab: select colors for various elements of the display.\n"
    "              (e.g. color for Projects, Profiles, Tasks, etc.).\n"
    "   - Reset to Default Colors: Restore every color to its default value.  \n"
    "* Analyze tab: Run the analysis for a Project, Profile, Task or Scene against an Ai model.\n"
    "   - Show/Edit API Key(s): Enter or change the API keys used by the server-based AI models.\n"
    "   - Change Prompt: Modify the prompt sent to the AI model.\n"
    "   - Run Analysis: Submit the selected Project/Profile/Task and prompt to the selected model.\n"
    "   - Extended: List all available models rather than just the default set.  \n"
    "* Debug tab: Display Runtime Settings option and turn on Debug mode.  \n"
    "* Map/Diagram/Tree view toolbar commands are...\n"
    "   - Search: Highlight every instance of the case-insensitive text entered in the search box, up to the first 200.  Click a line number to go to that line.\n"
    "   - Find/Replace: (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene.  Click a result to be taken to it.\n"
    "   - Save Results: Save the 'Find/Replace' results to a text file.\n"
    "   - Top / Bottom: Jump to the beginning or the end of the displayed output.\n"
    "   - Toggle Wrap: Turn line wrapping on or off in the displayed output.\n"
    "   - Profiles Per Line: (Diagram only) The number of Profiles drawn side-by-side on a single line.  \n"
    "* Display Help: Display this help text.  \n"
    "* Get Android Help: Display the help for fetching the XML file from your Android device.  \n"
    "* '?' buttons: Display the help specific to the section in which the button appears.  \n"
    "* Exit: Exit the program (quit).  \n"
    "Notes:  \n"
    "- View the entire change log history at https://github.com/mctinker/Map-Tasker/blob/Master/Changelog.md  \n"
    "- Changing the appearance mode will change the colors used for the output to their default values.  \n"
)
BACKUP_HELP_TEXT = (
    "The following steps are required in order to fetch a Tasker XML file directly"
    " from your Android device.  \n"
    "1- Both this device and the Android device must be on the same named network.  \n"
    "2- The Tasker Project 'HTTP Server Example' or identical function must be"
    " installed and active on the Android device (the server must be running):  \n"
    "    https://tinyurl.com/4p5cz8sv  \n"
    "That is the only setup required.  The 'List XML Files' option used to need a second, separate "
    "profile ('MapTasker List') imported from TaskerNet and left enabled; it no longer does.  MapTasker "
    "now installs a small Task named 'MapTasker List Files v1' on the device to do the listing, the same "
    "way 'App not listed?' installs one to fetch your applications.  \n"
    "You will be asked for the IP address, the port number for your Android device,"
    " as well as the file location on the Android device.  Default values are supplied, where...  \n"
    "'192.168.0.210' is the default IP address,  \n'1821' is the default port number for the Tasker HTTP"
    " Server Example running on your Android device  \n'/Tasker/configs/user/backup.xml' is the default file location.  "
    "If you don't know the file location and have already entered your IP address and port, then you can select "
    "the 'List XML Files' button to get a list of available XML files on your Android device for selection.  \n"
    "Usage Notes:  \n"
    "The IP address and port can be obtained by installing the 'HTTP Server Example' project from the above URL "
    "on your Android device. Then run the task named 'Update GD HTTP Info' to get the Android notification:  \n"
    "HTTP Server Info\n"
    'Server info updated {"device name":"http://192.168.0.49:1821"}  \n'
    "- To fetch the XML file, click on the button  \n 'Get XML from Android Device'  \n"
    "Then modify the default values presented in the input fields below this button, and then"
    " click on the button 'Enter and Click Here to Set XML Details' or 'List XML Files'.  \n"
    "- Hitting either button will ping the Android device to see if it is available.  The ping will timeout after"
    " 10 seconds if the device is not reachable.  Make sure that the IP address is correct.  \n"
    "Click on the 'Cancel Entry' button to back out of this fetch process.  \n"
)
LISTFILES_HELP_TEXT = (
    "Clicking this button will result in the following actions:  \n"
    "- The IP Address will be used to ping the Android device.  \n"
    "- The IP Address and port number will be used to query the Android device and get a list of available XML files "
    "found in the Tasker folder.  \n"
    "- The list of found XML files will be presented in a pulldown menu from which you can select the one you want "
    "to use.  \n"
    "- Once you have selected the XML file, it will be fetched and verified as valid XML which is then used as "
    "input to the program once you subsequently click on the 'Run' or 'ReRun' button.  \n"
    "The listing is done by a small Task named 'MapTasker List Files v1', which MapTasker installs on your "
    "Android device the first time you use this button and then leaves there.  Nothing has to be imported by "
    "hand.  It requires the 'HTTP Server Example' project running on the device and Tasker 6.2 or higher -- "
    "the same requirements 'Save to Android' has -- and Tasker will ask you to authorize the connection the "
    "first time.  \n"
    "Allow a few seconds: installing the Task (once), running it and reading back its answer is not instant.  \n"
)

VIEW_HELP_TEXT = (
    "Display the 'Map', 'Diagram' or 'Tree' view of your configuration directly within the GUI.  \n"
    "XML must first be obtained from the either local drive or Android device for the views to work.  \n"
    "If the XML has already been fetched, it will be used as input to the view.  Hitting the 'Clear' button will clear the view data.  \n"
    "Very large configurations will incur extended run times for Maps and Diagrams.  For best performance, select a single Project or Profile to map.  \n"
    "Optionally, limit the amount of data to be processed by using the 'View Limit' setting.  The larger the limit, the larger the output that will be allowed to be mapped.  The more output that is generated, the greater the processing time.  \n"
    "\nThe Diagram View has the following behavior:  \n"
    " - Only Projects and Profiles can be displayed. XML consisting of only a single Task or Scene will not be displayed.  \n"
    " - Click on a horizontal connector to highlight the entire connection in the diagram.  \n"
    "\nThe Tree View has the following behavior:  \n"
    "- Only Projects can be displayed. XML consisting of only a single Profile or Task or Scene will not be displayed.  \n"
    "- All Projects, Profiles, Tasks and Scenes are displayed regardless of the single name setting.  \n"
)
AI_HELP_TEXT = (
    "The Analyze tab is used to run the Ai analysis on your Profile, using either the local llama model or the server-based Open AI, Claude or DeepSeek models.  \n"
    "The following steps are required in order to run AI against your Profile.  \n"
    "1- If using a server-based AI, you must have a valid API key from the provider (e.g. OpenAI).  You can use the 'Show/Edit API Key(s)' button to enter your key(s).  \n"
    "2- The default prompt is: 'suggest improvements in performance and readibility: (your project/profile/task)', and is automatically preceded by: 'Given the following (Project/Profile/Task) in Tasker, '.  If modifying the prompt, you are only modifing the 'suggest improvements...' portion.  \n"
    "3- Select the model you want to use.  \n"
    "   o The model selected will determine with which AI the analysis is to be performed.  \n"
    "4- Click the 'Run Analysis' button.  It will turn green when all of the necessary data has been entered.  \n"
    "   o If you have not yet selected a model, prompt or single Project, Profile or Task, or valid API key, then you will be prompted to do so first.  \n"
    "   o The process may take some time and runs in the background.  The results will appear in a separate window.  \n"
    "   o Local models not yet loaded onto your computer will be loaded in the background once the analysis begins.  \n"
    "Your designated api-keys (if any), model, selected Project, Profile or Task and Ai prompt will all be saved across sessions.  \n"
    "The 'Rerun' feature will be used under-the-covers to display the results of the analysis in a new window.  \n"
)

VIEWLIMIT_HELP_TEXT = (
    "The 'View Limit' is a means to control the amount of processing time used when generating the view.  \n"
    "- The numbers represent the relative amount of output lines to be generated.  \n"
    "- The larger the limit, the larger the output that will be allowed to be mapped.  The more output that is generated, the greater the processing time.  \n"
    "- Very large configurations will generate very large output maps and will cause greater processing time.  On older devices, this can take up to 30 seconds or more.  \n"
    "- By setting a limit, you can control the processing time used when mapping a configuration by not allowing longer durations.  \n"
    "- If the limit is hit when calculating the map, the output will stop there.  \n"
    "- You can experiment with this setting to see which setting is best for your use case.  \n"
    "- Selecting a single Project, Profile or Task is another means to limit the processing time.  \n"
)

APIKEY_HELP_TEXT = (
    "This menu is where you define your AI API keys for use by the AI 'Analyze' button.  \n"
    "The keys are saved across sessions.  \n"
    "The keys are used to access the OpenAI, Claude AI, Gemini AI, and DeepSeek AI server-based models.  \n"
    "Click on the 'Clear' button to clear a specific API key entry.  \n"
    "Select 'Ok' to save the changes or 'Cancel' to back out of the changes.  \n"
)
# The main help screen's three pieces, held apart because the version number sits between
# the first two.  A msgid carrying the release number would be invalidated by every
# release, so there is deliberately no constant holding the assembled screen -- see
# build_help.
HELP_HEADING = "Help"
COMMAND_REFERENCE_TEXT = (
    "See the MapTasker [Command Reference](https://github.com/mctinker/Map-Tasker/wiki/Command-Reference)"
    " for more information.  \n"
)


def build_help(translate: Callable[[str], str] | None = None) -> str:
    """The 'Display Help' screen, in the language `translate` looks strings up in.

    Each piece is looked up on its own, and the version number is dropped in between them
    untranslated.  Handing gettext the whole screen instead is what used to happen, and it
    could only ever miss: no catalog holds a msgid with a version number in it, and gettext
    answers a miss by handing back what it was given -- which looks exactly like a
    translation into English, silently, in all 33 languages.

    The three pieces are msgids in their own right because sync_missing_msgids.py collects
    every upper-case string constant in this module (see its help_text_strings), so a
    catalog carries them without anything having to ask for them by name.

    Args:
        translate: the lookup each piece is put through -- maputil2.translate_string in the
            GUI.  Omitted leaves the screen in English.

    Returns:
        str - the assembled help screen
    """
    lookup = translate or (lambda text: text)
    return f"MapTasker {VERSION} {lookup(HELP_HEADING)}  \n{lookup(INFO_TEXT)}{lookup(COMMAND_REFERENCE_TEXT)}"
