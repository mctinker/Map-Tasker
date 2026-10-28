"""The AI handlers: picking a model, changing the prompt, the API keys dialog and the Analyze button.

What the AI work itself does is mapai's and aiutils's; the model lists are test_ai_model_lists's.  Here it is
what the window's AI controls do when they are used: the model and provider read off the dropdown, the prompt
dialog's four outcomes, the keys that are validated, committed and saved, and the order Analyze goes about
a run in -- model, key, a single selected object, a Map built for it, the analysis, and the window left tidy
whether it worked or not.

The window is a mock and everything outside the handlers (the pulldown helpers, the dialog, the worker thread
the Map is built on) is replaced by a recorder, so what is asserted is the handlers' own decisions.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from maptasker.src.core.config import AI_PROMPT
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import userintr_ai
from maptasker.src.gui.userintr import MapTaskerEventHandlers


def _window(**changes: Any) -> MagicMock:
    """A window that is not updating, with a model dropdown holding two prefixed options."""
    window = MagicMock()
    window.state = RunState()
    window.is_updating = False
    window.ai_model = ""
    window.ai_name = ""
    window.ai_apikey = ""
    window.ai_prompt = ""
    window.ai_model_option = SimpleNamespace(
        options=["OpenAI: gpt-5", "Anthropic: claude-sonnet-5-5"], value="", update=MagicMock()
    )
    window.initialization = False
    for name, value in changes.items():
        setattr(window, name, value)
    return window


def _handlers(window: MagicMock | None = None) -> MapTaskerEventHandlers:
    window = window or _window()
    return MapTaskerEventHandlers(window)


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Everything the handlers call outside themselves, replaced and recorded."""
    record = SimpleNamespace(
        notified=[],
        colour=[],
        labels=[],
        buttons=[],
        key_set=[],
        saved_args=[],
        built=[],
        analysed=[],
        shown=[],
    )
    record.set_ai_key_result = True
    record.listed = True

    monkeypatch.setattr(userintr_ai, "ui", MagicMock())
    userintr_ai.ui.notify = lambda message, **kw: record.notified.append((message, kw.get("type")))
    monkeypatch.setattr(userintr_ai, "get_api_key", lambda state: "key")
    monkeypatch.setattr(
        userintr_ai, "set_ai_key", lambda gui, model: record.key_set.append(model) or record.set_ai_key_result
    )
    monkeypatch.setattr(userintr_ai, "update_analysis_button_color", lambda gui: record.colour.append(gui))
    monkeypatch.setattr(userintr_ai, "display_selected_object_labels", lambda gui: record.labels.append(gui))
    monkeypatch.setattr(userintr_ai, "display_analyze_button", lambda gui, row, first_time: record.buttons.append(row))
    monkeypatch.setattr(userintr_ai, "list_tasker_objects", lambda gui: record.listed)
    monkeypatch.setattr(userintr_ai, "gui_settings", lambda gui: {"settings": True})
    monkeypatch.setattr(userintr_ai, "save_restore_args", lambda *a, **k: record.saved_args.append((a, k)) or ({}, {}))
    monkeypatch.setattr(userintr_ai, "display_error_file_and_ai_response", lambda owner: record.shown.append(owner))

    async def build(gui: object) -> bool:
        record.built.append(gui)
        return record.build_ok

    record.build_ok = True
    monkeypatch.setattr(userintr_ai, "build_analysis_lines", build)

    async def map_ai(state: object) -> None:
        record.analysed.append(state)
        if record.map_ai_raises:
            raise record.map_ai_raises

    record.map_ai_raises = None
    monkeypatch.setattr(userintr_ai, "map_ai", map_ai)
    return record


def _picked(value: object) -> Any:
    """What a dropdown hands its on_change: an event whose value is what was chosen."""
    return SimpleNamespace(value=value)


def _said(window: MagicMock) -> list[tuple[str, str]]:
    return [(c.args[0], c.args[1]) for c in window.display_message_box.call_args_list]


