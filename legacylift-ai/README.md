> ⚠️ **PROPRIETARY – HIGHLY SENSITIVE** ⚠️

> LegacyLift is CapTech intellectual property.
> This repository is not open source and may only be accessed and used by authorized CapTech personnel or clients under a specific Statement of Work.

---

# LegacyLift: AI-driven Requirements Reverse Engineering

**LegacyLift** analyzes legacy codebases and produces enterprise-grade documentation, requirements
and modernization plans, to accelerate modernization projects.

Two versions ship from this repository, and an engagement uses **one or the other**. They are
separate approaches, not layers of one product — v4 shares no component with v3.7 and does not run
its skills.

**The choice is accuracy against cost.** v4 is the current approach and produces the most accurate,
most detailed requirements reverse engineering available; it costs more to run and asks more of the
engagement. v3.7 is the older approach, yielding fewer requirements in less depth, and is kept for
clients who cannot or do not want to meet v4's prerequisites, or who would rather spend less than
get the most accurate result.

| | **LegacyLift v3.7 — "LegacyLift-classic"** | **LegacyLift v4** |
|---|---|---|
| Position | Older approach, retained | Current approach |
| Requirements produced | Fewer, less detailed | The most accurate and detailed available |
| Cost to run | Lower | Higher |
| Status | Released (`v3.7.0`) | Released (`v4.0.0`) |
| Shape | 18 Claude Code skills | A Python index, a data store, 10 commands, 7 agents, and a web review UI |
| Output | Markdown documents | Reviewable artifacts, a queryable requirements store, and generated markdown |
| State between runs | None — re-running overwrites | Durable — human review accumulates |
| Choose it when | v4's prerequisites cannot be met, or cost outweighs accuracy | Accuracy and depth are what the engagement is buying |

`/modernize-preflight` is the command that checks an estate against v4's prerequisites, and is the
first step of the v4 process below.

---

## LegacyLift v3.7 — "LegacyLift-classic"

The original documentation suite: 18 skills that read a legacy codebase and write interconnected
markdown with inline `file:line` citations — executive summary, system architecture, data model,
business rules, integration guide, use cases, user stories — plus validators, an exporter, and the
`fact-graph` skill that builds a shared JSON knowledge base the other skills consume.

It ships as a self-contained Claude Code plugin at
[`.claude/skills/legacylift-classic/`](./.claude/skills/legacylift-classic/). It needs nothing from
v4 — no index, no data store — which is what makes it the option for an estate that cannot meet
v4's prerequisites, and the cheaper one to run.

📖 **See [`.claude/skills/legacylift-classic/README.md`](./.claude/skills/legacylift-classic/README.md)**
for installation, the full skill inventory, and how to run it. Skills are invoked with the plugin
prefix — `/legacylift-classic:exec-summary-generator`.

---

## LegacyLift v4

v4 addresses the two things v3.7 could not do: it understands code without an LLM reading all of it,
and it *remembers*. Where v3.7 ends in a markdown file that the next run overwrites, v4 ends in a
store that accumulates.

### Three layers

**Layer 0 — the code index (disposable).** `legacylift-search`, a Python CLI, builds a local,
deterministic index of a repository and answers questions about it with no LLM in the loop: a
hashed file walk that classifies language and drops third-party code, tree-sitter symbol
extraction for 7 languages out of 15 it recognizes (the rest are indexed for retrieval, not
symbols), symbol-aware chunking, dense embeddings, and a call graph whose edges carry
confidence scores. Lives in `index.sqlite` plus a Chroma vector store, and is rebuildable at any time.

**Layer 1 — the knowledge store (durable).** `knowledge.sqlite` holds capability domains, generated
requirements with their citations and scenarios, and review state. A full re-index rebuilds Layer 0
from scratch and stops at this boundary — domain assignments, approved requirements and review notes
survive. That split is the load-bearing design decision of v4: machine-derived facts are cheap and
rebuildable, a reviewer's sign-off is not.

**Layer 2 — the agent surface.** 10 `/modernize-*` commands, 7 specialist agents and 6 workflow
scripts. None of the v3.7 skills are used here: v4 derives everything it needs from the source
repository and its own index.

### Install

