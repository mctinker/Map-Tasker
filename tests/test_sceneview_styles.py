"""The Scene preview's translations: Tasker's colours, sizes and weights into the CSS the browser draws.

None of these draws anything -- each takes a Scene's own values and returns a string -- so they are
tested without a window.  The one that matters most is the colour: Tasker puts the alpha FIRST.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src.gui import sceneview


def _args(inner: str) -> sceneview.ElementArgs:
    return sceneview.ElementArgs(ET.fromstring(f"<RectElement>{inner}</RectElement>"))


# ##################################################################################
# Colours
# ##################################################################################
def test_tasker_writes_the_alpha_first_and_css_wants_it_last() -> None:
    """ "#CA33DD20" is a green at 79% opacity; handed to CSS unchanged it would be a blue-grey at 12%."""
    colour = sceneview.tasker_colour("#CA33DD20")
    assert colour.css == "rgba(51,221,32,0.792)"
    assert colour.known


@pytest.mark.parametrize("short", ["#FFF", "#336699"])
def test_a_colour_css_already_understands_is_passed_through(short: str) -> None:
    assert sceneview.tasker_colour(short).css == short


@pytest.mark.parametrize("nothing", [None, "", "   "])
def test_no_colour_is_the_fallback_and_unknown(nothing: str | None) -> None:
    colour = sceneview.tasker_colour(nothing, fallback="white")
    assert colour.css == "white"
    assert not colour.known


def test_a_variable_colour_is_flagged_so_it_can_be_hatched() -> None:
    """Its value is not known until Tasker runs, and the preview must not guess one."""
    colour = sceneview.tasker_colour("%Accent")
    assert colour.is_variable
    assert colour.variable == "%Accent"
    assert not colour.known


@pytest.mark.parametrize("bad", ["#GGGGGGGG", "red", "#12345", "rgb(1,2,3)"])
def test_a_colour_that_is_not_one_is_the_fallback(bad: str) -> None:
    colour = sceneview.tasker_colour(bad, fallback="grey")
    assert colour.css == "grey"
    assert not colour.known


# ##################################################################################
# An element's own arguments
# ##################################################################################
def test_arguments_are_read_by_number() -> None:
    args = _args("<Str sr='arg2'>#FF0000FF</Str><Int sr='arg4' val='3'/><Str sr='arg9'>7</Str>")
    assert args.text(2) == "#FF0000FF"
    assert args.number(4) == 3
    assert args.number(9) == 7  # a number Tasker kept as a string
    assert args.text(99, "default") == "default"
    assert args.number(99, 5) == 5


def test_an_empty_string_argument_is_empty_not_none() -> None:
    assert _args("<Str sr='arg5'/>").text(5) == ""


def test_an_argument_that_is_not_a_number_falls_back() -> None:
    assert _args("<Str sr='arg1'>%Width</Str>").number(1, 10) == 10
    assert _args("<Int sr='arg1' val='x'/>").number(1, 10) == 10


def test_the_raw_number_is_shown_as_it_was_written() -> None:
    assert _args("<Str sr='arg1'>%Max</Str>").raw_number(1) == "%Max"
    assert _args("<Int sr='arg1' val='9'/>").raw_number(1) == "9"


def test_an_image_is_an_icon_a_file_or_nothing() -> None:
    assert _args("<Img sr='arg3'><nme>ic_home</nme></Img>").image(3) == ("icon", "ic_home")
    assert _args("<Img sr='arg3'><fle>/sdcard/a.png</fle></Img>").image(3) == ("file", "/sdcard/a.png")
    assert _args("<Img sr='arg3'/>").image(3) == ("", "")
    assert _args("").image(3) == ("", "")


# ##################################################################################
# A rectangle
# ##################################################################################
def test_a_rectangle_with_a_fill_is_filled() -> None:
    assert sceneview._rect_style(_args("<Str sr='arg2'>#FF336699</Str>")) == "background: rgba(51,102,153,1.0);"


def test_a_rectangle_with_no_colour_draws_no_background() -> None:
    assert sceneview._rect_style(_args("")) == ""


def test_a_variable_fill_is_hatched_not_guessed() -> None:
    assert sceneview.VARIABLE_FILL in sceneview._rect_style(_args("<Str sr='arg2'>%Fill</Str>"))


def test_a_shader_with_two_colours_is_a_gradient() -> None:
    style = sceneview._rect_style(
        _args("<Int sr='arg1' val='1'/><Str sr='arg2'>#FFFF0000</Str><Str sr='arg3'>#FF0000FF</Str>")
    )
    assert style.startswith("background: linear-gradient(to right, ")


def test_a_border_has_a_width_and_a_colour() -> None:
    style = sceneview._rect_style(_args("<Int sr='arg4' val='2'/><Str sr='arg5'>#FF0000FF</Str>"))
    assert "border: 2px solid rgba(0,0,255,1.0);" in style


def test_a_border_with_no_colour_gets_a_neutral_one() -> None:
    assert "rgba(148,163,184,0.9)" in sceneview._rect_style(_args("<Int sr='arg4' val='1'/>"))


@pytest.mark.parametrize(
    ("corners", "expected"),
    [
        (0, "8px 8px 8px 8px"),
        (1, "8px 8px 0 0"),  # top
        (2, "0 0 8px 8px"),  # bottom
        (3, "8px 0 0 8px"),  # left
        (4, "0 8px 8px 0"),  # right
        (99, "8px 8px 8px 8px"),  # an unknown setting rounds them all
    ],
)
def test_the_corner_radius_applies_to_the_corners_asked_for(corners: int, expected: str) -> None:
    style = sceneview._rect_style(_args(f"<Int sr='arg6' val='8'/><Int sr='arg7' val='{corners}'/>"))
    assert f"border-radius: {expected};" in style


# ##################################################################################
# Version 2 Scene lengths and weights
# ##################################################################################
@pytest.mark.parametrize(
    ("source", "keys", "expected"),
    [
        ({"all": "16"}, ("all",), "16px"),
        ({"all": "16.5"}, ("all",), "16.5px"),
        ({"all": " 8 "}, ("all",), "8px"),
        ({"all": "%Pad"}, ("all",), ""),  # a variable is not a length
        ({"all": "wide"}, ("all",), ""),
        ({}, ("all",), ""),
        ({"height": "4"}, ("all", "height"), "4px"),  # the first of the keys that is there
        ({"all": "%x", "height": "4"}, ("all", "height"), "4px"),  # ...and skips a variable
    ],
)
def test_a_length_is_the_first_usable_key_in_pixels(source: dict, keys: tuple, expected: str) -> None:
    assert sceneview._v2_number(source, *keys) == expected


def test_padding_composes_the_way_compose_does() -> None:
    style = sceneview._v2_padding({"horizontal": "8", "bottom": "2"})
    assert "padding-left: 8px;" in style
    assert "padding-right: 8px;" in style
    assert "padding-bottom: 2px;" in style
    assert "padding-top" not in style


def test_a_size_given_as_all_sets_both_sides() -> None:
    assert sceneview._v2_size({"all": "40"}) == "width: 40px; height: 40px; flex: none;"


def test_a_size_given_separately_sets_each() -> None:
    assert sceneview._v2_size({"width": "10", "height": "20"}) == "width: 10px;height: 20px;flex: none;"
    assert sceneview._v2_size({"width": "10"}) == "width: 10px;flex: none;"


def test_a_size_with_nothing_usable_sets_nothing() -> None:
    assert sceneview._v2_size({"width": "%w"}) == ""
    assert sceneview._v2_size({}) == ""


def test_maximum_sizes_become_max_properties() -> None:
    assert sceneview._v2_size_in({"maxWidth": "100", "maxHeight": "50"}) == "max-width: 100px;max-height: 50px;"
    assert sceneview._v2_size_in({}) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.5", "opacity: 0.5;"), ("2", "opacity: 1.0;"), ("-1", "opacity: 0.0;"), ("faint", ""), ("", "")],
)
def test_alpha_is_held_between_zero_and_one(value: str, expected: str) -> None:
    assert sceneview._v2_alpha({"value": value}) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("Bold", "font-weight: 700;"),
        ("Extra Light", "font-weight: 200;"),
        ("semi bold", "font-weight: 600;"),
        ("300", "font-weight: 300;"),
        ("650.0", "font-weight: 650;"),
        ("1000", ""),  # off CSS's scale
        ("50", ""),
        ("%weight", ""),
        ("", ""),
    ],
)
def test_a_font_weight_is_a_name_or_a_number_css_knows(amount: str, expected: str) -> None:
    assert sceneview._v2_weight({"amount": amount}) == expected


@pytest.mark.parametrize(
    ("fraction", "expected"),
    [("0.5", "50%"), ("", "100%"), ("junk", "100%"), ("3", "100%"), ("-1", "0%")],
)
def test_a_fill_takes_a_fraction_of_the_space(fraction: str, expected: str) -> None:
    assert sceneview._v2_fraction({"fraction": fraction}) == expected


def test_a_circle_is_round_whatever_its_radius_says() -> None:
    assert sceneview._v2_shape({"shape": "Circle", "radius": "4"}) == "border-radius: 50%;"
    assert sceneview._v2_shape({"shape": "Rounded", "radius": "4"}) == "border-radius: 4px;"
    assert sceneview._v2_shape({"shape": "Rounded"}) == ""


# ##################################################################################
# What a button does
# ##################################################################################
@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ({"type": "SetVariable", "variable": "%a", "value": "1"}, "SetVariable %a = 1"),
        ({"type": "SetVariable"}, "SetVariable ? = "),
        ({"type": "ToggleVariable", "variable": "%on"}, "ToggleVariable %on"),
        ({"type": "RunTask", "task": "Wake Up"}, "RunTask 'Wake Up'"),
        ({"type": "DismissLayout"}, "DismissLayout"),
        ({"type": "DismissLayout", "result": "ok"}, "DismissLayout → ok"),
        ({"type": "OutputToVariable"}, "OutputToVariable"),
        ({"type": "OutputToVariable", "bindings": {"a": ["%x", "%y"]}}, "OutputToVariable a→%x, %y"),
        ({"type": "DoSomething", "x": 1, "nested": {"y": 2}, "list": [3]}, "DoSomething(x=1)"),
        ({"type": "Mystery"}, "Mystery"),
        ({}, "?"),
    ],
)
def test_an_action_is_described_in_a_line(action: dict, expected: str) -> None:
    assert sceneview._v2_action_text(action) == expected


def test_markup_is_taken_off_and_entities_put_back() -> None:
    assert sceneview._v2_plain_text("Tom &amp; <b>Jerry</b>") == "Tom & Jerry"
