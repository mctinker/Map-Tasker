#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# MapTasker: read the Tasker backup file to map out the configuration                        #
#                                                                                            #
# Requirements                                                                               #
#      1- easygui API : pip3 install easygui                                                 #
#      2- python-tk@3.9 : brew install python-tk@3.9 or sudo apt-get install python3-tk      #
#      3- Python version 3.9 or higher                                                       #
#                                                                                            #
#                                                                                            #
# Version 4.3                                                                                #
#                                                                                            #
# - 4.3 Added: Support for more Action codes (e.g. plugin & other Task calls                 #
#       Fixed: Variable Search Replace action value 2 was sometimes incorrect                #
#       Fixed: Removed print output line for -t='task-name' option                           #
#       Fixed: Not displaying owning Project for Tasks not associated to a Profile           #
#       Fixed: Invalid Tasks Not Found Count at end, if -d0 or -d1 options                   #
# - 4.2 Fixed: Only display Scene Action detail for option -d2                               #
#       Added: Support for single Task detail only (option -t='Task Name Here')              #
#       Fixed: missing detail in Actions Notify, Custom Settings, Input Dialog & Set Alarm   #
#       Added: Details for plugin Actions                                                    #
#       Fixed: Unnamed/Anonymous Tasks output in wrong (Green) color when should be Red      #
#       Fixed: Remove 'Task ID: nnn' from output (of no benefit)                             #
# - 4.1 Fixed: Location of output file corrected to be the current folder in msg box         #
#       Fixed: If set / not set were reversed                                                #
#       Added: Support for disabled Actions and Action conditions (If...                     #
# - 4.0 Added: indentation support for if/then sequences                                     #
#       Fixed: Action "End For or Stop" is just "End For"                                    #
#       Added: Support for more Task Action codes                                            #
#       Added: Action numbers                                                                #
# - 3.0 Added: display label if found for Task action(s)                                     #
#       Added: Display entry vs exit Task type                                               #
#       Added: Support for many more Task Action codes                                       #
#       Added: Support for 3 levels of detail: none, unnamed Tasks only, all Tasks           #
#              Replaced argument -s with -d0 (no actions) and -d2 (all Task actions          #
#              Default is -d1: actions for unnamed/anonymous Tasks only                      #
#       Fixed: Some Scenes with Long Tap were not capturing the Task                         #
#       Fixed: Project with no Tasks was showing incorrect Project name                      #
# - 2.1 Fixed: actions were not sorted properly                                              #
#       Fixed: Stop action improperly reported as Else action                                #
#       Added: Support for more Task Action codes                                            #
# - 2.0 Added output style (linear or bullet), bullet_color as global var                    #
#       Added detail mode (default) which can be turned off with option -s                   #
#        displaying unnamed Task's Actions                                                   #
# - 1.2 Added -v and -h arguments to display the program version and help                    #
# - 1.2 launch browser to display results                                                    #
# - 1.1 Added list of Tasks for which there is no Profile                                    #
#                                                                                            #
# ########################################################################################## #
import easygui as g  # easygui dependency
import xml.etree.ElementTree as ET
import os
import sys
import webbrowser   # python-tk@3.9 dependency
import re

#  User-modifiable global constants
project_color = 'Black'
profile_color = 'Blue'
task_color = 'Green'
unknown_task_color = 'Red'
scene_color = 'Purple'
bullet_color = 'Black'
action_color = 'Orange'
action_label_color = 'Magenta'
action_condition_color = 'Coral'
disabled_task_color = 'Crimson'
browser_width = 200  # If text wraps over existing line, increase this number to match your browser's window width

# Unmodifiable global variables
disabled_task = ' <span style = "color:' + disabled_task_color + '"</span>[DISABLED]'
line_spacing = '0.0001em'

help_text1 = 'This program reads a Tasker backup file and displays the configuration of Profiles/Tasks/Scenes\n\n'
help_text2 = 'Runtime options...\n\n  -h  for this help\n  -d0 for no Task action details (silent)\n  '  \
             '-d1 display Task action details for unknown Tasks only (this is the default)\n  ' \
             "-d2 for full Task action details on every Task\n  " \
             "-t='a valid Task name'   ...to display the details for a single Task only (automatically sets -d option to -d2)\n  " \
             "-l  for list style output\n  -v  for this program's version."


help_text3 = '\n\nExit codes...\n  exit 1- no or improper filename selected\n  exit 2- output file failure\n ' \
             ' exit 3- file selected is not a valid Tasker backup file\n  exit 4- output text box error\n ' \
             ' exit 5- requested single Task not found.'
help_text4 = '\n\nThe output HTML file is saved in your current folder/directory'

caveat1 = '<span style = "color:Black"</span>CAVEATS:\n'
caveat2 = '- Most but not all Task actions have been mapped and will display as such.\n'
caveat3 = '- This has only been tested on my own backup.xml file.' \
          '  For problems, email mikrubin@gmail.com and attach your backup.xml file .'
caveat4 = '- Tasks that are identified as "Unnamed/Anonymous/Scene" have no name and can possibly\n' \
          '  be associated with a Scene (e.g. Tap / Long Tap Task actions).'

unknown_task_name = 'Unnamed/Anonymous/Scene.'
no_project = '-none found.'
no_profile = 'None or unnamed!'
my_version = '4.3'
my_file_name = '/MapTasker.html'
debug = False
debug_out = False


# Strip all html style code from string (e.g. <h1> &lt)
def strip_string(the_string):
    stripped = the_string.replace('&lt', '')
    stripped = stripped.replace('&gt', '')
    stripped = stripped.replace('&gt', '')
    p = re.compile(r'<.*?>')
    stripped = p.sub('', stripped)
    return stripped


# Evaluate the If operation
def evaluate_condition(child):
    first_string = child.find('lhs').text
    operation = child.find('op').text
    if operation == '0':
        the_operation = ' = '
    elif operation == '1':
        the_operation = ' != '
    elif operation == '2':
        the_operation = ' ~ '
    elif operation == '3':
        the_operation = ' !~ '
    elif operation == '6':
        the_operation = ' < '
    elif operation == '7':
        the_operation = ' > '
    elif operation == '12':
        the_operation = ' is set'
    elif operation == '13':
        the_operation = ' not set'
    else:
        the_operation = ' ? '
    if 'set' not in the_operation and child.find('rhs').text is not None:   #  No second string fort set/not set
        second_string = child.find('rhs').text
    else:
        second_string = ''
    return first_string, the_operation, second_string

