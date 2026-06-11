"""Custom Textual Theme — single amber family (400/500/600 ramp).

$primary == $accent for unified emphasis everywhere (progress bars match
titles/focus).  $boost is lighter (hover tint), $secondary deeper.
$warning is a distinct yellow, visually separate from the brand amber.
Panel is neutral gray instead of blue-slate, harmonizing with the warm accent.

Theme tokens like $text, $text-muted, $border are automatically derived
by Textual from the base colors defined here.
"""

from __future__ import annotations

from textual.theme import Theme

DASHBOARD_THEME = Theme(
    name="dashboard",
    primary="#f59e0b",     # amber-500 — brand emphasis (progress bars, primary buttons)
    secondary="#d97706",   # amber-600 — deeper amber, stays in-family
    accent="#f59e0b",      # == primary: titles/focus match progress-bar fill (no gold-vs-orange)
    background="#0d1117",   # unchanged
    surface="#161b22",      # unchanged
    panel="#21262d",       # was #1c2333 (blue-slate) → neutral gray, harmonizes with warm accent
    error="#ff4444",        # unchanged
    warning="#facc15",     # yellow-400 — brighter/yellower than brand amber → reads as distinct state
    success="#2ea043",      # unchanged
    foreground="#e6edf3",   # unchanged
    boost="#fbbf24",       # amber-400 — lighter highlight for hover tint, distinct from accent
)

# Alias for consumer clarity
AMBER_THEME = DASHBOARD_THEME
