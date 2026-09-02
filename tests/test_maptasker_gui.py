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

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

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
# Fixtures & MOCKING SETUP
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
    gui.display_detail_level = 3
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

    # An int on the GUI object -- every reader of display_detail_level compares it
    # numerically -- and the string the pulldown's own options are made of.
    assert mock_gui_instance.display_detail_level == 5
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
    # Verify the rendered view is handed to its own page.  The path and the query are
    # checked apart from one another: the path is what identifies the page, while the
    # query carries the jump target and the Project the Map was built for, and those two
    # keys have to reach the popout whether or not this run has anything to put in them.
    mock_popout.assert_called_once()
    opened = urlparse(mock_popout.call_args.args[0])
    assert opened.path == "/popout/map"
    assert parse_qs(opened.query, keep_blank_values=True) == {"goto": [""], "scope": [""]}


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


# ==========================================
# COMPARE FILES EVENT
# ==========================================
# The event that ties the comparison feature together: choose a file, load it without
# disturbing the loaded one (diffload), compare (xmldiff), save and display.  Every
# collaborator is patched here -- each has its own tests in test_diffload.py and
# test_xmldiff.py -- so what is under test is the wiring and the guards, which is where
# this layer's own logic lives.


@pytest.fixture
def _loaded_configuration():
    """PrimeItems holding something, so the event's "nothing loaded" guard passes."""
    previous = PrimeItems.tasker_root_elements
    PrimeItems.tasker_root_elements = {
        "all_projects": {},
        "all_profiles": {},
        "all_tasks": {"20": {"xml": None, "name": "Runner"}},
        "all_scenes": {},
        "all_services": [],
    }
    yield
    PrimeItems.tasker_root_elements = previous


@contextlib.contextmanager
def _patched_collaborators(**overrides):
    """Patch every name compare_files_event reaches for, with sensible defaults.

    A context manager over an ExitStack rather than a pile of nested `with`s: the event
    reaches for nine names, and only the one or two a given test overrides are worth
    seeing at the call site.
    """
    defaults = {
        "_choose_comparison_file": AsyncMock(return_value="/other/backup.xml"),
        "loaded_file_path": MagicMock(return_value="/loaded/backup.xml"),
        "load_for_comparison": MagicMock(return_value=(MagicMock(), "")),
        "current_configuration": MagicMock(return_value=MagicMock()),
        "order_by_age": MagicMock(side_effect=lambda a, b: (a, b)),
        "compare": MagicMock(return_value=("a report", {"ADDED": 1, "REMOVED": 0, "RENAMED": 0, "CHANGED": 0})),
        "write_comparison_report": MagicMock(return_value="MapTasker_Compare_01-01-2026_00-00-00.txt"),
        "NiceGuiTextView": MagicMock(),
        "ui": MagicMock(),
    }
    defaults.update(overrides)
    with contextlib.ExitStack() as stack:
        for name, value in defaults.items():
            stack.enter_context(patch(f"maptasker.src.userintr.{name}", value))
        yield


@pytest.mark.asyncio
async def test_compare_refuses_with_nothing_loaded(event_handler, mock_gui_instance):
    """No XML loaded means there is nothing to compare against, and it says so."""
    previous = PrimeItems.tasker_root_elements
    PrimeItems.tasker_root_elements = {"all_tasks": {}}
    chooser = AsyncMock()
    try:
        with patch("maptasker.src.userintr._choose_comparison_file", chooser):
            await event_handler.compare_files_event()
    finally:
        PrimeItems.tasker_root_elements = previous

    mock_gui_instance.display_message_box.assert_called_once()
    assert "No XML file has been loaded" in mock_gui_instance.display_message_box.call_args[0][0]
    chooser.assert_not_awaited()


@pytest.mark.asyncio
async def test_compare_cancelled_does_nothing(event_handler, mock_gui_instance, _loaded_configuration):
    """Backing out of the chooser writes no report and opens no view."""
    writer = MagicMock()
    with _patched_collaborators(
        _choose_comparison_file=AsyncMock(return_value=""),
        write_comparison_report=writer,
    ):
        await event_handler.compare_files_event()

    writer.assert_not_called()
    mock_gui_instance.display_message_box.assert_not_called()


@pytest.mark.asyncio
async def test_compare_refuses_the_file_already_loaded(event_handler, mock_gui_instance, _loaded_configuration):
    """Picking the loaded file is a mistake worth naming.

    Left to run, it produces a report saying nothing differs -- a confusing way to find
    out you picked the wrong file.
    """
    loader = MagicMock()
    with _patched_collaborators(
        _choose_comparison_file=AsyncMock(return_value="/loaded/backup.xml"),
        loaded_file_path=MagicMock(return_value="/loaded/backup.xml"),
        load_for_comparison=loader,
    ):
        await event_handler.compare_files_event()

    loader.assert_not_called()
    assert "already loaded" in mock_gui_instance.display_message_box.call_args[0][0]


@pytest.mark.asyncio
async def test_compare_reports_a_file_that_would_not_load(event_handler, mock_gui_instance, _loaded_configuration):
    """A bad comparison file is a message, and no view."""
    view = MagicMock()
    with _patched_collaborators(
        load_for_comparison=MagicMock(return_value=(None, "backup.xml could not be read.")),
        NiceGuiTextView=view,
    ):
        await event_handler.compare_files_event()

    mock_gui_instance.display_message_box.assert_called_once_with("backup.xml could not be read.", "Red")
    view.assert_not_called()


@pytest.mark.asyncio
async def test_compare_saves_and_displays(event_handler, mock_gui_instance, _loaded_configuration):
    """The whole path: ordered by age, compared, saved, displayed."""
    view = MagicMock()
    order = MagicMock(side_effect=lambda a, b: (a, b))
    with _patched_collaborators(NiceGuiTextView=view, order_by_age=order):
        await event_handler.compare_files_event()

    order.assert_called_once()
    assert "Comparison saved as" in mock_gui_instance.display_message_box.call_args[0][0]
    view.assert_called_once()
    assert view.call_args.kwargs["title"] == "Misc View"


@pytest.mark.asyncio
async def test_compare_escapes_the_report_for_display(event_handler, mock_gui_instance, _loaded_configuration):
    """A Tasker name holding '<' must reach the view as text, not as markup.

    NiceGuiTextView's Misc branch drops its content into a <pre> with sanitize=False, so
    the escape is the only thing standing between a Task named "<b>" and the page.
    """
    view = MagicMock()
    with _patched_collaborators(
        compare=MagicMock(return_value=("Task '<b>' & co", {"ADDED": 1, "REMOVED": 0, "RENAMED": 0, "CHANGED": 0})),
        NiceGuiTextView=view,
    ):
        await event_handler.compare_files_event()

    assert view.call_args.kwargs["the_data"] == "Task &#x27;&lt;b&gt;&#x27; &amp; co"


@pytest.mark.asyncio
async def test_compare_says_so_when_the_files_match(event_handler, mock_gui_instance, _loaded_configuration):
    """Two identical files produce a report that looks empty, so it is said out loud."""
    fake_ui = MagicMock()
    with _patched_collaborators(
        compare=MagicMock(return_value=("no differences", {"ADDED": 0, "REMOVED": 0, "RENAMED": 0, "CHANGED": 0})),
        ui=fake_ui,
    ):
        await event_handler.compare_files_event()

    notifications = [call.args[0] for call in fake_ui.notify.call_args_list]
    assert any("same configuration" in text for text in notifications)


@pytest.mark.asyncio
async def test_compare_still_displays_when_the_save_fails(event_handler, mock_gui_instance, _loaded_configuration):
    """A comparison whose report displayed fine is still worth showing when only the save
    went wrong -- the same call healthck's writer makes."""
    view = MagicMock()
    with _patched_collaborators(write_comparison_report=MagicMock(return_value=""), NiceGuiTextView=view):
        await event_handler.compare_files_event()

    assert "could not be saved" in mock_gui_instance.display_message_box.call_args[0][0]
    view.assert_called_once()


