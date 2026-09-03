#! /usr/bin/env python3
"""Find all 'display_message_box' calls in .py files in a directory, extract the message text,
translate it using GoogleTranslator from deep_translator, and save the results to a .pot file.

To run:
1- cd to /Users/mikrubin/MapTasker/maptasker/src/
2- run from with vscode

"""

import os

from deep_translator import GoogleTranslator


def extract_message_box_text(directory, output_file):
    results = []
    seen = set()
    translator_count = 0
    source_lang: str = "auto"
    target_lang: str = "es"
    error_msg_file = "translation_errors.log"
    translator = GoogleTranslator(source=source_lang, target=target_lang)

    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".py"):
                if filename == "disp_msg.py":
                    continue  # Skip this file to avoid self-translation
                path = os.path.join(root, filename)

                with open(path, encoding="utf-8") as f:
                    text = f.readlines()

                for count, line in enumerate(text):
                    if "def display_message_box(" in line:
                        # Skip function definition lines
                        continue
                    display_msg = line.find("display_message_box(")
                    if count % 1000 == 0:
                        print(f"Read {count} messages...")
                    if display_msg != -1:
                        msg_text = line[display_msg + 20 :]
                        if msg_text == "\n":
                            msg_text = text[count + 1].lstrip()
                        else:
                            msg_text = msg_text.split('"', 2)
                            if len(msg_text) >> 1:
                                if len(msg_text) == 3 and msg_text[2] == ")\n":
                                    continue  # Empty message box...color definition
                                msg_text = msg_text[1]
                            else:  # Ignore if just a color
                                continue

                        msg_text = msg_text.strip('"').replace('",\n', "")
                        # Translate non-empty msgid
                        if msg_text.startswith(('f"', "f'")) or "{" in msg_text or " + " in msg_text:
                            # Skip f-strings
                            translated_msg = "partial"
                        else:
                            translator_count += 1
                            if translator_count % 10 == 0:
                                print(f"Translated {translator_count} messages...")
                            translated_msg = translator.translate(msg_text) if msg_text else ""

                        if msg_text not in seen:
                            seen.add(msg_text)
                            results.append([msg_text, translated_msg, filename, count + 1])

    # Write results to file
    with (
        open(output_file, "w", encoding="utf-8") as out,
        open(error_msg_file, "w", encoding="utf-8") as err_out,
    ):
        for msg in results:
            if msg[1] == "partial":
                err_out.write(f"Skipped f-string translation for msgid: {msg[0]} in {msg[2]} line {msg[3]}\n")
                continue
            out.write(f'msgid "{msg[0]}"\n')
            out.write(f'msgstr "{msg[1]}"\n')

    print(f"Extracted {len(results)} msgids → {output_file}")


# Example usage:
if __name__ == "__main__":
    extract_message_box_text(
        directory=".",  # directory to scan
        output_file="messages.pot",  # output file
    )
