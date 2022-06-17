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
# Version 2.0                                                                                #
#                                                                                            #
# - 2.0 Added output style (linear or bullet), bullet_color as global var                    #
#       Added detail mode (default) which can be turned off with option -s                   #
#        displaying unnamed Task's Actions                                                   #
# - 1.2 Added -v and -h arguments to display the program version and help                    #
# - 1.2 launch browser to display results                                                    #
# - 1.1 Added list of Tasks for which there is no Profile                                    #
#                                                                                            #
# ########################################################################################## #
import xml.etree.ElementTree
import easygui as g
import xml.etree.ElementTree as ET
import os
import sys
import webbrowser
import copy

#  Global constants
project_color = 'Black'
profile_color = 'Blue'
task_color = 'Green'
unknown_task_color = 'Red'
scene_color = 'Purple'
bullet_color = 'Black'
action_color = 'Orange'
browser = 'Google Chrome.app'
line_spacing = '0.0001em'

help_text1 = 'This program reads a Tasker backup file and displays the configuration of Profiles/Tasks/Scenes\n\n'
help_text2 = 'Runtime options...\n  -h for this help\n  -s for no Task action details (silent)\n  -l for list style output\n  -v for version.'

caveat1 = 'CAVEATS:\n'
caveat2 = '1- Not all Task actions have been mapped and will display as such.\n'
caveat3 = '2- Actions listed are not necessarily in the precise order as they appear in the Task, and should\n'
caveat4 = '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;only be used to assist in identifying the Unnamed/Anonymous Task.'
unknown_task_name = 'Unnamed/Anonymous.'
my_version = '2.0'
my_file_name = '/MapTasker.html'


# Returns the action's name and associated variables depending on the input xml code
# <code>nn</code>  ...translate the nn into it's Action name
def getcode(code_child, code_action):
    taskcode = code_child.text
    if taskcode == '20':
        for cchild in code_action:
            if cchild.tag == 'App':
                app = cchild.find('appClass')
                lbl = cchild.find('label')
                return 'Tasker widget for ' + app.text + ' with label ' + lbl.text
    elif taskcode == '30':
        for cchild in code_action:
            try:
                if cchild.tag == 'Int' and cchild.attrib['val'] != '0':
                    return "Wait for " + cchild.attrib['val']
            except Exception as e:
                pass
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
                            print('var2.text:',var2.text)
                        var4 = children.find('rhs')
                        return "If " + var1.text + var3 + var4.text
    elif taskcode == '38':
        return "End If"
    elif taskcode == '39':
        count = 0
        for cchild in code_action:
            if cchild.tag == 'Str' and count == 0:
                count = 1
                var1 = cchild.text
            elif cchild.tag == 'Str' and count == 1:
                var2 = cchild.text
                return "For " + var1 + ' to ' + var2
            else:
                pass
        return "For " + var1
    elif taskcode == '40':
        return "End For or Stop"
    elif taskcode == '43':
        return "Else/Else If"
    elif taskcode == '49':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Destroy Scene " + cchild.text
    elif taskcode == '55':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Element Back Colour " + cchild.text
    elif taskcode == '66':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Element Image " + cchild.text
    elif taskcode == '102':
        return "Open File "
    elif taskcode == '105':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Set Clipboard To " + cchild.text
    elif taskcode == '119':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Open Map, Navigate to " + cchild.text
    elif taskcode == '135':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Go To " + cchild.text
    elif taskcode == '137':
        return "Else"
    elif taskcode == '173':
        return "Network Access "
    elif taskcode == '193':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Set Clipboard to " + cchild.text
    elif taskcode == '307':
        for cchild in code_action:
            if cchild.tag == 'Int':
                return "Media Volume to  " + cchild.attrib.get('val')
    elif taskcode == '331':
        return "Auto-Sync"
    elif taskcode == '355':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Array Push " + cchild.text
    elif taskcode == '356':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Array Pop " + cchild.text
    elif taskcode == '356':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Array Process " + cchild.text
    elif taskcode == '373':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Test Sensor " + cchild.text
            elif taskcode == '378':
                for cchild in code_action:
                    if cchild.tag == 'Str' and cchild.text != None:
                        return "List Dialog " + cchild.text
    elif taskcode == '410':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Write File " + cchild.text
    elif taskcode == '425':
        return "Turn Wifi"
    elif taskcode == '523':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Notify " + cchild.text
    elif taskcode == '547':
        var1 = ''
        for cchild in code_action:
            if cchild.tag == 'Str' and '%' == cchild.text[0:1]:
                if var1 == '':
                    var1 = cchild.text
                else:
                    return "Variable Set " + var1 + ' to ' + cchild.text
            elif cchild.tag == 'Str':
                return "Variable Set " + var1 + ' to ' + cchild.text
            else:
                pass
    elif taskcode == '548':
        for cchild in code_action:
            if cchild.tag == 'Str' and cchild.text != None:
                return "Flash Alert- " + cchild.text
    elif taskcode == '549':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Variable Clear " + cchild.text
    elif taskcode == '559':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Say " + cchild.text
    elif taskcode == '590':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Variable Split " + cchild.text
    elif taskcode == '779':
        for cchild in code_action:
            if cchild.tag == 'Str':
                return "Notify Cancel " + cchild.text
    elif taskcode == '810':
        for cchild in code_action:
            if cchild.tag == 'Int':
                return "Display Brightness to  " + cchild.attrib.get('val')
    elif 1000 < int(taskcode):
        return "Call to Plugin"
    else:
        return "Code " + taskcode + " not yet mapped"


# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
def ulify(element, out_style, out_unknown, lvl=int):   # lvl=0=heading 1=start list 2=Task/Profile/Scene 3=end list 4=special Task
    string = ''
    # Heading..............................
    if lvl == 0:  # lvl=4 >>> Heading
        string = "<b>" + element + "</b><br>\n"
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
            if out_style == 'L':
                string = '<p style = "color:' + action_color + ';line-height:' + line_spacing + '">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├⎯⎯' + element + '\n'
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
    return


# Construct Task Action output line
def build_action(alist, tcode, achild):
    if tcode != '':
        alist.append(tcode)
    else:
        alist.append('Action ' + achild.text + ': not yet mapped')
    return


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
        for action in task_actions:
            for child in action:
                try:
                    # Check for Task's "code"
                    if 'code' == child.tag:  # Get the specific Task Action code
                        task_code = getcode(child, action)
                        build_action(tasklist, task_code, child)
                    else:
                        pass
                except Exception as e:
                    pass
    return tasklist


# Get the name of the task given the Task ID
# return the Task's element and the Task's name
def get_task_name(the_task_id, all_the_tasks, found_tasks, the_task_list, have_the_task):
    task_name = ''
    for task in all_the_tasks:
        if the_task_id == task.find('id').text:
            found_tasks.append(the_task_id)
            try:
                task_name = task.find('nme').text
                if have_the_task:
                    the_task_list.append(task_name + '   <<< exit task' + '&nbsp;&nbsp;Task ID: ' + the_task_id)
                else:
                    the_task_list.append(task_name)
                    have_the_task = '1'
            except Exception as e:
                if have_the_task:
                    the_task_list.append(unknown_task_name + ' <<< Exit task' + '&nbsp;&nbsp;Task ID: ' + the_task_id)
                else:
                    the_task_list.append(unknown_task_name + '&nbsp;&nbsp;Task ID: ' + the_task_id)
                    have_the_task = '1'
                break
    return task, task_name