# ==========================================
# Importing a Profile into Tasker from the Edit Profile dialog
#
# The Save Profile To Android dialog now has two buttons that do genuinely different things.
# 'Save As File' uploads a .prf.xml Tasker never reads; 'Import Into Tasker' puts the
# Profile in front of Tasker's own import screen and waits for a person to tap Import.
#
# The person in the middle is what these are about.  Opening the screen and importing are
# not the same event, so the handler runs in two phases -- and the failure that matters is
# the one where it treats phase one as if it were phase two: MapTasker would show the edit
# as landed while the phone still had the dialog up, or had been declined.
# ==========================================


class _FakeField:
    """Stands in for a NiceGUI ui.input: .value is all the handler reads."""

    def __init__(self, value: str) -> None:
        self.value = value


@pytest.fixture
def profile_dialog_refs():
    """The two field_refs dicts the handler is given, for an EXISTING Profile (no
    'target_project_name' key -- that key's presence is what marks a brand-new one)."""
    return (
        {"name": _FakeField("Watched")},
        {"ip_address": _FakeField("192.168.0.210"), "ip_port": _FakeField("1821")},
    )


def _patch_import_path(monkeypatch, results: list, exists: bool | None = False) -> dict:
    """Point the handler's collaborators at fakes and record what it did.

    `results` is what run.io_bound returns, in order: the pre-check (see
    deviceinv.import_is_confirmable), the offer, then the confirmation if there is one.

    `exists` is what the device says about the path the import is going to write -- False
    (nothing there) for the ordinary case, True or None to reach the overwrite prompt.  The
    staged file is the object's own now, in Tasker's own folder, so an import can land on a
    file the user saved by hand and is asked about first.
    """
    from maptasker.src import userintr

    calls: dict = {
        "io_bound": [],
        "kept": [],
        "notify": [],
        "pending": [],
        "overwrite": [],
        "backed_up": [],
        # Whether the client's slot was entered for each notification.  nicegui builds an
        # element for every one of these and an element needs a slot, so a False in here is
        # the 'slot stack for this task is empty' crash in a test rather than on a phone.
        "in_slot": [],
    }

    class _FakeClient:
        """nicegui's client, with the one thing that matters here: being enterable."""

        depth = 0

        def __enter__(self):
            _FakeClient.depth += 1
            return self

        def __exit__(self, *_):
            _FakeClient.depth -= 1

    class _FakeContext:
        client = _FakeClient()

    _FakeClient.depth = 0
    monkeypatch.setattr(userintr, "context", _FakeContext)

    async def fake_io_bound(func, *args, **kwargs):
        calls["io_bound"].append((func, args, kwargs))
        return results[len(calls["io_bound"]) - 1]

    async def fake_ping(_self, _ip, _port) -> bool:
        return True

    monkeypatch.setattr(userintr.run, "io_bound", fake_io_bound)
    monkeypatch.setattr(userintr, "ping_android_device", fake_ping)
    # One read of the path answers both questions -- see maputil2.read_android_file.  The
    # content it hands back is what becomes the safety copy, with no second GET.
    monkeypatch.setattr(
        userintr,
        "read_android_file",
        lambda _ip, _port, _path: (exists, b"<TaskerData>the old one</TaskerData>" if exists else b""),
    )
    monkeypatch.setattr(
        userintr.presave,
        "save_android_safety_copy",
        lambda path, content: (calls["backed_up"].append((path, content)), (True, "/copies/old.prf.xml"))[1],
    )
    monkeypatch.setattr(
        userintr,
        "build_overwrite_confirm_dialog",
        lambda what, on_confirm, **kwargs: calls["overwrite"].append((what, on_confirm, kwargs)),
    )
    monkeypatch.setattr(userintr.profedit, "render_standalone_profile_xml", lambda _p: "<TaskerData/>")
    monkeypatch.setattr(userintr.projedit, "render_standalone_project_xml", lambda _n: "<TaskerData/>")
    monkeypatch.setattr(userintr.projedit, "project_profile_names", lambda _n: ["Watched", "Also Watched"])
    monkeypatch.setattr(userintr, "_unapplied_project_edits", lambda _refs: [])
    monkeypatch.setattr(userintr.sceneedit, "render_standalone_scene_xml", lambda _n: "<TaskerData/>")
    monkeypatch.setattr(userintr.sceneedit, "apply_edited_scene_to_live_tree", lambda _n, _s: None)
    monkeypatch.setattr(userintr, "_apply_scene_field_values", lambda _s, _refs: [])
    monkeypatch.setattr(
        userintr.MapTaskerEventHandlers,
        "_apply_profile_for_android",
        lambda _self, _profile, _refs: (True, False, ""),
    )
    monkeypatch.setattr(
        userintr.MapTaskerEventHandlers,
        "_keep_profile_in_loaded_config",
        lambda _self, *args: calls["kept"].append(args),
    )
    def fake_notify(message, **kwargs) -> None:
        calls["notify"].append((message, kwargs.get("type")))
        calls["in_slot"].append(_FakeClient.depth > 0)

    monkeypatch.setattr(userintr.ui, "notify", fake_notify)

    class _FakeNotification:
        """A ui.notification with the one thing the handler uses it for: being taken down."""

        def __init__(self, message, **kwargs) -> None:
            calls["notify"].append((message, kwargs.get("type")))
            calls["in_slot"].append(_FakeClient.depth > 0)
            calls["pending"].append(self)
            self.dismissed = False

        def dismiss(self) -> None:
            self.dismissed = True

    monkeypatch.setattr(userintr.ui, "notification", _FakeNotification)
    return calls


@pytest.mark.asyncio
async def test_a_new_profile_is_waited_for_before_anything_is_claimed(monkeypatch, event_handler, profile_dialog_refs):
    """Two phases, and the second one is the one that counts.

    The offer only opens a screen on the phone -- deviceinv.offer_to_tasker is called
    with wait_for_confirmation=False precisely so the user is told that much straight away --
    and nothing goes into the loaded configuration until Tasker reports the Profile.
    """
    from maptasker.src import deviceinv

    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (0, "Profile 'Watched' is now in Tasker")])
    android_dialog, parent_dialog = MagicMock(), MagicMock()

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        android_dialog,
        parent_dialog,
    )

    pre_check, offer, confirm = calls["io_bound"]
    assert pre_check[0] is deviceinv.import_is_confirmable
    assert offer[0] is deviceinv.offer_to_tasker
    assert offer[2]["wait_for_confirmation"] is False
    # The "Open with..." route: Android's own chooser, which the user picks Tasker out of,
    # rather than this program guessing what a '.prf.xml' resolves to (2026-08-28 it guessed
    # wrong twice -- see import_profile_into_tasker_event).
    assert offer[2]["route"] is deviceinv.OPEN_FILE_ROUTE
    assert confirm[0] is deviceinv.await_import

    assert len(calls["kept"]) == 1  # the edit reached the loaded configuration
    android_dialog.close.assert_called_once()
    parent_dialog.close.assert_called_once()
    assert calls["notify"][-1] == ("Profile 'Watched' is now in Tasker", "positive")


@pytest.mark.asyncio
async def test_a_file_already_on_the_device_is_asked_about_first(monkeypatch, event_handler, profile_dialog_refs):
    """The import writes exactly where 'Save As File' writes now, so it can land on a
    Watched.prf.xml the user saved by hand -- and they are asked before it does, in the same
    words that button uses.

    Nothing goes over the wire until they answer: the pre-check, the offer and the
    confirmation all sit behind the prompt, so Cancel costs them nothing but the click.
    """
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open")], exists=True)
    android_dialog, parent_dialog = MagicMock(), MagicMock()

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        android_dialog,
        parent_dialog,
    )

    assert len(calls["overwrite"]) == 1
    what, _on_confirm, kwargs = calls["overwrite"][0]
    assert what == "'/Tasker/profiles/Watched.prf.xml' on the Android device"
    assert kwargs == {"unknown": False}
    # Cancelled, as far as this test is concerned -- nothing was sent and nothing was closed.
    assert calls["io_bound"] == []
    assert calls["backed_up"] == []
    android_dialog.close.assert_not_called()
    parent_dialog.close.assert_not_called()


