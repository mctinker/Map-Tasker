# ########################################################################################## #
#                                                                                            #
# action: Task Action functions for MapTasker                                                #
#                                                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import routines.tasks as tasks
from routines.outputl import my_output
from routines.xmldata import tag_in_type


# #######################################################################################
# For this specific Scene, get any Tasks it might have and output the details
# #######################################################################################
def get_scene_details_and_output(
    the_list: list[str],
    output_list: list[str],
    tasks_found: list[str],
    program_args: dict,
    colormap: dict,
    all_tasker_items: dict,
) -> None:
    from routines.proclist import process_list

    scene_task_types = {
        "checkchangeTask": "Check Change",
        "clickTask": "TAP",
        "focuschangeTask": "Focus Change",
        "itemselectedTask": "Item Selected",
        "keyTask": "Key",
        "linkclickTask": "Link",
        "longclickTask": "LONG TAP",
        "mapclickTask": "Map",
        "maplongclickTask": "Long Map",
        "pageloadedTask": "Page Load",
        "strokeTask": "STROKE",
        "valueselectedTask": "Value Selected",
        "videoTask": "Video",
    }
    have_a_scene_task = False
    for my_scene in the_list:  # Go through each Scene to find TAP and Long TAP Tasks
        getout = 0
        for child in all_tasker_items["all_scenes"][
            my_scene
        ]:  # Go through sub-elements in the Scene element
            if tag_in_type(child.tag, True):
                for sub_child in child:  # Go through ListElement sub-items
                    if tag_in_type(
                        sub_child.tag, False
                    ):  # Task associated with this Scene's element?
                        my_output(
                            colormap, program_args, output_list, 1, ""
                        )  # Start Scene's Task list
                        have_a_scene_task = True
                        temp_task_list = [sub_child.text]
                        task_element, name_of_task = tasks.get_task_name(
                            sub_child.text,
                            tasks_found,
                            temp_task_list,
                            "",
                            all_tasker_items["all_tasks"],
                        )
                        temp_task_list = [
                            sub_child.text
                        ]  # reset to task name since get_task_name changes its value
                        extra = "&nbsp;&nbsp;ID:"
                        task_type = f"⎯Task: {scene_task_types[sub_child.tag]}{extra}"
                        process_list(
                            task_type,
                            output_list,
                            temp_task_list,
                            task_element,
                            tasks_found,
                            program_args,
                            colormap,
                            all_tasker_items,
                        )  # process the Scene's Task
                        my_output(
                            colormap, program_args, output_list, 3, ""
                        )  # End list
                    elif sub_child.tag == "Str":
                        break
                if (
                    have_a_scene_task
                ):  # Add Scene's Tasks to total list of Scene's Tasks
                    getout = 2
                else:
                    break
            elif child.tag == "Str":
                break
            elif (
                child.tag == "PropertiesElement"
            ):  # Have we gone past the point ofm interest?
                break
            if getout > 0:
                break
