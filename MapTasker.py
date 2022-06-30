#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# MapTasker: read the Tasker backup file to map out the configuration                        #
#                                                                                            #
# Requirements                                                                               #
#      1- easygui API : pip install easygui                                                  #
#      2- Python version 3.9 or higher                                                       #
#                                                                                            #
#                                                                                            #
# Version 3.0                                                                                #
#                                                                                            #
# - 3.0 Added: display label if found for Task action(s)                                     #
#       Added: Display entry vs exit Task type                                               #
#       Added: Support for many more Task Action codes                                       #
#       Added: Support for Action labels                                                     #
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
# import xml.etree.ElementTree
import easygui as g
import xml.etree.ElementTree as ET
import os
import sys
import webbrowser
import re

#  Global constants
project_color = 'Black'
profile_color = 'Blue'
task_color = 'Green'
unknown_task_color = 'Red'
scene_color = 'Purple'
bullet_color = 'Black'
action_color = 'Orange'
action_label_color = 'Magenta'
browser = 'Google Chrome.app'
line_spacing = '0.0001em'

help_text1 = 'This program reads a Tasker backup file and displays the configuration of Profiles/Tasks/Scenes\n\n'
help_text2 = 'Runtime options...\n\n  -h for this help\n\n  -d0 for no Task action details (silent)\n\n  -d1 display Task action details for unknown Tasks only (this is the default)\n\n ' \
             "-d2 for full Task action details on every Task\n\n -l for list style output\n\n  -v for this program's version."

caveat1 = 'CAVEATS:\n'
caveat2 = '- Most but not all Task actions have been mapped and will display as such.\n'
caveat3 = '- Some actions, variables and/or labels may display content in a different.  These colors are typically imbedded in the content as native html.'
caveat4 = '- This has only been tested on my own backup.xml file.  For problems, email mikrubin@gmail.com and attach your backup.xml file .'

unknown_task_name = 'Unnamed/Anonymous.'
my_version = '3.0'
my_file_name = '/MapTasker.html'
debug = False


# Get rid of embedded html that changes the font in any fashion
def get_label(the_label):
    lbl = the_label.replace('&lt', '')
    lbl = lbl.replace('&gt', '')
    p = re.compile(r'<.*?>')
    lbl = p.sub('', lbl)
    lbl = ' <span style = "color:' + action_label_color + '"</span>...with label: ' + lbl
    return lbl


