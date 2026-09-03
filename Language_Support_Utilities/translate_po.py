#! /usr/bin/env python3
"""Call deep_translator using GoogleTranslator to translate text from a file and save the output.

To run:
1- Open terminal to /Users/mikrubin/MapTasker/
2- run 'fish' to set export variables
3- Update the 3 constants, below.
3- run from with vscode

"""

import datetime
import os
import re
import shutil

from deep_translator import GoogleTranslator
from maptasker.src.sysconst import (
    VERSION,
)


def translate_po_file(
    input_file: str = "/Users/mikrubin/MapTasker/maptasker/locale/es/LC_MESSAGES/messages.po",
    output_file: str = "/Users/mikrubin/MapTasker/Language_Support_Utilities/messages_translated.po",
    source_lang: str = "en",
    target_lang: str = "es",
    reverse_translate: bool = False,
) -> None:
    """Automates translation of a PO (Portable Object) file using GoogleTranslator.

    This function reads a source PO file, translates the content of every
    `msgid` entry that has an empty or missing `msgstr`, and writes the
    original `msgid` and the new, machine-translated `msgstr` to a new PO file.
    Lines other than `msgid` and its corresponding empty `msgstr` (like comments)
    are generally preserved.

    Note: This is an initial machine translation intended to be reviewed by a human.
    It relies on an external library for the Google Translator functionality.

    Args:
        input_file: The full path to the source PO file to be read.
            Defaults to a local example path.
        output_file: The full path to the destination PO file. The function
            will automatically append the `target_lang` code to the filename
            (e.g., `messages_translated_es.po`).
        source_lang: The source language code (e.g., 'en', 'es'). Used by
            the translator engine.
        target_lang: The target language code (e.g., 'es', 'de'). Used by
            the translator engine and appended to the output filename.
        reverse_translate: If True, the function performs a **reverse lookup**
            translation by appending a new pair of `msgid`/`msgstr` entries
            where the translated string becomes the new `msgid` and the
            original source string becomes the new `msgstr`. This is useful
            for reverse lookups (e.g., in language switchers).

    Returns:
        None. The function writes the output to the specified `output_file` path.
    """
    po_header = """
msgid ''
msgstr ''
'Project-Id-Version: 10.0.0\n'
'Report-Msgid-Bugs-To: https://https://github.com/mctinker/Map-Tasker/issues\n'
'POT-Creation-Date: 2025-12-05 12:00+0000\n'
'PO-Revision-Date: 2025-12-05 12:00+0000\n'
'Last-Translator: Google Translate\n'
'Language-Team: LANGUAGE anon\n'
'Language: es\n'
'MIME-Version: 1.0\n'
'Content-Type: text/plain; charset=UTF-8\n'
'Content-Transfer-Encoding: 8bit\n'

    """
    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
    except Exception as e:  # noqa: BLE001
        print(f"Error translating '{target_lang}: {e}")
        return
    trans_count = 0
    # langs_dict = GoogleTranslator().get_supported_languages(as_dict=True)
    # for key, value in langs_dict.items():
    #     print(key, " ", value)

    # Add language identifier to outpuit filename.
    temp = output_file.split(".")
    out_name = f"{temp[0]}_{target_lang}".replace("-", "_")
    output_file = f"{out_name}.{temp[1]}"

    msgid_pattern = re.compile(r'^msgid\s+"(.*)"$')

    print("Translating language ", target_lang)

    # Setup the header
    date, time = get_formatted_datetime()
    header = (
        po_header.replace("10.0.0", VERSION)
        .replace("2025-12-05", date)
        .replace("12:00+0000", time)
        .replace(": es", f": {target_lang}")
    )

    # Create the necessary directories if they don't already exist
    target_lang = target_lang.replace("-", "_")  # Ensure directory name is valid
    create_directory_if_not_exists(f"/Users/mikrubin/MapTasker/maptasker/locale/{target_lang}")
    create_directory_if_not_exists(f"/Users/mikrubin/MapTasker/maptasker/locale/{target_lang}/LC_MESSAGES")

    messages_file = f"/Users/mikrubin/MapTasker/maptasker/locale/{target_lang}/LC_MESSAGES/messages.po"

    with open(input_file, encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
        if reverse_translate:
            outfile.close()
            os.remove(output_file)
            # Force a newline
            check_and_append_to_file(messages_file, "  \n")
        # Write out the header
        else:
            outfile.write(header.replace("'", '"'))

        # Translate all msgid lines
        for count, line in enumerate(infile):
            if count % 50 == 0:
                print("Processed ", count, " lines...")
            stripped = line.rstrip("\n")

            # 1. Keep comment lines starting with '#'
            if not reverse_translate and stripped.startswith("#"):
                outfile.write(" ")
                outfile.write(line)
                continue

            # 2. Ignore lines that are exactly: msgstr ""
            if stripped == 'msgstr ""':
                continue

            # 3. Process msgid lines
            match = msgid_pattern.match(stripped)
            if match:  # If we have 'msgid'...
                trans_count += 1
                if trans_count % 10 == 0:
                    print("Translated ", trans_count, " strings...")
                text_to_translate = match.group(1)

                # Translate non-empty msgid
                translated = translator.translate(text_to_translate) if text_to_translate else ""
                translated = translated.replace('"', "'")

                # If doing a reverse language translation, then just append translations to existing message.po files
                if reverse_translate:
                    # Original and translation
                    check_and_append_to_file(messages_file, line.replace("\n", ""))
                    check_and_append_to_file(messages_file, f'msgstr "{translated}"')
                    # Reverse translation
                    check_and_append_to_file(messages_file, f'msgid "{translated}"')
                    check_and_append_to_file(messages_file, f'msgstr "{text_to_translate}"')

                # Normal/full translation
                else:
                    # Write original msgid
                    outfile.write(line)

                    # Write auto-generated msgstr
                    outfile.write(f'msgstr "{translated}"\n')

            # 4. All other lines pass through unchanged
            # outfile.write(line)

    # Now move the file into the appropriate directory
    if not reverse_translate:
        move_file_to_directory(output_file, f"/Users/mikrubin/MapTasker/maptasker/locale/{target_lang}/LC_MESSAGES")


def move_file_to_directory(source_path: str, destination_dir: str) -> None:
    """
    Moves a file from a source path to a destination directory.

    Args:
        source_path (str): The path to the file you want to move.
        destination_dir (str): The path to the directory where the file should be moved.
    """
    print(f"\n--- Attempting to move '{source_path}' to '{destination_dir}' ---")

    # Check if the source file actually exists
    if not os.path.exists(source_path):
        print(f"❌ ERROR: Source file not found: {source_path}")
        return

    # Check if the destination directory exists
    if not os.path.isdir(destination_dir):
        print(f"❌ ERROR: Destination directory not found: {destination_dir}. Did you run the setup?")
        return

    try:
        # shutil.move() handles renaming if possible, or copy/delete otherwise.
        # It automatically resolves the final path of the moved file.
        final_destination = shutil.move(source_path, destination_dir)

        print(f"✅ Success! File moved to: {final_destination}")

    except shutil.Error as e:
        # Catches common errors like permissions or file name conflicts
        print(f"❌ ERROR during move operation: {e}")
    except Exception as e:
        # Catches any other unexpected errors
        print(f"❌ An unexpected error occurred: {e}")


def create_directory_if_not_exists(directory_path: str) -> None:
    """
    Checks if a directory exists, and creates it if it does not.
    This function can create multiple levels of directories (like 'data/logs/today').

    Args:
        directory_path (str): The full path of the directory to check/create.
    """
    try:
        # os.makedirs creates the directory.
        # exist_ok=True prevents an OSError if the directory already exists.
        os.makedirs(directory_path, exist_ok=True)
        print(f"Directory check successful. Path: '{directory_path}'")

        # We can add logic to confirm if it was created or already existed
        if not os.path.exists(directory_path):
            print(f"-> '{directory_path}' directory was created.")
        else:
            print(f"-> '{directory_path}' directory already existed.")

    except OSError as e:
        # Catches common issues like permission denied
        print(f"Error creating directory '{directory_path}': {e}")


def get_formatted_datetime() -> tuple[str, str]:
    """
    Returns the current date and time formatted as (YYYY-MM-DD, HH:MM+timezone).

    The timezone is represented as an offset (e.g., +05:30 or -04:00).

    Returns:
        tuple: A tuple containing two strings:
               - date_str (str): The date in 'YYYY-MM-DD' format.
               - time_str (str): The time in 'HH:MM+timezone' format.
    """
    # 1. Get the current datetime object.
    # We use astimezone() with a default argument to ensure the datetime object
    # is timezone-aware and represents the local time.
    now_local = datetime.datetime.now(datetime.UTC).astimezone()

    # 2. Format the date part (YYYY-MM-DD)
    # %Y: Year with century (e.g., 2025)
    # %m: Month as a zero-padded decimal number (e.g., 01, 12)
    # %d: Day of the month as a zero-padded decimal number (e.g., 01, 31)
    date_str = now_local.strftime("%Y-%m-%d")

    # 3. Format the time part (HH:MM+timezone)
    # %H: Hour (24-hour clock) as a zero-padded decimal number (e.g., 00, 23)
    # %M: Minute as a zero-padded decimal number (e.g., 00, 59)
    # %z: UTC offset in the form +HHMM or -HHMM.
    # We use a slight trick here to insert the colon into the timezone offset.

    # First, get the standard format +HHMM
    time_and_offset = now_local.strftime("%H:%M%z")

    # Second, insert the colon into the offset.
    # time_and_offset will look like '14:30+0530' (example)
    # We want '14:30+05:30'
    time_str = time_and_offset[:-2] + ":" + time_and_offset[-2:]

    # 4. Return the results
    return (date_str, time_str)


def check_and_append_to_file(filepath: str, target_string: str) -> bool:
    """
    Looks for a specific text string in a file. If the string is not found,
    it appends the string (plus a newline) to the end of the file.

    Args:
        filepath (str): The path to the file to modify.
        target_string (str): The string to search for and potentially append.

    Returns:
        bool: True if the file was modified (string appended), False otherwise.
    """

    if not os.path.exists(filepath):
        print(f"❌ Error: File not found at path: {filepath}")
        return False

    string_found = False

    # 1. READ and CHECK phase
    try:
        # Open in read mode ('r')
        with open(filepath) as f:
            # print(f"Searching for '{target_string}' in '{filepath}'...")

            # Read line by line for efficiency
            for line in f:
                if target_string in line:
                    string_found = True
                    break  # Stop searching as soon as it's found

        if string_found:
            # print("✅ String found. No action taken.")
            return False
        f.close()

    except OSError as e:
        print(f"❌ Error reading file {filepath}: {e}")
        return False

    # 2. APPEND phase (Only runs if string_found is False)
    if not string_found:
        try:
            # Open in append mode ('a')
            with open(filepath, "a", encoding="utf-8") as f:
                # Add a newline character before and after for clean formatting
                f.write(f"{target_string}\n")
            # print(f"➕ String NOT found. Appended: '{target_string}' to {filepath}.")  # noqa: RUF003
            return True  # noqa: TRY300

        except OSError as e:
            print(f"❌ Error writing to file {filepath}: {e}")
            return False
    return None


if __name__ == "__main__":
    # Input text expected to be in the format of a PO file, with msgid and msgstr pairs, or just msgid "text"
    in_file = "/Users/mikrubin/MapTasker/Language_Support_Utilities/reverse.txt"
    # Translate just the new text
    # translate_po_file(input_file=in_file, target_lang="es")
    # translate_po_file(input_file=in_file, target_lang="de")
    # translate_po_file(input_file=in_file, target_lang="zh-CN")
    # translate_po_file(input_file=in_file, target_lang="zh-TW")
    # translate_po_file(input_file=in_file, target_lang="ko")
    # translate_po_file(input_file=in_file, target_lang="pt")
    # translate_po_file(input_file=in_file, target_lang="fr")
    # translate_po_file(input_file=in_file, target_lang="ja")
    # translate_po_file(input_file=in_file, target_lang="ru")
    # translate_po_file(input_file=in_file, target_lang="hi")
    # translate_po_file(input_file=in_file, target_lang="ar")

    # Reverse translation
    # translate_po_file(input_file=in_file, target_lang="es", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="de", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="zh-CN", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="zh-TW", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="ko", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="pt", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="fr", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="ja", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="ru", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="hi", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="ar", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="bn", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="ur", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="id", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="sw", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="mr", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="te", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="tr", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="ta", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="vi", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="it", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="uk", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="pl", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="nl", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="th", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="gu", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="fa", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="sv", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="da", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="fi", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="no", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="el", reverse_translate=True)
    # translate_po_file(input_file=in_file, target_lang="cs", reverse_translate=True)

    # Translate it all.
    # translate_po_file(target_lang="es")
    # translate_po_file(target_lang="de")
    # translate_po_file(target_lang="zh-CN")
    # translate_po_file(target_lang="zh-TW")
    # translate_po_file(target_lang="ko")
    # translate_po_file(target_lang="pt")
    # translate_po_file(target_lang="fr")
    # translate_po_file(target_lang="ja")
    # translate_po_file(target_lang="ru")
    # translate_po_file(target_lang="hi")
    # translate_po_file(target_lang="ar")  # Arabian
    # translate_po_file(target_lang="bn")  # Bengali
    # translate_po_file(target_lang="ur")  # Urdu: Pakistan and India
    # translate_po_file(target_lang="id")  # Indonesia
    # translate_po_file(target_lang="sw")  # Swahili: East Africa
    # translate_po_file(target_lang="mr")  # Marathi: India
    # translate_po_file(target_lang="te")  # Teluga: India major IT workforce
    # translate_po_file(target_lang="tr")  # Turkey
    # translate_po_file(target_lang="ta")  # Tamali: India and Sri Lanka
    # translate_po_file(target_lang="vi")  # Vietnamese
    # translate_po_file(target_lang="it")  # Italy
    # translate_po_file(target_lang="uk")  # Ukraine
    # translate_po_file(target_lang="pl")  # Polish
    # translate_po_file(target_lang="nl")  # Dutch
    # translate_po_file(target_lang="th")  # Thailand
    # translate_po_file(target_lang="gu")  # Gujarati: India
    # translate_po_file(target_lang="fa")  # Persian
    # translate_po_file(target_lang="sv")  # Sweden
    # translate_po_file(target_lang="da")  # Danish
    # translate_po_file(target_lang="fi")  # Finland
    # translate_po_file(target_lang="no")  # Norway
    # translate_po_file(target_lang="el")  # Greece
    # translate_po_file(target_lang="cs")  # Czech Republic
