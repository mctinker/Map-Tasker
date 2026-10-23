"""The Object Properties form: a widget per scalar property, a panel per variable, and the Ok and Cancel behind them.

What a property means and how it is written back is objprops's, and is tested there.  Here it is the form: the
right widget for each kind of property with the value the element holds, a variable's fields and the way
"Same as Value" mirrors the Value into the Exported Value, Add and Remove Variable redrawing the panels, and
Ok and Cancel handing the form's own widgets to the editors handler.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from maptasker.src.core import objprops
from maptasker.src.gui import guiwins_props
from nicegui import ui

from tests.nicegui_harness import all_elements, click, found, label_texts, open_page, press

if TYPE_CHECKING:
    from collections.abc import Callable


def _spec(kind: str) -> objprops.PropField:
    """The first property of the given widget kind that any object has."""
    for specs in objprops.OBJECT_PROPERTIES.values():
        for spec in specs:
            if spec.kind == kind:
                return spec
    raise LookupError(kind)


# ##################################################################################
# One property's widget
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "widget_type", "value", "expected"),
    [
        ("checkbox", ui.checkbox, "true", True),
        ("checkbox", ui.checkbox, "false", False),
        ("number", ui.number, "7", 7),
        ("number", ui.number, "", None),
        ("slider", ui.number, "12", 12),
        ("text", ui.input, "a comment", "a comment"),
    ],
)
async def test_each_kind_of_property_gets_its_widget_holding_the_value(
    kind: str, widget_type: type, value: str, expected: object
) -> None:
    try:
        spec = _spec(kind)
    except LookupError:
        pytest.skip(f"no property of kind {kind}")
    made: list[object] = []

    def page() -> None:
        made.append(guiwins_props._build_property_widget(spec, value))

    async with open_page(page):
        assert isinstance(made[0], widget_type)
        assert made[0].value == expected  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_choice_defaults_to_its_first_option_when_the_element_holds_none() -> None:
    spec = _spec("choice")
    made: list[object] = []

    def page() -> None:
        made.append(guiwins_props._build_property_widget(spec, ""))

    async with open_page(page):
        assert made[0].value == spec.choices[0]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_duration_shows_the_cooldown_in_words() -> None:
    try:
        spec = _spec("duration")
    except LookupError:
        pytest.skip("no duration property")
    made: list[object] = []

    def page() -> None:
        made.append(guiwins_props._build_property_widget(spec, "90"))

    async with open_page(page):
        assert made[0].value == objprops.format_cooldown("90")  # type: ignore[attr-defined]


# ##################################################################################
# The whole form
# ##################################################################################
def _profile() -> ET.Element:
    return ET.fromstring('<Profile sr="prof0"><id>5</id><nme>Morning</nme></Profile>')


def _window() -> tuple[SimpleNamespace, MagicMock]:
    editors = MagicMock()
    return SimpleNamespace(event_handlers=SimpleNamespace(editors=editors)), editors


def _form(element: ET.Element | None = None, kind: str = objprops.KIND_PROFILE) -> tuple[Callable[[], None], MagicMock]:
    window, editors = _window()
    the_element = _profile() if element is None else element

    def page() -> None:
        guiwins_props.build_object_properties_dialog(window, kind, the_element, None)  # type: ignore[arg-type]

    return page, editors


@pytest.mark.asyncio
async def test_the_form_is_titled_for_the_kind_and_says_when_there_are_no_variables() -> None:
    page, _editors = _form()
    async with open_page(page) as user:
        labels = label_texts(user)
        assert "Profile Properties" in labels
        assert "No variables." in labels
        assert "Profile Variables" in labels


@pytest.mark.asyncio
async def test_a_project_explains_that_its_variables_reach_all_of_its_profiles_and_tasks() -> None:
    page, _editors = _form(ET.fromstring('<Project sr="proj0"><name>Home</name></Project>'), objprops.KIND_PROJECT)
    async with open_page(page) as user:
        assert any("available in all the profiles and tasks in this project" in text for text in label_texts(user))


@pytest.mark.asyncio
async def test_a_profile_explains_which_variable_wins_when_names_collide() -> None:
    page, _editors = _form()
    async with open_page(page) as user:
        assert any("The order of precedence is Task > Profile > Project." in text for text in label_texts(user))


@pytest.mark.asyncio
async def test_add_variable_puts_a_panel_with_every_field_and_remove_takes_it_out() -> None:
    page, _editors = _form()
    async with open_page(page) as user:
        await click(user, "Add Variable")
        labels = [e.props.get("label") for e in all_elements(user) if hasattr(e, "props")]
        for field in ("Name", "Value", "Display Name", "Prompt", "Exported Value"):
            assert field in labels
        assert "No variables." not in label_texts(user)

        await click(user, "Remove Variable")
        assert "No variables." in label_texts(user)


@pytest.mark.asyncio
async def test_two_variables_get_two_panels_and_removing_one_keeps_the_other() -> None:
    page, _editors = _form()
    async with open_page(page) as user:
        await click(user, "Add Variable")
        await click(user, "Add Variable")
        assert len([b for b in found(user, ui.button) if b.text == "Remove Variable"]) == 2
        first = [b for b in found(user, ui.button) if b.text == "Remove Variable"][0]
        await press(user, first)
        assert len([b for b in found(user, ui.button) if b.text == "Remove Variable"]) == 1


@pytest.mark.asyncio
async def test_same_as_value_follows_the_value_and_locks_the_exported_value() -> None:
    page, _editors = _form()
    async with open_page(page) as user:
        await click(user, "Add Variable")
        inputs = {e.props.get("label"): e for e in all_elements(user) if isinstance(e, ui.input)}
        same = next(e for e in all_elements(user) if isinstance(e, ui.checkbox) and e.text == "Same as Value")
        same.value = True
        inputs["Value"].value = "42"
        await asyncio.sleep(0.1)
        assert inputs["Exported Value"].value == "42"
        assert not inputs["Exported Value"].enabled
        same.value = False
        await asyncio.sleep(0.1)
        assert inputs["Exported Value"].enabled


@pytest.mark.asyncio
async def test_a_variable_the_element_already_holds_opens_with_its_name_and_value() -> None:
    element = _profile()
    props = objprops.load_properties(objprops.KIND_PROFILE, element)
    variable = objprops.add_variable(props)
    variable.find("pvn").text = "%mode"  # type: ignore[union-attr]
    ET.SubElement(variable, "pvv").text = "night"
    page, _editors = _form(element)
    async with open_page(page) as user:
        inputs = {e.props.get("label"): e for e in all_elements(user) if isinstance(e, ui.input)}
        assert inputs["Name"].value == "%mode"
        assert inputs["Value"].value == "night"
        (panel,) = [e for e in all_elements(user) if isinstance(e, ui.expansion)]
        assert panel.props["label"] == "%mode", "the panel is titled by the variable's name"
        assert panel.value is False, "a variable that already has a name opens closed"


@pytest.mark.asyncio
async def test_ok_and_cancel_hand_the_forms_own_widgets_to_the_editors_handler() -> None:
    page, editors = _form()
    async with open_page(page) as user:
        await click(user, "Cancel")
        editors.cancel_object_properties_event.assert_called_once()
        props, dialog = editors.cancel_object_properties_event.call_args.args
        assert props.kind == objprops.KIND_PROFILE

        await click(user, "Ok")
        editors.keep_object_properties_event.assert_called_once()
        props_ok, field_refs, dialog_ok, on_applied = editors.keep_object_properties_event.call_args.args
        assert props_ok is props and dialog_ok is dialog
        assert on_applied is None
        assert set(field_refs) >= {spec.key for spec in objprops.OBJECT_PROPERTIES[objprops.KIND_PROFILE]}


@pytest.mark.asyncio
async def test_a_variable_type_this_build_does_not_know_is_kept_as_an_option_not_dropped() -> None:
    element = _profile()
    props = objprops.load_properties(objprops.KIND_PROFILE, element)
    variable = objprops.add_variable(props)
    variable.find("pvt").text = "newer-type"  # type: ignore[union-attr]
    page, _editors = _form(element)
    async with open_page(page) as user:
        (select,) = [e for e in all_elements(user) if isinstance(e, ui.select) and e.props.get("label") == "Type"]
        assert select.value == "newer-type", "opening and closing the panel cannot silently retype the variable"
        assert "newer-type" in select.options
