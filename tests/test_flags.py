"""The three <flags> bitmasks in a Tasker backup (objprops) Unit Tests

Three unrelated things in a backup all name their bitfield <flags> -- a Profile, an App
context (a Profile's <App> condition) and a Legacy Scene element -- and each one's bits mean
something different.  objprops holds Tasker's own values for all three, and this file is
about the two that nothing else covers (test_objprops.py and test_property.py have the
Profile's, from the write and read sides) plus the decoder they share.

WHAT THESE TESTS ARE FOR is the reason the tables exist at all: a bit read as the wrong
setting is not a display fault, it is a wrong value written to someone's configuration.  So
each mask is checked against the meaning Tasker gives it, and a bit the tables have never
heard of is checked to survive rather than to be guessed at.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from maptasker.src import objprops, sceneview
from maptasker.src.condition import condition_app


def _element(xml: str) -> ET.Element:
    return ET.fromstring(xml)  # noqa: S314  (fixture text, defined in this file)


# --------------------------------------------------------------------------------------
# describe_flags: the decoder all three tables are read through
# --------------------------------------------------------------------------------------
def test_the_set_bits_are_named_lowest_first() -> None:
    """The order the masks are listed in, which is the order a reader checking a number
    against the table would go in.
    """
    assert objprops.describe_flags(10, objprops.PROFILE_FLAG_NAMES) == ["Collapsed", "Ignore Settings"]
    assert objprops.describe_flags(13, objprops.SCENE_ELEMENT_FLAG_NAMES) == [
        "Fixed position",
        "Visible",
        "Initial focus",
    ]


def test_a_value_with_nothing_set_names_nothing() -> None:
    """0 is what an absent or unreadable <flags> reads as, and it has to come back empty
    rather than as a list of everything or of the first bit.
    """
    assert objprops.describe_flags(0, objprops.PROFILE_FLAG_NAMES) == []


def test_a_bit_the_table_has_never_heard_of_is_still_reported() -> None:
    """None of the 5,586 sample Profile values exceeds 63, but a newer Tasker may define a
    seventh bit -- and a decode that dropped it would claim the tag held less than it does.
    """
    assert objprops.describe_flags(1 + (1 << 9), objprops.PROFILE_FLAG_NAMES) == [
        "Hide In Notification",
        "bit 9",
    ]


def test_the_profile_names_are_worded_as_the_bits_are() -> None:
    """Two of the six are the NEGATIVE of the setting Tasker's Properties screen shows.  This
    decodes the number in the file, so mask 1 has to read "Hide In Notification": calling it
    "Show In Notification" here would report the opposite of the truth.
    """
    assert objprops.PROFILE_FLAG_NAMES[objprops.PROFILE_HIDE_IN_NOTIFICATION_BIT] == "Hide In Notification"
    assert objprops.PROFILE_FLAG_NAMES[objprops.PROFILE_IGNORE_TASK_ORDER_BIT] == "Ignore Task Order"


# --------------------------------------------------------------------------------------
# An App context: mask 1 running services, mask 2 the foreground app (the default)
# --------------------------------------------------------------------------------------
def test_an_app_condition_at_the_default_says_nothing_extra() -> None:
    """All 162 App conditions in the sample backups hold 2, so a note on every one of them
    would pad the Map with what the reader already assumes.
    """
    assert condition_app(_element("<App><label0>Chrome</label0><flags>2</flags></App>"), "") == "Application: Chrome"


def test_an_app_condition_that_matches_running_services_says_so() -> None:
    """Mask 1 is a different question being asked of the device, and nothing else in the Map
    would show it.
    """
    condition = condition_app(_element("<App><label0>Chrome</label0><flags>1</flags></App>"), "")
    assert condition == "Application: Chrome (matching running services)"


def test_an_app_condition_matching_both_names_both() -> None:
    """Both bits set is a value the sample data has never held, so it is spelled out here
    rather than left to whichever phrasing the join happens to produce.
    """
    assert condition_app(_element("<App><label0>Chrome</label0><flags>3</flags></App>"), "") == (
        "Application: Chrome (matching running services and matching the foreground app)"
    )


def test_an_app_condition_with_no_flags_says_nothing_extra() -> None:
    """Absent reads as 0, and 0 is not a claim about how the match is made."""
    assert condition_app(_element("<App><label0>Chrome</label0></App>"), "") == "Application: Chrome"


# --------------------------------------------------------------------------------------
# A Legacy Scene element: mask 1 fixed, mask 2 background, mask 4 visible, mask 8 focus
# --------------------------------------------------------------------------------------
def test_a_scene_elements_bits_are_named_for_the_tooltip() -> None:
    """24 sample EditTextElements hold 13 -- fixed, visible and holding the initial focus,
    which is where an initial focus belongs.
    """
    assert sceneview.element_flag_names(_element("<EditTextElement><flags>13</flags></EditTextElement>")) == [
        "Fixed position",
        "Visible",
        "Initial focus",
    ]


def test_an_element_tasker_hides_is_reported_as_hidden() -> None:
    """Mask 4 is Visible, so 1 -- fixed position and nothing else -- is an element Tasker does
    not draw until a Task makes it visible.  172 sample elements are in that state.
    """
    element = _element("<ImageElement><flags>1</flags></ImageElement>")
    assert sceneview.element_is_hidden(element) is True
    assert sceneview.element_flag_names(element) == ["Fixed position"]


def test_the_commonest_value_is_a_plain_visible_element() -> None:
    """4,823 of the 7,302 sample elements hold exactly 4."""
    element = _element("<TextElement><flags>4</flags></TextElement>")
    assert sceneview.element_is_hidden(element) is False
    assert sceneview.element_flag_names(element) == ["Visible"]


def test_an_element_with_no_flags_at_all_is_not_hidden() -> None:
    """THE CASE THAT MATTERS MOST.  1,507 sample elements have no <flags>, a state Tasker
    itself produces, so absence means "nothing said" -- reading it as 0 would hide a fifth of
    every Scene in the preview, including all 862 <PropertiesElement>s.
    """
    element = _element("<RectElement><geom>0,0,10,10,0,0,10,10</geom></RectElement>")
    assert sceneview.element_is_hidden(element) is False
    assert sceneview.element_flag_names(element) == []


def test_an_unreadable_scene_flags_value_hides_nothing() -> None:
    """<flags> is Tasker's, and a value this build cannot parse is not grounds for leaving the
    element out of the picture -- the preview is the one place a wrong answer is silent, so an
    unreadable value is drawn as normal rather than dimmed away.
    """
    element = _element("<TextElement><flags>?</flags></TextElement>")
    assert sceneview.element_is_hidden(element) is False
    assert sceneview.element_flag_names(element) == []
