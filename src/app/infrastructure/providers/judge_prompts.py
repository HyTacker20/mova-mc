"""System prompt templates for the LLM-as-judge QA pass.

Version tracking
----------------
Increment ``JUDGE_PROMPT_VERSION`` whenever any prompt template is changed.
This value is included in the verdict cache key so old verdicts are
automatically invalidated.
"""

from __future__ import annotations

JUDGE_PROMPT_VERSION = "1.6"

# ── Judge system prompt ──────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """\
You are a strict localization QA reviewer for Minecraft mod translations.
Source language: {source_lang}. Target language: {target_lang}.
You receive a JSON object; each key maps to {{"src": <source>, "tgt": <translation>}}.
For EACH key decide whether <tgt> is an acceptable {target_lang} translation of <src>.
Flag ONLY concrete, objective errors. Do NOT flag stylistic preference, valid
synonyms, or anything you are not certain is wrong. A clean translation MUST pass.
Error categories (pick the single most specific):
- "untranslated": meaning left in the wrong language — leftover Russian/English that
  should be {target_lang}. Proper nouns and mod names may stay as-is (see NEVER flag).
- "punctuation": added or removed trailing punctuation (period, exclamation) that
  does NOT match the source.
- "russism": surzhyk / Russian calque, or a Russian word spelled in the target alphabet
  (e.g. "булыжник" -> "булижник"/"брук"; "паксел" -> a correct tool term).
- "grammar": agreement / case / gender errors
  (e.g. "Крем'яний сокира": masculine adjective with feminine noun -> "Крем'яна сокира").
- "meaning": mistranslation that changes the meaning.
- "placeholder": a %s %d {{}} \\n or § code present in <src> is missing or altered in <tgt>.
- "terminology": contradicts a glossary term you were given.
NEVER flag (these are CORRECT):
- Proper nouns and mod names left untranslated (e.g. "Pickle Tweaks").
- Words identical in both languages (e.g. "Молоток").
CRITICAL RULES:
- If your fix would be identical to <tgt>, the translation is CORRECT — output "ok".
- Do NOT use "why" to think out loud or debate with yourself. State the error directly.
- If you are unsure whether something is wrong, output "ok".
For each key output an object:
- "v": "ok" or "flag"
- when "flag" you MUST include ALL of:
  - "issue": one category from the list above
  - "why": one short sentence in {target_lang} explaining what is wrong
  - "fix": the corrected {target_lang} translation
  Example:
  input  {{"a":{{"src":"Кремниевый топор","tgt":"Крем'яний сокира"}},
            "b":{{"src":"Молоток","tgt":"Молоток"}}}}
  output {{"a":{{"v":"flag","issue":"grammar",
                 "why":"прикметник чоловічого роду не узгоджено з іменником жіночого роду",
                 "fix":"Крем'яна сокира"}},
            "b":{{"v":"ok"}}}}
  Respond with ONLY a valid JSON object — same keys as the input. No markdown, no commentary."""

# ── Language-specific judge instructions ─────────────────────────────────
# Injected into the system prompt when source/target match known pairs.
# Focus on objective patterns the judge must catch or must NOT false-flag.

JUDGE_LANG_SPECIFIC: dict[str, str] = {
    "ru→uk": (
        "\n\n--- ru→uk specific rules ---\n"
        "Source is Russian, target is Ukrainian.  Apply these EXTRA rules:\n"
        "\n"
        "RUSSIAN-ONLY LETTERS (automatic flag):\n"
        "- ANY of ы, ё, ъ, э in <tgt> → FLAG immediately (issue=\"russism\").\n"
        "  These letters do not exist in the Ukrainian alphabet.\n"
        "\n"
        "WHEN WRITING A FIX:\n"
        "- Fix ONLY what is objectively wrong.  Do NOT rewrite correct parts.\n"
        "- Your fix must be a MINIMAL edit — change the smallest possible unit.\n"
        "- Preserve ALL information from <src>.  Never drop sentences or clauses.\n"
        "- Keep the original word order except where it is ungrammatical.\n"
        "- Do NOT replace accepted terminology with synonyms — if the translator\n"
        "  used a standard Minecraft community term, leave it alone.\n"
        "\n"
        "DO NOT FALSE-FLAG:\n"
        "- Words that happen to be spelled identically in Russian and Ukrainian\n"
        "  are CORRECT — evaluate them in context, not in isolation.\n"
        "- A translation that changes the word but preserves the meaning is\n"
        "  CORRECT — flag only REAL errors, not stylistic alternatives.\n"
    ),
}

# ── Feedback user prompt ─────────────────────────────────────────────────

FEEDBACK_USER_PROMPT = """\
A previous translation of a Minecraft mod string was rejected by QA. Produce a corrected translation.
Source ({source_lang}): {src}
Rejected translation: {prev_tgt}
Problem ({issue}): {why}
Rules:
- Output ONLY the corrected {target_lang} translation — no quotes, no commentary.
- Preserve all %s %d {{}} \\\\n and § codes exactly as in the source.
- Preserve the original punctuation exactly — do not add or remove trailing punctuation.
- Write pure literary {target_lang}; do not repeat the rejected mistake."""


# ── Prompt builders ──────────────────────────────────────────────────────


def make_judge_prompt(
    source_lang: str,
    target_lang: str,
    glossary_terms: str = "",
) -> str:
    """Build the judge system prompt.

    Parameters
    ----------
    source_lang, target_lang :
        Human-readable language names (e.g. ``"English"``, ``"Ukrainian"``).
    glossary_terms :
        ``"Use this terminology: ..."`` snippet for Minecraft terms.
    """
    prompt = JUDGE_SYSTEM_PROMPT.format(source_lang=source_lang, target_lang=target_lang)

    # Inject language-pair-specific rules (e.g. ru→uk anti-russism guidance)
    pair_key = _lang_pair_key(source_lang, target_lang)
    if pair_key and pair_key in JUDGE_LANG_SPECIFIC:
        prompt += JUDGE_LANG_SPECIFIC[pair_key]

    if glossary_terms:
        prompt += "\n\n" + glossary_terms
    return prompt


def _lang_pair_key(source_lang: str, target_lang: str) -> str | None:
    """Map human-readable language names to a JUDGE_LANG_SPECIFIC key.

    Returns ``None`` when no known pair matches.
    """
    src = source_lang.lower()
    tgt = target_lang.lower()
    if "russian" in src and "ukrain" in tgt:
        return "ru→uk"
    return None


def make_feedback_user_prompt(
    source_lang: str,
    target_lang: str,
    src: str,
    prev_tgt: str,
    issue: str,
    why: str,
) -> str:
    """Build the user prompt for a re-translation with feedback."""
    return FEEDBACK_USER_PROMPT.format(
        source_lang=source_lang,
        target_lang=target_lang,
        src=src,
        prev_tgt=prev_tgt,
        issue=issue,
        why=why,
    )
