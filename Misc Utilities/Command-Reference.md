# MapTasker Command Reference

Every command, option and pulldown in the MapTasker user interface: **328** entries (**266** of them commands) across **14** windows.

_Generated from the MapTasker 13.1.0 source on 2026-09-03 by `build_command_wiki.py`._ _Do not edit this page by hand -- rerun that program instead._

## How to use this page

* **Searching:** press `Ctrl`/`⌘` + `F` and type any part of a command's name. Every command appears twice -- once in the alphabetical index, once in full under its window -- so a search always lands on something.
* **Reading a path:** commands are written as the clicks that get you there. `Edit Profile > Save To Android > Import Into Tasker` means click **Edit Profile**, then **Save To Android** in the dialog that opens, then **Import Into Tasker**.
* **Kinds:** _Command_ is a button, _Menu item_ sits in a pulldown menu, _Option_ is a checkbox or switch, _Pulldown_ is a list to choose from, and _Tab_ switches panels.
* **Descriptions** are the text MapTasker shows when you hover over the command.  Where a command has no hover text, the description comes from MapTasker's own Help, or from the note written beside it in the source -- which is said, where that is so.

## Contents

* [Command Index (A-Z)](#command-index-a-z)
* [Main Window](#main-window)
* [AI API Key Entry](#ai-api-key-entry)
* [Action Condition](#action-condition)
* [Choose An If Variant](#choose-an-if-variant)
* [Delete Project](#delete-project)
* [Delete Scene](#delete-scene)
* [Item Layout Designer](#item-layout-designer)
* [Map / Diagram / Tree View Toolbar](#map-diagram-tree-view-toolbar)
* [New Version Notice](#new-version-notice)
* [Object Properties](#object-properties)
* [Overwrite Confirmation](#overwrite-confirmation)
* [Render Scene](#render-scene)
* [Scene Preview Window](#scene-preview-window)
* [Scene Properties](#scene-properties)
* [Command-Line Arguments](#command-line-arguments)

## Command Index (A-Z)

| Command | Kind | Where it is | What it does |
| --- | --- | --- | --- |
| [Actions](#cmd-actions) | Option | Scene Preview Window | Show what each component does when tapped, and what it writes to. |
| [Add](#cmd-add) | Command | Item Layout Designer | Adds an element on top of the stack, in the middle of the Scene. |
| [Add](#cmd-add-scene-legacy-scene-add) | Command | Add Scene &gt; Legacy Scene | Adds inside the selected component if it can hold children, otherwise directly after it. |
| [Add](#cmd-edit-scene-add) | Command | Edit Scene | Adds inside the selected component if it can hold children, otherwise directly after it. |
| [Add it where missing](#cmd-find-replace-add-it-where-missing) | Option | Map / Diagram / Tree View Toolbar &gt; Find/Replace | Tasker leaves out an argument nobody ever set, so this is what makes "give every Flash a Timeout" reach the Flashes that have none. |
| [Add Profile](#cmd-add-profile) | Command | Main Window | Create a new object and add it to the loaded XML. |
| [Add Project](#cmd-add-project) | Command | Main Window | Create a new object and add it to the loaded XML. |
| [Add Scene](#cmd-add-scene) | Command | Main Window | Create a new object and add it to the loaded XML. |
| [Add Task](#cmd-add-profile-add-task) | Command | Add Profile | Create a new object and add it to the loaded XML. |
| [Add Task](#cmd-add-task) | Command | Main Window | Create a new object and add it to the loaded XML. |
| [Add Task](#cmd-edit-profile-add-task) | Command | Edit Profile | Create a new object and add it to the loaded XML. |
| [AI Model](#cmd-ai-model) | Pulldown | Main Window | Select the model belonging to the AI you wish to use. |
| [Analyze](#cmd-analyze) | Tab | Main Window | Run the analysis for a Project, Profile, Task or Scene against an Ai model. |
| [Apply to Task](#cmd-apply-to-task) | Command | Render Scene | Puts these action edits into the loaded configuration now, without closing -- the same as 'Ok' in the Edit Task dialog. |
| [Bounds](#cmd-bounds) | Option | Scene Preview Window | Outline every component and name it, the way the designer's tree names it. |
| [Cancel](#cmd-add-cancel) | Command | Item Layout Designer &gt; Add | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-cancel) | Command | Add Profile &gt; Add Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-pick-cancel) | Command | Add Profile &gt; Add Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-pick-icon-not-listed-cancel) | Command | Add Profile &gt; Add Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-save-to-android-cancel) | Command | Add Profile &gt; Add Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-cancel) | Command | Add Profile | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-pick-cancel) | Command | Add Profile &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-pick-icon-not-listed-cancel) | Command | Add Profile &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-save-to-android-cancel) | Command | Add Profile &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-project-cancel) | Command | Add Project | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-scene-cancel) | Command | Add Scene | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-scene-legacy-scene-add-cancel) | Command | Add Scene &gt; Legacy Scene &gt; Add | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-scene-legacy-scene-cancel) | Command | Add Scene &gt; Legacy Scene | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-scene-legacy-scene-pick-cancel) | Command | Add Scene &gt; Legacy Scene &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-scene-legacy-scene-rename-cancel) | Command | Add Scene &gt; Legacy Scene &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-cancel) | Command | Add Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-pick-cancel) | Command | Add Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-pick-icon-not-listed-cancel) | Command | Add Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-save-to-android-cancel) | Command | Add Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel) | Command | Main Window | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-2) | Command | AI API Key Entry | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-3) | Command | Action Condition | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-4) | Command | Choose An If Variant | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-5) | Command | Delete Project | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-6) | Command | Delete Scene | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-7) | Command | Object Properties | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-8) | Command | Overwrite Confirmation | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-9) | Command | Scene Properties | Puts these properties back the way they were when this window opened, and drops the actions of any Task edited under the Event tab. |
| [Cancel](#cmd-change-prompt-cancel) | Command | Change Prompt | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-compare-files-cancel) | Command | Compare Files | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-cancel) | Command | Edit Profile &gt; Add Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-pick-cancel) | Command | Edit Profile &gt; Add Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-pick-icon-not-listed-cancel) | Command | Edit Profile &gt; Add Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-save-to-android-cancel) | Command | Edit Profile &gt; Add Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-cancel) | Command | Edit Profile | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-delete-profile-cancel) | Command | Edit Profile &gt; Delete Profile | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-pick-cancel) | Command | Edit Profile &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-pick-icon-not-listed-cancel) | Command | Edit Profile &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-rename-cancel) | Command | Edit Profile &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-save-to-android-cancel) | Command | Edit Profile &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-project-cancel) | Command | Edit Project | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-project-rename-cancel) | Command | Edit Project &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-project-save-to-android-cancel) | Command | Edit Project &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-scene-add-cancel) | Command | Edit Scene &gt; Add | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-scene-cancel) | Command | Edit Scene | Closes without saving, and puts this Scene back exactly as it was when this dialog opened -- including anything moved or resized in the Preview. |
| [Cancel](#cmd-edit-scene-pick-cancel) | Command | Edit Scene &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-scene-rename-cancel) | Command | Edit Scene &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-scene-save-to-android-cancel) | Command | Edit Scene &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-cancel) | Command | Edit Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-delete-task-cancel) | Command | Edit Task &gt; Delete Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-pick-cancel) | Command | Edit Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-pick-icon-not-listed-cancel) | Command | Edit Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-rename-cancel) | Command | Edit Task &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-save-to-android-cancel) | Command | Edit Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-get-local-xml-file-cancel) | Command | Get Local XML File | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-pick-cancel) | Command | Render Scene &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-pick-icon-not-listed-cancel) | Command | Render Scene &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-rename-cancel) | Command | Item Layout Designer &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-rename-cancel-2) | Command | Scene Properties &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel Entry](#cmd-get-xml-from-android-device-cancel-entry) | Command | Get XML from Android Device | Back out of the Android fetch process. |
| [Cancel Entry](#cmd-get-xml-from-android-device-list-xml-files-cancel-entry) | Command | Get XML from Android Device &gt; List XML Files | Back out of the Android fetch process. |
| [Change Prompt](#cmd-change-prompt) | Command | Main Window | Modify the prompt sent to the AI model. |
| [Clear](#cmd-clear) | Command | Main Window | Clear the Map/Diagram/Tree view data currently held and displayed. |
| [Clear](#cmd-clear-2) | Command | AI API Key Entry | Clear the Map/Diagram/Tree view data currently held and displayed. |
| [Clear](#cmd-clear-3) | Command | Map / Diagram / Tree View Toolbar | Clear the Map/Diagram/Tree view data currently held and displayed. |
| [Close](#cmd-add-profile-add-task-save-to-android-import-into-tasker-close) | Command | Add Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-add-profile-add-task-save-to-android-save-as-file-close) | Command | Add Profile &gt; Add Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-add-profile-save-to-android-import-into-tasker-close) | Command | Add Profile &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-add-profile-save-to-android-save-as-file-close) | Command | Add Profile &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-add-scene-legacy-scene-close) | Command | Add Scene &gt; Legacy Scene | Closes this window without changing anything. |
| [Close](#cmd-add-scene-legacy-scene-picker-close) | Command | Add Scene &gt; Legacy Scene &gt; Picker | Closes this window without changing anything. |
| [Close](#cmd-add-scene-legacy-scene-show-when-close) | Command | Add Scene &gt; Legacy Scene &gt; Show When | Closes this window without changing anything. |
| [Close](#cmd-add-scene-legacy-scene-variable-close) | Command | Add Scene &gt; Legacy Scene &gt; Variable | Closes this window without changing anything. |
| [Close](#cmd-add-task-save-to-android-import-into-tasker-close) | Command | Add Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-add-task-save-to-android-save-as-file-close) | Command | Add Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-close) | Command | Item Layout Designer | Stop firing anything on this event. |
| [Close](#cmd-close-2) | Command | Render Scene | Stop firing anything on this event. |
| [Close](#cmd-edit-history-close) | Command | Edit History | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-add-task-save-to-android-import-into-tasker-close) | Command | Edit Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-add-task-save-to-android-save-as-file-close) | Command | Edit Profile &gt; Add Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-save-to-android-import-into-tasker-close) | Command | Edit Profile &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-save-to-android-save-as-file-close) | Command | Edit Profile &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-project-save-to-android-import-into-tasker-close) | Command | Edit Project &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-project-save-to-android-save-as-file-close) | Command | Edit Project &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-close) | Command | Edit Scene | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-picker-close) | Command | Edit Scene &gt; Picker | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-save-to-android-import-into-tasker-close) | Command | Edit Scene &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-save-to-android-save-as-file-close) | Command | Edit Scene &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-show-when-close) | Command | Edit Scene &gt; Show When | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-variable-close) | Command | Edit Scene &gt; Variable | Closes this window without changing anything. |
| [Close](#cmd-edit-task-save-to-android-import-into-tasker-close) | Command | Edit Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-task-save-to-android-save-as-file-close) | Command | Edit Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-find-replace-close) | Command | Map / Diagram / Tree View Toolbar &gt; Find/Replace | Closes this window without changing anything. |
| [Close](#cmd-get-xml-from-android-device-list-helper-tasks-close) | Command | Get XML from Android Device &gt; List Helper Tasks | Closes this window without changing anything. |
| [Close Tabs On Exit](#cmd-close-tabs-on-exit) | Option | Main Window | When enabled, clicking 'Exit' also closes the main MapTasker window and any Map/Diagram windows/tabs it opened. |
| [Collapse](#cmd-collapse) | Command | Map / Diagram / Tree View Toolbar | Collapse every Project down to its title bar. |
| [Colors](#cmd-colors) | Tab | Main Window | select colors for various elements of the display. |
| [Compare Files](#cmd-compare-files) | Command | Main Window | Compare another XML file against the loaded one: what was added, removed, renamed and changed. |
| [Create Task](#cmd-create-task) | Command | Render Scene | Adds this Task to the loaded configuration and points this event at it, the same as 'Ok' in the Add Task dialog -- nothing is written to a file and nothing is sent to Android. |
| [Dark Mode](#cmd-dark-mode) | Option | Main Window | Switch the GUI between light and dark appearance. |
| [Debug](#cmd-debug) | Tab | Main Window | Display Runtime Settings option and turn on Debug mode. |
| [Delete](#cmd-add-scene-legacy-scene-delete) | Command | Add Scene &gt; Legacy Scene | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-delete) | Command | Item Layout Designer | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-delete-2) | Command | Render Scene | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-delete-3) | Command | Scene Properties | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-edit-scene-delete) | Command | Edit Scene | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-edit-task-delete) | Command | Edit Task | Remove the object being edited from the loaded XML. |
| [Delete Profile](#cmd-edit-profile-delete-profile) | Command | Edit Profile | Deletes only this Profile. |
| [Delete Task](#cmd-edit-task-delete-task) | Command | Edit Task | Deletes this Task and every reference to it: it is removed from the Tasks of every Project that owns it, and from any Profile that runs it as its Entry/Exit Task. |
| [Detail Level](#cmd-detail-level) | Pulldown | Main Window | 0 = least detail, 5 = most detail. |
| [Diagram](#cmd-diagram) | Command | Main Window | Displays the Diagram view. |
| [Display Conditions](#cmd-display-conditions) | Option | Main Window | Enables the display of Profile Conditions (e.g. |
| [Display Directory](#cmd-display-directory) | Option | Main Window | Enables the display of the Project/Profile/Task/Scene Directory in the output. |
| [Display Help](#cmd-display-help) | Command | Main Window | Display this help text. |
| [Display Prettier Output](#cmd-display-prettier-output) | Option | Main Window | Enables the display of aligned text in the output. |
| [Display Tasker Preferences](#cmd-display-tasker-preferences) | Option | Main Window | Enables the display a breakdown of the Tasker system Preferences in the output. |
| [Display TaskerNet Info](#cmd-display-taskernet-info) | Option | Main Window | Enables the display of TaskerNet Descriptions in the output. |
| [Done](#cmd-done) | Command | Item Layout Designer | Closes this dialog, keeping what was edited in it. |
| [Duplicate](#cmd-add-scene-legacy-scene-duplicate) | Command | Add Scene &gt; Legacy Scene | Make a copy of the selected Scene element. |
| [Duplicate](#cmd-duplicate) | Command | Item Layout Designer | Make a copy of the selected Scene element. |
| [Duplicate](#cmd-edit-scene-duplicate) | Command | Edit Scene | Make a copy of the selected Scene element. |
| [Edit History](#cmd-edit-history) | Command | Main Window | List every change made to the loaded XML this session, newest first. |
| [Edit Profile](#cmd-edit-profile) | Command | Main Window | Modify the object currently selected in the pulldowns above. |
| [Edit Project](#cmd-edit-project) | Command | Main Window | Modify the object currently selected in the pulldowns above. |
| [Edit Scene](#cmd-edit-scene) | Command | Main Window | Modify the object currently selected in the pulldowns above. |
| [Edit Task](#cmd-edit-task) | Command | Main Window | Modify the object currently selected in the pulldowns above. |
| [Enabled](#cmd-edit-project-enabled) | Option | Edit Project | Disables the Project in the loaded backup, right now -- like Rename, this takes effect immediately rather than waiting for a save, and Cancel does not undo it. |
| [Exit](#cmd-exit) | Command | Main Window | Exit the program (quit). |
| [Expand](#cmd-expand) | Command | Map / Diagram / Tree View Toolbar | Expand every collapsed Project. |
| [Export Profile](#cmd-add-profile-export-profile) | Command | Add Profile | Saves this Profile, with all of its conditions and linked Tasks, as one standalone .prf.xml file -- the same format Tasker's own Profile export produces. |
| [Export Profile](#cmd-edit-profile-export-profile) | Command | Edit Profile | Saves this Profile as a standalone .prf.xml file on this computer. |
| [Export Project](#cmd-edit-project-export-project) | Command | Edit Project | Saves this Project, and everything in it -- every Profile and Task -- as one standalone file. |
| [Export Scene](#cmd-edit-scene-export-scene) | Command | Edit Scene | Saves this Scene, with all of its elements, as one standalone .scn.xml file -- the same format Tasker's own Scene export produces. |
| [Export Task](#cmd-add-profile-add-task-export-task) | Command | Add Profile &gt; Add Task | Exports the Task as XML to a file on your computer. |
| [Export Task](#cmd-add-task-export-task) | Command | Add Task | Exports the Task as XML to a file on your computer. |
| [Export Task](#cmd-edit-profile-add-task-export-task) | Command | Edit Profile &gt; Add Task | Exports the Task as XML to a file on your computer. |
| [Export Task](#cmd-edit-task-export-task) | Command | Edit Task | This will save the Task directly to your current drive. |
| [Extended](#cmd-extended) | Option | Main Window | Display an extended list of ALL available models. |
| [Find](#cmd-find-replace-find) | Tab | Map / Diagram / Tree View Toolbar &gt; Find/Replace | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Find](#cmd-find-replace-find-2) | Command | Map / Diagram / Tree View Toolbar &gt; Find/Replace | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Find/Replace](#cmd-find-replace) | Command | Map / Diagram / Tree View Toolbar | 'Find/Replace' asks the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything that names a given app or Scene. |
| [Font Optionmenu](#cmd-font-optionmenu) | Pulldown | Main Window | This is a list of all of the fonts available on your system, monospaced ones first and marked as such. |
| [Get Android Help](#cmd-get-android-help) | Command | Main Window | Display the help for fetching the XML file from your Android device. |
| [Get Local XML File](#cmd-get-local-xml-file) | Command | Main Window | Fetch XML from a local drive on this computer. |
| [Get XML from Android Device](#cmd-get-xml-from-android-device) | Command | Main Window | Fetch XML from an Android device. |
| [Health Check](#cmd-health-check) | Command | Main Window | Scan the loaded XML for broken references, unreferenced Tasks, Profiles and Scenes, and naming problems. |
| [Help](#cmd-help) | Command | Map / Diagram / Tree View Toolbar | The diagram is clickable: |
| [Hide Task Details Under Twisty](#cmd-hide-task-details-under-twisty) | Option | Main Window | When enabled, Task details are hidden under a twisty (expand/collapse) control in the output. |
| [Icon not listed?](#cmd-add-profile-add-task-pick-icon-not-listed) | Command | Add Profile &gt; Add Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-add-profile-pick-icon-not-listed) | Command | Add Profile &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-add-task-pick-icon-not-listed) | Command | Add Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-edit-profile-add-task-pick-icon-not-listed) | Command | Edit Profile &gt; Add Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-edit-profile-pick-icon-not-listed) | Command | Edit Profile &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-edit-task-pick-icon-not-listed) | Command | Edit Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-pick-icon-not-listed) | Command | Render Scene &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Import Into Tasker](#cmd-add-profile-add-task-save-to-android-import-into-tasker) | Command | Add Profile &gt; Add Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Import Into Tasker](#cmd-add-profile-save-to-android-import-into-tasker) | Command | Add Profile &gt; Save To Android | This copies the Profile to the device and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-add-task-save-to-android-import-into-tasker) | Command | Add Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Import Into Tasker](#cmd-edit-profile-add-task-save-to-android-import-into-tasker) | Command | Edit Profile &gt; Add Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Import Into Tasker](#cmd-edit-profile-save-to-android-import-into-tasker) | Command | Edit Profile &gt; Save To Android | This copies the Profile to the device and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-edit-project-save-to-android-import-into-tasker) | Command | Edit Project &gt; Save To Android | This copies the Project -- and every Profile and Task in it -- to the device and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-edit-scene-save-to-android-import-into-tasker) | Command | Edit Scene &gt; Save To Android | This sends the Scene -- and every Task its elements fire -- to the Android device under its own name, into /Tasker/scenes, and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-edit-task-save-to-android-import-into-tasker) | Command | Edit Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Indent Option](#cmd-indent-option) | Pulldown | Main Window | Set the indentation amount for If/Then/Else blocks. |
| [Just Display Everything!](#cmd-just-display-everything) | Option | Main Window | Enables the display of Conditions, TaskerNet Info, Preferences, the Directory, and Prettier Output. |
| [Landscape](#cmd-add-scene-legacy-scene-landscape) | Option | Add Scene &gt; Legacy Scene | This Scene has no landscape layout of its own (its size is -1). |
| [Landscape](#cmd-edit-scene-landscape) | Option | Edit Scene | This Scene has no landscape layout of its own (its size is -1). |
| [Landscape](#cmd-landscape) | Option | Item Layout Designer | This Scene has no landscape layout of its own (its size is -1). |
| [Landscape](#cmd-landscape-2) | Option | Scene Preview Window | Turn the screen on its side and let the layout re-flow into it. |
| [Legacy Scene](#cmd-add-scene-legacy-scene) | Command | Add Scene | A Legacy Scene has a pixel canvas and a list of UI elements. |
| [List Helper Tasks](#cmd-get-xml-from-android-device-list-helper-tasks) | Command | Get XML from Android Device | Lists the 'MapTasker ...' Tasks this program has installed on the Android device, and says which are left over from an earlier version. |
| [List Unnamed Items](#cmd-list-unnamed-items) | Option | Main Window | Select this to include Profiles and Tasks that do not have a name in the list. |
| [List XML Files](#cmd-get-xml-from-android-device-list-xml-files) | Command | Get XML from Android Device | List the XML files found on the Android device so you can select one rather than typing its location. |
| [Map](#cmd-map) | Command | Main Window | Displays the Map view. |
| [Narrow to Project](#cmd-find-replace-narrow-to-project) | Pulldown | Map / Diagram / Tree View Toolbar &gt; Find/Replace | Hidden under a scope, for the reason the Find tab's own gives. |
| [Notify Timeout Optionmenu](#cmd-notify-timeout-optionmenu) | Pulldown | Main Window | How long a pop-up message stays on screen before it disappears. |
| [Ok](#cmd-add-profile-add-task-ok) | Command | Add Profile &gt; Add Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-profile-ok) | Command | Add Profile | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-project-ok) | Command | Add Project | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-scene-legacy-scene-ok) | Command | Add Scene &gt; Legacy Scene | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-task-ok) | Command | Add Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-profile-add-task-ok) | Command | Edit Profile &gt; Add Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-profile-ok) | Command | Edit Profile | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-scene-ok) | Command | Edit Scene | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-task-ok) | Command | Edit Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-get-local-xml-file-ok) | Command | Get Local XML File | Keeps what this dialog holds and closes it. |
| [OK](#cmd-ok) | Command | AI API Key Entry | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-ok-2) | Command | Action Condition | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-ok-3) | Command | Object Properties | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-ok-4) | Command | Scene Properties | Keeps everything, including the actions of any Task edited under the Event tab. |
| [Only the matching text](#cmd-find-replace-only-the-matching-text) | Option | Map / Diagram / Tree View Toolbar &gt; Find/Replace | Off means the argument is SET to the new value; on means only the matched text inside it changes. |
| [Open View In New Window](#cmd-open-view-in-new-window) | Option | Main Window | When enabled, each Map/Diagram request opens in its own new window/tab, so you can keep earlier ones up alongside it to compare. |
| [Palette](#cmd-add-scene-legacy-scene-palette) | Command | Add Scene &gt; Legacy Scene | Pick one of Material's own colour roles. |
| [Palette](#cmd-edit-scene-palette) | Command | Edit Scene | Pick one of Material's own colour roles. |
| [Pick](#cmd-add-profile-add-task-pick) | Command | Add Profile &gt; Add Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-add-profile-pick) | Command | Add Profile | Fill all three fields in from the loaded configuration. |
| [Pick](#cmd-add-scene-legacy-scene-pick) | Command | Add Scene &gt; Legacy Scene | Pick a Material icon. |
| [Pick](#cmd-add-task-pick) | Command | Add Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-edit-profile-add-task-pick) | Command | Edit Profile &gt; Add Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-edit-profile-pick) | Command | Edit Profile | Fill all three fields in from the loaded configuration. |
| [Pick](#cmd-edit-scene-pick) | Command | Edit Scene | Pick a Material icon. |
| [Pick](#cmd-edit-task-pick) | Command | Edit Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-pick) | Command | Render Scene | Choose from the Applications named in the loaded configuration. |
| [Pick a Task](#cmd-add-profile-add-task-pick-a-task) | Pulldown | Add Profile &gt; Add Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-add-task-pick-a-task) | Pulldown | Add Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-edit-profile-add-task-pick-a-task) | Pulldown | Edit Profile &gt; Add Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-edit-task-pick-a-task) | Pulldown | Edit Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-pick-a-task) | Pulldown | Render Scene | Pick a Task which will be called by this action. |
| [Picker](#cmd-add-scene-legacy-scene-picker) | Command | Add Scene &gt; Legacy Scene | Pick from the Scene's environment and global variables. |
| [Picker](#cmd-edit-scene-picker) | Command | Edit Scene | Pick from the Scene's environment and global variables. |
| [Preview](#cmd-add-scene-legacy-scene-preview) | Command | Add Scene &gt; Legacy Scene | Draws this Scene as a picture in the main window -- including the components you have added or changed here but not yet saved. |
| [Preview](#cmd-edit-scene-preview) | Command | Edit Scene | Draws this Scene as a picture in the main window -- including the components you have added or changed here but not yet saved. |
| [Preview](#cmd-find-replace-preview) | Command | Map / Diagram / Tree View Toolbar &gt; Find/Replace | Display the Scene being edited as it will appear. |
| [Profile](#cmd-profile) | Pulldown | Main Window | Select a specific Profile to target for display or editing. |
| [Profiles Per Line](#cmd-profiles-per-line) | Pulldown | Map / Diagram / Tree View Toolbar | (Diagram only) The number of Profiles drawn side-by-side on a single line. |
| [Project](#cmd-project) | Pulldown | Main Window | Select a specific Project to target for display or editing. |
| [Redo](#cmd-redo) | Command | Main Window | Reapply the change most recently backed out by 'Undo'. |
| [Rename](#cmd-add-scene-legacy-scene-rename) | Command | Add Scene &gt; Legacy Scene | Tasks address this element by name (Element Text, Element Position, ... |
| [Rename](#cmd-add-scene-legacy-scene-rename-rename) | Command | Add Scene &gt; Legacy Scene &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-edit-profile-rename) | Command | Edit Profile | Prompts for a new name and applies just that to the loaded backup, right now. |
| [Rename](#cmd-edit-profile-rename-rename) | Command | Edit Profile &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-edit-project-rename) | Command | Edit Project | Prompts for a new name and applies it to the loaded backup, right now. |
| [Rename](#cmd-edit-project-rename-rename) | Command | Edit Project &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-edit-scene-rename) | Command | Edit Scene | Tasks address this element by name (Element Text, Element Position, ... |
| [Rename](#cmd-edit-scene-rename-rename) | Command | Edit Scene &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-edit-task-rename) | Command | Edit Task | Prompts for a new name and applies just that to the loaded backup, right now. |
| [Rename](#cmd-edit-task-rename-rename) | Command | Edit Task &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-rename) | Command | Item Layout Designer | Tasks address this element by name (Element Text, Element Position, ... |
| [Rename](#cmd-rename-2) | Command | Scene Properties | Tasks address this element by name (Element Text, Element Position, ... |
| [Rename](#cmd-rename-rename) | Command | Item Layout Designer &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-rename-rename-2) | Command | Scene Properties &gt; Rename | Give the object being edited a new name. |
| [Replace](#cmd-find-replace-replace) | Command | Map / Diagram / Tree View Toolbar &gt; Find/Replace | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Replace](#cmd-find-replace-replace-2) | Tab | Map / Diagram / Tree View Toolbar &gt; Find/Replace | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Report Issue](#cmd-report-issue) | Command | Main Window | Report any issues and/or suggestions to the developer. |
| [Reset](#cmd-reset) | Command | Map / Diagram / Tree View Toolbar | Back to the whole diagram: no zoom, nothing folded, nothing filtered. |
| [Reset Options](#cmd-reset-options) | Command | Main Window | Reset all of the options to their default values, including colors, font used, and other settings. |
| [Reset to Default Colors](#cmd-reset-to-default-colors) | Command | Main Window | Restore every color to its default value. |
| [Run Analysis](#cmd-run-analysis) | Command | Main Window | Submit the selected Project/Profile/Task and prompt to the selected model. |
| [Same as Value](#cmd-same-as-value) | Option | Object Properties | Under 'Exported Value' if you disable the 'Same as Value' option, you can customize what value gets exported when you share the variable with other users. |
| [Save As File](#cmd-add-profile-add-task-save-to-android-save-as-file) | Command | Add Profile &gt; Add Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save As File](#cmd-add-profile-save-to-android-save-as-file) | Command | Add Profile &gt; Save To Android | This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles. |
| [Save As File](#cmd-add-task-save-to-android-save-as-file) | Command | Add Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save As File](#cmd-edit-profile-add-task-save-to-android-save-as-file) | Command | Edit Profile &gt; Add Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save As File](#cmd-edit-profile-save-to-android-save-as-file) | Command | Edit Profile &gt; Save To Android | This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles. |
| [Save As File](#cmd-edit-project-save-to-android-save-as-file) | Command | Edit Project &gt; Save To Android | This will write the Project, and everything in it, as a standalone file onto the Android device, under /Tasker/projects. |
| [Save As File](#cmd-edit-scene-save-to-android-save-as-file) | Command | Edit Scene &gt; Save To Android | This will write the Scene as a standalone file onto the Android device, under /Tasker/scenes. |
| [Save As File](#cmd-edit-task-save-to-android-save-as-file) | Command | Edit Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save Results](#cmd-find-replace-save-results) | Command | Map / Diagram / Tree View Toolbar &gt; Find/Replace | Save the 'Find/Replace' results to a text file. |
| [Save To Android](#cmd-add-profile-add-task-save-to-android) | Command | Add Profile &gt; Add Task | Write the object back to your Android device. |
| [Save To Android](#cmd-add-profile-save-to-android) | Command | Add Profile | This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-add-task-save-to-android) | Command | Add Task | Write the object back to your Android device. |
| [Save To Android](#cmd-edit-profile-add-task-save-to-android) | Command | Edit Profile &gt; Add Task | Write the object back to your Android device. |
| [Save To Android](#cmd-edit-profile-save-to-android) | Command | Edit Profile | This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-edit-project-save-to-android) | Command | Edit Project | This will write the Project, and everything in it -- every Profile and Task -- as a standalone file onto your Android device, under /Tasker/projects -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-edit-scene-save-to-android) | Command | Edit Scene | This will write the Scene as a standalone file onto your Android device, under /Tasker/scenes -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-edit-task-save-to-android) | Command | Edit Task | This opens a choice of two: write the Task as a standalone file onto your Android device under /Tasker/tasks, or import it straight into Tasker's live configuration. |
| [Save To Current File](#cmd-add-profile-add-task-save-to-current-file) | Command | Add Profile &gt; Add Task | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-add-profile-save-to-current-file) | Command | Add Profile | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Profile added to its Project, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-add-task-save-to-current-file) | Command | Add Task | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-edit-profile-add-task-save-to-current-file) | Command | Edit Profile &gt; Add Task | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-edit-profile-save-to-current-file) | Command | Edit Profile | Saves the entire backup -- every Project, Profile and Task in it, not just this Profile -- with this dialog's edits applied, the same ones 'Ok' would keep. |
| [Save To Current File](#cmd-edit-project-save-to-current-file) | Command | Edit Project | Saves the entire backup -- every Project, Profile and Task in it, not just this Project -- including every edit made anywhere in this session. |
| [Save To Current File](#cmd-edit-scene-save-to-current-file) | Command | Edit Scene | Saves the entire backup -- every Project, Profile, Task and Scene in it, not just this Scene -- including every edit made anywhere in this session. |
| [Save To Current File](#cmd-edit-task-save-to-current-file) | Command | Edit Task | Saves the entire backup -- every Project, Profile and Task in it, not just this Task -- with this dialog's edits applied, the same ones 'Ok' would keep. |
| [Scene](#cmd-scene) | Pulldown | Main Window | Select a specific Scene to target for display or editing. |
| [Screen](#cmd-screen) | Pulldown | Scene Preview Window | A Version 2 Scene has no size of its own -- it lays itself out inside whatever screen it is shown on, so there is nothing in the backup file to draw it at. |
| [Search](#cmd-search) | Command | Map / Diagram / Tree View Toolbar | The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data. |
| [Show When](#cmd-add-scene-legacy-scene-show-when) | Command | Add Scene &gt; Legacy Scene | Pick from the Scene's environment and global variables. |
| [Show When](#cmd-edit-scene-show-when) | Command | Edit Scene | Pick from the Scene's environment and global variables. |
| [Snap](#cmd-add-scene-legacy-scene-snap) | Pulldown | Add Scene &gt; Legacy Scene | Round dragged positions and sizes to this many pixels. |
| [Snap](#cmd-edit-scene-snap) | Pulldown | Edit Scene | Round dragged positions and sizes to this many pixels. |
| [Snap](#cmd-snap) | Pulldown | Item Layout Designer | Round dragged positions and sizes to this many pixels. |
| [Snap](#cmd-snap-2) | Pulldown | Scene Preview Window | Round dragged positions and sizes to this many pixels. |
| [Specific Name](#cmd-specific-name) | Tab | Main Window | enter a single, specific named item to display... |
| [State](#cmd-add-scene-legacy-scene-state) | Pulldown | Add Scene &gt; Legacy Scene | Dynamic and Select Variable are worked out when the Scene is shown. |
| [State](#cmd-edit-scene-state) | Pulldown | Edit Scene | Dynamic and Select Variable are worked out when the Scene is shown. |
| [Stop Event](#cmd-stop-event) | Option | Render Scene | Any key handled by the scene is not passed on to the system -- how a Scene keeps the back key from closing it. |
| [Task](#cmd-task) | Pulldown | Main Window | Select a specific Task to target for display or editing. |
| [Text density](#cmd-text-density) | Pulldown | Scene Preview Window | A Scene's element positions are stored in device pixels, but its text sizes are stored in Android's sp units. |
| [Toggle Wrap](#cmd-toggle-wrap) | Command | Map / Diagram / Tree View Toolbar | Turn line wrapping on or off in the displayed output. |
| [Tree](#cmd-tree) | Command | Main Window | Displays the Tree view. |
| [Undo](#cmd-add-scene-legacy-scene-undo) | Command | Add Scene &gt; Legacy Scene | Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. |
| [Undo](#cmd-edit-scene-undo) | Command | Edit Scene | Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. |
| [Undo](#cmd-undo) | Command | Main Window | Take back the last change made to the loaded XML -- an edit, an Add, a Delete or a Rename, in any of the Edit panels. |
| [Undo](#cmd-undo-2) | Command | Item Layout Designer | Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. |
| [Upgrade to Latest Version](#cmd-upgrade-to-latest-version) | Command | New Version Notice | Clicking this will launch 'pip install --upgrade maptasker' in the background, and then relaunch MapTasker. |
| [Use](#cmd-add-profile-add-task-pick-use) | Command | Add Profile &gt; Add Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-add-profile-pick-use) | Command | Add Profile &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-add-task-pick-use) | Command | Add Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-edit-profile-add-task-pick-use) | Command | Edit Profile &gt; Add Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-edit-profile-pick-use) | Command | Edit Profile &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-edit-task-pick-use) | Command | Edit Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-pick-use) | Command | Render Scene &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use Selected](#cmd-add-profile-add-task-pick-use-selected) | Command | Add Profile &gt; Add Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-add-task-pick-use-selected) | Command | Add Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-edit-profile-add-task-pick-use-selected) | Command | Edit Profile &gt; Add Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-edit-task-pick-use-selected) | Command | Edit Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-pick-use-selected) | Command | Render Scene &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Variable](#cmd-add-scene-legacy-scene-variable) | Command | Add Scene &gt; Legacy Scene | Pick from the Scene's environment and global variables. |
| [Variable](#cmd-edit-scene-variable) | Command | Edit Scene | Pick from the Scene's environment and global variables. |
| [Variable Xref](#cmd-variable-xref) | Command | Main Window | Trace every %variable in the loaded XML: where each one is set, where it is read, which are read but never set, which are set but never read, and which near-identical names (%MyVar against %Myvar) are likely typos. |
| [Verify](#cmd-add-profile-add-task-save-to-android-verify) | Option | Add Profile &gt; Add Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-add-profile-save-to-android-verify) | Option | Add Profile &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-add-task-save-to-android-verify) | Option | Add Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-profile-add-task-save-to-android-verify) | Option | Edit Profile &gt; Add Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-profile-save-to-android-verify) | Option | Edit Profile &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-project-save-to-android-verify) | Option | Edit Project &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-scene-save-to-android-verify) | Option | Edit Scene &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-task-save-to-android-verify) | Option | Edit Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Viewlimit Optionmenu](#cmd-viewlimit-optionmenu) | Pulldown | Main Window | Select the maximum number of items to display in the view to be allowed. |
| [What's New?](#cmd-what-s-new) | Command | New Version Notice | Display the changes in the new version. |
| [Zoom In](#cmd-zoom-in) | Command | Map / Diagram / Tree View Toolbar | Zoom in. |
| [Zoom Out](#cmd-zoom-out) | Command | Map / Diagram / Tree View Toolbar | Zoom out. |

## Main Window

_Initializes the main GUI screen layout using NiceGUI with split sidebars._

<a id="cmd-ai-model"></a>
### AI Model

**Path:** Main Window &gt; AI Model  
**Kind:** Pulldown

Select the model belonging to the AI you wish to use.

<sub>Source: `guiutils.py` line 166</sub>

<a id="cmd-undo"></a>
### Undo

**Path:** Main Window &gt; Undo  
**Kind:** Command

Take back the last change made to the loaded XML -- an edit, an Add, a Delete or a Rename, in any of the Edit panels.

This changes what is loaded, not any file: nothing on disk or on the Android device is touched.

<sub>Source: `guiwins.py` line 423</sub>

<a id="cmd-redo"></a>
### Redo

**Path:** Main Window &gt; Redo  
**Kind:** Command

Reapply the change most recently backed out by 'Undo'.

<sub>Source: `guiwins.py` line 428</sub>

<a id="cmd-edit-history"></a>
### Edit History

**Path:** Main Window &gt; Edit History  
**Kind:** Command

List every change made to the loaded XML this session, newest first.

Opens **Edit History**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 446</sub>

<a id="cmd-edit-history-close"></a>
#### Close

**Path:** Main Window &gt; Edit History &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 406</sub>

<a id="cmd-dark-mode"></a>
### Dark Mode

**Path:** Main Window &gt; Dark Mode  
**Kind:** Option

Switch the GUI between light and dark appearance.

<sub>Source: `guiwins.py` line 13513</sub>

<a id="cmd-detail-level"></a>
### Detail Level

**Path:** Main Window &gt; Detail Level  
**Kind:** Pulldown

0 = least detail, 5 = most detail.

<sub>Source: `guiwins.py` line 13537</sub>

<a id="cmd-just-display-everything"></a>
### Just Display Everything!

**Path:** Main Window &gt; Just Display Everything!  
**Kind:** Option

Enables the display of Conditions, TaskerNet Info, Preferences, the Directory, and Prettier Output.

<sub>Source: `guiwins.py` line 13549</sub>

<a id="cmd-display-conditions"></a>
### Display Conditions

**Path:** Main Window &gt; Display Conditions  
**Kind:** Option

Enables the display of Profile Conditions (e.g. State, Event, etc.) details in the output.

<sub>Source: `guiwins.py` line 13558</sub>

<a id="cmd-display-taskernet-info"></a>
### Display TaskerNet Info

**Path:** Main Window &gt; Display TaskerNet Info  
**Kind:** Option

Enables the display of TaskerNet Descriptions in the output.

<sub>Source: `guiwins.py` line 13567</sub>

<a id="cmd-display-tasker-preferences"></a>
### Display Tasker Preferences

**Path:** Main Window &gt; Display Tasker Preferences  
**Kind:** Option

Enables the display a breakdown of the Tasker system Preferences in the output.

<sub>Source: `guiwins.py` line 13572</sub>

<a id="cmd-hide-task-details-under-twisty"></a>
### Hide Task Details Under Twisty

**Path:** Main Window &gt; Hide Task Details Under Twisty  
**Kind:** Option

When enabled, Task details are hidden under a twisty (expand/collapse) control in the output.

<sub>Source: `guiwins.py` line 13577</sub>

<a id="cmd-display-directory"></a>
### Display Directory

**Path:** Main Window &gt; Display Directory  
**Kind:** Option

Enables the display of the Project/Profile/Task/Scene Directory in the output.

<sub>Source: `guiwins.py` line 13586</sub>

<a id="cmd-display-prettier-output"></a>
### Display Prettier Output

**Path:** Main Window &gt; Display Prettier Output  
**Kind:** Option

Enables the display of aligned text in the output.

<sub>Source: `guiwins.py` line 13591</sub>

<a id="cmd-get-local-xml-file"></a>
### Get Local XML File

**Path:** Main Window &gt; Get Local XML File  
**Kind:** Command

Fetch XML from a local drive on this computer.

The XML fetched will become the current source for MapTasker commands.

Opens **Local File Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13620</sub>

<a id="cmd-get-local-xml-file-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Get Local XML File &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `getfile.py` line 50</sub>

<a id="cmd-get-local-xml-file-ok"></a>
#### Ok

**Path:** Main Window &gt; Get Local XML File &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `getfile.py` line 51</sub>

<a id="cmd-exit"></a>
### Exit

**Path:** Main Window &gt; Exit  
**Kind:** Command

Exit the program (quit).

<sub>Source: `guiwins.py` line 13633</sub>

<a id="cmd-close-tabs-on-exit"></a>
### Close Tabs On Exit

**Path:** Main Window &gt; Close Tabs On Exit  
**Kind:** Option

When enabled, clicking 'Exit' also closes the main MapTasker window and any Map/Diagram windows/tabs it opened.

When disabled, 'Exit' shuts down MapTasker but leaves those windows/tabs open.

<sub>Source: `guiwins.py` line 13642</sub>

<a id="cmd-open-view-in-new-window"></a>
### Open View In New Window

**Path:** Main Window &gt; Open View In New Window  
**Kind:** Option

When enabled, each Map/Diagram request opens in its own new window/tab, so you can keep earlier ones up alongside it to compare.

When disabled, a request reuses that view's existing window/tab, replacing what's in it.

Leave it off unless you want to compare: a brand new window/tab is the one your browser may block, since it gets opened once the view has finished building rather than the instant you click.

<sub>Source: `guiwins.py` line 13657</sub>

<a id="cmd-map"></a>
### Map

**Path:** Main Window &gt; Map  
**Kind:** Command

Displays the Map view.

Use this to display the Tasker configuration of your Projects, Profiles, Tasks, and Scenes.

<sub>Source: `guiwins.py` line 13683</sub>

<a id="cmd-diagram"></a>
### Diagram

**Path:** Main Window &gt; Diagram  
**Kind:** Command

Displays the Diagram view.

Use this to visualize the relationships between your Projects, Profiles, Tasks, and Scenes.

<sub>Source: `guiwins.py` line 13692</sub>

<a id="cmd-tree"></a>
### Tree

**Path:** Main Window &gt; Tree  
**Kind:** Command

Displays the Tree view.

Use this to navigate the hierarchical structure of your Projects, Profiles, Tasks, and Scenes.

<sub>Source: `guiwins.py` line 13704</sub>

<a id="cmd-health-check"></a>
### Health Check

**Path:** Main Window &gt; Health Check  
**Kind:** Command

Scan the loaded XML for broken references, unreferenced Tasks, Profiles and Scenes, and naming problems.

Results are displayed here and saved to a text file in the current directory.

<sub>Source: `guiwins.py` line 13722</sub>

<a id="cmd-compare-files"></a>
### Compare Files

**Path:** Main Window &gt; Compare Files  
**Kind:** Command

Compare another XML file against the loaded one: what was added, removed, renamed and changed.

Use it to see what a TaskerNet import brought in, what an edit changed, or what is different between two backups.

If the loaded file came from 'Save to Current File', the file it was saved from is offered directly.

Results are displayed here and saved to a text file in the current directory.

Opens **Compare Files**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13744</sub>

<a id="cmd-compare-files-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Compare Files &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `userintr.py` line 255</sub>

<a id="cmd-variable-xref"></a>
### Variable Xref

**Path:** Main Window &gt; Variable Xref  
**Kind:** Command

Trace every %variable in the loaded XML: where each one is set, where it is read, which are read but never set, which are set but never read, and which near-identical names (%MyVar against %Myvar) are likely typos.

Searched: Task actions and their conditions, plugin configuration, Profile contexts and Scenes.

Results are displayed here and saved to a text file in the current directory.

<sub>Source: `guiwins.py` line 13769</sub>

<a id="cmd-clear"></a>
### Clear

**Path:** Main Window &gt; Clear  
**Kind:** Command

Clear the Map/Diagram/Tree view data currently held and displayed.

<sub>Source: `guiwins.py` line 13790</sub>

<a id="cmd-specific-name"></a>
### Specific Name

**Path:** Main Window &gt; Specific Name  
**Kind:** Tab

enter a single, specific named item to display...

<sub>Source: `guiwins.py` line 13822</sub>

<a id="cmd-colors"></a>
### Colors

**Path:** Main Window &gt; Colors  
**Kind:** Tab

select colors for various elements of the display.

<sub>Source: `guiwins.py` line 13827</sub>

<a id="cmd-analyze"></a>
### Analyze

**Path:** Main Window &gt; Analyze  
**Kind:** Tab

Run the analysis for a Project, Profile, Task or Scene against an Ai model.

<sub>Source: `guiwins.py` line 13828</sub>

<a id="cmd-debug"></a>
### Debug

**Path:** Main Window &gt; Debug  
**Kind:** Tab

Display Runtime Settings option and turn on Debug mode.

<sub>Source: `guiwins.py` line 13829</sub>

<a id="cmd-project"></a>
### Project

**Path:** Main Window &gt; Project  
**Kind:** Pulldown

Select a specific Project to target for display or editing.

<sub>Source: `guiwins.py` line 13847</sub>

<a id="cmd-profile"></a>
### Profile

**Path:** Main Window &gt; Profile  
**Kind:** Pulldown

Select a specific Profile to target for display or editing.

<sub>Source: `guiwins.py` line 13861</sub>

<a id="cmd-task"></a>
### Task

**Path:** Main Window &gt; Task  
**Kind:** Pulldown

Select a specific Task to target for display or editing.

<sub>Source: `guiwins.py` line 13875</sub>

<a id="cmd-scene"></a>
### Scene

**Path:** Main Window &gt; Scene  
**Kind:** Pulldown

Select a specific Scene to target for display or editing.

<sub>Source: `guiwins.py` line 13889</sub>

<a id="cmd-list-unnamed-items"></a>
### List Unnamed Items

**Path:** Main Window &gt; List Unnamed Items  
**Kind:** Option

Select this to include Profiles and Tasks that do not have a name in the list.

<sub>Source: `guiwins.py` line 13904</sub>

<a id="cmd-edit-project"></a>
### Edit Project

**Path:** Main Window &gt; Edit Project  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Project**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13941</sub>

<a id="cmd-edit-project-enabled"></a>
#### Enabled

**Path:** Main Window &gt; Edit Project &gt; Enabled  
**Kind:** Option

Disables the Project in the loaded backup, right now -- like Rename, this takes effect immediately rather than waiting for a save, and Cancel does not undo it.

<sub>Source: `guiwins.py` line 2694</sub>

<a id="cmd-edit-project-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Edit Project &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2736</sub>

<a id="cmd-edit-project-rename"></a>
#### Rename

**Path:** Main Window &gt; Edit Project &gt; Rename  
**Kind:** Command

Prompts for a new name and applies it to the loaded backup, right now. The Project Name field above is read-only -- this is the only way to change it.

Opens **Rename**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2741</sub>

<a id="cmd-edit-project-rename-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Project &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8553</sub>

<a id="cmd-edit-project-rename-rename"></a>
##### Rename

**Path:** Main Window &gt; Edit Project &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 8554</sub>

<a id="cmd-edit-project-save-to-current-file"></a>
#### Save To Current File

**Path:** Main Window &gt; Edit Project &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this Project -- including every edit made anywhere in this session. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 2752</sub>

<a id="cmd-edit-project-save-to-android"></a>
#### Save To Android

**Path:** Main Window &gt; Edit Project &gt; Save To Android  
**Kind:** Command

This will write the Project, and everything in it -- every Profile and Task -- as a standalone file onto your Android device, under /Tasker/projects -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running.

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Project To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2773</sub>

<a id="cmd-edit-project-save-to-android-verify"></a>
##### Verify

**Path:** Main Window &gt; Edit Project &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-edit-project-save-to-android-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Project &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2832</sub>

<a id="cmd-edit-project-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main Window &gt; Edit Project &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Project, and everything in it, as a standalone file onto the Android device, under /Tasker/projects.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2833</sub>

<a id="cmd-edit-project-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Edit Project &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-project-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main Window &gt; Edit Project &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This copies the Project -- and every Profile and Task in it -- to the device and opens Android's 'Open with...' chooser for it. Pick Tasker, and its own import screen comes up; you then tap Import to finish, and nothing is imported until you do.

The Project is copied to /Tasker/projects under its own name first and offered from there, so it stays behind under a name you can find -- import it by hand from Tasker if the import screen does not come up. You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2856</sub>

<a id="cmd-edit-project-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Edit Project &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-project-export-project"></a>
#### Export Project

**Path:** Main Window &gt; Edit Project &gt; Export Project  
**Kind:** Command

Saves this Project, and everything in it -- every Profile and Task -- as one standalone file.

<sub>Source: `guiwins.py` line 2795</sub>

<a id="cmd-add-project"></a>
### Add Project

**Path:** Main Window &gt; Add Project  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Project**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13949</sub>

<a id="cmd-add-project-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Add Project &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2632</sub>

<a id="cmd-add-project-ok"></a>
#### Ok

**Path:** Main Window &gt; Add Project &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 2633</sub>

<a id="cmd-edit-profile"></a>
### Edit Profile

**Path:** Main Window &gt; Edit Profile  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Profile**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13958</sub>

<a id="cmd-edit-profile-pick"></a>
#### Pick

**Path:** Main Window &gt; Edit Profile &gt; Pick  
**Kind:** Command

Fill all three fields in from the loaded configuration.

Opens **App Entry Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 970</sub>

<a id="cmd-edit-profile-pick-use"></a>
##### Use

**Path:** Main Window &gt; Edit Profile &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins.py` line 740</sub>

<a id="cmd-edit-profile-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main Window &gt; Edit Profile &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Applications From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 865</sub>

<a id="cmd-edit-profile-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 705</sub>

<a id="cmd-edit-profile-pick-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 943</sub>

<a id="cmd-edit-profile-add-task"></a>
#### Add Task

**Path:** Main Window &gt; Edit Profile &gt; Add Task  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2068</sub>

<a id="cmd-edit-profile-add-task-pick-a-task"></a>
##### Pick a Task

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins.py` line 557</sub>

<a id="cmd-edit-profile-add-task-pick"></a>
##### Pick

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1164</sub>

<a id="cmd-edit-profile-add-task-pick-use"></a>
###### Use

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins.py` line 740</sub>

<a id="cmd-edit-profile-add-task-pick-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 848</sub>

<a id="cmd-edit-profile-add-task-pick-use-selected"></a>
###### Use Selected

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins.py` line 849</sub>

<a id="cmd-edit-profile-add-task-pick-icon-not-listed"></a>
###### Icon not listed?

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Applications From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 865</sub>

<a id="cmd-edit-profile-add-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 705</sub>

<a id="cmd-edit-profile-add-task-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 9026</sub>

<a id="cmd-edit-profile-add-task-ok"></a>
##### Ok

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 9027</sub>

<a id="cmd-edit-profile-add-task-save-to-current-file"></a>
##### Save To Current File

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 9036</sub>

<a id="cmd-edit-profile-add-task-save-to-android"></a>
##### Save To Android

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Android  
**Kind:** Command

Write the object back to your Android device.

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 9058</sub>

<a id="cmd-edit-profile-add-task-save-to-android-verify"></a>
###### Verify

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-edit-profile-add-task-save-to-android-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1879</sub>

<a id="cmd-edit-profile-add-task-save-to-android-save-as-file"></a>
###### Save As File

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1880</sub>

<a id="cmd-edit-profile-add-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-profile-add-task-save-to-android-import-into-tasker"></a>
###### Import Into Tasker

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1904</sub>

<a id="cmd-edit-profile-add-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-profile-add-task-export-task"></a>
##### Export Task

**Path:** Main Window &gt; Edit Profile &gt; Add Task &gt; Export Task  
**Kind:** Command

Exports the Task as XML to a file on your computer.

<sub>Source: `guiwins.py` line 9067</sub>

<a id="cmd-edit-profile-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2454</sub>

<a id="cmd-edit-profile-delete-profile"></a>
#### Delete Profile

**Path:** Main Window &gt; Edit Profile &gt; Delete Profile  
**Kind:** Command

Deletes only this Profile. Its Entry/Exit Tasks are kept -- a Task is owned by the Project, not by the Profile, and the same Task can be used by other Profiles.

Opens **Delete Profile**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2455</sub>

<a id="cmd-edit-profile-delete-profile-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Delete Profile &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8587</sub>

<a id="cmd-edit-profile-rename"></a>
#### Rename

**Path:** Main Window &gt; Edit Profile &gt; Rename  
**Kind:** Command

Prompts for a new name and applies just that to the loaded backup, right now. Everything else in this dialog stays pending until Ok/Save, and the dialog stays open so you can carry on editing.

Opens **Rename**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2466</sub>

<a id="cmd-edit-profile-rename-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8553</sub>

<a id="cmd-edit-profile-rename-rename"></a>
##### Rename

**Path:** Main Window &gt; Edit Profile &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 8554</sub>

<a id="cmd-edit-profile-ok"></a>
#### Ok

**Path:** Main Window &gt; Edit Profile &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 2478</sub>

<a id="cmd-edit-profile-save-to-current-file"></a>
#### Save To Current File

**Path:** Main Window &gt; Edit Profile &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this Profile -- with this dialog's edits applied, the same ones 'Ok' would keep. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 2482</sub>

<a id="cmd-edit-profile-save-to-android"></a>
#### Save To Android

**Path:** Main Window &gt; Edit Profile &gt; Save To Android  
**Kind:** Command

This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running (see the README's Direct XML Retrieval notes).

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Profile To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2503</sub>

<a id="cmd-edit-profile-save-to-android-verify"></a>
##### Verify

**Path:** Main Window &gt; Edit Profile &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-edit-profile-save-to-android-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Profile &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2554</sub>

<a id="cmd-edit-profile-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main Window &gt; Edit Profile &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2555</sub>

<a id="cmd-edit-profile-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Edit Profile &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-profile-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main Window &gt; Edit Profile &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This copies the Profile to the device and opens Android's 'Open with...' chooser for it. Pick Tasker, and its own import screen comes up; you then tap Import to finish -- nothing is imported until you do.

The Profile is copied to /Tasker/profiles under its own name first and offered from there, so it stays behind under a name you can find -- import it by hand from Tasker if the import screen does not come up. You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2580</sub>

<a id="cmd-edit-profile-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Edit Profile &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-profile-export-profile"></a>
#### Export Profile

**Path:** Main Window &gt; Edit Profile &gt; Export Profile  
**Kind:** Command

Saves this Profile as a standalone .prf.xml file on this computer.

<sub>Source: `guiwins.py` line 2524</sub>

<a id="cmd-add-profile"></a>
### Add Profile

**Path:** Main Window &gt; Add Profile  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Profile**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13966</sub>

<a id="cmd-add-profile-pick"></a>
#### Pick

**Path:** Main Window &gt; Add Profile &gt; Pick  
**Kind:** Command

Fill all three fields in from the loaded configuration.

Opens **App Entry Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 970</sub>

<a id="cmd-add-profile-pick-use"></a>
##### Use

**Path:** Main Window &gt; Add Profile &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins.py` line 740</sub>

<a id="cmd-add-profile-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main Window &gt; Add Profile &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Applications From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 865</sub>

<a id="cmd-add-profile-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Profile &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 705</sub>

<a id="cmd-add-profile-pick-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Add Profile &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 943</sub>

<a id="cmd-add-profile-add-task"></a>
#### Add Task

**Path:** Main Window &gt; Add Profile &gt; Add Task  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2068</sub>

<a id="cmd-add-profile-add-task-pick-a-task"></a>
##### Pick a Task

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins.py` line 557</sub>

<a id="cmd-add-profile-add-task-pick"></a>
##### Pick

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1164</sub>

<a id="cmd-add-profile-add-task-pick-use"></a>
###### Use

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins.py` line 740</sub>

<a id="cmd-add-profile-add-task-pick-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 848</sub>

<a id="cmd-add-profile-add-task-pick-use-selected"></a>
###### Use Selected

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins.py` line 849</sub>

<a id="cmd-add-profile-add-task-pick-icon-not-listed"></a>
###### Icon not listed?

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Applications From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 865</sub>

<a id="cmd-add-profile-add-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 705</sub>

<a id="cmd-add-profile-add-task-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 9026</sub>

<a id="cmd-add-profile-add-task-ok"></a>
##### Ok

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 9027</sub>

<a id="cmd-add-profile-add-task-save-to-current-file"></a>
##### Save To Current File

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 9036</sub>

<a id="cmd-add-profile-add-task-save-to-android"></a>
##### Save To Android

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Android  
**Kind:** Command

Write the object back to your Android device.

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 9058</sub>

<a id="cmd-add-profile-add-task-save-to-android-verify"></a>
###### Verify

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-add-profile-add-task-save-to-android-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1879</sub>

<a id="cmd-add-profile-add-task-save-to-android-save-as-file"></a>
###### Save As File

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1880</sub>

<a id="cmd-add-profile-add-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-add-profile-add-task-save-to-android-import-into-tasker"></a>
###### Import Into Tasker

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1904</sub>

<a id="cmd-add-profile-add-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-add-profile-add-task-export-task"></a>
##### Export Task

**Path:** Main Window &gt; Add Profile &gt; Add Task &gt; Export Task  
**Kind:** Command

Exports the Task as XML to a file on your computer.

<sub>Source: `guiwins.py` line 9067</sub>

<a id="cmd-add-profile-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Add Profile &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8736</sub>

<a id="cmd-add-profile-ok"></a>
#### Ok

**Path:** Main Window &gt; Add Profile &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 8737</sub>

<a id="cmd-add-profile-save-to-current-file"></a>
#### Save To Current File

**Path:** Main Window &gt; Add Profile &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Profile added to its Project, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 8741</sub>

<a id="cmd-add-profile-save-to-android"></a>
#### Save To Android

**Path:** Main Window &gt; Add Profile &gt; Save To Android  
**Kind:** Command

This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project (http://spoo.me/http_svr_example) must be installed and active on the Android device, with the server running (see the README's Direct XML Retrieval notes).

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Profile To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 8762</sub>

<a id="cmd-add-profile-save-to-android-verify"></a>
##### Verify

**Path:** Main Window &gt; Add Profile &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-add-profile-save-to-android-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Add Profile &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2554</sub>

<a id="cmd-add-profile-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main Window &gt; Add Profile &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2555</sub>

<a id="cmd-add-profile-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Add Profile &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-add-profile-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main Window &gt; Add Profile &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This copies the Profile to the device and opens Android's 'Open with...' chooser for it. Pick Tasker, and its own import screen comes up; you then tap Import to finish -- nothing is imported until you do.

The Profile is copied to /Tasker/profiles under its own name first and offered from there, so it stays behind under a name you can find -- import it by hand from Tasker if the import screen does not come up. You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2580</sub>

<a id="cmd-add-profile-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Add Profile &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-add-profile-export-profile"></a>
#### Export Profile

**Path:** Main Window &gt; Add Profile &gt; Export Profile  
**Kind:** Command

Saves this Profile, with all of its conditions and linked Tasks, as one standalone .prf.xml file -- the same format Tasker's own Profile export produces.

Tasks the Profile runs are not included; they belong to their own Project.

<sub>Source: `guiwins.py` line 8783</sub>

<a id="cmd-edit-task"></a>
### Edit Task

**Path:** Main Window &gt; Edit Task  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13975</sub>

<a id="cmd-edit-task-pick-a-task"></a>
#### Pick a Task

**Path:** Main Window &gt; Edit Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins.py` line 557</sub>

<a id="cmd-edit-task-pick"></a>
#### Pick

**Path:** Main Window &gt; Edit Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1164</sub>

<a id="cmd-edit-task-pick-use"></a>
##### Use

**Path:** Main Window &gt; Edit Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins.py` line 740</sub>

<a id="cmd-edit-task-pick-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 848</sub>

<a id="cmd-edit-task-pick-use-selected"></a>
##### Use Selected

**Path:** Main Window &gt; Edit Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins.py` line 849</sub>

<a id="cmd-edit-task-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main Window &gt; Edit Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Applications From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 865</sub>

<a id="cmd-edit-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Edit Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 705</sub>

<a id="cmd-edit-task-delete"></a>
#### Delete

**Path:** Main Window &gt; Edit Task &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins.py` line 1531</sub>

<a id="cmd-edit-task-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Edit Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1674</sub>

<a id="cmd-edit-task-delete-task"></a>
#### Delete Task

**Path:** Main Window &gt; Edit Task &gt; Delete Task  
**Kind:** Command

Deletes this Task and every reference to it: it is removed from the Tasks of every Project that owns it, and from any Profile that runs it as its Entry/Exit Task. The Profiles themselves are kept.

Opens **Delete Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1675</sub>

<a id="cmd-edit-task-delete-task-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Task &gt; Delete Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8624</sub>

<a id="cmd-edit-task-rename"></a>
#### Rename

**Path:** Main Window &gt; Edit Task &gt; Rename  
**Kind:** Command

Prompts for a new name and applies just that to the loaded backup, right now. Everything else in this dialog stays pending until Ok/Save, and the dialog stays open so you can carry on editing.

Opens **Rename**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1687</sub>

<a id="cmd-edit-task-rename-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Task &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8553</sub>

<a id="cmd-edit-task-rename-rename"></a>
##### Rename

**Path:** Main Window &gt; Edit Task &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 8554</sub>

<a id="cmd-edit-task-ok"></a>
#### Ok

**Path:** Main Window &gt; Edit Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 1699</sub>

<a id="cmd-edit-task-save-to-current-file"></a>
#### Save To Current File

**Path:** Main Window &gt; Edit Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this Task -- with this dialog's edits applied, the same ones 'Ok' would keep. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 1703</sub>

<a id="cmd-edit-task-save-to-android"></a>
#### Save To Android

**Path:** Main Window &gt; Edit Task &gt; Save To Android  
**Kind:** Command

This opens a choice of two: write the Task as a standalone file onto your Android device under /Tasker/tasks, or import it straight into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running (see the README's Direct XML Retrieval notes), and Tasker must be 6.2 or higher.

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while either one runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

You must exit and restart Tasker to see an imported Task in the Tasker UI.

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1724</sub>

<a id="cmd-edit-task-save-to-android-verify"></a>
##### Verify

**Path:** Main Window &gt; Edit Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-edit-task-save-to-android-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1879</sub>

<a id="cmd-edit-task-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main Window &gt; Edit Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1880</sub>

<a id="cmd-edit-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Edit Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-task-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main Window &gt; Edit Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1904</sub>

<a id="cmd-edit-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Edit Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-task-export-task"></a>
#### Export Task

**Path:** Main Window &gt; Edit Task &gt; Export Task  
**Kind:** Command

This will save the Task directly to your current drive.

<sub>Source: `guiwins.py` line 1748</sub>

<a id="cmd-add-task"></a>
### Add Task

**Path:** Main Window &gt; Add Task  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13983</sub>

<a id="cmd-add-task-pick-a-task"></a>
#### Pick a Task

**Path:** Main Window &gt; Add Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins.py` line 557</sub>

<a id="cmd-add-task-pick"></a>
#### Pick

**Path:** Main Window &gt; Add Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1164</sub>

<a id="cmd-add-task-pick-use"></a>
##### Use

**Path:** Main Window &gt; Add Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins.py` line 740</sub>

<a id="cmd-add-task-pick-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Add Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 848</sub>

<a id="cmd-add-task-pick-use-selected"></a>
##### Use Selected

**Path:** Main Window &gt; Add Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins.py` line 849</sub>

<a id="cmd-add-task-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main Window &gt; Add Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Applications From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 865</sub>

<a id="cmd-add-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 705</sub>

<a id="cmd-add-task-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Add Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 9026</sub>

<a id="cmd-add-task-ok"></a>
#### Ok

**Path:** Main Window &gt; Add Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 9027</sub>

<a id="cmd-add-task-save-to-current-file"></a>
#### Save To Current File

**Path:** Main Window &gt; Add Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 9036</sub>

<a id="cmd-add-task-save-to-android"></a>
#### Save To Android

**Path:** Main Window &gt; Add Task &gt; Save To Android  
**Kind:** Command

Write the object back to your Android device.

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 9058</sub>

<a id="cmd-add-task-save-to-android-verify"></a>
##### Verify

**Path:** Main Window &gt; Add Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-add-task-save-to-android-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Add Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1879</sub>

<a id="cmd-add-task-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main Window &gt; Add Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1880</sub>

<a id="cmd-add-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Add Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-add-task-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main Window &gt; Add Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1904</sub>

<a id="cmd-add-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Add Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-add-task-export-task"></a>
#### Export Task

**Path:** Main Window &gt; Add Task &gt; Export Task  
**Kind:** Command

Exports the Task as XML to a file on your computer.

<sub>Source: `guiwins.py` line 9067</sub>

<a id="cmd-edit-scene"></a>
### Edit Scene

**Path:** Main Window &gt; Edit Scene  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Scene**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 13998</sub>

<a id="cmd-edit-scene-picker"></a>
#### Picker

**Path:** Main Window &gt; Edit Scene &gt; Picker  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Variable / Show When Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3760</sub>

<a id="cmd-edit-scene-picker-close"></a>
##### Close

**Path:** Main Window &gt; Edit Scene &gt; Picker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 3718</sub>

<a id="cmd-edit-scene-palette"></a>
#### Palette

**Path:** Main Window &gt; Edit Scene &gt; Palette  
**Kind:** Command

Pick one of Material's own colour roles.

<sub>Source: `guiwins.py` line 3809</sub>

<a id="cmd-edit-scene-pick"></a>
#### Pick

**Path:** Main Window &gt; Edit Scene &gt; Pick  
**Kind:** Command

Pick a Material icon.

Opens **Icon**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3860</sub>

<a id="cmd-edit-scene-pick-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Scene &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3955</sub>

<a id="cmd-edit-scene-state"></a>
#### State

**Path:** Main Window &gt; Edit Scene &gt; State  
**Kind:** Pulldown

Dynamic and Select Variable are worked out when the Scene is shown.

<sub>Source: `guiwins.py` line 4027</sub>

<a id="cmd-edit-scene-variable"></a>
#### Variable

**Path:** Main Window &gt; Edit Scene &gt; Variable  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Variable / Show When Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 4075</sub>

<a id="cmd-edit-scene-variable-close"></a>
##### Close

**Path:** Main Window &gt; Edit Scene &gt; Variable &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 3718</sub>

<a id="cmd-edit-scene-show-when"></a>
#### Show When

**Path:** Main Window &gt; Edit Scene &gt; Show When  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Variable / Show When Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 4373</sub>

<a id="cmd-edit-scene-show-when-close"></a>
##### Close

**Path:** Main Window &gt; Edit Scene &gt; Show When &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 3718</sub>

<a id="cmd-edit-scene-close"></a>
#### Close

**Path:** Main Window &gt; Edit Scene &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 4453</sub>

<a id="cmd-edit-scene-add"></a>
#### Add

**Path:** Main Window &gt; Edit Scene &gt; Add  
**Kind:** Command

Adds inside the selected component if it can hold children, otherwise directly after it.

Opens **Add Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 4668</sub>

<a id="cmd-edit-scene-add-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Scene &gt; Add &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3371</sub>

<a id="cmd-edit-scene-undo"></a>
#### Undo

**Path:** Main Window &gt; Edit Scene &gt; Undo  
**Kind:** Command

Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. This changes what is loaded, not any file.

<sub>Source: `guiwins.py` line 4679</sub>

<a id="cmd-edit-scene-delete"></a>
#### Delete

**Path:** Main Window &gt; Edit Scene &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins.py` line 4732</sub>

<a id="cmd-edit-scene-landscape"></a>
#### Landscape

**Path:** Main Window &gt; Edit Scene &gt; Landscape  
**Kind:** Option

This Scene has no landscape layout of its own (its size is -1).

<sub>Source: `guiwins.py` line 6415</sub>

<a id="cmd-edit-scene-snap"></a>
#### Snap

**Path:** Main Window &gt; Edit Scene &gt; Snap  
**Kind:** Pulldown

Round dragged positions and sizes to this many pixels.

<sub>Source: `guiwins.py` line 6426</sub>

<a id="cmd-edit-scene-duplicate"></a>
#### Duplicate

**Path:** Main Window &gt; Edit Scene &gt; Duplicate  
**Kind:** Command

Make a copy of the selected Scene element.

<sub>Source: `guiwins.py` line 6500</sub>

<a id="cmd-edit-scene-rename"></a>
#### Rename

**Path:** Main Window &gt; Edit Scene &gt; Rename  
**Kind:** Command

Tasks address this element by name (Element Text, Element Position, ... 18 action codes in all), so renaming it is not a field edit. The Rename dialog lists what depends on the current name and offers to bring those Tasks along.

Opens **Rename Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 6705</sub>

<a id="cmd-edit-scene-rename-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Scene &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3454</sub>

<a id="cmd-edit-scene-rename-rename"></a>
##### Rename

**Path:** Main Window &gt; Edit Scene &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 3455</sub>

<a id="cmd-edit-scene-preview"></a>
#### Preview

**Path:** Main Window &gt; Edit Scene &gt; Preview  
**Kind:** Command

Draws this Scene as a picture in the main window -- including the components you have added or changed here but not yet saved.

A Version 2 layout has no size of its own, so the preview lays it out in a screen you pick, and re-flows it when you change that.

This dialog closes while the preview is up, with everything in it kept; the preview's 'Back to Editor' button brings it back.

It is a representation, not Tasker's own renderer: %variables are named rather than resolved, Material colours come from the baseline palette rather than the device's theme, and images, video and web content are shown as placeholders.

<sub>Source: `guiwins.py` line 7815</sub>

<a id="cmd-edit-scene-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Edit Scene &gt; Cancel  
**Kind:** Command

Closes without saving, and puts this Scene back exactly as it was when this dialog opened -- including anything moved or resized in the Preview.

A Rename is the one thing this cannot take back: it is applied to the loaded backup as it is confirmed, and closes this dialog with it.

<sub>Source: `guiwins.py` line 8205</sub>

<a id="cmd-edit-scene-ok"></a>
#### Ok

**Path:** Main Window &gt; Edit Scene &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 8234</sub>

<a id="cmd-edit-scene-save-to-current-file"></a>
#### Save To Current File

**Path:** Main Window &gt; Edit Scene &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile, Task and Scene in it, not just this Scene -- including every edit made anywhere in this session. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 8238</sub>

<a id="cmd-edit-scene-save-to-android"></a>
#### Save To Android

**Path:** Main Window &gt; Edit Scene &gt; Save To Android  
**Kind:** Command

This will write the Scene as a standalone file onto your Android device, under /Tasker/scenes -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running.

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Scene To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 8259</sub>

<a id="cmd-edit-scene-save-to-android-verify"></a>
##### Verify

**Path:** Main Window &gt; Edit Scene &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 1792</sub>

<a id="cmd-edit-scene-save-to-android-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Edit Scene &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8367</sub>

<a id="cmd-edit-scene-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main Window &gt; Edit Scene &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Scene as a standalone file onto the Android device, under /Tasker/scenes.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 8368</sub>

<a id="cmd-edit-scene-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main Window &gt; Edit Scene &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-scene-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main Window &gt; Edit Scene &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This sends the Scene -- and every Task its elements fire -- to the Android device under its own name, into /Tasker/scenes, and opens Android's 'Open with...' chooser for it.

If Tasker is in that chooser, pick it. A Scene is the one kind Tasker has been seen to refuse when it is handed one, so if it is not there -- or nothing happens -- finish it with Tasker's 'Scenes > Import One Scene' and pick the Scene by name. The file is on the device either way, and the message tells you its name.

You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 8390</sub>

<a id="cmd-edit-scene-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main Window &gt; Edit Scene &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1848</sub>

<a id="cmd-edit-scene-export-scene"></a>
#### Export Scene

**Path:** Main Window &gt; Edit Scene &gt; Export Scene  
**Kind:** Command

Saves this Scene, with all of its elements, as one standalone .scn.xml file -- the same format Tasker's own Scene export produces.

Tasks the Scene's elements run are not included; they belong to their own Project.

<sub>Source: `guiwins.py` line 8280</sub>

<a id="cmd-add-scene"></a>
### Add Scene

**Path:** Main Window &gt; Add Scene  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Scene Version**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 14006</sub>

<a id="cmd-add-scene-legacy-scene"></a>
#### Legacy Scene

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene  
**Kind:** Command

A Legacy Scene has a pixel canvas and a list of UI elements. It is the original Scene format, and is what Tasker itself produces.

Opens **Add Scene**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 7937</sub>

<a id="cmd-add-scene-legacy-scene-picker"></a>
##### Picker

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Picker  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Variable / Show When Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3760</sub>

<a id="cmd-add-scene-legacy-scene-picker-close"></a>
###### Close

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Picker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 3718</sub>

<a id="cmd-add-scene-legacy-scene-palette"></a>
##### Palette

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Palette  
**Kind:** Command

Pick one of Material's own colour roles.

<sub>Source: `guiwins.py` line 3809</sub>

<a id="cmd-add-scene-legacy-scene-pick"></a>
##### Pick

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Pick  
**Kind:** Command

Pick a Material icon.

Opens **Icon**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3860</sub>

<a id="cmd-add-scene-legacy-scene-pick-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3955</sub>

<a id="cmd-add-scene-legacy-scene-state"></a>
##### State

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; State  
**Kind:** Pulldown

Dynamic and Select Variable are worked out when the Scene is shown.

<sub>Source: `guiwins.py` line 4027</sub>

<a id="cmd-add-scene-legacy-scene-variable"></a>
##### Variable

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Variable  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Variable / Show When Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 4075</sub>

<a id="cmd-add-scene-legacy-scene-variable-close"></a>
###### Close

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Variable &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 3718</sub>

<a id="cmd-add-scene-legacy-scene-show-when"></a>
##### Show When

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Show When  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Variable / Show When Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 4373</sub>

<a id="cmd-add-scene-legacy-scene-show-when-close"></a>
###### Close

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Show When &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 3718</sub>

<a id="cmd-add-scene-legacy-scene-close"></a>
##### Close

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 4453</sub>

<a id="cmd-add-scene-legacy-scene-add"></a>
##### Add

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Add  
**Kind:** Command

Adds inside the selected component if it can hold children, otherwise directly after it.

Opens **Add Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 4668</sub>

<a id="cmd-add-scene-legacy-scene-add-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Add &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3371</sub>

<a id="cmd-add-scene-legacy-scene-undo"></a>
##### Undo

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Undo  
**Kind:** Command

Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. This changes what is loaded, not any file.

<sub>Source: `guiwins.py` line 4679</sub>

<a id="cmd-add-scene-legacy-scene-delete"></a>
##### Delete

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins.py` line 4732</sub>

<a id="cmd-add-scene-legacy-scene-landscape"></a>
##### Landscape

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Landscape  
**Kind:** Option

This Scene has no landscape layout of its own (its size is -1).

<sub>Source: `guiwins.py` line 6415</sub>

<a id="cmd-add-scene-legacy-scene-snap"></a>
##### Snap

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Snap  
**Kind:** Pulldown

Round dragged positions and sizes to this many pixels.

<sub>Source: `guiwins.py` line 6426</sub>

<a id="cmd-add-scene-legacy-scene-duplicate"></a>
##### Duplicate

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Duplicate  
**Kind:** Command

Make a copy of the selected Scene element.

<sub>Source: `guiwins.py` line 6500</sub>

<a id="cmd-add-scene-legacy-scene-rename"></a>
##### Rename

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Rename  
**Kind:** Command

Tasks address this element by name (Element Text, Element Position, ... 18 action codes in all), so renaming it is not a field edit. The Rename dialog lists what depends on the current name and offers to bring those Tasks along.

Opens **Rename Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 6705</sub>

<a id="cmd-add-scene-legacy-scene-rename-cancel"></a>
###### Cancel

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3454</sub>

<a id="cmd-add-scene-legacy-scene-rename-rename"></a>
###### Rename

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 3455</sub>

<a id="cmd-add-scene-legacy-scene-preview"></a>
##### Preview

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Preview  
**Kind:** Command

Draws this Scene as a picture in the main window -- including the components you have added or changed here but not yet saved.

A Version 2 layout has no size of its own, so the preview lays it out in a screen you pick, and re-flows it when you change that.

This dialog closes while the preview is up, with everything in it kept; the preview's 'Back to Editor' button brings it back.

It is a representation, not Tasker's own renderer: %variables are named rather than resolved, Material colours come from the baseline palette rather than the device's theme, and images, video and web content are shown as placeholders.

<sub>Source: `guiwins.py` line 7815</sub>

<a id="cmd-add-scene-legacy-scene-cancel"></a>
##### Cancel

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8022</sub>

<a id="cmd-add-scene-legacy-scene-ok"></a>
##### Ok

**Path:** Main Window &gt; Add Scene &gt; Legacy Scene &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 8023</sub>

<a id="cmd-add-scene-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Add Scene &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 7978</sub>

<a id="cmd-reset-to-default-colors"></a>
### Reset to Default Colors

**Path:** Main Window &gt; Reset to Default Colors  
**Kind:** Command

Restore every color to its default value.

<sub>Source: `guiwins.py` line 14039</sub>

<a id="cmd-cancel"></a>
### Cancel

**Path:** Main Window &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 14109</sub>

<a id="cmd-change-prompt"></a>
### Change Prompt

**Path:** Main Window &gt; Change Prompt  
**Kind:** Command

Modify the prompt sent to the AI model.

Opens **Change Prompt**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 14151</sub>

<a id="cmd-change-prompt-cancel"></a>
#### Cancel

**Path:** Main Window &gt; Change Prompt &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `userintr.py` line 6566</sub>

<a id="cmd-run-analysis"></a>
### Run Analysis

**Path:** Main Window &gt; Run Analysis  
**Kind:** Command

Submit the selected Project/Profile/Task and prompt to the selected model.

<sub>Source: `guiwins.py` line 14156</sub>

<a id="cmd-extended"></a>
### Extended

**Path:** Main Window &gt; Extended  
**Kind:** Option

Display an extended list of ALL available models.

Note: If the API key is not set for OpenAI or Gemini, then the default model list for the respective AI provider will be displayed.

Note: Not all models have been validated and one or more may return an error on analysis.

Note: Enabling this option for the first time will force the installation of the following modules and all of their dependencies: google-genai, anthropic, openai, ollama

<sub>Source: `guiwins.py` line 14175</sub>

<a id="cmd-indent-option"></a>
### Indent Option

**Path:** Main Window &gt; Indent Option  
**Kind:** Pulldown

Set the indentation amount for If/Then/Else blocks.

The default is '4'.

This affects how the output is formatted in the Map and Diagram views.

<sub>Source: `guiwins.py` line 14282</sub>

<a id="cmd-viewlimit-optionmenu"></a>
### Viewlimit Optionmenu

**Path:** Main Window &gt; Viewlimit Optionmenu  
**Kind:** Pulldown

Select the maximum number of items to display in the view to be allowed.

Anything over this amount will stop the generation of the view as a means to throttle the program.

Note: This is only for the 'Map' and 'Diagram' views, not the tree view.

<sub>Source: `guiwins.py` line 14332</sub>

<a id="cmd-notify-timeout-optionmenu"></a>
### Notify Timeout Optionmenu

**Path:** Main Window &gt; Notify Timeout Optionmenu  
**Kind:** Pulldown

How long a pop-up message stays on screen before it disappears.

'Until dismissed' keeps every message up until you close it, which is useful when a message scrolls past before you can read it.

A few messages set their own longer duration because they list things you have to read -- the Tasks affected by deleting or renaming a Scene element, for instance. Those keep their own timing whatever is chosen here.

<sub>Source: `guiwins.py` line 14373</sub>

<a id="cmd-reset-options"></a>
### Reset Options

**Path:** Main Window &gt; Reset Options  
**Kind:** Command

Reset all of the options to their default values, including colors, font used, and other settings.

The currently loaded XML will be cleared out.

<sub>Source: `guiwins.py` line 14397</sub>

<a id="cmd-report-issue"></a>
### Report Issue

**Path:** Main Window &gt; Report Issue  
**Kind:** Command

Report any issues and/or suggestions to the developer.

This will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.

<sub>Source: `guiwins.py` line 14430</sub>

<a id="cmd-font-optionmenu"></a>
### Font Optionmenu

**Path:** Main Window &gt; Font Optionmenu  
**Kind:** Pulldown

This is a list of all of the fonts available on your system, monospaced ones first and marked as such.

The font selected will be used in all output.

'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector alignment. A font that is not monospaced will not hold the Diagram's connectors or the output's indentation in line.

<sub>Source: `guiwins.py` line 14470</sub>

<a id="cmd-get-xml-from-android-device"></a>
### Get XML from Android Device

**Path:** Main Window &gt; Get XML from Android Device  
**Kind:** Command

Fetch XML from an Android device.

You must be on the same network as the Android device, and the device must be running and connected.

Opens **Get XML From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 14499</sub>

<a id="cmd-get-xml-from-android-device-list-xml-files"></a>
#### List XML Files

**Path:** Main Window &gt; Get XML from Android Device &gt; List XML Files  
**Kind:** Command

List the XML files found on the Android device so you can select one rather than typing its location.

Opens **Android XML File List**, whose own commands are listed beneath this one.

<sub>Source: `userintr.py` line 2915</sub>

<a id="cmd-get-xml-from-android-device-list-xml-files-cancel-entry"></a>
##### Cancel Entry

**Path:** Main Window &gt; Get XML from Android Device &gt; List XML Files &gt; Cancel Entry  
**Kind:** Command

Back out of the Android fetch process.

<sub>Source: `guiutils.py` line 1732</sub>

<a id="cmd-get-xml-from-android-device-list-helper-tasks"></a>
#### List Helper Tasks

**Path:** Main Window &gt; Get XML from Android Device &gt; List Helper Tasks  
**Kind:** Command

Lists the 'MapTasker ...' Tasks this program has installed on the Android device, and says which are left over from an earlier version.

Each one is installed under a versioned name and never replaced -- Tasker's import adds a second Task rather than replacing the first -- so old ones stay behind in your Task list. They do no harm; they are clutter.

Delete the ones it names from Tasker's own Tasks tab. Nothing here can do it for you: Tasker's HTTP API has no way to delete a Task.

Opens **Helper Tasks**, whose own commands are listed beneath this one.

<sub>Source: `userintr.py` line 2931</sub>

<a id="cmd-get-xml-from-android-device-list-helper-tasks-close"></a>
##### Close

**Path:** Main Window &gt; Get XML from Android Device &gt; List Helper Tasks &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 8470</sub>

<a id="cmd-get-xml-from-android-device-cancel-entry"></a>
#### Cancel Entry

**Path:** Main Window &gt; Get XML from Android Device &gt; Cancel Entry  
**Kind:** Command

Back out of the Android fetch process.

<sub>Source: `userintr.py` line 2956</sub>

<a id="cmd-display-help"></a>
### Display Help

**Path:** Main Window &gt; Display Help  
**Kind:** Command

Display this help text.

<sub>Source: `guiwins.py` line 14530</sub>

<a id="cmd-get-android-help"></a>
### Get Android Help

**Path:** Main Window &gt; Get Android Help  
**Kind:** Command

Display the help for fetching the XML file from your Android device.

<sub>Source: `guiwins.py` line 14537</sub>

## AI API Key Entry

_Initialize the NiceGUI dialog container._

<a id="cmd-ok"></a>
### OK

**Path:** AI API Key Entry &gt; OK  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins2.py` line 39</sub>

<a id="cmd-cancel-2"></a>
### Cancel

**Path:** AI API Key Entry &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins2.py` line 50</sub>

<a id="cmd-clear-2"></a>
### Clear

**Path:** AI API Key Entry &gt; Clear  
**Kind:** Command

Clear the Map/Diagram/Tree view data currently held and displayed.

<sub>Source: `guiwins2.py` line 87</sub>

## Action Condition

_Prompts for a per-action If condition (Target/Operator/Value) when the action's "If" checkbox is checked -- see _render_action_condition_checkbox._

<a id="cmd-cancel-3"></a>
### Cancel

**Path:** Action Condition &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1233</sub>

<a id="cmd-ok-2"></a>
### Ok

**Path:** Action Condition &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 1237</sub>

## Choose An If Variant

_Prompts for how much of an If block to insert when the user picks the "If" action in an Add/Edit Task action picker: just the "If", "If" plus a matching "End If", or a full "If"/"Else"/"End If" skeleton -- see taskedit.IF_BLOCK_VARIANTS/add_if_block_to_task._

<a id="cmd-cancel-4"></a>
### Cancel

**Path:** Choose An If Variant &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1352</sub>

## Delete Project

_Confirms deletion of a Project, offering a choice for what happens to the Profiles/Tasks it owns: moved into "Base" (Keep Contents) or deleted along with it (Delete Contents) -- see projedit.delete_project._

<a id="cmd-cancel-5"></a>
### Cancel

**Path:** Delete Project &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8657</sub>

## Delete Scene

_Confirms deletion of a Scene._

<a id="cmd-cancel-6"></a>
### Cancel

**Path:** Delete Scene &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8331</sub>

## Item Layout Designer

_Edit the Scene inside a List or a Spinner, in a designer of its own._

<a id="cmd-close"></a>
### Close

**Path:** Item Layout Designer &gt; Close  
**Kind:** Command

Stop firing anything on this event.

<sub>Source: `guiwins.py` line 6184</sub>

<a id="cmd-landscape"></a>
### Landscape

**Path:** Item Layout Designer &gt; Landscape  
**Kind:** Option

This Scene has no landscape layout of its own (its size is -1).

<sub>Source: `guiwins.py` line 6415</sub>

<a id="cmd-snap"></a>
### Snap

**Path:** Item Layout Designer &gt; Snap  
**Kind:** Pulldown

Round dragged positions and sizes to this many pixels.

<sub>Source: `guiwins.py` line 6426</sub>

<a id="cmd-add"></a>
### Add

**Path:** Item Layout Designer &gt; Add  
**Kind:** Command

Adds an element on top of the stack, in the middle of the Scene.

Opens **Add Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 6434</sub>

<a id="cmd-add-cancel"></a>
#### Cancel

**Path:** Item Layout Designer &gt; Add &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3578</sub>

<a id="cmd-undo-2"></a>
### Undo

**Path:** Item Layout Designer &gt; Undo  
**Kind:** Command

Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. This changes what is loaded, not any file.

<sub>Source: `guiwins.py` line 6441</sub>

<a id="cmd-duplicate"></a>
### Duplicate

**Path:** Item Layout Designer &gt; Duplicate  
**Kind:** Command

Make a copy of the selected Scene element.

<sub>Source: `guiwins.py` line 6500</sub>

<a id="cmd-delete"></a>
### Delete

**Path:** Item Layout Designer &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins.py` line 6503</sub>

<a id="cmd-done"></a>
### Done

**Path:** Item Layout Designer &gt; Done  
**Kind:** Command

Closes this dialog, keeping what was edited in it.

<sub>Source: `guiwins.py` line 6579</sub>

<a id="cmd-rename"></a>
### Rename

**Path:** Item Layout Designer &gt; Rename  
**Kind:** Command

Tasks address this element by name (Element Text, Element Position, ... 18 action codes in all), so renaming it is not a field edit. The Rename dialog lists what depends on the current name and offers to bring those Tasks along.

Opens **Rename Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 6705</sub>

<a id="cmd-rename-cancel"></a>
#### Cancel

**Path:** Item Layout Designer &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3454</sub>

<a id="cmd-rename-rename"></a>
#### Rename

**Path:** Item Layout Designer &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 3455</sub>

## Map / Diagram / Tree View Toolbar

_Builds the UI layout for the various text views, including toolbar and scrollable display area._

<a id="cmd-zoom-out"></a>
### Zoom Out

**Path:** Map / Diagram / Tree View Toolbar &gt; Zoom Out  
**Kind:** Command

Zoom out. Ctrl/⌘ and the scroll wheel does the same.

<sub>Source: `guiwins.py` line 9194</sub>

<a id="cmd-zoom-in"></a>
### Zoom In

**Path:** Map / Diagram / Tree View Toolbar &gt; Zoom In  
**Kind:** Command

Zoom in. Ctrl/⌘ and the scroll wheel does the same.

<sub>Source: `guiwins.py` line 9202</sub>

<a id="cmd-collapse"></a>
### Collapse

**Path:** Map / Diagram / Tree View Toolbar &gt; Collapse  
**Kind:** Command

Collapse every Project down to its title bar.

One Project on its own collapses by clicking the top edge of its box.

<sub>Source: `guiwins.py` line 9207</sub>

<a id="cmd-expand"></a>
### Expand

**Path:** Map / Diagram / Tree View Toolbar &gt; Expand  
**Kind:** Command

Expand every collapsed Project.

<sub>Source: `guiwins.py` line 9220</sub>

<a id="cmd-reset"></a>
### Reset

**Path:** Map / Diagram / Tree View Toolbar &gt; Reset  
**Kind:** Command

Back to the whole diagram: no zoom, nothing folded, nothing filtered.

<sub>Source: `guiwins.py` line 9225</sub>

<a id="cmd-help"></a>
### Help

**Path:** Map / Diagram / Tree View Toolbar &gt; Help  
**Kind:** Command

The diagram is clickable:

Click a Project, Profile, Task or Scene name to be taken to it in the Map.

Shift-click a Task to light up the whole chain of calls it takes part in -- everything it calls, everything that calls it, and the arrows between them.

Right-click any name for the rest: collapse its Project, show only that Project, follow its chain.

Click the ▾ beside a Project to collapse it, and the ▸ to bring it back.

Ctrl (or ⌘) and the scroll wheel zooms. Esc clears a chain.

<sub>Source: `guiwins.py` line 9232</sub>

<a id="cmd-search"></a>
### Search

**Path:** Map / Diagram / Tree View Toolbar &gt; Search  
**Kind:** Command

The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data.

It will only show the first 200 instances of the search string.

Click on the line number to go to that line in the text view box.

The 'Clear' button will clear the search results.

<sub>Source: `guiwins.py` line 10671</sub>

<a id="cmd-clear-3"></a>
### Clear

**Path:** Map / Diagram / Tree View Toolbar &gt; Clear  
**Kind:** Command

Clear the Map/Diagram/Tree view data currently held and displayed.

<sub>Source: `guiwins.py` line 10681</sub>

<a id="cmd-find-replace"></a>
### Find/Replace

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace  
**Kind:** Command

'Find/Replace' asks the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything that names a given app or Scene.

The boxes combine -- pick a trigger and an action to find the Profiles that trigger that way and run a Task that does that.

Results come back as a list of objects; click one to be taken to it.

Opens **Find / Replace**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 10690</sub>

<a id="cmd-find-replace-narrow-to-project"></a>
#### Narrow to Project

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Narrow to Project  
**Kind:** Pulldown

_There is no tooltip on this one; this is the note written beside it in the source._

Hidden under a scope, for the reason the Find tab's own gives.

<sub>Source: `guiwins.py` line 11647</sub>

<a id="cmd-find-replace-only-the-matching-text"></a>
#### Only the matching text

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Only the matching text  
**Kind:** Option

_There is no tooltip on this one; this is the note written beside it in the source._

Off means the argument is SET to the new value; on means only the matched text inside it changes. Both are things people mean by "replace", and which one they meant cannot be guessed from the two boxes above -- so it is asked, in the one place where the answer is visible while the values are being typed.

<sub>Source: `guiwins.py` line 11702</sub>

<a id="cmd-find-replace-add-it-where-missing"></a>
#### Add it where missing

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Add it where missing  
**Kind:** Option

_There is no tooltip on this one; this is the note written beside it in the source._

Tasker leaves out an argument nobody ever set, so this is what makes "give every Flash a Timeout" reach the Flashes that have none. Off by default: adding an argument to a hundred actions is a bigger thing than editing the ones that already have it, and the preview marks every row that is an addition rather than a change.

<sub>Source: `guiwins.py` line 11708</sub>

<a id="cmd-find-replace-preview"></a>
#### Preview

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Preview  
**Kind:** Command

Display the Scene being edited as it will appear.

<sub>Source: `guiwins.py` line 12193</sub>

<a id="cmd-find-replace-replace"></a>
#### Replace

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Replace  
**Kind:** Command

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins.py` line 12194</sub>

<a id="cmd-find-replace-find"></a>
#### Find

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Find  
**Kind:** Tab

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins.py` line 12410</sub>

<a id="cmd-find-replace-replace-2"></a>
#### Replace

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Replace  
**Kind:** Tab

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins.py` line 12411</sub>

<a id="cmd-find-replace-find-2"></a>
#### Find

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Find  
**Kind:** Command

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins.py` line 12599</sub>

<a id="cmd-find-replace-save-results"></a>
#### Save Results

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Save Results  
**Kind:** Command

Save the 'Find/Replace' results to a text file.

<sub>Source: `guiwins.py` line 12600</sub>

<a id="cmd-find-replace-close"></a>
#### Close

**Path:** Map / Diagram / Tree View Toolbar &gt; Find/Replace &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 12610</sub>

<a id="cmd-toggle-wrap"></a>
### Toggle Wrap

**Path:** Map / Diagram / Tree View Toolbar &gt; Toggle Wrap  
**Kind:** Command

Turn line wrapping on or off in the displayed output.

<sub>Source: `guiwins.py` line 10707</sub>

<a id="cmd-profiles-per-line"></a>
### Profiles Per Line

**Path:** Map / Diagram / Tree View Toolbar &gt; Profiles Per Line  
**Kind:** Pulldown

(Diagram only) The number of Profiles drawn side-by-side on a single line.

<sub>Source: `guiwins.py` line 10717</sub>

## New Version Notice

_Check if a new version is available and dynamically populate the upgrade container slot inside the right sidebar._

<a id="cmd-upgrade-to-latest-version"></a>
### Upgrade to Latest Version

**Path:** New Version Notice &gt; Upgrade to Latest Version  
**Kind:** Command

Clicking this will launch 'pip install --upgrade maptasker' in the background, and then relaunch MapTasker.

<sub>Source: `guiutils.py` line 1853</sub>

<a id="cmd-what-s-new"></a>
### What's New?

**Path:** New Version Notice &gt; What's New?  
**Kind:** Command

Display the changes in the new version.

<sub>Source: `guiutils.py` line 1865</sub>

## Object Properties

_The Properties editor, shared by every Add/Edit dialog -- see the section comment._

<a id="cmd-same-as-value"></a>
### Same as Value

**Path:** Object Properties &gt; Same as Value  
**Kind:** Option

Under 'Exported Value' if you disable the 'Same as Value' option, you can customize what value gets exported when you share the variable with other users. You can keep the 'Exported Value' field blank if you want the export to not have a value at all, or you can set the value you wish to always use for exports. If you enable the 'Same as Value' option, the current variable value will be used when exporting.

<sub>Source: `guiwins.py` line 3088</sub>

<a id="cmd-cancel-7"></a>
### Cancel

**Path:** Object Properties &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3199</sub>

<a id="cmd-ok-3"></a>
### Ok

**Path:** Object Properties &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 3203</sub>

## Overwrite Confirmation

_Confirms overwriting something that is already there, before anything is written._

<a id="cmd-cancel-8"></a>
### Cancel

**Path:** Overwrite Confirmation &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 8508</sub>

## Render Scene

_One Event sub-tab: when it fires, the Task it fires, and what that Task can read._

<a id="cmd-pick-a-task"></a>
### Pick a Task

**Path:** Render Scene &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins.py` line 557</sub>

<a id="cmd-pick"></a>
### Pick

**Path:** Render Scene &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1164</sub>

<a id="cmd-pick-use"></a>
#### Use

**Path:** Render Scene &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins.py` line 740</sub>

<a id="cmd-pick-cancel"></a>
#### Cancel

**Path:** Render Scene &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 848</sub>

<a id="cmd-pick-use-selected"></a>
#### Use Selected

**Path:** Render Scene &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins.py` line 849</sub>

<a id="cmd-pick-icon-not-listed"></a>
#### Icon not listed?

**Path:** Render Scene &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Applications From Android Device**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 865</sub>

<a id="cmd-pick-icon-not-listed-cancel"></a>
##### Cancel

**Path:** Render Scene &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 705</sub>

<a id="cmd-delete-2"></a>
### Delete

**Path:** Render Scene &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins.py` line 1531</sub>

<a id="cmd-close-2"></a>
### Close

**Path:** Render Scene &gt; Close  
**Kind:** Command

Stop firing anything on this event.

<sub>Source: `guiwins.py` line 7424</sub>

<a id="cmd-stop-event"></a>
### Stop Event

**Path:** Render Scene &gt; Stop Event  
**Kind:** Option

Any key handled by the scene is not passed on to the system -- how a Scene keeps the back key from closing it. Written the way Tasker writes it: a <stopEvent> inside the Scene's <LinkClickFilter>, created when this is ticked and taken away again when it is unticked and nothing else is left in it.

<sub>Source: `guiwins.py` line 7530</sub>

<a id="cmd-apply-to-task"></a>
### Apply to Task

**Path:** Render Scene &gt; Apply to Task  
**Kind:** Command

Puts these action edits into the loaded configuration now, without closing -- the same as 'Ok' in the Edit Task dialog. Ok does it for you here too, so this is only for keeping them mid-edit. Nothing is written to a file and nothing is sent to Android. This Task is not part of the Scene, so neither this window's Cancel nor the Scene dialog's takes these edits back once they have landed. Undo does.

<sub>Source: `guiwins.py` line 7626</sub>

<a id="cmd-create-task"></a>
### Create Task

**Path:** Render Scene &gt; Create Task  
**Kind:** Command

Adds this Task to the loaded configuration and points this event at it, the same as 'Ok' in the Add Task dialog -- nothing is written to a file and nothing is sent to Android. Ok does it for you too, so this is only for creating it without closing. Until then the Task exists only in this window and Cancel discards it. Afterwards it is a Task like any other -- Cancel takes the binding back but not the Task, and Undo takes both.

<sub>Source: `guiwins.py` line 7740</sub>

## Scene Preview Window

_Toolbar, then the scroll area the canvas is drawn into._

<a id="cmd-bounds"></a>
### Bounds

**Path:** Scene Preview Window &gt; Bounds  
**Kind:** Option

Outline every component and name it, the way the designer's tree names it.

<sub>Source: `guiwins.py` line 9982</sub>

<a id="cmd-actions"></a>
### Actions

**Path:** Scene Preview Window &gt; Actions  
**Kind:** Option

Show what each component does when tapped, and what it writes to.

<sub>Source: `guiwins.py` line 9995</sub>

<a id="cmd-landscape-2"></a>
### Landscape

**Path:** Scene Preview Window &gt; Landscape  
**Kind:** Option

Turn the screen on its side and let the layout re-flow into it.

<sub>Source: `guiwins.py` line 10036</sub>

<a id="cmd-text-density"></a>
### Text density

**Path:** Scene Preview Window &gt; Text density  
**Kind:** Pulldown

A Scene's element positions are stored in device pixels, but its text sizes are stored in Android's sp units. The number that converts between the two is a property of the phone the Scene is shown on, and is not in the backup file.

So it is set here. Raise it if the text looks too small for its elements, lower it if the text overflows them.

<sub>Source: `guiwins.py` line 10059</sub>

<a id="cmd-snap-2"></a>
### Snap

**Path:** Scene Preview Window &gt; Snap  
**Kind:** Pulldown

Round dragged positions and sizes to this many pixels.

<sub>Source: `guiwins.py` line 10092</sub>

<a id="cmd-screen"></a>
### Screen

**Path:** Scene Preview Window &gt; Screen  
**Kind:** Pulldown

A Version 2 Scene has no size of its own -- it lays itself out inside whatever screen it is shown on, so there is nothing in the backup file to draw it at.

Change this to see the layout re-flow. A Flow Row wraps differently, and any 'Show when' written against %sv2_render_width is asking about exactly this.

<sub>Source: `guiwins.py` line 10115</sub>

## Scene Properties

_The Scene's own Properties -- its <PropertiesElement> -- laid out the way Tasker's own "Scene Properties Edit" screen is: UI, Actions and Event, with Event holding Key, Home Tap and Tab Tap._

<a id="cmd-rename-2"></a>
### Rename

**Path:** Scene Properties &gt; Rename  
**Kind:** Command

Tasks address this element by name (Element Text, Element Position, ... 18 action codes in all), so renaming it is not a field edit. The Rename dialog lists what depends on the current name and offers to bring those Tasks along.

Opens **Rename Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 6705</sub>

<a id="cmd-rename-cancel-2"></a>
#### Cancel

**Path:** Scene Properties &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3454</sub>

<a id="cmd-rename-rename-2"></a>
#### Rename

**Path:** Scene Properties &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 3455</sub>

<a id="cmd-cancel-9"></a>
### Cancel

**Path:** Scene Properties &gt; Cancel  
**Kind:** Command

Puts these properties back the way they were when this window opened, and drops the actions of any Task edited under the Event tab. A Task already put into the configuration by its own button -- 'Apply to Task', or 'Create Task' -- stays there. Undo takes those back.

<sub>Source: `guiwins.py` line 6998</sub>

<a id="cmd-ok-4"></a>
### Ok

**Path:** Scene Properties &gt; Ok  
**Kind:** Command

Keeps everything, including the actions of any Task edited under the Event tab. A Task composed under an event that had none is created and bound if you put any actions in it. Undo takes a Task edit back.

<sub>Source: `guiwins.py` line 7008</sub>

<a id="cmd-delete-3"></a>
### Delete

**Path:** Scene Properties &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins.py` line 7186</sub>

## Command-Line Arguments

MapTasker can also be run from a terminal, where these arguments do the same job the settings above do in the window:

```
maptasker [arguments]
```

| Argument | Choices | What it does |
| --- | --- | --- |
| `-ai_model` |  | The model to use for Profiles and Tasks Ai analysis. |
| `-android_file` |  | File location of Tasker backup file on Android device Example: -a-android_file /Tasker/configs/user/backup.xml Also requires -android_ipaddr and -android_port arguments |
| `-android_ipaddr` |  | TCP/IP Address of Android device running Tasker server Example: -android_ipaddr 192.168.0.210 Also requires -android_port and -android_file arguments |
| `-android_port` |  | Port number of Android device running Tasker server Example: -android_port 1821 Also requires -android_ipaddr and -android_file arguments |
| `-appearance` | system, light, dark | Display appearance mode: system (default), light, dark Example: -appearance dark |
| `-conditions` |  | Display the condition(s) for Profiles and Tasks |
| `-debug` |  | Print and log debug information |
| `-detail` |  | Level of detail to display: 0 = display simple Project/Profile/Task/Scene names only with no details 1 = display all Task action details for unknown Tasks only 2 = display full Task action name on every Task 3 = display full Task action details on every Task with action details (default) 4 = detail level 3 plus global variables 5 = detail level 4 plus Scene element UI details. Example: '-detail 2' for Task action names only |
| `-directory` |  | Display a directory of hotlinks for all Projects/Profiles/Tasks/Scenes. |
| `-e`, `-everything` |  | Display everything: full detail, Profile/Task conditions, TaskerNet information, directory, etc.. |
| `-file` |  | Directory and file name of Tasker XML file to analyze. Example: -file ~/Downloads/backup.xml |
| `-font` |  | Name of monospaced font to use in output (default = 'Courier'). Enter font name of 'help' for a list of valid fonts. |
| `-g`, `-gui` |  | Prompt for (these) settings via the graphical user interface (GUI): This argument overrides all other arguments. |
| `-guiview` |  |  |
| `-i`, `-indent` |  | Number of spaces to indent Task If/Then/Else Actions (default = 4) |
| `-names` | bold, highlight, underline, italicize | Display all Projects/Profiles/Tasks/Scenes in bold, underlined, italicized and/or highlighted text. Example: names underline italicize |
| `-o`, `-outline` |  | Display configuration outline of Projects, Profiles, Tasks and Scenes, and display the configuraion Map (MapTasker_map.txt) in the default text editor" |
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
| `-view_limit` |  |  |

---

This page is generated from the MapTasker source by [`build_command_wiki.py`](https://github.com/mctinker/Map-Tasker/blob/Master/Misc%20Utilities/build_command_wiki.py). To refresh it after commands are added or changed:

```
python "Misc Utilities/build_command_wiki.py" --publish
```
