"""Tests for `gr_subject.py` -- the `subject` / `subject_provenance` derivation.

Milestone 1, Step 3 (`subject`/`subject_provenance` paragraphs) and Step 6a
of `docs/exec-plans/active/reqs-to-data-store.md`. The six numbered items
in `## Validation and Acceptance` (the ninth review round's "Neither
reserved domain becomes a subject" and "The subject fallback is populated"
entries) are each transcribed into one test class's docstring below.

`derive_subject` is pure -- no database, no filesystem, no model -- so
every test here calls it directly with hand-built `citation_domains` lists
rather than standing up a store or an index.
"""

from legacylift_search.gr_subject import (
    DOMAIN_EXCLUDED,
    DOMAIN_UNASSIGNED,
    derive_subject,
)

# A conformant B-UNCOND statement, worked out against the shipped
# `split_slots` (`gr_validator.py`) so this file's expectations are
# measured, not guessed: `split_slots(STATEMENT, "behavioral", "B-UNCOND")`
# locates `subject = (0, 9)`, i.e. exactly "A station".
STATEMENT = "A station must record a physical volume without overlap."
SUBJECT_SPAN_TEXT = "A station"


class TestNeitherReservedDomainBecomesASubject:
    """Item 1: no derived `subject` anywhere holds the literal `'excluded'`
    or `'unassigned'`.
    """

    def test_all_excluded_never_yields_the_literal_excluded(self):
        result = derive_subject(
            [DOMAIN_EXCLUDED, DOMAIN_EXCLUDED],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject != "excluded"
        assert result.subject != DOMAIN_EXCLUDED

    def test_all_unassigned_never_yields_the_literal_unassigned(self):
        result = derive_subject(
            [DOMAIN_UNASSIGNED, DOMAIN_UNASSIGNED],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject != "unassigned"
        assert result.subject != DOMAIN_UNASSIGNED

    def test_a_mixed_sentinel_set_never_yields_either_literal(self):
        result = derive_subject(
            [DOMAIN_EXCLUDED, DOMAIN_UNASSIGNED],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject not in (DOMAIN_EXCLUDED, DOMAIN_UNASSIGNED)

    def test_a_real_majority_domain_is_never_a_reserved_word_by_construction(self):
        # The derived branch only ever returns a value drawn from the real
        # (non-sentinel) entries it was given, so feeding it real domain
        # names that are not the two reserved strings can never produce
        # one -- recorded here as the trivial half of the property.
        result = derive_subject(
            ["billing", "billing", "shipping"], STATEMENT, "behavioral", "B-UNCOND"
        )
        assert result.subject == "billing"
        assert result.subject not in (DOMAIN_EXCLUDED, DOMAIN_UNASSIGNED)


class TestTheTwoSentinelsAreNotCollapsed:
    """Item 2: all-`excluded` citations get `derived_ambiguous`; all-
    `unassigned` citations get `llm_named`. This is the assertion that
    fails if the two sentinels are collapsed into one fallback provenance.
    """

    def test_all_excluded_is_derived_ambiguous(self):
        result = derive_subject(
            [DOMAIN_EXCLUDED, DOMAIN_EXCLUDED, DOMAIN_EXCLUDED],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject_provenance == "derived_ambiguous"

    def test_all_unassigned_is_llm_named(self):
        result = derive_subject(
            [DOMAIN_UNASSIGNED, DOMAIN_UNASSIGNED],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject_provenance == "llm_named"

    def test_the_two_provenances_differ_on_otherwise_identical_input(self):
        excluded_result = derive_subject(
            [DOMAIN_EXCLUDED], STATEMENT, "behavioral", "B-UNCOND"
        )
        unassigned_result = derive_subject(
            [DOMAIN_UNASSIGNED], STATEMENT, "behavioral", "B-UNCOND"
        )
        assert excluded_result.subject_provenance != unassigned_result.subject_provenance
        assert excluded_result.subject_provenance == "derived_ambiguous"
        assert unassigned_result.subject_provenance == "llm_named"


class TestTheSentinelLeavesTheDenominator:
    """Item 3: one `excluded` citation plus two in a real domain still
    derives from that real domain -- proving the sentinel left the
    denominator, not just the candidate set. Two excluded citations
    counted in the denominator would make "billing" a 2-of-3 minority
    rather than the 2-of-2 majority it actually is once the sentinel is
    dropped from both.
    """

    def test_one_excluded_plus_two_real_still_derives(self):
        result = derive_subject(
            [DOMAIN_EXCLUDED, "billing", "billing"],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject == "billing"
        assert result.subject_provenance == "derived"

    def test_one_unassigned_plus_two_real_still_derives(self):
        result = derive_subject(
            [DOMAIN_UNASSIGNED, "shipping", "shipping"],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject == "shipping"
        assert result.subject_provenance == "derived"


class TestTheSubjectFallbackIsPopulated:
    """Item 4: a cited file left `unassigned` gets `subject` set to the
    `[Subject]` span of the rule's own `statement`, not merely a fallback
    that is "available" but empty.
    """

    def test_unassigned_citation_reads_the_subject_span(self):
        result = derive_subject(
            [DOMAIN_UNASSIGNED], STATEMENT, "behavioral", "B-UNCOND"
        )
        assert result.subject == SUBJECT_SPAN_TEXT
        assert result.subject_provenance == "llm_named"

    def test_no_citations_at_all_also_reads_the_subject_span(self):
        # No domain can hold a majority of zero citations, so this takes
        # the fallback branch too. Not `llm_named` here (there is no
        # citation to be "all unassigned"), so the default
        # `derived_ambiguous` applies -- exercised for its own sake, since
        # it is the one input shape not covered by the named test items.
        result = derive_subject([], STATEMENT, "behavioral", "B-UNCOND")
        assert result.subject == SUBJECT_SPAN_TEXT
        assert result.subject_provenance == "derived_ambiguous"


class TestTheAbsentSubjectIsCountedSeparately:
    """Item 5: a rule whose `pattern` is NULL has no locatable `[Subject]`.
    `subject` is then `None` with the provenance still recorded, and that
    `None` must be distinguishable from a real `llm_named` string so
    `stats` can count it separately rather than folding it into
    `llm_named`'s figure.
    """

    def test_null_pattern_yields_none_subject_with_provenance_recorded(self):
        result = derive_subject(
            [DOMAIN_UNASSIGNED], STATEMENT, None, None
        )
        assert result.subject is None
        assert result.subject_provenance == "llm_named"

    def test_none_and_a_real_llm_named_value_are_distinguishable(self):
        absent = derive_subject([DOMAIN_UNASSIGNED], STATEMENT, None, None)
        named = derive_subject(
            [DOMAIN_UNASSIGNED], STATEMENT, "behavioral", "B-UNCOND"
        )
        assert absent.subject_provenance == named.subject_provenance == "llm_named"
        assert absent.subject is None
        assert named.subject is not None
        # The property `stats` relies on: filtering on `subject IS NULL`
        # separates the two without touching `subject_provenance` at all.
        assert absent.subject != named.subject


class TestTheMajorityRule:
    """Item 6: the majority rule itself, including a tie -- which is not a
    majority and falls through to the fallback branch exactly like any
    other non-majority split, with no separate tie-break.
    """

    def test_a_strict_majority_derives(self):
        result = derive_subject(
            ["billing", "billing", "shipping"], STATEMENT, "behavioral", "B-UNCOND"
        )
        assert result.subject == "billing"
        assert result.subject_provenance == "derived"

    def test_exactly_half_is_not_a_majority(self):
        # 2-of-4 is exactly half, not "more than half" -- must not derive.
        result = derive_subject(
            ["billing", "billing", "shipping", "shipping"],
            STATEMENT,
            "behavioral",
            "B-UNCOND",
        )
        assert result.subject_provenance == "derived_ambiguous"
        assert result.subject != "billing"
        assert result.subject != "shipping"

    def test_a_two_way_tie_falls_back_with_no_tie_break(self):
        result = derive_subject(
            ["billing", "shipping"], STATEMENT, "behavioral", "B-UNCOND"
        )
        assert result.subject_provenance == "derived_ambiguous"
        assert result.subject == SUBJECT_SPAN_TEXT

    def test_a_single_real_domain_is_a_trivial_majority(self):
        result = derive_subject(["billing"], STATEMENT, "behavioral", "B-UNCOND")
        assert result.subject == "billing"
        assert result.subject_provenance == "derived"
