#! /usr/bin/env python3
"""
Bring every messages.po up to date and then tidy it, in one pass.

This is the combination of seven scripts that were always run back to back, in this order:

  1. sync_missing_msgids          - append the strings the code asks for but a catalog lacks
  2. prune_stale_help_msgids      - drop help-screen entries whose English has since changed
  3. delete_dups_from_po          - remove second and later definitions of the same msgid
  4. fix_newline_edges_in_po      - make each msgstr start and end in newlines like its msgid
  5. fix_urls_in_po               - restore URLs that machine translation altered
  6. fix_msgstr_double_quotes_in_po - turn unescaped inner double quotes in msgstr into '
  7. delete_blank_lines_in_po     - keep only the first blank line of each catalog

Stages 1-3 decide which entries a catalog holds; 4-5 repair the content of the translations
themselves; 6-7 are the cosmetic tidy-up that goes last.

Run it after adding new translate_string() calls or editing a help screen, then run
po_to_mo.sh to recompile the .mo files.

Usage:
    sync_and_clean_po.py                      run all seven stages
    sync_and_clean_po.py --stages 3,6,7       run only the stages listed (names also work,
                                              e.g. --stages dups,quotes,blanks)
    sync_and_clean_po.py --dry-run-prune      report stale help entries without deleting
    sync_and_clean_po.py --dry-run-urls       report altered URLs without repairing them

Note on ordering: stage 2 deletes stale help entries so that stage 1 can add correctly
worded replacements, so running prune before sync gets both done in a single pass.  In the
order above, a stale entry pruned in stage 2 is not replaced until the next run.
"""

import argparse
import ast
import difflib
import os
import re
import socket
import sys
import time
from pathlib import Path

from maptasker.src.primitem import PrimeItems
from ollama import chat

# deep-translator issues its HTTP GET with no timeout, so a stalled connection to Google
# blocks forever and no exception is ever raised.  Same guard translate_text_lines_to_po.py
# uses -- it must run before the first request is made.
socket.setdefaulttimeout(20)

import requests
from deep_translator import GoogleTranslator
from deep_translator.exceptions import NotValidLength, TooManyRequests

SRC_PATH = Path("/Users/mikrubin/MapTasker_Dev/maptasker/src")
LOCALE_PATH = Path("/Users/mikrubin/MapTasker_Dev/maptasker/locale")

# Function names that mean "this string is user-visible and must be translated".
TRANSLATE_FUNCS = {"translate_string", "_translate", "_"}

# GoogleTranslator refuses anything from 5000 characters up (deep_translator's
# is_input_valid, called from google.py with max_chars=5000) and raises NotValidLength
# rather than translating a prefix.  The whole userhelp.py INFO_TEXT is a single msgid
# and has already grown past that, so long strings are translated a piece at a time and
# reassembled.  Held well under 5000: a translation can come back longer than the
# English it was given, and the reassembled string is what has to survive, not the
# request.
MAX_TRANSLATE_CHARS = 4000

REQUEST_DELAY = 0.4
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 3
THROTTLE_BACKOFF_SECONDS = 30

# How alike a catalog msgid must be to a current help text before it counts as that help
# text's stale predecessor.  0.55 comfortably clears the most heavily rewritten one seen
# (VIEW_HELP_TEXT, 57%) while staying far above any unrelated string's resemblance.
SIMILARITY_FLOOR = 0.55

# A help text is long and multi-line; nothing short can be a stale copy of one.
MIN_LENGTH = 300

ENTRY_RE = re.compile(
    r'^msgid\s+(?P<id>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)'
    r'\s*\nmsgstr\s+(?P<str>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)\s*?$',
    re.MULTILINE,
)

