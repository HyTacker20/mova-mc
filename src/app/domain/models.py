from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class TranslationUnit:
    """A single translatable entry extracted from a mod language file.

    Attributes:
        key: The key within the file (JSON key, LANG key, or mcfunction path:line).
        source_text: Original text in the source language.
        file_type: Source file format: json, lang, or mcfunction.
        placeholders: Format specifiers found in source_text (e.g. %s, {0}, §c).
        hint_text: Optional reference translation from a hint-language file.
    """

    key: str
    source_text: str
    file_type: Literal["json", "lang", "mcfunction"]
    placeholders: tuple[str, ...] = ()
    hint_text: str | None = None


@dataclass(frozen=True)
class TranslationResult:
    """The result of translating a single TranslationUnit.

    Attributes:
        unit: The original translation unit.
        translated_text: Translated text (equal to source_text if translation failed).
        success: Whether the translation was successful.
        cached: Whether the result came from cache rather than a provider call.
        error: Error message if translation was unsuccessful.
        qa_warnings: Non-blocking quality-assurance warnings (e.g. suspicious chars).
        qa_score: Quality score from the LLM judge (1..5, None = not judged).
        qa_issue: Category label when the judge flagged the translation.
        qa_attempts: Number of re-translation attempts performed.
    """

    unit: TranslationUnit
    translated_text: str
    success: bool = True
    cached: bool = False
    error: str | None = None
    qa_warnings: tuple[dict, ...] = ()
    qa_score: int | None = None
    qa_issue: str | None = None
    qa_attempts: int = 0


@dataclass(frozen=True)
class LangFile:
    """A language file within a mod, containing translatable entries.

    Attributes:
        mod_name: Name of the mod this file belongs to.
        source_path: Path to the source language file.
        target_path: Path where the translated file should be written.
        file_type: File format: json, lang, or mcfunction.
        units: Translatable entries (TranslationUnit before translation, TranslationResult after).
    """

    mod_name: str
    source_path: Path
    target_path: Path
    file_type: Literal["json", "lang", "mcfunction"]
    units: tuple[TranslationUnit | TranslationResult, ...] = ()


@dataclass(frozen=True)
class Mod:
    """A Minecraft mod archive with its discovered language files.

    Attributes:
        name: The mod name (JAR filename).
        path: Path to the JAR file.
        lang_files: Language files discovered within the mod.
        selected: Whether the user selected this mod for translation.
    """

    name: str
    path: Path
    lang_files: tuple[LangFile, ...] = ()
    selected: bool = True
