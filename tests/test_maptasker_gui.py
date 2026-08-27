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


def _patch_import_path(monkeypatch, results: list) -> dict:
    """Point the handler's collaborators at fakes and record what it did.

    `results` is what run.io_bound returns, in order: the pre-check (see
    deviceinv.import_is_confirmable), the offer, then the confirmation if there is one.
    """
    from maptasker.src import userintr

    calls: dict = {"io_bound": [], "kept": [], "notify": [], "pending": []}

    async def fake_io_bound(func, *args, **kwargs):
        calls["io_bound"].append((func, args, kwargs))
        return results[len(calls["io_bound"]) - 1]

    async def fake_ping(_self, _ip, _port) -> bool:
        return True

    monkeypatch.setattr(userintr.run, "io_bound", fake_io_bound)
    monkeypatch.setattr(userintr, "ping_android_device", fake_ping)
    monkeypatch.setattr(userintr.profedit, "render_standalone_profile_xml", lambda _p: "<TaskerData/>")
    monkeypatch.setattr(userintr.projedit, "render_standalone_project_xml", lambda _n: "<TaskerData/>")
    monkeypatch.setattr(userintr.projedit, "project_profile_names", lambda _n: ["Watched", "Also Watched"])
    monkeypatch.setattr(userintr, "_unapplied_project_edits", lambda _refs: [])
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
    monkeypatch.setattr(
        userintr.ui,
        "notify",
        lambda message, **kwargs: calls["notify"].append((message, kwargs.get("type"))),
    )

    class _FakeNotification:
        """A ui.notification with the one thing the handler uses it for: being taken down."""

        def __init__(self, message, **kwargs) -> None:
            calls["notify"].append((message, kwargs.get("type")))
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
    assert offer[2]["route"] is deviceinv.OPEN_FILE_ROUTE
    assert confirm[0] is deviceinv.await_import

    assert len(calls["kept"]) == 1  # the edit reached the loaded configuration
    android_dialog.close.assert_called_once()
    parent_dialog.close.assert_called_once()
    assert calls["notify"][-1] == ("Profile 'Watched' is now in Tasker", "positive")


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
    assert offer[2]["route"] is deviceinv.OPEN_PROJECT_ROUTE
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
