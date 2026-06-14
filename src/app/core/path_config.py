"""Path configuration — extracted from Settings for clean separation of I/O paths.

Separating paths from translation logic makes it obvious which settings
control *where* files go vs *how* they are processed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PathConfig:
    """Filesystem paths and output strategy for the translation pipeline."""

    mods_path: str = "./"
    """Directory containing source mod JARs."""

    translation_path: str = "./translated_mods"
    """Directory where translated JARs are written (``separate`` mode)."""

    output_mode: str = "resourcepack"
    """Output strategy:
    ``"separate"`` writes to ``translation_path``,
    ``"replace"`` overwrites original JARs in ``mods_path`` (DANGEROUS),
    ``"resourcepack"`` builds a Minecraft resource pack .zip in ``translation_path``."""

    # -- derived ---------------------------------------------------------

    @property
    def effective_output_path(self) -> str:
        """Directory where translated JARs should be written."""
        if self.output_mode == "replace":
            return self.mods_path
        # ``separate`` and ``resourcepack`` both use translation_path
        return self.translation_path

    def validate(self) -> None:
        """Raise ``ValueError`` on invalid configuration."""
        if self.output_mode not in ("separate", "replace", "resourcepack"):
            raise ValueError(
                f"output_mode must be 'separate', 'replace', or 'resourcepack', "
                f"got {self.output_mode!r}"
            )
        # Basic sanity — these are user-facing paths, not temp dirs.
        if not self.mods_path:
            raise ValueError("mods_path must not be empty")
        if not self.translation_path:
            raise ValueError("translation_path must not be empty")
