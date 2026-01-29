# MapTasker Change Log

All notable changes to this project will be documented in this file!

## [10.0.5] 29-Jan-2026

### Added

- Added: None

### Changed

- Changed: None

### Fixed

- Fixed: Some Tasks may not appear in the Map view when displaying TaskerNet descriptions.
- Fixed: The Map view (directory) ability to go up one level is not displaying.

### Known Issue

- The GUI window positioning on startup could be wrong if running under an older version of Parallels Desktop. Make certain Parallels' settings for Full Screen 'Scale to fit screen' is set to 'Keep ratio' if this option is available.

## Older History Logs

## [10.0.3-10.0.4] 27-Jan-2026

- Added: Additional plugins are now recognized: AutoBarCode, ADB Shell, Watchmaker, TouchTask, Blockada, Sleep as Android, FolderSync, Pushbullet, AutoMail
- Added: Language translations added to the Diagram view.
- Changed: Code optimization
- Changed: AI Gemini models '2.0 Flash 'and '2.0 Flash Lite' have been removed by Google and are no longer supported.
- Fixed: If using for the first time, the initial prompt to select the XML file can be hidden by other windows.
- Fixed: Tasks are not properly identified as 'Entry' or 'Exit' tasks.
- Fixed: The "Search" button in the Map and Diagram views is not being translated to German.
- Fixed: Translation is missing for some text strings in the GUI.
- Fixed: Buttons in the Map and Diagram views are overlapping each other for certain languages other than English.
- Fixed: Program error in Diagram view.
- Fixed: Program error when setting the view limit with a language other than English.
- Fixed: Changing language sets all of the selected Projects/Profiles/Tasks to 'None' in the pulldown menus even though a single item may have been selected.
- Fixed: The GUI single item selection section of labels is overlayed when changing language.
- Fixed: The tab names in the GUI are note getting translated.
- Fixed: Multiple rows of Scenes in the Diagram view are mis-aligned and in the wrong color.

## [10.0.2] 19-Dec-2025

- Added: 23 additional languages are now supported. English is always at the top of the selection list.
- Added: The country flag is displayed for each language selection.
- Changed: Restructured GUI code to optimize performance.
- Fixed: Language header incorrectly displays if displaying help in a language other than English.
- Fixed: Some buttons get overlaid if the language is changed.
- Fixed: Non-functional 'tts' Gemini models are incorrectly listed in the extended AI model list.
- Fixed: Non-functional 'codex' OpenAI models are incorrectly listed in the extended AI model list.

## [10.0.0-10.0.1] 15-Dec-2025

- Added: GUI Multilinqual support for: French, German, Hindi, Japanese, Korean, Simplified and Traditional Chinese, Spanish, Portuguese, and Russian.
- Changed: Code optimizations
- Fixed: Program error when clicking on the GUI 'Report an Issue' button.

## [9.1.1-9.1.3] 30-Nov-2025

- Changed: Performance tuning.
- Changed: Video hotlinks are temporarily not supported on Windows due to failing dependency on 'opencv-python'.
- Fixed: Possible program loop if displaying 'TaskerNet Info'.
- Fixed: Minor display error in certain TaskerNet Info hotlinks.
- Fixed: Version 9.1.0 fails to install on Windows due to a problem with the dependency on 'opencv-python'.

## [9.1.0] 20-Nov-2025

- Added: Video playback support has been added to TaskerNet descriptions and labels (Youtube via ffmpeg, and Dropbox).
- Added: 'ffmpeg' installation details have been included in the 'Caveats' section at the bottom of the Map view/HTML and in the README file.
- Added: Tasker version 6.6.12-beta is supported.
- Changed: Embedded 'href=url...' videos are now referenced via '[▶️ VIDEO: url...]'
- Fixed: Slight spacing/newline problem with images in TaskerNet descriptions.
- Fixed: Not properly recognizing new paragraph in embedded html.
- Fixed: Under certain situations, TaskerNet description lines would be repeated.
- Fixed: The program is incorrectly reporting that no Gemini AI models are found if in debug mode.

## [9.0.4-9.0.5] 06-Nov-2025

- Added: Created an additional output trace log file if 'debug' is on for the Map view.
- Added: Tasker beta 6.6.11-beta is now supported.
- Added: Task action 'Assistant Volume' is now supported.
- Changed: Code optimized for improved Map view performance.
- Fixed: A program error occurs in 'guimap.py'.
- Fixed: Eliminate excessive blank lines in the Map view.
- Fixed: The Project's 'properties' inadvertently pick up the color for 'Luancher Task' if there is a launcher task.

## [9.0.3] 30-Oct-2025

- Fixed: Embedded HTML list items are not all being formatted correctly.
- Fixed: There are an excessive number of spaces in TaskerNet descriptions.
- Fixed: Properly handle ordered lists in embedded HTML.
- Fixed: Embedded HTML 'Title' tag is not displaying.

## [9.0.2] 20-Oct-2025

