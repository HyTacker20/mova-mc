"""Tests for judge engine."""

from __future__ import annotations

import json

from app.infrastructure.providers.judge import LlmJudge, Verdict, parse_judge_response, verdict_from_entry

# ── parse_judge_response ────────────────────────────────────────────────


class TestParseJudgeResponse:
    def test_valid_nested_json(self) -> None:
        raw = '{"a": {"v": "ok"}, "b": {"v": "flag", "score": 1, "issue": "grammar", "why": "test", "fix": "fix"}}'
        result = parse_judge_response(raw)
        assert result is not None
        assert result["a"] == {"v": "ok"}
        assert result["b"] == {"v": "flag", "score": 1, "issue": "grammar", "why": "test", "fix": "fix"}

    def test_fenced_json(self) -> None:
        raw = '```json\n{"a": {"v": "ok"}}\n```'
        result = parse_judge_response(raw)
        assert result is not None
        assert result["a"] == {"v": "ok"}

    def test_trailing_comma(self) -> None:
        raw = '{"a": {"v": "ok"},}'
        result = parse_judge_response(raw)
        assert result is not None
        assert result["a"] == {"v": "ok"}

    def test_garbage_returns_none(self) -> None:
        assert parse_judge_response("not json at all") is None
        assert parse_judge_response("") is None
        assert parse_judge_response("{}") == {}  # valid empty dict

    def test_partial_keys(self) -> None:
        """If JSON is valid, all keys returned; if invalid, None."""
        raw = '{"a": {"v": "ok"}, "b": {"v": "flag"}}'
        result = parse_judge_response(raw)
        assert result is not None
        assert "a" in result
        assert "b" in result


# ── Verdict ──────────────────────────────────────────────────────────────


class TestVerdictFromEntry:
    def test_fix_equals_tgt_is_ok(self) -> None:
        entry = {
            "v": "flag",
            "issue": "grammar",
            "why": "wrong",
            "fix": "трансформована",
        }
        assert verdict_from_entry(entry, "трансформована").verdict == "ok"

    def test_fix_differs_stays_flag(self) -> None:
        entry = {
            "v": "flag",
            "issue": "grammar",
            "why": "рід",
            "fix": "Крем'яна сокира",
        }
        v = verdict_from_entry(entry, "Крем'яний сокира")
        assert v.is_flag
        assert v.fix == "Крем'яна сокира"


class TestVerdict:
    def test_ok_verdict(self) -> None:
        v = Verdict(verdict="ok")
        assert v.verdict == "ok"
        assert v.score is None
        assert v.issue is None

    def test_flag_verdict(self) -> None:
        v = Verdict(verdict="flag", score=2, issue="grammar", why="рід не узгоджено", fix="Крем'яна сокира")
        assert v.verdict == "flag"
        assert v.score == 2
        assert v.issue == "grammar"

    def test_is_flag_property(self) -> None:
        assert Verdict(verdict="flag").is_flag
        assert not Verdict(verdict="ok").is_flag


# ── LlmJudge ─────────────────────────────────────────────────────────────