# The same entry, but keeping the "msgid " / newline / "msgstr " text in groups of their
# own, so a stage that rewrites only the msgstr can put the entry back together verbatim.
REPAIR_ENTRY_RE = re.compile(
    r'(?P<head>^msgid\s+)(?P<id>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)'
    r'(?P<mid>\s*\nmsgstr\s+)(?P<str>"(?:[^"\\]|\\.)*"(?:\s*\n\s*"(?:[^"\\]|\\.)*")*)',
    re.MULTILINE,
)

# Stop at whitespace and at quotes, so a URL embedded in a quoted JSON example does not
# swallow the closing quote.
URL_RE = re.compile(r"https?://[^\s'\"]+")


def catalogs() -> list[Path]:
    """Every messages.po under LOCALE_PATH, in a stable order."""
    return sorted(LOCALE_PATH.rglob("messages.po"))


def decode(po_literal: str) -> str:
    """Concatenate a (possibly multi-line) .po string literal into its actual value."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', po_literal)
    return (
        "".join(parts)
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def encode(text: str) -> str:
    """Render a value back as a single-line .po string literal."""
    escaped = (
        text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    )
    return f'"{escaped}"'


# ######################################################################################
# Stage 1: sync missing msgids
# ######################################################################################
def source_strings() -> set[str]:
    """This function scans all Python files in the target source directory (SRC_PATH) to find every string literal that requires translation."""
    found = set()
    for py_file in sorted(SRC_PATH.glob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError as e:
            print(f"[Skipping] {py_file.name} does not parse: {e}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                continue
            if name not in TRANSLATE_FUNCS:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.strip():
                found.add(first.value)
    return found


def help_text_strings() -> set[str]:
    """The userhelp.py constants, which the AST scan above cannot see."""
    sys.path.insert(0, str(SRC_PATH.parent.parent))
    from maptasker.src import userhelp  # noqa: PLC0415

    return {
        value
        for name in dir(userhelp)
        if name.isupper() and name not in {"HELP", "VERSION"}
        if isinstance(value := getattr(userhelp, name), str) and value.strip()
    }


def existing_msgids(po_file: Path) -> set[str]:
    """The msgids a catalog already defines, following multi-line continuations."""
    msgids = set()
    current = None
    for raw_line in po_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith('msgid "'):
            current = ast.literal_eval(line[len("msgid ") :])
        elif current is not None and line.startswith('"'):
            # A continuation line of the msgid currently being read.
            current += ast.literal_eval(line)
        elif current is not None:
            if current:
                msgids.add(current)
            current = None
    if current:
        msgids.add(current)
    return msgids


def escape_po(text: str) -> str:
    """Make a string safe inside a double-quoted .po value."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")


def get_key_by_value(dictionary: dict, target_value: str) -> str | None:
    """Returns the first key that matches target_value, or None if not found."""
    for key, value in dictionary.items():
        if value == target_value:
            return key
    return None


def fallback_ai_translate(target_lang: str, text: str) -> str | None:
    """Use Ollama's chat model to translate text when GoogleTranslator fails."""
    print("Using fallback AI translator (Ollama) for translation:", text)

    # Try the target_lang directly, or try converting hyphen to underscore as fallback
    target_lang_name = (
        get_key_by_value(PrimeItems.languages, target_lang)
        or get_key_by_value(PrimeItems.languages, target_lang.replace("-", "_"))
        or target_lang
    )

    msg = f"""You are a professional English (en) to {target_lang_name} ({target_lang}) translator. Your goal is to accurately convey the meaning and nuances of the original English (en) text while adhering to {target_lang_name} grammar, vocabulary, and cultural sensitivities. Produce only the {target_lang_name} translation, without any additional explanations or commentary. Please translate the following English (en) text into {target_lang_name} ({target_lang}):

{text}"""

    try:
        response = chat(
            model="translategemma",
            messages=[{"role": "user", "content": msg}],
        )

        # Ollama's chat response stores content in response['message']['content'] or response.message.content
        translated_text = None
        if hasattr(response, "message") and hasattr(response.message, "content"):
            translated_text = response.message.content.strip()
        elif isinstance(response, dict):
            translated_text = response.get("message", {}).get("content", "").strip()

        print("      fallback AI translation:", translated_text)
        return translated_text if translated_text else None

    except Exception as e:  # noqa: BLE001
        print(f"    [Fallback Error] Ollama chat failed: {e}")
        return None


