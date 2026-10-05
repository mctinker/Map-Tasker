"""The two Scene designers behind one interface (guiwins_designers).

What a Scene dialog relies on is small: given a Scene it gets a designer for that Scene's kind, the
designer says what the Preview button promises, and it mounts everything below the Scene's name.
So that is what is asserted -- which designer a kind gets, what each puts into the dialog and into
field_refs (the Legacy size fields; none for Version 2, whose layout has no canvas to size), and
that a layout that will not decode is reported and left alone.  The designers themselves are far
larger and are exercised by test_scene_properties and the window tests; here their builders are
replaced so that only the interface is under test.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from nicegui import core, ui
from nicegui.testing.user_simulation import user_simulation

from maptasker.src import guiwins_designer_legacy, guiwins_designer_v2, guiwins_designers, objprops, sceneedit
from maptasker.src.primitem import RunState

_LEGACY = ET.fromstring(  # noqa: S314  (fixture text, defined in this file)
    '<Scene sr="sceneOld"><nme>Old</nme><widthPort>640</widthPort><heightPort>480</heightPort>'
    "<widthLand>-1</widthLand></Scene>",
)
_LAYOUT = {"name": "New", "root": {"type": "Column", "id": "root", "children": []}}

_built: dict = {}


def _v2_scene(*, decodable: bool = True) -> ET.Element:
    scene = ET.fromstring('<Scene sr="sceneNew"><nme>New</nme></Scene>')  # noqa: S314
    if decodable:
        sceneedit.encode_v2_layout(scene, _LAYOUT)
    else:
        ET.SubElement(scene, "lj").text = "not a layout"
    return scene


def _page() -> None:
    """The dialog body: whatever the designer puts below the name, on a page of its own."""
    designer = guiwins_designers.designer_for(_built["scene"])
    _built["designer"] = designer
    designer.build_body(
        SimpleNamespace(),
        SimpleNamespace(scene_element=_built["scene"]),
        _built["field_refs"],
        _built.get("dialog"),
        RunState(),
    )


async def _mount(scene: ET.Element) -> list[str]:
    """Mount the designer for this Scene and return the text of every label it drew."""
    _built.clear()
    _built.update(scene=scene, field_refs={})
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            try:
                return [element.text for element in user.find(kind=ui.label).elements]
            except AssertionError:  # user.find insists on at least one: a page with no labels has none
                return []
    finally:
        if core.app.is_started:
            await core.app.stop()


@pytest.fixture
def builders(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """The designers' real builders replaced, recording what each was handed."""
    calls: dict[str, list] = {"legacy": [], "v2": [], "properties": []}
    monkeypatch.setattr(guiwins_designer_legacy, "_build_legacy_designer", lambda *args: calls["legacy"].append(args))
    monkeypatch.setattr(
        guiwins_designer_v2,
        "_build_v2_designer",
        lambda *args, **kwargs: calls["v2"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        guiwins_designer_legacy,
        "_build_properties_button",
        lambda *args, **kwargs: calls["properties"].append((args, kwargs)),
    )
    return calls


# ##################################################################################
# Which designer
# ##################################################################################
def test_each_kind_of_scene_gets_the_designer_for_that_kind() -> None:
    """The one place that maps a kind to its designer."""
    assert isinstance(guiwins_designers.designer_for(_LEGACY), guiwins_designer_legacy.LegacyDesigner)
    assert isinstance(guiwins_designers.designer_for(_v2_scene()), guiwins_designer_v2.V2Designer)


def test_a_version_2_scene_is_a_version_2_scene_even_if_its_layout_is_broken() -> None:
    """The kind is decided by <lj> being there, so a corrupt layout still gets the Version 2 designer to say so."""
    assert isinstance(guiwins_designers.designer_for(_v2_scene(decodable=False)), guiwins_designer_v2.V2Designer)


def test_the_preview_says_what_it_draws_from_for_each_kind() -> None:
    """A Legacy Scene previews at the size typed in; a Version 2 Scene has none, so it lays out in a screen picked."""
    legacy = guiwins_designers.designer_for(_LEGACY).preview_tooltip
    v2 = guiwins_designers.designer_for(_v2_scene()).preview_tooltip
    assert "at the size typed above" in legacy
    assert "has no size of its own" in v2
    assert "has no size of its own" not in legacy
    assert "at the size typed above" not in v2


# ##################################################################################
# Mounting
# ##################################################################################
@pytest.mark.asyncio
async def test_a_legacy_scene_gets_its_size_fields_the_properties_button_and_the_canvas_designer(
    builders: dict[str, list],
) -> None:
    """Four size inputs carrying the Scene's own values, the Scene Properties button, then the canvas."""
    labels = await _mount(_LEGACY)

    assert set(_built["field_refs"]) == {key for key, _label in sceneedit.SCENE_DIMENSION_FIELDS}
    values = {key: field.value for key, field in _built["field_refs"].items()}
    assert values == {"widthPort": "640", "heightPort": "480", "widthLand": "-1", "heightLand": "-1"}
    assert "-1 means this orientation has no layout of its own." in labels

    [(args, kwargs)] = builders["properties"]
    assert args[1] == objprops.KIND_SCENE
    assert args[2] is _LEGACY
    assert callable(kwargs["opener"])
    assert len(builders["legacy"]) == 1
    assert builders["v2"] == []


@pytest.mark.asyncio
async def test_a_version_2_scene_gets_the_component_designer_and_no_size_fields(builders: dict[str, list]) -> None:
    """No size fields in field_refs is how the save path knows there is nothing to validate or write."""
    await _mount(_v2_scene())

    assert _built["field_refs"] == {}
    [(args, kwargs)] = builders["v2"]
    assert args[2] == _LAYOUT
    assert "state" in kwargs
    assert builders["legacy"] == []
    assert builders["properties"] == []


@pytest.mark.asyncio
async def test_a_version_2_layout_that_will_not_decode_is_reported_and_left_exactly_as_it_is(
    builders: dict[str, list],
) -> None:
    """Editing a layout that cannot be read would risk overwriting what cannot be seen."""
    labels = await _mount(_v2_scene(decodable=False))

    assert "This Scene's Version 2 layout could not be read, and will be left exactly as it is." in labels
    assert builders["v2"] == []
