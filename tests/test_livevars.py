"""Live variable values: the phone's answer beside the file's.

The Variable Cross-Reference can say a global is read but never set, or set but never read,
only about THIS FILE.  Whether that is a bug depends on whether the variable exists on the
phone, which is what these cases pin down -- along with the parts that must not change: a
report built with no device is the report it always was, and a failed read is never taken for
'the phone has no globals'.
"""

from __future__ import annotations

import base64
import json
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import livevars, taskerd, varxref
from maptasker.src.initparg import ProgramArguments
from maptasker.src.primitem import PrimeItems

# %Orphan is read and never set; %Dead is set and never read; %Both is set and read; %Kept is
# declared in the Variables tab, so it is neither.
_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="var0">
    <nme>%Kept</nme>
    <val>from the file</val>
  </Variable>
  <Task sr="task1">
    <id>1</id>
    <nme>Writer</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Dead</Str>
      <Str sr="arg1" ve="3">1</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Both</Str>
      <Str sr="arg1" ve="3">1</Str>
    </Action>
  </Task>
  <Task sr="task2">
    <id>2</id>
    <nme>Reader</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">%Orphan and %Both and %Kept</Str>
    </Action>
  </Task>
</TaskerData>
"""


def _encoded(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


@pytest.fixture(autouse=True)
def _loaded() -> None:
    root = ET.fromstring(_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100)
    tables = {
        "all_projects": {},
        "all_profiles": {},
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": {},
        "all_services": [],
        "all_profiles_by_name": {},
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items()
    }
    PrimeItems.tasker_root_elements = tables


def _live(**values: str) -> livevars.LiveValues:
    return livevars.LiveValues(
        address="192.168.0.210:1821", values={f"%{name}": value for name, value in values.items()}
    )


def _by_subject(live: livevars.LiveValues | None) -> dict[str, varxref.Suspect]:
    found = varxref.suspects(varxref.build_index(state=PrimeItems), live)
    return {suspect.subject: suspect for suspect in found}


# ##################################################################################
# Reading the device's answer
# ##################################################################################
def test_values_are_decoded_and_named_with_their_percent_sign() -> None:
    """The API sends Base64 values, and names with or without the '%'."""
    response = json.dumps([{"name": "Alpha", "value": _encoded("one")}, {"name": "%Beta", "value": _encoded("two")}])
    assert livevars.parse_globals(response) == {"%Alpha": "one", "%Beta": "two"}


def test_a_value_that_is_not_base64_is_shown_as_received() -> None:
    """Better the server's own text than a variable that vanishes and reads as absent."""
    assert livevars.parse_globals(json.dumps([{"name": "Odd", "value": "not base64!"}])) == {"%Odd": "not base64!"}


def test_an_empty_global_is_present_and_empty() -> None:
    """A global holding nothing is on the phone; absent is a different answer."""
    live = livevars.LiveValues("x:1", livevars.parse_globals(json.dumps([{"name": "Blank", "value": ""}])))
    assert live.has("%Blank")
    assert live.value("%Blank") == ""
    assert not live.has("%Missing")


@pytest.mark.parametrize("response", ["not json", json.dumps({"name": "x"}), None])
def test_an_answer_that_is_not_a_list_is_not_an_empty_list(response: object) -> None:
    """A failed read is never taken for 'the phone has no globals'."""
    assert livevars.parse_globals(response) is None


def test_a_failed_read_reports_why_and_returns_no_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """A device that cannot be reached is an error with its message, never an empty set of globals."""
    monkeypatch.setattr(livevars, "auth_key_for", lambda *_args: (0, "key"))
    monkeypatch.setattr(livevars, "http_request", lambda *_args, **_kwargs: (8, "Unable to reach the device."))
    assert livevars.fetch_live_values("192.168.0.210", "1821") == (8, "Unable to reach the device.", None)


