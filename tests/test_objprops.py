"""Object Properties (objprops.py) Unit Tests

What is asserted here is a set of ENCODING RULES that were derived by measurement rather
than from documentation, and each one is a way to lose a user's data silently.  They were
read off the 42 sample backups in XML/ -- 880 Projects, 3,526 Profiles, 9,601 Tasks, 1,209
<ProfileVariable> elements -- and the counts in each docstring are what the derivation
rests on, so a future change that contradicts one has something concrete to argue with.

The three that bite hardest, all found by testing rather than by reading:

  * <showinnot> is INVERTED.  It appears only ever as 'false' (414 times) and is absent
    when the setting is on, so "write it when the box is ticked" would stamp
    <showinnot>false</showinnot> onto the 9,187 Tasks that have never had one.
  * A field with no widget must be PRESERVED, not blanked.  <clearout> is set by Tasker
    (462 variables) and has no control on the properties form; writing "" over it is
    invisible data loss on something the user was never shown.
  * <rty> holds an INDEX, not a label.  Writing the dropdown's text into it produces
    <rty>Abort Existing Task</rty>, which is not something Tasker can read back.

The round-trip test is the backstop for all of them at once: open every object in the
sample data, read what the dialog would show, apply it back unchanged, and require the XML
to come out byte-identical.  It is run twice -- once with every field supplied, and once
with only the subset the dialog actually builds widgets for, which is the pass that catches
the <clearout> class of bug.
"""

from __future__ import annotations

import copy
import functools
import glob
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import objprops

# The variable fields guiwins._build_variable_panel actually creates widgets for.  Anything
# outside this list reaches objprops only as "not supplied" and must survive untouched --
# see test_a_field_with_no_widget_is_preserved.
GUI_VARIABLE_FIELDS = (
    "pvt",
    "pvn",
    "pvci",
    "strout",
    "immutable",
    "pvv",
    "pvdn",
    "pvd",
    "exportval",
    "same_as_value",
)

# One Task carrying every scalar property and a fully-populated variable, and one carrying
# none of them -- the two ends the apply path has to handle.  Values are transcribed from
# real objects in XML/backup.xml (Task 'Test1' and its %poop variable).
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Task sr="task179">
    <cdate>1671835573104</cdate>
    <edate>1784481834342</edate>
    <id>179</id>
    <nme>Furnished</nme>
    <pc>Task Test1 Property</pc>
    <rty>2</rty>
    <showinnot>false</showinnot>
    <stayawake>true</stayawake>
    <ProfileVariable sr="pv0">
      <clearout>true</clearout>
      <exportval></exportval>
      <immutable>true</immutable>
      <pvci>true</pvci>
      <pvd>yes</pvd>
      <pvdn>Poop</pvdn>
      <pvid>179</pvid>
      <pvit>t</pvit>
      <pvn>%poop</pvn>
      <pvt>t</pvt>
      <pvv>6</pvv>
      <strout>true</strout>
    </ProfileVariable>
  </Task>
  <Task sr="task180">
    <cdate>1671835573104</cdate>
    <edate>1784481834342</edate>
    <id>180</id>
    <nme>Bare</nme>
    <pri>100</pri>
  </Task>
</TaskerData>
"""


def _task(name: str) -> ET.Element:
    root = ET.fromstring(_FIXTURE_XML)  # noqa: S314  (fixture text, defined in this file)
    return next(task for task in root.iter("Task") if task.findtext("nme") == name)


def _dialog_values(props: objprops.EditableProperties, fields: tuple[str, ...] = ()) -> dict[str, str]:
    """What the dialog's widgets would hold for this object, as apply_properties takes it.

    `fields` limits the per-variable half to a subset, which is how the GUI's own field set
    is simulated -- pass GUI_VARIABLE_FIELDS for that.
    """
    values = dict(objprops.scalar_values(props))
    for index, variable in enumerate(props.variables):
        read = objprops.variable_values(variable)
        for tag in fields or tuple(read):
            values[f"var{index}_{tag}"] = read[tag]
    return values


# --------------------------------------------------------------------------------------
# The backstop: every object in the sample data survives a no-op edit unchanged.
# --------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _sample_objects() -> tuple[tuple[str, str, ET.Element], ...]:
    """Parsed once and shared: the round-trip test deep-copies before mutating, so the two
    parametrizations cannot see each other's edits."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    found = []
    # The synthetic backup always, so this runs on CI too; any real backups in XML/ as well.
    synthetic = os.path.join(here, "tests", "data", "synthetic_backup.xml")
    for path in [synthetic, *sorted(glob.glob(os.path.join(here, "XML", "*.xml")))]:
        try:
            root = ET.parse(path).getroot()  # noqa: S314  (this repo's own sample data)
        except ET.ParseError:
            continue
        for kind, tag in (
            (objprops.KIND_TASK, "Task"),
            (objprops.KIND_PROJECT, "Project"),
            (objprops.KIND_PROFILE, "Profile"),
        ):
            found.extend((os.path.basename(path), kind, element) for element in root.iter(tag))
    return tuple(found)


