# MapTasker Command Reference

MapTasker displays your Android Tasker configuration based on your uploaded Tasker XML file (e.g. 'backup.xml'). The display will optionally include all Projects, Profiles, Tasks and their actions, Profile/Task conditions and other Profile/Task related information.

Once the XML file is loaded, you can optionally edit your Projects, Profiles, Tasks, and Scenes.

This page describes each of the **93** commands, options and tabs in MapTasker's Help screen, in the same order, with more detail on each and the caveats that go with it.

_Generated from the MapTasker 15.1.0 source on 2026-10-27 by `build_command_wiki.py`._ _Do not edit this page by hand -- rerun that program instead._

## How to use this page

* **Finding a command:** the Contents below lists the commands alphabetically.  Click a name to go to its section, or press `Ctrl`/`⌘` + `F` and type any part of the name.  The sections themselves follow the order of MapTasker's own Help screen.
* **Reading a section:** each says what the command does, where it is in the window, the text MapTasker shows when you hover over it, and the dialog it opens.  Anything to watch out for -- a requirement, a limit, a command offered in only some views -- is under **Caveats**.
* **Nesting:** a command that belongs to a tab or a toolbar is listed beneath it, and says so.

## Contents

* ['?' buttons](#cmd-buttons)
* [Analyze tab](#cmd-analyze-tab)
  * [Show/Edit API Key(s)](#cmd-show-edit-api-key-s)
  * [Change Prompt](#cmd-change-prompt)
  * [Run Analysis](#cmd-run-analysis)
  * [Extended](#cmd-extended)
* [Application Settings: Restore](#cmd-application-settings-restore)
* [Application Settings: Save](#cmd-application-settings-save)
* [Assistance tab](#cmd-assistance-tab)
* [Changes Since...](#cmd-changes-since)
* [Clear](#cmd-clear)
* [Close Tabs On Exit](#cmd-close-tabs-on-exit)
* [Colors tab](#cmd-colors-tab)
  * [Reset to Default Colors](#cmd-reset-to-default-colors)
* [Compare Files](#cmd-compare-files)
* [Dark Mode](#cmd-dark-mode)
* [Detail Level](#cmd-detail-level)
* [Display Conditions](#cmd-display-conditions)
* [Display Directory](#cmd-display-directory)
* [Display Help](#cmd-display-help)
* [Display Prettier Output](#cmd-display-prettier-output)
* [Display Tasker Preferences](#cmd-display-tasker-preferences)
* [Display TaskerNet Info](#cmd-display-taskernet-info)
* [Display Views](#cmd-display-views)
* [Exit](#cmd-exit)
* [Fix Findings](#cmd-fix-findings)
* [Font To Use](#cmd-font-to-use)
* [Get Android Help](#cmd-get-android-help)
* [Get Local XML File](#cmd-get-local-xml-file)
* [Get XML from Android Device](#cmd-get-xml-from-android-device)
  * [List XML Files](#cmd-list-xml-files)
  * [Cancel Entry](#cmd-cancel-entry)
* [Health Check](#cmd-health-check)
* [Hide Task Details under Twisty](#cmd-hide-task-details-under-twisty)
* [Import With Dependencies](#cmd-import-with-dependencies)
* [Indentation](#cmd-indentation)
* [Just Display Everything](#cmd-just-display-everything)
* [Language](#cmd-language)
* [Live Run Monitor](#cmd-live-run-monitor)
* [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)
  * [Search](#cmd-search)
  * [Find/Replace](#cmd-find-replace)
  * [Ask AI](#cmd-ask-ai)
  * [Replace](#cmd-replace)
  * [Save Results](#cmd-save-results)
  * [Export](#cmd-export)
  * [Top / Bottom](#cmd-top-bottom)
  * [Toggle Wrap](#cmd-toggle-wrap)
  * [Profiles Per Line](#cmd-profiles-per-line)
  * [Zoom, Collapse All, Expand All, Reset](#cmd-zoom-collapse-all-expand-all-reset)
  * [Rebuild](#cmd-rebuild)
* [Missing Resources](#cmd-missing-resources)
* [Notification Duration](#cmd-notification-duration)
* [Open View In New Window](#cmd-open-view-in-new-window)
* [Outbound Inventory](#cmd-outbound-inventory)
* [Output Folder](#cmd-output-folder)
* [Pre-Build The Map](#cmd-pre-build-the-map)
* [Project/Profile/Task/Scene Names](#cmd-project-profile-task-scene-names)
* [Refactor > Variable](#cmd-refactor-variable)
* [Report Issue](#cmd-report-issue)
* [Reset Options](#cmd-reset-options)
* [Restore From History](#cmd-restore-from-history)
* [Specific Name tab](#cmd-specific-name-tab)
  * [Project Name](#cmd-project-name)
  * [Profile Name](#cmd-profile-name)
  * [Task Name](#cmd-task-name)
  * [Scene Name](#cmd-scene-name)
  * [List Unnamed Items](#cmd-list-unnamed-items)
  * [Add, Edit and Save](#cmd-add-edit-and-save)
    * [Add Project/Profile/Task/Scene](#cmd-add-project-profile-task-scene)
      * [Draft with AI](#cmd-draft-with-ai)
    * [Edit Project/Profile/Task/Scene](#cmd-edit-project-profile-task-scene)
    * [Rename](#cmd-rename)
    * [Delete](#cmd-delete)
    * [Add/Edit Properties](#cmd-add-edit-properties)
    * [Refactor](#cmd-refactor)
    * [Run On Android](#cmd-run-on-android)
    * [Duplicate](#cmd-duplicate)
    * [Preview](#cmd-preview)
    * [Save / Export](#cmd-save-export)
    * [Save To Current File](#cmd-save-to-current-file)
    * [Save To Android](#cmd-save-to-android)
  * [Editing Commands](#cmd-editing-commands)
    * [Undo](#cmd-undo)
    * [Redo](#cmd-redo)
    * [Edit History](#cmd-edit-history)
* [Task Action Limit](#cmd-task-action-limit)
* [Task Flow](#cmd-task-flow)
* [Task Stepper](#cmd-task-stepper)
* [Task Tests](#cmd-task-tests)
* [TaskerNet Description](#cmd-taskernet-description)
* [TaskerNet Updates](#cmd-taskernet-updates)
* [Trend Dashboard](#cmd-trend-dashboard)
* [Variable Xref](#cmd-variable-xref)
* [View Limit](#cmd-view-limit)
* [What Fires When?](#cmd-what-fires-when)
* [Command-Line Arguments](#command-line-arguments)

## Commands

<a id="cmd-detail-level"></a>
### Detail Level

**Type:** Pulldown  
**Where:** Left Drawer

How much of each Task the output shows. The levels are:

* **Level 0:** display first Task action only, for unnamed Tasks only (silent).
* **Level 1:** display all Task action details for unknown Tasks only (default).
* **Level 2:** display full Task action name on every Task.
* **Level 3:** display full Task action details on every Task with action details.
* **Level 4:** display level of 3 plus Project's global variables.
* **Level 5:** display level of 4 plus Scene argument details.

**Hover text:** 0 = least detail, 5 = most detail.

<a id="cmd-just-display-everything"></a>
### Just Display Everything

**Type:** Option  
**Where:** Left Drawer

Turns on the display of conditions, TaskerNet information, preferences, pretty output, directory, and configuration outline.

**Hover text:** Enables the display of Conditions, TaskerNet Info, Preferences, the Directory, and Prettier Output.

<a id="cmd-display-conditions"></a>
### Display Conditions

**Type:** Option  
**Where:** Left Drawer

Turn on the display of Profile and Task conditions.

**Hover text:** Enables the display of Profile Conditions (e.g. State, Event, etc.) details in the output.

<a id="cmd-display-taskernet-info"></a>
### Display TaskerNet Info

**Type:** Option  
**Where:** Left Drawer

If available, display TaskerNet publishing information.

**Hover text:** Enables the display of TaskerNet Descriptions in the output.

<a id="cmd-display-tasker-preferences"></a>
### Display Tasker Preferences

**Type:** Option  
**Where:** Left Drawer

Display Tasker's system Preferences.

**Hover text:** Enables the display a breakdown of the Tasker system Preferences in the output.

<a id="cmd-hide-task-details-under-twisty"></a>
### Hide Task Details under Twisty

**Type:** Option  
**Where:** Left Drawer

Hide Task information within ► and click to display.

**Hover text:** When enabled, Task details are hidden under a twisty (expand/collapse) control in the output.

<a id="cmd-display-directory"></a>
### Display Directory

**Type:** Option  
**Where:** Left Drawer

Display a directory of hyperlinks at the beginning of the output.

**Hover text:** Enables the display of the Project/Profile/Task/Scene Directory in the output.

<a id="cmd-display-prettier-output"></a>
### Display Prettier Output

**Type:** Option  
**Where:** Left Drawer

Make the output more human-readable by adding newlines and indentation for all arguments.

**Hover text:** Enables the display of aligned text in the output.

<a id="cmd-project-profile-task-scene-names"></a>
### Project/Profile/Task/Scene Names

Options to italicize, bold, underline and/or highlight the names of Projects, Profiles, Tasks and Scenes.

<a id="cmd-task-action-limit"></a>
### Task Action Limit

Display a warning if the Task has more than the specified number of actions.

<a id="cmd-indentation"></a>
### Indentation

**Type:** Pulldown  
**Where:** Left Drawer

The indentation amount for If/Then/Else Task Actions.

**Hover text:** Set the indentation amount for If/Then/Else blocks. The default is '4'. This affects how the output is formatted in the Map and Diagram views.

<a id="cmd-language"></a>
### Language

Select the language to be used for the output. The default is English.

<a id="cmd-font-to-use"></a>
### Font To Use

**Type:** Pulldown  
**Where:** Left Drawer

Change the monospace font used for the output.

**Hover text:** This is a list of all of the fonts available on your system, monospaced ones first and marked as such. The font selected will be used in all output. 'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector alignment.

**Caveats:**

* A font that is not monospaced will not hold the Diagram's connectors or the output's indentation in line.

<a id="cmd-view-limit"></a>
### View Limit

**Type:** Pulldown  
**Where:** Left Drawer

Control the amount of processing time used when generating the view.

**Hover text:** Select the maximum number of items to display in the view to be allowed. Anything over this amount will stop the generation of the view as a means to throttle the program.

**More detail:**

The 'View Limit' is a means to control the amount of processing time used when generating the view.

* The numbers represent the relative amount of output lines to be generated.
* The larger the limit, the larger the output that will be allowed to be mapped.  The more output that is generated, the greater the processing time.
* Very large configurations will generate very large output maps and will cause greater processing time.  On older devices, this can take up to 30 seconds or more.
* By setting a limit, you can control the processing time used when mapping a configuration by not allowing longer durations.
* If the limit is hit when calculating the map, the output will stop there.
* You can experiment with this setting to see which setting is best for your use case.
* Selecting a single Project, Profile or Task is another means to limit the processing time.

**Caveats:**

* On older devices, this can take up to 30 seconds or more.
* This is only for the 'Map' and 'Diagram' views, not the tree view.

<a id="cmd-notification-duration"></a>
### Notification Duration

**Type:** Pulldown  
**Where:** Left Drawer

How long a pop-up message stays on screen before it disappears. 'Until dismissed' keeps every message up until you close it.

**Hover text:** How long a pop-up message stays on screen before it disappears. 'Until dismissed' keeps every message up until you close it, which is useful when a message scrolls past before you can read it. A few messages set their own longer duration because they list things you have to read -- the Tasks affected by deleting or renaming a Scene element, for instance. Those keep their own timing whatever is chosen here.

<a id="cmd-dark-mode"></a>
### Dark Mode

**Type:** Option  
**Where:** Header

Switch the GUI between light and dark appearance.

**Caveats:**

* Changing the appearance mode will change the colors used for the output to their default values.

<a id="cmd-reset-options"></a>
### Reset Options

**Type:** Command  
**Where:** Right Drawer; Toolbar

Clear everything and start anew.

**Hover text:**

* **Reset Options** -- Reset all of the options to their default values, including colors, font used, and other settings. The currently loaded XML will be cleared out.
* **Reset** -- Back to the whole diagram: no zoom, nothing folded, nothing filtered.

<a id="cmd-get-local-xml-file"></a>
### Get Local XML File

**Type:** Command  
**Where:** Right Drawer

Fetch the backup/exported XML file from your local drive.

**Hover text:** Fetch XML from a local drive on this computer. The XML fetched will become the current source for MapTasker commands.

**Opens:** Local File Picker

<a id="cmd-application-settings-save"></a>
### Application Settings: Save

**Type:** Command  
**Where:** Right Drawer

Save these settings for later use.

<a id="cmd-application-settings-restore"></a>
### Application Settings: Restore

**Type:** Command  
**Where:** Right Drawer

Restore the settings from a previously saved session.

<a id="cmd-report-issue"></a>
### Report Issue

**Type:** Command  
**Where:** Right Drawer

Open the GitHub Issues page in your browser to report a problem or suggestion to the developer.

**Hover text:** Report any issues and/or suggestions to the developer. This will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.

<a id="cmd-display-views"></a>
### Display Views

Display your configuration Map, Diagram, or Tree view of your Projects, Profiles, Tasks and Scenes directly in the GUI.

**More detail:**

Display the 'Map', 'Diagram' or 'Tree' view of your configuration directly within the GUI.

XML must first be obtained from the either local drive or Android device for the views to work.

If the XML has already been fetched, it will be used as input to the view.  Hitting the 'Clear' button will clear the view data.

Very large configurations will incur extended run times for Maps and Diagrams.  For best performance, select a single Project or Profile to map.

Optionally, limit the amount of data to be processed by using the 'View Limit' setting.  The larger the limit, the larger the output that will be allowed to be mapped.  The more output that is generated, the greater the processing time.

The Diagram View has the following behavior:

* Only Projects and Profiles can be displayed. XML consisting of only a single Task or Scene will not be displayed.
* Click on a horizontal connector to highlight the entire connection in the diagram.

The Tree View has the following behavior:

* Only Projects can be displayed. XML consisting of only a single Profile or Task or Scene will not be displayed.
* All Projects, Profiles, Tasks and Scenes are displayed regardless of the single name setting.

**Caveats:**

* XML must first be obtained from the either local drive or Android device for the views to work.
* Very large configurations will incur extended run times for Maps and Diagrams.
* XML consisting of only a single Task or Scene will not be displayed.

<a id="cmd-clear"></a>
### Clear

**Type:** Command  
**Where:** AI API Key Entry; Buttons; Right Drawer (and 1 more)

Clear the Map/Diagram/Tree view data currently held and displayed.

<a id="cmd-health-check"></a>
### Health Check

**Type:** Command  
**Where:** Right Drawer

Scan the loaded XML for broken references, unreferenced Tasks, Profiles and Scenes, and naming problems. It also reports how your configuration will behave on the device: two Profiles watching the same trigger whose Tasks set the same thing opposite ways, a Profile whose conditions can never all be true, Tasks that poll in a loop, Profiles that keep a radio or sensor scanning or fire on a short timer, long-running Tasks left on the default collision handling, and actions that can block for ever because no timeout was set. Click a finding to be taken to it in the Map.

**Hover text:** Scan the loaded XML for broken references, unreferenced Tasks, Profiles and Scenes, naming problems, Task flow, variables, behaviour on the device, and secrets. You choose which of those to report before it runs, and that choice is remembered. Results are displayed here and saved to a text file in the Output Folder.

**Opens:** Health Check

<a id="cmd-fix-findings"></a>
### Fix Findings

**Type:** Command  
**Where:** Right Drawer

Repair the Health Check findings that have an obvious fix -- set a long-running Task's collision handling, give a blocking action a timeout, close an 'If' or 'For' that is never closed, point a broken 'Goto' at a label the Task actually carries, and delete a Task nothing in the file runs. You first choose which kinds of finding to fix, so only those are scanned for and listed. Every repair is listed with what it would change before anything is done, you tick only the ones you want, and however many you make it is one press of Undo afterwards.

**Hover text:** Repair the Health Check findings that have an obvious fix: set a long Task's collision handling, give a blocking action a timeout, close an 'If' that is never closed, point a broken 'Goto' at a label that exists, delete a Task nothing runs. Everything is shown before anything is done, you tick what you want, and the whole lot is one press of Undo afterwards.

**Caveats:**

* Most kinds of finding are not offered here: a broken 'Perform Task' or a password written into an action is a decision only you can make.

<a id="cmd-compare-files"></a>
### Compare Files

**Type:** Command  
**Where:** Right Drawer

Compare another XML file against the loaded one to see what was added, removed, renamed and changed.

**Hover text:** Compare another XML file against the loaded one: what was added, removed, renamed and changed. Use it to see what a TaskerNet import brought in, what an edit changed, or what is different between two backups. If the loaded file came from 'Save to Current File', the file it was saved from is offered directly. Results are displayed here and saved to a text file in the Output Folder.

**Opens:** Choose Comparison File

<a id="cmd-changes-since"></a>
### Changes Since...

**Type:** Command  
**Where:** Right Drawer

Show what has changed in your configuration since a moment you choose -- today, this week, this month, everything kept, or a specific date. Every configuration you load is kept, compressed, in the 'MapTasker_Timeline' folder in the current directory, so there is no file to find.

**Hover text:** What has changed in your configuration since a moment you choose: today, this week, this month, everything kept, or a specific date. No file to pick -- every configuration you load is kept, compressed, in a MapTasker_Timeline folder in the current directory, and the one from back then is compared against what you have open now. Results are displayed here and saved to a text file in the Output Folder.

**Opens:** Changes Since

<a id="cmd-restore-from-history"></a>
### Restore From History

**Type:** Command  
**Where:** Right Drawer

Bring back a Task, Profile or Scene that has been deleted, or put one back as it was before it was edited, from any configuration kept in that history. One object at a time: each restore is previewed before anything is done, says what it leaves for you to do (a Profile to relink, say), and is one press of Undo afterwards.

**Hover text:** Bring back a Task, Profile or Scene that has been deleted, or put one back as it was before it was edited -- from any configuration kept in the history that 'Changes Since...' reads. One object at a time, never a merge: every restore is shown before anything happens, says what it leaves for you to do (a Profile to relink, say), and is one press of Undo afterwards.

<a id="cmd-variable-xref"></a>
### Variable Xref

**Type:** Command  
**Where:** Right Drawer

Trace every %variable in the loaded XML: where each one is set, where it is read, which are read but never set, which are set but never read, and which near-identical names are likely typos.

**Hover text:** Trace every %variable in the loaded XML: where each one is set, where it is read, which are read but never set, which are set but never read, and which near-identical names (%MyVar against %Myvar) are likely typos. Searched: Task actions and their conditions, plugin configuration, Profile contexts and Scenes. Results are displayed here and saved to a text file in the Output Folder.

<a id="cmd-task-flow"></a>
### Task Flow

**Type:** Command  
**Where:** Right Drawer

Read every Task's control flow -- its If/Else/End If, For/End For, Goto and Stop -- and report what does not hold together: a block that is never closed, a Goto aimed at a label no action carries, and actions nothing can ever reach. With a single Task chosen in 'Specific Name', that Task is also drawn as a flowchart in its own window, with an arrow from every Goto to the action it lands on. Click any line of it to be taken to that action in the Map.

**Hover text:** Read every Task's control flow -- its If/Else/End If, For/End For, Goto and Stop -- and report what does not hold together: a block that is never closed, a Goto aimed at a label no action carries, and actions nothing can ever reach. With a single Task chosen in the 'Specific Name' tab, that Task is also drawn as a flowchart in its own window, with an arrow from every Goto to the action it lands on. Results are displayed here and saved to a text file in the Output Folder.

<a id="cmd-what-fires-when"></a>
### What Fires When?

**Type:** Command  
**Where:** Right Drawer

Pick a moment -- a date and time, the Wi-Fi network the device is on, the app in front and the battery level -- and see which Profiles it makes active, the order their entry Tasks start in (highest priority first), and where they collide: two Profiles whose Tasks set the same thing opposite ways, or one Task started by two Profiles at once. Anything the inputs do not describe, such as an Event, a location or a %variable, is treated as unknown, so a Profile that depends on it is shown as possible, with what it is waiting on. Click any name to be taken to it in the Map.

**Hover text:** Pick a moment -- a date and time, the Wi-Fi network the device is on, the app in front and the battery level -- and see which Profiles it makes active, the order their Tasks start in, and where they collide. Anything the inputs do not describe, such as an Event or a location, is treated as unknown, so a Profile that depends on it is shown as possible and says what it is waiting on.

**Opens:** Firesim

**Commands in it:** Now, Step

**Caveats:**

* Leave an input 'not simulated' to ignore it.

<a id="cmd-open-view-in-new-window"></a>
### Open View In New Window

**Type:** Option  
**Where:** Right Drawer

Open each Map/Diagram request in its own new window/tab rather than reusing that view's existing one.

**Hover text:** When enabled, each Map/Diagram request opens in its own new window/tab, so you can keep earlier ones up alongside it to compare. When disabled, a request reuses that view's existing window/tab, replacing what's in it.

**Caveats:**

* Leave it off unless you want to compare: a brand new window/tab is the one your browser may block, since it gets opened once the view has finished building rather than the instant you click.

<a id="cmd-close-tabs-on-exit"></a>
### Close Tabs On Exit

**Type:** Option  
**Where:** Right Drawer

Have 'Exit' also close the main MapTasker window and any Map/Diagram windows/tabs it opened.

**Hover text:** When enabled, clicking 'Exit' also closes the main MapTasker window and any Map/Diagram windows/tabs it opened. When disabled, 'Exit' shuts down MapTasker but leaves those windows/tabs open.

<a id="cmd-get-xml-from-android-device"></a>
### Get XML from Android Device

**Type:** Command  
**Where:** Right Drawer

Fetch the backup/exported XML file from Android device. You will be asked for the IP address and port number for your Android device, as well as the file location on the device.

**Hover text:** Fetch XML from an Android device.

**More detail:**

The following steps are required in order to fetch a Tasker XML file directly from your Android device.

1. Both this device and the Android device must be on the same named network.
2. The Tasker Project 'HTTP Server Example' or identical function must be installed and active on the Android device (the server must be running):

https://tinyurl.com/4p5cz8sv

That is the only setup required.  The 'List XML Files' option used to need a second, separate profile ('MapTasker List') imported from TaskerNet and left enabled; it no longer does.  MapTasker now installs a small Task named 'MapTasker List Files v1' on the device to do the listing, the same way 'App not listed?' installs one to fetch your applications.

You will be asked for the IP address, the port number for your Android device, as well as the file location on the Android device.  Default values are supplied, where...

'192.168.0.210' is the default IP address,

'1821' is the default port number for the Tasker HTTP Server Example running on your Android device

'/Tasker/configs/user/backup.xml' is the default file location.  If you don't know the file location and have already entered your IP address and port, then you can select the 'List XML Files' button to get a list of available XML files on your Android device for selection.

Usage Notes:

The IP address and port can be obtained by installing the 'HTTP Server Example' project from the above URL on your Android device. Then run the task named 'Update GD HTTP Info' to get the Android notification:

HTTP Server Info

Server info updated {"device name":"http://192.168.0.49:1821"}

* To fetch the XML file, click on the button

'Get XML from Android Device'

Then modify the default values presented in the input fields below this button, and then click on the button 'Enter and Click Here to Set XML Details' or 'List XML Files'.

* Hitting either button will ping the Android device to see if it is available.  The ping will timeout after 10 seconds if the device is not reachable.  Make sure that the IP address is correct.

Click on the 'Cancel Entry' button to back out of this fetch process.

**Caveats:**

* Both this device and the Android device must be on the same named network.
* The ping will timeout after 10 seconds if the device is not reachable.
* You must be on the same network as the Android device, and the device must be running and connected.

<a id="cmd-list-xml-files"></a>
#### List XML Files

_Part of [Get XML from Android Device](#cmd-get-xml-from-android-device)._

**Type:** Command  
**Where:** Mount List Files Row

List the XML files found on the Android device so you can select one rather than typing its location.

**More detail:**

Clicking this button will result in the following actions:

* The IP Address will be used to ping the Android device.
* The IP Address and port number will be used to query the Android device and get a list of available XML files found in the Tasker folder.
* The list of found XML files will be presented in a pulldown menu from which you can select the one you want to use.
* Once you have selected the XML file, it will be fetched and verified as valid XML which is then used as input to the program once you subsequently click on the 'Run' or 'ReRun' button.

The listing is done by a small Task named 'MapTasker List Files v1', which MapTasker installs on your Android device the first time you use this button and then leaves there.  Nothing has to be imported by hand.  It requires the 'HTTP Server Example' project running on the device and Tasker 6.2 or higher -- the same requirements 'Save to Android' has -- and Tasker will ask you to authorize the connection the first time.

Allow a few seconds: installing the Task (once), running it and reading back its answer is not instant.

**Caveats:**

* It requires the 'HTTP Server Example' project running on the device and Tasker 6.2 or higher -- the same requirements 'Save to Android' has -- and Tasker will ask you to authorize the connection the first time.
* Allow a few seconds: installing the Task (once), running it and reading back its answer is not instant.

<a id="cmd-cancel-entry"></a>
#### Cancel Entry

_Part of [Get XML from Android Device](#cmd-get-xml-from-android-device)._

**Type:** Command  
**Where:** Mount Cancel Row; Mount File Picker

Back out of the Android fetch process.

<a id="cmd-specific-name-tab"></a>
### Specific Name tab

**Type:** Tab  
**Where:** Main

Enter a single, specific named item to display.

**Caveats:**

* These four are exclusive: enter one only.

<a id="cmd-project-name"></a>
#### Project Name

_Part of [Specific Name tab](#cmd-specific-name-tab)._

Enter a specific Project to display.

<a id="cmd-profile-name"></a>
#### Profile Name

_Part of [Specific Name tab](#cmd-specific-name-tab)._

Enter a specific Profile to display.

<a id="cmd-task-name"></a>
#### Task Name

_Part of [Specific Name tab](#cmd-specific-name-tab)._

Enter a specific Task to display.

<a id="cmd-scene-name"></a>
#### Scene Name

_Part of [Specific Name tab](#cmd-specific-name-tab)._

Enter a specific Scene to display. Its owning Project's heading and the.

**Caveats:**

* Scene's elements (plus any Tasks those elements invoke) are displayed; the Project's Profiles and its other Scenes are not.

<a id="cmd-list-unnamed-items"></a>
#### List Unnamed Items

_Part of [Specific Name tab](#cmd-specific-name-tab)._

**Type:** Option  
**Where:** Main

Include unnamed Profiles and Tasks in the four pulldowns above.

**Hover text:** Select this to include Profiles and Tasks that do not have a name in the list.

<a id="cmd-add-edit-and-save"></a>
#### Add, Edit and Save

_Part of [Specific Name tab](#cmd-specific-name-tab)._

Add and Edit Projects, Profiles, Tasks and Scenes directly in the GUI, with various save options.

**Known issues:**

* Not all Task actions and Profile states or events editing are supported.  What remains unsupported is third-party plugins: their settings are an opaque payload that only the plugin's own configurator understands, so those still have to be set up inside Tasker.

<a id="cmd-add-project-profile-task-scene"></a>
##### Add Project/Profile/Task/Scene

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Main; Build

Create a new object and add it to the loaded XML.

**Opens:** Add Project, Add Scene Version

**Commands in it:** Legacy Scene

<a id="cmd-draft-with-ai"></a>
###### Draft with AI

_Part of [Add Project/Profile/Task/Scene](#cmd-add-project-profile-task-scene)._

In the Add Task window, turns a description in plain words into actions. The AI model chosen on the Analyze tab drafts actions from the ones the editor can build, and they are added to the Task unsaved, for you to review and edit. Whatever the AI suggested that MapTasker is unable to build is listed beside the draft, and a Stop button gives up on a slow model.

**Known issues:**

* It is slow and often unusable on very small local models (such as tinyllama); a larger local model or a cloud model is recommended.
* It cannot choose an Application or an icon for an action, and a plugin action it picks still has to be configured inside Tasker; both are left at their defaults for you to fill in.

<a id="cmd-edit-project-profile-task-scene"></a>
##### Edit Project/Profile/Task/Scene

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Main

Modify the object currently selected in the pulldowns above.

<a id="cmd-rename"></a>
##### Rename

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Edit Profile Buttons; Edit Project Buttons; Edit Scene Buttons (and 9 more)

Give the object being edited a new name.

**Hover text:**

* Prompts for a new name and applies just that to the loaded backup, right now. Everything else in this dialog stays pending until Ok/Save, and the dialog stays open so you can carry on editing.
* Prompts for a new name and applies it to the loaded backup, right now. The Project Name field above is read-only -- this is the only way to change it.
* Prompts for a new name and applies it to the loaded backup, right now -- renaming the Scene everywhere, including in the Scene list of every Project that holds it. The Scene Name field above is read-only -- this is the only way to change it.

**Opens:** Rename, Rename Legacy Element

**Caveats:**

* Tasks that show or hide this Scene by name are NOT updated; those still name the old Scene.

<a id="cmd-delete"></a>
##### Delete

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Delete All; Item Layout; Render (and 2 more)

Remove the object being edited from the loaded XML.

**Opens:** Build

<a id="cmd-add-edit-properties"></a>
##### Add/Edit Properties

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

The comments and variables Tasker keeps against a Project, Profile or Task, and its own settings (a Task's collision handling, for one).

<a id="cmd-refactor"></a>
##### Refactor

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Main

Make the structural changes Add, Edit and Delete cannot -- pull a run of a Task's actions out into a Task of its own, fold a Perform Task back into its caller, move a Task or Profile to another Project, or duplicate any object. Previewed before anything is done, and one press of Undo afterwards.

**Hover text:** The structural changes that Add, Edit and Delete cannot make: pull a run of a Task's actions out into a Task of their own, fold a Perform Task back into its caller, move a Task or Profile to another Project, or duplicate any object. The whole of a refactor is one press of Undo afterwards.

**Caveats:**

* Nothing is changed until you press Preview and then Apply, and the preview says what will happen step by step -- or why it will not.

<a id="cmd-run-on-android"></a>
##### Run On Android

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Main; Render Edit Task Buttons

Run the Task selected above on your Android device and see what it returned.

**Hover text:** Runs this Task on your Android device and shows what it returned, or the error. The device runs the Task as Tasker already has it: use 'Save To Android' first to run your edits.

<a id="cmd-duplicate"></a>
##### Duplicate

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Item Layout

Make a copy of the selected Scene element.

**Opens:** Build

<a id="cmd-preview"></a>
##### Preview

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Buttons; Draw Row; Main &gt; Add Scene &gt; Legacy Scene

Display the Scene being edited as it will appear.

<a id="cmd-save-export"></a>
##### Save / Export

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Right Drawer; Toolbar

Write the object out to a standalone XML file of your choosing.

**Hover text:** **Save** -- Save these settings for later use.

<a id="cmd-save-to-current-file"></a>
##### Save To Current File

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Add Profile Buttons; Build; Buttons (and 6 more)

Write the entire configuration to a new, timestamped file beside the loaded one.

**Hover text:**

* Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Profile added to its Project, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.
* Saves the entire backup -- every Project, Profile and Task in it, not just this Profile -- with this dialog's edits applied, the same ones 'Ok' would keep. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.
* Saves the entire backup -- every Project, Profile and Task in it, not just this Project -- including every edit made anywhere in this session. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<a id="cmd-save-to-android"></a>
##### Save To Android

_Part of [Add, Edit and Save](#cmd-add-edit-and-save)._

**Type:** Command  
**Where:** Add Profile Buttons; Edit Profile Buttons; Edit Project Buttons (and 3 more)

Write the object back to your Android device -- 'Save As File' puts it on the device as a file, and 'Import Into Tasker' hands it to Tasker itself (a Task goes straight in; a Profile, Project or Scene opens Tasker's import screen).

**Hover text:**

* This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration. Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.
* This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration. Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.
* This will write the Project, and everything in it -- every Profile and Task -- as a standalone file onto your Android device, under /Tasker/projects -- it does not import it into Tasker's live configuration. Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

**Opens:** Save Profile To Android, Save Project To Android, Save Scene To Android, Save To Android

**Commands in it:** Verify, Check IDs, Save As File, Import Into Tasker

**Caveats:**

* A safety copy of anything a save is about to overwrite is kept in the 'MapTasker_Backups' folder.
* The 'Http Server Example' Tasker Project (http://spoo.me/http_svr_example) must be installed and active on the Android device, with the server running (see the README's Direct XML Retrieval notes).
* The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.
* You must exit and restart Tasker to see an imported Task in the Tasker UI.

<a id="cmd-editing-commands"></a>
#### Editing Commands

_Part of [Specific Name tab](#cmd-specific-name-tab)._

Reverse and review the changes made to the loaded XML.

<a id="cmd-undo"></a>
##### Undo

_Part of [Editing Commands](#cmd-editing-commands)._

**Type:** Command  
**Where:** Item Layout; Main

Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. This changes what is loaded, not any file.

**Hover text:** Take back the last change made to the loaded XML -- an edit, an Add, a Delete or a Rename, in any of the Edit panels. This changes what is loaded, not any file: nothing on disk or on the Android device is touched.

**Opens:** Build

<a id="cmd-redo"></a>
##### Redo

_Part of [Editing Commands](#cmd-editing-commands)._

**Type:** Command  
**Where:** Main

Reapply the change most recently backed out by 'Undo'.

<a id="cmd-edit-history"></a>
##### Edit History

_Part of [Editing Commands](#cmd-editing-commands)._

**Type:** Command  
**Where:** Main

List every change made to the loaded XML this session, newest first.

**Opens:** Edit History

<a id="cmd-colors-tab"></a>
### Colors tab

**Type:** Tab  
**Where:** Main

Select colors for various elements of the display. (e.g. color for Projects, Profiles, Tasks, etc.).

**Caveats:**

* Changing the appearance mode will change the colors used for the output to their default values.

<a id="cmd-reset-to-default-colors"></a>
#### Reset to Default Colors

_Part of [Colors tab](#cmd-colors-tab)._

**Type:** Command  
**Where:** Main

Restore every color to its default value.

<a id="cmd-analyze-tab"></a>
### Analyze tab

**Type:** Tab  
**Where:** Main

Run the analysis for a Project, Profile, Task or Scene against an Ai model.

**More detail:**

The Analyze tab is used to run the Ai analysis on your Profile, using either the local llama model or the server-based Open AI, Claude or Gemini models.

The following steps are required in order to run AI against your Profile.

1. If using a server-based AI, you must have a valid API key from the provider (e.g. OpenAI).  You can use the 'Show/Edit API Key(s)' button to enter your key(s).
2. The default prompt is: 'suggest improvements in performance and readibility: (your project/profile/task)', and is automatically preceded by: 'Given the following (Project/Profile/Task) in Tasker, '.  If modifying the prompt, you are only modifing the 'suggest improvements...' portion.
3. Select the model you want to use.
    * The model selected will determine with which AI the analysis is to be performed.
4. Click the 'Run Analysis' button.  It will turn green when all of the necessary data has been entered.
    * If you have not yet selected a model, prompt or single Project, Profile or Task, or valid API key, then you will be prompted to do so first.
    * The process may take some time and runs in the background.  The results will appear in a separate window.
    * Local models not yet loaded onto your computer will be loaded in the background once the analysis begins.

Your designated api-keys (if any), model, selected Project, Profile or Task and Ai prompt will all be saved across sessions.

The 'Rerun' feature will be used under-the-covers to display the results of the analysis in a new window.

**Caveats:**

* If using a server-based AI, you must have a valid API key from the provider (e.g. OpenAI).
* If modifying the prompt, you are only modifing the 'suggest improvements...' portion.

<a id="cmd-show-edit-api-key-s"></a>
#### Show/Edit API Key(s)

_Part of [Analyze tab](#cmd-analyze-tab)._

Enter or change the API keys used by the server-based AI models.

**More detail:**

This menu is where you define your AI API keys for use by the AI 'Analyze' button.

The keys are saved across sessions.

The keys are used to access the OpenAI, Claude AI and Gemini AI server-based models.

Click on the 'Clear' button to clear a specific API key entry.

Select 'Ok' to save the changes or 'Cancel' to back out of the changes.

<a id="cmd-change-prompt"></a>
#### Change Prompt

_Part of [Analyze tab](#cmd-analyze-tab)._

**Type:** Command  
**Where:** Main

Modify the prompt sent to the AI model.

**Opens:** Ai Prompt

<a id="cmd-run-analysis"></a>
#### Run Analysis

_Part of [Analyze tab](#cmd-analyze-tab)._

**Type:** Command  
**Where:** Main

Submit the selected Project/Profile/Task and prompt to the selected model.

<a id="cmd-extended"></a>
#### Extended

_Part of [Analyze tab](#cmd-analyze-tab)._

**Type:** Option  
**Where:** Main

List all available models rather than just the default set.

**Hover text:** Display an extended list of ALL available models. Note: Not all models have been validated and one or more may return an error on analysis. Note: Enabling this option for the first time will force the installation of the following modules and all of their dependencies: google-genai, anthropic, openai, ollama

**Caveats:**

* If the API key is not set for OpenAI or Gemini, then the default model list for the respective AI provider will be displayed.

<a id="cmd-assistance-tab"></a>
### Assistance tab

**Type:** Tab  
**Where:** Main

Display Help and Get Android Help, the Display Runtime Settings option, Debug mode, and the notification log.

<a id="cmd-map-diagram-tree-view-toolbar"></a>
### Map / Diagram / Tree View Toolbar

The commands on the toolbar of the Map, Diagram and Tree views.

<a id="cmd-search"></a>
#### Search

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

Highlight every instance of the case-insensitive text entered in the search box, up to the first 200. Click a line number to go to that line.

<a id="cmd-find-replace"></a>
#### Find/Replace

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

**Type:** Command / Tab  
**Where:** Find / Replace; Find / Replace (Replace Tab)

Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

**Caveats:**

* Map and Diagram only.

<a id="cmd-ask-ai"></a>
#### Ask AI

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

**Type:** Command  
**Where:** Find / Replace

Type the question in plain words, and the AI model selected on the Analyze tab fills in the Find boxes for you. The search itself runs exactly as if you had picked them. This is in the Find/Replace window.

<a id="cmd-replace"></a>
#### Replace

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

**Type:** Command / Tab  
**Where:** Find / Replace; Find / Replace (Replace Tab)

Change what Find finds -- swap one Task action for another, rewrite an action's argument, replace a Profile condition, or rename a variable everywhere it is used. Every change is listed first, you tick the ones you want, and the whole lot is one press of Undo. This is in the Find/Replace window.

<a id="cmd-save-results"></a>
#### Save Results

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

**Type:** Command  
**Where:** Find / Replace

Save the 'Find/Replace' results to a text file.

<a id="cmd-export"></a>
#### Export

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

Save what the view shows to a file in the current directory, as Markdown, JSON or PDF.

**Caveats:**

* Map and Diagram only.

<a id="cmd-top-bottom"></a>
#### Top / Bottom

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

Jump to the beginning or the end of the displayed output.

<a id="cmd-toggle-wrap"></a>
#### Toggle Wrap

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

Turn line wrapping on or off in the displayed output.

<a id="cmd-profiles-per-line"></a>
#### Profiles Per Line

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

The number of Profiles drawn side-by-side on a single line.

**Caveats:**

* Diagram only.

<a id="cmd-zoom-collapse-all-expand-all-reset"></a>
#### Zoom, Collapse All, Expand All, Reset

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

Zoom the diagram in or out, fold every Project down to its title bar or open them all again, or go back to the whole diagram with nothing zoomed or folded.

**Caveats:**

* Diagram only.

<a id="cmd-rebuild"></a>
#### Rebuild

_Part of [Map / Diagram / Tree View Toolbar](#cmd-map-diagram-tree-view-toolbar)._

Offered when the Diagram was drawn for a different selection than the one chosen now; it draws the Diagram again for the current one.

**Caveats:**

* Diagram only.

<a id="cmd-display-help"></a>
### Display Help

**Type:** Command  
**Where:** Main

Display this help text.

<a id="cmd-get-android-help"></a>
### Get Android Help

**Type:** Command  
**Where:** Main

Display the help for fetching the XML file from your Android device.

<a id="cmd-buttons"></a>
### '?' buttons

Display the help specific to the section in which the button appears.

<a id="cmd-exit"></a>
### Exit

**Type:** Command  
**Where:** Right Drawer

Exit the program (quit).

<a id="cmd-output-folder"></a>
### Output Folder

Reports (Health Check, Fix, Find, Compare and the rest), view exports and the Map/Diagram files are written to the 'Output Folder' set in the settings drawer. Left empty, that is a 'MapTasker' folder in your Documents folder.

<a id="cmd-taskernet-updates"></a>
### TaskerNet Updates

**Type:** Command  
**Where:** Right Drawer

Link a Project, Profile, Task or Scene to the TaskerNet share it came from (paste the share's address and say which of yours it is), and MapTasker tells you when its author publishes a newer version -- when you start it, and whenever you press Check Now.

* Review lists what the author changed, each with a Take this button that previews the change before anything happens and is one press of Undo afterwards.
* What is taken is the author's version of that Task, Profile or Scene, except that a Profile stays as switched on or off as you had it.
* Accept Latest Version takes everything listed in one go instead, with no preview of its own (one press of Undo takes it back).
* Only the address of each linked share is sent to taskernet.com; nothing from your configuration leaves your computer.
* An update is someone else's automation that will run on your phone, so read each preview before you take it.
* The scan runs in the background -- close the window and carry on -- and a notification tells you when it is done.
* Stop ends the reading of TaskerNet's list early and compares yours with the part already read; Select All and Deselect All tick the whole list of possible matches.
* Each linked share shows when it was last checked, and Check Now ignores the 6 hours and checks every one.

**Hover text:** Link a Project, Profile, Task or Scene to the TaskerNet share it came from, and find out when its author publishes a newer version. Shows what the author changed and lets you take each change on its own, previewed first and one press of Undo afterwards. Only the address of each linked share is sent to taskernet.com; nothing from your configuration leaves this computer.

**Caveats:**

* Find Links searches TaskerNet's public shares for the ones your Projects, Profiles, Tasks and Scenes came from and links those whose content agrees with yours -- a name alone is not enough, as different authors reuse names; partial matches are listed for you to tick.
* Linked shares are also checked for a newer version automatically, without pressing Check Now: once when MapTasker starts and again each time the TaskerNet Updates window is opened, but only for a share that was last checked more than 6 hours ago.
* A check is not repeated on a timer, so a MapTasker left running for days will not look again until the window is opened or Check Now is pressed.
* A check reads only the share's publish date, changes nothing in your configuration, and when it fails the date of the last successful check is not replaced.

**Known issues:**

* It matches Tasks and Profiles by name, so one the author renames, or one with no name, can show up as new rather than changed.
* The first time you link a share, differences caused by Tasker rewriting it on import are listed along with real ones; later updates list only what the author changed.

<a id="cmd-task-stepper"></a>
### Task Stepper

**Type:** Command  
**Where:** Right Drawer

Dry-run one Task. Pick it, say what its variables hold when it starts (Suggest Inputs lists the ones it reads before it sets them), and press Step: it walks the Task action by action and shows which If, Else If, For and Goto branches it takes, which actions it skips, and what every variable holds after each step. Nothing runs on your phone and nothing in the configuration changes; each Task in What Fires When? has a Step button that opens it here.

**Hover text:** Dry-run one Task: pick it, say what its variables hold when it starts, and see which If, Else If, For and Goto branches it takes and what every variable holds after each action. Nothing is run on your phone and nothing in the configuration changes.

**Caveats:**

* Variable Set, Add, Clear and Split, and the conditions Tasker's If offers, are simulated; Flash, Notify and the like are shown with their variables filled in; anything that talks to the outside world is listed as not simulated, and a variable it may have set is unknown.
* A condition that depends on a variable with no value stops the walk and names it -- or is treated as not set, true or false, as you choose -- and what an action that is not simulated leaves behind can be typed in (5: %name = value).
* A Perform Task is walked into -- the called Task's actions appear indented under the call, it is given %par1 and %par2, shares the globals, and hands back its Return value (and its locals, if its Return passes them through) -- unless 'Follow Perform Task' is cleared, or the Task cannot be found, is named by a variable with no value, or is nested more than 8 deep, in which case the call is shown and its result is unknown.
* Actions that talk to the outside world are listed as 'not simulated', and a variable one of them may have set is treated as unknown rather than guessed.

<a id="cmd-trend-dashboard"></a>
### Trend Dashboard

**Type:** Command  
**Where:** Right Drawer

Is your configuration getting healthier or messier?

* Every configuration you load is kept (see Changes Since...); this measures each one -- how long the longest Task is and how many are over 100 actions, how deeply If and For blocks nest, how many Perform Tasks deep the longest chain of calls goes, and what the Health Check finds -- and shows each number over time with a sparkline, for the whole configuration or for one Project.
* It says 'healthier' when something fell and nothing rose, 'messier' when something rose and nothing fell, and 'about the same' otherwise; size is shown but never judged.
* Each configuration is measured once and the figures are kept, so only the first look is slow.
* The check for plugins missing from your device is left out, as it asks the device and not the backup.
* From the command line, -trend [-file backup.xml] [-project NAME] prints the same report and exits with 10 when the newest backup is messier than the one before.

**Hover text:** Is your configuration getting healthier or messier? Measures every configuration the history has kept -- Task length, nesting depth, how deep Perform Task calls go, and what the Health Check finds -- and shows each number over time, for the whole configuration and for each Project. Each configuration is measured once and the figures are kept, so only the first look is slow.

<a id="cmd-refactor-variable"></a>
### Refactor > Variable

Rename a variable everywhere it is used, or change it between global and local.

* Tasker reads the scope from the spelling -- all lower case is local to the running Task, any capital makes it a global shared by everything -- so Make local and Make global change who can see the value, and the preview checks it first.
* It reads the whole configuration whatever is selected above, and refuses (naming the place) when the new name is already a variable, when a Scene or a Profile's condition reads a global you are making local, or when a Task reads it before setting it.
* Several Tasks that shared a global each get a copy of their own, and a local made global is shared by every Task: the preview says both.
* Previewed before anything is done, and one press of Undo afterwards.

<a id="cmd-missing-resources"></a>
### Missing Resources

**Type:** Command  
**Where:** Right Drawer

Do the files, folders, images, sounds, Scenes and apps your Tasks and Profiles use still exist on your Android device? Press Check Device and MapTasker asks the device -- it puts a small helper Task there, hands it the list of paths to test, fetches the installed apps and asks Tasker for its Scenes -- then lists what the device does not have, with every action or Profile that uses each one (click a line to go to it). The Health Check reports the same as RESOURCE-MISSING from the last check, and says when it was made. Nothing is changed on the device but the helper Task and two small files in its Tasker folder, and nothing in your configuration changes.

**Hover text:** Do the files, folders, images, sounds, Scenes and apps your Tasks and Profiles use still exist on your Android device? Asks the device and lists the ones it does not have, with every place that uses each. The Health Check reports the same findings from the last time you checked.

**Caveats:**

* A path built from a variable, a wildcard and a web or content address cannot be tested and are listed as not checked; a path an action writes to is not tested, as it is not meant to exist yet; a ringtone, a Tasker icon and the images inside a Scene are not looked at.
* Something is called missing only when every device you have checked lacks it.
* Tasker must be running with the HTTP Server Example project active, and the device asks you to authorize the connection.

<a id="cmd-live-run-monitor"></a>
### Live Run Monitor

**Type:** Command  
**Where:** Right Drawer

Watch which Profiles and Tasks fire on your Android device as they do.

* Press Start and MapTasker puts a small helper Task on the device that looks at Tasker's own list of running Tasks and active Profiles several times a second and reports them back every few seconds; what became active, what started and what finished is logged (click a line to go to it), and with the Diagram open each is lit up there while it is on -- green while running or active, amber for a few seconds after -- and the Diagram scrolls to what has just fired.
* Open Diagram builds the Diagram for the one Project everything seen so far belongs to, or for the whole configuration, whatever is selected in the main window.
* Compare With What Fires When asks that feature which Profiles it says are active at the moment of the last look, and shows where the device disagrees.
* It is sampling and not a feed, so a Task that runs for less than the gap between looks can be missed, and Tasker reports names, so two objects with one name light together.
* Needs the interactive Diagram for the lights, and Tasker running with the HTTP Server Example project active.
* Closing it stops the monitoring.
* Nothing on the device is changed but the helper Task.

**Hover text:** Watch which Profiles and Tasks fire on your Android device as they do, and see them light up in the Diagram. Compare what the device really has active with what What Fires When predicted for the same moment. It samples several times a second, so a Task that runs for a moment can be missed. Nothing on the device is changed but one small helper Task.

<a id="cmd-pre-build-the-map"></a>
### Pre-Build The Map

**Type:** Option  
**Where:** Right Drawer

Build the Map in the background as soon as a file has been loaded, and again each time you choose a different single Project, Profile, Task or Scene (or go back to none), so that the Map button has nothing left to do and the Map opens at once. It builds only while nothing else is being shown, and with the settings the window holds then: change one of them (or edit the configuration) before pressing Map and the Map is built again, as it would have been without this. Pressing Map or Diagram while it is still building waits for it to finish. Off by default, because it uses the computer for a few seconds after every file is loaded or item chosen, whether or not you go on to ask for the Map.

**Hover text:** When enabled, the Map is built in the background as soon as a file has been loaded, and again each time you choose a different single Project, Profile, Task or Scene, so the Map button opens it at once. When disabled, the Map is built when you ask for it. Pressing Map or Diagram while it is still building waits for it to finish. Changing a setting, or editing the configuration, before you press Map means it is built again. It uses the computer for a few seconds after each file is loaded or item chosen, whether or not you go on to ask for the Map.

<a id="cmd-import-with-dependencies"></a>
### Import With Dependencies

**Type:** Command  
**Where:** Right Drawer

Bring a Project, Profile, Task or Scene in from another backup together with everything it needs.

* Choose the other file, find what you want in the list, and press Preview on its row.
* A Task brings the Tasks it performs and the Scenes it shows; a Scene brings the Tasks its elements run; a Profile brings the Tasks it runs; a Project brings everything it lists -- and in each case what those need in turn, and the global variables they use.
* The preview says what will be copied, what will be used instead because this file already has the same thing, and what will be copied under a new name -- 'Setup (imported)' -- because this file has a different Task of the same name; every call inside what is brought is then pointed at the new name, so it does what it did where it came from.
* Tasks and Profiles get new ids, and every link to them follows.
* Choose where they are filed: a Project of this file, or a new one.
* Nothing already in this file is changed apart from that Project listing more members, and the import is one press of Undo.
* Importing the same thing again brings nothing the second time.
* Not followed: a call whose name is built from a variable, and what is inside a Version 2 Scene's layout.
* Plugins the objects use are listed, but not checked.
* Nothing is sent anywhere.

**Hover text:** Bring a Project, Profile, Task or Scene in from another backup together with everything it needs: the Tasks it performs, the Scenes it shows and the Tasks those run, and the global variables they use. Shows what would be copied, renamed and left alone before anything happens. A Task or Scene this file already has, and that is identical, is used rather than copied. Nothing already in this file is changed, and the whole import is one press of Undo.

**Opens:** Local File Picker

<a id="cmd-task-tests"></a>
### Task Tests

**Type:** Command  
**Where:** Right Drawer

Keep a Task Stepper run as a named test, and run every test again after each edit.

* Step a Task with the values it starts with and press Save As Test: you choose the name, which of the variables the Task set to keep, whether to keep what it showed, said and sent (the text of each Flash, notification and web request, with the variables filled in), and whether to keep the route it took (off by default, because it also fails when an action is added above a branch).
* Task Tests lists every saved test and runs them all when it opens; a test that no longer passes says in words what moved -- a variable that is now a different value, an action that no longer happens or has changed.
* Keep New Result saves what the Task does now in the test's place, for a change you meant, and Delete All removes every test listed, after asking.
* Tests are found by the Task's name and kept in MapTasker_TaskTests.json in the current directory.
* A test of a Task that reads a global variable uses the value the backup holds, so it also notices when that moves.
* Nothing is run on your phone.

**Hover text:** Run the tests you have saved from the Task Stepper: a Task, the values it started with and what it did -- how it ended, the variables it set, and what it showed and sent. They are run again after every edit, Fix Findings pass, refactor or import, and you are told if a Task no longer does what it did.

**Caveats:**

* They are run again by themselves after every edit, Fix Findings pass, refactor, restore, import, Undo and Redo, and you are told only if one fails.
* A test whose Task is not in the open file is counted apart from a failure.

<a id="cmd-outbound-inventory"></a>
### Outbound Inventory

**Type:** Command  
**Where:** Right Drawer

One report of everything the loaded configuration reaches outside the phone with, Project by Project.

* It lists every Task action that sends a web request or downloads (HTTP Request, Get, Post, Head, Browse URL, HTTP Auth, Ping, Google Drive), sends or composes an SMS, MMS or email, makes a call or diverts calls, runs a shell command, runs a command as root, sends an Intent, or is one of the plugin actions that go online, and says where each one goes.
* Click any line to see that action in the Map view.
* An action that is turned off is listed and not counted.
* An address written in some other action, such as a Variable Set holding a server, is listed apart because a later request may use it.
* Nothing is contacted and nothing on your phone is changed.

**Hover text:** List everything the configuration reaches outside the phone with, Project by Project: every URL and host it contacts, and every SMS, call, shell command, root command and Intent it sends. The actions worth a look come first -- a command run as root, a request over plain http, an address built from a variable, an action carrying a key or password. Keys found in an address are replaced in the report. Results are displayed here and saved to a text file in the Output Folder.

**Caveats:**

* It opens with a count of each kind and the actions worth a look -- a command run as root, a request over plain http to somewhere that is not your own network, an address built from a variable, an action carrying a key or password -- then every host contacted and how many places use it, then the full list by Project and Task.
* Keys and passwords found in an address or command are replaced by a placeholder in the report, so it is safer to share than the backup, but a secret with no recognizable shape is not found.

<a id="cmd-taskernet-description"></a>
### TaskerNet Description

Add or edit the description anybody sees before importing a Project, Profile or Task from TaskerNet.

* Every Add and Edit dialog for those three has an Add TaskerNet Description button (Edit TaskerNet Description once there is one) beside its Properties button.
* Tasker says only that a description can use HTML formatting and some small images, so plain text works too.
* The window has a button for each tag real TaskerNet descriptions use -- bold, italic, underline, color, code, paragraph, line break, rule, bullets, numbers, headings, link, image and table -- which wrap whatever is selected in the box, or put a placeholder there for you to type over.
* Nothing blocks Ok, so a description with a problem is kept and the problem is said again.
* Clear then Ok takes the description off the object.
* For a Task or a Profile the description is kept with the other changes in the dialog and saved with them; for a Project being edited it reaches the loaded backup as soon as you press Ok, as Properties do.
* Search categories and the other TaskerNet flags already on an object are never changed.
* Nothing is sent to TaskerNet or your phone.

**Caveats:**

* Link and Image use the address typed below the box, and Add Line Breaks puts a <br/> on every line that does not already end a tag, since a line end in HTML is only a space.
* As you type, the HTML is checked: an unclosed tag, a tag nothing else uses, a script, an event handler or a link that is not to a web page, an email address or a TaskerNet share (taskershare://), and an image stored inside the description rather than linked to, which Tasker's 'small images' does not allow.
* Below it is a preview made by the code that draws the Map, so it shows what the Map will show; TaskerNet's own page is not drawn here and may differ.

## Command-Line Arguments

MapTasker can also be run from a terminal, where these arguments do the same job the settings above do in the window:

```
maptasker [arguments]
```

| Argument | Choices | What it does |
| --- | --- | --- |
| `-ai_model` | the available AI models | The model to use for Profiles and Tasks Ai analysis. |
| `-android_file` |  | File location of Tasker backup file on Android device<br>Example: -a-android_file /Tasker/configs/user/backup.xml<br>Also requires -android_ipaddr and -android_port arguments |
| `-android_ipaddr` |  | TCP/IP Address of Android device running Tasker server<br>Example: -android_ipaddr 192.168.0.210<br>Also requires -android_port and -android_file arguments |
| `-android_port` |  | Port number of Android device running Tasker server<br>Example: -android_port 1821<br>Also requires -android_ipaddr and -android_file arguments |
| `-appearance` | system, light, dark | Display appearance mode: system (default), light, dark<br>Example: -appearance dark |
| `-c<code>` |  | Provide a valid color for one kind of item in the output.  Example: -cp Blue |
| `-ch`, `-colorhelp` |  | Display a list of valid color names. |
| `-conditions` |  | Display the condition(s) for Profiles and Tasks |
| `-debug` |  | Print and log debug information |
| `-detail` | 0, 1, 2, 3, 4, 5 | Level of detail to display:<br>0 = display simple Project/Profile/Task/Scene names only with no details<br>1 = display all Task action details for unknown Tasks only<br>2 = display full Task action name on every Task<br>3 = display full Task action details on every Task with action details<br>4 = detail level 3 plus global variables<br>5 = detail level 4 plus Scene element UI details (default).<br>Example: '-detail 2' for Task action names only |
| `-directory` |  | Display a directory of hotlinks for all Projects/Profiles/Tasks/Scenes. |
| `-e`, `-everything` |  | Display everything: full detail, Profile/Task conditions,<br>TaskerNet information, directory, etc.. |
| `-file` |  | Directory and file name of Tasker XML file to analyze.<br>Example: -file ~/Downloads/backup.xml |
| `-font` |  | Name of monospaced font to use in output (default = 'Courier').<br>Enter font name of 'help' for a list of valid fonts. |
| `-g`, `-gui` |  | Prompt for (these) settings via the graphical user interface (GUI):<br>This argument overrides all other arguments. |
| `-i`, `-indent` |  | Number of spaces to indent Task If/Then/Else Actions (default = 4) |
| `-names` | bold, highlight, underline, italicize | Display all Projects/Profiles/Tasks/Scenes in bold, underlined, italicized and/or highlighted text.<br>Example: names underline italicize |
| `-o`, `-outline` |  | Display configuration outline of Projects, Profiles, Tasks and Scenes, and<br>display the configuraion Map (MapTasker_map.txt) in the default text editor" |
| `-outdir` |  | Folder to write reports, exports and the Map/Diagram files to<br>(default = a MapTasker folder in your Documents folder).<br>Example: -outdir ~/MapTasker_Reports |
| `-preferences` |  | Display Tasker preferences |
| `-pretty` |  | Make output prettier (one argument/parameter per line) |
| `-profile` |  | Display the details for a specific Profile only. |
| `-project` |  | Display the details for a specific Project only. |
| `-reset` |  | Reset previously saved arguments...start fresh. |
| `-runtime` |  | Display all runtime arguments/settings at the top of the output. |
| `-scene` |  | Display the details for a single Scene only (forces minimum of "-detail 3"). |
| `-task` |  | Display the details for a single Task only (forces minimum of "-detail 3"). |
| `-taskernet` |  | Display any TaskerNet information for Projects/Profiles. |
| `-twisty` |  | Hide Task's details under 'twisty' ➤. Click on twisty to display details. |
| `-v`, `-version` |  | Display the program version and license information. |

---

This page is generated from the MapTasker source by [`build_command_wiki.py`](https://github.com/mctinker/Map-Tasker/blob/Master/Misc%20Utilities/build_command_wiki.py). To refresh it after commands are added or changed:

```
python tools/misc/build_command_wiki.py --publish
```
