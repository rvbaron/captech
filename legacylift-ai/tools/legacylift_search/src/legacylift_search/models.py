"""Shared Pydantic data models for legacylift_search.

These types are the contract between modules implemented in subsequent
waves of the ExecPlan (`docs/exec-plans/active/semantic-code-search-graph-index.md`).
Field names and types match the milestone definitions exactly so that
parallel agents can implement modules against a stable interface.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator

from .identity import ENTITY_CLASSES


class TextRange(BaseModel):
    """Byte and line range for a region of source text. (Milestone 5)"""

    start_byte: int
    end_byte: int
    start_line: int
    end_line: int


class Symbol(BaseModel):
    """A named code entity extracted from a source file. (Milestone 5)

    ``entity_class`` is Milestone 1 Step 2 of
    `docs/exec-plans/active/reqs-to-data-store.md` (`NORMATIVE SPEC-3`
    §S3.1.2): the closed, coarse class (`identity.ENTITY_CLASSES`) that feeds
    `identity.anchor_key`. It is **declared by whichever extractor emits the
    symbol** — never derived from ``kind`` here or anywhere else, because the
    ``kind`` domain is not enumerable from this repository's source (framework
    extractors mint kinds from the client's own mapping files).

    **It is required, and deliberately has no default.** It briefly had
    ``"other"`` as one, for the single caller that rebuilt a `Symbol` from a
    database row with no such column; that caller now reads
    `symbols.entity_class` (`SQLiteStore.get_symbols_for_files`), so the
    default's only legitimate user is gone. Leaving it would have kept the
    exact hole this field exists to close: the *open* half of the ``kind``
    domain is classified at framework-extractor construction sites, which no
    data-file test can reach, so an omission there would have been silently
    absorbed as ``other`` — and promoting a kind out of ``other`` afterwards
    is an ``ak2:`` event, i.e. a corpus-wide re-key. Required makes an
    omission a validation error at the construction site instead.
    ``entity_class="other"`` remains the correct answer for a genuinely
    unknown kind; the point is that it must be *written*, not defaulted.

    **Adding, removing or renaming a value of `ENTITY_CLASSES`, or promoting a
    kind's declared class later, is an `ak2:` event** — it re-keys every
    `anchor_key` derived from it and is never an edit in place.
    """

    id: str
    language: str
    name: str
    qualified_name: str
    kind: str
    entity_class: str
    range: TextRange
    container: str | None = None
    signature: str | None = None

    @field_validator("entity_class")
    @classmethod
    def _check_entity_class(cls, v: str) -> str:
        if v not in ENTITY_CLASSES:
            raise ValueError(
                f"entity_class {v!r} is not one of the seven closed values "
                f"{sorted(ENTITY_CLASSES)}; see legacylift_search.identity"
            )
        return v


class SymbolRef(BaseModel):
    """A reference to a symbol (call, member access, import, etc.). (Milestone 5)"""

    id: str
    language: str
    name: str
    kind: str
    range: TextRange
    enclosing_symbol_id: str | None = None
    evidence: str


class SymbolFact(BaseModel):
    """An attribute-fact anchored on a definition symbol. (Milestones 23-25)

    Facts capture ``symbol -> predicate -> value`` assertions that have no
    target symbol (``http_method=GET``, ``requires_auth``, ``max_length=50``,
    column type/nullability, enum values), so they do not fit ``graph_edges``.
    They are extracted deterministically from AST nodes, so AST-derived facts
    carry ``confidence = 1.0``; lower confidence is reserved for heuristics.

    ``subject_symbol_id`` is the emitting symbol's exact ``.id`` string (reused
    verbatim, never recomputed) and is required — every fact is anchored on a
    definition symbol. The deterministic ``id`` keys on the ``object`` segment
    so multiple facts sharing subject/predicate/start_line (e.g. a single-line
    ``throws IOException, SQLException`` or ``enum { Open, Closed }``) do not
    collapse to one row.
    """

    id: str
    subject_symbol_id: str
    predicate: str
    object: str | None = None
    attributes: dict | None = None
    evidence: str
    confidence: float
    relative_path: str
    start_line: int
    language: str


class ExtractedFile(BaseModel):
    """All symbols and references extracted from a single file. (Milestone 5)"""

    symbols: list[Symbol]
    refs: list[SymbolRef]
    parse_errors: list[str]
    facts: list[SymbolFact] = []


class SourceFile(BaseModel):
    """A discovered source file with content metadata. (Milestone 3)"""

    absolute_path: Path
    repo_root: Path
    relative_path: str
    language: str
    size_bytes: int
    sha256: str
    mtime_ns: int


class CodeChunk(BaseModel):
    """A retrievable, contiguous slice of source code. (Milestone 6)"""

    id: str
    file_sha256: str
    relative_path: str
    language: str
    chunk_index: int
    chunk_kind: str
    symbol_id: str | None = None
    symbol_path: str | None = None
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    text: str
    text_sha256: str
    token_count_estimate: int


class GraphEdge(BaseModel):
    """A caller/callee or related code-graph edge. (Milestone 8)"""

    id: str
    caller_symbol_id: str | None
    callee_symbol_id: str | None
    callee_name: str
    edge_kind: str
    confidence: float
    evidence: str
    source_ref_id: str | None
    relative_path: str
    start_line: int


class SearchResult(BaseModel):
    """A ranked hybrid (vector + lexical) search hit. (Milestone 11)"""

    chunk_id: str
    score: float
    vector_rank: int | None
    lexical_rank: int | None
    relative_path: str
    language: str
    start_line: int
    end_line: int
    symbol_path: str | None
    snippet: str


class UncoveredChunk(BaseModel):
    """A chunk that no supplied citation claims. (Layer-0 retrieval, M3)"""

    chunk_id: str
    relative_path: str
    start_line: int
    end_line: int
    symbol: str | None = None


class DomainRecord(BaseModel):
    """A capability domain row from the durable knowledge store.

    (Milestone 2 of `domain-enhancements-plan.md`.) Mirrors the `domains`
    table in `knowledge.sqlite`. The reserved sentinel `domain_id =
    "unassigned"` is never represented as a `DomainRecord` — it is a
    `file_domains.domain` *value* only, synthesized as a display trailer by
    consumers (see `KnowledgeStore.list_domains`).
    """

    domain_id: str
    name: str
    description: str | None = None
    path_globs: list[str]
    assess_run_id: str | None = None
    display_order: int = 0


class DomainEdgeRecord(BaseModel):
    """An inter-domain dependency edge from the durable knowledge store.

    (Milestone 2 of `domain-enhancements-plan.md`.) Mirrors the
    `domain_edges` table; `kind` defaults to `""` (never `None`) to match
    the column's `NOT NULL DEFAULT ''`.
    """

    from_domain: str
    to_domain: str
    kind: str = ""
    evidence: str | None = None


class GRRecord(BaseModel):
    """One row of the `gr` table — a generated requirement. (M1 Step 3/4)

    Milestone 1 of `docs/exec-plans/active/reqs-to-data-store.md`. The field
    list mirrors `KnowledgeStore._migrate_gr_tables`' forty-two columns
    **exactly**, and `tests/test_gr_validator.py` asserts that against
    `PRAGMA table_info('gr')` rather than against this docstring — the DDL is
    the definitive column list, and an assertion computed from the thing it
    describes cannot drift from it.

    Step 3 deliberately deferred the record models to the steps that write
    them; Step 4 is the first of those, because `validate_statement` names
    this type and `Finding` in its signature.

    **The four JSON-bearing columns stay `str`, not parsed structures** —
    `structured_body`, `parameters`, `derived_from` and `extractor_payload`.
    They are TEXT in the schema, `extractor_payload` is the *verbatim*
    backstop whose whole value is that nothing reshapes it, and the ingest
    field map that decides how each is serialized is Step 6's. Parsing them
    here would make this model the place that decision lives, one step early.

    `modality_confirmed` is the one column typed as something other than its
    SQLite storage class: it is `INTEGER CHECK (… IN (0,1))` there and `bool`
    here, because it is a two-state flag and `pydantic` round-trips it.
    """

    gr_id: str
    kind: str
    name: str | None = None
    state: str = "draft"
    subject: str | None = None
    subject_provenance: str | None = None
    statement: str
    statement_extracted: str
    as_built: str | None = None
    rule_class: str | None = None
    pattern: str | None = None
    modality: str
    modality_extracted: str
    modality_confirmed: bool = False
    enforcement_level: str | None = None
    category: str | None = None
    priority: str | None = None
    confidence_extraction: str | None = None
    confidence_intent: str | None = None
    disposition: str | None = None
    structured_body: str | None = None
    structured_body_type: str | None = None
    implementation_notes: str | None = None
    parameters: str | None = None
    rationale: str | None = None
    fit_criterion: str | None = None
    assumptions: str | None = None
    assumptions_extracted: str | None = None
    sme_question: str | None = None
    suspected_defect: str | None = None
    derived_from: str | None = None
    superseded_by: str | None = None
    dedupe_key: str
    dedupe_key_anchor_only: str
    owner: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None
    extractor_payload: str
    first_seen_run_id: str | None = None
    created_at: str
    updated_at: str


class Finding(BaseModel):
    """One SPEC-1 validator finding against a requirement's `statement`.

    Milestone 1, Step 4 of `docs/exec-plans/active/reqs-to-data-store.md`.
    Mirrors the `gr_finding` table minus its `gr_id`, which the caller
    supplies — `validate_statement` validates one record and does not know
    where the row will land.

    ``span`` is the character offset range **within `statement`** that the
    finding points at, stored the way the column stores it: the literal
    `"start-end"`, or **`''` for a record-level finding — never `None`**.
    `span` is part of `gr_finding`'s `UNIQUE (gr_id, finding_id, span)` and
    SQLite treats NULLs as distinct, so a NULL span would let the same
    finding insert repeatedly.

    ``evaluated`` is **not a third severity value** and must never become
    one. `NORMATIVE SPEC-1` §S1.6 opens "Severity has exactly two values" and
    forbids re-severitying a check without amending SPEC-1, which is what
    makes Step 4's slot split an implementation note rather than an
    amendment. So `severity` keeps the severity the check *would* have
    carried and `evaluated = False` says the check could not be decided, with
    the reason in `message`.
    """

    finding_id: str
    severity: str
    span: str
    message: str
    evaluated: bool = True

    @field_validator("severity")
    @classmethod
    def _check_severity(cls, v: str) -> str:
        if v not in ("ERROR", "WARN"):
            raise ValueError(
                f"severity {v!r} is not one of the two SPEC-1 §S1.6 values "
                "('ERROR', 'WARN'); a third value would break the claim that "
                "the Step 4 slot split re-severities nothing"
            )
        return v


class GRCitation(BaseModel):
    """One row of `gr_citation` — a requirement's pointer at cited source.

    Milestone 1 Step 6a of `docs/exec-plans/active/reqs-to-data-store.md`.

    ``citation_id`` is a surrogate SQLite assigns on insert, so it is ``None``
    on a citation that has not been written yet; `gr_citation_anchor` hangs off
    it, which is why the table carries one at all rather than making every
    child repeat the four-column natural key.

    ``anchor_key`` is **never the empty string** and a validator enforces that
    here as well as in the DDL's `CHECK`. It is the value that silently
    collapses stage-one dedupe: with it, `dedupe_key_anchor_only` degenerates
    to the empty anchor joined to `rule_class` and `pattern`, identical for
    every rule in the corpus sharing a class and a pattern, and stage one
    auto-merges them on the first ingest. The file-level anchor is the total
    floor, so a real value always exists (Step 6a, `NORMATIVE SPEC-3` §S3.1.1).

    ``content_hash`` is the **span**-level grain (Step 1) and is nullable: a
    citation whose line range cannot be read inserts with NULL rather than
    being dropped or hashed over a guess. ``anchor_resolution`` beside it says
    which of the three things happened, and `'unresolved'` specifically means
    *the cited path is not in the working tree* — not a third tier beneath the
    file-level floor, which is total. A computed file-level anchor plus that
    label is how a stale citation stays visible instead of merely wrong.
    """

    citation_id: int | None = None
    gr_id: str
    anchor_key: str
    anchor_resolution: str
    relative_path: str
    start_line: int
    end_line: int
    content_hash: str | None = None
    verified_at: str | None = None
    provenance: str = "extracted"

    @field_validator("anchor_key")
    @classmethod
    def _check_anchor_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "anchor_key must never be the empty string: it is a tier-1 "
                "input to both dedupe keys, and '' makes every rule sharing a "
                "rule_class and pattern key identically (Step 6a). The "
                "file-level anchor is the floor -- use file_anchor_key()"
            )
        return v

    @field_validator("anchor_resolution")
    @classmethod
    def _check_anchor_resolution(cls, v: str) -> str:
        if v not in ("symbol", "file", "unresolved"):
            raise ValueError(
                f"anchor_resolution {v!r} is not one of ('symbol', 'file', "
                "'unresolved') (Step 6a)"
            )
        return v

    @field_validator("provenance")
    @classmethod
    def _check_provenance(cls, v: str) -> str:
        if v not in ("extracted", "repaired", "human"):
            raise ValueError(
                f"gr_citation.provenance {v!r} is not one of ('extracted', "
                "'repaired', 'human'). Note it is 'extracted', NOT "
                "'extractor' -- the ingest field map one table over calls the "
                "same idea by the other name"
            )
        return v


class GRCitationAnchor(BaseModel):
    """One row of `gr_citation_anchor` — the REST of a citation's anchors.

    Milestone 1 Step 3/6a. A citation spanning three sibling methods produces
    three rows here and exactly **one** `gr_citation.anchor_key` (the primary,
    chosen by Step 6a's deterministic rule). Two homes rather than one because
    the jobs pull in opposite directions: `gr_citation.anchor_key` must stay a
    single atomic value or the move-repair's equality lookup degrades to a
    substring match over 16-hex-char keys, which half-works silently; and this
    table must exist because "which symbols does this requirement touch?" is a
    first-class query one primary anchor cannot answer.

    ``is_primary`` marks the winner, which is recorded here **as well as** in
    `gr_citation.anchor_key` — the full set includes it.

    **This table is not an input to either dedupe key and must never become
    one.** Hashing the full set would re-key a rule whose own cited code never
    changed, the moment an unrelated sibling declaration was added inside its
    cited range. It is derived and rebuildable from the durable
    (path, start_line, end_line) triple.
    """

    citation_id: int
    anchor_key: str
    containment: str
    is_primary: bool = False

    @field_validator("anchor_key")
    @classmethod
    def _check_anchor_key(cls, v: str) -> str:
        if not v:
            raise ValueError("anchor_key must never be the empty string")
        return v

    @field_validator("containment")
    @classmethod
    def _check_containment(cls, v: str) -> str:
        if v not in ("contains", "intersects"):
            raise ValueError(
                f"containment {v!r} is not one of ('contains', 'intersects')"
            )
        return v


class AnchorHit(BaseModel):
    """One symbol a citation's line range lands on. (M1 Step 6a)

    Part of `AnchorResolution.all`, which becomes the `gr_citation_anchor`
    rows. ``containment`` is `'contains'` when the symbol's span encloses the
    citation's range and `'intersects'` when they merely overlap; the primary
    anchor is chosen from these by Step 6a's deterministic rule, and the full
    set is what answers "which symbols does this requirement touch?".

    **This set is not an input to either dedupe key and must never become
    one** — hashing it would re-key a rule whose own cited code never changed,
    the moment an unrelated sibling declaration appeared inside its range.
    """

    anchor_key: str
    containment: str

    @field_validator("anchor_key")
    @classmethod
    def _check_anchor_key(cls, v: str) -> str:
        if not v:
            raise ValueError("anchor_key must never be the empty string")
        return v

    @field_validator("containment")
    @classmethod
    def _check_containment(cls, v: str) -> str:
        if v not in ("contains", "intersects"):
            raise ValueError(
                f"containment {v!r} is not one of ('contains', 'intersects')"
            )
        return v


class AnchorResolution(BaseModel):
    """What `resolve_anchor` decided for one citation. (M1 Step 6a)

    ``primary`` is the single anchor that lands in `gr_citation.anchor_key`
    and is the **only** key input; ``all`` is one entry per containing or
    intersecting symbol, winner included, and becomes the
    `gr_citation_anchor` rows; ``resolution`` is the `anchor_resolution` value
    that produced the primary.

    ``primary`` is never the empty string — the file-level anchor is the floor
    — and when it *is* a file-level anchor, ``all`` holds that one entry.
    `'unresolved'` does not mean an absent anchor: it is the file-level anchor
    of a path that is not in the working tree, labelled so.

    The field is named ``all`` because the ExecPlan's Interfaces section names
    it that; it shadows the builtin only as an attribute, never in a scope
    where the builtin is reachable.
    """

    primary: str
    all: list[AnchorHit] = []
    resolution: str

    @field_validator("primary")
    @classmethod
    def _check_primary(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "primary must never be the empty string: the file-level "
                "anchor is the total floor (Step 6a, SPEC-3 §S3.1.1)"
            )
        return v

    @field_validator("resolution")
    @classmethod
    def _check_resolution(cls, v: str) -> str:
        if v not in ("symbol", "file", "unresolved"):
            raise ValueError(
                f"resolution {v!r} is not one of ('symbol', 'file', "
                "'unresolved')"
            )
        return v


class GRScenario(BaseModel):
    """One Given/When/Then, demoted to a child of a requirement. (M1 Step 3)

    Stored **verbatim**: G/W/T stops being the requirement (the normative
    record is `statement` plus `pattern`) and becomes a subordinate scenario.
    Three things depend on it — `given`/`when`/`then` are required fields of
    `RULES_SCHEMA` and the largest single volume of extracted content ingest
    would otherwise drop; the within-run old-shape-versus-new comparison reads
    both shapes off the same rule; and the completeness test asserts
    `gr_scenario` holds the G/W/T of every ingested rule.

    ``provenance`` is `'extracted'` for everything Milestone 1 writes. The
    merge refreshes the `'extracted'` set and leaves `'human'` rows untouched,
    which is why the value sits in the `UNIQUE (gr_id, provenance, ordinal)`
    tuple rather than being assumed.
    """

    scenario_id: int | None = None
    gr_id: str
    ordinal: int
    given: str | None = None
    when: str | None = None
    then: str | None = None
    and_clause: str | None = None
    provenance: str = "extracted"

    @field_validator("provenance")
    @classmethod
    def _check_provenance(cls, v: str) -> str:
        if v not in ("extracted", "human"):
            raise ValueError(
                f"gr_scenario.provenance {v!r} is not one of ('extracted', "
                "'human')"
            )
        return v


class GREdgeCase(BaseModel):
    """One entry of the extractor's `edgeCases`. (M1 Step 3)

    Deliberately the same shape as `GRScenario`, `provenance` included even
    though Milestone 1 writes only `'extracted'`: the two have identical
    lifecycles, are refreshed by the same merge rule, and a Milestone 4 that
    lets a reviewer add an edge case must not have to migrate a table to do it.
    """

    edge_case_id: int | None = None
    gr_id: str
    ordinal: int
    text: str
    provenance: str = "extracted"

    @field_validator("provenance")
    @classmethod
    def _check_provenance(cls, v: str) -> str:
        if v not in ("extracted", "human"):
            raise ValueError(
                f"gr_edge_case.provenance {v!r} is not one of ('extracted', "
                "'human')"
            )
        return v


class GRMergeCandidate(BaseModel):
    """One stage-two review candidate pair. (M1 Step 6)

    **Stage two never merges on its own** — no similarity threshold
    auto-merges anything, at any confidence. The asymmetry is deliberate: a
    false-distinct (a duplicate row) is visible and a reviewer merges it, so it
    is recoverable, while a false-same is invisible and a real rule silently
    never enters the corpus.

    ``similarity`` is nullable and **NULL is not zero**: a `'range_overlap'`
    or `'drift'` candidate was found by line-range intersection and has no
    similarity score at all, which must not be stored as `0.0` and read back
    as "semantically unrelated" (the plan's recurring absent-versus-real rule).

    ``run_id`` is recorded but is deliberately **not** part of the primary
    key. The pair is the identity, so surfacing the same pair on a later run
    updates one row rather than raising it again — and a resolution a reviewer
    has already recorded survives the next ingest.
    """

    gr_id_existing: str
    gr_id_incoming: str
    run_id: str | None = None
    similarity: float | None = None
    reason: str
    resolution: str = "unresolved"
    resolved_at: str | None = None

    @field_validator("reason")
    @classmethod
    def _check_reason(cls, v: str) -> str:
        if v not in ("semantic", "range_overlap", "drift"):
            raise ValueError(
                f"reason {v!r} is not one of ('semantic', 'range_overlap', "
                "'drift')"
            )
        return v

    @field_validator("resolution")
    @classmethod
    def _check_resolution(cls, v: str) -> str:
        if v not in ("merged", "distinct", "unresolved"):
            raise ValueError(
                f"resolution {v!r} is not one of ('merged', 'distinct', "
                "'unresolved')"
            )
        return v


class GRRunHit(BaseModel):
    """One OFFERED rule's outcome in one run. (M1 Step 3/6)

    One row means one *offered* rule, **not** one requirement: a single run can
    offer two rules that land on the same `gr_id`, because the extractor's own
    in-run dedupe keys on `path::lowercased-name` and so collapses same-*name*
    rules rather than same-*lines* rules. Two such rules can then collide on
    `dedupe_key`.

    Hence ``hit_id``, a surrogate, and **no uniqueness on (gr_id, run_id)** —
    two rules that both merge produce two rows identical in every natural
    column, and a natural key would refuse one, under-count `rules_in`, and
    fail the run-count identity for a reason that is not a defect in the merge.

    ``offer_ordinal`` is the rule's index within that run's input array. It is
    what traces a hit back to the specific offered object, what every ingest
    error message must name, and — counted on a first ingest into an empty
    store — **is** Step 10's mandatory intra-run collapse rate.

    Outcomes are defined so every offered rule produces exactly one row per
    run: `'new'` (neither key matched; a row was inserted), `'merged'` (exact
    `dedupe_key` match; the existing row was updated), `'candidate'` (matched
    `dedupe_key_anchor_only`, or stage two surfaced it — **a row was ALSO
    inserted**). So `rules_new` is *not* the number of rows inserted;
    `rules_new + rules_candidate` is.
    """

    hit_id: int | None = None
    gr_id: str
    run_id: str
    offer_ordinal: int
    outcome: str

    @field_validator("outcome")
    @classmethod
    def _check_outcome(cls, v: str) -> str:
        if v not in ("new", "merged", "candidate"):
            raise ValueError(
                f"outcome {v!r} is not one of ('new', 'merged', 'candidate')"
            )
        return v


class DataflowEntry(BaseModel):
    """One `reads[]`/`writes[]` entry for a requirement. (M1 Step 7)

    **`gr_dataflow` has no writer in Milestone 1 and the table ships empty**,
    for two independent reasons: the *computed* path is gated on Milestone 26
    of `docs/exec-plans/active/semantic-code-search-graph-index.md` (until it
    lands, `uses_table` edges emit SQL table *aliases* as datastore names and
    produce confident self-referencing edges), and the `llm_inferred` fallback
    has no extractor source until that field is added alongside the same work.
    `requirements stats` therefore reports the block **in words** and never as
    a rate — a percentage over an empty set is the defect, not the expected
    value.

    ``column`` is `''` rather than NULL for table-grain entries, matching the
    DDL's `NOT NULL DEFAULT ''`. That is the same reasoning as
    `Finding.span`: it sits in `UNIQUE (gr_id, direction, datastore, column)`
    and SQLite treats NULLs as distinct, so a NULL would let the same entry
    insert repeatedly. `''` means *this entry is about the whole datastore*,
    which is a real statement rather than an absent one.

    ``provenance`` `'llm_inferred'` fires on graph **silence**, never on graph
    disagreement, and inferred entries must never join a computed total.
    """

    gr_id: str
    direction: str
    datastore: str
    column: str = ""
    provenance: str
    explanation: str | None = None

    @field_validator("direction")
    @classmethod
    def _check_direction(cls, v: str) -> str:
        if v not in ("reads", "writes"):
            raise ValueError(
                f"direction {v!r} is not one of ('reads', 'writes')"
            )
        return v

    @field_validator("provenance")
    @classmethod
    def _check_provenance(cls, v: str) -> str:
        if v not in ("computed", "llm_inferred"):
            raise ValueError(
                f"gr_dataflow.provenance {v!r} is not one of ('computed', "
                "'llm_inferred')"
            )
        return v


class GRRun(BaseModel):
    """Per-extraction-run metadata — one row of `gr_run`. (M1 Step 3/10)

    **A failed ingest leaves no `gr_run` row at all** (Step 6): the whole
    SQLite half is one transaction, so a retry is a first ingest needing no
    cleanup, no resume flag and no deduplication of run metadata.

    ``final_round_chunk_coverage_pct`` is named for what the extractor
    actually returns — the FINAL ROUND's chunk coverage, not the run's union.
    Do not present it as whole-run coverage.

    ``not_accounted_for`` is nullable and **NULL is not zero**: NULL means
    coverage was never measured, zero means it was measured and nothing was
    left over. That distinction is the completeness gate — `complete` is 1 only
    when the value is non-NULL *and* zero — and collapsing it is the exact
    defect that let the gate pass on an unmeasured corpus. Take the count from
    the coverage payload's own total, never from `len(uncovered_chunks)`, which
    is a display list capped at forty entries.

    ``complete`` is a **generated VIRTUAL column** in SQLite, so
    `PRAGMA table_info('gr_run')` omits it — use `PRAGMA table_xinfo`. It is
    exposed here as a read-only property computing the identical expression
    rather than as a field, so nothing can set it out of step with
    ``not_accounted_for``.

    ``gate_excluded`` plus ``gate_excluded_reason`` is `retire-run`'s exit
    from the gate; ``coverage_source``/``coverage_measured_at`` is
    `set-run-coverage`'s. They are two commands and two column pairs on
    purpose: one records a measurement that was actually taken, the other a
    human's judgement that a run no longer counts, and the audit question is
    "why did this stop blocking?".
    """

    run_id: str
    system: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    rounds_run: int | None = None
    round_cap: int | None = None
    stop_reason: str | None = None
    new_rules_in_final_round: int | None = None
    final_round_chunk_coverage_pct: float | None = None
    not_accounted_for: int | None = None
    coverage_source: str | None = None
    coverage_measured_at: str | None = None
    gate_excluded: bool = False
    gate_excluded_reason: str | None = None
    injection_flags: str | None = None
    rules_in: int | None = None
    rules_new: int | None = None
    rules_merged: int | None = None
    rules_candidate: int | None = None
    rules_rejected: int | None = None

    @field_validator("stop_reason")
    @classmethod
    def _check_stop_reason(cls, v: str | None) -> str | None:
        if v is not None and v not in ("dry", "round_cap", "budget_exhausted"):
            raise ValueError(
                f"stop_reason {v!r} is not NULL and not one of ('dry', "
                "'round_cap', 'budget_exhausted')"
            )
        return v

    @field_validator("coverage_source")
    @classmethod
    def _check_coverage_source(cls, v: str | None) -> str | None:
        if v is not None and v not in ("extraction", "remeasured"):
            raise ValueError(
                f"coverage_source {v!r} is not NULL and not one of "
                "('extraction', 'remeasured')"
            )
        return v

    @model_validator(mode="after")
    def _check_gate_exclusion(self) -> GRRun:
        """Mirror the DDL's CHECK so it fails at construction, not on insert.

        Retiring a run is a human judgement and is logged as one, so the
        reason is required rather than optional: a NULL reason has no answer
        to the audit question the column exists for.
        """
        if self.gate_excluded and not (self.gate_excluded_reason or "").strip():
            raise ValueError(
                "gate_excluded requires a non-empty gate_excluded_reason "
                "(retire-run's --reason): the audit question is 'why did this "
                "run stop blocking the gate?'"
            )
        return self

    @property
    def complete(self) -> bool:
        """The `complete` generated column, computed identically.

        A NULL `not_accounted_for` means coverage was never measured and is
        **not** complete — that is the whole point of the column.
        """
        return self.not_accounted_for is not None and self.not_accounted_for == 0


class RefreshResult(BaseModel):
    """What `gr_refresh.refresh_gr_derived_sql` did — the SQL half. (M1 Step 5)

    Milestone 1 Step 5 of `docs/exec-plans/active/reqs-to-data-store.md`.
    Carries what `requirements stats` and the ingest banner must be able to
    report, and one thing beyond that which this plan's recurring
    absent-versus-real rule requires:

    ``leaked_terms_available`` is **False when no index was reachable**, under
    which `V-STY-03` ran on its morphological fallback alone. That is a
    supported state, not an error — but it is not the shipped check either, so
    a store cannot be allowed to present "no leakage found" and "leakage was
    never looked for" the same way. `stats` says which one it is.

    ``forgotten`` counts `gr_id`s that had no `gr` row: their FTS text was
    deleted rather than rewritten. Non-zero is normal only when a requirement
    was deleted between the caller's list and this call.
    """

    refreshed: int = 0
    findings_written: int = 0
    forgotten: int = 0
    leaked_terms_available: bool = False
    leaked_term_count: int = 0


class EmbedResult(BaseModel):
    """What `gr_refresh.refresh_gr_vectors` did — the vector half. (M1 Step 5)

    Milestone 1 Step 5. The vector half is the one permitted to degrade: the
    rules are already committed by the time it runs, so a missing embedder, an
    unreachable provider or a dimension mismatch must leave the store correct
    and merely under-populated.

    ``reason`` is therefore load-bearing rather than decorative. It is
    ``None`` **only** when nothing was skipped; whenever ``skipped`` is
    non-zero it holds the words the CLI prints, and those words name
    `requirements reindex-vectors` as the recovery. An empty reason beside a
    non-zero skip count would be the degradation that does not announce
    itself — the exact failure Step 5's shortfall check exists to catch one
    layer out.
    """

    embedded: int = 0
    skipped: int = 0
    deleted: int = 0
    reason: str | None = None

    @property
    def degraded(self) -> bool:
        """True when some requirement did not reach the collection."""
        return self.skipped > 0


class CoverageResult(BaseModel):
    """Chunk-level coverage of the indexed chunk inventory against a set of
    path:start-end citations. (Layer-0 retrieval, M3)

    A chunk is "claimed" when some citation cites the same file and overlaps
    its line range; otherwise it is "uncovered". ``uncovered_chunks`` lists the
    highest-value uncovered chunks (largest line span first) up to a caller
    limit, so a caller can target the biggest blind spots next.
    """

    total: int
    claimed: int
    uncovered: int
    pct: float
    uncovered_chunks: list[UncoveredChunk]


__all__ = [
    "TextRange",
    "Symbol",
    "SymbolRef",
    "SymbolFact",
    "ExtractedFile",
    "SourceFile",
    "CodeChunk",
    "GraphEdge",
    "SearchResult",
    "UncoveredChunk",
    "CoverageResult",
    "DomainRecord",
    "DomainEdgeRecord",
    "GRRecord",
    "GRCitation",
    "GRCitationAnchor",
    "AnchorHit",
    "AnchorResolution",
    "GRScenario",
    "GREdgeCase",
    "GRMergeCandidate",
    "GRRunHit",
    "DataflowEntry",
    "GRRun",
    "Finding",
    "RefreshResult",
    "EmbedResult",
]
