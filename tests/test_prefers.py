"""Tasker's Preferences: the <Setting> elements the Map prints under 'Tasker Preferences'.

Run on a RunState of their own, with a stand-in for the output so what is written can be read
back.  The service table (servicec) is the real one: a test that swapped it would not notice
the day an entry in it changed shape.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from maptasker.src import prefers
from maptasker.src.primitem import RunState
from maptasker.src.runcfg import current_config
from maptasker.src.servicec import service_codes

if TYPE_CHECKING:
    import pytest


class _Output:
    """Stands in for the OutputLines the run writes to: keeps (level, text, how) for each call."""

    def __init__(self) -> None:
        self.lines: list[tuple[int, str, object]] = []

    def add_line_to_output(self, level: int, text: str, how: object) -> None:
        self.lines.append((level, text, how))

    def text(self) -> str:
        return "\n".join(text for _level, text, _how in self.lines)


def _setting(name: str, value: str, kind: str = "s") -> ET.Element:
    return ET.fromstring(f"<Setting><n>{name}</n><t>{kind}</t><v>{value}</v></Setting>")  # noqa: S314


def _state(*settings: ET.Element) -> RunState:
    state = RunState()
    state.output_lines = _Output()
    state.tasker_root_elements = {"all_services": list(settings)}
    return state


def _named(display: str) -> str:
    """The first service code whose display name is this one."""
    return next(code for code, entry in service_codes.items() if entry["display"] == display)


def _process(name: str, value: str) -> list:
    lines: list = []
    prefers.process_service(name, value, lines)
    return lines


def test_a_preference_is_filed_under_its_number_with_its_name_and_value() -> None:
    """The number is what the list is sorted on, so the display order is Tasker's own."""
    [[number, line]] = _process("anm", "true")
    assert number == service_codes["anm"]["num"]
    assert "Animations" in line
    assert "true" in line


def test_a_choice_is_shown_as_the_item_chosen_not_its_index() -> None:
    """themeMaterial stores 3; the person chose 'Light'."""
    [[_, line]] = _process("themeMaterial", "3")
    assert "Light" in line


def test_the_default_notification_icon_reads_default() -> None:
    """Tasker writes 'cust_notification' for it, which means nothing to a reader."""
    [[_, line]] = _process("anm", "cust_notification")
    assert "Default" in line
    assert "cust_notification" not in line


def test_the_google_api_key_is_never_printed() -> None:
    """It is a credential, and a Map is a document people share."""
    [[_, line]] = _process("kcph", "AIzaSySecretSecretSecret")
    assert "Hidden" in line
    assert "Secret" not in line


def test_an_unnamed_preference_is_labelled_unknown_with_its_code() -> None:
    """The code is all there is to go on, so it is printed."""
    [[_, line]] = _process("kit", "x")
    assert "kit: Unknown" in line


def test_accessibility_packages_are_listed_one_per_line() -> None:
    """The value is JSON-ish text; each package name in it gets a line of its own."""
    value = '[{"packageName":"com.one"},{"packageName":"com.two"}]'
    [[_, line]] = _process("PREF_KEEP_ACCESSIBILITY_SERVICES_RUNNING", value)
    assert line.count("<br>") == 2
    assert "com.one" in line
    assert "com.two" in line


def test_a_file_without_preferences_says_so_once() -> None:
    """A single-object export has none, and an empty list would look like a bug."""
    lines: list = []
    prefers.process_preferences(lines, current_config(_state()), state=_state())
    [[_, line]] = lines
    assert "Preferences not found in this XML file" in line


def test_only_the_preferences_it_knows_are_listed_unless_debugging() -> None:
    """An unmapped one is noise for a reader, and a clue for the developer -- so debug only."""
    state = _state(_setting("anm", "true"), _setting("zzNotMapped", "7"))
    quiet: list = []
    prefers.process_preferences(quiet, current_config(state), state=state)
    assert len(quiet) == 1

    loud: list = []
    config = current_config(state).with_changes(debug=True)
    prefers.process_preferences(loud, config, state=state)
    mentions = [line for _num, line in loud if "zzNotMapped" in line]
    assert len(mentions) == 1
    assert "type:s" in mentions[0]
    assert "value:7" in mentions[0]


def test_a_setting_missing_a_part_ends_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """<Setting> without its <v> means the backup is damaged; guessing would hide that."""
    seen = {}
    monkeypatch.setattr(prefers, "error_handler", lambda message, code, state: seen.update(message=message, code=code))
    broken = ET.fromstring("<Setting><n>anm</n><t>s</t></Setting>")  # noqa: S314
    state = _state(broken)
    prefers.process_preferences([], current_config(state), state=state)
    assert seen["code"] == 3
    assert "corrupt" in seen["message"]


def test_get_preferences_prints_each_section_heading_once_in_tasker_order() -> None:
    """Sorted by number, with a heading where the section changes."""
    state = _state(_setting("tpEn", "true"), _setting("anm", "true"), _setting("sHapt", "false"))
    prefers.get_preferences(current_config(state), state=state)
    text = state.output_lines.text()
    assert text.count("Section: UI > General") == 1
    assert text.index("Animations") < text.index("Haptic Feedback") < text.index("Tips")
    assert state.output_lines.lines[0][1].startswith("Tasker Preferences")
