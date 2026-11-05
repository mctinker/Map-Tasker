"""The "Go to top" link on each Map entry is drawn as a hot-link: blue and underlined, like the Map's other links."""

from __future__ import annotations

from maptasker.src.core.sysconst import HOTLINK_STYLE
from maptasker.src.mapgen.lineout import LineOut


def link_for(element: str) -> str:
    return LineOut.add_gototop_link(LineOut.__new__(LineOut), element)


def test_the_link_carries_the_hot_link_style() -> None:
    link = link_for("Project: Home")

    assert f"<a href='#the_top' style=\"{HOTLINK_STYLE}\">Go to top</a>" in link


def test_the_hot_link_style_is_blue_and_underlined() -> None:
    """What makes it look like a link inside the Map view, where a plain anchor takes on the text around it."""
    assert "underline" in HOTLINK_STYLE
    assert "color: #3399ff" in HOTLINK_STYLE


def test_the_link_still_follows_the_name_after_the_same_spacing() -> None:
    short = link_for("Task: A")
    long = link_for("Task: " + "A" * 80)

    assert short.startswith("Task: A" + "&nbsp;" * 20 + "<a ")
    assert long.startswith("Task: " + "A" * 80 + "&nbsp;" * 5 + "<a ")
    assert short.endswith("</a><br>")
