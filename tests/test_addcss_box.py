"""The box around a TaskerNet description or a Task label takes the background the user assigned."""

from __future__ import annotations

import pytest
from maptasker.src.mapgen.addcss import box_colors


def _channels(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


@pytest.mark.parametrize("assigned", ["#8787e8", "Lavender", "222623", "#14003c", "LightYellow"])
def test_the_box_is_a_slightly_darker_tone_of_the_assigned_background(assigned: str) -> None:
    box = box_colors(assigned)[0]
    page = _channels(darker_reference(assigned))

    assert all(b <= p for b, p in zip(_channels(box), page, strict=True))
    assert _channels(box) != page, "not the same colour"
    assert all(b >= 0.8 * p - 1 for b, p in zip(_channels(box), page, strict=True)), "only slightly darker"


def darker_reference(assigned: str) -> str:
    """The assigned colour as #rrggbb, for comparing the box against."""
    from maptasker.src.core.htmlsafe import css_color
    from PIL import ImageColor

    red, green, blue = ImageColor.getrgb(css_color(assigned))[:3]
    return f"#{red:02x}{green:02x}{blue:02x}"


def test_the_exact_tone() -> None:
    assert box_colors("#8787e8")[0] == "#7a7ad1"  # 0.9 of each channel


def test_black_stays_black_and_leans_on_its_border() -> None:
    assert box_colors("#000000") == ("#000000", "#8a8f98")


def test_the_border_shows_against_the_background_it_is_on() -> None:
    assert box_colors("#14003c")[1] == "#8a8f98", "light on a dark page"
    assert box_colors("LightYellow")[1] == "#333", "dark on a light one"


@pytest.mark.parametrize("not_a_colour", ["", "not-a-colour"])
def test_with_no_usable_background_the_box_keeps_its_old_shades(not_a_colour: str) -> None:
    assert box_colors(not_a_colour) == ("#f9f9f9", "#333")
