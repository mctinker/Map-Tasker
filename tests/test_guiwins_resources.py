"""The Missing Resources dialog: what the last check found, asking the device again, and saving the report.

What is collected and concluded is test_resrefs', and how the phone is asked is test_deviceresource's.  What is tested
here is the dialog around them: that it opens on the answers already kept, that Check Device asks for what the
fields say and redraws from what came back, that a device which does not answer is said so and not mistaken for
"nothing is missing", and that the report can be saved.  The dialog is the real one, on a page of NiceGUI's in-process
user simulation; the device is not involved.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import resrefs
from maptasker.src.core import resstore
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.device import deviceresource
from maptasker.src.gui import guiwins_resources
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_resrefs import _FIXTURE_XML, PHONE, _answer, _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

    from nicegui.testing.user import User

_built: dict = {}
_jumps: list[object] = []
_remembered: list[tuple[str, str]] = []


@pytest.fixture(autouse=True)
def _configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The resrefs fixture loaded, a result store of the test's own, and no settings file written."""
    _built.clear()
    _jumps.clear()
    _remembered.clear()
    monkeypatch.setattr(resstore, "cache_path", lambda: str(tmp_path / "MapTasker_Resources.json"))
    monkeypatch.setattr(
        guiwins_resources, "remember_android_address", lambda _gui, ip, port: _remembered.append((ip, port))
    )
    monkeypatch.setattr(guiwins_resources, "remember_android_address_fields", lambda *_a, **_k: None)
    _load(_FIXTURE_XML)


def _gui() -> SimpleNamespace:
    """The little of MyGui the dialog uses: the run's state and an address to open with."""
    return SimpleNamespace(state=PrimeItems, android_last_ipaddr="192.0.2.1", android_last_port="1821")


def _page() -> None:
    def make_jump(target: object) -> Callable:
        async def go() -> None:
            _jumps.append(target)

        return go

    _built["dialog"] = guiwins_resources.build_resources_dialog(_gui(), make_jump)  # type: ignore[arg-type]
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _button(user: User, text: str) -> ui.button:
    (element,) = [e for e in user.find(kind=ui.button).elements if e.text == text]
    return element


def _shown(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _outcome(**changes: object) -> deviceresource.Outcome:
    outcome = deviceresource.Outcome(device=PHONE, asked=10, answered=10, missing=1)
    for name, value in changes.items():
        setattr(outcome, name, value)
    return outcome


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(60):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


@pytest.mark.asyncio
async def test_it_opens_on_what_the_last_check_found() -> None:
    _answer(PHONE, data=False, music=True)
    async with _open() as user:
        await user.should_see("Missing Resources")
        text = _shown(user)

        assert any(line.startswith("MISSING (1)") for line in text)
        assert any("Tasker/data.txt" in line for line in text)
        assert any(line.startswith(f"Checked against {PHONE}") for line in text)


@pytest.mark.asyncio
async def test_before_any_check_it_says_none_has_been_made() -> None:
    async with _open() as user:
        await user.should_see("No device has been checked yet.")
        assert any("None has been checked yet" in line for line in _shown(user))


@pytest.mark.asyncio
async def test_it_opens_with_the_address_the_other_android_dialogs_use() -> None:
    async with _open() as user:
        values = {e.props.get("label", ""): e.value for e in user.find(kind=ui.input).elements}

        assert values["Android IP Address"] == "192.0.2.1"
        assert values["Port"] == "1821"


@pytest.mark.asyncio
async def test_check_device_asks_what_the_fields_say_and_redraws_from_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[str, str, bool]] = []

    def fake_check(ip: str, port: str, references: resrefs.References, *, refresh_apps: bool, state: object) -> object:
        asked.append((ip, port, refresh_apps))
        assert references.questions()
        _answer(PHONE, data=False)
        return _outcome()

    monkeypatch.setattr(deviceresource, "check_device", fake_check)
    async with _open() as user:
        UserInteraction(user, {_button(user, "Check Device")}, None).click()
        await _until(lambda: asked)
        await user.should_see("Tasker/data.txt")

        assert asked == [("192.0.2.1", "1821", True)]
        assert _remembered == [("192.0.2.1", "1821")]
        assert user.notify.contains("1 missing")


@pytest.mark.asyncio
async def test_a_device_that_did_not_answer_is_said_so_and_its_problems_are_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        deviceresource,
        "check_device",
        lambda *_a, **_k: _outcome(answered=0, missing=0, errors=["Files and folders: unreachable"]),
    )
    async with _open() as user:
        UserInteraction(user, {_button(user, "Check Device")}, None).click()
        await user.should_see("Problem: Files and folders: unreachable")

        assert user.notify.contains("The device did not answer")


@pytest.mark.asyncio
async def test_the_refresh_checkbox_decides_whether_the_app_list_is_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[bool] = []
    monkeypatch.setattr(
        deviceresource,
        "check_device",
        lambda _ip, _port, _refs, *, refresh_apps, state: asked.append(refresh_apps) or _outcome(),
    )
    async with _open() as user:
        (box,) = user.find(kind=ui.checkbox).elements
        box.set_value(False)
        UserInteraction(user, {_button(user, "Check Device")}, None).click()
        await _until(lambda: asked)

        assert asked == [False]


@pytest.mark.asyncio
async def test_a_row_naming_a_place_is_a_link_into_the_map() -> None:
    _answer(PHONE, data=False)
    async with _open() as user:
        links = [element for element in user.find(kind=ui.link).elements if "action 9 -- Read File" in element.text]
        assert links

        UserInteraction(user, {links[0]}, None).click()
        await _until(lambda: _jumps)

        assert _jumps[0].action == 9  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_save_report_writes_the_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(resrefs, "output_path", lambda name, state: str(tmp_path / name))
    _answer(PHONE, data=False)
    async with _open() as user:
        UserInteraction(user, {_button(user, "Save Report")}, None).click()
        await _until(lambda: user.notify.contains("Report saved as"))

    (saved,) = tmp_path.glob("MapTasker_Resources_*.txt")
    assert "Tasker/data.txt" in saved.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_dialog_and_a_message() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}}
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No XML file has been loaded")
