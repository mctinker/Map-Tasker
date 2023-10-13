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
    # print('run_test sys.argv:', sys.argv)
    mapit.mapit_all("")
    # Take a breath between each run to avoid collision issues with browser
    time.sleep(1)


# Run these in small chunks, depending on the size of the backup file being used.
def test_main():
    # # Test name attributes
    # with patch("sys.argv", ["-test=yes", "restore", "debug", "outline" ]):
    #     test_it()
    # # Test name attributes
    # with patch("sys.argv", ["-test=yes", "detail=2", "debug", "names=bold highlight", "cHighlight LightBlue"]):
    #     test_it()
    # with patch(
    #     "sys.argv", ["-test=yes", "detail=2", "debug", "names=underline italicize", "f='Menlo'"]
    # ):
    #     test_it()
    # # Test light mode
    # with patch("sys.argv", ["-test=yes", "detail=2", "debug", "a=light"]):
    #     test_it()
    # # Test bold highlight ands directory
    # with patch("sys.argv", ["-test=yes", "detail=2", "debug", "names=bold highlight", "directory"]):
    #     test_it()
    # # Test full detail
    # with patch("sys.argv", ["-test=yes", "detail=3", "debug", "i=10"]):
    #     test_it()
    # # Test limited detail
    # with patch("sys.argv", ["-test=yes", "detail=2", "debug"]):
    #     test_it()
    # # Test limited detail 1
    # with patch("sys.argv", ["-test=yes", "detail=1", "debug"]):
    #     test_it()
    # # Test no detail
    # with patch("sys.argv", ["-test=yes", "detail=0", "debug"]):
    #     test_it()
    # # Test by Project name
    # with patch(
    #     "sys.argv", ["-test=yes", "project=Base", "debug", "conditions", "taskernet"]
    # ):
    #     test_it()
    # # Test by Profile name
    # with patch(
    #     "sys.argv",
    #     ["-test=yes", "profile=View File", "detail=3", "debug"],
    # ):
    #      test_it()
    # # Test by Task name
    # with patch("sys.argv", ["-test=yes", "task=Check Batteries", "debug", "detail=4"]):
    #     test_it()
    # # Test -pref
    # with patch("sys.argv", ["-test=yes", "preferences", "debug", "taskernet", "detail=2"]):
    #     test_it()
    # # Test -dir
    # with patch("sys.argv", ["-test=yes", "directory", "debug", "taskernet", "detail=4"]):
    #     test_it()
    # # Test new -everything with twisty and outline
    # with patch("sys.argv", ["-test=yes", "e", "twisty", "o"]):
    #     test_it()
    # # Test -b fetch backup xml file
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes",
    #         "b=http://192.168.0.210:1821+/Tasker/configs/user/backup.xml",
    #     ],
    # ):
    #     test_it()
    # Test colors
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes",
    #         "cBackground=Black",
    #         "cActionCondition=Yellow",
    #         "cProfileCondition=Red",
    #         "cActionLabel=White",
    #         "cProfile=Yellow",
    #         "cDisabledAction=Green",
    #         "cLauncherTask=Purple",
    #         "cActionName=White",
    #         "cTask=Yellow",
    #         "cUnknownTask=Green",
    #         "cScene=Teal",
    #         "cTaskerNetInfo=Violet",
    #         "cProfile=Yellow",
    #         "cDisabledProfile=Orange",
    #         "cBullet=Red",
    #         "cPreferences=Linen",
    #         "cAction=Blue",
    #         "cTrailingComments=LightGoldenrodYellow",
    #         "e",
    #         "debug",
    #     ],
    # ):
    #     test_it()



if __name__ == "__main__":
    test_main()