- Added: The 'strong', 'title', 'hr', 'figcaption' and 'legend' HTML tags are now supported.
- Added: Unrecognized HTML tags in labels and TaskerNet descriptions are now identified in the output as 'unmapped'
- Changed: No notable changes
- Fixed: List items in TaskerNet descriptions are not formatted properly.
- Fixed: Subtle errors in data mapping are going undetected.
- Fixed: Diagram view is using the wrong background color if the font is not 'Courier'

## [9.0.1] 15-Oct-2025

- Added: The 'Display Only' window now provides hotlinks to the associated line in the data for quick access.
- Added: Tasker version 6.6.6-beta is now supported.
- Added: The 'Extra Trigger' Profile event is now recognized.
- Added: Python 3.14 is now supported.
- Changed: The 'Google API Key' Tasker preference value is now hidden in the output for security purposes.
- Fixed: There are too many spaces between lines in labels and TaskerNet descriptions.
- Fixed: The Diagram view 'Top Task' and 'Bottom Task' buttons incorrectly overlay other buttons.
- Fixed: Incorrectly handling situation in which clicking on a hyperlink for an the object that no longer exists.

## [9.0.0] 12-Oct-2025

- Added: Support for Tasker version 6.6.4-beta.
- Added: 'Search Here' button has been added to the views, to begin the search at the current screen rather than at the top of the data.
- Added: 'Display Only' button has been added to the views, to display in a new miscellaneous window only those lines that match the search string.
- Fixed: 'print' statements are mistakenly displaying a list of directories at startup.
- Fixed: Gemini full model list is missing.
- Fixed: The text string '</div>' is found at the end of some Task actions in the Map view.
- Fixed: Program 'TclError' error on exit if all of the windows have been closed.

## [8.3.2] 05-Oct-2025

- Added: Embedded HTML now recognizes the 'big' tag.
- Fixed: Task 'TaskerNet descriptions' are not being displayed.
- FIxed: Program error when a hex color name is encountered.

## [8.3.1] 28-Sep-2025

- Added: Embedded HTML in labels and TaskerNet descriptions now support the 'pre', 'code' and table tags.
- Fixed: Extra blank lines are incorrectly added to TaskerNet descriptions.
- Fixed: "View Not Possible..." error message displays in GUI textbox incorrectly.
- Fixed: The space between lines of embedded HTML has been reduced so it better reflects TaskerNet descriptions and labels.
- Fixed: Underlined text is not displaying as such in embedded HTML tags.

## [8.3.0] 22-Sep-2025

- Added: Embedded HTML in labels and TaskerNet descriptions now support the 'pre', 'src' and 'style' tags. 'Style' tags and their contents are flagged.
- Changed: Support for the older configuration/setting JSON file format (12+ months old) has been dropped.
- Changed: The 'ReRun' and 'AI Analysis' buttons now exit and reload the program to eliminate Map view text size issues.
- Changed: Switched from Google's deprecated AI API to new generative API.
- Fixed: Incorrect spacing on list items in labels and TaskerNet descriptions with embedded HTML.
- Fixed: Embedded HTML 'href' reference in labels and TaskerNet descriptions are not properly recognized if it starts in column 1.
- Fixed: Labels and TaskerNet descriptions are displayed in the wrong font size. NOTE: It is still incorrect for Window.
- Fixed: Text in Map view is incorrect size after 'ReRun'.
- Fixed: GUI can sometimes close unexpectedly.
- FIxed: ChatGPT-5-mini model is misspelled.

## [8.2.1-8.2.2] 10-Sep-2025

- Added: TaskerNet descriptions with HTML are now handled like labels with HTML. The HTML is retained and the description is surrounded by a rectangle.
- Added: Labels and TaskerNet descriptions with html now recognize italicized/emphasized and bold text, as well as hotlinks.
- Changed: All Task labels are now outlined in a rectangle, rather than only those labels with HTML.
- Changed; Default font size for label and TaskerNet description text is set to that of the rest of the text in the Map view.
- Fixed: Various issues with embedded HTML in labels.
- Fixed: Formatting errors and missing commas in the 'To=' text if the Task action is a 'Variable Set'.
- Fixed: Not all embedded HTML in Task action titles is being properly displayed.

## [8.2.0] 29-Aug-2025

- Added: Task labels with embedded html are now displayed with that html (color, headings, lists) surrounded by a rectangle. This is a work in progress.
- Default AI model list has been updated.
- Changed: HTML in Task actions is now displayed as with HTML tags rather than having them removed.
- Changed: Lines that are very long are no longer identified with 'Continued >>>'.
- Fixed: Task actions with labels are not properly aligned if the 'pretty' option is selected.
- Fixed: Embedded HTML in task parameters are not appearing with their tags.
- Fixed: Diagram view shows 'Anchor {h3}{font color=...}' if there is a Task 'Anchor' in the configuration.

## [8.1.3-8.1.4] 31-July-2025

