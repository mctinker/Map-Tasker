"""Fuzz every input MapTasker reads from outside: whatever it is handed, the reader answers and does not raise.

The backup is fuzzed in test_fuzz_backup.  These are the rest of what comes in from a place MapTasker does not control:

  * the settings file, which a user edits by hand and a crash can leave half-written;
  * the configuration history, a folder of compressed snapshots in the user's own directory;
  * a Version 2 Scene's layout, a Base64 of gzipped JSON that Tasker writes and anything can damage;
  * what the phone answers, what TaskerNet answers, what an AI model replies;
  * the small caches and lists kept between sessions, which are files like any other.

Each is started from a well-formed one and spoiled (see tests/fuzzing.py), and checked against what the reader promises:
the answer it documents, its own error, or -- for a reader that "never raises" -- anything but an exception.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
import tomli_w
from hypothesis import assume, event, given
from hypothesis import strategies as st
from maptasker.src import clireports
from maptasker.src.analysis import mapask, timecomp
from maptasker.src.core import getputer, scenelayout, timeline
from maptasker.src.core.colrmode import effective_colors, set_color_mode
from maptasker.src.core.initparg import initialize_runtime_arguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import taskerd
from maptasker.src.mapops import mapdraft

from tests.fuzzing import JSON_VALUES, files_of_any_age, fuzz, json_documents, reshaped, spoiled
from tests.test_fuzz_backup import _SYNTHETIC, DOCUMENTED_EXIT_CODES, a_scratch_run, prime_a_run


# ##################################################################################
# The settings file
# ##################################################################################
def _a_real_settings_file() -> bytes:
    """A settings file as MapTasker writes one, made once."""
    with a_scratch_run(b"") as path:
        PrimeItems.program_arguments = initialize_runtime_arguments()
        PrimeItems.colors_to_use = set_color_mode("dark")
        target = path.with_name("MapTasker_Settings.toml")
        getputer.save_arguments(
            PrimeItems.program_arguments.as_dict(), dict(PrimeItems.colors_to_use), str(target), PrimeItems
        )
        return target.read_bytes()


_SETTINGS_FILE = _a_real_settings_file()


@st.composite
def settings_files(draw: st.DrawFn) -> bytes:
    """A settings file: the real one with bytes spoiled, with a value of the wrong kind where a value goes, or as an
    older version wrote it (its historical values back in, and a version that is missing or from earlier on)."""
    kind = draw(st.sampled_from(["bytes", "reshaped", "older"]))
    if kind == "bytes":
        return draw(spoiled(_SETTINGS_FILE))
    import tomllib

    if kind == "older":
        old = draw(files_of_any_age())
        document = tomllib.loads(_SETTINGS_FILE.decode("utf-8"))
        document["program_arguments"].update(old["program_arguments"])
        document.pop("settings_version", None)
        if "settings_version" in old:
            document["settings_version"] = old["settings_version"]
        return tomli_w.dumps(document).encode("utf-8")

    document = reshaped(tomllib.loads(_SETTINGS_FILE.decode("utf-8")))
    try:
        return tomli_w.dumps(draw(document)).encode("utf-8")
    except (TypeError, ValueError):
        assume(False)
        raise


@fuzz(300)
@given(data=settings_files())
def test_a_spoiled_settings_file_is_read_as_far_as_it_makes_sense(data: bytes) -> None:
    """A corrupt settings file comes back as the defaults and a note -- the program still starts."""
    with a_scratch_run(data) as path:
        prime_a_run()
        arguments, colors = getputer.read_toml_file(str(path), PrimeItems)
        assert path.read_bytes() == data, "reading the settings changed them"
    event(f"arguments: {type(arguments).__name__}")
    assert isinstance(arguments, dict)
    assert isinstance(colors, dict)


# What a save is handed for the colours differs by caller -- the whole palette (an exit save), only what the user
# changed (the Save button), nothing -- and the file means one thing whichever it was: the colours that differ from the
# appearance mode's palette.  The properties below are that, for colours of every shape.
_MODES = st.sampled_from(["dark", "light", "system"])
_PALETTE_KEYS = sorted(set_color_mode("dark"))
_COLOUR_NAMES = st.text(min_size=1, max_size=14)
_COLOUR_KEYS = st.one_of(st.sampled_from(_PALETTE_KEYS), st.text(min_size=1, max_size=10))


@st.composite
def colour_holdings(draw: st.DrawFn) -> tuple[str, dict[str, str], dict[str, str]]:
    """(the mode, the colours the user changed, and the same colours held another way: the whole palette under them)."""
    mode = draw(_MODES)
    changed = draw(st.dictionaries(_COLOUR_KEYS, _COLOUR_NAMES, max_size=8))
    return mode, changed, {**set_color_mode(mode), **changed}


def _saved_and_restored(mode: str, held: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """The [colors_to_use] table a save of `held` writes, and the colours a read of that file comes back with."""
    import tomllib

    with a_scratch_run(b"") as path:
        prime_a_run()
        target = path.with_name("MapTasker_Settings.toml")
        arguments = initialize_runtime_arguments().as_dict()
        arguments["appearance_mode"] = mode
        getputer.save_arguments(arguments, dict(held), str(target), PrimeItems)
        written = tomllib.loads(target.read_text(encoding="utf-8"))["colors_to_use"]
        _, restored = getputer.read_toml_file(str(target), PrimeItems)
        return written, restored


@fuzz(150)
@given(holding=colour_holdings())
def test_the_colours_saved_come_back_as_they_were_and_the_file_holds_only_what_differs(
    holding: tuple[str, dict[str, str], dict[str, str]],
) -> None:
    mode, changed, whole = holding
    wanted = {**set_color_mode(mode), **changed}
    palette = set_color_mode(mode)

    written_whole, restored_whole = _saved_and_restored(mode, whole)
    written_changed, restored_changed = _saved_and_restored(mode, changed)

    event(f"{len(written_changed)} colours differ")
    assert restored_whole == restored_changed == wanted, "the colours saved did not come back"
    assert written_whole == written_changed, "the file depends on how the caller held the colours"
    assert all(palette.get(name) != value for name, value in written_changed.items()), "a palette colour was written"
    assert set(written_changed) <= set(changed)


@fuzz(100)
@given(holding=colour_holdings())
def test_saving_what_was_read_writes_the_same_colours(holding: tuple[str, dict[str, str], dict[str, str]]) -> None:
    """Restoring and saving again, as every session does, neither adds nor loses a colour."""
    mode, changed, _ = holding
    written, restored = _saved_and_restored(mode, changed)
    written_again, restored_again = _saved_and_restored(mode, restored)

    assert written_again == written
    assert restored_again == restored


@fuzz(150)
@given(mode=_MODES, table=JSON_VALUES)
def test_a_colour_table_of_any_kind_is_read_as_far_as_it_makes_sense(mode: str, table: object) -> None:
    """Whatever stands where the colours go -- not a table, numbers for colours, a null key -- comes back as colours."""
    colours = effective_colors(table, mode)
    assert colours.keys() >= set_color_mode(mode).keys()
    assert all(isinstance(name, str) and isinstance(value, str) and value for name, value in colours.items())


# ##################################################################################
# The configuration history
# ##################################################################################
@st.composite
def histories(draw: st.DrawFn) -> tuple[list[bytes | None], list[str]]:
    """What each of two recorded snapshots holds afterwards (None: left alone), and extra file names in the folder."""
    held = [draw(st.one_of(st.none(), st.binary(max_size=40), spoiled(b"x" * 60, max_operations=2))) for _ in range(2)]
    names = draw(st.lists(st.text(alphabet="0123456789abcdef_-.:xz ", min_size=1, max_size=30), max_size=4))
    return held, names


@fuzz(60)
@given(history=histories(), real_gzip=st.data())
def test_a_damaged_history_is_a_message_not_a_crash(
    history: tuple[list[bytes | None], list[str]], real_gzip: st.DataObject
) -> None:
    held, extra_names = history
    with a_scratch_run(_SYNTHETIC) as path:
        prime_a_run()
        for number in range(2):
            path.write_bytes(_SYNTHETIC.replace(b"Remind Me", f"Remind Me {number}".encode()))
            with path.open(encoding="utf-8") as opened:
                PrimeItems.file_to_get = opened
                taskerd.get_the_xml_data(state=PrimeItems)
        folder = timeline.history_folder()
        assert folder is not None
        files = sorted(folder.iterdir())
        for snapshot_file, damage in zip(files, held, strict=False):
            if damage is None:
                continue
            body = damage
            if real_gzip.draw(st.booleans()):
                # A real gzip stream with its tail or a byte of its middle damaged: the shape a half-copied file has.
                packed = bytearray(gzip.compress(_SYNTHETIC))
                cut = real_gzip.draw(st.integers(min_value=0, max_value=len(packed) - 1))
                body = (
                    bytes(packed[:cut])
                    if real_gzip.draw(st.booleans())
                    else bytes(packed[:cut] + b"\xff" + packed[cut + 1 :])
                )
            snapshot_file.write_bytes(body)
        for name in extra_names:
            with contextlib.suppress(OSError, ValueError):
                (folder / name).write_bytes(b"not a snapshot")

        timeline.snapshots()
        timeline.since(timeline.clock.now())
        result = timecomp.changes_since(None, state=PrimeItems)

    assert isinstance(result, timecomp.Comparison)


# ##################################################################################
# A Version 2 Scene's layout
# ##################################################################################
_V2_LAYOUT: dict[str, Any] = {
    "name": "Panel",
    "defaultDisplayMode": "Dialog",
    "root": {
        "type": "Column",
        "id": "column1",
        "children": [
            {
                "type": "Text",
                "id": "text1",
                "text": "Hello %name",
                "modifiers": [{"type": "Padding", "all": 8}],
                "eventHandlers": {"onClick": {"task": "Reminder", "variables": ["%a", "%b"]}},
            },
            {"type": "Button", "id": "button1", "text": "OK", "eventHandlers": {"onClick": {"task": "Close"}}},
            {"type": "Row", "id": "row1", "children": [{"type": "Switch", "id": "switch1", "checked": "%flag"}]},
        ],
    },
}


def _blob(layout: Any) -> str:
    """A layout as Tasker stores it in <lj>: JSON, gzipped, Base64."""
    return base64.b64encode(gzip.compress(json.dumps(layout).encode("utf-8"), mtime=0)).decode("ascii")


@st.composite
def layout_blobs(draw: st.DrawFn) -> str:
    """The text of an <lj>: the real thing, reshaped, any JSON at all, or the Base64 with characters damaged."""
    good = _blob(_V2_LAYOUT)
    kind = draw(st.sampled_from(["reshaped", "any", "damaged", "text"]))
    if kind == "reshaped":
        return _blob(draw(reshaped(_V2_LAYOUT)))
    if kind == "any":
        return _blob(draw(JSON_VALUES))
    if kind == "damaged":
        return draw(spoiled(good.encode("ascii"), max_operations=3)).decode("latin-1")
    return draw(st.text(max_size=80))


@fuzz(400)
@given(text=layout_blobs())
def test_a_scene_layout_that_will_not_decode_is_a_message_not_an_exception(text: str) -> None:
    """decompress_gzip_json hands back an error message as text; decode_v2_layout turns that into None."""
    decoded = scenelayout.decompress_gzip_json(text)
    element = ET.fromstring("<Scene><nme>S</nme><lj/></Scene>")
    element.find("lj").text = text  # type: ignore[union-attr]
    layout = scenelayout.decode_v2_layout(element)

    assert layout is None or isinstance(layout, dict)
    if isinstance(decoded, str):
        assert layout is None


def _backup_with_a_scene(blob: str) -> bytes:
    """The synthetic backup with a Version 2 Scene added to its first Project, its layout being `blob`."""
    root = ET.fromstring(_SYNTHETIC)
    project = root.find("Project")
    assert project is not None
    scenes = project.find("scenes")
    assert scenes is not None
    scenes.text = f"{scenes.text},V2 Panel"
    scene = ET.SubElement(root, "Scene", sr="V2 Panel")
    ET.SubElement(scene, "nme").text = "V2 Panel"
    ET.SubElement(scene, "heightPort").text = "800"
    ET.SubElement(scene, "widthPort").text = "480"
    ET.SubElement(scene, "lj").text = blob
    return ET.tostring(root)


@pytest.mark.parametrize(
    "argv", [["-healthcheck"], ["-export", "map"], ["-export", "diagram"]], ids=["health", "map", "diagram"]
)
@fuzz(120)
@given(text=layout_blobs())
def test_a_spoiled_scene_layout_does_not_stop_a_report(argv: list[str], text: str) -> None:
    """The Map, the Diagram and the Health Check read every Scene's layout; a bad one is that Scene's problem alone."""
    with a_scratch_run(_backup_with_a_scene(text)) as path:
        code = clireports.run([*argv, "-file", str(path)])
    event(f"exit code {code}")
    assert code in DOCUMENTED_EXIT_CODES


# ##################################################################################
# What an AI model replies
# ##################################################################################
_PLAN_REPLY = {
    "name": "Say hello",
    "steps": [
        {"action": "548t", "purpose": "greet", "label": "Hello", "args": [{"id": "0", "value": "Hi %name"}]},
        {"action": "37t", "purpose": "check", "label": "", "args": []},
        {"action": "38t", "purpose": "", "label": "", "args": []},
    ],
    "unexpressed": "",
}
_DETAIL_REPLY = {"steps": [{"step": 1, "label": "Say it", "args": [{"id": "0", "value": "Hello"}]}]}


@st.composite
def replies(draw: st.DrawFn, base: dict[str, Any]) -> str:
    """A model's reply: the right object in prose or fencing, reshaped, any JSON, or the text damaged."""
    text = draw(json_documents(base))
    wrapper = draw(
        st.sampled_from(
            ["{}", "Sure! Here is the plan:\n{}\nHope that helps.", "```json\n{}\n```", "<think>{{}}</think>{}"]
        )
    )
    return wrapper.replace("{}", text) if draw(st.booleans()) else text


