#!/usr/bin/env bash
#
# run-ci.sh -- run the same checks as .github/workflows/ci.yml, locally.
#
# Every gate runs even if an earlier one fails, so one pass shows you
# everything that needs fixing. Exit status is 0 only if all of them pass.
#
#   ./run-ci.sh              run every gate
#   ./run-ci.sh --fix        format and auto-fix lint first, then run every gate
#   ./run-ci.sh --quick      skip the test and build gates (the slow ones)
#
# Keep this in step with .github/workflows/ci.yml when either changes.

set -uo pipefail

FIX=0
QUICK=0
for arg in "$@"; do
    case "$arg" in
        --fix) FIX=1 ;;
        --quick) QUICK=1 ;;
        -h | --help)
            sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            printf 'run-ci.sh: unknown option %s (try --help)\n' "$arg" >&2
            exit 2
            ;;
    esac
done

cd "$(dirname "$0")" || exit 1

# Colour only when writing to a terminal, so piping to a file stays readable.
if [ -t 1 ]; then
    BOLD=$(tput bold) RED=$(tput setaf 1) GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3) DIM=$(tput dim) RESET=$(tput sgr0)
else
    BOLD="" RED="" GREEN="" YELLOW="" DIM="" RESET=""
fi

PASSED=() FAILED=()

# run_gate <label> <command...>
run_gate() {
    label=$1
    shift
    printf '%s\n' "${BOLD}── ${label} ${RESET}${DIM}\$ $*${RESET}"
    start=$SECONDS
    if "$@"; then
        printf '%s\n\n' "  ${GREEN}✔ ${label} passed${RESET} ${DIM}($((SECONDS - start))s)${RESET}"
        PASSED+=("$label")
    else
        printf '%s\n\n' "  ${RED}✘ ${label} FAILED${RESET} ${DIM}($((SECONDS - start))s)${RESET}"
        FAILED+=("$label")
    fi
}

# A local pytest.ini outranks [tool.pytest.ini_options] in pyproject.toml, and
# it is not in the repository -- so CI never sees it. Anything it sets makes
# this run diverge from CI, which defeats the point of running it here.
if [ -f pytest.ini ]; then
    printf '%s\n' "${YELLOW}note:${RESET} pytest.ini is present and takes precedence over pyproject.toml."
    printf '%s\n\n' "      CI has no pytest.ini, so this run does not match it exactly. 'rm pytest.ini' to align."
fi

if [ "$FIX" -eq 1 ]; then
    printf '%s\n' "${BOLD}── applying fixes${RESET}"
    uv run ruff format
    uv run ruff check --fix
    printf '\n'
fi

# Gate 0: the lockfile must already agree with pyproject.toml. CI runs
# 'uv sync --locked', which fails outright on a stale lock -- catch that here
# rather than after a push.
run_gate "uv sync --locked" uv sync --locked --group dev

run_gate "ruff check" uv run --no-sync ruff check

run_gate "ruff format --check" uv run --no-sync ruff format --check

if [ "$QUICK" -eq 1 ]; then
    printf '%s\n\n' "${DIM}skipping test and build gates (--quick)${RESET}"
else
    # The coverage floor lives in [tool.coverage.report] fail_under, so this
    # gate fails on a coverage regression as well as on a failing test.
    run_gate "pytest + coverage" \
        uv run --no-sync pytest --cov=maptasker --cov-report=term-missing:skip-covered

    # Build into a scratch directory so the working tree stays clean.
    DIST=$(mktemp -d)
    trap 'rm -rf "$DIST"' EXIT
    run_gate "build + twine check" \
        bash -c 'uv build --out-dir "$1" >/dev/null && uvx twine check "$1"/*' _ "$DIST"
fi

printf '%s\n' "${BOLD}── summary${RESET}"
for g in ${PASSED+"${PASSED[@]}"}; do printf '%s\n' "  ${GREEN}✔${RESET} $g"; done
for g in ${FAILED+"${FAILED[@]}"}; do printf '%s\n' "  ${RED}✘${RESET} $g"; done

if [ ${#FAILED[@]} -gt 0 ]; then
    printf '\n%s\n' "${RED}${BOLD}${#FAILED[@]} gate(s) failed.${RESET} CI would fail on this commit."
    [ "$FIX" -eq 0 ] && printf '%s\n' "${DIM}Many lint and all format failures are fixable with: ./run-ci.sh --fix${RESET}"
    exit 1
fi

printf '\n%s\n' "${GREEN}${BOLD}All gates passed.${RESET} CI should be green on this commit."
