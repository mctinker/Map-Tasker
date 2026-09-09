#! /usr/bin/env python3
import os


def remove_duplicates_from_po(file_path: str) -> None:
    """
    Reads a .po file, removes duplicate 'msgid' entries and their
    corresponding 'msgstr' lines, and saves the file.
    """

    # # 1. Create a backup before modifying
    # backup_path = file_path + ".bak"
    # shutil.copyfile(file_path, backup_path)
    # print(f"Backed up: {backup_path}")

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    seen_msgids = set()
    cleaned_lines = []

    # This flag tracks if we are currently handling a duplicate
    # so we know to skip the next line (the msgstr)
    skip_next_msgstr = False

    # We use an index to look ahead if necessary, though the flag method works well
    for _i, line in enumerate(lines):
        stripped_line = line.strip()

        # 2. Check if the line is a msgid
        if stripped_line.startswith('msgid "'):
            # If we were waiting to skip a msgstr but hit a new msgid, reset (safety catch)
            skip_next_msgstr = False

            # Check if we have seen this msgid before
            if stripped_line in seen_msgids:
                print(f"  [Duplicate Found] Removing: {stripped_line} in {os.path.basename(file_path)}")
                skip_next_msgstr = True  # Trigger to skip the NEXT line (msgstr)
                continue  # Skip writing this current line
            seen_msgids.add(stripped_line)
            cleaned_lines.append(line)

        # 3. Check if the line is a msgstr AND we are supposed to skip it
        elif stripped_line.startswith('msgstr "') and skip_next_msgstr:
            # We skip this line because it belongs to the duplicate msgid
            skip_next_msgstr = False  # Reset flag
            continue

        # 4. Handle all other lines (comments, empty lines, etc.)
        else:
            # If we are skipping, and we hit a random empty line, we might still want to keep it
            # But usually, we just write everything else normally.

            # Note: This logic assumes the msgstr follows the msgid immediately.
            # If there are empty lines between duplicate msgid and msgstr,
            # this logic might need adjustment, but standard PO files don't do that.
            cleaned_lines.append(line)

    # 5. Write the cleaned content back to the file
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)

    print(f"Cleaned: {file_path}")


def main() -> None:
    # Define the target directory
    target_directory = "/Users/mikrubin/MapTasker_Dev/maptasker/locale"

    # Validate directory exists
    if not os.path.exists(target_directory):
        print(f"Error: Directory not found: {target_directory}")
        return

    print(f"Scanning directory: {target_directory}...\n")

    # Walk through the directory tree
    files_found = 0
    for root, _dirs, files in os.walk(target_directory):
        for file in files:
            if file == "messages.po":
                full_path = os.path.join(root, file)
                remove_duplicates_from_po(full_path)
                files_found += 1
                print("-" * 40)

    if files_found == 0:
        print("No 'messages.po' files found.")
    else:
        print(f"\nProcessing complete. Processed {files_found} files.")


if __name__ == "__main__":
    main()
