# Embed everything? — evaluate the 70% of chunks that never get a vector

**Status: DRAFT — not designed, not scheduled.** This file exists so that a large, measured, entirely
unevaluated tradeoff in Layer 0 is a *declared, deferred* deliverable rather than an assumption
inherited from a spike. It was raised while designing
[`active/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md): that plan is
about source the indexer never opens, and this one is about chunks the indexer opens, stores, and
then declines to embed.

This repository's ExecPlan conventions live in [`docs/exec-plan.md`](../../exec-plan.md). This draft is
**not yet a conforming ExecPlan** — no Plan of Work, no Concrete Steps, no acceptance criteria. Note
also that the deliverable here is most likely an *evaluation*, not a code change: the code to embed
everything already exists and is one config value away.

## The problem, stated as a measurement

`should_embed` (`embed_filter.py`) gives a chunk a dense vector when it clears `embed_min_tokens`
**or** when `has_business_logic` matches validation vocabulary, branching, or policy tokens.
`embed_min_tokens` defaults to `0` in code (`config.py:145`), which means embed everything — but
**every real manifest in this repository sets it to 80**, so the filter is on in practice on both
reference corpora.

Recomputing the partition over the stored chunks of both live indexes (measured 2026-09-01):

                            NNG app                    ctcm-api
        total chunks         15,040                     58,677
        >= 80 tokens          1,540  (10.2%)             3,444   (5.9%)
        rescued by logic      3,111  (20.7%)            13,768  (23.5%)
        NO VECTOR            10,389  (69.1%)            41,465  (70.7%)

Corroborated against the live Chroma stores rather than only the recomputation: NNG holds **4,651
vectors for 15,040 chunks (31%)**, ctcm-api **17,212 for 58,677 (29%)**. So roughly **seven chunks in
ten are absent from semantic search**, consistently across a Java/Spring application and a C# API.

Two secondary facts worth carrying into the design:

**The rescue path does most of the work.** More chunks are embedded because `has_business_logic`
matched (20.7% / 23.5%) than because they cleared the token floor (10.2% / 5.9%). The filter is, in
practice, a business-logic classifier with a size escape hatch — not a size filter with a
business-logic exception. Its regex vocabulary is therefore load-bearing and has never been evaluated
against anything.

**Deduplication is a separate, already-working saving.** `dedupe_by_text_sha` collapses identical
chunk text to one embedding and fans the vector back out to every member id, with no recall loss. It
saves 19.8% on NNG and 36.2% on ctcm-api and is not in question here.

## Why the saving is smaller than it looks

The filter drops small chunks by construction, so dropping 70% of chunks does not drop anything like
70% of tokens. Summing `token_count_estimate` over distinct chunk text:

                            embedded today    if embedded all      delta
        NNG app                   530,841            625,030    +94,189   (+18%)
        ctcm-api                1,088,904          1,343,731   +254,827   (+23%)

At Amazon Titan Embed Text v2 pricing (the provider both manifests configure) that is roughly
**$0.011 to $0.013 for NNG and $0.022 to $0.027 for ctcm-api.** The filter is discarding 70% of the
retrievable units of the corpus to save about half a cent per repository.

That framing is deliberately one-sided and the design conversation must supply the other side, which
is not money:

- **Wall clock on a local embedder.** The Titan API path runs at `max_concurrency: 16`. A local CPU
  embedder does not; at the measured Qwen rate of ~350 ms/chunk, NNG's additional 7,552 distinct
  chunks are roughly 44 minutes of extra indexing. That is the real cost, and it is paid by whoever
  is not using Bedrock.
- **Chroma index size and query latency** grow with vector count.
- **Precision.** More vectors means more candidates in top-k. A corpus where 70% of vectors are
  one-line getters may return worse results, not better, even as recall rises.

## The shape the answer has to take

**An evaluation, not a patch.** Flipping `embed_min_tokens` to `0` is a one-line manifest change; the
deliverable is the evidence that says whether to. That means:

**A query set with known-correct answers.** The candidates already exist in this repository: the
confirmed P0 rules from `/modernize-extract-rules` and their citations, and — once it lands — the
citation anchors of [`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md). Both give
"this query should retrieve this chunk" pairs that were produced independently of the embedding
filter.

**Both configurations, same corpus, same queries.** Index NNG and ctcm-api at `embed_min_tokens: 80`
and at `0`, then measure recall@k and precision@k on the same query set. The two corpora matter
because they are different stacks and the drop rate is suspiciously similar across them.

**A per-language answer, not one global verdict.** The dropped chunks are 97% Java on NNG and 100%
C# on ctcm-api — languages whose property/getter idiom produces exactly the tiny chunks the filter
targets. The right answer may well be a different floor per language rather than a single flag.

## Open questions the design conversation has to settle

**Whether recall is even the right metric.** A chunk with no vector is not unreachable: it remains in
SQLite and in the FTS5 index, and `symbols` lookups still find it. The module docstring is explicit
about this. So the honest question is not "can we find it" but "does the hybrid retriever find it as
well as a dense vector would" — and that requires evaluating the retriever, not the embedder.

**Whether `has_business_logic`'s vocabulary should be evaluated separately.** It is a hand-authored
regex list covering .NET DataAnnotations, Jakarta Bean Validation and pydantic. On a corpus in a
stack it does not enumerate, its rescue rate could fall to near zero and nobody would be told —
structurally the same blind spot `layer0-extraction-gap-detection.md` is about.

**Whether the default should change.** `config.py:145` says `0` and every real manifest says `80`. If
80 is the intended behavior the default is misleading; if 0 is, the manifests are drifting. One of
the two is wrong today regardless of how the evaluation comes out, and that is worth fixing whether
or not the rest of this plan proceeds.

## What must not happen

**Do not flip the flag on the strength of the cost table alone.** Half a cent is a real argument for
running the experiment and no argument at all for the outcome. Precision loss is the plausible harm
and it is unmeasured.

**Do not conflate "no vector" with "not indexed".** These chunks are fully present in SQLite and
FTS5. Any report or metric that counts them as missing — including any coverage percentage — would be
wrong in the same way the gap plan's percentages are wrong today.

**Do not evaluate on a corpus whose queries were written after seeing the results.** The value of the
extract-rules P0 citations as ground truth is precisely that they predate this question.

## Prior art in this repository

`docs/exec-plans/completed/domain-enhancements-plan.md` and the `domain-search-vector-recall-57` work
are the model: a suspected retrieval defect was settled by probing the real Titan collections at real
scale rather than by reasoning about the library's semantics, and the measurement overturned the
expected answer. The same discipline applies here — and note that issue #57's conclusion was pinned
to `chromadb 1.5.9`, which is still the pin in `pyproject.toml`.
