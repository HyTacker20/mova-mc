"""Resource pack builder — assemble translated language files into a Minecraft resource pack.

The workspace already has the correct ``assets/<namespace>/lang/`` layout from the
unpack stage. We walk the workspace, collect translated ``{target_lang}.json`` /
``{target_lang}.lang`` files, preserve their directory structure inside the zip,
and add a ``pack.mcmeta`` with auto-detected ``pack_format``.
"""

from __future__ import annotations

import json
import re
import struct
import zipfile
import zlib
from pathlib import Path

from loguru import logger

_PACK_DESCRIPTION = "MovaMC Translation Pack"

# Default pack.png — a simple 64x64 icon generated at runtime.
# Icon design: stylized "M" formed by blocks on a dark background,
# using the MovaMC green accent colour.
_ICON_SIZE = 64

# Blocky "M" shape (1 = filled, 0 = empty) at 8x6 "blocks" on 8x8 px cells
_M_PATTERN: list[list[int]] = [
    [1, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 0, 0, 0, 0, 1, 1],
    [1, 0, 1, 0, 0, 1, 0, 1],
    [1, 0, 0, 1, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 1],
]
_M_CELL = _ICON_SIZE // 8  # 8 px per cell


def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a single PNG chunk."""
    payload = chunk_type + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def _build_default_pack_png() -> bytes:
    """Generate a default pack.png (64x64 RGBA) using only stdlib."""
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width, height, bit depth 8, color type 6 (RGBA)
    ihdr_data = struct.pack(">IIBBBBB", _ICON_SIZE, _ICON_SIZE, 8, 6, 0, 0, 0)
    ihdr = _make_chunk(b"IHDR", ihdr_data)

    # Build pixel rows (filter byte 0 = None, then RGBA)
    # Background: dark navy (#1A1A2E). The "M" pattern is drawn in
    # warm amber/orange matching the web UI primary colour.
    raw_rows: list[bytes] = []
    base_y = (_ICON_SIZE - len(_M_PATTERN) * _M_CELL) // 2  # center vertically
    for y in range(_ICON_SIZE):
        row = bytearray()
        row.append(0)  # filter: none
        for x in range(_ICON_SIZE):
            # Default background
            r, g, b = 0x1A, 0x1A, 0x2E
            a = 0xFF

            # Map pixel to pattern cell
            py = (y - base_y) // _M_CELL
            px = x // _M_CELL
            if 0 <= py < len(_M_PATTERN):
                row_pat = _M_PATTERN[py]
                if 0 <= px < len(row_pat) and row_pat[px] == 1:
                    # Is this pixel a border of the block?
                    cx = x % _M_CELL
                    cy = (y - base_y) % _M_CELL
                    if cx < 2 or cy < 2:
                        # Top/left border: deeper amber
                        r, g, b = 0xC5, 0x60, 0x20
                    elif cx >= _M_CELL - 2 or cy >= _M_CELL - 2:
                        # Bottom/right border: lighter amber
                        r, g, b = 0xF0, 0x90, 0x50
                    else:
                        # Solid block fill: warm amber (#E8782E)
                        r, g, b = 0xE8, 0x78, 0x2E
            row.extend((r, g, b, a))
        raw_rows.append(bytes(row))

    # IDAT: compressed image data
    raw_data = b"".join(raw_rows)
    compressed = zlib.compress(raw_data)
    idat = _make_chunk(b"IDAT", compressed)

    # IEND
    iend = _make_chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


# Pre-built pack.png bytes (lazy-loaded)
_PACK_PNG: bytes | None = None


def get_pack_png() -> bytes:
    """Return the default ``pack.png`` bytes (generated once)."""
    global _PACK_PNG
    if _PACK_PNG is None:
        _PACK_PNG = _build_default_pack_png()
    return _PACK_PNG


# Maps (major, minor) Minecraft version to the *minimum* compatible pack_format.
# Newer patch versions within the same minor may use a higher format, but the
# oldest compatible value ensures the pack loads without rejection.
_VERSION_PACK_FORMAT: dict[tuple[int, int], int] = {
    (1, 6): 1,
    (1, 7): 1,
    (1, 8): 1,
    (1, 9): 2,
    (1, 10): 2,
    (1, 11): 3,
    (1, 12): 3,
    (1, 13): 4,
    (1, 14): 4,
    (1, 15): 5,
    (1, 16): 6,
    (1, 17): 7,
    (1, 18): 8,
    (1, 19): 9,
    (1, 20): 15,
    (1, 21): 34,
}

# If the version isn't in the table, use this. 3 = 1.11-1.12.2, the most
# common target for older modded Minecraft.
_FALLBACK_PACK_FORMAT = 3


def _parse_mc_version(version_str: str) -> tuple[int, int] | None:
    """Parse ``"1.12.2"`` → ``(1, 12)``, or ``None`` on failure."""
    m = re.match(r"(\d+)\.(\d+)", version_str)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def _version_to_pack_format(version: tuple[int, int]) -> int:
    """Look up the pack_format for a (major, minor) version tuple."""
    return _VERSION_PACK_FORMAT.get(version, _FALLBACK_PACK_FORMAT)


def _read_pack_format_from_mcmeta(mcmeta_path: Path) -> int | None:
    """Extract ``pack_format`` from an existing ``pack.mcmeta``, if any."""
    try:
        data = json.loads(mcmeta_path.read_text(encoding="utf-8"))
        pack = data.get("pack")
        if isinstance(pack, dict):
            result = pack.get("pack_format")
            if isinstance(result, int) or result is None:
                return result
        return None
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def _read_version_from_mcmod_info(info_path: Path) -> str | None:
    """Extract ``mcversion`` from a Forge ``mcmod.info`` JSON."""
    try:
        data = json.loads(info_path.read_text(encoding="utf-8"))
        # mcmod.info is either a list-of-dicts or a single dict
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            result = data.get("mcversion")
            if isinstance(result, str) or result is None:
                return result
        return None
    except (json.JSONDecodeError, OSError):
        return None


def _read_version_from_fabric_mod_json(path: Path) -> str | None:
    """Extract Minecraft version from ``fabric.mod.json``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # fabric.mod.json can have "depends" → "minecraft": "~1.19.2"
        depends = data.get("depends", {})
        mc = depends.get("minecraft")
        if isinstance(mc, str):
            return mc.strip().lstrip("~^>=<")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _read_version_from_mods_toml(path: Path) -> str | None:
    """Extract Minecraft version range from ``META-INF/mods.toml``."""
    try:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("versions="):
                # "versions=1.12.2" or "versions=[1.16,)"
                raw = line.split("=", 1)[1].strip().strip('"')
                return raw.split(",")[0].strip().lstrip("[")
    except OSError:
        pass
    return None


