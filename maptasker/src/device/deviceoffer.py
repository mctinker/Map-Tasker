"""deviceoffer: offering a Profile, Project, Scene or Task to Tasker's own import screen, and opening Tasker."""

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
# The Import Data route above hands the XML to Tasker headlessly, and is unproven.  This one
# hands the staged file to Android, which gives it to whatever registered for Tasker's file
# types -- Tasker's ordinary import screen, the one that comes up when a .prf.xml or a
# .prj.xml is opened from a file manager.  The user taps Import.
#
# CONFIRMED ON A REAL DEVICE (2026-08-27) for a Profile: the screen came up, the Profile
# imported, and Tasker offered to REPLACE a Profile it already had rather than adding a
# second.  That last part is why nothing here refuses a duplicate -- Tasker asks better than
# this could.
#
# WHY BOTH ROUTES EXIST
#
#   Import Data     headless -- but what 'Configuration' does to the REST of the
#                   configuration is not established, and the bad answer is unrecoverable.
#   Open File       one tap on the device -- but the semantics are Tasker's own documented
#                   import.  Nothing else in the configuration is at stake, so there is no
#                   acknowledged_risk gate on this one.
#
# So this is the one to reach for, and the one the GUI is built on -- see
# userintr_android.import_profile_into_tasker_event and import_project_into_tasker_event.
# SEND_INTENT_* stays as the fallback for a device where implicit resolution does not land
# on Tasker, not as a second candidate still being chosen between.
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
_SEND_INTENT_ACTION = "877t"  # arg0 Action, arg1 Cat, arg2 Mime Type, arg3 Data,
#                               arg4-6 Extra, arg7 Package, arg8 Class, arg9 Target
# The mime type an explicit Send Intent carries.  It has a named component to be delivered
# to, so the type is not doing any matching -- it is what the receiver reads to know what it
# was handed.
_SEND_INTENT_MIME_TYPE = "text/xml"
# ...and the OPEN WITH route deliberately carries NONE.  This is the one that matters, and it
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
# imported by hand either way.
_OPEN_WITH_MIME_TYPE = ""
_OPEN_PAYLOAD_OFFERED = "OFFERED"
# Firing an intent is immediate; this is a timeout on the device answering at all.
_OPEN_POLL_ATTEMPTS = 15

# --- 'Send Intent', for when implicit resolution does not find Tasker -------------------
#
# 'Open File' asks Android to find something that handles the file, and trusts it to land on
# Tasker.  If it does not -- nothing registered for 'text/xml', or a chooser comes up and
# Tasker is not in it -- this says where to send it instead: ACTION_VIEW at Tasker's own
# activity, explicitly.
#
# MEASURED, 2026-08-28, and the reason this route is no longer only a fallback: a '.scn.xml'
# offered through 'Open File' brings up a chooser with no Tasker in it, while the identical
# offer of a '.prf.xml' lands on Tasker's import screen.  Same mime type, same action, same
# staged directory -- so what Tasker matches on is the EXTENSION in its manifest, and it
# claims Profile, Project and Task files but not Scene files.  No mime type fixes that; a
# Scene has to be addressed rather than advertised.
#
# NAMING THE PACKAGE IS NOT ENOUGH TO ADDRESS IT.  An intent with a package but no class is
# still resolved against that package's intent-filters -- exactly the matching that just
# failed -- so a Scene sent that way would fail the same way, silently.  Naming the class
# (arg8) makes the intent EXPLICIT, and an explicit intent skips filter matching altogether
# and is delivered to that activity whatever its manifest claims.
#
# The shape is not invented.  Every ACTION_VIEW 'Send Intent' in this repo's real backups
# uses Cat=None and Target=Activity, and the ones aimed at a particular app name it in
# Package (arg7) -- e.g. 'google.navigation:q=%address' at com.google.android.apps.maps.
#
# THE ONE WAY THIS CAN FAIL THAT 'Open File' CANNOT: the Data field has to be a URI, and the
# only URI available from here is 'file://'.  Since Android 7 an app that puts a file:// URI
# into an outgoing intent gets a FileUriExposedException -- which is precisely what 'Open
# File' exists to avoid, since it can hand out a content:// URI from Tasker's own
# FileProvider and this cannot.  Whether Tasker's 'Send Intent' converts it or passes it
# straight through is not established here.
_VIEW_ACTION = "android.intent.action.VIEW"
# Both dropdowns by the label apply_arg_values matches on -- see actiont.lookup_values
# ["877"] and ["877a"], and the real backups above, which agree on both.
_INTENT_CATEGORY_NONE = "None"
_INTENT_TARGET_ACTIVITY = "Activity"
_TASKER_PACKAGE = "net.dinglisch.android.taskerm"
# Tasker's main activity, and the component an explicit ACTION_VIEW is delivered to.  Not
# guessed: Tasker writes this class itself, in the two places a backup records a component
# -- an <Img> naming Tasker's own launcher icon (<cls> beside <pkg>), and an Application
# event's <appClass> beside its <appPkg>.  It is the launcher activity, so it is exported
# and an outside intent can start it; it is also what an implicitly-resolved '.prf.xml'
# reaches today, so a Scene sent here arrives where a working Profile import arrives.
_TASKER_MAIN_ACTIVITY = "net.dinglisch.android.taskerm.Tasker"
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
    what Android will resolve to and being wrong silently (see build_send_intent_task, and
    _OPEN_WITH_MIME_TYPE for why this sends no mime type at all).

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


