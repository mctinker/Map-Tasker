"""What the device said, when it answers a request with a status that means no."""

from __future__ import annotations

import requests
from maptasker.src.core import maputil2


def _response(status: int, body: bytes) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = body
    return response


def test_a_refusal_with_a_reason_carries_the_reason() -> None:
    message = maputil2._status_failure("http://x/api/import", _response(400, b"  Task id 2061 already exists  "))

    assert message.endswith("with status code 400.  The device said: Task id 2061 already exists")


def test_a_refusal_with_no_body_is_the_plain_message() -> None:
    message = maputil2._status_failure("http://x/api/import", _response(400, b""))

    assert message == "Request failed for url: http://x/api/import ...with status code 400"


def test_a_long_body_is_cut_short() -> None:
    message = maputil2._status_failure("http://x", _response(500, b"x" * 5000))

    assert len(message) < 400