# Chase after relevant data after <code> Task action
def get_action_detail(code_flag,code_child):
    if code_flag == 0:  # Just check for a label
        lbl = ''
        for child in code_child:
            if child.tag == 'label' and child.text is not None:
                if debug and 'FILTER FOR' in child.text:
                    print('kaka')
                lbl = get_label(child.text)
                return lbl
        return lbl
    elif code_flag == 1:  # Get first Str value
        lbl = ''
        for child in code_child:
            if child.tag == 'label' and child.text is not None:
                lbl = get_label(child.text)
            elif child.tag == 'Str' and child.text is not None:
                return child.text + lbl
        return ''
    elif code_flag == 2:  # Get first two string values
        count = 0
        var1 = ''
        var2 = ''
        lbl = ''
        for child in code_child:
            if child.tag == 'label' and child.text is not None:
                lbl = get_label(child.text)
            elif child.tag == 'Str' and child.text is not None and count == 0:
                count = 1
                var1 = child.text
            elif child.tag == 'Str' and child.text is not None and count == 1:
                var2 = child.text
            else:
                pass
        return var1, var2 + lbl
    elif code_flag == 3:  # Return first Int attrib
        lbl = ''
        for child in code_child:
            if child.tag == 'label' and child.text is not None:
                lbl = get_label(child.text)
            elif child.tag == 'Int' and child.attrib.get('val') is not None:
                return child.attrib.get('val') + lbl
            else:
                for dchild in child:
                    if dchild.tag == 'var' and dchild.text is not None:
                        return dchild.text + lbl
        return lbl
    elif code_flag == 4: # Get unlimited number of Str values
        var1 = []
        lbl = ''
        for child in code_child:
            if child.tag == 'label' and child.text is not None:
                lbl = get_label(child.text)
            elif child.tag == 'Str' and child.text is not None:
                var1.append(child.text)
        return var1, lbl
    elif code_flag == 5:   # Get Application info
        lbl = ''
        for child in code_child:
            if child.tag == 'label' and child.text is not None:
                lbl = get_label(child.text)
            elif child.tag == 'App':
                if child.find('appClass').text is not None:
                    app = child.find('appClass').text
                else:
                    app = ''
                if child.find('label').text is not None:
                    lbl1 = child.find('label').text
                else:
                    lbl1 = ''
                return app, lbl1 + lbl
        return '', lbl
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
        for cchild in code_action:
            if 'ConditionList' == cchild.tag:  # If statement...
                for children in cchild:
                    if 'Condition' == children.tag:
                        var1 = children.find('lhs')
                        var2 = children.find('op')
                        if var2.text == '0':
                            var3 = ' = '
                        elif var2.text == '1':
                            var3 = ' != '
                        elif var2.text == '2':
                            var3 = ' ~ '
                        elif var2.text == '3':
                            var3 = ' !~ '
                        elif var2.text == '6':
                            var3 = ' < '
                        elif var2.text == '7':
                            var3 = ' > '
                        elif var2.text == '12':
                            var3 = ' not set '
                        elif var2.text == '13':
                            var3 = ' is set '
                        else:
                            var3 = ' ? '
                        var4 = children.find('rhs')
                        if var4.text == None:
                            var4.text = ''
                        return "If " + var1.text + var3 + var4.text

    elif taskcode == '38':
        return "End If" + get_action_detail(0, code_action)

    elif taskcode == '39':
        detail1, detail2 = get_action_detail(2, code_action)
        return "For " + detail1 + ' to ' + detail2

    elif taskcode == '40':
        return "End For or Stop" + get_action_detail(0, code_action)

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

    elif taskcode == '51':
        return "Element Text " + get_action_detail(1, code_action)

    elif taskcode == '54':
        return "Element Text Colour " + get_action_detail(1, code_action)

    elif taskcode == '55':
        return "Element Back Colour " + get_action_detail(1, code_action)

    elif taskcode == '58':
        det1, det2 = get_action_detail(2,code_action)
        return "Element Size for Scene " + det1 + ' to ' + det2

    elif taskcode == '61':
        return "Vibrate time at  " + get_action_detail(3,code_action)

    elif taskcode == '62':
        return "Vibrate Pattern of " + get_action_detail(1, code_action)

    elif taskcode == '66':
        return "Element Image " + get_action_detail(1, code_action)

    elif taskcode == '71':
        return "Element Text Size " + get_action_detail(1, code_action)

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
        return "Perform Task " + get_action_detail(1, code_action)

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

    elif taskcode == '248':
        return "Turn Off" + get_action_detail(0, code_action)

    elif taskcode == '294':
        return "Bluetooth" + get_action_detail(0, code_action)

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

    elif taskcode == '312':
        return "Do Not Disturb" + get_action_detail(0, code_action)

    elif taskcode == '331':
        return "Auto-Sync" + get_action_detail(0, code_action)

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

    elif taskcode == '394':
        return "Parse/Format DateTime " + get_action_detail(0, code_action)

    elif taskcode == '400':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Move (file) from " + detail1 + ' to ' + detail2

    elif taskcode == '406':
        return "Delete File " + get_action_detail(1, code_action)

    elif taskcode == '409':
        return "Create Directory " + get_action_detail(1, code_action)

    elif taskcode == '410':
        return "Write File " + get_action_detail(1, code_action)

    elif taskcode == '417':
        detail1, detail2 = get_action_detail(2, code_action)
        return "Read File " + detail1 + ' into ' + detail2

    elif taskcode == '425':
        return "Turn Wifi" + get_action_detail(0, code_action)

    elif taskcode == '430':
        return "Restart Tasker" + get_action_detail(0, code_action)

    elif taskcode == '433':
        return 'Mobile Data' + get_action_detail(0, code_action)

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
            detail2 = detail2 + ' , ' + item
        return 'Notify ' + detail2 + ' ' + lbl

    elif taskcode == '536':
        return "Notification Vibrate with title " + get_action_detail(1, code_action)

    elif taskcode == '538':
        return "Notification Sound with title " + get_action_detail(1, code_action)

    elif taskcode == '545':
        return "Variable Randomize " + get_action_detail(1, code_action)

    elif taskcode == '547':   # HERE
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

    elif taskcode == '902':
        return "Get Locations " + get_action_detail(1, code_action)

