# MapTasker Change Log

All notable changes to this project will be documented in this file!

## [5.2.2] 30-Sep-2024

### Added

- Added: Added the 'IA' (Icon Alignment) button next to the 'Diagram' view to enable/disable connector alignment if icons are in Task names for better performance with very complex diagrams.  Refer to the view '?' (help) in the GUI for details.
- Added: Tasker object names are colored in the Diagram view.

### Changed

- Changed:

### Fixed

- Fixed: Taks with commas in their names do not display correctly in the Diagram view.
- Fixed: Task names with "[" embedded in can not be found when clicking on it's directory hotlink.
- Fixed: Diagram is missing bars (|) in some instances.  Bars ares misaligned if the Task is not found.

### Known Issues

- Open Issue: The background color may not be correct if using the Firefox browser in light mode if the system default is dark mode.
- Open Issue: The Map view Project/Profile/Task/Scene names with icons are not displaying correctly in the Map view if using highlighting (underline, etc.).

## Older History Logs

## [5.2.0]

- Added: 'Up Two Levels' has been added to the Map view.
- Added: Ai analysis OpenAi models 'o1-preview' and 'o1-mini' have been added.
- Added: Ai analysis local models 'qwen2' and 'gemma2' have been added.
- Changed: Diagram rewrite to improve readibility and performance.
- Fixed: Diagram displaying too much filler between tasks.
- Fixed: Tasks not found in the diagram are not all being identified.
- Fixed: Diagram is displaying duplicate tasks in the '[Calls -> list of tasks'.
- Fixed: Directory entries are incorrect if there is one or more ">" or "<" in the object name.
- Fixed: Ai-Analysis using a local model (e.g. llama3.1) is not working.
- Open Issue: The background color may not be correct if using the Firefox browser in light mode if the system default is dark mode.
- Open Issue: The Map view Project/Profile/Task/Scene names with icons are not displaying correctly if using highlighting (underline, etc.).
- Open Issue: Projects, Profiles and Tasks with a comma in the name may not display correctly.

## [5.1.2]

- Added: 'Up Two Levels' has been added to the Map view.
- Changed: Map view performance has been improved when using the directory hyperlinks for single names that are already in the view.  It goes directly to the single named item in the current view rather than remapping the nnmed item and redrawing the view.
- Changed: To remap a single named item in the Map view, the single named item must be selected from the GUI and the 'Map' view button must be reselected.  Otherwise, it will simply display the single named item in the existing Map view.
- Fixed: Project/Profile/Task/Scene name highlighting is incomplete in the Map view.
- Fixed: Project/Profile/Task/Scene names with special characters in it are not displaying correctly.
- Fixed: 'Go to bottom' hotlink in Map view goes beyond the last entry in the list.
- Fixed: If no XML is loaded, the single name pulldowns are still incorrectly loaded with the prior XML names.
- Fixed: No indication is given that the search string was not found in the Map and Diagram views.
- Fixed: Unnamed Profiles have a blank name rather than 'None or unnamed!' as the name in certain situations.

## [5.1.1]

- Added: "Go to bottom" has been added to the Map view to jump to the bottom of the view.
- Added: "Go to top" has been added to Profile, Task and Scene elements in the browser.
- Changed: Don't display the message, "You can find 'MapTasker.html' in the current folder." if displaying the Map or Diagram views from the GUI.
- Fixed: Ai Analysis response window size and location are not being restored on recursive calls.
- Fixed: Horizontal scrollbars are not being shown in the GUI views.
- Fixed: Fetching xml from the Android device is not resetting the single Project/Profile/Task to none.
- Fixed: Program error if displaying the directory in the Map view.
- Fixed: Directory names in the Map view that exceeded 40 characters are not displaying correctly.  Now they are truncated with "..." at end.
- Fixed: If working with a Scene-only XML file, specifying a single named item results in program exiting rather than issuing an error message.

## [5.1.0]

- Added: Search string support added to Map , Diagram and Ai Analysis views.
- Added: 'Toggle Word Wrap' added to Map, Diagram and Ai Analysis views.
- Added: Copy and paste support added to Map, Diagram and Ai Analysis views.
- Added: The Diagram view now respects the 'View Limit'
- Added: The 'View Limit' has additional increments of 15000 and 25000.
- Changed: The GUI 'Map Limit' has been renamed to 'View Limit'.
- Changed: The Ai Analysis default prompt has been changed from "how could this be improved:" to "suggest improvoments for performance and readability:"
- Fixed: The Diagram view is printing '13' (old debug code).
- Fixed: Program error if a window is not defined.
- Fixed: view windows resizing are not being restored.
- Fixed: Hotlink colors are not correct in light mode.
- Fixed: Recursive Diagram views results in duplicated connections.
- Issue: A program error can occur in the external package 'Cria' when performing an Ai Analysis with a local (e.g. llama) model.

## [5.0.5]

- Added: "Go to top" hotlinks have been added to the 'Map' view to jump to the top of the map.
- Fixed: The 'Map' view directory entries have the wrong background color.
- Fixed: Project, Profile, Task and Scene name highlighting is not working in the 'Map' view.
- Fixed: Minor formatting changes in the 'Map' view.

## [5.0.3 and 5.0.4]

- Added: A message is printed indicating that the error "IMKClient Stall detected, *please Report*..." can be ignored on 'Map' and 'Diagram' views that take a long time to process.
- Changed: The background color for the directory has been darkened for dark mode and lightened in light mode to improve readability.
- Fixed: 'Diagram' view diagrams the entire project if a single Task is selected, rater than the Task's owning Profile.
- Fixed: 'Timeout=' Task action parameter is improperly formatted in the 'Map' view.
- Fixed: Notify Task action is incorrectly showing a zero value in the output.
- Fixed: 'Map' view gets a program error if a particular color is missing.
- Fixed: Saved color changes are being ignored if restoring the settings in the GUI.
- Fixed: The background color is not recognized in the 'Map' view.
- Fixed: 'Program error in 'Map' view.

## [5.0.2]

- Added: Display a message if 'Diagram' view is being processed in the background.
- Added: 'Map' view now has a "Up One Level" directory hotlink if a single Profile or Task is being mapped.
- Added: A progress bar has been added to the GUI to show the progress of the 'Diagram' view.
- Added: Tasker beta 6.14 'Remote Execution' Task action and associated preferences are now recognized.
- Changed: The 'Map' view directory hotlink for a Task unassociated with a Profile will now point up to the owning Project rather than the entire configuration.
- Changed: The GUI progress batr now shows a smoother color scheme transition (red through to green).
- Fixed: If Profile has no name, say so in the 'Map' view output.
- Fixed: The GUI list of Tasks incorrectly showed some Tasks names that were not proceeded by "Task:".
- Fixed: Program error if changing the indentation amount and then display the 'Map' or 'Diagram' view.
- Fixed: Moving a 'Map', 'Diagram' or 'Tree' view window will not change the window position on conseuqtive displays of the same view.
- Fixed: 'Map' view does not work if colors have not yet been defined.
- Fixed: Task action 'Browse URL' is missing the detailed parameters.
- Fixed: Performing a 'ReRun' proeeded by a 'Map' view with a single Task selected results in output not related to the single Task.
- Fixed: 'Map' view output spacing for Projects and Scenes is incorrect.