@pytest.mark.parametrize("fields", [(), GUI_VARIABLE_FIELDS], ids=["every-field", "gui-subset"])
def test_a_no_op_edit_changes_no_object_in_the_sample_data(fields: tuple[str, ...]) -> None:
    """Open it, read what the dialog shows, put it straight back: nothing may move.

    Run twice.  "every-field" checks the model against itself.  "gui-subset" is the one
    that matters, because it supplies only what the form has widgets for -- the pass that
    fails if an unsupplied tag is blanked rather than preserved.
    """
    objects = _sample_objects()
    if not objects:
        pytest.skip("no sample XML in XML/ to measure against")

    changed = []
    for source, kind, element in objects:
        before = ET.tostring(element)
        working = copy.deepcopy(element)
        props = objprops.load_properties(kind, working)
        errors = objprops.apply_properties(props, _dialog_values(props, fields))
        if errors or ET.tostring(working) != before:
            changed.append(f"{source} {kind} {element.findtext('nme') or element.findtext('name')}: {errors}")

    assert not changed, f"{len(changed)} of {len(objects)} objects changed: {changed[:5]}"


# --------------------------------------------------------------------------------------
# Defaults are written by leaving the tag out
# --------------------------------------------------------------------------------------
def test_a_property_set_back_to_its_default_loses_its_tag() -> None:
    """Tasker omits <pc>, <rty>, <stayawake> and <showinnot> at their defaults, so setting
    one back has to REMOVE it rather than write the default in.  Writing it would make an
    object differ from its own backup in a tag nobody touched.
    """
    task = _task("Furnished")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    values = _dialog_values(props)
    values.update({"pc": "", "rty": "Abort New Task", "stayawake": "false", "showinnot": "true"})

    assert objprops.apply_properties(props, values) == []
    for tag in ("pc", "rty", "stayawake", "showinnot"):
        assert task.find(tag) is None, f"<{tag}> should have been removed at its default"


def test_show_in_notification_defaults_on_and_is_written_only_when_switched_off() -> None:
    """The inverted one.  <showinnot> appears only as 'false' in the sample data (414
    times), so its absence means the setting is ON -- and a Task left alone must not
    acquire one.
    """
    bare = _task("Bare")
    assert objprops.scalar_values(objprops.load_properties(objprops.KIND_TASK, bare))["showinnot"] == "true"

    props = objprops.load_properties(objprops.KIND_TASK, bare)
    values = _dialog_values(props)
    assert objprops.apply_properties(props, values) == []
    assert bare.find("showinnot") is None, "an untouched Task must not gain a <showinnot>"

    values["showinnot"] = "false"
    assert objprops.apply_properties(props, values) == []
    assert bare.findtext("showinnot") == "false"


def test_keep_device_awake_defaults_off_and_is_written_only_when_switched_on() -> None:
    """<stayawake>'s the other way up from <showinnot> -- only ever 'true' (62 times) --
    and the same one rule has to produce both.
    """
    bare = _task("Bare")
    props = objprops.load_properties(objprops.KIND_TASK, bare)
    values = _dialog_values(props)

    values["stayawake"] = "true"
    assert objprops.apply_properties(props, values) == []
    assert bare.findtext("stayawake") == "true"

    values["stayawake"] = "false"
    assert objprops.apply_properties(props, values) == []
    assert bare.find("stayawake") is None


# --------------------------------------------------------------------------------------
# Collision Handling is an index
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "expected"),
    [("Abort New Task", None), ("Abort Existing Task", "1"), ("Run Both Together", "2")],
)
def test_collision_handling_is_stored_as_its_index(label: str, expected: str | None) -> None:
    """<rty> holds 1 or 2 in all 836 Tasks that carry one, and never 0 -- the 8,765 without
    are the ones on the default.  So the dropdown's LABEL must become an index, and index 0
    must become no tag at all.
    """
    task = _task("Bare")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    values = _dialog_values(props)
    values["rty"] = label

    assert objprops.apply_properties(props, values) == []
    assert task.findtext("rty") == expected
    assert objprops.scalar_values(objprops.load_properties(objprops.KIND_TASK, task))["rty"] == label


