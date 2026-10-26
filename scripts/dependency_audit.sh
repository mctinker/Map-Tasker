#!/usr/bin/env bash
#
# dependency_audit.sh -- check the exact versions in uv.lock against the known-vulnerability databases.
#
# The lock file is what CI tests and what a locked install gets, so it is the lock that is audited:
# every package MapTasker needs to run (the runtime dependencies and the optional "ai" extra), at the
# version pinned, and none of the development tools.  MapTasker holds an Android authorization key and
# the user's AI API keys, which is why an out-of-date HTTP stack is worth failing a build over.
#
# Needs a network (pip-audit asks PyPI's advisory service), so it is not part of the offline gates.
# On a failure, update the package named and commit the lock file:
#
#   uv lock --upgrade-package <name>
#
# Run by .github/workflows/audit.yml and by run-ci.sh.

set -euo pipefail

cd "$(dirname "$0")/.."

requirements=$(mktemp)
trap 'rm -f "$requirements"' EXIT

# Hashes stay in: pip-audit then checks the pinned files themselves and does not resolve anything.
uv export --locked --no-dev --all-extras --no-emit-project --format requirements-txt --output-file "$requirements" \
    >/dev/null
uvx pip-audit --requirement "$requirements" --disable-pip --progress-spinner off
