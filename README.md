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
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - License](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
<!-- [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai) -->
[![Code style: ruff](https://img.shields.io/badge/code%20style-black-000000.svg)](https://docs.astral.sh/ruff/formatter/)
[!["Buy Me A Coffee"](/documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

---

# MapTasker

## Display/Edit/Analyze the Tasker Project(s), Profile(s), Task(s), and Scene(s) in your browser based on Tasker's backup or exported XML file

Configuration Map...
![](https://github.com/mctinker/Map-Tasker/blob/Master/documentation_images/intro.png)

Diagram Map...
![](https://github.com/mctinker/Map-Tasker/blob/Master/documentation_images/Introd.png)

[[More Samples]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

This is an application in support of [Tasker](https://tasker.joaoapps.com/) that is intended to run on in a web browser (see [Note 1](#1)).

I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, and my phone was too small to navigate over my Projects, Profiles, Tasks, and Scenes.  So I wrote a Python program to provide a complete map of my entire configuration in my web browser based on my Tasker backup XML file that I saved to my local desktop drive.

Over time, I refined the map by providing many additional options, including the ability to edit Tasker objects and provide in-depth analysis of the Tasker configuration.

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
- Ai Analysis option to analyze a specific Project, Profile, Task or Scene using either the server-based ChatGPT/Claude/DeepSeek/Gemini or the local-based Llama (via Ollama) supported models.
- Display results directly within the GUI: (Configuration) Map View, Tree View, and Diagram View.
- Automatic update detection and optional installation of new versions.
- Enhanced search capabilities.
- Structured 'Find' in the Map and Diagram views: ask for every Task performing a given action, every Profile a given trigger fires, or everything that references a given app or Scene, and get back a clickable list of the objects rather than highlighted text.
- Add and Edit Projects, Profiles, Tasks, and Scenes (see [Note 6](#6))
- Analyze the health of the Tasker XML as well as the numerous variables throughout the configuration.
- Compare an XML file against the loaded XML. 

## Program Dependencies

### - Python version 3.11 or higher

### - Tasker full or partial XML file: backup.xml or other Tasker exported XML file

&nbsp;&nbsp;&nbsp;You will be prompted to locate and identify your Tasker exported XML file (e.g. backup.xml) on your desktop, created by Tasker version 5 or version 6.  Optionally, you can retrieve it directly from your Android device (see [Note 2](#2)).

### - Ai Analysis

&nbsp;&nbsp;&nbsp;This requires a valid API key if using the server-based analysis and/or Ollama to be installed for local analysis  (See [Note 3](#3)).


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

     ```maptasker```
     ...or if using uv to manage the virtual environment...
     ```uv run maptasker```


## Program Output

- “MapTasker.html”

     This file will be written to your runtime/current folder, which will be opened in your default browser as a new tab.  It will contain the mapping of your Tasker configuration.

- “MapTasker_Map.txt”

     This file will be written to your runtime/current folder as a result of running with the runtime option '-outline'.  It will contain a textual diagram of the configuration.  It will be displayed in your default text editor.  Ensure that 'text-wrap' is off and a monospace font is used when viewing this map in the text editor.

- "MapTasker_Settings.toml"

     This file contains your saved program settings.  You can modify this file but care should be taken not to change the field formats (e.g. _do not_ change an integer to a text string).  Incorrect values will be ignored.

- "MapTasker_Analysis_date_time.txt"

     This file will be created if you run the Ai analysis from the GUI, which holds the response from the analysis.  It will be displayed in a separate window along with the GUI.

- MapTasker_HealthCheck_date_time.txt

	This is the output from the Health Check run.
	
- MapTasker_Compare_date_time.txt

	This is the output from the XML File Compare run.
	
- MapTasker_VarXref_date_time.txt

This is the output from the Variable Xref (cross reference) run.
	
- "maptasker.log"

  This is a trace log file used for program debugging and will only be created if '-debug' is specified in the runtime options.

- MapTasker_Backups_date_time directory

  Backups files from 'Export' or 'Save to Android', in which the file already existed and an overwrite would occur.

  - MapTasker_Find_date_time.txt and MapTasker_Replace_date_time.txt

  The saved results of the structured search, from the Map and Diagram views, via the 'Find' command, or of the Replace preview results.

- hidden files: system settings, run counter, last 'version checked' date, and API keys.

## More: [[Runtime Options]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[Runtime Option Examples]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[Sample Output]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

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

**Q: The `MapTasker_Map.txt` diagram looks misaligned in Notepad on Windows.**

A: Notepad may not handle spacing correctly for this file.

It's recommended to use a different text editor like Notepad++, VS Code, or Typepad (and set it as your default for `.txt` files). Ensure 'text-wrap' is off and a monospace font is used.

**Q: How do I retrieve the Tasker XML file directly from my Android device?**

A: Prerequisites:

1- Browser and Android device on the same local network.

2- The ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) installed and active on the Android device, server running.

3- The [MapTasker List TaskerNet profile](https://shorturl.at/0MQrL) imported into Tasker for the 'List XML Files' button in the GUI.

Further details are available in the "Notes" section of this README.

**Q: Diagram connectors are misaligned for names in Chinese, Korean, or Japanese.**

A: This is a known issue related to font metrics for these languages in the diagramming library.

**Q: Why are some Task actions and Profile states/events not available for edit/addition?

A: In some cases, these actions, events, or states require information that is only available on Android and/or within Tasker, itself.  Allowing an edit for these would result in an incomplete Task or Profile, causing a Tasker failure. 

## Notes

Details for some of the points mentioned in the "Troubleshooting and FAQ" section are preserved here for additional context.

### 1
**Windows 11 Specifics:**

- Only WIndows 11 is supported.  Any earlier versions of Windows are not supported.
- For `MapTasker_Map.txt` display issues in Notepad, use an alternative text editor like Typepad and set it as default for `.txt` files.

### 2
**Direct XML Retrieval from Android:**

To retrieve the Tasker XML file directly:

- Ensure both desktop and Android devices are on the same local network and that Tasker is running.
- The ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) must be installed and active on the Android device, with the server running. Remember to run the "Update GD HTTP Info" Task and (first time only) enter your Google Drive ID when prompted.
- The [MapTasker List TaskerNet profile](https://shorturl.at/0MQrL) must be imported into Tasker for the 'List XML Files' button in the GUI. You can [preview this app on TaskerNet](https://taskernet.com/?public&tags=maptasker,Utility&time=AllTime).
- Once retrieved, the XML is saved on your desktop and doesn't need constant re-fetching unless changed.

### 3
**AI Support**

Ai analysis is available through the GUI only. You can run an analysis using a single Project, Profile, Task, or Scene only. Support is available for server-based OpenAi (ChatGPT), Gemini, and Anthropic, as well as local-based Llama models.

Llama based models are supported via [Ollama](https://ollama.com/), which you must manually download, install and run it once to set up the server on your desktop.  MapTasker will dynamically load the Llama models for you if not already loaded.

The supporting AI modules are not installed by default when MapTasker is installed.  Instead, they are dynamically installed upon first-use of the specific AI request.  In this way, if you do not plan to use AI, then you do not incur the overhead.


## Application Editing and Analysis Caveats
**MapTasker Editing and Analysis Caveats**

Refer the the [Caveats](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt) document for details.


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

- [x] Edit Support

- [x] Health Checkup and Variable Cross-reference

- [x] Edit 'Undo/Redo' function

- [x] Structure Search

- [x] Interactive Diagram view

- [x] Find and Replace function

- [ ] Capture Android Device Apps and Icons

- [ ] Export Map to Portable Formats (Markdown / JSON / PDF)

- [ ] Export Edits Directly Into Tasker

- [ ] Roundtrip (Device-to/from Android) Data Validation

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

- This project uses [Ruff](https://docs.astral.sh/ruff/formatter/) for code formatting. Please ensure your contributions are formatted with Ruff.

We appreciate your help in making MapTasker better!

## Known Issues

- Diagram connectors are misaligned if names are in Chinese, Korean or Japanese.
- Not all Task actions and Profile state/event editing are supported, since some require information which is only available on an Android device.

## Contributions

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021 for Clippy](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/), [DeepSeek AI](https://chat.deepseek.com/)

[Anonyo Noor for cria](https://github.com/leftmove/cria)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](/documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
