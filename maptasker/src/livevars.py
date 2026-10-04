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
# READ-ONLY.  The API can also set a global (POST api/globals); nothing here uses it.    #
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
from dataclasses import dataclass, field

from maptasker.src.maputil2 import LIST_READ_TIMEOUT_SECONDS, auth_key_for, http_request

GLOBALS_ENDPOINT = "api/globals"


@dataclass
class LiveValues:
    """The globals one device reported, at one moment."""

    address: str  # "192.168.0.210:1821"
    # "%Name" -> its value, decoded.  A global holding nothing is present with "" -- present
    # and empty are different answers from absent, and the report says so.
    values: dict[str, str] = field(default_factory=dict)

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
    try:
        reported = json.loads(response)
    except (ValueError, TypeError):
        return None
    if not isinstance(reported, list):
        return None

    values = {}
    for entry in reported:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        values[f"%{str(entry['name']).lstrip('%')}"] = _decode_value(entry.get("value"))
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