# --------------------------------------------------------------------------------------
# What the form does not show, the form does not destroy
# --------------------------------------------------------------------------------------
def test_a_field_with_no_widget_is_preserved() -> None:
    """<clearout> and <pvid> have no control on the form.  Applying an edit that supplies
    only the fields the form does show must leave them exactly as they were.

    This is the regression that shipped and was caught in the running app: <clearout> went
    from 'true' to empty on a variable whose visible fields nobody had changed.
    """
    task = _task("Furnished")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    values = _dialog_values(props, GUI_VARIABLE_FIELDS)
    values["pc"] = "edited"

    assert objprops.apply_properties(props, values) == []
    variable = task.find("ProfileVariable")
    assert variable.findtext("clearout") == "true"
    assert variable.findtext("pvid") == "179"


def test_the_owner_kind_is_always_corrected() -> None:
    """<pvit> is the one unshown field that IS rewritten: it matches the owning element in
    all 1,209 sample variables with no exceptions (pj/pr/t), so it is fully determined and
    a wrong one is worth fixing rather than preserving.
    """
    task = _task("Furnished")
    task.find("ProfileVariable/pvit").text = "pj"
    props = objprops.load_properties(objprops.KIND_TASK, task)

    assert objprops.apply_properties(props, _dialog_values(props, GUI_VARIABLE_FIELDS)) == []
    assert task.findtext("ProfileVariable/pvit") == "t"


def test_a_comment_keeps_the_whitespace_the_user_typed() -> None:
    """Three Projects in the sample data end their <pc> with a space.  A comment is free
    text, so stripping it makes an untouched object differ from its own backup.
    """
    task = _task("Bare")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    values = _dialog_values(props)
    values["pc"] = "trailing space "

    assert objprops.apply_properties(props, values) == []
    assert task.findtext("pc") == "trailing space "


# --------------------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------------------
def test_a_new_variable_carries_the_child_set_tasker_writes() -> None:
    """All 11 non-<pvv> children are present in all 1,209 sample variables, so a
    MapTasker-made variable has to have them too -- and <pvv>, which Tasker omits for a
    variable with no value (381 of the 1,209), has to be absent while it has none.
    """
    task = _task("Bare")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    variable = objprops.add_variable(props)

    assert variable.get("sr") == "pv0"
    assert [child.tag for child in variable] == [
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
        "strout",
    ]
    assert variable.findtext("pvit") == "t"


def test_a_new_variable_inherits_pvid_from_its_siblings() -> None:
    """Every object in the sample data that carries variables gives all of them the same
    <pvid>, so matching the siblings is what Tasker itself would have done.  It is NOT the
    object's own id -- a Project's is a UUID, and for Tasks the two agree in only 39 of 570
    cases -- which is why it is inherited rather than computed.
    """
    task = _task("Furnished")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    assert objprops.add_variable(props).findtext("pvid") == "179"


def test_removing_a_variable_renumbers_the_rest() -> None:
    """Every Tasker-written object numbers its variables pv0..pvN-1 with no gaps."""
    task = _task("Bare")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    for _ in range(3):
        objprops.add_variable(props)

    objprops.remove_variable(props, 1)
    assert [variable.get("sr") for variable in task.findall("ProfileVariable")] == ["pv0", "pv1"]


def test_variables_are_written_last() -> None:
    """<ProfileVariable> is the final child in all 538 sample objects that have one, and a
    new scalar has to land among the lowercase children rather than after it.
    """
    task = _task("Bare")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    objprops.add_variable(props)
    values = _dialog_values(props, GUI_VARIABLE_FIELDS)
    values.update({"pc": "note", "var0_pvn": "%thing"})

    assert objprops.apply_properties(props, values) == []
    assert [child.tag for child in task] == [
        "cdate",
        "edate",
        "id",
        "nme",
        "pc",
        "pri",
        "ProfileVariable",
    ]


def test_same_as_value_mirrors_the_value_into_the_exported_one() -> None:
    """Tasker has no tag for "Same as Value" -- it just writes <exportval> equal to <pvv>,
    which is the state it is read back out of.
    """
    task = _task("Furnished")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    values = _dialog_values(props, GUI_VARIABLE_FIELDS)
    assert values["var0_same_as_value"] == "false"

    values["var0_same_as_value"] = "true"
    assert objprops.apply_properties(props, values) == []
    assert task.findtext("ProfileVariable/exportval") == "6"
    assert objprops.variable_values(props.variables[0])["same_as_value"] == "true"


def test_an_unnamed_variable_is_dropped_on_cancel() -> None:
    """Add Variable puts a real element on straight away, so Cancel has to take back the
    one that was never finished -- and leave the named ones alone.
    """
    task = _task("Furnished")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    objprops.add_variable(props)

    assert objprops.discard_unnamed_variables(props) == 1
    assert [variable.findtext("pvn") for variable in task.findall("ProfileVariable")] == ["%poop"]