## [5.0.1]

- Added: 'Map' view 'Map Limit' pull-down added to the GUI to control the processing time when generating the map.
- Added: The new 'llama3.1' Ai model added to the 'Analysis' tab.
- Added: A progress bar has been added to show the progress of the 'Map' view.
- Fixed: Invalid spacing appears in the Map view directory list.
- Fixed: Spacing for parameters with "Pretty" enabled is slightly off in ther Map view.

## [5.0.0]

- Added: Support for Tasker Release 6.3.12.
- Added: 'Intensity Pattern' is now included with the "Notify" Task action.
- Added: Open Ai model 'cpt-40-mini' added to the 'Analysis' tab.
- Added: Direcory (hotlinks) are now supported in the 'Map' view within the GUI.
- Changed: Nothing has changed.
- Fixed: The 'Map' and 'Tree' views are not including Tasks that are not part of a Profile.
- Fixed: 'Map' view global variables are not displaying properly.
- Fixed: A caveat is not displaying properly.

## [4.2.2]

- Added: Display a "Please stand by" message while building the 'Map' view from the GUI.
- Added: Name highlighting (bold, underline, italicize and highlight) are now supported in the 'Map' view.
- Changed: Removed non-user modifiable arguments from the user settings file, 'MapTasker_Settings.toml'.
- Fixed: 'Update to Latest Version' gives a program error even though it still works.
- Fixed: Formatting for 'Configutration Parameter(s):' in the 'Map' view is incorrect.
- Fixed: If 'Get Local XML' is selected in the GUI and returns bad XML, the 'Current File' is not updated to 'None'.
- Fixed: If 'Tree' view is selected and there is no XML loaded, the error message says the 'Map is not possible rather than the 'View is not possible'.

## [4.2.1]

- Added: Color added to the Map View in the GUI.
- Fixed: The Map View formatting has been corrected.
- Fixed: Program terminates if doing a second "Map" view request with a single name selected.
- Fixed: Program abend if no XML file loaded when trying to get display a Map/Diagram/Tree view after having selected a single name.
- Fixed: The GUI 'Views' are incorrect if switching from one single name to another.
- Fixed: Parameters and arguments with embedded '<' and '>' characters were not appearing in the output.

## [4.1.1]

- Added: 'Cancel Entry' button added to 'Select XML From Android Device' prompt in GUI.
- Added: 'View' buttons now display the configuration 'Map', 'Diagram' or 'Tree' right within the GUI.
- Added: Hyperlinks have been added to the help text in the GUI.
- Changed: Added verticle scrollbars to the Analysis and Diagram Views output windows.
- Fixed: Help information in text box dopes not get removed once displayed.
- Fixed: Some window positions not saved under certain situations.
- Fixed: Unreference global variable values are not displaying properly.
- Fixed: Project global variables are not displaying if the display level is 5.
- Fixed: Program errors if doing a "Rerun" with "Debug" on.

## [4.1.0]

- Added: If 'Debug' is on and trying to get new XML data, then display the message that 'backup.xml' is being used.
- Added: Three new analysis models have been added: "qwen", "codellama" and "aya".
- Changed: Reemoved the requirement to manually install Ollama since it is now included.
- Changed: Simplified the ReRun option for Windows users.
- Fixed: GUI labels are difficult to see if in "light" appearance mode.
- Fixed: The saved GUI 'appearance' mode is not being restored on reentry to the GUI.
- Fixed: If no Project in XML, then the outline is blank.
- Fixed: A bad XML file was not properly being reported in the GUI.
- Fixed: Program error when getting XML from Android device.
- Fixed: GUI program error if no file has yet to be selected.

## [4.0.12] 18-June-2024

- Changed: Moved the 'Get XML from Android Device' button to avoid overlap with font selection button.
- Fixed: Restored font is not showing as the default font in the GUI.
- Fixed: The Ai Analysis window incorrectly hangs around from the previous analysis while doing a new analysis.
- Fixed: If displaying a single task only, the total number of Profiles displayed included the total for all Profiles under the Project in which the Task is contained, rather than just 1.
- Fixed: The 'Set Prompt' Ai Analysis dialog window is not always selectable.
- Fixed: "Reset Settings' does not reset the font to the default monospace Courier font.
- Fixed: Program error if trying to run analysis with no XML data loaded.
- Fixed: 'Run Analysis' button turns pink even if there is no model selected.
- Fixed: Select Project/Profile/Task names not working properly if there are none to select.

## [4.0.10/4.0.11]

- Fixed: Updating the program from the GUI doesn't reload the program with the new version just updated.
- Fixed: Color picker causes a program error.

## [4.0.9] 11-June-2024

- Added: Save the Treeview and Color Picker window positions and sizes, and restore the last-used position and size for each.
- Added: Support for Tasker version 6.3.10-rc.
- Added: Missing 'Device Admin/Owner' actions: Uninstall App, Perrmission, Clear Device Owner.
- Changed: Major overhaul of the README file.
- Fixed: Program error if Task action parameter is out of range (e.g. not yet defined).
- Fixed: Color picker does not show up after having done a 'ReRun'.
- Fixed: Tree view under Windows is not getting the proper arrow icons.

## [4.0.8]

- Added: The Ai Analysis models 'mistrel', 'codegemma', 'gemma', 'deepseek-coder' and 'phi3' have been added.
- Added: The model name and object name are now displayed with the Ai analysis response.
- Added: The message that the analysis is running in the background has been animated for awareness.
- Added: The pulldown menus for selecting a single object now includes "None" so that it can be used to clear the selection without having to resort to a 'Reset Settings' in the GUI.
- Added: Three additional Tasker preferences have been mapped and one has been corrected.
- Changed: Ai models are now listed alphabetically, with the last-used model listed first.  The default of 'None (llama)' has been removed.
- Fixed: The 'ReRun' command caused the error message: 'Task policy set failed...'.
- Fixed: If doing a single object (Project/Profile/Task)and doing Tasker Preferences, Preferences were empty.  Display appropriate message in output.
- Fixed: Getting XML file from Android device did not reset the local file pointer, causing a conflict between the two.

## [4.0.7]

- Added: An entire project can now be analyzed via the 'Analyze' tab.
- Changed: Redefined the default window size for the GUI so that it is large enough for asll of the fields to show appropriately.
- Fixed: Analysis API key is showing 'Set' when, in fact, it is unset.
- Fixed: Realigned the GUI fields for getting the file from the Android device.
- Fixed: Incorrectly defining Android device attributes when selecting "Get XML from Android Device" and then cancelling this option in the GUI.
- Fixed: If displaying the outline and processing only a single Profile, then the outline is showing all Projects rather than just the Project this Profile is a part of.
- Fixed: In certain circumstances, if doing a single Profile or Task, the containing Project/Profile would also be saved in the settings.

## [4.0.6]

- Added: Save and restore the Analysis Response window.
- Added: GUI messages with "True/False/On/Off" settings now display in appropriate colors.
- Changed: The 'List XML Files' button color is now the same as the 'Click Here to Set XML Details' button.
- Changed: Position the 'Analysis is running...' message over the GUI window.
- Fixed: Corrected the alignment of the GUI buttons for getting the XML from the Android device.
- Fixed: The GUI startup time is improved slightly.
- Fixed: The 'Report Issue' button is missing.
- Fixed: Text message window is not using the current font.