# ##################################################################################
# Picking a model
# ##################################################################################
@pytest.mark.parametrize(
    ("picked", "provider", "model"),
    [("OpenAI: gpt-5", "OpenAI", "gpt-5"), ("Anthropic: claude-sonnet-5-5", "Anthropic", "claude-sonnet-5-5")],
)
def test_a_prefixed_model_sets_the_provider_and_the_model_and_the_dropdown_follows(
    seen: SimpleNamespace, picked: str, provider: str, model: str
) -> None:
    window = _window()
    handlers = _handlers(window)

    handlers.ai.ai_model_selected_event(_picked(picked))

    assert (window.ai_name, window.ai_model) == (provider, model)
    assert handlers.state.program_arguments.ai_name == provider
    assert seen.key_set == [model]
    assert window.ai_model_option.value == picked, "the dropdown keeps showing its prefixed option"
    assert window.is_updating is False, "the echo guard is released"
    assert "Model: " + model in window.ai_apikey_and_model_lbl.text
    assert seen.colour == [window]


def test_a_bare_model_name_is_taken_as_it_stands() -> None:
    window = _window()
    window.ai_model_option = None
    handlers = _handlers(window)

    handlers.ai.ai_model_selected_event(_picked("  llama3.2  "))

    assert window.ai_model == "llama3.2"


def test_a_list_value_takes_the_first_model(seen: SimpleNamespace) -> None:
    window = _window()
    handlers = _handlers(window)

    handlers.ai.ai_model_selected_event(_picked(["gpt-5", "gpt-4o"]))

    assert window.ai_model == "gpt-5"


@pytest.mark.parametrize("updating", [True, False])
def test_an_empty_choice_or_an_echo_of_our_own_update_changes_nothing(seen: SimpleNamespace, updating: bool) -> None:
    window = _window(is_updating=updating)
    handlers = _handlers(window)

    handlers.ai.ai_model_selected_event(_picked("OpenAI: gpt-5" if updating else ""))

    assert window.ai_model == ""
    assert seen.key_set == []


def test_the_dropdown_is_left_alone_when_no_option_matches(seen: SimpleNamespace) -> None:
    window = _window()
    handlers = _handlers(window)

    handlers.ai.ai_model_selected_event(_picked("Other: unlisted"))

    assert window.ai_model_option.value == ""
    window.ai_model_option.update.assert_not_called()


# ##################################################################################
# The API keys dialog opens
# ##################################################################################
def test_the_keys_dialog_is_opened_with_the_key_already_held(seen: SimpleNamespace, monkeypatch) -> None:
    window = _window()
    dialog = MagicMock()
    monkeypatch.setattr(userintr_ai, "APIKeyDialog", MagicMock(return_value=dialog))

    _handlers(window).ai.ai_apikey_event()

    assert window.ai_apikey == "key"
    cast("MagicMock", userintr_ai.APIKeyDialog).assert_called_once_with(window)
    dialog.open.assert_called_once()


# ##################################################################################
# The prompt
# ##################################################################################
class _Dialog:
    """Stands in for ui.dialog(): a context manager that can be awaited for what was submitted."""

    def __init__(self, answer: object) -> None:
        self.answer = answer

    def props(self, _spec: str) -> _Dialog:
        return self

    def __enter__(self) -> _Dialog:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def __await__(self):
        async def answer() -> object:
            return self.answer

        return answer().__await__()


def _ask(monkeypatch: pytest.MonkeyPatch, answer: object) -> None:
    """The prompt dialog is answered with `answer` as soon as it opens."""
    ui = MagicMock()
    ui.dialog = lambda: _Dialog(answer)
    monkeypatch.setattr(userintr_ai, "ui", ui)