@pytest.mark.asyncio
async def test_a_destination_that_cannot_be_checked_still_asks(monkeypatch, event_handler, profile_dialog_refs):
    """read_android_file's existence answer is tri-state and None is 'could not tell'.  The
    honest thing is still a prompt -- 'this might overwrite something' -- rather than a
    silent write on exactly the flaky-connection case a user most wants asking about."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open")], exists=None)

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert len(calls["overwrite"]) == 1
    assert calls["overwrite"][0][2] == {"unknown": True}


@pytest.mark.asyncio
async def test_confirming_the_overwrite_copies_the_file_it_replaces(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """Overwrite goes ahead with the import AND keeps what it replaced.  The device has no
    versions and no undo, so the copy this takes is the only one there will ever be -- and it
    is made from the bytes the existence check already returned, not a second GET."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(
        monkeypatch,
        [True, (0, "screen is open"), (0, "Profile 'Watched' is now in Tasker")],
        exists=True,
    )

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )
    _what, on_confirm, _kwargs = calls["overwrite"][0]
    on_confirm()
    await asyncio.sleep(0)  # the prompt's callback is sync; the offer it starts is not
    await asyncio.sleep(0)

    assert calls["backed_up"] == [("/Tasker/profiles/Watched.prf.xml", b"<TaskerData>the old one</TaskerData>")]
    assert [call[0] for call in calls["io_bound"]][1].__name__ == "offer_to_tasker"


@pytest.mark.asyncio
async def test_an_offer_run_from_the_prompt_still_has_somewhere_to_draw(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """The overwrite prompt's callback is synchronous and the offer is not, so the offer is
    started with create_task -- and nicegui's slot stack is keyed by asyncio task, so that
    new task starts with an empty one.  Every ui.notify and ui.notification in the offer
    builds an element, an element needs a slot, and all of them raised
    'the slot stack for this task is empty' the first time a user pressed Overwrite.

    The client is captured in the handler's own task and re-entered inside the spawned one.
    This asserts the consequence rather than the mechanism: every notification the offer
    makes happens with somewhere to draw.
    """
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(
        monkeypatch,
        [True, (0, "screen is open"), (0, "Profile 'Watched' is now in Tasker")],
        exists=True,
    )

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )
    before = len(calls["in_slot"])
    calls["overwrite"][0][1]()  # the user presses Overwrite
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    spawned = calls["in_slot"][before:]
    assert spawned, calls["notify"]  # the offer did notify, so there is something to check
    assert all(spawned), calls["notify"]


@pytest.mark.asyncio
async def test_the_user_is_told_which_file_is_waiting_on_the_device(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """A handoff Tasker does not complete leaves the user to import the file themselves out
    of Tasker's own browser -- which they can only do if they are told which file it is.

    It could not be said at all while every import staged one 'maptasker_import.prf.xml': the
    name said nothing about which Profile was in it.  Now it is the Profile's own name, so it
    goes in the notification and into await_import's giving-up message.
    """
    from maptasker.src import deviceinv

    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (8, "Tasker has not reported it")])

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    staged = "/storage/emulated/0/Tasker/profiles/Watched.prf.xml"
    assert staged == deviceinv.SEND_INTENT_ROUTE.staged_file_paths("Watched")[2]
    assert any(staged in message for message, _type in calls["notify"])

    _pre_check, _offer, confirm = calls["io_bound"]
    assert confirm[0] is deviceinv.await_import
    assert confirm[2]["staged_at"] == staged


@pytest.mark.asyncio
async def test_the_panel_goes_as_soon_as_the_device_answers(monkeypatch, event_handler, profile_dialog_refs):
    """Sending it is the dialog's whole job, and the device answering is the end of it.

    It used to stay up through the confirmation wait -- up to two minutes of dead panel over
    a phone nobody has picked up -- and stayed up for good when a successful import was not
    seen by the poll.  So both dialogs close on the OFFER, before anything is waited on.
    """
    field_refs, android_refs = profile_dialog_refs
    _patch_import_path(monkeypatch, [True, (0, "screen is open"), (8, "may have been declined")])
    android_dialog, parent_dialog = MagicMock(), MagicMock()

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        android_dialog,
        parent_dialog,
    )

    android_dialog.close.assert_called_once()
    parent_dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_a_confirmation_that_never_comes_does_not_discard_the_edit(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """With the dialogs already closed there is no retry surface left, so throwing the edit
    away because a poll timed out would be silent data loss -- and a poll times out for
    reasons that say nothing about the edit, a phone still in a pocket most of all.  The
    warning reports on the DEVICE; the edit stays."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (8, "may have been declined")])

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert len(calls["kept"]) == 1
    assert ("may have been declined", "warning") in calls["notify"]


@pytest.mark.asyncio
async def test_an_unconfirmable_import_is_never_waited_on(monkeypatch, event_handler, profile_dialog_refs):
    """Tasker offers to REPLACE one it already has, and a replacement leaves the name, the
    count and the enabled state exactly as they were -- so 'does Tasker report this Profile'
    answers yes before the user touches anything.  Waiting on it would confirm the import the
    instant it was asked, Cancel included, so it must not be asked at all."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [False, (0, "screen is open")])
    android_dialog, parent_dialog = MagicMock(), MagicMock()

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        android_dialog,
        parent_dialog,
    )

    assert len(calls["io_bound"]) == 2  # pre-check and offer; no confirmation wait
    # The user's own edit is not thrown away over an answer that is never coming.
    assert len(calls["kept"]) == 1
    message, kind = calls["notify"][-1]
    assert kind == "info"
    assert "will offer to replace" in message
    android_dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_an_unreachable_pre_check_is_not_read_as_absent(monkeypatch, event_handler, profile_dialog_refs):
    """None means 'could not ask', and guessing 'absent' would send this down the path that
    treats a name appearing afterwards as proof -- turning an unconfirmable import into a
    reported success."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [None, (0, "screen is open")])

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert len(calls["io_bound"]) == 2  # no confirmation wait
    assert not any(kind == "positive" for _message, kind in calls["notify"])


@pytest.mark.asyncio
async def test_a_failed_offer_never_reaches_the_confirmation(monkeypatch, event_handler, profile_dialog_refs):
    """No screen was opened, so there is nothing to wait for.  Polling anyway would spend
    two minutes to report a failure that was already known."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (8, "Tasker could not open the file")])

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert len(calls["io_bound"]) == 2
    assert calls["kept"] == []
    assert any(kind == "negative" for _message, kind in calls["notify"])


@pytest.mark.asyncio
async def test_the_waiting_message_is_taken_down_by_the_outcome(monkeypatch, event_handler, profile_dialog_refs):
    """'Tap Import on the device' has no timeout, because there is no telling how long
    someone takes to reach their phone.  A message with no timeout and nothing to dismiss it
    is a box that sits on screen for the rest of the session -- so the outcome replaces it
    rather than stacking on top of it."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (0, "Profile 'Watched' is now in Tasker")])

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert len(calls["pending"]) == 1
    assert calls["pending"][0].dismissed is True
    assert calls["notify"][-1] == ("Profile 'Watched' is now in Tasker", "positive")


@pytest.mark.asyncio
async def test_the_replace_message_stays_because_nothing_follows_it(monkeypatch, event_handler, profile_dialog_refs):
    """The already-there case has no outcome coming that could replace it, and it asks the
    user to go and do something.  So it stays, and its close button is how it goes."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [False, (0, "screen is open")])

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert len(calls["pending"]) == 1
    assert calls["pending"][0].dismissed is False


