"""The two GR dedupe keys, and the tiered discriminator they hash.

Milestone 1, Step 6 of `docs/exec-plans/active/reqs-to-data-store.md`,
implementing `NORMATIVE SPEC-3` §S3.3.1 with the three refinements the plan's
Decision Log declares (when the key is recomputed, how a missing top-level
part is encoded, how a missing element *inside* the tier-2 discriminator is
encoded). Where the plan and SPEC-3 disagree, SPEC-3 wins; on those three the
plan wins.

Two keys answer two questions and both are stored as columns::

    dedupe_key             = "dk1:"  + sha256(anchors ␟ rule_class ␟ pattern ␟ discriminator)[:16]
    dedupe_key_anchor_only = "dka1:" + sha256(anchors ␟ rule_class ␟ pattern)[:16]

where `anchors` is `US.join(sorted(set(anchor_keys)))` and `␟`/`US` is U+001F,
imported from `identity` rather than redefined here. Two definitions of a hash
input is the defect this whole unit is about, so the separator and the digest
width both come from the one module that owns them.

Five rules carry the design and each has a silent failure behind it:

* **`anchor_keys` means one anchor per citation** — the `gr_citation.anchor_key`
  primary — **deduplicated and sorted across all of the requirement's
  citations.** It is requirement-level, *not* the contents of
  `gr_citation_anchor`. Two implementations reading this differently mint
  different keys for the same rule. `compute_dedupe_keys` deduplicates and
  sorts internally so a caller cannot get it wrong.
* **Every part is a string and a missing part is the empty string** — never
  `None`, never `"None"`, never `"NULL"`. `rule_class` and `pattern` are both
  nullable, so this is reachable on ordinary data. The formula is hashed, so an
  unencodable part is not a nullable column, it is an ambiguity.
* **The discriminator is tiered** (`select_discriminator`): tier 1 the
  canonical form of the structured body, tier 2 the sorted span-level
  `content_hash` set from the citations, tier 3 the empty string.
* **Tier 2's hole rule, which SPEC-3 does not state.** A citation whose range
  cannot be read stores a NULL `content_hash` rather than being dropped, so a
  requirement can hold two citations of which one has a hash and one does not.
  Each citation contributes either its `content_hash` or, when NULL, the
  literal `ch0:none`. Dropping NULL members is the tempting reading of "set"
  and is wrong: two correct implementations would then disagree about whether
  a hole shrinks the set or fills it. And encoding the hole as `''` would make
  an all-unreadable requirement produce the joined string `''` —
  byte-identical to tier 3, which means "no citations and no typed body at
  all". Those are different facts about a rule and must not share an encoding.
* **Tier 3 is nearly unreachable for this extractor** (`source` is a required
  field of `RULES_SCHEMA` and Step 3 forbids dropping a citation). It exists
  for Milestone 2's other producers and for citations a human adds during
  review. **Do not delete it as dead code** on the strength of a Milestone 1
  corpus.

**The keys are recomputed on extractor-owned writes only, never on a human
edit.** This refines SPEC-3 §S3.3's "recomputed on every write": `rule_class`
and `pattern` are inputs and both nullable while a record is `draft`, so a
literal reading re-keys the row the moment a reviewer fills one in and the
next extraction no longer matches it. Store both as columns; never derive on
read. `set-field` (Step 8) must therefore *not* call anything in this module.

`select_discriminator` is exposed separately from `compute_dedupe_keys` so
that ingest and the future move-repair share one implementation, and so a
test can assert which tier fired — the tier is otherwise unrecoverable from
the key.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Iterable, Sequence

from .identity import DIGEST_HEX_CHARS, UNIT_SEPARATOR

__all__ = [
    "DEDUPE_KEY_ANCHOR_ONLY_PREFIX",
    "DEDUPE_KEY_PREFIX",
    "MISSING_CONTENT_HASH",
    "TIER_EMPTY",
    "TIER_SPAN_HASHES",
    "TIER_STRUCTURED_BODY",
    "DedupeKeys",
    "Discriminator",
    "compute_dedupe_keys",
    "dedupe_key",
    "dedupe_key_anchor_only",
    "select_discriminator",
]


DEDUPE_KEY_PREFIX: Final[str] = "dk1:"
"""Version prefix on the full key. Mandatory, so the formula can evolve
unambiguously — a `dk2:` key is visibly not comparable with a `dk1:` one."""

DEDUPE_KEY_ANCHOR_ONLY_PREFIX: Final[str] = "dka1:"
"""Version prefix on the drift-resistant key. Deliberately a different
prefix, not the same one: the two keys live in two columns and a value that
wandered between them must be recognisable on sight."""

MISSING_CONTENT_HASH: Final[str] = "ch0:none"
"""The tier-2 sentinel for a citation whose `content_hash` is NULL.

