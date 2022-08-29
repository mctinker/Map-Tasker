#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# MapTasker: read the Tasker backup file to map out the configuration                        #
#                                                                                            #
# Requirements                                                                               #
#      1- Python version 3.10 or higher                                                      #
#      2- Your Tasker backup.xml file, uploaded to your MAC                                  #
#                                                                                            #
# Note: This should work on PC OS's other than a MAC, but it has not been tested             #
#       on any other platform.                                                               #
#                                                                                            #
# Add the following statement (without quotes) to your Terminal Shell configuration file     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                          #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                           #
#  "export TK_SILENCE_DEPRECATION = 1"                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# Version 6.3                                                                                #
#                                                                                            #
# ########################################################################################## #

# importing tkinter and tkinter.ttk
# and all their functions and classes
from tkinter import *
# Add the following statement to your Terminal Shell configuration file (BASH, Fish, etc.
#  to eliminate the runtime msg: DEPRECATION WARNING: The system version of Tk is deprecated and may be removed...
#  export TK_SILENCE_DEPRECATION = 1

# importing askopenfile (from class filedialog) and messagebox functions
from tkinter.filedialog import askopenfile
from tkinter import messagebox

# imports for keeping track of number of runs
#from __future__ import print_function
import atexit
from os import path
from json import dumps, loads


import xml.etree.ElementTree as ET
import os
import sys
import webbrowser
import re
import logging

#  START User-modifiable global constants #########################################################################
project_color = 'Black'   # Refer to the following for valid names: https://htmlcolorcodes.com/color-names/
profile_color = 'Blue'
disabled_profile_color = 'Red'
launcher_task_color = 'Chartreuse'
task_color = 'Green'
unknown_task_color = 'Red'
scene_color = 'Purple'
bullet_color = 'Black'
action_color = 'Orange'
action_label_color = 'Magenta'
action_condition_color = 'Coral'
disabled_action_color = 'Crimson'
profile_condition_color = 'Turquoise'
background_color = 'Lavender'

output_font = 'Courier'    # OS X Default monospace font
# output_font = 'Roboto Regular'    # Google monospace font
#  END User-modifiable global constants ##########################################################################

unknown_task_name = 'Unnamed/Anonymous.'
no_project = '-none found.'
counter_file = '.MapTasker_RunCount.txt'

# Initial logging and debug mode
debug = False    # Controls the output of IDs / codes
debug_out = False  # Prints the line to be added to the output
logger = logging.getLogger('tipper')
# logger.setLevel(logging.DEBUG)

logger.info('info message')

# The following are not used at this time
# logger.warning('warn message')
# logger.error('error message')
# logger.critical('critical message')
logger.addHandler(logging.StreamHandler())


def read_counter():
    return loads(open(counter_file, 'r').read()) + 1 if path.exists(counter_file) else 0


def write_counter():
    with open(counter_file, 'w') as f:
        f.write(dumps(counter))

counter = read_counter()
atexit.register(write_counter)

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
    match operation:
        case '0':
            the_operation = ' = '
        case'1':
            the_operation = ' != '
        case '2':
            the_operation = ' ~ '
        case '3':
            the_operation = ' !~ '
        case '6':
            the_operation = ' < '
        case '7':
            the_operation = ' > '
        case '12':
            the_operation = ' is set'
        case '13':
            the_operation = ' not set'
        case _:
            the_operation = ' ? '
    if 'set' not in the_operation and child.find('rhs').text is not None:  # No second string fort set/not set
        second_string = child.find('rhs').text
    else:
        second_string = ''

    return first_string, the_operation, second_string


# Get Task's label, disabled flag and any conditions
def get_label_disabled_condition(child):
    disabled_action_html = ' <span style = "color:' + disabled_action_color + '"</span>[DISABLED]'

    task_label = ''
    action_disabled = ''
    task_conditions = ''
    booleans = []
    the_action_code = child.find('code').text
    if child.find('label') is not None:
        lbl = strip_string(child.find('label').text)
        if lbl != '' and lbl != '\n':
            lbl.replace('\n', '')
            task_label = ' <span style = "color:' + action_label_color + '"</span>...with label: ' + lbl
    if child.find('on') is not None:  # disabled action?
        action_disabled = disabled_action_html
    if child.find('ConditionList') is not None:  # If condition on Action?
        condition_count = 0
        boolean_to_inject = ''
        for children in child.find('ConditionList'):
            if 'bool' in children.tag:
                booleans.append(children.text)
            elif 'Condition' == children.tag and the_action_code != '37':
                string1, operator, string2 = evaluate_condition(children)
                if condition_count != 0:
                    boolean_to_inject = booleans[condition_count-1].upper() + ' '
                task_conditions = task_conditions + ' <span style = "color:' + action_condition_color + '"</span> (' + \
                    boolean_to_inject + 'condition:  If ' + string1 + operator + string2 + ')'
                condition_count += 1
    return task_conditions + action_disabled + task_label


# Convert a list of items to a comma-separated string of items
def list_to_string(the_list):
    if the_list is not None:
        s = ', '
        the_string = s.join(the_list)
        return the_string
    else:
        return ''

#  Given an action code (xml), find Int (integer) args and match with names
#  Example:
#  3 Ints with arg0, arg1 and arg2, to be filled in with their matching name0, name1 and name2 + the associated text
#  action = xml element for Action <code>
#  arguments = list of Int arguments to look for (e.g. arg1,arg5,arg9)
#  names = list of entries to substitute the argn value against.  It can be a list, which signifies a pulldown list of options to map[ against.
def get_xml_int_argument_to_value(action, arguments, names):
    match_results = []
    for child in action:
        if 'Int' == child.tag:
            the_arg = child.attrib.get('sr')
            for arg in arguments:
                if arg == the_arg:
                    arg_location = arguments.index(arg)
                    if child.attrib.get('val') is not None:
                        the_int_value = child.attrib.get('val')
                        if type(names[arg_location]) is list:
                            the_list = names[arg_location]
                            the_title = the_list[0]  # Title is first element in the list
                            idx = 0
                            running = True
                            # Loop through list two items at a time: 1st element is digit, 2nd element is the name to apply if it matches.
                            while running:
                                idx = (idx + 1) % len(the_list)  # Get next element = first element in pair
                                this_element = the_list[idx]
                                if this_element.isdigit:   # First element of pair must be a digit
                                    idx = (idx + 1) % len(the_list)
                                    next_element = the_list[idx]  # Second element in pair
                                    if ' Close After (seconds):' == next_element:
                                        print('kaka')
                                    if this_element == the_int_value:
                                        match_results.append(the_title + next_element + ', ')
                                        break
                                    idx = (idx + 1) % len(the_list)
                                    if idx > len(the_list):
                                        break
                                else:
                                    exit(8)   #  Rutroh...not an even pair of elements
                            break  # Get out of arg loop and get next child
                        else:   # Not a list
                            match_results.append(names[arg_location] + the_int_value)  # Just grab the integer value
                            break
                    else:
                        match_results.append('')
    return match_results


#  Given an action code (xml), find Str (string) args and match with names
#  Example:
#  3 Strs with arg0, arg1 and arg2, to be filled in with their matching name0, name1 and name2 + the associated text
def get_xml_str_argument_to_value(action, arguments, names):
    match_results = []
    for child in action:
        if 'Str' == child.tag:
            the_arg = child.attrib.get('sr')
            for arg in arguments:
                if arg == the_arg:
                    arg_location = arguments.index(arg)
                    if child.text is not None:
                        match_results.append(names[arg_location] + child.text + ', ')
                    else:
                        match_results.append('')
    return match_results


# Chase after relevant data after <code> Task action
# code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
def get_action_detail(code_flag, code_child, action_type):
    switch_types = ['Off', 'On', 'Toggle']
    if action_type:    # Only get extras if this is a Task action (vs. a Profile condition)
        extra_stuff = get_label_disabled_condition(code_child)  # Look for extra Task stiff: label, disabled, conditions
    else:
        extra_stuff = ''
    if debug and action_type:  # Add the code if this is an Action
        extra_stuff = extra_stuff + '<font color=red> code:' + code_child.find('code').text
    child = code_child.find('se')
    if child is not None:
        if child.text == 'false':
            extra_stuff = ' [Continue Task After Error]' + extra_stuff

    # Figure out what to do based on the input variable code_flag
    match code_flag:
    # Just check for a label
        case 0:
            return extra_stuff

    # Get first Str value
        case 1:
            var1 = code_child.find('Str')
            if var1 is not None:
                if var1.text is not None:
                    return strip_string(var1.text) + extra_stuff
            return extra_stuff

    # Get first two string values
        case 2:
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

    # Return first Int attrib
        case 3:
            var1 = code_child.find('Int')
            if var1 is not None:
                if var1.attrib.get('val') is not None:
                    return var1.attrib.get('val'), extra_stuff
            return '', extra_stuff

    # Get unlimited number of Str values
        case 4:
            var1 = [child.text for child in code_child.findall('Str') if child.text is not None]
            for item in var1:
                strip_string(item)
            return var1, extra_stuff

    # Get Application info
        case 5:
            child = code_child.find('App')
            if child is not None:
                if child.tag == 'App':
                    if child.find('appClass') is None:
                        return '', ''
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

    # Get Plugin parameters
        case 6:
            child1 = code_child.find('Bundle')
            child2 = child1.find('Vals')
            child3 = child2.find('com.twofortyfouram.locale.intent.extra.BLURB')
            if child3 is not None and child3.text is not None:
                clean_string = child3.text.replace('</font><br><br>', '<br><br>')
                clean_string = clean_string.replace('&lt;', '<')
                clean_string = clean_string.replace('&gt;', '>')
                clean_string = clean_string.replace('<big>', '')
                return clean_string + extra_stuff  # Get rid of extra </font>
            else:
                return extra_stuff

    # Return first Int attrib as interpreted value: off, on, toggle
        case 7:
            for child in code_child:
                temp = child.attrib.get('val')
                if child.tag == 'Int' and temp is not None:
                    return switch_types[int(temp)] + extra_stuff
                else:
                    continue
            return extra_stuff

    # Return all Int attrib
        case 8:
            my_int = [child.attrib.get('val') for child in code_child if child.tag == 'Int' and child.attrib.get('val') is not None]
            return my_int, extra_stuff

        # Return first Str and first Int attrib
        case 9:
            var1 = code_child.find('Str')
            if var1 is not None:
                if var1.text is not None:
                    the_string = var1.text
                else:
                    the_string = ''
            var1 = code_child.find('Int')
            if var1 is not None:
                if var1.attrib.get('val') is not None:
                    the_integer = var1.attrib.get('val')
                else:
                    the_integer = ''
                    return var1.attrib.get('val'), extra_stuff
            return the_string, the_integer, extra_stuff
        case _:
            return '???'


