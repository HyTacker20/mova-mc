# Design

> Campfire — warm ember on deep charcoal. Dark, cozy, Minecraft-native.

## Theme

**Dark mode only.** The tool is used in the evening, in dim rooms, with the monitor as the primary light source. A light theme would be harsh and out of place.

**Physical scene:** A player in their room at night, desk lamp off, monitor glow the only light. They want to translate a modpack and get back to playing — the tool should feel like a warm corner of their screen, not a fluorescent office.

**Color strategy:** Restrained. Deep charcoal background, one warm amber-ember accent at ≤10% of surface area. Neutral grays for structure. Color is saved for focus states, primary actions, and progress — never decoration.

## Color Palette

All values in OKLCH. Accent hue anchored to seed 29° (ember-red), shifted to amber for readability.

| Token | OKLCH | Role |
|---|---|---|
| `--bg` | `oklch(0.08 0 0)` | Page background — deep charcoal, pure black |
| `--surface` | `oklch(0.12 0 0)` | Cards, panels, elevated containers |
| `--surface2` | `oklch(0.16 0 0)` | Input backgrounds, hover states |
| `--border` | `oklch(0.22 0 0)` | Subtle borders, dividers |
| `--border-focus` | `oklch(0.62 0.16 35)` | Focus ring — matches primary |
| `--primary` | `oklch(0.62 0.16 35)` | Primary actions, focus, progress fill — warm amber-ember |
| `--primary-dim` | `oklch(0.48 0.13 33)` | Primary hover/active — deeper ember |
| `--accent` | `oklch(0.58 0.14 75)` | Secondary brand color — warm gold, distinct from primary |
| `--text` | `oklch(0.93 0 0)` | Body text — near-white, ≥7:1 vs bg |
| `--text-muted` | `oklch(0.68 0 0)` | Secondary text, labels, hints — ≥4.5:1 vs bg |
| `--success` | `oklch(0.62 0.16 150)` | Success states — green, functional only |
| `--warning` | `oklch(0.70 0.16 80)` | Warning states — warm yellow |
| `--error` | `oklch(0.52 0.19 25)` | Error states — warm red |

### Contrast

| Pair | Ratio | Pass |
|---|---|---|
| text / bg | ~10:1 | AAA |
| muted / bg | ~5:1 | AA |
| primary / bg | ~5.5:1 | AA (large text) |
| text / primary | ~5.5:1 | AA — white text on amber buttons |

### Text on fills

- **Primary buttons** (amber fill): white text (`--text`). The Helmholtz-Kohlrausch effect makes saturated warm colors appear brighter; dark text on amber reads as muddy.
- **Error badges**: white text.
- **Success badges**: white text.
- **Warning badges**: dark text (`--bg`) — yellow fills are light enough.

## Typography

**Primary:** System sans-serif stack (`Segoe UI`, `system-ui`, sans-serif). Clean, zero-load, familiar.

**Direction for exploration:** A warm, approachable typeface with subtle character — not pixel-art, not cold geometric. Candidates:
- **Fraunces** — soft, crafted serif for headings. Warm and hand-made feel.
- **DM Sans** — geometric sans with gentle warmth.
- **Plus Jakarta Sans** — rounded, friendly, modern.

**Scale:** Fixed rem scale with tight ratio (1.125–1.2). Product UI, not marketing — consistent sizes, not fluid clamp headings.

**Rules:**
- Body line length: 65–75ch for prose
- One family for all UI (headings, buttons, labels, body, data)
- No display/body pairing needed
- `text-wrap: balance` on step titles (h1–h3 equivalent)

## Components

Every interactive element must ship with complete states: default, hover, focus, active, disabled, loading, error.

### Buttons
- **Primary:** filled amber (`--primary`), white text, bold. Hover: deeper ember (`--primary-dim`). Focus: gold ring (`--border-focus`).
- **Ghost:** transparent, muted text, subtle border. Hover: border brightens, text lightens.
- **Danger:** filled red (`--error`), white text.

### Inputs & Selects
- Background: `--surface2`, border: `--border`
- Focus: amber border (`--border-focus`)
- Placeholder: muted text at ≥4.5:1 contrast (same as body muted, not lighter)

### Progress
- Track: `--surface2`
- Fill: `--primary` (amber), smooth 250ms ease transition
- Entry-level progress: `--success` (green)

### Cards (StepCard)
- Background: `--surface`, border: `--border`, radius: 10px
- Max-width: 640px (860px for wide steps like translate run)
- Centered in viewport

### Mod list rows
- Grid layout: checkbox + name + meta + size
- Hover: `--surface2` background, 120ms transition
- No-language rows: 55% opacity

### Data tables
- Header: uppercase, tracked, muted, `--surface2` background
- Odd rows: `--surface` background
- Border-bottom separators

### Scrollbar
- Track: `--surface`
- Thumb: `--border`, hover: `--border-focus`

## Layout

- **Wizard shell:** Full-height flex column (header → body → none). No footer in web UI (actions inline in step card).
- **Header:** `--surface` background, bottom border, logo + stepper
- **Stepper:** Horizontal dots with connecting lines. Done = green, active = amber primary, pending = muted.
- **Body:** Centered card, flexbox for vertical stacking, Grid for 2D when needed.
- **Spacing:** 14px field gaps, 28px before actions row. No top margins — bottom-only rhythm.
- **Responsive:** Structural breakpoints, not fluid typography. Summary grid: 4-col → 2-col at 640px.

## Motion

- **Duration:** 150–250ms on state transitions. Users are in flow.
- **Purpose:** State change, feedback, loading — never decoration.
- **No page-load sequences.** The tool loads into a task.
- **Easing:** ease-out (cubic-bezier(0.16, 1, 0.3, 1)) for exits, ease-out-quart for entrances.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` → instant transitions or opacity crossfade.

## Icons

No icon library defined yet. Use Unicode or inline SVG for status indicators. Avoid emoji as primary UI elements (emoji as decoration is fine, but not as the only affordance).

## Anti-patterns (do not use)

- Gradient text, side-stripe borders, glassmorphism
- Hero-metric template (big number + small label grids)
- Identical card grids with icon + heading + text
- Tiny uppercase tracked eyebrow above every section
- Numbered section markers (01 / 02 / 03) as scaffolding
- Decorative motion, display fonts in UI labels
- Modal as first resort — exhaust inline/progressive alternatives first
- Inconsistent button shapes across screens