`ch0:` deliberately shares the shape of `identity`'s real `ch1:` prefix while
being a version no hash ever produces, so a sentinel in the set is legible
rather than mysterious — and cannot collide with a genuine hash.
"""

TIER_STRUCTURED_BODY: Final[int] = 1
TIER_SPAN_HASHES: Final[int] = 2
TIER_EMPTY: Final[int] = 3


@dataclass(frozen=True)
class Discriminator:
    """Which tier of `dedupe_key`'s discriminator fired, and its value.

    `tier` is carried beside `value` because the tier is **not** recoverable
    from the key, and two of this plan's acceptance criteria are stated about
    it: that the three tiers are selected in the right order, and that an
    all-unreadable requirement (tier 2, every member the sentinel) does not
    key like a requirement with no citations at all (tier 3, the empty
    string).
    """

    tier: int
    value: str


@dataclass(frozen=True)
class DedupeKeys:
    """Both stored keys plus the discriminator that produced the full one.

    `discriminator` is returned rather than discarded so the caller can
    record or assert the tier without recomputing it, and so nothing needs a
    second call into `select_discriminator` with the same inputs.
    """

    dedupe_key: str
    dedupe_key_anchor_only: str
    discriminator: Discriminator


def _encode(part: str | None) -> str:
    """Encode one top-level key part: a missing part is the empty string.

    **Never `None`, never `"None"`, never `"NULL"`.** The formula is hashed,
    so an unencodable part is not a nullable column, it is an ambiguity: two
    correct implementations that spell a missing discriminator differently
    produce different keys for the same rule, and the merge silently stops
    working with nothing raised anywhere.

    Args:
        part: A key part, or `None` for a missing one.

    Returns:
        `part` unchanged, or `""` when it is `None`.
    """
    return "" if part is None else part


def _anchor_field(anchor_keys: Iterable[str]) -> str:
    """Join the requirement's primary anchors: deduplicated, then sorted.

    One anchor per citation — the `gr_citation.anchor_key` primary — across
    **all** of the requirement's citations. The deduplication and the sort
    both happen here rather than at the call site, because "`sorted(anchor_keys)`"
    has two plausible readings and two implementations that read it
    differently mint different keys for the same rule.

    Args:
        anchor_keys: The primary anchor of each of the requirement's
            citations, in any order, with duplicates permitted.

    Returns:
        The U+001F-joined sorted unique anchors; `""` for no citations.
    """
    return UNIT_SEPARATOR.join(sorted(set(anchor_keys)))


def _digest(payload: str, prefix: str) -> str:
    """Hash one assembled payload to a prefixed 16-hex-character key."""
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[
        :DIGEST_HEX_CHARS
    ]


def select_discriminator(
    *,
    structured_body_canonical: str | None = None,
    citation_content_hashes: Sequence[str | None] = (),
) -> Discriminator:
    """Choose `dedupe_key`'s discriminator, in the specified order of preference.

    1. **Tier 1** — the canonical form of the structured body, if one exists.
       `gr_body_schemas.canonical_structured_body` is the named producer, and
       the caller passes its output: it sorts keys and drops optional
       whitespace, so two byte-different payloads describing the same table
       produce the same discriminator. A discriminator that moved with
       formatting would re-key a rule whose typed body never changed.
    2. **Tier 2** — the span-level `content_hash` set from the citations,
       deduplicated, sorted, and joined with U+001F. Each citation contributes
       either its hash or, when that is NULL, the literal
       `MISSING_CONTENT_HASH`. Fires whenever the requirement has at least one
       citation, which is what keeps it distinguishable from tier 3.
    3. **Tier 3** — the empty string. Fires only when the requirement has no
       citations *and* no typed body. Nearly unreachable for this extractor
       and deliberately retained; see the module docstring.

    Args:
        structured_body_canonical: The canonical structured-body string, or
            `None`/`""` when the rule carries no typed body. An empty string
            is treated as absent, because a body that canonicalises to
            nothing carries no discrimination and would otherwise shadow
            tier 2 with a value identical to tier 3's.
        citation_content_hashes: One entry per citation — its
            `gr_citation.content_hash`, or `None` when the cited range could
            not be read. **One entry per citation, not per distinct hash**:
            the deduplication happens here, and a caller that pre-filtered
            NULLs away would have already destroyed the hole rule.

    Returns:
        The `Discriminator`, carrying both the tier and the value to hash.
    """
    if structured_body_canonical:
        return Discriminator(
            tier=TIER_STRUCTURED_BODY, value=structured_body_canonical
        )
    if citation_content_hashes:
        members = {
            h if h is not None else MISSING_CONTENT_HASH
            for h in citation_content_hashes
        }
        return Discriminator(
            tier=TIER_SPAN_HASHES,
            value=UNIT_SEPARATOR.join(sorted(members)),
        )
    return Discriminator(tier=TIER_EMPTY, value="")


def dedupe_key(
    anchor_keys: Iterable[str],
    rule_class: str | None,
    pattern: str | None,
    discriminator: str,
) -> str:
    """Compute the full `dedupe_key`: "have I extracted this rule before?".

    Per Step 3::

        dedupe_key = "dk1:" + sha256(
            US.join(sorted(anchor_keys)) + US + rule_class + US + pattern
            + US + discriminator
        ).hexdigest()[:16]

    The anchor list is joined as well as the three remaining top-level parts,
    so a two-anchor rule cannot collide with a one-anchor rule whose inputs
    happen to concatenate to the same bytes.

    **Two exclusions must not be reversed.** `statement` is excluded because a
    human edits it: a key containing human-edited text stops matching what the
    extractor produces next run, so the *reviewed* rules become exactly the
    ones that duplicate. `subject` is excluded because it is domain-derived,
    so including it would put domain-retag churn back into the hash — and it
    is redundant anyway, since `anchor_key` already contains the path.
    `gr_citation_anchor`'s full anchor set is excluded for a third reason: it
    would re-key a rule whose own cited code never changed, the moment an
    unrelated sibling declaration appeared inside its cited range.

    Args:
        anchor_keys: The primary anchor of each citation; deduplicated and
            sorted here.
        rule_class: `gr.rule_class`, or `None` — encoded as `""`.
        pattern: `gr.pattern`, or `None` — encoded as `""`.
        discriminator: `select_discriminator(...).value`.

    Returns:
        The `dk1:`-prefixed key, 20 characters in total.
    """
    payload = UNIT_SEPARATOR.join(
        (
            _anchor_field(anchor_keys),
            _encode(rule_class),
            _encode(pattern),
            _encode(discriminator),
        )
    )
    return _digest(payload, DEDUPE_KEY_PREFIX)


def dedupe_key_anchor_only(
    anchor_keys: Iterable[str],
    rule_class: str | None,
    pattern: str | None,
) -> str:
    """Compute the drift-resistant key, over the tier-1 parts only.

    Per Step 3::

        dedupe_key_anchor_only = "dka1:" + sha256(
            US.join(sorted(anchor_keys)) + US + rule_class + US + pattern
        ).hexdigest()[:16]

    **Why a second key exists.** Tier 2 of the discriminator is the span-level
    `content_hash` set, so *any* edit to the cited code re-keys the rule: run
    N+1 misses on the full key for what is recognisably the same rule. Routing
    it to review is correct on the merits, but it must not arrive as a *cold*
    miss indistinguishable from a genuinely new rule, because on a repository
    under active modernization drift is the normal case. A hit here is a
    **high-confidence review candidate** carrying the reason `drift` — never
    an auto-merge, because no similarity signal auto-merges anything at any
    confidence, and this one is no exception.

    Same string rules as the full key: every part is a string, and a missing
    part is the empty string.

    Args:
        anchor_keys: The primary anchor of each citation; deduplicated and
            sorted here.
        rule_class: `gr.rule_class`, or `None` — encoded as `""`.
        pattern: `gr.pattern`, or `None` — encoded as `""`.

    Returns:
        The `dka1:`-prefixed key, 21 characters in total.
    """
    payload = UNIT_SEPARATOR.join(
        (_anchor_field(anchor_keys), _encode(rule_class), _encode(pattern))
    )
    return _digest(payload, DEDUPE_KEY_ANCHOR_ONLY_PREFIX)


def compute_dedupe_keys(
    anchor_keys: Iterable[str],
    rule_class: str | None,
    pattern: str | None,
    *,
    structured_body_canonical: str | None = None,
    citation_content_hashes: Sequence[str | None] = (),
) -> DedupeKeys:
    """Compute both keys and report which discriminator tier fired.

    The one entry point ingest and the move-repair both call. It exists so
    that the two keys are always computed from the same anchor set in the same
    call — a caller that computed them separately could pass a different
    anchor list to each, and the pair would then describe two different rules
    while looking like a matched set.

    Args:
        anchor_keys: The primary anchor of each of the requirement's
            citations; deduplicated and sorted internally.
        rule_class: `gr.rule_class`, or `None`.
        pattern: `gr.pattern`, or `None`.
        structured_body_canonical: `canonical_structured_body(body)`, or
            `None` where the rule has no typed body.
        citation_content_hashes: One entry per citation, `None` where the
            range could not be read.

    Returns:
        The `DedupeKeys` triple.
    """
    anchors = sorted(set(anchor_keys))
    discriminator = select_discriminator(
        structured_body_canonical=structured_body_canonical,
        citation_content_hashes=citation_content_hashes,
    )
    return DedupeKeys(
        dedupe_key=dedupe_key(anchors, rule_class, pattern, discriminator.value),
        dedupe_key_anchor_only=dedupe_key_anchor_only(anchors, rule_class, pattern),
        discriminator=discriminator,
    )
