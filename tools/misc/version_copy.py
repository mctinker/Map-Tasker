#! /usr/bin/env python3
"""
Directory Copier and String Replacer.

This module copies all files and subdirectories from a source directory to a target
directory, completely overwriting the target directory if it exists. During the copy
process, it replaces all occurrences of a specified string in directory names,
filenames, and inside text files while preserving original timestamps.
"""

import os
import shutil


def is_text_file(filepath: str) -> bool:
    """
    Determine if a file is plain text by attempting to read a sample chunk.

    Reading a small sample helps prevent attempting text replacement on binary
    files (e.g., images, executables, archives) which could corrupt them.

    Args:
        filepath: The full or relative path to the file to check.

    Returns:
        True if the file can be read as UTF-8 text, False otherwise.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            f.read(1024)
            return True
    except (UnicodeDecodeError, OSError):
        return False


def replace_in_file(filepath: str, old_str: str, new_str: str) -> None:
    """
    Replace all occurrences of a substring inside a text file.

    Args:
        filepath: Path to the target text file.
        old_str: The target substring to be replaced.
        new_str: The substring to replace `old_str` with.
    """
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if old_str in content:
            new_content = content.replace(old_str, new_str)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
    except Exception as e:  # noqa: BLE001
        print(f"Skipped text replacement for {filepath}: {e}")


def copy_and_rename(
    src_dir: str,
    dest_dir: str,
    old_str: str,
    new_str: str,
    exclude_files: list[str] | None = None,
) -> None:
    """
    Copy a directory tree to a new location, replacing target contents and string matches.

    Cleans and replaces the destination directory if it already exists. Recursively
    copies all subdirectories and files from `src_dir` to `dest_dir`, replacing
    occurrences of `old_str` with `new_str` in folder names, filenames, and text content.
    Retains all file and directory timestamp metadata (access and modification times).

    Args:
        src_dir: Path to the source directory.
        dest_dir: Path to the destination directory. Existing contents will be removed.
        old_str: The substring to search for in paths and file content.
        new_str: The substring to substitute for `old_str`.
        exclude_files: List of file names to exclude from copying.
    """
    if exclude_files is None:
        exclude_files = []
    exclude_set = set(exclude_files)

    src_dir = os.path.abspath(src_dir)
    dest_dir = os.path.abspath(dest_dir)

    # 1. Clean the target directory if it already exists
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    # Dictionary to record source directory paths and their corresponding destination paths
    dir_metadata_map = {}

    # 2. Walk through the source directory top-down
    for root, _dirs, files in os.walk(src_dir):
        rel_path = os.path.relpath(root, src_dir)

        # Replace string in the current directory relative path
        renamed_rel_path = rel_path.replace(old_str, new_str)
        current_dest_dir = os.path.join(dest_dir, renamed_rel_path)

        # Ensure destination subdirectory exists
        os.makedirs(current_dest_dir, exist_ok=True)
        dir_metadata_map[current_dest_dir] = root

        # 3. Process files
        for file in files:
            # Skip files specified in exclude_files
            if file in exclude_set:
                continue

            src_file_path = os.path.join(root, file)

            # Replace string in filename
            renamed_file = file.replace(old_str, new_str)
            dest_file_path = os.path.join(current_dest_dir, renamed_file)

            # Copy file with permissions and initial metadata
            shutil.copy2(src_file_path, dest_file_path)

            # 4. Modify text contents if it's a text file
            if is_text_file(dest_file_path):
                replace_in_file(dest_file_path, old_str, new_str)

            # Re-apply source timestamp metadata (mtime/atime) after file modification
            shutil.copystat(src_file_path, dest_file_path)

    # 5. Apply directory metadata (done bottom-up so child creation doesn't overwrite parent mtime)
    for target_path in sorted(dir_metadata_map.keys(), key=len, reverse=True):
        source_path = dir_metadata_map[target_path]
        shutil.copystat(source_path, target_path)


# --- Example Usage ---
if __name__ == "__main__":
    SOURCE_DIRECTORY: str = "/Users/mikrubin/MapTasker_Dev"
    TARGET_DIRECTORY: str = "/Users/mikrubin/MapTasker"
    OLD_STRING: str = "MapTasker_Dev"
    NEW_STRING: str = "MapTasker"
    FILES_TO_EXCLUDE: list[str] = [".DS_Store", "maptasker-dev.code-workspace", "secret.key"]

    # Execute the copy and string replacement
    copy_and_rename(
        SOURCE_DIRECTORY,
        TARGET_DIRECTORY,
        OLD_STRING,
        NEW_STRING,
        exclude_files=FILES_TO_EXCLUDE,
    )
    print(
        f"Successfully copied and renamed occurrences of '{OLD_STRING}' to '{NEW_STRING}' while preserving timestamps.",
    )
