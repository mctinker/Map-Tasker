"""deviceverify: asking the Android device's Tasker what it has -- and waiting for an answer that takes a person.

Tasker's HTTP API reports Profiles, Tasks and Scenes by name.  This is the reading side of every write to the
device: a request's own 200 is not evidence that anything was committed, so each import is confirmed by asking
afterwards (and, for the hand-over to Tasker's own import screen, for as long as it takes someone to pick up
the phone).  Blocking; a caller on the GUI's event loop must hand it to run.io_bound."""

from __future__ import annotations

import json
from urllib.parse import quote

from maptasker.src.devicetask import PROFILES_ENDPOINT, RESULT_POLL_SECONDS, TASKS_ENDPOINT
from maptasker.src.maputil2 import (
    LIST_READ_TIMEOUT_SECONDS,
    auth_key_for,
    device_address,
    http_request,
    spaced_attempts,
    tasker_name_query,
)

# How long to keep asking Tasker whether the import turned up -- times RESULT_POLL_SECONDS,
# so two minutes.  This one is waiting on a person, not on a device: they have to notice the
# screen, read it and tap Import.  Long enough not to give up on someone who put the phone
# down, short enough that a caller that never taps is not left hanging forever.
CONFIRM_POLL_ATTEMPTS = 60
# And five minutes for a Scene, which is not one tap.  Its user has to open the Scenes tab,
# find 'Import One Scene' in a menu, work a file picker and pick the right file -- so the
# two minutes that suit an import screen already in front of them would time out on someone
# who is doing exactly what they were asked to do, and say the import had not happened.
MANUAL_IMPORT_POLL_ATTEMPTS = 150


def verify_names_on_android(
    ip_address: str,
    ip_port: str,
    endpoint: str,
    names: list[str],
    auth_key: str,
) -> set[str] | None:
    """Which of these names Tasker reports at this endpoint, via GET <endpoint>?name=...&name=...
    None if the device could not be asked.

    Serves api/profiles and api/scenes alike: both answer a JSON array of objects with a
    "name", and both document 'name' as repeatable -- so this is one request however many
    names it is given, which matters for a Project, where the list is every Profile the
    Project owns and the answer is wanted repeatedly while someone finds their phone.

    None is not an empty set.  'Could not ask' and 'none of them are there' lead to opposite
    conclusions everywhere this is used.
    """
    names = [name.strip() for name in names if name and name.strip()]
    if not names:
        return set()

    query = "?" + "&".join(f"name={quote(name)}" for name in names)
    return_code, response = http_request(ip_address.strip(), ip_port.strip(), "", endpoint, query, auth_key)
    if return_code != 0:
        return None

    try:
        reported = json.loads(response)
    except (ValueError, TypeError):
        return None
    if not isinstance(reported, list):
        return None

    found = {entry.get("name") for entry in reported if isinstance(entry, dict)}
    return {name for name in names if name in found}


def verify_profiles_on_android(
    ip_address: str,
    ip_port: str,
    profile_names: list[str],
    auth_key: str,
) -> set[str] | None:
    """Which of these Profile names Tasker reports.  The api/profiles form of
    verify_names_on_android, kept because most callers only ever ask about Profiles.
    """
    return verify_names_on_android(ip_address, ip_port, PROFILES_ENDPOINT, profile_names, auth_key)


def verify_profile_on_android(ip_address: str, ip_port: str, profile_name: str, auth_key: str) -> bool:
    """Whether Tasker reports a Profile of this name.

    The single-name form of verify_profiles_on_android, and the Profile counterpart of
    taskedit_save.verify_task_on_android.  It earns its keep for the same reason: a request's own
    200 is not evidence that anything was committed.

    Returns True only on a successful GET that lists the Profile; a request that failed is
    False, i.e. 'not confirmed', never 'confirmed absent'.  Callers that need to tell those
    two apart must use the plural form, which answers None for the second.
    """
    present = verify_profiles_on_android(ip_address, ip_port, [profile_name], auth_key)
    return bool(present) and profile_name in present


def import_is_confirmable(
    ip_address: str,
    ip_port: str,
    names: list[str],
    endpoint: str = PROFILES_ENDPOINT,
) -> bool | None:
    """Whether an import of these Profiles could be told apart from doing nothing.
    True, False, or None if the device could not be asked.

    This is not a gate.  An import is confirmed by asking Tasker what it now has, and that
    question only means something when the answer was 'no' beforehand: a Profile that was
    already there answers 'yes' whether the user tapped Import, tapped Replace, or walked
    away -- Tasker replaces in that case, and a replacement leaves the name, the count and
    the enabled state exactly as they were.  So a caller has to know which case it is in
    before it offers, and report the two differently rather than claim a success it cannot
    see (see userintr_android.import_profile_into_tasker_event).

    An empty list is False, not True: a Project that owns no Profiles gives nothing to ask
    about, and 'no questions asked' must not read as 'confirmed'.

    None is kept apart from False for the same reason it is in verify_profiles_on_android --
    though every caller so far treats them alike, since neither can be confirmed and
    guessing the other way is what turns an unconfirmable import into a reported success.
    """
    names = [name.strip() for name in names if name and name.strip()]
    if not names:
        return False

    return_code, auth_key = auth_key_for(ip_address.strip(), ip_port.strip())
    if return_code != 0:
        return None

    present = verify_names_on_android(ip_address, ip_port, endpoint, names, auth_key)
    if present is None:
        return None
    return not present


