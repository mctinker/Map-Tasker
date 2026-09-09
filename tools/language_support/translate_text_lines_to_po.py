#! /usr/bin/env python3
"""
Translate and generate GETtext files using deep-translator.
Reads lines from an input file, translates them into multiple languages,
and appends the results to specific 'messages.po' files.
"""

import os
import socket
import sys
import time

# deep-translator issues its HTTP GET with no timeout, so a stalled connection to
# Google blocks forever and no exception is ever raised.  urllib3 falls back to the
# process-wide socket default when no timeout is supplied, so setting one here turns
# a hang into a catchable error.  This must run before the first request is made.
socket.setdefaulttimeout(20)

import requests
from deep_translator import GoogleTranslator
from deep_translator.exceptions import TooManyRequests

# Pause between requests.  Google throttles the free endpoint when hit back to back.
REQUEST_DELAY = 0.4

# Retry policy for a single translation.
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 3
THROTTLE_BACKOFF_SECONDS = 30


def translate_with_retry(translator: GoogleTranslator, text: str) -> str | None:
    """
    Translate a single string, retrying with backoff on timeouts and throttling.
    Returns None if every attempt failed or the translation came back unusable.
    """

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            translated = translator.translate(text)

            # deep-translator falls off the end of translate() and returns None when
            # the translation matches the input (common for 'Save', 'Rename', etc.).
            # Treat that as "no translation needed" rather than writing 'None'.
            if translated is None:
                return text

            return translated

        except TooManyRequests:
            wait = THROTTLE_BACKOFF_SECONDS * attempt
            print(f"    [Throttled] Waiting {wait}s before retry {attempt}/{MAX_ATTEMPTS}")
            time.sleep(wait)

        except (TimeoutError, requests.exceptions.RequestException, OSError) as e:
            wait = BACKOFF_SECONDS * attempt
            print(f"    [Network] {type(e).__name__}: {e} - retry {attempt}/{MAX_ATTEMPTS} in {wait}s")
            time.sleep(wait)

        except Exception as e:  # noqa: BLE001
            print(f"    [Error] {type(e).__name__}: {e}")
            return None

    return None


def escape_po(text: str) -> str:
    """Make a string safe to place inside a double-quoted .po value."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def translate_and_generate_gettext(input_file: str, languages: dict, base_locale_path: str) -> None:
    """
    Reads an input file, translates each line into target languages,
    and appends the output to existing messages.po files in the locale directory.
    """

    try:
        with open(input_file, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        return

    # Strip blanks up front so the per-language loops below stay simple.
    originals = [line.strip() for line in lines if line.strip()]
    if not originals:
        print("Nothing to translate.")
        return

    # Language is the outer loop so one translator (and one connection pool) serves
    # every line for that language, rather than building 33 translators per line.
    for lang_id, lang_name in languages.items():
        # We replace '_' with '-' because deep-translator/Google typically expects
        # codes like 'zh-CN' rather than 'zh_CN'.
        target_lang = lang_id.replace("_", "-")

        # 'in' is often used for Indonesian in older systems, but Google expects 'id'
        if target_lang == "in":
            target_lang = "id"

        # Construct the path to the messages.po file
        # Path format: .../locale/{lang_id}/LC_MESSAGES/messages.po
        po_file_path = os.path.join(
            base_locale_path,
            lang_id,
            "LC_MESSAGES",
            "messages.po",
        )

        # Check if the file exists before attempting to append
        if not os.path.exists(po_file_path):
            print(f"[Skipping] Could not find file: {po_file_path}")
            continue

        print(f"Translating to {lang_name} -> Appending to {po_file_path}")

        try:
            translator = GoogleTranslator(source="auto", target=target_lang)
        except Exception as e:  # noqa: BLE001
            print(f"  [Error] Could not create translator for {lang_id}: {e}")
            continue

        failures = 0

        # Hold the .po file open for the whole language instead of reopening per line.
        with open(po_file_path, "a", encoding="utf-8") as out_f:
            for original_text in originals:
                print(f"  {original_text}")

                translated_text = translate_with_retry(translator, original_text)

                if translated_text is None:
                    failures += 1
                    print(f"  [Failed] '{original_text}' -> {lang_id} (skipped)")
                    continue

                out_f.write(f'\nmsgid "{escape_po(original_text)}"\n')
                out_f.write(f'msgstr "{escape_po(translated_text)}"\n')
                out_f.flush()

                time.sleep(REQUEST_DELAY)

        if failures:
            print(f"  {failures} of {len(originals)} line(s) failed for {lang_name}.")


if __name__ == "__main__":
    # The base path where the language folders are located
    LOCALE_BASE_PATH = "/Users/mikrubin/MapTasker_Dev/maptasker/locale"

    # Dictionary of languages: Key is ISO identifier, Value is Name (for reference)
    # Ensure the keys here match the folder names under LOCALE_BASE_PATH
    languages = {
        "es": "Spanish",
        "de": "German",
        "zh_CN": "Simplified Chinese",
        "zh_TW": "Traditional Chinese",
        "hi": "Hindi",
        "fr": "French",
        "pt": "Portuguese",
        "ja": "Japanese",
        "ru": "Russian",
        "ko": "Korean",
        "ar": "Arabic",
        "bn": "Bengali",
        "ur": "Urdu",
        "id": "Indonesian",
        "sw": "Swahili",
        "mr": "Marathi",
        "te": "Telugu",
        "tr": "Turkish",
        "ta": "Tamali",
        "vi": "Vietnamese",
        "it": "Italian",
        "uk": "Ukrainian",
        "pl": "Polish",
        "nl": "Dutch",
        "th": "Thai",
        "gu": "Gujarati",
        "fa": "Persian",
        "sv": "Swedish",
        "da": "Danish",
        "fi": "Finish",
        "no": "Norwegian",
        "el": "Greek",
        "cs": "Czech",
    }

    input_filename = "input.txt"

    # Create a dummy input file for testing purposes if it doesn't exist
    if not os.path.exists(input_filename):
        print("No input.txt file found!")
        sys.exit(8)

    print(f"Targeting locale directory: {LOCALE_BASE_PATH}")
    translate_and_generate_gettext(input_filename, languages, LOCALE_BASE_PATH)
    print("Translation complete.")
