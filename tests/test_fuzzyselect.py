"""The Font pulldown's fuzzy filter (fuzzyselect, fuzzy_match.js and fuzzy_select.js) Unit Tests

The ranking is JavaScript, run in the browser, so it is tested by running it under Node where Node is installed (and
skipped where it is not); what is tested in Python is that the page links it, that the component is NiceGUI's own
select with only the filter changed, and that the font pulldown is one of these.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import nicegui.elements.select as nicegui_select
import pytest
from maptasker.src.core import assettext
from maptasker.src.gui import fuzzyselect, guiwins_tabs, webassets
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from nicegui.testing.user import User

MATCH_JS = assettext.ASSETS_DIR / "js" / "fuzzy_match.js"
SELECT_JS = assettext.ASSETS_DIR / "components" / "fuzzy_select.js"

# What the pulldown holds: monospaced first and marked, then the rest, the way get_font_selections gives them.
FONTS = [
    "Courier (monospaced)",
    "Courier New (monospaced)",
    "Menlo (monospaced)",
    "Apple Braille",
    "Arial",
    "Arial Black",
    "Avenir",
    "Baskerville",
    "Farisi",
    "Helvetica Neue",
    "Marion",
    "Times New Roman",
    "Hack Nerd Font (monospaced)",
    "Noto Sans Canadian Aboriginal",
]

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")


def _filter(typed: str, labels: list[str] = FONTS) -> list[str]:
    """What the pulldown would offer for `typed`, by running the page's own script under Node."""
    script = (
        f"const fuzzy = require({json.dumps(str(MATCH_JS))});"
        f"const options = {json.dumps([{'label': label} for label in labels])};"
        f"console.log(JSON.stringify(fuzzy.filter({json.dumps(typed)}, options).map((o) => o.label)));"
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(done.stdout)


# ==========================================
# The ranking
# ==========================================
@needs_node
def test_what_starts_with_the_text_comes_first_then_the_looser_matches() -> None:
    found = _filter("ari")

    assert found[:2] == ["Arial", "Arial Black"]
    assert found.index("Marion") > 1, "'ari' is inside it, and does not start it"
    assert "Farisi" in found


@needs_node
def test_nothing_that_does_not_match_is_offered() -> None:
    assert _filter("xyz") == []
    assert "Helvetica Neue" not in _filter("ari")


@needs_node
def test_a_word_that_starts_with_the_text_counts_not_only_the_first() -> None:
    assert _filter("bla") == ["Arial Black"]
    assert _filter("new")[:2] == ["Courier New (monospaced)", "Times New Roman"]


@needs_node
def test_one_slip_in_a_longer_word_still_finds_it() -> None:
    """'ariel' is how Arial is often said."""
    assert _filter("ariel")[:2] == ["Arial", "Arial Black"]


@needs_node
def test_a_slip_is_not_forgiven_in_a_short_word() -> None:
    """Three letters with one wrong would match nearly anything."""
    assert "Arial" not in _filter("arx")


@needs_node
def test_the_first_letters_of_the_words_find_it() -> None:
    assert _filter("tnr") == ["Times New Roman"]


@needs_node
def test_letters_in_order_close_together_find_it_from_the_start_of_a_word() -> None:
    assert _filter("avnr") == ["Avenir"]
    assert "Baskerville" not in _filter("ari"), "its letters are there in order, but scattered and mid-word"


@needs_node
def test_case_accents_and_spaces_do_not_matter() -> None:
    assert _filter("ÁRI")[:2] == ["Arial", "Arial Black"]
    assert _filter("times new")[0] == "Times New Roman"
    assert _filter("timesnew")[0] == "Times New Roman"


@needs_node
def test_the_monospaced_mark_can_be_searched_for() -> None:
    assert sorted(_filter("mono")) == sorted(font for font in FONTS if "(monospaced)" in font)


@needs_node
def test_a_font_file_name_finds_the_family_without_its_extension_or_style() -> None:
    assert _filter("Menlo-Regular.ttf")[0] == "Menlo (monospaced)"
    assert _filter("menlo-regular")[0] == "Menlo (monospaced)"
    assert _filter("Menlo.otf")[0] == "Menlo (monospaced)"


@needs_node
def test_a_style_word_part_way_through_being_typed_is_ignored_too() -> None:
    assert _filter("menlo-reg")[0] == "Menlo (monospaced)"
    assert _filter("menlo-r")[0] == "Menlo (monospaced)"


@needs_node
def test_two_style_words_run_together_are_both_ignored() -> None:
    assert _filter("HackNerdFont-BoldItalic.otf")[0] == "Hack Nerd Font (monospaced)"


@needs_node
def test_a_style_word_in_a_family_name_is_found_as_typed() -> None:
    """'Arial Black' is a family, not Arial with a style: stripping 'Black' would put Arial ahead of it."""
    assert _filter("Arial Black")[0] == "Arial Black"
    assert _filter("arial-black")[0] == "Arial Black"


@needs_node
def test_a_style_after_a_family_that_is_there_finds_the_family_before_a_near_miss() -> None:
    """'Arial-Bold' is Arial, not the looser match on Arial Rounded MT Bold."""
    assert _filter("Arial-Bold")[:2] == ["Arial", "Arial Black"]


@needs_node
def test_an_extension_alone_finds_nothing_that_is_not_there() -> None:
    assert _filter("xyz.ttf") == []


@needs_node
def test_nothing_typed_offers_everything_in_the_order_it_came() -> None:
    assert _filter("") == FONTS
    assert _filter("   ") == FONTS


@needs_node
def test_equally_good_matches_keep_the_order_they_came_in() -> None:
    assert _filter("cour") == ["Courier (monospaced)", "Courier New (monospaced)"]


# ==========================================
# The component
# ==========================================
def test_the_page_links_the_script_that_ranks() -> None:
    assert webassets.FUZZY_SCRIPT in webassets.head_html()
    assert MATCH_JS.is_file()


def test_the_component_is_nicegui_s_select_with_only_the_filter_changed() -> None:
    """If NiceGUI changes the code this replaces, the copy has to be made again from the new one."""
    stock_js = Path(nicegui_select.__file__).with_name("select.js").read_text(encoding="utf-8")
    ours = SELECT_JS.read_text(encoding="utf-8")

    for replaced in (
        "update(() => (this.filteredOptions = val ? this.findFilteredOptions() : this.initialOptions));",
        ".filter((v) => String(v.label).toLocaleLowerCase().indexOf(needle) > -1)",
    ):
        assert replaced in stock_js, "NiceGUI's select.js no longer has what fuzzy_select.js replaces"
    assert "window.mtFuzzy.filter" in ours
    for kept in (
        '@popup-show="addClass"',
        "forwardInputValue",
        'this.$emit("update:model-value", ...args);',
        "unmounted()",
    ):
        assert kept in ours, f"fuzzy_select.js lost {kept}"


@contextlib.asynccontextmanager
async def _open(build: Any) -> AsyncIterator[User]:
    try:
        async with user_simulation(root=build) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


@pytest.mark.asyncio
async def test_it_is_a_select_with_a_filter_box_that_uses_the_fuzzy_component() -> None:
    made: dict[str, Any] = {}

    def page() -> None:
        made["select"] = fuzzyselect.FuzzySelect({"a": "Arial", "b": "Avenir"}, value="a", with_input=True)

    async with _open(page):
        select = made["select"]

        assert isinstance(select, ui.select)
        assert select.props["use-input"] is True
        assert select.component is not None
        assert select.component.name == "fuzzy_select"
        assert select.value == "a"


@pytest.mark.asyncio
async def test_the_font_pulldown_is_one_and_shows_the_font_in_effect() -> None:
    made: dict[str, Any] = {}
    chosen: list[Any] = []

    def page() -> None:
        window = SimpleNamespace(
            state=SimpleNamespace(mono_fonts={"Courier": "Courier (monospaced)", "Arial": "Arial"}),
            font="Arial",
            event_handlers=SimpleNamespace(settings=SimpleNamespace(font_event=chosen.append)),
        )
        guiwins_tabs.create_font_section(window)  # type: ignore[arg-type]
        made["window"] = window

    async with _open(page):
        menu = made["window"].font_optionmenu

        assert isinstance(menu, fuzzyselect.FuzzySelect)
        assert menu.props["use-input"] is True
        assert menu.value == "Arial"
        assert made["window"].default_font == "Courier"