def translate_with_retry(translator: GoogleTranslator, target_lang: str, text: str) -> str | None:
    """Translate one string, backing off on timeouts and throttling.

    Falls back to ai-translator if GoogleTranslator attempts fail or crash.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            translated = translator.translate(text)
            # deep-translator returns None when the translation matches the input
            # (common for 'Save', 'Ok', etc.) -- that means "no change needed".
            return text if translated is None else translated  # noqa: TRY300

        except TooManyRequests:
            wait = THROTTLE_BACKOFF_SECONDS * attempt
            print(f"    [Throttled] waiting {wait}s before retry {attempt}/{MAX_ATTEMPTS}")
            time.sleep(wait)

        except (TimeoutError, requests.exceptions.RequestException, OSError) as e:
            wait = BACKOFF_SECONDS * attempt
            print(f"    [Network] {type(e).__name__}: {e} - retry {attempt}/{MAX_ATTEMPTS} in {wait}s")
            time.sleep(wait)

        except NotValidLength:
            # split_for_translation() below is meant to make this unreachable; if it ever
            # does fire, say which string and how long it was rather than leaving a bare
            # exception name to be tracked down.
            print(
                f"    [Error] NotValidLength: {len(text)} characters exceeds the "
                f"translator's limit -- MAX_TRANSLATE_CHARS is {MAX_TRANSLATE_CHARS}",
            )
            break

        except Exception as e:  # noqa: BLE001
            print(f"    [Error] {type(e).__name__}: {e}")
            break

    # If GoogleTranslator runs through retry attempts or throws an exception, use AI fallback
    return fallback_ai_translate(target_lang, text)


def split_for_translation(text: str, limit: int = MAX_TRANSLATE_CHARS) -> list[str]:
    r"""Break `text` into pieces no longer than `limit`, so that "".join() rebuilds it exactly.

    Blank lines first, then single newlines, then a hard cut -- in that order, so a break
    lands on a paragraph boundary wherever the text offers one.  The separators are kept
    (re.split with a capturing group returns them), and every piece is translated with its
    own leading/trailing newlines held back and re-attached, which is what makes the
    concatenation lossless rather than merely close.
    """
    if len(text) <= limit:
        return [text]

    def by_separator(chunk: str, pattern: str) -> list[str]:
        """Regroup `chunk`'s parts into the largest runs that still fit under the limit."""
        parts = [part for part in re.split(pattern, chunk) if part]
        pieces: list[str] = []
        current = ""
        for part in parts:
            if current and len(current) + len(part) > limit:
                pieces.append(current)
                current = ""
            current += part
        if current:
            pieces.append(current)
        return pieces

    pieces = by_separator(text, r"(\n{2,})")
    # A single paragraph over the limit: try again on single newlines, and failing that
    # (one very long unbroken line) cut it at the limit.  Both are last resorts -- neither
    # is reached by anything in userhelp.py today.
    if any(len(piece) > limit for piece in pieces):
        pieces = [
            sub_piece
            for piece in pieces
            for sub_piece in (by_separator(piece, r"(\n)") if len(piece) > limit else [piece])
        ]
    if any(len(piece) > limit for piece in pieces):
        pieces = [
            piece[start : start + limit] if len(piece) > limit else piece
            for piece in pieces
            for start in (range(0, len(piece), limit) if len(piece) > limit else [0])
        ]
    return pieces


