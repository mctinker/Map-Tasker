"""Object Properties in the MAP VIEW (property.py) Unit Tests

The read side of what test_objprops.py covers on the write side, for the five Profile
settings Tasker keeps outside the tags every object shares:

    Remaining Repeats      <repeats>       Limit Repeats         <flags> bit 2
    Delete On Zero Repeats <dod>           Enforce Task Order    <flags> bit 0
                                           Show In Notification  <flags> bit 4

None of the five appears on any of the 3,526 Profiles in XML/, so the sample data cannot
check this and these tests are what holds it.  The fixture is the Tasker 6.7.6 export with
the repeat group set; test_objprops.py's header carries the whole measured table.

What is asserted beyond "it shows up" is that the Map takes its LABELS AND DEFAULTS FROM
THE SAME TABLE THE PROPERTIES EDITOR IS BUILT FROM (objprops.OBJECT_PROPERTIES).  The two
had drifted over <limit>, which this module reported as "Limit Repeats" while three others
read it as "this Profile is disabled" -- it is the disabled marker, and the Map now says so.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src import objprops
from maptasker.src import property as prop

# The Atest2 export, trimmed to its properties and one condition: Limit Repeats (<flags> bit
# 2) with a count of 5 and Delete On Zero Repeats, and neither of the other two bits.  <clp>
# is kept because it is a real child of 462 sample Profiles that nothing here reports -- a tag
# the Map must walk past rather than trip over -- and so is <limit>, which is the disabled
# marker and must never come out under one of these labels.
_PROFILE_XML = """<Profile sr="prof858" ve="2">
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


def _profile(**overrides: str) -> ET.Element:
    """The fixture Profile, with any child's text replaced or any child removed (pass None)."""
    profile = ET.fromstring(_PROFILE_XML)  # noqa: S314  (fixture text, defined in this file)
    for tag, text in overrides.items():
        child = profile.find(tag)
        if text is None:
            if child is not None:
                profile.remove(child)
        elif child is None:
            ET.SubElement(profile, tag).text = text
        else:
            child.text = text
    return profile


def test_the_settings_are_reported_in_the_editors_own_order() -> None:
    """Tasker's Profile Properties screen order, which is the order the editor shows them in
    -- Limit Repeats, the count, what happens when it runs out, then the other two.
    """
    assert prop.profile_properties(_profile()) == [
        "Limit Repeats:true",
        "Remaining Repeats:5",
        "Delete On Zero Repeats:true",
    ]


def test_each_flags_setting_is_reported_off_the_export_that_isolates_it() -> None:
    """The three <flags> values Tasker wrote with exactly one box ticked, each reported as
    that one setting and nothing else.
    """
    assert "Enforce Task Order:true" in prop.profile_properties(_profile(flags="9"))
    assert "Show In Notification:true" in prop.profile_properties(_profile(flags="24"))
    assert "Limit Repeats:true" in prop.profile_properties(_profile(flags="12"))


def test_show_in_notification_is_reported_only_when_it_is_switched_on() -> None:
    """Not inverted on a Profile: bit 4 clear is the box unticked, and an unticked box is not
    something to put in the Map.
    """
    assert not any("Show In Notification" in item for item in prop.profile_properties(_profile()))
    assert "Show In Notification:true" in prop.profile_properties(_profile(flags="28"))


def test_a_profile_at_every_default_reports_none_of_them() -> None:
    """The five cost a Properties line only on a Profile that has actually had one set.  A
    <flags> of 10 is the commonest value in the sample backups (2,346 Profiles) and holds
    none of the three bits.
    """
    profile = _profile(repeats=None, dod=None, flags="10")
    assert prop.profile_properties(profile) == []


def test_a_profile_with_no_flags_at_all_is_read_as_both_defaults() -> None:
    """41 of the 3,526 sample Profiles have no <flags>, and Tasker writes none when the value
    would be 0 -- absent has to read as all three of its settings switched off rather than as
    anything missing.
    """
    profile = _profile(repeats=None, dod=None, flags=None)
    assert prop.profile_properties(profile) == []


def test_an_unreadable_flags_value_reports_no_bit_at_all() -> None:
    """<flags> is Tasker's, and a value this build cannot parse is not a licence to guess."""
    assert prop.profile_properties(_profile(repeats=None, dod=None, flags="not a number")) == []


def test_the_labels_are_the_ones_the_properties_editor_shows() -> None:
    """The Map and the editor must call each setting the same thing.  Both read
    objprops.OBJECT_PROPERTIES, so this is a guard against someone hard-coding a label here
    the next time one is added.
    """
    labels = {spec.key: spec.label for spec in objprops.OBJECT_PROPERTIES[objprops.KIND_PROFILE]}
    reported = [item.rsplit(":", 1)[0] for item in prop.profile_properties(_profile(flags="29"))]

    assert reported == [labels[key] for key in prop._PROFILE_PROPERTY_KEYS]


@pytest.fixture
def captured_output(monkeypatch):
    """The Map's output lines, captured instead of written."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    from maptasker.src.primitem import PrimeItems  # noqa: PLC0415

    lines: list[str] = []
    sink = MagicMock()
    sink.add_line_to_output = lambda _level, text, _format: lines.append(text)
    monkeypatch.setattr(PrimeItems, "output_lines", sink)
    monkeypatch.setitem(PrimeItems.program_arguments, "pretty", False)
    # parse_variable reports an unrecognised variable type through error.rutroh_error, which
    # reads this key -- a bare <ProfileVariable> in a fixture is enough to reach it.
    monkeypatch.setitem(PrimeItems.program_arguments, "debug", False)
    return lines


def test_the_map_line_carries_them(captured_output) -> None:
    """End to end: what a Profile's "Profile: Properties..." line actually says.  <flags> 29
    is every one of the three bits at once -- 1 + 4 + 16 + the baseline 8."""
    prop.get_properties("Profile:", _profile(flags="29"))

    assert len(captured_output) == 1
    line = captured_output[0]
    for item in (
        "Limit Repeats:true",
        "Remaining Repeats:5",
        "Delete On Zero Repeats:true",
        "Enforce Task Order:true",
        "Show In Notification:true",
    ):
        assert item in line


def test_the_limit_tag_is_reported_as_the_disabled_marker_it_is(captured_output) -> None:
    """It used to be labelled "Limit Repeats", which is a different setting living in <flags>
    bit 2 -- and since <limit> is on 2,378 of the 3,526 sample Profiles, that made two
    Profiles in every three look as though they limited their repeats.  It is only reported
    at all for a Profile that has variables (the gate get_properties applies to it and to
    Cooldown Time alike).
    """
    profile = _profile(flags="8")
    ET.SubElement(profile, "ProfileVariable")
    prop.get_properties("Profile:", profile)

    assert "Disabled:true" in captured_output[0]
    assert "Limit Repeats" not in captured_output[0]


def test_a_task_is_never_asked_for_a_profiles_settings(captured_output) -> None:
    """<flags> is on no Task and no Project in the sample data, and its bits mean what they
    mean because they were measured on a Profile.  Reading one off anything else would be
    inventing a setting.
    """
    task = ET.fromstring(  # noqa: S314  (fixture text, defined in this file)
        "<Task sr='task1'><nme>T</nme><flags>13</flags><stayawake>true</stayawake></Task>",
    )
    prop.get_properties("Task:", task)

    assert len(captured_output) == 1
    assert "Keep Device Awake:true" in captured_output[0]
    assert "Show In Notification" not in captured_output[0]
