"""parse_tasker_xml: the standard library's C parser, and the entity check that stands in for defusedxml's."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.xmldata import parse_tasker_xml

if TYPE_CHECKING:
    from pathlib import Path

BACKUP = '<?xml version="1.0" encoding="UTF-8"?>\n<TaskerData sr="" dvi="1" tv="6.3.13"><Task sr="task1"><nme>Hello</nme></Task></TaskerData>'


def parse(tmp_path: Path, text: str) -> ET.Element:
    """The root of the backup that `text` is."""
    path = tmp_path / "backup.xml"
    path.write_bytes(text.encode("utf-8"))
    root = parse_tasker_xml(str(path)).getroot()
    assert root is not None
    return root


def test_a_backup_is_parsed_by_the_c_implementation(tmp_path: Path) -> None:
    """The pure-Python Element is several times slower to build and to search; this is what the switch is for."""
    root = parse(tmp_path, BACKUP)

    assert type(root) is ET.Element
    assert root.findtext("Task/nme") == "Hello"


@pytest.mark.parametrize(
    "prologue",
    [
        '<!DOCTYPE TaskerData [<!ENTITY x "expanded">]>',
        '<!DOCTYPE TaskerData [<!ENTITY % p "x"><!ENTITY y "%p;">]>',
        '<!DOCTYPE TaskerData [<!ENTITY secret SYSTEM "file:///etc/passwd">]>',
        '<!DOCTYPE TaskerData SYSTEM "http://example.invalid/evil.dtd" [<!ENTITY x "y">]>',
    ],
    ids=["internal", "parameter", "external file", "external dtd"],
)
def test_a_document_that_declares_an_entity_is_refused_as_a_parse_error(tmp_path: Path, prologue: str) -> None:
    text = BACKUP.replace("<TaskerData", f"{prologue}<TaskerData", 1)

    with pytest.raises(ET.ParseError, match="declares an XML entity"):
        parse(tmp_path, text)


def test_an_entity_bomb_is_refused_at_once_and_never_expanded(tmp_path: Path) -> None:
    lols = "".join(
        f'<!ENTITY l{n} "&l{n - 1};&l{n - 1};&l{n - 1};&l{n - 1};&l{n - 1};&l{n - 1};&l{n - 1};&l{n - 1};&l{n - 1};&l{n - 1};">'
        for n in range(1, 10)
    )
    text = BACKUP.replace("<TaskerData", f'<!DOCTYPE TaskerData [<!ENTITY l0 "lol">{lols}]><TaskerData', 1).replace(
        "Hello", "&l9;"
    )

    started = time.perf_counter()
    with pytest.raises(ET.ParseError):
        parse(tmp_path, text)

    assert time.perf_counter() - started < 1


def test_a_document_type_that_declares_nothing_is_still_read(tmp_path: Path) -> None:
    """Refusing entities is not refusing every DOCTYPE: defusedxml let this one through and so does this."""
    text = BACKUP.replace("<TaskerData", "<!DOCTYPE TaskerData><TaskerData", 1)

    assert parse(tmp_path, text).findtext("Task/nme") == "Hello"


def test_a_predefined_entity_in_the_text_is_still_read(tmp_path: Path) -> None:
    """&amp; and its kin are not declarations, and a name with an ampersand is ordinary."""
    text = BACKUP.replace("Hello", "Tom &amp; Jerry &lt;3")

    assert parse(tmp_path, text).findtext("Task/nme") == "Tom & Jerry <3"


def test_a_file_that_is_not_xml_is_a_parse_error(tmp_path: Path) -> None:
    with pytest.raises(ET.ParseError):
        parse(tmp_path, "this is not xml")