## [4.0.3/4.0.4/4.0.5]

- Added: Restore the GUI window to the last-used position and size.
- Added: The ability to change the prompt used for the Profile/Task analysis has been added.
- Added: Going forward, if a new release is available, the GUI will provide a "What's New" button.  You will be able to see what is changing before applying the changes.
- Added: Ai Analysis now supports the new OpenAI "gpt-4o" model.
- Added: Support for Tasker 6.3.8 Beta code.
- Changed: Widened the GUI window slightly for better readability.
- Changed: 'Specific Name' items are now available via a pulldown menu.  It is no longer necessary to enter the names through a text input box.
- Changed: The settings file now sorts the colors to use by name.
- Fixed: The 'Reset' button in the GUI is not resetting the analysis model.
- Fixed: If 'Get Local XML' is selected in the GUI, the analyze Profile and Task list is not updated.
- Fixed: The 'Specific Name' tab has the label for the 'Colors' tab in the GUI.
- Fixed: Under certain situations, the GUI will use the old data even after getting a new XML file.
- Fixed: Occasion program abnormal termination when selecting a specific Project or Profile that has a Scene.
- Fixed: The program occasionally terminates abnormally when trying to save the settings file.

## [4.0.2]

- Added: Center the GUI window on the screen.
- Added: A popup window will display when analysis is running in the background.
- Fixed: The XML obtained via the 'Get Local XML' button is not saved in the settings.
- Fixed: A restored XML file name based on saved settings is not being displayed in the GUI.
- Fixed: Properly terminate the program if the GUI window is closed.
- Fixed: The GUI's 'Appearance Mode', 'Tree View' and 'Reset' buttons disappeared.

## [4.0/4.0.1]

- Added: Ai analysis support for Profiles and Tasks: both ChatGPT (server-based) and (O)llama (local-based).
- Added: Display the current file in GUI.
- Added: A new 'Get Local XML' button has been added to enable the GUI to get the local XML file and validate it for analysis.
- Changed: GUI color settings are now displayed in their colors on the startup of the GUI.
- Changed: GUI warning messages are now displayed in orange rather than red.
- Fixed: The program gets runtime errors if the settings saved file is corrupted.
- Fixed: The settings are not properly saved upon exit from the GUI.
- Fixed: Removed error message 'Program canceled by the user (killed GUI)' if the 'Exit' button is selected.
- Fixed: If the Android file location is specified on startup and the file is found on the local drive from the previous run, then use it and don't prompt again for it.
- Fixed: The GUI message window was not fully expanded.

## [3.2.2]

- Added: Add date and time to the output heading.
- Added: Add 'Display Prettier Output' to the GUI Help text.
- Changed: Scene elements with no geometry will no longer display 'n/a' for geometry values.
- Changed: If using the '-pretty' runtime option, trailing commas are removed since the arguments are already separated.
- Changed: Scene element names placed before element type for clarity.
- Changed: Moved the location of the 'Upgrade To Next Version' button in the GUI so that it doesn't overlap with another button.
- Fixed: Using the '-pretty' runtime option causes the string "Structure Output (JSON, etc)" to be incorrectly broken at the comma.
- Fixed: The '-pretty' option is not properly formatting Task action values or Profile conditions in the output.
- Fixed: Scene 'Properties" elements are being displayed with an invalid name.

## [3.2.1]

- Added: A new 'display detail level' of 5 (the new default) has been added to include Scene element UI and properties details.
- Added: Display the change log for the current release at the end of the Help information in the GUI.
- Added: A new runtime option '-pretty' will format the output such that each Project/Profile details, Task action's parameters, Scene element details, etc. are aligned on a separate line.
- Fixed: If a Scene has a sub-scene layout, output the details of the sub-scene.
- Fixed: Task action 'Stop' with Task name has an extra comma in the output.
- Fixed: When displaying a single Project, the Project line details are not displayed (e.g. Launcher Task).
- Fixed: If the XML file has been obtained from the Android device, don't prompt for the file again if doing a specific Project/Profile/Task.
- Fixed: On startup of the GUI, the information about the Android device and single Project/Profile/Task name are not displayed if restored from backup settings.
- Fixed: Scene sub-elements (e.g. Layout)are missing from the output.
- Fixed: If only doing a single Project with the '-directory' runtime option, some scene hotlinks in the directory do not work.
- Fixed: Twisty setting is not being restored on a rerun.
- Changed: Scene elements are now displayed as 'Element of type xxxx' to more clearly identify the element type (e.g. type: Text, Rect, Button, Image, etc.).
- Changed: Output Task action fields and values changed from "field:value" to "field=value" fo

## [3.1.8] 08-April-2024

- Added: A ruler line has been added to the output as a break to indicate the end of a Project.
- Added: A new button, 'Clear Messages', has been added to the GUI to empty the text message box.
- Added: Display all of the settings that are initially restored with the start of the GUI.
- Added: If the GUI is started along with the '-reset' option then display this in the message box.
- Fixed: The GUI is displaying 'Settings Restored' twice upon entry.
- Fixed: 'SyntaxWarning: invalid escape sequence' error messages if running with Python 3.12 or greater.
- Fixed: The GUI 'Restore Settings' now also includes the display of the colors restored.
- Changed: GUI messages were revamped to provide better details.
- Changed: Keep message history in GUI and retain each message's color.

## [3.1.7] 28-March-2024

- Fixed: Eliminate reading the XML file twice when running from the GUI.
- Fixed: The GUI gets a 'Backup File not found' error message if displaying the treeview after having restored the settings.

## [3.1.6] 25-March-2024

- Fixed: When selecting a single item to display in the GUI, the display of that name has additional invalid information.
- Fixed: Selecting bad XML from the GUI causes immediate exit instead of returning to the GUI.
- Added: Display a Tree View of the XML from within the GUI, via the new 'Tree View' button.
- Changed: Gui 'Run' command has been renamed 'Run and Exit'.
- Changed: Clear message history in GUI when an error occurs.

## [3.1.5] 17-March-2024

- Fixed: The wrong changelog information is being displayed with a new version update in the GUI.
- Fixed: The GUI 'Upgrade to Latest Version' button is sitting on top of the 'Report Issue' button.
- Fixed: The GUI 'Just Display Everything' button is missing.
- Fixed: The alignment of the Android XML fields in the GUI is off.
- Changed: The 'Get XML Help' button in the GUI is now called 'Get Android Help' for clarity.
- Added: The GUI message window now displays the message history.

## [3.1.4] 08-March-2024 (includes 3.1.3 changes)

- Fixed: File error displayed after getting the list of Android files in the GUI.
- Fixed: The Task name does not appear if the XML consists solely of a single Task.
- Fixed: If the 'Get XML File' IP address is a valid address on the local network but not accepting access via the port given, specify this in the error message.
- Changed: Don't reread the Android XML file if "Run" has been selected since we've already read the file to validate the XML.
- Changed: Improved the GUI help information for using the 'List XML File' button/feature.
- Added: The GUI has a new button to 'Report Issue', which can be used for issues and new feature requests.
- Added: The GUI 'Color" tab now has a button to reset all Tasker objects to their default colors.

## [3.1.2] 04-March-2024

