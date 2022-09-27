MapTasker Change log
 
  - 0.6.5 Added: additional Task actions recognized.   
                 Actions complete: Phone, Scenes.  
        Fixed: Incorrect indentation for Scene's Tasks and regular Tasks.  
        Fixed: Established a standard Action output format that will be used going forward.  
        Fixed: Eliminate extraneous print commands.  
        Fixed: Bug in Action, for which an integer value is stored in a variable.  
        Fixed: Not properly stripping all extraneous html (e.g. <small>) from backup xml.  
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
  - 2.0 Added output style (linear or bullet), bullet_color as global var                     
        Added detail mode (default) which can be turned off with option -s                    
         displaying unnamed Task's Actions                                                    
  - 1.2 Added -v and -h arguments to display the program version and help                     
  - 1.2 launch browser to display results                                                     
  - 1.1 Added list of Tasks for which there is no Profile                                     
