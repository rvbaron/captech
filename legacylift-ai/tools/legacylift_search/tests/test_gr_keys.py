"""Tests for the two GR dedupe keys and the tiered discriminator.

Milestone 1, Step 6 of `docs/exec-plans/active/reqs-to-data-store.md`, over
`NORMATIVE SPEC-3` §S3.3.1. Every test here fails before Step 6 with
`No module named 'legacylift_search.gr_keys'` and passes after.

The tests are chosen for the *silent* failures, not for coverage: every one
of them is a case where two plausible implementations produce different keys
for the same rule and the merge then stops working with nothing raised
anywhere.
"""

from __future__ import annotations

import hashlib
import inspect

from legacylift_search import gr_keys
from legacylift_search.gr_keys import (
    DEDUPE_KEY_ANCHOR_ONLY_PREFIX,
    DEDUPE_KEY_PREFIX,
    MISSING_CONTENT_HASH,
    TIER_EMPTY,
    TIER_SPAN_HASHES,
    TIER_STRUCTURED_BODY,
    compute_dedupe_keys,
    dedupe_key,
    dedupe_key_anchor_only,
    select_discriminator,
)
from legacylift_search.identity import DIGEST_HEX_CHARS, UNIT_SEPARATOR


def test_a_partially_hashable_citation_set_keys_deterministically():
    """Proves a NULL `content_hash` is spelled `ch0:none` in tier 2.

    A citation whose range cannot be read stores a NULL `content_hash` rather
    than being dropped, so a requirement can hold two citations of which one
    has a hash and one does not. This asserts the key equals the one computed
    from the same inputs with the missing hash spelled `ch0:none` — i.e. that
    the hole is *encoded*, not absent. It fails under the tempting reading of
    "set", which drops NULL members and joins what is left: that produces a
    one-member discriminator and a different key.
    """
    keys = compute_dedupe_keys(
        ["ak1:aaaaaaaaaaaaaaaa"],
        "behavioral",
        "B-COND",
        citation_content_hashes=["ch1:1111111111111111", None],
    )
    expected_discriminator = UNIT_SEPARATOR.join(
        sorted({"ch1:1111111111111111", MISSING_CONTENT_HASH})
    )
    assert keys.discriminator.value == expected_discriminator
    assert keys.dedupe_key == dedupe_key(
        ["ak1:aaaaaaaaaaaaaaaa"], "behavioral", "B-COND", expected_discriminator
    )
    # Deterministic: the same inputs twice give the same bytes.
    assert (
        compute_dedupe_keys(
            ["ak1:aaaaaaaaaaaaaaaa"],
            "behavioral",
            "B-COND",
            citation_content_hashes=["ch1:1111111111111111", None],
        ).dedupe_key
        == keys.dedupe_key
    )
    # And dropping the hole would have keyed differently, which is the defect.
    assert keys.dedupe_key != dedupe_key(
        ["ak1:aaaaaaaaaaaaaaaa"], "behavioral", "B-COND", "ch1:1111111111111111"
    )


def test_all_unreadable_citations_do_not_key_like_no_citations():
    """Proves the sentinel keeps tier 2 and tier 3 distinguishable.

    Encode a hole as `''` and a requirement whose every citation is
    unreadable produces the joined string `''` — byte-identical to tier 3,
    which means "this rule has no citations and no typed body at all". Those
    are two different facts about a rule and must not share an encoding.
    This is the tier-2-versus-tier-3 collapse the sentinel exists to prevent,
    and it fails the moment anyone spells the hole as the empty string.
    """
    anchors = ["ak1:aaaaaaaaaaaaaaaa"]
    all_unreadable = compute_dedupe_keys(
        anchors, "behavioral", "B-COND", citation_content_hashes=[None, None]
    )
    no_citations_at_all = compute_dedupe_keys(anchors, "behavioral", "B-COND")

    assert all_unreadable.discriminator.tier == TIER_SPAN_HASHES
    assert all_unreadable.discriminator.value == MISSING_CONTENT_HASH
    assert no_citations_at_all.discriminator.tier == TIER_EMPTY
    assert no_citations_at_all.discriminator.value == ""
    assert all_unreadable.dedupe_key != no_citations_at_all.dedupe_key


