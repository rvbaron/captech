"""Tests for embed_filter.py (spike #1 low-value filter + spike #2 dedup).

The central correctness property — the maintainer's caveat — is that a small
chunk carrying data-validation logic (attributes/annotations) is NEVER
filtered out of embedding. These tests pin that explicitly across C#, Java,
and Python forms.
"""

from __future__ import annotations

import hashlib

from legacylift_search.embed_filter import (
    dedupe_by_text_sha,
    has_business_logic,
    partition_for_embedding,
    should_embed,
)
from legacylift_search.models import CodeChunk


def _chunk(text: str, idx: int = 0, tokens: int | None = None) -> CodeChunk:
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if tokens is None:
        tokens = len(text.split())
    return CodeChunk(
        id=f"chunk:test:{idx}:{sha[:12]}",
        file_sha256="f" * 64,
        relative_path="src/Test.cs",
        language="csharp",
        chunk_index=idx,
        chunk_kind="symbol",
        symbol_id=None,
        symbol_path=None,
        start_byte=0,
        end_byte=len(text.encode("utf-8")),
        start_line=1,
        end_line=1 + text.count("\n"),
        text=text,
        text_sha256=sha,
        token_count_estimate=tokens,
    )


# --- has_business_logic: the caveat ---------------------------------------


def test_csharp_validation_attribute_is_business_logic() -> None:
    text = "[Required]\n[StringLength(50, MinimumLength = 2)]\npublic string Name { get; set; }"
    assert has_business_logic(text) is True


def test_java_bean_validation_annotation_is_business_logic() -> None:
    text = "@NotNull\n@Size(min = 2, max = 50)\nprivate String name;"
    assert has_business_logic(text) is True


def test_python_pydantic_validator_is_business_logic() -> None:
    text = "@field_validator('age')\ndef check_age(cls, v):\n    return v"
    assert has_business_logic(text) is True


def test_ef_column_mapping_is_business_logic() -> None:
    text = '[Column("customer_name")]\n[Key]\npublic string Name { get; set; }'
    assert has_business_logic(text) is True


def test_branching_logic_is_business_logic() -> None:
    text = "public bool IsValid(int x) { if (x > 0) return true; return false; }"
    assert has_business_logic(text) is True


def test_sql_constraint_is_business_logic() -> None:
    text = "age INT NOT NULL CHECK (age >= 0)"
    assert has_business_logic(text) is True


def test_trivial_getter_is_not_business_logic() -> None:
    text = "public string Name { get; set; }"
    assert has_business_logic(text) is False


def test_bare_non_validation_attribute_is_not_business_logic() -> None:
    # [Serializable] / @Override decorate but carry no validation/policy.
    assert has_business_logic("[Serializable]\npublic class Dto { }") is False
    assert has_business_logic("@Override\npublic void run() { }") is False


def test_empty_text_is_not_business_logic() -> None:
    assert has_business_logic("") is False


# --- should_embed ----------------------------------------------------------


def test_should_embed_disabled_filter_keeps_everything() -> None:
    tiny = _chunk("x;", tokens=1)
    assert should_embed(tiny, embed_min_tokens=0) is True


def test_should_embed_keeps_large_chunk() -> None:
    big = _chunk("word " * 100, tokens=100)
    assert should_embed(big, embed_min_tokens=80) is True


def test_should_embed_drops_small_trivial_chunk() -> None:
    trivial = _chunk("public string Name { get; set; }", tokens=6)
    assert should_embed(trivial, embed_min_tokens=80) is False


def test_should_embed_keeps_small_validation_chunk() -> None:
    """The caveat: small but validation-decorated → still embedded."""
    decorated = _chunk(
        "[Required]\npublic string Name { get; set; }", tokens=7
    )
    assert decorated.token_count_estimate < 80
    assert should_embed(decorated, embed_min_tokens=80) is True


# --- partition_for_embedding ----------------------------------------------


def test_partition_splits_and_protects_validation() -> None:
    chunks = [
        _chunk("word " * 100, idx=0, tokens=100),  # large -> embed
        _chunk("public int X { get; set; }", idx=1, tokens=6),  # trivial -> skip
        _chunk("[Required]\npublic int Y;", idx=2, tokens=4),  # small+valid -> embed
    ]
    to_embed, skipped = partition_for_embedding(chunks, embed_min_tokens=80)
    embed_ids = {c.id for c in to_embed}
    assert chunks[0].id in embed_ids
    assert chunks[2].id in embed_ids
    assert [c.id for c in skipped] == [chunks[1].id]


# --- dedupe_by_text_sha (spike #2) ----------------------------------------


def test_dedupe_collapses_identical_text() -> None:
    a = _chunk("identical body", idx=0)
    b = _chunk("identical body", idx=1)  # same text, different id
    c = _chunk("unique body", idx=2)
    reps, members = dedupe_by_text_sha([a, b, c])

    # Two distinct texts -> two representatives.
    assert len(reps) == 2
    # The shared sha maps to both members.
    assert len(members[a.text_sha256]) == 2
    assert {m.id for m in members[a.text_sha256]} == {a.id, b.id}
    assert len(members[c.text_sha256]) == 1


def test_dedupe_preserves_first_as_representative() -> None:
    a = _chunk("same", idx=0)
    b = _chunk("same", idx=1)
    reps, _ = dedupe_by_text_sha([a, b])
    assert reps[0].id == a.id
