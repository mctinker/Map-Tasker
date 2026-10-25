# MapTasker Runtime Options

The options MapTasker takes on the command line.  Everything here is also what `-h` prints.

_Generated from the MapTasker 15.0.2 source by `build_runtime_options_wiki.py`._ _Do not edit this page by hand -- rerun that program instead._

## How to use this page

* Options are written with a single dash, as in `-detail 3`.  A value with spaces in it goes in quotes.
* **Default** is what the option is when you do not give it.  MapTasker remembers the options you give it from one run to the next; `-reset` forgets them, and `-runtime` prints the ones in force at the top of the output.
* `-h` shows this list in the terminal.  `-g` (or `-gui`) asks for the options in a window instead, and overrides every other option.
* To run one of the reports below with no window, name it on the command line.  Those take the second set of options and nothing from the first.

## Contents

* [General options](#general-options)
* [Fetching the backup from an Android device](#fetching-the-backup-from-an-android-device)
* [Output color options](#output-color-options)
* [Reports with no window](#reports-with-no-window)
  * [Choose one report](#choose-one-report)
  * [Options for the reports](#options-for-the-reports)
* [Exit codes](#exit-codes)

## General options

| Option | Value | Default | What it does |
| --- | --- | --- | --- |
| `-ai_model` | _one of the choices below_ |  | The model to use for Profiles and Tasks Ai analysis.<br>_Choices:_ `gpt-5.5`, `gpt-5.5-pro`, `gpt-5.4`, `gpt-5.4-pro`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.3-Codex`, `gpt-5.2`, `gpt-5.2-pro`, `gpt-5.1`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-pro`, `gpt-4o`, `gpt-4o-latest`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `o1-mini`, `o1-pro`, `o1`, `o3`, `o3-pro`, `o4-mini`, `aya`, `codegemma:2b`, `codellama:latest`, `exaone-deep`, `gemma3:1b`, `gpt-oss`, `llama2`, `llama3.1`, `llama3.2`, `llama3.3`, `minimax-m3`, `mistral`, `mistral-nemo`, `phi3`, `phi4-mini`, `qwen3:1:latest`, `qwen3.5:0.8b`, `tinyllama`, `claude-fable-5-1`, `claude-haiku-4-5`, `claude-haiku-5-5`, `claude-opus-5`, `claude-opus-5-5`, `claude-sonnet-5`, `claude-sonnet-5-5`, `gemini-3.1-flash-lite`, `gemini-3.1-pro-preview`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`, `gemini-3.8-flash-lite`, `gemini-4-argon` |
| `-appearance` | `{system,light,dark}` | `system` | Display appearance mode: system (default), light, dark<br>Example: `-appearance dark` |
| `-conditions` |  |  | Display the condition(s) for Profiles and Tasks |
| `-debug` |  |  | Print and log debug information |
| `-detail` | `{0,1,2,3,4,5}` | `3` | Level of detail to display:<br>0 = display simple Project/Profile/Task/Scene names only with no details<br>1 = display all Task action details for unknown Tasks only<br>2 = display full Task action name on every Task<br>3 = display full Task action details on every Task with action details<br>4 = detail level 3 plus global variables<br>5 = detail level 4 plus Scene element UI details (default).<br>Example: `'-detail 2' for Task action names only` |
| `-directory` |  |  | Display a directory of hotlinks for all Projects/Profiles/Tasks/Scenes. |
| `-e, -everything` |  |  | Display everything: full detail, Profile/Task conditions,<br>TaskerNet information, directory, etc..<br>_Use only one of:_ `-e`, `-twisty` |
| `-file` | `FILE` |  | Directory and file name of Tasker XML file to analyze.<br>Example: `-file ~/Downloads/backup.xml` |
| `-font` | `FONT` |  | Name of monospaced font to use in output (default = 'Courier').<br>Enter font name of 'help' for a list of valid fonts. |
| `-g, -gui` |  |  | Prompt for (these) settings via the graphical user interface (GUI):<br>This argument overrides all other arguments. |
| `-i, -indent` | `I` | `4` | Number of spaces to indent Task If/Then/Else Actions (default = 4) |
| `-names` | `{bold,highlight,underline,italicize}` |  | Display all Projects/Profiles/Tasks/Scenes in bold, underlined, italicized and/or highlighted text.<br>Example: `names underline italicize` |
| `-o, -outline` |  |  | Display configuration outline of Projects, Profiles, Tasks and Scenes, and<br>display the configuraion Map (MapTasker_map.txt) in the default text editor" |
| `-outdir` | `OUTDIR` |  | Folder to write reports, exports and the Map/Diagram files to<br>(default = a MapTasker folder in your Documents folder).<br>Example: `-outdir ~/MapTasker_Reports` |
| `-preferences` |  |  | Display Tasker preferences |
| `-pretty` |  |  | Make output prettier (one argument/parameter per line) |
| `-project` | `PROJECT` |  | Display the details for a specific Project only.<br>_Use only one of:_ `-project`, `-profile`, `-task`, `-scene` |
| `-profile` | `PROFILE` |  | Display the details for a specific Profile only.<br>_Use only one of:_ `-profile`, `-project`, `-task`, `-scene` |
| `-task` | `TASK` |  | Display the details for a single Task only (forces minimum of "-detail 3").<br>_Use only one of:_ `-task`, `-project`, `-profile`, `-scene` |
| `-scene` | `SCENE` |  | Display the details for a single Scene only (forces minimum of "-detail 3").<br>_Use only one of:_ `-scene`, `-project`, `-profile`, `-task` |
| `-reset` |  |  | Reset previously saved arguments...start fresh. |
| `-runtime` |  |  | Display all runtime arguments/settings at the top of the output. |
| `-taskernet` |  |  | Display any TaskerNet information for Projects/Profiles. |
| `-twisty` |  |  | Hide Task's details under 'twisty' ➤. Click on twisty to display details.<br>_Use only one of:_ `-twisty`, `-e` |
| `-v, -version` |  |  | Display the program version and license information. |

## Fetching the backup from an Android device

The three `-android_` options go together: give all of them or none.  They fetch the backup from the device's Tasker HTTP server instead of reading a file with `-file`.

| Option | Value | Default | What it does |
| --- | --- | --- | --- |
| `-android_ipaddr` | `ANDROID_IPADDR` |  | TCP/IP Address of Android device running Tasker server<br>Example: `-android_ipaddr 192.168.0.210`<br>Also requires -android_port and -android_file arguments |
| `-android_port` | `ANDROID_PORT` |  | Port number of Android device running Tasker server<br>Example: `-android_port 1821`<br>Also requires -android_ipaddr and -android_file arguments |
| `-android_file` | `ANDROID_FILE` |  | File location of Tasker backup file on Android device<br>Example: `-a-android_file /Tasker/configs/user/backup.xml`<br>Also requires -android_ipaddr and -android_port arguments |

## Output color options

Each takes a color name (`-ch` lists the valid ones) or a hex value, as in `-cTask Green -cBackground Black -cProfile 19c8ff`.

| Option | Value | Default | What it does |
| --- | --- | --- | --- |
| `-cProject` | `CPROJECT` |  | Provide a valid color for Projects.  Example: -cProject Blue |
| `-cProfile` | `CPROFILE` |  | Provide a valid color for Profiles.  Example: -cProfile Blue |
| `-cTask` | `CTASK` |  | Provide a valid color for Tasks.  Example: -cTask Blue |
| `-cAction` | `CACTION` |  | Provide a valid color for Task 'actions'.  Example: -cAction Blue |
| `-cDisabledProfile` | `CDISABLEDPROFILE` |  | Provide a valid color for 'disabled' Profiles.  Example: -cDisabledProfile Blue |
| `-cUnnamedTask` | `CUNNAMEDTASK` |  | Provide a valid color for 'unnamed' Tasks.  Example: -cUnnamedTask Blue |
| `-cDisabledAction` | `CDISABLEDACTION` |  | Provide a valid color for disabled Task 'actions'.  Example: -cDisabledAction Blue |
| `-cActionCondition` | `CACTIONCONDITION` |  | Provide a valid color for Task action 'conditions'.  Example: -cActionCondition Blue |
| `-cProfileCondition` | `CPROFILECONDITION` |  | Provide a valid color for Profile 'conditions'.  Example: -cProfileCondition Blue |
| `-cLauncherTask` | `CLAUNCHERTASK` |  | Provide a valid color for Project's 'launcher' Task.  Example: -cLauncherTask Blue |
| `-cBackground` | `CBACKGROUND` |  | Provide a valid color for output background.  Example: -cBackground Blue |
| `-cScene` | `CSCENE` |  | Provide a valid color for Scenes.  Example: -cScene Blue |
| `-cActionLabel` | `CACTIONLABEL` |  | Provide a valid color for Task action 'labels'.  Example: -cActionLabel Blue |
| `-cActionName` | `CACTIONNAME` |  | Provide a valid color for Task action 'names'.  Example: -cActionName Blue |
| `-cTaskerNetInfo` | `CTASKERNETINFO` |  | Provide a valid color for TaskerNet 'information'.  Example: -cTaskerNetInfo Blue |
| `-cPreferences` | `CPREFERENCES` |  | Provide a valid color for Tasker 'preferences'.  Example: -cPreferences Blue |
| `-cTrailingComments` | `CTRAILINGCOMMENTS` |  | Provide a valid color for Trailing Comments.  Example: -cTrailingComments Blue |
| `-cHighlight` | `CHIGHLIGHT` |  | Provide a valid color for Highlight.  Example: -cHighlight Blue |
| `-cHeading` | `CHEADING` |  | Provide a valid color for Heading.  Example: -cHeading Blue |
| `-ch, -colorhelp` |  |  | Display a list of valid color names. |

## Reports with no window

These run a report from the command line and write it to standard output; everything else goes to standard error.  Name one report, then any of the options after it.  `maptasker -healthcheck -h` shows just these options.

### Choose one report

Exactly one of these is required.

| Option | Value | Default | What it does |
| --- | --- | --- | --- |
| `-healthcheck` |  |  | scan a backup for problems |
| `-compare` | `OLDER NEWER` |  | show what differs between two backups (which is older is settled by the files' dates) |
| `-changes_since` | `PERIOD` |  | show what changed since PERIOD: today, week, month, all, a date (YYYY-MM-DD) or Nd (e.g. 3d) |
| `-trend` |  |  | show whether the configuration is getting healthier or messier over the history (see -file, -project); exits 10 if the newest backup made it messier |
| `-export` | `{map,diagram}` |  | write the Map or the Diagram as a file (see -format), and print its path |
| `-watch` | `FOLDER` |  | record each new backup that appears in FOLDER in the history, until stopped |

### Options for the reports

Where an option is for one report only, its description says which.

| Option | Value | Default | What it does |
| --- | --- | --- | --- |
| `-file` | `FILE` |  | the Tasker backup to use: a file, or a folder to use the newest .xml in (-trend: only its name is used, to follow the backups of that file) |
| `-project` | `PROJECT` |  | -trend: look at this Project alone, not the whole configuration |
| `-outdir` | `OUTDIR` |  | the folder to write files into (see -save and -export) |
| `-history_dir` | `HISTORY_DIR` |  | the folder holding the history, if not MapTasker_Timeline here |
| `-save` |  |  | also save the report as a file, as the window does |
| `-fail_on` | `{error,warning,never}` | `error` | -healthcheck: which findings exit with 10 (default: error) |
| `-format` | `{md,json,pdf}` | `md` | -export: the format to write (default: md) |
| `-detail` | `{0,1,2,3,4,5}` |  | -export: the level of detail to build the Map at |
| `-interval` | `INTERVAL` | `60` | -watch: seconds between looks at the folder |
| `-once` |  |  | -watch: look once and stop (for a scheduled job) |

## Exit codes

What MapTasker exits with, so a script can tell what happened.

```text
Exit codes...
    exit 1- program error
    exit 2- output file failure
    exit 3- file selected is not a valid Tasker backup file
    exit 5- requested single Task not found
    exit 6- no or improper filename selected
    exit 7- invalid option
    exit 8- request to Android device running server failed.  See output for error code.
    exit 10- a command-line report found something (see below)
    exit 11- -changes_since or -trend had no earlier configuration to compare against
```

The reports above use these as well:

```text
The report is written to standard output; everything else goes to standard error.
Exit codes: 0 done, nothing to report; 10 the report found something (problems, or
differences, or -trend: the newest backup is messier); 11 Changes Since or -trend had
no earlier configuration to compare against;
1 program error; 2 a file could not be written; 3 not a valid Tasker backup;
6 no such file; 7 invalid option.
```