- Added: No new features have been added.
- Changed: Deprecated OpenAI default models have been removed.
- Changed: The color of the text in the Diagram 'Top Task' and 'Bottom Task' buttons has been changed to make these more visible when each button appears.
- Fixed: The GUI labels identifying the current single-named item are not being updated when going up one or more levels in the Map view.
- Fixed: 'Threading' error on exit after AI Analysis.
- Fixed: 'Invalid API Key' message appears for AI Analysis even though the API key is valid.
- Fixed: Unexpected program (normal) termination immediately after AI Analysis.
- Fixed: The 'Analysis is running in the background' message doesn't always appear.
- Fixed: Program error if running in non-GUI mode.

## [8.1.2] 29-July-2025

- Changed: 'What's New' now displays the new and previous 9 versions of the changelog rather than just the new version.
- Fixed: 'What's New' and 'Program Upgrade...' buttons always appear in the GUI even if no new version is available.

## [8.1.1] 27-July-2025

- Added: 'Extended' AI Model List is now available to include many more AI models in the GUI.
- Changed: Restructured the AI model handler to allow for the extended model list.
- Changed: 'Claude' AI models renamed to 'Anthropic'.
- Changed: Don't show the configuration in the web browser if doing an AI Analysis.
- Changed: Removed the 'please wait...' popup window for AI Analysis on Windows to eliminate a delay in the analysis.
- Fixed: Program error in the GUI if 'None' is selected as the AI model.
- Fixed: Entering an API key into the GUI does not update the 'Set' or 'Unset' message.
- Fixed: The error code message from Gemini has extraneous information.
- Fixed: AI Analysis is not working on Windows.
- Fixed: 'Upgrade to New Version' button is not automatically restarting MapTasker on Windows after the upgrade.
- Fixed: Saving the AI API key dialog can cause a program error when trying to save the window position.

## [8.1.0] 13-July-2025

- Added: Tasker version 6.6.3-beta is supported.
- Added: 'SecureTask Airplane Mode' plugin has been added.
- Added: Additional tooltips have been added to the GUI.
- Added: AI Llama model 'qwen3:1.7b' has been added.
- Changed: Tasks identified in Map view by hovering over a Project or Profile are listed as 'sorted'.
- Fixed: Initial GUI displays with a jitter effect due to resizing based on the saved settings.
- Fixed: Task action 'Call' is not appearing correctly.
- Fixed: Some Task action selected checkboxes are identified as '=1' rather than as '(selected)'.
- Fixed: The directory hotlink 'Up One Level' is not displaying in the Map View.
- Fixed: Incorrect output color in Map view if '\_color' is part of a variable name in a Task.
- Fixed: Caveat at the bottom referring to inactive and unreferenced global variables is not appearing if the display level is 5.

## [8.0.6]. 07-July-2025

- Changed: Code optimized to make it easier to pick up new changes in Tasker.
- Changed: The Diagram view jump-to-top-task and jump-to-bottom-task buttons are now dynamic, only displaying when appropriate.
- Changed: The AI Analysis output file is now saved with the date and time.
- Fixed: The GUI last-tab-used is not saved and restored if either 'Rerun' or 'Run and Exit' is selected.
- Fixed: Hover over directory name shows detail in the wrong background color in GUI on Windows.
- Fixed: The GUI default window size is not high enough to include the 'Reset' button.

## [8.0.5]

- Added: Tasker version 6.6.0-beta is supported.
- Fixed: 'Upgrade To Latest Version' GUI button is not working on Windows 11.
- Fixed: Program error in maputils is_color_dark when hovering over item in Map view and the background color is a hex value.
- Fixed: Task actions are double-spacing in the Map view on Windows.
- Fixed: AI Analysis window is missing the title.
- Fixed: Potential AI analysis loop if it this was left on in settings due to abnormal terminal.
- Fixed: Logging is not enabled if 'debug' is on in the saved settings at startup.
- Fixed: Program error if a new action argument is not yet supported.

## [8.0.4]

- Added: No additions.
- Changed: Gemini model 2.5 Pro has been upgraded from the preview model to 'gemini-2.5-pro'.
- Fixed: Ai-Analysis window is not getting the focus.
- Fixed: Numerous bugs when running on Windows 11.
- Fixed: Diagram and Map views are not being displayed in the defined background color.
- Fixed: The GUI 'hover tip' background and foreground colors are incorrect.

## [8.0.2]

- Added: The last 'tab' used in the GUI is now saved across sessions and restored on re-entry.
- Fixed: Closing the GUI window via the window icon is not saving the settings.
- Fixed: The diagram is not appearing in the default text editor if running with '-outline' option.
- Fixed: Changed error messages that referred to "Backup File" to read "XML File".
- Fixed: Debug option is not working.
- Fixed: Clicking on Map or Diagram view buttons in the GUI while either is already running causes an internal loop.

## [8.0.1]

