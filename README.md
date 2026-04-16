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

## Display the Tasker Project/Profile/Task/Scene hierarchy on a PC/MAC/LINUX/WIN11 machine based on Tasker's backup or exported XML file

Configuration Map...
![](https://github.com/mctinker/Map-Tasker/blob/Master/documentation_images/intro.png)

Diagram Map...
![](https://github.com/mctinker/Map-Tasker/blob/Master/documentation_images/Introd.png)

[[More Samples]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

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
- Save and restore runtime settings.
- Identify Tasks that have too many 'actions', and which should potentially be broken up into multiple Tasks.
- Ai Analysis option to analyze a specific Project, Profile or Task using either the server-based ChatGPT/Claude/DeepSeek/Gemini or the local-based Llama (via Ollama) supported models. *
- Display results directly within the GUI: (Configuration) Map View, Tree View, and Diagram View. *
- Automatic update detection and optional installation of new versions. *
- Enhanced search capabilities. *

&nbsp;&nbsp;&nbsp;&nbsp;* Available via the GUI only.

## Program Dependencies

### - Python version 3.11 (see [Note 4](#4)) or higher

### - TKinter 8.6 or higher (see [Note 3](#3))

### - Tasker full or partial XML file: backup.xml or other Tasker exported XML file

### - Optional 'ffmpeg' for inline Youtube video hotlinks (see [Note 6](#6))

&nbsp;&nbsp;&nbsp;You will be prompted to locate and identify your Tasker exported XML file (e.g. backup.xml) on your desktop, created by Tasker version 5 or version 6.  Optionally, you can retrieve it directly from your Android device (see [Note 2](#2)).

### - Ai Analysis

&nbsp;&nbsp;&nbsp;This requires a valid API key if using the server-based analysis and/or Ollama to be installed for local analysis  (See [Note 5](#5)).

## Project Structure

A brief overview of the main files and their purpose:

- `maptasker/`: Contains the core application code.
  - `maptasker/src/`: The main Python source files for MapTasker's logic.
  - `maptasker/assets/`: Static assets like icons, images, and JSON data used by the application.
  - `maptasker/custom_overrides/`: Contains custom modifications to third-party libraries.
  - `maptasker/locale`: language files for translations.
- `documentation_images/`: Images used within this README and other documentation.
- `tests/`: Contains test scripts and related files for ensuring code quality.
- `main.py`: The main entry point script for running MapTasker from a cloned repository.
- `LICENSE`: The MIT License file for the project.
- `README.md`: This file.
- `Changelog.md`: A log of changes made in each version.
- `pyproject.toml`: Project metadata and build system configuration.

## Installation

This program and all of it's perquisites will take about 230MBs of space.  It is recommended that you install it into a virtual environment (option 2).

- Install MapTasker by entering one of the following commands into the Terminal/Command Prompt:

     ```python -m pip install maptasker -U```
                 ...OR...
     ```uv add maptasker```

- To install it into a virtual environment, enter the following command into Terminal/command prompt:

  via pip...
  - `cd xxx`, where 'xxx' is a directory into which you want to set up the virtual environment.
  - `python -m venv venv`
  - Activate the virtual environment...
    MAC/linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `.venv\Scripts\activate`
  - `pip install maptasker`

  ...or...
  
  via uv...
  - `cd xxx`, where 'xxx' is a directory into which you want to set up the virtual environment.
  - `uv venv`
  - Activate the virtual environment...
    MAC/linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `.venv\Scripts\activate`
  - `uv pip install maptasker`
  
## Usage

- Enter the command:

     ```maptasker -option1 -option2```
     ...or...
     ```uv run maptasker -option1 -option2```

     &nbsp;See below for runtime options.

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

- hidden files: system settings, run counter, and API keys.

## More: [[Runtime Options]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Runtime Option Examples]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Sample Output]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## License

This project is licensed under the [MIT License](./LICENSE).

The MIT License is a permissive free software license originating at the Massachusetts Institute of Technology (MIT). As a permissive license, it puts only very limited restriction on reuse and has, therefore, high license compatibility.

In brief, this means you are free to:

- **Use**: Use the software for any purpose (commercial or private).
- **Modify**: Modify the software.
- **Distribute**: Distribute the original or modified software.
- **Sublicense**: Sublicense the software.

You must:

- **Include Copyright**: Include the original copyright notice and the license itself in any substantial portions of the software.

The software is provided "AS IS", without warranty of any kind. For the full license text, please see the [LICENSE](./LICENSE) file.

## Troubleshooting and FAQ

**Q: I'm having trouble with Tkinter versioning, especially on macOS with Brew.**

A: Tkinter 8.6 or higher is required.

    - The simplest solution is often to use the [standard Python release download](https://www.python.org) which usually includes a compatible Tcl/Tk.
    - To check your Tkinter version, run: `python -m tkinter`
    - If using Brew and encountering issues:
        - You might need to uninstall Python, install `tcl-tk@8` via Brew, and then reinstall Python.
        - For `pyenv` users:
            - Python 3.11 may need `tcl-tk@8`. Commands: `brew uninstall tcl-tk`, `pyenv uninstall 3.11.xx`, `brew install tcl-tk@8`, `pyenv install 3.11:latest`.
            - Python 3.12 should be upgraded to the latest 3.12.x: `pyenv install 3.12:latest`.
            - Python 3.13 generally works with newer Tcl/Tk versions.
    - The "Notes" section of this README contains further details, particularly regarding Tkinter installation complexities.

**Q: The `MapTasker_Map.txt` diagram looks misaligned in Notepad on Windows.**

A: Notepad may not handle spacing correctly for this file.

It's recommended to use a different text editor like Notepad++, VS Code, or Typepad (and set it as your default for `.txt` files). Ensure 'text-wrap' is off and a monospace font is used.

**Q: How do I retrieve the Tasker XML file directly from my Android device?**

A: Prerequisites:

1- Desktop and Android device on the same local network.

2- The ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) installed and active on the Android device, server running.

3- The [MapTasker List TaskerNet profile](https://shorturl.at/0MQrL) imported into Tasker for the 'List XML Files' button in the GUI.

Further details are available in the "Notes" section of this README.

**Q: I see the error message 'IMKClient Stall detected...' on macOS.**

A: This message can generally be ignored.

It's related to the input method kit on macOS and doesn't usually affect MapTasker's functionality.

**Q: The background color is incorrect in Firefox (light mode) if my system is in dark mode.**

A: This is a known issue with browser theme handling.

Try aligning your browser theme with your system theme or vice-versa.

**Q: Diagram connectors are misaligned for names in Chinese, Korean, or Japanese.**

A: This is a known issue related to font metrics for these languages in the diagramming library.

**Q: I can't upgrade to Python 3.11+. Can I still use MapTasker?**

A: Yes, an older version (2.6.3) is available for Python 3.10: `pip install maptasker==2.6.3`.

However, you will miss out on newer features and fixes. See the [Changelog](https://github.com/mctinker/Map-Tasker/blob/Master/Changelog.md) for details.

## Notes

Details for some of the points mentioned in the "Troubleshooting and FAQ" section are preserved here for additional context.

### 1
**Windows 11 Specifics:**

- Only WIndows 11 is supported.  Any earlier versions of Windows are not supported.
- For `MapTasker_Map.txt` display issues in Notepad, use an alternative text editor like Typepad and set it as default for `.txt` files.

### 2
**Direct XML Retrieval from Android:**

To retrieve the Tasker XML file directly:

- Ensure both desktop and Android devices are on the same local network.
- The ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) must be installed and active on the Android device, with the server running. Remember to run the "launch" Task and enter your Google Drive ID.
- The [MapTasker List TaskerNet profile](https://shorturl.at/0MQrL) must be imported into Tasker for the 'List XML Files' button in the GUI. You can [preview this app on TaskerNet](https://taskernet.com/?public&tags=maptasker,Utility&time=AllTime).
- Once retrieved, the XML is saved on your desktop and doesn't need constant re-fetching unless changed.

### 3
**Tkinter Installation:**

The most direct and simple solution for Tkinter compatibility is to get and use the [standard Python release download](https://www.python.org). If using package managers like Brew or version managers like `pyenv`, specific steps might be needed if Tkinter version issues (requiring 8.6+) arise:

- To determine your Tkinter version: `'python -m tkinter'`
- General Brew troubleshooting for Tkinter:
  - Uninstall Python.
  - `brew install tcl-tk@8`
  - Reinstall Python.
- For `pyenv` users with Tcl/Tk version 9 conflicts:
  - Python 3.11: `brew uninstall tcl-tk`, `pyenv uninstall 3.11.xx`, `brew install tcl-tk@8`, `pyenv install 3.11:latest`.
  - Python 3.12: Upgrade to the latest 3.12.x: `pyenv install 3.12:latest`.
  - Python 3.13: Generally compatible with Tcl/Tk version 9.
- If still having issues, [refer to this StackOverflow post.](https://shorturl.at/iAIRX)

### 4
**Older Python Versions:**

If you cannot use Python 3.11+, MapTasker version 2.6.3 is available for Python 3.10: `pip install maptasker==2.6.3`. This version will not have the latest features (see [Changelog](https://github.com/mctinker/Map-Tasker/blob/Master/Changelog.md)).

### 5
**AI Support**

Ai analysis is available through the GUI only. You can run an analysis using a single Project, Profile or Task only. Support is available for server-based OpenAi (ChatGPT) and local-based Llama models.

Llama based models are supported via [Ollama](https://ollama.com/), which you must manually download, install and run it once to set up the server on your desktop.



### 6
**Optional Addons:**
'ffmpeg' version 8 or highler can optionally be installed to make embedded YouTube videos clickable and to display them in a separate video-player window from within the Map view.  Other videos, such as those stored on Dropbox as 'mp4' files, are not affected and will display as a clickable hot-link.

The direct playing of YouTube videos is not supported on Windows due to a dependency issue.  Therefore, 'ffmpeg' is not required for Windows users.

The videos are identifiable via the text: '[▶️ VIDEO: some-youtube-url...]', and this text will be hot/clickable if ffmpeg is properly installed.

ffmpeg and all of its 92+ dependencies adds an additional 660 MBs to your installation (hard drive).

To install ffmpeg:
   MacOS: 'brew install ffmpeg'
   Linux: 'sudo apt update' and 'sudo apt install ffmpeg'
   Windows via Winget: 'winget install ffmpeg'
   Windows via Chocolatey: 'choco install ffmpeg'

Refer to [the ffmpeg download documentation](https://www.ffmpeg.org/download.html) for further details.

If ffmpeg is not installed, then '[▶️ VIDEO: some-youtube-url...]' will still appear, but will not be hot/clickable, and the video can not be displayed in a separate MapTasker window.

YouTube videos are downloaded to your local drive from which they are then played.  The bigger the video, the longer it will take to process the video.  Only YouTube videos with no audio or English audio will play under the current implementation.  Additional lanaguages will be supported in a future release.

MP4 videos are played directly from their source.

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

- [x] Add 'Search' and 'Word Wrap' to the Map view.

- [x] Add 'Search' to the Diagram view.

- [x] Identify Tasks with too many actions.

- [x] Support additional AI's

- [x] Fix minor formatting issues.

- [x] If Profile has no name, display the same name as that of Tasker

- [x] Properly handle Task anchors with embedded HTML

- [x] Multilingual Support

- [ ] Support additional plugins

- [ ] Map remaining Tasker preferences

## Privacy Statement

No information whatsoever is captured and sent via the network to myself or any other third party, other than that listed below (Network Traffic).

When reporting an error, you will most likely be asked to provide the output log file from the error and your XML file, both of which will be solely used to debug the program and then immediately deleted.

Network traffic is as follows:

- Local LAN traffic when fetching XML directly from your Android device.
- On startup, check against pypi.com to determine if a new release is available.
- Update the program from pypi.com (via 'pip) if 'Upgrade' is selected in the GUI.
- Read file 'maptasker_changelog.json' from '<https://github.com/mctinker/Map-Tasker>' if "What's New" is selected in the GUI.
- Use chatgpt.com when using AI analysis with any of the OpenAi models.  The output of MapTasker is sent to the server via the standard API call for analysis.  Likewise for Claude (Anthropic), Google (Gemini) and DeepSeek.
- New and updated local Ai models will be loaded from '<https://ollama.com/library>' when running the AI Analysis feature.
- Image and video sources as defined via the '<img src=https://...>' HTML tag in Task action labels and TaskerNet descriptions will be accessed.  Examples: imggur.com, Youtube, Dropbox, Google Drice, etc.

## Contributing

Contributions are welcome! Here are some ways you can contribute to MapTasker:

**Reporting Bugs:**

- If you find a bug, please open an issue on the [GitHub Issues page](https://github.com/mctinker/Map-Tasker/issues).
- Include as much detail as possible:
  - Steps to reproduce the bug.
  - Expected behavior and actual behavior.
  - Your operating system and Python version.
  - MapTasker version.
  - Relevant parts of your Tasker XML file (if applicable, and ensure no sensitive information is included).
  - The `maptasker.log` file if generated with the `-debug` option.

**Suggesting Enhancements:**

- Open an issue on GitHub, outlining your suggestion.
- Explain the use case and why this enhancement would be beneficial.

**Pull Requests:**

- If you'd like to contribute code:
    1. Fork the repository.
    2. Create a new branch for your feature or bug fix (e.g., `feature/new-output-format` or `fix/xml-parsing-error`).
    3. Make your changes.
    4. Ensure your code adheres to the Black code style (as indicated by the badge).
    5. Add tests for your changes in the `tests/` directory if applicable.
    6. Ensure all tests pass.
    7. Submit a pull request to the `Master` branch.

**Coding Style:**

- This project uses [Black](https://github.com/psf/black) for code formatting. Please ensure your contributions are formatted with Black.

We appreciate your help in making MapTasker better!

## Known Issues

- The background color may not be correct if using the Firefox browser in light mode if the system default is dark mode.
- Diagram connectors are misaligned if names are in Chinese, Korean or Japanese.
- Unable to change any colors in GUI if using UV to manage the application (this is an open UV bug).

## Contributions

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 for Clippy](https://github.com/con-dog/clippy)

[Tom Schimansky for CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

[Akash Bora for CTkColorPicker and XYFrame](https://github.com/Akascape/CTkColorPicker)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/), [DeepSeek AI](https://chat.deepseek.com/)

[Anonyo Noor for cria](https://github.com/leftmove/cria)

[!["Buy Me A Coffee"](/documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
