#! /usr/bin/env python3
"""
guiutil2: General utilities (NiceGUI Version).
These are pure Python functions pulled out to avoid circular imports.
"""

# import os
# import re

# import requests

# from maptasker.src.aiutils import get_api_key
# from maptasker.src.error import rutroh_error
# from maptasker.src.maputil2 import translate_string
# from maptasker.src.maputils import make_hex_color
# from maptasker.src.primitem import PrimeItems
# from maptasker.src.video import handle_image

# Define label fonts for headings (Replaced hardcoded pixel sizes with Tailwind text classes)
heading_fonts = {
    "0": "text-base",
    "1": "text-3xl",
    "2": "text-2xl",
    "3": "text-xl",
    "4": "text-lg",
    "5": "text-base font-bold",
    "6": "text-sm",
    "7": "text-xs",
}

# ==========================================
# PURE PYTHON UTILITIES (Keep your existing logic here)
# ==========================================


def sort_languages_with_priority(languages: list) -> list:
    """
    Sorts a list of languages, ensuring primary languages (like English)
    appear at the top of the dropdown.
    """
    # Keep your exact same sorting logic here!
    sorted_langs = sorted(languages)
    if "English" in sorted_langs:
        sorted_langs.remove("English")
        sorted_langs.insert(0, "English")
    return sorted_langs


# Note: If you have functions like `check_for_changelog`, `is_valid_ai_config`,
# or `draw_box_around_text` (if it just manipulates strings), paste them below!