@fuzz(400)
@given(reply=replies(_PLAN_REPLY))
def test_the_first_reply_of_a_draft_is_a_plan_or_an_ask_error(reply: str) -> None:
    prime_a_run()
    try:
        plan = mapdraft.parse_plan(reply, PrimeItems)
    except mapask.AskError:
        event("refused")
        return
    event("a plan")
    assert isinstance(plan, mapdraft.Plan)


@fuzz(300)
@given(reply=replies(_DETAIL_REPLY))
def test_the_second_reply_of_a_draft_is_details_or_an_ask_error(reply: str) -> None:
    prime_a_run()
    plan = mapdraft.parse_plan(json.dumps(_PLAN_REPLY), PrimeItems)
    drafted = [mapdraft.DraftStep(step.action_key) for step in plan.steps]
    try:
        steps, dropped = mapdraft.parse_details(reply, plan, drafted, PrimeItems)
    except mapask.AskError:
        event("refused")
        return
    assert len(steps) == len(drafted)
    assert isinstance(dropped, list)


@fuzz(500)
@given(reply=st.one_of(replies(_PLAN_REPLY), st.text(max_size=200)))
def test_any_reply_is_an_object_or_an_ask_error(reply: str) -> None:
    try:
        parsed = mapask.reply_object(reply)
    except mapask.AskError:
        return
    assert isinstance(parsed, dict)