# Get Task's label, disabled flag and any conditions
def get_label_disabled_condition(child):
    task_label = ''
    task_disabled = ''
    task_conditions = ''
    booleans = []
    the_action_code = child.find('code').text
    if child.find('label') is not None:
        lbl = strip_string(child.find('label').text)
        if lbl != '' and lbl != '\n':
            lbl.replace('\n','')
            task_label = ' <span style = "color:' + action_label_color + '"</span>...with label: ' + lbl
    if child.find('on') is not None:  # disabled action?
        task_disabled = disabled_task
    if child.find('ConditionList')  is not None:  # If condition on Action?
        condition_count = 0
        boolean_to_inject = ''
        for children in child.find('ConditionList'):
            if 'bool' in children.tag:
                booleans.append(children.text)
            elif 'Condition' == children.tag and the_action_code != '37':
                string1, operator, string2 = evaluate_condition(children)
                if condition_count != 0:
                    boolean_to_inject = booleans[condition_count-1].upper() + ' '
                task_conditions = task_conditions + ' <span style = "color:' + action_condition_color + '"</span> (' \
                                  + boolean_to_inject + 'condition:  If ' + string1 + operator + string2 + ')'
                condition_count += 1
    return task_conditions + task_disabled + task_label

# Chase after relevant data after <code> Task action
def get_action_detail(code_flag,code_child):
    extra_stuff = get_label_disabled_condition(code_child)  # Look for extra Task stiff: label, disabled, conditions
    if code_flag == 0:  # Just check for a label
        return extra_stuff
    elif code_flag == 1:  # Get first Str value
        for child in code_child:
            if child.tag == 'Str' and child.text is not None:
                return strip_string(child.text) + extra_stuff
        return ''
    elif code_flag == 2:  # Get first two string values
        count = 0
        var1 = ''
        var2 = ''
        for child in code_child:
            if child.tag == 'Str' and child.text is not None and count == 0:
                count = 1
                var1 = strip_string(child.text)
            elif child.tag == 'Str' and child.text is not None and count == 1:
                var2 = strip_string(child.text)
                return var1, var2 + extra_stuff
            else:
                pass
        return var1, var2 + extra_stuff
    elif code_flag == 3:  # Return first Int attrib
        for child in code_child:
            if child.tag == 'Int' and child.attrib.get('val') is not None:
                return child.attrib.get('val') + extra_stuff
            else:
                for dchild in child:
                    if dchild.tag == 'var' and dchild.text is not None:
                        return strip_string(dchild.text) + extra_stuff
        return extra_stuff
    elif code_flag == 4: # Get unlimited number of Str values
        var1 = []
        for child in code_child:
            if child.tag == 'Str' and child.text is not None:
                var1.append(child.text)
        for item in var1:
            strip_string(item)
        return var1, extra_stuff
    elif code_flag == 5:   # Get Application info
        lbl = ''
        for child in code_child:
            if child.tag == 'App':
                if child.find('appClass').text is not None:
                    app = child.find('appClass').text
                else:
                    app = ''
                if child.find('label').text is not None:
                    lbl1 = child.find('label').text
                else:
                    lbl1 = ''
                return app, lbl1 + extra_stuff
        return '', extra_stuff
    elif code_flag == 6:   # Get Plugin parameters
        child1 = code_child.find('Bundle')
        child2 = child1.find('Vals')
        child3 = child2.find('com.twofortyfouram.locale.intent.extra.BLURB')
        if child3 is not None:
            return child3.text + extra_stuff
        else:
            return extra_stuff
    elif code_flag == 7:  # Return first Int attrib as interpreted value
        for child in code_child:
            temp = child.attrib.get('val')
            if child.tag == 'Int' and temp is not None:
                if temp == '0':
                    return "off " + extra_stuff
                elif temp == '1':
                    return 'on ' + extra_stuff
                else:
                    return 'toggle ' + extra_stuff
            else:
                continue
        return extra_stuff
    else:
        return '???'


