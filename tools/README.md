# tools

Maintainer utilities. **Nothing here is part of the MapTasker package.**

None of it is imported by `maptasker/`, shipped in the wheel, or exercised by
the production code. It is the maintainer tooling used to build the wiki and keep
the translation catalogs in step with the code. Read a script's docstring before
running it; several take a path and edit files in place.

These are held to the project's lint and format gates (`[tool.ruff]` covers
`tools/` as well as `maptasker/` and `scripts/`), with a few relaxed rules for
one-off scripts listed in `pyproject.toml`.

## language_support/

Everything that keeps `maptasker/locale/*/LC_MESSAGES/messages.po` in step with
the strings the code actually asks to translate. Roughly in the order you would
use them:

| Script | What it does |
| --- | --- |
| `check_catalogs.py` | **Run this periodically.** Checks every catalog against the source, and every translated README against `README.md`, and with `--fix` brings them up to date |
| `sync_and_clean_po.py` | Brings every catalog up to date and repairs it, in seven stages |
| `translate_po.py` | Machine-translates untranslated entries (Google Translate) |
| `po_to_mo.sh` | Compiles every `messages.po` to the `messages.mo` the app loads |

`check_catalogs.py` is the one to run now and then (after adding a `translate_string()` call, rewording a help
screen, and before a release). On its own it only reports, one line a language, and exits 1 if anything needs doing:

```
python tools/language_support/check_catalogs.py                      # look
python tools/language_support/check_catalogs.py --fix                # translate what is missing, repair, recompile
python tools/language_support/check_catalogs.py --fix --no-translate # add it blank (shown in English) and translate later
python tools/language_support/check_catalogs.py --lang de --verbose  # one language, every string listed
python tools/language_support/check_catalogs.py --readme-only        # only the translated READMEs (or --catalogs-only)
```

It reports a string the program asks for that a catalog lacks; a string the program translates through a variable
(the language names, say) that nearly every catalog holds and one does not; a blank translation; a msgid defined
twice; a placeholder (`{count}`, `%s`) the translation lost; a `msgctxt` entry, which the program never looks up; and a
`messages.mo` that no longer says what its `.po` says. `--fix` removes the duplicates, makes context entries plain,
translates and adds what is missing (Ollama first, then Google: it needs the `ai` extra and a network), runs the repair
stages below over what was translated, and recompiles the `.mo` files. It never deletes a translation: the "orphans"
in a catalog are mostly reverse entries (`Nada` -> `None`) that turn a language the user typed in their own words
back into English. Machine translation of a single word has no context -- check the short ones it adds (`Finish`, the
program's spelling of the language Finnish, comes back as the verb). A placeholder it can only report.

It also checks `README_translated/README.<code>.md` against `README.md`, block by block (paragraph, list, table, code
block ...): a block the English has and the translation lacks, one whose links, images, code or table shape differ, one
only the translation has, a missing note after the title pointing back to the English, and blocks still in English.
`--fix` adds, replaces and drops those, and translates what is in English, with code, URLs and link targets protected from
the translator (a line that loses one stays in English and is retried next run). With `--no-translate` the English goes in
as it is. Rewriting a file also tidies its blank lines, and machine translation is a start -- read it before a release.

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
| `build_runtime_options_wiki.py` | Generates `Runtime-Options.md` and optionally publishes it |
| `build_generated_files_doc.py` | Generates the Generated-Output wiki page from `generated_output_files.md` |
| `wikipub.py` | The publishing helper the three generators share |

`publish-wikis.sh` at the repository root runs all three.

`Command-Reference.md` is generated output, checked in because it is the copy
published to the wiki. `no_description.log` is a per-run diagnostic and is
ignored by git -- rebuild it rather than reading a stale copy:

```
python tools/misc/build_command_wiki.py --stats
```