def test_a_missing_rule_class_or_pattern_encodes_as_the_empty_string():
    """Proves a missing top-level part is `''`, never `None`/`"None"`/`"NULL"`.

    `rule_class` and `pattern` are both nullable while a record is `draft`,
    so this is reachable on ordinary data rather than a corner case. The
    formula is hashed, so an unencodable part is not a nullable column, it is
    an ambiguity: two correct implementations that spell it differently
    produce different keys for the same rule. Fails if `None` reaches the
    payload as its `str()`.
    """
    anchors = ["ak1:aaaaaaaaaaaaaaaa"]
    assert dedupe_key(anchors, None, None, "") == dedupe_key(anchors, "", "", "")
    assert dedupe_key(anchors, None, None, "") != dedupe_key(
        anchors, "None", "None", ""
    )
    assert dedupe_key(anchors, None, None, "") != dedupe_key(
        anchors, "NULL", "NULL", ""
    )
    assert dedupe_key_anchor_only(anchors, None, None) == dedupe_key_anchor_only(
        anchors, "", ""
    )


def test_the_three_discriminator_tiers_are_selected_in_order_and_assertable():
    """Proves tier order and that the tier is recoverable from the result.

    Tier 1 (a canonical typed body) outranks tier 2 (the span-hash set) which
    outranks tier 3 (the empty string), and `Discriminator.tier` says which
    fired. The tier is otherwise unrecoverable from the key, and two of this
    plan's acceptance criteria are stated about it — which is why
    `select_discriminator` is exposed separately from `compute_dedupe_keys`
    at all.
    """
    body_wins = select_discriminator(
        structured_body_canonical='{"expression":"a+b"}',
        citation_content_hashes=["ch1:1111111111111111"],
    )
    assert body_wins.tier == TIER_STRUCTURED_BODY
    assert body_wins.value == '{"expression":"a+b"}'

    hashes_win = select_discriminator(
        citation_content_hashes=["ch1:2222222222222222"]
    )
    assert hashes_win.tier == TIER_SPAN_HASHES

    empty = select_discriminator()
    assert empty.tier == TIER_EMPTY
    assert empty.value == ""

    # A body that canonicalises to nothing is treated as absent rather than
    # shadowing tier 2 with a value identical to tier 3's.
    assert (
        select_discriminator(
            structured_body_canonical="", citation_content_hashes=["ch1:3"]
        ).tier
        == TIER_SPAN_HASHES
    )


def test_tier_three_is_reachable_and_is_not_dead_code():
    """Proves tier 3 exists and is exercised.

    Tier 3 is nearly unreachable for *this* extractor — `source` is a
    required field of `RULES_SCHEMA` and Step 3 forbids dropping a citation —
    so it is easy to delete as dead code. It exists for Milestone 2's other
    producers and for citations a human adds during review, and this test is
    what makes deleting it fail.
    """
    keys = compute_dedupe_keys([], None, None)
    assert keys.discriminator.tier == TIER_EMPTY
    assert keys.dedupe_key.startswith(DEDUPE_KEY_PREFIX)
    assert keys.dedupe_key_anchor_only.startswith(DEDUPE_KEY_ANCHOR_ONLY_PREFIX)


def test_anchor_keys_are_deduplicated_and_sorted_inside_the_functions():
    """Proves `sorted(anchor_keys)` has exactly one reading here.

    "`sorted(anchor_keys)`" has two plausible readings and two
    implementations that read it differently mint different keys for the same
    rule. The deduplication and the sort happen inside these functions, so a
    caller handing them the same anchors in a different order — or twice, as
    a requirement citing one symbol from two ranges does — gets the same key.
    """
    a, b = "ak1:aaaaaaaaaaaaaaaa", "ak1:bbbbbbbbbbbbbbbb"
    assert dedupe_key([a, b], None, None, "") == dedupe_key([b, a], None, None, "")
    assert dedupe_key([a, b, a], None, None, "") == dedupe_key(
        [a, b], None, None, ""
    )
    assert dedupe_key_anchor_only([a, b], None, None) == dedupe_key_anchor_only(
        [b, a, b], None, None
    )


def test_a_two_anchor_rule_cannot_collide_with_a_one_anchor_rule():
    """Proves the anchor list is joined with the separator, not concatenated.

    The formula joins the sorted anchor list *as well as* the remaining
    top-level parts, so a two-anchor rule cannot collide with a one-anchor
    rule whose inputs happen to concatenate to the same bytes. Fails if
    anyone joins the anchors with `''`.
    """
    two = dedupe_key(["ak1:aa", "ak1:bb"], None, None, "")
    one = dedupe_key(["ak1:aaak1:bb"], None, None, "")
    assert two != one


