"""Load, edit, save, reload: the configuration that comes back is the one that went out.

Every editor changes the loaded configuration in memory, and "Save To Current File" renders that configuration as a
file.  Whatever an editor did, the file has to read back as the same configuration, and writing it again has to give
the same file.  Example tests check the edits somebody thought of; these draw a sequence of the real editor
operations, in any order, on the synthetic backup and on spoiled-but-loadable ones, and compare what is in memory
with what a fresh load of the saved file holds.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from hypothesis import event, given
from hypothesis import strategies as st
from maptasker.src.core import maputil2
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.edit import profedit, projedit, taskedit, taskedit_save
from maptasker.src.mapgen import taskerd

from tests.fuzzing import fuzz
from tests.test_fuzz_backup import _SYNTHETIC, a_scratch_run, backups, prime_a_run

if TYPE_CHECKING:
    from collections.abc import Iterator
    from xml.etree.ElementTree import Element

_TABLES = ("all_projects", "all_profiles", "all_tasks", "all_scenes")
FLASH = "548t"  # an action that needs nothing from a device

# Names as people type them: accents, CJK, emoji, and the characters XML has to escape.
NAMES = st.text(alphabet="abcXYZ 019é日本🙂<>&\"'-_", min_size=1, max_size=12)


# ##################################################################################
# The configuration, as something two loads can be compared by
# ##################################################################################
def shape(element: Element) -> tuple:
    """An element with its indentation removed and nothing else: a leaf's text is compared exactly, spaces and all."""
    children = tuple(shape(child) for child in element)
    return (element.tag, tuple(sorted(element.attrib.items())), None if children else element.text or "", children)


def configuration() -> dict[str, dict[str, tuple]]:
    """Every Project, Profile, Task and Scene the run holds, by the key it is held under."""
    return {
        table: {
            key: (entry["name"], shape(entry["xml"])) for key, entry in PrimeItems.tasker_root_elements[table].items()
        }
        for table in _TABLES
    }


def load(path: Path) -> None:
    """What opening a file does, as the fuzz of the loader does it."""
    prime_a_run()
    with path.open(encoding="utf-8", errors="replace") as opened:
        PrimeItems.file_to_get = opened
        taskerd.get_the_xml_data(state=PrimeItems)


@contextlib.contextmanager
def a_loaded_backup(data: bytes) -> Iterator[Path | None]:
    """The backup as a file in a scratch folder, loaded; None for one the loader refuses, which has no round trip."""
    with a_scratch_run(data) as path:
        try:
            load(path)
        except MapTaskerError:
            event("refused")
            yield None
        else:
            yield path


def saved_and_reloaded(folder: Path) -> str:
    """Render the configuration, load what was rendered as a new run, and return the text."""
    text = maputil2.render_full_backup_xml(state=PrimeItems)
    saved = folder / "saved.xml"
    saved.write_text(text, encoding="utf-8")
    PrimeItemsReset()
    load(saved)
    return text


# ##################################################################################
# The editors, as the dialogs drive them
# ##################################################################################
def _names(table: str) -> list[str]:
    return sorted(entry["name"] for entry in PrimeItems.tasker_root_elements[table].values())


def _pick(names: list[str], index: int) -> str | None:
    return names[index % len(names)] if names else None


def rename_task(index: int, name: str) -> None:
    old = _pick(_names("all_tasks"), index)
    edited = taskedit.load_task_for_edit(old, state=PrimeItems) if old else None
    if edited and not taskedit.apply_task_rename(edited, name, state=PrimeItems):
        taskedit.rename_task_in_live_tree(edited, state=PrimeItems)


def rename_project(index: int, name: str) -> None:
    old = _pick(_names("all_projects"), index)
    edited = projedit.load_project_for_edit(old, state=PrimeItems) if old else None
    if old and edited and not projedit.apply_edits_to_project(edited, name, state=PrimeItems):
        projedit.rename_project_in_live_tree(old, edited, state=PrimeItems)


def rename_profile(index: int, name: str) -> None:
    old = _pick(_names("all_profiles"), index)
    edited = profedit.load_profile_for_edit(old, state=PrimeItems) if old else None
    if edited and not profedit.apply_profile_rename(edited, name, state=PrimeItems):
        profedit.rename_profile_in_live_tree(edited, state=PrimeItems)


def delete_task(index: int, _name: str) -> None:
    if old := _pick(_names("all_tasks"), index):
        taskedit_save.delete_task(old, state=PrimeItems)


def delete_profile(index: int, _name: str) -> None:
    if old := _pick(_names("all_profiles"), index):
        profedit.delete_profile(old, state=PrimeItems)


def add_task(index: int, name: str) -> None:
    if not name.strip():
        return  # The dialog creates the Task unnamed and refuses to keep it until it has a name.
    edited = taskedit.create_new_task(name, "100", state=PrimeItems)
    if isinstance(edited, str) or taskedit.task_name_exists(name, state=PrimeItems):
        return
    if index % 2:
        taskedit.add_action_to_task(edited, FLASH, state=PrimeItems)
    taskedit_save.register_new_task(edited, name.strip(), state=PrimeItems)
    if project := _pick(_names("all_projects"), index):
        profedit.add_task_to_project(edited.task_id, project, state=PrimeItems)


