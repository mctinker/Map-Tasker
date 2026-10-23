"""The small parts of the Action editor: the Position dropdown, an action's If, its error flag, and the If-block prompt.

What a condition or an error flag does to the XML is taskedit_apply's and taskedit's.  Here it is the widgets: the
Position choices rebuilt after every change and keeping the user's choice while it still exists, the If checkbox that
prompts on tick and stashes the condition on untick (so toggling is an edit and not a restart), the chained-conditions
note, the Continue After Error box only for an action that can fail, and the prompt for how much of an If to insert.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest
from maptasker.src.core.primitem import RunState
from maptasker.src.edit import taskedit_model
from maptasker.src.gui import guiwins_taskedit
from nicegui import ui

from tests.nicegui_harness import all_elements, click, label_texts, open_page

if TYPE_CHECKING:
    from collections.abc import Callable


def _task(*names: str) -> Any:
    return SimpleNamespace(
        actions=[SimpleNamespace(act_number=n, action_name=name) for n, name in enumerate(names, start=1)]
    )


# ##################################################################################
# The Position dropdown
# ##################################################################################
class _Select:
    def __init__(self, value: str) -> None:
        self.value = value
        self.options: list[str] = []

    def set_options(self, options: list[str], value: str) -> None:
        self.options, self.value = options, value


def test_position_offers_before_and_after_each_action_then_the_end() -> None:
    labels: dict[str, int | None] = {"stale": 1}
    select = _Select("At the End")

    guiwins_taskedit._refresh_position_options(_task("Flash", "Wait"), select, labels)  # type: ignore[arg-type]

    assert select.options == ["Before 1: Flash", "After 1: Flash", "Before 2: Wait", "After 2: Wait", "At the End"]
    assert labels == {
        "Before 1: Flash": 1,
        "After 1: Flash": 2,
        "Before 2: Wait": 2,
        "After 2: Wait": 3,
        "At the End": None,
    }


def test_position_keeps_the_choice_while_it_still_exists_and_falls_back_to_the_end_when_it_does_not() -> None:
    select = _Select("After 1: Flash")
    guiwins_taskedit._refresh_position_options(_task("Flash"), select, {})  # type: ignore[arg-type]
    assert select.value == "After 1: Flash"

    select = _Select("After 1: Flash")
    guiwins_taskedit._refresh_position_options(_task("Beep"), select, {})  # type: ignore[arg-type]
    assert select.value == "At the End", "stale labels would insert at the wrong spot"


@pytest.mark.parametrize(("setting", "expected"), [(2, 2), ("6", 6), (None, 4), (0, 4), ("many", 4), ([], 4)])
def test_the_if_indentation_is_the_users_setting_or_four(setting: object, expected: int) -> None:
    assert guiwins_taskedit._action_indent_spaces(SimpleNamespace(indent=setting)) == expected  # type: ignore[arg-type]


def test_a_window_with_no_indent_setting_indents_by_four() -> None:
    assert guiwins_taskedit._action_indent_spaces(SimpleNamespace()) == 4  # type: ignore[arg-type]


def _arg(value: str, options: list[str] | None) -> taskedit_model.EditableArg:
    return taskedit_model.EditableArg(
        arg_id="a",
        arg_name="Operator",
        widget_kind="dropdown",
        backing_tag="Int",
        is_var=False,
        element=None,
        current_value=value,
        dropdown_options=options,
    )


@pytest.mark.parametrize(
    ("value", "options", "expected"),
    [
        ("1", ["a", "b"], "b"),
        ("9", ["a", "b"], "a"),
        ("x", ["a", "b"], "a"),
        ("0", [], ""),
        ("0", None, ""),
        ("-1", ["a", "b"], "b"),
    ],
)
def test_a_dropdown_preselects_the_option_its_value_indexes_else_the_first(
    value: str, options: list[str] | None, expected: str
) -> None:
    assert guiwins_taskedit._dropdown_current_label(_arg(value, options)) == expected


# ##################################################################################
# Perform Task's name field
# ##################################################################################
@pytest.mark.asyncio
async def test_a_picked_task_overwrites_the_text_input_and_the_picker_is_never_a_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guiwins_taskedit.taskedit_args, "get_all_task_names", lambda state: ["Alpha", "Beta"])
    refs: dict[str, ui.input] = {}

    def page() -> None:
        guiwins_taskedit._render_task_name_field(
            cast("Any", None),
            cast("Any", None),
            _arg("typed", None),
            "name",
            refs,
            RunState(),
        )

    async with open_page(page) as user:
        assert refs["name"].value == "typed" and list(refs) == ["name"]
        (picker,) = [e for e in all_elements(user) if isinstance(e, ui.select)]
        picker.value = "Beta"
        await asyncio.sleep(0.05)
        assert refs["name"].value == "Beta"
        picker.value = None
        await asyncio.sleep(0.05)
        assert refs["name"].value == "Beta", "clearing the picker does not blank what was chosen"


@pytest.mark.asyncio
async def test_with_no_tasks_there_is_only_the_text_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiwins_taskedit.taskedit_args, "get_all_task_names", lambda state: [])

    def page() -> None:
        guiwins_taskedit._render_task_name_field(
            cast("Any", None), cast("Any", None), _arg("x", None), "name", {}, RunState()
        )

    async with open_page(page) as user:
        assert not [e for e in all_elements(user) if isinstance(e, ui.select)]


# ##################################################################################
# An action's If
# ##################################################################################
@pytest.fixture
def conditions(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(count=0, values=("", "", ""), has=False)
    monkeypatch.setattr(guiwins_taskedit.taskedit_apply, "action_condition_count", lambda action: record.count)
    monkeypatch.setattr(guiwins_taskedit.taskedit_apply, "get_action_condition_values", lambda action: record.values)
    monkeypatch.setattr(guiwins_taskedit.taskedit_apply, "action_has_condition", lambda action: record.has)
    record.editors = MagicMock()
    record.window = SimpleNamespace(event_handlers=SimpleNamespace(editors=record.editors))
    return record


@pytest.mark.asyncio
async def test_an_action_with_several_chained_conditions_is_not_editable_from_the_single_prompt(
    conditions: SimpleNamespace,
) -> None:
    conditions.count = 3
    action: Any = SimpleNamespace(act_number=1, action_name="Flash")

    def page() -> None:
        guiwins_taskedit._render_action_condition_checkbox(conditions.window, _task("Flash"), action, {})

    async with open_page(page) as user:
        assert "Has 3 chained If conditions -- not editable here." in label_texts(user)
        assert not [e for e in all_elements(user) if isinstance(e, ui.checkbox)]


@pytest.mark.asyncio
async def test_an_action_with_a_condition_shows_it_ticked_and_unticking_stashes_it_for_a_later_retick(
    conditions: SimpleNamespace,
) -> None:
    conditions.count, conditions.values, conditions.has = 1, ("%x", "equals", "1"), True
    cache: dict[int, tuple[str, str, str]] = {}
    action: Any = SimpleNamespace(act_number=1, action_name="Flash")
    task = _task("Flash")

    def page() -> None:
        guiwins_taskedit._render_action_condition_checkbox(conditions.window, task, action, cache)

    async with open_page(page) as user:
        (box,) = [e for e in all_elements(user) if isinstance(e, ui.checkbox)]
        assert box.value is True and box.text == "If: %x equals 1"
        box.value = False
        await asyncio.sleep(0.05)
        assert cache == {1: ("%x", "equals", "1")}
        conditions.editors.remove_action_condition_event.assert_called_once_with(task, 1)
        assert box.text == "If"


@pytest.mark.asyncio
async def test_ticking_an_action_with_no_condition_opens_the_prompt(
    conditions: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[Any, ...]] = []
    monkeypatch.setattr(guiwins_taskedit, "build_action_condition_dialog", lambda *a: opened.append(a))
    action: Any = SimpleNamespace(act_number=1, action_name="Flash")

    def page() -> None:
        guiwins_taskedit._render_action_condition_checkbox(conditions.window, _task("Flash"), action, {})

    async with open_page(page) as user:
        (box,) = [e for e in all_elements(user) if isinstance(e, ui.checkbox)]
        assert box.value is False and box.text == "If"
        box.value = True
        await asyncio.sleep(0.05)
        assert opened and opened[0][2] == 1


def _prompt(conditions: SimpleNamespace, task: Any, cache: dict, checkbox: Any) -> Callable[[], None]:
    def page() -> None:
        guiwins_taskedit.build_action_condition_dialog(conditions.window, task, 1, checkbox, cache)

    return page


@pytest.mark.asyncio
async def test_the_prompt_prefills_from_the_cache_first_and_hands_its_widgets_to_the_handler(
    conditions: SimpleNamespace,
) -> None:
    conditions.values = ("from-action", "", "")
    task = _task("Flash")
    checkbox = MagicMock()
    async with open_page(
        _prompt(conditions, task, {1: ("%cached", taskedit_model.IF_CONDITION_OPERATORS[1][1], "7")}, checkbox)
    ) as user:
        inputs = {e.props.get("label"): e for e in all_elements(user) if isinstance(e, ui.input)}
        assert inputs["Target"].value == "%cached" and inputs["Value"].value == "7"
        (operator,) = [e for e in all_elements(user) if isinstance(e, ui.select)]
        assert operator.value == taskedit_model.IF_CONDITION_OPERATORS[1][1]
        await click(user, "Ok")
        args = conditions.editors.set_action_condition_event.call_args.args
        assert args[0] is task and args[1] == 1 and args[2] is inputs["Target"] and args[3] is operator


@pytest.mark.asyncio
async def test_without_a_cache_the_prompt_reads_the_action_and_an_unknown_operator_falls_back_to_the_first(
    conditions: SimpleNamespace,
) -> None:
    conditions.values = ("%y", "no such operator", "z")
    async with open_page(_prompt(conditions, _task("Flash"), {}, MagicMock())) as user:
        inputs = {e.props.get("label"): e for e in all_elements(user) if isinstance(e, ui.input)}
        assert inputs["Target"].value == "%y"
        (operator,) = [e for e in all_elements(user) if isinstance(e, ui.select)]
        assert operator.value == taskedit_model.IF_CONDITION_OPERATORS[0][1]


@pytest.mark.asyncio
async def test_cancelling_the_prompt_unticks_the_box_and_adds_nothing(conditions: SimpleNamespace) -> None:
    checkbox = MagicMock()
    async with open_page(_prompt(conditions, _task("Flash"), {}, checkbox)) as user:
        await click(user, "Cancel")
        checkbox.set_value.assert_called_once_with(False)
        conditions.editors.set_action_condition_event.assert_not_called()


@pytest.mark.asyncio
async def test_a_prompt_for_an_action_that_is_not_there_builds_nothing(conditions: SimpleNamespace) -> None:
    def page() -> None:
        guiwins_taskedit.build_action_condition_dialog(conditions.window, _task("Flash"), 9, MagicMock(), {})

    async with open_page(page) as user:
        assert not [e for e in all_elements(user) if isinstance(e, ui.dialog)]


# ##################################################################################
# Continue Task After Error
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize("can_fail", [True, False])
async def test_the_error_box_exists_only_for_an_action_that_can_fail_and_routes_its_change(
    conditions: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, can_fail: bool
) -> None:
    monkeypatch.setattr(guiwins_taskedit.taskedit, "action_can_fail", lambda action: can_fail)
    monkeypatch.setattr(guiwins_taskedit.taskedit, "action_continues_after_error", lambda action: True)
    action: Any = SimpleNamespace(act_number=4, action_name="Flash")
    task = _task("Flash")

    def page() -> None:
        guiwins_taskedit._render_continue_after_error_checkbox(conditions.window, task, action)

    async with open_page(page) as user:
        boxes = [e for e in all_elements(user) if isinstance(e, ui.checkbox)]
        if not can_fail:
            assert boxes == []
            return
        assert boxes[0].value is True
        boxes[0].value = False
        await asyncio.sleep(0.05)
        conditions.editors.set_action_continue_after_error_event.assert_called_once_with(task, 4, False)


# ##################################################################################
# The plugin warning
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize("warning", ["Configure this in Tasker.", ""])
async def test_a_plugin_that_cannot_be_edited_here_carries_a_standing_warning(
    monkeypatch: pytest.MonkeyPatch, warning: str
) -> None:
    monkeypatch.setattr(
        guiwins_taskedit.taskedit_addable, "tasker_configuration_warning", lambda element, name: warning
    )

    def page() -> None:
        guiwins_taskedit._render_plugin_configuration_warning(MagicMock(), "AutoApps")

    async with open_page(page) as user:
        assert (warning in label_texts(user)) is bool(warning)


# ##################################################################################
# How much of an If to insert
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize("variant", taskedit_model.IF_BLOCK_VARIANTS)
async def test_each_variant_button_closes_the_prompt_and_reports_its_choice(variant: str) -> None:
    chosen: list[str] = []

    async with open_page(lambda: guiwins_taskedit.build_if_variant_dialog(chosen.append)) as user:
        await click(user, variant)
        assert chosen == [variant]
        (dialog,) = [e for e in all_elements(user) if isinstance(e, ui.dialog)]
        assert not dialog.value


@pytest.mark.asyncio
async def test_cancelling_the_if_prompt_inserts_nothing() -> None:
    chosen: list[str] = []

    async with open_page(lambda: guiwins_taskedit.build_if_variant_dialog(chosen.append)) as user:
        await click(user, "Cancel")
        assert chosen == []
