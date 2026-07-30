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
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maptasker.src.guiwins import NiceGuiTextView
from maptasker.src.mapfonts import get_monospaced_fonts
from maptasker.src.primitem import PrimeItems
from maptasker.src.userintr import MapTaskerEventHandlers, MyGui


# ==========================================
# FIXTURES & MOCKING SETUP
# ==========================================
@pytest.fixture
def mock_gui_instance(mocker):
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


def test_font_extraction_regex():
    """Tests Font Name Identification using a dynamic system font retrieved from the OS."""
    # 1. Grab a verified standard monospaced font family name from the local system
    # (Falls back to 'Courier' if the system configuration is unexpected)
    try:
        system_mono_font = get_monospaced_fonts()[0]
    except Exception:  # noqa: BLE001
        system_mono_font = "Courier"

    # 3. Unbind the method from the class context so we can test it standalone
    view_instance = MagicMock()
    view_instance.extract_first_font_name = NiceGuiTextView.extract_first_font_name.__get__(view_instance)

    # 4. Construct a dynamic CSS injection string using the real system font name
    css_payload = f"body {{ color: #000; font-family: '{system_mono_font}', monospace; }}"

    # 5. Execute the parser and validate the match
    extracted = view_instance.extract_first_font_name(css_payload)
    assert extracted == system_mono_font

    # 6. Test a fallback safety failure path
    bad_css = "body { color: red; }"
    assert view_instance.extract_first_font_name(bad_css) == "Font name not found"


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
@patch("nicegui.run.io_bound", new_callable=AsyncMock)
async def test_view_event_map_execution_flow(mock_io_bound, event_handler, mock_gui_instance):
    """Asserts that heavy HTML building offloads safely via NiceGUI thread workers."""
    mock_gui_instance.view_limit = 5000
    PrimeItems.output_lines = MagicMock()
    PrimeItems.output_lines.output_lines = []
    PrimeItems.error_code = 0

    with patch("maptasker.src.userintr.parse_html") as mock_parse_html:
        mock_parse_html.return_value = ["<div>Test Render Payload</div>"]

        await event_handler.view_event("map")

        # Verify background execution handoff
        mock_io_bound.assert_called_once()
        # Verify component slots get drawn cleanly
        assert mock_gui_instance.textview is not None


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
