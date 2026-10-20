#!/usr/bin/env bash
#
# publish-wikis.sh -- rebuild the generated wiki pages and push them to the wiki.
#
# Every page is built from the source every time, so what is published is never
# a stale file someone forgot to regenerate. A page that has not changed is not
# pushed at all. Each page is attempted even if another fails, and the exit
# status is 0 only if all succeed.
#
#   ./publish-wikis.sh             build all the pages and push them
#   ./publish-wikis.sh --dry-run   show what would be pushed, push nothing
#   ./publish-wikis.sh --check     build nothing; report whether the pages are current
#
# Pushing uses whatever credentials git already has for the Map-Tasker repository.
# Run --dry-run first if you want to see the diff before it is public.
#
# The pages, and where they land:
#   tools/misc/Command-Reference.md        -> <wiki>/Command-Reference
#   tools/misc/generated_output_files.md   -> <wiki>/Generated-Output
#   tools/misc/Runtime-Options.md          -> <wiki>/Runtime-Options
#                                             (every command-line option, read from the program's own parsers)

set -uo pipefail

DRY_RUN=0
CHECK=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --check) CHECK=1 ;;
        -h | --help)
            sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            printf 'publish-wikis.sh: unknown option %s (try --help)\n' "$arg" >&2
            exit 2
            ;;
    esac
done

if [ "$DRY_RUN" -eq 1 ] && [ "$CHECK" -eq 1 ]; then
    printf 'publish-wikis.sh: --dry-run and --check do different jobs; pick one.\n' >&2
    exit 2
fi

cd "$(dirname "$0")" || exit 1

# The Command-Reference and Generated-Output generators are standard library only and
# read the source as text; the Runtime-Options generator imports the program to ask its
# own parsers for the options, so it needs the project's packages as well.  All need the
# Python the project does (3.11 or later), and the python3 on a Mac's PATH can be the
# system's 3.9. Use the project's virtual environment when there is one. Let one
# already chosen win.
if [ -z "${PYTHON:-}" ]; then
    if [ -x .venv/bin/python ]; then
        PYTHON=.venv/bin/python
    else
        PYTHON=python3
    fi
fi
if ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    printf 'publish-wikis.sh: %s is %s; Python 3.11 or later is needed (set PYTHON to one).\n' \
        "$PYTHON" "$("$PYTHON" --version 2>&1)" >&2
    exit 2
fi

# Colour only when writing to a terminal, so piping to a file stays readable.
if [ -t 1 ]; then
    BOLD=$(tput bold) RED=$(tput setaf 1) GREEN=$(tput setaf 2)
    DIM=$(tput dim) RESET=$(tput sgr0)
else
    BOLD="" RED="" GREEN="" DIM="" RESET=""
fi

PUBLISHED=() FAILED=()

# publish_page <wiki page name> <generator> [extra generator arguments...]
publish_page() {
    label=$1
    shift
    printf '%s\n' "${BOLD}── ${label} ${RESET}${DIM}\$ $PYTHON $*${RESET}"
    if "$PYTHON" "$@"; then
        printf '%s\n\n' "  ${GREEN}✔ ${label}${RESET}"
        PUBLISHED+=("$label")
    else
        printf '%s\n\n' "  ${RED}✘ ${label} FAILED${RESET}"
        FAILED+=("$label")
    fi
}

ACTION=(--publish)
[ "$DRY_RUN" -eq 1 ] && ACTION=(--publish --dry-run)

if [ "$CHECK" -eq 1 ]; then
    # --check is the generators' own "is the page on disk current?" gate. Only the
    # newer generators have one; the Command Reference is stamped with the date it was
    # built, so it differs from itself every day and cannot be compared this way.
    publish_page "Generated-Output is current" tools/misc/build_generated_files_doc.py --check
    publish_page "Runtime-Options is current" tools/misc/build_runtime_options_wiki.py --check
else
    publish_page "Command-Reference" tools/misc/build_command_wiki.py "${ACTION[@]}"
    publish_page "Generated-Output" tools/misc/build_generated_files_doc.py "${ACTION[@]}"
    publish_page "Runtime-Options" tools/misc/build_runtime_options_wiki.py "${ACTION[@]}"
fi

printf '%s\n' "${BOLD}── summary${RESET}"
for page in ${PUBLISHED+"${PUBLISHED[@]}"}; do printf '%s\n' "  ${GREEN}✔${RESET} $page"; done
for page in ${FAILED+"${FAILED[@]}"}; do printf '%s\n' "  ${RED}✘${RESET} $page"; done

if [ ${#FAILED[@]} -gt 0 ]; then
    printf '\n%s\n' "${RED}${BOLD}${#FAILED[@]} page(s) failed.${RESET}"
    printf '%s\n' "${DIM}A clone that fails needs push access to the wiki; a wiki with no page yet has to have one made by hand first.${RESET}"
    exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
    printf '\n%s\n' "${GREEN}${BOLD}Dry run complete.${RESET} Nothing was pushed."
elif [ "$CHECK" -eq 1 ]; then
    printf '\n%s\n' "${GREEN}${BOLD}Up to date.${RESET}"
else
    printf '\n%s\n' "${GREEN}${BOLD}All pages are published.${RESET}"
    printf '%s\n' "${DIM}The regenerated pages in tools/misc are part of your working tree -- commit them too.${RESET}"
fi