# Plugins start here

    elif taskcode == '117240295':
        return "AutoWear Input" + get_action_detail(0, code_action)

    elif taskcode == '140618776':
        return "AutoWear Toast" + get_action_detail(0, code_action)

    elif taskcode == '191971507':
        return "AutoWear ADB Wifi" + get_action_detail(0, code_action)

    elif taskcode == '234244923':
        return "AutoInput Unlock Screen" + get_action_detail(0, code_action)

    elif taskcode == '268157305':
        return "AutoNotification Tiles" + get_action_detail(0, code_action)

    elif taskcode == '319692633':
        return "AutoShare Process Text" + get_action_detail(0, code_action)

    elif taskcode == '344636446':
        return "AutoVoice Trigger Alexa Routine" + get_action_detail(0, code_action)

    elif taskcode == '557649458':
        return "AutoWear Time" + get_action_detail(0, code_action)

    elif taskcode == '565385068' or taskcode == '166160670':
        return "AutoNotification " + get_action_detail(0, code_action)

    elif taskcode == '774351906':
        return "Join Action" + get_action_detail(0, code_action)

    elif taskcode == '778682267':
        return "AutoInput Gestures" + get_action_detail(0, code_action)

    elif taskcode == '811079103':
        return "AutoInput Action" + get_action_detail(0, code_action)

    elif taskcode == '906355163':
        return "AutoWear Voice Screen" + get_action_detail(0, code_action)

    elif taskcode == '1099157652':
        return "AutoTools Json Write" + get_action_detail(0, code_action)

    elif taskcode == '1040876951':
        return "AutoInput UI Query" + get_action_detail(0, code_action)

    elif taskcode == '1165325195':
        return "AutoTools Web Screen" + get_action_detail(0, code_action)

    elif taskcode == '1250249549':
        return "AutoInput Screen Off/On" + get_action_detail(0, code_action)

    elif taskcode == '1246578872':
        return "AutoWear Notification" + get_action_detail(0, code_action)

    elif taskcode == '1304982781':
        return "AutoTools Dialog" + get_action_detail(0, code_action)

    elif taskcode == '1410790256':
        return "AutoWear Floating Icon" + get_action_detail(0, code_action)

    elif taskcode == '1830829821':
        return "AutoWear 4 Screen" + get_action_detail(0, code_action)

    elif taskcode == '1957670352':
        return "AutoWear App" + get_action_detail(0, code_action)

    elif taskcode == '1339942270' or taskcode == '1620773086':
        return "SharpTools" + get_action_detail(0, code_action)

    elif taskcode == '1447159672':
        return "AutoTools Text" + get_action_detail(0, code_action)

    elif taskcode == '1508929357':
        return "AutoTools" + get_action_detail(0, code_action)

    elif taskcode == '1830656901':
        return "AutoWear List Screens" + get_action_detail(0, code_action)

    elif taskcode == '1732635924':
        return "AutoInput Gestures" + get_action_detail(0, code_action)

    elif 1000 < int(taskcode):
        return "Call to Plugin" + get_action_detail(0, code_action)

    else:
        return "Code " + taskcode + " not yet mapped"


# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
def ulify(element, out_style, out_unknown, lvl=int):   # lvl=0=heading 1=start list 2=Task/Profile/Scene 3=end list 4=special Task
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
        elif 'Task:' in element:  # Task ========================
            if out_style == 'L':
                if out_unknown == 1:
                    string = '<p style = "color:' + unknown_task_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + element + '\n'
                else:
                    string = '<p style = "color:' + task_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + element + '\n'
            else:
                if out_unknown == 1:
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
                tmp = element.replace('Action: ...','Action continued:')
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
def my_output(out_file, list_level, style, unknown, out_string):
    if 'Scene:' in out_string and 'L' == style:  # Handle special condition for Scenes in Linear mode.
        temp_element = out_string
        out_string = '<p style = "color:' + scene_color + ';line-height:' + line_spacing + '"'
        out_file.write(ulify(out_string, style, unknown, list_level))
        out_string = temp_element
    out_file.write(ulify(out_string, style, unknown, list_level))
    if debug:
        print('out_string:',ulify(out_string, style, unknown, list_level))
    return


# Construct Task Action output line
def build_action(alist, tcode, achild):
    if tcode != '':
        newline = tcode.find('\n')  # Break-up new line breaks
        tcode_len = len(tcode)
        if newline == -1 or tcode_len < 200:
            alist.append(tcode)
        else:
            array_of_lines = tcode.split('\n')
            count = 0
            for item in array_of_lines:
                if count == 0:
                    alist.append(item)
                else:
                    alist.append('...' + item)
                count =+ 1
    else:
        alist.append('Action ' + achild.text + ': not yet mapped')
    return


# Shell sort for Action list
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
        for action in task_actions:
            count_of_actions += 1
        # sort the Actions by attrib sr (e.g. sr='act0', act1, act2, etc.) to get them in true order
        shellSort(task_actions,count_of_actions)
        #reorder_attributes(task_actions)
        for action in task_actions:
            for child in action:
                try:
                    # Check for Task's "code"
                    if 'code' == child.tag:  # Get the specific Task Action code
                        task_code = getcode(child, action)
                        if debug:
                            print('Task ID:',current_task.attrib['sr'],' Code:',child.text,' task_code:',task_code,'Action attr:',action.attrib)
                        build_action(tasklist, task_code, child)
                    else:
                        pass
                except Exception as e:
                    pass
    return tasklist


