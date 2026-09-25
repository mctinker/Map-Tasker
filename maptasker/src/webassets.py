"""The app's own static files: the shared stylesheet, the Scene canvas script and the images.

They live under maptasker/assets as ordinary .css/.js/.png files -- so an editor highlights and
lints them -- and are served over HTTP from one NiceGUI static route.  Every page links the
stylesheet and script from its <head> (guiwins.inject_shared_head_styles), and after the first
page the browser has both cached, which is cheaper than the inline <style> each page used to
carry and far cheaper than resending the canvas script over the websocket on every re-render.
"""

from __future__ import annotations

from pathlib import Path

from nicegui import app

from maptasker.src.sysconst import VERSION

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ASSETS_URL = "/maptasker_assets"
STYLESHEET = "css/maptasker.css"
CANVAS_SCRIPT = "js/scene_canvas.js"

_mounted = False


def mount() -> str:
    """Serve the assets directory, once per process, and return the URL it is served from."""
    global _mounted  # noqa: PLW0603
    if not _mounted:
        app.add_static_files(ASSETS_URL, ASSETS_DIR)
        _mounted = True
    return ASSETS_URL


def url(relative: str) -> str:
    """The URL of one asset.  Versioned, so an upgraded install is not served a stale cached copy."""
    return f"{mount()}/{relative}?v={VERSION}"


def head_html() -> str:
    """The <link> and <script> tags every page needs in its <head>.

    The script is a plain blocking one, deliberately: the canvas calls sent over the websocket
    (see guiwins_canvas) run only after the page has loaded, and must find window.mtCanvas there.
    """
    return f'<link rel="stylesheet" href="{url(STYLESHEET)}">\n<script src="{url(CANVAS_SCRIPT)}"></script>'
