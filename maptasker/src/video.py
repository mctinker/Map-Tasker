#! /usr/bin/env python3
"""
Process videos from YouTube and Dropbox/MP4s (NiceGUI Version)
"""

import re

from nicegui import ui

from maptasker.src.maputil2 import translate_string
from maptasker.src.sysconst import logger

# We can keep your target dimensions for styling, though Tailwind handles scaling beautifully
TARGET_WIDTH = "640"
TARGET_HEIGHT = "640"


def handle_image(msg: str) -> str:
    """
    Extracts an image URL from an HTML 'href' or 'src' attribute.

    Since our NiceGuiTextView renders raw HTML, we don't need PIL or Tkinter PhotoImages.
    We just extract the URL and return a beautifully styled HTML <img> tag for the browser to render natively!
    """
    # Find the URL (basic regex looking for href="..." or src="...")
    match = re.search(r'(?:href|src)="([^"]+)"', msg)

    if match:
        image_url = match.group(1)
        # Return a native HTML image tag with Tailwind CSS classes for styling
        return (
            f"<img src='{image_url}' class='max-w-[{TARGET_WIDTH}px] rounded-lg shadow-md my-2' alt='Extracted Image'>"
        )

    logger.warning(f"Could not extract image URL from message: {msg}")
    return msg


def play_video(video_url_or_path: str, title: str = "MapTasker Video Player") -> None:
    """
    Plays a video natively in the browser using an HTML5 video player.
    Completely replaces the old CTk window and ffplay subprocess.
    """
    # Create a clean modal dialog to house the video player
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl p-0 overflow-hidden bg-black"):
        # Header bar
        with ui.row().classes("w-full justify-between items-center p-4 bg-gray-900 text-white"):
            ui.label(translate_string(title)).classes("text-lg font-bold truncate")
            ui.button(icon="close", on_click=dialog.close).props("flat round text-color=white")

        # Native browser HTML5 video player!
        # controls=True adds the standard play/pause/timeline/volume UI
        # autoplay=True starts it as soon as the dialog opens
        ui.video(video_url_or_path, controls=True, autoplay=True).classes("w-full h-auto aspect-video")

    dialog.open()
    return dialog


# Note: If you have logic that downloads YouTube videos using yt-dlp,
# keep that pure Python logic intact here. Once the .mp4 is downloaded
# locally, just pass the file path to `play_video(path)`!
