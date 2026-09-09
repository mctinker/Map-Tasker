"""editcommon: the naming, XML-child and device-upload steps the four object editors do identically.

projedit, profedit, taskedit and sceneedit each build an editable model of one kind of
Tasker object and export it, and the export is the same export four times over: turn the
object's name into a legal filename, work out where that file goes locally and on the
device, and -- for Save To Android -- upload it and read it back to prove it landed.
Only three things actually differ between them, and they are what EditorKind holds.

Kept as a module of its own, below all four editors in the import order, because the
duplication had already spread past them: deviceinv and presave each re-spell the
illegal-character substitution too, both with a comment saying they would rather have
imported it but that importing an editor would be a cycle.  Nothing here imports an
editor, so that reason is gone and they import this instead.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import defusedxml.ElementTree

# Characters a Tasker name is free to contain and a filename is not.  Public because
# presave flattens a whole device path with it rather than sanitizing one name.  Tasker names are
# free text -- "Wake: Up" and "Home/Work" are ordinary names -- and every one of these
# would either be rejected by the filesystem or change what the path means.
ILLEGAL_IN_FILENAME = re.compile(r'[\\/:*?"<>|]')

# What a failed upload's readback answers with when there is nothing to hand back.
_NO_BYTES = b""


def set_child_text(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    """Set (creating if need be) one child's text.

    Builds a new child with the parent's own class rather than ETW.SubElement: the tree
    being edited is parsed by defusedxml, whose hardened XMLParser forces the pure-Python
    Element implementation, and .append() enforces an exact type match -- so a
    stdlib-class child would be refused.
    """
    child = parent.find(tag)
    if child is None:
        child = type(parent)(tag)
        parent.append(child)
    child.text = text


def save_path_exists(output_path: str) -> bool:
    """Whether a file already sits at this save path (would be silently overwritten)."""
    return bool(output_path) and os.path.exists(output_path)


def sanitize_filename(name: str, fallback: str) -> str:
    """Strip characters illegal in filenames from an object's name (minimal, not a full slugify).

    `fallback` is what a name with nothing left in it becomes -- one that was empty or
    only whitespace.  A name of nothing BUT illegal characters does not reach it: those
    are substituted, not dropped, so '<>|' sanitizes to '___' and keeps it.

    Two different names can still sanitize onto one filename ("Wake: Up" and "Wake_ Up"
    both become "Wake_ Up"), which is the collision the save buttons' overwrite prompt
    exists to catch -- see EditorKind.android_path.
    """
    return ILLEGAL_IN_FILENAME.sub("_", name).strip() or fallback


@dataclass(frozen=True)
class EditorKind:
    """What one editor's exports need to know that the other three's don't.

    One instance per editor, built at import time beside that editor's own
    ANDROID_*_LOCATION and named EXPORT in all four (projedit.EXPORT, profedit.EXPORT,
    taskedit.EXPORT, sceneedit.EXPORT -- not PROJECT/PROFILE/TASK/SCENE, which mapjump
    already uses for these same four kinds as plain strings).  Everything else about an
    export is the same for all four and lives on this class.
    """

    # What a name with nothing usable left in it falls back to: "project", "task", ...
    fallback: str
    # The compound extension Tasker's own single-object exports use: ".prj.xml", ...
    extension: str
    # Destination folder on the Android device for Save To Android: "Tasker/projects", ...
    android_location: str

    def sanitize_filename(self, name: str) -> str:
        """This kind's name-to-filename substitution, with its own fallback."""
        return sanitize_filename(name, self.fallback)

    def default_save_path(self, name: str) -> str:
        """Default standalone-export path: {current runtime directory}/{sanitized name}{extension}.

        Uses os.getcwd() (the directory the app is running from) rather than the loaded
        backup file's directory -- the backup is picked from wherever the user keeps
        their XML (see getxml_event/local_xml_start_directory in userintr.py), which
        isn't necessarily where an exported object should land.
        """
        return os.path.join(os.getcwd(), f"{self.sanitize_filename(name)}{self.extension}")

    def android_path(self, name: str) -> str:
        """The absolute path a Save To Android of this object would write to on the device.

        Single source of truth for that path: the upload writes here and the GUI's
        overwrite check reads it back through maputil2.read_android_file, so the two must
        never drift apart.  Derived from the *sanitized* name, so two differently-named
        objects can map to one file ("Home/Work" and "Home_Work" both become
        "Home_Work") and a blank name lands on "{fallback}{extension}" -- the overwrite
        prompt this feeds is the only thing standing between those collisions and silent
        data loss, since /upload itself reports success either way.
        """
        return f"/{self.android_location}/{self.sanitize_filename(name)}{self.extension}"

    def upload_and_verify(
        self,
        ip_address: str,
        ip_port: str,
        object_name: str,
        render_bytes: Callable[[], bytes],
    ) -> tuple[int, str, bytes]:
        """Write the object onto the device's storage and hand back WHAT THE DEVICE NOW HOLDS.

        Returns (0, device_file_path, bytes_read_back) or (return_code, error_message, b"").

        THIS IS NOT AN IMPORT: nothing reaches Tasker's live configuration, Tasker does
        not watch these directories, and the file simply sits there for the user or their
        own device-side automation to pick up.  It also needs no authorization -- /upload
        takes no Authorization header, so unlike the api/import route there is no key to
        cache and no prompt on the device.  (taskedit.save_task_to_android does this write
        and then imports what it wrote; that second step is Task-only and stays there.)

        The readback is the point.  /upload answers 200 even for a nonexistent or bogus
        location -- it silently creates missing folders and never reports failure at the
        HTTP layer -- so a 200 alone proves nothing.  The bytes come back as the third
        value rather than being compared and dropped because one caller posts them
        onward: reading twice would leave the verified bytes and the imported bytes as
        separate facts about the device, which is exactly the gap where they could differ.

        `render_bytes` is called only once the address has been checked, so a missing IP
        costs nothing.  Anything it raises -- ValueError, where the object has been
        deleted since the dialog opened -- is the caller's to catch, since only the
        caller knows whether its render can raise at all.
        """
        # Lazy import to avoid a circular-import error (mirrors getbakup.get_backup_file()).
        from maptasker.src.maputil2 import http_upload_request, read_back_uploaded_file  # noqa: PLC0415

        ip_address = ip_address.strip()
        ip_port = ip_port.strip()
        if not ip_address or not ip_port:
            return 8, "Android IP address and port are required.", _NO_BYTES

        xml_bytes = render_bytes()
        device_path = self.android_path(object_name)
        filename = device_path.rsplit("/", 1)[-1]

        return_code, response = http_upload_request(
            ip_address,
            ip_port,
            self.android_location,
            filename,
            xml_bytes,
        )
        if return_code != 0:
            return return_code, str(response), _NO_BYTES

        # Retried rather than trusted: /upload is a Tasker Task writing to storage and this
        # read is a second request answered by a second Task, so a write still settling
        # answers 404 to a read that arrives too soon -- and failing on the first miss
        # aborts a save whose file is on the device a moment later.  See
        # maputil2.read_back_uploaded_file.
        verify_code, verify_content = read_back_uploaded_file(ip_address, ip_port, device_path, xml_bytes)
        if verify_code != 0:
            return 8, str(verify_content), _NO_BYTES

        return 0, device_path, verify_content
