#! /usr/bin/env python3
"""Try MapTasker's device features on a real phone, and record what happened.

Much of what MapTasker does to an Android device was worked out from Tasker's own files and never seen
working: the comments say "reasoned, not measured" where that is so.  A fake Tasker (tests/faketasker.py)
proves the conversation is right, and can prove nothing about what Android and Tasker do with it.  This
asks the phone, and asks YOU what you saw on it, and keeps the answers in a file with the date, so a claim
in the code can say when it was last checked instead of how it was reasoned.

    python tools/device_check.py --ip 192.168.0.210 --port 1821 --list            what each check settles
    python tools/device_check.py --ip 192.168.0.210 --port 1821                   the checks that need no backup
    python tools/device_check.py --ip ... --port ... --backup backup.xml          all of them
    python tools/device_check.py --ip ... --port ... --only api-key,open-with-profile

The phone needs the 'Tasker HTTP API' project, and the 'Http Server Example' project for the checks that read
and write files.  Tasker asks you to authorize the connection, several times: watch the phone.

Two kinds of check:

  * automatic -- MapTasker asks the phone and compares the answer.  Pass, or fail with the phone's message.
  * asked -- MapTasker does something the phone shows you (opens Tasker's import screen, a TaskerNet page),
    and asks what you saw.  Nothing is ever imported: back out of every screen.  The checks that need a loaded
    configuration to build their helper Task (the asked ones) take --backup.

One check is a diagnostic and is not in the default set: import-probe imports a trivial Task three ways to say what the
phone refuses.  It runs by itself when helper-round-trip fails, to say why, and with --only import-probe.  It leaves
Tasks named "MapTasker Device Check <date>" in your Task list, which only you can delete (Tasker's HTTP API cannot).

Each run is appended to device_check_results.json (--results) as {when, device, checks: [{id, status, detail}]},
and a summary table is printed.  Exit status 0 when nothing failed (a skipped check is not a failure), 1 if any did.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PASS, FAIL, SKIP = "pass", "fail", "skip"

# What Tasker would be given by an import that was allowed to finish: nothing the user would mind finding, named so it
# can be found and deleted, and never actually imported by this tool (the screens are backed out of).
CHECK_NAME = "MapTasker Device Check"
_PROFILE_XML = (
    '<TaskerData sr="" dvi="1" tv="6.3.13"><Profile sr="prof9991" ve="2"><cdate>1735689600000</cdate>'
    f'<edate>1735689600000</edate><id>9991</id><nme>{CHECK_NAME}</nme><Time sr="con0"><fh>3</fh><fm>0</fm>'
    "<th>3</th><tm>5</tm></Time></Profile></TaskerData>"
).encode()
_PROJECT_XML = (
    '<TaskerData sr="" dvi="1" tv="6.3.13"><Project sr="proj0" ve="2"><cdate>1735689600000</cdate>'
    f"<name>{CHECK_NAME}</name><id>9992</id></Project></TaskerData>"
).encode()


@dataclass
class Outcome:
    """What one check found."""

    status: str
    detail: str = ""


@dataclass
class Device:
    """The phone under test, and how this run talks to the person at it."""

    address: str
    port: str
    ask: Callable[[str, list[str]], int]  # a question and the answers it offers -> the index chosen (-1: no answer)
    has_backup: bool = False


@dataclass(frozen=True)
class Check:
    """One thing to try."""

    id: str
    title: str
    settles: str  # the claim in the code this settles, in a sentence
    run: Callable[[Device], Outcome]
    needs_backup: bool = False
    # A diagnostic, not part of the default set: run on its own with --only, or by itself right after the check it
    # names has failed, to say why.
    after_failure_of: str = ""


# ##################################################################################
# The automatic checks
# ##################################################################################
def _api_key(device: Device) -> Outcome:
    from maptasker.src.core import maputil2

    maputil2._auth_keys.clear()
    code, key = maputil2.get_android_auth_key(device.address, device.port)
    return Outcome(PASS if code == 0 else FAIL, "got a key" if code == 0 else str(key))


def _file_route(device: Device) -> Outcome:
    from maptasker.src.core.maputil2 import http_request

    code, response = http_request(device.address, device.port, "/Tasker", "file", "")
    if code in (0, 6):
        return Outcome(PASS, "the 'file' route answered")
    return Outcome(FAIL, str(response))


def _server_project(device: Device) -> Outcome:
    from maptasker.src.core.maputil2 import auth_key_for
    from maptasker.src.device import deviceserver

    code, key = auth_key_for(device.address, device.port)
    if code != 0:
        return Outcome(FAIL, str(key))
    installed = deviceserver.server_is_installed(device.address, device.port, key)
    if installed is None:
        return Outcome(FAIL, "Tasker did not answer api/profiles")
    names = ", ".join(deviceserver.SERVER_PROFILES)
    return Outcome(PASS if installed else FAIL, f"Profiles {names} {'are' if installed else 'are not both'} there")


def _lists(device: Device) -> Outcome:
    from maptasker.src.core.maputil2 import LIST_READ_TIMEOUT_SECONDS, auth_key_for, http_request

    code, key = auth_key_for(device.address, device.port)
    if code != 0:
        return Outcome(FAIL, str(key))
    problems, took = [], []
    for endpoint in ("api/profiles", "api/tasks", "api/scenes"):
        # The whole list: the phone goes through its whole configuration, which takes more than the usual five seconds
        # (measured on a real phone: Tasks and Profiles both timed out at five, and Profiles again at thirty).
        started = time.monotonic()
        code, response = http_request(
            device.address, device.port, "", endpoint, "", key, timeout=LIST_READ_TIMEOUT_SECONDS
        )
        took.append(f"{endpoint} {time.monotonic() - started:.1f}s")
        if code != 0:
            problems.append(f"{endpoint}: {response}")
            continue
        try:
            json.loads(response)
        except (ValueError, TypeError):
            problems.append(f"{endpoint}: not JSON")
    return Outcome(FAIL if problems else PASS, "; ".join(problems) or f"listed ({', '.join(took)})")


def _upload_round_trip(device: Device) -> Outcome:
    from maptasker.src.core import maputil2

    content = f"MapTasker device check {datetime.now().isoformat()}\n".encode()
    code, message = maputil2.http_upload_request(device.address, device.port, "Tasker", "maptasker_check.txt", content)
    if code != 0:
        return Outcome(FAIL, f"upload: {message}")
    exists, back = maputil2.read_android_file(device.address, device.port, "/Tasker/maptasker_check.txt")
    code, key = maputil2.auth_key_for(device.address, device.port)
    if code == 0:
        maputil2.http_delete_request(device.address, device.port, "/Tasker/maptasker_check.txt", key)
    if not exists:
        return Outcome(FAIL, "the file was uploaded and could not be read back")
    return Outcome(
        PASS if back == content else FAIL, "read back byte for byte" if back == content else "read back changed"
    )


def _helper_round_trip(device: Device) -> Outcome:
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import devicetask

    code, message, names = devicetask.fetch_tasker_object_names(device.address, device.port, state=PrimeItems)
    if code != 0:
        return Outcome(FAIL, message)
    counts = ", ".join(f"{len(found)} {kind}s" for kind, found in names.items())
    return Outcome(PASS, f"MapTasker's helper Task was installed, run and its answer read: {counts}")


def _import_probe(device: Device) -> Outcome:
    """Import a trivial Task three ways, which separates "this phone will not take an import" from "it will not take
    THESE Tasks", and finds what Tasker refuses a second time: the same name under a new id, or a new name under the
    same id.  Leaves up to three Tasks on the phone, named for the check."""
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device.devicetask import finish_helper_task, new_helper_task
    from maptasker.src.edit import taskedit_save

    # Named for the minute, so a run is never turned away by an earlier run's leftovers.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    first_id = ""
    results = []
    for label, name in (
        ("first", f"{CHECK_NAME} {stamp}"),
        ("same name, new id", f"{CHECK_NAME} {stamp}"),
        ("new name, same id", f"{CHECK_NAME} {stamp} b"),
    ):
        reserved = {first_id} if label == "same name, new id" else None
        built = new_helper_task(name, state=PrimeItems, reserved_ids=reserved)
        if isinstance(built, str):
            return Outcome(FAIL, built)
        edited, add, values = built
        task = add("548t", {"0": "MapTasker device check"}) or finish_helper_task(edited, name, values, PrimeItems)
        if isinstance(task, str):
            return Outcome(FAIL, task)
        if label == "first":
            first_id = task.task_id
        elif label == "new name, same id":
            task.task_id = first_id
            task.task_element.set("sr", f"task{first_id}")
            id_element = task.task_element.find("id")
            if id_element is not None:
                id_element.text = first_id
        code, message = taskedit_save.save_task_to_android(
            task, device.address, device.port, name, via_file=False, state=PrimeItems
        )
        results.append(f"{label}: {'accepted' if code == 0 else message}")
    detail = "; ".join(results) + f".  Tasks named '{CHECK_NAME}...' may be on the phone: delete them in Tasker."
    return Outcome(PASS if results[0].endswith("accepted") else FAIL, detail)


# ##################################################################################
# The asked checks
# ##################################################################################
_SEEN = [
    "Tasker's own import screen came up",
    "Android's 'Open with' list came up, and Tasker is in it",
    "Android's 'Open with' list came up, and Tasker is NOT in it",
    "Tasker itself opened, on its main screen, with no import screen",
    "nothing came up",
]


def _offer(device: Device, xml: bytes, route_name: str, what: str) -> Outcome:
    from maptasker.src.core import maputil2
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import deviceoffer

    route = getattr(deviceoffer, route_name)
    code, message = deviceoffer.offer_to_tasker(
        xml, CHECK_NAME, [], device.address, device.port, wait_for_confirmation=False, route=route, state=PrimeItems
    )
    if code != 0:
        return Outcome(FAIL, message)
    answer = device.ask(f"Look at the phone.  What came up for the {what}?  (Do NOT import it: go back.)", _SEEN)
    # The staged file is MapTasker's, named for the check; take it away again.
    code, key = maputil2.auth_key_for(device.address, device.port)
    if code == 0:
        maputil2.http_delete_request(device.address, device.port, route.staged_file_paths(CHECK_NAME)[1], key)
    if answer < 0:
        return Outcome(SKIP, "no answer given")
    return Outcome(PASS if answer in (0, 1) else FAIL, _SEEN[answer])


def _open_with_profile(device: Device) -> Outcome:
    return _offer(device, _PROFILE_XML, "OPEN_FILE_ROUTE", "Profile")


def _open_with_project(device: Device) -> Outcome:
    return _offer(device, _PROJECT_XML, "OPEN_PROJECT_ROUTE", "Project")


def _send_intent_profile(device: Device) -> Outcome:
    return _offer(device, _PROFILE_XML, "SEND_INTENT_ROUTE", "Profile, sent straight to Tasker")


def _share_link(device: Device) -> Outcome:
    from maptasker.src.core import maputil2
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import deviceserver
    from maptasker.src.device.devicetask import install_task_on_android, run_task_on_android

    code, key = maputil2.auth_key_for(device.address, device.port)
    if code != 0:
        return Outcome(FAIL, str(key))
    name = deviceserver.OPEN_SHARE_TASK_NAME
    code, message = install_task_on_android(
        device.address,
        device.port,
        key,
        name,
        lambda: deviceserver.build_open_share_task(state=PrimeItems),
        state=PrimeItems,
    )
    if code != 0:
        return Outcome(FAIL, message)
    code, message = run_task_on_android(
        device.address, device.port, name, maputil2.held_auth_key(device.address, device.port) or key
    )
    if code != 0:
        return Outcome(FAIL, message)
    answer = device.ask(
        "Look at the phone.  What came up for the Http Server Example's TaskerNet link?  (Do NOT import it.)",
        [
            "Tasker's import page for the project came up",
            "a browser opened on the TaskerNet page",
            "a list of apps to open the link with",
            "nothing came up",
        ],
    )
    if answer < 0:
        return Outcome(SKIP, "no answer given")
    return Outcome(PASS if answer < 3 else FAIL, ["Tasker", "the browser", "an app list", "nothing"][answer])


CHECKS = (
    Check("api-key", "Tasker HTTP API hands out a key", "api/auth answers once the phone's owner allows it", _api_key),
    Check(
        "file-route",
        "Http Server Example's file route answers",
        "'file' needs no key and 404s for a missing file",
        _file_route,
    ),
    Check(
        "server-project",
        "Http Server Example is installed",
        "its 'File System Host' and 'Upload Files' Profiles are in Tasker",
        _server_project,
    ),
    Check(
        "lists",
        "Profiles, Tasks and Scenes are listed",
        "api/profiles, api/tasks and api/scenes answer a JSON array",
        _lists,
    ),
    Check(
        "upload-round-trip",
        "A file can be written, read back and deleted",
        "/upload, 'file' and DELETE api/file agree byte for byte",
        _upload_round_trip,
    ),
    Check(
        "import-probe",
        "Tasker's import takes a trivial Task, and what it refuses the second time",
        "api/import refuses a Task whose NAME Tasker has; a new name under an id it has is taken (measured 2026-11-03)",
        _import_probe,
        needs_backup=True,
        after_failure_of="helper-round-trip",
    ),
    Check(
        "helper-round-trip",
        "A helper Task is installed, run and its answer read",
        "api/import, POST api/tasks and the answer file work together",
        _helper_round_trip,
        needs_backup=True,
    ),
    Check(
        "open-with-profile",
        "'Open with' reaches Tasker for a Profile",
        "an implicit VIEW with no mime type matches Tasker's .prf.xml filter (reasoned 2026-08-30; measured 2026-11-03: it does)",
        _open_with_profile,
        needs_backup=True,
    ),
    Check(
        "open-with-project",
        "'Open with' reaches Tasker for a Project",
        "the same for .prj.xml",
        _open_with_project,
        needs_backup=True,
    ),
    Check(
        "send-intent-profile",
        "An explicit intent reaches Tasker's import screen",
        "a file:// URI in Send Intent is accepted by Tasker (measured 2026-11-03: Tasker opens and shows no import screen)",
        _send_intent_profile,
        needs_backup=True,
    ),
    Check(
        "share-link",
        "The Http Server Example's TaskerNet link opens",
        "Android hands a taskernet.com/shares link to Tasker or a browser (measured 2026-11-03: the browser)",
        _share_link,
        needs_backup=True,
    ),
)


# ##################################################################################
# Running them
# ##################################################################################
def load_backup(path: Path) -> None:
    """Load a Tasker backup, as the helper Tasks are built out of one."""
    from maptasker.src.core.actionc import load_arg_specs
    from maptasker.src.core.colrmode import set_color_mode
    from maptasker.src.core.initparg import ProgramArguments
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.mapgen import taskerd
    from maptasker.src.mapgen.lineout import LineOut

    PrimeItems.program_arguments = ProgramArguments(debug=False, directory=False, pretty=False, gui=False)
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut(state=PrimeItems)
    load_arg_specs(state=PrimeItems)
    with path.open(encoding="utf-8", errors="replace") as opened:
        PrimeItems.file_to_get = opened
        taskerd.get_the_xml_data(state=PrimeItems)


def run_one(device: Device, check: Check) -> dict[str, str]:
    """Run one check and say what it found."""
    if check.needs_backup and not device.has_backup:
        outcome = Outcome(SKIP, "needs --backup")
    else:
        try:
            outcome = check.run(device)
        except Exception as error:  # a check that breaks is a result, not the end of the run
            outcome = Outcome(FAIL, f"{type(error).__name__}: {error}")
    print(f"  {outcome.status.upper():5} {check.id:20} {outcome.detail}")
    return {"id": check.id, "status": outcome.status, "detail": outcome.detail}


def run_checks(device: Device, chosen: list[Check]) -> list[dict[str, str]]:
    """Run these checks, in order, and return what each found.

    A diagnostic that names one of them (after_failure_of) runs right after it, if it failed and the diagnostic was not
    asked for already, so the run says why as well as that.
    """
    results = []
    for check in chosen:
        result = run_one(device, check)
        results.append(result)
        if result["status"] != FAIL:
            continue
        for diagnostic in CHECKS:
            if diagnostic.after_failure_of == check.id and diagnostic not in chosen:
                print(f"  ...{check.id} failed; trying {diagnostic.id} to find out why")
                results.append(run_one(device, diagnostic))
    return results


def ask_at_the_keyboard(question: str, answers: list[str]) -> int:
    """Put a question to whoever is at the keyboard.  Returns the index of the answer, or -1 for none/skip."""
    print(f"\n{question}")
    for number, answer in enumerate(answers, 1):
        print(f"   {number}) {answer}")
    reply = input("   which?  (Enter to skip) ").strip()
    return int(reply) - 1 if reply.isdigit() and 1 <= int(reply) <= len(answers) else -1


def main(argv: list[str] | None = None) -> int:
    """Run the checks asked for; return 1 if any failed."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--ip", help="the phone's IP address")
    parser.add_argument("--port", default="1821", help="the port Tasker's server listens on (default 1821)")
    parser.add_argument("--backup", type=Path, help="a Tasker backup to build the helper Tasks from")
    parser.add_argument("--only", help="comma-separated check ids")
    parser.add_argument("--list", action="store_true", help="say what each check settles, and stop")
    parser.add_argument("--results", type=Path, default=Path("device_check_results.json"), help="where runs are kept")
    options = parser.parse_args(argv)

    if options.list:
        for check in CHECKS:
            notes = (
                "[needs --backup]" if check.needs_backup else "",
                f"[after {check.after_failure_of} fails, or --only]" if check.after_failure_of else "",
            )
            print(
                f"{check.id:20} {check.title}\n{'':20} settles: {check.settles} {' '.join(n for n in notes if n)}".rstrip()
            )
        return 0
    if not options.ip:
        parser.error("--ip is required")

    wanted = set(options.only.split(",")) if options.only else {c.id for c in CHECKS if not c.after_failure_of}
    unknown = wanted - {check.id for check in CHECKS}
    if unknown:
        parser.error(f"no such check: {', '.join(sorted(unknown))}")
    chosen = [check for check in CHECKS if check.id in wanted]

    if options.backup:
        load_backup(options.backup)
    device = Device(options.ip, options.port, ask_at_the_keyboard, has_backup=bool(options.backup))

    print(f"Checking {device.address}:{device.port} -- watch the phone for authorization prompts.\n")
    results = run_checks(device, chosen)

    kept = json.loads(options.results.read_text(encoding="utf-8")) if options.results.exists() else []
    kept.append(
        {
            "when": datetime.now().astimezone().isoformat(timespec="seconds"),
            "device": f"{device.address}:{device.port}",
            "checks": results,
        }
    )
    options.results.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
    failed = [result for result in results if result["status"] == FAIL]
    print(f"\n{len(results) - len(failed)} of {len(results)} did not fail.  Kept in {options.results}.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
