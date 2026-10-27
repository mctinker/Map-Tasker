"""MapTasker Outbound Inventory (outbound) Unit Tests

The inventory answers "what does this configuration reach outside itself with, and to whom".  What is tested is
that each kind of action is found and read the way Tasker writes it, that the destination shown is the destination
the action has, that the report is safe to share (a key pasted into an address is never printed), and that it
declines to guess: an address built from a variable is flagged rather than given a host, and an action that is turned
off is listed and counted nowhere.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import outbound
from maptasker.src.core import piiscan
from maptasker.src.core.mapjump import text_report
from maptasker.src.core.primitem import PrimeItems

from tests.shared_fixtures import _load_local
from tests.test_taskstep import _act, _i, _s, disabled, flash, set_

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("_runtime")


def request(url: str, *, own: str = "") -> str:
    return _act("339", _s(1, "0"), _s(2, url), extra=own)


def http_get(server: str, path: str = "") -> str:
    return _act("118", _s(0, server), _s(1, path))


def shell(command: str, *, root: str = "0", shizuku: str = "0") -> str:
    return _act("123", _s(0, command), _i(1, 0), _i(2, root), _i(8, shizuku))


def sms(number: str, text: str = "hi") -> str:
    return _act("41", _s(0, number), _s(1, text))


def call(number: str) -> str:
    return _act("90", _s(0, number), _i(1, 0))


def intent(action: str, *, data: str = "", target: int = 0, package: str = "") -> str:
    return _act("877", _s(0, action), _s(3, data), _s(7, package), _i(9, target))


def load(tmp_path: Path, **tasks: tuple[str, ...]) -> None:
    """Tasks 1.. in a Project called 'Home', plus any Task whose name ends in '_loose' left outside it."""
    body = ""
    members = []
    for number, (name, actions) in enumerate(tasks.items(), start=1):
        numbered = "".join(action.replace("act{}", f"act{index}") for index, action in enumerate(actions))
        body += f'<Task sr="task{number}" ve="2"><id>{number}</id><nme>{name.replace("_", " ")}</nme>{numbered}</Task>'
        if not name.endswith("loose"):
            members.append(str(number))
    project = f'<Project sr="proj0" ve="2"><name>Home</name><tids>{",".join(members)}</tids></Project>'
    _load_local(tmp_path, f'<TaskerData sr="" dvi="1" tv="6.3.13">{project}{body}</TaskerData>')


def uses() -> list[outbound.Use]:
    return outbound.outbound_uses(PrimeItems)


def report() -> tuple[str, dict[str, int]]:
    rows, counts = outbound.run_outbound_inventory(PrimeItems)
    return text_report(rows), counts


# ##################################################################################
# Finding and reading each kind of action.
# ##################################################################################
def test_an_http_request_is_a_web_use_and_names_its_host(tmp_path: Path) -> None:
    load(tmp_path, Sync=(request("https://api.example.com/v1/items?x=1"),))

    (use,) = uses()

    assert use.category == outbound.WEB
    assert use.hosts == ["api.example.com"]
    assert use.flags == []
    assert use.where.action == 1


def test_a_get_joins_its_server_and_its_path_into_one_address(tmp_path: Path) -> None:
    load(tmp_path, Sync=(http_get("https://example.org:8443", "/status"),))

    (use,) = uses()

    assert use.detail == "https://example.org:8443/status"
    assert use.hosts == ["example.org"]


def test_a_user_and_password_in_the_address_are_not_taken_for_the_host(tmp_path: Path) -> None:
    assert outbound.host_of("https://bob:secret@Files.Example.com:21/x") == "files.example.com"
    assert outbound.host_of("[::1]:8080/x") == "::1"
    assert outbound.host_of("") == ""


def test_sms_call_shell_and_intent_are_each_their_own_category(tmp_path: Path) -> None:
    load(
        tmp_path,
        Mix=(
            sms("+1 415 555 0100"),
            call("911"),
            shell("ls /sdcard"),
            intent("android.intent.action.VIEW", data="https://intent.example.net/a", target=1),
        ),
    )

    assert [use.category for use in uses()] == [outbound.MESSAGE, outbound.CALL, outbound.SHELL, outbound.INTENT]
    text, counts = report()
    assert "+1 415 555 0100" in text, "a destination is the point of the report, so it is not redacted"
    assert "Activity: android.intent.action.VIEW" in text
    assert counts[outbound.INTENT] == 1
    assert uses()[3].hosts == ["intent.example.net"]


def test_a_shell_command_with_root_on_is_a_root_command_and_flagged(tmp_path: Path) -> None:
    load(tmp_path, Dangerous=(shell("rm -rf /data/x", root="1"),), Tame=(shell("date"),))

    root, tame = uses()

    assert root.category == outbound.ROOT
    assert root.flags == [outbound.FLAG_ROOT]
    assert tame.category == outbound.SHELL
    assert tame.flags == []


def test_root_that_a_variable_decides_is_flagged_as_possible_not_certain(tmp_path: Path) -> None:
    load(tmp_path, Maybe=(shell("id", root="%useroot"),))

    (use,) = uses()

    assert use.category == outbound.SHELL
    assert use.flags == [outbound.FLAG_ROOT_VARIABLE]


def test_a_plugin_on_the_list_is_found_and_the_address_in_its_settings_is_read(tmp_path: Path) -> None:
    bundle = "<Bundle sr='arg0'><Vals><url>https://hooks.example.com/abc</url></Vals></Bundle>"
    load(tmp_path, Hook=(_act("122375409", extra=bundle),))

    (use,) = uses()

    assert use.category == outbound.PLUGIN
    assert use.hosts == ["hooks.example.com"]


def test_a_plugin_that_names_no_address_says_where_to_look(tmp_path: Path) -> None:
    load(tmp_path, Hook=(_act("1887951895"),))

    (use,) = uses()

    assert "set inside the plugin" in use.detail
    assert use.hosts == []


def test_an_action_that_goes_nowhere_is_not_listed(tmp_path: Path) -> None:
    load(tmp_path, Quiet=(set_("%a", "1"), flash("hello")))

    assert uses() == []


# ##################################################################################
# What is worth a look, and the refusal to guess.
# ##################################################################################
def test_plain_http_is_flagged_unless_it_stays_on_the_users_own_network(tmp_path: Path) -> None:
    load(
        tmp_path,
        Out=(request("http://tracker.example.com/ping"),),
        In=(request("http://192.168.1.20/api"), request("http://nas.local/api"), request("http://localhost:8080/x")),
    )

    out, *home = uses()

    assert out.flags == [outbound.FLAG_PLAIN_HTTP]
    assert all(use.flags == [] for use in home)


def test_an_address_built_from_a_variable_is_flagged_and_given_no_host(tmp_path: Path) -> None:
    load(tmp_path, Dynamic=(request("%server/api"), request("https://api.example.com/%id")))

    variable, path_only = uses()

    assert variable.flags == [outbound.FLAG_VARIABLE_ADDRESS]
    assert variable.hosts == []
    assert path_only.flags == []
    assert path_only.hosts == ["api.example.com"]


def test_a_key_in_the_address_is_flagged_and_never_printed(tmp_path: Path) -> None:
    key = "AIza" + "B" * 35
    load(tmp_path, Leaky=(request(f"https://maps.example.com/geo?key={key}"),))

    (use,) = uses()
    text, counts = report()

    assert any(flag.startswith(outbound.FLAG_CREDENTIAL) for flag in use.flags)
    assert key not in text
    assert "[REDACTED:" in text
    assert "maps.example.com" in text, "the host stays: it is what the report is for"
    assert counts["flagged"] == 1


def test_a_filled_in_password_field_flags_the_action_though_nothing_is_printed_of_it(tmp_path: Path) -> None:
    auth = _act("351", _s(2, "id"), _s(4, "https://auth.example.com/code"), _s(9, "bob"), _s(10, "hunter2"))
    load(tmp_path, Login=(auth,))

    (use,) = uses()
    text, _ = report()

    assert any("PASSWORD" in flag for flag in use.flags)
    assert "hunter2" not in text


def test_an_app_link_or_a_file_is_an_intent_but_not_a_host_and_not_a_mystery(tmp_path: Path) -> None:
    load(
        tmp_path,
        Apps=(
            intent("android.intent.action.VIEW", data="whatsapp://send/?phone=%number", target=1),
            intent("android.intent.action.VIEW", data="file://%par1", target=1),
            intent("android.intent.action.VIEW", data="tel:5551234", target=1),
            _act("104", _s(0, "market://details?id=com.example")),
        ),
    )

    found = uses()

    assert [use.category for use in found] == [outbound.INTENT, outbound.INTENT, outbound.INTENT, outbound.WEB]
    assert all(use.hosts == [] and use.flags == [] for use in found)
    assert "whatsapp://send" in found[0].detail, "still listed: what the action does is the point"


def test_only_a_network_scheme_gives_a_host() -> None:
    assert outbound.host_of("ftp://files.example.com/a") == "files.example.com"
    assert outbound.host_of("files.example.com:2121") == "files.example.com", "a Server:Port has no scheme"
    assert outbound.host_of("whatsapp://send") == ""
    assert outbound.host_of("tel:5551234") == ""
    assert outbound.host_of("%server/x") == ""


def test_an_action_that_is_turned_off_is_listed_and_counted_nowhere(tmp_path: Path) -> None:
    load(tmp_path, Off=(disabled(request("https://off.example.com/x")),), On=(request("https://on.example.com/x"),))

    text, counts = report()

    assert counts["total"] == 1
    assert "(turned off)" in text
    assert "off.example.com" in text
    hosts_section = text.split("HOSTS CONTACTED")[1].split("BY PROJECT")[0]
    assert "on.example.com" in hosts_section
    assert "off.example.com" not in hosts_section


def test_an_address_written_in_another_action_is_listed_apart_and_not_counted_as_contacted(tmp_path: Path) -> None:
    load(tmp_path, Setup=(set_("%base", "https://later.example.com/api"),))

    text, counts = report()

    assert counts["total"] == 0
    assert "ADDRESSES WRITTEN IN OTHER ACTIONS" in text
    assert "later.example.com" in text
    assert "HOSTS CONTACTED" not in text


# ##################################################################################
# The report.
# ##################################################################################
def test_the_report_is_grouped_by_project_and_says_where_a_loose_task_is(tmp_path: Path) -> None:
    load(tmp_path, Sync=(request("https://a.example.com/x"),), Stray_loose=(sms("5551234"),))

    text, _ = report()

    assert "Project 'Home'   (1 action)" in text
    assert "Not in any Project   (1 action)" in text
    assert text.index("Project 'Home'") < text.index("Not in any Project")


def test_hosts_are_listed_busiest_first_with_how_many_places_use_them(tmp_path: Path) -> None:
    load(
        tmp_path,
        One=(request("https://rare.example.com/"),),
        Two=(request("https://busy.example.com/a"), request("https://busy.example.com/b")),
    )

    text, _ = report()

    hosts = text.split("HOSTS CONTACTED")[1].split("BY PROJECT")[0]
    assert hosts.index("busy.example.com") < hosts.index("rare.example.com")
    assert "2 places in 1 Project" in hosts


def test_the_summary_counts_hosts_and_a_clean_config_gets_no_needs_a_look_section(tmp_path: Path) -> None:
    load(tmp_path, Sync=(request("https://a.example.com/x"), request("https://b.example.com/x")))

    text, counts = report()

    assert "2 actions   2 hosts" in text
    assert "NEEDS A LOOK" not in text
    assert counts["flagged"] == 0


def test_a_configuration_that_reaches_nowhere_says_so_and_still_says_what_it_cannot_see(tmp_path: Path) -> None:
    load(tmp_path, Quiet=(set_("%a", "1"),))

    text, counts = report()

    assert "Nothing to report" in text
    assert "NOTE ON WHAT IS NOT LISTED" in text
    assert counts["total"] == 0


def test_every_row_that_names_a_place_points_at_it(tmp_path: Path) -> None:
    load(tmp_path, Sync=(request("http://tracker.example.com/x"),))

    rows, _ = outbound.run_outbound_inventory(PrimeItems)

    targets = [row.target for row in rows if row.target is not None]
    assert targets
    assert {target.key for target in targets if target.kind == "task"} == {"1"}
    assert any(target.action == 1 for target in targets)


def test_the_report_is_written_as_the_text_that_is_shown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    load(tmp_path, Sync=(request("https://a.example.com/x"),))
    monkeypatch.chdir(tmp_path)
    rows, _ = outbound.run_outbound_inventory(PrimeItems)

    file_name = outbound.write_outbound_report(rows, PrimeItems)

    assert os.path.basename(file_name).startswith("MapTasker_Outbound")
    with open(file_name, encoding="utf-8") as written:
        assert written.read() == text_report(rows)


# ##################################################################################
# piiscan's half of it.
# ##################################################################################
def test_redact_credentials_leaves_the_destinations_alone() -> None:
    key = "AIza" + "C" * 35

    redacted = piiscan.redact_credentials_in_text(f"https://x.example.com/?key={key}")
    assert key not in redacted
    assert redacted.startswith("https://x.example.com/?key=[REDACTED:")
    assert piiscan.redact_credentials_in_text("mail bob@example.com or +1 415 555 0100") == (
        "mail bob@example.com or +1 415 555 0100"
    )


def test_a_variable_in_a_credential_field_is_not_a_credential(tmp_path: Path) -> None:
    auth = _act("351", _s(2, "id"), _s(4, "https://auth.example.com/code"), _s(10, "%password"))
    load(tmp_path, Login=(auth,))

    (use,) = uses()

    assert use.flags == []


def test_credentials_in_action_names_each_kind_once_and_ignores_non_secrets(tmp_path: Path) -> None:
    key = "AIza" + "D" * 35
    load(
        tmp_path,
        Mixed=(
            request(
                f"https://x.example.com/?a={key}&amp;b={key}",
                own="<Bundle><Vals><who>bob@example.com</who></Vals></Bundle>",
            ),
        ),
    )
    action = PrimeItems.tasker_root_elements["all_tasks"]["1"]["xml"].find("Action")

    labels = piiscan.credentials_in_action(action)

    assert labels == ["API-KEY"], "once, and the email address in the bundle is not a credential"
