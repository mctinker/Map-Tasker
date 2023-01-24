# ########################################################################################## #
#                                                                                            #
# rungui: process GUI for MapTasker                                                          #
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
# ########################################################################################## #
import contextlib

from config import *

if GUI:
    from routines.userintr import MyGui


# #######################################################################################
# Output the provided message and return (then quit)
# #######################################################################################
def output_and_quit(arg0):
    out_message = arg0
    print(out_message)
    logger.debug(out_message)


# #######################################################################################
# Get the program arguments from GUI
# #######################################################################################
def process_gui(colormap, use_gui):
    if use_gui:
        from routines.userintr import MyGui

    # Display GUI and get the user input
    user_input = MyGui()
    user_input.mainloop()

    if user_input.exit:
        output_and_quit("Program exited. Goodbye.")
        exit()

    # User has either closed the window or hit the 'Run' button
    if not user_input.go_program:  # Window closed?
        output_and_quit("Program cancelled be user (killed GUI)")
        exit(99)

    # 'Run' button hit.  Get all the input from GUI variables
    try:
        display_detail_level = int(user_input.display_detail)
    except Exception as e:
        display_detail_level = 1
    # Ok, load up the arguments from the GUI
    display_profile_conditions = user_input.conditions
    single_project_name = user_input.project_name
    single_profile_name = user_input.profile_name
    single_task_name = user_input.task_name
    if user_input.color_lookup:  # If we have at least one color item selected...
        # Map the GUI named items to the action color named items
        for key, value in user_input.color_lookup.items():
            match key:
                case "Projects":
                    colormap["project_color"] = value
                case "Profiles":
                    colormap["profile_color"] = value
                case "Disabled Projects":
                    colormap["disabled_profile_color"] = value
                case "Launcher Task":
                    colormap["launcher_task_color"] = value
                case "Profile Conditions":
                    colormap["profile_condition_color"] = value
                case "Tasks":
                    colormap["task_color"] = value
                case "(Task) Actions":
                    colormap["action_color"] = value
                case "Action Conditions":
                    colormap["action_condition_color"] = value
                case "Action Labels":
                    colormap["action_label_color"] = value
                case "Action Names":
                    colormap["action_name_color"] = value
                case "Scenes":
                    colormap["scene_color"] = value
                case "Background":
                    colormap["background_color"] = value
                case "Bullets":
                    colormap["bullet_color"] = value
                case _:
                    pass

    debug = user_input.debug_mode

    # Delete the GUI
    del user_input

    return (
        display_detail_level,
        display_profile_conditions,
        single_project_name,
        single_profile_name,
        single_task_name,
        debug,
    )
