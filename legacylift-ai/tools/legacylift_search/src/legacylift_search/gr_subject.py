"""Subject derivation: `gr.subject` and `gr.subject_provenance`.

Milestone 1, Step 3 (the `subject`/`subject_provenance` paragraphs) and Step
6a ("What is derived at ingest, deterministically and with no model") of
`docs/exec-plans/active/reqs-to-data-store.md`.

**One implementation, called from two places.** `requirements ingest` calls
this on every rule it writes, and Step 8's `requirements rederive-subjects`
calls it again after a domain retag to recompute `subject` without moving
any dedupe key -- `derive_subject` here is that one implementation. It is a
pure function: no database handle, no filesystem access, and in particular
**no model call**. `legacylift_search` has no LLM dependency and this module
does not add one -- `llm_named` means "named by the model that already wrote
`statement`, read back deterministically with `split_slots`," not a fresh
inference.

**The two reserved sentinel domains are not the same, and collapsing them
is the ninth review round's own defect class.** `unassigned` means nobody
has classified the file yet, and `tag-domains` fixes it -- so an
all-`unassigned` requirement gets `llm_named`, the provenance whose whole
meaning is "fixable by re-tagging." `excluded` means the file was
deliberately declared out of scope, and re-running `tag-domains` changes
nothing about that -- so an all-`excluded` requirement gets
`derived_ambiguous` instead, because routing an unfixable case into the
bucket that means "fixable" would quietly depress the one rate the
Concrete Steps section says to read before trusting the derivation. Both
sentinels are excluded from the majority's candidate set *and* its
denominator: a requirement with one `excluded` citation and two in a real
domain still derives from that real domain, because the sentinel leaves the
count entirely rather than merely losing the vote.

**Never write `statement`.** This function only reads it, on the fallback
branch, via `gr_validator.split_slots`. Step 6a is explicit that ingest
performs no templating and `rederive-subjects` does not touch that column
at all.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from legacylift_search.gr_validator import split_slots

__all__ = ["SubjectDerivation", "derive_subject", "DOMAIN_UNASSIGNED", "DOMAIN_EXCLUDED"]

# The two reserved `file_domains.domain` sentinels (Step 3). Neither may ever
# become a `gr.subject` value -- see the module docstring for why they are
# not interchangeable despite both being "not a real domain."
DOMAIN_UNASSIGNED = "unassigned"
DOMAIN_EXCLUDED = "excluded"

_SENTINEL_DOMAINS = frozenset({DOMAIN_UNASSIGNED, DOMAIN_EXCLUDED})


@dataclass(frozen=True)
class SubjectDerivation:
    """The result of deriving one requirement's subject.

    `subject` is `str | None` rather than a sentinel string on purpose: an
    absent subject (no `[Subject]` span could be located on the fallback
    branch -- `pattern` is NULL, or the template keyword is absent from
    `statement`) and a model-named one must not share an encoding, because
    `requirements stats` counts the two separately rather than folding the
    absent case into `llm_named`'s figure. `subject_provenance` still
    records which branch ran even when `subject` is `None` -- "no subject
    was locatable" is a fact about *this* attempt, not a reason to omit
    which attempt it was.
    """

    subject: str | None
    subject_provenance: str  # 'derived' | 'derived_ambiguous' | 'llm_named'


def derive_subject(
    citation_domains: Sequence[str],
    statement: str,
    rule_class: str | None,
    pattern: str | None,
) -> SubjectDerivation:
    """Derive `subject` and `subject_provenance` for one requirement.

    Args:
        citation_domains: the `file_domains.domain` value for **each** of
            the requirement's citations, one entry per citation (not per
            distinct file -- `gr_citation` is one-to-many, and Step 3's
            majority is a majority over citations, so a file cited three
            times contributes three entries here). May contain the two
            reserved sentinels, `DOMAIN_UNASSIGNED` and `DOMAIN_EXCLUDED`.
        statement: the requirement's own `statement` text -- read, never
            written, on the fallback branch only.
        rule_class: `gr.rule_class`, passed straight through to
            `split_slots` for signature stability (see that function).
        pattern: `gr.pattern`. `None` means the fallback branch's
            `split_slots` call cannot locate a `[Subject]` span at all,
            which is the NULL-subject case this function must still label
            with a provenance.

    Returns:
        A `SubjectDerivation`. `subject_provenance` is always one of the
        three values; `subject` is `None` exactly when no domain holds a
        majority *and* `split_slots` could not locate a `[Subject]` span.

    The derivation, in order:

    1. **Derived branch** (Step 3): drop every sentinel entry from
       `citation_domains` -- both from the candidate set and from the
       denominator -- and take the domain holding a **strict majority**
       (more than half) of what remains. If one exists, that domain *is*
       the subject, with provenance `'derived'`. State it as majority and
       nothing else: a tie is not a majority and falls through exactly like
       any other non-majority split, with no separate tie-break rule (an
       earlier version of this plan proposed one and made it unreachable,
       since a tie can never be a majority).
    2. **Fallback branch**, taken whenever step 1 finds no majority --
       including when every citation is a sentinel, when the real-domain
       citations split with no majority, or when there are no citations at
       all. Provenance is `'derived_ambiguous'` by default (Step 3: "if no
       domain holds a majority... set subject_provenance to
       derived_ambiguous"), **except** the one named override: when every
       citation is `DOMAIN_UNASSIGNED`, provenance is `'llm_named'` instead
       -- the case that re-running `tag-domains` can actually fix. An
       all-`DOMAIN_EXCLUDED` set of citations, or any other sentinel-only
       mix, keeps the default `'derived_ambiguous'`.
    3. Within the fallback branch, read the `[Subject]` span out of
       `statement` with `gr_validator.split_slots(statement, rule_class,
       pattern)`. If it returns a span, `subject` is that slice of
       `statement`. If it returns `None` -- `pattern` is NULL, or the
       template's keyword is absent from `statement` -- `subject` is
       `None` and the provenance from step 2 is still returned unchanged.
    """
    real_domains = [d for d in citation_domains if d not in _SENTINEL_DOMAINS]

    if real_domains:
        counts = Counter(real_domains)
        domain, count = counts.most_common(1)[0]
        if count * 2 > len(real_domains):
            return SubjectDerivation(subject=domain, subject_provenance="derived")

    # Fallback branch: no real domain holds a majority (possibly because
    # there is no real domain at all). Decide provenance first -- it does
    # not depend on whether `split_slots` finds anything -- then attempt the
    # statement read.
    if citation_domains and all(d == DOMAIN_UNASSIGNED for d in citation_domains):
        provenance = "llm_named"
    else:
        provenance = "derived_ambiguous"

    spans = split_slots(statement, rule_class, pattern)
    if spans.subject is None:
        return SubjectDerivation(subject=None, subject_provenance=provenance)

    start, end = spans.subject
    return SubjectDerivation(subject=statement[start:end], subject_provenance=provenance)
