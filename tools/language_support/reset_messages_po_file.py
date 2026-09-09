#! /usr/bin/env python3
"""
Reset a messages.po file so that it only has the 'msgid' lines.
"""


def filter_po_file(input_filename: str, output_filename: str) -> None:
    """
    Reads a .po file and writes a new file excluding lines starting with 'msgstr "'.
    """
    try:
        # Open the source file for reading and the target for writing
        with open(input_filename, encoding="utf-8") as infile, open(output_filename, "w", encoding="utf-8") as outfile:
            for line in infile:
                # .startswith() checks the beginning of the string
                # We use .lstrip() just in case there is leading whitespace
                if not line.lstrip().startswith('msgstr "'):
                    outfile.write(line)

        print(f"Successfully created: {output_filename}")

    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' was not found.")
    except Exception as e:  # noqa: BLE001
        print(f"An unexpected error occurred: {e}")


# Run the function
if __name__ == "__main__":
    input_file = "/Users/mikrubin/MapTasker/maptasker/locale/ur/LC_MESSAGES/messages.po"
    filter_po_file(input_file, "messages_msgid_only.po")
