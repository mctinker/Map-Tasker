"""Object Properties in the MAP VIEW (property.py) Unit Tests

The read side of what test_objprops.py covers on the write side, for the five Profile
settings Tasker keeps outside the tags every object shares:

    Remaining Repeats         <repeats>       Enforce Task Order        <flags> mask 16, inverted
    Delete After Disable      <flags> mask 4  Run Exit Task On Startup  <flags> mask 32
    Restore Settings          <flags> mask 8  Show In Notification      <flags> mask 1, inverted

The bit layout is Tasker's own, transcribed in objprops; three of the five bits are worded as
the NEGATIVE of the setting shown ("ignore settings", "ignore task order", "hide in
notification"), so the Map reports those three when they are switched OFF -- except Restore
Settings, whose bit Tasker SETS on every Profile it creates, so for that one the Map reports
it switched ON (objprops.noteworthy_default).  None of the six settings appears on any of the
5,627 Profiles in XML/, so the sample data cannot check this and these tests are what holds
it.  The fixture is a Tasker 6.7.6 export with the repeat group set.

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

# The Atest2 export, trimmed to its properties and one condition: a repeat count of 5 and
# <flags>12</flags>, which is Delete After Disable (mask 4) plus the Ignore Settings bit
# (mask 8) that Tasker puts on every Profile it makes, and neither of the other two.  <clp> is kept because it is a real child of 462 sample
# Profiles that nothing here reports -- a tag the Map must walk past rather than trip over --
# and so are <limit>, which is the disabled marker and must never come out under one of these
# labels, and <dod>, mask 4's older twin, which no field reads.
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
    -- the count, what happens when it runs out, then the rest.  Only the two the fixture
    actually has: the other three are at their defaults and cost nothing.
    """
    assert prop.profile_properties(_profile()) == [
        "Remaining Repeats:5",
        "Delete After Disable:true",
    ]


def test_each_flags_bit_is_reported_as_the_one_setting_it_holds() -> None:
    """One mask at a time, against Tasker's own values -- including the two that are reported
    as switched OFF because the bit itself is worded as the negative.
    """
    assert "Show In Notification:false" in prop.profile_properties(_profile(flags="1"))
    assert "Delete After Disable:true" in prop.profile_properties(_profile(flags="4"))
    assert "Enforce Task Order:false" in prop.profile_properties(_profile(flags="16"))
    assert "Run Exit Task On Startup:true" in prop.profile_properties(_profile(flags="32"))
    # Restore Settings is the other way round: its bit is the state Tasker leaves, so it is
    # the value WITHOUT mask 8 that is worth reporting.
    assert "Restore Settings:true" in prop.profile_properties(_profile(flags="4"))
    for item in prop.profile_properties(_profile(flags="8")):
        assert "Restore Settings" not in item


def test_the_inverted_settings_are_reported_only_when_switched_off() -> None:
    """Mask 1 is "hide in notification" and mask 16 is "ignore task order", so a Profile
    without them is one whose owner has never touched either -- and a Map that reported those
    two on every such Profile would put a Properties line on nearly all of them.
    """
    for item in prop.profile_properties(_profile()):
        assert "Show In Notification" not in item
        assert "Enforce Task Order" not in item
    assert "Show In Notification:false" in prop.profile_properties(_profile(flags="13"))
    assert "Enforce Task Order:false" in prop.profile_properties(_profile(flags="28"))


def test_a_profile_at_every_default_reports_none_of_them() -> None:
    """These cost a Properties line only on a Profile that has actually had one set.  A
    <flags> of 10 is the commonest value in the sample backups (4,009 Profiles) and is the
    value Tasker gives a new Profile: mask 2, which no field reads, and the mask 8 that
    Restore Settings reads as the state Tasker left it in.
    """
    profile = _profile(repeats=None, flags="10")
    assert prop.profile_properties(profile) == []


def test_a_profile_with_no_flags_at_all_has_its_settings_read_from_the_absence() -> None:
    """41 of the 5,627 sample Profiles have no <flags>, and Tasker writes none when the value
    would be 0 -- absent has to read as every bit clear rather than as anything missing.  For
    the three inverted bits that means switched ON, and Restore Settings is the one where
    switched on is worth saying: Tasker sets that bit on every Profile it creates, so a
    Profile without it is one whose owner turned the setting on.
    """
    assert prop.profile_properties(_profile(repeats=None, flags=None)) == ["Restore Settings:true"]


def test_an_unreadable_flags_value_reports_no_bit_at_all() -> None:
    """<flags> is Tasker's, and a value this build cannot parse is not a licence to guess --
    least of all about Restore Settings, which an unreadable value would otherwise report as
    switched on, every bit reading as clear (objprops.bitfield_is_readable).
    """
    assert prop.profile_properties(_profile(repeats=None, flags="not a number")) == []


def test_the_labels_are_the_ones_the_properties_editor_shows() -> None:
    """The Map and the editor must call each setting the same thing.  Both read
    objprops.OBJECT_PROPERTIES, so this is a guard against someone hard-coding a label here
    the next time one is added.
    """
    labels = {spec.key: spec.label for spec in objprops.OBJECT_PROPERTIES[objprops.KIND_PROFILE]}
    # 53 is 1 + 4 + 16 + 32, every bit set but mask 8 -- and mask 8 CLEAR is what makes
    # Restore Settings worth reporting, so all six settings are reportable at once here and
    # the whole order is under test.
    reported = [item.rsplit(":", 1)[0] for item in prop.profile_properties(_profile(flags="53"))]

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
    """End to end: what a Profile's "Profile: Properties..." line actually says.  <flags> 53
    is 1 + 4 + 16 + 32: every bit set but mask 8, whose absence is what makes Restore Settings
    worth reporting."""
    prop.get_properties("Profile:", _profile(flags="53"))

    assert len(captured_output) == 1
    line = captured_output[0]
    for item in (
        "Remaining Repeats:5",
        "Delete After Disable:true",
        "Restore Settings:true",
        "Enforce Task Order:false",
        "Run Exit Task On Startup:true",
        "Show In Notification:false",
    ):
        assert item in line


def test_the_limit_tag_is_reported_as_the_disabled_marker_it_is(captured_output) -> None:
    """It used to be labelled "Limit Repeats", which is a different setting entirely -- a
    count in <repeats> -- and since <limit> is on 4,103 of the 5,627 sample Profiles, that
    made two Profiles in every three look as though they limited their repeats.  It is only
    reported at all for a Profile that has variables (the gate get_properties applies to it
    and to Cooldown Time alike).
    """
    profile = _profile(flags="8")
    ET.SubElement(profile, "ProfileVariable")
    prop.get_properties("Profile:", profile)

    assert "Disabled:true" in captured_output[0]
    assert "Limit Repeats" not in captured_output[0]


def test_a_task_is_never_asked_for_a_profiles_settings(captured_output) -> None:
    """<flags> is on no Task and no Project in the sample data, and the bits objprops names
    are a Profile's.  Reading one off anything else would be inventing a setting.
    """
    task = ET.fromstring(  # noqa: S314  (fixture text, defined in this file)
        "<Task sr='task1'><nme>T</nme><flags>13</flags><stayawake>true</stayawake></Task>",
    )
    prop.get_properties("Task:", task)

    assert len(captured_output) == 1
    assert "Keep Device Awake:true" in captured_output[0]
    assert "Show In Notification" not in captured_output[0]