class _FakeTransport:
    """Canned response transport for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses: list[str] = responses or []
        self.call_count = 0
        self.last_messages: list[dict[str, str]] | None = None
        self.last_temperature: float | None = None
        self.last_max_tokens: int | None = None

    def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        self.call_count += 1
        self.last_messages = messages
        self.last_temperature = temperature
        self.last_max_tokens = max_tokens
        if self.responses:
            return self.responses.pop(0)
        # Default: all ok
        return json.dumps({})


class _RaisingTransport:
    """Transport that always raises."""

    def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        raise RuntimeError("Transport failure")


class TestLlmJudge:
    def test_judge_batch_maps_verdicts(self) -> None:
        """Correct Verdict mapping from canned JSON response."""
        transport = _FakeTransport([
            json.dumps({
                "key1": {"v": "ok"},
                "key2": {"v": "flag", "score": 2, "issue": "grammar", "why": "рід не узгоджено", "fix": "Крем'яна"},
            })
        ])
        judge = LlmJudge(transport=transport, source_display="English", target_display="Ukrainian")
        items = [("key1", "Stone pickaxe", "Кам'яний кирка"), ("key2", "Stone axe", "Крем'яний сокира")]
        results = judge.judge_batch(items)
        assert len(results) == 2
        assert results["key1"] == Verdict("ok")
        assert results["key2"] == Verdict("flag", 2, "grammar", "рід не узгоджено", "Крем'яна")

    def test_judge_batch_chunking(self) -> None:
        """Multiple chunks when item count exceeds chunk_size."""
        transport = _FakeTransport([
            json.dumps({"k1": {"v": "ok"}, "k2": {"v": "ok"}}),
            json.dumps({"k3": {"v": "ok"}}),
        ])
        judge = LlmJudge(transport=transport, source_display="English", target_display="Ukrainian", chunk_size=2)
        items = [("k1", "a", "b"), ("k2", "c", "d"), ("k3", "e", "f")]
        results = judge.judge_batch(items)
        assert len(results) == 3
        assert transport.call_count == 2

    def test_fail_open_on_transport_error(self) -> None:
        """Transport error → all items default to ok."""
        transport = _RaisingTransport()
        judge = LlmJudge(transport=transport, source_display="English", target_display="Ukrainian")
        items = [("key1", "a", "b"), ("key2", "c", "d")]
        results = judge.judge_batch(items)
        assert len(results) == 2
        assert results["key1"] == Verdict("ok")
        assert results["key2"] == Verdict("ok")

    def test_fail_open_on_unparseable_response(self) -> None:
        """Garbage response → chunk defaults to ok."""
        transport = _FakeTransport(["garbage response"])
        judge = LlmJudge(transport=transport, source_display="English", target_display="Ukrainian")
        items = [("key1", "a", "b")]
        results = judge.judge_batch(items)
        assert len(results) == 1
        assert results["key1"] == Verdict("ok")

    def test_temperature_is_zero(self) -> None:
        """Judge always uses temperature=0.0 for deterministic classification."""
        transport = _FakeTransport([json.dumps({"k": {"v": "ok"}})])
        judge = LlmJudge(transport=transport, source_display="English", target_display="Ukrainian")
        judge.judge_batch([("k", "a", "b")])
        assert transport.last_temperature == 0.0

    def test_max_tokens(self) -> None:
        transport = _FakeTransport([json.dumps({"k": {"v": "ok"}})])
        judge = LlmJudge(transport=transport, source_display="English", target_display="Ukrainian", max_tokens=4096)
        judge.judge_batch([("k", "a", "b")])
        # Single-item chunk: max(256, min(4096, 72 * 1)) == 256
        assert transport.last_max_tokens == 256

    def test_glossary_injection(self) -> None:
        """Glossary terms are included in the system prompt."""
        transport = _FakeTransport([json.dumps({"k": {"v": "ok"}})])
        judge = LlmJudge(
            transport=transport,
            source_display="English",
            target_display="Ukrainian",
            glossary={"stone": "камінь", "axe": "сокира"},
        )
        judge.judge_batch([("k", "Stone axe", "Кам'яна сокира")])
        # The system prompt should include glossary terms
        system_msg = transport.last_messages[0]["content"]
        assert "stone→камінь" in system_msg or "stone" in system_msg

    def test_verdict_cache_hit_skips_transport(self, tmp_path) -> None:
        from app.infrastructure.cache.sqlite_cache import SqliteCache
        from app.infrastructure.providers.judge import build_verdict_cache_key

        cache = SqliteCache(str(tmp_path / "judge_cache.db"))
        src, tgt = "Stone pickaxe", "Кам'яний кирка"
        vkey = build_verdict_cache_key(src, tgt, "uk_UA", "gpt-test")
        cache.set_verdict(vkey, "flag", score=2, issue="grammar", attempts=0)

        transport = _FakeTransport()
        judge = LlmJudge(
            transport=transport,
            source_display="English",
            target_display="Ukrainian",
            cache=cache,
            target_lang="uk_UA",
            judge_model="gpt-test",
        )
        results = judge.judge_batch([("key1", src, tgt)])
        assert transport.call_count == 0
        assert results["key1"].is_flag
        assert results["key1"].score == 2
        cache.close()

    def test_parallel_judge_workers(self) -> None:
        transport = _FakeTransport([
            json.dumps({"k1": {"v": "ok"}, "k2": {"v": "ok"}}),
            json.dumps({"k3": {"v": "ok"}}),
        ])
        judge = LlmJudge(
            transport=transport,
            source_display="English",
            target_display="Ukrainian",
            chunk_size=2,
            judge_workers=2,
        )
        items = [("k1", "a", "b"), ("k2", "c", "d"), ("k3", "e", "f")]
        results = judge.judge_batch(items)
        assert len(results) == 3
        assert transport.call_count == 2

    def test_parallel_judge_workers_with_sqlite_cache(self, tmp_path) -> None:
        from app.infrastructure.cache.sqlite_cache import SqliteCache

        cache = SqliteCache(str(tmp_path / "parallel_judge.db"))
        transport = _FakeTransport([
            json.dumps({"k1": {"v": "ok"}, "k2": {"v": "ok"}}),
            json.dumps({"k3": {"v": "flag", "score": 2, "issue": "grammar"}}),
        ])
        judge = LlmJudge(
            transport=transport,
            source_display="English",
            target_display="Ukrainian",
            chunk_size=2,
            judge_workers=2,
            cache=cache,
            target_lang="uk_UA",
            judge_model="gpt-test",
        )
        items = [("k1", "a", "b"), ("k2", "c", "d"), ("k3", "e", "f")]
        results = judge.judge_batch(items)
        assert len(results) == 3
        assert results["k3"].is_flag
        assert transport.call_count == 2
        cache.close()


# ── Threshold logic ─────────────────────────────────────────────────────


def test_flag_selection_at_threshold() -> None:
    """Flag if score <= threshold, ok if score > threshold."""
    transport = _FakeTransport([
        json.dumps({
            "a": {"v": "flag", "score": 2},
            "b": {"v": "flag", "score": 4},
        })
    ])
    judge = LlmJudge(transport=transport, source_display="English", target_display="Ukrainian")
    items = [("a", "src", "tgt"), ("b", "src2", "tgt2")]
    results = judge.judge_batch(items)
    assert results["a"].is_flag
    assert results["b"].is_flag  # still flagged by judge, the threshold is applied in the stage
