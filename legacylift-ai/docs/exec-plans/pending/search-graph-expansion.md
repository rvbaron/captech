# Expand hybrid search one hop along the code graph

> **Status: PENDING — a draft, not yet a conforming ExecPlan.** It has a Purpose, Context and a
> Plan of Work, but no acceptance numbers, because the one measurement that would set them (does a
> graph hop improve recall on a real query set, or just add noise?) has not been taken. **This file
> is the definitive record of its own state.**
>
> **Filed 2026-09-14**, from the pre-v4.0.0 review. It is a *documentation* defect that became a
> feature request: `docs/architecture.md` claimed for some time that hybrid search results were
> "optionally expanded one hop along the graph", and the config knob that would control it
> (`search.graph_neighbor_depth`) has existed since the search milestone — but nothing on the
> search path has ever read it. The doc claim was corrected in the same change that filed this
> draft; the capability it described is the subject here.

This document must be maintained in accordance with [`docs/exec-plan.md`](../../exec-plan.md).

## Purpose / Big Picture

After this change, a hybrid search can return the chunks that a matching chunk *calls* or *is
called by*, not only the chunks whose own text matched. The user-visible behavior: searching for a
business term finds the method that implements it **and** its immediate callers, which is how a
reader actually establishes that a rule is reachable from an entry point. Today that second step is
a separate, manual `legacylift-search callers <symbol>` per hit.

The reason this matters for LegacyLift specifically: `/modernize-extract-rules` mines rules out of
retrieved chunks, and a rule's citation is only trustworthy if the mining agent saw the call site,
not just the calculation. One hop is the difference between "this code computes a late fee" and
"this code computes a late fee and is called from the billing batch job."

## Progress

- [x] (2026-09-14) Filed. Defect confirmed: `graph_neighbor_depth` has no reader on the search
      path; the doc claim it implied was removed from `docs/architecture.md`.
- [ ] **M1 — decide whether the hop helps.** A recall/precision measurement on a real query set,
      before any implementation. See *The measurement this is blocked on*.
- [ ] **M2 — implement, if M1 says yes.** Expansion in `SearchEngine.search`, behind the existing
      config knob, default off.
- [ ] **M3 — surface it.** A `--graph-hops` flag, and a decision on whether the plugin's Layer-0
      retrieval contract uses it.

## Context and Orientation

**The search path.** `tools/legacylift_search/src/legacylift_search/search.py` (260 lines) holds
`SearchEngine`. `search()` (`:156`) runs two arms — `_vector_ranks` (`:58`, Chroma) and
`_lexical_ranks` (`:93`, SQLite FTS5/BM25) — and fuses them with Reciprocal Rank Fusion at
`:187`, using `rrf_rank_constant` (default 60). The result is a list of `SearchResult`, each
carrying a chunk and a snippet. Nothing in the module touches the graph.

**The graph that would be traversed** is already built and already queried by other commands:
`graph_edges` in `index.sqlite` holds one row per reference with a `kind` (`call`, `dispatch`,
`read`, `write`, `uses_table`, …), a `confidence` score, and either a resolved `callee_symbol_id`
or an unresolved `callee_name`. `legacylift-search callers` / `callees` read it directly. See
[`active/code-graph-construction.md`](../active/code-graph-construction.md) for how edges are
produced.

**The dead knob.** `search.graph_neighbor_depth` is declared at
`src/legacylift_search/config.py` in `SearchConfig` (default `1`) and appears in exactly one other
place, `tests/test_config.py`, which asserts its default. There is no reader. It was left in place
rather than deleted — unlike the `languages` block removed the same day — precisely because this
draft exists: the knob is the intended interface, not an orphan.

**Terms.** *Hop* — following one `graph_edges` row from a symbol to a neighbour. *Expansion* —
adding the neighbour's chunk to a result set it did not match into on its own. *Provenance* — for
an expanded hit, the record of which matched hit pulled it in and over which edge.

## The measurement this is blocked on

