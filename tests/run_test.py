#! /usr/bin/env python3

#                                                                                      #
# run_test: run MapTasker unit test routines                                           #
#                                                                                      #


# Reference: https://github.com/Taskomater/Tasker-XML-Info                             #
#                                                                                      #
"""End-to-end driver that runs MapTasker once per runtime-argument combination.

Each case patches sys.argv and calls mapit.mapit_all().  The "-test=yes" first element
is what makes runcli use unit_test() to build the argument namespace from these lists
instead of parsing a real command line.

WHY THESE ARE SKIPPED BY DEFAULT
--------------------------------
mapit_all() reaches get_program_arguments() (progargs.py), whose `if GUI: process_gui(True)`
starts the NiceGUI web server and blocks until the window is closed -- config.GUI is True,
and runcli.process_cli additionally forces program_arguments["gui"] True on its own, so the
command-line branch below it is unreachable.  There is therefore no headless path for these
runs to take: collected normally they would hang `pytest tests/` rather than fail it.

They are still useful as a manual smoke test -- each case opens the GUI with those settings
applied -- so they run on request rather than never:

    python tests/run_test.py                 # run them directly
    MAPTASKER_E2E=1 pytest tests/run_test.py # or through pytest

Set MAPTASKER_XML / MAPTASKER_XML_BACKUP to point the cases at your own files.  Note that
get_program_arguments() silently substitutes backup.xml for a file that does not exist, so
a wrong path here quietly maps something else instead of reporting the mistake -- hence the
explicit check in run_maptasker().
"""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from maptasker.src import mapit

# The Android cases need a device on the LAN running the 'HTTP Server Example' Tasker
# project (see BACKUP_HELP_TEXT in userhelp.py) at this address.
ANDROID_IP_SUFFIX = os.environ.get("MAPTASKER_ANDROID_IP_SUFFIX", "59")

# Sample configurations to map.  Overridable so this is not tied to one machine.
FILE_TO_USE = os.environ.get("MAPTASKER_XML", "/Users/mikrubin/MapTasker/My_Apps.prj.xml")
FILE_TO_USE1 = os.environ.get("MAPTASKER_XML_BACKUP", "/Users/mikrubin/MapTasker/backup.xml")

# Collected only when explicitly asked for -- see the module docstring.
pytestmark = pytest.mark.skipif(
    os.environ.get("MAPTASKER_E2E") != "1",
    reason="Opens the NiceGUI window and blocks; set MAPTASKER_E2E=1 to run.",
)


def run_maptasker():
    """Run MapTasker once against whatever sys.argv the caller has patched in.

    Deliberately not named test_* -- pytest would otherwise collect this helper on its
    own and run it against pytest's argv rather than any of the cases below.
    """
    for label, path in (("MAPTASKER_XML", FILE_TO_USE), ("MAPTASKER_XML_BACKUP", FILE_TO_USE1)):
        if not Path(path).exists():
            msg = f"{label} points at {path}, which does not exist (MapTasker would silently map backup.xml instead)"
            raise FileNotFoundError(msg)

    mapit.mapit_all()
    # Take a breath between each run to avoid collision issues with browser
    time.sleep(1)


# Run these in small chunks, depending on the size of the backup file being used.
def test_main():
    """
    Test main function to test various scenarios using patch to simulate different sys.argv inputs.
    """
    ip = ANDROID_IP_SUFFIX
    file_to_use = FILE_TO_USE
    file_to_use1 = FILE_TO_USE1

    # # Test name attributes
    print("test 0")
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "debug",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test name attributes
    print("test 1")
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "detail=2",
            "debug",
            "names=bold highlight",
            "cHighlight LightBlue",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()

    print("test 2")
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "detail=1",
            "debug",
            "names=underline italicize",
            "font='Menlo'",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test light mode
    print("test 3")
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "detail=2",
            "debug",
            "appearance=light",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test max detail
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "detail=5",
            "debug",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test max detail
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "detail=4",
            "debug",
            "i=10",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test full detail
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "detail=3",
            "debug",
            "pretty",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test limited detail
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "detail=2",
            "debug",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test limited detail 1
    with patch(
        "sys.argv",
        ["-test=yes", "reset", "detail=1", "debug", f"file={file_to_use}"],
    ):
        run_maptasker()
    # Test no detail
    with patch(
        "sys.argv",
        ["-test=yes", "reset", "detail=0", "debug", f"file={file_to_use}"],
    ):
        run_maptasker()
    # Test by Project name
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "projectBase",
            "debug",
            "conditions",
            "taskernet",
            f"file={file_to_use1}",
        ],
    ):
        run_maptasker()
    # Test by Profile name
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "profile=SUS 2 - UPDATE NOTIFICATION",
            "detail=3",
            "debug",
            "pretty",
            f"file={file_to_use1}",
        ],
    ):
        run_maptasker()
    # Test by Task name
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "task=App Removed",
            "debug",
            "detail=4",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test -pref
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "preferences",
            "debug",
            "taskernet",
            "detail=2",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test -dir
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "directory",
            "debug",
            "taskernet",
            "detail=4",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test new -everything with twisty and outline
    with patch("sys.argv", ["-test=yes", "reset", "e", f"file={file_to_use}"]):
        run_maptasker()
    # Test fetch backup xml file
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            f"android_ipaddr=192.168.0.{ip}",
            "android_port=1821",
            "android_file=/Tasker/configs/user/backup.xml",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test just a Profile
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            f"android_ipaddr=192.168.0.{ip}",
            "android_port=1821",
            "android_file=/Tasker/profiles/File_List.prf.xml",
            f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test just a Task
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            f"android_ipaddr=192.168.0.{ip}",
            "android_port=1821",
            "android_file=/Tasker/tasks/SUS_12___SET_YOUR_LANGUAGE.tsk.xml",
            # f"file={file_to_use}",
        ],
    ):
        run_maptasker()
    # Test just a Scene
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "pretty",
            "detail=5",
            f"android_ipaddr=192.168.0.{ip}",
            "android_port=1821",
            "android_file=/Tasker/scenes/Lock.scn.xml",
        ],
    ):
        run_maptasker()
    # Test colors
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            "cBackground=Black",
            "cActionCondition=Yellow",
            "cProfileCondition=Red",
            "cActionLabel=White",
            "cProfile=Yellow",
            "cDisabledAction=Green",
            "cLauncherTask=Purple",
            "cActionName=White",
            "cTask=Yellow",
            "cUnknownTask=Green",
            "cScene=Teal",
            "cTaskerNetInfo=Violet",
            "cProfile=Yellow",
            "cDisabledProfile=Orange",
            "cBullet=Red",
            "cPreferences=Linen",
            "cAction=Blue",
            "cTrailingComments=LightGoldenrodYellow",
            "e",
            "debug",
            f"file={file_to_use1}",
        ],
    ):
        run_maptasker()

    # Test invalid runtime parameters

    # Test bad IP address/port/file
    with patch(
        "sys.argv",
        [
            "-test=yes",
            "reset",
            f"android_ipaddr=192.168.0.{ip}",
            "android_port=1821",
            "android_file=/Tasker/configs/user/backup.xml",
        ],
    ):
        run_maptasker()


if __name__ == "__main__":
    test_main()
