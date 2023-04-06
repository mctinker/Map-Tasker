MapTasker Change log
## [1.3.2] - 2023-04-06
### Added: Include Map-Tasker version in output title
### Changed: default color for Profile conditions
### Changed: eliminated colors in config.py...redundant
### Fixed: Bypass extra Task information if "Task not called by Profile" section
### Fixed: cleaned up improperly formatted output due to spurious HTML tag
### Fixed: incorrectly formatted HTML
### Fixed: Improved Taskernet description formatting
### Fixed: Spacing on indented If/For segments
### Added: Clearly identify Projects that have no Profiles

Older History Log 
- [1.3.1] - 2023-03-19
       - Added: GUI Appearance mode change (Dark/Light) now reflected in output   
       - Added: new color 'cTrailingComments' for comments at end of output   
       - Changed: GUI message box widths extended for readability   
       - Changed: Background color set to DarkBlue for better contrast   
       - Fixed: Runtime color selection error for certain parameter formats   
       - Fixed: Tasks not found in any Profile were not listing at the end   
       - Fixed: assigned comment color was not being used   
       - Fixed: Action 'set clipboard' missing details   
       - Fixed: List of Projects with no Tasks was repeating the same Project   
- [1.3.0] - 2023-03-11   
       - Added: Support for unit testing (no user impact)   
       - Added: Optionally display Tasker Preferences = runtime option '-preferences'   
       - Changed: Optimized initialization code   
       - Changed: Task(s) with no Profile will now be displayed under the Project it/they belong to   
       - Fixed: Go To 'action' not showing the label to go to.   
- [1.2.26] - 2023-02-27  
       - Added: New Task actions: Request Add Tile  
       - Added: Support for new parameters in Set Quick Tile, Progress Dialog  
       - Added: Display Project's/Task's Kid App info if details = 3  
       - Added: Display Profile/Task priority if details = 3  
       - Added: Log now includes 'Error:' for program/functional errors  
- [1.2.25] - 2023-02-22  
       - Fixed: Only first (TAP/LONG TAP) Task in Scene is displayed   
       - Fixed: Scene Tasks for rectangle, web elements, and 'ITEM TAP' missing  
       - Fixed: Corrected URL provided in 'Caveats' at bottom of output  
       - Added: Display Scene elements  
- [1.2.23] - 2023-02-20  
       - Fixed: GUI Restore not displaying 'file not found' in GUI
       - Added: GUI Restore changes display settings based on restored settings
- [1.2.22] - 2023-02-17     
       - Changed: Moved code base to src directory   
       - Changed: Primary program renamed from 'main' to 'maptasker'
- [1.2.2-thru-1.2.21] - 2023-02-17      
       Added: Packaged for pip install    
- [1.2.1] - 2023-02-05   
       - Updated for pip packaging  
       - Fixed: GUI 'Restore Settings' not changing the colors from saved settings  
       - Fixed: Bullet color not properly set in output  
       - Changed: Simplified command line code  
       - Added: Clarification on color argument options help by providing examples (-c)
- [1.2.0] - 2023-02-04
       - Added:  Formal argument parser    
       - Added:  Save runtime arguments to file and optionally restore them    
       - Added: Messages provided in GUI for Reset button and Color selection    
       - Added: Check for valid hex digits for program argument color    
       - Changed: Command Line Interface options have changed (see README)    
       - Fixed: Option '-e' only recognized via GUI and not CLI    
       - Changed: GUI Project/Profile/Task 'Name' buttons changed to radio buttons    
- [1.1.1] - 2023-01-27    
       - Added:  Project/Profile Taskernet details optionally displayed (see option -taskernet)    
       - Added: '-e' option for display "everything": Profile conditions, TaskerNet info and full details    
       - Fixed: Project 'launch' Tasks now properly displayed    
        - Fixed: README runtime options not formatted properly
