"""Tests for token-budget chunking."""

from __future__ import annotations

from app.application.token_budget import build_token_chunks, estimate_tokens


class TestEstimateTokens:
    def test_minimum_one(self) -> None:
        assert estimate_tokens("") == 1

    def test_scales_with_length(self) -> None:
        assert estimate_tokens("a" * 40) == 10


class TestBuildTokenChunks:
    def test_empty(self) -> None:
        chunks, long_items = build_token_chunks(
            [],
            max_input_tokens=1000,
            max_items=25,
            max_text_length=200,
        )
        assert chunks == []
        assert long_items == []

    def test_long_texts_separated(self) -> None:
        long_text = "x" * 250
        chunks, long_items = build_token_chunks(
            [("k1", "short"), ("k2", long_text)],
            max_input_tokens=5000,
            max_items=25,
            max_text_length=200,
        )
        assert long_items == [("k2", long_text)]
        assert len(chunks) == 1
        assert chunks[0] == [("k1", "short")]

    def test_respects_max_items(self) -> None:
        items = [(f"k{i}", "hi") for i in range(10)]
        chunks, long_items = build_token_chunks(
            items,
            max_input_tokens=100_000,
            max_items=3,
            max_text_length=200,
        )
        assert long_items == []
        assert sum(len(c) for c in chunks) == 10
        assert all(len(c) <= 3 for c in chunks)

    def test_respects_token_budget(self) -> None:
        items = [(f"k{i}", "word " * 50) for i in range(20)]
        chunks, _ = build_token_chunks(
            items,
            max_input_tokens=200,
            max_items=100,
            max_text_length=500,
        )
        assert len(chunks) > 1

    def test_single_item_chunk(self) -> None:
        chunks, long_items = build_token_chunks(
            [("only", "text")],
            max_input_tokens=3500,
            max_items=25,
            max_text_length=200,
        )
        assert long_items == []
        assert chunks == [[("only", "text")]]