# ==========================================
# The same, for a Project
#
# A Project goes down the identical path -- _offer_into_tasker is one implementation for
# both buttons -- so what is worth asserting here is only where the two genuinely differ:
# the route (which decides the staged file's extension, and so what Tasker thinks it is
# looking at), what confirms it, and the fact that a Project has no edit to keep.
# ==========================================


@pytest.mark.asyncio
async def test_a_project_is_offered_as_a_project(monkeypatch, event_handler, profile_dialog_refs):
    """The route is the whole difference at the device end: it stages the XML as
    '.prj.xml' rather than '.prf.xml', and the extension is what tells Tasker whether it is
    importing a Project or a Profile."""
    from maptasker.src import deviceinv

    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (0, "Project 'Home' is now in Tasker")])
    edited_project = MagicMock()
    edited_project.project_name = "Home"

    await event_handler.import_project_into_tasker_event(
        edited_project,
        {},
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    _pre_check, offer, _confirm = calls["io_bound"]
    assert offer[2]["route"] is deviceinv.OPEN_PROJECT_ROUTE  # explicit -- see the Profile's note
    assert offer[1][1] == "Home"


@pytest.mark.asyncio
async def test_a_project_is_confirmed_through_the_profiles_it_owns(monkeypatch, event_handler, profile_dialog_refs):
    """There is no /api/projects to ask about the Project itself, so the names that go to
    the device are the Profiles it brings with it -- see projedit.project_profile_names."""
    from maptasker.src import deviceinv

    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (0, "Project 'Home' is now in Tasker")])
    edited_project = MagicMock()
    edited_project.project_name = "Home"

    await event_handler.import_project_into_tasker_event(
        edited_project,
        {},
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    pre_check, offer, confirm = calls["io_bound"]
    assert pre_check[0] is deviceinv.import_is_confirmable
    assert pre_check[1][2] == ["Watched", "Also Watched"]
    assert offer[1][2] == ["Watched", "Also Watched"]
    assert confirm[1][2] == ["Watched", "Also Watched"]


@pytest.mark.asyncio
async def test_a_project_has_no_edit_to_keep(monkeypatch, event_handler, profile_dialog_refs):
    """Unlike a Profile, a Project is exported from the LIVE TREE by name -- there is no
    separate edited model, so there is nothing to register into the loaded configuration
    afterwards."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (0, "Project 'Home' is now in Tasker")])
    edited_project = MagicMock()
    edited_project.project_name = "Home"

    await event_handler.import_project_into_tasker_event(
        edited_project,
        {},
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert calls["kept"] == []


@pytest.mark.asyncio
async def test_unapplied_project_edits_stop_it_before_the_device(monkeypatch, event_handler, profile_dialog_refs):
    """Same guard save_project_to_android_event has, for the same reason: this exports the
    Project from the live tree by name, so a dialog field that was never applied would be
    dropped silently from what reaches the phone.  It has to fail before anything is sent."""
    from maptasker.src import userintr

    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open")])
    monkeypatch.setattr(userintr, "_unapplied_project_edits", lambda _refs: ["Colour was never applied."])
    edited_project = MagicMock()
    edited_project.project_name = "Home"

    await event_handler.import_project_into_tasker_event(
        edited_project,
        {},
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert calls["io_bound"] == []
    assert ("Colour was never applied.", "negative") in calls["notify"]


# ==========================================
# ...and for a Scene, which is offered the same way now
#
# A Scene used not to be offered at all.  Both measured handoffs failed -- an implicit VIEW
# for 'text/xml' put up a chooser with no Tasker in it, and an explicit intent made Tasker
# open, attempt visibly, and import nothing -- so the flow uploaded the file, opened Tasker,
# and left the whole import to the user.
#
# The "Open with..." is a third attempt rather than a repeat of either: an implicit VIEW
# carrying NO type, which is the only one of the three an extension filter can match (see
# deviceinv._OPEN_WITH_MIME_TYPE).  So a Scene goes through _offer_into_tasker like the other
# two, and everything that path already does -- the overwrite prompt, the safety copy,
# staging under its own name -- it now gets for free.  The by-hand instruction stays in the
# message, because that instruction is what this route used to be.
#
# The three io_bound calls, in order: the confirmable pre-check, the offer, and the
# confirmation wait.
# ==========================================


_SCENE_RESULTS = [
    True,
    (0, "screen is open"),
    (0, "Scene 'Dialog' is now in Tasker"),
]


async def _import_scene(event_handler, android_refs, scene_name: str = "Dialog") -> None:
    edited_scene = MagicMock()
    edited_scene.scene_name = scene_name
    await event_handler.import_scene_into_tasker_event(
        edited_scene,
        {},
        android_refs,
        MagicMock(),
        MagicMock(),
    )


@pytest.mark.asyncio
async def test_a_scene_already_on_the_device_is_asked_about_first(monkeypatch, event_handler, profile_dialog_refs):
    """This route always wrote the Scene under its own name into Tasker's own folder, so it
    always could land on a Dialog.scn.xml the user saved by hand -- it just never asked.  Now
    it asks the same question 'Save As File' asks, and keeps a copy when they say yes."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, _SCENE_RESULTS, exists=True)

    await _import_scene(event_handler, android_refs)

    assert len(calls["overwrite"]) == 1
    what, on_confirm, kwargs = calls["overwrite"][0]
    assert what == "'/Tasker/scenes/Dialog.scn.xml' on the Android device"
    assert kwargs == {"unknown": False}
    assert calls["io_bound"] == []  # nothing sent while the question is unanswered

    on_confirm()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert calls["backed_up"] == [("/Tasker/scenes/Dialog.scn.xml", b"<TaskerData>the old one</TaskerData>")]


@pytest.mark.asyncio
async def test_a_scene_is_sent_under_its_own_name(monkeypatch, event_handler, profile_dialog_refs):
    """The name is not cosmetic here.  If Tasker is not in the chooser the user finishes this
    by picking the file out of a list on their phone, so it has to be called what they are
    looking for.  This route got there first; the Profile and Project routes have since
    stopped staging one fixed 'maptasker_import' file too, and all three now stage through
    the same offer to the same path 'Save As File' writes."""
    from maptasker.src import deviceinv, sceneedit

    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, _SCENE_RESULTS)

    await _import_scene(event_handler, android_refs)

    _pre_check, offer, _confirm = calls["io_bound"]
    assert offer[0] is deviceinv.offer_to_tasker
    assert offer[1][1] == "Dialog"  # the object name the staged file is named after
    assert deviceinv.OPEN_SCENE_ROUTE.staged_file_paths("Dialog")[1] == sceneedit.android_scene_path("Dialog")


@pytest.mark.asyncio
async def test_a_scene_is_confirmed_at_the_scenes_endpoint(monkeypatch, event_handler, profile_dialog_refs):
    """Unlike a Project, a Scene has an endpoint of its own -- Tasker's API reports Scenes by
    name -- so once the user has done the import by hand, it can still be confirmed."""
    from maptasker.src import deviceinv

    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, _SCENE_RESULTS)

    await _import_scene(event_handler, android_refs)

    pre_check, offer, confirm = calls["io_bound"]
    assert pre_check[0] is deviceinv.import_is_confirmable
    assert pre_check[1][3] == deviceinv.SCENES_ENDPOINT
    assert offer[2]["route"] is deviceinv.OPEN_SCENE_ROUTE
    assert confirm[1][2] == ["Dialog"]
    assert confirm[1][4] == deviceinv.SCENES_ENDPOINT
    # Five minutes, not the two an import screen gets: this user may be working a file
    # picker, and a timeout would tell them an import they are in the middle of did not
    # happen.
    assert confirm[2]["attempts"] == deviceinv.MANUAL_IMPORT_POLL_ATTEMPTS
    assert deviceinv.MANUAL_IMPORT_POLL_ATTEMPTS > 60


