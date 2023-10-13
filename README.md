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
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[!["Buy Me A Coffee"](/documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

---
# MapTasker
## Display the Tasker Project/Profile/Task/Scene hierarchy on a MAC based on Tasker's backup.xml

This is an application in support of [Tasker](https://tasker.joaoapps.com/) that is intended to run on a MAC.
 
I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, so I wrote a Python program for my MAC to provide an indented list of my entire configuration based on my Tasker backup XML file that I save to my Google Drive.
 
A portion/example of the results can be found at https://imgur.com/a/KIR7Vep.
 
The Tasker backup xml can either be manually uploaded to your Mac/Google Drive, or this program can fetch it directly from your Android device.

### Program Dependencies
-	Python version v3.10 or higher and Tkinter (not included with Python 3.10 from 'brew')            


    python 3.10: `brew install python3.10`          
    Tkinter:     `brew install python-tk@3.10`           
     
-	Tasker full or partial backup.xml (anyname.xml…you will be prompted to locate and identify your Tasker backup xml file) on your MAC, created by Tasker version 5 or version 6. 


### Installation

- Make sure Python 3.10 or higher is installed on your MAC, along with Tkinter.    
- Install MapTasker by entering the following command into Terminal:    
 
     `pip3 install maptasker`        

- To install it into a virtual environment, enter the following command into Terminal:    

     `cd xxx`, where 'xxx' is a directory into which you want to set up the virtual environment    
     `python -m venv venv`    
     `set VIRTUAL_ENV {directory path to 'xxx'}/venv`    
     `source {directory path to 'xxx'}/venv/bin/activate`  
     `pip3 install maptasker` 
     
    
- To install it from GitHub, get the zip file by clicking on the ['Code'](https://github.com/mctinker/Map-Tasker) pull-down menu, select 'Download ZIP', save it into a new directory (e.g. /your_id/maptasker) and uncompress it into that directory.


### Usage 

- Ensure the dependencies are already installed.  Performing  `pip3 install maptasker` will automatically install the dependencies along with MapTasker. 
- If installed from Github, open a terminal window and change to the directory into which the zip file was uncompressed
- Enter the command:


     `maptasker (runtime options...se below)`
 
 See below for runtime options.
 
If running from the sourced GITHUB zip file, then do the following to run the program:

     `pip install -r requirements.txt`   ...one time only, to first install the prerequisites 
     `python main.py (runtime options...se below)`   ...to run Map-Tasker

Program out: the file “MapTasker.html” will be written to your runtime/current folder, which will be opened in your default browser as a new tab.
 
Runtime: `maptasker -option1 -option2` ...

### Runtime options 
 
    `-h` for help. 

    `-a` for appearance mode, one of system, light, dark.

    `-b ip_addr:port+file_location`  example: 192.168.0.210:8120+//Tasker/configs/user/backup.xml

        Get the backup file directly from the Android device (* = use default):   

        * For the "Get backup" option to work, you must have the following prerequisites: 
          1- Both the MAC and Android devices must be on the same network    
          2- The [sample Tasker Project](https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example)   must be installed and active on the Android device,  and the server must be running..see Android notification: "HTTP Server Info...".   
          3- See config.py to change the default settings permanently    

     `-conditions` to display a Profile's and Task's condition(s),    
    `-c(type) color_name`  define a specific color to 'type', where 'type' is *one* of the following:   

      'Project' 'Profile' 'Task' 'Action' 'DisabledProfile' 'UnknownTask'   
      'DisabledAction' 'ActionCondition' 'ProfileCondition' 'LauncherTask'   
      'Background' 'ActionLabel' 'Bullets' 'TaskerNetInfo', "Preferences',    
      "Heading', 'Highlight'    

      Example color options: -cTask Green -cBackground Black cProfile 19c8ff   

    `-ch` color help: display all valid colors",    
         
    `-detail 0` for silent mode: simple Project/Profile/Task/Scene names with no details,    
    `-detail 1` to display the Action list only if Task is unnamed or anonymous,   
    `-detail 2` to display Action list names for *all* Tasks,    
    `-detail 3` to display Action list names with *all* parameters for all Tasks (default),    
    `-detail 4` to display detail at level 3 plus all Project and unreferenced global variables,    
  
    `-directory` to display a directory of all Projects/Profiles/Tasks/Scenes,
    `-e` to display 'everything': Runtime settings, Tasker Preferences, Directory, Profile 'conditions', TaskerNet info and full Task (action) details with Project variables,    
    `-f` font to use (preferably a monospace font),   
    `-g` to get arguments from the GUI rather than via the command line,   
    `-i` the amount of indentation for If/Then/Else Task actions (default=4),   
    `-n {bold highlight italicize}` to add formatting options to Project/Profile/Task/Scene names,   
    `-o` to display the Configuration outline and output a map as MapTasker_map.txt  
    `-preferences` to display Tasker's preference settings,  
    `-restore` to restore previously saved runtime arguments,   
    `-runtime` to display the runtime arguments and their settings at the top of the output,       
    `-twisty` to display Task details hidden by a twisty "▶︎".  Click on twisty to reveal.   
    `-taskernet` to display any TaskerNet share details,  
    
    The following three arguments are mutually exclusive.  Use one only:   

    `-project 'name of the project'` to display a single Project, its Profiles and Tasks only,    
    `-profile 'profile name'` to display a single Profile and its Tasks only,    
    `-task 'task name'` to display a single Task only,  

    The following two arguments are exclusive.  Use one only:

    `-s`  save these settings for later reuse.    
    `-r` restores previously saved settings.  The restored settings override all other settings.
  

    Get the backup file directly from the Android device (*):

    `-b ip_addr:port+file_location`  example: 192.168.0.210:8120+//Tasker/configs/user/backup.xml

        * For the "Get backup" option to work, you must have the following prerequisites:
          1- Both the MAC and Android devices must be on the same network
          2- The [sample Tasker Project](https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example) must be installed and active on the Android device,  and the server must be running..see Android notification: "HTTP Server Info...".
          3- See config.py to change the default settings permanently

The MapTasker GUI:

<img src="/documentation_images/display_gui.png" width="800"/>

Sample output with runtime option '-detail 0':

<img src="/documentation_images/display_level-d0.png" width="800"/>

Sample output with runtime option '-detail 1':

<img src="/documentation_images/display_level-d1.png" width="800"/>

Sample output with runtime option '-detail 2':

<img src="/documentation_images/display_level-d2.png" width="800"/>

Sample output with runtime options '-detail 3 -conditions':

<img src="/documentation_images/display_level-d3.png" width="800"/>

Example runtime options: 
    
    'maptasker -detail 3 -conditions -taskernet -s'
        (show full detail including Profile/Task 'conditions' and TaskerNet 
         information, and save the settings)

Example using the GUI: 
    
    'maptasker -g'

Example fetching backup file directly from your Android device: 
    
    'maptasker -b 192.168.0.210:1821+/Tasker/configs/user/backup.xml'

Alternatively, see *config.py* for some user-customizable options.  Make user-specific changes in this file and save it rather than specifying them as arguments or via the GUI.


### To Do List (in no particular order)
  
[] Include/map remaining Tasker preferences    
[] Support additional plugins   
[] Improve Configuration Map: include Tasks not associtaed with any Profile   
[] Improve Configuration Map: include pointer to Tasks to which there is a Perform Task action.

### Contributions:
[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)   
[©Connor Talbot 2021](https://github.com/con-dog/clippy)   

<a href="https://www.buymeacoffee.com/mctinker"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=mctinker&button_colour=FFDD00&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=ffffff" /></a>