def build_send_intent_task(
    task_name: str,
    stage_path: str = STAGE_PATH_PARAMETER,
    result_write_path: str = "",
    header: str = "",
    mime_type: str = _SEND_INTENT_MIME_TYPE,
    package: str = _TASKER_PACKAGE,
    activity_class: str = _TASKER_MAIN_ACTIVITY,
    *,
    state: RunState,
) -> EditableTask | str:
    """Build the Task that sends Tasker an explicit ACTION_VIEW for the staged file.

    The same job build_open_file_task does, addressed rather than broadcast -- see the
    section comment above for when that matters and for the file:// caveat that comes with
    it, and build_open_file_task for why the path is %par1 rather than a literal.  Its
    answer file means exactly what that one's does.

    Package AND class, not package alone: with only a package this is still matched against
    Tasker's intent-filters, which is the matching that fails for a Scene.  Both together
    make it an explicit component intent, which is delivered without matching anything --
    the whole reason this route can reach Tasker where 'Open File' cannot.
    """
    built = new_helper_task(task_name, state=state)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(
        _SEND_INTENT_ACTION,
        {
            "0": _VIEW_ACTION,
            "1": _INTENT_CATEGORY_NONE,
            "2": mime_type,
            "3": f"file://{stage_path}",
            "7": package,
            "8": activity_class,
            "9": _INTENT_TARGET_ACTIVITY,
        },
    ) or _add_result_writes(add, result_write_path, header, stage_path)
    if error:
        return error
    return finish_helper_task(edited_task, task_name, values, state)


@dataclass(frozen=True)
class OfferRoute:
    """One way of putting one kind of thing in front of Tasker's import screen.

    Two dimensions, and they multiply: WHAT is being imported (a Profile, a Project) decides
    the staged file's extension -- which is what tells Tasker what it is looking at -- and
    HOW the screen is opened (Open File, Send Intent) decides the action in the helper Task.
    Every combination is otherwise identical, so they are data handed to one orchestrator
    rather than four copies of it.

    Separate answer files and headers per combination are not incidental: reading one
    route's payload as another's has to be an error rather than a silent misparse, the same
    reason _FILE_PAYLOAD_HEADER differs from _PAYLOAD_HEADER.

    THE STAGED FILE IS NOT PART OF THE ROUTE, because it is not fixed any more.  It is named
    after the object being imported and worked out per call by staged_file_paths, then handed
    to the helper Task as %par1 at run time -- see run_task_on_android.  A route describes
    how Tasker is asked; the object decides what it is asked about.
    """

    label: str  # "Profile" / "Project" / "Scene" -- how this reads in a message to the user
    confirm_endpoint: str  # where an import of this kind can be asked about afterwards
    task_name: str
    builder: Callable[..., object]  # takes the run state it builds the Task for: builder(state=...)
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


