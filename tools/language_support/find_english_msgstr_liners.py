#! /usr/bin/env python3
"""Search for and display all 'msgstr lines that are in English"""

import os

import polib
from deep_translator import GoogleTranslator


def find_english_msgstrs(root_dir: str = "locale") -> None:
    """
    Scans .po files and identifies msgstr entries that are written in English.
    """
    # Initialize the translator for detection purposes
    # Note: GoogleTranslator's detect method is often used for this
    translator = GoogleTranslator()

    if not os.path.exists(root_dir):
        print(f"Error: The directory '{root_dir}' does not exist.")
        return

    print(f"Scanning directory: {root_dir}...\n")

    for root, _dirs, files in os.walk(root_dir):
        for file in files:
            if file == "messages.po":
                file_path = os.path.join(root, file)
                process_po_file(file_path, translator)


def process_po_file(path: str, translator: GoogleTranslator) -> None:
    """
    Parses a single .po file and checks each msgstr.
    """
    try:
        # Load the po file
        po = polib.pofile(path)

        for entry in po:
            # We only care about msgstr that aren't empty
            if entry.msgstr.strip():
                try:
                    # Detect the language of the msgstr
                    # deep-translator uses various backends;
                    # here we check if the detected lang is 'en'
                    detected_lang = translator.detect_language(entry.msgstr)

                    if detected_lang == "en":
                        # entry.linenum provides the starting line in the file
                        print("Found English msgstr:")
                        print(f"  File: {path}")
                        print(f"  Line: {entry.linenum}")
                        print(f'  Text: "{entry.msgstr}"')
                        print("-" * 30)

                except Exception:  # noqa: BLE001, S112
                    # Detection can fail on very short strings or special characters
                    continue

    except Exception as e:  # noqa: BLE001
        print(f"Could not parse {path}: {e}")


if __name__ == "__main__":
    input_dir = "/Users/mikrubin/MapTasker/maptasker/locale"
    find_english_msgstrs(root_dir=input_dir)
