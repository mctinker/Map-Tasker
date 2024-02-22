<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./documentation_images/maptasker_logo_dark.png">
    <img src="./documentation_images/maptasker_logo_light.png">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - Downloads](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![Downloads](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![PyPI - License](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
<!-- [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai) -->
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[!["Buy Me A Coffee"](/documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

---

# MapTasker

## Display the Tasker Project/Profile/Task/Scene hierarchy on a PC/MAC/LINUX machine based on Tasker's backup.xml

This is an application in support of [Tasker](https://tasker.joaoapps.com/) that is intended to run on a desktop running Windows, MOS X or Linux <sup>1</sup>.
I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, so I wrote a Python program for my MAC to provide an indented list of my entire configuration based on my Tasker backup XML file that I saved to my Google Drive.

A portion/example of the results can be found at https://imgur.com/a/KIR7Vep.

The Tasker backup XML can either be manually uploaded to your Mac/Google Drive, or this program can fetch it directly from your Android device.

### Program Dependencies

#### - Python version v3.11 or higher <sup>4</sup> and Tkinter 8.6 or higher, using one of these methods...

##### Install Python directly from python.org (includes Tkinter).

##### Install Python using "pyenv" on macOS:

    `pyenv install 3.11`  (includes Tkinter)
    `pyenv local 3.11`

##### Install Python via Homebrew on macOS:

    python 3.11: `brew install python3.11`
    Tkinter 8.6: `brew install tcl-tk` <sup>3</sup>

#### - Tasker full or partial backup.xml

(anyname.xml…you will be prompted to locate and identify your Tasker backup xml file) on your MAC, created by Tasker version 5 or version 6.  Optionally <sup>2</sup>, this can be fetched directly from your Android device.


### Installation

- Install MapTasker by entering the following command into the Terminal:

     `pip3 install maptasker`

- To install it into a virtual environment, enter the following command into Terminal:

    - `cd xxx`, where 'xxx' is a directory into which you want to set up the virtual environment:
    -  `python -m venv venv`
    - `set VIRTUAL_ENV {directory path to 'xxx'}/venv`
    - `source {directory path to 'xxx'}/venv/bin/activate`
    - `pip3 install maptasker`

- To install it from GitHub, get the zip file by clicking on the ['Code'](https://github.com/mctinker/Map-Tasker) pull-down menu, select 'Download ZIP', save it into a new directory (e.g. /your_id/maptasker) and uncompress it into that directory.


### Usage

- Enter the command:

     `maptasker (runtime options...se below)`

 See below for runtime options.

- If running from the sourced GITHUB zip file, then do the following to run the program:

     `pip install -r requirements.txt`   ...one time only, to first install the prerequisites

     `python main.py (runtime options...se below)`   ...to run Map-Tasker

Program output:
- The file “MapTasker.html” will be written to your runtime/current folder, which will be opened in your default browser as a new tab.
- If the "-outline" runtime option is used, then a textual diagram of the configuration is also written as "MapTasker_Map.txt" and will be displayed in your default text editor.  Ensure that text-wrap is off and a monospace font is used when viewing this map in the text editor.
- The runtime settings are saved in the file" MapTasker_Settings.toml".  You can modify this file but care should be taken not to change the field formats (e.g. change an integer to a text string).  Incorrect values will be ignored.

Runtime: `maptasker -option1 -option2` ...

### Runtime options (only available if not using the GUI)

    `-h` for help.

    `-android_ipaddr` TCP/IP address of the Android device from which to fetch the backup file.<sup>2</sup>
    Example: 192.168.0.210

    `-android_port` the port number of the Android device from which to fetch the backup file.
    Example: 1821

    `-android_file` the location of the backup XML file on the Android device.
    Example: /Tasker/configs/user/backup.xml

    The above three 'android' options are mutually inclusive.

    `-appearance` for appearance mode, one of system, light, dark.

    `-conditions` to display a Profile's and Task's condition(s),

    `-c(type) color_name` defines a specific color to 'type', where 'type' is *one* of the following:

      'Project' 'Profile' 'Task' 'Action' 'DisabledProfile' 'UnknownTask'
      'DisabledAction' 'ActionCondition' 'ProfileCondition' 'LauncherTask'
      'Background' 'ActionLabel' 'Bullets' 'TaskerNetInfo', "Preferences',
      "Heading', 'Highlight'

        Example color options: -cTask Green -cBackground Black cProfile 19c8ff

    `-ch` color help: display all valid colors",

    `-detail 0` for silent mode: simple Project/Profile/Task/Scene names with no details,
    `-detail 1` to display the Action list only if the Task is unnamed or anonymous,
    `-detail 2` to display Action list names for *all* Tasks,
    `-detail 3` to display Action list names with *all* parameters for all Tasks,
    `-detail 4` to display detail at level 3 plus all Project and unreferenced global variables (default),

    `-directory` to display a directory of all Projects/Profiles/Tasks/Scenes,
    `-e` to display 'everything': Runtime settings, Tasker Preferences, Directory, Profile 'conditions', TaskerNet info and full Task (action) details with Project variables,
    `-f` font to use (preferably a monospace font),  If "-f help" is entered, then the list of installed monospace fonts on your system will be printed out on the runtime console.
    `-g` to get arguments from the GUI rather than via the command line,
    `-i` the amount of indentation for If/Then/Else Task actions (default=4),
    `-n {bold highlight italicize}` to add formatting options to Project/Profile/Task/Scene names,
    `-o` to display the Configuration outline and output a map as MapTasker_map.txt
    `-preferences` to display Tasker's preference settings,
    `-reset` to ignore and reset the previously stored runtime arguments to default values,
    `-runtime` to display the runtime arguments and their settings at the top of the output,
    `-twisty` to display Task details hidden by a twisty "▶︎".  Click on twisty to reveal.
    `-taskernet` to display any TaskerNet share details,

    The following three arguments are mutually exclusive.  Use one only:

    `-project 'name of the project'` to display a single Project, its Profiles and Tasks only,
    `-profile 'profile name'` to display a single Profile and its Tasks only,
    `-task 'task name'` to display a single Task only,

    Get the backup file directly from the Android device<sup>2</sup>:



The MapTasker GUI:

<img src="/documentation_images/display_gui.png" width="800"/>

Sample output with runtime option '-everything':

<img src="/documentation_images/display_level-d4.png" width="800"/>

<!-- Sample output with runtime option '-detail 1':

<img src="/documentation_images/display_level-d1.png" width="800"/>

Sample output with runtime option '-detail 2':

<img src="/documentation_images/display_level-d2.png" width="800"/>

Sample output with runtime options '-detail 3 -conditions':

<img src="/documentation_images/display_level-d3.png" width="800"/> -->

 Sample Configuration Map from runtime option -outline:

<img src="/documentation_images/configuration_map.png" width="800"/>

Example runtime options:

    'maptasker -detail 2 -conditions -taskernet'
        (show limited details and include Profile and Task 'conditions' and TaskerNet details.)

Example using the GUI:

    'maptasker -g'

Example fetching backup file directly from your Android device:

    'maptasker -android_ipaddr=192.168.0.60 -android_port=1821 -android_file=/Tasker/configs/user/backup.xml'


## Notes

<sup>1</sup> Windows 11 has been tested and verified to work.  Limitations:
- The Edge web browser, though, closes as soon as it opens when invoked from this program.  Therefore, it is recommended to use any browser other than Edge.
- Notepad does not treat spacing correctly for the configuration diagram (MapTasker_Map.txt).  Install an app such as "Typepad" and set it as your default app for opening txt files.

<sup>2</sup> For the "Get backup" (retrieve backup.xml directly from your Android device) option to work, you must have the following prerequisites:


- Both the MAC and Android devices must be on the same network

- The [sample Tasker Project](https://shorturl.at/bwCD4) must be installed and active on the Android device, and the server must be running (see Android notification: "HTTP Server Info...").

- Once the backup has been retrieved from your Android device, it is not necessary to keep retrieving it unless it has changed since it is automatically saved on your Mac.

<sup>3</sup> If having problems getting Tkinter to version 8.6, try the following:

- uninstall python
- brew install tcl-tk
- reinstall python

If still having Tkinter version problems, [refer to this StackOverflow post.](https://shorturl.at/iAIRX)

<sup>4</sup>
If you are unable to upgrade to Python version 3.11 or higher, an older version of MapTasker is still available for Python version 3.10, via the command:

	'pip install maptasker==2.6.3'

With this older version, you will not get the benefits offered by the newer version.  Refer to Changelog for details.

## To-Do List (in no particular order)

- [x] Auto Update Feature

- [x] Fix output column alignment

- [x] Support Windows

- [ ] Include/map remaining Tasker preferences

- [ ] Support additional plugins

## Privacy Statement

No information whatsoever is captured and sent via the network to myself or any other third party.

 When reporting an error, you will most likely be asked to provide the output log file from the error and your backup XML file, both of which will be solely used to debug the program and then immediately deleted.

The only network traffic that occurs is if and when you retrieve the backup file directly from your Android device on the same network, and during the GUI startup to check the pypi.org server for updates to the program.


## Contributions

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 for Clippy](https://github.com/con-dog/clippy)

[Tom Schimansky for CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

[Akash Bora for CTkColorPicker](https://github.com/Akascape/CTkColorPicker)



<a href="https://www.buymeacoffee.com/mctinker"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=mctinker&button_colour=FFDD00&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=ffffff" /></a>