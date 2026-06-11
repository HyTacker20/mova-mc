"""Layout-independent key bindings for Textual TUI.

Textual matches bindings on the character the terminal receives, not the
physical key.  On Ukrainian (ЙЦУКЕН) layouts the same key caps produce
Cyrillic characters (e.g. ``ctrl+с`` instead of ``ctrl+c``).
"""

from __future__ import annotations

from textual.binding import Binding, BindingType

# Latin key -> same physical key on standard Ukrainian (ЙЦУКЕН) layout.
_LATIN_TO_UKRAINIAN: dict[str, str] = {
    "q": "й",
    "c": "с",
    "l": "д",
}


def layout_binding(
    key: str,
    action: str,
    description: str = "",
    *,
    show: bool = True,
) -> list[BindingType]:
    """Return a Binding for *key* plus a Ukrainian-layout alias on the same key."""
    bindings: list[BindingType] = [
        Binding(key, action, description, show=show),
    ]
    parts = key.split("+")
    char = parts[-1]
    if len(char) == 1 and char in _LATIN_TO_UKRAINIAN:
        alias_char = _LATIN_TO_UKRAINIAN[char]
        alias_key = "+".join([*parts[:-1], alias_char]) if len(parts) > 1 else alias_char
        if alias_key != key:
            bindings.append(Binding(alias_key, action, description, show=show))
    return bindings
