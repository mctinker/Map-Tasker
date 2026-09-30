#! /usr/bin/env python3
"""maputil3: importing a library that only the AI features need (import_optional).

The AI libraries -- OpenAI, Anthropic, Google, Ollama -- are the optional "ai" extra
(pip install "maptasker[ai]"), so a plain install does not carry them.  MapTasker used to
run pip for whichever one was missing the first time it was wanted.  It no longer does:
installing software behind the user's back is not something a configuration viewer should
do, it cannot work in a frozen app or without a network, and it fetched whatever version
PyPI had that day rather than the one MapTasker was tested with.  Now the caller is handed
None and the user is told, once, what to install.
"""

import importlib

from maptasker.src import console

AI_EXTRA_INSTALL_COMMAND = 'pip install "maptasker[ai]"'

# The packages already reported missing, so a caller that asks again -- a model list rebuilt
# on every visit to the AI dialog, say -- does not repeat the same message.
_reported_missing: set[str] = set()


def import_optional(pypi_name: str, import_path: str) -> object:
    """
    Import a library from the "ai" extra, or say how to get it.

    Nothing is ever installed.  If the library is missing, one message names it and the
    command that installs the extra; later requests for the same library stay quiet.

    Args:
        pypi_name (str): the name the library is installed under (e.g. "google-genai").
        import_path (str): the module to import (e.g. "google.genai").

    Returns:
        object: the imported module, or None if the library is not installed.
    """
    try:
        return importlib.import_module(import_path)
    except ImportError as e:
        # A library that is installed but fails inside its own imports is not "missing"; say
        # what actually went wrong rather than sending the user off to install it again.
        if getattr(e, "name", None) not in {import_path, import_path.split(".", maxsplit=1)[0]}:
            console.error(f"MapTasker: the '{pypi_name}' package could not be loaded: {e}")
            return None
        if pypi_name not in _reported_missing:
            _reported_missing.add(pypi_name)
            console.error(
                f"MapTasker: the '{pypi_name}' package is not installed.  "
                f"Install the AI libraries with: {AI_EXTRA_INSTALL_COMMAND}",
            )
        return None
