"""MapTasker shared-asset URL Unit Tests"""

from __future__ import annotations

import os

from maptasker.src import webassets


def test_an_asset_url_changes_when_the_file_does(tmp_path, monkeypatch) -> None:
    """The release number alone left a browser serving a stylesheet from before a rule was added."""
    (tmp_path / "x.css").write_text("a {}")
    monkeypatch.setattr(webassets, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(webassets, "mount", lambda: "/assets")
    before = webassets.url("x.css")

    (tmp_path / "x.css").write_text("a { color: red }")
    os.utime(tmp_path / "x.css", ns=(1, 1))

    assert webassets.url("x.css") != before


def test_a_missing_asset_still_gets_a_url(tmp_path, monkeypatch) -> None:
    """Not having the file to date is no reason to fail drawing the page."""
    monkeypatch.setattr(webassets, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(webassets, "mount", lambda: "/assets")

    assert webassets.url("nope.css").startswith("/assets/nope.css?v=")