def _build_offer_routes(
    label: str,
    extension: str,
    confirm_endpoint: str,
    stage_location: str,
) -> tuple[OfferRoute, OfferRoute]:
    """The Open File and Send Intent routes for one kind of thing, from its name and the
    extension Tasker recognizes it by.

    A factory rather than eight hand-written constants: every one of those fields is derived
    from these arguments, and the way a hand-written set goes wrong is one of them not being
    -- a Project route left pointing at the Profile route's answer file would read a stale
    Profile import as its own success.

    ONLY A PROFILE AND A PROJECT, which is not an oversight: a Scene cannot be handed to
    Tasker by intent at all (measured four ways -- see the section comment above), so it
    does not go through here.  userintr_android.import_scene_into_tasker_event uploads it under its
    own name and opens Tasker instead.

    THE STAGED FILE CARRIES THE OBJECT'S OWN NAME, and it did not used to.  It was one fixed
    'maptasker_import.<ext>' per kind, on the reasoning that the path had to be baked into
    the helper Task at install time because 'POST /api/tasks carries a name and nothing
    else'.  That premise was wrong -- the body carries par1, and the HTTP Server Example's
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

    def route(verb: str, builder: Callable[..., object], hint: str) -> OfferRoute:
        # v4 since 2026-08-30, when the Open route stopped sending a mime type (see
        # _OPEN_WITH_MIME_TYPE); v3 was the same day, when the staged path stopped being
        # baked in and became %par1.  THE VERSION IN THE NAME IS LOAD-BEARING, and this is
        # what it is for: what the Task opens and what it opens it AS are both part of its
        # body, and install_task_on_android installs only what is not already there -- so a
        # device holding 'MapTasker Open Profile v3' would go on asking for text/xml forever,
        # silently, since that Task runs fine and writes its answer file either way.  A new
        # name is a new Task.
        task_name = f"MapTasker {verb} {label} v4"
        write_path = f"{_BOOKKEEPING_LOCATION}/maptasker_{verb.lower()}_{key}.txt"
        header = f"MAPTASKER-{verb.upper()}-{label.upper()} 1"
        return OfferRoute(
            label=label,
            confirm_endpoint=confirm_endpoint,
            task_name=task_name,
            # No path handed to the builder: it builds with %par1 and is told the real one
            # when it is run.
            builder=lambda state: builder(task_name, STAGE_PATH_PARAMETER, write_path, header, state=state),
            stage_location=stage_location,
            extension=extension,
            read_path=f"/{write_path}",
            header=header,
            failure_hint=hint,
        )

    return (
        route("Open", build_open_file_task, "Tasker could not open {path} for import."),
        route(
            "Send",
            build_send_intent_task,
            "Tasker refused an ACTION_VIEW for file://{path}.  A file:// URI in an outgoing "
            "intent is rejected on Android 7 and later; try the Open File route instead.",
        ),
    )


OPEN_FILE_ROUTE, SEND_INTENT_ROUTE = _build_offer_routes(
    "Profile", "prf.xml", PROFILES_ENDPOINT, stage_location=PROFILE_STAGE_LOCATION
)
# A Project has no endpoint of its own, so it is confirmed through the Profiles it brings --
# see open_project_on_device.
OPEN_PROJECT_ROUTE, SEND_INTENT_PROJECT_ROUTE = _build_offer_routes(
    "Project", "prj.xml", PROFILES_ENDPOINT, stage_location=_PROJECT_STAGE_LOCATION
)
# A Scene HAS routes now, and it did not before.  Every way of handing Tasker a '.scn.xml'
# had been tried and measured failing (see the section comment below), so a Scene was merely
# uploaded and Tasker opened, with the import left entirely to the user.  What had not been
# tried is an implicit ACTION_VIEW carrying NO mime type -- the "Open with..." a file manager
# fires -- and that is a different attempt from either of the measured ones: the implicit try
# asked for 'text/xml' and got a chooser of text/xml apps, and the explicit try bypassed
# matching altogether.  See _OPEN_WITH_MIME_TYPE.
#
# It is offered on that reasoning, not on a measurement, and it costs nothing if it is wrong:
# the file is already in /Tasker/scenes under the Scene's own name, and the message still
# tells the user how to import it by hand.  That instruction is what this route used to be.
OPEN_SCENE_ROUTE, SEND_INTENT_SCENE_ROUTE = _build_offer_routes(
    "Scene", "scn.xml", SCENES_ENDPOINT, stage_location=_SCENE_LOCATION
)
# And a Task, which reaches Tasker headlessly through api/import and needs none of this --
# taskedit_save.save_task_to_android is the route that works.  This is what is left when that has
# been tried twice and Tasker still does not report the Task: the file is in /Tasker/tasks,
# and the user can be handed the same chooser rather than told it did not work.  See
# userintr's Task import.
OPEN_TASK_ROUTE, SEND_INTENT_TASK_ROUTE = _build_offer_routes(
    "Task", "tsk.xml", TASKS_ENDPOINT, stage_location=_TASK_STAGE_LOCATION
)
# Every route there is, in one place, so anything that has to reason about all of them cannot
# be left behind by a new kind being added -- current_helper_task_names above all, where
# missing one would mean reporting a Task that is in use as dead and inviting the user to
# delete it.
ALL_OFFER_ROUTES = (
    OPEN_FILE_ROUTE,
    SEND_INTENT_ROUTE,
    OPEN_PROJECT_ROUTE,
    SEND_INTENT_PROJECT_ROUTE,
    OPEN_SCENE_ROUTE,
    SEND_INTENT_SCENE_ROUTE,
    OPEN_TASK_ROUTE,
    SEND_INTENT_TASK_ROUTE,
)


# --- Bringing Tasker up, with nothing handed to it ---------------------------------------
#
# MEASURED, 2026-08-28: with a Scene staged in /Tasker/scenes and an explicit ACTION_VIEW at
# Tasker's own activity, Tasker comes up, makes a visible attempt at an import, and imports
# nothing.  The same file, picked by hand through Tasker's 'Scenes > Import One Scene',
# imports correctly -- so the XML is right and it is the HANDOFF that Tasker will not
# complete.  For a while that was read as ending the intent story for Scenes, and this was
# what a Scene got instead: Tasker merely opened, the import left entirely to the user.
#
# It is no longer what the GUI does.  What those measurements did NOT try is an implicit VIEW
# carrying no mime type at all -- Android's "Open with..." -- and a Scene goes through that
# now like every other kind (see OPEN_SCENE_ROUTE and _OPEN_WITH_MIME_TYPE).  This is kept
# because it still works and still might be wanted: it is the one thing that can be done for
# a device where nothing can be handed over at all, and deleting a tested capability on the
# strength of a reasoned improvement would be the wrong way round.
#
# ACTION_MAIN rather than ACTION_VIEW: there is no file to hand over any more, and a VIEW
# with no data is not a launch.  MAIN at an explicit component is what launching an app IS.
_MAIN_ACTION = "android.intent.action.MAIN"
LAUNCH_TASKER_TASK_NAME = "MapTasker Open Tasker v1"
_LAUNCH_WRITE_PATH = "Tasker/maptasker_launch_tasker.txt"
_LAUNCH_READ_PATH = f"/{_LAUNCH_WRITE_PATH}"
_LAUNCH_HEADER = "MAPTASKER-LAUNCH-TASKER 1"


def build_launch_tasker_task(task_name: str = LAUNCH_TASKER_TASK_NAME, *, state: RunState) -> EditableTask | str:
    """Build the Task that brings Tasker to the foreground.  Returns an EditableTask, or an
    error message string, like every other builder here.

    'Send Intent' again, so this needs no application inventory -- 'Launch App' takes an
    App-category argument, and taskedit_addable.classify_action_addability refuses those while the
    inventory is empty, which it is on a machine that has never fetched one.
    """
    built = new_helper_task(task_name, state=state)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(
        _SEND_INTENT_ACTION,
        {
            "0": _MAIN_ACTION,
            "1": _INTENT_CATEGORY_NONE,
            "7": _TASKER_PACKAGE,
            "8": _TASKER_MAIN_ACTIVITY,
            "9": _INTENT_TARGET_ACTIVITY,
        },
    ) or _add_result_writes(add, _LAUNCH_WRITE_PATH, _LAUNCH_HEADER, f"/{_SCENE_LOCATION}")
    if error:
        return error
    return finish_helper_task(edited_task, task_name, values, state)


def open_tasker_on_device(ip_address: str, ip_port: str, state: RunState) -> tuple[int, str]:
    """Bring Tasker to the foreground on the device.  (0, "") or (return_code, message).

    NOT CALLED BY THE GUI any more -- see the section comment above.  Every import kind now
    gets Android's "Open with..." chooser instead, which puts Tasker's import screen one tap
    away rather than dropping the user into Tasker with nothing selected.  Kept for a device
    that will not take a handoff at all.

    The same exchange every helper Task goes through -- key, install if absent, clear the
    last answer, run, wait for the answer file -- with nothing handed over and nothing to
    confirm afterwards.  Whether Tasker is in front of the user is not a thing the HTTP API
    can be asked; the answer file says only that the Task ran and the intent went out.

    Blocking, like everything else here: a caller on the GUI thread must use run.io_bound.
    """

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    return_code, message = install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        LAUNCH_TASKER_TASK_NAME,
        functools.partial(build_launch_tasker_task, state=state),
        state=state,
    )
    if return_code != 0:
        return return_code, message
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    delete_code, delete_error = http_delete_request(ip_address, ip_port, _LAUNCH_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_LAUNCH_READ_PATH} before opening Tasker: {delete_error}")

    return_code, message = request_with_auth_key(
        ip_address,
        ip_port,
        lambda auth_key: run_task_on_android(ip_address, ip_port, LAUNCH_TASKER_TASK_NAME, auth_key),
    )
    if return_code != 0:
        return return_code, message

    text, error = poll_for_result(ip_address, ip_port, _LAUNCH_READ_PATH, _OPEN_POLL_ATTEMPTS, "launch result")
    if error:
        return 8, error
    if not text.splitlines() or text.splitlines()[0].strip() != _LAUNCH_HEADER:
        return 8, "The file the Android device wrote is not a MapTasker launch result."
    return 0, ""


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
        route: which kind, and how the screen is asked for.  OPEN_FILE_ROUTE and
            OPEN_PROJECT_ROUTE let Android find the handler; the SEND_INTENT_* pair address
            Tasker explicitly.  Prefer the first -- see the section comment for the file://
            URI only the second can trip over.

    Unlike import_profile_to_device this has no acknowledged_risk gate, and no duplicate
    check either.  It puts nothing at stake but the one Profile or Project: Android is
    handed a file, Tasker shows the user what it is about to import -- including, measured
    on a real device, an offer to replace something it already has -- and the semantics from
    there are Tasker's own documented ones.  Refusing a name Tasker already knows would only
    put a worse prompt in front of a better one.

    The exchange: get an API key, install the helper Task if it isn't there, clear the last
    answer, stage the XML, run the Task, confirm it ran, and then -- if asked, and if the
    answer would mean anything -- wait for the import to appear.  Returns (0, a sentence
    saying what happened and what the user still has to do) or (return_code, an error
    message).

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2 or
    higher.  Blocking, deliberately; a caller on the GUI thread must use run.io_bound.
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

    # Asked BEFORE the import, because afterwards the answer is worthless -- see
    # import_is_confirmable.  Nothing is gated on it; it only decides what can be said at
    # the end.
    wanted = [name.strip() for name in confirm_names if name and name.strip()]
    present_before = verify_names_on_android(ip_address, ip_port, route.confirm_endpoint, wanted, auth_key)
    confirmable = bool(wanted) and present_before == set()

    return_code, message = install_task_on_android(
        ip_address, ip_port, auth_key, route.task_name, functools.partial(route.builder, state=state), state=state
    )
    if return_code != 0:
        return return_code, message
    auth_key = held_auth_key(ip_address, ip_port) or auth_key

    return_code, message, auth_key = _hand_offer_to_device(ip_address, ip_port, xml_bytes, object_name, route, auth_key)
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


def open_profile_on_device(
    profile_xml: bytes,
    profile_name: str,
    ip_address: str,
    ip_port: str,
    wait_for_confirmation: bool = True,
    route: OfferRoute = OPEN_FILE_ROUTE,
    *,
    state: RunState,
) -> tuple[int, str]:
    """Offer one Profile to Tasker's import screen.  See offer_to_tasker, which does the work.

    A Profile confirms by its own name -- the list of one that offer_to_tasker's general
    case collapses to.
    """
    return offer_to_tasker(
        profile_xml,
        profile_name,
        [profile_name.strip()],
        ip_address,
        ip_port,
        wait_for_confirmation,
        route,
        state=state,
    )


def open_project_on_device(
    project_xml: bytes,
    project_name: str,
    profile_names: list[str],
    ip_address: str,
    ip_port: str,
    wait_for_confirmation: bool = True,
    route: OfferRoute = OPEN_PROJECT_ROUTE,
    *,
    state: RunState,
) -> tuple[int, str]:
    """Offer one Project -- and every Profile and Task it owns -- to Tasker's import screen.

    profile_names is the Project's own Profiles, which the caller reads off the live tree
    (projedit.project_profile_names).  They are what the import is confirmed by, because
    there is no /api/projects to ask about the Project itself; see the section comment.
    """
    return offer_to_tasker(
        project_xml, project_name, profile_names, ip_address, ip_port, wait_for_confirmation, route, state=state
    )