def translate_preserving_edges(translator: GoogleTranslator, target_lang: str, text: str) -> str | None:
    r"""Translate, keeping any leading/trailing newlines the original had.

    Anything over the translator's length limit goes over in pieces (see
    split_for_translation) and comes back concatenated, because the msgid the catalog needs
    is the whole string -- INFO_TEXT is asked for in one go at runtime, not paragraph by
    paragraph.
    """
    pieces = split_for_translation(text)
    translated_pieces = []
    if len(pieces) > 1:
        print(f"  [Split] {len(text)} characters -> {len(pieces)} pieces")

    for piece in pieces:
        core = piece.strip("\n")
        if not core:
            # Nothing but newlines: keep it verbatim, and don't spend a request on it.
            translated_pieces.append(piece)
            continue
        leading = piece[: len(piece) - len(piece.lstrip("\n"))]
        trailing = piece[len(piece.rstrip("\n")) :]

        translated = translate_with_retry(translator, target_lang, core)
        if translated is None:
            return None
        # Normalise before re-attaching leading/trailing newlines
        translated_pieces.append(leading + translated.strip("\n") + trailing)

    return "".join(translated_pieces)


def sync_language(po_file: Path, lang_dir: str, wanted: set[str]) -> tuple[int, int]:
    """Append every wanted string this catalog is missing.  Returns (added, failed)."""
    missing = sorted(wanted - existing_msgids(po_file))
    if not missing:
        print(f"{lang_dir}: already complete")
        return 0, 0

    # deep-translator/Google expect 'zh-CN' rather than the 'zh_CN' directory name.
    target_lang = lang_dir.replace("_", "-")

    print(f"{lang_dir}: {len(missing)} missing -> {po_file}")
    translator = None
    try:
        translator = GoogleTranslator(source="en", target=target_lang)
    except Exception as e:  # noqa: BLE001
        print(f"  [Error] could not create GoogleTranslator for {lang_dir}: {e}")

    added = failed = 0
    # Hold the file open for the whole language rather than reopening per string.
    with po_file.open("a", encoding="utf-8") as out:
        for text in missing:
            translated = None
            if translator:
                translated = translate_preserving_edges(translator, target_lang, text)
            else:
                # If GoogleTranslator failed initialization, jump directly to AI Translator fallback
                translated = fallback_ai_translate(target_lang, text)

            if translated is None:
                failed += 1
                print(f"  [Failed] {text!r}")
                continue
            out.write(f'\nmsgid "{escape_po(text)}"\n')
            out.write(f'msgstr "{escape_po(translated)}"\n')
            out.flush()
            added += 1
            time.sleep(REQUEST_DELAY)

    print(f"  added {added}, failed {failed}")
    return added, failed


def stage_sync_missing_msgids() -> int:
    """Sync every catalog under LOCALE_PATH against the strings the source asks for."""
    wanted = source_strings() | help_text_strings()
    print(f"strings requiring translation (call sites + userhelp constants): {len(wanted)}\n")

    found = catalogs()
    if not found:
        print(f"No catalogs found under {LOCALE_PATH}")
        return 8

    total_added = total_failed = 0
    for po_file in found:
        print(f"\nSyncing {po_file}...")
        added, failed = sync_language(po_file, po_file.parent.parent.name, wanted)
        total_added += added
        total_failed += failed

    print(f"\nDone: {total_added} entries added, {total_failed} failed.")
    return 1 if total_failed else 0


# ######################################################################################
# Stage 2: prune stale help msgids
# ######################################################################################
def prune(po_file: Path, current: set[str], apply: bool) -> list[tuple[str, float]]:
    """Drop stale help entries from one catalog.  Returns (excerpt, similarity) removed."""
    source = po_file.read_text(encoding="utf-8")
    removed = []

    def drop(match: re.Match) -> str:
        msgid = decode(match.group("id"))
        if len(msgid) < MIN_LENGTH or msgid in current:
            return match.group(0)

        best = max(
            (difflib.SequenceMatcher(None, msgid, text).ratio() for text in current),
            default=0.0,
        )
        if best < SIMILARITY_FLOOR:
            return match.group(0)

        removed.append((msgid[:70].replace("\n", " "), best))
        return ""  # Drop the whole entry; the sync stage will re-add a current one.

    pruned = ENTRY_RE.sub(drop, source)
    if removed and apply:
        # Collapse the blank-line run the deletion leaves behind.
        po_file.write_text(re.sub(r"\n{3,}", "\n\n", pruned), encoding="utf-8")
    return removed


