"""deviceoffer: offering a Profile, Project, Scene or Task to Tasker's own import screen."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.core import maputil2
from maptasker.src.core.maputil2 import (
    auth_key_for,
    device_address,
    held_auth_key,
    http_delete_request,
    request_with_auth_key,
)
from maptasker.src.core.sysconst import logger
from maptasker.src.device.devicetask import (
    PAYLOAD_TERMINATOR,
    PROFILE_STAGE_LOCATION,
    PROFILES_ENDPOINT,
    SCENES_ENDPOINT,
    STAGE_PATH_PARAMETER,
    TASKS_ENDPOINT,
    WRITE_FILE_ACTION,
    finish_helper_task,
    install_task_on_android,
    new_helper_task,
    poll_for_result,
    run_task_on_android,
    staged_paths,
)
from maptasker.src.device.deviceverify import CONFIRM_POLL_ATTEMPTS, await_import, verify_names_on_android

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit.taskedit_model import EditableTask

# ==========================================
# Offering a Profile or a Project to Tasker's own import screen
# ==========================================
#
# The staged file is handed to Android, which gives it to whatever registered for Tasker's file
# types -- Tasker's ordinary import screen, the one that comes up when a .prf.xml or a
# .prj.xml is opened from a file manager.  The user taps Import.
#
# CONFIRMED ON A REAL DEVICE (2026-08-27) for a Profile: the screen came up, the Profile
# imported, and Tasker offered to REPLACE a Profile it already had rather than adding a
# second.  That last part is why nothing here refuses a duplicate -- Tasker asks better than
# this could.
#
# WHY THERE IS NO HEADLESS IMPORT
#
# Handing the XML to Tasker's Import Data action would need no tap, but what its
# 'Configuration' type does to the REST of the configuration was never established, and the
# bad answer is unrecoverable.  An import screen that takes one tap on the device uses
# Tasker's own documented import, with nothing else in the configuration at stake -- and that
# is what the GUI is built on: see userintr_android.import_profile_into_tasker_event and
# import_project_into_tasker_event.
#
# WHAT THE ANSWER FILE PROVES, WHICH IS LESS THAN THE OTHER ROUTE'S
#
# 'Open File' fires an intent and returns; it does not wait for the person to decide.  So
# the Write Files after it run immediately, and the terminator means *the import screen was
# asked for*, not that anything was imported.  That is why this is two phases: the run is
# confirmed by the payload, and the import is confirmed separately by asking Tasker what it
# now has (await_import), for as long as it takes someone to pick up the phone.
#
# CONFIRMING A PROJECT, WHICH THE HTTP API CANNOT DO DIRECTLY
#
# There is no /api/projects.  Tasker's HTTP API can report Profiles, Tasks, Scenes and
# Globals by name, and that is the whole list -- so 'is this Project there now' is not a
# question that can be asked.
#
# What can be asked is whether the Profiles the Project OWNS are there, and a Project import
# brings its Profiles with it (projedit.render_standalone_project_xml bundles them).  So
# both kinds confirm the same way, through one list of Profile names: one name for a Profile
# import, its <pids> resolved to names for a Project import.  A Project with no Profiles at
# all has nothing to ask about and is simply unconfirmable, which is reported rather than
# guessed at.
#
# TaskerNet reaches the same screen via taskernet.com/shares/?user=...&id=Profile%3A<name>,
# and is not used: that URL only exists for a share PUBLISHED to Google's TaskerNet, so
# pushing a locally-edited Profile back to the user's own phone would mean publishing it to
# a third party first.  The local file reaches the same screen with nothing leaving the
# machine.  ('Browse URL' would also have been unbuildable here without an Applications
# fetch first -- its Package/App Name argument is category 'App', so
# classify_action_addability refuses it while the inventory is empty.  'Open File' takes a
# path and a mime type and nothing else.)

_OPEN_FILE_ACTION = "102t"  # arg0 File, arg1 Mime Type
# The OPEN WITH route deliberately carries NO mime type.  This is the one that matters, and it
# is reasoned rather than measured, so here is the reasoning in full.
#
# 'Open File' fires an implicit ACTION_VIEW, which is what produces Android's "Open with..."
# chooser -- the same list a file manager puts up when you long-press a file.  It used to
# send 'text/xml', on the argument that with no mime type Android has only the extension to
# go on and neither '.prf.xml' nor '.prj.xml' is one it knows.  That argument is about
# Android INFERRING a type, and inferring one is not what has to happen here.  What has to
# happen is Tasker's own intent-filter matching.
#
# An app that claims a file extension writes a filter with a scheme and a pathPattern
# ('.*\\.prf\\.xml') and NO android:mimeType.  Android's rule for those is unforgiving: a
# filter that declares no mimeType matches only an intent that carries no type.  So an
# ACTION_VIEW carrying 'text/xml' cannot match it, however right the path is -- and it is
# then matched only against filters that DO declare a type, which is every text/xml viewer on
# the device.  That is exactly what was seen on 2026-08-28: a chooser of seven apps with
# Tasker not among them.  Seven text/xml handlers is what asking for text/xml gets.
#
# Sending no type puts the extension filters back in the running, which is where Tasker is.
# It cannot be confirmed from here -- Tasker's manifest is not in this repo and the only
# proof is a device -- so if the chooser still comes up without Tasker in it, this is the
# line that was wrong, and the file is in Tasker's own folder under its own name to be
# imported by hand either way.  tools/device_check.py open-with-profile and open-with-project are that proof: they
# do the offer on a real phone and ask what came up.
#
# MEASURED 2026-11-03 for a PROJECT (open-with-project, a real phone): Android's "Open with" list came up, with Tasker
# in it, so the no-mime-type reasoning held.  The Profile check could not be run that day: the helper Task's import was
# refused with a 400 (see devicetask.install_task_on_android).
_OPEN_WITH_MIME_TYPE = ""
_OPEN_PAYLOAD_OFFERED = "OFFERED"
# Firing an intent is immediate; this is a timeout on the device answering at all.
_OPEN_POLL_ATTEMPTS = 15

# --- WHY THERE IS NO 'SEND INTENT' ROUTE -------------------------------------------------
#
# There used to be a second route beside 'Open File': a Send Intent, ACTION_VIEW addressed outright at Tasker's own
# activity (package AND class, so Android delivers it without matching any intent-filter), for a device where the
# implicit "Open with..." does not land on Tasker.  It is gone because it was measured not to do the job:
#
#   * 2026-08-28, a '.scn.xml': 'Open File' brought up a chooser with no Tasker in it, so the explicit intent was
#     built for Scenes.  It reached Tasker, and Tasker did nothing with the file.
#   * 2026-11-03 (tools/device_check.py, a real phone), a '.prf.xml': Tasker opened on its default Project ('Base')
#     and showed no import screen and no chooser.  The same result.  The intent arrives; Tasker does nothing with
#     the file.  Why is not established -- the Data field can only be a 'file://' URI from here, which Android 7 and
#     later refuses to let an app put in an outgoing intent, and 'Open File' hands out 'content://' URIs from Tasker's
#     own FileProvider instead -- but the result does not depend on the reason.
#
# So it never imported anything, and a fallback that opens Tasker on the wrong screen is worse than the message the
# user gets instead: the staged file is in Tasker's own folder under its own name, with the steps to import it by hand.
# Nothing here reaches Tasker explicitly any more.  (The taskernet link in deviceserver is a different Send Intent,
# with no file in it, and does work.)
# Where MapTasker's own bookkeeping goes -- the answer files every helper Task writes, and
# nothing else.  Not a staging folder: the file being imported goes in Tasker's own folder
# for its kind (below), and a '.txt' of ours dropped among the user's Profiles would be
# litter in a place they browse.
_BOOKKEEPING_LOCATION = "Tasker"
# Where each kind's XML is staged for Tasker to be handed.  Tasker's own folders, not a
# scratch corner of /Tasker: the user goes looking there for the file that is being imported
# -- reported, for a Profile that was nowhere to be found in /Tasker/profiles -- and if the
# handoff fails (an Android that will not resolve the file to Tasker, which is now measured
# on a real device) that folder is where Tasker's own import browses.  The same strings
# profedit.ANDROID_PROFILE_LOCATION, projedit.ANDROID_PROJECT_LOCATION and
# sceneedit.ANDROID_SCENE_LOCATION use for the file-write button, held together by a test
# rather than by an import, since those modules import from this one's callers.
#
# The Profile folder is PROFILE_STAGE_LOCATION, defined up in the Import Data section
# because that route stages into it too -- one folder per kind across BOTH routes, so a
# Profile on its way into Tasker is in the same place whichever way it was sent.
_PROJECT_STAGE_LOCATION = "Tasker/projects"
# Tasker's own Scene folder, the one its 'Scenes > Import One Scene' browses, and its Task
# folder, the one the Task import leaves its copy in.  Both are staging locations now that
# all four kinds go through the same offer -- and both are the same strings
# sceneedit.ANDROID_SCENE_LOCATION and taskedit_save.ANDROID_TASK_LOCATION use for the file-write
# buttons, held to them by a test rather than by an import for the reason above.
_SCENE_LOCATION = "Tasker/scenes"
_TASK_STAGE_LOCATION = "Tasker/tasks"


def _add_result_writes(
    add: Callable[[str, dict[str, str]], str],
    write_path: str,
    header: str,
    stage_path: str,
) -> str:
    """The four 'Write File' actions every offer Task ends with.  Returns "" or an error.

    The first write truncates and the rest append, so a re-run replaces the previous answer
    rather than growing it -- and the terminator lands last, which is what makes
    poll_for_result's completeness check mean anything.

    Note what these are worth on this route, which is less than in build_import_profile_task:
    the action before them does not block on the user's decision, so they run whether or not
    anything is ever imported.  They confirm the Task ran and the intent went out.  Whether
    an import arrived is await_import's question, not this file's.
    """
    for index, text in enumerate((header, _OPEN_PAYLOAD_OFFERED, stage_path, PAYLOAD_TERMINATOR)):
        error = add(
            WRITE_FILE_ACTION,
            {"0": write_path, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        if error:
            return error
    return ""


def build_open_file_task(
    task_name: str,
    stage_path: str = STAGE_PATH_PARAMETER,
    result_write_path: str = "",
    header: str = "",
    mime_type: str = _OPEN_WITH_MIME_TYPE,
    *,
    state: RunState,
) -> EditableTask | str:
    """Build the Task that puts Android's "Open with..." chooser up for the staged file.

    'Open File' on the staged path, then the four writes that say it ran.

    THIS IS THE "OPEN WITH..." ROUTE, and it is the one the GUI uses.  An implicit
    ACTION_VIEW is exactly what a file manager fires when you long-press a file and pick
    'Open with' -- Android puts up the chooser, the user picks Tasker, and Tasker's ordinary
    import screen comes up on a file it was handed the way it expects to be handed one.
    Nothing here decides what handles it, which is the point: the alternative is guessing
    what Android will resolve to and being wrong silently (see _OPEN_WITH_MIME_TYPE for why this
    sends no mime type at all).

    The staged path defaults to %par1 -- handed over with the run rather than baked in at
    install time.  It used to be baked in, on the belief that 'POST /api/tasks carries a
    Task name and nothing else'; it carries whatever the body carries, and the HTTP Server
    Example's own handler unpacks par1 into %par1 (see run_task_on_android for where that is
    read off).  That is what lets one installed Task open a file named after the Profile it
    belongs to, instead of every import sharing one filename.
    """
    built = new_helper_task(task_name, state=state)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(_OPEN_FILE_ACTION, {"0": stage_path, "1": mime_type}) or _add_result_writes(
        add,
        result_write_path,
        header,
        stage_path,
    )
    if error:
        return error
    return finish_helper_task(edited_task, task_name, values, state)


@dataclass(frozen=True)
class OfferRoute:
    """How one kind of thing (a Profile, Project, Scene or Task) is put in front of Tasker's import screen.

    WHAT is being imported decides the staged file's extension -- which is what tells Tasker what it is looking at.
    Every kind is otherwise identical, so they are data handed to one orchestrator rather than four copies of it.

    Separate answer files and headers per kind are not incidental: reading one kind's payload as another's has to
    be an error rather than a silent misparse, the same reason _FILE_PAYLOAD_HEADER differs from _PAYLOAD_HEADER.

    THE STAGED FILE IS NOT PART OF THE ROUTE, because it is not fixed any more.  It is named
    after the object being imported and worked out per call by staged_file_paths, then handed
    to the helper Task as %par1 at run time -- see run_task_on_android.  A route describes
    how Tasker is asked; the object decides what it is asked about.
    """

    label: str  # "Profile" / "Project" / "Scene" -- how this reads in a message to the user
    confirm_endpoint: str  # where an import of this kind can be asked about afterwards
    task_name: str
    builder: Callable[..., EditableTask | str]  # takes the run state it builds the Task for: builder(state=...)
    stage_location: str
    extension: str  # 'prf.xml' / 'prj.xml' -- what tells Tasker what it is looking at
    read_path: str
    header: str
    # A sentence for a handoff that did not land, with one '{path}' in it for the file it
    # was about.  A template rather than a finished string, since that file is per-object.
    failure_hint: str

    def staged_file_paths(self, object_name: str) -> tuple[str, str, str]:
        """(filename, read path, absolute path) for this object's staged file -- see
        staged_paths, which this is the per-route spelling of."""
        return staged_paths(self.stage_location, object_name, self.extension, self.label.lower())


def _build_offer_route(
    label: str,
    extension: str,
    confirm_endpoint: str,
    stage_location: str,
) -> OfferRoute:
    """The Open File route for one kind of thing, from its name and the extension Tasker recognizes it by.

    A factory rather than four hand-written constants: every field is derived from these arguments, and the way
    a hand-written set goes wrong is one of them not being -- a Project route left pointing at the Profile route's
    answer file would read a stale Profile import as its own success.

    THE STAGED FILE CARRIES THE OBJECT'S OWN NAME, and it did not used to.  It was one fixed
    'maptasker_import.<ext>' per kind, on the reasoning that the path had to be baked into
    the helper Task at install time because 'POST /api/tasks carries a name and nothing
    else'.  That premise was wrong -- the body carries par1, and the Tasker HTTP API's
    own handler unpacks it into %par1 for the Task it runs (read off the sample backup; see
    run_task_on_android).  So one installed Task now serves every object, and the file in
    the folder is the file the user is looking for.

    What that premise cost, and why this is a fix rather than a polish: a Profile sent to the
    device could not be found in /Tasker/profiles under its own name, a second import
    silently overwrote the first one's staged file, and when the handoff to Tasker failed --
    which it does, on a device that will not resolve the file to Tasker -- what was left for
    the user to import by hand was a file called 'maptasker_import.prf.xml' with no way to
    tell which Profile it held.

    stage_location is the folder that file goes in.  The ANSWER file does not follow it --
    those are MapTasker's bookkeeping, and .txt files dropped among the user's Profiles would
    be litter in a place they browse.
    """
    key = label.lower()
    # v4 since 2026-08-30, when the route stopped sending a mime type (see _OPEN_WITH_MIME_TYPE); v3 was the same
    # day, when the staged path stopped being baked in and became %par1.  THE VERSION IN THE NAME IS LOAD-BEARING,
    # and this is what it is for: what the Task opens and what it opens it AS are both part of its body, and
    # install_task_on_android installs only what is not already there -- so a device holding 'MapTasker Open
    # Profile v3' would go on asking for text/xml forever, silently, since that Task runs fine and writes its
    # answer file either way.  A new name is a new Task.
    #
    # ("Open" stays in every name although it is the only verb now: the Tasks already on people's phones are named
    # that, and a new name would mean installing them all again.)
    task_name = f"MapTasker Open {label} v4"
    write_path = f"{_BOOKKEEPING_LOCATION}/maptasker_open_{key}.txt"
    header = f"MAPTASKER-OPEN-{label.upper()} 1"

    def build(state: RunState) -> EditableTask | str:
        # No path handed to the builder: it builds with %par1 and is told the real one when it is run.
        return build_open_file_task(task_name, STAGE_PATH_PARAMETER, write_path, header, state=state)

    return OfferRoute(
        label=label,
        confirm_endpoint=confirm_endpoint,
        task_name=task_name,
        builder=build,
        stage_location=stage_location,
        extension=extension,
        read_path=f"/{write_path}",
        header=header,
        failure_hint="Tasker could not open {path} for import.",
    )


OPEN_FILE_ROUTE = _build_offer_route("Profile", "prf.xml", PROFILES_ENDPOINT, stage_location=PROFILE_STAGE_LOCATION)
# A Project has no endpoint of its own, so it is confirmed through the Profiles it brings --
# see offer_to_tasker's confirm_names.
OPEN_PROJECT_ROUTE = _build_offer_route("Project", "prj.xml", PROFILES_ENDPOINT, stage_location=_PROJECT_STAGE_LOCATION)
# A Scene HAS a route now, and it did not before.  Every way of handing Tasker a '.scn.xml'
# had been tried and measured failing (see the section comment above), so a Scene was merely
# uploaded and Tasker opened, with the import left entirely to the user.  What had not been
# tried is an implicit ACTION_VIEW carrying NO mime type -- the "Open with..." a file manager
# fires -- and that is a different attempt from either of the measured ones: the implicit try
# asked for 'text/xml' and got a chooser of text/xml apps, and the explicit try bypassed
# matching altogether.  See _OPEN_WITH_MIME_TYPE.
#
# It is offered on that reasoning, not on a measurement, and it costs nothing if it is wrong:
# the file is already in /Tasker/scenes under the Scene's own name, and the message still
# tells the user how to import it by hand.  That instruction is what this route used to be.
OPEN_SCENE_ROUTE = _build_offer_route("Scene", "scn.xml", SCENES_ENDPOINT, stage_location=_SCENE_LOCATION)
# And a Task, which reaches Tasker headlessly through api/import and needs none of this --
# taskedit_save.save_task_to_android is the route that works.  This is what is left when that has
# been tried twice and Tasker still does not report the Task: the file is in /Tasker/tasks,
# and the user can be handed the same chooser rather than told it did not work.  See
# userintr's Task import.
OPEN_TASK_ROUTE = _build_offer_route("Task", "tsk.xml", TASKS_ENDPOINT, stage_location=_TASK_STAGE_LOCATION)
# Every route there is, in one place, so anything that has to reason about all of them cannot
# be left behind by a new kind being added -- current_helper_task_names above all, where
# missing one would mean reporting a Task that is in use as dead and inviting the user to
# delete it.
ALL_OFFER_ROUTES = (OPEN_FILE_ROUTE, OPEN_PROJECT_ROUTE, OPEN_SCENE_ROUTE, OPEN_TASK_ROUTE)


def stage_xml(
    ip_address: str,
    ip_port: str,
    xml_bytes: bytes,
    object_name: str,
    route: OfferRoute,
) -> tuple[int, str]:
    """Put the rendered XML where this route's helper Task can reach it, under the object's
    own name.  Returns (0, its absolute path on the device) or (code, message).

    That path is what the caller hands the helper Task as %par1, so it comes back rather than
    being a constant on the route -- see OfferRoute and run_task_on_android.

    NOTHING IS READ FIRST, and that is not an oversight about clobbering.  The staged file is
    the user's own now -- this writes exactly where the 'Save As File' button writes, so an
    import of 'Morning' replaces a 'Morning.prf.xml' they saved by hand -- but the caller has
    already read that path to ask them about it, and it hands the bytes it got to
    presave.save_android_safety_copy itself.  Reading here as well would be a second GET of
    a path just read: another round trip, another chance for the two answers to disagree,
    and another 'File doesn't exist' flash on the phone for one save (see
    maputil2.read_android_file).  One read answers both questions, up there.

    Read back and compared byte for byte, because /upload answers 200 whatever it wrote (see
    maputil2.http_upload_request): it does not validate the location, it creates missing
    folders silently, and it reports nothing at the HTTP layer.  A half-written file would
    not fail loudly here -- it would be handed to Tasker.  save_profile_to_android reads its
    own upload back for exactly this reason.
    """
    filename, read_path, task_path = route.staged_file_paths(object_name)

    return_code, response = maputil2.http_upload_request(ip_address, ip_port, route.stage_location, filename, xml_bytes)
    if return_code != 0:
        return return_code, str(response)

    # Retried rather than trusted -- see maputil2.read_back_uploaded_file for the write that
    # is still settling when this arrives.
    verify_code, verify_content = maputil2.read_back_uploaded_file(ip_address, ip_port, read_path, xml_bytes)
    if verify_code != 0:
        return 8, str(verify_content)
    return 0, task_path


def _offer_input_problem(
    ip_address: str,
    ip_port: str,
    object_name: str,
    xml_bytes: bytes,
    route: OfferRoute,
) -> tuple[int, str] | None:
    """What is wrong with the request itself, as (return code, message), or None if there is nothing."""
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."
    if not object_name:
        return 8, f"A {route.label} name is needed."
    if not xml_bytes:
        return 8, f"There is no {route.label} XML to import."
    return None


def _hand_offer_to_device(
    ip_address: str,
    ip_port: str,
    xml_bytes: bytes,
    object_name: str,
    route: OfferRoute,
    auth_key: str,
) -> tuple[int, str, str]:
    """Stage the XML, run the helper Task that opens Tasker's import screen, and read back its answer.

    Returns (0, the path the file was staged at, the API key now held) once the Task has
    answered the way the route says it should, or (a return code, an error message, the key).
    """
    delete_code, delete_error = http_delete_request(ip_address, ip_port, route.read_path, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {route.read_path} before offering: {delete_error}")

    return_code, message = stage_xml(ip_address, ip_port, xml_bytes, object_name, route)
    if return_code != 0:
        return return_code, message, auth_key
    stage_task_path = message

    # The path goes over WITH the run, as %par1, rather than having been baked into the Task
    # when it was installed -- see run_task_on_android.
    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, route.task_name, auth_key, stage_task_path),
    )
    auth_key = held_auth_key(ip_address, ip_port) or auth_key
    if return_code != 0:
        return return_code, message, auth_key

    text, error = poll_for_result(ip_address, ip_port, route.read_path, _OPEN_POLL_ATTEMPTS, "import result")
    if error:
        return 8, f"{error}  {route.failure_hint.format(path=stage_task_path)}", auth_key
    if not text.splitlines() or text.splitlines()[0].strip() != route.header:
        return 8, "The file the Android device wrote is not a MapTasker import result.", auth_key
    return 0, stage_task_path, auth_key


def _offer_sent_message(subject: str, key: str, landed: str, *, already_there: bool) -> str:
    """What to say once the import screen is open and nothing more is being waited for.

    `already_there` is for an object Tasker already has: it will offer to replace it, and whether
    that was confirmed cannot be seen from here.
    """
    if already_there:
        return (
            f"{subject} was sent to {key} and Tasker's import screen was opened.  Tasker already has what "
            "this would import and will offer to replace it; whether that was confirmed cannot be seen "
            f"from here.{landed}"
        )
    return (
        f"{subject} was sent to {key} and Tasker's import screen was opened.  "
        f"It is not imported until it is confirmed on the device.{landed}"
    )


def _names_to_confirm(
    ip_address: str, ip_port: str, confirm_names: list[str], route: OfferRoute, auth_key: str
) -> tuple[list[str], bool]:
    """The names to wait for, and whether waiting for them can mean anything.

    Asked BEFORE the import, because afterwards the answer is worthless -- see
    import_is_confirmable.  Nothing is gated on it; it only decides what can be said at the end.
    """
    wanted = [name.strip() for name in confirm_names if name and name.strip()]
    present_before = verify_names_on_android(ip_address, ip_port, route.confirm_endpoint, wanted, auth_key)
    return wanted, bool(wanted) and present_before == set()


def _install_and_hand_off(
    ip_address: str,
    ip_port: str,
    xml_bytes: bytes,
    object_name: str,
    route: OfferRoute,
    auth_key: str,
    *,
    state: RunState,
) -> tuple[int, str, str]:
    """Install the route's helper Task if the device lacks it, then hand the XML over: (code, message, API key)."""
    return_code, message = install_task_on_android(
        ip_address, ip_port, auth_key, route.task_name, functools.partial(route.builder, state=state), state=state
    )
    if return_code != 0:
        return return_code, message, auth_key
    auth_key = held_auth_key(ip_address, ip_port) or auth_key
    return _hand_offer_to_device(ip_address, ip_port, xml_bytes, object_name, route, auth_key)