#
# Returns the action's name and associated variables depending on the input xml code
# <code>nn</code>  ...translate the nn into it's Action name
#
def getcode(code_child, code_action):
    taskcode = code_child.text

    if taskcode == '16':
        return 'System Lock' + get_action_detail(0, code_action)

    elif taskcode == '18':
        detail1, detail2 = get_action_detail(5, code_action)
        return 'Kill App package ' + detail1 + ' for app ' + detail2

    if taskcode == '20':
        detail1, detail2 = get_action_detail(5, code_action)
        return 'Tasker widget for ' + detail1 + ' with label ' + detail2

    elif taskcode == '30':
        return "Wait for " + get_action_detail(3, code_action)

    elif taskcode == '35':
        return "Wait" + get_action_detail(0, code_action)

    elif taskcode == '37':
        extra_stuff = get_label_disabled_condition(code_action)  # Look for extra Task stiff: label, disabled, conditions
        for cchild in code_action:
            if 'ConditionList' == cchild.tag:  # If statement...
                for children in cchild:
                    if 'Condition' == children.tag:
                        first_string, operator, second_string = evaluate_condition(children)
                        return "If " + first_string + operator + second_string + extra_stuff

    elif taskcode == '38':
        return "End If" + get_action_detail(0, code_action)

    elif taskcode == '39':
        detail1, detail2 = get_action_detail(2, code_action)
        return "For " + detail1 + ' to ' + detail2

    elif taskcode == '40':
        return "End For" + get_action_detail(0, code_action)

    elif taskcode == '41':
        det1, det2 = get_action_detail(2,code_action)
        return "Send SMS " + det1 + ' message: ' + det2

    elif taskcode == '43':
        return "Else/Else If" + get_action_detail(0, code_action)

    elif taskcode == '46':
        return "Create Scene " + get_action_detail(1,code_action)

    elif taskcode == '47':
        return "Show Scene " + get_action_detail(1,code_action)

    elif taskcode == '48':
        return "Hide Scene " + get_action_detail(1, code_action)

    elif taskcode == '49':
        return "Destroy Scene " + get_action_detail(1, code_action)

    elif taskcode == '50':
        det1, det2 = get_action_detail(2,code_action)
        return "Element Value " + det1 + ' Element: ' + det2

    elif taskcode == '51':
        return "Element Text " + get_action_detail(1, code_action)

    elif taskcode == '54':
        return "Element Text Colour " + get_action_detail(1, code_action)

    elif taskcode == '55':
        det1, det2 = get_action_detail(2, code_action)
        return "Element Back Colour of screen " + det1 + ' Element: ' + det2

    elif taskcode == '58':
        det1, det2 = get_action_detail(2,code_action)
        return "Element Size for Scene " + det1 + ' to ' + det2

    elif taskcode == '61':
        return "Vibrate time at  " + get_action_detail(3,code_action)

    elif taskcode == '62':
        return "Vibrate Pattern of " + get_action_detail(1, code_action)

    elif taskcode == '65':
        det1, det2 = get_action_detail(2,code_action)
        return "Element Visibility " + det1 + ' to element match of ' + det2

    elif taskcode == '66':
        return "Element Image " + get_action_detail(1, code_action)

    elif taskcode == '68':
        det1, det2 = get_action_detail(2,code_action)
        return "Element Focus for scene: " + det1 + ' element: ' + det2

    elif taskcode == '71':
        return "Element Text Size " + get_action_detail(1, code_action)

    elif taskcode == '100':
        return "Search " + get_action_detail(1, code_action)

    elif taskcode == '101':
        return "Take Photo filename " + get_action_detail(1, code_action)

    elif taskcode == '102':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Open File " + detail1 + ' ' + detail2

    elif taskcode == '104':
        return "Browse URL " + get_action_detail(1, code_action)

    elif taskcode == '105':
        return "Set Clipboard To " + get_action_detail(1, code_action)

    elif taskcode == '118':
        return "HTTP Get " + get_action_detail(1, code_action)

    elif taskcode == '119':
        return "Open Map, Navigate to " + get_action_detail(1, code_action)

    elif taskcode == '123':
        return "Run Shell " + get_action_detail(1, code_action)

    elif taskcode == '126':
        return "Return" + get_action_detail(0, code_action)

    elif taskcode == '129':
        return "JavaScriptlet " + get_action_detail(1, code_action)

    elif taskcode == '130':
        return "Perform Task: " + get_action_detail(1, code_action)

    elif taskcode == '131':
        return "JavaScript " + get_action_detail(1, code_action)

    elif taskcode == '133':
        return "Set Tasker Pref" + get_action_detail(0, code_action)

    elif taskcode == '135':
        return "Go To " + get_action_detail(1, code_action)

    elif taskcode == '137':
        return "Stop" + get_action_detail(0, code_action)

    elif taskcode == '159':
        return "Profile Status for " + get_action_detail(1, code_action)

    elif taskcode == '162':
            return "Setup Quick Setting for name " + get_action_detail(1, code_action)

    if taskcode == '165':
        return 'Cancel Alarm' + get_action_detail(0, code_action)

    elif taskcode == '171':
        return 'Beep' + get_action_detail(0, code_action)

    elif taskcode == '173':
        return "Network Access" + get_action_detail(0, code_action)

    elif taskcode == '171':
        var1 = 'Power Mode' + get_action_detail(0, code_action)

    elif taskcode == '175':
        return "Power Mode " + get_action_detail(0, code_action)

    elif taskcode == '193':
        return "Set Clipboard to " + get_action_detail(1, code_action)

    elif taskcode == '194':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Test Scene " + detail1 + ' store in ' + detail2

    elif taskcode == '195':
        det1, det2 = get_action_detail(2,code_action)
        return "Test Element scene:  " + det1 + ' element: ' + det2

    elif taskcode == '216':
        return "App Settings " + get_action_detail(1, code_action)

    elif taskcode == '203':
        return "Date Settings " + get_action_detail(0, code_action)

    elif taskcode == '214':
        return "Wireless Settings" + get_action_detail(0, code_action)

    elif taskcode == '235':
        detail1, lbl = get_action_detail(4,code_action)
        detail2 = ''
        for item in detail1:
            detail2 = detail2 + ' ' + item + ' '
        return 'Custom Settings' + detail2 + ' ' + lbl

    if taskcode == '245':
        return 'Back Button' + get_action_detail(0, code_action)

    elif taskcode == '248':
        return "Turn Off" + get_action_detail(0, code_action)

    elif taskcode == '294':
        return "Bluetooth " + get_action_detail(7, code_action)

    elif taskcode == '295':
        return "Bluetooth ID " + get_action_detail(1, code_action)

    elif taskcode == '296':
        return "Bluetooth Voice " + get_action_detail(7, code_action)

    elif taskcode == '300':
        return "Anchor" + get_action_detail(0, code_action)

    elif taskcode == '304':
        return "Ringer Volume to  " + get_action_detail(3, code_action)

    elif taskcode == '305':
        detail1 = get_action_detail(3, code_action)
        if detail1 != '':
            return "Notification Volume to  " + get_action_detail(3, code_action)
        else:
            return "Notification Volume" + get_action_detail(0, code_action)

    elif taskcode == '307':
        detail1 = get_action_detail(3, code_action)
        if detail1 != '':
            return "Media Volume to  " + get_action_detail(3, code_action)
        else:
            return "Media Volume" + get_action_detail(0, code_action)

    elif taskcode == '311':
        return "BT Voice Volume to " + get_action_detail(3, code_action)

    elif taskcode == '312':
        return "Do Not Disturb" + get_action_detail(0, code_action)

    elif taskcode == '313':
        return "Sound Mode" + get_action_detail(0, code_action)

    elif taskcode == '316':
        return "Display Size" + get_action_detail(0, code_action)

    elif taskcode == '319':
        return "Ask Permissions " + get_action_detail(1, code_action)

    elif taskcode == '328':
        return "Keyboard " + get_action_detail(0, code_action)

    elif taskcode == '331':
        return "Auto-Sync" + get_action_detail(0, code_action)

    elif taskcode == '334':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Save WaveNet " + detail1 + ' Voice: ' + detail2

    elif taskcode == '335':
        return "App Info" + get_action_detail(0, code_action)

    elif taskcode == '339':
        return "HTTP Request " + get_action_detail(1, code_action)

    elif taskcode == '340':
        return "Bluetooth Connection for device " + get_action_detail(1, code_action)

    elif taskcode == '341':
        return "Test Net " + get_action_detail(1, code_action)

    elif taskcode == '342':
        det1, det2 = get_action_detail(2,code_action)
        return "Test File with data " + det1 + ' store in ' + det2

    elif taskcode == '344':
        det1, det2 = get_action_detail(2,code_action)
        return "Test App " + det1 + ' store in ' + det2

    elif taskcode == '345':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Test Variable " + detail1 + ' and store into ' + detail2

    elif taskcode == '347':
        t = "Test Tasker and store results into " + get_action_detail(1, code_action)
        return "Test Tasker and store results into " + get_action_detail(1, code_action)

    elif taskcode == '348':
        return "Test Display " + get_action_detail(1, code_action)

    elif taskcode == '354':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Array Set for array " + detail1 + ' with values ' + detail2

    elif taskcode == '355':
        return "Array Push " + get_action_detail(1, code_action)

    elif taskcode == '357':
        return "Array Clear " + get_action_detail(1, code_action)

    elif taskcode == '356':
        return "Array Pop " + get_action_detail(1, code_action)

    elif taskcode == '358':
        return "Bluetooth Info " + get_action_detail(0, code_action)

    elif taskcode == '360':
        detail1, lbl = get_action_detail(4, code_action)
        detail2 = ''
        for item in detail1:
            detail2 = detail2 + ' , ' + item
        return 'Input Dialog ' + detail2 + ' ' + lbl

    elif taskcode == '365':
        return "Tasker Function " + get_action_detail(1, code_action)

    elif taskcode == '366':
        return "Get Location V2" + get_action_detail(0, code_action)

    elif taskcode == '367':
        return "Camera" + get_action_detail(0, code_action)

    elif taskcode == '369':
        return "Array Process " + get_action_detail(1, code_action)

    elif taskcode == '373':
        return "Test Sensor " + get_action_detail(1, code_action)

    elif taskcode == '377':
        detail1, lbl = get_action_detail(4, code_action)
        detail2 = ''
        for item in detail1:
            detail2 = detail2 + ' , ' + item
        return 'Text/Image Dialog ' + detail2 + ' ' + lbl

    elif taskcode == '378':
        return "List Dialog " + get_action_detail(1, code_action)

    elif taskcode == '383':
        return "Settings Panel" + get_action_detail(0, code_action)

    elif taskcode == '389':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Multiple Variables Set " + detail1 + ' to ' + detail2

    elif taskcode == '390':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Pick Input Dialog " + detail1 + ' with structure type ' + detail2

    elif taskcode == '392':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Set Variable Structure Type name " + detail1 + ' with structure type ' + detail2

    elif taskcode == '393':
        return "Array Merge " + get_action_detail(1, code_action)

    elif taskcode == '394':
        return "Parse/Format DateTime " + get_action_detail(0, code_action)

    elif taskcode == '396':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Simple Match/Regex " + detail1 + ' with regex ' + detail2

    elif taskcode == '399':
        return "Variable Map " + get_action_detail(1, code_action)

    elif taskcode == '400':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Move (file) from " + detail1 + ' to ' + detail2

    elif taskcode == '404':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Copy File " + detail1 + ' to ' + detail2

    elif taskcode == '406':
        return "Delete File " + get_action_detail(1, code_action)

    elif taskcode == '409':
        return "Create Directory " + get_action_detail(1, code_action)

    elif taskcode == '410':
        return "Write File " + get_action_detail(1, code_action)

    elif taskcode == '412':
        return "List Files " + get_action_detail(1, code_action)

    elif taskcode == '417':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Read File " + detail1 + ' into ' + detail2

    elif taskcode == '425':
        return "Turn Wifi" + get_action_detail(0, code_action)

    elif taskcode == '430':
        return "Restart Tasker" + get_action_detail(0, code_action)

    elif taskcode == '433':
        return 'Mobile Data' + get_action_detail(0, code_action)

    if taskcode == '443':
        return 'Media Control' + get_action_detail(0, code_action)

    elif taskcode == '445':
        return "Music Play " + get_action_detail(1, code_action)

    elif taskcode == '449':
        return "Music Stop" + get_action_detail(0, code_action)

    elif taskcode == '511':
        return 'Torch' + get_action_detail(0, code_action)

    elif taskcode == '512':
        return 'Status Bar' + get_action_detail(0, code_action)

    elif taskcode == '513':
        return "Close System Dialogs" + get_action_detail(0, code_action)

    elif taskcode == '523':
        detail1, lbl = get_action_detail(4, code_action)
        detail2 = ''
        for item in detail1:
            if item is not None:
                detail2 = detail2 + ' , ' + item
        return 'Notify ' + detail2 + ' ' + lbl

    elif taskcode == '536':
        return "Notification Vibrate with title " + get_action_detail(1, code_action)

    elif taskcode == '538':
        return "Notification Sound with title " + get_action_detail(1, code_action)

    elif taskcode == '550':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Popup title " + detail1 + ' with message: ' + detail2

    elif taskcode == '543':
        return "Start System Timer " + get_action_detail(1, code_action)

    elif taskcode == '545':
        return "Variable Randomize " + get_action_detail(1, code_action)

    elif taskcode == '547':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Variable Set " + detail1 + ' to ' + detail2

    elif taskcode == '548':
        return "Flash " + get_action_detail(1, code_action)

    elif taskcode == '549':
        return "Variable Clear " + get_action_detail(1, code_action)

    elif taskcode == '550':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Popup title " + detail1 + ' with text ' + detail2

    elif taskcode == '559':
        return "Say " + get_action_detail(1, code_action)

    elif taskcode == '566':
        detail1, lbl = get_action_detail(4, code_action)
        detail2 = ''
        for item in detail1:
            detail2 = detail2 + ' ' + item + ' '
        return 'Set Alarm ' + detail2 + ' ' + lbl

    elif taskcode == '567':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Calendar Insert " + detail1 + ' with description: ' + detail2

    elif taskcode == '590':
        return "Variable Split " + get_action_detail(1, code_action)

    elif taskcode == '592':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Variable Join " + detail1 + ' to ' + detail2

    elif taskcode == '596':
        return "Variable Convert " + get_action_detail(1, code_action)

    elif taskcode == '597':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Variable Section " + detail1 + ' from ' + detail2

    elif taskcode == '598':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Variable Search Replace " + detail1 + ' search for ' + detail2

    elif taskcode == '664':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Java Function return object " + detail1 + ' , ' + detail2

    elif taskcode == '667':
        detail1, detail2 = get_action_detail(2, code_action)
        return "SQL Query " + detail1 + ' to ' + detail2

    elif taskcode == '697':
        return "Shut Up" + get_action_detail(0, code_action)

    elif taskcode == '775':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Write Binary " + detail1 + ' file: ' + detail2

    elif taskcode == '779':
        return "Notify Cancel " + get_action_detail(1, code_action)

    elif taskcode == '806':
        return "Notify Cancel " + get_action_detail(3, code_action)

    elif taskcode == '810':
        return "Display Brightness to " + get_action_detail(3, code_action)

    elif taskcode == '812':
        return "Display Timeout " + get_action_detail(3, code_action)

    elif taskcode == '815':
        return "List Apps into " + get_action_detail(1, code_action)

    elif taskcode == '877':
        return "Send Intent " + get_action_detail(1, code_action)

    elif taskcode == '888':
        return "Variable Add " + get_action_detail(3, code_action)

    elif taskcode == '890':
        return "Variable Subtract " + get_action_detail(1, code_action)

    elif taskcode == '902':
        return "Get Locations " + get_action_detail(1, code_action)

    elif taskcode == '987':
        return "Soft Keyboard" + get_action_detail(0, code_action)

