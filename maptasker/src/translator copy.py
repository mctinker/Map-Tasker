"""Provide language translation capabilities using gettext."""

import gettext
from typing import ClassVar

from maptasker.src.primitem import PrimeItems


class Translator:
    """Provide language translation capabilities using gettext."""

    _ = staticmethod(lambda s: s)  # default: no translation

    # Mapping: human-readable language name → language code
    languages: ClassVar[dict[str, str]] = {
        "English": "en",
        "Spanish": "es",
        "French": "fr",
        "German": "de",
        "Italian": "it",
        # add more as needed
    }

    # Optional: mapping of language codes → translated language names
    # These will be updated whenever a language is set
    languages_translated: ClassVar[dict[str, str]] = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
    }

    @classmethod
    def set_language(cls, lang: str) -> str | None:
        """
        Set the translation language.

        :param lang: Either a language name ('Spanish') or code ('es')
        """
        # Resolve language name to code
        lang_code = PrimeItems.languages.get(lang, lang)

        # Load gettext translation
        translation = gettext.translation(
            "messages",
            localedir=f"maptasker{PrimeItems.slash}locale",
            languages=[lang_code],
            fallback=True,
        )
        PrimeItems._ = staticmethod(translation.gettext)

        # Optionally update translated language names
        for name, code in PrimeItems.languages.items():
            PrimeItems.languages_translated[code] = PrimeItems._(name)


# Shortcut alias
T = Translator
# Example usage:
# T.set_language('es')
# print(T._("Hello, World!"))
