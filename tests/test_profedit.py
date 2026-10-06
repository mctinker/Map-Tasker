"""profedit: the Profile editor's model -- what it reads, what it refuses, what it writes.

Edit Profile and Add Profile work on a deep copy of a Profile and only ever write the copy;
the loaded configuration changes at a handful of named points (register, add to a Project,
delete, apply, rename).  These tests hold both halves: that the copy is the only thing an
edit touches, and that each of those points leaves the tables and the Projects consistent.

Every condition type is exercised -- Time, Day, App and Loc, which have their own field
readers and writers, and State and Event, which borrow taskedit's argument machinery -- along
with the validation that must refuse a bad value before anything is written (all-or-nothing),
the Entry/Exit Task links, and the standalone export.

The fixture is built here from XML text, in the shape taskerd gives the tables, so no
personal backup is needed.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import editcommon, profedit, sessundo
from maptasker.src.primitem import PrimeItems

from tests.test_mapswap import _load

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>100,101,102,103,104</pids>
    <tids>20,21</tids>
    <mdate>1</mdate>
  </Project>
  <Project sr="proj1" ve="2">
    <name>Work</name>
    <pids>104</pids>
    <tids>22</tids>
  </Project>
  <Profile sr="prof100" ve="2">
    <cdate>1</cdate>
    <id>100</id>
    <mid0>20</mid0>
    <mid1>21</mid1>
    <nme>Morning</nme>
    <Time sr="con0">
      <cname>early</cname>
      <fh>8</fh>
      <fm>5</fm>
      <th>21</th>
      <tm>30</tm>
      <rep>2</rep>
      <repval>15</repval>
    </Time>
  </Profile>
  <Profile sr="prof101" ve="2">
    <id>101</id>
    <limit>true</limit>
    <mid0>20</mid0>
    <nme>Weekdays</nme>
    <Day sr="con0">
      <wday0>2</wday0>
      <wday1>3</wday1>
      <mnth0>0</mnth0>
      <mday0>1</mday0>
      <mday1>32</mday1>
    </Day>
  </Profile>
  <Profile sr="prof102" ve="2">
    <id>102</id>
    <mid0>20</mid0>
    <mid1>20</mid1>
    <nme>Apps</nme>
    <App sr="con0">
      <flags>2</flags>
      <cls0>com.a.Main</cls0>
      <label0>Alpha</label0>
      <pkg0>com.a</pkg0>
      <cls1/>
      <label1>Beta</label1>
      <pkg1>com.b</pkg1>
    </App>
  </Profile>
  <Profile sr="prof103" ve="2">
    <id>103</id>
    <mid0>21</mid0>
    <nme>Where</nme>
    <Loc sr="con0">
      <lat>40.7</lat>
      <long>-74.0</long>
      <rad>100</rad>
    </Loc>
  </Profile>
  <Profile sr="prof104" ve="2">
    <id>104</id>
    <nme>Triggers</nme>
    <State sr="con0" ve="2">
      <code>123</code>
      <Int sr="arg0" val="1"/>
    </State>
    <Event sr="con1" ve="2">
      <code>7</code>
      <pri>0</pri>
      <Int sr="arg0" val="1"/>
      <Str sr="arg1" ve="3">Mum</Str>
      <Str sr="arg2" ve="3"/>
      <Str sr="arg3" ve="3"/>
      <Str sr="arg4" ve="3"/>
    </Event>
    <State sr="con2" ve="2">
      <code>99999</code>
    </State>
  </Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Entry</nme></Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Exit</nme></Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Other</nme></Task>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def _backup() -> None:
    _load(_XML)


def _edit(name: str) -> profedit.EditableProfile:
    edited = profedit.load_profile_for_edit(name, state=PrimeItems)
    assert edited is not None
    return edited


def _only(edited: profedit.EditableProfile) -> profedit.EditableCondition:
    (condition,) = edited.conditions
    return condition


def _xml(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode")


def _field(cond_index: int, name: str) -> str:
    return profedit.condition_field_key(cond_index, name)


def _live(name: str) -> ET.Element:
    return PrimeItems.tasker_root_elements["all_profiles_by_name"][name]["xml"]


def _project(name: str) -> ET.Element:
    return PrimeItems.tasker_root_elements["all_projects"][name]["xml"]


# ##################################################################################
# Loading, and the copy being the only thing an edit touches.
# ##################################################################################
def test_a_profile_is_found_by_its_name() -> None:
    profile_id, element = profedit.resolve_profile_by_name("Morning", state=PrimeItems)

    assert profile_id == "100"
    assert element is _live("Morning")
    assert profedit.resolve_profile_by_name("Nobody", state=PrimeItems) is None
    assert profedit.load_profile_for_edit("Nobody", state=PrimeItems) is None


def test_loading_gives_a_copy_with_its_conditions_and_tasks() -> None:
    edited = _edit("Morning")

    assert edited.profile_id == "100"
    assert (edited.entry_task_id, edited.exit_task_id) == ("20", "21")
    assert edited.profile_element is not _live("Morning")
    assert [(c.cond_index, c.cond_type) for c in edited.conditions] == [(0, "Time")]


def test_metadata_and_task_links_are_not_conditions() -> None:
    edited = _edit("Weekdays")

    assert [c.cond_type for c in edited.conditions] == ["Day"]
    assert _edit("Triggers").conditions[0].cond_index == 0
    assert [c.cond_type for c in _edit("Triggers").conditions] == ["State", "Event", "State"]


def test_editing_the_copy_leaves_the_loaded_profile_alone() -> None:
    before = _xml(_live("Morning"))
    edited = _edit("Morning")
    profedit.set_profile_enabled(edited, enabled=False)
    profedit.link_task_to_profile(edited, "22", "Entry")
    profedit.remove_condition_from_profile(edited, 0)
    assert profedit.apply_edits_to_profile(edited, "Renamed", {}, state=PrimeItems) == []

    assert _xml(_live("Morning")) == before


# ##################################################################################
# Creating a Profile.
# ##################################################################################
def test_a_new_profile_has_the_metadata_real_ones_have() -> None:
    created = profedit.create_new_profile("  Fresh ", state=PrimeItems)

    assert isinstance(created, profedit.EditableProfile)
    element = created.profile_element
    assert element.get("sr") == f"prof{created.profile_id}"
    assert [child.tag for child in element] == ["cdate", "edate", "flags", "id", "nme"]
    assert element.findtext("nme") == "Fresh"
    assert element.findtext("id") == created.profile_id
    assert element.findtext("flags") == profedit.NEW_PROFILE_FLAGS == "10"
    assert created.conditions == []
    # One counter for Profiles and Tasks: the id is not one either already uses.
    assert created.profile_id not in {"100", "101", "102", "103", "104", "20", "21", "22"}


def test_a_new_profile_needs_a_backup_to_take_an_id_from(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "xml_root", None)

    assert "Load a Tasker backup" in profedit.create_new_profile("x", state=PrimeItems)


# ##################################################################################
# Conditions: reading, naming, adding, removing.
# ##################################################################################
def test_state_and_event_conditions_carry_their_arguments() -> None:
    state_condition, event_condition, unmapped = _edit("Triggers").conditions

    assert [a.arg_id for a in state_condition.args] == ["0"]
    assert [a.arg_id for a in event_condition.args] == ["0", "1", "2", "3", "4"]
    assert {a.arg_id: a.current_value for a in event_condition.args}["1"] == "Mum"
    # A code this table has never heard of has nothing to edit.
    assert unmapped.args == []


def test_a_condition_is_named_for_what_it_is() -> None:
    state_condition, event_condition, unmapped = _edit("Triggers").conditions

    assert profedit.get_condition_display_name(state_condition) == "State: Display State"
    assert profedit.get_condition_display_name(event_condition) == "Event: Received Text"
    assert profedit.get_condition_display_name(unmapped) == "State (code 99999 not mapped)"
    assert profedit.get_condition_display_name(_only(_edit("Morning"))) == "Time"


def test_argument_models_are_rebuilt_on_request() -> None:
    condition = _edit("Triggers").conditions[1]
    condition.args = []

    profedit.reclassify_condition_args(condition, state=PrimeItems)
    assert len(condition.args) == 5

    time_condition = _only(_edit("Morning"))
    profedit.reclassify_condition_args(time_condition, state=PrimeItems)
    assert time_condition.args == []


def test_conditions_are_found_by_index() -> None:
    edited = _edit("Triggers")

    assert profedit.find_condition(edited, 1) is edited.conditions[1]
    assert profedit.find_condition(edited, 9) is None
    assert profedit.condition_arg_key(2, "1") == "cond2_arg1"
    assert profedit.condition_field_key(2, "lat") == "cond2_lat"


def test_removing_a_condition_renumbers_the_rest() -> None:
    edited = _edit("Triggers")

    profedit.remove_condition_from_profile(edited, 0)

    assert [c.cond_type for c in edited.conditions] == ["Event", "State"]
    assert [c.cond_index for c in edited.conditions] == [0, 1]
    assert [c.condition_element.get("sr") for c in edited.conditions] == ["con0", "con1"]
    assert [child.tag for child in edited.profile_element if child.tag in ("State", "Event")] == ["Event", "State"]


def test_removing_a_condition_that_is_not_there_does_nothing() -> None:
    edited = _edit("Triggers")
    before = _xml(edited.profile_element)

    profedit.remove_condition_from_profile(edited, 7)

    assert _xml(edited.profile_element) == before


@pytest.mark.parametrize(
    ("cond_type", "children"),
    [
        ("Time", {"fh": "0", "fm": "0", "th": "0", "tm": "0"}),
        ("App", {"flags": "2"}),
        ("Loc", {"lat": "", "long": "", "rad": ""}),
        ("Day", {}),
    ],
)
def test_a_new_condition_starts_from_sensible_defaults(cond_type: str, children: dict[str, str]) -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)

    added = profedit.add_condition_to_profile(edited, cond_type)

    assert isinstance(added, profedit.EditableCondition)
    assert added.condition_element in list(edited.profile_element)
    assert added.condition_element.get("sr") == "con0"
    assert {child.tag: (child.text or "") for child in added.condition_element} == children
    assert edited.conditions == [added]


def test_conditions_added_one_after_another_are_numbered_in_order() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)

    first = profedit.add_condition_to_profile(edited, "Time")
    second = profedit.add_condition_to_profile(edited, "Loc")

    assert (first.cond_index, second.cond_index) == (0, 1)
    assert second.condition_element.get("sr") == "con1"


@pytest.mark.parametrize("cond_type", ["Event", "State", "Nonsense", ""])
def test_only_the_flat_condition_types_are_added_by_type_name(cond_type: str) -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)

    refused = profedit.add_condition_to_profile(edited, cond_type)

    assert isinstance(refused, list)
    assert "isn't supported here" in refused[0]
    assert edited.conditions == []


# ##################################################################################
# Events and States, added by code.
# ##################################################################################
def test_the_addable_events_and_states_are_listed_with_their_reasons() -> None:
    events = profedit.list_addable_events(state=PrimeItems)
    states = profedit.list_addable_states(state=PrimeItems)

    assert len(events) > 100
    assert len(states) > 50
    assert all(row["condition_key"].endswith("e") for row in events)
    assert all(row["condition_key"].endswith("s") for row in states)
    assert [row["name"] for row in events] == sorted(row["name"] for row in events)
    refused = [row for row in events if not row["addable"]]
    assert refused
    assert all(row["reason"] for row in refused)
    assert {"condition_key", "code", "name", "category_name", "addable", "reason"} <= events[0].keys()


def test_the_list_is_remembered_between_calls() -> None:
    assert profedit.list_addable_events(state=PrimeItems) is profedit.list_addable_events(state=PrimeItems)
    assert profedit.list_addable_events(state=PrimeItems) is not profedit.list_addable_states(state=PrimeItems)


def test_an_event_is_added_with_a_priority_and_its_arguments() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)

    added = profedit.add_event_condition_to_profile(edited, "7e", state=PrimeItems)

    assert isinstance(added, profedit.EditableCondition)
    assert added.cond_type == "Event"
    assert [child.tag for child in added.condition_element][:2] == ["code", "pri"]
    assert added.condition_element.findtext("code") == "7"
    assert added.condition_element.findtext("pri") == "0"
    assert [a.arg_id for a in added.args] == ["0", "1", "2", "3", "4"]


def test_a_state_is_added_without_a_priority() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)

    added = profedit.add_state_condition_to_profile(edited, "123s", state=PrimeItems)

    assert isinstance(added, profedit.EditableCondition)
    assert added.cond_type == "State"
    assert added.condition_element.find("pri") is None
    assert added.condition_element.findtext("code") == "123"
    assert [a.arg_id for a in added.args] == ["0"]


def test_a_code_that_cannot_be_built_is_refused_and_added_nowhere() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)
    refused_key = next(
        row["condition_key"] for row in profedit.list_addable_events(state=PrimeItems) if not row["addable"]
    )

    for result in (
        profedit.add_event_condition_to_profile(edited, refused_key, state=PrimeItems),
        profedit.add_event_condition_to_profile(edited, "999999999e", state=PrimeItems),
    ):
        assert isinstance(result, list)
        assert result[0]
    assert edited.conditions == []


# ##################################################################################
# Entry and Exit Tasks, and enabled.
# ##################################################################################
def test_linking_a_task_replaces_the_one_before() -> None:
    edited = _edit("Morning")

    profedit.link_task_to_profile(edited, "22", "Entry")
    profedit.link_task_to_profile(edited, "22", "Exit")

    assert (edited.entry_task_id, edited.exit_task_id) == ("22", "22")
    assert edited.profile_element.findtext("mid0") == "22"
    assert edited.profile_element.findtext("mid1") == "22"
    assert len(edited.profile_element.findall("mid0")) == 1


def test_a_new_link_goes_before_the_name_where_tasker_puts_it() -> None:
    """profiles.get_profile_tasks stops at <nme>: a link after it would be silently dropped."""
    edited = profedit.create_new_profile("P", state=PrimeItems)

    profedit.link_task_to_profile(edited, "20", "Entry")
    profedit.link_task_to_profile(edited, "21", "Exit")

    tags = [child.tag for child in edited.profile_element]
    assert tags.index("mid0") < tags.index("nme")
    assert tags.index("mid1") < tags.index("nme")


def test_a_link_is_appended_when_there_is_no_name_yet() -> None:
    element = ET.Element("Profile")

    profedit._set_profile_task_link(element, "mid0", "5")  # noqa: SLF001

    assert [(child.tag, child.text) for child in element] == [("mid0", "5")]


def test_unlinking_removes_the_reference_and_not_the_task() -> None:
    edited = _edit("Morning")

    profedit.unlink_task_from_profile(edited, "Entry")
    profedit.unlink_task_from_profile(edited, "Exit")
    profedit.unlink_task_from_profile(edited, "Exit")  # Nothing left to remove; not an error.

    assert (edited.entry_task_id, edited.exit_task_id) == ("", "")
    assert edited.profile_element.find("mid0") is None
    assert edited.profile_element.find("mid1") is None
    assert "20" in PrimeItems.tasker_root_elements["all_tasks"]


def test_a_profile_is_enabled_unless_limited() -> None:
    assert profedit.is_profile_enabled(_edit("Morning")) is True
    assert profedit.is_profile_enabled(_edit("Weekdays")) is False


def test_disabling_and_enabling_write_and_remove_the_limit() -> None:
    edited = _edit("Morning")

    profedit.set_profile_enabled(edited, enabled=False)
    assert edited.profile_element.findtext("limit") == "true"
    assert profedit.is_profile_enabled(edited) is False

    profedit.set_profile_enabled(edited, enabled=True)
    assert edited.profile_element.find("limit") is None
    profedit.set_profile_enabled(edited, enabled=True)  # Already enabled; still fine.
    assert profedit.is_profile_enabled(edited) is True


# ##################################################################################
# Time.
# ##################################################################################
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8:05am", ("time", "08:05 AM")),
        ("08:05 AM", ("time", "08:05 AM")),
        ("12:00 pm", ("time", "12:00 PM")),
        (" 9:30 Pm ", ("time", "09:30 PM")),
        ("%mytime", ("var", "%mytime")),
        ("13:00 PM", None),
        ("0:30 AM", None),
        ("8:60 AM", None),
        ("8:05", None),
        ("noon", None),
        ("%", None),
        ("% a", None),
        ("", None),
    ],
)
def test_a_time_is_a_twelve_hour_clock_time_or_a_variable(raw: str, expected: tuple[str, str] | None) -> None:
    assert profedit._classify_time_or_var(raw) == expected  # noqa: SLF001


@pytest.mark.parametrize(
    ("hour", "minute", "text"),
    [
        (0, 0, "12:00 AM"),
        (0, 5, "12:05 AM"),
        (9, 30, "09:30 AM"),
        (12, 0, "12:00 PM"),
        (13, 7, "01:07 PM"),
        (23, 59, "11:59 PM"),
    ],
)
def test_a_twenty_four_hour_time_reads_as_twelve(hour: int, minute: int, text: str) -> None:
    assert profedit._format_12_hour(hour, minute) == text  # noqa: SLF001


def test_a_time_condition_reads_for_display() -> None:
    assert profedit.get_time_field_values(_only(_edit("Morning"))) == {
        "start_time": "08:05 AM",
        "end_time": "09:30 PM",
        "rep_unit": "Minutes",
        "rep_value": "15",
    }


def test_a_time_condition_with_variables_and_no_repeat_reads_for_display() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)
    condition = profedit.add_condition_to_profile(edited, "Time")
    for tag, text in (("fromvar", "%start"), ("tovar", "%stop")):
        ET.SubElement(condition.condition_element, tag).text = text

    assert profedit.get_time_field_values(condition) == {
        "start_time": "%start",
        "end_time": "%stop",
        "rep_unit": "Hours",
        "rep_value": "",
    }


def test_garbage_in_the_hour_and_minute_reads_as_midnight() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)
    condition = profedit.add_condition_to_profile(edited, "Time")
    condition.condition_element.find("fh").text = "soon"
    condition.condition_element.find("fm").text = None

    assert profedit.get_time_field_values(condition)["start_time"] == "12:00 AM"
    assert profedit._int_or_zero(None) == 0  # noqa: SLF001


def _time_values(**changes: str) -> dict[str, str]:
    values = {
        _field(0, "start_time"): "8:05 AM",
        _field(0, "end_time"): "9:30 PM",
        _field(0, "rep_unit"): "Minutes",
        _field(0, "rep_value"): "15",
    }
    values.update({_field(0, key): value for key, value in changes.items()})
    return values


def test_time_values_are_written_as_twenty_four_hour_numbers() -> None:
    edited = _edit("Morning")

    errors = profedit.apply_edits_to_profile(
        edited,
        "Morning",
        _time_values(start_time="12:00 AM", end_time="12:30 PM", rep_unit="Hours", rep_value="2"),
        state=PrimeItems,
    )

    assert errors == []
    element = _only(edited).condition_element
    assert [element.findtext(tag) for tag in ("fh", "fm", "th", "tm")] == ["0", "0", "12", "30"]
    assert (element.findtext("rep"), element.findtext("repval")) == ("1", "2")
    assert element.findtext("cname") == "early"  # Not edited here; left alone.


def test_a_variable_replaces_the_literal_time_and_the_other_way_round() -> None:
    edited = _edit("Morning")

    assert profedit.apply_edits_to_profile(edited, "Morning", _time_values(start_time="%begin"), state=PrimeItems) == []
    element = _only(edited).condition_element
    assert element.findtext("fromvar") == "%begin"
    assert element.find("fh") is None
    assert element.find("fm") is None
    assert element.findtext("th") == "21"

    assert (
        profedit.apply_edits_to_profile(edited, "Morning", _time_values(start_time="7:15 pm"), state=PrimeItems) == []
    )
    assert element.find("fromvar") is None
    assert (element.findtext("fh"), element.findtext("fm")) == ("19", "15")


def test_a_blank_repeat_removes_it() -> None:
    edited = _edit("Morning")

    assert profedit.apply_edits_to_profile(edited, "Morning", _time_values(rep_value="  "), state=PrimeItems) == []

    element = _only(edited).condition_element
    assert element.find("rep") is None
    assert element.find("repval") is None


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"start_time": "late"}, "'Start Time' must be a valid time"),
        ({"end_time": ""}, "'End Time' must be a valid time"),
        ({"rep_value": "0"}, "'Every' must be a positive whole number"),
        ({"rep_value": "-3"}, "'Every' must be a positive whole number"),
        ({"rep_value": "1.5"}, "'Every' must be a positive whole number"),
        ({"rep_unit": "Days"}, "'Every' unit must be Hours or Minutes"),
    ],
)
def test_a_bad_time_value_is_refused_and_nothing_is_written(changes: dict[str, str], fragment: str) -> None:
    edited = _edit("Morning")
    before = _xml(edited.profile_element)

    errors = profedit.apply_edits_to_profile(edited, "Renamed", _time_values(**changes), state=PrimeItems)

    assert any(fragment in error for error in errors), errors
    assert _xml(edited.profile_element) == before  # All or nothing: not even the new name.


# ##################################################################################
# Loc.
# ##################################################################################
def _loc_values(**changes: str) -> dict[str, str]:
    values = {_field(0, "lat"): "51.5", _field(0, "long"): " -0.12 ", _field(0, "rad"): "250"}
    values.update({_field(0, key): value for key, value in changes.items()})
    return values


def test_a_location_reads_and_writes() -> None:
    edited = _edit("Where")
    assert profedit.get_loc_field_values(_only(edited)) == {"lat": "40.7", "long": "-74.0", "rad": "100"}

    assert profedit.apply_edits_to_profile(edited, "Where", _loc_values(), state=PrimeItems) == []

    assert profedit.get_loc_field_values(_only(edited)) == {"lat": "51.5", "long": "-0.12", "rad": "250"}


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"lat": ""}, "'Latitude' cannot be empty."),
        ({"long": "  "}, "'Longitude' cannot be empty."),
        ({"rad": "wide"}, "'Radius' must be a number."),
        ({"lat": "north"}, "'Latitude' must be a number."),
        ({"rad": "-1"}, "'Radius' must not be negative."),
    ],
)
def test_a_bad_location_is_refused(changes: dict[str, str], fragment: str) -> None:
    edited = _edit("Where")
    before = _xml(edited.profile_element)

    errors = profedit.apply_edits_to_profile(edited, "Where", _loc_values(**changes), state=PrimeItems)

    assert fragment in errors
    assert _xml(edited.profile_element) == before


def test_a_negative_coordinate_is_fine() -> None:
    assert profedit._validate_loc_field_values({"lat": "-33.9", "long": "-151.2", "rad": "0"}) == []  # noqa: SLF001


# ##################################################################################
# Day.
# ##################################################################################
def test_a_day_condition_reads_each_selection() -> None:
    condition = _only(_edit("Weekdays"))

    assert profedit.get_day_selected_weekdays(condition) == [2, 3]
    assert profedit.get_day_selected_months(condition) == [0]
    assert profedit.get_day_selected_month_days(condition) == [1, profedit.DAY_OF_MONTH_LAST_DAY]


def test_a_day_selection_ignores_what_is_not_a_number_and_repeats() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)
    condition = profedit.add_condition_to_profile(edited, "Day")
    for tag, text in (("wday0", "4"), ("wday1", "oops"), ("wday2", "4"), ("wday3", None), ("wday4", "1")):
        ET.SubElement(condition.condition_element, tag).text = text

    assert profedit.get_day_selected_weekdays(condition) == [1, 4]


def test_ticked_boxes_become_numbered_elements_in_order() -> None:
    edited = _edit("Weekdays")
    values = {
        _field(0, "wday1"): "1",
        _field(0, "wday7"): "true",
        _field(0, "wday4"): "True",
        _field(0, "wday5"): "0",  # Not ticked.
        _field(0, "mnth11"): "1",
        _field(0, "mday15"): "1",
        _field(0, "mday32"): "1",
    }

    assert profedit.apply_edits_to_profile(edited, "Weekdays", values, state=PrimeItems) == []

    element = _only(edited).condition_element
    assert [(c.tag, c.text) for c in element] == [
        ("wday0", "1"),
        ("wday1", "4"),
        ("wday2", "7"),
        ("mnth0", "11"),
        ("mday0", "15"),
        ("mday1", "32"),
    ]


def test_clearing_every_box_clears_the_selection() -> None:
    edited = _edit("Weekdays")

    assert profedit.apply_edits_to_profile(edited, "Weekdays", {}, state=PrimeItems) == []

    assert list(_only(edited).condition_element) == []


# ##################################################################################
# App.
# ##################################################################################
def test_an_app_condition_reads_its_entries_by_index() -> None:
    assert profedit.get_app_entries(_only(_edit("Apps"))) == [
        {"cls": "com.a.Main", "label": "Alpha", "pkg": "com.a"},
        {"cls": "", "label": "Beta", "pkg": "com.b"},
    ]


def test_an_entry_is_added_blank_and_removed_by_position() -> None:
    edited = _edit("Apps")
    condition = _only(edited)

    profedit.add_app_entry(condition)
    assert profedit.get_app_entries(condition)[-1] == {"cls": "", "label": "", "pkg": ""}
    assert len(profedit.get_app_entries(condition)) == 3

    profedit.remove_app_entry(condition, 0)
    assert [entry["pkg"] for entry in profedit.get_app_entries(condition)] == ["com.b", ""]
    # Out of range, either way, removes nothing.
    profedit.remove_app_entry(condition, 5)
    profedit.remove_app_entry(condition, -1)
    assert len(profedit.get_app_entries(condition)) == 2
    # The match mode in <flags> is not an entry and is left alone.
    assert condition.condition_element.findtext("flags") == "2"


def test_entries_are_renumbered_after_a_removal() -> None:
    condition = _only(_edit("Apps"))

    profedit.remove_app_entry(condition, 0)

    assert [child.tag for child in condition.condition_element] == ["flags", "cls0", "label0", "pkg0"]
    assert condition.condition_element.findtext("pkg0") == "com.b"


def test_app_entries_are_edited_and_trimmed() -> None:
    edited = _edit("Apps")
    values = {
        _field(0, "app0_pkg"): " com.new ",
        _field(0, "app0_label"): "New",
        _field(0, "app0_cls"): "com.new.Main",
        _field(0, "app1_pkg"): "com.b",
    }

    assert profedit.apply_edits_to_profile(edited, "Apps", values, state=PrimeItems) == []

    assert profedit.get_app_entries(_only(edited)) == [
        {"cls": "com.new.Main", "label": "New", "pkg": "com.new"},
        {"cls": "", "label": "", "pkg": "com.b"},
    ]


def test_an_entry_without_a_package_is_refused() -> None:
    edited = _edit("Apps")
    before = _xml(edited.profile_element)

    errors = profedit.apply_edits_to_profile(edited, "Apps", {_field(0, "app0_pkg"): "com.a"}, state=PrimeItems)

    assert errors == ["App entry 2 needs a Package name."]
    assert _xml(edited.profile_element) == before


# ##################################################################################
# State and Event.
# ##################################################################################
def test_state_and_event_values_are_written_through_the_argument_machinery() -> None:
    edited = _edit("Triggers")
    values = {
        profedit.condition_arg_key(0, "0"): "0",
        profedit.condition_arg_key(1, "0"): "SMS",
        profedit.condition_arg_key(1, "1"): "Dad",
        profedit.condition_arg_key(1, "2"): "hello",
    }

    assert profedit.apply_edits_to_profile(edited, "Triggers", values, state=PrimeItems) == []

    state_element, event_element, _ = (c.condition_element for c in edited.conditions)
    assert state_element.find("Int[@sr='arg0']").get("val") == "0"
    assert event_element.find("Int[@sr='arg0']").get("val") == "2"
    assert event_element.findtext("Str[@sr='arg1']") == "Dad"
    assert event_element.findtext("Str[@sr='arg2']") == "hello"


def test_a_bad_number_in_an_event_is_refused_and_says_which_condition() -> None:
    """Only a plain-number argument can fail: a dropdown or checkbox is whatever the dialog offered."""
    edited = profedit.create_new_profile("P", state=PrimeItems)
    event = profedit.add_event_condition_to_profile(edited, "599e", state=PrimeItems)  # Intent Received
    before = _xml(edited.profile_element)
    priority = profedit.condition_arg_key(event.cond_index, "5")

    errors = profedit.apply_edits_to_profile(edited, "P", {priority: "urgent"}, state=PrimeItems)

    assert errors == ["'Priority' must be a whole number. (Event condition 0)"]
    assert _xml(edited.profile_element) == before

    assert profedit.apply_edits_to_profile(edited, "P", {priority: "-3"}, state=PrimeItems) == []
    assert event.condition_element.find("Int[@sr='arg5']").get("val") == "-3"


def test_a_condition_with_nothing_to_edit_is_skipped() -> None:
    edited = profedit.create_new_profile("P", state=PrimeItems)
    profedit.add_state_condition_to_profile(edited, "100s", state=PrimeItems)

    assert profedit.apply_edits_to_profile(edited, "P", {}, state=PrimeItems) == []


# ##################################################################################
# Applying the whole dialog.
# ##################################################################################
def test_a_blank_name_is_refused() -> None:
    edited = _edit("Morning")

    assert profedit.apply_edits_to_profile(edited, "   ", _time_values(), state=PrimeItems) == [
        "Profile name cannot be empty.",
    ]
    assert edited.profile_element.findtext("nme") == "Morning"


def test_every_error_is_reported_at_once() -> None:
    edited = _edit("Morning")

    errors = profedit.apply_edits_to_profile(edited, "", _time_values(start_time="x", end_time="y"), state=PrimeItems)

    assert len(errors) == 3


def test_the_name_is_trimmed_and_written() -> None:
    edited = _edit("Morning")

    assert profedit.apply_edits_to_profile(edited, "  Early  ", _time_values(), state=PrimeItems) == []

    assert edited.profile_element.findtext("nme") == "Early"


# ##################################################################################
# Paths and names.
# ##################################################################################
def test_a_profile_name_becomes_a_safe_file_name() -> None:
    assert profedit.sanitize_filename('Home/Work: "daily"') == editcommon.sanitize_filename(
        'Home/Work: "daily"', "profile"
    )
    assert profedit.sanitize_filename("???") != ""
    assert profedit.android_profile_path("Home/Work") == "/Tasker/profiles/Home_Work.prf.xml"
    assert profedit.android_profile_path("Home_Work") == profedit.android_profile_path("Home/Work")
    assert profedit.default_save_path("Morning").endswith("Morning.prf.xml")


def test_a_name_is_taken_when_a_profile_has_it() -> None:
    assert profedit.profile_name_exists("Morning", state=PrimeItems) is True
    assert profedit.profile_name_exists("  Morning  ", state=PrimeItems) is True
    assert profedit.profile_name_exists("morning", state=PrimeItems) is False
    assert profedit.profile_name_exists("Fresh", state=PrimeItems) is False


def test_an_existing_file_is_noticed(tmp_path: os.PathLike) -> None:
    target = tmp_path / "x.prf.xml"
    assert profedit.save_path_exists(str(target)) is False

    target.write_text("old", encoding="utf-8")
    assert profedit.save_path_exists(str(target)) is True


# ##################################################################################
# The standalone export.
# ##################################################################################
def test_the_export_is_the_profile_and_its_tasks_under_one_root() -> None:
    xml = profedit.render_standalone_profile_xml(_edit("Morning"), state=PrimeItems)

    root = ET.fromstring(xml)  # noqa: S314
    assert root.tag == "TaskerData"
    assert root.get("tv") == "6.3.13"
    assert [child.tag for child in root] == ["Profile", "Task", "Task"]
    assert [task.findtext("nme") for task in root.findall("Task")] == ["Entry", "Exit"]
    # Straight to the root: no XML declaration, and one trailing newline.
    assert xml.startswith("<TaskerData")
    assert xml.endswith("</TaskerData>\n")


def test_a_task_used_for_entry_and_exit_is_bundled_once() -> None:
    root = ET.fromstring(profedit.render_standalone_profile_xml(_edit("Apps"), state=PrimeItems))  # noqa: S314

    assert len(root.findall("Task")) == 1


def test_a_profile_with_no_tasks_exports_alone() -> None:
    root = ET.fromstring(profedit.render_standalone_profile_xml(_edit("Triggers"), state=PrimeItems))  # noqa: S314

    assert [child.tag for child in root] == ["Profile"]


def test_a_linked_task_that_is_gone_is_left_out() -> None:
    edited = _edit("Morning")
    profedit.link_task_to_profile(edited, "9999", "Entry")

    root = ET.fromstring(profedit.render_standalone_profile_xml(edited, state=PrimeItems))  # noqa: S314

    assert [task.findtext("nme") for task in root.findall("Task")] == ["Exit"]


def test_the_export_is_of_the_edited_copy() -> None:
    edited = _edit("Morning")
    assert profedit.apply_edits_to_profile(edited, "Renamed", _time_values(), state=PrimeItems) == []

    root = ET.fromstring(profedit.render_standalone_profile_xml(edited, state=PrimeItems))  # noqa: S314

    assert root.find("Profile").findtext("nme") == "Renamed"
    assert _live("Morning").findtext("nme") == "Morning"


def test_the_export_can_have_its_secrets_taken_out() -> None:
    edited = _edit("Triggers")
    profedit.link_task_to_profile(edited, "20", "Entry")
    task_element = PrimeItems.tasker_root_elements["all_tasks"]["20"]["xml"]
    ET.SubElement(task_element, "Str").text = "password=hunter2"

    plain = profedit.render_standalone_profile_xml(edited, state=PrimeItems)
    redacted = profedit.render_standalone_profile_xml(edited, state=PrimeItems, redact=True)

    assert "hunter2" in plain
    assert "hunter2" not in redacted


def test_writing_a_file_takes_a_safety_copy_of_what_it_replaces(tmp_path: os.PathLike) -> None:
    target = tmp_path / "Morning.prf.xml"
    target.write_text("<old/>", encoding="utf-8")

    safety = profedit.write_standalone_profile_xml(_edit("Morning"), str(target), state=PrimeItems)

    assert target.read_text(encoding="utf-8").startswith("<TaskerData")
    assert safety
    with open(safety, encoding="utf-8") as copy:
        assert copy.read() == "<old/>"


def test_writing_a_new_file_has_nothing_to_copy(tmp_path: os.PathLike) -> None:
    target = tmp_path / "New.prf.xml"

    safety = profedit.write_standalone_profile_xml(_edit("Morning"), str(target), state=PrimeItems)

    assert safety == ""
    assert target.exists()


def test_an_unwritable_path_raises(tmp_path: os.PathLike) -> None:
    with pytest.raises(OSError):  # noqa: PT011
        profedit.write_standalone_profile_xml(
            _edit("Morning"), str(tmp_path / "no" / "such" / "x.xml"), state=PrimeItems
        )


def test_saving_to_android_uploads_the_rendered_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def upload(
        kind: editcommon.EditorKind,
        ip_address: str,
        ip_port: str,
        name: str,
        render_bytes: object,
    ) -> tuple[int, str, bytes]:
        seen.update(kind=kind, address=ip_address, port=ip_port, name=name, body=render_bytes())
        return 0, "/Tasker/profiles/Morning.prf.xml", b""

    monkeypatch.setattr(editcommon.EditorKind, "upload_and_verify", upload)
    result = profedit.save_profile_to_android(_edit("Morning"), "192.168.0.2", "1821", "Morning", state=PrimeItems)

    assert result == (0, "/Tasker/profiles/Morning.prf.xml")
    assert seen["kind"] is profedit.EXPORT
    assert (seen["address"], seen["port"], seen["name"]) == ("192.168.0.2", "1821", "Morning")
    assert seen["body"].startswith(b"<TaskerData")


def test_a_failed_upload_is_reported_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        editcommon.EditorKind,
        "upload_and_verify",
        lambda *_args: (8, "The device did not answer.", b""),
    )

    assert profedit.save_profile_to_android(_edit("Morning"), "1.2.3.4", "1821", "Morning", state=PrimeItems) == (
        8,
        "The device did not answer.",
    )


# ##################################################################################
# Changing the loaded configuration.
# ##################################################################################
def _new_profile(name: str = "Fresh", *, entry: str = "", exit_: str = "") -> profedit.EditableProfile:
    created = profedit.create_new_profile(name, state=PrimeItems)
    if entry:
        profedit.link_task_to_profile(created, entry, "Entry")
    if exit_:
        profedit.link_task_to_profile(created, exit_, "Exit")
    return created


def test_a_new_profile_must_have_an_entry_task_and_a_condition() -> None:
    created = _new_profile()
    assert len(profedit.validate_new_profile_requirements(created)) == 2

    profedit.link_task_to_profile(created, "20", "Entry")
    assert [("condition" in error) for error in profedit.validate_new_profile_requirements(created)] == [True]

    profedit.add_condition_to_profile(created, "Day")
    assert profedit.validate_new_profile_requirements(created) == []


def test_registering_makes_the_profile_findable_like_any_other() -> None:
    created = _new_profile()

    profedit.register_new_profile(created, "Fresh", state=PrimeItems)

    tables = PrimeItems.tasker_root_elements
    assert tables["all_profiles"][created.profile_id] == {"xml": created.profile_element, "name": "Fresh"}
    assert tables["all_profiles_by_name"]["Fresh"] == {"xml": created.profile_element, "id": created.profile_id}
    assert profedit.profile_name_exists("Fresh", state=PrimeItems)
    assert profedit.load_profile_for_edit("Fresh", state=PrimeItems) is not None


def test_adding_to_a_project_lists_the_profile_and_its_tasks() -> None:
    created = _new_profile(entry="22", exit_="20")
    profedit.register_new_profile(created, "Fresh", state=PrimeItems)

    profedit.add_profile_to_project(created, "Home", state=PrimeItems)

    home = _project("Home")
    assert home.findtext("pids").split(",") == ["100", "101", "102", "103", "104", created.profile_id]
    # Task 20 was already the Project's; 22 was not, and now is.
    assert home.findtext("tids").split(",") == ["20", "21", "22"]
    assert home.findtext("mdate") != "1"


def test_a_profile_is_listed_once_however_often_it_is_added() -> None:
    created = _new_profile()
    profedit.register_new_profile(created, "Fresh", state=PrimeItems)

    profedit.add_profile_to_project(created, "Home", state=PrimeItems)
    profedit.add_profile_to_project(created, "Home", state=PrimeItems)

    assert _project("Home").findtext("pids").split(",").count(created.profile_id) == 1


def test_a_project_with_no_lists_gets_them() -> None:
    created = _new_profile(entry="20")
    bare = PrimeItems.tasker_root_elements["all_projects"]["Work"]["xml"]
    bare.remove(bare.find("tids"))
    bare.remove(bare.find("pids"))

    profedit.add_profile_to_project(created, "Work", state=PrimeItems)

    assert bare.findtext("pids") == created.profile_id
    assert bare.findtext("tids") == "20"


def test_adding_to_a_project_that_is_not_there_does_nothing() -> None:
    created = _new_profile(entry="20")
    before = [_xml(p["xml"]) for p in PrimeItems.tasker_root_elements["all_projects"].values()]

    profedit.add_profile_to_project(created, "Nowhere", state=PrimeItems)
    profedit.add_task_to_project("20", "Nowhere", state=PrimeItems)

    assert [_xml(p["xml"]) for p in PrimeItems.tasker_root_elements["all_projects"].values()] == before


def test_a_task_is_added_to_a_project_once() -> None:
    profedit.add_task_to_project("30", "Work", state=PrimeItems)
    profedit.add_task_to_project("30", "Work", state=PrimeItems)

    assert _project("Work").findtext("tids") == "22,30"
    assert _project("Work").findtext("mdate")


def test_deleting_a_profile_removes_it_from_every_table_and_project() -> None:
    # Two Projects listing one Profile: neither may be left with a dangling id.
    assert "104" in _project("Home").findtext("pids").split(",")
    assert "104" in _project("Work").findtext("pids").split(",")

    assert profedit.delete_profile("Triggers", state=PrimeItems) == []

    tables = PrimeItems.tasker_root_elements
    assert "104" not in tables["all_profiles"]
    assert "Triggers" not in tables["all_profiles_by_name"]
    assert _project("Home").findtext("pids") == "100,101,102,103"
    assert _project("Work").findtext("pids") == ""
    assert _project("Work").findtext("mdate")


def test_deleting_a_profile_leaves_its_tasks_alone() -> None:
    assert profedit.delete_profile("Morning", state=PrimeItems) == []

    tasks = PrimeItems.tasker_root_elements["all_tasks"]
    assert {"20", "21"} <= tasks.keys()
    assert "20" in _project("Home").findtext("tids").split(",")


def test_deleting_a_profile_that_is_gone_says_so_and_changes_nothing() -> None:
    before = _xml(_project("Home"))

    assert profedit.delete_profile("Nobody", state=PrimeItems) == ["Profile 'Nobody' no longer exists."]

    assert _xml(_project("Home")) == before


def test_applying_an_edit_swaps_the_edited_copy_in() -> None:
    edited = _edit("Morning")
    assert profedit.apply_edits_to_profile(edited, "Early", _time_values(start_time="6:00 AM"), state=PrimeItems) == []

    profedit.apply_edited_profile_to_live_tree(edited, state=PrimeItems)

    tables = PrimeItems.tasker_root_elements
    assert tables["all_profiles"]["100"] == {"xml": edited.profile_element, "name": "Early"}
    assert "Morning" not in tables["all_profiles_by_name"]
    assert tables["all_profiles_by_name"]["Early"] == {"xml": edited.profile_element, "id": "100"}


def test_applying_an_edit_that_keeps_the_name_keeps_the_entry() -> None:
    edited = _edit("Morning")

    profedit.apply_edited_profile_to_live_tree(edited, state=PrimeItems)

    assert PrimeItems.tasker_root_elements["all_profiles_by_name"]["Morning"]["xml"] is edited.profile_element


def test_applying_an_edit_to_a_profile_nobody_registered_does_nothing() -> None:
    created = _new_profile()

    profedit.apply_edited_profile_to_live_tree(created, state=PrimeItems)

    assert created.profile_id not in PrimeItems.tasker_root_elements["all_profiles"]
    assert "Fresh" not in PrimeItems.tasker_root_elements["all_profiles_by_name"]


def test_a_rename_is_checked_against_the_other_profiles() -> None:
    edited = _edit("Morning")

    assert profedit.apply_profile_rename(edited, "  ", state=PrimeItems) == ["Profile name cannot be empty."]
    taken = profedit.apply_profile_rename(edited, "Weekdays", state=PrimeItems)
    assert taken == ["A Profile named 'Weekdays' already exists in this backup. Choose a different name."]
    assert edited.profile_element.findtext("nme") == "Morning"


def test_a_rename_may_keep_the_name_it_has_and_may_take_a_new_one() -> None:
    edited = _edit("Morning")

    assert profedit.apply_profile_rename(edited, "Morning", state=PrimeItems) == []
    assert profedit.apply_profile_rename(edited, "  Dawn  ", state=PrimeItems) == []

    assert edited.profile_element.findtext("nme") == "Dawn"


def test_renaming_in_the_live_tree_changes_the_element_and_moves_the_key() -> None:
    edited = _edit("Morning")
    assert profedit.apply_profile_rename(edited, "Dawn", state=PrimeItems) == []
    # A change made in the dialog that has not been applied: the rename must not carry it.
    profedit.set_profile_enabled(edited, enabled=False)
    live = _live("Morning")

    previous = profedit.rename_profile_in_live_tree(edited, state=PrimeItems)

    assert previous == "Morning"
    tables = PrimeItems.tasker_root_elements
    assert live.findtext("nme") == "Dawn"
    assert live.find("limit") is None
    assert tables["all_profiles"]["100"]["name"] == "Dawn"
    assert "Morning" not in tables["all_profiles_by_name"]
    assert tables["all_profiles_by_name"]["Dawn"] == {"xml": live, "id": "100"}


def test_renaming_a_profile_nobody_registered_does_nothing() -> None:
    created = _new_profile()

    assert profedit.rename_profile_in_live_tree(created, state=PrimeItems) == ""
    assert "Fresh" not in PrimeItems.tasker_root_elements["all_profiles_by_name"]


# ##################################################################################
# Undo.
# ##################################################################################
def test_adding_a_profile_to_a_project_is_one_step_to_undo() -> None:
    """Register and attach each open their own undo block; the user did one thing."""
    sessundo.clear()
    created = _new_profile(entry="20")
    before_pids = _project("Home").findtext("pids")

    with sessundo.undoable("Add Profile", state=PrimeItems):
        profedit.register_new_profile(created, "Fresh", state=PrimeItems)
        profedit.add_profile_to_project(created, "Home", state=PrimeItems)

    assert created.profile_id in _project("Home").findtext("pids").split(",")
    assert sessundo.next_undo_label() == "Add Profile"
    assert [label for label, _when in sessundo.history()] == ["Add Profile"]

    done, _message = sessundo.undo(state=PrimeItems)

    assert done
    assert "Fresh" not in PrimeItems.tasker_root_elements["all_profiles_by_name"]
    assert _project("Home").findtext("pids") == before_pids
    sessundo.clear()