**Do not implement first.** The failure mode of graph expansion is that it dilutes precision
invisibly: a high-fan-in utility (`SecurityRoles.java` has 22 inbound referencers, per
[`completed/refresh-nng-analysis.md`](../completed/refresh-nng-analysis.md)) will be dragged into
almost every result set, pushing genuine matches below the limit. That is strictly worse than not
expanding, and it would not show up as an error.

What M1 must produce:

1. **A query set with known answers** — 20–30 queries against a tracked corpus (`repos/ctcm/ctcm-api`
   is the reference), each with the chunks a human judges relevant. This is the expensive part and
   it does not exist yet.
2. **Recall and precision@10, expanded vs. not**, on that set.
3. **A fan-in distribution** for the corpus, so the dilution risk is quantified rather than
   asserted: how many symbols have more than N inbound edges.
4. **A decision on edge confidence.** `graph_edges.confidence` is 0.85 for resolved references and
   0.30 for unresolved ones. Expanding over 0.30 edges means expanding over guesses — and note
   that an unresolved edge does *not* mean a bad edge (a real table with no indexed DDL resolves at
   0.30 too; see Milestone 26 of
   [`active/semantic-code-search-graph-index.md`](../active/semantic-code-search-graph-index.md)).

If the answer is "it does not help", the right outcome is to **delete `graph_neighbor_depth`** and
close this draft — that is a success, not a failure, and it costs one measurement instead of a
feature nobody trusts.

## Plan of Work (sketch — M2 only, contingent on M1)

- Expansion happens **after** fusion, never inside it: fuse the two arms as today, take the top
  `limit` survivors, then expand. Expanding before fusion would let graph neighbours compete for
  rank against text matches, which is the dilution failure above by construction.
- Expanded hits are **labelled**, not silently merged. A `SearchResult` gains provenance —
  which hit pulled it in, over which edge kind, at what confidence — so a caller (and the mining
  agent) can tell a text match from a neighbour. An unlabelled expansion would corrupt
  `/modernize-extract-rules`' citations, which must point at code that was actually read.
- `graph_neighbor_depth: 0` means off and is the **default**, whatever M1 concludes. The knob's
  current default of `1` is a declaration of intent from before the feature existed and must be
  changed to `0` when a reader is added. This is not hypothetical: a tracked per-repo manifest
  already sets it explicitly (`repos/ctcm/ctcm-api/semantic-search.manifest.json:87` →
  `"graph_neighbor_depth": 1`), so adding a reader without flipping the default would switch
  expansion **on** for that corpus the moment the code lands.
- Depth > 1 is out of scope. Two hops from a high-fan-in node is the whole corpus.

## Surprises & Discoveries

- Observation: the config knob predates any reader by the entire life of the search feature, and a
  documentation claim grew up around it as though it were implemented.
  Evidence: `git log -S graph_neighbor_depth` shows it arriving in `485a9566` ("Add Pydantic v2
  manifest models for semantic code search"), i.e. with `SearchConfig` itself. `git grep -n
  graph_neighbor_depth` finds no reader anywhere: `config.py:218` declares it,
  `tests/test_config.py:72` asserts its default, and every other hit is prose in a plan document.
- Observation: the capability is not actually missing, only unintegrated — `callers` and `callees`
  traverse the same graph today.
  Evidence: both are live CLI commands; `legacylift-search --help` lists them.

## Decision Log

- Decision: keep `search.graph_neighbor_depth` rather than delete it as dead config, and file this
  draft instead.
  Rationale: the `languages` block deleted the same day had no intended reader and no design behind
  it; this knob has both. Deleting it would have discarded the interface along with the gap.
  Date/Author: 2026-09-14 / maintainer.
- Decision: M1 is a measurement, not an implementation, and it gates M2 absolutely.
  Rationale: the plausible outcome is that expansion hurts. Implementing first would make the
  measurement a formality performed against sunk cost.
  Date/Author: 2026-09-14 / maintainer.

## Outcomes & Retrospective

Not started beyond filing.
