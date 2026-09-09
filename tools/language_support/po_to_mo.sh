#!/usr/bin/env fish

# Compile every messages.po under maptasker/locale into its messages.mo.
#
# This replaces the previous hand-maintained list of 33 msgfmt invocations.  Adding a
# language now needs no edit here at all -- create locale/<code>/LC_MESSAGES/messages.po
# and it is picked up.  The old list also had to be kept in step with the language dict
# in translate_text_lines_to_po.py, so a language added to one but not the other was
# translated and then never compiled (or vice versa).
#
# Checking the exit status is the real change here.  msgfmt already reports problems --
# a msgid and msgstr disagreeing about a leading/trailing newline, say, which machine
# translation causes routinely by dropping the blank lines MapTasker's tooltips use for
# spacing -- as a "fatal error" and exits 1, with or without --check.  It nevertheless
# still writes a complete .mo, that entry included, so nothing visibly breaks at runtime
# and the old script (which never looked at exit codes, and printed 33 language banners
# the errors scrolled past) let those reports go unnoticed indefinitely.  Here a bad
# catalog is named and the script exits non-zero, so the problem gets fixed.
#
# --check adds the msgfmt checks that are not on by default (format strings, header,
# domain).  All 33 catalogs pass it today.
#
# Usage:
#   ./po_to_mo.sh                  # compile maptasker/locale next to this repo
#   ./po_to_mo.sh <locale_dir>     # compile some other tree (used to test changes)

set script_dir (dirname (status --current-filename))

if set -q argv[1]
    set locale_dir $argv[1]
else
    set locale_dir $script_dir/../maptasker/locale
end

if not test -d $locale_dir
    echo "po_to_mo: no such locale directory: $locale_dir" >&2
    exit 1
end

set catalogs $locale_dir/*/LC_MESSAGES/messages.po
if not set -q catalogs[1]
    echo "po_to_mo: no messages.po found under $locale_dir" >&2
    exit 1
end

set compiled 0
set failed

for po in $catalogs
    # locale/<code>/LC_MESSAGES/messages.po -- the language code is two levels up.
    set lang (basename (dirname (dirname $po)))
    set mo (dirname $po)/messages.mo

    echo -n "$lang: "
    # msgfmt reports its statistics and any errors on stderr, so let both through.
    if msgfmt --check --statistics -o $mo $po
        set compiled (math $compiled + 1)
    else
        set failed $failed $lang
    end
end

echo ""
echo "Compiled $compiled catalog(s) into .mo files."

if set -q failed[1]
    echo "FAILED: $failed" >&2
    echo "A .mo was still written for those languages -- msgfmt reports these errors but" >&2
    echo "compiles anyway -- so fix the .po and re-run rather than trusting the output." >&2
    echo "A msgid/msgstr newline mismatch is repairable with fix_newline_edges_in_po.py." >&2
    exit 1
end
