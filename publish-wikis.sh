#!/usr/bin/env bash
#
# publish-wikis.sh -- rebuild the generated wiki pages and push them to the wiki.
#
# Both pages are built from the source every time, so what is published is never
# a stale file someone forgot to regenerate. A page that has not changed is not
# pushed at all. Each page is attempted even if the other fails, and the exit
# status is 0 only if both succeed.
#
#   ./publish-wikis.sh             build both pages and push them
#   ./publish-wikis.sh --dry-run   show what would be pushed, push nothing
#   ./publish-wikis.sh --check     build nothing; report whether the pages are current
#
# Pushing uses whatever credentials git already has for the Map-Tasker repository.
# Run --dry-run first if you want to see the diff before it is public.
#
# The pages, and where they land:
#   tools/misc/Command-Reference.md        -> <wiki>/Command-Reference
#   tools/misc/generated_output_files.md   -> <wiki>/Generated-Output

set -uo pipefail

DRY_RUN=0
CHECK=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --check) CHECK=1 ;;
        -h | --help)
            sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
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

# Both generators are standard library only and read the version out of
# pyproject.toml, so no virtual environment is needed. Let one already chosen win.
PYTHON="${PYTHON:-python3}"

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
    # newer generator has one; the Command Reference is stamped with the date it was
    # built, so it differs from itself every day and cannot be compared this way.
    publish_page "Generated-Output is current" tools/misc/build_generated_files_doc.py --check
else
    publish_page "Command-Reference" tools/misc/build_command_wiki.py "${ACTION[@]}"
    publish_page "Generated-Output" tools/misc/build_generated_files_doc.py "${ACTION[@]}"
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
    printf '\n%s\n' "${GREEN}${BOLD}Both pages are published.${RESET}"
    printf '%s\n' "${DIM}The regenerated pages in tools/misc are part of your working tree -- commit them too.${RESET}"
fi
