"""Unnamed Projects, Profiles and Tasks in the Map's directory and its single-Task path.

The 'List Unnamed Items' checkbox is about the four 'Specific Name' pulldowns -- what they offer to choose from.  The
views are not a list to choose from, so what they hold does not depend on it.
"""

from __future__ import annotations

from typing import Any

import pytest
from maptasker.src.core import dirout
from maptasker.src.core.initparg import initialize_runtime_arguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.runcfg import current_config
from maptasker.src.mapgen import projects

from tests.doubles import fake_state

_MADE_UP = "Flash Text=hi.99 (Unnamed)"


@pytest.fixture(autouse=True)
def _directory_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PrimeItems, "directory_items", {"current_item": "", "projects": [], "profiles": [], "tasks": [], "scenes": []}
    )


@pytest.mark.parametrize("checkbox", [True, False])
def test_an_unnamed_task_is_in_the_directory_whatever_the_checkbox_says(checkbox: bool) -> None:
    arguments = initialize_runtime_arguments()
    arguments.update({"list_unnamed_items": checkbox})
    PrimeItems.program_arguments = arguments

    dirout.add_directory_item("tasks", _MADE_UP, state=PrimeItems)

    assert [name for _, name in PrimeItems.directory_items["tasks"]] == [_MADE_UP]


def test_an_unnamed_profile_is_in_the_directory_too() -> None:
    PrimeItems.program_arguments = initialize_runtime_arguments()

    dirout.add_directory_item("profiles", "Time 8:00 (Unnamed)", state=PrimeItems)

    assert [name for _, name in PrimeItems.directory_items["profiles"]] == ["Time 8:00 (Unnamed)"]


def test_the_bare_placeholder_is_still_no_entry_at_all() -> None:
    PrimeItems.program_arguments = initialize_runtime_arguments()

    dirout.add_directory_item("tasks", "Unnamed", state=PrimeItems)

    assert PrimeItems.directory_items["tasks"] == []


def test_a_name_is_entered_in_the_directory_once() -> None:
    PrimeItems.program_arguments = initialize_runtime_arguments()

    dirout.add_directory_item("tasks", _MADE_UP, state=PrimeItems)
    dirout.add_directory_item("tasks", _MADE_UP, state=PrimeItems)

    assert len(PrimeItems.directory_items["tasks"]) == 1


@pytest.mark.parametrize("checkbox", [True, False])
def test_a_single_unnamed_task_is_mapped_whatever_the_checkbox_says(
    monkeypatch: pytest.MonkeyPatch, checkbox: bool
) -> None:
    mapped: list[str] = []
    monkeypatch.setattr(projects, "_output_single_unnamed_task", lambda *_args, **_kwargs: mapped.append("unnamed"))
    arguments = initialize_runtime_arguments()
    arguments.update({"single_task_name": _MADE_UP, "list_unnamed_items": checkbox})
    PrimeItems.program_arguments = arguments
    state: Any = fake_state(
        tasker_root_elements={
            "all_tasks_by_name": {_MADE_UP: {}},
            "all_tasks": {},
            "all_projects": {},
            "all_profiles": {},
            "all_scenes": {},
        },
        program_arguments=arguments,
    )

    projects.process_projects_and_their_profiles([], [], current_config(state=PrimeItems), state=state)

    assert mapped == ["unnamed"]


# ##################################################################################
# The Tree
# ##################################################################################
@pytest.mark.usefixtures("_runtime")
@pytest.mark.parametrize("checkbox", [True, False])
def test_the_tree_lists_a_profiles_unnamed_task_whatever_the_checkbox_says(checkbox: bool) -> None:
    """The checkbox is for the pulldowns.  The Tree is built from the same Profiles and Tasks and holds them all."""
    from maptasker.src.gui import guiutils

    PrimeItems.program_arguments.list_unnamed_items = checkbox
    tables = PrimeItems.tasker_root_elements

    rows = guiutils.build_profiles(tables, list(tables["all_profiles"]), "Pack", state=PrimeItems)

    by_profile = {row["name"]: row["children"] for row in rows}
    assert any("(Unnamed)" in task for task in by_profile["Profile: Dawn"])