# Plugins start here

    elif taskcode == '117240295':
        return "AutoWear Input " + get_action_detail(6, code_action)

    elif taskcode == '140618776':
        return "AutoWear Toast " + get_action_detail(6, code_action)


    elif taskcode == '166160670':
        return "AutoNotification " + get_action_detail(6, code_action)

    elif taskcode == '191971507':
        return "AutoWear ADB Wifi " + get_action_detail(6, code_action)

    elif taskcode == '234244923':
        return "AutoInput Unlock Screen" + get_action_detail(0, code_action)

    elif taskcode == '268157305':
        return "AutoNotification Tiles " + get_action_detail(6, code_action)

    elif taskcode == '319692633':
        return "AutoShare Process Text " + get_action_detail(6, code_action)

    elif taskcode == '344636446':
        return "AutoVoice Trigger Alexa Routine " + get_action_detail(6, code_action)

    elif taskcode == '557649458':
        return "AutoWear Time " + get_action_detail(6, code_action)

    elif taskcode == '565385068':
        return "AutoWear Input " + get_action_detail(6, code_action)

    elif taskcode == '774351906':
        return " " + get_action_detail(6, code_action) # Join Action (contained in get_action_detail)

    elif taskcode == '778682267':
        return "AutoInput Gestures " + get_action_detail(6, code_action)

    elif taskcode == '811079103':
        return "AutoInput Global Action " + get_action_detail(6, code_action)

    elif taskcode == '906355163':
        return "AutoWear Voice Screen " + get_action_detail(6, code_action)

    elif taskcode == '940160580':
        return "AutoShare " + get_action_detail(6, code_action)

    elif taskcode == '1027911289':
        return "AutoVoice Set Cmd Id " + get_action_detail(6, code_action)

    elif taskcode == '1099157652':
        return "AutoTools Json Write " + get_action_detail(6, code_action)

    elif taskcode == '1040876951':
        return "AutoInput UI Query " + get_action_detail(6, code_action)

    elif taskcode == '1165325195':
        return "AutoTools Web Screen " + get_action_detail(6, code_action)

    elif taskcode == '1250249549':
        return "AutoInput Screen Off/On " + get_action_detail(6, code_action)

    elif taskcode == '1246578872':
        return "AutoWear Notification " + get_action_detail(6, code_action)

    elif taskcode == '1304982781':
        return "AutoTools Dialog " + get_action_detail(6, code_action)

    elif taskcode == '1410790256':
        return "AutoWear Floating Icon " + get_action_detail(6, code_action)

    elif taskcode == '1644316156':
        return "AutoNotification Reply " + get_action_detail(6, code_action)

    elif taskcode == '1754437993':
        return "AutoVoice Recognize " + get_action_detail(6, code_action)

    elif taskcode == '1830829821':
        return "AutoWear 4 Screen " + get_action_detail(6, code_action)

    elif taskcode == '1957670352':
        return "AutoWear App " + get_action_detail(6, code_action)

    elif taskcode == '1339942270':
        return "SharpTools Thing " + get_action_detail(6, code_action)

    elif taskcode == '1452528931':
        return "AutoContacts Query 2.0 " + get_action_detail(6, code_action)

    elif taskcode == '1620773086':
        return "SharpTools A Thing " + get_action_detail(6, code_action)

    elif taskcode == '1447159672':
        return "AutoTools Text " + get_action_detail(6, code_action)

    elif taskcode == '1508929357':
        return "AutoTools " + get_action_detail(6, code_action)

    elif taskcode == '1732635924':
        return "AutoInput Action " + get_action_detail(6, code_action)

    elif taskcode == '1830656901':
        return "AutoWear List Screens " + get_action_detail(6, code_action)

    elif taskcode == '2046367074':
        return "AutoNotification Cancel " + get_action_detail(6, code_action)

    elif 1000 < int(taskcode):
        return "Call to Plugin " + get_action_detail(6, code_action)

    else:
        return "Code " + taskcode + " not yet mapped"


# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
def ulify(element, out_style, lvl=int):   # lvl=0=heading 1=start list 2=Task/Profile/Scene 3=end list 4=special Task
    string = ''
    # Heading..............................
    if lvl == 0 or lvl == 4:  # lvl=4 >>> Heading or plain text line
        if lvl == 0:  #Heading
            string = "<b>" + element + "</b><br>\n"
        else:
            string = element + '<br>\n'
    # Start List..............................
    elif lvl == 1:  # lvl=1 >>> Start list
        if out_style == 'L':
            string = element
        else:
            string = "<ul>" + element + "\n"
    # Item in the list..............................
    elif lvl == 2:  # lvl=2 >>> List item
        if 'Project' == element[0:7]:   # Project ========================
            if out_style == 'L':
                string = '<p style = "color:' + project_color + ';">' + element + '</p>'
            else:
                string = '<li style="color:' + bullet_color + '" ><span style="color:' + project_color + ';">' + element + '</span></li>\n'
        elif 'Profile' == element[0:7]:  # Profile ========================
            if out_style == 'L':
                string = '<p style = "color:' + profile_color + ';line-height:' + line_spacing + '"> ├⎯' + element + '</p>\n'
            else:
                string = '<li style="color:' + bullet_color + '" ><span style="color:' + profile_color + ';">' + element + '</span></li>\n'
        elif 'Task:' in element and 'Perform Task:' not in element:  # Task ========================
            if out_style == 'L':
                if unknown_task_name in element:
                    string = '<p style = "color:' + unknown_task_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + element + '\n'
                else:
                    string = '<p style = "color:' + task_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + element + '\n'
            else:
                if unknown_task_name in element:
                    string = '<li style="color:' + bullet_color + '" ><span style="color:' + unknown_task_color + ';">' + element + '</span></li>\n'
                else:
                    string = '<li style="color:' + bullet_color + '" ><span style="color:' + task_color + ';">' + element + '</span></li>\n'
        elif 'Scene:' in element:  # Scene
            if out_style == 'L':
                string = '<p style = "color:' + scene_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + element + '\n'
            else:
                string = '<li style="color:' + bullet_color + '" ><span style="color:' + scene_color + ';">' + element + '</span></li>\n'
        elif 'Action:' in element:  # Action
            if 'Action: ...' in element:
                if '' == element[11:len(element)]:
                    string = ''
                    return string
                tmp = element.replace('Action: ...','Action continued >>> ')
                element = tmp
            if out_style == 'L':
                string = '<p style = "color:' + action_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├⎯⎯' + element + '\n'
            else:
                string = '<li style="color:' + bullet_color + '" ><span style="color:' + action_color + ';">' + element + '</span></li>\n'
        elif 'Label for' in element:  # Action
            if out_style == 'L':
                string = '<p style = "color:' + action_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├⎯⎯' + element + '\n'
            else:
                string = '<li style="color:' + bullet_color + '" ><span style="color:' + action_color + ';">' + element + '</span></li>\n'
        else:      # Must be additional item
            if out_style == 'L':
                string = element + '\n'
            else:
                string = "<li>" + element + "</li>\n"
    # End List..............................
    elif lvl == 3:  # lvl=3 >>> End list
        string = "</ul>"
    return string


