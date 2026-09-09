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
| `sync_and_clean_po.py` | Brings every catalog up to date and repairs it, in seven stages |
| `translate_po.py` | Machine-translates untranslated entries (Google Translate) |
| `translate_text_lines_to_po.py` | Turns a plain list of strings into catalog entries |
| `find_english_msgstr_liners.py` | Reports translations that are still English |
| `replace_line_in_po.py`, `reset_messages_po_file.py` | Small catalog edits |
| `po_to_mo.sh` | Compiles every `messages.po` to the `messages.mo` the app loads |

`sync_and_clean_po.py` is the one to reach for after adding a
`translate_string()` call or rewording a help screen, and the one to run when a
`tests/test_userhelp.py` help-text assertion fails. Its stages, in order:

| # | Name | What it does |
| --- | --- | --- |
| 1 | `sync` | Adds msgids the code asks for but a catalog does not hold |
| 2 | `prune` | Drops help-text entries whose English has since been reworded |
| 3 | `dups` | Removes second and later definitions of the same msgid |
| 4 | `newlines` | Makes each msgstr agree with its msgid on leading/trailing newlines |
| 5 | `urls` | Restores URLs that machine translation mangled |
| 6 | `quotes` | Repairs msgstr lines with unescaped quotes |
| 7 | `blanks` | Keeps only the first blank line of each catalog |

It writes by default and is safe to re-run. `--stages` takes a subset by number
or name; `--dry-run-prune` and `--dry-run-urls` make those two stages report
instead of edit. Recompile afterwards with `po_to_mo.sh`.

```
python tools/language_support/sync_and_clean_po.py --stages newlines,urls
```

`reverse.txt`, `reverse_language.po` and `reverse_language.pot` are fixture
input for `translate_po.py`, not catalogs the app loads.

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
