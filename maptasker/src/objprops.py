#! /usr/bin/env python3
"""objprops: the Properties panel shared by Project, Profile, Task and Scene.

What Tasker calls an object's Properties is a handful of scalar children plus any
number of <ProfileVariable> children.  The three non-Scene kinds differ only in WHICH
scalars they show -- the variables half is byte-identical between them, down to the
element name (a Task's variables are <ProfileVariable> too; only <pvit> says which
kind owns them).  So the scalars are a table (OBJECT_PROPERTIES) and everything else
is one code path.

A Scene's properties are a <PropertiesElement> instead, generated from arg_dict and
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
# a Project's <id> is a UUID while its pvid is a small integer (Smart Reminders is
# id=d69311f4-... pvid=1), and for Tasks the two agree in only 39 of 570 cases.  It
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
    """

    key: str  # field_refs key, unique within the dialog
    tag: str  # child tag of the object element
    label: str
    kind: str  # "text" | "checkbox" | "choice" | "slider" | "duration"
    default: str  # the value at which the tag is removed rather than written
    choices: tuple[str, ...] = ()
    tooltip: str = ""
    maximum: int = 0  # slider only


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

# Which scalars each kind shows, in the order Tasker shows them.
#
# THE PROFILE ROW IS INCOMPLETE ON PURPOSE.  Limit Repeats, Remaining Repeats, Delete On
# Zero Repeats, Enforce Task Order and Show In Notification have no tag in ANY of the
# 3,526 Profiles across the sample backups, so there is nothing to transcribe.  The two
# candidates are <clp> (462 Profiles, always the literal 'true', read by nothing in
# MapTasker) and bits of <flags> -- profedit.create_new_profile's docstring already
# establishes that bits 0/3/4/5 are "stable per-Profile settings with no other XML
# representation", which is this exact group.  But Remaining Repeats is a NUMBER and a
# bitfield cannot hold it, so at least one more tag exists that no sample carries.
#
# They are left out rather than guessed: a wrong <flags> bit changes some other
# behaviour on a real device.  To settle it, export one Profile, toggle one setting at a
# time in Tasker, re-export, and diff the pairs with xmldiff.py -- six exports covers all
# five.  Each then becomes one more row here and nothing else changes.
OBJECT_PROPERTIES: dict[str, tuple[PropField, ...]] = {
    KIND_PROJECT: (_COMMENTS,),
    KIND_PROFILE: (_LAUNCH_PRIORITY, _COOLDOWN, _COMMENTS),
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


def has_properties(kind: str, element: defusedxml.ElementTree.Element) -> bool:
    """Does this object have any properties set?  Decides whether the button in the
    Add/Edit dialog reads "Add Properties" or "Edit Properties".

    A tag holding its own default does not count -- that is the state Tasker would have
    written nothing for, so offering "Edit" for it would be claiming properties the
    object does not have.

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
        (element.findtext(spec.tag) or "") not in ("", spec.default) for spec in OBJECT_PROPERTIES.get(kind, ())
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
        elif spec.kind == "slider" and raw and not raw.isdigit():
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
    hand-made Testaroo.prf.xml.  Appending instead would put <pc> after <ProfileVariable>,
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
        # that parent.append() rejects.  Same note as projedit._set_child_text.
        child = type(parent)(tag)
        position = next(
            (
                index
                for index, sibling in enumerate(parent)
                if (sibling.tag[:1].isupper() or sibling.tag > tag)
            ),
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

    for index, variable in enumerate(props.variables):
        supplied = {
            tag: values[key]
            for tag in (*_VARIABLE_CHILDREN, "same_as_value")
            if (key := f"var{index}_{tag}") in values
        }
        _write_variable(props.kind, variable, supplied)

    return []


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
