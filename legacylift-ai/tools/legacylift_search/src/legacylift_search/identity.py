"""Shared identity: the one place any key in this system is computed.

Milestone 1, Step 1 of `docs/exec-plans/active/reqs-to-data-store.md`, which
implements `NORMATIVE SPEC-3` (§S3.1, §S3.1.1, §S3.1.2, §S3.2) of the design
draft in `docs/exec-plans/pending/reqs-to-data-store-plan-draft.md`.

**Every consumer of these keys must call this module.** If the Layer-0 index,
the exporter and the requirements (GR) store each compute their own anchor,
they cannot join, and the identity is not shared — which is the whole point.
A second implementation appearing beside this one is precisely the failure
this module exists to prevent.

Four keys are defined here, and each answers a different question:

* `anchor_key(...)`   — *which code entity does this cite?* Includes the path;
  excludes line numbers, body text, and domain.
* `file_anchor_key(...)` — the **file grain** of the same key (§S3.1.1), used
  by the citation fallback when a cited line range matches no symbol.
* `content_hash(...)` — *did the cited code change, and is it a clone?*
  Includes body text; excludes path, name, language, line numbers, and domain.
* `new_ulid(...)`     — the surrogate identifier for `gr_id` and
  `gr_run.run_id`. Not a hash: nothing joins on its internal structure.

Because `anchor_key` includes the path and excludes the body while
`content_hash` does the reverse, the pair is jointly informative on every
reindex — same anchor + same content is unchanged; same anchor + different
content is **drift**; different anchor + same content is a **clone or move**;
different in both is unrelated (§S3.2).

`entity_class`: the closed, coarse set
--------------------------------------
`entity_class` is a **closed, coarse** set of exactly seven values:

    type, function, field, table, column, file, other

`file` is in the list because the citation fallback computes a file-level
anchor and needs a class for it. `column` is in it although nothing emits a
column symbol today. Both are named now rather than appended later, because a
value appended later is not a free extension.

The set is coarse because it goes **into a hash**: a value that changed when
an extractor improved would churn identity corpus-wide. The fine-grained
`kind` stays a plain column, where churn is harmless.

**Adding, removing or renaming a value re-keys every `anchor_key` derived
from it.** Such a change is therefore an `ak2:` event — bump the prefix and
recompute every anchor in both databases — and is never an edit in place.
**The same binds the *assignment*:** an unclassified kind is `other`, and
promoting a kind out of `other` later is likewise an `ak2:` event. That is
what makes the open half of the `kind` domain safe: an unrecognised
framework's symbols land in `other` honestly rather than being guessed into a
class a later improvement would move.

**There is deliberately no `entity_class_of(kind)` function here, and writing
one is the defect this step exists to prevent.** The `kind` domain is not
enumerable from this repository's source — `xml_extractor.py:208` mints kinds
as ``f"hibernate_{tag}"`` from the *client's* own Hibernate mapping files, and
`:252` from the client's Spring Webflow state elements — so no total mapping
can exist. Per §S3.1.2, `entity_class` is **declared by whichever extractor
emits the symbol** and is stored on `symbols.entity_class` (Step 2). The one
narrow exception is the backfill-only compatibility shim
`migrations.SHIM_KIND_TO_ENTITY_CLASS`, which lives beside Step 2's migration
-- its single caller -- and not here, so that nothing reaching for a key
formula finds a `kind` lookup next to it. Read its docstring before using it
for anything.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from typing import Final

__all__ = [
    "DIGEST_HEX_CHARS",
    "ENTITY_CLASSES",
    "UNIT_SEPARATOR",
    "anchor_key",
    "content_hash",
    "file_anchor_key",
    "new_ulid",
    "normalize_path",
]


ENTITY_CLASSES: Final[frozenset[str]] = frozenset(
    {"type", "function", "field", "table", "column", "file", "other"}
)
"""The closed, coarse `entity_class` set. Changing it is an `ak2:` event."""

UNIT_SEPARATOR: Final[str] = "\x1f"
"""U+001F UNIT SEPARATOR — the `anchor_key` field delimiter.

It must be a character that cannot occur in the inputs. Joining with `:` is
broken, because both `qualified_name` and `relative_path` contain colons,
dots and slashes: `"a:b"` + `"c"` and `"a"` + `"b:c"` would hash identically.
No validated identifier or path component contains U+001F.