def test_the_anchor_only_key_ignores_the_discriminator_and_the_full_one_does_not():
    """Proves the two keys differ in exactly the drift-bearing part.

    Tier 2 of the discriminator is the span-level `content_hash` set, so
    *any* edit to the cited code re-keys the full key. That is intended — but
    the rule must not arrive at stage two as a *cold* miss, so a second
    drift-resistant key over the tier-1 parts only sits beside it. This is
    the property that makes a `drift` candidate possible at all.
    """
    anchors = ["ak1:aaaaaaaaaaaaaaaa"]
    before = compute_dedupe_keys(
        anchors, "behavioral", "B-COND", citation_content_hashes=["ch1:1"]
    )
    after = compute_dedupe_keys(
        anchors, "behavioral", "B-COND", citation_content_hashes=["ch1:2"]
    )
    assert before.dedupe_key != after.dedupe_key
    assert before.dedupe_key_anchor_only == after.dedupe_key_anchor_only


def test_reclassification_moves_both_keys():
    """Proves `rule_class`/`pattern` feed BOTH keys, so drift does not mask it.

    A run that classifies the same code `definitional` where the previous run
    said `behavioral`, or picks `B-COND` where the last run picked
    `B-UNCOND`, re-keys the rule — and it re-keys **both** keys, so the
    anchor-only fallback does not catch this one. Stage two's line-range
    intersection is what catches it, which is why that half exists.
    """
    anchors = ["ak1:aaaaaaaaaaaaaaaa"]
    a = compute_dedupe_keys(
        anchors, "behavioral", "B-COND", citation_content_hashes=["ch1:1"]
    )
    b = compute_dedupe_keys(
        anchors, "definitional", "D-NEC", citation_content_hashes=["ch1:1"]
    )
    assert a.dedupe_key != b.dedupe_key
    assert a.dedupe_key_anchor_only != b.dedupe_key_anchor_only


def test_the_separator_and_digest_width_come_from_identity():
    """Proves `gr_keys` hashes with identity's separator and digest width.

    Two definitions of a hash input is the defect this whole unit is about,
    so the key formula is reproduced here from `identity.UNIT_SEPARATOR` and
    `identity.DIGEST_HEX_CHARS` and must match byte-for-byte. Fails the
    moment anyone redefines either constant locally — including the
    plausible "tidy-up" of inlining `"\\x1f"` or `16`.
    """
    anchors = ["ak1:aaaaaaaaaaaaaaaa", "ak1:bbbbbbbbbbbbbbbb"]
    payload = UNIT_SEPARATOR.join(
        (UNIT_SEPARATOR.join(sorted(anchors)), "behavioral", "B-COND", "ch1:1")
    )
    expected = (
        DEDUPE_KEY_PREFIX
        + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:DIGEST_HEX_CHARS]
    )
    assert dedupe_key(anchors, "behavioral", "B-COND", "ch1:1") == expected

    anchor_payload = UNIT_SEPARATOR.join(
        (UNIT_SEPARATOR.join(sorted(anchors)), "behavioral", "B-COND")
    )
    assert dedupe_key_anchor_only(anchors, "behavioral", "B-COND") == (
        DEDUPE_KEY_ANCHOR_ONLY_PREFIX
        + hashlib.sha256(anchor_payload.encode("utf-8")).hexdigest()[
            :DIGEST_HEX_CHARS
        ]
    )
    assert len(dedupe_key(anchors, None, None, "")) == len(DEDUPE_KEY_PREFIX) + 16


def test_no_key_function_takes_a_domain_or_a_statement():
    """Proves both keys are stable under a domain retag, structurally.

    `NORMATIVE SPEC-3` §S3.6's invariant is that no key takes a domain as an
    input, so a retag is `UPDATE ... SET domain = ?` on one row and nothing
    re-keys. The executable form at this layer is that no parameter of any
    public key function can carry a domain, a subject or a statement — the
    three excluded inputs — so a retag has nothing to reach.

    It is a signature inspection rather than a source-text scan on purpose:
    the prose in these docstrings names all three excluded inputs repeatedly,
    and a grep for the words would trip on the documentation describing why
    they are absent. (`test_gr_ingest.py` carries the behavioural half, over
    a real retag.)
    """
    forbidden = ("domain", "subject", "statement")
    for name in ("dedupe_key", "dedupe_key_anchor_only", "compute_dedupe_keys"):
        parameters = inspect.signature(getattr(gr_keys, name)).parameters
        for parameter in parameters:
            assert not any(word in parameter.lower() for word in forbidden), (
                f"{name} accepts {parameter!r}, which would put "
                f"domain-retag churn or human-edited text into the hash"
            )
