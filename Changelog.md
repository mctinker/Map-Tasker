# MapTasker Change log  # ruff: noqa

All notable changes to this project will be documented in this file!

## [3.1.7] 28-March-2024

### Fixed

- Fixed: Eliminate reading the XML file twice when running from the GUI.
- Fixed: The GUI gets a 'Backup File not found' error message if displaying the treeview after having restored the settings.

## Older History Logs

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
