# MovaMC Roadmap

> Last updated: 2026-06-11

## What MovaMC does today

- **Translate entire modpacks** — drop a folder of JARs, get translated versions back
- **7 AI providers** — Google Translate (free), OpenAI, Anthropic, Gemini, Ollama (local), and any OpenAI-compatible API
- **Smart caching** — already-translated strings are never re-sent to the API; repeat runs are instant and free
- **Quality control** — built-in LLM judge scores every translation 1–5 and re-translates bad ones automatically
- **Ukrainian-first quality** — custom glossary (62 Minecraft terms), anti-surzhyk prompt, russism detector
- **Three file formats** — JSON with comments, Minecraft LANG (`key=value`), MCFUNCTION (`data modify storage`)
- **Placeholder safety** — `%s`, `%d`, `%1$s`, `§c`, `{name}` are validated so nothing breaks in-game
- **Both GUI and CLI** — interactive Textual TUI (`mova app`) or scriptable CLI (`mova cli`)

## What's coming next

### Now — better UX
- **Human-readable errors** — instead of "API key required", the app tells you where to get one and what it costs
- **Pre-flight cost estimate** — see the estimated LLM cost before you click Translate
- **Rescan & Retry** — rescan for mods without restarting the wizard; retry only the failed translations
- **Find your logs** — every error message shows the exact path to the log file

### Next — resource packs & reliability
- **Resource pack output** — translations packaged as standard Minecraft resource packs (survive mod updates, shareable on CurseForge/Modrinth)
- **Crash recovery** — pipeline saves progress after each mod; restart picks up where it left off
- **Web interface** — browser-based UI with side-by-side translation editor (replaces the terminal TUI)

### Later — smarter translation
- **Auto-detect source language** — no need to specify the mod's language manually
- **Whole-modpack context** — feed the LLM related strings from the same mod for more consistent translations
- **Web service** — upload a modpack, get a resource pack back (no install needed)

### Distribution
- **GitHub Releases** — pre-built `.exe` for Windows, `.whl` for Python users
- **Modrinth & Nexus pages** — reach Minecraft players where they already are
- **Community translation hub** — library of ready-to-use resource packs

## Future ideas

- `watch-mode` — re-translate automatically when mods update
- `crowdsource-fixes` — let the community upvote/downvote translations
- `launcher-integration` — one-click translate from Prism Launcher / Modrinth App
- `zip-modpack-support` — accept CurseForge/Modrinth export `.zip` files directly
- `multi-language-glossaries` — curated Minecraft term lists for Polish, Czech, Turkish
- `github-action-for-modders` — "translate my mod" as a GitHub Action for mod developers

---

## For contributors

- **AGENTS.md** — technical architecture reference for AI agents and developers
- **openspec/** — each planned feature has a spec-driven change folder with proposal, design, and tasks
- **CHANGELOG.md** — per-release change history (planned)
- **CONTRIBUTING.md** — how to contribute (planned)
