# legacylift-code-search

Local semantic, lexical, and graph code search indexer for LegacyLift v4.

This package provides the `legacylift-search` CLI for indexing a software
repository (Chroma vector store + SQLite metadata/graph/FTS) and querying it
with semantic, lexical, and call-graph commands.

For the full design and milestone plan see:

- `docs/exec-plans/active/semantic-code-search-graph-index.md`

## Installation

**Python 3.12 is required**, not merely recommended: `tree-sitter` 0.25.2 and
`tree-sitter-language-pack` 1.8.1 are what pin it, `.python-version` records the
same, and CI runs nothing else.

From the legacylift-ai repository root:

```
python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu   -e tools/legacylift_search
legacylift-search --help
```

The `--extra-index-url` is not optional housekeeping. `sentence-transformers`
pulls `torch`, and PyPI's default Linux wheel is the CUDA build at roughly
2.5 GB; nothing here needs it unless you are deliberately embedding on a GPU
(see *Running on GPU* below, which installs the CUDA wheel first, on purpose).

**Check that `legacylift-search --help` prints the command list and exits 0.**
With several Pythons on one machine the console script can end up in a `Scripts/`
directory belonging to an interpreter that does not have the package, where it
exits 1 with `ModuleNotFoundError: No module named 'legacylift_search'`. That
matters beyond this README: the `/modernize-*` commands invoke
`legacylift-search` from `PATH`, and when it fails they fall back to `grep`
rather than stopping, so a broken shim costs you Layer-0 retrieval quietly.
Where it cannot be put on `PATH`, every command accepts the documented fallback:

```
py -3.12 -m legacylift_search.cli <subcommand>
```

### Running the tests

The test framework is a `dev` extra rather than a runtime dependency, so install
it explicitly:

```
python -m pip install -e "tools/legacylift_search[dev]"
pytest -q
```

## Running on GPU

The slowest part of `legacylift-search index` on a real repo is the embedding
phase: the production `qwen3` embedder runs one Qwen3-Embedding-0.6B forward
pass per chunk. On CPU that is ~tens of ms per chunk (≈30–90 min for a large
.NET repo). On an NVIDIA GPU each pass is ~10–50× faster, so the same embed
finishes in single-digit minutes. The hash embedder used by tests is unaffected
and needs no GPU.

No code change is needed — `QwenEmbedder` already passes the configured device
to `sentence-transformers`, which auto-selects CUDA when it is available. The
work is entirely environmental: **the default install ships a CPU-only PyTorch**,
so a GPU box still embeds on CPU until you replace torch with a CUDA build.

### 1. Check whether the GPU is actually usable

```
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

- `...+cpu False` → CPU-only torch (the default). Continue to step 2.
- `...+cu124 True` (or similar) → CUDA is ready; skip to step 3.

### 2. Install a CUDA build of PyTorch

The CUDA wheels live on the PyTorch index, not PyPI, so pip needs an explicit
`--index-url`. Match the `cuXXX` tag to your installed driver/CUDA toolkit
(see https://pytorch.org/get-started/locally/ for the current matrix):

```
python -m pip install --upgrade --index-url https://download.pytorch.org/whl/cu124 torch
```

Then (optionally) add the HF acceleration helpers:

```
python -m pip install -e "tools/legacylift_search[gpu]"
```

Re-run the step 1 check and confirm `cuda.is_available()` is now `True`.

### 3. Point the indexer at the GPU

`device` defaults to `"auto"`, which lets `sentence-transformers` pick CUDA when
present — so once a CUDA torch is installed, no config change is required. To be
explicit (or to pin a specific card), set it in the repo manifest
(`semantic-search.manifest.json`):

```json
"embedding": {
  "provider": "qwen3",
  "model": "Qwen/Qwen3-Embedding-0.6B",
  "device": "cuda"
}
```

Accepted values follow PyTorch: `"auto"`, `"cpu"`, `"cuda"`, `"cuda:0"`, etc.
(On Apple Silicon, `"mps"` works but gives a smaller speedup than CUDA.)

### Requirements summary

- An NVIDIA GPU with a current driver. Qwen3-Embedding-0.6B is small
  (~0.6B params) — roughly **2–4 GB VRAM** is comfortable.
- A CUDA-enabled PyTorch wheel (step 2). This is the piece that is missing in a
  default install.
- Enough host RAM to hold the chunk batch; tune `embedding.batch_size` up on a
  GPU (the default 512 is reasonable) to keep the card busy.

GPU is the single biggest lever for embed time; it stacks with the
`chunking.embed_min_tokens` low-value filter and text-dedup that reduce how many
chunks need a forward pass in the first place.

## Hosted embedding (Amazon Bedrock)

`provider="api"` embeds via Amazon Bedrock instead of a local model, removing
per-host compute entirely (no GPU box, no multi-hour CPU pass). Install the
`aws` extra (`pip install -e .[aws]`) and set the Bedrock bearer token, then:

```jsonc
"embedding": {
  "provider": "api",
  "model": "amazon.titan-embed-text-v2:0",
  "dimension": 1024,
  "region": "us-east-2",
  "max_concurrency": 16
}
```

- Credentials come from the `AWS_BEARER_TOKEN_BEDROCK` environment variable,
  read automatically by botocore — the token is **never** stored in the
  manifest. The embedder fails with a clear message naming that variable if it
  is absent.
- `region` is explicit (`us-east-2`) and is **not** inherited from `AWS_REGION`.
- Titan embeds one text per request, so the embed phase is network-bound;
  `max_concurrency` issues that many `InvokeModel` requests in parallel (~16 is
  the sweet spot — higher invites throttling).
- The same provider serves query-time embedding, and `dimension` must match the
  Chroma collection — switching providers requires `--reset`. `vectors_present`
  checkpointing and `backfill-vectors` resumability carry over unchanged, so a
  network failure mid-run is resumable exactly like the local path.

## Status

Shipped and in use. Indexing, parsing, embedding, lexical and vector search,
the code graph, domain tagging and the requirements store are all real; the
"Wave 1 skeleton" this section used to describe was filled in long ago.

**1,263 tests across 62 modules** (`pytest --collect-only -q`, measured
2026-09-14). Re-measure rather than trusting this line — a test count copied
into a README is stale the week after it is written.

**Milestone state is not recorded here.** Which milestones are done, what is in
flight and what is next live in the ExecPlans, which are the definitive record
of their own state — see
[`docs/execplans-status.md`](../../docs/execplans-status.md) for the routing and
the two plans that own this package:
`docs/exec-plans/active/semantic-code-search-graph-index.md` (the Layer-0 index)
and `docs/exec-plans/active/reqs-to-data-store.md` (the requirements store).

### Repair commands

Both are resumable and process only what is missing, so they are safe to
re-run and safe to interrupt.

| Command | What it fills in |
|---|---|
| `backfill-vectors` | Dense vectors for chunks that have none — after an embedding provider change, or a run that was interrupted before the upsert finished. |
| `backfill-hashes` | `symbols.content_hash` for rows the version-2 migration left NULL. It **verifies each file's current on-disk `sha256` against `repo_files.sha256` first**, and leaves a drifted file's rows NULL rather than hashing source that never produced them; the next `index` run recovers those, because a drifted file is a changed file. Reports `symbols_hashed`, `symbols_skipped`, `files_drifted` and `remaining_null`. A plain `index` rerun will *not* do this — the skip-on-unchanged fast path never revisits an unchanged file. |

Both accept `--repo-root`, `--config`, `--index-dir` and `--analysis-dir`, with
the same precedence as every other command: `--index-dir` > `--analysis-dir` >
manifest.