- Added: Full support for Tasker version 6.5.8/9.
- Added: If selecting an unnamed Task to display from the single-name pulldown menu, display the owning Profile and Project names as well.
- Fixed: Clicking a directory hotlink can inadvertently go to a partial match of the Tasker object name.
- Fixed: Unable to change the color for unnamed Tasks.
- Fixed: Non-GUI mode abnormally terminates in diagram.py

## [8.0.0]

- Added: New 'List Unnamed Items' checkbox has been added to the GUI under the 'Specific Name' tab. Click on the text of the checkbox for details.
- Added: The Anthropic 'claude-opus-4-20250514' and 'claude-sonnet-4-20250514' AI models have been added.
- Changed: 'None or Unnamed!' in Profile names has been changed to 'Unnamed'.
- Changed: Gemini AI models 'gemini-2.5-flash-preview' and 'gemini-2.5-pro-preview' have been updated to the latest versions.
- Fixed: Too much javascript content is not appearing in the output.
- Fixed: Tasks with too many actions that have a '>' in the name are not hotlinks.
- Fixed: Program errors related to Tasks with no name.
- Fixed: Duplicate Tasks are displayed when hovering over Project or Profile name.
- Fixed: Selecting an unnamed Task in the GUI pulldown menu can not be found for display.

## [7.3.1]

- Added: Add unnamed Tasks (e.g. Scene related tasks) to the directory.
- Added: Hover over Profile now includes a list of Tasks in the Map view.
- Added: All unnamed Tasks now have a name consisting of the first action in the Task.
- Changed: 'Debug' mode no longer requires the XML file to be named 'backup'.
- Changed: Unnamed Tasks now have the name of the first action. Example: 'If %fast ~ no.475 (Unnamed)', where '475' is the Task id.
- Fixed: Hover over Task name in Map view gives program error if Task is not associated with a Profile.
- Fixed: 'Cancel Entry' button mistakenly leaves a '?' in the GUI.
- Fixed: Incorrectly including a '0' in the Profile name if it is anonymous.
- Fixed: Hover over a Project that has anonymous Profiles does display the Tasks under those Profiles.
- Fixed: Cleaned up unnamed Profile (conditional) names.
- Fixed: Task action output with 'continued >' lines are incorrectly being included in the action count.
- Fixed: Program error if searching for string in the Diagram view.

## [7.2.3]

- Added: Tasker version 6.5.6-rc is supported.
- Added: Two missing events and two missing plugins have been added.
- Added: Unnamed Profiles now have a name. See 'Changed', below.
- Changed: Unnamed Profiles are now listed as they are in Tasker, consisting of the conditions and are preceded by an asterisk and followed by a '(None or unnamed!).' plus unique ID number. Example: '\*Face Down (None or unnamed!).45'
- Changed: Unnamed Profiles now appear at the beginning of the Profile directory entries (all names start with '\*').
- Changed: Unnamed Tasks called by Scenes are now identified as 'Unnamed/Anonymous'.
- Changed: Extended Map view directory names from 40 characters long to 50 characters.
- Fixed: 'File Modified' event is not displaying 'File=' value.
- Fixed: Map view Scene elements are all misaligned.
- Fixed: The Map view is displaying duplicate Scene 'Properties --Task:...' details.
- Fixed: Program error if a 'Name' is associated with a Time or Day profile condition.
- Fixed: The Diagram view gets corrupted if the diagram is greater than 4500 characters in length (e.g. a massive diagram). The fix is to truncate those lines at 4500 characters.
- Fixed: Global variables are not appearing in the Map view.
- Fixed: Changed color settings are not being restored.
- Fixed: Hover over Task name in the Map view displays incorrect Profile and Project.
- Fixed: Hover over Scene name in Map view incorrectly displays HTML.
- Fixed: Owner display when hovering over search string in Map view is off the screen. Truncate the displayed results instead.
- Fixed: Program error if the progress bar window is closed during a loop condition.

## [7.2.2]

- Added: Gemini models "gemini-2.5-flash-preview-04-17" and "gemini-2.5-pro-preview-03-25" have been added.
- Changed: No changes.
- Fixed: Tasks with '<' or '>' in the name is not appearing correctly in the Map view.
- Fixed: Debug mode in GUI is not recognized.
- Fixed: Doing a Map or Diagram view can potentially invoke AI Analysis inadvertently.

## [7.2.0]

- Added: Hover over a matched search string in Map view displays all the matches from the 'Search'.
- Added: Ollama AI models 'exaone-deep', 'gemma3' and 'phi4-mini' have been added.
- Added: Deepseek AI 'deepseek-reaoner' model has been added.
- Added: Anthropic AI 'claude-3-7-sonnet' model has been added.
- Changed: Task 'Configuration parameter(s):' have been flattened (removed 'Continued >>>') if not doing 'Pretty' output.
- Fixed: If the 'Pretty' option is selected, properly align Profile condition arguments.
- Fixed: Task '[⛔DISABLED]' indicators are misaligned.
- Fixed: '<' and '>' are occasionally missing from IF conditions in the Map view.
- Fixed: Invalid progress bar window position hides the progress bar altogether.

## [7.1.2]

