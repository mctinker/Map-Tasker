# MapTasker version 4.0
## Display the Tasker Project/Profile/Task/Scene hierarchy on a MAC based on Tasker's backup.xml

This is an application in support of Tasker that is intended to run on a MAC.
 
I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, so I wrote a Python program for my MAC to provide an indented list of my entire configuration based on my Tasker backup XML file that I save to my Google Drive.
 
A portion/example of the results can be found at https://imgur.com/a/KIR7Vep
 
Program dependencies:
-	Python version 3 (v3.9 or higher preferrably)
-	easygui: 
  install from Terminal using the command: ```pip3 install --upgrade easygui```
-	python-tk@3.9: 
  brew install python-tk@3.9
-	input Tasker backup.xml (anyname.xml…you will be prompted to locate and identify your Tasker backup xml file) on your MAC, created by Tasker version 5 or version 6. 

To run the program from the directory in which MapTasker.py resides, enter: ```python3 MapTasker.py```
 
Program out: the file “MapTasker.html”, which can will be opened in your default browser as a new tab.  
 
I have only been able to test this on my own backup file. If you try it out and find an error and are willing to share your backup.xml file, please send a copy to mikrubin@gmail.com 
 
If you make changes and think they may benefit others, feel free to forward them to me, at the above email address, for inclusion.
 
While not tested, I don't see why this shouldn't work on Windows or Linux.
 
Runtime: python3 MapTasker.py -option1 -option2 ...
 
Runtime options: -h for help, -l for linear output rather than list, -d0 for silent mode (no Action details), -d1 to display Action list if Task is unnamed or anonymous (default), -d2 to display Action list for all Tasks
 
Additonally, an optional OS X compiled version of this program has been provided via the dist.zip:
- download the dist.zip
- unzip dist.zip
- To run MapTAsker, simply double-click on /dist/MapTasker/Maptasker
 
Note: this has not been tested on other MACs and I would be interested in hearing feedback (mikrubin@gmail.com) as to whether or not this is working. 
 
  
Change list:
- Version 4.0
    - Added: indentation support for if/then sequences                                     
    - Fixed: Action "End For or Stop" is just "End For"                                    
    - Added: Support for more Task Action codes                                            
    - Added: Action numbers
    - Added: compiled distribution library                                                                
- Version 3.0 
    - Added: display label if found for Task action(s)                                     
    - Added: Display entry vs exit Task type                                               
    - Added: Support for many more Task Action codes                                                                                          
    - Added: Support for 3 levels of detail: none, unnamed Tasks only, all Tasks           
             Replaced argument -s with -d0 (no actions) and -d2 (all Task actions          
             Default is -d1: actions for unnamed/anonymous Tasks only                      
    - Fixed: Some Scenes with Long Tap were not capturing the Task                         
    - Fixed: Project with no Tasks was showing incorrect Project name                      
- Version 2.1:
    - Fixed: actions were not sorted properly
    - Fixed: Stop action improperly reported as Else action
    - Added: Support for more Task Action codes
- Version 2.0 Major rewrite:
    1- Added "-l" runtime option to display in a linear fashion
    2- Added detail mode, which displays the Task's actions for unnamed/anonymous Tasks
       (Use "-s" runtime option to not display this detail)
-	Version 1.2 Added -v and -h arguments to display the program version and help                  
-	Version 1.2 launch browser to display results                                                    
-	Version 1.1: Added list all Tasks not called by a Profile