# --------------------------------------------------------------------------------------
# Validation, and what is deliberately NOT an error
# --------------------------------------------------------------------------------------
def test_a_variable_must_be_named_like_a_variable() -> None:
    task = _task("Furnished")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    values = _dialog_values(props, GUI_VARIABLE_FIELDS)
    values["var0_pvn"] = "poop"

    assert objprops.apply_properties(props, values)
    assert task.findtext("ProfileVariable/pvn") == "%poop", "a failed apply must write nothing"


def test_a_duplicate_variable_name_warns_rather_than_blocking() -> None:
    """Real backups contain them -- the Project 'Виджет Авто' in XML/backup.xml declares
    %aaa twice.  Refusing to save would make the dialog impossible to close on an object
    the user had not even edited.
    """
    task = _task("Furnished")
    props = objprops.load_properties(objprops.KIND_TASK, task)
    objprops.add_variable(props)
    values = _dialog_values(props, GUI_VARIABLE_FIELDS)
    values["var1_pvn"] = "%poop"

    assert objprops.validate(props, values) == []
    assert objprops.warnings(props, values) == ["This Task declares '%poop' more than once."]
    assert objprops.apply_properties(props, values) == []


# --------------------------------------------------------------------------------------
# Profile: the scalars have to land where they cannot be mistaken for a condition
# --------------------------------------------------------------------------------------
_PROFILE_XML = """<Profile sr="prof12" ve="2">
  <cdate>1671835573104</cdate>
  <edate>1784481834342</edate>
  <id>12</id>
  <mid0>99</mid0>
  <nme>Watched</nme>
  <Time sr="con0"><fh>8</fh><fm>0</fm></Time>
  <State sr="con1" ve="2"><code>123</code></State>
</Profile>
"""


def test_profile_scalars_are_written_ahead_of_the_conditions() -> None:
    """condition.py's parse_profile_condition walks a Profile's children and joins them
    with "AND", skipping a fixed ignore list that does NOT include <pc> or <cldm>.  A
    non-condition child landing AFTER a real condition therefore appends a dangling
    ", AND " to the Map view's condition text -- the "document-order luck" caveat
    profedit._PROFILE_METADATA_TAGS warns about, and visible today on a hand-made
    test Profile export, whose <limit> sits after its <State>.

    Nothing here fixes that.  What this asserts is that the properties editor cannot
    TRIGGER it: conditions are uppercase-tagged and the scalars are lowercase, so
    set_child_text_in_tag_order always places them ahead of every condition.
    """
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    props = objprops.load_properties(objprops.KIND_PROFILE, profile)
    values = dict(objprops.scalar_values(props))
    values.update({"pc": "a note", "cldm": "00:00:05:00", "pri": "40"})

    assert objprops.apply_properties(props, values) == []
    tags = [child.tag for child in profile]
    assert tags == ["cdate", "cldm", "edate", "id", "mid0", "nme", "pc", "pri", "Time", "State"]
    assert profile.findtext("cldm") == "300"

    first_condition = min(tags.index("Time"), tags.index("State"))
    for tag in ("pc", "cldm", "pri"):
        assert tags.index(tag) < first_condition, f"<{tag}> must precede every condition"


def test_a_profile_priority_outside_the_slider_range_is_refused() -> None:
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    props = objprops.load_properties(objprops.KIND_PROFILE, profile)
    values = dict(objprops.scalar_values(props))
    values["pri"] = "51"

    assert objprops.apply_properties(props, values) == [
        f"Launch Task Priority must be between 0 and {objprops.MAX_LAUNCH_PRIORITY}.",
    ]
    assert profile.find("pri") is None