##############################################################################################################
#                                                                                                            #
#  getcode: given the xml <code>nn</code>, figure out what (action) code it is and return the translation    #
#                                                                                                            #
#          code_child: used to parse the specific <code> xml for action details.                             #
#          code_action: the nnn in <code>nnn</code> xml                                                      #
#          type_action: true if Task action, False if not (e.g. a Profile state or event condition)          #
#                                                                                                            #
##############################################################################################################
def getcode(code_child, code_action, type_action):
    immersive_modes = ['Off', 'Hide Status Bar', 'Hide Navigation Bar', 'Hide Both', 'Toggle Last']
    rotation_types = ['Off', 'Portrait', 'Portrait Reverse', 'Landscape', 'Landscape Reverse']
    battery_status = ['Normal', 'Battery Saver', 'Toggle']
    quick_setting_status = ['Active', 'Inactive', 'Disabled']
    custom_setting_status = ['Global', 'Secure', 'System']
    location_mode_status = ['Off', 'Device Only', 'Battery Saving', 'High Accuracy']
    goto_type = ['Action Number', 'Action Loop', 'Top of Loop', 'End of Loop', 'End of If']
    ringtone_type = ['Alarm', 'Notification', 'Ringer']
    stayon_type = ['Never', 'With AC Power', 'With USB Power', 'With AC or USB Power', 'With Wireless Power',
                   'With Wireless or AC Power', 'With Wireless or USB Power', 'With Wireless, AC or USB Power']
    test_display_type = ['AutoRotate', 'Orientation', 'DPI', 'Available Resolution', 'Hardware Resolution',
                         'Is Locked', 'Is Securely Locked', 'Display Density', 'Navigation Bar Height',
                         'Navigation Bar Top Offset', 'Navigation Bar Top Offset', 'Status Bar Offset']
    filter_type = ['Black and White', 'Enhance Blue', 'Enhance Green', 'Greyscale', 'Set Alpha']
    button_type = ['Button', 'Toggle', 'Range', 'Toggle Range', 'No Action']
    media_type = ['Call', 'System', 'Ringer', 'Media', 'Alarm', 'Notification']
    cmd_type = ['Next', 'Pause', 'Previous', 'Toggle Pause', 'Stop', 'Play [Simulated Only]', 'Rewind', 'Fast Forward']
    location_type = ['Normal', 'Satellite', 'Terrain', 'Hybrid', 'None']
    format_type = ['MP4', '3GPP', 'AMR Narrowband', 'AMR Wideband', 'Hgd']
    source_type = ['Default', 'Microphone', 'Call Outgoing', 'Call Incoming', 'Call']
    test_media_type = ['Music File Artist Tag', 'Music File Duration Tag', 'Music File Title Tag', 'Music Playing Position',
                  'Music Playing Position Millis']
    no_yes = ['No', 'Yes']

    task_code = code_child.text

    # Start the search for the code and provide the results
    match task_code:
        case '15':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Lock ' + list_to_string(detail1) + ' ' + lbl
        case '16':
            return 'System Lock' + get_action_detail(0, code_action, type_action)
        case '18':
            detail1, detail2 = get_action_detail(5, code_action, type_action)
            return 'Kill App package ' + detail1 + ' for app ' + detail2
        case '20':
            detail1, detail2 = get_action_detail(5, code_action, type_action)
            return 'Launch App ' + detail1 + ' with app/package ' + detail2
        case '22':
            return 'Load Last App' + get_action_detail(0, code_action, type_action)
        case '25':
            return 'Go Home' + get_action_detail(0, code_action, type_action)
        case '30':
            detail1, detail2 = get_action_detail(3, code_action, type_action)
            return 'Wait for ' + detail1 + detail2
        case '35':
            return 'Wait' + get_action_detail(0, code_action, type_action)
        case '37':
            extra_stuff = ''
            if type_action:
                extra_stuff = get_label_disabled_condition(code_action)  # Look for extra Task stiff: label, disabled, conditions
            for cchild in code_action:
                if 'ConditionList' == cchild.tag:  # If statement...
                    for children in cchild:
                        if 'Condition' == children.tag:
                            first_string, operator, second_string = evaluate_condition(children)
                            return 'If ' + first_string + operator + second_string + extra_stuff
        case '38':
            return 'End If' + get_action_detail(0, code_action, type_action)
        case '39':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'For ' + detail1 + ' to ' + detail2
        case '40':
            return 'End For' + get_action_detail(0, code_action, type_action)
        case '41':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Send SMS ' + det1 + ' message: ' + det2
        case '43':
            return 'Else/Else If' + get_action_detail(0, code_action, type_action)
        case '46':
            return 'Create Scene ' + get_action_detail(1, code_action, type_action)
        case '47':
            return 'Show Scene ' + get_action_detail(1, code_action, type_action)
        case '48':
            return 'Hide Scene ' + get_action_detail(1, code_action, type_action)
        case '49':
            return 'Destroy Scene ' + get_action_detail(1, code_action, type_action)
        case '50':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Element Value ' + det1 + ' Element: ' + det2
        case '51':
            return 'Element Text ' + get_action_detail(1, code_action, type_action)
        case '54':
            return 'Element Text Colour ' + get_action_detail(1, code_action, type_action)
        case '55':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Element Back Colour of screen ' + det1 + ' Element: ' + det2
        case '57':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Element Position  for Scene ' + detail1 + ' element ' + detail2
        case '58':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Element Size for Scene ' + det1 + ' to ' + det2
        case '61':
            detail1, detail2 = get_action_detail(3, code_action, type_action)
            return 'Vibrate time at  ' + detail1 + detail2
        case '62':
            return 'Vibrate Pattern of ' + get_action_detail(1, code_action, type_action)
        case '65':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Element Visibility ' + det1 + ' to element match of ' + det2
        case '66':
            return 'Element Image ' + get_action_detail(1, code_action, type_action)
        case '68':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Element Focus for scene: ' + det1 + ' element: ' + det2
        case '71':
            return 'Element Text Size ' + get_action_detail(1, code_action, type_action)
        case '100':
            return 'Search ' + get_action_detail(1, code_action, type_action)
        case '101':
            return 'Take Photo filename ' + get_action_detail(1, code_action, type_action)
        case '102':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Open File ' + detail1 + ' ' + detail2
        case '103':
            detail1, xtra = get_action_detail(8, code_action, type_action)
            return 'Light Level from ' + detail1[0] + ' to ' + detail1[1] + xtra
        case '104':
            return 'Browse URL ' + get_action_detail(1, code_action, type_action)
        case '105':
            return 'Set Clipboard To ' + get_action_detail(1, code_action, type_action)
        case '109':
            return 'Set Wallpaper ' + get_action_detail(1, code_action, type_action)
        case '112':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Run SLA4 Script ' + detail1 + ' ' + detail2
        case '113':
            return 'Wifi Tether ' + get_action_detail(7, code_action, type_action)
        case '118':
            return 'HTTP Get ' + get_action_detail(1, code_action, type_action)
        case '119':
            return 'Open Map, Navigate to ' + get_action_detail(1, code_action, type_action)
        case '123':
            return 'Run Shell ' + get_action_detail(1, code_action, type_action)
        case '126':
            return 'Return' + get_action_detail(0, code_action, type_action)
        case '129':
            return 'JavaScriptlet ' + get_action_detail(1, code_action, type_action)
        case '130':
            return 'Perform Task: ' + get_action_detail(1, code_action, type_action)
        case '131':
            return 'JavaScript ' + get_action_detail(1, code_action, type_action)
        case '133':
            return 'Set Tasker Pref' + get_action_detail(0, code_action, type_action)
        case '135':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            return 'Go To type ' + goto_type[int(detail1)] + detail2
        case '136':
            return 'Sound Effects set to ' + get_action_detail(7, code_action, type_action)
        case '137':
            return 'Stop' + get_action_detail(0, code_action, type_action)
        case '140':
            battery_levels, xtra = get_action_detail(8, code_action, type_action)
            if battery_levels:
                return 'Battery Level from ' + battery_levels[0] + ' to ' + battery_levels[1] + xtra
            else:
                return 'Battery Level' + get_label_disabled_condition(code_action)
        case '150':
            return 'Keyboard set ' + get_action_detail(7, code_action, type_action)
        case '156':
            the_arguments = ['arg1', 'arg2']  # Ints: Format, Locality, Best Timeing
            the_names = [[' Locality:', '0', 'English', '1', ' German/Deutsch'],
                         ' Beat Timing:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'MIDI Play  Format: Tasker, ' + the_int_values[0]+ the_int_values[1] + \
                   ' Score:' + get_action_detail(1, code_action, type_action)
        case '159':
            return 'Profile Status for ' + get_action_detail(1, code_action, type_action)
        case '160':
            return 'Wifi Connected ' + get_action_detail(1, code_action, type_action)
        case '162':
            detail1 = get_action_detail(1, code_action, type_action)
            state_flag = False
            for child in code_action:   # Get whether active or inactive
                if 'Int' == child.tag:
                    if state_flag and child.attrib.get('val') is not None:  # We need the 2nd Int
                        return 'Setup Quick Setting set to ' + quick_setting_status[int(child.attrib.get('val'))] + ' for name ' + detail1
                    else:
                        state_flag = True
        case '165':
            return 'Cancel Alarm' + get_action_detail(0, code_action, type_action)
        case '171':
            return 'Beep' + get_action_detail(0, code_action, type_action)
        case '172':
            detail1 = get_action_detail(1, code_action, type_action)
            return 'Morse ' + detail1
        case '173':
            return 'Network Access' + get_action_detail(0, code_action, type_action)
        case '171':
            return 'Power Mode' + get_action_detail(0, code_action, type_action)
        case '175':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            battery = battery_status[int(detail1[0])]
            return 'Power Mode set to ' + battery + ' ' + detail2
        case '176':
            return 'Take Screenshot file ' + get_action_detail(1, code_action, type_action)
        case '177':
            return 'Haptic Feedback set to ' + get_action_detail(7, code_action, type_action)
        case '185':
            detail1, lbl = get_action_detail(8, code_action, type_action)  # Get int
            detail3 = filter_type[int(detail1[0])]
            return 'Filter Image mode ' + detail3 + ' threshold:' + detail1[1] + lbl
        case '187':
            detail1 = get_action_detail(1, code_action, type_action)  # Get Str
            detail2, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints
            if detail2[1] == 1:
                detail3 = ' Delete From Memory After '
            else:
                detail3 = ''
            return 'Save Image image quality:' + detail2[0] + detail3 + ' file:' + detail1
        case '188':
            max_wh = ''
            lbl = get_action_detail(0, code_action, type_action)
            for child in code_action:   #  We have to traverse the xml here due to complexity
                if 'Img' == child.tag:
                    sub_child = child.find('nme')
                    if sub_child is not None:
                        the_image = child.find('nme').text
                elif 'Int' == child.tag:
                    sub_child = child.find('var')
                    if sub_child is not None:
                        if sub_child.text is not None:
                            max_wh = ' Max Height or Width:' + sub_child.text
                    else:  # Get second (or first) Int
                        if child.attrib.get('val') is not None:
                            if child.attrib.get('val') == '1':
                                detail2 = ' Respect EXIF Orientation'
                            else:
                                detail2 = ''
                        break
            return 'Load Image ' + the_image + max_wh + detail2 + lbl
        case '189':
            detail1, lbl = get_action_detail(8, code_action, type_action)
            return 'Crop Image from left:' + detail1[0] + ' from right:' + detail1[1] + ' from top:' + detail1[2] + ' from bottom:' + detail1[3] + lbl
        case '190':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            if detail1 == '0':
                detail1 = 'Horizontal'
            else:
                detail1 = 'Vertical'
            return 'Flip Image ' + detail1 + detail2
        case '191':
            detail1, detail2 = get_action_detail(8, code_action, type_action)  # Get all Ints
            if detail1[0] == '0':
                detail1 = 'Left'
            else:
                detail1 = 'Right'
            return 'Rotate Image ' + detail1 + detail2
        case '192':
            the_arguments = ['arg0', 'arg2']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Play Ringtone  Type:' + ringtone_type[int(the_int_values[0])] + ', Stream:' + media_type[int(the_int_values[1])] + \
            ', Sound:' + get_action_detail(1, code_action,type_action)
        case '193':
            return 'Resize Image ' + get_action_detail(1, code_action, type_action)
        case '194':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Test Scene ' + detail1 + ' store in ' + detail2
        case '195':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Test Element scene:  ' + det1 + ' element: ' + det2
        case '216':
            return 'App Settings ' + get_action_detail(1, code_action, type_action)
        case '203':
            return 'Date Settings ' + get_action_detail(0, code_action, type_action)
        case '214':
            return 'Wireless Settings' + get_action_detail(0, code_action, type_action)
        case '235':
            detail2, lbl = get_action_detail(3, code_action, type_action)
            detail1, lbl = get_action_detail(4, code_action, type_action)
            detail3 = ''
            for item in detail1:
                detail3 = detail3 + ' ' + item + ' '
            return 'Custom Settings type ' + custom_setting_status[int(detail2)] + ' ' + detail3 + lbl
        case '244':
            return 'Toggle Split Screen' + get_action_detail(0, code_action, type_action)
        case '245':
            return 'Back Button' + get_action_detail(0, code_action, type_action)
        case '246':
            return 'Long Power Button' + get_action_detail(0, code_action, type_action)
        case '247':
            return 'Show Recents' + get_action_detail(0, code_action, type_action)
        case '248':
            return 'Turn Off' + get_action_detail(0, code_action, type_action)
        case '249':
            return 'System Screenshot' + get_action_detail(0, code_action, type_action)
        case '254':
            return 'Speakerphone set to ' + get_action_detail(7, code_action, type_action)
        case '256':
            return 'Vibrate On Ringer set to ' + get_action_detail(7, code_action, type_action)
        case '259':
            return 'Notification Pulse set to ' + get_action_detail(7, code_action, type_action)
        case '294':
            return 'Bluetooth ' + get_action_detail(7, code_action, type_action)
        case '295':
            return 'Bluetooth ID ' + get_action_detail(1, code_action, type_action)
        case '296':
            return 'Bluetooth Voice ' + get_action_detail(7, code_action, type_action)
        case '300':
            return 'Anchor' + get_action_detail(0, code_action, type_action)
        case '301':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Mic Volume set to  ' + detail1 + lbl
        case '303':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Alarm Volume to  ' + detail1 + lbl
        case '304':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Ringer Volume to  ' + detail1 + lbl
        case '305':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                return 'Notification Volume to  ' + detail1 + lbl
            else:
                return 'Notification Volume' + lbl
        case '306':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'In-Call Volume set to  ' + detail1 + lbl
        case '307':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                return 'Media Volume to  ' + detail1 + lbl
            else:
                return 'Media Volume' + lbl
        case '308':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'System Volume to  ' + detail1 + lbl
        case '309':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'DTMF Volume to  ' + detail1 + lbl
        case '310':
            return 'Vibrate Mode set to ' + get_action_detail(7, code_action, type_action)
        case '311':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                return 'BT Voice Volume to ' + detail1 + lbl
        case '312':
            return 'Do Not Disturb' + get_action_detail(0, code_action, type_action)
        case '313':
            return 'Sound Mode' + get_action_detail(0, code_action, type_action)
        case '314':
            detail1, lbl = get_action_detail(4, code_action, type_action)   # All Strs
            detail2, lbl = get_action_detail(8, code_action, type_action)   # All Ints
            if detail2[0] is not None:
                if detail2[0] == '0':
                    the_type = 'Credentials'
                else:
                    the_type = 'Biometric'
            if detail2[3] is not None:
                the_timeout = ' timeout:' + detail2[3]
            else:
                the_timeout = ''
            return 'Authentication Dialog type ' + the_type + list_to_string(detail1) + the_timeout
        case '316':
            return 'Display Size' + get_action_detail(0, code_action, type_action)
        case '318':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                return 'Force Rotation ' + rotation_types[int(detail1)] + lbl
            else:
                return 'Force Rotation ' + lbl
        case '319':
            return 'Ask Permissions ' + get_action_detail(1, code_action, type_action)
        case '321':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'GD Upload ' + list_to_string(detail1) + ' ' + lbl
        case '324':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            detail2, lbl = get_action_detail(8, code_action, type_action)
            if detail2[0] == '0':
                detail3 = 'Remote Folder'
            else:
                detail3 = 'Query'
            if detail2[1] == '0':
                detail4 = 'Both'
            elif detail2[1] == '1':
                detail4 = 'Files'
            else:
                detail4 = 'Folders'
            return 'GD List type ' + detail3 + '  Files or Folders:' + detail4 + list_to_string(detail1) + ' ' + lbl
        case '325':
            detail1, lbl = get_action_detail(4, code_action, type_action)  # All Strs
            detail2, lbl = get_action_detail(8, code_action, type_action)  # All Ints
            detail3 = ' Trash Value:'
            if detail2[0] == '0':
                detail3 = detail3 + 'Trash'
            else:
                detail3 = detail3 + 'Remove From Trash'
            detail4 = ' Type:'
            if detail2[1] == '0':
                detail4 = detail4 + 'File ID'
            else:
                detail4 = detail4 + 'Remote Path'
            return 'GD Trash' + detail3 + detail4 + ' ' + list_to_string(detail1) + ' ' + lbl
        case '326':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            detail2, lbl = get_action_detail(3, code_action, type_action)
            if detail2 == '0':
                detail2 = 'File ID'
            else:
                detail2 = 'Remote Path'
            return 'GD Download type ' + detail2 + ' ' + list_to_string(detail1) + ' ' + lbl
        case '327':
            detail1 = get_action_detail(1, code_action, type_action)
            detail2, lbl = get_action_detail(3, code_action, type_action)
            if detail2 == '1':
                detail2 = ' with Full Access '
            else:
                detail2 = ''
            return 'GD Sign In ' + detail2 + detail1
        case '328':
            return 'Keyboard ' + get_action_detail(0, code_action, type_action)
        case '329':
            the_arguments = ['arg0', 'arg1', 'arg2']
            the_names = [' Left:', ' Center:', ' Right:']
            the_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            return 'Navigation Bar ' + the_values[0] + the_values[1] + the_values[2] + get_action_detail(0, code_action, type_action)
        case '331':
            return 'Auto-Sync set to ' + get_action_detail(7, code_action, type_action)
        case '334':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Save WaveNet ' + detail1 + ' Voice: ' + detail2
        case '335':
            return 'App Info' + get_action_detail(0, code_action, type_action)
        case '339':
            return 'HTTP Request ' + get_action_detail(1, code_action, type_action)
        case '340':
            return 'Bluetooth Connection for device ' + get_action_detail(1, code_action, type_action)
        case '341':
            return 'Test Net ' + get_action_detail(1, code_action, type_action)
        case '342':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Test File with data ' + det1 + ' store in ' + det2
        case '343':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            detail2, detail3 = get_action_detail(2, code_action, type_action)
            return 'Test Media  Type:' + test_media_type[int(detail1)] + ', Data:' + detail2 + ', Store Results In:' + detail3
        case '344':
            det1, det2 = get_action_detail(2, code_action, type_action)
            return 'Test App ' + det1 + ' store in ' + det2
        case '345':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Test Variable ' + detail1 + ' and store into ' + detail2
        case '347':
            return 'Test Tasker and store results into ' + get_action_detail(1, code_action, type_action)
        case '348':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            detail3 = test_display_type[int(detail1[0])]
            return 'Test Display ' + detail3 + ' ' + detail2
        case '351':
            return 'HTTP Auth' + get_action_detail(0, code_action, type_action)
        case '354':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Array Set for array ' + detail1 + ' with values ' + detail2
        case '355':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            detail3, lbl = get_action_detail(4, code_action, type_action)  # Get all strings
            return 'Array Push position:' + detail1 + list_to_string(detail3) + lbl
        case '357':
            return 'Array Clear ' + get_action_detail(1, code_action, type_action)
        case '356':
            return 'Array Pop ' + get_action_detail(1, code_action, type_action)
        case '358':
            return 'Bluetooth Info ' + get_action_detail(0, code_action, type_action)
        case '360':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Input Dialog ' + list_to_string(detail1) + ' ' + lbl
        case '361':
            return 'Dark Mode ' + get_action_detail(7, code_action, type_action)
        case '365':
            return 'Tasker Function ' + get_action_detail(1, code_action, type_action)
        case '366':
            the_arguments = ['arg2', 'arg3', 'arg4', 'arg5', 'arg8']  # Min Acc, Speed, Altitude, Near Loc, Min Speed
            the_names = [' Min Accuracy:', ' Speed:', ' Altitude:', ' Near Loc:', ' Min Speed Accuracy:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg6', 'arg7', 'arg9']  # Timeout, Enable Loc, Last Loc, Force Accuracy
            the_names = ['Timeout (SECONDS):', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Get Location V2 ' + the_int_values[0] + ', Enable Location:' + no_yes[int(the_int_values[1])] + \
                   ', Last Location:' + no_yes[int(the_int_values[2])] + ', Force Accuracy:' + no_yes[int(the_int_values[3])] + \
                   get_action_detail(0, code_action, type_action)
        case '367':
            return 'Camera ' + get_action_detail(7, code_action, type_action)
        case '368':
            the_arguments = ['arg1', 'arg3']  # Title, Init Location
            the_names = [' Title:', ' Initial Location:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg2', 'arg4']  # Select Radius, Type
            the_names = ['', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Pick Location ' + the_str_values[0] + ', Select Radius:' + no_yes[int(the_int_values[0])] + \
                   ', ' + the_str_values[1] + ' Type:' + location_type[int(the_int_values[1])] + \
                   get_action_detail(0, code_action, type_action)
        case '369':
            return 'Array Process ' + get_action_detail(1, code_action, type_action)
        case '370':
            return 'Shortcut ' + get_action_detail(1, code_action, type_action)
        case '373':
            return 'Test Sensor ' + get_action_detail(1, code_action, type_action)
        case '374':
            return 'Screen Capture'
        case '375':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'ADB Wifi ' + list_to_string(detail1) + ' ' + lbl
        case '376':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Test Sensor file ' + detail1 + ' mime type ' + detail2
        case '377':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg8', 'arg9']
            the_names = [' Title:', ' Text:', ' Button 1:', ' Button 2:', ' Button 3:', ' Image:', ' Max W/H:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg6', 'arg7']
            the_names = [' Close After (seconds):', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Text/Image Dialog ' + the_str_values[0] + the_str_values[1] + the_str_values[2] + the_str_values[3] + \
                    the_str_values[4] + the_int_values[0] + the_int_values[1] + the_str_values[5]  + ', Use HTML:' + \
                   no_yes[int(the_int_values[1])] + the_str_values[6] + get_action_detail(0, code_action, type_action)
        case '378':
            return 'List Dialog ' + get_action_detail(1, code_action, type_action)
        case '383':
            return 'Settings Panel' + get_action_detail(0, code_action, type_action)
        case '384':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            detail2, lbl = get_action_detail(8, code_action, type_action)
            if detail2[0] == '0':
                detail3 = 'Add/Edit'
            else:
                detail3 = 'Delete'
            return 'Device Control (Power Menu Action) action:' + detail3 + ' type:' + button_type[int(detail2[1])] + ' ' + list_to_string(detail1) + lbl
        case '387':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                return 'Accessibility Volume to ' + detail1 + lbl
        case '389':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Multiple Variables Set ' + detail1 + ' to ' + detail2
        case '390':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Pick Input Dialog ' + detail1 + ' with structure type ' + detail2
        case '391':
            the_arguments = ['arg2', 'arg3', 'arg5', 'arg6']  # Get specific Strs
            the_names = [' Title:', ' Text:', ' Animation Images:', ' Animation Tint:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg4', 'arg7', 'arg10']  # Get specific Ints
            the_names = [[' Action:', '0', 'Show/Update', '1', ' Dismiss'], [' Type:', '0', 'Animation', '1', 'Progress Bar'],
                        ' Frame Duration:', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Progress Dialog ' + the_int_values[0] + the_str_values[0] + the_str_values[1] + the_int_values[2] + \
                    the_str_values[2] +  the_str_values[3] + the_int_values[3] + ', Use HTML:' + no_yes[int(the_int_values[1])] + \
                    get_action_detail(0, code_action, type_action)
        case '392':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Set Variable Structure Type name ' + detail1 + ' with structure type ' + detail2
        case '393':
            return 'Array Merge ' + get_action_detail(1, code_action, type_action)
        case '394':
            return 'Parse/Format DateTime ' + get_action_detail(0, code_action, type_action)
        case '396':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Simple Match/Regex ' + detail1 + ' with regex ' + detail2
        case '399':
            return 'Variable Map ' + get_action_detail(1, code_action, type_action)
        case '400':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Move (file) from ' + detail1 + ' to ' + detail2
        case '404':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Copy File ' + detail1 + ' to ' + detail2
        case '405':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Copy Dir ' + detail1 + ' to ' + detail2
        case '406':
            return 'Delete File ' + get_action_detail(1, code_action, type_action)
        case '407':
            the_arguments = ['arg1', 'arg2']
            the_names = [' Max Number:', ' Mime Type:']
            the_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail1, detail2 = get_action_detail(3, code_action, type_action)
            if detail1 == '1':
                detail1 = ' (Copy To Cache) '
            else:
                detail1 = ''
            return 'Pick Photos ' + the_values[0] + the_values[1] + detail1 + detail2
        case '408':
            return 'Delete Directory directory: ' + get_action_detail(1, code_action, type_action)
        case '409':
            return 'Create Directory ' + get_action_detail(1, code_action, type_action)
        case '410':
            return 'Write File ' + get_action_detail(1, code_action, type_action)
        case '412':
            return 'List Files directory ' + get_action_detail(1, code_action, type_action)
        case '414':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Get Pixel Colors image:' + detail1 + ' pixel coordinates:' + detail2
        case '415':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Read Line from file ' + list_to_string(detail1) + ' ' + lbl
        case '416':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Read Paragraph from file ' + list_to_string(detail1) + ' ' + lbl
        case '417':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Read File ' + detail1 + ' into ' + detail2
        case '420':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            detail3, lbl = get_action_detail(3, code_action, type_action)
            if detail3 == '1':
                detail3 = ' (Delete Orig checked) '
            else:
                detail3 = ''
            return 'Zip file ' + detail1 + ' into ' + detail2 + detail3 + lbl
        case '421':
            return 'Get Screen Info (assistant)' + get_action_detail(0, code_action, type_action)
        case '422':
            detail1, detail2, lbl = get_action_detail(9, code_action, type_action)
            if detail2 == '1':
                detail2 = ' (Delete Zip checked) '
            else:
                detail2 = ''
            return 'UnZip file ' + detail1 + detail2 + lbl
        case '424':
            return 'Get Battery Info' + get_action_detail(0, code_action, type_action)
        case '425':
            return 'Turn Wifi ' + get_action_detail(7, code_action, type_action)
        case '430':
            return 'Restart Tasker' + get_action_detail(0, code_action, type_action)
        case '433':
            return 'Mobile Data set to ' + get_action_detail(7, code_action, type_action)
        case '443':
            app_detail, lbl = get_action_detail(5, code_action, type_action)  # Get application name
            the_arguments = ['arg0', 'arg1', 'arg3']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Media Control&nbsp;&nbsp;Cmd:' + cmd_type[int(the_int_values[0])]+ ', Simulated Media Button:' + \
                   no_yes[int(the_int_values[1])]+ ', Use Notification If Available:' + no_yes[int(the_int_values[2])] + \
                    ', Package:' + app_detail + ' with app name:' + lbl
        case '445':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Music Play&nbsp;&nbsp;Start:' + the_int_values[0] + ', Loop:' + no_yes[int(the_int_values[1])] + \
                    ', Stream:' + media_type[int(the_int_values[2])] + ', Continue Task Immediately:' + no_yes[int(the_int_values[3])] + \
                   ', File:' + get_action_detail(1, code_action, type_action)
        case '447':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4', 'arg5']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '', '', '', ', Maximum Tracks:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Music Play Dir&nbsp;&nbsp;Subdirs:' + no_yes[int(the_int_values[0])] + ', Audio Only:' + no_yes[int(the_int_values[1])] + \
                   ', Random:' + no_yes[int(the_int_values[2])] + ', Flash:' + no_yes[int(the_int_values[3])] + \
                   ', ' + the_int_values[4] + ', Directory:' + get_action_detail(1, code_action, type_action)
        case '449':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Music Stop&nbsp;&nbsp;Clear Dir:' + no_yes[int(detail1)] + lbl
        case '451':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Music Skip  Jump: ' + detail1 + lbl
        case '453':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Music Back&nbsp;&nbsp;Jump: ' + detail1 + lbl
        case '455':
            the_arguments = ['arg1', 'arg2', 'arg3']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', ', MaxSize:', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Record Audio&nbsp;&nbsp;Source:' + source_type[int(the_int_values[0])] + the_int_values[1] + \
                   ', Format:' + format_type[int(the_int_values[2])] + \
                   ', File:' + get_action_detail(1, code_action, type_action)
        case '457':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                return 'Force Rotation ' + detail1 + lbl
        case '459':
            return 'Scan Media&nbsp;&nbsp;File:' + get_action_detail(1, code_action, type_action)
        case '461':
            detail1, detail2 = get_action_detail(5, code_action, False)
            if detail2 == '':
                return 'Notification'
            else:
                return 'Notification for app ' + detail2
        case '475':
            detail1, detail2, lbl = get_action_detail(9, code_action, type_action)
            if detail2 == '1':
                detail2 = ' (Delete Orig checked) '
            else:
                detail2 = ''
            return 'GZip file ' + detail1 + detail2 + lbl
        case '476':
            detail1, detail2, lbl = get_action_detail(9, code_action, type_action)
            if detail2 == '1':
                detail2 = ' (Delete Zip checked) '
            else:
                detail2 = ''
            return 'GUnzip file ' + detail1 + detail2 + lbl
        case '490':
            the_arguments = ['arg0', 'arg1']  # Int: Action, Use New API
            the_names = [[' Action:', '0', 'Grab', '1', 'Release'],
                         [' Use New API:', '0', 'No', '1', 'Yes']]
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Media Button Events ' + the_int_values[0] + the_int_values[1] + \
                   get_action_detail(0, code_action, type_action)
        case '511':
            return 'Torch' + get_action_detail(0, code_action, type_action)
        case '512':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 == '0':
                detail2 = 'Expanded'
            else:
                detail2 = 'Collapsed'
            return 'Status Bar' + detail2 + lbl
        case '513':
            return 'Close System Dialogs' + get_action_detail(0, code_action, type_action)
        case '523':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Notify ' + list_to_string(detail1) + ' ' + lbl
        case '525':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Notify LED title:' + detail1 + ' text:' + detail2
        case '536':
            return 'Notification Vibrate with title ' + get_action_detail(1, code_action, type_action)
        case '538':
            return 'Notification Sound with title ' + get_action_detail(1, code_action, type_action)
        case '550':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Popup title ' + detail1 + ' with message: ' + detail2
        case '552':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Popup Task Buttons ' + list_to_string(detail1) + ' ' + lbl
        case '543':
            return 'Start System Timer ' + get_action_detail(1, code_action, type_action)
        case '545':
            return 'Variable Randomize ' + get_action_detail(1, code_action, type_action)
        case '547':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Variable Set ' + detail1 + ' to ' + detail2
        case '548':
            return 'Flash ' + get_action_detail(1, code_action, type_action)
        case '549':
            return 'Variable Clear ' + get_action_detail(1, code_action, type_action)
        case '550':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Popup ' + detail1 + ' ' + detail2
        case '551':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Menu with fields: ' + list_to_string(detail1) + lbl
        case '559':
            return 'Say ' + get_action_detail(1, code_action, type_action)
        case '566':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Set Alarm ' + list_to_string(detail1) + ' ' + lbl
        case '567':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Calendar Insert ' + detail1 + ' with description: ' + detail2
        case '590':
            return 'Variable Split ' + get_action_detail(1, code_action, type_action)
        case '592':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Variable Join ' + detail1 + ' to ' + detail2
        case '596':
            return 'Variable Convert ' + get_action_detail(1, code_action, type_action)
        case '597':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Variable Section ' + detail1 + ' from ' + detail2
        case '598':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Variable Search Replace ' + detail1 + ' search for ' + detail2
        case '664':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Java Function return object ' + detail1 + ' , ' + detail2
        case '665':
            return 'Java Object ' + get_action_detail(1, code_action, type_action)
        case '667':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'SQL Query ' + detail1 + ' to ' + detail2
        case '697':
            return 'Shut Up' + get_action_detail(0, code_action, type_action)
        case '669':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            return 'Say To File ' + list_to_string(detail1) + ' ' + lbl
        case '775':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Write Binary ' + detail1 + ' file: ' + detail2
        case '776':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'Write Binary file ' + detail1 + ' to Var: ' + detail2
        case '779':
            return 'Notify Cancel ' + get_action_detail(1, code_action, type_action)
        case '806':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Notify Cancel ' + detail1 + lbl
        case '808':
            return 'Auto Brightness ' + get_action_detail(7, code_action, type_action)
        case '810':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Display Brightness to ' + detail1 + lbl
        case '812':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Display Timeout ' + detail1 + lbl
        case '815':
            return 'List Apps into ' + get_action_detail(1, code_action, type_action)
        case '820':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            return 'Stay On ' + stayon_type[int(detail1)] + detail2
        case '822':
            return 'Display Autorotate set to ' + get_action_detail(7, code_action, type_action)
        case '877':
            return 'Send Intent ' + get_action_detail(1, code_action, type_action)
        case '888':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Variable Add ' + detail1 + lbl
        case '890':
            return 'Variable Subtract ' + get_action_detail(1, code_action, type_action)
        case '900':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            detail3, lbl = get_action_detail(3, code_action, type_action)
            if detail3 == '1':
                detail3 = 'Include Hidden Files'
            else:
                detail3 = ''
            return 'Browse Files directory ' + detail1 + detail3 + ' match:' + detail2
        case '901':
            return 'Stop Location ' + get_action_detail(0, code_action, type_action)
        case '902':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3']  # Source, Timeout, Continue, Keep Tracking
            the_names = [[' Source:', '0', 'GPS', '1', 'Net', '2', 'Any'], 'Timeout (SECONDS):',
                         [' Continue Task Immediately:', '0', 'No', '1', 'Yes'],
                         [' Keep Tracking:', '0', 'No', '1', 'Yes']]
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            return 'Get Location ' + the_int_values[0] + the_int_values[1] + the_int_values[3] +  \
                   get_action_detail(0, code_action, type_action)
        case '903':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            detail2, lbl = get_action_detail(8, code_action, type_action)
            if detail2[0] == '0':
                language_model = 'Free Form'
            else:
                language_model = 'Web Search'
            if len(detail1) > 1:
                language = detail1[1]
                title = ' title:' + detail1[0]
            else:
                language = detail1[0]
                title = ''
            if len(detail2) > 2:
                if detail2[3] == '1':
                    hide_dial = ' (Hide Dialog)'
                else:
                    hide_dialog = ''
            return 'Get Voice' + title +  ' for language:' + language + ' model:' + language_model + hide_dialog + lbl
        case '904':
            return 'Voice Command' + get_action_detail(0, code_action, type_action)
        case '905':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Location Mode set to ' + location_mode_status[int(detail1)] + lbl
        case '906':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            return 'Immersive Mode ' + immersive_modes[int(detail1)] + lbl
        case '907':
            return 'Status Bar Icons ' + get_action_detail(1, code_action, type_action)
        case '941':
            detail1, detail2 = get_action_detail(2, code_action, type_action)
            return 'HTML Pop code: ' + detail1 + ' Layout: '+ detail2
        case '987':
            return 'Soft Keyboard' + get_action_detail(0, code_action, type_action)
        case '988':
            return 'Car Mode ' + get_action_detail(7, code_action, type_action)
        case '989':
            detail1 = get_action_detail(7, code_action, type_action)
            if detail1 == 'Toggle':
                detail1 ='Auto'
            return 'Car Mode ' + detail1

    # Plugins start here
        case '117240295':
            return 'AutoWear Input ' + get_action_detail(6, code_action, type_action)
        case '140618776':
            return 'AutoWear Toast ' + get_action_detail(6, code_action, type_action)
        case '166160670':
            return 'AutoNotification ' + get_action_detail(6, code_action, type_action)
        case '191971507':
            return 'AutoWear ADB Wifi ' + get_action_detail(6, code_action, type_action)
        case '234244923':
            return 'AutoInput Unlock Screen' + get_action_detail(0, code_action, type_action)
        case '268157305':
            return 'AutoNotification Tiles ' + get_action_detail(6, code_action, type_action)
        case '319692633':
            return 'AutoShare Process Text ' + get_action_detail(6, code_action, type_action)
        case '344636446':
            return 'AutoVoice Trigger Alexa Routine ' + get_action_detail(6, code_action, type_action)
        case '557649458':
            return 'AutoWear Time ' + get_action_detail(6, code_action, type_action)
        case '565385068':
            return 'AutoWear Input ' + get_action_detail(6, code_action, type_action)
        case '774351906':
            return ' ' + get_action_detail(6, code_action, type_action)  # Join Action (contained in get_action_detail)
        case '778682267':
            return 'AutoInput Gestures ' + get_action_detail(6, code_action, type_action)
        case '811079103':
            return 'AutoInput Global Action ' + get_action_detail(6, code_action, type_action)
        case '906355163':
            return 'AutoWear Voice Screen ' + get_action_detail(6, code_action, type_action)
        case '940160580':
            return 'AutoShare ' + get_action_detail(6, code_action, type_action)
        case '1027911289':
            return 'AutoVoice Set Cmd Id ' + get_action_detail(6, code_action, type_action)
        case '1099157652':
            return 'AutoTools Json Write ' + get_action_detail(6, code_action, type_action)
        case '1040876951':
            return 'AutoInput UI Query ' + get_action_detail(6, code_action, type_action)
        case '1150542767':
            return 'Double Tap Plugin ' + get_action_detail(6, code_action, type_action)
        case '1165325195':
            return 'AutoTools Web Screen ' + get_action_detail(6, code_action, type_action)
        case '1250249549':
            return 'AutoInput Screen Off/On ' + get_action_detail(6, code_action, type_action)
        case '1246578872':
            return 'AutoWear Notification ' + get_action_detail(6, code_action, type_action)
        case '1304982781':
            return 'AutoTools Dialog ' + get_action_detail(6, code_action, type_action)
        case '1410790256':
            return 'AutoWear Floating Icon ' + get_action_detail(6, code_action, type_action)
        case '1644316156':
            return 'AutoNotification Reply ' + get_action_detail(6, code_action, type_action)
        case '1754437993':
            return 'AutoVoice Recognize ' + get_action_detail(6, code_action, type_action)
        case '1830829821':
            return 'AutoWear 4 Screen ' + get_action_detail(6, code_action, type_action)
        case '1957670352':
            return 'AutoWear App ' + get_action_detail(6, code_action, type_action)
        case '1339942270':
            return 'SharpTools Thing ' + get_action_detail(6, code_action, type_action)
        case '1452528931':
            return 'AutoContacts Query 2.0 ' + get_action_detail(6, code_action, type_action)
        case '1620773086':
            return 'SharpTools A Thing ' + get_action_detail(6, code_action, type_action)
        case '1447159672':
            return 'AutoTools Text ' + get_action_detail(6, code_action, type_action)
        case '1508929357':
            return 'AutoTools ' + get_action_detail(6, code_action, type_action)
        case '1732635924':
            return 'AutoInput Action ' + get_action_detail(6, code_action, type_action)
        case '1830656901':
            return 'AutoWear List Screens ' + get_action_detail(6, code_action, type_action)
        case '1957681000':
            return 'AutoInput Gesture ' + get_action_detail(6, code_action, type_action)
        case '2046367074':
            return 'AutoNotification Cancel ' + get_action_detail(6, code_action, type_action)
        case _:
            if 1000 < int(task_code):
                return 'Call to Plugin ' + get_action_detail(6, code_action, type_action)
            else:
                return 'Code ' + task_code + ' not yet mapped'


# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
def ulify(element, lvl=int):   # lvl=0=heading 1=start list 2=Task/Profile/Scene 3=end list 4=special Task
    list_color = '<li style="color:'

    string = ''
    # Heading..............................
    if lvl == 0 or lvl == 4:  # lvl=4 >>> Heading or plain text line
        if lvl == 0:  # Heading
            string = '<b>' + element + '</b><br>\n'
        else:
            string = element + '<br>\n'
    # Start List..............................
    elif lvl == 1:  # lvl=1 >>> Start list
        string = '<ul>' + element + '\n'
    # Item in the list..............................
    elif lvl == 2:  # lvl=2 >>> List item
        if 'Project' == element[0:7]:   # Project ========================
            string = list_color + bullet_color + '" ><span style="color:' + project_color + ';">' + element + '</span></li>\n'
        elif 'Profile' == element[0:7]:  # Profile ========================
            string = list_color + bullet_color + '" ><span style="color:' + profile_color + ';">' + element + '</span></li>\n'
        elif element[0:5] == 'Task:' or '⎯Task:' in element:  # Task or Scene's Task ========================
            if unknown_task_name in element:
                string = list_color + bullet_color + '" ><span style="color:' + unknown_task_color + ';">' + element + '</span></li>\n'
            else:
                string = list_color + bullet_color + '" ><span style="color:' + task_color + ';">' + element + '</span></li>\n'
        elif 'Scene:' in element:  # Scene
            string = list_color + bullet_color + '" ><span style="color:' + scene_color + ';">' + element + '</span></li>\n'
        elif 'Action:' in element:  # Action
            if 'Action: ...' in element:   # If this is continued from the previous line, indicate so and ensure proper font
                if '' == element[11:len(element)]:
                    string = ''
                    return string
                tmp = element.replace('Action: ...', '<font face=' + output_font + '></font></b>Action continued >>> ')
                element = tmp
            string = list_color + bullet_color + '" ><span style="color:' + action_color + ';"><font face=' + output_font + '></font></b>' + element + '</span></li>\n'
        elif 'Label for' in element:  # Action
            string = list_color + bullet_color + '" ><span style="color:' + action_color + ';">' + element + '</span></li>\n'
        else:      # Must be additional item
            string = '<li>' + element + '</li>\n'
    # End List..............................
    elif lvl == 3:  # lvl=3 >>> End list
        string = '</ul>'
    return string


# Write line of output
def my_output(output_list, list_level, out_string):

    if 'Task ID:' in out_string and debug is False:   # Drop ID: nnn since we don't need it anymore
        temp_element = out_string.split('Task ID:')
        out_string = temp_element[0]
    output_list.append(ulify(out_string,  list_level))
    if debug_out:
        print('out_string:', ulify(out_string, list_level))
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

    # Break-up very long actions at new line
    if tcode != '':
        newline = tcode.find('\n')  # Break-up new line breaks
        tcode_len = len(tcode)
        # If no new line break or line break less than width set for browser, just put it as is
        # Otherwise, make it a continuation line using '...' has the continuation flag
        if newline == -1 and tcode_len > 80:
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


# Shell sort for Action list (Actions are not necessarily in numeric order in XML backup file).
def shell_sort(arr, n):
    gap = n // 2
    while gap > 0:
        j = gap
        # Check the array in from left to right
        # Till the last possible index of j
        while j < n:
            i = j - gap  # This will keep help in maintain gap value
            while i >= 0:
                # Get the n from <Action sr='actn' ve='7'> as a number for comparison purposes
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
    return


# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
def get_actions(current_task):
    tasklist = []
    try:
        task_actions = current_task.findall('Action')
    except Exception as e:
        print('Error: No action found!!!')
        return []
    if task_actions:
        count_of_actions = 0
        indentation_amount = ''
        indentation = 0
        for action in task_actions:
            count_of_actions += 1
        # sort the Actions by attrib sr (e.g. sr='act0', act1, act2, etc.) to get them in true order
        if count_of_actions > 1:
            shell_sort(task_actions, count_of_actions)
        for action in task_actions:
            child = action.find('code')   # Get the <code> element
            task_code = getcode(child, action, True)
            # logger.debug('Task ID:' + str(current_task.attrib['sr']) + ' Code:' + child.text + ' task_code:' + task_code + 'Action attr:' + str(action.attrib))
            # Calculate the amount of indention required
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
def get_task_name(the_task_id, all_the_tasks, tasks_that_have_been_found, the_task_list, task_type):
    task_name = ''
    for task in all_the_tasks:
        if the_task_id == task.find('id').text:
            tasks_that_have_been_found.append(the_task_id)
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

# See if the xml tag is one of the predefined types and return result
def tag_in_type(tag, flag):
    scene_task_element_types = ['ListElement', 'TextElement', 'ImageElement', 'ButtonElement', 'OvalElement',
                                'EditTextElement']
    scene_task_click_types = ['clickTask', 'longclickTask', 'itemclickTask', 'valueselectedTask', 'itemlongclickTask']

    if flag:
        if tag in scene_task_element_types:
            return True
        else:
            return False
    else:
        if tag in scene_task_click_types:
            return True
        else:
            return False

# Process Task/Scene text/line item: call recursively for Tasks within Scenes
def process_list(list_type, the_output, the_list, all_task_list, all_scene_list, the_task,
                 tasks_found, detail):
    # Output the item first (Task, Scene or Action)
    my_count = 0
    for the_item in the_list:
        temp_item = ''
        if not debug:  # Temporarily strip off 'ID: nnn' for the output and then put it back in place for later
            if '⎯Task:' in list_type:
                temp_item = the_item
                temp_list = list_type
                the_item = ''
                id_loc = list_type.find('ID:')
                if id_loc != -1:
                    list_type = list_type[0:id_loc]  # Drop the 'ID: nnn'
        else:
            logger.debug('def_process_list  the_item:' + the_item + ' the_list:' + str(the_list) + ' list_type:' + list_type)
        my_output(the_output, 2, list_type + '&nbsp;' + the_item)
        my_count += 1
        if temp_item:   # Put the_item back with the 'ID: nnn' portion included.
            the_item = temp_item
            list_type = temp_list

        # Output Actions for this Task if displaying detail and/or Task is unknown
        # Do we get the Task's Actions?
        if ('Task:' in list_type and unknown_task_name in the_item) or ('Task:' in list_type):
            if unknown_task_name in the_item or detail > 0:  # If Unknown task, then 'the_task' is not valid, and we have to find it.
                if '⎯Task:' in list_type:   # -Task: = Scene rather than a Task
                    temp = ['x', the_item]
                else:
                    temp = the_item.split('ID: ')  # Unknown/Anonymous!  Task ID: nn    << We just need the nn
                if len(temp) > 1:
                    the_task, kaka = get_task_name(temp[1], all_task_list, tasks_found, [temp[1]], '')

            # Get the Task's Actions
                alist = get_actions(the_task)
                if alist:
                    action_count = 1
                    my_output(the_output, 1, '')  # Start Action list
                    for taction in alist:
                        if taction is not None:
                            if 'Label for' in taction:
                                my_output(the_output, 2, taction)
                            else:
                                if '...' == taction[0:3]:
                                    my_output(the_output, 2, 'Action: ' + taction)
                                else:
                                    my_output(the_output, 2, 'Action: ' + str(action_count).zfill(2) + ' ' + taction)
                                    action_count += 1
                            if action_count == 2 and detail == 0 and unknown_task_name in the_item:  # Just show first Task if unknown Task
                                break
                            elif detail == 1 and unknown_task_name not in the_item:
                                break
                    my_output(the_output, 3, '')  # Close Action list

        # Must be a Scene.  Look for all 'Tap' Tasks for Scene
        elif 'Scene:' == list_type and detail == 2:  # We have a Scene: get its actions
            have_a_scene_task = False
            for my_scene in the_list:   # Go through each Scene to find TAP and Long TAP Tasks
                getout = 0
                for scene in all_scene_list:
                    for child in scene:
                        if child.tag == 'nme' and child.text == my_scene:  # Is this our Scene?
                            for cchild in scene:   # Go through sub-elements in the Scene element
                                if tag_in_type(cchild.tag, True):
                                    for subchild in cchild:   # Go through ListElement sub-items
                                        if tag_in_type(subchild.tag, False):   # Task associated with this Scene's element?
                                            have_a_scene_task = True
                                            temp_task_list = [subchild.text]
                                            task_element, name_of_task = get_task_name(subchild.text, all_task_list, tasks_found, temp_task_list, '')
                                            temp_task_list = [subchild.text]  # reset to task name since get_task_name changes its value
                                            extra = '&nbsp;&nbsp;ID:'
                                            if subchild.tag == 'itemclickTask' or subchild.tag == 'clickTask':
                                                task_type = '⎯Task: TAP' + extra
                                            elif 'long' in subchild.tag:
                                                task_type = '⎯Task: LONG TAP' + extra
                                            else:
                                                task_type = '⎯Task: TEXT CHANGED' + extra
                                            process_list(task_type, the_output, temp_task_list, all_task_list, all_scene_list, task_element, tasks_found, detail)  # Call ourselves iteratively
                                        elif subchild.tag == 'Str':
                                            break
                                    if have_a_scene_task:  # Add Scene's Tasks to total list of Scene's Tasks
                                        getout = 2
                                    else:
                                        getout = 1
                                        break
                                elif 'Str' == cchild.tag:
                                    break
                                elif 'PropertiesElement' == cchild.tag:   # Have we gone past the point ofm interest?
                                    break
                        if child.tag == 'ButtonElement':
                            break
                        if getout > 0:
                            break
    return


# Find the Project belonging to the Task id passed in
def get_project_for_solo_task(all_of_the_projects, the_task_id, projs_with_no_tasks):
    proj_name = no_project
    for project in all_of_the_projects:
        proj_name = project.find('name').text
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


# Get a specific Profile's Tasks
def get_profile_tasks(the_profile, all_the_tasks, found_tasks_list, task_list_output, task_to_be_found):
    keys_we_dont_want = ['cdate', 'edate', 'flags', 'id']
    for child in the_profile:
        if child.tag in keys_we_dont_want:
            continue
        if 'mid' in child.tag:
            task_type = 'Entry'
            if 'mid1' == child.tag:
                task_type = 'Exit'
            task_id = child.text
            if task_id == '18':
                logger.debug('====================================' + task_id + '====================================')
            the_task_element, the_task_name = get_task_name(task_id, all_the_tasks, found_tasks_list, task_list_output, task_type)
            if task_to_be_found and task_to_be_found == the_task_name:
                break
        elif 'nme' == child.tag:  # If hit Profile's name, we've passed all the Task ids.
            return the_task_element, the_task_name
    return the_task_element, the_task_name


# Identify whether the Task passed in is part of a Scene: True = yes, False = no
def task_in_scene(the_task_id, all_of_the_scenes):
    for scene in all_of_the_scenes:
        for child in scene:  # Go through sub-elements in the Scene element
            if tag_in_type(child.tag, True):
                for subchild in child:  # Go through xxxxElement sub-items
                    if tag_in_type(subchild.tag, False):
                        if the_task_id == subchild.text:
                            return True
                    elif 'Str' == child.tag:  # Passed any click Task
                        break
                    else:
                        continue
    return False


# Profile condition: Time
def condition_time(the_item, cond_string):
    to_hour, to_minute, from_hour, from_minute, rep, rep_type, from_variable, to_variable, = '', '', '', '', '', '', '', ''
    for child in the_item:
        match child.tag:
            case 'fh':
                from_hour = child.text
            case 'fm':
                from_minute = child.text
            case 'th':
                to_hour = child.text
            case 'tm':
                to_minute = child.text
            case 'rep':
                if '2' == child.text:
                    rep_type = ' minutes '
                else:
                    rep_type = ' hours '
            case 'repval':
                rep = ' repeat every ' + child.text + rep_type
            case 'fromvar':
                from_variable = child.text
            case 'tovar':
                to_variable = child.text
    if from_hour or from_minute:
        cond_string = cond_string + 'Time: from ' + from_hour + ':' + from_minute.zfill(2) + rep
    if to_hour or to_minute:
        cond_string = cond_string + ' to ' + to_hour + ':' + to_minute.zfill(2)
    elif from_variable or to_variable:
        cond_string = cond_string + 'Time: from ' + from_variable + ' to ' + to_variable + ' ' + rep
    else:
        cond_string = cond_string + child.text + ' not yet mapped'
    return cond_string


# Profile condition: Day
def condition_day(the_item, cond_string):
    weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
              'November', 'December']

    the_days_of_week = ''
    days_of_month = ''
    the_months = ''
    for child in the_item:
        if 'wday' in child.tag:
            the_days_of_week = the_days_of_week + weekdays[int(child.text) - 1] + ' '
        elif 'mday' in child.tag:
            days_of_month = days_of_month + child.text + ' '
        elif 'mnth' in child.tag:
            the_months = the_months + months[int(child.text)] + ' '
        else:
            break
    if the_days_of_week:
        cond_string = cond_string + 'Days of Week: ' + the_days_of_week
    if days_of_month:
        cond_string = cond_string + 'Days of Month: ' + days_of_month + ' '
    if the_months:
        cond_string = cond_string + 'Months: ' + the_months + ' '
    return cond_string


def condition_state(the_item, cond_string):
    for child in the_item:
        mobile_network_type = ['2G', '3G', '3G HSPA', '4G', '5G']
        if child.tag == 'code':
            match child.text:
                case '2':
                    state = 'BT Status'
                case '3':
                    state = 'BT Connected'
                case '10':
                    state = 'Power'
                case '30':
                    state = 'Headset Plugged'
                case '37':  # Variable Set
                    state = getcode(child, the_item, False)
                case '40':
                    state = 'Call'
                case '103':  # Light Level
                    state = getcode(child, the_item, False)
                case '110':  # Light Level
                    detail1, xtra = get_action_detail(8, the_item, False)
                    count = 0
                    detail2 = ''
                    for items in detail1:
                        if detail1[count] == '1':
                            detail2 = detail2 + ' ' + mobile_network_type[count]
                        count += 1
                        if count > 4:
                            break
                    state = 'Mobile Network:' + detail2
                case '143':  # Light Level
                    state = 'Task Running: ' + get_action_detail(1, the_item, False)
                case '165':  # State code 165 = action code 37
                    child.text = '37'
                    state = getcode(child, the_item, False)
                case '122':
                    orientation = get_action_detail(1, the_item, False)
                    if orientation == '0':
                        orientation = 'portrait'
                    else:
                        orientation = 'landscape'
                    state = 'Display Orientation: ' + orientation
                case '123':
                    display_state = get_action_detail(1, the_item, False)
                    if display_state == '0':
                        display_state = 'off'
                    else:
                        display_state = 'on'
                    state = 'Display State is ' + display_state
                case '125':
                    state = 'Proximity Sensor'
                case '140':
                    state = getcode(child, the_item, False)
                case '142':
                    state = 'Monitor Start'
                case '150':
                    state = 'USB Connected'
                case '160':
                    state = 'WiFi Connected (to) ' + get_action_detail(1, the_item, False)
                case '186':
                    child.text = '235'  # Custom Setting
                    state = getcode(child, the_item, False)
                case '188':
                    state = 'Dark Mode'
                case '235':  # Custom Setting
                    state = getcode(child, the_item, False)
                case '40830242':
                    state = 'AutoNotification Intercept'
                case '1138194991':
                    state = 'AutoWear'
                case _:
                    state = child.text + ' not yet mapped'
            cond_string = cond_string + 'State ' + state
            invert = the_item.find('pin')
            if invert is not None:
                if invert.text == 'true':
                    cond_string = cond_string + ' <em>[inverted]</em>'
            if debug:  # If debug add the code
                cond_string = cond_string + ' (code:' + child.text + ')'
        return cond_string


# Profile condition: Event
def condition_event(the_item, cond_string):
    the_event_code = the_item.find('code')
    sms_text_types = ['Any', 'MMS', 'SMS']
    volume_setting = ['Up', 'Down', 'Up or Down']

# Determine what the Event code is and return the actual Event text
    match the_event_code.text:
        case '4':
            event = 'Phone Idle'
        case '6':
            event = 'Phone Ringing caller ' + get_action_detail(1, the_item, False)
        case '7':
            the_type, lbl = get_action_detail(3, the_item, False)
            text_type = sms_text_types[int(the_type)]
            msg_fields = []
            for msg_string in the_item.iter('Str'):
                if msg_string.text is not None:
                    msg_fields.append(msg_string.text)
                else:
                    msg_fields.append('')
            event = 'Received Text type:' + text_type + ' sender:' + msg_fields[0] + ' content:' + msg_fields[1] + \
                    ' sim:' + msg_fields[2] + ' body:' +msg_fields[3]
        case '201':
            event = 'Assistance Request'
        case '203':
            battery_levels = ['highest', 'high', 'normal', 'low', 'lowest']
            pri = the_item.find('pri')
            the_battery_level = battery_levels[(int(pri.text)-1)]
            event = 'Battery Changed to ' + the_battery_level
        case '208':
            event = 'Display On'
        case '210':
            event = 'Display Off'
        case '222':
            str1, str2 = get_action_detail(2, the_item, False)
            event = 'File Modified file ' + str1 + ' Event ' + str2
        case '235':  # Custom Setting
            event = getcode(the_event_code, the_item, False)
        case '302':
            event = 'Time/Date Set'
        case '307':
            event = 'Monitor Start'
        case '411':
            event = 'Device Boots'
        case '450':
            event = 'New Package'
        case '451':
            event = 'Package Updated'
        case '453':
            event = 'Package Removed'
        case '461':
            event = getcode(the_event_code, the_item, False)
        case '464':
            event = 'Notification Removed'
        case '547':  # Variable Set
            event = getcode(the_event_code, the_item, False)
        case '599':
            event = 'Intent Received with action ' + get_action_detail(1, the_item, False)
        case '1000':
            event = 'Display Unlocked'
        case '2000':
            app, extra = get_action_detail(5, the_item, False)
            event = 'Notification Click ' + app + extra
        case '2075':  # Custom Settings
            the_event_code.text = '235'
            event = getcode(the_event_code, the_item, False)
        case '2077':
            event = 'Secondary App Opened'
        case '2078':
            event = 'App Changed'
        case '2079':
            the_volume, lbl = get_action_detail(3, the_item, False)
            if the_volume != '':
                event = 'Volume Long Press Volume '  + volume_setting[int(the_volume)] + lbl
            else:
                event = 'Volume Long Press Volume' + lbl
        case '2095':
            event = 'Tick for ' + get_action_detail(1, the_item, False)
        case '2080':  # BT Connected
            the_event_code.text = '340'
            event = getcode(the_event_code, the_item, False)
        case '2081':
            event = 'Music Track Changed'
        case '2085':
            event = 'Logcat Entry'
        case '2091':
            event = 'Logcat Entry'
        case '2093':
            event = 'Assistant Action'
        case '3001':
            event = 'Shake'
        case '3050':  # Variable set
            the_event_code.text = '547'
            event = getcode(the_event_code, the_item, False)
        case '18927444':
            event = 'AutoApps Command'
        case '41628340':
            event = 'AutoVoice Recognized'
        case '580953799':
            event = 'AutoShare'
        case '1150542767':
            event = 'Tap Tap Plugin'
        case '1520257414':
            event = 'AutoNotification Intercept'
        case '1664218170':
            event = 'AutoVoice Natural Language ' + get_action_detail(6, the_item, False)
        case '1691829355':
            event = 'SharpTools Thing'
        case '1825107102':
            event = 'AutoNotification'
        case '1861978578':
            event = 'AutoWear Command/Command Filter'
        case '1957681000':   # AutoInput Gesture
            event = getcode(the_event_code, the_item, False)
        case _:
            event = the_event_code.text + ' not yet mapped'

    cond_string = cond_string + 'Event ' + event
    if debug:  # If debug then add the code
        cond_string = cond_string + ' (code:' + the_event_code.text + ')'
    return cond_string


# Given a Profile, return its list of conditions
def parse_profile_condition(the_profile):
    cond_title = 'condition '
    ignore_items = ['cdate', 'edate', 'flags', 'id', 'ProfileVariable']
    condition = ''   # Assume no condition
    for item in the_profile:
        if item.tag in ignore_items or 'mid' in item.tag:  # Bypass junk we don't care about
            continue
        if condition:   # If we already have a condition, add 'and' (italicized)
            condition = condition + ' <em>and</em> '

        # Find out what the condition is and handle it
        match item.tag:

        # Condition = Time
            case 'Time':
                condition = condition_time(item, condition)  # Get the Time condition

            # Condition = Day of week
            case 'Day':
                condition = condition_day(item, condition)

            # Condition = State
            case 'State':
                condition = condition_state(item, condition)

            # Condition = Event
            case 'Event':
                condition = condition_event(item, condition)

            # Condition = App
            case 'App':
                the_apps = ''
                for apps in item:
                    if 'label' in apps.tag:
                        the_apps = the_apps + ' ' + apps.text
                condition = condition + 'Application' + the_apps

            # Condition = Location
            case 'Loc':
                lat = item.find('lat').text
                lon = item.find('long').text
                rad = item.find('rad').text
                if lat:
                    condition = condition + 'Location with latitude ' + lat + ' longitude ' + lon + ' radius ' + rad

            case _:
                pass

    if condition == '':
        return ''
    else:
        return cond_title + condition


# Clean up our memory hogs
def clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list):
    for elem in tree.iter():
        elem.clear()
    all_projects.clear()
    all_profiles.clear()
    all_tasks.clear()
    all_scenes.clear()
    root.clear()
    output_list.clear()


# Given a list [x,y,z] , print as x y z
def print_list(list_title,the_list):
    line_out = ''
    if list_title:
        print(list_title)
    for item in the_list:
        line_out = line_out + item + ' '
    print(line_out)
    return


# Validate the color name provided.  If color name is 'h', simply display all the colors
def validate_color(the_color):
    red_color_names = ['IndianRed', 'LightCoral', 'Salmon', 'DarkSalmon', 'LightSalmon', 'Crimson', 'Red', 'FireBrick',
                       'DarkRed']
    pink_color_names = ['Pink', 'LightPink', 'HotPink', 'DeepPink', 'MediumVioletRed', 'PaleVioletRed']
    orange_color_names = ['LightSalmon', 'Coral', 'Tomato', 'OrangeRed', 'DarkOrange', 'Orange']
    yellow_color_names = ['Gold', 'Yellow', 'LightYellow', 'LemonChiffon', 'LightGoldenrodYellow', 'PapayaWhip',
                          'Moccasin',
                          'PeachPuff', 'PaleGoldenrod', 'Khaki', 'DarkKhaki']
    purple_color_names = ['Lavender', 'Thistle', 'Plum', 'Violet', 'Orchid', 'Fuchsia', 'Magenta', 'MediumOrchid',
                          'MediumPurple', 'RebeccaPurple', 'BlueViolet', 'DarkViolet', 'DarkOrchid', 'DarkMagenta',
                          'Purple', 'Indigo', 'SlateBlue', 'DarkSlateBlue', 'MediumSlateBlue']
    green_color_names = ['GreenYellow', 'Chartreuse', 'LawnGreen', 'Lime', 'LimeGreen', 'PaleGreen', 'LightGreen',
                         'MediumSpringGreen', 'SpringGreen', 'MediumSeaGreen', 'SeaGreen', 'ForestGreen', 'Green',
                         'DarkGreen', 'YellowGreen', 'OliveDrab', 'Olive', 'DarkOliveGreen', 'MediumAquamarine',
                         'DarkSeaGreen',
                         'LightSeaGreen', 'DarkCyan', 'Teal']
    blue_color_names = ['Aqua', 'Cyan', 'LightCyan', 'PaleTurquoise', 'Aquamarine', 'Turquoise', 'MediumTurquoise',
                        'DarkTurquoise', 'CadetBlue', 'SteelBlue', 'LightSteelBlue', 'PowderBlue', 'LightBlue',
                        'SkyBlue',
                        'LightSkyBlue', 'DeepSkyBlue', 'DodgerBlue', 'CornflowerBlue', 'MediumSlateBlue', 'RoyalBlue',
                        'Blue', 'MediumBlue', 'DarkBlue', 'Navy', 'MidnightBlue']
    brown_color_names = ['Cornsilk', 'BlanchedAlmond', 'Bisque', 'NavajoWhite', 'Wheat', 'BurlyWood', 'Tan',
                         'RosyBrown',
                         'SandyBrown', 'Goldenrod', 'DarkGoldenrod', 'Peru', 'Chocolate', 'SaddleBrown',
                         'Sienna', 'Brown', 'Maroon']
    white_color_names = ['White', 'Snow', 'HoneyDew', 'MintCream', 'Azure', 'AliceBlue', 'GhostWhite', 'WhiteSmoke',
                         'SeaShell', 'Beige', 'OldLace', 'FloralWhite', 'Ivory', 'AntiqueWhite', 'Linen',
                         'LavenderBlush', 'MistyRose']
    gray_color_names = ['Gainsboro', 'LightGray', 'Silver', 'DarkGray', 'Gray', 'DimGray', 'LightSlateGray',
                        'SlateGray',
                        'DarkSlateGray', 'Black']

    all_colors = red_color_names + pink_color_names + orange_color_names + yellow_color_names + purple_color_names + \
                 green_color_names + blue_color_names + brown_color_names + white_color_names + gray_color_names

    if the_color == 'h':
        print_list('\nRed color names:', red_color_names)
        print_list('\nPink color names:', pink_color_names)
        print_list('\nOrange color names:', orange_color_names)
        print_list('\nYellow color names:', yellow_color_names)
        print_list('\nPurple color names:', purple_color_names)
        print_list('\nGreen color names:', green_color_names)
        print_list('\nBlue color names:', blue_color_names)
        print_list('\nBrown color names:', brown_color_names)
        print_list('\nWhite color names:', white_color_names)
        print_list('\nGray color names:', gray_color_names)
        exit(0)
    else:
        if the_color in all_colors:
            return True
        else:
            return False


# Get the runtime option for a color change and set it
def get_and_set_the_color(the_arg):
    global project_color, profile_color, task_color, action_color, disabled_profile_color, unknown_task_color, \
        disabled_action_color, action_condition_color, profile_condition_color, launcher_task_color, background_color, \
        scene_color, bullet_color, action_label_color
    types_for_color = ['Project', 'Profile', 'Task', 'Action', 'DisabledProfile', 'UnknownTask', 'DisabledAction',
                       'ActionCondition', 'ProfileCondition', 'LauncherTask', 'Background', 'Scene', 'Bullet',
                       'ActionLabel']

    the_color_option = the_arg[2:len(the_arg)].split('=')
    color_type = the_color_option[0]
    logger.debug('the_color_option:' + the_color_option[0] + 'color_type:' + color_type)
    if color_type not in types_for_color:
        print('Argument ' + the_arg + " is an invalid 'type' for color.  See the help (-h)!")
        exit(7)

    desired_color = the_color_option[1]
    logger.debug(' desired_color:' + desired_color)
    if validate_color(desired_color):  # If the color provided is valid...
        match color_type:  # Assign the color to the appropriate variable
            case 'Project':
                project_color = desired_color
            case 'Profile':
                profile_color = desired_color
            case 'Task':
                task_color = desired_color
            case 'Action':
                action_color = desired_color
            case 'DisabledProfile':
                disabled_profile_color = desired_color
            case 'UnknownTask':
                unknown_task_color = desired_color
            case 'DisabledAction':
                disabled_action_color = desired_color
            case 'ActionCondition':
                action_condition_color = desired_color
            case 'ProfileCondition':
                profile_condition_color = desired_color
            case 'LauncherTask':
                launcher_task_color = desired_color
            case 'Background':
                background_color = desired_color
            case 'Scene':
                scene_color = desired_color
            case 'Bullet':
                bullet_color = desired_color
            case 'ActionLabel':
                action_label_color = desired_color
            case _:
                print('get_and_set_the_color case not matching!')
                exit(1)


##############################################################################################################
#                                                                                                            #
#   Main Program Starts Here                                                                                 #
#                                                                                                            #
##############################################################################################################
def main():

    # Initialize local variables
    task_list = []
    found_tasks = []
    output_list = []
    projects_without_profiles = []
    single_task = ''
    single_task_found = ''
    single_task_nme_name = ''
    display_detail = 1     # Default (1) display detail: unknown Tasks actions only
    display_profile_conditions = False   # Default: False
    my_version = '6.3'

    my_file_name = '/MapTasker.html'
    no_profile = 'None or unnamed!'

    # Set up  html to use
    profile_color_html = '<span style = "color:' + profile_color + '"</span>'
    disabled_profile_html = ' <span style = "color:' + disabled_profile_color + '"</span>[DISABLED] ' + profile_color_html
    launcher_task_html = ' <span style = "color:' + launcher_task_color + '"</span>[Launcher Task] ' + profile_color_html
    condition_color_html = ' <span style = "color:' + profile_condition_color + '"</span>'

    help_text1 = '\nThis program reads a Tasker backup file (e.g. backup.xml) and displays the configuration of Profiles/Tasks/Scenes\n\n'
    help_text2 = 'Runtime options...\n\n  -h  for this help\n  -d0  display first Task action only, for unnamed Tasks only (silent)\n  ' \
                 '-d1  display all Task action details for unknown Tasks only (default)\n  ' \
                 '-d2  display full Task action details on every Task\n  ' \
                 "-t='a valid Task name'  display the details for a single Task only (automatically sets -d option to -d2)\n  " \
                 "-v  for this program's version\n  -p  display Profile conditions (default=unnamed Profiles only)\n  " \
                 "-c(type)=color_name  define a specific color to 'type', \n           where type is one of the following...\n  " \
                 "         Project Profile Task Action DisableProfile\n           UnknownTask DisabledAction ActionCondition\n           ProfileCondition LauncherTask Background\n  " \
                 "         Example options: -cTask=Green -cBackground=Black\n  -ch  color help: display all valid colors"

    help_text3 = '\n\nExit codes...\n  exit 1- program error\n  exit 2- output file failure\n ' \
                 ' exit 3- file selected is not a valid Tasker backup file\n ' \
                 ' exit 5- requested single Task not found\n  exit 6- no or improper filename selected\n ' \
                 ' exit 7- invalid option'
    help_text4 = '\n\nThe output HTML file is saved in your current folder/directory'

    caveat1 = '<span style = "color:Black"</span>CAVEATS:\n'
    caveat2 = '- Most but not all Task actions have been mapped and will display as such.  Likewise for Profile conditions.\n'
    caveat3 = '- This has only been tested on my own backup.xml file.' \
              '  For problems, email mikrubin@gmail.com and attach your backup.xml file .'
    caveat4 = '- Tasks that are identified as "Unnamed/Anonymous" have no name and are considered Anonymous.\n'
    caveat5 = '- For option -d0, Tasks that are identified as "Unnamed/Anonymous" will have their first Task only listed....\n' \
              '  just like Tasker does.'

    help_text = help_text1 + help_text2 + help_text3 + help_text4

    # Get any arguments passed to program
    logger.debug('sys.argv' + str(sys.argv))

    # Initialize tkinter
    tkroot = Tk()
    tkroot.geometry('200x100')
    tkroot.title("Select Tasker backup xml file")

    # Now go through the rest of the arguments
    for i, arg in enumerate(sys.argv):
        logger.debug('arg:' + arg)
        match arg[0:2]:
            case '-v':  # Version
                print('MapTask version ' + my_version)
                sys.exit()
            case '-h':  # Help
                print(help_text)
                sys.exit()
            case '-d':
                if arg == '-d0':  # Detail: 0 = no detail
                    display_detail = 0
                elif arg == '-d1':  # Detail: 0 = no detail
                    display_detail = 1
                elif arg == '-d2':  # Detail: 2 = all Task's actions/detail
                    display_detail = 2
            case '-t':
                if arg[2:3] == '=':
                    single_task = arg[3:len(arg)]
            case '-c':
                if arg[0:3] == '-ch':
                    validate_color('h')
                elif arg[0:2] == '-c':
                    get_and_set_the_color(arg)
            case '-p':
                display_profile_conditions = True
            case _:
                if 'MapTasker' not in arg:
                    print('Argument ' + arg + ' is invalid!')
                    exit(7)

    # Force full detail if we are doing a single Task
    if single_task:
        logger.debug('Single Task=' + single_task)
        display_detail = 2  # Force detailed output

    # Find the Tasker backup.xml
    if counter < 1:  # Only display message box on first run
        msg = 'Locate the Tasker backup xml file to use to map your Tasker environment'
        title = 'MapTasker'
        messagebox.showinfo(title, msg)

    dir_path = os.path.dirname(os.path.realpath(__file__))  # Get current directory
    filename = askopenfile(parent=tkroot, mode='r',
                           title='Select Tasker backup xml file', initialdir=dir_path,
                           filetypes = [('XML Files', '*.xml')])
    if filename is None:
        print('Backup selection cancelled.  Program ended.')
        exit(6)

    # Import xml
    tree = ET.parse(filename)
    root = tree.getroot()
    all_projects = root.findall('Project')
    all_profiles = root.findall('Profile')
    all_scenes = root.findall('Scene')
    all_tasks = root.findall('Task')

    if 'TaskerData' != root.tag:
        my_output(output_list, 0, 'You did not select a Tasker backup XML file...exit 2')
        exit(3)

    # Start the output with heading
    heading = '<body style="background-color:' + background_color + ';"><font face=' + output_font + '>Tasker Mapping................'
    my_output(output_list, 0, heading)
    my_output(output_list, 1, '')  # Start Project list

    # Traverse the xml

    # Start with Projects <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    for project in all_projects:
        if single_task_found == '1':   # Don't bother with another Project if we've done a single task only
            break
        project_name = project.find('name').text
        project_pids = ''
        my_output(output_list, 2, 'Project: ' + project_name)

        # Get Profiles and it's Project and Tasks
        my_output(output_list, 1, '')  # Start Profile list
        try:
            project_pids = project.find('pids').text  # Get a list of the Profiles for this Project
        # except xml.etree.ElementTree.ParseError doesn't compile:
        except Exception:  # Project has no Profiles
            projects_without_profiles.append(project_name)
            my_output(output_list, 2, 'Profile: ' + no_profile)
        if project_pids != '':  # Project has Profiles?
            profile_id = project_pids.split(',')

            # Now go through all the Profiles for this Project <<<<<<<<<<<<<<<<<<<<<
            for item in profile_id:
                # Find the Project's actual Profile element
                for profile in all_profiles:
                    # XML search order: id, mid"n", nme = Profile id, task list, Profile name
                    # Get the Tasks for this Profile
                    if item == profile.find('id').text:  # Is this the Profile we want?
                        task_list = []  # Get the Tasks for this Profile
                        our_task_element, our_task_name = get_profile_tasks(profile, all_tasks, found_tasks, task_list, single_task)
                        profile_name = ''
                        if debug:
                            profile_id = profile.find('id').text
                        # Examine Profile attributes
                        limit = profile.find('limit')  # Is the Profile disabled?
                        if limit is not None and limit.text == 'true':
                            disabled = disabled_profile_html
                        else:
                            disabled = ''
                        launcher_xml = profile.find('ProfileVariable')   # Is there a Launcher Task with this Profile?
                        if launcher_xml is not None:
                            launcher = launcher_task_html
                        else:
                            launcher = ''
                        if display_profile_conditions:
                            profile_condition = parse_profile_condition(profile)  # Get the Profile's condition
                            if profile_condition:
                                profile_name = condition_color_html + ' (' + profile_condition + ') ' + profile_color_html + profile_name + launcher + disabled
                        try:
                            profile_name = profile.find('nme').text + profile_name    # Get Profile's name
                        except Exception as e:  # no Profile name
                            if display_profile_conditions:
                                profile_condition = parse_profile_condition(profile)  # Get the Profile's condition
                                if profile_condition:
                                    profile_name = no_profile + condition_color_html + ' (' + profile_condition + ') ' + profile_color_html + launcher + disabled
                                else:
                                    profile_name = profile_name + no_profile + launcher + disabled
                            else:
                                profile_name = profile_name + no_profile + launcher + disabled
                        if debug:
                            profile_name = profile_name + ' ID:' + profile_id
                            my_output(output_list, 2,  profile_color_html + 'Profile: ' + profile_name)
                        else:
                            my_output(output_list, 2, 'Profile: ' + profile_name)

                # We have the Tasks.  Now let's output them.
                if our_task_name != '' and single_task:   # Are we mapping just a single Task?
                    if single_task == our_task_name:
                        my_output(output_list, 0, heading)
                        my_output(output_list, 1, '')  # Start Project list
                        my_output(output_list, 2, 'Project: ' + project_name)
                        my_output(output_list, 1, '')  # Start Profile list
                        my_output(output_list, 2, 'Profile: ' + profile_name)
                        output_list = output_list[len(output_list)-5:len(output_list)]  # Strip all output except last Profile name
                        my_output(output_list, 1, '')  # Start Project list
                        single_task_found = '1'
                        process_list('Task:', output_list, task_list, all_tasks, all_scenes, our_task_element,
                                     found_tasks, display_detail)
                        break  # Call it quits on Profiles
                    if single_task == our_task_name:
                        break  # Call it quits on Projects
                elif task_list:
                    process_list('Task:', output_list, task_list, all_tasks, all_scenes, our_task_element,
                                 found_tasks, display_detail)

        # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        if not (single_task and single_task_found):  # Only if not displaying a single Task
            scene_names = ''
            try:
                scene_names = project.find('scenes').text
            except Exception as e:
                pass
            if scene_names != '':
                scene_list = scene_names.split(',')
                process_list('Scene:', output_list, scene_list, all_tasks, all_scenes, our_task_element,
                             found_tasks, display_detail)

        my_output(output_list, 3, '')  # Close Profile list
    my_output(output_list, 3, '')  # Close Project list

    # #######################################################################################
    # Now let's look for Tasks that are not referenced by Profiles and display a total count
    # #######################################################################################
    # First, let's delete all the duplicates in the found task list
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
        if task_id == '103':
            logger.debug('No Profile ==========================' + task_id + '====================================')
        if task_id not in found_tasks:  # We have a solo Task not associated to any Profile
            project_name, the_project = get_project_for_solo_task(all_projects, task_id, projects_with_no_tasks)

            # At this point, we've found the Project this Task belongs to, or it doesn't belong to any Task
            if have_heading == 0:
                my_output(output_list, 0, '<hr>')  # blank line
                my_output(output_list, 0,
                          'Tasks that are not called by any Profile...')
                my_output(output_list, 1, '')  # Start Task list
                have_heading = 1

            # Get the Task's name
            try:
                task_name = task.find('nme').text
                single_task_nme_name = task_name
            except Exception as e:  # Task name not found!
                # Unknown Task.  Display details if requested
                task_name = unknown_task_name + '&nbsp;&nbsp;Task ID: ' + task_id
                if task_in_scene(task_id, all_scenes):  # Is this Task part of a Scene?
                    continue  # Ignore it if it is in a Scene
                else:     # Otherwise, let's add it to the count of unknown Tasks
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
                        output_list = ['<b><font face=' + output_font + '>MapTasker ...</b>']

                    if not unknown_task and display_detail == 1:  # Force -d0 if not unknown Task
                        temp_display_detail = display_detail
                        display_detail = 0
                    else:
                        temp_display_detail = ''
                    process_list('Task:', output_list, task_list, all_tasks, all_scenes, task,
                                 found_tasks, display_detail)
                    if temp_display_detail:
                        display_detail = temp_display_detail

    # Provide total number of unnamed Tasks
    if unnamed_task_count > 0:
        if display_detail > 0:
            my_output(output_list, 0, '')  # line
        my_output(output_list, 3, '')  # Close Task list
        if single_task_found == '' and display_detail != 0:   # If we don't have a single Task only, display total count of unnamed Tasks
            my_output(output_list, 0,
                      '<font color=' + unknown_task_color + '>There are a total of ' + str(
                          unnamed_task_count) + ' unnamed Tasks not associated with a Profile!')
    if task_name is True:
        my_output(output_list, 3,  '')  # Close Task list

    my_output(output_list, 3, '')  # Close out the list

    # List Projects with no Tasks
    if len(projects_with_no_tasks) > 0 and single_task_found == '':
        my_output(output_list, 0, '<hr><font color=Black><em>Projects Without Tasks...</em>')  # line
        for item in projects_with_no_tasks:
            my_output(output_list, 4, 'Project ' + item + ' has no Tasks')

    # List all Profiles with no Tasks
    if projects_without_profiles:
        my_output(output_list, 0, '<hr><font color=Black><em>Projects Without Profiles...</em>')  # line
        for item in projects_without_profiles:
            my_output(output_list, 4, 'Project ' + item + ' has no Profiles')

    # Requested single Task but invalid Task name provided (i.e. no Task found)?
    if single_task != '' and single_task_found == '':
        output_list.clear()
        print('Task ' + single_task + ' not found!!')
        clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)
        exit(5)

    # #######################################################################################
    # Let's wrap things up...
    # #######################################################################################
    # Output caveats if we are displaying the Actions
    my_output(output_list, 0, '<hr>')  # line
    my_output(output_list, 4, caveat1)  # caveat
    if display_detail > 0:  # Caveat about Actions
        my_output(output_list, 4, caveat2)  # caveat
    my_output(output_list, 4, caveat3)  # caveat
    my_output(output_list, 4, caveat4)  # caveat
    if display_detail == 0:  # Caveat about -d0 option and 1sat Action for unnamed Tasks
        my_output(output_list, 4, caveat5)  # caveat

    # Okay, lets generate the actual output file.
    # Store the output in the current  directory
    my_output_dir = os.getcwd()
    if my_output_dir is None:
        print('MapTasker cancelled.  An error occurred.  Program cancelled.')
        clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)
        exit(2)
    out_file = open(my_output_dir + my_file_name, "w")

    # Output the generated html
    for item in output_list:
        # Change "Action: nn ..." to Action nn: ..." (i.e. move the colon)
        action_position = item.find('Action: ')
        if action_position != -1:
            action_number_list = item[action_position+8:len(item)].split(' ')
            action_number = action_number_list[0]
            temp = item[0:action_position] + 'Action ' + action_number + ':' + item[action_position+8+len(action_number):len(item)]
            output_line = temp
        else:
            output_line = item
        out_file.write(output_line)

    out_file.close()  # Close our output file

    # Clean up memory
    clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)

    # Display final output
    webbrowser.open('file://' + my_output_dir + my_file_name, new=2)
    print("You can find 'MapTasker.html' in the current folder.  Your browser has displayed it in a new tab.  Program end.")


# Main call
if __name__ == "__main__":
    main()
