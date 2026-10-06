# MapTasker Command Reference

Every command, option and pulldown in the MapTasker user interface: **354** entries (**287** of them commands) across **30** windows.

_Generated from the MapTasker 14.1.1 source on 2026-10-06 by `build_command_wiki.py`._ _Do not edit this page by hand -- rerun that program instead._

## How to use this page

* **Searching:** press `Ctrl`/`⌘` + `F` and type any part of a command's name. Every command appears twice -- once in the alphabetical index, once in full under its window -- so a search always lands on something.
* **Reading a path:** commands are written as the clicks that get you there. `Edit Profile > Save To Android > Import Into Tasker` means click **Edit Profile**, then **Save To Android** in the dialog that opens, then **Import Into Tasker**.
* **Kinds:** _Command_ is a button, _Menu item_ sits in a pulldown menu, _Option_ is a checkbox or switch, _Pulldown_ is a list to choose from, and _Tab_ switches panels.
* **Descriptions** are the text MapTasker shows when you hover over the command.  Where a command has no hover text, the description comes from MapTasker's own Help, or from the note written beside it in the source -- which is said, where that is so.

## Contents

* [Command Index (A-Z)](#command-index-a-z)
* [AI API Key Entry](#ai-api-key-entry)
* [Action Condition](#action-condition)
* [Buttons](#buttons)
* [Delete Project](#delete-project)
* [Delete Scene](#delete-scene)
* [Get Xml From Android](#get-xml-from-android)
* [Header](#header)
* [If Variant](#if-variant)
* [Init](#init)
* [Item Layout](#item-layout)
* [Left Drawer](#left-drawer)
* [Main](#main)
* [Notification Log](#notification-log)
* [Object Properties](#object-properties)
* [Overwrite Confirmation](#overwrite-confirmation)
* [Render Background](#render-background)
* [Render Handlers](#render-handlers)
* [Render Header](#render-header)
* [Render Header](#render-header)
* [Render Modifiers](#render-modifiers)
* [Render Scene](#render-scene)
* [Render Tasks](#render-tasks)
* [Render Toolbar](#render-toolbar)
* [Render Toolbar](#render-toolbar)
* [Right Drawer](#right-drawer)
* [Scene Properties](#scene-properties)
* [Ui](#ui)
* [Ui](#ui)
* [Upgrade If Newer](#upgrade-if-newer)
* [Validate Or Filelist Xml](#validate-or-filelist-xml)
* [Command-Line Arguments](#command-line-arguments)

## Command Index (A-Z)

| Command | Kind | Where it is | What it does |
| --- | --- | --- | --- |
| [Actions](#cmd-actions) | Option | Ui | Show what each component does when tapped, and what it writes to. |
| [Add](#cmd-add) | Command | Render Header | Adds an element on top of the stack, in the middle of the Scene. |
| [Add](#cmd-add-2) | Command | Render Header | Adds inside the selected component if it can hold children, otherwise directly after it. |
| [Add it where missing](#cmd-add-it-where-missing) | Option | Init | Tasker leaves out an argument nobody ever set, so this is what makes "give every Flash a Timeout" reach the Flashes that have none. |
| [Add Profile](#cmd-add-profile) | Command | Main | Create a new object and add it to the loaded XML. |
| [Add Project](#cmd-add-project) | Command | Main | Create a new object and add it to the loaded XML. |
| [Add Scene](#cmd-add-scene) | Command | Main | Create a new object and add it to the loaded XML. |
| [Add Task](#cmd-add-profile-add-task) | Command | Main &gt; Add Profile | Create a new object and add it to the loaded XML. |
| [Add Task](#cmd-add-task) | Command | Main | Create a new object and add it to the loaded XML. |
| [Add Task](#cmd-edit-profile-add-task) | Command | Main &gt; Edit Profile | Create a new object and add it to the loaded XML. |
| [AI Model](#cmd-ai-model) | Pulldown | Main | Select the model belonging to the AI you wish to use. |
| [Analyze](#cmd-analyze) | Tab | Main | Run the analysis for a Project, Profile, Task or Scene against an Ai model. |
| [Apply to Task](#cmd-apply-to-task) | Command | Render Scene | Puts these action edits into the loaded configuration now, without closing -- the same as 'Ok' in the Edit Task dialog. |
| [Ask AI](#cmd-find-replace-ask-ai) | Command | Ui &gt; Find/Replace | (in the Find/Replace window) Type the question in plain words, and the AI model selected on the Analyze tab fills in the Find boxes for you. |
| [Bounds](#cmd-bounds) | Option | Ui | Outline every component and name it, the way the designer's tree names it. |
| [Cancel](#cmd-add-cancel) | Command | Render Header &gt; Add | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-cancel-2) | Command | Render Header &gt; Add | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-cancel) | Command | Main &gt; Add Profile &gt; Add Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-pick-cancel) | Command | Main &gt; Add Profile &gt; Add Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-pick-icon-not-listed-cancel) | Command | Main &gt; Add Profile &gt; Add Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-add-task-save-to-android-cancel) | Command | Main &gt; Add Profile &gt; Add Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-cancel) | Command | Main &gt; Add Profile | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-pick-cancel) | Command | Main &gt; Add Profile &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-pick-icon-not-listed-cancel) | Command | Main &gt; Add Profile &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-profile-save-to-android-cancel) | Command | Main &gt; Add Profile &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-project-cancel) | Command | Main &gt; Add Project | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-scene-cancel) | Command | Main &gt; Add Scene | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-scene-legacy-scene-cancel) | Command | Main &gt; Add Scene &gt; Legacy Scene | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-cancel) | Command | Main &gt; Add Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-pick-cancel) | Command | Main &gt; Add Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-pick-icon-not-listed-cancel) | Command | Main &gt; Add Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-add-task-save-to-android-cancel) | Command | Main &gt; Add Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel) | Command | AI API Key Entry | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-2) | Command | Action Condition | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-3) | Command | Delete Project | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-4) | Command | Delete Scene | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-5) | Command | If Variant | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-6) | Command | Main | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-7) | Command | Object Properties | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-8) | Command | Overwrite Confirmation | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-cancel-9) | Command | Scene Properties | Puts these properties back the way they were when this window opened, and drops the actions of any Task edited under the Event tab. |
| [Cancel](#cmd-change-prompt-cancel) | Command | Main &gt; Change Prompt | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-changes-since-cancel) | Command | Right Drawer &gt; Changes Since... | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-compare-files-cancel) | Command | Right Drawer &gt; Compare Files | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-cancel) | Command | Main &gt; Edit Profile &gt; Add Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-pick-cancel) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-pick-icon-not-listed-cancel) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-add-task-save-to-android-cancel) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-cancel) | Command | Main &gt; Edit Profile | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-delete-profile-cancel) | Command | Main &gt; Edit Profile &gt; Delete Profile | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-pick-cancel) | Command | Main &gt; Edit Profile &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-pick-icon-not-listed-cancel) | Command | Main &gt; Edit Profile &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-rename-cancel) | Command | Main &gt; Edit Profile &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-profile-save-to-android-cancel) | Command | Main &gt; Edit Profile &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-project-cancel) | Command | Main &gt; Edit Project | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-project-rename-cancel) | Command | Main &gt; Edit Project &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-project-save-to-android-cancel) | Command | Main &gt; Edit Project &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-scene-cancel) | Command | Main &gt; Edit Scene | Closes without saving, and puts this Scene back exactly as it was when this dialog opened -- including anything moved or resized in the Preview. |
| [Cancel](#cmd-edit-scene-rename-cancel) | Command | Main &gt; Edit Scene &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-scene-save-to-android-cancel) | Command | Main &gt; Edit Scene &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-cancel) | Command | Main &gt; Edit Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-delete-task-cancel) | Command | Main &gt; Edit Task &gt; Delete Task | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-pick-cancel) | Command | Main &gt; Edit Task &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-pick-icon-not-listed-cancel) | Command | Main &gt; Edit Task &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-rename-cancel) | Command | Main &gt; Edit Task &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-edit-task-save-to-android-cancel) | Command | Main &gt; Edit Task &gt; Save To Android | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-get-local-xml-file-cancel) | Command | Right Drawer &gt; Get Local XML File | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-health-check-cancel) | Command | Right Drawer &gt; Health Check | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-pick-cancel) | Command | Render Handlers &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-pick-cancel-2) | Command | Render Modifiers &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-pick-cancel-3) | Command | Render Scene &gt; Pick | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-pick-icon-not-listed-cancel) | Command | Render Scene &gt; Pick &gt; Icon not listed? | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-rename-cancel) | Command | Render Background &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-rename-cancel-2) | Command | Scene Properties &gt; Rename | Closes this dialog and keeps nothing it was holding. |
| [Cancel](#cmd-xref-live-cancel) | Command | Right Drawer &gt; Xref Live | Closes this dialog and keeps nothing it was holding. |
| [Cancel Entry](#cmd-cancel-entry) | Command | Get Xml From Android | Back out of the Android fetch process. |
| [Cancel Entry](#cmd-cancel-entry-2) | Command | Validate Or Filelist Xml | Back out of the Android fetch process. |
| [Change Prompt](#cmd-change-prompt) | Command | Main | Modify the prompt sent to the AI model. |
| [Changes Since...](#cmd-changes-since) | Command | Right Drawer | What has changed in your configuration since a moment you choose: today, this week, this month, everything kept, or a specific date. |
| [Check IDs](#cmd-add-profile-add-task-save-to-android-check-ids) | Option | Main &gt; Add Profile &gt; Add Task &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Check IDs](#cmd-add-profile-save-to-android-check-ids) | Option | Main &gt; Add Profile &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Check IDs](#cmd-add-task-save-to-android-check-ids) | Option | Main &gt; Add Task &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Check IDs](#cmd-edit-profile-add-task-save-to-android-check-ids) | Option | Main &gt; Edit Profile &gt; Add Task &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Check IDs](#cmd-edit-profile-save-to-android-check-ids) | Option | Main &gt; Edit Profile &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Check IDs](#cmd-edit-project-save-to-android-check-ids) | Option | Main &gt; Edit Project &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Check IDs](#cmd-edit-scene-save-to-android-check-ids) | Option | Main &gt; Edit Scene &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Check IDs](#cmd-edit-task-save-to-android-check-ids) | Option | Main &gt; Edit Task &gt; Save To Android | Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent. |
| [Clear](#cmd-clear) | Command | AI API Key Entry | Clear the Map/Diagram/Tree view data currently held and displayed. |
| [Clear](#cmd-clear-2) | Command | Right Drawer | Clear the Map/Diagram/Tree view data currently held and displayed. |
| [Clear](#cmd-clear-3) | Command | Ui | Clear the Map/Diagram/Tree view data currently held and displayed. |
| [Close](#cmd-add-profile-add-task-save-to-android-import-into-tasker-close) | Command | Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-add-profile-add-task-save-to-android-save-as-file-close) | Command | Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-add-profile-save-to-android-import-into-tasker-close) | Command | Main &gt; Add Profile &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-add-profile-save-to-android-save-as-file-close) | Command | Main &gt; Add Profile &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-add-task-save-to-android-import-into-tasker-close) | Command | Main &gt; Add Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-add-task-save-to-android-save-as-file-close) | Command | Main &gt; Add Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-close) | Command | Buttons | Closes this window without changing anything. |
| [Close](#cmd-close-2) | Command | Notification Log | Closes this window without changing anything. |
| [Close](#cmd-close-3) | Command | Render Handlers | Closes this window without changing anything. |
| [Close](#cmd-close-4) | Command | Render Modifiers | Closes this window without changing anything. |
| [Close](#cmd-close-5) | Command | Render Scene | Stop firing anything on this event. |
| [Close](#cmd-close-6) | Command | Render Tasks | Stop firing anything on this event. |
| [Close](#cmd-edit-history-close) | Command | Main &gt; Edit History | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-add-task-save-to-android-import-into-tasker-close) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-add-task-save-to-android-save-as-file-close) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-save-to-android-import-into-tasker-close) | Command | Main &gt; Edit Profile &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-profile-save-to-android-save-as-file-close) | Command | Main &gt; Edit Profile &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-project-save-to-android-import-into-tasker-close) | Command | Main &gt; Edit Project &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-project-save-to-android-save-as-file-close) | Command | Main &gt; Edit Project &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-save-to-android-import-into-tasker-close) | Command | Main &gt; Edit Scene &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-scene-save-to-android-save-as-file-close) | Command | Main &gt; Edit Scene &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-edit-task-run-on-android-close) | Command | Main &gt; Edit Task &gt; Run On Android | Closes this window without changing anything. |
| [Close](#cmd-edit-task-save-to-android-import-into-tasker-close) | Command | Main &gt; Edit Task &gt; Save To Android &gt; Import Into Tasker | Closes this window without changing anything. |
| [Close](#cmd-edit-task-save-to-android-save-as-file-close) | Command | Main &gt; Edit Task &gt; Save To Android &gt; Save As File | Closes this window without changing anything. |
| [Close](#cmd-find-replace-close) | Command | Ui &gt; Find/Replace | Closes this window without changing anything. |
| [Close](#cmd-list-helper-tasks-close) | Command | Get Xml From Android &gt; List Helper Tasks | Closes this window without changing anything. |
| [Close](#cmd-picker-close) | Command | Render Handlers &gt; Picker | Closes this window without changing anything. |
| [Close](#cmd-picker-close-2) | Command | Render Modifiers &gt; Picker | Closes this window without changing anything. |
| [Close](#cmd-put-helper-tasks-in-maptasker-project-close) | Command | Get Xml From Android &gt; Put Helper Tasks in 'MapTasker' Project | Closes this window without changing anything. |
| [Close](#cmd-refactor-close) | Command | Main &gt; Refactor | Closes this window without changing anything. |
| [Close](#cmd-restore-from-history-close) | Command | Right Drawer &gt; Restore From History | Closes this window without changing anything. |
| [Close](#cmd-run-on-android-close) | Command | Main &gt; Run On Android | Closes this window without changing anything. |
| [Close](#cmd-show-when-close) | Command | Render Handlers &gt; Show When | Closes this window without changing anything. |
| [Close](#cmd-show-when-close-2) | Command | Render Modifiers &gt; Show When | Closes this window without changing anything. |
| [Close](#cmd-variable-close) | Command | Render Handlers &gt; Variable | Closes this window without changing anything. |
| [Close](#cmd-variable-close-2) | Command | Render Modifiers &gt; Variable | Closes this window without changing anything. |
| [Close](#cmd-what-fires-when-close) | Command | Right Drawer &gt; What Fires When? | Closes this window without changing anything. |
| [Close Tabs On Exit](#cmd-close-tabs-on-exit) | Option | Right Drawer | When enabled, clicking 'Exit' also closes the main MapTasker window and any Map/Diagram windows/tabs it opened. |
| [Collapse](#cmd-collapse) | Command | Ui | Collapse every Project down to its title bar. |
| [Colors](#cmd-colors) | Tab | Main | select colors for various elements of the display. |
| [Compare Files](#cmd-compare-files) | Command | Right Drawer | Compare another XML file against the loaded one: what was added, removed, renamed and changed. |
| [Create Task](#cmd-create-task) | Command | Render Scene | Adds this Task to the loaded configuration and points this event at it, the same as 'Ok' in the Add Task dialog -- nothing is written to a file and nothing is sent to Android. |
| [Dark Mode](#cmd-dark-mode) | Option | Header | Switch the GUI between light and dark appearance. |
| [Debug](#cmd-debug) | Tab | Main | Display Runtime Settings option and turn on Debug mode. |
| [Delete](#cmd-delete) | Command | Render Scene | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-delete-2) | Command | Render Toolbar | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-delete-3) | Command | Render Toolbar | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-delete-4) | Command | Scene Properties | Remove the object being edited from the loaded XML. |
| [Delete](#cmd-edit-task-delete) | Command | Main &gt; Edit Task | Remove the object being edited from the loaded XML. |
| [Delete Profile](#cmd-edit-profile-delete-profile) | Command | Main &gt; Edit Profile | Deletes only this Profile. |
| [Delete Task](#cmd-edit-task-delete-task) | Command | Main &gt; Edit Task | Deletes this Task and every reference to it: it is removed from the Tasks of every Project that owns it, and from any Profile that runs it as its Entry/Exit Task. |
| [Detail Level](#cmd-detail-level) | Pulldown | Left Drawer | 0 = least detail, 5 = most detail. |
| [Diagram](#cmd-diagram) | Command | Right Drawer | Displays the Diagram view. |
| [Display Conditions](#cmd-display-conditions) | Option | Left Drawer | Enables the display of Profile Conditions (e.g. |
| [Display Directory](#cmd-display-directory) | Option | Left Drawer | Enables the display of the Project/Profile/Task/Scene Directory in the output. |
| [Display Help](#cmd-display-help) | Command | Right Drawer | Display this help text. |
| [Display Prettier Output](#cmd-display-prettier-output) | Option | Left Drawer | Enables the display of aligned text in the output. |
| [Display Tasker Preferences](#cmd-display-tasker-preferences) | Option | Left Drawer | Enables the display a breakdown of the Tasker system Preferences in the output. |
| [Display TaskerNet Info](#cmd-display-taskernet-info) | Option | Left Drawer | Enables the display of TaskerNet Descriptions in the output. |
| [Done](#cmd-done) | Command | Item Layout | Closes this dialog, keeping what was edited in it. |
| [Duplicate](#cmd-duplicate) | Command | Render Toolbar | Make a copy of the selected Scene element. |
| [Edit History](#cmd-edit-history) | Command | Main | List every change made to the loaded XML this session, newest first. |
| [Edit Profile](#cmd-edit-profile) | Command | Main | Modify the object currently selected in the pulldowns above. |
| [Edit Project](#cmd-edit-project) | Command | Main | Modify the object currently selected in the pulldowns above. |
| [Edit Scene](#cmd-edit-scene) | Command | Main | Modify the object currently selected in the pulldowns above. |
| [Edit Task](#cmd-edit-task) | Command | Main | Modify the object currently selected in the pulldowns above. |
| [Enabled](#cmd-edit-project-enabled) | Option | Main &gt; Edit Project | Disables the Project in the loaded backup, right now -- like Rename, this takes effect immediately rather than waiting for a save, and Cancel does not undo it. |
| [Exit](#cmd-exit) | Command | Right Drawer | Exit the program (quit). |
| [Expand](#cmd-expand) | Command | Ui | Expand every collapsed Project. |
| [Export](#cmd-export) | Command | Ui | (Map and Diagram only) Save what the view shows to a file in the current directory, as Markdown, JSON or PDF. |
| [Export Profile](#cmd-add-profile-export-profile) | Command | Main &gt; Add Profile | Saves this Profile, with all of its conditions and linked Tasks, as one standalone .prf.xml file -- the same format Tasker's own Profile export produces. |
| [Export Profile](#cmd-edit-profile-export-profile) | Command | Main &gt; Edit Profile | Saves this Profile as a standalone .prf.xml file on this computer. |
| [Export Project](#cmd-edit-project-export-project) | Command | Main &gt; Edit Project | Saves this Project, and everything in it -- every Profile and Task -- as one standalone file. |
| [Export Scene](#cmd-edit-scene-export-scene) | Command | Main &gt; Edit Scene | Saves this Scene, with all of its elements, as one standalone .scn.xml file -- the same format Tasker's own Scene export produces. |
| [Export Task](#cmd-add-profile-add-task-export-task) | Command | Main &gt; Add Profile &gt; Add Task | Exports the Task as XML to a file on your computer. |
| [Export Task](#cmd-add-task-export-task) | Command | Main &gt; Add Task | Exports the Task as XML to a file on your computer. |
| [Export Task](#cmd-edit-profile-add-task-export-task) | Command | Main &gt; Edit Profile &gt; Add Task | Exports the Task as XML to a file on your computer. |
| [Export Task](#cmd-edit-task-export-task) | Command | Main &gt; Edit Task | This will save the Task directly to your current drive. |
| [Extended](#cmd-extended) | Option | Main | Display an extended list of ALL available models. |
| [Find](#cmd-find-replace-find) | Tab | Ui &gt; Find/Replace | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Find](#cmd-find-replace-find-2) | Command | Ui &gt; Find/Replace | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Find/Replace](#cmd-find-replace) | Command | Ui | 'Find/Replace' asks the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything that names a given app or Scene. |
| [Fix Findings](#cmd-fix-findings) | Command | Right Drawer | Repair the Health Check findings that have an obvious fix: set a long Task's collision handling, give a blocking action a timeout, close an 'If' that is never closed, point a broken 'Goto' at a label that exists, delete a Task nothing runs. |
| [Font Optionmenu](#cmd-font-optionmenu) | Pulldown | Left Drawer | This is a list of all of the fonts available on your system, monospaced ones first and marked as such. |
| [Get Android Help](#cmd-get-android-help) | Command | Right Drawer | Display the help for fetching the XML file from your Android device. |
| [Get Local XML File](#cmd-get-local-xml-file) | Command | Right Drawer | Fetch XML from a local drive on this computer. |
| [Get XML from Android Device](#cmd-get-xml-from-android-device) | Command | Right Drawer | Fetch XML from an Android device. |
| [Health Check](#cmd-health-check) | Command | Right Drawer | Scan the loaded XML for broken references, unreferenced Tasks, Profiles and Scenes, naming problems, Task flow, variables, behaviour on the device, and secrets. |
| [Help](#cmd-help) | Command | Ui | The diagram is clickable: |
| [Hide Task Details Under Twisty](#cmd-hide-task-details-under-twisty) | Option | Left Drawer | When enabled, Task details are hidden under a twisty (expand/collapse) control in the output. |
| [Icon not listed?](#cmd-add-profile-add-task-pick-icon-not-listed) | Command | Main &gt; Add Profile &gt; Add Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-add-profile-pick-icon-not-listed) | Command | Main &gt; Add Profile &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-add-task-pick-icon-not-listed) | Command | Main &gt; Add Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-edit-profile-add-task-pick-icon-not-listed) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-edit-profile-pick-icon-not-listed) | Command | Main &gt; Edit Profile &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-edit-task-pick-icon-not-listed) | Command | Main &gt; Edit Task &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Icon not listed?](#cmd-pick-icon-not-listed) | Command | Render Scene &gt; Pick | Fetch every installed application's own icon from your Android device. |
| [Import Into Tasker](#cmd-add-profile-add-task-save-to-android-import-into-tasker) | Command | Main &gt; Add Profile &gt; Add Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Import Into Tasker](#cmd-add-profile-save-to-android-import-into-tasker) | Command | Main &gt; Add Profile &gt; Save To Android | This copies the Profile to the device and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-add-task-save-to-android-import-into-tasker) | Command | Main &gt; Add Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Import Into Tasker](#cmd-edit-profile-add-task-save-to-android-import-into-tasker) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Import Into Tasker](#cmd-edit-profile-save-to-android-import-into-tasker) | Command | Main &gt; Edit Profile &gt; Save To Android | This copies the Profile to the device and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-edit-project-save-to-android-import-into-tasker) | Command | Main &gt; Edit Project &gt; Save To Android | This copies the Project -- and every Profile and Task in it -- to the device and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-edit-scene-save-to-android-import-into-tasker) | Command | Main &gt; Edit Scene &gt; Save To Android | This sends the Scene -- and every Task its elements fire -- to the Android device under its own name, into /Tasker/scenes, and opens Android's 'Open with...' chooser for it. |
| [Import Into Tasker](#cmd-edit-task-save-to-android-import-into-tasker) | Command | Main &gt; Edit Task &gt; Save To Android | This puts the Task straight into Tasker's live configuration on the Android device. |
| [Indent Option](#cmd-indent-option) | Pulldown | Left Drawer | Set the indentation amount for If/Then/Else blocks. |
| [Just Display Everything!](#cmd-just-display-everything) | Option | Left Drawer | Enables the display of Conditions, TaskerNet Info, Preferences, the Directory, and Prettier Output. |
| [Landscape](#cmd-landscape) | Option | Render Header | This Scene has no landscape layout of its own (its size is -1). |
| [Landscape](#cmd-landscape-2) | Option | Ui | Turn the screen on its side and let the layout re-flow into it. |
| [Legacy Scene](#cmd-add-scene-legacy-scene) | Command | Main &gt; Add Scene | A Legacy Scene has a pixel canvas and a list of UI elements. |
| [List Helper Tasks](#cmd-list-helper-tasks) | Command | Get Xml From Android | Lists the 'MapTasker ...' Tasks this program has installed on the Android device, and says which are left over from an earlier version. |
| [List Unnamed Items](#cmd-list-unnamed-items) | Option | Main | Select this to include Profiles and Tasks that do not have a name in the list. |
| [List XML Files](#cmd-list-xml-files) | Command | Get Xml From Android | List the XML files found on the Android device so you can select one rather than typing its location. |
| [Map](#cmd-map) | Command | Right Drawer | Displays the Map view. |
| [Narrow to Project](#cmd-find-replace-narrow-to-project) | Pulldown | Ui &gt; Find/Replace | Hidden when a single Project/Profile/Task/Scene is selected, because the scope has already done the narrowing and this can then only mislead. |
| [Narrow to Project](#cmd-narrow-to-project) | Pulldown | Init | Hidden under a scope, for the reason the Find tab's own gives. |
| [Notify Timeout Optionmenu](#cmd-notify-timeout-optionmenu) | Pulldown | Left Drawer | How long a pop-up message stays on screen before it disappears. |
| [Now](#cmd-what-fires-when-now) | Command | Right Drawer &gt; What Fires When? | Set the date and time back to this moment. |
| [Ok](#cmd-add-profile-add-task-ok) | Command | Main &gt; Add Profile &gt; Add Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-profile-ok) | Command | Main &gt; Add Profile | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-project-ok) | Command | Main &gt; Add Project | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-scene-legacy-scene-ok) | Command | Main &gt; Add Scene &gt; Legacy Scene | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-add-task-ok) | Command | Main &gt; Add Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-profile-add-task-ok) | Command | Main &gt; Edit Profile &gt; Add Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-profile-ok) | Command | Main &gt; Edit Profile | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-scene-ok) | Command | Main &gt; Edit Scene | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-edit-task-ok) | Command | Main &gt; Edit Task | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-get-local-xml-file-ok) | Command | Right Drawer &gt; Get Local XML File | Keeps what this dialog holds and closes it. |
| [OK](#cmd-ok) | Command | AI API Key Entry | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-ok-2) | Command | Action Condition | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-ok-3) | Command | Object Properties | Keeps what this dialog holds and closes it. |
| [Ok](#cmd-ok-4) | Command | Scene Properties | Keeps everything, including the actions of any Task edited under the Event tab. |
| [Only the matching text](#cmd-only-the-matching-text) | Option | Init | Off means the argument is SET to the new value; on means only the matched text inside it changes. |
| [Open View In New Window](#cmd-open-view-in-new-window) | Option | Right Drawer | When enabled, each Map/Diagram request opens in its own new window/tab, so you can keep earlier ones up alongside it to compare. |
| [Palette](#cmd-palette) | Command | Render Handlers | Pick one of Material's own colour roles. |
| [Palette](#cmd-palette-2) | Command | Render Modifiers | Pick one of Material's own colour roles. |
| [Pick](#cmd-add-profile-add-task-pick) | Command | Main &gt; Add Profile &gt; Add Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-add-profile-pick) | Command | Main &gt; Add Profile | Fill all three fields in from the loaded configuration. |
| [Pick](#cmd-add-task-pick) | Command | Main &gt; Add Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-edit-profile-add-task-pick) | Command | Main &gt; Edit Profile &gt; Add Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-edit-profile-pick) | Command | Main &gt; Edit Profile | Fill all three fields in from the loaded configuration. |
| [Pick](#cmd-edit-task-pick) | Command | Main &gt; Edit Task | Choose from the Applications named in the loaded configuration. |
| [Pick](#cmd-pick) | Command | Render Handlers | Pick a Material icon. |
| [Pick](#cmd-pick-2) | Command | Render Modifiers | Pick a Material icon. |
| [Pick](#cmd-pick-3) | Command | Render Scene | Choose from the Applications named in the loaded configuration. |
| [Pick a Task](#cmd-add-profile-add-task-pick-a-task) | Pulldown | Main &gt; Add Profile &gt; Add Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-add-task-pick-a-task) | Pulldown | Main &gt; Add Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-edit-profile-add-task-pick-a-task) | Pulldown | Main &gt; Edit Profile &gt; Add Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-edit-task-pick-a-task) | Pulldown | Main &gt; Edit Task | Pick a Task which will be called by this action. |
| [Pick a Task](#cmd-pick-a-task) | Pulldown | Render Scene | Pick a Task which will be called by this action. |
| [Picker](#cmd-picker) | Command | Render Handlers | Pick from the Scene's environment and global variables. |
| [Picker](#cmd-picker-2) | Command | Render Modifiers | Pick from the Scene's environment and global variables. |
| [Preview](#cmd-add-scene-legacy-scene-preview) | Command | Main &gt; Add Scene &gt; Legacy Scene | Display the Scene being edited as it will appear. |
| [Preview](#cmd-edit-scene-preview) | Command | Main &gt; Edit Scene | Display the Scene being edited as it will appear. |
| [Preview](#cmd-preview) | Command | Init | Display the Scene being edited as it will appear. |
| [Preview](#cmd-refactor-preview) | Command | Main &gt; Refactor | Display the Scene being edited as it will appear. |
| [Profile](#cmd-profile) | Pulldown | Main | Select a specific Profile to target for display or editing. |
| [Profiles Per Line](#cmd-profiles-per-line) | Pulldown | Ui | (Diagram only) The number of Profiles drawn side-by-side on a single line. |
| [Project](#cmd-project) | Pulldown | Main | Select a specific Project to target for display or editing. |
| [Put Helper Tasks in 'MapTasker' Project](#cmd-put-helper-tasks-in-maptasker-project) | Command | Get Xml From Android | Puts every helper Task this version of MapTasker uses into one Project file, 'MapTasker.prj.xml', in /Tasker/projects on the device. |
| [Rebuild](#cmd-rebuild) | Command | Ui | (Diagram only) Offered when the Diagram was drawn for a different selection than the one chosen now; it draws the Diagram again for the current one. |
| [Redo](#cmd-redo) | Command | Main | Reapply the change most recently backed out by 'Undo'. |
| [Refactor](#cmd-refactor) | Command | Main | The structural changes that Add, Edit and Delete cannot make: pull a run of a Task's actions out into a Task of their own, fold a Perform Task back into its caller, move a Task or Profile to another Project, or duplicate any object. |
| [Rename](#cmd-edit-profile-rename) | Command | Main &gt; Edit Profile | Prompts for a new name and applies just that to the loaded backup, right now. |
| [Rename](#cmd-edit-profile-rename-rename) | Command | Main &gt; Edit Profile &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-edit-project-rename) | Command | Main &gt; Edit Project | Prompts for a new name and applies it to the loaded backup, right now. |
| [Rename](#cmd-edit-project-rename-rename) | Command | Main &gt; Edit Project &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-edit-scene-rename) | Command | Main &gt; Edit Scene | Prompts for a new name and applies it to the loaded backup, right now -- renaming the Scene everywhere, including in the Scene list of every Project that holds it. |
| [Rename](#cmd-edit-scene-rename-rename) | Command | Main &gt; Edit Scene &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-edit-task-rename) | Command | Main &gt; Edit Task | Prompts for a new name and applies just that to the loaded backup, right now. |
| [Rename](#cmd-edit-task-rename-rename) | Command | Main &gt; Edit Task &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-rename) | Command | Render Background | Tasks address this element by name (Element Text, Element Position, ... |
| [Rename](#cmd-rename-2) | Command | Scene Properties | Tasks address this element by name (Element Text, Element Position, ... |
| [Rename](#cmd-rename-rename) | Command | Render Background &gt; Rename | Give the object being edited a new name. |
| [Rename](#cmd-rename-rename-2) | Command | Scene Properties &gt; Rename | Give the object being edited a new name. |
| [Replace](#cmd-find-replace-replace) | Tab | Ui &gt; Find/Replace | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Replace](#cmd-replace) | Command | Init | (Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. |
| [Report Issue](#cmd-report-issue) | Command | Right Drawer | Report any issues and/or suggestions to the developer. |
| [Reset](#cmd-reset) | Command | Ui | Back to the whole diagram: no zoom, nothing folded, nothing filtered. |
| [Reset Options](#cmd-reset-options) | Command | Right Drawer | Reset all of the options to their default values, including colors, font used, and other settings. |
| [Reset to Default Colors](#cmd-reset-to-default-colors) | Command | Main | Restore every color to its default value. |
| [Restore](#cmd-restore) | Command | Right Drawer | Restore the settings from a previously saved session. |
| [Restore From History](#cmd-restore-from-history) | Command | Right Drawer | Bring back a Task, Profile or Scene that has been deleted, or put one back as it was before it was edited -- from any configuration kept in the history that 'Changes Since...' reads. |
| [Run Analysis](#cmd-run-analysis) | Command | Main | Submit the selected Project/Profile/Task and prompt to the selected model. |
| [Run On Android](#cmd-edit-task-run-on-android) | Command | Main &gt; Edit Task | Runs this Task on your Android device and shows what it returned, or the error. |
| [Run On Android](#cmd-run-on-android) | Command | Main | Run the selected Task on your Android device and see what it returned. |
| [Same as Value](#cmd-same-as-value) | Option | Object Properties | Under 'Exported Value' if you disable the 'Same as Value' option, you can customize what value gets exported when you share the variable with other users. |
| [Save](#cmd-save) | Command | Right Drawer | Save these settings for later use. |
| [Save As File](#cmd-add-profile-add-task-save-to-android-save-as-file) | Command | Main &gt; Add Profile &gt; Add Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save As File](#cmd-add-profile-save-to-android-save-as-file) | Command | Main &gt; Add Profile &gt; Save To Android | This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles. |
| [Save As File](#cmd-add-task-save-to-android-save-as-file) | Command | Main &gt; Add Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save As File](#cmd-edit-profile-add-task-save-to-android-save-as-file) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save As File](#cmd-edit-profile-save-to-android-save-as-file) | Command | Main &gt; Edit Profile &gt; Save To Android | This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles. |
| [Save As File](#cmd-edit-project-save-to-android-save-as-file) | Command | Main &gt; Edit Project &gt; Save To Android | This will write the Project, and everything in it, as a standalone file onto the Android device, under /Tasker/projects. |
| [Save As File](#cmd-edit-scene-save-to-android-save-as-file) | Command | Main &gt; Edit Scene &gt; Save To Android | This will write the Scene as a standalone file onto the Android device, under /Tasker/scenes. |
| [Save As File](#cmd-edit-task-save-to-android-save-as-file) | Command | Main &gt; Edit Task &gt; Save To Android | This will write the Task as a standalone file onto the Android device, under /Tasker/tasks. |
| [Save Results](#cmd-find-replace-save-results) | Command | Ui &gt; Find/Replace | Save the 'Find/Replace' results to a text file. |
| [Save To Android](#cmd-add-profile-add-task-save-to-android) | Command | Main &gt; Add Profile &gt; Add Task | Write the object back to your Android device -- 'Save As File' puts it on the device as a file, and 'Import Into Tasker' hands it to Tasker itself (a Task goes straight in; a Profile, Project or Scene opens Tasker's import screen). |
| [Save To Android](#cmd-add-profile-save-to-android) | Command | Main &gt; Add Profile | This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-add-task-save-to-android) | Command | Main &gt; Add Task | Write the object back to your Android device -- 'Save As File' puts it on the device as a file, and 'Import Into Tasker' hands it to Tasker itself (a Task goes straight in; a Profile, Project or Scene opens Tasker's import screen). |
| [Save To Android](#cmd-edit-profile-add-task-save-to-android) | Command | Main &gt; Edit Profile &gt; Add Task | Write the object back to your Android device -- 'Save As File' puts it on the device as a file, and 'Import Into Tasker' hands it to Tasker itself (a Task goes straight in; a Profile, Project or Scene opens Tasker's import screen). |
| [Save To Android](#cmd-edit-profile-save-to-android) | Command | Main &gt; Edit Profile | This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-edit-project-save-to-android) | Command | Main &gt; Edit Project | This will write the Project, and everything in it -- every Profile and Task -- as a standalone file onto your Android device, under /Tasker/projects -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-edit-scene-save-to-android) | Command | Main &gt; Edit Scene | This will write the Scene as a standalone file onto your Android device, under /Tasker/scenes -- it does not import it into Tasker's live configuration. |
| [Save To Android](#cmd-edit-task-save-to-android) | Command | Main &gt; Edit Task | This opens a choice of two: write the Task as a standalone file onto your Android device under /Tasker/tasks, or import it straight into Tasker's live configuration. |
| [Save To Current File](#cmd-add-profile-add-task-save-to-current-file) | Command | Main &gt; Add Profile &gt; Add Task | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-add-profile-save-to-current-file) | Command | Main &gt; Add Profile | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Profile added to its Project, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-add-task-save-to-current-file) | Command | Main &gt; Add Task | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-edit-profile-add-task-save-to-current-file) | Command | Main &gt; Edit Profile &gt; Add Task | Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. |
| [Save To Current File](#cmd-edit-profile-save-to-current-file) | Command | Main &gt; Edit Profile | Saves the entire backup -- every Project, Profile and Task in it, not just this Profile -- with this dialog's edits applied, the same ones 'Ok' would keep. |
| [Save To Current File](#cmd-edit-project-save-to-current-file) | Command | Main &gt; Edit Project | Saves the entire backup -- every Project, Profile and Task in it, not just this Project -- including every edit made anywhere in this session. |
| [Save To Current File](#cmd-edit-scene-save-to-current-file) | Command | Main &gt; Edit Scene | Saves the entire backup -- every Project, Profile, Task and Scene in it, not just this Scene -- including every edit made anywhere in this session. |
| [Save To Current File](#cmd-edit-task-save-to-current-file) | Command | Main &gt; Edit Task | Saves the entire backup -- every Project, Profile and Task in it, not just this Task -- with this dialog's edits applied, the same ones 'Ok' would keep. |
| [Save To Current File](#cmd-restore-from-history-save-to-current-file) | Command | Right Drawer &gt; Restore From History | Write the entire configuration to a new, timestamped file beside the loaded one. |
| [Save To Current File](#cmd-save-to-current-file) | Command | Buttons | Write the entire configuration to a new, timestamped file beside the loaded one. |
| [Scene](#cmd-scene) | Pulldown | Main | Select a specific Scene to target for display or editing. |
| [Screen](#cmd-screen) | Pulldown | Ui | A Version 2 Scene has no size of its own -- it lays itself out inside whatever screen it is shown on, so there is nothing in the backup file to draw it at. |
| [Search](#cmd-search) | Command | Ui | The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data. |
| [Show When](#cmd-show-when) | Command | Render Handlers | Pick from the Scene's environment and global variables. |
| [Show When](#cmd-show-when-2) | Command | Render Modifiers | Pick from the Scene's environment and global variables. |
| [Snap](#cmd-snap) | Pulldown | Render Header | Round dragged positions and sizes to this many pixels. |
| [Snap](#cmd-snap-2) | Pulldown | Ui | Round dragged positions and sizes to this many pixels. |
| [Specific Name](#cmd-specific-name) | Tab | Main | enter a single, specific named item to display... |
| [State](#cmd-state) | Pulldown | Render Handlers | Dynamic and Select Variable are worked out when the Scene is shown. |
| [State](#cmd-state-2) | Pulldown | Render Modifiers | Dynamic and Select Variable are worked out when the Scene is shown. |
| [Stop Event](#cmd-stop-event) | Option | Render Scene | Any key handled by the scene is not passed on to the system -- how a Scene keeps the back key from closing it. |
| [Task](#cmd-task) | Pulldown | Main | Select a specific Task to target for display or editing. |
| [Task Flow](#cmd-task-flow) | Command | Right Drawer | Read every Task's control flow -- its If/Else/End If, For/End For, Goto and Stop -- and report what does not hold together: a block that is never closed, a Goto aimed at a label no action carries, and actions nothing can ever reach. |
| [Text density](#cmd-text-density) | Pulldown | Ui | A Scene's element positions are stored in device pixels, but its text sizes are stored in Android's sp units. |
| [Toggle Wrap](#cmd-toggle-wrap) | Command | Ui | Turn line wrapping on or off in the displayed output. |
| [Tree](#cmd-tree) | Command | Right Drawer | Displays the Tree view. |
| [Undo](#cmd-undo) | Command | Main | Take back the last change made to the loaded XML -- an edit, an Add, a Delete or a Rename, in any of the Edit panels. |
| [Undo](#cmd-undo-2) | Command | Render Header | Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. |
| [Undo](#cmd-undo-3) | Command | Render Header | Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. |
| [Upgrade to Latest Version](#cmd-upgrade-to-latest-version) | Command | Upgrade If Newer | Clicking this will launch 'pip install --upgrade maptasker' in the background, and then relaunch MapTasker. |
| [Use](#cmd-add-profile-add-task-pick-use) | Command | Main &gt; Add Profile &gt; Add Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-add-profile-pick-use) | Command | Main &gt; Add Profile &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-add-task-pick-use) | Command | Main &gt; Add Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-edit-profile-add-task-pick-use) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-edit-profile-pick-use) | Command | Main &gt; Edit Profile &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-edit-task-pick-use) | Command | Main &gt; Edit Task &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use](#cmd-pick-use) | Command | Render Scene &gt; Pick | Uses what is entered or selected above, and closes the picker. |
| [Use Selected](#cmd-add-profile-add-task-pick-use-selected) | Command | Main &gt; Add Profile &gt; Add Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-add-task-pick-use-selected) | Command | Main &gt; Add Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-edit-profile-add-task-pick-use-selected) | Command | Main &gt; Edit Profile &gt; Add Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-edit-task-pick-use-selected) | Command | Main &gt; Edit Task &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Use Selected](#cmd-pick-use-selected) | Command | Render Scene &gt; Pick | Uses what is selected in the list above, and closes the picker. |
| [Variable](#cmd-variable) | Command | Render Handlers | Pick from the Scene's environment and global variables. |
| [Variable](#cmd-variable-2) | Command | Render Modifiers | Pick from the Scene's environment and global variables. |
| [Variable Xref](#cmd-variable-xref) | Command | Right Drawer | Trace every %variable in the loaded XML: where each one is set, where it is read, which are read but never set, which are set but never read, and which near-identical names (%MyVar against %Myvar) are likely typos. |
| [Verify](#cmd-add-profile-add-task-save-to-android-verify) | Option | Main &gt; Add Profile &gt; Add Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-add-profile-save-to-android-verify) | Option | Main &gt; Add Profile &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-add-task-save-to-android-verify) | Option | Main &gt; Add Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-profile-add-task-save-to-android-verify) | Option | Main &gt; Edit Profile &gt; Add Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-profile-save-to-android-verify) | Option | Main &gt; Edit Profile &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-project-save-to-android-verify) | Option | Main &gt; Edit Project &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-scene-save-to-android-verify) | Option | Main &gt; Edit Scene &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Verify](#cmd-edit-task-save-to-android-verify) | Option | Main &gt; Edit Task &gt; Save To Android | Reads the XML back before it is sent, and refuses the save if anything changed on the way through. |
| [Viewlimit Optionmenu](#cmd-viewlimit-optionmenu) | Pulldown | Left Drawer | Select the maximum number of items to display in the view to be allowed. |
| [What Fires When?](#cmd-what-fires-when) | Command | Right Drawer | Pick a moment -- a date and time, the Wi-Fi network the device is on, the app in front and the battery level -- and see which Profiles it makes active, the order their Tasks start in, and where they collide. |
| [What's New?](#cmd-what-s-new) | Command | Upgrade If Newer | Display the changes in the new version. |
| [Xref Live](#cmd-xref-live) | Command | Right Drawer | The Variable Xref, plus what each global variable holds right now on the Android device, read through Tasker's HTTP API. |
| [Zoom In](#cmd-zoom-in) | Command | Ui | Zoom in. |
| [Zoom Out](#cmd-zoom-out) | Command | Ui | Zoom out. |

## AI API Key Entry

_Initialize the NiceGUI dialog container._

<a id="cmd-ok"></a>
### OK

**Path:** AI API Key Entry &gt; OK  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins2.py` line 39</sub>

<a id="cmd-cancel"></a>
### Cancel

**Path:** AI API Key Entry &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins2.py` line 50</sub>

<a id="cmd-clear"></a>
### Clear

**Path:** AI API Key Entry &gt; Clear  
**Kind:** Command

Clear the Map/Diagram/Tree view data currently held and displayed.

<sub>Source: `guiwins2.py` line 87</sub>

## Action Condition

_Prompts for a per-action If condition (Target/Operator/Value) when the action's "If" checkbox is checked -- see _render_action_condition_checkbox._

<a id="cmd-cancel-2"></a>
### Cancel

**Path:** Action Condition &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 1016</sub>

<a id="cmd-ok-2"></a>
### Ok

**Path:** Action Condition &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins_taskedit.py` line 1020</sub>

## Buttons

_The row along the bottom, with the tooltip each button needs._

<a id="cmd-save-to-current-file"></a>
### Save To Current File

**Path:** Buttons &gt; Save To Current File  
**Kind:** Command

Write the entire configuration to a new, timestamped file beside the loaded one.

<sub>Source: `guiwins_fix.py` line 519</sub>

<a id="cmd-close"></a>
### Close

**Path:** Buttons &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_fix.py` line 540</sub>

## Delete Project

_Confirms deletion of a Project, offering a choice for what happens to the Profiles/Tasks it owns: moved into "Base" (Keep Contents) or deleted along with it (Delete Contents) -- see projedit.delete_project._

<a id="cmd-cancel-3"></a>
### Cancel

**Path:** Delete Project &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2179</sub>

## Delete Scene

_Confirms deletion of a Scene._

<a id="cmd-cancel-4"></a>
### Cancel

**Path:** Delete Scene &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1630</sub>

## Get Xml From Android

_Gets Android details from user inside the reactive right drawer container slot._

<a id="cmd-list-xml-files"></a>
### List XML Files

**Path:** Get Xml From Android &gt; List XML Files  
**Kind:** Command

List the XML files found on the Android device so you can select one rather than typing its location.

<sub>Source: `userintr_android.py` line 358</sub>

<a id="cmd-list-helper-tasks"></a>
### List Helper Tasks

**Path:** Get Xml From Android &gt; List Helper Tasks  
**Kind:** Command

Lists the 'MapTasker ...' Tasks this program has installed on the Android device, and says which are left over from an earlier version.

Each one is installed under a versioned name and never replaced -- Tasker's import adds a second Task rather than replacing the first -- so old ones stay behind in your Task list. They do no harm; they are clutter.

Delete the ones it names from Tasker's own Tasks tab. Nothing here can do it for you: Tasker's HTTP API has no way to delete a Task.

Opens **Helper Tasks**, whose own commands are listed beneath this one.

<sub>Source: `userintr_android.py` line 374</sub>

<a id="cmd-list-helper-tasks-close"></a>
#### Close

**Path:** Get Xml From Android &gt; List Helper Tasks &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1903</sub>

<a id="cmd-put-helper-tasks-in-maptasker-project"></a>
### Put Helper Tasks in 'MapTasker' Project

**Path:** Get Xml From Android &gt; Put Helper Tasks in 'MapTasker' Project  
**Kind:** Command

Puts every helper Task this version of MapTasker uses into one Project file, 'MapTasker.prj.xml', in /Tasker/projects on the device. Import it in Tasker: long-press the Projects tab bar and choose Import Project.

Once they are in that Project, deleting the 'MapTasker' Project in Tasker removes all of them at once. MapTasker puts back any it needs the next time it is used.

Tasker refuses the whole Project if it already has any of these Tasks, so any helper Tasks already on the device are listed first for you to delete manu.

Opens **Helpers In The Way**, whose own commands are listed beneath this one.

<sub>Source: `userintr_android.py` line 398</sub>

<a id="cmd-put-helper-tasks-in-maptasker-project-close"></a>
#### Close

**Path:** Get Xml From Android &gt; Put Helper Tasks in 'MapTasker' Project &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 1945</sub>

<a id="cmd-cancel-entry"></a>
### Cancel Entry

**Path:** Get Xml From Android &gt; Cancel Entry  
**Kind:** Command

Back out of the Android fetch process.

<sub>Source: `userintr_android.py` line 423</sub>

## Header

_The title bar: the app's name, the MapTasker logo and the Dark Mode switch._

<a id="cmd-dark-mode"></a>
### Dark Mode

**Path:** Header &gt; Dark Mode  
**Kind:** Option

Switch the GUI between light and dark appearance.

<sub>Source: `guiwins.py` line 2548</sub>

## If Variant

_Prompts for how much of an If block to insert when the user picks the "If" action in an Add/Edit Task action picker: just the "If", "If" plus a matching "End If", or a full "If"/"Else"/"End If" skeleton -- see taskedit.IF_BLOCK_VARIANTS/add_if_block_to_task._

<a id="cmd-cancel-5"></a>
### Cancel

**Path:** If Variant &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 1135</sub>

## Init

<a id="cmd-preview"></a>
### Preview

**Path:** Init &gt; Preview  
**Kind:** Command

Display the Scene being edited as it will appear.

<sub>Source: `guiwins_search.py` line 1210</sub>

<a id="cmd-replace"></a>
### Replace

**Path:** Init &gt; Replace  
**Kind:** Command

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins_search.py` line 1211</sub>

<a id="cmd-narrow-to-project"></a>
### Narrow to Project

**Path:** Init &gt; Narrow to Project  
**Kind:** Pulldown

_There is no tooltip on this one; this is the note written beside it in the source._

Hidden under a scope, for the reason the Find tab's own gives.

<sub>Source: `guiwins_search.py` line 1256</sub>

<a id="cmd-only-the-matching-text"></a>
### Only the matching text

**Path:** Init &gt; Only the matching text  
**Kind:** Option

_There is no tooltip on this one; this is the note written beside it in the source._

Off means the argument is SET to the new value; on means only the matched text inside it changes. Both are things people mean by "replace", and which one they meant cannot be guessed from the two boxes above -- so it is asked, in the one place where the answer is visible while the values are being typed.

<sub>Source: `guiwins_search.py` line 1313</sub>

<a id="cmd-add-it-where-missing"></a>
### Add it where missing

**Path:** Init &gt; Add it where missing  
**Kind:** Option

_There is no tooltip on this one; this is the note written beside it in the source._

Tasker leaves out an argument nobody ever set, so this is what makes "give every Flash a Timeout" reach the Flashes that have none. Off by default: adding an argument to a hundred actions is a bigger thing than editing the ones that already have it, and the preview marks every row that is an addition rather than a change.

<sub>Source: `guiwins_search.py` line 1319</sub>

## Item Layout

_Edit the Scene inside a List or a Spinner, in a designer of its own._

<a id="cmd-done"></a>
### Done

**Path:** Item Layout &gt; Done  
**Kind:** Command

Closes this dialog, keeping what was edited in it.

<sub>Source: `guiwins_designer_legacy.py` line 1341</sub>

## Left Drawer

_The left drawer: every option that decides what the output shows and how._

<a id="cmd-detail-level"></a>
### Detail Level

**Path:** Left Drawer &gt; Detail Level  
**Kind:** Pulldown

0 = least detail, 5 = most detail.

<sub>Source: `guiwins.py` line 2568</sub>

<a id="cmd-just-display-everything"></a>
### Just Display Everything!

**Path:** Left Drawer &gt; Just Display Everything!  
**Kind:** Option

Enables the display of Conditions, TaskerNet Info, Preferences, the Directory, and Prettier Output.

<sub>Source: `guiwins.py` line 2580</sub>

<a id="cmd-display-conditions"></a>
### Display Conditions

**Path:** Left Drawer &gt; Display Conditions  
**Kind:** Option

Enables the display of Profile Conditions (e.g. State, Event, etc.) details in the output.

<sub>Source: `guiwins.py` line 2589</sub>

<a id="cmd-display-taskernet-info"></a>
### Display TaskerNet Info

**Path:** Left Drawer &gt; Display TaskerNet Info  
**Kind:** Option

Enables the display of TaskerNet Descriptions in the output.

<sub>Source: `guiwins.py` line 2598</sub>

<a id="cmd-display-tasker-preferences"></a>
### Display Tasker Preferences

**Path:** Left Drawer &gt; Display Tasker Preferences  
**Kind:** Option

Enables the display a breakdown of the Tasker system Preferences in the output.

<sub>Source: `guiwins.py` line 2603</sub>

<a id="cmd-hide-task-details-under-twisty"></a>
### Hide Task Details Under Twisty

**Path:** Left Drawer &gt; Hide Task Details Under Twisty  
**Kind:** Option

When enabled, Task details are hidden under a twisty (expand/collapse) control in the output.

<sub>Source: `guiwins.py` line 2608</sub>

<a id="cmd-display-directory"></a>
### Display Directory

**Path:** Left Drawer &gt; Display Directory  
**Kind:** Option

Enables the display of the Project/Profile/Task/Scene Directory in the output.

<sub>Source: `guiwins.py` line 2617</sub>

<a id="cmd-display-prettier-output"></a>
### Display Prettier Output

**Path:** Left Drawer &gt; Display Prettier Output  
**Kind:** Option

Enables the display of aligned text in the output.

<sub>Source: `guiwins.py` line 2622</sub>

<a id="cmd-indent-option"></a>
### Indent Option

**Path:** Left Drawer &gt; Indent Option  
**Kind:** Pulldown

Set the indentation amount for If/Then/Else blocks.

The default is '4'.

This affects how the output is formatted in the Map and Diagram views.

<sub>Source: `guiwins.py` line 3513</sub>

<a id="cmd-viewlimit-optionmenu"></a>
### Viewlimit Optionmenu

**Path:** Left Drawer &gt; Viewlimit Optionmenu  
**Kind:** Pulldown

Select the maximum number of items to display in the view to be allowed.

Anything over this amount will stop the generation of the view as a means to throttle the program.

Note: This is only for the 'Map' and 'Diagram' views, not the tree view.

<sub>Source: `guiwins.py` line 3564</sub>

<a id="cmd-notify-timeout-optionmenu"></a>
### Notify Timeout Optionmenu

**Path:** Left Drawer &gt; Notify Timeout Optionmenu  
**Kind:** Pulldown

How long a pop-up message stays on screen before it disappears.

'Until dismissed' keeps every message up until you close it, which is useful when a message scrolls past before you can read it.

A few messages set their own longer duration because they list things you have to read -- the Tasks affected by deleting or renaming a Scene element, for instance. Those keep their own timing whatever is chosen here.

<sub>Source: `guiwins.py` line 3605</sub>

<a id="cmd-font-optionmenu"></a>
### Font Optionmenu

**Path:** Left Drawer &gt; Font Optionmenu  
**Kind:** Pulldown

This is a list of all of the fonts available on your system, monospaced ones first and marked as such.

The font selected will be used in all output.

'Courier' or 'Courier New' is highly recommended for Diagrams to ensure proper connector alignment. A font that is not monospaced will not hold the Diagram's connectors or the output's indentation in line.

<sub>Source: `guiwins.py` line 3752</sub>

## Main

_The middle of the window: the four tabs, the view underneath them, and the colour picker._

<a id="cmd-ai-model"></a>
### AI Model

**Path:** Main &gt; AI Model  
**Kind:** Pulldown

Select the model belonging to the AI you wish to use.

<sub>Source: `guiutils.py` line 178</sub>

<a id="cmd-refactor"></a>
### Refactor

**Path:** Main &gt; Refactor  
**Kind:** Command

The structural changes that Add, Edit and Delete cannot make: pull a run of a Task's actions out into a Task of their own, fold a Perform Task back into its caller, move a Task or Profile to another Project, or duplicate any object.

Nothing is changed until you press Preview and then Apply, and the preview says what will happen step by step -- or why it will not.

The whole of a refactor is one press of Undo afterwards.

Opens **Refactor**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 402</sub>

<a id="cmd-refactor-preview"></a>
#### Preview

**Path:** Main &gt; Refactor &gt; Preview  
**Kind:** Command

Display the Scene being edited as it will appear.

<sub>Source: `guiwins_refactor.py` line 307</sub>

<a id="cmd-refactor-close"></a>
#### Close

**Path:** Main &gt; Refactor &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_refactor.py` line 340</sub>

<a id="cmd-undo"></a>
### Undo

**Path:** Main &gt; Undo  
**Kind:** Command

Take back the last change made to the loaded XML -- an edit, an Add, a Delete or a Rename, in any of the Edit panels.

This changes what is loaded, not any file: nothing on disk or on the Android device is touched.

<sub>Source: `guiwins.py` line 433</sub>

<a id="cmd-redo"></a>
### Redo

**Path:** Main &gt; Redo  
**Kind:** Command

Reapply the change most recently backed out by 'Undo'.

<sub>Source: `guiwins.py` line 438</sub>

<a id="cmd-edit-history"></a>
### Edit History

**Path:** Main &gt; Edit History  
**Kind:** Command

List every change made to the loaded XML this session, newest first.

Opens **Edit History**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 456</sub>

<a id="cmd-edit-history-close"></a>
#### Close

**Path:** Main &gt; Edit History &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 384</sub>

<a id="cmd-specific-name"></a>
### Specific Name

**Path:** Main &gt; Specific Name  
**Kind:** Tab

enter a single, specific named item to display...

<sub>Source: `guiwins.py` line 3034</sub>

<a id="cmd-colors"></a>
### Colors

**Path:** Main &gt; Colors  
**Kind:** Tab

select colors for various elements of the display.

<sub>Source: `guiwins.py` line 3039</sub>

<a id="cmd-analyze"></a>
### Analyze

**Path:** Main &gt; Analyze  
**Kind:** Tab

Run the analysis for a Project, Profile, Task or Scene against an Ai model.

<sub>Source: `guiwins.py` line 3040</sub>

<a id="cmd-debug"></a>
### Debug

**Path:** Main &gt; Debug  
**Kind:** Tab

Display Runtime Settings option and turn on Debug mode.

<sub>Source: `guiwins.py` line 3041</sub>

<a id="cmd-cancel-6"></a>
### Cancel

**Path:** Main &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 3079</sub>

<a id="cmd-list-unnamed-items"></a>
### List Unnamed Items

**Path:** Main &gt; List Unnamed Items  
**Kind:** Option

Select this to include Profiles and Tasks that do not have a name in the list.

<sub>Source: `guiwins.py` line 3097</sub>

<a id="cmd-project"></a>
### Project

**Path:** Main &gt; Project  
**Kind:** Pulldown

Select a specific Project to target for display or editing.

<sub>Source: `guiwins.py` line 3117</sub>

<a id="cmd-profile"></a>
### Profile

**Path:** Main &gt; Profile  
**Kind:** Pulldown

Select a specific Profile to target for display or editing.

<sub>Source: `guiwins.py` line 3129</sub>

<a id="cmd-task"></a>
### Task

**Path:** Main &gt; Task  
**Kind:** Pulldown

Select a specific Task to target for display or editing.

<sub>Source: `guiwins.py` line 3141</sub>

<a id="cmd-scene"></a>
### Scene

**Path:** Main &gt; Scene  
**Kind:** Pulldown

Select a specific Scene to target for display or editing.

<sub>Source: `guiwins.py` line 3153</sub>

<a id="cmd-edit-project"></a>
### Edit Project

**Path:** Main &gt; Edit Project  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Project**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3193</sub>

<a id="cmd-edit-project-enabled"></a>
#### Enabled

**Path:** Main &gt; Edit Project &gt; Enabled  
**Kind:** Option

Disables the Project in the loaded backup, right now -- like Rename, this takes effect immediately rather than waiting for a save, and Cancel does not undo it.

<sub>Source: `guiwins.py` line 790</sub>

<a id="cmd-edit-project-cancel"></a>
#### Cancel

**Path:** Main &gt; Edit Project &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 833</sub>

<a id="cmd-edit-project-rename"></a>
#### Rename

**Path:** Main &gt; Edit Project &gt; Rename  
**Kind:** Command

Prompts for a new name and applies it to the loaded backup, right now. The Project Name field above is read-only -- this is the only way to change it.

Opens **Rename**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 838</sub>

<a id="cmd-edit-project-rename-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Project &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2132</sub>

<a id="cmd-edit-project-rename-rename"></a>
##### Rename

**Path:** Main &gt; Edit Project &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 2133</sub>

<a id="cmd-edit-project-save-to-current-file"></a>
#### Save To Current File

**Path:** Main &gt; Edit Project &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this Project -- including every edit made anywhere in this session. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 849</sub>

<a id="cmd-edit-project-save-to-android"></a>
#### Save To Android

**Path:** Main &gt; Edit Project &gt; Save To Android  
**Kind:** Command

This will write the Project, and everything in it -- every Profile and Task -- as a standalone file onto your Android device, under /Tasker/projects -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running.

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Project To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 870</sub>

<a id="cmd-edit-project-save-to-android-verify"></a>
##### Verify

**Path:** Main &gt; Edit Project &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-edit-project-save-to-android-check-ids"></a>
##### Check IDs

**Path:** Main &gt; Edit Project &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-edit-project-save-to-android-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Project &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 929</sub>

<a id="cmd-edit-project-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main &gt; Edit Project &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Project, and everything in it, as a standalone file onto the Android device, under /Tasker/projects.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 930</sub>

<a id="cmd-edit-project-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Edit Project &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-project-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main &gt; Edit Project &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This copies the Project -- and every Profile and Task in it -- to the device and opens Android's 'Open with...' chooser for it. Pick Tasker, and its own import screen comes up; you then tap Import to finish, and nothing is imported until you do.

The Project is copied to /Tasker/projects under its own name first and offered from there, so it stays behind under a name you can find -- import it by hand from Tasker if the import screen does not come up. You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 953</sub>

<a id="cmd-edit-project-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Edit Project &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-project-export-project"></a>
#### Export Project

**Path:** Main &gt; Edit Project &gt; Export Project  
**Kind:** Command

Saves this Project, and everything in it -- every Profile and Task -- as one standalone file.

<sub>Source: `guiwins.py` line 892</sub>

<a id="cmd-add-project"></a>
### Add Project

**Path:** Main &gt; Add Project  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Project**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3201</sub>

<a id="cmd-add-project-cancel"></a>
#### Cancel

**Path:** Main &gt; Add Project &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 728</sub>

<a id="cmd-add-project-ok"></a>
#### Ok

**Path:** Main &gt; Add Project &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 729</sub>

<a id="cmd-edit-profile"></a>
### Edit Profile

**Path:** Main &gt; Edit Profile  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Profile**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3210</sub>

<a id="cmd-edit-profile-add-task"></a>
#### Add Task

**Path:** Main &gt; Edit Profile &gt; Add Task  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 176</sub>

<a id="cmd-edit-profile-add-task-pick-a-task"></a>
##### Pick a Task

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins_taskedit.py` line 129</sub>

<a id="cmd-edit-profile-add-task-pick"></a>
##### Pick

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 947</sub>

<a id="cmd-edit-profile-add-task-pick-use"></a>
###### Use

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 520</sub>

<a id="cmd-edit-profile-add-task-pick-cancel"></a>
###### Cancel

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 628</sub>

<a id="cmd-edit-profile-add-task-pick-use-selected"></a>
###### Use Selected

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 629</sub>

<a id="cmd-edit-profile-add-task-pick-icon-not-listed"></a>
###### Icon not listed?

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Apps**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 645</sub>

<a id="cmd-edit-profile-add-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 328</sub>

<a id="cmd-edit-profile-add-task-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 1825</sub>

<a id="cmd-edit-profile-add-task-ok"></a>
##### Ok

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins_taskedit.py` line 1826</sub>

<a id="cmd-edit-profile-add-task-save-to-current-file"></a>
##### Save To Current File

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins_taskedit.py` line 1835</sub>

<a id="cmd-edit-profile-add-task-save-to-android"></a>
##### Save To Android

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android  
**Kind:** Command

Write the object back to your Android device -- 'Save As File' puts it on the device as a file, and 'Import Into Tasker' hands it to Tasker itself (a Task goes straight in; a Profile, Project or Scene opens Tasker's import screen).

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 1857</sub>

<a id="cmd-edit-profile-add-task-save-to-android-verify"></a>
###### Verify

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-edit-profile-add-task-save-to-android-check-ids"></a>
###### Check IDs

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-edit-profile-add-task-save-to-android-cancel"></a>
###### Cancel

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 648</sub>

<a id="cmd-edit-profile-add-task-save-to-android-save-as-file"></a>
###### Save As File

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 649</sub>

<a id="cmd-edit-profile-add-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-profile-add-task-save-to-android-import-into-tasker"></a>
###### Import Into Tasker

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 673</sub>

<a id="cmd-edit-profile-add-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-profile-add-task-export-task"></a>
##### Export Task

**Path:** Main &gt; Edit Profile &gt; Add Task &gt; Export Task  
**Kind:** Command

Exports the Task as XML to a file on your computer.

<sub>Source: `guiwins_taskedit.py` line 1866</sub>

<a id="cmd-edit-profile-cancel"></a>
#### Cancel

**Path:** Main &gt; Edit Profile &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_profedit.py` line 563</sub>

<a id="cmd-edit-profile-delete-profile"></a>
#### Delete Profile

**Path:** Main &gt; Edit Profile &gt; Delete Profile  
**Kind:** Command

Deletes only this Profile. Its Entry/Exit Tasks are kept -- a Task is owned by the Project, not by the Profile, and the same Task can be used by other Profiles.

Opens **Delete Profile**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 564</sub>

<a id="cmd-edit-profile-delete-profile-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Profile &gt; Delete Profile &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_profedit.py` line 740</sub>

<a id="cmd-edit-profile-rename"></a>
#### Rename

**Path:** Main &gt; Edit Profile &gt; Rename  
**Kind:** Command

Prompts for a new name and applies just that to the loaded backup, right now. Everything else in this dialog stays pending until Ok/Save, and the dialog stays open so you can carry on editing.

Opens **Rename**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 575</sub>

<a id="cmd-edit-profile-rename-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Profile &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2132</sub>

<a id="cmd-edit-profile-rename-rename"></a>
##### Rename

**Path:** Main &gt; Edit Profile &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 2133</sub>

<a id="cmd-edit-profile-ok"></a>
#### Ok

**Path:** Main &gt; Edit Profile &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins_profedit.py` line 587</sub>

<a id="cmd-edit-profile-save-to-current-file"></a>
#### Save To Current File

**Path:** Main &gt; Edit Profile &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this Profile -- with this dialog's edits applied, the same ones 'Ok' would keep. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins_profedit.py` line 591</sub>

<a id="cmd-edit-profile-save-to-android"></a>
#### Save To Android

**Path:** Main &gt; Edit Profile &gt; Save To Android  
**Kind:** Command

This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running (see the README's Direct XML Retrieval notes).

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Profile To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 612</sub>

<a id="cmd-edit-profile-save-to-android-verify"></a>
##### Verify

**Path:** Main &gt; Edit Profile &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-edit-profile-save-to-android-check-ids"></a>
##### Check IDs

**Path:** Main &gt; Edit Profile &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-edit-profile-save-to-android-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Profile &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_profedit.py` line 663</sub>

<a id="cmd-edit-profile-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main &gt; Edit Profile &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 664</sub>

<a id="cmd-edit-profile-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Edit Profile &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-profile-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main &gt; Edit Profile &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This copies the Profile to the device and opens Android's 'Open with...' chooser for it. Pick Tasker, and its own import screen comes up; you then tap Import to finish -- nothing is imported until you do.

The Profile is copied to /Tasker/profiles under its own name first and offered from there, so it stays behind under a name you can find -- import it by hand from Tasker if the import screen does not come up. You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 689</sub>

<a id="cmd-edit-profile-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Edit Profile &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-profile-export-profile"></a>
#### Export Profile

**Path:** Main &gt; Edit Profile &gt; Export Profile  
**Kind:** Command

Saves this Profile as a standalone .prf.xml file on this computer.

<sub>Source: `guiwins_profedit.py` line 633</sub>

<a id="cmd-edit-profile-pick"></a>
#### Pick

**Path:** Main &gt; Edit Profile &gt; Pick  
**Kind:** Command

Fill all three fields in from the loaded configuration.

Opens **App Entry Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 750</sub>

<a id="cmd-edit-profile-pick-use"></a>
##### Use

**Path:** Main &gt; Edit Profile &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 520</sub>

<a id="cmd-edit-profile-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main &gt; Edit Profile &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Apps**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 645</sub>

<a id="cmd-edit-profile-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main &gt; Edit Profile &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 328</sub>

<a id="cmd-edit-profile-pick-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Profile &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 723</sub>

<a id="cmd-add-profile"></a>
### Add Profile

**Path:** Main &gt; Add Profile  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Profile**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3218</sub>

<a id="cmd-add-profile-add-task"></a>
#### Add Task

**Path:** Main &gt; Add Profile &gt; Add Task  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 176</sub>

<a id="cmd-add-profile-add-task-pick-a-task"></a>
##### Pick a Task

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins_taskedit.py` line 129</sub>

<a id="cmd-add-profile-add-task-pick"></a>
##### Pick

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 947</sub>

<a id="cmd-add-profile-add-task-pick-use"></a>
###### Use

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 520</sub>

<a id="cmd-add-profile-add-task-pick-cancel"></a>
###### Cancel

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 628</sub>

<a id="cmd-add-profile-add-task-pick-use-selected"></a>
###### Use Selected

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 629</sub>

<a id="cmd-add-profile-add-task-pick-icon-not-listed"></a>
###### Icon not listed?

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Apps**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 645</sub>

<a id="cmd-add-profile-add-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 328</sub>

<a id="cmd-add-profile-add-task-cancel"></a>
##### Cancel

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 1825</sub>

<a id="cmd-add-profile-add-task-ok"></a>
##### Ok

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins_taskedit.py` line 1826</sub>

<a id="cmd-add-profile-add-task-save-to-current-file"></a>
##### Save To Current File

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins_taskedit.py` line 1835</sub>

<a id="cmd-add-profile-add-task-save-to-android"></a>
##### Save To Android

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android  
**Kind:** Command

Write the object back to your Android device -- 'Save As File' puts it on the device as a file, and 'Import Into Tasker' hands it to Tasker itself (a Task goes straight in; a Profile, Project or Scene opens Tasker's import screen).

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 1857</sub>

<a id="cmd-add-profile-add-task-save-to-android-verify"></a>
###### Verify

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-add-profile-add-task-save-to-android-check-ids"></a>
###### Check IDs

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-add-profile-add-task-save-to-android-cancel"></a>
###### Cancel

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 648</sub>

<a id="cmd-add-profile-add-task-save-to-android-save-as-file"></a>
###### Save As File

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 649</sub>

<a id="cmd-add-profile-add-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-add-profile-add-task-save-to-android-import-into-tasker"></a>
###### Import Into Tasker

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 673</sub>

<a id="cmd-add-profile-add-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-add-profile-add-task-export-task"></a>
##### Export Task

**Path:** Main &gt; Add Profile &gt; Add Task &gt; Export Task  
**Kind:** Command

Exports the Task as XML to a file on your computer.

<sub>Source: `guiwins_taskedit.py` line 1866</sub>

<a id="cmd-add-profile-pick"></a>
#### Pick

**Path:** Main &gt; Add Profile &gt; Pick  
**Kind:** Command

Fill all three fields in from the loaded configuration.

Opens **App Entry Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 750</sub>

<a id="cmd-add-profile-pick-use"></a>
##### Use

**Path:** Main &gt; Add Profile &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 520</sub>

<a id="cmd-add-profile-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main &gt; Add Profile &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Apps**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 645</sub>

<a id="cmd-add-profile-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main &gt; Add Profile &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 328</sub>

<a id="cmd-add-profile-pick-cancel"></a>
##### Cancel

**Path:** Main &gt; Add Profile &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 723</sub>

<a id="cmd-add-profile-cancel"></a>
#### Cancel

**Path:** Main &gt; Add Profile &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_profedit.py` line 811</sub>

<a id="cmd-add-profile-ok"></a>
#### Ok

**Path:** Main &gt; Add Profile &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins_profedit.py` line 812</sub>

<a id="cmd-add-profile-save-to-current-file"></a>
#### Save To Current File

**Path:** Main &gt; Add Profile &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Profile added to its Project, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins_profedit.py` line 816</sub>

<a id="cmd-add-profile-save-to-android"></a>
#### Save To Android

**Path:** Main &gt; Add Profile &gt; Save To Android  
**Kind:** Command

This will write the Profile as a standalone file onto your Android device, under /Tasker/profiles -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project (http://spoo.me/http_svr_example) must be installed and active on the Android device, with the server running (see the README's Direct XML Retrieval notes).

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Profile To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 837</sub>

<a id="cmd-add-profile-save-to-android-verify"></a>
##### Verify

**Path:** Main &gt; Add Profile &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-add-profile-save-to-android-check-ids"></a>
##### Check IDs

**Path:** Main &gt; Add Profile &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-add-profile-save-to-android-cancel"></a>
##### Cancel

**Path:** Main &gt; Add Profile &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_profedit.py` line 663</sub>

<a id="cmd-add-profile-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main &gt; Add Profile &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Profile as a standalone file onto the Android device, under /Tasker/profiles.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 664</sub>

<a id="cmd-add-profile-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Add Profile &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-add-profile-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main &gt; Add Profile &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This copies the Profile to the device and opens Android's 'Open with...' chooser for it. Pick Tasker, and its own import screen comes up; you then tap Import to finish -- nothing is imported until you do.

The Profile is copied to /Tasker/profiles under its own name first and offered from there, so it stays behind under a name you can find -- import it by hand from Tasker if the import screen does not come up. You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_profedit.py` line 689</sub>

<a id="cmd-add-profile-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Add Profile &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-add-profile-export-profile"></a>
#### Export Profile

**Path:** Main &gt; Add Profile &gt; Export Profile  
**Kind:** Command

Saves this Profile, with all of its conditions and linked Tasks, as one standalone .prf.xml file -- the same format Tasker's own Profile export produces.

Tasks the Profile runs are not included; they belong to their own Project.

<sub>Source: `guiwins_profedit.py` line 858</sub>

<a id="cmd-edit-task"></a>
### Edit Task

**Path:** Main &gt; Edit Task  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3227</sub>

<a id="cmd-edit-task-pick-a-task"></a>
#### Pick a Task

**Path:** Main &gt; Edit Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins_taskedit.py` line 129</sub>

<a id="cmd-edit-task-pick"></a>
#### Pick

**Path:** Main &gt; Edit Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 947</sub>

<a id="cmd-edit-task-pick-use"></a>
##### Use

**Path:** Main &gt; Edit Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 520</sub>

<a id="cmd-edit-task-pick-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 628</sub>

<a id="cmd-edit-task-pick-use-selected"></a>
##### Use Selected

**Path:** Main &gt; Edit Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 629</sub>

<a id="cmd-edit-task-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main &gt; Edit Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Apps**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 645</sub>

<a id="cmd-edit-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main &gt; Edit Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 328</sub>

<a id="cmd-edit-task-delete"></a>
#### Delete

**Path:** Main &gt; Edit Task &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins_taskedit.py` line 1314</sub>

<a id="cmd-edit-task-cancel"></a>
#### Cancel

**Path:** Main &gt; Edit Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 1458</sub>

<a id="cmd-edit-task-delete-task"></a>
#### Delete Task

**Path:** Main &gt; Edit Task &gt; Delete Task  
**Kind:** Command

Deletes this Task and every reference to it: it is removed from the Tasks of every Project that owns it, and from any Profile that runs it as its Entry/Exit Task. The Profiles themselves are kept.

Opens **Delete Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 1459</sub>

<a id="cmd-edit-task-delete-task-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Task &gt; Delete Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 1584</sub>

<a id="cmd-edit-task-rename"></a>
#### Rename

**Path:** Main &gt; Edit Task &gt; Rename  
**Kind:** Command

Prompts for a new name and applies just that to the loaded backup, right now. Everything else in this dialog stays pending until Ok/Save, and the dialog stays open so you can carry on editing.

Opens **Rename**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 1471</sub>

<a id="cmd-edit-task-rename-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Task &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2132</sub>

<a id="cmd-edit-task-rename-rename"></a>
##### Rename

**Path:** Main &gt; Edit Task &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 2133</sub>

<a id="cmd-edit-task-ok"></a>
#### Ok

**Path:** Main &gt; Edit Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins_taskedit.py` line 1483</sub>

<a id="cmd-edit-task-save-to-current-file"></a>
#### Save To Current File

**Path:** Main &gt; Edit Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this Task -- with this dialog's edits applied, the same ones 'Ok' would keep. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins_taskedit.py` line 1487</sub>

<a id="cmd-edit-task-save-to-android"></a>
#### Save To Android

**Path:** Main &gt; Edit Task &gt; Save To Android  
**Kind:** Command

This opens a choice of two: write the Task as a standalone file onto your Android device under /Tasker/tasks, or import it straight into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running (see the README's Direct XML Retrieval notes), and Tasker must be 6.2 or higher.

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while either one runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

You must exit and restart Tasker to see an imported Task in the Tasker UI.

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 1508</sub>

<a id="cmd-edit-task-save-to-android-verify"></a>
##### Verify

**Path:** Main &gt; Edit Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-edit-task-save-to-android-check-ids"></a>
##### Check IDs

**Path:** Main &gt; Edit Task &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-edit-task-save-to-android-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 648</sub>

<a id="cmd-edit-task-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main &gt; Edit Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 649</sub>

<a id="cmd-edit-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Edit Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-task-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main &gt; Edit Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 673</sub>

<a id="cmd-edit-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Edit Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-task-run-on-android"></a>
#### Run On Android

**Path:** Main &gt; Edit Task &gt; Run On Android  
**Kind:** Command

Runs this Task on your Android device and shows what it returned, or the error.

The device runs the Task as Tasker already has it: use 'Save To Android' first to run your edits.

Opens **Run Task On Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 1532</sub>

<a id="cmd-edit-task-run-on-android-close"></a>
##### Close

**Path:** Main &gt; Edit Task &gt; Run On Android &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_taskedit.py` line 488</sub>

<a id="cmd-edit-task-export-task"></a>
#### Export Task

**Path:** Main &gt; Edit Task &gt; Export Task  
**Kind:** Command

This will save the Task directly to your current drive.

<sub>Source: `guiwins_taskedit.py` line 1548</sub>

<a id="cmd-add-task"></a>
### Add Task

**Path:** Main &gt; Add Task  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Task**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3235</sub>

<a id="cmd-add-task-pick-a-task"></a>
#### Pick a Task

**Path:** Main &gt; Add Task &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins_taskedit.py` line 129</sub>

<a id="cmd-add-task-pick"></a>
#### Pick

**Path:** Main &gt; Add Task &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 947</sub>

<a id="cmd-add-task-pick-use"></a>
##### Use

**Path:** Main &gt; Add Task &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 520</sub>

<a id="cmd-add-task-pick-cancel"></a>
##### Cancel

**Path:** Main &gt; Add Task &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 628</sub>

<a id="cmd-add-task-pick-use-selected"></a>
##### Use Selected

**Path:** Main &gt; Add Task &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 629</sub>

<a id="cmd-add-task-pick-icon-not-listed"></a>
##### Icon not listed?

**Path:** Main &gt; Add Task &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Apps**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 645</sub>

<a id="cmd-add-task-pick-icon-not-listed-cancel"></a>
###### Cancel

**Path:** Main &gt; Add Task &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 328</sub>

<a id="cmd-add-task-cancel"></a>
#### Cancel

**Path:** Main &gt; Add Task &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 1825</sub>

<a id="cmd-add-task-ok"></a>
#### Ok

**Path:** Main &gt; Add Task &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins_taskedit.py` line 1826</sub>

<a id="cmd-add-task-save-to-current-file"></a>
#### Save To Current File

**Path:** Main &gt; Add Task &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile and Task in it, not just this one -- with the new Task added to it, the same way 'Ok' adds it. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins_taskedit.py` line 1835</sub>

<a id="cmd-add-task-save-to-android"></a>
#### Save To Android

**Path:** Main &gt; Add Task &gt; Save To Android  
**Kind:** Command

Write the object back to your Android device -- 'Save As File' puts it on the device as a file, and 'Import Into Tasker' hands it to Tasker itself (a Task goes straight in; a Profile, Project or Scene opens Tasker's import screen).

Opens **Save To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 1857</sub>

<a id="cmd-add-task-save-to-android-verify"></a>
##### Verify

**Path:** Main &gt; Add Task &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-add-task-save-to-android-check-ids"></a>
##### Check IDs

**Path:** Main &gt; Add Task &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-add-task-save-to-android-cancel"></a>
##### Cancel

**Path:** Main &gt; Add Task &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 648</sub>

<a id="cmd-add-task-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main &gt; Add Task &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Task as a standalone file onto the Android device, under /Tasker/tasks.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 649</sub>

<a id="cmd-add-task-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Add Task &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-add-task-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main &gt; Add Task &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This puts the Task straight into Tasker's live configuration on the Android device. Unlike a Profile, a Project or a Scene, no import screen and no tap on the device are needed -- Tasker's api/import takes a Task directly.

The Task is copied to /Tasker/tasks on the device first and imported from there, so the copy stays behind as a record of exactly what was imported. You will be asked before it replaces a file already at that path.

If Tasker does not report the Task after two attempts, that copy is handed to Android's 'Open with...' chooser instead, so you can import it by picking Tasker.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 673</sub>

<a id="cmd-add-task-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Add Task &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-add-task-export-task"></a>
#### Export Task

**Path:** Main &gt; Add Task &gt; Export Task  
**Kind:** Command

Exports the Task as XML to a file on your computer.

<sub>Source: `guiwins_taskedit.py` line 1866</sub>

<a id="cmd-run-on-android"></a>
### Run On Android

**Path:** Main &gt; Run On Android  
**Kind:** Command

Run the selected Task on your Android device and see what it returned.

Opens **Run Task On Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3243</sub>

<a id="cmd-run-on-android-close"></a>
#### Close

**Path:** Main &gt; Run On Android &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_taskedit.py` line 488</sub>

<a id="cmd-edit-scene"></a>
### Edit Scene

**Path:** Main &gt; Edit Scene  
**Kind:** Command

Modify the object currently selected in the pulldowns above.

Opens **Edit Scene**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3263</sub>

<a id="cmd-edit-scene-preview"></a>
#### Preview

**Path:** Main &gt; Edit Scene &gt; Preview  
**Kind:** Command

Display the Scene being edited as it will appear.

<sub>Source: `guiwins.py` line 1274</sub>

<a id="cmd-edit-scene-cancel"></a>
#### Cancel

**Path:** Main &gt; Edit Scene &gt; Cancel  
**Kind:** Command

Closes without saving, and puts this Scene back exactly as it was when this dialog opened -- including anything moved or resized in the Preview.

A Rename is the one thing this cannot take back: it is applied to the loaded backup as it is confirmed, and closes this dialog with it.

<sub>Source: `guiwins.py` line 1510</sub>

<a id="cmd-edit-scene-rename"></a>
#### Rename

**Path:** Main &gt; Edit Scene &gt; Rename  
**Kind:** Command

Prompts for a new name and applies it to the loaded backup, right now -- renaming the Scene everywhere, including in the Scene list of every Project that holds it.

Tasks that show or hide this Scene by name are NOT updated; those still name the old Scene.

The Scene Name field above is read-only -- this is the only way to change it.

Opens **Rename**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1524</sub>

<a id="cmd-edit-scene-rename-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Scene &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2132</sub>

<a id="cmd-edit-scene-rename-rename"></a>
##### Rename

**Path:** Main &gt; Edit Scene &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins.py` line 2133</sub>

<a id="cmd-edit-scene-ok"></a>
#### Ok

**Path:** Main &gt; Edit Scene &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 1539</sub>

<a id="cmd-edit-scene-save-to-current-file"></a>
#### Save To Current File

**Path:** Main &gt; Edit Scene &gt; Save To Current File  
**Kind:** Command

Saves the entire backup -- every Project, Profile, Task and Scene in it, not just this Scene -- including every edit made anywhere in this session. It is written to a new, timestamped copy of the file currently loaded: backup.xml becomes backup_20260728_143005.xml. The file you loaded is never written to, so it is left exactly as it was. The app then switches to the new copy, which becomes the current file for any further editing and saving; saving again replaces the timestamp rather than adding a second one. This writes to this computer only -- nothing is sent to your Android device.

<sub>Source: `guiwins.py` line 1543</sub>

<a id="cmd-edit-scene-save-to-android"></a>
#### Save To Android

**Path:** Main &gt; Edit Scene &gt; Save To Android  
**Kind:** Command

This will write the Scene as a standalone file onto your Android device, under /Tasker/scenes -- it does not import it into Tasker's live configuration.

The 'Http Server Example' Tasker Project must be installed and active on the Android device, with the server running.

The Android device must be on the same network, and the IP Address and Port must match its Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Save Scene To Android**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1564</sub>

<a id="cmd-edit-scene-save-to-android-verify"></a>
##### Verify

**Path:** Main &gt; Edit Scene &gt; Save To Android &gt; Verify  
**Kind:** Option

Reads the XML back before it is sent, and refuses the save if anything changed on the way through.

What this catches is the class of failure nothing else in the save path can: a value that this program's own writer and reader disagree about -- a carriage return inside a name, say, which is written out as typed and read back as a newline. The upload answers 200 and the file on the device matches the file that was sent, because both are already wrong.

Every object going up is compared against the one in the loaded configuration, including the Profiles, Scenes and Tasks bundled in that you did not edit. Nothing is sent if any of them differs; you get a report saying which and where.

It costs a fraction of a second and contacts nothing -- the whole check runs here, before the device is touched.

<sub>Source: `guiwins.py` line 533</sub>

<a id="cmd-edit-scene-save-to-android-check-ids"></a>
##### Check IDs

**Path:** Main &gt; Edit Scene &gt; Save To Android &gt; Check IDs  
**Kind:** Option

Has the device make a fresh backup before anything is sent, and compares its IDs with the ones being sent.

It reports an ID Tasker has already given to a different Project, Profile or Task, and an object Tasker has under a different ID. Tasker can leave an object out of an import when its ID is already taken -- and IDs for anything added here come from the loaded backup, which the device may have moved past.

It takes a few seconds, and installs a small 'MapTasker Backup For ID Check' Task on the device the first time. The backup is read into memory and deleted from the device; it is not saved on this computer.

<sub>Source: `guiwins.py` line 564</sub>

<a id="cmd-edit-scene-save-to-android-cancel"></a>
##### Cancel

**Path:** Main &gt; Edit Scene &gt; Save To Android &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1666</sub>

<a id="cmd-edit-scene-save-to-android-save-as-file"></a>
##### Save As File

**Path:** Main &gt; Edit Scene &gt; Save To Android &gt; Save As File  
**Kind:** Command

This will write the Scene as a standalone file onto the Android device, under /Tasker/scenes.

The IP Address and Port must match the Android device's Tasker server settings.

Watch the Android device while this runs: Tasker asks you to authorize the connection several times for one save, and a prompt left untapped fails it.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1667</sub>

<a id="cmd-edit-scene-save-to-android-save-as-file-close"></a>
###### Close

**Path:** Main &gt; Edit Scene &gt; Save To Android &gt; Save As File &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-scene-save-to-android-import-into-tasker"></a>
##### Import Into Tasker

**Path:** Main &gt; Edit Scene &gt; Save To Android &gt; Import Into Tasker  
**Kind:** Command

This sends the Scene -- and every Task its elements fire -- to the Android device under its own name, into /Tasker/scenes, and opens Android's 'Open with...' chooser for it.

If Tasker is in that chooser, pick it. A Scene is the one kind Tasker has been seen to refuse when it is handed one, so if it is not there -- or nothing happens -- finish it with Tasker's 'Scenes > Import One Scene' and pick the Scene by name. The file is on the device either way, and the message tells you its name.

You will be asked before it replaces a file already at that path.

The 'Http Server Example' Tasker Project must be installed and running, and Tasker must be 6.2 or higher.

The device will ask you to authorize MapTasker the first time.

Opens **Round Trip Report**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1689</sub>

<a id="cmd-edit-scene-save-to-android-import-into-tasker-close"></a>
###### Close

**Path:** Main &gt; Edit Scene &gt; Save To Android &gt; Import Into Tasker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 617</sub>

<a id="cmd-edit-scene-export-scene"></a>
#### Export Scene

**Path:** Main &gt; Edit Scene &gt; Export Scene  
**Kind:** Command

Saves this Scene, with all of its elements, as one standalone .scn.xml file -- the same format Tasker's own Scene export produces.

Tasks the Scene's elements run are not included; they belong to their own Project.

<sub>Source: `guiwins.py` line 1585</sub>

<a id="cmd-add-scene"></a>
### Add Scene

**Path:** Main &gt; Add Scene  
**Kind:** Command

Create a new object and add it to the loaded XML.

Opens **Add Scene Version**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3271</sub>

<a id="cmd-add-scene-legacy-scene"></a>
#### Legacy Scene

**Path:** Main &gt; Add Scene &gt; Legacy Scene  
**Kind:** Command

A Legacy Scene has a pixel canvas and a list of UI elements. It is the original Scene format, and is what Tasker itself produces.

Opens **Add Scene**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 1331</sub>

<a id="cmd-add-scene-legacy-scene-preview"></a>
##### Preview

**Path:** Main &gt; Add Scene &gt; Legacy Scene &gt; Preview  
**Kind:** Command

Display the Scene being edited as it will appear.

<sub>Source: `guiwins.py` line 1274</sub>

<a id="cmd-add-scene-legacy-scene-cancel"></a>
##### Cancel

**Path:** Main &gt; Add Scene &gt; Legacy Scene &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1416</sub>

<a id="cmd-add-scene-legacy-scene-ok"></a>
##### Ok

**Path:** Main &gt; Add Scene &gt; Legacy Scene &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 1417</sub>

<a id="cmd-add-scene-cancel"></a>
#### Cancel

**Path:** Main &gt; Add Scene &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1372</sub>

<a id="cmd-reset-to-default-colors"></a>
### Reset to Default Colors

**Path:** Main &gt; Reset to Default Colors  
**Kind:** Command

Restore every color to its default value.

<sub>Source: `guiwins.py` line 3302</sub>

<a id="cmd-change-prompt"></a>
### Change Prompt

**Path:** Main &gt; Change Prompt  
**Kind:** Command

Modify the prompt sent to the AI model.

Opens **Ai Prompt**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 3380</sub>

<a id="cmd-change-prompt-cancel"></a>
#### Cancel

**Path:** Main &gt; Change Prompt &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `userintr_ai.py` line 198</sub>

<a id="cmd-run-analysis"></a>
### Run Analysis

**Path:** Main &gt; Run Analysis  
**Kind:** Command

Submit the selected Project/Profile/Task and prompt to the selected model.

<sub>Source: `guiwins.py` line 3385</sub>

<a id="cmd-extended"></a>
### Extended

**Path:** Main &gt; Extended  
**Kind:** Option

Display an extended list of ALL available models.

Note: If the API key is not set for OpenAI or Gemini, then the default model list for the respective AI provider will be displayed.

Note: Not all models have been validated and one or more may return an error on analysis.

Note: Enabling this option for the first time will force the installation of the following modules and all of their dependencies: google-genai, anthropic, openai, ollama

<sub>Source: `guiwins.py` line 3404</sub>

## Notification Log

_Show every notification recorded since start-up (or the last Clear Log), newest last._

<a id="cmd-close-2"></a>
### Close

**Path:** Notification Log &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins.py` line 246</sub>

## Object Properties

_The Properties editor, shared by every Add/Edit dialog -- see the section comment._

<a id="cmd-same-as-value"></a>
### Same as Value

**Path:** Object Properties &gt; Same as Value  
**Kind:** Option

Under 'Exported Value' if you disable the 'Same as Value' option, you can customize what value gets exported when you share the variable with other users. You can keep the 'Exported Value' field blank if you want the export to not have a value at all, or you can set the value you wish to always use for exports. If you enable the 'Same as Value' option, the current variable value will be used when exporting.

<sub>Source: `guiwins.py` line 1105</sub>

<a id="cmd-cancel-7"></a>
### Cancel

**Path:** Object Properties &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1216</sub>

<a id="cmd-ok-3"></a>
### Ok

**Path:** Object Properties &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `guiwins.py` line 1220</sub>

## Overwrite Confirmation

_Confirms overwriting something that is already there, before anything is written._

<a id="cmd-cancel-8"></a>
### Cancel

**Path:** Overwrite Confirmation &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1999</sub>

## Render Background

_The element's background sub-element -- a whole RectElement inside it, and where most of a real Scene's colour lives._

<a id="cmd-rename"></a>
### Rename

**Path:** Render Background &gt; Rename  
**Kind:** Command

Tasks address this element by name (Element Text, Element Position, ... 18 action codes in all), so renaming it is not a field edit. The Rename dialog lists what depends on the current name and offers to bring those Tasks along.

Opens **Rename Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_legacyarg.py` line 123</sub>

<a id="cmd-rename-cancel"></a>
#### Cancel

**Path:** Render Background &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_designer_legacy.py` line 122</sub>

<a id="cmd-rename-rename"></a>
#### Rename

**Path:** Render Background &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins_designer_legacy.py` line 123</sub>

## Render Handlers

<a id="cmd-picker"></a>
### Picker

**Path:** Render Handlers &gt; Picker  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Show When**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 364</sub>

<a id="cmd-picker-close"></a>
#### Close

**Path:** Render Handlers &gt; Picker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 322</sub>

<a id="cmd-palette"></a>
### Palette

**Path:** Render Handlers &gt; Palette  
**Kind:** Command

Pick one of Material's own colour roles.

<sub>Source: `guiwins_designer_v2.py` line 411</sub>

<a id="cmd-pick"></a>
### Pick

**Path:** Render Handlers &gt; Pick  
**Kind:** Command

Pick a Material icon.

Opens **Icon**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 462</sub>

<a id="cmd-pick-cancel"></a>
#### Cancel

**Path:** Render Handlers &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_designer_v2.py` line 557</sub>

<a id="cmd-state"></a>
### State

**Path:** Render Handlers &gt; State  
**Kind:** Pulldown

Dynamic and Select Variable are worked out when the Scene is shown.

<sub>Source: `guiwins_designer_v2.py` line 630</sub>

<a id="cmd-variable"></a>
### Variable

**Path:** Render Handlers &gt; Variable  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Show When**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 678</sub>

<a id="cmd-variable-close"></a>
#### Close

**Path:** Render Handlers &gt; Variable &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 322</sub>

<a id="cmd-show-when"></a>
### Show When

**Path:** Render Handlers &gt; Show When  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Show When**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 995</sub>

<a id="cmd-show-when-close"></a>
#### Close

**Path:** Render Handlers &gt; Show When &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 322</sub>

<a id="cmd-close-3"></a>
### Close

**Path:** Render Handlers &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 1113</sub>

## Render Header

_The row above the canvas: the element count, orientation, snap, Add and Undo._

<a id="cmd-landscape"></a>
### Landscape

**Path:** Render Header &gt; Landscape  
**Kind:** Option

This Scene has no landscape layout of its own (its size is -1).

<sub>Source: `guiwins_designer_legacy.py` line 1187</sub>

<a id="cmd-snap"></a>
### Snap

**Path:** Render Header &gt; Snap  
**Kind:** Pulldown

Round dragged positions and sizes to this many pixels.

<sub>Source: `guiwins_designer_legacy.py` line 1198</sub>

<a id="cmd-add"></a>
### Add

**Path:** Render Header &gt; Add  
**Kind:** Command

Adds an element on top of the stack, in the middle of the Scene.

Opens **Add Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_legacy.py` line 1206</sub>

<a id="cmd-add-cancel"></a>
#### Cancel

**Path:** Render Header &gt; Add &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_designer_legacy.py` line 251</sub>

<a id="cmd-undo-2"></a>
### Undo

**Path:** Render Header &gt; Undo  
**Kind:** Command

Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. This changes what is loaded, not any file.

<sub>Source: `guiwins_designer_legacy.py` line 1213</sub>

## Render Header

<a id="cmd-add-2"></a>
### Add

**Path:** Render Header &gt; Add  
**Kind:** Command

Adds inside the selected component if it can hold children, otherwise directly after it.

Opens **Add Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 1290</sub>

<a id="cmd-add-cancel-2"></a>
#### Cancel

**Path:** Render Header &gt; Add &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_designer_v2.py` line 180</sub>

<a id="cmd-undo-3"></a>
### Undo

**Path:** Render Header &gt; Undo  
**Kind:** Command

Back out the most recent Add/Edit/Delete/Rename change made to the loaded XML. This changes what is loaded, not any file.

<sub>Source: `guiwins_designer_v2.py` line 1301</sub>

## Render Modifiers

<a id="cmd-picker-2"></a>
### Picker

**Path:** Render Modifiers &gt; Picker  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Show When**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 364</sub>

<a id="cmd-picker-close-2"></a>
#### Close

**Path:** Render Modifiers &gt; Picker &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 322</sub>

<a id="cmd-palette-2"></a>
### Palette

**Path:** Render Modifiers &gt; Palette  
**Kind:** Command

Pick one of Material's own colour roles.

<sub>Source: `guiwins_designer_v2.py` line 411</sub>

<a id="cmd-pick-2"></a>
### Pick

**Path:** Render Modifiers &gt; Pick  
**Kind:** Command

Pick a Material icon.

Opens **Icon**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 462</sub>

<a id="cmd-pick-cancel-2"></a>
#### Cancel

**Path:** Render Modifiers &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_designer_v2.py` line 557</sub>

<a id="cmd-state-2"></a>
### State

**Path:** Render Modifiers &gt; State  
**Kind:** Pulldown

Dynamic and Select Variable are worked out when the Scene is shown.

<sub>Source: `guiwins_designer_v2.py` line 630</sub>

<a id="cmd-variable-2"></a>
### Variable

**Path:** Render Modifiers &gt; Variable  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Show When**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 678</sub>

<a id="cmd-variable-close-2"></a>
#### Close

**Path:** Render Modifiers &gt; Variable &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 322</sub>

<a id="cmd-show-when-2"></a>
### Show When

**Path:** Render Modifiers &gt; Show When  
**Kind:** Command

Pick from the Scene's environment and global variables.

Opens **Show When**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_designer_v2.py` line 995</sub>

<a id="cmd-show-when-close-2"></a>
#### Close

**Path:** Render Modifiers &gt; Show When &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 322</sub>

<a id="cmd-close-4"></a>
### Close

**Path:** Render Modifiers &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_designer_v2.py` line 1075</sub>

## Render Scene

_One Event sub-tab: when it fires, the Task it fires, and what that Task can read._

<a id="cmd-pick-a-task"></a>
### Pick a Task

**Path:** Render Scene &gt; Pick a Task  
**Kind:** Pulldown

Pick a Task which will be called by this action.

<sub>Source: `guiwins_taskedit.py` line 129</sub>

<a id="cmd-close-5"></a>
### Close

**Path:** Render Scene &gt; Close  
**Kind:** Command

Stop firing anything on this event.

<sub>Source: `guiwins_sceneprops.py` line 756</sub>

<a id="cmd-stop-event"></a>
### Stop Event

**Path:** Render Scene &gt; Stop Event  
**Kind:** Option

Any key handled by the scene is not passed on to the system -- how a Scene keeps the back key from closing it. Written the way Tasker writes it: a <stopEvent> inside the Scene's <LinkClickFilter>, created when this is ticked and taken away again when it is unticked and nothing else is left in it.

<sub>Source: `guiwins_sceneprops.py` line 862</sub>

<a id="cmd-pick-3"></a>
### Pick

**Path:** Render Scene &gt; Pick  
**Kind:** Command

Choose from the Applications named in the loaded configuration.

Opens **App Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 947</sub>

<a id="cmd-pick-use"></a>
#### Use

**Path:** Render Scene &gt; Pick &gt; Use  
**Kind:** Command

Uses what is entered or selected above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 520</sub>

<a id="cmd-pick-cancel-3"></a>
#### Cancel

**Path:** Render Scene &gt; Pick &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 628</sub>

<a id="cmd-pick-use-selected"></a>
#### Use Selected

**Path:** Render Scene &gt; Pick &gt; Use Selected  
**Kind:** Command

Uses what is selected in the list above, and closes the picker.

<sub>Source: `guiwins_taskedit.py` line 629</sub>

<a id="cmd-pick-icon-not-listed"></a>
#### Icon not listed?

**Path:** Render Scene &gt; Pick &gt; Icon not listed?  
**Kind:** Command

Fetch every installed application's own icon from your Android device. What is listed now is only the icons this configuration already uses. Tasker's built-in icons and the contents of an icon pack cannot be fetched, and are typed by name.

Opens **Fetch Apps**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_taskedit.py` line 645</sub>

<a id="cmd-pick-icon-not-listed-cancel"></a>
##### Cancel

**Path:** Render Scene &gt; Pick &gt; Icon not listed? &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_taskedit.py` line 328</sub>

<a id="cmd-apply-to-task"></a>
### Apply to Task

**Path:** Render Scene &gt; Apply to Task  
**Kind:** Command

Puts these action edits into the loaded configuration now, without closing -- the same as 'Ok' in the Edit Task dialog. Ok does it for you here too, so this is only for keeping them mid-edit. Nothing is written to a file and nothing is sent to Android. This Task is not part of the Scene, so neither this window's Cancel nor the Scene dialog's takes these edits back once they have landed. Undo does.

<sub>Source: `guiwins_sceneprops.py` line 958</sub>

<a id="cmd-create-task"></a>
### Create Task

**Path:** Render Scene &gt; Create Task  
**Kind:** Command

Adds this Task to the loaded configuration and points this event at it, the same as 'Ok' in the Add Task dialog -- nothing is written to a file and nothing is sent to Android. Ok does it for you too, so this is only for creating it without closing. Until then the Task exists only in this window and Cancel discards it. Afterwards it is a Task like any other -- Cancel takes the binding back but not the Task, and Undo takes both.

<sub>Source: `guiwins_sceneprops.py` line 1070</sub>

<a id="cmd-delete"></a>
### Delete

**Path:** Render Scene &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins_taskedit.py` line 1314</sub>

## Render Tasks

_What this element does when it is used._

<a id="cmd-close-6"></a>
### Close

**Path:** Render Tasks &gt; Close  
**Kind:** Command

Stop firing anything on this event.

<sub>Source: `guiwins_designer_legacy.py` line 940</sub>

## Render Toolbar

_The structural operations, all of which need exactly one element selected._

<a id="cmd-duplicate"></a>
### Duplicate

**Path:** Render Toolbar &gt; Duplicate  
**Kind:** Command

Make a copy of the selected Scene element.

<sub>Source: `guiwins_designer_legacy.py` line 1264</sub>

<a id="cmd-delete-2"></a>
### Delete

**Path:** Render Toolbar &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins_designer_legacy.py` line 1267</sub>

## Render Toolbar

_The structural operations._

<a id="cmd-delete-3"></a>
### Delete

**Path:** Render Toolbar &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins_designer_v2.py` line 1354</sub>

## Right Drawer

_The right drawer: every action, report, setting and help button._

<a id="cmd-clear-2"></a>
### Clear

**Path:** Right Drawer &gt; Clear  
**Kind:** Command

Clear the Map/Diagram/Tree view data currently held and displayed.

<sub>Source: `guiwins.py` line 2666</sub>

<a id="cmd-get-local-xml-file"></a>
### Get Local XML File

**Path:** Right Drawer &gt; Get Local XML File  
**Kind:** Command

Fetch XML from a local drive on this computer.

The XML fetched will become the current source for MapTasker commands.

Opens **Local File Picker**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2691</sub>

<a id="cmd-get-local-xml-file-cancel"></a>
#### Cancel

**Path:** Right Drawer &gt; Get Local XML File &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `getfile.py` line 62</sub>

<a id="cmd-get-local-xml-file-ok"></a>
#### Ok

**Path:** Right Drawer &gt; Get Local XML File &gt; Ok  
**Kind:** Command

Keeps what this dialog holds and closes it. Nothing is written to a file: the change is kept in the loaded configuration, for a save to write out later.

<sub>Source: `getfile.py` line 63</sub>

<a id="cmd-exit"></a>
### Exit

**Path:** Right Drawer &gt; Exit  
**Kind:** Command

Exit the program (quit).

<sub>Source: `guiwins.py` line 2704</sub>

<a id="cmd-close-tabs-on-exit"></a>
### Close Tabs On Exit

**Path:** Right Drawer &gt; Close Tabs On Exit  
**Kind:** Option

When enabled, clicking 'Exit' also closes the main MapTasker window and any Map/Diagram windows/tabs it opened.

When disabled, 'Exit' shuts down MapTasker but leaves those windows/tabs open.

<sub>Source: `guiwins.py` line 2713</sub>

<a id="cmd-open-view-in-new-window"></a>
### Open View In New Window

**Path:** Right Drawer &gt; Open View In New Window  
**Kind:** Option

When enabled, each Map/Diagram request opens in its own new window/tab, so you can keep earlier ones up alongside it to compare.

When disabled, a request reuses that view's existing window/tab, replacing what's in it.

Leave it off unless you want to compare: a brand new window/tab is the one your browser may block, since it gets opened once the view has finished building rather than the instant you click.

<sub>Source: `guiwins.py` line 2728</sub>

<a id="cmd-map"></a>
### Map

**Path:** Right Drawer &gt; Map  
**Kind:** Command

Displays the Map view.

Use this to display the Tasker configuration of your Projects, Profiles, Tasks, and Scenes.

<sub>Source: `guiwins.py` line 2749</sub>

<a id="cmd-diagram"></a>
### Diagram

**Path:** Right Drawer &gt; Diagram  
**Kind:** Command

Displays the Diagram view.

Use this to visualize the relationships between your Projects, Profiles, Tasks, and Scenes.

<sub>Source: `guiwins.py` line 2758</sub>

<a id="cmd-tree"></a>
### Tree

**Path:** Right Drawer &gt; Tree  
**Kind:** Command

Displays the Tree view.

Use this to navigate the hierarchical structure of your Projects, Profiles, Tasks, and Scenes.

<sub>Source: `guiwins.py` line 2770</sub>

<a id="cmd-health-check"></a>
### Health Check

**Path:** Right Drawer &gt; Health Check  
**Kind:** Command

Scan the loaded XML for broken references, unreferenced Tasks, Profiles and Scenes, naming problems, Task flow, variables, behaviour on the device, and secrets.

You choose which of those to report before it runs, and that choice is remembered.

Results are displayed here and saved to a text file in the Output Folder.

Opens **Health Check**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2797</sub>

<a id="cmd-health-check-cancel"></a>
#### Cancel

**Path:** Right Drawer &gt; Health Check &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 1845</sub>

<a id="cmd-fix-findings"></a>
### Fix Findings

**Path:** Right Drawer &gt; Fix Findings  
**Kind:** Command

Repair the Health Check findings that have an obvious fix: set a long Task's collision handling, give a blocking action a timeout, close an 'If' that is never closed, point a broken 'Goto' at a label that exists, delete a Task nothing runs.

Everything is shown before anything is done, you tick what you want, and the whole lot is one press of Undo afterwards.

Most kinds of finding are not offered here -- a broken 'Perform Task' or a password written into an action is a decision only you can make.

<sub>Source: `guiwins.py` line 2824</sub>

<a id="cmd-compare-files"></a>
### Compare Files

**Path:** Right Drawer &gt; Compare Files  
**Kind:** Command

Compare another XML file against the loaded one: what was added, removed, renamed and changed.

Use it to see what a TaskerNet import brought in, what an edit changed, or what is different between two backups.

If the loaded file came from 'Save to Current File', the file it was saved from is offered directly.

Results are displayed here and saved to a text file in the Output Folder.

Opens **Choose Comparison File**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2853</sub>

<a id="cmd-compare-files-cancel"></a>
#### Cancel

**Path:** Right Drawer &gt; Compare Files &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `userintr_reports.py` line 79</sub>

<a id="cmd-changes-since"></a>
### Changes Since...

**Path:** Right Drawer &gt; Changes Since...  
**Kind:** Command

What has changed in your configuration since a moment you choose: today, this week, this month, everything kept, or a specific date.

No file to pick -- every configuration you load is kept, compressed, in a MapTasker_Timeline folder in the current directory, and the one from back then is compared against what you have open now.

Results are displayed here and saved to a text file in the Output Folder.

Opens **Changes Since**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2878</sub>

<a id="cmd-changes-since-cancel"></a>
#### Cancel

**Path:** Right Drawer &gt; Changes Since... &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins.py` line 2059</sub>

<a id="cmd-restore-from-history"></a>
### Restore From History

**Path:** Right Drawer &gt; Restore From History  
**Kind:** Command

Bring back a Task, Profile or Scene that has been deleted, or put one back as it was before it was edited -- from any configuration kept in the history that 'Changes Since...' reads.

One object at a time, never a merge: every restore is shown before anything happens, says what it leaves for you to do (a Profile to relink, say), and is one press of Undo afterwards.

Opens **Restore**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2904</sub>

<a id="cmd-restore-from-history-save-to-current-file"></a>
#### Save To Current File

**Path:** Right Drawer &gt; Restore From History &gt; Save To Current File  
**Kind:** Command

Write the entire configuration to a new, timestamped file beside the loaded one.

<sub>Source: `guiwins_restore.py` line 266</sub>

<a id="cmd-restore-from-history-close"></a>
#### Close

**Path:** Right Drawer &gt; Restore From History &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_restore.py` line 274</sub>

<a id="cmd-variable-xref"></a>
### Variable Xref

**Path:** Right Drawer &gt; Variable Xref  
**Kind:** Command

Trace every %variable in the loaded XML: where each one is set, where it is read, which are read but never set, which are set but never read, and which near-identical names (%MyVar against %Myvar) are likely typos.

Searched: Task actions and their conditions, plugin configuration, Profile contexts and Scenes.

Results are displayed here and saved to a text file in the Output Folder.

<sub>Source: `guiwins.py` line 2934</sub>

<a id="cmd-xref-live"></a>
### Xref Live

**Path:** Right Drawer &gt; Xref Live  
**Kind:** Command

The Variable Xref, plus what each global variable holds right now on the Android device, read through Tasker's HTTP API.

It also checks the 'read but never set' and 'set but never read' findings against the device: a variable the device does not have is a confirmed problem, and one it does have was set or read by something outside this file.

Nothing on the device is changed. Values appear in the saved report.

Opens **Variable Xref Live**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2952</sub>

<a id="cmd-xref-live-cancel"></a>
#### Cancel

**Path:** Right Drawer &gt; Xref Live &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `userintr_reports.py` line 257</sub>

<a id="cmd-task-flow"></a>
### Task Flow

**Path:** Right Drawer &gt; Task Flow  
**Kind:** Command

Read every Task's control flow -- its If/Else/End If, For/End For, Goto and Stop -- and report what does not hold together: a block that is never closed, a Goto aimed at a label no action carries, and actions nothing can ever reach.

With a single Task chosen in the 'Specific Name' tab, that Task is also drawn as a flowchart in its own window, with an arrow from every Goto to the action it lands on.

Results are displayed here and saved to a text file in the Output Folder.

<sub>Source: `guiwins.py` line 2974</sub>

<a id="cmd-what-fires-when"></a>
### What Fires When?

**Path:** Right Drawer &gt; What Fires When?  
**Kind:** Command

Pick a moment -- a date and time, the Wi-Fi network the device is on, the app in front and the battery level -- and see which Profiles it makes active, the order their Tasks start in, and where they collide.

Anything the inputs do not describe, such as an Event or a location, is treated as unknown, so a Profile that depends on it is shown as possible and says what it is waiting on.

Opens **Firesim**, whose own commands are listed beneath this one.

<sub>Source: `guiwins.py` line 2999</sub>

<a id="cmd-what-fires-when-now"></a>
#### Now

**Path:** Right Drawer &gt; What Fires When? &gt; Now  
**Kind:** Command

Set the date and time back to this moment.

<sub>Source: `guiwins_firesim.py` line 187</sub>

<a id="cmd-what-fires-when-close"></a>
#### Close

**Path:** Right Drawer &gt; What Fires When? &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_firesim.py` line 190</sub>

<a id="cmd-reset-options"></a>
### Reset Options

**Path:** Right Drawer &gt; Reset Options  
**Kind:** Command

Reset all of the options to their default values, including colors, font used, and other settings.

The currently loaded XML will be cleared out.

<sub>Source: `guiwins.py` line 3667</sub>

<a id="cmd-save"></a>
### Save

**Path:** Right Drawer &gt; Save  
**Kind:** Command

Save these settings for later use.

<sub>Source: `guiwins.py` line 3689</sub>

<a id="cmd-restore"></a>
### Restore

**Path:** Right Drawer &gt; Restore  
**Kind:** Command

Restore the settings from a previously saved session.

<sub>Source: `guiwins.py` line 3698</sub>

<a id="cmd-report-issue"></a>
### Report Issue

**Path:** Right Drawer &gt; Report Issue  
**Kind:** Command

Report any issues and/or suggestions to the developer.

This will open a browser window to the GitHub Issues page, and you will need a GitHub account to submit an issue.

<sub>Source: `guiwins.py` line 3709</sub>

<a id="cmd-get-xml-from-android-device"></a>
### Get XML from Android Device

**Path:** Right Drawer &gt; Get XML from Android Device  
**Kind:** Command

Fetch XML from an Android device.

You must be on the same network as the Android device, and the device must be running and connected.

<sub>Source: `guiwins.py` line 3781</sub>

<a id="cmd-display-help"></a>
### Display Help

**Path:** Right Drawer &gt; Display Help  
**Kind:** Command

Display this help text.

<sub>Source: `guiwins.py` line 3812</sub>

<a id="cmd-get-android-help"></a>
### Get Android Help

**Path:** Right Drawer &gt; Get Android Help  
**Kind:** Command

Display the help for fetching the XML file from your Android device.

<sub>Source: `guiwins.py` line 3819</sub>

## Scene Properties

_The Scene's own Properties -- its <PropertiesElement> -- laid out the way Tasker's own "Scene Properties Edit" screen is: UI, Actions and Event, with Event holding Key, Home Tap and Tab Tap._

<a id="cmd-rename-2"></a>
### Rename

**Path:** Scene Properties &gt; Rename  
**Kind:** Command

Tasks address this element by name (Element Text, Element Position, ... 18 action codes in all), so renaming it is not a field edit. The Rename dialog lists what depends on the current name and offers to bring those Tasks along.

Opens **Rename Legacy Element**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_legacyarg.py` line 123</sub>

<a id="cmd-rename-cancel-2"></a>
#### Cancel

**Path:** Scene Properties &gt; Rename &gt; Cancel  
**Kind:** Command

Closes this dialog and keeps nothing it was holding.

<sub>Source: `guiwins_designer_legacy.py` line 122</sub>

<a id="cmd-rename-rename-2"></a>
#### Rename

**Path:** Scene Properties &gt; Rename &gt; Rename  
**Kind:** Command

Give the object being edited a new name.

<sub>Source: `guiwins_designer_legacy.py` line 123</sub>

<a id="cmd-cancel-9"></a>
### Cancel

**Path:** Scene Properties &gt; Cancel  
**Kind:** Command

Puts these properties back the way they were when this window opened, and drops the actions of any Task edited under the Event tab. A Task already put into the configuration by its own button -- 'Apply to Task', or 'Create Task' -- stays there. Undo takes those back.

<sub>Source: `guiwins_sceneprops.py` line 326</sub>

<a id="cmd-ok-4"></a>
### Ok

**Path:** Scene Properties &gt; Ok  
**Kind:** Command

Keeps everything, including the actions of any Task edited under the Event tab. A Task composed under an event that had none is created and bound if you put any actions in it. Undo takes a Task edit back.

<sub>Source: `guiwins_sceneprops.py` line 336</sub>

<a id="cmd-delete-4"></a>
### Delete

**Path:** Scene Properties &gt; Delete  
**Kind:** Command

Remove the object being edited from the loaded XML.

<sub>Source: `guiwins_sceneprops.py` line 516</sub>

## Ui

_Toolbar, then the scroll area the canvas is drawn into._

<a id="cmd-bounds"></a>
### Bounds

**Path:** Ui &gt; Bounds  
**Kind:** Option

Outline every component and name it, the way the designer's tree names it.

<sub>Source: `guiwins_views.py` line 807</sub>

<a id="cmd-actions"></a>
### Actions

**Path:** Ui &gt; Actions  
**Kind:** Option

Show what each component does when tapped, and what it writes to.

<sub>Source: `guiwins_views.py` line 820</sub>

<a id="cmd-landscape-2"></a>
### Landscape

**Path:** Ui &gt; Landscape  
**Kind:** Option

Turn the screen on its side and let the layout re-flow into it.

<sub>Source: `guiwins_views.py` line 861</sub>

<a id="cmd-text-density"></a>
### Text density

**Path:** Ui &gt; Text density  
**Kind:** Pulldown

A Scene's element positions are stored in device pixels, but its text sizes are stored in Android's sp units. The number that converts between the two is a property of the phone the Scene is shown on, and is not in the backup file.

So it is set here. Raise it if the text looks too small for its elements, lower it if the text overflows them.

<sub>Source: `guiwins_views.py` line 884</sub>

<a id="cmd-snap-2"></a>
### Snap

**Path:** Ui &gt; Snap  
**Kind:** Pulldown

Round dragged positions and sizes to this many pixels.

<sub>Source: `guiwins_views.py` line 917</sub>

<a id="cmd-screen"></a>
### Screen

**Path:** Ui &gt; Screen  
**Kind:** Pulldown

A Version 2 Scene has no size of its own -- it lays itself out inside whatever screen it is shown on, so there is nothing in the backup file to draw it at.

Change this to see the layout re-flow. A Flow Row wraps differently, and any 'Show when' written against %sv2_render_width is asking about exactly this.

<sub>Source: `guiwins_views.py` line 940</sub>

## Ui

_Builds the UI layout for the various text views, including toolbar and scrollable display area._

<a id="cmd-export"></a>
### Export

**Path:** Ui &gt; Export  
**Kind:** Command

(Map and Diagram only) Save what the view shows to a file in the current directory, as Markdown, JSON or PDF.

<sub>Source: `guiwins_views.py` line 412</sub>

<a id="cmd-zoom-out"></a>
### Zoom Out

**Path:** Ui &gt; Zoom Out  
**Kind:** Command

Zoom out. Ctrl/⌘ and the scroll wheel does the same.

<sub>Source: `guiwins_views.py` line 442</sub>

<a id="cmd-zoom-in"></a>
### Zoom In

**Path:** Ui &gt; Zoom In  
**Kind:** Command

Zoom in. Ctrl/⌘ and the scroll wheel does the same.

<sub>Source: `guiwins_views.py` line 450</sub>

<a id="cmd-collapse"></a>
### Collapse

**Path:** Ui &gt; Collapse  
**Kind:** Command

Collapse every Project down to its title bar.

One Project on its own collapses by clicking the top edge of its box.

<sub>Source: `guiwins_views.py` line 455</sub>

<a id="cmd-expand"></a>
### Expand

**Path:** Ui &gt; Expand  
**Kind:** Command

Expand every collapsed Project.

<sub>Source: `guiwins_views.py` line 468</sub>

<a id="cmd-reset"></a>
### Reset

**Path:** Ui &gt; Reset  
**Kind:** Command

Back to the whole diagram: no zoom, nothing folded, nothing filtered.

<sub>Source: `guiwins_views.py` line 473</sub>

<a id="cmd-help"></a>
### Help

**Path:** Ui &gt; Help  
**Kind:** Command

The diagram is clickable:

Click a Project, Profile, Task or Scene name to be taken to it in the Map.

Shift-click a Task to light up the whole chain of calls it takes part in -- everything it calls, everything that calls it, and the arrows between them.

Right-click any name for the rest: collapse its Project, show only that Project, follow its chain.

Click the ▾ beside a Project to collapse it, and the ▸ to bring it back.

Ctrl (or ⌘) and the scroll wheel zooms. Esc clears a chain.

<sub>Source: `guiwins_views.py` line 480</sub>

<a id="cmd-rebuild"></a>
### Rebuild

**Path:** Ui &gt; Rebuild  
**Kind:** Command

(Diagram only) Offered when the Diagram was drawn for a different selection than the one chosen now; it draws the Diagram again for the current one.

<sub>Source: `guiwins_views.py` line 1553</sub>

<a id="cmd-search"></a>
### Search

**Path:** Ui &gt; Search  
**Kind:** Command

The 'Search' button will search for and highlight every instance of the case-insensitive string entered in the search box, starting at the top of the data.

It will only show the first 200 instances of the search string.

Click on the line number to go to that line in the text view box.

The 'Clear' button will clear the search results.

<sub>Source: `guiwins_views.py` line 1604</sub>

<a id="cmd-clear-3"></a>
### Clear

**Path:** Ui &gt; Clear  
**Kind:** Command

Clear the Map/Diagram/Tree view data currently held and displayed.

<sub>Source: `guiwins_views.py` line 1614</sub>

<a id="cmd-find-replace"></a>
### Find/Replace

**Path:** Ui &gt; Find/Replace  
**Kind:** Command

'Find/Replace' asks the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything that names a given app or Scene.

The boxes combine -- pick a trigger and an action to find the Profiles that trigger that way and run a Task that does that.

Results come back as a list of objects; click one to be taken to it.

Opens **Init**, whose own commands are listed beneath this one.

<sub>Source: `guiwins_views.py` line 1623</sub>

<a id="cmd-find-replace-find"></a>
#### Find

**Path:** Ui &gt; Find/Replace &gt; Find  
**Kind:** Tab

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins_search.py` line 740</sub>

<a id="cmd-find-replace-replace"></a>
#### Replace

**Path:** Ui &gt; Find/Replace &gt; Replace  
**Kind:** Tab

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins_search.py` line 741</sub>

<a id="cmd-find-replace-close"></a>
#### Close

**Path:** Ui &gt; Find/Replace &gt; Close  
**Kind:** Command

Closes this window without changing anything.

<sub>Source: `guiwins_search.py` line 761</sub>

<a id="cmd-find-replace-find-2"></a>
#### Find

**Path:** Ui &gt; Find/Replace &gt; Find  
**Kind:** Command

(Map and Diagram only) Ask the loaded configuration a question rather than searching the text on screen: every Task performing a given action, every Profile a given trigger fires, everything naming a given app or Scene. Click a result to be taken to it.

<sub>Source: `guiwins_search.py` line 815</sub>

<a id="cmd-find-replace-save-results"></a>
#### Save Results

**Path:** Ui &gt; Find/Replace &gt; Save Results  
**Kind:** Command

Save the 'Find/Replace' results to a text file.

<sub>Source: `guiwins_search.py` line 816</sub>

<a id="cmd-find-replace-ask-ai"></a>
#### Ask AI

**Path:** Ui &gt; Find/Replace &gt; Ask AI  
**Kind:** Command

(in the Find/Replace window) Type the question in plain words, and the AI model selected on the Analyze tab fills in the Find boxes for you. The search itself runs exactly as if you had picked them.

<sub>Source: `guiwins_search.py` line 836</sub>

<a id="cmd-find-replace-narrow-to-project"></a>
#### Narrow to Project

**Path:** Ui &gt; Find/Replace &gt; Narrow to Project  
**Kind:** Pulldown

_There is no tooltip on this one; this is the note written beside it in the source._

Hidden when a single Project/Profile/Task/Scene is selected, because the scope has already done the narrowing and this can then only mislead. "Every Project" is the option that goes wrong: with one Task selected it is the ONLY entry and means that Task, and with one Project selected it and that Project's own entry mean the same thing. Either way the label promises the whole configuration and delivers a corner of it. Left at "" rather than removed, so the query still reads a value and no code below has to care whether the widget is on screen.

<sub>Source: `guiwins_search.py` line 876</sub>

<a id="cmd-toggle-wrap"></a>
### Toggle Wrap

**Path:** Ui &gt; Toggle Wrap  
**Kind:** Command

Turn line wrapping on or off in the displayed output.

<sub>Source: `guiwins_views.py` line 1643</sub>

<a id="cmd-profiles-per-line"></a>
### Profiles Per Line

**Path:** Ui &gt; Profiles Per Line  
**Kind:** Pulldown

(Diagram only) The number of Profiles drawn side-by-side on a single line.

<sub>Source: `guiwins_views.py` line 1655</sub>

## Upgrade If Newer

_Ask PyPI on a worker thread, then fill the upgrade slot if there is a newer version._

<a id="cmd-upgrade-to-latest-version"></a>
### Upgrade to Latest Version

**Path:** Upgrade If Newer &gt; Upgrade to Latest Version  
**Kind:** Command

Clicking this will launch 'pip install --upgrade maptasker' in the background, and then relaunch MapTasker.

<sub>Source: `guiutils.py` line 1909</sub>

<a id="cmd-what-s-new"></a>
### What's New?

**Path:** Upgrade If Newer &gt; What's New?  
**Kind:** Command

Display the changes in the new version.

<sub>Source: `guiutils.py` line 1921</sub>

## Validate Or Filelist Xml

_Validates an XML file on an Android device or generates a NiceGUI dropdown selection list if no file or an explicit 'list files' action is requested._

<a id="cmd-cancel-entry-2"></a>
### Cancel Entry

**Path:** Validate Or Filelist Xml &gt; Cancel Entry  
**Kind:** Command

Back out of the Android fetch process.

<sub>Source: `userintr_android.py` line 291</sub>

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
| `-detail` |  | Level of detail to display: 0 = display simple Project/Profile/Task/Scene names only with no details 1 = display all Task action details for unknown Tasks only 2 = display full Task action name on every Task 3 = display full Task action details on every Task with action details 4 = detail level 3 plus global variables 5 = detail level 4 plus Scene element UI details (default). Example: '-detail 2' for Task action names only |
| `-directory` |  | Display a directory of hotlinks for all Projects/Profiles/Tasks/Scenes. |
| `-e`, `-everything` |  | Display everything: full detail, Profile/Task conditions, TaskerNet information, directory, etc.. |
| `-file` |  | Directory and file name of Tasker XML file to analyze. Example: -file ~/Downloads/backup.xml |
| `-font` |  | Name of monospaced font to use in output (default = 'Courier'). Enter font name of 'help' for a list of valid fonts. |
| `-g`, `-gui` |  | Prompt for (these) settings via the graphical user interface (GUI): This argument overrides all other arguments. |
| `-guiview` |  |  |
| `-i`, `-indent` |  | Number of spaces to indent Task If/Then/Else Actions (default = 4) |
| `-names` | bold, highlight, underline, italicize | Display all Projects/Profiles/Tasks/Scenes in bold, underlined, italicized and/or highlighted text. Example: names underline italicize |
| `-o`, `-outline` |  | Display configuration outline of Projects, Profiles, Tasks and Scenes, and display the configuraion Map (MapTasker_map.txt) in the default text editor" |
| `-outdir` |  | Folder to write reports, exports and the Map/Diagram files to (default = a MapTasker folder in your Documents folder). Example: -outdir ~/MapTasker_Reports |
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
python tools/misc/build_command_wiki.py --publish
```