# --------------------------------------------------------------------------------------
# Profile: the repeat group, and the four settings Tasker keeps in <flags>
#
# THE BIT LAYOUT IS TASKER'S OWN, TRANSCRIBED IN objprops, NOT MEASURED.  None of these five
# settings appears in any of the 5,627 Profiles in XML/, so the sample data cannot check this
# half and these tests are the only thing holding it:
#
#   mask 1    Hide In Notification        Show In Notification, INVERTED
#   mask 2    Collapsed                   Tasker's list state -- no field, carried through
#   mask 4    Delete After Disable
#   mask 8    Ignore Settings             Restore Settings, INVERTED -- and SET on a new
#                                         Profile, so its tasker_default is "off"
#   mask 16   Ignore Task Order           Enforce Task Order, INVERTED
#   mask 32   Run Exit Task On Startup
#
# The five exports of one Profile made with Tasker 6.7.6 -- 8 and <limit> for Limit Repeats,
# 9 for "Enforce Task Order", 24 for "Show In Notification", 12 with <repeats> <dod> <limit>
# for Limit Repeats with a count of 5 and Delete On 0, 13 for that plus "Enforce Task Order"
# -- had the last two of those labels the wrong way round, which is how mask 16 came to be
# written when a user ticked Show In Notification.  What they do still establish is the tags:
# <repeats> holds the count, and <dod> is an older twin of mask 4 that this form leaves alone.
#
# <limit> IS THE DISABLED MARKER AND NOTHING ELSE.  It belongs to the Edit Profile dialog's
# Enabled switch, and test_the_editor_never_touches_the_disabled_marker is what keeps this
# form's hands off it.
# --------------------------------------------------------------------------------------
_ATEST_PROFILE_XML = """<Profile sr="prof858" ve="2">
  <cdate>1741625861232</cdate>
  <clp>true</clp>
  <dod>true</dod>
  <edate>1788358814481</edate>
  <flags>12</flags>
  <id>858</id>
  <limit>true</limit>
  <mid0>179</mid0>
  <nme>Atest2</nme>
  <repeats>5</repeats>
  <Time sr="con1"><fh>14</fh><fm>55</fm></Time>
</Profile>
"""


def _atest_profile() -> ET.Element:
    return ET.fromstring(_ATEST_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)


def _profile_values(profile: ET.Element) -> tuple[objprops.EditableProperties, dict]:
    props = objprops.load_properties(objprops.KIND_PROFILE, profile)
    return props, dict(objprops.scalar_values(props))


def test_the_profile_settings_read_off_the_export_tasker_wrote() -> None:
    """<flags>12</flags> is mask 4 plus mask 8: Delete After Disable on, Ignore Settings on,
    and neither of the two inverted bits -- so the two settings they invert read as ON, which
    is what a Profile that has never had them touched is.
    """
    _props, values = _profile_values(_atest_profile())

    assert values["repeats"] == "5"
    assert values["delete_after_disable"] == "true"  # mask 4
    assert values["restore_settings"] == "false"  # mask 8 set = settings ignored
    assert values["run_exit_task_on_startup"] == "false"  # mask 32, clear
    assert values["enforce_task_order"] == "true"  # mask 16 clear = not ignored
    assert values["profile_showinnot"] == "true"  # mask 1 clear = not hidden


_FLAGS_FIELDS = (
    "delete_after_disable",
    "restore_settings",
    "run_exit_task_on_startup",
    "enforce_task_order",
    "profile_showinnot",
)
# The value each field reads when its bit is CLEAR -- spec.default, which is what the stored
# form turns on, NOT the value an untouched Profile has (see _RESTORE_SETTINGS.tasker_default).
_FLAGS_DEFAULTS = {"delete_after_disable": "false", "restore_settings": "true",
                   "run_exit_task_on_startup": "false", "enforce_task_order": "true",
                   "profile_showinnot": "true"}  # fmt: skip


def test_each_flags_bit_reads_as_the_one_setting_it_holds() -> None:
    """One bit at a time, against Tasker's own values.  A bit landing on the wrong field is
    exactly the fault this table replaced -- ticking Show In Notification used to set mask 16,
    Ignore Task Order -- so each value is checked to move ONE field and leave the rest alone.
    """
    for flags, expected in (
        ("1", "profile_showinnot"),
        ("4", "delete_after_disable"),
        ("8", "restore_settings"),
        ("16", "enforce_task_order"),
        ("32", "run_exit_task_on_startup"),
    ):
        profile = _atest_profile()
        profile.find("flags").text = flags
        _props, values = _profile_values(profile)
        changed = {key for key in _FLAGS_FIELDS if values[key] != _FLAGS_DEFAULTS[key]}
        assert changed == {expected}, f"<flags>{flags}</flags> should mean {expected} and nothing else"


def test_show_in_notification_is_inverted_because_the_bit_says_hide() -> None:
    """Mask 1 is "hide in notification", so the bit is written when the box is UNticked -- the
    same shape a Task's <showinnot> has.  Getting this backwards would report every Profile in
    a backup as kept out of the notification, and would write the bit onto Profiles whose
    owner had never touched it.
    """
    profile = _atest_profile()
    props, values = _profile_values(profile)
    assert values["profile_showinnot"] == "true"

    values["profile_showinnot"] = "false"
    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "13"  # 12 + mask 1

    assert objprops.scalar_values(props)["profile_showinnot"] == "false"