def detect_pack_format(workspace: Path) -> int:
    """Auto-detect the appropriate ``pack_format`` from mod metadata in *workspace*.

    Checks (in priority order):
    1. ``mcmod.info`` → parse ``mcversion``
    2. ``fabric.mod.json`` → parse minecraft dependency
    3. ``META-INF/mods.toml`` → parse version range
    4. Fallback: ``3`` (1.11-1.12.2)

    Note: does **not** trust the ``pack_format`` from the mod's own
    ``pack.mcmeta`` — those values are often wrong for the resource
    pack we are building (e.g. a 1.12.2 mod may ship ``pack_format: 1``).
    """
    workspace_files = list(workspace.rglob("*"))

    version_str: str | None = None

    # 1. mcmod.info (Forge 1.6-1.12)
    for f in workspace_files:
        if f.name == "mcmod.info" and f.is_file():
            version_str = _read_version_from_mcmod_info(f)
            if version_str:
                break

    # 2. fabric.mod.json (Fabric)
    if version_str is None:
        for f in workspace_files:
            if f.name == "fabric.mod.json" and f.is_file():
                version_str = _read_version_from_fabric_mod_json(f)
                if version_str:
                    break

    # 3. META-INF/mods.toml (Forge 1.13+)
    if version_str is None:
        for f in workspace_files:
            if f.name == "mods.toml" and f.is_file() and "META-INF" in str(f):
                version_str = _read_version_from_mods_toml(f)
                if version_str:
                    break

    if version_str:
        parsed = _parse_mc_version(version_str)
        if parsed:
            pf = _version_to_pack_format(parsed)
            logger.info(
                "Detected MC version={} → pack_format={} (from {})",
                version_str,
                pf,
                "mod metadata",
            )
            return pf
        logger.debug("Could not parse MC version from string: {}", version_str)

    logger.info(
        "Could not detect MC version from mod metadata — " "using fallback pack_format={}",
        _FALLBACK_PACK_FORMAT,
    )
    return _FALLBACK_PACK_FORMAT


