"""editcommon Unit Tests -- the four editors' exports must stay one implementation.

These assert AGREEMENT, not behaviour in isolation.  projedit, profedit, taskedit and
sceneedit each kept private copies of the filename sanitizing, the save-path shapes and the
upload-and-verify flow, and the copies had already drifted in name (default_save_path in two
of them, default_project_save_path/default_scene_save_path in the other two) if not yet in
what they did.  A bug in any one of them was four bugs.

So most of what is below is parameterized over all four kinds at once and asserts they
differ ONLY where they are supposed to -- the fallback word, the extension and the device
folder.  A fifth editor added later, or one quietly given its own copy of a helper again,
fails here rather than in whichever export the user happens to run.

The upload tests fake maputil2's two HTTP calls.  What they are really pinning is ORDER:
the address is checked before the render is attempted, so a missing IP costs nothing and --
for the two kinds whose render can raise because the object was deleted since the dialog
opened -- a blank IP reports the blank IP rather than the deletion.
"""

from __future__ import annotations

import os

import pytest
from maptasker.src import deviceinv, editcommon, presave, profedit, projedit, sceneedit, taskedit

# Every editor, and the three things it is allowed to differ in.
#   module, EXPORT kind, fallback word, extension, device folder, its own path helper
EDITORS = [
    (projedit, "project", ".prj.xml", "Tasker/projects", "android_project_path", "default_project_save_path"),
    (profedit, "profile", ".prf.xml", "Tasker/profiles", "android_profile_path", "default_save_path"),
    (taskedit, "task", ".tsk.xml", "Tasker/tasks", "android_task_path", "default_save_path"),
    (sceneedit, "scene", ".scn.xml", "Tasker/scenes", "android_scene_path", "default_scene_save_path"),
]
IDS = [e[1] for e in EDITORS]


@pytest.mark.parametrize(("module", "fallback", "extension", "folder", "android", "default"), EDITORS, ids=IDS)
def test_each_editor_declares_only_what_makes_it_different(
    module: object,
    fallback: str,
    extension: str,
    folder: str,
    android: str,
    default: str,
) -> None:
    """Each editor's EXPORT holds its three differences and nothing else."""
    assert module.EXPORT == editcommon.EditorKind(fallback=fallback, extension=extension, android_location=folder)
    # The public names the GUI and the tests already call must still be there.
    assert callable(getattr(module, android))
    assert callable(getattr(module, default))


@pytest.mark.parametrize(("module", "fallback", "extension", "folder", "android", "default"), EDITORS, ids=IDS)
def test_sanitize_is_the_same_substitution_in_all_four(
    module: object,
    fallback: str,
    extension: str,  # noqa: ARG001
    folder: str,  # noqa: ARG001
    android: str,  # noqa: ARG001
    default: str,  # noqa: ARG001
) -> None:
    """Same characters replaced, same way, in every editor -- only the fallback differs."""
    assert module.sanitize_filename("Wake: Up") == "Wake_ Up"
    assert module.sanitize_filename("Home/Work") == "Home_Work"
    assert module.sanitize_filename(r'a\b:c*d?e"f<g>h|i') == "a_b_c_d_e_f_g_h_i"
    assert module.sanitize_filename("  spaced  ") == "spaced"
    # The fallback is for a name with nothing left in it, NOT one that was all illegal
    # characters -- those are substituted and kept, which is why '<>|' survives as '___'.
    assert module.sanitize_filename("") == fallback
    assert module.sanitize_filename("   ") == fallback
    assert module.sanitize_filename("<>|") == "___"


@pytest.mark.parametrize(("module", "fallback", "extension", "folder", "android", "default"), EDITORS, ids=IDS)
def test_save_and_device_paths_differ_only_in_extension_and_folder(
    module: object,
    fallback: str,
    extension: str,
    folder: str,
    android: str,
    default: str,
) -> None:
    """The local default path and the device path are one shape with the kind filled in."""
    assert getattr(module, default)("My Name") == os.path.join(os.getcwd(), f"My Name{extension}")
    assert getattr(module, android)("My Name") == f"/{folder}/My Name{extension}"
    # Derived from the *sanitized* name, which is what makes two names collide on one file.
    assert getattr(module, android)("Wake: Up") == getattr(module, android)("Wake_ Up")
    assert getattr(module, android)("") == f"/{folder}/{fallback}{extension}"


@pytest.mark.parametrize(("module", "fallback", "extension", "folder", "android", "default"), EDITORS, ids=IDS)
def test_save_path_exists_agrees_everywhere(
    module: object,
    fallback: str,  # noqa: ARG001
    extension: str,  # noqa: ARG001
    folder: str,  # noqa: ARG001
    android: str,  # noqa: ARG001
    default: str,  # noqa: ARG001
) -> None:
    """An empty path is not an existing file, in all four."""
    assert module.save_path_exists("") is False
    assert module.save_path_exists("pyproject.toml") is True
    assert module.save_path_exists("no_such_file_anywhere_xyz") is False


def test_the_non_editors_share_the_same_substitution() -> None:
    """deviceinv and presave used to re-spell the pattern because importing an editor
    would have been a cycle.  editcommon is below all of them, so they no longer do --
    and deviceinv's staged path has to keep landing on the editor's own device path.
    """
    assert presave.ILLEGAL_IN_FILENAME is editcommon.ILLEGAL_IN_FILENAME
    for name in ("Opener", "Wake: Up", "a/b", ""):
        assert deviceinv.staged_paths("Tasker/tasks", name, "tsk.xml", "task")[1] == taskedit.android_task_path(name)