- Added: OpenAI's 'o1-pro' and 'gemini-2.5-pro-exp-03-25' AI models have been added (removed 'o1-preview').
- Added: Support for Tasker 6.5.3 Beta.
- Changed: Only display a 'Property' if it has a value or is checked.
- Fixed: Minor html formatting issues.
- Fixed: Events with multiple applications specified are not formatted properly.
- Fixed: Conditions associated with Profile States and Events are not displayed.
- Fixed: Profiles are being mis-identified as Launcher Tasks.
- Fixed: Program error if the XML file is not accessible during startup.
- Fixed: Program error on startup if the settings file is corrupt.

## [7.1.1]

- Added: Tasker version 6.5.1 Beta support (new 'Calendar' Task actions).
- Added: Closing the progress bar now also cancels the current view.
- Added: Scene Tasks have been added to the Diagram view.
- Added: Profile Events 'Network Changed', 'Pick Up Gesture', 'Fingerprint Gesture', 'Physical Activity', 'Clipboard Changed', 'Accessibility Services Changed', 'Device Unlock Failed' and 'Remote Action Token Changed' are now recognized.
- Added: Profile States 'Room', 'Reaching', 'Physical Activity', 'Matter Light', 'Data Usage', and 'Compass Orientation' are now recognized.
- Fixed: The current view continues to display as empty if closing the progress bar.
- Fixed: Screen WebElement 'Source=' HTML is missing and/or malformed.
- Fixed: States 'BT Status' and 'BT Near' not recognized.
- Fixed: Task action labels are not all displaying in the correct color.
- Fixed: Not correctly parsing action arguments that contain a '<'.
- Fixed: 'Run and Exit' after doing a 'Map' view from the GUI would display the wrong data in the browser.

## [7.1.0]

- Added: Task action 'Remote Action Execution' added.
- Added: Support for Tasker version 6.4.13
- Added: Event 'Intent Received' is missing the arguments.
- Added: Open AI 'gpt-4.5-preview' AI model.
- Added: Numerous Task action arguments have been added with the background synchronization with Tasker.
- Changed: Updated list of deprecated Task actions.
- Changed: Program data restructured to enable easier transition to future Tasker 'Task' action changes and improve accuracy.
- Changed: Removed no longer supported 'Gemini-1.0' and 'gemini-2.0-flash-exp' AI models.
- Fixed: 'UnboundLocalError' program error in scenes.py.ø
- Fixed: LLAMA AI Analysis fails due to improper API key when no API key is required.
- Fixed: Various Task action arguments were missing or incorrect.
- Fixed: Alignment of 'Configuration Parameter(s)' is not always correct if using 'pretty' option.
- Fixed: Program error if trying to close the progress bar window.
- Fixed: Removed redundant blank lines from the Map view.

## [7.0.2]

- Added: Task action 'Remote Action Execution' added.
- Changed: Updated list of deprecated Task actions.
- Fixed: 'UnboundLocalError' program error in scenes.py.
- Fixed: LLAMA AI Analysis fails due to improper API key when no API key is required.

## [7.0.1]

- Added: New Ai models added: gemini-2.0.flash, gemini-2.0-flash-lite-preview, gpt-4-turbo-preview
- Added: Task action "Get Pixel Colors' to map.
- Changed: Code optimizations.
- Fixed: Widget V2 missing the argument 'Ask To Add If Not Present'.
- Fixed: Program error when hovering over a Scene name in the Map view.
- Fixed: Program error in taskuniq.py.
- Fixed: MapTasker can not be installed with Python 3.13.2 or higher. Fixed so that it can run any 3.13.

## [7.0.0]

- Added: Hover tips for Scenes have been added to the Map view.
- Added: Claude AI (Anthropic), Gemini AI, and DeepSeek AI are now supported in the AI Analysis tab.
- Added: Support for multiple AI API keys.
- Added: Tasker Beta 6.4.12 supported.
- Added: Llama AI models 'deepseek-r1' and 'phi4' added.
- Changed: The GUI message box is now cleared before displaying an error during initialization.
- Changed: The AI API Key prompt has been modified for multiple keys, and for the identification of the current key to be used for the AI Analysis.
- Changed: The AI Model selection pulldown option list is now preceded by their owner: 'OpenAI', 'Claude', 'Gemini' and 'LLAMA'. Example: 'OpenAI: gpt-04', and each AI's list of models are now grouped together in the pulldown option list.
- Fixed: Program error if the AI model has not been set.
- Fixed: Ai Analysis of a single Task reports it as the Project owning the Task.
- Fixed: Keep the 'Analyze' tab active after an AI analysis.

## [6.1.1]

- Added: Added support for plugins: Muzei Wallpaper, Calendar Task, AutoTools OCR.
- Changed: Miscellaneous code optimized for performance.
- Fixed: Diagram connector alignment is somewhat corrected for Simplified Chinese, Korean and Japanese.
- Fixed: Removed extraneous blank line after Profile in the Map view.
- Fixed: Program error in Tkimage, when starting GUI if running via 'UV' Python package manager.
- Fixed: Program error in taskactn if debug is on.
- Fixed: Support Python 3.13.1