**Public because `gr_keys` hashes with the same delimiter** (Step 3's
`dedupe_key` formula is "`US` is the same U+001F separator `anchor_key`
uses"). It is imported there rather than redefined, because two definitions
of a hash input is the whole defect class this module exists to prevent.
"""

_UNIT_SEPARATOR: Final[str] = UNIT_SEPARATOR
"""Private alias kept so nothing that already imported it breaks."""

_ANCHOR_KEY_PREFIX: Final[str] = "ak1:"
_CONTENT_HASH_PREFIX: Final[str] = "ch1:"
DIGEST_HEX_CHARS: Final[int] = 16
"""16 hexadecimal characters = 64 bits, deliberately not 12.

At 48 bits and 100,000 entities a collision is roughly one in 55,000, and in
this store a collision would silently merge two signed-off requirements.
Sixty-four bits puts it near three in ten billion.

**Public for the same reason `UNIT_SEPARATOR` is:** both `dedupe_key` and
`dedupe_key_anchor_only` truncate to this width, and `gr_keys` imports it.
"""

_DIGEST_HEX_CHARS: Final[int] = DIGEST_HEX_CHARS
"""Private alias kept so nothing that already imported it breaks."""


def normalize_path(path: str) -> str:
    """Normalize a repository-relative path for hashing.

    Converts backslashes to forward slashes and strips a leading `./`
    (§S2.2, §S3.1 departure 3). Normalization is required because this
    repository runs on Windows and analyzes code authored on Linux, so
    without it the same file hashes differently per host.

    **Case is deliberately preserved.** Case-folding is wrong on
    case-sensitive filesystems, where `Foo.java` and `foo.java` are two
    different files.

    Nothing else is changed: no collapsing of duplicate slashes, no
    resolution of `..`, no trailing-slash handling, no `Path` round-trip.
    A key formula is a contract, and every extra rule is a way for two
    implementations to disagree.

    Args:
        path: A repository-relative path in any separator style.

    Returns:
        The path with `/` separators and no leading `./`. The transform is
        idempotent — `normalize_path(normalize_path(p)) == normalize_path(p)`
        — which is why the leading-`./` strip loops rather than firing once.
    """
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _reject_unit_separator(**fields: str) -> None:
    """Raise if any input contains the delimiter, which would break injectivity.

    The whole collision argument for U+001F rests on it not occurring in the
    inputs. Silently allowing it would reintroduce the exact defect the
    delimiter choice exists to fix, so it fails loudly instead.

    Args:
        **fields: Field name to value, for the error message.

    Raises:
        ValueError: If any value contains U+001F.
    """
    for name, value in fields.items():
        if _UNIT_SEPARATOR in value:
            raise ValueError(
                f"anchor_key input {name!r} contains U+001F, the field "
                f"delimiter; this would make the key non-injective"
            )


def anchor_key(
    language: str,
    entity_class: str,
    qualified_name: str,
    relative_path: str,
) -> str:
    """Compute the code-entity anchor: "which code entity does this cite?".

    Per `NORMATIVE SPEC-3` §S3.1::

        anchor_key = "ak1:" + sha256(
            language ␟ entity_class ␟ qualified_name ␟ normalize_path(relative_path)
        ).hexdigest()[:16]

    where `␟` is U+001F. Four properties of that formula are deliberate and
    must not be "improved": the delimiter cannot be `:` (see
    `_UNIT_SEPARATOR`); the hash takes the **coarse** `entity_class` and never
    the fine-grained `kind`; paths are separator-normalized but never
    case-folded; and the digest is 16 hex characters, not 12. The `ak1:`
    prefix is mandatory so the formula can evolve unambiguously.

    Includes the path. **Excludes line numbers, body text, and domain** — no
    key in this module takes a domain as an input, which is a hard invariant
    with a test attached.

    Args:
        language: The Layer-0 language key (e.g. `csharp`). The **empty
            string** for the file grain — see `file_anchor_key`.
        entity_class: One of `ENTITY_CLASSES`, declared by the emitting
            extractor (§S3.1.2). Never the fine-grained `kind`.
        qualified_name: The symbol's qualified name; `""` for the file grain.
        relative_path: A repository-relative path, normalized here.

    Returns:
        The `ak1:`-prefixed anchor key, 20 characters in total.

    Raises:
        ValueError: If `entity_class` is not in `ENTITY_CLASSES`, or if any
            input contains U+001F.
    """
    if entity_class not in ENTITY_CLASSES:
        raise ValueError(
            f"entity_class {entity_class!r} is not one of the seven closed "
            f"values {sorted(ENTITY_CLASSES)}; adding a value is an 'ak2:' "
            f"event, not an edit in place"
        )
    normalized_path = normalize_path(relative_path)
    _reject_unit_separator(
        language=language,
        qualified_name=qualified_name,
        relative_path=normalized_path,
    )
    payload = _UNIT_SEPARATOR.join(
        (language, entity_class, qualified_name, normalized_path)
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return _ANCHOR_KEY_PREFIX + digest[:_DIGEST_HEX_CHARS]


def file_anchor_key(relative_path: str) -> str:
    """Compute the **file grain** of `anchor_key` (`NORMATIVE SPEC-3` §S3.1.1).

    Returns `anchor_key("", "file", "", relative_path)`. This is the total
    fallback for a citation whose line range matches no symbol — a file type
    the indexer does not parse, lines between declarations, a bare path
    meaning the whole file, or an unresolved path not in the tree at all.

    **The empty `language` is a constant for the whole class, not an absence
    encoding, and it must not be "fixed" into a lookup.** Two measured
    reasons, the second load-bearing:

    1. It carries no information at this grain. With `entity_class` fixed at
       `file` and `qualified_name` at `""`, the only varying input is the
       path — which determines the extension, which determines the language.
       Measured across both NNG indexes and `ctcm-api`: zero files carry more
       than one symbol language, and zero symbols disagree with their file's.
    2. **Any lookup would make a tier-1 `dedupe_key` input a function of index
       state.** `repo_files.language` exists only for files the indexer
       accepted, `detect_language` rejects every unrecognised extension
       outright, and an `unresolved` citation names a path that is not in the
       tree at all — so the same citation would key differently before and
       after an `index` run. A constant cannot churn.

    This function takes no `language` argument on purpose: a signature that
    accepted one would invite exactly that lookup.

    Args:
        relative_path: A repository-relative path, normalized by `anchor_key`.
            The path need not exist on disk; this function never touches the
            filesystem.

    Returns:
        The `ak1:`-prefixed file-level anchor key.
    """
    return anchor_key("", "file", "", relative_path)


def _normalize_body(body_text: str) -> str:
    """Normalize a code body for hashing (`NORMATIVE SPEC-3` §S3.2).

    Converts line endings to `\\n`, strips trailing whitespace on each line,
    and drops leading and trailing blank lines.

    **Comments are kept.** A rule may be cited *to* a comment, so a comment
    change is real drift, not noise. Do not add a second, coarser near-clone
    hash here; if near-clone detection is ever wanted it is a separate key.

    Args:
        body_text: The raw source text of an entity or a cited span.

    Returns:
        The normalized body, with no trailing newline.
    """
    lines = [
        line.rstrip()
        for line in body_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    start = 0
    end = len(lines)
    while start < end and not lines[start]:
        start += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return "\n".join(lines[start:end])


def content_hash(body_text: str) -> str:
    """Compute the content hash: "did the cited code change, and is it a clone?".

    Per `NORMATIVE SPEC-3` §S3.2::

        content_hash = "ch1:" + sha256(normalized_body).hexdigest()[:16]

    Includes body text. **Excludes path, name, language, line numbers, and
    domain** — which is why the signature takes exactly one argument.

    One function, but **two grains, and both are required**. The
    *entity-level* hash lives on the Layer-0 `symbols` row and answers "did
    this entity's code change, and is it a clone of another entity" (Step 2).
    The *span-level* hash lives on each GR citation row, covers exactly the
    cited lines, and is the tier-2 input to `dedupe_key` (Step 3). Neither
    substitutes for the other; the caller chooses the grain by choosing what
    text to pass.

    Args:
        body_text: The raw source text of the entity or the cited span.

    Returns:
        The `ch1:`-prefixed content hash, 20 characters in total.
    """
    digest = hashlib.sha256(_normalize_body(body_text).encode("utf-8")).hexdigest()
    return _CONTENT_HASH_PREFIX + digest[:_DIGEST_HEX_CHARS]


# --------------------------------------------------------------------------
# Surrogate identifiers
# --------------------------------------------------------------------------

_CROCKFORD_BASE32: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""Crockford base32: `I`, `L`, `O` and `U` are omitted so a human
transcribing an identifier cannot confuse them."""

_ULID_CHARS: Final[int] = 26
_ULID_TIMESTAMP_BITS: Final[int] = 48
_ULID_RANDOM_BITS: Final[int] = 80
_ULID_MAX_TIMESTAMP: Final[int] = (1 << _ULID_TIMESTAMP_BITS) - 1
_ULID_MAX_RANDOM: Final[int] = (1 << _ULID_RANDOM_BITS) - 1

_ULID_LOCK = threading.Lock()
_ULID_LAST_TIMESTAMP_MS: int = -1
_ULID_LAST_RANDOM: int = -1


def _encode_crockford_base32(value: int, length: int) -> str:
    """Encode a non-negative integer as fixed-length Crockford base32.

    Args:
        value: The integer to encode, most significant bits first.
        length: The number of output characters (zero-padded on the left).

    Returns:
        A `length`-character string over `_CROCKFORD_BASE32`.
    """
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD_BASE32[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid(prefix: str) -> str:
    """Mint a fresh, lexicographically sortable surrogate identifier.

    This is the generator for `gr_id` (prefix `GR-`) and `gr_run.run_id`
    (prefix `RUN-`). It lives in this module rather than in the knowledge
    store because it is identity, and because a second implementation
    appearing beside it is the failure this module exists to prevent.

    The algorithm, per Step 3 of the ExecPlan — **Step 3 owns the final
    format; this implementation is written to it, and if Step 3 restates it
    differently, Step 3 wins**: take the current Unix time in *milliseconds*
    as a 48-bit big-endian integer, append **10 cryptographically random
    bytes** (`secrets.token_bytes(10)`), and encode the resulting 128 bits as
    **26 characters of Crockford base32**. Then prefix. `"GR-"` therefore
    yields a 29-character identifier.

    No dependency is added for this. `uuid.uuid7()` would have been the tidy
    answer and is Python 3.14, while this package targets 3.11 or later;
    `uuid4` was rejected because the export sorts by `gr_id` and wants
    creation order. A constant prefix preserves sortability and makes an
    identifier self-describing in the three places it appears outside the
    database — the CLI, the JSONL export, and `BUSINESS_RULES.md`.

    **Monotonic within a millisecond.** Identifiers minted in sequence sort in
    generation order, which plain per-call randomness would only achieve about
    half the time for two calls inside the same millisecond. Within a
    millisecond the random component is incremented rather than redrawn (the
    standard ULID monotonic factory); a clock that goes backwards is treated
    the same way, so the sequence never regresses.

    Unlike every other identifier here, this one is **not a hash**: nothing
    joins on its internal structure and no key input depends on how it was
    built, so a divergent implementation would be untidy rather than silently
    destructive. It still belongs in one function.

    Args:
        prefix: A constant prefix, e.g. `"GR-"` or `"RUN-"`. Prepended
            verbatim; sortability is preserved because it is constant per
            identifier family.

    Returns:
        `prefix` followed by 26 Crockford base32 characters.
    """
    global _ULID_LAST_TIMESTAMP_MS, _ULID_LAST_RANDOM

    with _ULID_LOCK:
        now_ms = (time.time_ns() // 1_000_000) & _ULID_MAX_TIMESTAMP
        if now_ms > _ULID_LAST_TIMESTAMP_MS:
            _ULID_LAST_TIMESTAMP_MS = now_ms
            _ULID_LAST_RANDOM = int.from_bytes(secrets.token_bytes(10), "big")
        else:
            # Same millisecond (or a clock that stepped backwards): increment
            # rather than redraw, so the sequence is strictly increasing.
            _ULID_LAST_RANDOM += 1
            if _ULID_LAST_RANDOM > _ULID_MAX_RANDOM:
                _ULID_LAST_TIMESTAMP_MS += 1
                _ULID_LAST_RANDOM = int.from_bytes(secrets.token_bytes(10), "big")
        timestamp_ms = _ULID_LAST_TIMESTAMP_MS
        random_bits = _ULID_LAST_RANDOM

    value = (timestamp_ms << _ULID_RANDOM_BITS) | random_bits
    return prefix + _encode_crockford_base32(value, _ULID_CHARS)
