import re

import requests
from packaging.version import InvalidVersion, Version


def check_dependency_updates(dependencies: list) -> None:
    """
    Checks a list of Python dependencies against PyPI for newer versions.

    Args:
        dependencies (list): A list of dependency strings (e.g., "requests>=2.32.3").
    """
    for dep in dependencies:
        match = re.match(r"([a-zA-Z0-9_-]+)([<>=~!]=?)(.+)?", dep)
        if match:
            package_name = match.group(1)
            operator = match.group(2) if match.group(2) else "=="  # Default to exact match if no operator
            current_version_str = match.group(3) if match.group(3) else None

            try:
                response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
                response.raise_for_status()  # Raise an exception for bad status codes
                latest_version_str = response.json()["info"]["version"]
                latest_version = Version(latest_version_str)

                if current_version_str:
                    current_version = Version(current_version_str)
                    if operator in {">=", ">", "<=", "<", "=="}:
                        if latest_version > current_version:
                            print(
                                f"Update available for {package_name}: Current version {current_version_str}, latest version {latest_version_str}",
                            )
                    elif operator == "!=":
                        if latest_version == current_version:
                            print(
                                f"Update available for {package_name}: Current version {current_version_str}, latest version {latest_version_str}",
                            )
                    elif operator == "~=":  # Compatible release
                        base_version = current_version.base_version
                        if not latest_version.startswith(base_version):
                            print(
                                f"Update available for {package_name}: Current version {current_version_str}, latest version {latest_version_str}",
                            )
                else:
                    print(
                        f"Latest version available for {package_name}: {latest_version_str}",
                    )

            except requests.exceptions.RequestException as e:
                print(f"Error checking {package_name}: {e}")
            except (InvalidVersion, KeyError) as e:
                print(f"Error parsing version for {package_name}: {e}")
        else:
            print(f"Invalid dependency format: {dep}")


# Your list of dependencies
# FIX Grab current list of dependencies fromproject.toml
dependencies = [
    "anthropic>=0.60.0",  #  Ai Anthropics support
    # "customtkinter>=5.2.2",  # GUI
    "darkdetect>=0.8.0",  # Appearance mode detection
    "defusedxml>=0.7.1",  # More secure xml parser
    "google-generativeai>=0.8.5",  #  Ai Google Generative support
    "ollama>=0.5.1",  #  Ai Ollama support > cria rquires this
    "openai>=1.98.0",  #  Ai OpenAi support
    "packaging>=25.0",  # Customtkinter needs this
    "pillow==11.3.0",  # Image support in GUI.  Revert back to 11.2.0 to avoid UV bug with tkinter.
    "psutil>=7.0.0",  #  System monitoring
    "requests>=2.32.4",  # HTTP Server function request
    "tomli_w>=1.2.0",  # Write toml file
    "webcolors>=24.11.1",  # For color matching
]

# Call the function to check for updates
check_dependency_updates(dependencies)