## [6.1.0]

- Added: Open AI new models 'o3' and '03-mini' have been added.
- Added: List Tasks with 'too many actions' warning at the bottom of the output with hotlinks to the Task.
- Added: The GUI has a slider to define the limit for 'too many Task actions' warning.
- Added: Additional tooltips have been added to the user interface.
- Changed: Updated the GUI help information.
- Fixed: Alignment of column heading in Project hover text is not correct.
- Fixed: Hover text for "Unnamed/Anonymous" Tasks is not correct.
- Fixed: Tooltips are too small to read.
- Fixed: Changing the Single Project, Profile or Task name uses the prior data in the Map view.
- Fixed: Task action arguments are not all aligned if 'Pretty' is selected.

## [6.0.6]

- Added: Scenes have been added to the directory in the Map view.
- Added: Open AI's 'chatgpt-4o-latest', and 'o1' models have been added.
- Added: Ollama 'llama3.3' model has been added.
- Changed: Hover text in the Map view for Projects and Tasks now display additional details.
- Changed: Unnamed/Anonymous Tasks are now displayed with an ID so that they can properly be parsed.
- Fixed: GUI Menu hover tooltips are displaying in a very small font.
- Fixed: Program error due to bad font name.
- Fixed: Projects with a trailing blank character are not properly recognized.
- Fixed: Numerous hover text issues.
- Fixed: Issue running AI Analysis with '01-preview' model.
- Fixed: When searching for the next or previous string in the Map or Diagram view, using the 'Top' button to navigate to the top does not restart the search from the beginning.

## [6.0.5]

- Added: Added a 'Buy Me A Coffee' button to the Debug tab in the GUI. :o)
- Added Tooltips to the GUI: hover over a button/checkbox/pulldown to get information about the command.
- Added: Hover over a Project/Profile/Task name in the Map view to get a description of the Project/Profile/Task. The information provided will be expanded over time.
- Added: New llama Ai models added: mistrel-nemo and tinyllama.
- Fixed: Highlighting (bold, underline, etc.) in the Map view is broken.
- Fixed: The program can get into a never-ending loop if the Ai analysis fails.

## [6.0.4]

- Added: Tasker 6.4.6 Beta is now fully supported (i.e. Widget V2 support).
- Added: Additional Profile Properties added to the output: Limit Repeats, Cooldown Time, Profile Variable Type.
- Added: Re-instituted the progress bar in the Map and Diagram views.
- Added: 'Profiles Per Line' option added to the Diagram view. Click on the '?' next to it for details.
- Added: Ollama models 'qwen2.5' and 'qwen2.5-coder' have been added.
- Changed: 'Go to top' and 'Go to bottom' hotlinks have been removed from the Map view in preference to the 'Top' and 'Bottom' buttons. 'Go to top' is still in the browser output.
- Changed: The popup window displaying 'The view is running in the background. Please stand by...' has been eliminated for improved performance.
- Fixed: Spacing for '[Continue Task After Error]' is incorrect in the Map view.
- Fixed: Diagram view is missing an occasional Task underneath it's Profile.
- Fixed: Eliminated potential 'Rutroh!...' output in the terminal.
- Fixed: The log file is not being generated if 'Debug' is turned on in the GUI.
- Fixed: Selecting a single named item in the GUI doesn't clear out the other single named items in the pulldown selection menus.
- Fixed: Program terminates abnormally if the Map or Diagram buttons are double-clicked.
- Fixed: 'Bottom Task' button points to the bottom Task's arrow rather than to the Task itself.

## [6.0.2/6.0.3]

- Added: 'Top Task' and 'Bottom Task' buttons added to the Diagram view when highlighting Task connectors, to jump to the top/bottom of the Task connector.
- Changed: The 'IA' Diagram view button has been removed since it is no longer needed.
- Changed: The progress bar in the Map and Diagram views has been removed temporarily due to a bug in some core python code.
- Changed: Python installations that use 'pyenv' version management, take note: tcl-tk has been upgraded to version 9 (brew install tcl-tk), which may cause an error when importing tkinter. If this error occurs:
  - if running python 3.11.10 or lower, then the new tcl-tk is not recognized and you will get an import error for 'tkinter'. Issue the commands (in the order specified):
    - 'brew uninstall tcl-tk',
    - 'pyenv uninstall 3.11.xx'
    - 'brew install tcl-tk8'
    - 'pyenv install 3.11:latest'
  - if running python 3.12.4, upgrade to 3.12.7 (the latest): 'pyenv install 3.12:latest'
  - Python version 3.13.0 works fine with the new tcl-tk.

