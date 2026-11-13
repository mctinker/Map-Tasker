"""The font name in the Diagram's header hint is a link to download it (guiwins_diagram._linked_font_hint)

The hint is plain text in the Diagram's file; the view makes the font's name a link, on the header lines only and only
where nothing else is drawn, so a Task that happens to be named the same is never turned into one.
"""

from __future__ import annotations

import gettext
from pathlib import Path

from maptasker.src.core.sysconst import DIAGRAM_FONT_LINK_TEXT, DIAGRAM_FONT_URL
from maptasker.src.gui.guiwins_diagram import HEADER_LINES, wrap_diagram_line
from maptasker.src.mapgen import diagram

HINT = "Display with a monospaced font (e.g. Menlo - monospaced) for accurate column alignment. And turn off line wrap."


def test_the_font_name_in_the_hint_is_a_link_to_the_download_that_opens_in_a_new_tab() -> None:
    html = wrap_diagram_line(2, HINT, {}, {}, {})

    assert f'<a href="{DIAGRAM_FONT_URL}"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert f">{DIAGRAM_FONT_LINK_TEXT}</a>" in html


def test_the_rest_of_the_hint_is_the_same_text_either_side_of_the_link() -> None:
    html = wrap_diagram_line(2, HINT, {}, {}, {})

    assert "Display with a monospaced font (e.g. <a " in html
    assert "</a>) for accurate column alignment. And turn off line wrap." in html


def test_only_the_font_name_is_the_link() -> None:
    assert wrap_diagram_line(2, HINT, {}, {}, {}).count("<a ") == 1


def test_a_line_below_the_header_with_the_same_words_is_not_made_a_link() -> None:
    assert "<a " not in wrap_diagram_line(HEADER_LINES, HINT, {}, {}, {})
    assert "<a " not in wrap_diagram_line(500, HINT, {}, {}, {})


def test_a_header_line_with_a_name_or_connector_drawn_on_it_is_not_made_a_link() -> None:
    node = {"col": 0, "len": 5, "anchor": "t1", "index": 0, "kind": "task"}

    assert "<a " not in wrap_diagram_line(2, HINT, {}, {2: [node]}, {})
    assert "<a " not in wrap_diagram_line(2, HINT, {2: [(0, 3, 1)]}, {}, {})


def test_a_line_without_the_font_name_is_left_alone() -> None:
    assert "<a " not in wrap_diagram_line(2, "Configuration Map", {}, {}, {})


def test_html_in_the_line_around_the_link_is_still_escaped() -> None:
    html = wrap_diagram_line(1, f"<b> {DIAGRAM_FONT_LINK_TEXT} & <i>", {}, {}, {})

    assert "&lt;b&gt; <a " in html
    assert "</a> &amp; &lt;i&gt;" in html


def test_the_download_is_a_secure_link_to_the_regular_font_file() -> None:
    assert DIAGRAM_FONT_URL.startswith("https://")
    assert DIAGRAM_FONT_URL.endswith("Menlo-Regular.ttf")


def test_the_hint_the_diagram_writes_names_the_font_the_link_is_made_from() -> None:
    """If the wording in diagram.py changes, the link text must still be in it, or the link is never made."""
    assert DIAGRAM_FONT_LINK_TEXT in Path(diagram.__file__).read_text(encoding="utf-8")
    assert "e.g. Menlo - monospaced" in Path(diagram.__file__).read_text(encoding="utf-8")


def test_every_language_keeps_the_words_the_link_is_made_from() -> None:
    """The font's name in the pulldown is always English, so the hint names it as it is, in every language.

    A translation that turned 'Menlo - monospaced' into the local words would have no link in the Diagram.
    """
    locale = Path(diagram.__file__).resolve().parents[2] / "locale"
    catalogs = sorted(locale.glob("*/LC_MESSAGES/messages.mo"))
    assert len(catalogs) >= 30

    for catalog in catalogs:
        with catalog.open("rb") as handle:
            translation = gettext.GNUTranslations(handle).gettext(HINT)
        assert translation != HINT, f"{catalog.parent.parent.name} has no translation of the hint"
        assert DIAGRAM_FONT_LINK_TEXT in translation, catalog.parent.parent.name
