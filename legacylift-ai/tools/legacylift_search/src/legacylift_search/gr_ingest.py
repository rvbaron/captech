"""Ingest: the two-stage merge, and the longest multi-table write here.

Milestone 1, Step 6 of `docs/exec-plans/active/reqs-to-data-store.md`, with
the field map and the anchor rules from Step 6a.

**Ingest is a merge, never truncate-and-insert**, and the two stages have
deliberately asymmetric behaviour:

1. **Stage one** is an exact `dedupe_key` match and it **merges
   automatically**. On a miss it tries `dedupe_key_anchor_only`; a hit there
   is a *high-confidence review candidate* carrying the reason `drift`, and
   **inserts a new row as well**.
2. **Stage two** runs only when neither key matched: it searches the
   `gr_statements` collection semantically **and** separately finds citations
   whose line ranges *intersect* an existing requirement's citations on the
   same file, and surfaces both as `gr_merge_candidate` rows.

**Stage two never merges on its own. No similarity threshold auto-merges
anything at any confidence.** The asymmetry is intentional and the reason
must be preserved here rather than rediscovered: the two failure modes are
not symmetric. A **false-distinct** — a duplicate row — is *visible*, and a
reviewer merges it, so it is recoverable. A **false-same** is *invisible*: a
real rule silently never enters the corpus, and coverage is this plan's
measured selling point. So the exact key is biased toward under-merging and
stage two recovers the residue without ever acting alone. Note also that
exact range equality is right for a *key* while range intersection is right
for a *candidate search* — different jobs, both needed.

`gr_merge_candidate`'s primary key is the **pair**, and `run_id` is
deliberately **not** in it, so the same pair surfacing on a later run updates
one row instead of being raised again and a resolution a reviewer already
recorded survives the next ingest.

One ingest is one transaction
-----------------------------
**One ingest is one transaction over the SQLite work — not one per rule.** It
touches `gr`, `gr_citation`, `gr_citation_anchor`, `gr_scenario`,
`gr_edge_case`, `gr_merge_candidate`, `gr_run` and `gr_run_hit`. Per-rule
commits mean a failure at rule 300 of 470 leaves a `gr_run` describing a run
that half-happened, and a retry appends a second run so `rules_in`
double-counts.

Two consequences are implemented rather than left to be inferred:

* **A failed ingest leaves no `gr_run` row at all**, so a retry is a first
  ingest needing no cleanup, no resume flag and no deduplication of run
  metadata. Say so plainly, because the instinct on seeing a half-finished
  job is to write recovery code for it — and there is no half-finished job to
  recover.
* **Every error names the offending rule by its `offer_ordinal` and the field
  that failed.** "ingest failed" over a 470-rule file tells the analyst
  nothing and sends them back to an extraction that cost hours.

**The embedding phase sits outside the transaction by design** (Step 5): the
rules commit as one unit and the vectors follow as the phase that is allowed
to degrade. `embedder=None` is a supported degraded success — ingest reports
`EmbedResult.reason` and the caller **exits zero**.

Field ownership is derived, never hand-maintained
-------------------------------------------------
The merge writes `EXTRACTOR_OWNED_FIELDS | SHADOWED_FIELDS`, the second
conditionally, taking the membership from `gr_fields` rather than from a list
here. There is **no "minus the insert-only pair"**: `disposition` and
`modality_confirmed` are human-writable and the merge never touches them.
`rationale`, `fit_criterion`, `enforcement_level`, `confidence_intent`,
`state`, `reviewed_by`, `owner`, `reviewed_at`, `review_note`, `disposition`
and `modality_confirmed` are never written on a merge.

Four `STORE_OWNED_FIELDS` columns *are* written on the merge, as store
bookkeeping outside the partition's field-mapped scope: `updated_at`, both
dedupe keys, and `extractor_payload`. **The merge refreshes
`extractor_payload`** and it participates in the value-changing-write
comparison — a payload frozen at first insert would defeat the one thing it
is for, promoting a field in a later milestone without re-running extraction.

`ruleClass` and `pattern` are column-mapped but sit **outside**
`EXTRACTOR_FIELD_MAP`: they are `HUMAN_WRITABLE_FIELDS`, written verbatim by
ingest **on insert only**. On a merge they can never change — both feed both
keys, so an exact-key hit implies they already agree and an anchor-only hit
inserts rather than updates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Final, Mapping

from .citations import WHOLE_FILE_END_LINE, AnchorResolver, parse_citation
from .gr_body_schemas import canonical_structured_body, validate_structured_body
from .gr_fields import (
    EXTRACTOR_FIELD_MAP,
    EXTRACTOR_OWNED_FIELDS,
    INSERT_ONLY_DEFAULTS,
    UNMAPPED_KEYS,
    get_shadowed_fields,
)
from .gr_keys import compute_dedupe_keys
from .gr_refresh import (
    describe_vector_shortfall,
    open_gr_collection,
    open_index_store_if_present,
    refresh_gr_derived_sql,
    refresh_gr_vectors,
)
from .gr_subject import DOMAIN_EXCLUDED, DOMAIN_UNASSIGNED, derive_subject
from .identity import content_hash, new_ulid, normalize_path
from .knowledge_store import KnowledgeStore
from .models import (
    EmbedResult,
    GRCitation,
    GREdgeCase,
    GRMergeCandidate,
    GRRun,
    GRRunHit,
    GRScenario,
    RefreshResult,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .embeddings import Embedder
    from .store import SQLiteStore
    from .vector_store import ChromaVectorStore

__all__ = [
    "CHILD_MAPPED_KEYS",
    "SEMANTIC_DISTANCE_MAX",
    "SEMANTIC_TOP_K",
    "VERBATIM_KEYS",
    "IngestError",
    "IngestResult",
    "ingest_extraction",
    "unmapped_rule_keys",
]


#: Incoming rule-object keys that land as **child-table rows** rather than as
#: `gr` columns. Step 3's completeness rule is a three-way disjunction —
#: mapped to a column, **or** to a child row, **or** named in
#: `gr_fields.UNMAPPED_KEYS` as knowingly unpromoted — and this constant is
#: the second branch, which had no computable referent before. `source`
#: becomes `gr_citation` rows; `given`/`when`/`then`/`and` become one
#: `gr_scenario` row; `edgeCases` becomes `gr_edge_case` rows.
CHILD_MAPPED_KEYS: Final[frozenset[str]] = frozenset(
    {"source", "given", "when", "then", "and", "edgeCases"}
)

#: Incoming keys ingest writes to a column **verbatim and outside**
#: `EXTRACTOR_FIELD_MAP`. Step 3's completeness test needs this third route
#: named explicitly or it fails on first real data: `ruleClass` and `pattern`
#: are `HUMAN_WRITABLE_FIELDS`, so they are deliberately absent from the
#: extractor field map, yet ingest is what first puts a value in them.
VERBATIM_KEYS: Final[dict[str, str]] = {"ruleClass": "rule_class", "pattern": "pattern"}

#: How many nearest neighbours stage two's semantic half considers per rule.
SEMANTIC_TOP_K: Final[int] = 5

#: The distance beyond which stage two does **not** raise a semantic
#: candidate. **This is a raise-a-candidate threshold and can never cause a
#: merge** — no similarity threshold auto-merges anything at any confidence,
#: so the only thing this number changes is which pairs a reviewer is shown.
#: The value is an unvalidated default and no corpus has been measured
#: against it yet; it is a parameter of `ingest_extraction` precisely so
#: tuning it needs no code change.
#:
#: **It is also metric-dependent, and nothing in this repository pins the
#: metric.** `ChromaVectorStore` sets `hnsw:sync_threshold` and
#: `hnsw:batch_size` but **no `hnsw:space`**, so the distance is whatever the
#: installed chromadb defaults to -- L2 on the pinned 1.5.9. Set a space, or
#: move the pin to a release with a different default, and this number
#: silently means something else. The failure direction is the quiet one: too
#: tight a threshold raises fewer candidates, and stage two returning no
#: candidates is indistinguishable from there being no near-duplicates to
#: find -- the same indistinguishability `open_gr_collection` guards against
#: for a reset-destroyed collection. Measure it on a real corpus before
#: trusting the candidate count as evidence of anything.
SEMANTIC_DISTANCE_MAX: Final[float] = 0.35

#: The keyword the pattern-free statement fallback uses, by `rule_class`.
#: `behavioral` takes `must` and `definitional` takes `always`; a NULL
#: `rule_class` also takes `must`, because `V-CLASS-01` already blocks such a
#: row from approval so nothing turns on the choice there.
_FALLBACK_KEYWORD: Final[dict[str | None, str]] = {
    "behavioral": "must",
    "definitional": "always",
    None: "must",
}


class IngestError(RuntimeError):
    """One rule could not be ingested, so the whole transaction failed.

    **The message always names the offending rule by its `offer_ordinal` and
    the field that failed.** That is the entire reason this class exists
    rather than letting a `ValueError` or an `sqlite3.IntegrityError` escape:
    "ingest failed" over a 470-rule file tells the analyst nothing and sends
    them back to an extraction that cost hours of model time.

    Attributes:
        offer_ordinal: The rule's index within this run's input array — the
            same value `gr_run_hit.offer_ordinal` would have carried.
        field: The incoming rule-object field that failed, or a short name for
            the check that failed when no single field is at fault.
    """

    def __init__(self, offer_ordinal: int, field: str, detail: str) -> None:
        self.offer_ordinal = offer_ordinal
        self.field = field
        super().__init__(
            f"ingest failed at offer_ordinal {offer_ordinal} on field "
            f"{field!r}: {detail}. Nothing was written -- the whole SQLite "
            f"half of an ingest is one transaction, so there is no gr_run "
            f"row, no gr rows and no partial state to clean up. Fix the "
            f"named rule and run the same command again."
        )


@dataclass
class IngestResult:
    """What one ingest did — the shape `stats` and the CLI banner read.

    Assembled rather than queried back so that a caller needs no second pass
    over the store to report a run, and so the counts the `gr_run` identity
    rests on (`rules_in = rules_new + rules_merged + rules_candidate`) are
    computed in one place.

    Two fields are easy to misread and are named apart deliberately.
    `rows_inserted` is `rules_new + rules_candidate`, **not** `rules_new`: a
    `candidate` outcome inserts a row as well as raising a pair.
    `not_accounted_for` is `int | None` and **None means never measured**, not
    zero — `complete` is then False, which is the whole point of the column.
    """

    run_id: str
    rules_in: int = 0
    rules_new: int = 0
    rules_merged: int = 0
    rules_candidate: int = 0
    rules_rejected: int = 0
    rows_inserted: int = 0
    #: Merged rules whose incoming values matched the stored row exactly, so
    #: no `UPDATE` ran and `updated_at` did not move. Still counted as
    #: `merged` and still given a `gr_run_hit`: being *seen* by a run and
    #: being *changed* by it are different facts.
    merges_with_no_change: int = 0
    gr_ids: list[str] = field(default_factory=list)
    candidates_raised: int = 0
    candidate_reasons: dict[str, int] = field(default_factory=dict)
    citations_inserted: int = 0
    citations_seen: int = 0
    scenarios_rewritten: int = 0
    edge_case_sets_rewritten: int = 0
    anchor_resolution_counts: dict[str, int] = field(default_factory=dict)
    #: The `file`-resolution rate broken down by file extension. A high rate
    #: concentrated in one extension is not noise, it is "Layer 0 has no
    #: extractor for this technology".
    file_resolution_by_extension: dict[str, int] = field(default_factory=dict)
    subject_provenance_counts: dict[str, int] = field(default_factory=dict)
    #: Requirements every one of whose citations landed on the `excluded`
    #: domain — Step 3's own figure, deliberately not folded into
    #: `derived_ambiguous`.
    all_excluded_requirements: int = 0
    discriminator_tiers: dict[int, int] = field(default_factory=dict)
    not_accounted_for: int | None = None
    #: `"40 of 512 shown"`, or None when coverage was never measured. The
    #: count comes from the coverage payload's own total and **never** from
    #: `len(uncovered_chunks)`, which the workflow caps at forty entries.
    coverage_rendering: str | None = None
    intra_run_collapse: int = 0
    index_present: bool = False
    index_sqlite_path: Path | None = None
    injection_flags: list[str] = field(default_factory=list)
    #: Every loud line ingest emitted, in order, so a caller that supplied no
    #: sink can still render them and `stats` can quote them.
    notices: list[str] = field(default_factory=list)
    refresh: RefreshResult | None = None
    embed: EmbedResult | None = None

    @property
    def complete(self) -> bool:
        """The `gr_run.complete` generated column, computed identically.

        NULL `not_accounted_for` means coverage was never measured and is
        **not** complete. NULL means never measured; zero means measured and
        nothing left over.
        """
        return self.not_accounted_for is not None and self.not_accounted_for == 0

    @property
    def vectors_degraded(self) -> bool:
        """True when some requirement did not reach `gr_statements`.

        The caller **exits zero** on this. A non-zero exit reads as "the
        ingest failed" and invites re-running the extraction, which is hours
        of model time to recover something that was never lost.
        """
        return self.embed is not None and self.embed.degraded


# ----------------------------------------------------------------------
# Reading the incoming rule object
# ----------------------------------------------------------------------


def unmapped_rule_keys(rule: Mapping[str, Any]) -> set[str]:
    """Keys of one incoming rule object that reach no declared destination.

    Step 3's completeness rule: every key of every ingested rule object must
    be mapped to a named column, **or** to a child-table row, **or** appear
    in `gr_fields.UNMAPPED_KEYS` as knowingly unpromoted. This function is
    that rule made computable, and it is what the completeness test asserts
    is empty.

    Note what it deliberately does **not** count as an escape hatch: every
    key is preserved in `gr.extractor_payload` verbatim, so a test phrased
    against the payload alone would be vacuous — it would pass for any key
    whatsoever. The payload is the lossless backstop; this function is the
    reviewable record of what was promoted.

    Args:
        rule: One rule object from the extractor's output.

    Returns:
        The keys reaching no column, no child row and no declared exemption.
        Empty on conforming input.
    """
    accounted = (
        set(EXTRACTOR_FIELD_MAP) | set(VERBATIM_KEYS) | CHILD_MAPPED_KEYS | UNMAPPED_KEYS
    )
    return {key for key in rule if key not in accounted}


def _text(rule: Mapping[str, Any], key: str) -> str | None:
    """Read one incoming text field, preserving `''` and absence separately.

    **`''` is not NULL and must not be normalized to it.** The extractor now
    always emits `assumptions`, sending `""` where the code assumes nothing:
    `""` means the agent considered assumptions and had none, NULL means the
    field never arrived. Collapsing the two is this plan's recurring defect
    class.
    """
    if key not in rule:
        return None
    value = rule[key]
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _fallback_statement(rule: Mapping[str, Any], rule_class: str | None) -> str:
    """The pattern-free statement fallback — a defensive default only.

    `gr.statement` is `NOT NULL` and that is load-bearing: four things
    downstream read the column (the validator, the FTS5 index, the
    `gr_statements` embedding, and the `statement = statement_extracted`
    equality that is the *sole* definition of "a human edited this"). Since
    Step 6a made `statement` a required extractor field this is no longer the
    common first-ingest path; it covers a schema-conforming rule that
    nonetheless arrives with an empty statement.

    Two properties are load-bearing. It **produces text only and never a
    `pattern` value**, so both dedupe keys, the `approved`-scoped `CHECK` and
    the approval gate are entirely unaffected and the honest NULL recording
    "the shape was undecided" survives. And Step 4's rule still applies on top
    of it: with `pattern` NULL the three `V-SLOT` checks stay undecidable and
    are emitted as not-evaluated.

    **The `[Subject]` source is an ambiguity the plan leaves open**, so it is
    resolved here and stated: the rule's own `name` (`RULES_SCHEMA` calls it a
    "Plain-English rule name", and it is required), falling back to
    `plainEnglish` and then to a neutral literal. Deliberately **not** one of
    `V-SLOT-02`'s four banned literals (`the system`, `the application`, `the
    software`, `the program`) — manufacturing a sentence that trips a check
    for a reason unrelated to the extraction would misdirect the reviewer.
    The manufactured sentence *will* trip the vagueness checks, which is the
    right outcome: these rows belong at the front of the review queue.
    """
    subject = (_text(rule, "name") or "").strip()
    if not subject:
        subject = (_text(rule, "plainEnglish") or "").strip()
    if not subject:
        subject = "This rule"
    predicate = (_text(rule, "then") or "").strip()
    if not predicate:
        predicate = (_text(rule, "plainEnglish") or "").strip()
    if not predicate:
        predicate = "be reviewed"
    return f"{subject} {_FALLBACK_KEYWORD.get(rule_class, 'must')} {predicate}"


def _structured_body(
    rule: Mapping[str, Any], offer_ordinal: int
) -> tuple[str | None, str | None, str | None]:
    """Validate the typed body on write and return what to store and to hash.

    **The pair is all-or-nothing.** A `structured_body` arriving without a
    `structured_body_type` is a *rejected row*, never a defaulted one,
    because the type is what selects the schema and a guessed type validates
    against the wrong one. A type without a body is refused for the mirror
    reason.

    The body is validated against the schema its type selects **on write**;
    a failure fails the ingest transaction naming the rule by
    `offer_ordinal`. `pydantic.ValidationError` is a subclass of
    `ValueError`, so one `except ValueError` covers a ragged
    `decision_table` and an unknown type alike.

    Returns:
        `(structured_body_json, structured_body_type, canonical_form)`. The
        canonical form is the **tier-1 `dedupe_key` discriminator**; the
        stored JSON is the body as it arrived.
    """
    body = rule.get("structuredBody")
    body_type = _text(rule, "structuredBodyType")
    if body is None and not body_type:
        return None, None, None
    if body is None:
        raise IngestError(
            offer_ordinal,
            "structuredBody",
            f"structuredBodyType {body_type!r} arrived with no structuredBody; "
            f"the pair is all-or-nothing, so this is a rejected row rather "
            f"than a defaulted one",
        )
    if not body_type:
        raise IngestError(
            offer_ordinal,
            "structuredBodyType",
            "structuredBody arrived with no structuredBodyType; the type is "
            "what selects the validation schema and a guessed type validates "
            "against the wrong one, so this is a rejected row rather than a "
            "defaulted one",
        )
    try:
        validated = validate_structured_body(body_type, body)
    except ValueError as exc:
        raise IngestError(
            offer_ordinal, "structuredBody", f"{body_type} body is invalid: {exc}"
        ) from exc
    return (
        json.dumps(body, ensure_ascii=False),
        body_type,
        canonical_structured_body(validated),
    )


# ----------------------------------------------------------------------
# Span-level content hashing
# ----------------------------------------------------------------------


def _file_lines(repo_root: Path, relative_path: str, cache: dict) -> list[str] | None:
    """This file's lines, read once per ingest. None when it cannot be read."""
    if relative_path in cache:
        return cache[relative_path]
    try:
        raw = (repo_root / relative_path).read_bytes()
    except OSError:
        lines = None
    else:
        lines = raw.decode("utf-8", errors="replace").splitlines()
    cache[relative_path] = lines
    return lines


def _span_content_hash(
    repo_root: Path,
    relative_path: str,
    start_line: int,
    end_line: int,
    cache: dict,
) -> str | None:
    """Hash exactly the cited lines — the **span** grain of `content_hash`.

    It cannot come from the extractor, which returns a `path:line-line` string
    and no source text, so the ingest path is what computes it: read the cited
    line range out of the working tree, normalize it, hash it.

    **When the file or the range cannot be read, return None and let the
    citation insert with a NULL `content_hash`.** Do not guess, and do not
    drop the citation. A range whose start is past the end of the file, or
    whose end is past it, "cannot be read" as specified — clamping would hash
    a range nobody cited and put a confident-looking value into a dedupe key.
    The one exception is `WHOLE_FILE_END_LINE`, which *means* "to the end".

    Returns:
        The `ch1:`-prefixed span hash, or None.
    """
    lines = _file_lines(repo_root, relative_path, cache)
    if lines is None:
        return None
    last = len(lines)
    end = last if end_line >= WHOLE_FILE_END_LINE else end_line
    if start_line < 1 or start_line > last or end < start_line or end > last:
        return None
    return content_hash("\n".join(lines[start_line - 1 : end]))


# ----------------------------------------------------------------------
# One rule
# ----------------------------------------------------------------------


@dataclass
class _Prepared:
    """One incoming rule turned into everything the merge needs to write."""

    offer_ordinal: int
    payload: str
    rule_class: str | None
    pattern: str | None
    #: The `VERBATIM_KEYS` columns, keyed by column name. Built from that
    #: constant rather than written out, so the constant is the one place the
    #: third write route is declared and cannot drift from what `_insert`
    #: actually writes.
    verbatim_columns: dict[str, Any]
    statement: str
    modality: str
    assumptions: str | None
    extractor_columns: dict[str, Any]
    citations: list[GRCitation]
    citation_anchors: list[list]
    scenarios: list[GRScenario]
    edge_cases: list[GREdgeCase]
    subject: str | None
    subject_provenance: str
    dedupe_key: str
    dedupe_key_anchor_only: str
    discriminator_tier: int
    all_citations_excluded: bool


def _prepare(
    rule: Mapping[str, Any],
    offer_ordinal: int,
    *,
    store: KnowledgeStore,
    repo_root: Path,
    resolver: AnchorResolver,
    line_cache: dict,
) -> _Prepared:
    """Turn one incoming rule object into the row and children it becomes.

    Every derivation here is deterministic and **no language model is on this
    path**: `legacylift_search` has no LLM dependency and ingest does not add
    one. What is derived is exactly what needs ingest-time context — the
    citation anchors and span hashes, `subject`/`subject_provenance`, both
    dedupe keys, the insert-only defaults and the timestamps.

    Raises:
        IngestError: Naming the rule by `offer_ordinal` and the field that
            failed.
    """
    # An unaccounted incoming key is deliberately NOT a hard failure here:
    # `extractor_payload` keeps it verbatim, and aborting a several-hundred-
    # rule ingest over a stray field would trade a real cost for no gain.
    # `unmapped_rule_keys` is the reviewable record, and the mapping
    # completeness test is where a `RULES_SCHEMA` addition is caught.
    verbatim_columns = {
        column: _text(rule, key) for key, column in VERBATIM_KEYS.items()
    }
    rule_class = verbatim_columns["rule_class"]
    pattern = verbatim_columns["pattern"]

    modality = _text(rule, "modality")
    if modality not in ("requirement", "expectation"):
        raise IngestError(
            offer_ordinal,
            "modality",
            f"{modality!r} is not one of ('requirement', 'expectation'); the "
            f"column is NOT NULL and CHECK-constrained, and ingest never "
            f"guesses a value into it",
        )

    statement = (_text(rule, "statement") or "").strip()
    if not statement:
        statement = _fallback_statement(rule, rule_class)

    assumptions = _text(rule, "assumptions")

    body_json, body_type, body_canonical = _structured_body(rule, offer_ordinal)

    # ---- citations, anchors and span hashes -------------------------------
    raw_source = rule.get("source")
    try:
        parsed = (
            parse_citation(raw_source, strict=True)
            if isinstance(raw_source, str) and raw_source.strip()
            else []
        )
    except ValueError as exc:
        raise IngestError(offer_ordinal, "source", str(exc)) from exc

    citations: list[GRCitation] = []
    citation_anchors: list[list] = []
    citation_domains: list[str] = []
    seen_tuples: set[tuple[str, int, int]] = set()
    for path, start, end in parsed:
        normalized = normalize_path(path)
        # The `gr_citation` uniqueness tuple is (gr_id, path, start, end), so
        # a rule citing the same range twice would fail its own insert. The
        # duplicate carries no information -- same anchor, same hash -- so it
        # is collapsed here rather than aborting a run over it.
        if (normalized, start, end) in seen_tuples:
            continue
        seen_tuples.add((normalized, start, end))
        resolution = resolver.resolve(normalized, start, end)
        span_hash = _span_content_hash(repo_root, normalized, start, end, line_cache)
        citations.append(
            GRCitation(
                gr_id="",  # assigned once the row has an identity
                anchor_key=resolution.primary,
                anchor_resolution=resolution.resolution,
                relative_path=normalized,
                start_line=start,
                end_line=end,
                content_hash=span_hash,
                provenance="extracted",
            )
        )
        citation_anchors.append(list(resolution.all))
        citation_domains.append(store.domain_for_file(normalized) or DOMAIN_UNASSIGNED)

    subject_derivation = derive_subject(
        citation_domains, statement, rule_class, pattern
    )

    keys = compute_dedupe_keys(
        [c.anchor_key for c in citations],
        rule_class,
        pattern,
        structured_body_canonical=body_canonical,
        citation_content_hashes=[c.content_hash for c in citations],
    )

    # ---- the extractor-owned column set, derived from the field map -------
    incoming = {
        "name": _text(rule, "name"),
        "category": _text(rule, "category"),
        "priority": _text(rule, "priority"),
        "suspectedDefect": _text(rule, "suspectedDefect"),
        "smeQuestion": _text(rule, "smeQuestion"),
        "parameters": _text(rule, "parameters"),
        "confidence": _text(rule, "confidence"),
        "plainEnglish": _text(rule, "plainEnglish"),
        "implementationNotes": _text(rule, "implementationNotes"),
        "structuredBody": body_json,
        "structuredBodyType": body_type,
        "statement": statement,
        "assumptions": assumptions,
        "modality": modality,
    }
    if set(incoming) != set(EXTRACTOR_FIELD_MAP):
        # A guard rather than a comment: this dict is the one place the field
        # map is *consumed*, so a `RULES_SCHEMA` key added to the map and not
        # read here would be silently dropped.
        raise IngestError(
            offer_ordinal,
            "EXTRACTOR_FIELD_MAP",
            f"ingest reads {sorted(incoming)} but the field map declares "
            f"{sorted(EXTRACTOR_FIELD_MAP)}; the two must agree exactly",
        )
    extractor_columns: dict[str, Any] = {}
    for key, columns in EXTRACTOR_FIELD_MAP.items():
        for column in columns:
            extractor_columns[column] = incoming[key]

    scenarios: list[GRScenario] = []
    scenario_fields = (
        _text(rule, "given"),
        _text(rule, "when"),
        _text(rule, "then"),
        _text(rule, "and"),
    )
    if any(v is not None for v in scenario_fields):
        scenarios.append(
            GRScenario(
                gr_id="",
                ordinal=0,
                given=scenario_fields[0],
                when=scenario_fields[1],
                then=scenario_fields[2],
                and_clause=scenario_fields[3],
                provenance="extracted",
            )
        )

    raw_edge_cases = rule.get("edgeCases") or []
    edge_cases = [
        GREdgeCase(gr_id="", ordinal=i, text=str(t), provenance="extracted")
        for i, t in enumerate(raw_edge_cases)
    ]

    return _Prepared(
        offer_ordinal=offer_ordinal,
        payload=json.dumps(rule, sort_keys=True, ensure_ascii=False),
        rule_class=rule_class,
        pattern=pattern,
        verbatim_columns=verbatim_columns,
        statement=statement,
        modality=modality,
        assumptions=assumptions,
        extractor_columns=extractor_columns,
        citations=citations,
        citation_anchors=citation_anchors,
        scenarios=scenarios,
        edge_cases=edge_cases,
        subject=subject_derivation.subject,
        subject_provenance=subject_derivation.subject_provenance,
        dedupe_key=keys.dedupe_key,
        dedupe_key_anchor_only=keys.dedupe_key_anchor_only,
        discriminator_tier=keys.discriminator.tier,
        all_citations_excluded=bool(citation_domains)
        and all(d == DOMAIN_EXCLUDED for d in citation_domains),
    )


# ----------------------------------------------------------------------
# The ingest itself
# ----------------------------------------------------------------------


def _resolve_index_store(
    index_sqlite_path: Path | None, notify: Callable[[str], None]
) -> tuple["SQLiteStore | None", bool]:
    """Open the Layer-0 index, loudly, or report that there is none.

    **`SQLiteStore.__init__` only records the path; `_connect()` opens lazily
    and SQLite creates the file on that first query.** So constructing a store
    against a missing `index.sqlite` materializes an empty database and then
    fails on `no such table: symbols`, and an empty index database beside an
    unindexed repository is indistinguishable from a real one on the next
    command. The guard is a plain `Path.exists()` **before** constructing
    anything, and acceptance requires that no `index.sqlite` is created.

    **The loud banner is printed at that check, naming the resolved index
    path**, because a mis-resolved path under the new output layout and a
    repository that genuinely was never indexed produce identical corpora and
    call for opposite fixes.

    A `None` store means every citation takes the file-level floor with
    `anchor_resolution = 'file'`, which is **correct rather than degraded**:
    the floor is index-independent by construction.
    """
    if index_sqlite_path is None:
        notify(
            "NO LAYER-0 INDEX PATH WAS SUPPLIED, so every citation will take "
            "the file-level anchor (anchor_resolution = 'file'). That is "
            "correct rather than degraded -- the file-level floor is total "
            "and index-independent -- but no citation in this run will "
            "resolve to a symbol, and stage two's structural half is the "
            "only recall left. Pass the resolved index path to get symbol "
            "anchors."
        )
        return None, False
    if not index_sqlite_path.exists():
        notify(
            f"NO LAYER-0 INDEX AT {index_sqlite_path} -- this repository has "
            f"never been indexed, or that path is wrong. Every citation in "
            f"this run will take the file-level anchor "
            f"(anchor_resolution = 'file'), which is correct rather than "
            f"degraded, but the corpus will be entirely 'file' and will look "
            f"exactly like a healthy one. Those two causes produce identical "
            f"corpora and call for opposite fixes, so check the path above "
            f"before concluding the repository is unindexed. No index.sqlite "
            f"has been created."
        )
        return None, False
    return open_index_store_if_present(index_sqlite_path), True


def _rules_of(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The offered rule objects, under either name the pipeline uses.

    Step 6 names the key `rules`; `extract-rules.js` really returns
    `confirmedRules`. Both are accepted rather than one being canonicalised
    at the call site, because a saved extractor-output JSON is the fixed input
    the headline merge criterion is stated against and it carries the second
    name.
    """
    for key in ("rules", "confirmedRules"):
        value = payload.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, Mapping)]
    return []


def _coverage_columns(
    payload: Mapping[str, Any], now: str
) -> tuple[float | None, int | None, str | None, str | None]:
    """Read the coverage payload into its four `gr_run` columns.

    **`not_accounted_for` comes from the coverage payload's own total, never
    from `len(uncovered_chunks)`** — that list is a display list the workflow
    caps at forty entries. A `coverage` of `null` (the shape the workflow
    really produces when `repoRoot` was omitted, no index existed, or the
    coverage command failed) and one carrying `skipped: true` (which the
    workflow normalizes away but the field map must still handle) both leave
    `not_accounted_for` **NULL**, and `complete` is then 0. **NULL means never
    measured; zero means measured and nothing left over** — store a zero for
    an unmeasured run and the gate passes most confidently in the one case it
    should stop.
    """
    coverage = payload.get("coverage")
    if not isinstance(coverage, Mapping) or coverage.get("skipped"):
        return None, None, None, None
    uncovered = coverage.get("uncovered")
    if not isinstance(uncovered, int):
        return None, None, None, None
    pct = coverage.get("pct")
    return (
        float(pct) if isinstance(pct, (int, float)) else None,
        uncovered,
        "extraction",
        now,
    )


def _coverage_rendering(payload: Mapping[str, Any], uncovered: int | None) -> str | None:
    """`"40 of 512 shown"` — the list length against the real total.

    Rendering the capped list's length as though it were the total is the
    defect this exists to prevent; naming both numbers is the fix.
    """
    if uncovered is None:
        return None
    coverage = payload.get("coverage")
    shown = 0
    if isinstance(coverage, Mapping):
        chunks = coverage.get("uncovered_chunks")
        if isinstance(chunks, list):
            shown = len(chunks)
    return f"{shown} of {uncovered} shown"


def ingest_extraction(
    store: KnowledgeStore,
    payload: Mapping[str, Any],
    repo_root: Path,
    *,
    index_sqlite_path: Path | None = None,
    embedder: "Embedder | None" = None,
    vector_base_dir: Path | None = None,
    on_notice: Callable[[str], None] | None = None,
    semantic_top_k: int = SEMANTIC_TOP_K,
    semantic_distance_max: float = SEMANTIC_DISTANCE_MAX,
) -> IngestResult:
    """Merge one extractor-output payload into the requirements store.

    **A callable function with no CLI dependency**, so Step 8's `requirements
    ingest` wires it rather than reimplementing it — and so the merge is
    testable without a command.

    Args:
        store: The knowledge store holding the GR tables. Must have no
            transaction open: this function owns one transaction for the whole
            run.
        payload: The extractor's decoded JSON output — `rules` (or
            `confirmedRules`), `rejectedRules`, `coverage`, `injectionFlags`
            and the run metadata.
        repo_root: The working tree the citations' paths are relative to. Not
            decoration: the staleness guard and the span-level `content_hash`
            both read it.
        index_sqlite_path: Where `index.sqlite` should be. **Checked with a
            plain `Path.exists()` before any store is constructed**, and
            `None` when absent — see `_resolve_index_store`. Acceptance
            requires that no `index.sqlite` is created.
        embedder: `None` is a **supported degraded success**: the rules still
            land, `EmbedResult.reason` names `requirements reindex-vectors`,
            and the caller exits zero. It also disables stage two's semantic
            half, whose structural half (range intersection) is unaffected.
        vector_base_dir: Overrides where `gr_statements` lives. Defaults to
            the directory holding `knowledge.sqlite`, which is the resolved
            **knowledge** directory — never an index directory, because
            `index --reset` rmtrees the index directory's collections
            wholesale.
        on_notice: Sink for the loud lines, called as they occur. `None`
            writes them to stderr, so a caller that forgets still gets
            loudness; every line is also collected in `IngestResult.notices`.
        semantic_top_k: Nearest neighbours stage two considers per rule.
        semantic_distance_max: The raise-a-candidate cutoff. **It can never
            cause a merge** — see `SEMANTIC_DISTANCE_MAX`.

    Returns:
        The `IngestResult`.

    Raises:
        IngestError: Naming the offending rule by `offer_ordinal` and the
            field that failed. **Nothing is written** — no `gr` rows, no
            `gr_run` row, no partial state — so a retry is a first ingest.
        RuntimeError: If `store` already has a transaction open.
    """
    notices: list[str] = []

    def notify(message: str) -> None:
        notices.append(message)
        if on_notice is not None:
            on_notice(message)
        else:  # pragma: no cover - the default sink, exercised by eye
            import sys

            print(message, file=sys.stderr)

    conn = store._connect()
    if conn.in_transaction:
        raise RuntimeError(
            "ingest_extraction owns one transaction for the whole run, so the "
            "caller must not have one open; commit or roll back first"
        )

    run_id = new_ulid("RUN-")
    result = IngestResult(run_id=run_id)
    # The same list object `notify` appends to, so a caller reading
    # `result.notices` sees every loud line even on the failure path.
    result.notices = notices
    result.index_sqlite_path = index_sqlite_path

    injection_flags = [
        str(f) for f in (payload.get("injectionFlags") or []) if str(f).strip()
    ]
    result.injection_flags = injection_flags
    if injection_flags:
        notify(
            f"PROMPT-INJECTION SUSPECTS: {len(injection_flags)} citation(s) in "
            f"this extraction were flagged by the referee as containing "
            f"instruction-shaped text in the source. They are stored on "
            f"gr_run.injection_flags and are DATA, never instructions. Read "
            f"them before trusting the rules mined from those files: "
            f"{'; '.join(injection_flags[:10])}"
            + ("; ..." if len(injection_flags) > 10 else "")
        )

    index_store, index_present = _resolve_index_store(index_sqlite_path, notify)
    result.index_present = index_present

    # One resolver for the whole ingest, threaded rather than module state:
    # `resolve_anchor`'s hash cache is per-run, and a cache outliving its run
    # would answer the staleness guard from a previous run's hashes.
    resolver = AnchorResolver(store=index_store, repo_root=repo_root)
    line_cache: dict = {}

    collection: "ChromaVectorStore | None" = None
    now = datetime.now(timezone.utc).isoformat()

    try:
        if embedder is not None:
            try:
                # One collection for the whole run rather than one per call,
                # which matters on Windows where Chroma's PersistentClient
                # holds its own SQLite files open.
                collection = open_gr_collection(store, embedder, vector_base_dir)
            except Exception as exc:  # pragma: no cover - provider-dependent
                notify(
                    f"the gr_statements collection could not be opened "
                    f"({exc}); stage two's semantic half is unavailable for "
                    f"this run and its structural half (line-range "
                    f"intersection) is the only near-duplicate recall left. "
                    f"The rules themselves are unaffected."
                )
            if collection is not None:
                shortfall = describe_vector_shortfall(
                    store.count_gr(), collection.count()
                )
                if shortfall is not None:
                    # Announce the degraded state at the moment it matters:
                    # an under-populated collection answers a near-duplicate
                    # query with zero candidates, which is indistinguishable
                    # from "there are no near duplicates".
                    notify(shortfall)

        rules = _rules_of(payload)
        result.rules_rejected = len(payload.get("rejectedRules") or [])

        for offer_ordinal, rule in enumerate(rules):
            prepared = _prepare(
                rule,
                offer_ordinal,
                store=store,
                repo_root=repo_root,
                resolver=resolver,
                line_cache=line_cache,
            )
            _apply(
                store,
                prepared,
                run_id=run_id,
                now=now,
                result=result,
                collection=collection,
                embedder=embedder,
                semantic_top_k=semantic_top_k,
                semantic_distance_max=semantic_distance_max,
            )

        result.rules_in = (
            result.rules_new + result.rules_merged + result.rules_candidate
        )
        result.rows_inserted = result.rules_new + result.rules_candidate

        pct, uncovered, source, measured_at = _coverage_columns(payload, now)
        result.not_accounted_for = uncovered
        result.coverage_rendering = _coverage_rendering(payload, uncovered)

        store.insert_gr_run(
            GRRun(
                run_id=run_id,
                system=_text(payload, "system"),
                started_at=_text(payload, "startedAt"),
                finished_at=now,
                rounds_run=_int(payload, "rounds", "roundsRun"),
                round_cap=_int(payload, "roundCap", "maxRounds"),
                stop_reason=_text(payload, "stopReason"),
                new_rules_in_final_round=_int(payload, "newRulesInFinalRound"),
                final_round_chunk_coverage_pct=pct,
                not_accounted_for=uncovered,
                coverage_source=source,
                coverage_measured_at=measured_at,
                injection_flags=(
                    json.dumps(injection_flags, ensure_ascii=False)
                    if injection_flags
                    else None
                ),
                rules_in=result.rules_in,
                rules_new=result.rules_new,
                rules_merged=result.rules_merged,
                rules_candidate=result.rules_candidate,
                rules_rejected=result.rules_rejected,
            )
        )

        # The SQL half of the refresh pair runs INSIDE this transaction (it
        # uses a SAVEPOINT, never a nested BEGIN), and once for the whole run
        # -- per record would mean several hundred separate validator runs.
        result.refresh = refresh_gr_derived_sql(
            store, result.gr_ids, index_store, repo_root
        )
        store.commit()
    except Exception:
        store.rollback()
        if index_store is not None:
            index_store.close()
        if collection is not None:
            collection.close()
        raise

    try:
        # The vector half runs AFTER the commit and is permitted to degrade.
        result.embed = refresh_gr_vectors(
            store, result.gr_ids, embedder, vector_base_dir, collection
        )
        if result.embed.reason:
            notify(result.embed.reason)
        result.intra_run_collapse = store.intra_run_collapse_count(run_id)
    finally:
        if index_store is not None:
            index_store.close()
        if collection is not None:
            collection.close()

    return result


def _int(payload: Mapping[str, Any], *keys: str) -> int | None:
    """The first of `keys` present in `payload` as an int, else None.

    Run metadata is recorded "where the payload carries them", and absence is
    normal rather than an error. **The reason changed on 2026-09-02 and the
    conclusion did not:** the workflow used to return `rounds` alone, and now
    emits `roundCap`, `stopReason` and `newRulesInFinalRound` too. Absence
    still has to be tolerated, because every run ingested before that change
    carries only `rounds` — and a NULL in those columns correctly means "never
    reported", which is exactly what those runs are.
    """
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _apply(
    store: KnowledgeStore,
    prepared: _Prepared,
    *,
    run_id: str,
    now: str,
    result: IngestResult,
    collection: "ChromaVectorStore | None",
    embedder: "Embedder | None",
    semantic_top_k: int,
    semantic_distance_max: float,
) -> None:
    """Run the two stages for one prepared rule and write what they decide."""
    existing = store.find_gr_by_dedupe_key(prepared.dedupe_key)
    if existing is not None:
        gr_id = existing.gr_id
        outcome = "merged"
        result.rules_merged += 1
        if not _merge(store, existing.gr_id, prepared, now=now):
            result.merges_with_no_change += 1
    else:
        gr_id = new_ulid("GR-")
        _insert(store, gr_id, prepared, run_id=run_id, now=now)
        anchor_hits = [
            g
            for g in store.gr_ids_by_anchor_only_key(prepared.dedupe_key_anchor_only)
            if g != gr_id
        ]
        if anchor_hits:
            # Stage one's fallback. The cited code drifted (or the extractor
            # reclassified the rule), so this is recognisably the same rule --
            # but it arrives as a HIGH-CONFIDENCE REVIEW CANDIDATE and an
            # extra row, never as a merge. Stage two is not run: there is
            # already a better candidate than it could find.
            outcome = "candidate"
            result.rules_candidate += 1
            for other in anchor_hits:
                _raise_candidate(store, other, gr_id, run_id, "drift", None, result)
        else:
            found = _stage_two(
                store,
                gr_id,
                prepared,
                run_id=run_id,
                result=result,
                collection=collection,
                embedder=embedder,
                semantic_top_k=semantic_top_k,
                semantic_distance_max=semantic_distance_max,
            )
            outcome = "candidate" if found else "new"
            if found:
                result.rules_candidate += 1
            else:
                result.rules_new += 1

    _write_children(store, gr_id, prepared, now=now, result=result)
    store.insert_gr_run_hit(
        GRRunHit(
            gr_id=gr_id,
            run_id=run_id,
            offer_ordinal=prepared.offer_ordinal,
            outcome=outcome,
        )
    )
    if gr_id not in result.gr_ids:
        result.gr_ids.append(gr_id)
    result.discriminator_tiers[prepared.discriminator_tier] = (
        result.discriminator_tiers.get(prepared.discriminator_tier, 0) + 1
    )
    result.subject_provenance_counts[prepared.subject_provenance] = (
        result.subject_provenance_counts.get(prepared.subject_provenance, 0) + 1
    )
    if prepared.all_citations_excluded:
        result.all_excluded_requirements += 1


def _insert(
    store: KnowledgeStore,
    gr_id: str,
    prepared: _Prepared,
    *,
    run_id: str,
    now: str,
) -> None:
    """Insert a fresh `draft` requirement.

    `state` is **always** `draft` and ingest writes nothing else, so an
    extractor can never approve its own output. `rule_class` and `pattern` are
    written verbatim **here and only here** — they are
    `HUMAN_WRITABLE_FIELDS`, so the merge never touches them; a human corrects
    an extractor's abstention through `set-field`.

    `INSERT_ONLY_DEFAULTS` (`disposition` = `captured`, `modality_confirmed` =
    false) belong to the human and are written only on this path: writing them
    on a merge would reset a reviewer's triage and erase an SME's modality
    confirmation on every re-extraction.
    """
    values: dict[str, Any] = {
        "gr_id": gr_id,
        "kind": "business_rule",
        "state": "draft",
        "subject": prepared.subject,
        "subject_provenance": prepared.subject_provenance,
        "dedupe_key": prepared.dedupe_key,
        "dedupe_key_anchor_only": prepared.dedupe_key_anchor_only,
        "extractor_payload": prepared.payload,
        "first_seen_run_id": run_id,
        "created_at": now,
        "updated_at": now,
    }
    values.update(prepared.verbatim_columns)
    values.update(INSERT_ONLY_DEFAULTS)
    values["modality_confirmed"] = int(bool(INSERT_ONLY_DEFAULTS["modality_confirmed"]))
    values.update(prepared.extractor_columns)
    store.insert_gr_row(values)


def _merge(
    store: KnowledgeStore,
    gr_id: str,
    prepared: _Prepared,
    *,
    now: str,
) -> bool:
    """Update an existing requirement, protecting every human write.

    The merge writes `EXTRACTOR_OWNED_FIELDS | SHADOWED_FIELDS` — the second
    conditionally — plus the four store-bookkeeping columns. For each shadowed
    field the incoming value goes to its `_extracted` shadow **always**, and
    to the live column **only if the live column equals its shadow on the
    stored row**; that equality, run through `gr_shadow_is_unedited` with
    SQLite `IS`, is precisely "no human has touched this". Where they differ
    the human's version stands and the new extractor value is still captured
    in the shadow, so a reviewer can see what the extractor would now say.

    **A write that changes no value must not bump `updated_at`.** Two headline
    claims are false without it: re-ingesting the same output *changes
    nothing*, and the second export is *byte-identical*. Get it wrong and the
    export diff shows all several hundred records as modified, which is the
    same as showing nothing.

    Returns:
        True when an `UPDATE` ran, False when every value already matched.
    """
    conn = store._connect()
    shadowed = get_shadowed_fields(conn)

    candidate: dict[str, Any] = {}
    for column, value in prepared.extractor_columns.items():
        if column in shadowed:
            # The live half of a shadowed pair: only where no human has
            # touched it. One shared helper, SQLite `IS`, all three fields.
            if store.gr_shadow_is_unedited(gr_id, column):
                candidate[column] = value
            continue
        if column in EXTRACTOR_OWNED_FIELDS:
            candidate[column] = value

    # Store bookkeeping, outside the ownership partition's field-mapped scope
    # but written by the merge. `extractor_payload` is refreshed and
    # participates in the comparison below -- a payload frozen at first insert
    # would defeat the one thing it is for.
    candidate["dedupe_key"] = prepared.dedupe_key
    candidate["dedupe_key_anchor_only"] = prepared.dedupe_key_anchor_only
    candidate["extractor_payload"] = prepared.payload

    columns = ", ".join(f'"{c}"' for c in candidate)
    stored = conn.execute(
        f"SELECT {columns} FROM gr WHERE gr_id = ?", (gr_id,)
    ).fetchone()
    if stored is not None and all(
        stored[column] == value for column, value in candidate.items()
    ):
        return False

    candidate["updated_at"] = now
    store.update_gr_row(gr_id, candidate)
    return True


def _write_children(
    store: KnowledgeStore,
    gr_id: str,
    prepared: _Prepared,
    *,
    now: str,
    result: IngestResult,
) -> None:
    """Write the citations, anchors, scenarios and edge cases.

    Citations insert on the uniqueness tuple `(gr_id, relative_path,
    start_line, end_line)`; the two child sets are refreshed per Step 3's
    rule, which preserves `provenance = 'human'` rows and makes a scenario
    absent from the second input actually disappear.
    """
    for citation, anchors in zip(prepared.citations, prepared.citation_anchors):
        stored = citation.model_copy(update={"gr_id": gr_id, "verified_at": now})
        citation_id, inserted = store.upsert_gr_citation(stored)
        store.replace_gr_citation_anchors(citation_id, anchors, stored.anchor_key)
        result.citations_seen += 1
        if inserted:
            result.citations_inserted += 1
        result.anchor_resolution_counts[citation.anchor_resolution] = (
            result.anchor_resolution_counts.get(citation.anchor_resolution, 0) + 1
        )
        if citation.anchor_resolution == "file":
            suffix = Path(citation.relative_path).suffix.lower() or "(none)"
            result.file_resolution_by_extension[suffix] = (
                result.file_resolution_by_extension.get(suffix, 0) + 1
            )

    if store.replace_gr_scenarios(
        gr_id, [s.model_copy(update={"gr_id": gr_id}) for s in prepared.scenarios]
    ):
        result.scenarios_rewritten += 1
    if store.replace_gr_edge_cases(
        gr_id, [e.model_copy(update={"gr_id": gr_id}) for e in prepared.edge_cases]
    ):
        result.edge_case_sets_rewritten += 1


def _raise_candidate(
    store: KnowledgeStore,
    gr_id_existing: str,
    gr_id_incoming: str,
    run_id: str,
    reason: str,
    similarity: float | None,
    result: IngestResult,
) -> None:
    """Record one suspected relationship. Never a merge.

    `similarity` is **NULL rather than zero** for a `drift` or
    `range_overlap` candidate: it was found structurally and has no similarity
    score at all, which must not be stored as `0.0` and read back as
    "semantically unrelated".
    """
    if store.record_gr_merge_candidate(
        GRMergeCandidate(
            gr_id_existing=gr_id_existing,
            gr_id_incoming=gr_id_incoming,
            run_id=run_id,
            similarity=similarity,
            reason=reason,
        )
    ):
        result.candidates_raised += 1
        result.candidate_reasons[reason] = result.candidate_reasons.get(reason, 0) + 1


def _stage_two(
    store: KnowledgeStore,
    gr_id: str,
    prepared: _Prepared,
    *,
    run_id: str,
    result: IngestResult,
    collection: "ChromaVectorStore | None",
    embedder: "Embedder | None",
    semantic_top_k: int,
    semantic_distance_max: float,
) -> bool:
    """Search for near-duplicates of a rule neither key recognised.

    Two searches, both of which only ever *surface* pairs:

    * **Semantic**, over the `gr_statements` collection. Unavailable when no
      embedder is configured, which is a supported degraded state the run
      already announced.
    * **Structural**, over `gr_citation`: existing requirements whose
      citations on the same file *intersect* this rule's ranges. Exact range
      equality is right for a key; intersection is right for a candidate
      search.

    **Neither merges. No similarity threshold auto-merges anything at any
    confidence**, because a false-same is invisible while a false-distinct is
    a duplicate row a reviewer can fix.

    Returns:
        True when at least one candidate was surfaced, which makes this
        rule's `gr_run_hit` outcome `candidate` rather than `new` — a row was
        inserted either way.
    """
    found = False

    if collection is not None and embedder is not None:
        try:
            hits = collection.query(
                embedder.embed_query(prepared.statement), semantic_top_k
            )
        except Exception:  # pragma: no cover - provider-dependent
            hits = []
        for hit in hits:
            if hit.id == gr_id or hit.distance > semantic_distance_max:
                continue
            _raise_candidate(
                store,
                hit.id,
                gr_id,
                run_id,
                "semantic",
                1.0 / (1.0 + float(hit.distance)),
                result,
            )
            found = True

    seen: set[str] = set()
    for citation in prepared.citations:
        for other in store.gr_ids_citing_overlapping_range(
            citation.relative_path, citation.start_line, citation.end_line, gr_id
        ):
            if other in seen:
                continue
            seen.add(other)
            _raise_candidate(
                store, other, gr_id, run_id, "range_overlap", None, result
            )
            found = True

    return found
