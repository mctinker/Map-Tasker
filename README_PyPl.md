# MapTasker

## Display the Tasker Project/Profile/Task/Scene hierarchy on in your browser based on Tasker's backup or exported XML file (e.g. backup.xml)

This is an application in support of [Tasker](https://tasker.joaoapps.com/) that is intended to run in your default browser.

## Installation:

- via uv: `uv add maptasker`
- via pip: `pip install maptasker`
  
NOTE: If MapTasker doesn't install on Windows 11, first install 'nicegui' and then install MapTasker.
  
## Updating MapTasker:

MapTasker has a built-in auto-updater.  If a new version is available, a "New Version" button will appear allowing the user to install the new version and relaunch MapTasker.
If the auto-updater does not work, then use one of the following:
	
- via uv: `uv sync --upgrade-package maptasker`
- via pip: `pip install --upgrade maptasker`

The older desktop version is available if needed:

- via uv: `uv add maptasker==10.2.7`
- via pip: `pip install maptasker==10.2.7`

For further details, refer to [the project on Github.](https://github.com/mctinker/Map-Tasker)