def test_enforce_task_order_is_inverted_because_the_bit_says_ignore() -> None:
    """Mask 16 is "ignore task order", so enforcing it CLEARS the bit and switching it off
    sets one.
    """
    profile = _atest_profile()
    profile.find("flags").text = "28"  # 12 + mask 16
    props, values = _profile_values(profile)
    assert values["enforce_task_order"] == "false"

    values["enforce_task_order"] = "true"
    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "12"


def test_delete_after_disable_is_mask_4_and_leaves_an_older_dod_alone() -> None:
    """Mask 4 is where the setting lives; <dod> is the older twin the one sample Profile that
    has one carries alongside the bit.  This form reads and writes the bit and does not touch
    the tag, so a file that has both keeps both.
    """
    profile = _atest_profile()
    props, values = _profile_values(profile)
    values["delete_after_disable"] = "false"

    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "8"
    assert profile.findtext("dod") == "true", "an older <dod> is not this form's to rewrite"
    assert profile.findtext("limit") == "true", "the disabled marker is not this form's to clear"


def test_limit_repeats_is_not_a_field_at_all() -> None:
    """It has no bit -- mask 4 is Delete After Disable -- and the exports that ticked it wrote
    <repeats> and <limit> instead.  A checkbox for it was writing mask 4, so the count in
    Remaining Repeats is the whole of what this form offers.
    """
    _props, values = _profile_values(_atest_profile())
    assert "limit_repeats" not in values
    assert "repeats" in values


def test_the_editor_never_touches_the_disabled_marker() -> None:
    """<limit> belongs to profedit.set_profile_enabled and the Edit Profile dialog's Enabled
    switch.  A properties form that wrote it would disable Profiles behind the user's back --
    and one that removed it would enable them.
    """
    for start in ("true", None):
        profile = _atest_profile()
        if start is None:
            profile.remove(profile.find("limit"))
        props, values = _profile_values(profile)
        assert "limit" not in values, "no field may be bound to the disabled marker"

        values.update({key: "true" for key in _FLAGS_FIELDS})
        values["delete_after_disable"] = "false"
        assert objprops.apply_properties(props, values) == []
        assert profile.findtext("limit") == start


def test_restore_settings_is_inverted_because_the_bit_says_ignore() -> None:
    """Mask 8 is "ignore settings", so ticking Restore Settings CLEARS it.  The fixture has
    the bit, which is the state Tasker leaves a new Profile in.
    """
    profile = _atest_profile()
    props, values = _profile_values(profile)
    assert values["restore_settings"] == "false"

    values["restore_settings"] = "true"
    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "4"  # 12 - mask 8

    assert objprops.scalar_values(props)["restore_settings"] == "true"


def test_restore_settings_switched_off_is_not_a_property_a_profile_has() -> None:
    """THE REASON tasker_default EXISTS.  Tasker sets mask 8 on every Profile it creates --
    4,892 of the 5,627 samples carry it -- so "off" is Tasker's choice, not the user's, and
    counting it would have almost every Profile in a backup claim properties it has not got.
    Switched ON is the state worth noticing, and 735 sample Profiles are in it.
    """
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    ET.SubElement(profile, "flags").text = "10"  # mask 2 + mask 8, Tasker's new-Profile value
    assert objprops.has_properties(objprops.KIND_PROFILE, profile) is False

    profile.find("flags").text = "2"  # mask 8 cleared: the user has switched it on
    assert objprops.has_properties(objprops.KIND_PROFILE, profile) is True


def test_an_unreadable_flags_value_claims_no_bit_backed_property() -> None:
    """An unparseable value reads as every bit clear, which for Restore Settings is "switched
    on" -- so without objprops.bitfield_is_readable a Profile whose <flags> nobody can read
    would claim a property off the back of it.
    """
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    ET.SubElement(profile, "flags").text = "not a number"
    assert objprops.has_properties(objprops.KIND_PROFILE, profile) is False


def test_the_flags_bits_no_field_owns_are_carried_through() -> None:
    """Mask 2, Tasker's collapsed-in-the-list state, is the one bit no field owns.  A rewrite
    that dropped it would collapse Profiles on a real device, so the value is
    read-modified-written rather than built from the fields this dialog shows.
    """
    profile = _atest_profile()
    profile.find("flags").text = "42"  # masks 2, 8 and 32 -- mask 2 is the one with no field

    props, values = _profile_values(profile)
    assert values["run_exit_task_on_startup"] == "true"
    values["profile_showinnot"] = "false"
    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "43"  # 42 + mask 1

    values = dict(objprops.scalar_values(props))
    values["profile_showinnot"] = "true"
    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "42"


