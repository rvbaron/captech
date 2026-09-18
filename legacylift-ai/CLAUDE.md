# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LegacyLift analyzes legacy codebases and produces enterprise-grade documentation, requirements
and modernization plans, to accelerate modernization projects.

**Two versions ship from this repository, and an engagement uses one or the other.** They are
separate approaches, not layers of one product — v4 shares no component with v3.7 and does not run
its skills. Know which one a task is about before you start.

| | **v4** | **v3.7 — "legacylift-classic"** |
|---|---|---|
| Position | **Current approach** (`v4.0.0`) | Older approach, retained (`v3.7.0`) |
| Shape | A Python index, a data store, 10 commands, 7 agents, and a web UI | 18 Claude Code skills |
| Output | A queryable requirements store + generated markdown | Markdown documents |
| State between runs | Durable — human review accumulates | None — re-running overwrites |
| Choose it when | Accuracy and depth are what the engagement is buying | v4's prerequisites cannot be met, or cost outweighs accuracy |

**Where to start:**
- **v4 engineering work** → **[`docs/architecture.md`](./docs/architecture.md)** — the components,
  the contracts between them, and the decisions that are load-bearing.
- **v3.7 skill work** → **[`.claude/skills/legacylift-classic/README.md`](./.claude/skills/legacylift-classic/README.md)** —
  installation, the full skill inventory, and how to run it.
- **In-flight engineering work** → **[`docs/exec-plans/`](./docs/exec-plans/)** — see *Execution
  Plans* below. The plans are the definitive record of their own state.

**Supporting components**:
- `repos/` — Sample and test repositories used to develop and validate both versions

## LegacyLift v4 (current approach)

**Full architecture: [`docs/architecture.md`](./docs/architecture.md).** Read it before working on
any of the three components below — this section is orientation, not a substitute.

v4 is **three deployable components** over **three layers**:

| Component | Path | Is |
|---|---|---|
| The plugin | `.claude/skills/code-modernization/` | **Layer 2** — 10 `/modernize-*` commands, 7 specialist agents, 6 workflow scripts |
| `legacylift-search` | `tools/legacylift_search/` | **Layers 0–1** — a Python CLI that builds the code index and owns the knowledge store |
| `platform-ui` | `platform-ui/` | The read-only review surface — .NET 10 minimal API + Angular 21 |

**The load-bearing decision is the Layer 0 / Layer 1 boundary.** Layer 0 (`index.sqlite` + Chroma)
is machine-derived and rebuildable — files, symbols, chunks, graph edges. Layer 1
(`knowledge.sqlite`) holds human judgment — capability domains, generated requirements, citations
and review state — and must never be casually destroyed. `index --reset` rebuilds Layer 0 and stops
at that boundary.

**The boundary is logical, not physical.** Both stores live in the same place — `analysis/<system>/`
in a `legacy/`+`analysis/` workspace, `<repo>/legacylift-docs/` otherwise — so **clearing that
directory destroys domain tagging too**; re-run `tag-domains` before `map` if you have.

Three facts that are easy to get wrong:

- **Never write the client's source.** Where *generated* output lands depends on the layout, and
  the difference is load-bearing: in a `legacy/` + `analysis/` workspace it goes to
  `analysis/<system>/`, but on a plain checkout — including `repos/<system>/<unit>`, which is what
  this repository uses — it falls back to `<repo>/legacylift-docs/` **inside that checkout**
  (`config.py:resolve_index_dir` branch 4; see [`docs/architecture.md`](./docs/architecture.md) §2).
  No `/modernize-*` command passes `--analysis-dir`, so nothing overrides it. Either way the source
  files themselves are read-only, and `legacylift-docs/index/` is gitignored.
- **Re-running extraction merges, it does not replace.** Running it twice produces the same count
  the second time, not double. That is the single most important observable behaviour in v4.
- **No automated producer can approve a requirement.** `ingest` writes `draft`; `set-state` requires
  a named reviewer and refuses `approved` while any evaluated `ERROR` finding stands.

The commands, in order — each standalone, stop and review between any two:

```
preflight → assess → map → extract-rules → brief (human gate) → uplift | transform | reimagine → harden
```

`/modernize-status` is read-only and reports which of these have run and what is next.

---

## Execution Plans (in-flight work)

Multi-session engineering work is tracked as **ExecPlans**. The format is defined in
[`docs/exec-plan.md`](./docs/exec-plan.md) (there is no `PLANS.md` at the repo root), and every
ExecPlan is meant to be self-contained: a new agent should be able to read one top to bottom and
continue without other context.

- `docs/exec-plans/active/` — in progress. **Read the plan before touching the code it covers.**
- `docs/exec-plans/pending/` — designed but not started, plus design/decision records.
- `docs/exec-plans/completed/` — shipped; authoritative for standing design decisions.

**Current status: [`docs/execplans-status.md`](./docs/execplans-status.md)** — which plans are
active, what each covers, and the traps to know before opening one. **Start there** if you are
picking up in-flight work.

**Where status is recorded — two rules, and neither is optional:**

1. **A plan is the definitive record of its own state.** Milestone progress, measurements,
   acceptance numbers, review series and the next action belong *inside* the plan document. Record
   what you did there as you do it.
2. **Cross-plan status belongs in `docs/execplans-status.md`, never in this file.** `CLAUDE.md`
   describes what ExecPlans are and links to the status file; it must not accumulate milestone
   state. If you find yourself adding a date, a count or a "next action" here, it goes in the status
   file instead.