- Fixed: Program error processing invalid color choice
    - [1.1.0] - 2023-01-23    
        - Added:  Optional GUI front-end for runtime options
        - Added:  Sample images to README    
        - Changed: Relocated called modules to subdirectory 'routines'    
        - Changed: Main program top all lowercase: maptasker.py    
        - Fixed: no longer producing log file if not in debug mode    
    - [1.0.1] - 2023-01-03    
           - Changed: Cleaned up output html    
           - Fixed: Removed extra comma at end of Task action
     - 1.0.0 - 2022-12-29    
          Changed: Program rewrite for performance, level of detail and readability    
          Changed: Removed word "Action" from output to remain consistent with Tasker
          Added: full package as zip file (see README)    
          Added: Support for 99% of Tasks, 90% of Plugins    
          Added: Support for action *name* only (no Task action parameters).  See -d2 option    
          Changed: '-d2' display detail option is now '-d3' option (see above change)    
          Fixed: A several improperly reported Task actions    
     - 0.8.0 - 2022-11-03
          Changed: Restructured code for better readability and performance
          Added: New option (-project='project name') to display a single Project, its Profiles and Tasks
          Added: Missing Plugin Actions: AutoTools Action Wait, Autotools Time, Autotools Json Read
          Fixed: Cleaned up a number of Task Actions
          Fixed: Background color option not getting properly set
          Fixed: -task= option could result in multiple Tasks being displayed for same Profile
     - 0.7.0 - 2022-10-26  
          Changed: Restructured code for better readability  
          Added: New option (-profile='profile name') to display a single Profile and it's Tasks  
          Changed: runtime option -p is now -profcon (display Profile conditions)  
          Changed: runtime option -t='task_name' is now -task='task_name' (display a single Task)  
          Fixed: Certain Tasks not being identified within Profile for option to display a single Task
          Fixed: Not properly reporting bad arguments  
     - 0.6.7 - 2022-10-17  
          Added: additional Task actions recognized and more in-depth detail for some preexisting Actions   
                   Actions completed: Zoom  
           Added: More details for a number of Actions  
           Flash, Notify, Google Drive  
           Added: Force continued Actions limit to avoid super large binary files from displaying  
           Added: Orientation Profile 'State' as condition  
           Added: Dark mode in user defined variables  
           Change: Converted lists to dictionaries for better performance  
           Fixed: Changed logic to allow for output cleanup after Action details  
           Fixed: Font corruption if Action label contains html.  Try to maintain most of the html.  
           Fixed: Invalid Project identified for Task ('...in Project xxx') if Task ID is subset of Project's Tasks (e.g. '83' in '283')
     - 0.6.6 - 2022-10-06  
           Added: additional Task actions recognized and more in-depth detail for some preexisting Actions  
                  Actions completed: Settings, System, Tasks, Tasker, Variables  
           Added: Optimized code for debug/testing mode  
           Added: More details for a number of Actions  
           Fixed: incorrect colors used if displaying specific Task  
           Fixed: Not capturing all Action attributes if type is Int (integer)  
           Fixed: Drop final comma from Action details since nothing follows after the comma  
     - 0.6.5 - 2022-09-27
           Added: additional Task actions recognized   
                    Actions complete: Phone, Scenes   
           Fixed: Incorrect indentation for Scene's Tasks and regular Tasks   
           Fixed: Established a standard Action output format that will be used going forward   
           Fixed: Eliminate extraneous print commands   
           Fixed: Bug in Action, for which an integer value is stored in a variable   
           Fixed: Not properly stripping all extraneous html from backup xml
     - 6.4 Added: additional Task actions recognized   
                    Actions complete: Media, Net                                       
           Fixed: Single Task option -t='task' sometimes returns multiple Tasks by mistake 
     - 6.3 Added: additional Task actions and Profile configurations recognized 
                    Actions complete: Google, Image, Input, Location                              
           Added: Start providing explicit detail for Actions
           Changed: Moved this change log to Changelog.md                                           
     - 6.2 Added: additional Task actions and Profile configurations recognized                  
                  Actions complete: Alert, App, Audio, Code, Display, File                       
           Added: prompt msgbox user to locate file first time the program is run                
           Fixed: don't display Scenes if displaying a single Task                               
           Fixed: not always finding Task being searched for (-t='task_name')                    
     - 6.1 Changed: removed requirements for easygui and python-tk@3.9                           
           Added: additional Task actions and Profile configurations recognized                  
     - 6.0 Added: support for colors as arguments -c(type)=color_name  type: Task/Profile/etc.   
           Added: additional Task actions and Profile configurations recognized                  
           Fixed: code refinement for better performance                                         
           Fixed: Action 'Turn Wifi' was not designating on/off/toggle                           
           Fixed: xml Actions with string 'Task' displaying in wrong color                       
           Perform: converted if-then-else processes to python 3.10's match case statements      
           Fixed: deal with extra html tags in plugin data which caused corrupted output font    
           Fixed: Go To Action had incorrect details                                             
           Fixed: Single Task option -t not working properly                                     
           Changed: Removed list output style (option -l)                                        
     - 5.2 Added: additional Task actions and Profile configurations recognized                  
           Added: If Profile condition is displayed, identify inverted conditions                
           Added: Summary at end of all Projects with no Profiles                                
           Added: Recognition of the existence of a Launcher Task                                
           Fixed: Scene details not displaying for runtime option -d1 (default)                  
           Fixed: Eliminated Profile & Task ID numbers...only needed for debug                   
           Fixed: code with name of 'Task:' incorrectly caused Task color                        
     - 5.1 Added: additional Task actions and Profile configurations recognized                  
     - 5.0 Added: Changed default font to monospace: Courier                                     
           Added: Action details for Power Mode, Mobile Data, Autosync and Setup Quick Setting   
           Added: Display Profile's condition (Time, State, Event, etc.) with option -p          
           Added: If Task is Unnamed, display just the first Task for -d0 option (like Tasker)   
           Added: identify disabled Profiles                                                     
           Fixed: exit code 1 is due to an program error...corrected and added exit 6            
           Fixed: some Scene-related Tasks wre not being listed                                  
           Fixed: Listing total unknown Tasks included those associated with Scenes              
           Fixed: Changed 'Action: nn' to 'Action nn:'   (moved then colon)                      
     - 4.3 Added: Support for more Action codes (e.g. plugin & other Task calls                  
           Fixed: Variable Search Replace action value 2 was sometimes incorrect                 
           Fixed: Removed print output line for -t='task-name' option                            
           Fixed: Not displaying owning Project for Tasks not associated to a Profile            
           Fixed: Invalid Tasks Not Found Count at end, if -d0 or -d1 options                    
     - 4.2 Fixed: Only display Scene Action detail for option -d2                                
           Added: Support for single Task detail only (option -t='Task Name Here')               
           Fixed: missing detail in Actions Notify, Custom Settings, Input Dialog & Set Alarm    
           Added: Details for plugin Actions                                                     
           Fixed: Unnamed/Anonymous Tasks output in wrong (Green) color when should be Red       
           Fixed: Remove 'Task ID: nnn' from output (of no benefit)                              
     - 4.1 Fixed: Location of output file corrected to be the current folder in msg box          
           Fixed: If set / not set were reversed                                                 
           Added: Support for disabled Actions and Action conditions (If...                      
     - 4.0 Added: indentation support for if/then sequences                                      
           Fixed: Action "End For or Stop" is just "End For"                                     
           Added: Support for more Task Action codes                                             
           Added: Action numbers                                                                 
     - 3.0 Added: display label if found for Task action(s)                                      
           Added: Display entry vs exit Task type                                                
           Added: Support for many more Task Action codes                                        
           Added: Support for 3 levels of detail: none, unnamed Tasks only, all Tasks            
                  Replaced argument -s with -d0 (no actions) and -d2 (all Task actions           
                  Default is -d1: actions for unnamed/anonymous Tasks only                       
           Fixed: Some Scenes with Long Tap were not capturing the Task                          
           Fixed: Project with no Tasks was showing incorrect Project name                       
     - 2.1 Fixed: actions were not sorted properly                                               
           Fixed: Stop action improperly reported as Else action                                 
           Added: Support for more Task Action codes                                             
     - 2.0 Added output style (linear or bullet), colormap['bullet_color'] as global var                     
           Added detail mode (default) which can be turned off with option -s                    
            displaying unnamed Task's Actions                                                    
     - 1.2 Added -v and -h arguments to display the program version and help                     
     - 1.2 launch browser to display results                                                     
     - 1.1 Added list of Tasks for which there is no Profile                                     