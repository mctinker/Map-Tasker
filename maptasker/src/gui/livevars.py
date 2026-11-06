"""Live variable values: what Tasker on the phone holds for each global right now."""

#! /usr/bin/env python3

#                                                                                      #
# livevars: Read the current value of every global variable from the Android device,    #
#           through Tasker's HTTP API, for varxref to set beside what the XML says.     #
#                                                                                      #
# The device half only.  varxref takes the LiveValues this returns and knows nothing     #
# about HTTP, so the report stays testable without a phone -- and so a report built with #
# no device (the usual case) is exactly the report it always was.                        #
#                                                                                      #
# READ, AND ONE WRITE.  fetch_live_values only reads.  set_global is the single thing   #
# here that changes the phone: it sets ONE global to ONE value, on the user's say-so,    #
# from the Variable Manager, and reads it back before it says it worked.                 #
#                                                                                      #
# UNVERIFIED, like the other api/* endpoints MapTasker did not write (see               #
# Tasker_API.md): that GET api/globals with no 'name' answers every user-defined global. #
# Its documentation says 'name' is optional and repeatable, and the Task behind it       #
# builds its list the way GET api/tasks does -- so this asks for the whole list once,    #
# rather than once per variable, and treats an answer that is not a list as a failure    #
# to read rather than as 'there are no globals'.                                         #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from typing import cast
from urllib.parse import quote

from maptasker.src.core.maputil2 import (
    LIST_READ_TIMEOUT_SECONDS,
    auth_key_for,
    http_post_request,
    http_request,
    request_with_auth_key,
)

GLOBALS_ENDPOINT = "api/globals"


@dataclass
class LiveValues:
    """The globals one device reported, at one moment."""

    address: str  # "192.168.0.210:1821"
    # "%Name" -> its value, decoded.  A global holding nothing is present with "" -- present
    # and empty are different answers from absent, and the report says so.
    values: dict[str, str] = field(default_factory=dict[str, str])

    def has(self, name: str) -> bool:
        """Whether the device holds a global of exactly this name (case counts, as in Tasker)."""
        return name in self.values

    def value(self, name: str) -> str:
        """That global's value, or "" when it has none or is not there -- has() tells those apart."""
        return self.values.get(name, "")


def _decode_value(raw: object) -> str:
    """A global's value from the API's Base64 text.

    Falls back to the text as received when it does not decode: an answer that is not
    Base64 is a server doing something this was not written for, and showing what it said
    is better than showing nothing, or dropping the variable and calling it absent.
    """
    if raw is None:
        return ""
    text = str(raw)
    try:
        return base64.b64decode(text, validate=True).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return text


def parse_globals(response: object) -> dict[str, str] | None:
    """{"%Name": value} from a GET api/globals answer, or None if it is not one.

    The API lists {"name", "value"} objects; the name arrives with or without its leading
    '%', so both spellings are made one -- the index names every variable with it.
    """
    if not isinstance(response, (str, bytes, bytearray)):
        return None
    try:
        reported = json.loads(response)
    except ValueError:
        return None
    if not isinstance(reported, list):
        return None

    values: dict[str, str] = {}
    for entry in cast("list[object]", reported):
        if not isinstance(entry, dict):
            continue
        fields = cast("dict[str, object]", entry)
        if not fields.get("name"):
            continue
        values[f"%{str(fields['name']).lstrip('%')}"] = _decode_value(fields.get("value"))
    return values


def fetch_live_values(ip_address: str, ip_port: str) -> tuple[int, str, LiveValues | None]:
    """Every global on the device.  (0, "", LiveValues) or (return_code, message, None).

    One GET, answered from the device's own list, so slow in proportion to how many globals
    it holds -- hence the long timeout the other list-everything reads use.

    Blocking, like every other call here; a caller on the GUI thread must use run.io_bound.
    """
    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.", None

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key, None

    return_code, response = http_request(
        ip_address,
        ip_port,
        "",
        GLOBALS_ENDPOINT,
        "",
        auth_key,
        timeout=LIST_READ_TIMEOUT_SECONDS,
    )
    if return_code != 0:
        return return_code, str(response), None

    values = parse_globals(response)
    if values is None:
        return 8, "The device's global variables were not readable as the list they should be.", None
    return 0, "", LiveValues(address=f"{ip_address}:{ip_port}", values=values)


# What the 'POST Globals' Task in Tasker's HTTP API project accepts as a name (read from the Task itself, in the
# sample backup): no spaces or '%', at least one capital letter -- which is what makes a name global -- and at least
# three characters.  Anything else it answers with a 400 and sets nothing, so it is refused here, in words, first.
_ACCEPTED_NAME = re.compile(r"^[^\s%]*[A-Z][^\s%]*$")
_MIN_NAME_LENGTH = 3

