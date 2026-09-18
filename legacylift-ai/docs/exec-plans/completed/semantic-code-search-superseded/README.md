# Semantic Code Search — Superseded Spec (Archived)

> **⚠️ These documents are SUPERSEDED and retained for historical reference only. Do not implement from them.**

## What this is

The original design for LegacyLift's semantic/hybrid code search, authored on the
`feature/hybrid-code-search` branch (last updated **2026-03-23**). The branch was salvaged into
`feature/version-next` and then deleted; these five files are its only substantive content and are
preserved here so the early thinking isn't lost.

| File | What it was |
|---|---|
| `hybrid-code-search.md` | Goals, benefits, high-level requirements for hybrid (vector + lexical) search |
| `scs-exec-plan.md` | The original ExecPlan (proposed an `scs` CLI) |
| `language-extractor.md` | AST node-kind notes for building the caller→callee graph across 6 languages |
| `language-extractor.json` | Proposed extractor config (confidence weights, per-language node kinds) |
| `manifest.json` | Proposed index-manifest schema |

## What superseded it

The concept graduated into a delivered implementation and an updated design; use these instead:

- **Shipped tool:** [`tools/legacylift_search/`](../../../../tools/legacylift_search) — the working
  `legacylift-search` package (chunking, embeddings, hybrid search, graph, language extractors,
  domain tagging). Note the CLI is `legacylift-search`, not the `scs` name used in these old docs.
- **Current design:** [`../../active/semantic-code-search-graph-index.md`](../../active/semantic-code-search-graph-index.md)
  (and its `-additional-info.md` companion).
- **Delivered extractor profiles:** `tools/legacylift_search/src/legacylift_search/profiles/extractors.json`
  supersedes `language-extractor.json`/`.md`.
- **Delivered manifest:** `semantic-search.manifest.json` supersedes `manifest.json`.

Where the old docs and the shipped code disagree, **the shipped code is authoritative.**