## LegacyLift v3.7 — "legacylift-classic" (retained)

The older approach: 18 documentation skills that read a legacy codebase and write interconnected
markdown with inline `file:line` citations, plus validators, an exporter, and the `fact-graph` skill
the others consume. It ships as a self-contained Claude Code plugin at
`.claude/skills/legacylift-classic/` and needs nothing from v4 — no index, no data store.

**None of it applies to v4**, which has no `SKILL.md` files, no `legacylift-docs/` *documentation* tree (v4 does use that directory, but only for its own index and knowledge store when there is no `analysis/` layout),
no 7-phase process and no `fact-graph`. Do not carry a convention from one into the other.

Two things worth knowing before reading further:

- **Skills are namespaced.** Every skill is invoked as `legacylift-classic:{skill-name}` —
  `/legacylift-classic:fact-graph`, or `claude --skill legacylift-classic:exec-summary-generator .`
  The bare names resolved only before v3.7.0, when these skills lived directly under
  `.claude/skills/`.
- **Output goes to `{repository}/legacylift-docs/`**, inside the analyzed repository — unlike v4,
  which writes to `analysis/<system>/`.

Everything else is documented in the plugin:

| Document | Carries |
|---|---|
| [`.claude/skills/legacylift-classic/README.md`](./.claude/skills/legacylift-classic/README.md) | Installation (copy the folder into `./.claude/skills/`), how it works, tech stack, example usage |
| [`.claude/skills/legacylift-classic/skills/README.md`](./.claude/skills/legacylift-classic/skills/README.md) | **The full skills inventory** — every skill, its type and its output file — plus the workflow diagram, the 7-phase process, and the fact-graph guide |
| `.claude/skills/legacylift-classic/skills/FACT-GRAPH-INTEGRATION.md` | How skills consume the fact-graph |
| `.claude/skills/legacylift-classic/skills/STATUS-REPORTING.md` | The status JSON contract |

## Model Configuration for Large Runs

Applies to **both versions**. Before running v3.7 documentation skills or the long v4 discovery
commands (`assess`, `map`, `extract-rules`), set an extended context window:

```bash
/model sonnet[1m]
```

---

## Test Repositories

The `repos/` directory contains codebases used to develop and validate both versions. They are
nested one level deep — the repository path is `repos/{system}/{unit}`, not `repos/{unit}`:

| Path | Stack | Purpose |
|---|---|---|
| `repos/ctcm/ctcm-api` | C# / .NET | REST API — SI/API documentation, the reference corpus for most skill work |
| `repos/ctcm/ctcm-db` | SQL Server | Database project (DDL, data scripts, SSRS) — data-model and table-validation work |
| `repos/ctcm/ctcm-web` | Angular / TypeScript | Front end — UI-side architecture docs |
| `repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app` | Java / Gradle (EAR, multi-module) | The NNG legacy application — the large-scale corpus behind the active ExecPlans |
| `repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.db.ETSPii` | SQL Server | NNG database scripts |

**`repos/nng-app-legacylift-analysis/` is gitignored in full** (`.gitignore:109`) — it is a
local-only working corpus, so a fresh clone has `repos/ctcm` and nothing else. Its sibling
`analysis*/` directories hold generated output, including corpora the ExecPlans describe as
unreproducible; do not delete or overwrite them.

To add a new test repository, clone it into `repos/` and run v4 commands or v3.7 skills against it.

---

## Environment Setup

Claude Code is configured with Direct Model Access. To get started using the **AI Lab** profile, follow [these instructions](https://github.com/captechconsulting/ailab-cookbook/blob/main/examples/Claude-Code.ipynb).

For significant **LegacyLift** development or to analyze client code, contact **Darrell Norton** for LL-specific credentials.

## Modifying the `code-modernization` Plugin (Apache 2.0 Attribution)

`.claude/skills/code-modernization/` is **v4's Layer 2** and is licensed under Apache 2.0 by
Anthropic. Whenever you modify **any** file in `.claude/skills/code-modernization/`, add (or update)
the following attribution line at the top of that file:

```
Modified by CapTech on [date]: [brief description].
```

- Use the current date (e.g., `2026-06-30`).
- Keep only the **latest** modification — do not accumulate a history. Overwrite the existing line rather than appending a new one.
- For markdown files with YAML frontmatter, place the line immediately after the frontmatter block; otherwise place it as the first line (as a comment appropriate to the file type, if applicable).
- The rule covers files **modified** from upstream. A file CapTech adds is not a modified
  upstream file and needs no such line.
- The plugin directory carries **two** licences and they are not interchangeable. `LICENSE` is the
  pristine upstream Apache text — **never edit it**; it is the copy §4(a) obliges us to give
  recipients. `LICENSE.md` is CapTech's, covering CapTech's modifications only, and is a
  byte-identical copy of the repository root's — **edit the root one and copy it over**, never the
  other way round. Attribution is in `NOTICE` (root), and the upstream commit this fork came from is
  in `.claude-plugin/.upstream`.
- Both duplications are CI-enforced by
  `tools/legacylift_search/tests/test_license_files_are_in_sync.py`. If it fails, the fix is to
  re-sync the copies — not to relax the test.

## Git Workflow

- Main branch: `main`
- Feature branches: `feature/{feature-name}`
- Bugfix branches: `fix/{issue-description}` or `bugfix/{issue-description}`
- Submit PRs for review before merging to main
