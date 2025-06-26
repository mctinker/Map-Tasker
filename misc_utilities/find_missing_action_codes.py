"""Match all Task actions agaianst our actyion codes and output those that are not found"""

import json

from maptasker.src.actionc import action_codes

# Extract set of 'display' values for fast lookup
valid_display_values = {code.name for code in action_codes.values()}

# Load JSON file
with open("task_all_actions.json", encoding="utf-8") as file:
    data = json.load(file)

# Collect names not found in action_codes
missing_names = [
    entry["name"] for entry in data if entry["name"] not in valid_display_values
]

# Write missing names to output file
with open("codes_not_found.txt", "w", encoding="utf-8") as file:
    file.write("\n".join(missing_names))

print(
    f"Done! {len(missing_names)} names not found and written to 'codes_not_found.txt'."
)
