# ########################################################################################## #
#                                                                                            #
# progargss: program arguments support routines                                              #
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

import sys
from config import *  # Configuration info

FONT_TO_USE = f"<font face={OUTPUT_FONT}>"


# #######################################################################################
# Display help
# #######################################################################################
def display_the_help():
    logger.info("display help and exit")
    help_text1 = "\nThis program reads a Tasker backup file (e.g. backup.xml) and displays the configuration of Profiles/Tasks/Scenes\n\n"
    help_text2 = (
        "Runtime options...\n\n  -h  for this help...overrides all other options\n  -d0  display all with first Task action only, for unnamed Tasks only (silent)\n  "
        "-d1  display all Task action details for unknown Tasks only (default)\n  "
        "-d2  display all Task action names only\n  "
        "-d3  display full Task action details (parameters) on every Task\n  "
        "-project='a valid Project name'  display the details for a single Project, its Profiles and its Task only\n  "
        "-profile='a valid Profile name'  display the details for a single Profile and its Task only\n  "
        "-task='a valid Task name'  display the details for a single Task only (automatically sets -d option to -d2)\n  "
        "-g  bring up the GUI (and ignore command line arguments)\n  "
        "-profcon  display the condition(s) for Profiles\n  "
        "-v  for this program's version\n  "
        "-c(type)=color_name  define a specific color to 'type', \n           where type is one of the following...\n  "
        "         Project Profile Task Action DisableProfile\n           UnknownTask DisabledAction ActionCondition ActionName\n  "
        "         ProfileCondition LauncherTask Background\n  "
        "         Example options: -cTask=Green -cBackground=Black\n  -ch  color help: display all valid colors"
    )

    help_text3 = (
        "\n\nExit codes...\n  exit 1- program error\n  exit 2- output file failure\n "
        " exit 3- file selected is not a valid Tasker backup file\n "
        " exit 5- requested single Task not found\n  exit 6- no or improper filename selected\n "
        " exit 7- invalid option\n  exit 8- unexpected xml error (report this as a bug)"
    )
    help_text4 = "\n\nThe output HTML file is saved in your current folder/directory"
    help_text = help_text1 + help_text2 + help_text3 + help_text4
    print(help_text)
    sys.exit()


# #######################################################################################
# At least one of the program arguments is bad.  Report and exit.
# #######################################################################################
def report_bad_argument(the_bad_argument):
    bad_message = f'Argument "{the_bad_argument}" is invalid!'
    logger.debug(f"{bad_message}-exit 7")
    print(bad_message)
    exit(7)


# #######################################################################################
# We have a -d argument.  Now find out what specific detail level is needed (e.g. -d2 ?)
# #######################################################################################
def get_detail_level(arg, display_detail_level, debug):
    match arg:
        case "-d0":  # Detail: 0 = no detail
            display_detail_level = 0
        case "-d1":  # Detail: 0 = no detail, first action only
            display_detail_level = 1
        case "-d2":  # Detail: 2 = all Task's actions names only
            display_detail_level = 2
        case "-d3":  # Detail: 3 = all Task's actions and parameters
            display_detail_level = 3
        case "-debug":
            debug = True
        case _:
            report_bad_argument(arg)
    level = str(display_detail_level)
    return display_detail_level, debug


# #######################################################################################
# We have a -p argument.  Now find out if -project, -profile or -profcon
# #######################################################################################
def get_dashp_specifics(
    arg,
    single_task_name,
    single_profile_name,
    single_project_name,
    display_profile_conditions,
    argument_precedence,
):
    match arg[1:8]:
        case "profile":
            if arg[8:9] == "=":
                single_profile_name = arg[9:]
                if single_task_name:
                    print(f'"-profile="{argument_precedence}"-task=".')
                    single_task_name = ""  # Single Profile overrides single Task
            else:
                report_bad_argument(arg)
        case "project":
            if arg[8:9] == "=":
                single_project_name = arg[9:]
                if single_task_name or single_profile_name:
                    print(f'"-project="{argument_precedence}"-task=" or "-profile=".')
                    single_task_name, single_profile_name = (
                        "",
                        "",
                    )  # Single Project overrides single Task/Profile
            else:
                report_bad_argument(arg)
        case "profcon":
            display_profile_conditions = True
        case _:
            report_bad_argument(arg)
    return (
        single_task_name,
        single_profile_name,
        single_project_name,
        display_profile_conditions,
    )