Two components are required to run the commands, and they install separately. A third,
`platform-ui`, is optional and is only a review surface over what the first two produce.

**1. The plugin (Layer 2)** — copy it into the workspace you will analyze. It is a CapTech fork, so
installing `code-modernization` from the marketplace gets the stock Anthropic plugin instead, and if
both are present the marketplace copy silently wins:

```bash
# from the root of the workspace you will run the commands in
mkdir -p .claude/skills
cp -r /path/to/legacylift-ai/.claude/skills/code-modernization .claude/skills/
```

**2. `legacylift-search` (Layers 0–1)** — the index and the knowledge store. **Python 3.12** (3.14
will not work: `tree-sitter` 0.25.2 and its language pack are what pin it), and install torch from
the CPU wheel index unless you specifically want GPU embedding — PyPI's default Linux torch wheel is
the CUDA build, about 2.5 GB:

```bash
# from the root of THIS repository
python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu   -e tools/legacylift_search
legacylift-search --help   # must print the command list, not a traceback
```

That last line is the check that matters. The `/modernize-*` commands invoke `legacylift-search`
from `PATH`; if the console script resolves into a Python installation that does not have the
package (easy to do with several Pythons on one machine), it exits non-zero and Layer-0 retrieval
silently degrades to `grep`. Where you cannot get it onto `PATH`, the documented fallback is
`py -3.12 -m legacylift_search.cli <subcommand>`, which the commands accept everywhere.

**3. `platform-ui`** (optional) — the read-only review surface, .NET 10 + Angular 21. It reads a
prepared snapshot rather than an analysis tree; [`platform-ui/README.md`](./platform-ui/README.md)
is the definitive account of building it and preparing its data.

📖 Per-component detail: [`.claude/skills/code-modernization/README.md`](./.claude/skills/code-modernization/README.md)
and [`tools/legacylift_search/README.md`](./tools/legacylift_search/README.md).

### The process

**1. Discover** — four commands, each producing a standalone artifact with `file:line` citations
that a client can review before committing to a rebuild:

| Command | Answers |
|---|---|
| `/modernize-preflight` | Is the estate ready to analyze? |
| `/modernize-assess` | What is here? — inventory, complexity, COCOMO scale |
| `/modernize-map` | How does it fit together? — topology, call graphs, data lineage |
| `/modernize-extract-rules` | What does the business require? — mined rules, each cited |

**2. Decide** — `/modernize-brief` turns those artifacts into a phased plan and recommends which
build method fits. **This is a human approval gate**: a steering committee decides with evidence
rather than with a vendor's estimate.

**3. Build** — one of three *methods*, not three tools:

| Command | Method | Equivalence proved by |
|---|---|---|
| `/modernize-uplift` | Same stack, version bump (.NET 4.8 → .NET 8) | One test suite run on both runtimes |
| `/modernize-transform` | One module, cross-stack, strangler fig | Characterization tests |
| `/modernize-reimagine` | Greenfield rebuild from extracted intent | Executable acceptance tests |

`uplift` exists because the common real case — a supported-version bump — is the one `transform`
gets wrong by rewriting. If its delta catalog shows most of the code is forced to change anyway, it
says so and hands off.

**4. Harden** — `/modernize-harden` runs a security pass on the still-running legacy system.

### Requirements as data, not prose

The largest body of work in v4. Extraction used to end in a markdown file: run it again and every
human correction, sign-off and rejection was gone. v4 replaces the file with a store — each rule
becomes a record with a stable identifier, citations back to the lines it was mined from, a review
lifecycle, and a notation strict enough to validate (ISO/IEC/IEEE 29148 supplies the sentence
skeleton, OMG SBVR the modal keyword, across ten closed patterns). Re-running extraction merges into
the store, so review accumulates. Markdown becomes a report generated from the store.

📖 **Full engineering briefing**: open
[`docs/legacylift-v4-overview/index.html`](./docs/legacylift-v4-overview/index.html) in any browser —
self-contained, no server or build step. Every figure in it was measured in this repository.
In-flight work is tracked as ExecPlans; [`docs/execplans-status.md`](./docs/execplans-status.md)
says which are active and what each covers.

---

*Empower your legacy modernization with AI-driven clarity and speed.*