def stage_prune_stale_help_msgids(apply: bool = True) -> int:
    """Prune every catalog; report only when `apply` is False."""
    current = help_text_strings()
    print(f"Current help texts: {len(current)}")
    print("Mode:", "APPLY" if apply else "dry run", "\n")

    total = 0
    for po_file in catalogs():
        removed = prune(po_file, current, apply)
        if removed:
            print(f"{po_file.parent.parent.name}: {len(removed)} stale")
            for excerpt, ratio in removed:
                print(f"    {ratio:.0%}  {excerpt!r}")
            total += len(removed)

    print(f"\nTotal stale entries {'removed' if apply else 'found'}: {total}")
    if not apply and total:
        print("Re-run without --dry-run-prune to remove them.")
    return 0


# ######################################################################################
# Stage 3: delete duplicate msgids
# ######################################################################################
def remove_duplicates_from_po(file_path: str) -> None:
    """
    Reads a .po file, removes duplicate 'msgid' entries and their
    corresponding 'msgstr' lines, and saves the file.
    """
    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    seen_msgids = set()
    cleaned_lines = []

    # This flag tracks if we are currently handling a duplicate
    # so we know to skip the next line (the msgstr)
    skip_next_msgstr = False

    for line in lines:
        stripped_line = line.strip()

        # 1. Check if the line is a msgid
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

        # 2. Check if the line is a msgstr AND we are supposed to skip it
        elif stripped_line.startswith('msgstr "') and skip_next_msgstr:
            # We skip this line because it belongs to the duplicate msgid
            skip_next_msgstr = False  # Reset flag
            continue

        # 3. Handle all other lines (comments, empty lines, etc.)
        else:
            # Note: This logic assumes the msgstr follows the msgid immediately.
            # If there are empty lines between duplicate msgid and msgstr,
            # this logic might need adjustment, but standard PO files don't do that.
            cleaned_lines.append(line)

    # 4. Write the cleaned content back to the file
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)

    print(f"Cleaned: {file_path}")


def stage_delete_dups_from_po() -> int:
    """Remove second and later definitions of the same msgid from every catalog."""
    if not LOCALE_PATH.exists():
        print(f"Error: Directory not found: {LOCALE_PATH}")
        return 8

    print(f"Scanning directory: {LOCALE_PATH}...\n")

    files_found = 0
    for po_file in catalogs():
        remove_duplicates_from_po(str(po_file))
        files_found += 1
        print("-" * 40)

    if files_found == 0:
        print("No 'messages.po' files found.")
    else:
        print(f"\nProcessing complete. Processed {files_found} files.")
    return 0


# ######################################################################################
# Stage 4: make msgstr newline edges match msgid
# ######################################################################################
def edges(text: str) -> tuple[str, str]:
    """The leading and trailing runs of newlines in a string."""
    leading = text[: len(text) - len(text.lstrip("\n"))]
    trailing = text[len(text.rstrip("\n")) :]
    return leading, trailing


def fix_newline_edges_in_file(po_file: Path) -> int:
    """Repair every mismatched entry in one catalog.  Returns the number fixed."""
    source = po_file.read_text(encoding="utf-8")
    fixed = 0

    def repair(match: re.Match) -> str:
        nonlocal fixed
        msgid = decode(match.group("id"))
        msgstr = decode(match.group("str"))

        # The header entry (empty msgid) is a different animal -- leave it alone.
        if not msgid or not msgstr:
            return match.group(0)

        want_lead, want_trail = edges(msgid)
        have_lead, have_trail = edges(msgstr)
        if want_lead == have_lead and want_trail == have_trail:
            return match.group(0)

        rebuilt = want_lead + msgstr.strip("\n") + want_trail
        fixed += 1
        return f"{match.group('head')}{match.group('id')}{match.group('mid')}{encode(rebuilt)}"

    repaired = REPAIR_ENTRY_RE.sub(repair, source)
    if fixed:
        po_file.write_text(repaired, encoding="utf-8")
    return fixed