- Fixed: Icons in Profile and Task names are invalid due to bad encoding.
- Fixed: GUI "?" left in the window after "Get Backup from Android Device" completed.
- Fixed: The automatic check for updates was not working due to a problem with the 24-hour check.
- Changed: All references to "Backup" in the GUI have been changed to "XML".

## [3.1.1] 01-March-2024

- Fixed: The GUI "Cancel" backup button overlaps the input field for the Android file location.
- Fixed: In the GUI, the display of the Android file location is sitting on top of the "Restore" button if the file location is long.
- Fixed: Removed a leftover debug print statement in the diagram code.
- Fixed: If the XML contains only a single Task, Profile or Scene and no Project, then nothing would be output.
- Fixed: Properly handle invalid XML files that don't parse.
- Fixed: Possible loop processing XML code with bad encoding.
- Added: New runtime argument "-file" is used to point to a specific XML file to use (e.g. -file ~/Downloads/backup.xml) instead of being prompted to select the file.
- Added: New ability in GUI to list the Android XML files for selection and select the XML file from the list, rather than manually enter the file location.  See README for details.
- Added: The XML file is validated in the GUI before the 'Run' button is selected.

## [3.1.0] 22-February-2024

- Fixed: Program error in runcli.py
- Fixed: The GUI was not displaying the fact that a single object (Project/Profile/Task) is being displayed on entry based on the settings restored.
- Fixed: Missing comma in the last argument of the Task action details.
- Fixed: Various changes in support of MS Windows.
- Fixed: GUI displayed "None" for the "Display Detail Level" setting when selecting "Just Display Everything!" rather than the actual set level.
- Fixed: Removed a duplicate Task action code.
- Fixed: Unreferenced global variables were not being displayed.
- Fixed: Cancel the "Get backup from Android device" didn't cancel the process.
- Added: MapTasker has now been tested and verified to run on Microsoft Windows 11.
- Added: Support for Tasker 6.3.3-beta's "Get Network Data Usage" and the rename of "List File/Folder Properties" to "Get File/Folder Properties".

## [3.0.5]

