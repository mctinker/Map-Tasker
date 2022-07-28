# MapTasker
## Display the Tasker Project/Profile/Task/Scene hierarchy on a MAC based on Tasker's backup.xml

This is an application in support of Tasker that is intended to run on a MAC.
 
I found that my Tasker Projects/Profiles/Tasks/Scenes were becoming unmanageable, so I wrote a Python program for my MAC to provide an indented list of my entire configuration based on my Tasker backup XML file that I save to my Google Drive.
 
A portion/example of the results can be found at https://imgur.com/a/KIR7Vep.
 
Program dependencies:
-	Python version v3.9 or higher preferrably
-	easygui: install from Terminal using the command: `pip3 install --upgrade easygui`
-	python-tk@3.9: install from Terminal using the command: `brew install python-tk@3.9`
-	input Tasker backup.xml (anyname.xml…you will be prompted to locate and identify your Tasker backup xml file) on your MAC, created by Tasker version 5 or version 6. 

To install, simply download MapTasker.py or dist.zip (see below for dist.zip)
 
To run the program from the directory in which MapTasker.py resides, enter: `python3 MapTasker.py`
 
Program out: the file “MapTasker.html” will be written to your runtime/current folder, which will be opened in your default browser as a new tab.  
 
I have only been able to test this on my own backup file. If you try it out and find an error and are willing to share your backup.xml file, please send a copy to mikrubin@gmail.com 
 
If you make changes and think they may benefit others, feel free to forward them to me, at the above email address, for inclusion.
 
While not tested, I don't see why this shouldn't work on Windows or Linux.
 
Runtime: `python3 MapTasker.py -option1 -option2` ...
 
Runtime options: `-h` for help, `-l` for linear output rather than list, `-d0` for silent mode (no Action details), `-d1` to display Action list if Task is unnamed or anonymous (default), `-d2` to display Action list for all Tasks, -t='task name' to display a single Task only, -p to display a Profile's condition(s).
 
Additonally, an optional OS X compiled version of this program has been provided via the dist.zip:
- download the dist.zip
- unzip dist.zip
- To run MapTasker, simply double-click on `/dist/MapTasker/Maptasker`
 
Note: this has not been tested on other MACs and I would be interested in hearing feedback (mikrubin@gmail.com) as to whether or not this is working.    
 
  
