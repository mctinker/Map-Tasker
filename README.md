# MapTasker
## Display the Tasker Project/Profile/Task/Scene hierarchy on a MAC based on Tasker's backup.xml

This is an application in support of [Tasker](https://tasker.joaoapps.com/) that is intended to run on a MAC.
 
I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, so I wrote a Python program for my MAC to provide an indented list of my entire configuration based on my Tasker backup XML file that I save to my Google Drive.
 
A portion/example of the results can be found at https://imgur.com/a/KIR7Vep.
 
### Program Dependencies
-	Python version v3.10 or higher and Tkinter (not included with Python 3.10 from 'brew')            


    python 3.10: `brew install python3.10`          
    Tkinter:     `brew install python-tk@3.10`           
     
-	Tasker full or partial backup.xml (anyname.xml…you will be prompted to locate and identify your Tasker backup xml file) on your MAC, created by Tasker version 5 or version 6. 


### Installation

- Install maptasker by entering the following command into Terminal:    
 

     `pip install maptasker`          
    
- From the GitHub 'Code' pull-down menu, select 'Download ZIP', save it into a new directory (e.g. /your_id/maptasker) and uncompress it into that directory.


### Usage 

- Ensure the dependencies are already installed.
- Open a terminal window and change to the directory into which the zip file was uncompressed
- From this directory, enter the command:


     `maptasker (runtime options...se below)` 
 
 (see below for runtime options)
 
Program out: the file “MapTasker.html” will be written to your runtime/current folder, which will be opened in your default browser as a new tab.
 
Runtime: `maptasker -option1 -option2` ...

### Runtime options 
 
    `-h` for help.  Also refer to HELP.md for more details,  
    `-detail 0` for silent mode (no Action details except for first Action on unnamed Tasks),  
    `-detail 1` to display Action list if Task onl is unnamed or anonymous (default),   
    `-detail 2` to display Action list names for *all* Tasks,    
    `-detail 3` to display Action list names with *all* parameters for all Tasks,    
    `-e` to display 'everything': Profile 'conditions', TaskerNet info and full Task (action) details    
    `-g` to get arguments from the GUI rather than via the command line,   
    
    The following three arguments are exclusive.  Use one only:

    `-project 'name of project'` to display a single Project, its Profiles and Tasks only,    
    `-profile 'profile name'` to display a single Profile and its Tasks only,    
    `-task 'task name'` to display a single Task only (forces option -d2),   
        
        
    `-taskernet` to display any TaskerNet share details,    
    `-conditions` to display a Profile's and Task's condition(s),   
    `-c(type) color_name`  define a specific color to 'type', where 'type' is *one* of the following:

      'Project' 'Profile' 'Task' 'Action' 'DisabledProfile' 'UnknownTask' 
      'DisabledAction' 'ActionCondition' 'ProfileCondition' 'LauncherTask' 
      'Background' 'ActionLabel' 'Bullets' 'TaskerNetInfo'
                
      Example color options: -cTask Green -cBackground Black cProfile 19c8ff   

    `-ch` color help: display all valid colors".     

    The following two arguments are exclusive.  Use one only:

    `-s`  save these settings for later reuse.    
    `-r`  restore previously saved settings. 

Sample output with runtime option '-detail 0':

<img src="/documentation_images/display_level-d0.png" width="400"/>

Sample output with runtime option '-detail 1':

<img src="/documentation_images/display_level-d1.png" width="400"/>

Sample output with runtime option '-detail 2':

<img src="/documentation_images/display_level-d2.png" width="400"/>

Sample output with runtime options '-detail 3 -profcon':

<img src="/documentation_images/display_level-d3.png" width="400"/>

Example runtime options: 
    
    'maptasker -detail 3 -conditions -taskernet -s'
        (show full detail including Profile/Task 'conditions' and TaskerNet 
         information, and save the settings)

Example using GUI: 
    
    'maptasker -g'

Alternatively, see *config.py* for user-customizable options.  Make user-specific changes in this file and save it rather than specifying them as arguments or via the GUI.


### To Do List (in no particular order)
[] Catch up with recent Tasker changes in the 6.1.n code base

[] Optionally, display Task and Profile properties

[] Complete insertion of Python docstrings

[] Optionally, display Scene element details

[] Manage dependencies through Poetry

