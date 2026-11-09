"""A Tasker HTTP Server on the loopback address, for tests that talk to a phone without one.

MapTasker's device layer speaks to the Tasker "HTTP Server Example" project: it asks for an API key, uploads files,
reads them back, imports Tasks, lists what Tasker holds, and runs Tasks whose only output is a file they write.  This
is that server -- a real one, on a real socket, so the code under test makes its real requests with its real
`requests` calls -- with a phone's storage and a Tasker's object lists held in plain dictionaries a test can set up
beforehand and inspect afterwards.

What it does not do is run Tasks.  A test says what a Task does when it is run -- `fake.on_task(name, handler)` -- and
the handler writes the file the real Task would have written.  Importing a Task makes it exist; running one that
does not exist answers 404, as Tasker's handler does.

Faults a phone has are switches: `refuse_auth` answers "not authorized" that many times before it relents, `reject_keys`
answers 401 to the next requests that carry the key, `slow_reads` makes a file appear only on the Nth read, and
`down()` stops it listening.
"""

from __future__ import annotations

import json
import threading
import time
from email import message_from_bytes
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from collections.abc import Callable

KEY = "fake-api-key"


class FakeTasker:
    """The phone: storage, Tasker's objects, and the server that exposes them."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.tasks: set[str] = set()
        self.profiles: set[str] = set()
        self.scenes: set[str] = set()
        self.handlers: dict[str, Callable[[FakeTasker, dict[str, Any]], str | None]] = {}
        self.requests: list[tuple[str, str]] = []  # (method, path-and-query) in the order they arrived
        self.refuse_auth = 0
        self.reject_keys = 0
        self.slow_reads: dict[str, int] = {}  # path -> reads that answer 404 before the file shows
        self.list_seconds = 0.0  # how long a Task, Profile or Scene list or lookup takes to answer: a big configuration
        self.import_answers = 200
        self.import_script: list[int] = []  # the next imports' statuses, one each, before import_answers applies
        self.ignored_imports: set[str] = set()  # names Tasker answers 200 for and does not commit
        self.imports_uploads_ending: list[str] = []  # an upload ending so is imported at once: the user taps Import
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ##################################################################################
    # Setting it up
    # ##################################################################################
    def on_task(self, name: str, handler: Callable[[FakeTasker, dict[str, Any]], str | None]) -> None:
        """What running the Task of this name does -- and the Task exists, as if it had been imported."""
        self.tasks.add(name)
        self.handlers[name] = handler

    def writes(self, task_name: str, path: str, content: str | bytes, *, installed: bool = True) -> None:
        """Running this Task leaves this file on the phone, as every MapTasker helper Task does.

        `installed=False` is a phone that has not been given the Task yet: it exists only once it has been imported.
        """
        data = content.encode("utf-8") if isinstance(content, str) else content
        handler = lambda fake, _body: fake.files.__setitem__(path, data)
        if installed:
            self.on_task(task_name, handler)
        else:
            self.handlers[task_name] = handler

    def seen(self, method: str, prefix: str) -> list[str]:
        """The paths of the requests of this method that began with this prefix."""
        return [path for made, path in self.requests if made == method and path.startswith(prefix)]

    # ##################################################################################
    # Listening
    # ##################################################################################
    def up(self) -> FakeTasker:
        """Start listening on a free port of the loopback address."""
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:  # the test output is not a server log
                return

            def _body(self) -> bytes:
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def _answer(
                self, status: int = 200, body: bytes | str = b"", kind: str = "application/octet-stream"
            ) -> None:
                data = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                fake._handle(self, "GET")

            def do_POST(self) -> None:
                fake._handle(self, "POST")

            def do_DELETE(self) -> None:
                fake._handle(self, "DELETE")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        return self

    def down(self) -> None:
        """Stop listening; the next request to it is refused, as a phone that has gone away refuses it."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    @property
    def address(self) -> str:
        return "127.0.0.1"

    @property
    def port(self) -> str:
        assert self._server is not None, "the fake phone is not up"
        return str(self._server.server_address[1])

    # ##################################################################################
    # Answering
    # ##################################################################################
    def _handle(self, request: Any, method: str) -> None:
        parts = urlsplit(request.path)
        path, query = unquote(parts.path), parse_qs(parts.query)
        self.requests.append((method, request.path))
        body = request._body() if method == "POST" else b""

        if method == "GET" and path == "/api/auth":
            return self._auth(request)
        if method == "GET" and path.startswith("/file/"):
            return self._read_file(request, path.removeprefix("/file"))
        if method == "POST" and path == "/upload":
            return self._upload(request, query, body)
        if not self._authorized(request):
            return request._answer(401)
        if method == "DELETE" and path.startswith("/api/file/"):
            self.files.pop(path.removeprefix("/api/file"), None)
            return request._answer(200)
        if method == "POST" and path == "/api/import":
            return self._import(request, body)
        if method == "POST" and path == "/api/tasks":
            return self._run(request, body)
        if method == "GET" and path in {"/api/tasks", "/api/profiles", "/api/scenes"}:
            return self._list(request, path, query)
        return request._answer(404)

    def _authorized(self, request: Any) -> bool:
        if self.reject_keys:
            self.reject_keys -= 1
            return False
        return request.headers.get("Authorization") == KEY

    def _auth(self, request: Any) -> None:
        if self.refuse_auth:
            self.refuse_auth -= 1
            return request._answer(403, json.dumps({"authorized": False}), "application/json")
        return request._answer(200, json.dumps({"authorized": True, "key": KEY}), "application/json")

    def _read_file(self, request: Any, path: str) -> None:
        if self.slow_reads.get(path, 0) > 0:
            self.slow_reads[path] -= 1
            return request._answer(404)
        if path not in self.files:
            return request._answer(404)
        return request._answer(200, self.files[path])

    def _upload(self, request: Any, query: dict[str, list[str]], body: bytes) -> None:
        """The multipart field's NAME is the destination filename, as the real server's handler takes it."""
        folder = "/" + (query.get("location") or [""])[0].strip("/")
        message = message_from_bytes(
            b"Content-Type: " + request.headers["Content-Type"].encode() + b"\r\n\r\n" + body, policy=HTTP
        )
        for part in message.iter_parts():
            filename = part.get_param("name", header="content-disposition") or part.get_filename() or ""
            stored = f"{folder}/{filename}".replace("//", "/")
            self.files[stored] = cast("bytes", part.get_payload(decode=True) or b"")
            if any(stored.endswith(ending) for ending in self.imports_uploads_ending):
                self.import_xml(self.files[stored])
        return request._answer(200, "OK")

    def _import(self, request: Any, body: bytes) -> None:
        status = self.import_script.pop(0) if self.import_script else self.import_answers
        if status != 200:
            return request._answer(status)
        return request._answer(200 if self.import_xml(body) else 400)

    def import_xml(self, xml: bytes) -> bool:
        """What Tasker does with an import: its Tasks, Profiles and Scenes now exist.  False if it was not XML."""
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return False
        self.tasks |= {name.text or "" for name in root.findall("Task/nme")} - self.ignored_imports
        self.profiles |= {name.text or "" for name in root.findall("Profile/nme")} - self.ignored_imports
        self.scenes |= {name.text or "" for name in root.findall("Scene/nme")} - self.ignored_imports
        return True

    def user_taps_import(self, task_name: str, answer_path: str, header: str) -> None:
        """Running this Task opens Tasker's import screen on the file it is given (%par1), and the user confirms it."""

        def open_and_confirm(fake: FakeTasker, body: dict[str, Any]) -> None:
            staged = body.get("par1", "").removeprefix("/storage/emulated/0")
            fake.import_xml(fake.files.get(staged, b""))
            fake.files[answer_path] = f"{header}\nMAPTASKER-END\n".encode()

        self.handlers[task_name] = open_and_confirm

    def _run(self, request: Any, body: bytes) -> None:
        asked = json.loads(body or b"{}")
        name = asked.get("name", "")
        if name not in self.tasks:
            return request._answer(404)
        handler = self.handlers.get(name)
        returned = handler(self, asked) if handler else None
        return request._answer(200, (returned or "%return") + "\n")

    def _list(self, request: Any, path: str, query: dict[str, list[str]]) -> None:
        time.sleep(self.list_seconds)
        held = {"/api/tasks": self.tasks, "/api/profiles": self.profiles, "/api/scenes": self.scenes}[path]
        wanted = query.get("name")
        names = sorted(name for name in held if not wanted or name in wanted)
        return request._answer(200, json.dumps([{"name": name} for name in names]), "application/json")
