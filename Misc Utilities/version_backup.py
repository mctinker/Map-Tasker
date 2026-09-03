#! /usr/bin/env python3
"""Backup Script: Compresses the current directory into a ZIP archive and copies it to specified destination directories.
This script prompts the user for a version ID, creates a timestamped ZIP archive of the current directory, and copies it to the specified destination directories."""

import datetime
import os
import shutil
import tempfile
import zipfile

# ==============================================================================

# CONFIGURATION

# ==============================================================================

# Add the full paths of the destination directories where copies will be sent.
DESTINATION_DIRECTORIES = [
    r"/Volumes/MyStuff/AMyStuff/Backups/MapTasker_Dev Older Copies",
    r"/Users/mikrubin/MikeSafe/MapTasker_Dev",
    r"/Users/mikrubin/Library/CloudStorage/GoogleDrive-mikrubin@gmail.com/My Drive/AMyStuff/Backups/MapTasker_Dev Older Copies",
]

# Add names of files or directories you wish to EXCLUDE from the backup.
# Examples: "__pycache__", ".git", "venv", "temp_data.csv", "backup_version.py"
EXCLUDE_LIST = {
    "__pycache__",
    "*/__pycache__/*",
    ".git",
    ".venv",
    "venv",
    ".ruff_cache",
    ".pytest_cache",
    "*.txt",
    "*.log",
    "*.pyc",
    ".vscode/extensions/",
    "dist/*",
    "*/dist/*",
    ".nicegui/*",
    "*/.nicegui/*",
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def get_supported_compression_methods() -> list[tuple[str, int]]:
    """Returns a list of tuples containing (method_name, zipfile_compression_constant)
    supported by the current Python environment.
    """
    methods = [
        ("STORED (No Compression)", zipfile.ZIP_STORED),
        ("DEFLATED (Standard)", zipfile.ZIP_DEFLATED),
    ]

    # BZIP2 support check
    try:
        import bz2  # noqa: F401, PLC0415

        methods.append(("BZIP2", zipfile.ZIP_BZIP2))
    except ImportError:
        pass

    # LZMA support check
    try:
        import lzma  # noqa: F401, PLC0415

        methods.append(("LZMA", zipfile.ZIP_LZMA))
    except ImportError:
        pass

    return methods


def is_excluded(item_name: str) -> bool:
    """Checks whether a given file or directory name is in the exclusion list."""
    return item_name in EXCLUDE_LIST


def build_zip_archive(target_path: str, compression_type: int) -> None:
    """Recursively walks the current directory and creates a zip file at target_path
    using the specified compression type, respecting the EXCLUDE_LIST.
    """
    with zipfile.ZipFile(target_path, "w", compression=compression_type) as zip_file:
        for root, dirs, files in os.walk("."):
            # Prune excluded directories in-place so os.walk does not recurse into them
            dirs[:] = [d for d in dirs if not is_excluded(d)]
            for file in files:
                if is_excluded(file):
                    continue
                filepath = os.path.join(root, file)

                # Skip the output zip file if it's stored in the current working directory
                if os.path.abspath(filepath) == os.path.abspath(target_path):
                    continue

                # Write file with relative path inside the zip archive
                zip_file.write(filepath, arcname=filepath)


def create_smallest_zip_archive(final_zip_filename: str) -> None:
    """Tests all supported compression methods in temporary files, finds the one
    that yields the smallest file size, and saves it as final_zip_filename.
    """

    # Override the supported methods to only use LZMA for now, as it is generally the most efficient.
    # supported_methods = get_supported_compression_methods()
    supported_methods = [("LZMA", 14)]
    best_method_name = None
    best_size = float("inf")
    best_temp_path = None
    print("Testing compression methods to find the smallest file size...")

    # Temporary folder to hold trial zip files during comparison
    with tempfile.TemporaryDirectory() as temp_dir:
        for method_name, compression_const in supported_methods:
            temp_zip_path = os.path.join(temp_dir, f"test_{compression_const}.zip")
            try:
                build_zip_archive(temp_zip_path, compression_const)
                size = os.path.getsize(temp_zip_path)
                print(f"  - {method_name}: {size:,} bytes")
                if size < best_size:
                    best_size = size
                    best_method_name = method_name
                    best_temp_path = temp_zip_path
            except Exception as err:  # noqa: BLE001
                print(f"  - {method_name}: Failed ({err})")
        if best_temp_path and os.path.exists(best_temp_path):
            print(f"\nSelected '{best_method_name}' ({best_size:,} bytes).")

            shutil.copy2(best_temp_path, final_zip_filename)

        else:
            msg = "Failed to build archive with any compression method."
            raise RuntimeError(msg)


def copy_archive_to_destinations(source_zip: str, destinations: list[str]) -> None:
    """Copies the final archive to each destination directory path."""
    for dest_dir in destinations:
        if os.path.exists(dest_dir):
            target_path = os.path.join(dest_dir, source_zip)
            shutil.copy2(source_zip, target_path)
            print(f"Copied to: {target_path}")
        else:
            print(f"Warning: Destination '{dest_dir}' does not exist. Skipping.")


# ==============================================================================
# MAIN WORKFLOW
# ==============================================================================


def main() -> None:
    """Main function to execute the backup process."""
    # 1. Prompt for Version ID
    version_id = input("Enter the version ID (e.g., 12.2.3): ").strip()
    if not version_id:
        version_id = "NoVersionID"
        # print("Error: Version ID cannot be empty.")
        # return

    # 2. Construct Filename
    current_dir_name = os.path.basename(os.getcwd())
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # noqa: DTZ005
    zip_filename = f"{current_dir_name}_{timestamp}-Version-{version_id}.zip"
    try:
        # 3. Test algorithms and write the smallest zip file locally
        create_smallest_zip_archive(zip_filename)

        # 4. Copy archive to all destination directories
        copy_archive_to_destinations(zip_filename, DESTINATION_DIRECTORIES)
    finally:
        # 5. Clean up temporary local archive
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
            print(f"Cleaned up temporary local archive: {zip_filename}")
    print("Process completed successfully.")


if __name__ == "__main__":
    main()
