"""MapTasker help screen (userhelp) Unit Tests

The 'Display Help' popup is assembled rather than looked up, because the version number
sits in the middle of it and no catalog can hold a msgid containing "13.0.2".  That makes
the assembly the thing to test: it broke once already, when the help text was reworded and
the heading the assembler searched for ("Help\n\n") became "Help  \n".  Nothing raised.
gettext answers a miss by handing back the string it was given, so the popup came up in
English in all 33 languages and looked for all the world like a translation.

So these tests assert against a real shipped catalog -- German, translated in full -- and
they assert on the pieces, since a screen that has silently stopped matching its msgid is
exactly what has no other symptom.
"""

from __future__ import annotations

import pytest

from maptasker.src import userhelp, userintr
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import VERSION
from maptasker.src.translator import T

# The pieces the GUI's help popups are built from, all of which the catalogs carry.
# userhelp.COMMAND_REFERENCE_TEXT is deliberately not among them: it was added to the help
# screen after the last catalog sync, so it is still English everywhere until
# sync_missing_msgids.py and po_to_mo.sh are run again.
TRANSLATED_HELP_PIECES = (
    "INFO_TEXT",
    "HELP_HEADING",
    "BACKUP_HELP_TEXT",
    "LISTFILES_HELP_TEXT",
    "VIEW_HELP_TEXT",
    "VIEWLIMIT_HELP_TEXT",
    "AI_HELP_TEXT",
    "APIKEY_HELP_TEXT",
)


@pytest.fixture
def german() -> None:
    """The GUI's language set to German, and put back afterwards.

    PrimeItems._ is global state: leaving a language behind here would translate whatever
    another test happens to look up next.
    """
    previous = getattr(PrimeItems, "_", None)
    T.set_language("German")
    yield
    if previous is None:
        delattr(PrimeItems, "_")
    else:
        PrimeItems._ = staticmethod(previous)


def test_help_screen_is_translated(german: None) -> None:
    """The body of the popup comes up in the selected language, not English."""
    screen = userhelp.build_help(translate_string)
    assert translate_string(userhelp.INFO_TEXT) in screen
    assert userhelp.INFO_TEXT not in screen


def test_help_heading_is_translated(german: None) -> None:
    """The heading beside the version number is looked up too."""
    screen = userhelp.build_help(translate_string)
    heading = translate_string(userhelp.HELP_HEADING)
    assert heading != userhelp.HELP_HEADING, "the German catalog should translate 'Help'"
    assert f"MapTasker {VERSION} {heading}" in screen


def test_version_is_never_translated(german: None) -> None:
    """The version goes in verbatim.  It is the reason the screen is assembled from pieces:
    were it part of a msgid, every release would invalidate the whole help translation.
    """
    assert f"MapTasker {VERSION} " in userhelp.build_help(translate_string)
    assert f"MapTasker {VERSION} " in userhelp.build_help()


def test_untranslated_screen_stays_english() -> None:
    """Called with no lookup -- the CLI, or before a language is chosen -- it is English."""
    screen = userhelp.build_help()
    assert userhelp.INFO_TEXT in screen
    assert screen.startswith(f"MapTasker {VERSION} {userhelp.HELP_HEADING}")
    assert screen.endswith(userhelp.COMMAND_REFERENCE_TEXT)


@pytest.mark.parametrize("name", TRANSLATED_HELP_PIECES)
def test_help_piece_is_still_a_msgid(name: str, german: None) -> None:
    """Every piece of help text the GUI shows is a msgid the catalogs actually hold.

    A reworded help string is a new msgid, and its translation is lost until the catalogs
    are synced -- with no error, no warning and no visible difference from a screen that
    was never translated.  This is the test that says so: if it fails after an edit to
    userhelp.py, run Language_Support_Utilities/sync_missing_msgids.py and then po_to_mo.sh.
    """
    english = getattr(userhelp, name)
    assert translate_string(english) != english, f"{name} is no longer in the German catalog"


def test_display_help_popup_is_translated(german: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """The popup itself, end to end: what 'Display Help' hands the dialog is in German.

    Driven through query_event rather than build_help alone because the break was on this
    side of the call -- the screen was assembled correctly and then sliced apart again here
    on a heading that no longer existed.  The changelog fetch and the dialog are the only
    things stubbed; the text between them is the real thing.
    """
    captured = {}
    monkeypatch.setattr(userintr, "get_changelog_file", lambda *args, **kwargs: ["## 13.0.3", "- Fixed: something."])
    monkeypatch.setattr(
        userintr,
        "create_popup_window",
        lambda title, message="", **kwargs: captured.update(title=title, message=message),
    )

    userintr.MapTaskerEventHandlers.query_event(object(), "help")

    assert translate_string(userhelp.INFO_TEXT) in captured["message"]
    assert userhelp.INFO_TEXT not in captured["message"]
    # The changelog is appended after the translated text, in the English GitHub sends.
    assert captured["message"].endswith("- Fixed: something.")
