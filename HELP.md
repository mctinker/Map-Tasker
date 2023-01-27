## MapTasker Help

### Description
The purpose of this program is to display your Android device's Tasker configuration from Tasker's backup file, in a browser on your Mac.
 
The display includes Projects, Profiles, Tasks, Task actions, Scenes and other Profile and Task related information.
 
### Program Requirements
To run this program, you must have the following installed on your Mac:
* Python 3.10 or higher
  * If using the GUI interface, the following must also be installed   
    

      tkinter:        brew install python-tk@3.10
      customtkinter:  pip install customtkinter
      ctkcolorpicker: pip install CTkColorPicker
      PIL:            pip install pillow      

      
* A copy of your Tasker backup file (xml), uploaded from your Android device to your Mac.
### Pre-run Configuration
The majority of the runtime options can be selected at runtime.  Or if you so choose, you can modify the file:    

    config.py

...to make your changes more permanent.
 
Additionally, if you wish to use the GUI rather than the CLI (Command Line Interface) for options selection, then you can enable the GUI in one of two ways:    

1. in the file, config.py, set the variable GUI to True.    

   ...or...   

2. from terminal, run: 'python3.10 maptasker.py -g'

### Runtime Options
There are a number of runtime options in which you can change what is displayed.
* Level of detail to display, from cursory (level 0) to very detailed (level 3)
* Whether to display Profile and Task "conditions"
* Display only a specific Project, Profile or Task (by name)
* Display colors for the various components of the output
* Debug mode: creates additional information in the output log file. Note: the backup file must be named "backup.xml" for debug mode to work.     

    
** If running from the command line, then the runtime options are:    

    -h  for this help...overrides all other options 

    -d0  display all with first Task action only, for unnamed Tasks only (silent)
    -d1  display all Task action details for unknown Tasks only (default)
    -d2  display all Task action names only
    -d3  display full Task action details (parameters) on every Task

    -e   display everything: Profile 'conditions', all Tasks and their actions in detail.
    -g   Use the built-in GUI to input the program arguments/options
    
    -project='a valid Project name'  display the details for a single Project, its Profiles and its Task only
    -profile='a valid Profile name'  display the details for a single Profile and its Task only
    -task='a valid Task name'  display the details for a single Task only (automatically sets -d option to -d2)
    
    -profcon  display the condition(s) for Profiles
    
    -v  for this program's version
    
    -c(type)=color_name  define a specific color to 'type', where type is one of the following...
                 Project Profile Task Action DisableProfile UnknownTask DisabledAction ActionCondition ActionName
                 ProfileCondition LauncherTask Background    

      Example options: -cTask=Green -cBackground=Black
    
    -ch  color help: display all valid color names"

### Exit Codes
    exit 1- program error
    exit 2- output file failure
    exit 3- file selected is not a valid Tasker backup file
    exit 5- requested single Task not found
    exit 6- no or improper filename selected
    exit 7- invalid runtime option
    exit 8- unexpected xml error (report this as a bug)