def write_pack_mcmeta(
    zf: zipfile.ZipFile,
    pack_format: int | None = None,
    description: str | None = None,
) -> None:
    """Write ``pack.mcmeta`` into an open zip file.

    If *pack_format* is omitted, it will be ``None`` here; the caller
    should always pass a detected value.
    """
    pf = pack_format if pack_format is not None else _FALLBACK_PACK_FORMAT
    desc = description if description else _PACK_DESCRIPTION
    data = {
        "pack": {
            "pack_format": pf,
            "description": desc,
        }
    }
    zf.writestr("pack.mcmeta", json.dumps(data, indent=2, ensure_ascii=False))


def build_resource_pack(
    workspace: Path,
    output_dir: Path,
    target_lang: str,
    pack_name: str,
    pack_format: int | None = None,
    description: str | None = None,
) -> Path:
    """Walk *workspace* and collect translated files into a resource pack zip.

    Parameters
    ----------
    workspace:
        Temp directory containing per-mod extracted directories with
        ``assets/<ns>/lang/`` trees.
    output_dir:
        Directory where the output ``.zip`` is created.
    target_lang:
        Target language code (e.g. ``"uk_UA"``, ``"es_ES"``).
    pack_name:
        Base name for the zip (without extension) — e.g.
        ``"mova_uk_UA"``.
    pack_format:
        Minecraft pack_format version. When ``None``, auto-detected
        from mod metadata in *workspace*.

    Returns
    -------
    Path
        Absolute path to the created ``.zip`` file.
    """
    if pack_format is None:
        pack_format = detect_pack_format(workspace)

    target_lang_lower = target_lang.lower()
    extensions = {".json", ".lang"}

    output_path = output_dir / f"{pack_name}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)

    collected: list[tuple[str, Path]] = []  # (arcname, file_path)
    for entry in sorted(workspace.rglob("*")):
        if not entry.is_file():
            continue
        stem_lower = entry.stem.lower()
        if stem_lower != target_lang_lower:
            continue
        if entry.suffix.lower() not in extensions:
            continue

        # Strip the per-mod directory prefix so the zip has:
        #   assets/<ns>/lang/<file>
        # instead of:
        #   <modname>/assets/<ns>/lang/<file>
        parts = entry.relative_to(workspace).parts
        arcname = str(Path(*parts[1:])) if len(parts) > 1 else str(Path(*parts))
        collected.append((arcname, entry))

    if not collected:
        logger.warning(
            "No target-language files found in workspace for lang={} — " "resource pack will contain only pack.mcmeta",
            target_lang,
        )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        write_pack_mcmeta(zf, pack_format=pack_format, description=description)
        zf.writestr("pack.png", get_pack_png())
        for arcname, file_path in collected:
            logger.debug("Adding {} → {}", file_path, arcname)
            zf.write(file_path, arcname)

    logger.info(
        "Resource pack written: {} ({} files, pack_format={})",
        output_path,
        len(collected),
        pack_format,
    )
    return output_path