- Fixed: Tasks identified as 'entry' or 'exit' in the Diagram view are not displaying any connectors.
- Fixed: Multiple Task6.0.2 on the same line in the Diagram view that are not found are not displaying '(not found)!' in the correct position.
- Fixed: Optimize the connector alignment in the Diagram view (performance enhancement).
- Fixed: The Diagram view has overlapping horizontal connectors in certain situations.
- Fixed: Diagram buttons disappear if the right side of window is shifted/resized to the left.
- Fixed: Clicking on 'Toggle Word Wrap' in the Ai Analysis results window causes a program error.

## [6.0.1]

- Added: Support for the latest 'Tasker 6.4.1 beta': new 'Widget V2' task action and other task action changes.
- Added: For task action elements that are either selected or not, display '(selected)' along with the element name (e.g. 'Continue Task Immediately (selected)').
- Changed: Improved the Diagram view performance.
- Fixed: Outer horizontal connectors in the Diagram view are too far to the right.
- Fixed: Program error during GUI initialization if previous run was for a single named item.
- Fixed: Output lines with 'Structure Output (JSON, etc)' are incorrectly displaying '&nbsp' string in front.

## [6.0]

- Added: The GUI 'views' now have a 'Top' and 'Bottom' button for quick navigation within the GUI views.
- Added: Allow the runtime option '-debug' to be carried into the GUI.
- Added: Ai analysis model 'llama3.2' has been added.
- Added: Python 3.13 fully supported.
- Changed: The Diagram view connectors have been shifted to the left as much as possible so that more can be seen within the view window.
- Fixed: The 'IA' Diagram button setting is being reversed (off rather than on, and vice versa) when restored during GUI initialization.

## [5.3.2]

- Added: Diagram view's Task connectors can now be clicked, with the mouse, to highlight the entire connection.
- Added: The "IA" button setting for the Diagram view is saved and restored between sessions.
- Changed: The Diagram view now includes all individual connectors to and from a Task, rather than a single connector for connections to/from the same Task.
- Fixed: Some connections in the Diagram view are not displaying correctly.
- Fixed: Hitting the 'Cancel' button on the file prompt is not clearing out the current file.
- Fixed: Settings are being displayed twice on initialization of the GUI.
- Fixed: Program errors on start up of GUI.

## [5.2.2]

- Added: Added the 'IA' (Icon Alignment) button next to the 'Diagram' view to enable/disable connector alignment if icons are in Task names for better performance with very complex diagrams. Refer to the view '?' (help) in the GUI for details.
- Added: Tasker object names are colored in the Diagram view.
- Fixed: Task with commas in their names do not display correctly in the Diagram view.
- Fixed: Task names with '[' embedded in can not be found when clicking on it's directory hotlink.
- Fixed: Diagram is missing bars (|) in some instances. Bars ares misaligned if the Task is not found.

## [5.2.0]

- Added: 'Up Two Levels' has been added to the Map view.
- Added: Ai analysis OpenAi models 'o1-preview' and 'o1-mini' have been added.
- Added: Ai analysis local models 'qwen2' and 'gemma2' have been added.
- Changed: Diagram rewrite to improve readability and performance.
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
- Changed: Map view performance has been improved when using the directory hyperlinks for single names that are already in the view. It goes directly to the single named item in the current view rather than remapping the named item and redrawing the view.
- Changed: To remap a single named item in the Map view, the single named item must be selected from the GUI and the 'Map' view button must be reselected. Otherwise, it will simply display the single named item in the existing Map view.
- Fixed: Project/Profile/Task/Scene name highlighting is incomplete in the Map view.
- Fixed: Project/Profile/Task/Scene names with special characters in it are not displaying correctly.
- Fixed: 'Go to bottom' hotlink in Map view goes beyond the last entry in the list.
- Fixed: If no XML is loaded, the single name pulldown are still incorrectly loaded with the prior XML names.
- Fixed: No indication is given that the search string was not found in the Map and Diagram views.
- Fixed: Unnamed Profiles have a blank name rather than 'None or unnamed!' as the name in certain situations.

## [5.1.1]

- Added: "Go to bottom" has been added to the Map view to jump to the bottom of the view.
- Added: "Go to top" has been added to Profile, Task and Scene elements in the browser.
- Changed: Don't display the message, "You can find 'MapTasker.html' in the current folder." if displaying the Map or Diagram views from the GUI.
- Fixed: Ai Analysis response window size and location are not being restored on recursive calls.
- Fixed: Horizontal scroll-bars are not being shown in the GUI views.
- Fixed: Fetching xml from the Android device is not resetting the single Project/Profile/Task to none.
- Fixed: Program error if displaying the directory in the Map view.
- Fixed: Directory names in the Map view that exceeded 40 characters are not displaying correctly. Now they are truncated with "..." at end.
- Fixed: If working with a Scene-only XML file, specifying a single named item results in program exiting rather than issuing an error message.

## [5.1.0]

