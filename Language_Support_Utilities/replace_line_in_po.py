#! /usr/bin/env python3
"""
Replace a string (e.g. 'msgid = "search"') with another string (e.g. 'msgid = "Search"')
in all messages.po files under the specified locale directory and its subdirectories.
"""

import os


def update_po_files(root_dir: str, target_text: str, replacement_text: str) -> None:
    """
    Traverses subdirectories to find messages.po files and replaces specific text.
    """
    # Normalize path for the current OS
    root_dir = os.path.abspath(root_dir)

    count = 0

    # os.walk goes through every folder and subfolder
    for root, _dirs, files in os.walk(root_dir):
        for filename in files:
            # Only process messages.po files
            if filename == "messages.po":
                file_path = os.path.join(root, filename)

                # 1. Read the file content
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # 2. Check if the target text exists in this file
                if target_text in content:
                    # 3. Perform the substitution
                    updated_content = content.replace(target_text, replacement_text)

                    # 4. Write the changes back to the file
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(updated_content)

                    print(f"Updated: {file_path}")
                    count += 1
                else:
                    print(f"Skipped (Not found): {file_path}")

    print(f"\nTask complete. {count} files were updated.")


# --- CONFIGURATION ---
# Change '.' to the actual path of your 'locale' folder if this script
# isn't running in the parent directory.
LOCALE_PATH = "/Users/mikrubin/MapTasker_Dev/maptasker/locale"

# Example: Adding msgctxt to your "Top" entry
OLD_LINE = "Click 'Get Local XML' to try a different XML file."
NEW_LINE = "Invalid XML!  Click 'Get Local XML File' to try a different XML file."

if __name__ == "__main__":
    update_po_files(LOCALE_PATH, OLD_LINE, NEW_LINE)
