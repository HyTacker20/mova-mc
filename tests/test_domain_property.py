"""Property-based tests for the domain layer using Hypothesis.

Tests invariants that hold for *all* inputs: placeholder extraction,
language registry consistency, and stats arithmetic.
"""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from app.domain.languages import (
    LANGUAGE_NAMES,
    get_language_english_name,
    is_valid_language,
)
from app.domain.placeholders import (
    _count_placeholders,
    extract_placeholders,
    validate_placeholders,
)
from app.domain.stats import FileStats, ModStats, OverallStats

# ── Placeholder strategies ──────────────────────────────────────────

_percent_fmt = st.sampled_from(["s", "d", "f", "i", "x", "X", "e", "E", "g", "G", "c"])
_width = st.integers(min_value=0, max_value=20).map(lambda x: str(x) if x else "")
_precision = st.integers(min_value=0, max_value=10).map(lambda x: f".{x}" if x else "")
_flag = st.sampled_from(["", "#", "0", "-", " ", "+"])
_index = st.integers(min_value=1, max_value=9).map(lambda x: f"{x}$")

percent_placeholder = st.builds(
    lambda idx, flag, w, prec, fmt: f"%{idx}{flag}{w}{prec}{fmt}",
    idx=st.just("") | _index,
    flag=_flag,
    w=_width,
    prec=_precision,
    fmt=_percent_fmt,
)

minecraft_color = st.sampled_from(
    [f"§{c}" for c in "0123456789abcdefklmnoqr"]
)

brace_placeholder = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=12,
).map(lambda s: f"{{{s}}}")

double_brace_placeholder = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=12,
).map(lambda s: f"{{{{{s}}}}}")

any_placeholder = percent_placeholder | minecraft_color | brace_placeholder | double_brace_placeholder


# ── Tests: extract_placeholders ─────────────────────────────────────


@given(st.lists(any_placeholder, min_size=0, max_size=10))
def test_extract_placeholders_deduplicated(placeholders: list[str]) -> None:
    """extract_placeholders always returns a deduplicated tuple."""
    text = " ".join(placeholders)
    result = extract_placeholders(text)
    assert isinstance(result, tuple)
    # No duplicates in result
    assert len(set(result)) == len(result)
    # Every token in result appears in input
    for ph in result:
        assert ph in text, f"{ph!r} not found in {text!r}"


@given(st.text(max_size=100))
def test_extract_placeholders_no_side_effects(text: str) -> None:
    """extract_placeholders is a pure function (no mutation, same result twice)."""
    assert extract_placeholders(text) == extract_placeholders(text)


@given(st.text(max_size=100))
def test_count_placeholders_matches_extract(text: str) -> None:
    """_count_placeholders keys match extract_placeholders output exactly."""
    extracted = extract_placeholders(text)
    counted = _count_placeholders(text)
    assert set(extracted) == set(counted.keys())
    # Every count is positive
    assert all(v >= 1 for v in counted.values())


@given(st.text(max_size=200))
def test_validate_placeholders_is_reflexive(text: str) -> None:
    """validate_placeholders(t, t) is always True (every string validates itself)."""
    assert validate_placeholders(text, text) is True


@given(any_placeholder, st.text(alphabet="abc ", min_size=0, max_size=10))
def test_validate_placeholder_preserved(ph: str, padding: str) -> None:
    """validate_placeholders returns True when the placeholder is preserved."""
    original = f"Hello {ph} world"
    translated = f"{padding}{ph}{padding}"
    assert validate_placeholders(original, translated), f"Failed: {original!r} -> {translated!r}"


@given(st.lists(any_placeholder, min_size=1, max_size=5))
def test_validate_fails_when_placeholder_dropped(placeholders: list[str]) -> None:
    """validate_placeholders returns False when a placeholder is missing."""
    assume(len(placeholders) >= 2)
    text = " ".join(placeholders)
    dropped = placeholders[:-1]  # drop last placeholder
    without = " ".join(dropped)
    assert not validate_placeholders(text, without), (
        f"Should fail: {text!r} -> {without!r}"
    )


# ── Tests: languages ────────────────────────────────────────────────


def test_all_language_codes_are_valid() -> None:
    """Every key in LANGUAGE_NAMES passes is_valid_language."""
    for code in LANGUAGE_NAMES:
        assert is_valid_language(code), f"{code} should be valid"


