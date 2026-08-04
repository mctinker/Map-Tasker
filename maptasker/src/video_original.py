#! /usr/bin/env python3
"""
Process videos from YouTube and Dropbox/MP4s (NiceGUI Version)
"""

import os
import re

from nicegui import ui

from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

# Maintain fallback scale defaults matching target configurations
TARGET_WIDTH = "640"
TARGET_HEIGHT = "640"


def handle_image(msg: str) -> str:
    """
    Extracts an image URL from an HTML 'href' attribute.

    Since NiceGuiTextView natively displays clean HTML blocks, we no longer need
    complex Tkinter Canvas rendering injections. We just return a fully styled
    HTML <img> block for the web view engine to process directly.
    """
    pattern = r'href="(.*?)"'
    match = re.search(pattern, msg)

    if match:
        url = match.group(1)
        return f"<img src='{url}' class='max-w-[300px] h-auto rounded shadow-sm my-2' alt='Embedded Graphics'>"

    logger.warning(f"No valid href token found to process image content: {msg}")
    return msg


def embed_video_placeholder(container: ui.element, media_url: str) -> None:
    """
    Renders an interactive video launcher link inside a NiceGUI parent container tree.
    Replaces old character index calculations and tag state allocations.
    """
    # Verify platform capability limits
    if PrimeItems.windows_system:
        # Fallback tracking indicator
        ui.label(f"[▶️ VIDEO: {media_url} (Playback unavailable on Windows)]").classes("text-gray-400 italic text-sm")
        return

    # Render an explicit text hyper-link connected directly to our modern modal play player
    with ui.row().classes("items-center gap-1 my-1"):
        ui.icon("play_circle", color="primary").classes("text-base")
        ui.link(
            f"Launch Media: {os.path.basename(media_url) or media_url}",
            on_click=lambda: play_video(media_url),
        ).classes("text-blue-600 font-medium underline text-sm hover:text-blue-800")


def play_video(video_url_or_path: str, title: str = "MapTasker Media Player") -> ui.dialog:
    """
    Plays an MP4 or shared remote video source directly inside a responsive NiceGUI
    modal dialog box context, utilizing standard browser HTML5 transport layers.

    Replaces: VideoEmbedder class, OpenCV frame capture loops, and ffplay subprocesses.
    """
    # 1. Modify stream pointers for special repository links
    if video_url_or_path.endswith("?dl=0"):
        video_url_or_path = video_url_or_path[:-1] + "1"

    # 2. Build out a high-contrast modal frame mirroring the width bounds of create_popup_window
    with (
        ui.dialog() as dialog,
        ui.card().classes("min-w-[400px] max-w-[800px] w-full items-center p-6 bg-slate-900 text-white"),
    ):
        # Display Title bar summary information
        ui.label(translate_string(title)).classes("text-lg font-bold text-blue-400 text-center truncate w-full mb-4")

        # Guard clause check against streaming restrictions
        if any(keyword in video_url_or_path for keyword in ["youtu.", "youtube."]):
            ui.label(
                translate_string(
                    "YouTube direct streaming requires third-party API tokens. Download the target track locally to view.",
                ),
            ).classes("text-red-400 text-sm text-center my-4 whitespace-pre-wrap")

            # Simple link helper tracking fallback info
            ui.link(video_url_or_path, video_url_or_path, new_tab=True).classes(
                "text-blue-400 text-xs break-all text-center underline",
            )
        else:
            # Inject native HTML5 Player component inside the modal tree hierarchy
            ui.video(video_url_or_path, controls=True, autoplay=True).classes(
                "w-full h-auto aspect-video rounded-md shadow-2xl border border-slate-700",
            )

        # Modal bottom window termination switch
        ui.button(translate_string("Close"), on_click=dialog.close).classes(
            "mt-6 bg-red-600 hover:bg-red-700 text-white font-bold w-full py-2",
        )

    # Open dialog canvas container immediately
    dialog.open()
    return dialog