_JSON_TYPE = "application/json"


def _name_problem(name: str) -> str:
    """Why the device would refuse this name, or "" when it would take it."""
    if not _ACCEPTED_NAME.match(name) or len(name) < _MIN_NAME_LENGTH:
        return (
            f"'%{name}' cannot be set through Tasker's HTTP API: a global's name needs a capital letter, at least "
            "three characters, and no spaces."
        )
    return ""


def read_global(ip_address: str, ip_port: str, name: str, auth_key: str) -> tuple[int, str, str | None]:
    """What one global holds on the device.  (0, "", its value), (0, "", None) when it has none, or (code, message, None)."""
    query = f"?name={quote(name.lstrip('%'))}"
    return_code, response = http_request(
        ip_address, ip_port, "", GLOBALS_ENDPOINT, query, auth_key, timeout=LIST_READ_TIMEOUT_SECONDS
    )
    if return_code != 0:
        return return_code, str(response), None
    values = parse_globals(response)
    if values is None:
        return 8, "The device's answer about that variable was not readable as the list it should be.", None
    return 0, "", values.get(f"%{name.lstrip('%')}")


def set_global(ip_address: str, ip_port: str, name: str, value: str) -> tuple[int, str]:
    """Set one global on the device to this value, and read it back.  (0, a sentence) or (return_code, message).

    The value goes as Base64, which is how the API passes one both ways (see _decode_value).  The write is not
    believed on the strength of the 200: the device is asked for the variable again, and only an answer that
    matches is reported as done -- the same rule every other write to the device here follows.

    An empty value is refused.  The API reads an empty one as "clear this global", which is a different thing to
    ask and not what a person pushing a value means.

    Blocking, like every other call here; a caller on the GUI thread must use run.io_bound.
    """
    ip_address, ip_port = ip_address.strip(), ip_port.strip()
    bare = name.strip().lstrip("%")
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed."
    if problem := _name_problem(bare):
        return 8, problem
    if not value:
        return 8, f"%{bare} was not sent: an empty value would clear it on the device, and nothing was changed."

    body = json.dumps({"name": bare, "value": base64.b64encode(value.encode("utf-8")).decode("ascii")}).encode("utf-8")
    return_code, response = request_with_auth_key(
        ip_address,
        ip_port,
        lambda key: http_post_request(ip_address, ip_port, "", GLOBALS_ENDPOINT, body, key, _JSON_TYPE),
    )
    if return_code != 0:
        return return_code, str(response)

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key
    return_code, message, held = read_global(ip_address, ip_port, bare, auth_key)
    if return_code != 0:
        return return_code, f"%{bare} was sent, but reading it back failed: {message}"
    if held != value:
        shown = "it has no value" if held is None else f"it holds '{held}'"
        return 8, f"%{bare} was sent, but the device does not hold what was sent: {shown}."
    return 0, f"%{bare} is now set on {ip_address}:{ip_port}."


def delete_global(ip_address: str, ip_port: str, name: str) -> tuple[int, str]:
    """Remove one global from the device, and read it back.  (0, a sentence) or (return_code, message).

    The 'POST Globals' Task in Tasker's HTTP API project clears a global when it is sent no value, and says so by
    answering with a null one.  So this posts the name with a JSON null, and -- as set_global does -- does not believe
    the 200: the device is asked for the variable again, and only an answer that has no such variable is reported as
    done.  A variable the device never had is therefore a success: it is not there, which is what was asked for.

    Blocking, like every other call here; a caller on the GUI thread must use run.io_bound.
    """
    ip_address, ip_port = ip_address.strip(), ip_port.strip()
    bare = name.strip().lstrip("%")
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed."
    if problem := _name_problem(bare):
        return 8, problem

    body = json.dumps({"name": bare, "value": None}).encode("utf-8")
    return_code, response = request_with_auth_key(
        ip_address,
        ip_port,
        lambda key: http_post_request(ip_address, ip_port, "", GLOBALS_ENDPOINT, body, key, _JSON_TYPE),
    )
    if return_code != 0:
        return return_code, str(response)

    return_code, auth_key = auth_key_for(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key
    return_code, message, held = read_global(ip_address, ip_port, bare, auth_key)
    if return_code != 0:
        return return_code, f"%{bare} was sent, but reading it back failed: {message}"
    if held is not None:
        return 8, f"%{bare} was asked to be cleared, but the device still holds '{held}'."
    return 0, f"%{bare} is no longer on {ip_address}:{ip_port}."