def test_english_name_never_contains_trailing_code() -> None:
    """get_language_english_name strips the trailing (code) suffix."""
    for code in LANGUAGE_NAMES:
        name = get_language_english_name(code)
        assert not name.endswith(f"({code})"), f"{code} -> {name!r} still has code suffix"
        assert name, f"English name for {code} is empty"


@given(st.sampled_from(sorted(LANGUAGE_NAMES.keys())))
def test_is_valid_language_roundtrip(code: str) -> None:
    """Known language codes are valid; unknown codes (random strings) are not."""
    assert is_valid_language(code)
    name = LANGUAGE_NAMES[code]
    assert code in name or get_language_english_name(code)


@given(st.text(min_size=1, max_size=10))
def test_is_valid_language_rejects_garbage(code: str) -> None:
    """Random strings are never valid language codes."""
    assume(code not in LANGUAGE_NAMES)
    assert not is_valid_language(code)


# ── Tests: stats invariants ────────────────────────────────────────

_uint = st.integers(min_value=0, max_value=1_000_000)


@given(
    entries_total=_uint,
    entries_translated=_uint,
    entries_failed=_uint,
)
def test_file_stats_invariants(
    entries_total: int,
    entries_translated: int,
    entries_failed: int,
) -> None:
    """FileStats invariants hold regardless of input."""
    assume(entries_translated + entries_failed <= entries_total)
    fs = FileStats(path="test.json", file_type="json")
    fs.start()
    fs.entries_total = entries_total
    fs.add_translated(entries_translated)
    fs.add_failed(entries_failed)
    fs.finish()

    assert fs.duration_ms >= 0
    assert fs.entries_total >= fs.entries_translated + fs.entries_failed


@given(
    st.lists(
        st.builds(
            lambda t, tr, fa: FileStats(
                path=f"{t}.json", file_type="json",
                entries_total=t, entries_translated=tr, entries_failed=fa,
            ),
            t=_uint, tr=_uint, fa=_uint,
        ).filter(lambda fs: fs.entries_translated + fs.entries_failed <= fs.entries_total),
        min_size=0,
        max_size=5,
    ),
)
def test_mod_stats_aggregation(files: list[FileStats]) -> None:
    """ModStats.finish() aggregates file stats correctly."""
    ms = ModStats(name="test.jar")
    ms.start()
    ms.files = files
    ms.finish()

    expected_total = sum(f.entries_total for f in files)
    expected_translated = sum(f.entries_translated for f in files)
    expected_failed = sum(f.entries_failed for f in files)

    assert ms.total_entries == expected_total
    assert ms.translated_entries == expected_translated
    assert ms.failed_entries == expected_failed


@given(
    st.lists(
        st.builds(
            lambda name, skipped, t, tr, fa: ModStats(
                name=name, skipped=skipped,
                total_entries=t, translated_entries=tr, failed_entries=fa,
            ),
            name=st.text(min_size=1, max_size=20),
            skipped=st.booleans(),
            t=_uint, tr=_uint, fa=_uint,
        ).filter(lambda ms: ms.translated_entries + ms.failed_entries <= ms.total_entries),
        min_size=0,
        max_size=5,
    ),
)
def test_overall_stats_aggregation(mods: list[ModStats]) -> None:
    """OverallStats.finish() aggregates mod stats correctly."""
    os = OverallStats()
    os.start()
    os.mods = mods
    os.finish()

    assert os.total_mods == len(mods)
    assert os.translated_mods == sum(1 for m in mods if not m.skipped)
    assert os.skipped_mods == sum(1 for m in mods if m.skipped)

    expected_total = sum(m.total_entries for m in mods)
    expected_translated = sum(m.translated_entries for m in mods)
    expected_failed = sum(m.failed_entries for m in mods)

    assert os.total_entries == expected_total
    assert os.translated_entries == expected_translated
    assert os.failed_entries == expected_failed


@given(
    st.builds(
        lambda t, tr, fa: FileStats(
            path="test.json", file_type="json",
            entries_total=t, entries_translated=tr, entries_failed=fa,
        ),
        t=_uint, tr=_uint, fa=_uint,
    ).filter(lambda fs: fs.entries_translated + fs.entries_failed > fs.entries_total),
)
def test_file_stats_can_overflow(fs: FileStats) -> None:
    """FileStats does not enforce the invariant internally (data integrity)."""
    # This is a documentation check: the stats classes are passive data
    # containers, not validators. The pipeline must ensure the invariant
    # total >= translated + failed holds before constructing stats.
    assert fs.entries_total < fs.entries_translated + fs.entries_failed
