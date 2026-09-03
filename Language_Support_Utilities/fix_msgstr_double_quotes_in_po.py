#! /usr/bin/env python3
"""Fix 'msgstr " "some_text" """

import os


def clean_and_format_po_files():
    """
    Traverses directories to clean 'message.po' files:
    1. Keeps only the first blank line.
    2. Replaces inner double-quotes with single quotes in msgstr lines.
    """
    target_file = "messages.po"
    root_dir = "/Users/mikrubin/MapTasker/maptasker/locale"

    print(f"Starting traversal in: {root_dir}")

    for root, _dirs, files in os.walk(root_dir):
        if target_file in files:
            file_path = os.path.join(root, target_file)
            process_file(file_path)


def process_file(file_path):
    cleaned_lines = []
    found_first_blank = False

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            # 1. Handle Blank Lines logic
            if not line.strip():
                if not found_first_blank:
                    cleaned_lines.append(line)
                    found_first_blank = True
                continue

            # 2. Handle msgstr replacement logic
            # We use lstrip() to catch lines that might have leading spaces
            if line.lstrip().startswith("msgstr"):
                processed_line = replace_inner_quotes(line)
                cleaned_lines.append(processed_line)
            else:
                cleaned_lines.append(line)

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)

        print(f"Processed: {file_path}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")


def replace_inner_quotes(line):
    """
    Replaces " with ' inside the msgstr quotes.
    Example: msgstr "He said "Hello"" -> msgstr "He said 'Hello'"
    """
    # Find the positions of the first and last double quotes
    first_quote_idx = line.find('"')
    last_quote_idx = line.rfind('"')

    # If we don't find at least two quotes, return line as is
    if first_quote_idx == -1 or first_quote_idx == last_quote_idx:
        return line

    # Split the line into three parts:
    # 1. Everything before and including the first quote
    # 2. The content between the quotes (where we replace)
    # 3. Everything from the last quote to the end of the line
    prefix = line[: first_quote_idx + 1]
    inner_content = line[first_quote_idx + 1 : last_quote_idx]
    suffix = line[last_quote_idx:]

    new_inner = inner_content.replace('"', "'")

    return prefix + new_inner + suffix


if __name__ == "__main__":
    clean_and_format_po_files()
    print("Task completed.")