# Write line of output
def my_output(output_list, list_level, style, out_string):
    if 'Scene:' in out_string and 'L' == style:  # Handle special condition for Scenes in Linear mode.
        temp_element = out_string
        out_string = '<p style = "color:' + scene_color + ';line-height:' + line_spacing + '"'
        output_list.append(ulify(out_string, style, list_level))
        out_string = temp_element
    if 'Task ID:' in out_string and debug is False:   # Drop ID: nnn since we don't need it anymore
        temp_element = out_string.split('Task ID:')
        out_string = temp_element[0]
    output_list.append(ulify(out_string, style, list_level))
    if debug_out:
        print('out_string:',ulify(out_string, style, list_level))
    return


# Construct Task Action output line
def build_action(alist, tcode, achild, indent, indent_amt):
    # Calculate total indentation to put in front of action
    count = indent
    if count != 0:
        tcode = indent_amt + tcode
        count = 0
    if count < 0:
        # indent_len = len(indent_amt)
        tcode = indent_amt + tcode
        count = 0
    # Break-up very long actions at new line
    if tcode != '':
        newline = tcode.find('\n')  # Break-up new line breaks
        tcode_len = len(tcode)
        # If no new line break or line break less than width set for browser, just put it as is
        # Otherwise, make it a continuation line using '...' has the continuation flag
        if newline == -1 or tcode_len < browser_width:
            alist.append(tcode)
        else:
            array_of_lines = tcode.split('\n')
            count = 0
            for item in array_of_lines:
                if count == 0:
                    alist.append(item)
                else:
                    alist.append('...' + item)
                count += 1
    # Unknown action...we have yet to identify it in our code.
    else:
        alist.append('Action ' + achild.text + ': not yet mapped')
    return


# Shell sort for Action list (Actions are not necessarily in numeric order in XML backup file.
def shellSort(arr, n):
    gap = n // 2
    attr1 = ET.Element
    attr2 = ET.Element
    while gap > 0:
        j = gap
        # Check the array in from left to right
        # Till the last possible index of j
        while j < n:
            i = j - gap  # This will keep help in maintain gap value
            while i >= 0:
                # Get the n from <Action sr="actn" ve="7"> as a number for comparison purposes
                attr1 = arr[i]
                attr2 = arr[i+gap]
                val1 = attr1.attrib['sr']
                val2 = attr2.attrib['sr']
                comp1 = val1[3:len(val1)]
                comp2 = val2[3:len(val2)]
                # If value on right side is already greater than left side value
                # We don't do swap else we swap
                if int(comp2) > int(comp1):
                    break
                else:
                    arr[i + gap], arr[i] = arr[i], arr[i + gap]
                i = i - gap  # To check left side also
                # If the element present is greater than current element
            j += 1
        gap = gap // 2


# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
def get_actions(current_task):
    tasklist = []
    try:
        task_actions = current_task.findall('Action')
    except Exception as e:
        print('No action found!!!')
        return []
    if task_actions:
        count_of_actions = 0
        indentation_amount = ''
        indentation = 0
        for action in task_actions:
            count_of_actions += 1
        # sort the Actions by attrib sr (e.g. sr='act0', act1, act2, etc.) to get them in true order
        if count_of_actions > 1:
            shellSort(task_actions,count_of_actions)
        for action in task_actions:
            child = action.find('code')   # Get the <code> element
            task_code = getcode(child, action)
            if debug:
                print('Task ID:',current_task.attrib['sr'],' Code:',child.text,' task_code:',task_code,'Action attr:',action.attrib)
            if 'End If' == task_code[0:6] or 'Else' == task_code[0:4] or 'End For' == task_code[0:7]:  # Do we un-indent?
                indentation -= 1
                length_indent = len(indentation_amount)
                indentation_amount = indentation_amount[24:length_indent]
            build_action(tasklist, task_code, child, indentation, indentation_amount)
            if 'If' == task_code[0:2] or 'Else' == task_code[0:4] or 'For' == task_code[0:3]:  # Do we indent?
                indentation += 1
                indentation_amount = indentation_amount + '&nbsp;&nbsp;&nbsp;&nbsp;'
    return tasklist


