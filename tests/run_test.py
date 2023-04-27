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
import sys


def test_main():
    # Test full detail
    with patch("sys.argv", ["-test=yes", "detail=3", "d"]):
        print('run_test sys.argv:', sys.argv)
        mapit.mapit_all("")
    # Test limited detail
    with patch("sys.argv", ["-test=yes", "detail=2", "d"]):
        print('run_test sys.argv:', sys.argv)
        mapit.mapit_all("")
    # Test limited detail 1
    with patch("sys.argv", ["-test=yes", "detail=1", "d"]):
        print('run_test sys.argv:', sys.argv)
        mapit.mapit_all("")
    # Test no detail
    with patch("sys.argv", ["-test=yes", "detail=0", "d"]):
        print('run_test sys.argv:', sys.argv)
        mapit.mapit_all("")
    # Test by Project name
    with patch(
        "sys.argv", ["-test=yes", "project=Base", "d", "conditions", "taskernet"]
    ):
        print('run_test sys.argv:', sys.argv)
        mapit.mapit_all("")
    # Test by Profile name
    with patch(
        "sys.argv",
        ["-test=yes", "profile=Check Smartthings Batteries", "detail=3", "d"],
    ):
        print('run_test sys.argv:', sys.argv)
        mapit.mapit_all("")
    # Test by Task name
    with patch("sys.argv", ["-test=yes", "task=Check Batteries", "d"]):
        print('run_test sys.argv:', sys.argv)
        mapit.mapit_all("")
    # Test new -pref
    with patch("sys.argv", ["-test=yes", "p", "d", "taskernet", "detail=2"]):
        mapit.mapit_all("")
    # Test new -everything
    with patch("sys.argv", ["-test=yes", "e"]):
        mapit.mapit_all("")
    # Test colors
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes",
    #         "cBackground=Black",
    #         "cActionCondition=Yellow",
    #         "cProfileCondition=Red",
    #         "cActionLabel=White",
    #         "e",
    #         "d",
    #     ],
    # ):
    #     mapit.mapit_all("")
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes",
    #         "cProfile=Yellow",
    #         "cDisabledAction=Green",
    #         "cLauncherTask=Red",
    #         "cActionName=White",
    #         "e",
    #         "d",
    #     ],
    # ):
    #     mapit.mapit_all("")
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes",
    #         "cTask=Yellow",
    #         "cUnknownTask=Green",
    #         "cScene=Red",
    #         "cTaskerNetInfo=White",
    #         "e",
    #         "d",
    #     ],
    # ):
    #     mapit.mapit_all("")
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes",
    #         "cProfile=Yellow",
    #         "cDisabledProfile=Orange",
    #         "cBullet=Red",
    #         "cPreferences=White",
    #         "e",
    #         "d",
    #     ],
    # ):
    #     mapit.mapit_all("")
    # with patch(
    #     "sys.argv",
    #     [
    #         "-test=yes",
    #         "cTask=Yellow",
    #         "cAction=Red",
    #         "cTrailingComments=Yellow",
    #         "e",
    #         "d",
    #     ],
    # ):
    #     mapit.mapit_all("")


if __name__ == "__main__":
    test_main()
