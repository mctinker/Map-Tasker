"""MapTasker Inbound Inventory (inbound) Unit Tests

The inventory answers "what can start this configuration's Tasks from outside, and does anything check who sent it".
What is tested is that each kind of trigger is found and read the way Tasker writes it, that the answer to the second
question is right in each of its four forms (filtered by the event, checked by an If in the Task, open, or a broadcast
only Android sends), that what a triggered Task can do is followed through Perform Task, and that a Profile that is
turned off is listed and counted nowhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import inbound
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems

from tests.shared_fixtures import _load_local
from tests.test_outbound import shell, sms
from tests.test_taskstep import _act, _cond, _i, _s, end_if, flash

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("_runtime")


def _event(code: str, *arguments: str) -> str:
    return f'<Event sr="con0" ve="2"><code>{code}</code>{"".join(arguments)}</Event>'


def http_event(path: str = "/go", *, port: str = "1821", method: str = "GET", wifi: int = 1, network: str = "") -> str:
    return _event("2089", _i(1, port), _s(2, method), _s(3, path), _s(4, ""), _i(5, 30), _i(6, wifi), _s(7, network))


def intent_event(action: str) -> str:
    return _event("599", _s(0, action), _i(1, 0), _i(2, 0), _s(3, ""), _s(4, ""))


def text_event(sender: str = "") -> str:
    return _event("7", _i(0, 0), _s(1, sender), _s(2, ""), _s(3, ""), _s(4, ""))


def share_event(package: str = "") -> str:
    return _event("2101", _s(1, package), _s(2, ""))


def command_event() -> str:
    return _event("2091", _s(1, ""), _s(2, ""), _i(3, 0), _i(4, 1))


def if_(lhs: str, rhs: str = "x") -> str:
    return _act("37", _cond(lhs, 2, rhs))


def perform(name: str) -> str:
    return _act("130", _s(0, name), _i(1, 5))


def profile(number: int, name: str, event: str, task: int, *, off: bool = False, extra: str = "") -> str:
    limit = "<limit>true</limit>" if off else ""
    return f'<Profile sr="prof{number}" ve="2"><id>{number}</id>{limit}<mid0>{task}</mid0><nme>{name}</nme>{event}{extra}</Profile>'


def load(tmp_path: Path, profiles: tuple[str, ...], settings: str = "", **tasks: tuple[str, ...]) -> None:
    """Tasks 1.. in a Project called 'Home', with the given Profiles beside them."""
    body = ""
    for number, (name, actions) in enumerate(tasks.items(), start=1):
        numbered = "".join(action.replace("act{}", f"act{index}") for index, action in enumerate(actions))
        body += f'<Task sr="task{number}" ve="2"><id>{number}</id><nme>{name.replace("_", " ")}</nme>{numbered}</Task>'
    ids = ",".join(str(number) for number in range(1, len(tasks) + 1))
    pids = ",".join(str(number) for number in range(1, len(profiles) + 1))
    project = f'<Project sr="proj0" ve="2"><name>Home</name><pids>{pids}</pids><tids>{ids}</tids></Project>'
    _load_local(
        tmp_path, f'<TaskerData sr="" dvi="1" tv="6.3.13">{project}{"".join(profiles)}{body}{settings}</TaskerData>'
    )


def entries() -> list[inbound.Entry]:
    return inbound.inbound_entries(PrimeItems)


def report() -> tuple[str, dict[str, int]]:
    rows, counts = inbound.run_inbound_inventory(PrimeItems)
    return text_report(rows), counts


# ##################################################################################
# Finding and reading each kind of trigger.
# ##################################################################################
def test_an_http_request_event_is_a_web_trigger_and_says_its_port_method_and_path(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "API", http_event("/api/tasks*", method="POST"), 1),), Handle=(flash("hi"),))

    (entry,) = entries()

    assert entry.category == inbound.WEB
    assert entry.what == "HTTP Request"
    assert entry.detail == "port 1821, POST /api/tasks*"
    assert entry.limits == ["Wi-Fi only"]
    assert [run.name for run in entry.runs] == ["Handle"]


def test_each_inbound_event_is_its_own_category(tmp_path: Path) -> None:
    load(
        tmp_path,
        (
            profile(1, "a", intent_event("com.example.GO"), 1),
            profile(2, "b", command_event(), 1),
            profile(3, "c", share_event(), 1),
            profile(4, "d", text_event(), 1),
            profile(5, "e", _event("2100"), 1),
        ),
        Do=(flash("x"),),
    )

    assert [entry.category for entry in entries()] == [
        inbound.INTENT,
        inbound.COMMAND,
        inbound.SHARE,
        inbound.TEXT,
        inbound.REMOTE,
    ]


def test_an_event_that_nothing_outside_can_send_is_not_listed(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Screen", _event("208"), 1),), Do=(flash("x"),))

    assert entries() == []
    text, counts = report()
    assert "Nothing to report" in text
    assert counts["total"] == 0


def test_an_intent_only_android_sends_is_a_system_broadcast_and_is_not_counted(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Wifi", intent_event("android.net.wifi.RSSI_CHANGED"), 1),), Do=(shell("id", root="1"),))

    (entry,) = entries()
    text, counts = report()

    assert entry.guard == inbound.SYSTEM
    assert entry.flags == []
    assert counts["total"] == 0
    assert "the Android system" in text


def test_an_intent_action_built_from_a_variable_is_flagged_as_unknowable(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Dyn", intent_event("%action"), 1),), Do=(flash("x"),))

    (entry,) = entries()

    assert inbound.FLAG_VARIABLE_ACTION in entry.flags


# ##################################################################################
# Does anything check who sent it.
# ##################################################################################
def test_a_trigger_with_nothing_in_the_way_is_open(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Any", intent_event("com.example.GO"), 1),), Do=(flash("x"),))

    (entry,) = entries()

    assert entry.guard == inbound.OPEN
    assert entry.flags == [], "open and harmless is listed, not flagged"


def test_a_received_text_from_one_number_is_filtered(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Mum", text_event("+1 415 555 0100"), 1),), Do=(shell("id", root="1"),))

    (entry,) = entries()

    assert entry.guard == inbound.FILTERED
    assert "+1 415 555 0100" in entry.guard_detail
    assert entry.flags == []


def test_a_received_share_from_one_app_is_filtered(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Chrome", share_event("com.android.chrome"), 1),), Do=(flash("x"),))

    assert entries()[0].guard == inbound.FILTERED


def test_an_if_on_a_variable_the_sender_supplied_makes_it_checked(tmp_path: Path) -> None:
    load(
        tmp_path,
        (profile(1, "API", http_event(), 1),),
        Handle=(if_("%http_request_headers(Authorization)", "%token"), shell("reboot", root="1"), end_if()),
    )

    (entry,) = entries()

    assert entry.guard == inbound.CHECKED
    assert "%http_request_headers" in entry.guard_detail
    assert entry.flags == []


def test_an_if_on_something_else_does_not_make_it_checked(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "API", http_event(), 1),), Handle=(if_("%SCREEN", "on"), flash("x"), end_if()))

    (entry,) = entries()

    assert entry.guard == inbound.OPEN
    assert "tests other things" in entry.guard_detail


def test_a_check_in_a_task_that_the_first_one_performs_counts(tmp_path: Path) -> None:
    load(
        tmp_path,
        (profile(1, "Cmd", command_event(), 1),),
        Front=(perform("Gate"),),
        Gate=(if_("%command_parameter", "secret"), end_if()),
    )

    assert entries()[0].guard == inbound.CHECKED


def test_handing_what_was_sent_to_another_task_to_examine_counts_as_a_check(tmp_path: Path) -> None:
    load(
        tmp_path,
        (profile(1, "API", http_event(), 1),),
        Front=(_act("130", _s(0, "Authorize"), _i(1, 5), _s(2, "%http_request_headers()"), _s(4, "%ok")),),
        Authorize=(flash("x"),),
    )

    (entry,) = entries()

    assert entry.guard == inbound.CHECKED
    assert entry.guard_detail == "%http_request_headers is handed to Task 'Authorize' to examine"


def test_a_task_that_performs_itself_does_not_hang_the_reader(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Loop", command_event(), 1),), Front=(perform("Front"),))

    assert entries()[0].guard == inbound.OPEN


# ##################################################################################
# What is worth a look.
# ##################################################################################
def test_an_open_web_server_is_always_worth_a_look_and_says_which_network(tmp_path: Path) -> None:
    load(
        tmp_path,
        (profile(1, "Lan", http_event(wifi=1), 1), profile(2, "World", http_event(wifi=0), 1)),
        Do=(flash("x"),),
    )

    lan, world = entries()

    assert lan.flags == [inbound.FLAG_ON_WIFI]
    assert world.flags == [inbound.FLAG_ANY_NETWORK]
    assert world.limits == []


def test_an_open_intent_that_starts_a_shell_command_is_worth_a_look(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Run", intent_event("com.example.RUN"), 1),), Do=(shell("rm x"), sms("+1 415 555 0100")))

    (entry,) = entries()

    assert entry.effects_dangerous == ["Message", "Shell"]
    assert entry.flags[0] == inbound.FLAG_ANY_APP
    assert "message, shell" in entry.flags[1]


def test_what_a_performed_task_does_counts_as_what_the_trigger_starts(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Cmd", command_event(), 1),), Front=(perform("Back"),), Back=(shell("id", root="1"),))

    (entry,) = entries()

    assert entry.effects == ["Root"]
    assert entry.needs_a_look


def test_a_profile_that_is_turned_off_is_listed_and_counted_nowhere(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "Off", http_event(), 1, off=True),), Do=(flash("x"),))

    (entry,) = entries()
    text, counts = report()

    assert not entry.enabled
    assert not entry.needs_a_look
    assert counts["total"] == 0
    assert "(turned off)" in text


def test_a_profile_with_other_conditions_says_the_event_only_counts_while_they_hold(tmp_path: Path) -> None:
    other = '<State sr="con1" ve="2"><code>165</code></State>'
    load(tmp_path, (profile(1, "Gated", http_event(), 1, extra=other),), Do=(flash("x"),))

    assert "only while 1 other condition hold" in entries()[0].limits


# ##################################################################################
# The report and the one setting.
# ##################################################################################
def test_the_report_names_the_trigger_who_can_send_it_and_what_it_starts(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "API", http_event(), 1),), Handle=(shell("id", root="1"),))

    text, counts = report()

    assert "NEEDS A LOOK -- 1 trigger" in text
    assert "HTTP Request: port 1821, GET /go" in text
    assert "From: anything that can reach this phone's web server" in text
    assert "OPEN -- nothing checks who sends it" in text
    assert "Starts Task 'Handle'; it can do: root" in text
    assert counts["open"] == 1
    assert counts["flagged"] == 1
    assert counts[inbound.WEB] == 1


def test_external_access_on_is_reported(tmp_path: Path) -> None:
    setting = "<Setting sr='prefs0'><n>aExt</n><t>b</t><v>true</v></Setting>"
    load(tmp_path, (profile(1, "x", command_event(), 1),), settings=setting, Do=(flash("x"),))

    text, counts = report()

    assert "Allow External Access is ON" in text
    assert counts["external_access"] == 1


def test_external_access_missing_from_the_file_is_said_not_assumed(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "x", command_event(), 1),), Do=(flash("x"),))

    text, counts = report()

    assert "is not in this file" in text
    assert counts["external_access"] == 0


def test_the_report_is_written_to_a_timestamped_file(tmp_path: Path) -> None:
    load(tmp_path, (profile(1, "x", command_event(), 1),), Do=(flash("x"),))
    rows, _counts = inbound.run_inbound_inventory(PrimeItems)

    path = inbound.write_inbound_report(rows, PrimeItems)

    assert path
    assert "MapTasker_Inbound_" in path
    assert "MapTasker Inbound Inventory" in open(path, encoding="utf-8").read()