def stage_fix_newline_edges_in_po() -> int:
    r"""Make every msgstr agree with its msgid about leading/trailing newlines.

    msgfmt reports a mismatch as a fatal error ("'msgid' and 'msgstr' entries do not both
    end with '\n'") and exits 1.  It does still write the .mo, that entry included, so this
    is not data loss -- but it fails the build and, more usefully, means the translated
    string lost the trailing blank line the English one uses to space a tooltip out.
    Machine translation is the usual source: Google drops those blank lines.

    Only the leading and trailing newline runs of the msgstr are touched -- the translated
    text itself is left exactly as it was.  Safe to re-run; it reports what it changed.
    """
    total = 0
    for po_file in catalogs():
        count = fix_newline_edges_in_file(po_file)
        if count:
            print(f"{po_file.parent.parent.name}: fixed {count}")
        total += count
    print(f"\nTotal entries repaired: {total}")
    return 0


# ######################################################################################
# Stage 5: restore URLs machine translation altered
# ######################################################################################
def repair_urls(msgid: str, msgstr: str) -> tuple[str, list[tuple[str, str]]]:
    """Return the msgstr with its URLs restored, plus a list of (before, after) changes."""
    expected = URL_RE.findall(msgid)
    found = URL_RE.findall(msgstr)
    if not expected or len(expected) != len(found):
        # Nothing to do, or the counts disagree -- in which case positional matching would
        # be a guess, so leave it for a human rather than corrupt it further.
        return msgstr, []

    changes = []
    result = msgstr
    for english, translated in zip(expected, found):
        if translated == english:
            continue
        if translated.startswith(english):
            extra = translated[len(english) :]
            # Punctuation the English did not have is noise; anything else is words, and
            # keeping them (spaced off the URL) preserves the sentence.
            replacement = english if extra.strip(".,;:!?)") == "" else f"{english} {extra}"
        else:
            replacement = english
        result = result.replace(translated, replacement, 1)
        changes.append((translated, replacement))
    return result, changes


def fix_urls_in_file(po_file: Path, apply: bool) -> list[tuple[str, str]]:
    """Repair one catalog.  Returns every (before, after) change made or proposed."""
    source = po_file.read_text(encoding="utf-8")
    all_changes = []

    def repair(match: re.Match) -> str:
        msgid = decode(match.group("id"))
        msgstr = decode(match.group("str"))
        if not msgid or not msgstr:
            return match.group(0)

        fixed, changes = repair_urls(msgid, msgstr)
        if not changes:
            return match.group(0)

        all_changes.extend(changes)
        return f"{match.group('head')}{match.group('id')}{match.group('mid')}{encode(fixed)}"

    repaired = REPAIR_ENTRY_RE.sub(repair, source)
    if all_changes and apply:
        po_file.write_text(repaired, encoding="utf-8")
    return all_changes


