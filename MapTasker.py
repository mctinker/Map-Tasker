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
# Version 0.7.0                                                                              #
#                                                                                            #
# ########################################################################################## #

# imports for keeping track of number of runs
# from __future__ import print_function
import atexit
import logging
import os
import re
import sys
import webbrowser
import xml.etree.ElementTree as ET
from json import dumps, loads
from os import path

# importing tkinter and tkinter.ttk
# and all their functions and classes
from tkinter import *
from tkinter import messagebox

# importing askopenfile (from class filedialog) and messagebox functions
# importing askopenfile function
# from class filedialog
from tkinter.filedialog import askopenfile

# Add the following statement to your Terminal Shell configuration file (BASH, Fish, etc.
#  to eliminate the runtime msg: DEPRECATION WARNING: The system version of Tk is deprecated and may be removed...
#  export TK_SILENCE_DEPRECATION = 1

# ####################################################################################################
#  START User-modifiable global constants
# ####################################################################################################
continue_limit = 50  # Define the maximum number of Action lines to continue to avoid runaway for huge binary files
# Monospace fonts work best for if/then/else/end indentation alignment
output_font = 'Courier'  # OS X Default monospace font
# output_font = 'Roboto Regular'    # Google monospace font
dark_mode = True
if dark_mode:  # Dark background with light text colors
    project_color = 'White'  # Refer to the following for valid names: https://htmlcolorcodes.com/color-names/
    profile_color = 'LightPink'
    disabled_profile_color = 'Red'
    launcher_task_color = 'Chartreuse'
    task_color = 'Yellow'
    unknown_task_color = 'Red'
    scene_color = 'Lime'
    bullet_color = 'Black'
    action_color = 'DarkOrange'
    action_label_color = 'Magenta'
    action_condition_color = 'LemonChiffon'
    disabled_action_color = 'Crimson'
    profile_condition_color = 'Turquoise'
    background_color = 'DarkSlateGray'
    trailing_comments_color = 'LightSeaGreen'
else:  # White background with dark text colors
    project_color = 'Black'  # Refer to the following for valid names: https://htmlcolorcodes.com/color-names/
    profile_color = 'Blue'
    disabled_profile_color = 'Red'
    launcher_task_color = 'Chartreuse'
    task_color = 'Green'
    unknown_task_color = 'Red'
    scene_color = 'Purple'
    bullet_color = 'Black'
    action_color = 'DarkOrange'
    action_label_color = 'Magenta'
    action_condition_color = 'Coral'
    disabled_action_color = 'Crimson'
    profile_condition_color = 'Turquoise'
    background_color = 'Lavender'
    trailing_comments_color = 'PeachPuff'
# ####################################################################################################
#  END User-modifiable global constants
# ####################################################################################################

unknown_task_name = 'Unnamed/Anonymous.'
no_project = '-none found.'
counter_file = '.MapTasker_RunCount.txt'
font_to_use = '<font face=' + output_font + '>'
display_profile_conditions = True  # Default: False
heading = '<body style="background-color:' + background_color + '">' + font_to_use + 'Tasker Mapping................'
no_profile = 'None or unnamed!'

# Initial logging and debug mode
debug = True  # Controls the output of IDs / codes
debug_out = False  # Prints the line to be added to the output

logger = logging.getLogger('tipper')
# logger.setLevel(logging.DEBUG)   #  << Set for Debug
# logger.info('info message')
# The following are not used at this time
# logger.warning('warn message')
# logger.error('error message')
# logger.critical('critical message')
logger.addHandler(logging.StreamHandler())


def read_counter():
    return loads(open(counter_file, 'r').read()) + 1 if path.exists(counter_file) else 0


def write_counter():
    with open(counter_file, 'w') as f:
        f.write(dumps(run_counter))
    return


run_counter = read_counter()
atexit.register(write_counter)


# ####################################################################################################
# Strip all html style code from string (e.g. <h1> &lt) and return the cleaned string
# ####################################################################################################
def strip_string(the_string):
    # stripped = the_string
    stripped = the_string.replace('</b>', '')
    stripped = stripped.replace('<br>', '')
    stripped = stripped.replace('<small>', '')
    stripped = stripped.replace('<tt>', '')
    if '<font color=red' not in stripped:
        stripped = stripped.replace('<font', '')
    stripped = stripped.replace('&lt', '')
    stripped = stripped.replace('&gt', '')
    p = re.compile(r'<.*?>')
    stripped = p.sub('', stripped)
    return stripped


# ####################################################################################################
# Evaluate the If statement and return the operation
# ####################################################################################################
def evaluate_condition(child):
    the_operations = {
        '0': ' = ',
        '1': ' != ',
        '2': ' ~ ',
        '3': ' !~ ',
        '4': ' !~R ',
        '5': ' ~R ',
        '6': ' < ',
        '7': ' > ',
        '8': ' = ',
        '12': ' is set',
        '13': ' not set',
    }

    first_string = child.find('lhs').text
    operation = child.find('op').text
    the_operation = the_operations[operation]
    if 'set' not in the_operation and child.find('rhs').text is not None:  # No second string fort set/not set
        second_string = child.find('rhs').text
    else:
        second_string = ''

    return first_string, the_operation, second_string


# ####################################################################################################
# Get Task's label, disabled flag and any conditions
# ####################################################################################################
def get_label_disabled_condition(child):
    disabled_action_html = ' <span style = "color:' + disabled_action_color + '"</span>[DISABLED]'

    task_label = ''
    action_disabled = ''
    task_conditions = ''
    booleans = []
    the_action_code = child.find('code').text
    if child.find('label') is not None:
        lbl = child.find('label').text
        # We have to be careful what we strip out and what we replace for the label to maintain
        #  as much of the visual context as possible without blowing-up everything else that follows.
        if lbl != '' and lbl != '\n':
            lbl = lbl.replace('\n', '')
            lbl = lbl.replace('</font>', '')
            lbl = lbl.replace('</big>', '')
            lbl = lbl.replace('</font></font>', '</font>')
            font_count = lbl.count('<font')
            if font_count > 0:  # Make sure we end with the same number combination of <font> and </font>
                end_font_count = lbl.count('/font')
                if font_count > end_font_count:
                    lbl = lbl + '</font>'
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
                    boolean_to_inject = booleans[condition_count - 1].upper() + ' '
                task_conditions = task_conditions + ' <span style = "color:' + action_condition_color + '"</span> (' + \
                                  boolean_to_inject + 'condition:  If ' + string1 + operator + string2 + ')'
                condition_count += 1
    return task_conditions + action_disabled + task_label


# ####################################################################################################
# Convert a list of items to a comma-separated string of items
# ####################################################################################################
def list_to_string(the_list):
    if the_list is not None:
        s = ', '
        the_string = s.join(the_list)
        return the_string
    else:
        return ''


# ####################################################################################################
# Delete crap that might be in the label
# ####################################################################################################
def cleanup_the_result(results):
    results = results.replace(', ,', ',')
    results = results.replace(',,', ',')
    results = results.replace('<big>', '')
    return results


# ####################################################################################################
# Delete any trailing comma in output line
# ####################################################################################################
def drop_trailing_comma(match_results):
    last_valid_entry = len(match_results) - 1  # Point to last item in list
    if last_valid_entry > 0:
        for item in reversed(match_results):
            if item != '':
                if item[len(item) - 2:len(item)] == ', ':
                    match_results[last_valid_entry] = item[0:len(item) - 2]  # Strip off final ', '
                    return match_results
                else:
                    break
            else:
                last_valid_entry = last_valid_entry - 1
                pass
    return match_results


# ####################################################################################################
#  Given an action code (xml), find Int (integer) args and match with names
#  Example:
#  3 Ints with arg0, arg1 and arg2, to be filled in with their matching name0, name1 and name2 + the associated text
#  action = xml element for Action <code>
#  arguments = list of Int arguments to look for (e.g. arg1,arg5,arg9)
#  names = list of entries to substitute the argn value against.
#    ...It can be a list, which signifies a pull-down list of options to map against.
# ####################################################################################################
def get_xml_int_argument_to_value(action, arguments, names):
    match_results = []
    for child in action:
        if 'Int' == child.tag:
            the_arg = child.attrib.get('sr')
            for arg in arguments:
                if arg == the_arg:
                    arg_location = arguments.index(arg)
                    the_int_value = ''
                    if child.attrib.get('val') is not None:
                        the_int_value = child.attrib.get('val')  # There a numeric value as a string?
                    elif child.find('var') is not None:  # There is a variable name?
                        the_int_value = child.find('var').text
                    if the_int_value:  # If we have an integer or variable name
                        if type(names[arg_location]) is list:
                            the_list = names[arg_location]
                            the_title = the_list[0]  # Title is first element in the list
                            idx = 0
                            running = True
                            # Loop through list two items at a time: 1st element is digit, 2nd element is the name
                            # to apply if it matches.
                            while running:
                                idx = (idx + 1) % len(the_list)  # Get next element = first element in pair
                                this_element = the_list[idx]
                                if this_element.isdigit:  # First element of pair must be a digit
                                    idx = (idx + 1) % len(the_list)
                                    next_element = the_list[idx]  # Second element in pair
                                    if this_element == the_int_value:
                                        match_results.append(the_title + next_element + ', ')
                                        break
                                    idx = (idx + 1) % len(the_list)
                                    if idx > len(the_list):
                                        break
                                else:
                                    exit(8)  # Rutroh...not an even pair of elements
                            break  # Get out of arg loop and get next child
                        else:  # Not a list
                            match_results.append(names[arg_location] + the_int_value)  # Just grab the integer value
                            break
                    else:
                        match_results.append('')  # No Integer value or variable found...return empty
    match_results = drop_trailing_comma(match_results)  # Drop trailing comma
    return match_results


# ####################################################################################################
#  Given an action code (xml), find Str (string) args and match with names
#  Example:
#  3 Strs with arg0, arg1 and arg2, to be filled in with their matching name0, name1 and name2 + the associated text
# ####################################################################################################
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
    match_results = drop_trailing_comma(match_results)  # Drop trailing comma
    return match_results  # Must be empty


