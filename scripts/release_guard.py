"""Refuse to release unless GitHub will stop at the PyPI upload and wait for a person.

The v15.2.0 tag went straight to PyPI: the release workflow's `pypi` job is held by its environment's required
reviewer, and the environment had none.  A PyPI release cannot be taken back, so the workflow asks, before it builds
anything, whether the `pypi` environment really has a required reviewer, and fails loudly when it does not.

    python scripts/release_guard.py [--environment pypi]        reads GITHUB_REPOSITORY and GH_TOKEN

Asking is the awkward part.  GitHub only tells a token with repository Administration (read) permission about an
environment's protection rules, and the workflow's own GITHUB_TOKEN is not given that.  So the workflow passes a
token of the owner's in the ENVIRONMENT_CHECK_TOKEN secret (a fine-grained token, this repository, Administration:
read -- and nothing else), and when there is none, or GitHub does not let it read the environment, this fails too.
A guard that passes because it could not look is no guard; the message says how to give it what it needs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

TIMEOUT_SECONDS = 30


def reviewer_problem(environment: dict[str, Any], name: str) -> str:
    """What is wrong with this environment's protection rules ("" when a person is required to approve a deployment)."""
    for rule in environment.get("protection_rules", []):
        if rule.get("type") == "required_reviewers" and rule.get("reviewers"):
            return ""
    return (
        f"The '{name}' environment has no required reviewer, so a release would publish to PyPI without anyone "
        "approving it -- which is how v15.2.0 went out.  Add one under the repository's Settings > Environments > "
        f"{name} > Required reviewers, and run the release again."
    )


def fetch_environment(repository: str, name: str, token: str) -> tuple[dict[str, Any] | None, str]:
    """The environment as GitHub describes it, or (None, why it could not be read).  Asked through the `gh` CLI."""
    try:
        done = subprocess.run(
            ["gh", "api", f"repos/{repository}/environments/{name}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT_SECONDS,
            env={**os.environ, "GH_TOKEN": token},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"Could not ask GitHub about the '{name}' environment: {error}"
    if done.returncode == 0:
        try:
            return json.loads(done.stdout), ""
        except json.JSONDecodeError:
            return None, f"GitHub's answer about the '{name}' environment could not be read."
    if "404" in done.stderr:
        return None, f"There is no '{name}' environment in {repository}.  Create it, with a required reviewer."
    return None, (
        f"GitHub would not show the '{name}' environment's protection rules ({done.stderr.strip()[:120]}).  The "
        "token needs repository Administration: read; put one in the ENVIRONMENT_CHECK_TOKEN secret."
    )


def main(argv: list[str] | None = None) -> int:
    """Exit 1, with the reason, unless the environment has a required reviewer."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--environment", default="pypi")
    options = parser.parse_args(argv)

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    if not repository or not token:
        print(
            "release guard: no token to ask GitHub with.  Add the ENVIRONMENT_CHECK_TOKEN secret "
            "(fine-grained, this repository, Administration: read); without it the release cannot be checked, "
            "and an unchecked release is not allowed."
        )
        return 1

    environment, why = fetch_environment(repository, options.environment, token)
    if environment is None:
        print(f"release guard: {why}")
        return 1
    if problem := reviewer_problem(environment, options.environment):
        print(f"release guard: {problem}")
        return 1
    print(f"release guard: the '{options.environment}' environment requires a reviewer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