# ##################################################################################
# What the phone answers
# ##################################################################################
_GLOBALS_ANSWER = [
    {"name": "%Count", "value": base64.b64encode(b"3").decode("ascii")},
    {"name": "Name", "value": "plain text"},
    {"name": "", "value": None},
]
_TASKS_ANSWER = [{"name": "Reminder", "running": False}, {"name": "Open Reminder List", "running": True}]
_AUTH_ANSWER = {"key": "k-1234", "authorized": True}


class _Answer:
    """What http_request / requests hand back, with the body a fuzz test chose."""

    def __init__(self, text: str, status: int = 200) -> None:
        self.text = text
        self.content = text.encode("utf-8", errors="replace")
        self.status_code = status

    def json(self) -> Any:
        return json.loads(self.text)


@fuzz(400)
@given(text=json_documents(_GLOBALS_ANSWER))
def test_the_phones_list_of_globals_is_a_dict_or_none(text: str) -> None:
    from maptasker.src.gui import livevars

    assert livevars.parse_globals(text) is None or isinstance(livevars.parse_globals(text), dict)
    assert livevars.parse_globals(text.encode("utf-8")) is None or isinstance(
        livevars.parse_globals(text.encode()), dict
    )


@pytest.mark.parametrize("which", ["names_on_device", "fetch_names"])
@fuzz(250)
@given(text=json_documents(_TASKS_ANSWER))
def test_the_phones_list_of_tasks_is_an_answer_with_a_code_and_a_message(
    monkeypatch: pytest.MonkeyPatch, which: str, text: str
) -> None:
    """Three readers of GET api/tasks: each ends in (code, message, names) -- an answer, whatever the phone said."""
    from maptasker.src.device import deviceverify

    monkeypatch.setattr(deviceverify, "http_request", lambda *_args, **_kwargs: (0, text))
    monkeypatch.setattr(deviceverify, "auth_key_for", lambda *_args, **_kwargs: (0, "key"))
    if which == "names_on_device":
        answer = deviceverify.task_names_on_device("192.168.0.2", "1821", ["Reminder"])
    else:
        answer = deviceverify.fetch_task_names_from_device("192.168.0.2", "1821")
    assert isinstance(answer[0], int)
    assert isinstance(answer[1], str)
    assert isinstance(answer[2], list)