# There is no duplicate check.  It puts nothing at stake but the one Profile or Project: Android is
# handed a file, Tasker shows the user what it is about to import -- including, measured
# on a real device, an offer to replace something it already has -- and the semantics from
# there are Tasker's own documented ones.  Refusing a name Tasker already knows would only
# put a worse prompt in front of a better one.
def offer_to_tasker(
    xml_bytes: bytes,
    object_name: str,
    confirm_names: list[str],
    ip_address: str,
    ip_port: str,
    wait_for_confirmation: bool = True,
    route: OfferRoute = OPEN_FILE_ROUTE,
    *,
    state: RunState,
) -> tuple[int, str]:
    """Offer a Profile, a Project or a Scene to Tasker's own import screen on the device.

    Args:
        xml_bytes: the standalone XML -- profedit.render_standalone_profile_xml or
            projedit.render_standalone_project_xml, encoded UTF-8, i.e. exactly what the
            file-writing Save To Android uploads today.
        object_name: what it is called, for the messages.
        confirm_names: the names an import of this would put in Tasker, asked about at the
            route's own confirm_endpoint -- its own name for a Profile or a Scene, and for a
            Project every Profile it owns, since there is no /api/projects to ask about the
            Project itself.  See the section comment.
        wait_for_confirmation: keep asking Tasker whether they turned up, for about two
            minutes (await_import).  False returns as soon as the screen has been asked for,
            which is what a GUI wanting to poll on its own should pass -- the return message
            then says the import is still pending, and must not be shown as a completed
            save.  True skips the wait when it could not mean anything and says so instead:
            see import_is_confirmable.
        route: which kind, and how the screen is asked for.  OPEN_FILE_ROUTE,
            OPEN_PROJECT_ROUTE, OPEN_SCENE_ROUTE or OPEN_TASK_ROUTE; each lets Android find the handler.

    (See the comment above this function for the rest.)

    The exchange: get an API key, install the helper Task if it isn't there, clear the last
    answer, stage the XML, run the Task, confirm it ran, and then -- if asked, and if the
    answer would mean anything -- wait for the import to appear.  Returns (0, a sentence
    saying what happened and what the user still has to do) or (return_code, an error
    message).

    Requires the Tasker HTTP API and Http Server Example projects running on the device and
    Tasker 6.2 or higher.  Blocking, deliberately; a caller on the GUI thread must use run.io_bound.
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    object_name = object_name.strip()
    if problem := _offer_input_problem(ip_address, ip_port, object_name, xml_bytes, route):
        return problem

    subject = f"{route.label} '{object_name}'"
    key = device_address(ip_address, ip_port)
    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    wanted, confirmable = _names_to_confirm(ip_address, ip_port, confirm_names, route, auth_key)

    return_code, message, auth_key = _install_and_hand_off(
        ip_address, ip_port, xml_bytes, object_name, route, auth_key, state=state
    )
    if return_code != 0:
        return return_code, message
    stage_task_path = message
    # Where the file actually is, said in every message from here on.  A handoff that fails
    # leaves the user to import it themselves out of Tasker's own browser, and that is only
    # possible if they are told which file -- the whole reason it carries the object's name.
    landed = f"  It is on the device at {stage_task_path}."

    if not wait_for_confirmation:
        return 0, _offer_sent_message(subject, key, landed, already_there=False)

    # Waiting for something that is already there would 'confirm' the import the instant it
    # was asked, whatever the user goes on to tap -- including Cancel.  So it is not asked.
    if not confirmable:
        return 0, _offer_sent_message(subject, key, landed, already_there=True)

    return await_import(
        ip_address,
        ip_port,
        wanted,
        subject,
        route.confirm_endpoint,
        auth_key,
        CONFIRM_POLL_ATTEMPTS,
        stage_task_path,
    )
