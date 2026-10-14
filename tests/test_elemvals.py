"""Profile/Task flags: priority, collision and Keep Device Awake, read off one XML element."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from maptasker.src.core import elemvals


def _element(inner: str = "") -> ET.Element:
    return ET.fromstring(f"<Task>{inner}</Task>")  # noqa: S314  (fixture text, defined in this file)


@pytest.mark.parametrize("function", [elemvals.get_collision, elemvals.get_awake])
def test_no_element_gives_no_flag(function: object) -> None:
    """A Profile or Task that was not found is not an error, just nothing to say."""
    assert function(None) == ""


def test_no_element_gives_no_priority_either_way() -> None:
    """Both forms -- the Event condition's and the Profile's -- come back empty."""
    assert elemvals.get_priority(None, event=True) == ""
    assert elemvals.get_priority(None, event=False) == ""


def test_an_element_without_a_priority_has_none() -> None:
    """Tasker leaves out <pri> when it is the default, and so does the Map."""
    assert elemvals.get_priority(_element(), event=False) == ""


def test_a_priority_is_worded_for_where_it_is_shown() -> None:
    """An Event condition carries it inline; a Profile carries it in brackets."""
    element = _element("<pri>7</pri>")
    assert elemvals.get_priority(element, event=True) == " Priority:7"
    assert elemvals.get_priority(element, event=False) == "&nbsp;&nbsp;[Priority: 7]"


def test_the_default_collision_setting_is_left_blank() -> None:
    """No <rty> means Abort The Task On Collision... which Tasker does not write out."""
    assert elemvals.get_collision(_element()) == ""


@pytest.mark.parametrize(
    ("flag", "said"),
    [
        ("0", "Abort New Task"),
        ("1", "Abort Existing Task"),
        ("2", "Run both together"),
        ("", "Abort New Task"),
        ("9", "Abort New Task"),
    ],
)
def test_each_collision_setting_is_named(flag: str, said: str) -> None:
    """Anything Tasker does not number 1 or 2 reads as the first setting, an empty tag included."""
    assert elemvals.get_collision(_element(f"<rty>{flag}</rty>")) == f"&nbsp;&nbsp;[Collision: {said}]"


def test_keep_device_awake_is_reported_when_present() -> None:
    """The presence of <stayawake> is the whole setting."""
    assert elemvals.get_awake(_element("<stayawake>true</stayawake>")) == "&nbsp;&nbsp;[Keep Device Awake]"
    assert elemvals.get_awake(_element()) == ""


def _state(*, pretty: bool) -> object:
    """The one part of a run these functions read."""
    return SimpleNamespace(program_arguments=SimpleNamespace(pretty=pretty))


def test_no_kid_app_says_nothing() -> None:
    """Most Projects were not made from a Kid App, and the Project that was not found is not an error."""
    assert elemvals.get_kid_app(None, _state(pretty=False)) == ""
    assert elemvals.get_kid_app(_element(), _state(pretty=False)) == ""


def test_a_kid_app_is_described_with_its_features_and_plugins() -> None:
    element = _element(
        "<Kid><pkg>com.example.kid</pkg><vnme>1.2</vnme><vTarg>34</vTarg>"
        "<feat1>Wifi</feat1><feat2>Sms</feat2><mplug1>Zoom</mplug1></Kid>",
    )

    described = elemvals.get_kid_app(element, _state(pretty=False))

    assert "Kid App Package:com.example.kid" in described
    assert "Version Name:1.2" in described
    assert "Target Android Version:34" in described
    assert "1=Wifi, 2=Sms" in described
    assert "Plugins: 1=Zoom" in described


def test_a_kid_app_without_features_or_plugins_lists_neither() -> None:
    described = elemvals.get_kid_app(
        _element("<Kid><pkg>a.b</pkg><vnme>1</vnme><vTarg>30</vTarg></Kid>"), _state(pretty=False)
    )
    assert "Features" not in described
    assert "Plugins" not in described


def test_pretty_mode_puts_each_kid_app_detail_on_its_own_line() -> None:
    element = _element("<Kid><pkg>a.b</pkg><vnme>1</vnme><vTarg>30</vTarg></Kid>")
    plain = elemvals.get_kid_app(element, _state(pretty=False))
    pretty = elemvals.get_kid_app(element, _state(pretty=True))
    assert plain.count("<br>") < pretty.count("<br>")
