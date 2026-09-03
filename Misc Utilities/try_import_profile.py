#! /usr/bin/env python3
"""Prototype harness for deviceinv.import_profile_to_device.

Two modes, and the first one touches nothing:

    build  -- synthesize 'MapTasker Import Profile v1' and print it as the standalone XML
              that would be POSTed to api/import to install it.  No device, no network.
              Read the <code>153</code> action's arg0/arg1/arg2 before doing anything else.

    build-open   -- the same, for 'MapTasker Open Profile v1': the route that hands the
              file to Tasker's own import screen instead (<code>102</code>, Open File).

    build-intent -- and for 'MapTasker Send Profile v1', which addresses Tasker explicitly
              (<code>877</code>, Send Intent).  The fallback for when Open File's implicit
              resolution does not land on Tasker.

    open   -- the Open File route against a real device.  Safe: Tasker shows you what it
              is about to import and you tap Import (or don't).  Try this one first.

    intent -- the Send Intent route against a real device.  Equally safe; try it if 'open'
              does not bring up Tasker's import screen.

    run    -- the Import Data route against a real device.  DESTRUCTIVE-UNTIL-PROVEN: what
              Tasker does to the rest of the configuration when handed a Profile as a
              'Configuration' import is exactly what this is meant to find out.  Point it
              at a device whose configuration you are willing to lose.

Usage:
    .venv/bin/python try_import_profile.py build [backup.xml]
    .venv/bin/python try_import_profile.py build-open [backup.xml]
    .venv/bin/python try_import_profile.py build-intent [backup.xml]
    .venv/bin/python try_import_profile.py build-open-project [backup.xml]
    .venv/bin/python try_import_profile.py build-profile <backup.xml> <profile name>
    .venv/bin/python try_import_profile.py open   <backup.xml> <profile name> <ip> <port>
    .venv/bin/python try_import_profile.py intent  <backup.xml> <profile name> <ip> <port>
    .venv/bin/python try_import_profile.py project <backup.xml> <PROJECT name> <ip> <port>
    .venv/bin/python try_import_profile.py run  <backup.xml> <profile name> <ip> <port>
"""

from __future__ import annotations

import json
import os
import sys

REPO = "/Users/mikrubin/MapTasker_Dev"
sys.path.insert(0, REPO)

from maptasker.src.primitem import PrimeItems  # noqa: E402


def bootstrap(backup_path: str) -> None:
    """The two pieces of program state the edit machinery needs, without starting the GUI.

    arg_specs.json is what classify_action_addability reads to tell an Int from an App
    picker (proginit loads it at startup); the parsed backup is what create_new_task needs
    for a collision-free id and for the Element class the synthesized XML has to match.
    """
    specs_path = os.path.join(REPO, "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_path, encoding="utf-8") as file:
        specs = json.load(file)
    count = len(specs)
    specs[str(count)] = "ConditionList"
    specs[str(count + 1)] = "Img"
    for key, value in specs.items():
        if value == "String":
            specs[key] = "Str"
            break
    PrimeItems.tasker_arg_specs = specs

    from maptasker.src import taskerd
    from maptasker.src.colrmode import set_color_mode
    from maptasker.src.initparg import initialize_runtime_arguments

    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.program_arguments["gui"] = False
    PrimeItems.file_to_get = open(backup_path, encoding="utf-8")  # noqa: SIM115
    return_code = taskerd.get_the_xml_data()
    PrimeItems.file_to_get.close()
    if return_code != 0:
        raise SystemExit(f"Could not read {backup_path} (taskerd returned {return_code}).")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    backup = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO, "XML", "backup.xml")
    bootstrap(backup)

    from maptasker.src import deviceinv, profedit, projedit, sceneedit, taskedit

    if mode in ("build", "build-open", "build-intent", "build-open-project", "build-open-scene"):
        builder = {
            "build": deviceinv.build_import_profile_task,
            "build-open": deviceinv.OPEN_FILE_ROUTE.builder,
            "build-intent": deviceinv.SEND_INTENT_ROUTE.builder,
            "build-open-project": deviceinv.OPEN_PROJECT_ROUTE.builder,
            "build-open-scene": deviceinv.OPEN_SCENE_ROUTE.builder,
        }[mode]
        built = builder()
        if isinstance(built, str):
            print(f"FAILED: {built}")
            return 1
        print(taskedit.render_standalone_task_xml(built))
        return 0

    profile_name = sys.argv[3] if len(sys.argv) > 3 else ""
    if not profile_name:
        print("A Profile name is required for this mode.")
        return 2

    edited = profedit.load_profile_for_edit(profile_name)
    if edited is None:
        print(f"FAILED: no Profile named '{profile_name}' in {backup}.")
        return 1
    profile_xml = profedit.render_standalone_profile_xml(edited).encode("utf-8")

    if mode == "build-profile":
        print(profile_xml.decode("utf-8"))
        return 0

    if mode in ("scene", "scene-intent"):
        scene_xml = sceneedit.render_standalone_scene_xml(profile_name).encode("utf-8")
        ip_address, ip_port = sys.argv[4], sys.argv[5]
        # 'scene' lets Android find the handler; 'scene-intent' names Tasker explicitly,
        # which is what to reach for when the first one raises an "Open with..." chooser
        # that Tasker is not in.
        route = deviceinv.SEND_INTENT_SCENE_ROUTE if mode == "scene-intent" else deviceinv.OPEN_SCENE_ROUTE
        print(f"Sending Scene '{profile_name}' to {ip_address} via {route.task_name}.")
        return_code, message = deviceinv.open_scene_on_device(
            scene_xml,
            profile_name,
            ip_address,
            ip_port,
            route=route,
        )
        print(f"[{return_code}] {message}")
        return 0 if return_code == 0 else 1

    if mode == "project":
        project_xml = projedit.render_standalone_project_xml(profile_name).encode("utf-8")
        profile_names = projedit.project_profile_names(profile_name)
        ip_address, ip_port = sys.argv[4], sys.argv[5]
        print(f"Sending Project '{profile_name}' ({len(profile_names)} confirmable Profiles) to {ip_address}.")
        return_code, message = deviceinv.open_project_on_device(
            project_xml,
            profile_name,
            profile_names,
            ip_address,
            ip_port,
        )
        print(f"[{return_code}] {message}")
        return 0 if return_code == 0 else 1

    if mode not in ("run", "open", "intent"):
        print(__doc__)
        return 2

    ip_address, ip_port = sys.argv[4], sys.argv[5]
    if mode in ("open", "intent"):
        route = deviceinv.SEND_INTENT_ROUTE if mode == "intent" else deviceinv.OPEN_FILE_ROUTE
        print(f"Sending '{profile_name}' to {ip_address}:{ip_port}.  Confirm the import on the device.")
        return_code, message = deviceinv.open_profile_on_device(
            profile_xml,
            profile_name,
            ip_address,
            ip_port,
            route=route,
        )
        print(f"[{return_code}] {message}")
        return 0 if return_code == 0 else 1

    print(f"About to import '{profile_name}' into Tasker on {ip_address}:{ip_port}.")
    print("This can alter the device's ENTIRE Tasker configuration.  Type the device IP again to go ahead: ", end="")
    if input().strip() != ip_address:
        print("Nothing was sent.")
        return 1

    return_code, message = deviceinv.import_profile_to_device(
        profile_xml,
        profile_name,
        ip_address,
        ip_port,
        acknowledged_risk=True,
    )
    print(f"[{return_code}] {message}")
    return 0 if return_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