- Added: Search string support added to Map , Diagram and Ai Analysis views.
- Added: 'Toggle Word Wrap' added to Map, Diagram and Ai Analysis views.
- Added: Copy and paste support added to Map, Diagram and Ai Analysis views.
- Added: The Diagram view now respects the 'View Limit'
- Added: The 'View Limit' has additional increments of 15000 and 25000.
- Changed: The GUI 'Map Limit' has been renamed to 'View Limit'.
- Changed: The Ai Analysis default prompt has been changed from "how could this be improved:" to "suggest improvements for performance and readability:"
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

- Added: A message is printed indicating that the error "IMKClient Stall detected, _please Report_..." can be ignored on 'Map' and 'Diagram' views that take a long time to process.
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
- Changed: The GUI progress bar now shows a smoother color scheme transition (red through to green).
- Fixed: If Profile has no name, say so in the 'Map' view output.
- Fixed: The GUI list of Tasks incorrectly showed some Tasks names that were not proceeded by "Task:".
- Fixed: Program error if changing the indentation amount and then display the 'Map' or 'Diagram' view.
- Fixed: Moving a 'Map', 'Diagram' or 'Tree' view window will not change the window position on consultive displays of the same view.
- Fixed: 'Map' view does not work if colors have not yet been defined.
- Fixed: Task action 'Browse URL' is missing the detailed parameters.
- Fixed: Performing a 'ReRun' proceeded by a 'Map' view with a single Task selected results in output not related to the single Task.
- Fixed: 'Map' view output spacing for Projects and Scenes is incorrect.

## [5.0.1]

- Added: 'Map' view 'Map Limit' pull-down added to the GUI to control the processing time when generating the map.
- Added: The new 'llama3.1' Ai model added to the 'Analysis' tab.
- Added: A progress bar has been added to show the progress of the 'Map' view.
- Fixed: Invalid spacing appears in the Map view directory list.
- Fixed: Spacing for parameters with "Pretty" enabled is slightly off in the Map view.

## [5.0.0]

- Added: Support for Tasker Release 6.3.12.
- Added: 'Intensity Pattern' is now included with the "Notify" Task action.
- Added: Open Ai model 'cpt-40-mini' added to the 'Analysis' tab.
- Added: Directory (hotlinks) are now supported in the 'Map' view within the GUI.
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
- Changed: Ai models are now listed alphabetically, with the last-used model listed first. The default of 'None (llama)' has been removed.
- Fixed: The 'ReRun' command caused the error message: 'Task policy set failed...'.
- Fixed: If doing a single object (Project/Profile/Task)and doing Tasker Preferences, Preferences were empty. Display appropriate message in output.
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
- Added: Going forward, if a new release is available, the GUI will provide a "What's New" button. You will be able to see what is changing before applying the changes.
- Added: Ai Analysis now supports the new OpenAI "gpt-4o" model.
- Added: Support for Tasker 6.3.8 Beta code.
- Changed: Widened the GUI window slightly for better readability.
- Changed: 'Specific Name' items are now available via a pulldown menu. It is no longer necessary to enter the names through a text input box.
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
- Added: New ability in GUI to list the Android XML files for selection and select the XML file from the list, rather than manually enter the file location. See README for details.
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
- Changed: Task entry and exit indicator from "<<<" to "⬅".
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
- Changed: Updated prerequisite versions for "customtkinter", "ctkcolorpicker" and "pillow". Eliminated "packaging" prerequisite.
- Changed: The default dark background color has been changed to a dark gray/brown color.
- Changed: Eliminated the "-save" and "-restore" runtime options. These are replaced by the "-reset" runtime option.
- Changed: Force plug-in configuration parameters to appear on separate output lines.
- Fixed: Unable to get the program version ('-version') if the last run was with the GUI.
- Fixed: The Task action arguments were being displayed out of order.
- Fixed: Not handling Task anchors properly.
- Fixed: Removed "save" and "restore" from the display of runtime options, which caused error messages to appear in the output.
- Added: The settings are now saved in the TOML format and can be user-viewed and/or edited. If a saved file is still in the old format, it will automatically be converted.
- Added: new "tomli_w" prerequisite for TOML file settings support.
- Added: "Time Zone" to the Task action "Parse/Format DateTime".
- Added: "Configuration Parameters" for Plugin actions.
- Added: "AutoCast" plug-in recognition.
- Added: If fetching the backup XML file from the Android device, display the 'android\_...' settings in the GUI.

## [2.6.3]

- Changed: The runtime options to fetch the backup file from the Android device have changed.
  See the 'Added" section. '-backup' is no longer supported.
  If the old options exist in the saved runtime file, they will automatically be converted to the new runtime option format.
- Changed: The runtime option '-appearance' can no longer be abbreviated as '-a'.
- Changed: The old format for the saved settings that date back to the year 2022 is no longer supported.
- Changed: Updated README to reflect new '-android\_...' runtime options.
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

- Changed: The runtime options are now automatically saved on exit and restored on entry. The runtime options '-save' and '-restore' have been removed.
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
- Changed: Default display detail level (runtime option 'detail) is now 4. I was 3.
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

## 6.0 Added: support for colors as arguments -c(type)=color_name type: Task/Profile/etc

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
