#! /usr/bin/env python3
"""objprops: the Properties panel shared by Project, Profile, Task and Scene.

What Tasker calls an object's Properties is a handful of scalar children plus any
number of <ProfileVariable> children.  The three non-Scene kinds differ only in WHICH
scalars they show -- the variables half is byte-identical between them, down to the
element name (a Task's variables are <ProfileVariable> too; only <pvit> says which
kind owns them).  So the scalars are a table (OBJECT_PROPERTIES) and everything else
is one code path.

A Scene's properties are a <PropertiesElement> instead, generated from action_codes and
already rendered by guiwins.render_scene_properties; nothing here touches them.

WHERE THE EDIT LANDS is the caller's decision and is NOT the same for every kind.
apply_properties writes onto whatever element it is handed:

  * Task, Profile -- hand it the WORKING COPY (edited_task.task_element,
    edited_profile.profile_element).  Every save path for those goes through the
    working copy -- apply_edited_task_to_live_tree swaps the whole element into
    all_tasks, and render_standalone_task_xml deep-copies it -- so a property written
    there reaches the live tree, the export and the upload alike.  Cancel on the
    parent dialog still discards it, and guiwins.editor_state hashes
    ETW.tostring(element), so "Changes Pending" lights up with no extra wiring.

  * Project -- hand it the working copy too, then mirror it onto the LIVE element with
    mirror_properties.  projedit.apply_properties_to_live_tree does both and is what the
    dialog actually calls.  The mirror is not optional: both Project saves render from
    the live tree BY NAME (projedit.write_standalone_project_xml(project_name, ...) and
    .save_project_to_android(project_name, ...)), so a property left on the copy alone
    would be silently dropped from the exported file and the upload -- the bug the
    EDIT_PROJECT_INERT_FIELDS comment above guiwins.build_edit_project_dialog warns
    about.  Both elements are written rather than just the live one because a Rename
    registers the COPY as the live element (rename_project_in_live_tree), so a property
    that existed only on the live element would be dropped by the next rename.  This is
    exactly what set_project_enabled already does, for the same reasons.

apply_properties itself takes no undo checkpoint.  For a working copy there is nothing
to check-point -- the live configuration has not changed yet, and the parent's own save
is already wrapped.  The Project path DOES reach the live tree, so its checkpoint is
taken by projedit.apply_properties_to_live_tree.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import defusedxml.ElementTree

KIND_PROJECT = "Project"
KIND_PROFILE = "Profile"
KIND_TASK = "Task"
KIND_SCENE = "Scene"

# Which <pvit> marks a variable as belonging to each kind.  Transcribed from the sample
# backups in XML/: 'pj' 663, 't' 596, 'pr' 15, and no other value.
PVIT_BY_KIND = {KIND_PROJECT: "pj", KIND_PROFILE: "pr", KIND_TASK: "t"}

# <pvid> is an opaque owner identifier and is NEVER rewritten on an existing variable.
#
# It is uniform within an object -- all 538 objects in the sample backups that carry
# variables give every one of them the same <pvid> -- but it is NOT the object's <id>:
# a Project's <id> is a UUID while its pvid is a small integer (a Project such as "Garden
# Watering" might be id=4b7e0c2a-... pvid=1), and for Tasks the two agree in only 39 of 570 cases.  It
# looks like a Tasker-internal index, and there is nothing in a backup to derive it
# from, so a value invented here would be wrong.
#
# Hence: preserved verbatim for a variable that already exists, and for a new one
# inherited from a sibling -- see _new_variable_pvid, which is the only place that has
# to guess and only does so for an object with no variables at all.
_FALLBACK_PVID = "1"

# Variable type code -> the label Tasker shows for it.
#
# DUPLICATED, FOR NOW, from property.py's variable_type_lookup (a local inside
# parse_variable, so there is nothing importable to share yet).  This module is the
# right home for it -- it is the only one that WRITES the codes -- so the tidy-up is
# to hoist property.py's copy away and have it import this.  Left alone here to keep
# this change off the read path.
#
# Codes actually seen in the sample backups: t n yn onoff b i cl d f a cac c ws cn ln
# ds.  The rest come from Tasker's own type list and are kept so a variable authored
# in Tasker round-trips through this editor with its type intact.
VARIABLE_TYPES: dict[str, str] = {
    "t": "Text",
    "n": "Number",
    "b": "True or False",
    "yn": "Yes or No",
    "onoff": "On or Off",
    "f": "File",
    "fs": "File (System)",
    "fss": "Files (System)",
    "i": "Image",
    "is": "Images",
    "d": "Directory",
    "ds": "Directory (System)",
    "ws": "WiFi SSID",
    "wm": "WiFi MAC",
    "bn": "Bluetooth device's name",
    "bm": "Bluetooth device's MAC address",
    "c": "Contact",
    "cn": "Contact Number",
    "cg": "Contact or Contact Group",
    "ti": "Time",
    "da": "Date",
    "a": "App",
    "as": "Apps",
    "la": "Launcher",
    "cl": "Color",
    "ln": "Language",
    "ttsv": "Text to Speech voice",
    "can": "Calendar",
    "cae": "Calendar Entry",
    "tz": "Time Zone",
    "ta": "Task",
    "prf": "Profile",
    "prj": "Project",
    "scn": "Scene",
    "cac": "User Certificate",
}

DEFAULT_VARIABLE_TYPE = "t"

# The children Tasker writes into every <ProfileVariable>, in the order it writes them
# (alphabetical).  All 11 are present in all 1,209 sample variables; <pvv> is the one
# exception and is omitted when the variable has no value (381 of the 1,209), which is
# why it is not in this tuple -- see _write_variable.
_VARIABLE_CHILDREN = (
    "clearout",
    "exportval",
    "immutable",
    "pvci",
    "pvd",
    "pvdn",
    "pvid",
    "pvit",
    "pvn",
    "pvt",
    "pvv",
    "strout",
)

# A variable name, as Tasker writes it.  All 1,209 sample names match this exactly.
_VARIABLE_NAME_PATTERN = re.compile(r"%[A-Za-z0-9_]+")

# Collision Handling, indexed by <rty>.  <rty> is 1 or 2 in all 836 Tasks that carry
# one (470 / 366) and never 0, and the 8,765 Tasks with no <rty> at all are the ones
# left on the default -- so index 0 is the default and is written by omitting the tag,
# the same convention <stayawake> and <showinnot> follow.  property.py:207 indexes this
# same list the same way on the read side.
COLLISION_CHOICES: tuple[str, ...] = ("Abort New Task", "Abort Existing Task", "Run Both Together")

# --------------------------------------------------------------------------------------
# <flags>: THE THREE BITFIELDS IN A TASKER BACKUP, FROM TASKER'S OWN VALUES
# --------------------------------------------------------------------------------------
# Three unrelated things in a backup all name their bitfield <flags> -- a Profile, an App
# context (a Profile's <App> condition) and a Legacy Scene element -- and each one's bits
# mean something different.  All three tables below are TRANSCRIBED FROM TASKER'S
# AUTHORITATIVE VALUES, not inferred, which is what makes them the one place to read and
# the reason every other module imports them from here instead of keeping a copy.
#
# THEY REPLACE A MEASUREMENT THAT HAD TWO OF THE PROFILE BITS IN THE WRONG PLACE.  Before
# this, a Profile's Show In Notification was taken to be mask 16 and Enforce Task Order
# mask 1, both read off two exports of one Profile made a setting at a time; the
# authoritative values have them the other way round AND worded as their negatives (mask 1
# is "hide", mask 16 is "ignore"), so each of those exports was an UNticked box rather than
# a ticked one.  Ticking Show In Notification in the Properties editor was therefore
# setting "ignore task order" on the Profile -- a wrong bit written to a real
# configuration, which is why nothing here is measured any more.
#
# The full distribution of the 5,586 sample Profiles that carry a <flags> supports the
# table as transcribed: 10 (collapsed + ignore settings, 4,009 -- Tasker's own value for a
# new Profile, NEW_PROFILE_FLAGS), 2 (583), 8 (351), 42 (120), 43 (112), 11 (89), 40 (81),
# 26 (61), 34 (55), 27 (46), 3 (38), 18 (17), 9 (11), 24 (6), 58 (3), 56 (2), 31 and 38
# (1 each).  Not one exceeds 63, which is the six bits below and no seventh.
#
# EVERY BIT NOT NAMED BY A PropField IS STILL CARRIED THROUGH UNTOUCHED.  Collapsed is the
# one left: Tasker's own list state, nothing a user would set from here.  So
# _apply_flag_bits read-modify-writes the value that is there rather than building a new one
# out of the fields it knows -- which also covers a bit from a Tasker newer than this table.

PROFILE_FLAGS_TAG = "flags"

# A Profile's <flags>, by bit number.  Two are worded as the NEGATIVE of the setting
# Tasker's Properties screen shows, which is exactly what PropField.default is for: those
# two carry a default of "true" and so are written when the box is UNticked.
PROFILE_HIDE_IN_NOTIFICATION_BIT = 0  # mask 1
PROFILE_COLLAPSED_BIT = 1  # mask 2 -- collapsed in Tasker's own list; stripped on export
PROFILE_DELETE_AFTER_DISABLE_BIT = 2  # mask 4
PROFILE_IGNORE_SETTINGS_BIT = 3  # mask 8 -- Restore Settings OFF, and SET on a new Profile
PROFILE_IGNORE_TASK_ORDER_BIT = 4  # mask 16
PROFILE_RUN_EXIT_TASK_ON_STARTUP_BIT = 5  # mask 32 -- if the Profile is not active

# What to call each bit where a raw <flags> is being REPORTED rather than edited (the Map's
# debug line).  Worded as the bit is worded, negatives and all: this decodes the number in
# the file, and calling mask 1 "Show In Notification" would invert its meaning.
PROFILE_FLAG_NAMES: dict[int, str] = {
    PROFILE_HIDE_IN_NOTIFICATION_BIT: "Hide In Notification",
    PROFILE_COLLAPSED_BIT: "Collapsed",
    PROFILE_DELETE_AFTER_DISABLE_BIT: "Delete After Disable",
    PROFILE_IGNORE_SETTINGS_BIT: "Ignore Settings",
    PROFILE_IGNORE_TASK_ORDER_BIT: "Ignore Task Order",
    PROFILE_RUN_EXIT_TASK_ON_STARTUP_BIT: "Run Exit Task On Startup",
}

# An App context's <flags> -- the <App> child of a Profile, which is the Application
# condition.  All 162 App conditions in the sample backups hold 2, the default, so only a
# value that is not 2 says anything a reader does not already assume (condition_app).
APP_MATCH_RUNNING_SERVICES_BIT = 0  # mask 1
APP_MATCH_FOREGROUND_APP_BIT = 1  # mask 2 -- the default
APP_FLAG_NAMES: dict[int, str] = {
    APP_MATCH_RUNNING_SERVICES_BIT: "matching running services",
    APP_MATCH_FOREGROUND_APP_BIT: "matching the foreground app",
}

# A Legacy Scene element's <flags>.  The sample data's 7,302 elements carry seven distinct
# values and these four bits explain all of them: 4 visible (4,823), 5 visible and fixed
# (573), 6 visible and behind (182), 1 fixed and NOT visible (172), 13 and 12 initial focus
# (24 and 21 -- 24 of the 13s are EditTextElements, which is where an initial focus goes).
#
# AN ELEMENT WITH NO <flags> AT ALL IS NOT AN INVISIBLE ELEMENT.  1,507 have none,
# including every one of the 862 <PropertiesElement>s, and Tasker itself produces that
# state (sceneedit's LEGACY_VE_BY_TYPE block) -- so absence means "nothing said" and is
# drawn as normal, and only a <flags> that IS there and has mask 4 clear is hidden.
SCENE_ELEMENT_FLAGS_TAG = "flags"
SCENE_ELEMENT_FIXED_POSITION_BIT = 0  # mask 1
SCENE_ELEMENT_BACKGROUND_BIT = 1  # mask 2
SCENE_ELEMENT_VISIBLE_BIT = 2  # mask 4
SCENE_ELEMENT_INITIAL_FOCUS_BIT = 3  # mask 8
SCENE_ELEMENT_FLAG_NAMES: dict[int, str] = {
    SCENE_ELEMENT_FIXED_POSITION_BIT: "Fixed position",
    SCENE_ELEMENT_BACKGROUND_BIT: "Background element",
    SCENE_ELEMENT_VISIBLE_BIT: "Visible",
    SCENE_ELEMENT_INITIAL_FOCUS_BIT: "Initial focus",
}

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
MAX_LAUNCH_PRIORITY = 50

# What separates the parts of a Cooldown Time on screen.  Purely a display convention --
# <cldm> holds a plain second count, so nothing in the XML depends on it -- but it is a
# constant rather than a literal because the format appears in four places that have to
# agree: the field's own label, format_cooldown, parse_cooldown, and the error message
# validate() gives when it will not parse.
COOLDOWN_SEPARATOR = ":"
COOLDOWN_FORMAT = COOLDOWN_SEPARATOR.join(("dd", "hh", "mm", "ss"))
# The units each part means, largest first -- shared by both directions so they cannot
# disagree about how many parts there are or what they weigh.
_COOLDOWN_UNITS = (SECONDS_PER_DAY, SECONDS_PER_HOUR, SECONDS_PER_MINUTE, 1)


@dataclass(frozen=True)
class PropField:
    """One scalar property: which tag holds it, how it is shown, and what value means
    "Tasker would not have written this tag at all".

    `default` is load-bearing rather than cosmetic.  Tasker omits <pc>, <rty>,
    <stayawake> and <showinnot> when they hold their default -- across the sample
    backups <stayawake> appears only as 'true' (62x) and <showinnot> only as 'false'
    (414x), never the other way -- so writing them unconditionally would make every
    edited object differ from its own backup in tags the user never touched: noise in
    xmldiff, and a bigger upload.  apply_properties REMOVES a tag whose value equals
    its default rather than writing it.

    That one rule covers both directions without a second flag.  <stayawake> defaults
    off, so it is written only when switched on; <showinnot> defaults ON, so it is
    written only when switched OFF.  Getting that pair backwards would stamp
    <showinnot>false</showinnot> onto the 9,187 Tasks that have never had one.

    `tasker_default` is for the ONE case where `default` is not also the state an untouched
    object is in: Restore Settings.  Its bit records the NEGATIVE (mask 8 is "ignore
    settings"), and Tasker SETS that bit on every Profile it creates -- 4,892 of the 5,627
    sample Profiles carry it, including the 4,009 at Tasker's own new-Profile value of 10.
    So `default` has to stay "true" (the bit is cleared when the box is ticked, and a Profile
    with no <flags> at all reads as ticked), while the value that means "nobody has touched
    this" is "false".  Everything that WRITES uses `default`; everything that asks whether a
    setting is worth REPORTING -- has_properties, the Map's Properties line -- uses
    noteworthy_default, or 4,892 Profiles would announce a setting Tasker chose for them.

    `bit` is for the properties Tasker keeps in a BITFIELD instead of in a tag of their
    own -- five of a Profile's, all inside <flags>.  The same `default` rule carries over
    unchanged: the bit is SET when the value differs from the default and CLEAR when it
    equals it, which is all an INVERTED bit needs.  Two of the four are inverted, because
    Tasker words them as the negative of the setting it shows: mask 1 is "hide in
    notification" and mask 16 is "ignore task order", so Show In Notification and Enforce
    Task Order both carry a default of "true" and write their bit when UNticked -- the shape
    a Task's <showinnot> has.  Every other bit of the tag, named here or not, is left
    exactly as it was -- see _apply_flag_bits.
    """

    key: str  # field_refs key, unique within the dialog
    tag: str  # child tag of the object element
    label: str
    kind: str  # "text" | "checkbox" | "choice" | "slider" | "number" | "duration"
    default: str  # the value at which the tag is removed rather than written
    choices: tuple[str, ...] = ()
    tooltip: str = ""
    maximum: int = 0  # slider only
    bit: int | None = None  # bitfield properties only: which bit of `tag` holds this one
    tasker_default: str = ""  # only when an untouched object is NOT at `default` -- see above


_COMMENTS = PropField("pc", "pc", "Comments", "text", "")

_COLLISION = PropField(
    "rty",
    "rty",
    "Collision Handling",
    "choice",
    "0",
    choices=COLLISION_CHOICES,
    tooltip=(
        "What to do when another copy of this task is already running.  "
        "See the page on Tasks in the userguide for more information."
    ),
)

_KEEP_AWAKE = PropField(
    "stayawake",
    "stayawake",
    "Keep Device Awake",
    "checkbox",
    "false",
    tooltip=(
        "Whether to keep the device running while the task is running.  The default is that "
        "tasks will be guaranteed to be kept running for around a minute from their start "
        "time.  Be careful specifying this option for a task with a loop, it can very quickly "
        "drain the battery."
    ),
)

_TASK_SHOW_IN_NOTIFICATION = PropField(
    "showinnot",
    "showinnot",
    "Show In Notification",
    "checkbox",
    "true",
    tooltip=(
        "Whether to include this task in the Running Tasks notification that updates every "
        "time a task is started or stopped."
    ),
)

_LAUNCH_PRIORITY = PropField(
    "pri",
    "pri",
    "Launch Task Priority",
    "slider",
    "",
    maximum=MAX_LAUNCH_PRIORITY,
    tooltip=(
        "The priority of the enter and exit tasks by this profile.  Note: this does not "
        "affect the profile becoming active in anyway."
    ),
)

_COOLDOWN = PropField(
    "cldm",
    "cldm",
    "Cooldown Time",
    "duration",
    "",
    tooltip=(
        "The times after the profile has become active before it can again become active.  "
        "Cooldown time is reset after a boot."
    ),
)

# THE PROFILE SETTINGS TASKER'S OWN PROPERTIES SCREEN HAS AND THE SAMPLE DATA DOES NOT.
# None of them appears in any of the 5,627 Profiles in XML/, so each was hunted down by
# measurement -- five exports of one Profile made with Tasker 6.7.6, a setting at a time --
# until Tasker's authoritative <flags> values arrived.  THE VALUES WIN WHERE THEY DISAGREE,
# and they disagree in three places; the exports are kept here because two of them are the
# only evidence about the tags that are NOT bits.
#
#   export     what was ticked                        <flags>  bits  other children
#   Atest1     Limit Repeats                              8    3     <limit>
#   Atest1-1   Enforce Task Order                         9    0,3   --
#   Atest1-2   Show In Notification                      24    3,4   --
#   Atest2     Limit Repeats, Remaining 5, Delete On 0    12    2,3   <repeats> <dod> <limit>
#   Atest2(2)  the same, plus Enforce Task Order          13    0,2,3 <repeats> <dod> <limit>
#
# Bit 3 (mask 8) is in all five and is Ignore Settings, not a baseline: it is Restore Settings
# switched off, which is the state Tasker leaves a new Profile in -- hence the field's
# tasker_default, and hence its being in all five exports without the tester touching it.
# Reading the rest against the real values:
#
#   mask 1    Hide In Notification    Atest1-2's "Show In Notification" export is a box
#             (bit 0)                 UNTICKED, not ticked -- so the field below defaults to
#                                     "true" and the bit is written when it is turned off,
#                                     the same shape a Task's <showinnot> has after all
#   mask 16   Ignore Task Order       likewise Atest1-1, and likewise inverted.  The two
#             (bit 4)                 exports had these two settings the wrong way round,
#                                     which is what made ticking Show In Notification write
#                                     mask 16 -- Ignore Task Order -- until now
#   mask 4    Delete After Disable    what Atest2's "Delete On 0" actually set.  The one
#             (bit 2)                 sample Profile with a <dod> has this bit as well, and
#                                     one other has the bit and no <dod>, so the BIT is
#                                     where the setting lives and <dod> is its older twin:
#                                     read and written through the bit, and a <dod> already
#                                     in a file is left exactly as it is
#   <repeats> Remaining Repeats       10 sample Profiles carry one
#
# LIMIT REPEATS IS NOT A FIELD ANY MORE.  It has no bit of its own -- mask 4 belongs to
# Delete After Disable -- and the two exports that ticked it wrote <repeats> and <limit>
# instead, so the checkbox had nowhere honest to put itself and was writing mask 4.  Giving
# Remaining Repeats a count is what limits a Profile's repeats, and that field owns it.
#
# <limit> IS NOT ONE OF THESE FIELDS AND MUST NOT BECOME ONE.  It identifies a disabled
# Tasker object and nothing else -- profiles.py greys the Profile out in the Map, healthck.py
# reports DISABLED-PROFILE, and profedit.set_profile_enabled writes and removes it for the
# Edit Profile dialog's Enabled switch, which is the one control that owns it.
_REMAINING_REPEATS = PropField(
    "repeats",
    "repeats",
    "Remaining Repeats",
    "number",
    "",
    tooltip=(
        "The number of times remaining before the profile becomes disabled.  Giving a count "
        "here is how a profile's repeats are limited e.g. if its enter task should only be "
        "run once."
    ),
)

_DELETE_AFTER_DISABLE = PropField(
    "delete_after_disable",
    PROFILE_FLAGS_TAG,
    "Delete After Disable",
    "checkbox",
    "false",
    bit=PROFILE_DELETE_AFTER_DISABLE_BIT,
    tooltip=(
        "Whether this profile should be deleted once it becomes disabled, which is what "
        "happens when its repeat count gets to 0."
    ),
)

_RESTORE_SETTINGS = PropField(
    "restore_settings",
    PROFILE_FLAGS_TAG,
    "Restore Settings",
    "checkbox",
    "true",
    bit=PROFILE_IGNORE_SETTINGS_BIT,
    tasker_default="false",
    tooltip=(
        "Whether to restore any settings that this profile's tasks changed when the profile "
        "becomes inactive.  Tasker leaves this off on a profile it creates, which is why a "
        "profile is only reported as having it when it has been switched ON."
    ),
)

_ENFORCE_TASK_ORDER = PropField(
    "enforce_task_order",
    PROFILE_FLAGS_TAG,
    "Enforce Task Order",
    "checkbox",
    "true",
    bit=PROFILE_IGNORE_TASK_ORDER_BIT,
    tooltip=(
        "Ensure that tasks resulting from the profile activation or deactivation remain "
        "queued until previous tasks from this profile are complete."
    ),
)

_RUN_EXIT_TASK_ON_STARTUP = PropField(
    "run_exit_task_on_startup",
    PROFILE_FLAGS_TAG,
    "Run Exit Task On Startup",
    "checkbox",
    "false",
    bit=PROFILE_RUN_EXIT_TASK_ON_STARTUP_BIT,
    tooltip=("Whether to run this profile's exit task when Tasker starts up and the profile is not active."),
)

_PROFILE_SHOW_IN_NOTIFICATION = PropField(
    "profile_showinnot",
    PROFILE_FLAGS_TAG,
    "Show In Notification",
    "checkbox",
    "true",
    bit=PROFILE_HIDE_IN_NOTIFICATION_BIT,
    tooltip=(
        "Whether to include this profile in the Running Profiles notification that updates "
        "every time a profile is started or stopped."
    ),
)

# Which scalars each kind shows, in the order Tasker shows them.
OBJECT_PROPERTIES: dict[str, tuple[PropField, ...]] = {
    KIND_PROJECT: (_COMMENTS,),
    KIND_PROFILE: (
        _LAUNCH_PRIORITY,
        _COOLDOWN,
        _REMAINING_REPEATS,
        _DELETE_AFTER_DISABLE,
        _RESTORE_SETTINGS,
        _ENFORCE_TASK_ORDER,
        _RUN_EXIT_TASK_ON_STARTUP,
        _PROFILE_SHOW_IN_NOTIFICATION,
        _COMMENTS,
    ),
    KIND_TASK: (_COLLISION, _KEEP_AWAKE, _TASK_SHOW_IN_NOTIFICATION, _COMMENTS),
}


@dataclass
class EditableProperties:
    """The properties of ONE object, opened for editing.

    `element` is whatever the caller handed over and is written to in place -- see the
    module docstring for which element that has to be, per kind.

    `variables` is a live list of the element's <ProfileVariable> children in document
    order.  add_variable/remove_variable keep it and the element in step; nothing else
    should append to either on its own.
    """

    kind: str
    element: defusedxml.ElementTree.Element
    variables: list[defusedxml.ElementTree.Element] = field(default_factory=list)


# --------------------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------------------
def load_properties(kind: str, element: defusedxml.ElementTree.Element) -> EditableProperties:
    """Open an object's properties for editing.  Takes no copy: see the module docstring
    on which element the caller is expected to hand over.
    """
    return EditableProperties(kind=kind, element=element, variables=list(element.findall("ProfileVariable")))


# The two values a checkbox property can hold, each other's opposite.  A bit-backed
# property is always a checkbox -- a bit cannot hold anything else -- so a lookup is all
# the "the other one" this needs.
_NEGATED = {"true": "false", "false": "true"}


def flag_bits(element: defusedxml.ElementTree.Element, tag: str = PROFILE_FLAGS_TAG) -> int:
    """The integer a bitfield tag holds, and 0 for one that is absent or unreadable.

    0 for unreadable rather than an error because <flags> is Tasker's, not ours: a value
    this build cannot parse is data to leave alone, and _apply_flag_bits leaves exactly
    that case untouched rather than replacing it with a number of its own.
    """
    text = (element.findtext(tag) or "").strip()
    return int(text) if text.isdigit() else 0


def describe_flags(value: int, names: dict[int, str]) -> list[str]:
    """The set bits of a <flags> value, named, lowest bit first -- for the places that
    REPORT a bitfield rather than edit one (the Map's debug line, a Scene element's
    tooltip, an App condition).

    A bit with no entry in `names` is reported as "bit N" rather than dropped: a value
    from a Tasker newer than the table is still worth showing as a number the reader can
    look up, and silently omitting it would claim the tag held less than it does.
    """
    return [names.get(bit, f"bit {bit}") for bit in range(value.bit_length()) if value & (1 << bit)]


def bitfield_is_readable(element: defusedxml.ElementTree.Element, tag: str = PROFILE_FLAGS_TAG) -> bool:
    """Can this object's bitfield tag be believed?  True when it is absent (which is a real
    state, and reads as every bit clear) or holds a number, and False for a value this build
    cannot parse.

    WORTH ASKING BECAUSE "EVERY BIT CLEAR" IS NOT A SAFE FALLBACK ANY MORE.  It used to be:
    every bit-backed field read as switched off, which is what an unparseable value should
    say.  Restore Settings changed that -- its bit records the negative, so bits-all-clear
    reads as that setting switched ON, and reporting it off the back of a value nobody can
    read would be inventing a setting.  So the places that REPORT bits ask this first, while
    the places that write them do not need to: _apply_flag_bits leaves an unreadable value
    exactly as it found it (see flag_bits).
    """
    text = (element.findtext(tag) or "").strip()
    return text == "" or text.isdigit()


def _bit_value(spec: PropField, element: defusedxml.ElementTree.Element) -> str:
    """A bit-backed property as the "true"/"false" the dialog deals in.

    The bit being SET means "not the default", which is the one rule that makes Delete
    After Disable (a bit that records the setting) and Enforce Task Order (a bit that
    records its negative) the same code -- see PropField.
    """
    return _NEGATED[spec.default] if flag_bits(element, spec.tag) & (1 << spec.bit) else spec.default


def noteworthy_default(spec: PropField) -> str:
    """The value that means "nobody has touched this setting" -- which is `default` for every
    field but Restore Settings, whose bit Tasker sets itself (see PropField).

    Separate from `default` because the two questions are different: `default` is how the
    value is STORED (which state leaves the tag or bit out), and this is whether the value is
    worth SAYING.  Conflating them would either report a setting on 4,892 of the 5,627 sample
    Profiles or write the bit the wrong way round.
    """
    return spec.tasker_default or spec.default


def has_properties(kind: str, element: defusedxml.ElementTree.Element) -> bool:
    """Does this object have any properties set?  Decides whether the button in the
    Add/Edit dialog reads "Add Properties" or "Edit Properties".

    A tag holding the value an untouched object has does not count -- that is the state
    Tasker itself would have left, so offering "Edit" for it would be claiming properties
    the object does not have.

    A Scene is the odd one out and is answered entirely by whether it has a
    <PropertiesElement>: its properties are that element's arguments rather than the
    scalars-and-variables the other three share, and 66 of the 366 Scenes in the sample
    data have none at all -- an ordinary state, and exactly the one "Add Properties"
    is for.
    """
    if kind == KIND_SCENE:
        return element.find("PropertiesElement") is not None

    if element.find("ProfileVariable") is not None:
        return True
    return any(
        _bit_value(spec, element) != noteworthy_default(spec) and bitfield_is_readable(element, spec.tag)
        if spec.bit is not None
        # A bitfield tag holds several properties at once, so its mere presence says
        # nothing -- only the one bit does.  Every other tag is its own answer.
        else (element.findtext(spec.tag) or "") not in ("", noteworthy_default(spec))
        for spec in OBJECT_PROPERTIES.get(kind, ())
    )


def _choice_label(spec: PropField, stored: str) -> str:
    """A "choice" tag's stored index as the label the dropdown shows.  An index outside
    the list is handed back as-is rather than snapped to the first entry, so a value this
    build does not know about survives a round trip instead of being silently rewritten.
    """
    return spec.choices[int(stored)] if stored.isdigit() and int(stored) < len(spec.choices) else stored


def _choice_index(spec: PropField, label: str) -> str:
    """The reverse: the dropdown's label back to the index the tag holds.  Anything not
    in the list is passed through, which is what round-trips an unknown value.
    """
    return str(spec.choices.index(label)) if label in spec.choices else label


def scalar_values(props: EditableProperties) -> dict[str, str]:
    """Current value per PropField.key, with defaults filled in for absent tags.  Seeds
    the widgets, so the dialog never reads the XML itself.

    A "choice" comes back as the LABEL, not the index its tag holds -- the dialog deals
    only in what it shows, and apply_properties converts back.  Getting that wrong writes
    '<rty>Abort Existing Task</rty>' where Tasker expects '<rty>1</rty>'.
    """
    values = {}
    for spec in OBJECT_PROPERTIES.get(props.kind, ()):
        if spec.bit is not None:
            values[spec.key] = _bit_value(spec, props.element)
            continue
        stored = props.element.findtext(spec.tag) or spec.default
        values[spec.key] = _choice_label(spec, stored) if spec.kind == "choice" else stored
    return values


def variable_values(variable: defusedxml.ElementTree.Element) -> dict[str, str]:
    """One variable's fields, keyed as the dialog keys them.

    "same_as_value" is computed rather than read: Tasker has no tag for it and simply
    writes <exportval> equal to <pvv> when the option is on.  Both being empty reads as
    on, which is what Tasker shows for a variable that has neither.
    """
    values = {tag: (variable.findtext(tag) or "") for tag in _VARIABLE_CHILDREN}
    values["same_as_value"] = "true" if values["exportval"] == values["pvv"] else "false"
    return values


def variable_display_name(variable: defusedxml.ElementTree.Element) -> str:
    """What to title a variable's panel with -- its name, or its display name if it has
    no name yet.
    """
    return (variable.findtext("pvn") or "").strip() or (variable.findtext("pvdn") or "").strip()


# --------------------------------------------------------------------------------------
# Cooldown: stored as seconds, shown as dd:hh:mm:ss
# --------------------------------------------------------------------------------------
def format_cooldown(seconds: str) -> str:
    """A <cldm> second count as dd:hh:mm:ss.  "" for an absent or unparseable value, so
    an empty field means "no cooldown" rather than "00:00:00:00".
    """
    text = (seconds or "").strip()
    if not text.isdigit():
        return ""
    total = int(text)
    days, total = divmod(total, SECONDS_PER_DAY)
    hours, total = divmod(total, SECONDS_PER_HOUR)
    minutes, secs = divmod(total, SECONDS_PER_MINUTE)
    return COOLDOWN_SEPARATOR.join(f"{part:02}" for part in (days, hours, minutes, secs))


def parse_cooldown(text: str) -> str | None:
    """dd:hh:mm:ss back to the second count <cldm> holds.  None when it does not parse,
    which is what validate() turns into an error message; "" for an empty field, which
    removes the tag.

    Shorter forms are accepted from the right, the way a person types them: "30" is 30
    seconds, "5:00" is five minutes.  Each part has to be a number, but they are not
    range-checked -- "00:00:90:00" is 90 minutes, and Tasker stores the total either way.

    A '.' is accepted as well as a ':', because ':' replaced it as the separator this
    field shows and a Cooldown typed the old way is still what the person meant.  Only
    one of the two may appear in a given value, so "1.2:3" is rejected rather than
    guessed at.
    """
    stripped = (text or "").strip()
    if not stripped:
        return ""
    separators = {character for character in (COOLDOWN_SEPARATOR, ".") if character in stripped}
    if len(separators) > 1:
        return None
    parts = stripped.split(separators.pop()) if separators else [stripped]
    if len(parts) > len(_COOLDOWN_UNITS) or not all(part.strip().isdigit() for part in parts):
        return None
    # Right-align against (days, hours, minutes, seconds) so "5:00" is mm:ss.
    multipliers = _COOLDOWN_UNITS[-len(parts) :]
    return str(sum(int(part) * multiplier for part, multiplier in zip(parts, multipliers, strict=True)))


# --------------------------------------------------------------------------------------
# Validating
# --------------------------------------------------------------------------------------
def validate(props: EditableProperties, values: dict[str, str]) -> list[str]:
    """Everything wrong with what is on screen, or [] when it is safe to apply.

    `values` is the dialog's snapshot: one entry per PropField.key, plus
    "var<n>_<tag>" per variable field.  Same all-or-nothing contract as
    taskedit.apply_edits_to_task and profedit.apply_edits_to_profile -- when this
    returns anything, apply_properties writes nothing.
    """
    errors: list[str] = []

    for spec in OBJECT_PROPERTIES.get(props.kind, ()):
        raw = (values.get(spec.key) or "").strip()
        if spec.kind == "duration" and parse_cooldown(raw) is None:
            errors.append(
                f"{spec.label} must be a {COOLDOWN_FORMAT} time, for example "
                f"{format_cooldown(str(SECONDS_PER_DAY + 6 * SECONDS_PER_HOUR + 30 * SECONDS_PER_MINUTE))}.",
            )
        elif spec.kind in ("slider", "number") and raw and not raw.isdigit():
            errors.append(f"{spec.label} must be a whole number.")
        elif spec.kind == "slider" and raw.isdigit() and int(raw) > spec.maximum:
            errors.append(f"{spec.label} must be between 0 and {spec.maximum}.")

    for index in range(len(props.variables)):
        name = (values.get(f"var{index}_pvn") or "").strip()
        if not name:
            errors.append(f"Variable {index + 1} has no name.")
        elif not _VARIABLE_NAME_PATTERN.fullmatch(name):
            errors.append(
                f"'{name}' is not a valid variable name -- it must start with % followed by "
                "letters, digits or underscores.",
            )

    return errors


def warnings(props: EditableProperties, values: dict[str, str]) -> list[str]:
    """Things worth saying but not worth refusing to save over.  Shown alongside a
    successful apply rather than instead of one.

    DUPLICATE NAMES ARE A WARNING, NOT AN ERROR, because real Tasker backups contain
    them -- the Project 'Виджет Авто' in XML/backup.xml declares %aaa twice.  Blocking
    on it would make this dialog refuse to close on an object the user had not even
    edited, which is worse than the duplicate.  Properties2.png only documents
    precedence ACROSS levels (Task beats Profile beats Project); within one object
    Tasker evidently just allows it.
    """
    seen: set[str] = set()
    duplicated: list[str] = []
    for index in range(len(props.variables)):
        name = (values.get(f"var{index}_pvn") or "").strip().casefold()
        if name and name in seen and name not in duplicated:
            duplicated.append(name)
        seen.add(name)

    return [f"This {props.kind} declares '{name}' more than once." for name in duplicated]


# --------------------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------------------
def set_child_text_in_tag_order(
    parent: defusedxml.ElementTree.Element,
    tag: str,
    text: str,
) -> None:
    """Set a child's text, inserting it at Tasker's own child position if it is new.

    Every object's lowercase children run alphabetically, with the compound
    uppercase-tagged ones (Share, Img, Kid, ProfileVariable, and a Profile's condition
    elements) after them all.  Checked across all 880 Projects, 3,526 Profiles and 9,601
    Tasks in this repo's sample backups: one exception, a <limit> after <State> in the
    hand-made test Profile export.  Appending instead would put <pc> after <ProfileVariable>,
    which no Tasker-written object does -- same reasoning as
    projedit.render_standalone_project_xml's pids-before-tids fix-up: what is exported has
    to look like what Tasker writes.

    Compound children are detected by a leading capital, NOT by `not tag.islower()`.
    <_arrlst_tagIds0> -- a real child of 5 Profiles and Tasks in the samples -- contains a
    capital I, so .islower() is False for it and it would be misfiled as compound; being
    always the first child ('_' sorts ahead of every lowercase letter), that would make
    this pick position 0 for every new tag and insert <pc> ahead of <cdate>.
    projedit._set_child_text_in_tag_order has that bug latent -- harmless there, since no
    Project carries an <_arrlst_tagIds0> -- and should be replaced by this function.

    Existing children are left where they are and only their text updated, since anything
    already in the element is already in Tasker's order.
    """
    child = parent.find(tag)
    if child is None:
        # Match the parent's actual Element class: defusedxml's hardened parser yields the
        # pure-Python implementation, and ETW.SubElement would build a stdlib-class child
        # that parent.append() rejects.  Same note as editcommon.set_child_text.
        child = type(parent)(tag)
        position = next(
            (index for index, sibling in enumerate(parent) if (sibling.tag[:1].isupper() or sibling.tag > tag)),
            len(parent),
        )
        parent.insert(position, child)
    child.text = text


def _remove_child(parent: defusedxml.ElementTree.Element, tag: str) -> None:
    """Take a tag away entirely -- how a property is set back to its default."""
    child = parent.find(tag)
    if child is not None:
        parent.remove(child)


def apply_properties(props: EditableProperties, values: dict[str, str]) -> list[str]:
    """Write the scalars and every variable onto props.element.  Validates first and
    writes nothing at all when validation fails, returning the messages.

    A scalar whose value equals its PropField.default is REMOVED rather than written --
    see PropField.  Variables are rewritten in place, so a variable that was already
    there keeps its position among the element's children.
    """
    errors = validate(props, values)
    if errors:
        return errors

    for spec in OBJECT_PROPERTIES.get(props.kind, ()):
        if spec.bit is not None:
            continue  # shares its tag with the other bits -- written together, below
        raw = values.get(spec.key) or ""
        if spec.kind == "duration":
            text = parse_cooldown(raw) or ""
        elif spec.kind == "choice":
            text = _choice_index(spec, raw.strip())
        elif spec.kind == "text":
            # NOT stripped.  A comment is free text and its whitespace is the user's:
            # three Projects in the sample backups end their <pc> with a space, and
            # stripping it makes an untouched object differ from its own backup.
            text = raw
        else:
            text = raw.strip()
        if not text or text == spec.default:
            _remove_child(props.element, spec.tag)
        else:
            set_child_text_in_tag_order(props.element, spec.tag, text)

    _apply_flag_bits(props, values)

    for index, variable in enumerate(props.variables):
        supplied = {
            tag: values[key] for tag in (*_VARIABLE_CHILDREN, "same_as_value") if (key := f"var{index}_{tag}") in values
        }
        _write_variable(props.kind, variable, supplied)

    return []


def _apply_flag_bits(props: EditableProperties, values: dict[str, str]) -> None:
    """Write every bit-backed property of this kind into its bitfield tag, in one pass.

    ONE PASS BECAUSE THEY SHARE A TAG.  All five of a Profile's bit-backed properties are
    <flags>, so writing them the way a scalar is written -- tag by tag, each rewriting the
    whole text -- would have the last overwrite the rest.

    BITS NO FIELD OWNS ARE CARRIED THROUGH.  Mask 2 is Tasker's own "collapsed in the list"
    state, and a rewrite that dropped it would collapse Profiles on a real device.  Hence
    read-modify-write of the value that is there, never a value built from the fields alone
    -- and that also covers a bit from a Tasker newer than this table.

    The tag is REMOVED when every bit ends up clear, which is what Tasker does -- it omits
    <flags> entirely rather than writing a 0 -- and an unchanged value is left exactly as it
    was found, so a no-op edit cannot rewrite '10' as '10' and disturb a byte of the file.
    An unreadable value is left alone for the same reason (see flag_bits).
    """
    specs = [spec for spec in OBJECT_PROPERTIES.get(props.kind, ()) if spec.bit is not None]
    if not specs:
        return

    tag = specs[0].tag
    current = flag_bits(props.element, tag)
    updated = current
    for spec in specs:
        raw = (values.get(spec.key) or "").strip()
        if not raw:
            # Not on screen, so not the user's to change -- the same rule _write_variable
            # follows for a variable field the form has no widget for.  A checkbox always
            # hands back 'true' or 'false', so this is only reachable from a caller that
            # supplies a subset.
            continue
        if raw == spec.default:
            updated &= ~(1 << spec.bit)
        else:
            updated |= 1 << spec.bit

    if updated == current and props.element.find(tag) is not None:
        return
    if updated:
        set_child_text_in_tag_order(props.element, tag, str(updated))
    else:
        _remove_child(props.element, tag)


def _write_variable(
    kind: str,
    variable: defusedxml.ElementTree.Element,
    supplied: dict[str, str],
) -> None:
    """Write one <ProfileVariable>'s children, in Tasker's order and with Tasker's child
    set, so a MapTasker-made variable is indistinguishable from a Tasker-made one.

    ONLY WHAT THE DIALOG ACTUALLY SHOWED IS WRITTEN.  A tag missing from `supplied` keeps
    whatever it already held, because a field with no widget is a field the user had no
    way to set -- blanking it would be silent data loss on something they never saw.
    <clearout> is the live case: Tasker sets it (it is 'true' on 462 sample variables) but
    the properties form has no control for it, since it is not one of the fields Tasker's
    own Project Variables screen exposes either.

    That is the same rule <pvid> and <pvit> follow, and it is why this takes the supplied
    subset rather than a dict filled in with "" for the rest.

    <pvv> is the one child written conditionally: Tasker omits it entirely for a variable
    with no value (381 of the 1,209 in the sample backups), while the other 11 are present
    in all 1,209 even when empty.

    "Same as Value" has no tag -- when it is on, <exportval> is written equal to <pvv>,
    which is the state variable_values() reads it back out of.
    """
    resolved = dict(supplied)

    if "pvv" in supplied and supplied.get("same_as_value") == "true":
        resolved["exportval"] = supplied["pvv"]
    if "pvt" in supplied:
        resolved["pvt"] = supplied["pvt"] or DEFAULT_VARIABLE_TYPE
    if "pvn" in supplied:
        resolved["pvn"] = supplied["pvn"].strip()
    # The owner kind is fully determined (pj/pr/t matches the owning element in all 1,209
    # sample variables, with no exceptions), so it is always corrected rather than trusted.
    resolved["pvit"] = PVIT_BY_KIND.get(kind, "")

    for tag in _VARIABLE_CHILDREN:
        if tag not in resolved:
            continue
        if tag == "pvv" and not resolved["pvv"]:
            _remove_child(variable, tag)
        else:
            set_child_text_in_tag_order(variable, tag, resolved[tag])


def mirror_properties(
    kind: str,
    source: defusedxml.ElementTree.Element,
    target: defusedxml.ElementTree.Element,
) -> None:
    """Replace `target`'s properties with `source`'s -- every scalar this kind owns, and
    the whole set of <ProfileVariable> children.

    For the one caller that has to keep two elements level: a Project's working copy and
    its live element (see projedit.apply_properties_to_live_tree).  A second
    apply_properties onto the live element would not do -- Add/Remove Variable are
    structural edits that happened on the copy alone, so the two disagree on how many
    variables there are and the dialog's var<n>_ keys would land on the wrong ones.
    Copying the finished subtree over sidesteps the index problem entirely.

    Scalars go in at Tasker's own child position and variables are appended, so the result
    is ordered like anything else this module writes.  A scalar absent from `source` is
    removed from `target` rather than left behind: absence is how a default is recorded,
    and a stale tag would read as a setting the user had switched off.
    """
    for spec in OBJECT_PROPERTIES.get(kind, ()):
        text = source.findtext(spec.tag)
        if text is None:
            _remove_child(target, spec.tag)
        else:
            set_child_text_in_tag_order(target, spec.tag, text)

    for existing in target.findall("ProfileVariable"):
        target.remove(existing)
    for variable in source.findall("ProfileVariable"):
        target.append(copy.deepcopy(variable))


def _new_variable_pvid(props: EditableProperties) -> str:
    """What <pvid> to give a brand-new variable.

    Inherited from a sibling wherever there is one, which is right rather than merely
    convenient: every object in the sample backups that carries variables gives all of
    them the same pvid, so matching the siblings is what Tasker itself would have done.

    An object with NO variables yet has nothing to inherit and nothing in the backup to
    derive one from -- this is the one guess in this module.  The object's own <id> is
    used when it is numeric (it is for a Task or a Profile; a Project's is a UUID),
    falling back to '1'.  If a variable added to a previously variable-less object comes
    back from Tasker renumbered, this is why, and it is harmless: pvid is not what
    Tasker matches variables by -- <pvn> is.
    """
    for sibling in props.variables:
        inherited = sibling.findtext("pvid")
        if inherited:
            return inherited
    own_id = props.element.findtext("id") or ""
    return own_id if own_id.isdigit() else _FALLBACK_PVID


def add_variable(props: EditableProperties) -> defusedxml.ElementTree.Element:
    """Append a new, empty <ProfileVariable> and hand it back.

    Given the full child set Tasker writes, so it is a well-formed variable from the
    moment it exists rather than only after the first save -- <pvv> excepted, which an
    empty variable has no business carrying (see _write_variable).
    """
    element_cls = type(props.element)
    variable = element_cls("ProfileVariable", {"sr": f"pv{len(props.variables)}"})
    defaults = {
        "clearout": "false",
        "immutable": "false",
        "pvci": "false",
        "strout": "false",
        "pvid": _new_variable_pvid(props),
        "pvit": PVIT_BY_KIND.get(props.kind, ""),
        "pvt": DEFAULT_VARIABLE_TYPE,
    }
    for tag in _VARIABLE_CHILDREN:
        if tag == "pvv":
            continue
        child = element_cls(tag)
        child.text = defaults.get(tag, "")
        variable.append(child)

    props.element.append(variable)
    props.variables.append(variable)
    return variable


def discard_unnamed_variables(props: EditableProperties) -> int:
    """Drop every variable that still has no name, and say how many went.  What Cancel
    calls.

    Add Variable puts a real <ProfileVariable> onto the element straight away, the way
    every other structural edit in this app does (the Scene designer's add/delete, Add
    Action) rather than holding it aside until a save -- values wait for a save, shapes
    do not.  For a Task or a Profile that lands on the working copy, so Cancel on the
    PARENT dialog still discards it; but Cancel on the properties dialog alone would
    otherwise leave a nameless variable behind for the parent's Ok to commit, and a
    variable with an empty <pvn> is not something Tasker would ever have written.

    A variable is only real once it is named, so an unnamed one is exactly the thing
    that was never finished being added.  Named ones are left alone -- Cancel is not
    an undo, for the same reason the Project dialog's Rename and Enabled are not undone
    by it.
    """
    unnamed = [index for index, variable in enumerate(props.variables) if not (variable.findtext("pvn") or "").strip()]
    for index in reversed(unnamed):
        remove_variable(props, index)
    return len(unnamed)


def remove_variable(props: EditableProperties, index: int) -> None:
    """Take a variable out, and renumber the sr= of the ones after it so they stay
    pv0..pvN-1 -- the contiguous numbering every Tasker-written object has.
    """
    if not 0 <= index < len(props.variables):
        return
    props.element.remove(props.variables.pop(index))
    for position, variable in enumerate(props.variables):
        variable.set("sr", f"pv{position}")