# Get the name of the task given the Task ID
# return the Task's element and the Task's name
def get_task_name(the_task_id, all_the_tasks, found_tasks, the_task_list, task_type):
    task_name = ''
    for task in all_the_tasks:
        if the_task_id == task.find('id').text:
            found_tasks.append(the_task_id)
            try:
                task_name = task.find('nme').text
                if task_type == 'Exit':
                    the_task_list.append(task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task&nbsp;&nbsp;Task ID: ' + the_task_id)
                else:
                    the_task_list.append(task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task&nbsp;&nbsp;Task ID: ' + the_task_id)
            except Exception as e:
                if task_type == 'Exit':
                    the_task_list.append(unknown_task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task&nbsp;&nbsp;Task ID: ' + the_task_id)
                else:
                    the_task_list.append(unknown_task_name + '&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task&nbsp;&nbsp;Task ID: ' + the_task_id)
            break
    return task, task_name


# Process Task/Scene text/line item: call recursively for Tasks within Scenes
def process_list(list_type, the_output, the_list, all_task_list, all_scene_list, the_task, the_style, the_unknown, tasks_found, detail):
    my_count = 0
    if the_style != 'L':
        my_output(the_output, 1, the_style, the_unknown, '')  # Start list_type list
        have_task = ''
    for the_item in the_list:
        if debug:
            print('the_item:',the_item,' list_type:',list_type)
        if my_count > 0 and the_style == 'L':  # If more than one list_type, skip normal output
            my_output(the_output, 2, the_style, the_unknown, '<br>&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + list_type + '&nbsp;' + the_item + '<br>')
        else:
            my_output(the_output, 2, the_style, the_unknown, list_type + '&nbsp;' + the_item)
            my_count += 1
        # Output Actions for this Task if displaying detail and Task is unknown
        # Do we get the Task's Actions?
        if ('Task:' in list_type and (detail > 0 and (the_unknown > 0 or unknown_task_name in the_item))) or ('Task:' in list_type and detail == 2):
            if unknown_task_name in the_item or detail > 0:  # If Unknown task, then "the_task" is not valid, and we have to find it.
            # if unknown_task_name in the_item or detail == 1:   # If Unknown task, then "the_task" is not valid, and we have to find it.
                if '⎯Task:' in list_type:   # -Task: = Scene rather than a Task
                    temp = ["x", the_item]
                else:
                    temp = the_item.split('ID: ')  # Unknown/Anonymous!  Task ID: nn    << We just need the nn
                if len(temp) > 1:
                    the_task, kaka = get_task_name(temp[1], all_task_list, tasks_found, [temp[1]], '')
            alist = get_actions(the_task)  # Get the Task's Actions
            if alist:
                my_output(the_output, 1, the_style, False, '')  # Start Action list
                for taction in alist:
                    if taction is not None:
                        if 'Label for' in taction:
                            my_output(the_output, 2, the_style, False, taction)
                        else:
                            my_output(the_output, 2, the_style, False, 'Action: ' + taction)
                my_output(the_output, 3, the_style, False, '')  # Close Action list
        # Must be a Scene.  Look for all "Tap" Tasks for Scene
        elif 'Scene:' == list_type:
            scene_task_list = []
            getout = 0
            for my_scene in the_list:   # Go through each Scene to find TAP and Long TAP Tasks
                for scene in all_scene_list:
                    for child in scene:
                        if child.tag == 'nme' and child.text == my_scene:  # Is this our Scene?
                            for cchild in scene:   # Go through sub-elements in the Scene element
                                if 'ListElement' == cchild.tag or 'TextElement' == cchild.tag or 'ImageElement' == cchild.tag:
                                    for subchild in cchild:   # Go through ListElement sub-items
                                        if 'click' in subchild.tag:
                                        #if subchild.tag == 'itemclickTask' or subchild.tag == 'itemlongclickTask' or subchild.tag == 'clickTask':
                                            scene_task_list.append(subchild.text)
                                            temp_task_list = [subchild.text]
                                            task_element, name_of_task = get_task_name(subchild.text, all_task_list, tasks_found, temp_task_list, '')
                                            temp_task_list = [subchild.text]  # reset to task name since get_task_name changes it's value
                                            if subchild.tag == 'itemclickTask' or subchild.tag == 'clickTask':
                                                task_type = '⎯Task: TAP&nbsp;&nbsp;ID:'
                                            elif 'long' in subchild.tag:
                                            # elif subchild.tag == 'itemlongclickTask':
                                                task_type = '⎯Task: LONG TAP&nbsp;&nbsp;ID:'
                                            process_list(task_type, the_output, temp_task_list, all_task_list,
                                                         all_scene_list, task_element, the_style,
                                                         1, tasks_found, detail) # Call ourselves iteratively
                                        elif subchild.tag == 'Str':
                                            break
                                    if scene_task_list:  # Display Tasks for Scene if we have 'em
                                        for the_scene_task in scene_task_list:  # Now add Task to the Task list.
                                            tasks_found.append(the_scene_task)  # < Fix
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
        my_output(the_output, 3, the_style, False, '')  # Close list_type list
        return


# Main program here >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Main program here >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>        
def main():
    task_list = []
    found_tasks = []
    display_detail = 1     # Default display detail: unknown Tasks actions only

    output_style = 'L'  # L=linear, default=bullet
    help_text = help_text1 + help_text2
    # Get any arguments passed to program
    for i, arg in enumerate(sys.argv):
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
        else:
            if 'MapTasker.py' not in arg:
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

    # Store the output in the same directory
    my_output_dir = os.getcwd()
    if my_output_dir is None:
        g.textbox(msg="MapTasker cancelled", title="MapTasker", text="An error occurred.  Program cancelled.")
        exit(2)
    out_file = open(my_output_dir + my_file_name, "w")

    # Import xml
    tree = ET.parse(filename)
    root = tree.getroot()
    all_scenes = root.findall('Scene')
    all_tasks = root.findall('Task')
    if 'TaskerData' != root.tag:
        my_output(out_file, 0, output_style, False, 'You did not select a Tasker backup XML file...exit 2')
        exit(3)

    my_output(out_file, 0, output_style, False, 'Tasker Mapping................')
    my_output(out_file, 1, output_style, False, '')  # Start Project list

    # Traverse the xml

    # Start with Projects <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    for project in root.findall('Project'):
        project_name = project.find('name').text
        project_pids = ''
        my_output(out_file, 2, output_style, False, 'Project: ' + project_name)

        # Get Profiles and it's Project and Tasks
        my_output(out_file, 1, output_style, False, '')  # Start Profile list
        try:
            project_pids = project.find('pids').text  # Project has no Profiles
        # except xml.etree.ElementTree.ParseError doesn't compile:
        except Exception:
            my_output(out_file, 2, output_style, False, 'Profile: none or unnamed!')
        if project_pids != '':  # Project has Profiles?
            profile_id = project_pids.split(',')

            # Now find the Profile's Tasks for this Project <<<<<<<<<<<<<<<<<<<<<
            for item in profile_id:
                for profile in root.findall('Profile'):
                    # XML search order: id, mid"n", nme = Profile id, task list, Profile name
                    # Get the Tasks for this Profile
                    if item == profile.find('id').text:  # Is this the Profile we want?
                        task_list = []  # Get the Tasks for this Profile
                        task_id_list = []
                        for child in profile:
                            if 'mid' in child.tag:
                                task_type = 'Entry'
                                if 'mid1' == child.tag:
                                    task_type = 'Exit'
                                task_id = child.text
                                task_id_list.append(task_id)
                                if debug and task_id == '100':
                                    print('====================================',task_id,'====================================')
                                our_task_element, our_task_name = get_task_name(task_id, all_tasks, found_tasks, task_list, task_type)
                            elif 'nme' == child.tag:  # If hit Profile's name, we've passed all of the Task ids.
                                break
                        try:
                            profile_name = profile.find('nme').text  # Get Profile's name
                        except Exception as e:  # no Profile name
                            profile_name = 'None or unnamed!'
                        my_output(out_file, 2, output_style, False, 'Profile: ' + profile_name)

                # We have the Tasks.  Now let's output them.
                if task_list:
                    unknown_task = 0
                    process_list('Task:', out_file, task_list, all_tasks, all_scenes, our_task_element, output_style, unknown_task, found_tasks, display_detail)

        # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        scene_names = ''
        try:
            scene_names = project.find('scenes').text
        except Exception as e:
            pass
        if scene_names != '':
            scene_list = scene_names.split(',')
            process_list('Scene:', out_file, scene_list, all_tasks, all_scenes, our_task_element, output_style, unknown_task, found_tasks, display_detail)

        my_output(out_file, 3, output_style, False, '')  # Close Profile list
    my_output(out_file, 3, output_style, False, '')  # Close Project list

    # Now let's look for Tasks that are not referenced by Profiles and display a total count
    task_name = ''
    unnamed_tasks = 0
    have_heading = 0
    projects_with_no_tasks = []
    for task in all_tasks:  # Get a/next Task
        unknown_task = 0
        task_id = task.find('id').text
        if task_id not in found_tasks:  # We have a solo Task
            # project_name = ''  # Find the Project it belongs to
            for project in root.findall('Project'):
                project_name = project.find('name').text
                project_tasks = ''
                try:
                    project_tasks = project.find('tids').text
                except Exception as e:  # Project has no Tasks
                    if project_name not in projects_with_no_tasks:
                        projects_with_no_tasks.append(project_name)
                    project_name = '-none found'
                    pass
                if task_id in project_tasks:
                    # project_name = project.find('name').text
                    break

            # At this point, we've found the Project this Task belongs to, or it doesn't belong to any Task
            if have_heading == 0:
                my_output(out_file, 0, output_style, False, '<hr>') # blank line
                my_output(out_file, 0, output_style, False, 'Tasks that are not in any Profile (may be a desktop Tasker Task/widget or Task in a Scene)...')
                my_output(out_file, 1, output_style, False, '')  # Start Task list
                have_heading = 1

            # Get the Task's name
            try:
                task_name = task.find('nme').text
            except Exception as e:  # Task name not found!
                unnamed_tasks += 1
                # Unknown Task.  Display details if requested
                task_name = unknown_task_name + '&nbsp;&nbsp;Task ID: ' + task_id
                unknown_task = 1
                if  display_detail > 0:
                    action_list = []
                    action_list = get_actions(task)

            # Identify which Project Task belongs to
            if unknown_task == 0 and project_name:
                task_name += ' with Task ID ' + task_id + ' ...in Project ' + project_name
                project_name = ''

            # Output the unknown Task's details
            if unknown_task == 0 or display_detail > 0:  # Only list named Tasks or if details are wanted
                task_list = [task_name]
                # This will output the task and it's Actions if displaying details
                process_list('Task:', out_file, task_list, all_tasks, all_scenes, task, output_style, unknown_task, found_tasks, display_detail)
            unknown_task = 0

    # Provide total number of unnamed Tasks
    if unnamed_tasks > 0:
        if output_style == 'L' or display_detail > 0:
            my_output(out_file, 0, output_style, False, '')  # line
            if output_style == 'L':
                my_output(out_file, 4, output_style, False, '<p style = "color:' + profile_color + ';line-height:normal"></p>\n')  # line spacing back to normal
        my_output(out_file, 3, output_style, False, '')  # Close Task list
        my_output(out_file, 0, output_style, False, '<font color=' + unknown_task_color +'>There are a total of ' + str(unnamed_tasks) + ' unnamed Tasks!!!')
    if task_name is True:
        my_output(out_file, 3, output_style, False, '')  # Close Task list
    my_output(out_file, 3, output_style, False, '')  # Close out the list

    # List Projects with no Tasks
    if len(projects_with_no_tasks) > 0:
        my_output(out_file, 0, output_style, False, '<hr><font color=Black>')  # line
        for item in projects_with_no_tasks:
            my_output(out_file, 4, output_style, False, 'Project ' + item + ' has no Tasks')

    # Let's wrap things up...
    # Output caveats if we are displaying the Actions
    my_output(out_file, 0, output_style, False, '<hr>')  # line
    my_output(out_file, 4, output_style, False, caveat1)  # caveat
    if display_detail > 0:  # Caveat about Actions
        my_output(out_file, 4, output_style, False, caveat2)  # caveat
    my_output(out_file, 4, output_style, False, caveat3)  # caveat
    my_output(out_file, 4, output_style, False, caveat4)  # caveat

    out_file.close()

    for elem in tree.iter():
        elem.clear()
    all_tasks.clear()
    all_scenes.clear()
    project.clear()
    profile.clear()
    root.clear()

    # Display final output
    webbrowser.open('file://' + my_output_dir + my_file_name, new=2)
    g.textbox(msg="MapTasker Done", title="MapTasker",
              text="You can find 'MapTasker.html' in the same folder as your backup xml file.  Your browser has displayed it in a new tab.  Program end.")


# Main call
if __name__ == "__main__":
    main()