@fuzz(250)
@given(text=json_documents(_TASKS_ANSWER))
def test_which_of_my_names_the_phone_reports_is_a_set_or_none(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """None is "could not ask", which is not the empty set ("none of them are there")."""
    from maptasker.src.device import deviceverify

    monkeypatch.setattr(deviceverify, "http_request", lambda *_args, **_kwargs: (0, text))
    found = deviceverify.verify_names_on_android("192.168.0.2", "1821", "api/tasks", ["Reminder"], "key")
    assert found is None or (isinstance(found, set) and found <= {"Reminder"})


@fuzz(250)
@given(text=json_documents(_TASKS_ANSWER))
def test_confirming_a_saved_task_is_a_yes_or_a_no(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    from maptasker.src.edit import taskedit_save

    monkeypatch.setattr(taskedit_save, "http_request", lambda *_args, **_kwargs: (0, text))
    assert taskedit_save.verify_task_on_android("192.168.0.2", "1821", "Reminder", "key") in (True, False)


@fuzz(250)
@given(text=st.one_of(json_documents({"a": [1, 2]}), st.text(max_size=60)))
def test_a_tasks_return_value_is_shown_as_text(text: str) -> None:
    from maptasker.src.gui import guiwins_taskpickers

    assert isinstance(guiwins_taskpickers._format_task_output(text), str)


@fuzz(300)
@given(text=json_documents(_AUTH_ANSWER), status=st.sampled_from([200, 403, 500]))
def test_the_phones_answer_to_an_authorization_request_is_a_key_or_a_message(
    monkeypatch: pytest.MonkeyPatch, text: str, status: int
) -> None:
    from maptasker.src.core import maputil2

    monkeypatch.setattr(maputil2, "_device_call", lambda *_args, **_kwargs: (_Answer(text, status), "", False))
    code, result, retryable = maputil2._request_android_auth_key("http://192.168.0.2:1821/api/auth")
    assert isinstance(code, int)
    assert isinstance(result, str)
    assert retryable in (True, False)


@fuzz(150)
@given(data=spoiled(b'<?xml version="1.0"?><TaskerData><Task><id>1</id><nme>T</nme></Task></TaskerData>'))
def test_what_the_phone_sends_as_a_backup_is_a_document_or_nothing(data: bytes) -> None:
    from maptasker.src.device import devicecheck

    root = devicecheck.parse_tasker_xml(data)
    assert root is None or root.tag


# ##################################################################################
# What TaskerNet answers
# ##################################################################################
_SHARE_INFO = {"info": {"date": 1700000000000, "name": "N", "description": "D", "stats": {"views": 3, "downloads": 4}}}
_PUBLIC_PAGE = {
    "shares": [{"url": "https://taskernet.com/shares/?user=u&id=Project%3AN", "downloads": 3}],
    "pageToken": "",
}
_SHARE_DATA = {"shareData": "taskerproject://" + base64.b64encode(gzip.compress(b"<TaskerData/>")).decode("ascii")}


def _ref() -> Any:
    from maptasker.src.mapops import tnupdate

    return tnupdate.ShareRef("user", "Project:N", "Project", "N")


@fuzz(300)
@given(answer=reshaped(_SHARE_INFO))
def test_a_shares_details_are_read_or_taskernet_is_blamed(monkeypatch: pytest.MonkeyPatch, answer: Any) -> None:
    from maptasker.src.mapops import tnupdate

    assume(isinstance(answer, dict))
    monkeypatch.setattr(tnupdate, "_get_json", lambda *_args, **_kwargs: answer)
    try:
        info = tnupdate.fetch_info(_ref())
    except tnupdate.TaskerNetError:
        return
    assert isinstance(info.name, str)


@fuzz(300)
@given(answer=reshaped(_SHARE_DATA))
def test_a_shares_xml_is_text_or_taskernet_is_blamed(monkeypatch: pytest.MonkeyPatch, answer: Any) -> None:
    from maptasker.src.mapops import tnupdate

    assume(isinstance(answer, dict))
    monkeypatch.setattr(tnupdate, "_get_json", lambda *_args, **_kwargs: answer)
    try:
        text = tnupdate.fetch_xml(_ref())
    except tnupdate.TaskerNetError:
        return
    assert isinstance(text, str)


@fuzz(300)
@given(
    payload=st.one_of(
        st.text(max_size=80), spoiled(_SHARE_DATA["shareData"].encode()).map(lambda b: b.decode("latin-1"))
    )
)
def test_a_shares_data_is_unpacked_or_taskernet_is_blamed(payload: str) -> None:
    from maptasker.src.mapops import tnupdate

    try:
        assert isinstance(tnupdate.decode_share_data(payload), str)
    except tnupdate.TaskerNetError:
        return


@fuzz(300)
@given(page=reshaped(_PUBLIC_PAGE))
def test_a_page_of_taskernets_listing_is_read_as_far_as_it_makes_sense(
    monkeypatch: pytest.MonkeyPatch, page: Any
) -> None:
    """The catalogue is crawled page by page: a page that is the wrong shape ends the crawl, it does not raise."""
    import threading

    from maptasker.src.mapops import tnfind, tnupdate

    assume(isinstance(page, dict))
    monkeypatch.setattr(tnupdate, "fetch_public_page", lambda *_args, **_kwargs: page)
    monkeypatch.setattr(tnfind.time, "sleep", lambda _seconds: None)
    catalogue = tnfind.crawl_catalogue(tnfind.Progress(), threading.Event())
    assert isinstance(catalogue.entries, list)


# ##################################################################################
# The small files kept between sessions
# ##################################################################################
def _file_reader(label: str) -> tuple[Any, bytes, str]:
    """(a function that reads the file, a well-formed file for it, the name it is kept under) for one reader."""
    from maptasker.src.analysis import taskcases
    from maptasker.src.core import apikeys, appinv, resstore
    from maptasker.src.core.sysconst import APPS_CACHE_FILE, RESOURCES_CACHE_FILE
    from maptasker.src.mapops import tnfind, tnupdate

    if label == "apps":
        base = {
            "devices": {
                "192.168.0.2": {"fetched": "2026-01-01 00:00:00", "apps": [{"pkg": "a.b", "label": "A", "cls": "c"}]}
            }
        }
        return (
            (lambda _path: (appinv.read_cache(), appinv.fetched_devices(), appinv.fetched_packages())),
            json.dumps(base).encode(),
            APPS_CACHE_FILE,
        )
    if label == "resources":
        return (lambda _path: resstore._read()), json.dumps({"checked": {"a": {"b": 1}}}).encode(), RESOURCES_CACHE_FILE
    if label == "catalogue":
        base = {"version": 1, "fetched": "x", "complete": True, "shares": [["u", "Project:N", 3]]}
        return (lambda path: tnfind.load_catalogue(Path(path))), json.dumps(base).encode(), "catalogue.json"
    if label == "links":
        base = {"links": [{"kind": "Project", "name": "N", "user": "u", "share_id": "Project:N"}]}
        return (lambda path: tnupdate.LinkBook(Path(path))), json.dumps(base).encode(), "links.json"
    if label == "cases":
        return (
            (lambda path: taskcases.load_book(str(path))),
            json.dumps({"version": 1, "after_edit": True, "cases": []}).encode(),
            "cases.json",
        )
    base = {"openai_key": "k"}
    return (
        (lambda path: apikeys._parse_keys(Path(path).read_text(encoding="utf-8", errors="replace"), "test")),
        json.dumps(base).encode(),
        "keys.json",
    )


@pytest.mark.parametrize("label", ["apps", "resources", "catalogue", "links", "cases", "keys"])
@fuzz(200)
@given(data=st.data())
def test_a_damaged_cache_or_list_is_read_as_empty_not_as_a_crash(label: str, data: st.DataObject) -> None:
    """Each is a file the program wrote and a user may have touched; the reader's promise is that it never raises."""
    reader, good, name = _file_reader(label)
    body = data.draw(st.one_of(spoiled(good), json_documents(json.loads(good)).map(lambda text: text.encode("utf-8"))))
    with a_scratch_run(b"") as path:
        target = path.with_name(name)
        target.write_bytes(body)
        reader(target)


@fuzz(200)
@given(
    text=json_documents(
        {"digest": "d", "when": "2026-01-01T00:00:00", "source": "s", "total": {}, "projects": {}, "version": 1}
    )
)
def test_a_trend_snapshot_is_read_or_refused_in_the_way_it_says(text: str) -> None:
    from maptasker.src.mapops import trend

    try:
        trend.SnapshotMetrics.from_json(text)
    except (ValueError, KeyError, TypeError):
        return