- Fixed: The table colors for Global Variables are wrong if not also displaying the Directory.
- Fixed: The absence of the runtime option "-GUI" was overridden by the restored savings and required the "-reset" option to stop the GUI from starting. Now, the presence or absence of this "GUI" setting in the runtime options overrides the saved settings.
- Fixed: Tasker grand totals at the end now reflect the number of Projects/Profiles/Tasks/Scenes displayed and not the total in the Tasker configuration.
- Fixed: Corrected README file to reference the older MapTasker as version 2.6.3 rather than 3.6.3.
- Changed: Eliminated list style in output to ensure proper alignment of Projects/Profiles/Tasks/Scenes.
- Changed: Eliminated bullet color runtime option (-cBullet color_name) since there are no longer any bullets.
- Changed:  Task entry and exit indicator from "<<<" to "⬅".
- Changed: When identifying a Project in the output, such as "Project project_name, put a single quote around the name (e.g. Project 'project_name') for clarity.
- Added: Disabled Profiles and Tasks now display as [⛔ DISABLED

## [3.0.3]

- Fixed: Eliminated redundant and unused code.
- Fixed: A program error occurs with the use of a unique runtime combination of options.
- Fixed: The program gets an error if debug is on and the file "backup.xml" is not found.
- Fixed: Setting the runtime option of "-detail 0" via the command line is ignored.
- Added: Support for Tasker 3.6.1 with the following new Task actions: Device Admin, Array Compare, List File/Folder Properties.
- Added: Support for Tasker 3.6.1 with "Used Memory" as a Test Tasker task action option.
- Added: Recognize a few additional Tasker preferences.
- Added: The runtime argument "-font help" will print the list of valid monospace fonts on your system.

## [3.0.2]

- Fixed: Program error if the settings file is not found.

## [3.0.1]

- Changed: The minimum version of Python is now 3.11.7 for TOML file settings support.
- Changed: README updated to reflect the new minimum version of Python and newer sample screenshots.
- Changed: Updated prerequisite versions for "customtkinter", "ctkcolorpicker" and "pillow".  Eliminated "packaging" prerequisite.
- Changed: The default dark background color has been changed to a dark gray/brown color.
- Changed: Eliminated the "-save" and "-restore" runtime options.  These are replaced by the "-reset" runtime option.
- Changed: Force plug-in configuration parameters to appear on separate output lines.
- Fixed: Unable to get the program version ('-version') if the last run was with the GUI.
- Fixed: The Task action arguments were being displayed out of order.
- Fixed: Not handling Task anchors properly.
- Fixed: Removed "save" and "restore" from the display of runtime options, which caused error messages to appear in the output.
- Added: The settings are now saved in the TOML format and can be user-viewed and/or edited.  If a saved file is still in the old format, it will automatically be converted.
- Added: new "tomli_w" prerequisite for TOML file settings support.
- Added: "Time Zone" to the Task action "Parse/Format DateTime".
- Added: "Configuration Parameters" for Plugin actions.
- Added: "AutoCast" plug-in recognition.
- Added: If fetching the backup XML file from the Android device, display the 'android_...' settings in the GUI.

## [2.6.3]

- Changed: The runtime options to fetch the backup file from the Android device have changed.
      See the 'Added" section.  '-backup' is no longer supported.
      If the old options exist in the saved runtime file, they will automatically be converted to the new runtime option format.
- Changed: The runtime option '-appearance' can no longer be abbreviated as '-a'.
- Changed: The old format for the saved settings that date back to the year 2022 is no longer supported.
- Changed: Updated README to reflect new '-android_...' runtime options.
- Changed: The GUI message box now only displays the current message and not any previous messages.
- Fixed: README had a bad reference to the supplemental information regarding Tkinter.
- Fixed: If the backup file is not found on the Android device via the GUI, the program ends rather than catching the error in the GUI.
- Fixed: Gracefully handle invalid command line options.
- Added: The runtime options for fetching the backup file directly from the Android device are 'android_ipaddr', 'android_port', and 'android_file'.
- Added: Added additional Task properties.

## [2.6.2]

- Changed: Eliminated PSUTIL dependency.
- Changed: On entry to the GUI, the individual items that have been automatically restored are no longer displayed in the text message window.
- Fixed: The "Rerun" command under certain conditions would never end.
- Fixed: Normal exits were not displaying the message that all had ended normally.
- Fixed: The saved runtime arguments were restored twice if using the GUI.
- Added: Recognize AutoLocation plugin (Geofences) for Task actions and Profile Events.

## [2.6.1]

- Changed: The runtime options are now automatically saved on exit and restored on entry.  The runtime options '-save' and '-restore' have been removed.
- Changed: The "Rerun" GUI option has been modified to use PSUTIL to avoid a program error.
- Changed: The migration functionality to support the older internal backup file format has been removed.
- Fixed: "Rerun" causes program error.
- Fixed: Program error writing diagram file (MapTasker_Map.txt) if on Python version 3.10.
- Fixed: Fixed bug in the program when opening output file if on Python version 3.10.
- Fixed: Program error if the window is closed before entering any input into the GUI.
- Added: New "-reset" runtime option to reset the program to the default settings rather than restore and use saved settings.
- Added: Added: Performance enhanced for outline/diagram

## [2.5.4]

- Changed: Anonymous Profiles and Tasks in the outline now have a unique number associated with each.
- Changed: Better arrow spacing in the outline diagram map.
- Changed: Moved the position of the down arrows in the diagram closer to the beginning for legibility.
- Fixed: The GUI allows invalid port and file location input on the "Get Backup from Android Device" input field.
- Fixed: The outline diagram is missing some links between called and caller Tasks.
- Added: Added: The GUI messages for getting the backup file from the Android device are clearer.
- Added: Add a header under grand totals at the end of the output.

## [2.5.3] 2023-Dec-08

- Changed: Anonymous Profiles in the outline now have a unique number associated with each.
- Fixed: The total counts and end of the output are wrong if doing a single Profile or Task.
- Fixed: The outline displayed Tasks under "No Profile" which were, in fact, under a profile.
- Fixed: In the GUI, selecting everything did not set the detail display level to 4.
- Fixed: The GUI did not properly position the "Fetch Backup from Android Device" input field.
- Fixed: The GUI was not picking up the correct default font in the font option pulldown.
- Added: The GUI messages for getting the backup file from the Android device are clearer.
- Added: Add a header under grand totals at the end of the output.

## [2.5.2] 2023-Dec-04

- Changed: Task action "continue limit" increased from 50 to 75 lines before it is cut off.
- Changed: Slight performance optimizations.
- Changed: Renamed depricate.py to deprecate.py
- Fix: Cleaned up this file for legibility.
- Fix: The program abends if the GUI window is closed.
- Added: The task action code was added to recognize the Termux plugin.

## [2.5.1] 2023-Nov-21

- Added: GUI 'Fetch Backup from Android Device' Help button and information added.
- Added: GUI improved color settings display of changes.
- Added: GUI single item (Project/Profile/Task) selection status is displayed.
- Changed: Default display detail level (runtime option 'detail) is now 4.  I was 3.
- Fixed: Stay in GUI if the cancel button is selected when prompted for the backup file.
- Fixed: GUI messages are not being cleared before displaying new error messages.
- Fixed: GUI labels that are reused were displaying previous text in the background.
- Fixed: Cleaned up the spelling of this file.

## [2.5.0] 2023-Nov-15

- Changed: Rewrite code to improve performance and maintainability.
- Changed: Renamed the files: "deprecated" > "depricate", "getputarg" > "getputer", "variables" > "globalvr", "shellsort" > "shelsort" for OS compatibility.
- Changed: A "rerun" now clears all settings after the run to avoid ever-growing memory demand.
- Fixed: The GUI now pings the IP address of the Android device to make sure it is reachable before fetching the backup from it.
- Fixed; The GUI "Get Backup FFrom Android Device" button is now properly formatted after usage.
- Fixed: Task action "Stream" missing the colon to offset the name from its setting/value.
- Fixed: Configuration diagram not accounting for icons in names, causing miss-alignment.
- Fixed: Program error if displaying a single Project/Profile/Task.
- Fixed: Outline displays everything when doing only a single Project/Profile/Task.
- Fixed: GUI Appearance Mode not being applied to the output.
- Fixed: Inadvertently displaying "Project:" twice when displaying a single Project only.
- Fixed: Clean up memory if doing a rerun.
- Fixed: Rerun not working properly if displaying only a single Project/Profile/Task.
- Fixed: "everything" runtime option not setting the display detail level to 4.

## [2.4.6] 2023-11-02

- Changed: GUI prompt to fetch backup from Android device now prompts with the default value for easy entry/modification.
- Added: Caller-to-Called Tasks are now individually identified in the Configuration diagram/map.
- Fixed: Configuration diagram/map "No Profiles" box includes Tasks that do have Profiles.

## [2.4.5] 2023-10-29

- Added: Code optimizations.
- Added: Missing Task plugin action AutoWear Dialog.
- Added: "Called Tasks" and "Called By Tasks" added to the configuration map (file MapTasker_Map.txt).
- Fixed: For Kid apps, remove the colon from "Kid app:" since it makes it look like the app is missing.
- Fixed: Set a timeout of 10 seconds for obtaining backup from the Android device.
- Fixed: Various plugin Task actions were not getting the correct plugin name although values were correct.
- Fixed: Added missing dependency on packaging by 'Customtkinter'.

## [2.4.3] 2023-10-13

- Added: When changing a specific color in the GUI, a sample of the new color will be displayed.
- Added: Configuration "map" now includes Tasks not associated with any Profile, entry/exit Task flags.
- Added: New display level of "4" to include the display of a Project's and all unreferenced global variables.
- Changed: Restructured code for performance.
- Changed: Displaying a single Task no longer forces display detail of 3.
- Fixed: GUI option "Just display everything" was not properly setting the Display Detail Level.##‘.
- Fixed: Program error if displaying a single Task.

## [2.4.1] 2023-09-30

      -  Added: Configuration Map, saved as "MapTasker_map.txt", added to Configuration Outline
      -  Added: Further code optimizations.
      -  Added: Outline now includes Task pointers to other Tasks (via Perform Task action).
      -  Added: Outline now includes Tasks in Project not associated with any Profile.
      -  Added: Task icon information is now included in the output.
      -  Changed: Profile/Task "Properties" added "...." for better visibility.
      -  Changed: Updated text in README and help for the "-outline" runtime option.
      -  Changed: Runtime option "twisty" is only allowed if "detail=3" (full detail).
      -  Fixed: Tasks with "No Profile", at the end of the output, are now properly formatted.
      -  Fixed: Properly remove trailing commas from Task actions.
      -  Fixed: Profile and Project properties are displaying in the wrong color.
      -  Fixed: Display detail level of 0 (zero) not showing properly or with enough detail.
      -  Fixed: GUI Restore not displaying the correct message for "Display Detail Level".
      -  Fixed: When displaying a single Project/Profile/Task, the grand-total counts did not reflect the single item.

## [2.3.6] 2023-09-18

      - Added: program optimizations for performance and memory usage.
      - Added: Further code and html optimizations.
      - Changed: Switch to inline CSS for colors and font, saving on output HTML size and better formatting.
      - Changed: changed the color of negative (False, None) values for runtime settings to make it easier to identify.
      - Changed: If only displaying a single Task, display the Profile's Scenes as well.
      - Changed: Bullets changed to diamonds.
      - Fixed: Selecting a single Project/Profile/Task name in GUI doesn't display the selection in the message box.
      - Fixed: Displaying any text in the GUI textbox after restoring settings does not get displayed.
      - Fixed: Incorrectly displaying directory for items not in the output.
      - Fixed: The color for labels was not correctly set.
      - Fixed: GUI single name error message displaying in green rather than red.
      - Fixed: Task's extra properties (priority, collision, etc.) not displaying correctly.

## [2.3.0 -2.3.5] 2023-09-06

      - Added: Some pazazz for user experience to the '-version' runtime option.
      - Added: New runtime option '-outline' to display Configuration Outline at the end of the output.
      - Added: New GUI Option: Just Display Everything- no need to click each display option checkbox.
      - Added: GUI text/info box font now reflects the font selected in the GUI.
      - Added: Added 'Display Help' button to GUI. Clicking displays help text.
      - Changed: Output error messages in red.
      - Changed: Rearrange GUI buttons to keep all display options in column 1.
      - Changed: Runtime options in output are now aligned for improved readability.
      - Fixed: Runtime arguments of a single letter (e.g. '-e' instead of '-everything') not being recognized.
      - Fixed: Outputing "MapTasker Version" twice in the heading.
      - Fixed: Specifying a specific Project/Profile/Task in GUI causes an error in the saved settings file.
      - Fixed: Program error when selecting color within GUI.
      - Fixed: Fetching backup.xml from the Android device could incorrectly fail with the 'Invalid URL!' error message.
      - Fixed: Runtime option '-everything' was not including Tasker's preferences

## [2.2.1] 2023-08-30

      - Fixed: The condition "matches regex" and "doesn't match regex" are incorrectly reversed.
      - Fixed: If conditions missing compound conditions like AND and OR.
      - Fixed: Profile compound condition format with "and" not consistent with If component "and" statements.
      - Fixed: Enlarged the images in the README file.
      - Changed: Further optimized the code

## [2.2.0] 2023-07-27

      - Added: New '-font' runtime argument to specify a specific (monospace) font to use for the map display. The default is 'Courier'.
      - Added: New '-runtime' runtime argument to display all of the runtime arguments and their settings at the beginning of the output.
      - Added: GUI updated to include help information about the Debug tab.
      - Changed: Updated GUI for the 'Font To Use' selection option and 'Display Runtime Settings' checkbox (under the 'Debug' tab).
      - Changed: Optimized code.
      - Changed: Updated README file with new runtime options.
      - Changed: Runtime argument to display Tasker Preferences option -p remove.  Now only -preferences
      - Fixed: Fixed missing 'restore' runtime option.
      - Fixed: Program error if restoring runtime settings and no indentation is specified.
      - Fixed: Program error when the runtime argument does not exist in the saved settings file.
      - Fixed: GUI 'Cancel' button now works.  Remove the message saying that it doesn't work.
      - Fixed: Output contains the unneeded extra commas.
      - Fixed: Runtime option -e (everything) not including Tasker Preferences.

## [2.1.2] 2023-07-18

      - Added: New '-indent' runtime argument to control the amount of indentation of if/then/else Task actions. The default is 4 spaces.
      - Fixed: Properties not showing the variable name.
      - Fixed: Project Properties and Taskernet information was not displaying for a specific Project.
      - Fixed: Don't display Task Properties if displaying Tasks that are not in any Profile.
      - Fixed: Underlining names caused extra blanks to be added to the names.
      - Fixed: Added appropriate spaces to deal with TaskerNet description formatting.
      - Fixed: Not picking up Tap Tap plugin Profile event.
      - Fixed: Added missing "AutoWear", "Locus Map" and "KWGT Custom Widget Maker" plugin Actions.
      - Fixed: Remove empty parameters from appearing in Task actions and extra spaces before commas
      - Changed: Continued Task actions are now indented properly underneath If/Else conditions
      - Changed: Optimized code

## [2.1.1] 2023-07-09

      - Fixed: Minor cosmetic issues with sample output and README file.
      - Fixed: Removed extraneous print color.

## [2.1.0] 2023-07-09

      - Added: Display Project/Profile/Task "properties" if the display detail level is 3.
      - Added: New runtime argument '-names {bold, highlight, underline, italicize}' to make all Project/Profile/Task/Scene 'names' display bold, highlighted, underlined and/or italicized.
      - Added: New runtime argument '-cHeading' to assign a color to the output heading lines.
      - Added: New runtime argument '-appearance' {system, light, dark} to switch between color themes.
      - Added: GUI: If a checkbox is selected or deselected, display the change in the message window.
      - Added: GUI: Colors for 'highlight' names, and for 'Heading'
      - Added: GUI: support new "names" bold/highlight/italicize/underline display options.
      - Changed: The GUI message box now shows all previous messages along with a new message at the bottom.
      - Fixed: If displaying the directory, some Project names incorrectly have an underscore embedded.
      - Fixed: Runtime argument "-restore" is not restoring all options correctly.
      - Fixed: Display level of 0 includes too much information.
      - Fixed: Cleaned up the README file.
      - Fixed: Default display detail level caused a program error.
      - Fixed: GUI color change resulted in two rather than a single notification.
      - Fixed: Output heading color was hard to see in light mode.
      - Fixed: Appearance mode not being saved correctly across sessions.
      - Fixed: Unit Test code was not handling program arguments properly.
      - Fixed: Setting the Action label color had no effect

## [2.0.10] 2023-07-24

      - Added: Support for new "Work Profile" Task Action and Profile State (Tasker version 6.2.9-rc)
      - Added: Added missing "Close After" sub-action on Pick Input Dialog Action
      - Changed: Display Grand Totals regardless of detail display level
      - Changed: If debug, redirect program abends (stack trace/error) to a debug log file
      - Fixed: Exit from GUI displays "Error" in printout when it is not an error.
      - Fixed: Under certain circumstances, fetching the backup XML file from the Android device not working
      - Fixed: Spurious indentation problems in output for Projects and Profiles
      - Fixed: Gracefully handle condition when Action/State/Event code not found
      - Fixed: The heading with Tasker and program versions was missing.

## [2.0.9] 2023-07-12

      -  Fixed: Rewrite directory code to eliminate problems with duplicate hyperlinks
      -  Fixed: "▶︎ Detail" still appearing if both -twisty and -directory options selected
      -  Fixed: When listing Tasks not called by any Profile, add a blank line first for legibility

## [2.0.8] 2023-07-11

      -  Fixed: Using both options "-directory" and "-twisty" together causes Task twisties to incorrectly appear as "▶︎ Detail"

## [2.0.7] 2023-07-09

      -  Added: New optional directory, via new runtime option "-directory"
      -  Added: a "Go to top" hotlink has been added to each Project line
      -  Fixed: Heading was displaying properly
      -  Changed: If the program crashes, provide a more graceful error message
      -  Changed: Removed the word "condition" from conditional statements...it is pretty obvious without stating it.

## [2.0.6] 2023-06-27

      -  Fixed: GUI use of the "Cancel" button is now properly recognized.
      -  Fixed: Fix Project/Scene indentation issue when using twisty
      -  Fixed: Removed extra blank link between twisties
      -  Fixed: Summary number of Tasks is for named Tasks only.
      -  Fixed: Summary count of unnamed Tasks included those under Scenes
      -  Changed: Total number of unnamed Tasks at the end (in red) removed since invalid
      -  Changed: Cleaned up the output HTML for slightly better reading/debugging

## [2.0.5] 2023-06-19

      - Fixed: Cancel button in GUI now recognized
      - Fixed: Project/Profile/Task name selection in GUI caused program error.
      - Fixed: GUI prompts twice for file if displaying by name

## [2.0.4] 2023-06-19

      - Added: summary totals of Profiles/Tasks under each Project if the display detail level is 3
      - Added: Profile "State" of Matter Light
      - Fixed: Event Sleeping missing arguments
      - Fixed: Don't allow Run from GUI if debug on and backup.xml file not found
      - Fixed: Help information regarding the display of a single Task and force the detail level to 3 (not 2)

## [2.0.3] 2023-06-13

      - Added: Task additional plug-ins mapped: AutoSpotify, AutoLaunch, AutoInput Actions V2, AutoBubbles, AutoContacts
      - Added: Add missing Scene elements
      - Added: Display Task's collision setting if detail = 3
      - Added: Display the backed-up device's screen resolution in the heading
      - Added: Support updated Profile HTTP Request
      - Added: new Task actions HTTP Response (deprecates HTTP GET/PUT/HEAD), Matter Light and Get Network Info (up to Tasker.6.2.5-beta)
      - Added: New Option "-backup" to fetch the Tasker backup file directly from the Android device.  Also available via the GUI via the new option: Get Backup from Device
      - Added: New option "-twisty" to display some details hidden by a twisty; click on twisty to display detail
      - Added: Display source backup file details right after the heading
      - Added: Display Scene and Scene's element's width and height, as well as that for sub-Scene (Layout) field
      - Fixed: catch possible program error processing Task actions if not mapped properly
      - Fixed: Gracefully handle new Tasker action items that have yet to be
      - Fixed: Show Scene "Display As" pull-down missing 'Activity, No Bar, No Status'
      - Fixed: In certain cases the Task's priority is not appearing.
      - Fixed: miscellaneous formatting and indentation errors
      - Changed: Restructured code for better performance
      - Changed: default display detail level is now 3 (highest level of detail)

## [1.3.5] 2023-05-15

      - Added: GUI "Cancel" button does not work.  Comment in the prompt notifies the user of this problem.
      - Added: If Profile has no name, then automatically display its condition(s)
      - Added: GUI single name for Project/Profile/Task now validates name entered before running.
      - Fixed: Program error in GUI when restoring settings.
      - Fixed: GUI restoring the settings does not display all settings restored in the message box.
      - Fixed: When a Task Action "continued" limit is reached, it was using the next Task's number
      - Fixed: Correct remaining garbage output HTML formatting
      - Fixed: Displaying Task action details for "detail" levels other than 3.

## [1.3.4] 2023-04-28

      - Added: GUI Rerun option to run multiple times until Exit (remains in GUI)
      - Fixed: If select "debug" mode in GUI, make sure backup.xml is in the current dir
      - Fixed: Error if end-of-file while migrating old settings file.  Now prints the error message that old settings are lost.
      - Fixed: Task Actions with "If x ~ <some trigger>" is not displaying the trigger due to  < >
      - Fixed: Action "Force Rotation" caused an indentation of all following Actions for the given Task
      - Changed: Moved Task's Priority into the same output line as Task, unless it has a Kid app
      - Changed: Moved all error handling to a common routine

## [1.3.3] 2023-04-17

      - Added: Additional error checking in the GUI
      - Fixed: Settings save/restore: replace pickle with JSON for security purposes.  The old settings file will be converted.
      - Fixed: Changed from the built-in XML tree to 'Defusxml' for improved security
      - Fixed: Changed exception handling to proper error types
      - Fixed: Corrected output formatting errors with improper fonts and character attributes
      - Changed: Code optimization for HTML colors and font

## [1.3.2] 2023-04-06: Maintenance Only

      - Added: Include the Map-Tasker version in the output title
      - Changed: default color for Profile conditions
      - Changed: eliminated colors in config.py...redundant
      - Fixed: Bypass extra Task information in the "Task not called by Profile" section
      - Fixed: cleaned up improperly formatted output due to spurious HTML tag
      - Fixed: Incorrectly formatted HTML
      - Fixed: Improved Taskernet description formatting
      - Fixed: Spacing on indented If/For segments
      - Added: More clearly identify Projects that have no Profiles

## [1.3.1] 2023-03-19

      - Added: The GUI Appearance mode change (Dark/Light) is now reflected in the output
      - Added: new color 'cTrailingComments' for comments at the end of the output
      - Changed: GUI message box widths extended for readability
      - Changed: Background color set to DarkBlue for better contrast
      - Fixed: Runtime color selection error for certain parameter formats
      - Fixed: Tasks not found in any Profile were not being listed at the end
      - Fixed: assigned comment color was not being used
      - Fixed: Action 'set clipboard' missing details
      - Fixed: List of Projects with no Tasks was repeating the same Project

## [1.3.0] 2023-03-11

      - Added: Support for unit testing (no user impact)
      - Added: Optionally display Tasker Preferences = runtime option '-preferences'
      - Changed: Optimized initialization code
      - Changed: Task(s) with no Profile will now be displayed under the Project it/they belong to
      - Fixed: Go To 'action' not showing the label to go to.

## [1.2.26] 2023-02-27

      - Added: New Task actions: Request Add Tile
      - Added: Support for new parameters in Set Quick Tile, Progress Dialog
      - Added: Display Project's/Task's Kid App info if 'details = 3'
      - Added: Display Profile/Task priority if details = 3
      - Added: Log now includes 'Error:' for program/functional errors

## [1.2.25] 2023-02-22

      - Fixed: Only the first (TAP/LONG TAP) Task in the Scene is displayed
      - Fixed: Scene Tasks for rectangle, web elements, and 'ITEM TAP' missing
      - Fixed: Corrected URL provided in 'Caveats' at the bottom of the output
      - Added: Display Scene elements

## [1.2.23] 2023-02-20

      - Fixed: GUI Restore not displaying 'file not found' in GUI
      - Added: GUI Restore changes display settings based on restored settings

## [1.2.22] 2023-02-17

      - Changed: Moved the code base to the src directory
      - Changed: Primary program renamed from 'main' to 'maptasker'

## [1.2.2-thru-1.2.21] 2023-02-17

       Added: Packaged for pip install

## [1.2.1] 2023-02-05

      - Updated for pip packaging
      - Fixed: GUI 'Restore Settings' not changing the colors from saved settings
      - Fixed: Bullet color not properly set in output
      - Changed: Simplified command line code
      - Added: Clarification on color argument options help by providing examples (-c)

## [1.2.0] 2023-02-04

      - Added:  Formal argument parser
      - Added:  Save runtime arguments to file and optionally restore them
      - Added: Messages provided in the GUI for the Reset button and the Color selection
      - Added: Check for valid hex digits for program argument color
      - Changed: Command Line Interface options have changed (see README)
      - Fixed: Option '-e' only recognized via GUI and not CLI
      - Changed: GUI Project/Profile/Task 'Name' buttons changed to radio buttons

## [1.1.1] 2023-01-27

      - Added:  Project/Profile Taskernet details optionally displayed (see option '-taskernet')
      - Added: '-e' option for the display "everything": Profile conditions, TaskerNet info and full details
      - Fixed: Project 'launch' Tasks are now properly displayed
      - Fixed: README runtime options not formatted properly
      - Fixed: Program error processing invalid color choice

## [1.1.0] 2023-01-23

      - Added:  Optional GUI front-end for runtime options
      - Added:  Sample images to README
      - Changed: Relocated called modules to subdirectory 'routines'
      - Changed: Main program top all lowercase: maptasker.py
      - Fixed: no longer producing log file if not in debug mode

## [1.0.1] 2023-01-03

      - Changed: Cleaned up the output HTML
      - Fixed: Removed extra comma at end of Task action

## 1.0.0 ## 2022-12-29

       Changed: Program rewrite for performance, level of detail and readability
       Changed: Removed word "Action" from output to remain consistent with Tasker
       Added: full package as a zip file (see README)
       Added: Support for 99% of Tasks, 90% of Plugins
       Added: Support for action *name* only (no Task action parameters).  See -d2 option
       Changed: The '-d2' display detail option is now the '-d3' option (see above change)
       Fixed: Several improperly reported Task actions

## 0.8.0 ## 2022-11-03

       Changed: Restructured code for better readability and performance
       Added: New option (-project='project name') to display a single Project, its Profiles and Tasks
       Added: Missing Plugin Actions: AutoTools Action Wait, Autotools Time, Autotools Json Read
       Fixed: Cleaned up several Task Actions
       Fixed: The background color option is not properly set
       Fixed: -task= option could result in multiple Tasks being displayed for the same Profile

## 0.7.0 ## 2022-10-26

       Changed: Restructured code for better readability
       Added: New option (-profile='profile name') to display a single Profile and its Tasks
       Changed: runtime option -p is now -profcon (display Profile conditions)
       Changed: runtime option -t='task_name' is now -task='task_name' (display a single Task)
       Fixed: Certain Tasks not being identified within Profile for the option to display a single Task
       Fixed: Not properly reporting bad arguments

## 0.6.7 ## 2022-10-17

       Added: additional Task actions recognized and more in-depth detail for some preexisting Actions
              Actions completed: Zoom
       Added: More details for some Actions Flash, Notify, Google Drive
       Added: Force continued Actions limit to avoid super large binary files from displaying
       Added: Orientation Profile 'State' as the condition
       Added: Dark mode in the user-defined variables Change: Converted lists to dictionaries for better performance
       Fixed: Changed logic to allow for output cleanup after Action details
       Fixed: Font corruption if the Action label contains HTML.  Try to maintain most of the HTML.
       Fixed: Invalid Project identified for Task ('...in Project xxx') if Task ID is a subset of Project's Tasks (e.g. '83' in '283')

## 0.6.6 ## 2022-10-06

       Added: Additional Task actions recognized and more in-depth detail for some preexisting Actions
              Actions completed: Settings, System, Tasks, Tasker, Variables
       Added: Optimized code for debug/testing mode
       Added: More details for some Actions Fixed: incorrect colors used if displaying specific Task
       Fixed: Not capturing all Action attributes if type is Int (integer)
       Fixed: Drop the final comma from Action details since nothing follows after the comma

## 0.6.5 ## 2022-09-27

       Added: Additional Task actions recognized
              Actions complete: Phone, Scenes
       Fixed: Incorrect indentation for Scene's Tasks and regular Tasks
       Fixed: Established a standard Action output format that will be used going forward
       Fixed: Eliminate extraneous print commands
       Fixed: Bug in Action, for which an integer value is stored in a variable
       Fixed: Not properly stripping all extraneous html from backup XML

## 6.4 Added: Additional Task actions recognized

              Actions complete: Media, Net
       Fixed: Single Task option -t='task' sometimes returns multiple Tasks by mistake

## 6.3 Added: Additional Task actions and Profile configurations recognized

       Actions complete: Google, Image, Input, Location
       Added: Start providing explicit detail for Actions
       Changed: Moved this change log to "Changelog.md".

## 6.2 Added: Additional Task actions and Profile configurations recognized

       Actions complete: Alert, App, Audio, Code, Display, File
       Added: prompt msgbox user to locate the file the first time the program is run
       Fixed: don't display Scenes if displaying a single Task
       Fixed: not always finding Task being searched for (-t='task_name')

## 6.1 Changed: Removed requirements for "easygui" and python-tk@3.9

       Added: Additional Task actions and Profile configurations recognized

## 6.0 Added: support for colors as arguments -c(type)=color_name  type: Task/Profile/etc

       Added: Additional Task actions and Profile configurations recognized
       Fixed: code refinement for better performance
       Fixed: Action 'Turn Wifi' was not designated on/off/toggle
       Fixed: XML Actions with string 'Task' displaying in the wrong color
       Perform: converted if-then-else processes to Python 3.10's match case statements
       Fixed: deal with extra HTML tags in plugin data which caused corrupted output font
       Fixed: Go To Action had incorrect details
       Fixed: Single Task option -t not working properly
       Changed: Removed list output style (option -l)

## 5.2 Added: Additional Task actions and Profile configurations recognized

       Added: If the Profile condition is displayed, identify inverted conditions
       Added: Summary at end of all Projects with no Profiles
       Added: Recognition of the existence of a Launcher Task
       Fixed: Scene details not displaying for runtime option -d1 (default)
       Fixed: Eliminated Profile & Task ID numbers...only needed for debug
       Fixed: code with name of 'Task:' incorrectly caused Task color

## 5.1 Added: Additional Task actions and Profile configurations recognized

## 5.0 Added: Changed default font to monospace: Courier

       Added: Action details for Power Mode, Mobile Data, Autosync and Setup Quick Setting
       Added: Display Profile's condition (Time, State, Event, etc.) with option -p
       Added: If Task is Unnamed, display just the first Task for -d0 option (like Tasker)
       Added: identify the disabled Profiles
       Fixed: exit code 1 is due to a program error...corrected and added exit 6
       Fixed: some Scene-related Tasks were not being listed
       Fixed: Listing total unknown Tasks including those associated with Scenes
       Fixed: Changed 'Action: nn' to 'Action nn:'   (moved then colon)

## 4.3 Added: Support for more Action codes (e.g. plugin & other Task calls)

       Fixed: Variable Search Replace action value 2 was sometimes incorrect
       Fixed: Removed print output line for -t='task-name' option
       Fixed: Not displaying owning Project for Tasks not associated with a Profile
       Fixed: Invalid Tasks Not Found Count at the end, if -d0 or -d1 options

## 4.2 Fixed: Only display Scene Action detail for option -d2

       Added: Support for single Task detail only (option -t='Task Name Here')
       Fixed: missing detail in Actions Notify, Custom Settings, Input Dialog & Set Alarm
       Added: Details for plugin Actions
       Fixed: Unnamed/Anonymous Tasks output in the wrong (Green) color when should be Red
       Fixed: Remove 'Task ID: nnn' from output (of no benefit)

## 4.1 Fixed: The location of the output file is corrected to be the current folder in the msg box

       Fixed: If set / not set were reversed
       Added: Support for disabled Actions and Action conditions (If...)

## 4.0 Added: indentation support for if/then sequences

       Fixed: Action "End For or Stop" is just "End For"
       Added: Support for more Task Action codes
       Added: Action numbers

## 3.0 Added: display label if found for Task action(s)

       Added: Display entry vs exit Task type
       Added: Support for many more Task Action codes
       Added: Support for 3 levels of detail: none, unnamed Tasks only, all Tasks
              Replaced argument -s with -d0 (no actions) and -d2 (all Task actions
              Default is -d1: actions for unnamed/anonymous Tasks only)
       Fixed: Some Scenes with Long Tap were not capturing the Task
       Fixed: Projects with no Tasks were showing an incorrect Project name

## 2.1 Fixed: actions were not sorted properly

       Fixed: Stop action improperly reported as Else action
       Added: Support for more Task Action codes

## 2.0 Added output style (linear or bullet), colormap['bullet_color'] as global var

       Added detail mode (default) which can be turned off with option -s
       displaying unnamed Task's Actions

## 1.2 Added -v and -h arguments to display the program version and help

## 1.2 launch browser to display results

## 1.1 Added list of Tasks for which there is no Profile
