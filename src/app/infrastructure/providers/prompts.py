"""System prompt templates for LLM-based translation providers.

Version tracking
----------------
Increment ``PROMPT_VERSION`` whenever any prompt template or language-
specific instruction is changed.  This value is included in the cache
key so that old cached translations are automatically invalidated.
"""

from __future__ import annotations

PROMPT_VERSION = "1.2"

# ── Base prompt templates ──────────────────────────────────────────────

TRANSLATION_SYSTEM_PROMPT = """You are a professional translator specializing in Minecraft mod localization.
Translate from {source_lang} to {target_lang}.

Guidelines:
- Preserve formatting like %s, %d, {{}} placeholders and § color codes
- Preserve literal \\\\n (newline) tokens as-is — do not convert them to actual line breaks
- Preserve the original punctuation exactly — do not add or remove trailing periods,
  exclamation marks, or other sentence-ending punctuation
- Use standard Minecraft terminology for blocks, items, entities, biomes,
  enchantments, effects, and game mechanics — keep them consistent
- Technical terms (mob names, block types, item IDs) should remain
  recognisable to players
- Maintain the vanilla Minecraft style: natural but game-appropriate tone
- Use natural, idiomatic expressions

CRITICAL: Respond with ONLY the translated text. No commentary, no analysis,
no quotes, no notes, no explanations — just the translation itself."""

CHUNK_TRANSLATION_SYSTEM_PROMPT = """You are a professional translator specializing in Minecraft mod localization.
Translate from {source_lang} to {target_lang}.

Guidelines:
- Preserve formatting like %s, %d, {{}} placeholders and § color codes
- Preserve literal \\\\n (newline) tokens as-is — do not convert them to actual line breaks
- Preserve the original punctuation exactly — do not add or remove trailing periods,
  exclamation marks, or other sentence-ending punctuation
- Use standard Minecraft terminology for blocks, items, entities, biomes,
  enchantments, effects, and game mechanics — keep them consistent
- Technical terms (mob names, block types, item IDs) should remain
  recognisable to players
- Maintain the vanilla Minecraft style: natural but game-appropriate tone
- Use natural, idiomatic expressions

You will receive a JSON object where each key maps to a source text.
Respond with ONLY a valid JSON object with the same keys mapped to their translations.
Your entire response must be parseable as JSON — no markdown fences, no commentary,
no notes, no explanations. Just raw JSON."""

# ── Language-specific instructions ─────────────────────────────────────
# Stored as structured data so prompts can change without bumping PROMPT_VERSION.

LANG_SPECIFIC_INSTRUCTIONS: dict[str, str] = {
    "uk_UA": (
        "IMPORTANT — Ukrainian language rules:\n"
        "- Write in pure literary Ukrainian. AVOID surzhyk (mixed Ukrainian-Russian).\n"
        "- NEVER use these russisms:\n"
        '  • "получити" → use "отримати"\n'
        '  • "слідуючий" → use "наступний"\n'
        '  • "співпадати" → use "збігатися"\n'
        '  • "на протязі" → use "протягом"\n'
        '  • "приймати участь" → use "брати участь"\n'
        '  • "відключити" → use "вимкнути"\n'
        '  • "у відповідності" → use "відповідно до"\n'  # noqa: RUF001
        '  • "являється" → use "є"\n'
        '  • "приймати міри" → use "вживати заходів"\n'
        "- Use the correct apostrophe (') not a straight apostrophe (') where appropriate.\n"
        '- Use the letter "ґ" (g with upturn) where etymologically correct (e.g., "ґанок", "ґудзик").\n'
        '- Use feminine forms for professions when context-appropriate (e.g., "авторка", "перекладачка").\n'
        "- DO NOT calque Russian sentence structure — Ukrainian has its own syntax.\n"
        "- Terminology consistency for mod items:\n"
        '  • "жезл" or "паличка" (wand) → translate as "жезл", NOT "посох" or "палиця"\n'
        '  • "режим" (mode) → keep as "режим", not "метод" or "спосіб"\n'
        '  • "рідина" (fluid/liquid) → keep as "рідина"\n'
    ),
}

# ── Prompt builders ────────────────────────────────────────────────────


def make_system_prompt(
    source_lang: str,
    target_lang: str,
    lang_specific_instructions: str = "",
    glossary_terms: str = "",
) -> str:
    """Build the single-item system prompt.

    Parameters
    ----------
    source_lang, target_lang :
        Human-readable language names (e.g. ``"English"``, ``"Ukrainian"``).
    lang_specific_instructions :
        Extra instructions for the target language (anti-surzhyk, etc.).
    glossary_terms :
        ``"Use this terminology: …"`` snippet for Minecraft terms.
    """
    prompt = TRANSLATION_SYSTEM_PROMPT.format(source_lang=source_lang, target_lang=target_lang)
    if lang_specific_instructions:
        prompt += "\n\n" + lang_specific_instructions
    if glossary_terms:
        prompt += "\n\n" + glossary_terms
    return prompt


def make_user_prompt(text: str, hint_text: str | None = None) -> str:
    """Build the user message for a single-item translation request."""
    if hint_text and hint_text.strip():
        return (
            "Reference translation (use as style/terminology guide; "
            f"translate the source text into the target language):\n{hint_text}\n\n"
            f"Source text to translate: {text}"
        )
    return f"Translate: {text}"


def make_chunk_system_prompt(
    source_lang: str,
    target_lang: str,
    lang_specific_instructions: str = "",
    glossary_terms: str = "",
) -> str:
    """Build the chunk-batch system prompt (JSON-in, JSON-out).

    Parameters are the same as :func:`make_system_prompt`.
    """
    prompt = CHUNK_TRANSLATION_SYSTEM_PROMPT.format(source_lang=source_lang, target_lang=target_lang)
    if lang_specific_instructions:
        prompt += "\n\n" + lang_specific_instructions
    if glossary_terms:
        prompt += "\n\n" + glossary_terms
    return prompt
