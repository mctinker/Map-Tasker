#! /usr/bin/env python3
"""
Bring every messages.po up to date with the strings the code actually asks to translate.

Scans maptasker/src for literals handed to translate_string() (and the PrimeItems._ /
_translate aliases), works out which of them each language's catalog is missing, and
appends just those -- translated via deep-translator, the same way translate_po.py and
translate_text_lines_to_po.py do.

Unlike translate_text_lines_to_po.py, which appends its input to all 33 catalogs blindly,
this only writes what a given catalog actually lacks.  That matters because msgfmt rejects
a .po with two definitions of the same msgid, so blind appends need a delete_dups pass
afterwards to stay compilable; this is re-runnable as-is.

Run it after adding new translate_string() calls, then run po_to_mo.sh to recompile.
"""

import ast
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

        print("bingo fallback AI translation:", translated_text)
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


def main() -> int:
    """Sync every catalog under LOCALE_PATH against the strings the source asks for."""
    wanted = source_strings() | help_text_strings()
    print(f"strings requiring translation (call sites + userhelp constants): {len(wanted)}\n")

    catalogs = sorted(LOCALE_PATH.glob("*/LC_MESSAGES/messages.po"))
    if not catalogs:
        print(f"No catalogs found under {LOCALE_PATH}")
        return 8

    total_added = total_failed = 0
    for po_file in catalogs:
        print(f"\nSyncing {po_file}...")
        added, failed = sync_language(po_file, po_file.parent.parent.name, wanted)
        total_added += added
        total_failed += failed

    print(f"\nDone: {total_added} entries added, {total_failed} failed.")
    print("Now run po_to_mo.sh to recompile the .mo files.")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
