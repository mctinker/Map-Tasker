"""Reading a backup in whatever encoding it is in, and never writing to it.

Tasker writes UTF-8, but a backup is a file that has been through other hands: saved by an editor in another
encoding, converted by a tool, copied by something that added a byte-order mark.  The loader reads it as the
encoding it is in -- a byte-order mark first, then UTF-8, then what the XML declaration names -- and parses a copy in
memory.  It used to repair an unreadable one by deleting the file and renaming a rewritten copy over it, so a crash
in between lost the backup; nothing now writes to the file, which is the guarantee these tests state.
"""

from __future__ import annotations

import codecs
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from maptasker.src.core import xmldata
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapgen import taskerd

from tests.doubles import required

NAME = "Café 日本 🙂"
BODY = f'<TaskerData sr="" dvi="1" tv="6.3.13"><Task sr="task1"><id>1</id><nme>{NAME}</nme></Task></TaskerData>'


def _document(declaration: str = "UTF-8") -> str:
    return f'<?xml version="1.0" encoding="{declaration}"?>\n{BODY}\n'


def _file(tmp_path: Path, data: bytes, name: str = "backup.xml") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _name_in(path: Path) -> str | None:
    return required(xmldata.parse_tasker_xml(str(path)).getroot()).findtext("Task/nme")


# ##################################################################################
# Every encoding a backup might be in
# ##################################################################################
@pytest.mark.parametrize(
    ("label", "encode"),
    [
        ("UTF-8", lambda text: text.encode("utf-8")),
        ("UTF-8 with a byte-order mark", lambda text: codecs.BOM_UTF8 + text.encode("utf-8")),
        ("UTF-16 with a mark, little-endian", lambda text: codecs.BOM_UTF16_LE + text.encode("utf-16-le")),
        ("UTF-16 with a mark, big-endian", lambda text: codecs.BOM_UTF16_BE + text.encode("utf-16-be")),
        ("UTF-16 with no mark, little-endian", lambda text: text.encode("utf-16-le")),
        ("UTF-16 with no mark, big-endian", lambda text: text.encode("utf-16-be")),
        ("UTF-32 with a mark", lambda text: codecs.BOM_UTF32_LE + text.encode("utf-32-le")),
    ],
)
def test_a_backup_is_read_in_the_encoding_it_is_in(tmp_path: Path, label: str, encode) -> None:
    declaration = "UTF-16" if "UTF-16" in label else "UTF-32" if "UTF-32" in label else "UTF-8"
    path = _file(tmp_path, encode(_document(declaration)))

    assert _name_in(path) == NAME, label


def test_a_latin_1_backup_is_read_by_the_encoding_it_declares(tmp_path: Path) -> None:
    """Forcing UTF-8 on it, as the loader once did, refused a file that says plainly what it is."""
    latin = '<?xml version="1.0" encoding="ISO-8859-1"?>\n<TaskerData><Task><nme>Café Zoë</nme></Task></TaskerData>\n'
    path = _file(tmp_path, latin.encode("latin-1"))

    assert _name_in(path) == "Café Zoë"


def test_a_file_that_declares_the_wrong_encoding_but_is_utf_8_is_read_as_utf_8(tmp_path: Path) -> None:
    """The bytes win over the label: an editor that changed the declaration and not the text must not make mojibake."""
    path = _file(tmp_path, _document("ISO-8859-1").encode("utf-8"))

    assert _name_in(path) == NAME


@pytest.mark.parametrize("declaration", ["", ' encoding="no-such-encoding"', ' encoding="shift_jis" '])
def test_bytes_that_cannot_be_read_are_refused_not_guessed_at(tmp_path: Path, declaration: str) -> None:
    """Not UTF-8, and no declaration that decodes them: a message, rather than a file read as the wrong thing."""
    data = f'<?xml version="1.0"{declaration}?>\n<TaskerData><nme>caf'.encode() + b"\xe9\xff\xfe</nme></TaskerData>"
    path = _file(tmp_path, data)

    with pytest.raises(UnicodeDecodeError):
        xmldata.parse_tasker_xml(str(path))


def test_attributes_run_together_are_still_repaired_in_any_encoding(tmp_path: Path) -> None:
    """Tasker 6.7.6-beta writes <TaskerData sr=""dvi="1">, which the repair handles; encoding must not undo that."""
    compact = (
        f'<?xml version="1.0" encoding="UTF-16"?>\n<TaskerData sr=""dvi="1"><Task><nme>{NAME}</nme></Task></TaskerData>'
    )
    path = _file(tmp_path, codecs.BOM_UTF16_LE + compact.encode("utf-16-le"))

    assert _name_in(path) == NAME


# ##################################################################################
# The file is never written
# ##################################################################################
@pytest.mark.parametrize(
    "data",
    [
        _document().encode("utf-8"),
        codecs.BOM_UTF16_LE + _document("UTF-16").encode("utf-16-le"),
        _document("ISO-8859-1").replace(NAME, "Café").encode("latin-1"),  # read as it declares
        b"<?xml version='1.0'?>\n<TaskerData><nme>caf\xe9\xff",  # unreadable
        b"<TaskerData><Task></TaskerData>",  # not well-formed
        b"",
    ],
    ids=["utf-8", "utf-16", "latin-1", "unreadable", "not well-formed", "empty"],
)
def test_loading_a_backup_leaves_the_file_exactly_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: bytes
) -> None:
    """Whether it loads or is refused, the file's bytes are the same afterwards and nothing is left beside it."""
    monkeypatch.chdir(tmp_path)
    path = _file(tmp_path, data)
    before = sorted(entry.name for entry in tmp_path.iterdir())

    with open(path, encoding="latin-1") as opened:
        PrimeItems.file_to_get = opened
        try:
            taskerd.get_the_xml_data(state=PrimeItems)
        except MapTaskerError:
            pass

    assert path.read_bytes() == data
    # The history folder is made by a successful load; what must not appear is a temporary rewrite.
    assert not (tmp_path / ".maptasker_tmp.xml").exists()
    assert {entry.name for entry in tmp_path.iterdir()} - set(before) <= {"MapTasker_Timeline"}


def test_a_backup_that_cannot_be_read_is_a_maptasker_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The load's contract: an unreadable file ends the load with a message, never a UnicodeDecodeError."""
    monkeypatch.chdir(tmp_path)
    path = _file(tmp_path, b"<TaskerData><nme>caf\xe9\xff</nme></TaskerData>")

    with open(path, encoding="latin-1") as opened:
        PrimeItems.file_to_get = opened
        with pytest.raises(MapTaskerError) as raised:
            taskerd.get_the_xml_data(state=PrimeItems)

    assert raised.value.exit_code == 1
    assert "backup.xml" in raised.value.message


def test_the_destructive_rewrite_is_gone() -> None:
    """The functions that deleted a backup and renamed a rewritten copy over it do not exist to be called."""
    assert not hasattr(xmldata, "rewrite_xml")
    assert not hasattr(xmldata, "append_files")


def test_the_utf_8_a_tasker_backup_is_in_is_not_copied(tmp_path: Path) -> None:
    """The ordinary case costs nothing extra: the bytes read are the bytes parsed."""
    data = _document().encode("utf-8")

    assert xmldata.backup_as_utf8(data) is data
    assert ET.fromstring(xmldata.backup_as_utf8(data)).findtext("Task/nme") == NAME
