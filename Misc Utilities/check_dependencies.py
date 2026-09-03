#! /usr/bin/env python3
"""Check andf Update Dependencies for the Project."""

import re

import requests
from packaging.version import InvalidVersion, Version


def parse_version_constraint(constraint: str):
    """
    Given a constraint like '>=15.0.16,<16.0.0', return:
      - operator: first operator (like '>=')
      - compare_version: version used for comparison (lowest bound)
      - full_constraint: the full string preserved as-is
    """
    if not constraint:
        return None, None, None

    # Split constraints inside parentheses or after operator
    parts = [p.strip() for p in constraint.split(",")]

    # First constraint used for version comparison
    first = parts[0]

    m = re.match(r"([<>=~!]=?)(.+)", first)
    if not m:
        return None, None, constraint

    operator = m.group(1)
    version = m.group(2).strip()

    return operator, version, constraint


def normalize_for_requirements(dep: str) -> str:
    """
    Convert deps like:
        pytube2 (>=15.0.16,<16.0.0)
    into:
        pytube2>=15.0.16,<16.0.0
    """
    m = re.match(r"([a-zA-Z0-9_-]+)\s*\(?(.+?)?\)?$", dep)
    if not m:
        return dep

    pkg = m.group(1)
    constraint = m.group(2)

    if not constraint:
        return pkg

    return f"{pkg}{constraint}"


def check_dependency_updates(dependencies: list, output_file: str, req_file: str) -> None:
    updated_dependencies = []

    for dep in dependencies:
        match = re.match(r"([a-zA-Z0-9_-]+)\s*\(?(.+?)?\)?$", dep)
        if not match:
            print(f"Invalid dependency format: {dep}")
            updated_dependencies.append(dep)
            continue

        package_name = match.group(1)
        constraint = match.group(2)

        operator, version_for_compare, full_constraint = parse_version_constraint(constraint)

        try:
            response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
            response.raise_for_status()
            latest_version_str = response.json()["info"]["version"]
            latest_version = Version(latest_version_str)

            def needs_update():
                if not version_for_compare:
                    return True

                try:
                    current_version = Version(version_for_compare)
                except InvalidVersion:
                    return False

                if operator in {">", ">=", "<", "<=", "=="}:
                    return latest_version > current_version
                if operator == "!=":
                    return latest_version == current_version
                if operator == "~=":
                    return not latest_version_str.startswith(current_version.base_version)
                return False

            # Build updated dependency
            if needs_update():
                print(
                    f"Update available for {package_name}: "
                    f"Current version {full_constraint}, latest {latest_version_str}",
                )

                if full_constraint and "," in full_constraint:
                    # Multi-range dependency – preserve format
                    new_dep = f"{package_name} ({full_constraint})"
                else:
                    new_dep = f"{package_name}{operator}{latest_version_str}"
            else:
                new_dep = dep

            updated_dependencies.append(new_dep)

        except Exception as e:
            print(f"Error checking {package_name}: {e}")
            updated_dependencies.append(dep)

    #
    # WRITE PYTHON FILE (updated_dependencies.py)
    #
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Auto-generated updated dependency list\n")
        f.write("updated_dependencies = [\n")
        for d in updated_dependencies:
            f.write(f"    {d!r},\n")
        f.write("]\n")

    print(f"\nUpdated dependency list written to: {output_file}")

    #
    # WRITE requirements.txt
    #
    with open(req_file, "w", encoding="utf-8") as f:
        for d in updated_dependencies:
            f.write(normalize_for_requirements(d) + "\n")

    print(f"requirements.txt written to: {req_file}")


# === Your dependency list ===
# Auto-generated updated dependency list
dependencies = [
    "darkdetect>=0.8.0",
    #     "deep_translator>=1.11.4",
    "defusedxml>=0.7.1",
    "nicegui>=3.16.0",
    "packaging>=26.3",
    "pillow==12.3.0",
    "requests>=2.34.2",
    "tomli_w>=1.2.0",
    # Development dependencies
    "ai-translator>=0.1.0",
    "black>=26.5.1",
    "deep-translator>=1.11.4",
    "ollama>=0.6.2",
    "pip-autoremove>=0.10.0",
    "pytest>=9.1.1",
    "pytest-asyncio>=1.4.0",
    "pytest-mock>=3.15.1",
    "vulture>=2.16",
]


# Run & create output files
check_dependency_updates(dependencies, "updated_dependencies.py", "requirements.txt")