# ####################################################################################################
# Chase after relevant data after <code> Task action
# code_flag identifies the type of xml data to go after based on the specific code in <code>xxx</code>
# ####################################################################################################
def get_action_detail(code_flag, code_child, action_type):
    switch_types = {0: 'Off', 1: 'On', 2: 'Toggle'}

    if action_type:  # Only get extras if this is a Task action (vs. a Profile condition)
        extra_stuff = get_label_disabled_condition(code_child)  # Look for extra Task stiff: label, disabled, conditions
        if '<font' in extra_stuff and '</font>' not in extra_stuff:  # Make sure we terminate any fonts
            extra_stuff = extra_stuff + '</font>'
        if '&lt;font' in extra_stuff and '&lt;/font&gt;' not in extra_stuff:  # Make sure we terminate any fonts
            extra_stuff = extra_stuff + '</font>'
        if '<b>' in extra_stuff and '</b>' not in extra_stuff:  # Make sure we terminate any bold
            extra_stuff = extra_stuff + '</b>'
    else:
        extra_stuff = ''
    if debug and action_type:  # Add the code if this is an Action
        extra_stuff = extra_stuff + '<font color=red> code:' + code_child.find('code').text + '</font>'
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
                    return var1, var2, extra_stuff
                else:
                    pass
            return var1, var2, extra_stuff

        # Return first Int attrib
        case 3:
            var1 = code_child.find('Int')
            if var1 is not None:
                if var1.attrib.get('val') is not None:  # Integer value
                    return var1.attrib.get('val'), extra_stuff
                elif var1.find('var') is not None:  # Integer stored in variable
                    return var1.find('var').text, extra_stuff
            return '', extra_stuff

        # Get unlimited number of Str values into a list
        case 4:
            var1 = [child.text for child in code_child.findall('Str') if child.text is not None]
            [strip_string(item) for item in var1]
            # for item in var1:
            #     strip_string(item)
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
            child3 = child2.find('com.twofortyfouram.locale.intent.extra.BLURB')  # 2:40 am...funny!
            if child3 is not None and child3.text is not None:
                # Get rid of extraneous html in Action's label
                clean_string = child3.text.replace('</font><br><br>', '<br><br>')
                clean_string = clean_string.replace('&lt;', '<')
                clean_string = clean_string.replace('&gt;', '>')
                return clean_string + extra_stuff
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
            my_integer = []
            for child in code_child:  # Look for all Ints under this Action
                if child.tag == 'Int':
                    if child.attrib.get('val') is not None:  # Integer value
                        my_integer.append(child.attrib.get('val'))
                    elif child.find('var') is not None:  # Integer stored in variable
                        my_integer.append(child.find('var').text)
                else:
                    pass
            return my_integer, extra_stuff
            # my_int = [child.attrib.get('val') for child in code_child if child.tag == 'Int' and child.attrib.get('val') is not None]
            # return my_int, extra_stuff

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
                    return var1.attrib.get('val'), extra_stuff
            return strip_string(the_string), the_integer, extra_stuff

        # Get Image info
        case 10:
            child = code_child.find('Img')
            if child is not None:
                if child.find('nme') is None:
                    return '', '', extra_stuff
                if child.find('nme').text is not None:
                    image_name = child.find('nme').text
                else:
                    image_name = ''
                package_xml = child.find('pkg')
                if package_xml is not None:
                    package = package_xml.text
                else:
                    package = ''
                return image_name, package, extra_stuff
            return '', '', extra_stuff

        # Combine case 2 and case 3
        case 11:
            detail1, detail2, lbl = get_action_detail(2, code_child, action_type)
            detail3, lbl = get_action_detail(3, code_child, action_type)
            return detail1, detail2, detail3, lbl

        case _:
            return '???', '???', extra_stuff


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
    # The following dictionary provides the strings for various specific code Actions which need to be looked up.
    # Example: xml code '175' (Power Mode) Int value of '2' = 'Toggle' in list of strings 'Normal', 'Battery Saver', 'Toggle'
    lookup_values = {
        '906': {0: 'Off', 1: 'Hide Status Bar', 2: 'Hide Navigation Bar', 3: 'Hide Both', 4: 'Toggle Last'},
        '175': {0: 'Normal', 1: 'Battery Saver', 2: 'Toggle'},
        '318': {0: 'Off', 1: 'Portrait', 2: 'Portrait Reverse', 3: 'Landscape', 4: 'Landscape Reverse'},
        '162a': {0: 'Active', 1: 'Inactive', 2: 'Disabled'},
        '235': {0: 'Global', 1: 'Secure', 2: 'System'},
        '905': {0: 'Off', 1: 'Device Only', 2: 'Battery Saving', 3: 'High Accuracy'},
        '135': {0: 'Action Number', 1: 'Action Loop', 2: 'Top of Loop', 3: 'End of Loop', 4: 'End of If'},
        '192': {0: 'Alarm', 1: 'Notification', 2: 'Ringer'},
        '192a': {0: 'Call', 1: 'System', 2: 'Ringer', 3: 'Media', 4: 'Alarm', 5: 'Notification'},
        '820': {0: 'Never', 1: 'With AC Power', 2: 'With USB Power', 3: 'With AC or USB Power',
                4: 'With Wireless Power',
                5: 'With Wireless or AC Power', 6: 'With Wireless or USB Power', 7: 'With Wireless',
                8: 'AC or USB Power'},
        '348': {0: 'AutoRotate', 1: 'Orientation', 2: 'DPI', 3: 'Available Resolution', 4: 'Hardware Resolution',
                5: 'Is Locked', 6: 'Is Securely Locked', 7: 'Display Density', 8: 'Navigation Bar Height',
                9: 'Navigation Bar Top Offset', 10: 'Navigation Bar Top Offset', 11: 'Status Bar Offset'},
        '185': {0: 'Black and White', 1: 'Enhance Blue', 2: 'Enhance Green', 3: 'Greyscale', 4: 'Set Alpha'},
        '384': {0: 'Button', 1: 'Toggle', 2: 'Range', 3: 'Toggle Range', 4: 'No Action'},
        '443': {0: 'Next', 1: 'Pause', 2: 'Previous', 3: 'Toggle Pause', 4: 'Stop', 5: 'Play [Simulated Only]',
                6: 'Rewind', 7: 'Fast Forward'},
        '368': {0: 'Normal', 1: 'Satellite', 3: 'Terrain', 4: 'Hybrid', 5: 'None'},
        '455': {0: 'MP4', 1: '3GPP', 2: 'AMR Narrowband', 3: 'AMR Wideband', 4: 'Hgd'},
        '455a': {0: 'Default', 1: 'Microphone', 2: 'Call Outgoing', 3: 'Call Incoming', 4: 'Call'},
        '343': {0: 'Music File Artist Tag', 1: 'Music File Duration Tag', 2: 'Music File Title Tag',
                3: 'Music Playing Position', 4: 'Music Playing Position Millis'},
        '340': {0: 'Connect', 1: 'Disconnect', 2: 'Pair', 3: 'Unpair (Forget)'},
        '358': {0: 'Single Device', 1: 'Paired Devices', 2: 'Scan Devices'},
        '339': {0: 'GET', 1: 'POST', 2: 'HEAD', 3: 'PUT', 4: 'PATCH', 5: 'Delete', 6: 'OPTIONS', 7: 'TRACE'},
        '363': {0: 'Auto', 1: '2G', 2: '3G', 3: '4G', 4: '2G and 3G', 5: '3G and 4G', 6: '5G', 7: '3G and 4G and 5G',
                8: '4G and 5G'},
        '173': {0: 'Allow All', 1: 'Allow', 2: 'Deny All', 3: 'Deny'},
        '341': {0: 'Connection Type', 1: 'Mobile Data Enabled', 2: 'Wifi Hidden', 3: 'Wifi MAC', 4: 'Wifi RSSI',
                5: 'Wifi SSID', 6: 'BT Paired Addresses', 7: 'BT Device Connected', 8: 'BT Device Name',
                9: 'BT Device Class Name', 10: 'Auto Sync', 11: 'Wifi IP Address'},
        '426': {0: 'Disconnect', 1: 'Reassociate', 2: 'Reconnect'},
        '427': {0: 'Default', 1: 'Never While Plugged', 2: 'Never'},
        '910': {0: 'View', 1: 'Clear Missed Calls', 2: 'Clear Incoming Calls', 3: 'Clear Outgoing Calls',
                4: 'Clear All',
                5: 'Mark All Acknowledged', 6: 'Mark All Read'},
        '346': {0: 'Contact Address, Home', 1: 'Contact Address, Work', 2: 'Contact Birthday', 3: 'Contact Email',
                4: 'Contact Name', 5: 'Contact Nickname', 6: 'Contact Organization', 7: 'Contact Photo URl',
                8: 'Contact Thumb URl'},
        '69': {0: 'Button', 1: 'Checkbox', 2: 'Image', 3: 'Text', 4: 'TextEdit', 5: 'Doodle', 6: 'Map', 7: 'Menu',
               8: 'Number Picker', 9: 'Oval', 10: 'Rectangle', 11: 'Slider', 12: 'Spinner', 13: 'Switch', 14: 'Toggle',
               15: 'Video', 16: 'Webview'},
        '47': {0: 'Overlay', 1: 'Overlay, Blocking', 2: 'Overlay, Blocking, Full Window', 3: 'Dialog',
               4: 'Dialog, Dim Behind Heavy', 5: 'Dialog, Dim Behind', 6: 'Activity', 7: 'Activity, No Bar',
               8: 'Activity, No Status', 9: 'Activity, No Bar, No Status, No Nav'},
        '64': {0: 'Disable Compass', 1: 'Disable Rotation Gestures', 2: 'Disable Tilt Gestures',
               3: 'Disable Zoom Gestures',
               4: 'Enable Compass', 5: 'Enable Rotation Gestures', 6: 'Enable Tilt Gestures', 7: 'Enable Zoom Gestures',
               8: 'Hide Roads', 9: 'Hide Satellite', 10: 'Hide Traffic', 11: 'Hide Zoom Controls', 12: 'Move To Marker',
               13: 'Move To Marker Animated', 14: 'Move To Point', 15: 'Move To Point Animated', 16: 'Set Zoom',
               17: 'Show Roads', 18: 'Show Satellite', 19: 'Show Traffic', 20: 'Show Zoom Controls', 21: 'Zoom In',
               22: 'Zoom Out'},
        '51': {0: 'Replace Existing', 1: 'Start', 2: 'End'},
        '612': {0: 'Goto', 1: 'Load', 2: 'Pause', 3: 'Play', 4: 'Resume', 5: 'Set Zoom', 6: 'Back', 7: 'Forward',
                8: 'Stop', 9: 'Toggle'},
        '65': {0: 'False', 1: 'True', 2: 'Toggle'},
        '53': {0: 'Clear Cache', 1: 'Clear History', 2: 'Find', 3: 'Find Next', 4: 'Go Back', 5: 'Go Forward',
               6: 'Load URL', 7: 'Page Button', 8: 'Page Down', 9: 'Page Top', 10: 'Page Up', 11: 'Reload',
               12: 'Show Zoom Controls', 13: 'Stop Loading', 14: 'Zoom In', 15: 'Zoom Out'},
        '195': {0: 'Element Position', 1: 'Element Size', 2: 'Value', 3: 'Element Visibility', 4: 'Element Depth',
                5: 'Maximum Value'},
        '383': {0: 'Connectivity', 1: 'NFC', 2: 'Volume', 3: 'WiFi', 4: 'Media Output'},
        '431': {0: 'Start', 1: 'Stop', 2: 'Stop All', 3: 'Add To Keep Running', 4: 'Remove From Keep Running',
                5: 'Query', 6: 'Toggle'},
        '165': {0: 'Snooze Current', 1: 'Disable Current', 2: 'Disable By Label', 3: 'Disable By Time',
                4: 'Disable Any'},
        '566': {0: 'Default', 1: 'Off', 2: 'On'},
        '369': {0: 'Remove Duplicates', 1: 'Reverse', 2: 'Rotate Left', 3: 'Rotate Right', 4: 'Shuffle',
                5: 'Sort Alpha',
                6: 'Sort Alpha, Reverse', 7: 'Sort Alpha Caseless', 8: 'Sort Alpha Caseless, Reverse',
                9: 'Sort Shortest First',
                10: 'Sort Longest First', 11: 'Sort Numeric, Integer', 12: 'Sort Numeric', 13: 'Floating-Point',
                14: 'Squash'},
        '394': {0: 'Custom', 1: 'Now (Current Date and Time)', 2: 'Milliseconds Since Epoch', 3: 'Seconds Since Epoch',
                4: 'ISO 8601', 5: 'Milliseconds Since Epoch UTC', 6: 'Seconds Since Epoch UTC'},
        '394a': {0: 'None', 1: 'Seconds', 2: 'Minutes', 3: 'Hours', 4: 'Days'},
        '133': {0: 'Service Check (MS)', 1: 'BT Scan Period', 2: 'Wifi Scan Period', 3: 'GPS Check Period',
                4: 'Net Location Period',
                5: 'GPS Check Timeout', 6: 'Display Off, All Checks', 7: 'Display Off, All Checks Timeout',
                8: 'BT Check Min Timeout',
                9: 'Wifi Check Min Timeout', 10: 'Camera Delay (MS)', 11: 'Cell Workaround', 12: 'Net/Cell Wake Screen',
                13: 'Run In Foreground',
                14: 'Accelerometer', 15: 'Proximity Sensor', 16: 'Light Sensor', 17: 'Pressure Sensor',
                18: 'Temperature Sensor',
                19: 'Humidity Sensor', 20: 'Magnetic Sensor', 21: 'Step Sensor', 22: 'Use Reliable Alarms',
                23: 'Run Log',
                24: 'Debug To System Log', 25: 'Debug To Internal Storage', 26: 'Lock Code', 27: 'App Check Method',
                28: 'Use Motion Detection'},
        '162': {0: '1st', 1: '2nd', 2: '3rd'},
        '147': {0: 'UI', 1: 'Monitor', 2: 'Action', 3: 'Misc'},
        '347': {0: 'Action', 1: 'Event', 2: 'State', 3: 'Global', 4: 'Local', 5: 'Profiles', 6: 'Scenes', 7: 'Tasks',
                8: 'Timer Widget Remaining', 9: 'Current Task Name'},
        '544': {0: 'End', 1: 'Pause', 2: 'Resume', 3: 'Reset', 4: 'Update'},
        '596': {0: 'Bytes to Kilobytes', 1: 'Bytes to Megabytes', 2: 'Bytes to Gigabytes', 3: 'Date Time to Seconds',
                4: 'Seconds to Date Time', 5: 'Seconds to Medium Date Time', 6: 'Seconds to Long Date Time',
                7: 'HTML to Text',
                8: 'Celsius to Fahrenheit', 9: 'Fahrenheit to Celsius', 10: 'Centimeters to Inches',
                11: 'Inches to Centimeters',
                12: 'Meters to Feet', 13: 'Feet to Meters', 14: 'Kilograms to Pounds', 15: 'Pounds to Kilograms',
                16: 'Kilometers to Miles',
                17: 'Miles to Kilometers', 18: 'URL Decode', 19: 'URL Encode', 20: 'Binary to Decimal',
                21: 'Decimal to Binary',
                22: 'Hex to Decimal', 23: 'Decimal to Hex', 24: 'Base65 Encode', 25: 'Base65 Decode',
                26: 'To MD5 Digest',
                27: 'To SHA1 Digest', 28: 'To Lower Case', 29: 'To Upper Case', 30: 'To Uppercase First'},
        '595': {0: 'Normal Text', 1: 'Caps / Word', 2: 'Caps / All', 3: 'Numeric / Decimal', 4: 'Numeric / Integer',
                5: 'Password',
                6: 'Phone Number', 7: 'Passcode'},
        '523': {0: 'Red', 1: 'Green', 2: 'Blue', 3: 'Yellow', 4: 'Turquoise', 5: 'Purple', 6: 'Orange',
                7: 'Pink', 8: 'White'},
        '324': {0: 'Both', 1: 'Files', 2: 'Folders'}
    }

    no_yes = {0: 'No', 1: 'Yes'}
    orientation_type = {0: 'All', 1: 'Portrait', 2: 'Landscape'}

    variable_array = '&nbsp;&nbsp;Variable Array:'
    name_array = '&nbsp;&nbsp;Name:'
    type_array = '&nbsp;&nbsp;Type:'
    element_array = '&nbsp;&nbsp;Element'
    google_account = '&nbsp;&nbsp;Google Drive Account:'
    detail1, detail2, detail3, detail4, detail5, detail6 = '', '', '', '', '', ''

    task_code = code_child.text
    logger.debug('getcode:' + task_code)

    # Start the search for the code and provide the results
    match task_code:
        case '15':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Lock ' + list_to_string(detail1) + ' ' + lbl
        case '16':
            the_result = 'System Lock' + get_action_detail(0, code_action, type_action)
        case '18':
            detail1, detail2 = get_action_detail(5, code_action, type_action)
            the_result = 'Kill App package ' + detail1 + ' for app ' + detail2
        case '20':
            detail1, detail2 = get_action_detail(5, code_action, type_action)
            the_result = 'Launch App ' + detail1 + ' with app/package ' + detail2
        case '22':
            the_result = 'Load Last App' + get_action_detail(0, code_action, type_action)
        case '25':
            the_result = 'Go Home' + get_action_detail(0, code_action, type_action)
        case '30':
            detail1, detail2 = get_action_detail(3, code_action, type_action)
            the_result = 'Wait for ' + detail1 + detail2
        case '35':
            the_result = 'Wait' + get_action_detail(0, code_action, type_action)
        case '37':
            extra_stuff = ''
            if type_action:
                extra_stuff = get_label_disabled_condition(
                    code_action)  # Look for extra Task stuff: label, disabled, conditions
            for child in code_action:
                if 'ConditionList' == child.tag:  # If statement...
                    for children in child:
                        if 'Condition' == children.tag:
                            first_string, operator, second_string = evaluate_condition(children)
                            the_result = 'If ' + first_string + operator + second_string + extra_stuff
        case '38':
            the_result = 'End If' + get_action_detail(0, code_action, type_action)
        case '39':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'For ' + detail1 + ' to ' + detail2 + lbl
        case '40':
            the_result = 'End For' + get_action_detail(0, code_action, type_action)
        case '41':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Send SMS&nbsp;&nbsp;Number:' + detail1 + ', Message: ' + detail2 + lbl
        case '42':
            # detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            # detail3, lbl = get_action_detail(3, code_action, type_action)
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Send Data SMS&nbsp;&nbsp;Number:' + detail1 + ', Port: ' + detail3 + ', Data:' + detail2 + lbl
        case '43':
            the_result = 'Else/Else If' + get_action_detail(0, code_action, type_action)
        case '46':
            the_result = 'Create Scene ' + get_action_detail(1, code_action, type_action)
        case '47':
            the_arguments = ['arg0']
            the_names = [' Name:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg6', 'arg7', 'arg8', 'arg9']
            the_names = ['', '', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[1] == '1':
                detail1 = ', Show Exit Button'
            if the_int_values[2] == '1':
                detail2 = ', Continue Task Immediately'
            if the_int_values[3] == '1':
                detail3 = ', Allow Outside Boundaries'
            if the_int_values[4] == '1':
                detail4 = ', Blocking Overlay +'
            the_result = 'Show Scene&nbsp;&nbsp;' + the_str_values[0] + ' Display As:' + lookup_values['47'][
                int(the_int_values[0])] + \
                         detail1 + detail2 + detail3 + detail4 + get_action_detail(0, code_action, type_action)
        case '48':
            the_result = 'Hide Scene ' + get_action_detail(1, code_action, type_action)
        case '49':
            the_result = 'Destroy Scene ' + get_action_detail(1, code_action, type_action)
        case '50':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Element Value&nbsp;&nbsp;Scene Name:' + detail2 + ', Element:' + detail3 + ', Value:' + detail3 + lbl
        case '51':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Element Text&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + ', Position:' + \
                         lookup_values['51'][int(detail3)] + lbl
        case '53':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Element Web Control&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + ', Mode:' + \
                         lookup_values['53'][int(detail3)] + lbl
        case '54':
            the_arguments = ['arg0', 'arg1', 'arg2']
            the_names = [' Scene Name:', ' Element:', ' Colour:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Element Text Colour&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         get_action_detail(0, code_action, type_action)
        case '55':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3']
            the_names = [' Scene Name:', ' Element:', ' Colour:', ' End Colour:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Element Back Colour&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         the_str_values[3] + get_action_detail(0, code_action, type_action)
        case '56':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_arguments = ['arg0', 'arg1', 'arg3']
            the_names = [' Scene Name:', ' Element:', ' Colour:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Element Border&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + ' Width:' + detail1 + \
                         the_str_values[2] + lbl
        case '57':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_arguments = ['arg2', 'arg3', 'arg4', 'arg5']
            the_names = ['', ', X:', ', Y:', ', Animation Time:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            orientation = orientation_type[int(the_int_values[0])]
            the_result = 'Element Position&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + ', Orientation:' + \
                         orientation + the_int_values[1] + the_int_values[2] + the_int_values[3] + lbl
        case '58':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_arguments = ['arg2', 'arg3', 'arg4', 'arg5']
            the_names = ['', ', Width:', ', Height:', ', Animation Time:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            orientation = orientation_type[int(the_int_values[0])]
            the_result = 'Element Size&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + ', Orientation:' + \
                         orientation + the_int_values[1] + the_int_values[2] + the_int_values[3] + lbl
        case '60':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3', 'arg7']
            the_names = [' Scene Name:', ' Element:', ' Lat,Long:', ' Label:', ', Spot Color:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg5', 'arg6']
            the_names = ['', ' Spot Radius:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Element Add GeoMarker ' + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         the_str_values[3] + \
                         the_int_values[1] + the_str_values[4] + get_action_detail(0, code_action, type_action)
        case '61':
            detail1, detail2 = get_action_detail(3, code_action, type_action)
            the_result = 'Vibrate time at  ' + detail1 + detail2
        case '62':
            the_result = 'Vibrate Pattern of ' + get_action_detail(1, code_action, type_action)
        case '63':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3']
            the_names = [' Scene Name:', ' Element:', ' Lat,Long:', ' Label:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Element Delete GeoMarker&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + \
                         the_str_values[2] + \
                         the_str_values[3] + get_action_detail(0, code_action, type_action)
        case '64':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Element Map Control&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + ', Mode:' + \
                         lookup_values['64'][int(detail3)] + lbl
        case '65':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_arguments = ['arg2', 'arg3', 'arg4']
            the_names = ['', ' Animated Time:', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[2] == '1':
                detail3 = ', Continue Task Immediately'
            the_result = 'Element Visibility&nbsp;&nbsp;Scene Name:' + detail1 + ', Element Match:' + detail2 + ', Set:' + \
                         lookup_values['65'][int(the_int_values[0])] + the_int_values[1] + detail3 + lbl
        case '66':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Element Image&nbsp;&nbsp;Scene Name:' + detail1 + 'Element:' + detail2 + lbl
        case '67':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Element Depth&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + ', Depth:' + detail3 + lbl
        case '68':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail3 == '1':
                detail3 = ', Set'
            the_result = 'Element Focus&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + detail3 + lbl
        case '69':
            the_arguments = ['arg0', 'arg3']
            the_names = [' Scene Name:', ' Content:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg2']
            the_names = ['', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[1] == '1':
                detail1 = ', Visible:On'
            the_result = 'Element Create&nbsp;&nbsp' + the_str_values[0] + ' Type:' + lookup_values['69'][
                int(the_int_values[0])] + \
                         detail1 + the_str_values[1] + get_action_detail(0, code_action, type_action)
        case '71':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Element Text Size&nbsp;&nbsp;Scene Name:' + detail1 + 'Element:' + detail2 + ', Text Size:' + detail3 + lbl
        case '73':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Element Destroy&nbsp;&nbsp;Scene Name:' + detail1 + 'Element:' + detail2 + lbl
        case '90':
            the_arguments = ['arg0', 'arg2']
            the_names = [' Number:', ' SIM Card:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1']
            the_names = ['']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Call&nbsp;&nbsp;' + the_str_values[0] + ' Auto Dial:' + no_yes[
                int(the_int_values[0])] + ', ' + \
                         the_str_values[1] + get_action_detail(0, code_action, type_action)
        case '95':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail1 != '':
                detail1 = ' Number Match:' + detail1
            if detail3 != '':
                detail3 = ' Info:Yes'
            the_result = 'Call Block&nbsp;&nbsp;' + detail1 + detail3 + lbl
        case '97':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail1 != '':
                detail1 = ' From Match:' + detail1
            if detail3 != '':
                detail3 = ' Info:Yes'
            the_result = 'Call Divert&nbsp;&nbsp;' + detail1 + detail3 + lbl
        case '99':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail1 != '':
                detail1 = ' Number:' + detail1
            if detail3 != '':
                detail3 = ' Info:Yes'
            the_result = 'Call Revert&nbsp;&nbsp;' + detail1 + detail3 + lbl
        case '100':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail3 == '1':
                detail3 = ', Web Search'
            the_result = 'Search&nbsp;&nbsp;For:' + detail1 + detail3 + lbl
        case '101':
            the_result = 'Take Photo filename ' + get_action_detail(1, code_action, type_action)
        case '102':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Open File&nbsp;&nbsp;' + detail1 + ' ' + detail2 + lbl
        case '103':
            detail1, xtra = get_action_detail(8, code_action, type_action)
            the_result = 'Light Level&nbsp;&nbsp;From:' + detail1[0] + ', To:' + detail1[1] + xtra
        case '104':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            detail4, the_app = get_action_detail(5, code_action, type_action)  # Get App
            detail4 = the_app.split('<')  # Get rid of the label
            the_result = 'Browse URL&nbsp;&nbsp;URL:' + detail1 + ', Pkg/App:' + detail4[0] + ', "Open With" Dialog:' + \
                         no_yes[int(detail3)] + ', "Open With" Title:' + detail2 + lbl
        case '105':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            if detail1 == '1':
                detail1 = ', Add'
            the_arguments = ['arg0', 'arg2']
            the_names = [' Text:', ' Image:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Set Clipboard&nbsp;&nbsp;' + the_str_values[0] + detail1 + the_str_values[1] + lbl
        case '109':
            the_result = 'Set Wallpaper' + name_array + get_action_detail(1, code_action, type_action)
        case '111':
            the_arguments = ['arg1', 'arg2', 'arg3']
            the_names = ['', '', '']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            if the_str_values[0] != '':
                detail1 = 'Subject:' + the_str_values[0]
            if the_str_values[1] != '':
                detail1 = detail1 + ' Message:' + the_str_values[1]
            if the_str_values[2] != '':
                detail1 = detail1 + ' Attachment:' + the_str_values[2]
            the_result = 'Compose MMS&nbsp;&nbsp;' + detail1 + get_action_detail(0, code_action, type_action)
        case '112':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Run SLA4 Script&nbsp;&nbsp;' + detail1 + ' ' + detail2 + lbl
        case '113':
            the_result = 'Wifi Tether&nbsp;&nbsp;' + get_action_detail(7, code_action, type_action)
        case '116':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3', 'arg4', 'arg6', 'arg7']
            the_names = [' Server:Port:', ' Path:', ' Data/File:', ' Cookies', ' User Agent:', ' Content Type',
                         ' Output File:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail1, lbl = get_action_detail(8, code_action, type_action)
            the_result = 'HTTP Post&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         the_str_values[3] + the_str_values[4] + ' Timeout:' + detail1[0] + the_str_values[5] + \
                         the_str_values[6] + ' Trust Any Certificate:' + no_yes[int(detail1[1])] + lbl
        case '117':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3', 'arg4']
            the_names = [' Server:Port:', ' Path:', ' Attributes:', ' Cookies', ' User Agent:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail1, lbl = get_action_detail(8, code_action, type_action)
            the_result = 'HTTP Head&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         the_str_values[3] + the_str_values[4] + ', Timeout:' + detail1[
                             0] + ', Trust Any Certificate:' + \
                         no_yes[int(detail1[1])] + lbl
        case '118':
            the_result = 'HTTP Get&nbsp;&nbsp;' + get_action_detail(1, code_action, type_action)
        case '119':
            the_result = 'Open Map&nbsp;&nbsp;Address:' + get_action_detail(1, code_action, type_action)
        case '123':
            the_result = 'Run Shell&nbsp;&nbsp;' + get_action_detail(1, code_action, type_action)
        case '125':
            the_arguments = ['arg0', 'arg1', 'arg2']  # Recipient, Subject, Message
            the_names = [' Recipient:', ' Subject:', ' Message:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Compose Email&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + the_str_values[2]
        case '126':
            the_result = 'Return' + get_action_detail(0, code_action, type_action)
        case '129':
            the_result = 'JavaScriptlet&nbsp;&nbsp;' + get_action_detail(1, code_action, type_action)
        case '130':
            the_result = 'Perform Task' + name_array + get_action_detail(1, code_action, type_action)
        case '131':
            the_result = 'JavaScript&nbsp;&nbsp;' + get_action_detail(1, code_action, type_action)
        case '133':
            detail1, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints
            the_result = 'Set Tasker Pref&nbsp;&nbsp;Set:' + lookup_values['133'][int(detail1[0])] + ', Value:' + \
                         detail1[
                             1] + lbl
        case '134':
            the_result = 'Query Action&nbsp;&nbsp;Action:' + get_action_detail(1, code_action, type_action)
        case '135':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            the_result = 'Go To type ' + lookup_values['135'][int(detail1)] + detail2
        case '136':
            the_result = 'Sound Effects set to ' + get_action_detail(7, code_action, type_action)
        case '137':
            the_result = 'Stop' + get_action_detail(0, code_action, type_action)
        case '138':
            detail1, detail2, lbl = get_action_detail(10, code_action, type_action)  # Get int
            the_result = 'Set Tasker Icon&nbsp;&nbsp;Icon:' + detail1 + ', Package:' + detail2 + lbl
        case '139':
            the_result = 'Disable (Tasker)'
        case '140':
            the_arguments = ['arg0', 'arg1']
            the_names = [' From:', ' To:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Change Icon Set&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + get_action_detail(0,
                                                                                                                   code_action,
                                                                                                                   type_action)
        case '142':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            if detail2:
                detail2 = ', Action:' + detail2
            the_result = 'Edit Task&nbsp;&nbsp;Task:' + detail1 + detail2 + lbl
        case '143':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            if detail2:
                detail2 = ', Element:' + detail2
            the_result = 'Edit Scene&nbsp;&nbsp;Scene Name' + detail1 + detail2 + lbl
        case '147':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            the_result = 'Show Prefs&nbsp;&nbsp;Section:' + lookup_values['147'][int(detail1)] + lbl
        case '148':
            the_result = 'Show Runlog' + get_action_detail(0, code_action, type_action)
        case '150':
            the_result = 'Keyboard set ' + get_action_detail(7, code_action, type_action)
        case '152':
            detail1, detail2, lbl = get_action_detail(10, code_action, type_action)
            detail3, detail4, lbl = get_action_detail(2, code_action, type_action)
            if detail2:
                detail2 = ', Element:' + detail2
            the_result = 'Set Widget Icon' + name_array + detail3 + ', Icon:' + detail1 + ', Package:' + detail2
        case '153':
            detail1, lbl = get_action_detail(8, code_action, type_action)
            if detail1[0] == '0':
                detail2 = 'Task'
            else:
                detail2 = 'Configuration'
            if len(detail1) > 1 and detail1[1] == '0':
                detail3 = ', Source: Variable'
            the_result = 'Import Data' + type_array + detail2 + detail3
        case '155':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            if detail2 != '':
                detail2 = ', Label:' + detail2
            the_result = 'Set Widget Label' + name_array + detail1 + detail2 + lbl
        case '156':
            the_arguments = ['arg1', 'arg2']  # Ints: Format, Locality, Best Timeing
            the_names = [[' Locality:', '0', 'English', '1', ' German/Deutsch'],
                         ' Beat Timing:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'MIDI Play  Format: Tasker, ' + the_int_values[0] + the_int_values[1] + \
                         ' Score:' + get_action_detail(1, code_action, type_action)
        case '159':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)  # Get two Strs (only need first)
            the_result = 'Profile Status' + name_array + detail1 + ', Set:' + get_action_detail(7, code_action,
                                                                                                type_action)
        case '160':
            the_result = 'Wifi Connected ' + get_action_detail(1, code_action, type_action)
        case '161':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3']
            the_names = ['', '', '', '']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail1 = range(0, 4)  # Go through 4 Strs
            for detail3 in detail1:
                if the_str_values[detail3] != '':
                    detail2 = detail2 + 'Task(' + str(detail3) + '):' + the_str_values[detail3]
            the_result = 'Setup App Shortcuts&nbsp;&nbsp;' + detail2 + get_action_detail(0, code_action, type_action)
        case '162':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)  # Get two Strs
            detail3, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints
            if detail3[2] != '0':
                detail4 = ', Can Use On Locked Device'
            if detail2 != '':
                detail2 = ', Long Click Task:' + detail2
            the_result = 'Setup Quick Setting Tile&nbsp;&nbsp;Number:' + lookup_values['162'][int(detail3[0])] + \
                         ', Name:' + detail1 + ', Status:' + lookup_values['162a'][
                             int(detail3[1])] + detail4 + detail2 + lbl
        case '165':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            the_result = 'Cancel Alarm&nbsp;&nbsp;Mode:' + lookup_values['165'][int(detail1)] + lbl
        case '166':
            the_result = 'Show Alarms ' + get_action_detail(0, code_action, type_action)
        case '171':
            the_result = 'Beep' + get_action_detail(0, code_action, type_action)
        case '172':
            detail1 = get_action_detail(1, code_action, type_action)
            the_result = 'Morse ' + detail1
        case '173':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            detail2, app = get_action_detail(5, code_action, type_action)
            the_result = 'Network Access&nbsp;&nbsp;Mode:' + lookup_values['173'][
                int(detail1)] + ', Package/App Name:' + app
        case '171':
            the_result = 'Power Mode' + get_action_detail(0, code_action, type_action)
        case '175':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            the_result = 'Power Mode set to ' + lookup_values[task_code][int(detail1[0])] + ' ' + detail2
        case '176':
            the_result = 'Take Screenshot file ' + get_action_detail(1, code_action, type_action)
        case '177':
            the_result = 'Haptic Feedback set to ' + get_action_detail(7, code_action, type_action)
        case '185':
            detail1, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints
            detail3 = lookup_values['185'][int(detail1[0])]
            the_result = 'Filter Image mode ' + detail3 + ' threshold:' + detail1[1] + lbl
        case '187':
            detail1 = get_action_detail(1, code_action, type_action)  # Get Str
            detail2, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints
            if detail2[1] == 1:
                detail3 = ' Delete From Memory After '
            the_result = 'Save Image image quality:' + detail2[0] + detail3 + ' file:' + detail1
        case '188':
            max_wh = ''
            lbl = get_action_detail(0, code_action, type_action)
            for child in code_action:  # We have to traverse the xml here due to complexity
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
                        break
            the_result = 'Load Image ' + the_image + max_wh + detail2 + lbl
        case '189':
            detail1, lbl = get_action_detail(8, code_action, type_action)
            the_result = 'Crop Image from left:' + detail1[0] + ' from right:' + detail1[1] + ' from top:' + detail1[
                2] + ' from bottom:' + detail1[3] + lbl
        case '190':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            if detail1 == '0':
                detail1 = 'Horizontal'
            else:
                detail1 = 'Vertical'
            the_result = 'Flip Image ' + detail1 + detail2
        case '191':
            detail1, detail2 = get_action_detail(8, code_action, type_action)  # Get all Ints
            if detail1[0] == '0':
                detail1 = 'Left'
            else:
                detail1 = 'Right'
            the_result = 'Rotate Image ' + detail1 + detail2
        case '192':
            the_arguments = ['arg0', 'arg2']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Play Ringtone  Type:' + lookup_values['192'][int(the_int_values[0])] + ', Stream:' + \
                         lookup_values['192a'][int(the_int_values[1])] + \
                         ', Sound:' + get_action_detail(1, code_action, type_action)
        case '193':
            the_result = 'Resize Image ' + get_action_detail(1, code_action, type_action)
        case '194':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Test Scene ' + detail1 + ' store in ' + detail2 + lbl
        case '195':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Test Element&nbsp;&nbsp;Scene Name:' + detail1 + ', Element:' + detail2 + ', Test:' + \
                         lookup_values['195'][int(detail3)] + lbl
        case '197':
            the_result = 'Developer Settings' + get_action_detail(0, code_action, type_action)
        case '198':
            the_result = 'Device Info Settings' + get_action_detail(0, code_action, type_action)
        case '199':
            the_result = 'Add Account Settings' + get_action_detail(0, code_action, type_action)
        case '200':
            the_result = 'All Settings' + get_action_detail(0, code_action, type_action)
        case '201':
            the_result = 'Airplane Mode Settings' + get_action_detail(0, code_action, type_action)
        case '202':
            the_result = 'APN Settings' + get_action_detail(0, code_action, type_action)
        case '203':
            the_result = 'Date Settings' + get_action_detail(0, code_action, type_action)
        case '204':
            the_result = 'Internal Storage Settings' + get_action_detail(0, code_action, type_action)
        case '206':
            the_result = 'Wireless Settings' + get_action_detail(1, code_action, type_action)
        case '208':
            the_result = 'Location Settings' + get_action_detail(0, code_action, type_action)
        case '210':
            the_result = 'Input Method Settings' + get_action_detail(0, code_action, type_action)
        case '211':
            the_result = 'Sync Settings' + get_action_detail(1, code_action, type_action)
        case '212':
            the_result = 'WiFi IP Settings' + get_action_detail(1, code_action, type_action)
        case '214':
            the_result = 'Wireless Settings' + get_action_detail(0, code_action, type_action)
        case '216':
            the_result = 'App Settings' + get_action_detail(1, code_action, type_action)
        case '218':
            the_result = 'Bluetooth Settings' + get_action_detail(1, code_action, type_action)
        case '219':
            the_result = 'Quick Settings' + get_action_detail(1, code_action, type_action)
        case '220':
            the_result = 'Mobile Data Settings' + get_action_detail(0, code_action, type_action)
        case '222':
            the_result = 'Display Settings' + get_action_detail(0, code_action, type_action)
        case '224':
            the_result = 'Locale Settings' + get_action_detail(0, code_action, type_action)
        case '226':
            the_result = 'App Manager Settings' + get_action_detail(0, code_action, type_action)
        case '227':
            the_result = 'Memory Card Settings' + get_action_detail(0, code_action, type_action)
        case '228':
            the_result = 'Network Operator Settings' + get_action_detail(0, code_action, type_action)
        case '230':
            the_result = 'Security Settings' + get_action_detail(1, code_action, type_action)
        case '231':
            the_result = 'Search Settings' + get_action_detail(1, code_action, type_action)
        case '232':
            the_result = 'Sound Settings' + get_action_detail(1, code_action, type_action)
        case '234':
            the_result = 'Dictionary Settings' + get_action_detail(0, code_action, type_action)
        case '235':
            the_arguments = ['arg1', 'arg2', 'arg4']
            the_names = [' Name:', ' Value:', ' Read Setting To:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg0', 'arg3']
            the_names = ['', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if len(the_int_values) > 1 and the_int_values[1] == '1':
                detail1 = ' Use Root'
            if len(the_str_values) == 3:
                detail2 = the_str_values[2]
            the_result = 'Custom Settings type ' + lookup_values['235'][int(the_int_values[0])] + the_str_values[0] + \
                         the_str_values[1] + detail2 + detail1 + get_action_detail(0, code_action, type_action)
        case '236':
            the_result = 'Accessibility Settings' + get_action_detail(0, code_action, type_action)
        case '237':
            the_result = 'Notification Listener Settings' + get_action_detail(0, code_action, type_action)
        case '238':
            the_result = 'Privacy Settings' + get_action_detail(0, code_action, type_action)
        case '239':
            the_result = 'Print Settings' + get_action_detail(0, code_action, type_action)
        case '244':
            the_result = 'Toggle Split Screen' + get_action_detail(0, code_action, type_action)
        case '245':
            the_result = 'Back Button' + get_action_detail(0, code_action, type_action)
        case '246':
            the_result = 'Long Power Button' + get_action_detail(0, code_action, type_action)
        case '247':
            the_result = 'Show Recents' + get_action_detail(0, code_action, type_action)
        case '248':
            the_result = 'Turn Off' + get_action_detail(0, code_action, type_action)
        case '249':
            the_result = 'System Screenshot' + get_action_detail(0, code_action, type_action)
        case '250':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            if detail1 != '':
                detail1 = 'Recipient(s):' + detail1 + ', Message:'
            the_result = 'Compose SMS&nbsp;&nbsp;' + detail1 + detail2 + lbl
        case '251':
            the_result = 'Battery Settings' + get_action_detail(0, code_action, type_action)
        case '252':
            detail1, detail2 = get_action_detail(5, code_action, type_action)
            the_result = 'Set SMS App&nbsp;&nbsp;App:' + detail2
        case '254':
            the_result = 'Speakerphone set to ' + get_action_detail(7, code_action, type_action)
        case '256':
            the_result = 'Vibrate On Ringer set to ' + get_action_detail(7, code_action, type_action)
        case '259':
            the_result = 'Notification Pulse set to ' + get_action_detail(7, code_action, type_action)
        case '294':
            the_result = 'Bluetooth &nbsp;&nbsp;Set:' + get_action_detail(7, code_action, type_action)
        case '295':
            the_result = 'Bluetooth ID' + name_array + get_action_detail(1, code_action, type_action)
        case '296':
            the_result = 'Bluetooth Voice ' + get_action_detail(7, code_action, type_action)
        case '300':
            the_result = 'Anchor' + get_action_detail(0, code_action, type_action)
        case '301':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Mic Volume set to  ' + detail1 + lbl
        case '303':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Alarm Volume to  ' + detail1 + lbl
        case '304':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Ringer Volume to  ' + detail1 + lbl
        case '305':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                the_result = 'Notification Volume to  ' + detail1 + lbl
            else:
                the_result = 'Notification Volume' + lbl
        case '306':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'In-Call Volume set to  ' + detail1 + lbl
        case '307':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                the_result = 'Media Volume to  ' + detail1 + lbl
            else:
                the_result = 'Media Volume' + lbl
        case '308':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'System Volume to  ' + detail1 + lbl
        case '309':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'DTMF Volume to  ' + detail1 + lbl
        case '310':
            the_result = 'Vibrate Mode set to ' + get_action_detail(7, code_action, type_action)
        case '311':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                the_result = 'BT Voice Volume to ' + detail1 + lbl
        case '312':
            the_result = 'Do Not Disturb' + get_action_detail(0, code_action, type_action)
        case '313':
            the_result = 'Sound Mode' + get_action_detail(0, code_action, type_action)
        case '314':
            detail1, lbl = get_action_detail(4, code_action, type_action)  # All Strs
            detail2, lbl = get_action_detail(8, code_action, type_action)  # All Ints
            if detail2[0] is not None:
                if detail2[0] == '0':
                    the_type = 'Credentials'
                else:
                    the_type = 'Biometric'
            if len(detail2) > 2:
                detail3 = ' timeout:' + detail2[3]
            the_result = 'Authentication Dialog type ' + the_type + list_to_string(detail1) + detail3
        case '316':
            the_result = 'Display Size' + get_action_detail(0, code_action, type_action)
        case '317':
            the_result = 'NFS&nbsp;&nbsp;set to ' + get_action_detail(7, code_action, type_action)
        case '318':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                the_result = 'Force Rotation ' + lookup_values['318'][int(detail1)] + lbl
            else:
                the_result = 'Force Rotation ' + lbl
        case '319':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Ask Permissions&nbsp;&nbsp;Required Permissions:' + detail1 + ', Prompt If Not Granted:' + detail2 + lbl
        case '320':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            detail2, lbl = get_action_detail(4, code_action, type_action)  # Get all Strs
            the_result = 'Ping&nbsp;&nbsp;Host:' + detail2[0] + ', Number:' + detail1 + ', Average Result Var:' + \
                         detail2[1] + \
                         ', Min Result Var:' + detail2[2] + ', Max Result Var:' + detail2[3] + lbl
        case '321':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg8']
            the_names = ['', ' Data/File:', ' Remote File:', 'Remote Folder:', 'Content Description:', ', Mime Type:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg6', 'arg7']
            the_names = ['', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[0] == '1':
                detail1 = ', Overwrite If Exists'
            if the_int_values[1] == '1':
                detail2 = ', Publicly Share File'
            the_result = 'GD Upload' + google_account + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         the_str_values[3] + the_str_values[4] + detail1 + detail2 + the_str_values[5] + \
                         get_action_detail(0, code_action, type_action)
        case '322':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail2:
                detail2 = ', Google Drive Account:' + detail2
            if detail3 == '1':
                detail3 = ', Include User Vars/Prefs'
            the_result = 'Data Backup&nbsp;&nbsp;Path:' + detail1 + detail2 + detail3 + lbl
        case '323':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3', 'arg4']  # Bluetooth, Cell, NFC, WiFi, Wimax
            the_names = ['', '', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Airplane Radios&nbsp;&nbsp;Bluetooth:' + no_yes[int(the_int_values[0])] + \
                         ', Cell:' + no_yes[int(the_int_values[1])] + ', NFC:' + no_yes[int(the_int_values[2])] + \
                         ', WiFi:' + no_yes[int(the_int_values[3])] + ', Wimax:' + no_yes[int(the_int_values[4])] + \
                         get_action_detail(0, code_action, type_action)
        case '324':
            the_arguments = ['arg1', 'arg5']
            the_names = ['', ', Query:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail2, lbl = get_action_detail(8, code_action, type_action)
            if detail2[0] == '0':
                detail3 = 'Remote Folder'
            else:
                detail3 = 'Query'
            the_result = 'GD List' + google_account + the_str_values[0] + ' Type:' + detail3 + ', Files or Folders:' + \
                         lookup_values['324'][int(detail2[1])] + the_str_values[1] + lbl
        case '325':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)  # All two Strs
            detail3, lbl = get_action_detail(8, code_action, type_action)  # All Ints
            detail4 = ' Trash Value:'
            if detail3[0] == '0':
                detail4 = detail4 + 'Trash'
            else:
                detail4 = detail4 + 'Remove From Trash'
            detail5 = ' Type:'
            if detail3[1] == '0':
                detail5 = detail5 + 'File ID'
            else:
                detail5 = detail5 + 'Remote Path'
            the_result = 'GD Trash' + google_account + detail1 + detail4 + detail5 + ', File ID: ' + detail2 + lbl
        case '326':
            the_arguments = ['arg1', 'arg4', 'arg5', 'arg6']
            the_names = ['', ', Remote Folder:', ' Remote File Name:', ' Local Path:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail2, lbl = get_action_detail(3, code_action, type_action)
            if detail2 == '0':
                detail2 = 'File ID'
            else:
                detail2 = 'Remote Path'
            the_result = 'GD Download' + google_account + the_str_values[0] + detail2 + ' ' + the_str_values[1] + \
                         the_str_values[2] + the_str_values[3] + lbl
        case '327':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail3 == '1':
                detail3 = ', Full Access '
            the_result = 'GD Sign In' + google_account + detail1 + detail3 + lbl
        case '328':
            the_result = 'Keyboard ' + get_action_detail(0, code_action, type_action)
        case '329':
            the_arguments = ['arg0', 'arg1', 'arg2']
            the_names = [' Left:', ' Center:', ' Right:']
            the_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Navigation Bar ' + the_values[0] + the_values[1] + the_values[2] + get_action_detail(0,
                                                                                                               code_action,
                                                                                                               type_action)
        case '330':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'NFC Tag&nbsp;&nbsp;Payload to Write:' + detail1 + ', Payload Type:' + detail2 + lbl
        case '331':
            the_result = 'Auto-Sync set to ' + get_action_detail(7, code_action, type_action)
        case '333':
            the_result = 'Airplane Mode ' + get_action_detail(7, code_action, type_action)
        case '334':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Save WaveNet ' + detail1 + ' Voice: ' + detail2 + lbl
        case '335':
            the_result = 'App Info' + get_action_detail(0, code_action, type_action)
        case '337':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Notification Settings&nbsp;&nbsp;Package:' + detail1 + ', Category:' + detail2 + lbl
        case '338':
            the_result = 'Notification Category Info Settings&nbsp;&nbsp;Category:' + get_action_detail(1, code_action,
                                                                                                        type_action)
        case '339':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_arguments = ['arg2', 'arg3', 'arg4', 'arg5', 'arg6', 'arg7']
            the_names = [' URL:', ' Headers:', ' Query Parameters:', ' Body:', ' File To Send:', ' File/Dir To Save:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'HTTP Request&nbsp;&nbsp;Method:' + lookup_values['339'][int(detail1)] + the_str_values[0] + \
                         the_str_values[1] + the_str_values[2] + the_str_values[3] + the_str_values[4] + the_str_values[
                             5] + lbl
        case '340':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get Int
            if detail1:
                detail3 = 'Action:' + lookup_values['340'][int(detail1)]
            the_result = 'Bluetooth Connection&nbsp;&nbsp;' + detail3 + \
                         ', for device ' + get_action_detail(1, code_action, type_action)
        case '341':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get int
            detail2, lbl = get_action_detail(4, code_action, type_action)  # Get all Strs
            the_result = 'Test Net' + type_array + lookup_values['341'][int(detail1)] + ', Store Result In:' + detail2[
                0] + lbl
        case '342':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Test File with data ' + detail1 + ' store in ' + detail2 + lbl
        case '343':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Test Media  Type:' + lookup_values['343'][
                int(detail3)] + ', Data:' + detail1 + ', Store Results In:' + detail2 + lbl
        case '344':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Test App ' + detail1 + ' store in ' + detail2 + lbl
        case '345':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Test Variable&nbsp;&nbsp;Data:' + detail1 + ', Store Result In:' + detail2 + lbl
        case '346':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Test Phone' + type_array + lookup_values['346'][int(detail3)] + ', Data:' + detail1 + \
                         ', Store Result In:' + detail2 + lbl
        case '347':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            detail3 = int(detail3)
            detail2 = lookup_values['347'][detail3]
            if detail3 < 5:
                detail2 = detail2 + ' Available'
            the_result = 'Test Tasker' + type_array + detail2 + ', Store Results in:' + detail1 + lbl
        case '348':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            detail3 = lookup_values['348'][int(detail1[0])]
            the_result = 'Test Display ' + detail3 + ' ' + detail2
        case '349':
            ddetail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail3 == '0':
                detail3 = 'Android ID'
            else:
                detail3 = 'User ID'
            the_result = 'Test System' + type_array + detail3 + ', Store Results In:' + detail1 + lbl
        case '351':
            the_result = 'HTTP Auth' + get_action_detail(0, code_action, type_action)
        case '354':
            the_arguments = ['arg0', 'arg1', 'arg2']
            the_names = ['', ' Values:', ' Splitter:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Array Set' + variable_array + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         get_action_detail(0, code_action, type_action)
        case '355':
            detail1, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints (only two needed)
            if len(detail1) > 1 and detail1[1] == '1':
                detail4 = ', Fill Spaces'
            detail2, detail3, lbl = get_action_detail(2, code_action, type_action)  # Get two STRs
            the_result = 'Array Push' + variable_array + detail2 + ', Position:' + detail1[
                0] + ', Values:' + detail3 + detail4 + lbl
        case '356':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail2 != '':
                detail2 = ', To Var:' + detail2
            if detail3 != '':
                detail3 = ', Position:' + detail3
            the_result = 'Array Pop' + variable_array + detail1 + detail3 + detail2 + lbl
        case '357':
            the_result = ' Array Clear' + variable_array + get_action_detail(1, code_action, type_action)
        case '358':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get int
            the_result = 'Bluetooth Info ' + lookup_values['358'][int(detail1)] + lbl
        case '360':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Input Dialog' + type_array + list_to_string(detail1) + ' ' + lbl
        case '361':
            the_result = 'Dark Mode ' + get_action_detail(7, code_action, type_action)
        case '362':
            the_result = 'Set Assistant&nbsp;&nbsp;Assistant:' + get_action_detail(1, code_action, type_action)
        case '363':
            detail1 = get_action_detail(1, code_action, type_action)  # Get Str
            detail2, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            the_result = 'Mobile Network Type ' + lookup_values['363'][int(detail2)] + ', SIM Card:' + detail1 + lbl
        case '364':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Input Dialog&nbsp;&nbsp;Minutes Difference:' + detail1 + lbl
        case '365':
            the_result = 'Tasker Function ' + get_action_detail(1, code_action, type_action)
        case '366':
            the_arguments = ['arg2', 'arg3', 'arg4', 'arg5', 'arg8']  # Min Acc, Speed, Altitude, Near Loc, Min Speed
            the_names = [' Min Accuracy:', ' Speed:', ' Altitude:', ' Near Loc:', ' Min Speed Accuracy:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg6', 'arg7', 'arg9']  # Timeout, Enable Loc, Last Loc, Force Accuracy
            the_names = ['Timeout (SECONDS):', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Get Location V2&nbsp;&nbsp;' + the_int_values[0] + the_str_values[0] + \
                         the_str_values[1] + the_str_values[2] + the_str_values[3] + ', Enable Location:' + \
                         no_yes[int(the_int_values[1])] + ', Last Location if Timeout:' + no_yes[
                             int(the_int_values[2])] + \
                         the_str_values[4] + ', Force Accuracy:' + no_yes[int(the_int_values[3])] + \
                         get_action_detail(0, code_action, type_action)
        case '367':
            the_result = 'Camera ' + get_action_detail(7, code_action, type_action)
        case '368':
            the_arguments = ['arg1', 'arg3']  # Title, Init Location
            the_names = [' Title:', ' Initial Location:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg2', 'arg4']  # Select Radius, Type
            the_names = ['', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Pick Location ' + the_str_values[0] + ', Select Radius:' + no_yes[int(the_int_values[0])] + \
                         ', ' + the_str_values[1] + ' Type:' + lookup_values['368'][int(the_int_values[1])] + \
                         get_action_detail(0, code_action, type_action)
        case '369':
            ddetail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Array Process' + variable_array + detail1 + ', Type:' + lookup_values['369'][
                int(detail3)] + lbl
        case '370':
            the_result = 'Shortcut ' + get_action_detail(1, code_action, type_action)
        case '372':
            the_result = 'Sensor Info' + type_array + get_action_detail(1, code_action, type_action)
        case '373':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)  # Get two Strs (only need first)
            detail3, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints as a list
            if len(detail3) > 1 and detail3[1] == '1':
                detail2 = ', Convert Orientation'
            the_result = 'Test Sensor&nbsp;&nbsp;Type' + detail1 + ', Timeout (Seconds):' + detail3[0] + detail2 + lbl
        case '374':
            the_result = 'Screen Capture'
        case '375':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg6']
            the_names = [' Command:', ' Host:', ' Port:', ' Result Encoding:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg4', 'arg5']
            the_names = ['Timeout (SECONDS):', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[1] == '1':
                detail1 = ', Enable Debugging, '
            the_result = 'ADB Wifi ' + the_str_values[0] + the_str_values[1] + the_str_values[2] + the_int_values[0] + \
                         detail1 + the_str_values[3] + get_action_detail(0, code_action, type_action)
        case '376':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Test Sensor file ' + detail1 + ' mime type ' + detail2 + lbl
        case '377':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg8', 'arg9']
            the_names = [' Title:', ' Text:', ' Button 1:', ' Button 2:', ' Button 3:', ' Image:', ' Max W/H:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg6', 'arg7']
            the_names = [' Close After (seconds):', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Text/Image Dialog ' + the_str_values[0] + the_str_values[1] + the_str_values[2] + \
                         the_str_values[
                             3] + \
                         the_str_values[4] + the_int_values[0] + the_int_values[1] + the_str_values[5] + ', Use HTML:' + \
                         no_yes[int(the_int_values[1])] + the_str_values[6] + get_action_detail(0, code_action,
                                                                                                type_action)
        case '378':
            the_result = 'List Dialog ' + get_action_detail(1, code_action, type_action)
        case '381':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            if detail1 != '':
                detail1 = 'Contact:' + detail1 + ', App:'
            the_result = 'Contact Via App&nbsp;&nbsp;' + detail1 + detail2 + lbl
        case '383':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            the_result = 'Settings Panel' + type_array + lookup_values['383'][int(detail1)] + lbl
        case '384':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            detail2, lbl = get_action_detail(8, code_action, type_action)
            if detail2[0] == '0':
                detail3 = 'Add/Edit'
            else:
                detail3 = 'Delete'
            if len(detail2) > 1:
                detail3 = lookup_values['384'][int(detail2[1])]
            the_result = 'Device Control (Power Menu Action) action:' + detail3 + ' type:' + detail3 + ' ' + \
                         list_to_string(detail1) + lbl
        case '385':
            the_result = 'Command&nbsp;&nbsp;' + get_action_detail(1, code_action, type_action)
        case '386':
            the_arguments = ['arg1', 'arg2', 'arg4', 'arg5']
            the_names = ['', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[0] == '0':
                detail1 = 'Disallow'
            else:
                detail1 = 'Allow'
            if the_int_values[1] == '1':
                detail1 = detail1 + ', Reject'
            if the_int_values[2] == '1':
                detail1 = detail1 + ', Skip Call Log'
            if the_int_values[3] == '1':
                detail1 = detail1 + ', Skip Notification'
            the_result = 'Call Screening&nbsp;&nbsp;Disallow/Allow:' + detail1 + get_action_detail(0, code_action,
                                                                                                   type_action)
        case '387':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                the_result = 'Accessibility Volume to ' + detail1 + lbl
        case '389':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4']
            the_names = [' Names:', ' Variable Names Splitter:', ' Values:', ' Value Splitter:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg5', 'arg6', 'arg7', 'arg8']
            the_names = ['', ' Max Rounding Digits:', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[0] == '1':
                detail1 = ', Do Maths'
            if the_int_values[2] == '1':
                detail2 = ', Keep Existing'
            if the_int_values[3] == '1':
                detail3 = ', Structure Output (JSON, etc)'
            the_result = 'Multiple Variables Set&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + \
                         the_str_values[2] + the_str_values[3] + detail1 + the_int_values[1] + detail2 + detail3 + \
                         get_action_detail(0, code_action, type_action)
        case '390':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Pick Input Dialog ' + detail1 + ' with structure type ' + detail2 + lbl
        case '391':
            the_arguments = ['arg2', 'arg3', 'arg5', 'arg6']  # Get specific Strs
            the_names = [' Title:', ' Text:', ' Animation Images:', ' Animation Tint:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg4', 'arg7', 'arg10']  # Get specific Ints
            the_names = [[' Action:', '0', 'Show/Update', '1', ' Dismiss'],
                         [' Type:', '0', 'Animation', '1', 'Progress Bar'],
                         ' Frame Duration:', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Progress Dialog ' + the_int_values[0] + the_str_values[0] + the_str_values[1] + \
                         the_int_values[2] + \
                         the_str_values[2] + the_str_values[3] + the_int_values[3] + ', Use HTML:' + no_yes[
                             int(the_int_values[1])] + \
                         get_action_detail(0, code_action, type_action)
        case '392':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Set Variable Structure' + name_array + detail1 + ', Structure Type:' + detail2 + lbl
        case '393':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            the_arguments = ['arg1', 'arg4', 'arg5', 'arg6']
            the_names = [' Names:', ' Format:', ' Output:', ' Join Output:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            if detail1 == '0':
                detail1 = 'Simple'
            else:
                detail1 = 'Format'
            the_result = 'Array Merge&nbsp;&nbsp;' + the_str_values[0] + ' Merge Type:' + detail1 + the_str_values[1] + \
                         the_str_values[2] + the_str_values[3] + lbl
        case '394':
            the_arguments = ['arg11', 'arg2', 'arg5', 'arg7']
            the_names = [' Output Offset:', ' Input:', '', '']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            if the_str_values[2]:
                detail1 = ' Output Format:' + the_str_values[2]
            if the_str_values[3]:
                detail2 = ' Formatted Variable Names:' + the_str_values[3]
            the_arguments = ['arg1', 'arg10', 'arg8', 'arg9']
            the_names = ['', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[2]:
                detail3 = ', Get All Details'
            if the_int_values[3]:
                detail4 = ', Do Maths'
            the_result = 'Parse/Format DateTime&nbsp;&nbsp;Input Type:' + lookup_values['394'][int(the_int_values[0])] + \
                         the_str_values[1] + detail1 + detail2 + detail3 + detail4 + ', Output Offset Type:' + \
                         lookup_values['394a'][int(the_int_values[1])] + get_action_detail(0, code_action, type_action)
        case '396':
            the_arguments = ['arg2', 'arg3', 'arg4']
            the_names = [' Text:', '', '']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            if the_str_values[1]:
                detail1 = ' Regex:' + the_str_values[1]
            if the_str_values[2]:
                detail2 = ' Match Pattern:' + the_str_values[2]
            detail3, lbl = get_action_detail(3, code_action, type_action)
            if detail3 == '0':
                detail3 = 'Simple'
            else:
                detail3 = 'Regex'
            the_result = 'Simple Match/Regex' + type_array + detail3 + the_str_values[0] + detail1 + detail2 + lbl
        case '397':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get int
            if detail1 == '1':
                detail1 = '&nbsp;&nbsp;Output Hashtags'
            the_result = 'Get Material You Colors' + detail1 + lbl
        case '398':
            the_result = 'Connect to WiFi with SSID:' + get_action_detail(1, code_action, type_action)
        case '399':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg9']
            the_names = [' Input:', ' Input Minimum:', ' Input Maximum:', ' Output Minimum:', ' Output Maximum:', '']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail1, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints
            if detail1[0]:
                detail2 = ', Invert'
            if detail1[1]:
                detail3 = ', Restrict Range'
            if the_str_values[5]:
                detail4 = ', Output Variable Name:' + the_str_values[5]
            the_result = 'Variable Map ' + the_str_values[0] + the_str_values[1] + the_str_values[2] + the_str_values[
                3] + \
                         the_str_values[4] + detail2 + detail3 + ', Max Rounding Digits:' + detail1[2] + detail4 + lbl
        case '400':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Move (file) from ' + detail1 + ' to ' + detail2 + lbl
        case '402':
            the_result = 'Get Clipboard' + get_action_detail(0, code_action, type_action)
        case '404':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Copy File ' + detail1 + ' to ' + detail2 + lbl
        case '405':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Copy Dir ' + detail1 + ' to ' + detail2 + lbl
        case '406':
            the_result = 'Delete File ' + get_action_detail(1, code_action, type_action)
        case '407':
            the_arguments = ['arg1', 'arg2']
            the_names = [' Max Number:', ' Mime Type:']
            the_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail1, detail2 = get_action_detail(3, code_action, type_action)
            if detail1 == '1':
                detail1 = ' (Copy To Cache) '
            the_result = 'Pick Photos ' + the_values[0] + the_values[1] + detail1 + detail2
        case '408':
            the_result = 'Delete Directory directory: ' + get_action_detail(1, code_action, type_action)
        case '409':
            the_result = 'Create Directory ' + get_action_detail(1, code_action, type_action)
        case '410':
            the_result = 'Write File ' + get_action_detail(1, code_action, type_action)
        case '412':
            the_result = 'List Files directory ' + get_action_detail(1, code_action, type_action)
        case '414':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Get Pixel Colors image:' + detail1 + ' pixel coordinates:' + detail2 + lbl
        case '415':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Read Line from file ' + list_to_string(detail1) + ' ' + lbl
        case '416':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Read Paragraph from file ' + list_to_string(detail1) + ' ' + lbl
        case '417':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Read File ' + detail1 + ' into ' + detail2 + lbl
        case '420':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail3 == '1':
                detail3 = ' (Delete Orig checked) '
            the_result = 'Zip file ' + detail1 + ' into ' + detail2 + detail3 + lbl
        case '421':
            the_result = 'Get Screen Info (assistant)' + get_action_detail(0, code_action, type_action)
        case '422':
            detail1, detail2, lbl = get_action_detail(9, code_action, type_action)
            if detail2 == '1':
                detail2 = ' (Delete Zip checked) '
            the_result = 'UnZip file ' + detail1 + detail2 + lbl
        case '424':
            the_result = 'Get Battery Info' + get_action_detail(0, code_action, type_action)
        case '425':
            the_result = 'Turn Wifi ' + get_action_detail(7, code_action, type_action)
        case '426':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            the_arguments = ['arg1', 'arg2']
            the_names = [', Force:', ', Report Failures:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Wifi Net&nbsp;&nbsp;Action:' + lookup_values['426'][int(detail1)] + the_int_values[0] + \
                         the_int_values[1] + lbl
        case '427':
            detail1, lbl = get_action_detail(3, code_action, type_action)  # Get Int
            the_result = 'Wifi Sleep&nbsp;&nbsp;Policy:' + lookup_values['427'][int(detail1)] + lbl
        case '430':
            the_result = 'Restart Tasker' + get_action_detail(0, code_action, type_action)
        case '431':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Accessibility Services&nbsp;&nbsp;Action:' + lookup_values['431'][
                int(detail1)] + ', Services:' + \
                         get_action_detail(1, code_action, type_action)
        case '433':
            the_result = 'Mobile Data set to ' + get_action_detail(7, code_action, type_action)
        case '443':
            app_detail, lbl = get_action_detail(5, code_action, type_action)  # Get application name
            the_arguments = ['arg0', 'arg1', 'arg3']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Media Control&nbsp;&nbsp;Cmd:' + lookup_values['443'][
                int(the_int_values[0])] + ', Simulated Media Button:' + \
                         no_yes[int(the_int_values[1])] + ', Use Notification If Available:' + no_yes[
                             int(the_int_values[2])] + \
                         ', Package:' + app_detail + ' with app name:' + lbl
        case '445':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Music Play&nbsp;&nbsp;Start:' + the_int_values[0] + ', Loop:' + no_yes[
                int(the_int_values[1])] + \
                         ', Stream:' + lookup_values['192a'][int(the_int_values[2])] + ', Continue Task Immediately:' + \
                         no_yes[int(the_int_values[3])] + \
                         ', File:' + get_action_detail(1, code_action, type_action)  # 192a = media_type
        case '447':
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4', 'arg5']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', '', '', '', ', Maximum Tracks:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Music Play Dir&nbsp;&nbsp;Subdirs:' + no_yes[int(the_int_values[0])] + ', Audio Only:' + \
                         no_yes[
                             int(the_int_values[1])] + \
                         ', Random:' + no_yes[int(the_int_values[2])] + ', Flash:' + no_yes[int(the_int_values[3])] + \
                         ', ' + the_int_values[4] + ', Directory:' + get_action_detail(1, code_action, type_action)
        case '449':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Music Stop&nbsp;&nbsp;Clear Dir:' + no_yes[int(detail1)] + lbl
        case '451':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Music Skip  Jump: ' + detail1 + lbl
        case '453':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Music Back&nbsp;&nbsp;Jump: ' + detail1 + lbl
        case '455':
            the_arguments = ['arg1', 'arg2', 'arg3']  # Int: Command, Simulate Button, Use Notification
            the_names = ['', ', MaxSize:', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Record Audio&nbsp;&nbsp;Source:' + lookup_values[task_code + 'a'][int(the_int_values[0])] + \
                         the_int_values[1] + \
                         ', Format:' + lookup_values[task_code][int(the_int_values[2])] + \
                         ', File:' + get_action_detail(1, code_action, type_action)
        case '457':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 != '':
                the_result = 'Force Rotation ' + detail1 + lbl
        case '459':
            the_result = 'Scan Media&nbsp;&nbsp;File:' + get_action_detail(1, code_action, type_action)
        case '461':
            detail1, detail2 = get_action_detail(5, code_action, False)
            if detail2 == '':
                the_result = 'Notification'
            else:
                the_result = 'Notification for app ' + detail2
        case '475':
            detail1, detail2, lbl = get_action_detail(9, code_action, type_action)
            if detail2 == '1':
                detail2 = ' (Delete Orig checked) '
            the_result = 'GZip file ' + detail1 + detail2 + lbl
        case '476':
            detail1, detail2, lbl = get_action_detail(9, code_action, type_action)
            if detail2 == '1':
                detail2 = ' (Delete Zip checked) '
            the_result = 'GUnzip file ' + detail1 + detail2 + lbl
        case '490':
            the_arguments = ['arg0', 'arg1']  # Int: Action, Use New API
            the_names = [[' Action:', '0', 'Grab', '1', 'Release'],
                         [' Use New API:', '0', 'No', '1', 'Yes']]
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Media Button Events ' + the_int_values[0] + the_int_values[1] + \
                         get_action_detail(0, code_action, type_action)
        case '511':
            the_result = 'Torch' + get_action_detail(0, code_action, type_action)
        case '512':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 == '0':
                detail2 = 'Expanded'
            else:
                detail2 = 'Collapsed'
            the_result = 'Status Bar' + detail2 + lbl
        case '513':
            the_result = 'Close System Dialogs' + get_action_detail(0, code_action, type_action)
        case '523':
            detail1, detail2, lbl = get_action_detail(10, code_action, type_action)
            if detail1:
                detail1 = ', Icon:' + detail2
                detail2 = ', Package:' + detail2
            the_arguments = ['arg0', 'arg1', 'arg10', 'arg11', 'arg9']
            the_names = ['', '  Text:', ', Vibrate:', ' Category:', ', Sound File:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg4', 'arg5', 'arg6', 'arg7', 'arg8']
            the_names = ['', '', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[0] == '1':
                detail3 = ', Permanent'
            if the_int_values[1]:
                detail4 = ', Priority:' + the_int_values[1]
            if the_int_values[2] == '1':
                detail5 = ', Repeat Alert'
            if the_int_values[3]:
                detail6 = ', LED Color:' + lookup_values['523'][int(the_int_values[3])]
            if the_int_values[4]:
                detail7 = ', LED Rate:' + the_int_values[4]
            else:
                detail7 = ''
            the_result = 'Notify&nbsp;&nbsp;Title:' + the_str_values[0] + the_str_values[
                1] + detail1 + detail2 + detail3 + \
                         detail4 + detail5 + detail6 + detail7 + the_str_values[4] + the_str_values[2] + the_str_values[
                             3] + lbl
        case '525':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Notify LED title:' + detail1 + ' text:' + detail2 + lbl
        case '536':
            the_result = 'Notification Vibrate with title ' + get_action_detail(1, code_action, type_action)
        case '538':
            the_result = 'Notification Sound with title ' + get_action_detail(1, code_action, type_action)
        case '550':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Popup title ' + detail1 + ' with message: ' + detail2 + lbl
        case '552':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Popup Task Buttons ' + list_to_string(detail1) + ' ' + lbl
        case '543':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)  # Get two Strs (only need first)
            detail3, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints as a list
            if len(detail3) > 1 and detail3[1] == '1':
                detail4 = ', Show UI'
            the_result = 'Start System Timer&nbsp;&nbsp;Seconds:' + detail3[0] + ', Message:' + detail1 + detail4 + lbl
        case '544':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Timer Widget Control' + name_array + detail1 + ', Type:' + lookup_values['544'][
                int(detail3)] + lbl
        case '545':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            detail3, lbl = get_action_detail(8, code_action, type_action)
            the_result = 'Variable Randomize' + name_array + detail1 + ', Min:' + detail3[0] + ', Max:' + detail3[
                1] + lbl
        case '546':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_arguments = ['arg1', 'arg2', 'arg3', 'arg4']
            the_names = [' Seconds:', ' Minutes:', ' Hours:', ' Days:']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Timer Widget Set' + name_array + detail1 + the_int_values[0] + the_int_values[1] + \
                         the_int_values[
                             2] + \
                         the_int_values[3] + lbl
        case '547':
            detail7 = ''
            if type_action:
                the_arguments = ['arg2', 'arg3', 'arg4', 'arg5', 'arg6']
                the_names = ['', '', '', ' Max Rounding Digits:', '']
                the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
                if the_int_values[0]:
                    detail3 = ', Recurse Variables'
                if the_int_values[1]:
                    detail4 = ', Do Maths'
                if the_int_values[2]:
                    detail5 = ', Append'
                if the_int_values[4]:
                    detail6 = ', Structure Output (JSON etc)'
                if the_int_values[3]:
                    detail7 = the_int_values[3]
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Variable Set' + name_array + detail1 + ', To:' + detail2 + detail3 + detail4 + detail5 + \
                         detail7 + detail6 + lbl
        case '548':
            the_arguments = ['arg0', 'arg10', 'arg13', 'arg3', 'arg4', 'arg5', 'arg6', 'arg7', 'arg8']
            the_names = ['', ' Text Color:', ' Position:', ' Title:', ' Icon:', ' Icon Size:', ' Background Color:',
                         'Task:', ' Timeout:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg11', 'arg12', 'arg14', 'arg2', 'arg9']
            the_names = ['', '', '', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            detail1 = 0
            detail2 = ['', '', '', '', '', '']
            trigger = [' Long,', ' Dismiss On Click,', ' Show Over Everything,', ' Use HTML,', ' Tasker Layout,',
                       ' Continue Task Immediately,']
            for item in the_int_values:
                if item == '1':
                    detail2[detail1] = trigger[detail1]
                    detail3 = '1'
                else:
                    detail2[detail1] = ''
                detail1 += 1
            if detail3:
                detail3 = ', '
            the_result = 'Flash&nbsp;&nbsp;Text:' + the_str_values[0] + detail3 + detail2[0] + detail2[1] + \
                         the_str_values[1] + the_str_values[2] + the_str_values[3] + the_str_values[4] + detail2[5] + \
                         the_str_values[6] + the_str_values[7] + the_str_values[8] + detail2[2] + detail2[3] + \
                         detail2[4] + detail2[5] + get_action_detail(0, code_action, type_action)
        case '549':
            detail1, lbl = get_action_detail(8, code_action, type_action)
            if detail1[0]:
                detail2 = ', Pattern Matching'
            if detail1[1]:
                detail3 = ', Local Variables Only'
            if detail1[2]:
                detail4 = ', Check All Variables'
            detail5, detail6, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Variable Clear' + name_array + detail5 + detail2 + detail3 + detail4 + lbl
        case '550':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Popup ' + detail1 + ' ' + detail2 + lbl
        case '551':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Menu with fields: ' + list_to_string(detail1) + lbl
        case '559':
            the_result = 'Say ' + get_action_detail(1, code_action, type_action)
        case '566':
            the_arguments = ['arg2', 'arg3']
            the_names = [' Label:', ' Sound:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg0', 'arg1', 'arg4', 'arg5']
            the_names = [' Hours:', ' Minutes:', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[3] == '1':
                detail1 = ', Confirm'
            the_result = 'Set Alarm&nbsp;&nbsp;' + the_int_values[0] + the_int_values[1] + the_str_values[0] + \
                         the_str_values[1] + ' Vibrate:' + lookup_values['566'][int(the_int_values[2])] + detail1 + \
                         get_action_detail(0, code_action, type_action)
        case '567':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)  # Get two Strs
            the_result = 'Calendar Insert ' + detail1 + ' with description: ' + detail2 + lbl
        case '590':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            if detail2:
                detail2 = ', Splitter:' + detail2
            detail3, lbl = get_action_detail(8, code_action, type_action)  # Get all Ints
            if detail3[0] == '1':
                detail4 = ', Delete Base'
            if detail3[1] == '1':
                detail5 = ', Regex'
            the_result = 'Variable Split' + name_array + detail2 + detail4 + detail5 + lbl
        case '592':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail2:
                detail2 = ', Joiner:' + detail2
            if detail3:
                detail3 = ', Delete Parts'
            the_result = 'Variable Join' + name_array + detail1 + detail2 + detail3 + lbl
        case '595':
            the_arguments = ['arg0', 'arg1', 'arg3', 'arg4', 'arg5']
            the_names = ['', ' Variable:', '', '', '']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg2', 'arg6', 'arg7']
            the_names = ['', ', Timeout (Seconds):', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[2]:
                detail1 = ', Show Over Keyguard'
            if the_str_values[0]:
                detail2 = 'Title:' + the_str_values[0]
            if the_str_values[2]:
                detail3 = ', Default:' + the_str_values[2]
            if the_str_values[3]:
                detail4 = ' Background Image:' + the_str_values[3]
            if the_str_values[4]:
                detail5 = ' Layout:' + the_str_values[4]
            the_result = 'Variable Query&nbsp;&nbsp;' + detail2 + the_str_values[1] + ', Input Type:' + \
                         lookup_values['595'][int(the_int_values[0])] + detail3 + detail4 + detail5 + the_int_values[
                             1] + \
                         detail1 + get_action_detail(0, code_action, type_action)
        case '596':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail2:
                detail2 = ', Store Results In:' + detail2
            the_result = 'Variable Convert ' + detail1 + ', Function:' + lookup_values['596'][
                int(detail3)] + detail2 + lbl
        case '597':
            the_arguments = ['arg1', 'arg2', 'arg3']
            the_names = [' From:', ', Length:', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[2]:
                detail1 = ', Adapt To Fit'
            detail2, detail3, lbl = get_action_detail(2, code_action, type_action)
            if detail3:
                detail3 = ', Store Results In:' + detail3
            the_result = 'Variable Section' + name_array + detail2 + ', ' + the_int_values[0] + the_int_values[
                1] + detail1 + \
                         detail3 + lbl
        case '598':
            the_arguments = ['arg0', 'arg1', 'arg5', 'arg7']
            the_names = ['', ' Search:', '', '']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            if the_str_values[2]:
                detail4 = ', Stop Matches In Array:' + the_str_values[2]
            if the_str_values[3]:
                detail6 = ', Replace With:' + the_str_values[3]
            the_arguments = ['arg2', 'arg3', 'arg4', 'arg6']
            the_names = ['Timeout (SECONDS):', '', '', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[0]:
                detail1 = ' Ignore Case'
            if the_int_values[1]:
                detail2 = ', Multi-Line'
            if the_int_values[2]:
                detail3 = ', One Match Only'
            if the_int_values[3]:
                detail5 = ', Replace Matches'
            the_result = 'Variable Search Replace' + variable_array + the_str_values[0] + the_str_values[1] + detail1 + \
                         detail2 + detail3 + detail4 + detail5 + detail6 + get_action_detail(0, code_action,
                                                                                             type_action)
        case '612':
            the_arguments = ['arg0', 'arg1', 'arg3']
            the_names = [' Scene Name:', ' Element:', ' MilliSeconds:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            detail3, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Element Video Control&nbsp;&nbsp;' + the_str_values[0] + the_str_values[1] + \
                         lookup_values['612'][int(detail3)] + the_str_values[2] + lbl
        case '664':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Java Function return object ' + detail1 + ' , ' + detail2 + lbl
        case '665':
            the_result = 'Java Object ' + get_action_detail(1, code_action, type_action)
        case '667':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'SQL Query ' + detail1 + ' to ' + detail2 + lbl
        case '697':
            the_result = 'Shut Up' + get_action_detail(0, code_action, type_action)
        case '669':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Say To File ' + list_to_string(detail1) + ' ' + lbl
        case '721':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail3:
                detail3 = ', Set'
            the_result = 'Zoom Visibility' + element_array + detail1 + detail3 + lbl
        case '731':
            the_result = 'Take Call' + get_action_detail(0, code_action, type_action)
        case '733':
            the_result = 'End Call' + get_action_detail(0, code_action, type_action)
        case '740':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Zoom Text' + element_array + detail1 + ', Text:' + detail2 + lbl
        case '741':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Zoom Text Size' + element_array + detail1 + ', Text Size:' + detail3 + lbl
        case '742':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Zoom Text Color' + element_array + detail1 + ', Text:' + detail2 + lbl
        case '760':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Zoom Alpha' + element_array + detail1 + ', Set:' + detail3 + lbl
        case '761':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Zoom Image' + element_array + detail1 + ', URL:' + detail2 + lbl
        case '762':
            detail1, lbl = get_action_detail(4, code_action, type_action)
            the_result = 'Zoom Color' + element_array + detail1[0] + ', Color:' + detail1[1] + ', End Color:' + detail1[
                2] + lbl
        case '775':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Write Binary ' + detail1 + ' file: ' + detail2 + lbl
        case '776':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Write Binary file ' + detail1 + ' to Var: ' + detail2 + lbl
        case '779':
            the_result = 'Notify Cancel ' + get_action_detail(1, code_action, type_action)
        case '793':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            the_result = 'Zoom State' + element_array + detail1 + ', State:' + detail3[0] + lbl
        case '794':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            detail3, lbl = get_action_detail(8, code_action, type_action)
            the_result = 'Zoom Position' + element_array + detail1 + ', Orientation:' + orientation_type[
                int(detail3[0])] + \
                         ', X:' + detail3[1] + ', Y:' + detail3[2] + lbl
        case '795':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            detail3, lbl = get_action_detail(8, code_action, type_action)
            the_result = 'Zoom Size' + element_array + detail1 + ', Orientation:' + orientation_type[int(detail3[0])] + \
                         ', Width:' + detail3[1] + ', Height:' + detail3[2] + lbl
        case '806':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Notify Cancel ' + detail1 + lbl
        case '808':
            the_result = 'Auto Brightness ' + get_action_detail(7, code_action, type_action)
        case '810':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Display Brightness to ' + detail1 + lbl
        case '812':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Display Timeout ' + detail1 + lbl
        case '815':
            the_result = 'List Apps into ' + get_action_detail(1, code_action, type_action)
        case '820':
            detail1, detail2 = get_action_detail(3, code_action, type_action)  # Get int
            the_result = 'Stay On ' + lookup_values['820'][int(detail1)] + detail2
        case '822':
            the_result = 'Display Autorotate set to ' + get_action_detail(7, code_action, type_action)
        case '877':
            the_result = 'Send Intent&nbsp;&nbsp;Action:' + get_action_detail(1, code_action, type_action)
        case '888':
            detail1, lbl = get_action_detail(8, code_action, type_action)
            detail2, detail3, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'Variable Add' + name_array + detail2 + ', Value:' + detail1[0] + ', Wrap Around:' + detail1[
                1] + lbl
        case '890':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            detail3, lbl = get_action_detail(8, code_action, type_action)
            if detail3[1]:
                detail4 = ', Wrap Around:' + detail3[1]
            the_result = 'Variable Subtract' + name_array + detail1 + ', Value:' + detail3[0] + detail4 + lbl
        case '900':
            detail1, detail2, detail3, lbl = get_action_detail(11, code_action, type_action)
            if detail3 == '1':
                detail3 = 'Include Hidden Files'
            the_result = 'Browse Files directory ' + detail1 + detail3 + ' match:' + detail2 + lbl
        case '901':
            the_result = 'Stop Location ' + get_action_detail(0, code_action, type_action)
        case '902':
            the_arguments = ['arg0', 'arg1', 'arg2', 'arg3']  # Source, Timeout, Continue, Keep Tracking
            the_names = [[' Source:', '0', 'GPS', '1', 'Net', '2', 'Any'], 'Timeout (SECONDS):',
                         [' Continue Task Immediately:', '0', 'No', '1', 'Yes'],
                         [' Keep Tracking:', '0', 'No', '1', 'Yes']]
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            the_result = 'Get Location ' + the_int_values[0] + the_int_values[1] + the_int_values[3] + \
                         get_action_detail(0, code_action, type_action)
        case '903':
            the_arguments = ['arg0', 'arg2']
            the_names = [' Title:', ' Language:']
            the_str_values = get_xml_str_argument_to_value(code_action, the_arguments, the_names)
            the_arguments = ['arg1', 'arg3', 'arg4', 'arg5']
            the_names = ['', ' Maximum Results:', ' Timeout (Seconds):', '']
            the_int_values = get_xml_int_argument_to_value(code_action, the_arguments, the_names)
            if the_int_values[0] == '0':
                detail1 = 'Free Form'
            else:
                detail1 = 'Web Search'
            if the_int_values[3] == '1':
                detail2 = ', Hide Dialog'
            the_result = 'Get Voice&nbsp;&nbsp;' + the_str_values[0] + ', Language Model:' + detail1 + \
                         the_str_values[1] + the_int_values[1] + the_int_values[2] + detail2 + \
                         get_action_detail(0, code_action, type_action)
        case '904':
            the_result = 'Voice Command' + get_action_detail(0, code_action, type_action)
        case '905':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Location Mode set to ' + lookup_values['905'][int(detail1)] + lbl
        case '906':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Immersive Mode ' + lookup_values[task_code][int(detail1)] + lbl
        case '907':
            the_result = 'Status Bar Icons ' + get_action_detail(1, code_action, type_action)
        case '909':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            if detail1 == '0':
                detail1 = 'Starred'
            elif detail1 == '1':
                detail1 = 'Frequent'
            else:
                detail1 = 'Shared, Frequent'
            the_result = 'Contacts' + type_array + detail1 + lbl
        case '910':
            detail1, lbl = get_action_detail(3, code_action, type_action)
            the_result = 'Call Log&nbsp;&nbsp;Action:' + lookup_values['910'][int(detail1)] + lbl
        case '941':
            detail1, detail2, lbl = get_action_detail(2, code_action, type_action)
            the_result = 'HTML Pop code: ' + detail1 + ' Layout: ' + detail2 + lbl
        case '956':
            the_result = 'NFC Settings' + get_action_detail(0, code_action, type_action)
        case '957':
            the_result = 'Android Beam Settings' + get_action_detail(0, code_action, type_action)
        case '958':
            the_result = 'NFC Payment Settings' + get_action_detail(0, code_action, type_action)
        case '959':
            the_result = 'Dream Settings' + get_action_detail(0, code_action, type_action)
        case '987':
            the_result = 'Soft Keyboard' + get_action_detail(0, code_action, type_action)
        case '988':
            the_result = 'Car Mode ' + get_action_detail(7, code_action, type_action)
        case '989':
            detail1 = get_action_detail(7, code_action, type_action)
            if detail1 == 'Toggle':
                detail1 = 'Auto'
            the_result = 'Car Mode ' + detail1

        # Plugins start here
        case '117240295':
            the_result = 'AutoWear Input ' + get_action_detail(6, code_action, type_action)
        case '140618776':
            the_result = 'AutoWear Toast ' + get_action_detail(6, code_action, type_action)
        case '166160670':
            the_result = 'AutoNotification ' + get_action_detail(6, code_action, type_action)
        case '191971507':
            the_result = 'AutoWear ADB Wifi ' + get_action_detail(6, code_action, type_action)
        case '234244923':
            the_result = 'AutoInput Unlock Screen' + get_action_detail(0, code_action, type_action)
        case '268157305':
            the_result = 'AutoNotification Tiles ' + get_action_detail(6, code_action, type_action)
        case '319692633':
            the_result = 'AutoShare Process Text ' + get_action_detail(6, code_action, type_action)
        case '344636446':
            the_result = 'AutoVoice Trigger Alexa Routine ' + get_action_detail(6, code_action, type_action)
        case '557649458':
            the_result = 'AutoWear Time ' + get_action_detail(6, code_action, type_action)
        case '565385068':
            the_result = 'AutoWear Input ' + get_action_detail(6, code_action, type_action)
        case '774351906':
            the_result = ' ' + get_action_detail(6, code_action,
                                                 type_action)  # 'Join Action' captured in get_action_detail(6, ...
        case '778682267':
            the_result = 'AutoInput Gestures ' + get_action_detail(6, code_action, type_action)
        case '811079103':
            the_result = 'AutoInput Global Action ' + get_action_detail(6, code_action, type_action)
        case '864692752':
            the_result = 'Join ' + get_action_detail(6, code_action, type_action)
        case '906355163':
            the_result = 'AutoWear Voice Screen ' + get_action_detail(6, code_action, type_action)
        case '940160580':
            the_result = 'AutoShare ' + get_action_detail(6, code_action, type_action)
        case '1027911289':
            the_result = 'AutoVoice Set Cmd Id ' + get_action_detail(6, code_action, type_action)
        case '1099157652':
            the_result = 'AutoTools Json Write ' + get_action_detail(6, code_action, type_action)
        case '1040876951':
            the_result = 'AutoInput UI Query ' + get_action_detail(6, code_action, type_action)
        case '1150542767':
            the_result = 'Double Tap Plugin ' + get_action_detail(6, code_action, type_action)
        case '1165325195':
            the_result = 'AutoTools Web Screen ' + get_action_detail(6, code_action, type_action)
        case '1250249549':
            the_result = 'AutoInput Screen Off/On ' + get_action_detail(6, code_action, type_action)
        case '1246578872':
            the_result = 'AutoWear Notification ' + get_action_detail(6, code_action, type_action)
        case '1304982781':
            the_result = 'AutoTools Dialog ' + get_action_detail(6, code_action, type_action)
        case '1410790256':
            the_result = 'AutoWear Floating Icon ' + get_action_detail(6, code_action, type_action)
        case '1644316156':
            the_result = 'AutoNotification Reply ' + get_action_detail(6, code_action, type_action)
        case '1754437993':
            the_result = 'AutoVoice Recognize ' + get_action_detail(6, code_action, type_action)
        case '1830829821':
            the_result = 'AutoWear 4 Screen ' + get_action_detail(6, code_action, type_action)
        case '1957670352':
            the_result = 'AutoWear App ' + get_action_detail(6, code_action, type_action)
        case '1339942270':
            the_result = 'SharpTools Thing ' + get_action_detail(6, code_action, type_action)
        case '1452528931':
            the_result = 'AutoContacts Query 2.0 ' + get_action_detail(6, code_action, type_action)
        case '1620773086':
            the_result = 'SharpTools A Thing ' + get_action_detail(6, code_action, type_action)
        case '1447159672':
            the_result = 'AutoTools Text ' + get_action_detail(6, code_action, type_action)
        case '1508929357':
            the_result = 'AutoTools ' + get_action_detail(6, code_action, type_action)
        case '1563799945':
            the_result = 'Secure Settings ' + get_action_detail(6, code_action, type_action)
        case '1732635924':
            the_result = 'AutoInput Action ' + get_action_detail(6, code_action, type_action)
        case '1830656901':
            the_result = 'AutoWear List Screens ' + get_action_detail(6, code_action, type_action)
        case '1957681000':
            the_result = 'AutoInput Gesture ' + get_action_detail(6, code_action, type_action)
        case '2046367074':
            the_result = 'AutoNotification Cancel ' + get_action_detail(6, code_action, type_action)
        case _:
            if 1000 < int(task_code):
                the_result = 'Call to Plugin ' + get_action_detail(6, code_action, type_action)
            else:
                the_result = 'Code ' + task_code + ' not yet mapped'

    # Drop here when we have the result = the_result
    the_result = cleanup_the_result(the_result)
    return the_result


# #############################################################################################
# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
# #############################################################################################
def ulify(element, lvl=int):  # lvl=0=heading 1=start list 2=Task/Profile/Scene 3=end list 4=special Task
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
        if 'Project' == element[0:7]:  # Project ========================
            string = list_color + bullet_color + '" ><span style="color:' + project_color + '">' + element + '</span></li>\n'
        elif 'Profile' == element[0:7]:  # Profile ========================
            string = list_color + bullet_color + '" ><span style="color:' + profile_color + '">' + element + '</span></li>\n'
        elif element[0:5] == 'Task:' or '⎯Task:' in element:  # Task or Scene's Task ========================
            if unknown_task_name in element:
                string = list_color + bullet_color + '" ><span style="color:' + unknown_task_color + ';">' + font_to_use + \
                        element + '</span></li>\n'
            else:
                string = list_color + bullet_color + '" ><span style="color:' + task_color + '">' + font_to_use + \
                         element + '</span></li>\n'
        elif 'Scene:' == element[0:6]:  # Scene
            string = list_color + bullet_color + '" ><span style="color:' + scene_color + '">' + element + '</span></li>\n'
        elif 'Action:' in element:  # Action
            if 'Action: ...' in element:  # If this is continued from the previous line, indicate so and ensure proper font
                if '' == element[11:len(element)]:
                    string = ''
                    return string
                tmp = element.replace('Action: ...', 'Action continued >>> ')
                # tmp = strip_string(element).replace('Action: ...', 'Action continued >>> ')
                element = tmp
            string = list_color + bullet_color + '" ><span style="color:' + action_color + '">' + font_to_use + \
                     '></font></b>' + element + '</span></li>\n'
        elif 'Label for' in element:  # Action
            string = list_color + bullet_color + '" ><span style="color:' + action_color + '">' + element + '</span></li>\n'
        else:  # Must be additional item
            string = '<li>' + element + '</li>\n'
    # End List..............................
    elif lvl == 3:  # lvl=3 >>> End list
        string = '</ul>'
    return string


# #############################################################################################
# Write line of output
# #############################################################################################
def my_output(output_list, list_level, out_string):
    if 'Task ID:' in out_string and debug is False:  # Drop ID: nnn since we don't need it anymore
        temp_element = out_string.split('Task ID:')
        out_string = temp_element[0]
    output_list.append(ulify(out_string, list_level))
    if debug_out:
        print('out_string:', ulify(out_string, list_level))
    return


# #############################################################################################
# Construct Task Action output line
# #############################################################################################
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
                if count == continue_limit:  # Only display up to so many continued lines
                    alist.append('<font color=red> ... continue limit of ' + str(continue_limit) +
                                 ' reached.  See "continue_limit =" in code for details')
                    break
    # Unknown action...we have yet to identify it in our code.
    else:
        alist.append('Action ' + achild.text + ': not yet mapped')
    return


# #############################################################################################
# Shell sort for Action list (Actions are not necessarily in numeric order in XML backup file).
# #############################################################################################
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
                attr2 = arr[i + gap]
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


# #######################################################################################
# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
# #######################################################################################
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
            child = action.find('code')  # Get the <code> element
            task_code = getcode(child, action, True)
            logger.debug('Task ID:' + str(action.attrib['sr']) + ' Code:' + child.text + ' task_code:' +
                         task_code + 'Action attr:' + str(action.attrib))
            # Calculate the amount of indention required
            if 'End If' == task_code[0:6] or 'Else' == task_code[0:4] or 'End For' == task_code[
                                                                                      0:7]:  # Do we un-indent?
                indentation -= 1
                length_indent = len(indentation_amount)
                indentation_amount = indentation_amount[24:length_indent]
            build_action(tasklist, task_code, child, indentation, indentation_amount)
            if 'If' == task_code[0:2] or 'Else' == task_code[0:4] or 'For' == task_code[0:3]:  # Do we indent?
                indentation += 1
                indentation_amount = indentation_amount + '&nbsp;&nbsp;&nbsp;&nbsp;'
    return tasklist


# #######################################################################################
# Get the name of the task given the Task ID
# return the Task's element and the Task's name
# #######################################################################################
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


# #######################################################################################
# See if the xml tag is one of the predefined types and return result
# #######################################################################################
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


# #######################################################################################
# Process Task/Scene text/line item: call recursively for Tasks within Scenes
# #######################################################################################
def process_list(list_type, the_output, the_list, all_task_list, all_scene_list, the_task, tasks_found, display_detail_level):
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
            logger.debug(
                'def_process_list  the_item:' + the_item + ' the_list:' + str(the_list) + ' list_type:' + list_type)
        my_output(the_output, 2, list_type + '&nbsp;' + the_item)
        my_count += 1
        if temp_item:  # Put the_item back with the 'ID: nnn' portion included.
            the_item = temp_item
            list_type = temp_list

        # Output Actions for this Task if displaying detail and/or Task is unknown
        # Do we get the Task's Actions?
        if ('Task:' in list_type and unknown_task_name in the_item) or ('Task:' in list_type):
            # If Unknown task, then 'the_task' is not valid, and we have to find it.
            if unknown_task_name in the_item or display_detail_level > 0:
                if '⎯Task:' in list_type:  # -Task: = Scene rather than a Task
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
                            if action_count == 2 and display_detail_level == 0 and unknown_task_name in the_item:  # Just show first Task if unknown Task
                                break
                            elif display_detail_level == 1 and unknown_task_name not in the_item:
                                break
                    my_output(the_output, 3, '')  # Close Action list

        # Must be a Scene.  Look for all 'Tap' Tasks for Scene
        elif 'Scene:' == list_type and display_detail_level == 2:  # We have a Scene: get its actions
            have_a_scene_task = False
            for my_scene in the_list:  # Go through each Scene to find TAP and Long TAP Tasks
                getout = 0
                for scene in all_scene_list:
                    for child in scene:
                        if child.tag == 'nme' and child.text == my_scene:  # Is this our Scene?
                            for cchild in scene:  # Go through sub-elements in the Scene element
                                if tag_in_type(cchild.tag, True):
                                    for subchild in cchild:  # Go through ListElement sub-items
                                        if tag_in_type(subchild.tag,
                                                       False):  # Task associated with this Scene's element?
                                            my_output(the_output, 1, '')  # Start Scene's Task list
                                            have_a_scene_task = True
                                            temp_task_list = [subchild.text]
                                            task_element, name_of_task = get_task_name(subchild.text, all_task_list,
                                                                                       tasks_found, temp_task_list, '')
                                            temp_task_list = [
                                                subchild.text]  # reset to task name since get_task_name changes its value
                                            extra = '&nbsp;&nbsp;ID:'
                                            if subchild.tag == 'itemclickTask' or subchild.tag == 'clickTask':
                                                task_type = '⎯Task: TAP' + extra
                                            elif 'long' in subchild.tag:
                                                task_type = '⎯Task: LONG TAP' + extra
                                            else:
                                                task_type = '⎯Task: TEXT CHANGED' + extra
                                            process_list(task_type, the_output, temp_task_list, all_task_list,
                                                         all_scene_list, task_element, tasks_found, display_detail_level)  # Call ourselves iteratively
                                            my_output(the_output, 3, '')  # End list
                                        elif subchild.tag == 'Str':
                                            break
                                    if have_a_scene_task:  # Add Scene's Tasks to total list of Scene's Tasks
                                        getout = 2
                                    else:
                                        getout = 1
                                        break
                                elif 'Str' == cchild.tag:
                                    break
                                elif 'PropertiesElement' == cchild.tag:  # Have we gone past the point ofm interest?
                                    break
                        if child.tag == 'ButtonElement':
                            break
                        if getout > 0:
                            break
    return


# #######################################################################################
# Find the Project belonging to the Task id passed in
# #######################################################################################
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
        list_of_tasks = proj_tasks.split(',')
        if the_task_id in list_of_tasks:
            return proj_name, project
    return proj_name, project


# #######################################################################################
# Get a specific Profile's Tasks (maximum of two:entry and exit)
# #######################################################################################
def get_profile_tasks(the_profile, all_the_tasks, found_tasks_list, task_list_output, single_task_name):
    keys_we_dont_want = ['cdate', 'edate', 'flags', 'id']
    the_task_element, the_task_name = '', ''

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
            the_task_element, the_task_name = get_task_name(task_id, all_the_tasks, found_tasks_list, task_list_output,
                                                            task_type)
            if single_task_name and single_task_name == the_task_name:
                break
        elif 'nme' == child.tag:  # If hit Profile's name, we've passed all the Task ids.
            return the_task_element, the_task_name
    return the_task_element, the_task_name


# #######################################################################################
# Identify whether the Task passed in is part of a Scene: True = yes, False = no
# #######################################################################################
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


# #######################################################################################
# Profile condition: Time
# #######################################################################################
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


# #######################################################################################
# Profile condition: Day
# #######################################################################################
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


# #######################################################################################
# Profile condition: State
# #######################################################################################
def condition_state(the_item, cond_string):
    for child in the_item:
        mobile_network_type = {0: '2G', 1: '3G', 2: '3G HSPA', 3: '4G', 4: '5G'}
        orientation_type = {0: 'Face Up', 1: 'Face Down', 2: 'Standing Up', 3: 'Upside Down', 4: 'Left Side',
                            5: 'Right Side'}
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
                case '120':
                    orientation, lbl = get_action_detail(3, the_item, False)
                    orientation = orientation_type[int(orientation)]
                    state = 'Orientation' + orientation
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
                    battery_levels, lbl = get_action_detail(8, the_item, False)
                    if battery_levels:
                        if len(battery_levels) == 2:
                            to_level = ' to ' + battery_levels[1]
                        else:
                            to_level = ''
                        state = 'Battery Level from ' + battery_levels[0] + to_level + lbl
                    else:
                        state = 'Battery Level' + get_label_disabled_condition(the_item) + lbl
                case '142':
                    state = 'Monitor Start'
                case '143':  # Light Level
                    state = 'Task Running: ' + get_action_detail(1, the_item, False)
                case '150':
                    state = 'USB Connected'
                case '160':
                    state = 'WiFi Connected (to) ' + get_action_detail(1, the_item, False)
                case '165':  # State code 165 = action code 37
                    child.text = '37'
                    state = getcode(child, the_item, False)
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
            cond_string = cond_string + 'State: ' + state
            invert = the_item.find('pin')
            if invert is not None:
                if invert.text == 'true':
                    cond_string = cond_string + ' <em>[inverted]</em>'
            if debug:  # If debug add the code
                cond_string = cond_string + ' (code:' + child.text + ')'
        return cond_string
    return


# #######################################################################################
# Profile condition: Event
# #######################################################################################
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
                    ' sim:' + msg_fields[2] + ' body:' + msg_fields[3]
        case '201':
            event = 'Assistance Request'
        case '203':
            battery_levels = ['highest', 'high', 'normal', 'low', 'lowest']
            pri = the_item.find('pri')
            the_battery_level = battery_levels[(int(pri.text) - 1)]
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
                event = 'Volume Long Press Volume ' + volume_setting[int(the_volume)] + lbl
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
        case '1957681000':  # AutoInput Gesture
            event = getcode(the_event_code, the_item, False)
        case _:
            event = the_event_code.text + ' not yet mapped'

    cond_string = cond_string + 'Event: ' + event
    if debug:  # If debug then add the code
        cond_string = cond_string + ' (code:' + the_event_code.text + ')'
    return cond_string


# #######################################################################################
# Given a Profile, return its list of conditions
# #######################################################################################
def parse_profile_condition(the_profile):
    cond_title = 'condition '
    ignore_items = ['cdate', 'edate', 'flags', 'id', 'ProfileVariable']
    condition = ''  # Assume no condition
    for item in the_profile:
        if item.tag in ignore_items or 'mid' in item.tag:  # Bypass junk we don't care about
            continue
        if condition:  # If we already have a condition, add 'and' (italicized)
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
                condition = condition + 'Application:' + the_apps

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


# #######################################################################################
# Clean up our memory hogs
# #######################################################################################
def clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list):
    for elem in tree.iter():
        elem.clear()
    all_projects.clear()
    all_profiles.clear()
    all_tasks.clear()
    all_scenes.clear()
    root.clear()
    output_list.clear()
    return


# #######################################################################################
# Given a list [x,y,z] , print as x y z
# #######################################################################################
def print_list(list_title, the_list):
    line_out = ''
    seperator = ', '
    list_length = len(the_list) - 1
    if list_title:
        print(list_title)
    for item in the_list:
        if the_list.index(item) == list_length:  # Last item in list?
            seperator = ''
        line_out = line_out + item + seperator
    print(line_out)
    return


# #######################################################################################
# Validate the color name provided.  If color name is 'h', simply display all the colors
# #######################################################################################
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
    return


# #######################################################################################
# Get the runtime option for a color change and set it
# #######################################################################################
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
    return


# #######################################################################################
# Display help
# #######################################################################################
def display_the_help():
    help_text1 = '\nThis program reads a Tasker backup file (e.g. backup.xml) and displays the configuration of Profiles/Tasks/Scenes\n\n'
    help_text2 = 'Runtime options...\n\n  -h  for this help...overrides all other options\n  -d0  display first Task action only, for unnamed Tasks only (silent)\n  ' \
                 '-d1  display all Task action details for unknown Tasks only (default)\n  ' \
                 '-d2  display full Task action details on every Task\n  ' \
                 "-task='a valid Task name'  display the details for a single Task only (automatically sets -d option to -d2)\n  " \
                 "-profile='a valid Profile name'  display the details for a single Profile and its Task only\n  " \
                 "-profcon  display the condition(s) for Profiles\n  " \
                 "-v  for this program's version\n  " \
                 "-c(type)=color_name  define a specific color to 'type', \n           where type is one of the following...\n  " \
                 "         Project Profile Task Action DisableProfile\n           UnknownTask DisabledAction ActionCondition\n           ProfileCondition LauncherTask Background\n  " \
                 "         Example options: -cTask=Green -cBackground=Black\n  -ch  color help: display all valid colors"

    help_text3 = '\n\nExit codes...\n  exit 1- program error\n  exit 2- output file failure\n ' \
                 ' exit 3- file selected is not a valid Tasker backup file\n ' \
                 ' exit 5- requested single Task not found\n  exit 6- no or improper filename selected\n ' \
                 ' exit 7- invalid option'
    help_text4 = '\n\nThe output HTML file is saved in your current folder/directory'
    help_text = help_text1 + help_text2 + help_text3 + help_text4

    print(help_text)
    sys.exit()


# #######################################################################################
# Display program's caveats
# #######################################################################################
def display_caveats(output_list, display_detail_level):
    caveat1 = '<span style = "color:' + trailing_comments_color + '"' + font_to_use + '</span>CAVEATS:\n'
    caveat2 = '- Most but not all Task actions have been mapped and will display as such.  Likewise for Profile conditions.\n'
    caveat3 = '- This has only been tested on my own backup.xml file.' \
              '  For problems, email mikrubin@gmail.com and attach your backup.xml file .'
    caveat4 = '- Tasks that are identified as "Unnamed/Anonymous" have no name and are considered Anonymous.\n'
    caveat5 = '- For option -d0, Tasks that are identified as "Unnamed/Anonymous" will have their first Task only listed....\n' \
              '  just like Tasker does.'
    my_output(output_list, 0, '<hr>')  # line
    my_output(output_list, 4, caveat1)  # caveat
    if display_detail_level > 0:  # Caveat about Actions
        my_output(output_list, 4, caveat2)  # caveat
    my_output(output_list, 4, caveat3)  # caveat
    my_output(output_list, 4, caveat4)  # caveat
    if display_detail_level == 0:  # Caveat about -d0 option and 1sat Action for unnamed Tasks
        my_output(output_list, 4, caveat5)  # caveat
    return


# #######################################################################################
# Open and read the Tasker backup XML file
# Return the file name for use for
# #######################################################################################
def open_and_get_backup_xml_file():
    cancel_message = 'Backup file selection cancelled.  Program ended.'
    filename = ''
    # Initialize tkinter
    tkroot = Tk()
    tkroot.geometry('200x100')
    tkroot.title("Select Tasker backup xml file")
    if debug:
        filename = open('/Users/mikrubin/My Drive/Python/backup.xml')
    else:
        dir_path = os.path.dirname(os.path.realpath(__file__))  # Get current directory
        try:
            filename = askopenfile(parent=tkroot, mode='r',
                                   title='Select Tasker backup xml file', initialdir=dir_path,
                                   filetypes=[('XML Files', '*.xml')])
        except Exception:
            print(cancel_message)
            exit(6)
        if filename is None:
            print(cancel_message)
            exit(6)
    return filename


# #######################################################################################
# At least one of the program arguments is bad.  Report and exit.
# #######################################################################################
def report_bad_argument(the_bad_argument):
    print('Argument "' + the_bad_argument + '" is invalid!')
    exit(7)


# #######################################################################################
# Get the program arguments (e.g. python MapTasker.py -x)
# #######################################################################################
def get_program_arguments():
    global debug
    my_version = 'MapTask version 0.7.0'
    my_license = 'GNU GENERAL PUBLIC LICENSE (Version 3, 29 June 2007)'
    profile_precedence = 'The argument "-profile has precedence over -task'
    display_detail_level, single_task_name, single_profile_name, display_profile_conditions = '', '', '', ''

    for i, arg in enumerate(sys.argv):
        logger.debug('arg:' + arg + ' ' + arg[0:2])
        match arg[0:2]:
            case '-v':  # Version
                print(my_version)
                print(my_license)
                sys.exit()
            case '-h':  # Help
                display_the_help()
            case '-d':
                match arg:
                    case '-d0':  # Detail: 0 = no detail
                        display_detail_level = 0
                    case '-d1':  # Detail: 0 = no detail
                        display_detail_level = 1
                    case '-d2':  # Detail: 2 = all Task's actions/detail
                        display_detail_level = 2
                    case '-debug':
                        debug = True
                    case _:
                        report_bad_argument(arg)
            case '-t':
                if arg[1:6] == 'task=':
                    if not single_profile_name:
                        single_task_name = arg[6:len(arg)]
                    else:
                        print(profile_precedence)
                else:
                    report_bad_argument(arg)
            case '-c':
                if arg[0:3] == '-ch':
                    validate_color('h')
                elif arg[0:2] == '-c':
                    get_and_set_the_color(arg)
                else:
                    report_bad_argument(arg)
            case '-p':  # This could be a Profile name, Project name, or Profile condition
                    match arg[1:8]:
                        case 'profile':
                            if arg[8:9] == '=':
                                single_profile_name = arg[9:len(arg)]
                                if single_task_name:
                                    print(profile_precedence)
                                    single_task_name = ''  # Single Profile overrides single Task
                            else:
                                report_bad_argument(arg)
                        case 'profcon':
                            display_profile_conditions = True
                        case _:
                            report_bad_argument(arg)
            case _:
                if 'MapTasker' not in arg:
                    report_bad_argument(arg)

    return display_detail_level, single_task_name, single_profile_name, display_profile_conditions, debug


# #######################################################################################
# We're only doing a single Task or Profile.  Clear the Output and start over.
# #######################################################################################
def refresh_our_output(include_the_profile, the_output_list, project_name, profile_name):
    the_output_list.clear()
    my_output(the_output_list, 0, font_to_use + heading)
    my_output(the_output_list, 1, '')  # Start Project list
    my_output(the_output_list, 2, 'Project: ' + project_name)
    if include_the_profile:
        my_output(the_output_list, 1, '')  # Start Profile list
        my_output(the_output_list, 2, 'Profile: ' + profile_name)
        my_output(the_output_list, 1, '')  # Start Project list
    return


# #######################################################################################
# output_task: we have a Task and need to generate the output
# #######################################################################################
def output_task(the_output_list, our_task_name, our_task_element, task_list, project_name, profile_name, all_tasks_found,
                all_scenes_found, list_of_found_tasks, display_detail_level, single_task_name):
    single_task_found = False

    if our_task_name != '' and single_task_name:  # Are we mapping just a single Task?
        if single_task_name == our_task_name:
            # We have the single Task we are looking for
            single_task_found = True
            refresh_our_output(True, the_output_list, project_name, profile_name)

            process_list('Task:', the_output_list, task_list, all_tasks_found, all_scenes_found, our_task_element,
                         list_of_found_tasks, display_detail_level)
            return True, single_task_found  # Call it quits on Task...we have the one we want
        else:   # <<< What do we do with this logic?
            if len(task_list) > 1:  # If multiple Tasks in this Profile, just get the one we want
                for task_item in task_list:
                    if single_task_name in task_item:
                        task_list = [task_item]
                        my_output(the_output_list, 1, '')  # Start Task list
                        process_list('Task:', the_output_list, task_list, all_tasks_found, all_scenes_found,
                                     our_task_element,
                                     list_of_found_tasks, display_detail_level)
                        my_output(the_output_list, 3, '')  # End Task list
                        break
                    else:
                        continue
            return True, single_task_found
    elif task_list:
        my_output(the_output_list, 1, '')  # Start Task list
        process_list('Task:', the_output_list, task_list, all_tasks_found, all_scenes_found, our_task_element,
                     list_of_found_tasks, display_detail_level)
        my_output(the_output_list, 3, '')  # End Task list
        return False, single_task_found  # Normal Task...continue processing them
    else:
        return False, single_task_found


# #######################################################################################
# process_projects: go through all Projects Profiles...and output them
# #######################################################################################
def process_profiles(the_output_list, project, project_name, profile_ids, all_profiles_found, all_tasks_found,
                     all_scenes_found, list_of_found_tasks, single_profile_name,
                     single_task_name, display_detail_level):

    # Set up html to use
    profile_color_html = '<span style = "color:' + profile_color + '"</span>' + font_to_use
    disabled_profile_html = ' <span style = "color:' + disabled_profile_color + '"</span>[DISABLED] '
    launcher_task_html = ' <span style = "color:' + launcher_task_color + '"</span>[Launcher Task] ' + profile_color_html
    condition_color_html = ' <span style = "color:' + profile_condition_color + '"</span>'
    our_task_element = ''
    single_profile_found = False
    single_task_found = False

    # Go through the Profiles found in the Project
    for item in profile_ids:
        # Find the Project's actual Profile element
        for profile in all_profiles_found:
            # XML search order: id, mid"n", nme = Profile id, task list, Profile name
            # Get the Tasks for this Profile
            if item == profile.find('id').text:  # Is this the Profile we want?
                # Are we searching for a specific Profile?
                if single_profile_name:
                    try:
                        profile_name = profile.find('nme').text
                        if single_profile_name == profile_name:
                            single_profile_found = True
                            refresh_our_output(False, the_output_list, project_name, '')
                            pass
                        else:
                            continue
                    except Exception as e:  # no Profile name
                        continue
                task_list = []  # Profile's Tasks will be filled in here
                our_task_element, our_task_name = get_profile_tasks(profile, all_tasks_found, list_of_found_tasks,
                                                                    task_list, single_task_name)
                if debug:  # We need the Profile's ID if we are debugging the code
                    profile_id = profile.find('id').text
                # Examine Profile attributes
                limit = profile.find('limit')  # Is the Profile disabled?
                if limit is not None and limit.text == 'true':
                    disabled = disabled_profile_html
                else:
                    disabled = ''
                launcher_xml = project.find('ProfileVariable')  # Is there a Launcher Task with this Project?
                if launcher_xml is not None:
                    launcher = launcher_task_html
                else:
                    launcher = ''
                profile_name = ''
                if display_profile_conditions:
                    profile_condition = parse_profile_condition(profile)  # Get the Profile's condition
                    if profile_condition:
                        profile_name = condition_color_html + ' (' + profile_condition + ') ' + \
                                       profile_name + launcher + disabled
                # Start formulating the Profile output line
                try:
                    profile_name = profile.find('nme').text + profile_name  # Get Profile's name
                except Exception as e:  # no Profile name
                    if display_profile_conditions:
                        profile_condition = parse_profile_condition(profile)  # Get the Profile's condition
                        if profile_condition:
                            profile_name = no_profile + condition_color_html + ' (' + profile_condition + ') ' + \
                                           profile_color_html + launcher + disabled
                        else:
                            profile_name = profile_name + no_profile + launcher + disabled
                    else:
                        profile_name = profile_name + no_profile + launcher + disabled
                if debug:
                    profile_name = profile_name + ' ID:' + profile_id
                my_output(the_output_list, 2, profile_color_html + 'Profile: ' + profile_name)

                # We have the Tasks for this Profile.  Now let's output them.
                # True = we're looking for a specifc Task
                # False = this is a normal Task
                specific_task, single_task_found = output_task(the_output_list, our_task_name, our_task_element, task_list, project_name, profile_name, \
                               all_tasks_found, all_scenes_found, list_of_found_tasks, display_detail_level,
                               single_task_name)
                if specific_task:
                    if single_task_name and single_task_found:  # Get out if we've got the Task we're looking for
                        return our_task_element, single_profile_found, single_task_found
                    else:
                        continue
                else:
                    if single_profile_found:
                        return our_task_element, single_profile_found, single_task_found
                    else:
                        continue
                # if single_profile_found:
                #     break
            else:
                continue
        # if not our_task_element:  # No Profile Tasks found
        #     return ''
    return our_task_element, single_profile_found, single_task_found


# #######################################################################################
# process_projects: go through all Projects Profiles...and output them
# #######################################################################################
def process_projects_and_their_profiles(all_projects, all_profiles, all_tasks, all_scenes, output_list,
                                        found_tasks, projects_without_profiles,
                                        single_task_name, single_profile_name, display_detail_level):
    single_profile_found = False
    single_task_found = False
    our_task_element = ''

    for project in all_projects:
        # Don't bother with another Project if we've done a single Task or Profile only
        if single_task_found or single_profile_found:
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
            profile_ids = project_pids.split(',')  # Get all the Profile IDs for this Project

            # Process the Project's Profiles
            our_task_element, single_profile_found, single_task_found = process_profiles(output_list, project, project_name, profile_ids, all_profiles, all_tasks,
                     all_scenes, found_tasks, single_profile_name,
                     single_task_name, display_detail_level)

            if single_profile_name:
                if single_profile_name and not single_profile_found:  # Get out of Profile loop if we have the one we want
                    continue  # On to next Project

        # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        # ...only if not displaying a single Task
        if not single_task_name:
            scene_names = ''
            try:
                scene_names = project.find('scenes').text
            except Exception as e:
                pass
            if scene_names:
                scene_list = scene_names.split(',')
                process_list('Scene:', output_list, scene_list, all_tasks, all_scenes, our_task_element,
                             found_tasks, display_detail_level)
        # Found our Task
        # else:
        #     my_output(output_list, 3, '')  # Close Profile list
        #     my_output(output_list, 3, '')  # Close Project list
        #     return single_profile_found

        my_output(output_list, 3, '')  # Close Profile list
        if single_profile_found or single_task_found:
            my_output(output_list, 3, '')  # Close Project list
            return single_profile_found, single_task_found
        else:
            pass
    my_output(output_list, 3, '')  # Close Project list

    return single_profile_found, single_task_found


# #######################################################################################
# process_tasks: go through all tasks and output them
# #######################################################################################
def process_tasks_not_called_by_profile(all_the_projects, all_the_scenes, all_the_tasks, the_output_list,
                                        found_tasks_list, list_of_projects_with_no_tasks, display_detail_level,
                                        single_task_name, single_task_found):

    # First, let's delete all the duplicates in the found task list
    res = []
    for i in found_tasks_list:
        if i not in res:
            res.append(i)
    found_tasks = res

    # See if we didn't find our task
    unnamed_task_count = 0
    have_heading = 0
    task_name = ''
    the_task_name = ''

    for task in all_the_tasks:  # Get a/next Task
        if single_task_found:  # If we just processed a single task only, then bail out.
            break
        unknown_task = ''
        task_id = task.find('id').text
        if task_id == '98':
            logger.debug('No Profile ==========================' + task_id + '====================================')
        if task_id not in found_tasks:  # We have a solo Task not associated to any Profile
            project_name, the_project = get_project_for_solo_task(all_the_projects, task_id,
                                                                  list_of_projects_with_no_tasks)

            # At this point, we've found the Project this Task belongs to, or it doesn't belong to any Task
            if have_heading == 0:
                my_output(the_output_list, 0, '<hr>')  # blank line
                my_output(the_output_list, 0, '<font color="' + trailing_comments_color + '"' + font_to_use + '"' + \
                          'Tasks that are not called by any Profile...')
                my_output(the_output_list, 1, '')  # Start Task list
                have_heading = 1
            else:
                pass

            # Get the Task's name
            try:
                task_name = task.find('nme').text
                the_task_name = task_name
            except Exception as e:  # Task name not found!
                # Unknown Task.  Display details if requested
                task_name = unknown_task_name + '&nbsp;&nbsp;Task ID: ' + task_id
                if task_in_scene(task_id, all_the_scenes):  # Is this Task part of a Scene?
                    continue  # Ignore it if it is in a Scene
                else:  # Otherwise, let's add it to the count of unknown Tasks
                    unknown_task = '1'
                    unnamed_task_count += 1

            # Identify which Project Task belongs to if Task has a valid name
            if not unknown_task and project_name != no_project:
                if debug:
                    task_name += ' with Task ID ' + task_id + ' ...in Project ' + project_name
                else:  # Drop Task ID nnn since we don't need it
                    task_name += ' ...in Project ' + project_name
            else:
                pass

            # Output the (possible unknown) Task's details
            if not unknown_task or display_detail_level > 0:  # Only list named Tasks or if details are wanted
                task_list = [task_name]

                # We have the Tasks.  Now let's output them.
                specific_task, single_task_found = output_task(the_output_list, the_task_name, task, task_list, project_name, 'None',
                            all_the_tasks, all_the_scenes, [], display_detail_level, single_task_name)
                if specific_task:
                    break
                else:
                    pass
            else:
                pass
        else:
            pass

    # Provide total number of unnamed Tasks
    if unnamed_task_count > 0:
        if display_detail_level > 0:
            my_output(the_output_list, 0, '')  # line
        my_output(the_output_list, 3, '')  # Close Task list
        # If we don't have a single Task only, display total count of unnamed Tasks
        if not single_task_found and display_detail_level != 0:
            my_output(the_output_list, 0,
                      '<font color=' + unknown_task_color + '>There are a total of ' + str(
                          unnamed_task_count) + ' unnamed Tasks not associated with a Profile!')
    if task_name is True:
        my_output(the_output_list, 3, '')  # Close Task list

    my_output(the_output_list, 3, '')  # Close out the list

    return


# #######################################################################################
# write_out_the_file: we have a list of output lines.  Write them out.
# #######################################################################################
def write_out_the_file(list_of_output, output_dir, file_name):
    out_file = open(output_dir + file_name, "w")
    for item in list_of_output:
        # Change "Action: nn ..." to Action nn: ..." (i.e. move the colon)
        action_position = item.find('Action: ')
        if action_position != -1:
            action_number_list = item[action_position + 8:len(item)].split(' ')
            action_number = action_number_list[0]
            temp = item[0:action_position] + 'Action ' + action_number + ':' + item[action_position + 8 + len(
                action_number):len(item)]
            output_line = temp
        else:
            output_line = item
        out_file.write(output_line)
    out_file.close()  # Close our output file
    return


# ###############################################################################################
# Output Projects Without Tasks and Projects Without Profiles
# ###############################################################################################
def process_missing_tasks_and_profiles(output_lines_list, projects_without_tasks, projects_with_no_profiles,
                                       single_task_found):
    # List Projects with no Tasks
    if len(projects_without_tasks) > 0 and not single_task_found:
        my_output(output_lines_list, 0, '<hr><font color=' + trailing_comments_color + '"' + font_to_use + \
                  '<em>Projects Without Tasks...</em>')  # line
        for item in projects_without_tasks:
            my_output(output_lines_list, 4, 'Project ' + item + ' has no Tasks')

    # List all Projects without Profiles
    if projects_with_no_profiles:
        my_output(output_lines_list, 0, '<hr><font color=' + trailing_comments_color + '"' + font_to_use + \
                  '<em>Projects Without Profiles...</em>')  # line
        for item in projects_with_no_profiles:
            my_output(output_lines_list, 4, 'Project ' + item + ' has no Profiles')

    return


# ###############################################################################################
# Cleanup memory and let user know there was no match found for Task/Profile
# ###############################################################################################
def clean_up_and_exit(name, profile_or_task_name, tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list):
    output_list.clear()
    print(name + ' ' + profile_or_task_name + ' not found!!')
    clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)
    exit(5)


##############################################################################################################
#                                                                                                            #
#   Main Program Starts Here                                                                                 #
#                                                                                                            #
##############################################################################################################
def main():
    # Initialize local variables
    found_tasks = []
    output_list = []
    projects_without_profiles = []
    projects_with_no_tasks = []
    my_file_name = '/MapTasker.html'
    display_detail_level = 1  # Default (1) display detail: unknown Tasks actions only

    # Get any arguments passed to program
    logger.debug('sys.argv' + str(sys.argv))
    display_detail_level, single_task_name, single_profile_name, display_profile_conditions, debug = get_program_arguments()
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< DELETE THESE FOR PRODUCTION >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

    # Force full detail if we are doing a single Task
    if single_task_name:
        logger.debug('Single Task=' + single_task_name)
        display_detail_level = 2  # Force detailed output <<<<<<<< CHANGE >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

    # Prompt user for Tasker's backup.xml file location
    if run_counter < 1:  # Only display message box on first run
        msg = 'Locate the Tasker backup xml file to use to map your Tasker environment'
        title = 'MapTasker'
        messagebox.showinfo(title, msg)

    # Open and read the file...
    filename = open_and_get_backup_xml_file()

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
    my_output(output_list, 0, heading)
    my_output(output_list, 1, '')  # Start Project list

    # #######################################################################################
    # Go through XML and Process all Projects
    # #######################################################################################
    single_profile_found, single_task_found = process_projects_and_their_profiles(all_projects, all_profiles, all_tasks, all_scenes, output_list,
                                                            found_tasks, projects_without_profiles,
                                                            single_task_name, single_profile_name, display_detail_level)

    if single_profile_name and not single_profile_found:
        clean_up_and_exit('Profile', single_profile_name, tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)

    # #######################################################################################
    # Now let's look for Tasks that are not referenced by Profiles and display a total count
    # #######################################################################################
    if not single_task_name and not single_profile_name:
        process_tasks_not_called_by_profile(all_projects, all_scenes, all_tasks, output_list, found_tasks,
                                            projects_with_no_tasks, display_detail_level, single_task_name, single_task_found)

    # #######################################################################################
    # List any Projects without Tasks and Projects without Profiles
    # #######################################################################################
        process_missing_tasks_and_profiles(output_list, projects_with_no_tasks, projects_without_profiles,
                                           single_task_found)

    # Requested single Task but invalid Task name provided (i.e. no Task found)?
    if (single_task_name and not single_task_found) and not (single_profile_name and single_profile_found):
        clean_up_and_exit('Task', single_task_name, tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)


    # #######################################################################################
    # Let's wrap things up...
    # #######################################################################################
    # Output caveats if we are displaying the Actions
    display_caveats(output_list, display_detail_level)

    # Okay, lets generate the actual output file.
    # Store the output in the current  directory
    my_output_dir = os.getcwd()
    if my_output_dir is None:
        print('MapTasker cancelled.  An error occurred.  Program cancelled.')
        clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)
        exit(2)

    # Output the generated html
    write_out_the_file(output_list, my_output_dir, my_file_name)

    # Clean up memory
    clean_up_memory(tree, all_projects, all_profiles, all_tasks, all_scenes, root, output_list)

    # Display final output
    webbrowser.open('file://' + my_output_dir + my_file_name, new=2)
    print(
        "You can find 'MapTasker.html' in the current folder.  Your browser has displayed it in a new tab.  Program end.")


# Main call
if __name__ == "__main__":
    main()
