# MapTasker
## Display the Tasker Project/Profile/Task/Scene hierarchy on a MAC based on Tasker's backup.xml

This is an application in support of Tasker (https://tasker.joaoapps.com/) that is intended to run on a MAC.
 
I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, so I wrote a Python program for my MAC to provide an indented list of my entire configuration based on my Tasker backup XML file that I save to my Google Drive.
 
A portion/example of the results can be found at https://imgur.com/a/KIR7Vep.
 
### Program dependencies:
-	Python version v3.10 or higher     


    brew install python3.10
    brew install python-tk@3.10
-	Tasker full or partial backup.xml (anyname.xml…you will be prompted to locate and identify your Tasker backup xml file) on your MAC, created by Tasker version 5 or version 6. 
-   If using the GUI, then these addition dependencies must be installed:    


    pip3 install customtkinter
    pip3 install ctkcolorpicker
    pip3 install pillow
    

### Installation

- From the GitHub 'Code' pull-down menu, select 'Download ZIP', save it into a new directory (e.g. /your_id/maptasker) and uncompress it into that directory.


### Usage 

- Ensure the dependencies are already installed.
- Open a terminal window and change to the directory into which the zip file was uncompressed
- From this directory, enter the command:


     `python3.10 maptasker.py` 
 
 (see below for runtime options)
 
Program out: the file “MapTasker.html” will be written to your runtime/current folder, which will be opened in your default browser as a new tab.
 
Runtime: `python3.10 maptasker.py -option1 -option2` ...
 
### Runtime options 
 
`-h` for help.  Also refer to HELP.md for more details,  
`-d0` for silent mode (no Action details except for first Action on unnamed Tasks),  
`-d1` to display Action list if Task onl is unnamed or anonymous (default),   
`-d2` to display Action list names for *all* Tasks,    
`-d3` to display Action list names with *all* parameters for all Tasks,    
`-e` to display 'everything': Profile 'conditions', TaskerNet info and full Task/Action details \n  
`-g` to get arguments from the GUI rather than via the command line,    
`-project='name of project'` to display a single Project, its Profiles and Tasks only,    
`-profile='profile name'` to display a single Profile and its Tasks only,    
`-task='task name'` to display a single Task only (forces option -d2),   
`-taskernet` to display any TaskerNet share details,    
`-profcon` to display a Profile's condition(s),   
`-c(type)=color_name`  define a specific color to 'type', where (type) is *one* of the following:
> Project Profile Task Action DisabledProfile UnknownTask DisabledAction ActionCondition ProfileCondition LauncherTask Background ActionLabel
            
    Example color options: -cTask=Green -cBackground=Black     
`-ch`  color help: display all valid colors". 

Sample output with runtime option '-d0':

<img src="/documentation_images/display_level-d0.png" width="400"/>

Sample output with runtime option '-d1':

<img src="/documentation_images/display_level-d1.png" width="400"/>

Sample output with runtime option '-d2':

<img src="/documentation_images/display_level-d2.png" width="400"/>

Sample output with runtime options '-d3 -profcon':

<img src="/documentation_images/display_level-d3.png" width="400"/>

    Example runtime options: 'python3.10 maptasker.py -d3 -profcon'

    Example using GUI: 'python3.10 maptasker.py -g'

Alternatively, see *config.py* for user-customizable options.  Make user-specific changes in this file and save it rather than specifying them as arguments or via the GUI.


### To Do List (in no particular order)
[] Catch up with recent Tasker changes in the 6.1.n code base

[] Optionally, display Task properties

[] Complete insertion of Python docstrings

[] Optionally, display Scene element details

[] Manage dependencies through Poetry
 
[] Package for pip

[] Save and restore program runtime settings