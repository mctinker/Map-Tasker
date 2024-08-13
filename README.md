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
[![image](https://img.shields.io/pypi/pyversions/maptasker.svg)](https://pypi.python.org/pypi/maptasker)
![PyPI - License](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
<!-- [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai) -->
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[!["Buy Me A Coffee"](/documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

---

# MapTasker

## Display the Tasker Project/Profile/Task/Scene hierarchy on a PC/MAC/LINUX machine based on Tasker's backup or exported XML file

![](https://github.com/mctinker/Map-Tasker/blob/Master/documentation_images/intro.png)

This is an application in support of [Tasker](https://tasker.joaoapps.com/) that is intended to run on a desktop running Windows, OS X or Linux (see [Note 1](#1)).

I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, and my phone was too small to navigate over my Projects, Profiles, Tasks and Scenes.  So I wrote a Python program for my desktop to provide a complete map of my entire configuration based on my Tasker backup XML file that I saved to my local desktop drive.

Over time, I refined the map by providing many additional options.

The Tasker backup or other Tasker exported XML can either be manually uploaded to your PC/Mac/Linux/cloud drive, or this program can retrieve it directly from your Android device (see [Note 2](#2)).

## Features

- Your choice of output detail level, from a summary overview to a very detailed level of your configuration.
- Display just a single Project, Profile, or Task.
- Include/exclude Profile and Task conditions: States, Events, etc.
- Just stream everything and/or make the output "pretty" by aligning all of the fields.
- Change the appearance: select 'light', or 'dark' or use the 'system' default.
- Output using your favorite monospaced font, and accent Project, Profile and Task names by making them italicized, bold, highlighted and/or underscored.
- Modify the colors associated with various aspects of the output to suit your mood.
- Include TaskerNet descriptions and/or Tasker preferences.
- For complex configurations, optionally include a dictionary of hotlinks to your Projects, Profiles, Tasks and Scenes.
- Display a diagram of your entire Tasker configuration.
- Command line or GUI interface.
- Use exported XML or fetch the XML directly from your Android device for the configuration mapping.
- Save and restore commonly used runtime settings.
- Ai Analysis option to analyze a specific Project, Profile or Task using either the server-based ChatGPT or the local-based Llama (via Ollama) supported models.*
- Display results directly within the GUI: (Configuration) Map View, Tree View, and Diagram View.*
- Automatic update detection and optional installation of new versions.*

&nbsp;&nbsp;&nbsp;&nbsp;* Available via the GUI only.

## Program Dependencies

### - Python version v3.11 (see [Note 4](#4)) or higher and Tkinter 8.6 or higher

### - TKinter 8.6 or higher (see [Note 3](#3))

### - Tasker full or partial full backup or other exported Tasker XML file

&nbsp;&nbsp;You will be prompted to locate and identify your Tasker exported XML file (e.g. backup.xml) on your desktop, created by Tasker version 5 or version 6.  Optionally, you can retrieve it directly from your Android device (see [Note 2](#2)).

### - Ai Analysis

&nbsp;&nbsp;This requires a valid ChatGPT API key if using the server-based analysis  (See [Note 5](#5)).

## Installation

- Install MapTasker by entering the following command into the Terminal:

     ```python -m pip install maptasker -U```

- To install it into a virtual environment, enter the following command into Terminal:

  - `cd xxx`, where 'xxx' is a directory into which you want to set up the virtual environment:
  - `python -m venv venv`
  - `source {directory path to 'xxx'}/venv/bin/activate`
  - `pip install maptasker`

- To install it from GitHub:
  - get the zip file by clicking on the ['Code'](https://github.com/mctinker/Map-Tasker) pull-down menu,
  - select 'Download ZIP',
  - save it into a new directory (e.g. /your_id/maptasker) and
  - uncompress it into that directory.
  - `pip install -r requirements.txt`   ...to first install the prerequisites

## Usage

- Enter the command:

     ```maptasker -option1 -option2``` ...

     &nbsp;See below for runtime options.

- If running from the sourced GITHUB zip file, then do the following to run the program:

     ```python main.py -option1 -option2```   ...to run Map-Tasker

- Get started with the GUI:
    ```maptasker -g```

## Program Output

- “MapTasker.html”

     This file will be written to your runtime/current folder, which will be opened in your default browser as a new tab.  It will contain the mapping of your Tasker configuration.

- “MapTasker_Map.txt”

     This file will be written to your runtime/current folder as a result of running with the runtime option '-outline'.  It will contain a textual diagram of the configuration.  It will be displayed in your default text editor.  Ensure that 'text-wrap' is off and a monospace font is used when viewing this map in the text editor.

- "MapTasker_Settings.toml"

     This file contains your saved program settings.  You can modify this file but care should be taken not to change the field formats (e.g. _do not_ change an integer to a text string).  Incorrect values will be ignored.

- "MapTasker_Analysis.txt"

     This file will be created if you run the Ai analysis from the GUI, which holds the response from the analysis.  It will be displayed in a separate window along with the GUI.

- "maptasker.log"

     This is a trace log file used for program debugging and will only be created if '-debug' is specified in the runtime options.

## More: [[Runtime Options]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Runtime Option Examples]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Sample Output]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## License

This program is licensed under the [MIT License](https://opensource.org/license/mit).

## Notes

### 1

Windows 11 has been tested and verified to work.  Limitations:

- If a conflict arises during installation of 'psutil', then do the following:
  - 'pip uninstall psutil'
  - 'pip install psutil==5.9.8'
  - 'pip install maptasker'

- Notepad does not treat spacing correctly for the configuration diagram (MapTasker_Map.txt).  Install an app such as "Typepad" and set it as your default app for opening 'txt' files.

### 2

To retrieve the Tasker XML file directly from your Android device, you must have the following prerequisites:

- Both the desktop and Android devices must be on the same local network.

- The ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) must be installed and active on the Android device, and the server must be running (see Android notification: "HTTP Server Info...").  Make sure to run the "launch" Task and enter your Google Drive ID.

- The TaskerNet profile, [MapTasker List](https://shorturl.at/0MQrL), must be imported into Tasker for the 'List XML Files' button to work in the GUI.  You can also first [preview this app on TaskerNet](https://taskernet.com/?public&tags=maptasker,Utility&time=AllTime).

- Once the XML has been retrieved from your Android device, it is not necessary to keep retrieving it unless it has changed since it is automatically saved on your desktop.

### 3

To determine the version of Tkinter you are using, run the following command from Terminal:

     'python -m tkinter'

If having problems getting Tkinter to version 8.6, try the following:

- uninstall python
- 'brew install tcl-tk'
- reinstall python

If still having Tkinter version problems, [refer to this StackOverflow post.](https://shorturl.at/iAIRX)

### 4

If you are unable to upgrade to Python version 3.11 or higher, an older version of MapTasker is still available for Python version 3.10, via the command:

	'pip install maptasker==2.6.3'

With this older version, you will not get the benefits offered by the newer version.  Refer to [Changelog](https://github.com/mctinker/Map-Tasker/blob/Master/Changelog.md) for details.

### 5

Ai analysis is available through the GUI only.  You can run an analysis using a single Project, Profile or Task only.  Support is available for server-based OpenAi (ChatGPT) and local-based Llama models.

## To-Do List (in no particular order)

- [x] Auto Update Feature

- [x] Fix output column alignment

- [x] Support Windows 11

- [x] Add a runtime option for more pretty output

- [x] Add AI support to analyze Profiles and Tasks

- [x] Save and restore the AI analysis window location

- [x] Add color to the Map View in the GUI

- [x] Add name attributes (highlight, bold, italicize, underline) to the Map View in the GUI

- [x] Display progress bar for diagram view

- [ ] Support additional plugins

- [ ] Map remaining Tasker preferences

## Privacy Statement

No information whatsoever is captured and sent via the network to myself or any other third party, other than that listed below (Network Traffic).

When reporting an error, you will most likely be asked to provide the output log file from the error and your XML file, both of which will be solely used to debug the program and then immediately deleted.

Network traffic is as follows:

- Local LAN traffic when fetching XML directly from your Android device.
- On startup, check against pypi.com to determine if a new release is available.
- Update the program from pypi.com (via 'pip) if 'Upgrade' is selected in the GUI.
- Read file 'maptasker_changelog.json' from 'https://github.com/mctinker/Map-Tasker' if "What's New" is selected in the GUI.
- Use chatgpt.com when using AI analysis with any of the OpenAi models.
- New local Ai models will be loaded from 'https://ollama.com/library'.

## Known Issues

- Firefox doesn't recognize a light background (appearance is 'light').  Themes and the Firefox "Manage Colors" settings can mess this up.

## Contributions

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 for Clippy](https://github.com/con-dog/clippy)

[Tom Schimansky for CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

[Akash Bora for CTkColorPicker and XYFrame](https://github.com/Akascape/CTkColorPicker)

[Ollama](https://ollama.com/) and [OpenAi](https://openai.com/)



<a href="https://www.buymeacoffee.com/mctinker"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=mctinker&button_colour=FFDD00&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=ffffff" /></a>