def test_a_good_read_returns_every_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """One unfiltered GET api/globals, with the device's key, and the address kept tidy."""
    seen = {}

    def request(_ip: str, _port: str, _location: str, endpoint: str, query: str, key: str, **_kwargs: object) -> tuple:
        seen.update(endpoint=endpoint, query=query, key=key)
        return 0, json.dumps([{"name": "Both", "value": _encoded("7")}]).encode()

    monkeypatch.setattr(livevars, "auth_key_for", lambda *_args: (0, "key"))
    monkeypatch.setattr(livevars, "http_request", request)
    return_code, message, live = livevars.fetch_live_values(" 192.168.0.210 ", "1821")
    assert (return_code, message) == (0, "")
    assert live is not None
    assert live.address == "192.168.0.210:1821"
    assert live.value("%Both") == "7"
    assert seen == {"endpoint": "api/globals", "query": "", "key": "key"}


def test_no_address_is_not_asked_about() -> None:
    """Nothing is sent when there is nowhere to send it."""
    assert livevars.fetch_live_values("", "1821")[0] == 8


# ##################################################################################
# Setting the phone's answer beside the file's
# ##################################################################################
def test_without_a_device_nothing_changes() -> None:
    """Every finding keeps an empty live line, so the plain report is the report it always was."""
    assert {name: suspect.live for name, suspect in _by_subject(None).items()} == {"%Orphan": "", "%Dead": ""}
    plain = varxref.text_report(varxref.build_report(varxref.build_index(state=PrimeItems), state=PrimeItems))
    assert "Live values" not in plain
    assert "    live   " not in plain
    assert "      live     " not in plain


def test_a_never_set_global_the_phone_holds_is_set_from_outside_the_file() -> None:
    """A read-but-never-set global that exists on the phone is not a bug in the file."""
    suspect = _by_subject(_live(Orphan="from a plugin"))["%Orphan"]
    assert "holds 'from a plugin'" in suspect.live
    assert "outside this file" in suspect.live


def test_a_never_set_global_the_phone_lacks_is_confirmed() -> None:
    """Absent from file and phone alike: the read really does see an empty value."""
    assert _by_subject(_live())["%Orphan"].live.startswith("not on the phone either -- confirmed")


def test_a_never_read_global_the_phone_holds_shows_its_value() -> None:
    """The value on the phone is shown, since it is the only evidence of what the variable is for."""
    suspect = _by_subject(_live(Dead="42"))["%Dead"]
    assert "holds '42'" in suspect.live


def test_a_never_read_global_the_phone_lacks_has_not_been_set() -> None:
    """Set here but absent there: the setting action has not run, or the value was cleared."""
    assert _by_subject(_live())["%Dead"].live.startswith("not on the phone --")


def test_the_phone_never_adds_or_removes_a_finding() -> None:
    """The file is the truth about what the configuration does; the phone only qualifies it."""
    assert set(_by_subject(_live(Orphan="x", Dead="y"))) == set(_by_subject(None))


def test_the_report_carries_the_phones_values_and_a_tally() -> None:
    """The saved report shows each value, and the header says how the phone split the findings."""
    live = _live(Orphan="seen", Both="7", Kept="from the phone")
    text = varxref.text_report(varxref.build_report(varxref.build_index(state=PrimeItems), live=live, state=PrimeItems))
    assert "Live values: 3 globals read from 192.168.0.210:1821" in text
    assert "of 1 read but never set: 0 confirmed -- not on the phone either, 1 exist on the phone" in text
    assert "of 1 set but never read: 1 not on the phone, 0 on the phone" in text
    assert "live   '7'" in text  # %Both's entry in the where-used index
    assert "live   '' " not in text


def test_a_declared_global_that_has_drifted_from_the_file_says_so() -> None:
    """A declared global is compared with its value in the file; an unchanged one is not flagged."""
    drifted = varxref.text_report(
        varxref.build_report(varxref.build_index(state=PrimeItems), live=_live(Kept="changed"), state=PrimeItems),
    )
    assert "live   'changed'  (differs from the value in this file)" in drifted

    same = varxref.text_report(
        varxref.build_report(varxref.build_index(state=PrimeItems), live=_live(Kept="from the file"), state=PrimeItems),
    )
    assert "live   'from the file'" in same
    assert "differs" not in same


def test_a_long_multiline_value_is_one_short_line() -> None:
    """A value is folded onto one line and cut, so one global cannot swamp the report."""
    shown = varxref._shown_value(  # noqa: SLF001
        "first line\n" + "x" * 100
    )
    assert "\n" not in shown
    assert len(shown) < 70
    assert shown.endswith("...'")