def test_a_bit_from_a_newer_tasker_is_carried_through_too() -> None:
    """The same rule, for a bit this table has never heard of: nothing above mask 32 is named,
    and none of the 5,586 sample values exceeds 63, but a value that does is Tasker's to
    define and ours to preserve.
    """
    profile = _atest_profile()
    profile.find("flags").text = "76"  # mask 64 (unknown) + mask 8 + mask 4

    props, values = _profile_values(profile)
    values["delete_after_disable"] = "false"
    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "72", "the unknown bit survives an edit to a known one"


def test_flags_is_removed_when_its_last_bit_is_cleared() -> None:
    """Tasker omits the element entirely rather than writing a 0 -- an exported Profile whose
    value would be 0 has no <flags> at all (profedit.create_new_profile).
    """
    profile = _atest_profile()
    profile.find("flags").text = "4"  # nothing set but Delete After Disable

    props, values = _profile_values(profile)
    values["delete_after_disable"] = "false"

    assert objprops.apply_properties(props, values) == []
    assert profile.find("flags") is None


def test_flags_is_not_created_by_a_profile_that_has_none() -> None:
    """The other end of the same rule: a Profile at every default must not gain a <flags>0>.
    The two inverted bits are what make this worth a test -- both fields read "true" here, and
    a build that took "true" for "write the bit" would stamp <flags>25</flags> onto the 41
    sample Profiles that have no <flags> at all.
    """
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    props, values = _profile_values(profile)
    assert values["delete_after_disable"] == "false"
    assert values["run_exit_task_on_startup"] == "false"
    assert values["restore_settings"] == "true"
    assert values["enforce_task_order"] == "true"
    assert values["profile_showinnot"] == "true"

    assert objprops.apply_properties(props, values) == []
    assert profile.find("flags") is None


def test_an_unreadable_flags_value_is_left_alone() -> None:
    """<flags> is Tasker's, not ours.  A value this build cannot parse is data to preserve,
    not something to replace with a number of our own.
    """
    profile = _atest_profile()
    profile.find("flags").text = "not a number"

    props, values = _profile_values(profile)
    assert objprops.apply_properties(props, values) == []
    assert profile.findtext("flags") == "not a number"


def test_the_repeat_group_is_cleared_by_removing_its_tags() -> None:
    """Same rule as every other property: the default is stored by leaving the tag out."""
    profile = _atest_profile()
    props, values = _profile_values(profile)
    values["repeats"] = ""

    assert objprops.apply_properties(props, values) == []
    assert profile.find("repeats") is None, "<repeats> should have been removed at its default"
    assert profile.findtext("dod") == "true", "<dod> belongs to no field and is not cleared with it"


def test_a_remaining_repeat_count_must_be_a_number() -> None:
    profile = _atest_profile()
    props, values = _profile_values(profile)
    values["repeats"] = "a few"

    assert objprops.apply_properties(props, values) == ["Remaining Repeats must be a whole number."]
    assert profile.findtext("repeats") == "5", "nothing may be written when validation fails"


def test_the_repeat_group_lands_in_taskers_child_order() -> None:
    """<repeats> and <flags> are new tags on an object that had neither, so they are placed
    rather than appended -- alphabetically among the lowercase children and ahead of every
    condition, which is what keeps condition.py from counting one as a context.
    """
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    props, values = _profile_values(profile)
    values.update({"repeats": "3", "delete_after_disable": "true"})

    assert objprops.apply_properties(props, values) == []
    assert [child.tag for child in profile] == [
        "cdate",
        "edate",
        "flags",
        "id",
        "mid0",
        "nme",
        "repeats",
        "Time",
        "State",
    ]


def test_a_flags_bit_on_its_own_counts_as_having_properties() -> None:
    """The button reads "Edit Properties" for an object that has some.  A bitfield tag holds
    several settings at once, so its presence proves nothing -- only the one bit does, or
    every Profile with a <flags> (5,586 of the 5,627 samples) would claim properties it has
    not got, 4,009 of them for the value Tasker gives a brand-new Profile.
    """
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    # 10 is Tasker's own new-Profile value: mask 2, which no field owns, plus mask 8, which
    # Restore Settings owns and reads as the state Tasker leaves (see its tasker_default).
    ET.SubElement(profile, "flags").text = "10"

    assert objprops.has_properties(objprops.KIND_PROFILE, profile) is False

    profile.find("flags").text = "11"  # + mask 1: Show In Notification switched off
    assert objprops.has_properties(objprops.KIND_PROFILE, profile) is True


def test_the_exported_profile_survives_a_no_op_edit() -> None:
    """The sample-data backstop cannot cover these five -- no Profile in XML/ carries one --
    so the export they were measured from gets the same treatment: open it, read what the
    dialog would show, put it straight back, and require every byte to be where it was.
    """
    profile = _atest_profile()
    before = ET.tostring(profile)
    props, values = _profile_values(profile)

    assert objprops.apply_properties(props, values) == []
    assert ET.tostring(profile) == before