def await_import(
    ip_address: str,
    ip_port: str,
    names: list[str],
    subject: str,
    endpoint: str = PROFILES_ENDPOINT,
    auth_key: str = "",
    attempts: int = CONFIRM_POLL_ATTEMPTS,
    staged_at: str = "",
) -> tuple[int, str]:
    """Wait for every one of these Profiles to appear in Tasker, and say whether they did.

    staged_at is where the file is sitting on the device, added to the giving-up message so
    the user can finish the import by hand out of Tasker's own browser.  Worth saying only
    because the file carries the object's own name now -- see _build_offer_routes.

    Phase two of the offer: the import screen is up on the device and this is waiting for
    someone to tap Import.  Returns (0, a sentence) once Tasker reports them all, or (8, a
    message) when the attempts run out.

    ALL of them, not any: a Project import that brought in half its Profiles is not a
    Project import that worked, and reporting the first arrival as success would race the
    device's own writing.  For a Profile import the list is one name and the distinction
    does not arise.

    Running out is NOT an error in the usual sense -- the likeliest cause is that the user
    declined the import, or has not got to their phone yet -- so the message says that
    rather than blaming the device.

    Blocking: it sleeps between polls, the same way poll_for_result does, and a caller on
    the GUI thread must hand it to run.io_bound.
    """
    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    wanted = {name.strip() for name in names if name and name.strip()}

    if not auth_key:
        return_code, auth_key = auth_key_for(ip_address, ip_port)
        if return_code != 0:
            return return_code, auth_key

    for _ in spaced_attempts(attempts, RESULT_POLL_SECONDS):
        present = verify_names_on_android(ip_address, ip_port, endpoint, sorted(wanted), auth_key)
        if present is not None and wanted <= present:
            return 0, f"{subject} is now in Tasker on {device_address(ip_address, ip_port)}."

    waiting = f"  The file is on the device at {staged_at} and can still be imported by hand." if staged_at else ""
    return 8, (
        f"Tasker has not reported {subject}.  The import screen was opened on the device -- it may still "
        f"be waiting to be confirmed, or the import may have been declined.{waiting}"
    )


def fetch_task_names_from_device(ip_address: str, ip_port: str) -> tuple[int, str, list[str]]:
    """Every Task Tasker knows about, by name.  (0, "", names) or (return_code, message, []).

    GET /api/tasks with NO name filter, which is the whole list: the server example's handler
    matches 'name=' out of the request path and, when there is none, sets its working list to
    every Task Tasker reports (act7/act9 of the 'GET Tasks' Task -- read off the sample
    backup, the same way everything else about that server was).  The response is the same
    JSON array of {"name":..., "running":...} that verify_names_on_android reads a filtered
    version of.

    Slow, because the handler looks every Task up one at a time before it answers -- see
    maputil2.LIST_READ_TIMEOUT_SECONDS.  To ask about particular Tasks, task_names_on_device.

    Blocking, like every other call here; a caller on the GUI thread must use run.io_bound.
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'.", []

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key, []

    return_code, response = http_request(
        ip_address,
        ip_port,
        "",
        TASKS_ENDPOINT,
        "",
        auth_key,
        timeout=LIST_READ_TIMEOUT_SECONDS,
    )
    if return_code != 0:
        return return_code, str(response), []

    try:
        reported = json.loads(response)
    except (ValueError, TypeError):
        return 8, "The device's Task list was not readable as JSON.", []
    if not isinstance(reported, list):
        return 8, "The device's Task list was not the list of Tasks it should be.", []

    return 0, "", [entry.get("name", "") for entry in reported if isinstance(entry, dict)]


def task_names_on_device(ip_address: str, ip_port: str, names: list[str]) -> tuple[int, str, list[str]]:
    """Which of these Task names Tasker has.  (0, "", names_found) or (return_code, message, []).

    One GET api/tasks?name=...&name=..., which the handler answers from just those Tasks, in a
    fraction of a second.  Only when a name cannot go in the filter (see
    maputil2.tasker_name_query) does it read the whole list instead, which takes seconds.
    """
    names = [name for name in names if name]
    query = tasker_name_query(names) if names else ""
    if query is None:
        return fetch_task_names_from_device(ip_address, ip_port)
    if not names:
        return 0, "", []

    return_code, auth_key = auth_key_for(ip_address.strip(), ip_port.strip())
    if return_code != 0:
        return return_code, auth_key, []

    return_code, response = http_request(ip_address.strip(), ip_port.strip(), "", TASKS_ENDPOINT, query, auth_key)
    if return_code != 0:
        return return_code, str(response), []

    try:
        reported = json.loads(response)
    except (ValueError, TypeError):
        return 8, "The device's Task list was not readable as JSON.", []
    if not isinstance(reported, list):
        return 8, "The device's Task list was not the list of Tasks it should be.", []

    return 0, "", [entry.get("name", "") for entry in reported if isinstance(entry, dict)]
