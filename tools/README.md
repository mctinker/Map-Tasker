# tools

Maintainer utilities. **Nothing here is part of the MapTasker package.**

None of it is imported by `maptasker/`, shipped in the wheel, or exercised by
the test suite. It is the ad-hoc tooling used to build the wiki, keep the
translation catalogs in step with the code, and answer the occasional question
about the codebase. Read a script's docstring before running it; several take a
path and edit files in place.

These are also outside the lint gate. `[tool.ruff]` in `pyproject.toml` covers
`maptasker/` and `scripts/`, not `tools/` -- product code is held to the
project's standard, one-off tools are not.

## language_support/

Everything that keeps `maptasker/locale/*/LC_MESSAGES/messages.po` in step with
the strings the code actually asks to translate. Roughly in the order you would
use them:

| Script | What it does |
| --- | --- |
| `sync_missing_msgids.py` | Adds msgids the code asks for but no catalog holds |
| `prune_stale_help_msgids.py` | Drops help-text entries whose English has since been reworded |
| `translate_po.py` | Machine-translates untranslated entries (Google Translate) |
| `translate_text_lines_to_po.py` | Turns a plain list of strings into catalog entries |
| `fix_urls_in_po.py` | Restores URLs that machine translation mangled |
| `fix_newline_edges_in_po.py` | Makes each msgstr agree with its msgid on leading/trailing newlines |
| `fix_msgstr_double_quotes_in_po.py` | Repairs msgstr lines with unescaped quotes |
| `find_english_msgstr_liners.py` | Reports translations that are still English |
| `delete_dups_from_po.py`, `delete_blank_lines_in_po.py`, `replace_line_in_po.py`, `reset_messages_po_file.py` | Small catalog edits |
| `po_to_mo.sh` | Compiles every `messages.po` to the `messages.mo` the app loads |

`sync_missing_msgids.py` and `prune_stale_help_msgids.py` are the pair
`tests/test_userhelp.py` points at when a help-text assertion fails.

`reverse.txt`, `reverse_language.po` and `reverse_language.pot` are fixture
input for those scripts, not catalogs the app loads.

## misc/

| Script | What it does |
| --- | --- |
| `build_command_wiki.py` | Generates `Command-Reference.md` and optionally publishes it to the wiki |
| `check_dependencies.py` | Reports outdated project dependencies |
| `version_backup.py` | Zips the working tree to a backup directory |
| `version_copy.py` | Copies a directory, rewriting a string as it goes |
| `find_missing_action_codes.py` | Lists Tasker action codes the mapper does not recognise |
| `disp_msg.py` | Collects every `display_message_box` string in the source |
| `try_import_profile.py` | Prototype harness for `deviceinv.import_profile_to_device` |
| `trace.py`, `substr_analysis.py`, `substr_analysis1.py`, `top_argument_list.py`, `display_avail_cursors.py` | One-off analysis and debugging aids |

`Command-Reference.md` is generated output, checked in because it is the copy
published to the wiki. `no_description.log` is a per-run diagnostic and is
ignored by git -- rebuild it rather than reading a stale copy:

```
python tools/misc/build_command_wiki.py --stats
```
