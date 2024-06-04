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

## Display the Tasker Project/Profile/Task/Scene hierarchy on a PC/MAC/LINUX machine based on Tasker's backup or exported XML file.

This is an application in support of [Tasker](https://tasker.joaoapps.com/) that is intended to run on a desktop running Windows, OS X or Linux (see [Note 1](#1)).

I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, my phone was too small to navigate over my Projects, Profiles, Tasks and Scenes.  So I wrote a Python program for my MAC to provide an indented list of my entire configuration based on my Tasker backup XML file that I saved to my Google Drive.

The Tasker backup or exported XML can either be manually uploaded to your PC/Mac/Linux/cloud-drive, or this program can fetch it directly from your Android device (see [Note 2](#2)).

### Features
 
 > Display everything from a summary overview to a very detailed level of your Tasker configuration.
 
 > Display just a single Project, Profile, or Task.
 
 > Include/exclude Profile and Task conditions: States, Events, etc.
 
 > Just stream everything or make the output "pretty" by aligning all of the fields.
 
 > Change the appearance: light, dark or use the system default.
 
 > Output using your favorite monospaced font, and accent Project, Profile and Task names by making them italicized, bold, highlighted and/or underscored.
 
 > Modify the colors associated with various aspects of the output to suit your mood.
 
 > Include TaskerNet descriptions and/or Tasker preferences.
 
 > For complex configurations, optionally include a dictionary of hot-links to your Projects, Profiles, Tasks and Scenes.
 
 > Display a diagram of your entire Tasker configuration.
 
 > Command line or GUI interface.
 
 > Use exported XML or fetch the XML directly from your Android device for the configuration mapping.
 
 > Save and restore commonly used runtime settings.
 
 > Ai Analysis option to analyze a specific Project, Profile or Task using either the server-based ChatGPT or the local-based Llama-ollama supported models.**
 
 > Tree view of Projects and their Profiles, Tasks and Scenes.**
 
 > Automatic update detection and optional installation.**

&nbsp;&nbsp;** Available via the GUI only.

### Program Dependencies

#### - Python version v3.11 (see [Note 4](#4)) or higher and Tkinter 8.6 or higher.

#### - Tasker full or partial backup or exported XML file.

&nbsp;&nbsp;-anyname-.xml: you will be prompted to locate and identify your Tasker backup/exported XML file (e.g. backup.xml) on your desktop, created by Tasker version 5 or version 6.  Optionally, this can be fetched directly from your Android device (see [Note 2](#2)).

#### - Ai Analysis
 
&nbsp;&nbsp;This requires a valid ChatGPT API key if using the server-based analysis, or the installation of ollama for local analysis (See [Note 5](#5)).


### Installation

- Install MapTasker by entering the following command into the Terminal:

     `pip install maptasker`

- To install it into a virtual environment, enter the following command into Terminal:

    - `cd xxx`, where 'xxx' is a directory into which you want to set up the virtual environment:
    -  `python -m venv venv`
    - `source {directory path to 'xxx'}/venv/bin/activate`
    - `pip install maptasker`

- To install it from GitHub: 
    - get the zip file by clicking on the ['Code'](https://github.com/mctinker/Map-Tasker) pull-down menu, 
    - select 'Download ZIP', 
    - save it into a new directory (e.g. /your_id/maptasker) and
    - uncompress it into that directory.
    - `pip install -r requirements.txt`   ...to first install the prerequisites


### Usage

- Enter the command:

     `maptasker -option1 -option2` ...

&nbsp;&nbsp;&nbsp;&nbsp;See below for runtime options.

- If running from the sourced GITHUB zip file, then do the following to run the program:

     `python main.py (runtime options...see below)`   ...to run Map-Tasker

Program output:
- The file “MapTasker.html” will be written to your runtime/current folder, which will be opened in your default browser as a new tab.
- If the "-outline" runtime option is used, then a textual diagram of the configuration is also written as "MapTasker_Map.txt" and will be displayed in your default text editor.  Ensure that text-wrap is off and a monospace font is used when viewing this map in the text editor.
- The runtime settings are saved in the file" MapTasker_Settings.toml".  You can modify this file but care should be taken not to change the field formats (e.g. change an integer to a text string).  Incorrect values will be ignored.
- "MapTasker_Map.txt" will be written if you ran MapTasker with the '-outline' runtime option.
- "MapTasker_Analysis.txt" will be created if you run the Ai Analysis from the GUI, which holds the response from the analysis.
- "maptasker.log" trace log file used for program debugging only.
<br><br>

### [Runtime options](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)

### [Example runtime options](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)

### [Sample Output](https://github.com/mctinker/Map-Tasker/wiki#sample-output)


## Notes

### 1

Windows 11 has been tested and verified to work.  Limitations:
- The Edge web browser, though, closes as soon as it opens when invoked from this program.  Therefore, it is recommended to use any browser other than Edge.
- Notepad does not treat spacing correctly for the configuration diagram (MapTasker_Map.txt).  Install an app such as "Typepad" and set it as your default app for opening txt files.

### 2

For the "Get backup" (retrieve the Tasker XML file directly from your Android device) option to work, you must have the following prerequisites:

- Both the desktop and Android devices must be on the same network.

- The [sample Tasker Project](https://shorturl.at/bwCD4) must be installed and active on the Android device, and the server must be running (see Android notification: "HTTP Server Info...").  Make sure to run the "launch" Task and enter your Google Drive ID.

- The TaskerNet profile, [MapTasker List](https://shorturl.at/buvK6), must be imported into Tasker in order for the 'List XML Files' button to work.

- Once the XML has been retrieved from your Android device, it is not necessary to keep retrieving it unless it has changed since it is automatically saved on your desktop.

### 3

If having problems getting Tkinter to version 8.6, try the following:

- uninstall python
- brew install tcl-tk
- reinstall python

If still having Tkinter version problems, [refer to this StackOverflow post.](https://shorturl.at/iAIRX)

### 4

If you are unable to upgrade to Python version 3.11 or higher, an older version of MapTasker is still available for Python version 3.10, via the command:

	'pip install maptasker==2.6.3'

With this older version, you will not get the benefits offered by the newer version.  Refer to Changelog for details.

### 5

Ai analysis is available through the GUI only.  You can run an analysis using a single Profile or Task only.  Support is available for server-based OpenAi (chat-gpt) and local-based Llama.

The usage of llama models also requires that you manually install Ollama from [here](https://ollama.com/download) and you must run the application once to do the initial setup.  Then you can run an analysis via the GUI (see the "Analyze" tab).

## To-Do List (in no particular order)

- [x] Auto Update Feature

- [x] Fix output column alignment

- [x] Support Windows 11

- [x] Add a runtime option for more pretty output

- [x] Add Ai support to analyze Profiles and Tasks

- [x] Save and restore the Ai Analysis window location

- [ ] Include/map remaining Tasker preferences

- [ ] Support additional plugins

## Privacy Statement

No information whatsoever is captured and sent via the network to myself or any other third party, other than through the use of server-based Ai Analysis which will send your Project/Profile/Task to ChatGPT.

When reporting an error, you will most likely be asked to provide the output log file from the error and your XML file, both of which will be solely used to debug the program and then immediately deleted.

The only network traffic that occurs is if and when you retrieve the backup/exported XML file directly from your Android device on the same network, use of the ChatGPT analysis feature, and during the GUI startup to check the pypi.org server for updates to the program.


## Contributions

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 for Clippy](https://github.com/con-dog/clippy)

[Tom Schimansky for CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

[Akash Bora for CTkColorPicker](https://github.com/Akascape/CTkColorPicker)



<a href="https://www.buymeacoffee.com/mctinker"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=mctinker&button_colour=FFDD00&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=ffffff" /></a>