def add_project(_index: int, name: str) -> None:
    if not name.strip():
        return
    edited = projedit.create_new_project(name, state=PrimeItems)
    if not isinstance(edited, str) and not projedit.project_name_exists(name, state=PrimeItems):
        projedit.register_new_project(edited, state=PrimeItems)


def switch_project(index: int, _name: str) -> None:
    old = _pick(_names("all_projects"), index)
    edited = projedit.load_project_for_edit(old, state=PrimeItems) if old else None
    if edited:
        projedit.set_project_enabled(edited, not projedit.is_project_enabled(edited), state=PrimeItems)


EDITS = {
    function.__name__: function
    for function in (
        rename_task,
        rename_project,
        rename_profile,
        delete_task,
        delete_profile,
        add_task,
        add_project,
        switch_project,
    )
}


@st.composite
def edit_sequences(draw: st.DrawFn) -> list[tuple[str, int, str]]:
    names = sorted(EDITS)
    return draw(
        st.lists(
            st.tuples(st.sampled_from(names), st.integers(min_value=0, max_value=50), NAMES),
            min_size=1,
            max_size=8,
        )
    )


def _same_after_a_save(folder: Path) -> None:
    """The property: what a load of the saved file holds is what was in memory, and saving again changes nothing."""
    before = configuration()
    text = saved_and_reloaded(folder)

    after = configuration()
    for table in _TABLES:
        assert after[table].keys() == before[table].keys(), f"{table} came back with different members"
        for key in before[table]:
            assert after[table][key] == before[table][key], f"{table} {key!r} came back changed"
    assert maputil2.render_full_backup_xml(state=PrimeItems) == text, "saving the reloaded file wrote something else"


# ##################################################################################
# The properties
# ##################################################################################
@fuzz(150)
@given(data=backups())
def test_a_backup_that_loads_saves_and_reloads_as_itself(data: bytes) -> None:
    with a_loaded_backup(data) as path:
        if path:
            _same_after_a_save(path.parent)


@fuzz(150)
@given(edits=edit_sequences())
def test_edited_configuration_saves_and_reloads_as_itself(edits: list[tuple[str, int, str]]) -> None:
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        for which, index, name in edits:
            EDITS[which](index, name)
        _same_after_a_save(path.parent)


@pytest.mark.parametrize("which", sorted(EDITS))
def test_each_edit_alone_saves_and_reloads_as_itself(which: str) -> None:
    """The cases the draw has to hit, stated one at a time so a failure names the editor."""
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        EDITS[which](0, "Edited")
        _same_after_a_save(path.parent)


@fuzz(150)
@given(
    edits=st.lists(
        st.tuples(
            st.sampled_from(["rename_task", "rename_project", "rename_profile", "add_task", "add_project"]),
            st.integers(min_value=0, max_value=50),
            st.text(alphabet=st.characters(codec="utf-8"), min_size=1, max_size=8),
        ),
        min_size=1,
        max_size=4,
    )
)
def test_any_name_an_editor_accepts_saves_and_reloads_as_itself(edits: list[tuple[str, int, str]]) -> None:
    """Whatever a name is made of -- control characters, a carriage return, a lone mark -- it is refused or it survives."""
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        for which, index, name in edits:
            EDITS[which](index, name)
        _same_after_a_save(path.parent)


# ##################################################################################
# What the properties found, stated as examples
# ##################################################################################
def test_saving_a_project_without_an_id_does_not_write_it_again() -> None:
    """The synthetic backup's Projects have no <id>; each save used to keep the tree's copy and append another."""
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        first = maputil2.render_full_backup_xml(state=PrimeItems)
        _same_after_a_save(path.parent)

    assert first.count("<Project ") == _SYNTHETIC.decode().count("<Project ") == 2


def test_saving_a_task_without_an_id_does_not_write_it_again() -> None:
    data = _SYNTHETIC.replace(b"<tids>104,105,107</tids>", b"<tids>104,105,107</tids>").replace(
        b'\t<Task sr="task101">', b'\t<Task sr="task900">\n\t\t<nme>No id</nme>\n\t</Task>\n\t<Task sr="task101">', 1
    )
    with a_loaded_backup(data) as path:
        assert path
        _same_after_a_save(path.parent)
        assert maputil2.render_full_backup_xml(state=PrimeItems).count("No id") == 1


@pytest.mark.parametrize("name", ["tab\x1fcontrol", "null\x00byte", "carriage\rreturn", "￾end"])
def test_a_name_a_backup_cannot_hold_is_refused_by_every_editor(name: str) -> None:
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        task = taskedit.load_task_for_edit(_names("all_tasks")[0], state=PrimeItems)
        project = projedit.load_project_for_edit(_names("all_projects")[0], state=PrimeItems)
        profile = profedit.load_profile_for_edit(_names("all_profiles")[0], state=PrimeItems)
        assert task
        assert project
        assert profile

        assert taskedit.apply_task_rename(task, name, state=PrimeItems)
        assert projedit.apply_edits_to_project(project, name, state=PrimeItems)
        assert profedit.apply_profile_rename(profile, name, state=PrimeItems)
        assert isinstance(taskedit.create_new_task(name, "100", state=PrimeItems), str)
        assert isinstance(projedit.create_new_project(name, state=PrimeItems), str)
        assert isinstance(profedit.create_new_profile(name, state=PrimeItems), str)
        _same_after_a_save(path.parent)