@pytest.mark.asyncio
async def test_cancelling_the_prompt_dialog_says_so(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _window(ai_prompt="Explain this")
    _ask(monkeypatch, None)

    await _handlers(window).ai.ai_prompt_event()

    assert _said(window) == [("Prompt change canceled.", "Orange")]
    assert window.ai_prompt == "Explain this"
    assert seen.colour == [window], "the Analyze button's colour is refreshed whatever the answer"


@pytest.mark.asyncio
async def test_a_blank_prompt_is_refused(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _window(ai_prompt="Explain this")
    _ask(monkeypatch, "   ")

    await _handlers(window).ai.ai_prompt_event()

    assert _said(window) == [("The prompt cannot be empty.", "Orange")]
    assert window.ai_prompt == "Explain this"


@pytest.mark.asyncio
async def test_the_same_prompt_is_not_a_change(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _window(ai_prompt="Explain this")
    _ask(monkeypatch, "Explain this")

    await _handlers(window).ai.ai_prompt_event()

    assert _said(window) == [("Prompt did not change.", "Orange")]


@pytest.mark.asyncio
async def test_a_new_prompt_is_kept_and_the_labels_redrawn(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(ai_prompt="Explain this")
    _ask(monkeypatch, "Find the bugs")

    await _handlers(window).ai.ai_prompt_event()

    assert window.ai_prompt == "Find the bugs"
    assert _said(window) == [("Prompt changed to 'Find the bugs'.", "Green")]
    assert seen.labels == [window]


@pytest.mark.asyncio
async def test_with_no_prompt_yet_the_built_in_one_is_offered(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(ai_prompt="")
    monkeypatch.setattr(userintr_ai, "get_ai_object", lambda: ("Task", "Wake Up"))
    _ask(monkeypatch, None)

    await _handlers(window).ai.ai_prompt_event()

    assert window.ai_prompt == AI_PROMPT


# ##################################################################################
# The Extended checkbox
# ##################################################################################
def _extended_window(**changes: Any) -> MagicMock:
    window = _window(
        displaying_extended_list=False,
        aimodel_extend_checkbox=MagicMock(value=True),
        get_input_and_put_message=MagicMock(return_value=True),
    )
    for name, value in changes.items():
        setattr(window, name, value)
    return window


@pytest.fixture
def pulldown(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    shown: list[object] = []
    monkeypatch.setattr(
        userintr_ai, "display_model_pulldown", lambda owner, extended_models=None: shown.append(extended_models)
    )

    async def io_bound(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(userintr_ai.run, "io_bound", io_bound)
    monkeypatch.setattr(userintr_ai, "get_extended_ai_model_list", lambda state: ["OpenAI: gpt-9"])
    return shown


@pytest.mark.asyncio
async def test_ticking_extended_fetches_the_list_off_the_event_loop_and_shows_it(pulldown: list[object]) -> None:
    window = _extended_window()

    await _handlers(window).ai.extended_models_event()

    assert pulldown == [["OpenAI: gpt-9"]]
    window.aimodel_extend_checkbox.disable.assert_called_once()
    window.aimodel_extend_checkbox.enable.assert_called_once()


@pytest.mark.asyncio
async def test_unticking_while_the_fetch_was_under_way_keeps_the_default_list(pulldown: list[object]) -> None:
    window = _extended_window(aimodel_extend_checkbox=MagicMock(value=False))

    await _handlers(window).ai.extended_models_event()

    assert pulldown == []


@pytest.mark.asyncio
@pytest.mark.parametrize("held", ["initialization", "displaying_extended_list"])
async def test_nothing_is_fetched_during_start_up_or_when_the_list_is_already_showing(
    pulldown: list[object], held: str
) -> None:
    window = _extended_window(**{held: True})

    await _handlers(window).ai.extended_models_event()

    assert pulldown == [None], "the pulldown is redrawn from what it already holds"
    window.aimodel_extend_checkbox.disable.assert_not_called()


# ##################################################################################
# Analyze
# ##################################################################################
def _analyze_window(**changes: Any) -> MagicMock:
    window = _window(
        ai_model="gpt-5",
        ai_name="OpenAI",
        single_project_name="",
        single_profile_name="",
        single_task_name="Wake Up",
        single_scene_name="",
        color_lookup={},
    )
    for name, value in changes.items():
        setattr(window, name, value)
    return window


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["None", ""])
async def test_analyze_with_no_model_chosen_says_so(seen: SimpleNamespace, model: str) -> None:
    window = _analyze_window(ai_model=model)

    await _handlers(window).ai.ai_analyze_event()

    assert _said(window) == [("No model selected.", "Orange")]
    assert seen.built == []


@pytest.mark.asyncio
async def test_analyze_without_a_key_for_the_model_says_so(seen: SimpleNamespace) -> None:
    seen.set_ai_key_result = False
    window = _analyze_window()

    await _handlers(window).ai.ai_analyze_event()

    assert "The API Key is not set for model gpt-5" in _said(window)[0][0]
    assert seen.built == []


@pytest.mark.asyncio
async def test_a_local_llama_needs_no_key(seen: SimpleNamespace) -> None:
    seen.set_ai_key_result = False
    window = _analyze_window(ai_name="LLAMA", ai_model="llama3.2")

    await _handlers(window).ai.ai_analyze_event()

    assert seen.analysed, "it went ahead without asking for a key"


@pytest.mark.asyncio
async def test_a_selected_object_is_mapped_analysed_and_the_flag_put_back(seen: SimpleNamespace) -> None:
    window = _analyze_window()
    handlers = _handlers(window)

    await handlers.ai.ai_analyze_event()

    assert seen.built == [window]
    assert seen.analysed == [handlers.state]
    assert seen.saved_args, "the window's settings are saved before the run"
    assert seen.shown == [handlers.ai]
    assert window.ai_analyze is False, "the run is over, so the window stops saying it is running"
    assert window.tab_to_use == "Analyze"
    assert handlers.state.program_arguments.ai_model == "gpt-5"
    assert _said(window)[0] == ("Running OpenAI analysis with model gpt-5.", "Green")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "provider"),
    [("gemini-3.5-flash", "Gemini"), ("claude-opus-5", "Anthropic"), ("o3", "OpenAI"), ("mistral", "LLAMA")],
)
async def test_a_missing_provider_name_is_worked_out_from_the_model(
    seen: SimpleNamespace, model: str, provider: str
) -> None:
    window = _analyze_window(ai_name="", ai_model=model)
    handlers = _handlers(window)

    await handlers.ai.ai_analyze_event()

    assert window.ai_name == provider
    assert handlers.state.program_arguments.ai_name == provider


@pytest.mark.asyncio
async def test_a_map_that_could_not_be_built_ends_the_run_before_the_analysis(seen: SimpleNamespace) -> None:
    seen.build_ok = False
    window = _analyze_window()

    await _handlers(window).ai.ai_analyze_event()

    assert seen.analysed == []
    assert window.ai_analyze is False


@pytest.mark.asyncio
async def test_an_analysis_that_fails_still_puts_the_flag_back(seen: SimpleNamespace) -> None:
    seen.map_ai_raises = RuntimeError("provider down")
    window = _analyze_window()

    with pytest.raises(RuntimeError, match="provider down"):
        await _handlers(window).ai.ai_analyze_event()

    assert window.ai_analyze is False


@pytest.mark.asyncio
async def test_no_loaded_configuration_is_reported_as_that(seen: SimpleNamespace) -> None:
    window = _analyze_window(single_task_name="")
    handlers = _handlers(window)
    handlers.state.tasker_root_elements = {"all_projects": {}, "all_profiles": {}, "all_tasks": {}}

    await handlers.ai.ai_analyze_event()

    assert "No projects, profiles, or tasks have been loaded" in _said(window)[0][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("anything_listed", [True, False])
async def test_loaded_but_nothing_selected_asks_for_one_and_redraws_the_button_if_there_is_nothing_to_pick(
    seen: SimpleNamespace, anything_listed: bool
) -> None:
    seen.listed = anything_listed
    window = _analyze_window(single_task_name="")
    handlers = _handlers(window)
    handlers.state.tasker_root_elements = {"all_projects": {"1": {}}, "all_profiles": {}, "all_tasks": {}}

    await handlers.ai.ai_analyze_event()

    assert "Single Project/Profile/Task has not been selected" in _said(window)[0][0]
    assert seen.buttons == ([] if anything_listed else [13])


@pytest.mark.asyncio
async def test_the_profile_placeholder_is_not_a_selection(seen: SimpleNamespace) -> None:
    window = _analyze_window(single_profile_name="None or unnamed!", single_task_name="")
    handlers = _handlers(window)
    handlers.state.tasker_root_elements = {"all_projects": {"1": {}}, "all_profiles": {}, "all_tasks": {}}

    await handlers.ai.ai_analyze_event()

    assert window.single_profile_name == ""


# ##################################################################################
# The Map an analysis is made from
# ##################################################################################
@pytest.fixture
def build(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(captured=[], cleared=[], front=[], built=[], raises=None)
    monkeypatch.undo()  # the `seen` replacements are not wanted here; set only what this needs
    monkeypatch.setattr(userintr_ai, "capture_gui_state", lambda gui, data, state: record.captured.append(data))
    monkeypatch.setattr(userintr_ai, "clear_error", lambda: record.cleared.append(True))
    monkeypatch.setattr(userintr_ai, "reset_attributes", lambda *names: None)
    monkeypatch.setattr(userintr_ai, "current_config", lambda: "config")
    monkeypatch.setattr(userintr_ai, "output_the_front_matter", lambda config, state: record.front.append(config))

    def build_html(name: str, state: object) -> int:
        record.built.append(name)
        if record.raises is not None:
            raise record.raises
        return 0

    async def io_bound(function: Any, *args: Any, **kwargs: Any) -> object:
        return function(*args, **kwargs)

    monkeypatch.setattr(userintr_ai, "build_html", build_html)
    monkeypatch.setattr(userintr_ai.run, "io_bound", io_bound)
    return record


def _building_window() -> MagicMock:
    """A window whose run has the output lines a Map is built into."""
    window = _window()
    window.state.output_lines = SimpleNamespace(output_lines=["left over"])
    return window


@pytest.mark.asyncio
async def test_the_analysis_map_is_built_with_the_flag_that_keeps_a_cached_map_out(build: SimpleNamespace) -> None:
    window = _building_window()

    assert await userintr_ai.build_analysis_lines(window) is True

    assert window.state.program_arguments.ai_analyze is True
    assert window.state.output_lines.output_lines == [], "the lines of the last Map are cleared first"
    assert build.built == [""]
    assert build.front == ["config"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason"), [(MapTaskerError("stop", 12), "stop"), (MapTaskerError(exit_code=12), "code 12")]
)
async def test_a_map_that_halts_says_why_in_its_own_words_or_by_its_exit_code(
    build: SimpleNamespace, error: MapTaskerError, reason: str
) -> None:
    build.raises = error
    window = _building_window()

    assert await userintr_ai.build_analysis_lines(window) is False

    assert window.display_message_box.call_args.args[0] == f"Analysis halted building the Map ({reason})."


@pytest.mark.asyncio
async def test_a_map_that_finishes_with_an_error_code_is_reported_and_the_error_cleared(build: SimpleNamespace) -> None:
    window = _building_window()
    window.state.error_code = 3
    window.state.error_msg = "bad tag"

    assert await userintr_ai.build_analysis_lines(window) is False

    assert "bad tag" in window.display_message_box.call_args.args[0]
    assert build.cleared, "the error is cleared so the next run starts clean"


# ##################################################################################
# The API keys dialog's buttons
# ##################################################################################
def _dialog(openai: str = "", anthropic: str = "", gemini: str = "") -> MagicMock:
    dialog = MagicMock()
    dialog.openai_key.value = openai
    dialog.anthropic_key.value = anthropic
    dialog.gemini_key.value = gemini
    return dialog


@pytest.fixture
def keys(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(saved=[], valid=True, raises=None, in_store=True)
    monkeypatch.setattr(userintr_ai, "valid_api_key", lambda key, value: record.valid)

    def save(keys_: object) -> bool:
        record.saved.append(dict(keys_))  # type: ignore[call-overload]
        if record.raises is not None:
            raise record.raises
        return record.in_store

    monkeypatch.setattr(userintr_ai, "save_api_keys", save)
    monkeypatch.setattr(userintr_ai, "fallback_file", lambda: "/home/me/.keys")
    return record


def test_cancel_closes_the_dialog_and_changes_no_key(keys: SimpleNamespace) -> None:
    window = _window()
    dialog = _dialog(openai="sk-new")
    handlers = _handlers(window)

    handlers.ai.ai_apikey_process_event(dialog, cancel=True, clear="")

    dialog.close.assert_called_once()
    assert _said(window) == [("'Cancel' button selected. No change to the API keys!", "Orange")]
    assert keys.saved == []


def test_nothing_happens_without_a_dialog(keys: SimpleNamespace) -> None:
    window = _window()

    _handlers(window).ai.ai_apikey_process_event(None, cancel=False, clear="")  # type: ignore[arg-type]

    assert _said(window) == []


def test_clear_empties_only_that_entry(keys: SimpleNamespace) -> None:
    window = _window()
    dialog = _dialog()
    dialog.entry_openai_key = MagicMock()

    _handlers(window).ai.ai_apikey_process_event(dialog, cancel=False, clear="openai_key")

    dialog.entry_openai_key.set_value.assert_called_once_with("")
    assert _said(window) == [("Openai API key cleared.", "LimeGreen")]
    dialog.close.assert_not_called()


def test_clearing_an_entry_the_dialog_does_not_have_does_nothing(keys: SimpleNamespace) -> None:
    window = _window()
    dialog = MagicMock(spec=["close"])

    _handlers(window).ai.ai_apikey_process_event(dialog, cancel=False, clear="nope_key")  # type: ignore[arg-type]

    assert _said(window) == []


def test_ok_with_nothing_changed_says_so_and_saves_nothing(keys: SimpleNamespace) -> None:
    window = _window()
    dialog = _dialog()
    handlers = _handlers(window)

    handlers.ai.ai_apikey_process_event(dialog, cancel=False, clear="")

    assert ("No API keys changed.", "LimeGreen") in _said(window)
    assert keys.saved == []
    dialog.close.assert_called_once()


def test_a_new_key_is_validated_kept_saved_and_the_window_refreshed(
    keys: SimpleNamespace, seen: SimpleNamespace
) -> None:
    window = _window(ai_model="gpt-5")
    dialog = _dialog(openai="sk-new")
    handlers = _handlers(window)

    handlers.ai.ai_apikey_process_event(dialog, cancel=False, clear="")

    assert handlers.state.ai["openai_key"] == "sk-new"
    assert keys.saved and keys.saved[0]["openai_key"] == "sk-new"
    assert seen.key_set == ["gpt-5"]
    assert seen.buttons == [13] and seen.labels == [window]
    dialog.close.assert_called_once()
    assert any("Openai Key API key saved: 'sk-new'." in m for m, _ in _said(window))


def test_an_invalid_key_is_refused_and_the_dialog_stays_open(keys: SimpleNamespace, seen: SimpleNamespace) -> None:
    keys.valid = False
    window = _window()
    dialog = _dialog(openai="short")
    handlers = _handlers(window)

    handlers.ai.ai_apikey_process_event(dialog, cancel=False, clear="")

    assert _said(window) == [("Openai API key is invalid!", "Red")]
    assert seen.notified[-1][1] == "negative"
    assert handlers.state.ai["openai_key"] == "", "nothing was committed"
    dialog.close.assert_not_called()
    assert keys.saved == []


def test_a_key_that_cannot_be_written_is_reported_but_the_refresh_still_happens(
    keys: SimpleNamespace, seen: SimpleNamespace
) -> None:
    keys.raises = OSError("disk full")
    window = _window(ai_model="gpt-5")

    _handlers(window).ai.ai_apikey_process_event(_dialog(gemini="g-new"), cancel=False, clear="")

    assert any("could not be saved" in m and "disk full" in m for m, _ in _said(window))
    assert seen.key_set == ["gpt-5"]


def test_with_no_password_store_the_file_the_keys_went_to_is_named(
    keys: SimpleNamespace, seen: SimpleNamespace
) -> None:
    keys.in_store = False
    window = _window()

    _handlers(window).ai.ai_apikey_process_event(_dialog(anthropic="a-new"), cancel=False, clear="")

    assert any("/home/me/.keys" in m for m, _ in _said(window))


def test_the_dialogs_buttons_route_to_the_window_they_are_on(keys: SimpleNamespace) -> None:
    window = _window()
    dialog = _dialog()
    window.ai_apikey_window = dialog

    _handlers(window).ai.ai_apikey_get_event(cancel=True, clear="")

    dialog.close.assert_called_once()