@pytest.mark.asyncio
async def test_the_scene_notification_names_the_file_and_the_menu(monkeypatch, event_handler, profile_dialog_refs):
    """The whole delivery, for the user, is this message: the file is on their phone and the
    last step is theirs.  A message that says 'import it' without saying which file, or
    where from, leaves them exactly where they started."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, _SCENE_RESULTS)

    await _import_scene(event_handler, android_refs)

    pending = [message for message, _type in calls["notify"] if "Import One Scene" in message]
    assert pending, calls["notify"]
    assert "/storage/emulated/0/Tasker/scenes/Dialog.scn.xml" in pending[0]
    assert "'Dialog'" in pending[0]
    assert "if Tasker is not in the chooser" in pending[0]


@pytest.mark.asyncio
async def test_a_scene_that_could_not_be_sent_does_not_send_anyone_to_their_phone(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """The upload verifies itself by reading the bytes back, and if that fails there is
    nothing on the device to import.  Sending the user to their phone then would be sending
    them to do something impossible, and the message has to be the failure, not the
    instructions."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (8, "could not confirm it landed correctly")])

    await _import_scene(event_handler, android_refs)

    assert len(calls["io_bound"]) == 2  # the pre-check and the offer, and nothing after it
    assert any("could not confirm it landed correctly" in message for message, _type in calls["notify"])
    assert not any("Import One Scene" in message for message, _type in calls["notify"])


@pytest.mark.asyncio
async def test_a_scene_the_chooser_could_not_place_still_says_what_to_do(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """The chooser may still not have Tasker in it -- that is measured for a '.scn.xml' with
    a mime type, and only reasoned to be different without one.  So the delivery does not
    depend on it: the file is on the device under its own name, and the message says which
    file and which menu, exactly as it did when opening Tasker was all this route could do."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(
        monkeypatch,
        [True, (0, "screen is open"), (8, "Tasker has not reported Scene 'Dialog'")],
    )

    await _import_scene(event_handler, android_refs)

    pending = [message for message, _type in calls["notify"] if "Import One Scene" in message]
    assert pending, calls["notify"]
    assert "/storage/emulated/0/Tasker/scenes/Dialog.scn.xml" in pending[0]
    # ...and the giving-up message is reported as a warning, not swallowed.
    assert ("Tasker has not reported Scene 'Dialog'", "warning") in calls["notify"]


@pytest.mark.asyncio
async def test_the_scene_edits_are_applied_before_the_export(monkeypatch, event_handler, profile_dialog_refs):
    """Load-bearing, and silent when missed: the export renders the Scene from the LIVE TREE
    by name, while the dialog edits a deep copy whose V2 layout nothing writes back until a
    save handler runs.  Without the apply, an element added a moment ago is simply absent
    from the file that reaches the phone."""
    from maptasker.src import userintr

    applied = []
    _field_refs, android_refs = profile_dialog_refs
    _patch_import_path(monkeypatch, _SCENE_RESULTS)
    monkeypatch.setattr(
        userintr.sceneedit,
        "apply_edited_scene_to_live_tree",
        lambda name, _scene: applied.append(name),
    )

    await _import_scene(event_handler, android_refs)

    assert applied == ["Dialog"]


@pytest.mark.asyncio
async def test_a_scene_that_fails_validation_never_reaches_the_device(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """Applying first is also what makes a bad field stop this before anything is sent,
    rather than after -- same order save_scene_to_android_event uses."""
    from maptasker.src import userintr

    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open")])
    monkeypatch.setattr(userintr, "_apply_scene_field_values", lambda _s, _refs: ["Width must be a number."])
    edited_scene = MagicMock()
    edited_scene.scene_name = "Dialog"

    await event_handler.import_scene_into_tasker_event(
        edited_scene,
        {},
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert calls["io_bound"] == []
    assert ("Width must be a number.", "negative") in calls["notify"]


# ==========================================
# Reporting the outcome cannot be what kills the session
#
# The confirmation wait is up to two minutes long, and the status notification it puts up
# carries a close button.  So by the time there is something to report, that element may be
# gone -- dismissed by the user, or taken with a client that reloaded -- and nicegui treats
# being driven after deletion as a bug in the application code.  Observed on a real run: the
# warning it logs was the first write to a stderr another thread had already closed (see
# maputil2.suppress_stdout), and the whole application went down with it.
# ==========================================


@pytest.mark.asyncio
async def test_a_notification_the_user_already_closed_does_not_take_the_app_down(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
):
    """The import still gets reported, and nothing propagates out of the handler."""
    from maptasker.src import userintr

    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, _SCENE_RESULTS)

    class _DeletedNotification:
        """nicegui's behaviour for an element that no longer exists."""

        def __init__(self, message, **kwargs) -> None:
            calls["notify"].append((message, kwargs.get("type")))

        def dismiss(self) -> None:
            raise ValueError("I/O operation on closed file.")

    monkeypatch.setattr(userintr.ui, "notification", _DeletedNotification)

    await _import_scene(event_handler, android_refs)

    # Got past the dismiss, and still said what happened.
    assert ("Scene 'Dialog' is now in Tasker", "positive") in calls["notify"]


@pytest.mark.asyncio
async def test_a_profile_notification_carries_no_such_advice(monkeypatch, event_handler, profile_dialog_refs):
    """A Profile reaches Tasker's import screen on its own, so there is nothing to finish by
    hand and nothing to say about it -- the hint is the Scene's, not everyone's."""
    field_refs, android_refs = profile_dialog_refs
    calls = _patch_import_path(monkeypatch, [True, (0, "screen is open"), (1, "not seen")])

    await event_handler.import_profile_into_tasker_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    pending = [message for message, _type in calls["notify"] if "import screen is open" in message]
    assert pending, calls["notify"]
    assert "Scenes tab" not in pending[0]


# ==========================================
# 'Save As File' for a Task
#
# The Save Task To Android dialog used to have one button, and it imported.  It now has the
# Profile dialog's pair, and the file half is what these cover: the same overwrite prompt,
# the same safety copy, the same read-back-verified upload -- and the same registration into
# the loaded configuration, which is the part that has nothing to do with the device and
# must not differ between the two buttons.
# ==========================================


@pytest.fixture
def task_dialog_refs():
    """The two field_refs dicts the Task handlers are given."""
    return (
        {"name": _FakeField("Opener"), "priority": _FakeField("100")},
        {"ip_address": _FakeField("192.168.0.210"), "ip_port": _FakeField("1821")},
    )


def _patch_task_file_path(monkeypatch, exists=False, upload=(0, "/Tasker/tasks/Opener.tsk.xml")) -> dict:
    """Point the file-write handler's collaborators at fakes and record what it did."""
    from maptasker.src import userintr

    calls: dict = {"notify": [], "uploaded": [], "overwrite": [], "backed_up": [], "kept": []}

    async def fake_ping(_self, _ip, _port) -> bool:
        return True

    monkeypatch.setattr(userintr, "ping_android_device", fake_ping)
    monkeypatch.setattr(userintr.taskedit, "apply_edits_to_task", lambda *_args: [])
    monkeypatch.setattr(userintr.taskedit, "task_name_exists", lambda _name: False)
    monkeypatch.setattr(userintr, "_task_arg_values", lambda _refs: {})
    monkeypatch.setattr(userintr, "refresh_tasker_object_pulldowns", lambda _gui: None)
    # Both halves of _keep_task_in_loaded_config: which one runs depends on whether the Task
    # is already registered, and the handler must do exactly one of them.
    monkeypatch.setattr(
        userintr.taskedit,
        "apply_edited_task_to_live_tree",
        lambda _task: calls["kept"].append("existing"),
    )
    monkeypatch.setattr(
        userintr.taskedit,
        "register_new_task",
        lambda _task, name: calls["kept"].append(f"new:{name}"),
    )
    # One read of the path now answers both questions -- see maputil2.read_android_file.
    # The content it hands back is what becomes the safety copy, with no second GET.
    monkeypatch.setattr(
        userintr,
        "read_android_file",
        lambda _ip, _port, _path: (exists, b"<TaskerData>the old one</TaskerData>" if exists else b""),
    )
    monkeypatch.setattr(
        userintr.presave,
        "save_android_safety_copy",
        lambda path, content: (calls["backed_up"].append((path, content)), (True, "/copies/Opener.tsk.xml"))[1],
    )

    def fake_upload(_task, _ip, _port, name):
        calls["uploaded"].append(name)
        return upload

    monkeypatch.setattr(userintr.taskedit, "save_task_to_android_file", fake_upload)
    monkeypatch.setattr(
        userintr,
        "build_overwrite_confirm_dialog",
        lambda what, on_confirm, **kwargs: calls["overwrite"].append((what, on_confirm, kwargs)),
    )
    monkeypatch.setattr(
        userintr.ui,
        "notify",
        lambda message, **kwargs: calls["notify"].append((message, kwargs.get("type"))),
    )
    return calls


async def _save_task_file(event_handler, task_dialog_refs) -> tuple:
    field_refs, android_refs = task_dialog_refs
    android_dialog, parent_dialog = MagicMock(), MagicMock()
    await event_handler.save_task_to_android_file_event(
        MagicMock(),
        field_refs,
        android_refs,
        android_dialog,
        parent_dialog,
    )
    return android_dialog, parent_dialog


@pytest.mark.asyncio
async def test_a_task_file_write_reports_where_it_landed(monkeypatch, event_handler, task_dialog_refs):
    """The path is the whole point of the message: nothing about this reaches Tasker, so
    what the user gets is a file, and they have to be told which one and where."""
    calls = _patch_task_file_path(monkeypatch)

    android_dialog, parent_dialog = await _save_task_file(event_handler, task_dialog_refs)

    assert calls["uploaded"] == ["Opener"]
    saved = [message for message, kind in calls["notify"] if kind == "positive"]
    assert saved and "/Tasker/tasks/Opener.tsk.xml" in saved[0]
    assert "/copies/Opener.tsk.xml" in saved[0]  # and what it replaced went somewhere
    android_dialog.close.assert_called_once()
    parent_dialog.close.assert_called_once()


@pytest.mark.asyncio
async def test_a_save_to_android_tells_the_user_to_watch_the_device(monkeypatch, event_handler, task_dialog_refs):
    """Tasker's HTTP server prompts on the phone per request rather than once per client,
    so one save puts several authorization prompts up -- and an unanswered one times out
    into a failure that reads like an unreachable device.  The warning has to come out
    before the requests do, not with the result, or the user reads it after the prompts
    have already gone."""
    calls = _patch_task_file_path(monkeypatch)

    await _save_task_file(event_handler, task_dialog_refs)

    warned = [
        index
        for index, (message, kind) in enumerate(calls["notify"])
        if kind == "warning" and "Watch your Android device" in message
    ]
    assert warned, calls["notify"]
    done = [index for index, (_message, kind) in enumerate(calls["notify"]) if kind == "positive"]
    assert warned[0] < done[0]


def test_every_save_to_android_path_warns_about_the_device_prompts() -> None:
    """The warning belongs to all eight buttons, not the one above -- and the way it stops
    being on all eight is a ninth handler written by copying one of them.  Reading the
    handlers themselves is what catches that; a behavioural test per handler would need
    each one's whole fixture and would still only cover the eight that exist today."""
    import ast
    import inspect

    from maptasker.src import userintr

    handlers = {
        "save_task_to_android_event",
        "save_task_to_android_file_event",
        "save_profile_to_android_event",
        "import_profile_into_tasker_event",
        "save_project_to_android_event",
        "import_project_into_tasker_event",
        "save_scene_to_android_event",
        "import_scene_into_tasker_event",
    }
    tree = ast.parse(inspect.getsource(userintr))
    warns = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name in handlers
        and any(
            isinstance(call.func, ast.Name) and call.func.id == "notify_watch_android_device"
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
        )
    }
    assert warns == handlers, f"no device warning in: {sorted(handlers - warns)}"