def stage_fix_urls_in_po(apply: bool = True) -> int:
    """Restore URLs that machine translation altered inside translated strings.

    A URL is not language.  Google mostly leaves them alone, but not reliably -- observed
    in MapTasker's own catalogs:

      * a letter dropped     https://taskernet.com/?public&tags=maptasker  ->  ...tags=matasker
      * case changed         https://t.ly/8vI1f                           ->  https://t.ly/8vi1f
      * a particle fused on  ...Changelog.md                              ->  ...Changelog.md에서

    The first two produce a link that simply does not work, and neither is visible without
    comparing against the English -- the help screen looks perfectly translated.

    Repair rule, applied per entry, matching the Nth URL of the msgstr to the Nth URL of
    the msgid (only when the two agree on how many there are, so nothing is guessed):

      * identical                  -> left alone
      * translated URL starts with
        the English one            -> the English URL, then the extra text, separated by a
                                      space so the link ends where it should.  Trailing
                                      ASCII punctuation is dropped instead, since the
                                      English had none there.
      * anything else              -> replaced with the English URL outright (corruption)
    """
    print("Mode:", "APPLY" if apply else "dry run", "\n")

    total = 0
    for po_file in catalogs():
        changes = fix_urls_in_file(po_file, apply)
        if changes:
            print(f"{po_file.parent.parent.name}:")
            for before, after in changes:
                print(f"    {before}")
                print(f" -> {after}")
            total += len(changes)

    print(f"\nURLs {'repaired' if apply else 'needing repair'}: {total}")
    if total and not apply:
        print("Re-run without --dry-run-urls to repair them.")
    return 0


# ######################################################################################
# Stage 6: fix inner double quotes in msgstr
# ######################################################################################
def replace_inner_quotes(line: str) -> str:
    r"""
    Replaces an unescaped " with ' inside the msgstr quotes.
    Example: msgstr "He said "Hello"" -> msgstr "He said 'Hello'"

    A quote the catalog already escapes (\") is correct as it stands and is left alone.
    Rewriting it would produce \', which is not a .po escape sequence at all: msgfmt
    rejects the whole catalog with "invalid control sequence", so every language that
    quotes a button name in its translations would stop compiling.
    """
    # Find the positions of the first and last double quotes
    first_quote_idx = line.find('"')
    last_quote_idx = line.rfind('"')

    # If we don't find at least two quotes, return line as is
    if first_quote_idx == -1 or first_quote_idx == last_quote_idx:
        return line

    # Split the line into three parts:
    # 1. Everything before and including the first quote
    # 2. The content between the quotes (where we replace)
    # 3. Everything from the last quote to the end of the line
    prefix = line[: first_quote_idx + 1]
    inner_content = line[first_quote_idx + 1 : last_quote_idx]
    suffix = line[last_quote_idx:]

    # Walk the content tracking backslash escapes, so \" (and the \\ that ends an escaped
    # backslash rather than starting an escape) are carried through untouched.
    replaced = []
    escaped = False
    for character in inner_content:
        if escaped:
            replaced.append(character)
            escaped = False
        elif character == "\\":
            replaced.append(character)
            escaped = True
        else:
            replaced.append("'" if character == '"' else character)
    new_inner = "".join(replaced)

    return prefix + new_inner + suffix


