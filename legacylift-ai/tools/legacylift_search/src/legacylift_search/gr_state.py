"""The lifecycle transition function, and the `draft -> approved` gate.

Milestone 1, Step 4 of `docs/exec-plans/active/reqs-to-data-store.md` (the
gate) with the transition graph from Step 8, which is where the graph is
written down.

**`set_state` is the only writer of `gr.state`.** Step 9's `import_records` is
the single declared exception, for the reasons that step gives. Nothing else
may touch the column — not the CLI, not the extractor wiring, not any future
producer — because the gate lives inside this one function and a second write
path is a way around it. `tests/test_gr_state.py` asserts that set is
complete rather than trusting this paragraph.

**No automated producer can move a record out of `draft`.** `ingest` writes
`draft` and never anything else, so an extractor can never approve its own
output, and `reviewer` is required here with no default so no caller can omit
it by accident: an approved corpus that cannot say who approved each record
fails the exact audit claim the lifecycle exists to support, and identity is
the one thing in this schema that cannot be reconstructed after the fact.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Final

from .gr_refresh import refresh_gr_derived_sql, refresh_gr_vectors
from .knowledge_store import KnowledgeStore
from .models import Finding

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path

    from .embeddings import Embedder
    from .store import SQLiteStore

__all__ = [
    "ALLOWED_TRANSITIONS",
    "ApprovalBlockedError",
    "StateTransitionError",
    "set_state",
]


#: The whole lifecycle graph, as a literal mapping rather than scattered `if`
#: statements, so the legal set is readable in one place and a test can
#: enumerate it. Four things about it are decisions rather than mechanics:
#:
#: * **`draft -> approved` is permitted directly**, without passing through
#:   `reviewed`. Milestone 1 has no review queue, so requiring two calls to
#:   record one person's single act of reading and signing off would be
#:   ceremony, and the gate fires either way.
#: * **`reviewed` means "a human has read this and has not signed it off"** —
#:   a real state precisely because it is the one a queue sorts on.
#: * **Only `-> approved` is gated.** Nothing gates `draft`, and nothing gates
#:   `reviewed` either: a gated `reviewed` would make the state a reviewer
#:   moves *through* unreachable on exactly the rows that most need review.
#: * **`rejected -> draft` reopens** a rule someone rejected in error, and
#:   `superseded` is terminal because its successor is where the work
#:   continues — a record that could leave `superseded` would leave
#:   `superseded_by` pointing somewhere with no defined meaning.
ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "draft": frozenset({"reviewed", "approved", "rejected"}),
    "reviewed": frozenset({"approved", "rejected", "draft"}),
    "approved": frozenset({"superseded", "rejected"}),
    "rejected": frozenset({"draft"}),
    "superseded": frozenset(),
}


class StateTransitionError(ValueError):
    """A state move that `set_state` refused."""


class ApprovalBlockedError(StateTransitionError):
    """`-> approved` refused because SPEC-1 `ERROR` findings stand.

    Carries the blocking findings so a caller can name them by identifier and
    message: a raw refusal that names nothing tells a reviewer nothing.
    """

    def __init__(self, message: str, findings: list[Finding]) -> None:
        super().__init__(message)
        self.findings = findings


def set_state(
    store: KnowledgeStore,
    gr_id: str,
    to_state: str,
    reviewer: str,
    note: str | None = None,
    *,
    superseded_by: str | None = None,
    embedder: Embedder | None = None,
    index_store: SQLiteStore | None = None,
    repo_root: Path | None = None,
) -> None:
    """Record a human judgement about one requirement, enforcing the gate.

    Args:
        store: The durable knowledge store holding the `gr` tables.
        gr_id: The requirement to move.
        to_state: One of the five lifecycle states.
        reviewer: **Required, with no default.** Lands in `gr.reviewed_by`.
        note: Optional free text; lands in `gr.review_note`.
        superseded_by: Required when `to_state` is `superseded` — the `gr_id`
            of the successor, recorded on the record being superseded. It is
            deliberately **not** `derived_from`, which means "the rules this
            rollup summarizes" and nothing else; mixing supersession into that
            array would give it two meanings with no discriminator.
        embedder: Passed straight to `refresh_gr_vectors` (Step 5). **None is
            a supported, degraded success**: the state change lands in SQLite
            and in `gr_fts`, and the record's `gr_statements` metadata stays
            behind until `requirements reindex-vectors` runs. Step 8's CLI
            passes the configured embedder, which is why this is a keyword
            with a default rather than a required parameter — it must never
            become a reason a human's judgement fails to record.
        index_store: Passed to `refresh_gr_derived_sql`, whose validator
            re-run uses it for `V-STY-03`'s `leaked_terms`. None means no
            index; the check falls back to its morphological half.
        repo_root: Threaded to `refresh_gr_derived_sql` for the same reason
            that function declares it.

    Raises:
        StateTransitionError: unknown requirement, unknown or illegal
            transition, missing reviewer, missing successor, or the
            `pattern IS NOT NULL` schema precondition on approval.
        ApprovalBlockedError: `-> approved` with evaluated `ERROR` findings
            standing.

    A move to the state a record already holds is a **no-op** rather than an
    error, and must not stamp `reviewed_at` or `review_note` or bump
    `updated_at` — the same value-changing-write rule the merge applies, for
    the same reason.
    """
    if not reviewer or not reviewer.strip():
        raise StateTransitionError(
            "set_state requires a reviewer identity and refuses to run "
            "without one: an approved corpus that cannot say who approved "
            "each record fails the audit claim the lifecycle exists to make."
        )
    if to_state not in ALLOWED_TRANSITIONS:
        raise StateTransitionError(
            f"unknown state {to_state!r}; the five states are "
            f"{sorted(ALLOWED_TRANSITIONS)}"
        )

    record = store.get_gr(gr_id)
    if record is None:
        raise StateTransitionError(f"no requirement {gr_id!r} in this store")

    if record.state == to_state:
        return  # no-op: changes nothing, stamps nothing, bumps nothing

    if to_state not in ALLOWED_TRANSITIONS[record.state]:
        allowed = sorted(ALLOWED_TRANSITIONS[record.state]) or ["(terminal)"]
        raise StateTransitionError(
            f"{record.state!r} -> {to_state!r} is not an allowed transition; "
            f"from {record.state!r} the allowed moves are {allowed}"
        )

    if to_state == "superseded" and not superseded_by:
        raise StateTransitionError(
            "moving to 'superseded' requires the gr_id of the successor, "
            "which is recorded in gr.superseded_by on this record"
        )

    if to_state == "approved":
        _enforce_approval_gate(store, record.gr_id, record.pattern)

    now = datetime.now(timezone.utc).isoformat()
    store.apply_gr_state(
        gr_id,
        state=to_state,
        reviewed_by=reviewer,
        reviewed_at=now,
        review_note=note,
        superseded_by=superseded_by,
        updated_at=now,
    )
    # Step 5's refresh pair, in the one order every writer calls it in.
    #
    # **`set_state` calls the FULL pair, not the vector half alone**, even
    # though it writes no text. `state` is `gr_statements` metadata, so
    # skipping the vector half answers `search --semantic --state approved`
    # with rules still tagged `draft`, silently and forever. And on one row
    # the SQL half is one delete-and-insert plus one validator run — a call
    # site that calls half the pair on a per-site judgement about which halves
    # matter is exactly the reasoning that produces a half-synced store.
    #
    # `apply_gr_state` above has already committed, so the SQL half here opens
    # and commits its own savepoint and the ordering the pair exists to
    # enforce — SQLite durable before any vector is written — still holds.
    # Both are skipped by the no-op return above, per the value-changing-write
    # rule.
    #
    # The `EmbedResult` is deliberately dropped rather than returned: this
    # function's declared return type is `None`, and a degraded vector half is
    # reported by `gr_refresh.describe_vector_shortfall`, which the CLI runs
    # against the whole collection. That is the right place for it — a
    # per-call return value would say "this one record missed" while the
    # question a reviewer actually has is "is the collection behind."
    refresh_gr_derived_sql(store, [gr_id], index_store, repo_root)
    store.commit()
    refresh_gr_vectors(store, [gr_id], embedder=embedder)


def _enforce_approval_gate(
    store: KnowledgeStore, gr_id: str, pattern: str | None
) -> None:
    """Refuse `-> approved` on a NULL `pattern` or a standing `ERROR`.

    Two preconditions, in this order, and the order matters. The `pattern`
    precondition fires **first** because the `gr` table carries a CHECK behind
    it and a raw `CHECK constraint failed` message names no finding and tells
    a reviewer nothing. The CHECK is defence in depth, so a caller that
    somehow bypasses `set_state` still cannot write an approved row with a
    NULL `pattern`; this is the message a human actually sees.

    In practice the `pattern` precondition rarely fires alone, because a NULL
    `pattern` travels with a NULL `rule_class` and `V-CLASS-01` already blocks
    that as an `ERROR`.
    """
    if pattern is None:
        raise StateTransitionError(
            f"{gr_id} cannot be approved while `pattern` is NULL: SPEC-1 "
            "§S1.4 requires a notation template on every settled rule. Set "
            "one with `requirements set-field` first (a NULL `pattern` "
            "usually travels with a NULL `rule_class`, which V-CLASS-01 also "
            "blocks)."
        )
    blocking = [
        f
        for f in store.list_gr_findings(gr_id)
        if f.severity == "ERROR" and f.evaluated
    ]
    if blocking:
        named = "; ".join(f"{f.finding_id}: {f.message}" for f in blocking)
        raise ApprovalBlockedError(
            f"{gr_id} cannot be approved while "
            f"{len(blocking)} ERROR finding(s) stand — {named}",
            blocking,
        )