def test_set_child_text_is_one_function_not_four() -> None:
    """All four editors bind the same object, so a fix to it cannot reach only some."""
    bound = {projedit._set_child_text, profedit._set_child_text, taskedit._set_child_text, sceneedit._set_child_text}
    assert bound == {editcommon.set_child_text}


# --------------------------------------------------------------------------------------
# The upload/verify flow.
# --------------------------------------------------------------------------------------
@pytest.fixture
def fake_device(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stand in for the two maputil2 HTTP calls, recording what the upload was handed.

    'renders' counts how many times a render was asked for, which is what the
    address-first ordering test reads.
    """
    from maptasker.src import maputil2

    state: dict = {"upload_result": (0, "ok"), "read_result": (0, b"<TaskerData/>"), "renders": 0, "upload_args": None}

    def fake_upload(ip: str, port: str, location: str, filename: str, data: bytes) -> tuple:
        state["upload_args"] = (ip, port, location, filename, data)
        return state["upload_result"]

    def fake_read(ip: str, port: str, path: str, sent: bytes) -> tuple:  # noqa: ARG001
        return state["read_result"]

    monkeypatch.setattr(maputil2, "http_upload_request", fake_upload)
    monkeypatch.setattr(maputil2, "read_back_uploaded_file", fake_read)

    def counted(*_args: object, **_kwargs: object) -> str:
        state["renders"] += 1
        return "<TaskerData/>"

    for module, attribute in (
        (projedit, "render_standalone_project_xml"),
        (profedit, "render_standalone_profile_xml"),
        (taskedit, "render_standalone_task_xml"),
        (sceneedit, "render_standalone_scene_xml"),
    ):
        monkeypatch.setattr(module, attribute, counted)
    return state


def _save_calls(ip: str, port: str) -> list[tuple[str, object]]:
    """The four editors' save-to-device entry points, called with this address."""
    return [
        ("project", lambda: projedit.save_project_to_android("Home/Work", ip, port)),
        ("profile", lambda: profedit.save_profile_to_android(None, ip, port, "Morning")),
        ("scene", lambda: sceneedit.save_scene_to_android("Dialog", ip, port)),
        ("task", lambda: taskedit.save_task_to_android_file(None, ip, port, "Opener")),
    ]


@pytest.mark.parametrize(("ip", "port"), [("", "1821"), ("1.2.3.4", ""), ("   ", "  ")])
def test_a_missing_address_is_reported_before_anything_is_rendered(
    fake_device: dict,
    ip: str,
    port: str,
) -> None:
    """No render, no request -- the same refusal and the same wording in all four."""
    for label, call in _save_calls(ip, port):
        fake_device["renders"] = 0
        assert call() == (8, "Android IP address and port are required."), label
        assert fake_device["renders"] == 0, f"{label} rendered before checking the address"
        assert fake_device["upload_args"] is None, label


def test_a_successful_save_uploads_to_the_kinds_own_folder(fake_device: dict) -> None:
    """Folder, filename and returned path all come from the one EditorKind."""
    expected = {
        "project": ("Tasker/projects", "Home_Work.prj.xml"),
        "profile": ("Tasker/profiles", "Morning.prf.xml"),
        "scene": ("Tasker/scenes", "Dialog.scn.xml"),
        "task": ("Tasker/tasks", "Opener.tsk.xml"),
    }
    for label, call in _save_calls("1.2.3.4", "1821"):
        folder, filename = expected[label]
        assert call() == (0, f"/{folder}/{filename}"), label
        assert fake_device["upload_args"][2:] == (folder, filename, b"<TaskerData/>"), label


def test_an_upload_failure_is_passed_straight_back(fake_device: dict) -> None:
    """The transport's own code and message, unchanged -- not flattened to 8."""
    fake_device["upload_result"] = (7, "connection refused")
    for label, call in _save_calls("1.2.3.4", "1821"):
        assert call() == (7, "connection refused"), label


def test_a_failed_readback_fails_the_save(fake_device: dict) -> None:
    """/upload answers 200 for a bogus location, so only the readback proves the write."""
    fake_device["read_result"] = (4, "bytes on device do not match")
    for label, call in _save_calls("1.2.3.4", "1821"):
        assert call() == (8, "bytes on device do not match"), label


def test_the_task_upload_hands_back_what_the_device_holds(fake_device: dict) -> None:
    """Task is the one caller that keeps the third value -- it posts those bytes to
    api/import, so what reaches Tasker is provably the file in the folder rather than a
    second render nothing has checked.
    """
    assert taskedit._put_task_file_on_android(None, "1.2.3.4", "1821", "Opener") == (
        0,
        "/Tasker/tasks/Opener.tsk.xml",
        b"<TaskerData/>",
    )


def test_a_render_that_raises_is_reported_by_the_kinds_that_can_raise(
    fake_device: dict,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Project and Scene render from the live tables by name, so the object can be gone
    by the time the button is pressed.  That stays a (8, message), not a traceback.
    """

    def deleted(*_args: object, **_kwargs: object) -> str:
        message = "Project 'Home/Work' no longer exists."
        raise ValueError(message)

    monkeypatch.setattr(projedit, "render_standalone_project_xml", deleted)
    monkeypatch.setattr(sceneedit, "render_standalone_scene_xml", deleted)
    assert projedit.save_project_to_android("Home/Work", "1.2.3.4", "1821") == (
        8,
        "Project 'Home/Work' no longer exists.",
    )
    assert sceneedit.save_scene_to_android("Dialog", "1.2.3.4", "1821") == (8, "Project 'Home/Work' no longer exists.")
