"""colors: the named colors are data (assets/json/color_names.json); how they are used is not.

validate_color's answers and the '-ch' listing are what the data file must keep producing,
so these pin the answers rather than the file's layout.
"""

from __future__ import annotations

import json

import pytest
from maptasker.src import colors
from maptasker.src.error import MapTaskerError


def test_every_named_color_is_valid() -> None:
    for names in colors.color_names().values():
        for name in names:
            assert colors.validate_color(name), name


@pytest.mark.parametrize("value", ["db29ff", "DB29FF", "fff", "0"])
def test_a_hex_value_is_valid(value: str) -> None:
    assert colors.validate_color(value) is True


@pytest.mark.parametrize("value", ["NotAColor", "red", "gg", "#fff"])
def test_anything_else_is_not(value: str) -> None:
    assert colors.validate_color(value) is False


def test_the_color_families_are_the_ten_there_have_always_been() -> None:
    families = colors.color_names()

    assert list(families) == ["Red", "Pink", "Orange", "Yellow", "Purple", "Green", "Blue", "Brown", "White", "Gray"]
    assert all(names and all(isinstance(name, str) for name in names) for names in families.values())
    assert sum(len(names) for names in families.values()) == 143


def test_the_file_is_valid_json_in_the_shape_it_is_read(tmp_path: object) -> None:
    with open(colors.COLOR_NAMES_FILE, encoding="utf-8") as file:
        data = json.load(file)

    assert data == colors.color_names()


def test_color_help_lists_every_family_then_the_hex_hint_and_ends_the_run(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(MapTaskerError):
        colors.validate_color("h")

    shown = capsys.readouterr().out
    positions = [shown.index(f"{family} color names:") for family in colors.color_names()]
    assert positions == sorted(positions)
    assert shown.index("Any color:") > positions[-1]
    assert "IndianRed" in shown
    assert "hex value.  Example 'db29ff'" in shown
