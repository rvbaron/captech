# platform-ui — a review surface for generated requirements

Milestone 1 of [`docs/exec-plans/pending/reqs-review-ui.md`](../docs/exec-plans/pending/reqs-review-ui.md):
a **read-only** web view over what the LegacyLift skills produce for a system —
the requirements store first, then the assessment, topology and domain tagging
around it.

Read-only is a design decision, not a shortfall. The store owns the approval
gate and every write path; this milestone proves the corpus is legible before
anything is allowed to change it. Where a write would go, the UI shows what the
store holds and says so.

## Running it

Two processes, no containers.

```bash
# 1. Copy the store + sidecars into data/ (re-run whenever the analysis tree changes)
python platform-ui/tools/prepare_data.py

# 2. API — http://localhost:5189
cd platform-ui/api && dotnet run

# 3. Web — http://localhost:4200 (proxies /api to the API)
cd platform-ui/web && npm install --legacy-peer-deps && npm start
```

From VS Code: open the `platform-ui` folder and run the **Platform UI (API +
Web)** compound launch configuration, which starts both. The
`prepare-data` task rebuilds the dataset.

`npm install` needs `--legacy-peer-deps` on this machine: npm 10.9.2's peer
resolver crashes on vitest 4's peer graph, which Angular 21 pulls in as its
default test runner.

## Stack

| Part | Choice |
|---|---|
| API | .NET 10 minimal API, `Microsoft.Data.Sqlite`, read-only connections |
| Web | Angular 21 LTS, Angular Material, mermaid 11, highlight.js, marked |
| Data | A copy of `knowledge.sqlite` plus files, under `data/` |

Angular 21 rather than 22 because 22 requires Node ≥ 22.22.3 and this machine
runs 22.17.1.

## The data approach — a copy, never the live tree

**platform-ui never reads an analysis tree. It reads a copy.**
`tools/prepare_data.py` copies the SQLite store and emits the JSON and markdown
sidecars that go with it into `data/`; the API is pointed at `data/` and has no
other source. Nothing in the app knows where an analysis tree is, or that one
exists.

```
                     prepare_data.py                    read-only
<workspace>/analysis/<system>/  ────────────►  platform-ui/data/  ────────►  API  ──►  web
  knowledge.sqlite              byte copy        <systemId>/knowledge.sqlite
  legacy/<system>/**            cited ranges     <systemId>/snippets.json
  domains.json, *.md, *.mmd     copy             <systemId>/{domains.json,docs,diagrams}
                                                 projects.json
```

Three reasons, all deliberate:

- **The live store is never opened.** `knowledge.sqlite` is copied
  byte-for-byte and read from the copy, so a UI bug, a SQLite lock or a stray
  write cannot reach Layer 1. On this corpus that matters twice over: the source
  store is the frozen 379/117 pair that Milestone 1.5 of the requirements plan
  compares against.
- **Only cited line ranges leave the analysis tree.** For each of the 383
  citations the script extracts that range plus eight lines of context into
  `snippets.json`. Whole client files are never copied, so the API cannot serve
  the source tree even by accident.
- **The UI has no dependency on the analysis layout.** It needs a data
  directory, not a workspace — which is what lets it run somewhere the client
  checkout is not.

The cost is that the view is a snapshot: re-run the script after any command
that changes the store, or the UI shows the previous run.

### What `data/` holds

```
data/
  projects.json                  the project/system catalog ("settings")
  <systemId>/
    knowledge.sqlite             byte copy of the Layer-1 store, opened read-only
    snippets.json                the cited line ranges only, with context
    domains.json                 the assess step's domain definitions
    docs/*.md                    ASSESSMENT, PREFLIGHT, and the stale pair
    diagrams/*.mmd               architecture, call graph, critical path, lineage
    TOPOLOGY.html                the map step's own interactive page
```

**`data/` is gitignored, and must stay that way.** Everything in it derives from
a client codebase. Rebuild it locally; never commit it.

### Pointing it at another engagement

```bash
python platform-ui/tools/prepare_data.py \
  --analysis-root /path/to/<workspace>          # holds analysis/ and legacy/
  --stale-docs-root /path/to/older/analysis     # optional; see below
```

Two things are **declared, not discovered**, and both describe the NNG demo and
nothing else. Edit them in `tools/prepare_data.py` for another engagement:

- **`SYSTEMS`** — the system ids to prepare, with the label and kind the UI
  shows. There is no scan of the analysis tree; a system absent from this list
  is absent from the dataset.
- **`PROJECT`** — the project id, client name, summary and the ordered `steps`
  the overview page renders as progress.

`--stale-docs-root` exists only because this corpus's `BUSINESS_RULES.md` and
`DATA_OBJECTS.md` were never re-rendered after the store landed; the only copies
sit in an older checkout outside the repo. Those two documents are shown
banner-flagged as predating the store, and when the path does not exist the copy
is skipped with a note — you lose two documents, not a working dataset.

## What the pages show

| Page | Source |
|---|---|
| Projects, project overview | `projects.json` + `/stats` |
| Requirements list | `gr` with server-side paging, FTS5 search, facet filters |
| Requirement detail | the whole `gr` row plus citations, findings, scenarios, edge cases, merge candidates |
| Review queue | `gr_merge_candidate` where `resolution = 'unresolved'` |
| Assessment, Preflight | the generated markdown |
| Graph | `ARCHITECTURE.mmd` + domains, with file counts from `file_domains` |
| Map | the three topology diagrams, plus `TOPOLOGY.html` in a frame |
| Data objects, Business rules | the stale June markdown, banner-flagged |
| Recommendation | an empty state — `/modernize-brief` has never been run |
| Requirement formats | the ten SPEC-1 sentence patterns |

## Two things the data made us get right

**A not-evaluated finding is not a violation.** 24 of the NNG store's 70 `ERROR`
rows carry `evaluated = 0` — checks that could not run because the statement
supplies no template to locate its slots. The store's approval gate is
`severity = 'ERROR' AND evaluated = 1`, so the UI counts them the same way: 44
rules are blocked, not 45, and a not-evaluated check is labelled **NOT RUN**
rather than coloured as an error. Folding the two together would have overstated
the blocked corpus by a quarter of its findings.

**A finding's `span` is often absent.** 41 of 287 findings carry a character
range into `statement`, and those are highlighted in place. The other 246 are
statement-wide and are listed beside the statement instead. The component only
ever draws the ranges it was given.

## Not in this milestone

Editing, state transitions, reviewer identity, merge resolution, bulk
operations. Each needs a write path, and a write path needs the reviewer
identity that `set_state` requires — which the review-UI plan says must be
answered by a design rather than bolted on.