@pytest.mark.asyncio
async def test_a_task_file_is_not_clobbered_without_asking(monkeypatch, event_handler, task_dialog_refs):
    """/upload overwrites silently and answers 200 either way, so the check has to happen
    here.  Nothing is uploaded until the prompt is answered -- the same guard the Profile and
    Project writes have."""
    calls = _patch_task_file_path(monkeypatch, exists=True)

    await _save_task_file(event_handler, task_dialog_refs)

    assert calls["uploaded"] == []
    assert calls["overwrite"], "no overwrite prompt"
    what, on_confirm, kwargs = calls["overwrite"][0]
    assert "/Tasker/tasks/Opener.tsk.xml" in what
    assert kwargs["unknown"] is False

    on_confirm()  # the user chooses Overwrite

    assert calls["uploaded"] == ["Opener"]
    assert calls["backed_up"] == [("/Tasker/tasks/Opener.tsk.xml", b"<TaskerData>the old one</TaskerData>")]


@pytest.mark.asyncio
async def test_a_task_file_asks_even_when_the_device_cannot_be_read(monkeypatch, event_handler, task_dialog_refs):
    """read_android_file's existence answer is tri-state, and None is 'could not tell'.  Treated as False
    it would skip the prompt on exactly the flaky connection where a user most wants it."""
    calls = _patch_task_file_path(monkeypatch, exists=None)

    await _save_task_file(event_handler, task_dialog_refs)

    assert calls["uploaded"] == []
    assert calls["overwrite"][0][2]["unknown"] is True


@pytest.mark.asyncio
async def test_a_failed_task_file_write_keeps_the_dialog_open(monkeypatch, event_handler, task_dialog_refs):
    """The connection details the user typed are in that dialog.  Closing it on a failure
    makes them type the address again to retry -- and the retry is the likely next move."""
    calls = _patch_task_file_path(monkeypatch, upload=(8, "could not confirm it landed correctly"))

    android_dialog, parent_dialog = await _save_task_file(event_handler, task_dialog_refs)

    assert any(kind == "negative" for _message, kind in calls["notify"])
    android_dialog.close.assert_not_called()
    parent_dialog.close.assert_not_called()
    assert calls["kept"] == []  # and nothing was claimed for the loaded configuration


@pytest.mark.asyncio
async def test_a_saved_task_reaches_the_loaded_configuration(monkeypatch, event_handler, task_dialog_refs):
    """The half that is not about the device at all.  Both buttons end here -- a Task
    registered by one and not the other would show up in the Edit Task picker only
    sometimes."""
    calls = _patch_task_file_path(monkeypatch)

    await _save_task_file(event_handler, task_dialog_refs)

    # A MagicMock Task carries an id the live tree has never heard of, so this is the
    # brand-new path -- registered under the name from the dialog, once.
    assert calls["kept"] == ["new:Opener"]


@pytest.mark.asyncio
async def test_the_task_import_asks_before_replacing_the_file_it_writes(
    monkeypatch,
    event_handler,
    task_dialog_refs,
):
    """The import writes /Tasker/tasks/<name>.tsk.xml and imports that, so it clobbers the
    same path 'Save As File' does -- and has to ask the same question, in the same words,
    whichever button the user pressed."""
    from maptasker.src import userintr

    calls = _patch_task_file_path(monkeypatch, exists=True)
    imported = []
    monkeypatch.setattr(
        userintr.taskedit,
        "save_task_to_android",
        lambda *args, **_kwargs: (imported.append(args[3]), (0, args[3], "KEY"))[1],
    )
    monkeypatch.setattr(userintr.taskedit, "verify_task_on_android", lambda *_args: True)
    field_refs, android_refs = task_dialog_refs

    await event_handler.save_task_to_android_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert imported == []  # nothing imported while the prompt is up
    what, on_confirm, kwargs = calls["overwrite"][0]
    assert "/Tasker/tasks/Opener.tsk.xml" in what
    assert kwargs["unknown"] is False

    on_confirm()  # the user chooses Overwrite

    assert imported == ["Opener"]
    # and the old file was copied first, from the bytes the existence check already had
    assert calls["backed_up"] == [("/Tasker/tasks/Opener.tsk.xml", b"<TaskerData>the old one</TaskerData>")]


