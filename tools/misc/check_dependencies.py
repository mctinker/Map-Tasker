#! /usr/bin/env python3
"""Check andf Update Dependencies for the Project."""

import re
import tomllib
from pathlib import Path

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


PYPROJECT_FILE = Path(__file__).resolve().parents[2] / "pyproject.toml"

# The only tables of pyproject.toml that declare packages: runtime and the 'ai' extra, and the groups.
DEPENDENCY_TABLES = {"project", "project.optional-dependencies", "dependency-groups"}
_TABLE_HEADER = re.compile(r"^\s*\[\[?([^\[\]]+)\]\]?\s*(?:#.*)?$")
# One dependency on a line of its own: "name[extras]>=1.2", with the quote style, the comma and any
# trailing comment kept as written.
_DEPENDENCY_LINE = re.compile(
    r"""^(?P<indent>\s*)(?P<quote>["'])(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[^\]]*\])?"""
    r"""(?P<spec>.*?)(?P=quote)(?P<tail>\s*,?\s*(?:#.*)?)$""",
)


def update_pyproject(changes: dict[str, str], pyproject_file: Path = PYPROJECT_FILE) -> int:
    """
    Apply version updates to pyproject.toml, in place, where each dependency is declared.

    'changes' maps a dependency as read_dependencies() returned it (extras removed) to its updated
    form.  Only the dependency's own line is touched, so every comment, the quote style, extras like
    'pyright[nodejs]', the ordering and the rest of the file stay as they were.  A package that is
    declared in more than one place (pytest, say) is updated in each.  Returns the lines changed.
    """
    if not changes:
        return 0

    with open(pyproject_file, encoding="utf-8", newline="") as f:
        lines = f.read().splitlines(keepends=True)

    table = ""
    applied: set[str] = set()
    count = 0
    for index, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        ending = raw[len(line) :]

        header = _TABLE_HEADER.match(line)
        if header:
            table = header.group(1).strip()
            continue
        if table not in DEPENDENCY_TABLES:
            continue

        m = _DEPENDENCY_LINE.match(line)
        if not m:
            continue
        old = m["name"] + m["spec"]
        new = changes.get(old)
        if new is None:
            continue

        # new is 'name<op>version'; put back the extras that read_dependencies() removed.
        new_spec = new[len(m["name"]) :]
        if ";" in m["spec"] and ";" not in new_spec:
            # Keep an environment marker such as "; sys_platform == 'win32'".
            new_spec += m["spec"][m["spec"].index(";") :]
        lines[index] = (
            f"{m['indent']}{m['quote']}{m['name']}{m['extras'] or ''}{new_spec}{m['quote']}{m['tail']}{ending}"
        )
        applied.add(old)
        count += 1

    for old in changes.keys() - applied:
        print(f"Not found in {pyproject_file.name}, so not updated there: {old}")

    if count:
        with open(pyproject_file, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines)
    print(f"{pyproject_file.name}: {count} dependency line(s) updated")
    return count


def needs_update(
    operator: str | None, version_for_compare: str | None, latest_version: Version, latest_version_str: str
) -> bool:
    """Return True if the latest release is newer than what the dependency constraint declares."""
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


def check_dependency_updates(dependencies: list, output_file: str, req_file: str) -> None:
    updated_dependencies = []
    changes: dict[str, str] = {}  # dependency as declared -> its new version, for pyproject.toml

    for dep in dependencies:
        match = re.match(r"([a-zA-Z0-9_-]+)\s*\(?(.+?)?\)?$", dep)
        if not match:
            print(f"Invalid dependency format: {dep}")
            updated_dependencies.append(dep)
            continue

        package_name = match.group(1)
        # An environment marker ("; sys_platform == 'win32'") is not part of the version constraint
        # and would make it unparseable, so set it aside and put it back on whatever is written.
        constraint, _, marker = (match.group(2) or "").partition(";")
        constraint = constraint.strip()
        marker_suffix = f"; {marker.strip()}" if marker.strip() else ""

        operator, version_for_compare, full_constraint = parse_version_constraint(constraint)

        try:
            response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
            response.raise_for_status()
            latest_version_str = response.json()["info"]["version"]
            latest_version = Version(latest_version_str)

            # Build updated dependency
            if needs_update(operator, version_for_compare, latest_version, latest_version_str):
                print(
                    f"Update available for {package_name}: "
                    f"Current version {full_constraint}, latest {latest_version_str}",
                )

                if full_constraint and "," in full_constraint:
                    # Multi-range dependency – preserve format
                    new_dep = f"{package_name} ({full_constraint}){marker_suffix}"
                else:
                    new_dep = f"{package_name}{operator}{latest_version_str}{marker_suffix}"
                    changes[dep] = new_dep
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

    #
    # UPDATE pyproject.toml, the one place the dependencies are declared
    #
    update_pyproject(changes)


# === The dependency list ===
# pyproject.toml is the one place dependencies are declared; this reads it rather than keeping
# a copy that goes stale (it once still listed 'black' and lacked 'platformdirs').
def read_dependencies() -> list[str]:
    """Return every dependency in pyproject.toml: runtime, every optional extra, and every dependency group."""
    pyproject = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))
    project = pyproject["project"]
    declared = [
        *project.get("dependencies", []),
        *(d for extra in project.get("optional-dependencies", {}).values() for d in extra),
        # A group also holds {include-group = ...} tables; only the strings are packages.
        *(d for group in pyproject.get("dependency-groups", {}).values() for d in group if isinstance(d, str)),
    ]
    # 'pyright[nodejs]>=1' -> 'pyright>=1': this only compares versions, and extras would
    # confuse the name/constraint split above.
    stripped = {re.sub(r"\[.*?\]", "", d) for d in declared}
    # The project itself ('maptasker[ai]' in the ai-dev group) is not on PyPI to be checked.
    own_name = re.compile(rf"^{re.escape(project['name'])}\b", re.IGNORECASE)
    return sorted(d for d in stripped if not own_name.match(d))


if __name__ == "__main__":
    # Run & create output files, and apply the updates to pyproject.toml
    check_dependency_updates(read_dependencies(), "updated_dependencies.py", "requirements.txt")