# Get the name of the task given the Task ID
# return the Task's element and the Task's name
def get_task_name(the_task_id, all_the_tasks, tasks_that_have_benn_found, the_task_list, task_type):
    task_name = ''
    for task in all_the_tasks:
        if the_task_id == task.find('id').text:
            tasks_that_have_benn_found.append(the_task_id)
            extra = '&nbsp;&nbsp;Task ID: ' + the_task_id
            try:
                task_name = task.find('nme').text
                if task_type == 'Exit':
                    the_task_list.append(task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task' + extra)
                else:
                    the_task_list.append(task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task' + extra)
            except Exception as e:
                if task_type == 'Exit':
                    the_task_list.append(unknown_task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task' + extra)
                else:
                    the_task_list.append(unknown_task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task' + extra)
            break
    return task, task_name


# Process Task/Scene text/line item: call recursively for Tasks within Scenes
def process_list(list_type, the_output, the_list, all_task_list, all_scene_list, the_task, the_style,
                 tasks_found, detail):
    my_count = 0
    if the_style != 'L':
        my_output(the_output, 1, the_style, '')  # Start list_type list
        have_task = ''
    for the_item in the_list:
        if debug:
            print('the_item:',the_item,' list_type:',list_type)
        if my_count > 0 and the_style == 'L':  # If more than one list_type, skip normal output
            my_output(the_output, 2, the_style, '<br>&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + list_type + '&nbsp;' + the_item + '<br>')
        else:
            my_output(the_output, 2, the_style,list_type + '&nbsp;' + the_item)
            my_count += 1
        # Output Actions for this Task if displaying detail and/or Task is unknown
        # Do we get the Task's Actions?
        if ('Task:' in list_type and (detail > 0 and unknown_task_name in the_item)) or ('Task:' in list_type and detail == 2):
            if unknown_task_name in the_item or detail > 0:  # If Unknown task, then "the_task" is not valid, and we have to find it.
                if '⎯Task:' in list_type:   # -Task: = Scene rather than a Task
                    temp = ["x", the_item]
                else:
                    temp = the_item.split('ID: ')  # Unknown/Anonymous!  Task ID: nn    << We just need the nn
                if len(temp) > 1:
                    the_task, kaka = get_task_name(temp[1], all_task_list, tasks_found, [temp[1]], '')
            alist = get_actions(the_task)  # Get the Task's Actions
            if alist:
                action_count = 1
                my_output(the_output, 1, the_style, '')  # Start Action list
                for taction in alist:
                    if taction is not None:
                        if 'Label for' in taction:
                            my_output(the_output, 2, the_style, taction)
                        else:
                            if '...' == taction[0:3]:
                                my_output(the_output, 2, the_style, 'Action: ' + taction)
                            else:
                                my_output(the_output, 2, the_style, 'Action: ' + str(action_count).zfill(2) + ' ' + taction)
                                action_count += 1
                my_output(the_output, 3, the_style, '')  # Close Action list
        # Must be a Scene.  Look for all "Tap" Tasks for Scene
        elif 'Scene:' == list_type and detail == 2:  # We have a Scene: get its actions
            scene_task_list = []
            for my_scene in the_list:   # Go through each Scene to find TAP and Long TAP Tasks
                getout = 0
                for scene in all_scene_list:
                    for child in scene:
                        if child.tag == 'nme' and child.text == my_scene:  # Is this our Scene?
                            for cchild in scene:   # Go through sub-elements in the Scene element
                                if 'ListElement' == cchild.tag or 'TextElement' == cchild.tag or 'ImageElement' == cchild.tag:
                                    for subchild in cchild:   # Go through ListElement sub-items
                                        if 'click' in subchild.tag:
                                            scene_task_list.append(subchild.text)
                                            temp_task_list = [subchild.text]
                                            task_element, name_of_task = get_task_name(subchild.text, all_task_list, tasks_found, temp_task_list, '')
                                            temp_task_list = [subchild.text]  # reset to task name since get_task_name changes it's value
                                            if subchild.tag == 'itemclickTask' or subchild.tag == 'clickTask':
                                                task_type = '⎯Task: TAP&nbsp;&nbsp;ID:'
                                            elif 'long' in subchild.tag:
                                                task_type = '⎯Task: LONG TAP&nbsp;&nbsp;ID:'
                                            process_list(task_type, the_output, temp_task_list, all_task_list,
                                                         all_scene_list, task_element, the_style,
                                                         tasks_found, detail) # Call ourselves iteratively
                                        elif subchild.tag == 'Str':
                                            break
                                    if scene_task_list:  # Display Tasks for Scene if we have 'em
                                        for the_scene_task in scene_task_list:  # Now add Task to the Task list.
                                            getout = 2
                                    else:
                                        getout = 1
                                        break
                                elif 'Str' == cchild.tag:
                                    break
                                elif 'ButtonElement' == cchild.tag:   # Have we gone past the point ofm interest?
                                    break
                        elif child.tag == 'nme':
                            if getout > 0:
                                break
                            pass
                        if child.tag == 'ButtonElement':
                            break
                        if getout > 0:
                            break
    if the_style != 'L':
        my_output(the_output, 3, the_style, '')  # Close list_type list
        return

# Find the Project belonging to the Task id passed in
def get_project_for_solo_task( all_of_the_projects, the_task_id, projs_with_no_tasks):
    proj_name = no_project
    for project in all_of_the_projects:
        proj_name = project.find('name').text
        proj_tasks = ''
        try:
            proj_tasks = project.find('tids').text
        except Exception as e:  # Project has no Tasks
            if proj_name not in projs_with_no_tasks:
                projs_with_no_tasks.append(proj_name)
            proj_name = no_project
            continue
        if the_task_id in proj_tasks:
            return proj_name, project
    return proj_name, project

# Main program here >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Main program here >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>        
def main():
    # Set local variables
    task_list = []
    found_tasks = []
    output_list = []
    single_task = ''
    single_task_found = ''
    single_task_nme_name = ''
    display_detail = 1     # Default display detail: unknown Tasks actions only

    output_style = ''  # L=linear, default=bullet

    help_text = help_text1 + help_text2 + help_text3 + help_text4
    # Get any arguments passed to program
    if debug:
        print('sys.argv:',sys.argv)
    # First, let's look to see if this run is for a single Task
    for item in sys.argv:
        if '-t=' == item[0:3]:
            single_task = item[3:len(item)]
            display_detail = 2  # Force detailed output
            break

    # Now go through the rest of the arguments
    for i, arg in enumerate(sys.argv):
        if debug:
            print('arg:',arg[0:4])
        if arg == '-v':  # Version
            g.textbox(msg="MapTasker Version", title="MapTasker", text="Version " + my_version)
            sys.exit()
        elif arg == '-h':  # Help
            g.textbox(msg="MapTasker Help", title="MapTasker", text=help_text)
            sys.exit()
        elif arg == '-d0':  # Detail: 0 = no detail
            display_detail = 0
        elif arg == '-d1':  # Detail: 0 = no detail
            display_detail = 1
        elif arg == '-d2':  # Detail: 2 = all Task's actions/detail
            display_detail = 2
        elif arg == '-l':
            output_style = 'L'
        elif arg[0:3] == '-t=':
            pass
        else:
            if 'MapTasker' not in arg:
                if g.textbox(msg='MapTasker', title="MapTasker", text="Argument " + arg + " is invalid!"):
                    pass
                else:
                    exit(4)

    # Find the Tasker backup.xml
    msg = 'Locate the Tasker backup xml file to use to map your Tasker environment'
    title = 'MapTasker'
    filename = g.fileopenbox(msg, title, default="*.xml", multiple=False)
    if filename is None:
        g.textbox(msg="MapTasker cancelled", title="MapTasker", text="Backup selection cancelled.  Program ended.")
        exit(1)

    # Import xml
    tree = ET.parse(filename)
    root = tree.getroot()
    all_projects = root.findall('Project')
    all_profiles = root.findall('Profile')
    all_scenes = root.findall('Scene')
    all_tasks = root.findall('Task')

    if 'TaskerData' != root.tag:
        my_output(output_list, 0, output_style, 'You did not select a Tasker backup XML file...exit 2')
        exit(3)

    my_output(output_list, 0, output_style, 'Tasker Mapping................')
    my_output(output_list, 1, output_style, '')  # Start Project list

    # Traverse the xml

    # Start with Projects <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    for project in all_projects:
        if single_task_found == '1':   # Don't bother with another Project if we've done a single task only
            break
        project_name = project.find('name').text
        project_pids = ''
        my_output(output_list, 2, output_style, 'Project: ' + project_name)

        # Get Profiles and it's Project and Tasks
        my_output(output_list, 1, output_style, '')  # Start Profile list
        try:
            project_pids = project.find('pids').text  # Project has no Profiles
        # except xml.etree.ElementTree.ParseError doesn't compile:
        except Exception:
            my_output(output_list, 2, output_style, 'Profile: ' + no_profile)
        if project_pids != '':  # Project has Profiles?
            profile_id = project_pids.split(',')

            # Now go through all the Profiles for this Project <<<<<<<<<<<<<<<<<<<<<
            for item in profile_id:

                for profile in all_profiles:
                    # XML search order: id, mid"n", nme = Profile id, task list, Profile name
                    # Get the Tasks for this Profile
                    if item == profile.find('id').text:  # Is this the Profile we want?
                        task_list = []  # Get the Tasks for this Profile
                        for child in profile:
                            if 'mid' in child.tag:
                                task_type = 'Entry'
                                if 'mid1' == child.tag:
                                    task_type = 'Exit'
                                task_id = child.text
                                #task_id_list.append(task_id)
                                if debug and task_id == '141':
                                    print('====================================',task_id,'====================================')
                                our_task_element, our_task_name = get_task_name(task_id, all_tasks, found_tasks, task_list, task_type)
                            elif 'nme' == child.tag:  # If hit Profile's name, we've passed all the Task ids.
                                break
                        try:
                            profile_name = profile.find('nme').text  # Get Profile's name
                        except Exception as e:  # no Profile name
                            profile_name = no_profile
                        my_output(output_list, 2, output_style, 'Profile: ' + profile_name)

                # We have the Tasks.  Now let's output them.
                if single_task:   # Are we mapping just a single Task?
                    if single_task == our_task_name:
                        output_list = output_list[len(output_list)-3:len(output_list)]
                        single_task_found = '1'
                        process_list('Task:', output_list, task_list, all_tasks, all_scenes, our_task_element,
                                     output_style, found_tasks, display_detail)
                elif task_list:
                    process_list('Task:', output_list, task_list, all_tasks, all_scenes, our_task_element, output_style,
                                 found_tasks, display_detail)

        # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        scene_names = ''
        try:
            scene_names = project.find('scenes').text
        except Exception as e:
            pass
        if scene_names != '':
            scene_list = scene_names.split(',')
            process_list('Scene:', output_list, scene_list, all_tasks, all_scenes, our_task_element, output_style,
                         found_tasks, display_detail)

        my_output(output_list, 3, output_style, '')  # Close Profile list
    my_output(output_list, 3, output_style, '')  # Close Project list

    # #######################################################################################
    # Now let's look for Tasks that are not referenced by Profiles and display a total count
    # #######################################################################################
    # First, let's delete all the duplicates in out found task list
    res = []
    for i in found_tasks:
        if i not in res:
            res.append(i)
    found_tasks = res
    # See if we didn't find our task
    unnamed_task_count = 0
    have_heading = 0
    task_name = ''
    projects_with_no_tasks = []
    for task in all_tasks:  # Get a/next Task
        unknown_task = ''
        if single_task_found == '1':  # If we just processed a single task only, then bail out.
            break
        task_id = task.find('id').text
        if debug and task_id == '103':
            print('No Profile ==========================', task_id, '====================================')
        if task_id not in found_tasks:  # We have a solo Task not associated to any Profile
            project_name, the_project = get_project_for_solo_task(all_projects, task_id, projects_with_no_tasks)

            # At this point, we've found the Project this Task belongs to, or it doesn't belong to any Task
            if have_heading == 0:
                my_output(output_list, 0, output_style, '<hr>')  # blank line
                my_output(output_list, 0, output_style,
                          'Tasks that are not in any Profile (may be a desktop Tasker Task/widget or Task in a Scene)...')
                my_output(output_list, 1, output_style, '')  # Start Task list
                have_heading = 1

            # Get the Task's name
            try:
                task_name = task.find('nme').text
                single_task_nme_name = task_name
            except Exception as e:  # Task name not found!
                # Unknown Task.  Display details if requested
                task_name = unknown_task_name + '&nbsp;&nbsp;Task ID: ' + task_id
                unknown_task = '1'
                unnamed_task_count += 1

            # Identify which Project Task belongs to if Task has a valid name
            if not unknown_task and project_name != no_project:
                if debug:
                    task_name += ' with Task ID ' + task_id + ' ...in Project ' + project_name
                else:   # Drop Task ID nnn since we don't need it
                    task_name += ' ...in Project ' + project_name

            # Output the (possible unknown) Task's details
            if not unknown_task or display_detail > 0:  # Only list named Tasks or if details are wanted
                task_list = [task_name]
                # This will output the task and it's Actions if displaying details
                if (single_task and single_task == single_task_nme_name) or single_task == '':
                    if single_task != '' and single_task == single_task_nme_name:
                        single_task_found = '1'
                        output_list.clear()
                        output_list = ['<b>MapTasker ...</b>' ]
                    process_list('Task:', output_list, task_list, all_tasks, all_scenes, task, output_style,
                                 found_tasks, display_detail)

    # Provide total number of unnamed Tasks
    if unnamed_task_count > 0:
        if output_style == 'L' or display_detail > 0:
            my_output(output_list, 0, output_style, '')  # line
            if output_style == 'L':
                my_output(output_list, 4, output_style,
                          '<p style = "color:' + profile_color + ';line-height:normal"></p>\n')  # line spacing back to normal
        my_output(output_list, 3, output_style, '')  # Close Task list
        if single_task_found == '':   # If we don't have a single Task only, display total count of unnamed Tasks
            my_output(output_list, 0, output_style,
                      '<font color=' + unknown_task_color + '>There are a total of ' + str(
                          unnamed_task_count) + ' unnamed Tasks!!!')
    if task_name is True:
        my_output(output_list, 3, output_style,  '')  # Close Task list

    my_output(output_list, 3, output_style, '')  # Close out the list

    # List Projects with no Tasks
    if len(projects_with_no_tasks) > 0:
        my_output(output_list, 0, output_style, '<hr><font color=Black>')  # line
        for item in projects_with_no_tasks:
            my_output(output_list, 4, output_style, 'Project ' + item + ' has no Tasks')

    # Requested single Task but invalid Task name provided (i.e. no Task found)?
    if single_task != '' and single_task_found == '':
        output_list.clear()
        g.textbox(msg="MapTasker", title="MapTasker", text="Task " + single_task + ' not found!!')
        exit(5)

    # Let's wrap things up...

    # Output caveats if we are displaying the Actions
    my_output(output_list, 0, output_style, '<hr>')  # line
    my_output(output_list, 4, output_style, caveat1)  # caveat
    if display_detail > 0:  # Caveat about Actions
        my_output(output_list, 4, output_style, caveat2)  # caveat
    my_output(output_list, 4, output_style, caveat3)  # caveat
    my_output(output_list, 4, output_style, caveat4)  # caveat

    # Okay, lets generate the actual output file.
    # Store the output in the current  directory
    my_output_dir = os.getcwd()
    if my_output_dir is None:
        g.textbox(msg="MapTasker cancelled", title="MapTasker", text="An error occurred.  Program cancelled.")
        exit(2)
    out_file = open(my_output_dir + my_file_name, "w")

    # Output the generated html
    for item in output_list:
        out_file.write(item)

    out_file.close()  # Close our output file

    # Clean up memory
    for elem in tree.iter():
        elem.clear()
    all_projects.clear()
    all_profiles.clear()
    all_tasks.clear()
    all_scenes.clear()
    root.clear()
    output_list.clear()

    # Display final output
    webbrowser.open('file://' + my_output_dir + my_file_name, new=2)
    g.textbox(msg="MapTasker Done", title="MapTasker",
              text="You can find 'MapTasker.html' in the current folder.  Your browser has displayed it in a new tab.  Program end.")


# Main call
if __name__ == "__main__":
    main()