@pytest.mark.asyncio
async def test_a_task_tasker_never_confirms_falls_back_to_the_open_with(
    monkeypatch,
    event_handler,
    task_dialog_refs,
):
    """api/import needs no tap and usually works, so it stays the route.  When it has been
    tried twice and Tasker still does not report the Task, the .tsk.xml is in /Tasker/tasks
    regardless -- written and read back before either attempt -- so the user gets the same
    "Open with..." chooser the other three kinds get instead of only bad news."""
    from maptasker.src import deviceinv, userintr

    calls = _patch_task_file_path(monkeypatch)
    monkeypatch.setattr(userintr.taskedit, "save_task_to_android", lambda *args, **_kwargs: (0, args[3], "KEY"))
    monkeypatch.setattr(userintr.taskedit, "verify_task_on_android", lambda *_args: False)
    monkeypatch.setattr(
        userintr.taskedit,
        "save_task_to_android_directory",
        lambda *_args, **_kwargs: (8, "Tasker did not report the Task"),
    )
    monkeypatch.setattr(userintr.taskedit, "render_standalone_task_xml", lambda _task: "<TaskerData/>")
    offered: list = []
    monkeypatch.setattr(
        userintr.deviceinv,
        "offer_to_tasker",
        lambda *args, **kwargs: (offered.append((args, kwargs)), (0, "screen is open"))[1],
    )
    field_refs, android_refs = task_dialog_refs

    await event_handler.save_task_to_android_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    assert len(offered) == 1
    args, kwargs = offered[0]
    assert args[1] == "Opener"  # staged as Opener.tsk.xml, its own name
    assert kwargs["route"] is deviceinv.OPEN_TASK_ROUTE
    # Any warning, not the first: every Save To Android / Import Into Tasker path now
    # opens with the "watch your device" heads-up (guiutils.notify_watch_android_device).
    handed = [message for message, kind in calls["notify"] if kind == "warning"]
    assert handed, calls["notify"]
    assert any("Open with" in message for message in handed), handed


@pytest.mark.asyncio
async def test_the_task_import_says_where_the_copy_was_left(monkeypatch, event_handler, task_dialog_refs):
    """The copy is the point of the change and the user has no other way to learn it is
    there -- an import that silently leaves a file behind is a file nobody knows to look
    for."""
    from maptasker.src import userintr

    calls = _patch_task_file_path(monkeypatch)
    monkeypatch.setattr(userintr.taskedit, "save_task_to_android", lambda *args, **_kwargs: (0, args[3], "KEY"))
    monkeypatch.setattr(userintr.taskedit, "verify_task_on_android", lambda *_args: True)
    field_refs, android_refs = task_dialog_refs

    await event_handler.save_task_to_android_event(
        MagicMock(),
        field_refs,
        android_refs,
        MagicMock(),
        MagicMock(),
    )

    saved = [message for message, kind in calls["notify"] if kind == "positive"]
    assert saved, calls["notify"]
    assert "/Tasker/tasks/Opener.tsk.xml" in saved[0]
    assert "/copies/Opener.tsk.xml" in saved[0]


# ==========================================
# ...and the same for a Profile, a Project and a Scene
#
# All four Save To Android file writes now read the destination ONCE: the answer says whether
# anything is there to clobber, and the same response carries what to keep as the safety
# copy.  Two reads meant two round trips, two chances to disagree about what was there, and
# two 'File doesn't exist' flashes on the phone for a single first-time save -- the Tasker
# HTTP Server Example's /file handler runs Test File and flashes on every miss.
#
# These three handlers had no coverage at all before, so what is pinned here is the whole
# shape: probe once, prompt before clobbering, copy what was there, then write.
# ==========================================


def _patch_object_save_path(monkeypatch, kind: str, exists=False, upload=(0, "/Tasker/x")) -> dict:
    """Fakes for one of the three non-Task Save To Android handlers."""
    from maptasker.src import userintr

    calls: dict = {"notify": [], "uploaded": [], "overwrite": [], "backed_up": []}

    async def fake_ping(_self, _ip, _port) -> bool:
        return True

    monkeypatch.setattr(userintr, "ping_android_device", fake_ping)
    monkeypatch.setattr(
        userintr,
        "read_android_file",
        lambda _ip, _port, _path: (exists, b"<TaskerData>the old one</TaskerData>" if exists else b""),
    )
    monkeypatch.setattr(
        userintr.presave,
        "save_android_safety_copy",
        lambda path, content: (calls["backed_up"].append((path, content)), (True, "/copies/old"))[1],
    )
    monkeypatch.setattr(
        userintr,
        "build_overwrite_confirm_dialog",
        lambda what, on_confirm, **kwargs: calls["overwrite"].append((what, on_confirm, kwargs)),
    )
    monkeypatch.setattr(
        userintr.ui,
        "notify",
        lambda message, **kwargs: calls["notify"].append((message, kwargs.get("type"))),
    )

    def record(*args: object) -> tuple:
        calls["uploaded"].append(args)
        return upload

    if kind == "profile":
        monkeypatch.setattr(
            userintr.MapTaskerEventHandlers,
            "_apply_profile_for_android",
            lambda _self, _profile, _refs: (True, False, ""),
        )
        # What the Profile does with the loaded configuration afterwards is its own business
        # and its own tests -- this is about the one read of the device path.
        monkeypatch.setattr(
            userintr.MapTaskerEventHandlers,
            "_keep_profile_in_loaded_config",
            lambda _self, *_args: None,
        )
        monkeypatch.setattr(userintr.profedit, "android_profile_path", lambda name: f"/Tasker/profiles/{name}.prf.xml")
        monkeypatch.setattr(userintr.profedit, "save_profile_to_android", record)
    elif kind == "project":
        monkeypatch.setattr(userintr, "_unapplied_project_edits", lambda _refs: [])
        monkeypatch.setattr(userintr.projedit, "android_project_path", lambda name: f"/Tasker/projects/{name}.prj.xml")
        monkeypatch.setattr(userintr.projedit, "save_project_to_android", record)
    else:
        monkeypatch.setattr(userintr, "_apply_scene_field_values", lambda _s, _refs: [])
        monkeypatch.setattr(userintr.sceneedit, "apply_edited_scene_to_live_tree", lambda _n, _s: None)
        monkeypatch.setattr(userintr.sceneedit, "android_scene_path", lambda name: f"/Tasker/scenes/{name}.scn.xml")
        monkeypatch.setattr(userintr.sceneedit, "save_scene_to_android", record)
    return calls


async def _save_object(event_handler, kind: str, android_refs) -> None:
    edited = MagicMock()
    edited.project_name = "Home"
    edited.scene_name = "Dialog"
    handler = {
        "profile": event_handler.save_profile_to_android_event,
        "project": event_handler.save_project_to_android_event,
        "scene": event_handler.save_scene_to_android_event,
    }[kind]
    await handler(edited, {"name": _FakeField("Watched")}, android_refs, MagicMock(), MagicMock())


@pytest.mark.parametrize(
    ("kind", "device_path"),
    [
        ("profile", "/Tasker/profiles/Watched.prf.xml"),
        ("project", "/Tasker/projects/Home.prj.xml"),
        ("scene", "/Tasker/scenes/Dialog.scn.xml"),
    ],
)
@pytest.mark.asyncio
async def test_each_kind_reads_its_destination_once_and_keeps_what_was_there(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
    kind,
    device_path,
):
    """The prompt and the safety copy come from the same single read: the copy is made of the
    bytes that read returned, so nothing goes back to the device to ask again."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_object_save_path(monkeypatch, kind, exists=True, upload=(0, device_path))

    await _save_object(event_handler, kind, android_refs)

    assert calls["uploaded"] == []  # nothing written while the prompt is up
    what, on_confirm, kwargs = calls["overwrite"][0]
    assert device_path in what
    assert kwargs["unknown"] is False

    on_confirm()  # the user chooses Overwrite

    assert calls["uploaded"], "the confirmed write never happened"
    assert calls["backed_up"] == [(device_path, b"<TaskerData>the old one</TaskerData>")]


@pytest.mark.parametrize("kind", ["profile", "project", "scene"])
@pytest.mark.asyncio
async def test_each_kind_writes_straight_through_when_nothing_is_there(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
    kind,
):
    """A first-time save asks nothing and copies nothing -- there is nothing to ask about and
    nothing to keep.  The read that established that is the only one made."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_object_save_path(monkeypatch, kind, exists=False)

    await _save_object(event_handler, kind, android_refs)

    assert calls["overwrite"] == []
    # The safety copy is handed nothing, and nothing is what it keeps (see
    # presave.save_android_safety_copy, which returns (True, "") for empty content).
    assert [content for _path, content in calls["backed_up"]] == [b""]
    assert calls["uploaded"], "the write never happened"