def fix_quotes_in_file(file_path: Path) -> None:
    """Keep only the first blank line and de-quote every msgstr in one catalog."""
    cleaned_lines = []
    found_first_blank = False

    try:
        with file_path.open(encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            # 1. Handle Blank Lines logic
            if not line.strip():
                if not found_first_blank:
                    cleaned_lines.append(line)
                    found_first_blank = True
                continue

            # 2. Handle msgstr replacement logic
            # We use lstrip() to catch lines that might have leading spaces
            if line.lstrip().startswith("msgstr"):
                cleaned_lines.append(replace_inner_quotes(line))
            else:
                cleaned_lines.append(line)

        with file_path.open("w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)

        print(f"Processed: {file_path}")

    except Exception as e:  # noqa: BLE001
        print(f"Error processing {file_path}: {e}")


def stage_fix_msgstr_double_quotes_in_po() -> int:
    """
    Clean every 'messages.po':
    1. Keeps only the first blank line.
    2. Replaces inner double-quotes with single quotes in msgstr lines.
    """
    print(f"Starting traversal in: {LOCALE_PATH}")
    for po_file in catalogs():
        fix_quotes_in_file(po_file)
    return 0


# ######################################################################################
# Stage 7: delete blank lines
# ######################################################################################
def strip_blank_lines_in_file(file_path: Path) -> None:
    """
    Reads a file and writes back the content with only the first blank line preserved.
    """
    cleaned_lines = []
    found_first_blank = False

    try:
        with file_path.open(encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            # .strip() checks if the line contains only whitespace or is empty
            if not line.strip():
                if not found_first_blank:
                    # This is the first blank line we've seen; keep it.
                    cleaned_lines.append(line)
                    found_first_blank = True
                # Otherwise it's a subsequent blank line; skip it.
            else:
                # It's a non-blank line; keep it.
                cleaned_lines.append(line)

        # Write the processed content back to the file
        with file_path.open("w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)

        print(f"Processed: {file_path}")

    except Exception as e:  # noqa: BLE001
        print(f"Error processing {file_path}: {e}")


def stage_delete_blank_lines_in_po() -> int:
    """Delete all blank lines in each 'messages.po' file, except for the first blank."""
    print(f"Starting traversal in: {LOCALE_PATH}")
    for po_file in catalogs():
        strip_blank_lines_in_file(po_file)
    return 0


# ######################################################################################
# Driver
# ######################################################################################
# Stage number -> (name usable with --stages, banner, callable).
STAGES = {
    1: ("sync", "Sync missing msgids", stage_sync_missing_msgids),
    2: ("prune", "Prune stale help msgids", stage_prune_stale_help_msgids),
    3: ("dups", "Delete duplicate msgids", stage_delete_dups_from_po),
    4: ("newlines", "Fix msgstr newline edges", stage_fix_newline_edges_in_po),
    5: ("urls", "Restore altered URLs", stage_fix_urls_in_po),
    6: ("quotes", "Fix double quotes in msgstr", stage_fix_msgstr_double_quotes_in_po),
    7: ("blanks", "Delete blank lines", stage_delete_blank_lines_in_po),
}


def parse_stages(spec: str) -> list[int]:
    """Turn '3,4,5' or 'dups,quotes,blanks' into an ordered list of stage numbers."""
    by_name = {name: number for number, (name, _, _) in STAGES.items()}
    wanted = set()
    for raw in spec.split(","):
        token = raw.strip().lower()
        if not token:
            continue
        if token.isdigit() and int(token) in STAGES:
            wanted.add(int(token))
        elif token in by_name:
            wanted.add(by_name[token])
        else:
            choices = ", ".join(f"{n}/{name}" for n, (name, _, _) in STAGES.items())
            raise argparse.ArgumentTypeError(f"unknown stage {raw!r}; choose from: {choices}")
    return sorted(wanted)


def main() -> int:
    """Run the requested stages, in order, over every catalog under LOCALE_PATH."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--stages",
        type=parse_stages,
        default=sorted(STAGES),
        help="Comma-separated stages to run, by number or name (default: all seven).",
    )
    parser.add_argument(
        "--dry-run-prune",
        action="store_true",
        help="Stage 2 only reports the stale help entries it would delete.",
    )
    parser.add_argument(
        "--dry-run-urls",
        action="store_true",
        help="Stage 5 only reports the URLs it would repair.",
    )
    args = parser.parse_args()

    if not args.stages:
        print("No stages selected; nothing to do.")
        return 0

    # The two stages that can report instead of write; everything else always writes.
    reporting_only = {2: args.dry_run_prune, 5: args.dry_run_urls}

    status = 0
    for number in args.stages:
        _, banner, run = STAGES[number]
        print(f"\n{'=' * 78}\nStage {number}: {banner}\n{'=' * 78}")
        result = run(apply=not reporting_only[number]) if number in reporting_only else run()
        status = status or result

    print("\nAll requested stages complete.")
    if 1 in args.stages:
        print("Now run po_to_mo.sh to recompile the .mo files.")
    return status


if __name__ == "__main__":
    sys.exit(main())
