#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# MapTasker: read the Tasker backup file to map out the configuration                        #
#                                                                                            #
# Version 1.1                                                                                #
#                                                                                            #
# - 1.1 Added list of Tasks for which there is no Profile                                    #
#                                                                                            #
# ########################################################################################## #

import easygui as g
import xml.etree.ElementTree as ET
import os
import sys, getopt

#  Global constants
project_color = 'Black'
profile_color = 'Blue'
task_color = 'Green'
scene_color = 'Purple'
unknown_task_name = 'Unnamed or Anonymous!!!'


def ulify(element, lvl=int):
    if lvl == 0:  # lvl=4 >>> Heading
        string = "<b>" + element + "</b>\n"
    elif lvl == 1:  # lvl=1 >>> Start list
        string = "<ul>" + element + "\n"
    elif lvl == 2:  # lvl=2 >>> List item
        if 'Project' == element[0:7]:
            string = '<li style="color:Red" ><span style="color:' + project_color + ';">' + element + '</span></li>\n'
        elif 'Profile' == element[0:7]:
            string = '<li style="color:Red" ><span style="color:' + profile_color + ';">' + element + '</span></li>\n'
        elif 'Task' == element[0:4]:
            string = '<li style="color:Red" ><span style="color:' + task_color + ';">' + element + '</span></li>\n'
        elif 'Scene' == element[0:5]:
            string = '<li style="color:Red" ><span style="color:' + scene_color + ';">' + element + '</span></li>\n'
        else:
            string = "<li>" + element + "</li>\n"
    elif lvl == 3:  # lvl=3 >>> End list
        string = "</ul>"
    return string


def my_output(out_file, list_level, out_string):
    out_file.write(ulify(out_string, list_level))


# Main program here >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>        
def main():
    task_list = []
    all_tasks = []

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
    out_file = open("MapTasker.html", "w")

    # Import xml
    tree = ET.parse(filename)
    root = tree.getroot()
    if 'TaskerData' != root.tag:
        my_output(out_file, 0, 'You did not select a Tasker backup XML file...exit 2')
        exit(2)

    my_output(out_file, 0, 'Tasker Mapping................')
    my_output(out_file, 1, '')  # Start Project list

    # Traverse the xml

    # Start with Projects <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    for project in root.findall('Project'):
        project_name = project.find('name').text
        project_pids = ''
        # print("Project:", project_name)
        my_output(out_file, 2, 'Project: ' + project_name)

        my_output(out_file, 1, '')  # Start Profile list
        try:
            project_pids = project.find('pids').text  # Project has no Profiles
        # except xml.etree.ElementTree.ParseError doesn't compile:
        except Exception:
            my_output(out_file, 2, 'Profile: none or unnamed!')
        if project_pids != '':  # Project has Profiles?
            profile_id = project_pids.split(',')
            # Now find the Profiles and their Task for this Project <<<<<<<<<<<<<<<<<<<<<
            for item in profile_id:
                for profile in root.findall('Profile'):
                    # XML search order: id, mid"n", nme = Profile id, task list, Profile name
                    if item == profile.find('id').text:  # Is this the Profile we want?
                        task_list = []  # Get the Tasks for this Profile
                        have_task = ''
                        for child in profile:
                            if 'mid' in child.tag:
                                task_id = child.text
                                for task in root.findall('Task'):
                                    if task_id == task.find('id').text:
                                        all_tasks.append(task_id)
                                        try:
                                            task_name = task.find('nme').text
                                            if have_task:
                                                task_list.append(task_name + '   <<< exit task')
                                            else:
                                                task_list.append(task_name)
                                                have_task = '1'
                                        except Exception as e:
                                            if have_task:
                                                task_list.append(unknown_task_name + ' <<< Exit task')
                                            else:
                                                task_list.append(unknown_task_name)
                                                have_task = '1'
                                            break
                        try:
                            profile_name = profile.find('nme').text  # Get Profile's name
                        except Exception as e:  # no Profile name
                            # my_output(out_file, 2, "Profile: Unnamed!!")
                            profile_name = 'Unnamed!!'
                            pass
                        my_output(out_file, 2, 'Profile: ' + profile_name)
                if task_list:
                    my_output(out_file, 1, '')  # Start Task/Scene list
                    for task in task_list:
                        my_output(out_file, 2, 'Task: ' + task)
                    my_output(out_file, 3, '')  # Close Task list

        # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        scene_names = ''
        try:
            scene_names = project.find('scenes').text
        except Exception as e:
            pass
        if scene_names != '':
            scene_list = scene_names.split(',')
            for scene in scene_list:
                my_output(out_file, 2, 'Scene: ' + scene)
            my_output(out_file, 3, '')  # Close Scene list

        my_output(out_file, 3, '')  # Close Profile list
    my_output(out_file, 3, '')  # Close Project list

    # Now let's look for Tasks that are not referenced by Profiles
    first_task = 1
    task_name = ''
    unnamed_tasks = 0
    for task in root.findall('Task'):  # Get a/next Task
        task_id = task.find('id').text
        if task_id in all_tasks:
            pass
        else:  # We have a solo Task
            project_name = '(None)'  # Find the Project it belongs to
            for project in root.findall('Project'):
                project_tasks = project.find('tids').text
                if task_id in project_tasks:
                    project_name = project.find('name').text
            if first_task == 1:
                my_output(out_file, 0, 'Tasks that are not in any Profile (may be a desktop Tasker Task/widget)...')
                my_output(out_file, 1, '')  # Start Task list
            try:
                task_name = task.find('nme').text
            except Exception as e:  # Task name not found!
                unnamed_tasks += 1
                pass
                # For future use
                task_name = unknown_task_name
                try:
                    action = task.find('Action')
                    for child in action:
                        if 'Str' == child.tag and child.text != 'None':
                            if '%' == child.text[0:1]:  # junk?
                                break
                            task_name += '  The first Task action is >>> ' + child.text
                            break
                except Exception as e:
                    pass

            task_name += ' ...in Project ' + project_name
            if unknown_task_name not in task_name:
                my_output(out_file, 2, 'Task: ' + task_name)
            first_task = 0
    if unnamed_tasks > 0:
        my_output(out_file, 2, 'There are ' + str(unnamed_tasks) + ' unnamed Tasks!!!')
    if task_name is True:
        my_output(out_file, 3, '')  # Close Task list

    my_output(out_file, 3, '')  # Close out the list
    out_file.close()
    g.textbox(msg="MapTasker Done", title="MapTasker",
              text="You can find 'MapTasker.html' in the same folder as the backup.xml file is located.  Open it with a browser.")


# Main call
if __name__ == "__main__":
    main()
