"""MapTasker GUI Event Handlers Unit Tests

This module contains unit tests for the MapTasker GUI event handlers, focusing on
the interaction between the GUI and the underlying logic. The tests are designed to
validate the behavior of the event handlers in response to various user actions and
system states, ensuring that the GUI updates correctly and that the application logic
is executed as expected.

The tests utilize the pytest framework along with unittest.mock for mocking dependencies
and isolating the components under test. Asynchronous tests are handled using pytest-asyncio.

The tests cover a range of scenarios, including:
- UI component interactions and regex parsing.
- Synchronous routine handlers for user input events.
- Asynchronous IO-bound operations and their execution flow.
- Color attribution mapping and event handling.
- Localization: the language in force before the layout is built, and the document
  language declaration that stops a browser re-translating the UI.
- The single Project/Profile/Task/Scene selection being dropped when new XML is loaded.

Note on the message assertions below: user-visible text is passed through
translate_string(), which returns its argument untouched until a language has been
loaded, so the English literal is what these tests compare against. reset_translation()
keeps that true regardless of what an earlier test did.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maptasker.src.guiutils import (
    SINGLE_ITEM_LABELS,
    clear_single_item_view_names,
    is_no_selection,
    reset_single_item_selection,
)
from maptasker.src.guiwins import NiceGuiTextView, document_language_html, set_document_language_js
from maptasker.src.mapfonts import get_monospaced_fonts
from maptasker.src.primitem import PrimeItems
from maptasker.src.userintr import MapTaskerEventHandlers, MyGui

# ==========================================
# FIXTURES & MOCKING SETUP
# ==========================================


@pytest.fixture(autouse=True)
def reset_translation():
    """Guarantee every test runs untranslated, whatever ran before it.

    Translator.set_language() installs PrimeItems._ as a class attribute that then
    outlives the test that caused it, and translate_string() uses it as soon as it
    exists.  One test switching language would otherwise make every later assertion
    against an English literal fail, in test-order-dependent ways.
    """
    had_translator = hasattr(PrimeItems, "_")
    previous = getattr(PrimeItems, "_", None)
    if had_translator:
        del PrimeItems._
    yield
    if had_translator:
        PrimeItems._ = previous
    elif hasattr(PrimeItems, "_"):
        del PrimeItems._


@pytest.fixture
def mock_gui_instance():
    """Creates a decoupled MyGui mockup context with required UI attribute references."""
    gui = MagicMock(spec=MyGui)

    # Initialize basic state variables matching _initialize_gui_settings
    gui.is_updating = False
    gui.display_detail_level = "3"
    gui.view_limit = 10000
    gui.task_action_warning_limit = 20
    gui.font = "Courier New"
    gui.language = "English"
    gui.single_project_name = ""
    gui.single_profile_name = ""
    gui.single_task_name = ""
    gui.single_scene_name = ""
    gui.color_lookup = {}
    gui.everything = False
    gui.appearance_mode = "Light"
    gui.ai_analyze = False

    # Mock visual components
    gui.content_container = MagicMock()
    gui.sidebar_detail_option = MagicMock()
    gui.task_action_limit = MagicMock()
    gui.task_action_label = MagicMock()
    gui.indent_option = MagicMock()
    gui.viewlimit_optionmenu = MagicMock()
    gui.everything_checkbox = MagicMock()
    gui.twisty_checkbox = MagicMock()
    gui.analysis_button = MagicMock()
    gui.tab_analyze = MagicMock()
    gui.tab_specific_name = MagicMock()

    # Mock standard framework methods
    gui.display_message_box = MagicMock()
    gui.get_input_and_put_message = lambda cb, title: cb.value

    return gui


@pytest.fixture
def event_handler(mock_gui_instance):
    """Instantiates event handlers pointing to our mock execution window."""
    return MapTaskerEventHandlers(mock_gui_instance)


class FakeSelect:
    """Stands in for a NiceGUI ui.select: the value and options are all these tests read."""

    def __init__(self, value: str, options: list | None = None) -> None:
        self.value = value
        self.options = options if options is not None else ["None"]

    def update(self) -> None:
        """NiceGUI pushes the change to the browser here; nothing to do in a test."""


@pytest.fixture
def gui_with_selection():
    """A view holding a single-Project selection in all three places one is recorded.

    Mirrors the reported sequence: a Map view was run against one Project, so the view
    attribute, PrimeItems.program_arguments and the pulldown widget all name it.
    """
    gui = MagicMock(spec=MyGui)
    gui.is_updating = False
    gui.specific_name_msg = "Display only Project 'My Project'"
    gui.single_project_name = "My Project"
    gui.single_profile_name = gui.single_task_name = gui.single_scene_name = ""
    for label in SINGLE_ITEM_LABELS:
        # The Project pulldown lists its entries prefixed ("Project: <name>"), which is
        # what the widget's value has to be for the selection to actually show.
        value = "Project: My Project" if label == "Project" else "None"
        setattr(
            gui,
            f"specific_{label.lower()}_optionmenu",
            FakeSelect(value, ["None", "Project: My Project"]),
        )

    saved_args = dict(PrimeItems.program_arguments)
    saved_found = dict(PrimeItems.found_named_items)
    PrimeItems.program_arguments["single_project_name"] = "My Project"
    for key in ("single_profile_name", "single_task_name", "single_scene_name"):
        PrimeItems.program_arguments[key] = ""
    PrimeItems.found_named_items["single_project_found"] = True

    yield gui

    PrimeItems.program_arguments.clear()
    PrimeItems.program_arguments.update(saved_args)
    PrimeItems.found_named_items.clear()
    PrimeItems.found_named_items.update(saved_found)


# ==========================================
# 1. UI COMPONENT & REGEX PARSING TESTS
# ==========================================
def test_html_optimize_pattern_substitution():
    """Validates module-level O(N) single-pass regex compilation constraints."""
    from maptasker.src.guiwins import HTML_OPTIMIZE_PATTERN, HTML_REPLACEMENT_MAP  # noqa: PLC0415

    raw_html = '<h2>MapTasker</h2>\n\n<h2><span class="normtab"></span>Directory</h2>'
    optimized = HTML_OPTIMIZE_PATTERN.sub(
        lambda match: HTML_REPLACEMENT_MAP[match.group(0)],
        raw_html,
    )

    assert '<a id="the_top"></a><h5>MapTasker</h5>' in optimized
    assert '<h6><span class="normtab"></span>Directory</h6>' in optimized


@pytest.fixture
def font_extractor():
    """extract_first_font_name bound to a stub, so it can be exercised standalone."""
    view_instance = MagicMock()
    view_instance.extract_first_font_name = NiceGuiTextView.extract_first_font_name.__get__(view_instance)
    return view_instance.extract_first_font_name


def test_font_extraction_regex(font_extractor):
    """Tests Font Name Identification using a dynamic system font retrieved from the OS."""
    # 1. Grab a verified standard monospaced font family name from the local system
    # (Falls back to 'Courier' if the system configuration is unexpected)
    try:
        system_mono_font = get_monospaced_fonts()[0]
    except Exception:  # noqa: BLE001
        system_mono_font = "Courier"

    # 2. Construct a dynamic CSS injection string using the real system font name
    css_payload = f"body {{ color: #000; font-family: '{system_mono_font}', monospace; }}"

    # 3. Execute the parser and validate the match
    assert font_extractor(css_payload) == system_mono_font

    # 4. Test a fallback safety failure path
    assert font_extractor("body { color: red; }") == "Font name not found"


@pytest.mark.parametrize(
    ("css", "expected"),
    [
        # The shape MapTasker actually writes: addcss.py emits "font-family:<font>, monospace;"
        # and the Map/Diagram view styles build the same.  A pattern that cannot cross the
        # comma matches none of these, so extract_first_font_name silently failed on every
        # real file and the view fell back to the GUI's current font instead of the one the
        # output was generated with.
        ("font-family:Courier New, monospace;", "Courier New"),
        ("body { font-family: 'Andale Mono', monospace; }", "Andale Mono"),
        ('font-family:"Monaspace Neon", monospace;', "Monaspace Neon"),
        # No fallback stack at all still has to work.
        ("font-family: Courier;", "Courier"),
        ("div { font-family: Menlo }", "Menlo"),
        # Nothing to find -- the caller keys its fallback off this exact string.
        ("body { color: red; }", "Font name not found"),
        ("font-family:;", "Font name not found"),
    ],
)
def test_font_extraction_handles_fallback_stacks(font_extractor, css, expected):
    """The first family is returned whether or not a fallback list follows it."""
    assert font_extractor(css) == expected


# ==========================================
# 2. SYNCHRONOUS ROUTINE HANDLERS
# ==========================================
def test_detail_selected_event(event_handler, mock_gui_instance):
    """Verifies display level modifications and UI state synchronization filters."""
    mock_event = MagicMock()
    mock_event.value = "5"

    event_handler.detail_selected_event(mock_event)

    assert mock_gui_instance.display_detail_level == "5"
    assert mock_gui_instance.sidebar_detail_option.value == "5"


def test_viewlimit_normalization(event_handler, mock_gui_instance):
    """Ensures unlimited integer strings map safely to mathematical overrides (9999999)."""
    mock_gui_instance.is_updating = False

    # Test text conversion boundary values
    event_handler.viewlimit_event(MagicMock(value="Unlimited"))
    assert mock_gui_instance.view_limit == 9999999
    assert mock_gui_instance.viewlimit_optionmenu.value == "Unlimited"

    # Test digit conversions
    event_handler.viewlimit_event(MagicMock(value="25000"))
    assert mock_gui_instance.view_limit == 25000


def test_twisty_versus_everything_mutual_exclusivity(event_handler, mock_gui_instance):
    """Validates mutual exclusivity constraint behavior for global view options."""
    mock_gui_instance.twisty_checkbox.value = True
    mock_gui_instance.everything = True  # Conflict flag activated

    event_handler.twisty_event()

    assert mock_gui_instance.twisty is False
    mock_gui_instance.twisty_checkbox.set_value.assert_called_with(False)
    mock_gui_instance.display_message_box.assert_any_call(
        "'Twisty' and 'Everything' are mutually exclusive.  Unchecking 'Twisty'.",
        "Orange",
    )


# ==========================================
# 3. ASYNCHRONOUS IO-BOUND THREAD TESTS
# ==========================================
@pytest.mark.asyncio
@patch("maptasker.src.userintr._open_popout_window")
@patch("maptasker.src.userintr.output_the_front_matter")
@patch("maptasker.src.userintr.capture_gui_state")
@patch("maptasker.src.userintr.ui")
@patch("maptasker.src.userintr.run.io_bound", new_callable=AsyncMock)
async def test_view_event_map_execution_flow(
    mock_io_bound,
    _mock_ui,
    _mock_capture,
    _mock_front_matter,
    mock_popout,
    event_handler,
    mock_gui_instance,
):
    """Asserts that heavy HTML building offloads safely via NiceGUI thread workers.

    The Map view no longer renders into the main window -- it builds the HTML on a worker
    thread and then opens a '/popout/map' page -- so the handoff and the popout are what
    identify the path, rather than a textview being assigned.
    """
    from maptasker.src.userintr import build_html  # noqa: PLC0415

    mock_gui_instance.view_limit = 5000
    PrimeItems.xml_root = MagicMock()  # Map refuses to run without loaded XML.
    PrimeItems.output_lines = MagicMock()
    PrimeItems.output_lines.output_lines = []
    PrimeItems.error_code = 0

    await event_handler.view_event("map")

    # Verify background execution handoff of the blocking HTML build
    mock_io_bound.assert_awaited_once_with(build_html, "")
    # Verify the rendered view is handed to its own page
    mock_popout.assert_called_once()
    assert mock_popout.call_args.args[0] == "/popout/map"


@pytest.mark.asyncio
@patch("maptasker.src.userintr.ui")
@patch("maptasker.src.userintr.run.io_bound", new_callable=AsyncMock)
async def test_view_event_map_requires_loaded_xml(mock_io_bound, _mock_ui, event_handler, mock_gui_instance):
    """With no XML loaded the Map view must refuse rather than build against nothing."""
    PrimeItems.xml_root = None

    await event_handler.view_event("map")

    mock_io_bound.assert_not_awaited()
    mock_gui_instance.display_message_box.assert_called_once_with(
        "No XML data loaded! Please select a valid XML file first.",
        "Orange",
    )


@pytest.mark.asyncio
async def test_ai_analyze_event_missing_model_safeguard(event_handler, mock_gui_instance):
    """Ensures analytical triggers abort dynamically with clean user feedback paths if no context is selected."""
    mock_gui_instance.ai_model = ""  # No LLM specified

    await event_handler.ai_analyze_event()

    mock_gui_instance.display_message_box.assert_called_once_with("No model selected.", "Orange")


# ==========================================
# 4. COLOR ATTRIBUTION MAPPING TESTS
# ==========================================
def test_extract_color_from_event(event_handler, mock_gui_instance):
    """Tests color category target assignment boundaries across Global lookups."""
    PrimeItems.colors_to_use = {}
    mock_gui_instance.color_lookup = {}

    # Emulate shifting "Projects" label to hex format color definitions
    event_handler.extract_color_from_event("#ff00ff", "Projects")

    assert mock_gui_instance.color_lookup["project_color"] == "#ff00ff"
    assert PrimeItems.colors_to_use["project_color"] == "#ff00ff"


# ==========================================
# 5. LOCALIZATION
# ==========================================
def test_set_startup_language_installs_translation_before_layout():
    """The saved language must be in force before any widget is built.

    Every label is translated by translate_string() at the moment it is created, so a
    language applied after initialize_screen() reaches nothing already on screen.
    """
    saved = PrimeItems.program_arguments.get("language")
    try:
        PrimeItems.program_arguments["language"] = "German"
        PrimeItems.program_arguments["reset"] = False

        gui = MagicMock(spec=MyGui)
        MyGui.set_startup_language(gui)

        assert gui.language == "German"
        assert hasattr(PrimeItems, "_"), "no translation function installed"
        assert PrimeItems._("Execution") == "Ausführung"
    finally:
        PrimeItems.program_arguments["language"] = saved


def test_set_startup_language_ignored_on_reset():
    """A reset run deliberately discards saved settings, so it starts out in English."""
    saved = PrimeItems.program_arguments.get("language")
    try:
        PrimeItems.program_arguments["language"] = "German"
        PrimeItems.program_arguments["reset"] = True

        gui = MagicMock(spec=MyGui)
        MyGui.set_startup_language(gui)

        assert not hasattr(PrimeItems, "_"), "reset run must not install a translation"
    finally:
        PrimeItems.program_arguments["language"] = saved
        PrimeItems.program_arguments["reset"] = False


def test_set_startup_language_rejects_unknown_language():
    """An unrecognized saved value (hand-edited settings) falls back rather than throwing."""
    saved = PrimeItems.program_arguments.get("language")
    try:
        PrimeItems.program_arguments["language"] = "Klingon"
        PrimeItems.program_arguments["reset"] = False

        gui = MagicMock(spec=MyGui)
        MyGui.set_startup_language(gui)

        assert not hasattr(PrimeItems, "_")
    finally:
        PrimeItems.program_arguments["language"] = saved


def test_document_language_declaration():
    """The page must state its language and opt out of browser translation.

    With no lang attribute the browser sniffs the text, decides the GUI is German, and
    translates it back to the reader's language -- undoing every translation MapTasker
    just applied and looking exactly like a localization failure.
    """
    saved = PrimeItems.program_arguments.get("language")
    try:
        PrimeItems.program_arguments["language"] = "Japanese"
        head = document_language_html()

        assert 'document.documentElement.lang = "ja"' in head
        assert 'setAttribute("translate", "no")' in head
        assert 'classList.add("notranslate")' in head
        assert '<meta name="google" content="notranslate">' in head
    finally:
        PrimeItems.program_arguments["language"] = saved


def test_document_language_js_shared_by_both_paths():
    """The page build and the runtime language switch emit the same JavaScript.

    Switching language rebuilds the layout but not the document, so language_set_event
    re-stamps the live lang attribute itself.  Both go through set_document_language_js
    precisely so the two can never disagree about what they set.
    """
    saved = PrimeItems.program_arguments.get("language")
    try:
        PrimeItems.program_arguments["language"] = "French"
        assert set_document_language_js("fr") in document_language_html()
        assert 'document.documentElement.lang = "fr"' in set_document_language_js("fr")
    finally:
        PrimeItems.program_arguments["language"] = saved


# ==========================================
# 6. SINGLE ITEM SELECTION RESET
# ==========================================
def test_is_no_selection_accepts_every_empty_form():
    """Nothing-selected reaches callers as empty, as 'None', and as the translated 'None'."""
    assert is_no_selection("")
    assert is_no_selection("None")
    assert not is_no_selection("My Project")


def test_reset_single_item_selection_clears_all_three_places(gui_with_selection):
    """Loading new XML must drop the previous file's selection everywhere it is held.

    The view attribute, PrimeItems.program_arguments (what a mapping run filters on) and
    the pulldown widget each hold it, and clearing only the first left the newly fetched
    backup being mapped through the old file's Project while its pulldown still showed
    that Project's name.
    """
    reset_single_item_selection(gui_with_selection)

    for label in SINGLE_ITEM_LABELS:
        assert getattr(gui_with_selection, f"single_{label.lower()}_name") == ""
        assert PrimeItems.program_arguments[f"single_{label.lower()}_name"] == ""
        widget = getattr(gui_with_selection, f"specific_{label.lower()}_optionmenu")
        assert widget.value == "None", f"{label} pulldown still shows {widget.value!r}"

    assert gui_with_selection.specific_name_msg == ""
    assert not PrimeItems.found_named_items["single_project_found"]
    # Assigning a select's .value fires its on_change, so the lock has to be released.
    assert gui_with_selection.is_updating is False


def test_clear_view_names_alone_leaves_the_selection_live(gui_with_selection):
    """Pins down why clear_single_item_view_names is not sufficient on its own.

    It is still the right call for restore-from-settings, where PrimeItems holds the name
    being restored and must survive -- so this documents the boundary rather than asking
    for it to change.
    """
    clear_single_item_view_names(gui_with_selection)

    assert gui_with_selection.single_project_name == ""
    # Still the active filter, and still on screen:
    assert PrimeItems.program_arguments["single_project_name"] == "My Project"
    assert gui_with_selection.specific_project_optionmenu.value == "Project: My Project"
