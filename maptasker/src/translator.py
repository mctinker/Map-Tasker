"""Provide language translation capabilities using gettext."""

import gettext

from maptasker.src.primitem import PrimeItems  # your global shared class


class Translator:
    """Provide language translation capabilities using gettext and PrimeItems as global state."""

    @classmethod
    def set_language(cls, lang: str) -> None:
        """
        Set the translation language.

        Args:
            lang: Either a human-readable language name ('Spanish') or language code ('es').
        """
        # Resolve language code using PrimeItems.languages
        lang_code = PrimeItems.languages.get(lang, lang)

        # Load gettext translation
        translation = gettext.translation(
            "messages",
            localedir=f"maptasker{PrimeItems.slash}locale",
            languages=[lang_code],
            fallback=True,
        )

        # Store translation function in PrimeItems
        PrimeItems._ = staticmethod(translation.gettext)

        # Update translated language names globally
        for name, code in PrimeItems.languages.items():
            PrimeItems.languages_translated[code] = PrimeItems._(name)


# Shortcut alias
T = Translator
# Example usage:
# T.set_language('es')
# print(PrimeItems._("Hello, World!"))
