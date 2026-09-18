"""Durable knowledge store: capability-domain data that survives `--reset`.

Milestones 1-2 of the ExecPlan
(`docs/exec-plans/pending/domain-enhancements-plan.md`). This module
introduces a second SQLite database, separate from the code-search
`index.sqlite`, to hold authored domain data (domain names, descriptions,
path globs, inter-domain edges, per-file domain assignments). Unlike the
code-search index, this database is never deleted by `index --reset` — it
lives outside the gitignored index directory and is the durable
"knowledge" half of the tool.

Milestone 2 adds the three domain tables (`domains`, `domain_edges`,
`file_domains`) and a read/write query API over them. The reserved
sentinel `domain_id = "unassigned"` is a `file_domains.domain` *value*
only — it is never inserted as a `domains`-table row, so `list_domains()`
never returns it (issues #28/#30 of the plan's design review).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from legacylift_search.migrations import (
    KNOWLEDGE_MIGRATIONS,
    run_migrations,
    stamp_fresh_database,
    was_database_empty,
)
from legacylift_search.models import (
    DataflowEntry,
    DomainEdgeRecord,
    DomainRecord,
    Finding,
    GRCitation,
    GREdgeCase,
    GRMergeCandidate,
    GRRecord,
    GRRun,
    GRRunHit,
    GRScenario,
)

#: The `gr_run` columns a reader may hydrate a `GRRun` from, taken from the
#: model rather than typed out. **`complete` is deliberately absent**, and
#: taking it from the model is what keeps it absent: it is a generated VIRTUAL
#: column that `SELECT *` returns and `PRAGMA table_info` hides, and `GRRun`
#: exposes it as a read-only property computing the same expression -- so a
#: `SELECT *` hydration would hand pydantic a value for a name that is not a
#: field, and the distinction that NULL `not_accounted_for` is "never
#: measured" would depend on which of the two paths a caller happened to read.
_GR_RUN_COLUMNS: tuple[str, ...] = tuple(GRRun.model_fields.keys())

#: Columns `count_gr_by` will group on. A whitelist because the name is
#: interpolated into SQL, and because a typo would otherwise return an empty
#: grouping that reads exactly like an empty corpus.
_GR_GROUPABLE_COLUMNS: frozenset[str] = frozenset(
    {
        "state",
        "kind",
        "category",
        "disposition",
        "subject_provenance",
        "priority",
        "rule_class",
        "pattern",
        "modality",
        "confidence_extraction",
        "confidence_intent",
        "enforcement_level",
    }
)

#: The default set `gr_field_fill_counts` reports on: the nine
#: `HUMAN_WRITABLE_FIELDS` plus the three shadowed ones, i.e. exactly what
#: `set-field` accepts, which is exactly the set whose fill rate is review
#: progress. Declared here as a list so the order `stats` prints is stable;
#: membership is asserted against `gr_fields.set_field_accepted_fields` by a
#: test rather than trusted.
GR_FILL_FIELDS: tuple[str, ...] = (
    "rule_class",
    "pattern",
    "enforcement_level",
    "confidence_intent",
    "disposition",
    "modality_confirmed",
    "rationale",
    "fit_criterion",
    "owner",
    "statement",
    "assumptions",
    "modality",
)

#: The reserved `file_domains.domain` value meaning "declared out of scope".
#: Duplicated from `gr_subject.DOMAIN_EXCLUDED` **only** as the SQL literal
#: this module's own query needs; `gr_subject` remains the owner of the
#: sentinel's meaning and a test asserts the two agree.
_DOMAIN_EXCLUDED_SQL: str = "excluded"


class KnowledgeStore:
    """SQLite persistence for durable, authored knowledge (capability domains).

    Mirrors `SQLiteStore`'s WAL/foreign-key pragma setup and idempotent
    `CREATE TABLE IF NOT EXISTS` migration style (`store.py`'s `migrate()`),
    but — deliberately, unlike `SQLiteStore` — runs that migration from
    `__init__` so that merely constructing a `KnowledgeStore` creates and
    migrates the durable file. `SQLiteStore.migrate()` is instead invoked
    explicitly by its callers.

    Has no read-only mode: construction always creates the parent directory
    and the SQLite file if they do not already exist. Read-only consumers
    (e.g. `domains`, `stats`, `validate`) must probe `sqlite_path.exists()`
    with a plain `Path.exists()` *before* constructing this class, or they
    will silently materialize an empty knowledge database as a side effect.
    """

    def __init__(self, sqlite_path: Path) -> None:
        """Open (creating if needed) the knowledge database at sqlite_path.

        Creates the parent directory (`legacylift-docs/knowledge/` is not
        committed to git — its only content is this gitignored database — so
        it must be created on demand at runtime), opens the connection, sets
        the WAL/foreign-key pragmas, runs `migrate()`, and then runs the
        versioned migration runner over `KNOWLEDGE_MIGRATIONS`.

        Args:
            sqlite_path: Path to the SQLite file (will be created if missing).
        """
        self.sqlite_path = sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: sqlite3.Connection | None = None
        conn = self._connect()
        # Milestone 0: snapshot emptiness BEFORE migrate() runs. Taken after
        # it, this would always see tables and stamp nothing, leaving every
        # fresh knowledge.sqlite at version 0.
        was_empty = was_database_empty(conn)
        self.migrate()
        # A database migrate() just created from nothing already carries
        # every column any migration would add, so stamp it at the highest
        # known version; an existing older one is brought forward by the
        # runner instead.
        if was_empty:
            stamp_fresh_database(conn, KNOWLEDGE_MIGRATIONS)
        run_migrations(conn, KNOWLEDGE_MIGRATIONS)

    def _connect(self) -> sqlite3.Connection:
        """Open or return the existing connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.sqlite_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def migrate(self) -> None:
        """Create all tables if they don't exist.

        Sets PRAGMA journal_mode=WAL and PRAGMA foreign_keys=ON (copied from
        `SQLiteStore.migrate`, `store.py:180-181` — NOT from `__init__`,
        which does not set them).
        """
        conn = self._connect()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # domains: authored (assess-emitted) domain catalog. The reserved
        # sentinel domain_id "unassigned" is NEVER inserted here (issues
        # #28/#30) — it only ever appears as a file_domains.domain value.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS domains (
              domain_id     TEXT PRIMARY KEY,
              name          TEXT NOT NULL,
              description   TEXT,
              path_globs    TEXT NOT NULL,
              assess_run_id TEXT,
              display_order INTEGER NOT NULL DEFAULT 0
            )
        """)

        # domain_edges: authored inter-domain dependency edges. `kind`
        # defaults to '' (never NULL) so a NULL PK column can't let
        # duplicate edges slip past INSERT OR REPLACE.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_edges (
              from_domain TEXT NOT NULL,
              to_domain   TEXT NOT NULL,
              kind        TEXT NOT NULL DEFAULT '',
              evidence    TEXT,
              PRIMARY KEY (from_domain, to_domain, kind)
            )
        """)

        # file_domains: one primary domain per file, keyed on relative_path.
        # `domain` may be the reserved value "unassigned". `source` is a
        # strict two-value enum: 'glob' (including unmatched files, which
        # carry domain='unassigned') or 'manual' (hand-authored, never
        # overwritten by glob resolution).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_domains (
              relative_path TEXT PRIMARY KEY,
              domain        TEXT NOT NULL,
              source        TEXT NOT NULL CHECK (source IN ('glob','manual')),
              assess_run_id TEXT,
              confidence    REAL NOT NULL DEFAULT 1.0
            )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_file_domains_domain ON file_domains(domain)"
        )

        # domain_exclusions: authored "not a business capability" globs (the
        # excluded-by-design tier). A file matching one of these, and NO
        # domain glob, is written to file_domains as the reserved
        # domain='excluded' value (source='glob') instead of 'unassigned' —
        # so it drops out of the coverage denominator and never triggers the
        # "re-run assess" gap hint. Like the `domains` catalog, this is a
        # replace-all authored set re-ingested on every `tag-domains` run.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_exclusions (
              pattern TEXT PRIMARY KEY
            )
        """)

        self._migrate_gr_tables(conn)

        conn.commit()

    # ------------------------------------------------------------------
    # The GR (generated requirement) tables (Milestone 1, Step 3)
    # ------------------------------------------------------------------

    def _migrate_gr_tables(self, conn: sqlite3.Connection) -> None:
        """Create the eleven GR tables if they do not exist.

        Milestone 1, Step 3 of `docs/exec-plans/active/reqs-to-data-store.md`.
        Read that step before changing any constraint here: nearly every
        `CHECK`, `UNIQUE` and nullability below closes a specific, named
        defect, and several of them look like they could be tightened or
        dropped when they cannot.

        **Why this is in `migrate()` and not in `KNOWLEDGE_MIGRATIONS`.**
        Milestone 0 split the contract: `migrate()` brings a missing or empty
        database up to the current baseline, and `run_migrations()` brings an
        existing older one forward. Adding a *table* needs only the first,
        because `migrate()` uses `CREATE TABLE IF NOT EXISTS` and
        `KnowledgeStore.__init__` runs it on **every** open -- so an existing
        `knowledge.sqlite` already carrying domain rows gains these eleven
        tables the next time anything touches it, with no version bump. A
        no-op version 2 would add a stamp and no behaviour. The first GR
        *column* addition is what needs a migration entry.

        **These tables hold human judgment**, which is why they are in this
        database rather than `index.sqlite`: `index --reset` deletes that one.

        Args:
            conn: The open connection, already carrying the WAL and
                foreign-key pragmas set by `migrate()`.
        """
        # ------------------------------------------------------------------
        # gr -- the central table, forty-two columns
        # ------------------------------------------------------------------
        #
        # The column count is load-bearing: Step 6's four-way ownership
        # partition (14 extractor-owned / 3 shadowed / 9 human-writable /
        # 16 store-owned) is asserted against `PRAGMA table_info('gr')`, so a
        # column added here without being classified there fails that test.
        # That is the point of the test; do not add a column casually.
        #
        # `gr_id` is an immutable surrogate (`identity.new_ulid("GR-")`) and
        # is deliberately NOT derived from content: a human edits a
        # requirement's wording during review, and content-derived identity
        # would mint a new requirement and destroy the sign-off.
        #
        # Nullability notes that are not free choices:
        #   * `statement`, `statement_extracted`, `modality` and
        #     `modality_extracted` are NOT NULL because the merge's
        #     "has a human edited this" test is `live IS shadow`, and SQLite's
        #     `=` over two NULLs yields NULL rather than true -- under which
        #     every statement-less row reads as human-edited and the merge
        #     stops updating it, silently and permanently.
        #   * `assumptions`/`assumptions_extracted` are the deliberate
        #     exception and ARE nullable, because assumptions are genuinely
        #     absent on many rules. That is exactly why the shared edited-test
        #     helper must use `IS` rather than `=` (Step 6).
        #   * `subject` is nullable: NULL means "no `[Subject]` slot could be
        #     located", which is this plan's absent-versus-real rule. Do not
        #     substitute a placeholder, and never one of `V-SLOT-02`'s four
        #     literals (`the system`, `the application`, `the software`,
        #     `the program`).
        #   * `pattern` is nullable, which is a deliberate departure from a
        #     literal reading of `NORMATIVE SPEC-1` S1.4 -- see the two CHECKs
        #     below and Step 3's discussion of why a flat NOT NULL makes a bad
        #     extraction unstorable, when nothing may gate `draft`.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr (
              -- `NOT NULL` is not redundant beside `PRIMARY KEY` here, and
              -- leaving it off is a real hole rather than a style choice. In a
              -- SQLite rowid table a PRIMARY KEY column that is not
              -- `INTEGER PRIMARY KEY` **admits NULL**, and the unique index
              -- treats NULLs as distinct -- so `gr_id TEXT PRIMARY KEY` alone
              -- accepts two keyless rows, in the one column this plan calls
              -- the immutable surrogate identity. Verified against this
              -- interpreter, not assumed.
              gr_id                 TEXT PRIMARY KEY NOT NULL,
              kind                  TEXT NOT NULL
                                      CHECK (kind IN ('business_rule','story')),
              name                  TEXT,
              state                 TEXT NOT NULL DEFAULT 'draft'
                                      CHECK (state IN ('draft','reviewed','approved',
                                                       'rejected','superseded')),
              subject               TEXT,
              subject_provenance    TEXT
                                      CHECK (subject_provenance IS NULL OR
                                             subject_provenance IN ('derived',
                                                                    'derived_ambiguous',
                                                                    'llm_named')),
              statement             TEXT NOT NULL,
              statement_extracted   TEXT NOT NULL,
              as_built              TEXT,
              rule_class            TEXT
                                      CHECK (rule_class IS NULL OR
                                             rule_class IN ('behavioral','definitional')),
              pattern               TEXT
                                      CHECK (pattern IS NULL OR pattern IN (
                                             'B-COND','B-UNCOND','B-PROHIB','B-RESTRICT',
                                             'D-NEC','D-IMPOSS','D-RESTRICT','D-COMPUTE',
                                             'D-INFER','D-CONST')),
              modality              TEXT NOT NULL
                                      CHECK (modality IN ('requirement','expectation')),
              modality_extracted    TEXT NOT NULL
                                      CHECK (modality_extracted IN ('requirement',
                                                                    'expectation')),
              modality_confirmed    INTEGER NOT NULL DEFAULT 0
                                      CHECK (modality_confirmed IN (0,1)),
              enforcement_level     TEXT
                                      CHECK (enforcement_level IS NULL OR
                                             enforcement_level IN ('strict','deferred',
                                                                   'pre-authorized',
                                                                   'post-justified',
                                                                   'override','guideline')),
              category              TEXT
                                      CHECK (category IS NULL OR
                                             category IN ('Calculation','Validation',
                                                          'Lifecycle','Policy')),
              priority              TEXT
                                      CHECK (priority IS NULL OR
                                             priority IN ('P0','P1','P2')),
              confidence_extraction TEXT
                                      CHECK (confidence_extraction IS NULL OR
                                             confidence_extraction IN ('High','Medium',
                                                                       'Low')),
              confidence_intent     TEXT
                                      CHECK (confidence_intent IS NULL OR
                                             confidence_intent IN ('High','Medium','Low')),
              disposition           TEXT
                                      CHECK (disposition IS NULL OR
                                             disposition IN ('captured','not_applicable',
                                                             'unreachable','delegated')),
              structured_body       TEXT,
              structured_body_type  TEXT
                                      CHECK (structured_body_type IS NULL OR
                                             structured_body_type IN ('decision_table',
                                                                      'state_transition',
                                                                      'formula','invariant')),
              implementation_notes  TEXT,
              parameters            TEXT,
              rationale             TEXT,
              fit_criterion         TEXT,
              assumptions           TEXT,
              assumptions_extracted TEXT,
              sme_question          TEXT,
              suspected_defect      TEXT,
              derived_from          TEXT,
              superseded_by         TEXT
                                      REFERENCES gr(gr_id) ON DELETE SET NULL,
              dedupe_key            TEXT NOT NULL,
              dedupe_key_anchor_only TEXT NOT NULL,
              owner                 TEXT,
              reviewed_by           TEXT,
              reviewed_at           TEXT,
              review_note           TEXT,
              extractor_payload     TEXT NOT NULL,
              first_seen_run_id     TEXT,
              created_at            TEXT NOT NULL,
              updated_at            TEXT NOT NULL,

              -- SPEC-1 S1.4's actual constraint, scoped to the state in which
              -- a GR is a settled rule. The `state <> 'approved'` term is NOT
              -- a weakening and must not be removed as one: Step 6a defaults
              -- `disposition` to 'captured' for every confirmed rule AND
              -- leaves `pattern` NULL where the shape is ambiguous, so the
              -- unscoped form rejects that INSERT outright -- and "nothing
              -- gates `draft`" becomes false in the one place it matters
              -- most, on a bad extraction. Presence is enforced ahead of this
              -- in `set_state`'s approval gate, which can name a finding; a
              -- raw "CHECK constraint failed" tells a reviewer nothing. This
              -- is defence in depth behind that gate.
              CHECK (state <> 'approved'
                     OR pattern IS NOT NULL
                     OR disposition IN ('not_applicable','unreachable','delegated')),

              -- The rule_class/pattern partition tie (SPEC-1 S1.7 item 2),
              -- written to tolerate both NULLs deliberately rather than
              -- relying on comparisons against NULL evaluating to unknown.
              CHECK (rule_class IS NULL OR pattern IS NULL
                     OR (rule_class = 'behavioral'   AND pattern LIKE 'B-%')
                     OR (rule_class = 'definitional' AND pattern LIKE 'D-%')),

              -- SPEC-1 S1.7 item 3. Phrased against `definitional`, not as
              -- "only when behavioral": the two differ for a `draft` row
              -- whose `rule_class` is still NULL, and the SPEC form is the
              -- one that lets such a row exist. A definitional rule cannot be
              -- "suggested but not enforced" because it cannot be violated.
              CHECK (rule_class <> 'definitional' OR enforcement_level IS NULL)
            )
        """)
        # Deliberately NOT constrained here, and each omission is a decision:
        #   * There is no `state = 'draft' OR rule_class IS NOT NULL` CHECK.
        #     SPEC-1 S1.7 item 1 reads that way, but it would make
        #     `set-state --to rejected` impossible on exactly the rows that
        #     most deserve rejecting -- a bad extraction with a NULL
        #     `rule_class`. Step 3 settles it: a NULL `rule_class` blocks
        #     *approval* (`V-CLASS-01`, an ERROR) and is not accommodated
        #     further.
        #   * `first_seen_run_id` carries no foreign key to `gr_run`. It would
        #     force ingest to insert the run row before the rules, and Step 6
        #     derives `gr_run`'s five counts from `gr_run_hit` -- i.e. from
        #     rows that do not exist until the rules are in. `gr_run_hit` is
        #     the authoritative "which runs saw this rule"; this column is the
        #     cheap indexed common case, which is why it is named
        #     `first_seen_run_id` and not `run_id`.
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_gr_state ON gr(state)",
            "CREATE INDEX IF NOT EXISTS ix_gr_dedupe_key ON gr(dedupe_key)",
            "CREATE INDEX IF NOT EXISTS ix_gr_dedupe_key_anchor_only "
            "ON gr(dedupe_key_anchor_only)",
            "CREATE INDEX IF NOT EXISTS ix_gr_first_seen_run_id "
            "ON gr(first_seen_run_id)",
        ):
            conn.execute(statement)

        # ------------------------------------------------------------------
        # gr_citation -- one-to-many, each citation carrying its own drift state
        # ------------------------------------------------------------------
        #
        # The surrogate `citation_id` exists because this table is itself a
        # parent (`gr_citation_anchor` hangs off it) and its natural key is a
        # four-column tuple no child should have to carry.
        #
        # `anchor_key` is populated at ingest (Step 6a), never by a later
        # pass, and `CHECK (anchor_key <> '')` is structural rather than
        # decorative: the empty string is the value that would silently
        # collapse stage-one dedupe into a corpus-wide auto-merge. The
        # file-level anchor is the floor, so there is always a real value.
        #
        # `content_hash` is the SPAN-level grain (Step 1) and is nullable: a
        # citation whose line range cannot be read inserts with NULL rather
        # than being dropped or guessed. `anchor_resolution = 'unresolved'`
        # alongside it distinguishes "the file is there but the range is not"
        # from "the path is not in the tree at all".
        #
        # The UNIQUE tuple IS the citation's identity, and it is what Step 6's
        # "add any new citations" tests against: without it a re-ingest
        # quietly accumulates duplicate citation rows under a correctly
        # deduplicated requirement -- the headline merge test passing while the
        # same bug runs one level down.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_citation (
              citation_id       INTEGER PRIMARY KEY,
              gr_id             TEXT NOT NULL
                                  REFERENCES gr(gr_id) ON DELETE CASCADE,
              anchor_key        TEXT NOT NULL CHECK (anchor_key <> ''),
              anchor_resolution TEXT NOT NULL
                                  CHECK (anchor_resolution IN ('symbol','file',
                                                               'unresolved')),
              relative_path     TEXT NOT NULL,
              start_line        INTEGER NOT NULL,
              end_line          INTEGER NOT NULL,
              content_hash      TEXT,
              verified_at       TEXT,
              provenance        TEXT NOT NULL
                                  CHECK (provenance IN ('extracted','repaired','human')),
              UNIQUE (gr_id, relative_path, start_line, end_line)
            )
        """)
        # Both indexes are required and they serve opposite directions:
        # `anchor_key` for the Step 1 move auto-repair's `WHERE anchor_key = ?`
        # lookup, `gr_id` for reading one requirement's citations.
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_gr_citation_gr_id ON gr_citation(gr_id)",
            "CREATE INDEX IF NOT EXISTS ix_gr_citation_anchor_key "
            "ON gr_citation(anchor_key)",
        ):
            conn.execute(statement)

        # ------------------------------------------------------------------
        # gr_citation_anchor -- the REST of a citation's resolved anchors
        # ------------------------------------------------------------------
        #
        # A citation spanning three sibling methods produces three rows here
        # and exactly ONE `gr_citation.anchor_key` (the primary, chosen by
        # Step 6a's deterministic rule).
        #
        # Two homes rather than one, because the two jobs pull in opposite
        # directions: `gr_citation.anchor_key` must stay a single atomic value
        # or the repair's equality lookup degrades to a substring match over
        # 16-hex-char keys, which half-works silently; and this table must
        # exist because "which symbols does this requirement touch?" is a
        # first-class query (Milestone 3's consumer) that one primary anchor
        # cannot answer.
        #
        # **This table is not an input to either dedupe key and must never
        # become one.** Hashing the full set would re-key a rule whose own
        # cited code never changed, the moment an unrelated sibling
        # declaration is added inside its cited range. It is derived and
        # rebuildable from the durable (path, start_line, end_line) triple.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_citation_anchor (
              citation_id INTEGER NOT NULL
                            REFERENCES gr_citation(citation_id) ON DELETE CASCADE,
              anchor_key  TEXT NOT NULL CHECK (anchor_key <> ''),
              containment TEXT NOT NULL
                            CHECK (containment IN ('contains','intersects')),
              is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
              PRIMARY KEY (citation_id, anchor_key)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_gr_citation_anchor_anchor_key "
            "ON gr_citation_anchor(anchor_key)"
        )

        # ------------------------------------------------------------------
        # gr_scenario -- the extractor's Given/When/Then, demoted to 0..n child
        # ------------------------------------------------------------------
        #
        # G/W/T is demoted, not discarded: it stops being the requirement (the
        # normative record is `statement` plus `pattern`) and becomes a
        # subordinate scenario, stored VERBATIM. Three things depend on it --
        # `given`/`when`/`then` are required fields of `RULES_SCHEMA` and so
        # are the largest single volume of extracted content ingest would
        # otherwise drop; the within-run old-shape-versus-new comparison needs
        # both shapes on one rule; and for conditional rules a G/W/T scenario
        # *is* the fit criterion.
        #
        # `when` and `then` are SQLite keywords (CASE expressions), hence the
        # double quotes. Every query against this table must quote them too.
        #
        # UNIQUE (gr_id, provenance, ordinal) is not decoration: without it a
        # re-ingest silently accumulates a second full set of scenarios under a
        # correctly deduplicated requirement, and the headline merge test
        # asserts requirement and citation counts, so it would pass while this
        # doubled underneath it. `provenance` is INSIDE the tuple so a human
        # scenario added during review can take an ordinal without colliding
        # with an extracted one, and so Step 3's refresh rule can address the
        # extracted subset alone.
        #
        # Not a `dedupe_key` input: it is extractor prose and would re-key on
        # every paraphrase, the same defect that keeps `as_built` out.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_scenario (
              scenario_id INTEGER PRIMARY KEY,
              gr_id       TEXT NOT NULL REFERENCES gr(gr_id) ON DELETE CASCADE,
              ordinal     INTEGER NOT NULL,
              "given"     TEXT,
              "when"      TEXT,
              "then"      TEXT,
              and_clause  TEXT,
              provenance  TEXT NOT NULL CHECK (provenance IN ('extracted','human')),
              UNIQUE (gr_id, provenance, ordinal)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_gr_scenario_gr_id ON gr_scenario(gr_id)"
        )

        # ------------------------------------------------------------------
        # gr_edge_case -- the extractor's `edgeCases`, same shape as gr_scenario
        # ------------------------------------------------------------------
        #
        # Deliberately identical in shape, `provenance` included even though
        # Milestone 1 writes only 'extracted': the two tables have identical
        # lifecycles, are refreshed by the same merge rule, and a Milestone 4
        # that lets a reviewer add an edge case must not have to migrate a
        # table to do it.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_edge_case (
              edge_case_id INTEGER PRIMARY KEY,
              gr_id        TEXT NOT NULL REFERENCES gr(gr_id) ON DELETE CASCADE,
              ordinal      INTEGER NOT NULL,
              text         TEXT NOT NULL,
              provenance   TEXT NOT NULL CHECK (provenance IN ('extracted','human')),
              UNIQUE (gr_id, provenance, ordinal)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_gr_edge_case_gr_id ON gr_edge_case(gr_id)"
        )

        # ------------------------------------------------------------------
        # gr_finding -- validator output (Step 4)
        # ------------------------------------------------------------------
        #
        # `span` is the character offset range WITHIN `statement` that the
        # finding points at, stored as "start-end", so a reviewer sees which
        # WORDS tripped a check. **Store '' for a record-level finding, never
        # NULL**: `span` is part of the UNIQUE tuple and SQLite treats NULLs as
        # distinct, so a NULL span would let the same finding insert
        # repeatedly. Hence NOT NULL here.
        #
        # `evaluated` is deliberately NOT a third severity value. SPEC-1 S1.6
        # opens "Severity has exactly two values" and forbids re-severitying
        # any check without amending SPEC-1, and Step 4's claim that the slot
        # split is not an amendment rests on that. So `severity` keeps the
        # severity the check WOULD have carried and `evaluated = 0` says it
        # could not be decided (e.g. `pattern` is NULL, so no template locates
        # `[Subject]`), with the reason in `message`.
        #
        # Re-validating a requirement DELETES that requirement's findings and
        # re-inserts them inside one transaction, so a finding that no longer
        # fires actually disappears rather than being stranded forever.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_finding (
              gr_id      TEXT NOT NULL REFERENCES gr(gr_id) ON DELETE CASCADE,
              finding_id TEXT NOT NULL,
              severity   TEXT NOT NULL CHECK (severity IN ('ERROR','WARN')),
              span       TEXT NOT NULL,
              message    TEXT NOT NULL,
              evaluated  INTEGER NOT NULL DEFAULT 1 CHECK (evaluated IN (0,1)),
              UNIQUE (gr_id, finding_id, span)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_gr_finding_gr_id ON gr_finding(gr_id)"
        )

        # ------------------------------------------------------------------
        # gr_dataflow -- the reads[]/writes[] block (Step 7)
        # ------------------------------------------------------------------
        #
        # **Created in Milestone 1 and stays empty through it -- neither of its
        # two writers exists yet** (the computed path is gated on Milestone 26
        # of the Layer-0 plan, and the LLM fallback has no extractor source).
        # The constraints are built properly anyway, because Step 7's tests run
        # against the computed code with its flag forced on.
        #
        # Two things make that UNIQUE actually work, and getting either wrong
        # reintroduces exactly the stacking it exists to prevent:
        #   1. `column` is '' rather than NULL for a table-level entry --
        #      SQLite treats NULLs as distinct in a UNIQUE index, so a NULL
        #      would let the identical entry insert on every recompute,
        #      without error, forever. Hence NOT NULL DEFAULT ''.
        #   2. Recompute is a delete-then-insert for the whole
        #      (gr_id, direction) pair inside one transaction, not a row-by-row
        #      upsert: the constraint stops duplicates but cannot make a STALE
        #      entry disappear.
        #
        # `column` is a SQLite keyword, hence the quotes.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_dataflow (
              gr_id       TEXT NOT NULL REFERENCES gr(gr_id) ON DELETE CASCADE,
              direction   TEXT NOT NULL CHECK (direction IN ('reads','writes')),
              datastore   TEXT NOT NULL,
              "column"    TEXT NOT NULL DEFAULT '',
              provenance  TEXT NOT NULL
                            CHECK (provenance IN ('computed','llm_inferred')),
              explanation TEXT,
              UNIQUE (gr_id, direction, datastore, "column")
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_gr_dataflow_gr_id ON gr_dataflow(gr_id)"
        )

        # ------------------------------------------------------------------
        # gr_merge_candidate -- stage two's persistent home (Step 6)
        # ------------------------------------------------------------------
        #
        # The incoming rule is still inserted as an ordinary `draft` row -- the
        # under-merge bias is the whole design and must not be softened here.
        # This row records only the SUSPECTED relationship between two records,
        # and `resolution` is what makes it usable: a reviewer's judgement that
        # two records are genuinely `distinct` sticks, so the same pair does
        # not resurface on every subsequent run.
        #
        # The pair IS the relationship's identity, so it is the primary key and
        # there is no surrogate. Without that, "has a reviewer already judged
        # this pair?" has no lookup and `list --candidates` grows a duplicate
        # for every run that re-surfaces one.
        #
        # **`run_id` is deliberately OUTSIDE the key, and that is the
        # load-bearing half.** Including it would key the pair per run, so run
        # N+2 could re-raise a pair a reviewer marked `distinct` in run N --
        # precisely the behaviour `resolution` exists to prevent, reintroduced
        # by the constraint meant to enforce it. `run_id` keeps its own
        # meaning: the run that FIRST raised the pair.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_merge_candidate (
              gr_id_existing TEXT NOT NULL REFERENCES gr(gr_id) ON DELETE CASCADE,
              gr_id_incoming TEXT NOT NULL REFERENCES gr(gr_id) ON DELETE CASCADE,
              run_id         TEXT,
              similarity     REAL,
              reason         TEXT NOT NULL
                               CHECK (reason IN ('semantic','range_overlap','drift')),
              resolution     TEXT NOT NULL DEFAULT 'unresolved'
                               CHECK (resolution IN ('merged','distinct','unresolved')),
              resolved_at    TEXT,
              PRIMARY KEY (gr_id_existing, gr_id_incoming)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_gr_merge_candidate_resolution "
            "ON gr_merge_candidate(resolution)"
        )

        # ------------------------------------------------------------------
        # gr_run -- per-extraction-run metadata
        # ------------------------------------------------------------------
        #
        # `final_round_chunk_coverage_pct` is named for what the extractor
        # actually returns: `coverage: lastCoverage`, the FINAL ROUND's chunk
        # coverage, not the run's union. Do not present it as whole-run
        # coverage. The cumulative figure that carries the argument for merging
        # is distinct files cited across all runs, which is a
        # COUNT(DISTINCT relative_path) over `gr_citation` and needs no column.
        #
        # **`not_accounted_for` is NULLABLE and NULL means "never measured" --
        # it is not zero.** The workflow returns `coverage: null` whenever
        # `repoRoot` was omitted, no index existed, or the coverage command
        # failed. Store a zero for such a run and the arithmetic says the run
        # is complete, `complete` goes to 1, and `export` waves through a
        # corpus whose coverage nobody ever looked at -- the gate passing most
        # confidently in the one case it should stop. Take the value from the
        # coverage payload's `uncovered` INTEGER, never from
        # `len(uncovered_chunks)`, which the workflow caps at 40.
        #
        # `complete` is a GENERATED column so its definition cannot be got
        # wrong by a writer, and so `gate_excluded` provably leaves it
        # untouched ("the record still says what was actually known").
        # **Note the quirk it brings: `PRAGMA table_info` OMITS generated
        # columns** -- use `PRAGMA table_xinfo` when enumerating this table's
        # columns, or `complete` will read as missing.
        #
        # The five counts are derived from `gr_run_hit` at write time (Step 6)
        # rather than being independently asserted, so
        # `rules_in = rules_new + rules_merged + rules_candidate` is a GROUP BY
        # over real rows. `rules_rejected` sits OUTSIDE that identity: rejected
        # rules never become `gr` rows at all, so do not try to make the four
        # numbers sum.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_run (
              -- NOT NULL for the same reason `gr.gr_id` carries it: a
              -- non-INTEGER PRIMARY KEY in a rowid table admits NULL, and
              -- NULLs are distinct to the unique index.
              run_id                    TEXT PRIMARY KEY NOT NULL,
              system                    TEXT,
              started_at                TEXT,
              finished_at               TEXT,
              rounds_run                INTEGER,
              round_cap                 INTEGER,
              stop_reason               TEXT
                                          CHECK (stop_reason IS NULL OR
                                                 stop_reason IN ('dry','round_cap',
                                                                 'budget_exhausted')),
              new_rules_in_final_round  INTEGER,
              final_round_chunk_coverage_pct REAL,
              not_accounted_for         INTEGER,
              coverage_source           TEXT
                                          CHECK (coverage_source IS NULL OR
                                                 coverage_source IN ('extraction',
                                                                     'remeasured')),
              coverage_measured_at      TEXT,
              gate_excluded             INTEGER NOT NULL DEFAULT 0
                                          CHECK (gate_excluded IN (0,1)),
              gate_excluded_reason      TEXT,
              injection_flags           TEXT,
              rules_in                  INTEGER,
              rules_new                 INTEGER,
              rules_merged              INTEGER,
              rules_candidate           INTEGER,
              rules_rejected            INTEGER,
              complete                  INTEGER GENERATED ALWAYS AS (
                                          CASE WHEN not_accounted_for IS NOT NULL
                                                AND not_accounted_for = 0
                                               THEN 1 ELSE 0 END) VIRTUAL,

              -- Retiring a run is a human judgement and is logged as one, so
              -- the reason is required rather than optional: the audit
              -- question is "why did this stop blocking?", and a NULL reason
              -- has no answer to it.
              CHECK (gate_excluded = 0 OR
                     (gate_excluded_reason IS NOT NULL AND gate_excluded_reason <> ''))
            )
        """)

        # ------------------------------------------------------------------
        # gr_run_hit -- the answer to "which runs saw this rule"
        # ------------------------------------------------------------------
        #
        # **The surrogate key is load-bearing and a natural key on
        # (gr_id, run_id) would break the count identity.** One row here means
        # one OFFERED rule, not one requirement, and a single run can offer two
        # rules that land on the same `gr_id`: the extractor's own in-run
        # dedupe keys on `path::lowercased-name`, so two rules mined from the
        # same lines under different names survive it and can then collide on
        # `dedupe_key` -- the first inserting as `new`, the second merging as
        # `merged`. Two rules that both merge produce two rows identical in
        # every natural column. Under a natural key one is refused or silently
        # absorbed, `rules_in` under-counts, and the identity fails for a
        # reason that is not a defect in the merge.
        #
        # So: `hit_id` as the primary key, **no uniqueness on
        # (gr_id, run_id)** -- do not add one -- and `offer_ordinal` recording
        # the rule's index within that run's input array, so a hit traces back
        # to the specific offered object rather than to a requirement that may
        # have absorbed several. That collapse is itself countable from
        # `offer_ordinal`, and on a first ingest into an empty store it IS the
        # intra-run collapse rate (Step 10's mandatory measurement).
        #
        # Outcomes, defined so that every offered rule produces EXACTLY ONE row
        # per run: `new` (neither key matched; a row was inserted), `merged`
        # (an exact `dedupe_key` match; the existing row was updated),
        # `candidate` (matched `dedupe_key_anchor_only`, or stage two surfaced
        # it -- **a row was ALSO inserted here**). Therefore `rules_new` is NOT
        # the number of rows inserted; `rules_new + rules_candidate` is.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_run_hit (
              hit_id        INTEGER PRIMARY KEY,
              gr_id         TEXT NOT NULL REFERENCES gr(gr_id) ON DELETE CASCADE,
              run_id        TEXT NOT NULL,
              offer_ordinal INTEGER NOT NULL,
              outcome       TEXT NOT NULL
                              CHECK (outcome IN ('new','merged','candidate'))
            )
        """)
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_gr_run_hit_gr_id ON gr_run_hit(gr_id)",
            "CREATE INDEX IF NOT EXISTS ix_gr_run_hit_run_id ON gr_run_hit(run_id)",
        ):
            conn.execute(statement)

        # ------------------------------------------------------------------
        # gr_import -- Step 9's import marker
        # ------------------------------------------------------------------
        #
        # One row per `requirements import` invocation, appended and never
        # updated. It earns its place for one reason: import is the single
        # declared exception to "`set_state` is the only writer of `gr.state`",
        # so a state change arriving through it must be traceable to a specific
        # import rather than appearing to have happened spontaneously. It is
        # deliberately NOT part of the JSONL export (that exports requirements;
        # this is local provenance about THIS machine) and deliberately not
        # joined to `gr` -- attributing each row to the import that last
        # touched it would be a per-record audit trail, which is Milestone 4's.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gr_import (
              import_id          INTEGER PRIMARY KEY,
              source_path        TEXT NOT NULL,
              imported_at        TEXT NOT NULL,
              rows_read          INTEGER NOT NULL,
              rows_changed_state INTEGER NOT NULL
            )
        """)

        # ------------------------------------------------------------------
        # gr_fts -- keyword search over the requirement text (Step 5)
        # ------------------------------------------------------------------
        #
        # Milestone 1 Step 5. **A table addition, so no KNOWLEDGE_MIGRATIONS
        # entry** -- the same reasoning the eleven tables above record, and
        # `CREATE VIRTUAL TABLE IF NOT EXISTS` is idempotent the same way.
        #
        # This is `chunk_fts`'s shape exactly (`store.py`, the `chunk_fts`
        # DDL): a **standalone** FTS5 table -- not external-content, not
        # contentless -- with the row key `UNINDEXED` so it is stored and
        # returnable but never searched. Three deliberate choices:
        #   * Standalone rather than external-content, because keeping an
        #     external-content table in step with `gr` needs triggers or exact
        #     rowid discipline, and Step 5 has already rejected triggers (a
        #     trigger cannot reach Chroma, so the vector half would need a
        #     second mechanism anyway, and two mechanisms is how a store ends
        #     up half-synced).
        #   * Standalone rather than contentless (`content=''`), because a
        #     contentless table cannot return the matched text, so
        #     `requirements search` could show no snippet -- most of what makes
        #     keyword search useful to a reviewer.
        #   * Delete-then-insert rather than upsert on every write, for the
        #     same reason `gr_finding` and `gr_dataflow` use it: it is the one
        #     form that makes stale content actually disappear.
        #
        # `assumptions` and `implementation_notes` are deliberately out of the
        # column set for now. Adding them later is free: this table carries no
        # durable state of its own and is rebuilt wholesale from `gr` by
        # `gr_refresh.refresh_gr_derived_sql`, its only writer.
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS gr_fts USING fts5(
              gr_id UNINDEXED,
              name,
              statement,
              as_built,
              rationale
            )
        """)

    # ------------------------------------------------------------------
    # Query API (Milestone 2)
    # ------------------------------------------------------------------

    def upsert_domain(
        self,
        domain_id: str,
        name: str,
        description: str | None,
        path_globs: list[str],
        assess_run_id: str | None,
        display_order: int,
    ) -> None:
        """Insert or replace an authored domain row.

        `path_globs` is serialized to a JSON array string for storage. Never
        call this with `domain_id == "unassigned"` — that slug is reserved
        as a `file_domains.domain` value only (issues #28/#30).
        """
        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO domains
                (domain_id, name, description, path_globs, assess_run_id, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                domain_id,
                name,
                description,
                json.dumps(list(path_globs)),
                assess_run_id,
                display_order,
            ),
        )
        conn.commit()

    def upsert_domain_edge(
        self,
        from_domain: str,
        to_domain: str,
        kind: str | None,
        evidence: str | None,
    ) -> None:
        """Insert or replace an authored inter-domain dependency edge.

        `kind` is normalized to `""` when `None` is passed, matching the
        column's `NOT NULL DEFAULT ''` (issue #51).
        """
        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO domain_edges
                (from_domain, to_domain, kind, evidence)
            VALUES (?, ?, ?, ?)
            """,
            (from_domain, to_domain, kind or "", evidence),
        )
        conn.commit()

    def upsert_file_domain(
        self,
        relative_path: str,
        domain: str,
        source: str,
        assess_run_id: str | None,
        confidence: float,
    ) -> None:
        """Insert or replace a per-file domain assignment.

        `domain` may be the reserved value `"unassigned"`. `source` must be
        `"glob"` or `"manual"` (enforced by the table's CHECK constraint).

        Manual-wins is enforced here at the write primitive, not just at the
        callers: a `source != 'manual'` write against a path that already
        carries a `source='manual'` row is a no-op. Today both callers (the
        indexer's 7-Auto and `tag-domains`) already filter manual paths out
        before calling this, so this guard is defense-in-depth that keeps the
        manual-wins invariant structural — a future caller cannot silently
        clobber a human correction by resolving a glob over it. A `manual`
        write still replaces any existing row, so correction tooling can
        overwrite a prior manual assignment.
        """
        conn = self._connect()
        if source != "manual":
            row = conn.execute(
                "SELECT source FROM file_domains WHERE relative_path = ?",
                (relative_path,),
            ).fetchone()
            if row is not None and row["source"] == "manual":
                return
        conn.execute(
            """
            INSERT OR REPLACE INTO file_domains
                (relative_path, domain, source, assess_run_id, confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (relative_path, domain, source, assess_run_id, confidence),
        )
        conn.commit()

    def list_domains(self) -> list[DomainRecord]:
        """Return all authored domains, ordered by `display_order, domain_id`.

        This ordering is load-bearing (issue #14): glob precedence is
        "first matching domain in declaration order wins," and later
        milestones' resolvers trust this ordering rather than re-sorting.
        The reserved "unassigned" sentinel is never returned — it has no
        `domains`-table row.
        """
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT domain_id, name, description, path_globs, assess_run_id, display_order
            FROM domains
            ORDER BY display_order, domain_id
            """
        ).fetchall()
        return [
            DomainRecord(
                domain_id=row["domain_id"],
                name=row["name"],
                description=row["description"],
                path_globs=json.loads(row["path_globs"]),
                assess_run_id=row["assess_run_id"],
                display_order=row["display_order"],
            )
            for row in rows
        ]

    def get_domain_edges(self) -> list[DomainEdgeRecord]:
        """Return all authored inter-domain dependency edges."""
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT from_domain, to_domain, kind, evidence
            FROM domain_edges
            ORDER BY from_domain, to_domain, kind
            """
        ).fetchall()
        return [
            DomainEdgeRecord(
                from_domain=row["from_domain"],
                to_domain=row["to_domain"],
                kind=row["kind"],
                evidence=row["evidence"],
            )
            for row in rows
        ]

    def files_for_domain(self, domain_id: str) -> list[str]:
        """Return the relative paths of every file assigned to `domain_id`.

        `domain_id` may be the reserved value `"unassigned"` — this method
        queries `file_domains` directly and has no dependency on the
        `domains` table.
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT relative_path FROM file_domains WHERE domain = ? ORDER BY relative_path",
            (domain_id,),
        ).fetchall()
        return [row["relative_path"] for row in rows]

    def domain_for_file(self, relative_path: str) -> str | None:
        """Return the domain assigned to `relative_path`, or None if untagged."""
        conn = self._connect()
        row = conn.execute(
            "SELECT domain FROM file_domains WHERE relative_path = ?",
            (relative_path,),
        ).fetchone()
        return row["domain"] if row is not None else None

    def domain_file_counts(self) -> dict[str, int]:
        """Return a raw `{domain: file_count}` map over `file_domains`.

        This is an unfiltered aggregate straight from the table. Callers
        that must not over-count after a `--reset` leaves ghost rows
        (issue #55) — the `domains`/`stats` CLI commands — intersect
        `files_for_domain()` results with the discovered file set instead
        of relying on this raw count directly.
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT domain, COUNT(*) AS c FROM file_domains GROUP BY domain"
        ).fetchall()
        return {row["domain"]: row["c"] for row in rows}

    # ------------------------------------------------------------------
    # Excluded-by-design tier (domain_exclusions)
    # ------------------------------------------------------------------

    def set_exclusions(self, patterns: list[str]) -> None:
        """Replace the authored exclusion glob set (replace-all, like domains).

        Idempotent: re-running `tag-domains` converges to exactly the
        `exclude_globs` in the current `domains.json`. Order is not
        significant (exclusions are a set-membership test, not first-match).
        """
        conn = self._connect()
        conn.execute("DELETE FROM domain_exclusions")
        conn.executemany(
            "INSERT OR IGNORE INTO domain_exclusions(pattern) VALUES (?)",
            [(p,) for p in patterns],
        )
        conn.commit()

    def list_exclusions(self) -> list[str]:
        """Return the authored exclusion globs (sorted for determinism)."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT pattern FROM domain_exclusions ORDER BY pattern"
        ).fetchall()
        return [row["pattern"] for row in rows]

    # ------------------------------------------------------------------
    # The GR read/write API (Milestone 1, Step 4 onward)
    # ------------------------------------------------------------------
    #
    # Only what Step 4 needs is here: reading one requirement, and the
    # finding and state writes the validator and its gate require. Ingest,
    # the merge and the rest of the read surface belong to Steps 6 and 8.

    def get_gr(self, gr_id: str) -> GRRecord | None:
        """Return one requirement, or None if this store has no such row."""
        conn = self._connect()
        row = conn.execute("SELECT * FROM gr WHERE gr_id = ?", (gr_id,)).fetchone()
        if row is None:
            return None
        return GRRecord(**{k: row[k] for k in row.keys()})

    def list_gr_findings(self, gr_id: str) -> list[Finding]:
        """Return one requirement's stored validator findings, in table order."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT finding_id, severity, span, message, evaluated "
            "FROM gr_finding WHERE gr_id = ? ORDER BY finding_id, span",
            (gr_id,),
        ).fetchall()
        return [
            Finding(
                finding_id=r["finding_id"],
                severity=r["severity"],
                span=r["span"],
                message=r["message"],
                evaluated=bool(r["evaluated"]),
            )
            for r in rows
        ]

    def replace_gr_findings(self, gr_id: str, findings: list[Finding]) -> None:
        """Delete this requirement's findings and insert the given set.

        **Delete-then-insert, not an upsert**, and inside one transaction: a
        finding that no longer fires must actually disappear rather than
        being stranded on the record forever. An upsert satisfies the
        `UNIQUE (gr_id, finding_id, span)` constraint and still leaves the
        stale rows behind, which is the failure the delete half prevents.

        Does **not** commit — Step 5's `refresh_gr_derived_sql` runs inside
        whatever transaction its caller already has open, which for ingest is
        the single transaction covering the run.
        """
        conn = self._connect()
        conn.execute("DELETE FROM gr_finding WHERE gr_id = ?", (gr_id,))
        conn.executemany(
            "INSERT INTO gr_finding(gr_id, finding_id, severity, span, message, "
            "evaluated) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (gr_id, f.finding_id, f.severity, f.span, f.message, int(f.evaluated))
                for f in findings
            ],
        )

    def apply_gr_state(
        self,
        gr_id: str,
        *,
        state: str,
        reviewed_by: str,
        reviewed_at: str,
        review_note: str | None,
        superseded_by: str | None,
        updated_at: str,
    ) -> None:
        """Write a state change and the three columns that record the review.

        **This is the mechanical writer, not the policy.** The transition
        graph, the reviewer requirement and the `draft -> approved` gate all
        live in `gr_state.set_state`, which is the only permitted caller
        (Step 9's `import_records` is the single declared exception). Calling
        this directly routes around the gate; a test asserts the writer set is
        complete.

        `reviewed_by`, `reviewed_at` and `review_note` are written together
        and are **last-write-wins, not a history** — one row records the most
        recent judgement. A per-transition audit trail is Milestone 4's.
        """
        conn = self._connect()
        if superseded_by is None:
            conn.execute(
                "UPDATE gr SET state = ?, reviewed_by = ?, reviewed_at = ?, "
                "review_note = ?, updated_at = ? WHERE gr_id = ?",
                (state, reviewed_by, reviewed_at, review_note, updated_at, gr_id),
            )
        else:
            conn.execute(
                "UPDATE gr SET state = ?, reviewed_by = ?, reviewed_at = ?, "
                "review_note = ?, superseded_by = ?, updated_at = ? "
                "WHERE gr_id = ?",
                (
                    state,
                    reviewed_by,
                    reviewed_at,
                    review_note,
                    superseded_by,
                    updated_at,
                    gr_id,
                ),
            )
        conn.commit()

    # ------------------------------------------------------------------
    # What Step 5's refresh pair reads and writes
    # ------------------------------------------------------------------

    def list_gr(self, gr_ids: list[str]) -> list[GRRecord]:
        """Return the requirements among `gr_ids` that exist, in that order.

        A `gr_id` with no row is simply absent from the result; the caller
        (`refresh_gr_derived_sql`) treats the difference as rows to *forget*,
        which is how a deleted requirement loses its FTS row and its vector.
        """
        if not gr_ids:
            return []
        conn = self._connect()
        found: dict[str, GRRecord] = {}
        for i in range(0, len(gr_ids), 500):
            batch = gr_ids[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            rows = conn.execute(
                f"SELECT * FROM gr WHERE gr_id IN ({placeholders})", batch
            ).fetchall()
            for row in rows:
                record = GRRecord(**{k: row[k] for k in row.keys()})
                found[record.gr_id] = record
        return [found[g] for g in gr_ids if g in found]

    def count_gr(self) -> int:
        """Total `gr` rows — the denominator of Step 5's shortfall check."""
        conn = self._connect()
        return int(conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0])

    def all_gr_ids(self) -> list[str]:
        """Every `gr_id`, ordered — what `reindex-vectors` walks (Step 8)."""
        conn = self._connect()
        return [
            r[0] for r in conn.execute("SELECT gr_id FROM gr ORDER BY gr_id").fetchall()
        ]

    def citation_paths_for_gr(self, gr_id: str) -> list[str]:
        """Distinct `relative_path` values this requirement cites.

        The input to Step 5's `leaked_terms` set. **A reader here rather than
        inline SQL in `gr_refresh`**: the two databases are never `ATTACH`ed,
        so every cross-store join is done in Python (the `domains_cmd`
        pattern), and each store keeps its own SQL.
        """
        conn = self._connect()
        return [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT relative_path FROM gr_citation WHERE gr_id = ? "
                "ORDER BY relative_path",
                (gr_id,),
            ).fetchall()
        ]

    def replace_gr_fts(self, record: GRRecord) -> None:
        """Rewrite one requirement's `gr_fts` row: delete, then insert.

        **The delete half is the point.** A standalone FTS5 table holds its own
        copy of the text, so an INSERT alone leaves the pre-edit wording
        searchable forever — the record answers to words it no longer contains.
        This mirrors the `chunk_fts` idiom in `store.py` exactly.

        Does **not** commit: like `replace_gr_findings`, this runs inside
        whatever transaction its caller already has open.
        """
        conn = self._connect()
        conn.execute("DELETE FROM gr_fts WHERE gr_id = ?", (record.gr_id,))
        conn.execute(
            "INSERT INTO gr_fts (gr_id, name, statement, as_built, rationale) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                record.gr_id,
                record.name or "",
                record.statement,
                record.as_built or "",
                record.rationale or "",
            ),
        )

    def delete_gr_fts(self, gr_id: str) -> None:
        """Forget a requirement's indexed text. Does not commit."""
        conn = self._connect()
        conn.execute("DELETE FROM gr_fts WHERE gr_id = ?", (gr_id,))

    def search_gr_fts(self, query: str, limit: int = 20) -> list[tuple[str, str]]:
        """Keyword-search requirements, returning `(gr_id, statement)` by rank.

        The minimal reader Step 5's own acceptance needs (an edit reaches
        search; the pre-edit wording stops matching). `requirements search`
        and its snippets are Step 8's.
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT gr_id, statement FROM gr_fts WHERE gr_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (query, limit),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    # ------------------------------------------------------------------
    # What Step 6's merge reads and writes
    # ------------------------------------------------------------------
    #
    # **Every raw `gr`-table write in the requirements path lives here**, and
    # not in `gr_ingest.py`, for a reason with a test attached:
    # `test_gr_state.py`'s writer census asserts that exactly two modules
    # contain a write statement targeting `gr`, so that "`set_state` and
    # `import_records` are the complete set of writers of `gr.state`" is
    # checkable rather than asserted. Ingest composing column-mapped writes
    # through this API keeps that property true, and keeps the SQL for one
    # table in one place.

    def find_gr_by_dedupe_key(self, dedupe_key: str) -> GRRecord | None:
        """Stage one's exact match: the row carrying this `dedupe_key`.

        `ix_gr_dedupe_key` serves it. Returns the *first* match ordered by
        `gr_id`, which is creation order — a second row sharing a key can
        only arise from a hash collision at 64 bits, and picking
        deterministically is better than picking arbitrarily.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM gr WHERE dedupe_key = ? ORDER BY gr_id LIMIT 1",
            (dedupe_key,),
        ).fetchone()
        if row is None:
            return None
        return GRRecord(**{k: row[k] for k in row.keys()})

    def gr_ids_by_anchor_only_key(self, dedupe_key_anchor_only: str) -> list[str]:
        """Stage one's fallback: every `gr_id` carrying this drift-resistant key.

        A **list**, because the anchor-only key is deliberately coarser than
        the full one — several requirements mined from the same anchors with
        the same class and pattern share it legitimately. The caller raises a
        `drift` candidate against each and inserts its own row regardless; it
        never merges, because no similarity signal auto-merges anything.
        """
        conn = self._connect()
        return [
            r[0]
            for r in conn.execute(
                "SELECT gr_id FROM gr WHERE dedupe_key_anchor_only = ? "
                "ORDER BY gr_id",
                (dedupe_key_anchor_only,),
            ).fetchall()
        ]

    def gr_shadow_is_unedited(self, gr_id: str, field: str) -> bool:
        """Is `field` still equal to its `_extracted` shadow on this row?

        **This is the "has a human edited this" test, and it is one equality
        over two columns — not a fuzzy comparison, not a timestamp
        comparison, not a "looks edited" heuristic.** All three shadowed
        fields (`statement`, `assumptions`, `modality`) call this one helper,
        which is the point of it existing:

        **The comparison is SQLite `IS`, never `=`.** `statement` and
        `modality` are `NOT NULL`, so the two operators agree on them — but
        `assumptions` is nullable, and `=` over two NULLs yields NULL rather
        than true. Under `=`, an unedited rule with no assumptions reads as
        human-edited and the merge stops updating it, permanently and
        silently. One helper disarms that trap once instead of getting it
        right in two fields out of three.

        Args:
            gr_id: The stored requirement.
            field: A shadowed field — one of `get_shadowed_fields(conn)`.
                Validated against that set, both because the name is
                interpolated into SQL and because a typo would otherwise
                answer "unedited" for a column that does not exist.

        Returns:
            True when the live column `IS` its shadow (so the merge may write
            the live column), False when they differ. Also False when no such
            row exists, which is the safe answer: nothing should be updated.

        Raises:
            ValueError: If `field` is not a shadowed field.
        """
        from legacylift_search.gr_fields import get_shadowed_fields

        conn = self._connect()
        if field not in get_shadowed_fields(conn):
            raise ValueError(
                f"{field!r} is not a shadowed field; the shadow-equality test "
                f"applies only to columns having a '<field>_extracted' "
                f"companion"
            )
        row = conn.execute(
            f'SELECT CASE WHEN "{field}" IS "{field}_extracted" THEN 1 ELSE 0 '
            f"END FROM gr WHERE gr_id = ?",
            (gr_id,),
        ).fetchone()
        return bool(row[0]) if row is not None else False

    def insert_gr_row(self, values: dict) -> None:
        """Insert one `gr` row from a column -> value mapping. Does not commit.

        A column-mapped write rather than a fixed column list: ingest derives
        which columns it writes from `gr_fields`' four sets, so a fixed list
        here would be a fifth hand-kept copy of exactly the membership that
        module exists to make single-sourced.
        """
        conn = self._connect()
        columns = ", ".join(f'"{c}"' for c in values)
        placeholders = ", ".join("?" for _ in values)
        conn.execute(
            f"INSERT INTO gr ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )

    def update_gr_row(self, gr_id: str, values: dict) -> None:
        """Update the named columns of one `gr` row. Does not commit.

        **The caller decides whether to call this at all.** Step 6's
        value-changing-write rule says a write that changes no value must not
        bump `updated_at`, so the comparison lives in the merge and this
        method is unconditional: given a mapping it writes it.
        """
        if not values:
            return
        conn = self._connect()
        set_clause = ", ".join(f'"{c}" = ?' for c in values)
        conn.execute(
            f"UPDATE gr SET {set_clause} WHERE gr_id = ?",
            (*values.values(), gr_id),
        )

    def list_gr_citations(self, gr_id: str) -> list[GRCitation]:
        """This requirement's citations, ordered by the uniqueness tuple."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT citation_id, gr_id, anchor_key, anchor_resolution, "
            "relative_path, start_line, end_line, content_hash, verified_at, "
            "provenance FROM gr_citation WHERE gr_id = ? "
            "ORDER BY relative_path, start_line, end_line",
            (gr_id,),
        ).fetchall()
        return [GRCitation(**{k: r[k] for k in r.keys()}) for r in rows]

    def upsert_gr_citation(self, citation: GRCitation) -> tuple[int, bool]:
        """Insert a citation, or refresh an existing one's drift columns.

        "Add any new citations" means insert on the `gr_citation` uniqueness
        tuple `(gr_id, relative_path, start_line, end_line)` — that tuple *is*
        the citation's identity. Without this rule a re-ingest leaves the
        requirement count flat, which is the headline acceptance test, while
        the citation count doubles underneath it: the same bug one level down.

        An existing citation is **left alone apart from `content_hash` and
        `verified_at`, and those move only when the hash actually changed.**
        That last clause is Step 6's value-changing-write rule applied one
        level down, and it is deliberate rather than inherited: `verified_at`
        is part of the JSONL export, so stamping it on every ingest would make
        "re-ingesting the same output changes nothing" false in a column
        nobody thinks to check.

        Returns:
            `(citation_id, inserted)` — `inserted` False means the row was
            already there, whatever happened to its drift columns.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT citation_id, content_hash FROM gr_citation "
            "WHERE gr_id = ? AND relative_path = ? AND start_line = ? "
            "AND end_line = ?",
            (
                citation.gr_id,
                citation.relative_path,
                citation.start_line,
                citation.end_line,
            ),
        ).fetchone()
        if row is not None:
            citation_id = int(row["citation_id"])
            if row["content_hash"] != citation.content_hash:
                conn.execute(
                    "UPDATE gr_citation SET content_hash = ?, verified_at = ? "
                    "WHERE citation_id = ?",
                    (citation.content_hash, citation.verified_at, citation_id),
                )
            return citation_id, False
        cursor = conn.execute(
            "INSERT INTO gr_citation (gr_id, anchor_key, anchor_resolution, "
            "relative_path, start_line, end_line, content_hash, verified_at, "
            "provenance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                citation.gr_id,
                citation.anchor_key,
                citation.anchor_resolution,
                citation.relative_path,
                citation.start_line,
                citation.end_line,
                citation.content_hash,
                citation.verified_at,
                citation.provenance,
            ),
        )
        return int(cursor.lastrowid), True

    def replace_gr_citation_anchors(
        self, citation_id: int, anchors: list, primary_anchor_key: str
    ) -> None:
        """Rewrite one citation's `gr_citation_anchor` set. Does not commit.

        Delete-then-insert, because the table is **derived and rebuildable**
        from the durable `(path, start_line, end_line)` triple: a symbol that
        no longer overlaps the range must actually disappear rather than being
        stranded, which an upsert cannot achieve.

        Args:
            citation_id: The parent citation.
            anchors: `AnchorResolution.all` — one entry per containing or
                intersecting symbol, winner included.
            primary_anchor_key: `AnchorResolution.primary`, which is also
                stored on `gr_citation.anchor_key`. `is_primary` marks it here
                **as well as** there, because the full set includes it.
        """
        conn = self._connect()
        conn.execute(
            "DELETE FROM gr_citation_anchor WHERE citation_id = ?", (citation_id,)
        )
        conn.executemany(
            "INSERT INTO gr_citation_anchor (citation_id, anchor_key, "
            "containment, is_primary) VALUES (?, ?, ?, ?)",
            [
                (
                    citation_id,
                    hit.anchor_key,
                    hit.containment,
                    int(hit.anchor_key == primary_anchor_key),
                )
                for hit in anchors
            ],
        )

    def list_gr_scenarios(
        self, gr_id: str, provenance: str = "extracted"
    ) -> list[GRScenario]:
        """One provenance's scenarios for a requirement, in ordinal order.

        `when` and `then` are SQLite keywords, hence the double quotes — every
        query against this table needs them.
        """
        conn = self._connect()
        rows = conn.execute(
            'SELECT scenario_id, gr_id, ordinal, "given", "when", "then", '
            "and_clause, provenance FROM gr_scenario "
            "WHERE gr_id = ? AND provenance = ? ORDER BY ordinal",
            (gr_id, provenance),
        ).fetchall()
        return [GRScenario(**{k: r[k] for k in r.keys()}) for r in rows]

    def replace_gr_scenarios(
        self, gr_id: str, scenarios: list, provenance: str = "extracted"
    ) -> bool:
        """Refresh one provenance's scenario set, per Step 3's merge rule.

        Compare the incoming set against the stored rows of that
        `provenance`; if they are identical, **do nothing at all**; otherwise
        delete that subset and insert the incoming one, inside the caller's
        transaction. Three properties of that phrasing are load-bearing:

        * **Scoping the delete to one `provenance`** preserves a reviewer's
          own scenarios, which a blanket delete would destroy.
        * **Delete-then-insert rather than upsert** is what makes a scenario
          the extractor no longer emits actually disappear instead of being
          stranded.
        * **Skipping the write entirely when the sets match** is Step 6's
          value-changing-write rule one level down: it keeps the surrogate
          keys stable across an idempotent re-ingest, which matters because
          Step 9's export must be byte-identical on a second run.

        Returns:
            True when rows were rewritten, False when the sets already matched.
        """
        stored = [
            (s.ordinal, s.given, s.when, s.then, s.and_clause)
            for s in self.list_gr_scenarios(gr_id, provenance)
        ]
        incoming = [
            (s.ordinal, s.given, s.when, s.then, s.and_clause) for s in scenarios
        ]
        if stored == incoming:
            return False
        conn = self._connect()
        conn.execute(
            "DELETE FROM gr_scenario WHERE gr_id = ? AND provenance = ?",
            (gr_id, provenance),
        )
        conn.executemany(
            'INSERT INTO gr_scenario (gr_id, ordinal, "given", "when", "then", '
            "and_clause, provenance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (gr_id, s.ordinal, s.given, s.when, s.then, s.and_clause, provenance)
                for s in scenarios
            ],
        )
        return True

    def list_gr_edge_cases(
        self, gr_id: str, provenance: str = "extracted"
    ) -> list[GREdgeCase]:
        """One provenance's edge cases for a requirement, in ordinal order."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT edge_case_id, gr_id, ordinal, text, provenance "
            "FROM gr_edge_case WHERE gr_id = ? AND provenance = ? "
            "ORDER BY ordinal",
            (gr_id, provenance),
        ).fetchall()
        return [GREdgeCase(**{k: r[k] for k in r.keys()}) for r in rows]

    def replace_gr_edge_cases(
        self, gr_id: str, edge_cases: list, provenance: str = "extracted"
    ) -> bool:
        """Refresh one provenance's edge-case set. Same rule as scenarios.

        The two tables carry the same shape deliberately and are refreshed by
        the same rule, so this is `replace_gr_scenarios` over one text column.

        Returns:
            True when rows were rewritten, False when the sets already matched.
        """
        stored = [
            (e.ordinal, e.text) for e in self.list_gr_edge_cases(gr_id, provenance)
        ]
        incoming = [(e.ordinal, e.text) for e in edge_cases]
        if stored == incoming:
            return False
        conn = self._connect()
        conn.execute(
            "DELETE FROM gr_edge_case WHERE gr_id = ? AND provenance = ?",
            (gr_id, provenance),
        )
        conn.executemany(
            "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) "
            "VALUES (?, ?, ?, ?)",
            [(gr_id, e.ordinal, e.text, provenance) for e in edge_cases],
        )
        return True

    def gr_ids_citing_overlapping_range(
        self, relative_path: str, start_line: int, end_line: int, exclude_gr_id: str
    ) -> list[str]:
        """Requirements whose citations on this file *intersect* this range.

        **Stage two's structural half, and intersection is right here while
        exact equality is right for a key.** They are different jobs and both
        are needed: `gr_citation`'s uniqueness tuple compares ranges exactly,
        because a key must be a key; this comparison is tolerant, because a
        candidate *search* that demanded exact equality would find only what
        stage one already found.

        `exclude_gr_id` is the incoming rule's own freshly-inserted row, which
        cites this range by construction and would otherwise be its own
        candidate.
        """
        conn = self._connect()
        return [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT gr_id FROM gr_citation "
                "WHERE relative_path = ? AND gr_id <> ? "
                "AND start_line <= ? AND end_line >= ? ORDER BY gr_id",
                (relative_path, exclude_gr_id, end_line, start_line),
            ).fetchall()
        ]

    def record_gr_merge_candidate(self, candidate: GRMergeCandidate) -> bool:
        """Raise a stage-two candidate pair, or refresh an unresolved one.

        **The pair is the primary key and `run_id` is deliberately outside
        it**, so the same pair surfacing on a later run updates one row rather
        than being raised again — and a resolution a reviewer already recorded
        survives the next ingest. Hence the rule Step 3 states: on a later run
        that would re-raise an existing pair, leave the row alone unless
        `resolution` is `unresolved`, in which case refreshing `similarity`
        and `reason` is fine. **Never overwrite a resolved one**, and never
        rewrite `run_id`, which keeps its meaning as the run that *first*
        raised the pair.

        Returns:
            True when a new row was inserted, False when an existing pair was
            refreshed or deliberately left alone.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT resolution FROM gr_merge_candidate "
            "WHERE gr_id_existing = ? AND gr_id_incoming = ?",
            (candidate.gr_id_existing, candidate.gr_id_incoming),
        ).fetchone()
        if row is not None:
            if row["resolution"] == "unresolved":
                conn.execute(
                    "UPDATE gr_merge_candidate SET similarity = ?, reason = ? "
                    "WHERE gr_id_existing = ? AND gr_id_incoming = ?",
                    (
                        candidate.similarity,
                        candidate.reason,
                        candidate.gr_id_existing,
                        candidate.gr_id_incoming,
                    ),
                )
            return False
        conn.execute(
            "INSERT INTO gr_merge_candidate (gr_id_existing, gr_id_incoming, "
            "run_id, similarity, reason, resolution, resolved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                candidate.gr_id_existing,
                candidate.gr_id_incoming,
                candidate.run_id,
                candidate.similarity,
                candidate.reason,
                candidate.resolution,
                candidate.resolved_at,
            ),
        )
        return True

    def insert_gr_run(self, run: GRRun) -> None:
        """Write the run's metadata row. Does not commit.

        **`complete` is not written**: it is a generated VIRTUAL column, so
        its definition cannot be got wrong by a writer. Note the quirk that
        follows — `PRAGMA table_info('gr_run')` omits it; use
        `PRAGMA table_xinfo`.
        """
        conn = self._connect()
        conn.execute(
            "INSERT INTO gr_run (run_id, system, started_at, finished_at, "
            "rounds_run, round_cap, stop_reason, new_rules_in_final_round, "
            "final_round_chunk_coverage_pct, not_accounted_for, "
            "coverage_source, coverage_measured_at, gate_excluded, "
            "gate_excluded_reason, injection_flags, rules_in, rules_new, "
            "rules_merged, rules_candidate, rules_rejected) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.system,
                run.started_at,
                run.finished_at,
                run.rounds_run,
                run.round_cap,
                run.stop_reason,
                run.new_rules_in_final_round,
                run.final_round_chunk_coverage_pct,
                run.not_accounted_for,
                run.coverage_source,
                run.coverage_measured_at,
                int(run.gate_excluded),
                run.gate_excluded_reason,
                run.injection_flags,
                run.rules_in,
                run.rules_new,
                run.rules_merged,
                run.rules_candidate,
                run.rules_rejected,
            ),
        )

    def insert_gr_run_hit(self, hit: GRRunHit) -> None:
        """Record one **offered** rule's outcome in one run. Does not commit.

        One row means one offered rule, not one requirement, and there is
        deliberately **no uniqueness on `(gr_id, run_id)`** — a single run can
        offer two rules that land on the same `gr_id`, and a natural key would
        refuse one of them, under-count `rules_in` and fail the run-count
        identity for a reason that is not a defect in the merge.
        """
        conn = self._connect()
        conn.execute(
            "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) "
            "VALUES (?, ?, ?, ?)",
            (hit.gr_id, hit.run_id, hit.offer_ordinal, hit.outcome),
        )

    def intra_run_collapse_count(self, run_id: str) -> int:
        """Offered rules in this run that landed on a shared `gr_id`.

        Step 6's mandatory measurement, and `gr_run_hit.offer_ordinal` makes
        it one query: the number of offered rules in a run that landed on a
        `gr_id` another rule in the same run also landed on. **On a first
        ingest into an empty store that figure *is* the intra-run collapse
        rate**, uncontaminated by cross-run merging.

        It is a count of *offers*, not of `gr_id`s: two rules collapsing onto
        one requirement contribute 2, because the question is how many mined
        rules lost their own row.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT COALESCE(SUM(n), 0) FROM (SELECT COUNT(*) AS n "
            "FROM gr_run_hit WHERE run_id = ? GROUP BY gr_id "
            "HAVING COUNT(*) > 1)",
            (run_id,),
        ).fetchone()
        return int(row[0])

    # ------------------------------------------------------------------
    # What Step 8's `requirements` command group reads and writes
    # ------------------------------------------------------------------
    #
    # Every raw `gr`-table statement in this milestone lives in this module
    # (see the Step 6 note above), so the readers `list`, `show`, `stats` and
    # `validate` need are here rather than in the CLI package. The writers
    # below touch `gr_run` and not `gr`, but they live here for the same
    # layering reason: one table, one place its SQL is written.

    def query_gr(
        self,
        *,
        state: str | None = None,
        category: str | None = None,
        kind: str | None = None,
        subject: str | None = None,
        disposition: str | None = None,
        limit: int | None = None,
    ) -> list[GRRecord]:
        """`requirements list`'s filtered read, ordered by `gr_id`.

        Every filter is an exact equality AND-ed with the others, and
        **`None` means "do not filter on this column", never "match NULL"**.
        The two are different questions and this signature can only ask the
        first: a caller wanting "requirements with no category" would be
        asking for `category IS NULL`, which is not expressible here and is
        deliberately left out rather than smuggled in as `None`, because a
        `None` that sometimes means "unfiltered" and sometimes means "NULL"
        is the absent-versus-real defect wearing a keyword argument. `stats`
        answers the NULL question instead, through `count_gr_by`, which keeps
        NULL as its own key.

        Ordered by `gr_id`, which is a ULID and therefore creation order --
        so a `--limit` takes the *oldest* matching requirements
        deterministically rather than an arbitrary page.

        Args:
            state, category, kind, subject, disposition: exact-match filters.
            limit: Maximum rows, or `None` for all of them. A negative limit
                is refused rather than silently meaning "unlimited", which is
                what SQLite's own `LIMIT -1` would do.

        Raises:
            ValueError: on a negative `limit`.
        """
        if limit is not None and limit < 0:
            raise ValueError(
                f"limit must be >= 0 or None (meaning unlimited); got {limit}"
            )
        clauses: list[str] = []
        params: list[object] = []
        for column, value in (
            ("state", state),
            ("category", category),
            ("kind", kind),
            ("subject", subject),
            ("disposition", disposition),
        ):
            if value is not None:
                clauses.append(f'"{column}" = ?')
                params.append(value)
        sql = "SELECT * FROM gr"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY gr_id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        conn = self._connect()
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [GRRecord(**{k: row[k] for k in row.keys()}) for row in rows]

    def list_unresolved_gr_merge_candidates(
        self, limit: int | None = None
    ) -> list[GRMergeCandidate]:
        """The `unresolved` stage-two pairs, backing `list --candidates`.

        Without this reader stage two of the merge is counted and never seen,
        and the whole under-merge safety argument collapses into a number
        nobody looks at (Step 8).

        **`similarity` is passed through as-is and a NULL one stays `None`.**
        A `range_overlap` or `drift` candidate has no similarity score at
        all -- there was no vector comparison -- and rendering that as `0.0`
        would read as "compared, and found maximally dissimilar", which is
        the opposite of what happened.
        """
        if limit is not None and limit < 0:
            raise ValueError(f"limit must be >= 0 or None; got {limit}")
        sql = (
            "SELECT gr_id_existing, gr_id_incoming, run_id, similarity, "
            "reason, resolution, resolved_at FROM gr_merge_candidate "
            "WHERE resolution = 'unresolved' "
            "ORDER BY gr_id_existing, gr_id_incoming"
        )
        params: tuple[object, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        conn = self._connect()
        rows = conn.execute(sql, params).fetchall()
        return [
            GRMergeCandidate(**{k: r[k] for k in r.keys()}) for r in rows
        ]

    def list_gr_dataflow(self, gr_id: str) -> list[DataflowEntry]:
        """One requirement's `reads[]`/`writes[]` entries, for `show`.

        **Empty throughout Milestone 1**, and that is correct rather than a
        gap: `gr_dataflow` has no writer yet (Step 7). `column` is `''` for a
        table-grain entry, never NULL, because it sits in the table's
        uniqueness tuple and SQLite treats NULLs as distinct.
        """
        conn = self._connect()
        rows = conn.execute(
            'SELECT gr_id, direction, datastore, "column", provenance, '
            "explanation FROM gr_dataflow WHERE gr_id = ? "
            'ORDER BY direction, datastore, "column"',
            (gr_id,),
        ).fetchall()
        return [DataflowEntry(**{k: r[k] for k in r.keys()}) for r in rows]

    def gr_dataflow_provenance_counts(self) -> dict[str, int]:
        """`{provenance: count}` over the whole `gr_dataflow` table.

        The three numbers `gr_dataflow.dataflow_status_text` takes. Absent
        provenance values are simply absent keys; the caller reads
        `.get(name, 0)`, and the *total* is a separate `COUNT(*)` rather
        than a sum of two keys, so a third provenance value appearing in a
        later milestone cannot silently vanish from the total.
        """
        conn = self._connect()
        return {
            row[0]: int(row[1])
            for row in conn.execute(
                "SELECT provenance, COUNT(*) FROM gr_dataflow "
                "GROUP BY provenance ORDER BY provenance"
            ).fetchall()
        }

    def count_gr_dataflow(self) -> int:
        """`COUNT(*) FROM gr_dataflow` -- the `total` `stats` reports on."""
        conn = self._connect()
        return int(conn.execute("SELECT COUNT(*) FROM gr_dataflow").fetchone()[0])

    def count_gr_by(self, column: str) -> dict[str | None, int]:
        """Grouped `gr` counts over one column, **NULL kept as its own key**.

        `stats` reports counts by `state`, `category`, `disposition` and
        `subject_provenance`, and for three of those four a NULL is a real
        and different fact from every non-NULL value:

        * a NULL `subject_provenance` means the row predates the derivation
          or never went through ingest;
        * a NULL `category` or `disposition` means nobody has triaged it.

        The key for those rows is Python `None`, never `''` and never folded
        into any real value. That is the whole reason this is a method rather
        than a `GROUP BY` written at the call site: `COALESCE(col, 'none')`
        is the natural thing to type and it silently merges a genuine
        `'none'` value with an absent one.

        A related and separately stated requirement: `stats` must count the
        NULL `subject` rows apart from the `llm_named` ones (the
        `gr_subject.SubjectDerivation` docstring, and the plan's ninth-round
        criterion). Those are two different columns -- `subject` and
        `subject_provenance` -- so `count_gr_by('subject_provenance')` gives
        the provenance split and `count_gr_null_subjects()` gives the
        absent-subject figure; neither is derivable from the other.

        Args:
            column: One of `_GR_GROUPABLE_COLUMNS`.

        Returns:
            `{value_or_None: count}`. Ordered with the `None` key last, so
            printing the mapping in iteration order puts the absent bucket at
            the end where it reads as one.

        Raises:
            ValueError: If `column` is not groupable. Refused rather than
                interpolated, both because the name reaches SQL and because a
                typo would otherwise answer with an empty grouping that looks
                exactly like an empty corpus.
        """
        if column not in _GR_GROUPABLE_COLUMNS:
            raise ValueError(
                f"{column!r} is not a groupable `gr` column; the groupable "
                f"set is {sorted(_GR_GROUPABLE_COLUMNS)}"
            )
        conn = self._connect()
        rows = conn.execute(
            f'SELECT "{column}", COUNT(*) FROM gr GROUP BY "{column}" '
            f'ORDER BY ("{column}" IS NULL), "{column}"'
        ).fetchall()
        return {row[0]: int(row[1]) for row in rows}

    def count_gr_null_subjects(self) -> int:
        """Requirements for which **no subject was locatable** at all.

        Counted apart from `llm_named` deliberately, and this is the method
        that makes that possible. `subject_provenance` records *which branch
        ran*; `subject IS NULL` records that the branch found nothing. A row
        can carry `subject_provenance = 'llm_named'` with a NULL `subject` --
        the fallback branch ran and `split_slots` could not locate a
        `[Subject]` span, because `pattern` is NULL or the template keyword
        is absent -- so folding the two together reports a model-named
        subject for a requirement that has none.
        """
        conn = self._connect()
        return int(
            conn.execute("SELECT COUNT(*) FROM gr WHERE subject IS NULL").fetchone()[0]
        )

    def gr_field_fill_counts(
        self, fields: tuple[str, ...] = GR_FILL_FIELDS
    ) -> dict[str, dict[str, int]]:
        """Per-column fill counts, backing `stats`' review-progress figures.

        Returns `{field: {"filled": n, "empty": n, "absent": n}}` where
        `absent` is `IS NULL`, `empty` is `= ''`, and `filled` is everything
        else. **Three numbers rather than one rate, and that is the decision
        this method exists to make.**

        `assumptions = ''` is a *real* value: Step 6a records that the
        extractor now always emits the key, sending `""` where the code
        assumes nothing beyond the statement, and ingest stores that `""` as
        it arrives. So for `assumptions` the honest fill numerator is
        `filled + empty` -- the field arrived -- and a rate computed as
        `filled / total` reports the exact opposite of the truth for the one
        column whose empty string is meaningful. For a free-text SME column
        (`rationale`, `fit_criterion`, `owner`) an empty string is a human
        who typed nothing and the numerator is `filled` alone.

        Returning the split rather than picking one numerator per column here
        is deliberate: a single `fill_rate` field would have to encode which
        rule it used, and the caller reporting review progress is the one
        that knows which question it is asking. In practice `empty` is zero
        for every column but `assumptions`, so the extra number costs a
        reader nothing and is the only thing standing between `assumptions`
        and a backwards figure.

        `modality_confirmed` is INTEGER `NOT NULL DEFAULT 0`, so it can never
        be `absent` and never be `empty`; it is reported through the same
        shape for uniformity, and `filled` there counts the rows carrying
        `1` **and** the rows carrying `0`, because `0` is a real value
        ("a human has not confirmed the modality") and not an absence. A
        caller wanting the confirmed count reads
        `count_gr_by('modality')`-style grouping or queries the column
        directly; it is not a fill question.

        Args:
            fields: Columns to report on. Defaults to `GR_FILL_FIELDS`, which
                is `set-field`'s accepted twelve.

        Raises:
            ValueError: If any name is not a `gr` column.
        """
        conn = self._connect()
        columns = frozenset(
            row[1] for row in conn.execute("PRAGMA table_info('gr')")
        )
        unknown = [f for f in fields if f not in columns]
        if unknown:
            raise ValueError(
                f"not `gr` columns: {sorted(unknown)}; fill counts are only "
                "defined over columns that exist"
            )
        out: dict[str, dict[str, int]] = {}
        for field in fields:
            row = conn.execute(
                f'SELECT SUM(CASE WHEN "{field}" IS NULL THEN 1 ELSE 0 END), '
                f"SUM(CASE WHEN \"{field}\" = '' THEN 1 ELSE 0 END), "
                f"COUNT(*) FROM gr"
            ).fetchone()
            absent = int(row[0] or 0)
            empty = int(row[1] or 0)
            total = int(row[2] or 0)
            out[field] = {
                "filled": total - absent - empty,
                "empty": empty,
                "absent": absent,
            }
        return out

    def count_gr_all_citations_excluded(self) -> int:
        """Requirements **every** one of whose citations is `excluded`.

        Step 3's own figure, deliberately **not** folded into
        `derived_ambiguous`: an all-`excluded` requirement means the corpus
        holds rules mined from code the analyst has since declared out of
        scope, which is a different fact from "no domain held a majority"
        even though both land in the same provenance bucket.

        One query rather than a cross-store join: `file_domains` and
        `gr_citation` are both in *this* database (the domain half predates
        the GR half here), so nothing has to be joined in Python.

        **A requirement with no citations at all does not count**, matching
        ingest's own `bool(citation_domains) and all(...)`: "every citation
        is excluded" is vacuously true over an empty set and would inflate
        the figure with rules that cite nothing. A citation whose path has no
        `file_domains` row is `unassigned`, not `excluded`, so the LEFT JOIN's
        NULL correctly fails the all-excluded test.

        The grain is **one entry per citation**, matching
        `gr_subject.derive_subject`'s contract, not per distinct file -- but
        the answer is the same either way for this predicate, since "all"
        over a multiset and over its support agree.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT c.gr_id FROM gr_citation c "
            "  LEFT JOIN file_domains f ON f.relative_path = c.relative_path "
            "  GROUP BY c.gr_id "
            "  HAVING COUNT(*) > 0 AND SUM(CASE WHEN f.domain = ? THEN 1 "
            "         ELSE 0 END) = COUNT(*)"
            ")",
            (_DOMAIN_EXCLUDED_SQL,),
        ).fetchone()
        return int(row[0])

    def list_gr_runs(self) -> list[GRRun]:
        """Every run's metadata row, newest `run_id` last.

        `run_id` carries a ULID after its `RUN-` prefix, so ordering by it is
        chronological. `complete` is **not** selected -- see
        `_GR_RUN_COLUMNS`; read it from `GRRun.complete`, which computes the
        generated column's own expression and therefore cannot disagree with
        `not_accounted_for`.
        """
        conn = self._connect()
        columns = ", ".join(f'"{c}"' for c in _GR_RUN_COLUMNS)
        rows = conn.execute(
            f"SELECT {columns} FROM gr_run ORDER BY run_id"
        ).fetchall()
        return [GRRun(**{k: r[k] for k in r.keys()}) for r in rows]

    def get_gr_run(self, run_id: str) -> GRRun | None:
        """One run's metadata row, or None if this store has no such run."""
        conn = self._connect()
        columns = ", ".join(f'"{c}"' for c in _GR_RUN_COLUMNS)
        row = conn.execute(
            f"SELECT {columns} FROM gr_run WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return GRRun(**{k: row[k] for k in row.keys()})

    def gr_finding_counts_by_severity(self) -> dict[str, dict[str, int]]:
        """`{severity: {"evaluated": n, "not_evaluated": n}}` over all rows.

        **The `evaluated` split is not decoration; `validate`'s exit code
        depends on it.** A finding carrying `evaluated = 0` is a check that
        could not be decided, never one that failed -- `gr_validator.
        can_approve` ignores exactly those -- so a `validate` that exited
        non-zero on the count of `ERROR` rows would refuse a corpus for
        checks nobody ran. Counting the two together would be the
        absent-versus-real defect in its exit-code form.
        """
        conn = self._connect()
        out: dict[str, dict[str, int]] = {}
        for severity, evaluated, count in conn.execute(
            "SELECT severity, evaluated, COUNT(*) FROM gr_finding "
            "GROUP BY severity, evaluated ORDER BY severity, evaluated"
        ).fetchall():
            bucket = out.setdefault(
                severity, {"evaluated": 0, "not_evaluated": 0}
            )
            bucket["evaluated" if evaluated else "not_evaluated"] += int(count)
        return out

    # -- the two `gr_run` writers Step 8 adds --------------------------
    #
    # These write `gr_run`, not `gr`, so the writer census does not see them
    # -- but they belong here anyway: the census is an enforcement of a
    # layering rule, not the rule itself, and one table's SQL living in one
    # place is the rule.

    def set_gr_run_coverage(
        self, run_id: str, *, not_accounted_for: int, measured_at: str
    ) -> None:
        """Record an independently **re-measured** coverage figure. Commits.

        `set-run-coverage`'s writer. Stamps `coverage_source = 'remeasured'`
        and `coverage_measured_at`, which is the whole point of the command
        being separate from `retire-run`: the audit question is "why did this
        run stop blocking the gate?", and this answers "because somebody
        actually went and measured it", with the timestamp of when.

        **A measurement that was not made cannot be recorded here.**
        `not_accounted_for` is `int` and not `int | None`: NULL in that column
        means "never measured" and is what the generated `complete` column
        keys off, so a command whose entire purpose is to assert that a figure
        was taken must refuse to write the encoding for "no figure was
        taken". Zero is a fine value and means the real thing -- measured,
        nothing left over.

        Raises:
            ValueError: on a `None` or negative `not_accounted_for`, an empty
                `measured_at`, or an unknown `run_id`. Refused at the method
                rather than left to the schema, which has no CHECK for any of
                these and would accept all three.
        """
        if not_accounted_for is None:  # type: ignore[unreachable]
            raise ValueError(
                "set_gr_run_coverage refuses to record a measurement that "
                "was not made: NULL `not_accounted_for` means 'coverage was "
                "never measured' and is exactly what this command exists to "
                "replace. Pass the measured count (0 is a real, valid "
                "measurement) or leave the run alone."
            )
        if not_accounted_for < 0:
            raise ValueError(
                f"not_accounted_for must be >= 0; got {not_accounted_for}"
            )
        if not measured_at or not measured_at.strip():
            raise ValueError(
                "coverage_measured_at is required: a re-measurement with no "
                "timestamp cannot answer when it was taken"
            )
        conn = self._connect()
        if conn.execute(
            "SELECT 1 FROM gr_run WHERE run_id = ?", (run_id,)
        ).fetchone() is None:
            raise ValueError(f"no run {run_id!r} in this store")
        conn.execute(
            "UPDATE gr_run SET not_accounted_for = ?, "
            "coverage_source = 'remeasured', coverage_measured_at = ? "
            "WHERE run_id = ?",
            (int(not_accounted_for), measured_at, run_id),
        )
        conn.commit()

    def retire_gr_run(self, run_id: str, *, reason: str) -> None:
        """Exclude a superseded run from the completeness gate. Commits.

        `retire-run`'s writer, and the second of `PR-54`'s two exits from the
        gate. It writes `gate_excluded = 1` and `gate_excluded_reason` and
        **leaves `not_accounted_for` -- and therefore the generated `complete`
        column -- untouched**, so the record still says what was actually
        known about the run. That asymmetry is the difference between the two
        commands: this one records a human's judgement that a run no longer
        counts, and overwriting the coverage figure while doing so would
        forge a measurement to justify the judgement.

        The reason is **required and non-empty**. The table's own CHECK
        enforces that, but a raw `CHECK constraint failed` names neither the
        column nor the question, so this refuses first with a message that
        does.

        Raises:
            ValueError: on an empty reason or an unknown `run_id`.
        """
        if not reason or not reason.strip():
            raise ValueError(
                "retire_gr_run requires a non-empty reason: the audit "
                "question is 'why did this run stop blocking the gate?', and "
                "a blank reason has no answer to it"
            )
        conn = self._connect()
        if conn.execute(
            "SELECT 1 FROM gr_run WHERE run_id = ?", (run_id,)
        ).fetchone() is None:
            raise ValueError(f"no run {run_id!r} in this store")
        conn.execute(
            "UPDATE gr_run SET gate_excluded = 1, gate_excluded_reason = ? "
            "WHERE run_id = ?",
            (reason, run_id),
        )
        conn.commit()

    def rollback(self) -> None:
        """Roll the open transaction back.

        The other half of `commit()`. Ingest is one transaction over the whole
        SQLite half of a run, so a failure must undo every table it touched —
        and a failed ingest leaves **no `gr_run` row at all**, which is what
        makes a retry a first ingest rather than a resume.
        """
        self._connect().rollback()

    def commit(self) -> None:
        """Commit the open transaction.

        Step 5's pair is ordered around a commit the *caller* owns — the SQL
        half inside it, the vector half after it — so a caller with no
        transaction machinery of its own needs one obvious way to say where
        that boundary is.
        """
        self._connect().commit()

    def close(self) -> None:
        """Close the database connection (mirrors `SQLiteStore.close`).

        Releases the WAL/SHM handles on Windows.
        """
        if self.conn:
            self.conn.close()
            self.conn = None


__all__ = ["GR_FILL_FIELDS", "KnowledgeStore"]
