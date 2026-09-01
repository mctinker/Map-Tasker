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
    for path in sorted(glob.glob(os.path.join(here, "XML", "*.xml"))):
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
    profedit._PROFILE_METADATA_TAGS warns about, and visible today on the hand-made
    Testaroo.prf.xml, whose <limit> sits after its <State>.

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
