"""maptext: the text a person reads, pulled into a table, translated, and put back.

Run on the synthetic backup the fuzz tests use (Legacy Scenes with a list in one, Flash actions in the Tasks) and on a Version 2
Scene built here, since the synthetic backup has none and its text lives in a gzipped JSON blob.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from maptasker.src import clireports
from maptasker.src.core import scenelayout
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import scenemodel, sessundo
from maptasker.src.mapops import mapswap, maptext

from tests.test_fuzz_backup import _SYNTHETIC
from tests.test_fuzz_roundtrip import a_loaded_backup

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def loaded() -> Iterator[Path]:
    """The synthetic backup, loaded; the folder it was written in."""
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        sessundo.clear(PrimeItems)
        yield path


def _add_v2_scene(name: str = "Panel") -> ET.Element:
    """A Version 2 Scene with a Text, a Button, a TextInput and a Text that is only a variable."""
    scene = ET.Element("Scene", {"sr": f"scene{name}"})
    ET.SubElement(scene, "nme").text = name
    layout = {
        "root": {
            "type": "Column",
            "children": [
                {"type": "Text", "id": "Title", "text": "Welcome back"},
                {"type": "Button", "id": "Go", "text": "Go %where now"},
                {"type": "TextInput", "id": "Who", "label": "Your name"},
                {"type": "Text", "id": "Echo", "text": "%echo"},
            ],
        }
    }
    scenelayout.encode_v2_layout(scene, layout)
    PrimeItems.tasker_root_elements["all_scenes"][name] = {"xml": scene, "name": name}
    return scene


def _by_text(items: list[maptext.TextItem]) -> dict[str, maptext.TextItem]:
    return {item.text: item for item in items}


# ##################################################################################
# Finding the text
# ##################################################################################
def test_the_text_of_tasks_and_legacy_scenes_is_found(loaded: Path) -> None:
    found = _by_text(maptext.extract(PrimeItems))

    assert found["Time to check your reminders"].kind == "Flash Text"
    assert found["Done"].kind == "List Item Label"
    assert found["Reminder List"].kind == "Properties Title"
    assert found["Today,Upcoming"].kind == "Properties Tab Labels"
    assert found["Chores done"].key.startswith("scene:Chores#act")  # the Flash a list item carries


def test_names_are_never_text(loaded: Path) -> None:
    """Other places refer to a Task or a Scene by its name; a translated one would break every one of them."""
    texts = {item.text for item in maptext.extract(PrimeItems)}

    assert "Remind Me" not in texts
    assert "Chores" not in {item.text for item in maptext.extract(PrimeItems) if item.kind != "Properties Title"}


def test_a_string_of_only_variables_has_nothing_to_translate(loaded: Path) -> None:
    _add_v2_scene()

    texts = {item.text for item in maptext.extract(PrimeItems)}

    assert "%echo" not in texts
    assert "Go %where now" in texts


def test_a_version_2_scenes_text_is_found_inside_its_layout(loaded: Path) -> None:
    _add_v2_scene()

    found = {item.text: item for item in maptext.extract(PrimeItems) if item.key.startswith("scene:Panel")}

    assert set(found) == {"Welcome back", "Go %where now", "Your name"}
    assert found["Your name"].kind == "TextInput Label"


def test_one_projects_text_only(loaded: Path) -> None:
    every = maptext.extract(PrimeItems)
    reminders = maptext.extract(PrimeItems, project="Reminders")

    assert 0 < len(reminders) < len(every)
    assert {item.project for item in reminders} == {"Reminders"}


# ##################################################################################
# The table
# ##################################################################################
@pytest.mark.parametrize("file_format", maptext.FORMATS)
def test_a_table_reads_back_as_it_was_written(loaded: Path, tmp_path: Path, file_format: str) -> None:
    items = maptext.extract(PrimeItems)
    path = tmp_path / f"table.{file_format}"

    assert maptext.write_table(items, path, file_format) == len(items)
    rows = maptext.read_table(path)

    assert [(row.key, row.text, row.translation) for row in rows] == [(item.key, item.text, "") for item in items]


def test_a_spreadsheets_line_ends_and_mark_are_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "t.csv"
    path.write_bytes('﻿key,text,translation\r\nk1,"two\r\nlines","dos\r\nlíneas"\r\n'.encode())

    (row,) = maptext.read_table(path)

    assert (row.text, row.translation) == ("two\nlines", "dos\nlíneas")


@pytest.mark.parametrize(
    ("content", "complaint"),
    [("key,text\nk,t\n", "no translation column"), ("[1, 2", "not valid JSON"), ('{"a": 1}', "list of rows")],
)
def test_a_table_that_cannot_be_read_says_why(tmp_path: Path, content: str, complaint: str) -> None:
    path = tmp_path / "t.csv"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(maptext.TextTableError, match=complaint):
        maptext.read_table(path)


def test_a_missing_table_says_so(tmp_path: Path) -> None:
    with pytest.raises(maptext.TextTableError, match="could not be read"):
        maptext.read_table(tmp_path / "nope.csv")


# ##################################################################################
# Putting it back
# ##################################################################################
def _translate(translations: dict[str, str], project: str = "") -> maptext.Plan:
    rows = [
        maptext.Row(item.key, item.owner, item.text, translations.get(item.text, ""))
        for item in maptext.extract(PrimeItems, project=project)
    ]
    return maptext.plan_apply(rows, PrimeItems, project=project)


def test_translations_are_written_where_the_text_was(loaded: Path) -> None:
    plan = _translate(
        {"Time to check your reminders": "Es hora de revisar", "Done": "Hecho", "Chores done": "Hecho todo"}
    )

    changed, errors = mapswap.apply(plan, PrimeItems)

    assert (changed, errors) == (3, [])
    texts = {item.text for item in maptext.extract(PrimeItems)}
    assert {"Es hora de revisar", "Hecho", "Hecho todo"} <= texts
    assert not {"Time to check your reminders", "Done"} & texts


def test_apply_can_be_undone_as_one_step(loaded: Path) -> None:
    before = {item.key: item.text for item in maptext.extract(PrimeItems)}
    plan = _translate({"Done": "Hecho", "Snooze": "Posponer"})

    mapswap.apply(plan, PrimeItems)
    assert sessundo.undo(PrimeItems)[0]

    assert {item.key: item.text for item in maptext.extract(PrimeItems)} == before


def test_a_version_2_scenes_text_is_rewritten_inside_its_layout(loaded: Path) -> None:
    scene = _add_v2_scene()
    plan = _translate({"Welcome back": "Bienvenido", "Go %where now": "Ve a %where ahora"})

    changed, errors = mapswap.apply(plan, PrimeItems)

    assert (changed, errors) == (2, [])
    layout = scenelayout.decode_v2_layout(scene)
    assert layout is not None
    texts = [child.get("text") for child in layout["root"]["children"]]
    assert texts == ["Bienvenido", "Ve a %where ahora", None, "%echo"]
    assert scenemodel.is_v2_scene(scene)


def test_a_translation_that_changes_the_variables_is_left_alone_and_said_so(loaded: Path) -> None:
    plan = _translate({"Showing %tap_label": "Mostrando %otra"})

    assert plan.changes == []
    (skip,) = plan.skips
    assert skip.reason == "variables"
    assert "%otra" in skip.explanation
    assert "%tap_label" in skip.explanation


def test_a_row_made_from_text_that_has_since_changed_is_left_alone(loaded: Path) -> None:
    item = _by_text(maptext.extract(PrimeItems))["Nice work"]
    item.site.element.text = "Nice work indeed"
    plan = maptext.plan_apply([maptext.Row(item.key, item.owner, "Nice work", "Buen trabajo")], PrimeItems)

    assert plan.changes == []
    assert plan.skips[0].reason == "changed"
    assert "Nice work indeed" in plan.skips[0].explanation


def test_a_row_for_something_not_in_this_configuration_is_reported(loaded: Path) -> None:
    plan = maptext.plan_apply([maptext.Row("task:9999#act1.arg0", "Task 'Gone'", "Hi", "Hola")], PrimeItems)

    assert plan.changes == []
    assert plan.skips[0].reason == "unknown"


def test_rows_with_no_translation_or_the_same_text_are_not_changes(loaded: Path) -> None:
    item = _by_text(maptext.extract(PrimeItems))["Nice work"]
    rows = [
        maptext.Row(item.key, item.owner, "Nice work", ""),
        maptext.Row(item.key, item.owner, "Nice work", "Nice work"),
    ]

    plan = maptext.plan_apply(rows, PrimeItems)

    assert plan.changes == []
    assert plan.skips == []


def test_a_project_scoped_apply_leaves_the_others_alone(loaded: Path) -> None:
    plan = _translate({"Nice work": "Buen trabajo", "Time to check your reminders": "Revisa"}, project="Reminders")
    mapswap.apply(plan, PrimeItems)

    texts = {item.text for item in maptext.extract(PrimeItems)}
    assert "Revisa" in texts
    assert "Nice work" in texts  # in the Household Project


# ##################################################################################
# From the command line
# ##################################################################################
def _run(arguments: list[str], tmp_path: Path) -> int:
    return clireports.run([*arguments, "-outdir", str(tmp_path)], state=PrimeItems)


def test_the_command_line_writes_a_table_and_puts_a_translation_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_bytes(_SYNTHETIC)

    assert _run(["-text", "export", "-file", str(backup)], tmp_path) == clireports.EXIT_OK
    table = Path(capsys.readouterr().out.strip())
    assert table.name == "MapTasker_Text.csv"

    rows = maptext.read_table(table)
    (done,) = [row for row in rows if row.text == "Nice work"]
    translated = tmp_path / "translated.csv"
    translated.write_text(f"key,text,translation\n{done.key},Nice work,Buen trabajo\n", encoding="utf-8")

    assert _run(["-text", "apply", "-file", str(backup), "-table", str(translated)], tmp_path) == clireports.EXIT_OK
    written = Path(capsys.readouterr().out.strip())
    assert written.name == "MapTasker_Text_Applied.xml"
    assert "Buen trabajo" in written.read_text(encoding="utf-8")
    assert "Nice work" in backup.read_text(encoding="utf-8")  # the backup itself is never touched


def test_the_command_line_exits_with_found_when_a_row_was_left_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_bytes(_SYNTHETIC)
    table = tmp_path / "t.csv"
    table.write_text("key,text,translation\ntask:9999#act1.arg0,Hi,Hola\n", encoding="utf-8")

    assert _run(["-text", "apply", "-file", str(backup), "-table", str(table)], tmp_path) == clireports.EXIT_FOUND
    assert "left alone" in capsys.readouterr().err


def test_a_project_apply_writes_that_project_to_share(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_bytes(_SYNTHETIC)
    assert _run(["-text", "export", "-file", str(backup), "-project", "Reminders"], tmp_path) == clireports.EXIT_OK
    rows = maptext.read_table(Path(capsys.readouterr().out.strip()))
    (remind,) = [row for row in rows if row.text == "Time to check your reminders"]
    table = tmp_path / "t.csv"
    table.write_text(f"key,text,translation\n{remind.key},{remind.text},Revisa tus recordatorios\n", encoding="utf-8")

    assert _run(["-text", "apply", "-file", str(backup), "-table", str(table), "-project", "Reminders"], tmp_path) == 0
    written = Path(capsys.readouterr().out.strip())

    assert written.name == "MapTasker_Text_Applied.prj.xml"
    assert "Revisa tus recordatorios" in written.read_text(encoding="utf-8")


def test_apply_without_a_table_or_for_an_unknown_project_is_a_bad_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup.xml"
    backup.write_bytes(_SYNTHETIC)

    assert _run(["-text", "apply", "-file", str(backup)], tmp_path) == clireports.EXIT_BAD_OPTION
    assert _run(["-text", "export", "-file", str(backup), "-project", "Nope"], tmp_path) == clireports.EXIT_BAD_OPTION
    assert "There is no Project named 'Nope'" in capsys.readouterr().err


def test_a_command_line_that_wants_no_text_table_does_not_load_the_code_for_one() -> None:
    """The start-up of every command line goes through clireports, so the table's code is imported when asked for."""
    program = (
        "import sys, maptasker.src.clireports;"
        "sys.exit(any(name.startswith('maptasker.src.mapops.maptext') for name in sys.modules))"
    )

    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0


def test_every_key_finds_exactly_one_field_even_where_a_scene_holds_a_sub_scene(loaded: Path) -> None:
    """A Scene with a sub-Scene has two Properties elements and the Map anchors neither's inside part (found on a real
    backup, where two texts shared a key and one translation went to the wrong place)."""
    scene = PrimeItems.tasker_root_elements["all_scenes"]["Chores"]["xml"]
    properties = scene.find("PropertiesElement")
    assert properties is not None
    clone = ET.fromstring(ET.tostring(properties))
    clone.find("Str[@sr='arg4']").text = "Nested title"  # type: ignore[union-attr]
    scene.append(clone)

    items = maptext.extract(PrimeItems)

    assert len({item.key for item in items}) == len(items)
    assert "Nested title" in {item.text for item in items}
