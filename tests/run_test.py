#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# run_test: run MapTasker unit test routines                                           #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# Reference: https://github.com/Taskomater/Tasker-XML-Info                             #
#                                                                                      #
# #################################################################################### #
import time
from unittest.mock import patch

from maptasker.src import mapit


def test_it():
    """
    Test the function 'test_it' by running it.

    This function is used to test the functionality of the 'test_it' function. It executes the following steps:

    1. Prints the value of 'sys.argv'.
    2. Calls the 'mapit.mapit_all' function with an empty string as the argument.
    3. Pauses the execution for 1 second.

    This function does not take any parameters and does not return any values.
    """
    # print('run_test sys.argv:', sys.argv)
    mapit.mapit_all("")
    # Take a breath between each run to avoid collision issues with browser
    time.sleep(1)


# Run these in small chunks, depending on the size of the backup file being used.
def test_main():
    """
    Test main function to test various scenarios using patch to simulate different sys.argv inputs.
    """
    ip = "60"
    ## Test name attributes
    #with patch("sys.argv", ["-test=yes", "reset", "restore", "debug", "outline" ]):
    #    test_it()
    ## Test name attributes
    #with patch("sys.argv", ["-test=yes", "reset", "detail=2", "debug", "names=bold highlight", "cHighlight LightBlue"]):
    #    test_it()
    #with patch(
    #    "sys.argv", ["-test=yes", "reset", "detail=1", "debug", "names=underline italicize", "font='Menlo'"], and 'Say WaveNet  Test/SSML= %antext ,' plus more.
    #):
    #    test_it()
    ## Test light mode
    #with patch("sys.argv", ["-test=yes", "reset", "detail=2", "debug", "appearance=light"]):
    #    test_it()
    ## Test max detail
    #with patch("sys.argv", ["-test=yes", "reset", "detail=5", "debug", "pretty"]):
    #    test_it()
    ## Test max detail
    #with patch("sys.argv", ["-test=yes", "reset", "detail=4", "debug", "i=10"]):
    #    test_it()
    ## Test full detail
    #with patch("sys.argv", ["-test=yes", "reset", "detail=3", "debug"]):
    #    test_it()
    ## Test limited detail
    #with patch("sys.argv", ["-test=yes", "reset", "detail=2", "debug"]):
    #    test_it()
    ## Test limited detail 1
    #with patch("sys.argv", ["-test=yes", "reset", "detail=1", "debug"]):
    #    test_it()
    ## Test no detail
    #with patch("sys.argv", ["-test=yes", "reset", "detail=0", "debug"]):
    #    test_it()
    ## Test by Project name
    #with patch(
    #    "sys.argv", ["-test=yes", "reset", "project=Base", "debug", "conditions", "taskernet"]):
    #    test_it()
    ## Test by Profile name
    #with patch(
    #    "sys.argv",
    #    ["-test=yes", "reset", "profile=Check Heat", "detail=3", "debug"]):
    #    test_it()
    ## Test by Task name
    #with patch("sys.argv", ["-test=yes", "reset", "task=Check Batteries", "debug", "detail=4"]):
    #    test_it()
    ## Test -pref
    #with patch("sys.argv", ["-test=yes", "reset", "preferences", "debug", "taskernet", "detail=2"]):
    #    test_it()
    ## Test -dir
    #with patch("sys.argv", ["-test=yes", "reset", "directory", "debug", "taskernet", "detail=4"]):
    #    test_it()
    ## Test new -everything with twisty and outline
    #with patch("sys.argv", ["-test=yes", "reset", "e"]):
    #    test_it()
    ## Test fetch backup xml file
    #with patch(
    #    "sys.argv",
    #    [
    #        "-test=yes", "reset",
    #        f"android_ipaddr=192.168.0.{ip}", "android_port=1821", "android_file=/Tasker/configs/user/backup.xml",
    #    ],
    #):
    #    test_it()
    ## Test just a Profile
    #with patch(
    #    "sys.argv",
    #    [
    #        "-test=yes", "reset",
    #        f"android_ipaddr=192.168.0.{ip}", "android_port=1821", "android_file=/Tasker/profiles/File_List.prf.xml",
    #    ],
    #):
    #    test_it()
    ## Test just a Task
    #with patch(
    #    "sys.argv",
    #    [
    #        "-test=yes", "reset",
    #        f"android_ipaddr=192.168.0.{ip}", "android_port=1821", "android_file=/Tasker/tasks/Setup_ADB_Permissions.tsk.xml",
    #    ],
    #):
    #    test_it()
    ## Test just a Scene
    #with patch(
    #    "sys.argv",
    #    [
    #        "-test=yes", "reset", "pretty",
    #        f"android_ipaddr=192.168.0.{ip}", "android_port=1821", "android_file=/Tasker/scenes/Lock.scn.xml",
    #    ],
    #):
    #    test_it()
    ## Test colors
    #with patch(
    #    "sys.argv",
    #    [
    #        "-test=yes", "reset",
    #        "cBackground=Black",
    #        "cActionCondition=Yellow",
    #        "cProfileCondition=Red",
    #        "cActionLabel=White",
    #        "cProfile=Yellow",
    #        "cDisabledAction=Green",
    #        "cLauncherTask=Purple",
    #        "cActionName=White",
    #        "cTask=Yellow",
    #        "cUnknownTask=Green",
    #        "cScene=Teal",
    #        "cTaskerNetInfo=Violet",
    #        "cProfile=Yellow",
    #        "cDisabledProfile=Orange",
    #        "cBullet=Red",
    #        "cPreferences=Linen",
    #        "cAction=Blue",
    #        "cTrailingComments=LightGoldenrodYellow",
    #        "e",
    #        "debug",
    #    ],
    #):
    #    test_it()

    # # Test invalid runtime parameters

    # # Test bad IP address/port/file
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes", "reset",
    #         "android_ipaddr192.168.0.6x", "android_port=1821", "android_file=/Tasker/configs/user/backup.xml",
    #     ],
    # ):
    #     test_it()


if __name__ == "__main__":
    test_main()