@pytest.mark.parametrize("kind", ["profile", "project", "scene"])
@pytest.mark.asyncio
async def test_each_kind_still_asks_when_the_device_cannot_be_read(
    monkeypatch,
    event_handler,
    profile_dialog_refs,
    kind,
):
    """None is 'could not tell', and treating it as False would skip the prompt on exactly
    the flaky connection where a user most wants it."""
    _field_refs, android_refs = profile_dialog_refs
    calls = _patch_object_save_path(monkeypatch, kind, exists=None)

    await _save_object(event_handler, kind, android_refs)

    assert calls["uploaded"] == []
    assert calls["overwrite"][0][2]["unknown"] is True


# ==========================================
# Listing the helper Tasks this program has left on the device
#
# A report, not a cleanup: Tasker's HTTP API has no route for deleting a Task, so the whole
# feature is naming the dead ones accurately enough that the user can delete them by hand
# without having to wonder which 'MapTasker ...' is still in use.
# ==========================================


def _patch_helper_task_listing(monkeypatch, result) -> dict:
    """Point the handler at fakes and record the dialog it opens."""
    from maptasker.src import userintr

    calls: dict = {"io_bound": [], "notify": [], "dialog": []}

    async def fake_io_bound(func, *args, **kwargs):
        calls["io_bound"].append((func, args, kwargs))
        return result

    async def fake_ping(_self, _ip, _port) -> bool:
        return True

    monkeypatch.setattr(userintr.run, "io_bound", fake_io_bound)
    monkeypatch.setattr(userintr, "ping_android_device", fake_ping)
    monkeypatch.setattr(
        userintr,
        "build_helper_tasks_dialog",
        lambda stale, current, device: calls["dialog"].append((stale, current, device)),
    )
    monkeypatch.setattr(
        userintr.ui,
        "notify",
        lambda message, **kwargs: calls["notify"].append((message, kwargs.get("type"))),
    )
    return calls


def _android_panel(event_handler, ip="192.168.0.210", port="1821") -> None:
    """The Get XML panel's own fields, which are where this reads the device from."""
    event_handler.gui.ip_entry = _FakeField(ip)
    event_handler.gui.port_entry = _FakeField(port)


@pytest.mark.asyncio
async def test_the_helper_task_listing_reports_what_the_device_has(monkeypatch, event_handler):
    """The two lists together are the whole answer: what to delete, and what to leave."""
    from maptasker.src import deviceinv

    calls = _patch_helper_task_listing(
        monkeypatch,
        (0, "", ["MapTasker Open Profile v1"], ["MapTasker Open Profile v4"]),
    )
    _android_panel(event_handler)

    await event_handler.list_helper_tasks_event()

    assert calls["io_bound"][0][0] is deviceinv.stale_helper_tasks_on_device
    assert calls["io_bound"][0][1] == ("192.168.0.210", "1821")
    assert calls["dialog"] == [(["MapTasker Open Profile v1"], ["MapTasker Open Profile v4"], "192.168.0.210:1821")]
    # The connection is remembered, the way every other successful Android call remembers it.
    assert event_handler.gui.android_ipaddr == "192.168.0.210"


@pytest.mark.asyncio
async def test_a_device_that_would_not_answer_opens_no_dialog(monkeypatch, event_handler):
    """An empty dialog would read as 'nothing left over', which is the opposite of what a
    device that never replied has told us."""
    calls = _patch_helper_task_listing(monkeypatch, (8, "Connection error", [], []))
    _android_panel(event_handler)

    await event_handler.list_helper_tasks_event()

    assert calls["dialog"] == []
    assert any("Connection error" in message for message, kind in calls["notify"] if kind == "negative")


# ==========================================
# 9. A RESTORED SINGLE NAME SURVIVING THE PULLDOWN REBUILD
# ==========================================
def _gui_with_pulldowns(options_per_label: dict) -> MagicMock:
    """A view whose four 'Specific Name' pulldowns hold the given option lists."""
    gui = MagicMock(spec=MyGui)
    gui.is_updating = False
    for label in SINGLE_ITEM_LABELS:
        setattr(gui, f"single_{label.lower()}_name", "")
        setattr(
            gui,
            f"specific_{label.lower()}_optionmenu",
            FakeSelect("None", list(options_per_label.get(label, ["None"]))),
        )
    return gui


def test_a_restored_profile_shows_in_a_pulldown_that_lists_names_bare():
    """An exported single-Profile XML has no Project, so get_tasker_objects lists the
    Profile names bare -- the restore path's guessed "Profile: <name>" matches nothing
    there and used to leave the pulldown showing only its "Profile" label."""
    from maptasker.src.guiutils import display_object_pulldowns  # noqa: PLC0415

    gui = _gui_with_pulldowns({})
    gui.single_profile_name = "$NewProfile"
    gui.specific_profile_optionmenu.value = "Profile: $NewProfile"

    display_object_pulldowns(gui, ["None"], ["None", "$NewProfile"], ["None"], ["None"])

    assert gui.specific_profile_optionmenu.value == "$NewProfile"
    assert gui.specific_profile_optionmenu.value in gui.specific_profile_optionmenu.options


def test_a_restored_profile_shows_in_a_pulldown_that_lists_names_prefixed():
    """The same selection against a full backup, where the Profile options do carry the
    "Profile: " head."""
    from maptasker.src.guiutils import display_object_pulldowns  # noqa: PLC0415

    gui = _gui_with_pulldowns({})
    gui.single_profile_name = "$NewProfile"
    gui.specific_profile_optionmenu.value = "None"

    display_object_pulldowns(gui, ["None"], ["None", "Profile: $NewProfile"], ["None"], ["None"])

    assert gui.specific_profile_optionmenu.value == "Profile: $NewProfile"


def test_rebuilding_the_lists_leaves_an_unselected_pulldown_alone():
    """Nothing selected stays nothing selected -- the re-point must not invent one."""
    from maptasker.src.guiutils import display_object_pulldowns  # noqa: PLC0415

    gui = _gui_with_pulldowns({})

    display_object_pulldowns(gui, ["None", "Project: Base"], ["None", "Profile: X"], ["None"], ["None"])

    for label in SINGLE_ITEM_LABELS:
        assert getattr(gui, f"specific_{label.lower()}_optionmenu").value == "None"


def test_the_selection_is_repointed_without_firing_the_change_handlers():
    """Assigning a select's .value fires its on_change, which would re-enter the
    single_xxx_name_event handlers -- so the re-point runs under the is_updating lock
    and hands it back as it found it."""
    from maptasker.src.guiutils import reapply_single_item_selections  # noqa: PLC0415

    gui = _gui_with_pulldowns({"Profile": ["None", "$NewProfile"]})
    gui.single_profile_name = "$NewProfile"
    seen = []

    class WatchedSelect(FakeSelect):
        def __setattr__(self, name, value):
            if name == "value":
                seen.append(gui.is_updating)
            object.__setattr__(self, name, value)

    gui.specific_profile_optionmenu = WatchedSelect("Profile: $NewProfile", ["None", "$NewProfile"])

    reapply_single_item_selections(gui)

    assert seen[-1] is True
    assert gui.is_updating is False
