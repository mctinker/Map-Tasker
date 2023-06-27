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

- Install maptasker by entering the following command into Terminal:    
 

     `pip3 install maptasker`        

- To install it to a virtual environment, enter the following command into Terminal:    

     `cd xxx`, where 'xxx' is a directory into which you want to setup the virtual environment    
     `python -m venv venv`    
     `set VIRTUAL_ENV {directory path to 'xxx'}/venv`    
     `source {directory path to 'xxx'}/venv/bin/activate`  
     `pip3 install maptasker` 
     
    
- To install it from GitHub, get the zip file by clicking on the ['Code'](https://github.com/mctinker/Map-Tasker) pull-down menu, select 'Download ZIP', save it into a new directory (e.g. /your_id/maptasker) and uncompress it into that directory.


### Usage 

- Ensure the dependencies are already installed.
- If installed from Github, open a terminal window and change to the directory into which the zip file was uncompressed
- Enter the command:


     `maptasker (runtime options...se below)`
 
 See below for runtime options.
 
If running from the sourced github zip file, then do the following to run the program:

     `pip install -r requirements.txt`   ...one time only, to first install the prerequisits 
     `python main.py (runtime options...se below)`   ...to run Map-Tasker

Program out: the file “MapTasker.html” will be written to your runtime/current folder, which will be opened in your default browser as a new tab.
 
Runtime: `maptasker -option1 -option2` ...

### Runtime options 
 
    `-h` for help.  Also refer to HELP.md for more details,  
    `-detail 0` for silent mode (no Action details except for first Action on unnamed Tasks),  
    `-detail 1` to display Action list only if Task is unnamed or anonymous (default),   
    `-detail 2` to display Action list names for *all* Tasks,    
    `-detail 3` to display Action list names with *all* parameters for all Tasks,    
    `-e` to display 'everything': Profile 'conditions', TaskerNet info and full Task (action) details    
    `-g` to get arguments from the GUI rather than via the command line,   
    
    The following three arguments are mutually exclusive.  Use one only:

    `-project 'name of project'` to display a single Project, its Profiles and Tasks only,    
    `-profile 'profile name'` to display a single Profile and its Tasks only,    
    `-task 'task name'` to display a single Task only (forces option -detail 3),   
        
        
    `-taskernet` to display any TaskerNet share details,  
    `-preferences` to display Tasker's preference settings,  
    `-conditions` to display a Profile's and Task's condition(s),

    `-c(type) color_name`  define a specific color to 'type', where 'type' is *one* of the following:

      'Project' 'Profile' 'Task' 'Action' 'DisabledProfile' 'UnknownTask' 
      'DisabledAction' 'ActionCondition' 'ProfileCondition' 'LauncherTask' 
      'Background' 'ActionLabel' 'Bullets' 'TaskerNetInfo', "Preferences'
                
      Example color options: -cTask Green -cBackground Black cProfile 19c8ff   

    `-ch` color help: display all valid colors".     

    The following two arguments are exclusive.  Use one only:

    `-s`  save these settings for later reuse.    
    `-r`  restore previously saved settings.

    `-t`  display Task/Scene details hidden by a twisty "▶︎".  Click on twisty to reveal.

    Get the backup file directly from the Android device (*):

    `-b ip_addr:port+file_location`  example: 192.168.0.210:8120+//Tasker/configs/user/backup.xml

        * For the "Get backup" option to work, you must have the following prequisites:
          1- Both the MAC and Android device must be on the same network
          2- The [sample Tasker Project](https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example) must be installed and active on the Android device,  and the server must be running..see Android notification: "HTTP Server Info...".
          3- See config.py to change the default settings permantely

The MapTasker GUI:

<img src="/documentation_images/display_gui.png" width="600"/>

Sample output with runtime option '-detail 0':

<img src="/documentation_images/display_level-d0.png" width="600"/>

Sample output with runtime option '-detail 1':

<img src="/documentation_images/display_level-d1.png" width="600"/>

Sample output with runtime option '-detail 2':

<img src="/documentation_images/display_level-d2.png" width="600"/>

Sample output with runtime options '-detail 3 -profcon':

<img src="/documentation_images/display_level-d3.png" width="600"/>

Example runtime options: 
    
    'maptasker -detail 3 -conditions -taskernet -s'
        (show full detail including Profile/Task 'conditions' and TaskerNet 
         information, and save the settings)

Example using GUI: 
    
    'maptasker -g'

Example fetching backup file directly from your Android device: 
    
    'maptasker -b 192.168.0.210:1821+/Tasker/configs/user/backup.xml'

Alternatively, see *config.py* for some user-customizable options.  Make user-specific changes in this file and save it rather than specifying them as arguments or via the GUI.


### To Do List (in no particular order)

[] Complete insertion of Python docstrings for programming etiquette

