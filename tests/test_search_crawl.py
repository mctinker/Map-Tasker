"""The page-side script behind the view search (guiwins_search.search_crawl_js).

The script is a .js file under maptasker/assets with four placeholders, filled in per search.
What matters is that each lands where the script expects it, and that nothing a user types
into the search box can be read as a placeholder -- or as anything but a string.
"""

from __future__ import annotations

import json

from maptasker.src import assettext, guiwins_search

_PLACEHOLDERS = ("__SCROLL_AREA_ID__", "__SEARCH_TERM__", "__TERM_LENGTH__", "__CONTENT_TOKEN__")


def test_the_script_is_shipped_with_the_assets() -> None:
    assert (assettext.ASSETS_DIR / guiwins_search.SEARCH_CRAWL_SCRIPT).is_file()


def test_every_placeholder_is_filled_in_exactly_once() -> None:
    template = assettext.text(guiwins_search.SEARCH_CRAWL_SCRIPT)
    script = guiwins_search.search_crawl_js(42, "Hello", 7)

    for placeholder in _PLACEHOLDERS:
        assert template.count(placeholder) == 1
        assert placeholder not in script
    assert 'document.getElementById("c42")' in script
    assert 'const searchTerm = "hello";' in script
    assert "const termLength = 5;" in script
    assert "const contentToken = 7;" in script


def test_the_term_is_searched_lowercase_but_measured_as_typed() -> None:
    """The page lowercases the content it compares against, and slices by the term's own length."""
    script = guiwins_search.search_crawl_js(1, "ÜBER", 0)

    assert f"const searchTerm = {json.dumps('über')};" in script
    assert "const termLength = 4;" in script


def test_a_term_cannot_break_out_of_its_string_or_pose_as_a_placeholder() -> None:
    hostile = 'a "quoted" \\ term </script> __TERM_LENGTH__ __CONTENT_TOKEN__'
    script = guiwins_search.search_crawl_js(3, hostile, 9)

    assert f"const searchTerm = {json.dumps(hostile.lower())};" in script
    assert f"const termLength = {len(hostile)};" in script
    assert "const contentToken = 9;" in script
    # The lookalikes sit inside the term's own string, untouched.
    assert "__term_length__ __content_token__" in script
