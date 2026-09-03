#! /usr/bin/env python3
"""
Delete all blank lines in each 'message.po' file, except fore the first blank.
"""

import os


def clean_po_files() -> None:
    """
    Traverses the current directory and subdirectories to clean 'message.po' files.
    Removes all blank lines except for the very first one encountered in each file.
    """
    # Target filename
    target_file = "messages.po"

    # Get the current working directory
    # root_dir = os.getcwd()
    root_dir = "/Users/mikrubin/MapTasker/maptasker/locale"

    print(f"Starting traversal in: {root_dir}")

    for root, _dirs, files in os.walk(root_dir):
        if target_file in files:
            file_path = os.path.join(root, target_file)
            print("bingo", file_path)
            process_file(file_path)


def process_file(file_path: str) -> None:
    """
    Reads a file and writes back the content with only the first blank line preserved.
    """
    cleaned_lines = []
    found_first_blank = False

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            # .strip() checks if the line contains only whitespace or is empty
            if not line.strip():
                if not found_first_blank:
                    # This is the first blank line we've seen; keep it.
                    cleaned_lines.append(line)
                    found_first_blank = True
                else:
                    # It's a subsequent blank line; skip it.
                    continue
            else:
                # It's a non-blank line; keep it.
                cleaned_lines.append(line)

        # Write the processed content back to the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)

        print(f"Processed: {file_path}")

    except Exception as e:  # noqa: BLE001
        print(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    clean_po_files()
    print("Task completed.")