# --------------------------------------------------------------------------------------
# Project: the copy and the live element have to stay level
# --------------------------------------------------------------------------------------
def test_mirroring_replaces_the_targets_properties_wholesale() -> None:
    """What projedit.apply_properties_to_live_tree uses to carry a Project's edits from
    the working copy onto the live element.  A second apply_properties would not do: Add
    and Remove Variable happen on the copy alone, so the two disagree on how many
    variables there are.
    """
    source = _task("Furnished")
    target = _task("Furnished")
    # Diverge the target the way an un-mirrored live element would be.
    target.find("pc").text = "stale"
    target.remove(target.find("ProfileVariable"))
    target.find("stayawake").text = "true"

    props = objprops.load_properties(objprops.KIND_TASK, source)
    objprops.add_variable(props)
    values = _dialog_values(props, GUI_VARIABLE_FIELDS)
    values["var1_pvn"] = "%second"
    assert objprops.apply_properties(props, values) == []

    objprops.mirror_properties(objprops.KIND_TASK, source, target)

    assert target.findtext("pc") == "Task Test1 Property"
    assert [v.findtext("pvn") for v in target.findall("ProfileVariable")] == ["%poop", "%second"]
    assert ET.tostring(target) == ET.tostring(source)


def test_mirroring_removes_a_property_the_source_no_longer_has() -> None:
    """Absence is how a default is recorded, so a tag left behind on the target would read
    as a setting the user had just switched off.
    """
    source = _task("Furnished")
    target = _task("Furnished")

    props = objprops.load_properties(objprops.KIND_TASK, source)
    values = _dialog_values(props, GUI_VARIABLE_FIELDS)
    values.update({"pc": "", "stayawake": "false"})
    assert objprops.apply_properties(props, values) == []

    objprops.mirror_properties(objprops.KIND_TASK, source, target)
    assert target.find("pc") is None
    assert target.find("stayawake") is None


def test_mirroring_leaves_everything_that_is_not_a_property_alone() -> None:
    """It replaces the properties, not the object: the target's own identity and content
    are none of its business.
    """
    source = _task("Furnished")
    target = _task("Furnished")
    target.find("id").text = "999"
    target.find("nme").text = "Live"

    objprops.mirror_properties(objprops.KIND_TASK, source, target)
    assert target.findtext("id") == "999"
    assert target.findtext("nme") == "Live"


# --------------------------------------------------------------------------------------
# Cooldown: seconds in the XML, dd:hh:mm:ss on screen
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("seconds", "shown"),
    [("", ""), ("0", "00:00:00:00"), ("5", "00:00:00:05"), ("93784", "01:02:03:04"), ("86400", "01:00:00:00")],
)
def test_a_cooldown_survives_being_shown(seconds: str, shown: str) -> None:
    assert objprops.format_cooldown(seconds) == shown
    assert objprops.parse_cooldown(shown) == seconds


def test_the_cooldown_format_is_written_from_one_constant() -> None:
    """The label, the two conversions and the error message all have to agree about the
    separator, so they all read it from COOLDOWN_SEPARATOR rather than spelling it out.
    """
    assert objprops.COOLDOWN_FORMAT == "dd:hh:mm:ss"
    assert objprops.COOLDOWN_SEPARATOR in objprops.format_cooldown("93784")


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("30", "30"), ("5:00", "300"), ("1:00:00", "3600"), ("", ""), ("x", None), ("1:2:3:4:5", None)],
)
def test_a_cooldown_can_be_typed_short(typed: str, expected: str | None) -> None:
    """Shorter forms are read from the right, the way a person types them: "5:00" is five
    minutes, not five days.
    """
    assert objprops.parse_cooldown(typed) == expected


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("01.02.03.04", "93784"), ("5.00", "300"), ("1.2.3.4.5", None), ("1.2:3", None)],
)
def test_a_cooldown_typed_the_old_way_still_reads(typed: str, expected: str | None) -> None:
    """'.' was the separator before ':' replaced it, and a Cooldown typed the old way is
    still what the person meant -- so both are accepted on the way in, while only ':' is
    ever shown.  Mixing the two is refused rather than guessed at.
    """
    assert objprops.parse_cooldown(typed) == expected


def test_a_cooldown_that_does_not_parse_is_an_error_and_writes_nothing() -> None:
    task = _task("Bare")
    props = objprops.load_properties(objprops.KIND_PROFILE, task)
    values = dict(objprops.scalar_values(props))
    values["cldm"] = "not a time"

    assert objprops.apply_properties(props, values)
    assert task.find("cldm") is None
