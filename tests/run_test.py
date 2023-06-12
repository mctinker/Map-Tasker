#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# run_test: run MapTasker unit test routines                                                 #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# Reference: https://github.com/Taskomater/Tasker-XML-Info                                   #
#                                                                                            #
# ########################################################################################## #
from unittest.mock import patch
from maptasker.src import mapit
import time


def test_it():
    # print('run_test sys.argv:', sys.argv)
    mapit.mapit_all("")
    # Take a breath between each run to avoid collision issues with browser
    time.sleep(1)


def test_main():
    # Test full detail
    with patch("sys.argv", ["-test=yes", "detail=3", "d"]):
        test_it()
    # Test limited detail
    with patch("sys.argv", ["-test=yes", "detail=2", "d"]):
        test_it()
    # Test limited detail 1
    with patch("sys.argv", ["-test=yes", "detail=1", "d"]):
        test_it()
    # Test no detail
    with patch("sys.argv", ["-test=yes", "detail=0", "d"]):
        test_it()
    # Test by Project name
    with patch(
        "sys.argv", ["-test=yes", "project=Base", "d", "conditions", "taskernet"]
    ):
        test_it()
    # Test by Profile name
    with patch(
        "sys.argv",
        ["-test=yes", "profile=Check Smartthings Batteries", "detail=3", "d"],
    ):
        test_it()
    # Test by Task name
    with patch("sys.argv", ["-test=yes", "task=Check Batteries", "d"]):
        test_it()
    # Test new -pref
    with patch("sys.argv", ["-test=yes", "p", "d", "taskernet", "detail=2"]):
        test_it()
    # Test new -everything
    with patch("sys.argv", ["-test=yes", "e"]):
        test_it()
    # Test -b fetch backup xml file
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "b=http://192.168.0.210:1821+/Tasker/configs/user/backup.xml",
        ],
    ):
        test_it()
    # Test -twisty
    with patch("sys.argv", ["-test=yes", "sys.argv", "d", "twisty"]):
        test_it()
    # Test colors
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "cBackground=Black",
            "cActionCondition=Yellow",
            "cProfileCondition=Red",
            "cActionLabel=White",
            "e",
            "d",
        ],
    ):
        test_it()
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "cProfile=Yellow",
            "cDisabledAction=Green",
            "cLauncherTask=Red",
            "cActionName=White",
            "e",
            "d",
        ],
    ):
        test_it()
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "cTask=Yellow",
            "cUnknownTask=Green",
            "cScene=Red",
            "cTaskerNetInfo=White",
            "e",
            "d",
        ],
    ):
        test_it()
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "cProfile=Yellow",
            "cDisabledProfile=Orange",
            "cBullet=Red",
            "cPreferences=White",
            "e",
            "d",
        ],
    ):
        test_it()
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "cTask=Yellow",
            "cAction=Red",
            "cTrailingComments=Yellow",
            "e",
            "d",
        ],
    ):
        test_it()


if __name__ == "__main__":
    test_main()