# Process Task/Scene text/line item: call recursively for Tasks within Scenes
def process_list(list_type, the_output, the_list, all_task_list, all_scene_list, the_task, the_style, the_unknown, tasks_found, detail):
    my_count = 0
    if the_style != 'L':
        my_output(the_output, 1, the_style, the_unknown, '')  # Start list_type list
    for the_item in the_list:
        if my_count > 0 and the_style == 'L':  # If more than one list_type, skip normal output
            my_output(the_output, 2, the_style, the_unknown, '<br>&nbsp;&nbsp;&nbsp;&nbsp;├⎯' + list_type + '&nbsp;' + the_item + '<br>')
        else:
            my_output(the_output, 2, the_style, the_unknown, list_type + '&nbsp;' + the_item)
            my_count += 1
        # Output Actions for this Task if displaying detail and Task is unknown
        # Do we get the Task's Actions?
        if 'Task:' in list_type and detail and (the_unknown == 1 or unknown_task_name in the_item):
            if unknown_task_name in the_item:   # If Unknown task, then "the_task" is not valid, and we have to find it.
                temp = the_item.split('ID: ')   # Unknown/Anonymous!  Task ID: nn    << We just need the nn
                the_task, kaka = get_task_name(temp[1], all_task_list, tasks_found, [temp[1]], the_unknown)
            alist = get_actions(the_task)  # <<<< The problem is the_task is not in the_item and a carryover from where process_list was called
            if alist:
                my_output(the_output, 1, the_style, False, '')  # Start Action list
                for taction in alist:
                    my_output(the_output, 2, the_style, False, 'Action: ' + str(taction))
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
                                have_the_task = '0'
                                if 'ListElement' == cchild.tag or 'TextElement' == cchild.tag or 'ImageElement' == cchild.tag:
                                    for subchild in cchild:   # Go through ListElement sub-items
                                        if subchild.tag == 'itemclickTask' or subchild.tag == 'itemlongclickTask' or subchild.tag == 'clickTask':
                                            scene_task_list.append(subchild.text)
                                            temp_task_list = [subchild.text]
                                            task_element, name_of_task = get_task_name(subchild.text, all_task_list, tasks_found, temp_task_list, the_unknown)
                                            temp_task_list = [subchild.text]  # reset to task name since get_task_name changes it's value
                                            if subchild.tag == 'itemclickTask' or subchild.tag == 'clickTask':
                                                task_type = '⎯Task: TAP&nbsp;&nbsp;ID:'
                                            elif subchild.tag == 'itemlongclickTask':
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
def main():
    task_list = []
    found_tasks = []
    display_detail = True

    output_style = ''  # L=linear, default=bullet
    help_text = help_text1 + help_text2
    # Get any arguments passed to program
    for i, arg in enumerate(sys.argv):
        if arg == '-v':  # Version
            g.textbox(msg="MapTasker Version", title="MapTasker", text="Version " + my_version)
            sys.exit()
        elif arg == '-h':  # Help
            g.textbox(msg="MapTasker Help", title="MapTasker", text=help_text)
            sys.exit()
        elif arg == '-s':  # Detail: -s = silent (no detail)
            display_detail = False
        elif arg == '-l':
            output_style = 'L'

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
        exit(1)
    out_file = open(my_output_dir + my_file_name, "w")

    # Import xml
    tree = ET.parse(filename)
    root = tree.getroot()
    all_scenes = root.findall('Scene')
    all_tasks = root.findall('Task')
    if 'TaskerData' != root.tag:
        my_output(out_file, 0, output_style, False, 'You did not select a Tasker backup XML file...exit 2')
        exit(2)

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
                        have_task = ''
                        for child in profile:
                            if 'mid' in child.tag:
                                task_id = child.text
                                task_id_list.append(task_id)
                                # if task_id == '65':
                                #     print('====================================',task_id,'====================================')
                                our_task_element, our_task_name = get_task_name(task_id, all_tasks, found_tasks, task_list, have_task)
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
    first_task = 1
    have_heading = 0
    for task in root.findall('Task'):  # Get a/next Task
        unknown_task = 0
        task_id = task.find('id').text
        if task_id not in found_tasks:  # We have a solo Task
            project_name = ''  # Find the Project it belongs to
            #action_list = []
            for project in root.findall('Project'):
                project_tasks = project.find('tids').text
                if task_id in project_tasks:
                    project_name = project.find('name').text
                    break
            if have_heading == 0:
                my_output(out_file, 0, output_style, False, '<hr>') # blank line
                my_output(out_file, 0, output_style, False, 'Tasks that are not in any Profile (may be a desktop Tasker Task/widget or Task in a Scene)...')
                my_output(out_file, 1, output_style, False, '')  # Start Task list
                have_heading = 1
            try:
                task_name = task.find('nme').text
            except Exception as e:  # Task name not found!
                unnamed_tasks += 1

                # Unknown Task.  Display details if requested
                task_name = unknown_task_name + '&nbsp;&nbsp;Task ID: ' + task_id
                unknown_task = 1
                if display_detail:
                    action_list = []
                    action_list = get_actions(task)

            # Identify which Project Task belongs to
            if unknown_task == 0 and project_name:
                task_name += ' ...in Project ' + project_name
                project_name = ''
            # Output the unknown Task's details
            if unknown_task == 0 or display_detail is True:  # Only list named Tasks or if details are wanted
                task_list = [task_name]
                # This will output the task and it's Actions if displaying details
                process_list('Task:', out_file, task_list, all_tasks, all_scenes, task, output_style, unknown_task, found_tasks, display_detail)
                first_task = 0
            unknown_task = 0

    # Provide total number of unnamed Tasks
    if unnamed_tasks > 0:
        if output_style == 'L' or display_detail is True:
            my_output(out_file, 0, output_style, False, '<hr>')  # line
        my_output(out_file, 3, output_style, False, '')  # Close Task list
        my_output(out_file, 0, output_style, False, 'There are a total of ' + str(unnamed_tasks) + ' unnamed Tasks!!!')
    if task_name is True:
        my_output(out_file, 3, output_style, False, '')  # Close Task list

    # Let's wrap things up...
    my_output(out_file, 3, output_style, False, '')  # Close out the list
    # Output caveats if we are displaying the Actions
    if display_detail:
        my_output(out_file, 0, output_style, False, '<hr>')  # line
        my_output(out_file, 0, output_style, False, caveat1)  # caveat
        my_output(out_file, 0, output_style, False, caveat2)  # caveat
        my_output(out_file, 0, output_style, False, caveat3)  # caveat
        my_output(out_file, 0, output_style, False, caveat4)  # caveat
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
