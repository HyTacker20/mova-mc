# Translation glossary

Optional, per-language terminology files that pin specific Minecraft terms to a
preferred translation. When a glossary entry's **English key** appears in a
source string, the pair is injected into the LLM system prompt as
`Use this terminology: <en>→<translation>.` so the model stays consistent.

Glossaries are **opt-in and manual** — they ship empty. Add an entry only for a
term the model actually gets wrong (which should be the exception, not the rule).

## How it works

- File name is `<lang_code>.json` (e.g. `uk_UA.json`), matching the **target**
  language code. Key matching is case-insensitive substring on the English key.
- Only LLM providers use the glossary; Google Translate ignores it.
- Adding/removing terms changes the cache signature, so affected strings are
  re-translated on the next run instead of returning a stale cached value.

## Format

A flat JSON object mapping `English term → translation`:

```json
{
  "Redstone": "Редстоун",
  "The End": "Край",
  "Creeper": "Кріпер"
}
```

## Adding terms

1. Open the file for your target language (e.g. `uk_UA.json`).
2. Add `"English": "Переклад"` pairs. Keep the English key exactly as it appears
   in the source text.
3. Save — the next translation run picks the terms up automatically.

You can also keep a glossary outside the repository and point to it with:

```bash
mova cli ... --glossary-path /path/to/glossary.json
```

User entries override the built-in file for the same English key.
