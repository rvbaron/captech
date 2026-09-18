"""Embed-eligibility helpers (spike #1 + #2).

These functions decide which chunks are worth a dense vector and collapse
duplicate chunk text so identical code is embedded once. They are pure and
side-effect free so they can be unit-tested without a store or embedder.

Design constraints (from the maintainer's caveat):

- A chunk below ``embed_min_tokens`` is normally skipped at EMBED time only —
  it still lives in SQLite + FTS5, so lexical and ``symbols`` lookups keep
  full recall. We just don't pay for a dense vector on, e.g., a one-line
  property getter or an interface method stub.
- BUT a small chunk that carries business logic — most importantly data
  *validation* attributes/annotations (`[Required]`, `@NotNull`,
  `@Validated`, EF/Hibernate column constraints) — MUST still be embedded.
  ``has_business_logic`` is the guard that protects those chunks regardless of
  size.
"""

from __future__ import annotations

import re

from .models import CodeChunk

# Validation / data-annotation attribute and decorator names across the
# supported stacks. Matched case-insensitively as whole words. This is the
# heart of the caveat: even a tiny property is semantically rich if it is
# decorated with one of these.
_VALIDATION_TERMS = (
    # .NET DataAnnotations + EF / FluentValidation
    "required",
    "stringlength",
    "maxlength",
    "minlength",
    "range",
    "regularexpression",
    "emailaddress",
    "phone",
    "creditcard",
    "compare",
    "validation",
    "validate",
    "key",
    "foreignkey",
    "column",
    "table",
    "index",
    "notmapped",
    "concurrencycheck",
    "timestamp",
    "datatype",
    # Java / Jakarta Bean Validation + Hibernate
    "notnull",
    "notblank",
    "notempty",
    "size",
    "min",
    "max",
    "pattern",
    "valid",
    "validated",
    "positive",
    "negative",
    "past",
    "future",
    "digits",
    "assert",
    "constraint",
    "entity",
    "joincolumn",
    "onetomany",
    "manytoone",
    "manytomany",
    # Python validators / pydantic
    "validator",
    "field_validator",
    "constr",
    "conint",
)

# Tokens that indicate branching, comparison, or policy logic — a small chunk
# with any of these is doing real work, not just declaring a member.
_LOGIC_PATTERNS = (
    r"\bif\b",
    r"\belse\b",
    r"\bswitch\b",
    r"\bcase\b",
    r"\bfor\b",
    r"\bforeach\b",
    r"\bwhile\b",
    r"\breturn\b.*[<>=!]",  # conditional return
    r"\bthrow\b",
    r"\braise\b",
    r"==|!=|<=|>=|&&|\|\|",
    # SQL constraints / policy
    r"\bcheck\b",
    r"\bunique\b",
    r"\bnot\s+null\b",
    r"\bdefault\b",
    r"\bconstraint\b",
)

# An attribute/decorator/annotation line: C# `[Attr]`, Java/Python `@Ann`.
_DECORATOR_PATTERN = re.compile(r"(^|\n)\s*(\[[^\]\n]+\]|@[A-Za-z_][\w.]*)", re.MULTILINE)

_VALIDATION_RE = re.compile(
    r"\b(" + "|".join(_VALIDATION_TERMS) + r")\b", re.IGNORECASE
)
_LOGIC_RE = re.compile("|".join(_LOGIC_PATTERNS), re.IGNORECASE)


def has_business_logic(text: str) -> bool:
    """True if the chunk text carries validation/policy/branching signal that
    justifies a dense vector even when the chunk is small.

    We deliberately bias toward keeping (false positives cost one embedding;
    false negatives silently drop business logic from semantic search).
    """
    if not text:
        return False
    # A decorator/attribute line is only meaningful if it names a known
    # validation/mapping term — a bare `[Serializable]` or `@Override` is not
    # business logic. Check decorator lines against the validation vocabulary.
    for m in _DECORATOR_PATTERN.finditer(text):
        if _VALIDATION_RE.search(m.group(2)):
            return True
    # Any validation term anywhere (covers fluent `.NotNull()`, pydantic
    # validators, EF `HasColumnName`, etc.).
    if _VALIDATION_RE.search(text):
        return True
    # Branching / comparison / policy logic.
    if _LOGIC_RE.search(text):
        return True
    return False


def should_embed(chunk: CodeChunk, embed_min_tokens: int) -> bool:
    """Decide whether ``chunk`` should receive a dense vector.

    - ``embed_min_tokens <= 0`` keeps the legacy behavior: embed everything.
    - Otherwise embed when the chunk meets the token floor OR carries business
      logic (so validation-decorated members are never dropped for being short).
    """
    if embed_min_tokens <= 0:
        return True
    if chunk.token_count_estimate >= embed_min_tokens:
        return True
    return has_business_logic(chunk.text)


def partition_for_embedding(
    chunks: list[CodeChunk], embed_min_tokens: int
) -> tuple[list[CodeChunk], list[CodeChunk]]:
    """Split chunks into (to_embed, skipped) per ``should_embed``."""
    to_embed: list[CodeChunk] = []
    skipped: list[CodeChunk] = []
    for c in chunks:
        if should_embed(c, embed_min_tokens):
            to_embed.append(c)
        else:
            skipped.append(c)
    return to_embed, skipped


def dedupe_by_text_sha(
    chunks: list[CodeChunk],
) -> tuple[list[CodeChunk], dict[str, list[CodeChunk]]]:
    """Collapse chunks that share identical text (spike #2).

    Returns ``(representatives, members_by_sha)`` where ``representatives`` has
    one chunk per distinct ``text_sha256`` (the first seen) and
    ``members_by_sha`` maps each sha to every chunk that shares it (including
    the representative). The caller embeds only the representatives, then fans
    the resulting vector out to every member id — so every chunk still gets a
    vector in Chroma with zero recall loss, but identical text is embedded once.
    """
    members_by_sha: dict[str, list[CodeChunk]] = {}
    representatives: list[CodeChunk] = []
    for c in chunks:
        bucket = members_by_sha.get(c.text_sha256)
        if bucket is None:
            members_by_sha[c.text_sha256] = [c]
            representatives.append(c)
        else:
            bucket.append(c)
    return representatives, members_by_sha


__all__ = [
    "has_business_logic",
    "should_embed",
    "partition_for_embedding",
    "dedupe_by_text_sha",
]
